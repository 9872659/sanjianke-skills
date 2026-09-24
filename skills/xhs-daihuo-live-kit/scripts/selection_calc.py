#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选品毛利与投放空间计算器。

把「售价 / 成本 / 物流 / 佣金 / 退货率」换算成带货决策真正需要的几个数：
单件毛利、佣金后毛利、退货后毛利、毛利率、保本 CPA、建议 CPA 上限，并给出结论。

纯离线，仅标准库。

用法：
    python3 selection_calc.py --price 89 --cost 32 --shipping 6 --commission 0.20
    python3 selection_calc.py --price 89 --cost 32 --shipping 6 --commission 0.2 --return-rate 0.08 --target-roas 3
    python3 selection_calc.py --price 89 --cost 32 --shipping 6 --commission 0.2 --json
    python3 selection_calc.py --batch products.csv

批量 CSV 表头（逗号分隔，UTF-8）：
    name,price,cost,shipping,commission,return_rate
    便携榨汁杯,89,32,6,0.20,0.08

口径说明：
    单件毛利     = 售价 - 成本 - 物流 - 包材
    佣金后毛利   = 单件毛利 - 售价 × 佣金率
    退货后毛利   = 佣金后毛利 × (1 - 退货率)
    保本 CPA     = 退货后毛利（超过就是纯亏）
    建议 CPA 上限 = 退货后毛利 × 0.5（留一半利润给经营与退款）
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# 毛利率阈值：>=主推线为主推，>=测试线为可测试，否则谨慎
PUSH_LINE = 0.35
TEST_LINE = 0.20
CPA_SAFETY = 0.5


def compute(price, cost, shipping, commission, return_rate=0.0, packaging=0.0, target_roas=None):
    """返回一件商品的完整测算结果。"""
    if price <= 0:
        raise ValueError("price 必须大于 0")
    for name, value in (("cost", cost), ("shipping", shipping),
                        ("packaging", packaging), ("commission", commission),
                        ("return_rate", return_rate)):
        if value < 0:
            raise ValueError("{} 不能为负数".format(name))
    if commission > 1:
        raise ValueError("commission 应为 0–1 之间的小数（20% 请写 0.2）")
    if return_rate >= 1:
        raise ValueError("return_rate 应小于 1")

    gross = price - cost - shipping - packaging
    after_commission = gross - price * commission
    after_return = after_commission * (1 - return_rate)
    margin_rate = after_commission / price
    breakeven_cpa = after_return
    suggested_cpa = after_return * CPA_SAFETY

    if margin_rate >= PUSH_LINE:
        verdict, reason = "可主推", "毛利率 {:.0%}，有投放余量".format(margin_rate)
    elif margin_rate >= TEST_LINE:
        verdict, reason = "可测试", "毛利率 {:.0%}，投放预算要克制".format(margin_rate)
    else:
        verdict, reason = "谨慎", "毛利率仅 {:.0%}，基本没有投放空间".format(margin_rate)

    if after_return <= 0:
        verdict, reason = "放弃", "退货后毛利为负，卖一单亏一单"

    result = {
        "price": round(price, 2),
        "cost": round(cost, 2),
        "shipping": round(shipping, 2),
        "packaging": round(packaging, 2),
        "commission": commission,
        "commission_amount": round(price * commission, 2),
        "return_rate": return_rate,
        "gross": round(gross, 2),
        "after_commission": round(after_commission, 2),
        "after_return": round(after_return, 2),
        "margin_rate": round(margin_rate, 4),
        "breakeven_cpa": round(breakeven_cpa, 2),
        "suggested_cpa": round(suggested_cpa, 2),
        "verdict": verdict,
        "reason": reason,
    }
    if target_roas:
        required_cpa = price / target_roas
        result["target_roas"] = target_roas
        result["required_cpa"] = round(required_cpa, 2)
        result["roas_feasible"] = required_cpa <= suggested_cpa
        result["roas_note"] = (
            "目标 ROAS {} 对应可承受 CPA {:.2f}，在建议上限 {:.2f} 以内，可行".format(
                target_roas, required_cpa, suggested_cpa)
            if result["roas_feasible"] else
            "目标 ROAS {} 需要 CPA {:.2f}，高于建议上限 {:.2f}，按当前毛利跑不动".format(
                target_roas, required_cpa, suggested_cpa)
        )
    return result


