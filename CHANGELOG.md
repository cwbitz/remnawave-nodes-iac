# Changelog

## [3.0.0](https://github.com/cwbitz/remnawave-nodes-iac/compare/v2.1.0...v3.0.0) (2026-11-20)


### ⚠ BREAKING CHANGES

* **make:** `make host-init`, `make host-bootstrap`, `make vault-edit`, `make vault-view` and `make hostkey-init` no longer exist; use `make prep`, `make deploy`, `make edit`, `make view` and `make hostkeys`. HOST_IP/HOST_PORT are now IP/PORT, and HOST accepts a comma-separated list of node names.

### Bug Fixes

* **agent:** restart the overlay agent when the daemon is not live ([#30](https://github.com/cwbitz/remnawave-nodes-iac/issues/30)) ([80f20ba](https://github.com/cwbitz/remnawave-nodes-iac/commit/80f20bac958b58ad7057c4d6e6b0b3de3d810907))
* **bootstrap:** report a changed host key as itself, not as bad credentials ([#28](https://github.com/cwbitz/remnawave-nodes-iac/issues/28)) ([5402eef](https://github.com/cwbitz/remnawave-nodes-iac/commit/5402eeff74802954a9e0a43dfffab0aba21112d3))
* **monitoring:** skip the CrowdSec pre-upgrade backup on a fresh host ([#29](https://github.com/cwbitz/remnawave-nodes-iac/issues/29)) ([743bd1a](https://github.com/cwbitz/remnawave-nodes-iac/commit/743bd1a4e0dcdd218875415ee5565165c5abe452))


### Code Refactoring

* **make:** rename the operator targets and accept a HOST list ([#26](https://github.com/cwbitz/remnawave-nodes-iac/issues/26)) ([aef2d41](https://github.com/cwbitz/remnawave-nodes-iac/commit/aef2d4141da8400de9afeb3d2a250848d586e406))

## [2.1.0](https://github.com/cwbitz/remnawave-nodes-iac/compare/v2.0.0...v2.1.0) (2026-11-19)


### Features

* **ssh-agent:** gate the insecure key fallback behind AGENT_ALLOW_INSECURE ([#23](https://github.com/cwbitz/remnawave-nodes-iac/issues/23)) ([63d39b3](https://github.com/cwbitz/remnawave-nodes-iac/commit/63d39b3683bd7ef9e9c5674d435770b132baace3))

## [2.0.0](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.2.0...v2.0.0) (2026-11-18)


### ⚠ BREAKING CHANGES

* **monitoring:** monitoring.enabled is no longer an operator knob; drop it from host_vars and toggle the components themselves.
* **inventory:** every host_vars/<host>/main.yml must move its firewall, sshd, monitoring and netbird keys under the matching group, and the NetBird overlay must be enabled explicitly on each node.
* **inventory:** every host_vars/<host>/main.yml must move its flat operator keys under the matching group.

### Code Refactoring

* **inventory:** cascade operator knobs into grouped mappings ([#18](https://github.com/cwbitz/remnawave-nodes-iac/issues/18)) ([b04d875](https://github.com/cwbitz/remnawave-nodes-iac/commit/b04d87588ab99e42d9b2e804adff0de752809d39))
* **inventory:** cascade the service knobs into grouped mappings ([#21](https://github.com/cwbitz/remnawave-nodes-iac/issues/21)) ([9b45c0c](https://github.com/cwbitz/remnawave-nodes-iac/commit/9b45c0ca5cad5c9680e5bbebbdd5314a153f8815))
* **monitoring:** derive the slice toggle from its components ([#22](https://github.com/cwbitz/remnawave-nodes-iac/issues/22)) ([58759ff](https://github.com/cwbitz/remnawave-nodes-iac/commit/58759ffbfd46b69a5af43c5042b54bef9c5b5bc0))

## [1.2.0](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.1.4...v1.2.0) (2026-11-16)


### Features

* **make:** add a rebuilt-host reset switch ([#15](https://github.com/cwbitz/remnawave-nodes-iac/issues/15)) ([b6b5f10](https://github.com/cwbitz/remnawave-nodes-iac/commit/b6b5f10a82a83d56c6b1e196d90da08c1fea2e94))

## [1.1.4](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.1.3...v1.1.4) (2026-11-16)


### Bug Fixes

* **privacy:** reject a tracked vault backup file ([#12](https://github.com/cwbitz/remnawave-nodes-iac/issues/12)) ([0ea7b66](https://github.com/cwbitz/remnawave-nodes-iac/commit/0ea7b662b8dd12157922eec8ae7785888042ff3e))

## [1.1.3](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.1.2...v1.1.3) (2026-11-12)


### Bug Fixes

* **ci:** stream the SSH runner output instead of buffering it ([#10](https://github.com/cwbitz/remnawave-nodes-iac/issues/10)) ([db5dd46](https://github.com/cwbitz/remnawave-nodes-iac/commit/db5dd46c1ddf7ae74bb56b4f7f937e0029166a48))

## [1.1.2](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.1.1...v1.1.2) (2026-11-12)


### Bug Fixes

* **vault:** refuse a vault edit that would drop newly written secrets ([#8](https://github.com/cwbitz/remnawave-nodes-iac/issues/8)) ([4722a22](https://github.com/cwbitz/remnawave-nodes-iac/commit/4722a2257e1f749b8daf9b4a9410954664185a85))

## [1.1.1](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.1.0...v1.1.1) (2026-10-28)


### Bug Fixes

* **release:** drop the unused component from the release config ([#5](https://github.com/cwbitz/remnawave-nodes-iac/issues/5)) ([a5e0a23](https://github.com/cwbitz/remnawave-nodes-iac/commit/a5e0a23ef4ad4814902095428b3c6f791cdf63ae))

## [1.1.0](https://github.com/cwbitz/remnawave-nodes-iac/compare/v1.0.0...v1.1.0) (2026-10-28)


### Features

* **monitoring:** expose the Alloy scrape cadence ([#3](https://github.com/cwbitz/remnawave-nodes-iac/issues/3)) ([d29172e](https://github.com/cwbitz/remnawave-nodes-iac/commit/d29172e3fb41129bc718bf2c1f7e8c93e4988ab1))

## Changelog

All notable changes to this project are documented here. Releases are cut from
Conventional Commits on `main` by release-please; do not edit this file by hand.
