# 三剪客 · 网页版文件管理器 Skill

filebrowser：网页版文件管理器 的安装、常用命令与避坑要点

---

## 前置条件

> **先确认前提**：上游项目已于 **2026-09-01 归档**，最后一个计划中的版本已经发布完毕，之后**不会再有新版本、Bug 修复或安全修复**。官方给出的使用建议是：不要直接暴露到互联网、保持命令执行功能关闭、在容器里以非特权用户运行且只挂载要对外的那一个目录。继续用它，就要按「无人维护软件」来对待。

- 一个要对外提供的目录，以及一个**有权限读写这个目录**的运行账号。
- **不要**把它直接挂在公网：前面需要一个会终止 TLS 并做认证的反向代理。
- 想更稳妥就用容器方式跑，只把需要的目录挂进去。
- 需要写两个文件的权限：数据库文件（默认 `./filebrowser.db`）和配置文件（`settings.json`）。
- 不需要外部数据库服务，也不需要任何第三方账号或 Key。
- 首次「快速初始化」时，随机初始密码**只在控制台打印一次**——要么当场记下，要么改用 `config init` + `users add` 显式建库建用户。
- Docker 方式额外要求：Docker 引擎可用；如果用 bind mount，宿主目录的权限要匹配容器内运行的 UID/GID（镜像默认 UID 1000 / GID 1000）。

---

## 使用

最短跑通路径（Docker，适合当一次性服务用）：

```bash
docker run \
    -v filebrowser_data:/srv \
    -v filebrowser_database:/database \
    -v filebrowser_config:/config \
    -p 8080:80 \
    filebrowser/filebrowser
```

启动日志里会打印访问地址与 `admin` 的随机密码，**只显示一次**。

用二进制跑，并且把配置先定好（比快速初始化可控）：

```bash
curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

filebrowser -d /etc/filebrowser/filebrowser.db config init
filebrowser -d /etc/filebrowser/filebrowser.db config set \
  --address 0.0.0.0 --port 8080 --root /srv/data --locale zh-cn

filebrowser -d /etc/filebrowser/filebrowser.db users add alice '一个足够长的密码'
filebrowser -d /etc/filebrowser/filebrowser.db users update alice --scope /srv/data/alice

filebrowser -d /etc/filebrowser/filebrowser.db -r /srv/data -a 127.0.0.1 -p 8080
```

生产里监听地址建议写 `127.0.0.1`，让它躲在反向代理后面，而不是自己直接对外。

参数可以三种方式给：命令行 flag、环境变量（`FB_` + flag 名的大写下划线形式，例如 `--disablePreviewResize` → `FB_DISABLE_PREVIEW_RESIZE`）、配置文件。
优先级从高到低是 flag > 环境变量 > 配置文件 > 数据库值 > 默认值。不指定 `--config` 时，它会在 `./`、`$HOME/`、`/etc/filebrowser/` 找 `.filebrowser.{json,toml,yaml,yml}`。

更完整的操作、坑表与安全检查清单见 `SKILL.md`。

---

## 依赖

| 依赖 | 必要性 | 说明 |
|---|---|---|
| 可执行文件 | 必需 | 单文件，静态发布，无语言运行时依赖 |
| 数据库文件 | 必需 | 嵌入式单文件数据库，存用户与配置；无需外部数据库服务 |
| 配置文件 | 可选 | `settings.json`；也可全部用 flag / 环境变量代替 |
| 可读写的目标目录 | 必需 | 它对外提供的文件根目录 |
| 反向代理 | 生产必需 | 用于 TLS 终止与认证；官方建议不要直接暴露服务 |
| Docker 引擎 | 容器方式需要 | 镜像默认以 UID 1000 / GID 1000 运行 |
| Redis | 可选 | 多实例部署时用 `--redisCacheUrl` 共享缓存 |
| TLS 证书与私钥 | 可选 | 用 `--cert` / `--key` 让它自己终止 TLS（生产更推荐放代理后面） |
| 外部认证程序 | 可选 | `--auth.method` 配成 hook / proxy 模式时使用 |

---

## 安全

- 不内嵌任何密钥；初始凭据在本地生成，云端账号与 Key 一概不需要。
- **本项目已归档，不再有安全修复**。所有安全措施都要靠部署侧的隔离来弥补，而不是等上游补丁。
- **不要直接暴露到公网。** 官方明确建议放在会终止 TLS 并执行自身认证的反向代理后面。
- **保持命令执行功能关闭。** `--disableExec` 默认就是 `true`，**不要**用 `--disableExec=false` 打开；该功能历史上出过多个漏洞，官方结论是需要重写才能安全。一旦打开，等同于给对方一个 shell。
- **会话不可吊销是已知且不会修的问题**：会话是自包含 JWT 而非服务端标识，登出、改密码、续期都不会让已签发的令牌失效，同一刷新令牌还可被重复兑换。因此要把 `--tokenExpirationTime` 按风险调短，并把令牌泄漏当成密码泄漏处理。
- **以非特权用户在容器内运行**，只挂载确实需要对外的那一个目录，避免一个漏洞就波及整台机器。
- **数据库文件等同全部账号凭据**，请把它放在只有服务账号可读的位置，并纳入备份。
- **按最小必要授权**：每个用户用 `--scope` 圈定可见目录，下载/上传/删除/改/重命名逐项决定，不给不必要的写权限。
- `--followExternalSymlinks` 官方标注为不安全，会跟随指向用户范围之外的链接，默认保持关闭。
- 用户名下的文件缓存目录可能残留文件内容，清理或迁移时别遗漏。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`filebrowser`
- 仓库：https://github.com/filebrowser/filebrowser

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
