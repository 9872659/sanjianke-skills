# 接口契约（实测原文 + 计费口径）

> 全部走 `https://api.a7w.cn`，鉴权 `Authorization: Bearer <你的 Key>`，请求 `Content-Type: application/json`。
> 返回信封：`{"code":1,"msg":"success","data":{…}}`；业务数据在 `data` 里，任务类还要再往 `data.result` 里看一眼。
> 单位：1 元 = 100 点。本页价格全部来自 **2026-11-08 `GET /api/v1/pricing` 现查**，辅以 2026-11-07/08 的实测流水。

---

## 一、`POST /api/v1/apps/smart_clip/news_mixcut` · 新闻体混剪

异步，返回 `task_id`。**本包的主力出片口**：按输入媒体时长计费，`processRules.videoDuration` 给了就按它算。

```json
{
  "styleId": "68aebb91b8619ed6f4168f40",
  "title": "地铁 3 号线延长运营",
  "materials": [
    {"type": "image", "fileUrl": "https://oss.gpu.likeadmin.cn/openapi/…png", "soundSwitch": false},
    {"type": "video", "fileUrl": "https://oss.gpu.likeadmin.cn/openapi/…mp4", "soundSwitch": false}
  ],
  "processRules": {
    "watermarkShow": true,
    "videoDuration": 30,
    "materialComposition": "order",
    "metadata": {"AIGC": "{\"Label\":\"1\",\"ContentProducer\":\"三剪客 api.a7w.cn\",\"ProduceID\":\"NS20261108021500\"}"}
  },
  "packRules": {
    "headerSwitch": true, "materialSwitch": true, "subtitleSwitch": true,
    "keywordSwitch": true,
    "backgroundMusic": {"audioSwitch": true, "audioUrl": "https://…bgm.mp3", "volume": 0.3}
  },
  "introduceCard": {"name": "三剪客资讯", "description": "每日资讯精选"}
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `styleId` | string | **是** | 视频模板 ID（来自 `smart_clip/template`，本包默认填文档示例值） |
| `title` | string | **是** | 3~1800 字；快讯标题控制在 20 字内 |
| `materials` | array | **是** | 每项 `type`（image / video）+ `fileUrl`；视频可带 `soundSwitch` |
| `introduceCard` | object | 否 | 身份栏 `name` / `description` |
| `packRules` | object | 否 | 只控制各图层是否参与包装，不控制显示隐藏 |
| `processRules.videoDuration` | int | 否 | **5~300** 秒；不带它时平台探测素材时长，探不到会拒绝提交 |
| `processRules.watermarkShow` | bool | 否 | true 时画面挂「AI 生成」字样 |
| `processRules.metadata` | object | 否 | 元水印，只写一组，**value 必须是字符串** |
| `processRules.materialComposition` | string | 否 | random / order |
| `callbackUrl` | string | 否 | 完成后回调的 HTTPS 地址 |

**计费**（`/api/v1/pricing` 原文）：

```json
"/api/v1/apps/smart_clip/*": {
           对外价 = 1.5 x 3 = 4.5 点/秒（15 秒 = 67.5 点）；body 不带 duration 时用 estimate 45 点预冻结…
           四个 api（template / template_detail / realman_broadcast / broadcast_mixcut / news_mixcut）同价"
}
```

- 一条 30 秒快讯 = 4.5 x 30 = **135 点**；90 秒深度 = **405 点**。
- 不带 `videoDuration` 时按 45 点预冻结，跑完按实际时长结算，**失败全额退回**。
- 素材总量：单图按 2 秒计，单个视频 ≤ 60 秒，全部素材合计 ≤ 5 分钟。

**素材要求**：mp4 / mov，h264 / h265，10~60fps，单边 < 2000px，单文件 < 500MB；图片 jpg / png / webp 静态图；背景音乐 mp3 / wav / m4a，≤ 120MB、≤ 5 分钟。

> 三个素材 `fileUrl`、背景音乐 `audioUrl`、AI 封面 `resultImageUrl` **不能重名**，重名会渲染异常 —— 所以本包每个文件都带不同后缀（`_cover` / `_scene` / `_chart`）。

---

## 二、`POST /api/v1/apps/full_video/submit` · 补镜头

异步，返回 `task_id`。单段 4~15 秒整数，按**总秒数 x 分辨率**计费。

```json
{"model": "full-video",
 "content": [
   {"type": "text", "text": "竖屏新闻现场，站台人流，镜头稳定，15 秒内"},
   {"type": "image_url", "role": "first_frame",
    "image_url": {"url": "https://oss.gpu.likeadmin.cn/openapi/…png"}}
 ],
 "duration": 15, "resolution": "1080P", "ratio": "9:16", "aigc_watermark": true}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `content` | 是 | 必含一条 `{"type":"text"}`；可带首帧 / 尾帧 / 参考媒体 |
