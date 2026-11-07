# 游戏宣发 三个节奏点一套交付

**一个上线期双语素材包，34 张静图 204 点 = 2.04 元；加一条 15 秒买量片与一条 30 秒品牌片，5,748 点 = 57.48 元。**

宣发岗一天真正要交的不是「一张图」，是「一个节奏点的一整套素材」：预约期要主视觉、角色立绘、商店五图和里程碑战报；上线期要 15 秒买量片放量、30 秒品牌片定调、上线战报对外；长线运营每个版本又是一套 KV + 战报 + 一条买量片。同一套素材还要同时满足 TapTap、B站、抖音、Steam、微信小游戏五个平台的规格，以及简中、繁中、英文、日文、韩文五个语种的命名与文案。

---

## 一个宣发岗一天 / 一个节奏点要交什么

| # | 交付物 | 规格 | 数量 | 命名 |
|---|---|---|---|---|
| 1 | 主视觉 KV | 9:16 + 16:9 / png / 上架尺寸见矩阵 | 3 / 语种 | `GL01-KV_taptap_9x16_zh-CN_v1.png` |
| 2 | 角色立绘 | 3:4 + 1:1 / png / 半身立绘 | 2 / 语种 | `GL01-CHAR_taptap_3x4_zh-CN_v1.png` |
| 3 | 商店五图 | 9:16（TapTap）/ 16:9（Steam）/ 每组 5 张 | 10 / 语种 | `GL01-STORE_taptap_9x16_zh-CN_v1_1.png` |
| 4 | 战报图 | 16:9 + 9:16 / png / 留数据位 | 2 / 语种 | `GL01-RPT_bilibili_16x9_zh-CN_v1.png` |
| 5 | 15 秒买量片 | 9:16 / H.264 / 1080P / 15 秒 | 1 / 语种 | `GL01-AD15_douyin_9x16_zh-CN_v1.mp4` |
| 6 | 30 秒品牌片 | 16:9 / H.264 / 1080P / 两段 15 秒拼 | 1 / 语种 | `GL01-BR30_bilibili_16x9_zh-CN_v1.mp4` |
| 7 | 多语言配音 | mp3 / 每条约 60 字 / 与视频条数一致 | 2 / 语种 | `GL01-AD15_douyin_9x16_zh-CN_v1_voice.mp3` |
| 8 | 宣发配乐 | mp3 / 30 秒循环 / 一个语种一首 | 1 / 语种 | `bgm_zh-CN.mp3` |
| 9 | 宣发排期 | T0 / T1 / T2 三段，含交付动作与日期 | 1 | `宣发排期.csv` |
| 10 | 素材矩阵 | 全量清单，可导入素材库 | 1 | `素材矩阵.csv` |
| 11 | 交付单 | 项目信息 / 节奏 / 清单 / 成本 / 平台规格 | 1 | `交付单.md` |

`plan` 一条命令把第 1~11 项里**能算的部分**全部写好：阶段、平台、尺寸、语种、命名、主标副标、行动号召、画面提示、成本单、交付清单、宣发排期，落在 `~/.a7w/game-promo/<日期>/`，纯本地、不联网、0 点。

---

## 这个包和底层能力包的分工

| 你手上要的东西 | 用哪个包 | 它交付什么 |
|---|---|---|
| 一张图 / 一套图 | `sanjianke-gpt-image` | 6 点一张，文生图 / 图生图 / GIF |
| 一段 4~15 秒镜头 | `a7w-full-video` | 首帧 + 运镜，按秒 x 分辨率计费 |
| 分辨率分档 + 素材托管 | `a7w-seedance` | create 出片 + 5 个素材管理接口 |
| 一条配音 / 一首配乐 | `a7w-voice-tts` / `a7w-music-generation` | 同步 tts · 克隆音色 · Suno 配乐参数表 |
| **一个宣发岗位在一个节奏点要交的整套素材 + 排期 + 交付单** | **本包** | 矩阵、文案、命名、平台规格、九道检查、成本单 |

