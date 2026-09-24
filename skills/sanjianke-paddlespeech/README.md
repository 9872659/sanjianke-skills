# 三剪客 · 语音识别与合成工具箱 Skill

语音识别、语音合成、声音分类、声纹提取与标点恢复一站式工具箱的安装、常用命令与避坑要点

---

## 前置条件

- **平台**：上游强烈建议在 **Linux** 上安装；Windows / macOS 也支持，但依赖问题更多。
- **Python**：>= 3.8。
- **系统**：`gcc >= 4.8.5`。
- **必须先装 PaddlePaddle**：PaddleSpeech 不会自动带对你的 paddlepaddle 版本，需要先按 PaddlePaddle 官方安装页面选好 CPU 或对应 CUDA 的 GPU 版并安装。
- **安装前置**：先 `pip install pytest-runner`。
- **输入格式**：音频要求 **16k 采样率 wav**。
- **功能限制**：语音翻译（英译中）依赖 kaldi 预编译工具，只在 Ubuntu 上支持。
- **可选**：GPU（训练与大批量推理建议有）；Docker（上游 README 提到可以在容器里启动服务）。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install pytest-runner
pip install paddlespeech

paddlespeech asr --lang zh --input zh.wav
paddlespeech tts --input "这里换成你要合成的文本" --output output.wav
```

先看有哪些子命令：

```bash
paddlespeech help
```

起一个本地语音服务：

```bash
paddlespeech_server start --config_file ./demos/speech_server/conf/application.yaml
paddlespeech_client asr --server_ip 127.0.0.1 --port 8090 --input input_16k.wav
```

用 Python API：

```python
from paddlespeech.cli.asr.infer import ASRExecutor

asr = ASRExecutor()
print(asr(audio_file="zh.wav"))
```

子命令、参数与服务端配置以 `paddlespeech help`、`paddlespeech_server help`、`paddlespeech_client help` 和上游仓库文档的当前内容为准。

---

## 依赖

- PaddlePaddle（CPU 版或匹配 CUDA 的 GPU 版，须单独安装）
- Python >= 3.8、`gcc >= 4.8.5`
- `pytest-runner`（安装前置）
- 上游安装文档中列出的其他系统与 Python 依赖（conda / librosa / gcc / kaldi 等场景分开说明）
- 可选：kaldi 预编译工具（仅语音翻译等少数功能需要，限 Ubuntu）
- 可选：GPU 与对应 CUDA 环境（训练、大批量推理）

---

## 安全

- 不内嵌任何密钥；该工具不需要账号或 API Key，推理全部在本地完成
- 首次运行会从网络下载预训练模型权重，注意磁盘占用与网络出口策略
- 起服务端时它会监听端口；默认配置通常绑在本机，若要对容器外或局域网暴露，请自行加上鉴权与访问控制，不要直接暴露到公网
- 输入音频与合成结果都可能是敏感素材（人声、声纹），文件落盘位置与留存策略请自行管控
- 声音克隆、语音合成类能力涉及他人声音权益，使用前请确认已取得授权

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`PaddleSpeech`
- 仓库：https://github.com/PaddlePaddle/PaddleSpeech

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
