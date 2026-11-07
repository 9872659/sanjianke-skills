# 接口契约（实测原文 + 计费口径）

> 全部走 `https://api.a7w.cn`，鉴权 `Authorization: Bearer <你的 Key>`。
> 返回信封：`{"code":1,"msg":"success","data":{…}}`；部分接口是裸对象，本包三种都兜。
> 单位：**1 元 = 100 点**。价目来源 `GET /api/v1/pricing`（2026-11-08 现查，115 条规则）+ 流水实测。

---

## 一、`POST /api/v1/images/generations` · 出图（同步）

端点**必须带 `/api` 前缀**：少一层会被路由到网关默认应用，`model` 被静默忽略。

```json
{"model": "gpt-image-2.6", "prompt": "知识付费招生素材，AI 短剧变现训练营，一个人对着电脑停住的瞬间",
 "n": 2, "size": "1152x1536", "output_format": "png"}
```

| 字段 | 说明 |
|---|---|
| `model` | `gpt-image-2.6` |
| `prompt` | 必填；空字符串返回 **422** `prompt: String should have at least 1 character` |
| `n` | **1~4**，一次多图，按张计费 |
| `size` | `auto` / `1024x1024` / `1024x1536` / `宽x高`；16 的倍数、长短边 ≤3:1、单边 ≤3840、总像素 655,360~8,294,400 |
| `output_format` | png / jpeg / webp / gif |

**计费**：**6 点/张**，与尺寸、质量、输出格式无关，按响应 `data` 里**实际返回张数**计。这个价在 `/api/v1/pricing` 里没有独立的键（走模型线结算），6 点是流水实测值：`1024x1024` 一张 43.6 秒出图、扣 6 点。返回默认 `b64_json`，本包自动解码落盘成 png。

知识付费的用法：**先出无字底版**（封面、大纲、价格卡都是底版），文字用排版叠上去。AI 出中文容易错字，底版 + 叠字比直接出带字图稳，换价也不用重跑。

---

## 二、`POST /api/v1/images/edits` · 改图（同步，multipart）

有讲师照、教室实拍时走这条，人脸与场景不走样。字段与出图相同，文件字段名 **`image`**：

```
multipart/form-data
  model         gpt-image-2.6
  prompt        "把这张讲师照改成竖版招生封面，保留本人五官与穿着"
  n             1
  size          1152x1536
  output_format png
  image         <本地文件>
```

**计费**：同样 **6 点/张**。

---

## 三、`POST /api/v1/apps/nano_banana/submit` · 参考图（异步）

```json
{"prompt": "讲师形象，同一人三个机位，工作室背景",
 "model": "nano-banana", "resolution": "1K", "aspect_ratio": "3:4"}
```

带参考图时加 `action: "edit"` 与 `image_urls: ["https://oss.gpu.likeadmin.cn/openapi/…"]`（地址先用 `/api/v1/upload` 换）。

**计费**（`/api/v1/pricing` 原文）：

```json
"/api/v1/apps/nano_banana/*": {
  "mode": "flat", "cost": 72, "markupPercent": 0,
  "note": "AI商品图 = 固定 72 点/次；商品多角度 = 25 点 x 选中视角数（请求体带 views[] 时生效）"
}
```

**72 点/次**是 flat，与返回几张无关。异步返回 `task_id`，**查结果只走 `GET /api/v1/tasks/<id>`**；
`POST /api/v1/apps/nano_banana/query` 每查一次 = 72 点，轮询 30 次就是 2,160 点。

---

## 四、`POST /api/v1/apps/full_video/submit` · 痛点短视频（异步）

