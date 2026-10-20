# Host monitoring & security

`roles/monitoring/` — optional, opt-in. Default on for nodes
(`monitoring_enabled: true` in `group_vars/remnanodes/main.yml`). Reached via
`make monitoring` or as part of `site.yml`. Debian-family only.

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

## Skipping

The play sets `gather_facts: false` and the role gathers facts itself, so hosts
that did not opt in (`monitoring_enabled: false`) are skipped without any
connection being made.
