# 短剧量产 · 一天 10 条日更的排产台

**一天 10 条短剧日更，8 个工位一张排产单，8,580 点 = 85.80 元，单条 8.58 元。**

选题 → 脚本 → 配音 → 数字人口播 → 配乐 → 卡点字幕 → 封面 → 分发交付，
按短剧团队的真实顺序排产，接 `api.a7w.cn` 的 4 条能力线，零依赖，只用 Python 标准库。

---

## 为什么值得用

日更团队最耗时间的从来不是「会不会写提示词」：

- **不知道一天 10 条怎么排** —— 哪几条先配音、哪几条等人物图、配乐和卡点谁先谁后；
- **不知道一条要花多少** —— 出到第 6 条才发现口播秒数把预算吃完了；
- **出完一堆 `output-1.mp4`** —— 分发时一集一集对号，10 条能花掉一晚上；
- **验收靠眼睛** —— 封面尺寸、字幕编码、体积上限，全靠人翻文件属性。

本包把这四件事做成了命令：`plan` 排产、`cost` 报价、`run`/`batch` 出片、`check` 验收。

---

## 价目表（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工位 | 走哪条线 | 单价 | 一条 45 秒 / 350 字 |
|---|---|---|---|
| 旁白配音 | `voice_tts/tts_async` | 0.18 点/字（上游实际点数 ×3） | 63 点 |
| 数字人口播 | `pic_lipsync/submit`（mode=text） | **15 点/秒**（上游 3 点/秒 ×5） | 675 点 |
| 配乐 | `media_services_33/music_generate` | 60 点/条（未配价，按预冻口径） | 60 点 |
| 卡点字幕 | `media_services_33/music_timestamped_lyrics` | 60 点/条 | 60 点 |
| 封面 / 片头 | 本地截帧 或 `full_video/submit` | 0 点 / 480P 14 · 768P 28 · 1080P 60 · 2K 80 · 4K 80 点/秒 | 0 点 |
| **合计** | | | **858 点 = 8.58 元** |

一天 10 条 = **8,580 点 = 85.80 元**。五种走法（`cost` 全打出来）：

| 走法 | 一天 10 条 |
|---|---|
| 全配（默认） | 8,580 点 = 85.80 元 |
| 只口播（配音/配乐/卡点复用现成素材） | 6,750 点 = 67.50 元 |
| 口播 30 秒（其余同默认） | 6,330 点 = 63.30 元 |
| 封面走 full_video 480P 4 秒 | 9,140 点 = 91.40 元 |
| 加一条 15 秒 1080P 预告片 | 17,580 点 = 175.80 元 |

---

## 三条实测干货

### 1. 口播 15 点/秒是全条 79% 的成本，秒数是唯一的大杠杆

一条 858 点里 675 点是数字人口播。45 秒砍到 30 秒，一天 10 条省 **2,250 点（22.50 元）**；
砍到 24 秒省 3,150 点。先把每条的时长定死，再谈别的优化 ——
配音 + 配乐 + 卡点三个工位合起来只有 183 点，改它们省不出钱。

### 2. `media_services_33` 的 29 个接口，一条都没配价

这个应用（ElevenLabs 配音 / `music_generate` 配乐 / `music_timestamped_lyrics` 时间戳）
在 `GET /api/v1/pricing` 里**一条规则都没有**，每次调用按默认预冻 60 点。
实测 4 条流水：`music_generate` / `music_extend` / `music_sounds` /
`music_timestamped_lyrics` 各 `reserve_sync` 冻 60、`refund:sync` 退 60。
所以配乐与卡点按 **60 点/条** 入账 —— 它是按条计费的接口，多跑一条就是 60 点。

### 3. 应用层 `query` 按次计费，本包只走 `GET /tasks/{id}`

`nano_banana/query` 实测每次扣 **72 点**，轮询一次就是一张图的钱。
所以 `status` 只打免费的 `GET /api/v1/tasks/{task_id}`，一次应用层 query 都不发。
`doctor` 同理：只发 7 个免费请求（4 个只读 GET + 空表单上传 + 余额复采），
**一次 `list_voices` 都不碰**（文档写「免费」，实测每次先冻 150 点再全额退）。

---

## 交付清单（一条 5 件必交 + 1 件选交）

| 工位 | 说明 | 必交 | 规格 | 命名 |
|---|---|---|---|---|
| `avatar` | 口播成片 | 是 | 1080×1920，≤200 MB | `SD_S01E03_avatar_1080x1920_v01.mp4` |
| `voice` | 旁白音轨 | 是 | mp3，≤20 MB | `SD_S01E03_voice_v01.mp3` |
| `music` | 配乐 | 是 | mp3，≤20 MB | `SD_S01E03_music_v01.mp3` |
| `beat` | 卡点字幕 | 是 | SRT / UTF-8，≤2 MB | `SD_S01E03_beat_v01.srt` |
| `cover` | 封面 | 是 | 1080×1920，≤2 MB | `SD_S01E03_cover_1080x1920_v01.jpg` |
| `promo` | 预告片 | 选 | 1080×1920，≤200 MB | `SD_S01E03_promo_1080x1920_v01.mp4` |

一天 10 条 = **50 件必交 + 10 件选交**。
命名规范：`<项目>_S<季两位>E<集两位>_<工位>_<规格>_v<版本两位>.<扩展名>`。

---

## 完整链路

```
plan（免费，本地）
  └─ 排产单 plan.json + slate.md：10 条 × 8 工位 × 5 段分镜 × 60 个文件名 × 点数

一条：voice 63 点 → avatar 675 点 → music 60 点 → beat 60 点 → cover 0 点 → check 免费
batch：同一条流水线 × N 条，闸门在整批开始前就卡住
```

