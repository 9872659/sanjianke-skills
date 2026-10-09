# 三剪客 · 人像增强

把 **`api.a7w.cn` 在架能力里的「人像增强」这一档**做成一个**独立的**命令行工具：
只做这一件事，参数与提示都收窄到这一档。

| 项 | 值 |
|---|---|
| 档位 id | `portrait` |
| 提交路径 | `POST /api/v1/video/viapi/portrait` |
| 单价 | **18 点/秒**（¥0.18/秒，1 元 = 100 点） |
| 单条上限 | **600 秒** |
| 素材要求 | 本网关素材（先 `upload` 拿地址） |
| 输入规格 | 输入 **<1920×1080**；上游当前公测免费 |

**按秒计费**，所以本包的重点不是「能调用」，而是**让你在花钱之前知道要花多少**：免费 `info` 看档位、`cost <秒数>` 算这一条多少钱、`--dry-run` 把免费闸门全验一遍却不提交。

---

## 安装

零依赖，只用 Python 标准库。**不需要 pip install 任何东西。**

```bash
git clone <本包地址>        # 或直接把 sanjianke-vr-portrait 目录拷走
cd sanjianke-vr-portrait
python3 scripts/run.py info     # 先看这一档的单价、上限、素材要求（免费）
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
python3 scripts/run.py --key sk-你的key info
```

读取顺序：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。

---

## 用法

### 1. 先看清楚再花钱

```bash
python3 scripts/run.py info                     # 单价 / 上限 / 素材要求 / 输入规格
python3 scripts/run.py points                   # 点数余额
python3 scripts/run.py doctor                    # 体检：Key/上传/素材入口/ffprobe
python3 scripts/run.py doctor --url <你的地址>    # 顺手验素材可达性 + 素材入口判定
python3 scripts/run.py cost 12                   # 这条 12 秒的片子要 216 点（¥2.16）
```

`cost` 是**纯本地计算，一次请求都不发**；`info` / `points` / `doctor` 只读免费接口，**不建任务**。

### 2. 白验一遍（不花钱）

```bash
python3 scripts/run.py upload 你的视频.mp4      # 先拿一个可用地址（免费）
python3 scripts/run.py enhance \
    --url <上面返回的地址> \
    --duration 12 --dry-run
```

`--dry-run` 会把**素材入口判据、素材可达性、时长、单条上限、输入规格、预算**全部验一遍，
然后**直接返回，不提交**。剩下唯一会花钱的一步就是 POST 上去。

### 3. 正式提交

```bash
# 提交并一次轮询到出片
python3 scripts/run.py enhance \
    --url <`upload` 返回的地址> \
    --duration 12 --budget 360 --yes --wait --out out.mp4

# 先提交、稍后再查
python3 scripts/run.py status task_xxxx --out out.mp4
python3 scripts/run.py tasks
```

不加 `--yes` 只会**打印报价并退出 4**，不会提交。`--budget` 的**单位是点**。

---

## ⚠️ 动手前必须知道的事

### 1. 这一档只收「本网关素材」

本档**只收「本网关素材」** —— 先用本网关的 `upload` 把本地文件传上来，再把返回的地址交给 `--url`。**不再需要任何第三方站点。**

```
POST api.a7w.cn/api/v1/upload      multipart/form-data，字段名 file
      ↓ 200 返回
https://oss.gpu.likeadmin.cn/openapi/…      ← 把这个地址原样交给 --url 即可
```

`upload` 子命令就是干这件事的：

```bash
python3 scripts/run.py upload 你的视频.mp4
# → url = https://oss.gpu.likeadmin.cn/openapi/…
python3 scripts/run.py doctor --url <上面那个 url>   # 免费确认能提交
```

任意第三方地址会被服务端在**扣费之前**拒掉（`400 url_not_allowed`，**不花钱**），本包还会**提前**在本地拦一道，让你不用白跑一次请求。

