#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 腾讯云超分台（MPS Super Resolution）

走 api.a7w.cn 的**腾讯云媒体处理（MPS）音视频增强**，把低清视频提到 1080P / 2K / 4K。
**异步任务**：提交拿 `task_id` → 轮询取成片地址。

## 权威规格（取自网关文档 /docs/tencent-superres*，2026-11-07 实测）

  接口根地址   https://api.a7w.cn/api/v1
  1080P        POST /video/tencent1080   → GET /video/tencent1080/{task_id}
  2K           POST /video/tencent2k     → GET /video/tencent2k/{task_id}
  4K           POST /video/tencent4k     → GET /video/tencent4k/{task_id}
  鉴权         Authorization: Bearer <你的 API Key>
  单价         **1080P 2 点/秒 · 2K 4 点/秒 · 4K 8 点/秒**，单笔**保底 10 点**
  计费口径     按**输入视频秒数**（不是输出），失败**全额退回**
  请求         {"video_url": "...", "duration": 600}（`videoUrl` / `url` 也认）
  提交返回     {"task_id","provider","resolution","seconds","points","status"}
  查询返回     处理中 `{"status":"processing"}` · 成功 `{"status":"success","video_url":...}`
               失败 `{"status":"failed","message":...,"refunded":N}`
  成品链接     保留 **24 小时**，请及时下载
  查询免费     查询接口一律不扣费

## 为什么有这一层

网关文档够清楚，但**用户真正会踩的坑都在「时长」和「路由」上**：

  · `duration` 不传 → 平台自己 ffprobe 探测，探测失败直接拒单
    （实测：`400 duration_unknown`「无法探测视频时长，请显式传 duration（秒）」）
  · 所以本包把 `--duration` 做成**必填**，先在本地算好点数再提交
  · `tsc_*`（短剧增强等 11 档）在价目表里，但路由尚未开放，本包只接三档

本包把省钱做成默认动作：`cost` 先报钱（4K 8 点/秒，10 分钟 48 块），
`--budget` 是第一道闸门（一个请求都不发），`--yes` 是第二道，
`doctor` 用「带 video_url 但缺 duration」探端点（上游规定 400，零扣费），
`submit` 结束打印**任务号 / 实际秒数 / 实际点数 / 成片地址**。

## 子命令

  catalog  三档能力清单 + 单价 + 保底（免费）
  cost     先算钱（免费）
  doctor   自检 Key / 余额 / 三档端点 / 查询路由（免费，不扣费）
  submit   提交超分任务（按秒计费，要 --yes）
  status   查一个任务（免费）
  tasks    我最近的超分任务（免费）
  log      本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --tier 4k --duration 600
  python3 scripts/run.py submit --url https://example.com/low.mp4 --tier 4k \
      --duration 600 --yes
  python3 scripts/run.py status task_xxx --tier 4k

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**
"""
import argparse
import json
import math
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
FLOOR_POINTS = 10                      # 单笔保底
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "mps-upscale-ledger.json")

# 档位：路径末段 → 单价（点/秒）+ 显示名
TIERS = {
    "tencent1080": {"label": "1080P", "points": 2, "resolution": "1080P"},
    "tencent2k": {"label": "2K", "points": 4, "resolution": "2K"},
    "tencent4k": {"label": "4K", "points": 8, "resolution": "4K"},
}
TIER_ALIAS = {
    "1080": "tencent1080", "1080p": "tencent1080", "tencent1080": "tencent1080",
    "2k": "tencent2k", "tencent2k": "tencent2k",
    "4k": "tencent4k", "tencent4k": "tencent4k",
}
TIER_ORDER = ("tencent1080", "tencent2k", "tencent4k")

# 价目表里的 tsc_* 档位（11 档）：路由尚未开放，本包不接
TSC_TIERS = ("tsc_teshd", "tsc_shortplay", "tsc_quality", "tsc_uhd")

# 实测：文档写的那条 GET 路由当前返回 SPA HTML 404，统一任务接口才是通的
QUERY_ROUTE_DOC = "%s/video/%%s/%%s" % API_PREFIX          # /video/{tier}/{task_id}
QUERY_ROUTE_OBJ = "%s/videos/%%s" % API_PREFIX             # /videos/{task_id}

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-mps-upscale/%s" % VERSION


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
            with open(cfg, encoding="utf-8") as f:
                d = json.load(f)
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                        # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=90):
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


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def is_html(txt):
    head = (txt or "").lstrip()[:200].lower()
    return head.startswith("<!") or head.startswith("<html")


def err_text(st, txt):
    if is_html(txt):
        return "HTTP %s（网关返回 HTML：这条路由没注册）" % st
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    return (txt or "").replace("\n", " ")[:240]


def parse_tier(v):
    t = TIER_ALIAS.get((v or "").strip().lower())
    if not t:
        raise Fail("usage", "档位只能是 1080p / 2k / 4k（收到 %r）" % (v,), EXIT_USAGE)
    return t


def points_for(tier, duration):
    """预计点数：按输入秒数 × 单价，单笔保底 10 点；小数秒向上取整。"""
    return max(FLOOR_POINTS, int(math.ceil(duration * TIERS[tier]["points"])))


def money(points):
    return round(points / 100.0, 2)


def hhmmss(seconds):
    s = int(round(seconds))
    return "%d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def _w(s):
    """显示宽度：中日韩全角按 2 列算，这样表格能对齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
               for c in str(s))


