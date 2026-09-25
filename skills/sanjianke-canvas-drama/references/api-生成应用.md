# API · 生成应用速查

出图、出视频、配音、数字人、音乐、超分、混剪 —— 这些「生成应用」的接口速查。
**每个应用的完整参数用 `python3 scripts/a7w.py schema <应用代号>` 现查**，本文是索引与必填项。

---

## 一、通用规则（五条，违反任意一条都会白跑）

| # | 规则 |
|---|---|
| 1 | **路径统一是 `POST /api/v1/apps/<应用代号>/<接口代号>`**。两个代号都取自平台返回的 `code` 字段 |
| 2 | ⚠️ **绝不要用平台返回的 `endpoint_path` 字段去拼 URL** —— 它的形态不统一（有的是另一套路由族，有的是相对路径，有的已含前缀），按它拼会打不通 |
| 3 | **`code == 1` 才是成功**（`{"code":1,"msg":"success"}`）。**HTTP 200 不代表业务成功** —— 失败时也可能返回 200 且 `code` 为 `0` |
| 4 | **素材一律用公网可访问的 URL**，不支持本地路径、不支持 Base64 |
| 5 | **应用代号用下划线，不用连字符**：`nano_banana`、`voice_tts`、`full_video` |

```bash
# 一把 Key 能用的全部应用（含接口数）
python3 scripts/a7w.py apps
# 某个应用的接口与参数
python3 scripts/a7w.py schema nano_banana
```

### 1.1 异步任务生命周期

```
提交 → pending → processing → completed
                        └──→ failed / cancelled
```

```bash
# 提交（客户端自动轮询到结束）
python3 scripts/a7w.py call <应用> <接口> --body '{...}'

# 只提交不等
python3 scripts/a7w.py call <应用> <接口> --body '{...}' --no-wait

# 查任务（免费）
python3 scripts/a7w.py task <task_id>
# 或 GET /api/v1/tasks/{task_id}
```

- **提交时会预冻结点数**，完成后按实际用量多退少补；**失败全额退回**
- **不要重复提交** —— 网络超时先按 `task_id` 查，确认真失败了再重提
- 不想轮询就传 `callback_url`，任务终态时平台会 POST 通知你；回调是「至少一次」语义，消费端要按 `task_id` 幂等

### 1.2 应用清单（21 个）

| 应用代号 | 平台名称 | 本文档位置 |
|---|---|---|
| `nano_banana` | nano-banana（图像） | §2 |
| `full_video` | 全能视频生成 | §3 |
| `happy_horse` | Happy Horse | §3 |
| `seedance` | Seedance 2.0 | §3 |
| `wan` | Wan 视频生成 | §3 |
| `grok_video` | Grok 视频生成 | §3 |
| `image_human` | 全驱动数字人 | §4 |
| `pic_lipsync` | 图片数字人 | §4 |
| `lipsync` | 数字人对口型 | §4 |
| `voice_tts` | 语音 TTS | §5 |
| `seedsvc` | 音色修改、AI 翻唱 | §5 |
| `music_generation` | 音乐生成 | §6 |
| `music_search` | 音乐搜索 | §6 |
| `mmaudio` | 音效生成、视频配音 | §6 |
| `flashvsr` | 视频超分 | §7 |
| `smart_clip` | 智能剪辑 | §7 |
| `action_transfer` | 动作迁移 | §7 |
| `person_replacement` | 人物替换 | §7 |
| `dressing_diffusion` | AI 换装 | §7 |
| `watermark_removal` | 水印消除 | §7 |
| `file_qa` | 文件问答 | §8 |

---

## 二、图像 · `nano_banana`

| 接口 | 路径 | 模式 | 计费 |
|---|---|---|---|
| `submit` | `POST /api/v1/apps/nano_banana/submit` | 异步 | 按模型与分辨率档，点/张 |
| `query` | `GET /api/v1/apps/nano_banana/query?task_id=…` | 同步 | **免费** |

**必填**：`prompt`
**常用可选**：`action`（`generate` 文生图 / `edit` 图生图）、`image_urls`（`edit` 时必填）、
`model`、`resolution`（`1K` / `2K` / `4K`）、`aspect_ratio`、`callback_url`

