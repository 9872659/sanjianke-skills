#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · GPT Image 2.6 出图台

走 api.a7w.cn 的 **GPT Image 2.6**（OpenAI Images API 兼容，**同步调用**）。

## 权威规格（取自网关文档 /docs/gpt-image-2-6-xt）

  接口根地址   https://api.a7w.cn/api/v1
  文生图       POST /images/generations   （JSON）
  图生图       POST /images/edits         （multipart/form-data）
  模型 ID      gpt-image-2.6
  单价         **6 点/张（¥0.06）**，按张计费，与尺寸/质量/格式无关
  计费口径     按 `data` 里**实际返回的张数**；参数错 / 失败 / 没出图 → **不扣费**
  返回         `data[].b64_json` 或 `data[].url`（两种都要处理）
  图片链接     有效期约 3 小时；**原样使用**（追加查询参数会 404）
  `n`          1–4，默认 1
  `size`       auto（默认）/ 1k / 2k / 4k / 宽x高
  `output_format`  png（默认）/ jpeg / webp / gif
  超时建议     180 秒以上（一张图通常 20–50 秒）

## 为什么有这一层

网关文档够清楚，但**用户真正会踩的坑在"钱"和"路径"上**：

  · 端点少了 `/api` 前缀（`/v1/images/generations` 在网关上会被忽略 model、落到默认应用）
  · 不知道 6 点/张，以为很贵不敢试
  · 返回是 `b64_json` 而不是 URL，直接找 `["data"][0]["url"]` 会拿到空
  · 图片链接 3 小时过期，没及时下载就没了

本包把这些做成默认动作：`cost` 先报钱（6 点/张），`--budget` 是第一道闸门，
`--outdir` 自动把 b64/URL 都落成文件，`gen` 结束打印**实际返回张数**与**实际点数**。

## 子命令

  models   图片模型清单（免费）
  cost     先算钱（免费）
  doctor   自检 Key / 端点 / 模型（免费，不扣费）
  gen      文生图（6 点/张，要 --yes）
  edit     图生图（multipart，要 --yes）
  log      本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --n 4
  python3 scripts/run.py gen  --prompt "一只橘猫在窗台晒太阳" --size 1024x1024 --yes
  python3 scripts/run.py gen  --prompt "一只橘猫在挥手" --gif --yes
  python3 scripts/run.py edit --prompt "把帽子戴到猫头上" --image cat.png --image hat.png --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题可加技术微信 技术微信。
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid


# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 `√`/`×` 这类 cp936 编不出的字符就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底，再把这类字符换掉，输出才不会变 `?`。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_MODEL = "gpt-image-2.6"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
POINTS_PER_IMAGE = 6
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "gpt-image-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-gpt-image/%s" % VERSION


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def load_conf(explicit_key=None, explicit_host=None):
    key = None
    if explicit_key:
        key = explicit_key.strip()
    if not key:
        key = (os.environ.get("A7W_API_KEY") or "").strip() or None
    host = (explicit_host or "").strip().rstrip("/") or None
    cfg = os.path.join(os.path.expanduser("~"), ".a7w", "config.json")
    if (not key or not host) and os.path.isfile(cfg):
        try:
            d = json.load(io.open(cfg, encoding="utf-8"))
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                        # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=240):
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=300):
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in fields.items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    for name, path in files:
        fn = os.path.basename(path)
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                   "Content-Type: %s\r\n\r\n" % (boundary, name, fn, ctype)).encode("utf-8"))
        buf.write(open(path, "rb").read())
        buf.write(b"\r\n")
    buf.write(("--%s--\r\n" % boundary).encode("utf-8"))
    payload = buf.getvalue()
    req = urllib.request.Request(url, method="POST", data=payload, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json",
        "Content-Type": "multipart/form-data; boundary=" + boundary,
        "Content-Length": str(len(payload)), "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or "", e.get("param") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
    return txt.replace("\n", " ")[:240]


def check_size(size):
    """按文档校验自定义尺寸。返回 (ok, 原因)。"""
    if not size or size in ("auto", "1k", "2k", "4k"):
        return True, ""
    if "x" not in size.lower():
        return False, "size 只能是 auto / 1k / 2k / 4k / 宽x高（例如 1024x1024）"
    try:
        w, h = [int(x) for x in size.lower().split("x", 1)]
    except Exception:                                            # noqa: BLE001
        return False, "size 格式不对：%s" % size
    if w % 16 or h % 16:
        return False, "宽高都必须是 16 的倍数（%dx%d）" % (w, h)
    lo, hi = min(w, h), max(w, h)
    if hi > 3 * lo:
        return False, "长边/短边不能超过 3:1（%dx%d）" % (w, h)
    if max(w, h) > 3840:
        return False, "单边不能超过 3840（%dx%d）" % (w, h)
    px = w * h
    if px < 655360 or px > 8294400:
        return False, "总像素需在 655,360–8,294,400 之间（当前 %d）" % px
    return True, ""


def save_images(d, outdir, prefix, fmt):
    """从响应里取图并落盘。b64 与 url 都处理。返回 (路径列表, 来源)。"""
    os.makedirs(outdir, exist_ok=True)
    paths, src = [], "none"
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, list):
        return paths, src
    for i, it in enumerate(data):
        if not isinstance(it, dict):
            continue
        b64 = it.get("b64_json")
        if b64:
            raw = base64.b64decode(b64)
            ext = fmt or "png"
            if raw[:3] == b"GIF":
                ext = "gif"
            p = os.path.join(outdir, "%s-%02d.%s" % (prefix, i + 1, ext))
            open(p, "wb").write(raw)
            paths.append(p)
            src = "b64_json"
            continue
        u = it.get("url")
        if u:
            # 文档：链接原样使用；下载不需要密钥；urllib 必须自设 UA，否则 403
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as x:
                raw = x.read()
            ext = fmt or "png"
            if raw[:3] == b"GIF":
                ext = "gif"
            p = os.path.join(outdir, "%s-%02d.%s" % (prefix, i + 1, ext))
            open(p, "wb").write(raw)
            paths.append(p)
            src = "url"
    return paths, src


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


