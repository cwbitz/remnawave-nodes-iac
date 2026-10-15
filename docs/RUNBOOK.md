# Runbook

[English](RUNBOOK.md) | [简体中文](RUNBOOK.zh-CN.md)

Operational procedures for the Remnawave proxy Nodes. See `README.md` for the
overview and `AGENTS.md` for design notes and gotchas.

## 0. Prerequisites (once)

- A fresh **Debian 13** VPS, SSH-reachable as `root` (only `root` is needed to
  start). No Docker and no prior system update required.
- Control node: ansible-core (pinned), Python 3, `openssl`, and the Galaxy
  collections: `make install`.
- A host entry: `make host-init HOST=<hostname>` — scaffolds
  `host_vars/<host>/` (encrypting `vault.yml`) and adds the host to
  `inventory/hosts.yml`; HOST defaults to `remnanode-1`. Then edit
  `inventory/host_vars/<host>/main.yml` and the vault
  (`make vault-edit HOST=<host>`).
- In the vault, fill in: the IP + SSH creds; the NetBird inputs
  (`vault_netbird_management_url`, `vault_netbird_setup_key`); and the Remnawave
  node inputs (`vault_remnanode_node_port`, `vault_remnanode_secret_key`) copied
  from the Panel's node.
- Create the non-root service account (as root, once): `make host-bootstrap`,
  then point the connection at it in `vault.yml`. Deploys refuse root unless
  `host_allow_root_login=true`.
- The vault password file is auto-created by the make targets
  (`~/.config/projects/remnawave-nodes-iac/ansible_vault_password`); keep it safe.

## 1. Create the node in the Panel

1. In the Remnawave Panel: **Nodes → Management**, add the node (name, address,
   `Node Port`).
2. Click **Copy docker-compose.yml**.
3. Write `NODE_PORT` and `SECRET_KEY` from that file into `vault.yml` as
   `vault_remnanode_node_port` and `vault_remnanode_secret_key`. The rest of the
   file is already the committed template.
4. Open `NODE_PORT` in the host/cloud firewall **only for the Panel's address**.

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
ansible -i inventory/hosts.yml remnawave_nodes -m ansible.builtin.ping
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
- node_exporter listens on `127.0.0.1:9100` plus the overlay address; CrowdSec
  exposes its metrics on `:6060` on the overlay. Both are discovered by the
  sibling `docker-stack-iac` Prometheus from the NetBird API.
- CrowdSec ships with `crowdsecurity/linux` + `crowdsecurity/sshd` and reads the
  SSH unit from the journal; the firewall bouncer enforces decisions via nftables.

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
| Overlay peer has no `wt0` address | Valid `vault_netbird_setup_key` and `vault_netbird_management_url`; `docker logs netbird`. A changed management URL needs a fresh key + reset `netbird_config` volume. |
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
  credential store and restrict `NODE_PORT` to the Panel only.
