# 模型比价器 · 同一个模型差 75 倍

> 同一个 Seedance，走应用层 **11,000 点**（¥110），走模型层 **762.30 点**（¥7.62）。
> 这条命令把全站这种差价一次翻出来，按倍数排序。

`api.a7w.cn` 的价目表里只写了「应用层」一口价。模型层那批接口
（`/api/v1/videos/generations`、`/api/v1/images/generations`、`/api/v1/tasks`、`/api/v1/videos`）
所以模型层的单价只能从自己的流水反推 —— 本包就是干这个的。

零依赖，只用 Python 标准库，只用 Python 3.7+。

---

## 一、装好就能跑的三步

```bash
# 1. 填 Key（也可以在 http://api.a7w.cn 注册后自己 export A7W_API_KEY）
python3 scripts/a7w.py login --key sk-你的key

# 2. 自检三个只读端点（0 点）
python3 scripts/run.py doctor

# 3. 看差价排行（0 点）
python3 scripts/run.py app-vs-model
```

`doctor` 的输出长这样：

```
自检（3 个只读 GET，扣 0 点）

  √ 模型目录 GET /api/v1/models    目录 221 · 模型层 ID 95 · 带模型层价目 92 · seedance 系 7
  √ 应用目录 GET /api/v1/apps      22 个应用 · 接口 100 个
  √ 应用层定价覆盖率               21 / 22 有专属规则；掉进通配的：media_services_33
  √ 模型层单价不在价目表里         3 / 4 条模型层路径没有专属规则；modelRates 只出现在 3 条规则上（image_human）
```

---

## 二、差价表（2026-11-07 真跑出来的）

| # | 能力 | 应用层路径 | 应用层价 | 模型层模型 | 模型层实测 | 倍数 |
|---|---|---|---|---|---|---|
| 1 | 出视频 | `/apps/seedance/submit` | 11,000 | `sd/doubao-seedance-2-0-260128` | 145.73 | **75.5×** |
| 2 | 出视频 | `/apps/seedance/submit` | 11,000 | `volcengine/doubao-seedance-2-5-260628` | 762.30 | **14.4×** |
| 3 | 出图 | `/apps/aigc_wan_image/generate/index` | 203 | `gpt-image-2` | 26 | 7.8× |
| 4 | 出图 | `/apps/aigc_photo_restore/*` | 105 | `seedream-5-0-flash` | 15.60 | 6.7× |
| 5 | 出图 | `/apps/dressing_diffusion/submit` | 200 | `gpt-image-2-pro` | 39 | 5.1× |
| 6 | 出图 | `/apps/nano_banana/submit` | 72 | `seedream-5-0-flash` | 15.60 | 4.6× |
| 7 | 出图 | `/apps/aigc_qwen_image/generate/index` | 78 | `gpt-image-2` | 26 | 3.0× |
| 8 | 出图 | `/apps/nano_banana/submit` | 72 | `gpt-image-2` | 26 | 2.8× |
| 9 | 出视频 | `/apps/wan/submit` | 800 | `wan3.0-video` | 300 | 2.7× |
| 10 | 出图 | `/apps/aigc_qwen_image_pro/generate/index` | 105 | `gpt-image-2-pro` | 39 | 2.7× |

**前两条是同一个模型**（两个 `doubao-seedance-*` 都是 Seedance，应用层 `seedance` 跑的就是它）；
第 3 条起是同一件事（出一张图），表里都标了口径。应用层价来自 `GET /api/v1/pricing` 的实时规则，
模型层价来自 `GET /api/v1/me/tasks` 的**真实成交价**（取实测最低那一笔）。

---

## 三、价目表里五个陷阱

