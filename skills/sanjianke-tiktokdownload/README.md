# 三剪客 · 抖音与 TikTok 作品批量下载 Skill

TikTokDownload：抖音与 TikTok 作品批量下载 的安装、常用命令与避坑要点

---

## 前置条件

- **Python ≥ 3.10**（上游推荐 3.11.1），并且 `pip` 可用；Linux / macOS 上命令里的 `pip` 换成 `pip3`。
- **Node.js 运行环境**：F2 的部分应用依赖 Node 来执行签名算法，建议先用 nvm 装好 Node 再装 F2。
- **终端**：命令行交互较重，Windows 上建议使用 Windows Terminal，旧版控制台显示会错乱。
- **一个抖音 / TikTok 账号**：用来导出登录 Cookie。大部分接口需要登录态，只有部分公开页面可游客访问。
- **网络出口**：直连平台接口不稳定时，需要自备 HTTP/HTTPS 代理。
- **磁盘余量**：视频 + 图集 + 封面的批量下载体积增长很快，先确认目标目录所在磁盘够用。

---

## 使用

最短跑通路径（三条命令）：

```bash
pip install -U f2                          # 1. 安装或升级
f2 dy -h                                   # 2. 确认帮助能打出来，参数以当前版本为准
f2 dy -M one -u "https://v.douyin.com/xxxx/"   # 3. 先下一条单作品验证链路通不通
```

链路通了再上批量：

```bash
# 主页作品批量下载，限定日期区间与数量，输出到指定目录
f2 dy -M post -u https://www.douyin.com/user/xxxxxxxx \
  -p ./Download -i "2023-01-01|2024-12-31" -o 100

# 抖音合集
f2 dy -M mix -u https://www.douyin.com/collection/xxxxxxxx

# TikTok 搜索关键字下载
f2 tk -M search -w "keyword" -p ./Download
```

配置与 Cookie：

```bash
f2 dy --init-config my_config.yaml     # 初始化一份配置文件
f2 dy --auto-cookie edge               # 从浏览器自动读 Cookie（先完全退出该浏览器）
f2 dy -k "your_cookie" -c my_config.yaml --update-config   # 手动更新 Cookie
f2 dy -c my_config.yaml                # 之后直接按配置跑
```

完整参数表、配置项含义与开发者接口用法，以仓库内说明和上游官方文档为准（`f2 dy -h`、`f2 tk -h`）。

本 Skill 只做「怎么装、怎么用、哪里会踩坑」的整理，不包含上游源码。

---

## 依赖

| 类别 | 依赖 | 说明 |
|---|---|---|
| 运行时 | Python ≥ 3.10 | 上游推荐 3.11.1 |
| 运行时 | Node.js | 部分应用依赖，用于签名相关处理 |
| 包 | `f2`（PyPI） | 实际提供 `f2` 命令的主体 |
| 外部服务 | 抖音 / TikTok 接口 | 需要可访问的网络出口与有效 Cookie |
| 可选 | 代理服务器 | 支持 HTTP / HTTPS，最多两个参数 |
| 可选 | 浏览器 | 仅在 `--auto-cookie` 场景需要，且要能读到其本地 Cookie |
| 磁盘 | 目标目录 | 默认 `./Download` |

F2 自身的库依赖（httpx、click、aiofiles、rich、pyyaml、jsonpath-ng、m3u8、pytest 等）会由 pip 自动安装，不需要手工逐个装。

---

## 安全

- 不内嵌任何密钥，本 Skill 内不含 Cookie、Token 或账号信息。
- **Cookie 等同于账号登录凭证**：拿到 Cookie 就能登录你的账号，不要写进脚本仓库、不要贴到 Issues / 群聊、不要留在命令历史里。
- 使用 `--auto-cookie` 会读取本机浏览器的 Cookie 数据库，属于本机敏感数据访问，仅在自己机器上使用。
- 下载内容可能涉及他人著作权：仅下载自己有权使用的素材，二次创作与分发要自行确认授权。
- 平台风控与账号安全：高频、大体量采集容易触发风控，建议保守设置并发与重试，必要时使用代理。
- 上游在仓库中明确说明项目仅供学习研究使用；实际合规责任在使用者。
- 本 Skill 正文为独立整理，不含上游源代码，也不对上游软件的问题提供技术支持。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`TikTokDownload`
- 仓库：https://github.com/Johnserf-Seed/TikTokDownload

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
