# 视频生成台 · 模型层
**一条 Seedance 片子：应用层 11,000 点，模型层 145.73 点。** 同一段提示词、同一个模型，走 `POST /api/v1/videos` 就是省 75 倍；Seedance 2.5 省 14 倍、Wan 3.0 省 2.7 倍。异步两步、零依赖，全部走 [api.a7w.cn](https://api.a7w.cn/)。

| 模型层 ID | 实测成交 | 应用层一口价 | 倍数 |
|---|---|---|---|
| `sd/doubao-seedance-2-0-260128` | **145.73 点** | 11,000 点 | **75.5 倍** |
| `volcengine/doubao-seedance-2-5-260628` | 762.30 点 | 11,000 点 | 14.4 倍 |
| `wan3.0-video` | 300 点 | 800 点 | 2.7 倍 |

1 元 = 100 点。最便宜的一档 **1.46 元一条**。

---

## 同一个模型，两条路差 75 倍

| 走法 | 端点 | 价格 |
|---|---|---|
| 应用层 | `POST /api/v1/apps/seedance/submit` | 一口价 **11,000 点**（110 元） |
| 模型层 | `POST /api/v1/videos`，`model` 填模型层 ID | 实测最低 **145.73 点**（1.46 元） |

11,000 ÷ 145.73 = 75.5 倍。Seedance 2.5 走模型层是 762.30 点，也是 11,000 ÷ 762.30 = 14.4 倍。
跑的是同一个模型，差价来自**计费口径**，不是画质。

---

## 价目表（模型层实测 vs 应用层）

| 模型（模型层 ID） | 实测成交 | 应用层 | 倍数 | 干什么 |
|---|---|---|---|---|
| `sd/doubao-seedance-2-0-260128` | **145.73 点** | 11,000 点 | **75.5 倍** | Seedance 2.0 标准版，同族最便宜 |
| `volcengine/doubao-seedance-2-5-260628` | 762.30 点 | 11,000 点 | 14.4 倍 | Seedance 2.5 旗舰版，画质最强 |
| `wan3.0-video` | 300 点 | 800 点 | 2.7 倍 | Wan 3.0，8 条成交全是 300 点 |
| `muse-video` | 11 点/秒（5 秒 55 点） | 无同款 | — | 720P 带声音，4–180 秒 |

- 「实测成交」取自 `GET /api/v1/me/tasks` 的 `actualPrice`：5 条 / 3 条 / 8 条 / 8 条样本。
- 先冻结后结算，任务失败**全额退回**；参数被校验拦下（400）不建任务、不扣费。

---

## 三条别人不会告诉你的

### 一、模型层单价不在价目表里

`GET /api/v1/pricing` 的 115 条规则里没有一条写模型层单价：全表没有 `modelPricing` 键，
`modelRates` 只出现在 3 条 `image_human` 规则上，含义是**按请求体 `mode` 取费率**：

```json
"modelRates": {"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}}
```

模型层命中的是通配 `*`：

```json
```

所以本包读**你自己的流水** `GET /api/v1/me/tasks`：每条任务带 `model` / `path` /
`actualPrice` / `reservePrice` / `rateNote`（模型层恒为「官方价 × 2.00」）。
按 model 归集就是你的真实成交价，行尾标 `live`；没跑过这个模型的账号退到本机
2026-11-07 实测基线，行尾标 `baseline`。

### 二、轮询一次就是一次的钱

应用层的 `POST /api/v1/apps/<app>/query` **按次计费**：`nano_banana/query` 72 点/次，
历史上有账号光轮询烧掉 15,552 点。模型层不用它，三条查询都免费：

| 路由 | 认哪种 id | 给什么 |
|---|---|---|
| `GET /api/v1/tasks/{id}` | `task_` 开头 | `status` / `progress` / `finished_at` |
| `GET /api/v1/videos/{id}` | `task_` 开头（Muse 族） | `video_url` / `expires_at` / `size` |
| `GET /api/v1/videos/generations/{id}` | **UUID（Seedance 族）** | `generation_status` / `video_url` / `video_url_expires_at` |

同一个 Seedance UUID 打到 `/tasks` 回 `404 page not found`、打到 `/videos` 回 400
`task_not_exist`，只有 `/videos/generations/{id}` 认得它。`status` / `wait` 三条都试，
`wait` 每 15 秒查一次，查一次 0 点。

### 三、探针要挑对模型

「合法 model + 缺 prompt」确实停在校验层，但结果按模型分三种：

| 探针 body | 返回 | 钱包 |
|---|---|---|
| `{}` | 400 `Model name not specified` | 不动 |
| `{"model":"muse-video"}` | 400 `field prompt is required` | 不动 |
| `{"model":"sd/doubao-seedance-2-0-260128"}` | 400 `prompt or content field is required` | 不动 |
| `{"model":"volcengine/doubao-seedance-2-5-260628"}` | 400 `prompt or content field is required` | 不动 |
| `{"model":"wan3.0-video"}` | **502 百炼提交失败** | **先冻 300 点再退** |

最后一条是本轮唯一动过钱包的调用：`reserve_sync:/api/v1/videos -300` →
`refund:submit_failed:/api/v1/videos +300`，净 0 点。所以 `doctor` 只探前三条，
`wan3.0-video` 一次都不探。

---

## 完整链路（提交 → 查询 → 下载）

```bash
# 1) 提交
POST /api/v1/videos
{"model": "sd/doubao-seedance-2-0-260128", "prompt": "山间的雾慢慢飘过松林，镜头缓慢推进", "seconds": 5}
# → {"id": "task_xxx", "object": "video", "status": "queued"}

# 2) 查询（免费，三种 id 形态都认）
GET /api/v1/tasks/task_xxx                  # task_ 开头：状态 / 进度
GET /api/v1/videos/task_xxx                 # Muse 族：成片 video_url 与 expires_at
GET /api/v1/videos/generations/<uuid>       # Seedance 族：generation_status 与 video_url

# 3) 下载
curl -o out.mp4 "<video_url>"
```

图片输入：`input_reference`（首帧，URL 或 data URL）、`images`（多图参考）。
本地图用 `gen --first-frame 首帧.jpg` 或 `--ref 参考.jpg`，脚本自动转 data URL。
成品链接有期限：实测 Muse 的 `expires_at` 在 7 天后、Seedance 的 `video_url_expires_at`
是 24 小时，以返回值为准，拿到就转存。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检：Key / 模型目录 / 价目通配 / 3 个零扣费探针 / 2 条查询 / 报价数据源
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --model sd/doubao-seedance-2-0-260128 --seconds 5

# 4) 先看请求，再真跑
python3 scripts/run.py gen --prompt "山间的雾慢慢飘过松林，镜头缓慢推进" --seconds 5 --dry-run
python3 scripts/run.py gen --prompt "山间的雾慢慢飘过松林，镜头缓慢推进" --seconds 5 --yes --wait

# 5) 只查不重提
python3 scripts/run.py status task_xxx
```

---

## 常用命令

```bash
python3 scripts/run.py catalog                                    # 4 个模型 + 报价来源 + 应用层对照
python3 scripts/run.py cost                                       # 4 档报价区间与闸门
python3 scripts/run.py cost --model muse-video --seconds 30        # 单档精算
python3 scripts/run.py gen --prompt "…" --seconds 5 --dry-run      # 只打印请求
python3 scripts/run.py gen --model volcengine/doubao-seedance-2-5-260628 \
    --prompt "…" --seconds 5 --yes --wait
python3 scripts/run.py gen --prompt "…" --seconds 8 --size 720x1280 --yes
python3 scripts/run.py gen --prompt "…" --seconds 5 --first-frame 首帧.jpg --yes
python3 scripts/run.py gen --prompt "…" --extra '{"ratio":"9:16","resolution":"720p"}' --yes
python3 scripts/run.py status task_xxx                            # 三条免费查询合并
python3 scripts/run.py wait task_xxx --outdir .                   # 等完成并下载
python3 scripts/run.py log --limit 10
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--model` | `sd/doubao-seedance-2-0-260128` | 模型层 ID，见 `catalog` |
| `--prompt` | 必填 | 提示词，最多 4000 字（主体 + 怎么动 + 镜头） |
| `--seconds` | 5 | 秒数 1–180（`muse-video` 是 4–180） |
| `--size` | 不传（muse-video 补 1280x720） | `1280x720` 横屏 / `720x1280` 竖屏 |
| `--first-frame` | — | 首帧图，本地路径或 URL，走 `input_reference` |
| `--ref` | — | 参考图，可重复；第 1 张是开头画面 |
| `--extra` | — | 额外参数 JSON，例如 `{"ratio":"9:16"}` |
| `--pages` | 2 | 读多少页 `/me/tasks` 报价（每页 20 条；0 = 只用基线） |
| `--budget` | 3500 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实出片 / 只打印请求 |
| `--wait` / `--every` / `--limit` | — / 15 / 3600 | 提交后等到完成并下载 / 轮询间隔 / 等待上限 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 4 个模型层模型 + 报价来源 + 应用层对照 |
| `cost` | 免费 | 报价区间与闸门（读你的成交价） |
| `doctor` | 免费 | 10 项自检：Key / 模型目录 / 价目通配 / 3 个探针 / 3 条查询 / 报价源 |
| `gen` | **按模型计费** | 提交任务（要 `--yes`）；`--wait` 等到完成并下载 |
| `status` | 免费 | `/tasks/{id}` + `/videos/{id}` + `/videos/generations/{id}` 合并 |
| `wait` | 免费 | 等任务完成并下载 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（参数缺失、秒数越界、选项缩写） |
| `3` | 自检不过（`doctor` 出现 ×） |
| `4` | 需要确认 —— 缺 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 等待超时 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "id": "task_xxx", "status": "queued",
 "model": "sd/doubao-seedance-2-0-260128", "seconds": 5,
 "quote": {"model": "…", "source": "live", "low": 145.73, "high": 181.79, "gate": 181.79},
 "gatePoints": 181.79}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`

`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`；`--json` 写在子命令**前后都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-model-video/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测返回原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 计费口径与保底

- 模型层单价**不在** `/api/v1/pricing` 里；成交价从 `GET /api/v1/me/tasks` 的 `actualPrice` 反推。
- 预冻结按上限冻（Seedance 两档 3,000 点、Wan 3,000 点以下 300 点），完成按实际结算。
- 任务失败全额退回；参数被校验拦下（400）不建任务、不扣费。
- `--budget` 按**报价上限**判定：宁可拦住一条，也不让一次冻结超支。
- 查询、轮询、看余额全部 0 点：`GET /api/v1/tasks/{id}`、`GET /api/v1/videos/{id}`、`GET /user/balance`、`GET /user/balance/logs`。

---

## 合规与边界

- 生成内容的合规责任在使用者：请用于有授权的素材与合法用途。
- 真实扣费以任务完成后 `/tasks/{id}` 或 `/me/tasks` 的 `actualPrice` 为准，`cost` 给的是报价区间。
- 成品链接有期限（Muse 实测 7 天、Seedance 24 小时），以返回的过期时间为准，请及时转存。
- 同一条任务只查不重提：重提就是再花一次。

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
