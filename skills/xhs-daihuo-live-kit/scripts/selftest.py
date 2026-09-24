#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本技能的内置自测。验证全部脚本的核心行为，无需第三方依赖、不联网、不写盘。

用法：
    python3 scripts/selftest.py           # 全部跑一遍
    python3 scripts/selftest.py -v        # 打印每个用例

退出码：0 全部通过；1 有失败用例。
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compliance_check as cc   # noqa: E402
import live_timer as lt         # noqa: E402
import note_score as ns         # noqa: E402
import selection_calc as sc     # noqa: E402

CHECKS = []


def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


# ---------------------------------------------------------------- 合规扫描
@check("合规：命中极限词 / 医疗功效 / 站外导流")
def _():
    findings = cc.scan("全网最低价，根治敏感肌，加微信 abc12345")
    terms = {f["term"] for f in findings}
    assert "全网最低" in terms, terms
    assert "根治" in terms, terms
    assert "微信" in terms, terms
    assert all(f["level"] == "high" for f in findings if f["term"] in {"根治", "微信"})


@check("合规：干净文本不产生高风险命中")
def _():
    findings = cc.scan("这款收纳盒容量 400ml，我用下来觉得放桌面刚好。")
    assert cc.summarize(findings)["high"] == 0, findings


@check("合规：verdict 分级正确")
def _():
    assert cc.verdict(cc.scan("全网最低价"))[0] == "blocked"
    assert cc.verdict(cc.scan("纯天然蜂蜜"))[0] == "pass"   # 未叠加类目规则
    assert cc.verdict(cc.scan("绝对值得买"))[0] == "blocked"


@check("合规：类目规则叠加生效")
def _():
    base = cc.scan("纯天然，零添加")
    with_cat = cc.scan("纯天然，零添加", categories=["food"])
    assert len(with_cat) > len(base), (base, with_cat)
    assert any(f["category"] == "食品" for f in with_cat), with_cat


