# 选曲与音色：两条选曲路线、音色挑选与配音参数

本文件是 `pick` / `voice` / `voices` 三个子命令的方法论底稿。

---

## 一、选曲的两条路线

### 路线 A：`music_search` 在线搜索（**按次扣点**）

先 schema 现查，别照抄记忆：

```bash
python3 scripts/a7w.py schema music_search
```

实测到的真实接口（`app 列表` 里就有这个 app，21 个插件之一）：

```
POST /api/v1/apps/music_search/search          ← 同步，只有一个接口
  入参：keyword   歌曲名 / 歌手名 / 专辑关键词
        page      页码，从 1 开始
        page_size 每页条数，**最大 20**
```

实测返回（原文，已截断长 URL）：

```json
{"code": 1, "msg": "success",
 "data": {
   "result": {
     "items": [{"type": "music", "songid": "5257138", "title": "屋顶",
                "author": "周杰伦,温岚,吴宗宪",
                "pic": "http://p2.music.126.net/.../109951165671182684.jpg?param=300x300",
                "link": "https://music.163.com/#/song?id=5257138",
                "url": "http://m801.music.126.net/.../....mp3?vuutv=..."}],
     "page": 1, "page_size": 3, "has_more": true},
   "usage": {"points_cost": 10, "actual_points": 10}}}
```

四条要点：

1. **它按次扣点，实测 10 点/次**，而且**与 `page_size` 无关**（`page_size` 取 2 和 3
   都是 10 点）。所以 `--page-size` 调大不额外花钱，但每多搜一首歌就多一次调用。
2. **`usage` 在 `data` 里，不在 `data.result` 里**。结算只认 `usage.points_cost`
   （本包 `points_of()` 会把 `usage` / `data.usage` / `result.usage` 三个位置都试一遍）。
3. `items[].url` 是**可直接下载的 mp3 地址**；`link` 是人看的网页地址；
   `has_more` 指示还有没有下一页。
4. 搜索结果来自流媒体源。本包**默认只存元信息，不落盘音频**（`--download` 才下）。
   播出 / 商用请自行确认授权——本包只负责挑与排。

### 路线 B：`--from-file` 本地歌单（**离线，不花钱**）

三种格式，按后缀分流：

