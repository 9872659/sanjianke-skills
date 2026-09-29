# 三剪客 · 播客全自动生产

给一个**主题**，一条链路产出一期**可发布的播客**：

```
outline   →   script   →   voice    →   music      →   mix
选题 + 提纲    双人对话稿    分角色配音    片头/转场/片尾     mp3 + 章节标记
（文本）       （文本）     （两个音色）   （纯器乐配乐）     + 时间轴（本地 ffmpeg）
```

面向播客、有声内容创作者。**跑之前先告诉你花多少钱**，配错了包不给你发出去。

```
outline →  选题 + 提纲（标题 / 角度 / 受众 / 章节 / 片头钩子 / 片尾收束）
script  →  双人对话稿（角色标注 + 交替发言 + 语气 + 逐章字数配额）
voices  →  现查可用音色，拿配音要的 reference_id（免费）
voice   →  分角色配音，两个音色，先报价，断点续跑
music   →  片头 / 转场 / 片尾配乐
mix     →  本地拼成 mp3 + 章节标记 + 时间轴（零网络零成本）
all     →  串起全流程，断点续跑
cost    →  只算钱，一次调用都不发
models  →  列出在架模型
```

## 30 秒上手

```bash
# 1) 拿 Key（新用户有赠送点数）
#    到 https://api.a7w.cn/ 注册，创建一个 API Key

# 2) 配 Key
export A7W_API_KEY="<你的Key>"          # Windows: $env:A7W_API_KEY="<你的Key>"

# 3) 选题与提纲
python3 scripts/run.py outline --topic "AI 剪辑到底省了谁的时间" --minutes 8 \
        --outdir D:/podcast/ep01

# 4) 双人对话稿
python3 scripts/run.py script --outdir D:/podcast/ep01

# 5) 看音色，整条复制 reference_id（32 位十六进制，抄短了会失败）
python3 scripts/run.py voices

# 6) 配音：先不带 --yes 报价，确认了再加
python3 scripts/run.py voice --outdir D:/podcast/ep01 \
        --voice-a <音色A> --voice-b <音色B>
python3 scripts/run.py voice --outdir D:/podcast/ep01 --yes

# 7) 配乐
python3 scripts/run.py music --outdir D:/podcast/ep01 --cues intro,bed,outro --budget 200

# 8) 本地混音
python3 scripts/run.py mix --outdir D:/podcast/ep01

# 9) 想一条命令跑完
python3 scripts/run.py all --topic "AI 剪辑到底省了谁的时间" --minutes 30 \
        --outdir D:/podcast/ep01 --budget 600
```

**零依赖**：只要 Python 3.7+，不用 `pip install` 任何东西。
`mix` 需要本机有 `ffmpeg`；没有的话它会把拼接清单与章节文件写完，
然后**明确报错退出**（`exit=2`），而不是假装成功（见「缺 ffmpeg 时会怎样」）。