```bash
# 文生图（定妆图、场景空镜图）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"prompt":"25 岁中国女性，齐肩黑色短发，正面半身像，影棚均匀柔光，纯中性灰背景，写实电影感","resolution":"1K","aspect_ratio":"9:16"}' \
  --out chars/LIN-face.png

# 图生图（锁角色出首帧，最常用的一个）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"edit","prompt":"保持人物长相与发型不变，改为：雨夜街头，撑着黑伞站在路灯下，中景，冷色调","resolution":"1K","aspect_ratio":"9:16","image_urls":["https://你的存储/chars/LIN-face.png"]}' \
  --out shots/S01-002.png
```

**硬约束**：普通模型只吃 `1K`，传 `2K`/`4K` 会报「未命中可用计费规格」；
要高清请换 `:official` 高清模型。模型与档位现查：

```bash
python3 scripts/a7w.py schema nano_banana
```

---

## 三、视频 · 五个应用

### 3.1 怎么选（一分钟决策）

```
都不确定                        → full_video（通用首选）
要声音画面一起出                → happy_horse
要按分辨率分档 + 素材管理        → seedance
要多参考素材（图/音/视频）混用    → wan
只要快                          → grok_video
静态对话戏，不需要真人连续动作    → 别用视频生成，走 image_human / lipsync（见 §4）
```

### 3.2 `full_video` · 全能视频生成

| 接口 | 路径 |
|---|---|
| `submit` | `POST /api/v1/apps/full_video/submit` |
| `query` | `GET /api/v1/apps/full_video/query?task_id=…`（免费） |

**必填**：`content`（数组，**须含一项 `text`**）
**常用可选**：`ratio`、`duration`（**4~15 秒整数**）、`resolution`（`480P` / `768P` / `1080P` / `2K` / `4K`）、
`aigc_watermark`、`callback_url`

```bash
# 文生视频 / 图生视频
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"role":"first_frame","type":"image_url","image_url":{"url":"https://你的存储/shots/S01-003.png"}},{"type":"text","text":"镜头缓慢推近，人物从低头看地缓缓抬头看向路灯，雨滴打在伞面上"}],"ratio":"9:16","resolution":"720P","duration":6}' \
  --out shots/S01-003.mp4
```

**硬约束（最容易踩，记牢）**

| 约束 | 值 |
|---|---|
| `duration` | **只能是 4~15 秒的整数** |
| 首帧 / 尾帧 | **各最多 1 张** |
| 参考图片 | 最多 9 张 |
| 参考视频 / 参考音频 | **各最多 3 个** |
| 模式互斥 | **首尾帧模式不能与参考媒体模式混用** |
| 参考媒体模式 | 至少要有 1 张参考图或 1 个参考视频，**不能只传参考音频** |
| 文本长度 | 768P / 1080P / 2K 上限 5000 字符；其他分辨率上限 7000 字符 |

**计费**：按分辨率 SKU 与生成时长计量 —— **480P 10 点/秒 · 768P 20 点/秒 · 1080P/2K/4K 40 点/秒**。

### 3.3 `happy_horse`

| 接口 | 路径 |
|---|---|
| `submit` | `POST /api/v1/apps/happy_horse/submit` |
| `create` | `POST /api/v1/apps/happy_horse/create` |
| `query` | `GET /api/v1/apps/happy_horse/query?task_id=…`（免费） |

**必填**：`model`（能力代号，决定怎么用 `media`）、`prompt`、`duration`（3~15 秒整数）、`resolution`（`720P` / `1080P`）

`model` 可选值：`happyhorse-1.1-t2v`（文生）/ `happyhorse-1.1-i2v`（单图首帧）/
`happyhorse-1.1-r2v`（多参考）/ `happyhorse-1.0-video-edit`（视频编辑）

`media` 是统一参考素材数组，元素形如 `{"url":"https://…","type":"video"}`：

| `model` | `media` 怎么传 |
|---|---|
| `t2v` | 不传 |
| `i2v` | 1 张 `image` |
| `r2v` | 1~9 张 `image`（建议至少 2 张） |
| `video-edit` | 1 个 `video`，可附 0~5 张 `image` |

**计费**：720P **0.9 点/秒** · 1080P **1.6 点/秒**。

