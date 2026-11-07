# 接口契约（实测原文 + 计费口径）

> 全部走 `https://api.a7w.cn`，鉴权 `Authorization: Bearer <你的 Key>`，请求 `Content-Type: application/json`。
> 返回信封：`{"code":1,"msg":"success","data":{…}}`；业务数据在 `data` 里，部分接口在 `data.result.data`。
> 单位：1 元 = 100 点。价格 `GET /api/v1/pricing`，2026-11-08 现查。

---

## 一、`POST /api/v1/apps/full_video/submit` · 一键成片

异步，返回 `task_id`。单段 4~15 秒整数；30 秒要拆 15 + 15，按**总秒数 x 分辨率**计费。

```json
{
  "model": "full-video",
  "content": [
    {"type": "text", "text": "竖屏手机实拍房源漫游，街边推到小区大门，户型图，客厅采光，整段 15 秒内"},
    {"type": "image_url", "role": "first_frame",
     "image_url": {"url": "https://oss.gpu.likeadmin.cn/openapi/…"}}
  ],
  "duration": 15,
  "resolution": "1080P",
  "ratio": "9:16",
  "aigc_watermark": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `content` | array | 是 | 必含一条 `{"type":"text"}`；可带首帧 / 尾帧 / 参考媒体 |
| `duration` | int | 否 | **4~15**，默认 4 |
| `resolution` | string | 否 | 480P / 768P / 1080P / 2K / 4K，默认 480P |
| `ratio` | string | 否 | 16:9 / 9:16 / 1:1 / 4:3 / 3:4 / adaptive |
| `model` | string | 否 | 固定 `full-video` |
| `aigc_watermark` | bool | 否 | 是否加生成标识，默认 false |

**计费**（`/api/v1/pricing` 原文）：

```json
"/api/v1/apps/full_video/submit": {
  "mode": "per_second",
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80（1 元=100 点，价格已含利润，不再叠加上游倍率）"
}
```

成片部分：一单 45 秒 1080P = 60 x 45 = **2,700 点 = 27 元**；同一单改 480P = 14 x 45 = 630 点。加上图片 36 点、口播 45 点、配乐 50 点，一单合计 2,831 点 = 28.31 元。

**限制**：首帧 / 尾帧各最多 1 张；参考图最多 9 张；参考视频与参考音频各最多 3 个；首尾帧模式与参考媒体模式不混用；768P 及以上文本上限 5,000 字符。

---

## 二、`POST /api/v1/images/generations` · 出图

同步，OpenAI Images API 兼容。端点**必须带 `/api` 前缀**，少一层会落到网关默认应用。

```json
{"model": "gpt-image-2.6",
 "prompt": "手机竖屏实拍，杭州余杭万科金域华府小区大门，门禁与招牌清晰，傍晚暖光，真实街景质感，画面无文字水印",
 "n": 1, "size": "1024x1536"}
```

| 字段 | 说明 |
|---|---|
| `model` | `gpt-image-2.6` |
| `prompt` | 提示词；空字符串返回 422（`prompt: String should have at least 1 character`） |
| `n` | 1~4 |
| `size` | `auto` / `1024x1024` / `1024x1536` / `1536x1024` 等；16 的倍数、长短边 ≤3:1、单边 ≤3840、总像素 655,360–8,294,400 |
| `output_format` | png / jpeg / webp / gif |

**计费：6 点/张**，与尺寸、质量、输出格式无关；按 `data` 实际返回张数计费。返回默认 `b64_json`，本包自动解码落成 png。

房源 6 张：`gate` 小区大门 / `building` 楼栋外立面 / `floorplan` 户型图 / `living` 客厅采光 / `bedroom` 主卧 / `amenity` 配套街景。
车源 5 张：`front45` 前 45 度 / `interior` 内饰中控 / `rear` 后排 / `detail` 漆面轮毂 / `dash` 仪表里程。

---

## 三、`POST /api/v1/apps/voice_tts/tts` · 口播（同步）

```json
{"text": "「万科金域华府」，杭州余杭，89平三居，268 万。12/18 层，南向，单元门在楼栋中间。",
 "model": "s2-pro", "format": "mp3"}
