# 三剪客 · 漫画分镜出图

把剧本或小说片段变成**漫画分镜序列**：角色设定卡 → 分镜表 → 逐格出图 →
**跨格一致性自检** → 拼页排版。面向漫画、条漫、分镜稿、AI 绘本。

```
characters    →  抽角色设定卡（外貌/服装/配色/特征词）
shots         →  出分镜表（每格景别/机位/画面/对白/出图提示词）
images        →  逐格出图（真花钱，先报价；支持参考图传递）
consistency   →  跨格角色一致性自检（零成本）
sheet         →  拼页/排版（本地渲染，零成本）
all           →  一条命令串全链路，断点续跑
cost / models →  算钱 / 现在有哪些模型
```

**它解决的不是「画不出图」，而是「同一个角色每格长得不一样」。**
同一个主角在第 1 格和第 12 格是两张脸，拼成一页就散了——这才是漫画/条漫流程里最贵的那一步。

## 30 秒上手

```bash
# 1) 拿 Key（新用户有赠送点数）
#    到 https://api.a7w.cn/ 注册，创建一个 API Key

# 2) 配 Key
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 3) 开工前现查接口（免费）
python3 scripts/a7w.py schema nano_banana

# 4) 抽角色设定卡（只花文本钱）
python3 scripts/run.py characters 剧本.md --out characters.json

# 5) 出分镜表（只花文本钱；出完就顺手跑一遍一致性闸门）
python3 scripts/run.py shots 剧本.md --characters characters.json --count 12 --out shots.json

# 6) 先看要花多少钱
python3 scripts/run.py cost --count 12
#   预估成本：12 张 × 24 点 = 288 点 = 2.88 元

# 7) 出图（先不带 --yes 报价，确认了再加）
python3 scripts/run.py images --shots shots.json --characters characters.json --outdir ./out
python3 scripts/run.py images --shots shots.json --characters characters.json \
    --outdir ./out --budget 300 --yes --snap-exact --ref-mode prev

# 8) 零成本自检 + 拼页
python3 scripts/run.py consistency --shots shots.json --characters characters.json
python3 scripts/run.py sheet --shots shots.json --state ./out/storyboard-state.json \
    --outdir ./pages --layout grid --cols 2 --rows 2
```

想一条命令跑完：

```bash
python3 scripts/run.py all 剧本.md --outdir ./storyboard --count 12 \
    --ref-mode prev --budget 300 --yes --snap-exact
```

**零依赖**，只要 Python 3.7+，不用 `pip install` 任何东西。
装了 Pillow 的话拼页缩放更清晰（走 LANCZOS），不装也能拼（内置纯标准库 PNG 解码/合成）。

`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端（我们靠 SHA256 校验各包副本是否一致），
本包没有改它；「读图片真实像素」放在独立模块 `scripts/imgprobe.py` 里。

## 与同族包的分工

| 包 | 产物 | 差别 |
|---|---|---|
| 新媒体配图工厂 | 文章配图（封面/内文） | 格与格之间没有角色关系 |
| 长文自动生产线 | 长文 + 配图 | 同上 |
| 短剧出片类包 | 成片（视频） | 产物是 mp4，不是分镜图 |
| **本包** | **分镜图序列 + 拼好的漫画页** | 每格有景别/机位，同一角色跨格一致 |

## 角色一致性怎么压（本包的核心）

三道一起上，少一道都压不住：

1. **角色设定卡** —— `features` 里 3~6 条、每条 4~12 字，只写看得见的东西
   （发型发色 / 瞳色 / 疤痕位置 / 固定配饰）。自检标准：画师只看这几条，画 10 次都是同一张脸。
   写「性格冷酷」是没用的，那些画不出来。
2. **硬约束提示词** —— 每格的出图提示词里必须**逐字写出**该格出场角色的全部特征词。
3. **多参考图** —— `action=edit` + `image_urls`，把**上一格**或**角色锚点图**当参考。

```bash
# 参考上一格（默认）：第 1 格文生图，第 2 格起用上一格的 image_url 做 edit
python3 scripts/run.py images --shots shots.json --characters characters.json \
    --outdir ./out --ref-mode prev --yes

# 角色锚点图（最能把脸钉住）：--anchor 或多个角色
python3 scripts/run.py images --shots shots.json --characters characters.json \
    --outdir ./out --ref-mode anchor --anchor chen=https://…/chen-anchor.png --yes
```

⚠️ 参考图必须是**公网可访问的 HTTP/HTTPS 地址**（上游 `image_urls` 的口径），本地文件传不上去。
本包不做上传——schema 里没有实测过的上传路径。想给角色做锚点图，
可以先用本包出一张角色设定图，再把它返回的 `image_url` 当锚点。

### 一致性闸门**不替你补词**

闸门逐字核对每格的提示词，报出「第几格 · 哪个角色 · 漏了哪个词」：

```
  ✗ chen       出场  3 格，特征词 5 条，漏词的格：3
     !! 第 3 格 · 陈默（chen）漏了特征词「左眉尾一道浅疤」
  结论：不通过（漏词如上）
