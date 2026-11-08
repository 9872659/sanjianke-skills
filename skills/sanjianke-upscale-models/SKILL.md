---
name: sanjianke-upscale-models
slug: sanjianke-upscale-models
displayName: 超分模型台 · 3 条线比价，1080P 一分钟 5.4 元
description: "1080P 一分钟 5.4 元、10 分钟 4K 120 元——三条超分线（VIAPI 9/15/20 点每秒、腾讯 2/4/8、模型层 50 点起）放进一个命令。腾讯同规格只要 1.2 元，当前 502 InvalidMpsUser（失败全额退）；catalog 先标哪条可用，compare 按秒报三线价并给推荐，--tier 一条命令下单。附腾讯 502、Topaz 404、Recraft 端点冻 20 退 20 的流水原文，先看清再点。技术微信：9872659。"
version: 1.0.0
summary: "同一段 480P 素材提到 1080P，三条线的价差是 4.5 倍：腾讯 2 点/秒（60 秒 120 点 = 1.2 元）、VIAPI 9 点/秒（540 点 = 5.4 元）、4K 旗舰 30 点/秒（1800 点 = 18 元）。腾讯最便宜，但 2026-11-07 完整参数实测 502 FailedOperation.InvalidMpsUser，本账号 3 条腾讯 4K 任务全部 refunded、chargedPoints=0，钱全额退回，这条路暂时走不通。VIAPI 三档空 body 实测 400 empty_url，路由在架，是现在能直接跑的一条。模型层 4 个超分模型（Topaz 视频 / Topaz 图像 / Recraft / Grok）在 /api/v1/models 目录里，但 /api/v1/pricing 的 115 条规则没有它们的单价，只命中通配「上游点数 x 2、单笔保底 50 点」；真实价要从 /api/v1/me/tasks 的 actualPrice 反推。Topaz 视频实测 404 model_not_found，Recraft 端点流水出现过先冻 20 点再全退。本包把「能用 / 暂时不通 / 待验证」做成第一列，doctor 用 7 个空 body POST 停在参数校验，14 个请求全部 0 点。技术微信：9872659。"
license: MIT
tags:
  - 三剪客
  - 视频超分
  - 模型比价
  - api.a7w.cn
---

# 超分模型台 · 3 条线比价，1080P 一分钟 5.4 元

一条 10 分钟 1080P 老片：VIAPI 现可用 54 元；腾讯同规格 12 元，当前 502 全额退；模型层 50 点起。

## 三条线，一张表

| 线路 | 档位 | 单价 | 60 秒 | 现状 |
|---|---|---|---|---|
| VIAPI | 标准超分 1080P | 9 点/秒 | 540 点 = 5.40 元 | 可用，空 body 400 empty_url |
| VIAPI | 高清超分 2K | 15 点/秒 | 900 点 = 9.00 元 | 可用 |
| VIAPI | 超清 4K | 20 点/秒 | 1,200 点 = 12.00 元 | 可用 |
| 腾讯 MPS | 1080P | 2 点/秒，保底 10 点 | 120 点 = 1.20 元 | 暂时不通，502 InvalidMpsUser |
| 腾讯 MPS | 2K | 4 点/秒，保底 10 点 | 240 点 = 2.40 元 | 暂时不通 |
| 腾讯 MPS | 4K | 8 点/秒，保底 10 点 | 480 点 = 4.80 元 | 暂时不通 |
| FlashVSR 应用 | 超分 | 10 点/秒，保底 20 点 | 600 点 = 6.00 元 | 可用，实测 settled 72.348 点 |
| 4K 旗舰 | `/video/upscale` | 30 点/秒 | 1,800 点 = 18.00 元 | 待验证，7 条历史任务全退 |
| 模型层 | Topaz 视频优化 | 50 点/次起 | 按次 | 未授权，404 model_not_found |
| 模型层 | Topaz 图像优化 | 50 点/次起 | 按次 | 待验证，需 image_url |
| 模型层 | Recraft 图像优化 | 50 点/次起 | 按次 | 待验证，需 image |
| 模型层 | 放大 Grok 视频 | 50 点/次起 | 按次 | 待验证，需本账号 task_id |

1 元 = 100 点。按秒线按**输入视频秒数**计费，最小计 1 秒；腾讯保底 10 点，FlashVSR 保底 20 点。

## 三条干货

### ① 腾讯 502 是上游凭据坏了，不是价格问题

完整参数提交 → `502 FailedOperation.InvalidMpsUser`「invalid mps user」。
本账号 3 条腾讯 4K 任务全部 `status=refunded`、`chargedPoints=0`、`refundedPoints=120/48`。
钱一分没少，但这条路现在走不通。空 body 仍然回 `400 video_url_required`，说明**端点本身在架**，
坏的是网关到腾讯云 MPS 的那段凭据。`catalog` 因此把腾讯三档标成「暂时不通」，
`submit` 默认拦下，避免点了才报错。

### ② 模型层单价不在价目表里，只能从流水反推

