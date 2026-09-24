# OpenHands Agent Canvas 自托管：拓扑、加固与常驻

内容取自仓库 README、`docs/SELF_HOSTING.md` 与 `README.windows.md`。命令与端口以官方文档当前内容为准。

---

## 一、组件与端口拓扑

`npx @openhands/agent-canvas --public` 一条命令会同时起四件事，并由一个 ingress 代理按路径分发：

```
用户 ── HTTPS/443 ──> nginx ──> Ingress 代理 127.0.0.1:8000
                                   ├── /*                → 静态前端 :3001
                                   ├── /api/*, /sockets  → Agent Server :18000
                                   └── /api/automation/* → Automation 后端 :18001
```

| 组件 | 端口 | 面向谁 |
|---|---|---|
| Ingress 代理 | 127.0.0.1:8000 | 唯一需要对外（经反代）暴露的入口 |
| 静态前端 | 3001 | 内部 |
| Agent Server | 18000 | 内部；用 `LOCAL_BACKEND_API_KEY` 鉴权 |
| Automation 后端 | 18001 | 内部 |

部署心法：**只让 8000 出现在反代后面，另外三个端口一律不要对外。**

---

## 二、加固顺序（官方立场：先锁网络，再启服务）

官方明确要求：**在第一次启动 agent server 之前**就把网络锁好。默认姿态是「除了自己 IP 的 SSH，什么都不通」。

1. **网络层**：入站 22 限制到自己的 IP / VPN 段；其余全丢。ingress（8000）、agent server（18000）、automation（18001）、静态服务（3001）都不能从外部直接访问。
2. **API Key**：`export LOCAL_BACKEND_API_KEY=$(openssl rand -base64 32)`。用 `export` 而不是写进命令行参数，避免出现在 `ps aux` 里。生成后另存一份。
3. **public 模式**：`npx @openhands/agent-canvas --public`。这个模式下 Key 不会被打进前端，用户打开界面要先粘贴 Key；每个 `/api/*` 请求都必须带匹配的 `X-Session-API-Key` 头。
4. **TLS（可选但推荐）**：域名 + nginx + certbot，只把 80（Let's Encrypt 挑战）与 443 打开；443 尽量也限制来源。
5. **常驻**：tmux（快）或 systemd（长期）。

> 官方提醒：`--public` 之外的模式会把 Key 自动注入前端，方便但**不适合公网可达的部署**。
>
> 官方也提醒：agent server 直接在宿主上运行，拥有该机器的文件系统、环境变量与网络权限。防火墙与 API Key 是唯一挡住陌生人的东西。

---

## 三、常驻配置

**tmux（临时）**

```bash
export LOCAL_BACKEND_API_KEY=<你保存的 Key>
tmux new-session -d -s canvas 'npx @openhands/agent-canvas --public'
# 之后重连
tmux attach -t canvas
```

**systemd（推荐）**：`/etc/systemd/system/agent-canvas.service`

```ini
[Unit]
Description=Agent Canvas
After=network.target

[Service]
Environment=LOCAL_BACKEND_API_KEY=<你的 Key>
ExecStart=npx @openhands/agent-canvas --public
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now agent-canvas
```

---

## 四、nginx 反代要点

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name canvas.example.com;

    location /.well-known/acme-challenge/ { root /var/www/html; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 必须：实时事件走 WebSocket / SSE
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/canvas.example.com /etc/nginx/sites-enabled/canvas.example.com
nginx -t && systemctl reload nginx
certbot --nginx -d canvas.example.com --non-interactive --agree-tos --email you@example.com --redirect

curl -I https://canvas.example.com/   # 200，显示 Key 输入页
curl -I http://canvas.example.com/    # 301 到 https
```

**502 Bad Gateway** 的官方解释很直接：`127.0.0.1:8000` 上的应用挂了，去看 `npx` 进程或 systemd 单元。

---

## 五、把远端注册成本地的一个后端

在本地 Canvas 里 **Manage backends → Add a backend**：

| 字段 | 填什么 |
|---|---|
| Host Name | 便于识别的名字，例如 `my-vm` |
| Host | 远端地址，例如 `https://canvas.example.com`；走 SSH 隧道则填 `http://localhost:8000` |
| Session API key | 远端设置的 `LOCAL_BACKEND_API_KEY` |

保存后状态应显示已连接，用后端切换器在本地与远端之间切。

---

## 六、一个必须知道的信任边界问题

官方自托管文档记录了（issue #16492）：**内置编辑器与 Canvas 共享同一个浏览器 origin**。编辑器通过路径前缀（默认 `/vscode`）挂在同一个代理端口上，路径前缀只负责路由，不负责隔离。因此**该 origin 上任何能执行脚本的内容**（包括通过扩展或受损资源进入的编辑器内容）都能读到 Canvas 的 `localStorage`，而里面存着**这个浏览器里注册的每一个后端**的 session key。

实践含义：
- 不要把不受信任的后端加进同一个浏览器；
- 不要把不受信任的编辑器扩展装进这个环境；
- 多后端共用浏览器时，把它们视为同一信任域。

---

## 七、Windows 上的 Docker 方式（对照）

```powershell
docker pull ghcr.io/openhands/agent-canvas:1.18.0

$env:PROJECTS_PATH = Join-Path $HOME "projects"
New-Item -ItemType Directory -Force -Path $env:PROJECTS_PATH, (Join-Path $env:USERPROFILE ".openhands") | Out-Null

docker run -it --rm `
  -p 8000:8000 `
  -v "$($env:USERPROFILE)\.openhands:/home/openhands/.openhands" `
  -v "$($env:PROJECTS_PATH):/projects" `
  ghcr.io/openhands/agent-canvas:1.18.0
```

然后打开 http://localhost:8000/canvas 。官方 Windows 说明单独放在 `README.windows.md`。

---

## 八、仓库分工（改东西之前先找对仓库）

| 仓库 | 负责什么 |
|---|---|
| `OpenHands/OpenHands` | Agent Canvas 前端、控制中心、后端选择、本地栈编排 |
| `OpenHands/software-agent-sdk` | Python SDK、Agent Server、Agent、工具、会话、工作区、事件与服务端 API |
| `OpenHands/typescript-client` | 浏览器可用的 TypeScript 客户端（给 Agent Server API 用） |
| `OpenHands/automation` | 自动化定义、调度、Webhook、运行历史与派发 |

---

## 九、本文件不覆盖

- Agent Server 的 REST API 细节（在 software-agent-sdk）。
- Automation 的定义语法（在 automation 仓库）。
- LLM 配置与 profile 的完整字段（在官方文档站的设置章节）。
- 具体镜像版本与发布日期（以仓库 releases 为准）。
