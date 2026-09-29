#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 课件配图与排版（sanjianke-slide-kit）。

把一份**讲义 / 大纲**变成**能用的课件**：

    outline  →   pages    →   images    →   render
    分页方案     每页内容      按页配图      本地排版成逐页 PNG
    （页标题/     成稿要点/     真花钱·先报价·  （+ 讲稿备注 + 可选 HTML）
      配图意图）   讲稿备注      断点续跑       零成本·零网络·需要 PIL

子命令
    outline  读讲义 → 分页方案（每页 kind / 标题 / 粗要点 / 备注草稿 / 配图意图）只花文本钱
    pages    把骨架展开成**成稿**（每页 1~6 条要点 + 80~400 字讲稿备注）只花文本钱
    images   按页出配图（真花钱，跑之前先报价并要求 --yes / --budget）
    render   本地排版成**逐页 PNG** + `notes.md` + 可选 `deck.html`（零成本、零网络，需要 PIL）
    all      串起 outline → pages → images → render，断点续跑
    cost     只算钱，一次调用都不发
    models   列出 api.a7w.cn 在架的模型与应用（免费）

真实请求的端点（都在 api.a7w.cn 上）
    大模型       POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    在架模型     GET  https://api.a7w.cn/api/v1/models
    出图（异步） POST https://api.a7w.cn/api/v1/apps/nano_banana/submit
    任务轮询     GET  https://api.a7w.cn/api/v1/tasks/<task_id>

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py models --key sk-xxxx
    export A7W_API_KEY=sk-xxxx      # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

本包与同族 L2 各包的边界（**改代码前先读这一段**）
    · `sanjianke-course-outline` 的输入是主题，产出是**纯文本三件套**（大纲 / 讲义 / 习题）。
      它的最小单位是「节」，一节 1500~3000 字散文，**不出课件、没有分页、没有版式**。
    · `sanjianke-image-factory` 的输入是一篇文章稿，产出是文章各段的**配图**。
      它的最小单位是「图」，图上的文字交给模型画进画面。
    · `sanjianke-cover-factory` 的输入是一批标题，产出是**同一个标题 × N 平台的封面**。
      它的最小单位是「封面」= 一张图 + 一行大字，**没有页序、没有多页概念、没有讲稿备注**。
    · 本包的输入是**一份讲义**，产出是**一份课件**：它的最小单位是**「页」**——
      一页 = 页型 + 标题 + 若干要点 + 讲稿备注 + 配图意图，**多页按页序组成 deck**，
      并且由**本地排版引擎**把「页」画成逐页 PNG（版心 / 换行 / 溢出判定全部本地可控）。
      同族三个包都**没有**「页」这个数据结构，也都没有多页版式引擎。
      核心那一段是「讲义 → 分页 → 每页要点提炼 → 配图 → 本地排版 → 讲稿备注」，
      与「给讲义配图」不是一回事：配图只是这条链路里的一步，且**图本身不含任何文字**。

八道本地硬闸门（都是**拦截**：标红 + stderr 汇总 + 退出码非 0，不是"提示一下"）
    1. 合规          广告法违禁词 + **教育类效果承诺**（保过 / 包学会 / 保证提分）；
                     「最X」有可枚举的上下文豁免，**句首不许误豁免**
    2. 占位符残留    `{}`、`[待填]`、`XXX`、`（此处省略）`、`TODO`/`TBD`
    3. prompt_echo   去标点相等 / 二元组 Jaccard ≥ 0.75 / **示例覆盖度 ≥ 0.60**
    4. 出图比例真伪  读**真实像素**，不许信接口自报；容差 3%（地板 0.25%），`--snap` 裁准
    5. 每页内容完整性 每页必须有**标题 + 至少 1 条要点**；空页 → 拦；**页数为 0 → 拦**
    6. 文字溢出      本地排版时版心放不下 → **拦截并报出实际像素与可用像素**，
                     **绝不静默截断**（同族 `xhs-note-factory` 因静默截断被修过）
    7. 成本上限      出图前必须先报价，超 `--budget` 停；2K/4K 无实测价 → **拒绝估算**
    8. `--outdir`    落在包内 → exit=2（产出图 / 课件不许进包，包内白名单只收文本）

设计取舍
    · 闸门判定全部在本地做**确定性**判定，不采信模型自评（"我检查过了"不算数）。
    · 页内容闸门**在花钱之前**就判（`images` 也判）：页面缺要点、文字太长就别出图，
      免得钱花了才发现这一页根本不能用。
    · **配图提示词里不许出现任何文字**（图上的字由本地渲染压上去），
      所以不给模型写错字的机会；这条在 `image_intent` 的闸门里会明确提示。
    · `render` 是**全有或全无**：任一页不合格就**一张 slide 都不写**，
      并在 stderr 逐条列出原因 —— 半套课件比没有课件更容易被误用。
    · 文本成本：网关不公布文本模型的单价（pricing 表不含文本模型、models 无价格字段、
      usage 无 points_cost），所以金额只能给**估算口径**（`--yuan-per-ktok`，默认 0.02
      元/千 token），输出里一律标成"估算"，**账单以 api.a7w.cn 控制台为准**。
    · 出图成本用**实测价**：nano_banana 1K = 24 点/张（1 元 = 100 点）。2K/4K 没实测过，
      **拒绝估算**（exit=3），除非用户自己用 `--points-per-image` 给单价。
    · 排版是本地渲染：**有 PIL 就用 PIL**；没有 PIL 就**明确报降级（exit=2）并说明**，
      绝不静默产出一份没有版式的"课件"，也绝不假装成功。
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# ⚠️ **不要往包内写 .pyc**。
#    `import a7w` / `import imgprobe` 会在 `scripts/__pycache__/` 下生成 `.pyc`，
#    而 Skill 包的上传白名单只收 `.md .py .txt .json .sh .js .yaml .yml .csv`——
#    多出来的 `.pyc` 会让上传 400。这事很阴：**只要跑过一次工具，包里就脏了**，
#    而用户完全不会意识到是自己"跑了一下"造成的。
#    所以在导入这两个模块**之前**关掉字节码写入。
sys.dont_write_bytecode = True
import a7w        # noqa: E402  ← 共用零依赖客户端；**逐字节等于规范版，本包不改它**
import imgprobe   # noqa: E402  ← 本包自己的图片头探针（读真实像素），独立模块

# 控制台统一按 UTF-8 输出，避免 Windows 代码页把中文和 emoji 打成乱码
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"       # 实测可用（会路由到 deepseek-flash）
CHAT_RETRIES = 4
STATE_NAME = "slide-kit-state.json"
DECK_NAME = "deck.json"
DECK_MD_NAME = "deck.md"
AUDIT_NAME = "AUDIT.md"
NOTES_NAME = "notes.md"
HTML_NAME = "deck.html"
IMAGES_SUBDIR = "images"
SLIDES_SUBDIR = "slides"
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# nano_banana 出图应用相关（本包业务，**放在这里而不是 a7w.py**）
#
# 【约定】`scripts/a7w.py` 是所有 Skill 包共用的零依赖客户端，我们靠
# 「包内副本 SHA256 == 规范版」批量校验 60+ 个包有没有被改坏。
# 所以**任何包都不许为了自己的业务往 a7w.py 里加东西**：
#   · 需要读图片像素     → 独立模块 `imgprobe.py`（已独立）
#   · 需要应用专属的接口 → 就写在下面这一段里
#
# 请求体字段用 `python scripts/a7w.py schema nano_banana` **现查**过，不要凭记忆加字段：
#   prompt / action / model / image_urls / resolution / aspect_ratio / callback_url
#
# 平台文档写的是 `data.result.status`，**实测不对**：status 在 `data` 顶层。
# 照文档写会永远读不到状态、一路轮询到超时，所以这里按实测结构取。
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"                   # 出图应用编码
API_SUBMIT = "submit"                       # POST /api/v1/apps/nano_banana/submit
TASK_URL = a7w.HOST + "/api/v1/tasks/{}"    # GET  /api/v1/tasks/<task_id>（统一任务查询，实际用它）

RESOLUTIONS = ("1K", "2K", "4K")
ASPECT_RATIOS = ("auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                 "5:4", "4:5", "21:9")
ACTIONS = ("generate", "edit")
POINTS_PER_IMAGE_1K = 24.0                  # 实测：nano_banana 1K = 24 点/张
POINTS_PER_YUAN = 100                       # 算力集市的充值比例：1 元 = 100 点
UNTESTED_RESOLUTIONS = ("2K", "4K")
POLL_TIMEOUT_DEFAULT = 600

# 文本成本**估算**口径（网关不公布文本单价，只是估算，不是账单）
YUAN_PER_KTOK_DEFAULT = 0.02

# ===========================================================================
# 课件版式规格（`specs` 语义内建在 render 里，**零网络**）
# ===========================================================================
#
# 画布 / 版心 / 字号 / 上限四者是**互相咬合**的，改一个要复核另外三个：
#   BULLET_MAX_CHARS = 按 body 字号在可用宽度里放得下的字数（见 `check_page_fit()`）
#   超出上限就拦截，而不是缩小字号硬塞 —— 同族 `xhs-note-factory`
#   刚因为「静默截断」被修过，本包连"静默缩到看不清"也不做。
#
# 版心（safe）是相对宽高的比例：
#   上边界避开课程 LOGO / 角标，下边界避开页码与录制水印，左右避开投影裁边。
# ---------------------------------------------------------------------------

DECK_RATIO = "16:9"
DECK_GEN_RATIO = "16:9"
DECK_TARGET_PX = (1920, 1080)

SAFE = {"top": 0.070, "bottom": 0.086, "left": 0.054, "right": 0.054}

# 字号（像素，按 1920x1080 画布）
COVER_TITLE_SIZE = 92
COVER_BODY_SIZE = 40
CONTENT_TITLE_SIZE = 62
CONTENT_BODY_SIZE = 42
FOOTER_SIZE = 24

TITLE_MAX_LINES = 2                 # 页标题最多两行
BULLET_MAX_ITEMS = 6                # 每页最多 6 条要点
BULLET_MAX_CHARS = 48               # 单条要点字数上限（渲染前还会按真实字体复核）
TITLE_MAX_CHARS = 30                # 页标题字数上限
NOTES_MIN_CHARS = 40                # 讲稿备注建议下限（低于它只告警，不拦）
NOTES_MAX_CHARS = 400
IMAGE_INTENT_MAX_CHARS = 200
SOURCE_MAX_CHARS = 24000            # 讲义原文上限；超了**报错**，绝不静默截断

PAGE_KINDS = ("cover", "section", "content", "summary")
CENTERED_KINDS = ("cover", "section", "summary")   # 居中版式（配图铺满 + 压暗）
DEFAULT_PAGE_KIND = "content"

# 出图比例 → 期望的数值比例（闸门四用；`auto` 不判）
MEASURED_1K_PIXELS = {              # 上游实测像素（1K 档，留作文档与排错依据）
    "1:1": [1024, 1024], "3:4": [864, 1184], "4:3": [1184, 864],
    "16:9": [1344, 768], "9:16": [768, 1344], "21:9": [1536, 672],
    "2:3": [832, 1248], "3:2": [1248, 832], "4:5": [896, 1152],
    "5:4": [1152, 896],
}

# ===========================================================================
# 闸门一：合规（广告法 + 教育类效果承诺）
# ===========================================================================
#
# 【「最X」的豁免：口径照抄同族模板，一处不改】
#   命中之后再看一眼**后续几个字**：如果接的是比较 / 程度 / 常见这类用法，
#   那它是"普通中文词"而不是"最高级广告语"，放行。
#   实测依据（继承课程 / 长文 / 封面三条产线）：真机连跑 4 次讲义，1 次被拦，拦下的是
#     「做菜和剪辑**最大**的共同点是：先做减法，再做加法」
#   这是讲义里在讲一件常识，不是给商品贴"最大"的标签。所以加一层上下文豁免，
#   但**豁免范围写死在代码里、可枚举、可复核**，不是一句"人工判断"了事。
#
#   ⚠️ **句首不许误豁免**：只在命中处**不是行首/句首**时才豁免，
#      因为"最大的区别是……"这种**句首**写法经常正是标题式的最高级宣称。
#      ——课件页标题几乎全在句首，所以这条对本包比对同族更关键。
#
#   ⚠️ **教育类效果承诺没有任何豁免**（本包新增的一档）：
#      知识付费 / 培训类课件最常见的违规不是"最"字，是**效果承诺**。
#      广告法明确禁止教育、培训广告对升学、通过考试、获得学位学历或合格证书
#      作保证性承诺，所以 保过 / 包过 / 包学会 / 保证提分 / 保就业 / 包分配 全部高风险拦截。
#
#   ⚠️ **豁免只允许一个「的」**，与同族模板逐字一致；不给逗号 / 顿号开豁免
#      （开了就等于给最高级广告语留后门：标点后面跟什么都行）。
# ---------------------------------------------------------------------------

BANNED_PATTERNS = [
    (r"国家级|世界级|最高级|最佳|最优|最强|第一品牌|全国第一|排名第一|销量第一", "高",
     "广告法第九条绝对化用语，课件正文与提示词都不许带"),
    (r"最[好棒优佳强低价]|最便宜|最先进|最领先|顶级|极品|绝无仅有|独一无二", "高",
     "绝对化用语，无法举证"),
    (r"100%|百分之百|百分百|全网最低|绝对(有效|安全|可靠|不会)", "高",
     "绝对化承诺，属虚假宣传高风险表述"),
    # ⚠️ 教育 / 培训专有的一档：效果承诺。**没有任何豁免**。
    (r"保过|包过|包学会|保证学会|保(证)?提分|提分保证|保就业|包分配|包拿证|保(证)?通过|"
     r"保(证)?上岸|一次通过|不过退款", "高",
     "教育 / 培训广告不得对通过考试、获得证书作保证性承诺（广告法第二十四条）"),
    (r"国家(认证|认可|免检)|央视(推荐|上榜)|官方(推荐|指定)|权威认证", "高",
     "虚构权威背书"),
    # ⚠️ **真机实测抓到的误伤（本包上线前跑出来的，不是想出来的）**：
    #    原来这条里是裸的 `特效`，于是「很多人以为剪辑是学**特效**、学转场」与
    #    「一上手就拖转场**特效**」被当成医疗功效宣称拦下——在影视 / 剪辑语境里
    #    `特效` 就是 VFX，是这个行业绕不开的常用词。
    #    处理口径与同族修 `唯一` 那次完全一样：**把裸词收紧成可枚举的搭配**。
    #    医疗意义上的「特效」在中文里几乎总是带着后缀（特效药 / 特效疗法 / 特效配方），
    #    裸的「特效"不构成任何可举证的疗效宣称。
    (r"根治|治愈|药到病除|包治|特效(药|疗法|配方|偏方|治疗|作用|成分|功效)|无副作用|抗癌|"
     r"降(血压|血糖|血脂)", "高",
     "医疗功效宣称，普通内容不得使用（裸的「特效」已按 VFX 语境豁免，见代码注释）"),
    (r"稳赚|保本|保收益|零风险|躺赚|日入过万|月入百万", "高",
     "投资 / 收益承诺，金融敏感表述"),
    # ⚠️ 同族踩过的坑：这条排他性规则原来写成裸的 `唯一`，真机跑习题时模型写了
    #    「判断一段画面是不是废片，**唯一标准**是画面够不够清晰稳定（答案：错）」——
    #    这是把"唯一"当普通词用，属于必然误伤，所以收紧成可枚举的搭配。
    (r"首[个创]|独家|唯一(选择|指定|授权|官方|认证|品牌|推荐|渠道|合作)|填充空白", "中",
     "排他性表述，需有可举证依据"),
    (r"免费领|免费送|0\s*元购|白送|扫码(加|进|领)|加微信|私信我|vx|VX", "中",
     "诱导分享或站外导流，平台普遍限制"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与真实活动一致"),
    (r"纯天然|无添加|零添加|无毒无害", "中", "成分 / 材质宣称需与检测报告一致"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "低", "标题党式诱导"),
]
BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# ⚠️ 同族踩过的坑：原来那条排他性规则写成裸的 `唯一`，真机跑习题时模型在题干里写了
# 「判断一段画面是不是废片，**唯一标准**是画面够不够清晰稳定（答案：错）」——
# 这是把"唯一"当普通词用，属于必然误伤，已收紧为可枚举的搭配
# `唯一(选择|指定|授权|官方|认证|品牌|推荐|渠道|合作)`（已直接写进 BANNED_PATTERNS）。
# 于是「唯一标准」「唯一目的」这类普通用法天然不命中，不需要再写豁免代码。

SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥",
)
SUPERLATIVE_OK_RE = re.compile(
    r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")

# 句首判定：命中处前面只有空白，或前一个非空白字符是句末标点 / 换行 → 视为句首。
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")


def _superlative_is_normal_usage(text, m):
    """「最…」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：
      1. 后文落在可枚举的豁免表里（SUPERLATIVE_OK_AFTER）
      2. 命中处**不在句首** —— 句首的「最大的区别是…」是标题式最高级宣称，照拦
    """
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


def compliance_scan(text):
    """扫一遍违禁词，返回命中列表（可能为空），按风险等级排序。

    同一个词可能在文中出现多次（一次是广告语、一次是普通用法），
    所以命中判定按**每一处出现**做，任一处未被豁免就算命中。
    """
    hits, seen = [], set()
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m):
                continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                continue
            seen.add(key)
            hits.append({"word": word, "level": lvl, "why": why})
            break
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits


# ===========================================================================
# 闸门二：占位符残留
# ===========================================================================
#
# 分页方案是模型吐的 JSON，模板没替换干净的形态与同族一致：
#   · `{}` / `{{标题}}`        JSON 骨架被当正文写进去了
#   · `[待填]` / `[待补充]`    模型给自己留的空档
#   · `XXX` / `xxx`            忘了替换的占位
#   · `（此处省略）`           模型懒得写，直接省略
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    (re.compile(r"\{\{?\s*[\u4e00-\u9fffA-Za-z0-9_]*\s*\}?\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【(（]\s*(待填|填空|待补充|待完善|待定)\s*[\]】)）]"), "[]",
     "残留了占位符 `[待填]`，模型给自己留的空档没补"),
    (re.compile(r"[\[【]\s*(略|此处省略)\s*[\]】]"), "[]",
     "残留了「此处省略」类占位"),
    (re.compile(r"[(（]\s*此处省略[^)）]{0,12}[)）]"), "（此处省略）",
     "残留了「（此处省略）」——模型把该写的内容省略了"),
    (re.compile(r"(?<![A-Za-z0-9])X{3,}(?![A-Za-z0-9])"), "XXX",
     "残留了占位符 `XXX`，忘了替换"),
    (re.compile(r"待补充|待完善|后续补充|此处略|TODO|TBD"), "待补充",
     "残留了「待补充」类字样，内容没写完"),
]


def placeholder_hits(text):
    hits = []
    for rx, tag, why in PLACEHOLDER_PATTERNS:
        m = rx.search(text or "")
        if m:
            hits.append({"tag": tag, "word": m.group(0), "why": why})
    return hits


