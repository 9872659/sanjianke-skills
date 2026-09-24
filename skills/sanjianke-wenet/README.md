# 三剪客 · 端到端语音识别工具包 Skill

wenet：端到端语音识别工具包 的安装、常用命令与避坑要点

---

## 前置条件

- Python 环境（上游训练示例用 3.10；pip 包未声明 Python 版本上限）
- 该项目**没有发布到 PyPI 的正式包**，必须从代码仓库安装，建议固定 commit 便于复现
- 想用 GPU：NVIDIA 显卡 + 匹配的驱动 + 对应 CUDA 版本的 torch；上游训练环境建议 CUDA 12.1
- 需要 sox（conda 环境用 `conda-forge::sox`；系统级安装需带开发头文件，否则报 sox 扩展缺失）
- 想编译 x86 运行时或接语言模型：cmake 3.14 以上
- 想走昇腾 NPU：CANN 工具链与 torch-npu 对应版本
- 预留磁盘空间放预训练模型权重与训练产物

---

## 使用

本篇是操作整理，把「装、跑、避坑」按顺序讲清楚，命令与参数均来自上游仓库与官方文档站。

常用入口速查：

- 命令行转写：`wenet -m paraformer audio.wav`（`-m` 可换模型名，以 `wenet -h` 为准）
- 指定语言：`wenet --language chinese audio.wav`
- 用 GPU：`--device cuda`（**默认是 cpu，不给提示**）
- 看时间戳/置信度：`-t` / `--show_tokens_info`
- 强制对齐：`--align --label "已知文本"`
- Python 接口：`wenet.load_model('paraformer')` 后反复调用 `model.transcribe('audio.wav')`
- 训练与部署：仓库配方 + `runtime/` 下的编译说明

完整的六块内容（用与不用、安装、常用操作、常见坑、权限与用途、能力边界）见 `SKILL.md`。

---

## 依赖

- torch、torchaudio：pip 安装会拉 `torch>=1.13.0` 且不设上限，需自行确认与驱动匹配（上游训练环境推荐 2.2.2+cu121）
- 包元数据列出的其他依赖：numpy、requests、tqdm、openai-whisper、librosa、pyyaml、jieba、sentencepiece、langid
- Windows 上额外需要 PySoundFile
- sox：音频读写依赖
- 可选：CUDA 12.1 运行时（训练）、CANN + torch-npu（昇腾 NPU）、cmake 3.14+（编译运行时）
- 无账号、无 API Key（使用公开预训练模型时）

---

## 安全

- 不内嵌任何密钥
- 首次运行会联网下载预训练模型权重，走内网或离线环境时需提前把权重放到约定位置
- 音频与转写文本默认只在本机流转，但若你把音频放在对象存储、或把服务暴露到公网，需自行加鉴权与访问控制
- 处理他人录音、会议内容、客服通话等敏感音频时，遵守所在地区的数据合规与隐私要求
- 训练任务会长时间占用显卡并写大量日志，注意磁盘与显存配额，避免影响同机其他服务
- 从代码仓库安装意味着跟随上游主分支变化，生产环境请固定到具体 commit 或 tag

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`wenet`
- 仓库：https://github.com/wenet-e2e/wenet

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
