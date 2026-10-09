# 三剪客 · 视频增强台

把 **`api.a7w.cn` 在架的那 10 档视频增强能力**收成一个命令行台子。
它们共用同一套「上传 → 提交 → 轮询 → 下载」流程，只是路径与单价不同 ——
所以做成**一个台子**，而不是 10 个包。

**按秒计费**，所以本包的重点不是"能调用"，而是**让你在花钱之前知道要花多少**：
免费 `tiers` 看 10 档价目、`cost` 算这一条多少钱、`--dry-run` 把免费闸门全验一遍却不提交。

| 档位 | 中文名 | 点/秒 | 单条上限 | 素材要求 |
|---|---|---|---|---|
| `upscale` | 4K旗舰版 | 30 | 30 秒 | 任意公网地址 |
| `superres` | 标准超分 1080P | 9 | 600 秒 | 本站素材 |
| `superres2k` | 高清超分 2K | 15 | 600 秒 | 本站素材 |
| `superres4k` | 超清超分 4K | 20 | 600 秒 | 本站素材 |
| `portrait` | 人像增强 | 18 | 600 秒 | 本站素材 |
| `subtitle` | 字幕擦除 | 9 | 600 秒 | 本站素材 |
| `cartoon` | 人像卡通化 | 24 | 600 秒 | 本站素材 |
| `segment` | 人像抠像 | 9 | 60 秒 | 本站素材 |
| `enhance` | 画质综合增强 | 15 | 600 秒 | 本站素材 |
| `colorize` | 视频校色 | 9 | 600 秒 | 本站素材 |

1 元 = 100 点。另有 `portrait` 上游当前**公测免费**、成本 0，售价 18 点/秒是纯毛利档（输入需 <1920×1080）。

---

## 安装

零依赖，只用 Python 标准库。**不需要 pip install 任何东西。**

```bash
git clone <本包地址>        # 或直接把 skills/sanjianke-video-vr 拷走
cd sanjianke-video-vr
python3 scripts/run.py tiers      # 先看看有哪些档位、各多少钱（免费，连 Key 都不用）
```

需要 Python 3.7+。**可选**：装 `ffmpeg`（自带 `ffprobe`）后，本包能自动探测素材时长与分辨率；
不装也能用，但提交时要显式传 `--duration`（本包**不会**替你猜 5 秒）。

---

## 配置 Key

