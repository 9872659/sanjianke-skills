# 接口契约（实测原文）

本包只发两类请求：**POST 提交**（清单里指定的端点）与 **GET 免费查询**。
下面所有「实测」日期为 2026-11-08，环境 `https://api.a7w.cn`，只读探针，本轮花费 0 点。

---

## 1. 提交端点（POST，放行表 72 个）

### 1.1 视频后处理（16 档）

| 端点 | 计费 | 单价 |
|---|---|---|
| `POST /api/v1/video/restore` | per_second | 36 点/秒 |
| `POST /api/v1/video/viapi/colorize` | per_second | 9 点/秒 |
| `POST /api/v1/video/viapi/subtitle` | per_second | 9 点/秒 |
| `POST /api/v1/video/viapi/segment` | per_second | 9 点/秒 |
| `POST /api/v1/video/viapi/superres` | per_second | 9 点/秒 |
| `POST /api/v1/video/viapi/enhance` | per_second | 15 点/秒 |
| `POST /api/v1/video/viapi/superres2k` | per_second | 15 点/秒 |
| `POST /api/v1/video/viapi/portrait` | per_second | 18 点/秒 |
| `POST /api/v1/video/viapi/faceswap` | per_second | 20 点/秒 |
| `POST /api/v1/video/viapi/shot` | per_second | 20 点/秒 |
| `POST /api/v1/video/viapi/superres4k` | per_second | 20 点/秒 |
| `POST /api/v1/video/viapi/cartoon` | per_second | 24 点/秒 |
| `POST /api/v1/video/viapi/interp` | per_second | 25 点/秒 |
| `POST /api/v1/video/viapi/castcrew` | per_second | 25 点/秒 |
| `POST /api/v1/video/viapi/delogo` | per_second | 25 点/秒 |
| `POST /api/v1/video/upscale` | per_second | 30 点/秒 |

请求体最小形态：`{"videoUrl": "<平台托管地址>", "duration": <秒>}`；`faceswap` 另需 `faceUrl`。

### 1.2 图片（2 个）

| 端点 | 计费 | 单价 |
|---|---|---|
| `POST /api/v1/images/generations` | per_image | 6 点/张 |
| `POST /api/v1/images/edits` | per_image | 6 点/张（multipart） |

### 1.3 应用提交（21 个，路径形如 `/api/v1/apps/<app>/<api>`）

