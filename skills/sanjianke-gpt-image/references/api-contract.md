# 接口契约（文档原文 + 实测）

> 权威来源：网关文档 `https://api.a7w.cn/docs.html#/docs/gpt-image-2-6-xt`（「GPT Image 2.6（轻量线路）」）
> 数据源：`https://api.a7w.cn/assets/docdata.json`
> 本文件的每条结论都经过真机验证（2026-11-07）。

---

## 一、接入信息（文档原文）

| 项目 | 值 |
|---|---|
| 接口根地址 | `https://api.a7w.cn/api/v1` |
| OpenAI SDK 的 `base_url` | `https://api.a7w.cn/api/v1` |
| 鉴权 | `Authorization: Bearer <你的 API 密钥>` |
| 模型 ID | `gpt-image-2.6` |
| 调用方式 | **同步**（请求完成后直接返回图片）|

- 客户端超时建议 **180 秒以上**：一张图通常 20–50 秒。
- `gpt-image-2.6` / `-sunburst` / `-flare` 三个名字**参数、限制、返回格式都一样**，
  **不能通过名字选速度或画质档位**。

---

## 二、文生图

```
POST https://api.a7w.cn/api/v1/images/generations
Content-Type: application/json
Authorization: Bearer <key>
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | `gpt-image-2.6` |
| `prompt` | 是 | 提示词 |
| `n` | 否 | 张数 **1–4**，默认 1 |
| `size` | 否 | 见下，默认 `auto` |
| `response_format` | 否 | `b64_json`（默认）或 `url` |
| `output_format` | 否 | `png`（默认）/ `jpeg` / `webp` / `gif` |
| `output_compression` | 否 | 0–100，只对 jpeg / webp 生效 |
| `background` | 否 | `auto`（默认）/ `transparent` / `opaque` |
| `quality` | 否 | `auto`/`low`/`medium`/`high`/`xhigh`/`max`，仅作提示，**不影响价格** |

### 尺寸

| 写法 | 结果 |
|---|---|
| 不传或 `auto` | 由模型决定，常见 1448×1086、1254×1254 |
| `1k` / `2k` / `4k` | 1024×1024 / 2048×2048 / 3840×2160 |
| `宽x高`（如 `1536x1024`） | 按请求尺寸返回 |

自定义尺寸需**同时**满足（否则 400，不扣费）：

- 宽高都是 **16 的倍数**
- 长边与短边比 **≤ 3:1**
- 单边 **≤ 3840**
- 总像素 **655,360 – 8,294,400**

### 背景

- `opaque`：不透明
- `transparent`：尽量透明，**不保证成功**，以响应 `background` 为准；**不能和 jpeg / gif 一起用**（400）
- `auto`：不处理

---

## 三、⚠️ 端点路径（这条最容易错）

**实测对比：**

| 路径 | 带 `{"model":…,"prompt":""}` 的返回 | 判定 |
|---|---|---|
| `POST /api/v1/images/generations` | **422** `prompt: String should have at least 1 character` | ✅ **正确**（与文档一致）|
| `POST /v1/images/generations` | 400 `prompt is required` | ❌ 另一套旧路由，**忽略 model** |

⚠️ **空 body `{}` 打到 `/api/v1/images/generations` 会返回 404（HTML 兜底）** ——
因为它**必须靠 body 里的 `model` 才能路由**。所以探端点时必须带 `model`，否则会误判成"端点不存在"。

**这是本包 `doctor` 的设计依据**：发 `{"model":"gpt-image-2.6","prompt":""}`，期待 **422**。

### 错误路由的后果（实测）

往 `/v1/images/generations` 传 `model: "gpt-image-2.6"`、甚至传 `no-such-model-xyz`，
**两次都路由到 `nano_banana` 并各扣 72 点**（`model_code=nano_banana/submit`），**且不报错**。

**所以"能出图"不等于"用对了模型"。**

---

## 四、图生图

```
POST https://api.a7w.cn/api/v1/images/edits
Content-Type: multipart/form-data   ← curl 用 -F 自动设置，不要手写
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | `gpt-image-2.6` |
| `prompt` | 是 | 想怎么改图 |
| `image` | 是 | 参考图文件；多张时重复传 `image[]`，**每次最多 20 张** |
| `mask` | 否 | 蒙版文件（当提示，不保证严格贴合边界）|
| `markup` | 否 | 标注层文件（透明背景 PNG，只对第一张生效）|
| 其他 | 否 | `size`/`n`/`response_format`/`output_format`/`output_compression`/`background`/`quality` 同文生图 |

整个请求建议 **不超过 50 MB**。

### 标注层（`markup`）要求

- 只对**第一张图**生效，其他图仍作参考图
- 必须是**含透明像素的 PNG**，宽高与第一张图相同
- 第一张图和标注层都不能超 16,777,216 像素；标注层不超 50 MB
- 每次**只能一个**标注层，不能和 `mask` 同用，不支持 `file_id`
- 不符合 → 400，**不扣费**

