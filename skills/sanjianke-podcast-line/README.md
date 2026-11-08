# 播客生产线 · 3 条请求出一期成品播客
**3 条请求、下限 180 点（1.80 元），把一份文稿变成一期能上架的播客 —— 配音、配乐、逐句字幕、章节目录。**

走 [api.a7w.cn](https://api.a7w.cn/) 的 Official 音频与辅助服务（应用代号 `media_services_33`），
本包接通其中最能打的三条：ElevenLabs 多语言 V2（配音）、Suno 音乐（配乐）、带时间戳歌词（字幕），
外加一个纯本地的章节拼装。异步提交 + 自动轮询，零依赖。

---

## 一期播客是怎么被 3 条请求拼出来的

```
python3 scripts/run.py vo --script ep01.md --voice eR40ATw9ArzDf9h3v7t7 --yes
#   #1  task_id=task_3e35...  （7200 字 → 切成 2 片，2 条请求）
#       audio_id：audio_xxxxxxxx  ← subs 要用它
#       音频：https://…/vo-01.mp3

python3 scripts/run.py bgm --prompt "lo-fi 钢琴，温暖，无人声" --style "lo-fi piano, warm" --duration 180 --yes
#   #1  task_id=task_9a1c...  ← 配乐任务，subs 要用它
#       音频：https://…/bgm.mp3

python3 scripts/run.py subs --task-id task_9a1c... --audio-id audio_xxxxxxxx --srt-out ep01.srt --yes
python3 scripts/run.py chapters --script ep01.md --srt ep01.srt --out ep01.chapters.txt
#   00:00 第 1 章 开场：为什么现在做播客
#   04:12 第 2 章 一段文稿怎么变成声音
#   11:38 第 3 章 配乐怎么选
```

两个小时的人工活，压到 **3 条请求 + 1 条本地命令**。`chapters` 花 0 点。

---

## 价目表

| 零件 | 子命令 | 接口 | 一条请求下限 | 一条给你什么 |
|---|---|---|---|---|
| **配音** | `vo` | `elevenlabs_text_to_speech_multilingual_v2` | 60 点 | 一条人声，5000 字以内，67 个音色 |
| **配乐** | `bgm` | `music_generate` | 60 点 | 一条 10–360 秒的片头 / 垫乐 / 转场 |
| **字幕** | `subs` | `music_timestamped_lyrics` | 60 点 | 逐句时间轴，顺手落一份 SRT |
| **章节** | `chapters` | 本地算 | **0 点** | `00:00 第 1 章 …` 章节块 |

**1 元 = 100 点**，所以：

| 一期节目 | 请求数 | 下限 | 折合 |
|---|---|---|---|
| 20 分钟口播（≈5000 字）+ 垫乐 + 字幕 | 3 | 180 点 | 1.80 元 |
| 30 分钟口播（≈7200 字，切 2 片）+ 垫乐 + 字幕 | 4 | 240 点 | 2.40 元 |
| 60 分钟长节目（≈14000 字，切 4 片）+ 垫乐 + 字幕 | 6 | 360 点 | 3.60 元 |
| 只要声音、已有现成 BGM | 1–4 | 60 点 × 片数 | 0.60 元 × 片数 |

价格口径**如实写**：`/api/v1/pricing` 共 115 条规则，**没有 `media_services_33` 的专属条目**，落通配：

```json
```

实测每次 POST 先 `reserve_sync` **预冻结 60 点**、失败全额退，所以 `cost` 给的是**下限估算**；

```bash
python3 scripts/run.py cost                        # 最少一次请求 → 60 点（0.60 元）
python3 scripts/run.py cost --script ep01.md --bgm --subs
python3 scripts/run.py cost --chars 12000 --bgm --subs
python3 scripts/run.py cost --script ep01.md --upstream 65   # 按你观察到的上游点数换算
```

---

## 三条干货（别人不一定会说的）

**1. 5000 字是 ElevenLabs 通道的单条硬上限，`vo` 会自动按句子切片。**
7000 字长稿 = 2 条请求、2 个 `task_id`、2 段音频；断点落在句号处，不会切在半句话上。
切片宽度用 `--chunk-chars` 调（默认 4500，留 10% 余量），`--no-split` 可以整篇一次交。

**2. 音色填 ID，不填名字。**
67 个 ID 全内置（`catalog --voices`，每个都带中文性格：电台主持人 / 有声书旁白 / 低沉共鸣…）。
给名字会被当场退 `2` 并提示最接近的 ID —— 本包不替用户猜，猜错会真的提交一条任务、真的冻结点数。

**3. 章节是免费的，而且可以反复重算。**
`chapters` 把文稿里的 `## 第 N 章` 按**正文累计字数**比例对到字幕时间轴：字幕改了、配音重录了，
重跑一次就有新章节，0 点。标题本身不算字数（标题不会被念出来），这条是踩过的坑。

---

## 三步上手

```bash
# 1) 自检（全只读 GET，0 点）：Key、余额、三条接口在架、通配价目、查询路由
python3 scripts/run.py doctor

# 2) 先看价（纯本地算术，0 点）：按你的文稿字数算要几条、下限多少点
python3 scripts/run.py cost --script ep01.md --bgm --subs

# 3) 出配音
python3 scripts/run.py vo --script ep01.md --voice eR40ATw9ArzDf9h3v7t7 --yes
```

两道闸门：缺 `--yes` 退 `4` 并写明下限多少点；预计超 `--budget` 退 `5`，**一个请求都不发**。
`--budget` 单位是**点**（1 元 = 100 点），默认 500。

---

## 常用命令

```bash
# 三件免费的先跑一遍
python3 scripts/run.py catalog                    # 三条接口 + 8 个播客常用音色 + 价格口径
python3 scripts/run.py catalog --voices           # 67 个音色 ID + 中文性格
python3 scripts/run.py doctor --probe             # 三条端点参数校验（冻 60 全退，净 0）

# 配音：长稿自动切片 / 只提交不等 / 顺手下载
python3 scripts/run.py vo --script ep01.md --voice x70vRnQBMBu4FAYhjJbO --yes
python3 scripts/run.py vo --script ep01.md --voice x70vRnQBMBu4FAYhjJbO --no-wait --manifest vo.json
python3 scripts/run.py vo --text "这一期聊聊播客。" --voice 8JVbfL6oEdmuxKn5DK2C --out ./podcast --yes

# 配乐：一句话 / 自定义风格 / 要人声 / 指定时长
python3 scripts/run.py bgm --prompt "lo-fi 钢琴，温暖，无人声" --duration 180 --yes
python3 scripts/run.py bgm --custom --style "city pop" --title "片头" --duration 30 --yes
python3 scripts/run.py bgm --custom --style "folk" --lyrics "[主歌]…" --vocal --yes

# 字幕 / 章节
python3 scripts/run.py subs --task-id task_9a1c... --audio-id audio_xxxxxxxx --srt-out ep01.srt --yes
python3 scripts/run.py chapters --script ep01.md --subs subs.json
python3 scripts/run.py chapters --script ep01.md --srt ep01.srt --out ep01.chapters.txt

# 免费续查 / 下载 / 台账
python3 scripts/run.py task --task-id task_xxx --out ./podcast
python3 scripts/run.py log

# 只看请求，不花钱
python3 scripts/run.py vo --script ep01.md --voice 6F5Zhi321D3Oq7v1oNT4 --dry-run
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--voice` | — | **必填**，67 个音色 ID 之一，`catalog --voices` 看全部 |
| `--script` | — | 文稿路径（`vo` 会自动切片；`cost` / `chapters` 也吃它） |
| `--text` | — | 直接给要配音的文本（≤5000 字，不切片） |
| `--chunk-chars` | 4500 | 配音切片字数，上限 5000 |
| `--no-split` | — | 整篇一次提交（超过 5000 字上游会拒） |
| `--speed` / `--style` / `--stability` / `--similarity` | — | 语速 0.7–1.2 / 风格 0–1 / 稳定性 0–1 / 相似度 0–1 |
| `--timestamps` | — | 让上游回逐词时间戳 |
| `--model` | `V6` | `V6` / `V6_MINI` / `V6_WILD` / `V5_5` / `V5` / `V4_5ALL` / `V4_5PLUS` / `V4_5` / `V4` |
| `--prompt` / `--style` / `--lyrics` | — | 配乐描述 / 风格标签 / 歌词，至少给一项 |
| `--custom` | — | 自定义模式（配 `--style` / `--lyrics` / `--title`，`--title` 必填） |
| `--vocal` | — | 要人声（默认纯音乐垫乐） |
| `--duration` | — | 配乐目标时长 10–360 秒 |
| `--task-id` / `--audio-id` | — | `subs` 必填，都来自配乐任务的返回 |
| `--srt-out` | — | `subs` 顺手把逐句时间轴落成 SRT |
| `--out` | — | 章节块输出文件（`chapters`）/ 音频下载目录（付费子命令） |
| `--budget` | 500 | 点数上限，**单位是点**（1 元 = 100 点） |
| `--upstream` | 0 | 你观察到的上游点数（`cost` 用它换算成交价） |
| `--yes` / `--dry-run` | — | 确认真实计费 / 只打印请求 |
| `--no-wait` | — | 只提交，拿 `task_id` 就走 |
| `--manifest` | — | 把 `task_id` 清单落盘，断了接着取 |

---

## 子命令

| 子命令 | 计费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 三条接口 + 67 个音色 + 价格口径 |
| `cost` | 免费 | 按文稿字数算下限（纯本地算术） |
| `doctor` | 免费 | 自检 Key / 余额 / 三条接口 / 价目 / 查询路由 |
| `chapters` | 免费 | 文稿章节 × 字幕时间轴 → 章节块（纯本地） |
| `vo` | 60 点/条起 | 配音，长稿自动切片 |
| `bgm` | 60 点/条起 | 配乐（片头 / 垫乐 / 转场） |
| `subs` | 60 点/条起 | 逐句时间轴，可落 SRT |
| `task` | 免费 | 查状态 / 补取结果 / 下载 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、音色 ID 不对、数值越界） |
| `3` | `doctor` 有检查项没过 |
| `4` | 没有 `--yes` |
| `5` | 预计超 `--budget`，**一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 轮询超时 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "line": "vo", "api": "elevenlabs_text_to_speech_multilingual_v2",
 "requestCount": 2, "estimatedPoints": 120, "isLowerBound": true,
 "tasks": [{"index": 1, "task_id": "task_xxx", "status": "completed",
            "audios": [{"audio_id": "audio_xxx", "audio_url": "https://…"}]}],
 "manifest": [{"index": 1, "task_id": "task_xxx", "chars": 4500}]}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-podcast-line/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md      三条接口的 schema 原文 + 实测返回
│   └── troubleshooting.md   按报错找原因
└── scripts/
    ├── a7w.py               零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py               本包命令层
```

---

## 排错速查

| 你看到的 | 原因 | 怎么办 |
|---|---|---|
| `input.text: 缺少必填参数` | 没给文稿 | 加 `--text` 或 `--script` |
| `input.voice: 不在允许选项内` | 填了名字不是 ID | `catalog --voices` 复制 67 个 ID 之一 |
| `input.custom_mode: 缺少必填参数` | 配乐少必填项 | 本包自动补 `model` / `custom_mode` / `instrumental` |
| `input.task_id: 缺少必填参数` | `subs` 缺参数 | `--task-id` + `--audio-id` 都要给 |
| `任务处理失败，请稍后重试` | 上游生成失败 | 失败任务全额退，按原参数重跑一次 |
| `任务不存在` | `task_id` 写错或已过期 | 用 `log` 里的 `task_id` |
| 闸门退 `4` | 少 `--yes` | 确认下限点数后加 `--yes` |
| 闸门退 `5` | 超 `--budget` | 调大 `--budget`（单位：点）或减少片数 |

接口原文见 `references/api-contract.md`，按报错找原因见 `references/troubleshooting.md`。

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
