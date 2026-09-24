---
name: sanjianke-httpie
slug: sanjianke-httpie
displayName: 三剪客 · HTTP 命令行客户端
description: "httpie：HTTP 命令行客户端 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "httpie：HTTP 命令行客户端 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · HTTP 命令行客户端

手上有接口要试、要复现一个报错、要把某个请求粘给别人看的时候，用 `curl` 常常要拼一长串 `-H`、`-d`、`-X`，JSON 还得自己转义。这个工具把「请求本身」写成了命令行语法：方法放 URL 前面，`=` 是 JSON 字段，`:` 是请求头，`==` 是查询参数，输出默认就带颜色和缩进。

它解决的是「快速发一个 HTTP 请求并看清发了什么、回了什么」这件事。写完的请求还能直接贴进工单或聊天窗口，对方照着敲就能复现。

**上游项目**：`httpie`　**仓库**：https://github.com/httpie/cli

## 什么时候用 / 不用

**用它**：

- 要调一个 JSON 接口，但不想手写 `Content-Type: application/json`、不想自己转义引号，`http POST host/api name=张三` 就够。
- 要复现线上问题，需要把「实际发出去的请求行、请求头、请求体」原样打出来看：`http -v`。
- 要按业务字段拼一个嵌套 JSON（对象套数组），用户把这叫「用命令行拼 JSON」。
- 要在一个会话里复用登录态和自定义头，反复打同一个服务的多个接口：`--session`。
- 要下载一个文件并顺便看响应头，或断点续传：`--download`、`--continue`。

**不要用它**：

- 要在脚本里解析响应做判断：默认输出带 ANSI 颜色、默认 4xx/5xx 也算成功退出，直接 `$()` 取出来的东西是给人看的，不是给程序看的。
- 要跑压测或高并发请求：它是单请求工具，一次一条，做并发/基准测试该换成专门的压测工具。
- 要做流式大文件转存、需要精细控制 socket、HTTP/2 优先级、TLS 指纹这类底层行为：它的表达能力到不了那一层。
- 要发二进制请求体（图片、protobuf 原始字节）：`=` 系列语法是给结构化数据和表单用的，原始字节场景别绕它。
- 只是查一个网址能不能通、或者做健康检查：`curl -sS -o /dev/null -w '%{http_code}'` 或语言里的 HTTP 库更直接，引入一个 Python 运行时反而更重。

## 安装

按装法分四类，选一个就行。完整安装矩阵以官方文档为准（https://httpie.io/docs/cli/installation）。

```bash
# 1) 跨平台：pip / pipx（需要 Python 3.7+）
python -m pip install --upgrade pip wheel
python -m pip install httpie
pipx install httpie                      # 想把它和项目环境隔离时用这个

# 2) macOS / Linuxbrew
brew update && brew install httpie

# 3) Windows
choco install httpie

# 4) Linux 发行版
sudo apt install httpie                  # Debian / Ubuntu（仓库版本可能偏旧）
dnf install httpie                       # Fedora
sudo pacman -Syu httpie                  # Arch
snap install httpie                      # Snapcraft

# 确认装上了（同时会暴露 http 和 https 两个可执行文件）
http --version
```

装完顺手核对一下它到底认哪些参数，不要凭记忆写：

```bash
http --help
http --debug          # 需要知道 config_dir / 环境信息时看这个
```

## 常用操作

下面每条都是可以直接改参数就跑的。`pie.dev` 是公开的 HTTP 测试服务，用来演示；换成自己的域名即可。

