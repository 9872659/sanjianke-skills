#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本技能的内置自测。验证全部脚本的核心行为。

不需要 ffmpeg、不联网、不写盘（自定义规则用例用临时目录）。
涉及 ffmpeg 的部分只测纯逻辑（dHash / 汉明距离 / 相似度 / 时长正则），
不实际调用二进制。

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
import frame_dedup as fd         # noqa: E402

CHECKS = []


def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


# ---------------------------------------------------------------- 文案合规
@check("合规：命中全集承诺 / 擦边 / 盗版导流")
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


@check("合规：类目规则叠加生效")
def _():
    base = dc.scan("限时最后一天")
    with_cat = dc.scan("限时最后一天", categories=["promotion"])
    assert len(with_cat) >= len(base), (base, with_cat)
    assert any(f["category"] == "推广话术" for f in with_cat), with_cat


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


@check("渲染：合规报告可正常生成")
def _():
    assert "blocked" in dc.render_text(dc.scan("全集免费"), "test")
    assert "规则" in dc.render_rules()
    assert "免责" in dc.render_explain()


# ---------------------------------------------------------------- 查重工具
def _frame(values):
    """把 72 个像素值打包成 9x8 灰度帧。"""
    assert len(values) == fd.FRAME_BYTES
    return bytes(values)


@check("查重：dHash 递增行全 0、递减行全 1")
def _():
    increasing = _frame([c for _r in range(fd.HASH_H) for c in range(fd.HASH_W)])
    assert fd.dhash(increasing) == 0, bin(fd.dhash(increasing))
    decreasing = _frame([fd.HASH_W - c for _r in range(fd.HASH_H) for c in range(fd.HASH_W)])
    assert fd.dhash(decreasing) == (1 << 64) - 1, bin(fd.dhash(decreasing))


@check("查重：汉明距离正确")
def _():
    assert fd.hamming(0, 0) == 0
    assert fd.hamming(0, 0b1011) == 3
    assert fd.hamming((1 << 64) - 1, 0) == 64


@check("查重：完全相同集合相似度为 100%")
def _():
    hashes = [0b1010, 0b0101, 0b1111, 0b0000]
    sim, matched = fd.similarity(hashes, list(hashes), 0)
    assert sim == 1.0 and matched == 4, (sim, matched)


@check("查重：完全不同集合相似度为 0%")
def _():
    a = [0b1111111111111111, 0b0000000000000000]
    b = [0b1111111100000000, 0b0000000011111111]
    sim, matched = fd.similarity(a, b, 0)
    assert sim == 0.0 and matched == 0, (sim, matched)


@check("查重：部分重合相似度按较短者计算")
def _():
    a = [0b0001, 0b0010, 0b0100, 0b1000]
    b = [0b0001, 0b0010, 0b1111, 0b1110]
    sim, matched = fd.similarity(a, b, 0)
    assert matched == 2, matched
    assert abs(sim - 0.5) < 1e-9, sim


@check("查重：贪心配对不重复计同一帧")
def _():
    # A 的两帧都能匹配 B 的同唯一一帧 → 只能算 1 次
    a = [0b1010, 0b1010]
    b = [0b1010]
    _, matched = fd.similarity(a, b, 0)
    assert matched == 1, matched


@check("查重：汉明距离容差生效")
def _():
    a = [0b0000]
    b = [0b0001]
    assert fd.similarity(a, b, 0)[1] == 0
    assert fd.similarity(a, b, 1)[1] == 1


@check("查重：空集合不抛异常")
def _():
    assert fd.similarity([], [0b1], 0)[0] == 0.0
    assert fd.similarity([0b1], [], 0)[0] == 0.0
    assert fd.similarity([], [], 0)[0] == 0.0


@check("查重：ffmpeg 时长正则解析正确")
def _():
    m = fd.DURATION_RE.search("  Duration: 00:03:01.23, start: 0.000000, bitrate: 5095 kb/s")
    assert m, "正则未匹配"
    hours, minutes, seconds = m.groups()
    assert int(hours) * 3600 + int(minutes) * 60 + float(seconds) == 181.23
    assert fd.DURATION_RE.search("no duration here") is None


@check("查重：二进制可用性判断")
def _():
    assert fd.binary_usable("") is False
    assert fd.binary_usable(None) is False
    assert fd.binary_usable("C:\\definitely\\not\\here\\ffmpeg.exe") is False


@check("查重：报告渲染可正常生成")
def _():
    results = {"a.mp4": {"hashes": [0b1, 0b10], "duration": 180.0},
               "b.mp4": {"hashes": [0b1, 0b10], "duration": 181.0}}
    text = fd.render_text(results, [("a.mp4", "b.mp4", 1.0, 2)], {}, 0.4, 24)
    assert "相似度" in text and "处理建议" in text, text
    empty = fd.render_text(results, [], {}, 0.4, 24)
    assert "未发现超过阈值" in empty, empty


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