```bash
python3 scripts/a7w.py call happy_horse submit \
  --body '{"model":"happyhorse-1.1-i2v","prompt":"镜头缓慢推近，人物抬头看路灯，雨滴打在伞面上","media":[{"url":"https://你的存储/shots/S01-003.png","type":"image"}],"duration":5,"resolution":"720P","ratio":"9:16"}' \
  --out shots/S01-003.mp4
```

### 3.4 `seedance` · 带素材管理

| 接口 | 路径 | 说明 |
|---|---|---|
| `create` | `POST /api/v1/apps/seedance/create` | 创建视频任务 |
| `query` | `GET /api/v1/apps/seedance/query?task_id=…` | 查任务（免费） |
| `createGroup` | `POST /api/v1/apps/seedance/createGroup` | 建素材组 |
| `createAsset` | `POST /api/v1/apps/seedance/createAsset` | 上传素材 |
| `updateAsset` | `POST /api/v1/apps/seedance/updateAsset` | 更新素材 |
| `getAsset` | `GET /api/v1/apps/seedance/getAsset` | 查素材 |
| `deleteAsset` | `POST /api/v1/apps/seedance/deleteAsset` | 删素材 |

**必填**：`content`（多模态数组，**至少一项 `text`**）
**常用可选**：`model`、`ratio`、`duration`（4~15，或 `-1` 自动）、`resolution`（`480p` / `720p` / `1080p`）、
`generate_audio`、`watermark`、`seed`、`callback_url`

`model` 只有四个公开名称：

| 输入含视频？ | 标准版 | 快速版 |
|---|---|---|
| 否（文生 / 图生 / 首尾帧） | `seedance-2-text-2-video` | `seedance-2-fast-text-2-video` |
| 是（视频编辑 / 延长 / 参考） | `seedance-2-video-2-video` | `seedance-2-fast-video-2-video` |

`content` 的元素用 `type` + `role` 表达角色：
`role` 取 `first_frame` / `last_frame` / `reference_image` / `reference_video` / `reference_audio`；
`type` 取 `text` / `image_url` / `video_url` / `audio_url`。
**图片最多 9 张、视频最多 3 个、音频最多 3 段，且不能只传音频。**

```bash
python3 scripts/a7w.py call seedance create \
  --body '{"model":"seedance-2-text-2-video","resolution":"720p","ratio":"9:16","duration":5,"content":[{"role":"first_frame","type":"image_url","image_url":{"url":"https://你的存储/shots/S01-003.png"}},{"type":"text","text":"镜头缓慢推近，人物抬头看向路灯"}]}' \
  --out shots/S01-003.mp4
```

**计费**：按输出 tokens × 定价矩阵（点/百万 tokens），分档 `480p` 3000/5000 · `720p` 3200/5500 · `1080p` 3500/6000。

### 3.5 `wan`

| 接口 | 路径 |
|---|---|
| `create` | `POST /api/v1/apps/wan/create` |
| `query` | `GET /api/v1/apps/wan/query?task_id=…`（免费） |

**必填**：`model` + `prompt`，另按 `model` 追加：

| `model` | 场景 | 还要必填 |
|---|---|---|
| `wan2.7` | 文生视频 | — |
| `wan2.7-r2v` | 角色 / 参考图生视频 | `image_with_roles`（最多 2 张，每项含 `url` 与 `role`） |
| `wan2.7-videoedit` | 视频编辑 | `video_urls`（最多 1 段） |

**常用可选**：`resolution`（`720p` / `1080p`）、`duration`（`wan2.7`/`r2v` 2~15；`videoedit` 2~10）、
`size`（画幅）、`image_urls`、`negative_prompt`、`watermark`、`seed`、`prompt_extend`、`callback_url`

```bash
python3 scripts/a7w.py call wan create \
  --body '{"model":"wan2.7-r2v","prompt":"镜头缓慢推近，人物抬头看向路灯，雨丝斜落","image_with_roles":[{"url":"https://你的存储/chars/LIN-face.png","role":"reference_image"}],"resolution":"720p","duration":5,"size":"9:16","negative_prompt":"低清晰度、畸形、多手指、文字水印、闪烁"}' \
  --out shots/S01-003.mp4
```

### 3.6 `grok_video`

