---
name: sanjianke-short-video-maker
slug: sanjianke-short-video-maker
displayName: AI短视频一键生成·选题脚本配音画面字幕全流程批量出片
description: "给一个选题就能出片：大模型写脚本 → TTS 出配音 → 出图定画面 → 图生视频补动感 → 时间轴压字幕 → 配 BGM → 本地合成，七道工序全部走 api.a7w.cn，一把 Key 跑完。支持 9:16 竖屏 / 16:9 横屏 / 1:1 方形，字幕时间轴两种做法都写清了怎么落地。含选题清单批量跑法、成本测算口径与常见坑，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "AI 短视频量产的成品 Skill：一个选题进，一条能发的短视频出。七道工序全部走 api.a7w.cn —— 选题与脚本走 OpenAI 兼容模型网关（75 个在架模型换 model 即换），配音走 `voice_tts`，画面走 `nano_banana` 出图，动感走 `full_video` / `happy_horse` 图生视频，字幕时间轴给出「分段合成累计时长」与「`stt` 精确时间戳」两种可落地做法，BGM 走 `music_generation` / `music_search`，成片超分走 `flashvsr`，口播号另有 `image_human` 一条路。支持竖屏 9:16 / 横屏 16:9 / 方形 1:1，含选题清单批量跑法、真实计费口径（1 元 = 100 点）、成本结构与常见坑。整套操作文档 + 零依赖客户端都在包里，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 短视频
  - 批量出片
  - 口播
---

# AI 短视频一键生成 · 选题到成片

做口播类、科普类、图文解说类短视频，最枯燥的不是创意，而是**重复工序**：
写一版脚本、找一堆能用的画面、配音、对时间轴压字幕、挑一首不炸的音轨、导出成竖屏。
选题一多，这条流水线就压垮人。

**给一个选题，按七道工序走完，出一条能发的短视频。**
所有 AI 环节都走 `api.a7w.cn`，一把 Key 跑完，不用自己部署任何模型。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 按点数计费（1 元 = 100 点）。**一条 60 秒竖屏约 8～15 元**，大头在画面 |
| 要多久 | 脚本与配音几秒；出图与视频逐段生成，一条片子约 5～15 分钟 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端；本地拼接需要 ffmpeg |
| 什么画幅 | `9:16` 竖屏 / `16:9` 横屏 / `1:1` 方形，全流程锁一个 |
| 能商用吗 | 可以。素材与音乐授权、内容合规责任由使用者承担 |

---

## 一、七道工序，各自调哪个应用

| 工序 | 用什么 | 接口 | 输入 → 输出 |
|---|---|---|---|
| **1 选题脚本** | 模型网关（OpenAI 兼容） | `POST /api/v1/chat/completions` | 选题 → 口播稿 + 分段 + 画面关键词 |
| **2 配音** | `voice_tts` | `POST /api/v1/apps/voice_tts/tts`（短）<br>`.../tts_async`（长） | 分段文案 → 逐段音频 |
| **3 出图** | `nano_banana` | `POST /api/v1/apps/nano_banana/submit` | 画面关键词 → 配图 / 首帧 |
| **4 出片** | `full_video`（首选）<br>`happy_horse`（声画一起出） | `.../full_video/submit`<br>`.../happy_horse/submit` | 首帧 + 运镜 → 4～15 秒片段 |
| **5 字幕** | `voice_tts/stt` 或 分段累计 | `POST /api/v1/apps/voice_tts/stt` | 配音音频 → 文字与时间轴 |
| **6 音乐** | `music_generation` / `music_search` | `.../music_generation/create`<br>`.../music_search/search` | 情绪描述 / 关键词 → BGM |
| **7 合成超分** | 本地 ffmpeg（+ 可选 `flashvsr`） | `POST /api/v1/apps/flashvsr/submit` | 片段 + 配音 + 字幕 + BGM → 成片 |