```

为什么不自动把特征词拼进去？因为那样闸门永远是绿的——**假绿闸门比没有闸门更危险**。
漏了就是漏了：重跑 `shots`，或手改分镜表里那一格的 `prompt` 再重出这一格。

`--min-palette-ratio` 管配色漂移，默认 `0`（**只报告不拦**），因为配色是风格软约束。

## 七道硬闸门

闸门都**拦截**（不是警告），因为出图按次扣费，一致性崩了要整批重画：

1. **合规** —— 广告法违禁词；「最X」有**可枚举的上下文豁免**，但**句首不豁免**
   （`最大的区别是…` 句首 → 拦；`这是两种走法最大的区别所在` → 放行）
2. **占位符残留** —— `{}` / `[待填]` / `XXX` / `（此处省略）`
3. **`prompt_echo`** —— 出图提示词照抄了提示词里的示例：
   去标点后相等、**Jaccard ≥ 0.75**、或**示例二元组覆盖度 ≥ 0.60**，三条任一命中即拦
   （第三条是补漏：提示词动辄 60~140 字而示例只有 25 字，Jaccard 会被长度差摊薄）
4. **比例真伪** —— 读**图片文件真实像素**，不信接口自报；容差 3%；
   `--snap-exact` 裁到像素级精确（实测 3:4 → 864x1184 裁到 864x1152，偏差 0.0000%）
5. **分镜结构** —— 每格必须有景别（枚举：大远景/远景/全景/中景/中近景/近景/特写/大特写）
   + 画面描述；缺项标红；**格数为 0 → 拦**
6. **角色一致性** —— 设定卡里的特征词必须都出现；漏了就报出是哪一格漏了哪个词
7. **成本上限 + 产出位置** —— 超 `--budget` 不提交；`--outdir` 落在包内 → 退出码 2

## 成本

| 项 | 实测 |
|---|---|
| `nano_banana` 1K 出图 | **24 点/张** = 0.24 元 |
| 充值 | 1 元 = 100 点 |
| 提交时冻结 | 实测 `frozen_points = 31.2`（**预冻结，不是最终扣费**） |
| 完成后结算 | `usage.points_cost = 24` |
| 2K / 4K · 其它模型 | **没有实测价 → 拒绝估算（退出码 3）**，要估就给 `--points-per-image` |

**只信任务返回的 `usage.points_cost`。** 平台的 `pricing_matrix` / `tenant_*` / `fixed_price`
字段我们验证过半数不可信（`image_human` 写 1.5/2/4/8 点/秒、实测 2/3/6/12）。
schema 的 `api_doc` 里列了官方模型的文档价，但**那是文档价，不是我们实扣的数**。

## 断点续跑

出图中断后原样重跑即可。断点 key 含**八维**：格号 + 提示词全文摘要 + 比例 + resolution +
模型 + action + 角色设定卡摘要 + 参考图摘要——**改任一维都重出重扣**（输入变了就该重画）：

```
[1/2] #1 已完成，跳过（上次扣费 24.0 点，不再重复扣）
[2/2] #2 发现未完成的 task_id=task_xxx，续查而不重新提交
```

断点里的提示词取的是**全文摘要**，不是前 N 个字符：同族包按 `prompt[:24]` 取 key 的那一版，
提示词只改第 25 字之后就**静默复用旧图**了——那比多扣一次费危险得多。

改了 `--snap` / `--snap-exact` 口径不会重复扣费：原始下载文件还在，
脚本会**本地重裁**（零成本）；旧版断点里没存原始文件时会**明确警告**"无法本地重裁"。

## 拼页：图上不带字

```bash
# 条漫：单列竖排，一页 4 格
python3 scripts/run.py sheet --shots shots.json --state ./out/storyboard-state.json \
    --outdir ./pages --layout strip --rows 4 --panel-w 620

# 页漫：2 列 x 2 行
python3 scripts/run.py sheet --shots shots.json --state ./out/storyboard-state.json \
    --outdir ./pages --layout grid --cols 2 --rows 2 --panel-w 580 --panel-h 620 --fit contain
```

产出 `page-01.png`、`page-02.png`… 与 `dialogue.md`（逐格对白/旁白清单）。
每页的真实像素会**读回复核**，不信自己写的尺寸变量。

**为什么不把对白烧进图里**：零依赖做不了字体栅格化（标准库没有字库解析与字形光栅化），
而且 AI 出图的文字基本都是错的——实测提示词里写了"不要文字"，门上还是长出了
`TIME REPAIR` 和镜像的 `OPENING`。所以口径是**图不带字，字另外给**，
交给后期或设计工具加字。这是明确的设计取舍，不是遗漏。

## 图片放哪里

**必须放在 Skill 包外**（默认 `%TEMP%\storyboard-images`）。包只收文本文件，
图片会让上传 400——脚本也会拒绝把 `--outdir` 指到包内（退出码 2）。

## 文档

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 完整操作文档（子命令、参数、七道闸门、排错、退出码） |
| `references/storyboard-method.md` | 分镜方法：景别/机位/格与页/节奏/比例规范 |
| `references/character-consistency.md` | 角色一致性与画风：设定卡写法、硬约束提示词、参考图用法与实测边界 |
| `references/cost-and-troubleshooting.md` | 计费口径、实测数据、排错与对账 |

## 脚本

| 文件 | 说明 |
|---|---|
| `scripts/run.py` | 八个子命令 + 七道闸门 + 断点续跑 + 本地拼页 |
| `scripts/imgprobe.py` | 图片头探针：读 PNG/JPEG/GIF/WebP 真实像素（只读，纯标准库） |
| `scripts/a7w.py` | 共用零依赖客户端，**逐字节等于规范版，本包不改动** |

## 更新记录

| 版本 | 变更 |
|---|---|
| 1.0.0 | 首个版本：角色设定卡 → 分镜表 → 逐格出图（含参考图传递）→ 跨格一致性自检 → 本地拼页；七道硬闸门；断点 key 八维；`--snap-exact` 像素级裁准。 |

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
