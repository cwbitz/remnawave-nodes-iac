# Runbook

Operational procedures for the Remnawave proxy Nodes. See `README.md` for the
overview, `docs/components/` for component design notes, and `AGENTS.md` for
conventions and gotchas.

## 0. Prerequisites (once)

- A fresh **Debian 13** VPS, SSH-reachable as `root` (only `root` is needed to
  start). No Docker and no prior system update required.
- Control node: ansible-core (pinned), Python 3, `openssl`, and the Galaxy
  collections: `make install`.
- A host entry: `make host-init HOST=<hostname> HOST_IP=<management-ip>` —
  scaffolds `host_vars/<host>/` (encrypting `vault.yml`) and adds the host to
  `inventory/hosts.yml` as `ansible_host` (`HOST_PORT=` sets `ansible_port`); HOST
  defaults to `remnanode-1`. Without `HOST_IP` the entry keeps the
  `CHANGE_ME_HOST_IP` placeholder that the site preflight rejects.
- Non-secret settings go in `inventory/host_vars/<host>/main.yml`
  (`remnanode_node_port`, `netbird_management_url`, ...); the vault holds the SSH
  creds, `vault_netbird_setup_key` and the Remnawave node secret
  `vault_remnanode_secret_key` (copied from the Panel's node). Edit the vault with
  `make vault-edit HOST=<host>`.
- Create the non-root service account (as root, once): `make host-bootstrap`,
  then point the connection at it in `vault.yml`. Deploys refuse root unless
  `host_allow_root_login=true`.
- The vault password file is auto-created by the make targets
  (`~/.config/projects/remnawave-nodes-iac/ansible_vault_password`); keep it safe.

## 1. Create the node in the Panel

1. In the Remnawave Panel: **Nodes → Management**, add the node (name, address,
   `Node Port`).
2. Click **Copy docker-compose.yml**.
3. Write `NODE_PORT` into `main.yml` as `remnanode_node_port` and `SECRET_KEY`
   into `vault.yml` as `vault_remnanode_secret_key`. The rest of the
   file is already the committed template.
4. Keep `NODE_PORT` **off the public internet** — the Panel reaches the node over
   the NetBird overlay (`docs/components/panel-contract.md`).

## 2. Deploy

```bash
make dry-run     # dry run (--check --diff)
make deploy      # bootstrap the host, then deploy the node stack
```

`make lint` (syntax check + `ansible-lint`) is an internal CI check, hidden from
`make help`.

Focused tags: `monitoring`, `remnanode` (`make deploy TAGS=remnanode`).

`make deploy` runs `playbooks/bootstrap.yml` (service account + Docker), then
`playbooks/site.yml` (overlay join + monitoring, then the Remnawave Node).

Verify:

```bash
ansible -i inventory/hosts.yml remnanodes -m ansible.builtin.ping
ssh <host> 'cd /opt/remnanode && docker compose ps'
ssh <host> 'docker logs --tail=50 remnanode'
ssh <host> 'ip -4 -o addr show wt0'          # overlay peer address
ssh <host> 'ss -lntp | grep <NODE_PORT>'     # node listening for the Panel
```

In the Panel, the node should turn **healthy/connected** after the first config
push.

## 3. Day-2 changes

- Edit `inventory/host_vars/<host>/main.yml` (non-secret) or the vault (secret),
  then `make deploy`.
- Image versions live in `roles/remnanode/defaults/main.yml`,
  `roles/agent/defaults/main.yml`, `roles/monitoring/defaults/main.yml`
  (Renovate-tracked); `remnanode_version` follows `latest`.
- Never edit rendered files under `/opt/remnanode` or `/opt/netbird-agent` on the
  host — rendering is the source of truth.

## 4. Overlay and monitoring

```bash
make agent        # join/resync the NetBird overlay
make monitoring   # node_exporter + CrowdSec + firewall bouncer (+ agent)
```

- The overlay setup key is `vault_netbird_setup_key`; its auto-group decides what
  the central observability stack discovers.
- The exporters bind the overlay address (node_exporter `:9100`, CrowdSec LAPI
  `:6060`) and are discovered by the sibling `docker-stack-iac` Prometheus.
- Details: `docs/components/netbird-overlay.md` and
  `docs/components/monitoring-security.md`.

## 5. Upgrade and rollback

- **Node upgrade**: let Renovate bump `/…/remnanode_version` (or edit it), then
  `make deploy TAGS=remnanode`.
- **Version rollback**: set the previous tag and re-run the deploy.
- **Full node rebuild**: re-run `make host-init`/`make vault-edit`, or on an
  already-scaffolded host recreate the container with `make deploy`.
- **Config rollback**: `git revert` or edit the per-host vars, then `make deploy`.

## 6. Troubleshooting

| Symptom | Check / action |
|---|---|
| Panel shows the node offline | `ss -lntp | grep <NODE_PORT>` on the host; the Panel can reach the node's IP:NODE_PORT; `vault_remnanode_secret_key` matches the Panel's node; `docker logs remnanode`. |
| Node container restarts | `docker logs remnanode`; confirm `NODE_PORT`/`SECRET_KEY` are correct and unchanged. |
| Overlay peer has no `wt0` address | Valid `vault_netbird_setup_key` and `netbird_management_url` (main.yml); `docker logs netbird`. A changed management URL needs a fresh key + reset `netbird_config` volume. |
| Central Prometheus shows the node down | The peer joined with a group the observability stack discovers (`endpoint`); overlay up; `curl -s <overlay-ip>:9100/metrics` from another peer. |
| `make deploy` refuses root | Expected: run `make host-bootstrap` first, then connect as the `ansible` account in `vault.yml` (or set `host_allow_root_login=true`). |
| SSH refuses the private key (`UNPROTECTED PRIVATE KEY FILE`, `are too open`) | The shared `scripts/run-with-ssh-agent.sh` starts the pinned Keychain agent, loads the vault keys and retries once. If it still fails, check the `vault_*_ssh_privkey_file` paths and run `make agent-load`. |
| A vault file is unreadable | It must be ansible-vault encrypted; the helpers re-encrypt a plaintext file on the next write. |

Useful commands:

```bash
make print [HOST=<host>]                        # resolved vars incl. vault
ssh <host> 'cd /opt/remnanode && docker compose logs -f'
ssh <host> 'cd /opt/remnanode && docker compose ps'
ssh <host> 'systemctl status crowdsec crowdsec-firewall-bouncer prometheus-node-exporter'
```

## 7. Secrets and safety

- Never commit `vault.yml` (gitignored, even when encrypted).
- The vault password file is required to decrypt any vault.
- `SECRET_KEY` authenticates the node to the Panel — treat `vault.yml` as a live
  credential store and keep `NODE_PORT` off the public internet (the Panel reaches
  the node over the overlay).
