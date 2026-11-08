---
name: sanjianke-ecom-picset
slug: sanjianke-ecom-picset
displayName: 电商图包：一张商品图出 10 张上架素材
version: 1.0.0
summary: "电商出图的真实成本不在「会不会写提示词」，在「用哪条线、要不要重复劳动」。本包把一张商品图到一套上架素材拆成五个动作：主图位规划、尺寸适配、按位出图、批量命名、合规清单。价格摊开：gpt-image-2.6 文生图 6 点/张、改图 6 点/次（流水实测两笔各 -6）、nano_banana 72 点/次、换装 200 点/次。同一套 10 张，全走 gpt 是 60 点，全走 nano 是 720 点，加一次换装是 260 点，先用 `cost` 看清再动手。三条实测结论做成默认行为：① 应用层 query 按次扣费，流水 216 笔 × 72 点 = 15,552 点，轮询只走免费的 `GET /api/v1/tasks/<id>`；② `GET /api/v1/apps/<app>` 读一次就按该应用单价扣（换装 200、出图 72），`doctor` 一次都不读；③ 800×800 只有 640,000 像素、低于下限 655,360，按平台自动换算成 1024×1024 / 768×1024 / 1200×1600。`plan` 与 `check` 纯本地 0 点；`gen` 每张图单独一次请求（n=1），出几张算几张。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 商品图
  - 主图规格
  - api.a7w.cn
---

# 电商图包 · 一张商品图出 10 张上架素材

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。新用户有赠送点数，可以先免费自检再出图：
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**一张商品图，10 张能上架的素材，60 点 = 6 毛钱。** 主图位规划、尺寸适配、批量命名、合规清单，一条流水线跑完。

## 价目表（四条路径，价格都核过源）

| 路径 | 端点 | 单价 | 形态 | 什么时候用 |
|---|---|---|---|---|
| **文生图** gpt-image-2.6 | `POST /api/v1/images/generations` | **6 点/张** | 同步 | 白底图 / 场景图 / 细节图，本包默认 |
| **改图** gpt-image-2.6 | `POST /api/v1/images/edits` | **6 点/次** | 同步 | 有实拍图要保商品不走样，加 `--ref` |
| **出图** nano_banana | `POST /api/v1/apps/nano_banana/submit` | **72 点/次** | 异步 | 要 2K/4K、要 12 张参考图 |
| **换装** dressing_diffusion | `POST /api/v1/apps/dressing_diffusion/submit` | **200 点/次** | 异步 | 模特图 + 服装图 → 穿在身上的效果图 |

同一套 10 张（主图 5 + 场景 3 + 细节 2）：

| 走法 | 算法 | 点数 | 折合 |
|---|---|---|---|
| 全 gpt（默认） | 10 × 6 | **60 点** | 0.60 元 |
| 全 gpt 改图（带实拍图） | 10 × 6 | **60 点** | 0.60 元 |
| 全 nano | 10 × 72 | 720 点 | 7.20 元 |
| 换装 1 张 + gpt 10 张 | 200 + 60 | 260 点 | 2.60 元 |

**结论**：主图、场景、细节全部走 6 点那条；换装只买「衣服穿上去」那一张，别的线替不了。

## 三条干货（都是流水里看出来的，已做成默认行为）

**1. 应用层 `query` 不是免费读。** 流水里 `sync:/api/v1/apps/nano_banana/query` 共 **216 笔、
每笔 −72 点、合计 −15,552 点**。所以本包所有异步轮询只走免费的 `GET /api/v1/tasks/<id>`，
`doctor` 里有一条检查专门盯着这件事。

**2. 800×800 不是合法请求尺寸。** gpt-image 要求总像素 655,360–8,294,400，而 800×800 只有
**640,000**——差 15,360，扣在「看着对、其实不合法」上。本包按平台自动换算：

| `--platform` | 平台要求 | 实际请求 `size` | 为什么 |
|---|---|---|---|
| `taobao` / `1688` / `pinduoduo` | 800×800（1:1） | `1024x1024` | 800×800 像素不够，1024 是最近的合法正方 |
| `taobao34` | 750×1000（3:4） | `768x1024` | 750 不是 16 的倍数，768×1024 恰好 3:4 |
| `douyin` | 1200×1600（3:4） | `1200x1600` | 本身合法，原样用 |
| `detail` | 750 宽（详情单屏） | `768x1024` | 出完统一缩到 750 宽再拼 |

有商品实拍图时加 `--ref 实拍.png`，同样的 6 点走改图线，商品不走样、背景重新生。