| 接口 | 路径 |
|---|---|
| `submit` | `POST /api/v1/apps/grok_video/submit` |
| `query` | `GET /api/v1/apps/grok_video/query?task_id=…`（免费） |

文生视频，有快速与标准两档。参数用 `python3 scripts/a7w.py schema grok_video` 现查。

---

## 四、数字人 · 三个应用（最容易选错）

| 应用 | 手上有什么 | 产出 | 什么时候用 |
|---|---|---|---|
| `pic_lipsync` | 一张人物图 + 音频或文案 | 口播视频 | **只要嘴动**即可 |
| `image_human` | 图片 + 参考音频 | 全驱动数字人视频 | 要**头、表情、身体一起动** |
| `lipsync` | 视频 + 音频 | 对口型后的视频 | 已有真人视频，**换口型**对齐新音轨 |

```
手上是照片  → pic_lipsync（只要嘴动）或 image_human（要自然全身动）
手上是视频  → lipsync（换口型）
```

### 4.1 `image_human` · 全驱动数字人

`POST /api/v1/apps/image_human/submit`

**必填**：`file_url`（人物图 URL）、`ref_file_url`（驱动音频 URL）
**常用可选**：`mode`（`fast` / `standard` / `2k` / `4k`）、`prompt`、`duration`

**计费按驱动音频时长计**，单价随 `mode` 档位变化（点/秒）：

| `mode` | 点/秒 | 60 秒 | 120 秒 |
|---|---|---|---|
| `fast` | 1.5 | 90 点 / 0.90 元 | 180 点 / 1.80 元 |
| `standard` | 2 | 120 点 / 1.20 元 | 240 点 / 2.40 元 |
| `2k` | 4 | 240 点 / 2.40 元 | 480 点 / 4.80 元 |
| `4k` | 8 | 480 点 / 4.80 元 | 960 点 / 9.60 元 |

> **四档价差 5.3 倍，先算钱再选档。** 发布平台会二次压缩时，
> 竖屏短剧用 `fast` 或 `standard` 就够。

```bash
python3 scripts/a7w.py call image_human submit \
  --body '{"file_url":"https://你的存储/shots/S01-002.png","ref_file_url":"https://你的存储/dub/S01-002.mp3","mode":"fast","prompt":"人物说话自然，面对镜头，肢体语言自然，人物清晰可鉴。"}' \
  --out shots/S01-002-lip.mp4
```

### 4.2 `lipsync` · 数字人对口型

`POST /api/v1/apps/lipsync/submit`

**必填**：`video_url`（数字人原始视频 URL）、`audio_url`（驱动音频 URL）
**常用可选**：`model`（`xiaojiayu1.0` / `xiaojiayu2.0` / `xiaojiayu3.0`，也可写简写 `1.0` / `2.0` / `3.0`）、`mode`、`fps`、`video_params`

```bash
python3 scripts/a7w.py call lipsync submit \
  --body '{"video_url":"https://你的存储/shots/S01-003.mp4","audio_url":"https://你的存储/dub/S01-003.mp3","model":"xiaojiayu2.0"}' \
  --out shots/S01-003-lip.mp4
```

计费以站内为准，用 `python3 scripts/a7w.py schema lipsync` 读租户价。

### 4.3 `pic_lipsync`

`POST /api/v1/apps/pic_lipsync/submit` —— 一张图 + 音频 / 文案出口播视频。
参数用 `schema pic_lipsync` 现查。

---

## 五、语音 · `voice_tts` 与 `seedsvc`

### 5.1 `voice_tts` 的六个接口

| 接口 | 路径 | 模式 | 计费 |
|---|---|---|---|
| `tts` | `POST /api/v1/apps/voice_tts/tts` | 同步（≤500 字） | 50 点 / 1k tokens |
| `tts_async` | `POST /api/v1/apps/voice_tts/tts_async` | 异步（约 1 万字内） | 同上 |
| `tts_live` | `POST /api/v1/apps/voice_tts/tts_live` | 流式 | 同上 |
| `clone_voice` | `POST /api/v1/apps/voice_tts/clone_voice` | 同步 | **200 点/次** |
| `list_voices` | `GET /api/v1/apps/voice_tts/list_voices` | 同步 | **免费** |
| `stt` | `POST /api/v1/apps/voice_tts/stt` | 同步 | 按音频时长 |

