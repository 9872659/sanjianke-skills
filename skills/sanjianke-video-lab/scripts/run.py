#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 视频后处理台（11 个能力，一个命令）

走 api.a7w.cn 的视频后处理通道，**异步两步**：POST 提交拿 taskId → GET 轮询结果。
11 个能力用 `--tier` 切，每档走哪条路径是 **实测定死的**，不是随手拼的。

## 实测路径表（2026-11-07，空 body 探针，零扣费）

  restore    /api/v1/video/restore          400 pixverse_empty_url   ← 只有扁平这条通
             /api/v1/video/viapi/restore    404 unknown_tool          ← 这条不通
  faceswap   /api/v1/video/faceswap          404（SPA 兜底）           ← 只有 viapi 通
  segment    /api/v1/video/segment           404（SPA 兜底）
  cartoon    /api/v1/video/cartoon           404（SPA 兜底）
  其余 7 档  扁平 / viapi 都 400 empty_url（两条都通，本包统一走 viapi）

所以本包的规则是：**restore 走扁平，其余 10 档统一走 `/api/v1/video/viapi/<tier>`**。
`catalog` 会把每档实际用的路径打出来。

## 价格（POST /api/v1/pricing 实测，单位：点）

  restore 36/秒   cartoon 24/秒   faceswap 20/秒   portrait 18/秒
  enhance 15/秒   colorize 9/秒   subtitle 9/秒    segment 9/秒
  shot 20/次      castcrew 25/次  delogo 25/次

`shot` / `castcrew` / `delogo` 的 note 写「点/次」，price rule 里是 `per_second`。
本包按 note 计一次，同时在 `cost` 里把「按秒引擎」的口径写清楚 —— 以实际结算为准。

## 唯一硬约束：videoUrl 必须是**平台托管**的地址

  实测往 /api/v1/video/viapi/shot 发 {"videoUrl": "https://cdn.example.com/a.mp4"}：
  400 `url_not_allowed`「videoUrl 必须是本站（vr.a7w.cn）、本站七牛
  （cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）」

  → 所以 `upload` 是配套子命令：POST /api/v1/upload（multipart，字段名 file，免费）
    返回 data.url（oss.gpu.likeadmin.cn/openapi/…，最长 24 小时），直接喂给 submit。
  `submit` 会先本地预检这条白名单，不合格当场退回、不浪费一次请求（--allow-any-url 可跳过）。

## 子命令

  catalog  11 档能力 + 每档实际路径 + 单价（免费）
  cost     先算钱：1 / 10 / 30 分钟价目（免费）
  doctor   自检 Key / 11 个端点 / 价目表 / 查询路由 / 上传（免费，不扣费）
  upload   上传本地视频，拿一个能直接提交的地址（免费）
  submit   提交任务（要 --yes，受 --budget 管）
  status   查任务（免费；先查通用 GET /api/v1/tasks/{id}）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --tier restore --seconds 600
  python3 scripts/run.py doctor
  python3 scripts/run.py upload --file input.mp4
  python3 scripts/run.py submit --tier delogo --video-url "https://oss.gpu.likeadmin.cn/openapi/..." --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # 中文控制台不因个别符号崩掉
    except Exception:                        # noqa: BLE001
        pass

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "video-lab-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-video-lab/%s" % VERSION

