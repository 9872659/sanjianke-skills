# 三剪客 · 识别文字自动剪视频 Skill

先用语音识别出带时间戳的文稿，再按文字或说话人定位并自动裁出对应片段。本包给出安装、界面与命令行两种用法、模型选型与排错要点。

---

## 前置条件

- **一个独立的 Python 虚拟环境**（官方明确要求与已有环境隔离，示例用 Python 3.12），不要装进正在运行的服务环境。
- **匹配本机平台的 PyTorch / torchaudio**，并且要在装其余依赖之前先装好。CPU 环境从 PyTorch 官方 CPU 源装；GPU 环境按其官方安装指引选版本。
- 输入素材必须**有人声**；若是视频，必须有音轨。
- 首次运行需要网络：模型权重不在源码包里，是启动时另行下载的，同时要留足磁盘空间。
- 走大模型辅助剪辑或视频理解挑段落时，另需相应服务的 API Key（可用环境变量配置）。
- 走第三方长音频路线时，需要额外起一个本地推理服务。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最省事的路径——起本地网页，上传视频、识别、复制文字、点裁剪：

```bash
python funclip/launch.py
```

脚本化路径——命令行两段式，先识别再按文字裁剪：

```bash
python funclip/videoclipper.py --stage 1 --file input.mp4 --output_dir ./output

python funclip/videoclipper.py --stage 2 --file input.mp4 --output_dir ./output \
  --dest_text '要保留的那句话' --output_file ./output/res.mp4
```

参数名、默认值与新增模型选项以 `python funclip/launch.py --help`、`python funclip/videoclipper.py --help` 和上游仓库当前文档为准。

---

## 依赖

- 匹配平台的 `torch` / `torchaudio`（先装）
- 仓库 `requirements.txt`：语音识别框架、受版本约束的 `transformers` 与 hub 库、`moviepy`、`pillow`、`numpy`、Gradio 4.x 运行时等
- 模型权重：单独下载，不在源码包内
- 可选：视频理解 SDK —— 仅走视频理解模型挑段落时需要
- 可选：一个本地推理服务 —— 仅走第三方长音频路线时需要
- 系统级：无需额外系统包；服务对外暴露靠启动参数而非系统依赖

---

## 安全

- 不内嵌任何密钥
- 界面支持把 API Key 粘进输入框，也支持用环境变量配置；**优先用环境变量**，避免密钥留在界面或截图里
- 启动时 `-s True` 会把服务开成公网可访问，公开部署前务必确认监听范围与访问控制，必要时配合反向代理与鉴权
- 素材与中间文件都落在本地工作目录（`--output_dir`）；批量作业前确认目录权限与磁盘余量
- 安装依赖时如遇 HTTPS 证书失败，应通过可信 CA（`--cert` / `PIP_CERT`）解决，**不要**关闭证书校验或随意信任主机
- 不要把原生新路线的升级命令执行进 FunClip 环境：它需要保留 Transformers 4.x 的那套版本约束

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`FunClip`
- 仓库：https://github.com/modelscope/FunClip

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
