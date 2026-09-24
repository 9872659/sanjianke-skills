# 三剪客 · 单机分析型 SQL 引擎 Skill

把 CSV / Parquet 等表格文件当数据库查，用 SQL 做单机分析、清洗与导出，不用起服务、不用先导入。

---

## 前置条件

- **走 CLI**：下载 DuckDB 的单文件可执行客户端（Windows / macOS / Linux 都有预编译版），解压即用，无需其他运行时。下载入口见 https://duckdb.org/install/ 的 CLI 页签。
- **走 Python**：官方要求 Python 3.9 或更新。本文实测环境为 Python 3.11.9 + `duckdb` 1.5.5（Windows）。
- 需要在命令行里用，就装 CLI；需要在脚本里用，就装 Python 包。两者是各自独立的安装物。
- 若要读取 Excel 等额外格式或访问远端存储，需要能联网下载扩展；本地查 CSV / Parquet 不需要网络。
- 不需要账号、Key 或注册。

---

## 使用

1. 先确认要分析的东西在哪：文件路径、分隔符、有没有表头。用 `SELECT * FROM 'xxx.csv' LIMIT 5;` 探一下最快。
2. 想清楚这次是「查文件」还是「开已有的库文件」——命令行里多写一个文件名就会创建 / 打开持久化库。
3. 按需选入口：
   - 一次性跑一条 SQL：`duckdb -c "SELECT ..."`（跑完即退，适合脚本）。
   - 交互式探索：直接 `duckdb` 进内存库，或 `duckdb my_database.duckdb` 开持久库。
   - Python 里集成：`import duckdb` 后用 `duckdb.sql(...)` 或 `duckdb.connect()`。
4. 结果要交出去就用 `COPY ... TO ...` 导出成 CSV / Parquet，别在终端里截屏抄数。
5. 只读场景给库文件加 `-readonly`，避免误写。

完整的六块说明（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| 平台 | Windows / macOS / Linux |
| CLI | 官方预编译单文件可执行程序，无额外运行时依赖 |
| Python | 3.9+；`pip install duckdb`，也支持 `conda install python-duckdb -c conda-forge` |
| pandas（可选） | 只有用 `.df()` / `fetchdf()` 这类转 DataFrame 的方法才需要；它不是 DuckDB 的默认依赖，缺了会在调用时报错 |
| pyarrow（可选） | 需要 Arrow 格式输出时使用 |
| 网络（部分场景） | 仅安装扩展时需要；本地文件分析与本地库读写不需要 |

---

## 安全

- 不内嵌任何密钥。
- 默认在本地进程内运行，不起服务、不监听端口、不对外开放连接。
- 打开不受信任来源的数据库文件时建议用 `-readonly`，避免意外写入或改动原文件。
- `-unsigned` 会允许加载未签名扩展，官方定位是给扩展开发者调试用，生产环境不要随手加。
- 扩展默认从官方仓库下载；在离线或内网环境请按官方文档走离线安装，不要把扩展下载地址随意替换成第三方镜像。
- 用 SQL 处理来自网络的原始数据时，注意数据本身的可信度；本 Skill 不代替数据合规审查。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`duckdb`
- 仓库：https://github.com/duckdb/duckdb

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
