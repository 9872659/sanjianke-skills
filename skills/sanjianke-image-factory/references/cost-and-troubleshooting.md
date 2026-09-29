# 计费口径与排错

> 本文件是三剪客 · 新媒体配图工厂的**对账依据**。
> 里面每一个数字都来自实测（真金白银跑出来的），不是从平台价格字段抄的——
> 那些字段我们验证过半数不可信。

## 一、实测单价

| 项 | 实测值 | 备注 |
|---|---|---|
| `nano_banana` 1K 出图 | **24 点/张** | = 0.24 元 |
| 充值比例 | **1 元 = 100 点** | |
| 提交时冻结 | `frozen_points = 31.2` | **预冻结，不是最终扣费** |
| 提交时冻结点（另一字段） | `relay_points = 31.2` | 同上 |
| 完成时结算 | `usage.points_cost = 24` | **唯一可信的结算依据** |
| 冻结与实扣的差 | 31.2 → 24，差 **30%** | 所以不能拿 `frozen_points` 记账 |
| 任务失败 | 全额退回 | |

`2K` / `4K` **我们没有实测过**，所以脚本**拒绝估算**并返回退出码 3。
想估就给 `--points-per-image <点数>`。

### 为什么只信 `usage.points_cost`

平台的 `pricing_matrix` / `tenant_fixed_points` / `tenant_points_per_1k_input` 这类字段，
我们逐项比对过，**半数与实扣不符**：

| 字段声称 | 实测 |
|---|---|
| `image_human` 写 1.5 / 2 / 4 / 8 点/秒 | 实扣 **2 / 3 / 6 / 12** |
| `voice_tts` / `voice_stt` 写 30 点 | 实扣 **40** |

出图接口的文档里甚至写着 `计费：免费`、`tenant_fixed_points=0.00`，
而实测每张扣 24 点。**这些字段只能当参考，绝不能当结算价写进文档或代码。**

### 任务返回里的两个不同字段

`submit` 的响应：

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "task_xxx", "status": "pending", "app": "nano_banana",
          "api": "submit", "frozen_points": 31.2, "actual_points": 0,
          "relay_points": 31.2}}
```

`GET /api/v1/tasks/<task_id>` 的完成响应：

```json
{"code": 1, "msg": "success",
 "data": {"task_id": "task_xxx", "status": "completed",
          "result": {"image_url": "https://.../task_xxx_1.png", "success": true},
          "usage": {"points_cost": 24, "input_tokens": 0, "output_tokens": 0}}}
```

**注意 `status` 在 `data` 顶层，不在 `data.result` 里。**
照着"`data.result.status`"写会永远读不到状态、一路轮询到超时——我们踩过。

## 二、响应信封（最容易搞错的一条）

```
code == 1  才是成功   ← 不是 0 ！
```

- **HTTP 200 不代表业务成功**，必须看 body 里的 `code`
- 平台官方文档的失败示例写的是 `"code": 0`，成功示例写的是 `"code": 1`
- 实际写错的代价是"提交失败还当成成功"，后面一路错到出图数量不对

`scripts/a7w.py` 的 `_unwrap()` 就是这个口径：

```python
ok = code in (1, 200, "1", "200") or code is None
```

### 常见失败响应

```json
{"code": 0, "data": [],
 "msg": "当前请求未命中可用计费规格，请检查模型、分辨率是否在支持范围内。",
 "show": 1}
```

常见原因：`prompt` 为空、`action` 无效、`model` 不支持、
**普通模型传了非 1K 分辨率**、点数不足、Key 无权限。

## 三、成本前置的三道算式

```bash
# 1) 出图前算总价（不提交任何任务）
python3 scripts/run.py cost --count 8
#   预估成本：8 张 × 24 点 = 192 点 = 1.92 元

# 2) 设预算上限：超了直接停，退出码 3
python3 scripts/run.py gen --plan plan.json --outdir ./out --budget 200 --yes

