---
name: sanjianke-drama-studio-kit
slug: sanjianke-drama-studio-kit
displayName: 三剪客 · AI 短剧创作台
description: "短剧创作台的选型评估与私有化搭建指南，含真实算力接入：出图走 `/api/v1/apps/nano_banana/submit`、出片走 `/api/v1/apps/full_video/submit`、配音走 `/api/v1/apps/voice_tts/tts`，并按 `/api/v1/pricing` 的真实单价做成本估算。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.5
summary: "面向要自建 AI 短剧创作台的技术负责人：先用使用方身份与五维权重把「该不该自建、选哪个底座」定下来，再处理许可这类一票否决项，然后按 B/S 架构装环境、建库、管密钥、接模型、配对象存储并发布，最后给出上线检查、四笔成本账与故障排查顺序。四类创作算力（出图 / 出片 / 配音 / 单价）已接到 api.a7w.cn：`scripts/run.py pilot` 用一个镜头跑通全链路并打印真实扣点，`scripts/cost_estimate.py --a7w-live` 按平台实收价算单集成本。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI短剧
  - 影视创作
  - 工具选型
---

# 三剪客 · AI 短剧创作台

自建一套 AI 短剧创作台，钱通常不是烧在写代码上，而是烧在**一开始就挑错了底座**：
拿强著佐权许可的项目当闭源产品对外卖、把按秒计费的视频模型当成按次计费来排期、
GPU 预算全砸下去，最后发现卡住流程的是 CPU 上的 FFmpeg 合成。

所以这份 Skill 的着力点在前半段——**把判断做在动手之前**。

它只负责创作台本身的三件事：**要不要自己搭、搭在哪个底座上、搭好之后怎么让它一直跑下去**。
剧本怎么写、画面怎么调，属于创作环节，不在范围内。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **仅在你显式调用 `scripts/run.py` 或 `cost_estimate.py --a7w-live` 时需要** | 这些命令会请求 `api.a7w.cn` 的出图 / 出片 / 配音 / 取价接口，用真实算力跑通最小闭环。只读本文档、只跑默认的 `cost_estimate.py` 时**不联网** |
| 读取文件 | 仅读取用户主动指定的路径 | 读取部署配置、日志片段、目录清单用于诊断 |
| 写入文件 | 仅在用户指定输出路径时 | 测算脚本只把结果打印到终端；`--out` / `--price-out` / `pilot` 才落盘 |
| 凭证 | 只在调用算力时读取你自己的 Key | Key 从 `--key`、环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取；**不内嵌、不写入任何交付文件**。文档中的其他变量名均为占位符 |
| 子进程 / 后台常驻 | 不申请 | 脚本执行完即退出，不驻留 |

**本 Skill 不内嵌任何密钥。** 明文密钥只存在于你自己的环境变量或 `~/.a7w/config.json` 里；
上面这些联网命令是你**主动**发起的真实调用，会产生平台点数消费（1 元 = 100 点，
失败全额退回），每次调用的实际扣费都在 `usage.points_cost` 里当场打印出来。

> 想先用最低成本验一遍：`python scripts/run.py pricing` 只读取价与规则表，免费；
> `python scripts/run.py image --prompt "测试" --dry-run` 只打印请求体，不花钱。

### 第三方与合规提示

候选底座如果用的是 **AGPL-3.0** 这类带网络服务条款的强著佐权许可，
把它挂在公网上给用户用，通常就要向使用者提供对应源码。这是许可义务，
不是技术难题，但必须在上线前由法务或合规负责人确认。展开说明见
`references/ops-and-compliance.md`。

## 触发场景

- 「短剧这块，我们自己搭一套，还是直接买现成的？」
- 「这个开源短剧平台能不能商用？许可有没有坑？」
- 「机器已经买了，MySQL、Redis、FFmpeg 这些到底怎么装？」
- 「画面出来了，但配音和口型对不上，合出来的时长总是错位。」
- 「对象存储账单超了，出片成本到底花在哪一块？」
- 「模型用哪家？文本、图片、视频、配音能不能混着用？」

