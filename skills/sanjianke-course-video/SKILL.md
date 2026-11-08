---
name: sanjianke-course-video
slug: sanjianke-course-video
displayName: 10 章课程口播课件 · 每章 60 秒 6 元起
description: "**一份大纲，出 10 章讲师口播课件：每章 60 秒 6 元起（600 点），配音另计约 0.5 元/章。** `plan` 切章节出讲稿（0 点），`voice` 按节配音（0.18 点/字），`slide` 用课件图出章节视频（10/15/30/60 点/输入秒），`mouth` 一图 + 参考音色 + 文案直出口播（15 点/秒），`stitch` 出 ffconcat 拼接清单。`course.json` 记进度，断了接着跑不重扣。三条实测干货成了默认动作：image_human 省略 mode 会「出片按 standard、收钱按 fast」，所以 `--mode` 必填；pic_lipsync 的档位参数真名是 quality；应用层 /query 每轮询一次就是一次的钱，轮询只走 GET /api/v1/tasks/{id}。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 课程视频
  - 数字人课件
  - api.a7w.cn
---

# 10 章课程口播课件 · 每章 60 秒 6 元起

> **一份大纲，出 10 章讲师口播课件。** 每章 60 秒 6 元起，配音另计约 0.5 元/章。

## 一句话

大纲 `.md` 进去，`course.json` 进度清单 + N 段章节成片 + 一条拼接命令出来。
10 章 × 60 秒 = **6,000 点（60 元）**（课件图 fast 档）；换成 4K 是 36,000 点（360 元）。

**按章切的三条理由：** 课是分批交的，第 3 章讲完就要发出去；一章出问题只重跑一章，费用按章结、账单能对到章号；`course.json` 记着每章的 `audioUrl` / `videoUrl` / `spentPoints`，换台机器接着跑。

## 价目（1 元 = 100 点，2026-11-07 现查 /api/v1/pricing）

| 环节 | 端点 | 单价 | 10 章 × 60 秒 |
|---|---|---|---|
| 讲稿/进度 | 本地 `plan` | 0 点 | 0 点 |
| 分节配音 | `voice_tts/tts_async` | 0.18 点/字 | 约 490 点（4.90 元）|
| 课件图出片 | `image_human/submit` | **fast 10 / standard 15 / 2k 30 / 4k 60** 点/输入秒 | **6,000 / 9,000 / 18,000 / 36,000 点** |
| 一图口播 | `pic_lipsync/submit` | 15 点/秒 | 9,000 点（90 元）|
| 章节拼接 | 本地 `stitch` | 0 点 | 0 点 |

- `image_human` 按**输入音频秒数**计费，带上 `duration` 价格才被费率卡锁死，预算能算到个位
- 真跑以后一律以返回里的 `usage.points_cost` 为准

## 三条干货

### 干货一：`image_human` 省略 mode，出片与收费会走两个档

`params_schema.mode.default` 是 `standard`，`/pricing` 的 `defaultModel` 是 `fast`。
省略时：**出片按 standard、收钱按 fast**（15 点/秒 vs 10 点/秒）。本包 `slide --mode` 必填。

### 干货二：`pic_lipsync` 的档位参数叫 `quality`

`mode` 只切 `audio` / `text`，档位是 `quality`（`standard` / `fast` / `max`）。
`mode=text` 省掉的是录音，**参考音色省不掉** —— `audio_url` 仍然必填，给 3–10 秒清晰人声。

### 干货三：应用层 `/query` 一次就是一次的钱

历史流水：`nano_banana/query` 72 点/次，108 次 = 7,776 点。
本包在 `http_json` 里拦掉任何以 `/query` 结尾的地址，轮询只走 **GET `/api/v1/tasks/{id}`**（只读、免费）。
`doctor` 同理：只发 4 个只读 GET，连「缺必填参数的 POST」都不发 —— 实测应用层 submit 会先冻再退，`list_voices` 每次也冻 150 点。

## 和 sanjianke-digital-host / avatar-autoclip 的分工

