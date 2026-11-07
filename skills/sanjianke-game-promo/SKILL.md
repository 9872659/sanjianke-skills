---
name: sanjianke-game-promo
slug: sanjianke-game-promo
displayName: 游戏宣发 三个节奏点一套交付
description: "**上线期双语素材包 34 张静图 204 点 = 2.04 元**；加 15 秒买量片与 30 秒品牌片共 5,748 点 = 57.48 元。按预约期 / 上线期 / 长线运营三个节奏点排矩阵：6 类素材 x 5 个平台（TapTap / B站 / 抖音 / Steam / 微信小游戏）x 5 个语种。出图 6 点/张，full_video 1080P 60 点/秒，seedance 预告片 11,000 点/次，查进度只走 GET /tasks/<id>（0 点）。plan 与 qc 纯本地 0 点，一次出矩阵、多语言文案、命名、交付清单、排期与九道检查。缺 --yes 退 4 报金额，超 --budget 退 5 一个请求都不发。需要自备 api.a7w.cn 的 Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
summary: "一个节奏点要交的不是一张图，是一整套素材。本包把六条能力按宣发岗位流程重排：预约期出主视觉、立绘、商店五图与里程碑战报；上线期加 15 秒买量片、30 秒品牌片与战报；长线运营每个版本一套 KV + 战报 + 一条买量片。价目（1 元 = 100 点）：gpt-image-2.6 6 点/张、full_video 1080P 60 点/秒（15 秒 900 点）、seedance create 11,000 点/次、voice_tts 约 0.18 点/字、music_generate 50 点起、upload 与 GET /tasks/<id> 都是 0 点。上线期双语包：静图 34 张 204 点（2.04 元）；加买量片与品牌片 5,748 点；加预告片 27,748 点。三条实测：seedance/query 一次 11,000 点，查进度只走 GET /tasks/<id>；GET /apps/<app> 命中通配、扣了不退，目录只看 /apps 与 /pricing；首帧图只认本站地址，本地图先 POST /upload。九道检查覆盖版号、适龄、概率、话术、命名、尺寸与阶段。缺 --yes 退 4，超 --budget 退 5 不发请求。需要自备 api.a7w.cn 的 Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 游戏宣发
  - 买量素材
  - 多语言
  - api.a7w.cn
---

# 游戏宣发 · 三个节奏点一套交付

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

**一个上线期双语素材包，34 张静图 204 点 = 2.04 元。** 主视觉、角色立绘、商店五图、战报图一次排完；加一条 15 秒买量片（900 点）和一条 30 秒品牌片（1,800 点），整包 5,748 点 = 57.48 元。预约期、上线期、长线运营，每个节奏点各有一套该交的东西。

## 这个包和底层能力包的分工

| 你手上要的东西 | 用哪个包 | 它交付什么 |
|---|---|---|
| 一张图 / 一套图 | `sanjianke-gpt-image` | 6 点一张，文生图 / 图生图 / GIF |
| 一段 4~15 秒镜头 | `a7w-full-video` | 首帧 + 运镜，按秒 x 分辨率计费 |
| 分辨率分档 + 素材托管 | `a7w-seedance` | create 出片 + 5 个素材管理接口 |
| 一条配音 / 一首配乐 | `a7w-voice-tts` / `a7w-music-generation` | 同步 tts · 克隆音色 · Suno 配乐参数表 |
| **一个宣发岗位在一个节奏点要交的整套素材 + 排期 + 交付单** | **本包** | 矩阵、文案、命名、平台规格、九道检查、成本单 |

底层包做单步，本包做「一个岗位一个节奏点要交的东西」：先把阶段、平台、语种、命名、预算排好，再决定哪几条值得花钱。

## 交付清单（宣发岗一天 / 一个节奏点）

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
| 9 | 排期 / 矩阵 / 交付单 | T0~T2 排期、全量清单、成本单 | 3 份 | `宣发排期.csv` / `素材矩阵.csv` / `交付单.md` |