**不适合用在**：只想剪一条已经拍好的片子（那是剪辑工具的事）、
只想写剧本不打算落地系统、或者指望这份 Skill 直接产出一部成片。

## 快速开始

先回答三个问题，路线基本就唯一了：

1. **给谁用**——只有自己团队用，还是要开账号给外部客户？
2. **许可**——底座带的是不是 AGPL 这一类强著佐权许可？要拿去商用，法务这关先过。
3. **量级**——每月出多少集？这一条决定算力走按量 API 还是自建推理。

```bash
# 第 1 步：先算钱。默认离线改参数即可，不联网、不写文件
python scripts/cost_estimate.py --episodes 30 --minutes 2 \
  --gen-image 40 --gen-video 30 --gen-tts 30

# 第 1 步（推荐）：用 api.a7w.cn 的**真实单价**算，而不是占位示例值
python scripts/run.py pricing --probe image --out a7w-prices.json
python scripts/cost_estimate.py --episodes 30 --minutes 2 \
  --price-file a7w-prices.json --a7w-video-resolution 1080P \
  --clip-seconds 6 --tts-chars 24

# 第 2 步：按打分表定底座（五项加权，低于 3.0 不建议自建）
#   见 references/selection-scorecard.md

# 第 3 步：照部署清单搭环境（依赖版本、库表字符集、发布方式）
#   见 references/deploy-and-configure.md

# 第 3.5 步：先用**一个镜头**把真实算力链路跑通（最低成本验证法）
python scripts/run.py pilot --topic "雨夜霓虹街头，女主撑伞回头看向镜头" \
  --line "你终于回来了。" --out-dir pilot

# 第 4 步：上线前过一遍检查项，并确认许可义务
#   见 references/ops-and-compliance.md
```

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 判断该不该自建、选哪个底座、许可有没有坑 | `references/selection-scorecard.md` |
| 装环境、配数据库与 Redis、接模型与对象存储、构建发布 | `references/deploy-and-configure.md` |
| 日常运维、账单控制、故障定位、许可义务与上线检查 | `references/ops-and-compliance.md` |
| 估算存储占用、回源带宽与单集成本 | `scripts/cost_estimate.py` |
| 真的出图 / 出片 / 配音，或现拉真实单价 | `scripts/run.py` |
| 直接调平台接口（自己写代码时） | `scripts/a7w.py`（零依赖客户端，七个子命令） |

---

## 怎么用（命令行）

配一把 Key 就能跑（三种方式任选，**包内不内嵌任何密钥**）：

```bash
python scripts/a7w.py login --key sk-xxxx      # 验证并保存到 ~/.a7w/config.json
export A7W_API_KEY=sk-xxxx                     # Windows: set A7W_API_KEY=sk-xxxx
# 或临时指定：python scripts/run.py image --prompt "..." --key sk-xxxx
```

