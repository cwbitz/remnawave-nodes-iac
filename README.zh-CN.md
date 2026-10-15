# remnawave-nodes-iac

[English](README.md) | [简体中文](README.zh-CN.md)

用 Ansible 管理 **Remnawave 代理节点（Node）** —— 即由 Remnawave Panel 下发代理
配置的轻量 `remnawave/node`（内置 Xray-core）容器。项目从一台全新 Debian 系 VPS 的
**初始状态**开始管理：主机初始化、加入 NetBird 覆盖网络、主机监控与安全，最后部署
Remnawave Node 本身。

**Panel（控制面）** 与中央可观测栈位于兄弟项目 `docker-stack-iac`；**NetBird
management 服务端**位于兄弟项目 `netbird-iac`。本项目只拥有节点，并仅通过这两个控制
面的公共接口消费它们（对 Panel 是 `NODE_PORT` / `SECRET_KEY`，对 overlay 是
management URL + setup key）。

## 管理内容

```
┌──────────────────────────── Remnawave 节点 VPS ───────────────────────────┐
│                                                                            │
│  remnanode (Xray-core)          netbird agent          host security       │
│   network_mode: host   ───────  加入 overlay     ─────  node_exporter        │
│   监听 NODE_PORT                (wt0)                  CrowdSec + bouncer   │
│        ▲                                                                   │
└────────┼───────────────────────────────────────────────────────────────────┘
         │ Panel -> Node 内部 API（NODE_PORT、SECRET_KEY）
         │ NetBird overlay -> Prometheus 抓取 :9100 与 :6060
```

1. **主机初始化**（`playbooks/bootstrap.yml`，`make host-bootstrap`）：按
   `ansible → admin → root` 顺序探测 SSH 身份，必要时创建最小权限的 `ansible`
   服务账户（NOPASSWD sudo），并安装 Docker Engine + Compose v2。可选设置 APT /
   Docker registry 镜像。
2. **Overlay + 监控**（`roles/monitoring`，其内部包含 `roles/agent`）：安装
   `prometheus-node-exporter`、`crowdsec` 与 `crowdsec-firewall-bouncer`（nftables），
   并把主机加入 NetBird 覆盖网络，使中央 Prometheus/Alloy 无需公网端口即可抓取。
3. **Remnawave Node**（`roles/remnanode`）：渲染
   `/opt/remnanode/docker-compose.yml`，以 `NODE_PORT` / `SECRET_KEY` 运行
   `remnawave/node` 容器。

## Remnawave Node 输入

在 Panel 里进入 **Nodes → Management**，添加节点并点击 **Copy
docker-compose.yml**，内容形如：

```yaml
services:
  remnanode:
    container_name: remnanode
    hostname: remnanode
    image: remnawave/node:latest
    network_mode: host
    restart: always
    cap_add:
      - NET_ADMIN
    ulimits:
      nofile:
        soft: 1048576
        hard: 1048576
    environment:
      - NODE_PORT=2222
      - SECRET_KEY="xxxxxx"
```

把两个环境变量值写入本项目 vault（它们是仅有的节点专属密钥）：

```yaml
# inventory/host_vars/<host>/vault.yml
vault_remnanode_node_port: "2222"
vault_remnanode_secret_key: "xxxxxx"
```

该 compose 文件中其余静态部分即已提交的模板
`roles/remnanode/templates/remnanode/docker-compose.yml.j2`。渲染即唯一事实来源 ——
**不要**在主机上直接编辑生成的文件。

> 节点的 `NODE_PORT` 只应允许 **Panel** 访问。请在主机防火墙 / 上游安全组里把它限制
> 为 Panel 的地址；CrowdSec 防火墙 bouncer 只负责 nftables 拦截决策，并不构成基础
> 防火墙。

## NetBird overlay 输入

本项目不拥有 management 服务端，因此两项输入都保存在本项目 vault 中：

```yaml
# inventory/host_vars/<host>/vault.yml
vault_netbird_management_url: "https://netbird.example.com"
vault_netbird_setup_key: "..."   # 本节点的注册密钥
```

