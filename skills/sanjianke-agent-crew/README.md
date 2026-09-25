# 多角色 Agent 协作编排 · 角色分工与流程控制

把一段活儿拆成几个**有岗位、有目标、有背景故事**的角色，让它们按顺序或按层级协作完成
多步骤任务。模型入口统一走 OpenAI 兼容网关，**改一个 `base_url` 就接完**，
还能给每个角色单独指定模型。

---

## 这个包解决什么

多角色协作最难的不是「怎么调模型」，而是**「怎么描述分工」**：
谁负责哪一步、产出怎么传给下一步、什么时候算干完了。

本包讲的是**怎么把角色的模型入口指向 `api.a7w.cn`**，以及角色建模、数据流声明、
终止条件、多角色成本估算这些工程要点。**不涉及任何需要本地部署的模型权重。**

---

## 前置条件

- 一个 [api.a7w.cn](https://api.a7w.cn/) 账号，并已创建 API Key（新用户有赠送点数）。
- 能访问 `https://api.a7w.cn` 的网络出口（内网 / CI 需放行该域名）。
- **想跟着跑客户端脚本的话**：Python 3.8+，只用标准库，无需 `pip install`。
- 用多角色框架自带 SDK 时：按该框架自己的要求准备运行环境。

---

## 快速开始

### 1. 配置 Key

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 2. 把模型入口指向网关

```bash
# .env（几乎所有框架都认这个文件）
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.a7w.cn/api/v1
```

> 键名以你所用框架的当前版本为准（常见还有 `OPENAI_API_BASE`、`LLM_BASE_URL`）。
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

1. **按环节分档选模型**：调研用快模型、撰写用中档、评审用强模型。账单还是同一份，
   总成本能降一大截。
2. **数据流显式声明**：谁读谁的产出写在代码里，不要靠模型自己接。
3. **终止条件必须设**：评审角色的系统提示里写死触发词（如 `APPROVE`），
   代码里匹配它，并确认它在正常路径下真会被触发。
4. **该确定的交给代码**：审批、分支、重试用确定性流程，判断类环节才交给角色。
5. **结构化输出**：要给下游消费的产出用 JSON / 结构化模型，别让模型自由发挥。

细节见 `SKILL.md` 与 `references/角色编排指南.md`。

---

## 依赖

- **Python 3.8+**（仅客户端脚本；只用 `urllib` 等标准库）。
- 一个可用的模型：由 `api.a7w.cn` 提供，**无需自备 GPU**。
- 网络：能访问 `https://api.a7w.cn`。

---

## 安全

- **不内嵌任何密钥。** Key 由使用者提供，从环境变量 `A7W_API_KEY` 或
  `~/.a7w/config.json` 读取；脚本只把 Key 发往 `api.a7w.cn`。
- **Key 等同于余额**，不要写进代码、不要提交进 Git 仓库。
- 请求只发往 `api.a7w.cn`，不发送到其他任何地址。
- **成本可控性**：多角色多轮会放大 token 消耗，**务必先设终止条件再跑长任务**。
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
