# 三剪客 · 文档智能解析工具箱 Skill

PDF-Extract-Kit：文档智能解析工具箱 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.10，官方推荐用 conda 建独立虚拟环境（依赖栈较重，不建议装进系统环境）
- 建议有 NVIDIA GPU；**表格识别模型只支持 GPU**，flash attention 需 Ampere 及更新架构
- 磁盘留出模型权重空间（多任务模型合计体量不小，以权重仓库文件列表为准）
- 能访问 HuggingFace 或 ModelScope 以下载权重（国内建议 ModelScope）
- 不需要账号或 API Key（公开权重可直接下载）

---

## 使用

```bash
conda create -n pdf-extract-kit-1.0 python=3.10 -y
conda activate pdf-extract-kit-1.0

git clone https://github.com/opendatalab/PDF-Extract-Kit.git
cd PDF-Extract-Kit

pip install -r requirements.txt        # GPU
# pip install -r requirements-cpu.txt  # 纯 CPU（表格识别仍不可用）
```

下载权重后，在**仓库根目录**按任务执行：

```bash
python scripts/layout_detection.py --config configs/layout_detection.yaml
python scripts/formula_detection.py --config configs/formula_detection.yaml
python scripts/formula_recognition.py --config configs/formula_recognition.yaml
python scripts/ocr.py --config configs/ocr.yaml
python scripts/table_parsing.py --config configs/table_parsing.yaml
```

结果与可视化图输出在各自的 `outputs/<任务名>/` 目录。

完整的「什么时候用 / 不用、安装、常用操作、常见坑、能力边界」见 `SKILL.md`。

---

## 依赖

| 依赖 | 是否必须 | 用途 |
|---|---|---|
| Python 3.10 | 必须 | 官方推荐版本 |
| PyMuPDF | 必须 | PDF 读取 |
| ultralytics >= 8.2.85 | 必须 | YOLO 系列（版面检测 / 公式检测） |
| doclayout-yolo == 0.0.2 | 必须 | 默认版面检测模型 |
| unimernet == 0.2.1 | 必须 | 公式识别 |
| paddlepaddle / paddlepaddle-gpu + paddleocr == 2.7.3 | 必须 | OCR |
| struct-eqtable | 必须 | 表格识别（仅 GPU） |
| omegaconf、matplotlib | 必须 | 配置解析与可视化 |
| lmdeploy | 可选 | 表格识别加速推理 |
| detectron2 | 按需 | 仅 LayoutLMv3 版面检测模型需要 |

---

## 安全

- 不内嵌任何密钥
- 模型权重从第三方仓库下载，注意校验来源与磁盘占用；离线环境需提前离线搬运
- 推理默认本地执行，不上传文档内容；但**文档本身可能含敏感信息**，注意输出目录的权限与留存
- 项目为 **AGPL-3.0**：对外提供网络服务也会触发开源义务，商用前先做合规评估
- 大批量推理注意显存与内存占用，避免 OOM 影响同机其它服务

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`PDF-Extract-Kit`
- 仓库：https://github.com/opendatalab/PDF-Extract-Kit

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
