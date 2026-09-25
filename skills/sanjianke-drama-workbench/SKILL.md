---
name: sanjianke-drama-workbench
slug: sanjianke-drama-workbench
displayName: AI短剧制作工作台·多应用组合配方单镜头SOP与批量排产
description: "把 api.a7w.cn 上的生成应用搭成一张短剧制作工作台：哪个应用擅长什么、什么输入该配哪个、一个镜头从首帧到成片的六步 SOP、六套现成的组合配方（静态对话戏/动作戏/旁白戏/快剪混剪/老片修复/数字人口播）、多项目并行排产与按应用对账，全部写清「传什么、调哪个接口、拿回什么」。含零依赖客户端与成本测算脚本，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "AI 短剧制作工作台的成品 Skill：面向真正要出片的人，把 api.a7w.cn 上的 21 个生成应用搭成一条可复用的制作流水线。含应用能力矩阵与选型打分表（出图 / 出片 / 配音 / 口型 / 音乐 / 音效 / 超分各挑哪个、为什么），六套现成组合配方（静态对话戏、动作戏、旁白戏、快剪混剪、老片修复、数字人口播），一个镜头从首帧到成片的六步 SOP（每步写清传什么、调哪个接口、拿回什么、怎么验收），以及多项目并行排产、任务表断点续跑、按应用对账与成片抽检清单。含一个零依赖客户端与一个零依赖成本测算脚本。整套操作文档 + 脚本都在包里，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 短剧
  - 工作流
  - 批量出片
---

# AI 短剧制作工作台 · 多应用协同

**一张工作台，把 api.a7w.cn 上的生成应用按「一个镜头一条产线」搭起来用。**

不是教你写剧本 —— 那是创作侧的事。这里管的是**工具侧怎么配、怎么传、怎么验收**：

- 手上这张图 / 这段音频 / 这句台词，**该调哪个应用**？
- 一个镜头从首帧到成片，**六步分别传什么、拿回什么**？
- 六套常见戏份（对话、动作、旁白、混剪、修复、口播）**各自的配方是什么**？
- 多个项目并行时，**怎么排产、怎么断点续跑、怎么对账**？

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 按点数计费（1 元 = 100 点）。包里带成本测算脚本，**先算再跑** |
| 要装什么 | **什么都不用装**。零依赖客户端 + 零依赖测算脚本 |
| 要几把 Key | **一把**。全部应用共用同一套鉴权、同一份账单 |
| 要几个应用 | 核心 6 个覆盖 90% 场景，其余按需插拔（见第一节矩阵） |
| 能商用吗 | 可以。素材授权与内容合规责任由使用者承担 |

---

## 一、应用能力矩阵 · 传什么进、拿什么出

| 你要的 | 应用 | 接口 | 传什么进 | 拿什么出 |
|---|---|---|---|---|
| **出图** | `nano_banana` | `/submit` | 画面描述 +（可选）参考图 URL | 角色图 / 场景图 / 首帧 |
| **出片（通用）** | `full_video` | `/submit` | 文本 + 可选首尾帧 / 参考媒体 | 4～15 秒视频片段 |
| **出片（声画一起）** | `happy_horse` | `/submit` | 文本 + 可选 1～9 张参考图 | 带对白与音效的片段 |
| **出片（分辨率分档）** | `seedance` | `/create` | 文本 + 图 + 视频 + 音频任意组合 | 480p / 720p / 1080p 片段 |
| **角色配音** | `voice_tts` | `/clone_voice` + `/tts_async` | 参考音频 / 台词文本 | 音色 ID / 台词音频 |
| **换口型** | `lipsync` | `/submit` | 视频 URL + 音频 URL | 对口型后的视频 |
| **图让它开口** | `image_human` | `/submit` | 人物图 URL + 驱动音频 URL | 数字人口播视频 |
| **BGM** | `music_generation` | `/create` | 风格描述（`instrumental: true`） | 一首配乐 |
| **现成配乐** | `music_search` | `/search` | 关键词 | 候选曲目列表 |
| **音效 / 环境音** | `mmaudio` | `/submit` | 视频 URL + 音效描述 | 带音效的视频 |
| **超分** | `flashvsr` | `/submit` | 视频 URL | 高清成片 |
| **换动作 / 换人 / 换装** | `action_transfer` / `person_replacement` / `dressing_diffusion` | `/submit` | 参考图 + 视频 / 形象图 | 迁移后的视频 |