`GET /api/v1/pricing` 的 115 条规则里没有 `/api/v1/videos`、`/api/v1/videos/generations`、
`/api/v1/images/generations`。它们命中通配：

```json
```

所以模型层只能读自己的 `GET /api/v1/me/tasks`（免费），按 `model` 归集 `actualPrice`。
有成交样本标 `source=live`；没有就标 `source=baseline`，只报「50 点起（通配保底）」，
不编单价。本账号 1,398 条任务里，4 个模型层超分模型 0 条成交样本，所以 4 个全是 baseline。

### ③ 目录里有，不等于当前 Key 能调

`/api/v1/models` 有 316 条，4 个超分模型都在。但：

- `POST /api/v1/videos {"model":"topaz-video-upscale"}` → `404 model_not_found`
- `POST /api/v1/images/generations {"model":"recraft-crisp-upscale"}` → 端点流水里出现过先 `reserve_sync` 冻 20 点，
  再 `refund` 20 点，净 0；缺的是 `image` 素材
- `grok-imagine-upscale` 只收本账号已完成的 Grok 视频 `task_id`，外部视频喂不进去

`catalog` 把「目录在架」和「当前可调」分开标，`doctor` 只做零扣费验证。

## 完整用法

```bash
# 1) 免费：12 条路线 + 单价 + 状态（不用 Key）
python3 scripts/run.py catalog

# 2) 免费：先算钱（1/5/10/30/60 分钟）
python3 scripts/run.py cost --seconds 600
python3 scripts/run.py cost --tier superres4k --seconds 600

# 3) 免费：三线比价 + 推荐
python3 scripts/run.py compare --target 1080p --seconds 60
python3 scripts/run.py compare --target 4k --seconds 600

# 4) 免费：同一需求多模型横评（要 Key，只读 /me/tasks）
python3 scripts/run.py models --models topaz-video-upscale,recraft-crisp-upscale

# 5) 免费：自检 Key / 价目表 / 模型 / 7 个端点
python3 scripts/run.py doctor

# 6) 免费：上传素材，拿平台托管地址
python3 scripts/run.py upload --file low.mp4

# 7) 真提交（要 --yes，受 --budget 管）
python3 scripts/run.py submit --tier superres --video-url "https://..." --seconds 60 --yes

# 8) 查任务（免费）
python3 scripts/run.py status --task-id task_xxx --tier superres
```

全局选项写在子命令前后都可以：`--json` / `--key` / `--host` / `--budget` / `--max-tokens`。

## 三步上手

1. **看**：`python3 scripts/run.py catalog` —— 先看「状态」列，绿色 √ 才是现可用的。
2. **算**：`python3 scripts/run.py compare --target 1080p --seconds 60` —— 一行给出推荐和「腾讯修好后能省多少」。
3. **跑**：`python3 scripts/run.py submit --tier superres --video-url "你的地址" --seconds 60 --yes` —— 先 `upload` 拿地址，再提交。

## 规格

- **输入**：mp4 / mov / mkv 等公网可访问地址，或先用 `upload`（multipart，字段名 `file`，免费）拿平台地址。
- **输出**：`taskId` + 状态；查询走 `GET /api/v1/tasks/{id}`（模型层）、`GET /api/v1/videos/{id}`（腾讯 / 通用）、`GET /api/v1/video/viapi/result/{id}`（VIAPI），查询免费。
- **计费**：1 元 = 100 点；按秒线按输入秒数；腾讯保底 10 点、FlashVSR 保底 20 点；失败任务全额退回，实扣看 `netPoints`。
- **双闸门**：缺 `--yes` → exit 4（先告诉你要花多少点）；预计点数超 `--budget` → exit 5，一个请求都不发。
- **退出码**：0 成功 / 2 用法错 / 3 自检未过 / 4 需 `--yes` / 5 预算不足 / 6 调用失败 / 1 内部错 / 130 中断。
- **JSON 契约**：成功 `{"ok":true,...}`；失败 `{"ok":false,"exit":N,"error":{"kind","message"}}`。
- **零依赖**：只用 Python 标准库；不内嵌 Key，`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。

## 和已有超分包的分工

| 包 | 管什么 | 什么时候用它 |
|---|---|---|
| `sanjianke-vr-superres` / `-2k` / `-4k` | 只做 VIAPI 单档：规格、ffprobe 体检、单档提交 | 已经确定走 VIAPI 某一档 |
| `sanjianke-mps-upscale` | 只做腾讯 MPS 三档 | 腾讯 502 修好、要 2/4/8 点每秒 |
| `a7w-flashvsr` | 只做 FlashVSR 应用单档 | 只跑 FlashVSR，按 `input_url` 提交 |
| `sanjianke-vr-upscale-4k` | 只做 `/video/upscale` 4K 旗舰 | 明确要 4K 旗舰版 |
| **本包** | 三线比价 + 4 个模型层横评 + 能用/不通状态标记 | **还不知道选哪条，先比价** |

本包不替代上面任何一个：单档深做看专包，跨线选型看本包。两者共用同一套 `api.a7w.cn` Key。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
