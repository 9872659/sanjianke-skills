# 三剪客 · 开源语音合成与音色克隆 Skill

在自己的机器上把文本合成为语音：给一段参考音频就能复制音色，也能把已有语音转换成另一个人的嗓音。命令行、Python API、本地服务三种用法齐全，还带完整的训练与微调流程。

---

## 前置条件

- **Python**：官方给出的验证范围是 3.10 以上、3.15 以下。
- **PyTorch**：2.2 以上。**必须自行先装**——从某个版本起它不再作为默认依赖一起安装；使用新版 PyTorch 时还需要 `torchcodec`。CPU 可跑，GPU 明显更快。
- **虚拟环境**：官方强烈推荐用 uv 建虚拟环境（直接照搬命令时把 `uv` 去掉也能用普通 venv）。
- **包名注意**：PyPI 上的安装包名是 `coqui-tts`，而代码里的导入名是 `TTS`，两者不一样。
- **语言前端**：非英语语言需要对应的可选依赖，例如中文要装 `zh` extra。
- **磁盘**：每个模型的权重都是运行时单独下载的，多个模型累计占用可观。
- **维护状态**：上游原仓库已归档，当前维护与文档由社区接手的版本提供。建议锁定版本使用。

---

## 使用

安装（顺序不能颠倒）：

```bash
uv pip install torch torchaudio torchcodec --torch-backend=auto
uv pip install coqui-tts
uv pip install coqui-tts[server,zh]      # 需要本地服务和中文时
```

先看有哪些模型：

```bash
tts --list_models
```

一行出配音：

```bash
tts --text "要合成的文本" --out_path output/speech.wav
```

克隆音色并缓存，之后复用：

```bash
tts --model_name "tts_models/multilingual/multi-dataset/xtts_v2" \
    --text "Hello world" --language_idx "en" \
    --speaker_wav "my/cloning/audio.wav" --speaker_idx "MySpeaker1"

tts --model_name "tts_models/multilingual/multi-dataset/xtts_v2" \
    --text "Hello world" --language_idx "en" --speaker_idx "MySpeaker1"
```

起服务：

```bash
tts-server --model_name "tts_models/en/vctk/vits" --speaker_idx p376
```

六块正文（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

- **核心**：Python 3.10~3.15、PyTorch 2.2+、`coqui-tts` 包。
- **PyTorch 生态**：`torch`、`torchaudio`，新版 PyTorch 还需要 `torchcodec`。
- **可选 extras**：`all`、`notebooks`、`server`、`bn`、`ja`、`ko`、`zh`、`languages`；另有 `cpu` / `cuda` / `codec` / `codec-cuda` 用于装 PyTorch 相关依赖。
- **模型**：运行时从模型托管站下载；也可使用自己训练产出的 `.pth` + `config.json` 组合，声码器可单独指定。
- **系统依赖**：Ubuntu / Debian 上可用仓库的 `make system-deps` 安装；其它平台以官方文档为准。
- **硬件**：CPU 可运行；批量合成与训练建议使用 GPU。

---

## 安全

- 不内嵌任何密钥，本包只有文字说明。
- 音色克隆与语音转换涉及他人声音权益：**必须获得声音所有者的明确同意**，不得用于冒充、欺骗或制造虚假信息。官方文档对此有同等要求。
- 参考音频往往包含真实人物的生物特征信息，注意存储与使用范围，不要随意上传到第三方平台。
- 模型权重是运行时从外部地址下载的，注意核对来源；内网环境建议预先下载并在受控位置分发。
- `tts-server` 默认监听本机 5002 端口，且官方明确说明未做性能优化、不是生产级服务。对外暴露前必须自行加上鉴权、限流与输入校验。
- 训练会长时间占用 GPU 与磁盘，注意工作目录空间与显存被其它任务抢占的情况。
- 商用前请分别核对**代码**与**预训练模型**各自的许可条款——两者可能不是同一套条款。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Coqui TTS`
- 仓库：https://github.com/coqui-ai/TTS
- 安装文档：https://coqui-tts.readthedocs.io/en/latest/installation.html
- 推理文档：https://coqui-tts.readthedocs.io/en/latest/inference.html
- 克隆文档：https://coqui-tts.readthedocs.io/en/latest/cloning.html

> 说明：上游原仓库已归档，实际维护与文档目前由社区接手的版本提供。安装命令与参数请以该文档站当前内容为准。

---

## 许可证

MIT，见 `LICENSE.md`。

> 上游项目的**代码**与**发布的预训练模型**可能适用不同的许可条款，且条款与商业使用限制可能随版本变化。商用前请自行核对官方当前说明，不要仅凭本包的 MIT 声明推断上游授权。

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