**路径规则**：一律 `/api/v1/apps/<应用代号>/<接口代号>`，
两个代号都用**下划线**。**不要用平台的 `endpoint_path` 字段拼 URL** ——
部分应用给出的路径属于别的路由族（如 `voice_tts` 给的是 `/v1/tts`），直接请求打不通。

> 现查最准：`python3 scripts/a7w.py apps` 与 `python3 scripts/a7w.py schema <应用代号>`。

---

## 二、选型打分表 · 五个视频应用怎么挑

| 你的约束 | 选它 | 为什么 |
|---|---|---|
| 不知道选谁 | `full_video` | **通用首选**，文 / 首尾帧 / 多模态参考都吃 |
| 要声画一起出 | `happy_horse` | 一阶段生成，对白与画面同时出，省一道配音 |
| 要分辨率分档交付 | `seedance` | 480p / 720p / 1080p 独立 SKU，还带素材管理 |
| 要多种参考混着用 | `wan` | 文字 + 角色参考（多图多音多视频）+ 视频编辑 |
| 只要快 | `grok_video` | 有快速档与标准档 |
| 对话戏、不想出整段视频 | `image_human` / `lipsync` | **图片 + 音频** 就够，比重生成视频便宜得多 |

```
要声音画面一起出        → happy_horse
要多种参考素材混着用    → wan
要按分辨率分档、要管理素材 → seedance
只要快                  → grok_video
静态对话戏              → image_human（只有图）或 lipsync（已有视频）
都不确定                → full_video
```

---

## 三、六套组合配方

**配方 = 一串按顺序调用的应用**。挑一套套进你的项目即可，细节见 `references/组合配方.md`。

| 配方 | 适合 | 应用的调用顺序 |
|---|---|---|
| **A 静态对话戏** | 两人对话、情绪戏、内心独白 | `nano_banana` → `voice_tts/clone_voice` → `voice_tts/tts_async` → `image_human` 或 `lipsync` → `mmaudio` |
| **B 动作戏** | 追逐、打斗、转场 | `nano_banana`（首帧） → `full_video`（多段 4～8 秒） → `mmaudio`（音效） → `flashvsr` |
| **C 旁白戏** | 剧情推进、时间跳跃 | `nano_banana`（场景图） → `voice_tts/tts_async`（旁白） → `music_generation`（BGM） → 本地合成 |
| **D 快剪混剪** | 预告、集锦、回顾 | `smart_clip` 系列接口 或 本地 ffmpeg 拼已有素材 → `voice_tts` → `music_generation` |
| **E 老片修复** | 老素材、糊素材重制 | `flashvsr`（超分） → `mmaudio`（补音效） 或 `seedsvc`（音色转换） |
| **F 数字人口播** | 解说、带货、口播矩阵 | `voice_tts/tts` → `image_human`（`fast` 档试跑） → `flashvsr`（按需） |

**选配方的判断口径**：**先看有没有「真人连续动作」** ——
没有就用配方 A/C（便宜得多），有就用 B/D。

---

## 四、一个镜头的六步 SOP

每一步都写清「传什么 → 调哪个接口 → 拿回什么 → 怎么验收」。

