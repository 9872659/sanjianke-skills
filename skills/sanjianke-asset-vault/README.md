# 素材库管家 · 上传 0 点，11 个应用的素材一表管到底

**上传一个素材 0 点，11 个应用的 22 条 create/remove 入口和 24 小时到期时间，一张表全看清。**

这是「素材管理」不是「生成」。所有生成类包都在教你怎么出片，没有一个包管：素材传到哪了、还能用几小时、这个文件是不是传过、清一次要花多少钱。本包只做这一层。

---

## 实测事实（2026-11-08，本账号 + 只读 GET）

| 事实 | 实测值 |
|---|---|
| 上传价格 | `POST /api/v1/upload` 的规则是 `{"mode":"flat","cost":0,"markupPercent":0}`，明文写着「上传不计费」 |
| 上传返回 | `url` / `path` / `name` / `size` / `mime_type` / `type`；实测 252 B 假 mp4 → `video/mp4`、`type=video` |
| 地址有效期 | **最长 24 小时**，平台可提前回收（文档原文） |
| 缺 file 探针 | `HTTP 200 {"code":0,"msg":"请使用 file 字段提交一个文件","data":null}` |
| 应用目录 | `GET /api/v1/apps` 共 **22 个应用**，其中 11 个有 create/remove 计价规则 |
| 价目表 | `GET /api/v1/pricing` 共 **115 条规则**，22 条是这 11 个应用的 create/remove |
| 应用目录登记 | 只有 `happy_horse` / `wan` / `seedance` 登记了 `create`，只有 `watermark_removal` 登记了 `remove` |
| 任务台账 | `GET /api/v1/me/tasks` 共 **1,398 条**，每页固定 20 条，`limit` 是统计窗口 |

---

## 价目表：create 从 45 点到 11,000 点

| 应用 | create 价 | remove 价 | 默认入口 |
|---|---|---|---|
| smart_clip 智能剪辑 | 45 点/次 | 动态 ×2 | broadcast_mixcut |
| nano_banana 出图 | 72 点/次（带 views 时 25 点/视角） | 动态 ×2 | submit |
| image_human 数字人 | 10 / 15 / 30 / 60 点/输入秒 | 动态 ×2 | submit |
| dressing_diffusion 换装 | 200 点/次 | 动态 ×2 | submit |
| seedsvc 翻唱 | 220 点/次 | 动态 ×2 | submit |
| grok_video | 300 点/次 | 动态 ×2 | submit |
| happy_horse | 650 点/次 | 动态 ×2 | create |
| lipsync 对口型 | 动态 ×3（保底 1 点） | 动态 ×3（保底 1 点） | submit |
| wan 万相视频 | 动态 ×3（保底 1 点） | 动态 ×2 | create |
| watermark_removal | 动态 ×2 | **100 点/次** | remove |
| seedance | **11,000 点/次** | 动态 ×2 | create |

---

## 三条别人不会告诉你的

### 一、`remove` 清理不是免费动作

10 个应用的 remove 是 `cost:0 + markupPercent:100` ——「按上游实际点数 ×2」，价目表不写死单价。
`watermark_removal/remove` 更特殊：它是这个应用的**主业务**「去水印 / 分享链解析」，固定 **100 点/次**。

所以本包把清理拆成两条命令：`prune` 免费只动本地台账，`release` 计费且必须 `--yes`。

### 二、价目表里有 create 规则 ≠ 应用目录登记了 create

价目表按路径前缀匹配，所以每个应用的 `/create` 都能查到一条规则；但 `GET /api/v1/apps` 里真正登记 `create` 的只有 3 个应用。
`catalog` 把两个来源并排打出来，`bind` 默认走「目录登记的那个入口」，你手动指定一个不存在的接口时它会直接拒绝并列出可用入口。

### 三、seedance 的素材三件套按价目表字面是 11,000 点/次

`createGroup` / `createAsset` / `deleteAsset` 在应用目录里登记了，但 `/pricing` 里没有专属规则，命中 `/api/v1/apps/seedance/*` 这条通配规则 = 固定 11,000 点/次。
真正入库的字段是文档级的：`createAsset` 要 `URL` + `GroupId` + `AssetType`，先 `createGroup` 拿 `GroupId`。
其余没有专属规则的接口命中全局通配 `*`：上游实际点数 ×2，单笔保底 50 点。

---

## 实测成交价（`GET /api/v1/me/tasks`，免费）

| 路径 | 笔数 | actualPrice 区间 |
|---|---|---|
| `/api/v1/apps/nano_banana/submit` | 165 | 72 - 72 |
| `/api/v1/apps/wan/create` | 124 | 120 - 2,400（另有三笔 108,000 / 162,000 / 270,000） |
| `/api/v1/apps/smart_clip/realman_broadcast` | 163 | 8.78 - 1,476 |
| `/api/v1/apps/image_human/submit` | 14 | 90 - 12,748.8 |
| `/api/v1/apps/seedance/create` | 7 | 388 - 11,000 |

