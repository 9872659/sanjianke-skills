# 文生视频模型台 · 一句话横评 5 个模型，最低 0.44 元一条

**同一句话，5 个视频模型先报价再出片。**
最便宜 44 点（0.44 元），最贵上界 3,045.71 点（30.46 元）—— 差 **11.7 倍**，看完价再决定跑一个还是全跑。

实测：`muse-video` **44 - 260 点/条**、`Seedance 2.0` **145.73 点起**、`Seedance 2.5` **762.30 点起**、
`Wan 3.0` **300 点**（8 笔成交全同价）。

---

## 三条干货

### 一、提交端点分两条，走错就是 404

目录里 47 个视频型号，`POST /api/v1/videos` 只认 4 个裸模型层 ID
（`muse-video`、`sd/doubao-seedance-2-0-260128`、`volcengine/doubao-seedance-2-5-260628`、`wan3.0-video`）。
拿目录型号去打这条：

```
POST /api/v1/videos  {"model":"kling-4-0"}
-> HTTP 404  {"error":{"code":"model_not_found",
    "message":"The model `kling-4-0` does not exist or you do not have access to it."}}

POST /api/v1/videos/generations  {"model":"kling-4-0"}
-> HTTP 400  {"error":"prompt or content field is required","type":"invalid_request_error"}
```

同一个型号名，一条 404、一条 400。**`/api/v1/videos/generations` 才是横评的提交端点** ——
本包按型号的历史成功路径分流：`muse-video` 走 `/videos`，其余 12 个走 `/videos/generations`。
`--route` 可以强制指定。

### 二、kling 家族是 14 个型号，不是一个

`GET /api/v1/models` 里 kling 一共 14 条：`kling-4-0`、`kling-v2-1-pro`、`kling-v2-1-standard`、
`kling-2-1-master`、`kling-ai-avatar-standard`、`kling-ai-avatar-pro`、`kling-2-5-turbo-pro`、
`kling-2-6`、`kling-2.6-motion-control`、`kling-3.0-video`、`kling-3.0-motion-control`、
`kling-3-0-turbo`、`kling-3.0-omni-transformation`、`kling-3-0-omni`。

14 条**全部**在 `/videos/generations` 上停在 `400 prompt is required`（2026-11-08 逐条实测，0 点）。
本包默认横评最新的一档 `kling-4-0`；想跑别的档直接写型号名：`--models kling-3-0-omni`。

### 三、单价只能反推，价目表里没有

`GET /api/v1/pricing` 的 **115 条规则**里没有 `/api/v1/videos/generations`，
整张表也没有 `modelPricing` 键；模型层命中的是通配 `*`：

```json
```

所以真实单价只存在于 `GET /api/v1/me/tasks` 的 `actualPrice` 里。本包按 `model` 归集：
跑过标 `source=live`（显示你的成交区间与笔数），没跑过用同路 16 笔区间标 `source=baseline`，
**不编单价**；每跑成功一次，下一次报价自动换成你自己的成交价。

---

## 价目表（2026-11-08，1 元 = 100 点）

| 型号 | 报价（点/条） | 折合 | 来源 |
|---|---|---|---|
| `muse-video` | **44 - 260** | 0.44 - 2.60 元 | 本账号 8 笔成交；官方 11 点/秒 |
| `sd/doubao-seedance-2-0-260128` | **145.73 - 3,000** | 1.46 - 30 元 | 本账号 5 笔成交 |
| `wan3.0-video` | **300** | 3 元 | 本账号 8 笔成交，全是 300 |
| `volcengine/doubao-seedance-2-5-260628` | **762.30 - 3,045.71** | 7.62 - 30.46 元 | 本账号 3 笔成交 |
| `kling-4-0` / `veo3.1-pro` / `veo3.1-fast` / `hailuo-02-standard` / `hailuo-02-pro` / `vidu-q4` / `runway` / `pixverse-v6` / `pixverse-v6-max` | 44 - 3,045.71 | 0.44 - 30.46 元 | 本账号 0 笔成交，标 baseline，保底 50 点 |

`--budget` 单位是「点」，默认 12,500 点（125 元）。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 0 点自检
python3 scripts/run.py doctor

# 3) 0 点报价：同一句话，5 个模型逐个报
python3 scripts/run.py cost

# 4) 横评出片
python3 scripts/run.py gen --models muse-video,kling-4-0 \
    --prompt "雨夜街头，霓虹灯下撑伞的女孩回头" --seconds 5 --yes
```

---

## 用法示例

```bash
# 看 13 个型号的报价 / 来源 / 提交路径
python3 scripts/run.py catalog

# 只报 3 个型号
python3 scripts/run.py cost --models muse-video,kling-4-0,veo3.1-pro --seconds 5

# 同一句话跑 5 个模型，落盘 + 对比清单
python3 scripts/run.py gen \
    --models muse-video,sd/doubao-seedance-2-0-260128,kling-4-0,veo3.1-pro,hailuo-02-standard \
    --prompt "海边日落，浪花慢镜头，暖调" --seconds 5 --yes

# 先看请求，一分钱不花
python3 scripts/run.py gen --models muse-video,kling-4-0 --prompt "一只橘猫" --dry-run