# ===========================================================================
# 闸门三：prompt_echo（照抄提示词示例）
# ===========================================================================
#
# 事故复盘（来自爆款标题工坊的实测）：提示词里写过的示例，
# 哪怕明确标着「这是错的写法」，模型照样照抄——公众号那一轮最高分 89.0 的标题
# **一字不差就是提示词里的示例**。最高分变成「抄标准答案」，排序就废了。
#
# 本包的形态是：示例页标题 / 示例配图意图被照抄 → 整份课件变成"把示例换个主题词"，
# 看起来完全正常，直到你发现它是模板填空题。而课件是**要拿去上课的**，
# 一页一页的模板填空比一份模板文件更贵（浪费的是学员的时间）。
#
# 判定：去标点后相等 → 命中；字符二元组 Jaccard ≥ 0.75 → 命中；
#       示例的二元组覆盖度 ≥ 0.60 → 命中（第三条，见下）。
#
# 【为什么还要第三条】同族实测抓到一个设计缺陷：Jaccard 在两个长度差几十倍的对象
# 之间会被**稀释**。把一条 40 字的示例原样塞进一份 2400 字的产出：
#   2400 字产出里夹带 40 字示例 → Jaccard 0.171（旧判据放行 ❌）、覆盖度 1.000（新判据拦下 ✓）
# 覆盖度只看"示例被抄了多少"，不看产出有多长，长文夹带照抄躲不过去。
#
# 阈值 0.75 的标定依据（同族实测）：逐字照抄 1.000 / 只改标点 1.000 / 少两个字 0.840 /
# 加一个尾巴 0.857 / 同构照抄 0.778 / 英文示例近亲 0.766 —— 全部拦；
# 而真实业务产出只有 0.042 / 0.000 —— 放行。17 倍以上安全距离。
#
# 长度守卫是**相对**的：max(6, len(示例)//2)，短串不比（二元组集合太小、指标虚高）。
# ---------------------------------------------------------------------------

ECHO_MIN_LEN_FLOOR = 6
ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60

# 提示词里出现过的示例文本。**新增示例必须登记到这里。**
# 全部是「跨主题」的假例子：正常课件不会讲社区团购 / 机械制图 / 架子鼓坐姿，
# 所以它们出现在真实产出里 = 照抄。
PROMPT_SAMPLES = [
    "社区团购的选品清单怎么定",
    "机械制图里停机点的标注顺序",
    "架子鼓坐姿的三个支点与常见误区",
    "清晨的木质案板上摊开一张手写清单，侧逆光，浅景深纪实摄影，画面里没有任何文字",
    "先讲一个反直觉的现象，再抛出本节要解决的问题，最后给出判断标准",
]


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。"""
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_for_echo(sample)) // 2)


def _norm_for_echo(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _bigrams(s):
    s = _norm_for_echo(s)
    if len(s) < 2:
        return set(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _similarity(a, b):
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(len(ba | bb))


def prompt_echo(prompt, samples=None):
    """文本是否与登记过的示例「抄得太近」。

    三条命中路径（任一即命中）：
      · 去标点后**完全相同**（最直接的照抄）
      · 字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
      · 示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（把示例夹带进更长的产出里；
        Jaccard 会被长度摊薄，只有覆盖度抓得住）

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。
    """
    target = _norm_for_echo(prompt)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        if target == _norm_for_echo(s):
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(prompt, s)
        base = _bigrams(s)
        contain = (len(_bigrams(prompt) & base) / float(len(base))) if base else 0.0
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule
    return False, best_score, best_sample, ""


def text_gate(text, where="内容"):
    """对一段课件文本跑三道本地检查（合规 / 占位符 / 照抄示例）。"""
    leaks = []
    for h in compliance_scan(text):
        leaks.append(("banned_word", "%s命中违禁词「%s」（%s 风险）：%s"
                      % (where, h["word"], h["level"], h["why"])))
    for h in placeholder_hits(text):
        leaks.append(("placeholder", "%s里%s" % (where, h["why"])))
    echoed, score, sample, rule = prompt_echo(text)
    if echoed:
        if rule == "contain":
            leaks.append(("prompt_echo",
                          "%s有 %.0f%% 的内容来自示例「%s」（覆盖度 ≥ %.2f 即判照抄／"
                          "同构改写；Jaccard 会随文本变长被摊薄）"
                          % (where, score * 100, sample[:28], ECHO_CONTAIN)))
        else:
            leaks.append(("prompt_echo",
                          "%s与示例「%s」相似度 %.2f，属照抄/同构改写"
                          "（模型会锚定提示词里的示例）" % (where, sample[:28], score)))
    return leaks


# ===========================================================================
# 闸门四：比例真伪（读真实像素，不信自报值）
# ===========================================================================
#
# 事故来源：标题工坊上一版只信模型自报的 `formula` 字段做模板污染判定，
# 结果那个真该被判命的标题恰好漏判——闸门是**假绿**的。
# 同一个错误在出图场景的形态是：接口 / 模型自报 `aspect_ratio=16:9`，
# 但真实像素是 1024x1024。只信自报值 → 用户拿去投影才发现版式全错。
#
# ⚠️ 实测到的上游特性（必须写进文档，否则闸门天天误报）：
#   上游不是按比例给像素，而是先定总像素、再把每边向下取整到 32 的倍数。
#   所以 10 种比例里有 5 种给不出像素级精确比例：
#       请求 3:4  → 864x1184   = 0.7297（3:4 = 0.75）  偏差 2.7%
#       请求 16:9 → 1344x768   = 1.7500（16:9 = 1.778）偏差 1.6%
#       请求 9:16 → 768x1344   = 0.5714（9:16 = 0.5625）偏差 1.6%
#       请求 21:9 → 1536x672   = 2.2857（21:9 = 2.333）偏差 2.0%
#       请求 4:5  → 896x1152   = 0.7778（4:5 = 0.8）    偏差 2.8%
#   精确的 5 种：1:1 / 4:3 / 2:3 / 3:2（还有非整比的 auto）
#   这**不是**网关 bug，是扩散模型按 32 对齐的常规做法。但它意味着
#   「请求比例 == 产出比例」这个断言对一半的比例天然不成立。
#
# 处理方式（三条一起用，缺一条闸门就会变成天天误报的噪音）：
#   a) 默认容差 3%：容差内不算「假」，但会**明确打印真实像素与偏差**，不藏
#   b) 超过容差 → 标红 + 计入闸门失败 + 退出码 3
#   c) `--snap`：出图后按**请求比例**精确裁掉多余像素，让产出真的等于请求比例
# ---------------------------------------------------------------------------

RATIO_TOLERANCE = 0.03        # 默认 3%（实测最大偏差 2.9%）
# 容差地板：**像素只能是整数**，所以「裁到精确比例」本身就有量化误差。
# 实测（--snap 之后复核）：16:9 裁后偏差 0.0925%；相邻整数像素间隔约 0.27%。
# 0.0025 是保守地板，仍能抓住真错：请求 16:9 却给 4:3 的偏差是 25%，比地板大 100 倍。
RATIO_TOLERANCE_FLOOR = 0.0025

parse_ratio = imgprobe.parse_ratio
ratio_label = imgprobe.ratio_label


def check_ratio(path, want_ratio, tolerance=None):
    """闸门四：读真实像素，判是否等于请求比例。

    返回 dict（`ok` 为闸门结论）：
        real_px / real_label / real_ratio / want_ratio / deviation / ok
    """
    tol = RATIO_TOLERANCE if tolerance is None else float(tolerance)
    clamped = max(tol, RATIO_TOLERANCE_FLOOR)
    rec_floor = clamped > tol
    w, h, fmt = imgprobe.image_size(path)
    want = parse_ratio(want_ratio)
    rec = {"file": str(path), "format": fmt, "want_ratio": want_ratio,
           "want_value": want, "real_px": [w, h],
           "real_label": (ratio_label(w, h) if w and h else "?"),
           "real_ratio": (w / float(h)) if (w and h) else None,
           "deviation": None, "tolerance": clamped, "floor": rec_floor,
           # 这一档上游**实测**会给的像素 —— 写进记录，排错时不用翻文档
           "expected_1k_px": MEASURED_1K_PIXELS.get(str(want_ratio)),
           "ok": False, "why": ""}
    if want is None:
        rec["ok"] = True
        rec["why"] = "比例 `%s` 不是可判定的比例（auto / 解析不了），跳过真伪判定" % want_ratio
        return rec
    if not w or not h:
        rec["why"] = ("读不出真实像素（文件头不是 png/jpeg/gif/webp，或文件损坏）—— "
                      "**不许信接口自报的 aspect_ratio**，这条判为不合格")
        return rec
    dev = abs(rec["real_ratio"] - want) / want
    rec["deviation"] = dev
    exp = rec["expected_1k_px"]
    exp_txt = ("（这一档上游 1K 实测给的是 %dx%d）" % (exp[0], exp[1])) if exp else ""
    if dev <= clamped:
        rec["ok"] = True
        rec["why"] = ("真实像素 %dx%d（%s）= %.4f，请求 %s = %.4f，偏差 %.2f%%（容差 %.2f%%）%s"
                      % (w, h, rec["real_label"], rec["real_ratio"], want_ratio, want,
                         dev * 100, clamped * 100, exp_txt))
        if rec_floor:
            rec["why"] += "；容差被抬到地板 %.3f%%（整数像素的量化误差）" % (clamped * 100)
    else:
        rec["why"] = ("真实像素 %dx%d（%s）= %.4f，与请求的 %s = %.4f 偏差 %.2f%%，"
                      "**超过容差 %.2f%%**%s —— 上游按 32 对齐，5/10 种比例给不出精确值，"
                      "用 `--snap` 让产出真的等于请求比例"
                      % (w, h, rec["real_label"], rec["real_ratio"], want_ratio, want,
                         dev * 100, clamped * 100, exp_txt))
    return rec


# ===========================================================================
# 字体与排版量算（本地渲染，零网络）
# ===========================================================================
#
# 字体只从**系统字体**里找（不下载、不打包字体文件 —— 字体有授权问题，
# 包内也不许有字体这种二进制资源）。找不到就报降级，不静默出一份没版式的课件。
# ---------------------------------------------------------------------------

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",     # 微软雅黑 Bold（Windows 首选）
    r"C:\Windows\Fonts\msyh.ttc",       # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\Deng.ttf",       # 等线 Bold
    r"C:\Windows\Fonts\simsun.ttc",     # 宋体（兜底）
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
)

# 版式参数变了必须重新渲染。**dead parameter 警告**：任何影响产出的参数
# 都要么进 `render_state_key`，要么就别加进命令行（同族踩过"死参数 → 静默复用旧产物"）。
#
# ⚠️ **改了任何画法（字号 / 间距 / 对齐 / 配色 / 分区），必须把这个数字 +1**，
#    否则断点续跑会把改之前渲染的旧 slide 当成"已渲染"直接复用，
#    你会以为改了、其实图还是旧的 —— 这正是同族"死参数"事故的形态。
#    v2：居中版式的要点块改为"整块居中 + 块内左对齐、标记点对齐成一列"；
#        修掉页脚页码被局部变量覆盖的 bug（曾画出「1 / 326」）。
LAYOUT_VERSION = 2

# 主题（配色）。背景 / 标题 / 正文 / 强调 / 压暗层。
THEMES = {
    "ink": {"name": "墨白（浅底深字，默认）",
            "bg": (250, 250, 248), "title": (22, 26, 34), "body": (62, 68, 80),
            "accent": (205, 74, 54), "rule": (222, 224, 228), "scrim": (8, 10, 14),
            "on_image_title": (255, 255, 255), "on_image_body": (236, 238, 242),
            "panel": (255, 255, 255)},
    "night": {"name": "夜讲（深底浅字，适合录屏）",
              "bg": (18, 20, 26), "title": (246, 247, 250), "body": (204, 210, 222),
              "accent": (255, 140, 88), "rule": (52, 56, 66), "scrim": (0, 0, 0),
              "on_image_title": (255, 255, 255), "on_image_body": (238, 240, 244),
              "panel": (26, 29, 36)},
    "warm": {"name": "暖讲（米底暖字，适合知识付费）",
             "bg": (253, 247, 240), "title": (58, 40, 28), "body": (104, 80, 62),
             "accent": (190, 88, 42), "rule": (236, 222, 208), "scrim": (28, 16, 8),
             "on_image_title": (255, 250, 244), "on_image_body": (246, 236, 226),
             "panel": (255, 252, 247)},
}
THEME_CHOICES = tuple(THEMES.keys())

_FONT_CACHE = {}


def has_pil():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def find_font(explicit=None):
    """找一个能渲染中文的系统字体。返回 (路径, 候选表)；找不到返回 (None, 表)。"""
    if explicit:
        return (explicit if Path(explicit).is_file() else None), list(FONT_CANDIDATES)
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return p, list(FONT_CANDIDATES)
    return None, list(FONT_CANDIDATES)


def load_font(path, size):
    from PIL import ImageFont
    key = (str(path), int(size))
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(path), int(size))
    return _FONT_CACHE[key]


def text_width(font, s):
    """量一段文字的真实像素宽。

    ⚠️ 两个坑都实测踩过（同族口径）：
      · `font.getbbox()` 在某些字形上会返回 `None`（PIL 未渲染时），
        `None[2]` 直接抛 `TypeError`；也可能返回 `(0,0,0,0)`（字体里没有这个字形）。
      · 老版本 PIL 没有 `getbbox`，只有 `getsize`。
    这里把三条路都兜住，取不到就返回 0（宁可判"窄"，也不要崩在渲染阶段）。
    """
    try:
        bb = font.getbbox(s)
        if bb:
            return max(0, bb[2] - bb[0])
    except Exception:
        pass
    try:
        return max(0, font.getsize(s)[0])
    except Exception:
        return 0


def glyph_height(font):
    """字形的实际高度（不带上/下行留白）。

    `font.getmetrics()` 给的是 `(ascent, descent)`，两者相加比字形本身高出一截
    （实测 76px 字：85+21=106，而字形只有 80）。用它当行距会让多行文字比排版框高，
    字就画到框外面去了 —— 所以行距与框高统一走这个函数。
    """
    try:
        bb = font.getbbox("字测国")
        if bb:
            return max(1, bb[3] - bb[1])
    except Exception:
        pass
    try:
        asc, desc = font.getmetrics()
        return max(1, asc + desc - max(4, (asc + desc) // 8))
    except Exception:
        return 1


def wrap_text(text, font, max_width):
    """按字符贪心断行（中文不需要词级断行），返回行列表。

    **不截断**：断不下的字符照样留在最后一行，由闸门去报"超了"。
    空文本返回 `[""]`（由调用方按"空内容"报错，不在这里静默吞掉）。
    """
    lines, cur = [], ""
    for ch in text or "":
        trial = cur + ch
        w = text_width(font, trial)
        if cur and w > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur or not lines:
        lines.append(cur)
    return lines


# ===========================================================================
# 版式：一页怎么摆（内容画之前的**确定性**排版计划）
# ===========================================================================

def safe_rect(width=None, height=None):
    """算版心（像素矩形）。不传宽高就按课件目标像素算。"""
    if width is None or height is None:
        width, height = DECK_TARGET_PX
    return {
        "left": int(round(width * SAFE["left"])),
        "right": int(round(width * (1.0 - SAFE["right"]))),
        "top": int(round(height * SAFE["top"])),
        "bottom": int(round(height * (1.0 - SAFE["bottom"]))),
    }


def image_box(has_image, width, height):
    """配图区（有图版式的右侧）。返回 (x0, y0, x1, y1) 或 None。"""
    if not has_image:
        return None
    safe = safe_rect(width, height)
    x0 = int(round(width * 0.545))
    return (x0, safe["top"], safe["right"], safe["bottom"])


def text_zone(has_image, kind, width, height):
    """文本区（x0, y0, x1, y1）。有图版式在左侧，无图版式占满但**限宽可读**。"""
    safe = safe_rect(width, height)
    if kind in CENTERED_KINDS:
        # 居中版式：整幅宽度，但上下留得更多（大字压在图中央）
        return (safe["left"] + int(width * 0.04), safe["top"] + int(height * 0.06),
                safe["right"] - int(width * 0.04), safe["bottom"] - int(height * 0.04))
    if has_image:
        return (safe["left"], safe["top"], int(round(width * 0.505)), safe["bottom"])
    # 无图版式：**限宽**到画布的 70%。实测教训：早期放到 82%（≈35 字/行）时，
    # 闸门六在无图版式下几乎**永远不可能触发**（6 条 × 48 字也只排 12 行，装得下）——
    # 一个打不响的闸门等于没有闸门。70% 既让版面读得动（≈30 字/行），
    # 也让"内容太多"这件事能在无图版式下如实暴露出来。
    x1 = min(safe["right"], safe["left"] + int(round(width * 0.70)))
    return (safe["left"], safe["top"], x1, safe["bottom"])


def page_text_of(page, key):
    """只从**一个入口**取页面文本字段。

    ⚠️ 同族实测踩过**最危险的那种 bug**：取文本读错字段 → 读到空串 →
    闸门全绿（长度 0 当然不超限）→ **静默产出一页什么都没有的课件，还报告成功**。
    教训是「静默截断」，这里是它的兄弟形态「静默留空」。所以取文本只有这一个入口。
    """
    v = (page or {}).get(key)
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if v is None:
        return ""
    return str(v)


def page_bullets(page):
    """取一页的要点列表（过滤空项）。"""
    b = page_text_of(page, "bullets")
    if isinstance(b, list):
        return b
    return [ln.strip() for ln in str(b).splitlines() if ln.strip()]


def plan_page(page, has_image, font_path, width=None, height=None, theme="ink"):
    """算一页的排版计划（不画图）。

    返回 dict：
        ok / why / kind / overflow[] / title_lines / bullet_lines / box 各区域
    `ok=False` 时 `why` 说明原因，`overflow` 逐条列出**超出的实际像素与可用像素**。
    """
    width = width or DECK_TARGET_PX[0]
    height = height or DECK_TARGET_PX[1]
    kind = page.get("kind") or DEFAULT_PAGE_KIND
    if kind not in PAGE_KINDS:
        kind = DEFAULT_PAGE_KIND
    centered = kind in CENTERED_KINDS
    tx0, ty0, tx1, ty1 = text_zone(has_image, kind, width, height)

    tsize = COVER_TITLE_SIZE if kind == "cover" else (
        CONTENT_TITLE_SIZE if kind == "content" else int(CONTENT_TITLE_SIZE * 1.15))
    bsize = COVER_BODY_SIZE if centered else CONTENT_BODY_SIZE
    title_font = load_font(font_path, tsize)
    body_font = load_font(font_path, bsize)

    title = page_text_of(page, "title").strip()
    bullets = page_bullets(page)
    rec = {"kind": kind, "centered": centered, "ok": True, "why": "", "overflow": [],
           "title": title, "title_size": tsize, "body_size": bsize,
           "title_lines": [], "bullet_lines": [], "box_title": None, "box_bullets": [],
           "zone": [tx0, ty0, tx1, ty1], "avail_w": tx1 - tx0, "avail_h": ty1 - ty0,
           "need_h": 0, "has_image": bool(has_image)}
    if not title:
        rec["ok"] = False
        rec["why"] = ("**这一页没有标题** —— 拒绝产出一页没有标题的课件"
                      "（闸门五：每页必须有标题 + 至少 1 条要点）")
        return rec
    if not bullets:
        rec["ok"] = False
        rec["why"] = ("**这一页一条要点都没有** —— 空页会被拦下"
                      "（闸门五：每页必须有标题 + 至少 1 条要点）")
        return rec

    avail_w = tx1 - tx0
    if not centered:
        avail_w = max(120, avail_w)

    title_lines = wrap_text(title, title_font, avail_w)
    t_lh = glyph_height(title_font) + 10
    if len(title_lines) > TITLE_MAX_LINES:
        rec["overflow"].append({
            "field": "title", "reason": "title_too_many_lines",
            "detail": "页标题「%s」在 %dpx 字号下断成 %d 行，超过上限 %d 行"
                      % (title, tsize, len(title_lines), TITLE_MAX_LINES),
            "actual": len(title_lines), "limit": TITLE_MAX_LINES})
    for i, ln in enumerate(title_lines):
        wpx = text_width(title_font, ln)
        if wpx > avail_w:
            rec["overflow"].append({
                "field": "title", "reason": "title_too_wide", "line": i + 1,
                "detail": "页标题第 %d 行「%s」实际 %dpx，可用 %dpx" % (i + 1, ln, wpx, avail_w),
                "actual": wpx, "limit": avail_w})

    marker_w = int(bsize * 1.15)
    b_wrap_w = max(120, avail_w - marker_w)
    bullet_lines, per_bullet = [], []
    for bi, b in enumerate(bullets):
        if len(b) > BULLET_MAX_CHARS:
            rec["overflow"].append({
                "field": "bullets", "reason": "bullet_too_long", "index": bi + 1,
                "detail": ("第 %d 条要点 %d 字，超过上限 %d 字（多出 %d 字：「%s」）"
                           % (bi + 1, len(b), BULLET_MAX_CHARS, len(b) - BULLET_MAX_CHARS,
                              b[BULLET_MAX_CHARS:]))
                + "。**不截断**——把这条拆成两条，或压缩到 %d 字以内" % BULLET_MAX_CHARS,
                "actual": len(b), "limit": BULLET_MAX_CHARS})
        lines = wrap_text(b, body_font, b_wrap_w)
        per_bullet.append(lines)
        bullet_lines.extend(lines)
    if len(bullets) > BULLET_MAX_ITEMS:
        rec["overflow"].append({
            "field": "bullets", "reason": "too_many_bullets",
            "detail": "这一页 %d 条要点，超过上限 %d 条" % (len(bullets), BULLET_MAX_ITEMS),
            "actual": len(bullets), "limit": BULLET_MAX_ITEMS})

    b_lh = glyph_height(body_font) + 14
    b_gap = int(bsize * 0.42)
    title_h = t_lh * len(title_lines)
    gap_title = int(tsize * 0.52) if not centered else int(tsize * 0.44)
    bullets_h = (b_lh * len(bullet_lines)) + (b_gap * max(0, len(bullets) - 1))
    need_h = title_h + gap_title + bullets_h
    rec["need_h"] = need_h
    if need_h > (ty1 - ty0):
        # 逐条定位：哪些要点把版心撑爆了（**报出实际像素，不静默截断**）
        detail = ("这一页标题 + 要点排下来需要 %dpx 高，版心只有 %dpx，"
                  "**放不下**（超出 %dpx）—— 减少要点条数 / 缩短要点，"
                  "**不做静默截断或自动缩字号**" % (need_h, ty1 - ty0, need_h - (ty1 - ty0)))
        rec["overflow"].append({
            "field": "block", "reason": "text_overflow",
            "detail": detail, "actual": need_h, "limit": ty1 - ty0,
            "title_lines": len(title_lines), "bullet_lines": len(bullet_lines)})

    y = ty0
    rec["box_title"] = (tx0, y, tx1, y + title_h)
    y += title_h + gap_title
    boxes = []
    for lines in per_bullet:
        h = b_lh * len(lines)
        boxes.append((tx0, y, tx1, y + h))
        y += h + b_gap
    rec["box_bullets"] = boxes
    rec["title_lines"] = title_lines
    rec["bullet_lines"] = bullet_lines
    rec["per_bullet_lines"] = per_bullet
    if rec["overflow"]:
        rec["ok"] = False
        rec["why"] = rec["overflow"][0]["detail"]
    return rec


# ===========================================================================
# 渲染（PIL 本地渲染；没有 PIL 就明确降级）
# ===========================================================================

def _cover_fit(im, bw, bh):
    """把图画成"填满目标框"（等比放大后居中裁掉多余的部分）。"""
    from PIL import Image
    iw, ih = im.size
    if iw <= 0 or ih <= 0:
        raise ValueError("底图尺寸非法：%sx%s" % (iw, ih))
    scale = max(bw / float(iw), bh / float(ih))
    nw, nh = max(bw, int(round(iw * scale))), max(bh, int(round(ih * scale)))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - bw) // 2, (nh - bh) // 2
    return im2.crop((left, top, left + bw, top + bh))


def _draw_wrapped(draw, lines, font, x, y, line_h, fill, shadow=False,
                  stroke_width=0, stroke_fill=None, center_x=None):
    """逐行画文本。`center_x` 给了就按它水平居中。"""
    for i, ln in enumerate(lines):
        if center_x is not None:
            w = text_width(font, ln)
            px = center_x - w // 2
        else:
            px = x
        py = y + i * line_h
        if shadow:
            draw.text((px + 2, py + 2), ln, font=font, fill=(0, 0, 0, 130),
                      stroke_width=stroke_width, stroke_fill=(0, 0, 0, 130))
        draw.text((px, py), ln, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill or (0, 0, 0))


def render_page(page, plan, dst, theme="ink", font_path=None, width=None,
                height=None, image_path=None, page_no=1, total=1, deck_title=""):
    """把一页画成 PNG。返回 dict（含真实输出像素，渲染后**复量一次**）。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return {"ok": False, "kind": "no_pil",
                "why": "没有 PIL：本地排版成逐页 PNG 需要 PIL（pip install pillow）。"
                       "**拒绝静默产出一份没有版式的课件**"}
    width = width or DECK_TARGET_PX[0]
    height = height or DECK_TARGET_PX[1]
    th = THEMES.get(theme, THEMES["ink"])
    kind = plan["kind"]
    centered = plan["centered"]

    im = Image.new("RGB", (width, height), th["bg"])
    dr = ImageDraw.Draw(im, "RGBA")

    used_image = None
    if image_path and Path(image_path).is_file():
        try:
            src = Image.open(image_path)
            src = src.convert("RGB")
            if centered:
                # 铺满 + 压暗：白字在任何照片上都读得清
                im = _cover_fit(src, width, height)
                scrim = Image.new("RGBA", (width, height), (th["scrim"][0], th["scrim"][1],
                                                            th["scrim"][2], 150))
                im = Image.alpha_composite(im.convert("RGBA"), scrim).convert("RGB")
            else:
                box = image_box(True, width, height)
                bw, bh = box[2] - box[0], box[3] - box[1]
                patch = _cover_fit(src, bw, bh)
                im.paste(patch, (box[0], box[1]))
            dr = ImageDraw.Draw(im, "RGBA")
            used_image = str(image_path)
        except Exception as exc:
            return {"ok": False, "kind": "call",
                    "why": "打不开/缩放配图 %s：%s" % (image_path, exc)}

    on_image = bool(used_image) and centered
    title_color = th["on_image_title"] if on_image else th["title"]
    body_color = th["on_image_body"] if on_image else th["body"]
    title_font = load_font(font_path, plan["title_size"])
    body_font = load_font(font_path, plan["body_size"])
    t_lh = glyph_height(title_font) + 10
    b_lh = glyph_height(body_font) + 14
    b_gap = int(plan["body_size"] * 0.42)
    stroke_w = 3 if on_image else 0
    stroke_c = (0, 0, 0) if on_image else None

    # 标题
    bx0, by0, bx1, by1 = plan["box_title"]
    if centered:
        cx = (bx0 + bx1) // 2
        _draw_wrapped(dr, plan["title_lines"], title_font, bx0, by0, t_lh,
                      title_color, shadow=on_image, stroke_width=stroke_w,
                      stroke_fill=stroke_c, center_x=cx)
    else:
        _draw_wrapped(dr, plan["title_lines"], title_font, bx0, by0, t_lh, title_color)
        # 标题下的强调短线
        y_rule = by1 + int(plan["title_size"] * 0.34)
        dr.rectangle([bx0, y_rule, bx0 + int(width * 0.062), y_rule + 6],
                     fill=th["accent"])

    # 要点
    marker = "·" if centered else "▪"
    marker_w = int(plan["body_size"] * 1.15)
    # 居中版式：先把**整块**居中，块内每条要点**左对齐**、标记点对齐成一列。
    # ⚠️ 两个真机踩过的坑，都在这几行里：
    #   1. 早期写成"每条要点各自居中" → 标记点参差不齐、整页像没排版。
    #      闸门与像素全绿，**只有肉眼看图才发现**。
    #   2. 早期这里有个局部变量叫 `total = full_w + marker_w`，
    #      把 `render_page` 的 `total` 形参**覆盖掉了** ——
    #      于是页脚页码画成「1 / 326」（那个 326 其实是某条要点的像素宽）。
    #      变量名一律避开形参：这里用 `blk_w`。
    block_x = None
    if centered:
        blk_w = 0
        for lines in plan["per_bullet_lines"]:
            mw = max([text_width(body_font, ln) for ln in lines] or [0])
            blk_w = max(blk_w, mw + marker_w)
        block_x = (plan["zone"][0] + plan["zone"][2]) // 2 - blk_w // 2
    for i, lines in enumerate(plan["per_bullet_lines"]):
        if i >= len(plan["box_bullets"]):
            break
        mx0, my0, mx1, my1 = plan["box_bullets"][i]
        if centered and block_x is not None:
            dr.text((block_x, my0), marker, font=body_font, fill=th["accent"],
                    stroke_width=stroke_w, stroke_fill=stroke_c)
            _draw_wrapped(dr, lines, body_font, block_x + marker_w, my0, b_lh,
                          body_color, shadow=on_image, stroke_width=stroke_w,
                          stroke_fill=stroke_c)
        else:
            dr.text((mx0, my0), marker, font=body_font, fill=th["accent"])
            _draw_wrapped(dr, lines, body_font, mx0 + marker_w, my0, b_lh, body_color)

    # 页脚：品牌 + 页码
    safe = safe_rect(width, height)
    foot_font = load_font(font_path, FOOTER_SIZE)
    fy = safe["bottom"] + int(height * 0.022)
    foot_color = th["on_image_body"] if used_image and centered else th["body"]
    dr.text((safe["left"], fy), "三剪客 · %s" % (deck_title or "课件"),
            font=foot_font, fill=foot_color)
    pn = "%d / %d" % (page_no, total)
    dr.text((safe["right"] - text_width(foot_font, pn), fy), pn,
            font=foot_font, fill=foot_color)

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    out_px = imgprobe.image_size(dst)
    return {"ok": True, "out_px": [out_px[0], out_px[1]],
            "want_px": [width, height], "used_image": used_image,
            "size_bytes": Path(dst).stat().st_size,
            "title_lines": len(plan["title_lines"]),
            "bullet_lines": len(plan["bullet_lines"]),
            "need_h": plan["need_h"], "avail_h": plan["avail_h"],
            "theme": theme, "font": font_path, "layout_version": LAYOUT_VERSION}


