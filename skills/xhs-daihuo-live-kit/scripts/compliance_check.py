#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小红书带货文案 · 离线合规自检（v1.1.0）。

按五类基础规则 + 可选类目规则扫描文本：极限词、医疗功效、金融收益承诺、
站外导流、平台敏感操作。纯离线运行，仅使用 Python 标准库，不联网、不读取凭据；
默认只读，仅当显式传入 --out 时才写文件。

本工具是启发式自检，词表来自公开经验整理，不等于平台官方审核规则，也不构成法律意见。
高风险类目（医疗、保健、食品、金融、母婴、特殊化妆品）必须人工复核。

用法：
    python3 compliance_check.py --file note.md
    python3 compliance_check.py --text "全网最低价，根治敏感肌"
    python3 compliance_check.py --file script.txt --category cosmetics
    python3 compliance_check.py --file note.md --format json --strict
    python3 compliance_check.py --file note.md --format csv --out report.csv
    python3 compliance_check.py --file note.md --rules my-terms.json
    python3 compliance_check.py --list-rules
    python3 compliance_check.py --explain

也可作为库使用：

    from compliance_check import scan, summarize
    findings = scan("全网最低价", categories=["cosmetics"])
"""

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

LEVEL_ORDER = {"low": 1, "medium": 2, "high": 3}
LEVEL_LABEL = {"low": "低", "medium": "中", "high": "高"}

DISCLAIMER = "启发式自检，不等于平台官方审核规则，不构成法律意见。"

# --------------------------------------------------------------------------
# 基础规则：(类别, 等级, 词, 建议)
# --------------------------------------------------------------------------
BASE_TERMS = [
    # --- 极限词 / 绝对化用语 ---
    ("极限词", "high", "最好", "换成可验证的具体事实"),
    ("极限词", "high", "最佳", "换成可验证的具体事实"),
    ("极限词", "high", "最强", "换成可验证的具体事实"),
    ("极限词", "high", "最便宜", "改为「我对比过的几家里这个价格更低」"),
    ("极限词", "high", "最低价", "改为「我对比过的几家里这个价格更低」"),
    ("极限词", "high", "全网最低", "删除绝对化比较，改为具体对比范围"),
    ("极限词", "high", "史上最低", "删除绝对化比较"),
    ("极限词", "high", "最有效", "改为主观感受或删除"),
    ("极限词", "high", "第一", "删除排名类表述"),
    ("极限词", "high", "排名第一", "删除排名类表述"),
    ("极限词", "high", "销量第一", "删除排名类表述，或补充可核实来源"),
    ("极限词", "high", "领先品牌", "删除无根据背书"),
    ("极限词", "high", "世界级", "删除无根据背书"),
    ("极限词", "high", "国家级", "删除无根据背书"),
    ("极限词", "high", "顶级", "删除无根据背书"),
    ("极限词", "high", "顶尖", "删除无根据背书"),
    ("极限词", "high", "极致", "删除绝对化用语"),
    ("极限词", "high", "唯一", "删除排他性表述"),
    ("极限词", "high", "独家", "删除排他性表述，或补充真实授权依据"),
    ("极限词", "high", "绝对", "删除绝对化用语"),
    ("极限词", "high", "100%", "改为具体比例或删除"),
    ("极限词", "high", "百分百", "改为具体比例或删除"),
    ("极限词", "high", "永久", "改为「正常使用下可用 x 年」或删除"),
    ("极限词", "high", "终身", "改为具体保障期限"),
    ("极限词", "high", "一劳永逸", "删除绝对化表述"),
    ("极限词", "high", "绝无仅有", "删除绝对化表述"),
    ("极限词", "high", "空前绝后", "删除绝对化表述"),
    ("极限词", "high", "万能", "删除绝对化表述"),
    ("极限词", "high", "包治", "删除绝对化表述"),
    ("极限词", "medium", "超值", "促销感过强，改为具体价格或配置对比"),
    ("极限词", "medium", "秒杀", "需有真实活动依据，否则删除"),
    ("极限词", "medium", "全网", "泛指全平台易被判绝对化，改为具体范围"),
    ("极限词", "low", "最", "「最」字需逐条确认语境，避免绝对化"),
    ("极限词", "low", "神器", "改为具体功能描述"),
    ("极限词", "low", "必买", "改为适用人群描述"),

    # --- 医疗 / 功效 ---
    ("医疗功效", "high", "治疗", "删除疾病治疗类表述"),
    ("医疗功效", "high", "治愈", "删除疾病治疗类表述"),
    ("医疗功效", "high", "根治", "删除疾病治疗类表述，改为主观使用感受"),
    ("医疗功效", "high", "药到病除", "删除疾病治疗类表述"),
    ("医疗功效", "high", "疗效", "删除功效承诺"),
    ("医疗功效", "high", "药用", "删除医疗属性表述"),
    ("医疗功效", "high", "医用", "删除医疗属性表述（械字号需按注册证范围表述）"),
    ("医疗功效", "high", "消炎", "删除症状类表述"),
    ("医疗功效", "high", "杀菌", "改为「清洁后不易留味」等非功效表述"),
    ("医疗功效", "high", "抑菌", "需消字号资质；否则改为清洁类表述"),
    ("医疗功效", "high", "抗癌", "删除疾病相关表述"),
    ("医疗功效", "high", "抗肿瘤", "删除疾病相关表述"),
    ("医疗功效", "high", "降血压", "删除疾病相关表述"),
    ("医疗功效", "high", "降血糖", "删除疾病相关表述"),
    ("医疗功效", "high", "降血脂", "删除疾病相关表述"),
    ("医疗功效", "high", "镇痛", "删除疾病相关表述"),
    ("医疗功效", "high", "无副作用", "删除安全性承诺"),
    ("医疗功效", "high", "无添加", "需有检测依据，否则删除"),
    ("医疗功效", "high", "美白", "属特殊化妆品功效，需注册证；否则改为使用感受"),
    ("医疗功效", "high", "祛斑", "属特殊化妆品功效，需注册证；否则删除"),
    ("医疗功效", "high", "祛痘", "改为主观使用感受，不作功效承诺"),
    ("医疗功效", "high", "生发", "删除功效承诺"),
    ("医疗功效", "high", "防脱", "属特殊化妆品功效，需注册证；否则删除"),
    ("医疗功效", "high", "减肥", "删除功效承诺"),
    ("医疗功效", "high", "瘦身", "删除功效承诺"),
    ("医疗功效", "high", "丰胸", "删除功效承诺"),
    ("医疗功效", "high", "增高", "删除功效承诺"),
    ("医疗功效", "high", "排毒", "删除功效承诺"),
    ("医疗功效", "high", "提高免疫力", "删除保健功效承诺"),
    ("医疗功效", "high", "增强免疫力", "删除保健功效承诺"),
    ("医疗功效", "medium", "修复", "改为「用后觉得没那么干」等感受表述"),
    ("医疗功效", "medium", "敏感肌可用", "需有测试依据，否则改为个人感受"),
    ("医疗功效", "medium", "抗老", "改为使用感受描述，不作功效承诺"),
    ("医疗功效", "medium", "淡纹", "改为使用感受描述，不作功效承诺"),
    ("医疗功效", "medium", "除螨", "需检测依据，否则删除"),

    # --- 金融 / 收益承诺 ---
    ("金融收益", "high", "稳赚", "删除收益承诺"),
    ("金融收益", "high", "稳赚不赔", "删除收益承诺"),
    ("金融收益", "high", "包赚", "删除收益承诺"),
    ("金融收益", "high", "躺赚", "删除收益承诺"),
    ("金融收益", "high", "暴利", "删除收益承诺"),
    ("金融收益", "high", "保本", "删除风险承诺"),
    ("金融收益", "high", "零风险", "删除风险承诺"),
    ("金融收益", "high", "无风险", "删除风险承诺"),
    ("金融收益", "high", "日入过万", "删除收益预期"),
    ("金融收益", "high", "月入十万", "删除收益预期"),
    ("金融收益", "high", "投资回报", "删除收益预期表述"),
    ("金融收益", "high", "包过", "删除结果承诺"),
    ("金融收益", "high", "通过率", "删除结果承诺，需真实可核实数据"),

    # --- 站外导流 ---
    ("站外导流", "high", "微信", "删除站外联系方式，交易只在平台内完成"),
    ("站外导流", "high", "威信", "删除站外联系方式"),
    ("站外导流", "high", "V信", "删除站外联系方式"),
    ("站外导流", "high", "加V", "删除站外联系方式"),
    ("站外导流", "high", "vx", "删除站外联系方式"),
    ("站外导流", "high", "VX", "删除站外联系方式"),
    ("站外导流", "high", "扣扣", "删除站外联系方式"),
    ("站外导流", "high", "QQ号", "删除站外联系方式"),
    ("站外导流", "high", "手机号", "删除联系方式"),
    ("站外导流", "high", "公众号", "删除站外导流指引"),
    ("站外导流", "high", "扫码加", "删除站外导流指引"),
    ("站外导流", "high", "私聊", "改为引导平台内商品卡"),
    ("站外导流", "high", "加我", "删除私下联系引导"),
    ("站外导流", "high", "私信我", "改为引导平台内商品卡"),
    ("站外导流", "high", "一手货源", "删除私下交易引导"),
    ("站外导流", "high", "代购", "删除私下交易引导"),
    ("站外导流", "high", "低价出", "改为平台内价格表述"),
    ("站外导流", "medium", "淘宝", "避免提及站外平台名"),
    ("站外导流", "medium", "天猫", "避免提及站外平台名"),
    ("站外导流", "medium", "京东", "避免提及站外平台名"),
    ("站外导流", "medium", "拼多多", "避免提及站外平台名"),
    ("站外导流", "medium", "抖音", "避免提及站外平台名"),
    ("站外导流", "medium", "快手", "避免提及站外平台名"),
    ("站外导流", "medium", "闲鱼", "避免提及站外平台名"),
    ("站外导流", "medium", "咸鱼", "避免提及站外平台名"),

    # --- 平台敏感操作 ---
    ("敏感操作", "high", "刷单", "删除违规操作相关表述"),
    ("敏感操作", "high", "刷量", "删除违规操作相关表述"),
    ("敏感操作", "high", "好评返现", "删除返现引导"),
    ("敏感操作", "high", "点赞返现", "删除返现引导"),
    ("敏感操作", "medium", "返现", "删除返现引导"),
    ("敏感操作", "medium", "三天见效", "效果承诺，改为使用周期描述或删除"),
    ("敏感操作", "medium", "立即见效", "效果承诺，删除"),
    ("敏感操作", "medium", "一分钟搞定", "删除效果时效承诺"),
    ("敏感操作", "medium", "仅此一天", "需有真实活动依据，否则删除"),
    ("敏感操作", "medium", "过了今天就没有", "需有真实活动依据，否则删除"),
    ("敏感操作", "medium", "限时抢购", "需有真实活动依据，否则删除"),
]

# --------------------------------------------------------------------------
# 类目规则：--category 触发
# --------------------------------------------------------------------------
CATEGORY_TERMS = {
    "cosmetics": [
        ("化妆品", "high", "药妆", "国内无「药妆」法定概念，删除"),
        ("化妆品", "high", "医学护肤", "删除医疗暗示"),
        ("化妆品", "high", "械字号面膜", "表述需与注册证一致，通常不得用于普通化妆品"),
        ("化妆品", "medium", "成分党", "可保留，但成分功效描述需与备案一致"),
        ("化妆品", "medium", "instant", "即时效果承诺需谨慎，改为使用感受"),
        ("化妆品", "medium", "毛孔隐形", "改为视觉感受描述，避免效果承诺"),
    ],
    "food": [
        ("食品", "high", "纯天然", "无国家标准定义，属绝对化用语，删除"),
        ("食品", "high", "零添加", "需有检测依据且符合标准，否则删除"),
        ("食品", "high", "有机", "需有机认证证书，否则删除"),
        ("食品", "high", "绿色食品", "需认证标志，否则删除"),
        ("食品", "high", "壮阳", "删除功效承诺"),
        ("食品", "high", "解酒", "删除功效承诺"),
        ("食品", "high", "养胃", "删除功效承诺，改为口感描述"),
        ("食品", "high", "降火", "删除功效承诺"),
        ("食品", "medium", "儿童食品", "需符合相应标准，谨慎表述适用年龄"),
    ],
    "health": [
        ("保健", "high", "增强抵抗力", "保健食品需蓝帽子，且不得宣称疾病预防"),
        ("保健", "high", "调理", "删除中医功效类表述"),
        ("保健", "high", "药食同源", "不等于可以宣称功效，谨慎使用"),
        ("保健", "high", "代替药物", "严禁表述"),
        ("保健", "high", "疗程", "医疗用语，删除"),
        ("保健", "medium", "滋补", "传统表述，建议改为食用场景描述"),
    ],
    "mother-baby": [
        ("母婴", "high", "益智", "删除功效承诺"),
        ("母婴", "high", "促进发育", "删除功效承诺"),
        ("母婴", "high", "无激素", "需检测依据，否则删除"),
        ("母婴", "high", "可吞咽", "涉及安全承诺，需有检测依据"),
        ("母婴", "medium", "宝宝专用", "需与实际执行标准一致"),
        ("母婴", "medium", "食品级", "需明确对应标准，避免泛指"),
    ],
    "apparel": [
        ("服饰", "high", "纯羊毛", "需与成分标一致，否则属虚假宣传"),
        ("服饰", "high", "真皮", "需与材质标一致"),
        ("服饰", "high", "进口面料", "需可核实的产地依据"),
        ("服饰", "medium", "显瘦十斤", "效果承诺，改为版型描述"),
        ("服饰", "medium", "不缩水", "改为洗涤建议或实测说明"),
    ],
    "digital": [
        ("3C", "high", "官方授权", "需有授权文件，否则删除"),
        ("3C", "high", "正品保证", "需说明鉴定方式，避免空口承诺"),
        ("3C", "medium", "原装", "需明确是原装正品还是原装配件"),
        ("3C", "medium", "终身保修", "改为具体保修期限"),
    ],
    "appliance": [
        ("家电", "high", "杀菌率99%", "需检测报告，否则改为「清洁更彻底」"),
        ("家电", "high", "医用级", "删除医疗等级暗示"),
        ("家电", "medium", "静音", "需给出分贝范围"),
        ("家电", "medium", "省电", "需给出功耗对比依据"),
    ],
}

CATEGORY_NOTES = {
    "general": "通用类目：按五类基础规则执行。",
    "cosmetics": "化妆品：美白/防晒/祛斑/防脱/染发/烫发属特殊化妆品，需注册证；普通化妆品不得宣称上述功效。",
    "food": "食品：不得宣称治疗、减肥、增强免疫；有机、绿色食品需证书；「零添加」「纯天然」风险高。",
    "health": "保健食品：需蓝帽子标识，且不得宣称疾病预防或治疗，不得替代药物。",
    "mother-baby": "母婴：不得宣称益智、增高、促进发育；涉及安全性的表述必须有检测依据。",
    "apparel": "服饰：材质、成分、产地必须与标识一致，否则构成虚假宣传。",
    "digital": "3C：授权、正品、原装等表述必须有可核实依据；保修期限要与政策一致。",
    "appliance": "家电：涉及杀菌率、静音、省电等参数，必须能给出检测报告或明确数值。",
}

# (类别, 等级, 正则, 建议, 展示名)
BASE_REGEXES = [
    ("敏感操作", "medium", re.compile(r"最后\s*\d+\s*件"), "库存紧迫需有真实依据，否则删除", "最后 N 件"),
    ("敏感操作", "medium", re.compile(r"已抢\s*\d+\s*[万]?单"), "销量数据需可核实，否则删除", "已抢 N 单"),
    ("站外导流", "high", re.compile(r"1[3-9]\d{9}"), "删除手机号", "疑似手机号"),
    ("站外导流", "high", re.compile(r"[a-zA-Z][\w.-]{5,}@[\w-]+\.[a-zA-Z]{2,}"), "删除邮箱", "疑似邮箱"),
    ("站外导流", "medium", re.compile(r"(?:微信|vx|VX|QQ)\s*[:：]?\s*[a-zA-Z0-9_-]{5,}"), "删除站外账号", "疑似站外账号"),
]


def _compile_regex(pattern_text):
    try:
        return re.compile(pattern_text)
    except re.error as exc:
        raise SystemExit("自定义规则中的正则不合法：{} ({})".format(pattern_text, exc))


def load_custom_rules(path):
    """读取自定义规则 JSON，返回 (terms, regexes)。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    terms, regexes = [], []
    for item in data.get("terms", []) or []:
        missing = [k for k in ("category", "level", "term") if not item.get(k)]
        if missing:
            raise SystemExit("自定义 term 缺少字段 {}：{}".format("/".join(missing), item))
        level = item["level"]
        if level not in LEVEL_ORDER:
            raise SystemExit("自定义 term 的 level 非法：{}".format(level))
        terms.append((item["category"], level, item["term"], item.get("advice", "")))
    for item in data.get("regex", []) or []:
        missing = [k for k in ("category", "level", "pattern") if not item.get(k)]
        if missing:
            raise SystemExit("自定义 regex 缺少字段 {}：{}".format("/".join(missing), item))
        level = item["level"]
        if level not in LEVEL_ORDER:
            raise SystemExit("自定义 regex 的 level 非法：{}".format(level))
        regexes.append((
            item["category"], level, _compile_regex(item["pattern"]),
            item.get("advice", ""), item.get("label", item["pattern"]),
        ))
    return terms, regexes


