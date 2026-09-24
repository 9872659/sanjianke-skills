# 三剪客 · 中文 OCR 与版面分析 Skill

中文 OCR 首选工具：一行命令识别文字，或把整页复杂版面拆成标题、正文、表格、公式，输出可检索的 Markdown / JSON。支持纯 CPU、GPU、ONNX、Transformer 多种推理后端。

---

## 前置条件

- Python 3.8~3.12，建议独立虚拟环境。
- 先装 PaddlePaddle 框架，再装 paddleocr（默认本地推理引擎依赖它）。
- 要版面解析 / 表格 / 公式能力，必须装 `"paddleocr[all]"` 而不是基础版。
- 首次运行会下载模型权重，需要网络和足够磁盘空间。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install paddlepaddle
pip install "paddleocr[all]"

# 通用 OCR
paddleocr ocr -i ./general_ocr_002.png --save_path ./output --device cpu

# 版面解析，导出结构化结果
paddleocr pp_structurev3 -i ./pp_structure_v3_demo.png --device cpu
```

Python 里取结构化结果：

```python
from paddleocr import PPStructureV3

pipeline = PPStructureV3()
for res in pipeline.predict("./pp_structure_v3_demo.png"):
    res.save_to_json(save_path="output")
    res.save_to_markdown(save_path="output")
```

模型名、`lang` 取值与 CLI 参数随后续版本变动，执行前以 `paddleocr --help` 和官方文档当前内容为准。

---

## 依赖

- Python 3.8~3.12
- PaddlePaddle（CPU 版或对应 CUDA 的 GPU 版）
- `paddleocr`（基础版）或 `paddleocr[all]`（完整版）
- 可选推理引擎：transformers、onnxruntime（另有 OpenVINO / TensorRT 等高性能推理路径）
- 网络与磁盘：模型权重下载

---

## 安全

- 不内嵌任何密钥
- 本地推理不联网（除首次下载模型外），文档不出机器
- 若把模型下载源指向第三方镜像，注意来源可信度
- 服务化部署（HTTP / Docker）时须自行加访问控制，不要裸暴露到公网

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`PaddleOCR`
- 仓库：https://github.com/PaddlePaddle/PaddleOCR

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
