#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 出海本地化小组 —— 跨语言多智能体互审（零第三方依赖）。

**产品线 L3（多智能体协作型）**。与 L1 `sanjianke-multiplat-rewrite` 的分界不是
"多了个翻译步骤"，而是三件在单角色改写里**结构上不存在**的事：

  1. **跨语言**：源语言 → 目标语言，目标语言侧还有一套自己的广告法与平台规则
  2. **术语一致**：同一个源词在全篇必须同一个译法（要术语表 + 版本 + 逐处定位）
  3. **文化风险**：目标市场能不能接受（禁忌 / 宗教 / 颜色 / 数字 / 幽默失效 / 政治敏感），
     并且这一席**能否决**

四个角色各有目标函数、产出物与否决权：

    译审     意思准不准、有没有漏译错译    → 译文 + 逐句回译对照   **能打回**
    文化适配 目标市场能不能接受            → 文化风险清单          **能否决**
    术语官   术语全篇一致、合行业惯例      → 术语表 + 不一致清单   **能打回**
    合规     目标市场广告法 / 平台规则     → 放行 / 打回 / 一票否决 **一票否决**

**信息隔离是结构性的，不是口头约定**：译审看不到文化适配的结论，文化适配也看不到
术语官的不一致清单；每个角色能看到的字段写死成 `ROLES[...]["inputs"]` 白名单，
调用前由 `assert_isolation()` 做文本级扫描（prompt 里出现别的角色的结论标记词 → 退出码 3）。
两席互审是**四次独立调用**，不是一次回答的四种复述。

**反馈是有向的、分级的**：某个角色打回时，重译提示词里只带**它自己的可执行要求**
（`requirements`），带的是"改成什么"，不带"谁在什么立场上说了什么" ——
既让打回真的生效，又不让下一轮的译审顺着别人的结论走。

子命令：

    roles           四个角色的职权、产出物与否决权（纯本地，零成本）
    glossary        从源文抽出术语表（源词 → 目标语规范译法）
    translate       译审出译文 + 逐句回译对照（带锚点校验）
    culture         文化适配出风险清单（**能否决**）
    glossary_check  术语一致性核对（**能打回**，可零成本重跑）
    compliance      目标市场合规裁决（**可否决**，一票否决）
    run             一条命令跑完整协作：四个角色互审 + 轮次上限 + 明确出口
    log             读回全过程：谁在第几轮打回了什么、引用了哪句
    cost            报价：这一趟大概花多少 token（金额要你自己填单价）
    models          列出 api.a7w.cn 当前在架的模型（模型名会变，现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py roles
    python3 run.py glossary       --file 源文.md --target-lang en --market us --outdir /tmp/lc
    python3 run.py translate      --file 源文.md --target-lang en --market us --glossary /tmp/lc/glossary.json
    python3 run.py culture        --file 源文.md --translation /tmp/lc/translation.json --market us
    python3 run.py glossary_check --file 源文.md --translation /tmp/lc/translation.json \
                                  --glossary /tmp/lc/glossary.json      # 纯本地，可零成本重跑
    python3 run.py compliance     --file 源文.md --translation /tmp/lc/translation.json --market us
    python3 run.py run            --file 源文.md --target-lang en --market us --rounds 2 --outdir /tmp/lc
    python3 run.py run            --file 源文.md --target-lang en --dry-run   # 只看提示词

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py run --file 源文.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json
    （scripts/a7w.py login --key sk-xxxx）

设计取舍
    · **为什么不是"翻一遍再让模型自己检查"**：一个声音自检时，它检查的是自己的判断；
      本包的四个角色看不到彼此的结论，所以打回一定是**真的不同意**，不是自己附和自己。
    · **谈不拢不许假装谈拢**：轮次用尽仍有打回/否决 → 走显式出口，产出带未决项、
      退出码 6，并在 `unresolved` 里写明是哪一席在第几轮、引用了哪句。
    · **违禁词表与市场文化规则都是启发式自检**，来自公开经验整理，不构成法律意见，
      也不等于任何平台的官方审核标准。
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 关掉字节码写入。**必须在任何本地 import 之前** —— 迟一行，那个模块就已经落盘了
# （同族实测记录：`import a7w` 之后再设 flag，scripts/__pycache__/a7w.cpython-*.pyc
# 已经生成，flag 只对之后 import 的模块生效）。
#
# 另外：`.pyc` **不会**导致上传被拒 —— `__pycache__` 与 `*.pyc` 本来就在 CLI 的
# 排除清单里，不会被打包。这一行是"让包保持干净"，不是上传的硬前提。
# 真正该做的两件事：自检脚本别 import 入口（非要 import 就先设这个 flag），
# 以及跑完 `py_compile` 之后清掉 `__pycache__`。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

PKG_ROOT = Path(__file__).resolve().parent.parent

# 退出码。数值与同族对齐：
EXIT_OK = 0            # 全流程走通：四席都没打回、没否决、没有硬闸门命中
EXIT_INTERNAL = 1      # 未捕获异常（--json 下给 kind:"internal" 信封）
EXIT_USAGE = 2         # 参数/配置错（文件不存在、--outdir 在包内、给了 --budget 没给单价）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/锚点/术语不一致/数字丢失/裁决不完整）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止
EXIT_UNRESOLVED = 6    # 轮次用尽仍有未决项（**分歧如实报出，不许假装谈拢**）
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。改了角色提示词/裁决规则/术语表规则却不改 key，
# 续跑会把上一版口径的旧产物当成"已完成"直接复用，产出对不上文档。
ROLE_VERSION = "lc-roles-1.0.0"
PROMPT_VERSION = "lc-prompt-1.0.0"
RULING_VERSION = "lc-ruling-1.0.0"
GLOSSARY_VERSION = "lc-glossary-1.0.0"
CULTURE_RULES_VERSION = "lc-culture-1.0.0"
UNIT_RULES_VERSION = "lc-units-1.0.0"

STATE_NAME = "localize-state.json"
LOG_NAME = "crew-log.md"

DEFAULT_SOURCE_LANG = "zh"
DEFAULT_TARGET_LANG = "en"
DEFAULT_MARKET = "us"
DEFAULT_ROUNDS = 1
DEFAULT_TARGET_MULTIPLE = 1.0   # 目标译文长度 ≈ 源文 × 该系数（英译中 ≈ 1.6，中译英 ≈ 1.0）
TARGET_MULTIPLE_MIN = 0.3
TARGET_MULTIPLE_MAX = 4.0


# ===========================================================================
# 语言与市场
#
# 目标市场不是装饰：它同时决定**文化适配那一席的规则包**与**合规那一席的市场法域**。
# 所以它必须进断点 key —— 换成日本市场而复用上一次的合规结论，是这类工具最危险的
# 一种"静默复用"。
# ===========================================================================

LANGS = {
    "zh": "中文（简体）",
    "zh-tw": "中文（繁体）",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "es": "西班牙文",
    "pt": "葡萄牙文",
    "fr": "法文",
    "de": "德文",
    "ar": "阿拉伯文",
    "th": "泰文",
    "vi": "越南文",
    "id": "印尼文",
    "ru": "俄文",
}
LANG_CHOICES = list(LANGS.keys())


def lang_name(code):
    return LANGS.get(code, code)


# 每个市场：文化适配要盯的点 + 合规要查的规则 + 平台规则提示。
# 这些是**启发式自检口径**，不构成法律意见；高风险类目必须人工复核。
MARKETS = {
    "us": {
        "name": "美国",
        "region": "北美",
        "religion": "基督教（新教/天主教）为主，同时有大量犹太教、穆斯林、无宗教人群",
        "culture_focus": [
            "宗教符号与节日（圣诞/复活节的商业化边界、不得戏用宗教意象）",
            "种族、移民、原住民、奴隶制历史的表述（极敏感，必须中性）",
            "个人隐私与数据（不得暗示收集健康/财务数据）",
            "性别与身体表述（不得物化，避免性别刻板印象）",
            "枪支、酒精、大麻、处方药（广告受严格限制）",
            "夸张宣传的法律后果（FTC 要求可举证）",
        ],
        "color_taboo": "红色可以；避免用「黑色=丧事」这类中式联想；彩虹色在部分语境会被读成政治立场",
        "number_taboo": "13（部分酒店楼层跳过），4 不是禁忌",
        "humor_risk": "反讽与自嘲在美国受众里有效，但对宗教、种族、体型的玩笑几乎必然翻车",
        "political_risk": "党争、选举、移民政策、堕胎、枪支管制 —— 一律不碰",
        "law": "FTC 广告规则（宣称必须有可举证依据）+ 各州消费者保护法",
        "rules": [
            ("绝对化用语", r"\b(best|greatest|number one|#1|No\.?\s*1|world'?s\s+best|"
                          r"finest|perfect|unbeatable|guaranteed)\b", "高",
             "FTC 要求「最佳/第一/保证」类宣称有可举证依据，无依据即属虚假广告"),
            ("比较级宣称", r"\b(better than|cheaper than|faster than|more effective than|"
                          r"outperforms)\b", "中",
             "比较广告必须能举证，且不得贬低指名竞品"),
            ("医疗功效", r"\b(cure[sd]?|heal[sd]?|treat(s|ed|ment)?|clinically proven|"
                        r"FDA[- ]approved|eliminates?\s+(acne|pain|disease))\b", "高",
             "FDA 禁止未经批准的药品/器械功效宣称"),
            ("减肥增效", r"\b(lose \d+ ?(pounds|lbs|kg)|melt fat|burn fat overnight|"
                        r"detox)\b", "高",
             "减重宣称必须有实证，快速见效类属高风险"),
            ("金融收益", r"\b(guaranteed (returns?|income|profit)|risk[- ]free investment|"
                        r"double your money|get rich)\b", "高",
             "SEC/FTC 禁止无风险高收益承诺"),
            ("儿童相关", r"\b(kids?|children|teens?)\b.{0,24}\b(free|buy|order|sign up)\b", "高",
             "COPPA 限制针对 13 岁以下儿童的收集与商业诱导"),
            ("站外导流", r"\b(click the link|DM me|WhatsApp|WeChat|Telegram)\b", "中",
             "多数平台限制站外导流与私域收集"),
        ],
        "platform": "Meta / TikTok / Amazon 均要求广告可举证；Amazon 禁止在 listing 里写竞品名",
    },
    "eu": {
        "name": "欧盟",
        "region": "欧洲",
        "religion": "天主教/新教/东正教并存，世俗化程度高；穆斯林人口在增长",
        "culture_focus": [
            "各国差异极大（北欧 / 南欧 / 东欧不能当同一个市场）",
            "环保与可持续宣称受强力监管（greenwashing 直接罚）",
            "数据隐私（GDPR）：不得暗示收集个人数据",
            "动物福利、劳工权益、性别平等",
            "历史符号（纳粹、极权、殖民）零容忍",
        ],
        "color_taboo": "颜色禁忌因国而异：德国忌黑/棕，法国忌墨绿，比利时忌蓝（政治联想）",
        "number_taboo": "13（多国），意大利忌 17",
        "humor_risk": "英式自嘲可以，对宗教/战争/民族的玩笑零容忍",
        "political_risk": "各国党争、难民政策、脱欧、俄乌 —— 一律不碰",
        "law": "不公平商业行为指令（UCPD）附件一 31 项「永远不公平」的商业行为 + GDPR + 各国广告法",
        "rules": [
            ("绝对化用语", r"\b(best|number one|#1|the only|unbeatable|perfect|"
                          r"100\s*%|guaranteed)\b", "高",
             "UCPD 禁止无法举证的优越性宣称与「唯一」类排他宣称"),
            ("绿色宣称", r"\b(eco[- ]?friendly|carbon[- ]?neutral|100\s*%\s*(natural|recycled)|"
                        r"sustainable|green)\b", "高",
             "「绿色宣称」须有全生命周期证据，否则属 greenwashing（多国已立法处罚）"),
            ("比较级宣称", r"\b(better than|the cheapest|more effective)\b", "中",
             "比较必须客观、可核实、且比较同类"),
            ("医疗功效", r"\b(cure[sd]?|heal[sd]?|clinically proven|medical grade)\b", "高",
             "欧盟禁止非药品使用医疗功效宣称"),
            ("金融收益", r"\b(guaranteed (returns?|profit)|risk[- ]free)\b", "高",
             "MiFID II 与各国金融推广规则禁止无风险承诺"),
            ("儿童相关", r"\b(kids?|children)\b.{0,24}\b(buy|order|subscribe|free)\b", "高",
             "欧盟禁止直接 exhortation 儿童购买，并限制儿童数据"),
        ],
        "platform": "TikTok EU / Meta 对 greenwashing 与健康宣称会直接拒登",
    },
    "jp": {
        "name": "日本",
        "region": "东亚",
        "religion": "神道与佛教共存，宗教在商业中低调",
        "culture_focus": [
            "敬语层级（です/ます ↔ である）与受众身份必须匹配，用错很失礼",
            "「本音/建前」：直白否定式文案在日文里读起来很冲",
            "数字与谐音禁忌（4 = 死、9 = 苦）",
            "颜色：白色（丧事）、绿色在部分场景有负面联想",
            "对「效果绝对」类宣称的容忍度极低，药机法管得很细",
        ],
        "color_taboo": "白（丧事）、黑（丧事）慎用于喜庆场景",
        "number_taboo": "4（し=死）、9（く=苦）、42（死に）",
        "humor_risk": "幽默偏轻自嘲与共感，直接调侃受众会适得其反",
        "political_risk": "靖国、战争责任、天皇、在日外国人 —— 一律不碰",
        "law": "景品表示法（優良誤認・有利誤認）+ 薬機法（功效宣称）+ 特定商交易法",
        "rules": [
            ("绝对化用语", r"(最高|最強|No\.?\s*1|ナンバーワン|日本一|世界一|絶対|"
                          r"完璧|唯一|必ず)", "高",
             "景品表示法禁止「優良誤認」：无依据的「最高/日本一」属违法表示"),
            ("医疗功效", r"(治る|治癒|効く|痩せる|アンチエイジング|医薬品|"
                        r"臨床的に証明)", "高",
             "薬機法限制非药品的疗效宣称，罚款很重"),
            ("比较级宣称", r"(他社より|一番安い|より効果)", "中",
             "比较广告须有客观依据，且不得贬低他社"),
            ("金融收益", r"(元本保証|必ず儲かる|確実な利益)", "高",
             "金商法禁止无风险收益承诺"),
            ("儿童相关", r"(お子様).{0,16}(購入|申込|無料)", "高",
             "对儿童的商业诱导受严格限制"),
        ],
        "platform": "Yahoo!広告 / Meta JP 对「No.1」类表示要求出典标注，否则拒登",
    },
    "sea": {
        "name": "东南亚（印尼 / 泰国 / 越南 / 菲律宾）",
        "region": "东南亚",
        "religion": "印尼/马来西亚以伊斯兰教为主；泰国佛教；菲律宾天主教；越南民间信仰",
        "culture_focus": [
            "印尼：清真（Halal）认证是硬门槛，猪/酒精/非清真成分不能出现",
            "泰国：王室不可戏谑（法律后果极重）、佛像不得商用、头部视为神圣",
            "越南/菲律宾：语言本地化程度要求高，纯英文素材接受度低于预期",
            "价格敏感，但对「本地化过的品牌」好感明显更高",
            "肤色相关表述极敏感，美白类宣传在部分地区已被限制",
        ],
        "color_taboo": "泰国忌黑（丧）与对王室的颜色联想；印尼绿色是宗教色，不可轻用",
        "number_taboo": "无强禁忌；泰国忌 6（部分语境）",
        "humor_risk": "幽默依赖语言双关，直译过去大多失效；不要拿宗教与王室开玩笑",
        "political_risk": "王室（泰国）、宗教派别（印尼）、南海议题（越南）—— 一律不碰",
        "law": "印尼 BPOM/Halal 认证 + 泰国 Consumer Protection Act + 越南 Advertising Law",
        "rules": [
            ("绝对化用语", r"\b(best|number one|#1|nomor satu|terbaik|最|ที่สุด)\b", "高",
             "多数东南亚国家沿用「无法举证的优越宣称」即违规的口径"),
            ("清真相关", r"\b(pork|bacon|alcohol|contains? alcohol|non[- ]halal)\b", "高",
             "印尼/马来西亚：非清真成分与酒精出现在食品/化妆品宣传中属违规"),
            ("医疗功效", r"\b(cure[sd]?|heal[sd]?|treat(s|ment)?|menyembuhkan|"
                        r"clinically proven)\b", "高",
             "东南亚多国要求功效宣称事前备案，未备案即违规"),
            ("美白宣称", r"\b(whiten(ing)?|skin whitening|memutihkan)\b", "中",
             "美白类宣称在泰国、印尼已被收紧，且易触发肤色敏感"),
            ("金融收益", r"\b(guaranteed (returns?|profit)|risk[- ]free|untung pasti)\b", "高",
             "无风险高收益承诺在东盟各国普遍违法"),
            ("儿童相关", r"\b(kids?|children|anak)\b.{0,20}\b(buy|order|free)\b", "高",
             "对儿童的商业诱导受限制"),
        ],
        "platform": "Shopee / Lazada / TikTok Shop 印尼站要求 Halal 与 BPOM 资质才允许上架",
    },
    "me": {
        "name": "中东（海湾六国）",
        "region": "中东北非",
        "religion": "伊斯兰教（逊尼派为主）",
        "culture_focus": [
            "清真：猪、酒精、非清真成分一律不能出现，明示或暗示都不行",
            "斋月（Ramadan）期间的排期与文案语气要专门处理",
            "女性形象与着装：须保守呈现，不得物化",
            "左手、鞋底朝向等符号禁忌（视觉素材也要过）",
            "以色列、政治立场、教派冲突 —— 零容忍",
        ],
        "color_taboo": "绿色是宗教色（不可轻用），金色/白色可；避免用于宗教器物的图形",
        "number_taboo": "无强数字禁忌",
        "humor_risk": "反讽在当地文案里常被读成冒犯，不宜使用",
        "political_risk": "宗教、教派、以色列/巴勒斯坦、王室 —— 一律不碰",
        "law": "各国广告法（以伊斯兰教义与公共道德为底线）+ 沙特 GAMR 广告审批 + 阿联酋 NMO",
        "rules": [
            ("清真相关", r"\b(pork|bacon|ham|alcohol|beer|wine|bar|pub|non[- ]halal)\b", "高",
             "伊斯兰教义与海湾各国法规：猪肉与酒精不得出现在宣传物料中"),
            ("绝对化用语", r"\b(best|number one|#1|the only|guaranteed)\b", "高",
             "无法举证的优越宣称在多数海湾国家属违规"),
            ("宗教与政治", r"\b(god|jesus|christ|israel|zion|christmas|new year)\b", "中",
             "宗教人物与非伊斯兰节日在商业文案中慎用；涉以色列内容零容忍"),
            ("女性形象", r"\b(bikini|lingerie|sexy|provocative)\b", "高",
             "女性形象须保守呈现，物化表述直接违反公共道德条款"),
            ("医疗功效", r"\b(cure[sd]?|heal[sd]?|clinically proven)\b", "高",
             "功效宣称需卫生部门审批"),
            ("金融收益", r"\b(guaranteed (returns?|profit)|risk[- ]free|interest[- ]bearing)\b", "高",
             "含利息（riba）的金融宣称在伊斯兰金融框架下违规"),
        ],
        "platform": "Snapchat / TikTok 中东站点要求在 Ramadan 期间使用专用素材，且宗教内容需审核",
    },
    "br": {
        "name": "巴西 / 拉美",
        "region": "拉美",
        "religion": "天主教为主，福音派增长明显",
        "culture_focus": [
            "葡萄牙语（巴西）与西班牙语（拉美）不能混用，用错很掉价",
            "家庭与社交场景在广告里权重极高",
            "肤色与阶层：不得暗示阶层优越感",
            "本地节日（狂欢节、亡灵节）不能当通用道具",
        ],
        "color_taboo": "紫色在巴西与丧事相关，慎用为喜庆主色",
        "number_taboo": "13（部分人群）",
        "humor_risk": "自嘲与夸张式幽默有效，但涉及宗教与性别的玩笑风险高",
        "political_risk": "军政时期、原住民议题、党争 —— 一律不碰",
        "law": "巴西 CDC（消费者保护法典）+ CONAR 广告自律准则",
        "rules": [
            ("绝对化用语", r"\b(melhor|número um|número 1|o único|garantido|"
                          r"100\s*%)\b", "高",
             "CONAR 要求优越性宣称可举证，绝对化用语属典型违规"),
            ("比较级宣称", r"\b(melhor que|mais barato que)\b", "中",
             "比较广告须客观、可比、且不贬低竞品"),
            ("医疗功效", r"\b(cura|curar|trata|tratamento|comprovado clinicamente)\b", "高",
             "ANVISA 禁止非注册产品做疗效宣称"),
            ("金融收益", r"\b(retorno garantido|sem risco|lucro certo)\b", "高",
             "CVM 禁止无风险收益承诺"),
            ("儿童相关", r"\b(criança|crianças|infantil)\b.{0,20}\b(compre|grátis)\b", "高",
             "CONANDA 对儿童广告限制极严"),
        ],
        "platform": "Meta BR 对医疗与金融类广告要求资质文件；TikTok BR 禁止未成年人形象用于带货",
    },
}
MARKET_CHOICES = list(MARKETS.keys())


def market_of(a):
    return MARKETS.get(a.market, MARKETS[DEFAULT_MARKET])


# ===========================================================================
# 角色表：L3 的地基
#
# `inputs` 是**允许进入该角色上下文的字段白名单**，`forbidden` 是被显式排除的字段。
# 这两栏不是文档，是 build_*_prompt() 真实读的那份数据 —— 提示词模板按它拼装，
# assert_isolation() 按它验证。改这里就同时改了行为与判定，不会文档与实现两张皮。
# ===========================================================================

ROLE_ORDER = ("translator", "terminologist", "culture", "compliance")

ROLES = {
    "translator": {
        "name": "译审",
        "goal": "意思准不准、有没有漏译错译 —— 交不出一份能逐句对上的回译对照就是失职",
        "deliverable": "译文 + 逐句回译对照（源句 → 译文 → 回译）",
        "veto": "**能打回**：意思错、漏译、增译、术语表里的词没按规范译法来 —— 必须重译",
        # ⚠️ 关键：文化适配的结论与合规裁决被显式排除在译审上下文之外。
        "inputs": ["source", "target_lang", "market", "glossary", "feedback"],
        "forbidden": ["culture_risks", "culture_verdict", "compliance_verdict", "compliance_risks"],
        "exit_on_fail": "打回 → 重译；轮次用尽仍打回 → 带未决项产出（退出码 6）",
    },
    "terminologist": {
        "name": "术语官",
        "goal": "术语全篇一致、与行业惯例一致 —— 同一个源词出现两种译法就是失职",
        "deliverable": "术语表定稿 + 不一致清单（每条给出全部出现位置）",
        "veto": "**能打回**：同一源词多译、或术语表里的规范译法没落地 —— 必须统一",
        # ⚠️ 关键：文化适配与合规的结论不进术语官上下文。
        "inputs": ["source", "translation", "glossary", "target_lang", "market"],
        "forbidden": ["culture_risks", "culture_verdict", "compliance_verdict", "compliance_risks"],
        "exit_on_fail": "不一致 → 打回；轮次用尽仍不一致 → 带未决项产出（退出码 6）",
    },
    "culture": {
        "name": "文化适配",
        "goal": "目标市场的文化能不能接受 —— 踩红线就必须改，不看它翻得准不准",
        "deliverable": "文化风险清单（禁忌 / 宗教 / 颜色 / 数字 / 幽默失效 / 政治敏感）",
        "veto": "**能否决**：踩红线（宗教、政治、禁忌符号）必须改，不接受「综合评估后放行」",
        # ⚠️ 关键：术语官的清单与合规的裁决不进文化适配上下文。
        # 文化适配必须自己看市场，不许顺着别人的结论走。
        "inputs": ["source", "translation", "market", "target_lang"],
        "forbidden": ["glossary_issues", "terminology_verdict", "compliance_verdict",
                      "compliance_risks"],
        "exit_on_fail": "否决 → 重译或改文案；轮次用尽仍否决 → 带未决项产出（退出码 6）",
    },
    "compliance": {
        "name": "合规",
        "goal": "目标市场的广告法 / 平台规则 —— 只看这一稿能不能发，不看它写得好不好",
        "deliverable": "风险裁决：pass（放行）/ fix（可安全替换）/ send_back（打回）/ veto（一票否决）",
        "veto": "**一票否决**：判 veto 直接终止，产出就是带未决项，不换词硬发",
        # ⚠️ 关键：译审的问题、术语官的不一致、文化适配的风险结论都不进合规上下文。
        # 合规的提示词里明说"本小组内部没有给出任何风险结论，你不得假设前道已放行"。
        "inputs": ["source", "translation", "market", "target_lang"],
        "forbidden": ["glossary_issues", "terminology_verdict", "culture_risks",
                      "culture_verdict", "translation_issues"],
        "exit_on_fail": "打回/veto → 修订；用尽仍不放行 → 带未决项产出（退出码 3 / 6）",
    },
}

# 每个角色调用的提示词里**禁止出现的标记词**。assert_isolation 用它做文本级检查：
# 排除一个字段，靠的不是"我模板里没写"，而是"调用前真的扫过一遍"。
ISOLATION_MARKERS = {
    "culture_risks": ["文化风险清单", "文化适配的", "culture_risks", "宗教红线"],
    "culture_verdict": ["文化适配判", "文化否决", "culture_verdict"],
    "compliance_verdict": ["合规裁决", "合规已放行", "compliance_verdict", "一票否决"],
    "compliance_risks": ["广告法违禁", "compliance_risks", "平台规则风险"],
    "glossary_issues": ["术语不一致清单", "术语官的", "glossary_issues"],
    "terminology_verdict": ["术语官判", "术语打回", "terminology_verdict"],
    "translation_issues": ["译审问题清单", "译审打回", "translation_issues"],
}

# 提示词里出现过的**跨主题**示例（正常不该被抄）。新增示例必须登记到这里。
# 跨主题 = 与任何真实出海选题都不搭（社区菜市场摊位租金），模型不会主动抄过去；
# 万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "菜市场摊位租金这笔账，我记了三个月",
    "先说结论：摊位租金高不高，跟人流量不成正比",
    "我在菜市场摆了两年摊，租金这块踩过三个坑",
]

# 全局裁决说明（进提示词，也进文档）。
CONVERGE_NOTE = (
    "裁决不是投票：译审能打回、术语官能打回、文化适配能否决、合规有一票否决 —— "
    "四席**各自独立**给出结论，彼此看不到对方的意见。任何一席打回/否决都要在下一轮"
    "真的改掉；轮次用尽还是打回/否决，就走**显式出口**（产出带未决项，退出码 6），"
    "**不许写「综合评估后放行」这种假装谈拢的话**。"
)

# 「实质性改动」判定：译文与上一轮相似度 ≥ 此值即判「没改」。
BODY_MIN_SIM = 0.90
MAX_NO_CHANGE_STRIKES = 1

VERDICT_PASS = "pass"
VERDICT_FIX = "fix"
VERDICT_SEND_BACK = "send_back"
VERDICT_VETO = "veto"
VERDICT_ANY = (VERDICT_PASS, VERDICT_FIX, VERDICT_SEND_BACK, VERDICT_VETO)
VERDICT_LABEL = {
    VERDICT_PASS: "放行",
    VERDICT_FIX: "可替换后放行",
    VERDICT_SEND_BACK: "打回重译",
    VERDICT_VETO: "一票否决",
}
VERDICT_HARD = (VERDICT_SEND_BACK, VERDICT_VETO)

# 各席的头两个字裁决取值（归一化用；模型可能吐同义词）。
TERM_VERDICT_MAP = {
    "pass": VERDICT_PASS, "ok": VERDICT_PASS, "放行": VERDICT_PASS, "通过": VERDICT_PASS,
    "一致": VERDICT_PASS, "无问题": VERDICT_PASS, "clean": VERDICT_PASS,
    "send_back": VERDICT_SEND_BACK, "打回": VERDICT_SEND_BACK, "不一致": VERDICT_SEND_BACK,
    "fail": VERDICT_SEND_BACK, "重译": VERDICT_SEND_BACK,
    "fix": VERDICT_FIX, "可替换": VERDICT_FIX,
    "veto": VERDICT_VETO, "否决": VERDICT_VETO, "一票否决": VERDICT_VETO,
}
CULTURE_VERDICT_MAP = dict(TERM_VERDICT_MAP)


# ===========================================================================
# 闸门一：合规
#
# 两侧口径，**分开扫**（这是同族 review-board 踩过的一次误报之后定的）：
#   · **材料侧**（源文）全扫高/中/低，最X 照查 —— 源文是要被翻出去的东西
#   · **产出侧**（译文 + 各席的裁决文书）只查高风险，并排除两类正常写法：
#       1. **引用材料**：该词在源文/译文里本来就有 → 判为引用，不计命中
#       2. **警告语境**：命中前后 24 字内有禁止/举证/风险类标记词 → 判为"提到/在禁止"
#     被排除的**全部留原因**（`not_counted_reason`），不静默丢弃；闸门仍然有牙：
#     「本方案必须保证过审」这种小句里没有任何标记词，照样拦。
# ===========================================================================

