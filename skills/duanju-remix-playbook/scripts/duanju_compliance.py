#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短剧二创 · 文案与推广语合规自检。

短剧推广的高危词和带货完全不同：全集承诺、独家宣称、擦边引流、盗版暗示是重灾区。
本脚本按这几个类别扫描解说稿、标题、封面文案与推广话术。

纯离线，仅使用 Python 标准库，不联网、不读凭据；默认只读，仅 --out 时写盘。

用法：
    python3 duanju_compliance.py --file script.txt
    python3 duanju_compliance.py --text "全集免费，未删减完整版"
    python3 duanju_compliance.py --file script.txt --category promotion
    python3 duanju_compliance.py --file script.txt --format json --strict
    python3 duanju_compliance.py --file script.txt --rules my-terms.json
    python3 duanju_compliance.py --list-rules
    python3 duanju_compliance.py --explain

也可作为库使用：
    from duanju_compliance import scan, summarize, verdict
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

DISCLAIMER = "启发式自检，不等于平台官方审核规则，也不构成法律意见。"

BASE_TERMS = [
    # --- 全集 / 完整度承诺 ---
    ("全集承诺", "high", "全集免费", "改为「点击下方观看」等不承诺完整度的引导"),
    ("全集承诺", "high", "免费看全集", "改为中性引导，不承诺全集"),
    ("全集承诺", "high", "完整版", "需与实际可观看范围一致，否则删除"),
    ("全集承诺", "high", "未删减", "平台敏感表述，删除"),
    ("全集承诺", "high", "无删减", "平台敏感表述，删除"),
    ("全集承诺", "high", "完整全集", "删除完整度承诺"),
    ("全集承诺", "medium", "全剧", "改为「后续剧情」，避免完整度承诺"),
    ("全集承诺", "medium", "一口气看完", "改为「继续看下去」"),

    # --- 独家 / 首发宣称 ---
    ("独家宣称", "high", "全网独播", "无独家授权不得使用，删除"),
    ("独家宣称", "high", "独家资源", "需可核实授权，否则删除"),
    ("独家宣称", "high", "独家播出", "需可核实授权，否则删除"),
    ("独家宣称", "high", "全网首发", "需可核实，否则删除"),
    ("独家宣称", "high", "首播", "改为具体上线时间描述"),
    ("独家宣称", "medium", "全网最", "绝对化用语，改为具体范围"),

    # --- 擦边引流 ---
    ("擦边引流", "high", "大尺度", "平台重点打击，删除"),
    ("擦边引流", "high", "激情", "删除"),
    ("擦边引流", "high", "暧昧", "删除"),
    ("擦边引流", "high", "香艳", "删除"),
    ("擦边引流", "high", "露骨", "删除"),
    ("擦边引流", "high", "少儿不宜", "删除"),
    ("擦边引流", "high", "限制级", "删除"),
    ("擦边引流", "medium", "甜宠", "题材标签可用，但不得与擦边话术组合"),

    # --- 暴力血腥 ---
    ("暴力血腥", "high", "血腥", "删除，剪辑时也应避开画面"),
    ("暴力血腥", "high", "残肢", "删除"),
    ("暴力血腥", "high", "虐杀", "删除"),
    ("暴力血腥", "medium", "打斗", "可保留但不做钩子主诉求"),

    # --- 盗版 / 站外搬运暗示 ---
    ("盗版搬运", "high", "网盘", "站外分享引导，删除"),
    ("盗版搬运", "high", "无删减资源", "盗版暗示，删除"),
    ("盗版搬运", "high", "资源分享", "站外分享引导，删除"),
    ("盗版搬运", "high", "搬运", "自曝违规，删除"),
    ("盗版搬运", "high", "微信公众号", "站外导流，删除"),
    ("盗版搬运", "high", "微信", "站外导流，删除"),
    ("盗版搬运", "high", "私信我", "改为引导平台内观看"),
    ("盗版搬运", "high", "加V", "站外导流，删除"),
    ("盗版搬运", "medium", "私信", "改为引导平台内观看"),

    # --- 收益 / 诱导 ---
    ("收益诱导", "high", "看剧赚钱", "收益承诺，删除"),
    ("收益诱导", "high", "边看边赚", "收益承诺，删除"),
    ("收益诱导", "high", "日入过万", "收益承诺，删除"),
    ("收益诱导", "high", "不点后悔", "诱导性话术，改为中性引导"),
    ("收益诱导", "high", "点进去就送", "需有真实活动依据，否则删除"),
    ("收益诱导", "medium", "最后机会", "需有真实活动依据，否则删除"),
    ("收益诱导", "medium", "点开有惊喜", "改为具体说明"),

    # --- 极限词（沿用广告法口径）---
    ("极限词", "high", "最好看", "改为主观感受或删除"),
    ("极限词", "high", "第一", "删除排名类表述"),
    ("极限词", "high", "史上最", "删除绝对化比较"),
    ("极限词", "high", "绝对", "删除绝对化用语"),
    ("极限词", "high", "100%", "改为具体比例或删除"),
    ("极限词", "low", "最", "「最」字需逐条确认语境"),
]

