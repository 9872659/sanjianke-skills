# 成本预估器 花之前先把这一单算清

**一单 5,587 点 = 55.87 元，算这一单 0 点。** 走 [api.a7w.cn](https://api.a7w.cn/) 的四个只读端点：价目、模型目录、应用目录、你自己的任务台账。零依赖，只用 Python 标准库。

这个包的位置很明确：**钱还没花出去的那一刻**。把「今天要几张图、几条片子几秒、几段配音几字、几次后处理几秒」写成一份 JSON 清单，它给你逐项单价、合计、区间，以及这单会踩到哪几个价格陷阱。

---

## 为什么需要这一层

生成式接口的报价单，几乎没人能一眼看懂：

- 价目表 115 条规则，按路径匹配，有精确路径、有 `/apps/x/*` 通配、还有一条全局 `*`；
- 价目表里写着的一些档位，路由根本没注册；
- 同一个模型，走应用层和走模型层能差 75 倍；
- 模型层的单价，价目表里没有，只能从自己的流水里反推。

所以「大概多少钱」这句话，靠拍脑袋一定错。本包把这五件事做成默认动作，报价的每一行都带来源与口径。

---

## 这一单怎么算（`quote`）

```bash
python3 scripts/run.py quote --preset duanju --out 报价
```

```
报价单 · 短剧一集（8 分钟成片）
  6 张分镜图 + 1 条 15 秒 1080P 成片 + 2 条模型层 10 秒视频 + 2 分钟修复 + 220 字配音
================================================================================
  #   项目                   计费口径                   数量      点数        元
  ----------------------------------------------------------------------------
  1   分镜图                 点/张                      6 张      36.00       0.36
  2   成片 1080P             60 点/秒（1080P）          15 秒 × 1 900.00      9.00
  3   模型层补镜             点/条                      2 条      291.46      2.91   !
  4   老素材修复             36 点/秒                   120 秒 × 1 4,320.00    43.20
  5   旁白配音               点/字                      220 字 × 1 39.60       0.40
================================================================================
  基准合计               5,587        点 = 55.87 元
  区间                   5,587 ~ 7,491 点 = 55.87 ~ 74.91 元
```

**区间三档**：乐观 = 按次 / 实测最低口径；基准 = 价目表 rule 口径；保守 = 基准 +30% 重跑余量（按次与按秒混用的档位按 rule ×2）。报给甲方就用基准，自己排期按保守。

清单长这样（`sample` 会替你起个头）：

```json
{
  "title": "短剧一集",
  "items": [
    {"kind": "image", "target": "gpt-image-2.6", "count": 6, "label": "分镜图"},
    {"kind": "video", "target": "full_video", "resolution": "1080P", "seconds": 15},
    {"kind": "video", "target": "model:sd/doubao-seedance-2-0-260128", "seconds": 10, "count": 2},
    {"kind": "post",  "target": "restore", "seconds": 120},
    {"kind": "voice", "target": "voice_tts", "chars": 220}
  ]
}
```

`kind` 五种：`image` / `video` / `post` / `voice` / `app`。`target` 可以写模型名（`gpt-image-2.6`）、档位名（`restore`）、应用名（`full_video`），模型层写 `model:<模型ID>`。

---

## 数据从哪来

| 端点 | 返回 | 用途 |
|---|---|---|
| `GET /api/v1/models` | 316 条 = 221 目录模型 + 95 裸模型层 ID | 模型清单；92 条文本模型带「每百万 token」价 |
| `GET /api/v1/apps` | 22 个应用 / 100 个接口 | 应用目录与接口清单 |
| `GET /api/v1/me/tasks` | 1,398 条，每页恒 20 条 | 模型层单价只能从 `actualPrice` 反推 |
| `GET /api/v1/tasks/<id>` | 假 id → 200「任务不存在」 | 证明查询路由在、不扣费 |
| `GET /user/balance` · `/user/balance/logs` | 余额与流水 | `doctor` 前后各读一次，证明本轮 0 点 |

模型层价格的两个来源：价目表的通配兜底，以及你自己的 `actualPrice`。本包先铺一份 2026-11-08 的实测基线，再用你流水里的最低成交价覆盖，来源字段写清楚是「实测」还是「通配保底」。

---

## 五类价格陷阱（`traps`）

| # | 陷阱 | 现查到的数字 | 报价里怎么体现 |
|---|---|---|---|
| ① | 价目表有、路由 404 | 11 个 `tsc_*` 档，2~6 点/秒、保底 10 点 | 那一行标 `!`，提示换 viapi 同档 |
| ② | 路由在、上游 502 | 3 个腾讯档：1080 2 / 2k 4 / 4k 8 点/秒 | 标注上游凭据问题、整批退款实扣 0 |
| ③ | note 写「点/次」、rule 是 per_second | 6 条：`shot` `castcrew` `delogo` 各扁平 + viapi | 按秒报，区间下限用按次口径 |
| ④ | 落通配保底 | 未定价接口 = 上游×2、保底 50 点 | 标注「通配保底」，实测 15.60 / 26 / 44 点都低于 50 |
| ⑤ | 应用层 vs 模型层 | Seedance 11,000 vs 145.73 = 75.5 倍 | 应用层那一行标 `!`，指向 `compare` |

`doctor` 每次核对这组计数（①11 ②3 ③6 ④保底 50 ⑤配对 11 组），价目一动就会变红。

---

## 应用层 vs 模型层（`compare`）

```bash
python3 scripts/run.py compare --pages 5
```

```
  #   应用层               价        模型层                             实测价     倍数
  ------------------------------------------------------------------------------------
  1   seedance             11,000    sd/doubao-seedance-2-0-260128      145.73     75.5×
  2   happy_horse          650       muse-video                         44.00      14.8×
  3   seedance             11,000    volcengine/doubao-seedance-2-5-26  762.30     14.4×
  4   aigc_wan_image       203       gpt-image-2                        26.00      7.8×
  5   grok_video           300       muse-video                         44.00      6.8×
```

最贵的一对：`seedance` 走应用层 11,000 点，走模型层 145.73 点 —— 差 75.5 倍，一条省 10,854.27 点（108.54 元）。

---

## 预算档位（`budget`）

| 预算 | 点数 | 能做什么 |
|---|---|---|
| 10 元 | 1,000 | 166 张图 / 16 秒 1080P / 111 秒超分 / 5,555 字配音 / 6 条模型层 Seedance |
| 100 元 | 10,000 | 1,666 张图 / 166 秒 1080P / 18 分钟超分 / 68 条模型层 Seedance |
| 1000 元 | 100,000 | 16,666 张图 / 1,666 秒 1080P / 686 条模型层 Seedance / 9 条应用层 Seedance |

同一个预算，走模型层能出更多条；应用层一口价先吃预算。

---

## 快速开始

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"

# 2) 免费：自检 + 报价 + 比价
python3 scripts/run.py doctor
python3 scripts/run.py quote --preset duanju --out 报价
python3 scripts/run.py compare --pages 5

# 3) 换成自己的单量
python3 scripts/run.py sample --preset ecom --out .
python3 scripts/run.py quote --file "电商一条详情（主图 + 短视频）.plan.json" --budget 20000
```

`doctor` 打印 11 项检查，跑之前和跑之后各读一次流水 —— **两次最近一笔完全相同，就是本轮 0 点的硬证据**。

---

## 用法示例

```bash
# 三个内置清单：短剧一集 / 电商一条详情 / 口播一条
python3 scripts/run.py quote --preset duanju
python3 scripts/run.py quote --preset ecom
python3 scripts/run.py quote --preset koubo

# 只打印请求，不联网
python3 scripts/run.py quote --preset duanju --dry-run

# 完全不出网：本地缓存或内置基线（0 请求）
python3 scripts/run.py quote --preset koubo --offline

# 预算超了也要看全表（仍然 0 点）
python3 scripts/run.py quote --preset duanju --allow-over-budget

# 价目总表 + 模型目录构成
python3 scripts/run.py catalog --models

# 机器可读
python3 scripts/run.py quote --preset duanju --json
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点）；本单超它退 5 |
| `--file` / `--preset` | — | 清单文件 / `duanju` `ecom` `koubo` |
| `--out` | — | 写盘目录（`*.quote.json` + `*.quote.md`，或清单样例） |
| `--offline` | — | 完全不出网，0 请求 |
| `--allow-over-budget` | — | 超预算也照报（仍然 0 点） |
| `--pages` / `--all` | 5 / — | 翻几页台账找实测价；`--all` 约 70 页，要 `--yes` |
| `--json` | — | stdout 只有一个 JSON 文档 |
| `--dry-run` | — | 只打印请求，一个都不发 |
| `--yes` | — | 确认批量只读扫描（≥30 个请求时） |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `quote` | **0 点** | 逐项报价 + 合计 + 区间 + 陷阱（核心） |
| `compare` | **0 点** | 应用层 vs 模型层差价排行 |
| `traps` | **0 点** | 五类陷阱逐条摊开 |
| `budget` | **0 点** | 10 / 100 / 1000 元各能做什么 |
| `cost` | **0 点** | 常用四件事 + 三档单量 |
| `catalog` | **0 点** | 价目总表（按口径分组）+ 模型目录 |
| `doctor` | **0 点** | 7 个只读端点 + 价目一致性 + 流水前后比对 |
| `sample` | **0 点** | 写一份清单样例（离线，0 请求） |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（清单格式 / 未知对象 / 选项缩写） |
| `3` | 自检未过 |
| `4` | 缺 `--yes`（批量只读 ≥30 个请求） |
| `5` | 超 `--budget` —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

超预算这条闸门跑在任何请求之前：先用内置基线算一遍，超了就直接退 5。这也是为什么 `quote --preset duanju --budget 500` 是 0.1 秒返回、网络流量为 0。

---

## `--json` 契约

```json
{"ok": true, "estimate": true, "title": "短剧一集（8 分钟成片）",
 "items": [{"kind": "image", "target": "gpt-image-2.6", "pointsBase": 36.0,
            "rangeLow": 36.0, "rangeHigh": 43.2, "src": "流水 sync 实测"}],
 "total": {"pointsBase": 5587.06, "rangeLow": 5587.06, "rangeHigh": 7491.32,
           "yuanBase": 55.87, "rangeLowYuan": 55.87, "rangeHighYuan": 74.91},
 "traps": [{"kind": "wildcard", "text": "落通配：对外 = 上游×2、保底 50 点"}],
 "estimatedPoints": 0, "actualPoints": 0}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "这单基线价 5,587 点（55.87 元）超过 --budget 500 点，一个请求都没发。"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-cost-forecast/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       四个只读端点的原始结构（实测原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 实测记录

```
2026-11-08  只读探针（本轮真实花费 0 点）
  GET  /api/v1/models       316 条 = 221 目录 + 95 裸模型层 ID（带价 92 条，全是文本）
  GET  /api/v1/apps         22 个应用 / 100 个接口（media_services_33 占 29 个）
  GET  /api/v1/me/tasks     1,398 条台账 · 每页 20 条 · 带 actualPrice
  GET  /api/v1/tasks/probe-no-such-task → 200「任务不存在」，0 点
  GET  /user/balance/logs   7,888 条；最近一笔仍是 01:46:12 的 -6（sync:/images/generations）
  五类陷阱计数             ①11 ②3 ③6 ④保底 50 ⑤配对 11 组
```

---

## 免责

- 报价是**预估值**：真实扣费以接口返回的 `usage.points_cost` / 任务台账的 `actualPrice` 为准，失败任务全额退回。
- 模型层单价由你自己账户的历史成交价反推，样本越少偏差越大；没有成交记录时按通配保底报上界，来源字段会写「通配保底」。
- 价目表随时可能变；`doctor` 会把线上价与本地基线逐档比对，价目一动就会提示。
- 按报价单去真正执行时，带 `videoUrl` 的接口只收平台托管地址：本地素材先 `POST /api/v1/upload`（免费）换成 `oss.gpu.likeadmin.cn/openapi/…`，再提交；外站地址会 400 `url_not_allowed`。这一步不占预算。

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