## 完整链路（五个动作）

```bash
# 0) 免费：四条路径的价 + 一套素材四种走法 + 尺寸适配表
python3 scripts/run.py catalog

# 1) 免费：先算钱（本次 + 三条线对照），超预算这里就能看到
python3 scripts/run.py cost --platform taobao --main 5 --scene 3 --detail 2

# 2) 免费：自检 Key / 端点 / 价目表，并证明本轮扣 0 点
python3 scripts/run.py doctor

# 3) 免费：主图位规划，生成 plan.json（每个位的提示词、尺寸、点数都写进去）
python3 scripts/run.py plan --product "白色亚麻衬衫" --platform taobao --outdir ./out

# 4) 出图：按位跑（6 点/张；加 --ref 走改图线；加 --engine nano 走 72 点那条）
python3 scripts/run.py gen --plan ./out/plan.json --outdir ./out --yes

# 5) 免费：批量命名 + 合规清单
python3 scripts/run.py names --dir ./out --platform taobao --apply
python3 scripts/run.py check --dir ./out --platform taobao
```

只想先看请求、不花钱：任何付费命令加 `--dry-run`，端点、body、点数逐条打出来。

## 三步上手

```bash
python3 scripts/a7w.py login --key sk-你的key          # 1) 填 Key
python3 scripts/run.py doctor                          # 2) 自检（0 点）
python3 scripts/run.py plan --product "白色亚麻衬衫" --platform taobao --outdir ./out
```

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 四条路径的价 + 一套素材四种走法 + 尺寸适配表 |
| `cost` | 免费 | 算钱：`--main/--scene/--detail`、`--engine`、`--ref`、`--dress` |
| `doctor` | 免费 | 自检 6 类检查，含「余额前后一致 = 扣 0 点」 |
| `plan` | 免费 | 生成 `plan.json`（10 个位的提示词 + 尺寸 + 点数） |
| `gen` | **6 点/张** | 按位出图；`--slot` / `--kind` 选位，`--ref` 改图，`--engine nano` 切 72 点线 |
| `names` | 免费 | 批量命名成 `picset_taobao_main01_1024x1024.png`，`--apply` 才动文件 |
| `check` | 免费 | 合规清单：真实像素、比例偏差、命名、体积、计划齐不齐 |
| `status` | 免费 | 查异步任务（只走 `/api/v1/tasks/<id>`） |
| `log` | 免费 | 本地台账（`~/.a7w/ecom-picset-ledger.json`） |

## 和 sanjianke-ecom-studio 的分工

两个包都接同一批线，分工是**「一步」和「一套」**：

| | `sanjianke-ecom-studio` | 本包 `sanjianke-ecom-picset` |
|---|---|---|
| 形态 | 单步工具 + 三条线比价 | 一套素材的流水线（5 个动作串起来） |
| 入口 | 直接给提示词或换装图 | 先 `plan` 排 10 个位，再逐位出图 |
| 交付物 | 出图 + 落盘 + 台账 | plan.json + 按位文件 + 规范命名 + 合规清单 |
| 擅长 | 临时补一张、试提示词、单次换装 | 新品上架、一批 SKU 走同一套模板 |

一句话：**要「来一张」用 ecom-studio；要「上新一套」用本包。**

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | 只用 Python 3.7+ 标准库，`pip install` 一个都不用 |
| 出图线 | gpt-image-2.6 同步（`n=1`，每张一次请求）；nano_banana 异步（submit → 轮询 `/tasks`） |
| 计费口径 | gpt 6 点/张（流水 82 笔 −6）；改图 6 点/次（流水 2 笔 −6）；nano 72、换装 200（价格表 flat） |
| 闸门 | 缺 `--yes` → 退出码 4 并报要花多少；预计 > `--budget` → 5，**一个请求都不发**；`--budget` 单位是「点」，1 元 = 100 点，默认 500 |
| 退出码 | `0` 成功 / `2` 用法错 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断；`check` 不通过给 `3` |
| `--json` | 写在子命令前后都行，stdout 只有一个 JSON：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}`，`kind` 取 `usage｜gate｜confirm｜budget｜call｜interrupt｜internal` |
| 尺寸校验 | 本地先验：16 的倍数、长边/短边 ≤ 3:1、单边 ≤ 3840、总像素 655,360–8,294,400 |
| 合规清单 | `check` 用文件头读真实像素，比例容差 3%（+0.25% 像素舍入），默认单张 ≤ 3 MB |

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
