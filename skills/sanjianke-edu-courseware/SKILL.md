---
name: sanjianke-edu-courseware
slug: sanjianke-edu-courseware
displayName: 教育课件 · 一节课 5 样交付物
description: "**一节课 60 分钟，交 5 样东西**：分节讲稿、16:9 课件图（6 点/张）、配音（0.18 点/字）、口播视频（10 点/秒起）、字幕与章节索引。`lesson` 读一份大纲 Markdown，直接写出知识点 / 分节 / 讲稿 / 配图提示 / 字幕 / 章节索引 / 测验点；`deck` 用一张风格卡把整套课件图的色板、字体、构图钉死；`board` 给出这个行业一节课的交付清单与命名规则。三个钱上的坑做成了默认动作：pic_lipsync 的档位参数真名是 quality、image_human 省略 mode 会「出片标准档、收钱快速档」、应用层 /query 每调一次都是一次的钱。零依赖，先 `cost` 再 `--yes`。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "教育课件的难点不在生成，而在「一节课」这个交付单位：教研要交讲稿、要交图、要交配音、要交视频、还要交章节索引和测验点，学员进度得跟着走。本包把这套活拆成 13 个命令，四条能力线全部走 api.a7w.cn 的官方接口：课件图用 gpt-image-2.6（6 点/张，与尺寸质量无关）、配音用 voice_tts/tts_async（按上游实际点数 ×3，约 0.18 点/字，单笔 6 点起）、一图口播用 pic_lipsync/submit（mode=text，quality 才是档位真名，15 点/秒、单笔 50 点起，text 模式省录音但 audio_url 参考音色仍必填）、课件出片用 image_human/submit（10/15/30/60 点/输入秒，mode 与 duration 都必填，否则出片与收钱走两个档）。本地三步 0 点：lesson 拆课、deck 统一风格、board 出交付清单与合规项。两道闸门在本地：cost 先算钱，超 --budget 直接退 5 且一个请求都不发，缺 --yes 退 4。轮询只走 GET /tasks/{id}，应用层 /query 在 http 层拦死。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 教育课件
  - 课程视频
  - api.a7w.cn
---

# 教育课件 · 一节课 5 样交付物