@check("合规：自定义规则文件可合并")
def _():
    payload = {
        "terms": [{"category": "私有", "level": "high", "term": "内部黑话", "advice": "删除"}],
        "regex": [{"category": "私有", "level": "medium", "pattern": "XHS-\\d+", "label": "内部编号"}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rules.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        terms, regexes = cc.load_custom_rules(path)
    assert len(terms) == 1 and len(regexes) == 1
    findings = cc.scan("内部黑话 XHS-123", extra_terms=terms, extra_regexes=regexes)
    assert {f["term"] for f in findings} >= {"内部黑话", "内部编号"}, findings


@check("合规：非法自定义等级会被拒绝")
def _():
    payload = {"terms": [{"category": "私有", "level": "critical", "term": "x"}]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rules.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            cc.load_custom_rules(path)
        except SystemExit:
            return
    raise AssertionError("非法 level 未被拒绝")


@check("合规：CSV 输出含表头且行数正确")
def _():
    findings = cc.scan("全网最低价，根治")
    csv_text = cc.render_csv(findings)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("level,category,term"), lines[0]
    assert len(lines) == len(findings) + 1, (len(lines), len(findings))


@check("合规：去重后同一行同一词只报一次")
def _():
    findings = cc.scan("最好最好最好")
    assert len([f for f in findings if f["term"] == "最好"]) == 1, findings


# ---------------------------------------------------------------- 选品测算
@check("选品：已知数值测算正确")
def _():
    r = sc.compute(price=100, cost=30, shipping=5, commission=0.20, return_rate=0.10)
    assert r["gross"] == 65, r
    assert r["after_commission"] == 45, r
    assert r["after_return"] == 40.5, r
    assert r["margin_rate"] == 0.45, r
    assert r["breakeven_cpa"] == 40.5, r
    assert r["suggested_cpa"] == 20.25, r
    assert r["verdict"] == "可主推", r


@check("选品：低毛利被判为谨慎")
def _():
    r = sc.compute(price=100, cost=70, shipping=8, commission=0.10)
    assert r["verdict"] == "谨慎", r


@check("选品：退货后毛利为负判为放弃")
def _():
    r = sc.compute(price=100, cost=95, shipping=9, commission=0.05, return_rate=0.5)
    assert r["verdict"] == "放弃", r


@check("选品：目标 ROAS 反推 CPA")
def _():
    r = sc.compute(price=100, cost=30, shipping=5, commission=0.2, target_roas=5)
    assert r["required_cpa"] == 20.0, r
    assert r["roas_feasible"] is True, r
    tight = sc.compute(price=100, cost=30, shipping=5, commission=0.2, target_roas=2)
    assert tight["roas_feasible"] is False, tight


@check("选品：非法入参被拒绝")
def _():
    for kwargs in ({"price": 0, "cost": 1, "shipping": 0, "commission": 0},
                   {"price": 10, "cost": 1, "shipping": 0, "commission": 1.5}):
        try:
            sc.compute(**kwargs)
        except ValueError:
            continue
        raise AssertionError("非法入参未被拒绝：{}".format(kwargs))


# ---------------------------------------------------------------- 直播时间轴
@check("时间轴：30 分钟切分严丝合缝")
def _():
    rows = lt.build(30, [])
    assert len(rows) == len(lt.PHASES), rows
    assert rows[0]["start"] == "00:00" and rows[-1]["end"] == "30:00", rows
    assert all(r["start"] == prev["end"] for prev, r in zip(rows, rows[1:])), rows


@check("时间轴：商品被分配到产品引入阶段")
def _():
    rows = lt.build(30, ["便携榨汁杯", "收纳盒"])
    phases = [r["phase"] for r in rows]
    assert any("便携榨汁杯" in p for p in phases), phases
    assert any("收纳盒" in p for p in phases), phases
    assert sum(1 for p in phases if p == "产品引入") == 0, phases


@check("时间轴：时长过短会被拒绝")
def _():
    try:
        lt.build(5, [])
    except ValueError:
        return
    raise AssertionError("过短时长未被拒绝")


@check("时间轴：CSV 渲染含表头")
def _():
    csv_text = lt.render_csv(lt.build(30, ["A"]))
    assert csv_text.splitlines()[0] == "start,end,phase,goal,action,item", csv_text.splitlines()[0]


# ---------------------------------------------------------------- 笔记评分
GOOD_NOTE = """## 标题候选
1. 租房党别再买贵的收纳了
2. 用了两周我把旧的扔了
3. 三个细节判断值不值
4. 89 块的桌面快乐
5. 小桌子也能收得干净
## 正文
租房三年，我试过四种收纳方式。
最后只留下这个，因为两点。
容量 400ml，抽屉里刚好横放，不占地方。
我每天下班顺手一放，桌面再没乱过。
不适合要装大件衣物的人，这个只适合零碎。
如果你也是小桌子，直接买基础款就够。
## 标签
#收纳 #租房好物 #桌面收纳 #小户型 #收纳盒 #整理
## 封面大字
1. 租房党收好了
2. 89 块的桌面
3. 用两周换掉旧的
"""

BAD_NOTE = """## 标题候选
1. 超值好物
## 正文
本产品质量优良，值得购买。
## 标签
#好物
## 封面大字
1. 超值好物推荐给大家快来买
"""


@check("评分：交付格式能被正确解析")
def _():
    sections = ns.parse_note(GOOD_NOTE)
    assert len(sections["title"]) == 5, sections
    assert len(sections["body"]) == 6, sections
    assert len(sections["tags"]) == 6, sections
    assert len(sections["cover"]) == 3, sections


@check("评分：好笔记显著高于差笔记")
def _():
    good, _, good_fixes = ns.score(GOOD_NOTE)
    bad, _, bad_fixes = ns.score(BAD_NOTE)
    assert 0 <= bad < good <= 100, (bad, good)
    assert good >= 80, (good, good_fixes)
    assert bad < 60, (bad, bad_fixes)


@check("评分：差笔记会给出结构化改进项")
def _():
    _, _, fixes = ns.score(BAD_NOTE)
    joined = " ".join(fixes)
    assert "标题候选" in joined, fixes
    assert "标签" in joined, fixes


@check("评分：合规命中会扣分并提示")
def _():
    dirty = GOOD_NOTE.replace("租房党别再买贵的收纳了", "全网最低价收纳盒")
    clean, _, _ = ns.score(GOOD_NOTE)
    scored, _, fixes = ns.score(dirty)
    assert scored < clean, (scored, clean)
    assert any("高风险" in f for f in fixes), fixes


@check("时间轴：多个商品各占独立时段且首尾衔接")
def _():
    rows = lt.build(30, ["A", "B", "C"])
    prod_rows = [r for r in rows if r["item"]]
    assert len(prod_rows) == 3, rows
    assert len({(r["start"], r["end"]) for r in prod_rows}) == 3, prod_rows
    assert all(r["start"] == prev["end"] for prev, r in zip(rows, rows[1:])), rows
    assert rows[0]["start"] == "00:00" and rows[-1]["end"] == "30:00", rows


@check("渲染：各脚本文本输出均可正常生成")
def _():
    assert "结论" in sc.render_text(sc.compute(price=89, cost=32, shipping=6, commission=0.2))
    batch = [dict(sc.compute(price=89, cost=32, shipping=6, commission=0.2), name="测试品")]
    assert "测试品" in sc.render_batch_text(batch)
    assert "合规自检结果" in cc.render_text(cc.scan("全网最低价"), "test")
    assert "结论：blocked" in cc.render_text(cc.scan("全网最低价"), "test", ["food"])
    assert "直播时间轴" in lt.render_md(lt.build(30, ["A"]), 30, ["A"])
    total, details, fixes = ns.score(GOOD_NOTE)
    assert "总分" in ns.render_text(total, details, fixes, "test")


@check("渲染：零命中时 CSV 只输出表头")
def _():
    csv_text = cc.render_csv(cc.scan("干净的一句话"))
    assert csv_text.strip().splitlines() == ["level,category,term,line,column,advice,context"], csv_text


def main(argv):
    verbose = "-v" in argv or "--verbose" in argv
    passed, failed = 0, []
    for name, fn in CHECKS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - 自测需要捕获全部异常
            failed.append((name, "{}: {}".format(type(exc).__name__, exc)))
            if verbose:
                print("FAIL  {}".format(name))
        else:
            passed += 1
            if verbose:
                print("ok    {}".format(name))

    print("=" * 58)
    print("selftest: {} passed, {} failed, {} total".format(passed, len(failed), len(CHECKS)))
    for name, reason in failed:
        print("  FAIL {} -> {}".format(name, reason))
    print("=" * 58)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
