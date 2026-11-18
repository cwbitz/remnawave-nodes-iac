#!/usr/bin/env python3
"""Audit inventory/host_vars/example/main.yml against the knob cascade.

`make host-init` copies the example (comment-free) to
``inventory/host_vars/<host>/main.yml``, so the example is the template for every
new host and must mirror every operator knob with its project default. The
operator knobs are grouped mappings; their defaults live in
``inventory/group_vars/**/*.yml`` as ``<group>_defaults`` and the flat variables
the roles consume are derived from ``<group>_cfg``. This audit (run by
``make lint`` / CI) keeps that true:

* **Groups** — every ``<group>_defaults`` mapping has a top-level ``<group>`` in
  the example and a matching key in ``inventory/knob_schema.yml`` (and vice
  versa).
* **Presence** — every key of the defaults mapping is present at the same path
  in the example, and the example declares no key the defaults do not.
* **Value** — a scalar or flow-collection example value must equal the default,
  so scaffolding a host is behaviour-neutral. A block sequence or nested mapping
  is presence-checked only.

Standard library only (like the other scripts/), so a plain `python3` can run it.

Usage: audit_example_knobs.py [repo root]      # exit 1 with a report on failure
"""
from __future__ import annotations

import glob
import os
import re
import sys

KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:\s+(.*))?$")
SCHEMA_RE = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_]*):")


def strip_inline_comment(raw: str) -> str:
    """Drop a trailing ` # comment` that is outside quotes."""
    quote = ""
    for index, char in enumerate(raw):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or raw[index - 1].isspace()):
            return raw[:index]
    return raw


def split_top_level(text: str) -> list[str]:
    """Split a flow collection body on commas that are outside quotes."""
    items, current, quote, depth = [], "", "", 0
    for char in text:
        if quote:
            current += char
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
            current += char
        elif char in "[{":
            depth += 1
            current += char
        elif char in "]}":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            items.append(current)
            current = ""
        else:
            current += char
    if current.strip():
        items.append(current)
    return items


def parse_scalar(raw: str):
    """Parse the YAML subset used by the knob values; None = block/nested."""
    text = strip_inline_comment(raw).strip()
    if text == "":
        return None
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if text == "{}":
        return {}
    if text.startswith("[") and text.endswith("]"):
        body = text[1:-1].strip()
        return [parse_scalar(item) for item in split_top_level(body)] if body else []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        return text


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _skip_block(lines: list[str], index: int, indent: int) -> int:
    while index < len(lines) and _indent(lines[index]) >= indent:
        index += 1
    return index


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[dict, int]:
    result: dict = {}
    while index < len(lines):
        line = lines[index]
        current = _indent(line)
        if current < indent:
            break
        if current > indent:
            index += 1
            continue
        match = KEY_RE.match(line.strip())
        if not match:
            index += 1
            continue
        key = match.group(1)
        rest = (match.group(2) or "").strip()
        index += 1
        if rest and rest[0] not in ">|":
            result[key] = parse_scalar(rest)
            continue
        if index >= len(lines) or _indent(lines[index]) <= current:
            result[key] = None
            continue
        if lines[index].strip().startswith("- "):
            result[key] = None
            index = _skip_block(lines, index, _indent(lines[index]))
            continue
        result[key], index = _parse_block(lines, index, _indent(lines[index]))
    return result, index


def parse_mapping(path: str) -> dict:
    """Parse the indented block-mapping subset of a YAML file."""
    lines: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or stripped == "---":
                continue
            lines.append(raw.rstrip())
    value, _ = _parse_block(lines, 0, 0)
    return value


def schema_keys(root: str) -> set[str]:
    """Return the top-level keys of operator_knob_schema (stdlib only)."""
    path = os.path.join(root, "inventory/knob_schema.yml")
    if not os.path.isfile(path):
        return set()
    keys = set()
    in_schema = False
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("operator_knob_schema:"):
                in_schema = True
                continue
            if not in_schema:
                continue
            if line.strip() and not line[0].isspace():
                break
            match = SCHEMA_RE.match(line)
            if match:
                keys.add(match.group(1))
    return keys


def declared_groups(root: str) -> dict[str, tuple[dict, str]]:
    """Return the <group>_defaults mappings declared in group_vars."""
    groups: dict[str, tuple[dict, str]] = {}
    pattern = os.path.join(root, "inventory/group_vars/*/*.yml")
    for path in sorted(glob.glob(pattern)):
        for key, value in parse_mapping(path).items():
            if not key.endswith("_defaults") or not isinstance(value, dict):
                continue
            groups[key[: -len("_defaults")]] = (value, os.path.relpath(path, root))
    return groups


def compare(prefix: str, defaults: dict, example: dict, problems: list[str]) -> int:
    """Compare one group mapping recursively; return the number of knobs seen."""
    seen = 0
    for key, default in defaults.items():
        path = f"{prefix}.{key}" if prefix else key
        seen += 1
        if key not in example:
            problems.append(f"{path}: missing from the example (default {default!r})")
            continue
        actual = example[key]
        if isinstance(default, dict):
            if not isinstance(actual, dict):
                problems.append(f"{path}: must be a mapping in the example")
            else:
                seen += compare(path, default, actual, problems)
        elif default is not None and actual is not None and actual != default:
            problems.append(f"{path}: example value {actual!r} != default {default!r}")
    for key in example:
        if key not in defaults:
            path = f"{prefix}.{key}" if prefix else key
            problems.append(f"{path}: not declared in the project defaults")
    return seen


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else os.getcwd()
    example = os.path.join(root, "inventory/host_vars/example/main.yml")
    if not os.path.isfile(example):
        print(f"ERROR: {example} does not exist", file=sys.stderr)
        return 1

    groups = declared_groups(root)
    example_groups = parse_mapping(example)
    schema = schema_keys(root)

    problems: list[str] = []
    for key in sorted(example_groups.keys() - schema):
        problems.append(f"{key}: present in the example but missing from inventory/knob_schema.yml")
    for key in sorted(schema - example_groups.keys()):
        problems.append(f"{key}: in inventory/knob_schema.yml but not the example")
    for key in sorted(example_groups.keys() - groups.keys()):
        problems.append(f"{key}: has no <group>_defaults mapping in inventory/group_vars")
    for key in sorted(groups.keys() - example_groups.keys()):
        problems.append(f"{key}: has a <group>_defaults mapping but no example section")

    knobs = 0
    for name, (defaults, source) in sorted(groups.items()):
        if name not in example_groups:
            continue
        if not isinstance(example_groups[name], dict):
            problems.append(f"{name}: must be a mapping in the example ({source})")
            continue
        knobs += compare(name, defaults, example_groups[name], problems)

    if problems:
        print(f"audit_example_knobs: {len(problems)} problem(s) in {example}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"audit_example_knobs: OK ({len(groups)} groups, {knobs} knobs checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
