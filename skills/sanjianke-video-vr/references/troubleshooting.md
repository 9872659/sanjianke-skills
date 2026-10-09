# 排错、`--json` 契约与真机实测记录

---

## 1. 排错顺序（照这个顺序走，能省很多钱）

```
① python3 scripts/run.py doctor
       └ Key 不通？    → login --key sk-x
       └ 白名单不在？  → 见 §2（9 档跑不通的根因）
       └ 没 ffprobe？  → 装 ffmpeg，或提交时显式 --duration
② python3 scripts/run.py tiers          # 确认档位存在、单价、上限
③ python3 scripts/run.py cost --for <档位>:<秒>     # 先算钱
④ python3 scripts/run.py enhance ... --dry-run      # 白验全部免费闸门
⑤ python3 scripts/run.py enhance ... --budget N --yes [--wait]
```

**永远先 `doctor`。** 它一次把 Key、档位表、上传入口、素材入口判据、本机 ffprobe 全查一遍，
而且**零成本、不建任务**。

---

## 2. "9 档提交就 400 `url_not_allowed`" —— 三步就能定位

`viapi/*` 那 9 档**只收「本网关素材」**：先把本地文件用本网关的 `upload` 传上来，
再把返回的地址交给 `--url`。**不再需要任何第三方站点。**

```
POST api.a7w.cn/api/v1/upload      multipart/form-data，字段名 file
      ↓ 200 返回
https://oss.gpu.likeadmin.cn/openapi/…      ← 把这个地址原样交给 --url 即可
```

### 第一步：确认地址来源

| 你的 `--url` 是 | `upscale` | 其余 9 档 |
|---|---|---|
| 本网关 `upload` 返回的 `oss.gpu.likeadmin.cn/openapi/…` | ✅ | 取决于线上入口判据 |
| 任意第三方公网地址 | ✅ | ❌ 400 `url_not_allowed`（**未扣费**） |
| 本站素材地址 | ✅ | ✅ |

### 第二步：让 `doctor` 零成本实测

```bash
python3 scripts/run.py doctor
# 看「入口白名单」这一项：
#   ✓ 已放行 → 探针被 502 挡在素材镜像（未扣费），upload 的地址可直接提交
#   ! 未放行 → 探针被 400 拒（未扣费），见第三步
```

原理：拿一个**上传域前缀下、绝对不可能存在**的地址去打这一档 ——
**未放行就 400，已放行就会走到素材镜像并 502**；两条路都在**冻结扣费之前**，
所以这一次实测**不建任务、不扣费**。

### 第三步：未放行时的出路

| 出路 | 做法 | 谁来做 |
|---|---|---|
| ① 换档 | 用 `--tier upscale`（4K旗舰版，30 点/秒，收任意公网地址） | 使用者 |
| ② 换素材位置 | 改用本档入口判据内的素材地址（例如本站素材），再 `--url` 传进来 | 使用者/运营 |
| ③ 平台放行（**长期解**） | 在 relay 的**入口**判据里放行 `oss.gpu.likeadmin.cn/openapi/`（出口白名单不必动） | 平台 |

**平台一旦放行，本包无需改动即刻可用** —— 本包只是提前把人话讲清楚，不是绕过它。

---

## 3. 报错对照表（上游 code → 人话）

| 上游 code | HTTP | 本包的说法 / 处置 |
|---|---|---|
| `empty_url` / `pixverse_empty_url` | 400 | 没给 `videoUrl` |
| `url_not_allowed` | 400 | **这一档只收本网关素材**：先 `upload`，再用返回的地址（见 §2，本包会提前拦） |
| `invalid_resolution` | 400 | `upscale` 目前只支持 `4k` |
| `superres_input_too_large` | 400 | 超分输入需 <1920×1080，先降分辨率或改用 `upscale` |
| `interp_input_too_large` | 400 | 插帧仅支持 ≤720P（该档已下线） |
| `oss_mirror_failed` | 502 | 素材转存阿里云 OSS 失败（**未扣费**）：地址 404 / 不是视频 / 需要鉴权 |
| `insufficient_points` | 402 | 点数不足，去 https://api.a7w.cn/ 充值 |
| `tool_not_launched` | 501 | 该档位未开放 |
| `unknown_tool` | 404 | 档位 id 不认识，跑 `tiers` |
| `viapi_not_configured` | 400 | 平台侧凭据未配置（服务端问题，不是你的问题） |
| `unauthorized` | 401 | Key 无效/缺失 |
| `not_found` | 404 | 任务不存在（taskId 写错，或不是这个档位提交的） |
| `forbidden` | 403 | 任务属于别的用户 |
| `transfer_failed`（是 `status` 不是 `code`） | 200 | 成片转存失败，**已退款**，重新提交 |

