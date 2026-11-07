---
name: sanjianke-suno-music
slug: sanjianke-suno-music
displayName: Suno 音乐台 一句话出一首歌
description: "**给人一句话，它给你一首完整的歌 —— 带人声、带伴奏、带时间戳歌词。** 走 api.a7w.cn 的 Official 音频（`media_services_33`），7 个 Suno 音乐接口接通：一句话出歌、给副歌再接一段、按描述出音效、用自己的声音建音色、导出带时间戳歌词做字幕、过期再恢复、把一首歌的味道存成 Persona。提交后自动轮询，完成时把 `audio_id` 与音频直链打出来 —— 延长、取歌词、建 Persona 都要它。价格：`/api/v1/pricing` 里没有它的专属规则，落通配「上游实际点数 × 2，单笔保底 50 点」，所以 `cost` 是**下限估算**，真跑一条才知道准确点数。`--budget` 是第一道闸门、`--yes` 第二道，`doctor` 用必然被校验拦下的请求把 7 个端点探一遍，零扣费。遇到问题可加技术微信 9872659。"
version: 1.0.2
summary: "一个命令出一首完整的歌。`song --prompt \"夏夜霓虹的温暖合成器流行\"` 提交后自动轮询，完成时打印每首的 `audio_id`、时长、直链与歌词。控词加 `--custom --style … --lyrics … --title …`；纯音乐加 `--instrumental`；`--duration` 控时长、`--variety` 控多样性。model 用 `V6`（默认）、`V6_MINI` 轻快省、`V6_WILD` 更敢玩。另外 6 个各管一段：`extend` 拿 `audio_id` 接着往下写、`sound` 一句话出音效（本包总是显式传 `--tempo`，缺省值判类型错误，默认 120）、`voice` 走 `prepare → create` 建音色、`lyrics` 用 `task_id + audio_id` 取带时间戳歌词做字幕、`recover` 过期后重取、`persona` 存成可复用模板。网关成功判据是 `code=1`；校验失败也是 HTTP 200 + `code=0`，本包按 `code` 判定。价格「上游 × 2，保底 50 点」，`cost` 给下限、`--upstream` 可换算。需要自备 api.a7w.cn 的 Key（注册见 https://api.a7w.cn/ ）。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 音乐生成
  - Suno
  - api.a7w.cn
---