> 标记只用来指位置，一般不会留在结果里；**这不是局部锁定，整张图会重新生成**。

---

## 五、GIF 动图

传 `output_format=gif`，或提示词里明确要 GIF。

- **尺寸和帧数由模型决定**（实测约 8–16 帧，边长 170–900 像素）；
  `size`、`frame_count`、`frame_duration_ms` **对 GIF 不生效**
- `url` 模式返回 `.gif` 链接；`b64_json` 解码后就是 GIF
- **按一张计费**
- 偶尔只出静态图（返回 PNG）
- `background=transparent` **不能**和 `output_format=gif` 同用（400）
- 显式传 `jpeg`/`webp` 时返回首帧静态图
- 耗时更长，最长见过约 130 秒

---

## 六、返回结果

```json
{
  "created": 1793900000,
  "data": [
    { "b64_json": "iVBORw0KGgo...", "revised_prompt": "一只橘猫在窗台晒太阳",
      "width": 1024, "height": 1024 }
  ],
  "usage": { "input_tokens": 13, "output_tokens": 1056, "total_tokens": 1069 },
  "background": "auto",
  "output_format": "png",
  "quality": "auto",
  "size": "1024x1024"
}
```

- `data` 每项带 **`b64_json` 或 `url`**，两种都要处理
- `usage` 仅供参考，**费用按张计算**
- `n > 1` 时 `data` 内容准确，顶层 `size`/`output_format` 可能是请求值

**图片链接**：有效期约 **3 小时**，请及时下载；**原样使用**（追加查询参数会 404）；
下载**不需要密钥**；用 Python 标准库 `urllib` 需**自设 `User-Agent`**（默认值会被拒 403），
`requests` / `httpx` / `curl` / 浏览器不受影响。

---

## 七、流式

传 `stream: true` 时响应为 SSE，生成完成后只有一个事件：

```text
event: image_generation.completed
data: {"type":"image_generation.completed","b64_json":"iVBORw0KGgo...","usage":{...}}
```

图生图事件名是 `image_edit.completed`。流式**只能配 `b64_json`**，配 `url` 会返回 502（不扣费）。

---

## 八、价格

| 张数 | 价格 |
|---|---|
| 1 张 | **6 点（¥0.06）** |
| 2 张 | 12 点 |
| 3 张 | 18 点 |
| 4 张 | 24 点 |

- **按张计费**，与尺寸、质量、输出格式**都无关**
- 按 `data` 里**实际返回的张数**计费
- 参数错误、请求失败、没返回图片 → **不扣费**
- 客户端中途断开或流式中断 → **仍按请求张数计费**
- **内容审核拒绝** → 返回错误并说明原因，**不扣费**

---

## 九、与标准 Images 接口的差异

| 项目 | 这里的行为 |
|---|---|
| `n` | 最大 **4** |
| `response_format` | 支持 `url` |
| `data[].width` / `height` | **额外返回** |
| `output_format=gif` | 支持；帧数/时长/尺寸由模型决定；偶尔只出静态 PNG |
| `output_format=svg` | 返回 **400**；**不支持 SVG** |
| `complexity` / `frame_count` / `frame_duration_ms` / `moderation` / `partial_images` / `input_fidelity` | **传了不报错，但不起作用** |
| `markup` 的 `file_id` | 不支持 |

---

## 十、错误码

| 情况 | 状态码 | `param` | 提示 |
|---|---|---|---|
| 尺寸不符合要求 | 400 | `size` | width/height must be multiples of 16 等 |
| `output_format` 不支持 | 400 | `output_format` | Supported: 'png','jpeg','webp','gif' |
| 透明背景配 jpeg/gif | 400 | `output_format` | Transparent backgrounds are only supported with 'png' or 'webp' |
| `background` 不支持 | 400 | `background` | Supported: 'transparent','opaque','auto' |
| `n` 超范围 | 400 | `n` | expected an integer in [1, 4] |
| `output_compression` 超范围 | 400 | `output_compression` | expected an integer in [0, 100] |
| 图片无法解析 | 400 | `image` | Invalid input image: ... |
| 标注层不合格 | 400 | `markup` | markup must be a PNG with transparent pixels |
| **缺 `prompt`** | **422** | | **String should have at least 1 character** |
| 模型名写错 / 无权限 | 404 | | The model `xxx` does not exist or you do not have access to it |

---

## 十一、本包实测记录

```
2026-11-07  gpt-image-2.6  1024x1024  n=1
  POST /api/v1/images/generations
  出图   43.6 秒
  返回   1 张（b64_json）
  产物   1,639,194 字节 PNG（1024×1024，魔数 \x89PNG\r\n\x1a\n）
  扣费   6 点（¥0.06）
```
