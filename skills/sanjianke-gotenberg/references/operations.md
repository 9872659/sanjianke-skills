# 部署与调参

## 一、镜像变体怎么选

| 变体 | 体积 | 含什么 | 什么时候选 |
|---|---|---|---|
| `gotenberg/gotenberg:8` | 完整 | Chromium + LibreOffice + PDF 引擎 | 默认选它。要转 Office，或不确定要什么 |
| `gotenberg/gotenberg:8-chromium` | 约小 30% | Chromium + PDF 引擎 | 只转网页 / HTML / Markdown，且要做截图 |
| `gotenberg/gotenberg:8-libreoffice` | 约小 40% | LibreOffice + PDF 引擎 | 只转 Office 文档，不需要 URL / HTML / 截图 |

三种变体**都含 PDF 引擎**（合并、拆分、加密、水印、元数据、书签、附件等）。

功能可用性对照：

| 功能 | 完整 | Chromium | LibreOffice |
|---|:--:|:--:|:--:|
| URL / HTML / Markdown 转 PDF | ✓ | ✓ | ✗ |
| 截图 | ✓ | ✓ | ✗ |
| Office 文档转换 | ✓ | ✗ | ✓ |
| 合并 / 拆分 / 旋转 / 扁平化 | ✓ | ✓ | ✓ |
| 加密 / 水印 / 图章 | ✓ | ✓ | ✓ |
| 读 / 写元数据与书签 | ✓ | ✓ | ✓ |
| 内嵌附件 | ✓ | ✓ | ✓ |
| Factur-X 电子发票 | ✓ | ✗ | ✓ |
| PDF/A 与 PDF/UA | ✓ | ✗ | ✓ |
| Webhook 异步 | ✓ | ✓ | ✓ |
| `downloadFrom` 远端输入 | ✓ | ✓ | ✓ |

**请求一个变体不支持的功能会直接报错**，不是静默降级。别指望在 `:8-chromium` 上转 docx。

## 二、云平台变体

| 平台 | 镜像 |
|---|---|
| Cloud Run | `gotenberg/gotenberg:8-cloudrun`、`…:8-chromium-cloudrun`、`…:8-libreoffice-cloudrun` |
| AWS Lambda（Beta） | `gotenberg/gotenberg:8-aws-lambda`、`…:8-chromium-aws-lambda`、`…:8-libreoffice-aws-lambda` |

Cloud Run 变体已经做了：读 Cloud Run 给的 `PORT`、输出 Cloud Run 兼容日志格式、自动预热 Chromium 与 LibreOffice、**用同步 webhook 模式**（因为 Cloud Run 没有 HTTP 活动就会停容器）。官方建议至少 **1Gi 内存**。

Lambda 变体：用 `AWS_LWA_PORT` 配端口，`AWS_LWA_READINESS_CHECK_PATH=/health`，`AWS_LWA_INVOKE_MODE=buffered`，同样走同步 webhook 模式。`buffered` 模式**响应上限 6MB**，更大的输出必须用 webhook 上传到 S3。

## 三、配置方式

两个等价入口：

```bash
# 覆盖 command
docker run --rm -p "3000:3000" gotenberg/gotenberg:8 gotenberg --api-timeout=120s

# 环境变量
docker run --rm -p "3000:3000" -e API_TIMEOUT=120s gotenberg/gotenberg:8
```

Compose：

```yaml
services:
  gotenberg:
    image: gotenberg/gotenberg:8
    command:
      - "gotenberg"
      - "--api-timeout=120s"
    # 或
    environment:
      API_TIMEOUT: "120s"
```

**覆盖 command，不要覆盖 entrypoint。**

### 最常动的 API 配置

