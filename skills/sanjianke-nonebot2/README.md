# 三剪客 · 多平台聊天机器人框架 Skill

Python 异步聊天机器人框架：脚手架建项目、配置分层、插件加载与部署避坑

---

## 前置条件

- Python 3.10 及以上（官方文档另处写 3.9，以包元数据为准），并强烈建议使用虚拟环境
- 若机器上装过第一代框架，先 `pip uninstall nonebot` 卸载，避免与新版冲突
- 一个明确的连接方式（反向 WebSocket / HTTP 上报 / 正向 WebSocket），据此选驱动器与适配器
- 想连聊天软件还需要另外准备协议端（如 OneBot 实现）或平台官方接口凭据
- 只用 Console 适配器验证框架时，不需要任何外部服务

---

## 使用

1. 按 `SKILL.md`「安装」一节用 pipx 装脚手架，`nb create` 生成项目并选好模板、适配器、驱动器。
2. 在项目目录里 `nb run`；先用 Console 适配器的 `/echo hello world` 验证框架本身正常。
3. 装目标平台的适配器并注册，按适配器文档配置连接地址，确保驱动器类型匹配连接方式。
4. 把业务写成插件，或用 `nb plugin install` 装商店插件；插件注册信息放 `pyproject.toml`。
5. 配置放 `.env` 与 `.env.{ENVIRONMENT}`，注意优先级是"直接传入 > 环境变量 > dotenv"。
6. 上线前按「常见坑」与「自检清单」逐条过一遍，尤其是版本、驱动匹配与事件循环相关项。

---

## 依赖

- Python 3.10 ～ 3.13 一线（包元数据 `>=3.10, <4.0`）
- 驱动器：安装时以可选依赖形式引入，如 `nonebot2[fastapi]`、`nonebot2[aiohttp]`、`nonebot2[httpx]`、`nonebot2[websockets]`、`nonebot2[quart]` 或 `nonebot2[all]`
- 适配器：单独的包，如 `nonebot-adapter-onebot`、`nonebot-adapter-console`
- 脚手架：pipx 或 uv tool 安装的 `nb-cli`，要求 Python 3.10+
- 容器化部署需要 Docker 与 docker compose（通过脚手架 Docker 插件使用）

---

## 安全

- 不内嵌任何密钥
- 各平台的 Token / AppID / AppSecret 建议用环境变量注入，不要写进提交到版本库的 `.env`
- `.env` 与 `.env.{环境}` 文件应限制读取权限，尤其是在共享服务器上
- 反向 WebSocket 与 HTTP 上报地址默认只监听本机；需要对外暴露时必须评估访问控制，必要时放在反代后面
- 插件拥有与机器人进程相同的权限，安装第三方插件前应确认来源可信
- 生产环境用容器或专用账号运行，不要用 root

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`NoneBot2`
- 仓库：https://github.com/nonebot/nonebot2

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
