# 运维手册

[English](RUNBOOK.md) | [简体中文](RUNBOOK.zh-CN.md)

Remnawave 代理节点（Node）的运维流程。总览见 `README.md`，设计说明与注意事项见
`AGENTS.md`。

## 0. 前置（一次性）

- 一台全新的 **Debian 13** VPS，可经 SSH 以 `root` 登录（初始只需 `root`）。无需
  预装 Docker，也无需先更新系统。
- 控制端：ansible-core（已固定版本）、Python 3、`openssl`，以及 Galaxy collections：
  `make install`。
- 主机条目：`make host-init HOST=<hostname>` —— 脚手架 `host_vars/<host>/`
  （加密 `vault.yml`）并把主机名写入 `inventory/hosts.yml`；HOST 缺省为
  `remnanode-1`。然后编辑 `inventory/host_vars/<host>/main.yml` 与 vault
  （`make vault-edit HOST=<host>`）。
- 在 vault 中填写：IP + SSH 凭据；NetBird 输入
  （`vault_netbird_management_url`、`vault_netbird_setup_key`）；以及从 Panel 复制的
  Remnawave 节点输入（`vault_remnanode_node_port`、`vault_remnanode_secret_key`）。
- 以 root 创建非 root 服务账户（一次）：`make host-bootstrap`，然后在 `vault.yml`
  中把连接指向该账户。除 `host_allow_root_login=true` 外，部署拒绝以 root 运行。
- vault 密码文件由 make 目标自动创建
  （`~/.config/projects/remnawave-nodes-iac/ansible_vault_password`）；请妥善保管。

## 1. 在 Panel 中创建节点

1. Remnawave Panel：**Nodes → Management**，添加节点（名称、地址、`Node Port`）。
2. 点击 **Copy docker-compose.yml**。
3. 把其中的 `NODE_PORT` 与 `SECRET_KEY` 写入 `vault.yml`，变量名为
   `vault_remnanode_node_port` 与 `vault_remnanode_secret_key`。文件其余部分已是提交
   的模板。
4. 在主机 / 云防火墙中开放 `NODE_PORT`，**仅**对 Panel 的地址。

## 2. 部署

```bash
make dry-run     # 试运行（--check --diff）
make deploy      # 先初始化主机，再部署节点栈
```

`make lint`（语法检查 + `ansible-lint`）是内部 CI 检查，不出现在 `make help`。

聚焦 tag：`monitoring`、`remnanode`（`make deploy TAGS=remnanode`）。

`make deploy` 依次运行 `playbooks/bootstrap.yml`（服务账户 + Docker）与
`playbooks/site.yml`（加入 overlay + 监控，然后 Remnawave Node）。

验证：

```bash
ansible -i inventory/hosts.yml remnawave_nodes -m ansible.builtin.ping
ssh <host> 'cd /opt/remnanode && docker compose ps'
ssh <host> 'docker logs --tail=50 remnanode'
ssh <host> 'ip -4 -o addr show wt0'          # overlay 地址
ssh <host> 'ss -lntp | grep <NODE_PORT>'     # 节点监听 Panel
```

Panel 中该节点应在其首次下发配置后变为 **healthy/connected**。

## 3. 日常变更

- 编辑 `inventory/host_vars/<host>/main.yml`（非密钥）或 vault（密钥），然后
  `make deploy`。
- 镜像版本位于 `roles/remnanode/defaults/main.yml`、
  `roles/agent/defaults/main.yml`、`roles/monitoring/defaults/main.yml`
  （Renovate 跟踪）；`remnanode_version` 跟随 `latest`。
- 切勿在主机的 `/opt/remnanode`、`/opt/netbird-agent` 下直接编辑生成的文件 ——
  渲染即唯一事实来源。

## 4. Overlay 与监控

```bash
make agent        # 加入 / 重同步 NetBird overlay
make monitoring   # node_exporter + CrowdSec + firewall bouncer（含 agent）
```

- overlay 的 setup key 是 `vault_netbird_setup_key`；其自动分组决定中央可观测栈会发现
  什么。
- node_exporter 监听 `127.0.0.1:9100` 与 overlay 地址；CrowdSec 在 overlay 上暴露
  `:6060` 指标。二者由兄弟项目 `docker-stack-iac` 的 Prometheus 经 NetBird API 发现。
- CrowdSec 自带 `crowdsecurity/linux` + `crowdsecurity/sshd`，从 journal 读取 SSH
  单元；firewall bouncer 通过 nftables 执行拦截决策。

## 5. 升级与回滚

- **节点升级**：让 Renovate 升级 `remnanode_version`（或手动修改），然后
  `make deploy TAGS=remnanode`。
- **版本回滚**：设置上一个 tag 并重新部署。
- **整机重建**：重跑 `make host-init` / `make vault-edit`；已脚手架的主机上直接
  `make deploy` 重建容器。
- **配置回滚**：`git revert` 或编辑 per-host 变量，然后 `make deploy`。

## 6. 故障排查

| 现象 | 检查 / 处理 |
|---|---|
| Panel 显示节点离线 | 主机上 `ss -lntp | grep <NODE_PORT>`；Panel 能访问节点 IP:NODE_PORT；`vault_remnanode_secret_key` 与 Panel 节点一致；`docker logs remnanode`。 |
| 节点容器反复重启 | `docker logs remnanode`；确认 `NODE_PORT` / `SECRET_KEY` 正确且未变。 |
| overlay peer 无 `wt0` 地址 | `vault_netbird_setup_key` 与 `vault_netbird_management_url` 有效；`docker logs netbird`。更改 management URL 需新 key 并重置 `netbird_config` 卷。 |
| 中央 Prometheus 显示节点 down | peer 以可观测栈发现的分组加入（`endpoint`）；overlay 正常；从另一个 peer `curl -s <overlay-ip>:9100/metrics`。 |
| `make deploy` 拒绝 root | 符合预期：先 `make host-bootstrap`，再在 `vault.yml` 中改用 `ansible` 账户连接（或设 `host_allow_root_login=true`）。 |
| SSH 拒绝私钥（`UNPROTECTED PRIVATE KEY FILE`、`are too open`） | 共享脚本 `scripts/run-with-ssh-agent.sh` 会启动固定的 Keychain agent、加载 vault 密钥并重试一次。仍失败则检查 `vault_*_ssh_privkey_file` 路径并运行 `make agent-load`。 |
| 无法读取 vault 文件 | 必须是 ansible-vault 加密的；helper 会在下次写入时把明文文件重新加密。 |

常用命令：

```bash
make print [HOST=<host>]                        # 解析后的变量（含解密 vault）
ssh <host> 'cd /opt/remnanode && docker compose logs -f'
ssh <host> 'cd /opt/remnanode && docker compose ps'
ssh <host> 'systemctl status crowdsec crowdsec-firewall-bouncer prometheus-node-exporter'
```

## 7. 密钥与安全

- 切勿提交 `vault.yml`（已 gitignore，即使加密）。
- 解密任何 vault 都需要 vault 密码文件。
- `SECRET_KEY` 用于节点向 Panel 认证 —— 把 `vault.yml` 当作在线凭据库，并把
  `NODE_PORT` 限制为仅 Panel 可访问。
