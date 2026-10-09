# `portrait`（人像增强）· 排错、`--json` 契约与真机实测记录

---

## 1. 排错顺序（照这个顺序走，能省很多钱）

```
① python3 scripts/run.py doctor
       └ Key 不通？    → login --key sk-x
       └ 没 ffprobe？  → 装 ffmpeg，或提交时显式 --duration
       └ 素材入口没过？ → 见 §2（本档的素材通道）
② python3 scripts/run.py info          # 确认单价、上限、素材要求
③ python3 scripts/run.py cost <秒数>     # 先算钱
④ python3 scripts/run.py enhance ... --dry-run      # 白验全部免费闸门
⑤ python3 scripts/run.py enhance ... --budget N --yes [--wait]
```

**永远先 `doctor`。** 它一次把 Key、上传入口、素材入口判据、素材可达性、本机 ffprobe 全查一遍，而且**零成本、不建任务**。

---

## 2. 「提交就 400 `url_not_allowed`」 —— 三步就能定位

`viapi/*` 各档**只收本网关素材**：先把本地文件用本网关的 `upload` 传上来，再把返回的地址交给 `--url`。**不再需要任何第三方站点。**

```
POST api.a7w.cn/api/v1/upload      multipart/form-data，字段名 file
      ↓ 200 返回
https://oss.gpu.likeadmin.cn/openapi/…      ← 把这个地址原样交给 --url 即可
```

### 第一步：确认地址来源

| 你的 `--url` 是 | `upscale` | 其余各档 |
|---|---|---|
| 本网关 `upload` 返回的 `oss.gpu.likeadmin.cn/openapi/…` | ✅ | 取决于线上入口判据 |
| 任意第三方公网地址 | ✅ | ❌ 400 `url_not_allowed`（**未扣费**） |
| 本站素材地址 | ✅ | ✅ |

### 第二步：让 `doctor` 零成本实测入口判据

```bash
python3 scripts/run.py doctor
# 看「入口白名单」这一项：
#   ✓ 已放行 → 探针被 502 挡在素材镜像（未扣费），upload 的地址可直接提交
#   ! 未放行 → 探针被 400 拒（未扣费），见第三步
```

原理：拿一个**上传域里根本不存在的地址**去打这一档 —— **放行就会走到素材镜像并 502，未放行就 400**，两条路都在冻结扣费之前。

### 第三步：未放行时的出路

| 出路 | 做法 | 谁来做 |
|---|---|---|
| ① 换档 | 用 `sanjianke-vr-upscale-4k`（4K旗舰版，30 点/秒，收任意公网地址） | 使用者 |
| ② 换素材位置 | 改用本站素材地址（本档入口判据内的地址），再 `--url` 传进来 | 使用者/运营 |
| ③ 平台放行（**长期解**） | 在 relay 的**入口**判据里放行 `oss.gpu.likeadmin.cn/openapi/`（出口白名单不必动） | 平台 |

**平台一旦放行，本包无需改动即刻可用** —— 本包只是提前把人话讲清楚，不是绕过它。

---

## 3. 报错对照表（上游 code → 人话）

| 上游 code | HTTP | 本包的说法 / 处置 |
|---|---|---|
| `empty_url` / `pixverse_empty_url` | 400 | 没给 `videoUrl` |
| `url_not_allowed` | 400 | **本档只收本站素材**（见 §2，本包会提前拦） |
| `invalid_resolution` | 400 | `upscale` 目前只支持 `4k` |
| `superres_input_too_large` | 400 | 超分输入需 <1920×1080，先降分辨率 |
| `interp_input_too_large` | 400 | 插帧仅支持 ≤720P（该档已下线） |
| `oss_mirror_failed` | 502 | 素材转存阿里云 OSS 失败（**未扣费**）：地址 404 / 不是视频 / 需要鉴权 |
| `insufficient_points` | 402 | 点数不足，去 https://api.a7w.cn/ 充值 |
| `tool_not_launched` | 501 | 该档位未开放 |
| `unknown_tool` | 404 | 档位 id 不认识，跑 `info` |
| `viapi_not_configured` | 400 | 平台侧凭据未配置（服务端问题，不是你的问题） |
| `unauthorized` | 401 | Key 无效/缺失 |
| `not_found` | 404 | 任务不存在（taskId 写错，或不是本档提交的） |
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

`--json` 写在子命令**前面或后面都可以**（`--json info` ≡ `info --json`）。

### 实测样例

`enhance --dry-run --json`（成功，且**未提交**）：

```json
{
 "ok": true,
 "dryRun": true,
 "tier": "portrait",
 "path": "/api/v1/video/viapi/portrait",
 "videoUrl": "https://.../compare-original-vs-4k.mp4",
 "durationSeconds": 5.0,
 "billedSeconds": 5,
 "pointsPerSecond": 18,
 "costPoints": 90,
 "costYuan": 0.9,
 "reachable": {"status": 206, "contentType": "video/mp4", "bytes": 6959040},
 "needsOwnUrl": true,
 "requestBody": {"videoUrl": "...", "duration": 5}
}
```

素材入口被拦（`exit=3`）：

```json
{"ok": false, "exit": 3,
 "error": {"kind": "gate",
           "message": "**标准超分 1080P**（`superres`）只收本网关素材，你的地址不在入口判据内…"},
 "tier": "portrait", "hint": "url_not_allowed"}
```

