# Umi-OCR HTTP 接口速查

来源：上游 `docs/http/` 目录下的官方接口文档。默认端口 `1224`，可在「全局设置」中修改。使用前必须允许 HTTP 服务（默认开启）；仅在需要局域网访问时才把主机切到「任何可用地址」。

在线参数查询（务必先查，不同 OCR 引擎插件参数不同）：

```python
import requests
print(requests.get("http://127.0.0.1:1224/api/ocr/get_options").json())
```

## 通用约定

- 成功 / 失败用 `code` 区分：`100` 成功，`101` 无文本，其余为失败。
- 返回值里的非英文字符是 `\uXXXX` 转义；转义换行 `\\n` 可能被某些 http 库还原成真实换行，导致 JSON 解析失败——先把真实换行替换回 `\\n` 再解析。
- 官方明确提示：不要并发调用，串行处理；偶发 `ECONNREFUSED` 重发即可。

## 一、图片 OCR

### `GET /api/ocr/get_options`

返回图片 OCR 接口的参数定义（`title` / `toolTip` / `default` / `type` / `optionsList`）。所有参数均可选，不传则用默认值。

### `POST /api/ocr`

```json
{
  "base64": "iVBORw0KGgoAAAAN……",
  "options": {
    "ocr.language": "models/config_chinese.txt",
    "ocr.cls": false,
    "ocr.limit_side_len": 4320,
    "tbpu.parser": "multi_para",
    "tbpu.ignoreArea": [[[0, 0], [100, 50]]],
    "data.format": "text"
  }
}
```

- `base64` 必填，**不带** `data:image/png;base64,` 前缀。
- 响应字段：`code`、`data`、`time`（秒）、`timestamp`（秒）。
- `data.format = "text"` 时 `data` 是拼接好的纯文本；`"dict"`（默认）时是列表，每项含 `text`、`score`、`box`（左上/右上/右下/左下四角坐标）、`end`（行结束符，按 `本行+结束符+下一行+…` 拼接可还原段落）。

常用参数一览（**注意多项只对 PaddleOCR 插件生效，换引擎先查 `get_options`**）：

| 键 | 默认值 | 可选值 / 说明 |
|---|---|---|
| `ocr.language` | `models/config_chinese.txt` | 简体中文 / English / 繁體中文 / 日本語 / 한국어 / Русский 等模型配置 |
| `ocr.cls` | `false` | 纠正文本方向，识别倾斜或倒置文本，会降速 |
| `ocr.limit_side_len` | `960` | `960` / `2880` / `4320` / `999999`（无限制），大图调高 |
| `tbpu.parser` | `multi_para` | `multi_para` / `multi_line` / `multi_none` / `single_para` / `single_line` / `single_none` / `single_code`（保留缩进，适合代码截图）/ `none` |
| `tbpu.ignoreArea` | `[]` | 嵌套整数列表，每项 `[[左上x,y],[右下x,y]]`，只忽略完全落在框内的整个文本块 |
| `data.format` | `dict` | `dict`（含位置）/ `text`（纯文本） |

## 二、文档识别（PDF / 电子书）

需要 `v2.1.4` 及以上版本。流程五步：上传 → 轮询 → 生成 → 下载 → 清理。

### 0. `GET /api/doc/get_options`

除上表中的 `ocr.*` 与 `tbpu.*` 外，文档接口另有：

| 键 | 默认值 | 说明 |
|---|---|---|
| `tbpu.ignoreRangeStart` / `tbpu.ignoreRangeEnd` | `1` / `-1` | 忽略区域生效的页数范围，`-X` 表示倒数第 X 页 |
| `pageRangeStart` / `pageRangeEnd` | `1` / `-1` | OCR 页数范围 |
| `pageList` | `[]` | 指定页列表，如 `[1,2,5]`；与页数范围同时填写时 `pageList` 优先 |
| `password` | `""` | 加密文档的密码 |
| `doc.extractionMode` | `mixed` | `mixed`（混合 OCR/原文本）/ `fullPage`（整页强制 OCR）/ `imageOnly`（仅 OCR 图片）/ `textOnly`（仅拷贝原有文本） |