| # | 陷阱 | 实测数字 |
|---|---|---|
| ① | 价目表里有、路由 404 | **11 个 `tsc_*` 档位**：`tsc_common` / `tsc_common_hd` / `tsc_aigc` / `tsc_aigc_hd` / `tsc_shortplay` / `tsc_shortplay_hd` / `tsc_uhd` / `tsc_oldsd` / `tsc_oldsd_hd` / `tsc_teshd` / `tsc_quality`，每条都写着 2~6 点/秒、保底 10 点 |
| ② | 路由在、上游凭据坏 | `/video/tencent1080`（2 点/秒）/ `tencent2k`（4）/ `tencent4k`（8）→ 502 `InvalidMpsUser`；本账号腾讯 4K 任务全部 `refunded`，实扣 0 点 |
| ③ | 应用层 vs 模型层 | seedance 11,000 点 vs 762.30 点 = **14.4 倍**；同族 2.0 更低到 145.73 点 = **75.5 倍** |
| ④ | 单位混用 | `shot`（20）/ `castcrew`（25）/ `delogo`（25）含 viapi 版共 6 条，note 写「点/次」，rule 是 `per_second` → 10 秒素材按 10 倍扣 |
| ⑤ | 通配保底 | 未单独定价的接口 = 上游点数 × 2、单笔保底 50 点；模型层四条路径里三条落在这一条下面 |

---

## 四、我要做 X，最便宜怎么走

| 我要 | 最便宜的路 | 价 | 最贵的那条 |
|---|---|---|---|
| 一张图 | `gpt-image-2`（模型层 `/tasks`） | 26 点 / ¥0.26 | `aigc_wan_image` 203 点 / ¥2.03 |
| 一条视频 | `muse-video`（模型层 `/videos`） | 44 点 / ¥0.44 | `seedance` 11,000 点 / ¥110 |
| 一段配音 | 语音 TTS | 实测 1~66 点 | `mmaudio` 495 点 / ¥4.95 |
| 超分 1 分钟 | VIAPI 超分·标准 | 9 点/秒 = 540 点 | `/video/upscale` 30 点/秒 = 1,800 点 |
| 画质增强 1 分钟 | 画质综合增强 15 点/秒 | 900 点 | 视频修复 36 点/秒 = 2,160 点 |

---

## 五、六个子命令

| 命令 | 干什么 | 花费 |
|---|---|---|
| `app-vs-model` | 应用层 vs 模型层差价排行（本包核心） | **0 点** |
| `cheapest --for image\|video\|voice\|upscale` | 按意图给最便宜的路 | **0 点** |
| `traps` | 价目表「看着有、实际不通」清单 | **0 点** |
| `budget` | 按典型用量算预算 | **0 点** |
| `catalog --type video\|image\|text` | 模型清单（按类型分组） | **0 点** |
| `doctor` | 自检三个只读端点 + 应用层定价覆盖率 | **0 点** |

```bash
python3 scripts/run.py app-vs-model --all --yes          # 翻完 70 页台账（仍 0 点）
python3 scripts/run.py app-vs-model --stat median        # 模型层取中位数
python3 scripts/run.py cheapest --for video --live       # 把模型层实测价排进来
python3 scripts/run.py cheapest --for upscale --json     # 给程序读
python3 scripts/run.py budget                            # 10 秒视频 / 一张图 / 一分钟语音
python3 scripts/run.py catalog --type image --limit 20
```

---

## 六、为什么全程 0 点

- 三个数据端点 + 一个台账端点，**全是只读 GET**：`/api/v1/pricing`、`/api/v1/models`、
  `/api/v1/apps`、`/api/v1/me/tasks`。
- `run.py` 的 `http_json` 只接受 `GET`，传别的当场抛 `usage`，**不会走到网络**。
  源码里不存在 `POST` / `PUT` / `DELETE` / `submit` / `create` 之类写操作。
- 实测证明：跑完全部子命令前后各读一次 `/user/balance`，
  余额 `999997393482.2579` 点 → `999997393482.2579` 点，**分毫不差**；
  `/user/balance/logs` 在同一个时间窗口内**新增 0 条**扣费流水。

`--budget` 依旧生效：给 `--budget 0` 直接退 `5`，一个请求都不发。

---

## 七、`--json` 契约

```json
{"ok": true, "stat": "min", "count": 10,
 "rows": [{"cap": "出视频", "appPath": "/api/v1/apps/seedance/submit",
           "appPoints": 11000, "model": "volcengine/doubao-seedance-2-5-260628",
           "modelPoints": 762.3, "times": 14.4, "sameModel": true}],
 "estimatedPoints": 0}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "..."}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 八、文件结构

```
sanjianke-price-radar/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       三个端点的原始结构（实测原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致）
    └── run.py                本包命令层
```

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