| 步 | 传什么 | 调哪个接口 | 拿回什么 | 验收 |
|---|---|---|---|---|
| **1 首帧** | 画面描述 +（可选）角色定妆图 | `POST /api/v1/apps/nano_banana/submit` | `task_id` → 图片 URL | 角色长相与定妆图一致；画幅正确 |
| **2 台词** | 台词文本 + 角色 `reference_id` | `POST /api/v1/apps/voice_tts/tts_async` | `task_id` → 音频 URL | 音色对、语气对、时长与分镜一致 |
| **3 出片** | 首帧图 + 运镜描述 | `POST /api/v1/apps/full_video/submit` | `task_id` → 视频 URL | 动作自然、无穿模、时长 4～15 秒 |
| **4 口型** | 视频 URL + 音频 URL | `POST /api/v1/apps/lipsync/submit` | `task_id` → 视频 URL | 口型同步、无音画错位 |
| **5 声音** | 视频 URL + 音效描述 | `POST /api/v1/apps/mmaudio/submit` | `task_id` → 视频 URL | 环境音贴合场景、不盖过台词 |
| **6 交付** | 视频 URL | `POST /api/v1/apps/flashvsr/submit` | `task_id` → 高清视频 URL | 分辨率达标、无异常锐化 |

> 没有台词 / 不需要口型的镜头，**跳过 2 和 4** —— 这两步是可选的，别硬走。
> 每步都把 `task_id` 写进 `tasks.csv`，断了能续。

---

## 五、三分钟跑通（最小闭环）

### 第一步：拿到你自己的 Key

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，用户中心创建 Key，新用户送点数。

### 第二步：先算钱

```bash
python3 scripts/cost_estimate.py --shots 15 --image 24 --duration 40 --tts-chars 1800
```

### 第三步：跑一个镜头

```bash
# 1) 首帧
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"generate","prompt":"短剧：雨夜街头，女主撑伞站在路灯下，中景，冷色调，写实电影感","aspect_ratio":"9:16"}' \
  --out shot01.png

# 2) 台词
python3 scripts/a7w.py call voice_tts tts_async \
  --body '{"text":"这雨，下了整整十年。","reference_id":"<角色音色 ID>"}' \
  --out shot01.mp3

# 3) 出片（把 shot01.png 传到公网拿到 URL 再用）
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"type":"text","text":"镜头缓慢推近，女主抬头看向路灯，雨滴打在伞面上"}],"ratio":"9:16","resolution":"720P","duration":6}' \
  --out shot01.mp4

# 4) 对口型
python3 scripts/a7w.py call lipsync submit \
  --body '{"video_url":"https://你的存储/shot01.mp4","audio_url":"https://你的存储/shot01.mp3"}' \
  --out shot01-lip.mp4
```

---

## 六、包里有什么

```
sanjianke-drama-workbench/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 应用矩阵与选型.md        能力矩阵、五个视频应用打分表、输入形态对照
│   ├── 组合配方.md              六套配方的逐步调用与参数
│   ├── 单镜头SOP.md             六步 SOP 的详细参数、验收标准与异常处理
│   ├── 排产与对账.md            多项目并行、任务表、断点续跑、按应用对账
│   ├── getting-started.md      注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、错误码、计费口径
└── scripts/
    ├── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
    └── cost_estimate.py        工作台成本测算（零依赖，不联网）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 先看平台上有哪些应用、某个应用有哪些接口
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema nano_banana
python3 scripts/a7w.py schema voice_tts

# 先算钱
python3 scripts/cost_estimate.py --shots 15 --duration 40

# 调接口（异步自动轮询到结束，--out 直接落盘）
python3 scripts/a7w.py call full_video submit --body '{...}' --out shot.mp4
```

---

## 七、素材要求

| 素材 | 要求 |
|---|---|
| 图片 / 视频 / 音频入参 | 一律**公网可访问的 URL**，不支持本地路径、不支持 Base64 |
| 参考音色 | mp3 / wav / ogg / flac；**干净单人声**效果最好 |
| 画幅 | 竖屏短剧统一 `9:16`，全流程别中途换 |
| 分辨率 | 全流程锁定同一档（如 720P），避免最后拼接时尺寸不一 |
| 本地文件 | **先传到对象存储拿到公网直链**，再来调 |

