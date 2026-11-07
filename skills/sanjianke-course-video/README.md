# 10 章课程口播课件 · 每章 60 秒 6 元起

**一份大纲 `.md` → 一整套讲师口播课件。** 10 章 × 60 秒 = **6,000 点（60 元）**（课件图 fast 档 + 配音约 490 点）。

走 [api.a7w.cn](https://api.a7w.cn/) 的三个应用：`voice_tts` 配音、`image_human` 出章节视频、`pic_lipsync` 出一图口播。零依赖，只用 Python 标准库。

---

## 三个真会花错钱的坑，都做成了默认动作

### 坑一：`image_human` 省略 `mode`，出片和收钱会走两个档

| 来源 | 字段 | 值 |
|---|---|---|
| `params_schema.mode.default` | 出片档位 | `standard` |
| `/api/v1/pricing` 的 `defaultModel` | 计费档位 | `fast` |

省略 `mode` 时：**出片按 standard、收钱按 fast**（15 点/秒 vs 10 点/秒）。
所以本包 `slide --mode` 是**必填参数**，永不下发省略 mode 的请求。

### 坑二：`pic_lipsync` 的档位参数叫 `quality`，不叫 `mode`

`mode` 只切 `audio` / `text`，档位真名是 `quality`（`standard` / `fast` / `max`）。
`mode=text` 省掉的是录音，**参考音色省不掉** —— `audio_url` 仍然必填，给 3–10 秒单人清晰人声。

### 坑三：应用层 `/query` 一次就是一次的钱

历史流水：`nano_banana/query` **72 点/次**，108 次 = **7,776 点**。
本包在 `http_json()` 里拦掉任何以 `/query` 结尾的地址，轮询只走 **GET `/api/v1/tasks/{id}`**（只读、免费）。

`doctor` 同理：只发 4 个只读 GET，**一个 submit 都不发**。实测应用层 submit 是「先冻结、再验参、失败再退」，连缺必填的请求都会产生 `-250 / +250` 一对流水；`voice_tts/list_voices` 这种看着免费的，也是每次 `-150 / +150`。

---

## 价目（1 元 = 100 点，2026-11-07 现查 `/api/v1/pricing`）

| 环节 | 端点 | 单价 | 10 章 × 60 秒 |
|---|---|---|---|
| 讲稿 / 进度清单 | 本地 `plan` | 0 点 | 0 点 |
| 分节配音 | `voice_tts/tts_async` | 0.18 点/字（上游实际 ×3） | 约 490 点（4.90 元） |
| 课件图出片 | `image_human/submit` | **fast 10 / standard 15 / 2k 30 / 4k 60** 点/输入秒 | **6,000 / 9,000 / 18,000 / 36,000 点** |
| 一图口播 | `pic_lipsync/submit` | 15 点/秒（上游实际 ×5） | 9,000 点（90 元） |
| 章节拼接 | 本地 `stitch` | 0 点 | 0 点 |

- `image_human` 按**输入音频秒数**计费，带上 `duration` 价格才被费率卡锁死，预算能算到个位
- 配音 `0.18 点/字` 来自实测：`tts_live` 33 字 → 上游 1.98 点 → 我方 5.94 点
- `pic_lipsync` 计费卡是「上游实际点数 ×5」，上游实测固定 3 点/秒 ⇒ 对外 15 点/秒
- 真跑以后一律以返回里的 `usage.points_cost` 为准

---

## 完整链路

```
outline.md ──plan──► course.json（讲稿 + 进度）             0 点
                        │
                        ├─voice──► 每章配音 mp3（tts_async）   0.18 点/字
                        │             │
                        │             ▼
                        └─────slide──► 每章成片（image_human） 10–60 点/输入秒
                                      │
                                      ▼
                                   stitch ──► ffconcat 清单 + ffmpeg 一条命令   0 点
```

大纲格式（`plan` 就认这三样）：

```markdown
# 课程名

## 第一章 先认识这个平台

- 要点一
- 要点二
```

---

## 三步上手

```bash
# 0) Key（三选一）
export A7W_API_KEY=sk-你的key          # 或 python3 scripts/a7w.py login --key sk-...

# 1) 自检（免费）：4 个只读 GET，一个 submit 都不发
python3 scripts/run.py doctor

# 2) 大纲 → 讲稿 + 进度清单（免费，本地）
python3 scripts/run.py plan --outline course-outline.md -o course.json

# 3) 先算钱，再出片
python3 scripts/run.py cost --chapters 10 --seconds 60 --route slide --mode fast
python3 scripts/run.py voice --course course.json --limit 2 --yes
python3 scripts/run.py slide --course course.json --image slide.png --mode fast --yes
python3 scripts/run.py stitch --course course.json
```

---

## 常用命令

```bash
# 5 段链路 + 三条路线价目一览
python3 scripts/run.py catalog

# 只跑第 3、4 章（断点续跑）
python3 scripts/run.py voice --course course.json --only 3,4 --yes

# 给 duration 留 10% 余量，避免平台探测时长比你自己算的长
python3 scripts/run.py slide --course course.json --image slide.png --mode standard --pad 10 --yes

# 一图 + 参考音色 + 文案，直接出口播（不需要先配音）
python3 scripts/run.py mouth --image teacher.png --voice-ref voice.mp3 \
    --content "这一节讲三个概念…" --quality standard --yes

# 只看请求体，不花钱
python3 scripts/run.py slide --course course.json --image slide.png --mode fast --dry-run

# 查任务（免费）
python3 scripts/run.py status --task-id task_xxx

# 本地台账
python3 scripts/run.py log
```

**缺 `--yes` 退 `4`**，并告诉你这次要花多少点；**预计点数超过 `--budget` 退 `5`，一个请求都不发**。

---

## 和 sanjianke-digital-host / avatar-autoclip 的分工

| | 本包 `sanjianke-course-video` | `sanjianke-digital-host` | `avatar-autoclip` |
|---|---|---|---|
| 交付物 | 一套课：N 段章节成片 + 拼接清单 | 一段口播视频（一个镜头） | 一条竖屏成品短视频 |
| 输入 | 一份大纲 `.md`（多章多节） | 一张图 + 一段话/音频 | 一张参考图 + 一段文案 |
| 强项 | 章节、进度、断点续跑、逐章对账 | 三条口播路线一次讲透，单价最清楚 | 字幕、封面、模板、智能剪辑一条龙 |
| 计费 | 逐章预算，`course.json` 记每章实际点数 | 单次 15 点/秒 或 10–60 点/输入秒 | 全链路叠加 |
| 什么时候用它 | 要交一套分章节课件 | 只要一个口播镜头 | 要一条能直接发的短视频 |

一句话选法：**要「一套课」用本包；要「一个镜头」用 digital-host；要「一条短视频成片」用 avatar-autoclip。**

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 5 段链路 + 三条路线价目对照 |
| `cost` | 免费 | 按章节数 × 每章秒数算钱 |
| `doctor` | 免费 | 自检 Key / 三条链路已配价 / 速率卡 / 查询线 / 余额 |
| `plan` | 免费 | 大纲 → 讲稿 + `course.json` 进度清单 |
| `voice` | **0.18 点/字** | 分节口播配音（要 `--yes`） |
| `slide` | **10–60 点/输入秒** | 课件图 → 章节视频（`--mode` 必填） |
| `mouth` | **15 点/秒** | 一图 + 参考音色 + 文案 → 口播 |
| `stitch` | 免费 | 章节拼接清单 + 进度回看 |
| `status` | 免费 | 查任务 `GET /api/v1/tasks/{id}` |
| `log` | 免费 | 本地台账 |

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget` | 5000 | **单位是点**（1 元 = 100 点），超了退 5 且不发请求 |
| `--yes` | — | 缺了退 4，并告诉你这次要花多少 |
| `--mode` | 必填（`slide`） | `fast` / `standard` / `2k` / `4k` |
| `--quality` | `standard` | `mouth` 的档位：`standard` / `fast` / `max` |
| `--limit` | 全部 | 本次最多跑几章 |
| `--only` | — | 只跑这几章，比如 `3,4` |
| `--pad` | 0 | 给 `duration` 留余量（百分比，建议 10） |
| `--upload` | — | 本地课件图先传平台临时地址（上传不计费） |
| `--dry-run` | — | 打印请求体与预估点数，不提交 |
| `--json` | — | stdout 只有一个 JSON 文档 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺参数、选项缩写、大纲没章节） |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 自检没过 / 任务失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "cmd": "slide", "course": "course.json", "chapters": 10,
 "mode": "fast", "estimatedPoints": 6000, "billedPoints": 5987.5,
 "elapsed": 812.4, "results": [{"index": 1, "taskId": "task_xxx", "status": "completed"}]}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档，进度全部走 stderr。

---

## 进度清单 `course.json`

```json
{"title": "三剪客 API 入门课", "route": "slide", "mode": "fast",
 "chapters": [{"index": 1, "title": "第一章 …", "script": "这是《…》第 1 章，…",
               "chars": 143, "seconds": 31.8, "status": "video",
               "audioUrl": "https://…/tts_xxx.mp3",
               "videoUrl": "https://…/chapter-01.mp4", "spentPoints": 318.0}]}
```

`status` 依次是 `planned` → `audio` → `video`。每跑完一章就落盘一次，断了重跑同一条命令会跳过已完成的章。

---

## 文件结构

```
sanjianke-course-video/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       三个应用的参数、单价、实测原文
│   └── troubleshooting.md    按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 实测记录（2026-11-07，本轮 0 点）

```
自检（全程免费：4 个只读 GET，一个 submit 都不发）

  √ Key 有效 + 应用目录可达              HTTP 200 success · 22 个应用
  √ 三条链路都已在网关配价               定价表 115 条，命中 3/3 条链路
  √ 速率卡一致（10/15/30/60 点/输入秒）  live={"fast":10,"standard":15,"2k":30,"4k":60} · defaultModel=fast
  √ 口播口径一致（上游实际点数 ×5）      markupPercent=400 · minPoints=50（声明字段）
  √ 轮询线 GET /api/v1/tasks/{id} 可用   HTTP 200 任务不存在
```

`GET /user/balance/logs` 前后对比：最新一条流水时间不变、总条数不变、可用点数不变。

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
