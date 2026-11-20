SHELL := /bin/bash
.DEFAULT_GOAL := help

ANS_PLAY      := ansible-playbook
PLAYBOOK      := playbooks/site.yml
INV           := inventory/hosts.yml
INVENTORY_DIR := inventory
INVENTORY_HOSTS = ansible-inventory -i $(INV) --list 2>/dev/null | python3 -c 'import json,sys; print("\n".join(sorted(json.load(sys.stdin).get("_meta",{}).get("hostvars",{}))))'

TAGS ?=
TAGS_ARG = $(if $(TAGS),--tags $(TAGS),)
HOST ?=

comma := ,
HOST_LITERAL_BAD = $(strip $(findstring *,$(HOST))$(findstring ?,$(HOST))$(findstring [,$(HOST))$(findstring ],$(HOST))$(findstring !,$(HOST))$(findstring :,$(HOST)))
$(if $(HOST_LITERAL_BAD),$(error HOST must be comma-separated literal host names (no Ansible pattern syntax); got '$(HOST)'))
$(if $(word 2,$(HOST)),$(error HOST must be comma-separated literal host names (no spaces); got '$(HOST)'))
HOST_LIST = $(strip $(subst $(comma), ,$(HOST)))
HOST_ARG = $(if $(HOST),--limit '$(HOST):localhost',)
HOST_SINGLE_GUARD = test "$$(printf '%s' '$(HOST_LIST)' | wc -w)" -le 1 || { echo "ERROR: this target needs exactly one HOST; got '$(HOST)'." >&2; exit 2; }

IP ?=
PORT ?=

$(foreach v,HOST IP PORT,$(if $(filter environment,$(origin $(v))),$(warning $(v) is inherited from the environment; pass $(v)=... explicitly if unintended)))
REBUILD ?=

export ANSIBLE_VAULT_PASSWORD_FILE := $(HOME)/.config/projects/remnawave-nodes-iac/ansible_vault_password

VAULT_PASSWORD_HINT := ERROR: Ansible Vault cannot decrypt this file - the password in $(ANSIBLE_VAULT_PASSWORD_FILE) is missing or incorrect. Restore the original password, or re-encrypt the vault file with the current one.

SSHPASS_BIN   ?= $(HOME)/.local/bin/sshpass

KEYCHAIN_PIN     := $(CURDIR)/keychain.pin
KEYCHAIN_VERSION := $(shell awk '!/^#/ && NF {print $$1; exit}' $(KEYCHAIN_PIN))
KEYCHAIN_SHA256  := $(shell awk '!/^#/ && NF {print $$2; exit}' $(KEYCHAIN_PIN) | sed 's/^sha256://')
KEYCHAIN_URL     ?= https://github.com/danielrobbins/keychain/releases/download/$(KEYCHAIN_VERSION)/keychain-$(KEYCHAIN_VERSION).pyz
KEYCHAIN_BIN     ?= $(HOME)/.local/bin/keychain
KEYCHAIN_CACHE   ?= $(HOME)/.cache/remnawave-nodes-iac
KEYCHAIN_ASSET   := $(KEYCHAIN_CACHE)/keychain-$(KEYCHAIN_VERSION).pyz
KEYCHAIN_AGENT   := eval "$$($(KEYCHAIN_BIN) agent start --eval --quiet 2>/dev/null)"

SSH_AGENT_ENV   ?= $(HOME)/.cache/iac/ssh-agent.env
SSH_AGENT_RUN   ?= $(CURDIR)/scripts/run-with-ssh-agent.sh
SSH_AGENT_KEY_VARS ?= host_iac_ssh_privkey_file host_admin_ssh_privkey_file host_root_ssh_privkey_file
export SSH_AGENT_ENV
export SSH_AGENT_KEYCHAIN_BIN  := $(KEYCHAIN_BIN)
export SSH_AGENT_ANS_PLAY      := $(ANS_PLAY)
export SSH_AGENT_INVENTORY     := $(INV)
export SSH_AGENT_LOAD_PLAYBOOK := playbooks/ssh_agent_load.yml

SSH_AGENT_PROBE := ansible-inventory -i $(INV) --list 2>/dev/null | SSH_AGENT_KEY_VARS="$(SSH_AGENT_KEY_VARS)" python3 -c "import json,os,sys; names=os.environ['SSH_AGENT_KEY_VARS'].split(); vs=json.load(sys.stdin).get('_meta',{}).get('hostvars',{}); ks={os.path.expanduser(h.get(v)) for h in vs.values() for v in names if h.get(v)}; sys.exit(0 if any(os.path.isfile(k) and (os.stat(k).st_mode & 0o077) for k in ks) else 1)"

