---
name: sanjianke-siyuan
slug: sanjianke-siyuan
displayName: 三剪客 · 思源笔记本地知识库
description: "思源笔记 siyuan：本地优先的块级知识库，自带内核 HTTP API 与命令行，能把笔记、搜索、导入导出接到自动化流水线里。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "思源笔记 siyuan：本地优先的块级知识库，自带内核 HTTP API 与命令行，能把笔记、搜索、导入导出接到自动化流水线里。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 办公
  - 协作
---

# 三剪客 · 思源笔记本地知识库

思源笔记把笔记拆成「块」，每个块有独立 ID，可以互相引用、被 SQL 查到，也能整块搬走。它自己带一个本地内核进程，内核既提供网页版界面，也对外暴露一套 HTTP 接口和一套命令行工具。

所以它跟纯 GUI 笔记软件的区别在于：**你的知识库是一个可以被程序读写的数据源**。批量灌入 Markdown、定时跑全文检索、按条件导出成文档、把 AI 生成的内容写回某个笔记本，都能落到具体命令上，不用靠模拟点击。

要落地自动化，先分清两条路：只读写工作空间数据、不想起服务，用 `siyuan` 命令行；要实时读写、要跟打开着的界面联动，用内核 HTTP 接口。

**上游项目**：`思源笔记 siyuan`　**仓库**：https://github.com/siyuan-note/siyuan

## 什么时候用 / 不用

**用它**：

- 「我有一批 Markdown / 素材，要按目录结构灌进某个笔记本」，需要批量建文档而不是一篇篇手点。
- 「在全部笔记里找提到某个词的地方」，还要看命中的是哪篇、哪个块——命令行检索比翻文档树快得多。
- 「把某个文档按 Markdown 导出去，喂给下游的排版或发布流程」。
- 「我有几百条散落资产（PDF、Word、Excel），想连资产正文一起搜」，需要带 `--asset` 的全文检索。
- 「要用 SQL 直接查块表」，比如统计标签分布、捞出某个时间段新增的块。

**不要用它**：

- 只是想把一段文本存起来备用——随手写个文件更省事，为了存文本去装一个带内核的笔记应用不划算。
- 目标知识库里已经有别人在编辑，而你要做的是大批量重写或删除——先确认没有并发编辑，再决定是否直连。
- 需要多人实时协同编辑同一篇文档——它的块级结构更适合「各写各的、互相引用」，不是在线协作文档那套模型。
- 想要一个开箱即用的云端托管服务、有人替你运维——这里讲的是自建和本地部署，运维、备份、鉴权都得你自己负责。
- 只是想在文件系统里对 `.sy` 文件做字符串替换——`.sy` 是 JSON 结构，直接改文件容易破坏块结构，应该走命令行或接口。

## 安装

桌面端最省事：从应用商店或官方安装包安装，装完内核目录会在安装路径的 `resources/kernel/` 下，命令行二进制是 `SiYuan-Kernel`。

```bash
# Windows：安装程序会自动把内核目录加进 PATH，装完直接用
siyuan --help

# macOS：安装后建软链
ln -s /Applications/SiYuan.app/Contents/Resources/kernel/SiYuan-Kernel /usr/local/bin/siyuan

# Linux：安装后建软链（<install-dir> 换成实际安装目录）
ln -s <install-dir>/resources/kernel/SiYuan-Kernel /usr/local/bin/siyuan
```

Windows 上如果装的是 Microsoft Store 版，它跑在 MSIX 沙箱里、改不了 `PATH`，需要自己放一个 `siyuan.cmd` 转发脚本到已在 `PATH` 里的目录；这段脚本以官方 README 给出的写法为准，不要凭印象手写。

服务端推荐 Docker。镜像名 `b3log/siyuan`。**注意：从 v3.7.0 起必须显式带上 `serve` 子命令**，否则容器起不来：

```bash
docker run -d \
  -v /siyuan/workspace:/siyuan/workspace \
  -p 6806:6806 \
  -e PUID=1001 -e PGID=1002 \
  b3log/siyuan \
  serve \
  --workspace=/siyuan/workspace/ \
  --accessAuthCode=换成你自己的密码
```

`docker run --rm b3log/siyuan serve --help` 可以列出全部服务参数。Docker Compose 写法把 `command` 写成 `['serve', '--workspace=/siyuan/workspace/', '--accessAuthCode=${AuthCode}']` 即可。

## 常用操作

以下命令来自官方 README 的命令行章节。`-w` 指定工作空间路径；不带服务也能跑，它直接读工作空间数据。所有命令默认 `-f table`，加 `-f json` 出结构化结果，适合接脚本。

```bash
# 1. 列出全部笔记本（拿笔记本 ID 的第一步）
siyuan notebook list -w ~/SiYuan

# 2. 全文检索，JSON 输出便于后续解析
siyuan search "关键词" -w ~/SiYuan -f json

# 3. 连资产文件正文一起搜，可限定扩展名
siyuan search "检索词" --asset -w ~/SiYuan
siyuan search "检索词" --asset --ext pdf --ext docx -w ~/SiYuan

# 4. 把某个文档导出成 Markdown（--id 是文档/块 ID）
siyuan export md --id <block-id> -w ~/SiYuan

# 5. 跑一条 SQL 查询，看块数据
siyuan sql "SELECT id, content FROM blocks LIMIT 5" -w ~/SiYuan -f json

# 6. 看某个文档的大纲 / 处理每日笔记
siyuan outline --id <block-id> -w ~/SiYuan
siyuan dailynote -w ~/SiYuan
```

