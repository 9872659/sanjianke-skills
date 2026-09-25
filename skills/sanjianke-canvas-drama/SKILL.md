---
name: sanjianke-canvas-drama
slug: sanjianke-canvas-drama
displayName: AI短剧创作画布·智能分镜图像视频生成一站式出片工作流
description: "把一部短剧从想法做到能发：无限画布式排布分镜、AI Agent 拆解剧本、逐镜生成图像与视频、配音配乐、导出成片——全流程一套工作流。图像、视频、语音、音乐全部走 api.a7w.cn，一把 Key 打通，不用自己部署模型。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "一套跑得通的 AI 短剧创作工作流：用无限画布排布分镜、用 AI Agent 拆解剧本与人物小传、逐镜生成图像与视频、配音配乐、最后导出成片。覆盖剧本结构拆解、人物一致性控制、分镜表写法、镜头语言与运镜提示词、首尾帧衔接、对口型与数字人口播、字幕与配乐合成等完整链路。所有 AI 能力走 api.a7w.cn——图像、视频、语音、音乐一个 Key 全包，不用自己部署模型、不用买显卡。适用于短剧批量出片、小说改编、广告分镜、漫画分镜转视频、口播矩阵号、课程视频制作等场景。含分镜模板、提示词范式、成本估算与排错清单。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 短剧
  - 分镜
  - 视频生成
---

# AI 短剧创作画布 · 从剧本到成片

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

**想法 → 剧本 → 分镜 → 出图 → 出片 → 配音 → 成片。** 一条流水线走完，
不用在五六个工具之间倒腾文件。

画布上排好每一镜，Agent 帮你拆剧本、写提示词、检查上下文连贯；
图像、视频、语音、音乐全部由 **api.a7w.cn** 一把 Key 驱动。

| 你最关心 | 答案 |
|---|---|
| 要不要自己部署 | **不用**。包里自带零依赖客户端，配好 Key 就能跑 |
| 要花多少钱 | 按点数计费，用多少扣多少，**没有月费** |
| 能出多长 | 单镜 5~10 秒，按分镜拼接；一集 2 分钟约 20~30 镜 |
| 人物会变形吗 | 用「人物定妆图 + 首尾帧衔接」控制，文档给了具体做法 |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、七步流水线

| 步 | 做什么 | 走哪个能力 |
|---|---|---|
| 1 | **拆剧本**：分场、人物小传、情绪曲线 | 模型网关 `chat/completions` |
| 2 | **写分镜表**：镜号、景别、运镜、时长、台词 | 模型网关 |
| 3 | **定人物**：主角定妆图，锁定形象 | `nano_banana` 文生图 |
| 4 | **出关键帧**：每镜首帧（必要时加尾帧） | `nano_banana` 图生图 |
| 5 | **生成视频**：首尾帧驱动，得到镜头素材 | `full_video` / `happy_horse` / `seedance` / `wan` |
| 6 | **配音配乐**：台词配音、音色克隆、背景音乐 | `voice_tts` / `music_generation` / `mmaudio` |
| 7 | **合成成片**：拼接、字幕、混音、必要处超分 | 本地 ffmpeg + `flashvsr` |

> 画布上的排布顺序就是第 2 步产出的分镜表 —— 镜号即节点编号，
> 改哪一镜就只重跑那一个节点，不用整片重来。

---

## 二、三分钟跑通（最小闭环）

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，创建一个 API Key（形如 `sk-...`）：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：让模型拆剧本、出分镜表

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<先用 GET /api/v1/models 查到可用模型名>",
    "messages": [{"role":"user","content":"把下面这段剧情拆成 12 个分镜，每镜给：镜号、景别、运镜、时长、画面描述、台词。<剧情略>"}]
  }'
```

> **模型名不要猜。** 先 `GET https://api.a7w.cn/api/v1/models` 拿在架模型清单再填。
> 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`），HTTP 200 不代表业务成功。

### 第三步：定人物 + 出关键帧

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/nano_banana/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"25 岁女性，短发，米色风衣，正面半身像，影棚均匀布光，中性背景，写实风格"}'
# → 拿 task_id，再 POST /api/v1/apps/nano_banana/query 取图
```

**第一张定妆图存好当参考图**，后面每一镜都用它做图生图，人物才不跑形。

