# 三剪客 · 极速语音转写 Skill

在本机 GPU 上把长音频快速转成带时间戳的 JSON 文字稿的安装、常用命令与避坑要点

---

## 前置条件

- **硬件**：NVIDIA 显卡（并装好匹配 CUDA 版本的 PyTorch），或 Apple Silicon 的 Mac。其他设备不在上游承诺范围内。
- **Python**：上游打包元数据声明 `requires-python >= 3.8`；但 Python 3.11.x 搭配 pipx 存在版本误判问题，需要忽略 Python 版本要求安装，详见 `SKILL.md` 的「安装」一节。
- **pipx 或 pip**：上游推荐 pipx，把工具装成独立环境里的全局命令。
- **网络**：首次运行需要下载模型权重（默认检查点体积较大）。
- **可选**：要开 Flash Attention 2 需另外安装 `flash-attn`；要说话人分离需自备 Hugging Face Token。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pipx install insanely-fast-whisper
insanely-fast-whisper --file-name your_audio.mp3
```

macOS 上补一个设备参数：

```bash
insanely-fast-whisper --file-name your_audio.mp3 --device-id mps
```

显存不够就往下调 batch size：

```bash
insanely-fast-whisper --file-name your_audio.mp3 --batch-size 8
```

结果默认写到 `output.json`，结构是 `speakers` / `chunks` / `text` 三个键。

CLI 参数与默认值以 `insanely-fast-whisper --help` 和上游仓库 README 的当前内容为准。

---

## 依赖

- `transformers`、`accelerate`、`pyannote-audio`、`rich`、`setuptools`（由包管理器自动拉取）
- 与显卡匹配的 CUDA 版 PyTorch（或 macOS 上的 mps 支持）
- 可选：`flash-attn`（启用 `--flash True` 时）
- 可选：Hugging Face Token（启用说话人分离时）

---

## 安全

- 不内嵌任何密钥；`--hf-token` 由使用者自己提供，注意不要写进会入库的脚本或镜像
- 该工具会把音频文件内容送进本地模型推理；若 `--file-name` 传的是 URL，它会主动联网下载，处理不受信任的来源前请先确认目标地址
- 首次运行会从模型仓库拉取权重，注意磁盘占用与网络出口策略
- 转写结果可能包含原始录音里的敏感信息，`output.json` 落盘位置与留存策略请自行管控

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`insanely-fast-whisper`
- 仓库：https://github.com/Vaibhavs10/insanely-fast-whisper

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
