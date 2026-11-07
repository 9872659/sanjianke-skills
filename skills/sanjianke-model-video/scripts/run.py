#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 视频生成台（模型层，sanjianke-model-video）

## 一句话

同一个视频模型，走**应用层**和走**模型层**是两个价：

    应用层  POST /api/v1/apps/seedance/submit                    11,000 点（一口价）
    模型层  POST /api/v1/videos  model=sd/doubao-seedance-2-0-260128    145.73 点
    模型层  POST /api/v1/videos  model=volcengine/doubao-seedance-2-5-260628  762.30 点

11,000 / 145.73 = 75.5 倍；11,000 / 762.30 = 14.4 倍。同一条片子。

## 为什么价目表里看不到模型层单价

`GET /api/v1/pricing` 的 115 条规则里**没有模型层的单价**：整张表没有
`modelPricing` 键；`modelRates` 只出现在 3 条 `image_human` 规则上，含义是
「按请求体 mode 取费率」（fast 10 / standard 15 / 2k 30 / 4k 60），不是模型价目表。
模型层命中的是通配 `*`：

    {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
     "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}

所以本包的报价只能从**你自己的流水**反推：`GET /api/v1/me/tasks` 每条任务都带
`actualPrice` / `reservePrice` / `rateNote`，按 model 归集就是你的真实成交价。
没跑过这个模型的账号，退到本机 2026-11-07 的实测基线，并在输出里标
`source=baseline`（不是你的价，是本机实测）。

## 零扣费探针表（2026-11-07 实测，本轮净 0 点）

    POST /api/v1/videos  {}                                   400 Model name not specified
    POST /api/v1/videos  {"model":"muse-video"}               400 plugin_request_invalid
    POST /api/v1/videos  {"model":"sd/doubao-seedance-2-0-…"} 400 prompt or content field is required
    POST /api/v1/videos  {"model":"volcengine/doubao-seedance-2-5-…"}   同上
    POST /api/v1/videos  {"model":"wan3.0-video"}             **502，先冻 300 点再退**

最后一条是唯一动过钱包的调用：`reserve_sync:/api/v1/videos -300` →
`refund:submit_failed:/api/v1/videos +300`，净 0 点，但钱包被冻过一次。
所以 `doctor` 只探前三条，`wan3.0-video` 一次都不探。

## 轮询一律走免费 GET

    免费  GET /api/v1/tasks/<id>     200，假 id 回 {"code":0,"msg":"任务不存在"}
    免费  GET /api/v1/videos/<id>    400 task_not_exist（假 id）

    收费  POST /api/v1/apps/<app>/query   每查一次就是一次的钱
          （nano_banana/query 72 点/次，历史烧掉 15,552 点）

## 子命令

  catalog  4 个模型层模型 + 报价来源 + 应用层对照（免费）
  cost     先算钱（免费；读你的历史成交价，没历史给基线区间并标注）
  doctor   自检 Key / 端点 / 报价数据源（免费；只发会 400 的探针）
  gen      提交任务（要 --yes，受 --budget 管）；--wait 则等到完成并下载
  status   查任务（免费；三条查询路由自动试：/tasks、/videos、/videos/generations）
  wait     等一个任务完成并下载（免费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --model sd/doubao-seedance-2-0-260128 --seconds 5
  python3 scripts/run.py doctor
  python3 scripts/run.py gen --prompt "…" --seconds 5 --dry-run
  python3 scripts/run.py gen --prompt "…" --seconds 5 --yes --wait
  python3 scripts/run.py status task_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request


# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 cp936 编不出的字符就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底；本包全文只用 cp936 覆盖得到的 √ × · → 「」 ≥ ≤。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
POINTS_PER_YUAN = 100
DEFAULT_MODEL = "sd/doubao-seedance-2-0-260128"
DEFAULT_SECONDS = 5
DEFAULT_BUDGET = 3500            # 单位：点。够一条 Seedance 2.5 的上限 3,046 点
UNKNOWN_RESERVE = 3000           # 没有价格样本时按视频模型层常见预冻结估
PAGE_SIZE_ME = 20                # /api/v1/me/tasks 每页恒 20 条
DEFAULT_PAGES = 2                # 默认只扫最近 40 条，够报价就停

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "model-video-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-model-video/%s" % VERSION

# ── 模型层视频模型 ───────────────────────────────────────────────────────────
# samples：本机 2026-11-07 从 GET /api/v1/me/tasks 的 actualPrice 实测到的成交价
# rate：官方文档写死的点/秒（只有 muse-video 有）
# app_points / app：同一模型走应用层的一口价，用来算「便宜几倍」
MODELS = {
    "sd/doubao-seedance-2-0-260128": dict(
        name="Seedance 2.0 标准版",
        samples=[145.73, 181.79, 181.79, 3000.0, 3000.0],
        reserve=3000, rate=None,
        app_points=11000, app="seedance",
        note="同族最便宜的一档；实测最低 145.73 点"),
    "volcengine/doubao-seedance-2-5-260628": dict(
        name="Seedance 2.5 旗舰版",
        samples=[762.3, 3000.0, 3045.71],
        reserve=3000, rate=None,
        app_points=11000, app="seedance",
        note="画质最强的一档；实测最低 762.30 点"),
    "wan3.0-video": dict(
        name="Wan 3.0",
        samples=[300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0],
        reserve=300, rate=None,
        app_points=800, app="wan",
        note="8 条成交全是 300 点，最稳的一档；走百炼通道"),
    "muse-video": dict(
        name="Muse Video 720P 带声音",
        samples=[44.0, 44.0, 55.0, 55.0, 55.0, 55.0, 55.0, 260.0],
        reserve=None, rate=11,
        app_points=None, app=None,
        note="官方写死 11 点/秒，按请求秒数结算，4–180 秒"),
}
MODEL_ORDER = ["sd/doubao-seedance-2-0-260128", "volcengine/doubao-seedance-2-5-260628",
               "wan3.0-video", "muse-video"]

TERMINAL_OK = ("completed", "succeeded", "success", "done", "finished")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "refunded",
                "expired", "timeout", "rejected")


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