def pad(s, n):
    s = str(s)
    return s + " " * max(0, n - _w(s))


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            with open(LEDGER, encoding="utf-8") as f:
                arr = json.load(f)
        arr.append(rec)
        with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


def norm_duration(v):
    """把 600 / 600.0 统一成 600；600.5 保留小数。"""
    f = float(v)
    if f == int(f):
        return int(f)
    return round(f, 3)


# ───────────────────── 查询：三级路由 ─────────────────────
def query_task(key, host, tier, task_id, timeout=60):
    """返回 (route, data)。按「文档路由 → 统一任务路由 → 台账」依次试。

    · /video/{tier}/{task_id}   文档写的；实测当前返回 SPA HTML 404
    · /videos/{task_id}         统一任务对象；实测 200 / 400 task_not_exist
    · /me/tasks                 本人台账；带 status / resultUrl / chargedPoints
    """
    tried = []
    for route in (QUERY_ROUTE_DOC % (tier, task_id), QUERY_ROUTE_OBJ % task_id):
        st, txt = http_json("GET", host + route, key, timeout=timeout)
        d = jloads(txt)
        if st == 200 and isinstance(d, dict):
            return route, d
        tried.append("%s→%s" % (route, st))
    st, txt = http_json("GET", host + API_PREFIX + "/me/tasks?per_page=100", key,
                        timeout=timeout)
    d = jloads(txt)
    if st == 200 and isinstance(d, dict):
        for t in (d.get("tasks") or []):
            if isinstance(t, dict) and t.get("taskId") == task_id:
                return "/me/tasks", t
    raise Fail("call", "查不到任务 %s（试过：%s）" % (task_id, " · ".join(tried)), EXIT_CALL)


def task_state(d):
    """把三种返回归一成 (state, progress, video_url, message)。"""
    st = str(d.get("status") or "").lower()
    prog = d.get("progress")
    url = (d.get("video_url") or d.get("resultUrl") or d.get("url")
           or (d.get("resultUrls") or [None])[0])
    msg = d.get("message") or d.get("error") or d.get("failReason") or ""
    if st in ("success", "succeeded", "completed", "done"):
        return "success", prog, url, msg
    if st in ("failed", "error", "cancelled", "canceled"):
        return "failed", prog, url, msg
    if st in ("processing", "running", "pending", "queued", "submitted", ""):
        if url:
            return "success", prog, url, msg
        return "processing", prog, url, msg
    return "processing", prog, url, msg