define SSH_AGENT_PREPARE
	@set -e; \
	mkdir -p "$$(dirname "$(SSH_AGENT_ENV)")"; \
	rm -f "$(SSH_AGENT_ENV)"; \
	if [ -n "$${SSH_AUTH_SOCK:-}" ] && ssh-add -l >/dev/null 2>&1; then \
		echo "ssh-agent: reusing loaded agent"; \
		echo "export SSH_AUTH_SOCK='$$SSH_AUTH_SOCK'" > "$(SSH_AGENT_ENV)"; exit 0; \
	fi; \
	if [ "$(SSH_AGENT_FORCE)" != "1" ] && ! $(SSH_AGENT_PROBE); then \
		echo "ssh-agent: not needed (keys usable or password auth)"; exit 0; \
	fi; \
	echo "ssh-agent: starting Keychain and loading keys"; \
	eval "$$($(KEYCHAIN_BIN) agent start --eval --quiet 2>/dev/null)"; \
	echo "export SSH_AUTH_SOCK='$$SSH_AUTH_SOCK'" > "$(SSH_AGENT_ENV)"; \
	$(ANS_PLAY) -i $(INV) $(SSH_AGENT_LOAD_PLAYBOOK)
endef

agent-needed: vault-init
	@$(SSH_AGENT_PROBE)

agent-fallback: ensure-keychain
	$(SSH_AGENT_PREPARE)

agent-ensure: ensure-keychain
	$(SSH_AGENT_PREPARE)
agent-ensure: SSH_AGENT_FORCE := 1

agent-load: vault-init ensure-keychain
	@$(KEYCHAIN_AGENT); \
	$(ANS_PLAY) -i $(INV) $(SSH_AGENT_LOAD_PLAYBOOK)

agent-check: ensure-keychain
	@$(KEYCHAIN_AGENT); \
	if ssh-add -l >/dev/null 2>&1; then \
		echo "ssh-agent: identities loaded"; \
	else \
		echo "ERROR: the Keychain ssh-agent has no identities loaded."; \
		echo "Load the connection keys with: make agent-load"; \
		exit 1; \
	fi

.PHONY: help
HELP_TARGETS := install prep edit view \
                deploy dry-run print \
                help

help: ## Show this help
	@printf '\nUsage: make <target> [VAR=value ...]\n\n'
	@awk -v order="$(HELP_TARGETS)" 'BEGIN { FS = ":.*?## "; n=split(order, a, " "); for (i=1;i<=n;i++) rank[a[i]]=i } \
		/^[a-zA-Z0-9_-]+:.*?## / { if ($$1 in rank) desc[$$1]=$$2 } \
		END { for (i=1;i<=n;i++) { t=a[i]; if (t in desc) printf "  \033[36m%-25s\033[0m %s\n", t, desc[t] } }' \
		$(MAKEFILE_LIST)
	@printf '\n'
.PHONY: install
install: ensure-sshpass ensure-keychain ## Install the pinned toolchain, Ansible collections and control-node dependencies
	@if command -v mise >/dev/null 2>&1; then mise install; \
	elif command -v asdf >/dev/null 2>&1; then asdf install; \
	else echo "Neither mise nor asdf found; install one, or ensure ansible-core 2.19.x is on PATH." >&2; exit 1; fi
	@$(MAKE) --no-print-directory ensure-ansible-collections

ensure-ansible-collections:
	@ansible-galaxy collection install -r requirements.yml

.PHONY: ensure-ansible-collections ensure-sshpass ensure-keychain keychain-fetch verify-keychain-pin \
        agent-needed agent-fallback agent-ensure agent-load agent-check require-inventory
ensure-sshpass:
	@set -e; \
	if command -v sshpass >/dev/null 2>&1 || [ -x "$(SSHPASS_BIN)" ]; then \
		echo "sshpass: present"; \
	elif sudo -n true >/dev/null 2>&1; then \
		echo "sshpass: installing via sudo apt-get..."; \
		sudo -n apt-get install -y sshpass; \
	else \
		echo "sshpass: installing rootless into $(dir $(SSHPASS_BIN))..."; \
		if ! command -v apt-get >/dev/null 2>&1 || ! command -v dpkg-deb >/dev/null 2>&1; then \
			echo "Cannot auto-install sshpass (apt-get/dpkg-deb not found)." >&2; \
			echo "Install sshpass manually, or use key-only bootstrap credentials." >&2; \
			exit 1; \
		fi; \
		tmp=$$(mktemp -d); \
		trap 'rm -rf "$$tmp"' EXIT; \
		cd "$$tmp"; \
		apt-get download sshpass >/dev/null 2>&1; \
		dpkg-deb -x sshpass_*.deb root; \
		mkdir -p "$(dir $(SSHPASS_BIN))"; \
		install -m 0755 root/usr/bin/sshpass "$(SSHPASS_BIN)"; \
		echo "sshpass installed: $(SSHPASS_BIN)"; \
	fi

