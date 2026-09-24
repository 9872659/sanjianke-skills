# 三剪客 · 轻量多语言 OCR Skill

RapidOCR：轻量多语言 OCR 的安装、常用命令与避坑要点

---

## 前置条件

- Python 环境（官方安装页标注支持 3.6 至 3.12 区间，实际以官方文档为准）。
- 已安装 `rapidocr` 与至少一个推理引擎（默认 ONNX Runtime：`pip install rapidocr onnxruntime`）。
- 首次使用需要联网下载模型；离线环境请先执行 `rapidocr download_models`。
- 待识别的图片（PDF 需先转成图片）。

---

## 使用

把本目录作为 Skill 交给 Agent，Agent 会按 `SKILL.md` 中的示例组织识别脚本。
常见任务：

- 单图文字提取（含坐标与置信度）；
- 批量图片 OCR，输出文本或结构化结果；
- 切语种模型（日文 / 韩文 / 俄文 / 泰文等）；
- CPU / GPU 引擎切换与离线部署。

调试顺序建议：先 `rapidocr check`，再用 1~2 张样图定参数，最后跑批量。

---

## 依赖

- `rapidocr` Python 包。
- 推理引擎：`onnxruntime`（默认，CPU 版即可），或 openvino / paddle / torch / mnn / tensorrt。
- 间接依赖：opencv_python、numpy、Shapely、Pillow、omegaconf、PyYAML 等。
- 无云端账号、无 API Key。

---

## 安全

- 不内嵌任何密钥
- 识别全程在本地进行，图片不会上传到第三方 OCR 服务。
- 模型权重来自公开托管站，首次下载请校验来源可信。
- 处理含个人信息的图片时注意落盘位置与清理策略。
- OCR 结果可能包含识别错误，涉及金额、身份、法务的内容必须人工复核。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`RapidOCR`
- 仓库：https://github.com/RapidAI/RapidOCR

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
