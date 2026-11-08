# 接口契约（实测原文 + live 定价）

三个应用共用一套平台外壳：

```
接口根地址   https://api.a7w.cn/api/v1
提交         POST /apps/{app}/submit        JSON，返回 task_id
应用级查询   POST /apps/{app}/query         body {"task_id": "..."}
平台任务查询 GET  /tasks/{task_id}          状态 + 结果 + usage
价目         GET  /pricing?type=app_api&app_code=&api_code=
临时上传     POST /upload                   multipart 单字段 file（不计费）
```

**三个应用都只有 `submit` + `query` 两个接口。**
`create / remove / cancel / callback / list / result / status` 这七个动作在应用层全部不存在。

---

## 1. `pic_lipsync`（图片数字人，app id=27）

`POST /api/v1/apps/pic_lipsync/submit`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `image_url` | string | **是** | — | 人物图片 URL |
| `audio_url` | string | **是** | — | audio 模式是驱动音频；**text 模式是参考音色** |
| `mode` | string | 否 | `audio` | `audio` 音频驱动 / `text` 文案驱动 |
| `content` | string | text 模式必填 | — | 图片人物用参考音色朗读的文案 |
| `quality` | string | 否 | `standard` | `fast` / `standard` / `max`（**档位真名是 quality，不是 mode**）|
| `model` | string | 否 | `super-lipsync-pro` | 枚举里只有这一个值 |
| `prompt` | string | 否 | — | 人物动作、表情、画面风格 |

`POST /api/v1/apps/pic_lipsync/query` → `{"task_id": "task_xxx"}`

### 实测原文（缺一个必填：参数校验报错，不建任务；但会**先预扣再退**，见第 7 节）

```json
{"code":0,"msg":"请提供 image_url","data":null}
{"code":0,"msg":"text 模式请提供 audio_url 作为参考音色","data":null}
```

第二条是本包最重要的卖点注解：**文案驱动省掉录音，但省不掉「参考音色」**。
`mode=text` 时 `audio_url` 不是驱动音频，而是"用谁的声音来念"。

### 计费（2026-10-10 站主批准，live 定价接口原文）

```json
"/api/v1/apps/pic_lipsync/submit": {
}
```

- 公开文档写「单笔保底 50 点」；`cost` 按 50 点下限预估，不低估

---

## 2. `image_human`（全驱动数字人，app id=15）

`POST /api/v1/apps/image_human/submit`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `file_url` | string | **是** | — | 人物图片 URL |
| `ref_file_url` | string | **是** | — | 驱动音频 URL |
| `duration` | number | 否 | — | 输入音频秒数；**给了它价格才被费率卡锁死** |
| `mode` | string | 否 | schema 写 `standard`，计费卡写 `fast` | `fast` / `standard` / `2k` / `4k` |
| `resolution` | string | 否 | — | `2k` / `4k`，`mode` 的兼容别名 |
| `prompt` | string | 否 | 人物说话自然，面对镜头… | 画面提示词 |

`POST /api/v1/apps/image_human/query` → `{"task_id": "task_xxx"}`

### 🔴 默认档位自相矛盾（本包用必填参数堵死）

| 来源 | 字段 | 值 |
|---|---|---|
| `GET /api/v1/apps/image_human` | `default_params.mode` / `params_schema.mode.default` | `standard` |
| `GET /api/v1/pricing` | `defaultModel` + note「缺省 mode=fast（=10）」 | `fast` |

不显式传 `mode` 时：**出片按 standard，收钱按 fast**（15 vs 10 点/秒）。
所以 `drive --mode` 是必填参数，本包永不下发省略 mode 的请求。

### 计费（live 定价接口原文）

```json
"modelRates": {"fast": {"*": 10}, "standard": {"*": 15}, "2k": {"*": 30}, "4k": {"*": 60}},
"defaultModel": "fast"
```

### 实测原文

```json
// 只给 file_url + ref_file_url，缺 duration
{"code":0,"msg":"无法从该地址下载媒体，请确认链接可公网访问、未过期，且允许本平台服务器拉取（防盗链/OSS 权限需放行）。 详情：Could not resolve host: example.invalid; Name or service not known","data":null}
```

缺 `duration` 时它先去下载 ref 音频算秒数 —— 下载不到就停在建任务之前。

---

## 3. `lipsync`（数字人对口型，app id=10）

`POST /api/v1/apps/lipsync/submit`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `video_url` | string | **是** | — | 已有视频 URL |
| `audio_url` | string | **是** | — | 新配音音频 URL |
| `model` | string | 否 | `xiaojiayu1.0` | `xiaojiayu1.0` / `2.0` / `3.0` |
| `fps` | string | 否 | — | 输出帧率 |
| `video_params` | object | 否 | — | 画面参数对象 |
| `mode` | string | 否 | `async_query` | 内部字段，一般不用传 |

`POST /api/v1/apps/lipsync/query` → `{"task_id": "task_xxx"}`