keychain-fetch:
	@set -e; \
	mkdir -p "$(KEYCHAIN_CACHE)"; \
	if [ -f "$(KEYCHAIN_ASSET)" ] \
	   && printf '%s  %s\n' "$(KEYCHAIN_SHA256)" "$(KEYCHAIN_ASSET)" | sha256sum -c - >/dev/null 2>&1; then \
		exit 0; \
	fi; \
	echo "downloading keychain v$(KEYCHAIN_VERSION)..."; \
	if ! curl -fsSL -o "$(KEYCHAIN_ASSET).tmp" "$(KEYCHAIN_URL)"; then \
		echo "ERROR: failed to download Keychain v$(KEYCHAIN_VERSION)." >&2; \
		echo "  URL: $(KEYCHAIN_URL)" >&2; \
		echo "  Download it manually to: $(KEYCHAIN_ASSET)" >&2; \
		echo "  then re-run 'make install'." >&2; \
		rm -f "$(KEYCHAIN_ASSET).tmp"; \
		exit 1; \
	fi; \
	mv "$(KEYCHAIN_ASSET).tmp" "$(KEYCHAIN_ASSET)"

verify-keychain-pin: keychain-fetch
	@set -e; \
	printf '%s  %s\n' "$(KEYCHAIN_SHA256)" "$(KEYCHAIN_ASSET)" | sha256sum -c -; \
	echo "keychain pin OK: v$(KEYCHAIN_VERSION)"

ensure-keychain: verify-keychain-pin
	@set -e; \
	if [ -f "$(KEYCHAIN_BIN)" ] \
	   && printf '%s  %s\n' "$(KEYCHAIN_SHA256)" "$(KEYCHAIN_BIN)" | sha256sum -c - >/dev/null 2>&1; then \
		echo "keychain:  present (v$(KEYCHAIN_VERSION), $(KEYCHAIN_BIN))"; exit 0; \
	fi; \
	mkdir -p "$$(dirname "$(KEYCHAIN_BIN)")"; \
	install -m 0755 "$(KEYCHAIN_ASSET)" "$(KEYCHAIN_BIN)"; \
	echo "keychain installed: $(KEYCHAIN_BIN) (v$(KEYCHAIN_VERSION))"

.PHONY: prep
prep: vault-init ## Scaffold a node: inventory entry and host_vars pair; HOST=<host>, IP=<address>, FORCE=1 overwrites
	@$(HOST_SINGLE_GUARD); set -e; host="$(HOST)"; \
	if [ -z "$$host" ]; then \
		hosts="$$($(INVENTORY_HOSTS))"; \
		set -- $$hosts; \
		if [ "$$#" -gt 1 ]; then echo "ERROR: $(INV) holds $$# hosts; pass HOST=<hostname>." >&2; exit 1; fi; \
		[ "$$#" -eq 1 ] && host="$$1"; \
	fi; \
	host="$${host:-remnanode-1}"; ip="$(IP)"; ip="$${ip:-CHANGE_ME_HOST_IP}"; \
	if [ -e "$(INV)" ]; then :; else python3 $(CURDIR)/scripts/render_clean_template.py inventory/hosts.yml.example $(INV); echo "Created $(INV) from example (comments stripped)"; fi; \
	install -d -m 0700 $(INVENTORY_DIR)/host_vars/$$host; \
	if [ ! -e $(INVENTORY_DIR)/host_vars/$$host/main.yml ]; then python3 $(CURDIR)/scripts/render_clean_template.py --strip-blank-lines $(INVENTORY_DIR)/host_vars/example/main.yml $(INVENTORY_DIR)/host_vars/$$host/main.yml; fi; \
	chmod 0644 $(INVENTORY_DIR)/host_vars/$$host/main.yml; \
	if [ ! -e $(INVENTORY_DIR)/host_vars/$$host/vault.yml ]; then python3 $(CURDIR)/scripts/render_clean_template.py --strip-blank-lines $(INVENTORY_DIR)/host_vars/example/vault.yml.example $(INVENTORY_DIR)/host_vars/$$host/vault.yml; fi; \
	if grep -q 'ANSIBLE_VAULT' $(INVENTORY_DIR)/host_vars/$$host/vault.yml; then :; else \
		echo "Encrypting $(INVENTORY_DIR)/host_vars/$$host/vault.yml..."; \
		ansible-vault encrypt $(INVENTORY_DIR)/host_vars/$$host/vault.yml; \
	fi; \
	chmod 0600 $(INVENTORY_DIR)/host_vars/$$host/vault.yml; \
	entry=$$(python3 $(CURDIR)/scripts/ensure_inventory_host.py "$(INV)" "$$host" --group remnanodes --ansible-host "$$ip" $(if $(PORT),--ansible-port "$(PORT)") $(if $(FORCE),--force)); \
	printf '%s\n' "$$entry"; \
	effective_host=$$(printf '%s\n' "$$entry" | sed -n 's/^effective ansible_host=//p'); \
	effective_port=$$(printf '%s\n' "$$entry" | sed -n 's/^effective ansible_port=//p'); \
	echo "Scaffolded $(INVENTORY_DIR)/host_vars/$$host/ (ansible_host: $${effective_host:-unset}, ansible_port: $${effective_port:-22} in $(INV))"; \
	echo "next: make edit HOST=$$host   (fill the CHANGE_ME_* values; generated ones fill themselves)"; \
	echo "      verify: make print HOST=$$host"

