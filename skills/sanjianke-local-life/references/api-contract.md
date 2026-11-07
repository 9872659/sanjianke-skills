# 接口契约（实测原文 + 计费口径）

> 全部走 `https://api.a7w.cn`，鉴权 `Authorization: Bearer <你的 Key>`，请求 `Content-Type: application/json`。
> 返回信封：`{"code":1,"msg":"success","data":{…}}`；业务数据在 `data` 里，部分接口在 `data.result.data`。
> 单位：1 元 = 100 点。价格 `GET /api/v1/pricing`，2026-11-08 现查。

---

## 一、`POST /api/v1/apps/full_video/submit` · 一键成片

异步，返回 `task_id`。单段 4~15 秒整数；24 秒要拆两段，按**总秒数 x 分辨率**计费。

```json
{
  "model": "full-video",
  "content": [
    {"type": "text", "text": "竖屏手机实拍探店，门头推到招牌，暖黄灯光，画面无文字"},
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
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80"
}
```

25 秒 1080P = 60 x 25 = **1,500 点 = 15 元**。

**限制**：首帧 / 尾帧各最多 1 张；参考图最多 9 张；参考视频与参考音频各最多 3 个；首尾帧模式与参考媒体模式不混用；768P 及以上文本上限 5,000 字符。

---

## 二、`POST /api/v1/images/generations` · 出图

同步，OpenAI Images API 兼容。端点**必须带 `/api` 前缀**，少一层会落到网关默认应用。

```json
{"model": "gpt-image-2.6", "prompt": "手机竖屏实拍，火锅店招牌菜刚出锅，热气腾腾",
 "n": 1, "size": "1024x1536"}
```

| 字段 | 说明 |
|---|---|
| `model` | `gpt-image-2.6` |
| `prompt` | 提示词；空字符串返回 422（`String should have at least 1 character`） |
| `n` | 1~4 |
| `size` | `auto` / `1024x1024` / `1024x1536` / 1536x1024 等；16 的倍数、长短边 ≤3:1、单边 ≤3840、总像素 655,360–8,294,400 |
| `output_format` | png / jpeg / webp / gif |

**计费：6 点/张**，与尺寸、质量、输出格式无关；按 `data` 实际返回张数计费。返回默认 `b64_json`，可加 `--want-url`。

---

## 三、`POST /api/v1/apps/voice_tts/tts` · 口播（同步）

```json
{"text": "在成都春熙路，这家老灶门火锅，中午十一点就开始排队。",
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

---

## 四、`POST /api/v1/apps/media_services_33/music_generate` · 配乐

必填 `model` / `custom_mode` / `instrumental`；`prompt`、`style`、`title`、`duration`、`negative_tags` 等可选。

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "轻快城市探店 vlog，鼓点清楚，适合 25 秒竖屏"}
```

**计费**：该路径没有专属规则，落通配 `*`：`{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}`，即 **上游实际点数 x 2、单笔保底 50 点**。返回里可能有 `audio_url`，也可能是 `task_id`（用 `GET /api/v1/tasks/<id>` 取结果）。

---

## 五、`POST /api/v1/apps/watermark_removal/<接口>` · 同城爆款参考

8 个接口同价，同步返回、没有 `task_id`：

| 接口 | 用途 | 必填 |
|---|---|---|
| `douyin_search_video` | 抖音搜索作品 | `keyword` |
| `xhs_search_note` | 小红书搜索笔记 | `keyword`（可选 page / sort / noteType / noteTime） |
| `douyin_video_detail` | 抖音视频详情 | `videoId` |
| `xhs_note_detail` | 小红书笔记详情 | `noteId` |
| `douyin_user_video_list` | 抖音用户作品 | `secUid` |
| `xhs_user_note_list` | 小红书用户笔记 | `userId` |
| `xhs_user_detail` | 小红书用户详情 | `userId` |
| `remove` | 分享链去水印 | `url` |

**计费**（原文）：

```json
"/api/v1/apps/watermark_removal/*": {
  "mode": "flat", "cost": 100,
  "note": "去水印/分享链解析：固定 100 点/次（上游按请求 20 点，失败亦计）"
}
```

100 点/次 = 1 元，与返回 1 条还是几十条无关。参数不全被上游拦下也照计。

---

## 六、`GET /api/v1/tasks/<task_id>` · 查进度

```bash
curl -H "Authorization: Bearer $A7W_API_KEY" \
  https://api.a7w.cn/api/v1/tasks/tsk_xxxxxxxx
```

- 任务不存在时：HTTP 200 + `{"code":0,"msg":"任务不存在"}`，**0 点**。
- 价目表：`/api/v1/tasks` 是 `per_module`，只在请求体带非空 `module_codes[]` 时按 50 点 x 模块数；本包只发 GET，不触发。
- **应用层 `/query` 不在这里用**：`nano_banana/query` 72 点/次，每查一次都是一次的钱。

---

## 七、`POST /api/v1/upload` · 换白名单地址

`multipart/form-data`，字段名 **`file`**，免费（`/api/v1/pricing` 里 `"/api/v1/upload": {"mode":"flat","cost":0}`）。

返回 `data.url`，形如 `https://oss.gpu.likeadmin.cn/openapi/…`，约 24 小时有效。

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

## 八、探针禁区（2026-11-07 实测，472 点换来的）

| 端点 | 行为 | 本包做法 |
|---|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配计价，**即时结算、不退**（dressing_diffusion 200、nano_banana 72） | 一次都不打 |
| `POST /api/v1/apps/<app>/query` | 每查一次按该应用单价计费（nano_banana/query 72 点/次） | 只走 `GET /tasks/<id>` |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结，再校验失败 refund（净额 0，钱包被短暂动过） | 必填在本地卡死，缺了退 2 |

**完全安全、`doctor` 只用这些**：

```
GET  /api/v1/models           GET  /api/v1/apps        GET  /api/v1/pricing
GET  /api/v1/tasks/<id>       GET  /user/balance       GET  /user/balance/logs
POST /api/v1/upload（缺 file）  POST /api/v1/images/generations {"prompt":""} → 422
POST /api/v1/video/viapi/<tier> {} → 400 empty_url
```

`doctor` 的判据：`400/422` + 参数报错 = 端点存在，停在校验层；`404` + HTML = 未注册；`200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` = 应用层兜底话术，不可信。
