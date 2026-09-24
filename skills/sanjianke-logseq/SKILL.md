---
name: sanjianke-logseq
slug: sanjianke-logseq
displayName: 三剪客 · Logseq 大纲双链笔记
description: "Logseq：以大纲和双向链接为核心的知识管理工具，笔记就是本地 Markdown 文件，还带一个能直接读写图库的命令行。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Logseq：以大纲和双向链接为核心的知识管理工具，笔记就是本地 Markdown 文件，还带一个能直接读写图库的命令行。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · Logseq 大纲双链笔记

Logseq 用大纲结构记笔记：每条都是节点，可以折叠、可以互相引用，页面和块之间自动长出反向链接。笔记存在本地，Git 能管、别的编辑器能开。

它真正特别的地方是有**两种图库形态**。一种是大家熟的文件版，笔记就是本地 Markdown / Org 文件，所见即所得。另一种是数据库版，数据落在本地 SQLite 里，支持属性、查询和一套命令行工具。两者不要混着理解，命令和文件布局都不一样。

这个 Skill 把两条路都写清楚：用命令行批量读写、备份、导出，全部是针对**数据库版**的；如果你用的是文件版，就按本地 Markdown 文件来管，别指望命令行能操作它。

**上游项目**：`Logseq`　**仓库**：https://github.com/logseq/logseq

## 什么时候用 / 不用

**用它**：

- 「我要按大纲整理思路」，需要能随时折叠、拖拽、把一段提到别处还能自动更新引用。
- 「笔记要能被我自己的脚本读写」——数据库版提供命令行，能建页面、写块、查询、导出。
- 「笔记要存在本地、用 Git 管版本」，不接受锁在某个云服务里。
- 「要把 PDF 和笔记放在一起做批注」，然后在笔记里引用批注内容。
- 「需要定期自动备份图库」——命令行有专门的备份子命令，可挂进定时任务。

**不要用它**：

- 想要「像 Word 一样的连续长文档」排版体验——它是大纲结构，长文写作和排版不是它的强项。
- 用的是文件版却想用命令行批量改内容——命令行只面向数据库版；文件版直接编辑 Markdown 文件即可。
- 生产性资料、不能丢的数据，却打算直接上数据库版——数据库版目前仍是 beta，官方明确提示存在数据丢失可能。
- 需要多人实时协作编辑同一份笔记，且要求成熟的冲突处理——协作能力还在推进中，别当成熟产品用。
- 团队要的是「有权限体系、有审计、有 SSO 的知识库」——那是另一种形态的产品，应该评估面向团队的知识库平台而不是个人笔记工具。

## 安装

**桌面端**：从官方仓库的 Releases 页面下载对应系统的安装包，装完打开即可。

**Linux 一键安装脚本**（官方 README 提供）：

```bash
# 最新版
curl -fsSL https://raw.githubusercontent.com/logseq/logseq/master/scripts/install-linux.sh | bash

# 指定版本（版本号以官方 Releases 为准，不要照抄示例值）
curl -fsSL https://raw.githubusercontent.com/logseq/logseq/master/scripts/install-linux.sh | bash -s -- <版本号>

# 无需 root 的用户级安装
curl -fsSL https://raw.githubusercontent.com/logseq/logseq/master/scripts/install-linux.sh | bash -s -- --user
```

**数据库版**：可以直接用网页版 `https://app.logseq.com/` 试；桌面版从官方 nightly 发布页下载对应平台的构建产物；想追最新开发状态则从源码构建，**稳定分支与主分支的取舍以官方 README 的说明为准**。

**命令行**（随数据库版提供，二进制名是 `logseq`）。从源码构建出运行产物后本地调用，或者 link 成全局命令：

```bash
# 直接跑本地构建产物
node ./dist/logseq.js graph list

# 让它变成全局可用的 logseq 命令
npm link
logseq graph list
```

命令行会自动拉起并管理它依赖的本地后台服务，**不要自己去手动启动那个服务**。

## 常用操作

命令行默认把图库和配置放在 `~/logseq` 下：图库数据在 `<root-dir>/graphs`，配置文件是 `<root-dir>/cli.edn`。全局参数 `--root-dir`、`--graph`、`--output` 分别覆盖配置里的根目录、当前图库和输出格式；**命令行参数 > 环境变量 > 配置文件**。

