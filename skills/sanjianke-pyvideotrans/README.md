# 三剪客 · 视频翻译与多角色 AI 配音 Skill

从语音识别到字幕翻译、多角色 AI 配音与音画合成的整条视频换语言流水线，带 GUI、CLI、WebUI 与容器化四种跑法。

---

## 前置条件

- Python 3.10（仓库 `.python-version` 已指定）；或直接用 Windows 预打包版，免环境配置
- FFmpeg 必须安装并配到环境变量（Windows 打包版已内置；源码部署必须自己装）
- 包管理器建议用 `uv`
- 磁盘要有余量：模型与缓存占用可观，启用视频慢速时临时文件可能远大于原片
- 要用 GPU 加速的话：NVIDIA 显卡 + CUDA 12.8+ + cuDNN 9.11+（只支持 N 卡）
- 要用在线识别 / 翻译 / 配音渠道的话：准备对应平台的 Key，并确认网络可达（境外接口可能需代理）
- 系统要求：Windows 10/11 或主流 macOS / Linux；不支持 Windows 7

---

## 使用

**GUI（桌面版）**：解压到不含中文与空格的路径，双击 `sp.exe`；源码部署用 `uv run sp.py`。识别、翻译、配音三个阶段都可暂停下来人工校对。

**CLI（服务器 / 批量）**：四种任务类型，`--task` 与 `--name` 必选。

```bash
# 视频翻译：识别 → 翻译 → 配音 → 合成
uv run cli.py --task vtv --name "./video.mp4" \
  --source_language_code zh-cn --target_language_code en \
  --voice_role "en-US-GuyNeural"

# 语音转录成字幕
uv run cli.py --task stt --name "./audio.wav" --model_name large-v3

# 字幕翻译
uv run cli.py --task sts --name "./subs.srt" --target_language_code en

# 文字配音
uv run cli.py --task tts --name "./subs.srt" --voice_role "zh-CN-YunyangNeural"

# 查真实可用的渠道 / 语言 / 模型编号（不要凭印象写编号）
uv run cli.py --list providers
uv run cli.py --list languages
uv run cli.py --list models
```

**WebUI（远端 / 局域网）**：

```bash
uv sync --extra webui
uv run webui.py                 # 默认 0.0.0.0:7860
uv run webui.py --port 8080     # 指定端口
uv run webui.py --share         # 生成临时公网链接
```

**容器化**：

```bash
docker build -t pyvideotrans-webui .
docker run -d -p 7860:7860 --name pyvideotrans pyvideotrans-webui
```

完整参数表、对齐策略、故障排查与权限说明见 `SKILL.md`。

---

## 依赖

- FFmpeg（含 `ffprobe`）：音视频处理的基础依赖，源码部署必须自行安装
- Python 3.10 与 `uv`；macOS 另需 libsndfile，Linux 另需 libsndfile1-dev
- 本地模型：识别用的 whisper 系列模型、说话人分离模型、本地 TTS 模型（按需下载，占磁盘）
- 可选加速：NVIDIA CUDA 12.8+ 与 cuDNN 9.11+
- 在线渠道：大模型翻译 Key、商业 TTS Key、云厂商识别 Key 等（按实际选用的渠道而定）
- WebUI / 容器：`--extra webui` 或 Docker；GPU 容器需 nvidia-container-toolkit
- 本地克隆音色：需另行部署 F5-TTS / CosyVoice / GPT-SoVITS 等服务并暴露 API

---

## 安全

- 不内嵌任何密钥：在线渠道的 Key 由使用者自行填写，保存在本机 `videotrans/` 配置中，本包不含任何凭证
- 待处理素材必须有合法授权：上游明确声明使用者需自行承担调用第三方接口与处理受版权保护内容带来的后果
- 使用在线渠道时，音频与字幕文本会外发到对应服务商；涉密素材请改用本地离线渠道
- 网络代理配置要谨慎：填错会直接报错，不清楚就留空；国内接口与本地 TTS 默认不走代理
- 本地 TTS 服务与 WebUI 会监听端口，`--share` 会生成公网链接，对外开放前先确认鉴权与网络环境
- 说话人分离等部分模型需要到模型平台申请令牌并同意授权协议，请自行评估数据用途
- 软件为 GPL-v3：集成进商业产品需遵守该协议；所用第三方模型与 API 另有各自条款

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pyvideotrans`
- 仓库：https://github.com/jianchang512/pyvideotrans

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