| | 本包 `sanjianke-course-video` | `sanjianke-digital-host` | `avatar-autoclip` |
|---|---|---|---|
| 交付物 | 一套课：N 段章节成片 + 拼接清单 | 一段口播视频（一个镜头） | 一条竖屏成品短视频 |
| 输入 | 一份大纲 `.md`（多章多节） | 一张图 + 一段话/音频 | 一张参考图 + 一段文案 |
| 强项 | 章节、进度、断点续跑、逐章对账 | 三条口播路线一次讲透，单价最清楚 | 字幕、封面、模板、智能剪辑一条龙 |
| 计费 | 逐章预算，`course.json` 记每章实际点数 | 单次 15 点/秒 或 10–60 点/输入秒 | 全链路叠加 |
| 什么时候用它 | 要交一套分章节课件 | 只要一个口播镜头 | 要一条能直接发的短视频 |

一句话选法：**要「一套课」用本包；要「一个镜头」用 digital-host；要「一条短视频成片」用 avatar-autoclip。**

## 完整链路

```
outline.md ──plan──► course.json（讲稿 + 进度）             0 点
                        │
                        ├─voice──► 每章配音 mp3（tts_async）   0.18 点/字
                        │             │
                        │             ▼
                        └─────slide──► 每章成片（image_human） 10–60 点/输入秒
                                      │
                                      ▼
                                   stitch ──► ffconcat 清单 + ffmpeg 一条命令   0 点
```

## 三步上手

```bash
# 0) Key（三选一）
export A7W_API_KEY=sk-你的key          # 或 python3 scripts/a7w.py login --key sk-...
# 1) 自检（免费）：4 个只读 GET，一个 submit 都不发
python3 scripts/run.py doctor
# 2) 大纲 → 讲稿 + 进度清单（免费，本地）
python3 scripts/run.py plan --outline course-outline.md -o course.json
```

## 常用命令

```bash
# 先算钱：10 章 × 60 秒
python3 scripts/run.py cost --chapters 10 --seconds 60 --route slide --mode fast
# 分节配音（先跑两章试听）
python3 scripts/run.py voice --course course.json --limit 2 --yes
# 课件图出片（--mode 必填；--pad 10 给 duration 留余量）
python3 scripts/run.py slide --course course.json --image slide.png --mode fast --pad 10 --yes
# 一图 + 参考音色 + 文案，直接出口播
python3 scripts/run.py mouth --image teacher.png --voice-ref voice.mp3 \
    --content "这一节讲三个概念…" --quality standard --yes
# 章节拼接清单 + 进度回看（--dry-run 只看请求体，不花钱）
python3 scripts/run.py stitch --course course.json
```

## 实测记录（2026-11-07，本轮 0 点）

```
自检（全程免费：4 个只读 GET，一个 submit 都不发）

  √ Key 有效 + 应用目录可达              HTTP 200 success · 22 个应用
  √ 三条链路都已在网关配价               定价表 115 条，命中 3/3 条链路
  √ 速率卡一致（10/15/30/60 点/输入秒）  live={"fast":10,"standard":15,"2k":30,"4k":60} · defaultModel=fast
  √ 轮询线 GET /api/v1/tasks/{id} 可用   HTTP 200 任务不存在
```

`GET /user/balance/logs` 前后对比：最新一条流水时间不变、总条数不变、可用点数不变 —— 本轮真实花费 **0 点**。

## 规格

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | 5000 | **单位是点**（1 元 = 100 点），超了退 5 且不发请求 |
| `--yes` | — | 缺了退 4，并告诉你这次要花多少 |
| `--mode` | 必填 | `slide` 的档位：fast / standard / 2k / 4k |
| `--quality` | standard | `mouth` 的档位：standard / fast / max |
| `--limit` / `--only` | 全部 | 本次跑几章 / 只跑哪几章（断点续跑） |
| `--pad` | 0 | 给 `duration` 留余量（百分比，建议 10） |
| `--dry-run` | — | 打印请求体与预估点数，不提交 |

退出码：`0` 成功 · `2` 用法错 · `4` 缺 `--yes` · `5` 超预算 · `6` 调用失败 · `1` 内部错 · `130` 中断。
`--json` 契约：成功 `{"ok": true, ...}`；失败 `{"ok": false, "exit": N, "error": {"kind": "...", "message": "..."}}`。

```
sanjianke-course-video/
├── SKILL.md · README.md · LICENSE.md
├── references/  api-contract.md（参数/单价/实测原文）· troubleshooting.md（按报错找原因）
└── scripts/     a7w.py（零依赖客户端，逐字节一致）· run.py（本包命令层）
```

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
