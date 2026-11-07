---
name: sanjianke-ai-soundtrack
slug: sanjianke-ai-soundtrack
displayName: AI 配乐 60 点一段 卡点与混音一起给
description: "**一条 3 分钟视频，60 点（0.60 元）配齐一段卡点配乐。** 给一条视频，四步自动走完：按 BPM 算小节并把切点吸到鼓点、出配乐、接到视频时长、给一条 ffmpeg 混音命令。走 api.a7w.cn 的 Official 音频（`media_services_33`），4 个接口接通：`music_generate` 出音乐、`music_extend` 接到时长、`music_sounds` 铺环境音、`music_timestamped_lyrics` 出时间轴。`duration` 10-360 秒只在 V6 系自定义模式下生效，本包自动切对。价格落通配「上游 x 2，保底 50 点」，实测每笔冻 60 点，`cost` 给下限。`--budget` 与 `--yes` 双闸门，`doctor` 默认 0 个 POST、0 冻结。问题可加技术微信 9872659。"
version: 1.0.0
summary: "配乐难的不是生成音乐，是把音乐**配到画面**上：一首 3 分钟的歌接到 8 分钟片子上，要么重复到腻，要么接缝一跳就露馅。本包把它拆成能算的四步。`plan --duration 480 --bpm 92 --shots 14,47,96` 先出方案：一小节 2.609 秒、每个切点吸到最近小节、每段用哪个接口、下限多少点，一分钱不花。`gen --duration 180 --yes` 出音乐，配乐默认 instrumental=true。超 6 分钟就 `extend --audio-id … --continue-at 360` 接着写，同一首不断。最后 `mix --video in.mp4 --duration 480` 给一条 ffmpeg 命令：逐段对齐、接缝淡入 0.5 秒、音量 0.35、aloop 补够再 atrim 到视频时长、尾部 2.5 秒淡出，视频流 copy 不重编码。价格落通配「上游实际点数 x 2，单笔保底 50 点」，实测空 body 提交流水 +60/-60（净 0），所以每笔真冻结 60 点，`cost` 按 60 点/次给下限。轮询只走 GET /api/v1/tasks/<id>（免费）。需要自备 Key（注册见 https://api.a7w.cn/ ）。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 音频配乐
  - 视频配乐
  - api.a7w.cn
---

# AI 配乐 60 点一段 卡点与混音一起给