CATEGORY_TERMS = {
    "promotion": [
        ("推广话术", "high", "限时", "需有真实活动依据，否则删除"),
        ("推广话术", "high", "仅此一天", "需有真实活动依据，否则删除"),
        ("推广话术", "high", "最后一天", "需有真实活动依据，否则删除"),
        ("推广话术", "medium", "关注领", "需有真实活动依据，否则删除"),
        ("推广话术", "medium", "评论区扣", "改为中性互动引导"),
    ],
    "title": [
        ("标题封面", "medium", "震惊", "标题党，改为具体信息"),
        ("标题封面", "medium", "竟然", "标题党，改为具体信息"),
        ("标题封面", "medium", "太敢拍了", "擦边暗示，删除"),
    ],
    "comment": [
        ("评论话术", "high", "私我", "站外导流，改为引导平台内观看"),
        ("评论话术", "high", "链接在简介", "站外导流风险，改为平台内引导"),
        ("评论话术", "medium", "我发你", "改为公开说明渠道"),
    ],
}

CATEGORY_NOTES = {
    "general": "通用：按全集承诺、独家宣称、擦边引流、暴力血腥、盗版搬运、收益诱导、极限词七类执行。",
    "promotion": "推广话术：限时、最后一天等时效性表述必须有真实活动依据。",
    "title": "标题与封面：标题党在短剧赛道同样受限流处罚。",
    "comment": "评论话术：不得在评论区引导站外联系或私发资源。",
}

BASE_REGEXES = [
    ("盗版搬运", "high", re.compile(r"1[3-9]\d{9}"), "删除手机号", "疑似手机号"),
    ("盗版搬运", "high", re.compile(r"[a-zA-Z][\w.-]{5,}@[\w-]+\.[a-zA-Z]{2,}"), "删除邮箱", "疑似邮箱"),
    ("盗版搬运", "medium", re.compile(r"(?:微信|vx|VX|QQ)\s*[:：]?\s*[a-zA-Z0-9_-]{5,}"), "删除站外账号", "疑似站外账号"),
    ("盗版搬运", "medium", re.compile(r"(?:https?://|pan\.|www\.)\S+"), "删除站外链接", "疑似站外链接"),
]


def _compile(pattern_text):
    try:
        return re.compile(pattern_text)
    except re.error as exc:
        raise SystemExit("自定义规则中的正则不合法：{} ({})".format(pattern_text, exc))