# ===========================================================================
# 成本
# ===========================================================================

def unit_points(resolution, override=None):
    """单张出图成本（点）。只有 1K 有实测价；2K/4K 不给默认值。"""
    if override is not None:
        return float(override)
    if (resolution or "1K").upper() == "1K":
        return float(POINTS_PER_IMAGE_1K)
    return None


def estimate_image_cost(count, resolution="1K", override=None):
    """出图成本预估。2K/4K 没实测价 → points 为 None（**拒绝估算**）。"""
    pts = unit_points(resolution, override)
    rec = {"count": int(count), "resolution": resolution,
           "points_per_image": pts, "total_points": None, "total_yuan": None,
           "measured": (resolution or "1K").upper() == "1K" and override is None,
           # 明示"这一档我们没实测过"，让消费方一眼看出金额为什么是空的
           "untested": (resolution or "1K").upper() in UNTESTED_RESOLUTIONS}
    if pts is not None:
        rec["total_points"] = round(pts * count, 2)
        rec["total_yuan"] = round(pts * count / float(POINTS_PER_YUAN), 2)
    return rec


def fmt_image_cost(rec):
    if rec["total_points"] is None:
        return ("%d 张 × %s：**没有实测单价，拒绝估算**（只有 1K 有实测价 24 点/张）。"
                "给 --points-per-image 指定单价后才能算" % (rec["count"], rec["resolution"]))
    tag = "实测价" if rec["measured"] else "指定价"
    return ("%d 张 × %g 点/张（%s，%s）= **%g 点 = %.2f 元**"
            % (rec["count"], rec["points_per_image"], rec["resolution"], tag,
               rec["total_points"], rec["total_yuan"]))


# 文本 token **估算**口径（网关不公布文本单价，这是估算不是账单）
EST_OUTLINE_PROMPT_TOK = 1500
EST_OUTLINE_TOK_PER_PAGE = 200
PAGES_PER_CALL = 3
EST_PAGES_PROMPT_TOK = 1600
EST_PAGES_TOK_PER_PAGE = 340


def estimate_text_cost(pages, do_outline=True, do_pages=True, yuan_per_ktok=None):
    """文本成本**估算**（token × 自填单价）。单价缺省时只报 token 不报金额。"""
    batches = (max(1, int(pages)) + PAGES_PER_CALL - 1) // PAGES_PER_CALL
    calls = []
    if do_outline:
        calls.append({"stage": "outline", "prompt_tokens": EST_OUTLINE_PROMPT_TOK,
                      "completion_tokens": EST_OUTLINE_TOK_PER_PAGE * int(pages)})
    if do_pages:
        calls.append({"stage": "pages(%d 页/次)" % PAGES_PER_CALL,
                      "prompt_tokens": EST_PAGES_PROMPT_TOK * batches,
                      "completion_tokens": EST_PAGES_TOK_PER_PAGE * int(pages),
                      "calls": batches})
    total = sum(c["prompt_tokens"] + c["completion_tokens"] for c in calls)
    rec = {"calls": calls, "total_tokens": total, "yuan_per_ktok": yuan_per_ktok,
           "total_yuan": None, "estimated": True}
    if yuan_per_ktok is not None:
        rec["total_yuan"] = round(total / 1000.0 * float(yuan_per_ktok), 4)
    return rec


# ===========================================================================
# 接口封装
# ===========================================================================

def submit_image(prompt, aspect_ratio="16:9", resolution="1K",
                 model="nano-banana", action="generate", image_urls=None,
                 callback_url=None, key=None, timeout=180):
    """提交一个出图任务，返回网关 data（含 task_id 与预冻结点数）。

    请求体字段用 `python scripts/a7w.py schema nano_banana` 实查过，不要凭记忆加字段。
    """
    if action not in ACTIONS:
        raise a7w.A7wError("action 只能是 {}，收到 {!r}".format(" / ".join(ACTIONS), action))
    if resolution not in RESOLUTIONS:
        raise a7w.A7wError("resolution 只能是 {}，收到 {!r}".format(" / ".join(RESOLUTIONS), resolution))
    if aspect_ratio not in ASPECT_RATIOS:
        raise a7w.A7wError("aspect_ratio 只能是 {}，收到 {!r}".format(
            " / ".join(ASPECT_RATIOS), aspect_ratio))
    if action == "edit" and not image_urls:
        raise a7w.A7wError("action=edit 时必须提供 image_urls")
    body = {"prompt": prompt, "action": action, "model": model,
            "resolution": resolution, "aspect_ratio": aspect_ratio}
    if image_urls:
        body["image_urls"] = list(image_urls)
    if callback_url:
        body["callback_url"] = callback_url
    url = "{}/api/v1/apps/{}/{}".format(a7w.HOST, APP_IMAGE, API_SUBMIT)
    return a7w._unwrap(a7w._request("POST", url, a7w.load_key(key), body=body, timeout=timeout))


def task_state(task_id, key=None):
    """查一次任务，返回 (状态, 归一化 data, 原始信封)。

    ⚠️ 实测：`status` 在 `data` **顶层**，不在 `data.result` 里（平台文档写错了）。
    """
    payload = a7w._request("GET", TASK_URL.format(task_id), a7w.load_key(key))
    data = a7w._unwrap(payload) or {}
    return data.get("status"), data, payload


def poll_task(task_id, key=None, timeout=POLL_TIMEOUT_DEFAULT,
              interval=a7w.POLL_INTERVAL, on_tick=None):
    """轮询任务到终态。

    **必须有超时上限**：出图会卡在 processing，无限等会把批处理挂死。
    返回 (状态, data, 原始信封, 轮询次数)。
    """
    deadline = time.time() + timeout
    ticks = 0
    last = None
    while True:
        time.sleep(interval)
        ticks += 1
        status, data, payload = task_state(task_id, key)
        if status != last and on_tick:
            on_tick(status, data)
        last = status
        if status in a7w.TERMINAL:
            return status, data, payload, ticks
        if time.time() >= deadline:
            return "timeout", data, payload, ticks


def points_cost(data):
    """从任务返回里取**实际扣费**。

    ⚠️ 只信 usage.points_cost。平台的 pricing_matrix / tenant_* 字段我们验证过半数不可信
    （`image_human` 字段写 1.5/2/4/8 点/秒、实测 2/3/6/12；`voice_tts/stt` 字段写 30、实扣 40），
    所以那些字段只当参考，绝不写进结算口径。
    提交响应里的 frozen_points 也只是**预冻结**（实测 31.2），失败全额退回，不是最终扣费。
    """
    usage = (data or {}).get("usage") or {}
    for k in ("points_cost", "actual_points"):
        v = usage.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    res = (data or {}).get("result") or {}
    v = res.get("actual_points")
    return float(v) if isinstance(v, (int, float)) else None


def find_image_urls(data):
    """把任务结果里所有图片地址挖出来（结构会有差异，做深度搜索）。

    实测 completed 返回同时给了三处：`result.image_url`、
    `result.data[0].image_url`、`result.results[0].image_url`。只取第一处也能跑，
    但结构一变就瞎，所以这里按深度优先把所有 `image_url` 都收齐再去重保序。
    """
    found = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("image_url", "url", "output_url") and isinstance(v, str) \
                        and v.startswith("http"):
                    if v not in found:
                        found.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk((data or {}).get("result"))
    return found


