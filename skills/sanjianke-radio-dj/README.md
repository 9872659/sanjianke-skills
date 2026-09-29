# 三剪客 · AI 电台 / 歌单串词

给一个**主题**或一份**歌单**，一条链路产出一期**可播出的电台节目**：

```
plan    →   script   →   voice    →   pick        →   mix
节目单      串词稿       主持人口播      选曲（搜索 / 歌单）   串词 + 歌曲拼接
选曲顺序    开场+过渡N   先报价          本地 or 在线          节目单 + 时间轴
+ 串词意图  + 结尾       断点续跑        实测 10 点/次         （本地 ffmpeg）
```

面向音乐电台、歌单号、店铺背景音。**跑之前先告诉你花多少钱**，稿子不合格不给你录。

```
plan    →  节目单：选曲顺序 + 每段串词的意图（开场 / 过渡 / 结尾）
script  →  写串词：开场 + 每首前的过渡 + 结尾（三段结构缺一不可）
voice   →  串词配音（先报价，断点续跑，已完成的片段不重复扣费）
pick    →  选曲：music_search 搜索，或 --from-file 读本地歌单（离线不花钱）
music   →  垫乐：music_generation/create（异步，先报价）
mix     →  串词 + 歌曲拼接 + 节目单 / 时间轴（本地 ffmpeg，零成本）
all     →  串起全流程，断点续跑
cost    →  只算钱，一次调用都不发
voices  →  现查可用音色，拿配音要的 reference_id（免费）
models  →  现查在架模型 + 本包用到的 app 的真实接口
```

## 30 秒上手

```bash
# 1) 拿 Key（新用户有赠送点数）
#    到 https://api.a7w.cn/ 注册，创建一个 API Key

# 2) 配 Key
export A7W_API_KEY="<你的Key>"          # Windows: $env:A7W_API_KEY="<你的Key>"

# 3) 节目单（不给 --songs 就按目标时长自动推荐曲目数）
python3 scripts/run.py plan --topic "深夜开车听的 City Pop" --minutes 30 \
        --mode "深夜陪伴" --outdir D:/radio/ep01

# 4) 串词
python3 scripts/run.py script --outdir D:/radio/ep01

# 5) 选曲：本地歌单（离线不花钱）或在线搜索（10 点/次）
python3 scripts/run.py pick --outdir D:/radio/ep01 --from-file D:/radio/playlist.txt
# 想让模型在曲库里自己挑：
python3 scripts/run.py pick --outdir D:/radio/ep01 --budget 100

# 6) 配音：先不带 --yes 报价，确认了再加
python3 scripts/run.py voice --outdir D:/radio/ep01
python3 scripts/run.py voice --outdir D:/radio/ep01 --yes

# 7) 本地拼接（需要 ffmpeg）
python3 scripts/run.py mix --outdir D:/radio/ep01

# 8) 想一条命令跑完
python3 scripts/run.py all --topic "深夜开车听的 City Pop" --minutes 30 \
        --outdir D:/radio/ep01 --budget 600
```

**零依赖**：只要 Python 3.7+，不用 `pip install` 任何东西。
`mix` 需要本机有 `ffmpeg`；没有的话它会把节目单与拼接清单写完，
然后**明确报错退出**（`exit=2`），而不是假装成功（见「缺 ffmpeg 时会怎样」）。