`cost --live` 会把这些真实成交价排进表里（source=live）；没有历史成交的标 source=pricing。

---

## 九条命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `upload` | 0 点 | 批量上传本地素材 → 本地台账（同文件自动复用地址） |
| `ls` | 0 点 | 台账：剩余小时数 / 标签 / 绑定过哪些应用 |
| `tag` | 0 点 | 打标签、写备注 |
| `prune` | 0 点 | 清掉过期 / 超期的本地台账记录 |
| `catalog` | 0 点 | 11 个应用的 create/remove 两条路 + 单价 + 目录登记 |
| `cost` | 0 点 | 同一份素材投多个应用，逐个报价（`--live` 带真实成交价） |
| `doctor` | 0 点 | 9 个只读探针 + 1 次缺参上传，0 点不建任务 |
| `bind` | **计费** | 把素材登记进某个应用，要 `--yes`，受 `--budget` 管 |
| `release` | **计费** | 调应用的 remove 做远端清理，要 `--yes` |

---

## 用法

```bash
# 1) 上传：一个文件 0 点，批量也能一次给
python3 scripts/run.py upload --file 产品图.png --tag product --note "白底主图"
python3 scripts/run.py upload --dir ./素材 --tag 双11

# 2) 台账：id / 剩余小时数 / 标签 / 绑定过哪些应用
python3 scripts/run.py ls
python3 scripts/run.py tag --id e424e6c0 --tag cover --note "主图"

# 3) 比价：同一份素材投给谁最便宜
python3 scripts/run.py cost --apps smart_clip,wan,seedance --seconds 10
python3 scripts/run.py cost --live --pages 5

# 4) 登记：先干跑看请求体，再 --yes 真提交
python3 scripts/run.py bind --app nano_banana --id e424e6c0 --dry-run
python3 scripts/run.py bind --app nano_banana --id e424e6c0 --yes

# 5) 清理：本地免费，远端计费
python3 scripts/run.py prune
python3 scripts/run.py release --app watermark_removal --param url=https://v.douyin.com/xxx/ --yes
```

`bind` 把素材地址注入到该应用文档里的字段：nano_banana / dressing_diffusion 等用 `image_url`，happy_horse 用 `media`，watermark_removal 用 `url`。
wan / seedance 的素材在数组里，本包不猜，要求你用 `--param` 明确给：

```bash
python3 scripts/run.py bind --app wan --id e424e6c0 \
  --param 'image_urls=["https://oss.gpu.likeadmin.cn/openapi/..."]' \
  --param model=wan2.7 --param prompt="复古跑车沿海岸公路" --seconds 10 --yes
```

---

## 三步上手

```bash
# 第 1 步：自检（9 个只读探针 + 1 次缺参上传，0 点、不建任务）
python3 scripts/run.py doctor

# 第 2 步：看价（免费，两个应用起就能横评）
python3 scripts/run.py catalog
python3 scripts/run.py cost --apps nano_banana,smart_clip,grok_video

# 第 3 步：传一个素材，登记进最便宜的那个
python3 scripts/run.py upload --file 首图.png --tag cover
python3 scripts/run.py bind --app smart_clip --id <id> --param ... --yes
```

```
√ 余额可用（冻结 0）   √ 115 条规则 / 22 条 create+remove 全在
√ 22 个应用 / 11 个目标应用全在   √ 上传规则 cost=0
√ 上传探针 HTTP 200 code=0   √ 任务查询   √ 我的任务台账可读   √ 流水可读
```

---

## 零依赖、两道闸门

- **零依赖**：只要 Python 3.7+，不装任何第三方包。
- **默认 0 点**：7 个免费命令不写任何计费接口；`bind` / `release` 才动钱。
- **两道闸门**：缺 `--yes` 退 `4` 并说清要花多少点；预计超 `--budget` 退 `5`，**一个请求都不发**；`--budget 0` 对只读命令也直接退 5。
- **干跑**：`--dry-run` 打印将发出的完整请求体和价格，不提交、不冻结。
- **Key 三选一**：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。

---

## 目录结构

```
sanjianke-asset-vault/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       端点实测原文、22 条规则、字段表
│   └── troubleshooting.md    排错：按现象找原因
└── scripts/
    ├── a7w.py                零依赖客户端（家族逐字节一致）
    └── run.py                本包命令层（默认只发 GET + 免费 upload）
```

台账落在 `~/.a7w/asset-vault/ledger.json`，只存本机，不上传任何地方。

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