### 第四步：首尾帧 → 视频

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/full_video/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content":[{"role":"first_frame","type":"image_url","image_url":{"url":"<本镜首帧图 URL>"}},{"type":"text","text":"缓慢推近，人物转头看向窗外"}],"ratio":"9:16","resolution":"720P","duration":6}'
```

> `content` 数组里**必须有一项 `text`**；`duration` 只吃 **4~15 秒的整数**。

### 第五步：配音 → 合成

```bash
# 台词配音（音色克隆见 references/配音与配乐.md）
# 注意参数名是 reference_id，值是 clone_voice 返回的 model_id
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/voice_tts/tts" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"<本镜台词>","reference_id":"<音色 ID>"}'
```

最后用本地 ffmpeg 把镜头、配音、字幕、BGM 合成 —— 命令在
`references/合成与导出.md` 里，逐条可复制。

---

## 三、包里有什么

```
sanjianke-canvas-drama/
├── SKILL.md                    本文件：七步流水线 + 最小闭环
├── README.md
├── LICENSE.md
├── references/
│   ├── 分镜方法.md              分镜表模板、景别与运镜词表、上下文连贯校验
│   ├── 人物一致性.md            定妆图 → 参考图 → 首尾帧的三层锁定
│   ├── 提示词范式.md            图像 / 视频提示词结构与正反例
│   ├── 配音与配乐.md            音色克隆、分段配音、BGM 与音效
│   ├── 合成与导出.md            ffmpeg 拼接、字幕、混音、超分
│   ├── 成本估算.md              各环节点数、一集预算、省钱顺序
│   ├── api-模型网关.md          OpenAI 兼容入口、鉴权、错误码
│   ├── api-生成应用.md          图像 / 视频 / 语音应用接口速查
│   ├── getting-started.md       注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 看有哪些模型 / 哪些应用
python3 scripts/a7w.py whoami
python3 scripts/a7w.py apps

# 看某个应用的接口与参数
python3 scripts/a7w.py schema nano_banana

# 提交应用任务（客户端自动轮询到结束）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"prompt":"25 岁女性，短发，米色风衣，正面半身像"}'
```

---

## 四、十三个常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **模型名靠猜** | 报模型不存在 | 先 `GET /api/v1/models` 查在册名单 |
| **拿 `code == 0` 判成功** | 明明成功却判失败 | 平台成功码是 **`1`** |
| **HTTP 200 就当成功** | 实际是业务错误 | 必须看响应体里的 `code` / `msg` |
| **入参给本地路径** | 报参数错误 | 图片 / 视频 / 音频一律用**公网 URL** |
| **每镜都重新描述人物** | 人物一镜一个样 | 用**同一张定妆图**做参考图，别用文字重述 |
| **首尾帧不衔接** | 镜头之间跳 | 上一镜尾帧 = 下一镜首帧 |
| **单镜拉太长** | 动作崩坏 | 单镜 5~10 秒；长动作拆成多镜 |
| **重复提交异步任务** | 扣两次钱 | 先记 `task_id`，用查询接口（免费）确认 |
| **不计成本就开跑** | 一集超预算 | 先按 `references/成本估算.md` 估一遍 |
| **字幕时间轴靠手数** | 对不上 | 配音后取时长累计生成 SRT |
| **口播镜不用数字人** | 嘴型对不上 | 真人口播走 `image_human` / `lipsync` |
| **画质不够再超分** | 时间翻倍 | 需要 2K/4K 交付时用 `flashvsr`，别的场景不必 |
| **PowerShell 里 JSON 引号被吃** | 报「请求体不是合法 JSON」 | 用 `--body` 传文件或改用 bash |

---

## 五、计费口径

**按点数计费，1 元 = 100 点。用多少扣多少，没有月费。**

| 环节 | 大致量级 |
|---|---|
| 剧本 / 分镜（模型网关） | 按 tokens，几千 tokens 几毛钱 |
| 图像（`nano_banana`） | 按档位，单张几毛 |
| 视频（`full_video` 等） | 按秒，**这是成本大头** |
| 语音（`voice_tts`） | 按字符或时长 |
| 音乐（`music_generation`） | 按次 |

- **先冻结后结算**，失败全额退回
- 查询类接口**免费**，可以放心轮询
- 每次返回的 `data.usage.points_cost` 是本次真实扣费
- 平台同时给标准价与租户实际结算价，**以实际扣费为准**

> **省钱顺序**：先砍视频秒数（占大头）→ 复用已生成的图片资产 → 再考虑配音配乐。
> 详细测算见 `references/成本估算.md`。

---

## 六、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn`（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载素材 |
| 子进程 | 本地合成需要 `ffmpeg` | 拼接、字幕、混音 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`。

- **不提供 Key、不代付费用**
- **不替代版权与内容合规审查**：剧本、素材与成片的合规责任由使用者承担
- **不替代肖像与声音授权**：用他人形象或音色前必须取得本人授权

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
