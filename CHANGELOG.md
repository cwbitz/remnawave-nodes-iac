# Changelog

## [2.0.0](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.0.0...v2.0.0) (2026-10-27)


### ⚠ BREAKING CHANGES

* drop code comments and align the operator surface
* **ssh:** vault_host_{ansible,admin,root}_ssh_privkey_file, vault_host_{ansible,admin,root}_ssh_pubkey_file and vault_host_admin_user are no longer read; move their values to the host's main.yml as host_<id>_ssh_privkey_file, host_<id>_ssh_pubkey_file and host_admin_username.
* **bootstrap:** bootstrap_password and bootstrap_sudo_nopasswd are no longer operator knobs.
* **monitoring:** the two Alloy knob names changed; existing host_vars must use the new names.
* **agent:** netbird_dns_manage and netbird_agent_routing are no longer operator knobs; routing/exit-node setups are outside this project's scope.
* **firewall:** operators must use `systemctl ... firewall` and `nft list table inet basefw`; `firewall_overlay_iface` and `firewall_netbird_wg_port` are no longer host overrides.
* existing inventory/host_vars files and the vault templates must rename the affected keys; the old names are no longer read.
* **inventory:** an existing inventory/hosts.yml must rename its `remnawave_nodes` group to `remnanodes` and drop the `all.vars` engine baseline that now lives in inventory/group_vars/all/main.yml.
* **inventory:** vault_host.{ip,port}, vault_netbird_management_url and vault_remnanode_node_port are gone. Set ansible_host/ansible_port in the inventory (or HOST_IP/HOST_PORT via host-init) and netbird_management_url / remnanode_node_port in the host main.yml.

### Features

