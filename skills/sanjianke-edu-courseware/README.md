# 教育课件 · 一节课 5 样交付物
**一份大纲进去，出来一节课能直接交的 5 样东西。** 课件图 6 点/张（六分钱），
配音 0.18 点/字，口播视频 10 点/秒起，讲稿 / 字幕 / 章节索引 / 测验点全部本地 0 点生成。

一节 3 分钟的课件视频，fast 档 ≈ **1,800 点（18 元）**；一天交 3 节 ≈ **56.67 元**。

---

## 为什么按「一节课」交付

做课不是做一条片子。教研岗一天要交的是：

- 这节课拆成几个知识点、分成几节
- 每节的讲稿（多少字、讲多久）
- 每节的课件图（多大、什么风格、叫什么名字）
- 每节的配音、口播视频、字幕
- 学员从哪一节开始、看到哪解锁下一节、测验点在哪
- 整套课的风格是不是一个样

这些活单看都不难，难在**一节课要同时对齐 5 样东西**。本包把它们收进一个
`lesson.json`：拆课、配图提示、字幕时间轴、章节索引、测验题、每节文件名都在里面，
换人接手照着跑就行。

---

## 这个包和底层能力包的分工

| 层 | 包 | 管什么 |
|---|---|---|
| 单步能力 | GPT Image / 语音 / 数字人类能力包 | 一次调用怎么传参、一张图 / 一条音频怎么出 |
| 成片链 | `sanjianke-course-video` | 大纲 → 章节成片的一条流水线 |
| 岗位交付 | **本包** | 一节课的 5 样交付物、尺寸与命名、风格统一、交付清单、合规留档 |

底层包回答「接口怎么调」，成片链回答「一条片子怎么拼」，本包回答
**「教研岗今天要交什么、交成什么样、一共多少钱」**。三条线共用同一套官方接口，
`lesson.json` 可以直接喂给成片链，两边混用不冲突。

---

## 一节课拆成 7 步

| 步 | 做什么 | 命令 | 产物 | 花费 |
|---|---|---|---|---|
| 1 | 知识点 → 分节 | `lesson` | `lesson.json` | 0 点 |
| 2 | 每节讲稿 + 字数 | `lesson` | `script` / `chars` | 0 点 |
| 3 | 配图提示 + 风格统一 | `lesson` + `deck` | `imagePrompt` / `*-deck.md` | 0 点 |
| 4 | 出课件图 | `art` | `*-cover.png` / `*-s01.png` | 6 点/张 |
| 5 | 讲稿转配音 | `narrate` | `*-s01.mp3` | 0.18 点/字 |
| 6 | 口播视频 | `screen` 或 `talk` | `*-s01.mp4` | 10 点/秒起 |
| 7 | 字幕 + 章节索引 + 测验点 | `lesson` + `board` | `*-s01.srt` / 索引 / 清单 | 0 点 |

---

## 交付清单

| 交付物 | 数量 | 规格 | 命名 |
|---|---|---|---|
| 拆课 / 讲稿 / 字幕 / 索引 | 1 份 JSON + N 份 srt | UTF-8 | `<slug>-s01.srt` |
| 课件图 | N + 1 张（含封面） | 1536x864 PNG，16:9 | `<slug>-cover.png` / `<slug>-s01.png` |
| 分节配音 | N 条 | mp3，48 kHz | `<slug>-s01.mp3` |
| 口播视频 | N 条 | 1080p mp4 | `<slug>-s01.mp4` |
| 课程页素材 | 1 份 | 章节索引 + 测验点 + 进度 | `lesson.json` |

`board` 会把数量、规格、命名、单价、小计、合规项一次列全，交付前照着打勾。

---

## 价格（1 元 = 100 点，2026-11-07 现查 `/api/v1/pricing`）

| 环节 | 端点 | 单价 | 一节 3 分钟 |
|---|---|---|---|
| 课件图 | `POST /api/v1/images/generations` | 6 点/张 | 4 张 = 24 点 |
| 配音 | `apps/voice_tts/tts_async` | 0.18 点/字（上游实际点数 ×3） | 450 字 ≈ 81 点 |
| 一图口播 | `apps/pic_lipsync/submit` | 15 点/秒，单笔 50 点起 | 180 秒 = 2,700 点 |
| 课件出片 | `apps/image_human/submit` | fast 10 / standard 15 / 2k 30 / 4k 60 点/秒 | 180 秒 fast = 1,800 点 |

**一天 3 节 × 3 分钟**：主方案（课件图 + 配音 + 课件出片）≈ **5,667 点（56.67 元）**；
同样 3 节走一图口播 ≈ 8,367 点。两条路二选一，`board` 分开算，不叠加。

---

## 三条干货（都做成了默认动作）

