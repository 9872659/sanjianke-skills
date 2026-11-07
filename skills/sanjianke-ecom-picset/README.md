# 电商图包 · 一张商品图出 10 张上架素材

**一套 10 张电商上架素材（主图 5 + 场景 3 + 细节 2）只要 60 点 = 0.60 元。**

主图位规划 → 尺寸适配 → 按位出图 → 批量命名 → 合规清单，五个动作一条流水线，
接 `api.a7w.cn` 的 gpt-image-2.6，零依赖，只用 Python 标准库。

---

## 为什么值得用

自己出电商图，最耗时间的从来不是「写提示词」：

- **不知道要出几张、每张干什么** —— 打开后台才发现主图位是 5 个，场景和细节要另外补；
- **尺寸对不上** —— 平台写 800×800，请求发出去被网关按像素下限拒了；
- **出完一堆 `output-1.png`** —— 上架时一张张对位，10 张能花掉半小时；
- **不知道一套要花多少钱** —— 出到一半才发现走错了线。

本包把这四件事做成了命令：`plan` 排位、`cost` 报价、`gen` 出图、`names` 改名、`check` 验收。

---

## 价目表（四条路径，价格都核过源）

| 路径 | 端点 | 单价 | 形态 | 什么时候用 |
|---|---|---|---|---|
| **文生图** gpt-image-2.6 | `POST /api/v1/images/generations` | **6 点/张** | 同步 | 白底 / 场景 / 细节，本包默认 |
| **改图** gpt-image-2.6 | `POST /api/v1/images/edits` | **6 点/次** | 同步 | 有实拍图要保商品不走样，加 `--ref` |
| **出图** nano_banana | `POST /api/v1/apps/nano_banana/submit` | **72 点/次** | 异步 | 要 2K/4K、要 12 张参考图 |
| **换装** dressing_diffusion | `POST /api/v1/apps/dressing_diffusion/submit` | **200 点/次** | 异步 | 模特图 + 服装图 → 试穿效果图 |

同一套 10 张的四种走法：

| 走法 | 算法 | 点数 | 折合 |
|---|---|---|---|
| 全 gpt（默认） | 10 × 6 | **60 点** | 0.60 元 |
| 全 gpt 改图（带实拍图） | 10 × 6 | **60 点** | 0.60 元 |
| 全 nano | 10 × 72 | 720 点 | 7.20 元 |
| 换装 1 张 + gpt 10 张 | 200 + 60 | 260 点 | 2.60 元 |

价格出处：gpt 的 6 点/张来自流水（`sync:/api/v1/images/generations` 148 笔里 82 笔是 −6），
改图 6 点/次来自流水（`sync:/api/v1/images/edits` 2 笔各 −6）；nano 72、换装 200 来自
`GET /api/v1/pricing` 的 flat 规则。

---

## 三条实测干货

### 1. 应用层 `query` 不是免费读

流水里 `sync:/api/v1/apps/nano_banana/query` 共 **216 笔、每笔 −72 点、合计 −15,552 点**。
轮询一次就是一张图的钱。所以本包所有异步轮询只走免费的 `GET /api/v1/tasks/<task_id>`，
`doctor` 里有一条检查专门盯着这件事。

### 2. 800×800 不是合法请求尺寸

gpt-image 要求总像素 655,360–8,294,400，而 800×800 只有 **640,000**。
差 15,360，扣在「看着对、其实不合法」上。本包按平台自动换算：

| `--platform` | 平台要求 | 实际请求 `size` |
|---|---|---|
| `taobao` / `1688` / `pinduoduo` | 800×800（1:1） | `1024x1024` |
| `taobao34` | 750×1000（3:4） | `768x1024` |
| `douyin` | 1200×1600（3:4） | `1200x1600` |
| `detail` | 750 宽（详情单屏） | `768x1024` |

750 也不是 16 的倍数，所以 3:4 一律给 768×1024（既合法又恰好 3:4）。

### 3. 改图不加价

流水里 `sync:/api/v1/images/edits` 两笔各 **−6 点**，和文生图同价。
有商品实拍图时加 `--ref 实拍.png`，同样的 6 点走改图线：商品不走样、背景重新生。

