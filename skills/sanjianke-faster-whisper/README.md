# 三剪客 · 语音转文字与字幕生成 Skill

faster-whisper：把音频/视频转成带时间轴的文字，出 SRT 字幕、做批量转写与本地离线识别的 Python 库，含安装、真实调用方式与避坑要点。

---

## 前置条件

- Python 3.9 或更高
- 不需要单独安装 ffmpeg：音频解码走 PyAV，FFmpeg 动态库已打包在里面
- GPU 运行额外需要 NVIDIA cuBLAS（CUDA 12）与 cuDNN 9，并保证启动 Python 前已设好库搜索路径
- 首次按模型名加载会从 Hugging Face Hub 下载权重，需要联网与磁盘空间；离线场景要提前缓存
- 公开模型不需要账号或 API Key
- 这是一个 Python 库，不是命令行程序——需要自己写几行调用脚本

---

## 使用

最小可用示例：

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe("audio.mp3", beam_size=5)

print("Detected language '%s' with probability %f" % (info.language, info.language_probability))
for segment in segments:
    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
```

关键点：`segments` 是生成器，必须被遍历或转成 list，转写才真正执行。

长音频或批量素材用批处理管线更快：

```python
from faster_whisper import WhisperModel, BatchedInferencePipeline

model = WhisperModel("turbo", device="cuda", compute_type="float16")
batched_model = BatchedInferencePipeline(model=model)
segments, info = batched_model.transcribe("audio.mp3", batch_size=16)
```

要词级时间轴就加 `word_timestamps=True`，再读 `segment.words` 里每个词的 `start` / `end` / `word`。完整参数、字幕导出写法与排查表都在 `SKILL.md` 里。

---

## 依赖

- 运行时：Python 3.9+
- Python 包：`ctranslate2`、`tokenizers`、`huggingface_hub`、`av`（PyAV）、`numpy`、`onnxruntime`（VAD 用）、`tqdm`
- 系统库：GPU 场景需要 NVIDIA cuBLAS（CUDA 12）与 cuDNN 9；新版 `ctranslate2` 只支持 CUDA 12 + cuDNN 9
- 模型权重：按模型名加载时从 Hugging Face Hub 上的 CTranslate2 转换仓库下载
- 可选：加载自定义微调模型时需要 `transformers[torch]` 与 `ct2-transformers-converter`

---

## 安全

- 不内嵌任何密钥
- 转写全程可在本地完成：权重缓存好后配合 `local_files_only=True` 即可断网运行，素材不出本机
- 需要读入音频/视频文件；转写结果的落盘由使用者自己的脚本负责
- 需要下载模型权重时会访问 Hugging Face Hub；受限模型可传 Hugging Face token
- 可用 `num_workers` 起多进程、多 GPU 并行，注意批量任务的资源占用
- 转写他人音视频内容请注意素材授权与当地法律要求

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`faster-whisper`
- 仓库：https://github.com/SYSTRAN/faster-whisper

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
