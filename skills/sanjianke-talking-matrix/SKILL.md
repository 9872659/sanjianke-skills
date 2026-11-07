---
name: sanjianke-talking-matrix
slug: sanjianke-talking-matrix
displayName: 口播矩阵 3 形象 × 4 音色一次出 12 条
description: "**3 个形象 × 4 个音色 = 12 条口播，一条命令跑完，约 2,564 点（25.64 元）。** 一段文案进来，配音只做 4 次 —— 每个音色一次，复用到 12 条视频里，这是矩阵最省的一刀。三个应用：voice_tts 配音 0.18 点/字、pic_lipsync 图片数字人 15 点/秒、image_human 全驱数字人 10/15/30/60 点/输入秒。上传/配音/提交/轮询/断点续跑都进 state，重跑只补没跑完的，配过音的音色不再付第二次钱。付费 submit 只发一次，重试只在免费的上传与轮询；轮询只走 GET /tasks/<id>。cost 先算钱、--budget 超了退 5 零请求、--yes 缺了退 4 报点数，doctor 只读 GET。零依赖。需要自备 API Key，注册见 https://api.a7w.cn/ 。技术微信 9872659。"
version: 1.0.0
summary: "算账：60 字约 14 秒，单条 lipsync 210 点；3 形象 × 4 音色 = 12 条，配音 4 次 44 点 + 视频 2,520 点 = 2,564 点（25.64 元）。配音每个音色只做一次，复用音频，省掉 N-1 次重复合成。三个应用：voice_tts/tts 同步配音（≤500 字，直回 audio_url；33 字上游 1.98 点→我方 5.94 点）；pic_lipsync/submit 图片数字人，档位真名是 quality，按上游实际点数 ×5 即 15 点/秒；image_human/submit 全驱四档 fast 10 / standard 15 / 2k 30 / 4k 60 点/输入秒，mode 必须显式给 —— schema 默认 standard、计费卡默认 fast。链路：上传图 0 点 → 逐音色配音 → 笛卡尔积提交 → 并发轮询 → 按 {prefix}_{序号}-{形象}_{音色}.mp4 落盘。state 存每条的 task_id、成片与点数，断点续跑成立；文案指纹进 key，换文案不误用旧音频。付费 submit 只发一次，中断记 unknown 先对账；重试只在免费环节；轮询只走 GET /tasks/<id>。零依赖。需要自备 API Key，注册见 https://api.a7w.cn/ 。技术微信9872659。"
license: MIT
tags:
  - 三剪客
  - 数字人
  - 口播矩阵
  - 批量出片
  - api.a7w.cn
---

# 口播矩阵 · 一段文案 × N 个形象 × M 个音色

> **先申请你自己的 API Key。** 本包不内嵌 Key，扣的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的账户余额。
> 存起来只要一条命令：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**一段文案，3 个形象 × 4 个音色 = 12 条口播，一条命令，约 2,564 点（25.64 元）。**
配音只做 4 次，视频做 12 次 —— 这就是矩阵和「跑 12 遍单条」的全部差别。

## 价目表（`GET /api/v1/pricing` 现查，1 元 = 100 点）

| 环节 | 接口 | 单价 |
|---|---|---|
| 配音 | `voice_tts/tts` | **0.18 点/字**（上游实际点数 ×3；33 字实测 5.94 点）|
| 视频 · lipsync | `pic_lipsync/submit` | **15 点/秒**（上游实际点数 ×5）|
| 视频 · human fast | `image_human/submit` | **10 点/输入秒** |
| 视频 · human standard | 同上 | **15 点/输入秒** |
| 视频 · human 2k / 4k | 同上 | **30 / 60 点/输入秒** |
| 上传 | `POST /api/v1/upload` | **0 点**（24 小时有效）|
| 轮询 | `GET /api/v1/tasks/<id>` | **0 点** |
| 建专属音色 | `voice_tts/clone_voice` | 600 点/次 |

| 矩阵规模（60 字 / 14 秒） | 成片 | 点数 | 元 |
|---|---|---|---|
| 1 × 1 | 1 条 | 221 | 2.21 |
| 2 × 2 | 4 条 | 862 | 8.62 |
| **3 × 4** | **12 条** | **2,564** | **25.64** |
| 5 × 6 | 30 条 | 6,366 | 63.66 |

实测锚点：`tts_live` 33 字上游 1.98 点 → 我方 5.94 点；`/pricing` 115 条规则里三张卡都在；
`/apps` 22 个应用、`list_voices` total=58（2026-11-07 现查）。

**两处口径写清楚：** lipsync 单笔保底 50 点（短文案按 50 兜底，钱不会算少）；human 带上 `duration`
价格才被费率卡锁死 = 费率 × 秒数，所以 `--engine human` 要求给秒数。

## 两个引擎怎么选

| 场景 | 引擎 | 价格 | 一句话 |
|---|---|---|---|
| 图 + 文案，口型自然，最常用 | `lipsync`（pic_lipsync）| 15 点/秒 | 便宜、稳、参数少 |
| 先跑量看效果，预算优先 | `lipsync --quality fast` | 15 点/秒起 | 档位真名是 `quality` |
| 要 2K / 4K 成片 | `human --mode 2k` / `4k` | 30 / 60 点/输入秒 | 贵 2–4 倍，画质优先 |
| 已有录音，只想对口型 | `human` + `--audio` | 按输入秒 | 跳过配音，省一笔 |

