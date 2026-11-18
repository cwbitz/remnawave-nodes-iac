"""Coverage for ``scripts/audit_example_knobs.py``.

The fixture is a snapshot of the project's own tracked tree, so the suite follows
the knob inventory instead of duplicating it: the audit must pass on the tree as
committed, and must fail when a grouped example knob is dropped or a flat example
knob drifts from its default.
"""
from __future__ import annotations

import pathlib
import re

NESTED_KEY = re.compile(r"^(\s+)([a-z_][a-z0-9_]*):")


def example_path(root: pathlib.Path) -> pathlib.Path:
    matches = [
        path
        for path in root.rglob("main.yml")
        if path.parent.name == "example" and path.parent.parent.name == "host_vars"
    ]
    assert matches, "the tracked tree carries no host_vars/example/main.yml"
    return matches[0]


def nested_knob_lines(root: pathlib.Path) -> list[tuple[int, str]]:
    """Line index and key of every nested (grouped) knob line in the example."""
    lines = example_path(root).read_text(encoding="utf-8").splitlines(keepends=True)
    entries = []
    for index, line in enumerate(lines):
        match = NESTED_KEY.match(line)
        if match:
            entries.append((index, match.group(2)))
    return entries


def test_audit_passes_on_the_tracked_tree(run_python_at, tracked_snapshot):
    result = run_python_at(tracked_snapshot, "audit_example_knobs.py", tracked_snapshot)

    assert result.returncode == 0, result.stdout + result.stderr


def test_dropping_a_grouped_example_knob_is_reported(run_python_at, tracked_snapshot):
    example = example_path(tracked_snapshot)
    original = example.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    for index, key in nested_knob_lines(tracked_snapshot):
        example.write_text("".join(lines[:index] + lines[index + 1:]), encoding="utf-8")
        result = run_python_at(tracked_snapshot, "audit_example_knobs.py", tracked_snapshot)
        example.write_text(original, encoding="utf-8")
        if result.returncode == 1:
            assert key in result.stdout, result.stdout
            return

    raise AssertionError("dropping a grouped example knob never failed the audit")


def test_drifting_a_flat_example_value_is_reported(run_python_at, tracked_snapshot):
    example = example_path(tracked_snapshot)
    original = example.read_text(encoding="utf-8")

    example.write_text(
        original.replace('remnanode_node_port: ""', 'remnanode_node_port: "2222"'),
        encoding="utf-8",
    )
    result = run_python_at(tracked_snapshot, "audit_example_knobs.py", tracked_snapshot)
    example.write_text(original, encoding="utf-8")

    assert result.returncode == 1, result.stdout
    assert "remnanode_node_port" in result.stdout, result.stdout