```json
{
  "model": "full-video",
  "content": [
    {"type": "text", "text": "竖屏招生短视频，0-3 秒 学员处境特写，3-9 秒 课程交付物，9-15 秒 讲师出镜"},
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
| `aigc_watermark` | bool | 否 | 是否加生成标识，默认 false |

**计费**（`/api/v1/pricing` 原文）：

```json
"/api/v1/apps/full_video/submit": {
  "mode": "per_second",
  "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
  "note": "2026-11-06 站主定价：480P 0.14 元/秒、768P 0.28、1080P 0.60、2K/4K 0.80"
}
```

15 秒 1080P = 60 x 15 = **900 点 = 9 元**。24 秒要拆 15 + 9 两段，按总秒数计费。

**限制**：首帧 / 尾帧各最多 1 张；参考图最多 9 张；参考视频与参考音频各最多 3 个；首尾帧模式与参考媒体模式不混用；768P 及以上文本上限 5,000 字符。

知识付费的用法：一条 15 秒痛点视频正好覆盖「处境 → 交付物 → 讲师一句话」三段，不要再长；长片属于正课，交 `sanjianke-course-video`。

---

## 五、`POST /api/v1/apps/voice_tts/tts` · 讲师口播（同步）

```json
{"text": "8 年影视后期讲师，带过 1200 名学员", "model": "s2-pro", "format": "mp3"}
```

| 字段 | 说明 |
|---|---|
| `text` | 必填；同步接口建议 500 字内，长文走 `tts_async` |
| `model` | `s1` / `s2-pro`，默认 `s2-pro` |
| `format` | mp3 / wav / ogg / opus / pcm |
| `reference_id` | 克隆音色 ID，可选（讲师真声克隆走这里） |

返回 `data.audio_url`。

**计费**：`/api/v1/apps/voice_tts/*` 是 `mode=flat, cost=0, markupPercent=200`，note 原文
「对外价 = 上游实际点数（响应 `usage.points_cost` / `actual_points`，单位是点）x 3，单笔保底 > 0」。
实测基准：`tts_live` 33 字上游 1.98 点 → 我方 5.94 点，所以本包按 **0.18 点/字**估，实际以 `usage.points_cost` 为准。
60 字讲师背书 ≈ 11 点 = 0.11 元。

---

## 六、`POST /api/v1/apps/media_services_33/music_generate` · 招生配乐（异步）

必填 `model` / `custom_mode` / `instrumental`；`prompt`、`style`、`title`、`duration`、`negative_tags` 等可选。

```json
{"model": "V6", "custom_mode": false, "instrumental": true,
 "prompt": "轻钢琴渐强，温暖，适合 30 秒招生短片"}
```

**计费**：该路径没有专属规则，落通配 `*`：`{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}`，
即**上游实际点数 x 2、单笔保底 50 点**。返回里可能有 `audio_url`，也可能是 `task_id`（用 `GET /api/v1/tasks/<id>` 取结果）。
`media_services_33` 在架 29 个接口（`/api/v1/apps` 现查，2026-11-08 实测 29），配乐取 `music_generate`。

---

## 七、`GET /api/v1/tasks/<task_id>` · 查进度（免费）

```bash
curl -H "Authorization: Bearer $A7W_API_KEY" \
  https://api.a7w.cn/api/v1/tasks/tsk_xxxxxxxx
```

- 任务不存在时：HTTP 200 + `{"code":0,"msg":"任务不存在"}`，**0 点**。
- 价目表里 `/api/v1/tasks` 是 `per_module`，**只在请求体带非空 `module_codes[]` 时**按 50 点 x 模块数；本包只发 GET，不触发。
- 应用层 `/query` 不在本包的调用路径里。

---

## 八、`POST /api/v1/upload` · 换白名单地址（免费）

`multipart/form-data`，字段名 **`file`**。价目表 `"/api/v1/upload": {"mode":"flat","cost":0}`，
note 原文「上传不计费（2026-10-04 站主批准）。上传是生成的前置动作、不是可计费服务」。

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

**本地讲师照、教室实拍、封面底版都要先 upload**，再喂给 `img --ref` / `film --image`。

---

## 九、尺寸校验（`qc` 与 `img` 共用的四条）

| 规则 | 说明 |
|---|---|
| 16 的倍数 | `720x1280`、`1024x1024`、`1024x1280`、`1152x1536`、`1280x720` 都合规 |
| 长短边 ≤ 3:1 | 9:16 = 1.78、4:5 = 1.25，都过 |
| 单边 ≤ 3840 | 上架尺寸 1920 是后期放大，不占生成预算 |
| 总像素 655,360~8,294,400 | 800x800 只有 640,000，低于下限，所以 1:1 请求 1024x1024 |

知识付费的五个版位对应关系：3x4 → 1152x1536、9x16 → 720x1280、1x1 → 1024x1024、16x9 → 1280x720、4x5 → 1024x1280。

---

## 十、探针禁区（2026-11-07 实测，472 点换来的）

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

`doctor` 的判据：`400/422` + 参数报错 = 端点存在，停在校验层；`404` + HTML = 未注册；
`200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` = 应用层兜底话术，不可信。

2026-11-08 本轮实测：`doctor` 10 项全 √（余额 999,997,393,482 点 · 目录 22 个应用 · media_services_33 在架 29 个接口 · full_video 5 档按秒价全一致 · nano 72 / 通配保底 50 / upload 0 · 出图 422 · 视频线 400 empty_url · 任务查询 200 · 上传口 200）。自检前后 `/user/balance/logs` 最新一笔都是 **2026-11-07 23:54:08 退款 300 点**，**本轮 0 点**。