```bash
# 1) 最普通的 GET，外加两个查询参数（== 是 URL 参数，自动转义，不用管 & 符号）
http GET https://pie.dev/get q==httpie per_page==1

# 2) POST 一个 JSON：= 是字符串字段，:= 是原始 JSON（数字、布尔、数组、对象都走 :=）
http POST https://pie.dev/post \
  Content-Type:application/json \
  name=John age:=29 married:=false hobbies:='["cli","api"]'

# 3) 只看「实际发出去/收到了什么」，排错必用（-v 会打印请求行、请求头、请求体）
http -v https://pie.dev/get

# 4) 不联网，只把请求拼出来看看对不对（离线模式，调语法很方便）
http --offline --print=HB https://pie.dev/post hello=offline

# 5) 表单 / 文件上传（注意：文件字段只在 -f 或 --multipart 下才有效）
http -f POST https://pie.dev/post hello=World
http -f POST https://pie.dev/post cv@./resume.pdf

# 6) 会话复用：第一次带上认证和自定义头，之后只要带 --session 名字
http --session=./sess.json https://pie.dev/headers X-API-Token:123
http --session=./sess.json https://pie.dev/headers

# 7) 下载 / 续传：-d 下载，-c 续传（必须配 -o 才有意义）
http --download https://pie.dev/image/png
http -dco file.zip https://pie.dev/bytes/100000

# 8) 在脚本里安全调用：忽略 stdin + 设超时 + 用退出码判断 HTTP 状态
http --ignore-stdin --timeout=5 --check-status -b https://pie.dev/status/500; echo "exit=$?"
```

想把它当脚本里的通用客户端时，退出码是有约定的：`2` 超时、`3` 出现 3xx 且没 `--follow`、`4` = 4xx、`5` = 5xx、`6` 超过 `--max-redirects`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `name=John` 发出去是字符串，`age=29` 也被当成字符串 `"29"` | `=` 永远按字符串序列化，只有 `:=` 才是「原样塞进 JSON」 | 数字/布尔/数组/对象一律用 `:=`：`age:=29`、`ok:=true`、`hobbies:='["a"]'` |
| 输出里全是 `[38;5;...m` 之类的乱码 | 终端排版默认开启颜色和缩进，`--pretty=all` 是终端下的默认值 | 管道或 CI 里显式 `--pretty=none`；或加 `--style=auto`；`--unsorted` 只是关排序，不是关颜色 |
| 脚本里执行就卡住不动，本地手敲却正常 | 非交互环境下 stdin 不是终端，它会认为「有重定向输入」并等你喂请求体 | 脚本里加 `--ignore-stdin`（简写 `-I`），除非你确实在 `cat file \| http ...` |
| 返回 404 / 500 了，但 `echo $?` 还是 0 | 默认只有网络层错误才影响退出码，HTTP 状态码不影响 | 需要按状态码判断时加 `--check-status`（3xx→3、4xx→4、5xx→5），或者自己解析 `-p h` |
| `http -d file.json` 下载下来一堆乱码或只有响应头 | `--download` 只改「响应体怎么存」，且它隐含 `--follow` 和 `--check-status`，`Accept-Encoding` 也不能同时设 | 下载走 `--download`，要原始字节直接走重定向输出 `http URL > image.png` |
| 上传文件的字段根本没带上 | 文件字段（`field@path`）只在 `-f/--form` 或 `--multipart` 下才生效 | 加 `-f`；需要强制 multipart 时用 `--multipart`；MIME 类型写成 `'cv@cv.txt;type=text/markdown'` |
| 请求头名字以 `-` 开头时被当成参数报错 | 解析器把 `-` 开头的项当选项了 | 把所有这类项放到 `--` 之后：`http URL -- -X-Trace:1` |
| 明明没给方法，却发了 POST | 方法可省略：有数据体默认 POST，无数据体默认 GET | 想要 GET 带体就显式写 `http GET URL field=value` |
| session 文件里能看到明文密码和 Cookie | 会话文件就是普通 JSON，凭据、Cookie、自定义头都是明文存的 | 别把 session 文件提交进仓库，加进 `.gitignore`；临时用 `--session-read-only` 避免被写回 |
| 输出重定向到文件后，请求体里的二进制把终端搞花了 | 二进制内容默认不打印，但重定向后是否「可打印」的判断会变 | 用 `--print=b`/`-b` 明确只取响应体；混合场景配 `--quiet` |
| 返回体特别大时内存飙高 | 开启颜色/格式化时会把整个响应缓冲下来再处理 | 加 `--stream`（或 `-S`），并配 `--pretty=none` 使用 |
| 把 `curl` 的 `-d`、`-X` 直接搬过来，结果变成了请求头 | `-d`、`-X` 不在它这里，冒号分隔的项会被当成请求头 | 改成 `URL field=value` 的结构；不确定就先 `--offline --print=HB` 看一眼拼出来的请求 |
| 自签证书环境报 SSL 错误 | 默认校验证书链 | 调试期 `--verify=no`；正式环境用 `--verify=/path/ca-bundle.pem` 指向私有 CA |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 这是它的核心功能：向用户指定的 URL 发请求。请只对已授权、你信得过的地址使用 |
| 读取文件 | 按需 | `field=@file`、`:=@file.json`、`@data.txt` 会读取本地文件内容并放进请求体 |
| 写入文件 | 按需 | `--output / -o`、`--download / -d` 会写文件；`--session=<路径>` 会创建/更新会话 JSON |
| 凭证 | 按需 | `--auth` / `-a` 会用到账号密码或 Token；`--session` 会把凭据和 Cookie 明文落到磁盘 |
| 子进程 / 后台常驻 | 否 | 一次性进程，跑完即退出，不驻留、不监听端口 |