**配音必填**：`text`
**音色参数**：**`reference_id`**（值是 `clone_voice` 返回的 `model_id`）；
**注意参数名不是 `voice_id`** —— 传错会报参数不合法。

```bash
# 克隆音色（每个角色只做一次）
python3 scripts/a7w.py call voice_tts clone_voice \
  --body '{"title":"LIN-林晚-清冷","audio_url":"https://你的存储/chars/LIN-voice-ref.mp3","description":"女主，清冷，语速偏慢","enhance_audio_quality":true}'

# 查已有音色（免费）
python3 scripts/a7w.py call voice_tts list_voices --body '{"page_size":20,"page_number":1,"self":true}'

# 短句同步合成
python3 scripts/a7w.py call voice_tts tts \
  --body '{"text":"这雨，下了整整十年。","reference_id":"model_xxxxxxxxxxxx","format":"mp3","sample_rate":44100}' \
  --out dub/S01-002.mp3

# 长旁白异步合成
python3 scripts/a7w.py call voice_tts tts_async \
  --body '{"text":"<整段旁白>","reference_id":"model_xxxxxxxxxxxx"}' \
  --out dub/narration-01.mp3
```

`clone_voice` 的参考音频要求：**10 秒 ~ 5 分钟纯干声**（无 BGM、无混响、无第二人声），
格式 `mp3` / `wav` / `ogg` / `flac`，`title` **必填**。

### 5.2 `seedsvc` · 音色修改 / AI 翻唱

`POST /api/v1/apps/seedsvc/submit` —— 传入原始音频与目标音色参考，
得到换了音色的音频。参数用 `schema seedsvc` 现查。

---

## 六、音乐与音效

### 6.1 `music_generation`

| 接口 | 路径 | 用途 |
|---|---|---|
| `create` | `POST /api/v1/apps/music_generation/create` | 生成 / 续写 / 翻唱 / 分轨 / 混音（**65 点/次**起） |
| `query` | `GET /api/v1/apps/music_generation/query?task_id=…` | 查任务（免费） |
| `lyrics` | `POST /api/v1/apps/music_generation/lyrics` | 写歌词 |
| `style` | `POST /api/v1/apps/music_generation/style` | 风格建议 |
| `persona` | `POST /api/v1/apps/music_generation/persona` | 歌手 / 声音风格 ID |
| `timing` | `POST /api/v1/apps/music_generation/timing` | 歌词卡点时间轴（**免费**） |
| `voice_clone` | `POST /api/v1/apps/music_generation/voice_clone` | 歌声音色 |
| `upload_audio` | `POST /api/v1/apps/music_generation/upload_audio` | 换音频 ID |
| `vox` / `wav` / `mp4` / `midi` | 同名路径 | 人声 / 音频 / 视频 / MIDI 导出 |
| `mashup_lyrics` | `POST /api/v1/apps/music_generation/mashup_lyrics` | 混音歌词 |

**`create` 做 BGM 的关键参数**：`prompt`（**写情绪不写乐器**）、`instrumental: true`（纯伴奏）、
`type`（默认 `generate`）、`style`、`style_negative`

```bash
python3 scripts/a7w.py call music_generation create \
  --body '{"type":"generate","prompt":"情绪克制、紧张感逐渐累积的都市悬疑氛围，低音弦乐铺底，不要鼓点，不要人声","style":"cinematic tension, low strings, no drums","instrumental":true}' \
  --out music/bgm-ep01.mp3
```

`type` 价格对照（点/次）：`generate` / `extend` / `cover` / `stems` 等 **65**；
`concat` **14**；`all_stems` **230**；`replace_section` **90**。

### 6.2 `music_search`

`POST /api/v1/apps/music_search/search` —— 找现成曲子。参数用 `schema music_search` 现查。

### 6.3 `mmaudio` · 音效与环境音

`POST /api/v1/apps/mmaudio/submit` —— **0.1 点/次**，性价比最高的一步。

**必填**：`input_url`（输入视频 URL）
**常用可选**：`prompt`（音效描述）、`duration`、`audio_url`（参考音频）

```bash
python3 scripts/a7w.py call mmaudio submit \
  --body '{"input_url":"https://你的存储/shots/S01-003.mp4","prompt":"雨夜城市街道，雨打伞面，远处车流驶过，整体安静，不出现人声"}' \
  --out shots/S01-003-sfx.mp4
```

