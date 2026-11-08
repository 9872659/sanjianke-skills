# 排错：按报错找原因

先跑 `python3 scripts/run.py doctor`（0 点）。它会把 Key、7 个只读端点、422 探针、
余额前后对比、今日图片流水一次打出来，多数问题看一眼就定位。

---

## 一、快速对照表

| 你看到的现象 | 真正原因 | 怎么改 |
|---|---|---|
| `HTTP 404` + `<!DOCTYPE html>` | 型号在目录里但还没上架，网关回 SPA 兜底 | `catalog --all` 看状态，换一个「可调用」的型号 |
| `400 prompt is required` | 端点少了 `/api` 前缀，落到旧路由 | 用 `https://api.a7w.cn/api/v1/images/generations` |
| `422 prompt: String should have at least 1 character` | 这是**正常的探针返回** | 什么都不用改，说明端点对了 |
| `502 百炼提交失败：Access denied` | 该型号在阿里云百炼侧未开通 | 换型号；`qwen-image-3.0-pro` 走应用层有 105 点成交记录 |
| 流水里 `-20` 紧接 `+20` | 上游失败，冻结后全额退 | 净 0，不用处理；看 `refund:` 那一笔 |
| `失败：目录里没有这些型号：xxx`（exit 2） | 型号名写错或不在图片目录 | `catalog` 复制准确的 `model_code` |
| `失败：这些型号在目录里还是待验证状态`（exit 2） | 该型号 `channel=official`、描述带「完成上架」 | 换可调用型号，或 `--allow-any-model` 直接试 |
| `失败：这会真实出图…确认请加 --yes`（exit 4） | 第二道闸门 | 看它报的点数，确认后加 `--yes` |
| `失败：预计 X 点超过 --budget Y 点`（exit 5） | 第一道闸门 | 调大 `--budget`，或减型号 / 减 `--n` |
| `失败：n 只能是 1-4`（exit 2） | 张数越界 | `--n` 取 1 - 4 |
| `失败：尺寸不合法`（exit 2） | gpt-image 系四条硬约束 | 换 `auto` / `1k` / `2k` / `4k`，或按约束改宽高 |
| `失败：查不到任务 task_xxx（HTTP 200）：任务不存在`（exit 6） | id 写错，或任务不在这个 Key 下 | 用提交时返回的 id |
| 图片链接 404 | 链接约 3 小时过期，或加了查询参数 | 原样使用；本包默认落 b64 文件，不受影响 |
| 下载图片 403 | `urllib` 没带 User-Agent | 本包已自带 UA；自写脚本请补上 |
| 报价和账单对不上 | 报的是「按上界预估」，实际按返回张数结算 | 看 `GET /user/balance/logs` 的 `points` |
| 单价看起来是旧的 | 本机价格缓存 6 小时 | `--refresh` 重扫 `me/tasks` |
| 终端里中文变 `?` | 控制台编码是 cp936，个别符号编不出来 | 本包已用 `errors="replace"` 兜底；测试时设 `PYTHONIOENCODING=gbk` |

---

## 二、404 HTML：型号没上架，不是路径错

```bash
POST /api/v1/images/generations  {"model":"flux-2-flex","prompt":""}
-> HTTP 404  <!DOCTYPE html> … nuxt-spa-loading …
```

同一个 Key、同一个路径，换成 `gpt-image-2.6` 就是 **422**。
所以 404 说明「这个型号没有路由」，不是端点写错。

判断方法（0 点，不用发请求）：看 `GET /api/v1/models` 里这条记录

```
channel_code = "official"
vendor_code  = "official"
description  = "模型接口及可用规格详见开发文档；同步后请先验证并完成上架。"
```

三条同时命中，就是「目录已同步、路由未上架」。本包 `catalog` 把它标成「目录待验证」，
`gen` 预检直接拦住，并在报错里列出可调用型号。

---

## 三、422 是正确结果，不是报错

```json
{"error": {"message": "prompt: String should have at least 1 character",
           "type": "invalid_request_error", "code": "bad_request"}}
```

`doctor` 的探针就是故意发空 prompt。拿到 422 说明：路径对、Key 有效、参数校验在工作，
而且**停在扣费之前**（不建任务、不冻结）。

