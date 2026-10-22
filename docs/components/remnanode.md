# Remnawave Node container

`roles/remnanode/` — renders and runs the `remnawave/node` (Xray-core) container in
`remnanode_dir` = `/opt/remnanode`, as part of `site.yml` (`TAGS=remnanode`).

## Inputs

Created in the Panel (**Nodes → Management**, then **Copy docker-compose.yml**).
Only two values are needed:

- `remnanode_node_port` — the `NODE_PORT` value (non-secret; host `main.yml`).
- `remnanode_secret_key` — the `SECRET_KEY` value, resolved by
  `roles/remnanode/defaults` from `vault_remnanode_secret_key` (never set in
  `main.yml`).

The role asserts a valid 1–65535 `NODE_PORT` and a non-empty `SECRET_KEY`, renders
`roles/remnanode/templates/remnanode/docker-compose.yml.j2` to
`/opt/remnanode/docker-compose.yml`, then runs it. The rest of the Panel's
generated compose file is the committed template — rendering is the source of
truth; never edit the file on the host.

## Security

- `SECRET_KEY` is a live credential: the Panel authenticates the node with it.
- The rendered compose file holds the live `SECRET_KEY`; it is mode `0600` and the
  render task is `no_log`. It is gitignored — never commit it.
- The container is `network_mode: host`, so `NODE_PORT` is exposed on every
  interface unless `firewall_enabled` is set. `roles/firewall` then closes it to
  the public internet (reachable over the NetBird overlay only) — see
  [`firewall.md`](firewall.md). The Xray inbounds the Panel pushes are public by
  design; declare their ports there.

## Changing inputs

Changing `NODE_PORT` / `SECRET_KEY` re-renders the compose file and recreates the
container; keep the vault in sync with the Panel's node definition.

## Image

`remnanode_version` defaults to `latest` (the Panel generates
`remnawave/node:latest`). Upstream publishes no pinned tags, so Renovate tracks it
for manual review (see the baseline table in [`AGENTS.md`](../../AGENTS.md)).
