# AI 配乐 60 点一段 卡点与混音一起给

**一条 3 分钟视频，60 点（0.60 元）配齐一段卡点配乐。** 节奏先算，音乐再出，时长接上，混音清单直接能跑。

走 [api.a7w.cn](https://api.a7w.cn/) 的 Official 音频与辅助服务（应用代号 `media_services_33`），本包只接配乐需要的 4 个接口。

---

## 价目表

| 你的片子 | 配乐段数 | 下限 | 折合 |
|---|---|---|---|
| 3 分钟以内 | 1 次 `gen` | **60 点** | **0.60 元** |
| 6 分钟 | 1 次 `gen`（`--duration 360`） | 60 点 | 0.60 元 |
| 8 分钟 | `gen` + 1 次 `extend` | 120 点 | 1.20 元 |
| 10 分钟 | `gen` + 2 次 `extend` | 180 点 | 1.80 元 |
| 加一层环境音 | 再来 1 次 `sound` | +60 点 | +0.60 元 |

计费口径（诚实版）：

```json
{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
 "note":"未单独定价的接口：对外 = 上游实际点数 x 2，单笔保底 50 点"}
```

- `/api/v1/pricing` 里**没有 `media_services_33` 的专属规则**，落通配 `*`
- **实测每笔冻结 60 点**（= 上游 30 点 x 2），比规则写的 50 点保底高
- `cost` 默认按 60 点/次给**下限**；上游真实点数要真跑一次才看得到，按任务详情结算
- 1 元 = 100 点；`--budget` 的单位就是「点」

---

## 三条干货

### 一、空 body 的提交也会冻结 60 点

```
POST /api/v1/apps/media_services_33/music_generate  {}
  -> {"code":0,"msg":"input.custom_mode: 缺少必填参数；…；input.model: 缺少必填参数"}
  -> 账户流水  +60 点  /  -60 点   净 0，余额不动，调用数 +1
```

「缺参数会停在扣费之前」这句是错的。网关先 `reserve_sync` 冻 60 点，再跑参数校验，失败再全额退。

所以本包 `doctor` **一个 POST 都不发**：只用 `/models` `/apps` `/pricing` `/tasks/<id>` `/user/balance` 这些只读接口，把 Key、应用、4 个接口、价目、查询路由全验一遍，**0 冻结**。

### 二、`duration` 只在「自定义模式 + V6 系」下生效

`duration` 是 10-360 秒，但只有 `custom_mode=true` 且 `model` 属于 `V6` / `V6_MINI` / `V6_WILD` 时才控制长度。
用别的 model 或非自定义模式，它安静地按默认时长出——你以为配到 3 分钟，出来的可能是 2 分钟。

本包做了两件事：`--duration` 自动把 `custom_mode` 打开；model 不在 V6 系就当场退 `2` 并告诉你该换哪个。
`--prompt` 在自定义模式下会被自动挪到 `style`（自定义模式里 `style` 才是风格标签），标题缺省自动补 `配乐-HHMMSS`。

### 三、轮询千万别打应用层的 `/query`

应用层 `/query` **每调一次就是一次的钱**（历史教训：`nano_banana/query` 72 点/次，累计烧掉 15,552 点）。

本包轮询**只走 `GET /api/v1/tasks/<task_id>`**，只读、免费、可反复打。`--no-wait` 只拿 `task_id` 就走，之后 `task --task-id …` 免费接着取，同一条结果不会重复提交，也就不会再冻结一次。

---

## 完整链路

```
定时长/BPM  ->  plan 出分段与卡点  ->  gen 出第一段  ->  extend 接到时长  ->  mix 出 ffmpeg 清单  ->  跑
   （本地免费）        （本地免费）        （60 点/段）       （60 点/段）        （本地免费）
```

```bash
python3 scripts/run.py plan   --duration 480 --bpm 92 --shots 14,47,96,140,300,470 --style "tension strings"
python3 scripts/run.py gen    --prompt "tension strings, low pulse" --duration 360 --yes
python3 scripts/run.py extend --audio-id <上一段的 audio_id> --continue-at 360 --yes
python3 scripts/run.py mix    --video input.mp4 --audio seg-1.mp3 --audio seg-2.mp3 --duration 480
```

`plan` 的输出长这样（8 分钟片子、92 BPM）：

```
  视频   480 秒（8 分 0 秒）
  节奏   92 BPM，4/4 拍，一小节 2.609 秒
  对齐   184 小节 = 480.00 秒

  分段   #    角色     起         止         小节     调用
  1     前奏      0         240       92     music_generate
  2     尾声      240       480       92     music_extend

  卡点    12.00 秒 -> 第  5 小节 =   13.04 秒  偏移 +1.04 秒
         47.00 秒 -> 第 18 小节 =   46.96 秒  偏移 -0.04 秒

  花费   下限 2 次 x 60 点 = 120 点 = 1.20 元
```

---

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

---

## 常用命令

```bash
python3 scripts/run.py catalog                    # 现查 29 个音频接口 + 本包 4 个的必填项
python3 scripts/run.py plan --duration 480 --bpm 92 --shots 12,47,96
python3 scripts/run.py gen --prompt "雨夜霓虹，慢板合成器" --yes
python3 scripts/run.py gen --prompt "…" --duration 180 --model V6_MINI --yes
python3 scripts/run.py extend --audio-id <id> --continue-at 180 --yes
python3 scripts/run.py sound --prompt "雨打铁皮棚，远处闷雷" --tempo 90 --yes
python3 scripts/run.py mix --video in.mp4 --audio seg-1.mp3 --duration 180
python3 scripts/run.py task --task-id <id>        # 免费查（只走 GET /tasks/<id>）
python3 scripts/run.py log --limit 10             # 本地台账
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` | — | 一句风格描述（非自定义模式）；自定义模式下自动转成 `style` |
| `--style` | — | 风格标签，例如 tension strings / 国风 / lo-fi |
| `--custom` | 关 | 自定义模式，给 `--style` `--lyrics` `--title` |
| `--duration` | — | 目标时长 **10-360 秒**，只在 V6 系 + 自定义模式生效 |
| `--model` | `V6` | `V6` / `V6_MINI` / `V6_WILD` / `V5_5` / `V5` / `V4_5ALL` / `V4_5PLUS` / `V4_5` / `V4` |
| `--vocal` | 关 | 要人声；**默认纯音乐**（配乐用 instrumental=true） |
| `--bpm` | 90 | `plan` 用的小节基准，4/4 拍 |
| `--shots` | — | 镜头切点秒数，逗号分隔，`plan` 会把它们吸到最近小节 |
| `--budget` | 600 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--upstream` | 30 | 上游点数，用于把下限换算成你的实际价 |
| `--yes` | — | 确认真实计费 |
| `--dry-run` | — | 只打印请求，不提交 |

---

## 子命令

| 子命令 | 计费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 现查 29 个音频接口 + 本包 4 个的必填项与 model 枚举 |
| `cost` | 免费 | 先算钱：1 / 3 / 5 次的下限 |
| `doctor` | 免费 | 自检 Key / 应用 / 4 个接口 / 价目 / 查询路由（0 个 POST） |
| `plan` | 免费 | 给时长和 BPM，出分段、卡点、下限（不联网） |
| `gen` | 60 点/次起 | 生成配乐 |
| `extend` | 60 点/次起 | 延长到目标时长 |
| `sound` | 60 点/次起 | 环境音 / 转场音效 |
| `mix` | 免费 | 出 ffmpeg 混音清单（不联网） |
| `task` | 免费 | 查任务 / 取音频直链 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、model 不在枚举、数值越界、选项缩写） |
| `3` | `doctor` 有检查项没过 |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 轮询超时 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "api": "music_generate", "task_id": "task_xxx", "status": "completed",
 "audios": [{"audio_id": "audio_xxx", "audio_url": "https://…", "title": "配乐-233626"}],
 "pointsFloor": 60, "usage": {"points_cost": 30}}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`。
`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-ai-soundtrack/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（schema 原文 + 实测）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 和 sanjianke-suno-music 的分工

两个包都走同一个 `media_services_33`、同一套价格口径、可以共用一个 Key。区别是「一首歌」和「一条片子」：

| 你要干的事 | 用哪个 | 它多做了什么 |
|---|---|---|
| 成片要配乐、要对卡点、要控时长 | **本包** | `plan` 算小节与切点、`extend` 接到时长、`mix` 出 ffmpeg 清单 |
| 要一首完整带人声的歌，写词照唱 | `sanjianke-suno-music` | 7 个 Suno 接口全接，`--custom --lyrics --title` 走歌词路线 |
| 要自建音色、Persona、恢复过期音频 | `sanjianke-suno-music` | `voice` / `persona` / `recover` 三个接口只它接 |
| 要环境音、转场音效铺底 | **本包** `sound` | 默认显式传 `sound_tempo`，撞不上类型校验坑 |
| 要时间戳歌词压字幕 | 两个都有 | 本包按「配乐卡点」用，suno 那边按「歌词字幕」用 |

**做歌找 suno-music，做片子找本包。** 本包只接 4 个接口，suno-music 接 7 个，重复的只有 `music_generate` 这一个入口。

---

## 实测记录

```
2026-11-07  接口探针（净 0 点，未生成任何任务）
  空 body POST music_generate        -> code 0，缺 custom_mode / instrumental / model
  空 body POST music_extend          -> code 0，缺 audio_id / model
  空 body POST music_sounds          -> code 0，缺 prompt / model + sound_tempo 类型不正确
  空 body POST music_timestamped_lyrics -> code 0，缺 task_id / audio_id
  每笔流水 +60 点 / -60 点，净 0，余额不变
```

**`sound_tempo` 这一条值得记住**：schema 里标「可选、默认 Auto」，真省掉它，上游报 `input.sound_tempo: 类型不正确`。
所以本包 `sound` 子命令**总是显式传** `--tempo`（默认 120）。

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
