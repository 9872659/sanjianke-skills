# 三剪客 · 中文文本纠错工具箱 Skill

pycorrector：中文文本纠错工具箱 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.6 及以上（PyPI 元数据口径）；仓库自述练习环境为 3.8 及以上
- 决定走哪条模型路线：统计语言模型（CPU 可跑）/ BERT 类 / T5 / ERNIE / BART / 大模型路线
- 统计模型路线需要预先准备好中文语言模型文件，或允许首次运行联网自动下载（体积较大）
- 深度学习路线需要额外装 torch、transformers 或 PaddlePaddle；大模型路线建议有 NVIDIA 显卡
- 准备好业务侧的专名词典与混淆集，否则专名容易被误改
- 待处理文本统一为 UTF-8 编码

---

## 使用

本篇是操作整理，把「装、跑、避坑」按顺序讲清楚，命令、类名与参数均来自上游仓库自己的说明。

常用入口速查：

- 建对象：`Corrector()`（统计模型，CPU）、`MacBertCorrector(...)`、`T5Corrector()`、`ErnieCscCorrector()` 等
- 纠错：`m.correct(句子)` 返回 dict；`m.correct_batch([句子, ...])` 返回 list
- 只检测：`m.detect(句子)`，返回错误词与起止下标
- 自定义：`Corrector(proper_name_path=...)`、`Corrector(custom_confusion_path_or_dict=...)`
- 换模型：`Corrector(language_model_path='...klm')`
- 命令行：`python -m pycorrector input.txt -o out.txt -n -d`（参数以本地 `-h` 为准）
- 附带能力：`pycorrector.traditional2simplified(...)`、`pycorrector.simplified2traditional(...)`、`EnSpellCorrector()`

完整的六块内容（用与不用、安装、常用操作、常见坑、权限与用途、能力边界）见 `SKILL.md`。

---

## 依赖

- pip 主包的依赖以仓库 `requirements.txt` 为准
- 统计模型路线：中文 KenLM 语言模型文件，外加该路线的运行依赖
- BERT 类路线（如 MacBERT）：PyTorch + transformers，并需下载对应权重
- ERNIE 路线：PaddlePaddle
- BART 路线（ModelScope 版）：modelscope 与 fairseq 的指定版本（仓库有明确版本口径）
- 大模型路线：对应开源权重的下载与显存
- 无强制账号或 Key；模型默认缓存在用户主目录下的模型目录中

---

## 安全

- 不内嵌任何密钥
- 纯本地推理不上传文本；只有首次自动下载模型文件时会联网
- 首次运行会自动往用户主目录写模型缓存，共享机器上注意目录权限与占用空间
- 纠错结果可能误杀专名，任何对外发布前都要保留人工抽检环节
- 处理客户文本、聊天记录等敏感语料时，遵守所在地区的数据合规要求，不要把语料写进公开仓库

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pycorrector`
- 仓库：https://github.com/shibing624/pycorrector

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