`plan` 一条命令把第 1~9 项里能算的部分全部写好，落在 `~/.a7w/game-promo/<日期>/`，纯本地、不联网、0 点。

## 三个节奏点

| 阶段 | 窗口 | 交什么 | 观察指标 |
|---|---|---|---|
| `T0` 预约期 | 上线前 30 天 | 主视觉 + 角色立绘 + 商店五图 + 预约里程碑战报 | 预约转化率 / 商店页访问 |
| `T1` 上线期 | 上线日到上线后 14 天 | 15 秒买量片放量 + 30 秒品牌片 + 上线战报 | 首日 ROI / 买量成本 / 首日留存 |
| `T2` 长线运营 | 上线后 15 天起 | 每个版本一套 KV + 战报 + 一条买量片 | 版本回流 / 版本付费率 |

## 平台规格（`plan` 与 `qc` 用的就是这张表）

| 平台 | 比例 | 请求尺寸 | 上架尺寸 | 用途 |
|---|---|---|---|---|
| `taptap` | 9:16 / 3:4 | 720x1280 / 1152x1536 | 1080x1920 / 1242x1660 | 预约页头图、详情竖图、论坛活动 |
| `bilibili` | 16:9 / 3:4 / 1:1 | 1280x720 / 1152x1536 / 1024x1024 | 1920x1080 / 1242x1660 / 1080x1080 | 视频封面、动态图、UP 主头像 |
| `douyin` | 9:16 / 1:1 | 720x1280 / 1024x1024 | 1080x1920 / 1080x1080 | 买量片、直播预约、星图任务 |
| `steam` | 16:9 / 1:1 | 1280x720 / 1024x1024 | 1920x1080 / 1080x1080 | 商店页头图、库页胶囊 |
| `wechat` | 9:16 / 1:1 | 720x1280 / 1024x1024 | 1080x1920 / 1080x1080 | 小游戏入口、朋友圈 |

请求尺寸守在 gpt-image 四条内：16 的倍数、长短边 3:1 内、单边 3840 内、总像素 655,360~8,294,400。

## 一个上线期双语包多少钱（1 元 = 100 点）

| 走法 | 点数 | 元 |
|---|---|---|
| 全静态（34 张 = 2 语种 x 17 张） | **204** | **2.04** |
| 静态 + 两条 15 秒买量片 + 配音 + 配乐 | 2,126 | 21.26 |
| 静态 + 买量片 + 品牌片 + 配音 + 配乐 | **5,748** | **57.48** |
| 再加两条 seedance 预告片 | 27,748 | 277.48 |

单条 15 秒 1080P 买量片 = 900 点 = 9 元；30 秒品牌片按两段 15 秒提交 = 1,800 点 = 18 元；seedance 预告片是 flat 11,000 点/次 = 110 元。

## 三条干货（别人不写进文档的）

**一、seedance 的 `query` 一次就是 11,000 点。** 价目表 `/api/v1/apps/seedance/*` 是 flat 11,000，连查询口都算在内。本包 `--action query` 直接转成 `GET /api/v1/tasks/<id>`（0 点），等十分钟也是 0 点。

**二、`GET /api/v1/apps/<app>` 是收费的。** 它命中 `/apps/<app>/*` 的通配计价，按该应用 flat 单价即时扣费、不退（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔）。要目录只看 `/api/v1/apps` 列表和 `/api/v1/pricing`，两条都是 cost:0。

**三、首帧图有域名白名单。** 外站地址一律 400 `url_not_allowed`，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。`film --image kv.png` 会先 `POST /api/v1/upload`（免费）换地址；`img --ref 草稿.png` 走 multipart 直接送文件，整条改图线不需要公网地址。

## 多语言怎么发