底层包做单步，本包做「一个岗位一个节奏点要交的东西」：先在本地把阶段、平台、语种、命名、预算排好，再决定哪几条值得花钱。

---

## 三个节奏点

| 阶段 | 窗口 | 交什么 | 观察指标 |
|---|---|---|---|
| `T0` 预约期 | 上线前 30 天 | 主视觉 + 角色立绘 + 商店五图 + 预约里程碑战报 | 预约转化率 / 商店页访问 |
| `T1` 上线期 | 上线日到上线后 14 天 | 15 秒买量片放量 + 30 秒品牌片 + 上线战报 | 首日 ROI / 买量成本 / 首日留存 |
| `T2` 长线运营 | 上线后 15 天起 | 每个版本一套 KV + 战报 + 一条买量片 | 版本回流 / 版本付费率 |

上线日由 `--launch-date` 指定，排期按它倒推：T0 = 上线前 30 天，T1 = 上线日到 +13 天，T2 = +14 天到 +90 天。

---

## 平台规格

| 平台 | 比例 | 请求尺寸 | 上架尺寸 | 用途 |
|---|---|---|---|---|
| `taptap` | 9:16 / 3:4 | 720x1280 / 1152x1536 | 1080x1920 / 1242x1660 | 预约页头图、详情竖图、论坛活动 |
| `bilibili` | 16:9 / 3:4 / 1:1 | 1280x720 / 1152x1536 / 1024x1024 | 1920x1080 / 1242x1660 / 1080x1080 | 视频封面、动态图、UP 主头像 |
| `douyin` | 9:16 / 1:1 | 720x1280 / 1024x1024 | 1080x1920 / 1080x1080 | 买量片、直播预约、星图任务 |
| `steam` | 16:9 / 1:1 | 1280x720 / 1024x1024 | 1920x1080 / 1080x1080 | 商店页头图、库页胶囊 |
| `wechat` | 9:16 / 1:1 | 720x1280 / 1024x1024 | 1080x1920 / 1080x1080 | 小游戏入口、朋友圈 |

请求尺寸都守在 gpt-image 的合法区间里：16 的倍数、长短边 3:1 内、单边 3840 内、总像素 655,360~8,294,400。`qc` 按这四条再验一遍，省得跑完 34 张才发现尺寸不合法。

---

## 6 类素材 x 5 平台 x 5 语种怎么排

| 素材 | 出到哪些平台 | 张数 / 条数 |
|---|---|---|
| 主视觉 KV | TapTap 9:16、B站 16:9、Steam 16:9 | 3 / 语种 |
| 角色立绘 | TapTap 3:4、B站 1:1 | 2 / 语种 |
| 商店五图 | TapTap 9:16 x5、Steam 16:9 x5 | 10 / 语种 |
| 战报图 | B站 16:9、抖音 9:16 | 2 / 语种 |
| 15 秒买量片 | 抖音 9:16，复用到 TapTap / 微信小游戏 / 视频号 | 1 / 语种 |
| 30 秒品牌片 | B站 16:9，复用到 Steam / YouTube | 1 / 语种 |

**命名 `游戏码-素材_平台_尺寸_语种_v版本`**：

```
GL01-KV_taptap_9x16_zh-CN_v1.png      主视觉 / TapTap 竖版 / 简中 / 第 1 版
GL01-STORE_steam_16x9_en-US_v1_3.png  商店五图第 3 张 / Steam 横版 / 英文
GL01-AD15_douyin_9x16_zh-CN_v1.mp4    15 秒买量片 / 抖音竖版 / 简中
```

文件名就是 A/B 表与素材库的主键：一眼看出这一轮改的是素材、平台、语种还是版本。`qc` 会按这条正则逐个验。

---

## 价目表（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing` + 流水实测）

