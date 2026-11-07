---
name: sanjianke-ecom-detail
slug: sanjianke-ecom-detail
displayName: 电商详情页 一张实拍出整页 13 张
description: "**一张商品实拍，出一整页 13 张详情图：78 点 = 0.78 元，一位 6 分钱。** 主图 5 + 卖点 3 + 场景 2 + 细节 2 + 参数 1，按详情页真实顺序排好：`plan` 出结构单、`gen` 逐位出图、`check` 验交付。三条实测写进默认动作：800x800 只有 640,000 像素、低于 655,360 下限，1:1 位统一请求 1024x1024；上传接口价格表 cost 0，实拍图拿白名单地址不花钱；应用层 query 按次计费（72 点/次），查任务只走免费的 GET /tasks/{id}。缺 --yes 退 4 报要花多少，超 --budget 退 5 一个请求都不发。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "详情页的成本不在「会不会写提示词」，在结构、尺寸、文案位、合规这四件事上。本包把一张商品实拍到一个能上架的整页拆成五个动作：结构单、按位出图、批量命名、交付验收、合规改写。价目（1 元 = 100 点）：gpt-image-2.6 6 点/张（与尺寸、质量、格式无关，13 位同为 78 点）、改图 6 点/张（带实拍图走 /api/v1/images/edits，商品不走样）、nano_banana 72 点/次、dressing_diffusion 200 点/次、上传 0 点。四条走法一次摊开：全 gpt 78 点、换装 1 位 + 其余 gpt 272 点、全 nano 936 点、主图 5 位走多角度 423 点。三条实测做成默认：① 800x800 = 640,000 像素，低于 655,360 下限，1:1 位统一请求 1024x1024；② 上传价格表 cost 0，实拍图多传几张不花钱；③ 应用层 query 按次计费，status 只走免费的 GET /api/v1/tasks/{id}。`plan` 与 `check` 纯本地 0 点，doctor 用「带 model 的空 prompt」探端点。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 详情页
  - 商品图
  - api.a7w.cn
---

# 电商详情页 · 一张商品实拍出整页 13 张

> ## 先申请你自己的 API Key
>
> 本包不内嵌 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己账户的余额。
> 新用户有赠送点数，可以先免费自检再出图：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**一张商品实拍，一整页 13 张详情图，78 点 = 0.78 元（一位 6 分钱）。**
结构单、逐位出图、批量命名、交付验收、合规改写，五个动作一条链跑完。

## 价格（2026-11-08 现查 `GET /api/v1/pricing`，115 条规则）

| 线 | 端点 | 单价 | 形态 | 什么时候用 |
|---|---|---|---|---|
| **文生图** gpt-image-2.6 | `POST /api/v1/images/generations` | **6 点/张** | 同步 | 13 位默认走这条，最划算 |
| **改图** gpt-image-2.6 | `POST /api/v1/images/edits` | **6 点/张** | 同步 | 有实拍图，加 `--ref` 商品不走样 |
| **参考图** nano_banana | `POST /api/v1/apps/nano_banana/submit` | **72 点/次** | 异步 | 要 2K/4K 或拿参考图改画面 |
| **换装** dressing_diffusion | `POST /api/v1/apps/dressing_diffusion/submit` | **200 点/次** | 异步 | 服装类目，出「穿在身上」那一位 |
| **上传** | `POST /api/v1/upload` | **0 点** | 同步 | 实拍图先传，拿白名单地址 |

一整页四种走法：全 gpt **78 点**、换装 1 位 + 其余 gpt **272 点**、全 nano **936 点**、主图 5 位走多角度 **423 点**，`cost` 一条命令全打出来。

## 详情页结构（行业顺序，不是接口顺序）