# 「第一」的可枚举上下文豁免：长文里「第一年」「第一步」是**序数**，不是最高级宣称。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯"
)
BANNED_PATTERNS = [
    # --- 源语言侧（中文）广告法违禁词 ---
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎)", "高",
     "广告法第九条禁止「最高级」用语", "superlative"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证", "superlative"),
    (r"第一(?!" + FIRST_ORDINAL_AFTER + r")", "高",
     "「第一」类排他性表述", "first"),
    (r"排名第一|销量第一|口碑第一|行业第一|全国第一|全网第一|全球第一|世界第一", "高",
     "「第一」类排他性表述", "first"),
    (r"No\.?\s*1|TOP\s*1|top\s*1", "高",
     "「第一」类排他性表述", "first"),
    (r"国家级|世界级|全球级|国际级", "高",
     "「国家级」等权威性词汇属明令禁止", "authority"),
    (r"100\s*%|百分之百|百分百", "高",
     "绝对化效果承诺", "absolute"),
    (r"绝对(有效|安全|放心|不会|能|可以)|保证(有效|成功|瘦|赚)|无效退款", "高",
     "绝对化保证与效果担保", "absolute"),
    (r"根治|治愈|痊愈|药到病除|包治|治疗(好|效果)|疗效|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用", "medical"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高",
     "投资类收益承诺", "finance"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐", "高",
     "不得虚构权威背书", "authority"),
    (r"催情|壮阳|丰胸|减肥(药|神器)|美白针|生发(神器)", "高",
     "特殊功效与特殊品类敏感词", "medical"),
    (r"免费领|免费送|0\s*元购|白送", "中",
     "可能构成虚假优惠或诱导分享", "promo"),
    (r"秒杀|抢购|限时(抢|购)|最后(一天|三天)|仅限今天", "中",
     "促销时限表述需与实际活动一致", "promo"),
    (r"独家|唯一|首个|首创|填补空白|领先(品牌|技术)", "中",
     "排他性表述需有可举证依据", "exclusive"),
    (r"纯天然|无添加|零添加|无毒无害", "中",
     "成分宣称需与检测报告一致", "ingredient"),
    (r"点击链接|加微信|私信我|扫码(加|进)|vx|VX|微信号", "中",
     "站外导流，平台普遍限制", "diversion"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "中",
     "标题党式诱导", "clickbait"),
    (r"[！!]{2,}|[?？]{3,}", "低",
     "标点堆砌，易被判标题党/低质", "punct"),
]
# 编译一次，四处复用（源语言侧扫描 + 产出侧扫描都读这一份）。
BANNED_RE = [(re.compile(p), lvl, why, tag) for p, lvl, why, tag in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# 「最X」的可枚举上下文豁免表。
# 事故复盘（同族，长文场景踩出来的）：`最大区别` / `最主要的是` 这类是**普通中文用法**，
# 不是最高级商品宣称。一刀切拦下会把正常稿子整篇判死，用户就会干脆关掉闸门 —— 那更糟。
# 所以开了豁免口子，但同时加一条**句首不豁免**：句首的「最大区别是…」是标题式宣称，照拦。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "低", "高", "多", "少", "大", "小", "早", "晚",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")

# 产出侧**不查**的条目：`最X` 是上下文依赖最强的一条。
# 真机实测（同族 review-board 第一轮就踩到）：评审写「这笔账里最大的一块」
# 是普通中文程度用法，不是商品宣称；而这类误报会让人把整个合规闸门关掉。
# 材料侧**照查**（译文与源文才是会被公开发布的东西）。
OUTPUT_EXCLUDED_TAGS = ("superlative",)

# 「提到」而不是「主张」的上下文标记。
# 判定方式很朴素：看命中所在的那**一整个小句**里有没有这些词 ——
# 有就是"提到/在拦它"，没有才是"自己在主张"。
META_CONTEXT_RE = re.compile(
    "禁止|严禁|不得|不许|不能|不可|避免|杜绝|防范|防止|违规|风险|涉嫌|属于|构成|"
    "无出处|无法举证|不可举证|举证|撤回|删除|删掉|去掉|不实|虚假|夸大|诱导|"
    "不构成|不算|不是|未|没|缺|整改|改为|改成|替换|风险点|红线|合规问题|"
    "forbid|prohibit|banned|must not|risk|compliance|violat|illegal|unsubstantiated")
_SENT_BOUND = re.compile(r"[。！？!?；;\n]")


def _ctx_window(text, pos, width=200):
    """命中所在**小句**的全部文字（**不跨句末标点**）。

    为什么按小句而不是固定字符数：中文评审句子里逗号、顿号极多，
    按逗号切成更小的单位会把「明确禁止代发、代拍、刷量」切碎成「刷量」，
    标记词正好被切掉 —— 这是同族自测时真踩到的一次。
    为什么 width 给得很大（200）：warning 语境常常离命中词十几个字
    （「本稿禁止使用 guaranteed 这类绝对化用语」里，命中词与标记词隔了 8 个字），
    窗口太小会让"在禁止"被误判成"在主张"。**不跨句末标点**这条才是真正的边界 ——
    跨句取词会把上一句的"禁止"借给下一句的违规宣称。
    """
    start = 0
    for m in _SENT_BOUND.finditer(text):
        if m.end() <= pos:
            start = m.end()
        else:
            break
    m = _SENT_BOUND.search(text, pos)
    end = m.start() if m else len(text)
    return text[max(start, pos - width):min(end, pos + width)]


def _superlative_is_normal_usage(text, start, end):
    """「最X」后面接的是比较或程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：
      1. 后文落在可枚举的豁免表里（SUPERLATIVE_OK_AFTER）
      2. 命中处不在句首 —— 句首的「最大区别是…」是标题式最高级宣称，照拦

    ⚠️ 这里必须用**命中位置**在原文上判断，不能用匹配到的字面量。
    事故（本包自测时抓到）：违禁词表里第一条是 `最(好|佳|优|…)`，对「最大的区别」
    它先匹配到「最」，但如果拿 `m.group(0)` 取自**别的**规则（或取到别处出现的
    「最好」），`group(0).startswith("最")` 之后又去看 `text[m.end():]`，
    就会拿着 A 命中的位置去看 B 的后续 —— 普通用法会被误判成最高级宣称。
    位置化的判断没有这个歧义。
    """
    after = (text or "")[start:]
    if not after.startswith("最"):
        return False
    before = (text or "")[:start]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    return bool(SUPERLATIVE_OK_RE.match(after[1:]))


def compliance_scan(text, levels=None):
    """扫一遍违禁词（源语言侧表），返回 (命中列表, 豁免列表)。

    `levels` 可以只扫某一档风险：材料侧全扫（高/中/低），产出侧只扫高风险。
    被豁免的疑似命中**不静默放过**，逐条进 `exempted`。
    """
    hits, exempted, seen = [], [], set()
    t = text or ""
    for rx, lvl, why, tag in BANNED_RE:
        if levels is not None and lvl not in levels:
            continue
        for m in rx.finditer(t):
            if tag == "superlative" and _superlative_is_normal_usage(t, m.start(), m.end()):
                exempted.append({"word": m.group(0), "level": lvl, "tag": tag,
                                 "why": "「最X」后接比较/程度词且不在句首，判为普通用法",
                                 "context": t[max(0, m.start() - 12):m.end() + 12]})
                continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                continue
            seen.add(key)
            hits.append({"word": word, "level": lvl, "why": why, "tag": tag,
                         "context": t[max(0, m.start() - 12):m.end() + 12]})
            break
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits, exempted


def market_compliance_scan(text, market):
    """扫**目标市场**侧的规则（绝对化 / 比较级 / 医疗 / 金融 / 儿童…）。

    这一趟是出海本地化与"同一语言换平台形态"最实质的差别之一：
    目标语言侧有一整张自己的法域规则表，而不是把中文违禁词表翻一遍。
    """
    mk = MARKETS.get(market) or MARKETS[DEFAULT_MARKET]
    hits, seen = [], set()
    t = text or ""
    for label, pattern, level, why in mk["rules"]:
        rx = re.compile(pattern, re.I)
        for m in rx.finditer(t):
            word = m.group(0)
            key = (label, word.lower())
            if key in seen:
                continue
            seen.add(key)
            hits.append({"market": mk["name"], "rule": label, "word": word,
                         "level": level, "why": why,
                         "context": t[max(0, m.start() - 24):m.end() + 24]})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits, mk


def _mentioned_context(prose, word, ctx, pos):
    """命中是不是落在**警告/引用语境**里（而不是自己在主张）。

    判定方式很朴素：看命中所在的**整个小句**里有没有禁止/举证/风险类标记词 ——
    有就是"提到/在拦它"，没有才是"自己在主张"。

    ⚠️ 两个坑都是本包自测时真踩到的：
      1. **标记词必须落在命中词本身之外**。「本方案必须保证过审」被放过过一次：
         `META_CONTEXT_RE` 里有「保证」，而命中的词恰好就是「保证」自己，
         于是"自己在承诺"被读成"在禁止承诺" —— 闸门就这样失去了牙。
      2. 窗口位置必须按 `_ctx_window` 的实际起点还原。写死 `pos - 24` 在窗口宽度
         改过之后会算错，误判方向随机，最难查。
    返回标记词；没有则返回 None。
    """
    if pos < 0 or not ctx:
        return None
    m = META_CONTEXT_RE.search(ctx)
    if not m:
        return None
    c_start = pos - (ctx.index(word) if word and word in ctx else 0)
    m_abs_start, m_abs_end = c_start + m.start(), c_start + m.end()
    w_start, w_end = pos, pos + max(1, len(word or ""))
    if not (m_abs_end <= w_start or m_abs_start >= w_end):
        return None                     # 标记词就是命中词自己 → 不算"提到"
    return m.group(0)


def compliance_scan_output(prose, material, market):
    """产出侧合规（**与材料侧口径不同**）。

    产出侧收紧成三条**能解释的**规则：
      1. 只查**高风险**（广告法明令禁止的那一类）；中低风险项与 `最X`
         在裁决文书里多半是描述性用语，列进 `contextual_only` 提示人工看，不拦。
      2. 材料里/译文里已经出现过的词判为**引用**，不计命中。
      3. 命中所在的**小句**里有禁止/举证/风险类标记词的判为**提到**，不计命中；
         小句里没有任何标记词的才是**自己在主张** → 拦
         （「本方案必须保证过审」照样拦得住）。
    被排除的条目**全部保留在案**（带 `not_counted_reason`），不静默丢弃。
    """
    hi_all, exempted = compliance_scan(prose, levels=("高",))
    hi, soft = [], []
    for h in hi_all:
        if h.get("tag") in OUTPUT_EXCLUDED_TAGS:
            h = dict(h)
            h["not_counted_reason"] = (
                "「最X」在裁决文书里多为普通中文程度用法（如「最大的一块」），"
                "产出侧不拦；材料侧照查")
            soft.append(h)
            continue
        # 源语言侧（中文）高风险项同样要看是不是"提到"：
        # 裁决文书里写「本稿禁止使用国家级、疗效这类词」是在要求删除，不是自己在宣称。
        pos = prose.find(h["word"])
        ctx = _ctx_window(prose, pos) if pos >= 0 else ""
        mk = _mentioned_context(prose, h["word"], ctx, pos)
        if mk:
            h = dict(h)
            h["not_counted_reason"] = (
                "命中所在小句里有「{}」这类标记词——判为**提到/在禁止**，"
                "不是在主张违规宣称".format(mk))
            h["context_window"] = ctx[:80]
            soft.append(h)
            continue
        hi.append(h)
    mk_hits, _mk = market_compliance_scan(prose, market)
    for h in mk_hits:
        if h["level"] != "高":
            soft.append(h)
            continue
        h2 = dict(h)
        pos = prose.find(h["word"])
        ctx = _ctx_window(prose, pos) if pos >= 0 else ""
        mk = _mentioned_context(prose, h["word"], ctx, pos)
        if mk:
            h2["not_counted_reason"] = (
                "命中所在小句里有「{}」这类标记词——判为**提到/在禁止**，"
                "不是在主张违规宣称".format(mk))
            h2["context_window"] = ctx[:80]
            h2["_mentioned"] = True
            hi.append(h2)
            continue
        hi.append(h2)
    mat_words = {h["word"].lower() for h in compliance_scan(material)[0]}
    mat_words |= {h["word"].lower() for h in market_compliance_scan(material, market)[0]}
    fresh, quoted, mentioned = [], [], []
    for h in hi:
        if h.get("_mentioned"):
            h.pop("_mentioned", None)
            mentioned.append(h)
            continue
        if h["word"].lower() in mat_words:
            h = dict(h)
            h["not_counted_reason"] = "该词在源文/译文里本来就有——判为**引用材料**，不计命中"
            quoted.append(h)
            continue
        fresh.append(h)
    contextual, _ = compliance_scan(prose, levels=("中", "低"))
    return fresh, quoted, mentioned, contextual + soft, exempted


# ===========================================================================
# 闸门二：占位符残留
#
# `{}` / `[待填]` / `XXX` / `（此处省略）` 是最典型的"没交付"形态：
# 模板没被替换干净，模型给自己留了空档。
# `[1]`（引用序号）、`[图 2]`（配图位）是**正常写法**，不按括号内容一刀切。
# ===========================================================================

PLACEHOLDER_PATTERNS = [
    (re.compile(r"\{\{?\s*[\u4e00-\u9fffA-Za-z0-9_]*\s*\}?\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【（(]\s*(待填|填空|待补充|待完善|待定)\s*[\]】）)]"), "[]",
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
    """扫占位符残留，返回命中列表（可能为空）。"""
    hits = []
    t = text or ""
    for rx, label, why in PLACEHOLDER_PATTERNS:
        m = rx.search(t)
        if m:
            hits.append({"kind": label, "word": m.group(0)[:40], "why": why})
    return hits


# ===========================================================================
# 闸门三：照抄提示词示例（prompt_echo）
#
# 事故复盘（同族，两例，都是实测抓到的「模型锚定示例」）：
#   1. 提示词里写过正例 → 模型直接产出同构句
#   2. 提示词里留过一整句示例 → 最高分的那条一字不差就是它
#
# 本包是长文场景，所以判定分两层：整段先比一次（只认 exact / jaccard），
# 再**逐句**比一次（含覆盖度判据）。正文上千字时整段比对的分母被撑大，
# 模型把示例原样抄进某一句，这道闸门会完全看不见。
#
# 【contain 必须加适用窗口】——长文对短示例会**饱和误报**：
# 目标文本越长，示例的二元组被覆盖的概率越高，覆盖度会虚假地冲到 1.0。
# 所以 contain 只在「目标归一后长度 ≤ 示例长度 × 3.0 且示例归一后 ≥ 8 字」时才适用。
# ===========================================================================

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6          # 长度守卫的绝对下限，防极短串的二元组噪声
ECHO_CONTAIN_MAX_RATIO = 3.0    # contain 适用窗口上界倍数：len(目标) ≤ len(示例) × 该系数
ECHO_CONTAIN_MIN_SAMPLE = 8     # contain 适用窗口：示例归一后至少这么长


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。

    **相对阈值**，不是绝对值。绝对阈值（比如 12）在示例只有 15~17 字时
    占了示例长度的七成以上，会把「≤11 字的截断照抄」整档放过。
    """
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_anchor(sample)) // 2)


def _norm_anchor(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。

    抄示例的文本往往只改标点（`，`↔`、`↔空格），所以必须先抹平标点再看。
    """
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _bigrams(s):
    s = _norm_anchor(s)
    if len(s) < 2:
        return set(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _similarity(a, b):
    """字符二元组 Jaccard 相似度，0~1。"""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(len(ba | bb))


def prompt_echo(text, samples=None, allow_contain=True):
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据)；判据是 "exact" / "jaccard" / "contain"。
    `allow_contain=False` 时**不启用**覆盖度判据（整段长文比对用，见 prompt_echo_scan）。
    """
    target = _norm_anchor(text)
    if not target:
        return False, 0.0, "", ""
    best_score, best_sample, best_rule = 0.0, "", ""
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        ns = _norm_anchor(s)
        if target == ns:
            return True, 1.0, s, "exact"
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(text, s)
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        # contain **只在适用窗口内**启用：目标不能长过示例的 ECHO_CONTAIN_MAX_RATIO 倍，
        # 且示例本身要够长（归一后 ≥ ECHO_CONTAIN_MIN_SAMPLE），否则短示例的二元组底座太小，
        # 覆盖度会被噪声顶到 1.0（长文饱和误报就是这么来的）。
        base = _bigrams(s)
        in_window = (bool(ns) and len(target) <= len(ns) * ECHO_CONTAIN_MAX_RATIO
                     and len(ns) >= ECHO_CONTAIN_MIN_SAMPLE)
        if allow_contain and in_window and base:
            contain = len(_bigrams(text) & base) / float(len(base))
            if contain >= ECHO_CONTAIN and contain >= best_score:
                best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule
    return False, best_score, best_sample, ""


# 拆句：中文句末标点 + 英文句末标点 + 换行。用于**逐句**比对与逐句定位。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|(?<=[.!?])\s+|\n+")


def split_sentences(text):
    """把正文拆成句子列表（保序、去空白项）。"""
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def split_paras(text):
    """把正文拆成段落列表。段落 = 一个或连续多个非空行。"""
    paras, cur = [], []
    for line in (text or "").splitlines():
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append("\n".join(cur))
            cur = []
    if cur:
        paras.append("\n".join(cur))
    return paras


def prompt_echo_scan(text, samples=None, label="译文"):
    """在长文本里找「照抄提示词示例」的地方，返回命中列表（可能为空）。

    两层：整段先比一次（只认 exact / jaccard，兜整篇照抄的极端情况），
    再**逐句**比一次（含覆盖度判据，兜「某一句是抄的」这个真实形态）。
    """
    hits = []
    whole_hit, score, sample, rule = prompt_echo(text, samples, allow_contain=False)
    if whole_hit:
        hits.append({"part": label, "segment": (text or "")[:40], "rule": rule,
                     "sim": round(score, 3), "sample": sample,
                     "why": ("与提示词示例去掉标点后完全相同（照抄示例）" if rule == "exact"
                             else "与提示词示例相似度 {:.2f}，属同构照抄".format(score))})
        return hits
    for seg in split_sentences(text):
        hit, score, sample, rule = prompt_echo(seg, samples)
        if not hit:
            continue
        if rule == "contain":
            why = ("{}里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；适用窗口内才启用，见 ECHO_CONTAIN_MAX_RATIO）"
                   .format(label, seg[:20], score * 100, sample[:24], ECHO_CONTAIN))
        elif rule == "exact":
            why = "{}里的「{}」与提示词示例去掉标点后完全相同（照抄示例）".format(label, seg[:20])
        else:
            why = "{}里的「{}」与提示词示例相似度 {:.2f}，属同构照抄".format(label, seg[:20], score)
        hits.append({"part": label, "segment": seg[:40], "rule": rule,
                     "sim": round(score, 3), "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits


# ===========================================================================
# 闸门四：锚点到句子
#
# 「每条意见必须引用真实原文」这件事**不靠提示词求模型配合**，而是本地校验引文
# 能不能在源文（或译文）里找到。编造的引文会被剔出，并把整份产出判为定位失败。
# ===========================================================================

ANCHOR_MIN_SUBSTR = 4      # 精确子串匹配的最低长度（低风险判据，门槛可以矮）
ANCHOR_MIN_CHARS = 8       # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55          # 模糊匹配阈值
ANCHOR_MAX_MISS = 0.40     # 未锚定率超过它就判「定位失败」


def verify_anchor(quote, sentences, norms=None):
    """引文能否在给定句子里找到。返回 (是否锚定, 方式, 最相似的句子)。

    三级判据，从严到宽：
      1. 精确子串（去标点归一后）：引文是某句的连续子串 → 锚定
      2. 反向子串：某句是引文的连续子串（模型把两句拼一起引）
      3. 二元组 Jaccard ≥ ANCHOR_SIM 且引文够长
    """
    q = _norm_anchor(quote)
    if not q:
        return False, "empty", ""
    if len(q) < ANCHOR_MIN_SUBSTR:
        return False, "too_short", ""
    ns = norms if norms is not None else [_norm_anchor(s) for s in sentences]
    best, best_sim = "", 0.0
    for raw, n in zip(sentences, ns):
        if not n:
            continue
        if q in n or n in q:
            return True, "substring", raw
        if len(q) >= ANCHOR_MIN_CHARS and len(n) >= ANCHOR_MIN_CHARS:
            sim = _similarity(q, n)
            if sim > best_sim:
                best_sim, best = sim, raw
    if best_sim >= ANCHOR_SIM:
        return True, "fuzzy:{:.2f}".format(best_sim), best
    return False, "miss", best


def anchor_issues(issues, text, quote_key="quote", label="原文"):
    """把一份意见清单里的引文逐条本地校验。

    返回 (锚定列表, 未锚定列表, 统计)。未锚定的**剔出**后续流程（不许进重译输入）。
    """
    sentences = split_sentences(text)
    norms = [_norm_anchor(s) for s in sentences]
    good, bad = [], []
    for it in (issues or []):
        if not isinstance(it, dict):
            continue
        quote = str(it.get(quote_key) or "").strip()
        ok, how, matched = verify_anchor(quote, sentences, norms)
        rec = dict(it)
        rec["anchor"] = {"ok": ok, "how": how, "matched": matched[:80]}
        if ok:
            rec["sentence"] = matched
            good.append(rec)
        else:
            rec["unanchored_reason"] = (
                "这条意见引的「{}」在{}里找不到对应句子（判据：精确子串 / 反向子串 / "
                "二元组 Jaccard ≥ {:.2f}），按编造引文剔出".format(quote[:40], label, ANCHOR_SIM))
            bad.append(rec)
    total = len(good) + len(bad)
    stat = {"total": total, "verified": len(good), "unanchored": len(bad),
            "unanchored_ratio": round(len(bad) / float(total), 3) if total else 0.0}
    return good, bad, stat


# ===========================================================================
# 闸门五：术语一致性（**本包核心之一**）
#
# 这是"跨语言 + 四个立场互审"在结构上独有的一件事：同一个源词在全篇必须同一个译法。
# 判定**不靠模型自报**，本地自己算：
#
#   1. 从源文里按**句子**找术语表的每个源词 → 得到出现位置集合
#   2. 用译文返回的逐句对齐（source 句 ↔ target 句）定位每一处对应的目标句
#   3. 逐处检查该目标句里有没有**规范译法的变体**（大小写/复数/连字符归一）
#   4. 判定：
#        · 有 ≥1 处用了规范译法、又有 ≥1 处没用 → **不一致**（同词多译）→ 硬闸门
#        · 一处都没用规范译法，但该词在源文里出现多次 → **术语表未落地** → 硬闸门
#        · 只出现一次且译法不同 → 提示（可能是合理意译），不拦
#
# 目标语言是英文时，"同一个词的不同译法"最常见的形态是大小写与单复数
# （`short drama` / `Short Drama` / `short dramas`），所以归一化必须把这三样抹平，
# 否则闸门会被格式差异刷屏、误报到没人看。
# ===========================================================================

GLOSSARY_TYPES = ("品牌名", "产品名", "专有名词", "行业术语", "功能名词", "人名", "机构名")


def _norm_term(s, target_lang=None):
    """术语归一：小写、去空格与连字符、去英文复数尾、去中文标点。

    为什么必须做：`Short Drama` / `short-drama` / `short dramas` 在术语一致这件事上
    是**同一个译法**；不归一就会把格式差异报成"同词多译"，闸门立刻废掉。
    """
    t = _norm_anchor(s).lower()
    if not t:
        return ""
    if target_lang and str(target_lang).startswith(("en", "es", "pt", "fr", "de")):
        # 英文类语言的复数与所有格：-s / -es / -'s（归一后撇号已被抹掉）
        if len(t) > 4 and t.endswith("es") and not t.endswith("ses"):
            t = t[:-2]
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
    return t


def _term_variants(canonical):
    """规范译法的可接受变体（归一后同一即可，这里只为报告时能列出人看得懂的形式）。"""
    base = str(canonical or "").strip()
    out = [base]
    if base and base[0].isascii() and base[0].isalpha() and base[0].islower():
        out.append(base[0].upper() + base[1:])
    return out


def glossary_consistency(source_text, target_text, glossary, pairs=None, target_lang=None):
    """逐处核对术语表是否落地、是否全篇一致。**纯本地、零成本**。

    返回一个报告 dict：`terms` 每条术语逐处明细 + 全篇判定；`inconsistent` 汇总。
    `pairs` 是译文返回的逐句对齐（`[{"source":…, "target":…}]`），
    有它才能把"源文里的这一处"映射到"译文里的那一句"；没有就退化为全篇检查。
    """
    src_sents = split_sentences(source_text)
    tgt_sents = split_sentences(target_text)
    pair_src = []
    pair_tgt = []
    if isinstance(pairs, list):
        for p in pairs:
            if isinstance(p, dict):
                pair_src.append(str(p.get("source") or ""))
                pair_tgt.append(str(p.get("target") or ""))
    terms, inconsistent = [], []
    for g in (glossary or []):
        if not isinstance(g, dict):
            continue
        src_term = str(g.get("source_term") or "").strip()
        canon = str(g.get("canonical") or "").strip()
        if not src_term or not canon:
            continue
        canon_n = _norm_term(canon, target_lang)
        occ = []
        for i, s in enumerate(src_sents):
            if src_term in s:
                occ.append(i)
        if not occ:
            terms.append({"source_term": src_term, "canonical": canon, "type": g.get("type"),
                          "occurrences": 0, "hits": 0, "misses": [],
                          "verdict": "未在源文出现（词表项已忽略）"})
            continue
        hits, misses = [], []
        for i in occ:
            tgt = None
            if pair_tgt and i < len(pair_tgt):
                tgt = pair_tgt[i]
            if tgt is None and tgt_sents and i < len(tgt_sents):
                tgt = tgt_sents[i]
            if tgt is None:
                tgt = target_text or ""
            if canon_n and canon_n in _norm_term(tgt, target_lang):
                hits.append({"src_sentence": src_sents[i][:80], "target_sentence": tgt[:120]})
            else:
                misses.append({"src_sentence": src_sents[i][:80], "target_sentence": tgt[:120],
                               "source_index": i})
        if misses and hits:
            verdict = "不一致（同一源词在部分位置没用规范译法）"
            inconsistent.append({"source_term": src_term, "canonical": canon,
                                 "occurrences": len(occ), "hits": len(hits),
                                 "misses": misses, "kind": "mixed"})
        elif misses and len(occ) >= 2:
            verdict = "术语表未落地（全篇都没用规范译法）"
            inconsistent.append({"source_term": src_term, "canonical": canon,
                                 "occurrences": len(occ), "hits": 0,
                                 "misses": misses, "kind": "ignored"})
        elif misses:
            verdict = "单处译法不同（可能是合理意译，仅提示）"
        else:
            verdict = "全篇一致"
        terms.append({"source_term": src_term, "canonical": canon,
                      "type": g.get("type") or g.get("category"), "occurrences": len(occ),
                      "hits": len(hits), "misses": misses, "verdict": verdict})
    used = [t for t in terms if t["occurrences"]]
    return {
        "version": GLOSSARY_VERSION,
        "terms": terms,
        "checked_terms": len(used),
        "inconsistent": inconsistent,
        "inconsistent_count": len(inconsistent),
        "pair_alignment": {"pairs": len(pair_tgt), "source_sentences": len(src_sents),
                           "target_sentences": len(tgt_sents)},
        "ok": not inconsistent,
    }


# ===========================================================================
# 闸门六：数字与单位保全（**本包核心之二**）
#
# 跨语言场景里这条比同语言的改稿更要命：源文写「3 斤」，译文写「3 jin」等于没本地化；
# 写「1.5 斤」等于把数字改了；写「3 kg」则是**算错**（3 斤 = 1.5 kg）。
# 所以本地做三件事：
#   1. 抽源文的数字 + 单位（确定性）
#   2. 按单位换算表算出**目标市场的期望值**
#   3. 在译文里查：数字还在吗？换算对不对？
#
# 【诚实说明这是启发式】数字这一条是确定性的；单位换算只在登记过的单位上做
# （未登记的单位只查数字在不在，不判对错）。货币换算必须显式给汇率 ——
# **不给汇率就不猜**，只查数字在不在。
# ===========================================================================

_NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?")

# 计量单位换算：单位 → (基准量, 目标市场, 换算函数名, 目标单位, 说明)
# 只登记**有确定换算系数**的，且只在目标市场用英制时才判对错。
MASS_UNITS = {
    "斤": ("mass", 0.5, "公斤/千克/kg"),
    "公斤": ("mass", 1.0, "公斤/千克/kg"),
    "千克": ("mass", 1.0, "公斤/千克/kg"),
    "kg": ("mass", 1.0, "公斤/千克/kg"),
    "KG": ("mass", 1.0, "公斤/千克/kg"),
    "克": ("mass", 0.001, "公斤/千克/kg"),
    "g": ("mass", 0.001, "公斤/千克/kg"),
    "磅": ("mass", 0.45359237, "公斤/千克/kg"),
    "lb": ("mass", 0.45359237, "公斤/千克/kg"),
    "lbs": ("mass", 0.45359237, "公斤/千克/kg"),
}
LENGTH_UNITS = {
    "米": ("len", 1.0, "米/m"),
    "m": ("len", 1.0, "米/m"),
    "厘米": ("len", 0.01, "米/m"),
    "cm": ("len", 0.01, "米/m"),
    "毫米": ("len", 0.001, "米/m"),
    "mm": ("len", 0.001, "米/m"),
    "公里": ("len", 1000.0, "米/m"),
    "千米": ("len", 1000.0, "米/m"),
    "km": ("len", 1000.0, "米/m"),
    "英里": ("len", 1609.344, "米/m"),
    "mile": ("len", 1609.344, "米/m"),
    "miles": ("len", 1609.344, "米/m"),
    "英尺": ("len", 0.3048, "米/m"),
    "ft": ("len", 0.3048, "米/m"),
    "feet": ("len", 0.3048, "米/m"),
    "inch": ("len", 0.0254, "米/m"),
    "英寸": ("len", 0.0254, "米/m"),
}
AREA_UNITS = {
    "平方米": ("area", 1.0, "平方米/m2"),
    "平米": ("area", 1.0, "平方米/m2"),
    "m2": ("area", 1.0, "平方米/m2"),
    "㎡": ("area", 1.0, "平方米/m2"),
    "平方英尺": ("area", 0.09290304, "平方米/m2"),
    "sqft": ("area", 0.09290304, "平方米/m2"),
    "sq ft": ("area", 0.09290304, "平方米/m2"),
    "亩": ("area", 666.6667, "平方米/m2"),
    "公顷": ("area", 10000.0, "平方米/m2"),
}
TEMP_UNITS = {"摄氏度": ("temp", None, "摄氏度/°C"), "°c": ("temp", None, "摄氏度/°C"),
              "°f": ("temp", None, "华氏度/°F"), "华氏度": ("temp", None, "华氏度/°F")}
ALL_UNITS = {}
for _d in (MASS_UNITS, LENGTH_UNITS, AREA_UNITS, TEMP_UNITS):
    ALL_UNITS.update(_d)

# 目标市场是否用英制（决定"必须换算"的判定）。**只对登记过的市场下结论**，
# 没登记就退化为"只查数字在不在"，不猜。
IMPERIAL_MARKETS = {"us"}
# 英制下的目标单位与换算（基准量 → 目标单位）。基准：质量 kg、长度 m、面积 m2。
IMPERIAL_TARGET = {
    "mass": ("lb", 2.2046226218),
    "len": ("ft", 3.280839895),
    "area": ("sq ft", 10.76391042),
}
# 单位出现在数字**后面**的匹配：`3 斤` / `3斤` / `3 kg` / `3.5公斤`
_NUM_UNIT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(平方米|平米|平方英尺|sq\s*ft|sqft|㎡|摄氏度|华氏度|°C|°F|"
    r"公斤|千克|厘米|毫米|公里|千米|英里|英尺|英寸|斤|克|磅|亩|公顷|"
    r"kg|KG|lb|lbs|km|cm|mm|ft|feet|inch|miles|mile|g|m)(?![A-Za-z0-9])",
    re.I)

# 货币：只查数字与符号在不在，**不给汇率就不换算**（禁止编价/编汇率）。
CURRENCY_TOKENS = {"元": "CNY", "块": "CNY", "人民币": "CNY", "万元": "CNY",
                   "美元": "USD", "美金": "USD", "欧元": "EUR", "日元": "JPY",
                   "港币": "HKD", "英镑": "GBP", "USD": "USD", "CNY": "CNY",
                   "EUR": "EUR", "$": "USD", "¥": "CNY", "€": "EUR", "£": "GBP"}


def _num_close(a, b, rel=0.02, abs_=0.06):
    """两个数是否"算得对"：允许 2% 相对误差或 0.06 绝对误差（模型会四舍五入）。"""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= max(abs_ + abs(a) * rel, abs_)


def extract_measure_facts(text):
    """抽源文里的「数字 + 单位」事实（确定性）。返回列表。"""
    out = []
    t = text or ""
    for m in _NUM_UNIT_RE.finditer(t):
        raw_num = m.group(1).replace(",", ".")
        unit = re.sub(r"\s+", " ", m.group(2)).strip()
        key = unit.lower().replace(" ", "")
        spec = ALL_UNITS.get(unit) or ALL_UNITS.get(key)
        if spec is None:
            # 单位没登记（含 `m` 这类歧义单位被 \b? 放宽后误抓的），只记数字
            out.append({"number": raw_num, "unit": unit, "family": None, "base": None,
                        "registered": False,
                        "context": t[max(0, m.start() - 12):m.end() + 12]})
            continue
        family, factor, base_unit = spec
        try:
            val = float(raw_num)
        except ValueError:
            continue
        base = None
        if family == "temp":
            base = val
        elif factor is not None:
            base = val * factor
        out.append({"number": raw_num, "value": val, "unit": unit, "family": family,
                    "factor": factor, "base": base, "base_unit": base_unit,
                    "registered": True,
                    "context": t[max(0, m.start() - 12):m.end() + 12]})
    return out


def extract_numbers(text):
    """抽所有裸数字（含货币符号形态），用于"数字丢了没有"这一层。"""
    out = []
    for m in _NUM_TOKEN_RE.finditer(text or ""):
        raw = m.group(0)
        out.append({"raw": raw, "value": float(raw.replace(",", ".")),
                    "context": (text or "")[max(0, m.start() - 14):m.end() + 14]})
    return out


def number_in_text(target, num, rel=0.02):
    """译文里有没有这个数（**换写法也算**：3 → 三 / three / 3.0；斤→kg 的换算值也算）。

    这是"数字保全"闸门的核心判据，所以它刻意宽松一点，宁可漏报也不误报 ——
    真正会拦下来的是**数字整条消失**，不是"写法变了"。
    """
    if num is None:
        return False
    t = target or ""
    try:
        val = float(str(num).replace(",", "."))
    except (TypeError, ValueError):
        return bool(str(num) in t)
    # 直接形态：3 / 3.0 / 3.00
    for m in _NUM_TOKEN_RE.finditer(t):
        try:
            got = float(m.group(0).replace(",", "."))
        except ValueError:
            continue
        if _num_close(got, val, rel=rel):
            return True
    # 中文数字
    if _cn_number_in_text(t, val):
        return True
    # 英文拼写（one..twenty 与常见的整十）
    if _en_number_in_text(t, val):
        return True
    return False


_CN_DIGIT = "零一二三四五六七八九"
_CN_UNIT = ("", "十", "百", "千")
_CN_BIG = ("", "万", "亿")


def int_to_cn(n):
    """非负整数 → 中文写法（0~99999999）。只为判断"数字是不是只换了写法"。"""
    n = int(n)
    if n < 0:
        return ""
    if n == 0:
        return "零"
    groups = []
    while n > 0:
        groups.append(n % 10000)
        n //= 10000
    out = []
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi]
        if g == 0:
            if out and not out[-1].endswith("零"):
                out.append("零")
            continue
        seg, zero = [], False
        for pos in range(3, -1, -1):
            d = (g // (10 ** pos)) % 10
            if d == 0:
                zero = True
                continue
            if zero and seg:
                seg.append("零")
            zero = False
            seg.append(_CN_DIGIT[d] + _CN_UNIT[pos])
        s = "".join(seg)
        if s.startswith("一十"):
            s = s[1:]
        out.append(s + _CN_BIG[gi])
    return "".join(out).rstrip("零") or "零"


def _cn_number_in_text(text, val):
    if val != int(val) or val < 0 or val > 99999999:
        return False
    return int_to_cn(int(val)) in (text or "")


_EN_ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
            "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
            "sixteen", "seventeen", "eighteen", "nineteen")
_EN_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
            "eighty", "ninety")


def _en_number_words(n):
    n = int(n)
    if n < 0 or n > 999:
        return []
    if n < 20:
        return [_EN_ONES[n]]
    if n < 100:
        w = [_EN_TENS[n // 10]]
        if n % 10:
            w.append(_EN_ONES[n % 10])
        return [" ".join(w)] + w
    w = [_EN_ONES[n // 100] + " hundred"]
    r = n % 100
    if r:
        w.append(_EN_ONES[r] if r < 20 else _EN_TENS[r // 10])
        w.append(_EN_ONES[r] if r < 20 else _EN_TENS[r // 10])
    return w


def _en_number_in_text(text, val):
    if val != int(val) or val < 0 or val > 999:
        return False
    low = (text or "").lower()
    return any(w and w in low for w in _en_number_words(int(val)))


def convert_expected(fact, market):
    """按目标市场算出期望值。返回 dict 或 None（不该换算/没有汇率）。

    **不给汇率就不猜**：货币换算必须显式给 `--fx-rate`；没给只查数字在不在。
    """
    fam = fact.get("family")
    if not fact.get("registered") or fam is None or fact.get("base") is None:
        return None
    if market in IMPERIAL_MARKETS:
        if fam == "temp":
            c = fact["value"]
            if fact["unit"].lower() in ("°f", "华氏度"):
                return None                    # 源文本来就是华氏度，不用换
            return {"unit": "°F", "value": c * 9.0 / 5.0 + 32.0,
                    "why": "摄氏 → 华氏（目标市场用华氏度）"}
        tgt = IMPERIAL_TARGET.get(fam)
        if tgt:
            unit, factor = tgt
            return {"unit": unit, "value": (fact["base"] or 0) * factor,
                    "why": "{} → {}（目标市场用英制）".format(fact["unit"], unit)}
        return None
    # 公制市场：源文用的就是公制 → 不需要换算
    if fam == "temp" and fact["unit"].lower() in ("°f", "华氏度"):
        return {"unit": "°C", "value": (fact["value"] - 32.0) * 5.0 / 9.0,
                "why": "华氏 → 摄氏（目标市场用公制）"}
    if fam in ("mass", "len", "area") and fact.get("factor") and fact["unit"] not in (
            {"mass": "公斤", "len": "米", "area": "平方米"}.get(fam),):
        base_unit = {"mass": "kg", "len": "m", "area": "m2"}[fam]
        return {"unit": base_unit, "value": fact["base"],
                "why": "换算到公制基准单位 {}（源文单位 {}）".format(base_unit, fact["unit"])}
    return None


def measure_report(source_text, target_text, market, pairs=None, fx_rate=None):
    """数字与单位保全报告（纯本地、零成本）。

    三层判定：
      1. **数字还在吗**：源文里每个数字，译文里有没有（换写法也算）→ 丢了就是硬闸门
      2. **单位换算对吗**：登记过的单位按目标市场算期望值，译文里查得到吗
      3. **货币**：只查数字与货币符号是否在；给了 `--fx-rate` 才额外算期望值
    """
    facts = extract_measure_facts(source_text)
    bare = extract_numbers(source_text)
    tgt = target_text or ""
    registered_vals = set()
    rows, missing, wrong = [], [], []
    for f in facts:
        n = f["number"]
        exp = convert_expected(f, market)
        exp_ok = None
        if exp is not None:
            exp_ok = number_in_text(tgt, round(exp["value"], 4), rel=0.03)
            registered_vals.add(round(float(n.replace(",", ".")), 4))
        present = number_in_text(tgt, n)
        # ⚠️ 判定口径（本包自测时想错了一次）：
        #   · 需要换算时，**换算后的值在**就等于这个事实在（3 斤 → 3.31 lb 不该判"丢了 3"）
        #   · 需要换算、原数字在、换算值不在 → 这是**没本地化 / 算错**，不是丢数字
        #   · 不需要换算时，只有原数字在才算在
        if exp is not None:
            kept = bool(exp_ok)
            bad_conv = bool(present) and not exp_ok
        else:
            kept = present
            bad_conv = False
        rec = {"number": n, "unit": f["unit"], "context": f["context"],
               "present": kept, "number_as_source": present, "expected": exp,
               "expected_present": exp_ok, "registered": f["registered"]}
        rows.append(rec)
        if not kept:
            missing.append(rec)
        elif bad_conv:
            wrong.append(rec)
    # 裸数字（没跟单位的）单独查一轮：货币、日期、规格都靠它
    for b in bare:
        v = b["value"]
        if round(v, 4) in registered_vals:
            continue
        if not number_in_text(tgt, b["raw"]):
            # 货币汇率：给了汇率才额外算
            text_ctx = b["context"]
            cur = None
            for k, code in CURRENCY_TOKENS.items():
                if k in text_ctx:
                    cur = code
                    break
            extra = None
            if cur and fx_rate and cur == "CNY" and market in ("us", "eu", "jp"):
                tgt_cur = {"us": "USD", "eu": "EUR", "jp": "JPY"}[market]
                if tgt_cur == "USD" and fx_rate:
                    extra = {"unit": tgt_cur, "value": v * fx_rate,
                             "why": "按用户给的汇率换算（汇率是外部输入，脚本不猜）"}
                    if number_in_text(tgt, round(extra["value"], 4), rel=0.03):
                        rows.append({"number": b["raw"], "unit": cur, "context": text_ctx,
                                     "present": False, "expected": extra,
                                     "expected_present": True, "registered": False,
                                     "note": "原数字不在译文里，但换算后的金额在（判为已本地化）"})
                        continue
            miss = {"number": b["raw"], "unit": cur, "context": text_ctx,
                    "present": False, "expected": extra, "expected_present": None,
                    "registered": False}
            rows.append(miss)
            missing.append(miss)
    return {
        "version": UNIT_RULES_VERSION,
        "market": market,
        "imperial": market in IMPERIAL_MARKETS,
        "fx_rate": fx_rate,
        "rows": rows,
        "missing": missing,
        "missing_count": len(missing),
        "wrong_conversion": wrong,
        "wrong_count": len(wrong),
        "ok": not missing and not wrong,
    }


# ===========================================================================
# 闸门七：裁决完整性（**不许假装谈拢**）
#
# 每一席的打回/否决都必须留下可读理由；四条交叉核对防止"名义上互审、实际放行"：
#   1. 说打回了却没给理由 → 拦
#   2. 说放行了却在自己的清单里列了高风险项 → 拦（自相矛盾）
#   3. 下了打回/否决的结论，最终产物却声称"全部通过" → 拦（假装谈拢）
#   4. 综合裁决声称"综合评估后放行"但仍有未决项 → 拦
# ===========================================================================

FAKE_AGREE_PATTERNS = [
    r"综合评估后放行", r"综合来看没有问题", r"总体上可以接受", r"基本符合要求",
    r"已基本解决", r"不影响发布", r"可以发布", r"视为通过",
]
FAKE_AGREE_RE = re.compile("|".join(FAKE_AGREE_PATTERNS))
NO_REASON_WORDS = ("", "无", "N/A", "n/a", "-", "略", "见上", "同上")


def verdict_gate(verdict, reasons, role, require_reason_for=VERDICT_HARD):
    """单席裁决书的完整性检查。返回问题清单（空 = 通过）。"""
    problems = []
    v = verdict if verdict in VERDICT_ANY else None
    if v is None:
        problems.append("「{}」没有给出可识别的裁决（取值只能是 {}）"
                        .format(ROLES[role]["name"], " / ".join(VERDICT_ANY)))
        return problems
    if v in require_reason_for:
        rs = [str(r).strip() for r in (reasons or []) if str(r).strip()]
        rs = [r for r in rs if r not in NO_REASON_WORDS]
        if not rs:
            problems.append("「{}」判了 {}（{}），却没有留下任何理由 —— "
                            "打回/否决必须留可读理由"
                            .format(ROLES[role]["name"], v, VERDICT_LABEL.get(v, v)))
    return problems


def decision_closure(final, roles_verdicts, unresolved, rounds_used):
    """全局裁决闭合检查：**不许假装谈拢**。

    `final` 是最终综合裁决 dict，`roles_verdicts` 是四席各自的裁决。
    返回问题清单；命中任何一条都意味着产出在"声称的状态"与"实际状态"之间对不上。
    """
    problems = []
    hard = {r: v for r, v in (roles_verdicts or {}).items()
            if v in VERDICT_HARD and r in ROLES}
    fv = (final or {}).get("verdict")
    if fv not in VERDICT_ANY:
        problems.append("最终裁决没有给出可识别的结论（取值只能是 {}）"
                        .format(" / ".join(VERDICT_ANY)))
    if hard and fv == VERDICT_PASS:
        problems.append("{} 判了打回/否决，最终裁决却写「放行」—— 少数派被抹平，"
                        "不许假装谈拢".format(
                            "、".join(ROLES[r]["name"] for r in hard)))
    if unresolved and fv == VERDICT_PASS:
        problems.append("还有 {} 条未决项，最终裁决却写「放行」".format(len(unresolved)))
    text = " ".join(str((final or {}).get(k) or "") for k in
                    ("summary", "reason", "note", "rationale"))
    if unresolved and FAKE_AGREE_RE.search(text):
        m = FAKE_AGREE_RE.search(text)
        problems.append("还有未决项，最终裁决里却出现「{}」这类**假装谈拢**的措辞"
                        .format(m.group(0)))
    if fv in VERDICT_HARD and not str((final or {}).get("reason") or "").strip():
        problems.append("最终裁决判了 {}，却没写理由".format(VERDICT_LABEL.get(fv, fv)))
    if rounds_used and not (final or {}).get("rounds_used"):
        problems.append("最终裁决里没有记录用了多少轮（无法复核终止机制）")
    return problems


# ===========================================================================
# 信息隔离：结构性的，不是口头约定
# ===========================================================================

class IsolationBreach(Exception):
    """提示词里出现了本该被隔离的结论标记词（结构性信息隔离被破坏）。"""


def check_isolation(stage, prompt_text, excluded_fields=None):
    """在**每次调用前**做文本级检查：本角色看不到的字段，其标记词不许出现在提示词里。

    返回 {"stage","excluded","markers_checked","leaked","ok"}，结果写进产出与流程日志。
    这是"排除一个字段"的可复核证据：靠的不是"我模板里没写"，而是"调用前真的扫过一遍"。
    """
    if stage not in ROLES:
        return {"stage": stage, "excluded": [], "markers_checked": 0, "leaked": [], "ok": True}
    excluded = list(excluded_fields if excluded_fields is not None
                    else ROLES[stage]["forbidden"])
    checked, leaked = 0, []
    for field in excluded:
        for mk in ISOLATION_MARKERS.get(field, []):
            checked += 1
            if mk in (prompt_text or ""):
                leaked.append({"field": field, "marker": mk})
    return {"stage": stage, "role": ROLES[stage]["name"], "excluded": excluded,
            "markers_checked": checked, "leaked": leaked, "ok": not leaked}


def assert_isolation(stage, prompt_text, excluded_fields=None):
    """不通过就抛 —— **调用前**抛，一分钱都不花。"""
    rep = check_isolation(stage, prompt_text, excluded_fields)
    if not rep["ok"]:
        leaked = "、".join("{}里的「{}」".format(x["field"], x["marker"])
                          for x in rep["leaked"])
        raise IsolationBreach(
            "信息隔离被破坏：「{}」这一席的提示词里出现了本该看不到的 {}。"
            "宁可不发这次调用，也不要让四个角色变成一次回答的四种复述。"
            .format(ROLES[stage]["name"], leaked))
    return rep


# ===========================================================================
# 闸门总入口
# ===========================================================================

def text_gates(text, label, material=None, market=DEFAULT_MARKET, side="output"):
    """闸门一/二/三的统一入口。返回 (problems, detail)。

    `side="material"`：源文口径（全扫高/中/低）
    `side="output"`：产出侧口径（只扫高风险 + 排除引用/警告语境，被排除的留原因）
    """
    problems, detail = [], {}
    if side == "material":
        comp, exempted = compliance_scan(text)
        mk_hits, _mk = market_compliance_scan(text, market)
        comp = list(comp) + list(mk_hits)
        quoted, mentioned, soft = [], [], []
    else:
        comp, quoted, mentioned, soft, exempted = compliance_scan_output(
            text, material or "", market)
    if comp:
        detail["compliance"] = comp
        for h in comp[:3]:
            problems.append("合规命中【{}】「{}」：{}".format(
                h.get("level", "?"), h.get("word") or h.get("match"), h.get("why")))
        if len(comp) > 3:
            problems.append("合规还有 {} 处命中（见 --json 的 gates.compliance）"
                            .format(len(comp) - 3))
    if exempted:
        detail["compliance_exempted"] = exempted
    if quoted:
        detail["compliance_quoted"] = quoted
    if mentioned:
        detail["compliance_mentioned"] = mentioned
    if soft:
        detail["compliance_contextual_only"] = soft
    ph = placeholder_hits(text)
    if ph:
        detail["placeholder"] = ph
        for h in ph[:3]:
            problems.append("占位符残留：{}（{}）".format(h["word"], h["why"]))
    echo = prompt_echo_scan(text, label=label)
    if echo:
        detail["prompt_echo"] = echo
        for h in echo[:2]:
            problems.append("照抄提示词示例：{}".format(h["why"]))
    return problems, detail


# ===========================================================================
# 提示词卫生自检
#
# 教训是通用的：一个为**产出**设计的检查，不能直接拿去扫**输入**
# （提示词里为说明输出结构写的 `{...}` 不是没填干净的模板）。
# 所以这张表**刻意比 PLACEHOLDER_PATTERNS 窄**。
# ===========================================================================

PROMPT_DIRT_PATTERNS = [
    (r"\{\s*\}", "提示词里有空占位花括号"),
    (r"待填|待补充|待定", "提示词里有「待填/待补充」字样"),
    (r"\bXXX+\b|\bxxx+\b", "提示词里有连续占位字母"),
    (r"\bTODO\b|\bTBD\b|\bFIXME\b", "提示词里有 TODO/TBD 标记"),
    (r"请(填写|替换|补充)", "提示词里有「请填写/请替换」提示语"),
]
PROMPT_DIRT_RE = [(re.compile(p), why) for p, why in PROMPT_DIRT_PATTERNS]


def prompt_hygiene(prompt):
    """出站前扫一眼提示词里有没有"可照抄的脏东西"。返回命中列表。"""
    hits = []
    for rx, why in PROMPT_DIRT_RE:
        m = rx.search(prompt or "")
        if m:
            hits.append({"match": m.group(0)[:30], "why": why})
    return hits


# ===========================================================================
# 异常与成本
# ===========================================================================

class LcError(a7w.A7wError):
    """本地化流程里的所有可预期失败。子类各自带退出码。"""
    exit_code = EXIT_CALL


class UsageError(LcError):
    """参数/配置用错了（文件不存在、市场名错、给了 --budget 没给单价…）。→ 退出码 2

    为什么要跟调用失败分开：这两类错误的**处理方式完全不同**。
    参数错了改命令重跑，不花一分钱；调用失败要查 Key / 点数 / 模型名。
    """
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """产出路径落在 Skill 包内（退出码 2）。"""


class GateFail(LcError):
    """硬闸门命中（退出码 3）。"""
    exit_code = EXIT_GATE


class BudgetStop(LcError):
    """预算超限，已就地中止（退出码 5）。"""
    exit_code = EXIT_BUDGET


class UnresolvedStop(LcError):
    """轮次用尽仍有未决项（退出码 6）—— 分歧如实报出，不许假装谈拢。"""
    exit_code = EXIT_UNRESOLVED


class DryRunStop(Exception):
    """`--dry-run`：把将发出的提示词带出来，不花钱。"""

    def __init__(self, stage, prompt, system=None):
        Exception.__init__(self, stage)
        self.stage, self.prompt, self.system = stage, prompt, system


# 字符 → token 的标定比例（**是同族实测值**，不是厂商文档）：
CHARS_PER_TOKEN_IN = 1.61      # 输入侧：拿真实调用标定，实测均值 1.612
TOKENS_PER_CHAR_OUT = 1.11     # 输出侧：1 个原始字符 ≈ 多少 token，实测均值 1.109
POINTS_PER_YUAN = 100.0        # 平台口径：1 元 = 100 点

# 各席输出的经验 token 量（报价用）。**刻意压低**：
# 输出越长，越容易撞上 `max_tokens`（`finish_reason=length`），
# 也越容易碰上模型吐坏 JSON（实测到过语法错与传输中断两种）。
# 所以上限不是"越大越好"，而是"刚好够写短"。
# ⚠️ 曾经这里写着"网关在 2600~2900 字符处有上限"—— 那是个**错误归因**，已撤回：
# 同一端点实测能拿到 3984 字符的完整内容（`finish_reason='stop'`）。
GLOSSARY_OUT_TOKENS = 700
TRANSLATE_OUT_TOKENS = 1500
TERM_OUT_TOKENS = 700
CULTURE_OUT_TOKENS = 1200
COMPLIANCE_OUT_TOKENS = 1200


def estimate_tokens_in(text):
    """估输入 token。用**原始字符数**（含换行），因为换行也要花 token。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(text, rounds=DEFAULT_ROUNDS, retry_rate=0.5):
    """一次协作的调用清单（用于报价，越清楚越好）。

    `retry_rate` 是"某一席打回后需要重译"的经验概率，用来把轮次折成期望调用数 ——
    报价宁可略高，别让人以为 11 次就够。
    """
    src_in = estimate_tokens_in(text)
    per_call_in = src_in + 460      # 源文 + 术语表/市场规则/输出 schema 的固定开销
    calls = [
        {"stage": "术语表（glossary）", "calls": 1,
         "tokens_in": per_call_in, "tokens_out": GLOSSARY_OUT_TOKENS,
         "note": "源文 → 术语表；可用 --glossary 复用已有结果，省掉这一次"},
        {"stage": "初译（译审 translate）", "calls": 1,
         "tokens_in": per_call_in + 200, "tokens_out": TRANSLATE_OUT_TOKENS,
         "note": "译文 + 逐句回译对照"},
        {"stage": "四席互审（术语官 / 文化适配 / 合规）", "calls": 3,
         "tokens_in": per_call_in * 3, "tokens_out": TERM_OUT_TOKENS + CULTURE_OUT_TOKENS
         + COMPLIANCE_OUT_TOKENS,
         "note": "四次独立调用，提示词里只有本席的立场（术语官是纯本地校验，不花 token）"},
        {"stage": "重译（每轮被打回就 1 次）",
         "calls": max(0, int(round(max(0, rounds) * retry_rate))),
         "tokens_in": (per_call_in + 400) * max(0, int(round(max(0, rounds) * retry_rate))),
         "tokens_out": TRANSLATE_OUT_TOKENS * max(0, int(round(max(0, rounds) * retry_rate))),
         "note": "重译输入只带**本席自己的可执行要求**，不带别人的立场"},
    ]
    return calls


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    """按 token 与单价算点数/金额。**不给单价就不给金额 —— 不编价。**"""
    rec = {"tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
           "tokens_total": int(tokens_in) + int(tokens_out),
           "price_in": price_in, "price_out": price_out,
           "points": None, "yuan": None, "priced": bool(price_in is not None
                                                        and price_out is not None)}
    if rec["priced"]:
        pts = (tokens_in / 1e6) * float(price_in) + (tokens_out / 1e6) * float(price_out)
        rec["points"] = round(pts, 4)
        rec["yuan"] = round(pts / POINTS_PER_YUAN, 6)
    return rec


def fmt_cost(rec):
    """人读的 token 描述。

    ⚠️ 要能吃下**两种形状**：`compute_cost` 的报价记录（`tokens_in` / `tokens_out` /
    `tokens_total`）与 `CostTracker.usage` 的累计用量（`prompt_tokens` /
    `completion_tokens` / `total_tokens`）。
    事故（本包真机跑到最后一刻才炸）：只按第一种形状写，累计用量进来就是
    `KeyError: 'tokens_total'` —— 前面每一步都成功，倒在"打印成本"这一行。
    """
    if not rec:
        return "（无记录）"
    tin = rec.get("tokens_in")
    tout = rec.get("tokens_out")
    ttot = rec.get("tokens_total")
    if tin is None:
        tin = rec.get("prompt_tokens") or 0
    if tout is None:
        tout = rec.get("completion_tokens") or 0
    if ttot is None:
        ttot = rec.get("total_tokens") or (int(tin or 0) + int(tout or 0))
    s = "{} token（入 {} / 出 {}）".format(int(ttot or 0), int(tin or 0), int(tout or 0))
    if rec.get("calls"):
        s += "，共 {} 次调用".format(rec["calls"])
    pts = rec.get("points")
    yuan = rec.get("yuan")
    if pts is None and rec.get("priced") and rec.get("price_in") is not None:
        pts = ((int(tin or 0) / 1e6) * float(rec.get("price_in") or 0)
               + (int(tout or 0) / 1e6) * float(rec.get("price_out") or 0))
        yuan = pts / POINTS_PER_YUAN
    if pts is not None:
        s += "，约 {:.4f} 点".format(pts)
        if yuan is not None:
            s += " ≈ {:.6f} 元".format(yuan)
    else:
        s += "（没给单价，本包不编金额）"
    return s


def new_usage():
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


def add_usage(acc, usage):
    if not usage:
        return acc
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        try:
            acc[k] = int(acc.get(k, 0)) + int(usage.get(k) or 0)
        except (TypeError, ValueError):
            pass
    # 记调用次数（`calls` 是消费者最关心的两个数之一，另一个是 token）。
    # 事故（本包真机跑完才注意到）：累计用量里 `calls` 一直是 0，因为这里没加 ——
    # `new_usage()` 初始化了它，但没人维护，报告里的"共 N 次调用"永远是空的。
    acc["calls"] = int(acc.get("calls", 0)) + 1
    return acc


class CostTracker:
    """调用级成本台账。`--budget` 是**硬上限**：超了就地中止，不再发下一次请求。"""

    def __init__(self, budget=None, price_in=None, price_out=None):
        self.budget = budget
        self.price_in = price_in
        self.price_out = price_out
        self.calls = []
        self.usage = new_usage()
        self.spent_points = 0.0

    def charge(self, label, usage, elapsed=0.0):
        rec = {"label": label, "usage": usage or {}, "elapsed": round(elapsed, 2)}
        self.calls.append(rec)
        add_usage(self.usage, usage)
        if self.price_in is not None and self.price_out is not None and usage:
            pts = ((int(usage.get("prompt_tokens") or 0) / 1e6) * float(self.price_in)
                   + (int(usage.get("completion_tokens") or 0) / 1e6) * float(self.price_out))
            rec["points"] = round(pts, 4)
            self.spent_points += pts
        return rec

    def check(self, label):
        """花钱之前先算一次。超预算**在发请求之前**抛，钱不会花出去。"""
        if self.budget is None:
            return
        if self.price_in is None or self.price_out is None:
            raise UsageError("给了 --budget 就必须给 --price-in 与 --price-out"
                             "（单位：点/百万 token）—— 没有单价，预算上限没有意义")
        if self.spent_points >= self.budget:
            raise BudgetStop("已花 {:.4f} 点，达到 --budget {:.4f}，就地中止（{}）"
                             .format(self.spent_points, self.budget, label))

    def priced_dict(self):
        d = dict(self.usage)
        if self.price_in is not None and self.price_out is not None:
            d["points"] = round(self.spent_points, 4)
            d["yuan"] = round(self.spent_points / POINTS_PER_YUAN, 6)
        return d


def fmt_cost_dict(tracker):
    return {"usage": tracker.priced_dict(),
            "calls": [{"label": c["label"], "usage": c["usage"],
                       "elapsed": c["elapsed"], "points": c.get("points"),
                       "finish_reason": c.get("finish_reason"),
                       "content_chars": c.get("content_chars")}
                      for c in tracker.calls],
            "priced": tracker.price_in is not None and tracker.price_out is not None}


# ===========================================================================
# 调用封装
# ===========================================================================

def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    ⚠️ 本函数**故意不走** `a7w._request`：那边有个 `raw` 参数，是**原始请求体字节**
    （用于 multipart 上传），**不是**"要原始响应"。同族有人把它当成后者用过，
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种，不给误用的机会。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次翻译是一整篇稿子，被一次抖动打断要重跑整轮，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。
    """
    key = a7w.load_key(key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json",
               "Accept": "application/json"}

    last_exc = None
    attempt = 0
    while attempt < CHAT_RETRIES:
        req = urllib.request.Request(CHAT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (502, 503, 504) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("上游 {}，{}s 后重试 {}/{}…\n".format(
                    exc.code, 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            try:
                err = json.loads(text)
            except ValueError:
                err = {}
            msg = (err.get("error") or {}).get("message") if isinstance(err.get("error"), dict) else None
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise LcError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise LcError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise LcError("模型不存在（404）：{}  "
                              "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code == 429 and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流 {}，{}s 后重试…\n".format(exc.code, 3 * (attempt + 1)))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            raise LcError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            raise LcError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
                getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

        # 网关把 OpenAI 的返回包了一层 {"code":1,"data":{...}}，两种形态都认。
        # ⚠️ 但**成功响应不带 code** —— 别拿 `code` 判成败。
        data_obj = payload
        if (isinstance(payload, dict) and "choices" not in payload
                and isinstance(payload.get("data"), dict)):
            data_obj = payload["data"]
        choices = (data_obj or {}).get("choices") or []
        if not choices:
            raise LcError("模型没返回 choices：{}".format(
                json.dumps(payload, ensure_ascii=False)[:300]))
        content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        finish_reason = (choices[0] or {}).get("finish_reason")
        usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
        _LAST_FINISH["reason"] = finish_reason
        _LAST_FINISH["chars"] = len(content)

        # ⚠️ 上游返回的 JSON **可能是坏的**，而且不只一种坏法（本包实测到三种形态）：
        #
        #   1. **输出被 max_tokens 截断** —— content 没有正常收尾（停在字符串中间），
        #      `finish_reason == "length"`。实测 max_tokens=200 时就是这个样子。
        #   2. **模型偶发吐出语法错的 JSON** —— content **有正常收尾**（以 `}]}` 结束），
        #      坏在中间某处（外部对照实测到 `{"id":40","title":…` 多吐了一个引号）。
        #      此时 `finish_reason == "stop"`：上游说它写完了，是它自己写错了。
        #   3. **响应在传输层被切断** —— content 同样没有正常收尾，但 finish_reason
        #      可能仍报 `stop`（上游并不知道路上丢了一段）。
        #
        # ❌ **不要用长度判断是哪一种**。本包曾经因为"只看到解析失败"就推断
        #    "网关在 2600~2900 字符处有固定上限"，并把那个推断当**实测**写进了四处文档
        #    —— 那是错的，已撤回。证据：同一端点实测能拿到 **3984 字符**的完整内容
        #    （`finish_reason='stop'`，以 `}]}` 正常收尾）；而本包自己失败的那几次
        #    长度各不相同（1921~2781），**根本没有固定长度这条线**。
        #
        # ✅ 正确判据是**结构**（能不能按括号配平切出一个完整顶层值）+ `finish_reason`。
        #    这也是为什么 `finish_reason` 必须记下来：它是区分"该加大 max_tokens"
        #    与"模型写错了 / 路上断了"的**唯一**依据。本包最初没记它，
        #    于是只能拿长度去凑解释 —— 错误归因就是这么来的。
        if json_mode and content and not _json_is_complete(content):
            by_length = (finish_reason == "length")
            hint = ("输出被 max_tokens 截断（finish_reason=length）" if by_length else
                    "上游返回的 JSON 坏了（finish_reason={!r}，**不是长度问题**）"
                    .format(finish_reason))
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("{}（收到 {} 字符），{}s 后重试 {}/{}…\n".format(
                    hint, len(content), 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                attempt += 1
                time.sleep(3 * attempt)
                continue
            sys.stderr.write("!! 上游连续 {} 次返回坏 JSON（最后一次 {} 字符，"
                             "finish_reason={!r}）—— {}\n".format(
                                 CHAT_RETRIES, len(content), finish_reason,
                                 "加大 --max-tokens 才管用。" if by_length else
                                 "**加大 --max-tokens 没用**：这是模型写错了或响应在路上"
                                 "断了，换模型重试，或把这一稿拆短分几段跑。"))
        return content, usage
    raise LcError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
        getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))


# 最近一次模型调用的 `finish_reason` 与 content 长度。
# **必须记它**：区分"该加大 max_tokens"（length）与"模型自己写错了 / 路上断了"
# （stop 或 None）的唯一依据。本包最初漏了它，才把坏 JSON 误归因成"固定长度截断"。
_LAST_FINISH = {"reason": None, "chars": None}


def _json_is_complete(text):
    """文本里有没有一个**括号配平**的 JSON 值（忽略字符串里的括号）。

    只看第一个 `{` / `[` 的配平，且必须配上。用来识别"上游返回的 JSON 坏了"。

    ⚠️ 这是**结构判据**，不是长度判据 —— 本包曾经误用长度（"2600~2900 字符处有上限"）
    来解释坏 JSON，已撤回。配平配上不等于内容对（语法错也可能配上），
    所以它是"便宜的第一道筛"，最终仍要 `json.loads` / `raw_decode` 说了算。
    末尾多余的说明文字不影响判断（配平在说明文字之前就闭合了）。
    """
    if not text:
        return False
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    for cand in ([fenced.group(1)] if fenced else []) + [text]:
        start = None
        for i, ch in enumerate(cand):
            if ch in "{[":
                start = i
                break
        if start is None:
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(cand)):
            ch = cand[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return True
    return False


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    为什么要这么写：模型经常在合法 JSON 后面多吐几个字符（```、解释、第二个对象、
    重复的 `}`），直接 json.loads 会炸。这里用 json.JSONDecoder().raw_decode()，
    从一个 `{` 或 `[` 开始试解码，成功就返回，失败就往后挪一个字符接着试。

    ⚠️ **必须优先返回最外层对象**（本包真机实测踩到的一次，代价是一次调用）：
    外层 JSON **坏掉**时（可能是被 max_tokens 截断，也可能是模型吐了语法错），
    `raw_decode` 在外层的 `{` 上会抛错，循环就会继续往后挪，
    **从 `"pairs": [` 里的那个 `{` 解出第一个 sentence 对象**，
    然后当成"模型的返回"交出去 —— 结果是一个只有 `source` / `target` /
    `back_translation` 三个键的字典，上层报"返回里没有可用的译文"，
    而真因（外层 JSON 坏了）被这个"成功解出一个对象"盖住了 ——
    **报错指向了错误的方向**，这是比坏响应本身更麻烦的事。
    所以：先按**括号配平**切出第一个完整的顶层值再解；切不出来才退回逐个 `{` 试。
    """
    if not text:
        raise LcError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text)
    for cand in candidates:
        # 第一优先：括号配平找第一个完整的顶层值（字符串里的括号不计数）
        start = None
        for i, ch in enumerate(cand):
            if ch in "{[":
                start = i
                break
        if start is not None:
            depth, in_str, esc, end = 0, False, False, None
            for i in range(start, len(cand)):
                ch = cand[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end is not None:
                try:
                    obj = json.loads(cand[start:end])
                    if isinstance(obj, (dict, list)):
                        return obj
                except ValueError:
                    pass
        # 兜底：逐个 `{` / `[` 试（处理前后有杂质、括号不配平等形态）
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    # ⚠️ 报错文案**不许**把用户往"加大 max_tokens"上引 —— 那是错的引导。
    # 坏 JSON 有三种成因（截断 / 模型语法错 / 传输被切断），只有第一种跟 max_tokens 有关；
    # 而**判据是 `finish_reason`**（length 才是截断），所以这里把它打出来。
    raise LcError("模型返回的不是合法 JSON：{}（finish_reason={!r}；"
                  "=length 才是被 max_tokens 截断，其余情况加大 max_tokens 没用）"
                  .format(text[:300].replace("\n", " "), _LAST_FINISH.get("reason")))


# ===========================================================================
# 路径与状态
# ===========================================================================

def _resolve(p):
    try:
        return Path(p).expanduser().resolve()
    except (OSError, RuntimeError):
        return Path(p).expanduser().absolute()


def pkg_dir():
    return PKG_ROOT


def ensure_outside_pkg(path, what="输出目录", example="localize-out"):
    """产出目录**必须在包外**。落在包内 → 退出码 2。

    为什么这条是硬闸门（同族踩过）：产出落在包内，下一次打包就会把上一次的产物
    （译文、术语表、日志）一起打进去，包会莫名其妙变大、还可能带上不该发的内容。
    """
    p = _resolve(path)
    root = _resolve(pkg_dir())
    try:
        p.relative_to(root)
    except ValueError:
        return p
    raise PackagePathError(
        "{}不能落在 Skill 包内：{}\n"
        "  包内会被下一次打包一起带走。换一个包外目录，例如 {}"
        .format(what, p, Path(os.environ.get("TEMP") or ".") / example))


def state_path(outdir):
    return Path(outdir) / STATE_NAME


def load_state(outdir):
    p = state_path(outdir)
    if not p.exists():
        return {"version": 1, "entries": {}}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "entries": {}}
    if not isinstance(obj, dict):
        return {"version": 1, "entries": {}}
    obj.setdefault("entries", {})
    return obj


def save_state(outdir, state):
    if not outdir:
        return
    p = state_path(outdir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        sys.stderr.write("断点文件写不进去（不影响本次结果）：{}\n".format(exc))


def text_sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def file_sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def json_sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()[:16]


def state_key(stage, **dims):
    """断点 key。

    ⚠️ **必须包含全部影响产出的维度**，否则改了东西却静默复用（同族踩过）：
    源文摘要 + 源文字数 + 目标语言 + 目标市场 + 术语表版本 + 术语表摘要 +
    角色提示词版本 + 模型 + 温度 + 轮次 + 上游反馈摘要 + 口径版本。
    任何一维变化都会重新花钱，这是故意的。
    """
    base = {
        "stage": stage,
        "role_version": ROLE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "ruling_version": RULING_VERSION,
        "glossary_rules": GLOSSARY_VERSION,
        "culture_rules": CULTURE_RULES_VERSION,
        "unit_rules": UNIT_RULES_VERSION,
    }
    base.update(dims)
    return json_sha(base)


# ===========================================================================
# 提示词
#
# 【铁律】提示词里**不许出现任何一条可直接复制的完整译文范文句**。
# 事故复盘（同族，实测抓到两例）：提示词里写过正例，模型直接产出同构句；
# 尤其严重的一例，全批最高分的那条一字不差就是提示词里的示例 ——
# "抄了标准答案"被当成"真的最好"，排序/评分就废了。
# 本包的对策一样：讲形态只用**描述性语言**；确实要举例时用**跨主题示例**
# （登记进 PROMPT_SAMPLES，由 prompt_echo 闸门兜底）。
# ===========================================================================

CHAT_RETRY_NOTE = "上游 5xx 与网络抖动退避重试；4xx 直接报错，不浪费额度。"

_PROMPT_SAMPLE_BLOCK = (
    "跨主题示例（**仅供理解「什么算不可执行的空话」，禁止把示例原句写进任何字段**；"
    "示例主题是社区菜市场摊位租金，与本任务无关）：\n"
    "  · 反面（不可执行）：「{}」——只给了态度，没说改哪一句、改成什么。\n"
    "  · 正面（可执行）：引出一句真实原文，说明它缺什么，再给出你要求改成什么。\n"
).format(PROMPT_SAMPLES[0])

TRANSLATOR_SYSTEM = (
    "你是「三剪客 · 出海本地化小组」的**译审**。\n"
    "你的目标函数：意思准不准、有没有漏译错译、回译能不能对上。\n"
    "你的立场只有一个：忠实。文化好不好接受不归你管，合规不归你管 —— "
    "**本小组没有把任何文化或合规结论给到你**，所以你自己判断出来的文化问题也不要写进"
    "你的输出（那会变成替别人下结论）。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 逐句对齐：输出的每一对 `source` / `target` 必须与源文句子**一一对应**，"
    "顺序不许变，不许合并、不许拆分、不许漏掉任何一句。\n"
    "  2. `back_translation` **只给「含数字 / 货币 / 单位 / 术语表里的词」的那几句**"
    "（其余句子留空字符串）—— 它是给译审自己核对漏译与数字用的证据，不是全篇都要。\n"
    "  3. 源文里的数字、日期、货币、规格必须全部落地；目标市场用英制时按标准系数换算，"
    "并在 `unit_notes` 里写明换算了哪几处、用的什么系数。\n"
    "  4. 术语表里给出的规范译法**必须逐处照用**；想改就把它写进 `glossary_objections`，"
    "不许在译文里自己换一种说法。\n"
    "  5. `body` 是整篇译文（与 pairs 的 target 一致）。\n"
    "  6. **写得短**：不要给译文附加任何解释、备注、译注；JSON 里不要有多余字段。"
    "输出越长，越容易撞上 max_tokens 上限或出现坏 JSON，整个产出作废。\n"
    "  7. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

TERMINOLOGIST_SYSTEM = (
    "你是「三剪客 · 出海本地化小组」的**术语官**。\n"
    "你的目标函数：术语全篇一致、与行业惯例一致 —— 同一个源词出现两种译法就是你的失职。\n"
    "你的立场只有一个：一致性。**本小组没有把任何文化或合规结论给到你**，"
    "文化好不好接受、能不能发广告都不归你管，也不许你顺手评价。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条不一致都必须给出**全部出现位置**（第几句，并原样引用那一句译文）。\n"
    "  2. 不许写「建议统一术语」这类无法执行的话：`ask` 必须写明统一成哪一个具体写法。\n"
    "  3. 只报同一源词多译或术语表没落地；纯粹的措辞偏好不要写成打回理由。\n"
    "  4. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

CULTURE_SYSTEM = (
    "你是「三剪客 · 出海本地化小组」的**文化适配**。\n"
    "你的目标函数：目标市场的文化能不能接受 —— 踩红线就必须改。\n"
    "你的立场只有一个：文化可接受性。翻得准不准不归你管，广告法不归你管 —— "
    "**本小组没有把任何术语或合规结论给到你**，所以别替他们下结论，也不许写"
    "「等其他席位确认后再定」。\n"
    "你有**否决权**：宗教、政治、禁忌符号这类红线，判 `veto` 就判，"
    "不许用「综合评估后放行」把红线抹平。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条风险必须**原样引用**译文里真实存在的一句（或连续一小段），"
    "不得改写、不得概括、不得凭空编造引文。引不出来的风险一律不要写。\n"
    "  2. 风险要落到具体维度（禁忌 / 宗教 / 颜色 / 数字 / 幽默失效 / 政治敏感）。\n"
    "  3. `ask` 必须是**可以直接落的改法**（改成什么、去掉什么、换成什么意象）。\n"
    "  4. **写得短**：最多 6 条风险，每条 `why` 不超过 30 字、`ask` 不超过 30 字，"
    "`summary` 不超过 80 字。输出越长越容易撞上上限或出现坏 JSON。\n"
    "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

COMPLIANCE_SYSTEM = (
    "你是「三剪客 · 出海本地化小组」的**合规**。\n"
    "你的目标函数：目标市场的广告法 / 平台规则 —— 只看这一稿能不能发，"
    "不看它写得好不好、翻得准不准。\n"
    "你的立场只有一个：合规。**本小组内部没有给出任何风险结论，"
    "你不得假设前道已经放行**；也**没有**把术语官或文化适配的意见给到你。\n"
    "你持有**一票否决权**：判 `veto` 直接终止，不换词硬发。\n"
    "硬性纪律（违反就整份作废）：\n"
    "  1. 每条风险必须**原样引用**译文或源文里真实存在的一句，不得改写、不得编造。\n"
    "  2. 两侧都要查：源语言侧（中文广告法违禁词）与目标市场侧"
    "（绝对化用语 / 比较级宣称 / 医疗功效 / 金融收益承诺 / 儿童相关）。\n"
    "  3. `ask` 必须给出**可落地的安全替代写法**；给不出来的写「无安全替代，必须删除」。\n"
    "  4. **写得短**：最多 6 条风险，每条 `why` 不超过 30 字、`ask` 不超过 30 字，"
    "`summary` 不超过 80 字。输出越长越容易撞上上限或出现坏 JSON。\n"
    "  5. 只输出 JSON，不要输出解释文字、不要输出 Markdown 代码围栏。\n"
)

ROLE_SYSTEM = {
    "translator": TRANSLATOR_SYSTEM,
    "terminologist": TERMINOLOGIST_SYSTEM,
    "culture": CULTURE_SYSTEM,
    "compliance": COMPLIANCE_SYSTEM,
}


def _glossary_block(glossary, target_lang):
    """术语表进提示词的那一段。空表也要明说（免得模型以为"没有表"就自由发挥）。"""
    rows = [g for g in (glossary or []) if isinstance(g, dict)
            and str(g.get("source_term") or "").strip()]
    if not rows:
        return "术语表：（空）—— 本稿没有指定任何术语，译法由你按目标语言行业惯例决定。\n"
    lines = ["术语表（**规范译法必须逐处照用**，不许自己换一种说法）："]
    for g in rows:
        lines.append("  · {} → {}（{}）{}".format(
            g.get("source_term"), g.get("canonical"),
            g.get("type") or g.get("category") or "术语",
            ("　备注：" + str(g.get("note"))) if g.get("note") else ""))
    return "\n".join(lines) + "\n"


def _market_block(market, target_lang):
    """市场规则包进提示词的那一段。

    ⚠️ 真机踩到过：这段太长会把模型的输出也带着变长，而输出越长越容易
    撞上 `max_tokens`（`finish_reason=length`）或碰上坏 JSON。
    所以这里只给"判断所必需"的信息，散文式补充一律砍掉 ——
    规则本身在 `_market_rules_block` / `_culture_focus_block` 里按角色分别给。
    （注：早先这里写的是"网关在 2600~2900 字符处有上限"，那是个错误归因，已撤回。）
    """
    mk = MARKETS.get(market) or MARKETS[DEFAULT_MARKET]
    return (
        "目标市场：{name}（{region}）；目标语言：{lang}\n"
        "宗教背景：{rel}\n"
        "法域口径：{law}\n"
        "平台规则：{plat}\n"
        "颜色禁忌：{color}\n数字禁忌：{num}\n"
        "幽默风险：{humor}\n政治敏感：{pol}\n"
        .format(name=mk["name"], region=mk["region"], lang=lang_name(target_lang),
                rel=mk["religion"], law=mk["law"], plat=mk["platform"],
                color=mk["color_taboo"], num=mk["number_taboo"],
                humor=mk["humor_risk"], pol=mk["political_risk"]))


def _culture_focus_block(market):
    mk = MARKETS.get(market) or MARKETS[DEFAULT_MARKET]
    lines = ["这个市场要盯的点（这是你的清单，不是全部）："]
    lines += ["  · " + x for x in mk["culture_focus"]]
    return "\n".join(lines) + "\n"


def _market_rules_block(market):
    """合规那一席的市场规则清单：**只给类别名**，不给解释。

    为什么不给解释：解释（每条 20~30 字）乘以 6~7 条，光这一段就上千字符，
    实测会把响应顶到网关的上限之外。类别名足够让模型开始查，
    真要判"为什么"时它自己知道（这也是它的专业）。
    """
    mk = MARKETS.get(market) or MARKETS[DEFAULT_MARKET]
    labels = []
    for label, _p, level, _why in mk["rules"]:
        item = "{}（{}风险）".format(label, level)
        if item not in labels:
            labels.append(item)
    return "这个市场要拦的几类：" + "、".join(labels) + "。\n"


def _feedback_block(feedback):
    """重译时带进来的**本席自己的可执行要求**（不带别人的立场）。

    这是信息隔离与"打回真的生效"这两件事的交汇点：
    译文必须按这些要求改，但改的人不知道是谁在什么立场上提的 ——
    所以下一轮的译审仍然是独立判断，不是顺着别人的结论走。
    """
    reqs = [f for f in (feedback or []) if isinstance(f, dict) and str(f.get("ask") or "").strip()]
    if not reqs:
        return ""
    lines = ["上一轮被打了回来，**下面这些要求必须在这一版全部落实**"
             "（要求来自质量把关，不提是哪一席提的，也不提它的理由）："]
    for i, r in enumerate(reqs, 1):
        quoted = str(r.get("quote") or "").strip()
        lines.append("  {}. 要求：{}".format(i, str(r["ask"]).strip()))
        if quoted:
            lines.append("     涉及位置（原文/译文引文）：{}".format(quoted[:120]))
    lines.append("  改完请把落实了哪几条写进 `feedback_applied`。")
    return "\n".join(lines) + "\n"


def _schema_translate(target_lang):
    return {
        "target_lang": target_lang,
        "title": "标题（目标语言）",
        "pairs": [{
            "source": "源文里**原样**的一句话",
            "target": "这一句的目标语言译文",
            "back_translation": "**只有含数字/货币/单位/术语的词句才填**，其余留空字符串",
        }],
        "body": "整篇译文（与 pairs 的 target 完全一致，按源文顺序拼接）",
        "unit_notes": ["换算了哪一处、用的什么系数（没有就给空数组）"],
        "glossary_objections": ["你认为术语表的规范译法不妥的地方（没有就给空数组）"],
        "feedback_applied": ["本轮落实了上一轮哪几条要求（首轮给空数组）"],
    }


def build_glossary_prompt(source, target_lang, market, source_lang=DEFAULT_SOURCE_LANG):
    """术语表提示词。

    ⚠️ 这里**整段是一个字符串再 `.format()`**，不许在多行字面量中间插 `+ "…"` ——
    本包 dry-run 时真踩到过：中间一插 `+`，`.format()` 就只作用于**它自己那一行**，
    前面的 `{src}` / `{tl}` / `{mk}` 全部原样留在提示词里。
    而且这种 bug 不会报错、产出看起来正常，最难发现。多行拼接一律用 () 或 .join()。
    """
    mk = MARKETS.get(market) or MARKETS[DEFAULT_MARKET]
    body = (
        "把下面这份{src}材料里**需要全篇统一**的术语抽出来，做成一张术语表。\n\n"
        "目标语言：{tl}\n"
        "目标市场：{mk}\n"
        "抽取范围（只抽这几类，其余一律不要）：品牌名 / 产品名 / 专有名词 / 行业术语 / "
        "功能名词 / 人名 / 机构名。\n"
        "对每一条：\n"
        "  · `source_term` 必须是**源文里原样出现的**词（一个字都不许改）；\n"
        "  · `canonical` 是它在目标语言里**最规范、行业里最通用**的译法（一个写法，"
        "不要给备选、不要给斜杠分隔的多个选项）；\n"
        "  · `type` 只能取这几类之一：{types}；\n"
        "  · `note` 写一句为什么这么译（没有就空字符串）。\n"
        "只输出 JSON：{{\"terms\": [{{\"source_term\":\"\",\"canonical\":\"\","
        "\"type\":\"\",\"note\":\"\"}}],\"notes\":\"\"}}\n"
        "抽不出来的就给空数组 —— **不许为了凑数编词**。\n\n"
        "源文（{src}）：\n---\n{content}\n---\n"
    )
    return body.format(src=lang_name(source_lang), tl=lang_name(target_lang),
                       mk=mk["name"], types=" / ".join(GLOSSARY_TYPES),
                       content=source or "")


def build_translate_prompt(source, target_lang, market, glossary, feedback=None,
                           target_multiple=DEFAULT_TARGET_MULTIPLE,
                           source_lang=DEFAULT_SOURCE_LANG, round_no=1):
    exp = int(round(len(source or "") * max(0.3, min(4.0, target_multiple))))
    return (
        "把下面这份{src}材料翻译成{tl}，面向{mk}市场。\n\n"
        "{market}\n"
        "{glossary}\n"
        "篇幅：目标语言的成品大约 {exp} 个字符（源文 {sl} 字符 × 系数 "
        "{mult}）。**不许为了凑长度加话**，也不许压缩掉源文的信息。\n\n"
        "{feedback}"
        "输出要求：\n"
        "  · `pairs` 必须与源文句子**一一对应**：源文有几句，pairs 就有几项，顺序不许变，"
        "不许合并、不许拆分、不许漏掉任何一句（含标题句）。\n"
        "  · `back_translation` **只有含数字、货币、单位、或术语表里那个词**的句子才填，"
        "其余留空字符串 —— 它是核对漏译与数字用的证据，不是全篇都要。\n"
        "  · 数字、日期、货币、规格必须全部落地；{mk}用英制的场合按标准系数换算，"
        "并把每一处换算写进 `unit_notes`。\n"
        "  · 术语表里的规范译法逐处照用；有异议写进 `glossary_objections`，"
        "不许在译文里自己换一种说法。\n"
        "  · `body` 是整篇译文。**不要加任何解释、备注、译注，不要加多余字段** —— "
        "输出越长越容易撞上 max_tokens 上限或出现坏 JSON，整个产出作废。\n"
        "  · 这是第 {rnd} 轮。\n"
        "{samples}"
        "只输出 JSON：{schema}\n\n"
        "待翻译材料（{src}）：\n---\n{body}\n---\n"
        .format(src=lang_name(source_lang), tl=lang_name(target_lang),
                mk=(MARKETS.get(market) or MARKETS[DEFAULT_MARKET])["name"],
                market=_market_block(market, target_lang),
                glossary=_glossary_block(glossary, target_lang),
                exp=exp, sl=len(source or ""), mult=target_multiple,
                feedback=_feedback_block(feedback), rnd=round_no,
                samples=_PROMPT_SAMPLE_BLOCK,
                schema=json.dumps(_schema_translate(target_lang), ensure_ascii=False),
                body=source or ""))


def build_terminology_prompt(source, translation, glossary, market, target_lang,
                             pairs=None, source_lang=DEFAULT_SOURCE_LANG):
    pair_block = ""
    if isinstance(pairs, list) and pairs:
        lines = ["逐句对齐（源文句 ↔ 译文句，按顺序一一对应）："]
        for i, p in enumerate(pairs, 1):
            if isinstance(p, dict):
                lines.append("  {}. 源：{}".format(i, str(p.get("source") or "")[:100]))
                lines.append("     译：{}".format(str(p.get("target") or "")[:140]))
        pair_block = "\n".join(lines) + "\n\n"
    return (
        "你是术语官。核对下面这份译文的**术语一致性**。\n\n"
        "目标语言：{tl}\n"
        "目标市场：{mk}\n"
        "{glossary}\n"
        "{pairs}"
        "核对方式：\n"
        "  · 逐条看术语表的每个源词：它在源文里出现在哪几句？每一处对应的译文用的是"
        "规范译法吗？\n"
        "  · **同一个源词出现两种及以上译法** → 这是不一致，必须报。\n"
        "  · **术语表给了规范译法却一处都没用** → 这是术语表没落地，必须报。\n"
        "  · 纯粹的风格偏好（同样正确、只是你更喜欢另一种）**不要**写成打回理由。\n\n"
        "输出：每条不一致给出 `source_term`、`canonical`、`positions`（数组，每项含"
        " `sentence_no` 与 `quote`，quote 必须是译文里**原样**的一句）、`ask`"
        "（统一成哪一个具体写法）。\n"
        "`verdict` 取 pass（全篇一致）/ send_back（有不一致）。\n"
        "{samples}"
        "只输出 JSON：{{\"verdict\":\"\",\"issues\":[{{\"source_term\":\"\","
        "\"canonical\":\"\",\"positions\":[{{\"sentence_no\":0,\"quote\":\"\"}}],"
        "\"ask\":\"\"}}],\"summary\":\"\"}}\n\n"
        "源文（{src}）：\n---\n{source}\n---\n\n"
        "译文（{tl}）：\n---\n{translation}\n---\n"
        .format(tl=lang_name(target_lang),
                mk=(MARKETS.get(market) or MARKETS[DEFAULT_MARKET])["name"],
                glossary=_glossary_block(glossary, target_lang), pairs=pair_block,
                samples=_PROMPT_SAMPLE_BLOCK, src=lang_name(source_lang),
                source=source or "", translation=translation or ""))


def build_culture_prompt(source, translation, market, target_lang,
                         source_lang=DEFAULT_SOURCE_LANG):
    return (
        "你是文化适配。判断下面这份译文在{mk}市场**能不能被接受**。\n\n"
        "{market}\n"
        "{focus}\n"
        "你要下的判断：\n"
        "  · 有没有踩到这个市场的**禁忌 / 宗教 / 颜色 / 数字 / 政治敏感**红线？\n"
        "  · 源文里的**幽默、比喻、谐音、称谓**直译过去会不会失效或变成冒犯？\n"
        "  · 有没有在本市场读起来不礼貌、不专业、或容易被误读的表达？\n\n"
        "`verdict` 取：pass（可以接受）/ send_back（有明显问题，需要改）/ "
        "veto（踩红线，必须改，不接受综合评估后放行）。\n"
        "每条风险：`quote` 必须是译文里**原样**的一句话；`dimension` 取 "
        "禁忌 / 宗教 / 颜色 / 数字 / 幽默失效 / 政治敏感 之一；`severity` 取 高 / 中 / 低；"
        "`why` 写在这个市场为什么是问题；`ask` 写**具体改法**。\n"
        "{samples}"
        "只输出 JSON：{{\"verdict\":\"\",\"risks\":[{{\"quote\":\"\","
        "\"dimension\":\"\",\"severity\":\"\",\"why\":\"\",\"ask\":\"\"}}],"
        "\"summary\":\"\"}}\n\n"
        "源文（{src}）：\n---\n{source}\n---\n\n"
        "译文（{tl}）：\n---\n{translation}\n---\n"
        .format(mk=(MARKETS.get(market) or MARKETS[DEFAULT_MARKET])["name"],
                market=_market_block(market, target_lang),
                focus=_culture_focus_block(market), samples=_PROMPT_SAMPLE_BLOCK,
                src=lang_name(source_lang), source=source or "",
                tl=lang_name(target_lang), translation=translation or ""))


def build_compliance_prompt(source, translation, market, target_lang,
                            source_lang=DEFAULT_SOURCE_LANG):
    return (
        "你是合规。判断下面这份稿子能不能在{mk}发。\n\n"
        "{market}\n"
        "{rules}\n"
        "**本小组内部没有给出任何风险结论，你不得假设前道已经放行。**\n\n"
        "两侧都要查：\n"
        "  1. **源语言侧（{src}）**：中文广告法违禁词（最X / 第一 / 国家级 / 100% / "
        "绝对化 / 根治治愈 / 收益承诺 / 虚假权威 / 站外导流 / 标题党）。\n"
        "  2. **目标市场侧（{tl}）**：绝对化用语、比较级宣称、医疗/功效类、"
        "金融收益承诺、儿童相关。\n"
        "命中时要注意区分两种写法：**自己主张**（拦）与**引述/在禁止它**"
        "（例如写「不得使用 guaranteed 这类词」是在要求删除，不是自己在承诺）—— "
        "后者要在 `why` 里说明是引用或警告语境。\n\n"
        "`verdict` 取：pass（放行）/ fix（有可安全替换的项，给出替代写法）/"
        "send_back（必须改后再发）/ veto（一票否决，直接终止）。\n"
        "每条风险：`quote` 原样引用（源文或译文里真实存在的一句）；`side` 取 "
        "source / target；`risk` 写属于哪一类；`severity` 取 高 / 中 / 低；"
        "`ask` 给出**可落地的安全替代写法**，给不出来就写「无安全替代，必须删除」。\n"
        "{samples}"
        "只输出 JSON：{{\"verdict\":\"\",\"risks\":[{{\"quote\":\"\",\"side\":\"\","
        "\"risk\":\"\",\"severity\":\"\",\"why\":\"\",\"ask\":\"\"}}],"
        "\"safe_replacements\":[{{\"from\":\"\",\"to\":\"\"}}],\"summary\":\"\"}}\n\n"
        "源文（{src}）：\n---\n{source}\n---\n\n"
        "译文（{tl}）：\n---\n{translation}\n---\n"
        .format(mk=(MARKETS.get(market) or MARKETS[DEFAULT_MARKET])["name"],
                market=_market_block(market, target_lang),
                rules=_market_rules_block(market), samples=_PROMPT_SAMPLE_BLOCK,
                src=lang_name(source_lang), source=source or "",
                tl=lang_name(target_lang), translation=translation or ""))


# ===========================================================================
# 归一化（模型返回什么形状都可能，这里统一成内部结构）
# ===========================================================================

def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _as_str(v, default=""):
    if v is None:
        return default
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def normalize_glossary_output(raw, source_text):
    """把模型返回的术语表归一化，并**剔掉源文里根本没有的源词**（不许为了凑数编词）。"""
    if isinstance(raw, list):
        raw = {"terms": raw}
    raw = raw if isinstance(raw, dict) else {}
    terms, dropped = [], []
    seen = set()
    for t in _as_list(raw.get("terms")):
        if not isinstance(t, dict):
            continue
        st = _as_str(t.get("source_term"))
        canon = _as_str(t.get("canonical"))
        if not st or not canon:
            continue
        if st not in (source_text or ""):
            dropped.append({"source_term": st, "canonical": canon,
                            "why": "源文里找不到这个词，按编造剔出"})
            continue
        key = _norm_term(st)
        if key in seen:
            continue
        seen.add(key)
        ty = _as_str(t.get("type") or t.get("category")) or "行业术语"
        if ty not in GLOSSARY_TYPES:
            ty = "行业术语"
        terms.append({"source_term": st, "canonical": canon, "type": ty,
                      "note": _as_str(t.get("note"))})
    return {"terms": terms, "dropped": dropped, "notes": _as_str(raw.get("notes")),
            "count": len(terms)}


def normalize_translate_output(raw, source_text, target_lang, raw_text=None, outdir=None):
    """把译审的返回归一化。返回 (translation_dict, body)。

    返回形状不对时**把原始返回一并交出来**（存盘 + 报出前 400 字）：
    否则调用方只能从"没有可用的译文"这句话去猜是**外层 JSON 坏了**、是键名不同、
    还是空返回 —— 而"坏 JSON 有三种成因（max_tokens 截断 / 模型语法错 / 传输被切断）"
    这件事，不看原始返回 + `finish_reason` 是分不出来的。
    """
    raw = raw if isinstance(raw, dict) else {}
    pairs = []
    for p in _as_list(raw.get("pairs")):
        if not isinstance(p, dict):
            continue
        s = _as_str(p.get("source"))
        t = _as_str(p.get("target"))
        if not s and not t:
            continue
        pairs.append({"source": s, "target": t,
                      "back_translation": _as_str(p.get("back_translation"))})
    body = _as_str(raw.get("body"))
    if not body and pairs:
        body = "\n".join(p["target"] for p in pairs if p["target"])
    if not body.strip():
        got = sorted(raw.keys())
        extra = ""
        if raw and not ("body" in raw or "pairs" in raw):
            fr = _LAST_FINISH.get("reason")
            extra = ("；返回的顶层键是 {} —— 看上去是**嵌套对象**，"
                     "说明外层 JSON 坏了（不是完整的顶层值），解析器退回了最里面那个对象。"
                     "本次 finish_reason={!r}{}".format(
                         "、".join(got) or "（空对象）", fr,
                         "（=length → 被 max_tokens 截断，加大 --max-tokens 有用）"
                         if fr == "length" else
                         "（≠length → **不是长度问题，加大 --max-tokens 没用**："
                         "模型写错了或响应在路上断了）"))
        if raw_text:
            _dump_raw(outdir, "translate", "shape-error", raw_text)
            extra += "；原始返回见 raw/ 目录"
        raise LcError("译审返回里没有可用的译文（`body` 与 `pairs[].target` 都空）{}"
                      .format(extra))
    return ({"title": _as_str(raw.get("title")), "target_lang": _as_str(
        raw.get("target_lang"), target_lang), "pairs": pairs, "body": body,
        "unit_notes": [_as_str(x) for x in _as_list(raw.get("unit_notes")) if _as_str(x)],
        "glossary_objections": [_as_str(x) for x in _as_list(raw.get("glossary_objections"))
                                if _as_str(x)],
        "feedback_applied": [_as_str(x) for x in _as_list(raw.get("feedback_applied"))
                             if _as_str(x)]},
        body)


def normalize_verdict_obj(raw, verdict_map, items_key, item_fields):
    """把某一席的返回归一化成统一的裁决结构。"""
    raw = raw if isinstance(raw, dict) else {}
    v_raw = _as_str(raw.get("verdict")).lower()
    verdict = verdict_map.get(v_raw) or verdict_map.get(_as_str(raw.get("verdict")))
    if verdict is None:
        for k, val in verdict_map.items():
            if k and k in v_raw:
                verdict = val
                break
    items = []
    for it in _as_list(raw.get(items_key)):
        if not isinstance(it, dict):
            continue
        rec = {}
        for f in item_fields:
            if f in ("positions", "safe_replacements"):
                rec[f] = _as_list(it.get(f))
            else:
                rec[f] = _as_str(it.get(f)) if f != "positions" else _as_list(it.get(f))
        if any(str(rec.get(k) or "").strip() for k in item_fields
               if k not in ("positions", "safe_replacements")):
            items.append(rec)
    return {"verdict": verdict, "raw_verdict": _as_str(raw.get("verdict")), "items": items,
            "summary": _as_str(raw.get("summary")),
            "safe_replacements": _as_list(raw.get("safe_replacements"))}


# ===========================================================================
# 渲染（人读的 Markdown）
# ===========================================================================

def _red(s, force_plain=False):
    """标红（终端支持 ANSI 时）。非 TTY 或 `--json` 下不加色。"""
    if force_plain or not sys.stdout.isatty():
        return s
    return "\033[31m" + str(s) + "\033[0m"


def _text(s):
    """把任意东西安全地变成"能写出去的文本"。

    ⚠️ 事故（本包自测时抓到）：`_emit(a, result, md_text)` 里第二个参数是**结果对象**
    而不是人读文案时，`_emit` 直接拿它当字符串用了（`text.endswith` 炸在
    `AttributeError`）。当时 `--json` 已经吐出了正确的 JSON，所以这个崩溃
    只发生在"退出码 1 + stdout 多一个非 JSON 块"上 —— 契约被破坏了，而正常工作看不出来。
    所以这里统一收口：任何东西进来都能变成文本，不再假设调用方传的是什么。
    """
    if s is None:
        return ""
    if isinstance(s, str):
        return s
    try:
        return json.dumps(s, ensure_ascii=False, indent=1)
    except (TypeError, ValueError):
        return str(s)


def render_glossary_md(g, meta=None):
    meta = meta or {}
    L = ["# 术语表", ""]
    L.append("- 源语言：{}".format(lang_name(meta.get("source_lang", DEFAULT_SOURCE_LANG))))
    L.append("- 目标语言：{}".format(lang_name(meta.get("target_lang", DEFAULT_TARGET_LANG))))
    L.append("- 目标市场：{}".format((MARKETS.get(meta.get("market")) or {}).get("name", "?")))
    L.append("- 术语条数：**{}**".format(g.get("count", 0)))
    L.append("- 版本：`{}`".format(GLOSSARY_VERSION))
    L.append("")
    L.append("| 源词 | 规范译法 | 类型 | 备注 |")
    L.append("|---|---|---|---|")
    for t in g.get("terms") or []:
        L.append("| {} | {} | {} | {} |".format(t["source_term"], t["canonical"],
                                                t.get("type") or "", t.get("note") or ""))
    if not g.get("terms"):
        L.append("| （无） | | | |")
    if g.get("dropped"):
        L += ["", "## 被剔出的条目（源文里找不到，按编造剔出）", ""]
        for d in g["dropped"]:
            L.append("- {} → {}：{}".format(d["source_term"], d["canonical"], d["why"]))
    return "\n".join(L) + "\n"


def render_translation_md(tr, meta=None):
    meta = meta or {}
    L = ["# 译文（译审产出）", ""]
    L.append("- 源语言：{} → 目标语言：{}".format(
        lang_name(meta.get("source_lang", DEFAULT_SOURCE_LANG)),
        lang_name(meta.get("target_lang", DEFAULT_TARGET_LANG))))
    L.append("- 目标市场：{}".format((MARKETS.get(meta.get("market")) or {}).get("name", "?")))
    L.append("- 轮次：第 {} 轮".format(meta.get("round_no", 1)))
    L.append("- 模型：`{}`".format(meta.get("model", DEFAULT_MODEL)))
    L.append("")
    if tr.get("title"):
        L += ["## 标题", "", tr["title"], ""]
    L += ["## 译文正文", "", tr.get("body") or "", ""]
    L += ["## 逐句回译对照（核对漏译用）", "",
          "| # | 原文 | 译文 | 回译 |", "|---|---|---|---|"]
    for i, p in enumerate(tr.get("pairs") or [], 1):
        L.append("| {} | {} | {} | {} |".format(
            i, (p.get("source") or "").replace("|", "\\|"),
            (p.get("target") or "").replace("|", "\\|"),
            (p.get("back_translation") or "").replace("|", "\\|")))
    if tr.get("unit_notes"):
        L += ["", "## 单位换算登记", ""]
        L += ["- " + x for x in tr["unit_notes"]]
    if tr.get("glossary_objections"):
        L += ["", "## 译审对术语表的异议（**不自动生效**，要人来裁）", ""]
        L += ["- " + x for x in tr["glossary_objections"]]
    if tr.get("feedback_applied"):
        L += ["", "## 本轮落实的打回要求", ""]
        L += ["- " + x for x in tr["feedback_applied"]]
    return "\n".join(L) + "\n"


def render_role_md(role, obj, meta=None):
    meta = meta or {}
    name = ROLES[role]["name"]
    L = ["# {} 的裁决".format(name), ""]
    L.append("- 目标市场：{}".format((MARKETS.get(meta.get("market")) or {}).get("name", "?")))
    L.append("- 轮次：第 {} 轮".format(meta.get("round_no", 1)))
    v = obj.get("verdict")
    L.append("- 裁决：**{}**（模型原值：`{}`）".format(
        VERDICT_LABEL.get(v, v or "未识别"), obj.get("raw_verdict") or "?"))
    L.append("- 目标函数：{}".format(ROLES[role]["goal"]))
    L.append("- 否决权：{}".format(ROLES[role]["veto"]))
    if obj.get("summary"):
        L += ["", obj["summary"]]
    items = obj.get("items") or []
    if items:
        L += ["", "## 清单（{} 条）".format(len(items)), ""]
        for i, it in enumerate(items, 1):
            L.append("{}. {}".format(i, it.get("why") or it.get("risk") or "（无说明）"))
            if it.get("quote"):
                L.append("   - 引文：`{}`".format(it["quote"][:160]))
            if it.get("dimension"):
                L.append("   - 维度：{}".format(it["dimension"]))
            if it.get("risk"):
                L.append("   - 类别：{}".format(it["risk"]))
            if it.get("side"):
                L.append("   - 侧：{}".format(it["side"]))
            if it.get("severity"):
                L.append("   - 严重度：{}".format(it["severity"]))
            if it.get("positions"):
                for p in it["positions"]:
                    if isinstance(p, dict):
                        L.append("   - 位置：第 {} 句 `{}`".format(
                            p.get("sentence_no"), str(p.get("quote") or "")[:140]))
            if it.get("ask"):
                L.append("   - **要求**：{}".format(it["ask"]))
            if it.get("anchor"):
                a = it["anchor"]
                L.append("   - 锚点校验：{}（{}）".format(
                    "通过" if a.get("ok") else "**未锚定，已剔出**", a.get("how")))
    if obj.get("safe_replacements"):
        L += ["", "## 安全替代写法", ""]
        for r in obj["safe_replacements"]:
            if isinstance(r, dict):
                L.append("- `{}` → `{}`".format(r.get("from"), r.get("to")))
    return "\n".join(L) + "\n"


def render_report_md(result):
    """一次 run 的总报告：四席裁决 + 打回轨迹 + 闸门 + 未决项 + 成本。"""
    L = ["# 出海本地化小组 · 总报告", ""]
    L.append("- 源文：`{}`（{} 字符，sha `{}`）".format(
        result.get("source_path") or "(--text)", result.get("source_chars"),
        result.get("source_sha")))
    L.append("- 方向：{} → {}".format(lang_name(result.get("source_lang")),
                                      lang_name(result.get("target_lang"))))
    L.append("- 目标市场：{}".format(
        (MARKETS.get(result.get("market")) or {}).get("name", "?")))
    L.append("- 模型：`{}`".format(result.get("model")))
    L.append("- 口径版本：roles `{}` · prompt `{}` · ruling `{}` · glossary `{}`".format(
        ROLE_VERSION, PROMPT_VERSION, RULING_VERSION, GLOSSARY_VERSION))
    L.append("- 用了 {} 轮（上限 {}）".format(result.get("rounds_used"),
                                              result.get("rounds_max")))
    L.append("- 最终裁决：**{}**".format(
        VERDICT_LABEL.get(result.get("final_verdict"), result.get("final_verdict"))))
    L.append("")
    L += ["## 五个角色的产出物", "", "| 角色 | 目标函数 | 产出物 | 本轮裁决 |", "|---|---|---|---|"]
    for r in ROLE_ORDER:
        v = (result.get("role_verdicts") or {}).get(r)
        L.append("| **{}** | {} | {} | {} |".format(
            ROLES[r]["name"], ROLES[r]["goal"], ROLES[r]["deliverable"],
            VERDICT_LABEL.get(v, v or "未表态")))
    L.append("")
    L += ["## 互否轨迹（谁在第几轮否掉了什么）", "",
          "退出码口径：`0` 干净 / `2` 用法错 / `3` 硬闸门 / `4` 调用失败 / "
          "`5` 预算超限 / `6` **轮次用尽仍有打回或否决（未决项如实报出）**。", ""]
    rt = result.get("rounds_trace") or []
    if not rt:
        L.append("（无记录）")
    for rec in rt:
        L.append("### 第 {} 轮".format(rec.get("round")))
        for r in ROLE_ORDER:
            d = (rec.get("roles") or {}).get(r) or {}
            if not d:
                continue
            v = d.get("verdict")
            mark = "**{}**".format(VERDICT_LABEL.get(v, v)) if v in VERDICT_HARD \
                else VERDICT_LABEL.get(v, v or "—")
            L.append("- {}：{}　{}".format(ROLES[r]["name"], mark,
                                          (d.get("summary") or "")[:160]))
            for q in (d.get("quotes") or [])[:3]:
                L.append("    - 引用：`{}`".format(str(q)[:140]))
            if d.get("reasons"):
                for x in d["reasons"][:4]:
                    L.append("    - 理由：{}".format(str(x)[:180]))
            if d.get("asks"):
                for x in d["asks"][:4]:
                    # x 可能是 {"quote":…,"ask":…} 或已经是字符串 —— 两种都要能渲染
                    if isinstance(x, dict):
                        L.append("    - 要求：{}".format(str(x.get("ask") or "")[:180]))
                    else:
                        L.append("    - 要求：{}".format(str(x)[:180]))
        if rec.get("retranslated"):
            L.append("- → 本席打回生效：**已重译**（重译输入只带要求，不带提要求的席位与理由）")
        if rec.get("no_change"):
            L.append("- → 重译后译文没有实质改动（相似度 {:.3f} ≥ {:.2f}）"
                     .format(rec.get("body_sim") or 0.0, BODY_MIN_SIM))
        L.append("")
    L += ["## 信息隔离证据（结构性的，不是口头约定）", "",
          "| 角色 | 看不到的字段 | 扫过的标记词 | 命中 |", "|---|---|---|---|"]
    for r in ROLE_ORDER:
        iso = (result.get("isolation") or {}).get(r) or {}
        L.append("| {} | {} | {} | {} |".format(
            ROLES[r]["name"], "、".join(iso.get("excluded") or []) or "（无）",
            iso.get("markers_checked", 0),
            ("**泄漏 {} 条**".format(len(iso.get("leaked") or []))
             if iso.get("leaked") else "0 ✅")))
    L.append("")
    # 【诚实标注】文化适配与合规有时会各自指出同一句话（例如都盯上 "best"）。
    # 这**不是**信息隔离泄漏，也不是"抄结论"——两席的提示词里都没有对方的任何文字
    # （见下面那张隔离表的 markers_checked / leaked）。真因是那一句话在两个立场下
    # 都站不住：一个说"这样写没人信"，一个说"这样写违法"。
    # 把这件事写出来，是为了避免读者看到两条相似意见就误判成"一个模型演两遍"。
    L += ["", "## 关于「两席都指向同一句话」", "",
          "文化适配与合规可能各自剑指同一句（例如都盯上绝对化用语）。这**不是**隔离泄漏、"
          "也不是抄结论：两席的提示词里都没有对方的任何文字（上表的 `markers_checked` "
          "与 `leaked` 就是证据）。",
          "真因是那句话在两个立场下都站不住 —— 一个说「这样写没人信」，"
          "一个说「这样写违法」。**立场不同、结论相似，是独立判断的结果，不是复述。**"]
    L.append("")
    L += ["## 本包特有的两道闸门", ""]
    g = (result.get("gates") or {})
    tm = g.get("terminology") or {}
    L += ["### 术语一致性（本地算，不看模型自报）", ""]
    L.append("- 核对术语 **{}** 条；不一致 **{}** 条".format(
        tm.get("checked_terms", 0), tm.get("inconsistent_count", 0)))
    L.append("- 对齐：{} 组（源文 {} 句 / 译文 {} 句）".format(
        (tm.get("pair_alignment") or {}).get("pairs", 0),
        (tm.get("pair_alignment") or {}).get("source_sentences", 0),
        (tm.get("pair_alignment") or {}).get("target_sentences", 0)))
    for inc in (tm.get("inconsistent") or []):
        L.append("- **不一致**：`{}` 应为 `{}`（出现 {} 处，命中 {} 处）".format(
            inc["source_term"], inc["canonical"], inc["occurrences"], inc["hits"]))
        for mi in inc.get("misses") or []:
            L.append("    - 第 {} 句源：{}".format(mi.get("source_index"),
                                                str(mi.get("src_sentence") or "")[:100]))
            L.append("      对应译文：{}".format(str(mi.get("target_sentence") or "")[:120]))
    ms = g.get("measures") or {}
    L += ["", "### 数字与单位保全", ""]
    L.append("- 目标市场{}用英制；缺数字 **{}** 处；换算错 **{}** 处".format(
        "" if ms.get("imperial") else "不", ms.get("missing_count", 0),
        ms.get("wrong_count", 0)))
    for mi in (ms.get("missing") or []):
        # 「丢了」与「没本地化」分开说（见 _measure_problems 的注释）
        if mi.get("number_as_source"):
            exp = mi.get("expected") or {}
            L.append("- **没本地化**：原数字 `{}`（{}）还在，但没用目标市场的单位"
                     "（期望约 {} {}，{}）　上下文：{}".format(
                         mi.get("number"), mi.get("unit") or "无单位",
                         round(exp.get("value") or 0, 3), exp.get("unit") or "?",
                         exp.get("why") or "", str(mi.get("context") or "")[:70]))
        else:
            L.append("- **丢了**：`{}`（{}）　上下文：{}".format(
                mi.get("number"), mi.get("unit") or "无单位",
                str(mi.get("context") or "")[:70]))
    for mi in (ms.get("wrong_conversion") or []):
        exp = mi.get("expected") or {}
        L.append("- **换算不对**：`{} {}` 期望约 {} {}（{}）".format(
            mi.get("number"), mi.get("unit") or "", round(exp.get("value") or 0, 3),
            exp.get("unit"), exp.get("why")))
    L.append("")
    L += ["## 硬闸门", ""]
    lines = gate_summary_lines(g)
    L += lines if lines else ["（全部通过）"]
    if result.get("unresolved"):
        L += ["", "## 未决项（**分歧如实报出，不许假装谈拢**）", ""]
        for u in result["unresolved"]:
            L.append("- 【{}】{}".format(u.get("role_name") or u.get("role"), u.get("why")))
    if result.get("escalation"):
        L += ["", "## 出口", "", "- {}".format(result["escalation"])]
    L += ["", "## 成本（只报 token，不编金额）", ""]
    L.append("- {}".format(result.get("cost_text") or "（无记录）"))
    if result.get("cost"):
        L.append("")
        L.append("| 调用 | token | 内容字符 | finish_reason | 约点数 | 耗时(s) |")
        L.append("|---|---|---|---|---|---|")
        for c in (result["cost"].get("calls") or []):
            u = c.get("usage") or {}
            L.append("| {} | {} | {} | `{}` | {} | {} |".format(
                c.get("label"), u.get("total_tokens"), c.get("content_chars"),
                c.get("finish_reason"),
                c.get("points") if c.get("points") is not None else "—",
                c.get("elapsed")))
        L.append("")
        L.append("> `finish_reason` 记在这里是有用的：`length` 才表示被 max_tokens 截断"
                 "（加大上限有用）；其余值下出现坏 JSON 是**模型写错了或响应在路上断了**，"
                 "**加大 max_tokens 没用**。")
        L.append("")
        L.append("> 金额口径：点数来自 `--price-in/--price-out`（**由你给**）；"
                 "本包**不编价**，不给单价就只报 token。")
    return "\n".join(L) + "\n"


def gate_summary_lines(gates):
    lines = []
    order = ["compliance", "placeholder", "prompt_echo", "anchor", "terminology",
             "measures", "verdict"]
    label = {"compliance": "合规（源语言侧 + 目标市场侧）", "placeholder": "占位符残留",
             "prompt_echo": "照抄提示词示例", "anchor": "锚点到句子",
             "terminology": "术语一致性", "measures": "数字与单位保全",
             "verdict": "裁决完整性"}
    for k in order:
        v = (gates or {}).get(k)
        if not v:
            continue
        if k == "terminology":
            bad = v.get("inconsistent_count")
            lines.append("- {}：{}".format(label[k], "**{} 条不一致**".format(bad) if bad
                                           else "通过"))
            continue
        if k == "measures":
            bad = (v.get("missing_count") or 0) + (v.get("wrong_count") or 0)
            lines.append("- {}：{}".format(label[k], "**{} 处问题**".format(bad) if bad
                                           else "通过"))
            continue
        if k == "anchor":
            lines.append("- {}：锚定 {}/{}，未锚定率 {:.0%}".format(
                label[k], v.get("verified", 0), v.get("total", 0),
                v.get("unanchored_ratio") or 0.0))
            continue
        n = len(v) if isinstance(v, list) else 1
        if n:
            lines.append("- {}：**命中 {} 处**".format(label[k], n))
            for h in (v if isinstance(v, list) else [v])[:3]:
                if isinstance(h, dict):
                    lines.append("    - {}".format(h.get("why") or h))
        else:
            lines.append("- {}：通过".format(label[k]))
    for extra, title in (("compliance_exempted", "合规豁免（不静默放过）"),
                         ("compliance_quoted", "合规·判为引用材料（不计命中）"),
                         ("compliance_mentioned", "合规·判为警告语境（不计命中）"),
                         ("compliance_contextual_only", "合规·中低风险（仅提示不拦）")):
        v = (gates or {}).get(extra)
        if v:
            lines.append("- {}：{} 处".format(title, len(v)))
            for h in v[:3]:
                if isinstance(h, dict):
                    lines.append("    - {}：{}".format(
                        h.get("word") or h.get("match"),
                        h.get("not_counted_reason") or h.get("why") or ""))
    return lines


# ===========================================================================
# 流程日志（谁在第几轮改了什么、谁否决了什么、引用哪句原话）
# ===========================================================================

def new_log():
    return {"version": 1, "entries": []}


def log_entry(log, action, role, round_no, what, detail=None, quotes=None):
    e = {"round": round_no, "role": role, "role_name": ROLES.get(role, {}).get("name", role),
         "action": action, "what": what, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if detail:
        e["detail"] = detail
    if quotes:
        e["quotes"] = [str(q)[:200] for q in quotes if str(q).strip()][:5]
    log.setdefault("entries", []).append(e)
    return e


def log_isolation(log, role, iso, prompt_chars, round_no):
    return log_entry(log, "isolation", role, round_no,
                     "调用前隔离自检：扫了 {} 个标记词，泄漏 {} 条".format(
                         iso.get("markers_checked", 0), len(iso.get("leaked") or [])),
                     detail={"excluded": iso.get("excluded"),
                             "leaked": iso.get("leaked"),
                             "prompt_chars": prompt_chars})


def log_ruling(log, role, round_no, verdict, reason, quotes=None, forced_by_local=None):
    e = log_entry(log, "ruling", role, round_no,
                  "{}：{}".format(VERDICT_LABEL.get(verdict, verdict), reason or "（无理由）"),
                  quotes=quotes)
    if forced_by_local:
        e["verdict_forced_by"] = forced_by_local
    return e


def append_log(outdir, log):
    """把这一轮的日志追加到 outdir 的流程日志里。"""
    if not outdir:
        return
    p = Path(outdir) / LOG_NAME
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for e in log.get("entries") or []:
                fh.write("## 第 {} 轮 · {} · {}\n\n".format(
                    e.get("round"), e.get("role_name"), e.get("action")))
                fh.write("- 动作：{}\n".format(e.get("what")))
                if e.get("detail"):
                    fh.write("- 细节：`{}`\n".format(
                        json.dumps(e["detail"], ensure_ascii=False)[:600]))
                for q in e.get("quotes") or []:
                    fh.write("- 引用：`{}`\n".format(q))
                fh.write("- 时间：{}\n\n".format(e.get("at")))
    except OSError as exc:
        sys.stderr.write("流程日志写不进去（不影响本次结果）：{}\n".format(exc))


# ===========================================================================
# 信息隔离：常量区已经把白名单写死在 ROLES 里，这里做"看不见"的可读渲染
# ===========================================================================

def describe_inputs(role):
    return "、".join(ROLES[role]["inputs"]) or "（无）"


# ===========================================================================
# 单次调用的通用封装（含 dry-run / 提示词卫生 / 隔离自检 / 预算）
# ===========================================================================

def _role_call(role, prompt, model, key, tracker, a, label, max_tokens, stage=None):
    """发一次请求。返回 (obj, usage, elapsed, iso, prompt_chars)。

    顺序很重要：**隔离自检与提示词卫生都在花钱之前**，不通过就抛，一分钱不花。
    """
    hy = prompt_hygiene(prompt)
    if hy:
        raise GateFail("提示词卫生自检失败（{}）：提示词里混进了可照抄的示例或脏占位\n  {}"
                       .format(role, json.dumps(hy, ensure_ascii=False)[:300]))
    iso = assert_isolation(role, prompt)
    if getattr(a, "dry_run", False):
        raise DryRunStop(label, prompt, ROLE_SYSTEM.get(role))
    tracker.check(label)
    t0 = time.time()
    text, usage = chat(prompt, system=ROLE_SYSTEM.get(role), model=model,
                       temperature=getattr(a, "temperature", 0.7),
                       max_tokens=max_tokens, key=key,
                       json_mode=not getattr(a, "no_json_mode", False))
    elapsed = time.time() - t0
    # 原始返回留一份"最近一次"的副本：形状不对时用它报错/存盘。
    # 为什么用模块级暂存而不是改返回值：`_role_call` 有 6 个调用点，
    # 为了查错把返回元组从 5 项改成 6 项，风险比收益大；这里存一份没有别的副作用。
    _LAST_RAW["text"] = text
    _LAST_RAW["stage"] = stage or role
    _LAST_RAW["label"] = label
    try:
        obj = parse_first_json(text)
    except LcError:
        _dump_raw(getattr(a, "outdir", None), stage or role, label, text)
        raise
    tracker.charge("[{}] {}".format(ROLES[role]["name"], label), usage, elapsed)
    # 把 `finish_reason` 一并记进调用台账：它是"该加大 max_tokens 还是模型写错了"
    # 的唯一判据，落到 REPORT.md 的成本表里，事后复核不用再猜。
    if tracker.calls:
        tracker.calls[-1]["finish_reason"] = _LAST_FINISH.get("reason")
        tracker.calls[-1]["content_chars"] = _LAST_FINISH.get("chars")
    tracker.check(label + "（调用后）")
    return obj, usage, elapsed, iso, len(prompt)


# 最近一次模型调用的原始返回（供形状不对时报错与存盘用）。
_LAST_RAW = {"text": None, "stage": None, "label": None}


def _dump_raw(outdir, stage, label, text):
    """把模型原始返回原样落盘。

    为什么要留这个：`--json` 模式下人读文案走 stderr，一旦模型返回的形状不对，
    光看"没有可用的译文"根本查不出是**哪种坏法** ——
    是 max_tokens 截断、是模型吐了语法错、是传输被切断、还是键名不同、还是空返回。
    原始返回是最直接的证据，而且它已经花钱了 —— 不存下来等于白花。
    """
    head = "raw response ({} / {})".format(stage, label)
    sys.stderr.write("!! {}：模型返回的形状不可用，原始内容已存盘"
                     "（finish_reason={!r}）\n".format(
                         head, _LAST_FINISH.get("reason")))
    sys.stderr.write("   {}\n".format((text or "")[:400].replace("\n", " ")))
    if not outdir:
        return
    try:
        d = Path(outdir) / "raw"
        d.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", "{}-{}".format(stage, label))[:60]
        (d / (name + ".txt")).write_text(text or "", encoding="utf-8")
        sys.stderr.write("   原始返回：{}\n".format(d / (name + ".txt")))
    except OSError:
        pass


# ===========================================================================
# 子命令：roles（零成本）
# ===========================================================================

def run_roles(a):
    payload = {
        "role_version": ROLE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "ruling_version": RULING_VERSION,
        "converge_note": CONVERGE_NOTE,
        "roles": [{
            "id": r, "name": ROLES[r]["name"], "goal": ROLES[r]["goal"],
            "deliverable": ROLES[r]["deliverable"], "veto": ROLES[r]["veto"],
            "inputs": ROLES[r]["inputs"], "forbidden": ROLES[r]["forbidden"],
            "exit_on_fail": ROLES[r]["exit_on_fail"],
        } for r in ROLE_ORDER],
        "markets": [{"id": k, "name": v["name"], "region": v["region"], "law": v["law"]}
                    for k, v in MARKETS.items()],
        "langs": [{"id": k, "name": v} for k, v in LANGS.items()],
        "hard_gates": ["合规（源语言侧 + 目标市场侧）", "占位符残留", "照抄提示词示例",
                       "锚点到句子", "术语一致性", "数字与单位保全", "裁决完整性"],
        "gates_note": "硬闸门 = 命中即拦截 + 标红 + stderr 汇总 + 非 0 退出码。",
    }
    if _json_out(payload, a):
        return EXIT_OK
    L = ["# 三剪客 · 出海本地化小组 —— 四个角色", "",
         "**{}**".format(CONVERGE_NOTE), "",
         "| 角色 | 目标函数 | 产出物 | 否决权 |", "|---|---|---|---|"]
    for r in ROLE_ORDER:
        L.append("| **{}** | {} | {} | {} |".format(
            ROLES[r]["name"], ROLES[r]["goal"], ROLES[r]["deliverable"], ROLES[r]["veto"]))
    L += ["", "## 信息隔离：每个角色看不到什么（结构性保证）", "",
          "| 角色 | 看得到（白名单） | 看不到（被显式排除） |", "|---|---|---|"]
    for r in ROLE_ORDER:
        L.append("| {} | {} | {} |".format(
            ROLES[r]["name"], describe_inputs(r),
            "、".join(ROLES[r]["forbidden"]) or "（无）"))
    L += ["", "## 支持的目标市场", "", "| 市场 | 法域口径 |", "|---|---|"]
    for k, v in MARKETS.items():
        L.append("| {}（`{}`） | {} |".format(v["name"], k, v["law"]))
    L += ["", "## 硬闸门", ""]
    for g in payload["hard_gates"]:
        L.append("- " + g)
    L += ["", payload["gates_note"]]
    text = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    sys.stdout.write(text)
    return EXIT_OK


# ===========================================================================
# 子命令：glossary（花钱；--budget 校验是第一步）
# ===========================================================================

def _check_budget_opts(a):
    """**每个会花钱的子命令的第一步都调它。**
    给了 `--budget` 就必须给单价，否则预算上限没有意义（退出码 2）。"""
    if getattr(a, "budget", None) is not None and (
            getattr(a, "price_in", None) is None or getattr(a, "price_out", None) is None):
        raise UsageError("给了 --budget 就必须给 --price-in 与 --price-out"
                         "（单位：点/百万 token）—— 没有单价，预算上限没有意义")
    return True


def read_text(path, what="文件"):
    p = Path(path)
    if not p.exists():
        raise UsageError("找不到{}：{}".format(what, p))
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UsageError("{}不是可识别的文本编码（utf-8 / gb18030）：{}".format(what, p))


def ensure_outdir(a, default_name="localize-out"):
    if not getattr(a, "outdir", None):
        return None, None
    outdir = ensure_outside_pkg(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = {"version": 1, "entries": {}} if getattr(a, "force", False) \
        else load_state(outdir)
    return outdir, state


def _store(state, key, payload, label, dims):
    state.setdefault("entries", {})[key] = {
        "dims": dims, "label": label, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "payload": payload,
    }


def glossary_once(a, source, target_lang, market, model, key, tracker, state=None,
                  outdir=None):
    skey = state_key("glossary", source_sha=text_sha(source),
                     source_chars=len(source or ""), target_lang=target_lang,
                     market=market, model=model,
                     temperature=getattr(a, "temperature", 0.7))
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("术语表已在断点里，跳过（零成本）。\n")
            return hit["payload"], {}, 0.0, \
                {"stage": "glossary", "excluded": [], "markers_checked": 0,
                 "leaked": [], "ok": True}, 0, True
    prompt = build_glossary_prompt(source, target_lang, market,
                                   getattr(a, "source_lang", DEFAULT_SOURCE_LANG))
    obj, usage, elapsed, iso, pchars = _role_call(
        "translator", prompt, model, key, tracker, a, "术语表", GLOSSARY_OUT_TOKENS)
    g = normalize_glossary_output(obj, source)
    if state is not None:
        _store(state, skey, g, "glossary",
               {"source_sha": text_sha(source), "target_lang": target_lang,
                "market": market, "model": model})
        if outdir:
            save_state(outdir, state)
    return g, usage, elapsed, iso, pchars, False


def run_glossary(a):
    source = read_source(a)
    _check_budget_opts(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir, state = ensure_outdir(a)
    g, usage, elapsed, iso, pchars, cached = glossary_once(
        a, source, target_lang, market, a.model, a.key, tracker, state, outdir)
    log = new_log()
    log_isolation(log, "translator", iso, pchars, 1)
    log_entry(log, "glossary", "translator", 1, "出术语表",
              "{} 条；剔出编造 {} 条".format(g.get("count"), len(g.get("dropped") or [])))
    # 术语表本身就是"产出"，所以产出侧口径照扫一遍（引用/警告语境照旧留原因）
    problems, detail = text_gates(
        "\n".join(t["canonical"] for t in g["terms"]), "术语表", material=source,
        market=market, side="output")
    gates = detail if problems else {}
    rc = EXIT_GATE if problems else EXIT_OK
    md = render_glossary_md(g, {"source_lang": a.source_lang, "target_lang": target_lang,
                                "market": market})
    result = {"mode": "glossary", "role_version": ROLE_VERSION,
              "prompt_version": PROMPT_VERSION, "model": a.model,
              "source_lang": a.source_lang, "target_lang": target_lang, "market": market,
              "source_sha": text_sha(source), "source_chars": len(source),
              "glossary": g, "glossary_version": GLOSSARY_VERSION,
              "gates": gates, "gate_failed": bool(problems), "log": log,
              "usage": usage, "elapsed": elapsed,
              "cost": fmt_cost_dict(tracker) if tracker.calls else None,
              "cached": cached}
    if outdir is not None:
        (outdir / "glossary.json").write_text(
            json.dumps({"glossary_version": GLOSSARY_VERSION, "target_lang": target_lang,
                        "market": market, "source_sha": text_sha(source),
                        "source_chars": len(source), "terms": g["terms"],
                        "dropped": g["dropped"], "notes": g["notes"]},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "glossary.md").write_text(md, encoding="utf-8")
        append_log(outdir, log)
        sys.stderr.write("目录产物：{}（glossary.json / glossary.md）\n".format(outdir))
    if problems:
        _gate_stderr("术语表", detail)
    _emit(a, result, md, ok=not problems)
    return rc


# ===========================================================================
# 输入校验
# ===========================================================================

def read_source(a):
    if getattr(a, "text", None):
        return a.text
    if getattr(a, "file", None):
        return read_text(a.file, "源文")
    raise UsageError("必须给 --file（源文文件）或 --text（直接给正文）")


def check_market(m):
    if m not in MARKETS:
        raise UsageError("不支持的目标市场：{}（可选：{}）".format(
            m, " / ".join(MARKET_CHOICES)))
    return m


def check_lang(l):
    if l not in LANGS:
        raise UsageError("不支持的语言代码：{}（可选：{}）".format(l, " / ".join(LANG_CHOICES)))
    return l


def check_rounds(n):
    if n < 1 or n > 5:
        raise UsageError("--rounds 必须在 1~5 之间（默认 {}）—— 这个上限是故意的："
                         "同族有过\"为覆盖多种结局反复跑\"把预算跑超 3~4 倍的先例；"
                         "要更多轮就显式改这个数，不要靠默认值兜".format(DEFAULT_ROUNDS))
    return n


def load_glossary_file(path, source, target_lang):
    """读术语表文件，并**核对它是不是针对这一版源文与这个目标语言**。

    为什么要核对：术语表是断点 key 的一维。拿一份别的源文的术语表来续跑，
    产出会看起来正常、实际上术语完全对不上 —— 这类"静默复用"最难查。
    """
    p = Path(path)
    if not p.exists():
        raise UsageError("找不到术语表文件：{}".format(p))
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("术语表不是合法 JSON：{}（{}）".format(p, exc))
    if not isinstance(obj, dict):
        raise UsageError("术语表格式不对：顶层必须是对象，实际是 {}".format(type(obj).__name__))
    sha = obj.get("source_sha")
    if sha and sha != text_sha(source):
        raise UsageError(
            "术语表针对的不是这一版源文（术语表 sha `{}` ≠ 当前源文 sha `{}`）——"
            "拒绝复用。重新跑 `glossary`，或换一份配套的术语表。"
            .format(sha, text_sha(source)))
    tl = obj.get("target_lang")
    if tl and tl != target_lang:
        raise UsageError("术语表是给 `{}` 用的，当前目标语言是 `{}` —— 拒绝复用"
                         .format(tl, target_lang))
    terms = obj.get("terms")
    if not isinstance(terms, list):
        raise UsageError("术语表里没有 `terms` 数组")
    return {"terms": [t for t in terms if isinstance(t, dict)], "source_sha": sha,
            "target_lang": tl, "market": obj.get("market"),
            "dropped": obj.get("dropped") or [], "notes": obj.get("notes") or "",
            "count": len([t for t in terms if isinstance(t, dict)]),
            "path": str(p)}


def check_glossary_opt(a, source, target_lang):
    """`--glossary` 有就给，没有就 None（`run` 里会先跑一次 glossary）。"""
    path = getattr(a, "glossary", None)
    if not path:
        return None
    return load_glossary_file(path, source, target_lang)


# ===========================================================================
# 子命令：translate（译审）
# ===========================================================================

def translate_once(a, source, target_lang, market, glossary, model, key, tracker,
                   state=None, outdir=None, feedback=None, round_no=1):
    fb_sha = json_sha(feedback or [])
    skey = state_key("translate", source_sha=text_sha(source), source_chars=len(source),
                     target_lang=target_lang, market=market,
                     glossary_sha=json_sha(glossary or []),
                     glossary_version=GLOSSARY_VERSION, model=model,
                     temperature=getattr(a, "temperature", 0.7), round_no=round_no,
                     feedback_sha=fb_sha,
                     target_multiple=getattr(a, "target_multiple", DEFAULT_TARGET_MULTIPLE))
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("第 {} 轮译文已在断点里，跳过（零成本）。\n".format(round_no))
            tr = hit["payload"]
            return tr, hit["payload"].get("body", ""), {}, 0.0, \
                {"stage": "translator", "excluded": [], "markers_checked": 0,
                 "leaked": [], "ok": True}, 0, True
    prompt = build_translate_prompt(
        source, target_lang, market, glossary, feedback=feedback,
        target_multiple=getattr(a, "target_multiple", DEFAULT_TARGET_MULTIPLE),
        source_lang=getattr(a, "source_lang", DEFAULT_SOURCE_LANG), round_no=round_no)
    obj, usage, elapsed, iso, pchars = _role_call(
        "translator", prompt, model, key, tracker, a, "译文（第 {} 轮）".format(round_no),
        TRANSLATE_OUT_TOKENS, stage="translate")
    tr, body = normalize_translate_output(obj, source, target_lang,
                                          raw_text=_LAST_RAW.get("text"), outdir=outdir)
    if state is not None:
        _store(state, skey, tr, "translate",
               {"source_sha": text_sha(source), "target_lang": target_lang,
                "market": market, "glossary_sha": json_sha(glossary or []),
                "round_no": round_no, "feedback_sha": fb_sha, "model": model})
        if outdir:
            save_state(outdir, state)
    return tr, body, usage, elapsed, iso, pchars, False


def run_translate(a):
    source = read_source(a)
    _check_budget_opts(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    glossary = check_glossary_opt(a, source, target_lang)
    glist = (glossary or {}).get("terms") or []
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir, state = ensure_outdir(a)
    tr, body, usage, elapsed, iso, pchars, cached = translate_once(
        a, source, target_lang, market, glist, a.model, a.key, tracker, state, outdir,
        round_no=1)
    log = new_log()
    log_isolation(log, "translator", iso, pchars, 1)
    # 闸门：译文侧的合规/占位符/照抄示例 + 逐句回译对照的句子锚点
    problems, detail = text_gates(body, "译文", material=source, market=market,
                                 side="output")
    mats = body + "\n" + "\n".join(p.get("back_translation") or ""
                                   for p in tr.get("pairs") or [])
    prob2, detail2 = text_gates(mats, "回译", material=source, market=market, side="output")
    detail.update({("retrans_" + k): v for k, v in detail2.items()})
    problems += prob2
    # 锚点：译文的每一对 source 必须能在源文里找到（防"编造原文"）
    src_pairs = [{"quote": p.get("source")} for p in tr.get("pairs") or []]
    good, bad, astat = anchor_issues(src_pairs, source, label="源文")
    detail["anchor"] = astat
    if astat["unanchored_ratio"] > ANCHOR_MAX_MISS:
        problems.append("逐句对齐的源句有 {}/{} 条在源文里找不到（未锚定率 {:.0%} > {:.0%}）"
                        "—— 判为定位失败".format(astat["unanchored"], astat["total"],
                                                 astat["unanchored_ratio"], ANCHOR_MAX_MISS))
    # 句子覆盖：源文每一句都必须出现在 pairs 里（防漏译整句）
    missing_sents = [s for s in split_sentences(source)
                     if not any(_norm_anchor(s) and (
                         _norm_anchor(s) in _norm_anchor(p.get("source"))
                         or _norm_anchor(p.get("source")) in _norm_anchor(s))
                         for p in tr.get("pairs") or [])]
    if missing_sents:
        detail["missing_sentences"] = [s[:80] for s in missing_sents]
        problems.append("源文有 {} 句没有进逐句对照（可能漏译）".format(len(missing_sents)))
    # 数字与单位保全
    mrep = measure_report(source, body, market, pairs=tr.get("pairs"),
                          fx_rate=getattr(a, "fx_rate", None))
    detail["measures"] = mrep
    problems += _measure_problems(mrep)
    # 术语一致性（本地算）
    trep = glossary_consistency(source, body, glist, pairs=tr.get("pairs"),
                                target_lang=target_lang)
    detail["terminology"] = trep
    if trep["inconsistent_count"]:
        problems.append("术语不一致 {} 条：{}".format(
            trep["inconsistent_count"],
            "、".join("{}（应为 {}）".format(i["source_term"], i["canonical"])
                      for i in trep["inconsistent"][:4])))
    gates = detail
    rc = EXIT_GATE if problems else EXIT_OK
    result = {
        "mode": "translate", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "model": a.model, "source_lang": a.source_lang, "target_lang": target_lang,
        "market": market, "source_sha": text_sha(source), "source_chars": len(source),
        "source_path": str(a.file) if getattr(a, "file", None) else None,
        "glossary": {"count": len(glist), "sha": json_sha(glist),
                     "path": (glossary or {}).get("path")},
        "translation": tr, "body": body, "chars": len(body),
        "gates": gates, "gate_failed": bool(problems), "problems": problems,
        "log": log, "usage": usage, "elapsed": elapsed, "cached": cached,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
        "isolation": {"translator": iso},
    }
    md = render_translation_md(tr, {"source_lang": a.source_lang, "target_lang": target_lang,
                                    "market": market, "model": a.model, "round_no": 1})
    if outdir is not None:
        (outdir / "translation.json").write_text(
            json.dumps({"translation": tr, "market": market, "target_lang": target_lang,
                        "source_sha": text_sha(source), "glossary_sha": json_sha(glist)},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "translation.md").write_text(md, encoding="utf-8")
        append_log(outdir, log)
        sys.stderr.write("目录产物：{}（translation.json / translation.md）\n".format(outdir))
    if problems:
        _gate_stderr("译文", detail)
    _emit(a, result, md, ok=not problems)
    return rc


def load_translation_file(path):
    p = Path(path)
    if not p.exists():
        raise UsageError("找不到译文文件：{}".format(p))
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("译文不是合法 JSON：{}（{}）".format(p, exc))
    if isinstance(obj, dict) and isinstance(obj.get("translation"), dict):
        tr = obj["translation"]
    elif isinstance(obj, dict) and obj.get("pairs") is not None:
        tr = obj
    else:
        raise UsageError("译文文件里没有 `translation` 或 `pairs`：{}".format(p))
    tr.setdefault("pairs", [])
    tr.setdefault("body", "\n".join(p.get("target") or "" for p in tr["pairs"]))
    tr.setdefault("unit_notes", [])
    tr.setdefault("glossary_objections", [])
    tr.setdefault("feedback_applied", [])
    return tr


# ===========================================================================
# 子命令：culture（文化适配，**能否决**）
# ===========================================================================

def culture_once(a, source, translation, target_lang, market, model, key, tracker,
                 state=None, outdir=None, round_no=1):
    body = translation.get("body") or ""
    skey = state_key("culture", source_sha=text_sha(source), body_sha=text_sha(body),
                     target_lang=target_lang, market=market, model=model,
                     temperature=getattr(a, "temperature", 0.7), round_no=round_no)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("文化适配（第 {} 轮）已在断点里，跳过（零成本）。\n".format(round_no))
            return hit["payload"], {}, 0.0, \
                {"stage": "culture", "excluded": [], "markers_checked": 0,
                 "leaked": [], "ok": True}, 0, True
    prompt = build_culture_prompt(source, body, market, target_lang,
                                 getattr(a, "source_lang", DEFAULT_SOURCE_LANG))
    obj, usage, elapsed, iso, pchars = _role_call(
        "culture", prompt, model, key, tracker, a, "文化风险清单（第 {} 轮）".format(round_no),
        CULTURE_OUT_TOKENS)
    res = normalize_verdict_obj(obj, CULTURE_VERDICT_MAP, "risks",
                                ("quote", "dimension", "severity", "why", "ask"))
    if state is not None:
        _store(state, skey, res, "culture",
               {"source_sha": text_sha(source), "body_sha": text_sha(body),
                "market": market, "round_no": round_no, "model": model})
        if outdir:
            save_state(outdir, state)
    return res, usage, elapsed, iso, pchars, False


def run_culture(a):
    source = read_source(a)
    _check_budget_opts(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    translation = load_translation_file(a.translation)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir, state = ensure_outdir(a)
    res, usage, elapsed, iso, pchars, cached = culture_once(
        a, source, translation, target_lang, market, a.model, a.key, tracker, state, outdir)
    log = new_log()
    log_isolation(log, "culture", iso, pchars, 1)
    # 锚点：每条风险必须引用译文里真实存在的一句
    good, bad, astat = anchor_issues(res["items"], translation.get("body") or "",
                                     label="译文")
    res["items"] = good
    res["unanchored"] = bad
    log_ruling(log, "culture", 1, res["verdict"] or "(未识别)",
               res.get("summary") or "（无总评）",
               quotes=[i.get("quote") for i in good[:3]])
    problems = []
    if astat["unanchored_ratio"] > ANCHOR_MAX_MISS and astat["total"]:
        problems.append("文化风险有 {}/{} 条引文在译文里找不到（未锚定率 {:.0%}）—— "
                        "判为定位失败".format(astat["unanchored"], astat["total"],
                                             astat["unanchored_ratio"]))
    elif bad:
        problems.append("{}/{} 条文化风险引文编造，已剔出".format(
            astat["unanchored"], astat["total"]))
    vg = verdict_gate(res.get("verdict"), [i.get("why") or i.get("ask") for i in good],
                      "culture")
    problems += vg
    detail = {"anchor": astat, "verdict": vg or None}
    p2, d2 = text_gates(res.get("summary") or "", "文化适配裁决",
                        material=source, market=market, side="output")
    problems += p2
    detail.update(d2)
    rc = EXIT_GATE if problems else EXIT_OK
    result = {"mode": "culture", "role_version": ROLE_VERSION,
              "prompt_version": PROMPT_VERSION, "model": a.model,
              "source_lang": a.source_lang, "target_lang": target_lang, "market": market,
              "target_market_name": (MARKETS.get(market) or {})["name"],
              "verdict": res.get("verdict"), "raw_verdict": res.get("raw_verdict"),
              "verdict_label": VERDICT_LABEL.get(res.get("verdict")),
              "veto_power": ROLES["culture"]["veto"],
              "risks": good, "unanchored_risks": bad, "anchor": astat,
              "summary": res.get("summary"), "gates": detail,
              "gate_failed": bool(problems), "problems": problems, "log": log,
              "usage": usage, "elapsed": elapsed, "cached": cached,
              "isolation": {"culture": iso},
              "cost": fmt_cost_dict(tracker) if tracker.calls else None}
    md = render_role_md("culture", res, {"market": market, "round_no": 1})
    if outdir is not None:
        (outdir / "culture.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "culture.md").write_text(md, encoding="utf-8")
        append_log(outdir, log)
        sys.stderr.write("目录产物：{}（culture.json / culture.md）\n".format(outdir))
    if problems:
        _gate_stderr("文化适配", detail)
    _emit(a, result, md, ok=not problems)
    return rc


# ===========================================================================
# 子命令：glossary_check（术语一致性，**能打回**；纯本地，可零成本重跑）
# ===========================================================================

def run_glossary_check(a):
    """纯本地子命令：不调模型、不花钱。所以这里**不校验 --budget**（没有花费）。"""
    source = read_source(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    glossary = check_glossary_opt(a, source, target_lang)
    if glossary is None:
        raise UsageError("glossary_check 需要 --glossary 指一份术语表"
                         "（`run.py glossary --file … --json --out glossary.json`）")
    translation = load_translation_file(a.translation)
    rep = glossary_consistency(source, translation.get("body") or "",
                               glossary.get("terms") or [],
                               pairs=translation.get("pairs"), target_lang=target_lang)
    # 本命令**不看模型自报**：判定完全由本地算；模型自报的清单只作对照
    trep = {"local": rep}
    problems = []
    if rep["inconsistent_count"]:
        problems.append("术语不一致 {} 条".format(rep["inconsistent_count"]))
    verdict = VERDICT_SEND_BACK if problems else VERDICT_PASS
    result = {"mode": "glossary_check", "role_version": ROLE_VERSION,
              "glossary_version": GLOSSARY_VERSION, "source_lang": a.source_lang,
              "target_lang": target_lang, "market": market,
              "source_sha": text_sha(source), "glossary_sha": json_sha(glossary["terms"]),
              "verdict": verdict, "verdict_label": VERDICT_LABEL[verdict],
              "veto_power": ROLES["terminologist"]["veto"],
              "terminology": rep, "problems": problems,
              "gate_failed": bool(problems), "paid": False,
              "note": "本子命令**纯本地零成本**：判定不依赖模型自报，结论可复现",
              "checks": trep}
    rc = EXIT_GATE if problems else EXIT_OK
    md = ["# 术语官 · 一致性核对（纯本地，零成本）", "",
          "- 目标语言：{}".format(lang_name(target_lang)),
          "- 目标市场：{}".format((MARKETS.get(market) or {})["name"]),
          "- 核对术语：**{}** 条".format(rep["checked_terms"]),
          "- 对齐：{} 组（源文 {} 句 / 译文 {} 句）".format(
              rep["pair_alignment"]["pairs"], rep["pair_alignment"]["source_sentences"],
              rep["pair_alignment"]["target_sentences"]),
          "- 裁决：**{}**".format(VERDICT_LABEL[verdict]),
          "", "| 源词 | 规范译法 | 出现 | 命中 | 判定 |", "|---|---|---|---|---|"]
    for t in rep["terms"]:
        md.append("| {} | {} | {} | {} | {} |".format(
            t["source_term"], t["canonical"], t["occurrences"], t["hits"], t["verdict"]))
    if rep["inconsistent"]:
        md += ["", "## 不一致明细（**全部出现位置**）", ""]
        for inc in rep["inconsistent"]:
            md.append("### `{}` → 应为 `{}`（{} 处出现，{} 处命中）".format(
                inc["source_term"], inc["canonical"], inc["occurrences"], inc["hits"]))
            for mi in inc["misses"]:
                md.append("- 第 {} 句源文：{}".format(mi.get("source_index"),
                                                    mi.get("src_sentence")))
                md.append("  - 对应译文：{}".format(mi.get("target_sentence")))
            md.append("")
    md_text = "\n".join(md) + "\n"
    if a.out:
        Path(a.out).write_text(md_text, encoding="utf-8")
    # ⚠️ 参数顺序：第 2 个是人读文案，第 3 个才是 JSON 对象。
    # 本包自测时写反过一次（把 md 传成 json_obj），表现是"stdout 多出一个非 JSON 块"
    # 而退出码看起来正常 —— 契约被破坏却不容易发现。
    _emit(a, md_text, result, ok=not problems)
    return rc


# ===========================================================================
# 子命令：compliance（目标市场合规，**可否决**）
# ===========================================================================

def compliance_once(a, source, translation, target_lang, market, model, key, tracker,
                    state=None, outdir=None, round_no=1):
    body = translation.get("body") or ""
    skey = state_key("compliance", source_sha=text_sha(source), body_sha=text_sha(body),
                     target_lang=target_lang, market=market, model=model,
                     temperature=getattr(a, "temperature", 0.7), round_no=round_no)
    if state is not None:
        hit = (state.get("entries") or {}).get(skey)
        if hit:
            sys.stderr.write("合规（第 {} 轮）已在断点里，跳过（零成本）。\n".format(round_no))
            return hit["payload"], {}, 0.0, \
                {"stage": "compliance", "excluded": [], "markers_checked": 0,
                 "leaked": [], "ok": True}, 0, True
    prompt = build_compliance_prompt(source, body, market, target_lang,
                                    getattr(a, "source_lang", DEFAULT_SOURCE_LANG))
    obj, usage, elapsed, iso, pchars = _role_call(
        "compliance", prompt, model, key, tracker, a,
        "合规裁决（第 {} 轮）".format(round_no), COMPLIANCE_OUT_TOKENS)
    res = normalize_verdict_obj(obj, TERM_VERDICT_MAP, "risks",
                                ("quote", "side", "risk", "severity", "why", "ask"))
    res["safe_replacements"] = [r for r in res.get("safe_replacements") or []
                                if isinstance(r, dict)]
    if state is not None:
        _store(state, skey, res, "compliance",
               {"source_sha": text_sha(source), "body_sha": text_sha(body),
                "market": market, "round_no": round_no, "model": model})
        if outdir:
            save_state(outdir, state)
    return res, usage, elapsed, iso, pchars, False


def run_compliance(a):
    source = read_source(a)
    _check_budget_opts(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    translation = load_translation_file(a.translation)
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir, state = ensure_outdir(a)
    res, usage, elapsed, iso, pchars, cached = compliance_once(
        a, source, translation, target_lang, market, a.model, a.key, tracker, state, outdir)
    log = new_log()
    log_isolation(log, "compliance", iso, pchars, 1)
    material = source + "\n" + (translation.get("body") or "")
    good, bad, astat = anchor_issues(res["items"], material, label="源文或译文")
    res["items"] = good
    res["unanchored"] = bad
    log_ruling(log, "compliance", 1, res["verdict"] or "(未识别)",
               res.get("summary") or "（无总评）",
               quotes=[i.get("quote") for i in good[:3]])
    problems = []
    if astat["total"] and astat["unanchored_ratio"] > ANCHOR_MAX_MISS:
        problems.append("合规风险有 {}/{} 条引文在源文或译文里找不到（未锚定率 {:.0%}）—— "
                        "判为定位失败".format(astat["unanchored"], astat["total"],
                                             astat["unanchored_ratio"]))
    elif bad:
        problems.append("{}/{} 条合规风险引文编造，已剔出".format(astat["unanchored"],
                                                              astat["total"]))
    vg = verdict_gate(res.get("verdict"), [i.get("why") or i.get("ask") for i in good],
                      "compliance")
    problems += vg
    # 产出侧合规（裁决文书自己的文字）+ 材料侧（源文，全扫）
    p_out, d_out = text_gates(res.get("summary") or "", "合规裁决",
                              material=material, market=market, side="output")
    problems += p_out
    p_mat, d_mat = text_gates(source, "源文", market=market, side="material")
    detail = {"anchor": astat, "verdict": vg or None}
    detail.update(d_out)
    detail["source_side"] = d_mat
    if p_mat:
        problems.append("源语言侧命中 {} 处（材料侧照查）".format(len(p_mat)))
    rc = EXIT_GATE if problems else EXIT_OK
    result = {"mode": "compliance", "role_version": ROLE_VERSION,
              "prompt_version": PROMPT_VERSION, "ruling_version": RULING_VERSION,
              "model": a.model, "source_lang": a.source_lang, "target_lang": target_lang,
              "market": market, "target_market_name": (MARKETS.get(market) or {})["name"],
              "law": (MARKETS.get(market) or {})["law"],
              "verdict": res.get("verdict"), "raw_verdict": res.get("raw_verdict"),
              "verdict_label": VERDICT_LABEL.get(res.get("verdict")),
              "veto_power": ROLES["compliance"]["veto"],
              "risks": good, "unanchored_risks": bad, "anchor": astat,
              "safe_replacements": res.get("safe_replacements") or [],
              "summary": res.get("summary"), "gates": detail,
              "gate_failed": bool(problems), "problems": problems, "log": log,
              "usage": usage, "elapsed": elapsed, "cached": cached,
              "isolation": {"compliance": iso},
              "cost": fmt_cost_dict(tracker) if tracker.calls else None}
    md = render_role_md("compliance", res, {"market": market, "round_no": 1})
    if outdir is not None:
        (outdir / "compliance.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "compliance.md").write_text(md, encoding="utf-8")
        append_log(outdir, log)
        sys.stderr.write("目录产物：{}（compliance.json / compliance.md）\n".format(outdir))
    if problems:
        _gate_stderr("合规", detail)
    _emit(a, result, md, ok=not problems)
    return rc


# ===========================================================================
# 子命令：run（一条命令出成品）
#
# 一轮的走向（四席**并行独立**，不是投票，也不是串行顺序放行）：
#
#     译审 translate ─┬─▶ 术语官 glossary_check（纯本地）
#                     ├─▶ 文化适配 culture（**能否决**）
#                     └─▶ 合规 compliance（**可否决 / 一票否决**）
#
# 任何一席打回/否决 → 下一轮重译，重译提示词里**只带要求，不带提要求的席位与理由**
# （有向反馈：打回真的生效，同时保住下一轮的独立性）。
# ===========================================================================

def _quotes_of(role, obj):
    out = []
    for it in (obj.get("items") or []):
        if str(it.get("quote") or "").strip():
            out.append(it["quote"])
    return out[:5]


def _asks_of(role, obj, limit=6):
    out = []
    for it in (obj.get("items") or []):
        ask = str(it.get("ask") or "").strip()
        if ask:
            out.append({"quote": it.get("quote"), "ask": ask, "role": role})
    return out[:limit]


def _reasons_of(obj, limit=6):
    out = []
    for it in (obj.get("items") or []):
        r = str(it.get("why") or "").strip()
        if r:
            out.append(r)
    if not out and str(obj.get("summary") or "").strip():
        out.append(obj.get("summary"))
    return out[:limit]


def body_similarity(a_text, b_text):
    """两版正文的相似度（字符二元组 Jaccard）。用来判"这一轮有没有实质改动"。"""
    return round(_similarity(a_text or "", b_text or ""), 4)


def run_run(a):
    source = read_source(a)
    _check_budget_opts(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    rounds_max = check_rounds(getattr(a, "rounds", DEFAULT_ROUNDS))
    tracker = CostTracker(a.budget, a.price_in, a.price_out)
    outdir = ensure_outside_pkg(a.outdir) if getattr(a, "outdir", None) else None
    if outdir is not None:
        outdir.mkdir(parents=True, exist_ok=True)
    state = ({"version": 1, "entries": {}} if getattr(a, "force", False)
             else load_state(outdir)) if outdir else None

    g_in = check_glossary_opt(a, source, target_lang)
    glossary = (g_in or {}).get("terms") or []
    gl_source = "复用 --glossary" if g_in else "本趟现抽"
    log = new_log()
    usage_acc = new_usage()
    glossary_obj = g_in
    iso_evidence = {}
    glossary_cached = None

    if g_in is None:
        g, u1, _e1, iso_g, pc1, cached = glossary_once(
            a, source, target_lang, market, a.model, a.key, tracker, state, outdir)
        glossary = g["terms"]
        glossary_obj = g
        glossary_cached = cached
        add_usage(usage_acc, u1)
        iso_evidence["translator_glossary"] = iso_g
        log_isolation(log, "translator", iso_g, pc1, 0)
        log_entry(log, "glossary", "translator", 0, "出术语表",
                  "{} 条；剔出编造 {} 条".format(g.get("count"),
                                                len(g.get("dropped") or [])))

    rounds_trace = []
    unresolved = []
    escalation = None
    final_tr = None
    final_body = ""
    all_gates = {}
    role_verdicts = {}
    feedback = None
    prev_body = None
    no_change_strikes = 0

    for rnd in range(1, rounds_max + 1):
        tr, body, u2, _e2, iso_t, pc2, cached = translate_once(
            a, source, target_lang, market, glossary, a.model, a.key, tracker, state,
            outdir, feedback=feedback, round_no=rnd)
        add_usage(usage_acc, u2)
        iso_evidence["translator"] = iso_t
        log_isolation(log, "translator", iso_t, pc2, rnd)
        log_entry(log, "translate", "translator", rnd, "交译文",
                  "{} 字符；逐句对齐 {} 组；落实打回要求 {} 条".format(
                      len(body), len(tr.get("pairs") or []),
                      len(tr.get("feedback_applied") or [])),
                  quotes=[p.get("target") for p in (tr.get("pairs") or [])[:2]])

        # ---- 术语官：纯本地核查（零成本），判定不看模型自报 ----
        trep = glossary_consistency(source, body, glossary,
                                    pairs=tr.get("pairs"), target_lang=target_lang)
        # ---- 文化适配 ----
        cul, u3, _e3, iso_c, pc3, cached_c = culture_once(
            a, source, tr, target_lang, market, a.model, a.key, tracker, state, outdir,
            round_no=rnd)
        add_usage(usage_acc, u3)
        iso_evidence["culture"] = iso_c
        log_isolation(log, "culture", iso_c, pc3, rnd)
        good_c, bad_c, astat_c = anchor_issues(cul["items"], body, label="译文")
        cul["items"], cul["unanchored"] = good_c, bad_c
        # ---- 合规 ----
        comp, u4, _e4, iso_k, pc4, cached_k = compliance_once(
            a, source, tr, target_lang, market, a.model, a.key, tracker, state, outdir,
            round_no=rnd)
        add_usage(usage_acc, u4)
        iso_evidence["compliance"] = iso_k
        log_isolation(log, "compliance", iso_k, pc4, rnd)
        material = source + "\n" + body
        good_k, bad_k, astat_k = anchor_issues(comp["items"], material, label="源文或译文")
        comp["items"], comp["unanchored"] = good_k, bad_k

        # ---- 局部闸门（本地判定，不看模型自报） ----
        p_t, d_t = text_gates(body, "译文", material=source, market=market, side="output")
        mrep = measure_report(source, body, market, pairs=tr.get("pairs"),
                              fx_rate=getattr(a, "fx_rate", None))
        p_c, d_c = text_gates(cul.get("summary") or "", "文化适配裁决", material=material,
                              market=market, side="output")
        p_k, d_k = text_gates(comp.get("summary") or "", "合规裁决", material=material,
                              market=market, side="output")
        p_mat, d_mat = text_gates(source, "源文", market=market, side="material")

        v_term = VERDICT_SEND_BACK if trep["inconsistent_count"] else VERDICT_PASS
        v_cul = cul.get("verdict") or VERDICT_PASS
        v_comp = comp.get("verdict") or VERDICT_PASS
        # 合规的一票否决：模型自己判 veto 就停；本地也留一道（源语言侧高风险）
        veto_local = bool(p_mat and any(
            h.get("level") == "高" for h in (d_mat.get("compliance") or [])))
        if veto_local and v_comp == VERDICT_PASS:
            v_comp = VERDICT_SEND_BACK
        v_trans = VERDICT_PASS
        trans_reasons = list(p_t) + _measure_problems(mrep)
        if trans_reasons:
            v_trans = VERDICT_SEND_BACK

        role_verdicts = {"translator": v_trans, "terminologist": v_term,
                         "culture": v_cul, "compliance": v_comp}
        # 裁决完整性：打回/否决必须留可读理由 + 不许自相矛盾
        vp = []
        vp += verdict_gate(v_cul, _reasons_of(cul), "culture")
        vp += verdict_gate(v_comp, _reasons_of(comp), "compliance")
        if v_term == VERDICT_SEND_BACK:
            vp += ["术语官打回：{} 条术语不一致（本地判定，见 terminology）".format(
                trep["inconsistent_count"])]
        if v_trans == VERDICT_SEND_BACK:
            vp += ["译审打回：{}".format("；".join(trans_reasons[:3]))]

        rec = {"round": rnd, "roles": {
            "translator": {"verdict": v_trans, "summary": "；".join(trans_reasons[:3]),
                           "quotes": [p.get("target") for p in (tr.get("pairs") or [])[:2]],
                           "reasons": trans_reasons[:6],
                           "asks": [{"quote": m.get("context"),
                                     "ask": "把数字 {} 补回译文（单位 {}）".format(
                                         m.get("number"), m.get("unit") or "无")}
                                    for m in (mrep.get("missing") or [])[:3]]},
            "terminologist": {"verdict": v_term,
                              "summary": "{} 条不一致 / 核对 {} 条".format(
                                  trep["inconsistent_count"], trep["checked_terms"]),
                              "quotes": [i["misses"][0]["target_sentence"]
                                         for i in trep["inconsistent"] if i.get("misses")],
                              "reasons": ["`{}` 应为 `{}`（{} 处出现，{} 处命中）".format(
                                  i["source_term"], i["canonical"], i["occurrences"],
                                  i["hits"]) for i in trep["inconsistent"][:6]],
                              "asks": [{"quote": i["misses"][0]["target_sentence"],
                                        "ask": "把 `{}` 全部统一成 `{}`".format(
                                            i["source_term"], i["canonical"])}
                                       for i in trep["inconsistent"] if i.get("misses")][:6]},
            "culture": {"verdict": v_cul, "summary": cul.get("summary"),
                        "quotes": _quotes_of("culture", cul),
                        "reasons": _reasons_of(cul), "asks": _asks_of("culture", cul)},
            "compliance": {"verdict": v_comp, "summary": comp.get("summary"),
                           "quotes": _quotes_of("compliance", comp),
                           "reasons": _reasons_of(comp), "asks": _asks_of("compliance", comp)},
        }, "gates": {"terminology": trep, "measures": mrep,
                     "anchor": {"translation": None, "culture": astat_c,
                                "compliance": astat_k},
                     "output": d_t, "culture_doc": d_c, "compliance_doc": d_k,
                     "source_side": d_mat},
            "verdict_problems": vp}
        # 未锚定的引文一律剔出重译输入（不许拿编造的引文去要求别人改）
        if bad_c or bad_k:
            rec["dropped_unanchored"] = {
                "culture": [b.get("quote") for b in bad_c],
                "compliance": [b.get("quote") for b in bad_k]}

        hard = [r for r, v in role_verdicts.items() if v in VERDICT_HARD]
        if rnd > 1:
            sim = body_similarity(prev_body or "", body)
            rec["body_sim"] = sim
            if sim >= BODY_MIN_SIM:
                no_change_strikes += 1
                rec["no_change"] = True
            else:
                no_change_strikes = 0
        prev_body = body

        if not hard:
            final_tr, final_body = tr, body
            all_gates = rec["gates"]
            all_gates["verdict"] = vp or None
            rounds_trace.append(rec)
            escalation = ("第 {} 轮四席全部放行（译审 / 术语官 / 文化适配 / 合规）"
                          .format(rnd))
            break

        # 打回 → 组装**有向反馈**：只带要求，不带提要求的席位与理由
        #
        # 这是本包信息隔离与"打回真的生效"这两件事的交汇点：
        # 下一轮重译必须按这些要求改，但改的人**不知道是谁在什么立场上提的** ——
        # 所以下一轮的译审仍然是独立判断，不是顺着别人的结论走。
        feedback = []
        for r in hard:
            for it in (rec["roles"][r].get("asks") or []):
                ask = str(it.get("ask") or "").strip()
                if ask:
                    feedback.append({"quote": it.get("quote"), "ask": ask})
        # 术语官与译审的打回要求从**本地判定**里构造（它们的结论不是模型自报的清单）
        for r in hard:
            if r == "terminologist":
                for i in trep["inconsistent"]:
                    for mi in i["misses"][:3]:
                        feedback.append({"quote": mi.get("target_sentence"),
                                         "ask": "把 `{}` 统一成 `{}`（这一处现在没用规范译法）"
                                                .format(i["source_term"], i["canonical"])})
            if r == "translator":
                for m in mrep["missing"][:4]:
                    feedback.append({"quote": m.get("context"),
                                     "ask": "把数字 {}（单位 {}）补回译文，别丢数字"
                                            .format(m.get("number"), m.get("unit") or "无")})
                for m in mrep["wrong_conversion"][:3]:
                    exp = m.get("expected") or {}
                    feedback.append({"quote": m.get("context"),
                                     "ask": "这一处单位换算不对：`{} {}` 在目标市场应约为 "
                                            "{} {}（{}）".format(
                                                m.get("number"), m.get("unit") or "",
                                                round(exp.get("value") or 0, 3),
                                                exp.get("unit"), exp.get("why"))})
                for prob in p_t[:4]:
                    feedback.append({"quote": None, "ask": prob})
        # 去重（同样的要求别重复塞）
        seen_fb, fb2 = set(), []
        for f in feedback:
            key = (str(f.get("quote") or "")[:40], str(f.get("ask") or "")[:60])
            if key in seen_fb:
                continue
            seen_fb.add(key)
            fb2.append(f)
        feedback = fb2
        rec["retranslated"] = True
        rec["feedback_count"] = len(feedback)
        rounds_trace.append(rec)
        log_ruling(log, "translator", rnd, VERDICT_SEND_BACK if hard else VERDICT_PASS,
                   "打回席位：{}；组装了 {} 条可执行要求给下一轮重译"
                   .format("、".join(ROLES[r]["name"] for r in hard), len(feedback)),
                   quotes=[q for r in hard for q in
                           (rec["roles"][r].get("quotes") or [])[:2]])
        # 连续两轮没有实质改动 → 显式出口（别再把钱花在同一件事上）
        if no_change_strikes > MAX_NO_CHANGE_STRIKES:
            escalation = ("连续 {} 轮重译后译文没有实质改动（相似度 ≥ {:.2f}），"
                          "判定为改不动，升级给人看".format(no_change_strikes, BODY_MIN_SIM))
            final_tr, final_body = tr, body
            all_gates = rec["gates"]
            break
        if rnd == rounds_max:
            final_tr, final_body = tr, body
            all_gates = rec["gates"]
            for r in hard:
                for reason in (rec["roles"][r].get("reasons") or ["（无理由）"])[:3]:
                    unresolved.append({
                        "role": r, "role_name": ROLES[r]["name"], "round": rnd,
                        "verdict": role_verdicts[r],
                        "verdict_label": VERDICT_LABEL.get(role_verdicts[r]),
                        "why": reason,
                        "quotes": (rec["roles"][r].get("quotes") or [])[:2]})
            escalation = ("轮次用尽（{} 轮）仍有 {} 席打回/否决 —— "
                          "产出带未决项，**不假装谈拢**"
                          .format(rounds_max, len(hard)))

    # ---- 最终综合裁决 ----
    hard_final = {r: v for r, v in role_verdicts.items() if v in VERDICT_HARD}
    if unresolved:
        final_verdict = VERDICT_VETO if any(
            v == VERDICT_VETO for v in role_verdicts.values()) else VERDICT_SEND_BACK
    elif hard_final:
        final_verdict = VERDICT_SEND_BACK
    elif role_verdicts.get("compliance") == VERDICT_FIX:
        final_verdict = VERDICT_FIX
    else:
        final_verdict = VERDICT_PASS
    final_verdict = final_verdict or VERDICT_PASS

    # ---- 总闸门：裁决闭合 + 产出侧/材料侧合规 ----
    gate_problems = []
    gate_gates = dict(all_gates or {})
    if final_body:
        p_b, d_b = text_gates(final_body, "定稿译文", material=source, market=market,
                              side="output")
        gate_problems += p_b
        gate_gates["final_output"] = d_b
        mrep_f = gate_gates.get("measures") or measure_report(
            source, final_body, market, pairs=(final_tr or {}).get("pairs"),
            fx_rate=getattr(a, "fx_rate", None))
        if mrep_f.get("missing"):
            gate_problems.append("定稿仍缺数字 {} 处".format(mrep_f["missing_count"]))
        trep_f = gate_gates.get("terminology")
        if trep_f and trep_f.get("inconsistent_count"):
            gate_problems.append("定稿仍有术语不一致 {} 条".format(
                trep_f["inconsistent_count"]))
    dc = decision_closure(
        {"verdict": final_verdict,
         "summary": (final_tr or {}).get("title") or "",
         "reason": (escalation or ""),
         "rounds_used": len(rounds_trace)},
        role_verdicts, unresolved, len(rounds_trace))
    if dc:
        gate_problems += dc
        gate_gates["verdict"] = dc
    # 隔离被破坏是不可能发生的（调用前就抛了），这里只是把证据写进产出
    if any(v.get("leaked") for v in iso_evidence.values()):
        gate_problems.append("信息隔离被破坏（有席位看到了别的席位的结论）")

    # ---- 产物 ----
    translation_md = render_translation_md(
        final_tr or {"body": final_body, "pairs": []},
        {"source_lang": a.source_lang, "target_lang": target_lang, "market": market,
         "model": a.model, "round_no": len(rounds_trace)})
    md_out = ""
    if final_body:
        md_out = final_body if final_body.endswith("\n") else final_body + "\n"
    result = {
        "mode": "run", "role_version": ROLE_VERSION, "prompt_version": PROMPT_VERSION,
        "ruling_version": RULING_VERSION, "glossary_version": GLOSSARY_VERSION,
        "model": a.model, "source_lang": a.source_lang, "target_lang": target_lang,
        "market": market, "market_name": (MARKETS.get(market) or {})["name"],
        "law": (MARKETS.get(market) or {})["law"],
        "source_path": str(a.file) if getattr(a, "file", None) else None,
        "source_sha": text_sha(source), "source_chars": len(source),
        "target_multiple": getattr(a, "target_multiple", DEFAULT_TARGET_MULTIPLE),
        "glossary": {"count": len(glossary), "sha": json_sha(glossary),
                     "source": gl_source,
                     "dropped": len((glossary_obj or {}).get("dropped") or []),
                     "terms": glossary},
        "glossary_obj": glossary_obj,
        "translation": final_tr,
        "final_body": final_body, "final_chars": len(final_body),
        "final_verdict": final_verdict,
        "final_verdict_label": VERDICT_LABEL.get(final_verdict),
        "role_verdicts": role_verdicts,
        "role_verdict_labels": {r: VERDICT_LABEL.get(v) for r, v in role_verdicts.items()},
        "rounds_used": len(rounds_trace), "rounds_max": rounds_max,
        "rounds_trace": rounds_trace,
        "unresolved": unresolved, "escalation": escalation,
        "gates": gate_gates, "gate_failed": bool(gate_problems),
        "problems": gate_problems,
        "isolation": {k: v for k, v in iso_evidence.items()},
        "isolation_whitelist": {r: {"inputs": ROLES[r]["inputs"],
                                    "forbidden": ROLES[r]["forbidden"]}
                                for r in ROLE_ORDER},
        "log": log,
        "usage": usage_acc,
        "usage_calls": tracker.calls,
        "cost": fmt_cost_dict(tracker) if tracker.calls else None,
        "cost_text": fmt_cost(tracker.usage),
        "cached_any": bool(glossary_cached),
    }
    report_md = render_report_md(result)
    if outdir is not None:
        (outdir / "final.md").write_text(md_out or "（本轮没有产出译文）\n", encoding="utf-8")
        (outdir / "final.json").write_text(json.dumps({
            "final_verdict": final_verdict, "final_verdict_label":
                VERDICT_LABEL.get(final_verdict), "translation": final_tr,
            "role_verdicts": role_verdicts, "unresolved": unresolved,
            "escalation": escalation}, ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "glossary.json").write_text(json.dumps(
            {"glossary_version": GLOSSARY_VERSION, "target_lang": target_lang,
             "market": market, "source_sha": text_sha(source), "source_chars": len(source),
             "terms": glossary, "dropped": (glossary_obj or {}).get("dropped") or [],
             "notes": (glossary_obj or {}).get("notes") or ""},
            ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "glossary.md").write_text(
            render_glossary_md(glossary_obj or {"terms": glossary, "count": len(glossary)},
                               {"source_lang": a.source_lang, "target_lang": target_lang,
                                "market": market}), encoding="utf-8")
        (outdir / "translation.md").write_text(translation_md, encoding="utf-8")
        # `translation.json` 也落一份：这样 `check` / `glossary_check` 这些**纯本地**
        # 子命令能直接拿 `run` 的产物重跑闸门，不必重跑任何调用。
        # 事故（本包自测时发现）：run 只落 translation.md，于是想零成本复查一次
        # 数字/术语都做不到 —— 而"改完再核一遍"正是这两个子命令存在的理由。
        (outdir / "translation.json").write_text(json.dumps({
            "translation": final_tr or {"body": final_body, "pairs": []},
            "market": market, "target_lang": target_lang, "source_lang": a.source_lang,
            "source_sha": text_sha(source), "glossary_sha": json_sha(glossary),
            "rounds_used": len(rounds_trace),
            "final_verdict": final_verdict,
            "unresolved": len(unresolved)}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        (outdir / "REPORT.md").write_text(report_md, encoding="utf-8")
        (outdir / "run.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        (outdir / "log.json").write_text(
            json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        append_log(outdir, log)
        sys.stderr.write("目录产物：{}（final.md / final.json / glossary.json / "
                         "translation.md / REPORT.md / log.json / {})\n".format(
                             outdir, STATE_NAME))
    if gate_problems:
        _gate_stderr("定稿", gate_gates)
    if unresolved:
        sys.stderr.write(_red("!! 有 {} 条未决项（轮次用尽仍有席位打回/否决）：\n".format(
            len(unresolved))))
        for u in unresolved:
            sys.stderr.write("   · 【{}】第 {} 轮 {}：{}\n".format(
                u["role_name"], u["round"], u.get("verdict_label"), u["why"]))
        sys.stderr.write("   **分歧如实报出，不假装谈拢**；产出仍已落盘（带未决项）。\n")
    _emit(a, result, report_md, ok=not gate_problems and not unresolved)
    if unresolved:
        return EXIT_UNRESOLVED
    return EXIT_GATE if gate_problems else EXIT_OK


# ===========================================================================
# 子命令：check（对一份已有译文跑**全部本地闸门**，零成本）
#
# 为什么需要它：`glossary_check` 只管术语一致性。而"数字丢了没有"、
# "有没有占位符残留"、"译文长度对不对"这些同样是纯本地判定 ——
# 没有理由为了重跑它们而再花一次模型调用。改完译文之后反复跑的就是这个命令。
# ===========================================================================

def _measure_problems(mrep):
    """把数字/单位报告翻译成人能直接处置的几条问题。

    ⚠️ 「丢了」与「没本地化」必须**分开报**（本包自测时发现的措辞问题）：
    两者的处置完全不同 —— 丢数字是"漏译，重译"；没本地化是"换算没做，改这一处"。
    混成一句"数字/单位丢失 N 处"，人得自己去 JSON 里分辨，等于没报。
    区分依据：`number_as_source` 为真说明原数字还在，只是没按目标市场换算。
    """
    problems = []
    lost = [m for m in (mrep.get("missing") or []) if not m.get("number_as_source")]
    unlocal = [m for m in (mrep.get("missing") or []) if m.get("number_as_source")]
    if lost:
        problems.append("数字整条丢失 {} 处：{}".format(
            len(lost), "、".join("{} {}".format(m.get("number"), m.get("unit") or "")
                                for m in lost[:5])))
    if unlocal:
        exp = (unlocal[0].get("expected") or {})
        problems.append("数字还在但没按目标市场换算 {} 处（例如 `{} {}` 期望约 {} {}）：{}"
                        .format(len(unlocal), unlocal[0].get("number"),
                                unlocal[0].get("unit") or "",
                                round(exp.get("value") or 0, 3), exp.get("unit") or "?",
                                "、".join("{} {}".format(m.get("number"),
                                                        m.get("unit") or "")
                                          for m in unlocal[:5])))
    if mrep.get("wrong_conversion"):
        problems.append("单位换算不对 {} 处".format(mrep["wrong_count"]))
    return problems


def run_check(a):
    """纯本地：对一份已有译文跑全部确定性闸门。**不调模型、不花钱**。"""
    source = read_source(a)
    market = check_market(a.market)
    target_lang = check_lang(a.target_lang)
    glossary = check_glossary_opt(a, source, target_lang)
    translation = load_translation_file(a.translation)
    body = translation.get("body") or ""
    pairs = translation.get("pairs") or []

    problems, gates = [], {}

    # 闸门二/三：占位符 + 照抄提示词示例（先查，拦下来再谈别的）
    p_out, d_out = text_gates(body, "译文", material=source, market=market, side="output")
    problems += p_out
    gates.update(d_out)
    # 闸门一（材料侧）：源文照查
    p_mat, d_mat = text_gates(source, "源文", market=market, side="material")
    gates["source_side"] = d_mat
    if p_mat:
        problems.append("源语言侧命中 {} 处（材料侧照查）".format(len(p_mat)))

    # 闸门五：术语一致性（给了 --glossary 才查）
    if glossary is not None:
        trep = glossary_consistency(source, body, glossary.get("terms") or [],
                                    pairs=pairs, target_lang=target_lang)
        gates["terminology"] = trep
        if trep["inconsistent_count"]:
            problems.append("术语不一致 {} 条：{}".format(
                trep["inconsistent_count"],
                "、".join("{}（应为 {}）".format(i["source_term"], i["canonical"])
                          for i in trep["inconsistent"][:4])))
    else:
        gates["terminology"] = {"checked_terms": 0, "inconsistent_count": 0,
                               "inconsistent": [], "note": "没给 --glossary，跳过术语核对"}

    # 闸门六：数字与单位保全（**本包核心，且这条以前只有花钱的路径才查得到**）
    mrep = measure_report(source, body, market, pairs=pairs,
                          fx_rate=getattr(a, "fx_rate", None))
    gates["measures"] = mrep
    problems += _measure_problems(mrep)

    # 闸门四：锚点到句子（逐句对齐的源句必须能在源文里找到）
    src_pairs = [{"quote": p.get("source")} for p in pairs]
    good, bad, astat = anchor_issues(src_pairs, source, label="源文")
    gates["anchor"] = astat
    if astat["total"] and astat["unanchored_ratio"] > ANCHOR_MAX_MISS:
        problems.append("逐句对齐的源句有 {}/{} 条在源文里找不到（未锚定率 {:.0%} > "
                        "{:.0%}）—— 判为定位失败".format(
                            astat["unanchored"], astat["total"],
                            astat["unanchored_ratio"], ANCHOR_MAX_MISS))
    for b in bad[:3]:
        problems.append("编造引文已剔出：{}".format(
            str(b.get("unanchored_reason") or b.get("quote"))[:100]))

    # 源文句子覆盖（防漏译整句）
    missing_sents = [s for s in split_sentences(source)
                     if not any(_norm_anchor(s) and (
                         _norm_anchor(s) in _norm_anchor(p.get("source"))
                         or _norm_anchor(p.get("source")) in _norm_anchor(s))
                         for p in pairs)]
    if missing_sents:
        gates["missing_sentences"] = [s[:80] for s in missing_sents]
        problems.append("源文有 {} 句没有进逐句对照（可能漏译）".format(len(missing_sents)))

    # 篇幅（软提示，不拦）：只报不拦，理由是"短一点"在不少场景是合理选择
    exp = int(round(len(source) * max(0.3, min(4.0, getattr(
        a, "target_multiple", DEFAULT_TARGET_MULTIPLE)))))
    gates["length"] = {"source_chars": len(source), "target_chars": len(body),
                       "expected": exp, "target_multiple": getattr(
                           a, "target_multiple", DEFAULT_TARGET_MULTIPLE)}
    rc = EXIT_GATE if problems else EXIT_OK
    result = {"mode": "check", "role_version": ROLE_VERSION,
              "glossary_version": GLOSSARY_VERSION, "unit_rules": UNIT_RULES_VERSION,
              "source_lang": a.source_lang, "target_lang": target_lang, "market": market,
              "target_market_name": (MARKETS.get(market) or {})["name"],
              "source_sha": text_sha(source), "source_chars": len(source),
              "chars": len(body), "pairs": len(pairs),
              "glossary": ({"count": (glossary or {}).get("count", 0),
                            "path": (glossary or {}).get("path")} if glossary else None),
              "gates": gates, "problems": problems, "gate_failed": bool(problems),
              "paid": False,
              "note": "本子命令**纯本地零成本**：不调模型、不联网，判定可复现"}
    md = ["# 本地闸门自检（纯本地，零成本）", "",
          "- 源文 {} 字符 → 译文 {} 字符（目标约 {} 字符）".format(
              len(source), len(body), exp),
          "- 逐句对照 {} 组；术语表 {} 条".format(
              len(pairs), (glossary or {}).get("count", 0)),
          "- 目标市场：{}".format((MARKETS.get(market) or {})["name"]),
          "- 裁决：**{}**".format("有硬闸门命中" if problems else "全部通过"),
          "", "## 命中明细", ""]
    md += ["- " + p for p in problems] if problems else ["（无）"]
    md += ["", "## 术语一致性", ""]
    tm = gates.get("terminology") or {}
    md.append("- 核对 {} 条；不一致 {} 条".format(
        tm.get("checked_terms", 0), tm.get("inconsistent_count", 0)))
    for inc in (tm.get("inconsistent") or []):
        md.append("- **{}** 应为 `{}`（{} 处出现，{} 处命中）".format(
            inc["source_term"], inc["canonical"], inc["occurrences"], inc["hits"]))
    md += ["", "## 数字与单位", ""]
    ms = gates.get("measures") or {}
    md.append("- 缺 {} 处；换算不对 {} 处".format(
        ms.get("missing_count", 0), ms.get("wrong_count", 0)))
    for mi in (ms.get("missing") or []):
        if mi.get("number_as_source"):
            ex = mi.get("expected") or {}
            md.append("- **没本地化**：原数字 `{}`（{}）还在，但没用目标市场的单位"
                      "（期望约 {} {}，{}）".format(
                          mi.get("number"), mi.get("unit") or "无单位",
                          round(ex.get("value") or 0, 3), ex.get("unit") or "?",
                          ex.get("why") or ""))
        else:
            md.append("- **丢了**：`{}`（{}）　上下文：{}".format(
                mi.get("number"), mi.get("unit") or "无单位",
                str(mi.get("context") or "")[:70]))
    for mi in (ms.get("wrong_conversion") or []):
        ex = mi.get("expected") or {}
        md.append("- **换算不对**：`{} {}` 期望约 {} {}（{}）".format(
            mi.get("number"), mi.get("unit") or "", round(ex.get("value") or 0, 3),
            ex.get("unit"), ex.get("why")))
    md_text = "\n".join(md) + "\n"
    if getattr(a, "out", None):
        Path(a.out).write_text(md_text, encoding="utf-8")
    if problems:
        _gate_stderr("本地闸门", gates)
    _emit(a, md_text, result, ok=not problems)
    return rc


# ===========================================================================
# 子命令：log
# ===========================================================================

def run_log(a):
    outdir = ensure_outside_pkg(a.outdir, "读日志的目录", "localize-out")
    p = Path(outdir) / "log.json"
    if not p.exists():
        raise UsageError("这个目录里没有 log.json（要先跑 run --outdir {}）：{}".format(
            outdir, outdir))
    try:
        log = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("log.json 读不了：{}".format(exc))
    entries = log.get("entries") or []
    if _json_out({"outdir": str(outdir), "entries": len(entries), "log": log}, a):
        return EXIT_OK
    L = ["# 出海本地化小组 · 全过程记录", "",
         "目录：`{}`；条目 {} 条".format(outdir, len(entries)), ""]
    for e in entries:
        L.append("## 第 {} 轮 · {} · {}".format(e.get("round"), e.get("role_name"),
                                               e.get("action")))
        L.append("- {}".format(e.get("what")))
        if e.get("detail"):
            L.append("- 细节：`{}`".format(
                json.dumps(e["detail"], ensure_ascii=False)[:500]))
        for q in e.get("quotes") or []:
            L.append("- 引用：`{}`".format(q))
        L.append("- 时间：{}".format(e.get("at")))
        L.append("")
    text = "\n".join(L) + "\n"
    sys.stdout.write(text)
    return EXIT_OK


# ===========================================================================
# 子命令：cost
# ===========================================================================

def run_cost(a):
    source = ""
    if getattr(a, "from_result", None):
        p = Path(a.from_result)
        if not p.exists():
            raise UsageError("找不到结果文件：{}".format(p))
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UsageError("结果文件不是合法 JSON：{}".format(exc))
        usage = obj.get("usage") or obj.get("usage_calls")
        if isinstance(usage, list):
            tot = new_usage()
            for c in usage:
                add_usage(tot, c.get("usage") or {})
            usage = tot
        if not isinstance(usage, dict):
            raise UsageError("结果文件里没有 usage：{}".format(p))
        rec = compute_cost(int(usage.get("prompt_tokens") or 0),
                           int(usage.get("completion_tokens") or 0),
                           a.price_in, a.price_out)
        rec["source"] = str(p)
        rec["calls"] = len(obj.get("usage_calls") or []) if isinstance(
            obj.get("usage_calls"), list) else None
        if _json_out(rec, a):
            return EXIT_OK
        sys.stdout.write("实际 token：{}\n".format(fmt_cost(rec)))
        return EXIT_OK
    if getattr(a, "text", None):
        source = a.text
    elif getattr(a, "file", None):
        source = read_text(a.file, "源文")
    else:
        raise UsageError("cost 需要 --file / --text（按材料估），"
                         "或 --from-result（按真实 usage 算）")
    rounds = max(0, int(getattr(a, "rounds", DEFAULT_ROUNDS) or 0))
    calls = estimate_calls(source, rounds=rounds)
    tin = sum(c["tokens_in"] for c in calls)
    tout = sum(c["tokens_out"] for c in calls)
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rec.update({"mode": "estimate", "source_chars": len(source), "rounds": rounds,
                "calls": calls,
                "call_count": sum(c["calls"] for c in calls),
                "note": "字符 → token 用同族实测标定（入 1 token ≈ {:.2f} 字符，"
                        "出 1 字符 ≈ {} token）；**这是估算，不是账单**。"
                        "金额必须由你给单价 —— 本包不编价。".format(
                            CHARS_PER_TOKEN_IN, TOKENS_PER_CHAR_OUT)})
    if a.budget is not None:
        _check_budget_opts(a)
        rec["budget"] = a.budget
        if rec.get("points") is not None:
            rec["budget_ok"] = rec["points"] <= a.budget
            if not rec["budget_ok"]:
                # ⚠️ `--json` 下 `ok` 必须与退出码一致：退出码非 0 就是 ok=false。
                # 本包自测时抓到过这里只写 `ok:true`（因为走了"成功出口"），
                # 于是"预算超了"这件事在 JSON 里读起来像成功 —— 契约被破坏。
                msg = ("预估 {:.4f} 点已超过 --budget {:.4f}（跑之前就该发现）"
                       .format(rec["points"], a.budget))
                rec["error"] = {"kind": "budget", "message": msg,
                                "detail": {"points": rec["points"], "budget": a.budget}}
                sys.stderr.write(_red("!! " + msg + "\n"))
                if _json_out(rec, a, ok=False):
                    return EXIT_BUDGET
                sys.stdout.write(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
                return EXIT_BUDGET
    if _json_out(rec, a):
        return EXIT_OK
    L = ["# 报价（估算，不是账单）", "",
         "- 源文字符：{}".format(len(source)),
         "- 轮次上限：{}".format(rounds),
         "- 预计调用：**{} 次**".format(rec["call_count"]),
         "- 预计 token：{}".format(fmt_cost(rec)), "",
         "| 阶段 | 调用 | 入 token | 出 token | 说明 |", "|---|---|---|---|---|"]
    for c in calls:
        L.append("| {} | {} | {} | {} | {} |".format(c["stage"], c["calls"],
                                                    c["tokens_in"], c["tokens_out"],
                                                    c["note"]))
    L += ["", rec["note"]]
    if a.budget is not None:
        L += ["", "- 预算上限：{:.4f} 点；{}".format(
            a.budget, "在预算内" if rec.get("budget_ok") else "**超预算**")]
    text = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return EXIT_OK


# ===========================================================================
# 子命令：models
# ===========================================================================

def run_models(a):
    key = a7w.load_key(getattr(a, "key", None), required=False)
    req = urllib.request.Request(MODELS_URL, method="GET")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        raise LcError("模型清单取不到（HTTP {}）：{}".format(
            exc.code, exc.read().decode("utf-8", "replace")[:200]))
    except (urllib.error.URLError, OSError) as exc:
        raise LcError("网络错误：{}（确认能访问 {}）".format(exc, MODELS_URL))
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(payload, dict) and "choices" not in payload and isinstance(
            payload.get("data"), dict):
        data = payload["data"].get("data") or payload["data"]
    rows = data if isinstance(data, list) else []
    if getattr(a, "type", "text") not in ("all", None, ""):
        want = a.type
        filtered = []
        for m in rows:
            if not isinstance(m, dict):
                continue
            t = str(m.get("type") or m.get("category") or "text")
            if want in t:
                filtered.append(m)
        rows = filtered or rows
    if _json_out({"models_url": MODELS_URL, "count": len(rows),
                  "note": "成功响应**不带 `code`**；`deepseek-chat` 实测可用但可能不在这个"
                          "列表里 —— 「列表里没有」不等于「不能用」",
                  "models": rows}, a):
        return EXIT_OK
    L = ["# api.a7w.cn 在架模型", "", "共 {} 条（类型过滤：{}）".format(
        len(rows), getattr(a, "type", "text")), ""]
    for m in rows[:200]:
        if isinstance(m, dict):
            L.append("- `{}`".format(m.get("id") or m.get("model") or m))
        else:
            L.append("- `{}`".format(m))
    L += ["", "> `deepseek-chat` 实测可用（路由到 `deepseek-flash`），"
              "但它**不在**这个列表里 —— 「列表里没有」不等于「不能用」。"]
    text = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return EXIT_OK


# ===========================================================================
# 输出与 JSON 契约
#
# 契约（只在 `--json` 下生效，与同族完全一致）：
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 {"ok": true, "data": [...]}
#   · 失败：stdout 只有一个 JSON 信封
#     {"ok": false, "exit": <码>, "error": {"kind": …, "message": …, "detail": …}}
#   · `--json` 写在子命令**前面或后面都可以**
#   · stdout 只有一个 JSON（进度与人读文案都走 stderr）
# ===========================================================================

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}
_KIND_BY_EXIT = {EXIT_INTERNAL: "internal", EXIT_USAGE: "usage", EXIT_GATE: "gate",
                 EXIT_CALL: "call", EXIT_BUDGET: "budget", EXIT_UNRESOLVED: "unresolved",
                 EXIT_INTERRUPT: "interrupt"}


def _json_payload(obj, ok=True):
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        out.update(obj)
        return out
    return {"ok": bool(ok), "data": obj}


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_write(text):
    """把 JSON 文本写到**真 stdout**并记账。"""
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
    return True


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
    """`--json` 模式的失败出口：只在本次还没输出过 JSON 结果时补信封。"""
    if _JSON["emitted"] or not _json_want(a):
        return
    err = {"kind": kind or _KIND_BY_EXIT.get(rc, "call"),
           "message": message or "命令以退出码 {} 结束（人读原因见 stderr）".format(rc)}
    if detail is not None:
        err["detail"] = detail
    _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                           ensure_ascii=False, indent=1))


def _json_internal(exc):
    """未预料异常的兜底信封 —— **报 bug，不藏 bug**。

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr，
    这里不重复、也不吞。`detail.where` 只取**最后一帧**的文件名:行号，整条栈不进 JSON。
    如果本次已经吐过结果，就**不再补信封**（守住"stdout 永远只有一个 JSON"这条不变量）。
    """
    if _JSON["emitted"]:
        return
    tb = sys.exc_info()[2]
    frames = traceback.extract_tb(tb) if tb else []
    detail = {"type": type(exc).__name__}
    if frames:
        last = frames[-1]
        detail["where"] = "{}:{}".format(os.path.basename(last.filename), last.lineno)
    err = {"kind": "internal",
           "message": "{}: {}".format(type(exc).__name__, exc),
           "detail": detail}
    _json_write(json.dumps({"ok": False, "exit": EXIT_INTERNAL, "error": err},
                           ensure_ascii=False, indent=1))


def _fail(rc, kind, message, detail=None):
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


def _emit(a, md_text, json_obj=None, ok=True):
    """统一出口：`--json` 下只吐 JSON（人读文案走 stderr），否则吐人读文案。

    顺序与不变量：
      · `--json`：stdout **只有一个** JSON（结果对象）；md 文案原样走 stderr；
        非 `--json` 时才可能写 `--out` 文件或 stdout。
        ⚠️ 先判 `--json` 再写文件，否则 `--json --out x.md` 会把 md 也写进 stdout。
    """
    body = _text(md_text)
    if _json_out(json_obj if json_obj is not None else {}, a, ok=ok):
        if body:
            sys.stderr.write(body if body.endswith("\n") else body + "\n")
        return True
    if getattr(a, "out", None):
        try:
            Path(a.out).write_text(body if body.endswith("\n") else body + "\n",
                                   encoding="utf-8")
            sys.stderr.write("已写入 {}\n".format(a.out))
        except OSError as exc:
            sys.stderr.write("写不进去（{}）：{}\n".format(a.out, exc))
    if body:
        sys.stdout.write(body if body.endswith("\n") else body + "\n")
    return False


def _gate_stderr(label, gates):
    """硬闸门命中时的 stderr 汇总（标红 + 逐条原因 + 提示退出码）。"""
    lines = ["", _red("!! {} 命中硬闸门：".format(label))]
    for line in gate_summary_lines(gates):
        lines.append("   " + line)
    lines.append(_red("   退出码 3（硬闸门；可直接进 CI）"))
    sys.stderr.write("\n".join(lines) + "\n")


def _print_prompt_preview(prompt, system, title):
    sys.stdout.write("=" * 72 + "\n")
    sys.stdout.write("【{}】将发送的提示词（--dry-run，没有花钱）\n".format(title))
    sys.stdout.write("=" * 72 + "\n")
    if system:
        sys.stdout.write("[system]\n{}\n\n".format(system))
    sys.stdout.write("[user]\n{}\n".format(prompt))


# ===========================================================================
# 入口
# ===========================================================================

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py cost --file x --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p, out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=8192, dest="max_tokens",
                   help="最大输出 token，默认 8192（长篇材料别低于 4096）")
    p.add_argument("--key", help="临时指定 A7W API Key")
    if out:
        p.add_argument("--out", help="把结果写到这个文件")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_cost_opts(p):
    p.add_argument("--price-in", type=float, dest="price_in",
                   help="输入单价，单位「点/百万 token」。不给我就不给金额（不编价）")
    p.add_argument("--price-out", type=float, dest="price_out",
                   help="输出单价，单位「点/百万 token」")
    p.add_argument("--budget", type=float,
                   help="预算上限（点）。超了就地中止，退出码 5；用 --budget 必须给单价")


def _add_source_opts(p, required=True):
    p.add_argument("--file", required=required, help="源文文件（.md / .txt，UTF-8）")
    p.add_argument("--text", help="或直接给源文正文（与 --file 同时给时以 --text 为准）")
    p.add_argument("--source-lang", default=DEFAULT_SOURCE_LANG, dest="source_lang",
                   help="源语言代码，默认 {}（可选：{}）".format(
                       DEFAULT_SOURCE_LANG, " / ".join(LANG_CHOICES)))
    p.add_argument("--target-lang", default=DEFAULT_TARGET_LANG, dest="target_lang",
                   help="目标语言代码，默认 {}（可选：{}）".format(
                       DEFAULT_TARGET_LANG, " / ".join(LANG_CHOICES)))
    p.add_argument("--market", default=DEFAULT_MARKET, choices=MARKET_CHOICES,
                   help="目标市场，默认 {}（决定文化规则包与合规法域）".format(DEFAULT_MARKET))
    p.add_argument("--glossary", help="术语表 JSON（glossary --json --out 的产物）；"
                                     "会核对源文摘要与目标语言，对不上直接拒绝复用")
    p.add_argument("--fx-rate", type=float, dest="fx_rate",
                   help="人民币→目标货币汇率（**外部输入**）。不给就不换算货币，只查数字在不在")


def _add_outdir_opts(p, default=None):
    p.add_argument("--outdir", default=default,
                   help="目录产物落这里（**必须在包外**，落在包内退出码 2）")
    p.add_argument("--force", action="store_true", help="忽略断点文件从头重跑")


def _parser(**kw):
    """统一构造 ArgumentParser，**关掉长选项前缀缩写**（`allow_abbrev=False`）。

    事故复盘（同族自测时踩到的真实坑，不是理论问题）：
    子命令上同时有 `--outdir` 时，用户写 `--out report.json` 想输出结果文件，
    argparse 默认允许**前缀缩写**，于是 `--out` 被当成 `--outdir` 的缩写匹配上了 ——
    结果：产出目录变成了一个叫 `report.json` 的目录，而且**不报任何错**。
    这类"参数被静默吃成另一个参数"的错误最难查，因为命令行看起来是对的。
    关掉缩写后，`--out` 直接报 unrecognized arguments（退出码 2），一眼就能看出问题。
    """
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def _main(argv_eff):
    ap = _parser(
        prog="run.py",
        description="三剪客 · 出海本地化小组 —— L3 跨语言多智能体互审"
                    "（译审 / 文化适配 / 术语官 / 合规，走 api.a7w.cn 的 OpenAI 兼容端点）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出四个角色的职权、产出物与否决权（零成本）")
    _add_json(p)
    p.add_argument("--out", help="把职权表写到这个文件")
    p.set_defaults(func=run_roles)

    p = sub.add_parser("glossary", help="从源文抽出术语表（源词 → 目标语规范译法）")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_outdir_opts(p)
    p.set_defaults(func=run_glossary)

    p = sub.add_parser("translate", help="译审出译文 + 逐句回译对照")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_outdir_opts(p)
    p.add_argument("--target-multiple", type=float, default=DEFAULT_TARGET_MULTIPLE,
                   dest="target_multiple",
                   help="译文目标长度 ≈ 源文长度 × 该系数，默认 {}"
                        "（中译英 ≈ 1.0，英译中 ≈ 1.6）".format(DEFAULT_TARGET_MULTIPLE))
    p.set_defaults(func=run_translate)

    p = sub.add_parser("culture", help="文化适配出风险清单（**能否决**）")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_outdir_opts(p)
    p.add_argument("--translation", required=True,
                   help="译文 JSON（translate --json --out 的产物）")
    p.set_defaults(func=run_culture)

    p = sub.add_parser("glossary_check", help="术语一致性核对（**能打回**；纯本地零成本）")
    _add_source_opts(p)
    _add_json(p)
    p.add_argument("--translation", required=True, help="译文 JSON")
    p.add_argument("--out", help="把核对结果写到这个文件")
    p.add_argument("--key", help="（本子命令用不到 Key，留着是为了命令行统一）")
    p.set_defaults(func=run_glossary_check)

    p = sub.add_parser("check", help="对一份已有译文跑**全部本地闸门**（纯本地零成本）")
    _add_source_opts(p)
    _add_json(p)
    p.add_argument("--translation", required=True, help="译文 JSON")
    p.add_argument("--target-multiple", type=float, default=DEFAULT_TARGET_MULTIPLE,
                   dest="target_multiple", help="目标长度系数（只用于报出「目标字符数」）")
    p.add_argument("--out", help="把自检结果写到这个文件")
    p.add_argument("--key", help="（本子命令用不到 Key，留着是为了命令行统一）")
    p.set_defaults(func=run_check)

    p = sub.add_parser("compliance", help="目标市场合规裁决（**可否决 / 一票否决**）")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_outdir_opts(p)
    p.add_argument("--translation", required=True, help="译文 JSON")
    p.set_defaults(func=run_compliance)

    p = sub.add_parser("run", help="一条命令跑完整协作：四席互审 + 轮次上限 + 明确出口")
    _add_source_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    p.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS,
                   help="最多几轮（打回就重译一轮），默认 {}（上限 5）".format(DEFAULT_ROUNDS))
    p.add_argument("--target-multiple", type=float, default=DEFAULT_TARGET_MULTIPLE,
                   dest="target_multiple", help="译文目标长度 ≈ 源文 × 该系数")
    _add_outdir_opts(p, default=str(Path(os.environ.get("TEMP") or ".") / "localize-out"))
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="读回全过程：谁在第几轮打回了什么、引用了哪句")
    p.add_argument("--outdir", required=True, help="run 的 --outdir")
    _add_json(p)
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：这一趟大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份源文估")
    p.add_argument("--text", help="或直接给文本")
    p.add_argument("--from-result", dest="from_result",
                   help="读一份 run/translate 的 --json --out 结果，按**真实 usage** 算")
    p.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="按几轮估")
    _add_cost_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把报价写到这个文件")
    p.set_defaults(func=run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.add_argument("--out", help="把清单写到这个文件")
    p.set_defaults(func=run_models)

    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        # argparse 的参数错（退出码 2）也要给信封；--help（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    # 补默认值（子命令用 set_defaults 声明过的字段在各命令里都能读到）
    for k, v in (("json", False), ("out", None), ("dry_run", False), ("no_json_mode", False),
                 ("budget", None), ("price_in", None), ("price_out", None), ("force", False),
                 ("rounds", DEFAULT_ROUNDS), ("target_multiple", DEFAULT_TARGET_MULTIPLE),                 ("source_lang", DEFAULT_SOURCE_LANG), ("target_lang", DEFAULT_TARGET_LANG),
                 ("market", DEFAULT_MARKET), ("glossary", None), ("fx_rate", None),
                 ("file", None), ("text", None), ("outdir", None), ("key", None),
                 ("translation", None), ("from_result", None), ("type", "text"),
                 ("temperature", 0.7), ("max_tokens", 8192), ("model", DEFAULT_MODEL)):
        if not hasattr(a, k):
            setattr(a, k, v)

    kind, msg, detail = None, None, None
    try:
        rc = a.func(a)
    except DryRunStop as exc:
        _print_prompt_preview(exc.prompt, exc.system, exc.stage)
        return EXIT_OK
    except IsolationBreach as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = EXIT_GATE, "gate", str(exc)
    except LcError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = exc.exit_code, _KIND_BY_EXIT.get(exc.exit_code, "call"), str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = EXIT_CALL, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("已中断\n")
        rc, kind, msg = EXIT_INTERRUPT, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        _json_fail(rc, reason.get("kind") or kind, reason.get("message") or msg,
                   reason.get("detail"), a)
    return rc


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与以前完全一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被重定向吞掉）
    _JSON["want"] = "--json" in argv_eff  # argparse 失败时还没有 a，先按命令行判断
    _JSON["emitted"] = False
    _JSON["reason"] = None
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise                                 # 非 --json：原样冒泡
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return EXIT_INTERNAL


def cli():
    """stdout/stderr 的编码收口。"""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    return main()


if __name__ == "__main__":
    sys.exit(cli())
