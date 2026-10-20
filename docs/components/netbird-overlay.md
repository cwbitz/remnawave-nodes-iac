# NetBird overlay join

`roles/agent/` — joins a node to the NetBird mesh by running the
`netbirdio/netbird` agent container in `agent_dir` = `/opt/netbird-agent`. Reached
via `make agent`, or as part of `roles/monitoring` / `site.yml`.

## Inputs (owned by this project)

- `netbird_management_url` — non-secret; host `main.yml` (empty = NetBird Cloud).
- `netbird_peer_setup_key` — from `vault_netbird_setup_key`; this node's enrollment key.

The management server is owned by the sibling `netbird-iac` project and is never
read from as source. The setup key's auto-group decides which peers the central
observability stack discovers — the route-less `endpoint` key (the default) grants
no exit/LAN routes.

## DNS and routing

The agent always serves the NetBird DNS zone (`<peer>.netbird.selfhosted`): it
installs itself as the host resolver through systemd-resolved over D-Bus, and
falls back to rewriting `/etc/resolv.conf` on hosts without systemd-resolved
(hence the D-Bus **and** `/etc/resolv.conf` mounts in the agent compose). The host
therefore resolves peer names — which is what makes a `loki_push_url` like
`http://<central-peer>.netbird.selfhosted:3100` work — and containers that need
the zone get it via a `dns: ["<overlay-ip>"]` override (the agent's embedded
resolver), because Docker's embedded DNS does not forward to the host resolver.

Nodes are plain endpoints: they never enable IP forwarding or act as a
routed-network gateway / exit node (that is a routing peer's job, outside this
project's scope).

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
