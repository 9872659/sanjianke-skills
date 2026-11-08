# 口播矩阵 · 一段文案 × N 个形象 × M 个音色

**3 个形象 × 4 个音色 = 12 条口播，一条命令跑完，约 2,564 点（25.64 元）。**
走 [api.a7w.cn](https://api.a7w.cn/) 的三个应用：`voice_tts` 配音、`pic_lipsync` 图片数字人、`image_human` 全驱数字人。

矩阵里最值钱的算术：**配音只做 M 次，视频才做 N × M 次。** 同一段文案、同一个音色，音频合成一次就够所有形象复用。

---

## 矩阵的算术（60 字 ≈ 14 秒）

```
配音   0.18 点/字 × 60 字 × 4 音色        =    44 点
视频   15 点/秒 × 14 秒 × 12 条            = 2,520 点
------------------------------------------------------
合计                                       = 2,564 点 = 25.64 元
```

同一段文案换规模：

| 形象 × 音色 | 成片 | 点数 | 元 |
|---|---|---|---|
| 1 × 1 | 1 条 | 221 | 2.21 |
| 2 × 2 | 4 条 | 862 | 8.62 |
| **3 × 4** | **12 条** | **2,564** | **25.64** |
| 5 × 6 | 30 条 | 6,366 | 63.66 |
| 10 × 10 | 100 条 | 21,110 | 211.10 |

`cost` 会把配音、视频、合计三行拆开给你看，配音那一行永远是「× 音色数」，永远不乘形象数。

---

## 三个真会花错钱的地方，都做成了默认动作

### 一、把配音也乘上形象数，一笔预算直接多算 N 倍

12 条视频不等于 12 次配音。本包 `cost` 与 `run` 都按「音色数」算配音，并在 state 里缓存
每个音色的 `audio_url`，重跑直接复用。

### 二、用应用层 `/query` 轮询 —— 每调一次就是一次的钱

```
✅ GET  /api/v1/tasks/<task_id>      0 点/次，唯一合法轮询线
❌ POST /api/v1/apps/<app>/query     每调一次就是一次的钱
```

实测 `nano_banana/query` 72 点/次，历史上有 15,552 点烧在这条路上。本包代码里没有 query 这条路，
`doctor` 也只发四个只读 GET。

### 三、付费提交重试 —— 5xx 时任务可能已经建好，重发就是再扣一次

所以重试只放在**免费**的两个环节：`POST /upload` 与 `GET /tasks/<id>`。
付费 `submit` 只发一次；网络中断的条目在 state 里记成 `unknown`，用 `status` 对账，
确认网关那边没有任务再重跑。

---

## 价格（`GET /api/v1/pricing` 现查，1 元 = 100 点）

| 环节 | 接口 | 单价 |
|---|---|---|
| 配音 | `voice_tts/tts` | **0.18 点/字**|
| 视频 · lipsync | `pic_lipsync/submit` | **15 点/秒**|
| 视频 · human | `image_human/submit` | **10 / 15 / 30 / 60 点/输入秒**（fast / standard / 2k / 4k）|
| 上传 | `POST /api/v1/upload` | **0 点**（24 小时有效）|
| 轮询 | `GET /api/v1/tasks/<id>` | **0 点** |
| 建专属音色 | `voice_tts/clone_voice` | 600 点/次 |
| 音色库 | `voice_tts/list_voices` | 净 0（先冻 150 点、随即全额退）|

`image_human` 的 `mode` 必须显式给：schema 默认 `standard`、计费卡默认 `fast`，
漏传就是「出片按标准、收钱按快速」。本包把 `--mode` 做成 `--engine human` 的必填项。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检（只有只读 GET，一个 POST 都不发）
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --images 3 --voices 4 --chars 60     # 2,564 点

# 4) 试水一条
python3 scripts/run.py run --workdir ./matrix \
    --images face_a.png --voices model_xxx --content "你的文案" --limit 1 --yes

# 5) 全量（自动跳过刚做完那条，配音也不再付第二次钱）
python3 scripts/run.py run --workdir ./matrix \
    --images face_a.png --images face_b.png --images face_c.png \
    --voices model_xxx --voices model_yyy --voices model_zzz --voices model_www \
    --content "你的文案" --concurrency 3 --yes
```

不加 `--yes` 退 `4`，并直接告诉你这次要花多少点；超过 `--budget` 退 `5`，**一个请求都不发**。

---

## `run` 内部做了什么

```
文案(≤500字) --voice_tts/tts × M--> M 段 audio_url（每音色一次）
形象图 × N   --POST /upload-------> N 个平台地址（0 点）
                    │
       N × M 笛卡尔积 --submit----> 每条一个 task_id（并发 --concurrency）
                    │
        GET /tasks/<id> ----------> 状态 / 成片 / 实扣点数（0 点）
                    │
   {prefix}_{序号}-{形象}_{音色}.mp4 落盘（--outdir，默认 = --workdir）
                    │
        matrix-state.json --------> 断点续跑：重跑只补没跑完的
```

- **上传先做**：上传 0 点，形象图不齐就停在这一步，不进付费环节。
- **配音第二**：每个音色一次，失败即停，已配好的写进 state。
- **提交第三**：付费，每条只发一次，`--concurrency` 控制同时压几条。
- **轮询第四**：免费，只走 `/tasks/<id>`，`--interval` 默认 8 秒。
- **落盘第五**：按规范名保存，重跑覆盖同一位置，不会堆一堆 `xxx(1).mp4`。

---

## 断点续跑与命名规范

`--workdir` 下有一个 `matrix-state.json`，记着每个形象的上传地址、每个音色的音频地址、
每条 combo 的 `task_id` / `status` / `videoUrl` / `file` / 点数。

- 重跑 `run`：已完成的不再提交，配音直接复用，只补没跑完的。
- 换了文案：文案指纹进了 state 的 key，旧音频不会被误用，整批按新文案重算。
- 文件名：`{prefix}_{形象序号}-{形象名}_{音色}.{ext}`，例如
  `talking_01-face_a-model_xxx.mp4` —— 可预测、可排序、可直接对比。

---

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 两个引擎、价目、规模预算一屏对照 |
| `cost --images 3 --voices 4 --chars 60` | 免费 | 先算钱 |
| `doctor` | 免费 | 六项自检（四个只读 GET）|
| `voices --yes` | 净 0（先冻 150 点再退）| 列音色库拿 `reference_id` |
| `tts --voices a b --content "…"` | 约 0.18 点/字 × 音色数 | 只配音 |
| `run --dry-run` | 免费 | 打印每一步请求 |
| `run --yes` | 见价目表 | 全链路 |
| `status --workdir ./matrix` | 免费 | 整张矩阵对账 |
| `status --task-id task_xxx` | 免费 | 查单条 |
| `log` | 免费 | 本地台账 |

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--images` | 必填 | 本地路径或 http(s) 地址，可重复 |
| `--voices` | 必填 | 音色 `reference_id`，可重复 |
| `--audio` | — | 已有音频地址：跳过配音直接做矩阵 |
| `--content` / `--content-file` | 必填 | 文案，同步配音上限 500 字 |
| `--engine` | `lipsync` | `lipsync`（pic_lipsync）/ `human`（image_human）|
| `--quality` | `standard` | lipsync 档位 `standard` / `fast` / `max` |
| `--mode` | — | human 档位 `fast` / `standard` / `2k` / `4k`（human 必填）|
| `--seconds` | 按字数推算 | 4.5 字/秒；human 建议直接给 |
| `--concurrency` | 2 | 同时提交/轮询几条 |
| `--limit` | — | 先只做前 N 条试水 |
| `--workdir` | `.` | state 与成片目录 |
| `--prefix` | `talking` | 成片文件名前缀 |
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点）|
| `--yes` | — | 确认真实扣费 |
| `--dry-run` | — | 只打印请求，不提交 |

---

## 退出码与 `--json`

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺参数、超 500 字、human 漏 `--mode`、选项缩写）|
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 有 `unknown` 待对账 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断（已完成的都在 state 里）|

```json
{"ok": true, "engine": "lipsync", "images": 3, "voices": 4, "videos": 12,
 "submitted": 12, "completed": 12, "failed": 0, "unknown": 0,
 "estimatedPoints": 2564, "billedPoints": 2564.0,
 "points": [{"combo": "face_a__model_xxx-da9593", "status": "completed", "taskId": "task_xxx",
             "points": 210.0, "videoUrl": "https://…/a.mp4", "file": "./matrix/talking_01-face_a_model_xxx.mp4"}],
 "files": ["./matrix/talking_01-face_a_model_xxx.mp4"],
 "statePath": "./matrix/matrix-state.json"}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-talking-matrix/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文 + live 定价）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 和 sanjianke-digital-host 的分工

| 你要什么 | 用哪个 |
|---|---|
| 一条片子、一个形象、一个音色，最快出片 | `sanjianke-digital-host talk` |
| 一段文案出 N 形象 × M 音色，批量对比 | **本包 `run`** |
| 已有录音，图 + 音频全驱动（单条） | `digital-host drive` |
| 同上，但要批量 | **本包 `--engine human`** |
| 已有视频换口型 | `digital-host dub` |
| 并发控制、命名规范、断点续跑 | **本包**（`digital-host` 不做这些）|
| 只要配音、不要视频 | `sanjianke-audiobook-line narrate` |

---

## 实测记录（2026-11-07）

```
POST /api/v1/apps/voice_tts/tts   33 字  上游 1.98 点 -> 我方 5.94 点（0.18 点/字）
GET  /api/v1/pricing              115 条规则，pic_lipsync ×5 / image_human 四档 / voice_tts ×3
GET  /api/v1/apps                 22 个应用，本包用其中 3 个
GET  /api/v1/apps/voice_tts/list_voices   total=58（这条会先冻 150 点再全额退）
```

---

## 已知限制

1. **同步配音上限 500 字**（`voice_tts/tts`）；更长的文案请拆段，每段各自跑矩阵。
2. **`image_human` 的价格与 `duration` 绑定**：不给秒数就按上游冻结点算，估不准，所以 human 引擎要求 `--seconds`。
3. **`lipsync` 的成片地址有效期以网关为准**，跑完请及时 `--save` 落盘。
4. **state 是按目录记的**：同一 `--workdir` 换文案会按新指纹重算，旧成片仍留在目录里。
5. **并发默认 2**：网关对同一 Key 的连接数敏感，压太高容易触发 502，调大前先小批量试。

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
