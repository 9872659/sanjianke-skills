---
name: sanjianke-audio-tools
slug: sanjianke-audio-tools
displayName: 音频工具台 · 人声分离 42 点 / 补帧 25 点每秒
description: "**一首 3 分钟的歌，42 点（0.42 元）拆出人声和伴奏两条轨；30 秒的片子补到 60fps，750 点（7.50 元）。** 一条命令接完二次创作的音频后处理：本地音频 `upload`（0 点）换平台地址 → `audio-id`（39 点）换 audio_id → `split`（42 点）出人声 / 伴奏 → `mashup`（36 点）把两段歌词融成一段新的 → `interp`（25 点/秒）把片子补到 60fps。全部走 api.a7w.cn，零依赖、只用 Python 标准库。价格口径如实写：`vox` / `mashup_lyrics` / `upload_audio` 在 `GET /api/v1/pricing` 里只有一条 `music_generation/*` 的「上游实际点数 × 3」，没有独立单价，本包按平台 schema 的 14 / 12 / 13 点折算成 42 / 36 / 39 点，真实成交价只在返回体 `usage.points_cost` 里；`interp` 是价目表里唯一写死的 25 点/秒。`--budget`（单位：点）与 `--yes` 双闸门，超预算一个请求都不发；`doctor` 打 10 项免费探针、三个音频接口一次都不 POST。需要自备 api.a7w.cn 的 Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "二次创作最花时间的两步是「把歌拆开」和「把片子补顺」，本包把这两步做成一条链路。**价目（1 元 = 100 点，2026-11-08 现查 GET /api/v1/pricing，115 条规则）**：`vox` 按次，上游 14 点 × 3 = 42 点；`mashup_lyrics` 上游 12 点 × 3 = 36 点；`upload_audio` 上游 13 点 × 3 = 39 点；`interp` 按秒 25 点/秒；`upload` 与 `GET /api/v1/tasks/<id>` 都是 0 点。**三个接口的真实归属**：`vox` / `mashup_lyrics` / `upload_audio` 在 `music_generation`（13 个接口，drive=suno_music）名下，不在 `media_services_33`（29 个接口，drive=official）里；`mashup_lyrics` 与 `upload_audio` 是同步（call_type=1），`vox` 是异步（call_type=2，回 task_id）。**实测**：`POST /api/v1/video/viapi/interp` 空 body 回 400 `empty_url`、坏 URL 回 400 `url_not_allowed`（白名单：vr.a7w.cn / cdn2.jiujiushuyuan.cn/vr/ / oss.gpu.likeadmin.cn/openapi/）；`POST /api/v1/upload` 不带 file 回 200 code 0；本账号 1398 条任务台账里 `music_generation/create` 实测 84.50 - 325.00 点，`vox` 与 `interp` 还没有成交样本，所以本包对 create 两档只报实测区间、没样本时显示「待实测」，不编单价。**横评**：`models --need relabel` 把 `mashup_lyrics`（36 点）与文本模型（`/api/v1/models` 里 92 个带每千 token 单价的文本模型）同台报价；`--need split` 比 `vox` 与 `create` 的 stems / all_stems；`--need interp` 比在线 25 点/秒与本机 ffmpeg 0 点。**探针纪律**：只读 GET 或空 body POST，`GET /api/v1/apps/<app>` 一次都不打（命中通配计价、即时扣费不退），缺参的应用层 POST 也不打（先 reserve_sync 冻 60 点再退）。**退出码**：0 成功 / 2 用法 / 4 需 --yes / 5 超预算 / 6 调用失败 / 130 中断，`--json` 走 `{ok:true}` 与 `{ok:false,exit,error}`。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 音频后处理
  - 人声分离
  - 视频补帧
  - api.a7w.cn
---

# 音频工具台

**一条 3 分钟的歌，42 点拆成人声与伴奏；30 秒的片子，750 点补到 60fps。**