def scan(text, categories=None, extra_terms=None, extra_regexes=None):
    """扫描文本，返回命中列表（按等级降序、行号升序）。"""
    terms = list(BASE_TERMS)
    for cat in (categories or []):
        terms.extend(CATEGORY_TERMS.get(cat, []))
    terms.extend(extra_terms or [])
    regexes = list(BASE_REGEXES) + list(extra_regexes or [])

    findings = []
    lines = text.splitlines() or [""]
    for lineno, line in enumerate(lines, start=1):
        lowered = line.lower()
        for category, level, term, advice in terms:
            needle = term.lower()
            start = 0
            while True:
                idx = lowered.find(needle, start)
                if idx < 0:
                    break
                findings.append({
                    "category": category,
                    "level": level,
                    "term": term,
                    "line": lineno,
                    "column": idx + 1,
                    "context": line.strip()[:120],
                    "advice": advice,
                })
                start = idx + max(1, len(needle))
        for category, level, pattern, advice, label in regexes:
            for m in pattern.finditer(line):
                findings.append({
                    "category": category,
                    "level": level,
                    "term": label,
                    "line": lineno,
                    "column": m.start() + 1,
                    "context": line.strip()[:120],
                    "advice": advice,
                })

    seen, deduped = set(), []
    for f in findings:
        key = (f["category"], f["term"], f["line"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    deduped.sort(key=lambda f: (-LEVEL_ORDER[f["level"]], f["line"], f["column"]))
    return deduped


def summarize(findings):
    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f["level"]] += 1
    return counts


def verdict(findings):
    """返回 (结论, 说明)。"""
    counts = summarize(findings)
    if counts["high"] > 0:
        return "blocked", "存在高风险命中，必须修改后才能发布"
    if counts["medium"] > 0:
        return "review", "存在中风险命中，需补充真实依据或改写"
    if counts["low"] > 0:
        return "check", "存在待确认项，请逐条确认语境"
    return "pass", "未命中规则"


def render_text(findings, source, categories=None):
    counts = summarize(findings)
    code, desc = verdict(findings)
    out = ["=" * 62,
           "小红书带货文案 · 合规自检结果",
           "来源：{}".format(source)]
    if categories:
        out.append("类目：{}".format("、".join(categories)))
        for cat in categories:
            note = CATEGORY_NOTES.get(cat)
            if note:
                out.append("  · {}".format(note))
    out.append("=" * 62)
    out.append("结论：{} —— {}".format(code, desc))
    if not findings:
        out.append("未命中规则。注意：本工具为启发式自检，不等于平台审核通过。")
        return "\n".join(out)
    out.append("命中：高风险 {} ｜ 中风险 {} ｜ 待确认 {}".format(
        counts["high"], counts["medium"], counts["low"]))
    out.append("")
    for f in findings:
        out.append("[{}][{}] 第 {} 行 第 {} 列：{}".format(
            LEVEL_LABEL[f["level"]], f["category"], f["line"], f["column"], f["term"]))
        if f["context"]:
            out.append("    上下文：{}".format(f["context"]))
        if f["advice"]:
            out.append("    建议：{}".format(f["advice"]))
    out.append("")
    out.append("提示：高风险项必须修改；中风险项需补充真实依据或改写；")
    out.append("      本工具不识别谐音与图片文字，高风险类目请人工复核。")
    return "\n".join(out)


def render_csv(findings):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["level", "category", "term", "line", "column", "advice", "context"])
    for f in findings:
        writer.writerow([f["level"], f["category"], f["term"], f["line"], f["column"],
                         f["advice"], f["context"]])
    return buf.getvalue().rstrip("\n")