| 参数 / 环境变量 | 说明 | 默认 |
|---|---|---|
| `--api-port` / `API_PORT` | 监听端口 | `3000` |
| `--api-bind-ip` / `API_BIND_IP` | 绑定的 IP | `0.0.0.0` |
| `--api-timeout` / `API_TIMEOUT` | **请求总超时** | `30s` |
| `--api-start-timeout` | API 启动时限 | `30s` |
| `--api-body-limit` / `API_BODY_LIMIT` | multipart body 上限，如 `5MB`、`1GB` | 无 |
| `--api-root-path` | API 根路径，用于 URL 路径式服务发现 | `/` |
| `--api-correlation-id-header` | 请求追踪头名 | `Gotenberg-Trace` |
| `--api-enable-basic-auth` | 开 Basic Auth，读 `GOTENBERG_API_BASIC_AUTH_USERNAME` / `_PASSWORD` | `false` |
| `--api-enable-oidc-auth` | 开 OIDC bearer 鉴权（与 Basic Auth **互斥**） | `false` |
| `--api-oidc-issuer` / `..-audience` / `..-jwks-url` | OIDC 参数；jwks 留空时从 issuer 的 well-known 配置发现 | 无 |
| `--api-enable-debug-route` | 打开 `/debug` | `false` |
| `--api-tls-cert-file` / `--api-tls-key-file` | 直接上 HTTPS | 无 |
| `--gotenberg-graceful-shutdown-duration` | 优雅关停等待时长 | `30s` |

已弃用但你可能在老配置里见到：`--api-trace-header`（→ `--api-correlation-id-header`）、`--api-disable-health-check-logging`（→ `--api-disable-health-check-route-telemetry`），均自 8.29.0 起。

### Chromium 模块

| 参数 | 说明 | 默认 |
|---|---|---|
| `--chromium-max-concurrency` | 并发转换数，**Chromium 最多支持 6** | `6` |
| `--chromium-restart-after` | 转换多少次后自动重启浏览器，`0` 关闭 | `100` |
| `--chromium-max-queue-size` | 排队上限，`0` 表示不限 | `0` |
| `--chromium-auto-start` | 启动时就拉起浏览器 | `false` |
| `--chromium-start-timeout` | 启动 / 重启浏览器时限 | `20s` |
| `--chromium-idle-shutdown-timeout` | 空闲多久后关掉浏览器，`0` 关闭 | `0s` |
| `--chromium-disable-javascript` | 禁用 JS | `false` |
| `--chromium-clear-cache` / `-cookies` / `-storage` | 每次转换之间清理缓存 / Cookie / 本地存储 | `false` |
| `--chromium-deny-list` | 用正则拒绝导航与子资源 | `^file:(?!//\/tmp/).*` |
| `--chromium-allow-list` | 用正则放行（**匹配会绕过 IP 段检查**） | 全部 |
| `--chromium-deny-private-ips` | 拒绝解析到非公网 IP 的地址 | `false` |
| `--chromium-proxy-server` / `--chromium-host-resolver-rules` | 出站代理 / 自定义解析；**一旦设置就跳过 DNS-rebind 防护代理** | 无 |
| `--chromium-enable-environment-proxy` | 走 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` | `false` |
| `--chromium-ignore-certificate-errors` | 忽略证书错误 | `false` |

自 8.32.0 起，Chromium 的每个 HTTP/HTTPS 请求都走一个进程内 pinning 代理：DNS 只解析一次，然后拨号到校验过的 IP。

### LibreOffice 模块

| 参数 | 说明 | 默认 |
|---|---|---|
| `--libreoffice-restart-after` | 转换多少次后重启 | `10` |
| `--libreoffice-max-queue-size` | 排队上限 | `0` |
| `--libreoffice-auto-start` | 启动时预热 | `false` |
| `--libreoffice-start-timeout` | 启动时限 | `20s` |
| `--libreoffice-idle-shutdown-timeout` | 空闲关停 | `0s` |
| `--libreoffice-deny-list` / `--libreoffice-allow-list` | 出站抓取（内嵌图片、链接内容）的拒绝 / 放行正则 | 无 / 全部 |

自 8.34.0 起，**上传的文档永不被视为可信**：文档里链接的 `file://` 路径与外部 URL 会在任何抓取发生前就被拦掉。

换 LibreOffice 界面语言需要**自建镜像**（默认英语）。官方给了 Dockerfile 样例：基于 `gotenberg/gotenberg:8`，用 root 装 `libreoffice-l10n-<lang>`，改 `/etc/locale.gen` 后 `locale-gen`，再设置 `LANG` / `LANGUAGE` / `LC_ALL`，最后切回 `USER gotenberg`。

