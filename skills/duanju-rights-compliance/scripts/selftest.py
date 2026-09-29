#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内置自测：验证合规扫描脚本的核心行为。

不需要联网、不需要第三方包、不写盘（自定义规则用例使用临时目录）。

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

import duanju_compliance as dc   # noqa: E402
import run as rp                 # noqa: E402  导入不联网：网络调用只在 run.main() 里

CHECKS = []

# 七类规则各一个代表词，用于覆盖度测试
CATEGORY_SAMPLES = {
    "全集承诺": "全集免费",
    "独家宣称": "全网独播",
    "擦边引流": "大尺度",
    "暴力血腥": "血腥",
    "盗版搬运": "网盘",
    "收益诱导": "看剧赚钱",
    "极限词": "最好看",
}


def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


@check("规则覆盖：七类高危规则各自都能命中")
def _():
    missing = []
    for category, sample in CATEGORY_SAMPLES.items():
        findings = dc.scan(sample)
        if not any(f["category"] == category for f in findings):
            missing.append(category)
    assert not missing, "以下类别未命中：{}".format("、".join(missing))


@check("规则覆盖：命中项都带等级与建议")
def _():
    for sample in CATEGORY_SAMPLES.values():
        for f in dc.scan(sample):
            assert f["level"] in ("high", "medium", "low"), f
            assert f["advice"], "命中项缺少建议：{}".format(f)


@check("合规：一句典型违规文案命中多个高风险")
def _():
    findings = dc.scan("全集免费未删减，大尺度激情，加微信发资源")
    terms = {f["term"] for f in findings}
    assert "全集免费" in terms, terms
    assert "未删减" in terms, terms
    assert "大尺度" in terms, terms
    assert "微信" in terms, terms
    assert dc.summarize(findings)["high"] >= 4, findings


@check("合规：干净文案不产生高风险命中")
def _():
    findings = dc.scan("她推开那扇门，才发现三年前的真相。继续看下去，答案在第 12 集。")
    assert dc.summarize(findings)["high"] == 0, findings
    assert dc.verdict(findings)[0] == "pass", findings


@check("合规：verdict 分级正确")
def _():
    assert dc.verdict(dc.scan("全网独播"))[0] == "blocked"
    assert dc.verdict(dc.scan("私信"))[0] == "review"
    assert dc.verdict(dc.scan("最近更新"))[0] in ("check", "review")


@check("合规：类目规则可叠加")
def _():
    base = dc.scan("限时最后一天")
    with_cat = dc.scan("限时最后一天", categories=["promotion"])
    assert len(with_cat) >= len(base), (base, with_cat)
    assert any(f["category"] == "推广话术" for f in with_cat), with_cat


@check("合规：三个类目都可用")
def _():
    for cat in sorted(dc.CATEGORY_TERMS):
        findings = dc.scan("测试文本", categories=[cat])
        assert isinstance(findings, list), cat


