"""Alloy push wiring: the write-endpoint URL contract.

The role keeps the knobs as base URLs and appends the receiver paths in the
templates. A value that already carries one of those paths would be sent twice,
so the knob gate rejects it; this suite pins both behaviours.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "roles" / "monitoring" / "templates" / "monitoring" / "config.alloy.j2"
SCHEMA = ROOT / "inventory" / "knob_schema.yml"


def test_both_push_urls_take_a_base_url() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    assert 'url = "{{ loki_push_url }}/loki/api/v1/push"' in template
    assert 'url = "{{ prometheus_remote_write_url }}/api/v1/write"' in template


def test_the_schema_rejects_a_remote_write_url_with_the_appended_path() -> None:
    schema = SCHEMA.read_text(encoding="utf-8")
    assert "regex_replace('/+$', '')" in schema
    assert "is not search('/api/v1/write$')" in schema
