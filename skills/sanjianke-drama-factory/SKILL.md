---
name: sanjianke-drama-factory
slug: sanjianke-drama-factory
displayName: AI短剧量产工厂·小说改编剧本分镜图视频配音全流程一键出片
description: "把一本小说变成能投放的短剧：策划 → 编剧 → 分镜 → 出图 → 出片 → 配音 → 混音 → 超分，八道工序全部走 api.a7w.cn 的生成应用，一条 Base URL、一把 Key 跑完。含三道质量门禁（改编可行性、故事骨架、分镜铁律）与一份出片成本测算脚本，批量出片不靠手感靠口径。整套操作文档（工序-应用-接口对照表、每道工序的真实调用、成本测算、批量排产、常见坑）+ 零依赖客户端都在包里，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "AI 短剧量产的成品 Skill：一本小说进，能投放的短剧出。八道工序各自对应 api.a7w.cn 上的一个生成应用 —— 策划与编剧走 OpenAI 兼容模型网关（DeepSeek / 千问 / 智谱等 75 个在架模型换 model 即换），出图走 `nano_banana`，出片走 `full_video` / `happy_horse` / `seedance`，角色配音走 `voice_tts` 的 `clone_voice` + `tts_async`，口型走 `lipsync` / `image_human`，背景音乐与音效走 `music_generation` / `music_search` / `mmaudio`，成片超分走 `flashvsr`。含三道质量门禁（小说改编可行性评估、故事骨架十二项审查、分镜表铁律与片段过渡桥梁）与一份零依赖出片成本测算脚本，批量出片不靠手感靠口径。整套操作文档 + 客户端 + 测算脚本都在包里，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 短剧
  - 小说改编
  - 批量出片
---

# AI 短剧量产工厂 · 小说到成片

把一本小说，变成能投放的短剧。

这里是一整套跑通「**策划 → 编剧 → 分镜 → 出图 → 出片 → 配音 → 混音 → 超分**」的
工业化流程 —— 不是零散技巧，而是可以直接照着执行、批量复制的作业体系。
**八道工序全部走 api.a7w.cn 的生成应用，一把 Key 跑完，不用自己部署任何模型。**

| 你最关心 | 答案 |
|---|---|
| 多少钱 | 按点数计费（1 元 = 100 点）。**2 分钟一集约 30～45 元**，成本近八成在视频生成 |
| 要多久 | 视频逐段生成，单段 4～15 秒；一集 2 分钟约 10～20 个片段 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端与成本测算脚本 |
| 要几把 Key | **一把**。模型网关与全部生成应用共用同一套鉴权、同一份账单 |
| 能商用吗 | 可以。改编他人作品需自行取得授权，内容合规责任由使用者承担 |

---

## 一、八道工序，各自调哪个应用

| 工序 | 用什么 | 接口 | 输入 → 输出 |
|---|---|---|---|
| **1 策划** | 模型网关（OpenAI 兼容） | `POST /api/v1/chat/completions` | 小说文本 → 改编可行性结论 + 故事骨架 |
| **2 编剧** | 模型网关 | `POST /api/v1/chat/completions` | 骨架 → 分集大纲 + 每集剧本（含台词） |
| **3 分镜** | 模型网关 | `POST /api/v1/chat/completions` | 剧本 → 分镜表 JSON（镜号 / 画面 / 台词 / 时长） |
| **4 出图** | `nano_banana` | `POST /api/v1/apps/nano_banana/submit` | 分镜描述 + 角色形象 → 角色图 / 场景图 / 首帧 |
| **5 出片** | `full_video`（通用首选）<br>`happy_horse`（声画一起出）<br>`seedance`（分辨率分档） | `.../full_video/submit`<br>`.../happy_horse/submit`<br>`.../seedance/create` | 首帧图 + 运镜描述 → 4～15 秒视频片段 |
| **6 配音** | `voice_tts` | `.../voice_tts/clone_voice`<br>`.../voice_tts/tts_async` | 参考音频 → 角色音色<br>台词 → 配音音频 |
| **7 口型** | `lipsync`（有视频）<br>`image_human`（只有图） | `.../lipsync/submit`<br>`.../image_human/submit` | 视频 / 图 + 音频 → 对口型成片 |
| **8 混音与超分** | `music_generation` / `music_search` / `mmaudio` / `flashvsr` | `.../music_generation/create`<br>`.../music_search/search`<br>`.../mmaudio/submit`<br>`.../flashvsr/submit` | 风格描述 / 关键词 / 视频 → BGM、音效、超分成片 |

