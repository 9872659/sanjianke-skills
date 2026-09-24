# 三剪客 · 百模型统一调用 Skill

把 100+ 家模型的调用统一成 OpenAI 格式：写代码时当 Python 库换模型名，做平台时起一个网关把密钥、额度、限流、用量统计收在一处。

---

## 前置条件

- Python 环境：SDK 与 Proxy 都在 Python 生态里。
- 各模型供应商的 API Key（环境变量命名约定如 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`）。
- SDK 形态：`uv add litellm` 或 `pip install litellm` 即可，无需服务端。
- 网关形态：Docker 与 docker compose；生产建议 Postgres（必需，用于虚拟密钥与花费统计）与 Redis。
- 想用虚拟密钥或预算控制，**必须连数据库**，否则这两项不生效。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

SDK 最短路径：

```bash
uv add litellm
export OPENAI_API_KEY="your-openai-key"
```

```python
from litellm import completion

response = completion(model="openai/gpt-4o",
                      messages=[{"role": "user", "content": "Hello!"}])
# 换供应商只改 model 字符串
response = completion(model="anthropic/claude-sonnet-4-20250514",
                      messages=[{"role": "user", "content": "Hello!"}])
```

网关最短路径（官方一键 compose，含 Postgres，端口 4000）：

```bash
curl -sSL https://docs.litellm.ai/docker-compose.yml | docker compose -f - up -d
# 管理界面 http://localhost:4000/ui （用户名 admin，密码是 LITELLM_MASTER_KEY）
```

或者本地包：

```bash
uv tool install 'litellm[proxy]'
litellm --model gpt-4o
```

客户端就是官方 OpenAI SDK，把 `base_url` 指向 `http://0.0.0.0:4000` 即可。

config.yaml 的五段配置（`model_list` / `router_settings` / `litellm_settings` / `general_settings` / `environment_variables`）与各段细节以 https://docs.litellm.ai/docs/proxy/configs 的当前内容为准。

---

## 依赖

- `litellm`（SDK）或 `litellm[proxy]`（网关）
- 各供应商的 API Key（环境变量注入）
- 网关形态：Docker + docker compose；生产需要 Postgres，建议加 Redis
- 云上部署：AWS / GCP 的 Terraform 模块，或 Kubernetes + Helm
- MCP / A2A 网关能力按需引入对应 SDK（如 `a2a-sdk`）

---

## 安全

- 不内嵌任何密钥
- 网关侧会集中保管**所有供应商的 API Key**，它是新的密钥中心，必须按密钥中心的标准来防护
- 供应商密钥一律走环境变量或密钥管理；`config.yaml` 里用 `os.environ/VAR_NAME` 形式引用，不要把明文写进仓库
- `LITELLM_MASTER_KEY` 是网关的最高权限凭证，不要沿用示例默认值；`LITELLM_SALT_KEY` 用于加密界面里填的供应商密钥，设成长随机值后**不要再改**
- 面向团队时用虚拟密钥而不是分发 master key，并按应用/人设置额度与可用模型范围
- 官方镜像是带 cosign 签名的，生产建议用 `-stable` 标签并按其说明校验签名
- 网关对外暴露时需自己加 TLS、网络隔离与访问控制，并留意它会转发全部模型流量，日志里可能含敏感 prompt

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`LiteLLM`
- 仓库：https://github.com/BerriAI/litellm

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
