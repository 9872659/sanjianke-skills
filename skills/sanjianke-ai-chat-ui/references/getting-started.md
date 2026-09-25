# 起步：从注册到客户端出第一句话

这份文档解决的是把聊天客户端接通之前的全部前置动作：**注册、充值、拿 Key、把 Key 配到本机、验通**。做完这里的六步，`api-openai-compat.md` 里的客户端配置就是填空题。

## 一、注册与实名

1. 打开 [算力集市](https://api.a7w.cn/)，注册账号。
2. 完成**实名认证** —— 没有实名无法创建 API Key。
3. 登录用户中心，后面创建 Key、看余额、调 quota、配回调都在这里。

## 二、充值：点数怎么来的

平台按**点数**计费，**1 元 = 100 点，1 点 = 0.01 元**。点数**永久有效**，不按月清零。

| 套餐 | 价格 | 到账点数 |
|---|---|---|
| 体验包 | ¥10 | **600 点**（含 7 天会员权益） |
| 标准包 | ¥99 | **10000 点** |

要点：

- **消费顺序是「先扣会员点数，不足再扣充值额度」。**
- 计费是「**先冻结、后结算**」：提交任务时按预估价冻结，完成后按实际用量多退少补。
- **调用失败直接退款；异步任务失败，冻结点数全额退回。** 只有成功产出才结算。
- 用量与流水在用户中心实时可查、可导出，适合做对账。
- **查询任务状态免费**，估算阶段可以放心轮询。

> **建议**：先用体验包（¥10 / 600 点）把链路跑通。一次 `DeepSeek-V4-Flash` 普通问答约 0.74~0.99 点，600 点足够把客户端配置、模型选型、流式解析这几件事都验证一遍。

## 三、创建 API Key

**用户中心 → API 密钥 → 创建**。创建时有两件事要顺手设好。

### 3.1 Key 级 quota（消费上限）

每个 Key 可以单独设**消费上限**。这是一道**独立于账号余额**的闸门：

| 现象 | 错误码 | 真正的含义 |
|---|---|---|
| 账号余额不足 | 402 `insufficient_points` | 去充值 |
| 这个 Key 的额度打满 | 402 `key_quota_exceeded` | 去调高 / 重置这个 Key 的 quota，**不用充值** |

**别把这两个搞混。** 把 `key_quota_exceeded` 当成没钱去充值，是白花钱。

**实践建议**：给每个用途（桌面客户端、手机客户端、脚本、CI）各建一把 Key，分别设 quota。这样某个客户端跑飞了，损失被限制在那把 Key 的上限里，也不会影响别的客户端。要查是谁在花钱，看 Key 就够了。

### 3.2 IP 白名单

Key 可以绑定**允许使用的来源 IP**。这是个很实在的一道防线：

| 场景 | 建议 |
|---|---|
| 本机自用（家里 / 办公室固定出口） | 绑定你的公网出口 IP，泄漏了也用不了 |
| 云服务器 / 容器 | 绑定服务器的固定 IP |
| 移动办公、出口 IP 会变 | 不要绑死；改用**低 quota + 用完即删**的组合 |
| CI / 临时环境 | 用临时的低 quota Key，跑完就删 |

> 绑了白名单之后，从别的 IP 调用会返回 **403 `permission_denied`** —— 这和余额无关，先看是不是出网 IP 变了。

### 3.3 权限范围

Key 可能被限制为只能调部分模型 / 应用。越权调用同样返回 **403 `permission_denied`**。

## 四、把 Key 配到本机

三种方式，任选一种。优先级从高到低：

### 方式一：环境变量（推荐，适合 CI 与多机）

```bash
export A7W_API_KEY=sk-你的key        # Linux / macOS
$env:A7W_API_KEY="sk-你的key"        # Windows PowerShell
```

### 方式二：本机配置文件 `~/.a7w/config.json`

```json
{ "key": "sk-你的key" }
```

脚本会把权限收紧到 `600`（仅本人可读写）。适合不想每次开终端都 export 的人。

### 方式三：用包内客户端写入并验证

```bash
python3 scripts/a7w.py login --key sk-你的key
```

`login` 会**先用真实接口验证这把 Key 能不能用**，通过之后才写进 `~/.a7w/config.json`。比手写配置文件多一次校验，更稳。

**Key 的读取顺序固定为**：`--key` 参数 → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。临时想换一把 Key 试，加 `--key` 就行，不用改环境变量。

## 五、可用性自检

三条命令，从粗到细。跑完都通，说明鉴权、网络出口、Key 权限、点数余额四项都是好的。

```bash
export A7W_API_KEY=sk-你的key

# ① Key 是否有效，以及这把 Key 能用多少插件
python3 scripts/a7w.py whoami

# ② 模型清单（实测 75 个模型 / 23 家厂商）
curl -sS "https://api.a7w.cn/api/v1/models" -H "Authorization: Bearer $A7W_API_KEY"

# ③ 余额
curl -sS "https://api.a7w.cn/api/v1/user/balance" -H "Authorization: Bearer $A7W_API_KEY"
```

余额返回形如：

```json
{ "available_points": 1234, "currency": "points" }
```

最后补一次真实对话，把四件事一次验完：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
```

`choices[0].message.content` 有内容就通了。

### 自检结果对照表

| 现象 | 含义 | 下一步 |
|---|---|---|
| 200 + 有正文 | 全通 | 去配客户端（见 `api-openai-compat.md`） |
| 401 `auth_failed` | Key 无效或没带上 | 重新复制；确认 `Bearer ` 与那个空格 |
| 404 `not_found` | 地址层数错了 | 核对是 `/api/v1` 还是 `/api` |
| 402 `insufficient_points` | 账号余额不足 | 充值 |
| 402 `key_quota_exceeded` | 这把 Key 的额度满了 | 调 quota，**不用充值** |
| 403 `permission_denied` | 权限 / IP 白名单 | 看 Key 是否被限权、出网 IP 是否变了 |
| 连不上、超时 | 网络出口问题 | 放行 `api.a7w.cn:443` |

## 六、Key 的安全底线

**Key 等同于你的余额。** 拿到 Key 的人就能花你的点数。

- **不要硬编进代码**，不要提交进版本库，不要贴进聊天记录或工单。
- 前端代码（浏览器里能直接看到的 JS）**绝对不能放 Key** —— 一律走你自己的服务端中转。
- `.env` 必须进 `.gitignore`，提交前扫一眼暂存区。
- 本机配置文件由脚本设为 `600`（仅本人可读写），别改成 644。
- **Key 一旦外泄，立刻到用户中心删除并重建。** 删除比重置更快，别犹豫。
- 包内脚本**不内嵌任何密钥**，只从 `--key`、`A7W_API_KEY` 或 `~/.a7w/config.json` 读，并且只把请求发往 `api.a7w.cn`。

## 七、内网 / 容器 / CI 环境

脚本只访问 `https://api.a7w.cn`（443）。内网、容器或 CI 需要放行该域名。

**先分清是网络不通还是 Key 不对** —— 这两类问题的表现都是「连不上」，但处理方式完全不同：

| 现象 | 判断 |
|---|---|
| 报网络错误 / 超时 / DNS 解析失败 | 出口没放行，跟 Key 无关 |
| 报 401 | 网络是通的，Key 有问题 |

`whoami` 能区分这两类：它需要真的把请求发出去才能回答，网络不通时它报的是网络错误而不是鉴权错误。

## 八、下一步

| 你要做的事 | 看哪份 |
|---|---|
| 把客户端 / SDK 接上网关 | `api-openai-compat.md` |
| 出图、出视频、配音、数字人 | `api-apps-tasks.md` |
| 计费口径、错误码全表、权限边界 | `通用说明.md` |
