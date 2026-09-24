# 部署与启动

适用：第一次把 OpenMAIC 跑起来、换部署形态、放到服务器上对外提供服务。

## 1. 环境核对（先做这一步，能省掉一半报错）

| 检查项 | 命令 | 通过标准 |
|---|---|---|
| Node 版本 | `node -v` | `v22.19.0` 或更高；低版本会在 install 阶段直接失败 |
| pnpm 版本 | `pnpm -v` | `10.x` 起 |
| 端口占用 | `lsof -i :3000`（Windows：`netstat -ano \| findstr :3000`） | 3000 空闲，或被你自己可控的进程占用 |
| Docker（可选） | `docker compose version` | Compose v2，能正常输出 |

pnpm 没装时用 `corepack enable && corepack prepare pnpm@latest --activate`，不要用 `npm i -g` 混装。

## 2. 取代码与安装

```bash
git clone https://github.com/THU-MAIC/OpenMAIC.git
cd OpenMAIC
pnpm install
cp .env.example .env.local
```

`pnpm install` 在 monorepo 工作区里会同时装根包与 `packages/` 下的子包，首次通常 3～8 分钟。装完不要急着启动，先配 Key。

## 3. 最小配置

`.env.local` 里只需要两行就能跑：

```env
OPENAI_API_KEY=sk-...
DEFAULT_MODEL=openai:gpt-5.5
```

要点：

1. **`DEFAULT_MODEL` 必须带服务商前缀**（`服务商:模型名`）。裸模型名会被服务端在启动校验里拒绝，这是最常见的「启动就报错」原因。
2. 服务商前缀可换：`google:`、`anthropic:`、`deepseek:`、`qwen:`、`kimi:`、`minimax:`、`glm:`、`grok:`、`xiaomi:`、`bedrock:`、`openrouter:`、`siliconflow:`、`atlascloud:` 等，具体见 `references/03-customize-and-troubleshoot.md`。
3. 要语音讲解就补 TTS 的 Key，要联网检索就补搜索的 Key；这两项缺失不会阻止启动，只是 `/api/health` 里对应的能力位为 `false`。
4. 推荐起步模型是快档的 Flash 类，质量优先再换 Pro 类——课堂生成是长链路多轮调用，模型档位直接决定等待时间和花费。

## 4. 三种启动路线

### 路线 A：本地开发（改代码用）

```bash
pnpm dev
```

- 默认监听 `http://localhost:3000`
- 带热更新，改了组件立刻生效
- 改 `NEXT_PUBLIC_*` 变量**不会**热更新，必须重启并重新构建

### 路线 B：生产构建（自建服务器推荐）

```bash
pnpm build && pnpm start
```

先 build 再 start，不能只 start。构建产物与 `NEXT_PUBLIC_*` 的取值绑定，改这些变量后必须重新 build。

### 路线 C：容器（最省事，一致性好）

```bash
docker compose up --build
```

- 应用容器把 3000 端口映射到宿主机 3000，访问方式与本地一致
- 配置走 `env_file: .env.local`，所以你还是要先写 `.env.local`
- 数据卷 `openmaic-data` 挂到容器内 `/app/data`
- 想用外部 provider 配置文件，把 compose 里那行 `./server-providers.yml:/app/server-providers.yml:ro` 的注释去掉

国内网络下构建慢，可以用两个构建参数换源（**只填公共镜像地址，绝不要把账号密码或令牌塞进去，构建参数会被写进镜像元数据**）：

```bash
ALPINE_MIRROR=mirrors.aliyun.com \
NPM_REGISTRY=https://registry.npmmirror.com \
docker compose up --build
```

直接 build 镜像时同理：

```bash
docker build \
  --build-arg ALPINE_MIRROR=mirrors.aliyun.com \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  -t openmaic:local .
```

这两个参数**不加速**基础镜像和 Dockerfile frontend 的拉取；那部分要靠给 Docker daemon 配 registry mirror。

## 5. 健康检查与能力位

```bash
curl -s http://localhost:3000/api/health
```

返回结构固定：`status`、`version`、`capabilities`。`capabilities` 里四项按服务商是否配置并**未被显式关闭**来判断：

| 字段 | 为 true 的条件 |
|---|---|
| `webSearch` | 至少配了一家检索服务商 |
| `imageGeneration` | 至少配了一家出图服务商 |
| `videoGeneration` | 至少配了一家出视频服务商 |
| `tts` | 至少配了一家语音合成服务商 |

被显式设为 `disabled: true` 的服务商不计入。只要有一项你「明明配了却是 false」，先去查这一项。

## 6. 站点访问密码

对外提供服务前，在 `.env.local` 加一行：

```env
ACCESS_CODE=your-secret-code
```

