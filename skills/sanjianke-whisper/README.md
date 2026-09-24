# 三剪客 · 语音识别与转写 Skill

Whisper：把音视频里的人声转成带时间轴的文字，支持多语言识别、语种自动判定与「非英语语音翻成英文」。

---

## 前置条件

- Python 3.8–3.11（官方说明的兼容区间，参考环境为 Python 3.9.9）。
- **必须安装 ffmpeg 命令行工具**（不是 Python 包），它用于解码音频；没有就直接失败。
- 较新的 PyTorch；官方参考环境是 1.10.1。
- 需要预留磁盘空间：模型权重从几十 MB 到 1.5 GB 级不等，首次使用会下载。
- 若目标平台没有 tiktoken 预编译 wheel，还需要 Rust 工具链才能装成功。
- 不需要任何账号或 API Key。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install -U openai-whisper          # 装包
sudo apt install ffmpeg                # 装 ffmpeg（macOS 用 brew，Windows 用 choco / scoop）

whisper audio.mp3 --model turbo        # 转写
whisper japanese.wav --language Japanese                            # 指定语种
whisper japanese.wav --model medium --language Japanese --task translate   # 翻译成英文
whisper --help                         # 看全部参数
```

只想要时间戳或想在代码里用：

```python
import whisper

model = whisper.load_model("turbo")
result = model.transcribe("audio.mp3")
print(result["text"])
```

**选型提醒**：`turbo` 精度接近 `large-v3`、速度快，但没有翻译能力；要翻译必须换多语言模型（`medium` 或 `large` 效果最好）。参数名与可选输出格式请以当前版本的 `whisper --help` 与上游仓库 README 为准。

---

## 依赖

- Python 3.8–3.11 + 较新的 PyTorch
- ffmpeg 命令行工具（必需）
- tiktoken（官方点名的关键 Python 依赖）
- 可选：Rust 工具链 + setuptools-rust（当平台没有 tiktoken 预编译 wheel 时）
- 模型权重（首次使用按所选尺寸自动下载）
- 可选：NVIDIA GPU + 对应 CUDA 版 PyTorch（显著加速，非必需）

---

## 安全

- 不内嵌任何密钥
- 全程本地推理：除首次下载模型权重外不联网，语音素材不会离开本机，适合处理不便上传的内容
- 音频解码交给本地 ffmpeg 子进程，输入文件由调用方控制，不要对不可信路径做拼接
- 输出会写入你指定的目录，批量任务前先确认目标路径与磁盘余量
- 转写他人录音可能涉及隐私与肖像/声音权益，使用前须确认已获授权，并妥善保管转写结果
- 模型权重应从官方发布渠道获取，避免使用来源不明的权重文件

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Whisper`
- 仓库：https://github.com/openai/whisper

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