.PHONY: rebuild-reset
rebuild-reset:
	@if [ -n "$(REBUILD)" ]; then \
		echo "REBUILD=1: a changed host key will be accepted, cached facts and generated state are dropped"; \
		echo "           delete host-returned secrets from vault.yml (tokens, setup keys) before the first run"; \
		rm -rf .cache/facts; \
	fi

.PHONY: hostkeys
hostkeys: vault-init
	@set -e; \
	nh="$(HOME)/.ssh/known_hosts"; mkdir -p "$$(dirname "$$nh")"; tmp=$$(mktemp); targets=$$(mktemp); tsv=$$(mktemp); pub=$$(mktemp); failures=0; strict="$(if $(HOST),1,0)"; \
	trap 'rm -f "$$tmp" "$$targets" "$$tsv" "$$pub"' EXIT; \
	if [ -f "$$nh" ]; then cp "$$nh" "$$tmp"; else : > "$$tmp"; fi; \
	$(ANS_PLAY) -i $(INV) playbooks/host_keys.yml -e host_keys_out="$$targets" -e host_keys_hosts='$(HOST)' >/dev/null; \
	python3 -c 'import json,sys; [print("{}\t{}\t{}".format(t["name"],t["host"],t["port"])) for t in json.load(open(sys.argv[1]))]' "$$targets" > "$$tsv"; \
	mv "$$tsv" "$$targets"; \
	test -s "$$targets" || { echo "ERROR: no hosts resolved from the inventory."; exit 1; }; \
	while IFS=$$'\t' read -r name host port; do \
		[ -n "$$name" ] || continue; \
		echo "host key: $$name ($$host:$$port)"; \
		if ! keys="$$(ssh-keyscan -T 5 -p "$$port" "$$host" 2>/dev/null)" || [ -z "$$keys" ]; then \
			echo "ERROR: ssh-keyscan returned no host key for $$host:$$port; entry left unchanged" >&2; failures=1; continue; \
		fi; \
		if [ "$$port" = "22" ]; then key="$$host"; else key="[$$host]:$$port"; fi; \
		old=$$(ssh-keygen -F "$$key" -f "$$tmp" 2>/dev/null | awk '!/^#/ && NF {print $$2" "$$3}' | sort); \
		new=$$(printf '%s\n' "$$keys" | awk '{print $$2" "$$3}' | sort); \
		printf '%s\n' "$$keys" | awk '{print $$2" "$$3}' > "$$pub"; \
		ssh-keygen -lf "$$pub" 2>/dev/null | sed 's/^/  fingerprint: /' >&2 || true; \
		if [ -n "$$old" ] && [ -n "$$(comm -23 <(printf '%s\n' "$$old") <(printf '%s\n' "$$new"))" ]; then \
			if [ "$(FORCE)" != "1" ] && [ "$(REBUILD)" != "1" ]; then \
				echo "ERROR: host key changed for $$key; verify the fingerprint, then re-run with FORCE=1 (or REBUILD=1 after a host rebuild)" >&2; failures=1; continue; \
			fi; \
			echo "  changed: replacing the recorded key" >&2; \
		fi; \
		ssh-keygen -R "$$key" -f "$$tmp" >/dev/null 2>&1 || true; \
		printf '%s\n' "$$keys" >> "$$tmp"; \
	done < "$$targets"; \
	chmod 600 "$$tmp"; mv "$$tmp" "$$nh"; \
	if [ "$$failures" -ne 0 ]; then \
		if [ "$$strict" = "1" ]; then \
			echo "ERROR: the selected host key was not refreshed; known_hosts is unchanged for it" >&2; exit 1; \
		else \
			echo "WARNING: some host keys were not refreshed; known_hosts updated for the rest" >&2; \
		fi; \
	fi; \
	echo "host keys refreshed in $$nh"

