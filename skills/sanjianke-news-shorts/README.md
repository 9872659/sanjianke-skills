# 新闻资讯短视频 一条快讯 1.80 元

**一条快讯 1.80 元，一天 8 条快讯加 2 条深度 42.80 元。** 前 3 秒一句标题把人钉住，接着交代事件，补背景，说影响，最后落到来源。稿子、字幕、标题、标签、配图提示词、文件名和交付单先在本地排好，再决定哪几条值得花钱。

深度是同一套打法：把五段拉长到 90 秒，事件段给 15 秒、影响段给 30 秒，中间补一段 AI 镜头顶住画面。

---

## 一单要交什么

| # | 交付物 | 规格 | 一天数量 | 命名 |
|---|---|---|---|---|
| 1 | 快讯成片 | 1080x1920 / H.264 / 25fps / 30 秒 / 9:16 | 8 | `20261108_市地铁集团_快讯_douyin_30s.mp4` |
| 2 | 深度成片 | 1920x1080 / H.264 / 25fps / 90 秒 / 16:9 | 2 | `20261108_市地铁集团_深度_bilibili_90s.mp4` |
| 3 | 封面图 | 1080x1920 png（快讯）/ 1536x1024 png（深度） | 10 | `*_cover.png` |
| 4 | 配图 | 快讯 3 张 / 深度 6 张，1024x1536 或 1536x1024 png | 30 | `*_scene.png` `*_chart.png` |
| 5 | 播报音频 | mp3 / 44.1kHz / 单条 500 字内 | 10 | `*_voice.mp3` |
| 6 | 字幕 | SRT，一行 ≤ 16 字、一条 ≤ 32 字 | 10 | `*_30s.srt` |
| 7 | 文案包 | 标题 3 条 + 描述 1 条 + 标签 6 个 + 来源行 | 10 | `*_文案.md` |
| 8 | 交付单 | 结构 / 配图 prompt / 成本 / 合规 / 命名 | 1 份 | `*_交付单.md` |
| 9 | 配乐 | 30 秒循环，一天一条可复用 | 1 | `bgm.mp3` |

`plan` 一条命令把 1、3、4、6、7、8 里的**脚本部分**全部写好（五段分镜、播报稿、SRT、3 条标题、平台描述、6 个标签、全部配图 prompt、文件命名、成本单），落在 `~/.a7w/news-shorts/<模板>-<日期>/`，纯本地、不联网、0 点。

命名规则：`日期_主体_模板_平台_秒数`。一单一目录，交付单一页能对得上。

---

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

---

## 新闻体五段结构

| 快讯 30 秒 | 深度 90 秒 | 段 | 画面 | 播报干什么 |
|---|---|---|---|---|
| 0-3 秒 | 0-3 秒 | 标题 | 主体标识 / 现场空镜，大字标题压下三分之一 | 一句标题念完，尾字收干净 |
| 3-11 秒 | 3-18 秒 | 事件 | 事发地点、相关人群、可核对画面 | 时间 + 地点 + 主体 + 动作 + 数字 |
| 11-19 秒 | 18-40 秒 | 背景 | 旧画面、数据板、通报截图 | 此前的口径与本次的差别 |
| 19-26 秒 | 40-70 秒 | 影响 | 受影响人群、路口、站台、办事窗口 | 谁受影响、什么时候开始执行 |
| 26-30 秒 | 70-90 秒 | 来源 | 来源字幕板 + 通报时间 + AI 标注 | 来源单位念全，收一句「以官方最新通报为准」 |

秒数按权重分配（快讯 3/8/8/7/4，深度 3/15/22/30/20），`--seconds` 改总时长，五段等比缩放，脚本不用手改。

---

## 播报与字幕规范

| 项 | 快讯 | 深度 |
|---|---|---|
| 播报语速 | 4.4~5.8 字/秒（30 秒配 150 字） | 2.9~4.2 字/秒（90 秒配 300 字） |
| 段间停顿 | 0.4 秒 | 0.4 秒 + 空镜留一拍 |
| 字幕行宽 | 一行 ≤ 16 字、一条 ≤ 32 字、两行封顶 | 同左 |
| 字幕位置 | 下三分之一、距底边 12% | 同左 |
| 来源字幕 | 常驻最后 3 秒 | 常驻最后 5 秒 |

- 数字前后各留一个空格：「多运 1.2 万人次」「末班车 23:30」，TTS 断句更稳。
- 人名、机构名首次出现给全称，第二遍再简称。
- 片尾定格 1 秒留给来源字幕板，`qc` 会量每条字幕的字数。

