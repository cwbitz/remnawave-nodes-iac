"""Curated Alloy counters parsed by the opt-in push verification.

The role keeps the patterns in ``roles/monitoring/vars/main.yml`` and applies
them to Alloy's own ``/metrics`` output. This suite runs them against a
realistic exposition body (taken from ``grafana/alloy`` v1.18.x), so a pattern
that stops matching - or that reads a counter which moves before the receiver
acknowledges the write - fails here instead of on a live node.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VARS = ROOT / "roles" / "monitoring" / "vars" / "main.yml"
TEMPLATE = ROOT / "roles" / "monitoring" / "templates" / "monitoring" / "config.alloy.j2"
KNOBS = ROOT / "inventory" / "group_vars" / "all" / "knobs.yml"
SCHEMA = ROOT / "inventory" / "knob_schema.yml"
COMPOSE = ROOT / "roles" / "monitoring" / "templates" / "monitoring" / "docker-compose.yml.j2"
RECEIVER = ROOT / "roles" / "monitoring" / "templates" / "monitoring" / "verify-receiver.conf.j2"
TASKS = ROOT / "roles" / "monitoring" / "tasks" / "main.yml"

LABELS = (
    'component_id="prometheus.remote_write.central",component_path="/",'
    'remote_name="720d31",url="http://central.example:9090/api/v1/write"'
)

METRICS = f"""\
# HELP prometheus_remote_storage_queue_highest_sent_timestamp_seconds Highest timestamp successfully sent by this queue, in seconds since epoch. Initialized to 0 when no data has been sent yet.
# TYPE prometheus_remote_storage_queue_highest_sent_timestamp_seconds gauge
prometheus_remote_storage_queue_highest_sent_timestamp_seconds{{{LABELS}}} 1.795267833e+09
# HELP prometheus_remote_storage_queue_highest_timestamp_seconds Highest timestamp that was enqueued, in seconds since epoch. Initialized to 0 when no data has been received yet.
# TYPE prometheus_remote_storage_queue_highest_timestamp_seconds gauge
prometheus_remote_storage_queue_highest_timestamp_seconds{{{LABELS}}} 1.795267833e+09
# HELP prometheus_remote_storage_samples_total Total number of samples sent to remote storage.
# TYPE prometheus_remote_storage_samples_total counter
prometheus_remote_storage_samples_total{{{LABELS}}} 8424
# HELP prometheus_remote_storage_samples_failed_total Total number of samples which failed on send to remote storage, non-recoverable errors.
# TYPE prometheus_remote_storage_samples_failed_total counter
prometheus_remote_storage_samples_failed_total{{{LABELS}}} 0
# HELP prometheus_remote_storage_samples_dropped_total Total number of samples which were dropped after being read from the WAL before being sent via remote write.
# TYPE prometheus_remote_storage_samples_dropped_total counter
prometheus_remote_storage_samples_dropped_total{{{LABELS},reason="too_old"}} 0
# HELP loki_write_dropped_entries_total Total number of dropped entries.
# TYPE loki_write_dropped_entries_total counter
loki_write_dropped_entries_total{{component_id="loki.write.central",component_path="/",host="central.example:3100",reason="ingester_error"}} 0
loki_write_dropped_entries_total{{component_id="loki.write.central",component_path="/",host="central.example:3100",reason="queue_is_full"}} 0
"""


def pattern(name: str) -> str:
    text = VARS.read_text(encoding="utf-8")
    match = re.search(rf"^{name}: '(.*)'$", text, re.MULTILINE)
    assert match, f"{name} is not declared in roles/monitoring/vars/main.yml"
    return match.group(1)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("alloy_acked_push_re", 1.795267833e09),
        ("alloy_dropped_samples_re", 0.0),
        ("alloy_dropped_entries_re", 0.0),
    ],
)
def test_pattern_sums_every_series(name: str, expected: float) -> None:
    values = re.findall(pattern(name), METRICS)
    assert values
    assert sum(float(value) for value in values) == expected


def test_pattern_ignores_help_and_type_lines() -> None:
    assert re.findall(pattern("alloy_acked_push_re"), METRICS) == ["1.795267833e+09"]


def test_acknowledgement_pattern_ignores_the_enqueued_timestamp() -> None:
    values = re.findall(pattern("alloy_acked_push_re"), METRICS)
    assert values == ["1.795267833e+09"]
    enqueued_only = (
        "prometheus_remote_storage_queue_highest_timestamp_seconds"
        f"{{{LABELS}}} 1.795267833e+09\n"
    )
    assert re.findall(pattern("alloy_acked_push_re"), enqueued_only) == []


def test_acknowledgement_pattern_ignores_the_pre_store_sample_counter() -> None:
    assert re.findall(pattern("alloy_acked_push_re"), f"prometheus_remote_storage_samples_total{{{LABELS}}} 8424\n") == []


def test_unacknowledged_push_sums_to_zero() -> None:
    body = f"prometheus_remote_storage_queue_highest_sent_timestamp_seconds{{{LABELS}}} 0\n"
    values = re.findall(pattern("alloy_acked_push_re"), body)
    assert sum(float(value) for value in values) == 0


def test_dropped_pattern_counts_failed_and_dropped_samples() -> None:
    body = (
        f"prometheus_remote_storage_samples_failed_total{{{LABELS}}} 2\n"
        f'prometheus_remote_storage_samples_dropped_total{{{LABELS},reason="too_old"}} 1\n'
        f"prometheus_remote_storage_samples_total{{{LABELS}}} 8424\n"
    )
    values = re.findall(pattern("alloy_dropped_samples_re"), body)
    assert sorted(values) == ["1", "2"]


def test_both_push_urls_take_a_base_url() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    assert 'url = "{{ loki_push_url }}/loki/api/v1/push"' in template
    assert 'url = "{{ prometheus_remote_write_url }}/api/v1/write"' in template


def test_the_schema_rejects_a_remote_write_url_with_the_appended_path() -> None:
    schema = SCHEMA.read_text(encoding="utf-8")
    assert "regex_replace('/+$', '')" in schema
    assert "is not search('/api/v1/write$')" in schema


def test_local_receiver_defaults_off() -> None:
    assert re.search(
        r'verify_receiver:\n\s+mode: "disabled"\n\s+port: 3100\n',
        KNOBS.read_text(encoding="utf-8"),
    )


def test_local_receiver_is_loopback_only() -> None:
    assert (
        "alloy_verify_receiver_address: \"{{ '127.0.0.1:' ~ alloy_verify_receiver_port }}\""
        in KNOBS.read_text(encoding="utf-8")
    )
    conf = RECEIVER.read_text(encoding="utf-8")
    assert "listen {{ alloy_verify_receiver_address }};" in conf
    assert "0.0.0.0" not in conf


def test_local_receiver_acknowledges_both_write_paths() -> None:
    conf = RECEIVER.read_text(encoding="utf-8")
    for path in ("/api/v1/write", "/loki/api/v1/push"):
        assert re.search(rf"location = {re.escape(path)} \{{\s*return 2[0-9][0-9];", conf), path


def test_local_receiver_derives_both_push_urls() -> None:
    knobs = KNOBS.read_text(encoding="utf-8")
    assert knobs.count("('http://' ~ alloy_verify_receiver_address)") == 2


def test_local_receiver_verifies_the_push_automatically() -> None:
    knobs = KNOBS.read_text(encoding="utf-8")
    block = re.search(r"alloy_verify_push: >-\n(?:\s+.*\n)+", knobs)
    assert block, "alloy_verify_push derivation is missing"
    assert "alloy_verify_receiver_enabled | bool" in block.group(0)


def test_local_receiver_joins_the_monitoring_compose_project() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "{% if alloy_verify_receiver_enabled | bool %}" in compose
    assert "container_name: alloy-verify-receiver" in compose
    assert "./verify-receiver.conf:/etc/nginx/conf.d/default.conf:ro" in compose


def test_verification_compares_against_a_baseline() -> None:
    tasks = TASKS.read_text(encoding="utf-8")
    baseline = tasks.index("monitoring_alloy_metrics_baseline")
    waited = tasks.index("until: >-\n    (monitoring_alloy_metrics.status")
    assert baseline < waited, "the counters must be snapshotted before waiting"
    assert "> (monitoring_alloy_ack_baseline | float)" in tasks
    assert "<= (monitoring_alloy_dropped_samples_baseline | float)" in tasks
    assert "<= (monitoring_alloy_dropped_entries_baseline | float)" in tasks


def test_verification_does_not_require_cumulative_counters_to_be_zero() -> None:
    tasks = TASKS.read_text(encoding="utf-8")
    assert "alloy_dropped_samples_re)) | map('float') | sum) == 0" not in tasks
    assert "alloy_dropped_entries_re)) | map('float') | sum) == 0" not in tasks
    assert "alloy_acked_push_re)) | map('float') | sum) > 0" not in tasks