def render_rules():
    out = ["基础规则（类别 / 等级 / 词 / 建议）", "-" * 62]
    for category, level, term, advice in BASE_TERMS:
        out.append("{:<8} {:<6} {:<12} {}".format(category, LEVEL_LABEL[level], term, advice))
    for name, items in CATEGORY_TERMS.items():
        out.append("")
        out.append("类目规则 --category {}：".format(name))
        for category, level, term, advice in items:
            out.append("{:<8} {:<6} {:<12} {}".format(category, LEVEL_LABEL[level], term, advice))
    out.append("")
    out.append("正则规则：")
    for category, level, pattern, advice, label in BASE_REGEXES:
        out.append("{:<8} {:<6} {:<12} {}".format(category, LEVEL_LABEL[level], label, pattern.pattern))
    return "\n".join(out)


def render_explain():
    out = ["类目规则说明", "-" * 62]
    for name, note in CATEGORY_NOTES.items():
        out.append("--category {:<12} {}".format(name, note))
    out.append("")
    out.append("免责声明：{}".format(DISCLAIMER))
    out.append("规则表来自公开经验整理，平台规则会变动，高风险类目必须人工复核。")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="compliance_check.py",
        description="小红书带货文案离线合规自检（极限词/医疗功效/金融收益/站外导流/敏感操作）",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", "-f", help="待检查的 UTF-8 文本文件")
    src.add_argument("--text", "-t", help="直接传入待检查文本")
    parser.add_argument("--category", "-c", action="append", default=[],
                        choices=sorted(CATEGORY_TERMS.keys()),
                        help="叠加类目规则，可重复传入")
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text")
    parser.add_argument("--strict", action="store_true", help="存在高风险项时以退出码 1 结束")
    parser.add_argument("--min-level", choices=["low", "medium", "high"], default="low",
                        help="只输出不低于该等级的结果（默认 low）")
    parser.add_argument("--rules", help="自定义规则 JSON 文件（合并到内置规则）")
    parser.add_argument("--out", help="把结果写入指定文件（默认只打印到标准输出）")
    parser.add_argument("--list-rules", action="store_true", help="打印全部规则后退出")
    parser.add_argument("--explain", action="store_true", help="打印类目说明与免责声明后退出")
    args = parser.parse_args(argv)

    if args.list_rules:
        print(render_rules())
        return 0
    if args.explain:
        print(render_explain())
        return 0

    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print("找不到文件：{}".format(path), file=sys.stderr)
            return 2
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print("文件不是 UTF-8 编码，请先转码：{}".format(path), file=sys.stderr)
            return 2
        source = str(path)
    elif args.text is not None:
        text = args.text
        source = "命令行文本"
    else:
        parser.error("需要 --file 或 --text（或用 --list-rules / --explain）")
        return 2

    extra_terms, extra_regexes = ([], [])
    if args.rules:
        try:
            extra_terms, extra_regexes = load_custom_rules(args.rules)
        except (OSError, json.JSONDecodeError) as exc:
            print("自定义规则读取失败：{}".format(exc), file=sys.stderr)
            return 2

    findings = scan(text, categories=args.category,
                    extra_terms=extra_terms, extra_regexes=extra_regexes)
    findings = [f for f in findings if LEVEL_ORDER[f["level"]] >= LEVEL_ORDER[args.min_level]]

    if args.format == "json":
        payload = {
            "source": source,
            "categories": args.category,
            "summary": summarize(findings),
            "verdict": verdict(findings)[0],
            "findings": findings,
            "disclaimer": DISCLAIMER,
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    elif args.format == "csv":
        rendered = render_csv(findings)
    else:
        rendered = render_text(findings, source, args.category)

    print(rendered)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
        print("\n结果已写入：{}".format(args.out), file=sys.stderr)

    if args.strict and any(f["level"] == "high" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
