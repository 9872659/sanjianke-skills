---
name: sanjianke-stirling-pdf
slug: sanjianke-stirling-pdf
displayName: 三剪客 · 本地 PDF 工具箱
description: "自建一套属于自己的 PDF 处理服务：合并拆分、加水印、签名脱敏、格式互转、OCR、压缩，还能把操作串成流水线批量跑，通过 REST API 或内置 MCP 交给脚本和 AI 助手调用。含 Docker 部署、API 调用与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "把 50 多个 PDF 工具装进自己机器：一条 docker run 起服务，浏览器点着用，脚本走 REST API，重复流程用流水线一次跑完。文档不出本地。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
  - PDF
---

# 三剪客 · 本地 PDF 工具箱

要合并几十份 PDF、给合同加水印、把扫描件变可搜索、把 Word 转 PDF——常规做法是找在线网站，代价是把文件传到别人服务器上。Stirling-PDF 换了个路子：**整套工具装进你自己的机器**，浏览器里点着用，脚本里走 REST API，文档一步都不出本地网络。

它提供 50 多个 PDF 工具（编辑、合并、拆分、签名、脱敏、转换、OCR、压缩等），并且支持把多步操作串成流水线一次跑完。对个人是省事的桌面/网页工具，对团队是可集成的私有文档处理服务。

**上游项目**：`Stirling-PDF`　**仓库**：https://github.com/Stirling-Tools/Stirling-PDF

## 什么时候用 / 不用

**用它**：

- 文档涉及合同、证件、财务报表这类**不方便上传到第三方网站**的材料，需要在本地或内网完成处理。
- 有一批重复的 PDF 操作要自动化：批量加水印、批量转格式、批量 OCR、批量压缩，希望用脚本或 API 跑而不是手点。
- 团队需要一套统一的 PDF 服务给多个系统调用，不想为每个功能找不同工具。
- 想让 AI 助手直接操作 PDF（启用内置 MCP 服务后，助手可以发现并调用这些 PDF 操作）。
- 需要一个能串流程的自动化入口：把「OCR → 压缩 → 加水印 → 签名」这类链路配一次，之后反复用。

**不要用它**：

- **只想处理一两份文件的临时需求**。起 Docker、配端口、等启动，成本比找一个现成工具高；这种场景直接上轻量命令行工具更划算。
- **要求极高保真的专业排版出版**。它不是排版软件，复杂版式的转换质量取决于底层组件（LibreOffice 等）。
- **需要表格结构识别、公式识别、手写体高精度识别**。它的 OCR 基于 Tesseract，官方明确说明只做文字识别，不做表格结构与公式识别，手写体精度有限。
- **打算把服务直接暴露到公网而不做加固**。这是个功能齐全的自建服务，默认就带登录体系；暴露前必须改掉默认口令并配置好安全设置。
- **没有服务器资源的环境**。完整镜像内存占用不低，资源极度受限时只能选精简版并接受功能裁剪。

## 安装

### Docker（首选方式）

```bash
# 最小可用
docker run -d \
  --name stirling-pdf \
  -p 8080:8080 \
  -v ./stirling-data:/configs \
  docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest
```

打开 `http://localhost:8080`。

```yaml
# docker-compose.yml —— 带 OCR、配置持久化和日志的完整配置
services:
  stirling-pdf:
    image: docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest
    container_name: stirling-pdf
    ports:
      - '8080:8080'
    volumes:
      - ./stirling-data/tessdata:/usr/share/tessdata  # OCR 语言包
      - ./stirling-data/configs:/configs              # 设置与数据库
      - ./stirling-data/logs:/logs                    # 应用日志
      - ./stirling-data/pipeline:/pipeline            # 自动化配置
    environment:
      - SECURITY_ENABLELOGIN=false      # 显式关掉登录（默认是开启）
      - SYSTEM_DEFAULTLOCALE=en-GB      # 默认界面语言
    restart: unless-stopped
```

```bash
docker-compose up -d
```

**镜像版本怎么选**：

| 版本 | 标签 | 内容 | 适合谁 |
|---|---|---|---|
| Standard | `latest` | 全部 PDF 功能 | 大多数人，功能与体积均衡 |
| Fat | `latest-fat` | 全部功能 + 额外字体与工具 | 追求最高转换质量、格式支持最全 |
| Ultra-Lite | `latest-ultra-lite` | 仅核心功能 | 资源受限（树莓派、低配 VPS）、只做基础操作 |