| 类型 | 张数 | 画面 | 文案位 |
|---|---|---|---|
| 主图 `main` | 5 | 白底正面 / 核心卖点 / 使用场景 / 细节特写 / 规格尺寸 | 角标 1 处 + 标题 1 行（不超过 10 字）+ 标注 2-3 处 |
| 卖点 `point` | 3 | 痛点对比 / 材质工艺 / 信任背书 | 标题 8 字 + 副标题 18 字 |
| 场景 `scene` | 2 | 生活场景 / 出行送礼 | 副标题 12 字 |
| 细节 `detail` | 2 | 材质微距 / 工艺走线 | 标注 2 处 |
| 参数 `param` | 1 | 规格表（详情页最后一屏） | 表格 8 行 |

13 个位的画面描述、文案位、提示词、文件名，`plan` 全写进 `plan.json` 与 `page.md`。

## 五个平台的尺寸（这张表决定第一批图会不会白跑）

| `--platform` | 平台 | 比例 | 主图请求 / 上架 | 参数图请求 / 上架 |
|---|---|---|---|---|
| `taobao` | 淘宝 / 天猫 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |
| `douyin` | 抖音商城 | 3:4 | 1200x1600 / 1200x1600 | 768x1024 / 750x1000 |
| `pinduoduo` | 拼多多 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |
| `jd` | 京东 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |
| `1688` | 1688 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |

**800×800 不是合法请求尺寸**：只有 640,000 像素，低于 gpt-image 的 655,360 下限。
所以 1:1 位统一请求 1024×1024 —— 1024 方图本身满足「1:1 且不小于 800」，可以直接上架；
参数图 750 宽不是 16 的倍数，请求 768×1024（3:4，正好落在详情页宽度上）。

## 三条别人不会告诉你的

**一、详情页的钱要花在「位」上，不是花在「张」上。** gpt-image 按张计费，与尺寸、质量、
输出格式都无关 —— 1200×1600 和 1024×1024 都是 6 点。所以抖音竖版主图不加钱，
2K 反而没必要：上架口径 800-1600 宽，6 点档够用。

**二、上传是 0 点，实拍图先传再出图。** 价目表里 `/api/v1/upload` 写着 `cost: 0`，
返回 `oss.gpu.likeadmin.cn/openapi/…` 的白名单地址（约 24 小时有效）。商品实拍多传几张
不花钱，改图线和 nano 线都吃这个地址。

**三、应用层 query 按次计费，查任务只走 `/tasks/{id}`。** `nano_banana/query` 一次 72 点，
轮询一次就是一张商品图的价。本包 `status` 只打免费的 `GET /api/v1/tasks/{id}`；
`doctor` 一次 `GET /api/v1/apps/<app>` 都不发（那条通配计价，换装读一次就是 200 点）。

## 交付清单（一单要交的东西）

| 类型 | 张数 | 出图尺寸 | 上架尺寸 | 命名 |
|---|---|---|---|---|
| 主图 | 5 | 1024x1024（抖音 1200x1600） | 800x800（抖音原图） | `SHIRT01_D01_main_1024x1024_v01.png` |
| 卖点 | 3 | 同上 | 同上 | `SHIRT01_D06_point_1024x1024_v01.png` |
| 场景 | 2 | 同上 | 同上 | `SHIRT01_D09_scene_1024x1024_v01.png` |
| 细节 | 2 | 同上 | 同上 | `SHIRT01_D11_detail_1024x1024_v01.png` |
| 参数 | 1 | 768x1024 | 750x1000 | `SHIRT01_D13_param_768x1024_v01.png` |

**命名规范：`<SKU>_D<位号两位>_<类型>_<宽x高>_v<版本两位>.<png|jpg|webp>`。**
`plan` 按这套写 13 个文件名，`check` 按这套验：张数、命名、真实像素（读文件头）、体积；
再加 `--copy 文案.json` 就逐条扫绝对化用语。`page.md` 里带一张合规改写对照表，
把「全网最低价」改成「同款比价截图 + 到手价（附链接）」这种可验证的写法。

## 这个包和底层能力包的分工

能力包做「单步调通一条线」，本包做「一个岗位一单要交的那一页」。