.PHONY: vault-init
vault-init:
	@mkdir -p $(dir $(ANSIBLE_VAULT_PASSWORD_FILE))
	@if [ ! -s "$(ANSIBLE_VAULT_PASSWORD_FILE)" ]; then \
		openssl rand -base64 32 > "$(ANSIBLE_VAULT_PASSWORD_FILE)"; \
		chmod 600 "$(ANSIBLE_VAULT_PASSWORD_FILE)"; \
		echo "vault password generated: $(ANSIBLE_VAULT_PASSWORD_FILE) (BACK IT UP in a password manager)"; \
	fi
	@test "$$(wc -c < "$(ANSIBLE_VAULT_PASSWORD_FILE)")" -ge 44 || { echo "ERROR: vault password too weak"; exit 1; }
	@f=""; \
	for c in $$(find "$(INVENTORY_DIR)" -type f -name 'vault*.yml' 2>/dev/null); do \
		if head -c 16 "$$c" | grep -q 'ANSIBLE_VAULT'; then f="$$c"; break; fi; \
	done; \
	if [ -n "$$f" ] && command -v ansible-vault >/dev/null 2>&1; then \
		ansible-vault view "$$f" >/dev/null 2>&1 \
			|| { printf '%s\n' "$(VAULT_PASSWORD_HINT)" >&2; exit 1; }; \
	fi

.PHONY: require-inventory
require-inventory:
	@if [ ! -f "$(INV)" ]; then \
		echo "ERROR: $(INV) does not exist yet." >&2; \
		echo "Create a host from the committed template first:" >&2; \
		echo "  make prep HOST=<hostname>" >&2; \
		echo "(it copies inventory/hosts.yml.example -> $(INV) and scaffolds host_vars/<hostname>/)" >&2; \
		exit 1; \
	fi

.PHONY: edit
edit: vault-init require-inventory ## Edit a node's vault, keys sorted; HOST=<host>
	@host="$(HOST)"; \
	if [ -z "$$host" ]; then \
		hosts="$$($(INVENTORY_HOSTS))"; \
		set -- $$hosts; \
		[ "$$#" -eq 1 ] && host="$$1"; \
	fi; \
	if [ -z "$$host" ]; then \
		echo "Usage: make edit HOST=<hostname> (required when the inventory has more than one host)" >&2; \
		echo "Available hosts:" >&2; \
		printf '  %s\n' $$hosts >&2; \
		exit 1; \
	fi; \
	p="$(INVENTORY_DIR)/host_vars/$$host/vault.yml"; \
	if [ ! -f "$$p" ]; then echo "No such vault file: $$p" >&2; exit 1; fi; \
	if grep -q 'ANSIBLE_VAULT' "$$p"; then :; else \
		echo "Encrypting plaintext $$p before editing..."; \
		ansible-vault encrypt "$$p" >/dev/null; \
	fi; \
	python3 $(CURDIR)/scripts/edit_vault.py "$$p"

.PHONY: view
view: vault-init require-inventory ## Print every node's vault, or one with HOST=<host>
	@hosts="$(HOST)"; \
	[ -n "$$hosts" ] || hosts="$$($(INVENTORY_HOSTS))"; \
	if [ -z "$$hosts" ]; then \
		echo "No hosts found in $(INV)." >&2; exit 1; \
	fi; \
	for host in $$hosts; do \
		p="$(INVENTORY_DIR)/host_vars/$$host/vault.yml"; \
		printf '\n\033[1m== %s ==\033[0m\n' "$$p"; \
		if [ ! -f "$$p" ]; then echo "(missing)"; continue; fi; \
		if grep -q 'ANSIBLE_VAULT' "$$p"; then \
			ansible-vault view "$$p" 2>/dev/null \
				|| { printf '%s\n' "$(VAULT_PASSWORD_HINT)" >&2; exit 1; }; \
		else cat "$$p"; fi; \
	done