---

## 4. `--json` 契约

```json
// 成功
{"ok": true, ...}
// 失败
{"ok": false, "exit": 3, "error": {"kind": "gate", "message": "..."}}
```

| exit | 含义 | `error.kind` |
|---|---|---|
| 0 | 成功 | — |
| 1 | 内部错误 | `internal` |
| 2 | 用法错误 | `usage` |
| 3 | 闸门没过（白名单 / 可达性 / 时长 / 上限 / 规格） | `gate` |
| 4 | 需要 `--yes`（报价已打印，**未提交**） | `confirm` |
| 5 | 预算超限 | `budget` |
| 130 | 被中断 | `interrupt` |

`--json` 写在子命令**前面或后面都可以**（`--json tiers` ≡ `tiers --json`）。

### 实测样例

`enhance --dry-run --json`（成功，且**未提交**）：

```json
{
 "ok": true,
 "dryRun": true,
 "tier": "upscale",
 "path": "/api/v1/video/upscale",
 "videoUrl": "https://cdn2.jiujiushuyuan.cn/vr/demo/moments/compare-original-vs-4k.mp4",
 "durationSeconds": 5.0,
 "billedSeconds": 5,
 "pointsPerSecond": 30,
 "costPoints": 150,
 "costYuan": 1.5,
 "reachable": {"status": 206, "contentType": "video/mp4", "bytes": 6959040},
 "needsOwnUrl": false,
 "requestBody": {"videoUrl": "...", "duration": 5, "targetResolution": "4k"}
}
```

白名单被拦（`exit=3`）：

```json
{"ok": false, "exit": 3,
 "error": {"kind": "gate",
           "message": "这一档**只收本站素材**，你的地址不在白名单内；提交必然被拒…"},
 "tier": "superres", "hint": "url_not_allowed"}
```

预算被拦（`exit=5`）：

```json
{"ok": false, "exit": 5,
 "error": {"kind": "budget", "message": "预算不够：本次需要 45 点，--budget 只给了 1 点。…"},
 "tier": "superres", "costPoints": 45, "budgetPoints": 1.0}
```

需要 `--yes`（`exit=4`，**未提交**）：

```json
{"ok": false, "exit": 4,
 "error": {"kind": "confirm", "message": "提交会冻结 45 点（¥0.45），需要 --yes。…"},
 "dryRunHint": "加 --dry-run 可零成本走一遍全部闸门", ...}
```

---

## 5. 常见问题

### Q: 查询回来 `videoUrl` 是空的，是失败了吗？
不是。成片要先**转存到本站/七牛**，转存完才有地址。`note` 会写「正在转存到本站，请稍候…」。
继续轮询即可；用 `--wait` 让它自己等到出片。

### Q: `status` 报「不知道这个 taskId 属于哪个档位」
查询接口是**路径形式**（`<提交路径>/<taskId>`），所以要知道档位。
本包提交的任务会记进 `~/.a7w/video-vr-tasks.json`，`status` 会自己去找。
如果是别处提交的，显式加 `--tier`。

### Q: 为什么不能用 `GET /api/v1/tasks/<id>` 查？
那是**网关自有层**，返回 `{"code":0,"msg":"任务不存在"}`，查不到 relay 的任务。
正解是 `GET <提交路径>/<taskId>`。

### Q: `tiers` 说「在线源当前不可达」
线上 `GET /api/v1/video/viapi/tools` 的状态变过（早先免鉴权 200，后来 401/404）。
本包会自动退回**内置档位表**（单价取自 `vr.a7w.cn` 前端档位表），
并**如实打印**这一点，不假装是权威值。功能不受影响。

### Q: 本机没有 ffprobe 会怎样？
不能用"自动探测时长"这条路。本包**不会**替你猜 5 秒，而是报错要求显式 `--duration`：

```
✗ 拿不到素材时长，**本包不会静默按 5 秒提交**（那会让你为未知时长付费）。
    → 装 ffmpeg/ffprobe 让本包自动探测，或显式传 --duration <秒>。
```

装一个即可：`winget install Gyan.FFmpeg`（Windows）/ `brew install ffmpeg`（macOS）/
`sudo apt install ffmpeg`（Linux）。

---

## 6. 真机实测记录（可复核）

### 6.1 免费接口

```
GET  /health                     → 200 {"ok":true,"service":"relay-platform","time":...}
GET  /api/v1/apps                → 200 {"code":1,"msg":"success","data":[21 个 app]}
GET  /api/v1/me/tasks            → 200 {"tasks":[...]}
GET  /api/v1/video/viapi/tools   → 早先 200（1294 B，10 档）；后来 401/404（见 api-contract.md §8）
```