def http_json(method, url, key, body=None, timeout=120, retries=2):
    """网关会重置空闲连接（WinError 10054），网络类错误退避重试一次；
    4xx 是业务错误，原样返回给调用方判断。"""
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries - 1:
                last = e
                time.sleep(1 + attempt)
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                continue
            raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        if isinstance(d.get("error"), dict):
            e = d["error"]
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        elif isinstance(d.get("error"), str) and d["error"]:
            return str(d["error"])[:300]
        for k in ("message", "msg", "detail"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条路径下没有该端点" % st
    return txt.replace("\n", " ")[:240]


def fmt_pts(n):
    try:
        v = float(n)
    except Exception:                                            # noqa: BLE001
        return str(n)
    if abs(v - round(v)) < 0.005:
        return "{:,}".format(int(round(v)))
    return "{:,.2f}".format(v)


def _sw(s):
    """显示宽度：中文按 2 格算，表格才对得齐。"""
    w = 0
    for ch in str(s):
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def pad(s, width):
    s = str(s)
    acc, out = 0, ""
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if acc + cw > width:
            break
        out += ch
        acc += cw
    return out + " " * max(0, width - acc)


def yuan(pts):
    return "%.2f 元" % (float(pts) / POINTS_PER_YUAN)


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


# ─────────────────────── 报价：你的历史成交价 → 基线 ───────────────────────
class PriceBook:
    """先读你自己的流水（/api/v1/me/tasks 的 actualPrice），没有再退基线。"""

    def __init__(self, a, key, host):
        self.a, self.key, self.host = a, key, host
        self._live = None
        self.scanned = 0
        self.error = ""

    def scan(self):
        if self._live is not None:
            return self._live
        live = {}
        pages = max(0, int(getattr(self.a, "pages", DEFAULT_PAGES) or 0))
        if pages and self.key:
            try:
                for pg in range(1, pages + 1):
                    st, txt = http_json(
                        "GET", "%s%s/me/tasks?limit=2000&page=%d" % (self.host, API_PREFIX, pg),
                        self.key, None, 45)
                    if st != 200:
                        self.error = "HTTP %s %s" % (st, err_text(st, txt)[:60])
                        break
                    ts = (jloads(txt) or {}).get("tasks") or []
                    if not ts:
                        break
                    self.scanned += len(ts)
                    for t in ts:
                        p = t.get("path") or ""
                        m = (t.get("model") or "").strip()
                        if not m or "/apps/" in p:
                            continue
                        try:
                            v = float(t.get("actualPrice") or 0)
                        except Exception:                        # noqa: BLE001
                            continue
                        if v > 0:
                            live.setdefault(m, []).append(round(v, 2))
                    if len(ts) < PAGE_SIZE_ME:
                        break
            except Fail as e:
                self.error = e.message[:80]
        self._live = live
        return live

    def quote(self, model, seconds):
        """返回报价 dict：low/high/median/n/source/gate/basis。"""
        seconds = max(1, int(seconds or DEFAULT_SECONDS))
        meta = MODELS.get(model) or {}
        live = self.scan()
        samples = sorted(live.get(model) or [])
        if samples:
            source = "live"
            basis = "你账号的 %d 条成交记录（actualPrice）" % len(samples)
        elif meta.get("rate"):
            source = "rate"
            samples = sorted(meta.get("samples") or [])
            basis = "官方文档写死 %d 点/秒" % meta["rate"]
        elif meta.get("samples"):
            source = "baseline"
            samples = sorted(meta["samples"])
            basis = "本机 2026-11-07 实测基线，%d 条样本（不是你的流水）" % len(samples)
        else:
            return dict(model=model, source="none", n=0, low=None, high=None,
                        median=None, gate=UNKNOWN_RESERVE, exact=False,
                        basis="这个模型没有价格样本，按视频模型层常见预冻结 %s 点估"
                              % fmt_pts(UNKNOWN_RESERVE))
        if meta.get("rate"):
            pts = int(round(float(meta["rate"]) * seconds))
            return dict(model=model, source=source, n=len(samples) or 1, low=pts, high=pts,
                        median=pts, gate=pts, exact=True, rate=meta["rate"],
                        seconds=seconds,
                        basis="%d 点/秒 × %d 秒 = %s 点（官方口径，按请求秒数结算）"
                              % (meta["rate"], seconds, fmt_pts(pts)))
        n = len(samples)
        med = samples[n // 2] if n % 2 else (samples[n // 2 - 1] + samples[n // 2]) / 2.0
        return dict(model=model, source=source, n=n, low=samples[0], high=samples[-1],
                    median=med, gate=float(samples[-1]), exact=(samples[0] == samples[-1]),
                    basis=basis)


def quote_line(q):
    if q["source"] == "none":
        return "无样本，按 %s 点估" % fmt_pts(q["gate"])
    if q.get("rate"):
        return "%s 点（%d 点/秒 × %d 秒）" % (fmt_pts(q["gate"]), q["rate"], q["seconds"])
    if q["low"] == q["high"]:
        return "%s 点（%s）" % (fmt_pts(q["low"]), q["source"])
    return "%s – %s 点（%s，%d 条）" % (fmt_pts(q["low"]), fmt_pts(q["high"]),
                                       q["source"], q["n"])


def quote_full(q):
    """一行说完：区间 + 依据。"""
    if q["source"] == "none":
        return "%s · %s" % (quote_line(q), q["basis"])
    if q.get("rate") or q["low"] == q["high"]:
        return "%s · %s" % (quote_line(q), q["basis"])
    return "%s – %s 点 · %s" % (fmt_pts(q["low"]), fmt_pts(q["high"]), q["basis"])


def ratio_text(model, pts):
    meta = MODELS.get(model) or {}
    app = meta.get("app_points")
    if not app or not pts:
        return ""
    return "省 %.1f 倍" % (float(app) / float(pts))


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    book = PriceBook(a, key, host)
    rows = []
    for m in MODEL_ORDER:
        q = book.quote(m, a.seconds)
        meta = MODELS[m]
        rows.append({"model": m, "name": meta["name"], "quote": q,
                     "quoteText": quote_line(q), "appPoints": meta.get("app_points"),
                     "app": meta.get("app"), "note": meta["note"],
                     "ratio": (float(meta["app_points"]) / q["low"])
                     if meta.get("app_points") and q["low"] else None,
                     "reserve": meta.get("reserve")})
    out = {"ok": True, "models": rows, "pointsPerYuan": POINTS_PER_YUAN,
           "scannedTasks": book.scanned, "priceSource": "GET /api/v1/me/tasks"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 视频生成台（模型层）—— 4 个模型，一条命令")
    print()
    for r in rows:
        m = MODELS[r["model"]]
        print("  %s" % r["model"])
        print("      %s" % m["name"])
        print("      报价  %s" % r["quoteText"])
        if r["appPoints"]:
            print("      应用层 %s %s  →  便宜 %.1f 倍"
                  % (pad("/" + (r["app"] or "") + "/submit", 22),
                     pad("%s 点" % fmt_pts(r["appPoints"]), 10), r["ratio"] or 0))
        else:
            print("      应用层 无同款对照（这是模型层独有的 720P 带声音档）")
        print("      说明  %s" % m["note"])
        print()
    print("  报价口径：先读你账号 /api/v1/me/tasks 的 actualPrice（本次扫了 %d 条任务），"
          % book.scanned)
    print("  没跑过就退到本机实测基线，行尾标 baseline。价目表 /api/v1/pricing 里")
    print("  没有模型层单价，模型层命中通配：上游实际点数 x 2、单笔保底 50 点。")
    print()
    print("  1 元 = 100 点。最便宜的一档 Seedance 2.0 实测 145.73 点 = 1.46 元一条。")
    return 0


def cmd_cost(a, key, host):
    book = PriceBook(a, key, host)
    targets = [a.model] if a.model else MODEL_ORDER
    detail = None
    if a.model:
        q = book.quote(a.model, a.seconds)
        detail = {"model": a.model, "seconds": a.seconds, "quote": q,
                  "yuan": round((q["gate"] or 0) / float(POINTS_PER_YUAN), 2)}
    table = []
    for m in targets:
        q = book.quote(m, a.seconds)
        table.append({"model": m, "name": (MODELS.get(m) or {}).get("name") or "-",
                      "low": q["low"], "high": q["high"], "gate": q["gate"],
                      "source": q["source"], "n": q["n"],
                      "appPoints": (MODELS.get(m) or {}).get("app_points"),
                      "ratio": (float((MODELS.get(m) or {}).get("app_points") or 0) / q["low"])
                      if q["low"] and (MODELS.get(m) or {}).get("app_points") else None})
    out = {"ok": True, "seconds": a.seconds, "pointsPerYuan": POINTS_PER_YUAN,
           "scannedTasks": book.scanned, "priceSource": "GET /api/v1/me/tasks",
           "table": table, "detail": detail,
           "notes": [
               "1 元 = 100 点；模型层单价不在 /api/v1/pricing 里，只能从 actualPrice 反推",
               "报价 = 你账号里同一模型的 actualPrice 区间；秒数只影响实际结算",
               "闸门按区间上限判定（预冻结也是按上限冻的），宁可拦住也不超支",
               "任务失败全额退回；参数被校验拦下（400）不建任务、不扣费"],
           }
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估花费（1 元 = 100 点）")
    print()
    if detail:
        q = detail["quote"]
        print("  --model %s" % a.model)
        print("  %s" % q["basis"])
        print("  闸门按 %s 点判定（%s）" % (fmt_pts(q["gate"]), yuan(q["gate"])))
        if q["low"] is not None and q["low"] != q["high"]:
            print("  历史区间 %s – %s 点（%d 条成交）" % (fmt_pts(q["low"]),
                                                  fmt_pts(q["high"]), q["n"]))
        print()
    print("  %s %s %s %s" % (pad("--model", 38), pad("报价区间", 22),
                             pad("闸门", 10), "应用层"))
    print("  " + "-" * 84)
    for r in table:
        rng = "无样本" if r["low"] is None else (
            fmt_pts(r["low"]) if r["low"] == r["high"]
            else "%s - %s" % (fmt_pts(r["low"]), fmt_pts(r["high"])))
        app = "便宜 %.1f 倍" % r["ratio"] if r["ratio"] else "-"
        print("  %s %s %s %s" % (pad(r["model"], 38), pad(rng, 22),
                                 pad(fmt_pts(r["gate"]), 10), app))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    if a.model and a.model not in MODELS:
        print()
        print("  这个 model 不在本包的 4 个里：没有基线，只有你自己的流水才算得准。")
    return 0


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/user/balance", key, None, 40)
    d = jloads(txt) or {}
    checks.append(("Key 有效 + 余额接口可达", st == 200,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(d.get("available_points") or d.get("points") or 0),
                       fmt_pts(d.get("frozen") or 0))))

    st, txt = http_json("GET", host + API_PREFIX + "/models", key, None, 60)
    codes, vids, bare = set(), [], 0
    if st == 200:
        data = (jloads(txt) or {}).get("data") or []
        for it in data:
            if it.get("model_code"):
                codes.add(it.get("model_code"))
            else:
                bare += 1
            if it.get("type_code") == "video":
                vids.append(it.get("model_code") or it.get("id"))
    missing = [m for m in MODEL_ORDER if m not in codes and m not in
               {(it.get("id") or "") for it in ((jloads(txt) or {}).get("data") or [])}]
    checks.append(("模型目录可达 + 4 个模型都在架", st == 200 and not missing,
                   "HTTP %s · 视频模型 %d 个 · 裸模型层 ID %d 条%s"
                   % (st, len(vids), bare,
                      "" if not missing else " · 缺 " + ",".join(missing)[:60])))

    # 价目表：模型层没有专属规则，只有通配（上游 x2、保底 50）
    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, None, 60)
    rule, has_model_pricing = {}, None
    if st_p == 200:
        pr = jloads(txt_p) or {}
        has_model_pricing = "modelPricing" in pr
        rule = (pr.get("pricing") or {}).get("*") or {}
    checks.append(("模型层无专属价目（通配：上游 x%.0f、保底 %s 点）" % (
        (float(rule.get("markupPercent") or 100) / 100.0) + 1.0,
        fmt_pts(rule.get("minPoints") or 50)),
        st_p == 200 and not has_model_pricing and bool(rule),
        "HTTP %s · %s" % (st_p, "只有通配规则" if rule else "价目表结构变了")))

    # 提交端点：空 body → 400「Model name not specified」
    st1, txt1 = http_json("POST", host + API_PREFIX + "/videos", key, {}, 45)
    d1 = jloads(txt1) or {}
    e1 = d1.get("error") if isinstance(d1.get("error"), dict) else {}
    msg1 = (e1.get("message") or d1.get("message") or "")[:60]
    checks.append(("提交端点存在（空 body 400 Model name not specified）",
                   st1 == 400 and "model name" in msg1.lower(),
                   "HTTP %s %s" % (st1, msg1[:46])))

    # 合法 model + 缺 prompt → 400，停在参数校验层，不建任务
    for model in ("muse-video", DEFAULT_MODEL):
        st2, txt2 = http_json("POST", host + API_PREFIX + "/videos", key,
                              {"model": model}, 45)
        d2 = jloads(txt2) or {}
        e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
        msg2 = (e2.get("message") if isinstance(e2, dict) else "") or ""
        if not msg2 and isinstance(d2.get("error"), str):
            msg2 = d2["error"]
        msg2 = (msg2 or d2.get("message") or "")[:60]
        checks.append(("缺 prompt 被拦（%s）" % model, st2 == 400 and "prompt" in msg2.lower(),
                       "HTTP %s %s" % (st2, msg2[:44])))

    # 查询路由（三条都免费）
    st3, txt3 = http_json("GET", host + API_PREFIX + "/tasks/x-doctor-probe", key, None, 40)
    d3 = jloads(txt3) or {}
    checks.append(("通用查询 /tasks/{id} 可用（假 id 回「任务不存在」）",
                   st3 == 200 and d3.get("code") == 0,
                   "HTTP %s %s" % (st3, str(d3.get("msg") or "")[:20])))

    st4, txt4 = http_json("GET", host + API_PREFIX + "/videos/x-doctor-probe", key, None, 40)
    d4 = jloads(txt4) or {}
    checks.append(("视频查询 /videos/{id} 可用（假 id 回 task_not_exist）",
                   st4 == 400 and str(d4.get("code") or "") == "task_not_exist",
                   "HTTP %s %s" % (st4, str(d4.get("code") or err_text(st4, txt4))[:24])))

    st5, txt5 = http_json("GET", host + API_PREFIX + "/videos/generations/x-doctor-probe",
                          key, None, 40)
    d5 = jloads(txt5) or {}
    checks.append(("模型层查询 /videos/generations/{id}（假 id 回 not found）",
                   st5 == 404 and str(d5.get("error") or "").lower() == "task not found",
                   "HTTP %s %s" % (st5, str(d5.get("error") or err_text(st5, txt5))[:24])))

    # 报价数据源
    book = PriceBook(a, key, host)
    book.scan()
    hit = len([m for m in MODEL_ORDER if book._live and book._live.get(m)])
    checks.append(("报价数据源可用（/me/tasks，扫到 %d 条任务）" % book.scanned,
                   bool(book.scanned) and not book.error,
                   "%d 个模型有你的成交记录%s" % (hit, (" · " + book.error) if book.error else "")))

    out = {"ok": all(c[1] for c in checks), "host": host, "models": MODEL_ORDER,
           "endpoint": host + API_PREFIX + "/videos",
           "query": [host + API_PREFIX + "/tasks/<id>",
                     host + API_PREFIX + "/videos/<id>",
                     host + API_PREFIX + "/videos/generations/<id>"],
           "priceSource": host + API_PREFIX + "/me/tasks",
           "scannedTasks": book.scanned,
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（不建任务、不扣费：只读 GET + 缺 prompt 的 POST，全部停在 400）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 58), dt))
    print()
    print("  提交：POST %s  （OpenAI 视频接口形态）" % out["endpoint"])
    print("  查询：GET  %s" % out["query"][0])
    print("        GET  %s" % out["query"][1])
    print("        GET  %s（Seedance 族只认这条）" % out["query"][2])
    print("  报价：GET  %s" % out["priceSource"])
    print("  省钱：同一模型走应用层 11,000 点，模型层实测 145.73 点（75.5 倍）")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 参数与请求体 ─────────────────────────