setup key 的自动分组决定了中央可观测栈会发现哪些 peer（默认 `endpoint`：无路由、无
exit/LAN 路由）。仅当节点需要为某个 routed network / exit node 转发流量时才设置
`netbird_agent_routing: true`。

## 依赖

- 一台全新的 **Debian 13** VPS，可经 SSH 以 `root` 登录（初始只需 `root`；bootstrap
  会创建 `ansible` 服务账户）。无需预装 Docker，也无需先更新系统。
- 控制端：`mise` 或 `asdf`、`openssl`，以及对主机的 SSH 访问。`sshpass` 仅
  `make host-bootstrap` 的密码探测需要，由 `make install` 自动安装；`make install`
  还会安装固定的 Keychain 3（ssh-agent 兜底，仅当私钥权限被 OpenSSH 拒绝时使用，
  如 WSL 下）。

## 快速开始

```bash
# 1. 工具链 + collections
make install

# 2. 从模板脚手架主机（vault.yml 自动加密，主机名自动写入 inventory/hosts.yml，
#    生成的文件无注释；HOST 缺省为 remnanode-1）
make host-init HOST=remnawave-node-1
#    - 编辑 inventory/host_vars/remnawave-node-1/main.yml   （可选，非密钥）
#    - 编辑加密 vault：
make vault-edit HOST=remnawave-node-1
#      （IP、SSH 凭据、netbird URL + setup key、NODE_PORT + SECRET_KEY）

# 3. 试运行、部署
make dry-run
make deploy
```

`make deploy` 是一键入口：先初始化主机，再部署节点栈（`playbooks/site.yml`）。全新
主机上 `ansible` 服务账户尚不存在，因此 `deploy` 会先执行与 `make host-bootstrap`
相同的初始化。

`make lint`（语法检查 + `ansible-lint`）是 CI 运行的内部检查，不出现在 `make help`。

## 入口

| 目标 | Playbook | 作用 |
|---|---|---|
| `make host-bootstrap` | `bootstrap.yml` | 探测 SSH 身份、创建 `ansible` 账户、安装 Docker。`HOST=<name>` 只处理一台。 |
| `make agent` | `agent.yml` | 仅把节点加入 NetBird overlay。 |
| `make monitoring` | `monitoring.yml` | node_exporter + CrowdSec + firewall bouncer（含 overlay agent）。 |
| `make deploy` | `bootstrap.yml` + `site.yml` | 完整节点栈：monitoring/agent + Remnawave Node。 |
| `make dry-run` | `site.yml --check --diff` | 安全预览。 |
| `make print [HOST=]` | — | 打印解析后的主机变量（含解密 vault）。 |

`make deploy TAGS=remnanode`（或 `TAGS=monitoring`）只运行对应角色。

## 密钥

切勿提交 vault。每台主机唯一的加密 vault
`inventory/host_vars/<host>/vault.yml` 保存 SSH 身份、NetBird 输入、Remnawave
`NODE_PORT` / `SECRET_KEY`，以及控制端生成的服务账户密码（未提供公钥时）。它被
gitignore，即使加密也从不提交；提交的 schema 参考为
`inventory/host_vars/example/vault.yml.example`。

## 布局

```
inventory/            # hosts.yml(.example)、group_vars/{all,remnawave_nodes}、host_vars/example
playbooks/bootstrap.yml   # 主机初始化：服务账户 + Docker（+ 镜像）
playbooks/agent.yml       # 加入 NetBird overlay（agent 角色）
playbooks/monitoring.yml  # 主机监控 + 安全
playbooks/site.yml        # 完整节点栈（monitoring/agent + remnanode）
roles/agent               # NetBird overlay agent（加入覆盖网络）
roles/monitoring          # node_exporter + CrowdSec + firewall bouncer（+ agent）
roles/remnanode           # Remnawave Node 容器
roles/helpers/            # 共享 vault 密钥生成 + Docker 安装
docs/RUNBOOK.md           # 运维手册（部署、验证、回滚）
```

## 许可

见 `LICENSE`。