def download(url, dst, timeout=180, key=None, retries=3):
    """把图下载到 dst（零依赖）。

    ⚠️ **不要走 `a7w._request` 下图片**，它有两个坑，两个都实测踩过：
      1. `_request(..., raw=X)` 里的 `raw` 是**原始请求体**，不是"要原始响应"。
         传 `raw=True` 会让 `headers["Content-Type"] = None`，`putheader` 直接抛
         `TypeError: expected string or bytes-like object, got 'NoneType'`；
         就算绕过去，`_request` 末尾做的是 `json.loads(resp.read())` —— **PNG 不是 JSON**。
      2. 传 `key=None` 时它会做 `"Bearer " + key` → `TypeError: can only concatenate
         str (not "NoneType") to str`。发生在**图已经出好、钱已经扣了**之后，最亏。
    所以这里自带一小段 urllib 下载：拿字节、不解析 JSON、Key 走 `a7w.load_key` 兜底、
    网络类错误退避重试。**它就是本包自己的业务代码，不污染共用的 a7w.py。**
    """
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + (a7w.load_key(key) or ""),
                      "Accept": "image/*,*/*"})
    last = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                blob = resp.read()
            if not blob:
                raise a7w.A7wError("下载到的内容是空的：%s" % url)
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_bytes(blob)
            return len(blob)
        except urllib.error.HTTPError as exc:
            raise a7w.A7wError("下载图片失败（HTTP %s）：%s" % (exc.code, url))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
    raise a7w.A7wError("下载图片失败（已重试 %d 次）：%s（%s）" % (retries, url, last))


