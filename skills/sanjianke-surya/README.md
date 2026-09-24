# 三剪客 · 版面分析与表格识别 Skill

surya：版面分析与表格识别 的安装、常用命令与避坑要点

---

## 前置条件

- Python 环境，能 `pip install surya-ocr`
- 一个跑得起来的推理后端，二选一：
  - NVIDIA GPU + Docker + NVIDIA Container Toolkit（走 vllm）
  - CPU / Apple Silicon 上的 `llama-server`（走 llama.cpp；macOS 可 `brew install llama.cpp`）
- 首次运行能联网下载模型权重，并预留磁盘空间

只用文字行检测（`surya_detect`）可以不要后端，它是独立的 torch 小模型。

---

## 使用

装好之后按需要选入口：

| 目标 | 命令 |
|---|---|
| 整页 OCR（文字 + 坐标 + HTML 片段） | `surya_ocr DATA_PATH` |
| 版面标签与阅读顺序 | `surya_layout DATA_PATH` |
| 表格行列与单元格 | `surya_table DATA_PATH` |
| 只要文字行坐标 | `surya_detect DATA_PATH` |
| 手动试效果 | `surya_gui` |

连着跑多条命令时用 `--keep_server` 复用同一个推理服务。详细参数、环境变量、
输出字段见 `SKILL.md` 与 `references/` 下两份速查。

---

## 依赖

- `surya-ocr`（Python 包）及它带的检测模型
- 版面 / OCR / 表格识别共用的 VLM 后端：vllm 或 llama.cpp
- 可选：`streamlit`、`pdftext`（只在用 `surya_gui` 时需要）

---

## 安全

- 不内嵌任何密钥
- 全程可以本地推理，文档不出本机；只有首次下载模型权重需要联网
- 会拉起本地推理服务进程或容器，`--keep_server` 时命令退出后仍在跑，用完请手动停掉
- 模型权重是修改版 OpenRAIL-M 许可，商业使用有规模门槛，落地前先确认适用范围

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`surya`
- 仓库：https://github.com/datalab-to/surya

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
