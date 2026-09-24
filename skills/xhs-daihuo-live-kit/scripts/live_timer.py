#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直播时间轴生成器。

按五段式比例把一场直播切成分钟级流程表，并把商品分配到「产品引入」阶段，
输出可直接交给主播与场控的骨架表格。纯离线，仅标准库。

用法：
    python3 live_timer.py --minutes 30 --products "便携榨汁杯,收纳盒,除味喷雾"
    python3 live_timer.py --minutes 90 --products "A,B,C,D" --format csv --out timeline.csv
    python3 live_timer.py --minutes 30 --json

口径：五段式比例来自 references/live-script-playbook.md
    开场留人 10% ｜ 痛点共鸣 17% ｜ 产品引入 23% ｜ 信任建立 23% ｜ 逼单转化 27%
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

PHASES = [
    ("开场留人", 0.10, "给停留理由，不发散", "口播：今天讲什么 / 有什么 / 值多少"),
    ("痛点共鸣", 0.17, "让人对号入座", "举 2–3 个具体场景，不推销"),
    ("产品引入", 0.23, "只讲 3 个卖点", "演示 + 对比，一个卖点一个动作"),
    ("信任建立", 0.23, "消除疑虑", "资质、实测、售后、真实评价"),
    ("逼单转化", 0.27, "给行动指令", "价格锚点、库存说明、下单路径"),
]

PRODUCT_STEPS = ["痛点提问", "外观展示", "核心卖点 1", "核心卖点 2", "演示验证", "价格锚点", "下单指令"]


def fmt(seconds):
    return "{:02d}:{:02d}".format(int(seconds) // 60, int(seconds) % 60)


def build(minutes, products):
    if minutes <= 0:
        raise ValueError("minutes 必须大于 0")
    if minutes < 10:
        raise ValueError("低于 10 分钟的场次不适合五段式，请把时长调到 10 分钟以上")

    total = minutes * 60
    # 先按比例取整到秒，再把余数补给最后一段，保证时间轴严丝合缝
    allocated = []
    used = 0
    for idx, (name, ratio, goal, action) in enumerate(PHASES):
        if idx == len(PHASES) - 1:
            secs = total - used
        else:
            secs = int(round(total * ratio))
            used += secs
        allocated.append({"phase": name, "seconds": secs, "goal": goal, "action": action})

    # 商品在「产品引入」窗口内按顺序平分时段
    products = list(products or [])
    blocks = []
    for block in allocated:
        if block["phase"] == "产品引入" and products:
            count = len(products)
            base, remainder = divmod(block["seconds"], count)
            for i, product in enumerate(products):
                secs = base + (1 if i < remainder else 0)
                blocks.append({
                    "phase": "产品引入 · {}".format(product),
                    "seconds": secs,
                    "goal": "讲透 3 个卖点",
                    "action": " / ".join(PRODUCT_STEPS),
                    "item": product,
                })
        else:
            blocks.append(dict(block, item=""))

    rows = []
    cursor = 0
    for block in blocks:
        rows.append({
            "start": fmt(cursor),
            "end": fmt(cursor + block["seconds"]),
            "phase": block["phase"],
            "goal": block["goal"],
            "action": block["action"],
            "item": block["item"],
        })
        cursor += block["seconds"]

    if cursor != total:  # 理论上不可达，留作不变量自检
        raise AssertionError("时间轴总长 {} 秒与设定 {} 秒不一致".format(cursor, total))
    return rows


def render_md(rows, minutes, products):
    out = ["# 直播时间轴（{} 分钟）".format(minutes), ""]
    if products:
        out.append("商品顺序：{}".format(" → ".join(products)))
        out.append("")
    out.append("| 时间 | 阶段 | 目标 | 动作 | 口播要点 | 屏幕/道具 |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        out.append("| {}–{} | {} | {} | {} |  |  |".format(
            r["start"], r["end"], r["phase"], r["goal"], r["action"]))
    out.append("")
    out.append("## 话术卡（每个商品一张，照着填）")
    out.append("")
    for product in (products or ["主推品"]):
        out.append("### {}".format(product))
        for step in PRODUCT_STEPS:
            out.append("- **{}**：".format(step))
        out.append("")
    out.append("## 场控清单")
    out.append("")
    out.append("- [ ] 演示道具按顺序摆好，直播中不现找")
    out.append("- [ ] 每个商品的上架时间与主播口播对齐")
    out.append("- [ ] 倒计时只在有真实活动依据时使用")
    out.append("- [ ] 全程不出现违禁表述（跑一次 compliance_check.py）")
    return "\n".join(out)


def render_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["start", "end", "phase", "goal", "action", "item"])
    for r in rows:
        writer.writerow([r["start"], r["end"], r["phase"], r["goal"], r["action"], r["item"]])
    return buf.getvalue().rstrip("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="live_timer.py",
        description="按五段式比例生成分钟级直播时间轴",
    )
    parser.add_argument("--minutes", type=int, required=True, help="直播总时长（分钟）")
    parser.add_argument("--products", default="", help="商品名，逗号分隔，按出场顺序")
    parser.add_argument("--format", choices=["md", "csv", "json"], default="md")
    parser.add_argument("--out", help="结果写入文件")
    args = parser.parse_args(argv)

    products = [p.strip() for p in args.products.split(",") if p.strip()]
    try:
        rows = build(args.minutes, products)
    except ValueError as exc:
        print("生成失败：{}".format(exc), file=sys.stderr)
        return 2

    if args.format == "json":
        rendered = json.dumps({"minutes": args.minutes, "products": products, "rows": rows},
                              ensure_ascii=False, indent=2)
    elif args.format == "csv":
        rendered = render_csv(rows)
    else:
        rendered = render_md(rows, args.minutes, products)

    print(rendered)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
        print("\n结果已写入：{}".format(args.out), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
