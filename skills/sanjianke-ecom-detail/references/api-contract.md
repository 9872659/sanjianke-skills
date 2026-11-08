# 接口契约（实测原文 + 文档口径）

> 网关：`https://api.a7w.cn`，API 前缀 `/api/v1`，鉴权 `Authorization: Bearer <你的 Key>`
> 采集时间：2026-11-08（本包 7 文件版本 1.0.0）
> 所有数值都是当天现查 `GET /api/v1/pricing`、`GET /api/v1/models`、`GET /api/v1/apps` 与四类探针得来的。

---

## 一、价目（`GET /api/v1/pricing` 原文，115 条规则）

| 键 | mode | cost | note 原文（节选） |
|---|---|---|---|
| `/api/v1/upload` | flat | **0** | 「上传不计费（2026-10-04 站主批准）。上传是生成的前置动作、不是可计费服务」 |
| `/api/v1/apps/nano_banana/*` | flat | **72** | 「AI 商品图 = 固定 72 点/次；商品多角度 = 25 点 × 选中视角数（请求体带 views[] 时生效，不带 views 时仍按本固定价 72）」 |
| `/api/v1/apps/dressing_diffusion/*` | flat | **200** | 「固定 200 点/次」 |
| `/api/v1/tasks/*` | — | — | 任务查询，只读 |

**`/api/v1/images/generations` 不在价目表里。** 115 条规则中没有这一条，
所以 6 点/张的口径来自接口文档与流水实扣（2026-11-07 一笔 `-6`），本包因此用
「带 model 的空 prompt → 422」验端点，不拿价格表当证据。

---

## 二、文生图（本包默认线，6 点/张）

```
POST https://api.a7w.cn/api/v1/images/generations
Content-Type: application/json
Authorization: Bearer <key>
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | `gpt-image-2.6`（目录里 316 个模型，这个名字带点号，别写成 `gpt-image-2-6`） |
| `prompt` | 是 | 提示词；空字符串 → **422** |
| `n` | 否 | 张数 **1–4**，默认 1。本包按位出图，固定 `n=1` |
| `size` | 否 | `auto` / `1k` / `2k` / `4k` / `宽x高`（如 `1024x1024`、`1200x1600`） |
| `output_format` | 否 | `png`（默认）/ `jpeg` / `webp` / `gif`。本包只开放前三种 |
| `response_format` | 否 | 默认 `b64_json`；要链接就传 `url`（约 3 小时有效） |
| `background` | 否 | `auto` / `transparent` / `opaque`（透明只配 png / webp） |
| `quality` | 否 | 仅提示，**不影响价格** |

### 自定义尺寸四条硬约束（不合规 → 400，不扣费）

- 宽高都是 **16 的倍数**
- 长边 / 短边 **≤ 3:1**
- 单边 **≤ 3840**
- 总像素 **655,360 – 8,294,400**

**这就是 `--platform taobao` 请求 1024×1024 而不是 800×800 的原因**：
800×800 = 640,000 像素，差 15,360 才到下限。

### 返回

```json
{
  "created": 1793900000,
  "data": [
    {"b64_json": "iVBORw0KGgo...", "revised_prompt": "…", "width": 1024, "height": 1024}
  ],
  "usage": {"input_tokens": 13, "output_tokens": 1056, "total_tokens": 1069},
  "size": "1024x1024",
  "output_format": "png"
}
```

`data` 里每项带 `b64_json` **或** `url`，两种都要处理；本包两种都落盘。
计费按 `data` 里**实际返回的张数**，`n=1` 只回 0 张就不扣费。

---

## 三、改图（带商品实拍图，同样 6 点/张）

```
POST https://api.a7w.cn/api/v1/images/edits
Content-Type: multipart/form-data
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | `gpt-image-2.6` |
| `prompt` | 是 | 想怎么改；仍要写清画面（比如「换成米白背景、保留面料纹理」） |
| `image` | 是 | 参考图文件，可多张（每次最多 20 张）；本包用 `--ref` 传本地实拍图 |
| `size` / `n` / `output_format` | 否 | 同文生图 |

实测两笔 `sync:/api/v1/images/edits` 各 **−6 点**，与文生图同价 —— 这是电商最划算的一条：
商品本体不走样，只重画背景与构图。

---

## 四、参考图出图（nano_banana，72 点/次，异步）