预算被拦（`exit=5`）：

```json
{"ok": false, "exit": 5,
 "error": {"kind": "budget", "message": "预算不够：本次需要 18 点，--budget 只给了 1 点。…"},
 "tier": "portrait", "costPoints": 18, "budgetPoints": 1.0}
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
不是。成片要先**转存到本站/七牛**，转存完才有地址。`note` 会写「正在转存到本站，请稍候…」。继续轮询即可；用 `--wait` 让它自己等到出片。

### Q: `status` 报「不知道这个 taskId 属于哪个档位」
查询接口是**路径形式**（`<提交路径>/<taskId>`），所以要知道档位。本包提交的任务会记进 `~/.a7w/video-vr-tasks.json`，`status` 会自己去找。如果是别处提交的，显式加 `--tier portrait`。

### Q: 为什么不能用 `GET /api/v1/tasks/<id>` 查？
那是**网关自有层**，返回 `{"code":0,"msg":"任务不存在"}`，查不到 relay 的任务。正解是 `GET /api/v1/video/viapi/portrait/<taskId>`。

### Q: `info` 说「在线源当前不可达」
线上 `GET /api/v1/video/viapi/tools` 的状态变过（早先免鉴权 200，后来 401/404）。
本包会自动退回**内置档位表**（单价取自 `api.a7w.cn` 在架能力），并**如实打印**这一点，不假装是权威值。功能不受影响。

### Q: 本机没有 ffprobe 会怎样？
不能用「自动探测时长」这条路。本包**不会**替你猜 5 秒，而是报错要求显式 `--duration`：

```
✗ 拿不到素材时长，**本包不会静默按 5 秒提交**（那会让你为未知时长付费）。
     → 装 ffmpeg/ffprobe 让本包自动探测，或显式传 --duration <秒>。
```

装一个即可：`winget install Gyan.FFmpeg`（Windows）/ `brew install ffmpeg`（macOS）/ `sudo apt install ffmpeg`（Linux）。

---

## 6. 真机实测记录（可复核）

### 6.1 免费接口

```
GET  /health                     → 200 {"ok":true,"service":"relay-platform","time":...}
GET  /api/v1/apps                → 200 {"code":1,"msg":"success","data":[app...]}
GET  /api/v1/me/tasks            → 200 {"tasks":[...]}
GET  /api/v1/video/viapi/tools   → 早先 200（1294 B）；后来 401/404（见 api-contract.md §8）
```

### 6.2 各档空 body（全部停在参数校验，**0 花费**）

```
POST /api/v1/video/upscale              {} → 400 pixverse_empty_url  videoUrl 不能为空
POST /api/v1/video/viapi/<9 档>          {} → 400 empty_url           videoUrl 不能为空
```

### 6.3 素材入口判据（`POST /api/v1/video/viapi/portrait`，**0 花费**）

```
https://oss.gpu.likeadmin.cn/openapi/…（**upload 的返回**） → 由线上入口判据决定（见下）
https://oss.gpu.likeadmin.cn/openapi/<不存在>.mp4（入口探针） → 400 `url_not_allowed`（未放行）或 502 `oss_mirror_failed`（已放行）；**两者都不扣费**
https://cdn2.jiujiushuyuan.cn/vr/<不存在>.mp4（本站素材） → 502 `oss_mirror_failed`（**未扣费**）
https://example.invalid/x.mp4（任意第三方）             → 400 `url_not_allowed`（**未扣费**）
```

### 6.4 上传接口

```
POST /api/v1/upload  匿名              → 401 unauthorized（Missing or invalid relay API key.）
POST /api/v1/upload  带 Key，空 body   → 200 {"code":0,"msg":"请使用 file 字段提交一个文件"}
POST /api/v1/upload  带 Key，multipart file= → 200
     {"code":1,"msg":"success","data":{"url":"https://oss.gpu.likeadmin.cn/openapi/18/20261001/<32hex>.mp4",
      "name":"a7w_probe_1s.mp4","size":32,"mime_type":"video/mp4","type":"video"}}
     域名取样 3 次一致 → 稳定落在 oss.gpu.likeadmin.cn
```

### 6.5 本包自测（零成本）

`_vrsplit_selftest.py`（在包外运行）对 10 个单档包逐一覆盖：

- 用法闸门（`exit=2`）：缺 `--url`、非 HTTP、`--budget` 为负
- 素材入口闸门（`exit=3`）：本档地址判定（`exit=0` 的入口放行算「过闸」）
- 可达性闸门（`exit=3`）：探不到就拒提交，`--force` 可绕过
- 时长闸门（`exit=3`）：不给 `--duration` 且本机无 ffprobe 时报错，**不静默按 5 秒**
- 上限闸门（`exit=3`）：超过 600 秒
- 预算闸门（`exit=5`）与 `--yes` 闸门（`exit=4`）
- `--dry-run` 成功路径（`exit=0`，断言 `requestBody`）
- `--json` 契约（前置/后置、成功/失败信封）
- 免费子命令：`info` / `whoami` / `points` / `doctor`（不建任务）

外加 `--help` 冒烟：父命令 + **每一个**子命令全部 `exit=0`（`allow_abbrev=False` 在父 parser 与每一个子 parser 上都加了）。

**本轮实测花费：0 点。** 只跑 `--dry-run`、扣费前的闸门用例与免费子命令。
