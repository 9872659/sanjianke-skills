---
name: sanjianke-ecom-studio
slug: sanjianke-ecom-studio
displayName: 电商素材台 换装出图一套配齐
description: "**一件衣服，三种用法：换到模特身上（200 点）、出场景图（6 点）、出细节图（6 点）—— 一套主图不到一块钱。** `catalog` 把换装 200 点/次、nano_banana 72 点/次、gpt-image-2.6 6 点/张三条线并排摆出来：同一个「1 次换装 + 4 张场景细节」的活，走 6 点那条 224 点，走 72 点那条 344 点。`cost` 先报价，`--budget` 与 `--yes` 是两道硬闸门；`doctor` 用只读目录与价格表自检，0 建单 0 扣费。`batch` 一条链路跑完：模特图 + 服装图换装出效果图，再批量出场景图与细节图，自动落盘到本地。零依赖，只用 Python 标准库。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "电商出图最贵的不是「不会写提示词」，是「用错线」：换装、nano_banana、gpt-image 三条线单价差 33 倍，一套素材选错线就是多花三位数的点。本包先摊价再动手——`catalog` 用服务端价格表把 200 / 72 / 6 三档并排，`cost` 按件算钱，`--budget` 超了直接退 5、一个请求都不发，`--yes` 没给退 4 并告诉你这次要花多少。三个实测结论写进了默认行为：① 两个应用层 submit **空 body 也会建单**，所以本包任何路径都不会发空 body 或缺必填的 submit，缺参数在本地就退 2；② `GET /api/v1/apps/<app>` **按该应用单价计费**（换装一次 200 点、出图一次 72 点），`doctor` 因此只用免费的 /models、/apps、/pricing；③ 轮询只走免费的 `GET /api/v1/tasks/<task_id>`，不走应用级 query。`batch` 把「换装 1 次 + 场景 2 张 + 细节 2 张」串成一条链路，默认 224 点，全走 gpt 只要 36 点。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 换装
  - 商品图
  - api.a7w.cn
---

