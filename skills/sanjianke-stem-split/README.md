# 三剪客 · 音乐分轨与人声提取 Skill

Demucs：音乐分轨与人声提取 的安装、常用命令与避坑要点

---

## 前置条件

- Python 环境。官方 README 写至少 3.8，但 PyPI 上 4.1.0 的包元数据要求 `>=3.10`，先确认你装得到的版本再定解释器。
- 想用 GPU 加速的话，显卡显存至少 3GB；官方给的账是默认参数下约需 7GB。
- Windows 用户：官方要求把文档里的 `python3` 换成 `python.exe`，并在 Anaconda 控制台里执行命令。
- 素材路径不要带空格；带了就整体加引号。
- 首次运行某个模型需要能访问权重下载源，或提前把权重准备好。
- **心理准备**：上游原仓库已停止维护，官方 README 明确说不接受功能请求。要用于生产就得接受「不会再有上游支持」这个前提。

---

## 使用

拿到这个 Skill 后，Agent 会按这套顺序干活：

1. **先判断该不该用**。素材必须是音乐混音；要实时、要转写文字、要认人，都不该用它。
2. **确认环境**：Python 版本、显存档位、`demucs` 命令是否可用（不可用就改 `python -m demucs`）。
3. **跑最小示例**：`demucs 一首短歌.mp3`，确认 `separated/<模型名>/<曲名>/` 下出现四路音轨。
4. **按目标选模式**：要伴奏就 `--two-stems=vocals`；要四轨就默认；要更高质量换 `-n`。
5. **按显存调参**：不够就先降 `--segment`，再 `PYTORCH_NO_CUDA_MEMORY_CACHING=1`，最后 `-d cpu`。
6. **校验结果**：逐轨试听，检查串音与轨间音量比例，再决定是否批量跑。

细节命令与完整避坑表见 `SKILL.md`。

---

## 依赖

- Python 包：`demucs`（`python3 -m pip install -U demucs`，Windows 用 `python -m pip`）。
- 运行时依赖（4.1.0 包元数据）：`einops`、`huggingface-hub`、`julius`、`lameenc`、`pyyaml`、`safetensors`、`sphn`、`torch`、`tqdm`；macOS x86_64 另有 `numpy<2`、`torch<2.3,>=2.1` 约束。
- 训练相关（`train` extra，只做分离不需要）：`dora-search`、`hydra-core`、`hydra-colorlog`、`musdb`、`museval`、`submitit`、`treetable`、`torchaudio`；量化模型另需 `diffq`。
- 音高/速度增强要 `soundstretch`/`soundtouch`（仅训练用）。
- Windows 上音频读取依赖 `ffmpeg`（`torchaudio` 在 Windows 支持有限）。
- 网络：首次使用某个模型需要下载权重。

---

## 安全

- 不内嵌任何密钥，也不需要任何账号或 API Key。
- 分离过程完全本地运行，不上传音频。
- 处理前确认显存与内存：`-j` 会按倍数放大内存占用，小机器上开大值可能把系统拖死。
- 输出目录默认为当前工作目录下的 `separated/`，会写入与原文件同量级甚至更大的音频文件，先确认磁盘空间。
- **版权与授权**：分离他人音乐属于对原作品的再加工，能不能做、能不能发布取决于你所在地区的法律与素材授权。本 Skill 只讲工具用法，不提供任何版权结论。
- **维护风险**：上游原仓库已停止维护，供应链上没有上游修复承诺。生产使用建议锁定版本并把代码与模型权重自行归档。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Demucs`
- 仓库：https://github.com/facebookresearch/demucs

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