| | 能力包（`sanjianke-ecom-studio` / `sanjianke-ecom-picset`） | 本包 `sanjianke-ecom-detail` |
|---|---|---|
| 形态 | 单步比价 / 一套素材流水线 | 一整页详情页结构：13 位 × 平台尺寸 × 文案位 |
| 入口 | 一次出图、一次换装、一次批量 | 一张结构单管 13 位，按类型或位号挑选 |
| 交付物 | 若干张图 + 台账 | 13 张按规范命名的图 + `plan.json` + `page.md` + 验收报告 |
| 谁在用 | 设计试提示词、运营补一张 | 店铺运营 / 视觉一单做完上架、验收、对账 |
| 价格视角 | 单张 / 单次 | 一整页 / 四种走法 / 一单 78 点 |

同赛道三个包一句话分清：

- 临时来一张、三条线比价、单次换装 → `sanjianke-ecom-studio`
- 一套 10 张上架素材（主图 + 场景 + 细节）流水线 → `sanjianke-ecom-picset`
- 一整页详情页：13 位结构、平台尺寸、文案位、合规验收 → **本包**

## 三步上手

```bash
python3 scripts/a7w.py login --key sk-你的key                    # 1) 填 Key
python3 scripts/run.py doctor                                    # 2) 自检（0 点）
python3 scripts/run.py plan --product "白色亚麻衬衫" --sku SHIRT01 --platform taobao --write --outdir ./out
```

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 13 位结构 + 五平台尺寸表 + 五条线的价 |
| `cost` | 免费 | 算钱：一页 13 位 + 四种走法（`--dress` 加换装位数） |
| `doctor` | 免费 | 10 项自检，含「余额与流水前后一致 = 本轮 0 点」 |
| `plan` | 免费 | 出结构单：13 位的画面 / 文案位 / 尺寸 / 文件名（`--write` 落盘） |
| `upload` | 免费 | 实拍图传平台，拿 `oss.gpu.likeadmin.cn` 白名单地址 |
| `gen` | **6 点/张**（nano 72、换装 200） | 按位出图；`--slot` / `--kind` 选位，`--ref` 走改图线 |
| `check` | 免费 | 交付验收：张数 / 命名 / 像素 / 体积 / 文案合规 |
| `status` | 免费 | 查异步任务（只走 `GET /api/v1/tasks/{id}`） |
| `log` | 免费 | 本地台账（`~/.a7w/ecom-detail-ledger.json`） |

```bash
python3 scripts/run.py cost --platform taobao
python3 scripts/run.py upload --file 实拍.jpg
python3 scripts/run.py gen --plan ./out/plan.json --ref 实拍.jpg --outdir ./out --yes
python3 scripts/run.py check --dir ./out --plan ./out/plan.json --copy ./out/copy.json
```

## 规格

| 项 | 说明 |
|---|---|
| 依赖与出图线 | Python 3.7+ 标准库，`pip install` 一个都不用；gpt 文生图 / 改图（同步）· nano_banana（异步）· dressing_diffusion（异步）· `/api/v1/upload`（0 点） |
| 计费口径 | gpt 6 点/张（按响应里实际张数）；nano 72 点/次（多角度 25 点 × 视角数）；换装 200 点/次；上传 0 点 |
| 闸门 | 缺 `--yes` → **4** 并报出要花多少点；预计 > `--budget` → **5**，一个请求都不发；`--budget` 单位是「点」，默认 500 = 5 元 |
| 退出码 | `0` 成功 / `2` 用法错 / `3` 验收没过 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 写在子命令前后都行，stdout 只有一个 JSON 文档：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}`，`kind` 取 `usage｜gate｜confirm｜budget｜call｜interrupt｜internal` |
| 尺寸校验 | 本地先验：16 的倍数、长边/短边 ≤ 3:1、单边 ≤ 3840、总像素 655,360 – 8,294,400 |

排错见 `references/troubleshooting.md`，接口原文见 `references/api-contract.md`。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
