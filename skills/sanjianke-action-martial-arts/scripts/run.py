#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 黄色的大宝剑专用武打流

走 api.a7w.cn 的**工作流应用**（69 个按次调用应用之一）。
上游报价 ￥0.01/次，本站 1.5 点（￥0.015）。

端点：
  GET  /api/v1/gpu/apps                        应用清单（68 个兄弟应用也在这里）
  GET  /api/v1/gpu/apps/wf_9dbf70f6a4479ddcb762/schema          本应用参数
  POST /api/v1/gpu/assets                      上传素材（免费），拿 asset://
  POST /api/v1/gpu/apps/wf_9dbf70f6a4479ddcb762/run             提交 {"inputs":{...}}
  GET  /api/v1/gpu/workflows/execution          轮询（run_order_id）
"""
import argparse
import io
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

VERSION = "1.0.0"
HOST = "https://api.a7w.cn"
API = "/api/v1"
UA = "sanjianke-gpu-workflow/%s" % VERSION

# ── 本应用契约（生成器内嵌，JSON 文本，避免把 JSON 的 true/false 当 Python 用）──
APP = json.loads(r"""{
 "workflow_id": "wf_9dbf70f6a4479ddcb762",
 "title": "黄色的大宝剑专用武打流",
 "desc": "B站打戏UP主@黄色的大宝剑专用。精制武打流。非加速流。",
 "kind": "image",
 "quote_yuan": 0.01,
 "user_yuan": 0.015,
 "user_points": 1.5,
 "params": [
  {
   "name": "node_148_aspect_ratio",
   "label": "比例选择",
   "type": "string",
   "required": true
  },
  {
   "name": "node_148_megapixels",
   "label": "分辨率选择（0.4-2.0）",
   "type": "float",
   "required": true
  },
  {
   "name": "node_132_value",
   "label": "视频时长（4-15）",
   "type": "float",
   "required": true
  },
  {
   "name": "node_124_steps",
   "label": "一采步数",
   "type": "int",
   "required": true
  },
  {
   "name": "node_138_value",
   "label": "提示词输入",
   "type": "string",
   "required": true
  },
  {
   "name": "node_137_image",
   "label": "图片一",
   "type": "image_input",
   "required": true
  },
  {
   "name": "node_152_image",
   "label": "图片二",
   "type": "image_input",
   "required": false
  },
  {
   "name": "node_197_image",
   "label": "图片三",
   "type": "image_input",
   "required": false
  },
  {
   "name": "node_198_image",
   "label": "图片四",
   "type": "image_input",
   "required": false
  }
 ]
}""")

POINTS = APP["user_points"]
KIND_CN = {"video": "视频", "image": "图片", "text": "文本", "audio": "音频"}
EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1
EXIT_TIMEOUT = 7


class Fail(Exception):
    def __init__(self, kind, message, code):
        super().__init__(message)
        self.kind, self.message, self.code = kind, message, code


def say(m):
    sys.stderr.write(m + "\n")


def load_key(explicit=None):
    k = (explicit or "").strip() or (os.environ.get("A7W_API_KEY") or "").strip()
    if not k:
        cfg = os.path.join(os.path.expanduser("~"), ".a7w", "config.json")
        if os.path.isfile(cfg):
            try:
                d = json.load(io.open(cfg, encoding="utf-8"))
                k = str(d.get("key") or d.get("api_key") or "").strip()
            except Exception:
                pass
    return k


def http(method, path, key, body=None, timeout=180):
    data = None
    hdr = {"Authorization": "Bearer " + key, "Accept": "application/json",
           "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(HOST + path, method=method, data=data, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        raise Fail("call", "连不上 %s：%s" % (path, e), EXIT_CALL)


def jl(t):
    try:
        return json.loads(t)
    except Exception:
        return None


def err_of(txt):
    d = jl(txt) or {}
    for k in ("msg", "message"):
        if d.get(k):
            return str(d[k])[:300]
    e = d.get("error")
    if isinstance(e, dict) and e.get("message"):
        return str(e["message"])[:300]
    return txt.replace("\n", " ")[:240]


def upload(path, key, media_type, purpose="temp_input"):
    """POST /api/v1/gpu/assets（免费）→ asset://"""
    boundary = "----sj" + uuid.uuid4().hex
    fn = os.path.basename(path)
    ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
    buf = io.BytesIO()
    for name, val in (("media_type", media_type), ("purpose", purpose)):
        buf.write(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                   % (boundary, name, val)).encode())
    buf.write(('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
               'Content-Type: %s\r\n\r\n' % (boundary, fn, ctype)).encode())
    buf.write(open(path, "rb").read())
    buf.write(("\r\n--%s--\r\n" % boundary).encode())
    payload = buf.getvalue()
    req = urllib.request.Request(
        HOST + API + "/gpu/assets", method="POST", data=payload,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json",
                 "Content-Type": "multipart/form-data; boundary=" + boundary,
                 "Content-Length": str(len(payload)), "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=300) as x:
            st, txt = x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, txt = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        raise Fail("call", "上传失败：%s" % e, EXIT_CALL)
    d = jl(txt) or {}
    uri = ((d.get("data") or {}).get("asset_uri")
           or (d.get("data") or {}).get("uri") or "")
    if st != 200 or not uri:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_of(txt)), EXIT_CALL)
    return uri