| `duration` | 否 | **4~15**，默认 4 |
| `resolution` | 否 | 480P / 768P / 1080P / 2K / 4K，默认 480P |
| `ratio` | 否 | 16:9 / 9:16 / 1:1 / 4:3 / 3:4 / adaptive |
| `aigc_watermark` | 否 | 本包默认 **true**，片内带生成标识 |

**计费**：

```json
"/api/v1/apps/full_video/submit": {
  "mode": "per_second",
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80（1 元=100 点，价格已含利润，不叠加倍率）"
}
```

15 秒 1080P = 60 x 15 = **900 点 = 9.00 元**；同一段 480P = 210 点。

---

## 三、`POST /api/v1/images/generations` · 配图

同步，OpenAI Images API 兼容。端点**必须带 `/api` 前缀**，少一层会落到网关默认应用。

```json
{"model": "gpt-image-2.6",
 "prompt": "地铁延长运营——新闻资讯封面，竖屏构图，主体在画面中部，冷色调新闻质感，留出上三分之一标题区，画面无文字、无水印",
 "n": 1, "size": "1024x1536"}
```

| 字段 | 说明 |
|---|---|
| `prompt` | 空字符串返回 **422** `prompt: String should have at least 1 character`（`doctor` 就用这条探端点，0 点） |
| `n` | 1~4 |
| `size` | `auto` / `1024x1024` / `1024x1536` / `1536x1024`；16 的倍数、长短边 ≤ 3:1、单边 ≤ 3840、总像素 655,360–8,294,400 |
| `output_format` | png / jpeg / webp / gif |

**计费：6 点/张**，与尺寸、格式无关，按 `data` 实际返回张数计。实测 1024x1024 一张 43.6 秒出图、扣 6 点。返回默认 `b64_json`，本包自动解码落 png。

图种：快讯 `cover` / `scene` / `chart`（3 张）；深度 `cover` / `scene` / `people` / `chart` / `timeline` / `ending`（6 张）。

---

## 四、`POST /api/v1/apps/voice_tts/tts` · 播报

```json
{"text": "今天起，杭州市地铁集团把末班车延到 23:30。日均多运 1.2 万人次。", "model": "s2-pro", "format": "mp3"}
```

| 字段 | 说明 |
|---|---|
| `text` | 必填；同步接口建议 500 字内，长文走 `tts_async` |
| `model` | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | mp3 / wav / ogg / opus / pcm |
| `reference_id` | 克隆音色 ID，可选 |

返回 `data.audio_url`。

---

## 五、`POST /api/v1/apps/media_services_33/music_generate` · 配乐

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "新闻快讯片头感：短促电子鼓点加铜管重音，118 BPM，8 秒一个循环，收尾干净"}
```

### media_services_33 在架的 29 个接口（`GET /api/v1/apps` 现查）

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

全路径都是 `POST /api/v1/apps/media_services_33/<接口>`，29 条统一落通配：上游 x 2、保底 50 点。

---

## 六、`POST /api/v1/apps/watermark_removal/douyin_search_video` · 采集参考（抖音）

同步返回，没有 `task_id`，不需要轮询。

```json
{"keyword": "地铁 延长运营", "page": "1"}
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `keyword` | **是** | 搜索关键词 |
| `page` | 否 | 页码 |
| `searchId` | 否 | 翻页会话标识（也可写 `search_id`） |

## 七、`POST /api/v1/apps/watermark_removal/xhs_search_note` · 采集参考（小红书）