> **`mmaudio` 只做环境音与音效，不做 BGM。** 描述里明确写「不出现人声」，避免和台词打架。

---

## 七、后期 · 超分与剪辑

### 7.1 `flashvsr` · 视频超分

`POST /api/v1/apps/flashvsr/submit`

**必填**：`input_url`（待超分视频 URL）；`duration` 不传则由平台自行探测。

```bash
python3 scripts/a7w.py call flashvsr submit \
  --body '{"input_url":"https://你的存储/ep01-deliver.mp4"}' \
  --out ep01-4k.mp4
```

**计费**：固定 0.1 点 + 3 点/单位（按用量）。**只在要交付母版时做** ——
发布平台会二次压缩时，超分收益有限。

### 7.2 `smart_clip` · 智能剪辑

| 接口 | 路径 |
|---|---|
| `template` | `POST /api/v1/apps/smart_clip/template` |
| `template_detail` | `POST /api/v1/apps/smart_clip/template_detail` |
| `broadcast_mixcut` | `POST /api/v1/apps/smart_clip/broadcast_mixcut` |
| `realman_broadcast` | `POST /api/v1/apps/smart_clip/realman_broadcast` |
| `news_mixcut` | `POST /api/v1/apps/smart_clip/news_mixcut` |

**调用顺序固定：先 `template` 拿模板列表 → 再 `template_detail` 看要传什么 → 最后调对应的混剪接口。**
不要猜参数。计费约 720p **0.2 点/秒** · 1080p **0.3 点/秒**。

### 7.3 `action_transfer` / `person_replacement` / `dressing_diffusion`

| 应用 | 接口 | 用途 | 计费 |
|---|---|---|---|
| `action_transfer` | `submit` / `query` | 把一段动作搬到另一形象上 | 分档，1 / 2 / 3 点/秒 |
| `person_replacement` | `submit` / `query` | 换人 | 同动作迁移分档 |
| `dressing_diffusion` | `submit` / `query` | AI 换装（上衣 / 下装 / 全身） | `schema dressing_diffusion` 现查 |
| `watermark_removal` | `submit` / `query` | 水印消除（工具类，按次计费） | `schema watermark_removal` 现查 |

> 使用换装、动作迁移、人物替换、水印消除这类能力前，
> 请自行确认素材与肖像的授权（见 `通用说明.md` 的能力边界）。

---

## 八、文档 · `file_qa`

公网文档的问答与解析，路径按接口代号拼（如 `/api/v1/apps/file_qa/chat`、`/api/v1/apps/file_qa/parse`）。
参数用 `schema file_qa` 现查。

---

## 九、速查表：按需求找应用

| 你的需求 | 应用 · 接口 | 必填参数 |
|---|---|---|
| 出角色定妆图 / 场景图 / 首帧图 | `nano_banana` · `submit` | `prompt` |
| 用参考图锁角色出图 | `nano_banana` · `submit` | `action=edit` + `prompt` + `image_urls` |
| 出片（通用首选） | `full_video` · `submit` | `content`（含 `text`） |
| 出片（要声画一起出） | `happy_horse` · `submit` | `model` + `prompt` + `duration` + `resolution` |
| 出片（要分辨率分档 / 素材管理） | `seedance` · `create` | `content`（含 `text`） |
| 出片（多参考混用） | `wan` · `create` | `model` + `prompt`（+ `image_with_roles` / `video_urls`） |
| 手上是照片，要数字人自然动 | `image_human` · `submit` | `file_url` + `ref_file_url` |
| 手上是照片，只要嘴动 | `pic_lipsync` · `submit` | 图 + 音频 / 文案 |
| 手上是视频，要换口型 | `lipsync` · `submit` | `video_url` + `audio_url` |
| 克隆角色音色 | `voice_tts` · `clone_voice` | `title`（+ `audio_url`） |
| 台词配音 | `voice_tts` · `tts` / `tts_async` | `text`（+ `reference_id`） |
| 查已有音色 | `voice_tts` · `list_voices` | — |
| 音频转文字（做字幕） | `voice_tts` · `stt` | 音频 URL |
| 出 BGM | `music_generation` · `create` | `prompt` + `instrumental: true` |
| 找现成曲子 | `music_search` · `search` | 关键词 |
| 补环境音 / 音效 | `mmaudio` · `submit` | `input_url` |
| 换音色 / AI 翻唱 | `seedsvc` · `submit` | 原始音频 + 目标音色 |
| 成片超分 | `flashvsr` · `submit` | `input_url` |
| 模板混剪 | `smart_clip` · 见 §7.2 | 先 `template` → `template_detail` |
| 动作迁移 / 换人 / 换装 | `action_transfer` / `person_replacement` / `dressing_diffusion` · `submit` | `schema <app>` 现查 |
| 拆剧本、出分镜、写提示词 | **模型网关** `/api/v1/chat/completions` | `model` + `messages` |

