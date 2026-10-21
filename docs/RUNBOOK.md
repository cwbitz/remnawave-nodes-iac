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
  `allow_root_login=true`.
- Key-only SSH administration is an **opt-in** step (`sshd_hardening_enabled`
  in the host's `main.yml`, off by default): enable it only after
  `make host-bootstrap` has authorized the `iac` key. See §4c.
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
   the NetBird overlay (`docs/components/panel-contract.md`). `roles/firewall`
   enforces this; keep the SSH/admin port (22 by default) in
   `firewall_public_tcp_ports` and declare the Xray inbounds the Panel pushes so
   public proxy ports stay open.

## 2. Deploy

```bash
make dry-run     # dry run (--check --diff)
make deploy      # bootstrap the host, then deploy the node stack
```

`make lint` (syntax check + `ansible-lint`) is an internal CI check, hidden from
`make help`.

Focused tags: `monitoring`, `firewall`, `sshd`, `remnanode`
(`make deploy TAGS=remnanode`).

`make deploy` runs `playbooks/bootstrap.yml` (service account + Docker), then
`playbooks/site.yml` (overlay join + monitoring, then the Remnawave Node).

Verify:

```bash
ansible -i inventory/hosts.yml remnanodes -m ansible.builtin.ping
ssh <host> 'cd /opt/remnanode && docker compose ps'
ssh <host> 'docker logs --tail=50 remnanode'
ssh <host> 'ip -4 -o addr show wt0'          # overlay peer address
ssh <host> 'ss -lntp | grep <NODE_PORT>'     # node listening for the Panel
ssh <host> 'nft list table inet basefw'      # the base firewall ruleset
ssh <host> 'systemctl is-active firewall'
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
- node_exporter has no listen knob: the overlay address is the only listener, and
  a systemd drop-in
  (`/etc/systemd/system/prometheus-node-exporter.service.d/10-overlay-wait.conf`)
  waits for the overlay at boot (the agent container creates it after systemd
  started the unit).
- Details: `docs/components/netbird-overlay.md` and
  `docs/components/monitoring-security.md`.

## 4b. Host firewall

```bash
make deploy TAGS=firewall   # apply the default-deny inbound firewall only
```

- `roles/firewall` keeps `NODE_PORT` (and everything else) off the public
  internet: only the overlay, the WireGuard UDP port and the declared public
  ports (the SSH/admin port and the Xray inbounds) are reachable. Details:
  `docs/components/firewall.md`.
- When the Panel pushes an Xray inbound on a public port, declare it in
  `firewall_public_tcp_ports` (or `..._udp_ports`) in the host's `main.yml`
  and re-run; otherwise the proxy is unreachable from clients.

## 4c. SSH hardening

```bash
make deploy TAGS=sshd   # key-only SSH (roles/sshd)
```

- Off by default. Set `sshd_hardening_enabled: true` in the host's
  `main.yml` only **after** `make host-bootstrap` has authorized a key that
  survives it (the `iac` key, or root's with
  `sshd_permit_root_login: prohibit-password`) — the role proves a key-only login
  works and rolls itself back (failing the run) otherwise. Details:
  [`docs/components/sshd-hardening.md`](components/sshd-hardening.md).
- Password logins (including root's) are closed; the root-login policy is
  `sshd_permit_root_login` (`no` disables root SSH, `prohibit-password` keeps it
  by key only). `iac` with its key is the default SSH identity; the
  OS/console login (root + `sudo`) is unaffected.
- Rollback (or recovery when the key material is lost): from the provider console
  `rm /etc/ssh/sshd_config.d/00-sshd-hardening.conf && systemctl reload ssh`,
  then set `sshd_hardening_enabled: false` in the host's `main.yml`.

## 5. Upgrade and rollback

- **Node upgrade**: let Renovate bump `/…/remnanode_version` (or edit it), then
  `make deploy TAGS=remnanode`.
- **Version rollback**: set the previous tag and re-run the deploy.
- **Full node rebuild**: re-run `make host-init`/`make vault-edit`, or on an
  already-scaffolded host recreate the container with `make deploy`.
- **Config rollback**: `git revert` or edit the per-host vars, then `make deploy`.
- **SSH hardening rollback**: `rm /etc/ssh/sshd_config.d/00-sshd-hardening.conf
  && systemctl reload ssh` (provider console), then set
  `sshd_hardening_enabled: false` and re-run.

## 6. Troubleshooting

| Symptom | Check / action |
|---|---|
| Panel shows the node offline | `ss -lntp | grep <NODE_PORT>` on the host; the Panel can reach the node's IP:NODE_PORT; `vault_remnanode_secret_key` matches the Panel's node; `docker logs remnanode`. |
| Node container restarts | `docker logs remnanode`; confirm `NODE_PORT`/`SECRET_KEY` are correct and unchanged. |
| Overlay peer has no `wt0` address | Valid `vault_netbird_setup_key` and `netbird_management_url` (main.yml); `docker logs netbird`. A changed management URL needs a fresh key + reset `netbird_config` volume. |
| Central Prometheus shows the node down | The peer joined with a group the observability stack discovers (`endpoint`); overlay up; `curl -s <overlay-ip>:9100/metrics` from another peer. |
| `make deploy` refuses root | Expected: run `make host-bootstrap` first, then connect as the `iac` account in `vault.yml` (or set `allow_root_login=true`). |
| SSH refuses the private key (`UNPROTECTED PRIVATE KEY FILE`, `are too open`) | The shared `scripts/run-with-ssh-agent.sh` starts the pinned Keychain agent, loads the vault keys and retries once. If it still fails, check the `vault_*_ssh_privkey_file` paths and run `make agent-load`. |
| `make deploy TAGS=sshd` failed and the host kept password login | Expected: the role reverted `/etc/ssh/sshd_config.d/00-sshd-hardening.conf` and failed. Read the task that failed (the key-only login probe is the usual one): the `iac` key must be authorized by `make host-bootstrap` and accepted by OpenSSH (`make agent-load` for a `/mnt/c` key). |
| No usable SSH login after enabling hardening | Recover from the provider console: `rm /etc/ssh/sshd_config.d/00-sshd-hardening.conf && systemctl reload ssh`, then set `sshd_hardening_enabled: false` in the host's `main.yml` and re-run. |
| A vault file is unreadable | It must be ansible-vault encrypted; the helpers re-encrypt a plaintext file on the next write. |
| `NODE_PORT` reachable from the internet | The base firewall is missing or disabled: `nft list table inet basefw` / `systemctl status firewall`; re-run `make deploy TAGS=firewall`. (The NetBird agent adds one extra `iifname "wt0" counter … accept` rule of its own; that is expected.) |
| Proxy clients cannot connect after a Panel config push | The pushed Xray inbound port is not open: add it to `firewall_public_tcp_ports` in the host's `main.yml` and re-run `make deploy TAGS=firewall`. |
| SSH/overlay lost after applying the firewall | Recover from the provider console: `systemctl stop firewall` (then `nft delete table inet basefw`), fix the knobs, and re-run. |
| Panel cannot reach the node after the firewall | Check `wt0` is up (`ip -4 -o addr show wt0`), that the Panel's node address is the node's **overlay** IP, and that the tenant ACL allows `NODE_PORT` (`nft list chain ip netbird netbird-acl-input-rules` on the node shows only `9100`/`6060` by default — the overlay drops the rest). |

Useful commands:

```bash
make print [HOST=<host>]                        # resolved vars incl. vault
ssh <host> 'cd /opt/remnanode && docker compose logs -f'
ssh <host> 'cd /opt/remnanode && docker compose ps'
ssh <host> 'systemctl status crowdsec crowdsec-firewall-bouncer prometheus-node-exporter'
ssh <host> 'systemctl status firewall && nft list table inet basefw'
```

## 7. Secrets and safety

- Never commit `vault.yml` (gitignored, even when encrypted).
- The vault password file is required to decrypt any vault.
- `SECRET_KEY` authenticates the node to the Panel — treat `vault.yml` as a live
  credential store and keep `NODE_PORT` off the public internet (the Panel reaches
  the node over the overlay).
