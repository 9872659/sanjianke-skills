---
name: sanjianke-stem-split
slug: sanjianke-stem-split
displayName: 歌曲伴奏人声分离·一键提取鼓点贝斯四轨拆解在线工具
description: "把一首歌拆成人声、鼓、贝斯、伴奏四条独立音轨——上传音频链接，约 1 分钟拿到可下载的分轨文件。做剪辑要干净伴奏、做二创要单人声、做混音要单独鼓轨，一条接口全解决。单次 0.65 元，无需自己部署模型或买显卡。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ，新用户送点数）。遇到问题加技术微信 9872659。"
version: 2.0.0
summary: "把一首歌在线上拆成人声、鼓、贝斯、伴奏四条独立音轨，也可只分离人声与伴奏两轨。上传音频链接即得可下载的分轨文件，单次 0.65 元，不需要自己部署模型、不需要显卡、不需要懂音频工程。覆盖卡拉 OK 伴奏提取、短视频二创单人声、混音分轨素材、播客人声净化、影视对白提取等场景。含完整参数表、真实计费口径、批量分轨思路与排错指南。作者亲测实操后发布，下载即可使用，自用商用均可。运行需自备 api.a7w.cn 的 API Key（注册领 Key 见 https://api.a7w.cn/ ）。遇到问题加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 音频处理
  - 人声分离
  - 分轨
---

# 歌曲伴奏人声分离 · 四轨拆解

> ## ⚠️ 先申请你自己的 API Key
>
> **本 Skill 不内嵌任何密钥，也不代付费用。** 请到
> **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册并创建**你自己的** API Key
> （新用户有赠送点数，可以先免费试跑几条）。
>
> 拿到后填进环境变量 `A7W_API_KEY`，或直接传给 `--key` 参数。
> **请勿使用他人提供的 Key** —— 用量与费用都记在 Key 所属账号上。

一首歌里人声、鼓、贝斯、伴奏混在一起。你想要把它们拆开 —— 做剪辑要干净的伴奏，
做二创要单拿人声，做混音要单独的鼓轨。

**上传一个音频链接，约 1 分钟拿到几条可下载的独立音轨。** 不用装环境、不用买显卡、
不用懂音频工程。

| 你最关心 | 答案 |
|---|---|
| 多少钱 | **0.65 元一次**（65 点，1 元 = 100 点），拆两轨还是四轨都是这个价 |
| 要多久 | 异步任务，通常 1 分钟内；查询免费，可以放心轮询 |
| 要装什么 | **什么都不用装**。包里自带零依赖客户端，或者直接用 `curl` |
| 能拿几轨 | **两轨**（人声 / 伴奏）或**四轨**（人声 / 鼓 / 贝斯 / 其他） |
| 能商用吗 | 可以。生成内容的使用与合规责任由使用者承担 |

---

## 一、两种拆法，按需选

| 你想要的 | 用哪个 | 结果 |
|---|---|---|
| **只要伴奏**（卡拉 OK、翻唱底带） | `stems` | 人声 + 伴奏 两条 |
| **只要人声**（二创、混音取材） | `stems` | 同上，取人声那条即可 |
| **要完整四轨**（鼓 / 贝斯 / 人声 / 其他） | `all_stems` | 四条独立音轨 |

**价格一样，都是 0.65 元。** 所以要做混音就直接上四轨，别省。

---

## 二、三分钟跑通

### 第一步：拿到你自己的 Key