**本包不内嵌任何密钥，也不代付费用。** 到 [算力集市 api.a7w.cn](https://api.a7w.cn/) 注册领 Key。

```bash
# 方式一：存起来（推荐）
python3 scripts/run.py login --key sk-你的key

# 方式二：环境变量
export A7W_API_KEY=sk-你的key          # Windows: set A7W_API_KEY=sk-你的key

# 方式三：临时传
python3 scripts/run.py --key sk-你的key tiers
```

读取顺序：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。

---

## 用法

### 1. 先看清楚再花钱

```bash
python3 scripts/run.py tiers                        # 10 档 + 单价 + 上限 + 素材要求
python3 scripts/run.py doctor                       # 体检：Key/档位/上传/素材入口判据(零成本实测)/ffprobe
python3 scripts/run.py cost --for superres:12       # 这条 12 秒的片子要 108 点（¥1.08）
python3 scripts/run.py cost --for upscale:10 --for subtitle:120
```

`cost` 是**纯本地计算，一次请求都不发**；`tiers` 与 `doctor` 只读免费接口，**不建任务**。

### 2. 白验一遍（不花钱）

```bash
python3 scripts/run.py enhance --tier superres \
    --url https://cdn2.jiujiushuyuan.cn/vr/demo/your.mp4 \
    --duration 12 --dry-run
```

`--dry-run` 会把**素材入口判据、素材可达性、时长、单条上限、输入规格、预算**全部验一遍，
然后**直接返回，不提交**。剩下唯一会花钱的一步就是 POST 上去。

### 3. 正式提交

```bash
# 提交并一次轮询到出片
python3 scripts/run.py enhance --tier superres \
    --url https://cdn2.jiujiushuyuan.cn/vr/demo/your.mp4 \
    --duration 12 --budget 500 --yes --wait --out out.mp4

# 先提交、稍后再查
python3 scripts/run.py enhance --tier upscale --url <地址> --duration 8 --yes
python3 scripts/run.py status task_xxxx --out out.mp4
python3 scripts/run.py tasks
```

不加 `--yes` 只会**打印报价并退出 4**，不会提交。`--budget` 的**单位是点**。

---

## ⚠️ 三件必须在动手前知道的事

### 1. `upscale` 档不校验素材可达性

给它一个 404 地址，它**照样返回 201 并冻结点数**（30 点/秒，2 秒就 60 点）。
**本包对每一档都先探素材可达性，探不到就拒绝提交**；强行绕过要显式 `--force`。

### 2. `duration` 不传就可能被按 5 秒收费

服务端在 `duration` 缺失时会自己 `ffprobe`，**探测不到就按 5 秒收费**。
本包一律先本地探测；拿不到就**报错要求显式 `--duration`**，绝不静默按 5 秒提交。

### 3. 9 档只收「本网关素材」—— 先 `upload`

**素材通道只有一条：用本网关的 `upload` 把本地文件传上来，再把返回的地址交给 `--url`。**
**不再需要任何第三方站点。**

```
POST api.a7w.cn/api/v1/upload      multipart/form-data，字段名 file
      ↓ 200 返回
https://oss.gpu.likeadmin.cn/openapi/…      ← 把这个地址原样交给 --url 即可
```

```bash
python3 scripts/run.py upload 你的视频.mp4       # 免费，不建任务
python3 scripts/run.py doctor                    # 零成本实测线上入口判据
python3 scripts/run.py enhance --tier colorize --url <上面返回的地址> \
    --duration 12 --budget 200 --yes --wait --out out.mp4
```

⚠️ **入口判据以线上为准。** `doctor` 的「入口白名单」一项会**零成本实测**：
拿一个上传域里**根本不存在的地址**去打这一档 —— **未放行 → 400 `url_not_allowed`；
已放行 → 502 `oss_mirror_failed`**。两条路都在**冻结扣费之前**返回，不建任务、不扣费。

任意第三方地址会被服务端在**扣费之前**拒掉（**不花钱**）；本包还会在本地**提前**拦住，
不会让你白撞一次请求。跑 `doctor` 可看到完整判定。

### ⚖️ 字幕擦除的合规边界

`subtitle` 档去除画面硬字幕。使用它意味着你承诺：**你对素材拥有合法权利**，
**不得用于去除他人作品的权利管理信息**，也不得用于规避平台原创声明或盗用他人内容。
授权责任在使用者。拿不准就不要做这一档。

---

## 退出码与 `--json` 契约

```json
{"ok": true,  ...}
{"ok": false, "exit": 3, "error": {"kind": "gate", "message": "..."}}
```

| exit | 含义 | `error.kind` |
|---|---|---|
| 0 | 成功 | — |
| 1 | 内部错误 | `internal` |
| 2 | 用法错误 | `usage` |
| 3 | 闸门没过（素材入口判据/可达性/时长/上限/规格） | `gate` |
| 4 | 需要 `--yes`（报价已打印，未提交） | `confirm` |
| 5 | 预算超限 | `budget` |
| 130 | 被中断 | `interrupt` |

`--json` 写在子命令前面或后面都可以。

---

## 闸门顺序（为什么 `--dry-run` 很值钱）

线上服务端判定顺序是「空 URL → 素材入口判据 → 素材可达性/转存 → ffprobe 时长 →
单条上限 → 输入规格 → **冻结扣费** → 提交上游」。**扣费点很靠后**，
所以参数错、地址不在入口判据内、规格不符全部**在扣费之前返回，天然免费**。
本包在此之上又补了「素材可达性（替 `upscale` 补课）」「本机 ffprobe」「预算」三道，
全部发生在提交之前。

---

## 文件结构

```
sanjianke-video-vr/
├── SKILL.md                      主文档（10 档、闸门、合规边界、全部子命令）
├── README.md                     本文件
├── LICENSE.md                    MIT
├── references/
│   ├── api-contract.md           10 档完整契约（请求/查询/单价/上限/素材入口判据/闸门）
│   ├── cost-and-limits.md        计费口径、上限、输入规格、成本与毛利
│   └── troubleshooting.md        报错对照、排错顺序、真机实测记录
└── scripts/
    ├── run.py                    命令行台子（零依赖）
    └── a7w.py                    算力网关零依赖客户端（上传/请求/落盘）
```

---

## 已知边界（如实说明）

- **9 档只收本网关素材**：先用 `upload <文件>` 上传、再用返回的地址提交（见上文 §3）。
  **入口判据以线上为准** —— `doctor` **零成本实测**并如实报告（400 = 未放行，502 = 已放行，
  两条路都在扣费之前，都不花钱）。不需要任何第三方站点。
- **`tiers` 的在线权威源不稳定**：线上 `GET /api/v1/video/viapi/tools` 早先免鉴权可读，
  后来变为 401/404。本包自动退回内置档位表（取自 `api.a7w.cn` 在架能力）
  并**如实打印"在线源当前不可达"**。价格与规格以线上为准。
- **输入规格是上游限制**，本包只能提前拦，不能改变上游行为。

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
