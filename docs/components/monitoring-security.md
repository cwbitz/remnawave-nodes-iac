# Host monitoring & security

`roles/monitoring/` — optional, opt-in per host
(`monitoring_enabled: true` in `inventory/host_vars/<host>/main.yml`; default
`false`). Reached via `make monitoring` or as part of `site.yml`. Debian-family
only.

## What it installs

- `prometheus-node-exporter` — host metrics. Binds the **overlay address only**
  (`<overlay-ip>:9100`), so the central Prometheus scrapes it with no public and
  no local listener. A systemd drop-in waits for the overlay before starting it,
  so the bind survives a reboot.
- `crowdsec` — log-based detection (SSH brute force, scans) from the systemd
  journal (no rsyslog needed); its metrics listen on `:6060` on the overlay.
- `crowdsec-firewall-bouncer` — enforces CrowdSec decisions via nftables. **Not a
  base firewall**: it only acts on CrowdSec decisions (the base firewall is
  `roles/firewall`, see [`firewall.md`](firewall.md)).
- `grafana/alloy` (optional, `alloy_enabled`) — ships host journal logs to a
  central Loki reachable at `loki_push_url` over the overlay (an overlay IP, or
  preferably the central peer's NetBird name `<peer>.netbird.selfhosted`, which
  the alloy container resolves through the agent and which survives a
  re-enrolled central peer).

The Debian packages self-configure: crowdsec enables `crowdsecurity/linux` +
`crowdsecurity/sshd` and reads `ssh.service` from journald; the firewall bouncer
registers its LAPI key against the local LAPI on install.

## Overlay + discovery

The role **includes `roles/agent`** so the exporters are reachable over the
overlay. The sibling `docker-stack-iac` Prometheus discovers peers from the NetBird
API and scrapes `:9100` and `:6060`.

## Disabling

`playbooks/site.yml` includes the role while `monitoring_enabled` is true and runs
its `cleanup` tasks when it is false; `roles/monitoring/tasks/main.yml` runs the
same cleanup for a component disabled on its own. Cleanup stops and disables
`prometheus-node-exporter` (`node_exporter_enabled: false`), stops and disables
`crowdsec` and `crowdsec-firewall-bouncer` (`crowdsec_enabled: false`), and takes
the Alloy compose stack down (`alloy_enabled: false`, only when a rendered
`/opt/monitoring/docker-compose.yml` exists). Packages and rendered configuration
stay in place, so re-enabling a component needs only `make deploy`; units are
guarded on `ansible_facts.services`, so a host that never installed them is
untouched.

The role gathers facts itself, so it does not depend on a prior fact-gathering
pass. A host with `monitoring_enabled: false` is cleaned up without installing
anything and without including the overlay agent.