设置后访客要先输密码，所有 API 路由一并受保护；不设置就是完全开放。不要把 `ACCESS_CODE` 当成账号体系，它只是单口令门禁。

## 7. 可选档位

### 服务端持久化（PostgreSQL 16）

`--profile server-persistence` 只起两个容器：应用本体 + PostgreSQL。持久化 HTTP 服务内嵌在应用里（`/api/persistence`），没有独立服务。

```bash
cp .env.example .env.local
printf '\nDATABASE_URL=postgres://openmaic:openmaic-dev@postgres:5432/openmaic\nPERSISTENCE_DEV_TOKEN=openmaic-local-dev\n' >> .env.local
NEXT_PUBLIC_PERSISTENCE=1 NEXT_PUBLIC_PERSISTENCE_TOKEN=openmaic-local-dev \
  docker compose --profile server-persistence up --build
```

三个必须记住的点：

1. `NEXT_PUBLIC_PERSISTENCE` 是**编译期**开关，会打进浏览器 bundle；构建时必须与服务端 token 一致，否则前端会走 HTTP 持久化而端点报配置/认证错误。
2. `PERSISTENCE_DEV_TOKEN` / `NEXT_PUBLIC_PERSISTENCE_TOKEN` **不是真正的密钥**：带 `NEXT_PUBLIC_` 的那个任何人能从 JS 里抠出来，进而读写所有学习者的分区。**只在本机或可信内网的单用户部署用。**生产要换成真正的会话校验。
3. `PERSISTENCE_POSTGRES_PASSWORD` 只在数据目录为空时初始化角色，之后改它不会轮换已有卷。要换密码得进库执行 `ALTER ROLE openmaic WITH PASSWORD '...'` 并同步改 `DATABASE_URL`。

资产回收默认开启：每 15 分钟（`ASSET_COLLECTION_INTERVAL_MS`）一轮，清理解除引用超过 1 小时（`ASSET_COLLECTION_GRACE_MS`）的字节。那 1 小时就是用户删除后字节的实际保留窗口，别随手调大。`ASSET_COLLECTION_ENABLED=0` 可关掉。

设备维度的数据（匿名设备学习者 key、播放进度）仍留在浏览器；已有的浏览器课程会在首次访问时逐门懒式迁移到服务端。

### MP4 视频导出

导出视频在浏览器里先构建一个自包含的合成工程，真正转 MP4 需要 Chromium + FFmpeg，所以跑在独立的 `render-service` 容器里：

```bash
docker compose --profile video-export up --build
```

- 该容器挂在 `internal: true` 的 `render` 网络上，无外网出口，自身还用 iptables 封了出站；因此它需要 `CAP_NET_ADMIN`，没有该权限时仍能启动但会告警且不封锁出站。
- 标准资源档要 **8 GiB** 内存上限；小机器用 `RENDER_RESOURCE_PROFILE=low-memory` 配 `RENDER_SERVICE_MEMORY_LIMIT=4g`。
- `shm_size: 2gb` 是 Chromium 帧渲染的下限，不要调回 Docker 默认的 64 MiB。
- 单实例并发被刻意压到 1（`RENDER_MAX_CONCURRENCY=1`）。想让服务端识别到可用渲染，`RENDER_SERVICE_URL` 指向 `http://render-service:9000`；容器不在时应用会报「MP4 导出不可用」并降级为下载 ZIP，这是预期行为，不是 bug。

### 本地模型与本地语音（无 Key 方案）

Ollama / Lemonade 走 OpenAI 兼容接口，本地起好之后在 `.env.local` 指向本机即可，例如：

```env
LEMONADE_BASE_URL=http://localhost:13305/v1
TTS_LEMONADE_BASE_URL=http://localhost:13305/v1
ASR_LEMONADE_BASE_URL=http://localhost:13305/v1
IMAGE_LEMONADE_BASE_URL=http://localhost:13305/v1
```

本地语音识别走 FunASR 的 OpenAI 兼容服务：`ASR_FUNASR_BASE_URL=http://localhost:8000/v1`。纯 CPU 环境选小模型档，有 GPU 再上大档。

### 云平台一键部署

仓库带 Vercel 的 Deploy 按钮，流程是：fork → 导入 → 配环境变量（至少一个 LLM Key）→ 部署。注意容器专属的档位（渲染服务、Postgres profile）在 Serverless 平台上不适用。

## 8. 对外发布前的收尾

1. `ACCESS_CODE` 已设置。
2. 反向代理只暴露 3000，`.env.local` 不出现在任何静态目录里。
3. 持久化档位没有直接暴露给公网；如果暴露了，按第 7 节第 2 条当作「临时方案」处理，尽快替换掉开发令牌校验。
4. `GET /api/health` 在代理后仍返回 `status: ok`。
5. 容器加了 `restart: unless-stopped`（compose 已默认带上）。