**接口路径一律是 `/api/v1/apps/<应用代号>/<接口代号>`**，两个代号都用**下划线**，
都可以用 `python3 scripts/a7w.py schema <应用代号>` 现查。

### 三条可替换的支线

| 需求 | 用哪个 |
|---|---|
| 把 A 的动作搬到 B 身上 | `action_transfer/submit`（分 fast / standard / max 三档） |
| 把视频里的人换成另一个 | `person_replacement/submit` |
| 给角色换服装 | `dressing_diffusion/submit` |

---

## 二、三道质量门禁（省钱的关键）

**改一句话的成本，到分镜阶段是十几张图，到出片阶段是几百块。**
所以问题必须在最便宜的那一步拦下。

### 门禁一：小说改编可行性（动手前）

先做三件事，别急着生成：

1. **看体量与结构**：多少章、多少字、是否**单线推进**。短剧要单线，多线并行的长篇改起来会丢掉大半。
2. **找核心矛盾**：主角的「强欲望」和「强阻碍」分别是什么？对照**矛盾四级阶梯**判断在第几级 —— 低于 3 级基本是平淡剧。
3. **看爽点类型**：属于优势/金手指、归属、还是秩序型？金手指是否新颖、**是否有约束**（没边界就是无敌外挂）。

给出结论时要直说：**适合改 / 需要大改 / 不适合改**，以及理由。不要含糊其辞地说「可以试试」。

### 门禁二：故事骨架十二项审查

骨架出来后，逐条对：

- 压缩比 ≤ 40%？
- 每集有集末钩子？抽 3 集看
- 章节号能在事件表里找到？对不上就是编造
- 大三角（主线冲突）贯穿始终？
- 核心矛盾在第几级？低于 3 级打回
- 金手指有约束吗？
- 人物小传 ≤ 4 人？
- 反派动机合理？「纯嫉妒」打回
- 五个付费卡点按 N×10 / 30 / 50 / 70 / 90% 落位？**卡在主线上？**
- 前 10 集能剪出约 10 个 30 秒爆点？
- 结局是爽剧收尾？
- 每集字数与时长匹配（2 分钟一集，剧本约 1200～1800 字）？

### 门禁三：分镜表铁律

分镜是最容易「看起来没问题、出片全是坑」的一步。重点查这六条：

| 铁律 | 违反的表现 |
|---|---|
| **台词零删改** | 台词被精简、合并、省略修饰词 |
| **在场人物不能消失** | 剧本没写「离开」，人却在分镜里没了 |
| **人物外观交给图片资产** | 分镜提示词里出现服装 / 发型 / 长相（会和角色图打架） |
| **声音只写环境音 + 音效** | 出现 BGM、配乐、音乐（BGM 是第 8 道工序的事） |
| **长台词超 20 字强制拆镜** | 长台词挤在一个固定镜头里 |
| **单片段 ≤ 15 秒** | 有超长片段（生成类接口按时长计费，也吃不下超长） |

另外专门查**片段间过渡**有没有做 —— 这是分镜质量的分水岭。
四类桥梁：**动作衔接、情绪衔接、空间与视线衔接、台词与动作的黏合**。
每个片段至少要挂上其中一类，否则成片会「一跳一跳」。

---

## 三、三分钟跑通：从小说到第一集

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，在控制台创建一个 API Key（形如 `sk-...`），
填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：先算钱，再动手

```bash
python3 scripts/cost_estimate.py --episodes 30 --minutes 2
```

### 第三步：策划与编剧（模型网关）

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-V4-Pro",
    "messages": [{
      "role": "user",
      "content": "你是短剧策划。下面是一本小说的前三章梗概。请输出：1) 改编可行性结论（适合改/需要大改/不适合改）与理由；2) 核心矛盾（主角强欲望 + 强阻碍）；3) 按矛盾四级阶梯打分（1-4 级）；4) 建议的金手指与它的约束。只输出结论，不要客套。\n\n【小说梗概】……"
    }]
  }'