| 端点 | 点数 |
|---|---|
| `/api/v1/apps/nano_banana/submit` | 72 |
| `/api/v1/apps/aigc_qwen_image/generate/index` | 78 |
| `/api/v1/apps/aigc_qwen_image_pro/generate/index` | 105 |
| `/api/v1/apps/aigc_photo_restore/generate/index` | 105（2K 203） |
| `/api/v1/apps/aigc_wan_image/generate/index` | 203 |
| `/api/v1/apps/dressing_diffusion/submit` | 200 |
| `/api/v1/apps/grok_video/submit` | 300 |
| `/api/v1/apps/happy_horse/submit` | 650 |
| `/api/v1/apps/mmaudio/submit` | 495 |
| `/api/v1/apps/seedance/submit`、`/create` | 11,000 |
| `/api/v1/apps/seedsvc/submit` | 220 |
| `/api/v1/apps/wan/submit` | 800 |
| `/api/v1/apps/smart_clip/submit` | 45 |
| `/api/v1/apps/pic_lipsync/submit` | 保底 50 |
| `/api/v1/apps/action_transfer/submit` | 预扣 300，成片按秒结算 |
| `/api/v1/apps/person_replacement/submit` | 预扣 300，成片按秒结算 |
| `/api/v1/apps/flashvsr/submit` | 10 点/秒，保底 20 |
| `/api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒 |
| `/api/v1/apps/image_human/submit` | 按档位结算，清单写 points |
| `/api/v1/apps/lipsync/submit` | 按上游结算，清单写 points |

### 1.4 语音（4 个）

| 端点 | 计费 |
|---|---|
| `/api/v1/apps/voice_tts/tts_async`、`tts_live` | 约 0.18 点/字 |
| `/api/v1/apps/indextts/submit` | 约 0.18 点/字 |
| `/api/v1/apps/voice_tts/clone_voice` | 600 点/次 |

### 1.5 音频 / 音乐（29 个，`/api/v1/apps/media_services_33/<code>`）

`GET /api/v1/apps` 里 `media_services_33` 正好 29 个接口，价目表 `fixed_price` 全是 `0.0000` 占位，
实际按上游 ×3 结算，所以清单里写 `points`：

```
google_gemini_3_8_flash_lite_tts   google_gemini_3_8_flash_tts   google_gemini_2_5_pro_tts
gemini_omni_audio                  gemini_omni_character
elevenlabs_text_to_dialogue_v3     elevenlabs_text_to_speech_multilingual_v2
elevenlabs_text_to_speech_turbo_2_5
music_generate_voice  music_generate  music_recovery_audio  music_extend  music_sounds
music_timestamped_lyrics  music_check_voice  music_generate_persona  music_replace_section
music_generate_lyrics  music_boost_music_style  music_cover_generate  music_add_vocals
music_separate_vocals  music_generate_midi_from_audio  music_mashup  music_create_music_video
music_upload_and_extend_audio  music_upload_and_cover_audio  music_add_instrumental
music_convert_to_wav_format
```

---

## 2. 免费查询视图

### 2.1 通用任务视图（实测）

```
GET /api/v1/tasks/probe-no-such-task
→ 200 {"code":0,"msg":"任务不存在","data":null}
```

真实任务返回 `data` 对象，本包按 `status` / `state` / `task_status` 取状态，
成功态 `completed / succeeded / success / done / finished`，失败态 `failed / error / cancelled / canceled / timeout / expired`。

### 2.2 视频后处理结果视图（家族实测 2026-11-07）

```
GET /api/v1/video/viapi/result/<taskId>   ← 视频后处理任务的真实视图
GET /api/v1/video/restore/<taskId>        ← restore 档
GET /api/v1/video/viapi/result/probe-no-such-task
→ 404 {"error":{"code":"not_found",...}}
```

**`/api/v1/tasks/<id>` 查不到视频后处理任务**（实测返回「任务不存在」），所以本包按端点分流：
视频档走 `result` 视图，图片与应用档走通用视图。

### 2.3 余额与流水（实测原文）

```
GET /user/balance
→ 200 {"available_points": 999997393470.2579, "points": 999997393470.2579, "frozen": 0,
       "member_points": 0, "yuan": 9999973934.7, "rate": 100, "currency": "points",
       "note": "本平台按用户/Key 隔离统计，非上游租户级数字"}
```

```
GET /user/balance/logs?limit=3
→ 200 {"total": 7888, "logs": [{"at": 1794073572698, "type": "charge", "typeName": "冻结/预扣",
        "kind": "out", "balanceMoving": true, "isSettle": false, "points": -6, "amount": 6,
        "balanceAfter": 999997393470.258, "path": "", "taskId": "",
        "reference": "sync:/api/v1/images/generations", "orderId": "", "model": "", "provider": ""}],
       "inPoints": 274775.5268, "outPoints": 680504.1125, "netPoints": -405728.5857,
       "balanceMoving": -175774.7757, "consumePoints": 74567.18, "rate": 100, "currency": "points"}
```

`limit` 有效，上限 1000。**这是「本轮 0 点」的硬证据**：跑前跑后各读一次 `limit=1`，
最近一笔的 `at` 与 `points` 完全一致，就说明期间没有任何冻结或扣费。

---

## 3. 价目与目录

### 3.1 `GET /api/v1/pricing`（裸对象，不套 code/data）

```json
{"currency": "points", "markupPercent": 20, "site": "...", "note": "...",
 "pricing": {
   "/api/v1/video/viapi/enhance": {"mode": "per_second", "perSecond": 15,
                                    "markupPercent": 0,
                                    "note": "画质综合增强（VIAPI EnhanceVideoQuality）：15 点/秒"},
   "/api/v1/apps/full_video/submit": {"mode": "per_second",
                                      "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60,
                                                          "2K": 80, "4K": 80}},
   "/api/v1/upload": {"mode": "flat", "cost": 0, "markupPercent": 0,
                      "note": "★上传不计费……上传是生成的前置动作、不是可计费服务"},
   "/api/v1/tasks": {"mode": "per_module", "cost": 50}
 }}