命名的子命令分组（官方 README 的命令表）：`notebook` / `document` / `dailynote` 管笔记本与文档，`block` / `attr` / `outline` 管块内容，`tag` / `bookmark` / `template` 管元数据，`search` / `sql` 管查询，`ref` 看反向链接，`export` / `import` / `inbox` 管导入导出，`repo` / `history` / `sync` 管快照与同步，`asset` / `file` 管资源与文件，`database` 管属性视图，`serve` 起内核服务。**每个子命令的具体参数以 `siyuan <子命令> --help` 为准**，不要跨版本照搬。

内核 HTTP 接口适合「服务正在跑、要实时读写」的场景：

```bash
# 接口地址固定是本机 6806，除特别说明外都是 POST，参数放 body 的 JSON 字符串
# 鉴权头：Authorization: Token <你的 API token>
# token 在 设置 - 鉴权 - API token 里查看

# 列笔记本
curl -X POST http://127.0.0.1:6806/api/notebook/lsNotebooks \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" -d '{}'

# 用 Markdown 建文档（path 必须以 / 开头，层级用 / 分隔）
curl -X POST http://127.0.0.1:6806/api/filetree/createDocWithMd \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"notebook":"<笔记本ID>","path":"/素材/示例","markdown":"# 标题\n\n正文"}'

# 往某个父块末尾追加内容
curl -X POST http://127.0.0.1:6806/api/block/appendBlock \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"dataType":"markdown","data":"追加的一段","parentID":"<父块ID>"}'
```

返回体统一是 `{"code":0,"msg":"","data":{}}` 的形状，`code` 非 0 就是出错。**`code: 0` 只代表这个接口自己没报错，不代表索引、缓存、WebSocket 广播或同步状态都刷完了**，需要看到最新索引时得自己等一拍或重新查一次。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| Docker 容器起来又挂，日志提示必须设置访问授权 | 用 Docker 部署时，锁屏密码和有效 OIDC 配置两者必须至少有一个，否则内核直接以安全风险码退出 | 传 `--accessAuthCode` 或设 `SIYUAN_ACCESS_AUTH_CODE`，配好 OIDC，或者明确设 `SIYUAN_ACCESS_AUTH_CODE_BYPASS=true`。**不要为了省事就bypass，那等于把知识库裸奔在公网** |
| 升级到 v3.7.0 之后容器再也起不来 | 该版本起 `serve` 子命令必须显式传，旧的 `docker run` 写法失效 | 在镜像名后补上 `serve`，再跟 `--workspace` 和 `--accessAuthCode` |
| 挂载目录里数据可读可写，但应用报权限错误 | 容器内用户由 `PUID` / `PGID` 决定，宿主机目录的属主跟它不一致 | 先 `chown -R <PUID>:<PGID> /宿主机/workspace`，再启动容器；不要额外传 `-u` 去改用户 |
| 删掉容器之后数据全没了 | 工作空间没挂载出来，或者挂载路径跟 `--workspace` 不一致 | 挂载前先确认 `-v` 的容器侧路径与 `--workspace` 完全相同；官方建议两边路径写成一致（例如都用 `/siyuan/workspace`） |
| 用第三方同步盘同步工作空间，数据损坏 | 官方明确不支持用第三方同步盘同步数据，块结构被并发改写就废了 | 用内置的同步能力或定期导出备份；已经损坏的从备份恢复 |
| 反代之后能打开页面但登录态反复失效、消息不刷新 | 只代理了 HTTP，没给 `/ws` 配 WebSocket 转发；或者配了 URL 重写 | 在 Nginx 里为 `/ws` 单独配置 WebSocket 反代；不要用 URL 重写做跳转，直接配反向代理 |
| Docker 版导不出 PDF / Word / HTML，也导不进 Markdown 文件 | 这是 Docker 部署的已知能力限制 | 需要这些格式就在桌面端做；服务端只做浏览器访问和接口调用 |
| 反复用同一个 `path` 调建文档接口，第二次没生效 | 该接口对已存在的 `path` 不会覆盖 | 想让内容变化就走块级更新接口，或者换个 `path` |
| 把 `conf.json` 或工作空间目录丢进了 Git 仓库 | `conf.json` 里存着 API token、同步凭据、OIDC client secret 等敏感字段 | 把配置目录和工作空间加进 `.gitignore`，共享前先看一遍敏感字段 |
| 直接编辑 `.sy` 文件想批量改内容 | `.sy` 是 JSON 结构的文档数据，手改极易破坏块结构 | 走 `siyuan` 命令行的 `block` 系列或 HTTP 接口做块级修改 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 调用本机内核的 6806 端口接口；从官方源下载安装包或镜像；启用同步时连云端 |
| 读取文件 | 是 | 读取工作空间下的笔记本与 `.sy` 文档数据、`assets` 资源目录，以及作为导入源的 Markdown / 资产文件 |
| 写入文件 | 是 | 在工作空间内建文档、写块、写资源；命令行导出时写目标文件；内核自身维护 `conf.json`、索引与历史 |
| 凭证 | 是 | 内核 API token（设置 - 鉴权 - API token 查看）；Docker 部署的锁屏密码 / `SIYUAN_ACCESS_AUTH_CODE`；启用 OIDC 时是 client secret 等；同步功能的账号凭据。**这些都要当密钥对待，不要写进脚本、日志或公开仓库** |
| 子进程 / 后台常驻 | 是 | 内核本身是常驻进程；Docker 部署下容器长期运行；命令行工具会读写工作空间数据 |