```

**换模型就是换 `model` 字符串**，不用换 Key、不用换地址、账单还是同一份。
国产线推荐 `DeepSeek-V4-Pro`、`Qwen3.7-Max`、`GLM-5.2`、`Kimi-K2.6`。

### 第四步：出图（角色与首帧）

```bash
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"generate","prompt":"短剧女主形象定妆照：25 岁都市女性，短发，浅灰西装，正面半身，纯白背景，写实风格，光线柔和","model":"nano-banana","resolution":"1K","aspect_ratio":"9:16"}' \
  --out 角色-女主.png
```

图生图（锁住同一个角色的长相）用 `"action":"edit"` + `"image_urls":["上一张角色图的 URL"]`。

### 第五步：出片（单个片段）

```bash
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"type":"text","text":"镜头缓缓推近，女主站在落地窗前，转身看向镜头，表情从疲惫转为坚定"}],"ratio":"9:16","resolution":"1080P","duration":5}' \
  --out 片段-01.mp4
```

> 片段时长只能是 **4～15 秒整数**，`content` 必须含一项文本。
> 首尾帧模式与参考媒体模式**不能混用**。

### 第六步：配音与口型

```bash
# 6.1 先克隆角色音色（一次即可，之后反复用）
python3 scripts/a7w.py call voice_tts clone_voice \
  --body '{"title":"女主-清冷","audio_url":"https://你的存储/参考音色.mp3"}'

# 6.2 台词合成（长台词走异步）
python3 scripts/a7w.py call voice_tts tts_async \
  --body '{"text":"我等这一天，等了整整十年。","reference_id":"<上一步返回的 model_id>"}' \
  --out 台词-01.mp3

# 6.3 让画面里的角色对上口型
python3 scripts/a7w.py call lipsync submit \
  --body '{"video_url":"https://你的存储/片段-01.mp4","audio_url":"https://你的存储/台词-01.mp3"}' \
  --out 片段-01-对口型.mp4
```

### 第七步：BGM、音效、超分

```bash
# BGM（按风格生成一首）
python3 scripts/a7w.py call music_generation create \
  --body '{"type":"generate","prompt":"都市悬疑短剧背景音乐，低音弦乐铺底，克制、紧张感渐强，无人声","instrumental":true}' \
  --out bgm.mp3

# 现成配乐也可以搜
python3 scripts/a7w.py call music_search search --body '{"keyword":"悬疑 紧张","page_size":10}'

# 给片段配音效
python3 scripts/a7w.py call mmaudio submit \
  --body '{"video_url":"https://你的存储/片段-01.mp4","prompt":"办公室环境音，空调低鸣，远处键盘声"}'

# 成片超分
python3 scripts/a7w.py call flashvsr submit \
  --body '{"input_url":"https://你的存储/成片.mp4"}'
```

### 第八步：本地合成

各片段、配音、BGM 都拿到之后，用本地 ffmpeg 按分镜表的时间轴拼接、混音、压字幕。
**合成放本地做**：便宜、可反复修改，不用重复扣点。

---

## 四、包里有什么

```
sanjianke-drama-factory/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 产线手册.md              八道工序的衔接、每步的输入输出与验收标准
│   ├── 质量门禁.md              改编可行性、骨架十二项、分镜铁律与过渡桥梁
│   ├── 接口速查.md              全部用到的应用与接口参数表
│   ├── 成本与排产.md            成本结构、批量排产、并发与断点续跑
│   ├── getting-started.md      注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、错误码、计费口径
└── scripts/
    ├── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
    └── cost_estimate.py        出片成本测算（零依赖，不联网）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 先算钱
python3 scripts/cost_estimate.py --episodes 30 --minutes 2

# 看某个应用有哪些接口与参数
python3 scripts/a7w.py schema nano_banana
python3 scripts/a7w.py schema voice_tts

