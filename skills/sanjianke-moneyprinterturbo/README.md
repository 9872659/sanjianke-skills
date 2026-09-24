# 三剪客 · 一句话生成AI短视频 Skill

MoneyPrinterTurbo：给一个主题或关键词，自动生成脚本、配音、字幕、素材匹配与背景音乐，合成竖屏 / 横屏 / 方形短视频。

---

## 前置条件

- Python **3.11 或更高**（上游要求，推荐 3.11）；或使用 Docker Desktop / Docker Compose。
- 安装路径**不要含中文、特殊字符或空格**（Windows 上尤其重要）。
- 首次启动会由 `config.example.toml` 自动生成 `config.toml`，无需手动创建；填凭据也是在生成后的文件里填。
- 至少准备一项：大模型服务的凭据（用于写脚本），以及默认素材源的 API Key。
- 默认配音走免费在线 TTS，不需要 API Key；换其他配音服务才需要对应凭据。
- 建议显存 0 也可以跑，但启用本地 Whisper 字幕或批量生成时，独立显卡会明显更快。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（命令行出片）：

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
cd MoneyPrinterTurbo
uv python install 3.11
uv sync --frozen
uv run python cli.py --video-subject "人工智能如何改变日常生活"
```

Docker 起服务：

```bash
cp config.example.toml config.toml
docker compose -f docker-compose.release.yml up
# WebUI: http://127.0.0.1:8501   API 文档: http://127.0.0.1:8080/docs
```

批量跑清单（UTF-8 JSON 数组或 JSONL，最多 100 条、1 MiB）：

```bash
uv run python cli.py --batch-file ./tasks.json --stop-at video
```

命令行的完整参数与流水线阶段划分以 `uv run python cli.py --help` 的输出为准；可用的模型服务与素材源清单以项目内 `config.example.toml` 的注释和仓库当前内容为准。

---

## 依赖

- Python 3.11+，或 Docker（上游推荐用 `docker-compose.release.yml` 拉预构建镜像）
- ffmpeg 与 ffprobe（通常自动下载检测；失败时配置 `ffmpeg_path`）
- 大模型服务凭据（云端或本地兼容服务均可，具体 provider 见项目内注册表）
- 素材源凭据（默认素材源需申请 API Key；用本地素材源则不需要）
- 可选：本地 Whisper 字幕所需模型（默认约 3 GB，`large-v3-turbo` 约 1.6 GB）
- 可选：Redis（开启 `enable_redis` 时用于任务状态）
- 可选：第三方跨平台发布服务的凭据

---

## 安全

- 不内嵌任何密钥
- 所有真实密钥只应写在 `config.toml` 里；上游明确要求不要提交该文件，`.example` 模板才是可以入库的
- 可选保护项 `[app].api_key` 一旦配置，API 路由与任务产物下载都要求 `x-api-key` 请求头；纯本地使用可留空，但对公网暴露前务必开启
- API 默认只允许同源网页访问；跨源需求应通过 `CORS_ALLOWED_ORIGINS` 逐个列出可信来源，而不是无差别放开
- 本机浏览器访问的 WebUI 与 API 服务默认监听地址由 `listen_host` 决定，`0.0.0.0` 会监听全部网卡，公网机器上应改为 `127.0.0.1` 或加反向代理与鉴权
- `enable_redis` 的场景下，任务状态是序列化存储的，Redis 必须保持私有，不能让不可信写入方修改任务记录
- 使用按次计费的文生视频源会产生真实费用，命令行要求显式传确认开关后再提交任务
- 素材、背景音乐与配音都有各自授权条件，对外发布前须自行确认权利来源
- 开启第三方跨平台发布意味着生成物会自动上传到外部平台，请确认账号与隐私设置（含"是否面向儿童"这类声明项）

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`MoneyPrinterTurbo`
- 仓库：https://github.com/harry0703/MoneyPrinterTurbo

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