五个语种标签：`zh-CN` 简体、`zh-TW` 繁体、`en-US` 英文、`ja-JP` 日文、`ko-KR` 韩文，`--locale` 可重复给。每语种一套完整素材，命名带语种标签；画面可复用一套，文案与配音按语种分别出，行动号召按阶段切换（预约 / 下载 / 更新版本）。

## 三步上手

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key

# 2) 免费：自检 + 算钱 + 排矩阵 + 过检查
python3 scripts/run.py doctor
python3 scripts/run.py cost --phase T1 --locales 2
python3 scripts/run.py plan --game "代号：山海" --code GL01 --phase T1 \
    --locale zh-CN --locale en-US --launch-date 20261201 --rating 16+
python3 scripts/run.py qc --plan ~/.a7w/game-promo/20261108/plan.json

# 3) 按矩阵花钱（每一步都能单跑、能续跑）
python3 scripts/run.py img  --asset kv --size 16x9 --locale zh-CN --n 2 --yes
python3 scripts/run.py film --asset ad15 --seconds 15 --image GL01-KV.png --yes
python3 scripts/run.py voice --text "今日公测，登录领限定角色" --yes
python3 scripts/run.py status --task-id tsk_xxx
```

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 11 个动作 + 6 类素材 + 5 平台规格 + 现查单价 |
| `cost --phase T1 --locales 2` | 免费 | 一个宣发包多少钱，四种走法对比 |
| `plan --game "…" --locale zh-CN` | 免费 | 矩阵、多语言文案、命名、交付清单、排期 |
| `qc --plan plan.json` | 免费 | 九道检查：版号 / 概率公示 / 话术 / 命名 / 尺寸 / 多语言 / 阶段 / 矩阵 |
| `img --asset kv --size 16x9` | **6 点/张** | 主视觉、立绘、商店五图、战报图；`--ref` 走改图线 |
| `film --asset ad15` | **60 点/秒** | 买量片，15 秒 900 点，首帧自动 upload |
| `seedance --action create` | **11,000 点/次** | 预告片；`group/asset/get/update/delete` 是素材托管，`query` 免费转任务查询 |
| `voice --text "…"` | **约 0.18 点/字** | 多语言配音，500 字内一条 |
| `music --style "…"` | **50 点起** | 宣发配乐，30 秒循环 |
| `upload --file kv.png` | 免费 | 换 `oss.gpu.likeadmin.cn` 白名单地址 |
| `status --task-id tsk_xxx` | 免费 | 只走 `GET /api/v1/tasks/<id>` |

## 合规检查（`qc` 已经做成默认动作）

- **版号与适龄**：交付单写上限号与 12+ / 16+ / 18+ 标识，18+ 素材走微信小游戏与抖音要先提交分级材料。
- **概率公示**：文案里出现抽卡、十连、概率、保底时，同时给出「概率公示」口径。
- **买量话术**：把「最 / 第一 / 100% / 稳赚」换成可验证的结果，例如「首周预约 120 万」。
- **阶段口径**：预约期素材写预约，上线后素材写当期版本，一句话对得上排期。
- **命名与多语言**：`游戏码-素材_平台_尺寸_语种_v版本`，每语种一套完整素材、组内条数一一对应。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--game` / `--code` | 代号：山海 / GL01 | 游戏名；游戏码 2~6 位，进文件名 |
| `--genre` | 二次元卡牌 | 品类，进提示词与副标 |
| `--phase` | T1 | T0 预约期 / T1 上线期 / T2 长线运营 |
| `--locale` | zh-CN | 可重复给：zh-CN / zh-TW / en-US / ja-JP / ko-KR |
| `--launch-date` / `--rating` | 今天+30 天 / all | 上线日 YYYYMMDD；适龄 12+ / 16+ / 18+ |
| `--asset` / `--size` | kv / 16x9 | 素材类型与尺寸，见 catalog |
| `--budget` | 8000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

退出码：`0` 成功 / `2` 用法错 / `3` 检查没过 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断。`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
