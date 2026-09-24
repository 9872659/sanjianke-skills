# 三剪客 · 图谱增强检索 Skill

GraphRAG：图谱增强检索 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.10–3.12，建议单独建虚拟环境（3.13 不在支持范围）。
- 一个可用的 chat 模型接口与一个 embedding 模型接口，并留出足够额度。
- 待处理的语料已整理成文本文件，准备放进工作区的 `input/` 目录。
- 已规划成本上限：索引阶段会反复调用模型，语料越大花费越高。
- 磁盘留有空间，索引产物是多张 parquet 表加 LLM 缓存。
- 能长时间运行的机器或后台任务环境，索引可能跑很久。

---

## 使用

把本目录作为 Skill 交给 Agent，或直接对照 `SKILL.md` 操作。典型流程：

1. 建目录、建虚拟环境、`pip install graphrag`。
2. `graphrag init` 生成 `.env`、`settings.yaml` 与 `input/`。
3. 把语料放进 `input/`，在 `.env` 里填好 Key。
4. `graphrag index --dry-run` 先校验配置，再用 `--method fast` 拿小样本试效果。
5. 效果可接受后跑全量 `graphrag index`。
6. 宏观问题用默认的 global，实体关系问题加 `--method local`。
7. 效果不满意时先 `graphrag prompt-tune` 调提示词，而不是先换模型。

命令与参数以 `graphrag --help` 及各子命令 `--help` 为准；本 Skill 记录的是常用路径与已知坑位。

---

## 依赖

- `graphrag` 本体及其 Python 依赖。
- 外部 chat 模型与 embedding 模型接口（OpenAI 或 Azure 风格）。
- 读取 parquet 需要额外工具（如 pandas）才能查看索引产物。
- 无需向量数据库，索引与检索自包含在工作区目录里。

---

## 安全

- 不内嵌任何密钥
- `.env` 里的 `GRAPHRAG_API_KEY` 必须加入忽略规则，不要提交进版本库或打进镜像。
- 索引前确认语料的使用授权；把内部文档送进外部模型接口属于数据出域行为。
- 索引产物含原文语义摘要，落盘目录按同等密级管理。
- `graphrag init --force` 会覆盖 `settings.yaml` 与提示词文件，执行前先备份。
- 问答结果是模型生成内容，涉及对外发布前必须人工复核。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`GraphRAG`
- 仓库：https://github.com/microsoft/graphrag

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
