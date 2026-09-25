# 单镜头 SOP · 从首帧到成片的六步

**一个镜头 = 六步。** 每步写清「传什么 → 调哪个接口 → 拿回什么 → 怎么验收 → 出问题怎么办」。

---

## 步 1 · 首帧

| 项 | 内容 |
|---|---|
| 应用 | `nano_banana` |
| 接口 | `POST /api/v1/apps/nano_banana/submit` |
| 传什么 | `prompt`（画面描述）；锁定角色时 `action=edit` + `image_urls=[定妆图 URL]` |
| 拿回什么 | `task_id` → 查到的 `image_url` |
| 验收 | 角色长相与定妆图一致；画幅 `9:16`；主体清晰、构图留出运动空间 |

```bash
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"generate","prompt":"雨夜街头，女主撑伞站在路灯下，中景，冷色调，写实电影感","resolution":"1K","aspect_ratio":"9:16"}' \
  --out shot01.png
```

**出问题怎么办**

| 现象 | 处理 |
|---|---|
| 角色每次都不一样 | 改成 `action=edit` + 固定 `image_urls` |
| 报「未命中可用计费规格」 | 普通模型只吃 `1K`；高清要 `:official` 模型 |
| 图片 URL 拉不到 | 换成匿名可访问的公网直链 |

---

## 步 2 · 台词（可选）

| 项 | 内容 |
|---|---|
| 应用 | `voice_tts` |
| 接口 | 短台词 `POST /api/v1/apps/voice_tts/tts`；长台词 `POST /api/v1/apps/voice_tts/tts_async` |
| 传什么 | `text` + `reference_id`（角色音色 ID） |
| 拿回什么 | 音频 URL |
| 验收 | 音色对、语气对；**音频时长与分镜里的镜头时长匹配**（差太多要改台词或改镜头时长） |

```bash
# 先克隆一次（每个角色只做一次）
python3 scripts/a7w.py call voice_tts clone_voice \
  --body '{"title":"女主-清冷","audio_url":"https://你的存储/参考音色.mp3"}'

# 再逐句合成
python3 scripts/a7w.py call voice_tts tts_async \
  --body '{"text":"这雨，下了整整十年。","reference_id":"<音色 ID>"}' \
  --out shot01.mp3
```

**注意**
- `tts` 建议 ≤500 字；长文走 `tts_async`（≤10000 字）
- `prosody` 对象可调 `speed` / `volume` / `normalize_loudness`
- 无声镜头**跳过这一步**

---

## 步 3 · 出片（可选）

| 项 | 内容 |
|---|---|
| 应用 | `full_video`（首选）/ `happy_horse` / `seedance` |
| 接口 | `POST /api/v1/apps/full_video/submit` |
| 传什么 | `content`（**须含一项文本**）+ `ratio` + `duration` + `resolution` |
| 拿回什么 | `task_id` → 视频 URL |
| 验收 | 动作自然、无穿模；时长与分镜一致；画幅与首帧一致 |

```bash
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"type":"text","text":"镜头缓慢推近，女主抬头看向路灯，雨滴打在伞面上"}],"ratio":"9:16","resolution":"720P","duration":6}' \
  --out shot01.mp4
```

**硬约束（记牢，这几条最容易踩）**
- `duration` **只能是 4～15 秒整数**
- 首帧尾帧各最多 1 张；参考图最多 9 张；参考视频 / 音频各最多 3 个
- **首尾帧模式不能与参考媒体模式混用**；参考媒体模式至少要有 1 张参考图或 1 个参考视频
- 768P / 1080P / 2K 的文本总长 ≤ 5000 字符，其他分辨率 ≤ 7000 字符

**静态对话戏请跳过这一步**，走配方 A 的「图 + 口型」更省。

---

## 步 4 · 口型（可选）

| 项 | 内容 |
|---|---|
| 应用 | `lipsync`（已有视频）或 `image_human`（只有图） |
| 接口 | `POST /api/v1/apps/lipsync/submit` |
| 传什么 | `video_url` + `audio_url`；`model` 可选 `xiaojiayu1.0` / `2.0` / `3.0` |
| 拿回什么 | 对口型后的视频 URL |
| 验收 | 口型同步、无音画错位；头部动作自然；画幅不变 |