# ───────────────────────── 子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for t in TIER_ORDER:
        info = TIERS[t]
        rows.append({"tier": t, "resolution": info["resolution"],
                     "pointsPerSecond": info["points"],
                     "floorPoints": FLOOR_POINTS,
                     "points10min": points_for(t, 600),
                     "yuan10min": money(points_for(t, 600)),
                     "points30min": points_for(t, 1800),
                     "yuan30min": money(points_for(t, 1800))})
    out = {"ok": True, "tiers": rows, "floorPoints": FLOOR_POINTS,
           "pendingTiers": list(TSC_TIERS),
           "endpointPattern": "%s/video/{tier}" % API_PREFIX}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("腾讯云超分（MPS 音视频增强）在架三档")
    print()
    print("  " + pad("档位", 8) + pad("分辨率", 9) + pad("单价", 12)
          + pad("10 分钟", 20) + pad("30 分钟", 22))
    print("  " + "-" * 68)
    for r in rows:
        print("  " + pad(r["tier"].replace("tencent", ""), 8)
              + pad(r["resolution"], 9)
              + pad("%d 点/秒" % r["pointsPerSecond"], 12)
              + pad("%d 点（¥%.2f）" % (r["points10min"], r["yuan10min"]), 20)
              + pad("%d 点（¥%.2f）" % (r["points30min"], r["yuan30min"]), 22))
    print()
    print("  单笔保底 %d 点；按**输入视频秒数**计费（不是输出）；失败全额退回。" % FLOOR_POINTS)
    print("  提交：POST %s/video/{tencent1080|tencent2k|tencent4k}" % API_PREFIX)
    print("  查询：GET  %s/video/{tier}/{task_id}（文档）· GET %s/videos/{task_id}"
          % (API_PREFIX, API_PREFIX))
    return 0


