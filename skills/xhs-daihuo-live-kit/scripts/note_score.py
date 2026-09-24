#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商品笔记质量评分器（0–100）。

按 SKILL.md 约定的交付格式解析一篇笔记，从标题、正文、标签、封面、合规五个维度打分，
并给出可执行的改进项。纯离线，仅标准库；合规维度复用 compliance_check.py。

约定的笔记文件格式：
    ## 标题候选
    1. 标题一
    2. 标题二
    ## 正文
    正文段落……
    ## 标签
    #标签1 #标签2
    ## 封面大字
    1. 大字一

用法：
    python3 note_score.py --file note.md
    python3 note_score.py --file note.md --json
    python3 note_score.py --file note.md --min-score 80
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compliance_check import scan, summarize  # noqa: E402

SECTION_KEYS = {
    "title": ("标题", "title"),
    "body": ("正文", "文案", "body"),
    "tags": ("标签", "话题", "tag"),
    "cover": ("封面", "cover"),
}

TITLE_LIMIT = 20
COVER_LIMIT = 9
LINE_LIMIT = 60

ACTION_WORDS = ("适合", "建议", "直接买", "可以试试", "推荐给", "闭眼入", "按需", "看需求")
REVERSE_WORDS = ("不适合", "别买", "如果你", "除非你", "不建议")
FIRST_PERSON = ("我", "自己", "亲测", "自用")


def parse_note(text):
    """把交付格式的笔记解析成 {'title': [...], 'body': [...], 'tags': [...], 'cover': [...]}"""
    sections = {"title": [], "body": [], "tags": [], "cover": []}
    current = None
    for raw in text.splitlines():
        line = raw.rstrip()
        # 标准 ATX 标题要求 # 后有空格；否则 "#收纳" 这类标签会被误判为标题
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if heading:
            label = heading.group(1)
            current = None
            for key, keywords in SECTION_KEYS.items():
                if any(kw in label for kw in keywords):
                    current = key
                    break
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        sections[current].append(stripped)

    def strip_index(items):
        out = []
        for item in items:
            out.append(re.sub(r"^\s*(?:\d+[.、)]|[-*·])\s*", "", item).strip())
        return [i for i in out if i]

    sections["title"] = strip_index(sections["title"])
    sections["cover"] = strip_index(sections["cover"])
    if sections["tags"]:
        joined = " ".join(sections["tags"])
        sections["tags"] = [t for t in re.split(r"[\s,，]+", joined) if t]
    return sections


