# 三剪客 · 中文 NLP 与 LLM 全流程工具库 Skill

PaddleNLP：中文 NLP 与 LLM 全流程工具库 的安装、常用命令与避坑要点

---

## 前置条件

- **Python 环境**：安装文档的 conda 示例用 Python 3.9；Taskflow 文档标注的最低要求是 python ≥ 3.6。建议 3.9 或 3.10，并放在独立虚拟环境或 conda 环境里，避免与系统里其它深度学习框架互相污染。
- **先装飞桨框架，再装本库**。官方安装文档假设环境里已有 `paddlepaddle` 或 `paddlepaddle-gpu`，且版本大于或等于 3.0。顺序反了会在导入阶段就报错。
- **硬件与 wheel 匹配**。用 GPU 就要装 `paddlepaddle-gpu` 且 CUDA 版本与显卡驱动匹配；具体命令到飞桨官网安装页按自己的环境生成，不要照抄别人的版本号。
- **网络**：首次调用 `Taskflow` 或首次 `from_pretrained` 会联网下载模型权重，需要能访问权重源。完全离线的环境要提前把权重放到本地。
- **磁盘**：飞桨框架本身数百 MB 到数 GB，各任务权重从几十 MB 到数百 MB；大模型场景的权重与优化器状态可达数十 GB。

---

## 使用

最短上手路径如下，完整内容见 `SKILL.md`。

**1）验证环境**

```bash
python -c "import paddle, paddlenlp; print(paddle.__version__, paddlenlp.__version__)"
```

两者都能打印版本号且不报错，才算装好。

**2）跑一个开箱即用的中文任务**

```python
from paddlenlp import Taskflow

ner = Taskflow("ner")
print(ner("第十四届全运会在西安举办"))
```

第一次运行会下载该任务的模型权重，耗时属于正常现象。

**3）做信息抽取要带 schema**

```python
from paddlenlp import Taskflow

schema = {"产品": ["品牌", "型号"]}
ie = Taskflow("information_extraction", schema=schema)
print(ie("这款手机外观漂亮，价格也合适。"))
```

**4）加载中文预训练模型做微调**：用 `paddlenlp.transformers.<模型>Tokenizer.from_pretrained(...)` 配合对应的 `...ForSequenceClassification` 等任务头类。

**5）大模型链路**（预训练 / 精调 / DPO / RLHF / 融合 / 量化 / 推理部署）在仓库里有独立子工程与官方文档，命令随模型与硬件变化，以对应文档章节为准。

---

## 依赖

- **必需**：`paddlepaddle` 或 `paddlepaddle-gpu`（文档假设版本 ≥ 3.0）、`paddlenlp` 本体
- **可选**：conda / miniconda（管理环境）、Docker（隔离体验）、大模型链路的量化与推理相关组件
- **安装方式**：pip（可锁版本或装开发版）、飞桨官方 wheel 源、源码安装（克隆仓库后按根目录说明操作）
- **不需要**：任何 API Key 或云账号，推理与训练都在本地完成

---

## 安全

- 不内嵌任何密钥，也不要求填写任何账号信息
- 全部推理在本地完成，待处理的文本默认不会离开你的机器；唯一的对外网络行为是安装依赖与下载模型权重
- 如果按项目的部署方案把推理服务暴露到网络上，请自行加鉴权与访问控制——库本身不提供对外服务的认证层
- 首次运行会向模型权重源发起请求，内网环境请先确认出网策略与合规要求
- 模型可能生成或标注出错误内容，涉及对外发布或合规判定的场景必须人工复核

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`PaddleNLP`
- 仓库：https://github.com/PaddlePaddle/PaddleNLP

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