换版本就是换标签：`docker ... stirling-pdf:latest-ultra-lite`。

**升级**：

```bash
docker stop stirling-pdf
docker rm stirling-pdf
docker pull docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest
# 然后重新执行原来的 docker run
```

Compose 方式：`docker-compose down && docker-compose pull && docker-compose up -d`。数据都在挂载卷里，升级不丢。

**默认账号**：登录默认开启（`security.enableLogin: true`），首次启动会创建默认管理员 `admin` / `stirling`，**登录后立刻改密码**。想要无登录体验必须显式设置 `SECURITY_ENABLELOGIN=false`。

### 其他平台

- **桌面客户端**：官方提供桌面版（本地/自建模式）。具体安装包与步骤以 [官方安装文档](https://docs.stirlingpdf.com) 为准。
- **Kubernetes**：官方安装文档中有独立章节。以官方文档为准。
- **NAS / 虚拟化**：TrueNAS、Unraid、Proxmox LXC、Synology、UGREEN、Asustor、CasaOS / Portainer、Podman (Quadlet) 等平台都有社区维护的安装方式，官方安装文档里逐个列了步骤。这些集成由社区维护，问题要报到对应项目。
- **源码开发**：需要 JDK 25、Node.js 22+、Docker、Task（任务运行器）；`task dev` 会同时起后端与前端。

## 常用操作

**1. 加水印（官方文档给出的 CLI 示例）**

```bash
curl -X POST "http://localhost:8080/api/v1/security/add-watermark" \
     -H "Content-Type: multipart/form-data" \
     -F "fileInput=@/path/to/sample.pdf" \
     -F "watermarkType=text" \
     -F "watermarkText=YOUR_WATERMARK_TEXT" \
     -F "alphabet=roman" \
     -F "fontSize=30" \
     -F "rotation=0" \
     -F "opacity=0.5" \
     -F "widthSpacer=50" \
     -F "heightSpacer=50" \
     -o output.pdf
```

Windows CMD 下把行尾的 `\` 换成 `^`。

**2. 对扫描件做 OCR，让 PDF 变成可搜索**

```bash
curl -X POST http://stirling-pdf:8080/api/v1/misc/ocr-pdf \
  -F "fileInput=@scanned.pdf" \
  -F "languages=eng" \
  -F "languages=spa" \
  -F "ocrType=skip-text" \
  -F "ocrRenderType=hocr" \
  -F "deskew=true" \
  -F "clean=true" \
  -F "cleanFinal=true" \
  -F "sidecar=false" \
  -o searchable.pdf
```

`ocrType` 取值：`skip-text`（只处理本来没有文字层的页，对应界面里的 Auto 模式）、强制全部重做、或遇到已有文字就中止。多个语言就写多个 `languages` 字段。

**3. 开安全认证后带 API Key 调用**

```bash
# 用环境变量设一个全局 Key（适合无头脚本）
# SECURITY_CUSTOMGLOBALAPIKEY=your-custom-api-key

curl -X POST "http://localhost:8080/api/v1/security/add-watermark" \
     -H "X-API-KEY: your-api-key-here" \
     -H "Content-Type: multipart/form-data" \
     -F "fileInput=@sample.pdf" \
     -F "watermarkType=text" \
     -F "watermarkText=DRAFT" \
     -o output.pdf
```

也可以登录后在账户设置里取每个用户自己的 API Key。

**4. 一次请求跑完整条流水线**

```bash
# 端点：POST /api/v1/pipeline/handleData
# 请求：multipart，一个或多个 fileInput 分部 + 一个 json 分部（完整流水线配置）
# 响应：单个处理结果，或流水线产生多个输出时返回 ZIP
```

流水线 JSON 的获取捷径：先在界面里的「Automate」工具里可视化搭好流程，点保存面板里的「Export for Folder Scanning」，导出的就是 API 需要的格式；把这坨 JSON 塞进 HTTP 请求的 `json` 表单字段即可。

**5. 查完整接口清单**

浏览器打开 `http://<你的实例>:8080/swagger-ui/index.html`，可以浏览全部端点、直接试调、看请求/响应结构和认证要求。也可从界面右上角齿轮图标里的 API 文档入口进。

**6. 让 AI 助手直接调用（可选）**

内置 MCP 服务默认关闭。启用方式二选一：`settings.yml` 里设 `mcp.enabled: true`，或设环境变量 `MCP_ENABLED=true`；也可以在管理界面 **Admin Settings → MCP Server** 里开。启用后还需要配置认证模式（OAuth2 或 API Key），否则客户端无法调用工具。

```json
{
  "mcpServers": {
    "stirling-pdf": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://your-host:8080/mcp",
        "--header",
        "X-API-KEY:your-stirling-api-key"
      ]
    }
  }
}
```

端点固定是 `POST /mcp`；客户端用 API Key 模式时，Key 放在 `X-API-KEY` 头或 `Authorization: Bearer` 头里。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 启动后打不开 `localhost:8080` | 端口被占用、防火墙拦截，或容器反复重启 | 换端口映射 `-p 9000:8080`；看 `docker logs stirling-pdf`；资源不足就换 `latest-ultra-lite` |
| 挂载卷报权限错误 | 宿主目录不存在或权限不够 | 先建目录，再 `chmod -R 755 ./stirling-data` |
| OCR 里找不到我要的语言 | 语言包取决于镜像里装了哪些 Tesseract 语言包；默认镜像只含英、德、法、葡、简体中文 | 自备 `.traineddata` 挂到 `/usr/share/tessdata`，或装系统语言包。新版镜像里路径已改为 `/usr/share/tessdata`，旧路径只是向后兼容 |
| OCR 加了 `deskew` / `clean` / `cleanFinal` 却像没生效 | 这些高级选项依赖 OCRmyPDF；只有 Tesseract 时会被忽略 | 确认镜像内包含 OCRmyPDF，否则别指望这些选项 |
| OCR 后拿不到表格结构 | Tesseract 只做文字识别，不做表格结构与公式识别 | 表格类需求换专门的版面/表格识别工具，别在这里硬啃 |
| 转换 Word / Office 文件失败或质量差 | 这类转换依赖 LibreOffice，`latest` 与 `latest-fat`、`ultra-lite` 的差别就在这里 | 装完整版或 Fat 版镜像；`ultra-lite` 只做基础 PDF 操作，不要用它转 Office |
| 设了登录关闭却还是有登录页 | 新版本登录默认是开的，需要显式关 | 设 `SECURITY_ENABLELOGIN=false`；若容器已初始化过，确认 `/configs` 卷里的旧配置没有把设置顶回去 |
| 用默认 `admin` / `stirling` 就跑上线了 | 默认口令是公开的 | 首次登录立刻改密码；对外暴露前把安全设置配好 |
| 某些功能在 API 里找不到对应端点 | 部分功能（如查看 PDF、可视化签名）只在前端实现，没有后端 API | 这类操作只能走 Web UI；API 里没有就是设计如此 |
| 上传报 400 / 401 / 415 | 文件字段名不对、缺 API Key、或 `Content-Type` 不是 multipart | 文件字段统一用 `fileInput`；开认证时带 `X-API-KEY`；显式声明 `-H "Content-Type: multipart/form-data"` |
| 启用 MCP 后客户端调用 401 | 只开了 `mcp.enabled` 但没配认证；OAuth 模式下 `issuerUri` 为空会拒绝所有 token | API Key 模式：设 `MCP_AUTH_MODE=apikey` 并用已有用户 Key。OAuth 模式：必须设 `issuerUri`，且 `resourceId` 要等于客户端实际调用的 `/mcp` 公网地址并以 `/mcp` 结尾 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 拉取 Docker 镜像；服务监听端口供浏览器与脚本访问；MCP 模式下的协议通信 |
| 读取文件 | 是 | 读取待处理的 PDF / 图片 / Office 文档；挂载卷读取配置、日志、OCR 语言包与流水线配置 |
| 写入文件 | 是 | 输出处理结果；向 `/configs`、`/logs`、`/pipeline` 挂载卷写配置、日志与自动化配置 |
| 凭证 | 是 | 登录账号与 API Key（`X-API-KEY`）；MCP 的 OAuth2 相关配置。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | 以 Docker 容器形式长期运行；内部会调用 LibreOffice、Tesseract、qpdf、WeasyPrint 等外部组件完成转换与 OCR |

## 触发场景

- 「帮我把这几个 PDF 合并成一个」
- 「这份扫描件要能搜索，给我 OCR 一下」
- 「给这份合同每页加个『绝密』水印」
- 「Java 里怎么调 PDF 转换接口，不想用在线服务」
- 「把 PDF 压缩小一点再发出去」
- 「搭一个内网的 PDF 处理服务，别的系统要调」
- 「这台机器上批量处理 PDF 的自动化怎么配」

## 能力边界

**覆盖**：

- 50+ PDF 工具，跨编辑、合并、拆分、签名、脱敏、转换、OCR、压缩等类别。
- 三种使用界面：桌面客户端、浏览器 UI、自建服务器 + 私有 API。
- 面向几乎全部工具提供 REST API，可按 `POST /api/v1/<分类>/<操作>` 的规律调用。
- 无代码流程编排：界面上搭好流水线，可导出配置给自动化工具用，也可通过 `/api/v1/pipeline/handleData` 一次请求跑完整条链路。
- 可选的 MCP 服务，把 PDF 操作暴露给 MCP 客户端（Claude Desktop、IDE 助手、MCP Inspector 等）。
- 面向监控的统计与健康检查端点；界面 40+ 种语言。

**不覆盖**：

- 不做排版设计，不面向出版级高保真版面还原。
- OCR 只做文字识别，不做表格结构识别、公式识别；手写体精度有限，装饰性字体和小于 8pt 的小字效果差。
- 并非所有功能都有 API：只在前端实现的操作（如查看 PDF、可视化签名）无法通过接口调用。
- 官方不为 n8n / Zapier / Make / Power Automate 等平台提供专用插件或节点，集成一律走 REST API。
- 自建部署下 MCP 的 `stirling_ai` 工具不暴露任何能力（AI 引擎是云端特性）。

## 依赖条件

- Docker（推荐方式），或具备 JDK 25 等完整工具链的本地环境用于源码开发。
- 数据卷建议至少挂 `/configs`；要 OCR 再挂 `/usr/share/tessdata`，要日志挂 `/logs`，要自动化配置挂 `/pipeline`。
- OCR 需要 Tesseract（镜像已含）；高级 OCR 预处理选项需要 OCRmyPDF。
- Office 格式转换依赖 LibreOffice；PDF 优化依赖 qpdf；AI 文档创建依赖 WeasyPrint。缺少这些组件时相关功能自动不可用。
- 完整版镜像建议预留 4G 级别内存（官方 compose 示例里给内存限制写的就是 `4G`）。
- MCP 方式需要 MCP 客户端（如 Claude Desktop + `mcp-remote` 桥接）。

## 已知限制

- 界面截图、版本号与功能清单随版本演进，具体以你部署的实例和 [官方文档](https://docs.stirlingpdf.com) 为准；此处不臆断版本号与发布日期。
- 上游项目是 open-core 模式：本 Skill 只覆盖社区版可见的能力，付费/企业特性（SSO、审计等）不在范围内。
- 社区维护的 NAS / 虚拟化集成不属于上游官方支持范围。
- MCP 的 `stirling_ai` 工具在自建场景下形同虚设。
- 前端专属功能无法通过 API 自动化。

## 自检清单

- [ ] 确认目标操作在 API 里确实存在（查 `/swagger-ui/index.html`）；只在前端实现的功能改用 UI。
- [ ] 容器起来了且 `docker logs stirling-pdf` 无持续报错。
- [ ] 端口没冲突，浏览器能打开首页。
- [ ] 需要持久化的目录都已挂载，且宿主目录权限正确。
- [ ] 默认口令已修改；对外暴露前安全设置已确认。
- [ ] 开认证时：请求带上了 `X-API-KEY`（或全局 Key 已通过环境变量设好）。
- [ ] 请求的 `Content-Type` 是 `multipart/form-data`，文件字段名是 `fileInput`。
- [ ] OCR 场景：所需语言包已装，`ocrType` 选择符合预期（不要误用强制模式覆盖已有文字层）。
- [ ] 依赖外部组件的操作（Office 转换、qpdf、WeasyPrint）：确认所用镜像版本包含这些组件。
- [ ] 用流水线时：JSON 是从界面导出的、格式正确，且响应是单文件还是 ZIP 已按预期处理。
- [ ] 启用 MCP 时：认证模式已配好（API Key 模式设了 `MCP_AUTH_MODE=apikey`；OAuth 模式设了 `issuerUri` 且 `resourceId` 以 `/mcp` 结尾）。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Stirling-Tools/Stirling-PDF | 上游仓库（安装与完整文档以它为准） |
| https://docs.stirlingpdf.com | 官方文档站（Docker 安装、配置、自动化、OCR 等） |

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