def pick(kind):
    """按类型找第一个必填参数名。"""
    suffix = {"image": ("_image", "image"), "video": ("_video", "video"),
              "audio": ("_audio", "audio"), "text": ("_text", "_prompt", "text", "prompt")}
    pats = suffix.get(kind, ())
    cands = [p for p in APP["params"] if p.get("required")]
    for p in cands:
        n = (p.get("name") or "").lower()
        if any(n.endswith(s) or s in n for s in pats):
            return p["name"]
    for p in APP["params"]:
        n = (p.get("name") or "").lower()
        if any(n.endswith(s) or s in n for s in pats):
            return p["name"]
    return None


def cmd_info(a, key):
    ok = bool(key)
    checks = [("Key 读取", ok, "从 --key / A7W_API_KEY / ~/.a7w/config.json 读到" if ok
               else "没读到；用 --key 或环境变量 A7W_API_KEY")]
    if ok:
        st, txt = http("GET", API + "/gpu/apps", key)
        apps = ((jl(txt) or {}).get("data") or {}).get("apps") or []
        found = next((x for x in apps if x.get("workflow_id") == APP["workflow_id"]), None)
        checks.append(("应用清单可读", st == 200, "HTTP %s · %d 个应用" % (st, len(apps))))
        checks.append(("本应用在架", found is not None,
                       "workflow_id %s" % APP["workflow_id"]))
    out = {"ok": all(c[1] for c in checks), "app": APP["title"],
           "workflow_id": APP["workflow_id"], "points": POINTS,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("%s（%s）" % (APP["title"], KIND_CN.get(APP["kind"], APP["kind"])))
    print()
    print("  价格：上游 ￥%s/次 · 本站 %s 点（￥%s）" % (APP["quote_yuan"], POINTS, APP["user_yuan"]))
    print("  端点：POST %s/gpu/apps/%s/run" % (API, APP["workflow_id"]))
    print()
    print("自检（只读 GET，不扣费）")
    for n, o, d in checks:
        print("  %s %-18s %s" % ("√" if o else "×", n, d))
    return 0 if out["ok"] else EXIT_GATE


def cmd_params(a, key):
    out = {"ok": True, "app": APP["title"], "params": APP["params"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("%s · 参数表（%d 个）" % (APP["title"], len(APP["params"])))
    print()
    print("  %-28s %-22s %-8s %-8s %s" % ("参数名", "含义", "类型", "必填", "默认"))
    print("  " + "-" * 92)
    for p in APP["params"]:
        print("  %-28s %-22s %-8s %-8s %s"
              % (p.get("name", "")[:26], str(p.get("label") or "")[:20],
                 p.get("type") or "", "是" if p.get("required") else "-",
                 str(p.get("default"))[:14]))
    print()
    print("  人话入口：--image / --video / --audio / --text（自动匹配上面第一个必填的对应类型）")
    print("  兜底：--set 参数名=值")
    return 0


def build_inputs(a, key):
    inp = {}
    for kind, val in (("image", a.image), ("video", a.video),
                      ("audio", a.audio), ("text", a.text)):
        if not val:
            continue
        name = pick(kind)
        if not name:
            raise Fail("usage", "本应用没有 %s 类型参数（用 --params 看参数表）" % kind, EXIT_USAGE)
        if kind in ("image", "video", "audio") and os.path.isfile(val):
            say("上传 %s …" % os.path.basename(val))
            inp[name] = upload(val, key, kind)
        else:
            inp[name] = val
    for kv in (a.set or []):
        if "=" not in kv:
            raise Fail("usage", "--set 要写成 名=值：%s" % kv, EXIT_USAGE)
        k, v = kv.split("=", 1)
        inp[k.strip()] = v.strip()
    for p in APP["params"]:
        if p.get("required") and p.get("name") not in inp:
            raise Fail("usage",
                       "缺必填参数 %s（%s）。用 --params 看全表，或 --set %s=值"
                       % (p["name"], p.get("label") or "", p["name"]), EXIT_USAGE)
    return inp


def cmd_run(a, key):
    if not key:
        raise Fail("usage", "没有 API Key", EXIT_USAGE)
    if not a.batch and not (a.image or a.video or a.audio or a.text or a.set):
        raise Fail("usage", "至少给一个 --image/--video/--audio/--text，或 --set 名=值",
                   EXIT_USAGE)
    jobs = []
    if a.batch:
        if not os.path.isfile(a.batch):
            raise Fail("usage", "清单文件不存在：%s" % a.batch, EXIT_USAGE)
        for ln in io.open(a.batch, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                jobs.append(json.loads(ln))
            except Exception:
                raise Fail("usage", "清单第 %d 行不是合法 JSON" % (len(jobs) + 1), EXIT_USAGE)
    else:
        jobs.append(None)

    cost = POINTS * (1 if not a.count else a.count) * len(jobs)
    if cost > a.budget:
        raise Fail("budget", "预计 %s 点超过 --budget %s 点。一个请求都没发。"
                   % (cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实提交 %d 次，扣约 %s 点（￥%.2f）。确认请加 --yes。"
                   % (len(jobs) * (a.count or 1), cost, cost / 100.0), EXIT_CONFIRM)

    url = API + "/gpu/apps/%s/run" % APP["workflow_id"]
    outs = []
    for idx, job in enumerate(jobs):
        if job is None:
            inputs = build_inputs(a, key)
            times = a.count or 1
        else:
            inputs = dict(job.get("inputs") or {})
            for p in APP["params"]:
                if p.get("required") and p.get("name") not in inputs:
                    raise Fail("usage", "清单第 %d 行缺必填 %s" % (idx + 1, p["name"]), EXIT_USAGE)
            times = int(job.get("count") or 1)
        for _ in range(times):
            if a.dry_run:
                outs.append({"dryRun": True, "inputs": inputs})
                continue
            say("提交中（%s）…" % APP["title"])
            st, txt = http("POST", url, key, {"inputs": inputs})
            d = jl(txt) or {}
            dd = d.get("data") if isinstance(d.get("data"), dict) else {}
            rid = dd.get("run_order_id") or dd.get("id") or ""
            if st != 200 or not rid:
                outs.append({"ok": False, "http": st, "error": err_of(txt)})
                continue
            say("已提交 run_order_id=%s，轮询…" % rid)
            outs.append(wait_run(rid, key, a.every, a.limit, a.json))

    bad = [o for o in outs if o.get("ok") is False]
    if a.json:
        print(json.dumps({"ok": not bad, "app": APP["title"], "results": outs},
                         ensure_ascii=False))
        return 0 if not bad else EXIT_CALL
    for o in outs:
        if o.get("dryRun"):
            print("干跑：%s" % json.dumps(o["inputs"], ensure_ascii=False))
        elif o.get("ok") is False:
            print("失败（HTTP %s）：%s" % (o.get("http"), o.get("error")))
        else:
            print("完成：%s" % (o.get("files") or o.get("status")))
    return 0 if not bad else EXIT_CALL


def wait_run(rid, key, every, limit, quiet):
    path = API + "/gpu/workflows/execution?run_order_id=" + urllib.parse.quote(str(rid))
    end = time.time() + limit
    last = None
    while time.time() < end:
        st, txt = http("GET", path, key, timeout=90)
        d = jl(txt) or {}
        dd = d.get("data") if isinstance(d.get("data"), dict) else {}
        if isinstance(dd, list) and dd:
            dd = dd[0]
        status = (dd.get("status") or dd.get("state") or "").lower()
        if status != last and not quiet:
            say("  状态：%s" % status)
            last = status
        files = dd.get("outputs") or dd.get("files") or dd.get("videos") or []
        if status in ("success", "succeeded", "completed", "done") or (
                not status and files):
            return {"ok": True, "status": status, "files": files, "raw": dd}
        if status in ("failed", "error", "cancelled"):
            return {"ok": False, "http": st, "error": str(dd.get("error") or dd.get("message") or status)[:200]}
        time.sleep(every)
    return {"ok": False, "http": 0,
            "error": "轮询超时（%d 秒）——任务可能仍在跑，用 run_order_id=%s 再查" % (limit, rid)}


def main(argv):
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · %s（工作流应用 · %s 点/次）" % (APP["title"], POINTS),
        epilog="端点：POST %s/gpu/apps/%s/run · GET /api/v1/gpu/workflows/execution"
               % (API, APP["workflow_id"]),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--budget", type=int, default=2000, help="点数上限（单位：点）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("info", help="应用信息 + 自检（免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_info)
    p = sub.add_parser("params", help="参数表（label 对照，免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_params)
    p = sub.add_parser("run", help="提交任务", allow_abbrev=False)
    p.add_argument("--image", help="图片（本地文件自动上传）")
    p.add_argument("--video", help="视频")
    p.add_argument("--audio", help="音频")
    p.add_argument("--text", help="文本/提示词")
    p.add_argument("--set", action="append", help="参数名=值（可重复）")
    p.add_argument("--count", type=int, default=1, help="同一输入跑几次")
    p.add_argument("--batch", help="JSONL 清单（每行一个 {inputs:{},count:N}）")
    p.add_argument("--every", type=int, default=10, help="轮询间隔秒")
    p.add_argument("--limit", type=int, default=1800, help="轮询上限秒")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求")
    p.set_defaults(fn=cmd_run)

    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--budget", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)

    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key = load_key(a.key)
    try:
        return a.fn(a, key)
    except Fail as e:
        if a.json:
            print(json.dumps({"ok": False, "exit": e.code,
                              "error": {"kind": e.kind, "message": e.message}},
                             ensure_ascii=False))
        else:
            say("失败：%s" % e.message)
        return e.code


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        say("已中断。任务可能仍在跑 —— 用 run_order_id 查，别重提。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
