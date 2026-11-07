# 电商详情页 · 一张商品实拍出整页 13 张

**一张商品实拍，一整页 13 张详情图，78 点 = 0.78 元（一位 6 分钱）。**
主图 5 + 卖点 3 + 场景 2 + 细节 2 + 参数 1，走 [api.a7w.cn](https://api.a7w.cn/) 的 `gpt-image-2.6`，零依赖。

实测：`GET /api/v1/pricing` 115 条规则里，上传 `cost: 0`、nano_banana 72 点/次、
换装 200 点/次；gpt-image-2.6 按张 6 点（与尺寸、质量、格式都无关）。

---

## 三个真会白跑一趟的坑，都做成了默认动作

### 坑一：800×800 不是合法请求尺寸

gpt-image 要求总像素 **655,360 – 8,294,400**，而 800×800 只有 **640,000** —— 差 15,360。
看着对，其实会被参数校验拦下。所以 1:1 位统一请求 **1024×1024**：

- 1024 方图满足「1:1 且不小于 800」，**本身就能直接上架**，不用再缩
- 抖音 1200×1600（3:4）本身合法，原样请求
- 参数图 750 宽 → 请求 768×1024（750 不是 16 的倍数）

### 坑二：应用层 query 不是免费读

`nano_banana/query` 实测 **72 点/次**，轮询一次就是一张商品图的价。
本包 `status` 只走免费的 `GET /api/v1/tasks/{id}`，`doctor` 一次应用层 query 都不发。

同理，`GET /api/v1/apps/<app>` 命中通配计价（nano 72 / 换装 200，`sync` 即时结算不退），
所以 `doctor` 只用免费的 `/models`、`/apps`（列表）、`/pricing`。

### 坑三：改图不加价，商品实拍图别浪费

`POST /api/v1/images/edits` 实测同样 **6 点/张**。有商品实拍就加 `--ref 实拍.jpg`，
同价走改图线，商品不走样、背景重画。实拍图先 `upload`（**0 点**）拿白名单地址，
nano 线与换装线都吃这个地址。

---

## 价格

| 线 | 端点 | 单价 | 形态 |
|---|---|---|---|
| 文生图 gpt-image-2.6 | `POST /api/v1/images/generations` | **6 点/张** | 同步 |
| 改图 gpt-image-2.6 | `POST /api/v1/images/edits` | **6 点/张** | 同步 |
| 参考图 nano_banana | `POST /api/v1/apps/nano_banana/submit` | **72 点/次** | 异步 |
| 换装 dressing_diffusion | `POST /api/v1/apps/dressing_diffusion/submit` | **200 点/次** | 异步 |
| 上传 | `POST /api/v1/upload` | **0 点** | 同步 |

一整页四种走法：

| 走法 | 算法 | 点数 | 折合 |
|---|---|---|---|
| 全 gpt（默认） | 13 × 6 | **78 点** | 0.78 元 |
| 换装 1 位 + 其余 gpt | 200 + 12 × 6 | 272 点 | 2.72 元 |
| 全 nano | 13 × 72 | 936 点 | 9.36 元 |
| 主图 5 位多角度（各 3 视角）+ 其余 gpt | 5 × 25 × 3 + 8 × 6 | 423 点 | 4.23 元 |

nano 的多角度按 **25 点 × 选中视角数**（价格表原文，带 `views[]` 时生效）。

---

## 详情页 13 位

| 位号 | 类型 | 画面 | 文案位 |
|---|---|---|---|
| D01 | 主图 | 正面白底 | 角标（不超过 6 字） |
| D02 | 主图 | 核心卖点 | 标题（不超过 10 字） |
| D03 | 主图 | 使用场景 | 标题（不超过 10 字） |
| D04 | 主图 | 细节特写 | 标注 2 处 |
| D05 | 主图 | 规格尺寸 | 标题 + 标注 3 处 |
| D06 | 卖点 | 痛点对比 | 标题 8 字 + 副标题 18 字 |
| D07 | 卖点 | 材质工艺 | 标题 + 可验证参数 |
| D08 | 卖点 | 信任背书 | 标题 + 报告编号 |
| D09 | 场景 | 生活场景 | 副标题 12 字 |
| D10 | 场景 | 出行 / 送礼 | 副标题 12 字 |
| D11 | 细节 | 材质微距 | 标注 2 处 |
| D12 | 细节 | 工艺走线 | 标注 2 处 |
| D13 | 参数 | 规格表 | 表格 8 行 |

---

## 五个平台的尺寸

| `--platform` | 平台 | 比例 | 主图请求 / 上架 | 参数图请求 / 上架 |
|---|---|---|---|---|
| `taobao` | 淘宝 / 天猫 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |
| `douyin` | 抖音商城 | 3:4 | 1200x1600 / 1200x1600 | 768x1024 / 750x1000 |
| `pinduoduo` | 拼多多 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |
| `jd` | 京东 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |
| `1688` | 1688 | 1:1 | 1024x1024 / 800x800 | 768x1024 / 750x1000 |

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检（0 点）
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --platform taobao

# 4) 出结构单（13 位的画面 + 文案位 + 尺寸 + 文件名）
python3 scripts/run.py plan --product "白色亚麻衬衫" --sku SHIRT01 \
    --platform taobao --sell "100%亚麻,180g克重" --write --outdir ./out

# 5) 出图（6 点/张，加 --ref 走改图线）
python3 scripts/run.py gen --plan ./out/plan.json --ref 实拍.jpg --outdir ./out --yes

# 6) 验收（张数 / 命名 / 像素 / 文案合规）
python3 scripts/run.py check --dir ./out --plan ./out/plan.json
```

---

## 常用命令

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 13 位结构 + 五平台尺寸表 + 五条线的价 |
| `cost` | 免费 | 一页 13 位 + 四种走法 |
| `doctor` | 免费 | 10 项自检，含「余额与流水前后一致 = 本轮 0 点」 |
| `plan` | 免费 | 出结构单（`--write` 落 `plan.json` + `page.md`） |
| `upload` | 免费 | 实拍图传平台，拿 `oss.gpu.likeadmin.cn` 白名单地址 |
| `gen` | **6 点/张** | 按位出图；`--slot` / `--kind` 选位，`--ref` 改图 |
| `check` | 免费 | 交付验收 + 文案合规扫描 |
| `status` | 免费 | 查异步任务（只走 `GET /api/v1/tasks/{id}`） |
| `log` | 免费 | 本地台账 |

```bash
# 只出主图 5 张
python3 scripts/run.py gen --plan ./out/plan.json --kind main --outdir ./out --yes

# 只补一张，先看请求不花钱
python3 scripts/run.py gen --plan ./out/plan.json --slot 7 --dry-run

# 换装（服装类目）：模特图 + 服装图先 upload，再走 dress
python3 scripts/run.py gen --plan ./out/plan.json --slot 3 --engine dress \
    --model-url "https://oss.gpu.likeadmin.cn/openapi/…" \
    --garment-url "https://oss.gpu.likeadmin.cn/openapi/…" --yes
```

---

## 和 sanjianke-ecom-studio / sanjianke-ecom-picset 的分工

| | 能力包 | 本包 |
|---|---|---|
| 形态 | 单步比价、一套素材流水线 | 一整页详情页结构（13 位 × 平台尺寸 × 文案位） |
| 交付物 | 若干张图 | 13 张规范命名的图 + `plan.json` + `page.md` + 验收报告 |
| 谁在用 | 设计试提示词、运营补一张 | 店铺运营一单做完上架、验收、对账 |

一句话：**要「来一张」用 ecom-studio，要「一套素材」用 ecom-picset，要「一整页」用本包。**

---

## 规格

| 项 | 说明 |
|---|---|
| 依赖 | Python 3.7+ 标准库，`pip install` 一个都不用 |
| 命名 | `<SKU>_D<位号两位>_<类型>_<宽x高>_v<版本两位>.<png\|jpg\|webp>` |
| 闸门 | 缺 `--yes` → 4 并报要花多少点；超 `--budget` → 5，一个请求都不发；`--budget` 单位是点，默认 500 = 5 元 |
| 退出码 | `0` 成功 / `2` 用法错 / `3` 验收没过 / `4` 需 `--yes` / `5` 预算不足 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}` |

---

## 实测记录

```
2026-11-08  GET /api/v1/pricing
  115 条规则 · /api/v1/upload cost 0 · nano_banana/* 72 · dressing_diffusion/* 200
  /api/v1/images/generations 不在价目表内，6 点/张取自文档与流水实扣

2026-11-08  POST /api/v1/images/generations {"model":"gpt-image-2.6","prompt":""}
  HTTP 422 · prompt: String should have at least 1 character

2026-11-08  POST /api/v1/upload（空表单）
  HTTP 200 · {"code":0,"msg":"请使用 file 字段提交一个文件"}

2026-11-08  GET /api/v1/tasks/probe-no-such-task
  HTTP 200 · {"code":0,"msg":"任务不存在"}
```

---

## 免责

- 生成内容的合规责任在使用者：素材与文案按平台规则逐条核对。
- 真实扣费以响应里**实际返回的张数**为准，`cost` 给的是预估。
- 图床链接有时效（约 24 小时），出完图及时落盘到本地。

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
