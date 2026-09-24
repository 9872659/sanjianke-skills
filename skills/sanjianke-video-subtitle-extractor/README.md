# 三剪客 · 视频硬字幕提取成 SRT Skill

video-subtitle-extractor：视频硬字幕提取成 SRT 的安装、常用命令与避坑要点

---

## 前置条件

- **Python 3.12+**，并且必须使用虚拟环境（官方要求），避免与系统环境冲突。
- 视频路径与程序路径必须是**纯英文、无空格**。官方用加粗加感叹号强调过：含中文或空格可能出现未知错误。
- 按硬件选一条加速路径：NVIDIA 显卡走 CUDA（官方推荐 CUDA 11.8 + cuDNN 8.6.0）；AMD/Intel 或 NVIDIA 50 系走 DirectML；macOS/AMD ROCm 走 ONNX（官方标注未测试）；无显卡走 CPU。
- 要先装对应版本的 PaddlePaddle（GPU 版或 CPU 版），再装 `requirements.txt` 里的依赖。
- 首次运行需要能下载 OCR 模型权重。
- **先试官方打包好的压缩包**。官方建议：直接下载解压运行，跑不通再走源码安装。

---

## 使用

拿到这个 Skill 后，Agent 会按这套顺序干活：

1. **先判断该不该用**。字幕必须是**烧进画面**的硬字幕；内嵌字幕轨请改用 ffmpeg 直接抽，不要过 OCR。
2. **确认环境**：Python ≥ 3.12、虚拟环境已激活、路径无中文和空格、加速路径与硬件匹配。
3. **先试打包版**，省掉一整套环境安装。
4. **跑单文件**：`python gui.py`，点【打开】选**单个**视频 → 调整字幕区域 → 点【运行】。命令行版是 `python ./backend/main.py`，按提示交互式输入视频路径与 `ymin ymax xmin xmax` 区域。
5. **按需调优**：优先快速/自动模式；台标水印混进来就用 `backend/configs/typoMap.json` 删掉。
6. **校验结果**：抽查时间轴、丢轴情况与错别字，再决定要不要切精准模式或批量跑。

细节命令与完整避坑表见 `SKILL.md`。

---

## 依赖

- Python ≥ 3.12，虚拟环境。
- `paddlepaddle-gpu==3.3.1`（CUDA 11.8 源）或 `paddlepaddle==3.3.1`（CPU 源），按硬件二选一。
- CUDA / cuDNN：走 CUDA 路径时必需，官方推荐 CUDA 11.8 + cuDNN 8.6.0，50 系显卡需要 CUDA 12.8.0 及以上而当前 Paddle 尚未支持。
- `requirements.txt`；DirectML 路径另需 `requirements_directml.txt`；ONNX 路径需自备合适的 onnxruntime 后端依赖。
- 随包提供的外部字幕检测程序（按 Windows / macOS / Linux 分目录存放）。
- 网络：安装阶段与首次运行需要；**识别过程本身是本地 OCR，不调用任何在线识别服务**。

---

## 安全

- 不内嵌任何密钥，不需要任何账号或 API Key——这正是它相对在线 OCR 服务的核心差异。
- 处理过程会拉起外部字幕检测程序与 OCR 工作进程；这些进程随包提供，注意来源与完整性校验。
- 过程中会在源码目录上一级的 `output/<视频名>/` 下写入抽帧图片、`raw.txt`、`raw_vsf.srt` 等中间产物，跑完默认清理。**处理涉密素材前先确认这些中间产物的落点、清理策略与磁盘权限**——抽帧图片等于把画面复制了一份到磁盘上。
- 输出的 SRT 默认写在视频文件同目录下，注意不要把结果写到非预期位置。
- **版权与授权**：提取他人视频的字幕并在你的作品里使用，属于对原作品的再加工；能否使用与发布取决于你所在地区的法律与素材授权。本 Skill 只讲工具用法，不提供任何版权结论。
- 官方明确说明不支持 macOS 上的 ONNX 路径（未测试），别把它当成受支持的生产方案。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`video-subtitle-extractor`
- 仓库：https://github.com/YaoFANGUK/video-subtitle-extractor

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
