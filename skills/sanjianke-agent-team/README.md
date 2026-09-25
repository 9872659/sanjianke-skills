# 多智能体软件开发团队 · 一句话需求生成项目骨架

给一句需求，拿回一整套东西：**用户故事、需求拆解、数据结构、接口设计、文档**，
最后落到一个能打开的项目仓库。模型入口统一走 OpenAI 兼容网关，
**改一个 `base_url` 就接完**。

---

## 这个包解决什么

这类框架把**一家软件公司的分工与流程**搬到模型上：产品经理、架构师、项目经理、
工程师各司其职，按流程把需求一层层往下传。

本包讲的是**怎么把这条流水线的模型入口指向 `api.a7w.cn`**，以及角色分工、
需求写法、产物目录、成本估算这些工程要点。
**不涉及任何需要本地部署的模型权重。**

---

## 前置条件

- 一个 [api.a7w.cn](https://api.a7w.cn/) 账号，并已创建 API Key（新用户有赠送点数）。
- 能访问 `https://api.a7w.cn` 的网络出口（内网 / CI 需放行该域名）。
- **想跟着跑客户端脚本的话**：Python 3.8+，只用标准库，无需 `pip install`。
- 用多角色流水线框架自带 SDK 时：按该框架自己的版本要求准备运行环境
  （Python 版本区间、可选的前端构建工具等，以框架当前文档为准）。

---

## 快速开始

### 1. 配置 Key

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 2. 把模型入口指向网关

```bash
export OPENAI_API_KEY=sk-你的key
export OPENAI_BASE_URL=https://api.a7w.cn/api/v1
```

或写进框架的模型配置文件：

```yaml
llm:
  api_type: "openai"
  model: "DeepSeek-V4-Pro"
  base_url: "https://api.a7w.cn/api/v1"
  api_key: "sk-你的key"
```

> 配置文件名与键名以你所用框架的当前版本为准。
> **值永远是同一个网关地址与同一把 Key。**

### 3. 验证一条调用

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

成功返回体是 `{"code":1,"msg":"success",...}` —— **成功码是 `1`，不是 `0`。**

### 4. 零依赖客户端

```bash
python3 scripts/a7w.py whoami      # 验证 Key
python3 scripts/a7w.py apps        # 列出全部能力
python3 scripts/a7w.py call chat completions \
  --body '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}]}'
```

---

## 使用建议

1. **需求里写清验收标准**：越具体，产出越稳，返工越少。
2. **按角色分档选模型**：需求拆解用快模型、架构设计用强模型，账单还是同一份。
3. **从小需求试跑**：先用一个命令行小工具校准单次消耗，再上更大的需求。
4. **产物落独立目录**：别写进源码目录，并加进版本控制忽略规则。
5. **产出定位是骨架与文档**：当作起步脚手架用，接手后自行补测试与边界处理。

细节见 `SKILL.md` 与 `references/团队流水线指南.md`。

---

## 依赖

- **Python 3.8+**（仅客户端脚本；只用 `urllib` 等标准库）。
- 一个可用的模型：由 `api.a7w.cn` 提供，**无需自备 GPU**。
- 网络：能访问 `https://api.a7w.cn`。
- 用流水线框架时的其他前置（解释器版本区间、可选构建工具）以框架当前文档为准。

---

## 安全

- **不内嵌任何密钥。** Key 由使用者提供，从环境变量 `A7W_API_KEY` 或
  `~/.a7w/config.json` 读取；脚本只把 Key 发往 `api.a7w.cn`。
- **Key 等同于余额**，不要写进代码、不要提交进 Git 仓库。
- 请求只发往 `api.a7w.cn`，不发送到其他任何地址。
- **产物目录**：生成的项目文件会写盘，先确认目录边界与磁盘空间。
- **成本可控性**：一条需求会触发多次调用，**先试跑小需求再放大**。
- **合规**：生成内容的使用与合规责任由使用者承担。

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