### 计费（live 定价接口原文）

```json
"model_rates": {"xiaojiayu1.0": 0.9, "xiaojiayu2.0": 4.5, "xiaojiayu3.0": 4.5},
```

### 实测原文

```json
{"code":0,"msg":"当前请求未命中可用计费规格，请检查模型是否在支持范围内。","data":null}
```

这个应用先解析计费规格、后校验参数，所以缺参时看到的是这句。

---

## 4. 任务查询（三条路，只有一条是平台线）

| 路径 | 形态 | 实测 |
|---|---|---|
| `GET /api/v1/tasks/{task_id}` | 平台任务线 | `{"code":0,"msg":"任务不存在","data":null}`；存在时 `data` 里带 `status` / `result` / `usage` |
| `POST /api/v1/apps/{code}/query` | 应用级查询 | body `{"task_id": "..."}`，结果在 `data.result.data` |
| `GET /api/v1/videos/{task_id}` | 另一套（非平台线） | HTTP 400 `{"code":"task_not_exist","message":"task_not_exist","data":null}` |

`status` 枚举：`pending` / `processing` / `completed` / `failed` / `cancelled`。

### 三个真会踩的形态坑

1. **`result` 是双重身份字段**。任务完成后 `data` 里也有一个 `result`，
   和「中转包装层」的 `result` 同名。无脑往下钻会丢掉 `status` → 轮询永远等不到终态。
2. **视频地址不在固定字段**。按优先级兜：`video_url` → `video_uri` → `output_url` → `result_url`，
   本包 `find_media` 直接递归扫所有 http 字符串 + 视频后缀。
3. **刚 `completed` 时结果地址偶尔是空串**（实测竞态，数字人/剪辑/TTS/生图都吃）。
   本包取不到地址时提示「隔几秒再查一次」。

---

## 5. 平台信封

```jsonc
// 成功
{"code":1,"msg":"success","data":{"task_id":"task_xxx","frozen_points":"17.52"}}
// 参数/计费错误
{"code":0,"msg":"请提供 image_url","data":null}
// 网关错误对象
{"error":{"message":"点数余额不足","type":"insufficient_points","code":"insufficient_points"}}
```

判据：`code==1` 且 `data` 非空才算成功；其余一律取 `msg` / `message` 当错误文案。

---

## 6. 本轮实测记录（净花费 0 点）

```
探针前  GET /api/v1/tasks → 20 条，最新 completed_at 2026-11-07T09:51:39Z
探针    4 发「缺一个必填」的 submit（pic_lipsync×2 / image_human / lipsync）
        + 3 发 quality=bogus（每发同样缺一个必填）
探针后  GET /api/v1/tasks → 仍是 20 条，task_id 一条不差
        三个数字人应用相关任务 1 条（pic_lipsync，completed_at 06:22:43Z，早于本次会话）
代价    净 0 点（10 对「冻结 −N → 退款 +N」，见下）
```

---

## 7. 🔴 应用层 submit 是「先预扣、后验参」

这是本轮最值钱的一条实测，也是 `doctor` 为什么不发 submit 的原因。

`GET /user/balance/logs?limit=1000` 的实际流水（时间 UTC）：

```
11:37:01Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/pic_lipsync/submit
11:37:02Z  退款       +250  ref=refund:sync:/api/v1/apps/pic_lipsync/submit
11:37:05Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/pic_lipsync/submit
11:37:07Z  退款       +250  ref=refund:sync:/api/v1/apps/pic_lipsync/submit
11:37:16Z  冻结/预扣   -250  ref=reserve_sync:/api/v1/apps/image_human/submit
11:37:19Z  退款       +250  ref=refund:sync:/api/v1/apps/image_human/submit
11:37:21Z  冻结/预扣   -150  ref=reserve_sync:/api/v1/apps/lipsync/submit
11:37:22Z  退款       +150  ref=refund:sync:/api/v1/apps/lipsync/submit
```

**连「缺 image_url」「缺 audio_url」这种必然被校验拦下的请求，也是先扣再退。**
冻结额就是各自规则的保底价：`pic_lipsync` 与 `image_human` 各 250 点，`lipsync` 150 点。
净额 0，但钱包被短暂动过 —— 所以：

1. `doctor` 改成**只发四个只读 GET**（`/apps`、`/pricing`、`/tasks/{id}`、`/user/balance`），
   端点存在性用定价表里已配价的三条规则证明，一次 submit 都不发。
2. 任何 `submit` 都只允许出现在**付费命令**里，并且必须先过 `--budget` 与 `--yes` 两道闸门。

> 另一条同源实测：`GET /api/v1/apps/{app}`（读单个应用 schema）会命中
> `/api/v1/apps/<app>/*` 的通配计价（如 `dressing_diffusion` 200 点、`nano_banana` 72 点），
> **是 charge 不是 reserve，没看到退款**。本包全程不调用它，应用参数一律从
> 平台定价表与本地已抓取的 schema 快照里取。