def snap_to_ratio(src, dst, want_ratio, probe_pil=True):
    """把图按请求比例**居中裁准**（写操作；只读探针留在 imgprobe.py 里）。

    PIL 在就用 PIL；没有 PIL 就用标准库 PNG 重写（同族同款兜底），
    两者都没有就**如实报失败**，不静默拷贝一张比例不对的图交差。
    """
    want = parse_ratio(want_ratio)
    if want is None:
        raise UsageError("`--snap` 需要可判定的比例，收到 %r" % want_ratio)
    w, h, fmt = imgprobe.image_size(src)
    if not w or not h:
        raise a7w.A7wError("读不出真实像素，无法裁剪：%s" % src)
    cur = w / float(h)
    if abs(cur - want) / want <= RATIO_TOLERANCE_FLOOR:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_bytes(Path(src).read_bytes())
        return {"ok": True, "already": True, "out_px": [w, h]}
    if probe_pil and has_pil():
        from PIL import Image
        im = Image.open(src).convert("RGB")
        if cur > want:                       # 太宽 → 裁左右
            nw = max(1, int(round(h * want)))
            left = (w - nw) // 2
            im = im.crop((left, 0, left + nw, h))
        else:                                # 太高 → 裁上下
            nh = max(1, int(round(w / want)))
            top = (h - nh) // 2
            im = im.crop((0, top, w, top + nh))
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        im.save(dst)
        nw, nh, _ = imgprobe.image_size(dst)
        return {"ok": True, "already": False, "out_px": [nw, nh]}
    raise UsageError("`--snap` 需要 PIL（pip install pillow）来裁剪非 PNG 图片；"
                     "本机没有 PIL，请去掉 --snap 或装 pillow")


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, json_mode=True, retries=CHAT_RETRIES):
    """一次文本调用（OpenAI 兼容）。返回 (content, usage)。

    ⚠️ 走 `/chat/completions` 的成功响应**不带 `code` 字段**，
    直接读 `choices[0].message.content`；`{"code":1,"data":{...}}` 那层信封是给生成应用的。
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(retries):
        try:
            payload = a7w._request("POST", CHAT_URL, a7w.load_key(key), body=body, timeout=300)
            if isinstance(payload, dict) and payload.get("choices"):
                content = ((payload["choices"][0].get("message") or {}).get("content")) or ""
                return content, payload.get("usage") or {}
            last = a7w.A7wError("模型没返回 choices：%s" % json.dumps(
                payload, ensure_ascii=False)[:200])
        except a7w.A7wError as exc:
            last = exc
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    raise last or a7w.A7wError("文本调用失败")


def parse_first_json(text):
    """从模型输出里抠出第一个完整 JSON 对象（前后有多余字符也能救）。"""
    if not text:
        raise a7w.A7wError("模型返回为空")
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except ValueError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = dec.raw_decode(s[i:])
                return obj
            except ValueError:
                continue
    raise a7w.A7wError("模型返回的不是合法 JSON（前 200 字：%s）" % s[:200])


# ===========================================================================
# 提示词（分页方案 / 每页内容）
# ===========================================================================
#
# ⚠️ 治本的一条：提示词里**不许出现任何一份可直接复制的完整产出**。
#    举例统一用**跨主题**示例（社区团购选品 / 机械制图停机点 / 架子鼓坐姿，
#    与知识付费 / 企业内训的常见主题明显不搭），并登记进 PROMPT_SAMPLES。
#    万一以后有人把真实示例加回提示词，闸门三会兜住。
# ---------------------------------------------------------------------------

SYSTEM_OUTLINE = (
    "你是三剪客的课件设计助手，把一份讲义 / 课程大纲拆成**逐页课件方案**（分页方案）。\n"
    "硬性要求：\n"
    "1. 只输出 JSON 对象，不要解释、不要 Markdown 代码块。\n"
    "2. 每一页都要有 `title`（页标题，不超过 30 个字）与 `image_intent`\n"
    "   （配图意图，95~150 个中文字）：写清**主体、构图、光线、色调、质感**，\n"
    "   **画面里绝对不许出现任何文字 / 字母 / 数字**——图上的字由本地排版软件压上去，\n"
    "   让出图模型写字一定会写错。\n"
    "3. `kind` 只能是 cover / content / section / summary 之一；\n"
    "   第一页必须是 cover，章节切换用 section，最后一页建议 summary。\n"
    "4. `bullets` 给 1~3 条粗要点，每条不超过 20 字 —— 这是分页骨架，后续会被逐页展开。\n"
    "5. `notes` 给一句话讲稿备注草稿（不超过 60 字）。\n"
    "6. **不许编造**讲义里没有的数字、人名、机构、结论；\n"
    "   教育类内容**不许做任何效果承诺**（禁止出现 保过 / 包过 / 包学会 / 保证提分 这类词）。\n"
    "7. 页数按用户要求（允许上下浮动 1 页）。\n\n"
    "输出结构：\n"
    '{"deck_title":"课件名","pages":[{"kind":"cover","title":"页标题",'
    '"bullets":["粗要点"],"notes":"备注草稿","image_intent":"画面描述"}]}\n\n'
    "**跨主题**的字段形态示例（只示范写法，**严禁照抄**）：\n"
    "- 页标题写法示例：`社区团购的选品清单怎么定`\n"
    "- 配图意图写法示例：`清晨的木质案板上摊开一张手写清单，侧逆光，浅景深纪实摄影，"
    "画面里没有任何文字`\n"
)

SYSTEM_PAGES = (
    "你是三剪客的课件设计助手，把分页方案的骨架展开成**可以直接拿去上课的逐页内容**。\n"
    "硬性要求：\n"
    "1. 只输出 JSON 对象，不要解释、不要 Markdown 代码块。\n"
    "2. 页序与页标题**基本保持不变**（可微调措辞，**不许增删页**）。\n"
    "3. 每页 `bullets` 给 1~6 条，**每条不超过 40 个字**，是能对着投影念出来的要点，\n"
    "   不要写成整段话；一条要点只讲一件事。\n"
    "4. 每页 `notes` 给 80~400 字的**讲稿备注**：这一页你打算怎么讲、要强调什么、\n"
    "   学员最容易在哪里卡住。备注是给讲课的人看的，不要复述要点。\n"
    "5. `image_intent` 保持画面描述，**画面里不许出现任何文字 / 字母 / 数字**。\n"
    "6. **不许编数据、人名、机构**；不做任何效果承诺（禁止 保过 / 包过 / 包学会 / 保证提分）。\n\n"
    "输出结构：\n"
    '{"pages":[{"id":"p01","title":"页标题","bullets":["要点"],"notes":"讲稿备注",'
    '"image_intent":"画面描述"}]}\n\n'
    "**跨主题**的写法示例（只示范写法，**严禁照抄**）：\n"
    "- 讲稿备注写法示例：`先讲一个反直觉的现象，再抛出本节要解决的问题，最后给出判断标准`\n"
)


def build_outline_prompt(source_text, pages, level, audience, topic=None):
    lv = {"zero": "零基础（每个术语第一次出现都要用大白话解释一句）",
          "basic": "入门（跳过名词解释，重点讲为什么这么做）",
          "advanced": "进阶（直接讲原理、边界条件与取舍）"}.get(level, "入门")
    head = ["请把下面这份讲义拆成 **约 %d 页**的课件分页方案。" % pages,
            "受众水平：%s" % lv]
    if audience:
        head.append("受众补充：%s" % audience)
    if topic:
        head.append("课程主题：%s" % topic)
    head.append("")
    head.append("=== 讲义原文（这是你的唯一事实来源，不许编造它之外的内容）===")
    head.append(source_text)
    head.append("=== 讲义原文结束 ===")
    head.append("")
    head.append("现在输出 JSON（约 %d 页）。" % pages)
    return "\n".join(head)


def build_pages_prompt(skeletons, level, style=None):
    lv = {"zero": "零基础", "basic": "入门", "advanced": "进阶"}.get(level, "入门")
    lines = ["请把下面 %d 页的**分页骨架**展开成成稿内容（受众水平：%s）。" % (len(skeletons), lv),
             "保持页序与页标题不变，逐页补齐 `bullets`（1~6 条、每条不超过 40 字）",
             "与 `notes`（80~400 字讲稿备注）。"]
    if style:
        lines.append("讲课风格补充：%s" % style)
    lines.append("")
    lines.append("=== 分页骨架 ===")
    for i, s in enumerate(skeletons):
        lines.append("第 %d 页" % (i + 1))
        lines.append(json.dumps({k: s.get(k) for k in
                                 ("id", "kind", "title", "bullets", "notes", "image_intent")},
                                ensure_ascii=False))
    lines.append("=== 骨架结束 ===")
    lines.append("")
    lines.append("现在输出 JSON：{\"pages\":[{\"id\":\"p01\",\"title\":\"…\","
                 "\"bullets\":[\"…\"],\"notes\":\"…\",\"image_intent\":\"…\"}]}")
    return "\n".join(lines)


# ===========================================================================
# 断点续跑（key 必须含全部影响产出的维度）
# ===========================================================================
#
# ⚠️ 同族踩过的坑，逐条都在这里挡住：
#   · **内容截断**：`prompt[:N]` 当摘要 → 只改后半句时 key 不变，静默复用旧产物。
#     所以提示词摘要一律取**全文**归一化后的 sha1。
#   · **`resolution` 不入 key**：换了档位却复用 1K 的旧图。所以它进 key。
#   · **死参数**：命令行加了 `--theme` 之类影响产出的参数、却没进 key →
#     改了参数、产物一动不动。所以本包的 key 分三档，影响什么就把什么写进去：
#       `page_state_key`   每页文本（id + 全文摘要 + level + model + 提示词版本）
#       `image_state_key`  出图（页 id + 提示词全文摘要 + gen_ratio + resolution + model）
#       `render_state_key` 渲染（页 id + 全部页文本 + 主题 + 字体 + 画布 + 配图 + 版式版本）
# ---------------------------------------------------------------------------

PROMPT_VERSION = "v1"

# 影响产出的**版式参数**：任何一项变了，渲染就必须重做（否则用户以为改了、其实没变）。
LAYOUT_PARAMS = ("layout_version", "theme", "font", "width", "height", "page_no", "total")


def prompt_digest(text):
    """文本**全文**摘要（归一化后 sha1 前 16 位十六进制）。

    绝不用 `text[:N]`：那样只改后半句时 key 不变。
    """
    return hashlib.sha1(_norm_for_echo(text).encode("utf-8")).hexdigest()[:16]


def page_content_digest(page):
    """一页的**全部**文本内容摘要（标题 + 要点 + 备注 + 配图意图）。"""
    payload = "|".join([
        page_text_of(page, "title"),
        " / ".join(page_bullets(page)),
        page_text_of(page, "notes"),
        page_text_of(page, "image_intent"),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def page_state_key(page, level, model):
    """`pages` 断点 key：页 id + 骨架全文摘要 + level + 模型 + 提示词版本。"""
    return "page:%s:%s:%s:%s:%s" % (
        page.get("id"), prompt_digest(json.dumps(page, ensure_ascii=False)),
        level or "basic", model or DEFAULT_MODEL, PROMPT_VERSION)


def image_prompt_of(page):
    """一页的**出图提示词**（画面描述；**不含任何文字**）。

    收尾统一加一句"画面里不要出现任何文字"，防止模型自己往图里写字。
    """
    intent = page_text_of(page, "image_intent").strip()
    if not intent:
        intent = page_text_of(page, "title").strip()
    return ("%s。画面干净、留白充足，**画面里不要出现任何文字、字母、数字或水印**。"
            "适合作为课件配图，横版构图。" % intent).strip()


def image_state_key(page, gen_ratio, resolution, model):
    """出图断点 key：页 id + 提示词全文摘要 + 比例 + 分辨率 + 模型。

    ⚠️ `resolution` 必须进 key（同族踩过：换了档位却静默复用 1K 的旧图）。
    ⚠️ 提示词用**全文**摘要（同族踩过：截断摘要 → 改了后半句不复用新图）。
    """
    return "img:%s:%s:%s:%s:%s" % (
        page.get("id"), prompt_digest(image_prompt_of(page)),
        gen_ratio or DECK_GEN_RATIO, resolution or "1K", model or "nano-banana")


def render_state_key(page, image_path, params):
    """渲染断点 key：页 id + 页内容摘要 + 配图（路径 + 大小）+ **全部版式参数**。"""
    img_sig = ""
    if image_path and Path(image_path).is_file():
        st = Path(image_path).stat()
        img_sig = "%s:%d:%d" % (Path(image_path).name, st.st_size, int(st.st_mtime))
    payload = "|".join([
        page.get("id") or "", page_content_digest(page),
        page.get("kind") or DEFAULT_PAGE_KIND, img_sig,
    ] + [str(params.get(k, "")) for k in LAYOUT_PARAMS])
    return "render:%s:%s" % (page.get("id"), hashlib.sha1(
        payload.encode("utf-8")).hexdigest()[:16])


def load_state(path):
    p = Path(path)
    if not p.is_file():
        return {"version": 1, "items": {}}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or "items" not in obj:
            return {"version": 1, "items": {}}
        return obj
    except (OSError, ValueError):
        sys.stderr.write("⚠ 断点文件读不动（%s），按空处理——注意这会导致重跑重扣\n" % path)
        return {"version": 1, "items": {}}


def save_state(path, state):
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def state_check(state, key, dims, where="断点"):
    """命中 key 之后**逐维复核**记录里的值（同族口径）。

    说不清来历的旧记录一律重做，**绝不静默复用**。
    返回 True 表示可以复用。
    """
    it = (state.get("items") or {}).get(key)
    if not isinstance(it, dict):
        return False
    for k, v in (dims or {}).items():
        if str(it.get(k, "")) != str(v):
            sys.stderr.write("⚠ %s 命中但 %s 对不上（记录 %r ≠ 本次 %r）→ 重做\n"
                             % (where, k, it.get(k), v))
            return False
    return True


def file_identity(path):
    """产物文件自己的身份（字节数 + mtime 秒）。读不到返回 None。"""
    try:
        st = Path(path).stat()
        return {"bytes": int(st.st_size), "mtime": int(st.st_mtime)}
    except OSError:
        return None


def stamp_artifact(rec, path):
    """把产物身份盖进断点记录（渲染 / 出图成功后都调它）。"""
    fi = file_identity(path)
    if fi:
        rec["out_bytes"] = fi["bytes"]
        rec["out_mtime"] = fi["mtime"]
    return rec


def state_artifact_ok(rec, path, where="断点"):
    """断点命中后，**再核一次产物文件本身的身份**。

    ⚠️ 这是真机踩出来的一个**静默复用**事故，形态很隐蔽：
      `--theme ink` 渲一遍 → 改成 `--theme night` 渲一遍 → 再改回 `--theme ink`。
      两个主题**写同一个文件名**（`slides/slide-01.png`），
      而 `render` 断点 key 里**含主题**，所以切回 ink 时 ink 的旧记录仍然"命中" →
      直接跳过 → **磁盘上留着的却是 night 的图**，命令还报告"已渲染，跳过（断点续跑）"。
      也就是说：断点 key 的所有维度都对得上，产物却是别人的。

    凡是「**key 的某一维不同、但产物路径相同**」的参数都会踩这个坑
    （主题 / 分辨率 / 比例 / 字体…）。所以命中还不够，必须核对产物身份。
    对不上就重做——宁可多渲一次（本地渲染零成本），也不要交一份说不清来历的产物。
    """
    rb = (rec or {}).get("out_bytes")
    rm = (rec or {}).get("out_mtime")
    cur = file_identity(path)
    if cur is None:
        return False
    if rb is None or rm is None:
        sys.stderr.write("⚠ %s 记录里没有产物身份（升级前的旧记录）→ 重做\n" % where)
        return False
    if int(rb) != cur["bytes"] or int(rm) != cur["mtime"]:
        sys.stderr.write("⚠ %s 记录说产物是 %s 字节 / mtime %s，磁盘上却是 %s / %s "
                         "→ **产物被别人覆盖过，重做**\n"
                         % (where, rb, rm, cur["bytes"], cur["mtime"]))
        return False
    return True


# ===========================================================================
# JSON 契约（--json）
# ===========================================================================

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None,
         # `trace` = 本次退出码非 0 时，命令自己**已经**吐过一个完整 JSON 了
         # （典型的：命令跑完了、产出也给了，只是闸门判定不合格 → 结果里 ok=false）。
         # ⚠️ 实测踩过：报价阶段曾经"先吐报价 JSON、再补失败信封"，
         #    于是 stdout 上出现**两个 JSON 文档**，`json.loads` 直接
         #    `Extra data: line N column 1` —— 把「stdout 只有一个 JSON」这条不变量打破了。
         # 退出码语义一个字不变，只是不再画蛇添足补信封。
         "trace": False}

# 退出码 → 失败类别（与 SKILL.md 里公示的退出码表一致）
_KIND_BY_EXIT = {2: "usage", 3: "gate", 4: "call", 5: "interrupt", 130: "interrupt"}


def _json_payload(obj, ok=True):
    """结果对象补 ok；顶层是数组时包成 {"ok": …, "data": […] }。"""
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        out.update(obj)
        return out
    return {"ok": bool(ok), "data": obj}


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_write(text):
    """把 JSON 文本写到**真 stdout** 并记账（绕开可能的 stdout 重定向）。"""
    (_JSON["stdout"] or sys.stdout).write(text + "\n")
    _JSON["emitted"] = True


def _json_want(a=None):
    if a is not None:
        return bool(getattr(a, "json", False))
    return bool(_JSON["want"])


def _json_out(obj, a=None, indent=1, ok=True):
    """`--json` 模式的成功出口。返回是否已输出。"""
    if not _json_want(a):
        return False
    _json_write(_json_text(obj, indent=indent, ok=ok))
    _JSON["trace"] = True
    return True


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
    """`--json` 模式的失败出口：只在本次还没输出过 JSON 结果时补信封。"""
    if _JSON["emitted"] or not _json_want(a):
        return
    err = {"kind": kind or _KIND_BY_EXIT.get(rc, "call"),
           "message": message or "命令以退出码 %s 结束（人读原因见 stderr）" % rc}
    if detail is not None:
        err["detail"] = detail
    _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                           ensure_ascii=False, indent=1))


def _json_internal(exc):
    """未预料异常的兜底信封 —— **报 bug，不藏 bug**。

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr。
    如果本次已经吐过结果，就**不再补信封**（守住"stdout 永远只有一个 JSON"这条不变量）。
    """
    if _JSON["emitted"]:
        return
    tb = sys.exc_info()[2]
    frames = traceback.extract_tb(tb) if tb else []
    detail = {"type": type(exc).__name__}
    if frames:
        last = frames[-1]
        detail["where"] = "%s:%d" % (os.path.basename(last.filename), last.lineno)
    err = {"kind": "internal",
           "message": "%s: %s" % (type(exc).__name__, exc),
           "detail": detail}
    _json_write(json.dumps({"ok": False, "exit": 1, "error": err},
                           ensure_ascii=False, indent=1))


def _fail(rc, kind, message, detail=None):
    """命令函数决定失败时调它：记下原因，返回原退出码（退出码语义不变）。"""
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


def _add_json(p, suppress=True):
    """让 `--json` 写在子命令**前后都能用**（与同族模板同口径）。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py outline --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关。

    ⚠️ **两个位置用的默认值不一样，这是必须的**：
      · 父级（顶层）用 `default=False` —— 这样 `a.json` **永远存在**，
        命令函数里可以直接 `if a.json:` 而不会 AttributeError。
      · 子命令用 `default=argparse.SUPPRESS` —— 否则子命令的默认值会把父级已经
        解析到的 `True` 覆盖掉（`outline --json` 就会被静默降级成非 JSON 输出）。
    同族模板这里写漏过一次：两个位置都用 SUPPRESS → 不加 `--json` 时属性根本不存在，
    所有 `a.json` 读取都崩在 AttributeError。
    """
    p.add_argument("--json", action="store_true",
                   default=(argparse.SUPPRESS if suppress else False),
                   help="以 JSON 输出（写在子命令前后都可以）")


# ===========================================================================
# 通用工具
# ===========================================================================

def _red(s, force_plain=False):
    if force_plain or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return "!! " + s
    return "\033[31m" + s + "\033[0m"


def ensure_outside_pkg(outdir):
    """`--outdir` 在包内 → 抛 UsageError（exit=2）。

    包内不许有任何图片：SkillHub 的上传白名单只收
    `.md .py .txt .json .sh .js .yaml .yml .csv`，图片会让上传 400。
    """
    pkg_dir = Path(__file__).resolve().parent.parent
    try:
        Path(outdir).resolve().relative_to(pkg_dir)
    except ValueError:
        return
    raise UsageError(
        "输出目录 %s 在 Skill 包内（%s）。包内不许有任何图片——上传白名单只收文本，"
        "请换到包外，例如 %s"
        % (Path(outdir).resolve(), pkg_dir,
           Path(os.environ.get("TEMP") or ".") / "slide-kit-out"))


class UsageError(a7w.A7wError):
    """用法错误（退出码 2）。"""


def _split_lines(text):
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        s = re.sub(r"^[-*•·\d.、)）\s]+", "", s).strip()
        if s:
            out.append(s)
    return out


def _load_source(a):
    """读讲义 / 大纲原文。超长**报错**，绝不静默截断。"""
    text = ""
    if getattr(a, "file", None):
        p = Path(a.file)
        if not p.is_file():
            raise UsageError("找不到讲义文件：%s" % a.file)
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    elif getattr(a, "text", None):
        text = a.text
    if len(text) > SOURCE_MAX_CHARS:
        raise UsageError(
            "讲义原文 %d 字，超过上限 %d 字。**不做静默截断**（截掉的内容你永远不知道少了什么）——"
            "请把讲义拆成两半分开跑，或先让 `sanjianke-course-outline` 精简一版"
            % (len(text), SOURCE_MAX_CHARS))
    return text


# 各子命令的参数集并不完全相同（`all` 要串起所有阶段），
# 所以跨命令调用时用一张**显式默认表**补齐缺的属性 —— 不用 `getattr(a, x, None)`
# 到处撒，那样漏一个就是一个 AttributeError 崩在半路（同族踩过）。
_ARG_DEFAULTS = {
    "from_file": None, "is_result": False, "embed": False, "out": None,
    "dry_run": False, "html": True, "only": None, "count": None, "deck": None,
    "style": None, "strict_notes": False, "theme": None, "font": None,
    "force": False, "every": 1, "resolution": "1K", "outdir": "slide-out",
    "budget": None, "yuan_per_ktok": YUAN_PER_KTOK_DEFAULT,
}


def _clone_args(a, **over):
    """把 `a` 复制成一个补齐了默认属性的 Namespace，再用 `over` 覆盖。"""
    d = dict(_ARG_DEFAULTS)
    d.update(vars(a))
    d.update(over)
    return argparse.Namespace(**d)


def norm_page(obj, idx, source_kind=None):
    """把模型返回的一条页码记录**归一化**（缺字段不崩，交给闸门去判）。"""
    if not isinstance(obj, dict):
        return None
    kind = str(obj.get("kind") or "").strip().lower()
    if kind not in PAGE_KINDS:
        kind = source_kind or DEFAULT_PAGE_KIND
    bullets = obj.get("bullets")
    if isinstance(bullets, str):
        bullets = _split_lines(bullets)
    elif isinstance(bullets, list):
        bullets = [str(b).strip() for b in bullets if str(b).strip()]
    else:
        bullets = []
    return {
        "id": str(obj.get("id") or ("p%02d" % (idx + 1))).strip(),
        "kind": kind,
        "title": str(obj.get("title") or "").strip(),
        "bullets": bullets,
        "notes": str(obj.get("notes") or "").strip(),
        "image_intent": str(obj.get("image_intent") or obj.get("image") or "").strip(),
    }


def deck_path(outdir):
    return Path(outdir) / DECK_NAME


def load_deck(a):
    """载入 deck.json（`--deck` 优先，否则用 `--outdir`）。"""
    p = Path(getattr(a, "deck", None) or deck_path(a.outdir))
    if not p.is_file():
        raise UsageError("找不到分页方案文件：%s（先跑 `outline`）" % p)
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("分页方案文件读不动（%s）：%s" % (p, exc))
    if not isinstance(obj, dict) or not isinstance(obj.get("pages"), list):
        raise UsageError("分页方案文件结构不对（缺 pages 数组）：%s" % p)
    return obj, p


def save_deck(obj, path):
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def selected_pages(pages, a):
    """按 --only / --count 过滤（顺序保持页序）。"""
    sel = list(pages)
    only = getattr(a, "only", None)
    if only:
        ids = {s.strip() for s in only.split(",") if s.strip()}
        sel = [p for p in sel if p.get("id") in ids]
    cnt = getattr(a, "count", None)
    if cnt:
        sel = sel[:cnt]
    return sel


def pages_with_image(pages, every):
    """按 `--every N` 判哪些页配图（页序 1、1+N、1+2N… 配图）。"""
    every = max(1, int(every or 1))
    out = []
    for i, p in enumerate(pages):
        out.append(bool(i % every == 0))
    return out


# ===========================================================================
# 闸门五：每页内容完整性
# ===========================================================================

def check_pages_complete(pages, require_notes=False, where="分页方案"):
    """闸门五：页数 > 0、每页有标题 + 至少 1 条要点；空页 / 零页 → 拦。

    返回 (bad, warns)。`bad` 非空即拦截。
    """
    bad, warns = [], []
    if not pages:
        bad.append({"id": "-", "leaks": [
            ("no_pages", "%s里**一页都没有**（页数为 0）—— 拒绝产出一份空课件"
                         % where)]})
        return bad, warns
    seen = set()
    for i, p in enumerate(pages):
        leaks = []
        pid = p.get("id") or ("p%02d" % (i + 1))
        if pid in seen:
            leaks.append(("dup_id", "页 id 重复：%s（页 id 必须唯一，否则断点续跑会串页）" % pid))
        seen.add(pid)
        title = page_text_of(p, "title").strip()
        bullets = page_bullets(p)
        if not title:
            leaks.append(("empty_title", "第 %d 页**没有标题**" % (i + 1)))
        elif len(title) > TITLE_MAX_CHARS:
            leaks.append(("title_too_long",
                          "第 %d 页标题 %d 字，超过上限 %d 字（多出「%s」）"
                          % (i + 1, len(title), TITLE_MAX_CHARS, title[TITLE_MAX_CHARS:])))
        if not bullets:
            leaks.append(("empty_page",
                          "第 %d 页「%s」**一条要点都没有**（空页）—— "
                          "闸门五：每页必须有标题 + 至少 1 条要点"
                          % (i + 1, title or "(无标题)")))
        for bi, b in enumerate(bullets):
            if len(b) > BULLET_MAX_CHARS:
                leaks.append(("bullet_too_long",
                              "第 %d 页第 %d 条要点 %d 字，超过上限 %d 字（多出 %d 字：「%s」）"
                              "——**不截断**，请拆条或压缩"
                              % (i + 1, bi + 1, len(b), BULLET_MAX_CHARS,
                                 len(b) - BULLET_MAX_CHARS, b[BULLET_MAX_CHARS:])))
        if len(bullets) > BULLET_MAX_ITEMS:
            leaks.append(("too_many_bullets",
                          "第 %d 页 %d 条要点，超过上限 %d 条"
                          % (i + 1, len(bullets), BULLET_MAX_ITEMS)))
        notes = page_text_of(p, "notes").strip()
        if not notes and p.get("kind") != "cover":
            detail = "第 %d 页「%s」缺讲稿备注" % (i + 1, title or "(无标题)")
            if require_notes:
                # `--strict-notes`：备注是课件的一部分，缺了就当闸门失败
                leaks.append(("empty_notes", detail))
            else:
                warns.append({"id": pid, "title": title, "detail": detail})
        elif notes and len(notes) < NOTES_MIN_CHARS and p.get("kind") != "cover":
            warns.append({"id": pid, "title": title,
                          "detail": "第 %d 页备注只有 %d 字（建议 ≥ %d 字）"
                                    % (i + 1, len(notes), NOTES_MIN_CHARS)})
        # ⚠️ 上限也要真判。否则文档里写的「备注 ≤ 400 字 / 配图意图 ≤ 200 字」就是**死口径**
        #    —— 写了不查，用户会以为超了会被拦。这里按**告警**处理（不拦）：
        #    备注长一点只是啰嗦，不像文字溢出那样会把版面撑坏。
        if len(notes) > NOTES_MAX_CHARS:
            warns.append({"id": pid, "title": title,
                          "detail": "第 %d 页备注 %d 字，超过建议上限 %d 字（不拦，但讲师可能读不完）"
                                    % (i + 1, len(notes), NOTES_MAX_CHARS)})
        intent = page_text_of(p, "image_intent").strip()
        if len(intent) > IMAGE_INTENT_MAX_CHARS:
            warns.append({"id": pid, "title": title,
                          "detail": "第 %d 页配图意图 %d 字，超过上限 %d 字"
                                    "（画面描述太长会稀释主体，建议删到 %d 字内）"
                                    % (i + 1, len(intent), IMAGE_INTENT_MAX_CHARS,
                                       IMAGE_INTENT_MAX_CHARS)})
        if leaks:
            bad.append({"id": pid, "title": title, "leaks": leaks})
    return bad, warns


def _report_gate_bad(bad, headline, extra=""):
    """统一的闸门失败输出：标红 + stderr 汇总（不静默）。"""
    sys.stderr.write("\n")
    for b in bad:
        for kind, why in b.get("leaks") or []:
            sys.stderr.write("   %s #%s %s\n" % (_red("[%s]" % kind), b.get("id"), why))
    sys.stderr.write("\n%s\n" % _red(
        headline + ("\n" + extra if extra else "")))


def gates_for_pages(pages, where="页内容"):
    """闸门一 / 二 / 三：对每一页的**全部文本**跑合规 / 占位符 / 照抄示例。"""
    bad = []
    for p in pages:
        leaks = []
        pid = p.get("id") or "?"
        leaks += text_gate(page_text_of(p, "title"), "%s 第 %s 页标题" % (where, pid))
        for i, b in enumerate(page_bullets(p)):
            leaks += text_gate(b, "%s 第 %s 页第 %d 条要点" % (where, pid, i + 1))
        leaks += text_gate(page_text_of(p, "notes"), "%s 第 %s 页讲稿备注" % (where, pid))
        leaks += text_gate(page_text_of(p, "image_intent"), "%s 第 %s 页配图意图" % (where, pid))
        if leaks:
            bad.append({"id": pid, "title": page_text_of(p, "title"), "leaks": leaks})
    return bad


# ===========================================================================
# 命令：outline —— 读讲义 → 分页方案
# ===========================================================================

def cmd_outline(a):
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)

    # --from-file：**不调模型**，直接拿一份返回 JSON 过闸门（零成本自检）
    if a.from_file:
        raw = Path(a.from_file).read_text(encoding="utf-8-sig", errors="replace")
        obj = parse_first_json(raw)
    else:
        source = _load_source(a)
        if not source.strip():
            raise UsageError(
                "没有给讲义原文。三种给法任选一种：\n"
                "  1) 位置参数：run.py outline 讲义.md --pages 12 --outdir D:/slides/x\n"
                "  2) --text \"<讲义正文>\"\n"
                "  3) --from-file <一份模型返回的 JSON>（**零成本闸门自检**，不调模型）")
        prompt = build_outline_prompt(source, a.pages, a.level, a.audience, a.topic)
        if a.dry_run:
            sys.stderr.write("=== 将发送的提示词（--dry-run，不调模型、不花钱）===\n")
            sys.stderr.write(SYSTEM_OUTLINE + "\n---\n" + prompt + "\n")
            return 0
        if a.budget is not None:
            est = estimate_text_cost(a.pages, True, False, a.yuan_per_ktok)
            if est["total_yuan"] is not None and est["total_yuan"] > a.budget:
                msg = ("预估 %.4f 元超过预算上限 %g 元（口径：%.4f 元/千 token **估算**），"
                       "**已中断，未发起调用**" % (est["total_yuan"], a.budget,
                                          float(a.yuan_per_ktok or 0)))
                sys.stderr.write("\n%s\n" % _red(msg))
                return _fail(3, "budget", msg)
        content, usage = chat(prompt, SYSTEM_OUTLINE, a.model, a.temperature,
                              a.max_tokens, a.key, not a.no_json_mode)
        obj = parse_first_json(content)
        sys.stderr.write("outline 用量：%s\n" % json.dumps(usage, ensure_ascii=False))

    pages_raw = obj.get("pages") if isinstance(obj, dict) else None
    if not isinstance(pages_raw, list):
        raise a7w.A7wError("模型返回里没有 pages 数组：%s"
                           % json.dumps(obj, ensure_ascii=False)[:200])
    pages = [p for p in (norm_page(o, i) for i, o in enumerate(pages_raw)) if p]

    # ---- 结构闸门：页数 > 0 / 每页有标题 / 有配图意图 / 首页是 cover / 页数对得上 ----
    bad, warns = [], []
    if not pages:
        bad.append({"id": "-", "leaks": [("no_pages", "分页方案里一页都没有（页数为 0）")]})
    if pages and pages[0].get("kind") != "cover":
        warns.append({"id": pages[0].get("id"), "title": pages[0].get("title"),
                      "detail": "第一页 kind 不是 cover（建议首页做封页）"})
    want = int(a.pages or 0)
    if want and pages and abs(len(pages) - want) > 1:
        bad.append({"id": "-", "leaks": [
            ("page_count", "要求约 %d 页，实际解析出 %d 页（差 %d 页，容忍 ±1）—— "
                           "页数对不上说明模型没按规模分页，别急着往下跑"
             % (want, len(pages), abs(len(pages) - want)))]})
    for i, p in enumerate(pages):
        leaks = []
        if not page_text_of(p, "title").strip():
            leaks.append(("empty_title", "第 %d 页没有标题" % (i + 1)))
        if not page_text_of(p, "image_intent").strip():
            leaks.append(("no_image_intent",
                          "第 %d 页没有配图意图（image_intent）—— 没有它这一步就出不了图" % (i + 1)))
        if leaks:
            bad.append({"id": p.get("id"), "title": p.get("title"), "leaks": leaks})

    # ---- 闸门一 / 二 / 三：文本内容 ----
    bad += gates_for_pages(pages, "分页方案")

    if bad:
        if a.json:
            _json_out({"stage": "gate", "count": len(bad), "blocked": bad,
                       "warnings": warns}, a, ok=False)
        _report_gate_bad(bad,
                         "分页方案未通过闸门，**没有写出任何文件**。"
                         "分页骨架错了，后面每一页都是错的——先在源头改掉。")
        return _fail(3, "gate", "outline 闸门未通过：%d 项" % len(bad))

    deck = {"version": 1, "generated_by": "sanjianke-slide-kit", "kit_version": VERSION,
            "topic": str(obj.get("deck_title") or a.topic or "课件").strip(),
            "deck_title": str(obj.get("deck_title") or a.topic or "课件").strip(),
            "audience": a.audience or "", "level": a.level,
            "ratio": DECK_RATIO, "gen_ratio": DECK_GEN_RATIO,
            "resolution": getattr(a, "resolution", None) or "1K",
            "every": int(getattr(a, "every", None) or 1),
            "model": a.model, "stage": "outline",
            "pages": pages}
    # ⚠️ **分页骨架是不可变输入**，单独存一份。
    #    实测踩过两次，两次都是这份可变骨架害的：
    #      1. `pages` 展开成功后会把成稿写回 `deck["pages"]`，第二次跑 `pages` 时
    #         批次输入已经变成成稿 → 批次摘要变了 → 断点全部失效 →
    #         **每重跑一次就重新调一遍模型（白花钱）**。
    #      2. `kind`（封页 / 章节点 / 小结）被展开阶段的缺省值覆盖，
    #         封面页丢掉整幅铺底版式，而所有闸门与像素检查**全绿**。
    #    所以：`skeleton_pages` 一旦写下就不再改，`pages` 永远从它展开。
    deck["skeleton_pages"] = json.loads(json.dumps(pages, ensure_ascii=False))
    outdir.mkdir(parents=True, exist_ok=True)
    dp = outdir / DECK_NAME
    save_deck(deck, dp)
    md = outdir / DECK_MD_NAME
    md.write_text(render_deck_md(deck), encoding="utf-8")
    if a.out:
        Path(a.out).write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        _json_out({"stage": "outline", "deck": str(dp), "pages": len(pages),
                   "warnings": warns,
                   "deck_data": deck if a.embed else None}, a, ok=True)
    else:
        sys.stdout.write("分页方案已写出：%s（%d 页）\n" % (dp, len(pages)))
        sys.stdout.write(render_deck_md(deck))
    for w in warns:
        sys.stderr.write("⚠ %s\n" % w.get("detail"))
    return 0


def render_deck_md(deck):
    """把 deck 渲染成人读的 Markdown 分页稿。"""
    lines = ["# %s" % (deck.get("deck_title") or "课件"), "",
             "- 页数：%d" % len(deck.get("pages") or []),
             "- 版式：%s（%dx%d）" % (deck.get("ratio") or DECK_RATIO,
                                      DECK_TARGET_PX[0], DECK_TARGET_PX[1]),
             "- 受众水平：%s" % (deck.get("level") or "basic"), ""]
    for i, p in enumerate(deck.get("pages") or []):
        lines.append("## 第 %d 页　%s" % (i + 1, p.get("title") or "(无标题)"))
        lines.append("")
        lines.append("`%s` · `%s`" % (p.get("kind") or DEFAULT_PAGE_KIND, p.get("id") or ""))
        lines.append("")
        for b in page_bullets(p):
            lines.append("- %s" % b)
        if not page_bullets(p):
            lines.append("- （这一页没有要点）")
        lines.append("")
        if page_text_of(p, "notes"):
            lines.append("> **讲稿备注**：%s" % page_text_of(p, "notes"))
            lines.append("")
        if page_text_of(p, "image_intent"):
            lines.append("> **配图意图**：%s" % page_text_of(p, "image_intent"))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ===========================================================================
# 命令：pages —— 每页内容（成稿要点 + 讲稿备注）
# ===========================================================================

def cmd_pages(a):
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    deck, dp = load_deck(a)
    # 永远从**不可变的分页骨架**展开（手工写的 deck 没有它，就用当前 pages 兜底）。
    skeleton = deck.get("skeleton_pages") or deck.get("pages") or []
    pages = skeleton

    if a.from_file:
        raw = Path(a.from_file).read_text(encoding="utf-8-sig", errors="replace")
        obj = parse_first_json(raw)
        got = obj.get("pages") if isinstance(obj, dict) else None
        if not isinstance(got, list):
            raise a7w.A7wError("返回里没有 pages 数组：%s"
                               % json.dumps(obj, ensure_ascii=False)[:200])
        merged, warns = merge_page_content(pages, got)
        bad_all = gates_for_pages(merged, "页内容")
        bad_c, warns2 = check_pages_complete(merged, a.strict_notes, "页内容")
        bad_all += bad_c
        if bad_all:
            if a.json:
                _json_out({"stage": "gate", "count": len(bad_all), "blocked": bad_all}, a,
                          ok=False)
            _report_gate_bad(bad_all, "页内容未通过闸门，**没有写出任何文件**。")
            return _fail(3, "gate", "pages 闸门未通过：%d 项" % len(bad_all))
        deck["pages"] = merged
        deck.setdefault("skeleton_pages", json.loads(json.dumps(pages, ensure_ascii=False)))
        deck["stage"] = "pages"
        save_deck(deck, dp)
        sys.stdout.write("页内容已写出：%s（%d 页）\n" % (dp, len(merged)))
        return 0

    state_p = outdir / STATE_NAME
    state = load_state(state_p)
    sys.stderr.write("pages：%d 页，按 %d 页一批展开…\n" % (len(pages), PAGES_PER_CALL))
    result, warns, usage_total, calls, skipped = [], [], {}, 0, 0
    for start in range(0, len(pages), PAGES_PER_CALL):
        batch = pages[start:start + PAGES_PER_CALL]
        key = "batch:%s:%s:%s" % (
            hashlib.sha1(json.dumps(batch, ensure_ascii=False).encode("utf-8")).hexdigest()[:16],
            a.model, PROMPT_VERSION)
        dims = {"model": a.model, "level": deck.get("level") or a.level,
                "prompt_version": PROMPT_VERSION}
        if not a.force and state_check(state, key, dims, "pages 断点"):
            rec = state["items"][key]
            result.extend(rec.get("pages") or [])
            sys.stderr.write("[%d/%d] 已有成稿，跳过（断点续跑，不再重复扣费）\n"
                             % (start // PAGES_PER_CALL + 1,
                                (len(pages) + PAGES_PER_CALL - 1) // PAGES_PER_CALL))
            skipped += 1
            continue
        if a.budget is not None:
            est = estimate_text_cost(max(1, len(batch)), False, True, a.yuan_per_ktok)
            spent = sum(usage_total.values()) / 1000.0 * float(a.yuan_per_ktok or 0)
            if (spent + (est["total_yuan"] or 0)) > a.budget:
                msg = ("累计预计 %.4f 元超过预算上限 %g 元（文本口径 %.4f 元/千 token "
                       "**估算**），**已中断，未发起这一次调用**"
                       % (spent + (est["total_yuan"] or 0), a.budget,
                          float(a.yuan_per_ktok or 0)))
                sys.stderr.write("\n%s\n" % _red(msg))
                return _fail(3, "budget", msg)
        prompt = build_pages_prompt(batch, deck.get("level") or a.level, a.style)
        if a.dry_run:
            sys.stderr.write("=== 第 %d 批提示词（--dry-run）===\n%s\n---\n%s\n"
                             % (start // PAGES_PER_CALL + 1, SYSTEM_PAGES, prompt))
            continue
        content, usage = chat(prompt, SYSTEM_PAGES, a.model, a.temperature,
                              a.max_tokens, a.key, not a.no_json_mode)
        calls += 1
        for k, v in (usage or {}).items():
            if isinstance(v, int):
                usage_total[k] = usage_total.get(k, 0) + v
        got = (parse_first_json(content) or {}).get("pages")
        if not isinstance(got, list):
            raise a7w.A7wError("这一批返回里没有 pages 数组")
        merged, w = merge_page_content(batch, got)
        result.extend(merged)
        warns.extend(w)
        state["items"][key] = {"model": a.model, "level": deck.get("level") or a.level,
                               "prompt_version": PROMPT_VERSION, "pages": merged}
        save_state(state_p, state)
        sys.stderr.write("[%d/%d] 完成\n" % (start // PAGES_PER_CALL + 1,
                                            (len(pages) + PAGES_PER_CALL - 1) // PAGES_PER_CALL))
    if a.dry_run:
        return 0

    bad = gates_for_pages(result, "页内容")
    bad_c, warns2 = check_pages_complete(result, a.strict_notes, "页内容")
    bad += bad_c
    warns.extend(warns2)
    if bad:
        if a.json:
            _json_out({"stage": "gate", "count": len(bad), "blocked": bad}, a, ok=False)
        _report_gate_bad(bad, "页内容未通过闸门，**没有写出任何文件**。"
                              "成稿有问题的页会一页一页被学员看到，先在源头改掉。")
        return _fail(3, "gate", "pages 闸门未通过：%d 项" % len(bad))

    deck["pages"] = result
    deck["skeleton_pages"] = json.loads(json.dumps(pages, ensure_ascii=False))
    deck["stage"] = "pages"
    save_deck(deck, dp)
    (outdir / DECK_MD_NAME).write_text(render_deck_md(deck), encoding="utf-8")
    ti = sum(v for k, v in usage_total.items() if k == "prompt_tokens")
    to = sum(v for k, v in usage_total.items() if k == "completion_tokens")
    summary = {"stage": "pages", "deck": str(dp), "pages": len(result),
               "calls": calls, "skipped_batches": skipped,
               "usage_prompt_tokens": ti, "usage_completion_tokens": to,
               "warnings": warns}
    if a.json:
        _json_out(summary, a, ok=True)
    else:
        sys.stdout.write("页内容已写出：%s（%d 页；%d 次调用，跳过 %d 批）\n"
                         % (dp, len(result), calls, skipped))
        sys.stdout.write(render_deck_md(deck))
    for w in warns:
        sys.stderr.write("⚠ %s\n" % w.get("detail"))
    return 0


def merge_page_content(skeleton, got):
    """把展开结果合并回骨架：**以骨架的页序与页标题为准**，成稿内容只认模型返回的。

    ⚠️ 实测踩过一次**最危险的"静默修复"**：早期版本写的是
    `merged["bullets"] = cand["bullets"] or sk["bullets"]` ——
    模型**明确返回了空要点**（或压根没返回这一页）时，`or` 会退回**骨架里的粗要点**，
    于是"空页"被悄悄补上了草稿，**闸门五读到的是补过之后的内容 → 全绿**。
    用户拿到的是一份"每页都有要点"但要点其实是分页草稿的课件，而且报告说一切正常。
    这就是同族「静默截断 / 静默留空」的第三个兄弟：**静默兜底**。
    所以现在的口径是：**模型返回空就是空，不拿骨架兜底**，交给闸门五去拦。
    （`image_intent` 例外：它是分页阶段的产物、`outline` 已经校验过，
      模型不重复返回时沿用骨架的画面描述属于正常合并，不属于"补内容"。）
    """
    by_id = {}
    for i, o in enumerate(got):
        n = norm_page(o, i)
        if n:
            by_id.setdefault(n["id"], n)
    out, warns = [], []
    used = set()
    for i, sk in enumerate(skeleton):
        cand = by_id.get(sk.get("id")) or (norm_page(got[i], i) if i < len(got) else None)
        if cand and cand["id"] in by_id:
            used.add(cand["id"])
        merged = dict(sk)
        merged["bullets"] = list(cand["bullets"]) if cand else []      # 不兜底
        merged["notes"] = (cand["notes"] if cand else "")              # 不兜底
        merged["image_intent"] = ((cand["image_intent"] if cand else "")
                                  or (sk.get("image_intent") or ""))
        # ⚠️ **`kind` 是分页阶段的决定，展开阶段不许改它。**
        #    实测踩过（而且是**肉眼看图才发现、所有闸门与像素检查全绿**的那一类）：
        #    `SYSTEM_PAGES` 并不要求模型返回 `kind`，而 `norm_page` 会把缺省值补成
        #    `"content"`，于是 `merged["kind"] = cand["kind"]` 把首尾页的
        #    cover / section / summary **静默降级成全篇 content** ——
        #    封面页丢掉了整幅铺底的版式，封面看起来和普通内容页一模一样。
        #    所以 `kind` 只认骨架；只有骨架自己没给出合法 kind 时才回落到模型值。
        if merged.get("kind") not in PAGE_KINDS and cand \
                and cand.get("kind") in PAGE_KINDS:
            merged["kind"] = cand["kind"]
        out.append(merged)
    extra = [k for k in by_id if k not in used]
    if extra:
        warns.append({"id": ",".join(extra), "title": "",
                      "detail": "模型多返回了 %d 页（%s），已忽略——页序与页数由分页方案定死"
                                % (len(extra), ",".join(extra))})
    if len(got) < len(skeleton):
        warns.append({"id": "-", "title": "",
                      "detail": "模型只返回 %d 页，骨架有 %d 页；缺的页按空页处理（会被闸门拦下）"
                                % (len(got), len(skeleton))})
    return out, warns


# ===========================================================================
# 命令：images —— 按页出配图
# ===========================================================================

def _quote_lines(sel, flags, cost, a, outdir):
    lines = ["本次要出 %d 张配图 → %s" % (len(sel), outdir / IMAGES_SUBDIR),
             "  " + fmt_image_cost(cost)]
    for i, (p, has) in enumerate(zip(sel, flags)):
        if not has:
            continue
        lines.append("  #%-5s %-8s %-6s %s" % (p.get("id"), p.get("kind"),
                                               DECK_GEN_RATIO, p.get("title")))
    if a.budget is not None:
        ty = cost["total_yuan"]
        ok = (ty is not None and ty <= a.budget)
        lines.append("  预算 %g 元：%s" % (a.budget, "在预算内" if ok else "超了，会被拦下"))
    return lines


def _print_quote(lines, to_stderr=False):
    out = sys.stderr if to_stderr else sys.stdout
    for ln in lines:
        out.write(ln + "\n")


def cmd_images(a):
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    deck, _ = load_deck(a)
    pages_all = deck.get("pages") or []
    every = int(a.every or deck.get("every") or 1)
    flags_all = pages_with_image(pages_all, every)
    pairs = list(zip(pages_all, flags_all))
    if a.only:
        ids = {s.strip() for s in a.only.split(",") if s.strip()}
        pairs = [(p, f) for (p, f) in pairs if p.get("id") in ids]
    if a.count:
        pairs = pairs[:a.count]
    sel = [p for (p, f) in pairs if f]
    if not sel:
        raise UsageError("按 --only / --count / --every=%d 过滤后没有需要出图的页" % every)

    # ---- 闸门五：页内容完整性（**在花钱之前**）----
    bad_c, _w = check_pages_complete(sel, False, "待出图的页")
    if bad_c:
        if a.json:
            _json_out({"stage": "gate", "count": len(bad_c), "blocked": bad_c}, a, ok=False)
        _report_gate_bad(bad_c, "有 %d 页内容不完整，**已拦截，未提交任何任务（不花一分钱）**。"
                                "\n空页 / 缺要点的页就算出了图也不能用，先在源头补上。"
                                % len(bad_c))
        return _fail(3, "gate", "闸门五：%d 页内容不完整，未提交任何任务" % len(bad_c))

    # ---- 闸门一 / 二 / 三：出图提示词 ----
    prompt_bad = []
    for p in sel:
        leaks = text_gate(image_prompt_of(p), "第 %s 页配图提示词" % p.get("id"))
        if leaks:
            prompt_bad.append({"id": p.get("id"), "title": p.get("title"), "leaks": leaks})
    if prompt_bad and not a.allow_prompt_hits:
        if a.json:
            _json_out({"stage": "gate", "count": len(prompt_bad), "blocked": prompt_bad},
                      a, ok=False)
        _report_gate_bad(prompt_bad, "有 %d 页的出图提示词命中闸门，**已拦截，未提交任何任务**。"
                                     % len(prompt_bad))
        return _fail(3, "gate", "闸门一/二/三：%d 页提示词不合格，未提交任何任务"
                     % len(prompt_bad))

    resolution = a.resolution or deck.get("resolution") or "1K"
    gen_ratio = a.ratio or deck.get("gen_ratio") or DECK_GEN_RATIO
    cost = estimate_image_cost(len(sel), resolution, a.points_per_image)

    # ---- 闸门七：成本上限（**在提交任何任务之前**）----
    if cost["total_points"] is None:
        msg = ("%s 档没有实测单价，**拒绝凭猜估算**（只有 1K 有实测价 24 点/张）。"
               "给 --points-per-image 指定单价，或先用 1K 出。" % resolution)
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "budget", msg)
    if a.budget is not None and cost["total_yuan"] > a.budget:
        msg = ("预估 %g 点 = %.2f 元，超过预算上限 %g 元，**已中断，未提交任何任务**"
               % (cost["total_points"], cost["total_yuan"], a.budget))
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "budget", msg)

    lines = _quote_lines(sel, [True] * len(sel), cost, a, outdir)
    need_yes = not a.yes and a.budget is None
    if need_yes or a.dry_run:
        if a.json:
            for ln in lines:
                sys.stderr.write(ln + "\n")
            _json_out({"stage": "quote", "outdir": str(outdir), "cost": cost,
                       "items": [{"id": p.get("id"), "title": p.get("title")}
                                 for p in sel]}, a, ok=not need_yes)
        else:
            _print_quote(lines)
        if a.dry_run:
            return 0
        sys.stderr.write("\n**这是一次真花钱的操作。**\n\n")
        sys.stderr.write("\n确认后加 --yes 重跑（或用 --budget 设上限）。\n")
        return _fail(4, "call", "需要 --yes 确认（还没花钱，也没提交）")

    if a.json:
        for ln in lines:
            sys.stderr.write(ln + "\n")
    else:
        _print_quote(lines)
    sys.stderr.write("\n开始出图…\n")
    return _run_images(a, sel, deck, outdir, cost, resolution, gen_ratio, every, pairs)


def _run_images(a, sel, deck, outdir, cost, resolution, gen_ratio, every, pairs):
    img_dir = outdir / IMAGES_SUBDIR
    img_dir.mkdir(parents=True, exist_ok=True)
    state_p = outdir / STATE_NAME
    state = load_state(state_p)
    done, gate_bad, ratio_bad, spent_pts = [], [], [], 0.0
    for i, p in enumerate(sel, 1):
        pid = p.get("id") or ("p%02d" % i)
        dst = img_dir / ("%s.png" % pid)
        prompt = image_prompt_of(p)
        model = a.model_image or "nano-banana"
        key = image_state_key(p, gen_ratio, resolution, model)
        dims = {"gen_ratio": gen_ratio, "resolution": resolution, "model": model,
                "prompt_digest": prompt_digest(prompt)}
        prev = (state.get("items") or {}).get(key)
        if not a.force and prev and Path(dst).is_file() and state_check(state, key, dims,
                                                                       "出图断点") \
                and state_artifact_ok(prev, dst, "出图断点"):
            sys.stderr.write("[%d/%d] #%s 已有图，跳过（断点续跑，不再重复扣费）\n"
                             % (i, len(sel), pid))
            done.append({"id": pid, "file": str(dst), "points_cost": prev.get("points_cost"),
                         "skipped": True, "real_px": list(imgprobe.image_size(dst)[:2])})
            continue
        # 已提交未完成 → 续查 task_id，**绝不重新提交**（否则白扣一次费）
        if not a.force and prev and prev.get("task_id") and not Path(dst).is_file():
            st, data, _pl, ticks = poll_task(prev["task_id"], a.key, a.poll_timeout,
                                             on_tick=lambda s, d: sys.stderr.write(
                                                 "  #%s 任务状态 %s\n" % (pid, s)))
            if st == "completed":
                urls = find_image_urls(data)
                if urls:
                    nbytes = download(urls[0], dst, key=a.key)
                    pts = points_cost(data)
                    rec = dict(prev)
                    rec.update({"points_cost": pts, "url": urls[0], "bytes": nbytes})
                    state["items"][key] = stamp_artifact(rec, dst)
                    save_state(state_p, state)
                    sys.stderr.write("  #%s 续查成功（未重新提交，0 点）\n" % pid)
                    done.append({"id": pid, "file": str(dst), "points_cost": pts,
                                 "recovered": True, "real_px": list(imgprobe.image_size(dst)[:2])})
                    continue
            sys.stderr.write("  #%s 续查未完成（%s），本次重新提交\n" % (pid, st))

        if a.budget is not None and (spent_pts / float(POINTS_PER_YUAN)) > a.budget:
            msg = ("本次已产生 %.2f 元，超过预算上限 %g 元，**已停止继续提交**"
                   % (spent_pts / float(POINTS_PER_YUAN), a.budget))
            sys.stderr.write("\n%s\n" % _red(msg))
            return _fail(3, "budget", msg)
        sys.stderr.write("[%d/%d] #%s 提交出图任务…\n" % (i, len(sel), pid))
        data = submit_image(prompt, gen_ratio, resolution, model, key=a.key)
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise a7w.A7wError("提交后没有拿到 task_id：%s"
                               % json.dumps(data, ensure_ascii=False)[:200])
        rec = {"task_id": task_id, "status": "submitted", "gen_ratio": gen_ratio,
               "resolution": resolution, "model": model, "prompt_digest": prompt_digest(prompt),
               "frozen_points": data.get("frozen_points")}
        state["items"][key] = rec
        save_state(state_p, state)

        st, tdata, _pl, ticks = poll_task(
            task_id, a.key, a.poll_timeout,
            on_tick=lambda s, d: sys.stderr.write("  #%s 任务状态 %s\n" % (pid, s)))
        if st != "completed":
            sys.stderr.write("  %s #%s 任务未成功（%s）；task_id 已记进断点文件，"
                             "重跑会**续查**而不是重新提交（不重复扣费）\n"
                             % (_red("[未完成]"), pid, st))
            return _fail(4, "call", "出图任务未完成：%s（%s）" % (pid, st))

        urls = find_image_urls(tdata)
        if not urls:
            raise a7w.A7wError("#%s 任务完成但没有图片地址：%s"
                               % (pid, json.dumps(tdata, ensure_ascii=False)[:200]))
        nbytes = download(urls[0], dst, key=a.key)
        pts = points_cost(tdata)
        if pts:
            spent_pts += pts
        # ---- 闸门四：比例真伪（读真实像素，不信自报值）----
        if a.snap:
            snap_to_ratio(dst, dst, gen_ratio)
        chk = check_ratio(dst, gen_ratio, a.ratio_tolerance)
        if not chk["ok"]:
            ratio_bad.append({"id": pid, "leaks": [("ratio_fake", chk["why"])]})
        rec.update({"status": "completed", "points_cost": pts, "url": urls[0],
                    "bytes": nbytes, "real_px": chk["real_px"],
                    "real_label": chk["real_label"], "deviation": chk["deviation"]})
        # 盖上产物身份（字节数 + mtime）：换了 resolution / ratio 会写同名文件，
        # 切回旧档位时只靠 key 命中会静默复用别人的图（与 render 同一个坑）。
        state["items"][key] = stamp_artifact(rec, dst)
        save_state(state_p, state)
        sys.stderr.write("  %s #%s %s（%s 点，%d 字节）\n"
                         % ("[完成]" if chk["ok"] else _red("[比例存疑]"), pid,
                            chk["why"], pts, nbytes))
        done.append({"id": pid, "file": str(dst), "points_cost": pts,
                     "real_px": chk["real_px"], "real_label": chk["real_label"],
                     "deviation": chk["deviation"], "ratio_ok": chk["ok"],
                     "bytes": nbytes, "url": urls[0]})

    # 逐页复核：**应该**有图的页是否真有图（不静默漏页）
    missing = [p.get("id") for p in sel if not (img_dir / ("%s.png" % p.get("id"))).is_file()]
    if missing:
        sys.stderr.write("%s 这些页没有拿到图：%s\n" % (_red("[缺图]"), ",".join(missing)))

    deck["images"] = done
    deck["every"] = every
    save_deck(deck, outdir / DECK_NAME)

    if ratio_bad:
        if a.json:
            _json_out({"stage": "gate", "count": len(ratio_bad), "blocked": ratio_bad,
                       "images": done}, a, ok=False)
        _report_gate_bad(ratio_bad,
                         "有 %d 张图的**真实像素**与请求比例不符（闸门四：只信真实像素），"
                         "请用 `--snap` 重跑这几页。" % len(ratio_bad))
        return _fail(3, "gate", "闸门四：%d 张图比例不符" % len(ratio_bad))

    summary = {"stage": "images", "outdir": str(img_dir), "count": len(done),
               "images": done, "points_total": round(spent_pts, 2),
               "yuan_total": round(spent_pts / float(POINTS_PER_YUAN), 2),
               "missing": missing}
    if a.json:
        _json_out(summary, a, ok=True)
    else:
        sys.stdout.write("\n出图完成：%d 张，共 %.2f 点 = %.2f 元（只信 usage.points_cost）\n"
                         % (len(done), spent_pts, spent_pts / float(POINTS_PER_YUAN)))
    return 0


# ===========================================================================
# 命令：render —— 本地排版成逐页 PNG（零成本、零网络）
# ===========================================================================

def cmd_render(a):
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    if not has_pil():
        msg = ("没有 PIL：本地排版成逐页 PNG 需要 PIL（pip install pillow）。"
               "**拒绝静默产出一份没有版式的课件**，也拒绝假装成功。"
               "装上 pillow 后**原样重跑同一条命令即可**（断点续跑不会重复扣钱）。"
               "如果确实不装 PIL：本包不提供 PPTX 直出（python-pptx 同样不是标准库），"
               "这一步没有降级路径。")
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(2, "usage", msg)

    deck, dp = load_deck(a)
    pages_all = deck.get("pages") or []
    pages = selected_pages(pages_all, a)
    if not pages:
        if not pages_all:
            # ⚠️ 分页方案本身一页都没有 → 这是**闸门五**（exit=3），不是用法错误（exit=2）。
            #    两者分开是有意的：exit=3 = "上游没问题，是被本地规则拦了"；
            #    exit=2 = "你命令用错了"。空方案是产出不合格，不是命令写错。
            bad = [{"id": "-", "leaks": [
                ("no_pages", "分页方案 %s 里**一页都没有**（页数为 0）—— "
                             "拒绝产出一份空课件。先跑 `outline` 出分页方案。" % dp)]}]
            if a.json:
                _json_out({"stage": "gate", "count": 1, "blocked": bad}, a, ok=False)
            _report_gate_bad(bad, "闸门五：页数为 0，**一张 slide 都没有写出**。")
            return _fail(3, "gate", "闸门五：页数为 0，未渲染任何页")
        raise UsageError("--only / --count 过滤后没有可渲染的页（分页方案里有 %d 页）"
                         % len(pages_all))

    theme = a.theme or deck.get("theme") or "ink"
    if theme not in THEMES:
        raise UsageError("--theme 只能是 %s，收到 %r" % (" / ".join(THEME_CHOICES), theme))
    width, height = DECK_TARGET_PX
    font_path, candidates = find_font(a.font)
    if not font_path:
        msg = ("系统里找不到可用的中文字体（找过：%s）。"
               "本地排版必须有一个能渲染中文的字体——**拒绝产出一份中文方块图**。"
               "用 `--font <字体文件路径>` 指定一个。" % " ; ".join(candidates))
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(2, "usage", msg)

    every = int(a.every or deck.get("every") or 1)
    flags = pages_with_image(pages_all, every)
    flag_of = {p.get("id"): f for p, f in zip(pages_all, flags)}
    img_dir = outdir / IMAGES_SUBDIR

    # ---- 闸门一 / 二 / 三：文本 ----
    gate_bad = gates_for_pages(pages, "页内容")
    # ---- 闸门五：每页内容完整性 ----
    bad_c, warns = check_pages_complete(pages, a.strict_notes, "页内容")
    gate_bad += bad_c

    # ---- 闸门四：配图比例真伪（render 是最后一道防线，**再读一次真实像素**）----
    ratio_notes, ratio_bad = [], []
    for p in pages:
        fp = img_dir / ("%s.png" % (p.get("id") or ""))
        if not fp.is_file():
            continue
        chk = check_ratio(fp, p.get("gen_ratio") or deck.get("gen_ratio") or DECK_GEN_RATIO,
                          a.ratio_tolerance)
        (ratio_notes if chk["ok"] else ratio_bad).append(
            {"id": p.get("id"), "file": str(fp), "real_px": chk["real_px"],
             "real_label": chk["real_label"], "deviation": chk["deviation"],
             "why": chk["why"]})
        if not chk["ok"]:
            gate_bad.append({"id": p.get("id"), "title": p.get("title"),
                             "leaks": [("ratio_fake", chk["why"])]})

    # ---- 闸门六：文字溢出（**用真实字体排版后判定**，报出实际像素）----
    plans, plan_bad = [], []
    for i, p in enumerate(pages):
        pid = p.get("id") or ("p%02d" % (i + 1))
        has_img = bool(flag_of.get(p.get("id"), True)) and (img_dir / ("%s.png" % pid)).is_file()
        plan = plan_page(p, has_img, font_path, width, height, theme)
        plans.append((p, plan, has_img))
        if not plan["ok"]:
            plan_bad.append({"id": pid, "title": page_text_of(p, "title"),
                             "leaks": [(o.get("reason") or "text_overflow", o.get("detail"))
                                       for o in plan["overflow"]]})

    missing_img = [p.get("id") for p, _pl, _h in plans
                   if flag_of.get(p.get("id"), True)
                   and not (img_dir / ("%s.png" % (p.get("id") or ""))).is_file()]

    if gate_bad or plan_bad:
        if a.json:
            _json_out({"stage": "gate", "count": len(gate_bad) + len(plan_bad),
                       "blocked": gate_bad + plan_bad,
                       "ratio_checked": ratio_notes, "missing_images": missing_img}, a,
                      ok=False)
        if plan_bad:
            sys.stderr.write("\n")
            for b in plan_bad:
                for kind, why in b["leaks"]:
                    sys.stderr.write("   %s #%s %s\n" % (_red("[%s]" % kind), b["id"], why))
            sys.stderr.write("\n%s\n" % _red(
                "有 %d 页的文字放不进版心，**一张 slide 都没有写出**。\n"
                "上限：标题 ≤ %d 字 / %d 行，每条要点 ≤ %d 字，每页 ≤ %d 条要点。\n"
                "**不做静默截断、也不自动缩字号**——放了十几年投影的经验是："
                "缩到看不清比缺一句话更糟。请改内容，不要改闸门。"
                % (len(plan_bad), TITLE_MAX_CHARS, TITLE_MAX_LINES,
                   BULLET_MAX_CHARS, BULLET_MAX_ITEMS)))
        if gate_bad:
            _report_gate_bad(gate_bad, "render 闸门未通过，**一张 slide 都没有写出**。")
        return _fail(3, "gate", "render 闸门未通过：%d 项" % (len(gate_bad) + len(plan_bad)))

    # ---- 渲染 ----
    slides_dir = outdir / SLIDES_SUBDIR
    slides_dir.mkdir(parents=True, exist_ok=True)
    state_p = outdir / STATE_NAME
    state = load_state(state_p)
    deck_title = deck.get("deck_title") or deck.get("topic") or "课件"
    total = len(plans)
    out_recs, skipped = [], 0
    for i, (p, plan, has_img) in enumerate(plans, 1):
        pid = p.get("id") or ("p%02d" % i)
        dst = slides_dir / ("slide-%02d.png" % i)
        img_path = (img_dir / ("%s.png" % pid)) if has_img else None
        params = {"layout_version": LAYOUT_VERSION, "theme": theme, "font": font_path,
                  "width": width, "height": height, "page_no": i, "total": total}
        key = render_state_key(p, img_path, params)
        dims = {"layout_version": LAYOUT_VERSION, "theme": theme, "font": font_path,
                "width": width, "height": height, "page_no": i, "total": total}
        # 断点命中要过两关：① key 的所有维度都对得上 ② **产物文件本身的身份**也对得上
        # （② 是命门：换了主题重渲会把同名文件覆盖掉，切回旧主题时只查 ① 会静默复用别人的图）
        reuse = (not a.force and Path(dst).is_file()
                 and state_check(state, key, dims, "渲染断点")
                 and state_artifact_ok(state["items"].get(key), dst, "渲染断点"))
        if reuse:
            st = Path(dst).stat()
            w, h, _f = imgprobe.image_size(dst)
            out_recs.append({"page": i, "id": pid, "file": str(dst), "skipped": True,
                             "bytes": st.st_size, "out_px": [w, h], "theme": theme,
                             "layout_version": LAYOUT_VERSION})
            skipped += 1
            sys.stderr.write("[%d/%d] #%s 已渲染，跳过（断点续跑）\n" % (i, total, pid))
            continue
        rec = render_page(p, plan, dst, theme, font_path, width, height, img_path,
                          i, total, deck_title)
        if not rec.get("ok"):
            sys.stderr.write("\n%s\n" % _red("渲染 #%s 失败：%s" % (pid, rec.get("why"))))
            return _fail(2, "usage", "渲染失败：%s" % rec.get("why"))
        rec.update({"page": i, "id": pid, "file": str(dst), "skipped": False})
        out_recs.append(rec)
        rec_state = {"layout_version": LAYOUT_VERSION, "theme": theme,
                     "font": font_path, "width": width, "height": height,
                     "page_no": i, "total": total}
        # 盖上**产物身份**（字节数 + mtime）。下次断点命中时要靠它确认
        # 磁盘上的文件确实是"这一组版式参数"产出的，而不是被别的主题覆盖过。
        state["items"][key] = stamp_artifact(rec_state, dst)
        save_state(state_p, state)
        sys.stderr.write("[%d/%d] #%s → %s（%dx%d，%d 字节）\n"
                         % (i, total, pid, dst.name, rec["out_px"][0], rec["out_px"][1],
                            rec["size_bytes"]))

    # ---- 讲稿备注 ----
    notes_p = outdir / NOTES_NAME
    notes_p.write_text(render_notes_md(deck, pages), encoding="utf-8")
    html_p = None
    if a.html:
        html_p = outdir / HTML_NAME
        html_p.write_text(render_deck_html(deck, pages, out_recs, theme), encoding="utf-8")
    audit = render_audit_md(deck, pages, out_recs, theme, font_path, ratio_notes,
                            missing_img, warns)
    (outdir / AUDIT_NAME).write_text(audit, encoding="utf-8")
    deck["theme"] = theme
    deck["stage"] = "render"
    deck["render"] = {"layout_version": LAYOUT_VERSION, "slides": out_recs,
                      "notes": str(notes_p), "html": (str(html_p) if html_p else None)}
    save_deck(deck, outdir / DECK_NAME)

    summary = {"stage": "render", "outdir": str(slides_dir), "pages": len(out_recs),
               "skipped": skipped, "slides": out_recs, "notes": str(notes_p),
               "html": (str(html_p) if html_p else None), "theme": theme,
               "font": font_path, "layout_version": LAYOUT_VERSION,
               "ratio_checked": ratio_notes, "missing_images": missing_img,
               "warnings": warns}
    if a.json:
        _json_out(summary, a, ok=True)
    else:
        sys.stdout.write("\n课件已排版完成：%s（%d 页，跳过 %d 页）\n"
                         % (slides_dir, len(out_recs), skipped))
        sys.stdout.write("讲稿备注：%s\n" % notes_p)
        if html_p:
            sys.stdout.write("HTML（可直接打印 / 转 PPT）：%s\n" % html_p)
        for r in out_recs:
            sys.stdout.write("  %s  %dx%d  %d 字节%s\n"
                             % (Path(r["file"]).name, r["out_px"][0], r["out_px"][1],
                                r.get("bytes") or r.get("size_bytes") or 0,
                                "（跳过）" if r.get("skipped") else ""))
    for w in warns:
        sys.stderr.write("⚠ %s\n" % w.get("detail"))
    if missing_img:
        sys.stderr.write("⚠ 这些页按**无图版式**渲染（没找到配图）：%s\n" % ",".join(missing_img))
    return 0


def render_notes_md(deck, pages):
    """讲稿备注单独成册（讲课的人只需要这一份）。"""
    lines = ["# %s · 讲稿备注" % (deck.get("deck_title") or deck.get("topic") or "课件"),
             "",
             "> 每一页对应一张 slide；页码与 `slides/slide-NN.png` 一一对应。", ""]
    for i, p in enumerate(pages, 1):
        lines.append("## 第 %d 页　%s" % (i, page_text_of(p, "title") or "(无标题)"))
        lines.append("")
        for b in page_bullets(p):
            lines.append("- %s" % b)
        lines.append("")
        notes = page_text_of(p, "notes").strip()
        lines.append(notes if notes else "（这一页没有讲稿备注）")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_deck_html(deck, pages, recs, theme):
    """一份自包含 HTML：每页一张图 + 备注，方便打印或粘进 PPT。"""
    th = THEMES.get(theme, THEMES["ink"])
    bg = "#%02X%02X%02X" % th["bg"]
    fg = "#%02X%02X%02X" % th["title"]
    by_page = {r.get("page"): r for r in recs}
    out = ["<!DOCTYPE html>", '<html lang="zh-CN"><head><meta charset="utf-8">',
           "<title>%s</title>" % (deck.get("deck_title") or "课件"),
           "<style>",
           "body{margin:0;background:%s;color:%s;font-family:system-ui,'Microsoft YaHei',sans-serif}" % (bg, fg),
           ".slide{page-break-after:always;break-after:page;padding:24px 0;text-align:center}",
           ".slide img{max-width:100%;box-shadow:0 2px 12px rgba(0,0,0,.18)}",
           ".notes{max-width:960px;margin:12px auto 0;text-align:left;font-size:15px;line-height:1.7}",
           ".meta{font-size:13px;opacity:.7;margin-top:6px}",
           "@media print{body{background:#fff}.notes{display:none}}",
           "</style></head><body>",
           "<h1 style='text-align:center;padding:18px 0'>%s</h1>"
           % (deck.get("deck_title") or "课件")]
    for i, p in enumerate(pages, 1):
        r = by_page.get(i) or {}
        rel = Path(r["file"]).name if r.get("file") else ""
        out.append('<div class="slide">')
        if rel:
            out.append('<img src="%s/%s" alt="第 %d 页">' % (SLIDES_SUBDIR, rel, i))
        out.append('<div class="notes"><strong>第 %d 页　%s</strong><br>%s</div>'
                   % (i, _html_escape(page_text_of(p, "title")),
                      "<br>".join("- " + _html_escape(b) for b in page_bullets(p))))
        n = _html_escape(page_text_of(p, "notes"))
        if n:
            out.append('<div class="notes"><em>讲稿备注</em><br>%s</div>' % n)
        out.append('<div class="meta">%s</div>' % _html_escape(rel))
        out.append("</div>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def _html_escape(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_audit_md(deck, pages, recs, theme, font_path, ratio_notes, missing_img, warns):
    th = THEMES.get(theme, THEMES["ink"])
    lines = ["# 课件自检报告（AUDIT）", "",
             "| 项 | 值 |", "|---|---|",
             "| 课件名 | %s |" % (deck.get("deck_title") or "-"),
             "| 页数 | %d |" % len(pages),
             "| 画布 | %dx%d |" % DECK_TARGET_PX,
             "| 主题 | %s（%s） |" % (theme, th["name"]),
             "| 字体 | `%s` |" % font_path,
             "| 版式版本 | %d |" % LAYOUT_VERSION,
             "| 工具版本 | %s |" % VERSION, ""]
    lines += ["## 闸门结果", "",
              "| # | 闸门 | 结论 |", "|---|---|---|",
              "| 1 | 合规（广告法 + 教育类效果承诺） | 通过 |",
              "| 2 | 占位符残留 | 通过 |",
              "| 3 | prompt_echo（照抄提示词示例） | 通过 |",
              "| 4 | 配图比例真伪（读真实像素） | %s |"
              % ("通过（%d 张复核）" % len(ratio_notes) if ratio_notes else "本次无配图"),
              "| 5 | 每页内容完整性（标题 + ≥1 条要点） | 通过 |",
              "| 6 | 文字溢出（真实字体排版） | 通过 |", ""]
    lines += ["## 逐页产出", "",
              "| 页 | id | 标题 | 输出像素 | 字节 | 配图 |", "|---|---|---|---|---|---|"]
    for r in recs:
        p = pages[r["page"] - 1] if r["page"] - 1 < len(pages) else {}
        lines.append("| %d | %s | %s | %dx%d | %d | %s |"
                     % (r["page"], r.get("id"), page_text_of(p, "title"),
                        r["out_px"][0], r["out_px"][1],
                        r.get("bytes") or r.get("size_bytes") or 0,
                        Path(r["used_image"]).name if r.get("used_image") else "无（无图版式）"))
    if ratio_notes:
        lines += ["", "## 配图比例复核（真实像素）", "",
                  "| 页 | 文件 | 真实像素 | 比例 | 偏差 |", "|---|---|---|---|---|"]
        for r in ratio_notes:
            dev = ("%.2f%%" % (r["deviation"] * 100)) if r["deviation"] is not None else "-"
            lines.append("| %s | %s | %dx%d | %s | %s |"
                         % (r["id"], Path(r["file"]).name, r["real_px"][0], r["real_px"][1],
                            r["real_label"], dev))
    if missing_img:
        lines += ["", "## 按无图版式渲染的页", "",
                  "这些页**没有找到配图**，已按无图版式（文字占满版心）渲染：",
                  "", "- " + "、".join(missing_img)]
    if warns:
        lines += ["", "## 告警（不拦，但请看一眼）", ""]
        for w in warns:
            lines.append("- %s" % w.get("detail"))
    lines += ["", "---", "",
              "> 本报告由 `scripts/run.py` 本地生成，**零网络**。",
              "> 违禁词表是启发式自检工具，不构成法律意见；",
              "> 课件内容的事实性、版权与宣发合规责任由使用者承担。"]
    return "\n".join(lines).rstrip() + "\n"


# ===========================================================================
# 命令：all / cost / models
# ===========================================================================

def cmd_all(a):
    outdir = Path(a.outdir)
    ensure_outside_pkg(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    force = bool(getattr(a, "force", False))
    # [1] outline
    dp = outdir / DECK_NAME
    have_content = False
    if dp.is_file() and not force:
        try:
            obj = json.loads(dp.read_text(encoding="utf-8"))
            have_content = bool(obj.get("pages")) and obj.get("stage") in ("pages", "render")
        except (OSError, ValueError):
            have_content = False
    if have_content:
        sys.stderr.write("[1/4] 分页方案已完成，跳过（断点续跑，不再重复扣费）\n")
    else:
        sys.stderr.write("[1/4] 分页方案…\n")
        rc = cmd_outline(_clone_args(a, from_file=None, is_result=False, embed=False, out=None))
        if rc:
            return rc
    # [2] pages
    if have_content:
        sys.stderr.write("[2/4] 页内容已完成，跳过\n")
    else:
        sys.stderr.write("[2/4] 页内容…\n")
        rc = cmd_pages(_clone_args(a, from_file=None))
        if rc:
            return rc
    # [3] images
    deck, _ = load_deck(a)
    if deck.get("images") and not force:
        sys.stderr.write("[3/4] 配图已完成，跳过\n")
    else:
        sys.stderr.write("[3/4] 配图（真花钱，先报价）…\n")
        rc = cmd_images(_clone_args(a, only=None, count=None))
        if rc:
            return rc
    # [4] render
    sys.stderr.write("[4/4] 本地排版…\n")
    return cmd_render(_clone_args(a, only=None, count=None))


def cmd_cost(a):
    resolution = a.resolution or "1K"
    n_pages = int(a.pages or 12)
    every = max(1, int(a.every or 1))
    if not a.with_text:
        a.with_outline = a.with_pages = False
    n_images = int(a.images) if a.images is not None else (
        (n_pages + every - 1) // every if a.with_images else 0)
    imgs = estimate_image_cost(n_images, resolution, a.points_per_image)
    texts = estimate_text_cost(n_pages, a.with_outline, a.with_pages, a.yuan_per_ktok)
    total_yuan = None
    if imgs["total_yuan"] is not None and texts["total_yuan"] is not None:
        total_yuan = round(imgs["total_yuan"] + texts["total_yuan"], 4)
    rec = {"pages": n_pages, "every": every, "resolution": resolution,
           "images": imgs, "text": texts, "total_yuan": total_yuan,
           "points_per_yuan": POINTS_PER_YUAN}

    if imgs["total_points"] is None:
        msg = ("%s 档没有实测单价，**拒绝凭猜估算**（只有 1K 有实测价 24 点/张）。"
               "给 --points-per-image 指定单价。" % resolution)
        sys.stderr.write("\n%s\n" % _red(msg))
        # ⚠️ 这里是**拒绝**，不是"跑完了但结果不合格"，所以走**信封**而不是
        #    `ok:false` 的结果对象 —— 否则消费方拿到一个没有 `error.kind` 的
        #    `ok:false`，无法把"拒绝估算"和"闸门命中"分开处理。
        #    已经算出来的成本构成挂在 `error.detail` 里，一点信息都不丢。
        return _fail(3, "budget", msg, detail=rec)
    if a.budget is not None and total_yuan is not None and total_yuan > a.budget:
        msg = ("预估合计 %.4f 元超过预算上限 %g 元，**已中断（本来也不会在这里花钱）**"
               % (total_yuan, a.budget))
        sys.stderr.write("\n%s\n" % _red(msg))
        return _fail(3, "budget", msg)

    if a.json:
        _json_out(rec, a, ok=True)
        return 0
    sys.stdout.write("=== 课件成本预估（一次调用都不发）===\n")
    sys.stdout.write("规模：%d 页，每 %d 页一张配图 → %d 张\n" % (n_pages, every, n_images))
    sys.stdout.write("出图：%s\n" % fmt_image_cost(imgs))
    if a.with_outline or a.with_pages:
        sys.stdout.write("文本（**估算口径**，不是账单）：\n")
        for c in texts["calls"]:
            sys.stdout.write("  %-16s prompt≈%d tok + completion≈%d tok%s\n"
                             % (c["stage"], c["prompt_tokens"], c["completion_tokens"],
                                "" if "calls" not in c else " × %d 次" % c["calls"]))
        sys.stdout.write("  合计 ≈ %d token" % texts["total_tokens"])
        if texts["total_yuan"] is not None:
            sys.stdout.write(" ≈ %.4f 元（按 %.4f 元/千 token）\n"
                             % (texts["total_yuan"], float(a.yuan_per_ktok)))
        else:
            sys.stdout.write("（没给 --yuan-per-ktok，**只报 token、不报金额**——不编单价）\n")
    if total_yuan is not None:
        sys.stdout.write("\n合计 ≈ %.4f 元（出图实测价 + 文本估算，账单以 api.a7w.cn 控制台为准）\n"
                         % total_yuan)
    if a.budget is not None:
        sys.stdout.write("预算 %g 元：%s\n" % (a.budget, "在预算内"))
    return 0


def cmd_models(a):
    key = a7w.load_key(a.key)
    recs = {}
    try:
        apps = a7w._request("GET", a7w.HOST + "/api/v1/apps", key)
        recs["apps"] = a7w._unwrap(apps)
    except a7w.A7wError as exc:
        sys.stderr.write("⚠ 取应用清单失败：%s\n" % exc)
        recs["apps"] = None
    try:
        models = a7w._request("GET", a7w.HOST + "/api/v1/models", key)
        recs["models"] = a7w._unwrap(models)
    except a7w.A7wError as exc:
        sys.stderr.write("⚠ 取模型清单失败：%s\n" % exc)
        recs["models"] = None

    def _rows(obj):
        if obj is None:
            return []
        if isinstance(obj, list):
            return obj
        for k in ("data", "list", "items", "apps", "models"):
            v = obj.get(k)
            if isinstance(v, list):
                return v
        return []

    want = (a.type or "all").lower()
    rows = _rows(recs["models"])
    picked = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        t = str(r.get("type_code") or r.get("type") or "").lower()
        if want in ("all", "") or want in t:
            picked.append(r)
    if a.json:
        _json_out({"apps": _rows(recs["apps"]) if recs["apps"] is not None else None,
                   "models": picked if recs["models"] is not None else None,
                   "type": want}, a, ok=True)
        return 0
    if recs["apps"] is not None:
        sys.stdout.write("=== 在架生成应用（GET %s/api/v1/apps）===\n" % a7w.HOST)
        for r in _rows(recs["apps"]):
            if isinstance(r, dict):
                sys.stdout.write("  %-18s %s\n" % (r.get("code") or r.get("app") or "?",
                                                   r.get("name") or r.get("title") or ""))
    if recs["models"] is not None:
        sys.stdout.write("\n=== 在架模型（GET %s/api/v1/models，type=%s）===\n" % (a7w.HOST, want))
        for r in picked:
            sys.stdout.write("  %-28s %-10s %s\n" % (r.get("model") or r.get("id") or "?",
                                                     r.get("type_code") or r.get("type") or "",
                                                     r.get("name") or ""))
    sys.stdout.write("\n出图模型的可选值现查：python scripts/a7w.py schema nano_banana\n")
    return 0


# ===========================================================================
# 命令行
# ===========================================================================

def _add_model_opts(p):
    p.add_argument("--key", help="临时指定 API Key（优先级最高；别写进脚本或文档）")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="文本模型名，默认 %s（实测可用）。用 `models` 现查在架模型" % DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=8192, help="最大输出 token，默认 8192")
    p.add_argument("--no-json-mode", action="store_true",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_budget_opt(p):
    p.add_argument("--budget", type=float,
                   help="成本上限（**元**，出图按实测 24 点/张 = 0.24 元换算），超了退出码 3")
    p.add_argument("--yuan-per-ktok", type=float, default=YUAN_PER_KTOK_DEFAULT,
                   help="文本单价（元/千 token）**估算口径**，默认 %.2f，不是账单"
                        % YUAN_PER_KTOK_DEFAULT)


def _add_source_opts(p):
    p.add_argument("file", nargs="?", help="讲义 / 大纲文件（Markdown / 纯文本）")
    p.add_argument("--text", help="直接给讲义正文（与位置参数二选一）")
    p.add_argument("--topic", help="课程主题（给 `--from-file` 或做兜底标题用）")
    p.add_argument("--audience", help="受众补充说明")
    p.add_argument("--level", default="basic", choices=["zero", "basic", "advanced"],
                   help="受众水平，默认 basic")
    p.add_argument("--pages", type=int, default=12, help="目标页数，默认 12（容忍 ±1）")


def _add_deck_opts(p):
    p.add_argument("--outdir", default="slide-out", help="产出目录（**指到包外**）")
    p.add_argument("--deck", help="分页方案文件，默认 <outdir>/%s" % DECK_NAME)
    p.add_argument("--only", help="只处理这些页 id，逗号分隔（例：p03,p05）")
    p.add_argument("--count", type=int, help="最多处理几页")
    p.add_argument("--every", type=int, default=1,
                   help="每 N 页配一张图（1=每页一图，2=数页一图），默认 1")
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复扣费**）")
    _add_budget_opt(p)
    _add_json(p)


def _add_image_opts(p):
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS),
                   help="出图分辨率档，默认 1K（只有 1K 有实测单价）")
    p.add_argument("--ratio", help="出图比例，默认按分页方案（%s）" % DECK_GEN_RATIO)
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    p.add_argument("--snap", action="store_true",
                   help="出图后按请求比例**居中裁准**（上游按 32 对齐，5/10 种比例不精确）")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="比例容差，默认 %.2f（实测最大偏差 2.9%%）" % RATIO_TOLERANCE)
    p.add_argument("--poll-timeout", type=int, default=POLL_TIMEOUT_DEFAULT,
                   help="单张出图轮询上限（秒），默认 %d" % POLL_TIMEOUT_DEFAULT)
    p.add_argument("--yes", action="store_true", help="确认真花钱的操作（不加它只报价）")
    p.add_argument("--dry-run", action="store_true", help="只报价 / 只打提示词，不花钱")
    p.add_argument("--allow-prompt-hits", action="store_true",
                   help="放行**出图提示词**闸门命中（页面内容闸门永远不放行）")
    p.add_argument("--model-image", default="nano-banana", help="出图模型，默认 nano-banana")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 课件配图与排版：讲义 → 分页 → 每页内容 → 配图 → 本地排版 PNG",
        epilog="端点：POST /api/v1/chat/completions（文本）、"
               "POST /api/v1/apps/nano_banana/submit（出图）、"
               "GET /api/v1/tasks/<task_id>（轮询）、GET /api/v1/models（模型清单）")
    ap.add_argument("--version", action="version", version="sanjianke-slide-kit %s" % VERSION)
    _add_json(ap, suppress=False)      # 父级：default=False，保证 a.json 永远存在
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- outline ---
    p = sub.add_parser("outline", help="读讲义 → 分页方案（只花文本钱）")
    _add_source_opts(p)
    p.add_argument("--outdir", default="slide-out", help="产出目录（**指到包外**）")
    p.add_argument("--out", help="额外把分页方案 JSON 写一份到指定路径")
    p.add_argument("--from-file", help="**零成本闸门自检**：直接拿一份返回 JSON 过闸门，不调模型")
    p.add_argument("--embed", action="store_true", help="--json 时把完整 deck 也嵌进输出")
    p.add_argument("--dry-run", action="store_true", help="只打印将发送的提示词，不调模型")
    _add_model_opts(p)
    _add_budget_opt(p)
    _add_json(p)
    p.set_defaults(func=cmd_outline)

    # --- pages ---
    p = sub.add_parser("pages", help="把分页方案展开成成稿（要点 + 讲稿备注）")
    _add_deck_opts(p)
    p.add_argument("--style", help="讲课风格补充说明")
    p.add_argument("--strict-notes", action="store_true",
                   help="缺讲稿备注也算闸门失败（默认只告警）")
    p.add_argument("--from-file", help="**零成本闸门自检**：拿一份返回 JSON 过闸门，不调模型")
    p.add_argument("--dry-run", action="store_true", help="只打印将发送的提示词，不调模型")
    _add_model_opts(p)
    p.set_defaults(func=cmd_pages)

    # --- images ---
    p = sub.add_parser("images", help="按页出配图（真花钱，先报价）")
    _add_deck_opts(p)
    _add_image_opts(p)
    _add_model_opts(p)
    p.set_defaults(func=cmd_images)

    # --- render ---
    p = sub.add_parser("render", help="本地排版成逐页 PNG（零成本、零网络，需要 PIL）")
    _add_deck_opts(p)
    p.add_argument("--theme", choices=list(THEME_CHOICES),
                   help="配色主题，默认按分页方案或 ink")
    p.add_argument("--font", help="中文字体文件路径（默认从系统字体里找）")
    p.add_argument("--no-html", dest="html", action="store_false", default=True,
                   help="不导出 deck.html")
    p.add_argument("--strict-notes", action="store_true",
                   help="缺讲稿备注也算闸门失败（默认只告警）")
    p.add_argument("--ratio-tolerance", type=float, default=RATIO_TOLERANCE,
                   help="配图比例容差，默认 %.2f" % RATIO_TOLERANCE)
    p.set_defaults(func=cmd_render)

    # --- all ---
    p = sub.add_parser("all", help="串起 outline → pages → images → render（断点续跑）")
    _add_source_opts(p)
    p.add_argument("--outdir", default="slide-out", help="产出目录（**指到包外**）")
    p.add_argument("--style", help="讲课风格补充说明")
    p.add_argument("--every", type=int, default=1, help="每 N 页配一张图，默认 1")
    _add_image_opts(p)
    _add_model_opts(p)
    p.add_argument("--theme", choices=list(THEME_CHOICES), help="配色主题")
    p.add_argument("--font", help="中文字体文件路径")
    p.add_argument("--no-html", dest="html", action="store_false", default=True,
                   help="不导出 deck.html")
    p.add_argument("--strict-notes", action="store_true", help="缺讲稿备注也算闸门失败")
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑（**会重复扣费**）")
    _add_budget_opt(p)
    _add_json(p)
    p.set_defaults(func=cmd_all)

    # --- cost ---
    p = sub.add_parser("cost", help="只算钱，一次调用都不发")
    p.add_argument("--pages", type=int, default=12, help="页数，默认 12")
    p.add_argument("--every", type=int, default=1, help="每 N 页一张图，默认 1")
    p.add_argument("--images", type=int, help="直接指定要出几张图（覆盖 --pages / --every）")
    p.add_argument("--no-images", dest="with_images", action="store_false", default=True,
                   help="不算出图的钱")
    p.add_argument("--no-text", dest="with_text", action="store_false", default=True,
                   help="不算文本的钱（等于 --no-outline --no-pages）")
    p.add_argument("--no-outline", dest="with_outline", action="store_false", default=True,
                   help="不算 outline 的钱")
    p.add_argument("--no-pages", dest="with_pages", action="store_false", default=True,
                   help="不算 pages 的钱")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--points-per-image", type=float, help="覆盖单张单价（点）")
    _add_budget_opt(p)
    _add_json(p)
    p.set_defaults(func=cmd_cost)

    # --- models ---
    p = sub.add_parser("models", help="列出在架模型与应用（零成本）")
    p.add_argument("--type", default="all", help="只看某类模型：text / image / all")
    _add_model_opts(p)
    _add_json(p)
    p.set_defaults(func=cmd_models)
    return ap


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与普通 CLI 一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被重定向吞掉）
    _JSON["want"] = "--json" in argv_eff  # argparse 失败时还没有 a，先按命令行判断
    _JSON["emitted"] = False
    _JSON["reason"] = None
    _JSON["trace"] = False
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise                                 # 非 --json：原样冒泡
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return 1


def _main(argv_eff):
    ap = build_parser()
    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        # argparse 的参数错（退出码 2）也要给信封；--help / --version（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    kind, msg = None, None
    try:
        rc = a.func(a)
    except UsageError as exc:
        sys.stderr.write("\n错误：%s\n" % exc)
        rc, kind, msg = 2, "usage", str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("\n错误：%s\n" % exc)
        rc, kind, msg = 4, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（已提交的任务记在断点文件里，重跑可续查）\n")
        rc, kind, msg = 130, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        if _JSON["trace"]:
            # 命令自己已经吐过完整 JSON（结果里 ok=false）→ **绝不再补信封**，
            # 否则 stdout 上会有两个 JSON 文档，消费方 `json.loads` 直接失败。
            sys.stderr.write("\n%s\n" % _red(
                "本次以退出码 %d 结束；结果 JSON 已经在上面的 stdout 里（ok=false）。"
                % rc))
            return rc
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


if __name__ == "__main__":
    sys.exit(main())
