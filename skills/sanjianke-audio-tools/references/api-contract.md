# 音频工具台 · 接口契约（实测原文）

> 全部来自 2026-11-08 的实测：只读 GET、空 body POST、坏 URL POST。
> 没有做任何真实生成，也没有触发 `reserve_sync`。本账号余额全程
> 999,997,393,008.98 点，流水最新一笔停在 12:11:55 的 `gpu:app`（与本包无关）。

---

## 1. 端点总表

| 能力 | 方法 | 路径 | 形态 | 计费 |
|---|---|---|---|---|
| 上传本地文件 | POST | `/api/v1/upload` | multipart，字段名 `file` | 0 点 |
| 换 audio_id | POST | `/api/v1/apps/music_generation/upload_audio` | JSON，同步 | 上游 13 点 × 3 = 39 点 |
| 人声分离 | POST | `/api/v1/apps/music_generation/vox` | JSON，异步 | 上游 14 点 × 3 = 42 点 |
| 混搭歌词 | POST | `/api/v1/apps/music_generation/mashup_lyrics` | JSON，同步 | 上游 12 点 × 3 = 36 点 |
| 整曲 / 四轨分离 | POST | `/api/v1/apps/music_generation/create` | JSON，异步 | 随 `type` 变，只认实测 |
| 视频补帧 | POST | `/api/v1/video/viapi/interp` | JSON，异步 | 25 点/秒 |
| 查任务 | GET | `/api/v1/tasks/<task_id>` | — | 0 点 |

公共请求头：

```
Authorization: Bearer <你的 Key>
Content-Type: application/json
Accept: application/json
```

## 2. 三个音频接口的归属（实测，容易搞错的一条）

`GET /api/v1/apps` 回 200，22 个应用、100 个接口。逐条数出来：

```
music_generation    13 个接口   driver=suno_music
  mashup_lyrics   id=68  call_type=1  method=POST  category=audio
  vox             id=67  call_type=2  method=POST  category=audio
  upload_audio    id=59  call_type=1  method=POST  category=audio
  （其余 10 个：create / query / lyrics / style / midi / timing / mp4 / wav /
    voice_clone / persona）

media_services_33   29 个接口   driver=official
  elevenlabs_text_to_speech_multilingual_v2 / elevenlabs_text_to_dialogue_v3 /
  google_gemini_3_8_flash_tts / music_generate / music_extend / music_sounds /
  music_timestamped_lyrics / …
  —— 上面三个 code 一个都不在这里
```

结论：拼路径必须用 `/api/v1/apps/music_generation/<code>`。`call_type=1` 是同步
（结果直接回），`call_type=2` 是异步（回 `task_id`，要自己轮询）。

## 3. `POST .../upload_audio` · 地址换 ID

请求体（平台 schema 原文）：

```json
{
  "audio_url": {
    "type": "string",
    "example": "https://example.com/ref.mp3",
    "description": "可公开访问的音频文件 URL，用于生成后续创作需要的音频 ID。"
  }
}
```

- 必填：`audio_url`（http / https）
- 成功回 `data.result.audio_id`（形如 `audio_xxxxxxxxxxxx`），可能同时带
  `audio_url` / `duration` / `title`
- 返回体里 `data.usage.points_cost` 是这一单的真实点数，`actual_points` 是结算值

平台文档的成功示例（同 schema）：

```json
{"code":1,"msg":"success","data":{
  "result":{"status":"completed","audio_id":"audio_xxxxxxxxxxxx",
            "audio_url":"https://example.com/music/reference.mp3",
            "title":"reference_audio","duration":198,
            "data":{"audio_id":"audio_xxxxxxxxxxxx","duration":198}},
  "usage":{"points_cost":13,"actual_points":13}}}
```

## 4. `POST .../vox` · 人声分离

请求体：

```json
{
  "audio_id":    {"type":"string", "example":"audio_xxxxxxxxxxxx",
                  "description":"音频 ID，用于定位已生成或已上传的音频片段。"},
  "vocal_start": {"type":"number", "description":"人声提取开始时间，单位秒。"},
  "vocal_end":   {"type":"number", "description":"人声提取结束时间，单位秒。"},
  "callback_url":{"type":"string", "description":"任务完成或失败时由平台主动通知的 HTTPS 地址。"}
}
```

- 必填只有 `audio_id`；`vocal_start` / `vocal_end` 是**按秒裁切**，只取副歌那一段就填这两个
- 异步：成功回 `data.task_id` + `status` + `frozen_points` + `actual_points`
- 完成后的结构（平台文档示例）：

