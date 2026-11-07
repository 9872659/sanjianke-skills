# 视频后处理台 11 个能力一个命令
**9 点一秒起。** 一条老片，去台标、擦字幕、校色、增强，11 个工序一条命令跑完 —— 全部走 [api.a7w.cn](https://api.a7w.cn/)，异步两步、零依赖。

| 最便宜的三档 | 单价 | 10 分钟 |
|---|---|---|
| `colorize` 校色 / 黑白上色 | **9 点/秒** | 5,400 点 |
| `segment` 人像抠像 / 绿幕 | **9 点/秒** | 5,400 点 |
| `subtitle` 字幕擦除 | **9 点/秒** | 5,400 点 |

1 元 = 100 点。最贵的一档 `restore`（视频修复）36 点/秒。

---

## 11 档能力与价目（按点/秒从低到高）

| 能力 | `--tier` | 单价 | 10 分钟 | 干什么 |
|---|---|---|---|---|
| 校色 / 黑白上色 | `colorize` | **9 点/秒** | 5,400 点 | 黑白片自动上色，还原自然色调 |
| 人像抠像 / 绿幕 | `segment` | **9 点/秒** | 5,400 点 | 输出人像 mask 视频，换背景用 |
| 字幕擦除 | `subtitle` | **9 点/秒** | 5,400 点 | 擦掉硬字幕，二创换字幕的第一步 |
| 画质综合增强 | `enhance` | 15 点/秒 | 9,000 点 | 清晰度 / 对比度 / 细节整体提一档 |
| 人像增强 | `portrait` | 18 点/秒 | 10,800 点 | 只提人脸清晰度，GPEN 路线 |
| 换脸 / 人脸融合 | `faceswap` | 20 点/秒 | 12,000 点 | 视频里最大的人脸换成你的人脸图 |
| 镜头检测 | `shot` | 20 点/次 | 20 点 | 按镜头切分，返回切点帧号 |
| 人像卡通化 | `cartoon` | 24 点/秒 | 14,400 点 | 真人转动漫风 |
| 硬字幕 / 演职员表 OCR | `castcrew` | 25 点/次 | 25 点 | 抽硬字幕与滚动演职员表，附 SRT |
| 台标 / Logo 擦除 | `delogo` | 25 点/次 | 25 点 | 擦台标、平台 logo（最多 2 个区域） |
| 视频修复 | `restore` | 36 点/秒 | 21,600 点 | 去划痕 / 噪点 / 闪烁，老片抢救 |

- 按秒档按视频秒数计费，**最小计 1 秒**；按次档与素材时长无关。
- 按秒档**先按秒数冻结、完成后按实际时长结算**，任务失败**全额退回**。
- `portrait` 的价签写 18 点/秒，规则注里写「公测免费」，以实际账单为准。

---

## `--tier` 怎么选

| 你要干什么 | 用哪个 |
|---|---|
| 老片发灰、偏色、黑白片要上色 | `colorize`（9 点/秒，最便宜） |
| 二创要换字幕，先把原字幕抹掉 | `subtitle`（9 点/秒） |
| 换背景 / 做绿幕素材 | `segment`（9 点/秒，输出人像 mask） |
| 片子糊、要整体提一档 | `enhance`；只想把人脸提清楚用 `portrait` |
| 画面有划痕、噪点、闪烁 | `restore`（36 点/秒） |
| 视频里换一张脸 | `faceswap`（还要 `--face-url` 人脸图） |
| 真人转动漫风 | `cartoon` |
| 去台标 / 平台 logo | `delogo`（25 点/次） |
| 要分镜点、要按镜头切片 | `shot`（20 点/次，纯结构化结果） |
| 要硬字幕文本、要演职员表 SRT | `castcrew`（25 点/次） |

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检：Key / 11 个端点 / 价目表 / 查询 / 上传
python3 scripts/run.py doctor

# 3) 上传本地片子，拿一个能直接提交的地址（免费）
python3 scripts/run.py upload --file input.mp4

# 4) 先算钱，再提交
python3 scripts/run.py cost --tier delogo
python3 scripts/run.py submit --tier delogo \
    --video-url "https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4" --yes

# 5) 查结果
python3 scripts/run.py status --task-id task_xxx
```

---

## 三条别人不会告诉你的

### 一、11 档走的不是同一条路径

空 body 探针实测（`doctor` 每次都会重跑这 11 条）：

| 能力 | 扁平 `/api/v1/video/X` | `/api/v1/video/viapi/X` | 本包用 |
|---|---|---|---|
| `restore` | **400 `pixverse_empty_url`** | **404 `unknown_tool`** | 扁平 |
| `faceswap` | **404（SPA 兜底）** | **400 `empty_url`** | viapi |
| `segment` | **404（SPA 兜底）** | **400 `empty_url`** | viapi |
| `cartoon` | **404（SPA 兜底）** | **400 `empty_url`** | viapi |
| 其余 7 档 | 400 `empty_url` | 400 `empty_url` | viapi |

`restore` 只有扁平那条通；换脸 / 抠像 / 卡通化只有 viapi 那条通；其余两条都能走，本包统一走 viapi。`catalog` 会逐档把实际路径打出来。

### 二、`videoUrl` 用平台托管的地址

外站地址会在门口被挡下，实测原文：

```json
{"error":{"code":"url_not_allowed","message":"videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）","type":"relay"}}
```

所以配了 `upload`：`POST /api/v1/upload`，multipart 字段名 `file`，**免费**，单文件默认上限 512 MB，返回：

```json
{"code":1,"msg":"success","data":{"url":"https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4","path":"openapi/18/20261107/xxxx.mp4","name":"input.mp4","size":1024,"mime_type":"video/mp4","type":"video"}}
```

`data.url` 最长 24 小时有效，拿到就直接喂 `submit`。`submit` 会先本地预检这条白名单，不合格当场退 `2`，省一次白跑（`--allow-any-url` 可跳过预检）。

### 三、按秒档「先冻结、后结算」

提交时按 `duration` 预冻结（缺省 5 秒），完成后按**实际时长**结算，任务失败全额退回。所以：

- `submit` 不传 `--duration` 也能跑，`cost` 就按 5 秒给估算；
- 想算准就显式传秒数，`--budget` 是硬闸门：**预计点数超上限，一个请求都不发**。

---

## 常用命令

```bash
python3 scripts/run.py catalog                                     # 11 档 + 路径 + 单价
python3 scripts/run.py cost                                        # 全档 1/10/30 分钟价目
python3 scripts/run.py cost --tier restore --seconds 600           # 10 分钟多少钱
python3 scripts/run.py submit --tier colorize --video-url "..." --dry-run
python3 scripts/run.py submit --tier faceswap --video-url "..." --face-url "..." --yes
python3 scripts/run.py submit --tier restore --video-url "..." --duration 180 --budget 8000 --yes
python3 scripts/run.py status --task-id task_xxx --tier colorize
python3 scripts/run.py log --limit 10
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--tier` | 必填 | 11 档之一，见 `catalog` |
| `--video-url` | 必填 | 平台托管的视频地址（先 `upload`） |
| `--duration` | 5 | 视频秒数，用于预冻结；按次档不需要 |
| `--face-url` | — | 人脸参考图，任意 http(s) 图片地址（只 `faceswap`） |
| `--seed` / `--callback-url` | — | 只 `restore` 用 |
| `--route` | `auto` | `auto` / `flat` / `viapi`，强制走某条路径 |
| `--allow-any-url` | — | 跳过本地白名单预检，把地址交给上游判断 |
| `--file` | — | `upload` 用，本地文件路径 |
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实提交并冻结点数 |
| `--dry-run` | — | 只打印请求，不提交 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 11 档能力 + 每档实际路径 + 单价 |
| `cost` | 免费 | 1 / 10 / 30 分钟价目 |
| `doctor` | 免费 | 自检 Key / 11 个端点 / 价目表 / 查询 / 上传 |
| `upload` | 免费 | 上传本地视频，拿可提交的地址 |
| `submit` | **按档计费** | 提交任务（要 `--yes`） |
| `status` | 免费 | 查任务（`video/viapi/result/{id}`，带 `refund`） |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（参数缺失、地址预检没过、选项缩写） |
| `3` | 自检没过（`doctor` 出现 ×） |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "tier": "colorize", "taskId": "task_xxx", "status": "PENDING",
 "duration": 30, "cost": 270, "balance": 999999, "estimatedPoints": 270}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`

`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`；`--json` 写在子命令**前后都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-video-lab/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（文档原文 + 实测返回）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 计费口径与保底

- 成品链接有效期约 **30 分钟**，`status` 拿到就转存。
- 查任务用 `GET /api/v1/video/viapi/result/{taskId}`（免费，带 `status` / `message` / `refund`）；
  通用 `GET /api/v1/tasks/{taskId}` 只服务模型与应用任务，实测查不到后处理任务。
- 状态会来回：实测同一 taskId 先 `failed` + `refund: 45`，几分钟后又 `processing`（平台自动重试），隔 30 秒再查一次。
- `shot` / `castcrew` / `delogo` 的价签写「点/次」，引擎规则是 `per_second` —— 本包按价签收一次，`cost` 会把两种口径都打出来，以实际账单为准。
- 按秒档最小计 1 秒；任务失败全额退回。
- `--budget` 与 `--yes` 是本地闸门：预算内才发请求，`--yes` 到了才提交。

---

## 合规与边界

- 生成内容的合规责任在使用者：请用于有授权的素材与合法用途。
- 真实扣费以任务完成时返回的 `usage.points_cost`（或 `cost`）为准，`cost` 给的是预估。
- 上传接口仅作临时中转，返回地址最长 24 小时，请及时转存到自己的存储。

---

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