def to_ref(src, max_bytes=10 * 1024 * 1024):
    """本地图片 → data URL；URL 原样返回。"""
    if src.startswith(("http://", "https://", "data:")):
        return src
    if not os.path.isfile(src):
        raise Fail("usage", "参考图不存在：%s" % src, EXIT_USAGE)
    blob = open(src, "rb").read()
    if len(blob) > max_bytes:
        raise Fail("usage", "单张图超过 10 MB：%s（%d 字节）" % (src, len(blob)), EXIT_USAGE)
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        mime = "image/webp"
    elif blob[:2] == b"\xff\xd8":
        mime = "image/jpeg"
    else:
        raise Fail("usage", "参考图只支持 png/jpeg/webp：%s" % src, EXIT_USAGE)
    return "data:%s;base64,%s" % (mime, base64.b64encode(blob).decode())


def _check(a, model, seconds, refs):
    if not a.prompt or not a.prompt.strip():
        raise Fail("usage", "必须给 --prompt（画面写清三件事：主体是什么、怎么动、镜头怎么走）",
                   EXIT_USAGE)
    if len(a.prompt) > 4000:
        raise Fail("usage", "--prompt 最多 4000 字（当前 %d）" % len(a.prompt), EXIT_USAGE)
    if not model:
        raise Fail("usage", "必须给 --model（见 catalog 的 4 个）", EXIT_USAGE)
    if seconds < 1 or seconds > 180:
        raise Fail("usage", "--seconds 只支持 1 到 180 的整数（当前 %s）" % seconds, EXIT_USAGE)
    if model == "muse-video" and (seconds < 4 or seconds > 180):
        raise Fail("usage", "muse-video 的 --seconds 只支持 4 到 180（当前 %s）" % seconds,
                   EXIT_USAGE)
    if a.size and not (len(a.size.split("x")) == 2 and
                       all(p.isdigit() for p in a.size.split("x"))):
        raise Fail("usage", "--size 写成 宽x高，例如 1280x720 或 720x1280（当前 %s）" % a.size,
                   EXIT_USAGE)
    cap = 4 if model == "muse-video" else 9
    if len(refs) > cap:
        raise Fail("usage", "参考图最多 %d 张（当前 %d）" % (cap, len(refs)), EXIT_USAGE)