### 1. `POST /api/doc/upload`

表单 `formData`：

- `file`：必填，要上传的文件。
- `json`：可选，参数字典的 **JSON 字符串**。

响应：`code`（`100` 上传成功）、`data`（成功时是任务 ID，失败时是原因）。

```python
import json, requests
with open("scan.pdf", "rb") as f:
    r = requests.post(
        "http://127.0.0.1:1224/api/doc/upload",
        files={"file": f},
        data={"json": json.dumps({"doc.extractionMode": "mixed"})},
    ).json()
task_id = r["data"]
```

### 2. `POST /api/doc/result`

请求：`{"id": "<task_id>", "is_data": true, "is_unread": true, "format": "text"}`

- `is_data`：`true` 才返回识别结果；`false`（默认）只返回任务状态。
- `is_unread`：`true`（默认）只返回未读过的条目。
- `format`：`dict`（默认）或 `text`。

响应在 `code == 100` 时另有：`processed_count`（已完成页数）、`pages_count`（总页数）、`is_done`、`state`（`waiting` / `running` / `success` / `failure`）、`message`（仅失败时存在，失败也可能拿到已完成部分的结果）。

轮询直到 `is_done == true`。

### 3. `POST /api/doc/download`

请求：`{"id": "<task_id>", "file_types": ["pdfLayered"], "ignore_blank": true}`

- `file_types` 单项返回单文件下载链接；多项返回打包的 zip 链接。
  - `pdfLayered`（默认）双层可搜索 PDF、`pdfOneLayer` 单层纯文本 PDF、`txt`（带页数信息）、`txtPlain`（仅文本）、`jsonl`、`csv`（每行一页）。
- `ignore_blank`：`true`（默认）跳过空页。

响应：`code`、`data`（下载链接）、`name`（文件名）。**必须**在 `is_done && state == "success"` 之后调用。

### 4. 下载结果

对第 3 步拿到的链接发 GET，或直接用浏览器打开。链接里的 id **不是**任务 ID，不能用任务 ID 拼出来。

### 5. `GET /api/doc/clear/<id>`

清理任务及其在服务器上的全部临时文件；任务进行中执行会强制终止。清理后无法再查状态或下载。不手动清理的话 **24 小时后自动清理**；软件意外关闭后，下次启动会自动清理遗留任务。

## 三、二维码

### `POST /api/qrcode` — 识别

```json
{"base64": "……", "options": {"preprocessing.grayscale": false}}
```

可选预处理参数：`preprocessing.median_filter_size`（1~9 奇数）、`preprocessing.sharpness_factor`（0.1~10.0）、`preprocessing.contrast_factor`（0.1~10.0）、`preprocessing.grayscale`（布尔）、`preprocessing.threshold`（0~255，仅灰度时生效）。

成功时 `data` 是列表（一图可多码），每项含 `text`、`format`（如 `QRCode`）、`box`、`orientation`（0 为正上）、`score`（恒为 1，无意义）。

### `POST /api/qrcode` — 生成

```json
{"text": "要写入的文本", "options": {"format": "QRCode", "w": 0, "h": 0, "quiet_zone": -1, "ec_level": -1}}
```

- `w` / `h` 默认 `0` 表示自动取最小适配尺寸；`quiet_zone` 默认 `-1` 自动。
- `ec_level`：`-1` 自动 / `1` 7% / `0` 15% / `3` 25% / `2` 30%，仅对 `Aztec`、`PDF417`、`QRCode` 生效。
- 成功时 `data` 是 jpeg 图片的 base64 字符串。

支持的 19 种协议：`Aztec`、`Codabar`、`Code128`、`Code39`、`Code93`、`DataBar`、`DataBarExpanded`、`DataMatrix`、`EAN13`、`EAN8`、`ITF`、`LinearCodes`、`MatrixCodes`、`MaxiCode`、`MicroQRCode`、`PDF417`、`QRCode`、`UPCA`、`UPCE`。

## 四、命令行转发

程序的 `>` / `|` 重定向不可靠。要用程序调用命令行并拿到回传，改用 HTTP 转发命令行接口，具体端点与参数以官方 `docs/http/argv.md` 为准。