## 触发场景

- 「帮我发个 POST 到这个接口，带上这几个字段，看看返回什么」
- 「这个接口本地测是好的，你把我实际发出去的请求原样打出来」
- 「curl 那串太长了，换个能看懂的写法」
- 「这个请求要带登录态，别每打一个接口都重新登录」
- 「把这个文件用表单上传上去，顺便指定 MIME 类型」
- 「我要下载这个地址，断了能接着下」

## 能力边界

**覆盖**：

- 构造并发送任意方法、任意请求头、JSON / 表单 / multipart 三种请求体。
- 打印请求与响应全貌（`-v`）、离线拼装（`--offline`）、只取某几段输出（`--print`）。
- 会话持久化（自定义头、认证、Cookie）、重定向跟随、超时与代理、下载与断点续传。
- 流式响应（`--stream`）、字符集/MIME 覆盖（`--response-charset`、`--response-mime`）。
- 插件扩展新认证方式和输出格式（通过它自带的插件管理子命令）。

**不覆盖**：

- 不做并发压测、不做性能基准、不生成测试报告。
- 不做 WebSocket / gRPC 原生调用（这些要靠插件或别的工具）。
- 不做断言、不做测试用例编排，也不替你判断「这个响应算不算对」。
- 不管理环境变量集合、不做集合式工作区导出（会话文件只是明文 JSON）。
- 不做证书自动签发、不绕过 TLS 校验之外的网络安全策略。

## 依赖条件

- Python 3.7 及以上（pip / pipx 装法）；单文件发行版和包管理器装法则自带运行时。
- 一个可访问的目标服务；内网地址需要确保运行环境本身能路由到。
- 可选：私有 CA 证书文件（自签环境）、代理地址、`~/.netrc` 中的凭据。
- 想在 CI 里复用会话时，需要让工作区保留 `HTTPIE_CONFIG_DIR` 指向的目录。

## 已知限制

- 默认不做 HTTP 状态码检查，`4xx/5xx` 依然返回 0，脚本里必须自己加 `--check-status`。
- 非交互环境下不关 stdin 会挂起，这属于设计行为，不是故障。
- 会话文件明文存凭据；跨机器共享会话文件前要自己处理脱敏。
- 格式化输出会把响应缓冲到内存，超大响应要靠 `--stream` 规避。
- 输出是给人看的排版（含 ANSI 与缩进），当机器可读的中间格式用时，得显式关掉样式。

## 自检清单

执行前：

- [ ] 已确认目标地址是用户给的、或明确授权的地址，不是自己臆测出来的。
- [ ] 已确认请求方法和请求体类型（JSON / 表单 / multipart），`=` 与 `:=` 没混。
- [ ] 若在脚本或 CI 中调用，已带上 `--ignore-stdin`、`--timeout`，需要判错时带上 `--check-status`。
- [ ] 若涉及凭据，已确认不会把 session 文件或命令行参数写进日志、提交进仓库。

执行后：

- [ ] 看的是第几层输出（响应头 / 响应体 / 元数据），要不要用 `--print` 明确一下。
- [ ] 退出码是否被正确解释（有 `--check-status` 时 4/5 是正常语义，不是工具坏了）。
- [ ] 下载或写文件的操作，路径是否落在预期目录，是否覆盖了已有文件。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/httpie/cli | 上游仓库（安装与完整文档以它为准） |
| https://httpie.io/docs/cli/installation | 官方安装矩阵（各平台/包管理器） |
| https://httpie.io/docs/cli/config-file-directory | 配置目录与会话文件位置 |

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