`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端（我们靠 SHA256 校验各包副本
是否一致），本包**逐字节没有改它**；本包的业务逻辑全在 `scripts/run.py` 里。

## 六道硬闸门

命中即**标红 + stderr 汇总 + 退出码非 0**，可以直接进 CI。

| # | 闸门 | 判定 | 退出码 |
|---|---|---|---|
| 1 | 合规 | 广告法违禁词 + 口播红线；「最X」按可枚举语境豁免，句首不豁免 | 3 |
| 2 | 占位符残留 | `{}`、`[待填]`、`XXX`、`此处省略`、`TODO` | 3 |
| 3 | prompt_echo | 去标点相等 / Jaccard ≥ 0.75 / 覆盖度 ≥ 0.60 + 相对长度守卫 | 3 |
| 4 | **串词结构** | **开场 + 每首前的过渡（条数 = 歌曲数）+ 结尾，缺一不可** | 3 |
| 5 | 时长台账 | 串词时长 + 歌曲时长合计，偏离目标超过 ±25% | 3 |
| 6 | 成本上限 | 跑前必须报价 + `--yes` 或 `--budget` | 2 / 5 |

外加一条产出位置闸门：`--outdir` 指到包内直接 `exit=2`
（包内不许出现音频，SkillHub 的扩展名白名单只放 `.md .py .txt .json .sh .js .yaml .yml .csv`）。

### 第 4 道闸门为什么是本包最值钱的那道

一份**只有歌单**的稿子：字数对、时长对、合规干净、读起来也顺——
它在任何一道常规检查里都是合格的，但它配出来只是"报幕"，不是电台节目。

这道闸门不采信模型自报的结构字段，而是用正则去读**渲染后的成品稿**：

```
## 【开场】
## 【过渡 1】
## 【过渡 2】
## 【结尾】
```

读不出开场 / 读不出结尾 / 过渡条数不等于歌曲数，一律拦。
**少了哪一条过渡，就意味着有一首歌是硬切进去的。**

## 实测数据（真机跑出来的，不是估算）

| 项目 | 实测值 |
|---|---|
| 节目单（30 分钟 / 4 首） | 1840 token，约 7 秒 |
| 串词（30 分钟 / 4 首） | 2026~3619 token，2499~3226 字，开场 + 4 条过渡 + 结尾，约 20 秒 |
| 配音单价 | **50 点/千字**，278 / 318 / 496 字三组样本逐条吻合（13.9 / 15.9 / 24.8 点） |
| 选曲单价 | **10 点/次**，与 `page_size` 无关（page_size 2 与 3 都是 10 点） |
| 配乐单价 | `music_generation/create` = **65 点/次**；歌词 12 点/次 |
| 混音 | 17.5 MB mp3，18:16，1 条开场 + 4 首歌，5 条章节标记 + 逐段时间轴 |
| 断点续跑 | 同一请求重跑：跳过 1 个片段，**0 次调用、0 点**（台词/音色/语速任一变化都会重配重扣） |
| 30 分钟一期口径 | 5 首（190 秒/首）≈ 20 分钟音乐 + 约 1900 字串词 ≈ 95 点配音 |

结算只认 `usage.points_cost`。平台的 `pricing_matrix` / `tenant_*` 字段半数不可信，
本包不拿它们算钱；文本大模型的单价平台不公开，`cost` 不给 `--points-per-ktok`
就**只报 token 数、不报金额**——不编单价。

## 三条实测确认的接口事实

```bash
python3 scripts/a7w.py schema voice_tts          # 配音的真实参数
python3 scripts/a7w.py schema music_generation   # 配乐的真实参数
python3 scripts/a7w.py schema music_search       # 选曲的真实参数
```

1. **配音的音色参数叫 `reference_id`，不叫 `voice_id`**。值是 `list_voices` 返回的
   `id` / `model_id`，**32 位十六进制，抄短一位就得到 `code=0 任务处理失败`**。
2. **配乐的创建动作叫 `create`，不叫 `generate`**。接口里没有 `generate`；
   它只是 `create` 的 `type` 参数的一个取值。`create` 的参数表里**没有时长参数**。
3. **`music_search` 这个 app 是真实存在的**（任务书里让我现查确认）：
   `POST /api/v1/apps/music_search/search`，一个同步接口，
   入参 `{keyword, page, page_size≤20}`，返回 `data.result.items[]`，
   每项含 `title / author / url / link / pic / songid`，`url` 可直接下载。
   **它按次扣点（实测 10 点/次），不是免费接口。**

另外：

- `/chat/completions` 的**成功响应不带 `code`**；生成应用**`code == 1` 才是成功**。
- 异步任务的 **`status` 在任务 `data` 顶层**，不在 `data.result` 里（平台文档写错了）。
  实测原文：`data.status = 'completed'`、`data.result.status = None`。

## 产出目录长这样

```
D:/radio/ep01/
├── plan.json / plan.md            节目单（曲目 + 每段串词的意图）
├── script.json / script.md        串词稿（成品稿，闸门读的就是它）
├── playlist.json / program-list.txt  选曲结果与排播用的节目单
├── voice/                         串词配音片段 + index.json
├── music/bed.mp3                  垫乐（可选）
├── songs/                         本地音频（--download 或手工放）
├── radio-state.json               断点文件（重跑不重复扣费）
├── program.mp3                    **成片**
├── chapters.txt / chapters.json   章节标记（每首歌一条）
├── timeline.md / playlist.txt     时间轴与拼接清单
└── .mix/                          归一化后的 wav 中间件（可整目录删掉）
```

音频一律落在**包外**的 `--outdir` 里。

## 缺 ffmpeg 时会怎样

`mix` 会写出 `playlist.txt`、`chapters.txt`、`program-list.txt`、`mix-commands.txt`
（都是文本），**但不产出 mp3**，并以 `exit=2` 明确报错。

装上 ffmpeg 后**原样重跑同一条命令即可**——断点续跑：台词与风格提示词没变就不会
重复扣配音 / 选曲 / 配乐的钱。ffmpeg 不一定要在 PATH 上：
`--ffmpeg <路径>` 或环境变量 `FFMPEG` 都行。

## 长什么样（串词片段）

```markdown
## 【开场】

把灯调暗一点。仪表盘那点微光就够了。前面路灯一段一段掠过去，
车窗外的城市只剩轮廓……这一期，是给不想立刻到家的人听的。

## 【过渡 1】

刚上高架那几分钟，速度还没稳下来，车里安静得有点空。
这种时候需要一点霓虹感，把这份安静先填满。竹内玛莉亚的《Plastic Love》。
它是入口，不是这一期的全部，你听下去就知道。

## 【结尾】

好。灯可以关了。这一期，就是一段夜路的完整闭环……
```

配音时**按串词段切块**（开场 / 过渡 i / 结尾各是独立音频）：
这样才插得进歌与歌之间。段内超过同步上限（500 字）再按句末标点拆。

## 文档

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 完整说明：能力、命令、参数、排错、已知取舍 |
| `references/radio-script-method.md` | 串词方法与时长 / 字数换算、三段结构的写法 |
| `references/pick-and-voice.md` | 选曲路线、音色挑选与配音参数 |
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
