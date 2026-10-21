# SSH hardening

`roles/sshd/` — key-only SSH administration for the Node host, applied as a
drop-in under `/etc/ssh/sshd_config.d/` (`00-sshd-hardening.conf`). Reached
via `make deploy TAGS=sshd` or `playbooks/site.yml`. Debian-family only.

## Why

A node is a public VPS: `roles/firewall` deliberately keeps SSH reachable from the
internet (CrowdSec's bouncer handles the brute force), and stock Debian images let
**root log in with a password**. `playbooks/bootstrap.yml` never touches
`sshd_config` (it says so explicitly: *"sshd config is out of scope"*), and its
probe falls back to the root password — so password login stays open until this
role is opted into.

It is **opt-in per host** (`sshd_hardening_enabled`, off by default): closing
password login removes the very path the bootstrap probe relies on, so it is only
safe once a keyed login survives it — the `iac` automation account's key
(installed by `make host-bootstrap` from `host_iac_ssh_pubkey_file`),
or root's key on a root-administered host (`host_root_ssh_pubkey_file` with
`sshd_permit_root_login: prohibit-password`).

## How

The drop-in closes password login on **every** path, and pins the root-login
policy:

| Directive | Value | Why |
|---|---|---|
| `PubkeyAuthentication` | `yes` | the only remaining login method |
| `PasswordAuthentication` | `no` | the ssh password auth method |
| `KbdInteractiveAuthentication` | `no` | PAM keyboard-interactive otherwise still accepts a password |
| `PermitEmptyPasswords` | `no` | unchanged default, pinned explicitly |
| `PermitRootLogin` | `no` \| `prohibit-password` | `sshd_permit_root_login`, independent of the toggle: `no` disables root SSH, `prohibit-password` keeps it by key only |

A drop-in is used so the provider's cloud-init config and the operator's
`sshd_config` are never edited. The file is named `00-` because sshd keeps the
**first** value obtained for a keyword and the main `sshd_config` `Include`s the
drop-in directory — `00-` therefore wins over a provider drop-in such as
`50-cloud-init.conf`. That ordering is not assumed: the role asserts the
**effective** configuration with `sshd -T` and rolls back if it did not take.

## Safety

Hardening is the one change here that can take the host away from its operator, so
the role verifies instead of trusting:

1. **Preconditions** — a keyed login must survive: the `iac` identity's
   public key, or root's when `sshd_permit_root_login` allows it (else nothing
   runs).
2. **Before loading** — the rendered drop-in is validated with `sshd -t`; a bad
   file fails while the running sshd still serves the previous configuration.
3. **After loading** — the effective configuration is asserted with `sshd -T`
   (`passwordauthentication no`, `kbdinteractiveauthentication no`,
   `pubkeyauthentication yes`, `permitrootlogin <sshd_permit_root_login>`), which
   catches a pre-existing drop-in that wins the first-obtained-value rule.
4. **Then the login is re-proven** — a fresh, key-only (`BatchMode`,
   `PreferredAuthentications=publickey`) connection as the chosen identity
   (`iac`, or root) from the control node must succeed.

Any failure at 2–4 triggers the `rescue`: the drop-in is restored to its previous
state (or removed when there was none), sshd is reloaded, and the run fails
loudly. A locked-out host is therefore a failed run, not a silent state.

## Configuration

Operator knobs live in `inventory/host_vars/<host>/main.yml` (see
`host_vars/example/main.yml`):

- `sshd_hardening_enabled` — per-host opt-in (role default `false`; nothing is
  written until it is set).
- `sshd_permit_root_login` — root-login policy, default `no`: `no` disables root
  SSH, `prohibit-password` keeps it reachable by public key only. Independent of
  the toggle above.

Password login itself is not configurable: it is closed on every path. `iac`
(public key) is the default SSH identity; with `sshd_permit_root_login:
prohibit-password` root's key is a valid identity too, while `no` leaves root the
provider console and `sudo` only. The bootstrap still authorizes root's public
key (it does not know about this role), so it is simply unused when root SSH is
off.

## Recovery and rollback

The escape hatch is the provider console (the OS login is unaffected by sshd). On
a host whose key material was lost, recover from the console and re-open the
password path:

```bash
rm /etc/ssh/sshd_config.d/00-sshd-hardening.conf
systemctl reload ssh
```

Then set `sshd_hardening_enabled: false` in the host's `main.yml` so a later
deploy does not re-apply it, fix the key (`make agent-load` when OpenSSH refuses a
WSL `/mnt/c` key), and re-enable.

## Gotchas

- The key OpenSSH refuses is a real failure mode here: keys under `/mnt/c` (WSL)
  are often world-readable, and OpenSSH rejects them. The role proves the login
  with the normal `ssh` client, so it fails (and reverts) rather than trusting the
  configured path.
- The `[iac, admin, root]` probe in `playbooks/bootstrap.yml`
  loses its password fallback once hardening is on: at least one of the `iac` or root
  keys must be in place first (root only when `sshd_permit_root_login` allows it).
- A client with no key configured sees `Permission denied (publickey)` — not a
  password prompt — once password authentication is off.
- sshd is reloaded (`SIGHUP`), never restarted mid-run: the session the deploy is
  using survives.

## See also

`docs/components/host-bootstrap.md` (the service account and key wiring),
[`firewall.md`](firewall.md) (SSH stays open to the internet),
[`RUNBOOK.md`](../RUNBOOK.md) (deploy, verify, rollback).