# ───────────────────────── 子命令 ─────────────────────────
def cmd_models(a, key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/models", key)
    if st != 200:
        raise Fail("call", "拉模型清单失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    d = jloads(txt) or {}
    data = d.get("data") or d.get("models") or d
    items = []
    if isinstance(data, dict):
        for v in data.values():
            items += v if isinstance(v, list) else [v]
    elif isinstance(data, list):
        items = data
    imgs = [it for it in items if isinstance(it, dict) and it.get("type_code") == "image"]
    rows = [{"model_code": it.get("model_code"), "model_name": it.get("model_name"),
             "参考图上限": it.get("max_reference_images"),
             "说明": (it.get("description") or "")[:50]} for it in imgs]
    out = {"ok": True, "count": len(rows), "models": rows}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("api.a7w.cn 在架图片模型（%d 个）" % len(rows))
    print()
    print("  %-24s %-24s %-7s %s" % ("model_code", "名称", "参考图", "说明"))
    print("  " + "-" * 92)
    for r in rows:
        mark = "  ← 本包默认" if r["model_code"] == DEFAULT_MODEL else ""
        print("  %-24s %-24s %-7s %s%s" % (
            r["model_code"], (r["model_name"] or "")[:22],
            r["参考图上限"], r["说明"][:32], mark))
    return 0


def cmd_cost(a, key, host):
    total = POINTS_PER_IMAGE * a.n
    out = {"ok": True, "n": a.n, "pointsPerImage": POINTS_PER_IMAGE,
           "total": total, "yuan": round(total / 100.0, 2),
           "basis": "文档：6 点/张，按张计费，与尺寸/质量/格式无关"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本")
    print("  模型：%s（按张计费）" % a.model)
    print("  张数：%d × %d 点 = **%d 点 = %.2f 元**"
          % (a.n, POINTS_PER_IMAGE, total, total / 100.0))
    print("  依据：%s" % out["basis"])
    print()
    print("  注意：按 `data` 里**实际返回张数**计费；参数错 / 失败 / 没出图 → 不扣费。")
    return 0


def cmd_doctor(a, key, host):
    checks = []
    st, txt = http_json("GET", host + API_PREFIX + "/models", key)
    checks.append(("Key 有效性 + 模型目录可达", st == 200, "HTTP %s" % st))

    codes = set()
    if st == 200:
        d = jloads(txt) or {}
        data = d.get("data") or d.get("models") or d
        items = []
        if isinstance(data, dict):
            for v in data.values():
                items += v if isinstance(v, list) else [v]
        elif isinstance(data, list):
            items = data
        codes = {it.get("model_code") for it in items if isinstance(it, dict)}
    checks.append(("模型 %s 在架" % DEFAULT_MODEL, DEFAULT_MODEL in codes,
                   "目录共 %d 个" % len(codes)))

    # 端点存在性必须**带 model** 才探得出来（空 {} 会掉到 404 HTML 兜底）。
    # 带 model + 空 prompt → 文档规定的 422「String should have at least 1 character」，不扣费。
    st2, txt2 = http_json("POST", host + API_PREFIX + "/images/generations", key,
                          {"model": DEFAULT_MODEL, "prompt": ""})
    d2 = jloads(txt2) or {}
    e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
    ok2 = st2 == 422 and "at least 1 character" in (e2.get("message") or "")
    checks.append(("文生图端点可用（422 即正确）", ok2,
                   "HTTP %s %s" % (st2, (e2.get("message") or "")[:46])))

    out = {"ok": all(c[1] for c in checks),
           "endpoint": host + API_PREFIX + "/images/generations",
           "pointsPerImage": POINTS_PER_IMAGE,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（不扣费：只读接口 + 空 body 触发参数校验）")
    print()
    for n, o, d in checks:
        print("  %s %-28s %s" % ("√" if o else "×", n, d))
    print()
    print("  端点：%s" % out["endpoint"])
    print("  单价：%d 点/张（¥%.2f）" % (POINTS_PER_IMAGE, POINTS_PER_IMAGE / 100.0))
    return 0 if out["ok"] else EXIT_GATE


def _preflight(a, n, size, fmt, bg):
    ok, why = check_size(size)
    if not ok:
        raise Fail("usage", "尺寸不合法：%s" % why, EXIT_USAGE)
    if bg == "transparent" and fmt in ("jpeg", "gif"):
        raise Fail("usage", "透明背景不能配 %s（文档：只支持 png / webp）" % fmt, EXIT_USAGE)
    if fmt == "svg":
        raise Fail("usage", "不支持 SVG（文档明确 400）", EXIT_USAGE)
    if not (1 <= n <= 4):
        raise Fail("usage", "n 必须是 1–4（文档：expected an integer in [1, 4]）", EXIT_USAGE)
    cost = POINTS_PER_IMAGE * n
    if cost > a.budget:
        raise Fail("budget", "预计 %d 点超过 --budget %d 点。调大 --budget 或减少 --n。"
                   % (cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实出图并扣约 %d 点（%.2f 元）。确认请加 --yes。"
                   % (cost, cost / 100.0), EXIT_CONFIRM)
    return cost


def cmd_gen(a, key, host):
    if not a.prompt:
        raise Fail("usage", "必须给 --prompt", EXIT_USAGE)
    fmt = "gif" if a.gif else a.output_format
    cost = _preflight(a, a.n, a.size, fmt, a.background)
    url = host + API_PREFIX + "/images/generations"
    body = {"model": a.model, "prompt": a.prompt, "n": a.n}
    if a.size and a.size != "auto":
        body["size"] = a.size
    body["output_format"] = fmt
    body["response_format"] = "url" if a.want_url else "b64_json"
    if a.background:
        body["background"] = a.background
    if a.quality:
        body["quality"] = a.quality
    if a.compression is not None:
        body["output_compression"] = a.compression

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": round(cost / 100.0, 2)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：%s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (cost, cost / 100.0))
        return 0

    say("正在出图（%s，%d 张，同步调用）…" % (a.model, a.n))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(180, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "http": st, "error": msg, "endpoint": "generations"})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)

    data = d.get("data") or []
    got = len(data) if isinstance(data, list) else 0
    paths, src = save_images(d, a.outdir, a.prefix, fmt if fmt != "gif" else None)
    urls = [it.get("url") for it in data if isinstance(it, dict) and it.get("url")]
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(got), "mode": "gen",
           "model": a.model, "requested": a.n, "returned": got, "source": src,
           "elapsed": round(dt, 1), "files": paths, "urls": urls,
           "billedPoints": POINTS_PER_IMAGE * got}
    ledger_add(rec)
    out = {"ok": bool(got), "mode": "gen", "model": a.model, "elapsed": round(dt, 1),
           "requested": a.n, "returned": got, "source": src, "files": paths,
           "urls": urls, "billedPoints": POINTS_PER_IMAGE * got,
           "size": d.get("size"), "output_format": d.get("output_format"),
           "usage": d.get("usage")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if got else EXIT_CALL
    if not got:
        say("  响应里没有图。原始返回：")
        print(txt[:800])
        return EXIT_CALL
    print("出图完成（%.1fs）" % dt)
    print("  模型：%s" % a.model)
    print("  请求 %d 张 / **实际返回 %d 张**" % (a.n, got))
    print("  计费：%d 点（%.2f 元）—— 按实际返回张数" % (POINTS_PER_IMAGE * got,
                                                         POINTS_PER_IMAGE * got / 100.0))
    print("  来源：%s" % src)
    print()
    for p in paths:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    for u in urls:
        print("  链接：%s  ← 约 3 小时后过期，请及时下载" % u)
    return 0


def cmd_edit(a, key, host):
    if not a.prompt:
        raise Fail("usage", "必须给 --prompt（想怎么改图）", EXIT_USAGE)
    if not a.image:
        raise Fail("usage", "至少给一个 --image（可重复，最多 20 张）", EXIT_USAGE)
    for p in a.image:
        if not os.path.isfile(p):
            raise Fail("usage", "参考图不存在：%s" % p, EXIT_USAGE)
    fmt = "gif" if a.gif else a.output_format
    cost = _preflight(a, a.n, a.size, fmt, a.background)
    url = host + API_PREFIX + "/images/edits"
    fields = {"model": a.model, "prompt": a.prompt, "n": a.n,
              "output_format": fmt,
              "response_format": "url" if a.want_url else "b64_json"}
    if a.size and a.size != "auto":
        fields["size"] = a.size
    if a.background:
        fields["background"] = a.background
    files = [("image[]", p) for p in a.image]
    if a.mask:
        files.append(("mask", a.mask))
    if a.markup:
        files.append(("markup", a.markup))

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "fields": fields,
               "files": [f[1] for f in files], "estimatedPoints": cost}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：%s（multipart/form-data）" % url)
        print("  字段：%s" % json.dumps(fields, ensure_ascii=False))
        print("  文件：%s" % ", ".join(f[1] for f in files))
        print("  预估：%d 点（%.2f 元）" % (cost, cost / 100.0))
        return 0

    say("正在改图（%s，%d 张，%d 个参考图）…" % (a.model, a.n, len(a.image)))
    t0 = time.time()
    st, txt = http_multipart(url, key, fields, files, timeout=max(180, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "http": st, "error": msg, "endpoint": "edits"})
        raise Fail("call", "改图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    data = d.get("data") or []
    got = len(data) if isinstance(data, list) else 0
    paths, src = save_images(d, a.outdir, a.prefix, fmt if fmt != "gif" else None)
    urls = [it.get("url") for it in data if isinstance(it, dict) and it.get("url")]
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(got), "mode": "edit",
                "model": a.model, "requested": a.n, "returned": got, "source": src,
                "elapsed": round(dt, 1), "files": paths, "urls": urls,
                "billedPoints": POINTS_PER_IMAGE * got})
    out = {"ok": bool(got), "mode": "edit", "model": a.model, "elapsed": round(dt, 1),
           "requested": a.n, "returned": got, "source": src, "files": paths,
           "urls": urls, "billedPoints": POINTS_PER_IMAGE * got}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if got else EXIT_CALL
    if not got:
        say("  响应里没有图。")
        print(txt[:800])
        return EXIT_CALL
    print("改图完成（%.1fs）" % dt)
    print("  请求 %d 张 / 实际返回 %d 张 · 计费 %d 点"
          % (a.n, got, POINTS_PER_IMAGE * got))
    for p in paths:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    for u in urls:
        print("  链接：%s  ← 约 3 小时后过期" % u)
    return 0


def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        arr = json.load(io.open(LEDGER, encoding="utf-8"))
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        print("  %s  %-5s %-16s 请求%s/回%s  %s 点  %.1fs" % (
            e.get("at"), e.get("mode") or "-", e.get("model") or "",
            e.get("requested"), e.get("returned"),
            e.get("billedPoints"), e.get("elapsed") or 0))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · GPT Image 2.6 出图台（走 api.a7w.cn，OpenAI Images API 兼容）",
        epilog="端点：POST %s/api/v1/images/generations · POST %s/api/v1/images/edits · "
               "GET %s/api/v1/models" % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=500, help="点数上限（单位：点，默认 500）")
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("models", help="列出在架图片模型（免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser("cost", help="先算钱（免费，6 点/张）", allow_abbrev=False)
    p.add_argument("--n", type=int, default=1, help="张数 1–4")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 端点 / 模型（免费，不扣费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_common(p, with_files=False):
        p.add_argument("--prompt", help="提示词")
        p.add_argument("--n", type=int, default=1, help="张数 1–4（默认 1）")
        p.add_argument("--size", default="auto",
                       help="auto / 1k / 2k / 4k / 宽x高（默认 auto）")
        p.add_argument("--output-format", default="png",
                       choices=["png", "jpeg", "webp", "gif"], help="输出格式（默认 png）")
        p.add_argument("--gif", action="store_true", help="等价于 --output-format gif")
        p.add_argument("--background", default=None,
                       choices=["auto", "transparent", "opaque"], help="背景")
        p.add_argument("--quality", default=None,
                       choices=["auto", "low", "medium", "high", "xhigh", "max"],
                       help="质量（仅作提示，不影响价格）")
        p.add_argument("--compression", type=int, default=None,
                       help="0–100，只对 jpeg/webp 生效")
        p.add_argument("--want-url", action="store_true",
                       help="让网关返回 url 而不是 b64_json")
        p.add_argument("--model", default=DEFAULT_MODEL)
        p.add_argument("--outdir", default=".", help="图片保存目录（默认当前目录）")
        p.add_argument("--prefix", default="gptimg", help="文件名前缀")
        p.add_argument("--timeout", type=int, default=240, help="单次请求超时秒数")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        if with_files:
            p.add_argument("--image", action="append",
                           help="参考图文件路径（可重复，最多 20 张）")
            p.add_argument("--mask", help="蒙版文件（可选）")
            p.add_argument("--markup", help="标注层 PNG（可选，需透明像素）")

    p = sub.add_parser("gen", help="文生图（6 点/张，要 --yes）", allow_abbrev=False)
    add_common(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("edit", help="图生图（multipart，要 --yes）", allow_abbrev=False)
    add_common(p, with_files=True)
    p.set_defaults(fn=cmd_edit)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key, host = load_conf(a.key, a.host)
    if not key and a.fn is not cmd_models:
        raise Fail("usage",
                   "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                   "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                   EXIT_USAGE)
    try:
        return a.fn(a, key, host)
    except Fail as e:
        if a.json:
            print(json.dumps({"ok": False, "exit": e.exit_code,
                              "error": {"kind": e.kind, "message": e.message}},
                             ensure_ascii=False))
        else:
            say("失败：%s" % e.message)
        return e.exit_code


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        say("已中断。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