**接口路径一律是 `/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都用**下划线**。
现查：`python3 scripts/a7w.py apps` 与 `python3 scripts/a7w.py schema <应用代号>`。

### 两条可选支线

| 你的号是 | 走哪条 |
|---|---|
| **口播号 / 带货号**（要真人形象出镜） | 工序 2 之后直接上 `image_human/submit`：人物图 + 配音 → 数字人口播视频，跳过 3 和 4 |
| **素材混剪号**（手上已有素材） | 用 `smart_clip` 系列：`template` → `template_detail` → `broadcast_mixcut`，跳过 3 和 4 |

---

## 二、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，在控制台创建一个 API Key（形如 `sk-...`），
填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：写脚本（模型网关）

让模型**按「一个镜头一句话」分段输出 JSON**，后面每一步都用得上：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{
      "role": "user",
      "content": "你是短视频编导。围绕选题「人工智能如何改变日常生活」写一条 60 秒竖屏口播稿。要求：1) 开头 3 秒必须有钩子；2) 分成 8～12 个镜头，每个镜头一句话，不超过 25 字；3) 每个镜头给一个英文画面关键词（用于文生图）。输出 JSON 数组，每项含 shot_id、line、visual。只输出 JSON。"
    }]
  }'
```

**换模型就是换 `model` 字符串**，不用换地址、不用换 Key、账单还是同一份。
日常出稿用 `DeepSeek-V4-Flash`（快、省），要打磨用 `DeepSeek-V4-Pro` 或 `Qwen3.7-Max`。

### 第三步：逐段配音

```bash
python3 scripts/a7w.py call voice_tts tts \
  --body '{"text":"你有没有发现，手机越来越懂你了？","format":"mp3","prosody":{"speed":1.05}}' \
  --out dub/shot01.mp3
```

长文案（>500 字）用 `tts_async`。想用自己的声音，先 `clone_voice` 一次拿音色 ID。

### 第四步：出图与出片

```bash
# 出图（每个镜头一张）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"generate","prompt":"a smartphone interface with AI assistant, soft morning light, clean minimal, 9:16 vertical","aspect_ratio":"9:16"}' \
  --out imgs/shot01.png

# 图生视频（要动感时才做，能省则省）
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"type":"text","text":"镜头缓慢推近，屏幕上的光晕轻轻流动"}],"ratio":"9:16","resolution":"720P","duration":5}' \
  --out clips/shot01.mp4
```

### 第五步：配 BGM

```bash
# 现成曲子
python3 scripts/a7w.py call music_search search --body '{"keyword":"轻快 科技","page_size":10}'

# 或者生成一首专属的
python3 scripts/a7w.py call music_generation create \
  --body '{"type":"generate","prompt":"轻快的科技感电子音乐，节奏明快，情绪向上，无人声","instrumental":true}' \
  --out bgm.mp3
```

### 第六步：本地合成

用 ffmpeg 按时间轴拼接画面、混入配音与 BGM、烧字幕：

```bash
# 1) 画面拼接（片单文件 concat.txt 每行 file 'clips/shot01.mp4'）
ffmpeg -f concat -safe 0 -i concat.txt -c copy video.mp4

# 2) 配音拼接
ffmpeg -f concat -safe 0 -i dub.txt -c copy voice.mp3

# 3) 混音（BGM 压低，别盖过人声）
ffmpeg -i voice.mp3 -i bgm.mp3 -filter_complex \
  "[1:a]volume=0.18[b];[0:a][b]amix=inputs=2:duration=first[a]" -map "[a]" mix.mp3

# 4) 合成 + 烧字幕
ffmpeg -i video.mp4 -i mix.mp3 -vf "subtitles=sub.srt" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest out.mp4
```

**合成放本地做**：便宜、可反复修改，不用重复扣点。

### 第七步（可选）：超分

```bash
python3 scripts/a7w.py call flashvsr submit \
  --body '{"input_url":"https://你的存储/out.mp4"}'
```

> 平台会二次压缩的渠道（抖音 / 小红书 / 视频号），超分收益有限；
> 真要交付母版才做这一步。

---

## 三、字幕时间轴怎么来（两条可落地的做法）

字幕最容易卡住的地方就是「时间轴从哪来」。两条路都可行，按你的情况选。

### 做法一：分段合成，累计时长（**推荐，最可控**）

每句话单独合成一段音频，用每段音频的真实时长累加，生成 SRT。

```
shot01.mp3  时长 3.2 秒  → 00:00:00,000 → 00:00:03,200
shot02.mp3  时长 4.1 秒  → 00:00:03,200 → 00:00:07,300
shot03.mp3  时长 2.8 秒  → 00:00:07,300 → 00:00:10,100
```