---

## 十、计费快照

**1 元 = 100 点。先冻结后结算，失败全额退回。查询类免费。**

| 环节 | 口径 | 点数 |
|---|---|---|
| `nano_banana` `submit` | 点 / 张（1K 普通模型） | 24 |
| `full_video` `submit` | 点 / 秒 | 480P 10 · 768P 20 · 1080P/2K/4K 40 |
| `happy_horse` `submit` | 点 / 秒 | 720P 0.9 · 1080P 1.6 |
| `seedance` `create` | 点 / 百万 tokens（分档） | 480p 3000/5000 · 720p 3200/5500 · 1080p 3500/6000 |
| `image_human` `submit` | 点 / 秒 | fast 1.5 · standard 2 · 2k 4 · 4k 8 |
| `voice_tts` `clone_voice` | 点 / 次 | 200 |
| `voice_tts` `tts` / `tts_async` | 点 / 1k tokens | 50 |
| `music_generation` `create` | 点 / 次 | 65（`concat` 14 · `all_stems` 230 · `replace_section` 90） |
| `mmaudio` `submit` | 点 / 次 | 0.1 |
| `flashvsr` `submit` | 固定 + 按用量 | 0.1 + 3 点/单位 |
| `smart_clip` | 点 / 秒 | 720p 0.2 · 1080p 0.3 |
| 各家 `query` | **免费** | 0 |

> 上表是快照。平台同时给出**标准价**（`fixed_price` / `input_price`）与
> **租户实际结算价**（`tenant_*`）—— **做预算一律用 `tenant_*`，最终以实际扣费为准**。
> 每次调用返回的 `data.usage.points_cost` 就是本次真实扣费。
> 一集 2 分钟的完整测算见 `成本估算.md`。

---

## 十一、异常速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 报参数错误 | 用了本地路径 / 数组传成了字符串 | 一律用**公网 URL**；数组写 `["…"]` |
| HTTP 404 且响应体为空 | 应用代号拼错 | 代号用**下划线**：`nano_banana`、`voice_tts`、`full_video` |
| 打不通 / 路径不对 | 用了 `endpoint_path` 拼 URL | 只用 `/api/v1/apps/<应用代号>/<接口代号>` |
| HTTP 200 但 `code` 为 `0` | 业务失败 | **成功码是 `1`**，必须看响应体里的 `code` / `msg` |
| 「未命中可用计费规格」 | 普通模型传了 `2K`/`4K` | 普通模型用 `1K`；高清换 `:official` 模型 |
| 提交失败 | `full_video` 的 `duration` 超了 15 秒，或首尾帧与参考媒体混用 | 拆镜；两种模式分开用 |
| `402 insufficient_points` | **账号**余额不足 | 充值；错误信息里有本次所需点数 |
| `402 key_quota_exceeded` | **该 Key** 的额度打满 | 调高 / 重置 Key 的 quota |
| `403 permission_denied` | Key 没有该应用权限 | 与余额无关，检查应用是否已开通 |
| `429 queue_limit_exceeded` | 并发任务达上限 | 降并发（视频 2~4 路），退避后重试 |
| 任务 `failed` | 素材或参数问题 | 看 `error` 字段；换素材或核对参数后重试 |
| 扣了两次钱 | 重复提交了异步任务 | 提交前落盘记 `task_id`，超时先查再用 `query` 确认 |
| 音色参数报错 | 用了 `voice_id` | 参数名是 **`reference_id`**，值是 `model_id` |
