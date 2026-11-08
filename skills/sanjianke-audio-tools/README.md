# 音频工具台（sanjianke-audio-tools）

**一首 3 分钟的歌，42 点（0.42 元）拆出人声与伴奏；30 秒的片子，750 点补到 60fps。**

二次创作的音频后处理通常卡在两件事：把一条歌拆成人声和伴奏，把一段 30fps 的素材补成 60fps。本包把这两件事接成一条链，全部走 [api.a7w.cn](https://api.a7w.cn/)，零依赖、只用 Python 标准库。

```
本地音频 --upload 0 点--> 平台地址 --audio-id 39 点--> audio_id
         --split 42 点--> 人声 / 伴奏两条轨
         --mashup 36 点--> 两段歌词融成一段新的
本地视频 --upload 0 点--> 平台地址 --interp 25 点/秒--> 60fps
```

## 文件结构

```
sanjianke-audio-tools/
├── SKILL.md                        技能说明（给模型看）
├── README.md                       这一份（给人看）
├── LICENSE.md                      MIT
├── references/
│   ├── api-contract.md             六个接口的实测契约（含原始返回）
│   ├── troubleshooting.md          按报错找原因
│   └── 二创链路.md                  分离 / 改词 / 补帧 的落地流程与 ffmpeg 命令
└── scripts/
    ├── a7w.py                      家族统一客户端（登录 / 查余额）
    └── run.py                      本包命令层（12 个子命令）
```

## 安装

没有任何第三方依赖，Python 3.8 以上直接跑：

```bash
python3 scripts/run.py catalog        # 不用 Key，先看 8 条路线
```

Key 三种来源，任选一种：

```bash
export A7W_API_KEY=sk-xxxx                     # 环境变量
python3 scripts/run.py catalog --key sk-xxxx   # 命令行
python3 scripts/a7w.py login --key sk-xxxx     # 落到 ~/.a7w/config.json
```

注册领 Key 在 [算力集市](https://api.a7w.cn/)。

## 快速开始

```bash
# 1. 先看钱（免费）
python3 scripts/run.py cost --seconds 60

# 2. 自检（免费，10 项探针，0 点）
python3 scripts/run.py doctor

# 3. 干跑整条链路，看清每一步发什么、花多少
python3 scripts/run.py chain --file hook.mp3 --seconds 30 --dry-run
```

## 命令表

| 命令 | 干什么 | 花费 |
|---|---|---|
| `catalog` | 8 条路线：单价 / 调用形态 / 路径 | 0 点（不用 Key） |
| `cost` | 单次价 + 整条链路总价 | 0 点（不用 Key） |
| `doctor` | 10 项自检 + 流水近 1 小时净额 | 0 点 |
| `upload` | 本地文件 → 平台地址（multipart，字段名 `file`） | 0 点 |
| `audio-id` | 平台地址 → `audio_id` | 39 点起 |
| `split` | `audio_id` → 人声 / 伴奏（可只取副歌那一段） | 42 点起 |
| `mashup` | 两段歌词 → 一段新的（同步回文本） | 36 点起 |
| `interp` | 视频补到 60fps | 25 点/秒 |
| `chain` | upload → audio-id → split（可选 mashup / interp） | 逐笔相加 |
| `models` | 同一需求多模型横评（`--need relabel/split/interp`） | 0 点 |
| `status` | 查任务，只打 `GET /api/v1/tasks/<id>` | 0 点 |
| `log` | 本地台账 | 0 点 |

## 价格表（1 元 = 100 点）

| 能力 | 端点 | 单价 | 计费口径 |
|---|---|---|---|
| 上传 | `POST /api/v1/upload` | **0 点** | 免费，返回本站托管地址 |
| 换 audio_id | `POST /api/v1/apps/music_generation/upload_audio` | **39 点/次** | 上游 13 点 × 3 |
| 人声分离 | `POST /api/v1/apps/music_generation/vox` | **42 点/次** | 上游 14 点 × 3，异步 |
| 混搭歌词 | `POST /api/v1/apps/music_generation/mashup_lyrics` | **36 点/次** | 上游 12 点 × 3，同步 |
| 整曲分离 | `POST /api/v1/apps/music_generation/create`（`type=stems`） | 实测区间 | 本账号 8 条 84.50 - 325.00 点 |
| 四轨分离 | 同上（`type=all_stems`） | 实测区间 | 同路径，价随 type 变 |
| 视频补帧 | `POST /api/v1/video/viapi/interp` | **25 点/秒** | 价目表写死 `perSecond=25` |
| 查任务 | `GET /api/v1/tasks/<task_id>` | **0 点** | 免费，别去碰应用层 `/query` |

三档按次的价是这么来的：`GET /api/v1/pricing` 里 `music_generation` 没有独立规则，只有一条 `music_generation/*` 的 `markupPercent=200`（上游实际点数 × 3）；平台 schema 写 `vox` 14 点、`mashup_lyrics` 12 点、`upload_audio` 13 点，乘 3 得到 42 / 36 / 39。真实成交价只在返回体的 `data.usage.points_cost`。

## 三个接口到底挂在哪个应用下

2026-11-08 `GET /api/v1/apps` 现查，22 个应用共 100 个接口：

| 接口 code | 应用 | call_type | 形态 |
|---|---|---|---|
| `vox` | `music_generation` | 2 | 异步，回 `task_id` |
| `mashup_lyrics` | `music_generation` | 1 | 同步，直接回文本 |
| `upload_audio` | `music_generation` | 1 | 同步，回 `audio_id` |

`media_services_33` 是另一个应用（29 个接口，drive=official），装的是 ElevenLabs 配音与音乐生成那一批，这三个 code 不在里面。路径拼错就是 404，`catalog` 打出来的路径是唯一正确的那个。

## 和已有包的分工

| 包 | 它管什么 | 本包的边界 |
|---|---|---|
| `sanjianke-suno-music` | 从零生成一首歌（`create` / `lyrics` / `persona` / `style`） | 本包接**手上已有的音频**，做分离与改词 |
| `sanjianke-pro-voice` | 配音与对白（`media_services_33` 的 8 条 TTS 线） | 本包不生成人声，只拆人声、只换词 |
| `sanjianke-video-lab` | 11 档视频后处理（修复 / 上色 / 擦字幕 / 抠像） | `interp` 是**第 12 档**：补帧。其余 11 档归它 |
| `sanjianke-ai-soundtrack` | 配乐、卡点、接时长 | 本包不改 BPM、不铺环境音，只拆轨与补帧 |

## 常见问题

**问：`split` 出来的两条轨是哪个字段。**
`vox` 是异步的，提交回 `task_id`，产物在 `status` 里按 `*_url` 键打出来（人声 / 伴奏 / 原曲都会列出来）。`status --json` 给完整结构，键名以线上为准。

**问：为什么 `interp` 标「待验证」。**
价目表有 `perSecond=25`，空 body 与坏 URL 两种探针都停在参数校验（400 `empty_url` / 400 `url_not_allowed`），说明路由在架；线上档位说明写过「已下线」，所以本包不把它当默认路径，`cost` 里单独标状态，真跑一条才知道结不结算。

**问：`create` 两档为什么不给固定价。**
`create` 的价随 `type` 变，本账号 8 条实测从 84.50 到 325.00 点，差 4 倍。本包只报实测区间；没有流水的账号显示「待实测」，不填一个好看的数字。

**问：会不会偷偷扣点。**
不会。`doctor` 只发只读 GET、两个 `interp` 空 body 探针、一个不带 file 的上传，三个音频接口一次都不 POST（缺参会先 `reserve_sync` 冻 60 点再退，钱包会被动一下）。所有写操作都要 `--yes`，并且先过 `--budget` 这道闸：超预算时一个请求都不发。

## 实测记录

```
2026-11-08  本账号 1398 条任务台账，余额 999,997,393,008.98 点
            music_generation/create         8 条   84.50 - 325.00 点
            vox / mashup_lyrics / upload_audio / interp   0 条
            /api/v1/apps      22 个应用 / 100 个接口
            /api/v1/pricing   115 条规则，music_generation 落通配 ×3
            interp 空 body    → 400 empty_url
            interp 坏 URL     → 400 url_not_allowed
            upload 不带 file  → 200 code 0
```

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