| 工序 | 接口 | 单价 | 形态 |
|---|---|---|---|
| 出图 | `POST /api/v1/images/generations` | **6 点/张** | 同步，n 1~4 |
| 改图 | `POST /api/v1/images/edits` | **6 点/张** | 同步，带草稿不走样 |
| 买量片 / 品牌片 | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒 | 异步，单段 4~15 秒 |
| 预告片 | `POST /api/v1/apps/seedance/create` | **11,000 点/次** | 异步，flat |
| 素材托管 | `POST /api/v1/apps/seedance/createGroup` 等 5 个 | 落 `/apps/seedance/*` 通配，按 11,000 点/次估 | multipart |
| 配音 | `POST /api/v1/apps/voice_tts/tts` | 约 **0.18 点/字** | 同步，上游真实点数 x 3 |
| 配乐 | `POST /api/v1/apps/media_services_33/music_generate` | **50 点起/首** | 异步，上游 x 2 保底 50 |
| 查进度 | `GET /api/v1/tasks/<task_id>` | **0 点** | 只读 |
| 传素材 | `POST /api/v1/upload` | **0 点** | multipart，字段名 file |
| 排期 / 矩阵 / 检查 | `plan` / `qc`（纯本地） | **0 点** | 不联网 |

### 一个上线期双语包多少钱

| 走法 | 点数 | 元 |
|---|---|---|
| 全静态（34 张 = 2 语种 x 17 张） | **204** | **2.04** |
| 静态 + 两条 15 秒买量片 + 配音 + 配乐 | 2,126 | 21.26 |
| 静态 + 买量片 + 品牌片 + 配音 + 配乐 | **5,748** | **57.48** |
| 再加两条 seedance 预告片 | 27,748 | 277.48 |

单条 15 秒 1080P 买量片 = 900 点 = 9 元；30 秒品牌片按两段 15 秒提交 = 1,800 点 = 18 元；seedance 预告片是 flat 11,000 点/次 = 110 元。`cost` 会把四种走法一次打出来。

---

## 快速开始

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 2) 免费：自检 + 算钱
python3 scripts/run.py doctor
python3 scripts/run.py cost --phase T1 --locales 2

# 3) 免费：排矩阵、多语言文案、交付清单、宣发排期，再过一遍九道检查
python3 scripts/run.py plan --game "代号：山海" --code GL01 --phase T1 \
    --locale zh-CN --locale en-US --launch-date 20261201 \
    --license-no "ISBN 978-7-XXXX" --rating 16+
python3 scripts/run.py qc --plan ~/.a7w/game-promo/20261108/plan.json