```

| 字段 | 说明 |
|---|---|
| `text` | 必填；同步接口建议 500 字内，长文走 `tts_async` |
| `model` | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | mp3 / wav / ogg / opus / pcm |
| `reference_id` | 克隆音色 ID，可选 |

返回 `data.audio_url`。

**计费**：`/api/v1/pricing` 里 `/api/v1/apps/voice_tts/*` 是 `mode=flat, cost=0, markupPercent=200`，note 原文「对外价 = 上游实际点数（响应 `usage.points_cost` / `actual_points`，单位是点）x 3，单笔保底 > 0」。实测基准：`tts_live` 33 字上游 1.98 点 → 我方 5.94 点，所以本包按 **0.18 点/字**估，实际以返回的 `usage.points_cost` 为准。

一单两条片的房源码约 250 字（主片 153 + 快切 98），约 45 点。

---

## 四、`POST /api/v1/apps/media_services_33/music_generate` · 配乐

必填 `model` / `custom_mode` / `instrumental`；`prompt`、`style`、`title`、`duration`、`negative_tags` 等可选。

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "温暖钢琴加轻弦乐，92 BPM，节奏平稳，适合 30 秒房源漫游"}
```

**计费**：该路径没有专属规则，落通配 `*`：`{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}`，即 **上游实际点数 x 2、单笔保底 50 点**。返回里可能有 `audio_url`，也可能只有 `task_id`（用 `GET /api/v1/tasks/<id>` 取结果）。

### media_services_33 在架的 29 个接口（`GET /api/v1/apps` 现查）

`music_generate` 只是其中一条。要换风格或换做法时，按下面这张表挑，参数照抄：

| 用途 | 接口 | 必填 |
|---|---|---|
| 生成音乐（本包用） | `music_generate` | `model` `custom_mode` `instrumental` |
| 生成歌词 | `music_generate_lyrics` | `prompt` |
| 提升风格描述 | `music_boost_music_style` | `content` |
| 延长音乐 | `music_extend` | `model` `audio_id` |
| 上传并延长 | `music_upload_and_extend_audio` | `model` `upload_url` |
| 上传并翻唱 | `music_upload_and_cover_audio` | `model` `instrumental` |
| 生成混音 | `music_mashup` | `model` `style` `title` `upload_url_list` |
| 添加人声 | `music_add_vocals` | `style` `title` `upload_url` `negative_tags` |
| 添加伴奏 | `music_add_instrumental` | `tags` `title` `upload_url` `negative_tags` |
| 替换音乐分区 | `music_replace_section` | `tags` `title` `prompt` `full_lyrics` `infill_start_s` `infill_end_s` |
| 人声乐器分离 | `music_separate_vocals` | — |
| 生成声音（音效） | `music_sounds` | `model` `prompt` |
| 生成音乐封面 | `music_cover_generate` | `task_id` |
| 生成 Persona | `music_generate_persona` | `name` `task_id` `audio_id` `description` |
| 自建音色 | `music_generate_voice` | — |
| 检查音色可用 | `music_check_voice` | `task_id` |
| 恢复音频 | `music_recovery_audio` | `task_id` |
| 带时间戳歌词 | `music_timestamped_lyrics` | `task_id` `audio_id` |
| 音频转 MIDI | `music_generate_midi_from_audio` | `task_id` |
| 转 WAV | `music_convert_to_wav_format` | `task_id` `audio_id` |
| 创建音乐视频 | `music_create_music_video` | `task_id` `audio_id` |
| Gemini 3.8 Flash 文生语音 | `google_gemini_3_8_flash_tts` | `speakers` `dialogue_turns` |
| Gemini 3.8 Flash Lite 文生语音 | `google_gemini_3_8_flash_lite_tts` | `speakers` `dialogue_turns` |
| Gemini 2.5 Pro 文生语音 | `google_gemini_2_5_pro_tts` | `speakers` `dialogue_turns` |
| Gemini Omni Audio | `gemini_omni_audio` | `name` `audio_id` |
| Gemini Omni Character | `gemini_omni_character` | `image_urls` `descriptions` |
| ElevenLabs 多语言 V2 | `elevenlabs_text_to_speech_multilingual_v2` | `text` `voice` |
| ElevenLabs Turbo 2.5 | `elevenlabs_text_to_speech_turbo_2_5` | `text` `voice` |
| ElevenLabs 对话 V3 | `elevenlabs_text_to_dialogue_v3` | `dialogue` |

全路径都是 `POST /api/v1/apps/media_services_33/<接口>`。29 条都没有专属价格规则，统一落通配：上游 x 2、保底 50 点。

---

## 五、`GET /api/v1/tasks/<task_id>` · 查进度

```bash
curl -H "Authorization: Bearer $A7W_API_KEY" \
  https://api.a7w.cn/api/v1/tasks/tsk_xxxxxxxx
```

- 任务不存在时：HTTP 200 + `{"code":0,"msg":"任务不存在"}`，**0 点**。
- 价目表：`/api/v1/tasks` 是 `per_module`，只在请求体带非空 `module_codes[]` 时按 50 点 x 模块数；本包只发 GET，不触发。
- **应用层 `/query` 不在这里用**：`nano_banana/query` 72 点/次，每查一次都是一次的钱。

---

## 六、`POST /api/v1/upload` · 换白名单地址

`multipart/form-data`，字段名 **`file`**，免费。`/api/v1/pricing` 原文：

```json
"/api/v1/upload": {"mode": "flat", "cost": 0, "markupPercent": 0,
  "note": "★上传不计费（2026-10-04 站主批准）…计费引擎对 cost:0 有显式语义：server.js isFreePath 里 ruleCost === 0 即视为免费路径。"}
```

返回 `data.url`，形如 `https://oss.gpu.likeadmin.cn/openapi/…`，最长 24 小时有效。

`full_video` 对首帧 / 参考图做域名白名单校验，实测报错原文：

```
400 url_not_allowed
"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
 或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

| 放行 | 判定 |
|---|---|
| `vr.a7w.cn` / `*.a7w.cn` | 本站 |
| `cdn2.jiujiushuyuan.cn/vr/…` | 本站七牛 |
| `oss.gpu.likeadmin.cn/openapi/…` | 本站上传接口 |

---

## 七、平台尺寸（发布页当期口径）

| `--platform` | 平台 | 画幅 | 尺寸 | 时长上限 |
|---|---|---|---|---|
| `beike` | 贝壳找房 | 9:16 | 1080x1920 | 60 秒 |
| `anjuke` | 安居客 | 9:16 | 1080x1920 | 60 秒 |
| `dcd` | 懂车帝 | 9:16 | 1080x1920 | 60 秒 |
| `autohome` | 汽车之家 | 16:9 | 1920x1080 | 120 秒 |

---

## 八、探针禁区（2026-11-07 实测，472 点换来的）

| 端点 | 行为 | 本包做法 |
|---|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，**即时结算、不退**（dressing_diffusion 200、nano_banana 72） | 一次都不打 |
| `POST /api/v1/apps/<app>/query` | 每查一次按该应用单价计费（nano_banana/query 72 点/次） | 只走 `GET /tasks/<id>` |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结，再校验失败 refund（净额 0，钱包被短暂动过） | 必填在本地卡死，缺了退 2 |

**完全安全、`doctor` 只用这些（2026-11-08 逐条复验）**：

```
GET  /api/v1/apps             → 22 个应用，media_services_33 在架 29 个接口
GET  /api/v1/pricing          → 裸对象，不套 code/data
GET  /api/v1/tasks/<id>       → 200 {"code":0,"msg":"任务不存在"}
GET  /user/balance            → available_points / frozen / rate=100
GET  /user/balance/logs?limit=1 → 最新一笔流水（自检前后对比，证明 0 点）
POST /api/v1/upload（缺 file）  → 200 {"code":0,"msg":"请使用 file 字段提交一个文件"}
POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""} → 422
POST /api/v1/video/viapi/enhance {} → 400 empty_url（视频线在参数校验就停）
```

`doctor` 的判据：`400/422` + 参数报错 = 端点存在，停在校验层；`404` + HTML = 未注册；`200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` = 应用层兜底话术，不可信（假代号也返回同一句）。