链路只有一条，五步：

```
本地音频 --upload 0 点--> 平台地址 --audio-id 39 点--> audio_id
         --split 42 点--> 人声 / 伴奏两条轨
         --mashup 36 点--> 两段歌词融成一段新的
本地视频 --upload 0 点--> 平台地址 --interp 25 点/秒--> 60fps
```

## 价目表（GET /api/v1/pricing 现查，1 元 = 100 点）

| 能力 | 端点 | 单价 | 口径 |
|---|---|---|---|
| 上传本地文件 | `POST /api/v1/upload` | **0 点** | multipart 字段名 `file`，免费 |
| 换 audio_id | `POST /api/v1/apps/music_generation/upload_audio` | **39 点/次** | 上游 13 点 × 3，同步 |
| 人声分离 | `POST /api/v1/apps/music_generation/vox` | **42 点/次** | 上游 14 点 × 3，异步回 task_id |
| 混搭歌词 | `POST /api/v1/apps/music_generation/mashup_lyrics` | **36 点/次** | 上游 12 点 × 3，同步直接回文本 |
| 整曲分离 | `POST /api/v1/apps/music_generation/create`（`type=stems`） | 实测区间 | 本账号 8 条 84.50 - 325.00 点 |
| 四轨分离 | 同上（`type=all_stems`） | 实测区间 | 同一条路径，价随 type 变 |
| 视频补帧 | `POST /api/v1/video/viapi/interp` | **25 点/秒** | 价目表写死的 perSecond=25 |
| 查任务 | `GET /api/v1/tasks/<task_id>` | **0 点** | 只打这一条，应用层 /query 一律不碰 |
| 本机补帧 | `ffmpeg -vf minterpolate` | **0 点** | 不联网，慢，胜在免费 |

## 三条干货

**一、这三个接口不在 `media_services_33` 里。** 2026-11-08 `GET /api/v1/apps` 现查：22 个应用 100 个接口，`vox` / `mashup_lyrics` / `upload_audio` 挂在 `music_generation`（13 个接口，drive=suno_music）名下，`media_services_33`（29 个接口，drive=official）装的是 ElevenLabs 配音与音乐生成那一批。拼错应用代号就是 404。

**二、42 / 36 / 39 是「上游 × 3」，不是价目表单价。** `GET /api/v1/pricing` 里只有一条 `/api/v1/apps/music_generation/*`：`{"mode":"flat","cost":0,"markupPercent":200}`，意思是上游实际点数 × 3。平台 schema 写 14 / 12 / 13 点，乘 3 才是 42 / 36 / 39；真实成交价只在返回体 `data.usage.points_cost`。本账号 `create` 实测 84.50 - 325.00 点，说明同一路径的价会随 type 拉开 4 倍，所以 `create` 两档只报实测区间。

**三、`interp` 的空探针能过，真单还没跑过。** 空 body 回 400 `empty_url`、填一个坏 URL 回 400 `url_not_allowed`，两条都停在参数校验层，说明路由在架；线上档位说明写过「已下线」，所以本包把它标成「待验证」，真跑一条才知道结不结算。素材白名单只有三处：`vr.a7w.cn`、`cdn2.jiujiushuyuan.cn/vr/`、`oss.gpu.likeadmin.cn/openapi/`（`upload` 返回的就是第三种）。想省钱又要 60fps，`models --need interp` 会同时给出本机 ffmpeg 的 0 点命令。

## 完整用法（12 个命令）