.PHONY: validate-knobs
validate-knobs: vault-init
	@if [ -f $(INV) ]; then $(ANS_PLAY) -i $(INV) playbooks/validate_knobs.yml; else echo "validate-knobs: $(INV) missing, skipped"; fi

.PHONY: test
test:
	pytest -q tests

.PHONY: lint
lint: vault-init validate-knobs
	$(ANS_PLAY) --syntax-check playbooks/site.yml
	$(ANS_PLAY) --syntax-check playbooks/bootstrap.yml
	$(ANS_PLAY) --syntax-check playbooks/agent.yml
	$(ANS_PLAY) --syntax-check playbooks/monitoring.yml
	ansible-lint playbooks/site.yml playbooks/bootstrap.yml playbooks/agent.yml playbooks/monitoring.yml
	yamllint .
	shellcheck scripts/*.sh
	python3 -m compileall -q scripts
	$(ANS_PLAY) --syntax-check tests/knob_contract.yml
	$(ANS_PLAY) -i localhost, tests/knob_contract.yml
	python3 scripts/audit_example_knobs.py
	python3 scripts/check_host_keys.py
	python3 scripts/check_repo_privacy.py
	python3 scripts/check_script_modes.py
	gitleaks dir . --config .gitleaks.toml --no-banner --redact

.PHONY: dry-run
dry-run: vault-init rebuild-reset validate-knobs agent-fallback ## Preview the deploy with --check --diff; HOST=<hosts>, REBUILD=1 after a rebuild
	$(SSH_AGENT_RUN) $(ANS_PLAY) -i $(INV) $(PLAYBOOK) $(HOST_ARG) --check --diff $(TAGS_ARG)

.PHONY: deploy
deploy: vault-init rebuild-reset hostkeys validate-knobs agent-fallback ## Bootstrap the selected nodes, then deploy the Remnawave node stack; HOST=<hosts>, TAGS=<tags>, REBUILD=1 after a rebuild
	@set -e; \
	hosts="$(HOST_LIST)"; \
	if [ -z "$$hosts" ]; then \
		hosts="$$(ansible -i $(INV) --list-hosts remnanodes 2>/dev/null \
			| tail -n +2 | awk '$$1=$$1' | sed '/^$$/d')"; \
	fi; \
	if [ -z "$$hosts" ]; then \
		echo "ERROR: no remnanodes host resolved from $(INV)." >&2; \
		echo "Scaffold one with: make prep HOST=<hostname> IP=<management-ip>" >&2; \
		exit 1; \
	fi; \
	for host in $$hosts; do \
		echo "==> Bootstrapping $$host (playbooks/bootstrap.yml: service account, Docker)..."; \
		$(SSH_AGENT_RUN) $(ANS_PLAY) -i $(INV) playbooks/bootstrap.yml -e bootstrap_host="$$host"; \
	done
	@echo "==> Deploying the Remnawave node stack (playbooks/site.yml)..."
	$(SSH_AGENT_RUN) $(ANS_PLAY) -i $(INV) $(PLAYBOOK) $(HOST_ARG) $(TAGS_ARG)

.PHONY: agent
agent: vault-init agent-fallback
	$(SSH_AGENT_RUN) $(ANS_PLAY) -i $(INV) playbooks/agent.yml $(HOST_ARG)

.PHONY: monitoring
monitoring: vault-init agent-fallback
	$(SSH_AGENT_RUN) $(ANS_PLAY) -i $(INV) playbooks/monitoring.yml $(HOST_ARG)

.PHONY: print
print: vault-init require-inventory ## Print a node's resolved variables, including decrypted vault values; HOST=<host>
	@host="$(HOST)"; \
	if [ -z "$$host" ]; then \
		hosts="$$($(INVENTORY_HOSTS))"; \
		set -- $$hosts; \
		[ "$$#" -eq 1 ] && host="$$1"; \
	fi; \
	if [ -z "$$host" ]; then \
		echo "Usage: make print HOST=<hostname> (required when the inventory has no single host)" >&2; exit 1; \
	fi; \
	echo "Resolved host: $$host"; \
	ansible -i $(INV) "$$host" -m ansible.builtin.debug -a "var=hostvars[inventory_hostname]"
