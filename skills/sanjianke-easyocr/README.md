# 三剪客 · 多语言即用 OCR Skill

EasyOCR：多语言即用 OCR 的安装、常用命令与避坑要点

---

## 前置条件

- Python 环境（官方未给出版本下限，以实际安装为准）。
- PyTorch 与 torchvision：Windows 上必须先按官方指引安装并选对 CUDA 版本；纯 CPU 机器把 CUDA 选成 None。
- 首次使用某种语言时需要能下载模型权重，或提前把模型文件准备好。
- 有 GPU 更好；没有 GPU 时显式关掉即可运行。

---

## 使用

主体是 `SKILL.md`，建议按顺序读：

1. **什么时候用 / 不用** —— 图片文字提取、要坐标与置信度时用它；手写、版面结构、PDF 文档则不用。
2. **安装** —— pip 装法、Windows 的 PyTorch 前置步骤、仓库内的 Dockerfile 说明、依赖清单。
3. **常用操作** —— 最小示例、输出结构、多种输入形态、CPU 模式、段落聚合、字符集限定、旋转处理、命令行用法、离线部署。
4. **常见坑** —— 首次下载模型、torch 不匹配、默认开 GPU、语言列表、结果顺序、白名单与黑名单互斥等。

最短的一次调用：

```python
import easyocr

reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
print(reader.readtext('chinese.jpg', detail=0))
```

---

## 依赖

- `torch`、`torchvision>=0.5`（先装，且版本要与机器匹配）。
- `opencv-python-headless`、`scipy`、`numpy`、`Pillow`、`scikit-image`、`python-bidi`、`PyYAML`、`Shapely`、`pyclipper`、`ninja`（由 pip 自动带上）。
- 磁盘：torch 与各语言模型权重都占空间，多语言部署前先实测。
- 网络：首次运行按语言下载模型；离线环境用模型下载页手工准备。

---

## 安全

- 不内嵌任何密钥、Token 或 Cookie。
- 只读取用户指定的图片；识别结果默认只在内存里，是否落盘由调用方决定。
- 会写入模型权重到模型目录（默认 `~/.EasyOCR/`），生产环境建议显式指定 `model_storage_directory` 到受控路径。
- 处理敏感图片时注意：默认开启的模型自动下载需要联网，涉密环境请先用 `download_enabled=False` + 本地模型。
- 项目本体为 Apache 2.0；模型权重的许可与用途限制需自行确认。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`EasyOCR`
- 仓库：https://github.com/JaidedAI/EasyOCR

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
