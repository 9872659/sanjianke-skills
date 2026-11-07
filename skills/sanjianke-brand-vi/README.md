# 品牌 VI 生成 一套 VI 六毛钱

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。

**一套标准 VI 60 点，六毛钱。** 4 张 LOGO 概念稿挑一张定稿，再从定稿派生名片、易拉宝、包装、社媒头像、封面，最后压成一页 VI 手册 —— 一套东西共用一套色、一套字号、一个母版。

```
轻量版   5 张              30 点   = 0.30 元
标准版  10 张              60 点   = 0.60 元
专业版  10 张 + 3 次派生   276 点  = 2.76 元
```

## 为什么有这一层

出图的接口文档够清楚，但一个品牌设计单真正会卡住的三件事不在文档里：

1. **一张图几毛钱、一套图多少钱，没人先算。** 本包 `cost` 先给三套交付的价，`--budget` 是第一道闸门、`--yes` 是第二道，超预算时一个请求都不发。
2. **同一个 prompt 出四稿会出四个气质。** 一致性只能靠参考图：定稿 logo 先进 `image_urls`，再由 nano-banana 派生其余物料；改字改色走 `images/edits`，不动构图。
3. **色卡和字表是交付物的一半。** 客户真正拿走的是「主色 #2D75BE、正文 15.38:1、辅色上配墨色字」这些话，本包 `palette` 与 `plan` 直接把这些写成 `palette.md` / `type.md`。

## 价目（2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 文生图 | `POST /api/v1/images/generations` | **6 点/张**（n 收 1–4，尺寸/质量/格式同价） |
| 局部改图 | `POST /api/v1/images/edits`（multipart，字段 `image[]`） | **6 点/张** |
| 参考图派生 | `POST /api/v1/apps/nano_banana/submit` | **72 点/次**（本租户 flat） |
| 上传换地址 | `POST /api/v1/upload`（字段 `file`） | **0 点** |
| 查任务 | `GET /api/v1/tasks/<task_id>` | **0 点** |
| 本地三项 | `palette` / `plan` / `qc` | **0 点** |

6 点/张 不是估的：`GET /user/balance/logs` 里成图那两笔都是 `sync:/api/v1/images/generations`，各 −6 点 —— 同步结算、一笔一张。

## 交付清单（一个客户 = 一单）

| # | 交付物 | 规格 | 数量 |
|---|---|---|---|
| 1 | LOGO 概念稿 | 1024x1024 png，四方向 | 4 |
| 2 | 名片 | 1536x1024 png，3:2 | 1 |
| 3 | 易拉宝 | 1024x2560 png，2:5（80x200cm 出血） | 1 |
| 4 | 包装 | 1024x1024 png，方盒正面 | 1 |
| 5 | 社媒头像 | 1024x1024 png，圆形安全区 86% | 1 |
| 6 | 封面 | 1536x864 png，16:9 | 1 |
| 7 | 手册页 + 色卡 + 字表 | 1040x1472 png（A4 竖）+ 两份 md | 3 |

命名 `日期_客户_物料_尺寸或序号`，一单一个目录：`~/.a7w/brand-vi/<客户>-<日期>/`。

## 三步上手

### 第 0 步：拿 Key