```
# playlist.txt —— 每行一首（`#` 开头是注释；行首序号会被吃掉）
真夜中のドア - 松原みき
Plastic Love — 竹内まりや
Ride on Time
```

```csv
曲目,歌手
真夜中のドア,松原みき
Plastic Love,竹内まりや
```

```json
{"tracks": [{"title": "真夜中のドア", "artist": "松原みき"}]}
```

`pick` 会在歌单文件同目录与 `<outdir>/songs/` 里找同名音频
（`歌名.mp3` / `歌名 - 歌手.mp3` / `NNN-歌名.mp3`）。

**什么时候该用路线 B**：你已经确认过授权、或者只想把手上这批音频排成节目。
它零成本、零网络、结果完全可预测。

---

## 二、选曲的打分与"近似匹配"

搜索路线里，每首歌的挑选是**打分制**（`_match_score`）：

```
歌名完全相同              +0.6
歌名互相包含              +0.4
歌名二元组相似度          +0.6 × Jaccard
歌手互相包含              +0.4
歌手相似度                +0.4 × Jaccard
没给歌手                  +0.2
```

- 打分 **≥ 0.75** 就认为"够像了"，不再多花一次调用（`--tries 2` 时才会再搜一轮）
- 打分 **< 0.55** 的条目会在产出里标 `approx: true`，并在 stderr 明确提示
  "**近似匹配，请人工复核**"——不静默把一首不对的歌放进节目单

搜索结果一条都没命中时，那一首**跳过且不占位**（不塞一首凑数的进去）。

---

## 三、音色：先查，再整条复制

```bash
python3 scripts/run.py voices
```

输出里 `reference_id` **整条打印，不截断**。这不是格式化偏好，是被实测咬过的：

> 同族包的第一版按 `%-28s` 截断显示，实测时照着屏幕抄了前 28 位，
> 结果 tts 返回 `code=0 任务处理失败`。列表里唯一要"抄下来用"的字段被截断，
> 是那一版最蠢的一个 bug。真正的 id 是 **32 位十六进制**
> （例：`0705a04a4c3f4b65b888d2aa7a4e6b08`）。

**报 `code=0 任务处理失败` 时的排查顺序**：

1. 去掉 `--voice` 再跑一次。不指定音色用平台默认音色，能成功就说明是音色 ID 的问题。
2. 用 `run.py voices` 重新整条复制。
3. 仍失败就看文本：空文本、纯符号、超长单句都可能触发。

`list_voices` 的参数（schema 原文）：`tag` 按标签筛、`title` 按名称搜、
`sort_by` 支持 `score / task_count / created_at`、`language` 按语言筛、
`page_size`（官方默认 10）、`page_number`、`title_language`。

---

## 四、配音参数

```bash
python3 scripts/a7w.py schema voice_tts
```

本包用到的三个：

| 参数 | 说明 |
|---|---|
| `text` | 待合成文本。**同步接口建议不超过 500 字符**（schema 原文） |
| `model` | TTS 模型：`s1` / `s2-pro`，默认 `s2-pro` |
| `format` | `wav / pcm / mp3 / opus`，默认 `mp3` |
| `prosody` | 语调对象：`speed`、`volume`、`normalize_loudness`（仅 s2-pro） |
| `reference_id` | **音色模型 ID**。单说话人传 string；多说话人可传 string[]（仅 s2-pro） |

**它叫 `reference_id`，不叫 `voice_id`。** 这是本包 schema 现查确认的第一条。

### 分块策略：为什么按"串词段"切，而不是整篇一段

电台的形态是 **说一句 → 放一首 → 再说一句**。整篇合成一段音频，
根本插不进歌与歌之间。所以 `draft_voice_chunks()`：

1. **按串词段切**（开场 / 过渡 i / 结尾各是独立音频文件）
2. 段内超过 500 字，再按句末标点（`。！？；` 与换行）拆块
3. 单句超过 500 字（少见）硬切
4. 单块超过 5000 字才切到异步端点 `tts_async`（异步支持约 10000 字符）

文件命名 `NNN-段落名.mp3`（例 `001-开场.mp3`、`003-过渡_1.mp3`），
`voice/index.json` 里记着每一段的段落名、字数、扣点、是否来自断点续跑。

### 断点 key 里为什么有五个维度

配音的断点 key = `{正文, reference_id, 语速, 模型, 格式}` 的哈希。

**手挑字段的错法永远是"漏了某个维度"**，而漏掉的后果是**静默复用旧产物**——
本库同族实测踩过两次：

- 内容截断（`--sample-chars` 试跑的短音频）不入 key → 被当成完整产物复用
- `resolution` 不入 key → 改了档位却拿到旧档位的图

所以本包的口径是：**把真正要发出去的请求体整体入 key**，而不是挑几个字段。
代价是"改了台词或换了音色就会重配重扣"——这是刻意选择的错法方向：
多花一次钱看得见，复用错产物看不见。

---

## 五、垫乐（`music`）

```bash
python3 scripts/a7w.py schema music_generation
```

两条实测事实：

1. **创建动作叫 `create`，不叫 `generate`**。接口清单里没有 `generate`；
   `generate` 只是 `create` 的 `type` 参数的一个取值。
2. **`create` 的参数表里没有时长参数**。垫乐多长由上游决定，
   所以长度控制在 `mix` 阶段做：`--bed-seconds` 循环铺多久、`--bed-volume` 压到多低。

`music` 单独成一个子命令（而不是让 `mix` 顺手生成）的理由是成本边界：
`create` 是**异步 + 65 点/次**的付费调用，而 `mix` 是零成本的本地步骤。
把付费调用塞进零成本步骤里，会让"我只是想重新拼一次"变成"又花了 65 点"。
