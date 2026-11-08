---
name: sanjianke-news-shorts
slug: sanjianke-news-shorts
displayName: 新闻资讯短视频 一条快讯 1.80 元
description: "**一条快讯 1.80 元、一条深度 13.95 元，一天 8 条快讯加 2 条深度 42.80 元**：标题 3 秒抓人 → 事件 → 背景 → 影响 → 来源，五段时间码先排好，播报稿、字幕 SRT、3 条标题、平台描述、6 个标签、配图 prompt、文件命名与交付单一次生成，全在本地、0 点。按秒与按字花钱：新闻体混剪 4.5 点/秒（一条 30 秒 135 点），补镜头 1080P 60 点/秒，出图 6 点/张，播报约 0.18 点/字，配乐 50 点起；查进度只走 GET /api/v1/tasks/<id>（0 点），素材先 POST /api/v1/upload（免费）换白名单地址。合规四项做成了默认动作：来源标注、事实口径、AI 生成标注、平台时长。`plan` 与 `qc` 纯本地 0 点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "一个媒体号一天要交什么。**一条快讯 1.80 元**（30 秒竖屏 1080x1920）：混剪 135 点、播报 27 点（150 字）、配图 18 点（3 张）；**一条深度 13.95 元**（90 秒横屏）：混剪 405 点、补镜头 900 点、播报 54 点、配图 36 点；一天 8 快讯 + 2 深度 + 1 首配乐 = **4,280 点 = 42.80 元**。**价目**（1 元=100 点）：smart_clip/* 4.5 点/秒；full_video 480P 14 / 1080P 60 点/秒；出图 6 点/张；voice_tts 上游 x 3、0.18 点/字；配乐保底 50 点；采集 100 点/次。**流程**：plan 本地出五段结构 / 播报稿 / SRT / 文案 / 配图 / 交付单；qc 本地过十二道检查；hunt / cover / voice / music / film / mix 逐项花钱。**三条规矩**：轮询只走 GET /tasks；目录只看 /apps 与 /pricing；素材先 upload 换白名单地址。**闸门**：缺 --yes 退 4，超 --budget 退 5 且一个请求都不发。需要自备 api.a7w.cn 的 Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 新闻资讯
  - 资讯短视频
  - api.a7w.cn
---

# 新闻资讯短视频 一条快讯 1.80 元

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

**一条快讯 1.80 元，把一件事讲完。** 前 3 秒一句标题把人钉住，接着交代事件，补背景，说影响，最后落到来源。稿子、字幕、标题、标签、配图提示词、文件名和交付单先在本地排好，再决定哪几条值得花钱。

## 这个包和底层能力包的分工

| 你手上要的东西 | 用哪个包 | 它交付什么 |
|---|---|---|
| 抖快小红书上的热点素材参考 | `sanjianke-ecom-spy` | 采集接口、参数表与排序口径 |
| 一张资讯配图 / 封面 | `sanjianke-gpt-image` | 6 点一张，文生图 / 图生图 / GIF |
| 一段 4~15 秒的镜头 | `a7w-full-video` | 首帧 + 运镜，按秒 x 分辨率计费 |
| 一条播报 | `a7w-voice-tts` | 同步 tts / 长文 tts_async / 克隆音色 |
| 新闻体混剪本体 | `a7w-smart-clip` | news_mixcut 的全部参数与图层结构 |
| 一首配乐 | `a7w-music-generation` | Suno 线接口与参数表 |
| **一个媒体号一天要交的 10 条片 + 30 张图 + 播报 + 字幕 + 文案 + 交付单** | **本包** | 五段结构、新闻体话术、字幕规范、合规检查、成本单 |

底层包做单步，本包做「一单要交的东西」：先把结构、播报、字幕、来源排好，再决定哪几条值得花钱。

## 交付清单（一天 / 一单）

| # | 交付物 | 规格 | 一天数量 | 命名 |
|---|---|---|---|---|
| 1 | 快讯成片 | 1080x1920 / H.264 / 25fps / 30 秒 / 9:16 | 8 | `20261108_市地铁集团_快讯_douyin_30s.mp4` |
| 2 | 深度成片 | 1920x1080 / H.264 / 25fps / 90 秒 / 16:9 | 2 | `20261108_市地铁集团_深度_bilibili_90s.mp4` |
| 3 | 封面图 | 1080x1920 png（快讯）/ 1536x1024 png（深度） | 10 | `*_cover.png` |
| 4 | 配图 | 快讯 3 张 / 深度 6 张，1024x1536 或 1536x1024 png | 30 | `*_scene.png` `*_chart.png` |
| 5 | 播报音频 + 字幕 | mp3 / 44.1kHz / 单条 500 字内；SRT 一行 ≤ 16 字 | 10 | `*_voice.mp3` `*_30s.srt` |
| 6 | 文案包 | 标题 3 条 + 描述 1 条 + 标签 6 个 + 来源行 | 10 | `*_文案.md` |
| 7 | 交付单 + 配乐 | 结构 / 配图 prompt / 成本 / 合规 / 命名；30 秒循环 | 各 1 | `*_交付单.md` `bgm.mp3` |

命名规则：`日期_主体_模板_平台_秒数`，一单一目录，`plan` 直接写进交付单。

## 新闻体五段结构

| 快讯 30 秒 | 深度 90 秒 | 段 | 画面 | 播报干什么 |
|---|---|---|---|---|
| 0-3 秒 | 0-3 秒 | 标题 | 主体标识 / 现场空镜，大字标题压下三分之一 | 一句标题念完，尾字收干净 |
| 3-11 秒 | 3-18 秒 | 事件 | 事发地点、相关人群、可核对画面 | 时间 + 地点 + 主体 + 动作 + 数字 |
| 11-19 秒 | 18-40 秒 | 背景 | 旧画面、数据板、通报截图 | 此前的口径与本次的差别 |
| 19-26 秒 | 40-70 秒 | 影响 | 受影响人群、路口、站台、办事窗口 | 谁受影响、什么时候开始执行 |
| 26-30 秒 | 70-90 秒 | 来源 | 来源字幕板 + 通报时间 + AI 标注 | 来源单位念全，收一句「以官方最新通报为准」 |

秒数按权重分配（快讯 3/8/8/7/4，深度 3/15/22/30/20），`--seconds` 改总时长，五段等比缩放。

## 播报语速与字幕规范

- **快讯 4.4~5.8 字/秒**（30 秒配 150 字）；**深度 2.9~4.2 字/秒**（90 秒配 300 字）。`qc` 按这两个窗口校验。
- 数字前后各留一个空格：「多运 1.2 万人次」「末班车 23:30」，TTS 断句更稳；段间停 0.4 秒，片尾定格 1 秒。
- 字幕一行 ≤ 16 字、一条 ≤ 32 字、两行封顶，位置在画面下三分之一、距底边 12%，`plan` 生成的 SRT 已按此切好。
- 来源字幕常驻最后 3 秒，与口播收尾句同步；人名、机构名首次出现给全称。

## 价目表与一单的钱（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 采集参考 | `POST /api/v1/apps/watermark_removal/douyin_search_video` · `xhs_search_note` | **100 点/次**（flat，失败亦计） |
| 配图 | `POST /api/v1/images/generations` | **6 点/张**（尺寸与格式同价） |
| 播报 | `POST /api/v1/apps/voice_tts/tts` | 约 **0.18 点/字** |
| 配乐 | `POST /api/v1/apps/media_services_33/music_generate` | **50 点起/首** |
| 补镜头 | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒 |
| 混剪 | `POST /api/v1/apps/smart_clip/news_mixcut` | **4.5 点/秒**（无 duration 时预冻结 45 点） |
| 免费四项 | `GET /tasks/<id>` · `POST /upload` · `plan` · `qc` | **0 点** |

一条快讯 30 秒：混剪 135 + 播报 27（150 字）+ 配图 18（3 张）= **180 点 = 1.80 元**。
一条深度 90 秒：混剪 405 + 补镜头 900（15 秒 1080P）+ 播报 54 + 配图 36 = **1,395 点 = 13.95 元**。
一天 8 条快讯（1,440）+ 2 条深度（2,790）+ 1 首配乐（50）= **4,280 点 = 42.80 元**。深度换 480P，一单降到 715.8 点（7.16 元）。

## 三条干货（别人不写进文档的）

1. **读比写贵，轮询只走通用查询。** 应用层 `/query` 每查一次按该应用单价结算，`nano_banana/query` 实测 72 点/次；本包只打 `GET /api/v1/tasks/<id>`，价目表里这条是 cost:0。`GET /api/v1/apps/<app>` 会命中 `/apps/<app>/*` 通配计价、即时扣费不退（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔），要目录只看 `/api/v1/apps` 与 `/api/v1/pricing`。
2. **混剪按秒、采集按次，两笔最容易被忽略。** 30 秒混剪 135 点，比 3 张配图贵 7 倍；采集一次 100 点、与返回条数无关，换个关键词就是新的一次，先想好词再发。深度片的补镜头 900 点占一单 65%，先用 480P 试结构，定稿再上 1080P。
3. **素材有域名白名单。** 外站地址一律 400 `url_not_allowed`，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。`film --image 本地图.png` 与 `mix --material 本地素材.png` 都会先 `POST /api/v1/upload`（免费）换地址。

## 三步上手

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"
# 2) 免费：自检 + 算钱 + 出一单的播报稿 / 字幕 / 文案 / 交付单 + 合规检查
python3 scripts/run.py doctor
python3 scripts/run.py cost --flash 8 --depth 2
python3 scripts/run.py plan --topic "地铁 3 号线今起延长运营" --when "今天起" \
    --where 杭州 --subject 市地铁集团 --event "把末班车延到 23:30" \
    --figure "日均多运 1.2 万人次" --source "市地铁集团通报" --template flash
python3 scripts/run.py qc --plan ~/.a7w/news-shorts/flash-20261108/plan.json
# 3) 按交付单花钱（每步都能单跑、能续跑）
python3 scripts/run.py hunt  --platform dy --keyword "地铁 延长运营" --yes
python3 scripts/run.py cover --template flash --topic "地铁延长运营" --yes
python3 scripts/run.py voice --script ~/.a7w/news-shorts/flash-20261108/播报稿.md --yes
python3 scripts/run.py mix   --title "地铁 3 号线延长运营" --material cover.png --yes
python3 scripts/run.py status --task-id tsk_xxx
```

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 六道工序 + 端点 + 单价 + 两套模板 + 平台尺寸 |
| `cost --flash 8 --depth 2` | 免费 | 一天要多少钱，按五档分辨率列出来 |
| `plan --template depth` | 免费 | 深度五段结构，一次出播报稿 / SRT / 文案 / 交付单 |
| `qc --plan plan.json` | 免费 | 十二道检查：来源 / 三要素 / 数字 / AI 标注 / 语速 / 时长 / 标题 / 字幕 / 三组词表 |
| `hunt --platform dy` | **100 点 = 1.00 元** | 采集热点参考，一次一页 |
| `cover --template flash` | **18 点 = 0.18 元** | 快讯 3 张配图一次出齐 |
| `voice --script 播报稿.md` | **约 0.18 点/字** | 播报，500 字内一条 |
| `music --mood depth` | **50 点起** | 30 秒循环配乐 |
| `film --seconds 15` | **900 点 = 9.00 元** | 补 1 段镜头，首帧图自动 upload |
| `mix --material a.png` | **4.5 点/秒** | 新闻体混剪，素材自动 upload |
| `status` / `log` | 免费 | 查进度（反复查都是 0 点）/ 本地台账 |

## 合规检查（`qc` 已经做成默认动作）

- **来源标注**：口播念发布主体，画面挂来源字幕板，描述写「来源：XX 通报」，三处一句一致。
- **事实口径**：数字带单位与时间，通报原文照抄，收尾统一「以官方最新通报为准」。
- **AI 生成标注**：片尾字幕板写「AI 辅助生成」，混剪提交时 `watermarkShow=true` 加画面标识与 `metadata.AIGC`。
- **传闻与猜测用正向替代**：「据说 / 网传 / 疑似」换成发布主体与时间，例如「据市地铁集团通报」。
- **标题三秒**：三条标题都在 20 字内，主体 + 动作在前、数字在后，`qc` 逐条量过。
- **平台时长**：快讯 60 秒、深度 180 秒、B 站 480 秒，`qc` 按 `--platform` 校验。

## 参数与退出码

| 参数 | 默认 | 说明 |
|---|---|---|
| `--template` / `--platform` | flash / douyin | flash 快讯 30 秒竖屏、depth 深度 90 秒横屏；douyin / kuaishou / xhs / channels / bilibili |
| `--topic` / `--source` | 示例 / 待填 | 标题主体；来源单位（`qc` 会查它有没有出现在口播与描述里） |
| `--when` / `--where` / `--subject` | 今天上午 / 本市 / 相关部门 | 事件三要素 |
| `--event` / `--figure` / `--quote` | 发布最新通报 / 空 / 空 | 动作、关键数字、官方原话 |
| `--ai-label` / `--seconds` | AI 辅助生成 / 模板默认 | 片尾与描述的标注文案；总秒数 |
| `--budget` | 6000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

退出码：`0` 成功 / `2` 用法错 / `3` 自检或合规没过 / `4` 缺 `--yes` / `5` 超预算且一个请求都没发 / `6` 调用失败 / `1` 内部错 / `130` 中断。`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档；`--json` 写在子命令前后都可以。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
