# 三剪客 · 多情感多音色语音合成 Skill

EmotiVoice：多情感多音色语音合成 的安装、常用命令与避坑要点

---

## 前置条件

- 一台带 NVIDIA 显卡的机器，驱动正常，`nvidia-smi` 能出结果（纯 CPU 能跑通但很慢，不适合批量）
- 磁盘预留空间放预训练权重与输出音频，权重体积不小，先看清剩余空间
- 想走 Docker：已装好 Docker，以及 NVIDIA 容器工具链（Windows 需要先配通 WSL2 的 GPU 透传）
- 想走本地安装：已装好 conda，能创建 Python 3.8 的独立环境
- 能访问权重托管站点与代码托管站点；网络受限时改用逐文件下载的方式补齐

---

## 使用

本篇是操作整理，把「装、跑、避坑」按顺序讲清楚，命令与参数均来自上游仓库自己的说明。

常用入口速查：

- 网页试听界面：`streamlit run demo_page.py`，或 Docker 方式打开 `http://localhost:8501`
- OpenAI 兼容接口：`uvicorn openaiapi:app --reload`，Docker 方式暴露在 `http://localhost:8000`
- 命令行批量合成：先用 `python frontend.py` 转音素，再跑 `inference_am_vocoder_joint.py`
- 权重摆放：`g_*`、`do_*` 进 `outputs/prompt_tts_open_source_joint/ckpt`，`checkpoint_*` 进 `outputs/style_encoder/ckpt`

完整的六块内容（用与不用、安装、常用操作、常见坑、权限与用途、能力边界）见 `SKILL.md`。

---

## 依赖

- Python 3.8 及以上（PyPI 元数据声明 `>=3.8.0`）
- PyTorch、torchaudio，按显卡驱动的 CUDA 版本匹配安装
- numpy、numba、scipy、soundfile、yacs、g2p_en、jieba、pypinyin
- transformers：版本敏感，按上游 README 指定版本安装
- streamlit（网页界面）、fastapi + uvicorn + pydub + pyrubberband（OpenAI 兼容接口）
- git-lfs（拉取 BERT 权重）；预训练权重需另行下载
- 中文字素与数字处理相关依赖由仓库的安装清单覆盖，以仓库当前说明为准

---

## 安全

- 不内嵌任何密钥
- 纯本地推理不需要任何账号或 API Key，也不会上传你的文本与音频
- 若把网页界面或 HTTP 接口暴露到公网，必须自行加鉴权与访问控制（示例命令都只绑定 `127.0.0.1`）
- 音色克隆只使用你拥有授权的录音；用他人声音合成并对外发布可能涉及人格权与平台规则风险
- 交互式页面另有上游单独的用户协议文件约束，商用前请自行阅读
- 模型权重与生成的音频建议纳入版本管理之外的临时目录，避免误提交进仓库

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`EmotiVoice`
- 仓库：https://github.com/netease-youdao/EmotiVoice

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
