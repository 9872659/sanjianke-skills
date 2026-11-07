# 高保真语音台 短剧配音一句话一个角色
**同一个剧本，五个角色，五种声音 —— 一人一句，一次出完，还能带时间戳字幕。** 走 [api.a7w.cn](https://api.a7w.cn/) 的语音通道，8 个接口一条命令，零依赖。

| 你要的 | 用哪个 |
|---|---|
| 音质标杆、单人旁白、有声书 | `speak --line v2`（ElevenLabs 多语言 V2，67 音色） |
| 同样能打但要更快 | `speak --line turbo`（Turbo 2.5，唯一支持强制语言的档） |
| 短剧对手戏、播客双人 | `dialogue`（对话 V3，每句自带音色） |
| 五人群戏、要接话、要语气词 | `scene --line gemini38`（70 音色，逐句可给语气） |
| 有声书要口音 / 语速 / 情感 | `scene --line gemini25pro`（30 音色 + 8 口音 + 4 档语速 + 6 种情感） |
| 造一个专属音色 / 角色 | `design` / `character`（Omni） |

---

## 8 条线一览

| `--line` | 接口 code | 必填 | 音色 | 干什么 |
|---|---|---|---|---|
| `v2` | `elevenlabs_text_to_speech_multilingual_v2` | `text` `voice` | 67 | 多语言 V2，行业标杆音质 |
| `turbo` | `elevenlabs_text_to_speech_turbo_2_5` | `text` `voice` | 67 | Turbo 2.5，极速档 |
| `v3` | `elevenlabs_text_to_dialogue_v3` | `dialogue` | 67 | 多人对白，每句自带音色 |
| `gemini38` | `google_gemini_3_8_flash_tts` | `speakers` `dialogue_turns` | 70 | 对话式，逐句语气 + 语气词 |
| `gemini38lite` | `google_gemini_3_8_flash_lite_tts` | `speakers` `dialogue_turns` | 70 | 同上，轻量档 |
| `gemini25pro` | `google_gemini_2_5_pro_tts` | `speakers` `dialogue_turns` | 30 | 2.5 Pro，口音 / 语速 / 情感 |
| `omni` | `gemini_omni_audio` | `name` `audio_id` | 30 底子 | 描述换音色 |
| `character` | `gemini_omni_character` | `image_urls` `descriptions` | 30 | 参考图造角色 |

统一形态：`POST /api/v1/apps/media_services_33/<接口code>`（JSON），一次请求一条任务。
查询：`GET /api/v1/tasks/<task_id>`，免费。

---

## 三条音色线怎么选

### 一、ElevenLabs 多语言 V2 —— 音质标杆

67 个音色 ID，情绪三件套齐：`speed`（0.7~1.2）、`stability`（0~1）、`similarity_boost`（0~1），
再加 `style`（夸张度 0~1）。适合单人旁白、预告片、有声书。

```bash
python3 scripts/run.py speak --line v2 --text "你终于来了。" --voice James \
    --speed 0.95 --stability 0.4 --similarity 0.8 --yes
```

### 二、ElevenLabs Turbo 2.5 —— 同一套音色，出得更快

音色表、参数和 V2 一样，快的代价是细节少一点。它有一个 V2 没有的能力：
**`--language-code` 强制语言**（ISO 639-1）。V2 传了会被上游打回，本包在本地就拦住。

```bash
python3 scripts/run.py speak --line turbo --text "你终于来了。" --voice Arabella --language-code zh --yes
```

### 三、Gemini 对话式 —— 会接话的那一种

3.8 两条线（`gemini38` / `gemini38lite`）有 70 个 `voice_name`，默认 `Fola`；
2.5 Pro 只有 30 个，但多了 `accent`（8 种）、`pace`（4 档）、`style`（6 种情感）。

```bash
# 3.8：逐句给语气，两人对话加语气词
python3 scripts/run.py scene --line gemini38 --cast "1=Kore" --cast "2=Fenrir" \
    --turn "1: 门外有人。" --turn "2: <whispering> 别开门。" \
    --style-turn "2=Low whisper, close mic" --filler-words --yes

# 2.5 Pro：有声书路线，口音 + 情感 + 场景
python3 scripts/run.py scene --line gemini25pro --cast "1=Kore" \
    --accent "British (RP)" --emotion Newscaster --pace Natural \
    --scene "A quiet room with a fireplace crackling softly." \
    --turn "1: 门开了。" --yes
```

3.8 的台词里可以插 40 个语气标签：`<laugh>` `<sigh>` `<whispering>` `<long pause>` `<gasp>` `<cry>` …
`voices --line gemini38` 会把全表打出来。

---

## `dialogue`：一次出完整段对手戏

普通 TTS 是「一段文本一个音色」，跑五个人要发五次、拼五次。
**V3 的 `dialogue` 是数组，每句自带 `voice`**：

```json
{"dialogue": [
  {"text": "你终于来了。",   "voice": "EkK5I93UQWFDigLMpZcX"},
  {"text": "我一直在等你。", "voice": "Z3R5wn05IrDiVCyEkUrK"}
]}
```

传成字符串会被挡回来（实测原文）：

```json
{"code":0,"msg":"input.dialogue: 类型不正确","data":null}
```

本包把组装做完了，你只管给角色和台词：

```bash
python3 scripts/run.py dialogue --voices "林晚=James" --voices "沈砚=Arabella" \
    --turn "林晚: 你终于来了。" --turn "沈砚: 我一直在等你。" --yes
```

三条规则：所有台词加起来 ≤ 5000 字符、每个角色必须分到音色、`voice` 只能是 67 个 ID 之一
（写名字本包自动换，重名取第一个并告一声）。

---

## 一条完整链路：剧本 → 分角色 → 配音 → 时间戳 → 对齐字幕

```bash
# 1) 剧本存成 UTF-8，一行一句「角色: 台词」，# 开头是注释
#    林晚: 你终于来了。
#    沈砚: 我一直在等你。

# 2) 干跑：只看请求体对不对，不发请求、不冻结
python3 scripts/run.py dialogue --script 剧本.txt \
    --voices "林晚=James" --voices "沈砚=Arabella" --dry-run

# 3) 真跑：一次出完整段对手戏
python3 scripts/run.py dialogue --script 剧本.txt \
    --voices "林晚=James" --voices "沈砚=Arabella" --yes

# 4) 逐句要时间戳（v2 / turbo 的 --timestamps），拿去对齐字幕
python3 scripts/run.py speak --line v2 --text "门开了。" --voice James --timestamps --yes

# 5) 追结果
python3 scripts/run.py task --task-id task_xxx
```

脚本化时用 `--json`：固定给 `taskId` 与 `audioUrls` 两个键，其余字段各线不完全一样。
时间戳字段以实际返回为准，`speak` 会把原始返回一并打出来。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检：Key / 应用 / 8 个端点 / 价目口径 / 查询路由
python3 scripts/run.py doctor

# 3) 挑音色
python3 scripts/run.py voices --line v2

# 4) 先算钱，再出声
python3 scripts/run.py cost
python3 scripts/run.py speak --text "你终于来了。" --voice James --yes
```

`doctor` 默认**一个 POST 都不发**：它只用只读接口（余额 / 应用目录 / 价目表 / 任务查询）
就能确认 8 个端点已经注册。想看端点真实返回时加 `--probe-post`：
8 个端点各打一次坏参数，每条冻结 60 点后原路退回，**净 0**。

---

## 三条别人不会告诉你的

### 一、`voice` 是 20 位 ID，不是名字

67 个 ID 写在枚举里，名字只出现在字段说明文字中。实测传名字出去：

```json
{"code":0,"msg":"input.voice: 不在允许选项内","data":null}
```

本包 `--voice James` 自动换成 `EkK5I93UQWFDigLMpZcX`；`Mark` / `Hope` / `Viraj` 各有两个 ID，
取第一个并在 stderr 告一声。想自己填就 `voices --line v2` 复制 ID。

### 二、参数校验失败也是 HTTP 200

```json
{"code":0,"msg":"input.text: 缺少必填参数","data":null}
```

状态码没有区分度，判成功只能看 `code == 1`。Gemini 三条线遇到类型错更直接：HTTP 500
「服务内部错误」，同样不建单，冻结的 60 点原路退回（`refund:sync_error`）。流水长这样：

```
20:57:07  charge  -60  reserve_sync:/api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
20:57:11  refund  +60  refund:sync_error:/api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
```

### 三、2.5 Pro 的音色表和 3.8 不是同一张

3.8 有 70 个 `voice_name`、2.5 Pro 只有 30 个，而且 2.5 Pro 的 `accent` 是必填（默认 Neutral）。
拿 3.8 的名字打 2.5 Pro 会白跑一次，所以本包按线在**本地**校验：报错时一个请求都没发。

---

## 常用命令

```bash
python3 scripts/run.py catalog                                     # 8 条线 + 接口 code + 音色数
python3 scripts/run.py voices --line gemini38                      # 70 音色 + 40 语气标签
python3 scripts/run.py cost --tasks 5                              # 五条任务的下限
python3 scripts/run.py speak --text "…" --voice Arabella --speed 0.9 --stability 0.4 --yes
python3 scripts/run.py speak --text "…" --voice James --timestamps --yes
python3 scripts/run.py dialogue --script 剧本.txt --voices "1=James" --voices "2=Arabella" --yes
python3 scripts/run.py scene --line gemini38 --cast "1=Kore" --cast "2=Fenrir" --turn "1: 门外有人。" --turn "2: <whispering> 别开门。" --filler-words --yes
python3 scripts/run.py design --name "深夜电台-阿岚" --audio-id achernar --description "低沉、微哑、语速偏慢的深夜电台男声" --yes
python3 scripts/run.py character --image-url "https://…/head.jpg" --description "银白短发、未来风机能夹克" --character-name 阿岚 --yes
python3 scripts/run.py task --task-id task_xxx
python3 scripts/run.py log --limit 10
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--line` | `v2` | `speak` 用 v2 / turbo；`scene` 用 gemini38 / gemini38lite / gemini25pro |
| `--text` / `--text-file` | — | 单人台词，≤ 5000 字符（UTF-8） |
| `--voice` | 必填 | 音色 ID 或名字（67 个，见 `voices`） |
| `--speed` / `--stability` / `--similarity` / `--style-level` | — | V2 / Turbo 的情绪参数 |
| `--language-code` | — | 强制语言（只有 turbo 支持） |
| `--timestamps` | — | v2 / turbo 顺带要逐词时间戳 |
| `--turn` / `--script` | — | 「角色: 台词」重复给，或整份剧本文件 |
| `--voices` / `--cast` | 必填 | 角色=音色（V3 用 `--voices`，Gemini 用 `--cast`） |
| `--style-turn` | — | 逐句语气（只 3.8） |
| `--accent` / `--pace` / `--emotion` | — | 口音 / 语速 / 情感（只 2.5 Pro） |
| `--filler-words` | — | 两人对话加语气词（只 3.8） |
| `--budget` | 600 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实建单 / 只打印请求 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 8 条线 + 接口 code + 音色数 |
| `voices` | 免费 | 音色库：ElevenLabs 67 / 3.8 70 / 2.5 Pro 30 / Omni 30 |
| `cost` | 免费 | 下限估算（60 点/条） |
| `doctor` | 免费 | 自检（默认零 POST；`--probe-post` 深探也是净 0） |
| `speak` | **计费** | 单人配音（v2 / turbo） |
| `dialogue` | **计费** | 多人对白（v3） |
| `scene` | **计费** | 场景对话（gemini38 / gemini38lite / gemini25pro） |
| `design` | **计费** | 设计音色（omni） |
| `character` | **计费** | 造角色（character） |
| `task` | 免费 | 查任务 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺参数、音色不在表里、选项缩写） |
| `3` | 自检没过（`doctor` 出现 ×） |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "line": "v2", "code": "elevenlabs_text_to_speech_multilingual_v2",
 "taskId": "task_xxx", "audioUrls": ["https://…"], "estimatedPoints": 60}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`

`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`；`--json` 写在子命令**前后都可以**，
stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-pro-voice/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（params_schema + 实测返回）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 计费口径与保底

- `pricing` 的 115 条规则里没有 `media_services_33`，也没有 `elevenlabs_*` —— 全部落通配
  `{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}`：**上游实际点数 × 2，单笔保底 50 点**。
- 实测每次 POST 预冻结 **60 点**（50 × 站点 20% 加价），失败原路退回，净 0。
- 所以 `cost` 给的是**下限 60 点/条**。一条到底多少钱 = 上游按字数算的真实点数 × 2，真跑一条才看得见。
- 一次请求 = 一条任务：十句对白的群戏也是 1 条，不是 10 条。
- `--budget` 与 `--yes` 是本地闸门：预算内才发请求，`--yes` 到了才建单。

---

## 合规与边界

- 生成内容的合规责任在使用者：请用于有授权的剧本与合法用途。
- 声音克隆（3.8 的 `replica`）需要两段真人录音 + 本人同意声明，本包不代录、不代签。
- 真实扣费以任务完成时上游返回的点数为准，`cost` 给的是下限估算。
- 角色名的自动编号只影响 `speaker_id`，台词文本原样发送。

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
