# 三剪客 · CSV 处理 CLI 套件 Skill

用 14 个命令行工具把 CSV 转格式、筛行选列、排序合并、体检清洗，甚至不建库直接写 SQL 查询。

---

## 前置条件

- Python 3（官方支持 Linux / macOS / Windows 上非 EOL 的版本）
- `pip` 可用；官方建议装在虚拟环境里
- 需要读 `.zst` 压缩文件时额外装 `csvkit[zstandard]`
- 需要连 PostgreSQL / MySQL 时，另行安装对应数据库驱动
- 不需要账号或 API Key

---

## 使用

```bash
pip install csvkit

csvcut -n data.csv                    # 先看有哪些列
in2csv book.xlsx > data.csv           # Excel 转 CSV
csvstat data.csv                      # 看列级统计与行数
csvcut -c county,total_cost data.csv \
  | csvgrep -c county -m LANCASTER \
  | csvsort -c total_cost -r | csvlook    # 选列→筛行→排序→预览
csvsql --query "select * from joined where quantity > 5;" joined.csv   # 直接对 CSV 跑 SQL
```

`SKILL.md` 里有全部子命令的用法、通用参数说明与避坑表。

---

## 依赖

- 运行依赖：`csvkit`（含 agate、agate-excel、agate-dbf、agate-sql、sqlalchemy 等）
- 可选依赖：`csvkit[zstandard]`（读 `.zst`）；数据库驱动 `psycopg2` / `mysql-connector-python` / `mysqlclient`
- 不依赖外部二进制；纯 Python 实现
- 不需要账号、Key 或在线服务

---

## 安全

- 不内嵌任何密钥
- 本地 CSV 处理全程离线；只有你自己写的 `curl | in2csv` 管道才会联网
- 数据库连接串可能含用户名密码，建议使用密码文件（如 PostgreSQL 的 `.pgpass`）而非明文写在命令里
- `csvsql --db ... --insert` 会真实写库，执行前确认连接串与目标表名
- `csvformat` / 重定向会覆盖同名输出文件，注意备份源数据

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`csvkit`
- 仓库：https://github.com/wireservice/csvkit

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