@check("合规：自定义规则文件可合并")
def _():
    payload = {
        "terms": [{"category": "私有", "level": "high", "term": "内部黑话", "advice": "删除"}],
        "regex": [{"category": "私有", "level": "medium", "pattern": "DJ-\\d+", "label": "内部编号"}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rules.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        terms, regexes = dc.load_custom_rules(path)
    assert len(terms) == 1 and len(regexes) == 1
    findings = dc.scan("内部黑话 DJ-123", extra_terms=terms, extra_regexes=regexes)
    assert {f["term"] for f in findings} >= {"内部黑话", "内部编号"}, findings


@check("合规：非法自定义等级会被拒绝")
def _():
    payload = {"terms": [{"category": "私有", "level": "critical", "term": "x"}]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rules.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            dc.load_custom_rules(path)
        except SystemExit:
            return
    raise AssertionError("非法 level 未被拒绝")


@check("合规：正则规则可识别手机号与站外链接")
def _():
    findings = dc.scan("联系我 13800138000，或者看 https://example.com/x")
    terms = {f["term"] for f in findings}
    assert "疑似手机号" in terms, terms
    assert "疑似站外链接" in terms, terms


@check("合规：CSV 输出含表头且行数正确")
def _():
    findings = dc.scan("全集免费，大尺度")
    lines = dc.render_csv(findings).strip().splitlines()
    assert lines[0].startswith("level,category,term"), lines[0]
    assert len(lines) == len(findings) + 1, (len(lines), len(findings))


@check("合规：零命中时 CSV 只输出表头")
def _():
    csv_text = dc.render_csv(dc.scan("一句干净的话"))
    assert csv_text.strip().splitlines() == ["level,category,term,line,column,advice,context"], csv_text


@check("合规：同一行同一词只报一次")
def _():
    findings = dc.scan("未删减未删减未删减")
    assert len([f for f in findings if f["term"] == "未删减"]) == 1, findings


@check("渲染：文本报告可正常生成")
def _():
    assert "blocked" in dc.render_text(dc.scan("全集免费"), "test")
    assert "pass" in dc.render_text(dc.scan("一句干净的话"), "test")


@check("渲染：规则表与说明可正常生成")
def _():
    assert "规则" in dc.render_rules()
    assert "免责" in dc.render_explain()


@check("渲染：报告含命中位置")
def _():
    text = dc.render_text(dc.scan("第一行\n第二行有大尺度"), "test")
    assert "第 2 行" in text, text


# ------------------------------------------------- 算力版脚本的纯逻辑（离线）
# `run.py` 里只有「把这一批文案 POST 出去」那一步需要网络；解析、合并、输入读取、
# 渲染都是纯函数，这里全部离线验证（自定义规则/CSV 用例用临时目录）。
@check("算力版：模型输出能解析成 JSON 数组")
def _():
    # 实测踩坑：模型会在合法 JSON 后面多吐一两个字符；也可能包在对象里
    assert rp.parse_json_array('[{"index": 1}]"') == [{"index": 1}]
    assert rp.parse_json_array('```json\n[{"index": 2}]\n```') == [{"index": 2}]
    assert rp.parse_json_array('好的：{"items": [{"index": 3}]} 以上') == [{"index": 3}]
    assert rp.parse_json_array('[{"index": 3}') is None      # 截断时不得抛异常、不得瞎猜
    assert rp.parse_json_array("完全不是 JSON") is None


@check("算力版：等级归一化与兜底")
def _():
    ok = rp.normalize_judgment({"index": 1, "level": "HIGH", "categories": "擦边",
                                "reason": "理由", "rewrite": "改写"}, 1)
    assert ok["level"] == "high" and ok["level_ok"] is True, ok
    assert ok["categories"] == ["擦边"], ok
    bad = rp.normalize_judgment({"index": 2, "level": "critical"}, 2)
    assert bad["level"] == "low" and bad["level_ok"] is False, bad
    clean = rp.normalize_judgment({"index": 3, "level": "pass", "rewrite": "不该有"}, 3)
    assert clean["rewrite"] == "", clean
    assert rp.normalize_judgment("不是对象", 4) is None


@check("算力版：本地命中与模型判定取更高等级")
def _():
    high = {"level": "high", "terms": [], "advice": [], "categories": []}
    pass_ = {"level": "pass", "terms": [], "advice": [], "categories": []}
    med = {"level": "medium", "terms": [], "advice": [], "categories": []}
    assert rp.merge(high, {"level": "pass"})[0] == "high"
    assert rp.merge(pass_, {"level": "medium"})[0] == "medium"
    assert rp.merge(pass_, {"level": "medium"})[1] == ["大模型"]
    assert rp.merge(pass_, None)[0] == "pass"
    assert rp.merge(med, None)[1] == ["本地正则"]


@check("算力版：离线粗筛能给出等级与命中词")
def _():
    local = rp.local_scan("全集免费未删减", None, [], [])
    assert local["level"] == "high", local
    assert "全集免费" in [t for t, _lv in local["terms"]], local
    assert rp.local_scan("一句干净的话", None, [], [])["level"] == "pass"


@check("算力版：verdict 分级与 CSV 表头")
def _():
    items = [{"index": 1, "text": "x", "local": {"level": "high", "terms": [("全集免费", "high")],
                                                 "advice": [], "categories": []},
              "llm": None, "final_level": "high", "sources": ["本地正则"]}]
    s = rp.summarize(items, [])
    assert s["verdict"] == "blocked" and s["high"] == 1, s
    csv_text = rp.render_csv(items)
    assert csv_text.splitlines()[0] == ",".join(rp.CSV_COLUMNS), csv_text


@check("算力版：CSV --column 与 txt 输入都能读")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "a.csv"
        csv_path.write_text("id,title,text\n1,反转,她推开门\n2,独家,全网独播\n", encoding="utf-8")
        args = rp.build_parser().parse_args(["screen", "--file", str(csv_path), "--column", "text"])
        items, sources = rp.read_items(args)
        assert items == ["她推开门", "全网独播"], items
        assert sources and sources[0].endswith("a.csv"), sources

        txt_path = Path(tmp) / "b.txt"
        txt_path.write_text("# 注释\n干净的一句\n\n全集免费\n", encoding="utf-8")
        args2 = rp.build_parser().parse_args(["screen", "--file", str(txt_path)])
        items2, _ = rp.read_items(args2)
        assert items2 == ["干净的一句", "全集免费"], items2


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