到 [api.a7w.cn](https://api.a7w.cn/) 注册，创建 API Key（形如 `sk-...`）。

### 第 1 步：零依赖

只要 Python 3.7+，不需要 `pip install` 任何东西。

```bash
export A7W_API_KEY=sk-你的key        # Linux / macOS
$env:A7W_API_KEY="sk-你的key"        # Windows PowerShell
python3 scripts/a7w.py login --key sk-你的key   # 或者存起来反复用
```

### 第 2 步：免费三件事（自检 / 算钱 / 出计划）

```bash
python3 scripts/run.py doctor
```

```
√ Key + 余额接口可达                   HTTP 200 · 可用 999,997,393,470 点 · 冻结 0 点
√ 出图模型 gpt-image-2.6 在架          HTTP 200 · 参考图上限 6 张
√ 参考图应用 nano_banana 在架          HTTP 200 · submit 参考图上限 12 张
√ 价目对齐（派生 72 点 / 上传 0 点）    HTTP 200 · nano_banana flat 72 · upload 0
√ 文生图端点可用（422 即正确）          HTTP 422 prompt: String should have at least 1 characte
√ 改图端点可用（500 image is required 即正确）HTTP 500 image is required
√ 上传接口可用（提示补 file 字段即正确）HTTP 200 请使用文件字段提交一个文件
√ 任务查询 GET /tasks/{id} 可用        HTTP 200 任务不存在
√ 花费复核：流水未被本轮改动            HTTP 200 · 共 7,897 条 · 最新一笔 11-08 01:46:12
```

```bash
python3 scripts/run.py cost --set standard
python3 scripts/run.py plan --client 示例科技 --industry 科技 --hue 210 --set pro
python3 scripts/run.py qc
```

`plan` 会在 `~/.a7w/brand-vi/示例科技-20261108/` 写出 5 个文件：`plan.json`、`prompts.md`（10 条 prompt）、`delivery.md`（交付清单 + 点数）、`palette.md`（7 色 + 底色到字色）、`type.md`（7 级字号 + 字体授权）。

### 第 3 步：按 `delivery.md` 花钱

```bash
# 四稿概念稿（24 点）
python3 scripts/run.py gen --kind logo --client 示例科技 --yes

# 定稿派生名片（72 点，异步拿 taskId；会自动 upload 拿平台地址）
python3 scripts/run.py refine --ref ./logo-01.png --kind card \
    --prompt "把这张标志套进名片版式，左下角留姓名与电话两行" --yes

# 改字改色（6 点/张）
python3 scripts/run.py edit --image card.png --prompt "整体压低 10% 亮度，保留版式" --yes

# 查进度（0 点，反复查都是 0 点）
python3 scripts/run.py status --task-id task_xxx
```

**不加 `--yes` 会退 `4`**，并告诉你这次要花多少点。想先看不花钱的请求：

```bash
python3 scripts/run.py gen --kind logo --dry-run
```

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 12 个工序 + 单价 + 7 个交付尺寸 + 三套配置 |
| `cost` | 免费 | 一套多少钱；`--images 18 --refines 4` 自算 |
| `doctor` | 免费 | 8 条自检（只读 GET + 三条参数校验探针） |
| `palette` | 免费 | 7 色 + 7 级字号 + 底色到字色对比度表 |
| `plan` | 免费 | prompt 包 / 交付清单 / 色卡 / 字表 / 成本单，5 个文件写盘 |
| `qc` | 免费 | 商标词 / 字体 / 对比度 / 清单 / 命名 五条 |
| `gen` | **6 点/张** | 文生图，n 收 1–4 |
| `edit` | **6 点/张** | 局部改图（multipart） |
| `refine` | **72 点/次** | 参考图派生，异步 |
| `upload` | 免费 | 本地图换平台地址 |
| `status` | 免费 | 查任务 |
| `log` | 免费 | 本地台账 |

## `qc` 的五条

1. **商标与名人 41 词零出现**（耐克 / 苹果 / 迪士尼 / 春晚 / 奥运 / 名人姓名一类）
2. **字体只用可商用白名单**（思源黑体 / 思源宋体 / 阿里巴巴普惠体 / MiSans / Inter 等 13 款）
3. **底色到字色的对比度**：正文 4.5:1、大字 3.0:1，色卡上写死每个底色配哪个字色
4. **交付清单齐全**：logo、五场景、手册页
5. **命名统一**：`日期_客户_物料_尺寸或序号`

## 实测记录（2026-11-08）

```
GET /api/v1/models           316 个模型，图片类 50 个
gpt-image-2.6                type=image，参考图上限 6 张
GET /api/v1/apps            22 个应用，nano_banana id=22，submit 参考图上限 12 张
GET /api/v1/pricing         /api/v1/apps/nano_banana/submit  flat 72
                            /api/v1/upload                   flat 0
POST /images/generations {"model":"gpt-image-2.6","prompt":""}  → 422
POST /images/edits      （只有 model、无图）                     → 500 image is required
POST /api/v1/upload     （无 file）                              → 200 请使用 file 字段提交一个文件
GET  /api/v1/tasks/probe-no-such-task                            → 200 任务不存在
余额 999,997,393,470.2579 点（前后完全一致）· 流水 7,897 条未变
```

## 三条规矩

1. **`GET /api/v1/apps/nano_banana` 是收费的。** 它命中 `/apps/nano_banana/*` 的通配 flat 72，即时扣、不退。本包一次都不发，只用 `GET /api/v1/apps` 列表 + `/api/v1/pricing` 确认在架。
2. **缺参的 `/submit` 不是免费探针。** 它走 `reserve_sync`：先冻 72 再参数校验、再全额退，净额 0，但钱包被短暂动过。
3. **查进度只走 `GET /api/v1/tasks/{id}`**（实测 0 点，假 id 返回「任务不存在」）。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--client` / `--industry` | 示例科技 / 科技 | 品牌名与行业，进 prompt、文件名与配色饱和度 |
| `--hue` | 210 | 主色色相 0–359 |
| `--set` | standard | lite / standard / pro |
| `--kind` | logo（gen）/ card（refine） | logo / card / rollup / packaging / avatar / cover / manual |
| `--n` | logo 4，其余 1 | 1–4，越界退 2 |
| `--size` | 按物料 | 宽x高，四条硬约束本地先校验 |
| `--budget` | 3000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

### 尺寸的四条硬约束（不合规 → 本地退 2，不发请求）

- 宽高都是 **16 的倍数**
- 长边 / 短边 **不超过 3:1**
- 单边 **不超过 3840**
- 总像素 **655,360 – 8,294,400**

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺参数、尺寸不合规、`n` 越界、选项缩写） |
| `3` | 自检或合规没过 |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

## `--json` 契约

```json
{"ok": true, "mode": "gen", "kind": "logo", "requested": 4, "returned": 4,
 "files": ["./20261108-logo-01.png"], "billedPoints": 24, "size": "1024x1024"}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档，按 UTF-8 输出。

## 文件结构

```
sanjianke-brand-vi/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致）
    └── run.py                本包命令层
```

## 免责

- 生成内容的合规责任在使用者：标志、包装、宣传图上出现的元素与文字，由使用者确认没有第三方权利。
- `qc` 的词表与字体白名单是**尽力而为**的检查，最后一眼还得人过。
- 真实扣费以响应里**实际返回的张数**与任务冻结的快照为准，`cost` 给的是预估。

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