def build_body(a, model, seconds, refs):
    body = {"model": model, "prompt": a.prompt}
    body["seconds"] = int(seconds)
    size = a.size
    if not size and model == "muse-video":
        size = "1280x720"                      # 官方建议总是填，缺省即横屏
    if size:
        body["size"] = size
    if a.first_frame:
        if refs:
            raise Fail("usage", "首帧用 --first-frame；多图参考用 --ref。两者别同时给",
                       EXIT_USAGE)
        body["input_reference"] = to_ref(a.first_frame)
    elif refs:
        body["images"] = [to_ref(r) for r in refs]
    if a.extra:
        try:
            extra = json.loads(a.extra)
        except Exception:                                        # noqa: BLE001
            raise Fail("usage", "--extra 要是 JSON 对象，例如 '{\"ratio\":\"9:16\"}'",
                       EXIT_USAGE)
        if not isinstance(extra, dict):
            raise Fail("usage", "--extra 要是 JSON 对象（当前是 %s）" % type(extra).__name__,
                       EXIT_USAGE)
        body.update(extra)
    return body


def _mask_body(body):
    out = dict(body)
    for k in ("input_reference",):
        if isinstance(out.get(k), str) and out[k].startswith("data:"):
            out[k] = "<本地图 -> data URL>"
    if isinstance(out.get("images"), list):
        out["images"] = ["<本地图 -> data URL>" if isinstance(x, str) and x.startswith("data:")
                         else x for x in out["images"]]
    return out


