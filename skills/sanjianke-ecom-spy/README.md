# 带货素材侦察 1 元拆一条爆款
**1 元（100 点）扒一条爆款，30 秒拆出标题公式、3 秒钩子、时长节奏和 3 条能直接换词的仿写标题。** 从抖音 / 小红书找到对标，把「为什么它火」写成结构，再把结构换成你的选题和封面 —— 全部走 [api.a7w.cn](https://api.a7w.cn/)，8 个接口、零依赖。

| 一条完整链路 | 花多少 |
|---|---|
| 搜关键词拿到几十条对标 | **100 点（¥1.00）** |
| 排序 / 拆结构 / 仿写 / 出图方案（本地跑） | **0 点** |
| 封面图（nano-banana AI 商品图，可选） | 72 点（¥0.72） |
| 合计 | **172 点 = ¥1.72** |

1 元 = 100 点。8 个接口一律 100 点/次，与返回条数、素材时长都无关。

---

## 价目表（8 个接口同价，`GET /api/v1/pricing` 实测）

| 能力 | 子命令 | 接口 code | 必填 | 单价 |
|---|---|---|---|---|
| 抖音搜索 | `hunt --platform dy` / `dy-search` | `douyin_search_video` | `keyword` | **100 点/次** |
| 小红书搜索 | `hunt --platform xhs` / `xhs-search` | `xhs_search_note` | `keyword` | **100 点/次** |
| 抖音视频详情 | `dy-video` | `douyin_video_detail` | `videoId` | 100 点/次 |
| 小红书笔记详情 | `xhs-note` | `xhs_note_detail` | `noteId` | 100 点/次 |
| 抖音用户作品 | `dy-user` | `douyin_user_video_list` | `secUid` | 100 点/次 |
| 小红书用户笔记 | `xhs-user-notes` | `xhs_user_note_list` | `userId` | 100 点/次 |
| 小红书用户详情 | `xhs-user` | `xhs_user_detail` | `userId` | 100 点/次 |
| 去水印取地址 | `strip` | `remove` | `url` | 100 点/次 |

价格规则原文（`/api/v1/pricing`，逐字）：

```json
"/api/v1/apps/watermark_removal/*": {
  "mode": "flat", "cost": 100, "markupPercent": 0,
  "note": "去水印/分享链解析：固定 100 点/次（上游按请求 20 点，失败亦计）"
}
```

---

## 三条别人不会告诉你的

### 一、8 个接口同一个价，所以「少搜、挑着看详情」才是省钱姿势

搜索一次就把几十条对标的标题、时长、点赞、收藏、评论一次带回来 —— 这些字段本身就够拆结构了。真正的钱花在「详情」上，而详情也是一次 100 点。

| 跑法 | 调用次数 | 花费 |
|---|---|---|
| 搜 1 次，本地排序 + 拆结构 + 仿写 | 1 | **100 点** |
| 搜 1 次 + 看 3 条详情 | 4 | 400 点 |
| 搜 1 次 + 20 条全看详情 | 21 | 2,100 点 |

本包默认就是这个姿势：`hunt` 只发 1 次搜索，然后当场排序、拆结构、给仿写和封面方案，全在本地算。

### 二、失败也计一次，所以探针只走 GET

规则 note 最后两个字是「失败亦计」。参数不全被上游拦下，同样按 100 点/次计。所以本包：

- 必填缺失在本地就退回，退 `2`，**一个请求都不发**；
- `doctor` 全部只读 GET（余额 / 模型目录 / 应用名单 / 价目 / 任务路由 / 流水 6 项），一次 POST 都不发；
- 端点存在性用 `GET /api/v1/apps` 的接口名单来证明 —— 8 个 code 一个不少才算过。

### 三、结构分析不用再花一分钱

搜索结果的 JSON 存进本地快照（`~/.a7w/ecom-spy/snapshots/`），之后 `rank` / `breakdown` / `clone` / `cover` 全是读本地文件，0 点，想跑几遍跑几遍。

- `rank`：按「赞 1 + 藏 2 + 评 3 + 转 4」排，收藏与评论权重更高（带货看的是想买，不是路过点赞）；
- `breakdown`：标题字数、数字 / 价格 / 疑问 / 身份 / 痛点 / 承诺六项要素、钩子类型、时长档与逐段节奏；
- `clone`：3 条标题 + 3 个口播钩子 + 5 段分镜骨架，主词、数字、价格锚都取自原片；
- `cover`：3 条封面 prompt（白底商品图 / 使用场景 / 前后对比）+ 该走哪条出图线 + 实际单价。

---

## 完整链路

```
① 搜索   hunt --platform dy --keyword "收纳盒"          100 点
             │
             ├─ 快照落盘  ~/.a7w/ecom-spy/snapshots/xxx.json
             ↓
② 排序   rank --by heat --top 10                        0 点
             ↓
③ 拆结构 breakdown --top 3                              0 点
             标题公式 / 钩子 / 时长 / 节奏
             ↓
④ 仿写   clone --count 3                                0 点
             3 条标题 + 3 个钩子 + 5 段分镜
             ↓
⑤ 出图   cover                                          0 点
             3 条 prompt + 走 nano_banana（72 点/张）
```

**一条链路 = 172 点（¥1.72）**：100 点采集，72 点一张封面，中间三步全免费。

---

## 三步上手

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检 + 免费看价
python3 scripts/run.py doctor
python3 scripts/run.py cost --search 1 --detail 3

# 3) 一条命令跑完整条链（1 次调用 = 100 点）
python3 scripts/run.py hunt --platform dy --keyword "收纳盒" --yes
```

跑完 `hunt` 你会直接看到：热度前 3 的对标、每条的标题公式 / 钩子 / 节奏、3 条仿写标题、3 条封面 prompt 和报价。

---

## 常用命令

```bash
python3 scripts/run.py catalog                                    # 8 个接口 + 必填 + 单价
python3 scripts/run.py cost --search 1 --detail 3 --strip 1        # 先算钱
python3 scripts/run.py doctor                                     # 只读自检，0 点
python3 scripts/run.py hunt --platform xhs --keyword "通勤穿搭" --yes
python3 scripts/run.py hunt --platform dy --keyword "小家电" --dry-run   # 只看请求
python3 scripts/run.py dy-search --keyword "收纳" --yes
python3 scripts/run.py xhs-search --keyword "通勤穿搭" --sort popularity_descending --yes
python3 scripts/run.py xhs-note --note-id 69db4372000000002103a442 --yes
python3 scripts/run.py dy-video --video-id 7000000000000000000 --yes
python3 scripts/run.py dy-user --sec-uid MS4wLjABAAAA... --yes
python3 scripts/run.py xhs-user --user-id 5f1a2b3c --yes
python3 scripts/run.py xhs-user-notes --user-id 5f1a2b3c --yes
python3 scripts/run.py strip --url "https://v.douyin.com/xxxxxxx/" --yes
python3 scripts/run.py rank --by collects --top 10                 # 本地 0 点
python3 scripts/run.py breakdown --top 3
python3 scripts/run.py clone --count 3
python3 scripts/run.py cover
python3 scripts/run.py log
```

**不加 `--yes` 退 `4`** 并告诉你这次要花多少点；**预计点数超 `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 1000 = 10 次调用）。

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--keyword` | 必填 | 搜索关键词（`hunt` / `dy-search` / `xhs-search`） |
| `--platform` | `dy` | `dy` 抖音 / `xhs` 小红书（只 `hunt`） |
| `--video-id` | 必填 | 抖音作品 ID |
| `--sec-uid` | 必填 | 抖音用户 secUid |
| `--note-id` | 必填 | 小红书笔记 ID |
| `--user-id` | 必填 | 小红书用户 ID |
| `--sort` | — | 小红书排序：`general` / `popularity_descending` / `time_descending` / `comment_descending` / `collect_descending` |
| `--note-type` | — | 小红书笔记类型：`_0` 通用 / `_1` 视频 / `_2` 图文 |
| `--page` / `--cursor` / `--last-cursor` / `--max-cursor` / `--search-id` | — | 翻页游标，取自上一页返回 |
| `--url` | 必填 | 分享链接（`strip`） |
| `--snapshot` | 最新 | 读哪份快照（`rank` / `breakdown` / `clone` / `cover`） |
| `--by` | `heat` | 排序口径：`heat` / `likes` / `collects` / `comments` / `shares` / `short` |
| `--top` | 10 / 1 | 显示几条 / 拆几条 |
| `--count` | 3 | 仿写几条标题（最多 3） |
| `--budget` | 1000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实调用 / 只打印请求 |
| `--json` / `--key` / `--host` | — | 写在子命令前后都可以 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 8 个接口 + 必填项 + 单价 |
| `cost` | 免费 | 先算钱：单次 / 组合 / 按预算能跑几次 |
| `doctor` | 免费 | 只读自检 6 项，一次 POST 都不发 |
| `rank` | 免费 | 爆款榜（本地读快照） |
| `breakdown` | 免费 | 拆结构：公式 / 钩子 / 时长 / 节奏 |
| `clone` | 免费 | 3 条标题 + 3 个钩子 + 5 段分镜 |
| `cover` | 免费 | 3 条封面 prompt + 出图线报价 |
| `log` | 免费 | 本地台账 |
| `hunt` | **100 点** | 搜索 + 当场拆结构（1 次调用） |
| `dy-search` / `xhs-search` | **100 点** | 搜索 |
| `dy-video` / `xhs-note` | **100 点** | 详情 |
| `dy-user` / `xhs-user-notes` / `xhs-user` | **100 点** | 用户与作品列表 |
| `strip` | **100 点** | 分享链接 → 无水印地址 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、快照不存在、选项缩写） |
| `3` | 自检没过（`doctor` 出现 ×） |
| `4` | 需要确认 —— 没给 `--yes`，会告诉你这次要花多少点 |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

成功：

```json
{"ok": true, "api": "douyin_search_video", "name": "抖音搜索", "count": 20,
 "items": [{"id": "7...", "title": "...", "author": "...", "likes": 120000,
            "collects": 34000, "comments": 892, "shares": 210, "duration": 23.0}],
 "estimatedPoints": 100, "yuan": "1.00", "snapshot": "~/.a7w/ecom-spy/snapshots/xxx.json"}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`；`--json` 写在子命令**前后都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-ecom-spy/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       8 个接口的参数表 + 价格原文 + 返回体形态
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 计费口径

- 8 个接口一律 **100 点/次 = ¥1.00**，flat，和返回条数、素材时长都无关。
- 上游按请求 **20 点**，对外 100 点 —— 这个 5 倍是写在规则里的售价，不是估算。
- 规则 note 写「失败亦计」，所以本地先把必填卡住，参数齐了才发。
- `--budget` 与 `--yes` 是本地闸门：预算内才发请求，`--yes` 到了才提交。
- 对账看 `GET /user/balance/logs`（免费），`sync:/api/v1/apps/watermark_removal/...` 每次 -100 点。

---

## 合规与边界

- 采集结果用于**结构分析**：拆标题怎么写、钩子怎么起、节奏怎么排，再把方法用在你自己的原创内容上。
- 原片素材的权利归原作者，转载与二创请在取得授权后使用。
- 内容真实性与广告标注按平台规则执行，带货口径以商家提供的资质与检测报告为准。

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