### PDF 引擎模块

| 参数 | 默认 |
|---|---|
| `--pdfengines-merge-engines` | `qpdf,pdfcpu,pdftk` |
| `--pdfengines-split-engines` | `pdfcpu,qpdf,pdftk` |
| `--pdfengines-flatten-engines` | `qpdf` |
| `--pdfengines-convert-engines` | `libreoffice-pdfengine` |
| `--pdfengines-optimize-images-engines` | `pdfcpu` |
| `--pdfengines-read-metadata-engines` / `-write-…` | `exiftool` |
| `--pdfengines-encrypt-engines` | `qpdf,pdftk,pdfcpu` |
| `--pdfengines-embed-engines` | `pdfcpu` |
| `--pdfengines-watermark-engines` / `-stamp-…` | `pdfcpu,pdftk` |
| `--pdfengines-rotate-engines` | `pdfcpu,pdftk` |
| `--pdfengines-factur-x-engines` | `qpdf` |
| `--pdfengines-read-bookmarks-engines` / `-write-…` | `pdfcpu` |
| `--pdfengines-max-concurrency` | `1`（**跨所有请求**，对 LibreOffice 不生效） |

`--pdfengines-engines` 自 8.13.0 起弃用。

### 日志

| 参数 | 说明 | 默认 |
|---|---|---|
| `--log-std-format` | `auto` / `json` / `text` | `auto` |
| `--log-level` | `error` / `warn` / `info` / `debug` | `info` |
| `--log-fields-prefix` | 给每个字段加前缀 | 无 |
| `--log-std-enable-gcp-fields` | 输出 GCP 的 time / message / severity 字段 | `false` |
| `--log-std-level-case` | `lower` 或 `upper`；**其他值会导致启动失败** | `lower` |

弃用映射：`--log-format` → `--log-std-format`（8.29.0）、`--log-enable-gcp-severity` → `--log-enable-gcp-fields`（8.19.0）、`--log-enable-gcp-fields` → `--log-std-enable-gcp-fields`（8.29.0）、`--prometheus-disable-route-logging` → `--prometheus-disable-route-telemetry`（8.29.0）。

## 四、Webhook 异步模式

同步模式下请求要一直挂着等转换完，大文档很容易撞上 `--api-timeout`。异步模式把结果 POST 到你指定的回调地址，请求立刻返回。

| 参数 | 说明 | 默认 |
|---|---|---|
| `--webhook-enable-sync-mode` | 开同步模式（Cloud Run / Lambda 变体默认开启） | `false` |
| `--webhook-allow-list` / `--webhook-deny-list` | 回调 URL（成功、错误、事件）的正则规则 | 全部 / 无 |
| `--webhook-deny-private-ips` / `--webhook-deny-public-ips` | 按回调目标 IP 段拒绝 | `false` |
| `--webhook-enable-environment-proxy` | 回调走环境变量里的代理 | `false` |
| `--webhook-max-retry` | 重试次数 | `4` |
| `--webhook-retry-min-wait` / `--webhook-retry-max-wait` | 退避等待区间 | `1s` / `30s` |
| `--webhook-client-timeout` | 回调请求超时 | `30s` |
| `--webhook-disable` | 关掉 webhook 功能 | `false` |

自 8.31.0 起成功与错误回调**共用同一套 allow / deny 规则**，`--webhook-error-allow-list` 与 `--webhook-error-deny-list` 已弃用。

用 webhook 时还有个容易漏的点：**优雅关停时长要 ≥ API 超时**（8.21.0 之前尤其明显），否则容器可能在异步任务跑完前就开始关停。

## 五、远端输入（downloadFrom）

不想自己把文件传到 Gotenberg，可以让服务去远端拉。相关配置：