```json
{"code":1,"msg":"success","data":{
  "result":{"task_id":"task_xxxxxxxxxxxx","status":"completed",
            "data":{"id":"vox_xxxxxxxxxxxx","status":"complete",
                    "vocal_start_s":"0.0","vocal_end_s":"20.0"}},
  "usage":{"points_cost":14,"actual_points":14}}}
```

本包 `status` 会把结果里所有 `*_url` 键列出来（人声轨 / 伴奏轨 / 原曲都在这一层），
`--json` 给完整结构。

## 5. `POST .../mashup_lyrics` · 两段词融一段

```json
{
  "lyrics_a": {"type":"string", "description":"第一段歌词文本。"},
  "lyrics_b": {"type":"string", "description":"第二段歌词文本。"}
}
```

- 两个都必填；同步返回，结果在 `data.result.data.text`
- 返回的文本自带 `[singer A]` / `[transition]` / `[singer B]` 这样的分段，直接能喂
  给 `create` 的 `type=cover`
- 平台文档示例：`usage.points_cost = 12`，`actual_points = 12`

本包 `mashup` 支持 `--a-file` / `--b-file`（UTF-8 文本），中文歌词走文件比命令行
引号稳。

## 6. `POST /api/v1/video/viapi/interp` · 补到 60fps

价目表原文（`GET /api/v1/pricing` 的 `pricing` 对象里这一条）：

```json
"/api/v1/video/viapi/interp": {
  "mode": "per_second",
  "perSecond": 25,
  "note": "视频插帧 60fps"
}
```

实测探针（两条，全部停在参数校验，0 点）：

```
POST /api/v1/video/viapi/interp   {}
→ 400 {"error":{"code":"empty_url","message":"videoUrl 不能为空","type":"relay"}}

POST /api/v1/video/viapi/interp   {"videoUrl":"https://example.invalid/a.mp4"}
→ 400 {"error":{"code":"url_not_allowed",
        "message":"videoUrl 必须是本站（vr.a7w.cn）、本站七牛
        （cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址
        （oss.gpu.likeadmin.cn/openapi/）","type":"relay"}}
```

- 请求体：`videoUrl`（必填）、`duration`（按秒计费，强烈建议给）
- 异步：成功回 `taskId` + `status`，查询走 `GET /api/v1/tasks/<id>`
- 状态标「待验证」的原因：价目表有这一条、路由也回结构化校验错误，但线上档位
  说明写过「已下线」。本包不把它当默认路径，`cost` 里单独标状态

## 7. 计费口径（`GET /api/v1/pricing` 原文）

```
规则数：115 条（2026-11-08）

"/api/v1/apps/music_generation/*":
           query/余额等 0 点…"}

"/api/v1/upload":

"*"（通配）:
```

推导：

```
vox           上游 14 点  × 3 = 42 点
mashup_lyrics 上游 12 点  × 3 = 36 点
upload_audio  上游 13 点  × 3 = 39 点
interp        价目表直接写死 25 点/秒
upload        0 点
```

`create` 没有可用单价：同一条路径按 `type` 分价，本包只报实测区间。

## 8. 轮询（只走免费视图）

```
GET /api/v1/tasks/<task_id>
→ 200 {"code":0,"msg":"任务不存在","data":null}      # 假 ID
→ 200 {"code":1,"data":{...}}                       # 真 ID，按 status 判终态
```

`GET /api/v1/tasks/<task_id>` 是统一任务查询接口，`cost: 0`。**应用层 `/query`
一次一扣**，本包一次都不碰；`music_generation` 的 `query` 虽然在 pricing 的 note
里写「0 点」，本包仍然不用它，少一条要解释的路径。

## 9. 探针判定表（本包自己遵守的）

| 返回 | 含义 | 本包做法 |
|---|---|---|
| `400` / `422` + 参数报错 | 端点存在，停在参数校验 | 可用作探针 |
| `404` + HTML | 该前缀下没有这个端点 | 说明路径拼错 |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，不可信 | 不当成「端点不存在」 |
| `502` + `InvalidMpsUser` | 路由在，上游凭据坏 | 不当成「本包的问题」 |

## 10. 本轮实测时间线（0 点）

```
12:11:55  charge   -43.95  gpu:app:wf_42c5986f3781b6210c3e      ← 与本包无关
12:22     GET /api/v1/apps · /pricing · /models · /me/tasks(70 页)
          POST /api/v1/video/viapi/interp {}          → 400 empty_url
          POST /api/v1/video/viapi/interp 坏 URL       → 400 url_not_allowed
          GET  /api/v1/tasks/probe-no-such-task        → 200 任务不存在
12:22     余额 999,997,393,008.98 点（与开始完全相同）
          流水最新一笔仍是 12:11:55 的 gpu:app —— 没有任何本包产生的 charge
```