```bash
python3 scripts/a7w.py call lipsync submit \
  --body '{"video_url":"https://你的存储/shot01.mp4","audio_url":"https://你的存储/shot01.mp3","model":"xiaojiayu2.0"}' \
  --out shot01-lip.mp4
```

**用 `image_human` 时**：`file_url`（人物图）+ `ref_file_url`（驱动音频），
`mode` 四档 `fast` 1.5 / `standard` 2 / `2k` 4 / `4k` 8 点每秒。**先算钱再选档。**

---

## 步 5 · 声音

| 项 | 内容 |
|---|---|
| 应用 | `mmaudio` |
| 接口 | `POST /api/v1/apps/mmaudio/submit` |
| 传什么 | 视频 URL + 音效 / 环境音描述 |
| 拿回什么 | 带音效的视频 URL |
| 验收 | 环境音贴合场景；**不盖过台词** |

**描述写法**：写「空间 + 具体声源 + 强弱」，例如
`室内办公室，空调低鸣，远处键盘声，整体安静，不出现人声`。

> **不要在出片接口里要求配乐。** 声音只写环境音与音效，BGM 走步 5 之后的独立工序。

---

## 步 6 · 交付

| 项 | 内容 |
|---|---|
| 应用 | `flashvsr` |
| 接口 | `POST /api/v1/apps/flashvsr/submit` |
| 传什么 | `input_url`（**必填**）；`duration` 不传则平台自行探测 |
| 拿回什么 | 高清视频 URL |
| 验收 | 分辨率达标；**无异常锐化、无边缘光晕**；音画同步未被破坏 |

```bash
python3 scripts/a7w.py call flashvsr submit \
  --body '{"input_url":"https://你的存储/shot01-lip.mp4"}' \
  --out shot01-4k.mp4
```

**什么时候跳过**：目标平台会二次压缩时（竖屏短剧发布到抖音 / 小红书 / 视频号），
超分的收益很有限。**真要交付母版才做这一步。**

---

## 每步都要做的一件事：记任务表

每一步提交后，往 `tasks.csv` 追加一行：

```csv
shot_id,stage,app,api,task_id,status,points,input_url,output_url,updated_at
shot01,image,nano_banana,submit,task_aaa,completed,24,,"https://.../shot01.png",2026-01-01T10:00:00
```

- `status` 只认 `pending` / `completed` / `failed`
- 重跑时**只补 `status != completed` 的行**
- `points` 用来对账，一眼看出钱花在哪个应用上

---

## 完整的最小闭环（照抄即可）

```bash
export A7W_API_KEY=sk-你的key

# 1 首帧
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"generate","prompt":"雨夜街头，女主撑伞站在路灯下，中景，冷色调","aspect_ratio":"9:16"}' \
  --out shot01.png

# 2 台词
python3 scripts/a7w.py call voice_tts tts_async \
  --body '{"text":"这雨，下了整整十年。","reference_id":"<音色 ID>"}' \
  --out shot01.mp3

# 3 出片（先把 shot01.png 传到公网拿到 URL）
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"type":"text","text":"镜头缓慢推近，女主抬头看向路灯"}],"ratio":"9:16","resolution":"720P","duration":6}' \
  --out shot01.mp4

# 4 口型
python3 scripts/a7w.py call lipsync submit \
  --body '{"video_url":"https://你的存储/shot01.mp4","audio_url":"https://你的存储/shot01.mp3"}' \
  --out shot01-lip.mp4
```

---

## 异常速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 报参数错误 | 用了本地路径 / `image_urls` 传成了字符串 | 换公网直链；数组要用 `["..."]` |
| 404 | 应用代号用了连字符 | 用下划线：`nano_banana`、`voice_tts` |
| 打不通 | 用 `endpoint_path` 拼了 URL | 只用 `/api/v1/apps/<应用代号>/<接口代号>` |
| 提交失败 | `duration` 超了 15 秒，或首尾帧与参考媒体混用 | 拆镜；两种模式分开用 |
| 429 | 并发任务达上限 | 降并发，等队列消化后重试 |
| 402 | 点数不足或 Key 的 quota 打满 | 分清是账号没钱还是 Key 额度满；错误信息里有本次所需点数 |
| 任务 `failed` | 上游处理失败 | 看 `error` 字段；换素材或稍后重试 |
| 拿 `code == 0` 判成失败 | 判断口径错了 | 平台成功码是 **`1`** |