`qwen-image-3.0` 这类型号会先 `reserve_sync -20` 再 `refund +20`，
所以本包只探 `gpt-image-2.6`，不逐型号探。

---

## 四、`502 百炼提交失败：Access denied`

```json
{"code": 0, "msg": "百炼提交失败：Access denied, please make sure your account is in good standing.
 （该模型可能尚未在阿里云百炼控制台开通/激活…）"}
```

这是上游账号状态问题，不是本包的问题。两条路：

1. 换一个已上架型号（`catalog` 里状态是「可调用」的）；
2. 走应用层同能力：`qwen-image-3.0-pro` 在 `GET /api/v1/me/tasks` 里有 105 点/张的成交记录。

流水会显示冻结后又退回，净 0；担心钱包被动过，就看 `refund:` 那一笔的 `balanceMoving`。

---

## 五、预算与确认两道闸门

```bash
$ python3 scripts/run.py gen --models gpt-image-2.6 --prompt "雨夜街头"
失败：这会真实出图：1 个型号 x 1 张，按上界约 6 点（0.06 元）。确认请加 --yes。
$ echo $?    # 4

$ python3 scripts/run.py gen --models gpt-image-2.6 --prompt "雨夜街头" --budget 1 --yes
失败：预计 6 点（0.06 元）超过 --budget 1 点。这一条只读了免费台账，一个出图请求都没发。
$ echo $?    # 5
```

- `--budget` 单位是**点**（1 元 = 100 点），默认 200 点；
- 预算是「每个型号的上界单价 x n」相加，宁高不低；
- `--dry-run` 连 `--yes` 都不用，一个请求都不发。

---

## 六、异步任务：只走 `GET /api/v1/tasks/<id>`

```bash
python3 scripts/run.py status --task-id task_xxx
```

返回 `{"code":0,"msg":"任务不存在"}` 也是 **HTTP 200**，所以本包判断看 `code` 与 `data`。

应用层的 `POST /api/v1/apps/nano_banana/query` 每查一次扣 **72 点**，
本包一次都不用；`gen` 遇到异步型号时用 `--every`（默认 5 秒）轮询
`GET /api/v1/tasks/<id>`，`--wait` 默认 600 秒。

---

## 七、落盘与命名

```
run-20261108-093000/
├── 01-gpt_image_2_6-01.png
├── 02-seedream_5_0_flash-01.png
├── manifest.json
└── 对比清单.md
```

- 第一段是型号序号，第二段是型号（`.` 换成 `_`），第三段是第几张；
- 响应里 `b64_json` 直接解码写文件，不依赖 3 小时有效的链接；
- 复制目录后想重出清单：`python3 scripts/run.py sheet --run <目录>`，纯本地。

---

## 八、单价与缓存

本包单价按这个顺序取：

1. `GET /api/v1/me/tasks` 里该型号的 `actualPrice`（`source=live`）；
2. 内置基线：本账号流水 / 台账里的成交价（`source=baseline`）；
3. 都没有：用同一条图片路径 70 笔流水的 **4 - 13.78 点**区间，预算按上界（`source=baseline`）。

缓存文件在 `~/.a7w/image-models-prices.json`，有效期 6 小时。
刚跑完一批想立刻看到新成交价，加 `--refresh`。
想扩大统计窗口：`--pages 20`（每页 20 条，越大越慢）。

---

## 九、编码与终端

- 本包在 import 阶段对 `stdout` / `stderr` 做 `reconfigure(errors="replace")`；
- 全文只用 cp936 覆盖得到的字符（`√ × · 「」` 与中文标点），金额写「元」或全角 ￥；
- 复现 GBK 环境：

```powershell
$env:PYTHONIOENCODING="gbk"
python -u scripts\run.py doctor
```

如果看到 `?`，先确认是不是把半角 `¥` 或 emoji 塞进了提示词 ——
提示词里的特殊符号会被控制台编码替换，请求本身不受影响。

---

## 十、还是不通

把这三样一起发出来，定位最快：

1. `python3 scripts/run.py doctor --json`
2. 出图命令的 `--dry-run` 输出（请求体全在里面）
3. `GET /user/balance/logs?limit=20` 的原文

技术微信见 SKILL.md 末尾「联系我们」。