| 参数 | 说明 | 默认 |
|---|---|---|
| `--api-download-from-allow-list` | 允许拉取的 URL 正则；**匹配会绕过 IP 段检查** | 全部 |
| `--api-download-from-deny-list` | 拒绝的 URL 正则；**命中一律拒绝**，优先级高于 allow-list | 无 |
| `--api-download-from-deny-private-ips` | 拒绝解析到非公网 IP 的 `downloadFrom` URL | `false` |
| `--api-download-from-deny-public-ips` | 拒绝解析到公网 IP 的 URL | `false` |
| `--api-download-from-max-retry` | 重试次数 | `4` |
| `--api-download-from-max-concurrency` | 每次请求并发拉取数，`0` 不限 | `10` |
| `--api-download-from-max-entries` | 每次请求最多几个条目，超了 400，`0` 不限 | `0` |
| `--api-disable-download-from` | 直接关掉这个功能 | `false` |

自 8.32.0 起，出站过滤**默认放行**，需要按模块自己配白名单。官方专门有一篇《Writing a Safe Allow-List》讲怎么写才安全：正则是**后缀匹配**的，`example.com` 会连带匹配 `evilexample.com`，所以要写成锚定到主机名边界的形式。

## 六、Kubernetes

镜像以非 root 用户 `gotenberg`（UID/GID **1001**）运行。从 8.21.0 起也支持任意 UID（OpenShift）。

```yaml
securityContext:
  readOnlyRootFilesystem: false
  allowPrivilegeEscalation: false
  privileged: false
  runAsUser: 1001
```

官方建议**至少 512Mi 内存 + 0.2 CPU**。社区维护的 Helm chart 在 `MaikuMori/helm-charts`。

## 七、字体

自 8.30.0 起字体栈从 30+ 包精简到 8 个：

| 包 | 覆盖 |
|---|---|
| `fonts-noto-core` | 阿拉伯、孟加拉、天城文、埃塞俄比亚、格鲁吉亚、古吉拉特、古木基、希伯来、卡纳达、高棉、老挝、马拉雅拉姆、缅甸、僧伽罗、泰米尔、泰卢固、泰文等 |
| `fonts-noto-cjk` | 中日韩 |
| `fonts-noto-color-emoji` | 彩色 emoji |
| `fonts-dejavu` | 拉丁、希腊、西里尔 |
| `fonts-crosextra-carlito` | 与 Calibri 度量兼容 |
| `fonts-crosextra-caladea` | 与 Cambria 度量兼容 |
| `fonts-liberation` / `fonts-liberation2` | 与 Arial、Times New Roman、Courier New 度量兼容 |

**微软核心字体（`ttf-mscorefonts-installer`）因授权原因不随镜像分发**，只给了度量兼容替代品，大多数情况下版面能保住。

自建镜像的三种场景（官方样例）：装微软核心字体（需接受 EULA）、装特定文种字体包（如 `fonts-hosny-amiri`、`fonts-thai-tlwg`）、塞自己的 `.ttf` 文件。

## 八、部署后的验收顺序

```bash
# 1. 进程级探活
curl --fail --silent --show-error --max-time 5 http://localhost:3000/health

# 2. 版本确认
curl --fail --silent http://localhost:3000/version

# 3. 端到端冒烟：这一步成功才算真的可用
curl --fail-with-body --silent --show-error --max-time 75 \
  --request POST http://localhost:3000/forms/chromium/convert/url \
  --form url=https://sparksuite.github.io/simple-html-invoice-template/ \
  -o smoke.pdf

# 4. 如果要用 Office 转换，必须单独再冒烟一次（切换变体最容易漏）
curl --fail-with-body --silent --show-error --max-time 75 \
  --request POST http://localhost:3000/forms/libreoffice/convert \
  --form files=@sample.docx \
  -o smoke-office.pdf
```

`/health` 只说明 API 进程活着，**不检查 Chromium、LibreOffice 是否可用**，所以必须用真实转换来验收。

## 九、无成本的试跑路径

不想先装 Docker，可以用官方 demo：

```bash
curl --request POST https://demo.gotenberg.dev/forms/chromium/convert/url \
  --form url=https://sparksuite.github.io/simple-html-invoice-template/ \
  -o my.pdf
```

demo 跑在 512MB RAM / 0.5 CPU 的实例上，限流为**每 IP 每秒 2 个请求、body 上限 5MB**。只适合验证请求格式，不适合压测或真实批量。

**不要拿 demo 传任何敏感文件。**
