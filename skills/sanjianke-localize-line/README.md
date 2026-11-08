# 多语言出海 · 一条中文视频出 12 语版本

**一条 10 分钟中文视频，240 点（2.40 元）起，出一版外语配音 + 双语字幕。**
转写、翻译、配音、字幕四步接成一条命令，走 [api.a7w.cn](https://api.a7w.cn/)，一个 Key，零依赖。

```
原视频 ─► 转写（字级时间轴）─► 逐条翻译 ─► ElevenLabs 外语配音 ─► 字幕对齐
         120 点/次              按 token        60 点/条起            0 点（本地）
```

---

## 为什么值得用

| 你原来的做法 | 本包 |
|---|---|
| 先听写一遍，再对着时间轴手打 | `stt` 一次拿全文 + 字级时间轴，自动断行 |
| 翻译完才发现行数对不上画面 | 逐条翻译、行数锁死，时间轴 1:1 带过去 |
| 找外语配音要按段落拆、还要对时长 | 按 5000 字切块提交，音色从 67 个里挑 |
| 字幕再花一次钱做对齐 | 本地合并成 SRT / VTT，0 点、0 网络 |

一条 5 分钟的中文视频，**180 点（1.80 元）起**就能拿到外语配音 + 双语字幕。

---

## 价目（1 元 = 100 点）

| 步骤 | 端点 | 价 | 口径 |
|---|---|---|---|
| 转写 | `POST /api/v1/apps/voice_tts/stt` | **120 点/次** | 上游真实 40 点 x 3，预扣 150 点 |
| 翻译 | `POST /api/v1/chat/completions` | 按 token | 平台不公布点数，本包只报 token |
| 配音 | `POST /api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2` | **60 点/条起** | 通配：上游 x 2、保底 50；预扣 60 |
| 字幕 | 本地纯 Python | **0 点** | 不联网 |

| 视频时长 | 源文约 | 目标语言约 | 配音条数 | 合计 |
|---|---|---|---|---|
| 1 分钟 | 240 字 | 720 字 | 1 条 | **180 点（1.80 元）起** |
| 5 分钟 | 1200 字 | 3600 字 | 1 条 | **180 点（1.80 元）起** |
| 10 分钟 | 2400 字 | 7200 字 | 2 条 | **240 点（2.40 元）起** |
| 20 分钟 | 4800 字 | 14400 字 | 3 条 | **300 点（3.00 元）起** |
| 30 分钟 | 7200 字 | 21600 字 | 5 条 | **420 点（4.20 元）起** |

---

## 三条干货

### 一、5000 字是硬上限，长片贵在条数

`schema` 原文 `text.maxLength = 5000`。10 分钟中文视频的英文稿约 7000–8000 字，要切 2 条请求。
`run` 算三次预算：提交前按 `--minutes` 估、转写后按真实字数复核、翻译后按实际目标字数再复核，
三次都在**发钱之前**；超 `--budget` 就地停，退 `5`。

### 二、`voice` 是 67 个 ID 的枚举，不是名字

默认 `EkK5I93UQWFDigLMpZcX`（James）。填名字也能跑：本地精确且唯一才转成 ID
（`Brian` -> `nPczCjzI2devNBz1zQrb`），猜不中退 `2` 并列出相近项，不把错参数交给上游。

`language_code` 不传给 m2 档：schema 原文写明「只有 Turbo v2.5 和 Flash v2.5 支持语言强制，
其他模型带上会返回错误」。m2 靠目标语言文本自己识别 —— 所以 `translate` 要在 `voice` 前面跑。

### 三、字幕不花第二次钱

`stt` 的 `ignore_timestamps` 默认 `true`（时间戳会被丢掉），本包固定传 `false`。
返回的字级 segment **不带标点**，标点只在 `result.text`；本包按序回填，对不齐就原样返回，
再按「句末 / 停顿 >0.7 秒 / 单行 >18 字」合并成字幕行，本地出 SRT + VTT。

配音加 `--timestamps` 时，还能按配音时间轴重排字幕（`subtitle --align dub`），烧进画面更贴口型。

---

## 一条命令跑完

```bash
export A7W_API_KEY=sk-你的key

python3 scripts/run.py doctor                                  # 免费，0 个 POST
python3 scripts/run.py cost --minutes 10                       # 先看钱
python3 scripts/run.py run --input 第03集.mp4 --to en \
    --voice Brian --outdir ./出片 --yes
```

产物（`./出片/`）：

```
localize-source.srt       原语言字幕
localize-en.srt           英语字幕（原时间轴，剪辑直接套）
localize-en.vtt           网页 / 播放器用
localize-en.txt           配音稿（一行一句）
localize-dub-01.mp3       英语配音（多块时是 -01 / -02 …）
localize-en.json          带时间轴的逐条译文（可继续喂给 voice / subtitle）
localize-manifest.json    整条链路的清单与点数
```

---

## 分步跑（每一步都能单独用）

```bash
# 1) 转写：原视频 -> 台词稿 + 字级时间轴
python3 scripts/run.py transcribe --input 第03集.mp4 --outdir ./出片 --yes

# 2) 翻译：逐条翻，行数锁死
python3 scripts/run.py translate --in ./出片/localize-source.json --to ja --yes

# 3) 配音：67 个音色随便挑，顺手取逐词时间轴
python3 scripts/run.py voice --in ./出片/localize-ja.json --voice hpp4J3VqNfWAUOO0d1Us \
    --timestamps --outdir ./出片 --yes

# 4) 字幕：按原时间轴，或按配音时间轴重排
python3 scripts/run.py subtitle --in ./出片/localize-ja.json --to ja --outdir ./出片
python3 scripts/run.py subtitle --in ./出片/localize-ja.json --to ja \
    --align dub --dub ./出片/localize-dub-01.timestamps.json --outdir ./出片
```

自带台词稿（跳过翻译，只买转写 + 配音）：

```bash
python3 scripts/run.py run --input 预告.mp4 --to es --script 西班牙语台词.txt --yes
```

---

## 和 `sanjianke-localize-crew` 的分工

| 维度 | `sanjianke-localize-crew` | 本包 |
|---|---|---|
| 输入 | 文本稿 | **中文视频 / 音频** |
| 输出 | 译文 + 术语表 + 四席裁决 | 源字幕 + 目标字幕 + 配音 mp3 + 配音稿 + manifest |
| 核心 | 四席独立互审、术语一致、数字单位 | **转写 -> 翻译 -> 配音 -> 字幕对齐** |
| 端点 | `chat/completions` | `voice_tts/stt` + `chat/completions` + ElevenLabs m2 |
| 花钱 | 只花 token | 转写 120 点 + 配音 60 点/条起 |
| 什么时候用 | 文案要先定稿、要被否过 | 成片要出多语言版本 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 4 条线路 + 12 语言 + 67 音色 + 价目（`--voices` 全列） |
| `cost` | 免费 | 1/5/10/20/30/60 分钟价目 |
| `doctor` | 免费 | 5 条只读 GET：余额 / 应用 / 价目 / 任务 / 模型，0 个 POST |
| `transcribe` | **120 点/次** | 原视频 -> 台词稿 + 字级时间轴 + 源字幕 |
| `translate` | 按 token | 逐条翻译，行数与时间轴锁死 |
| `voice` | **60 点/条起** | 外语配音（67 音色，`--timestamps` 取逐词时间轴） |
| `subtitle` | **0 点** | 本地生成 SRT / VTT / 纯文本 |
| `run` | 转写 + 配音 | 四步一条命令 + 多版本输出 |
| `task` | 免费 | 查任务（`GET /api/v1/tasks/<id>`） |
| `log` | 免费 | 本地台账 |

---

## 参数（常用）

| 参数 | 默认 | 说明 |
|---|---|---|
| `--to` | `en` | 12 种语言：`en` `ja` `ko` `es` `pt` `fr` `de` `ru` `ar` `th` `vi` `id` |
| `--voice` | Brian | 67 个音色 ID 之一，也可填名字（唯一匹配） |
| `--timestamps` | — | 配音同时取逐词时间轴，供 `subtitle --align dub` 用 |
| `--speed` / `--style` / `--stability` / `--similarity` | 1 / 0 / 0.5 / 0.75 | 语速 0.7–1.2，其余 0–1，本地先校验 |
| `--minutes` / `--chars` | 10 / 0 | 估预算用；`--chars` 更准，给了优先 |
| `--ratio` | 3.0 | 目标字数 / 源字数，估配音条数（估多不会多扣） |
| `--budget` | 600 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实计费；缺它退 `4` |
| `--dry-run` | — | 只打印请求，不提交、不扣费 |
| `--outdir` / `--prefix` | `.` / `localize` | 产物目录与文件名前缀 |

---

## 退出码与 `--json`

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺参数、语言码错、音色名猜不中、选项缩写） |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 返回里没有音频 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

```json
{"ok": true, "mode": "run", "to": "en", "lines": 312, "chunks": 2,
 "srt": "…/localize-en.srt", "dub": [{"chunk": 1, "file": "…/localize-dub-01.mp3"}],
 "pointsFloor": 240}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

---

## 安全边界（为什么本包自检 0 点）

| 动作 | 为什么不做 |
|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，`sync:` 即时扣、不退 |
| 应用层 `submit` 缺必填 | 会先 `reserve_sync` 冻 60 / 150 点再退，净 0 但动钱包 |
| `GET /apps/voice_tts/list_voices` | 同样会 `reserve_sync` 冻 150 点 |
| 应用层 `/query` 轮询 | **一次轮询就是一次的钱**；本包只用 `GET /api/v1/tasks/<id>`（免费） |

`doctor` 只打 5 条只读 GET，`--budget` 与 `--yes` 两道闸门都在发请求前拦。

---

## 文件结构

```
sanjianke-localize-line/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（schema 原文 + 实测锚点 + 67 音色）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 边界（如实写）

- 本轮零花费：配音成功后的返回结构、`timestamps` 的具体键名按平台文档与同族实测写，
  解析器对 `audio_url` / `url` / `result.*` 做了递归兜底。真跑一条时 `voice --json`
  会把返回原样打出来，`task --task-id` 也能回看。
- 翻译走 `chat/completions`，平台不公布点数，所以本包只报 token（入 1 token 约 1.61 字、
  出 1 字约 1.11 token），不编金额。
- 多块配音是**多个 mp3**（`-dub-01` / `-dub-02` …），拼接与混轨交给剪辑软件或 ffmpeg。
- 生成内容的合规责任在使用者：配音与字幕的语言、口音、内容由使用者把关。

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