> **先申请你自己的 API Key**：本包不内嵌任何 Key，用的是**你自己**在
> [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。
> 登录：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**一条 3 分钟视频，60 点（0.60 元）配齐一段卡点配乐。** 节奏先算，音乐再出，时长接上，混音清单直接能跑。

## 价目表

| 你的片子 | 配乐段数 | 下限 | 折合 |
|---|---|---|---|
| 3 分钟以内 | 1 次 `gen` | **60 点** | **0.60 元** |
| 6 分钟 | 1 次 `gen`（`--duration 360`） | 60 点 | 0.60 元 |
| 8 分钟 | `gen` + 1 次 `extend` | 120 点 | 1.20 元 |
| 10 分钟 | `gen` + 2 次 `extend` | 180 点 | 1.80 元 |
| 加一层环境音 | 再来 1 次 `sound` | +60 点 | +0.60 元 |

- 计费口径：`/api/v1/pricing` 里**没有 `media_services_33` 的专属规则**，落通配 `*`：
  **对外 = 上游实际点数 x 2，单笔保底 50 点**（1 元 = 100 点）。
- **实测每笔冻结 60 点**（= 上游 30 点 x 2），比规则写的 50 点保底高，所以 `cost` 默认按 60 点/次给。
- `cost` 给的是**下限**；上游真实点数要真跑一次才看得到，最终按任务详情结算。
- `plan` / `mix` / `catalog` / `cost` / `doctor` / `task` / `log` 全是 0 点。

## 三条干货

### 一、空 body 的提交也会冻结 60 点

```
POST /api/v1/apps/media_services_33/music_generate  {}
  -> {"code":0,"msg":"input.custom_mode: 缺少必填参数；…；input.model: 缺少必填参数"}
  -> 账户流水  +60 点  /  -60 点   净 0，余额不动，调用数 +1
```

**「缺参数会停在扣费之前」这句是错的。** 网关先 `reserve_sync` 冻 60 点，再跑参数校验，失败再全额退。
所以本包 `doctor` **一个 POST 都不发**：只用 `/models` `/apps` `/pricing` `/tasks/<id>` `/user/balance` 这些只读接口，
把 Key、应用、4 个接口、价目、查询路由全验一遍，**0 冻结**。想看提交路由是否可达，加 `doctor --probe-post`，
它会先告诉你每条会冻结 60 点再退回。

### 二、`duration` 只在「自定义模式 + V6 系」下生效

`duration` 是 10-360 秒，但只有 `custom_mode=true` 且 `model` 是 `V6` / `V6_MINI` / `V6_WILD` 时才控制长度。
用别的 model 或非自定义模式，它安静地按默认时长出——你以为配到 3 分钟，出来的可能是 2 分钟。

本包做了两件事：`--duration` 自动把 `custom_mode` 打开；model 不在 V6 系就当场退 `2`，并告诉你该换哪个。
`--prompt "紧张的弦乐"` 在自定义模式下会被自动挪到 `style`（自定义模式里 `style` 才是风格标签），标题缺省自动补 `配乐-HHMMSS`。

### 三、轮询千万别打应用层的 `/query`

应用层 `/query` **每调一次就是一次的钱**（历史教训：`nano_banana/query` 72 点/次，累计烧掉 15,552 点）。
本包轮询**只走 `GET /api/v1/tasks/<task_id>`**，这条是只读、免费、可反复打。

`gen` / `extend` 提交后默认帮你轮询；`--no-wait` 只拿 `task_id` 就走，之后 `task --task-id …` 免费接着取，
同一条结果**不会重复提交**，也就不会再冻结一次。

## 完整链路

```
定时长/BPM  ->  plan 出分段与卡点  ->  gen 出第一段  ->  extend 接到时长  ->  mix 出 ffmpeg 清单  ->  跑
   （本地免费）        （本地免费）        （60 点/段）       （60 点/段）        （本地免费）
```

```bash
python3 scripts/run.py plan  --duration 480 --bpm 92 --shots 14,47,96,140,300,470 --style "tension strings"
python3 scripts/run.py gen   --prompt "tension strings, low pulse" --duration 360 --yes
python3 scripts/run.py extend --audio-id <上一段的 audio_id> --continue-at 360 --yes
python3 scripts/run.py mix   --video input.mp4 --audio seg-1.mp3 --audio seg-2.mp3 --duration 480
```

## 和 sanjianke-suno-music 的分工

两个包都走同一个 `media_services_33`、同一套价格口径、可以共用一个 Key。**分工是「一首歌」和「一条片子」的区别：**

| 你要干的事 | 用哪个 | 它多做了什么 |
|---|---|---|
| 成片要配乐、要对卡点、要控时长 | **本包** `sanjianke-ai-soundtrack` | `plan` 算小节与切点、`extend` 接到时长、`mix` 出 ffmpeg 清单 |
| 要一首完整带人声的歌，写词照唱 | `sanjianke-suno-music` | 7 个 Suno 接口全接，`--custom --lyrics --title` 走歌词路线 |
| 要自建音色、Persona、恢复过期音频 | `sanjianke-suno-music` | `voice` / `persona` / `recover` 三个接口只它接 |
| 要环境音、转场音效铺底 | **本包** `sound` | 默认显式传 `sound_tempo`，撞不上类型校验坑 |
| 要时间戳歌词压字幕 | 两个都有 | 本包按「配乐卡点」用，suno 那边按「歌词字幕」用 |

一句话：**做歌找 suno-music，做片子找本包。** 本包只接 4 个接口，suno-music 接 7 个，重复的只有 `music_generate` 这一个入口。

## 三步上手

```bash
# 1) 自检（不扣费、0 冻结）：Key / 应用 / 4 个接口 / 价目 / 查询路由
python3 scripts/run.py doctor

# 2) 先看方案和钱（不联网、不花钱）
python3 scripts/run.py plan --duration 180 --bpm 92 --style "tension strings"
python3 scripts/run.py cost --calls 1

# 3) 出配乐
python3 scripts/run.py gen --prompt "tension strings, low pulse" --duration 180 --yes
```

缺 `--yes` 退 `4` 并告诉你下限多少；下限超 `--budget` 退 `5`，**一个请求都不发**。
想先看不花钱的请求：`gen --prompt "…" --dry-run`。

## 常用命令

```bash
python3 scripts/run.py catalog                     # 现查 29 个音频接口 + 本包 4 个的必填项
python3 scripts/run.py plan --duration 480 --bpm 92 --shots 12,47,96     # 分段 + 卡点表
python3 scripts/run.py gen --prompt "雨夜霓虹，慢板合成器" --yes          # 一句话出配乐
python3 scripts/run.py gen --prompt "…" --duration 180 --model V6_MINI --yes
python3 scripts/run.py extend --audio-id <id> --continue-at 180 --yes     # 接到时长
python3 scripts/run.py sound --prompt "雨打铁皮棚，远处闷雷" --tempo 90 --yes   # 环境音
python3 scripts/run.py mix --video in.mp4 --audio seg-1.mp3 --duration 180      # 混音清单
python3 scripts/run.py task --task-id <id>         # 免费查（只走 GET /tasks/<id>）
```

## 规格

| 项目 | 值 |
|---|---|
| 端点 | `POST https://api.a7w.cn/api/v1/apps/media_services_33/<接口code>` |
| 查询 | `GET https://api.a7w.cn/api/v1/tasks/<task_id>`（轮询只走这条） |
| 鉴权 | `Authorization: Bearer <你的 Key>` |
| 接口 | `music_generate` / `music_extend` / `music_sounds` / `music_timestamped_lyrics` |
| model | `V6`（默认）/ `V6_MINI` / `V6_WILD` / `V5_5` / `V5` / `V4_5ALL` / `V4_5PLUS` / `V4_5` / `V4`；`sound` 收 V5 起 |
| duration | 10-360 秒，仅自定义模式 + V6 系生效 |
| 返回 | `{"code":1,"msg":"success","data":{…}}`；**校验失败也是 HTTP 200**，只是 `code=0` |
| `--budget` | 点数上限，**单位是点**（1 元 = 100 点），默认 600 |
| 依赖 | 零依赖，Python 3.7+，只用标准库 |
| 音频类型 | 配乐默认 `instrumental=true`（纯音乐），要人声加 `--vocal` |

`music_sounds` 的 `sound_tempo` 在 schema 里标「可选、默认 Auto」，上游却按类型校验——
实测省掉它直接报 `input.sound_tempo: 类型不正确`，所以本包**总是显式传**（默认 120）。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