---

## 八、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿本地路径当入参** | 报参数错误 | 一律用**公网可访问的 URL** |
| **应用代号写成连字符** | 404 | 用下划线：`nano_banana`、`voice_tts`、`happy_horse` |
| **用 `endpoint_path` 拼 URL** | 打不通 | 只用 `/api/v1/apps/<应用代号>/<接口代号>` |
| **全流程没统一画幅** | 拼接时尺寸不一、要重裁 | 开工就把 `9:16` 写进每个接口的 `ratio` / `aspect_ratio` |
| **每个镜头都重出角色图** | 角色长相漂移、图片钱翻倍 | 先出定妆图，后续首帧走 `action=edit` + 同一张参考图 |
| **对话戏也全段生成视频** | 成本翻几倍 | 静态对话用配方 A：图片 + `image_human` / `lipsync` |
| **首尾帧与参考媒体混用** | 提交失败 | 两种模式分开用，一次只走一种 |
| **重复提交** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认状态 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`** |

---

## 九、多项目并行与对账

| 原则 | 做法 |
|---|---|
| **一个项目一张任务表** | `proj/<项目>/tasks.csv`，字段含 `shot_id` / `stage` / `app` / `task_id` / `status` / `points` |
| **断点续跑** | 重跑只补 `status != completed` 的行，不重做已成功的镜头 |
| **并发 2～4 路起步** | `429` 是排队上限到了；并发越高不一定越快 |
| **给 Key 设上限** | 跑批量前给 Key 设 quota，参数写错时能止损 |
| **按应用对账** | 按 `app` 汇总 `points`，一眼看出钱花在哪个应用上 |
| **成片抽检** | 每集抽查：口型对得上、画幅正确、音量不炸、无缺镜 |

```bash
# 按应用汇总本次项目的点数消耗（PowerShell 示例）
Import-Csv proj/ep01/tasks.csv | Group-Object app |
  ForEach-Object { "{0,-20} {1,10}" -f $_.Name, (($_.Group | Measure-Object points -Sum).Sum) }
```

`references/排产与对账.md` 里给了任务表结构、续跑规则与对账口径。
需要更贴合你流程的排产方案，加微信聊。

---

## 十、计费

| 项目 | 口径 | 参考价 |
|---|---|---|
| 出图 `nano_banana` | 按张 | 24 点/张（`nano-banana` · 1K） |
| 出片 `full_video` | 按分辨率 × 秒 | 参考 20 点/秒（1080P） |
| 出片 `happy_horse` | 按秒 | 720P **0.9 点/秒**；1080P **1.6 点/秒** |
| 配音 `voice_tts` | 按 Token | 输入 50 点/千 Token |
| 克隆音色 `clone_voice` | 按次 | 200 点/次（租户价） |
| 口型 `image_human` | 按驱动音频秒 | `fast` 1.5 / `standard` 2 / `2k` 4 / `4k` 8 点每秒 |
| 口型 `lipsync` | 按次 | 见 `schema lipsync` 的 `tenant_*` |
| BGM `music_generation/create` | 按次 | 65 点/次 |
| 搜曲 `music_search/search` | 按次 | 10 点/次 |
| 超分 `flashvsr` | 按秒 | 见 `schema flashvsr` 的 `tenant_*` |
| 查任务 `GET /api/v1/tasks/{id}` | — | **免费** |

1 元 = 100 点。**逐接口真实价用 `python3 scripts/a7w.py schema <应用代号>` 读 `tenant_*` 字段**，
最终以 `data.usage.points_cost` 的实际扣费为准。

---

## 十一、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的应用接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不生成剧本内容**：这里只管工具侧的调用与排产，创作侧另说
- **不替代素材与内容合规审查**：授权与合规责任由使用者承担
- **不含模型效果的主观排名**：各家迭代快，结论极易过期；选型以能力矩阵与你的实测为准

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
