# 三剪客 · 高性能 DataFrame 计算库 Skill

比 pandas 更快、更省内存的 DataFrame 计算库，带惰性查询优化与流出式执行，能处理超过内存的数据集。

---

## 前置条件

- Python 环境（本文实测 Python 3.11.9）；官方支持的最低版本以官方安装文档为准。
- 有本地数据文件（CSV / Parquet / JSON 等）或已在内存里的数据需要处理。
- 想用 `to_pandas()` 过桥、或读取 Excel / 数据库 / 云存储时，需要额外安装对应的可选依赖。
- 不需要账号、Key 或注册；核心计算全程本地。

---

## 使用

1. 先判断数据量级：小数据用 `read_*` 即时读取最省心；大数据先走 `pl.scan_*` 或 `.lazy()`。
2. 惰性计划写完一定要 `.collect()`，不然拿到的是查询而不是结果；不确定时先 `.explain()` 看优化后的计划。
3. 内存吃紧或数据大于内存时，把收集方式改成 `collect(engine="streaming")`。
4. 变换用表达式写（`pl.col(...)`、`df.select(...)`、`df.filter(...)`、`df.with_columns(...)`），这些方法返回新的 DataFrame，记得接住返回值。
5. 要和别的库交换数据，用 `to_pandas()` / `to_arrow()` / `to_numpy()`；大结果集转换前先裁剪规模。
6. 要配合 Python `multiprocessing` 时，必须显式用 `get_context("spawn")`。

完整的六块说明（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| Python | `pip install polars` |
| 平台 | Windows / macOS / Linux |
| pandas（可选） | 只有 `to_pandas()` / `from_pandas()` 这类互操作才需要 |
| pyarrow / NumPy（可选） | Arrow、NumPy 互操作时使用 |
| 其它 optional extras | Excel、数据库、云存储、GPU 等按官方安装文档的 Feature flags 一节选择 |
| 网络 | 核心计算不需要；仅安装可选依赖或读取远端存储时需要 |

---

## 安全

- 不内嵌任何密钥。
- 默认在进程内本地计算，不起服务、不监听端口、不对外开放连接。
- 读取外部来源的数据文件时，注意数据本身的可信度；本 Skill 不代替数据合规审查。
- 用 `multiprocessing` 时务必用 `spawn`，避免多线程进程被 `fork` 带来的不安全状态。
- 从远端存储 / 数据库读数据时才需要凭证，请用环境变量或密钥管理工具注入，不要硬编码在脚本里。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`polars`
- 仓库：https://github.com/pola-rs/polars

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