到 **[api.a7w.cn](https://api.a7w.cn/)** 注册，在控制台创建一个 API Key（形如 `sk-...`），
填进环境变量：

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
```

### 第二步：把音频换成 ID

先用 `upload_audio` 把你的**公网音频链接**换成一个音频 ID：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/music_generation/upload_audio" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"audio_url":"https://你的存储/我的歌.mp3"}'
```

### 第三步：提交分轨任务

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/music_generation/create" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"all_stems","audio_id":"<上一步拿到的 audio_id>"}'
```

返回里带一个 `task_id`，记下来。

### 第四步：查结果（免费）

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/music_generation/query" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_id":"<上一步的 task_id>"}'
```

结果里是本条任务产出的各轨音频链接，直接下载即可。

---

## 三、包里有什么

```
sanjianke-demucs/
├── SKILL.md                    本文件
├── README.md
├── LICENSE.md
├── references/
│   ├── 分轨指南.md              两种拆法怎么选、素材要求、批量分轨思路
│   ├── api-create.md           create 接口完整参数（stems / all_stems）
│   ├── api-upload-query.md     upload_audio 与 query 的参数与返回
│   ├── getting-started.md      注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

### 零安装用法

```bash
export A7W_API_KEY=sk-你的key

# 看这个插件有哪些接口与参数
python3 scripts/a7w.py schema music_generation

# 上传音频 → 拿 audio_id
python3 scripts/a7w.py call music_generation upload_audio \
  --body '{"audio_url":"https://你的存储/我的歌.mp3"}'

# 四轨分离（客户端会自动轮询到结束）
python3 scripts/a7w.py call music_generation create \
  --body '{"type":"all_stems","audio_id":"<audio_id>"}'
```

---

## 四、素材要求

| 要求 | 说明 |
|---|---|
| 格式 | MP3 / WAV 等常见音频格式 |
| 访问 | **必须是公网可访问的 URL**，不支持本地路径、不支持 Base64 |
| 内容 | 音乐（人声 + 伴奏的混音）。**纯人声或纯伴奏**的素材没必要拆 |
| 长度 | 没有硬限制；整轨一次拆更省事 |

> 本地文件先传到对象存储 / 图床拿到公网链接，再走 `upload_audio`。

---

## 五、常见坑

| 坑 | 表现 | 怎么避 |
|---|---|---|
| **拿本地路径当入参** | 报参数错误 | 一律用**公网可访问的 URL** |
| **忘了先 upload_audio** | 没有 `audio_id` 可用 | 有链接就先换 ID；平台上已有音频 ID 的可跳过 |
| **重复提交** | 扣两次钱 | 先记 `task_id`，用 `query`（免费）确认状态 |
| **拿播客 / 会议录音来拆** | 结果不理想 | 这个能力是为**音乐混音**设计的（鼓/贝斯/人声/其他），语音类素材不适合 |
| **想拆钢琴等具体乐器** | 只会归到「其他」 | 四轨是固定的，不细分具体乐器 |
| **拿 `code == 0` 判断成功** | 明明成功却判成失败 | 平台成功码是 **`1`**（`{"code":1,"msg":"success"}`） |

---

## 六、批量分轨

做矩阵号、批量二创时一次拆几十首很常见。思路是：**先批量 `upload_audio` 拿 ID，
再逐个 `create`**，并控制异步任务的并发，别一次全发出去。

`references/分轨指南.md` 里给了批量脚本的写法和并发建议。
需要更贴合你流程的批量方案，加微信聊。

---

## 七、计费

| 动作 | 点数 | 折合 |
|---|---|---|
| `upload_audio` 换 ID | 13 | 0.13 元 |
| **`create` 分轨（两轨或四轨）** | **65** | **0.65 元** |
| `query` 查任务 | **免费** | — |

1 元 = 100 点。**按点数计费，用多少扣多少，没有月费。**

> 平台同时给出标准价与租户实际结算价，**以账号里实际扣费为准**。
> 每次返回的 `data.usage.points_cost` 就是本次真实扣费。

---

## 八、权限与边界

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **申请** | 调用 `api.a7w.cn` 的音频接口（本 Skill 唯一的联网行为） |
| 读取文件 | 仅读取你指定的输入文件 | 用作素材入参 |
| 写入文件 | 仅在传入 `--out` 时 | 保存返回的 JSON 或下载分轨 |
| 凭证 | 读取**你自己**提供的 API Key | 从环境变量或 `~/.a7w/config.json` 读取 |

**不内嵌任何密钥。** 请求只发往 `api.a7w.cn`，不发送到其他任何地址。

- **不提供 Key、不代付费用**：Key 必须你自己在 api.a7w.cn 申请
- **不替代版权审查**：分轨别人的歌用于二创 / 商用前，请自行确认授权

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