def render_text(r, name=None):
    out = []
    if name:
        out.append("【{}】".format(name))
    out.append("售价 {price} ｜ 成本 {cost} ｜ 物流 {shipping} ｜ 包材 {packaging} ｜ 佣金 {commission_pct} ｜ 退货率 {return_pct}".format(
        commission_pct="{:.0%}".format(r["commission"]),
        return_pct="{:.0%}".format(r["return_rate"]),
        **r))
    out.append("-" * 58)
    out.append("单件毛利      {}".format(r["gross"]))
    out.append("佣金           -{}".format(r["commission_amount"]))
    out.append("佣金后毛利    {}   （占售价 {:.1%}）".format(r["after_commission"], r["margin_rate"]))
    out.append("退货后毛利    {}".format(r["after_return"]))
    out.append("保本 CPA      {}   （投放超过这个数就是纯亏）".format(r["breakeven_cpa"]))
    out.append("建议 CPA 上限 {}   （留一半利润给经营与退款）".format(r["suggested_cpa"]))
    if "required_cpa" in r:
        out.append("目标 ROAS {}  → 需要 CPA {}".format(r["target_roas"], r["required_cpa"]))
        out.append("              {}".format(r["roas_note"]))
    out.append("-" * 58)
    out.append("【结论】{} —— {}".format(r["verdict"], r["reason"]))
    return "\n".join(out)


def run_batch(path):
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"price", "cost", "shipping", "commission"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("CSV 缺少列：{}".format("、".join(sorted(missing))))
        for raw in reader:
            rows.append(compute(
                price=float(raw["price"]),
                cost=float(raw["cost"]),
                shipping=float(raw["shipping"]),
                commission=float(raw["commission"]),
                return_rate=float(raw.get("return_rate") or 0),
                packaging=float(raw.get("packaging") or 0),
                target_roas=float(raw["target_roas"]) if raw.get("target_roas") else None,
            ))
            rows[-1]["name"] = raw.get("name") or "未命名"
    return rows


def render_batch_text(rows):
    out = ["{:<16} {:>7} {:>9} {:>9} {:>9} {:>9}  {}".format(
        "商品", "售价", "佣金后", "退货后", "保本CPA", "建议CPA", "结论"),
        "-" * 84]
    for r in rows:
        out.append("{:<16} {:>7} {:>9} {:>9} {:>9} {:>9}  {}".format(
            r["name"][:14], r["price"], r["after_commission"], r["after_return"],
            r["breakeven_cpa"], r["suggested_cpa"], r["verdict"]))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="selection_calc.py",
        description="小红书带货选品毛利与投放空间计算器",
    )
    parser.add_argument("--price", type=float, help="售价")
    parser.add_argument("--cost", type=float, help="商品成本")
    parser.add_argument("--shipping", type=float, default=0.0, help="单件物流成本（默认 0）")
    parser.add_argument("--packaging", type=float, default=0.0, help="包材成本（默认 0）")
    parser.add_argument("--commission", type=float, default=0.0, help="佣金率，小数（20%% 写 0.2）")
    parser.add_argument("--return-rate", type=float, default=0.0, help="退货率，小数（8%% 写 0.08）")
    parser.add_argument("--target-roas", type=float, default=None, help="目标投产比，用于反推可承受 CPA")
    parser.add_argument("--batch", help="批量 CSV 路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--out", help="结果写入文件")
    args = parser.parse_args(argv)

    try:
        if args.batch:
            rows = run_batch(args.batch)
            if args.json:
                rendered = json.dumps({"items": rows}, ensure_ascii=False, indent=2)
            else:
                rendered = render_batch_text(rows)
        else:
            if args.price is None or args.cost is None:
                parser.error("单件模式需要 --price 与 --cost（或使用 --batch）")
            r = compute(price=args.price, cost=args.cost, shipping=args.shipping,
                        commission=args.commission, return_rate=args.return_rate,
                        packaging=args.packaging, target_roas=args.target_roas)
            rendered = json.dumps(r, ensure_ascii=False, indent=2) if args.json else render_text(r)
    except (ValueError, OSError) as exc:
        print("计算失败：{}".format(exc), file=sys.stderr)
        return 2

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