```bash
# 1. 列出所有数据库版图库
logseq graph list

# 2. 新建一个图库并切过去
logseq graph create --graph demo

# 3. 往某个页面写一条块（不给目标就落到今天的日志页）
logseq upsert block --target-page TestPage --content "hello world"

# 4. 搜块、搜页面
logseq search block --content "关键词"
logseq search page --content "关键词"

# 5. 看页面内容树，结构化输出便于接脚本
logseq show --page TestPage --output json

# 6. 图库导出与备份
logseq graph export --type edn --file /tmp/demo.edn --graph demo
logseq graph backup create --graph demo --name nightly
logseq graph backup list
```

维护类命令：

```bash
# 跑运行时诊断（运行产物、根目录权限、后台服务就绪度）
logseq doctor

# 看后台服务列表（human 输出带 OWNER 和 REVISION 两列）
logseq server list

# 重启某个图库的后台服务
logseq server restart --graph demo

# 初始化命令补全（zsh / bash）
eval "$(logseq completion bash)"
```

查询与结构化输出：`logseq query --query <edn>` 跑 Datalog 查询，`logseq query list` 看内置的具名查询（官方文档提到的内置集包含 `block-search`、`task-search`、`recent-updated`、`list-status`、`list-priority`）。输出格式全局用 `--output human|json|edn`，脚本里建议固定成 `json`。**每个子命令的具体参数以 `logseq <子命令> --help` 和官方 CLI 文档为准**。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 数据库版用着用着数据出问题 | 数据库版目前仍是 beta，官方明确提示可能发生数据丢失 | 挂上自动备份或定期做 SQLite 图库备份，别把关键资料只放在一个测试图库里 |
| 升级 CLI 之后原来设的自定义路径全失效了 | 配置位置迁移过：老的 `~/.logseq/cli-graphs` 和 `~/.logseq/cli.edn` 不再被默认读取 | 用 `--root-dir` 和 / 或 `--config` 指回原来的位置 |
| 图库数据目录里出现了 `logseq_db_` 开头的名字，命令按名字找不到图库 | 图库目录名是面向用户的（例如 `demo`），不该带前缀 | 用 `graph list` 拿到的真实名字去调命令，不要自己拼目录名 |
| 命令行报「图库已存在」或「图库不存在」 | 不同子命令的前置检查不一致：SQLite 导入要求新图库，EDN 导入和备份恢复不要求；除建图库外，目标图库不存在都会直接报不存在 | 动手前先 `graph list` / `graph info` 确认真实状态，别靠猜 |
| `server stop` / `server restart` 报服务被别的所有者占用 | 后台服务带所有者标记，命令行只能停停自己启动的（或标记为未知来源的） | 用 `server list` 看 `OWNER` 列；确需处理时走 `server cleanup` 这个手动维护命令 |
| 命令行输出里某些字段不见了或名字对不上 | JSON 输出的键做过一次从扁平到带命名空间的迁移（例如旧的 `title` 变成 `block/title`，`id` 变成 `db/id`） | 写解析逻辑前先按当前版本实际输出对一遍键名，不要沿用旧文档里的扁平键 |
| 结构化输出模式下同步进度条不出现 | 结构化输出默认自动关掉进度流 | 确实需要进度就显式加 `--progress true`；`--progress false` 则始终抑制 |
| 同步相关的命令报找不到加密密码 | 加密图库的密码要在同步流程里提供并持久化，配置项里的旧字段会被静默忽略 | 在 `sync start` / `sync download` 时用 `--e2ee-password` 提供一次 |
| 图库备份恢复之后发现少了东西 | 备份只复制 `db.sqlite`，另外两个辅助数据库是有意排除的 | 需要完整快照时用导出功能，别只依赖备份目录 |
| 把笔记目录塞进第三方同步盘（网盘 / iCloud 之类） | 多个客户端并发改写同一批数据，容易把图库写坏 | 用官方同步能力，或用 Git 这类显式提交的版本管理；不要用自动同步盘 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 下载安装包与发布产物；使用同步与团队协作能力时连云端；登录时打开浏览器完成授权回调 |
| 读取文件 | 是 | 读取 `<root-dir>/graphs` 下的图库数据、`cli.edn` 配置、`auth.json` 登录态、素材与附件文件 |
| 写入文件 | 是 | 创建与修改图库数据、写备份快照、写导出文件、写登录态与本地密钥存储、命令行工作目录下的技能文件 |
| 凭证 | 是 | 云端登录后的 token（存于 `~/logseq/auth.json`，含 id / access / refresh 三类 token）；加密图库的密码；节点运行时优先放系统钥匙串，失败时回落到本地 KV 文件。**都按密钥对待，不要提交进仓库** |
| 子进程 / 后台常驻 | 是 | 命令行会按需拉起并管理本地后台服务进程，并读写锁文件；桌面端本身也是常驻应用 |

