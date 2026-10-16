<div align="center">

# Remnawave Nodes IaC

Ansible IaC that manages the **Remnawave proxy Nodes** — the lightweight
`remnawave/node` (Xray-core) containers that a Remnawave Panel pushes proxy
configuration to. It manages each node from the very first boot of a blank
Debian-family VPS: host bootstrap, NetBird overlay join, host monitoring and
security, then the Remnawave Node itself.

From a blank VPS to a ready Remnawave node

[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)
</div>


The **Panel** (control plane) and the central observability stack live in the
sibling `docker-stack-iac` project; the **NetBird management server** lives in
`netbird-iac`. This project owns only the nodes and consumes those control planes
through their public interfaces (`NODE_PORT` / `SECRET_KEY` for the Panel, the
management URL + a setup key for the overlay).

## What it manages

```
┌──────────────────────────── Remnawave node VPS ────────────────────────────┐
│                                                                            │
│  remnanode (Xray-core)          netbird agent          host security       │
│   network_mode: host   ───────  joins the overlay  ─── node_exporter       │
│   listens on NODE_PORT          (wt0)                  CrowdSec + bouncer  │
│        ▲                                                                   │
└────────┼───────────────────────────────────────────────────────────────────┘
         │ Panel -> Node internal API (NODE_PORT, SECRET_KEY)
         │ NetBird overlay -> Prometheus scrapes :9100 and :6060
```

1. **Host bootstrap** (`playbooks/bootstrap.yml`, `make host-bootstrap`): probes
   the SSH identities `ansible → admin → root`, creates the least-privilege
   `ansible` service account (NOPASSWD sudo) when needed, and installs Docker
   Engine + the Compose v2 plugin. Optionally sets APT/Docker registry mirrors.
2. **Overlay + monitoring** (`roles/monitoring`, which includes `roles/agent`):
   installs `prometheus-node-exporter`, `crowdsec` and the
   `crowdsec-firewall-bouncer` (nftables), and joins the host to the NetBird
   overlay so the central Prometheus/Alloy reaches the exporters with no public
   port.
3. **Remnawave Node** (`roles/remnanode`): renders `/opt/remnanode/docker-compose.yml`
   and runs the `remnawave/node` container with `NODE_PORT` / `SECRET_KEY`.

## Remnawave Node inputs

In the Panel go to **Nodes → Management**, add the node, and click
**Copy docker-compose.yml**. It looks like this:

```yaml
services:
  remnanode:
    container_name: remnanode
    hostname: remnanode
    image: remnawave/node:latest
    network_mode: host
    restart: always
    cap_add:
      - NET_ADMIN
    ulimits:
      nofile:
        soft: 1048576
        hard: 1048576
    environment:
      - NODE_PORT=2222
      - SECRET_KEY="xxxxxx"
```

Only the two environment values are needed: `NODE_PORT` is a plain per-host
setting and `SECRET_KEY` is the only node-specific secret:

```yaml
# inventory/host_vars/<host>/main.yml
remnanode_node_port: "2222"

# inventory/host_vars/<host>/vault.yml
vault_remnanode_secret_key: "xxxxxx"
```

The rest of that compose file is the committed template
`roles/remnanode/templates/remnanode/docker-compose.yml.j2` — rendering is the
source of truth; never edit the file on the host.

> Keep the node's `NODE_PORT` **off the public internet**: the Panel is the TLS
> client and reaches the node over the NetBird overlay. See
> `docs/components/panel-contract.md`.

## NetBird overlay inputs

The management server is owned by the sibling `netbird-iac` project; this project
holds both inputs itself — the non-secret management URL in the host's `main.yml`
and the enrollment setup key in the vault:

```yaml
# inventory/host_vars/<host>/main.yml
netbird_management_url: "https://netbird.example.com"

# inventory/host_vars/<host>/vault.yml
vault_netbird_setup_key: "..."   # this node's enrollment key
```

The setup key's auto-group decides which peers the central observability stack
discovers (`endpoint` by default: route-less, no exit/LAN routes). Set
`netbird_agent_routing: true` only for a node that routes for a routed
network / exit node.

## Requirements

