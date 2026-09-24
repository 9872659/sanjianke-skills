#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档问答 / PDF 内容提取 —— 零安装版（走平台 file_qa/chat）。

原先要用这个 Skill，得先 pip install marker-pdf 和它的 PyTorch，**再准备一个能跑的
推理后端**：NVIDIA 卡上是 Docker + NVIDIA Container Toolkit + vLLM，CPU / Apple
Silicon 上是 llama.cpp 的 llama-server；首次运行还要下模型权重。只想「问问这份 PDF
里写了什么」的话，这层前置实在太重了。

现在本机只要求 Python 3.8+：把文档的公网地址和问题提交给 api.a7w.cn，直接拿回答案。

=========================  必读限制（先说清楚）  ========================

【file_qa 只吃公网 HTTP(S) 地址，不支持本地文件上传】
    实测 `file_qa/chat` 的入参是 `file_urls`（数组）+ `question`，**没有任何文件字段**，
    平台文档也写明了：客户端只需提交 URL，不支持上传文件、Base64 或本地路径。
    所以 `--url` 必须是一个**公网服务器能直接 GET 到**的地址，
    形如 https://.../论文.pdf ；你本机的 C:\\Users\\...\\论文.pdf 是传不进去的。

【怎么先拿到公网 URL】（下面「零安装用法」里也有一份，任选一种）
    1) 对象存储：阿里云 OSS / 腾讯云 COS / 七牛 / MinIO / AWS S3，
       上传后取**公开读直链**或带签名的临时直链。最稳，适合批量。
    2) 临时分享站（几十 MB 的小文件够用）：
       curl -F "file=@论文.pdf" https://0x0.st          # 返回一行纯文本直链
       curl -T 论文.pdf https://transfer.sh/论文.pdf     # 返回一行直链
       curl -F "file=@论文.pdf" https://tmpfiles.org/api/v1/upload
       注意：这类站点有的会给出一个**预览页**地址，要取真正的文件直链。
    3) 你已有的静态站点 / GitHub Pages / 发布一个 Release 附件，都是可用的直链。
    4) 内网文档：用 frp / ngrok / cloudflared 之类的隧道，把本机一个 HTTP 目录
       （`python -m http.server 8000`）临时映射成公网地址。
    5) 网盘分享页**不行**：需要登录、需要 cookie、或返回的是 HTML 预览页的，
       平台抓不到正文。要的是「丢进浏览器就能直接下载」的那种地址。

用法
    python3 run.py --url https://example.com/论文.pdf "这篇论文的核心贡献是什么"
    python3 run.py --url https://example.com/a.pdf --url https://example.com/b.pdf "两篇的方法差异"
    python3 run.py --url https://example.com/财报.pdf "把关键财务数据整理成表格" -o 答案.md
    python3 run.py --url https://example.com/扫描件.pdf "逐页提取正文" --mode task   # 转异步，避免长连接被掐

第一次使用需要配 Key（三种方式任选）：
    python3 run.py --url ... "问题" --key sk-xxxx
    set A7W_API_KEY=sk-xxxx            # Windows；Linux/macOS 用 export
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

输出约定
    · stdout：一行 JSON（给 Agent / 程序解析），含 answer / url / question / points_cost
    · stderr：答案正文与人类可读的进度、统计信息

计费：`file_qa/chat` 按 Token 计价（参考：输入 2600 点/百万 Token、
输出 13000 点/百万 Token），返回里带 `points_cost`，以平台实时价为准。

能力边界（平台接口做不到的）
    · 不能传本地文件：只接受公网 HTTP(S) 地址，没有文件上传 / Base64 / 本地路径的入口。
    · 不返回版面结构：`chat` 给的是**自然语言答案**，拿不到 marker 那种「块类型 / 坐标 /
      章节层级」的 JSON 树，也没有「表格 → 结构化数组」的直接输出。
    · 不做版式还原、不输出可编辑的 Office 文件。
    · 不保证 100% 准确：复杂嵌套表格与表单仍可能出错，需要人工抽检。
    · 文档页数 / 体积上限以平台为准；超长文档建议拆开或改用 --mode task。