```
POST https://api.a7w.cn/api/v1/apps/nano_banana/submit
Content-Type: application/json
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `prompt` | 是 | 提示词 |
| `model` | 否 | `nano-banana`（默认）/ `nano-banana-2` / `-2-lite` / `-pro` / `:official` 系列 |
| `action` | 否 | `generate` / `edit`（`edit` 时 `image_urls` 必填） |
| `image_urls` | 条件 | 参考图地址数组，最多 12 张；走白名单地址（见第六节） |
| `resolution` | 否 | `1K` / `2K` / `4K` |
| `aspect_ratio` | 否 | `auto` / `1:1` / `16:9` / `9:16` / `4:3` / `3:4` / `3:2` / `2:3` / `5:4` / `4:5` / `21:9` |

返回 `task_id`，**用 `GET /api/v1/tasks/{task_id}` 查**（免费）。
价格表原文：带 `views[]` 时按 25 点 × 视角数计费，不带就是固定 72。

---

## 五、换装（dressing_diffusion，200 点/次，异步）

```
POST https://api.a7w.cn/api/v1/apps/dressing_diffusion/submit
Content-Type: application/json
```

```json
{
  "model_url": "https://oss.gpu.likeadmin.cn/openapi/model.jpg",
  "garment": {"data": [{"category": "upper", "url": "https://oss.gpu.likeadmin.cn/openapi/shirt.jpg"}]}
}
```

- `model_url` 必填（模特图地址）
- `garment` 必填，`data[]` 里每项 `category` 取 `upper` / `bottom` / `full`
- 返回 `task_id`，文档口径 10–30 秒出图
- **空 body 也会建单**，所以本包缺参在本地就退 2，一个请求都不发

---

## 六、上传（0 点，拿白名单地址）

```
POST https://api.a7w.cn/api/v1/upload
Content-Type: multipart/form-data    字段名固定是 file
```

返回：

```json
{"code": 1, "data": {"url": "https://oss.gpu.likeadmin.cn/openapi/xxxx.jpg",
                     "path": "...", "name": "...", "size": 6103,
                     "mime_type": "image/png", "type": "image"}}
```

**空表单的实测返回**（本包 `doctor` 用这条探针，0 点）：

```json
{"code": 0, "msg": "请使用 file 字段提交一个文件", "data": null}
```

上游素材地址白名单（实测报错原文）：

- 本站：`*.a7w.cn`（含 `vr.a7w.cn`）
- 本站七牛：`cdn2.jiujiushuyuan.cn/vr/…`
- 本站上传接口：`oss.gpu.likeadmin.cn/openapi/…` ← **本包 upload 返回的就是这个**

外站地址（`https://example.invalid/x.mp4`）实测 `400 url_not_allowed`。

---

## 七、任务查询（免费，本包唯一的轮询口）

```
GET https://api.a7w.cn/api/v1/tasks/{task_id}
```

假 id 的实测返回（说明路由在、且不扣费）：

```json
{"code": 0, "msg": "任务不存在", "data": null}
```

**应用层 `query` 是另一条计费路**：`nano_banana/query` 实测 72 点/次。
本包 `status` 一次应用层 query 都不发。

---

## 八、探针纪律（2026-11-07 用 472 点买来的）

### 会真扣、不退（`sync:` 即时结算）

```
❌ GET /api/v1/apps/<app>
   dressing_diffusion  200 点/次
   nano_banana          72 点/次
   pic_lipsync          保底 50 点
   image_human          保底 250 点
```

实测流水：

```
19:35:08  -200  sync:/api/v1/apps/dressing_diffusion
19:35:11   -72  sync:/api/v1/apps/nano_banana
19:35:34  -200  sync:/api/v1/apps/dressing_diffusion
```

### 会预冻、失败全额退（`reserve_sync:`）

```
⚠ POST /api/v1/apps/<app>/submit 缺必填
   → 先 reserve_sync 冻结，再参数校验失败 → refund 全额退
   净额 0，但钱包被短暂动过
```

所以「缺必填参数会停在扣费之前」这句在应用层不成立，本包一律本地先校验。

### 完全安全（本包只打这些）

```
✅ GET  /api/v1/models
✅ GET  /api/v1/apps               列表，不读 /apps/<app>
✅ GET  /api/v1/pricing
✅ GET  /api/v1/tasks/<id>
✅ GET  /user/balance
✅ GET  /user/balance/logs         limit 上限 1000
✅ POST /api/v1/upload             空表单 / 真文件都 0 点
✅ POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""} → 422
```

### 判断端点是否存在的免费判据

| 返回 | 含义 |
|---|---|
| `400` / `422` + 参数报错 | 端点在，停在校验层 |
| `404` + HTML | 前缀下没有这个端点 |
| `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术，不可信 |
| `502` + `InvalidMpsUser` | 路由在，上游凭据坏了 |

---

## 九、错误码（images 线）

| 情况 | 状态码 | 提示 |
|---|---|---|
| 尺寸不合规 | 400 | width/height must be multiples of 16 等 |
| `output_format` 超出枚举 | 400 | Supported: 'png','jpeg','webp','gif' |
| 透明配 jpeg / gif | 400 | Transparent backgrounds are only supported with 'png' or 'webp' |
| `n` 越界 | 400 | expected an integer in [1, 4] |
| 缺 `prompt` | **422** | String should have at least 1 character |
| 模型名错 / 无权限 | 404 | The model `xxx` does not exist or you do not have access to it |

---

## 十、本包实测记录（2026-11-08）

```
GET  /api/v1/pricing          200 · 115 条规则 · upload=0 nano=72 dress=200
GET  /api/v1/models           200 · 316 个模型 · gpt-image-2.6 在架
GET  /api/v1/apps             200 · 22 个应用 · nano_banana / dressing_diffusion 都在
POST /api/v1/images/generations  {"model":"gpt-image-2.6","prompt":""}
                              422 · prompt: String should have at least 1 character
POST /api/v1/upload            200 · {"code":0,"msg":"请使用 file 字段提交一个文件"}
GET  /api/v1/tasks/probe-no-such-task
                              200 · {"code":0,"msg":"任务不存在"}
GET  /user/balance            200 · 可用 / 冻结 / rate=100
GET  /user/balance/logs       200 · 共 7,903 条流水

本轮花费 0 点：余额前后一致、流水 7,903 → 7,903 条、会话窗口内新增 0 条。
```