# 竖屏 + 等到完成并下载
python3 scripts/run.py gen --models vidu-q4 --prompt "女孩转身走向镜头" \
    --seconds 5 --size 720x1280 --yes --wait

# 查任务 / 等任务（都免费）
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py wait task_xxx --outdir .

# 重出对比清单（免费）
python3 scripts/run.py sheet --run ./run-20261108-101500
```

### 落盘规范

```
run-20261108-101500/
├── 01-muse_video.mp4        序号-型号.mp4
├── 02-kling_4_0.mp4
├── manifest.json            结构化结果（含实际点数）
└── 对比清单.md              同一句话的五个模型，一张表看完
```

型号里的 `.` 与 `/` 会换成 `_`，文件名全平台可用。

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--models` | 5 个默认型号 | 逗号分隔，例如 `a,b,c`，一次最多 8 个 |
| `--model` | — | 只跑一个型号 |
| `--prompt` | 必填 | 所有模型共用同一句，≤4000 字 |
| `--seconds` | 5 | 每条多少秒（1 - 180，按型号支持范围） |
| `--size` | 模型默认 | `1280x720` / `720x1280` |
| `--extra` | — | 额外请求字段，JSON 对象，例如 `{"ratio":"9:16"}` |
| `--route` | `auto` | `auto` / `generations` / `videos` |
| `--wait` | — | 提交后等到完成并自动下载 |
| `--outdir` | `.` | 落盘根目录 |
| `--budget` | 12500 | 点数上限（单位：点） |
| `--pages` | 10 | 翻几页 me/tasks 找成交价（每页 20 条） |
| `--refresh` | — | 忽略本机价格缓存（6 小时） |
| `--allow-any-model` | — | 型号不在 13 个里也允许提交（按同路区间报价） |
| `--yes` | — | 确认真实出片 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 13 个型号 + 报价 + 来源 + 提交路径 |
| `cost` | 免费 | 同一句话多模型逐个报价，按上界排序 |
| `doctor` | 免费 | 6 个只读端点 + 3 个 400 探针 + 余额/流水对比 |
| `gen` | 按条 | 多模型横评出片，落盘 + manifest + 对比清单 |
| `status` | 免费 | 查任务（只走 `GET /api/v1/tasks/<id>`） |
| `wait` | 免费 | 等任务完成并下载 |
| `sheet` | 免费 | 用 manifest 重出对比清单 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（型号不在名单 / 缺 prompt / 秒数越界 / 命令行缩写） |
| `4` | 需要确认 —— 没给 `--yes`，会先告诉你这次要花多少 |
| `5` | 超预算 —— 一个出片请求都不发 |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "runId": "20261108-101500", "dir": "./run-20261108-101500",
 "results": [{"model": "muse-video", "status": "submitted", "taskId": "task_xxx",
              "gate": 260, "source": "live"}],
 "totalEstimated": 3305.71, "totalActual": null}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

---

## 和已有包的分工

| 你的需求 | 用哪个包 | 为什么 |
|---|---|---|
| 同一句话横评几个视频模型，选一个或全跑 | **本包** | 13 个型号逐个报价 + 同 prompt 出片 + 对比清单 |
| 只要 muse-video：4 - 180 秒、按秒计费、凑档不加钱 | `sanjianke-muse-video` | 单模型深度：秒数档位、首帧/多图参考、3 分钟长片 |
| 只要 Seedance / Wan 模型层，含应用层比价 | `sanjianke-model-video` | 单家族深度：4 个模型、应用层 11,000 点对照 |
| 看全站应用层与模型层的差价排行 | `sanjianke-price-radar` | 6 个只读子命令、115 条规则、app-vs-model 排行 |
| 视频后处理（超分 / 去字幕 / 换脸 / 擦 logo） | `sanjianke-video-lab` | 11 档后处理能力，按秒/按次计价 |

---

## 文件结构

```
sanjianke-video-models/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文 + 单价反推法 + 路由分工）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，16,797 B 逐字节一致）
    └── run.py                本包命令层
```

---

## 实测记录

```
2026-11-08 doctor（6 个只读端点 + 3 个 400 探针）
  √ 模型目录        HTTP 200 · 共 316 条 · 视频型号 47 个 · kling 家族 14 个
  √ 价目表          HTTP 200 · 115 条规则 · 模型层规则 表里没有 · 通配保底 50 点
  √ 提交端点        HTTP 400 · model field is required
  √ 型号可提交      HTTP 400 · prompt or content field is required（kling-4-0）
  √ 路由分工        HTTP 404 · model_not_found（/videos 不认 kling-4-0）
  √ 余额前后对比    前 999,997,393,470.26 -> 后同值 · 差 0 点
  √ 流水            最近 100 条里视频线 2 笔 · 今日净 0 点
  本轮花费 0 点
```

```bash
$ python3 scripts/run.py cost
  合计（按上界）：12,397.13 点 = 123.97 元
  按上界：最贵 hailuo-02-standard 3,045.71 点 · 最便宜 muse-video 260 点 · 相差 11.7 倍
```

---

## 免责

- 单价按「点/条」计，实际以响应里的 `usage` 与 `GET /user/balance/logs` 为准。
- 生成内容的合规责任在使用者：用在合法、有授权的素材与用途上。

## 许可证

MIT，见 `LICENSE.md`。

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
