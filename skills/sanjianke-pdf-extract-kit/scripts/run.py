#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档解析问答 —— 零安装版（就着一份公网文档提问）。

原先要用这个 Skill，得 conda 建环境、装 Paddle / Ultralytics / PyMuPDF、从
HuggingFace 下模型权重，而且表格识别必须要有 NVIDIA 显卡。现在不需要：文档留在
公网，问题送到 api.a7w.cn 就出答案，本机只要求有 Python 3.8+。

用法
    python3 run.py --url https://example.com/report.pdf "这份文档里的表格列了什么？"
    python3 run.py --url https://example.com/scan.pdf --focus ocr          # 按任务的问法
    python3 run.py --url https://example.com/paper.pdf --focus formula "顺便说下有哪些符号定义"
    python3 run.py --url https://example.com/a.pdf --url https://example.com/b.pdf "两份文档的表格字段差异"
    python3 run.py https://example.com/report.pdf "版面里有没有跨页表格"      # 地址可为位置参数
    python3 run.py --url https://example.com/report.pdf -o 答案.md "把结论整理成要点"

--focus 取值（只是把问题换成对应任务的问法，**不是**真的调用那 5 个模型）
    auto     默认，用你自己写的问题
    layout   问版面结构：标题 / 正文 / 表格 / 图片各有哪些
    ocr      问原文文字：尽量完整按顺序输出文字，不要总结
    table    问表格：逐个还原行列内容
    formula  问公式：尽量给出对应 LaTeX
    summary  问要点：主题、核心结论、关键数据

第一次使用需要配 Key（三种方式任选）：
    python3 run.py --url ... "问题" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

重要限制（务必先看清）
    · file_qa **只接受公网 HTTP/HTTPS 文档地址**：不支持上传本地文件，也不支持
      Base64 或本地路径。本机文件要先放到任何可公网访问的位置（对象存储、网盘
      直链、自己的服务器、静态站点），拿到 https:// 地址再传进来。
    · 这是**问答式**接口，不是「PDF 解析成结构化结果」：不像本项目那样单独调用
      版面检测 / 公式识别 / OCR / 表格识别这 5 个模型，拿不到区块坐标框、LaTeX
      公式串、HTML 表格这类机器可读产物，也不做内容重组（那本来是 MinerU 的活）。
    · 平台 schema 里声明的 `stream`（SSE 流式）实测不可用：传 stream=true 会直接
      返回 {"code":0,"msg":"任务处理失败，请稍后重试"}，所以本脚本统一等完整答案。

计费：输入 2,600 点/百万 Token、输出 13,000 点/百万 Token（以平台实时价为准）。
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "file_qa"
API = "chat"
MAX_URLS = 8
MAX_QUESTION = 20000
DOC_EXT = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".html", ".htm",
           ".ppt", ".pptx", ".xls", ".xlsx", ".csv"}

LOCAL_HINT = (
    "file_qa 只接受公网 HTTP/HTTPS 文档地址，不支持上传本地文件、Base64 或本地路径。\n"
    "  怎么办：先把文档放到任何一个可公网访问的位置（对象存储 / 网盘直链 / 自己的\n"
    "  服务器 / 静态站点），拿到 https:// 开头的地址再传进来。")

# 把「原项目的 5 个小任务」翻译成问答接口能听懂的问法。
FOCUS = {
    "auto": None,
    "layout": "请说明这份文档的版面结构：有哪些标题、正文段落、表格、图片，"
              "各自大致出现在什么位置、起什么作用。按页面顺序说。",
    "ocr": "请把这份文档里的文字内容尽可能完整地识别出来，按原文顺序输出纯文本，"
           "不要总结、不要省略。",
    "table": "请把这份文档里的表格逐个列出来，用 Markdown 表格还原每一行每一列的内容；"
             "没有表格就明确说明没有。",
    "formula": "请把这份文档里出现的公式逐个列出来，尽量给出对应的 LaTeX 写法；"
               "没有公式就明确说明没有。",
    "summary": "请用要点总结这份文档：主题是什么、核心结论有哪些、关键数据和结论"
               "分别落在哪几页。",
}


def pick(data, *paths):
    """按顺序找第一个非空的返回字段——同步/异步两种返回结构都兼容。"""
    for p in paths:
        v = a7w.dig(data, *p)
        if v not in (None, "", [], {}):
            return v
    return None