> **用自己的 Key**：在 [api.a7w.cn](https://api.a7w.cn/) 注册领 Key，本包不内嵌任何 Key。
> `python3 scripts/a7w.py login --key sk-你的key`

一份大纲进去，出来一节课的 5 样交付物：**讲稿 + 课件图 + 配音 + 口播视频 + 字幕与章节索引**。
一套课一个风格卡、一套命名、一张交付清单，换人接手也能接着跑。

## 这个包和底层能力包的分工

| 层 | 包 | 管什么 |
|---|---|---|
| 单步能力 | `sanjianke-gpt-image` / 语音 / 数字人类能力包 | 一次调用怎么传参、一张图 / 一条音频怎么出 |
| 成片链 | `sanjianke-course-video` | 大纲 → 章节成片的一条流水线 |
| 岗位交付 | **本包** | 一节课要交的 5 样东西、尺寸与命名、风格统一、交付清单、合规留档 |

底层包回答「这个接口怎么调」；本包回答「教研岗今天要交什么、交成什么样、一共多少钱」。
渲染走同一条官方接口，所以两边可以混用：本包出的 `lesson.json` 能直接喂给成片链。

## 一节课的拆法（7 步，前 3 步 0 点）

| 步 | 做什么 | 命令 | 产物 |
|---|---|---|---|
| 1 | 知识点 → 分节 | `lesson` | `lesson.json` 的 sections |
| 2 | 每节讲稿 + 字数 | `lesson` | 每节 `script` / `chars` |
| 3 | 配图提示 + 风格统一 | `lesson` + `deck` | `imagePrompt` / `*-deck.md` |
| 4 | 出课件图 | `art` | `*-cover.png` / `*-s01.png` |
| 5 | 讲稿转配音 | `narrate` | `*-s01.mp3` |
| 6 | 口播视频 | `screen`（或 `talk`） | `*-s01.mp4` |
| 7 | 字幕 + 章节索引 + 测验点 | `lesson` + `board` | `*-s01.srt` / 索引 / 交付清单 |

## 交付清单（这个行业一节课要交的东西）

| 交付物 | 数量 | 规格 | 命名 | 单价 |
|---|---|---|---|---|
| 拆课 / 讲稿 / 字幕 / 索引 | 1 份 JSON + N 份 srt | UTF-8 | `<slug>-s01.srt` | 0 点（本地） |
| 课件图 | N + 1 张（含封面） | 1536x864 PNG，16:9 | `<slug>-cover.png` / `<slug>-s01.png` | 6 点/张 |
| 分节配音 | N 条 | mp3，48 kHz | `<slug>-s01.mp3` | 0.18 点/字，单笔 6 点起 |
| 口播视频 | N 条 | 1080p mp4 | `<slug>-s01.mp4` | 10 / 15 / 30 / 60 点/秒 |
| 课程页素材 | 1 份 | 章节索引 + 测验点 + 进度 | `lesson.json` | 0 点（本地） |

**一天的量**：3 节 × 3 分钟，fast 档 ≈ **5,667 点（56.67 元）**；同样 3 节走一图口播 ≈ 8,367 点。
`board` 会把两条路一起算给你，主方案与替换方案不叠加。

## 价格（1 元 = 100 点，2026-11-07 现查 `/api/v1/pricing`）

| 环节 | 端点 | 单价 | 一节 3 分钟 |
|---|---|---|---|
| 课件图 | `POST /api/v1/images/generations` | 6 点/张 | 4 张 = 24 点 |
| 配音 | `apps/voice_tts/tts_async` | 0.18 点/字（×3 结算） | 450 字 ≈ 81 点 |
| 一图口播 | `apps/pic_lipsync/submit` | 15 点/秒，50 点起 | 180 秒 = 2,700 点 |
| 课件出片 | `apps/image_human/submit` | fast 10 / standard 15 / 2k 30 / 4k 60 点/秒 | 180 秒 fast = 1,800 点 |

## 三条行业干货（都做成了默认动作）

**一：`pic_lipsync` 的档位参数叫 `quality`，不叫 mode。** `mode` 只切 `audio` / `text`；
`quality` 才是 `standard` / `fast` / `max`。`mode=text` 省掉录音，但**省不掉参考音色**：
`audio_url` 仍必填，给 3–10 秒清晰人声最稳。不传 quality 时上游按 standard 3 点/秒 收，
我方 ×5 = 15 点/秒，所以 `talk --quality` 必填。

**二：`image_human` 省略 mode，会「出片标准档、收钱快速档」。** schema 默认 `standard`，
`/pricing` 的 `defaultModel` 是 `fast`；两头不一致时画面按 standard 出、账单按 fast 记。
本包 `screen --mode` 必填，`--duration` 也必填 —— 带上输入秒数，价格才被费率卡锁死。

**三：应用层 `/query` 每调一次就是一次的钱。** 历史流水：`nano_banana/query` 72 点/次，
108 次 = 7,776 点。本包在 http 层把任何以 `/query` 结尾的地址拦死，
轮询只走 **GET `/api/v1/tasks/{id}`**（只读、免费）。

## 三步上手

```bash
python3 scripts/run.py doctor                        # 1) 自检（只读 + 空 prompt 422，0 点）
python3 scripts/run.py cost --sections 3 --seconds 180 --mode fast   # 2) 先算钱
python3 scripts/run.py lesson --outline 课程大纲.md --slug buoyancy   # 3) 拆课（本地 0 点）
python3 scripts/run.py deck --lesson lesson.json --write             #    风格卡
python3 scripts/run.py board --lesson lesson.json                    #    交付清单
```

## 常用命令

```bash
# 出课件图（6 点/张；--cover 多出 1 张封面）
python3 scripts/run.py art --lesson lesson.json --cover --outdir ./课件 --yes

# 本节配音（0.18 点/字，单笔 6 点起）
python3 scripts/run.py narrate --lesson lesson.json --section 1 --voice 音色ID --yes

# 本地素材转托管地址（免费；配图与音频要公网可拉）
python3 scripts/run.py upload --file ./课件/buoyancy-s01.png

# 一图口播：一图 + 参考音色 + 文案（quality 必填）
python3 scripts/run.py talk --image-url "https://oss.gpu.likeadmin.cn/openapi/…" \
    --audio-url "https://oss.gpu.likeadmin.cn/openapi/…" \
    --content "本节口播文案" --quality standard --yes

# 课件图 + 配音 → 数字人视频（mode / duration 必填）
python3 scripts/run.py screen --image-url "https://oss.gpu.likeadmin.cn/openapi/…" \
    --audio-url "https://oss.gpu.likeadmin.cn/openapi/…" --duration 180 --mode fast --yes

python3 scripts/run.py status --task-id task_xxx     # 查任务（免费，只走这条）
```

## 子命令

| 子命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 四条能力线 + 本地三步 + 价目 |
| `cost` | 免费 | 整门课先算钱（分节数 × 秒数） |
| `doctor` | 免费 | 只读自检 Key / 应用 / 价目 / 任务 / 上传 / 文生图 422 |
| `lesson` | 免费 | 大纲 → `lesson.json`（讲稿 / 字幕 / 索引 / 测验点） |
| `deck` | 免费 | 风格卡 + 逐节配图提示词 |
| `board` | 免费 | 交付清单 + 命名 + 合规检查 |
| `upload` | 免费 | 本地素材 → 平台托管地址 |
| `art` | **6 点/张** | 课件图（要 `--yes`） |
| `narrate` | **0.18 点/字** | 分节配音（要 `--yes`） |
| `talk` | **15 点/秒** | 一图口播，文案驱动（要 `--yes`） |
| `screen` | **10/15/30/60 点/秒** | 课件图 + 配音 → 口播视频（要 `--yes`） |
| `status` | 免费 | 查任务 |
| `log` | 免费 | 本地台账 |

## 退出码与 `--json`

`0` 成功 / `2` 用法错 / `4` 需 `--yes`（并告诉你多少点）/ `5` 预算不足（一个请求都不发）/
`6` 调用失败 / `1` 内部错 / `130` 中断。

成功：`{"ok": true, "taskId": "...", "estimatedPoints": 1800, ...}`
失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`
`--json` 放在子命令前后都可以，stdout 只有一个 JSON 文档。

## 实测与边界

- 本轮花费 **0 点**：只读 GET + 空 prompt 422 + 空上传，没有任何 submit。
- 配图 / 音频 / 参考音色要给**公网可拉**的地址：`upload` 返回的
  `oss.gpu.likeadmin.cn/openapi/…` 可直接用，有效期约 24 小时。
- 文生图返回的链接约 3 小时有效，及时转存；任务失败全额退回。
- 按秒计费的任务先冻结、完成后按实际时长结算；`cost` 给的是预估。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