**优点**：时间轴与画面一一对应（因为画面也是按镜头出的），不用再做对齐；
改一句台词只重做那一段。

```bash
# 取每段音频时长（ffprobe）
ffprobe -v error -show_entries format=duration -of csv=p=0 dub/shot01.mp3
```

一段 20 行的 Python 就能把「文案 + 时长」写标准 SRT，模板见
`references/字幕与合成.md`。

### 做法二：用 `stt` 拿精确时间戳

把整条配音传回 `voice_tts/stt`，把 `ignore_timestamps` 设为 `false`，
让平台返回精确时间戳，再转成 SRT：

```bash
python3 scripts/a7w.py call voice_tts stt \
  --body '{"audio_url":"https://你的存储/voice.mp3","language":"zh","ignore_timestamps":false}'
```

**适合**：文案是一整段、画面与句子不要求严格对应（如素材混剪号）。
**先跑一次 `python3 scripts/a7w.py schema voice_tts` 核对参数与返回结构**，
以实际返回为准。

> 两条路的取舍：**画面按镜头出 → 用做法一；画面是现成素材池 → 用做法二。**

---

## 四、画幅与形态

| 画幅 | 尺寸 | 适合 |
|---|---|---|
| `9:16` 竖屏 | 1080×1920 | 抖音 / 快手 / 视频号 / 小红书 |
| `16:9` 横屏 | 1920×1080 | B 站 / YouTube / 视频号横版 |
| `1:1` 方形 | 1080×1080 | 部分信息流投放位 |

**全流程锁一个画幅**：`nano_banana` 传 `aspect_ratio`，
`full_video` 传 `ratio`，本地合成的输出也保持一致。
**中途换尺寸，最后拼接一定要重裁，白花时间。**

---

## 五、批量：一个清单跑一批

把选题写成 JSONL（一行一个），循环跑整条流水线：

```jsonl
{"topic": "人工智能如何改变日常生活", "aspect": "9:16", "seconds": 60}
{"topic": "三个让厨房变整齐的小习惯", "aspect": "9:16", "seconds": 45}
```

**批量纪律**：

| 纪律 | 做法 |
|---|---|
| **先跑通一条** | 一条完整成片验证后再铺开，别一上来就 50 条 |
| **并发 2～4 路** | 视频生成从低并发起步；`429` 说明排队上限到了 |
| **一条一张任务表** | 记 `topic` / `shot_id` / `task_id` / `status`，断了能续 |
| **给 Key 设上限** | 批量前把 quota 设成预算的 1.2 倍，参数写错时能止损 |
| **边出边抽检** | 每条出完抽查：字幕对得上、音量不炸、画幅正确 |

`references/批量出片.md` 里给了清单结构、续跑规则与批量脚本骨架。
需要更贴合你流程的批量方案，加微信聊。

---

## 六、包里有什么

```
sanjianke-short-video-maker/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 出片流水线.md            七道工序的衔接、每步参数与验收
│   ├── 字幕与合成.md            两种时间轴做法、SRT 生成、ffmpeg 合成命令
│   ├── 批量出片.md              选题清单、并发、续跑、对账
│   ├── 接口速查.md              全部用到的应用与接口参数
│   ├── getting-started.md      注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 看平台上有哪些应用、某个应用有哪些接口与参数
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py schema nano_banana

# 配音 / 出图 / 出片（异步接口自动轮询到结束，--out 直接落盘）
python3 scripts/a7w.py call voice_tts tts --body '{...}' --out shot01.mp3
python3 scripts/a7w.py call nano_banana submit --body '{...}' --out shot01.png
python3 scripts/a7w.py call full_video submit --body '{...}' --out shot01.mp4

# 查任务（免费）
python3 scripts/a7w.py task <task_id>
```

---

## 七、素材要求

| 素材 | 要求 |
|---|---|
| 图片 / 视频 / 音频入参 | 一律**公网可访问的 URL**，不支持本地路径、不支持 Base64 |
| 生成用的提示词 | 画面关键词建议英文，出图稳定性更好 |
| 配音文案 | 单段 ≤500 字走同步 `tts`；更长走 `tts_async`（≤10000 字） |
| 音频格式 | mp3 / wav / ogg；单文件建议 ≤50MB，时长 ≤30 分钟 |
| 参考音色 | mp3 / wav / ogg / flac；干净单人声效果最好 |
| 本地文件 | **先传到对象存储拿到公网直链**，再来调 |