```
python3 scripts/run.py catalog                    # 8 条路线：单价 / 形态 / 路径（免费）
python3 scripts/run.py cost --seconds 60          # 单次价 + 整条链路总价（免费）
python3 scripts/run.py doctor                     # 10 项自检 + 流水（免费，0 点）
python3 scripts/run.py upload --file hook.mp3     # 本地文件 -> 平台地址（0 点）
python3 scripts/run.py audio-id --audio-url "https://oss.gpu.likeadmin.cn/openapi/..." --yes
python3 scripts/run.py split --audio-id audio_xxx --start 0 --end 30 --yes
python3 scripts/run.py mashup --a-file a.txt --b-file b.txt --yes
python3 scripts/run.py interp --video-url "https://..." --seconds 30 --yes
python3 scripts/run.py chain --file hook.mp3 --seconds 30 --dry-run
python3 scripts/run.py chain --file hook.mp3 --with-interp --video-url "https://..." --yes
python3 scripts/run.py models --need relabel --chars 2000
python3 scripts/run.py status --task-id task_xxx --video
```

`--dry-run` 打请求不提交；缺 `--yes` 退 4 并告诉你要花多少；超 `--budget` 退 5，一个请求都不发；`--json` 只输出一个 JSON 文档。

## 三步上手

**第一步，先看清价格。** `catalog` 不用 Key，直接看到 8 条路线；`cost --seconds 60` 告诉你「0 + 39 + 42 + 36 + 1500 = 1617 点」这笔账怎么来的。

**第二步，自检。** `doctor` 打 10 项：Key 与余额、价目表两条关键规则、三个接口在不在 `music_generation` 名下、92 个文本模型单价可读、`me/tasks` 台账、`interp` 空 body、`interp` 坏 URL、上传口、任务查询、流水。三个音频接口**一次都不 POST**，钱包不会被动。

**第三步，跑链路。** 先 `chain --dry-run` 看总价，再加 `--yes` 真跑；只想补帧就单独 `interp`。事后 `models --need split` 把 `vox` 与 `create` 的实测价摆一起，谁便宜一眼看到。

## 四个场景，笔笔有账

| 场景 | 走哪几步 | 点数 | 折合 |
|---|---|---|---|
| 只要伴奏做个 remix | upload → audio-id → split | 0 + 39 + 42 = **81** | 0.81 元 |
| 拆完再换一版词 | 上面三步 + mashup | 81 + 36 = **117** | 1.17 元 |
| 30 秒片子补到 60fps | upload → interp（30 秒） | 0 + 750 = **750** | 7.50 元 |
| 整条链路（30 秒片） | 五步全走 | 117 + 750 = **867** | 8.67 元 |

一笔一笔能对上：`cost --seconds 30` 打出来的就是这几行。

## 实测原文（2026-11-08，本账号）

```
GET  /api/v1/apps     → 200 · 22 个应用 / 100 个接口
  music_generation   13 个接口  vox(call_type=2) / mashup_lyrics(1) / upload_audio(1)
  media_services_33  29 个接口  三个 code 都不在这里

GET  /api/v1/pricing  → 200 · 115 条规则 · markupPercent=20
  /api/v1/apps/music_generation/*  {"mode":"flat","cost":0,"markupPercent":200}
  /api/v1/video/viapi/interp       {"mode":"per_second","perSecond":25}
  /api/v1/upload                   {"mode":"flat","cost":0}

POST /api/v1/video/viapi/interp  {}
  → 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空"}}
POST /api/v1/video/viapi/interp  {"videoUrl":"https://example.invalid/a.mp4"}
  → 400 {"error":{"code":"url_not_allowed","message":"videoUrl 必须是本站…"}}
POST /api/v1/upload（不带 file）   → 200 {"code":0,"msg":"…请使用 file 字段提交一个文件"}
GET  /api/v1/tasks/probe-no-such-task → 200 {"code":0,"msg":"任务不存在","data":null}
```

## 素材与白名单

- **音频**：`upload_audio` 只吃一个可公网访问的 `audio_url`；本地文件先走 `upload`（0 点）换成本站地址，再换 `audio_id`。URL 最短 24 小时内有效，`upload` 完要接着走下一步。
- **视频**：`interp` 只收本站托管的 `videoUrl`，三处白名单 —— `vr.a7w.cn` / `cdn2.jiujiushuyuan.cn/vr/` / `oss.gpu.likeadmin.cn/openapi/`。本包提交前先本地预检，不合格当场退回，省一次 400。
- **歌词**：中文歌词走 `--a-file` / `--b-file`（UTF-8 文本），比命令行里塞引号稳。