| 工位 | 你给什么 | 拿到什么 |
|---|---|---|
| `voice` | 文案 | 旁白 mp3 |
| `avatar` | 人物图 + 参考音色 + 文案 | 数字人口播 mp4（mode=text 一次成） |
| `music` | 配乐提示词 + 秒数 | `task_id` + `audio_id`（下一站要这两个） |
| `beat` | 上一站的 `task_id` + `audio_id` | 字级时间轴（SRT） |
| `cover` | 本地截帧 0 点；要动态片头加 `--cover 480P` | 封面 jpg / 片头 mp4 |

```bash
# 0) 免费：8 工位 + 单价 + 一条/一天总账
python3 scripts/run.py catalog

# 1) 免费：先算钱（一条、一天、五种走法）
python3 scripts/run.py cost --episodes 10 --seconds 45 --chars 350

# 2) 免费：自检（7 个免费请求，含「余额前后一致 = 本轮 0 点」）
python3 scripts/run.py doctor

# 3) 免费：出排产单
python3 scripts/run.py plan --project SD --episodes 10 --write --outdir ./out

# 4) 出片：先上传素材（免费），再跑一条
python3 scripts/run.py upload --file 人物图.jpg
python3 scripts/run.py run --plan ./out/plan.json --ep S01E03 --step avatar \
  --image-url "https://oss.gpu.likeadmin.cn/openapi/..." \
  --voice-ref "https://oss.gpu.likeadmin.cn/openapi/..." \
  --text "她扫了三年地，转身在董事会上叫出了所有人的名字" --yes

# 5) 出片：跑一天
python3 scripts/run.py batch --plan ./out/plan.json --episodes 1-10 --yes

# 6) 免费：交付清单验收
python3 scripts/run.py check --dir ./out --plan ./out/plan.json
```

任何付费命令加 `--dry-run`，端点、body、点数逐条打出来，不提交。

---

## 三步上手

```bash
python3 scripts/a7w.py login --key sk-你的key    # 1) 填 Key（不内嵌，用你自己的）
python3 scripts/run.py doctor                    # 2) 自检，0 点
python3 scripts/run.py plan --project SD --episodes 10 --write --outdir ./out
```

---

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 8 工位 + 4 条能力线 + 单价 + 一条/一天总账 |
| `cost` | 免费 | 算钱：一条、一天、五种走法对照 |
| `plan` | 免费 | 出排产单：钩子 + 5 段分镜 + 8 工位 + 60 个文件名 + 点数 |
| `doctor` | 免费 | 7 个免费请求自检，证明本轮 0 点 |
| `upload` | 免费 | 本地素材传平台，拿 `oss.gpu.likeadmin.cn` 白名单地址 |
| `check` | 免费 | 交付清单验收：齐不齐 / 命名 / 封面像素 / 体积 / SRT 编码 |
| `run` | **按工位计价**（一条全跑 858 点） | 跑一条：`--step voice\|avatar\|music\|beat\|cover` 或 `--all` |
| `batch` | **×条数** | 跑一天：`--episodes all\|1-10\|1,3,5`，可 `--keep-going` |
| `status` | 免费 | 查任务（只走 `GET /api/v1/tasks/{id}`） |
| `log` | 免费 | 本地台账（`~/.a7w/shortdrama-mass-ledger.json`） |

两道闸门：缺 `--yes` 退 **4** 并告诉你要花多少点；预计超 `--budget` 退 **5**，一个请求都不发。
`--budget` 单位是「点」，默认 10000 = 100 元。

---

## 和同赛道三个包的分工

能力包做「单步调通一个接口」，本包做「一个岗位一天要交的东西」：

| | 能力包（`a7w-*` / `sanjianke-*`） | 本包 |
|---|---|---|
| 形态 | 单步：一次提交、一次查询、一次落盘 | 排产 → 出片 → 交付 → 验收，一天 10 条打成一单 |
| 入口 | 每个包只认自己的端点与参数 | 一张 `plan.json` 管 10 条 × 8 工位 |
| 交付物 | 一条任务的结果 | 50 件必交文件 + 命名规范 + 交付清单 |
| 谁在用 | 工程师调接口、验价格 | 制片 / 编导 / 运营排产、验收、对账 |

| 你要什么 | 用哪个 |
|---|---|
| 一条 60 秒素材做二创（去台标 → 擦硬字幕 → 提画质 → 换解说 → 套模板） | `sanjianke-shortdrama-remix` |
| 一张图 + 一段文案，出一张口播 | `sanjianke-digital-host` |
| 一张图 + 一段文字，全流程出一条成片（含字级字幕与 AI 封面） | `avatar-autoclip` |
| 一天 10 条的排产、命名、批量出片、交付验收 | **本包** |

---

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | Python 3.7+，只用标准库，`pip install` 一个都不用 |
| 能力线 | `voice_tts/tts_async` · `pic_lipsync/submit`（mode=text）· `media_services_33/music_generate` · `media_services_33/music_timestamped_lyrics` · `full_video/submit` · `POST /api/v1/upload` |
| 轮询 | 只走 `GET /api/v1/tasks/{task_id}`；应用层 `query` 按次计费，本包一次都不发 |
| 计费口径 | 配音上游 ×3、口播上游 ×5、media33 未配价按 60 点/条、full_video 按分辨率 14–80 点/秒、上传 0 点 |
| 退出码 | `0` 成功 / `2` 用法错 / `3` 自检或验收没过 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 前后都能写，stdout 只有一个 JSON：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}` |
| Key | `--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`；本包不内嵌任何 Key |

## 文档

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 完整说明：8 工位、交付清单、分工、闸门、退出码 |
| `references/api-contract.md` | 4 条能力线的接口原文与计费口径（实测） |
| `references/troubleshooting.md` | 按报错找原因 |

---

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