---

## 八、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿本地路径当入参** | 报参数错误 | 一律用**公网可访问的 URL** |
| **应用代号写成连字符** | 404 | 用下划线：`nano_banana`、`voice_tts`、`happy_horse` |
| **用 `endpoint_path` 拼 URL** | 打不通 | 只用 `/api/v1/apps/<应用代号>/<接口代号>` |
| **全流程没锁画幅** | 拼接时尺寸不一要重裁 | 开工就把 `9:16` 写进每个接口 |
| **每个镜头都生成视频** | 成本翻几倍 | 静态画面用**图片 + 本地缓慢推拉**（ffmpeg zoompan），只给需要动感的镜头出片 |
| **字幕对不上画面** | 用整段转写的粗糙时间轴 | 画面按镜头出就用「分段累计时长」的做法一 |
| **BGM 盖过人声** | 听不清台词 | BGM 压到 0.15～0.2 倍音量再混 |
| **长文案走同步 `tts`** | 报错或截断 | >500 字改用 `tts_async` |
| **重复提交** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认状态 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**；模型网关看有没有 `choices` |

---

## 九、计费

| 工序 | 口径 | 参考价 |
|---|---|---|
| 脚本撰写（模型网关） | 按点数/百万 Token | 一条 60 秒口播稿约几角钱 |
| 配音 `voice_tts/tts` | 输入 50 点/千 Token | 200 字台词约 10 点 = 0.10 元 |
| 克隆音色 `clone_voice` | 按次 | 200 点/次（租户价，**做一次长期用**） |
| 出图 `nano_banana` | 按张 | 24 点/张（1K） |
| 图生视频 `full_video` | 按分辨率 × 秒 | 参考 20 点/秒（1080P）；720P 更省 |
| 口播数字人 `image_human` | 按驱动音频秒 | `fast` 1.5 / `standard` 2 / `2k` 4 / `4k` 8 点每秒 |
| 字幕 `voice_tts/stt` | 按次 | 30 点/次 |
| BGM `music_generation/create` | 按次 | 65 点/次 |
| 搜曲 `music_search/search` | 按次 | 10 点/次 |
| 超分 `flashvsr` | 按秒 | 见 `schema flashvsr` 的 `tenant_*` |
| 查任务 | — | **免费** |

1 元 = 100 点。**一条 60 秒竖屏（8 个镜头 + 配音 + BGM，含 30% 废片率）约 8～15 元**，
其中画面占大头。

> **省钱按优先级：**
> 1. **静态画面别出视频** —— 用图片 + 本地缓慢推拉（ffmpeg zoompan），免费做出「活」的感觉；
> 2. **少出图** —— 同一场景复用配图，别每句都重出；
> 3. **分辨率锁够用档** —— 竖屏短剧平台会二次压缩，720P 通常够；
> 4. **音色克隆只做一次** —— 之后所有片子复用同一个 `reference_id`。

> 平台同时给出标准价与租户实际结算价，**以你账号里实际扣费为准**。
> 每次返回的 `data.usage.points_cost` 就是本次真实扣费。

---

## 十、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型网关与生成应用（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出；本地拼接由你自行调用 ffmpeg |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代素材与音乐授权审查**：用于商用或对外发布前，请自行确认各来源的授权条款
- **不替代内容合规审查**：生成内容的标识与合规责任由使用者承担

---

## 关于这个 Skill

**作者亲测实操后发布，下载后可直接使用，自用商用都可以。**

所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/) —— 一把 API Key 打通
大模型、语音、图像、视频、数字人等全部算力，注册即送点数，按量计费、没有月费。

| 你可能想问 | 答案 |
|---|---|
| 要不要额外部署 | 不用。**下载本包即可使用**，不必去别处找源码 |
| 怎么开始 | 到 api.a7w.cn 注册领 Key → 填进 `A7W_API_KEY` → 一条命令跑起来 |
| 能不能商用 | 可以 |
| 遇到问题找谁 | 见文末「联系我们」，作者本人答疑 |

> 使用中碰到任何问题 —— 报错、效果不理想、想省钱、想批量 —— 都欢迎加微信聊。
> 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的示例。

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