## 触发场景

- 「帮我把这批 Markdown 按目录结构导进思源笔记。」
- 「在我思源的所有笔记里搜一下，哪些文档提到过这个方案？」
- 「把那个文档导成 Markdown，我要拿去排版。」
- 「用 Docker 起一个思源笔记服务端，配好密码和挂载目录。」
- 「我连资产正文一起搜，PDF 和 Word 里的关键词也要命中。」
- 「帮我写条 SQL，统计一下每个标签下有多少个块。」

## 能力边界

**覆盖**：

- 本地 / 自建部署的完整路径：桌面安装包、应用商店、包管理器、Docker、Unraid、TrueNAS。
- 工作空间数据操作：笔记本与文档的增删改查、块级读写、属性与大纲、标签与书签、模板。
- 查询能力：全文检索、资产正文检索、语义检索、SQL 查询、反向链接。
- 导入导出：Markdown、HTML、预览、Word、`.sy.zip`、Data，以及云端收件箱导入。
- 数据管理：`repo` 快照、`history` 历史版本、`sync` 云端同步。
- 内核 HTTP 接口：笔记本、文档、资源、块、属性、数据库（属性视图）、搜索、SQL、模板、文件、导出、转换、通知、系统信息等接口族。
- 部署形态差异的取舍：桌面端有完整能力，Docker 版以浏览器访问和接口为主。

**不覆盖**：

- 多人实时协同编辑同一篇文档的冲突合并策略。
- 用第三方同步盘同步工作空间（官方明确不支持）。
- 替你选型或做成本评估——免费功能与付费会员权益的范围以官方定价页为准。
- Docker 版不支持的导出格式（PDF / HTML / Word）和 Markdown 导入。
- 移动端与桌面端应用的内部开发、插件与主题的开发调试。
- 非公开的内核路由：只有官方 API 文档里有独立小节的接口才是公开 API，其余路由和事务类操作属于内部实现，不保证兼容性和行为稳定性。

## 依赖条件

- 桌面端：Windows / macOS / Linux 安装包，或对应的应用商店版本；手机端有 Android / iOS / HarmonyOS 应用。
- 服务端：Docker（推荐）或 Docker Compose；需要把工作空间目录挂载进容器并设好宿主机属主。
- 命令行：来自安装目录里的内核二进制，需要把它放进 `PATH` 或建软链。
- HTTP 接口：需要内核正在运行（端口 6806），并在设置里拿到 API token。
- 可选：OIDC 身份提供方的 client id / secret；对象存储或 WebDAV 账号（用于同步到第三方存储）。

## 已知限制

- Docker 部署不支持桌面端和移动端应用连接，只能浏览器访问。
- Docker 部署不支持导出 PDF / HTML / Word，也不支持导入 Markdown 文件。
- 只读角色下部分写接口不可用；保存搜索条件这类操作需要管理员角色。
- 接口对已存在 `path` 的建文档请求不覆盖；重复请求是否幂等要看各接口自己的说明，没写就别假定可安全重试。
- 非公开路由没有兼容性承诺，升级可能改变行为。
- 直接操作第三方同步盘会损坏数据，官方不支持这种同步方式。

## 自检清单

执行前：

- [ ] 确认要动的是哪个工作空间、哪个笔记本，命令里的 `-w` 指向对不对。
- [ ] 已备份（用导出功能，或直接复制工作空间目录）。
- [ ] Docker 部署已设访问授权，且不是靠 bypass 绕过的。
- [ ] 宿主机挂载目录属主与 `PUID` / `PGID` 一致。
- [ ] 批量写之前，先用 `-f json` 小范围试跑一条，确认 ID 和路径都对。
- [ ] 目标笔记本当前没有别人在并发编辑。

执行后：

- [ ] 用 `siyuan search` 或 `sql` 抽查写入结果，别只看返回码。
- [ ] 确认没有把 token、锁屏密码写进命令历史或日志。
- [ ] 需要索引即时生效的，重新读一次确认数据已经可查。
- [ ] 涉及删除的，确认删除范围没有超出预期，必要时从 `repo` 快照恢复。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/siyuan-note/siyuan | 上游仓库（安装与完整文档以它为准） |
| https://github.com/siyuan-note/siyuan/blob/master/docs/API.md | 内核 HTTP 接口清单与参数（以仓库实际版本为准） |

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