"""


import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "file_qa"
API = "chat"
SLUG = "sanjianke-marker"
MAX_URLS = 8
MAX_QUESTION = 20000

GET_URL_HINT = (
    "怎么拿到公网 URL（任选一种）：\n"
    "  1) 对象存储：阿里云 OSS / 腾讯云 COS / 七牛 / MinIO / AWS S3，上传后取公开读直链；\n"
    "  2) 临时分享站：curl -F \"file=@报告.pdf\" https://0x0.st\n"
    "                 curl -T 报告.pdf https://transfer.sh/报告.pdf\n"
    "  3) 已有的静态站点 / GitHub Pages / Release 附件；\n"
    "  4) 内网文档：cloudflared / ngrok / frp 把 `python -m http.server 8000` 映射成公网地址。\n"
    "  网盘分享页、需要登录或需要 cookie 的地址不行——平台抓不到正文。\n")


def check_urls(urls):
    """挑出明显不合规的地址，给出中文可读的原因。"""
    bad = []
    for u in urls:
        low = u.strip().lower()
        if not (low.startswith("http://") or low.startswith("https://")):
            bad.append((u, "不是 HTTP(S) 地址。本地路径传不进去："
                           "file_qa 只接受公网 URL，不支持上传文件或本地路径。"))
    return bad


def main():
    ap = argparse.ArgumentParser(
        description="文档问答 / PDF 内容提取：把公网文档地址和问题交给 api.a7w.cn（零安装）",
        epilog="注意：file_qa 只接受公网 HTTP(S) 文档地址，不支持本地文件上传。")
    ap.add_argument("question", nargs="?", help="要问这份文档的问题（最多 20000 字符）")
    ap.add_argument("--url", action="append", metavar="公网URL",
                    help="文档的公网 HTTP(S) 地址，可重复传，最多 {} 个".format(MAX_URLS))
    ap.add_argument("--mode", default="sync", choices=["sync", "task", "async"],
                    help="sync 同步返回（默认）；task/async 转异步任务再轮询，长文档更稳")
    ap.add_argument("--timeout", type=float, default=float(a7w.POLL_TIMEOUT),
                    help="异步模式下的轮询上限秒数，默认 %(default)s")
    ap.add_argument("-o", "--out", metavar="文件", help="把答案写入指定文件")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    if not a.url:
        ap.error("必须用 --url 给至少一个公网文档地址。\n" + GET_URL_HINT)
    if not a.question:
        ap.error("请给出要问的问题，例如：python3 run.py --url https://example.com/a.pdf \"这份文档讲了什么\"")
    if len(a.url) > MAX_URLS:
        ap.error("最多一次传 {} 个文档地址，现在传了 {} 个".format(MAX_URLS, len(a.url)))

    bad = check_urls(a.url)
    if bad:
        for u, why in bad:
            sys.stderr.write("地址不合格：{}\n  原因：{}\n".format(u, why))
        sys.stderr.write(GET_URL_HINT)
        return 3

    if len(a.question) > MAX_QUESTION:
        ap.error("问题超过 {} 字符，平台会拒绝。请精简。".format(MAX_QUESTION))

    body = {"file_urls": a.url, "question": a.question, "stream": False}
    if a.mode != "sync":
        body["mode"] = a.mode

    sys.stderr.write("文档 {} 个，模式 {}，提交中…\n".format(len(a.url), a.mode))
    for u in a.url:
        sys.stderr.write("  · {}\n".format(u))
    try:
        data = a7w.call(APP, API, body, key=a.key, timeout=a.timeout)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        sys.stderr.write("如果报的是取文档失败 / 无法访问，先自己用浏览器打开这个地址确认：\n"
                         "要能被公网直接下载，不能是需要登录的页面或网盘分享页。\n"
                         + GET_URL_HINT)
        return 4

    # 同步返回：{result:{answer,usage}, usage:{...}}；
    # 异步走完后 a7w.call 返回：{task_id,status,result:{answer,usage},usage:{...}}
    # 两种形状里 answer 都在 data.result.answer，所以统一从那里取。
    usage = a7w.dig(data, "usage") or {}
    answer = (a7w.dig(data, "result", "answer") or a7w.dig(data, "answer") or "").strip()
    tokens = a7w.dig(data, "result", "usage") or {}

    if not answer:
        sys.stderr.write("接口没返回答案字段，原始返回如下：\n{}\n"
                         .format(json.dumps(data, ensure_ascii=False, indent=2)))
        print(json.dumps({"ok": False, "stage": "parse", "urls": a.url,
                          "question": a.question, "response": data},
                         ensure_ascii=False))
        return 5

    cost = a7w.dig(usage or {}, "points_cost") or a7w.dig(usage or {}, "actual_points")

    sys.stderr.write("\n----- 答案 ｜ {} 字 ｜ 消耗 {} 点 -----\n{}\n-----\n".format(
        len(answer), cost if cost is not None else "?", answer))

    if a.out:
        Path(a.out).write_text(answer + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))

    # 给 Agent 解析用：stdout 只有这一行 JSON
    print(json.dumps({
        "ok": True,
        "slug": SLUG,
        "urls": a.url,
        "question": a.question,
        "mode": a.mode,
        "chars": len(answer),
        "answer": answer,
        "input_tokens": a7w.dig(tokens or {}, "input_tokens"),
        "output_tokens": a7w.dig(tokens or {}, "output_tokens"),
        "total_tokens": a7w.dig(tokens or {}, "total_tokens"),
        "points_cost": cost,
        "out": str(Path(a.out).resolve()) if a.out else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