```

115 条规则。`/api/v1/upload` 的 `cost` 为 0 —— 上传免费是写进计费引擎的，不是口头约定。

### 3.2 `GET /api/v1/apps`（22 个应用 / 100 个接口）

```json
{"code": ..., "msg": "...", "data": [
  {"id": 19, "name": "人物替换", "code": "person_replacement", "driver_code": "elastic_gpu",
   "billing_mode": 1, "category_code": "other",
   "apis": [{"id": 52, "code": "submit", "name": "提交任务", "method": "POST", "call_type": 2},
            {"id": 53, "code": "query",  "name": "查询任务", "method": "POST", "call_type": 1}]}
]}
```

接口的 `path` 不直接给，按 `/api/v1/apps/<app.code>/<api.code>` 拼。`media_services_33` 下 29 个，
`voice_tts` 6 个，`music_generation` 13 个。

---

## 4. 会扣钱的三类路径（清单里一律拒掉）

| 路径 | 计费 | 实测 |
|---|---|---|
| `GET /api/v1/apps/<app>` | 命中 `/apps/<app>/*` 通配，按该应用 flat 单价 **sync 扣，无退款** | 2026-11-07：dressing_diffusion -200、nano_banana -72、dressing_diffusion -200 |
| `POST /api/v1/apps/<app>/query` | 应用层查询按次计费 | billing 台账里 `*/query` 是独立路径 |
| `POST /api/v1/apps/<app>/submit` 缺必填 | 先 `reserve_sync` 冻结 → 校验失败 → 全额退 | pic_lipsync 冻 250 · image_human 冻 250 · lipsync 冻 150 · seedance 冻 11,000 |

`POST /api/v1/tasks` 属于第四类：`per_module` 50 点，是查询入口，不当提交端点用。

### 判断端点是否存在的免费判据

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | 存在，停在校验层 |
| `404` + HTML | 未注册（SPA 兜底） |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术 |
| `502` + `InvalidMpsUser` | 路由在，上游凭据坏了 |

---

## 5. videoUrl 白名单（实测 400 原文）

```
400 url_not_allowed
"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
 或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）"
```

正确做法：`POST /api/v1/upload`（multipart，字段名 `file`，免费）→ 拿 `data.url` → 写进 `body.videoUrl`。
本包在 `plan` / `run` 阶段做本地预检，不合格当场退 2，省一次往返。

---

## 6. 本包自己的契约

### 6.1 清单行

```json
{"id": "enh-0001", "endpoint": "/api/v1/video/viapi/enhance",
 "body": {"videoUrl": "https://oss.gpu.likeadmin.cn/openapi/a.mp4", "duration": 15},
 "points": 225, "poll": "video", "note": "第 1 集"}
```

### 6.2 状态文件 `<清单>.state.json`

```json
{"version": 1, "manifest": "...", "manifestSha256": "...", "path": "...",
 "createdAt": "2026-11-08T03:07:44", "updatedAt": "2026-11-08T03:08:07",
 "spent": 534.0, "budget": 10000,
 "tasks": {"img-a": {"status": "done", "taskId": "img-1", "points": 6.0,
                     "estimatedPoints": 6.0, "attempts": 1, "why": "查询 /api/v1/tasks/img-1",
                     "http": 200, "at": "2026-11-08T03:08:06"}}}
```

### 6.3 退出码

`0` 成功 · `2` 用法错 · `3` 自检未过 · `4` 缺 `--yes` · `5` 超预算 · `6` 有任务失败 · `1` 内部错 · `130` 中断。

### 6.4 结果文件（`--report DIR`）

- `<清单>.result.json`：`{"summary": {...}, "state": "...", "rows": [...]}`
- `<清单>.failed.jsonl`：每行 `{"id", "endpoint", "error"}`，补跑依据
