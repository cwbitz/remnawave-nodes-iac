# Host bootstrap

`playbooks/bootstrap.yml` (`make host-bootstrap [HOST=]`) — optional, opt-in, and
never part of `playbooks/site.yml`; `make deploy` runs it first. It targets one
host at a time.

## What it does

1. **Probes the SSH identities** `[iac, admin, root]` (key first,
   then password) and uses the first that can also escalate: `iac` is proven with
   `sudo -n`, `admin` with its password through `sudo -S`, and `root` needs no
   escalation.
2. **Creates/repairs the `iac` automation account** with NOPASSWD sudo, unless it
   already connected as `iac`. Password mode hashes with a per-account random
   salt and applies `update_password=on_create`, so re-runs are idempotent and a
   host-side rotation is preserved. If sshd disables password auth, password login
   fails (sshd config is out of scope).
3. **Ensures Docker Engine + the Compose v2 plugin** through the shared
   `helpers/install_docker` task (Docker's official install script,
   `https://get.docker.com`). `install_docker: false` skips the install and fails
   with guidance when Docker is missing.
4. **Optionally sets the clock and mirrors** (each a no-op unless set):
   `timezone` (an existing IANA zone), `apt_mirror` (the Debian suite root,
   ending in `/debian`; the security suite derives from it) and
   `docker_registry_mirrors`.
5. **Authorizes configured SSH public keys** (`host_<id>_ssh_pubkey_file` in the
   host's `main.yml`).

## Identity wiring

The `iac` / `admin` / `root` aliases are derived per host in
`inventory/group_vars/all/main.yml` from that host's own vault; the
value schema is `inventory/host_vars/example/vault.yml.example`.

A private-key path alone is **not** key mode: the account still gets a password
(from `vault_host_iac_password`, generated when empty) so an unauthorized key
cannot lock you out; it becomes key-only once its **public**-key path is set.

`create_admin_account: true` additionally creates the optional human `admin` account
(console login + sudo), which always gets a password plus any configured key.

## Platform

Debian-family Linux. Automatic Docker install is Debian-only; non-Debian is
best-effort (install Docker yourself and re-run). CrowdSec and the nftables
firewall bouncer come from the Debian repositories (present in Debian 13 / trixie).

## See also

`playbooks/bootstrap.yml` (the flow and inline comments) and `docs/RUNBOOK.md` §0.