---

## 完整链路

```bash
# 0) 免费：四条路径的价 + 四种走法 + 尺寸适配表
python3 scripts/run.py catalog

# 1) 免费：先算钱
python3 scripts/run.py cost --platform taobao --main 5 --scene 3 --detail 2

# 2) 免费：自检（含「本轮扣 0 点」的余额前后对比）
python3 scripts/run.py doctor

# 3) 免费：主图位规划 → plan.json
python3 scripts/run.py plan --product "白色亚麻衬衫" --platform taobao --outdir ./out

# 4) 出图：按位跑（6 点/张）
python3 scripts/run.py gen --plan ./out/plan.json --outdir ./out --yes

#    只补两个位、且用实拍图保商品一致：同样是 6 点/张
python3 scripts/run.py gen --plan ./out/plan.json --slot main01,main02 \
    --ref 实拍.png --outdir ./out --yes

# 5) 免费：批量命名 + 合规清单
python3 scripts/run.py names --dir ./out --platform taobao --apply
python3 scripts/run.py check --dir ./out --platform taobao
```

---

## 三步上手

```bash
python3 scripts/a7w.py login --key sk-你的key    # 1) 填 Key（不内嵌，用你自己的）
python3 scripts/run.py doctor                    # 2) 自检，0 点
python3 scripts/run.py plan --product "白色亚麻衬衫" --platform taobao --outdir ./out
```

---

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 四条路径的价 + 一套素材四种走法 + 尺寸适配表 |
| `cost` | 免费 | 算钱：`--main/--scene/--detail`、`--engine`、`--ref`、`--dress` |
| `doctor` | 免费 | 6 类自检，含「余额前后一致 = 扣 0 点」 |
| `plan` | 免费 | 生成 `plan.json`：10 个位的提示词、尺寸、点数 |
| `gen` | **6 点/张** | 按位出图；`--slot`/`--kind` 选位，`--ref` 改图，`--engine nano` 切 72 点线 |
| `names` | 免费 | 批量命名成 `picset_taobao_main01_1024x1024.png`，`--apply` 才动文件 |
| `check` | 免费 | 合规清单：真实像素、比例偏差、命名、体积、计划齐不齐 |
| `status` | 免费 | 查异步任务（只走 `/api/v1/tasks/<id>`） |
| `log` | 免费 | 本地台账 |

两道闸门：缺 `--yes` 退 **4** 并告诉你要花多少；预计超 `--budget` 退 **5**，一个请求都不发。
`--budget` 单位是「点」，1 元 = 100 点，默认 500。先看不花钱的请求就加 `--dry-run`。

---

## 和 sanjianke-ecom-studio 的分工

| | `sanjianke-ecom-studio` | 本包 |
|---|---|---|
| 形态 | 单步工具 + 三条线比价 | 一套素材的流水线（5 个动作） |
| 入口 | 直接给提示词或换装图 | 先 `plan` 排 10 个位，再逐位出图 |
| 交付物 | 出图 + 落盘 + 台账 | plan.json + 按位文件 + 规范命名 + 合规清单 |
| 擅长 | 临时补一张、试提示词、单次换装 | 新品上架、一批 SKU 走同一套模板 |

**要「来一张」用 ecom-studio；要「上新一套」用本包。**

---

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | Python 3.7+，只用标准库，`pip install` 一个都不用 |
| 出图线 | gpt-image-2.6 同步（`n=1`，每张一次请求）；nano_banana 异步（submit → 轮询 `/tasks`） |
| 尺寸校验 | 本地先验：16 的倍数、长边/短边 ≤ 3:1、单边 ≤ 3840、总像素 655,360–8,294,400 |
| 合规清单 | `check` 用文件头读真实像素，比例容差 3%（+0.25% 像素舍入），默认单张 ≤ 3 MB |
| 退出码 | `0` 成功 / `2` 用法错 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断；`check` 不通过给 `3` |
| `--json` | 前后都能写，stdout 只有一个 JSON：成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}` |
| Key | `--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`；本包不内嵌任何 Key |

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