# ── 11 档能力：单价来自 GET /api/v1/pricing，路径来自空 body 探针 ────────────
#  route: flat  → /api/v1/video/<tier>
#         viapi → /api/v1/video/viapi/<tier>
TIERS = {
    "restore": dict(points=36, unit="per_second", route="flat",
                    name="视频修复", action="video-restore（站内通道）",
                    desc="去划痕 / 噪点 / 闪烁 / 压缩损伤，老片抢救"),
    "cartoon": dict(points=24, unit="per_second", route="viapi",
                    name="人像卡通化", action="GenerateHumanAnimeStyleVideo",
                    desc="真人转动漫风，短剧二创封面感"),
    "faceswap": dict(points=20, unit="per_second", route="viapi",
                     name="换脸 / 人脸融合", action="MergeVideoFace",
                     extra="faceUrl", desc="把视频里最大的人脸换成你的人脸图"),
    "portrait": dict(points=18, unit="per_second", route="viapi",
                     name="人像增强", action="EnhancePortraitVideo",
                     desc="只提人脸清晰度，GPEN 路线"),
    "enhance": dict(points=15, unit="per_second", route="viapi",
                    name="画质综合增强", action="EnhanceVideoQuality",
                    desc="清晰度 / 对比度 / 细节整体提一档"),
    "colorize": dict(points=9, unit="per_second", route="viapi",
                     name="视频校色 / 黑白上色", action="AdjustVideoColor",
                     desc="黑白片自动上色，还原自然色调"),
    "subtitle": dict(points=9, unit="per_second", route="viapi",
                     name="字幕擦除", action="EraseVideoSubtitles",
                     desc="擦掉硬字幕，二创换字幕的第一步"),
    "segment": dict(points=9, unit="per_second", route="viapi",
                    name="人像抠像 / 绿幕", action="SegmentVideoBody",
                    desc="输出人像 mask 视频，换背景用"),
    "shot": dict(points=20, unit="per_call", route="viapi",
                 name="镜头检测", action="DetectVideoShot",
                 desc="按镜头切分，返回切点帧号，纯结构化结果"),
    "castcrew": dict(points=25, unit="per_call", route="viapi",
                     name="硬字幕 / 演职员表 OCR", action="RecognizeVideoCastCrewList",
                     desc="抽出硬字幕与滚动演职员表，附 SRT"),
    "delogo": dict(points=25, unit="per_call", route="viapi",
                   name="台标 / Logo 擦除", action="EraseVideoLogo",
                   desc="擦掉台标、平台 logo（最多 2 个区域）"),
}
TIER_ORDER = ["colorize", "segment", "subtitle", "enhance", "portrait", "faceswap",
              "shot", "cartoon", "castcrew", "delogo", "restore"]
DEFAULT_DURATION = 5          # 文档：duration 缺省 5 秒（用于预冻结）
POINTS_PER_YUAN = 100

# 上游对 videoUrl 的白名单（实测报错原文）：
#   本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）、
#   本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）
UPLOAD_PATH = API_PREFIX + "/upload"


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
        except Exception:                                            # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120):
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


