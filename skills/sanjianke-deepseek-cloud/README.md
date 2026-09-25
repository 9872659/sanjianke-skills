# 三剪客 · DeepSeek 全系云端直连 Skill

不用自己部署，直接调 api.a7w.cn 在架的 DeepSeek 全系大模型 —— 免部署、免显卡、免运维，填两行配置就能用。

---

## 前置条件

- 一个 **api.a7w.cn 账号**，并在用户中心创建好自己的 API Key（形如 `sk-...`）。注册领 Key：https://api.a7w.cn/ ，新用户有赠送点数。
- 能访问 `https://api.a7w.cn` 的网络出口（内网 / CI 环境需放行该域名）。
- 不需要显卡，不需要准备模型文件，不需要任何推理环境。

## 使用

拿到这个 Skill 后，Agent 会按这套顺序干活：

1. **先确认要做什么**。是日常问答、高难推理、长文处理、代码生成，还是批量跑量 —— 决定用哪一款 DeepSeek。
2. **拉一次在架模型清单**。`GET https://api.a7w.cn/api/v1/models`，模型编码逐字复制，不照抄文章里的旧名。
3. **配好 Key**。填进环境变量 `A7W_API_KEY`，或用零依赖客户端 `python3 scripts/a7w.py login --key sk-xxx`。
4. **跑最小示例**。一条 `POST https://api.a7w.cn/api/v1/chat/completions`，确认 `code == 1` 且 `choices[0].message.content` 有内容。
5. **按需要上流式**。请求体加 `"stream": true`，逐行取 `choices[0].delta.content` 拼接输出。
6. **切模型**。只改 `model` 字符串，`base_url`、Key、账单都不动。
7. **上量前先对账**。先跑几条小请求看一眼点数消耗，再估批量成本。

三种接线方式任选：`curl` 直连、OpenAI SDK（只换 `base_url` 与 `api_key`）、包内零依赖客户端 `python3 scripts/a7w.py`。

完整参数、按用途选型表、流式示例与避坑表见 `SKILL.md`。

## 依赖

- **Python 3.8+**，只用标准库（`urllib`），**不需要安装任何第三方包**。
- 一个 **api.a7w.cn 的 API Key**，你自己的账号创建。
- 除零依赖客户端外，其他方式所需的 OpenAI SDK 由你的项目自行选择（Python 用 `openai`，Node 用 `openai`），本包不强制。
- 网络：需要能访问 `https://api.a7w.cn`。

## 安全

- **不内嵌任何密钥**，也不需要任何账号以外的凭证。
- 请求只发往 `api.a7w.cn`，不发送到其他任何地址。
- Key 从 `--key` 参数、环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取；**不要硬编进代码，不要提交进仓库**。
- 本包不提供 Key、不代付费用：用量与费用都记在 Key 所属账号上，**请勿使用他人提供的 Key**。
- 每个 Key 可以单独设消费上限（quota），打满后该 Key 就调不动了 —— 这跟账号余额是两回事，报错也不同码。
- **调用失败直接退款；异步任务失败，冻结点数全额退回。**
- **内容合规**：生成内容的使用与合规责任由使用者承担，本 Skill 只讲接口用法，不提供任何合规结论。

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 平台：算力集市 `api.a7w.cn`
- 模型：DeepSeek 系列，由平台侧在架提供

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
