# 电商素材台 · 换装出图一套配齐

**一件衣服，三种用法：换到模特身上（200 点）、出场景图（6 点）、出细节图（6 点）—— 一套主图不到一块钱。**

走 [api.a7w.cn](https://api.a7w.cn/) 的三条生成线，零依赖、只用 Python 标准库：

| 线 | 单价 | 端点 |
|---|---|---|
| 换装 `dressing_diffusion` | **200 点/次** | `POST /api/v1/apps/dressing_diffusion/submit` |
| 出图 `nano_banana` | **72 点/次** | `POST /api/v1/apps/nano_banana/submit` |
| 主图 `gpt-image-2.6` | **6 点/张** | `POST /api/v1/images/generations`（同步） |

同一套「1 张换装 + 2 张场景 + 2 张细节」：全 gpt **36 点**、换装 + gpt 224 点、
换装 + nano 344 点、全 nano 432 点。**6 点那张最划算**，换装只买「衣服穿上去」那一张。

---

## 三条实测出来的省钱规则，都做成了默认动作

### 1. 应用层 `submit` 空 body 也会建单

`dressing_diffusion` 和 `nano_banana` 的 `submit`，**一个空 JSON 也能拿到 `task_id`**
（实测 `200 / code:1 / success`，任务真的建了，预扣照走）。所以「先空 body 探参数」这个习惯，
在这两条线上就是直接下单。

本包的做法：`dress` / `generate` / `batch` 先在本地校验，**缺必填直接退 2，一个请求都不发**；
内部还有一道兜底，空 body 一律拒绝。

### 2. `GET /api/v1/apps/<app>` 不是免费读

价格表把 `dressing_diffusion/*` 记成 200 点、`nano_banana/*` 记成 72 点，**读一次 schema 就按这个价扣**
（实测：读一次换装应用 −200 点，读一次出图应用 −72 点）。

本包的做法：`doctor` 只用免费的 `GET /api/v1/models`、`GET /api/v1/apps`、`GET /api/v1/pricing`
判断「应用在架 + 端点存在 + 价格对不对」，**不读单应用 schema**。

### 3. 轮询只走 `/api/v1/tasks/<task_id>`

价格表里两个应用的 `query` 没有单独标 0，而同表的 `pic_lipsync/query`、`flashvsr/query`
都显式标了 `cost: 0`。本包的轮询与 `status` 一律走免费的 `GET /api/v1/tasks/<task_id>`。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费：三条线并排的价（离线）
python3 scripts/run.py catalog

# 3) 免费：自检 Key / 端点 / 价格表（0 建单、0 扣费）
python3 scripts/run.py doctor

# 4) 免费：先算钱
python3 scripts/run.py cost --dress 1 --scene 2 --detail 2     # 224 点 = 2.24 元

# 5) 换装（200 点）
python3 scripts/run.py dress \
    --model-url https://example.com/model.jpg \
    --garment upper=https://example.com/shirt.jpg --yes

# 6) 批量场景图 / 细节图（6 点/张）
python3 scripts/run.py generate --engine gpt --n 2 --outdir ./out --yes \
    --prompt "白色亚麻衬衫的咖啡馆场景图，自然光，无文字"
```

---

## 一条命令跑完整套

```bash
python3 scripts/run.py batch \
    --model-url https://example.com/model.jpg \
    --garment upper=https://example.com/shirt.jpg \
    --product "白色亚麻衬衫" --scene 2 --detail 2 --outdir ./out --yes
```

默认「换装 1 次 + 场景 2 张 + 细节 2 张」= **224 点（2.24 元）**。
想省掉换装那一步加 `--no-dress`，一套 4 张场景/细节只要 **24 点**。

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费（离线） | 三条线的能力、端点、单价并排 + 一套素材四种走法 |
| `cost` | 免费 | 先算钱：`--dress / --nano / --gpt / --scene / --detail` |
| `doctor` | 免费 | 自检 Key、两个应用在架、价格表口径、gpt 端点（422）、任务查询 |
| `dress` | **200 点/次** | 换装：`--model-url` + `--garment upper=URL`（可 `bottom=` / `full=`） |
| `generate` | **72 点/次** 或 **6 点/张** | `--engine nano`（默认）/ `--engine gpt` |
| `batch` | 200 + 6 × 张数 | 换装 → 场景图 → 细节图，一条链路 |
| `status` | 免费 | 查任务；给 `--outdir` 顺手下载结果图 |
| `log` | 免费 | 本地台账（`~/.a7w/ecom-studio-ledger.json`） |

---

## 用法示例

```bash
# 上下套装一起换（上衣 + 裤子）
python3 scripts/run.py dress --model-url https://.../m.jpg \
    --garment upper=https://.../shirt.jpg \
    --garment bottom=https://.../pants.jpg --yes

# 连衣裙 / 全身装
python3 scripts/run.py dress --model-url https://.../m.jpg \
    --garment full=https://.../dress.jpg --yes

# nano 线：2K + 参考图编辑（72 点/次）
python3 scripts/run.py generate --prompt "把背景换成明亮的厨房，商品形状保持不变" \
    --resolution 2K --aspect-ratio 1:1 \
    --image https://.../product.jpg --yes

# 只看请求不花钱
python3 scripts/run.py batch --model-url https://.../m.jpg \
    --garment upper=https://.../c.jpg --dry-run

# 把上一次没等到的任务捞回来
python3 scripts/run.py status task_xxxxxxxx --outdir ./out
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--model-url` | 必填 | 模特图 http(s) 链接（`dress` / `batch`） |
| `--garment` | 必填 | 服装图，可重复：`upper=URL` / `bottom=URL` / `full=URL` |
| `--prompt` | 必填 | 画面描述（`generate` / `batch` 的提示词可用 `--scene-prompt` 覆盖） |
| `--engine` | `nano` | `nano` = 72 点/次；`gpt` = 6 点/张 |
| `--resolution` | `1K` | nano 档位：`1K` / `2K` / `4K` |
| `--aspect-ratio` | `auto` | `1:1` / `3:4` / `4:5` / `16:9` / `9:16` … |
| `--image` | — | nano 参考图 URL，给了就自动转 `action=edit`（最多 12 张） |
| `--n` | 1 | gpt 张数 1–4 |
| `--size` | `auto` | gpt 尺寸：`auto` / `1024x1024` / `1k` / `2k` / `4k` |
| `--scene` / `--detail` | 2 / 2 | `batch` 里场景图、细节图各几张 |
| `--outdir` | `.` | 图片保存目录（建议 `./out` 这类包外目录） |
| `--budget` | 600 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实扣费 |
| `--dry-run` | — | 只打印请求，不提交 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、URL 不合法、`n` 越界、选项缩写） |
| `4` | 需要确认 —— 没给 `--yes`（还没花钱） |
| `5` | 预算不足 —— 一个请求都不发 |
| `6` | 调用失败 / 任务失败 / 没出图 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "line": "gpt", "elapsed": 43.6, "requested": 1, "returned": 1,
 "files": ["./shot-01.png"], "urls": [], "billedPoints": 6}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档，人读信息走 stderr。

---

## 计费口径

| 项 | 口径 |
|---|---|
| 换装 | 服务端 flat **200 点/次**（`/api/v1/pricing` 原文：固定 200 点/次） |
| nano_banana | 服务端 flat **72 点/次**；请求体带 `views[]` 时改为 25 点 × 视角数 |
| gpt-image-2.6 | **6 点/张**，按 `data` 里实际返回张数；参数错 / 失败不扣费 |
| 对账 | 以任务返回的 `usage.points_cost` 为准；每笔真实扣费都记进 `log` |

---

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

---

## 免责

- 生成内容的合规责任在使用者：肖像与商标请自行排查，商品卖点文案由你确认。
- 真实扣费以任务返回的 `usage.points_cost` 为准，`cost` 给的是预估。
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
