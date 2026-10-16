# Host monitoring & security

`roles/monitoring/` — optional, opt-in. Default on for nodes
(`monitoring_enabled: true` in `group_vars/remnawave_nodes/main.yml`). Reached via
`make monitoring` or as part of `site.yml`. Debian-family only.

## What it installs

- `prometheus-node-exporter` — host metrics. Binds `127.0.0.1:9100` **plus the
  overlay address** (`node_exporter_listen_addr` widens the local address), so the
  central Prometheus scrapes it with no public port.
- `crowdsec` — log-based detection (SSH brute force, scans) from the systemd
  journal (no rsyslog needed); its metrics listen on `:6060` on the overlay.
- `crowdsec-firewall-bouncer` — enforces CrowdSec decisions via nftables. **Not a
  base firewall**: it only acts on CrowdSec decisions.
- `grafana/alloy` (optional, `alloy_enabled`) — ships host journal logs to a
  central Loki reachable at `loki_url` over the overlay.

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
