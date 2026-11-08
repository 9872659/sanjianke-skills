# 排错手册 · 按报错找原因

先跑一次零扣费自检：

```bash
python3 scripts/run.py doctor
```

15 项全 √ 再往下排。doctor 只发只读 GET 和空 body POST，停在参数校验，不建任务。

---

## 1. 快速决策树

```text
要提 1080P / 2K / 4K 视频
├─ 想现在就跑通
│   └─ VIAPI：superres(9) / superres2k(15) / superres4k(20) 点每秒
├─ 想最便宜
│   └─ 腾讯：1080P 2 / 2K 4 / 4K 8 点每秒
│       └─ 当前 502 InvalidMpsUser → 等修复；提交失败全额退
├─ 只跑 FlashVSR
│   └─ a7w-flashvsr 专包；本包 --tier flashvsr 也能提交
└─ 要 4K 旗舰
    └─ /video/upscale 30 点每秒；本账号 7 条历史任务全退，先 5 秒小样

要放大图片
└─ 模型层：recraft-crisp-upscale（image）/ topaz-image-upscale（image_url）
    └─ 50 点/次起；当前无成交样本，先验一单
```

---

## 2. 报错对照表

| 现象 | 原因 | 处理 |
|---|---|---|
| `400 empty_url` / `videoUrl 不能为空` | VIAPI 没收到视频地址 | 加 `--video-url`，或先 `upload --file` 拿地址 |
| `400 video_url_required` | 腾讯线字段名是 `video_url`，不是 `videoUrl` | 本包已按档位自动选字段；自己调接口时按 `references/api-contract.md` |
| `400 pixverse_empty_url` | `/video/upscale` 没收到视频地址 | 同上，先 `upload` |
| `400 duration_unknown` | 服务端 ffprobe 探测失败，且没传 duration | 显式加 `--seconds`（本包按秒档强制要求） |
| `400 url_not_allowed` | 视频地址不在本站白名单 | 先 `POST /api/v1/upload`（免费），用返回的 `oss.gpu.likeadmin.cn/openapi/...` |
| `401` / `403` | Key 缺失、过期、或没权限 | `--key` / `A7W_API_KEY` / `~/.a7w/config.json` 三选一；确认 Key 属于 api.a7w.cn |
| `502 FailedOperation.InvalidMpsUser` | 腾讯 MPS 网关凭据坏了 | 这是平台侧问题；换 `--tier superres`，或等修复。失败任务全额退 |
| `404 model_not_found` | 模型在目录里，但当前 Key 没授权 | `topaz-video-upscale` 实测如此；加 `--allow-blocked` 只会再收一次 404，净 0 点 |
| `404` + HTML | 路径前缀不对（SPA 兜底） | 例如 `/api/v1/video/viapi/upscale` 是 404，正确是 `/api/v1/video/upscale` |
| `400 task_not_exist` | 查询路由对，但任务号不存在 | 核对 `--task-id`；模型层任务用 `/api/v1/videos/<id>`，VIAPI 用 `/video/viapi/result/<id>` |
| `200 {"code":0,"msg":"任务不存在"}` | 通用 `/api/v1/tasks/<id>` 查不到视频任务 | 换 `/api/v1/videos/<id>` 或对应档位的查询路由 |
| 提交成功但状态 `refunded` | 上游失败，平台已退款 | 看 `netPoints`；腾讯 502 就是这种，实扣 0 点 |
| 余额被冻了一下又回来 | `reserve_sync` 先冻再退 | 净 0 点；`doctor` 已避开这类探针 |

---

## 3. 闸门与退出码

| 退出码 | 含义 | 典型触发 |
|---|---|---|
| 0 | 成功 | 免费命令 / 提交成功 |
| 2 | 用法错 | 缺 `--video-url`、`--seconds`、档位未知、`--allow-blocked` 未加 |
| 3 | 自检未过 | `doctor` 有检查项失败（网络 / 价目漂移） |
| 4 | 需要 `--yes` | 真提交前没确认；消息里会写清要花多少点 |
| 5 | 预算不足 | 预计点数 > `--budget`，**一个请求都不发** |
| 6 | 调用失败 | 上游 4xx/5xx、网络异常、查不到任务 |
| 1 | 内部错 | 未捕获异常，带 traceback |
| 130 | 中断 | Ctrl+C |

`--budget` 单位是**点**，1 元 = 100 点，默认 5000（50 元）。
`--budget 0` 会直接退 5：0 点预算等于不授权任何调用。

---

## 4. 模型层专项

### 4.1 为什么 `models` 全是 baseline

`/api/v1/me/tasks` 里没有这 4 个模型的 `actualPrice`。本包不会编单价，
只报「50 点起（通配保底）」。跑过一单后，再执行：

```bash
python3 scripts/run.py models --pages 20
```

就会自动出现 `source=live` 和真实成交区间。

### 4.2 为什么 Topaz 视频一直 404

`POST /api/v1/videos {"model":"topaz-video-upscale"}` 实测返回
`404 model_not_found`。目录里有，但当前 Key 没开通这个模型。
等平台开通后再跑；本包默认在 `submit` 前拦下，避免白跑。

### 4.3 为什么 Recraft 会冻 20 点

`POST /api/v1/images/generations` 走的是「先 `reserve_sync` 预估、失败再 `refund`」。
缺 `image` 素材时，同端点流水里出现过（2026-11-08 09:16）：

```text
charge  -20  reserve_sync:/api/v1/images/generations
refund  +20  refund:submit_failed:/api/v1/images/generations
```

净 0 点，但钱包会短暂动一下。补 `image` 后再提交；`doctor` 不探这个端点。

### 4.4 模型层真实单价怎么算

见 `references/model-pricing.md`：按 `model` 归集 `actualPrice`，取最低 / 中位 / 最高，
有样本 `source=live`，无样本 `source=baseline`。

---

## 5. 输出与编码

### 5.1 Windows 控制台出现 `?`

本包所有输出都过 `safe`：cp936 编不出的字符替换成 `-`，不会变 `?`。
金额一律写「元」，U+00A5 这个符号在 cp936 下编不出。

自测：

```powershell
$env:PYTHONIOENCODING="gbk"
python -u scripts/run.py doctor
```

GBK 严格解码应成功，输出里 0 个问号。

### 5.2 JSON 里出现 `-`

同样是 `safe` 对 cp936 外字符的替换。JSON 结构不变，字段值可能把
en dash / 特殊符号换成 `-`。

### 5.3 `--json` 只有一个文档

成功：`{"ok": true, ...}`。
失败：`{"ok": false, "exit": N, "error": {"kind": "...", "message": "..."}}`。
`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。

---

## 6. 本轮花费自查

```bash
# 1) 看余额
python3 scripts/run.py doctor

# 2) 看流水（最近 1000 条）
python3 scripts/run.py status --task-id <你的任务号> --tier superres

# 3) 直接查网关流水
curl -H "Authorization: Bearer $A7W_API_KEY" \
  "https://api.a7w.cn/user/balance/logs?limit=1000"
```

`charge` 是冻结 / 预扣，`refund` 是退回，两者相加为净额。
腾讯 502 的任务：`status=refunded`、`chargedPoints=0`，净 0 点。