def http_multipart(url, key, fields, files, timeout=600):
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
        with open(path, "rb") as fh:
            buf.write(fh.read())
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
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """上游只收本站托管的地址。返回 (ok, 说明)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                            # noqa: BLE001
        return False, "URL 解析失败"
    host = (p.hostname or "").lower()
    path = p.path or ""
    if host == "vr.a7w.cn" or host.endswith(".a7w.cn"):
        return True, "本站"
    if host == "cdn2.jiujiushuyuan.cn" and path.startswith("/vr/"):
        return True, "本站七牛"
    if host == "oss.gpu.likeadmin.cn" and path.startswith("/openapi/"):
        return True, "本站上传接口"
    return False, host or u[:60]


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
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return txt.replace("\n", " ")[:240]


def route_path(tier, route=None):
    """实际要打的路径。tier 必须是 TIERS 里的键。"""
    meta = TIERS[tier]
    how = route or "auto"
    if how == "auto":
        how = meta["route"]
    if how == "viapi":
        return API_PREFIX + "/video/viapi/" + tier
    return API_PREFIX + "/video/" + tier


def unit_label(meta):
    return "点/秒" if meta["unit"] == "per_second" else "点/次"


def estimate(tier, seconds, count):
    """返回 (点数, 口径说明)。per_second 用秒数，per_call 用次数。"""
    meta = TIERS[tier]
    if meta["unit"] == "per_second":
        pts = meta["points"] * max(1, int(seconds)) * max(1, int(count))
        basis = "%d 点/秒 × %d 秒 × %d 次 = %d 点" % (
            meta["points"], seconds, count, pts)
    else:
        pts = meta["points"] * max(1, int(count))
        basis = "%d 点/次 × %d 次 = %d 点（与素材时长无关）" % (
            meta["points"], count, pts)
    return pts, basis


def fmt_pts(n):
    return "{:,}".format(int(round(n)))


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


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for t in TIER_ORDER:
        m = TIERS[t]
        rows.append({"tier": t, "name": m["name"], "points": m["points"],
                     "unit": unit_label(m), "unitCode": m["unit"],
                     "path": route_path(t), "route": m["route"],
                     "action": m["action"], "desc": m["desc"]})
    out = {"ok": True, "count": len(rows), "tiers": rows,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 视频后处理台 —— 11 档能力（按单价从低到高）")
    print()
    print("  %-9s %-22s %-35s %-11s %s" % ("--tier", "能力", "实际路径", "单价", "一句话"))
    print("  " + "-" * 108)
    for r in rows:
        print("  %-9s %-22s %-35s %-11s %s" % (
            r["tier"], r["name"], r["path"], "%d %s" % (r["points"], r["unit"]),
            r["desc"]))
    print()
    print("  路径规则：restore 只走扁平 /api/v1/video/restore；其余 10 档统一走")
    print("  /api/v1/video/viapi/<tier>。每一条都用空 body 探针验过，验完仍是 0 条任务。")
    print()
    print("  1 元 = 100 点。最便宜的三档 colorize / segment / subtitle 都是 9 点/秒（0.09 元）。")
    return 0


def cmd_cost(a, key, host):
    tiers = list(TIERS) if not a.tier else [a.tier]
    seconds = a.seconds
    detail = None
    if a.tier:
        pts, basis = estimate(a.tier, seconds, a.count)
        detail = {"tier": a.tier, "seconds": seconds, "count": a.count,
                  "points": pts, "yuan": round(pts / float(POINTS_PER_YUAN), 2),
                  "basis": basis}
    table = []
    for t in TIER_ORDER:
        if t not in tiers:
            continue
        m = TIERS[t]
        row = {"tier": t, "unit": unit_label(m), "points": m["points"]}
        if m["unit"] == "per_second":
            row.update({"m1": m["points"] * 60, "m10": m["points"] * 600,
                        "m30": m["points"] * 1800})
        else:
            row.update({"m1": m["points"], "m10": m["points"], "m30": m["points"],
                        "perCall": True})
        table.append(row)
    out = {"ok": True, "seconds": seconds, "count": a.count,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "table": table, "detail": detail,
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-07 实测）",
               "按秒档按视频秒数计费，最小计 1 秒",
               "shot / castcrew / delogo：note 写「点/次」，rule 里是 per_second，"
               "本包按 note 计一次，实际结算以上游为准",
               "portrait：rule 是 18 点/秒，note 写「公测免费」，以实际账单为准",
               "任务失败全额退回；按秒档先按秒数冻结、完成后按实际时长结算",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print()
    if detail:
        print("  --tier %s（%s，%s）" % (a.tier, TIERS[a.tier]["name"],
                                        unit_label(TIERS[a.tier])))
        print("  %s" % detail["basis"])
        print("  = %d 点 = %.2f 元" % (detail["points"], detail["yuan"]))
        print()
    print("  %-9s %-9s %10s %10s %10s" % ("--tier", "单价", "1 分钟", "10 分钟", "30 分钟"))
    print("  " + "-" * 56)
    for r in table:
        mark = "  ← 按次" if r.get("perCall") else ""
        print("  %-9s %-9s %10s %10s %10s%s" % (
            r["tier"], "%d %s" % (r["points"], r["unit"]),
            fmt_pts(r["m1"]), fmt_pts(r["m10"]), fmt_pts(r["m30"]), mark))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


TIER_PROBE_EXPECT = {"restore": "pixverse_empty_url"}     # 其余都是 empty_url


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(d.get("available_points") or d.get("points") or 0),
                       fmt_pts(d.get("frozen") or 0))))

    # 价目表：本地写死的 11 个单价 vs /api/v1/pricing 现查
    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
    pricing, drift = {}, []
    if st_p == 200:
        try:
            pricing = (jloads(txt_p) or {}).get("pricing") or {}
        except Exception:                                        # noqa: BLE001
            pricing = {}
    for t in TIER_ORDER:
        row = pricing.get(route_path(t)) or {}
        live = row.get("perSecond")
        if live is None:
            drift.append("%s 线上无此键" % t)
        elif int(live) != TIERS[t]["points"]:
            drift.append("%s 本地 %d / 线上 %s" % (t, TIERS[t]["points"], live))
    checks.append(("11 档单价与 /api/v1/pricing 一致", st_p == 200 and not drift,
                   "HTTP %s · %s" % (st_p, "全一致" if not drift else " / ".join(drift)[:120])))

    # 端点探针：空 body → 400 参数校验，停在扣费之前
    for t in TIER_ORDER:
        path = route_path(t)
        want = TIER_PROBE_EXPECT.get(t, "empty_url")
        say("  探 %-9s %s …" % (t, path))
        st2, txt2 = http_json("POST", host + path, key, {}, timeout=a.timeout)
        d2 = jloads(txt2) or {}
        e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
        code = (e2.get("code") or "")
        ok2 = st2 == 400 and code == want
        checks.append(("端点 %-9s 可用（400 %s 即正确）" % (t, want), ok2,
                       "HTTP %s %s" % (st2, code or err_text(st2, txt2)[:40])))

    # 查询路由：假 taskId → 结构化 not_found 说明路由在
    for label, path in (("viapi 查询路由", API_PREFIX + "/video/viapi/result/probe-no-such-task"),
                        ("restore 查询路由", API_PREFIX + "/video/restore/probe-no-such-task")):
        st3, txt3 = http_json("GET", host + path, key, timeout=40)
        d3 = jloads(txt3) or {}
        code3 = ((d3.get("error") or {}) if isinstance(d3.get("error"), dict) else {}).get("code") or ""
        checks.append((label + "可达（404 not_found 即正确）", st3 == 404 and code3 == "not_found",
                       "HTTP %s %s" % (st3, code3 or err_text(st3, txt3)[:40])))

    # 通用任务查询：假 id → code 0「任务不存在」，说明路由在且不扣费
    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task", key, timeout=40)
    d4 = jloads(txt4) or {}
    checks.append(("通用任务查询 GET /tasks/{id} 可用", st4 == 200 and d4.get("code") == 0,
                   "HTTP %s %s" % (st4, (d4.get("msg") or "")[:40])))

    # 上传接口：不带 file → 参数校验提示，不落文件
    st5, txt5 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
    d5 = jloads(txt5) or {}
    checks.append(("上传接口 POST /upload 可用", st5 == 200 and d5.get("code") == 0,
                   "HTTP %s %s" % (st5, (d5.get("msg") or "")[:40])))

    out = {"ok": all(c[1] for c in checks), "host": host, "tierCount": len(TIERS),
           "pricingSource": host + API_PREFIX + "/pricing",
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print()
    print("自检（不扣费：只读接口 + 空 body 触发参数校验，任务 0 条、冻结 0 点）")
    print()
    for n, o, d in checks:
        print("  %s %-42s %s" % ("√" if o else "×", n, d))
    print()
    print("  端点：11 档，restore 走扁平，其余走 /api/v1/video/viapi/<tier>")
    print("  配套：upload 拿地址 · GET /video/viapi/result/{id} 查进度 · /pricing 对价")
    print("  单价：最便宜 9 点/秒，最贵 36 点/秒（1 元 = 100 点）")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 上传 ─────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要上传的视频/图片路径）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传）")
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        return 0
    say("正在上传 %s（%d 字节）…" % (os.path.basename(path), size))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "mode": "upload",
                    "file": path, "http": st, "error": msg})
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    ok_url, kind = url_allowed(got)
    out = {"ok": True, "url": got, "path": data.get("path"), "name": data.get("name"),
           "size": data.get("size"), "mime": data.get("mime_type"),
           "type": data.get("type"), "hostKind": kind, "urlAllowed": ok_url,
           "elapsed": round(dt, 1)}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "upload",
                "file": path, "size": size, "url": got, "elapsed": round(dt, 1)})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs）" % dt)
    print("  地址：%s" % got)
    print("  类型：%s · %s · %d 字节" % (data.get("type"), data.get("mime_type"),
                                        data.get("size") or size))
    print("  归属：%s（上游白名单内，可直接给 submit 用）" % kind)
    print()
    print("  下一步：python3 scripts/run.py submit --tier colorize --video-url \"%s\" --yes" % got)
    return 0


# ───────────────────────── 提交 ─────────────────────────
def _preflight(a, tier, seconds, count):
    meta = TIERS[tier]
    if not a.video_url:
        raise Fail("usage", "必须给 --video-url（平台托管的视频地址，先用 upload 拿）",
                   EXIT_USAGE)
    if not re.match(r"^https?://", a.video_url, re.I):
        raise Fail("usage", "--video-url 要以 http:// 或 https:// 开头", EXIT_USAGE)
    ok_url, kind = url_allowed(a.video_url)
    if not ok_url and not a.allow_any_url:
        raise Fail("usage",
                   "上游只收本站托管的地址（%s 不在白名单）。三种可用写法：\n"
                   "  · 先 upload 再 submit（推荐）：python3 scripts/run.py upload --file 你的视频.mp4\n"
                   "  · 本站成片地址：https://vr.a7w.cn/result/xxx.mp4\n"
                   "  · 本站七牛：https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4\n"
                   "确实要用外站地址时加 --allow-any-url 交给上游判断。" % kind,
                   EXIT_USAGE)
    if meta.get("extra") == "faceUrl" and not a.face_url:
        raise Fail("usage", "%s 这档还要 --face-url（人脸参考图，任意 http(s) 图片地址）"
                   % tier, EXIT_USAGE)
    if a.face_url and meta.get("extra") != "faceUrl":
        raise Fail("usage", "--face-url 只用于 faceswap 这档", EXIT_USAGE)
    if (a.seed is not None or a.callback_url) and tier != "restore":
        raise Fail("usage", "--seed / --callback-url 只用于 restore 这档", EXIT_USAGE)
    cost, basis = estimate(tier, seconds, count)
    if cost > a.budget:
        raise Fail("budget", "预计 %d 点超过 --budget %d 点（%s）。调大 --budget 或缩小时长。"
                   % (cost, a.budget, basis), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实提交视频任务并预冻结约 %d 点（%.2f 元）。确认请加 --yes。"
                   % (cost, cost / float(POINTS_PER_YUAN)), EXIT_CONFIRM)
    return cost, basis


def _body(a, tier):
    meta = TIERS[tier]
    body = {"videoUrl": a.video_url}
    if meta["unit"] == "per_second":
        body["duration"] = int(a.duration) if a.duration is not None else DEFAULT_DURATION
    if meta.get("extra") == "faceUrl":
        body["faceUrl"] = a.face_url
    if tier == "restore":
        if a.seed is not None:
            body["seed"] = a.seed
        if a.callback_url:
            body["callback_url"] = a.callback_url
    return body


def cmd_submit(a, key, host):
    tier = a.tier
    seconds = a.duration if a.duration is not None else DEFAULT_DURATION
    cost, basis = _preflight(a, tier, seconds, 1)
    path = route_path(tier, a.route)
    url = host + path
    body = _body(a, tier)

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "tier": tier, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": round(cost / float(POINTS_PER_YUAN), 2),
               "basis": basis}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：%s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）· %s" % (cost, cost / float(POINTS_PER_YUAN), basis))
        return 0

    say("正在提交 %s（%s，%s）…" % (tier, TIERS[tier]["name"], unit_label(TIERS[tier])))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if isinstance(d.get("data"), dict) and d.get("code") == 1:
        d = d["data"]                                   # 统一成扁平结构
    if st not in (200, 201) or d.get("code") == 0:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "mode": "submit",
                    "tier": tier, "http": st, "error": msg, "endpoint": path})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)

    task_id = d.get("taskId") or d.get("task_id") or d.get("id")
    status = d.get("status")
    real_cost = d.get("cost")
    out = {"ok": bool(task_id), "tier": tier, "taskId": task_id, "status": status,
           "duration": d.get("duration"), "cost": real_cost, "balance": d.get("balance"),
           "estimatedPoints": cost, "elapsed": round(dt, 1), "endpoint": path,
           "query": API_PREFIX + ("/video/viapi/result/" if TIERS[tier]["route"] == "viapi"
                                  else "/video/" + tier + "/") + str(task_id or "<taskId>")}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(task_id),
                "mode": "submit", "tier": tier, "taskId": task_id, "status": status,
                "duration": d.get("duration"), "cost": real_cost,
                "estimatedPoints": cost, "elapsed": round(dt, 1), "endpoint": path})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if task_id else EXIT_CALL
    if not task_id:
        say("  响应里没有 taskId。原始返回：")
        print(txt[:800])
        return EXIT_CALL
    print("已提交（%.1fs）" % dt)
    print("  能力：%s（%s）" % (tier, TIERS[tier]["name"]))
    print("  任务：%s   状态：%s" % (task_id, status))
    if d.get("duration") is not None:
        print("  时长：%s 秒" % d.get("duration"))
    if real_cost is not None:
        print("  预冻结：%s 点（完成后按实际时长结算，失败全额退回）" % real_cost)
    if d.get("balance") is not None:
        print("  余额：%s 点" % fmt_pts(d["balance"]))
    print()
    print("  查进度：python3 scripts/run.py status --task-id %s --tier %s"
          % (task_id, tier))
    return 0


def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    # 顺序有讲究：通用 /tasks/{id} **查不到视频后处理任务**（实测返回「任务不存在」），
    # 真正的视图在 /api/v1/video/viapi/result/{id} 与各档 /<tier>/{id}（两者同源）。
    # 实测同一 taskId 会先 failed + refund，几分钟后回到 processing（平台自动重试）。
    cands = [API_PREFIX + "/tasks/" + tid,
             API_PREFIX + "/video/viapi/result/" + tid,
             API_PREFIX + "/video/viapi/query/" + tid]
    if a.tier:
        cands.append(route_path(a.tier) + "/" + tid)
    for t in TIER_ORDER:
        p = route_path(t) + "/" + tid
        if p not in cands:
            cands.append(p)

    hit = None
    for p in cands:
        st, txt = http_json("GET", host + p, key, timeout=40)
        d = jloads(txt) or {}
        e = d.get("error") if isinstance(d.get("error"), dict) else {}
        empty = (st == 404 and e.get("code") == "not_found") or (
            st == 200 and d.get("code") == 0 and not d.get("data"))
        if empty:
            continue
        hit = (p, st, txt, d)
        break
    if hit is None:
        raise Fail("call", "查不到任务 %s（试过 %d 条查询路由，都说不存在）。"
                   % (tid, len(cands)), EXIT_CALL)
    p, st, txt, d = hit
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if isinstance(d.get("data"), dict) and d.get("code") == 1:
        d = d["data"]
    usage = d.get("usage") if isinstance(d.get("usage"), dict) else {}
    cost = d.get("cost") if d.get("cost") is not None else usage.get("points_cost")
    out = {"ok": True, "taskId": tid, "path": p, "tool": d.get("tool"),
           "status": d.get("status"), "message": d.get("message"),
           "videoUrl": d.get("videoUrl"), "artifactUrl": d.get("artifactUrl"),
           "cost": cost, "refund": d.get("refund"), "result": d.get("result"),
           "error": d.get("error")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  查询路径：%s" % p)
    if d.get("tool"):
        print("  能力：%s" % d.get("tool"))
    print("  状态：%s" % d.get("status"))
    if cost is not None:
        print("  实扣：%s 点" % cost)
    if d.get("refund") is not None:
        print("  退回：%s 点" % d.get("refund"))
    if d.get("message"):
        print("  说明：%s" % str(d.get("message"))[:300])
    if d.get("videoUrl"):
        print("  成片：%s  (链接约 30 分钟有效，及时转存)" % d.get("videoUrl"))
    if d.get("artifactUrl"):
        print("  附件：%s" % d.get("artifactUrl"))
    if d.get("error"):
        print("  错误：%s" % json.dumps(d.get("error"), ensure_ascii=False)[:300])
    if d.get("result") is not None:
        print("  结果：%s" % json.dumps(d.get("result"), ensure_ascii=False)[:600])
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
        mode = e.get("mode") or "-"
        if mode == "upload":
            what = os.path.basename(e.get("file") or "-")
            pts = "-"
        else:
            what = e.get("taskId") or (e.get("error") or "")[:40] or "-"
            pts = e.get("estimatedPoints")
        print("  %s  %-6s %-6s %-9s %-40s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", mode, e.get("tier") or "-",
            what[:40], ("%s 点" % pts) if pts not in (None, "-") else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 视频后处理台（11 个能力一个命令，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/video/restore（restore）· "
               "POST %s/api/v1/video/viapi/<tier>（其余 10 档）· "
               "POST %s/api/v1/upload（先传后提交）· GET %s/api/v1/tasks/<taskId>" % (
                   DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=5000,
                    help="点数上限（单位：点，默认 5000 = 50 元）")
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="11 档能力 + 每档实际路径 + 单价（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：1/10/30 分钟价目（免费）", allow_abbrev=False)
    p.add_argument("--tier", choices=TIER_ORDER, help="只看这一档（默认全部）")
    p.add_argument("--seconds", type=int, default=60, help="按多少秒估算（默认 60）")
    p.add_argument("--count", type=int, default=1, help="跑几次（默认 1）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 11 个端点 / 价目表（免费，不扣费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="上传本地视频，拿一个能直接提交的地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径（默认单文件 512 MB 上限）")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    def add_submit(p):
        p.add_argument("--tier", choices=TIER_ORDER, required=True,
                       help="能力档位，见 catalog")
        p.add_argument("--video-url", help="视频地址，必须公网可访问（http/https）")
        p.add_argument("--duration", type=int, default=None,
                       help="视频秒数（用于预冻结，缺省 %d 秒）" % DEFAULT_DURATION)
        p.add_argument("--face-url", help="人像参考图地址（只 faceswap 用）")
        p.add_argument("--seed", type=int, default=None, help="随机种子（只 restore 用）")
        p.add_argument("--callback-url", help="完成回调地址（只 restore 用）")
        p.add_argument("--route", choices=["auto", "flat", "viapi"], default="auto",
                       help="强制走扁平或 viapi 路径（默认 auto：按实测表选）")
        p.add_argument("--allow-any-url", action="store_true",
                       help="跳过本地白名单预检，把地址直接交给上游判断")
        p.add_argument("--timeout", type=int, default=120, help="提交超时秒数（默认 120）")
        p.add_argument("--yes", action="store_true", help="确认真实提交并冻结点数")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("submit", help="提交任务（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    add_submit(p)
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("status", help="查任务（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 taskId")
    p.add_argument("--tier", choices=TIER_ORDER, help="知道是哪一档时填上，查得更快")
    p.set_defaults(fn=cmd_status)

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


FREE = ("cmd_catalog", "cmd_cost", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key, host = load_conf(a.key, a.host)
    fn_name = getattr(a.fn, "__name__", "")
    if not key and fn_name not in FREE:
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