def cmd_cost(a, key, host):
    if a.duration is None:
        rows = []
        for t in TIER_ORDER:
            rows.append({"tier": t, "pointsPerSecond": TIERS[t]["points"],
                         "at60s": points_for(t, 60), "at600s": points_for(t, 600),
                         "at1800s": points_for(t, 1800)})
        out = {"ok": True, "floorPoints": FLOOR_POINTS, "table": rows,
               "basis": "平台价目表：1080P 2 点/秒 · 2K 4 点/秒 · 4K 8 点/秒，单笔保底 10 点"}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("腾讯云超分价目（1 元 = 100 点，按输入秒数计费）")
        print()
        print("  " + pad("档位", 8) + pad("单价", 12) + pad("1 分钟", 20)
              + pad("10 分钟", 22) + pad("30 分钟", 24))
        print("  " + "-" * 84)
        for r in rows:
            print("  " + pad(r["tier"].replace("tencent", ""), 8)
                  + pad("%d 点/秒" % r["pointsPerSecond"], 12)
                  + pad("%d 点 / ¥%.2f" % (r["at60s"], money(r["at60s"])), 20)
                  + pad("%d 点 / ¥%.2f" % (r["at600s"], money(r["at600s"])), 22)
                  + pad("%d 点 / ¥%.2f" % (r["at1800s"], money(r["at1800s"])), 24))
        print()
        print("  保底：单笔 %d 点（1 秒 4K 也只收 10 点）。" % FLOOR_POINTS)
        print("  对比 VIAPI：1080P 9 点/秒、2K 15 点/秒、4K 20 点/秒 —— "
              "本线便宜 4.5× / 3.75× / 2.5×。")
        return 0

    tier = parse_tier(a.tier or "4k")
    dur = float(a.duration)
    if dur <= 0:
        raise Fail("usage", "--duration 必须是正数（秒）", EXIT_USAGE)
    pts = points_for(tier, dur)
    out = {"ok": True, "tier": tier, "resolution": TIERS[tier]["resolution"],
           "duration": norm_duration(dur), "pointsPerSecond": TIERS[tier]["points"],
           "floorPoints": FLOOR_POINTS, "total": pts, "yuan": money(pts),
           "basis": "按输入秒数计费，单笔保底 10 点"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    raw = int(math.ceil(dur * TIERS[tier]["points"]))
    print("预估成本")
    print("  档位：%s（%d 点/秒）" % (TIERS[tier]["resolution"], TIERS[tier]["points"]))
    print("  时长：%s（%.0f 秒）" % (hhmmss(dur), dur))
    print("  算账：%.0f 秒 × %d 点/秒 = %d 点" % (dur, TIERS[tier]["points"], raw))
    if raw < FLOOR_POINTS:
        print("  保底：低于单笔保底 %d 点，按 %d 点收" % (FLOOR_POINTS, FLOOR_POINTS))
    print("  应付：**%d 点 = %.2f 元**" % (pts, money(pts)))
    print("  依据：%s" % out["basis"])
    print()
    print("  失败全额退回；查询接口不扣费；成品链接保留 24 小时。")
    return 0


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + "/user/balance", key)
    d = jloads(txt) or {}
    bal = d.get("available_points")
    checks.append(("Key 有效 + 余额可读", st == 200,
                   "HTTP %s · 余额 %s 点" % (st, bal if bal is not None else "-")))

    # 端点探针：带 video_url 但**缺 duration** → 上游规定 400 duration_unknown，停在扣费之前。
    for t in TIER_ORDER:
        st2, txt2 = http_json("POST", host + API_PREFIX + "/video/" + t, key,
                              {"video_url": "https://example.invalid/probe.mp4"})
        d2 = jloads(txt2) or {}
        e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
        code = (e2.get("code") or "")
        ok = st2 == 400 and code == "duration_unknown"
        checks.append(("提交端点 %s 可用（400 duration_unknown 即正确）" % t, ok,
                       "HTTP %s %s" % (st2, code or err_text(st2, txt2)[:40])))

    # 查询路由：/videos/{task_id} 对不存在的 id 返回 400 task_not_exist 即为通
    st3, txt3 = http_json("GET", host + API_PREFIX + "/videos/999999999", key)
    d3 = jloads(txt3) or {}
    ok3 = st3 in (400, 404) and str(d3.get("code") or "") == "task_not_exist"
    checks.append(("查询路由 /api/v1/videos/{task_id} 可用", ok3,
                   "HTTP %s %s" % (st3, d3.get("code") or err_text(st3, txt3)[:40])))

    out = {"ok": all(c[1] for c in checks),
           "endpoint": host + API_PREFIX + "/video/{tier}",
           "floorPoints": FLOOR_POINTS,
           "pointsPerSecond": {t: TIERS[t]["points"] for t in TIER_ORDER},
           "checks": [{"name": n, "ok": o, "detail": det} for n, o, det in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（不扣费：只读 GET + 缺 duration 的 POST，全部停在上游参数校验）")
    print()
    for n, o, det in checks:
        print("  %s %-40s %s" % ("✓" if o else "✗", n, det))
    print()
    print("  提交：%s" % out["endpoint"])
    print("  单价：1080P 2 点/秒 · 2K 4 点/秒 · 4K 8 点/秒，单笔保底 %d 点" % FLOOR_POINTS)
    return 0 if out["ok"] else EXIT_GATE


def _preflight(a, tier, dur):
    if not a.url:
        raise Fail("usage", "必须给 --url（公网可访问的视频地址）", EXIT_USAGE)
    if not (a.url.startswith("http://") or a.url.startswith("https://")):
        raise Fail("usage", "--url 必须是公网可访问的 http(s) 地址：%s" % a.url, EXIT_USAGE)
    if dur is None:
        raise Fail("usage",
                   "必须给 --duration（视频秒数）。平台自动探测会失败并拒单，"
                   "本包要求显式传：`--duration 600`。", EXIT_USAGE)
    dur = float(dur)
    if dur <= 0:
        raise Fail("usage", "--duration 必须是正数（秒）", EXIT_USAGE)
    if dur > 86400:
        raise Fail("usage", "--duration 超过 86400 秒（24 小时），请先切片", EXIT_USAGE)
    cost = points_for(tier, dur)
    if cost > a.budget:
        raise Fail("budget", "预计 %d 点超过 --budget %d 点。调大 --budget 或降档/切片。"
                   % (cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实提交超分并扣约 %d 点（%.2f 元）。确认请加 --yes。"
                   % (cost, money(cost)), EXIT_CONFIRM)
    return cost, dur


def _wait(a, key, host, tier, task_id):
    deadline = time.time() + max(30, a.timeout)
    last = "pending"
    while True:
        try:
            route, d = query_task(key, host, tier, task_id, timeout=60)
        except Fail:
            route, d = None, {}
        state, prog, url, msg = task_state(d) if isinstance(d, dict) else ("processing", None, None, "")
        if state == "success":
            return state, url, msg, prog, route
        if state == "failed":
            return state, url, msg, prog, route
        last = state
        if time.time() > deadline:
            raise Fail("call", "轮询超时（%ds），任务 %s 仍在 %s。稍后 `status %s` 再查。"
                       % (a.timeout, task_id, last, task_id), EXIT_CALL)
        say("  … %s（%s）%s" % (task_id, last,
                               ("进度 %s%%" % prog) if prog not in (None, "") else ""))
        time.sleep(max(3, a.interval))


def cmd_submit(a, key, host):
    tier = parse_tier(a.tier)
    cost, dur = _preflight(a, tier, a.duration)
    url = host + API_PREFIX + "/video/" + tier
    body = {"video_url": a.url, "duration": norm_duration(dur)}
    if a.callback_url:
        body["callback_url"] = a.callback_url

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "tier": tier, "estimatedPoints": cost, "yuan": money(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：%s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (cost, money(cost)))
        return 0

    say("正在提交（%s，%s）…" % (TIERS[tier]["resolution"], hhmmss(dur)))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(60, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    task_id = d.get("task_id") or d.get("taskId") or d.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "http": st, "error": msg, "tier": tier, "seconds": norm_duration(dur)})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)

    secs = d.get("seconds") or norm_duration(dur)
    pts = d.get("points") or cost
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "tier": tier,
           "taskId": task_id, "seconds": secs, "points": pts, "dryRun": False}
    ledger_add(rec)

    result = {"ok": True, "tier": tier, "resolution": d.get("resolution")
              or TIERS[tier]["resolution"], "taskId": task_id,
              "status": d.get("status") or "processing", "seconds": secs,
              "points": pts, "yuan": money(pts), "provider": d.get("provider"),
              "videoUrl": None, "waited": bool(a.wait)}

    if not a.wait:
        if a.json:
            print(json.dumps(result, ensure_ascii=False))
            return 0
        print("已提交（%.1fs）" % dt)
        print("  任务号：%s" % task_id)
        print("  档位：%s · 时长 %s · 预计 %s 点（¥%.2f）"
              % (result["resolution"], hhmmss(float(secs)), pts, money(pts)))
        print("  查询：python3 scripts/run.py status %s --tier %s" % (task_id, tier))
        return 0

    state, vurl, msg, prog, route = _wait(a, key, host, tier, task_id)
    result["status"] = state
    result["videoUrl"] = vurl
    result["route"] = route
    result["error"] = msg or None
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": state == "success",
                "tier": tier, "taskId": task_id, "status": state, "videoUrl": vurl})
    if a.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if state == "success" else EXIT_CALL
    if state != "success":
        say("任务失败：%s（失败全额退回，点数原路返还）" % (msg or state))
        return EXIT_CALL
    print("超分完成")
    print("  任务号：%s" % task_id)
    print("  档位：%s · 输入 %s · 计费 %s 点（¥%.2f）"
          % (result["resolution"], hhmmss(float(secs)), pts, money(pts)))
    print("  成片：%s" % vurl)
    print("  链接保留 24 小时，请及时下载。")
    if a.out and vurl:
        save(vurl, a.out)
        print("  已保存：%s（%d 字节）" % (a.out, os.path.getsize(a.out)))
    return 0