| 参数 | 必填 | 说明 |
|---|---|---|
| `keyword` | **是** | 搜索关键词 |
| `page` | 否 | 页码，默认 1 |
| `sort` | 否 | general / popularity_descending / time_descending / comment_descending / collect_descending |
| `noteType` | 否 | `_0` 通用 / `_1` 视频 / `_2` 图文 |
| `noteTime` | 否 | 发布时间筛选 |

**计费（两个接口同价）**：

```json
"/api/v1/apps/watermark_removal/*": {
  "note": "去水印/分享链解析：固定 100 点/次"
}
```

与返回条数无关，**失败亦计** —— 所以本包一次都不拿它做探针，`doctor` 也不碰它。

---

## 八、`GET /api/v1/tasks/<task_id>` · 查进度

```bash
curl -H "Authorization: Bearer $A7W_API_KEY" https://api.a7w.cn/api/v1/tasks/tsk_xxxxxxxx
```

- 任务不存在：HTTP 200 + `{"code":0,"msg":"任务不存在"}`，**0 点**。
- 价目表里 `/api/v1/tasks` 是 `per_module`（`module_codes[]` 非空时 50 点 x 模块数）；本包只发 GET，不触发。
- **应用层 `/query` 不在这里用**：`nano_banana/query` 72 点/次，每查一次都是一次的钱。

---

## 九、`POST /api/v1/upload` · 换白名单地址

`multipart/form-data`，字段名 **`file`**，免费。返回 `data.url`，形如 `https://oss.gpu.likeadmin.cn/openapi/…`，最长 24 小时有效。

| 放行 | 判定 |
|---|---|
| `vr.a7w.cn` / `*.a7w.cn` | 本站 |
| `cdn2.jiujiushuyuan.cn/vr/…` | 本站七牛 |
| `oss.gpu.likeadmin.cn/openapi/…` | 本站上传接口 |

外站地址实测报错原文：

```
400 url_not_allowed
"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
 或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

---

## 十、平台尺寸与时长（发布页当期口径）

| `--platform` | 平台 | 画幅 | 尺寸 | 时长上限 |
|---|---|---|---|---|
| `douyin` | 抖音 | 9:16 | 1080x1920 | 180 秒 |
| `kuaishou` | 快手 | 9:16 | 1080x1920 | 180 秒 |
| `xhs` | 小红书 | 9:16 | 1080x1920 | 180 秒 |
| `channels` | 视频号 | 9:16 | 1080x1920 | 180 秒 |
| `bilibili` | B 站 | 16:9 | 1920x1080 | 480 秒 |

模板上限更严：快讯 60 秒、深度 180 秒，`qc` 按模板上限校验。

---

## 十一、探针禁区（2026-11-07 实测，472 点换来的）

| 端点 | 行为 | 本包做法 |
|---|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，**即时结算、不退**（dressing_diffusion 200、nano_banana 72） | 一次都不打 |
| `POST /api/v1/apps/<app>/query` | 每查一次按该应用单价计费（nano_banana/query 72 点/次） | 只走 `GET /tasks/<id>` |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结，再校验失败 refund（净额 0，钱包被短暂动过） | 必填在本地卡死，缺了退 2 |
| `POST /api/v1/apps/watermark_removal/<接口>` | flat 100 点/次，**失败亦计** | 只在用户带 `--yes` 时发 |

**完全安全、`doctor` 只用这些（2026-11-08 逐条复验，10 项全 √、0 点）**：

```
GET  /api/v1/apps              → 22 个应用；media_services_33 29 接口 / smart_clip 5 / watermark_removal 8
GET  /api/v1/pricing           → 裸对象，不套 code/data
GET  /user/balance             → available_points / frozen / rate=100
GET  /user/balance/logs?limit=1 → 最新一笔流水（自检前后对比，证明 0 点）
GET  /api/v1/tasks/<假id>       → 200 {"code":0,"msg":"任务不存在"}
POST /api/v1/upload（缺 file）   → 200 {"code":0,"msg":"请使用 file 字段提交一个文件"}
POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""} → 422
POST /api/v1/video/viapi/<tier> {} → 400 empty_url（视频线在参数校验就停）
```

`doctor` 的判据：`400/422` + 参数报错 = 端点存在，停在校验层；`404` + HTML = 未注册；`200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` = 应用层兜底话术，不可信（假代号也返回同一句）。