* add the Remnawave nodes IaC project ([7334639](https://github.com/cwbitz/remnawave-nodes-iac/commit/733463930c9fa77a4a33f0dc0719945e52c1b561))
* **agent:** always serve the NetBird DNS zone ([b5c7d4f](https://github.com/cwbitz/remnawave-nodes-iac/commit/b5c7d4f8a9358aac0c7d71d7172de6ead35ff892))
* **agent:** decouple the overlay from monitoring ([2ceb267](https://github.com/cwbitz/remnawave-nodes-iac/commit/2ceb2679d1e799c5a71354a8c5f20dee3d3e997e))
* **agent:** serve the netbird DNS zone on the host ([b285d90](https://github.com/cwbitz/remnawave-nodes-iac/commit/b285d904c97d8f1658d40c3350b8445856cf5ee3))
* **bootstrap:** add a timezone operator knob ([0451727](https://github.com/cwbitz/remnawave-nodes-iac/commit/04517271e275e73c0da6a83f81828ba4b47faed8))
* **config:** align the operator surface with the role domains ([5b09d19](https://github.com/cwbitz/remnawave-nodes-iac/commit/5b09d19d5eb125150a63b325670c51d44ace8210))
* **deploy:** bootstrap every node before the site deploy ([4d7268d](https://github.com/cwbitz/remnawave-nodes-iac/commit/4d7268d5f9f2633a3d4902ba899cfa1185ecd571))
* **firewall:** accept port ranges and validate before the live ruleset ([69e51f1](https://github.com/cwbitz/remnawave-nodes-iac/commit/69e51f19559929aa10df76db038104b8f8b3e053))
* **firewall:** add a default-deny inbound host firewall ([700296e](https://github.com/cwbitz/remnawave-nodes-iac/commit/700296ecea02dfbbc63471d22c621e025029c7df))
* **lint:** audit the example host vars against the project knobs ([e3c0a34](https://github.com/cwbitz/remnawave-nodes-iac/commit/e3c0a345104ab2e79d8cd25596ef708984d537c2))
* **lint:** reject real identifiers in tracked files ([9f47ab7](https://github.com/cwbitz/remnawave-nodes-iac/commit/9f47ab7e05777fe7cae9e767bc3d3da5efe8bcc6))
* **make:** auto-detect the single host in vault-edit ([b887c10](https://github.com/cwbitz/remnawave-nodes-iac/commit/b887c10da1304e547ce2ea8282be73ee0e4f2179))
* **make:** refresh host keys before bootstrap and deploy ([219b07f](https://github.com/cwbitz/remnawave-nodes-iac/commit/219b07f098b192c21c2c34a817a499632be1a4a0))
* **make:** rename HOST_KEY to REFRESH and trim the scaffolded vault ([2ce34dd](https://github.com/cwbitz/remnawave-nodes-iac/commit/2ce34dd8a61706eeadd4a106c66a6e61e8ab98a6))
* **make:** report the key count after sorting the vault ([e8b2d53](https://github.com/cwbitz/remnawave-nodes-iac/commit/e8b2d53f53ac4ebce5652a493bd432cef9e04d75))
* **make:** sort vault keys after editing ([47b2f99](https://github.com/cwbitz/remnawave-nodes-iac/commit/47b2f99886b1ae29452eb295e9b7690e21aaeabe))
* **make:** unify FORCE, scope host keys and dedupe host lookup ([946e2ae](https://github.com/cwbitz/remnawave-nodes-iac/commit/946e2ae87d3ed6a0f5e8b7f0aa3b95a422696838))
* **monitoring:** add the CrowdSec blocklist importer and Alloy metric push ([a3813ce](https://github.com/cwbitz/remnawave-nodes-iac/commit/a3813ceede1eb792a03ea2bd3ed675fb6996a8d1))
* **monitoring:** expose a knob that serves the central CrowdSec web UI ([1d06ace](https://github.com/cwbitz/remnawave-nodes-iac/commit/1d06ace33c077ef31da1945d5ad68a2cbfefbad0))
* **monitoring:** expose the node_exporter collector set ([adb1b2c](https://github.com/cwbitz/remnawave-nodes-iac/commit/adb1b2c4a167cf5f0611e37836b828faadadade3))
* **monitoring:** resolve the Loki push URL through NetBird DNS ([24d849d](https://github.com/cwbitz/remnawave-nodes-iac/commit/24d849dd661c6453fdf877a83d36fb34d37d6585))
* **monitoring:** ship curated journal presets to Loki ([95c2a6b](https://github.com/cwbitz/remnawave-nodes-iac/commit/95c2a6b122ce26d78be0ddff78fae8d410d8db41))
* **monitoring:** tear down the components that are disabled ([88aacb5](https://github.com/cwbitz/remnawave-nodes-iac/commit/88aacb57a26f6fefe4f1f17e0fe21143446f8f83))
* **sshd:** add opt-in key-only SSH hardening ([828c89d](https://github.com/cwbitz/remnawave-nodes-iac/commit/828c89dea06138719085ab01d9d4f0b00d38974e))
* **validation:** add the operator-knob schema and preflight ([344fe58](https://github.com/cwbitz/remnawave-nodes-iac/commit/344fe587fa0963039c4cc5855ea2f4fa4e9d3939))
* **validation:** reject SSH host-key verification bypasses ([826c7e2](https://github.com/cwbitz/remnawave-nodes-iac/commit/826c7e2391ce655406a3a279edd87ca8c72e3ace))
* **validation:** require the knob schema to cover the example ([327b149](https://github.com/cwbitz/remnawave-nodes-iac/commit/327b1492b3dc4ad2b1b64615f3f34cc2cb78f3c2))


### Bug Fixes

* **agent:** redact the overlay setup key from verbose output ([bb87d35](https://github.com/cwbitz/remnawave-nodes-iac/commit/bb87d3530cc54e66985d83b95fcc97727c1ffc4a))
* **bootstrap:** derive the security mirror when the knob is empty ([81a7570](https://github.com/cwbitz/remnawave-nodes-iac/commit/81a75704bb274cd8a08fea0c2821586cd8607d20))
* **bootstrap:** map an unresolvable hostname to the loopback alias ([005a0d8](https://github.com/cwbitz/remnawave-nodes-iac/commit/005a0d8c6592ae26e863dda7f3dad2d53e423749))
* **bootstrap:** only accept an SSH identity that can escalate to root ([42c22c7](https://github.com/cwbitz/remnawave-nodes-iac/commit/42c22c723e037c3f9a89c855ba39238d9b7b5bff))
* **bootstrap:** verify escalation and the requested timezone ([2a01f3d](https://github.com/cwbitz/remnawave-nodes-iac/commit/2a01f3ddc26c0dc1450f366fa9dd0af838f062bd))
* **dry-run:** skip absent services and the overlay wait in check mode ([0e181a9](https://github.com/cwbitz/remnawave-nodes-iac/commit/0e181a9229de337b1851ee2fe767f6a089152673))
* **firewall:** retire the one-shot legacy table cleanup ([50da1ad](https://github.com/cwbitz/remnawave-nodes-iac/commit/50da1add7962309fd4c3d6ed097efcd7143a5b27))
* **gitignore:** re-include the example host_vars without a trailing slash ([1687caf](https://github.com/cwbitz/remnawave-nodes-iac/commit/1687caf722670d0666519743706fadfa35d8a406))
* **helpers:** keep control-node tasks unprivileged under become ([8fca14f](https://github.com/cwbitz/remnawave-nodes-iac/commit/8fca14f34d920a9925e286f52e5bf48bd2dc641a))
* **helpers:** reinstall Docker when Compose is missing ([b2a293c](https://github.com/cwbitz/remnawave-nodes-iac/commit/b2a293c00cd37604468369a037c9969901ed1dd8))
* **helpers:** resolve ansible-vault from the running interpreter ([ccef28d](https://github.com/cwbitz/remnawave-nodes-iac/commit/ccef28d02d98a235e85961b7e810a591fbcd2cae))
* **hostkeys:** refresh known_hosts atomically and reject changed keys ([b7c4b3d](https://github.com/cwbitz/remnawave-nodes-iac/commit/b7c4b3dba39336155e8a4943629b4ce4de69cac3))
* **make:** skip validate-knobs when the inventory is missing ([ed1275f](https://github.com/cwbitz/remnawave-nodes-iac/commit/ed1275ff54f4c8b8650ef5a4928e5e912f1206f2))
* **monitoring:** bind the overlay addresses reliably at boot ([846ddde](https://github.com/cwbitz/remnawave-nodes-iac/commit/846ddde2bcbcce1f7d223f0a332671671f588b6e))
* **monitoring:** drop the duplicated node_exporter collector list ([6bf8e39](https://github.com/cwbitz/remnawave-nodes-iac/commit/6bf8e396c5d68297c239a369b1262e9b8ecc7de8))
* **monitoring:** let the tagged cleanup inherit its tags ([a29228e](https://github.com/cwbitz/remnawave-nodes-iac/commit/a29228ea3d821008e0a0a763e7330e56258e24d1))
* **monitoring:** warn when the central Loki is unreachable ([e0536f0](https://github.com/cwbitz/remnawave-nodes-iac/commit/e0536f00acdfe52c489b3337baa3c07e69c3022c))
* **playbooks:** keep control-node plays from escalating privileges ([f9163cf](https://github.com/cwbitz/remnawave-nodes-iac/commit/f9163cfebf3e409801a777e2e451bb9ef70459e5))
* **preflight:** name the host in the placeholder message ([e4361f6](https://github.com/cwbitz/remnawave-nodes-iac/commit/e4361f65e26e6e9a74127de2ffb504dc0d252899))
* **remnanode:** pin the node image version ([7da606f](https://github.com/cwbitz/remnawave-nodes-iac/commit/7da606f3f0fbb6506edee2b5bca990b0023d1d45))


### Code Refactoring

* **bootstrap:** take the service-account password from the vault ([bc42d3a](https://github.com/cwbitz/remnawave-nodes-iac/commit/bc42d3ab3974714b567b448215ff5733dd129fc7))
* drop code comments and align the operator surface ([c40888b](https://github.com/cwbitz/remnawave-nodes-iac/commit/c40888b0c67928242959e49c88781ad749d87109))
* **firewall:** rename the unit/table and retire the legacy names ([5466cd8](https://github.com/cwbitz/remnawave-nodes-iac/commit/5466cd8cd5a70bdc4a6c62ee164358156cc8a0b2))
* **inventory:** rename the node group to remnanodes and pin the account names ([b8e3a2e](https://github.com/cwbitz/remnawave-nodes-iac/commit/b8e3a2e89945faa38dd3c109dffdf4622022bc69))
* **inventory:** source host connection and node config from the inventory ([1863347](https://github.com/cwbitz/remnawave-nodes-iac/commit/1863347b4adcf03ebeecd334bd7db7828dd596cf))
* normalize the operator knob names ([c09cdbb](https://github.com/cwbitz/remnawave-nodes-iac/commit/c09cdbb47ebf7c6cbfd9074cb7f389b9f5f8d261))
* **ssh:** keep non-secret SSH identity settings in host_vars ([d4ecedf](https://github.com/cwbitz/remnawave-nodes-iac/commit/d4ecedf04b502c7275d87df74152ca97a6eae6e1))

## Changelog

All notable changes to this project are documented here. Releases are cut from
Conventional Commits on `main` by release-please; do not edit this file by hand.