---

## 价目表（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 采集参考 | `POST /api/v1/apps/watermark_removal/douyin_search_video` · `xhs_search_note` | **100 点/次**（flat，失败亦计） |
| 配图 | `POST /api/v1/images/generations` | **6 点/张**（尺寸与格式同价，按实际返回张数计） |
| 播报 | `POST /api/v1/apps/voice_tts/tts` | 约 **0.18 点/字**（上游真实点数 x 3） |
| 配乐 | `POST /api/v1/apps/media_services_33/music_generate` | **50 点起/首**（上游 x 2，保底 50） |
| 补镜头 | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒 |
| 混剪 | `POST /api/v1/apps/smart_clip/news_mixcut` | **4.5 点/秒**（无 duration 时预冻结 45 点） |
| 查进度 / 传素材 | `GET /api/v1/tasks/<id>` · `POST /api/v1/upload` | **0 点** |
| 脚本 / 检查 | `plan` / `qc`（纯本地） | **0 点** |

### 一单多少钱（1080P）

| 项 | 一条快讯 30 秒 | 一条深度 90 秒 |
|---|---|---|
| 混剪 4.5 点/秒 | 135 | 405 |
| 补镜头 15 秒 | 0 | 900 |
| 播报 0.18 点/字 | 27（150 字） | 54（300 字） |
| 配图 6 点/张 | 18（3 张） | 36（6 张） |
| **合计** | **180 点 = 1.80 元** | **1,395 点 = 13.95 元** |

### 一天多少钱

| 组合 | 点数 | 折合 |
|---|---|---|
| 8 条快讯 + 2 条深度 + 1 首配乐 | **4,280 点** | **42.80 元** |
| 只做 10 条快讯 + 1 首配乐 | 1,850 点 | 18.50 元 |
| 只做 3 条深度 + 1 首配乐 | 4,235 点 | 42.35 元 |

### 深度按分辨率

| 分辨率 | 一条深度 | 一天 2 条加 8 快讯 |
|---|---|---|
| 480P | 715.8 点 = 7.16 元 | 2,864 点 ≈ 28.64 元 |
| 768P | 925.8 点 = 9.26 元 | 3,284 点 ≈ 32.84 元 |
| **1080P** | **1,395 点 = 13.95 元** | **4,280 点 = 42.80 元** |
| 2K / 4K | 1,705.8 点 = 17.06 元 | 4,844 点 ≈ 48.44 元 |

`full_video` 单段 4~15 秒，`mix` 的 `videoDuration` 是 5~300 秒，两条都是按秒算。

---

## 快速开始

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 2) 免费：自检 + 算钱
python3 scripts/run.py doctor
python3 scripts/run.py cost --flash 8 --depth 2

# 3) 免费：出一单的播报稿 / 字幕 / 文案 / 交付单，再过一遍合规
python3 scripts/run.py plan --topic "地铁 3 号线今起延长运营" --when "今天起" \
    --where 杭州 --subject 市地铁集团 --event "把末班车延到 23:30" \
    --figure "日均多运 1.2 万人次" --source "市地铁集团通报" \
    --platform douyin --template flash
python3 scripts/run.py qc --plan ~/.a7w/news-shorts/flash-20261108/plan.json

# 4) 按交付单花钱
python3 scripts/run.py hunt  --platform dy --keyword "地铁 延长运营" --yes
python3 scripts/run.py cover --template flash --topic "地铁延长运营" --yes
python3 scripts/run.py voice --script ~/.a7w/news-shorts/flash-20261108/播报稿.md --yes
python3 scripts/run.py music --mood flash --yes
python3 scripts/run.py film  --text "竖屏新闻现场，站台人流" --image cover.png --yes
python3 scripts/run.py mix   --title "地铁 3 号线延长运营" --material cover.png --yes
python3 scripts/run.py status --task-id tsk_xxx
```

---

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 六道工序 + 端点 + 单价 + 两套模板 + 平台尺寸 |
| `cost --flash 8 --depth 2` | 免费 | 一天要多少钱，按五档分辨率列出来 |
| `plan --template depth` | 免费 | 深度五段结构，一次出播报稿 / SRT / 文案 / 交付单 |
| `qc --plan plan.json` | 免费 | 十二道检查 |
| `hunt --platform xhs` | **100 点 = 1.00 元** | 小红书笔记参考，一次一页 |
| `cover --kind cover` | **6 点/张** | 只出封面 |
| `voice --script 播报稿.md` | **约 0.18 点/字** | 播报，500 字内一条 |
| `music --mood depth` | **50 点起** | 专题底乐 |
| `film --seconds 15` | **900 点 = 9.00 元** | 补 1 段镜头，首帧图自动 upload |
| `mix --material a.png --seconds 30` | **135 点 = 1.35 元** | 新闻体混剪，素材自动 upload |
| `upload --file a.png` | 免费 | 换 `oss.gpu.likeadmin.cn` 白名单地址 |
| `status` / `log` | 免费 | 查进度，反复查都是 0 点 / 本地台账 |

**不加 `--yes` 退 `4`** 并告诉你这次要花多少点；**预计点数超 `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 6000 = 60 元）。