def cmd_gen(a, key, host):
    model = a.model or DEFAULT_MODEL
    seconds = a.seconds
    refs = list(a.ref or [])
    _check(a, model, seconds, refs)
    book = PriceBook(a, key, host)
    q = book.quote(model, seconds)
    cost = q["gate"]

    if cost > a.budget:
        raise Fail("budget",
                   "报价上限 %s 点超过 --budget %s 点（%s）。%s。"
                   "调大 --budget（单位：点）或换更便宜的一档。一个请求都没发。"
                   % (fmt_pts(cost), fmt_pts(a.budget), q["basis"],
                      "预冻结按上限冻" if not q["exact"] else "这条按秒计费"),
                   EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实出片：报价 %s，闸门按 %s 点（%s）判定，上游预冻结约 %s 点，"
                   "失败全额退回。确认请加 --yes。"
                   % (quote_line(q), fmt_pts(cost), yuan(cost),
                      fmt_pts((MODELS.get(model) or {}).get("reserve") or cost)),
                   EXIT_CONFIRM)

    body = build_body(a, model, seconds, refs)
    url = host + API_PREFIX + "/videos"
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "model": model,
               "requestBody": _mask_body(body), "quote": q, "gatePoints": cost}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(_mask_body(body), ensure_ascii=False)[:600])
        print("  报价：%s" % quote_full(q))
        print("  闸门：按 %s 点（%s）判定" % (fmt_pts(cost), yuan(cost)))
        r = ratio_text(model, q["low"])
        if r:
            print("  对照：同一模型应用层 %s 点，本包 %s" % (
                fmt_pts((MODELS.get(model) or {}).get("app_points")), r))
        return 0

    say("正在提交（%s，%d 秒）…" % (model, seconds))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(60, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    if isinstance(d.get("data"), dict) and d.get("code") in (0, 1):
        d = d["data"]                              # 套了 code/data 的那种返回
    if st not in (200, 201) or (d.get("code") == 0 and not (d.get("id") or d.get("taskId"))):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "model": model,
                    "seconds": seconds, "http": st, "error": msg})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)

    tid = d.get("id") or d.get("task_id") or d.get("taskId")
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(tid), "model": model,
           "seconds": seconds, "id": tid, "status": d.get("status"),
           "quote": q["low"], "gatePoints": cost, "elapsed": round(dt, 1)}
    ledger_add(rec)
    if not tid:
        if a.json:
            print(json.dumps({"ok": False, "exit": EXIT_CALL,
                              "error": {"kind": "call",
                                        "message": "提交没有返回任务 ID：%s" % txt[:200]}},
                             ensure_ascii=False))
            return EXIT_CALL
        say("  提交没有返回任务 ID。原始返回（前 600 字）：")
        print(txt[:600])
        return EXIT_CALL

    if a.wait:
        say("已提交 %s，开始等待（每 %d 秒查一次，上限 %d 分钟）…"
            % (tid, a.every, a.limit // 60))
        return _wait_and_download(a, key, host, tid, a.every, a.limit)

    out = {"ok": True, "id": tid, "status": d.get("status"), "model": model,
           "seconds": seconds, "quote": q, "gatePoints": cost,
           "next": "python3 scripts/run.py wait %s --outdir %s" % (tid, a.outdir)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s" % tid)
    print("  状态：%s" % d.get("status"))
    print("  模型：%s（%d 秒）" % (model, seconds))
    print("  报价：%s；预冻结约 %s 点，完成按实际结算，失败全额退回" % (
        quote_line(q), fmt_pts((MODELS.get(model) or {}).get("reserve") or cost)))
    print()
    print("  这是异步任务，不会自动完成。跟踪它（查任务全部免费）：")
    print("    python3 scripts/run.py wait %s --outdir %s" % (tid, a.outdir))
    print("    python3 scripts/run.py status %s" % tid)
    print()
    print("  同一个任务只查不重提：重提就是再花一次。")
    return 0


# ───────────────────────── 查询 / 等待 ─────────────────────────
def _pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _dig_url(d):
    """成片地址可能在顶层，也可能在 result / storage 里。"""
    for src in (d, d.get("result") or {}, d.get("storage") or {}):
        if isinstance(src, dict):
            for k in ("video_url", "videoUrl", "url", "resultUrl", "result_url",
                      "output_url"):
                v = src.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return v
    return None


def _vurl(d):
    return _dig_url(d) or _pick(d, "videoUrl", "resultUrl", "result_url")


def _exp_text(v):
    if isinstance(v, (int, float)) and v > 0:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(v))
    if isinstance(v, str) and v.strip():
        return v.strip().replace("T", " ")[:19]
    return ""


def fetch_task(a, key, host, tid):
    """三条免费查询合并（实测：不同家族的 id 落在不同路由上）。

      1) GET /api/v1/tasks/{id}               → 状态/进度（task_ 开头那种）
      2) GET /api/v1/videos/{id}              → 成片 video_url / expires_at
      3) GET /api/v1/videos/generations/{id}  → 模型层 Seedance 族（UUID 那种）
    """
    qtid = urllib.parse.quote(tid)
    out, errors = {}, []

    st, txt = http_json("GET", "%s%s/tasks/%s" % (host, API_PREFIX, qtid), key, None, 45)
    d = jloads(txt) or {}
    body = d.get("data") if isinstance(d.get("data"), dict) else d
    if st == 200 and isinstance(body, dict) and (
            body.get("status") or body.get("task_id") or body.get("taskId")):
        out["_tasksHit"] = True
        for k in ("status", "progress", "task_id", "created_at", "finished_at",
                  "fail_reason", "cost", "actualPrice", "reservePrice", "refund"):
            if body.get(k) is not None:
                out[k] = body[k]
    else:
        errors.append("tasks: HTTP %s %s" % (st, str(d.get("msg") or err_text(st, txt))[:40]))

    st2, txt2 = http_json("GET", "%s%s/videos/%s" % (host, API_PREFIX, qtid), key, None, 45)
    d2 = jloads(txt2) or {}
    if st2 == 200 and isinstance(d2, dict) and (d2.get("status") or d2.get("id")):
        out["_videosHit"] = True
        for k in ("status", "progress", "seconds", "size", "video_url", "url",
                  "expires_at", "created_at", "completed_at", "model", "error"):
            if d2.get(k) is not None:
                out[k] = d2[k]
    else:
        errors.append("videos: HTTP %s %s" % (st2, str(d2.get("code")
                                                       or err_text(st2, txt2))[:40]))

    st3, txt3 = http_json("GET", "%s%s/videos/generations/%s"
                          % (host, API_PREFIX, qtid), key, None, 45)
    d3 = jloads(txt3) or {}
    if st3 == 200 and isinstance(d3, dict) and (
            d3.get("status") or d3.get("generation_status") or d3.get("id")):
        out["_genHit"] = True
        out.setdefault("status", d3.get("status") or d3.get("generation_status"))
        for k in ("model", "duration", "video_url_expires_at", "storage_url_expires_at",
                  "delivery_status", "created_at", "updated_at"):
            if d3.get(k) is not None:
                out.setdefault(k, d3[k])
        if not _vurl(out):
            u = _dig_url(d3)
            if u:
                out["video_url"] = u
    else:
        errors.append("generations: HTTP %s %s" % (
            st3, str(d3.get("code") or d3.get("error") or err_text(st3, txt3))[:40]))

    out["_errors"] = errors
    return out


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给任务 ID（提交时返回的 id）", EXIT_USAGE)
    d = fetch_task(a, key, host, a.task_id)
    if not (d.get("_tasksHit") or d.get("_videosHit") or d.get("_genHit")):
        raise Fail("call", "三条免费查询都没拿到 %s：%s" % (a.task_id, " / ".join(d["_errors"])),
                   EXIT_CALL)
    st = str(d.get("status") or "").lower()
    q = ["%s%s/tasks/%s" % (host, API_PREFIX, a.task_id),
         "%s%s/videos/%s" % (host, API_PREFIX, a.task_id),
         "%s%s/videos/generations/%s" % (host, API_PREFIX, a.task_id)]
    out = {"ok": True, "id": a.task_id, "status": st, "progress": d.get("progress"),
           "videoUrl": _vurl(d), "seconds": _pick(d, "seconds", "duration"),
           "size": d.get("size"),
           "expiresAt": _exp_text(_pick(d, "expires_at", "video_url_expires_at")),
           "cost": _pick(d, "actualPrice", "cost", "chargedPoints", "netPoints"),
           "reserve": _pick(d, "reservePrice", "frozenPoints"),
           "refund": d.get("refund"), "error": d.get("error"), "query": q}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s%s" % (st or "?", "（进度 %s）" % d.get("progress")
                            if d.get("progress") is not None else ""))
    if out["seconds"] is not None:
        print("  请求：%s 秒 · %s" % (out["seconds"], d.get("size") or "-"))
    if out["cost"] is not None:
        print("  实扣：%s 点（%s）" % (fmt_pts(out["cost"]), yuan(out["cost"])))
    if out["reserve"] is not None:
        print("  冻结：%s 点" % fmt_pts(out["reserve"]))
    if out["refund"] is not None:
        print("  退回：%s 点" % fmt_pts(out["refund"]))
    if out["videoUrl"]:
        print("  成片：%s" % out["videoUrl"])
        if out["expiresAt"]:
            print("  过期：%s（以返回的过期时间为准，拿到就转存）" % out["expiresAt"])
    if d.get("error"):
        print("  错误：%s" % (json.dumps(d["error"], ensure_ascii=False)
                              if not isinstance(d["error"], str) else d["error"])[:300])
    print()
    print("  查询路径（都免费）：GET /api/v1/tasks/<id> · /videos/<id> · /videos/generations/<id>")
    return 0


