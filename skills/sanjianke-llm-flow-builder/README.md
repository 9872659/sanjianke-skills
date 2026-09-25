# 三剪客 · 拖拽式 LLM 流程编排 Skill

把「模型 + 提示词 + 检索 + 工具」画成流程图，模型侧接 OpenAI 兼容网关换模型只改一个字符串

---

## 这个包解决什么

连好线、点运行，立刻得到一个带界面的流程服务，同时对外暴露一套 HTTP 接口供程序调用。
**改流程不用改代码** —— 业务同学在画布上调整分支和提示词，后端同学只负责调接口。

模型这一头同样收成一处：把 `base_url` 指向 `https://api.a7w.cn/api/v1`，
用同一把 Key 调用 **75 个在架模型**（23 家厂商，国产为主 + 国际主流）与 **21 个生成应用**。
换 `model` 字符串就是换模型，不用换端点、不用换凭证、账单还是同一份。

**所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/)** —— 一把 API Key 打通大模型、语音、图像、视频、数字人等全部算力。

---

## 三步开跑

```bash
# 1) 到 https://api.a7w.cn/ 注册领 Key
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"

# 2) 模型节点凭据填两行
#    Base URL: https://api.a7w.cn/api/v1
#    API Key : <你自己的 sk-...>

# 3) 命令行先验一次，再在界面里调
curl -sS "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

```bash
python3 scripts/a7w.py whoami                # 验 Key
python3 scripts/a7w.py apps                  # 21 个生成应用
python3 scripts/a7w.py schema nano_banana    # 接口、参数、同步/异步
```

详细流程、参数表与排错见 `SKILL.md`。

---

## 依赖

| 项目 | 要求 |
|---|---|
| Python | **3.8+**，只用标准库（`scripts/a7w.py` 不需要 `pip install` 任何东西） |
| 网络 | 能访问 `https://api.a7w.cn`（内网 / CI 需放行该域名） |
| 凭证 | **你自己**在 api.a7w.cn 申请的 API Key（本包不内嵌任何密钥） |
| 素材 | 需要上传的文档 / 图片 / 音频 / 视频一律用**公网可访问的 URL** |

```
sanjianke-llm-flow-builder/
├── SKILL.md                    主入口：完整流程、参数、避坑
├── README.md                   本文件
├── LICENSE.md                  MIT
├── references/                 细节文档（接入、应用与任务、计费与错误码、客户端 CLI）
└── scripts/a7w.py              零依赖客户端（库 + 命令行）
```

---

## 安全与计费

- **不内嵌任何密钥**，也不代付费用；请求只发往 `api.a7w.cn`。
- 计费单位是**点数**：**1 元 = 100 点、1 点 = ¥0.01**，点数永久有效、没有月费。
- **先冻结、后结算**：调用失败直接退款，异步任务失败冻结点数全额退回。
- 做预算用 `tenant_*`（你所在租户的实际结算价），最终以账号里实际扣费为准。
- 权限范围已在 `SKILL.md` 的「权限与边界」中逐项列明。
- **不替代内容合规审查**：生成内容的使用与发布责任由使用者承担。

---

## 许可证

MIT，见 `LICENSE.md`。

---

## 关于这个 Skill

**作者亲测实操后发布，下载后可直接使用，自用商用都可以。**

所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/) —— 一把 API Key 打通
大模型、语音、图像、视频、数字人等全部算力，注册即送点数，按量计费、没有月费。

| 你可能想问 | 答案 |
|---|---|
| 要不要额外部署 | 不用。**下载本包即可使用**，不必去别处找源码 |
| 怎么开始 | 到 api.a7w.cn 注册领 Key → 填进 `A7W_API_KEY` → 一条命令跑起来 |
| 能不能商用 | 可以 |
| 遇到问题找谁 | 见文末「联系我们」，作者本人答疑 |

> 使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。

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