def score(note_text):
    """返回 (总分, 明细列表, 改进项列表)。明细项为 (维度, 得分, 满分, 说明)。"""
    sections = parse_note(note_text)
    details, fixes = [], []

    # ---- 标题 20 ----
    titles = sections["title"]
    got = 0
    if len(titles) >= 5:
        got += 8
    else:
        fixes.append("标题候选只有 {} 条，至少给 5 条不同钩子类型".format(len(titles)))
    too_long = [t for t in titles if len(t) > TITLE_LIMIT]
    if titles and not too_long:
        got += 6
    elif too_long:
        fixes.append("有 {} 条标题超过 {} 字，手机上会折行：{}".format(
            len(too_long), TITLE_LIMIT, too_long[0][:24]))
    title_findings = scan(" ".join(titles))
    if not any(f["level"] == "high" for f in title_findings):
        got += 6
    else:
        fixes.append("标题命中高风险词：{}".format(
            "、".join(sorted({f["term"] for f in title_findings if f["level"] == "high"}))))
    details.append(("标题", got, 20, "{} 条候选".format(len(titles))))

    # ---- 正文 30 ----
    body = sections["body"]
    body_text = "\n".join(body)
    got = 0
    if len(body) >= 3:
        got += 6
    else:
        fixes.append("正文只有 {} 段，建议按「开头钩子 / 证据 / 行动」至少 3 段".format(len(body)))
    if re.search(r"\d", body_text):
        got += 6
    else:
        fixes.append("正文没有任何具体数字，形容词换不来信任（如「续航 12 小时」）")
    if any(w in body_text for w in FIRST_PERSON):
        got += 4
    else:
        fixes.append("正文缺少第一人称体验视角，读起来像说明书")
    if any(w in body_text for w in REVERSE_WORDS):
        got += 6
    else:
        fixes.append("没有反向说明（「不适合谁」），补一句可信度会明显提升")
    longest = max((len(line) for line in body), default=0)
    if longest <= LINE_LIMIT:
        got += 4
    else:
        fixes.append("正文最长一行 {} 字，手机阅读体验差，建议每 3–4 行断句".format(longest))
    if any(w in body_text for w in ACTION_WORDS):
        got += 4
    else:
        fixes.append("结尾缺少行动指令（「如果你也是 xx 情况，选基础款就够」）")
    details.append(("正文", got, 30, "{} 段 / 最长 {} 字".format(len(body), longest)))

    # ---- 标签 15 ----
    tags = sections["tags"]
    got = 0
    if 6 <= len(tags) <= 10:
        got += 8
    else:
        fixes.append("标签 {} 个，建议 6–10 个（1 大词 + 2–3 精准词 + 1 长尾 + 品类词）".format(len(tags)))
    lengths = {len(t) for t in tags}
    if len(lengths) >= 2 and len(tags) >= 4:
        got += 7
    else:
        fixes.append("标签词长过于单一，说明没做「大词 + 精准词 + 长尾词」的组合")
    details.append(("标签", got, 15, "{} 个".format(len(tags))))

    # ---- 封面 15 ----
    covers = sections["cover"]
    got = 0
    if len(covers) >= 3:
        got += 6
    else:
        fixes.append("封面大字只有 {} 条，建议给 3 条备选".format(len(covers)))
    too_long_cover = [c for c in covers if len(c) > COVER_LIMIT]
    if covers and not too_long_cover:
        got += 5
    elif too_long_cover:
        fixes.append("封面大字「{}」超过 {} 字，封面放不下".format(too_long_cover[0][:16], COVER_LIMIT))
    if covers and titles and not (set(covers) & set(titles)):
        got += 4
    elif covers:
        fixes.append("封面大字与标题重复，封面应该独立成句而不是复述标题")
    details.append(("封面", got, 15, "{} 条".format(len(covers))))

    # ---- 合规 20 ----
    findings = scan(note_text)
    counts = summarize(findings)
    got = 0
    if counts["high"] == 0:
        got += 12
    else:
        fixes.append("命中 {} 个高风险词：{}".format(
            counts["high"], "、".join(sorted({f["term"] for f in findings if f["level"] == "high"}))))
    if counts["medium"] == 0:
        got += 8
    else:
        fixes.append("命中 {} 个中风险词，需补依据或改写".format(counts["medium"]))
    details.append(("合规", got, 20, "high {} / medium {} / low {}".format(
        counts["high"], counts["medium"], counts["low"])))

    total = sum(d[1] for d in details)
    return total, details, fixes


def grade(total):
    if total >= 90:
        return "A（可直接发布）"
    if total >= 75:
        return "B（小改后发布）"
    if total >= 60:
        return "C（需要补内容）"
    return "D（结构不完整，建议重写）"


def render_text(total, details, fixes, source):
    out = ["=" * 58,
           "商品笔记质量评分",
           "来源：{}".format(source),
           "=" * 58,
           "总分：{}/100   {}".format(total, grade(total)),
           ""]
    for name, got, full, note in details:
        bar = "█" * int(round(got / full * 20)) if full else ""
        out.append("{:<4} {:>3}/{:<3} {:<20} {}".format(name, got, full, bar, note))
    out.append("")
    if fixes:
        out.append("改进项（按重要性排序）：")
        for i, fix in enumerate(fixes, 1):
            out.append("  {}. {}".format(i, fix))
    else:
        out.append("没有发现明显问题。")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="note_score.py",
        description="按 SKILL.md 交付格式给商品笔记打分（0–100）",
    )
    parser.add_argument("--file", "-f", required=True, help="笔记文件（UTF-8）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--min-score", type=int, default=None, help="低于该分数时退出码 1")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        print("找不到文件：{}".format(path), file=sys.stderr)
        return 2
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print("文件不是 UTF-8 编码：{}".format(path), file=sys.stderr)
        return 2

    total, details, fixes = score(text)
    if args.json:
        print(json.dumps({
            "source": str(path),
            "score": total,
            "grade": grade(total),
            "dimensions": [{"name": n, "score": g, "full": f, "note": note} for n, g, f, note in details],
            "fixes": fixes,
        }, ensure_ascii=False, indent=2))
    else:
        print(render_text(total, details, fixes, path))

    if args.min_score is not None and total < args.min_score:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