# 4) 按矩阵花钱（每一步都能单跑、能续跑）
python3 scripts/run.py img  --asset kv --size 16x9 --locale zh-CN --n 2 --yes
python3 scripts/run.py film --asset ad15 --seconds 15 --image GL01-KV.png --yes
python3 scripts/run.py voice --text "今日公测，登录领限定角色" --yes
python3 scripts/run.py music --style "史诗管弦，鼓点推进，适合 30 秒宣发片" --yes
python3 scripts/run.py status --task-id tsk_xxx
```

---

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 11 个动作 + 6 类素材 + 5 平台规格 + 现查单价 |
| `cost --phase T1 --locales 2` | 免费 | 一个宣发包多少钱，四种走法对比 |
| `plan --game "…" --locale zh-CN` | 免费 | 矩阵、多语言文案、命名、交付清单、排期 |
| `qc --plan plan.json` | 免费 | 九道检查：版号 / 概率公示 / 话术 / 命名 / 尺寸 / 多语言 / 阶段 / 矩阵 |
| `img --asset kv --size 16x9` | **6 点/张** | 主视觉、立绘、商店五图、战报图 |
| `img --ref 草稿.png` | **6 点/张** | 走改图线，构图与主体不走样 |
| `film --asset ad15` | **60 点/秒** | 买量片，15 秒 900 点，首帧图自动 upload |
| `seedance --action create` | **11,000 点/次** | 预告片，分辨率分档 |
| `seedance --action group/asset/get/update/delete` | 落 11,000 点通配 | 素材托管，multipart |
| `seedance --action query` | 免费 | 转成 `GET /tasks/<id>`，一次 0 点 |
| `voice --script 配音稿.txt` | **约 0.18 点/字** | 多语言配音，500 字内一条 |
| `music --style "…"` | **50 点起** | 宣发配乐，30 秒循环 |
| `upload --file kv.png` | 免费 | 换 `oss.gpu.likeadmin.cn` 白名单地址 |
| `status --task-id tsk_xxx` | 免费 | 只走 `GET /api/v1/tasks/<id>` |
| `log` | 免费 | 本地台账 |

**不加 `--yes` 退 `4`** 并告诉你这次要花多少点；**预计点数超 `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 8000 = 80 元，seedance 预告片记得调到 12000）。

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--game` / `--code` | 代号：山海 / GL01 | 游戏名；游戏码 2~6 位，进文件名 |
| `--genre` | 二次元卡牌 | 品类，进提示词与副标 |
| `--phase` | T1 | T0 预约期 / T1 上线期 / T2 长线运营 |
| `--locale` | zh-CN | 可重复给：zh-CN / zh-TW / en-US / ja-JP / ko-KR |
| `--launch-date` | 今天 + 30 天 | 上线日 YYYYMMDD，排期按它倒推 |
| `--license-no` / `--rating` | 空 / all | 版号与适龄标识，进交付单 |
| `--asset` / `--size` | kv / 16x9 | 素材类型与尺寸，见 catalog |
| `--n` | 1 | 出图张数 1~4，一次多图按张计费 |
| `--seconds` / `--resolution` | 15 / 1080P | 视频秒数与分辨率 |
| `--with-video` | 关 | `plan` 时把视频与配音也计进本次预算 |
| `--budget` | 8000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填参数、秒数越界、选项缩写） |
| `3` | `qc` 检查没过 |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档；`--json` 写在子命令前后都可以。

---

## 文件结构

```
sanjianke-game-promo/
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

运行时产生的矩阵、文案、图片都落在 `~/.a7w/game-promo/`，不往包目录里写。

---

## 三条用钱换来的规矩

**一、轮询一次就是一次的钱，seedance 尤其贵。** `seedance/query` 落在 `/api/v1/apps/seedance/*` 通配价上，一次 11,000 点；轮询 10 次就是 110,000 点。本包 `status` 与 `--action query` 都只打 `GET /api/v1/tasks/<id>`，价目表里这条是 cost:0，等半小时也是 0 点。

**二、`GET /api/v1/apps/<app>` 是收费的。** 它命中 `/apps/<app>/*` 的通配计价，按该应用 flat 单价即时扣费、不退（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔）。要目录只看 `/api/v1/apps` 列表和 `/api/v1/pricing`，两条都是 cost:0。

**三、首帧图有域名白名单。** 外站地址一律 400 `url_not_allowed`，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。`film --image kv.png` 会先 `POST /api/v1/upload`（免费）换地址；`img --ref 草稿.png` 走 multipart 直接送文件，整条改图线不需要公网地址。

---

## 多语言与合规

- **一套画面，分语种文案**：画面复用一套，主标、副标、行动号召按 `--locale` 分别生成，配音按语种分别合成。
- **版号与适龄**：交付单写上限号与 12+ / 16+ / 18+ 标识；18+ 素材走微信小游戏与抖音要先提交分级材料。
- **概率公示**：文案里出现抽卡、十连、概率、保底时，同时给出「概率公示」口径。
- **买量话术**：把「最 / 第一 / 100% / 稳赚」换成可验证的结果，例如「首周预约 120 万」。
- **阶段口径**：预约期素材写预约，上线后素材写当期版本，一句话对得上排期。
- **素材来源**：立绘与 KV 自有素材优先，参考图只借构图，人物与 logo 自己出。
- **生成标识**：平台要求 AIGC 标识时，`film --aigc-mark` 重跑即可。

---

## 遇到报错

先看 `references/troubleshooting.md`：按退出码与 HTTP 状态码分节，每条都给真实报错原文与处理动作。跑一遍 `doctor`，出现 `×` 的那一行就是问题所在。

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