def load_custom_rules(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    terms, regexes = [], []
    for item in data.get("terms", []) or []:
        missing = [k for k in ("category", "level", "term") if not item.get(k)]
        if missing:
            raise SystemExit("自定义 term 缺少字段 {}：{}".format("/".join(missing), item))
        if item["level"] not in LEVEL_ORDER:
            raise SystemExit("自定义 term 的 level 非法：{}".format(item["level"]))
        terms.append((item["category"], item["level"], item["term"], item.get("advice", "")))
    for item in data.get("regex", []) or []:
        missing = [k for k in ("category", "level", "pattern") if not item.get(k)]
        if missing:
            raise SystemExit("自定义 regex 缺少字段 {}：{}".format("/".join(missing), item))
        if item["level"] not in LEVEL_ORDER:
            raise SystemExit("自定义 regex 的 level 非法：{}".format(item["level"]))
        regexes.append((item["category"], item["level"], _compile(item["pattern"]),
                        item.get("advice", ""), item.get("label", item["pattern"])))
    return terms, regexes


def scan(text, categories=None, extra_terms=None, extra_regexes=None):
    terms = list(BASE_TERMS)
    for cat in (categories or []):
        terms.extend(CATEGORY_TERMS.get(cat, []))
    terms.extend(extra_terms or [])
    regexes = list(BASE_REGEXES) + list(extra_regexes or [])

    findings = []
    for lineno, line in enumerate(text.splitlines() or [""], start=1):
        lowered = line.lower()
        for category, level, term, advice in terms:
            needle = term.lower()
            start = 0
            while True:
                idx = lowered.find(needle, start)
                if idx < 0:
                    break
                findings.append({
                    "category": category, "level": level, "term": term,
                    "line": lineno, "column": idx + 1,
                    "context": line.strip()[:120], "advice": advice,
                })
                start = idx + max(1, len(needle))
        for category, level, pattern, advice, label in regexes:
            for m in pattern.finditer(line):
                findings.append({
                    "category": category, "level": level, "term": label,
                    "line": lineno, "column": m.start() + 1,
                    "context": line.strip()[:120], "advice": advice,
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
    counts = summarize(findings)
    if counts["high"] > 0:
        return "blocked", "存在高风险命中，必须修改后才能出片"
    if counts["medium"] > 0:
        return "review", "存在中风险命中，需补充真实依据或改写"
    if counts["low"] > 0:
        return "check", "存在待确认项，请逐条确认语境"
    return "pass", "未命中规则"


def render_text(findings, source, categories=None):
    counts = summarize(findings)
    code, desc = verdict(findings)
    out = ["=" * 62, "短剧二创 · 文案合规自检结果", "来源：{}".format(source)]
    if categories:
        out.append("类目：{}".format("、".join(categories)))
        for cat in categories:
            note = CATEGORY_NOTES.get(cat)
            if note:
                out.append("  · {}".format(note))
    out.append("=" * 62)
    out.append("结论：{} —— {}".format(code, desc))
    if not findings:
        out.append("未命中规则。本工具为启发式自检，不等于平台审核通过。")
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
    out.append("提示：高风险项必须修改；不识别谐音与画面内容，需人工复核。")
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
    out.append("完整的授权与内容门禁见 references/rights-checklist.md。")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="duanju_compliance.py",
        description="短剧二创文案合规自检（全集承诺/独家宣称/擦边引流/暴力血腥/盗版搬运/收益诱导/极限词）",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", "-f", help="待检查的 UTF-8 文本文件")
    src.add_argument("--text", "-t", help="直接传入待检查文本")
    parser.add_argument("--category", "-c", action="append", default=[],
                        choices=sorted(CATEGORY_TERMS.keys()), help="叠加类目规则，可重复")
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text")
    parser.add_argument("--strict", action="store_true", help="存在高风险项时以退出码 1 结束")
    parser.add_argument("--min-level", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--rules", help="自定义规则 JSON 文件")
    parser.add_argument("--out", help="结果写入文件")
    parser.add_argument("--list-rules", action="store_true", help="打印全部规则后退出")
    parser.add_argument("--explain", action="store_true", help="打印类目说明后退出")
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
            print("文件不是 UTF-8 编码：{}".format(path), file=sys.stderr)
            return 2
        source = str(path)
    elif args.text is not None:
        text, source = args.text, "命令行文本"
    else:
        parser.error("需要 --file 或 --text（或用 --list-rules / --explain）")
        return 2

    extra_terms, extra_regexes = [], []
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
        rendered = json.dumps({
            "source": source, "categories": args.category,
            "summary": summarize(findings), "verdict": verdict(findings)[0],
            "findings": findings, "disclaimer": DISCLAIMER,
        }, ensure_ascii=False, indent=2)
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
