#!/usr/bin/env python3
"""Audit inventory/host_vars/example/main.yml against the project's knobs.

`make host-init` copies the example (comment-free) to
``inventory/host_vars/<host>/main.yml``, so the example is the template for every
new host and must carry every operator knob with its project default. This audit
(run by ``make lint`` / CI) keeps that true:

* **Presence** — every operator knob, i.e. every variable declared in
  ``inventory/group_vars/**/main.yml`` or ``roles/*/defaults/main.yml``, must be
  represented in the example.
* **Value** — its example value must equal the EFFECTIVE default (group_vars wins
  over the role default), so scaffolding a host is behaviour-neutral.
* **Derived knobs** — a knob whose ABSENCE is meaningful (its value is derived
  from another variable at run time, e.g. ``x | default(<derived>)``) must be
  documented but COMMENTED OUT, otherwise the derivation is defeated.
* Not per-host knobs (skipped): the SSH connection wiring, the control-node
  baseline, role-internal constants and vault-bound secrets — see the explicit
  sets below. Playbook-level knobs are presence-checked through ``EXTRA``.

Standard library only (like the other scripts/), so a plain `python3` can run it.
Values are compared with a small scalar parser; a key whose value is a block or
nested structure is presence-checked only.

Usage: audit_example_knobs.py [repo root]      # exit 1 with a report on failure
"""
from __future__ import annotations

import glob
import os
import re
import sys

# --------------------------------------------------------------------------------
# Exclusions (explicit and documented — keep them in sync with the project).
# --------------------------------------------------------------------------------
# SSH connection wiring + control-node baseline: not per-host knobs, they live in
# inventory/group_vars/<group>/main.yml (and group_vars/all for the engine range).
WIRING = {
    "ssh_identities", "ssh_identity", "ssh_user", "ssh_password",
    "ssh_privkey_file", "ssh_become", "ssh_common_args",
    "ansible_user", "ansible_password", "ansible_ssh_private_key_file",
    "ansible_become", "ansible_ssh_common_args", "become", "user", "password",
    "privkey", "pubkey", "root", "admin", "ansible",
    "ansible_core_min_version", "ansible_core_max_version",
    "ansible_core_allow_untested",
}
# Role-internal constants that happen to live in defaults/ (paths, Renovate-pinned
# image tags): changing them per host is not a supported operator knob.
INTERNAL = {
    "agent_dir", "monitoring_dir", "remnanode_dir",
    "netbird_agent_version", "alloy_version", "remnanode_version",
}
# Vault-bound inputs: the example references the vault variable while the role
# default adds a `| default('', true)` guard, so the texts differ by design.
VAULT_BOUND = {"netbird_peer_setup_key", "remnanode_secret_key"}
# Knobs whose ABSENCE is meaningful. They must be documented in the example but
# stay COMMENTED OUT: setting them (even to "") disables the run-time derivation.
DERIVED = {"apt_security_mirror"}
# Playbook-level knobs (declared as play vars, not in group_vars/defaults):
# presence as an ACTIVE line required; the values are the documented defaults.
EXTRA = {
    "apt_mirror", "docker_registry_mirrors", "allow_root_login",
}

KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
CKEY_RE = re.compile(r"^\s*#\s*([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


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
    if text.startswith("[") and text.endswith("]"):
        body = text[1:-1].strip()
        return [parse_scalar(item) for item in split_top_level(body)] if body else []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        return text


def scan(path: str) -> tuple[dict, dict]:
    """Return ({key: value}, {key: value}) for ACTIVE and COMMENTED lines."""
    active: dict = {}
    commented: dict = {}
    try:
        handle = open(path, encoding="utf-8")
    except OSError:
        return active, commented
    with handle:
        for line in handle:
            if (m := KEY_RE.match(line)):
                active[m.group(1)] = parse_scalar(m.group(2))
            elif (m := CKEY_RE.match(line)):
                commented[m.group(1)] = parse_scalar(m.group(2))
    return active, commented


def declared_knobs(root: str) -> dict[str, tuple[object, str]]:
    """Effective default per knob: role defaults first, group_vars win."""
    knobs: dict[str, tuple[object, str]] = {}
    paths = sorted(glob.glob(os.path.join(root, "roles/*/defaults/main.yml")))
    paths += sorted(glob.glob(os.path.join(root, "inventory/group_vars/*/main.yml")))
    for path in paths:
        for key, value in scan(path)[0].items():
            knobs[key] = (value, os.path.relpath(path, root))
    return knobs


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else os.getcwd()
    example = os.path.join(root, "inventory/host_vars/example/main.yml")
    if not os.path.isfile(example):
        print(f"ERROR: {example} does not exist", file=sys.stderr)
        return 1
    active, commented = scan(example)

    problems: list[str] = []
    knobs = declared_knobs(root)
    for key, (default, source) in sorted(knobs.items()):
        if key in WIRING or key in INTERNAL:
            continue
        if key in DERIVED:
            if key not in commented:
                problems.append(
                    f"{key}: documented (commented) entry missing — setting it, even "
                    f"empty, defeats its run-time derivation ({source})"
                )
            elif key in active:
                problems.append(f"{key}: must not be an ACTIVE line (derived on absence)")
            continue
        if key not in active:
            problems.append(f"{key}: missing from the example (default {default!r} in {source})")
            continue
        if key in VAULT_BOUND:
            continue
        if default is not None and active[key] != default:
            problems.append(
                f"{key}: example value {active[key]!r} != effective default {default!r} "
                f"({source})"
            )

    for key in sorted(EXTRA):
        if key not in active:
            problems.append(f"{key}: playbook-level knob missing (or commented out) in the example")

    if problems:
        print(f"audit_example_knobs: {len(problems)} problem(s) in {example}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"audit_example_knobs: OK ({len(knobs)} declared knobs checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