def main():
    ap = argparse.ArgumentParser(
        description="就着一份公网文档提问（走 api.a7w.cn 的 file_qa/chat，零安装）",
        epilog="注意：只支持公网 HTTP/HTTPS 文档地址，不支持本地文件上传。")
    ap.add_argument("question", nargs="*",
                    help="要问的问题（写成多个词会拼成一句；也可以直接给 http(s) 地址）")
    ap.add_argument("--url", action="append", default=[],
                    help="公网文档地址，可重复传多个（最多 {} 个）".format(MAX_URLS))
    ap.add_argument("--focus", default="auto", choices=sorted(FOCUS),
                    help="按任务换问法：auto / layout / ocr / table / formula / summary")
    ap.add_argument("--question-file", help="从文本文件读取问题（问题很长时用这个）")
    ap.add_argument("--mode", default="sync", choices=["sync", "async", "task"],
                    help="sync=同步等完整答案（默认）；async/task=提交异步任务并自动轮询（平台两种写法等价）")
    ap.add_argument("-o", "--out", help="把答案写入指定文件")
    ap.add_argument("--plain", action="store_true", help="stdout 只打印答案正文，不打 JSON")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    urls = list(a.url)
    words = []
    for item in a.question:
        if re.match(r"^https?://", item, re.I):
            urls.append(item)
        else:
            words.append(item)
    question = " ".join(words).strip()
    if a.question_file:
        try:
            extra = Path(a.question_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            sys.stderr.write("读不到问题文件：{}\n".format(exc))
            return 2
        question = (question + "\n" + extra).strip() if question else extra

    preset = FOCUS[a.focus]
    if preset:
        question = preset if not question else preset + "\n\n另外： " + question
        sys.stderr.write("--focus {}：已按这个任务的问法提问。\n".format(a.focus))

    bad = [u for u in urls if not re.match(r"^https?://", u, re.I)]
    if bad:
        sys.stderr.write("这个地址不能传：{}\n  {}".format(bad[0], LOCAL_HINT))
        if Path(bad[0]).exists():
            sys.stderr.write("\n（它在你本机是存在的，但平台读不到本机文件。）")
        sys.stderr.write("\n")
        return 2

    urls = list(dict.fromkeys(urls))            # 去重，保持顺序
    if not urls:
        sys.stderr.write("没有可用的文档地址。用法：run.py --url <公网文档URL> \"问题\"\n")
        local = [w for w in words
                 if Path(w).is_file() or Path(w).suffix.lower() in DOC_EXT]
        if local:
            sys.stderr.write("你给的是「{}」，看起来是本地文件路径。\n  {}\n"
                             .format(local[0], LOCAL_HINT))
        else:
            sys.stderr.write("  {}\n".format(LOCAL_HINT))
        return 2
    if len(urls) > MAX_URLS:
        sys.stderr.write("一次最多 {} 个文档地址，现在给了 {} 个。\n"
                         .format(MAX_URLS, len(urls)))
        return 2
    if not question:
        sys.stderr.write("还没写问题。用法：run.py --url <公网文档URL> \"你的问题\"\n")
        return 2
    if len(question) > MAX_QUESTION:
        sys.stderr.write("问题太长（{} 字符），接口上限 {} 字符。\n"
                         .format(len(question), MAX_QUESTION))
        return 2

    body = {"file_urls": urls, "question": question, "mode": a.mode}
    try:
        data = a7w.call(APP, API, body, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    answer = pick(data, ("result", "answer"), ("answer",),
                  ("result", "result", "answer"), ("result", "text"), ("text",))
    if not answer:
        sys.stderr.write("接口没返回答案字段，原始返回已打到 stdout，请照原样反馈。\n")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 5

    tin = pick(data, ("result", "usage", "input_tokens"), ("usage", "input_tokens"))
    tout = pick(data, ("result", "usage", "output_tokens"), ("usage", "output_tokens"))
    points = pick(data, ("usage", "actual_points"), ("usage", "points_cost"),
                  ("result", "usage", "actual_points"), ("result", "usage", "points_cost"))

    if a.out:
        try:
            Path(a.out).write_text(str(answer).rstrip() + "\n", encoding="utf-8")
        except OSError as exc:
            sys.stderr.write("答案已经拿到了，但写文件失败：{}\n".format(exc))
            return 6

    # 人类可读的信息走 stderr
    sys.stderr.write("\n----- 回答 -----\n{}\n---------------\n".format(answer))
    sys.stderr.write("文档 {} 个｜focus {}｜模式 {}｜输入 {} tokens｜输出 {} tokens｜"
                     "消耗 {} 点{}\n"
                     .format(len(urls), a.focus, a.mode,
                             tin if tin is not None else "?",
                             tout if tout is not None else "?",
                             points if points is not None else "?",
                             "｜已写入 " + str(a.out) if a.out else ""))

    if a.plain:
        print(answer)
    else:
        print(json.dumps({"ok": True, "answer": answer, "chars": len(str(answer)),
                          "file_urls": urls, "focus": a.focus, "mode": a.mode,
                          "input_tokens": tin, "output_tokens": tout,
                          "points_cost": points,
                          "out": str(Path(a.out).resolve()) if a.out else None},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