- A fresh **Debian 13** VPS reachable over SSH as `root` (only `root` is required
  initially; the bootstrap creates the `ansible` service account). No Docker and
  no prior system update are needed.
- On the control node: `mise` or `asdf`, `openssl`, and SSH access to the host.
  `sshpass` is only needed for the `make host-bootstrap` password probe and is
  auto-installed by `make install`; `make install` also installs the pinned
  Keychain 3 (an ssh-agent fallback used only when a private key's permissions are
  rejected by OpenSSH, e.g. under WSL).

## Quickstart

```bash
# 1. Toolchain + collections
make install

# 2. Scaffold a host from the committed template (vault.yml is encrypted for you,
#    the host is added to inventory/hosts.yml, and the generated files are
#    comment-free). HOST defaults to remnanode-1; HOST_IP writes ansible_host
#    (otherwise the entry keeps the CHANGE_ME_HOST_IP placeholder the site
#    preflight rejects), HOST_PORT sets ansible_port.
make host-init HOST=remnanode-1 HOST_IP=203.0.113.10
#    - edit inventory/host_vars/remnanode-1/main.yml   (non-secret: NODE_PORT, NetBird URL, ...)
#    - edit the encrypted vault:
make vault-edit HOST=remnanode-1
#      (SSH creds, NetBird setup key, SECRET_KEY)

# 3. Dry-run, deploy
make dry-run
make deploy
```

`make deploy` is the one-shot entry point: it bootstraps the host, then deploys
the node stack (`playbooks/site.yml`). On a fresh host the `ansible` service
account does not exist yet, so `deploy` runs the same host bootstrap as
`make host-bootstrap` first.

## Entry points

| Target | Playbook | What it does |
|---|---|---|
| `make host-bootstrap` | `bootstrap.yml` | Probe SSH identities, create the `ansible` account, install Docker. `HOST=<name>` targets one host. |
| `make agent` | `agent.yml` | Join the nodes to the NetBird overlay only. |
| `make monitoring` | `monitoring.yml` | node_exporter + CrowdSec + firewall bouncer (+ overlay agent). |
| `make deploy` | `bootstrap.yml` + `site.yml` | Full node stack: monitoring/agent + Remnawave Node. |
| `make dry-run` | `site.yml --check --diff` | Safe preview. |
| `make print [HOST=]` | — | Resolved host vars incl. decrypted vault. |

`make deploy TAGS=remnanode` (or `TAGS=monitoring`) runs only that role. The
internal `make lint` (syntax check + `ansible-lint`) is hidden from `make help`.

## Secrets

Never commit vaults. The single per-host encrypted vault
`inventory/host_vars/<host>/vault.yml` holds the SSH identity values, the NetBird
setup key, the Remnawave `SECRET_KEY`, and the control-generated service-account
password (when no public key is given). It is gitignored and never committed, even
encrypted; the committed schema reference is
`inventory/host_vars/example/vault.yml.example`.

## Documentation

- [`AGENTS.md`](AGENTS.md) — conventions, gotchas, and the command reference.
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — operations (deploy, verify, rollback).
- [`docs/components/`](docs/components/) — component design notes:
  [`host-bootstrap.md`](docs/components/host-bootstrap.md),
  [`netbird-overlay.md`](docs/components/netbird-overlay.md),
  [`monitoring-security.md`](docs/components/monitoring-security.md),
  [`remnanode.md`](docs/components/remnanode.md),
  [`panel-contract.md`](docs/components/panel-contract.md).

## Layout

```
inventory/                # hosts.yml(.example), group_vars/remnawave_nodes, host_vars/example
playbooks/bootstrap.yml   # host init: service account + Docker (+ mirrors)
playbooks/agent.yml       # join the NetBird overlay (agent role)
playbooks/monitoring.yml  # host monitoring + security
playbooks/site.yml        # full node stack (monitoring/agent + remnanode)
roles/agent               # NetBird overlay agent (mesh join)
roles/monitoring          # node_exporter + CrowdSec + firewall bouncer (+ agent)
roles/remnanode           # the Remnawave Node container
roles/helpers/            # shared vault-secret provisioning + Docker install
docs/                     # this repo's docs (RUNBOOK.md, components/)
```

## License

See `LICENSE`.