# Suno 音乐台 一句话出一首歌
> **先申请你自己的 API Key**：本包不内嵌任何 Key，用的是**你自己**在
> [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。
> 登录：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**给人一句话，它给你一首完整的歌。** 走 `api.a7w.cn` 的 `media_services_33`，7 个 Suno 音乐接口一个命令一个，异步提交 + 自动轮询，零依赖。

## 能干什么

| 能力 | 一条具体用法 | 你会拿到 |
|---|---|---|
| **出歌** | `song --prompt "夏夜霓虹的温暖合成器流行"` | 一首完整歌：人声 + 伴奏 + 歌名 |
| **写词出歌** | `song --custom --style "dream pop" --lyrics "[主歌]…" --title 夜行` | 歌词严格照唱，风格按你的标签走 |
| **纯音乐** | `song --prompt "钢琴独白" --instrumental` | 无人声的伴奏曲 |
| **延长** | `extend --audio-id <audio_id> --lyrics "…"` | 在原曲后面再接一段 |
| **音效** | `sound --prompt "雨打铁皮棚，远处闷雷" --tempo 90 --loop` | 一段可循环的音效 |
| **自建音色** | `voice --action prepare --voice-url <样本> --start 3 --end 18` | 验证短句 → `create` 出你的音色 |
| **时间戳歌词** | `lyrics --task-id <id> --audio-id <id>` | 逐句时间轴，直接压字幕 |
| **恢复** | `recover --task-id <id>` | 链接过期后把音频再取一次 |
| **Persona** | `persona --name 夜行嗓 --task-id <id> --audio-id <id> --description "…"` | 可复用的风格模板 |

## 怎么串起来

```
写词  →  出歌  →  不满意就延长  →  要字幕就取时间戳歌词  →  要自己的声音就建音色
```

```bash
python3 scripts/run.py song   --custom --style "city pop" --lyrics "[主歌]霓虹把街角点亮" \
    --title "夜行" --yes
# 完成时会打印 audio_id，记下来
python3 scripts/run.py extend --audio-id <audio_id> --lyrics "…" --yes
python3 scripts/run.py lyrics --task-id <task_id> --audio-id <audio_id> --yes
python3 scripts/run.py voice  --action prepare --voice-url https://…/me.wav --start 3 --end 18 --yes
```

`--no-wait` 只提交拿 `task_id` 就走，之后 `task --task-id …` 免费续查，**同一条结果不会重复提交**。

## 价格口径（诚实版）

`/api/v1/pricing` 里**没有 `media_services_33` 的专属规则**，落通配：

```json
{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
 "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}
```

也就是说：**一条歌对外点数 = 上游实际点数 × 2，单笔保底 50 点（¥0.50）**。
上游真实点数要真跑一条才看得到，所以 **`cost` 给的是下限估算**，不是报价：

```bash
python3 scripts/run.py cost                      # 未知上游 → 至少 50 点（¥0.50）
python3 scripts/run.py cost --upstream 65        # 你观察到的上游 65 点 → 130 点（¥1.30）
python3 scripts/run.py cost --upstream 65 --tasks 3
```

## 三步上手

```bash
# 1) 自检（不扣费）：Key、应用、7 个端点、任务查询
python3 scripts/run.py doctor

# 2) 先看价：给的是下限
python3 scripts/run.py cost --tasks 1

# 3) 出歌
python3 scripts/run.py song --prompt "夏夜霓虹的温暖合成器流行" --yes
```

缺 `--yes` 退 `4` 并告诉你下限是多少；下限超 `--budget` 退 `5`，**一个请求都不发**。
想先看不花钱的请求：`song --prompt "…" --dry-run`。

## 子命令

| 子命令 | 计费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 现查 7 个接口的必填项与 `model` 枚举 |
| `doctor` | 免费 | 自检 Key / 应用 / 7 个端点 / 任务查询 |
| `cost` | 免费 | 先算钱（下限） |
| `song` | 上游×2 保底 50 点 | 生成音乐 |
| `extend` | 同上 | 延长音乐 |
| `sound` | 同上 | 生成音效 |
| `voice` | 同上 | 自建音色（prepare → create） |
| `lyrics` | 同上 | 带时间戳歌词 |
| `recover` | 同上 | 恢复音频 |
| `persona` | 同上 | 生成 Persona |
| `task` | 免费 | 查状态 / 补取结果 |
| `log` | 免费 | 本地台账 |

## 关键参数

| 参数 | 说明 |
|---|---|
| `--model` | `V6`（默认）/ `V6_MINI` / `V6_WILD` / `V5_5` / `V5` / `V4_5ALL` / `V4_5PLUS` / `V4_5` / `V4`；`sound` 只收 `V5`/`V5_5`/`V6` 系 |
| `--budget` | 点数上限，**单位是点**（1 元 = 100 点），默认 500 |
| `--upstream` | 你观察到的上游点数，用来把下限换算成实际价 |
| `--out DIR` | 顺手把音频下载到本地 |

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、`model` 不在枚举、数值越界） |
| `3` | `doctor` 有检查项没过 |
| `4` | 没有 `--yes` |
| `5` | 下限超 `--budget`，**一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 轮询超时 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

## `--json` 契约

```json
{"ok": true, "api": "music_generate", "task_id": "task_xxx", "status": "completed",
 "audios": [{"audio_id": "audio_xxx", "audio_url": "https://…", "title": "夜行"}],
 "pointsFloor": 50, "usage": {"points_cost": 65}}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`。
`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 文件结构

```
sanjianke-suno-music/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（schema 原文 + 实测）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致）
    └── run.py                本包命令层
```

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