## 常见报错速查

| 返回 | 意思 | 怎么办 |
|---|---|---|
| `400 empty_url` | `videoUrl` 没给 | 先 `upload` 拿地址 |
| `400 url_not_allowed` | 地址不在三处白名单 | 换成本站地址；只有确知要直连才加 `--allow-any-url` |
| `400` / `422` + `input.xxx` | 参数类型或枚举不对 | 按提示改；这一层不建任务、不扣点 |
| `200 {"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术 | 说明这条 code 拼错或该应用没开，回 `catalog` 对路径 |
| `404` + HTML | 前缀下没有该端点 | 三个音频接口必须是 `/api/v1/apps/music_generation/<code>` |
| `HTTP 500` | 上游偶发 | 重试一次；失败任务全额退回，净 0 点 |
| 余额被冻 60 点后又退回 | 缺参 POST 触发了 `reserve_sync` | 本包不做这种探针；真遇到了等 refund 即可 |

## 这套价格怎么算出来的

1. `GET /api/v1/pricing` 的 115 条规则里，`music_generation` 只有通配 `music_generation/*`，`markupPercent=200` = 上游 × 3。
2. 上游价来自平台 schema：`vox` 14 点、`mashup_lyrics` 12 点、`upload_audio` 13 点，都是按次。
3. 14 × 3 = 42，12 × 3 = 36，13 × 3 = 39；`create` 的价随 `type` 变，只报 `/api/v1/me/tasks` 的实测区间。
4. `interp` 不用推：价目表直接写 `perSecond=25`。
5. 结论一句话：**按次档按「上游 × 3」估，按秒档按 25 点/秒算，没样本就写待实测。**

## 和已有包的分工

| 包 | 它管什么 | 本包的边界 |
|---|---|---|
| `sanjianke-suno-music` | 从零生成一首歌（create / lyrics / persona / style） | 本包接你**手上已有的音频**，做分离与改词；生成归它 |
| `sanjianke-pro-voice` | 配音与对白（`media_services_33` 的 8 条 TTS 线） | 本包不生成人声，只拆人声、只换词 |
| `sanjianke-video-lab` | 11 档视频后处理（修复 / 上色 / 擦字幕 / 抠像） | `interp` 是**第 12 档**：补帧。其余 11 档归它 |
| `sanjianke-ai-soundtrack` | 配乐、卡点、接时长 | 本包不改 BPM、不铺环境音，只拆轨与补帧 |

## 规格

- **零依赖**：只用 Python 3 标准库；`scripts/a7w.py` 是家族统一客户端（登录 / 回显 Key 状态）。
- **Key 三种来源**：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`，源码里没有任何 Key。
- **退出码**：`0` 成功 / `2` 用法 / `4` 需 `--yes` / `5` 超预算 / `6` 调用失败 / `1` 内部 / `130` 中断。
- **JSON 契约**：成功 `{"ok":true,...}`；失败 `{"ok":false,"exit":N,"error":{"kind":"usage|gate|confirm|budget|call|interrupt|internal","message":"..."}}`。
- **台账**：每次提交写 `~/.a7w/audio-tools-ledger.json`，`log` 看最近 20 条。
- **中文控制台**：输出统一过 `safe()`，cp936 编不出的字符换成 `-`（不留半角问号），符号只用 `√ × · →`，金额写「元」。
- **实测基线**：2026-11-08，本账号 1398 条任务、余额 999,997,393,008.98 点；`music_generation/create` 8 条 84.50 - 325.00 点，`vox` / `mashup_lyrics` / `upload_audio` / `interp` 均无成交样本。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