拿 Key：到 [算力集市](https://api.a7w.cn/) 注册领取，新用户有赠送点数；**1 元 = 100 点**，失败全额退回。

### 1. 先看清参数再动手（不要凭记忆写参数名）

```bash
python scripts/a7w.py schema nano_banana     # 出图有哪些参数、哪个必填
python scripts/a7w.py schema full_video      # 出片的 content 数组长什么样
python scripts/a7w.py schema voice_tts       # 配音的音色参数叫什么
python scripts/run.py models --filter deepseek
```

### 2. 出一张分镜图

```bash
python scripts/run.py image \
  --prompt "雨夜霓虹街头，女主撑伞回头看向镜头，电影感，浅景深" \
  --resolution 1K --aspect-ratio 9:16 --out shot1.png
```

### 3. 拿这张图当首帧出片

```bash
python scripts/run.py video \
  --first-frame "https://你的图床/shot1.png" \
  --prompt "镜头缓慢推近，雨丝落在伞面" \
  --resolution 480P --duration 4 --out shot1.mp4
```

视频是**按分辨率每秒计费**的，先用 480P / 4 秒试通再放大。

### 4. 出一句台词配音

```bash
python scripts/run.py voices --page-size 5           # 先拿音色 ID（model_id）
python scripts/run.py voice --text "你终于回来了。" \
  --reference-id 28d41fb94dc14b48b9af875b82ca5f97 --out line1.mp3
```

### 5. 一个镜头跑通全链路（先花小钱，再批量投）

```bash
python scripts/run.py pilot --topic "雨夜霓虹街头，女主撑伞回头看向镜头" \
  --line "你终于回来了。" --out-dir pilot
# 输出 pilot/shot1.png + pilot/shot1.mp4 + pilot/line1.mp3，
# 并把每一步的真实扣点单独打出来
```

### 6. 按真实单价算成本

```bash
python scripts/run.py pricing --probe image --out a7w-prices.json   # 现拉单价，含实测出图价
python scripts/cost_estimate.py --episodes 30 --minutes 2 \
  --price-file a7w-prices.json --a7w-video-resolution 1080P \
  --clip-seconds 6 --tts-chars 24 --price-out 本次采用的单价.json
# 也可以省掉快照这一步，直接算：
python scripts/cost_estimate.py --episodes 30 --minutes 2 --a7w-live
```

`cost_estimate.py` **默认仍然完全离线**（纯计算、不联网、不写文件），只在给了
`--a7w-live` 或 `--price-file` 时才按平台真实单价算。

## 接入 api.a7w.cn 的真实端点

创作台要接的四类算力，逐条对应到平台接口（都能用 `scripts/run.py` 直接跑）：

| 环节 | 接口 | 关键参数 | 备注 |
|---|---|---|---|
| 出图 | `POST /api/v1/apps/nano_banana/submit` | `prompt`、`action=generate\|edit`、`resolution`(1K/2K/4K)、`aspect_ratio`、`image_urls`(edit 必填) | 异步，返回 `task_id`；查询用 `POST /api/v1/apps/nano_banana/query` |
| 出片 | `POST /api/v1/apps/full_video/submit` | `content`（数组，**必含一条 `{"type":"text"}`**）、`ratio`、`resolution`(480P/768P/1080P/2K/4K)、`duration`(4~15 整数) | 异步；查询用 `POST /api/v1/apps/full_video/query` |
| 配音 | `POST /api/v1/apps/voice_tts/tts` | `text`、**`reference_id`**（音色 ID，不是 `voice_id`）、`format` | 同步；长文用 `POST /api/v1/apps/voice_tts/tts_async` |
| 音色 | `POST /api/v1/apps/voice_tts/clone_voice` / `POST /api/v1/apps/voice_tts/list_voices` | `title`+`audio_url` / 分页参数 | 克隆是同步，返回 `model_id` 即 `reference_id` |
| 数字人 | `POST /api/v1/apps/image_human/submit` | `file_url`(人物图)、`ref_file_url`(驱动音频)、`mode`(fast/standard/2k/4k) | 按驱动音频的时长计费；四档单价见下方实测表，参数可用 `python scripts/a7w.py schema image_human` 现查 |
| 音乐 | `POST /api/v1/apps/music_generation/create` | 见 schema | 生成 65 点、歌词 12 点 |
| 取价 | `GET /api/v1/pricing`、`GET /api/v1/apps/<app>` | — | 前者是规则表（只覆盖少量接口），后者给逐接口的 `tenant_*` 字段价 |

裸调用（不写代码，直接用平台接口）：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/apps/full_video/submit" \
  -H "Authorization: Bearer $A7W_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"full-video","ratio":"9:16","resolution":"480P","duration":4,
       "content":[{"role":"first_frame","type":"image_url",
                   "image_url":{"url":"<首帧图公网 URL>"}},
                  {"type":"text","text":"缓慢推近，人物转头看向窗外"}]}'