### 6.2 10 档空 body（全部停在参数校验，0 花费）

```
POST /api/v1/video/upscale              {} → 400 pixverse_empty_url  videoUrl 不能为空
POST /api/v1/video/viapi/<各档>          {} → 400 empty_url           videoUrl 不能为空
```

### 6.3 素材入口判据（`POST /api/v1/video/viapi/colorize`，0 花费）

**2026-10-02 本轮复测**（全部在冻结扣费之前返回）：

```
https://oss.gpu.likeadmin.cn/openapi/18/20261002/<真实 upload 返回的>.mp4  → 400 url_not_allowed
https://oss.gpu.likeadmin.cn/openapi/<不存在>.mp4                        → 400 url_not_allowed
https://cdn2.jiujiushuyuan.cn/vr/<不存在>.mp4                            → 502 oss_mirror_failed
https://example.invalid/x.mp4                                            → 400 url_not_allowed
```

线上报错原文（**这一轮仍是旧文案**，说明入口判据尚未放行上传域）：

```
{"error":{"code":"url_not_allowed",
 "message":"videoUrl 必须是本站（vr.a7w.cn）或本站七牛（cdn2.jiujiushuyuan.cn/vr/）地址"}}
```

→ **所以本包不写死"upload 的地址一定能提交"**，而是让 `doctor` 每次**实测**并如实报告。
第二行那个「上传域里根本不存在的地址」就是探针：**未放行 → 400；已放行 → 502**，都不扣费。

### 6.4 上传接口

```
POST /api/v1/upload  匿名              → 401 unauthorized（Missing or invalid relay API key.）
POST /api/v1/upload  带 Key，空 body   → 200 {"code":0,"msg":"请使用 file 字段提交一个文件"}
POST /api/v1/upload  带 Key，multipart file= → 200
     {"code":1,"msg":"success","data":{"url":"https://oss.gpu.likeadmin.cn/openapi/18/20261001/<32hex>.mp4",
      "name":"a7w_probe_1s.mp4","size":32,"mime_type":"video/mp4","type":"video"}}
     域名取样 3 次一致 → 稳定落在 oss.gpu.likeadmin.cn
```

### 6.5 ★ 花钱教训（必须记住）

`POST /api/v1/video/upscale` **不校验素材可达性** —— 实测三条全部 201 并各冻结 60 点
（2 秒 × 30 点/秒）：

```
{"videoUrl":"https://oss.gpu.likeadmin.cn/.../x.mp4","duration":2}  → 201 costIn=60
{"videoUrl":"https://example.invalid/x.mp4","duration":2}          → 201 costIn=60
{"videoUrl":"https://cdn2.jiujiushuyuan.cn/vr/<不存在>.mp4","duration":2} → 201 costIn=60
```

余额变化（提交响应里的 `balance`）：`999997920934.5667 → …874.5667 → …814.5667`。

**这就是本包为什么要替 `upscale` 补一道可达性闸门。**

### 6.6 ★ 端到端成片（真机，唯一花钱的一档）

`colorize` 档，素材用入口判据内的本站素材（实测 **1.5 秒 / 3.7 MB**），`--duration 2`：

```
提交  POST /api/v1/video/viapi/colorize   {"videoUrl": <本站素材>, "duration": 2}
      → 201 {"taskId": "task_...", "status": "PENDING", "costIn": 18, ...}
轮询  GET  /api/v1/video/viapi/colorize/<taskId>
      → 200 {"status": "completed", "videoUrl": "https://cdn2.jiujiushuyuan.cn/vr/....mp4",
             "cost": <实扣>, ...}
```

> 本轮的真实 `taskId` / 成片 URL / 实扣点数见包外报告与
> `_vrsplit_selftest_result.json` 同级的实测记录文件。

### 6.7 本包自测（零成本）

`video_vr_selftest.py`（在包外运行）逐项覆盖，**全部通过，花费 0 点**：

- 用法闸门（`exit=2`）
- 素材入口闸门（`exit=3`，9 档逐一 + `--json` + `upscale` 不受限）
- 可达性闸门（含 `--force` 通路）
- 时长闸门（没装 ffprobe 时不静默按 5 秒）
- 上限 / 预算（`exit=5`）与 `--yes`（`exit=4`）闸门
- `--dry-run` 成功路径（`exit=0`，含 `requestBody` 断言）
- 免费子命令 `tiers` / `info` / `whoami` / `points` / `doctor`
- `--json` 前置/后置、成功/失败信封

外加 `--help` 冒烟：父命令 + 10 个子命令 **全部 exit=0**
（`allow_abbrev=False` 在父 parser 与每一个子 parser 上都加了）。

**零成本部分花费：0 点。**