## 触发场景

- 「帮我把这批内容按页写进 Logseq 的数据库版图库。」
- 「我想在 Logseq 里搜一下哪些块提到过这个词。」
- 「把图库导出一份 EDN / SQLite 快照，我要做长期归档。」
- 「怎么给 Logseq 图库加自动备份？」
- 「命令行报图库不存在，但我明明建过，怎么排查？」
- 「升级之后我自定义的图库路径丢了，怎么找回来？」

## 能力边界

**覆盖**：

- 两种图库形态的区别与各自的正确用法：文件版按本地文件管，数据库版走命令行。
- 安装路径：桌面端安装包、Linux 安装脚本、网页版试用、从源码构建、命令行 link。
- 命令行能力：图库清单与增删切换、页面与块的增改移删、标签与属性、素材、搜索与 Datalog 查询、内容树展示、导入导出、备份与恢复、同步、服务与诊断、命令补全。
- 命令行配置模型：根目录、当前图库、输出格式三者的优先级与对应环境变量。
- 结构化输出：human / json / edn 三种模式的选择与键名约定。
- 常见故障定位方向：图库不存在、服务所有权冲突、配置迁移、备份范围、同步密码。

**不覆盖**：

- 图形界面里的具体操作路径、快捷键与主题配置。
- 文件版图库的批量编辑——那直接按本地 Markdown / Org 文件处理即可，不走命令行。
- 插件与主题的开发（有独立的插件接口文档站）。
- 云同步服务的账号开通、套餐与团队权限管理。
- 多人实时协作的冲突合并策略细节。
- 替你把关数据安全——数据库版处于 beta，是否需要它由你按数据重要性判断。

## 依赖条件

- 桌面端：Windows / macOS / Linux；移动端另有应用，覆盖大部分桌面能力。
- 网页版：现代浏览器，访问 `https://app.logseq.com/`。
- 命令行：需要 Node.js 运行时，以及从源码构建出的命令行运行产物。
- 默认目录布局：`<root-dir>` 默认 `~/logseq`，图库在 `<root-dir>/graphs`，配置在 `<root-dir>/cli.edn`，登录态在 `~/logseq/auth.json`。
- 可选：Logseq 云端账号（同步与协作）、系统钥匙串（存加密图库密码）。

## 已知限制

- 数据库版仍在 beta，移动端应用与实时协作处于更早的阶段，官方提示存在数据丢失可能。
- 图库备份只复制 `db.sqlite`，不含辅助数据库，不能当成完整快照。
- 结构化的 JSON 输出键名经历过命名空间化迁移，跨版本写死的解析逻辑会失效。
- 后台服务带所有者语义，命令行的停止 / 重启只对它有权限的服务生效。
- 命令行默认读取新的配置位置，老路径需要显式传参才能继续用。
- 命令行与桌面端共用图库时依赖同一套锁文件协议，版本不一致会出现修订号不匹配。

## 自检清单

执行前：

- [ ] 先确认用的是文件版还是数据库版；命令行只对数据库版有效。
- [ ] 用 `logseq graph list` 确认真实图库名，不要自己拼目录名。
- [ ] 明确 `<root-dir>` 和 `--config` 指向，尤其从旧版本升级过来的机器。
- [ ] 大批量写入前先 `logseq graph backup create` 打一个快照。
- [ ] 涉及加密图库的，先备好 `--e2ee-password` 并在同步流程里持久化。
- [ ] 需要机器解析输出的一律加 `--output json`。

执行后：

- [ ] 用 `logseq show --page <页面>` 或 `search` 抽查写入结果。
- [ ] 用 `logseq doctor` 看有没有权限或服务修订号告警。
- [ ] 确认没有把登录态文件（`auth.json`）或加密密码提交进版本库。
- [ ] 定期验证备份能恢复，而不是只看备份列表里有条目。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/logseq/logseq | 上游仓库（安装与完整文档以它为准） |
| https://github.com/logseq/logseq/blob/master/docs/cli/logseq-cli.md | 命令行完整子命令与参数说明 |

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