⚠️ **入口白名单以线上为准**：`doctor` 会**零成本实测**这道判据并如实报告（探针被 400 拒 = 该前缀当前未放行；被 502 挡在素材镜像 = 已放行，两者都不扣费）。若某天未放行，改走本站素材地址，或先用 `sanjianke-vr-upscale-4k`（不收白名单，收任意公网地址）。

### 2. `duration` 不传就可能被按 5 秒收费

服务端在 `duration` 缺失时会自己 `ffprobe`，**探测不到就按 5 秒收费**。
本包一律先本地探测；拿不到就**报错要求显式 `--duration`**，绝不静默按 5 秒提交。

### 3. 免鉴权在线档位表当前不可达

`GET /api/v1/video/viapi/tools` 早先免鉴权 200，后来变为 401/404。本包单价取自 **`api.a7w.cn` 在架能力**（内置档位表），`info` 会如实打印来源，在线源恢复时自动采用线上值。**价格与规格以线上为准。**


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
| 3 | 闸门没过（白名单/可达性/时长/上限/规格） | `gate` |
| 4 | 需要 `--yes`（报价已打印，未提交） | `confirm` |
| 5 | 预算超限 | `budget` |
| 130 | 被中断 | `interrupt` |

`--json` 写在子命令前面或后面都可以。

---

## 闸门顺序（为什么 `--dry-run` 很值钱）

线上服务端判定顺序是「空 URL → 素材入口判据 → 素材可达性/转存 → ffprobe 时长 →
单条上限 → 输入规格 → **冻结扣费** → 提交上游」。**扣费点很靠后**，
所以参数错、地址不在入口判据内、规格不符全部**在扣费之前返回，天然免费**。

| 闸门 | 内容 | 不过时 |
|---|---|---|
| [闸门1] 用法 | `--url` / `--duration` / `--budget` 合法性 | exit 2 |
| [闸门2] 素材入口 | 本档只收本网关素材（先 `upload`；本包提前拦，服务端也会拦） | exit 3 |
| [闸门3] 可达性 | 探素材 HTTP HEAD/GET（探不到就拒提交） | exit 3 |
| [闸门4] 时长 | 本地 ffprobe；拿不到就报错，**绝不静默按 5 秒** | exit 3 |
| [闸门5] 上限 | 单条时长上限 600s | exit 3 |
| [闸门6] 规格 | 输入 **<1920×1080**；上游当前公测免费 | exit 3 |
| [闸门7] 预算 | `--budget`（**单位：点**） | exit 5 |
| [闸门8] 确认 | 不加 `--yes` 只报价，不提交 | exit 4 |
| → 真提交 | POST /api/v1/video/viapi/portrait（**这一步之后才会花钱**） | — |

---

## 文件结构

```
sanjianke-vr-portrait/
├── SKILL.md                      主文档（本档契约、闸门、合规边界、全部子命令）
├── README.md                     本文件
├── LICENSE.md                    MIT
├── references/
│   ├── api-contract.md           本档完整契约（请求/查询/单价/上限/白名单/闸门）
│   ├── cost-and-limits.md        计费口径、上限、输入规格、成本与毛利
│   └── troubleshooting.md        报错对照、排错顺序、真机实测记录
└── scripts/
    ├── run.py                    命令行（零依赖，只做本档）
    └── a7w.py                    算力网关零依赖客户端（上传/请求/落盘）
```

---

## 已知边界（如实说明）

- **素材入口判据以线上为准**：本档只收本网关素材（先 `upload`）。`doctor` **零成本实测**该前缀是否已放行并如实报告（400 = 未放行，502 = 已放行，两者都不扣费）。
- **在线权威源不稳定**：`GET /api/v1/video/viapi/tools` 早先免鉴权可读，后来变为 401/404。本包自动退回内置档位表（取自 `api.a7w.cn` 在架能力）并**如实打印「在线源当前不可达」**。价格与规格以线上为准。
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