```

三条必须记住的口径：

1. **`code == 1` 才算业务成功**（不是 0）。HTTP 200 不等于调用成功。
2. **实际扣费看 `usage.points_cost`**；同步接口有时是 `usage.actual_points`。失败全额退回。
3. **异步任务先提交再轮询**：`POST /api/v1/apps/<app>/<api>` 拿 `task_id`，再
   `GET /api/v1/tasks/{task_id}` 查 `status`（`completed` / `failed` / `cancelled`）。
   轮询超时**不等于失败**，先查任务，别重新提交——重提就是第二次扣费。

### 实测到的真实单价（2026-09 快照，调价请重跑 `pricing`）

| 项目 | 单价 | 来源 |
|---|---|---|
| `nano_banana/submit` 1K 文生图 | **24 点 / 张**（≈0.24 元） | 实测 `usage.points_cost` |
| `full_video/submit` 480P / 768P / 1080P·2K·4K | **10 / 20 / 40 点/秒** | `GET /api/v1/pricing`，实测 480P 4 秒 = 40 点 |
| `voice_tts/tts` | **50 点/千字**（= 0.05 点/字，无最低消费） | 实测 6 组：2/7/7/21/32/74/137 字分别扣 0.10/0.35/0.35/1.05/1.60/3.70/6.85 点，**全部 = 字数 × 0.05**，与租户字段 `50` 一致 |
| `voice_tts/stt` | **40 点 / 次** | 真打 3 次实测，`usage.points_cost` 均为 40；租户字段 `tenant_fixed_points` 写的是 30 |
| `voice_tts/clone_voice` | 200 点 / 次 | 租户价字段 = 公示价 ×4（未必等于实际结算价） |
| `music_generation/create` / `lyrics` | 65 点 / 12 点 | 租户价字段（未必等于实际结算价） |
| `image_human/submit` `fast` / `standard` / `2k` / `4k` | **2 / 3 / 6 / 12 点/秒** | 四档各真打一次实测：2.64 秒音频分别扣 5.28 / 7.92 / 15.74 / 31.49 点 |

> 预算一律以返回里的 `data.usage.points_cost` 为准（**公示价和 `tenant_*` 字段价都不能直接当结算价**）——
> 实测两者能差数倍（如 `clone_voice` 公示 50 点、实收 200 点）。
> 但也要注意租户字段本身未必等于结算价：`image_human/submit` 的
> `tenant_points_per_1k_input` 是 2.0，实测 `standard` 档实际按 3 点/秒结算；
> `voice_tts/stt` 的字段写 30、实测 40。
> **拿不准就以实测扣点为准**（`usage.points_cost`）；本表价格来自实测，平台调价后需重新核对。

---

## 路线 A：先把决策做对，再碰服务器

有人第一句话就是「帮我装起来」的时候，**别顺着往下讲安装步骤**。先让他把下面这几件事回答完：

| 必须问清 | 为什么它决定方案 |
|---|---|
| 底座许可类型 | AGPL 类许可对外提供服务会触发源码披露义务，这一条能直接否掉方案 |
| 使用范围（内部 / 对外） | 决定要不要做多租户、配额、审计，工作量差一倍以上 |
| 每月目标集数 | 决定按量 API 还是自建推理，拐点一般出现在每月百集量级 |
| 团队现有技能栈 | Java + Vue 一条线、Python 一条线，选错了迭代速度直接腰斩 |
| 硬件预算 | 瓶颈常在 CPU 转码而不在 GPU 推理，机器配错钱就白花 |

打分口径、以及自建 / 采购 / SaaS 三条路线怎么取舍，见
`references/selection-scorecard.md`。**加权分掉到 3.0 以下，就把「不建议自建」这句话
直接说出来**，并指出是哪几项把它拉下来的。

---

## 路线 B：部署与配置

决定自建之后，按这个顺序推进，**每一步都要能验收再进下一步**：

1. **基线**：核对 CPU、内存、磁盘与转码能力，别只盯着 GPU
2. **依赖**：数据库、缓存、多媒体工具三件套装好，并逐个验证版本
3. **库表**：建库建表时把字符集定成 `utf8mb4`，中文标题和台词的坑都在这里
4. **密钥**：模型与存储凭证一律走环境变量或密文配置，**不进代码库**
5. **模型**：文本 / 图片 / 视频 / 配音四类分别指定供应商，别只配一家
6. **存储**：对象存储与 CDN 打通，确认回源域名和跨域设置
7. **构建**：前端构建产物交给 Nginx，后端以常驻服务方式托管
8. **联调**：走一遍最小闭环——建项目 → 拆镜头 → 出图 → 出片 → 整集合成

具体命令、配置文件骨架、字符集与跨域怎么写，见
`references/deploy-and-configure.md`。

**最低成本验证法**：先用一个镜头把全链路跑通，再谈批量投入。
不少团队跳过这一步直接批量生成，结果最后才发现配音时长的对齐策略有问题，
前面生成的费用全部作废。

---

## 路线 C：上线之后的运维、成本与合规

上线只是开始。有三件事要固定成例行动作：

- **巡检**：任务队列积压、失败率、磁盘余量、证书有效期
- **对账**：模型调用、对象存储、回源带宽、转码算力这四笔账分开记
- **备份与演练**：数据库定期备份，**并且真的恢复过一次**

对外提供服务之前，必须确认许可义务（AGPL 类需提供源码），
同时确认生成内容的标识与备案要求。故障定位顺序、账单异常特征、
上线检查项与许可义务说明，见 `references/ops-and-compliance.md`。

---

## 能力边界

**覆盖**：

- 自建 AI 短剧创作台的五维选型打分与自建 / 采购决策
- B/S 全栈架构的依赖清单、环境准备、库表字符集与密钥管理规范
- 文本 / 图片 / 视频 / 配音四类模型供应商的接入与混配思路
- **四类创作算力的真实接入**：出图 `nano_banana`、出片 `full_video`、配音 `voice_tts`、
  以及按 `GET /api/v1/pricing`＋`tenant_*` 现拉真实单价；命令行可直接跑通一个镜头
- 对象存储 + CDN 的配置要点与成本构成拆解
- 上线检查项、日常巡检项、故障定位顺序
- AGPL 类许可的对外服务义务提示与生成内容合规提示

**不覆盖**：

- 不提供任何上游项目的源代码、补丁或封装
- 不替用户做商用合规的法律判断，只提示风险点
- 不替你做创作决策。`run.py pilot` 只为验证链路生成**一个示例镜头**（图/片/配音），
  不产出可用成片，也不写剧本或台词——分镜、台词、风格仍由你和创作环节决定
- 不代为申请或代管任何 API Key、账号、云资源（Key 由你自己在平台创建）
- 不含模型效果的主观评测排名（各家迭代快，结论极易过期）
- 不含 K8s 集群编排、多租户计费系统的完整实现

## 依赖条件

| 项目 | 要求 | 说明 |
|---|---|---|
| 运行环境 | Windows / Linux / macOS 任一 | 只读这份文档时无任何依赖 |
| Python | 3.8+ | `scripts/cost_estimate.py`（默认纯离线）与 `scripts/run.py`（联网调算力）都只用标准库，无需 pip 安装 |
| 平台账号 | 一把 `api.a7w.cn` 的 API Key | 只有 `run.py` 与 `cost_estimate.py --a7w-live` 需要；到 https://api.a7w.cn/ 注册领取，1 元 = 100 点 |
| 待部署主机 | 见 `references/deploy-and-configure.md` 的基线表 | JDK、构建工具、运行时、数据库、缓存、FFmpeg |
| 第三方服务 | 对象存储（可选 CDN） | 需使用者自行申请，本 Skill 不代管 |

## 已知限制

- 上游项目迭代较快，表结构、配置项与路由**都可能变动**；
  本文出现的字段名和路径都是骨架性质的示例，真正落地时以你手上那个版本的
  配置文件与建表语句为最终依据。
- 平台价格与限流策略变动频繁：`cost_estimate.py` **不给** `--a7w-live` / `--price-file`
  时用的是**默认示例单价**，结论只能当量级看；要采信请先现拉真实单价
  （`run.py pricing`）或直接 `--a7w-live`。对象存储与回源带宽两项单价始终是示例值。
- 本文写下的实测价（如 1K 出图 24 点/张、480P 视频 10 点/秒、
  数字人四档 2/3/6/12 点/秒）是**某次快照**，仅用于说明口径；
  以现场 `python scripts/run.py pricing` 与实际扣点为准。
  数字人那四档是在 **2.64 秒**的驱动音频上测的（按秒结算），
  换个时长请按点/秒重算，并以实际扣点核对。
- 成本测算为量级估算，未计入重试、失败重跑与人工返工带来的额外消耗，
  实际支出通常高于测算值。视频与数字人按秒计费，档位选错会让成本翻数倍。
- `run.py` 的异步任务轮询上限是 1800 秒；超时**不等于失败**，
  用 `--task-id` 接着查，别重新提交。
- 本 Skill 不判断某个具体项目是否适合你的团队，只提供判断框架。

## 自检清单

部署前：

- [ ] 已确认底座许可类型，并判断对外服务是否触发源码披露义务
- [ ] 已确认使用范围（内部自用 / 对外经营），并据此确定是否需要多租户
- [ ] 已明确每月目标集数，并据此选好按量 API 或自建推理
- [ ] 已完成五维打分，加权分与结论一致
- [ ] 数据库字符集为 `utf8mb4`，已用中文标题实测插入与查询
- [ ] 所有密钥走环境变量或密文配置，代码库中没有任何明文凭据
- [ ] 四类模型供应商分别配置完成，并各做过一次真实调用
- [ ] 已用 `python scripts/run.py pilot` 用一个镜头跑通「出图 → 出片 → 配音」，
      并核对了每步的 `usage.points_cost`
- [ ] 成本测算用的是现拉的真实单价（`--a7w-live` 或 `--price-file`），不是示例值
- [ ] 对象存储回源域名与跨域设置已验证
- [ ] 已用单个镜头跑通全链路，再放大到批量

上线后：

- [ ] 后台任务失败率与积压量在观测范围内
- [ ] 数据库备份已实际恢复验证过一次
- [ ] 四笔成本账分开记录，且能定位异常波动来源
- [ ] 平台点数流水与本地记录的 `task_id` 逐条对得上（防重复提交）
- [ ] 生成内容的标识与备案要求已确认

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/selection-scorecard.md` | 使用方分类、五维权重与判定线、许可一票否决项、三路线取舍、取证清单 |
| `references/deploy-and-configure.md` | 机器档位、依赖安装、库表与字符集、密钥存放、模型接入、对象存储、常驻与发布 |
| `references/ops-and-compliance.md` | 许可义务、上线检查表、巡检项、四笔账、故障定位顺序、备份演练 |
| `scripts/run.py` | **算力接入层**：`pricing` / `models` / `voices` / `image` / `video` / `voice` / `pilot`，全部真调 `api.a7w.cn` |
| `scripts/cost_estimate.py` | 成本测算：默认离线纯计算；`--a7w-live` / `--price-file` 时按平台真实单价算 |
| `scripts/a7w.py` | 零依赖客户端：`login / whoami / apps / points / schema / call / task` 七个子命令 |
| `CHANGELOG.md` | 版本变更记录 |

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