# 调用（异步接口自动轮询到结束，--out 直接落盘）
python3 scripts/a7w.py call nano_banana submit --body '{...}' --out 角色.png
python3 scripts/a7w.py call full_video submit --body '{...}' --out 片段.mp4
```

---

## 五、素材要求

| 素材 | 要求 |
|---|---|
| 原著文本 | 直接贴进模型网关的 `messages`；超长就按章切分，分批分析 |
| 参考图（锁角色） | 公网可访问 URL；角色图越一致，后面越不会「换脸」 |
| 参考音色 | 公网可访问 URL，支持 mp3 / wav / ogg / flac；干净单人声效果最好 |
| 视频 / 音频素材 | 一律**公网可访问的 URL**，不支持本地路径、不支持 Base64 |
| 本地文件 | **先传到对象存储拿到公网直链**，再来调 |

---

## 六、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿本地路径当入参** | 报参数错误 | 一律用**公网可访问的 URL** |
| **应用代号写成连字符** | 404 | 应用代码用**下划线**：`nano_banana`、`voice_tts`、`happy_horse` |
| **用平台的 `endpoint_path` 拼 URL** | 打不通 | 一律用 `/api/v1/apps/<应用代号>/<接口代号>` |
| **分镜里写了服装 / 长相** | 角色每镜都在变脸 | 人物外观交给图片资产，分镜只写动作与运镜 |
| **分镜里写了 BGM** | 声音和音乐对不上 | 声音只写环境音与音效；BGM 单独走第 8 道工序 |
| **单片段超过 15 秒** | 提交被拒或生成不完整 | 长台词拆镜，单片段 4～15 秒 |
| **首尾帧与参考媒体混用** | 提交失败 | 两种模式分开用，一次只走一种 |
| **重复提交** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认状态 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**；模型网关看有没有 `choices` |

---

## 七、批量排产

一部剧 30 集、每集 15 个片段，就是 450 次视频生成 —— **排产比调参重要得多**。

| 原则 | 做法 |
|---|---|
| **先跑通一条** | 用单个片段跑通全链路（图 → 视频 → 配音 → 口型 → 混音），再放大批量 |
| **先图后视频** | 所有角色图、首帧图**先全部出完并人工过一遍**，再开始出视频 |
| **控制并发** | 视频生成从 **2～4 路**起步；`429` 说明排队上限到了，降并发 |
| **断点续跑** | 每个任务把 `task_id`、素材 URL、状态写进一张任务表（CSV / SQLite），重跑只补失败的 |
| **分批验收** | 每集出完立刻抽查：口型对得上、画幅正确、音量不炸 |

`references/成本与排产.md` 里给了任务表结构与批量脚本写法。
需要更贴合你流程的排产方案，加微信聊。

---

## 八、成本

**成本结构（2 分钟一集约 15 个片段，含 30% 废片率）：**

| 项目 | 占比 | 说明 |
|---|---|---|
| **视频生成** | **约 78%** | 按分辨率 × 秒数计费，是全流程的绝对大头 |
| **图片生成** | **约 15%** | `nano_banana` 24 点/张；一集约 24 张（首帧 + 角色图） |
| 口型 / 数字人 | 约 3% | 按驱动音频秒数计费 |
| 配音 | 约 2% | `voice_tts` 输入 50 点/千 Token |
| BGM | 约 1.5% | `music_generation/create` 65 点/首，一集用一首甚至复用 |

> **省钱按优先级做两件事：**
> 1. **减少要生成的视频秒数** —— 减镜头、复用镜头、拉长单镜头、
>    把静态对话改成「图片 + 口型」。视频占总额近八成，砍这里最有效。
> 2. **复用图片资产** —— 同一张角色图反复做首帧，别每个镜头重出一遍。
>    图片占约 15%，复用能直接省掉这部分的大半。

```bash
# 快速估算
python3 scripts/cost_estimate.py --episodes 30 --minutes 2
python3 scripts/cost_estimate.py --minutes 2 --video-points-per-sec 20 --waste 0.4
python3 scripts/cost_estimate.py --episodes 30 --minutes 2 --json
```

> 脚本里的单价是**参考默认值**，不是报价。请把当期真实单价传进来再采信结论。

1 元 = 100 点。平台同时给出标准价与租户实际结算价，**以你账号里实际扣费为准**。

---

## 九、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的模型网关与生成应用（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载产物 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代版权审查**：改编他人作品需要授权，请在开拍前确认权利归属
- **不替代内容合规审查**：生成内容的标识与合规责任由使用者承担
- **不保证成片质量**：方法论提高稳定性，成片效果取决于所用模型、原著质量与执行

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