### 一：`pic_lipsync` 的档位参数叫 `quality`，不叫 mode

`mode` 只切 `audio` / `text`；`quality` 才是 `standard` / `fast` / `max`。
`mode=text` 省掉录音，但**省不掉参考音色**：`audio_url` 仍必填，给 3–10 秒清晰人声最稳。
不传 quality 时上游按 standard 3 点/秒 收，我方 ×5 = 15 点/秒 —— 所以 `talk --quality` 必填。

### 二：`image_human` 省略 mode，会「出片标准档、收钱快速档」

`schema.default` 是 `standard`，`/pricing` 的 `defaultModel` 是 `fast`。省略 mode 时
画面按 standard 出、账单按 fast 记。本包 `screen --mode` 必填，`--duration` 也必填 ——
带上输入秒数，价格才会被费率卡锁死，`cost` 才算得准。

### 三：应用层 `/query` 每调一次就是一次的钱

历史流水：`nano_banana/query` 72 点/次，108 次 = 7,776 点。
本包在 http 层把任何以 `/query` 结尾的地址拦死，轮询只走
**GET `/api/v1/tasks/{id}`**（只读、免费）。`doctor` 也只发只读请求和一次空 prompt 422。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或：python3 scripts/a7w.py login --key sk-你的key

# 2) 自检（0 点）
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --sections 3 --seconds 180 --mode fast

# 4) 拆课 → 风格卡 → 交付清单（本地 0 点）
python3 scripts/run.py lesson --outline 课程大纲.md --slug buoyancy
python3 scripts/run.py deck --lesson lesson.json --write
python3 scripts/run.py board --lesson lesson.json
```

### 大纲怎么写

```markdown
# 初中物理 · 浮力入门

## 第1节 什么是浮力
- 知识点：浮力定义、方向、施力物体
- 讲稿：把一个木块放进水里，它会浮起来……
- 配图：木块浮在水面，箭头标出竖直向上的浮力
- 时长：150
- 测验：浮力的方向是？| A. 竖直向下 | B. 竖直向上 | C. 水平向前 | 答案 B
```

`##` 一行一节；`- 知识点 / 讲稿 / 配图 / 时长 / 测验 / 进度` 都是可选标签，
没写讲稿时会用知识点拼一句，没写时长用 `--seconds`。

---

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
```

**不加 `--yes` 会退 `4`**，并告诉你这次多少点；超 `--budget` 退 `5`，一个请求都不发。
想先看不花钱的请求：

```bash
python3 scripts/run.py art --lesson lesson.json --cover --dry-run
```

---

## 子命令

| 子命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 四条能力线 + 本地三步 + 价目 |
| `cost` | 免费 | 整门课先算钱 |
| `doctor` | 免费 | 只读自检 Key / 应用 / 价目 / 任务 / 上传 / 文生图 422 |
| `lesson` | 免费 | 大纲 → `lesson.json` |
| `deck` | 免费 | 风格卡 + 逐节配图提示词 |
| `board` | 免费 | 交付清单 + 命名 + 合规检查 |
| `upload` | 免费 | 本地素材 → 平台托管地址 |
| `art` | 6 点/张 | 课件图（要 `--yes`） |
| `narrate` | 0.18 点/字 | 分节配音（要 `--yes`） |
| `talk` | 15 点/秒 | 一图口播（要 `--yes`） |
| `screen` | 10/15/30/60 点/秒 | 课件图 + 配音 → 口播视频（要 `--yes`） |
| `status` | 免费 | 查任务 |
| `log` | 免费 | 本地台账 |

---

## 实测记录（本轮 0 点）

```
GET  /user/balance                        HTTP 200
GET  /api/v1/apps                         HTTP 200，22 个应用，四条链路全在架
GET  /api/v1/pricing                      HTTP 200，image_human fast=10 点/秒 等规则一致
GET  /api/v1/tasks/probe-no-such-task     HTTP 200「任务不存在」
POST /api/v1/images/generations {prompt:""}   HTTP 422（参数校验，0 点）
POST /api/v1/upload 不带 file              HTTP 200「请使用 file 字段提交一个文件」
GET  /user/balance/logs?limit=1           条数与最新时间前后不变
结论：本轮真实花费 0 点，没有任何 submit
```

---

## 边界

- 配图 / 音频 / 参考音色要给**公网可拉**的地址；`upload` 返回的托管地址有效期约 24 小时。
- 文生图返回的链接约 3 小时有效，及时转存。
- 按秒计费的任务先冻结、完成后按实际时长结算；任务失败全额退回。
- 预览、试跑一律用 `--dry-run`；真实提交一律核对 `cost` 给的点数。

---

## 文件结构

`
sanjianke-edu-courseware/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       四条链路契约 + 实测原文
│   └── troubleshooting.md    按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
`

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