# 3) 不带 --yes 只报价
python3 scripts/run.py gen --plan plan.json --outdir ./out
#   预估成本：... 这是一次真花钱的操作（约 1.92 元）。确认后加 --yes 重跑。
```

`--budget` 是**点**不是元：`--budget 200` = 2 元。

预算会被检查**两次**：

1. 提交前：预估总价 > 预算 → 一个任务都不提交
2. 每张提交前：已花 + 待花 > 预算 → 就地停（因为真实扣费可能比预估高）

## 四、断点续跑与"不重复扣费"

出图是**异步 + 按次扣费**：一次抖动、一次 Ctrl+C，都会让"已经提交并冻结了点数"的
任务悬在那里。没有断点记录，重跑就会把同一张图再买一遍。

断点文件默认在 `<outdir>/image-factory-state.json`，每张图记：

| 字段 | 用途 |
|---|---|
| `task_id` | **续查**用。pending 的项重跑时先拿它去查，而不是重新提交 |
| `status` | `pending` / `completed` / `failed` |
| `points_cost` | 实扣点数，重跑时累加起来对账 |
| `file` / `real_px` / `ratio_ok` | 产出与闸门结论 |
| `request` | 提交时**真实发送的参数**（对账与复现用） |
| `raw_task` | 任务返回原文 |

重跑的行为：

```
[1/3] #1 已完成，跳过（上次扣费 24.0 点，不再重复扣）
[2/3] #3 发现未完成的 task_id=task_xxx，续查而不重新提交
[3/3] #2 提交：aspect_ratio=3:4 resolution=1K model=nano-banana
```

**key 是提示词 + 比例 + 分辨率 + 模型的哈希。** 改了提示词就是新的一项 → 会重画重扣。
这是设计如此（改了提示词就该重画）；只改摆放位置不改提示词，重跑会被跳过。

## 五、退避重试

网关到上游的 `upstream timeout` / HTTP 502 **实测很频繁**，
长异步任务的轮询也会被重置连接（`WinError 10054 远程主机强迫关闭了一个现有的连接`）。

所以 `scripts/a7w.py` 的 `_request()` 对**网络类错误与 5xx** 做指数退避重试（4 次），
对 4xx（业务错误）**不重试**——4xx 重试只是浪费额度。

`upstream timeout` 的典型形态是提交时返回 `code: 0` 加一段上游超时消息，
或者干脆连接被重置。前者是业务错误，脚本会直接报出来让你决定是否重提；
后者会被自动重试。

**注意**：提交成功但轮询中断时，钱**已经冻结了**。所以脚本在提交后立刻把
`task_id` 落盘，中断也能用 `python3 scripts/a7w.py task <task_id>` 续查，
不会白丢。

## 六、超时与轮询

| 参数 | 默认 | 说明 |
|---|---|---|
| `--poll-interval` | 5 秒 | 轮询间隔。平台建议 3~5 秒 |
| `--poll-timeout` | 600 秒 | **上限**，不是期望时长（实测单张 5~30 秒完成） |
| `--max-seconds` | 无 | 整批最长耗时，到点中断并保留断点，退出码 5 |

**轮询必须有上限**，否则一张卡住的任务会把整批挂死。

## 七、排错速查

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `鉴权失败（401）` | Key 无效/过期/写错 | 到 https://api.a7w.cn/ 重新领取 |
| 点数不足（402） | 余额不够 | 充值；或用 `cost` 先算一趟要多少钱 |
| HTTP 200 但 `code: 0` | 业务失败（不是网络问题） | 看 `msg`；别把 `code == 0` 当成功 |
| `未命中可用计费规格` | `model` + `resolution` 组合不支持 | 普通 `nano-banana` 只支持 `1K`；高清档换 `nano-banana-2:official` 等 |
| 上游 502 / `upstream timeout` | 网关抖动，很常见 | 已自动退避重试 4 次；持续失败就换模型或缩小批次 |
| 轮询一直 `processing` | 任务卡住 | 等 `--poll-timeout` 到点；保留 `task_id` 续查 |
| 真实像素 ≠ 请求比例 | **上游按 32 对齐**，正常现象 | 加 `--snap`；或放宽 `--ratio-tolerance` |
| `读不出真实像素` | 下载被截断 / 不是图片 | 删掉断点记录重出（`--force`） |
| 每张都失败 | Key 无该应用权限，或该应用不在你账号的可选范围 | `python3 scripts/run.py models` 看清单 |
| 提示词被判不合格 | 违禁词 / 照抄示例 / 占位符 | 改提示词；确实要带违禁词才加 `--allow-prompt-hits` |

## 八、对账

`gen --report evidence.json` 会产出一份证据文件，每张图记了：

- **真实请求参数**：`prompt` / `action` / `resolution` / `aspect_ratio` / `model`
- **任务返回原文**：`raw_task`（含 `usage.points_cost`）
- **真实像素**：`real_px` 与 `real_ratio`（读文件头得出的，不是自报值）
- **请求比例与偏差**：`want_ratio` / `deviation`
- **裁剪记录**：`snap`（方式、裁剪框、裁后复核结果）

对账方式：把 `points_cost` 逐张加起来，与账号后台的扣费流水比。
差在哪就查那一条的 `raw_task`。

## 九、已知的没能确认项

诚实列出来，别当成都验证过：

1. **2K / 4K 的真实扣费**没有实测过（只跑过 1K）。脚本因此拒绝估算这两档。
2. **`nano-banana-2` / `-pro` / `:official` 各档的实际扣费**没实测过，
   文档里的 38 / 45 / 28.03 点来自平台文档，**未经验证**。
3. **`relay_points` 与 `frozen_points` 为什么都等于 31.2**、以及 31.2 这个数怎么来的
   （是 24 × 1.3 的加价率还是别的口径），没有确认。
4. **`code` 在成功响应里出现 `code: 0` 的边界**：我们实测到的失败响应确实带 `code: 0`，
   但也见过不带 `code` 字段的成功响应（走 OpenAI 兼容的 `/chat/completions` 时），
   所以 `_unwrap()` 把 `code is None` 也当成功。这是保守处理，不是确证。
5. **并发提交的限流口径**没测过。本包是**串行**出图，没做并发。
6. **`callback_url` 回调**没有实测过，本包没用到它。

### 已经补掉的一条（v1.0.1）

- ~~WebP 的 VP8X 尺寸解析没有真实文件可回归~~ → **已补**。
  用 Pillow 12.3.0 真实编码器产出三种 WebP 交叉验证，`imgprobe.py` 全部读对：
  `VP8 `（有损，800x600）、`VP8X`（扩展，带 ALPH，640x480）、`VP8L`（无损，320x240 / 1024x768）。
  顺带纠正一个**测试侧**的错误：我原先手搓 VP8X 时只写了 3 字节 flags+reserved
  （规范是 flags(1) + reserved(3) 共 4 字节），导致 fixture 错位、误报产品代码有 bug。
  真正的偏移是：payload 从第 20 字节起，宽高各 3 字节小端分别在 `[24:27]` / `[27:30]`。
