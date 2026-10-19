# Host firewall

`roles/firewall/` — the host's **base firewall**: default-deny inbound, on by
default for nodes (`firewall_enabled: true` in
`group_vars/remnanodes/main.yml`). Reached via `make deploy` (`TAGS=firewall`) or
`playbooks/site.yml`. Debian-family only.

## Why

The Node runs with `network_mode: host` and publishes `NODE_PORT` on `0.0.0.0`.
The Panel is the TLS client and reaches it over the NetBird overlay, so the port
must be reachable on the overlay and **nowhere else**. `crowdsec-firewall-bouncer`
is not a base firewall (it only enforces CrowdSec decisions), and the upstream
Node image offers no bind-address option, so packet filtering is the only way to
close the port.

The other half of the overlay path is the **tenant ACL** (owned by `netbird-iac`):
the node's NetBird client drops everything from `wt0` that the pushed policy does
not list, so `NODE_PORT` must be allowed there from the Panel peer's group.

## How

A **dedicated nftables table** (`inet hostfw`) with an `input` hook, policy
`drop`, accepting only (in this order):

| Traffic | Why |
|---|---|
| `iif lo` | loopback |
| `iifname wt0` | the NetBird overlay: only authenticated mesh peers can inject there, so no Panel-IP allowlist is needed (the Panel sits behind a rotating home-broadband IP) |
| `udp <netbird_wg>` | the NetBird WireGuard port (`firewall_netbird_wg_port`, default 51820) — closing it would not break the mesh but would force relayed instead of direct P2P peers |
| `ct state established,related` | replies to host-initiated flows (mesh management, DNS, image pulls, apt) |
| `icmp`/`ipv6-icmp` | path-MTU discovery, diagnostics (`firewall_allow_icmp`) |
| `tcp <ssh>` | SSH (`firewall_ssh_port`, defaults to the inventory `ansible_port`, then 22) |
| `tcp`/`udp <public_ports>` | the Xray inbounds the Panel pushes (`firewall_public_tcp_ports` / `..._udp_ports`) |

The overlay and the WireGuard port are accepted **before** any conntrack-state
rule, and there is no `ct state invalid drop`: the kernel's WireGuard bypasses the
netfilter output hook (its outbound handshake is never tracked), so its return
traffic has no prior conntrack entry and can be classified `invalid` — dropping
that state would break the tunnel (and with it the management/relay traffic
NetBird routes through the overlay).

The table is **separate**, so nothing else is flushed or replaced: Docker owns
`ip/ip6 filter`+`nat`, CrowdSec owns `ip crowdsec`, NetBird owns `ip netbird` and
the Node owns `ip remnanode`. An `inet` `drop` is terminal, so the default-deny
holds even though Docker's `ip`-filter `INPUT` chain keeps policy `accept`. The
`FORWARD` path is left to Docker/NetBird.

## Configuration

Operator knobs live in `inventory/host_vars/<host>/main.yml` (see
`host_vars/example/main.yml`):

- `firewall_enabled` — per-host opt-in (default `false`; the group sets `true`).
- `firewall_public_tcp_ports` / `firewall_public_udp_ports` — the Xray
  inbounds the Panel pushes. **The Panel owns these ports**, so this project cannot
  derive them; declare the ones you actually expose (empty = no proxy service yet).
- `firewall_ssh_port` / `firewall_netbird_wg_port` /
  `firewall_overlay_iface` / `firewall_allow_icmp` — overrides.

## Persistence and safety

- The ruleset is rendered to `/etc/nftables.d/90-host-firewall.nft` and loaded by
  an Ansible-managed oneshot unit `host-firewall.service`, which validates with
  `nft -c` *before* applying: a bad ruleset fails the start and never loads, so it
  cannot leave the host unfirewalled. The unit reloads only when the rendered
  ruleset differs.
- It never enables Debian's `nftables.service` (whose stock config does
  `flush ruleset`, which would race with Docker/CrowdSec/NetBird at boot).
- SSH is always allowed and the role re-checks reachability
  (`wait_for_connection`) after applying, so a mistake fails the run loudly
  instead of silently locking the host out. If a lockout does happen, recover via
  the provider console: `systemctl stop host-firewall` (or delete the table with
  `nft delete table inet hostfw`).

## Rollback

```bash
# Revert to no base firewall on the host:
ssh <host> 'systemctl disable --now host-firewall && nft delete table inet hostfw'
```

Then set `firewall_enabled: false` in the host's `main.yml` so a later
deploy does not re-apply it.
