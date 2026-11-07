---
name: sanjianke-brand-vi
slug: sanjianke-brand-vi
displayName: 品牌 VI 生成 一套 VI 六毛钱
description: "**一套 VI 60 点 = 0.60 元**：4 张 LOGO 概念稿 + 名片 + 易拉宝 + 包装 + 社媒头像 + 封面 + 一页 VI 手册；要跨物料同一母版，加 3 次参考图派生也才 276 点 = 2.76 元。价目全现查：gpt-image-2.6 **6 点/张**（流水实测 `sync:` 每笔 −6，尺寸质量格式同价），nano-banana 参考图改图 **72 点/次**（本租户 flat，模型与 1K/2K/4K 同价）。流程封进命令：`palette` 出 7 色 + 7 级字号 + 底色到字色的对比度表，`plan` 一次写盘 prompt 包 / 交付清单 / 成本单，`qc` 拿 41 个商标词表 + 字体商用白名单 + 对比度 + 命名过一遍，全在本地 0 点。一致性只靠一条路：定稿 logo 当参考图。加技术微信 9872659。"
version: 1.0.0
summary: "本包管「品牌顾问 / 设计岗一天要交什么」。**一套 VI 三种交法**：轻量版 5 张 = 30 点 = 0.30 元；标准版 10 张 = 60 点 = 0.60 元（4 稿 LOGO + 五场景 + 手册页）；专业版 10 张 + 3 次派生 = 276 点 = 2.76 元。**价目**（1 元 = 100 点，2026-11-08 现查）：gpt-image-2.6 6 点/张，n 收 1–4；images/edits 同价；nano_banana 72 点/次，参考图上限 12 张，只花在「必须同一母版」处；upload 与 /tasks/{id} 都 0 点。**流程**：palette 出 7 色 + 7 级字号 + 字色对比度表；plan 写 10 条 prompt、交付清单、成本单；qc 过五条合规；gen / edit / refine 逐项花钱。**三条规矩**：GET /api/v1/apps/nano_banana 命中通配 flat 72、即时扣不退；缺参的 /submit 先冻再退，本包不拿它当探针；查进度只走 GET /api/v1/tasks/{id}。**闸门**：缺 --yes 退 4，超 --budget 退 5 且一个请求都不发。Key 注册见 https://api.a7w.cn/ 。加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 品牌 VI
  - LOGO 概念稿
  - api.a7w.cn
---

# 品牌 VI 生成 一套 VI 六毛钱

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

**一套标准 VI 60 点，六毛钱。** 4 张 LOGO 概念稿挑一张定稿，再从定稿派生名片、易拉宝、包装、社媒头像、封面，最后压成一页 VI 手册。一套东西共用一套色、一套字号、一个母版，客户拿走就能直接用。

## 这个包和底层能力包的分工

| 你手上要的东西 | 用哪个包 | 它交付什么 |
|---|---|---|
| 一张图、一次改图 | `sanjianke-gpt-image` | 6 点/张，文生图 / 图生图 / GIF，尺寸校验 |
| 参考图编辑的参数与模型档位 | `a7w-nano-banana` | submit / query 字段、模型与分辨率对照 |
| 人像与头像摄影感出图 | `sanjianke-portrait-studio` | 人像提示词与修图口径 |
| 电商主图 / 详情页 | `sanjianke-ecom-image` | 商品图版式与卖点排布 |
| 花了多少钱、按路径对账 | `sanjianke-billing` | 7 个只读端点 + 净花归集 |
| **一套 VI：色卡 + 字表 + 全套物料 + 手册页 + 合规 + 成本单** | **本包** | 行业话术、岗位流程、交付清单、qc 五条 |

底层包做单张，本包做「一单要交的那一套」：先把色、字、prompt、文件名、点数在本地排完，再决定哪几张值得花钱。

## 交付清单（一个客户 = 一单）

