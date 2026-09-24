# 三剪客 · 说话人分离转写 Skill

把多人对话音频转成「谁在什么时候说了什么」：人声分离 + 语音识别 + 说话人分离 + 时间戳对齐，产出带说话人标签的文稿与字幕。

---

## 前置条件

- **Python >= 3.10**（3.9 也能用，但需要手工逐个装依赖，官方不推荐）。
- **Cython 必须先装**，它是安装其余依赖的前置条件。
- **FFMPEG 必须安装且能从命令行调用**，否则无法解码音频。
- 安装依赖时要带约束文件：`pip install -c constraints.txt -r requirements.txt`，它负责把 numpy 等卡在兼容区间。
- 安装过程需要网络：依赖里有若干来自 Git 仓库的包，模型权重也在首次运行时下载。
- 建议有 GPU。默认设备在检测到 GPU 时用 `cuda`；并行脚本官方建议显存 >= 10GB。
- 不需要账号或 API Key。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
python diarize.py -a AUDIO_FILE_NAME
```

输出落在输入音频同目录、同主文件名下：`.txt`（带说话人前缀的文稿）和 `.srt`（带说话人标签的字幕）。

显存充足、想缩短总耗时（官方标注为实验性）：

```bash
python diarize_parallel.py -a AUDIO_FILE_NAME
```

参数名与默认值以 `python diarize.py --help` / `python diarize_parallel.py --help` 和上游仓库当前内容为准；两个脚本的默认参数并不一致。

---

## 依赖

- 系统级：**FFMPEG**（必需）
- Python 包：**Cython**（安装前置），随后按 `constraints.txt` + `requirements.txt` 安装
- `requirements.txt` 主要内容：语音/说话人分离的重型工具包（`nemo_toolkit[asr]`）、`faster-whisper`、`nltk`，以及三个从 Git 安装的包（人声分离、标点恢复、强制对齐）
- `constraints.txt`：把 `numpy` 限制在 2.0 以下，并额外固定一个来自 Git 的依赖
- 模型权重：首次运行时下载，不在仓库内
- 可选：无。没有需要额外采购的服务

---

## 安全

- 不内嵌任何密钥
- 全程离线本地推理：音频不会被上传到任何第三方转写服务，适合处理会议、访谈等敏感录音；但请注意**首次运行会联网下载模型权重**
- 依赖里有多个直接指向 Git 仓库的包（而非固定版本的发布包），安装时应确认来源可信、必要时锁定到具体提交
- 输出的 `.txt` 与 `.srt` 会与输入音频放在同一目录，内容包含完整对话记录；批处理前确认目录权限与共享范围
- 运行期间会在**当前工作目录**创建 `temp_outputs_<pid>` 临时目录存放人声分离的中间文件（含分离出的人声），正常结束时清理；进程被强杀会残留，需手工删除
- 依赖链较重且包含 GPU 工具包，建议在隔离环境或容器中安装，避免污染既有 Python 环境
- 输出为带 BOM 的 UTF-8；程序化读取时按 `utf-8-sig` 解码

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`whisper-diarization`
- 仓库：https://github.com/MahmoudAshraf97/whisper-diarization

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