# 电商素材台 · 换装出图一套配齐

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，也不代付费用。到 **[算力集市 api.a7w.cn](https://api.a7w.cn/)** 注册、
> 创建**你自己的** Key（新用户有赠送点数，可以先免费试跑），填进环境变量 `A7W_API_KEY`
> 或传给 `--key`：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**一件衣服、一张商品图，出一整套能上架的电商素材。** 三条线按件计价，选对线一套不到一块钱。

## 三条线对照（价格来自服务端价格表）

| 线 | 单价 | 端点 | 干什么 | 什么时候用 |
|---|---|---|---|---|
| **换装** `dressing_diffusion` | **200 点/次** | `POST /api/v1/apps/dressing_diffusion/submit` | 模特图 + 服装平铺图 → 穿在身上的效果图 | 有模特图，要把衣服穿上去 |
| **出图** `nano_banana` | **72 点/次** | `POST /api/v1/apps/nano_banana/submit` | 文生图 / 参考图编辑，1K·2K·4K，12 张参考图 | 要 2K/4K 或拿参考图改画面 |
| **主图** `gpt-image-2.6` | **6 点/张** | `POST /api/v1/images/generations`（同步） | 白底图 / 场景图 / 细节图，一次 1~4 张 | 批量铺图；**6 点那张最划算** |

同一套「1 张换装 + 2 张场景 + 2 张细节」的四种走法：

| 走法 | 算法 | 点数 | 折合 |
|---|---|---|---|
| 全 gpt（6 张） | 6 × 6 | **36 点** | 0.36 元 |
| 换装 + gpt | 200 + 4 × 6 | 224 点 | 2.24 元 |
| 换装 + nano | 200 + 2 × 72 | 344 点 | 3.44 元 |
| 全 nano（6 次） | 6 × 72 | 432 点 | 4.32 元 |

**结论**：换装只买「衣服穿上去」这一张（200 点，别的线替不了）；其余批量图全部走 gpt 的 6 点/张。

## 一条完整链路：商品图 → 换装 → 场景图 → 细节图 → 一套上架素材

```bash
# 0) 免费（离线）：三条线并排的价 + 一套素材四种走法
python3 scripts/run.py catalog

# 1) 免费：自检 Key / 两个应用在架 / 价格表 / gpt 端点（0 建单、0 扣费）
python3 scripts/run.py doctor

# 2) 免费：先算这一套要多少点
python3 scripts/run.py cost --dress 1 --scene 2 --detail 2      # 224 点 = 2.24 元

# 3) 换装：模特图 + 服装平铺图 → 试穿效果图（200 点）
python3 scripts/run.py dress --model-url https://example.com/model.jpg \
    --garment upper=https://example.com/shirt.jpg --yes

# 4) 场景图 + 细节图：同一件商品批量 4 张（4 × 6 = 24 点）
python3 scripts/run.py generate --engine gpt --n 2 --outdir ./out --yes \
    --prompt "白色亚麻衬衫的咖啡馆场景图，自然光，无文字"
python3 scripts/run.py generate --engine gpt --n 2 --outdir ./out --yes \
    --prompt "白色亚麻衬衫的领口走线细节特写，微距，纯色背景"

# 或者一条命令跑完整套（换装 + 场景 + 细节），默认 224 点
python3 scripts/run.py batch --model-url https://example.com/model.jpg \
    --garment upper=https://example.com/shirt.jpg \
    --product "白色亚麻衬衫" --scene 2 --detail 2 --outdir ./out --yes
```

想省掉换装那一步就加 `--no-dress`：一套 4 张场景/细节只要 24 点。

## 三条实测出来的省钱规则（本包已做成默认行为）

**1. 应用层 `submit` 空 body 也会建单。** `dressing_diffusion` 与 `nano_banana` 的 `submit`，
一个空 JSON 也能拿到 `task_id`（实测 `200 / code:1 / success`，任务真的建了）。
本包在本地先校验，缺必填直接退 2，一个请求都不发；内部还有一道兜底，空 body 一律拒绝。

**2. `GET /api/v1/apps/<app>` 不是免费读。** 价格表把 `dressing_diffusion/*` 记成 200 点、
`nano_banana/*` 记成 72 点，读一次 schema 就按这个价扣。本包 `doctor` 只用免费的
`GET /api/v1/models`、`GET /api/v1/apps`、`GET /api/v1/pricing` 判「应用在架 + 端点存在 + 价格对不对」。

**3. 轮询只走 `/api/v1/tasks/<task_id>`。** 价格表里两个应用的 `query` 没有单独标 0
（同表的 `pic_lipsync/query`、`flashvsr/query` 都显式标了 `cost: 0`），所以本包所有轮询与
`status` 都走免费的 `GET /api/v1/tasks/<task_id>`。

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费（离线） | 三条线能力/端点/单价 + 一套素材四种走法 |
| `cost` | 免费 | 算钱：`--dress / --nano / --gpt / --scene / --detail`，不给参数按一套标准素材算 |
| `doctor` | 免费 | 自检 Key、两个应用在架、价格表口径、gpt 端点（422）、任务查询端点 |
| `dress` | **200 点/次** | 换装：`--model-url` + `--garment upper=URL`（可 `bottom=` / `full=`，可多件） |
| `generate` | **72 点/次** 或 **6 点/张** | `--engine nano`（默认）走应用线；`--engine gpt` 走 6 点/张 |
| `batch` | 200 + 6 × 张数 | 换装 → 场景图 → 细节图，一条链路，自动落盘 |
| `status` | 免费 | 查任务，给 `--outdir` 就顺手下载结果图 |
| `log` | 免费 | 本地台账（`~/.a7w/ecom-studio-ledger.json`） |

常用参数：`--garment` 可多件（`upper=` / `bottom=` / `full=`）；`--engine nano` 时可加
`--resolution 1K|2K|4K`、`--aspect-ratio 3:4`、`--image 参考图URL`（自动转 `edit`）；
`--engine gpt` 时可加 `--n 1~4`、`--size 1024x1024`。`--outdir` 指到包外（如 `./out`），
`--budget` 单位是点（默认 600，1 元 = 100 点），`--yes` 确认真扣费，`--dry-run` 只打印请求。

## 退出码与 `--json`

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、URL 不合法、`n` 越界、选项缩写） |
| `4` | 需要确认 —— 没给 `--yes`（还没花钱） |
| `5` | 预算不足 —— 一个请求都不发 |
| `6` | 调用失败 / 任务失败 / 没出图 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档：成功 `{"ok": true, ...}`；
失败 `{"ok": false, "exit": N, "error": {"kind": "...", "message": "..."}}`，`kind` 取
`usage` / `gate` / `confirm` / `budget` / `call` / `interrupt` / `internal`；人读信息走 stderr。

## 计费口径

| 项 | 口径 |
|---|---|
| 换装 | 服务端 flat **200 点/次**（`/api/v1/pricing` 原文：固定 200 点/次） |
| nano_banana | 服务端 flat **72 点/次**；请求体带 `views[]` 时改为 25 点 × 视角数 |
| gpt-image-2.6 | **6 点/张**，按 `data` 里实际返回张数；参数错 / 失败不扣费 |
| 对账 | 以任务返回的 `usage.points_cost` 为准，本包每笔真实扣费都记进 `log` |

## 文件结构

```
sanjianke-ecom-studio/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（schema 原文 + 实测返回）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
