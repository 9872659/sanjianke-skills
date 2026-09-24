# 三剪客 · HTTP 命令行客户端 Skill

httpie：HTTP 命令行客户端 的安装、常用命令与避坑要点

---

## 前置条件

- 目标机器上要有 Python 3.7 或更新版本（只有走 pip / pipx 装法才需要；用包管理器、单文件发行版安装时运行时是自带的）。
- 先确认 `python --version` 与 `python -m pip --version` 都能正常输出，再动手装。
- 需要有一个可以访问的目标服务；访问内网地址时，运行这个 Skill 的机器本身要能路由过去，否则报的是连接错误而不是接口错误。
- 如果要连自签证书的服务，提前准备好私有 CA 的 bundle 文件路径。
- 如果要复用登录态，先想清楚会话文件放在哪（默认在配置目录下，可用 `HTTPIE_CONFIG_DIR` 改）。

## 使用

最短跑通路径是三步：

```bash
# 1) 装上并确认可执行文件存在（会同时提供 http 与 https 两个命令）
python -m pip install httpie
http --version

# 2) 先离线拼一个请求，确认语法和字段类型都对，再真发
http --offline --print=HB POST https://pie.dev/post name=John age:=29

# 3) 真发出去，需要排错时带上 -v 把请求与响应都打出来
http -v POST https://pie.dev/post name=John age:=29
```

日常最常用的几条：

```bash
# 读一个接口 + 查询参数（== 会自动转义，不用管 & 号）
http GET https://pie.dev/get q==httpie per_page==1

# 表单与文件上传（文件字段必须配 -f 或 --multipart）
http -f POST https://pie.dev/post hello=World
http -f POST https://pie.dev/post cv@./resume.pdf

# 复用登录态（第一次带上认证与自定义头，之后就只带会话名）
http --session=./sess.json https://pie.dev/headers X-API-Token:123
http --session=./sess.json https://pie.dev/headers

# 在脚本/CI 里调用：关掉 stdin 等待、设超时、按 HTTP 状态码取退出码
http --ignore-stdin --timeout=5 --check-status -b https://pie.dev/status/500; echo "exit=$?"

# 下载与续传
http --download https://pie.dev/image/png
http -dco file.zip https://pie.dev/bytes/100000
```

参数全集以 `http --help` 与官方文档为准：https://httpie.io/docs/cli

## 依赖

- **运行时**：Python 3.7+（pip / pipx 装法）。包管理器与单文件发行版自带运行时，无需额外准备。
- **直接依赖**：安装时由包管理器自动拉取，不需要手动处理。
- **可选能力**：
  - 私有 CA 证书文件 —— 访问自签 HTTPS 服务时通过 `--verify=<路径>` 指定。
  - 代理 —— 通过 `--proxy` 或 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` 环境变量。
  - `~/.netrc` —— 开启凭据自动读取时会用到；不想用它可加 `--ignore-netrc`。
  - 插件 —— 通过 `httpie cli plugins install <名称>` 装入配置目录，用于扩展认证方式或输出格式。
- **不需要**：GPU、模型权重、任何模型服务的 Key。这是纯客户端的网络请求工具。

## 安全

- 不内嵌任何密钥：本 Skill 正文与脚本里没有任何 Token、密码或私钥。
- **凭据会落盘**：`--session` 生成的会话文件是普通 JSON，认证信息、Cookie、自定义请求头都以明文保存。用完请勿提交进仓库，建议把会话文件路径加进 `.gitignore`。
- **命令行参数可见**：`-a user:pass` 这类写法会出现在进程列表和 shell 历史里；敏感场景改用 `-a user` 交互式输入密码，或用只读会话文件。
- **请求内容会被发到远端**：`field=@file` 与 `:=@file` 会把本地文件内容塞进请求体，发之前确认目标地址可信、内容不含不该外发的数据。
- **TLS 校验**：`--verify=no` 只应在临时排错时使用；正式环境请指定私有 CA bundle，不要长期关闭校验。
- **只对已授权地址发请求**：这是主动向外部发起连接的工具，请勿用于未经授权的目标探测。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`httpie`
- 仓库：https://github.com/httpie/cli

---

## 许可证

MIT，见 `LICENSE.md`。

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
