#!/usr/bin/env python3
"""Audit inventory/host_vars/example/main.yml against the project's knobs.

`make prep` copies the example (comment-free) to
``inventory/host_vars/<host>/main.yml``, so the example is the template for every
new host and must carry every operator knob with its project default. This audit
(run by ``make lint`` / CI) keeps that true:

* **Coverage** — the top-level keys of ``inventory/knob_schema.yml`` and of the
  example are the same set.
* **Flat knobs** — every literal knob declared in ``roles/*/defaults`` or
  ``inventory/group_vars`` is present in the example with the same value. A
  template value (``{{ ... }}``) is derived, never an operator knob.
* **Grouped knobs** — every ``<group>_defaults`` mapping in group_vars has a
  matching example section, and the example carries every key at the same path
  (recursively) with the same value. A block sequence or nested mapping is
  presence-checked only.
* **Playbook-level knobs** — the ``EXTRA`` knobs (declared only in playbooks) are
  presence-checked.

Standard library only (like the other scripts/), so a plain `python3` can run it.

Usage: audit_example_knobs.py [repo root]      # exit 1 with a report on failure
"""
from __future__ import annotations

import glob
import os
import re
import sys

WIRING = {
    "ssh_identities", "ssh_identity", "ssh_user", "ssh_password",
    "ssh_privkey_file", "ssh_become", "ssh_common_args",
    "ansible_user", "ansible_password", "ansible_ssh_private_key_file",
    "ansible_become", "ansible_ssh_common_args", "become", "user", "password",
    "privkey", "pubkey", "root", "admin", "iac", "legacy", "ansible",
    "ansible_core_min_version", "ansible_core_max_version",
    "ansible_core_allow_untested",
}
EXTRA = {
    "apt_mirror", "docker_registry_mirrors", "allow_root_login", "timezone",
}

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


def is_template(value) -> bool:
    return isinstance(value, str) and value.lstrip().startswith("{{")


def declared(root: str) -> tuple[dict[str, tuple[dict, str]], dict[str, tuple[object, str]]]:
    """Return the grouped defaults and the flat literal knobs with their source."""
    groups: dict[str, tuple[dict, str]] = {}
    flats: dict[str, tuple[object, str]] = {}
    paths = sorted(glob.glob(os.path.join(root, "roles/*/defaults/main.yml")))
    paths += sorted(glob.glob(os.path.join(root, "inventory/group_vars/*/*.yml")))
    for path in paths:
        source = os.path.relpath(path, root)
        for key, value in parse_mapping(path).items():
            if key.endswith("_defaults") and isinstance(value, dict):
                groups[key[: -len("_defaults")]] = (value, source)
            elif key.endswith("_cfg") or isinstance(value, dict) or value is None:
                continue
            elif is_template(value):
                continue
            else:
                flats[key] = (value, source)
    return groups, flats


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
    example_path = os.path.join(root, "inventory/host_vars/example/main.yml")
    if not os.path.isfile(example_path):
        print(f"ERROR: {example_path} does not exist", file=sys.stderr)
        return 1

    groups, flats = declared(root)
    example = parse_mapping(example_path)
    schema = schema_keys(root)

    problems: list[str] = []
    for key in sorted(example.keys() - schema):
        problems.append(f"{key}: present in the example but missing from inventory/knob_schema.yml")
    for key in sorted(schema - example.keys()):
        problems.append(f"{key}: in inventory/knob_schema.yml but not the example")
    for key in sorted(flats.keys() - WIRING):
        default, source = flats[key]
        if key not in example:
            problems.append(f"{key}: missing from the example (default {default!r} in {source})")
        elif default is not None and example[key] is not None and example[key] != default:
            problems.append(
                f"{key}: example value {example[key]!r} != effective default {default!r} "
                f"({source})"
            )
    for key in sorted(EXTRA):
        if key not in example:
            problems.append(f"{key}: playbook-level knob missing (or commented out) in the example")

    knobs = 0
    for name, (defaults, source) in sorted(groups.items()):
        if name not in example:
            problems.append(f"{name}: has a <group>_defaults mapping but no example section")
            continue
        if not isinstance(example[name], dict):
            problems.append(f"{name}: must be a mapping in the example ({source})")
            continue
        knobs += compare(name, defaults, example[name], problems)

    if problems:
        print(f"audit_example_knobs: {len(problems)} problem(s) in {example_path}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        f"audit_example_knobs: OK ({len(groups)} groups, {knobs} grouped knobs, "
        f"{len([key for key in flats if key not in WIRING])} flat knobs checked)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