---

## 三条用钱换来的规矩

**一、读比写贵。** 应用层 `/query` 每查一次都按该应用单价结算，`nano_banana/query` 实测 72 点/次；`GET /api/v1/apps/<app>` 更狠，命中 `/apps/<app>/*` 通配计价、即时扣费不退（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔）。本包所有查询走 `GET /api/v1/tasks/<id>`，要目录只看 `/api/v1/apps` 与 `/api/v1/pricing`，两条都是 cost:0。

**二、混剪按秒、采集按次。** 30 秒混剪 135 点，比 3 张配图贵 7 倍；采集一次 100 点、与返回条数无关，换个关键词就是新的一次，先想好词再发。深度片的补镜头 900 点占一单 65%，先用 480P 把结构跑通，定稿那一条再上 1080P。

**三、素材有域名白名单。** 外站地址一律 400 `url_not_allowed`，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。`film --image 本地图.png` 与 `mix --material 本地素材.png` 都会先 `POST /api/v1/upload`（免费）换地址。

---

## 合规检查（`qc` 已经做成默认动作）

- **来源标注**：口播念发布主体，画面挂来源字幕板，描述写「来源：XX 通报」，三处一句一致。
- **事实口径**：数字带单位与时间，通报原文照抄，收尾统一「以官方最新通报为准」。
- **AI 生成标注**：片尾字幕板写「AI 辅助生成」，混剪提交时 `watermarkShow=true` 加画面标识与 `metadata.AIGC`。
- **传闻与猜测用正向替代**：「据说 / 网传 / 疑似」换成发布主体与时间，例如「据市地铁集团通报」。
- **标题三秒**：三条标题都在 20 字内，主体 + 动作在前、数字在后，`qc` 逐条量过。
- **平台时长**：快讯 60 秒、深度 180 秒、B 站 480 秒，`qc` 按 `--platform` 校验。

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--template` | flash | flash 快讯 30 秒竖屏 / depth 深度 90 秒横屏 |
| `--platform` | douyin | douyin / kuaishou / xhs / channels / bilibili |
| `--topic` / `--source` | 示例 / 待填 | 标题主体；来源单位 |
| `--when` / `--where` / `--subject` | 今天上午 / 本市 / 相关部门 | 事件三要素 |
| `--event` / `--figure` / `--quote` | 发布最新通报 / 空 / 空 | 动作、关键数字、官方原话 |
| `--background` / `--impact` | 通用背景 / 通用影响 | 背景段与影响段（建议手改成这条新闻的事实） |
| `--ai-label` | AI 辅助生成 | 片尾与描述的标注文案 |
| `--reporter` / `--column` | 空 / 空 | 记者署名与栏目名（进身份栏） |
| `--seconds` / `--resolution` | 模板默认 / 1080P | 总秒数；补镜头分辨率 |
| `--shots` | 快讯 0 / 深度 1 | 补镜头段数，每段 15 秒 |
| `--kind` | all | 图种：cover / scene / chart / people / timeline / ending |
| `--style-id` | 文档示例值 | `news_mixcut` 的模板 ID，来自 `smart_clip/template` |
| `--material` | — | 混剪素材，可重复给；本地文件自动 upload |
| `--budget` | 6000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺 `--topic` / `--keyword` / `--material`、秒数越界、选项缩写） |
| `3` | 自检或合规检查没过 |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档；`--json` 写在子命令前后都可以。

---

## 文件结构

```
sanjianke-news-shorts/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文 + 计费口径）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

运行时的稿子、字幕、图片都落在 `~/.a7w/news-shorts/`，不往包目录里写。

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
