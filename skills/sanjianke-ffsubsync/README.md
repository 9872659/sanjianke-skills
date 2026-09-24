# 三剪客 · 字幕与视频自动对齐 Skill

把对不上的字幕自动对齐到视频：以音轨或一份已同步的参照字幕为基准，算出偏移与帧率缩放后改写时间轴。

---

## 前置条件

- **先装 ffmpeg**，并确保 `ffmpeg` / `ffprobe` 能从命令行直接调用（在 PATH 中）。这是硬前置，Python 包不会替你装。
- 一个可用的 Python 环境（上游 README 标注兼容 Python >= 3.6，实际可用区间以 PyPI 页面为准）。
- 想用神经网络 VAD（`--vad=fused` 等）时，另需可选的 torch 依赖。
- 走 `--whisper-weights` 转写路线时，需要 ffmpeg >= 8.0 且构建带 whisper 滤镜，并自备 ggml 模型文件。
- 不需要账号、不需要 API Key。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（视频当参照）：

```bash
pip install ffsubsync
ffs video.mp4 -i unsynchronized.srt -o synchronized.srt
```

更快的一条路——手头有已同步的字幕就直接拿它当参照，通常一秒内出结果：

```bash
ffsubsync reference.srt -i unsynchronized.srt -o synchronized.srt
```

批量：省略 `-i`，让它自己找参照旁边的同名字幕，逐个写成 `<名字>.synced.srt`，原文件不动：

```bash
ffs video.mp4
```

参数名、默认值与新增选项以 `ffs --help` 和上游仓库 / 文档站的当前内容为准。

---

## 依赖

- 系统级：**ffmpeg**（必需），含 `ffprobe`
- Python 包：`ffsubsync`（数值计算依赖随包安装）
- 可选：torch —— `pip install ffsubsync[torch]`，用于 silero / fused 系列 VAD
- 可选：whisper.cpp 的 ggml 模型文件 + 支持 whisper 滤镜的 ffmpeg >= 8.0
- 可选：Docker（官方预构建镜像在 GitHub Container Registry：`ghcr.io/smacke/ffsubsync`）

---

## 安全

- 不内嵌任何密钥
- 参照物可以是远程 URL（`http(s)` / `rtmp` / `rtsp` / `ftp`），此时会把外部内容拉进本机分析；不要对不受信任的来源开放这一入口，以免被用来探测内网地址
- `--overwrite-input` 会**直接覆盖原始字幕**，不可撤销；批量使用前先备份，且注意它与 `-o` 互斥
- 它会以当前进程权限读写文件、并调用本机 ffmpeg 子进程；处理来源不明的素材时，建议在容器或隔离目录里跑
- 自动发现模式会扫描参照文件所在目录；不要把参照指向一个混入无关文件的目录
- 批处理时建议打开 `--skip-sync-on-low-quality`，让不可信的对齐保持原样，而不是写出一个可能更糟的结果

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`ffsubsync`
- 仓库：https://github.com/smacke/ffsubsync

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