`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端（我们靠 SHA256 校验各包副本
是否一致），本包**逐字节没有改它**；本包的业务逻辑全在 `scripts/run.py` 里。

## 六道硬闸门

命中即**标红 + stderr 汇总 + 退出码非 0**，可以直接进 CI。

| # | 闸门 | 判定 | 退出码 |
|---|---|---|---|
| 1 | 合规 | 广告法违禁词 + 播客口播红线；「最X」按可枚举语境豁免 | 3 |
| 2 | 占位符残留 | `{}`、`[待填]`、`XXX`、`此处省略`、`TODO` | 3 |
| 3 | prompt_echo | 去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60 | 3 |
| 4 | **对话稿结构** | **恰好两个角色标注 + 交替发言** | 3 |
| 5 | 时长估算 | 按字数估时长，偏离目标超过 ±25% | 3 |
| 6 | 成本上限 | 跑前必须报价 + `--yes` 或 `--budget` | 2 / 5 |

外加一条产出位置闸门：`--outdir` 指到包内直接 `exit=2`
（包内不许出现音频，SkillHub 的扩展名白名单只放 `.md .py .txt .json .sh .js .yaml .yml .csv`）。

### 第 4 道闸门为什么是本包最值钱的那道

一份**单角色**的稿子：字数对、时长对、合规干净、读起来也顺——
它在任何一道常规检查里都是合格的，但它配出来只是朗读，不是播客。

这道闸门不采信模型自报的结构字段，而是用正则去读**渲染后的成品稿**：

```
**主持人**（平稳）：...
**嘉宾**（追问）：...
```

读不出两个角色标注、或出现"没有角色标注的发言行"，一律拦。

## 实测数据（真机跑出来的，不是估算）

| 项目 | 实测值 |
|---|---|
| 提纲（8 分钟一期） | 1211 token，约 5 秒 |
| 对话稿（8 分钟一期） | 4367 token，63 句，两个角色，相邻同角色占比 **0.032**，约 15 秒 |
| 配音单价 | **50 点/千字**，21 / 24 / 46 / 52 / 57 字五组样本逐条线性，**无最低消费** |
| 配音样本 | 200 字 = **10.0 点**（≈ 0.10 元） |
| 配乐单价 | `music_generation/create` = **65 点/次**（≈ 0.65 元）；歌词 12 点/次 |
| 混音 | 887 KB mp3，55.36 秒，一条章节标记 + 逐段时间轴 |
| 断点续跑 | 5 段配音全部跳过，**0 次调用、0.0 秒、0 点**（台词与音色都没变时；配音断点按「台词 + 角色」判定，台词一改就会重配重扣） |
| 30 分钟一期口径 | 7950 字 ≈ 398 点配音 + 195 点配乐 ≈ **5.93 元** |

结算只认 `usage.points_cost`。平台的 `pricing_matrix` / `tenant_*` 字段半数不可信，
本包不拿它们算钱；文本大模型的单价平台不公开，`cost` 不给 `--points-per-ktok`
就**只报 token 数、不报金额**——不编单价。

## 两条实测确认的接口事实

```bash
python3 scripts/a7w.py schema voice_tts          # 配音的真实参数
python3 scripts/a7w.py schema music_generation   # 配乐的真实参数
```

1. **配音的音色参数叫 `reference_id`，不叫 `voice_id`**。值是 `list_voices` 返回的
   `id` / `model_id`，**32 位十六进制，抄短一位就得到 `code=0 任务处理失败`**。
2. **配乐的创建动作叫 `create`，不叫 `generate`**。接口里没有 `generate`；
   它只是 `create` 的 `type` 参数的一个取值。

另外：

- `/chat/completions` 的**成功响应不带 `code`**；生成应用**`code == 1` 才是成功**。
- 异步任务的 **`status` 在任务 `data` 顶层**，不在 `data.result` 里（平台文档写错了）。
  实测原文：`data.status = 'completed'`、`data.result.status = None`。

## 产出目录长这样

```
D:/podcast/ep01/
├── outline.json / outline.md      选题与提纲
├── script.json  / script.md       双人对话稿（成品稿，闸门读的就是它）
├── voice/                         分角色配音片段 + index.json
├── music/                         片头 / 转场 / 片尾配乐
├── podcast-state.json             断点文件（重跑不重复扣费；配音按「台词 + 角色」判定，改台词会重配重扣）
├── episode.mp3                    **成片**
├── chapters.txt / chapters.json   章节标记（FFmpeg metadata 格式）
├── timeline.md / playlist.txt     时间轴与拼接清单
└── .mix/                          归一化后的 wav 中间件（可整目录删掉）
```

音频一律落在**包外**的 `--outdir` 里。

## 缺 ffmpeg 时会怎样

`mix` 会写出 `playlist.txt`、`chapters.txt`、`mix-commands.txt`（都是文本），
**但不产出 mp3**，并以 `exit=2` 明确报错。

装上 ffmpeg 后**原样重跑同一条命令即可**——断点续跑：台词与配乐提示词没变就不会重复扣配音 / 配乐的钱（台词一改就要重配重扣）。
ffmpeg 不一定要在 PATH 上：`--ffmpeg <路径>` 或环境变量 `FFMPEG` 都行。

## 长什么样（对话稿片段）

```markdown
## 第 1 章　省时间的承诺从哪来

> 本章主线：先拆开"AI剪辑省时间"这句话，看它默认比较的是哪两步。

**主持人**（平稳开场）：如果你用 AI 剪过片，可能发现总时间没少，甚至更累。这期我们把省下的时间和新增的时间一笔笔摊开。

**嘉宾**（认真）：对，很多人一上来就问"AI 剪辑能省多少时间"，但这个问题本身就有个陷阱……

**主持人**（追问）：所以省掉的是机械操作那一段，不是判断和决策？

**嘉宾**（解释）：没错。AI 帮你把素材按时间线拼起来、切掉明显废片，这确实是体力活……
```

配音时**同章节内、同角色的连续台词会合并成一块**（≤500 字，同步接口的建议上限）：
实测无最低消费，合并不会多花钱，但能把调用次数从几百次压到几十次。

## 文档

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 完整说明：能力、命令、参数、排错、已知取舍 |
| `references/podcast-script-method.md` | 对话稿方法与时长 / 字数换算 |
| `references/voice-and-music.md` | 音色挑选、配音参数与配乐档位 |
| `references/cost-and-troubleshooting.md` | 实测单价、报价口径与排错手册 |

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