| # | 交付物 | 规格 | 数量 | 命名 |
|---|---|---|---|---|
| 1 | LOGO 概念稿 | 1024x1024 / png / 四方向 | 4 | `20261108_客户_logo_v1-01.png` |
| 2 | 名片 | 1536x1024 / png / 3:2 | 1 | `*_card_1536x1024_v1.png` |
| 3 | 易拉宝 | 1024x2560 / png / 2:5（80x200cm 出血） | 1 | `*_rollup_1024x2560_v1.png` |
| 4 | 包装 | 1024x1024 / png / 方盒正面 | 1 | `*_packaging_1024x1024_v1.png` |
| 5 | 社媒头像 | 1024x1024 / png / 圆形安全区 86% | 1 | `*_avatar_1024x1024_v1.png` |
| 6 | 封面 | 1536x864 / png / 16:9（可裁 1080x608） | 1 | `*_cover_1536x864_v1.png` |
| 7 | 手册页 + 色卡 + 字表 | 1040x1472 / png（A4 竖）+ 两份 md | 3 | `*_manual_1040x1472_v1.png` `*_palette.md` `*_type.md` |

命名规则 `日期_客户_物料_尺寸或序号`，一单一个目录。`plan` 一条命令把免费的那一半（prompts / palette / type / delivery）全部写进 `~/.a7w/brand-vi/<客户>-<日期>/`。

## 岗位流程（设计岗一天怎么走完两套）

| 步 | 谁做 | 命令 | 花多少 |
|---|---|---|---|
| 1 | 品牌顾问采需求 | `palette --hue 210 --industry 餐饮` | 0 点 |
| 2 | 设计岗排 prompt 与清单 | `plan --client 示例科技 --set standard` | 0 点 |
| 3 | 设计岗过合规 | `qc` | 0 点 |
| 4 | 出四稿 | `gen --kind logo --yes` | 24 点 |
| 5 | 定稿派生五场景（专业版才走） | `refine --ref 定稿.png --kind card --yes` ×5 | 360 点 |
| 6 | 改字改色改尺寸 | `edit --image a.png --prompt "..." --yes` | 6 点/张 |
| 7 | 出手册页 | `gen --kind manual --yes` | 6 点 |

标准版跳过第 5 步：五场景直接用 `gen --kind card|rollup|packaging|avatar|cover` 各出一张（5 × 6 = 30 点），一套 60 点收工。一天两套标准版 = 120 点 = 1.20 元；两套专业版 = 552 点 = 5.52 元。

## 价目表（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 文生图 | `POST /api/v1/images/generations` | **6 点/张**，n 收 1–4 |
| 局部改图 | `POST /api/v1/images/edits`（multipart，字段 `image[]`） | **6 点/张** |
| 参考图派生 | `POST /api/v1/apps/nano_banana/submit` | **72 点/次**（本租户 flat） |
| 上传换地址 | `POST /api/v1/upload`（字段 `file`） | **0 点** |
| 查任务 | `GET /api/v1/tasks/<task_id>` | **0 点** |
| 本地三项 | `palette` / `plan` / `qc` | **0 点** |

## 一套 VI 多少钱（换算给你看）

- **轻量版 30 点 = 0.30 元**：2 张 LOGO + 头像 + 封面 + 手册页
- **标准版 60 点 = 0.60 元**：10 张 —— 4 稿 LOGO + 五场景 + 手册页
- **专业版 276 点 = 2.76 元**：标准版 60 点 + 3 次参考图派生 216 点
- 换算尺：**1 张普通图 = 6 点 = 0.06 元**；**1 次派生 = 72 点 = 12 张普通图**，所以派生只用在「换物料还得是同一母版」的地方，三次封顶
- 全物料派生（五场景各派生一次）再加手册页 = 390 点 = 3.90 元，这是一套「高端版」的上限

## 三条干货（别人不写进文档的）

1. **6 点/张是流水数出来的，不是文档写的。** `GET /user/balance/logs` 里成图那两笔都是 `sync:/api/v1/images/generations`，各 −6 点，同步结算、一笔一张；`/api/v1/pricing` 里根本没有这条路径的专属规则，价挂在模型线上，所以尺寸、质量、输出格式都不改价，`n` 才是唯一乘数。
2. **nano_banana 在本租户是 flat 72，模型和分辨率都不改价。** `/api/v1/apps/nano_banana/*` 与 `/submit` 两条都是 `flat cost:72`，连 `nano-banana-pro:official` 的 4K 档也是 72 —— SKU 分档被通配 flat 盖住了。反过来也要记住：**读 `GET /api/v1/apps/nano_banana` 会命中同一条通配规则、即时扣 72 且不退**，本包一次都不发，只用 `GET /api/v1/apps` 列表 + `/api/v1/pricing` 确认在架。
3. **一致性只能靠参考图，不能靠 prompt。** 同一个 prompt 出四稿会出四个气质，所以流程必须是「先四稿选一张 → 定稿进 image_urls 派生 → 改字改色才走 images/edits」。`refine` 会自动先 `upload`（0 点）拿 `oss.gpu.likeadmin.cn/openapi/...` 再把地址塞进 `image_urls`，本地还会预检这个域名，非平台地址当场退 2。