## 三条别人不会告诉你的口径

1. **配音要乘 M，不要乘 N × M。** 同一段文案、同一个音色，音频只合成一次就够 4 个形象复用。
   按 N × M 算配音费是最常见的估错方式，本包 `cost` 直接按 M 算给你看。
2. **轮询只走 `GET /api/v1/tasks/<id>`。** 应用层 `POST /apps/<app>/query` 每调一次就是一次的钱
   （实测 `nano_banana/query` 72 点/次）。本包代码里没有 query 这条路，连 `doctor` 都不碰。
3. **付费提交不重试。** 网关 5xx 时任务可能已经建好了，重发就是再扣一次。
   所以重试只放在免费的上传与轮询上；中断的条目记成 `unknown`，用 `status` 对账后再决定。

## 完整链路（`run` 一条命令走完）

```
文案(≤500字) ──voice_tts/tts×M──> M 段 audio_url（每音色一次，可复用）
形象图 ×N ────POST /upload────────> N 个平台地址（0 点，oss.gpu.likeadmin.cn）
                    │
        N × M 笛卡尔积 ──submit──> 每条一个 task_id（并发 --concurrency）
                    │
            GET /tasks/<id> ──────> 状态 / 成片 / 实扣点数（0 点）
                    │
      {prefix}_{序号}-{形象}_{音色}.mp4 落盘（--outdir，默认 --workdir）
                    │
        matrix-state.json ───────> 断点续跑：重跑只补没跑完的
```

## 三步上手

```bash
# 1) 免费自检 + 先看钱（零请求扣费）
python3 scripts/run.py doctor
python3 scripts/run.py cost --images 3 --voices 4 --chars 60     # 2,564 点 / 25.64 元

# 2) 试水一条（先只做第 1 条，确认形象和音色都对）
python3 scripts/run.py run --workdir ./matrix \
    --images face_a.png --voices model_xxx --content "你的文案" --limit 1 --yes

# 3) 全量（自动跳过刚做完那条，配音也不再付第二次钱）
python3 scripts/run.py run --workdir ./matrix \
    --images face_a.png --images face_b.png --images face_c.png \
    --voices model_xxx --voices model_yyy --voices model_zzz --voices model_www \
    --content "你的文案" --concurrency 3 --yes
```

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 两个引擎、价目、规模预算一屏对照 |
| `cost --images 3 --voices 4 --chars 60` | 免费 | 先算钱（配音按 M 次算）|
| `doctor` | 免费 | 六项自检，四个只读 GET，一个 POST 都不发 |
| `voices --yes` | 净 0（先冻 150 点再全额退）| 列音色库，拿 `reference_id` |
| `tts --voices a b --content "…"` | 约 0.18 点/字 × 音色数 | 只配音，产音频清单 |
| `run … --dry-run` | 免费 | 打印每一步请求，不提交 |
| `run … --yes` | 见价目表 | 上传 → 配音 → N×M 提交 → 轮询 → 落盘 |
| `status --workdir ./matrix` | 免费 | 整张矩阵对账（只走 /tasks）|
| `status --task-id task_xxx` | 免费 | 查单条 |
| `log` | 免费 | 本地台账 |

## 和 sanjianke-digital-host 的分工

| 你要什么 | 用哪个 |
|---|---|
| 一条片子、一个形象、一个音色，最快出片 | `sanjianke-digital-host talk` |
| 一段文案要出 N 个形象 × M 个音色，批量对比 | **本包 `run`** |
| 文案驱动（不用自己录音，给参考音色即可） | 两者都行；批量走本包 |
| 已有录音，图 + 音频全驱动 | `digital-host drive`（单条）／本包 `--engine human`（批量）|
| 已有视频换口型 | `digital-host dub` |
| 要并发控制、失败重试、命名规范、断点续跑 | **本包**（这些是 `digital-host` 不做的）|
| 只要配音、不要视频 | `sanjianke-audiobook-line narrate` |

## 规格

| 项 | 说明 |
|---|---|
| 引擎 | `--engine lipsync`（默认，pic_lipsync）/ `--engine human`（image_human）|
| 档位 | lipsync 用 `--quality standard\|fast\|max`；human 用 `--mode fast\|standard\|2k\|4k`（**必填**）|
| 文案 | `--content` 或 `--content-file`，同步配音上限 500 字；超了拆段 |
| 规模 | `--images` / `--voices` 都可重复传；`--concurrency` 默认 2 |
| 试水 | `--limit 1` 只做第一条 |
| 断点 | `--workdir` 下 `matrix-state.json`；文案指纹进 key，换文案不会误用旧音频 |
| 输出 | `{prefix}_{序号}-{形象}_{音色}.mp4`，`--prefix` 改前缀、`--no-save` 只留链接 |
| 闸门 | 缺 `--yes` → 退 4 并报出点数；超 `--budget` → 退 5，**一个请求都不发** |
| 退出码 | `0` 成功 / `2` 用法错 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 写在子命令前后都行；成功 `{"ok":true,…}`，失败 `{"ok":false,"exit":N,"error":{"kind","message"}}` |

## 免责

- 人像合成请自备**肖像权与声音授权**；用真人形象、真人声音前，确保你拿到了对方同意。
- `cost` 是预估；真实扣费以任务详情里的 `usage.points_cost` 为准。
- 生成内容的合规责任在使用者：用于伪造他人身份、侵权素材或违法用途都不合适。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