def save(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as x:
        raw = x.read()
    if len(raw) < 10240:
        raise Fail("call", "下载回来的文件只有 %d 字节，不像成片" % len(raw), EXIT_CALL)
    with open(path, "wb") as f:
        f.write(raw)


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给任务号（submit 返回的 task_id）", EXIT_USAGE)
    tier = parse_tier(a.tier)
    route, d = query_task(key, host, tier, a.task_id, timeout=max(30, a.timeout))
    state, prog, vurl, msg = task_state(d)
    out = {"ok": True, "taskId": a.task_id, "tier": tier, "status": state,
           "progress": prog, "videoUrl": vurl,
           "chargedPoints": d.get("chargedPoints"), "netPoints": d.get("netPoints"),
           "route": route, "error": msg or None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s%s" % (state, ("（进度 %s%%）" % prog) if prog not in (None, "") else ""))
    if vurl:
        print("  成片：%s" % vurl)
    if d.get("chargedPoints") is not None:
        print("  扣费：%s 点（净 %s 点）" % (d.get("chargedPoints"), d.get("netPoints")))
    if msg:
        print("  说明：%s" % msg)
    print("  路由：%s（免费）" % route)
    return 0


def cmd_tasks(a, key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/me/tasks?per_page=%d" % a.limit, key)
    if st != 200:
        raise Fail("call", "拉任务列表失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    d = jloads(txt) or {}
    rows = []
    for t in (d.get("tasks") or [])[:a.limit]:
        if not isinstance(t, dict):
            continue
        rows.append({"taskId": t.get("taskId") or t.get("task_id"),
                     "model": t.get("model"), "path": t.get("path"),
                     "status": t.get("status"),
                     "netPoints": t.get("netPoints"), "ms": t.get("ms")})
    mine = [r for r in rows if "/video/" in str(r.get("path") or "")]
    out = {"ok": True, "count": len(rows), "superResCount": len(mine),
           "tasks": rows, "superRes": mine}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("最近 %d 个任务（其中超分 %d 个）" % (len(rows), len(mine)))
    print()
    print("  %-38s %-14s %-26s %-10s %s"
          % ("taskId", "model", "path", "status", "净扣点"))
    print("  " + "-" * 98)
    for r in rows:
        print("  %-38s %-14s %-26s %-10s %s" % (
            (r["taskId"] or "")[:38], (r["model"] or "")[:14],
            (r["path"] or "")[:26], (r["status"] or "")[:10],
            r["netPoints"] if r["netPoints"] is not None else "-"))
    return 0


def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        with open(LEDGER, encoding="utf-8") as f:
            arr = json.load(f)
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        print("  %s  %-8s %-30s %-10s %s 点 / %s 秒" % (
            e.get("at"), (e.get("tier") or "").replace("tencent", ""),
            e.get("taskId") or "-", e.get("status") or ("ok" if e.get("ok") else "fail"),
            e.get("points") or 0, e.get("seconds") or "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 腾讯云超分台（走 api.a7w.cn 的腾讯云 MPS 音视频增强）",
        epilog="端点：POST %s/api/v1/video/{tencent1080|tencent2k|tencent4k} · "
               "GET %s/api/v1/video/{tier}/{task_id} · GET %s/api/v1/videos/{task_id}"
               % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=6000,
                    help="点数上限（单位：点，1 元 = 100 点，默认 6000）")
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="三档能力清单 + 单价 + 保底（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱（免费）", allow_abbrev=False)
    p.add_argument("--tier", default=None, help="1080p / 2k / 4k（默认 4k）")
    p.add_argument("--duration", type=float, default=None,
                   help="视频秒数（不传就打印三档价目表）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 余额 / 三档端点 / 查询路由（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("submit", help="提交超分任务（按秒计费，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--url", help="公网可访问的视频地址（必需）")
    p.add_argument("--tier", default="4k", help="1080p / 2k / 4k（默认 4k）")
    p.add_argument("--duration", type=float, default=None,
                   help="视频秒数（必需；平台自动探测会失败）")
    p.add_argument("--callback-url", default=None, help="任务完成回调地址（可选）")
    p.add_argument("--wait", dest="wait", action="store_true", default=True,
                   help="提交后轮询到完成（默认）")
    p.add_argument("--no-wait", dest="wait", action="store_false",
                   help="只提交，不轮询")
    p.add_argument("--interval", type=int, default=10, help="轮询间隔秒数（默认 10）")
    p.add_argument("--timeout", type=int, default=3600, help="轮询总超时秒数（默认 3600）")
    p.add_argument("--out", default=None, help="把成片下载到这个本地路径（可选）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("status", help="查一个任务（免费）", allow_abbrev=False)
    p.add_argument("task_id", help="submit 返回的 task_id")
    p.add_argument("--tier", default="4k", help="1080p / 2k / 4k（默认 4k）")
    p.add_argument("--timeout", type=int, default=60, help="单次查询超时秒数")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("tasks", help="我最近的任务（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20,
                   help="条数（默认 20；/me/tasks 单页上限 20）")
    p.set_defaults(fn=cmd_tasks)

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
    if not key and a.fn not in (cmd_catalog, cmd_cost, cmd_log):
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