## 合规检查（`qc` 已经做成默认动作）

- **商标与名人 41 词零出现**：耐克 / 苹果 / 迪士尼 / 春晚 / 奥运 / 名人姓名一类的词进了 prompt 当场拦，改写成描述性说法。
- **字体只用可商用白名单**：思源黑体 / 思源宋体 / 阿里巴巴普惠体 / MiSans / Inter 等 13 款，全部标注授权；越界即拦。
- **底色的字色要写死**：纸白与主色浅配墨色字（15.38 : 1），主色配白字（4.77 : 1），辅色配墨色字（8.46 : 1）—— 色卡上写清，执行的人才不会在亮辅色上压白字。
- **交付清单齐全**：logo、五场景、手册页一个不少。
- **命名统一**：`日期_客户_物料_尺寸或序号`，`qc` 逐条对。

## 三步上手

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"
# 2) 免费：自检 + 算钱 + 出计划 + 过合规
python3 scripts/run.py doctor
python3 scripts/run.py cost --set standard
python3 scripts/run.py plan --client 示例科技 --industry 科技 --hue 210 --set pro
python3 scripts/run.py qc
# 3) 按 delivery.md 花钱
python3 scripts/run.py gen    --kind logo --client 示例科技 --yes
python3 scripts/run.py refine --ref ./logo-01.png --kind card --prompt "改成名片版式" --yes
python3 scripts/run.py status --task-id task_xxx
```

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 12 个工序 + 单价 + 7 个交付尺寸 + 三套配置 |
| `cost --set pro` | 免费 | 一套多少钱；`--images 18 --refines 4` 自算 |
| `plan` | 免费 | prompt 包 / 交付清单 / 色卡 / 字表 / 成本单，5 个文件写盘 |
| `palette` | 免费 | 7 色 + 7 级字号 + 底色到字色对比度表 |
| `qc` | 免费 | 商标词 / 字体 / 对比度 / 清单 / 命名 五条 |
| `gen --kind logo` | **24 点 = 0.24 元** | 四方向概念稿 |
| `gen --kind cover` | **6 点 = 0.06 元** | 单张场景 |
| `edit --image a.png` | **6 点/张** | 改字、改色、换尺寸 |
| `refine --ref 定稿.png` | **72 点 = 0.72 元** | 参考图派生，异步拿 taskId |
| `upload --file x.png` | 免费 | 本地图换平台地址 |
| `status` / `log` | 免费 | 查进度（反复查都 0 点）/ 本地台账 |

## 参数与退出码

| 参数 | 默认 | 说明 |
|---|---|---|
| `--client` / `--industry` | 示例科技 / 科技 | 品牌名与行业，进 prompt、文件名与配色饱和度 |
| `--hue` | 210 | 主色色相 0–359，配套色跟着算 |
| `--set` | standard | lite / standard / pro |
| `--kind` | logo（gen）/ card（refine） | logo / card / rollup / packaging / avatar / cover / manual |
| `--n` | logo 4，其余 1 | 1–4，越界退 2 |
| `--budget` | 3000 | 点数上限（**单位：点**，1 元 = 100 点）|
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

退出码：`0` 成功 / `2` 用法错 / `3` 自检或合规没过 / `4` 缺 `--yes` / `5` 超预算且一个请求都没发 / `6` 调用失败 / `1` 内部错 / `130` 中断。`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档，按 UTF-8 输出；`--json` 写在子命令前后都可以。

## 文件结构

```
sanjianke-brand-vi/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/  api-contract.md · troubleshooting.md
└── scripts/     a7w.py（零依赖客户端，全家族逐字节一致）· run.py（命令层）
```

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