def _download(a, vurl, tid):
    os.makedirs(a.outdir, exist_ok=True)
    tail = tid[-8:] if tid else "out"
    path = os.path.join(a.outdir, "%s-%s.mp4" % (a.prefix, tail))
    req = urllib.request.Request(vurl, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=900) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    return path


def _wait_and_download(a, key, host, tid, every, limit):
    end = time.time() + max(30, limit)
    last = None
    while time.time() < end:
        d = fetch_task(a, key, host, tid)
        st = str(d.get("status") or "").lower()
        if st != last:
            say("  状态：%s" % (st or "?"))
            last = st
        if st in TERMINAL_OK:
            vurl = _vurl(d)
            secs = _pick(d, "seconds", "duration")
            out = {"ok": bool(vurl), "id": tid, "status": st, "videoUrl": vurl,
                   "seconds": secs, "size": d.get("size"),
                   "expiresAt": _exp_text(_pick(d, "expires_at", "video_url_expires_at")),
                   "cost": _pick(d, "actualPrice", "cost", "chargedPoints")}
            path = ""
            if vurl:
                try:
                    path = _download(a, vurl, tid)
                    out["file"] = path
                    out["bytes"] = os.path.getsize(path)
                except Exception as e:                           # noqa: BLE001
                    out["downloadError"] = "%s: %s" % (type(e).__name__, e)
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(vurl),
                        "id": tid, "done": True, "file": path})
            if a.json:
                print(json.dumps(out, ensure_ascii=False))
                return 0 if vurl else EXIT_CALL
            if not vurl:
                say("  已完成，但返回里没有成片地址：%s"
                    % json.dumps(d, ensure_ascii=False)[:400])
                return EXIT_CALL
            print()
            print("出片完成")
            print("  任务：%s" % tid)
            if secs is not None:
                print("  规格：%s · %s 秒" % (d.get("size") or "-", secs))
            if out.get("cost") is not None:
                print("  实扣：%s 点（%s）" % (fmt_pts(out["cost"]), yuan(out["cost"])))
            if out.get("file"):
                print("  文件：%s（%d 字节）" % (out["file"], out["bytes"]))
            if out.get("downloadError"):
                print("  下载没成功：%s" % out["downloadError"])
            print("  线上：%s" % vurl)
            if out.get("expiresAt"):
                print("  过期：%s（以返回的过期时间为准，拿到就转存）" % out["expiresAt"])
            return 0
        if st in TERMINAL_BAD:
            e = d.get("error") or {}
            msg = e.get("message") if isinstance(e, dict) else str(e)
            raise Fail("call", "任务失败：%s —— 冻结的点数会全额退回（流水里能看到 refund）"
                       % (msg or st), EXIT_CALL)
        time.sleep(max(2, every))
    raise Fail("call",
               "等了 %d 分钟还没完成。任务没丢，用 `wait %s` 接着查；"
               "同一个任务只查不重提，重提就是再花一次。" % (max(30, limit) // 60, tid),
               EXIT_CALL)


def cmd_wait(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给任务 ID", EXIT_USAGE)
    say("等待 %s（每 %d 秒查一次，上限 %d 分钟）…" % (a.task_id, a.every, a.limit // 60))
    return _wait_and_download(a, key, host, a.task_id, a.every, a.limit)


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
        print("  %s  %s %s %s %s" % (
            e.get("at"), pad("ok" if e.get("ok") else "fail", 6),
            pad((e.get("id") or e.get("error") or "-"), 42),
            pad("%s 秒" % e.get("seconds") if e.get("seconds") else "-", 8),
            ("%s 点" % fmt_pts(e["quote"])) if e.get("quote") is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 视频生成台（模型层）：POST /api/v1/videos，比应用层便宜 14–75 倍",
        epilog="提交 POST %s/api/v1/videos · 查询 GET %s/api/v1/tasks/{id} 与 "
               "GET %s/api/v1/videos/{id} · 报价 GET %s/api/v1/me/tasks" % (
                   DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                    help="读多少页 /me/tasks 报价（每页 20 条，默认 %d；0 = 只用基线）"
                         % DEFAULT_PAGES)
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="4 个模型层模型 + 报价来源 + 应用层对照（免费）",
                       allow_abbrev=False)
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="按多少秒估算（默认 %d；只对按秒计费的模型有用）" % DEFAULT_SECONDS)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱（免费；读你的历史成交价）", allow_abbrev=False)
    p.add_argument("--model", default=None, help="只看这一档（默认 4 档全看）")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS, help="秒数（默认 %d）"
                                                                      % DEFAULT_SECONDS)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 端点 / 报价数据源（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_gen(p):
        p.add_argument("--prompt", help="提示词，最多 4000 字（主体 + 怎么动 + 镜头）")
        p.add_argument("--model", default=DEFAULT_MODEL,
                       help="模型，默认 %s（见 catalog）" % DEFAULT_MODEL)
        p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                       help="秒数 1–180（默认 %d）" % DEFAULT_SECONDS)
        p.add_argument("--size", default=None, help="1280x720 横屏 / 720x1280 竖屏（默认不传）")
        p.add_argument("--first-frame", dest="first_frame", default=None,
                       help="首帧图（本地路径或 URL），走 input_reference")
        p.add_argument("--ref", action="append",
                       help="参考图（本地路径或 URL，可重复；第 1 张是开头画面）")
        p.add_argument("--extra", default=None,
                       help="额外参数 JSON，例如 '{\"ratio\":\"9:16\",\"resolution\":\"720p\"}'")
        p.add_argument("--outdir", default=".", help="--wait 成功后视频保存目录")
        p.add_argument("--prefix", default="mv", help="文件名前缀")
        p.add_argument("--wait", action="store_true",
                       help="提交后等到完成并下载（视频一般 1–15 分钟）")
        p.add_argument("--every", type=int, default=15, help="轮询间隔秒数（默认 15）")
        p.add_argument("--limit", type=int, default=3600, help="等待上限秒数（默认 3600）")
        p.add_argument("--timeout", type=int, default=180, help="提交请求超时秒数")
        p.add_argument("--yes", action="store_true", help="确认真实出片并预冻结")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("gen", help="提交任务（要 --yes；--wait 则等到完成并下载）",
                       allow_abbrev=False)
    add_gen(p)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("status", help="查任务（免费；三条查询路由自动试）",
                       allow_abbrev=False)
    p.add_argument("task_id", nargs="?", help="任务 ID")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("wait", help="等任务完成并下载（免费）", allow_abbrev=False)
    p.add_argument("task_id", nargs="?", help="任务 ID")
    p.add_argument("--outdir", default=".", help="视频保存目录")
    p.add_argument("--prefix", default="mv", help="文件名前缀")
    p.add_argument("--every", type=int, default=15, help="轮询间隔秒数（默认 15）")
    p.add_argument("--limit", type=int, default=3600, help="等待上限秒数（默认 3600）")
    p.set_defaults(fn=cmd_wait)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以（实测只加父级无效）
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--pages", dict(type=int)), ("--max-tokens", dict(type=int))):
            if _n in _sp._option_string_actions:
                continue
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_doctor", "cmd_status", "cmd_wait", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("budget", DEFAULT_BUDGET), ("pages", DEFAULT_PAGES),
                       ("max_tokens", 0), ("json", False)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    if not key and getattr(a.fn, "__name__", "") not in FREE:
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
        say("已中断。任务可能仍在跑 —— 用 `status <id>` 查，同一个任务只查不重提。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
