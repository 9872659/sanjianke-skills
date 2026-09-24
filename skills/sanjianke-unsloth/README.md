# 三剪客 · 低显存微调加速 Skill

Unsloth：用一张消费级显卡微调大模型——桌面版 / Studio / Core 三条安装路径、Docker 起服务、把本地模型接给编码 Agent，以及显存、端口、许可与安全避坑。

---

## 前置条件

- **一块可用的 GPU**（NVIDIA / AMD / Intel 任一）。没有 GPU 也能用 CPU / Vulkan 后端跑，但就失去了"低显存加速"这个核心价值。
- **按形态准备环境**：
  - **桌面版**：对应平台的原生安装包（Windows `.exe` / macOS `.dmg` / Ubuntu `.deb` / Linux `.AppImage`）。
  - **Studio**：macOS / Linux / WSL 用官方安装脚本，Windows 用 PowerShell 脚本。
  - **Core**：Python 3.13（官方示例版本）+ `uv`；Windows 上先用 `winget` 装 Python 与 uv。
  - **Docker**：本机 Docker；Linux 需先配 GPU 容器工具链，Windows 走 Docker Desktop + WSL 2。
- **磁盘空间**：模型权重与检查点体量很大，且默认落在用户目录下的 Hugging Face 缓存里。
- **凭证**：下载受限模型需要模型仓库的访问令牌；Studio / Jupyter 需要自行设置访问密码。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径（Studio，macOS / Linux / WSL）：

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
unsloth studio
```

Windows：

```powershell
irm https://unsloth.ai/install.ps1 | iex
unsloth studio
```

Core（代码版，Linux / WSL）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv unsloth_env --python 3.13
source unsloth_env/bin/activate
uv pip install unsloth --torch-backend=auto
```

把本地模型接给编码 Agent：

```bash
unsloth start claude --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL
```

训练参数、导出格式与高级开关随版本演进，落地前以官方文档与 `--help` 为准。

---

## 依赖

- GPU：NVIDIA / AMD / Intel；也支持 CPU 与 Vulkan 后端（无加速收益）
- `uv` + Python 3.13（Core 路径）；`winget`（Windows 装 Python 与 uv）
- Docker（容器路径）；Linux 上另需 GPU 容器工具链
- 模型仓库的访问令牌（下载受限模型时）
- 足够的磁盘空间放模型权重、检查点与导出产物

---

## 安全

- 不内嵌任何密钥
- 官方明确提示**服务端工具默认开启**：把 Studio 暴露到公网前，务必设强密码，不需要工具能力时加 `--disable-tools`
- `--secure` 会经隧道把服务暴露到公网（换来的是外部设备可访问），只在确有需要时使用
- 安装方式是"远程脚本管道给 shell 执行"，对供应链敏感的环境应改用安装包或 Docker 镜像
- 许可为 Apache 2.0 + AGPL-3.0 双许可，商用前先确认自己用的是哪一部分
- Studio / Jupyter 密码不要用弱口令，也不要写进会提交到 Git 的文件

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Unsloth`
- 仓库：https://github.com/unslothai/unsloth

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
