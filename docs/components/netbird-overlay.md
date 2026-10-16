# NetBird overlay join

`roles/agent/` — joins a node to the NetBird mesh by running the
`netbirdio/netbird` agent container in `agent_dir` = `/opt/netbird-agent`. Reached
via `make agent`, or as part of `roles/monitoring` / `site.yml`.

## Inputs (owned by this project)

- `netbird_management_url` — non-secret; host `main.yml` (empty = NetBird Cloud).
- `peer_setup_key` — from `vault_netbird_setup_key`; this node's enrollment key.

The management server is owned by the sibling `netbird-iac` project and is never
read from as source. The setup key's auto-group decides which peers the central
observability stack discovers — the route-less `endpoint` key (the default) grants
no exit/LAN routes.

## Routing nodes

`netbird_agent_routing: true` enables IPv4/IPv6 forwarding on the host — the
host-side requirement for a routed-network gateway / exit node.

## Ownership / convergence

The agent runs in this role's own compose project (`netbird-agent`). A `netbird`
container owned by a **different** compose project is removed first (ours is left
alone), so taking over the container name converges from any prior layout.

## Gotcha

The agent persists the management URL in `/var/lib/netbird/default.json` on the
`netbird_config` volume, and the persisted value wins over `NB_MANAGEMENT_URL`.
Changing the management URL needs a fresh setup key and a reset of
`netbird_config` (a new peer), or an in-container
`netbird up --management-url <new>`.
