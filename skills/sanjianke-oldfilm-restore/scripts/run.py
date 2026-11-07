#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 老片转高清一条龙（超分 / 校色 / 增强 / 修复 串成一条流水线）

**一条命令跑完 3~4 个工序**：每一步的产物落盘，下一步自动接着喂，
断在半路用 `resume` 接着跑（**不会重复付费**）。

## 实测路径表（2026-11-07，空 body 探针，零扣费）

  校色     POST /api/v1/video/viapi/colorize     -> 400 empty_url
  标准超分  POST /api/v1/video/viapi/superres     -> 400 empty_url
  增强     POST /api/v1/video/viapi/enhance      -> 400 empty_url
  2K 超分  POST /api/v1/video/viapi/superres2k   -> 400 empty_url
  人像增强  POST /api/v1/video/viapi/portrait     -> 400 empty_url
  4K 超分  POST /api/v1/video/viapi/superres4k   -> 400 empty_url
  视频修复  POST /api/v1/video/restore           -> 400 pixverse_empty_url   ← 只有扁平这条通
           POST /api/v1/video/viapi/restore     -> 404 unknown_tool          ← 这条是 404

  查询     GET  /api/v1/video/viapi/result/<taskId>      -> 404 not_found（路由在，免费）
           GET  /api/v1/video/restore/<taskId>           -> 404 not_found（路由在，免费）

## 价格（GET /api/v1/pricing 实测，单位：点/秒，1 元 = 100 点）

  colorize 9   superres 9   enhance 15   superres2k 15
  portrait 18  superres4k 20  restore 36

## 唯一硬约束：videoUrl 必须是**平台托管**的地址

  外站地址会 400 `url_not_allowed`：
  「videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
    或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）」

  → 所以每一步的产物都先落盘，再按白名单决定「直接用成片链接」还是
    「重新 POST /api/v1/upload 拿一个白名单地址」（upload 免费）。
  → 链条的第一脚也支持 `--video-url` 直接给一个已托管的地址。

## 计费口径

  按秒计费，先按 `duration` 冻结、完成后按实际时长结算，任务失败全额退回。
  本包把 `duration` 按实测时长显式传上去，冻结多少就是多少。

## 子命令

  catalog  7 档能力 + 实际路径 + 单价（免费）
  cost     5 套预设的钱（免费）
  plan     打印完整流水线计划与每一步的请求体（本地，免费）
  doctor   自检 Key / 7 个端点 / 价目表 / 查询路由 / 上传（免费，不扣费）
  upload   上传本地片子，拿一个能直接提交的地址（免费）
  run      起一条流水线（要 --yes，受 --budget 管）
  resume   断点续跑（已完成的步不重跑、已提交的任务不重提）
  status   查单个任务（免费）
  log      本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --seconds 60
  python3 scripts/run.py plan --preset standard --seconds 60
  python3 scripts/run.py run --file old.mp4 --preset standard --yes
  python3 scripts/run.py run --file old.mp4 --preset repair --no-wait
  python3 scripts/run.py resume --workdir oldfilm-work
  python3 scripts/run.py status --task-id task_xxx --tier superres

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
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

# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8。
# 先把 errors 兜成 replace，再全篇只用 cp936 编得出的符号（√ × → · ─ ），
# 编不出的符号一个都不出现，PYTHONIOENCODING=gbk 也照样 exit=0。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "oldfilm-ledger.json")
DEFAULT_WORKDIR = "oldfilm-work"
DEFAULT_SECONDS = 60
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 5000

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-oldfilm-restore/%s" % VERSION

UPLOAD_PATH = API_PREFIX + "/upload"

# ── 7 档能力：单价取自 GET /api/v1/pricing，路径取自空 body 探针 ─────────────
#   route flat  → /api/v1/video/<tier>          （只有 restore 走这条）
#         viapi → /api/v1/video/viapi/<tier>
TIERS = {
    "colorize": dict(points=9, route="viapi", name="校色 / 黑白上色",
                     action="AdjustVideoColor",
                     desc="灰片、偏色、黑白片还原自然色调"),
    "superres": dict(points=9, route="viapi", name="标准超分 1080P",
                     action="SuperResolution", desc="480P / 720P 提到 1080P"),
    "enhance": dict(points=15, route="viapi", name="画质综合增强",
                    action="EnhanceVideoQuality",
                    desc="清晰度 / 对比度 / 细节整体提一档，收尾用"),
    "superres2k": dict(points=15, route="viapi", name="高清超分 2K/60 帧",
                       action="SuperResolution2K", desc="2K 交付，顺带补帧到 60"),
    "portrait": dict(points=18, route="viapi", name="人像增强",
                     action="EnhancePortraitVideo",
                     desc="只提人脸清晰度，人物特写多的片子"),
    "superres4k": dict(points=20, route="viapi", name="超分 4K",
                       action="SuperResolution4K", desc="4K 交付"),
    "restore": dict(points=36, route="flat", name="视频修复",
                    action="video-restore（站内通道）",
                    desc="去划痕 / 噪点 / 闪烁 / 压缩损伤，老胶片抢救"),
}
TIER_ORDER = ["colorize", "superres", "enhance", "superres2k", "portrait",
              "superres4k", "restore"]

# ── 5 套预设：顺序是「先修、再分、后调」──────────────────────────────────────
#   修复压最前面（噪点被超分会一起放大），超分居中，校色与增强收尾。
PRESETS = {
    "quick": dict(steps=["superres", "enhance"],
                  name="快修", note="片源还算干净，只补清晰度"),
    "standard": dict(steps=["superres", "colorize", "enhance"],
                     name="标准一条龙", note="默认：超分 → 校色 → 增强"),
    "repair": dict(steps=["restore", "superres", "colorize"],
                   name="老片抢救", note="有划痕 / 噪点 / 闪烁的老胶片"),
    "cinema": dict(steps=["restore", "superres4k", "enhance"],
                   name="4K 交付", note="修复 → 4K 超分 → 增强"),
    "portrait": dict(steps=["portrait", "superres2k", "enhance"],
                     name="人物特写", note="人像先提清，再 2K，再增强"),
}
PRESET_ORDER = ["quick", "standard", "repair", "portrait", "cinema"]
DEFAULT_PRESET = "standard"

TERMINAL_OK = ("completed", "success", "succeeded", "done")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "timeout", "expired")


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


def http_json(method, url, key, body=None, timeout=120, retries=3):
    """发一次请求。网关会重置空闲连接（WinError 10054），网络类错误退避重试；
    4xx 是业务错误，原样交给调用方判断。"""
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
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, getattr(e, "reason", e), retries - 1), EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


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
    except (urllib.error.URLError, ConnectionResetError) as e:
        raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


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
        if d.get("code") is not None:
            return str(d.get("code"))[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return txt.replace("\n", " ")[:240]


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


def route_path(tier):
    if TIERS[tier]["route"] == "viapi":
        return API_PREFIX + "/video/viapi/" + tier
    return API_PREFIX + "/video/" + tier


def query_path(tier, task_id):
    tid = urllib.parse.quote(str(task_id))
    if TIERS[tier]["route"] == "viapi":
        return API_PREFIX + "/video/viapi/result/" + tid
    return API_PREFIX + "/video/" + tier + "/" + tid


def query_hint(tier):
    if TIERS[tier]["route"] == "viapi":
        return API_PREFIX + "/video/viapi/result/<taskId>"
    return API_PREFIX + "/video/" + tier + "/<taskId>"


def money(pts):
    """324.0 -> '324'；19.8 -> '19.8'；14.4 -> '14.4'。"""
    return ("%.2f" % (float(pts) / POINTS_PER_YUAN)).rstrip("0").rstrip(".")


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                            # noqa: BLE001
        return str(n)


def yuan(pts):
    return round(float(pts) / POINTS_PER_YUAN, 2)


# ───────────────────────── 计划与价格（全本地，免费） ─────────────────────────
def resolve_steps(a):
    if getattr(a, "steps", None):
        raw = [s.strip() for s in a.steps.split(",") if s.strip()]
        bad = [s for s in raw if s not in TIERS]
        if bad:
            raise Fail("usage", "--steps 里有不认识的工序：%s（可选：%s）"
                       % (", ".join(bad), " / ".join(TIER_ORDER)), EXIT_USAGE)
        if len(raw) > 4:
            raise Fail("usage", "一条流水线最多串 4 步（当前 %d 步）。步数越多越贵。"
                       % len(raw), EXIT_USAGE)
        return raw
    preset = getattr(a, "preset", None) or DEFAULT_PRESET
    if preset not in PRESETS:
        raise Fail("usage", "--preset 只能是：%s" % " / ".join(PRESET_ORDER), EXIT_USAGE)
    return list(PRESETS[preset]["steps"])


def chain_cost(steps, seconds):
    rows, total = [], 0
    for i, t in enumerate(steps, 1):
        pts = TIERS[t]["points"] * max(1, int(seconds))
        total += pts
        rows.append({"i": i, "tier": t, "name": TIERS[t]["name"],
                     "pointsPerSecond": TIERS[t]["points"], "points": pts,
                     "path": route_path(t)})
    return rows, total


def basis_text(steps, seconds):
    return " + ".join("%s %d" % (t, TIERS[t]["points"]) for t in steps) + \
        " = %d 点/秒 × %d 秒 = %d 点" % (
            sum(TIERS[t]["points"] for t in steps), seconds,
            sum(TIERS[t]["points"] for t in steps) * max(1, int(seconds)))


def probe_seconds(path):
    """零依赖读 MP4/MOV 的 mvhd 拿时长。读不出来返回 None。"""
    try:
        size = os.path.getsize(path)

        def boxes(f, start, end):
            pos = start
            while pos + 8 <= end:
                f.seek(pos)
                hdr = f.read(8)
                if len(hdr) < 8:
                    return
                n = int.from_bytes(hdr[0:4], "big")
                typ = hdr[4:8]
                hsz = 8
                if n == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        return
                    n = int.from_bytes(ext, "big")
                    hsz = 16
                elif n == 0:
                    n = end - pos
                if n < hsz or pos + n > end:
                    return
                yield typ, pos, hsz, n
                pos += n

        with open(path, "rb") as f:
            for typ, pos, hsz, n in boxes(f, 0, size):
                if typ != b"moov":
                    continue
                for t2, p2, h2, _n2 in boxes(f, pos + hsz, pos + n):
                    if t2 != b"mvhd":
                        continue
                    f.seek(p2 + h2)
                    d = f.read(32)
                    if len(d) < 20:
                        return None
                    if d[0] == 1:
                        ts = int.from_bytes(d[20:24], "big")
                        du = int.from_bytes(d[24:32], "big")
                    else:
                        ts = int.from_bytes(d[12:16], "big")
                        du = int.from_bytes(d[16:20], "big")
                    if ts:
                        return max(1, int(round(float(du) / ts)))
                    return None
    except Exception:                                            # noqa: BLE001
        return None
    return None


def resolve_seconds(a):
    """--seconds 优先；没给就读文件头；都读不到用 60 秒。"""
    if getattr(a, "seconds", None):
        return max(1, int(a.seconds)), "--seconds"
    p = getattr(a, "file", None)
    if p and os.path.isfile(p):
        s = probe_seconds(p)
        if s:
            return s, "文件头"
    return DEFAULT_SECONDS, "默认"


def gate(a, cost, basis):
    """两道闸门：预算不够 → 5（一个请求都不发）；没 --yes → 4。"""
    if cost > a.budget:
        raise Fail("budget", "这条流水线预计 %s 点（%s 元），超过 --budget %s 点。"
                             "一个请求都没发。调大 --budget（单位：点，1 元 = 100 点）再试。"
                   % (fmt_pts(cost), money(cost), fmt_pts(a.budget)), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实跑完整条流水线，预计 %s 点（%s 元）。%s\n"
                              "确认请加 --yes；只想看请求就加 --dry-run。"
                   % (fmt_pts(cost), money(cost), basis), EXIT_CONFIRM)
    return cost


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for t in TIER_ORDER:
        m = TIERS[t]
        rows.append({"tier": t, "name": m["name"], "points": m["points"],
                     "unit": "点/秒", "path": route_path(t), "route": m["route"],
                     "action": m["action"], "desc": m["desc"]})
    presets = [{"preset": p, "name": PRESETS[p]["name"], "steps": PRESETS[p]["steps"],
                "pointsPerSecond": sum(TIERS[s]["points"] for s in PRESETS[p]["steps"]),
                "note": PRESETS[p]["note"]} for p in PRESET_ORDER]
    out = {"ok": True, "count": len(rows), "tiers": rows, "presets": presets,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("老片转高清一条龙 —— 7 档工序（按单价从低到高，1 元 = 100 点）")
    print()
    print("  %-11s %-16s %-8s %-31s %s" % ("工序", "名字", "单价", "实际路径", "一句话"))
    print("  " + "-" * 104)
    for r in rows:
        print("  %-11s %-16s %-8s %-31s %s" % (
            r["tier"], r["name"], "%d 点/秒" % r["points"], r["path"], r["desc"]))
    print()
    print("  5 套预设（每套就是一条串好的流水线）：")
    print()
    print("  %-10s %-12s %-9s %s" % ("--preset", "名字", "合计", "串了哪几步"))
    print("  " + "-" * 76)
    for p in presets:
        print("  %-10s %-12s %-9s %s" % (
            p["preset"], p["name"], "%d 点/秒" % p["pointsPerSecond"], " → ".join(p["steps"])))
    print()
    print("  路径规则：restore 只走扁平 /api/v1/video/restore；其余 6 档统一走")
    print("  /api/v1/video/viapi/<tier>。7 条都用空 body 探针验过，验完 0 条任务、0 点冻结。")
    print("  查询统一走 GET /api/v1/video/viapi/result/<taskId>（免费）。")
    return 0


def cmd_cost(a, key, host):
    seconds = max(1, int(a.seconds))
    rows = []
    for p in PRESET_ORDER:
        steps = PRESETS[p]["steps"]
        _r, total = chain_cost(steps, seconds)
        rows.append({"preset": p, "name": PRESETS[p]["name"], "steps": steps,
                     "pointsPerSecond": sum(TIERS[s]["points"] for s in steps),
                     "points": total, "yuan": yuan(total)})
    single = []
    for t in TIER_ORDER:
        single.append({"tier": t, "points": TIERS[t]["points"],
                       "points60": TIERS[t]["points"] * seconds})
    out = {"ok": True, "seconds": seconds, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "presets": rows, "tiers": single,
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-07 实测）",
                     "按秒计费，最小计 1 秒；先按 duration 冻结、完成后按实际时长结算",
                     "任务失败全额退回；链条里任意一步失败，前面已完成的步仍然计费",
                     "restore 的 note 写「固定 36 点/秒（4K超清的 2 倍）」，36 点/秒就是 4K 超清档的两倍价"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点，按 %d 秒算）" % seconds)
    print()
    print("  %-10s %-12s %-9s %12s %10s  %s" % (
        "--preset", "名字", "合计", "本条流水线", "折人民币", "串了哪几步"))
    print("  " + "-" * 96)
    for r in rows:
        print("  %-10s %-12s %-9s %12s %9.2f 元  %s" % (
            r["preset"], r["name"], "%d 点/秒" % r["pointsPerSecond"],
            fmt_pts(r["points"]), r["yuan"], " → ".join(r["steps"])))
    print()
    print("  单步价（同样按 %d 秒算）：" % seconds)
    for s in single:
        print("    %-11s %2d 点/秒 × %d 秒 = %s 点" % (
            s["tier"], s["points"], seconds, fmt_pts(s["points60"])))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


def cmd_plan(a, key, host):
    steps = resolve_steps(a)
    seconds, src = resolve_seconds(a)
    rows, total = chain_cost(steps, seconds)
    preset = getattr(a, "preset", None) or DEFAULT_PRESET
    out = {"ok": True, "preset": preset, "steps": rows, "seconds": seconds,
           "secondsSource": src, "totalPoints": total, "yuan": yuan(total),
           "upload": {"method": "POST", "path": UPLOAD_PATH, "free": True},
           "basis": basis_text(steps, seconds)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("流水线计划：%s（%s）" % (PRESETS.get(preset, {}).get("name", "自定义"), preset))
    print("  时长来源：%s（%d 秒）" % (src, seconds))
    print()
    print("  %-4s %-11s %-16s %10s %-31s %s" % ("步", "工序", "名字", "本步点数", "端点", "产物"))
    print("  " + "-" * 96)
    for r in rows:
        print("  %-4s %-11s %-16s %10s %-31s %s" % (
            "第%d步" % r["i"], r["tier"], r["name"], fmt_pts(r["points"]),
            "POST " + r["path"], "%02d-%s.mp4" % (r["i"], r["tier"])))
    print()
    print("  合计：%s 点 = %s 元（1 元 = 100 点）" % (fmt_pts(total), money(total)))
    print("  %s" % basis_text(steps, seconds))
    print()
    print("  每一步实际发出的请求：")
    print("    POST %s%s   （multipart，免费；产物不在白名单时才用）" % (host, UPLOAD_PATH))
    for r in rows:
        print("    POST %s%s  {\"videoUrl\": \"<上一步产物>\", \"duration\": %d}"
              % (host, r["path"], seconds))
        print("    GET  %s%s  （轮询，免费）"
              % (host, query_hint(r["tier"])))
    print()
    print("  加 --yes 才真跑；先看一遍不花钱的请求：run --file 老片.mp4 --dry-run")
    return 0


TIER_PROBE_EXPECT = {"restore": "pixverse_empty_url"}


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    avail = d.get("available_points")
    checks.append(("Key + 余额接口可达", st == 200 and avail is not None,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(avail or 0), fmt_pts(d.get("frozen") or 0))))

    # 价目表：本地写死的 7 个单价 vs /api/v1/pricing 现查
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
    checks.append(("7 档单价与 /api/v1/pricing 一致", st_p == 200 and not drift,
                   "HTTP %s · %s" % (st_p, "全一致" if not drift
                                     else " / ".join(drift)[:120])))

    # 端点探针：空 body → 400 参数校验，停在扣费之前
    for t in TIER_ORDER:
        path = route_path(t)
        want = TIER_PROBE_EXPECT.get(t, "empty_url")
        say("  探 %-11s %s …" % (t, path))
        st2, txt2 = http_json("POST", host + path, key, {}, timeout=a.timeout)
        d2 = jloads(txt2) or {}
        e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
        code = e2.get("code") or ""
        ok2 = st2 == 400 and code == want
        checks.append(("端点 %-11s 可用（400 %s 即正确）" % (t, want), ok2,
                       "HTTP %s %s" % (st2, code or err_text(st2, txt2)[:40])))

    # 查询路由：假 taskId → 结构化 not_found，说明路由在、且免费
    for label, path in (
            ("viapi 查询路由", query_path("superres", "probe-no-such-task")),
            ("restore 查询路由", query_path("restore", "probe-no-such-task"))):
        st3, txt3 = http_json("GET", host + path, key, timeout=40)
        d3 = jloads(txt3) or {}
        code3 = ((d3.get("error") or {}) if isinstance(d3.get("error"), dict) else {}).get("code") or ""
        checks.append((label + "可达（404 not_found 即正确）",
                       st3 == 404 and code3 == "not_found",
                       "HTTP %s %s" % (st3, code3 or err_text(st3, txt3)[:40])))

    # 上传接口：不带 file → code 0 提示，不落文件、不扣费
    st5, txt5 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
    d5 = jloads(txt5) or {}
    checks.append(("上传接口 POST /upload 可用", st5 == 200 and d5.get("code") == 0,
                   "HTTP %s %s" % (st5, str(d5.get("msg") or "")[:40])))

    out = {"ok": all(c[1] for c in checks), "host": host, "tierCount": len(TIERS),
           "presetCount": len(PRESETS),
           "pricingSource": host + API_PREFIX + "/pricing",
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print()
    print("自检（不扣费：只读接口 + 空 body 触发参数校验，任务 0 条、冻结 0 点）")
    print()
    for n, o, dt in checks:
        print("  %s %-44s %s" % ("√" if o else "×", n, dt))
    print()
    print("  端点：7 档，restore 走扁平，其余 6 档走 /api/v1/video/viapi/<tier>")
    print("  配套：upload 拿白名单地址 · GET /video/viapi/result/{id} 查进度 · /pricing 对价")
    print("  单价：最便宜 9 点/秒，最贵 36 点/秒（1 元 = 100 点）")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 上传 ─────────────────────────
def do_upload(a, key, host, path):
    size = os.path.getsize(path)
    say("  上传 %s（%s 字节）…" % (os.path.basename(path), fmt_pts(size)))
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [("file", path)],
                             timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    ok_url, kind = url_allowed(got)
    say("  已上传 · 归属 %s · 白名单 %s" % (kind, "通过" if ok_url else "未通过"))
    return got, data


def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要上传的视频路径）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不扣费）")
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  文件：%s（%s 字节）" % (path, fmt_pts(size)))
        return 0
    t0 = time.time()
    got, data = do_upload(a, key, host, path)
    dt = time.time() - t0
    ok_url, kind = url_allowed(got)
    out = {"ok": True, "url": got, "path": data.get("path"), "name": data.get("name"),
           "size": data.get("size"), "mime": data.get("mime_type"),
           "hostKind": kind, "urlAllowed": ok_url, "elapsed": round(dt, 1)}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "upload",
                "file": path, "size": size, "url": got})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1f 秒，免费）" % dt)
    print("  地址：%s" % got)
    print("  类型：%s · %s · %s 字节" % (data.get("type"), data.get("mime_type"),
                                        fmt_pts(data.get("size") or size)))
    print("  归属：%s（上游白名单内，可直接给 run 当 --video-url）" % kind)
    print()
    print("  下一步：python3 scripts/run.py run --video-url \"%s\" --preset standard --yes" % got)
    return 0


# ───────────────────────── 任务状态 ─────────────────────────
def _find_url(node, depth=0):
    """在任意结构里找成片地址，优先常见字段名。"""
    if depth > 6:
        return None
    if isinstance(node, dict):
        for k in ("videoUrl", "video_url", "artifactUrl", "artifact_url",
                  "outputUrl", "output_url", "resultUrl", "url"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in node.values():
            got = _find_url(v, depth + 1)
            if got:
                return got
    elif isinstance(node, list):
        for v in node:
            got = _find_url(v, depth + 1)
            if got:
                return got
    return None


def fetch_task(a, key, host, tier, task_id):
    st, txt = http_json("GET", host + query_path(tier, task_id), key, timeout=60)
    d = jloads(txt) or {}
    if st == 404:
        e = d.get("error") if isinstance(d.get("error"), dict) else {}
        if e.get("code") == "not_found":
            raise Fail("call", "任务 %s 查不到（查询路由说 not_found）。确认 taskId 没抄错。"
                       % task_id, EXIT_CALL)
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if isinstance(d.get("data"), dict) and d.get("code") in (1, 200):
        d = d["data"]
    return d


def poll(a, key, host, tier, task_id):
    """轮询到终态。查询路由免费，轮一次不花一次的钱。"""
    deadline = time.time() + max(30, a.wait)
    last = None
    while True:
        d = fetch_task(a, key, host, tier, task_id)
        st = str(d.get("status") or "").lower()
        if st != last:
            say("  第 %s 步状态：%s" % (tier, st or "?"))
            last = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            d["_terminal"] = st
            return d
        if time.time() >= deadline:
            raise Fail("call",
                       "等了 %d 秒还没完成。任务没丢——用 `resume --workdir %s` 接着等，"
                       "**不要重新提交**（会再付一次）。" % (a.wait, a.workdir), EXIT_CALL)
        time.sleep(max(1, a.every))


def download(url, dest, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as x:
        ctype = (x.headers.get("Content-Type") or "").lower()
        raw = x.read()
    if ctype.startswith("text/html"):
        raise Fail("call", "下载回来的是一张网页，不是视频：%s" % url[:120], EXIT_CALL)
    d = os.path.dirname(os.path.abspath(dest))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with io.open(dest, "wb") as fh:
        fh.write(raw)
    return len(raw)


# ───────────────────────── 状态文件 ─────────────────────────
def state_path(workdir):
    return os.path.join(workdir, "state.json")


def save_state(workdir, state):
    state["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if not os.path.isdir(workdir):
        os.makedirs(workdir, exist_ok=True)
    io.open(state_path(workdir), "w", encoding="utf-8", newline="\n").write(
        json.dumps(state, ensure_ascii=False, indent=1))
    return state


def load_state(workdir):
    p = state_path(workdir)
    if not os.path.isfile(p):
        raise Fail("usage", "没有找到 %s。先起一条：`run --file 老片.mp4 --preset standard --yes`"
                   % p, EXIT_USAGE)
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        raise Fail("usage", "状态文件读不了（%s）：%s" % (p, e), EXIT_USAGE)


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


# ───────────────────────── 流水线引擎 ─────────────────────────
def _pick_url(tier, entry, a, key, host):
    """每一步的产物：落盘已有 → 成片链接在白名单内就直接用，否则重新上传。"""
    url = entry.get("resultUrl")
    local = entry.get("file")
    if url and not a.reupload:
        ok, kind = url_allowed(url)
        if ok:
            say("  上一步成片在白名单内（%s），直接喂给 %s" % (kind, tier))
            return url
    if not local or not os.path.isfile(local):
        raise Fail("call", "第 %d 步缺产物文件，接不上下一步：%s"
                   % (entry["i"], local or "（无）"), EXIT_CALL)
    got, _data = do_upload(a, key, host, local)
    return got


def _run_chain(a, key, host, state, start_url):
    steps = state["steps"]
    cur = start_url
    for entry in steps:
        tier = entry["tier"]
        if entry.get("status") == "completed":
            cur = entry.get("feedUrl") or entry.get("resultUrl") or cur
            continue

        task_id = entry.get("taskId")
        if not task_id:
            say("第 %d/%d 步：%s（%s，%d 点/秒）提交…" % (
                entry["i"], len(steps), tier, TIERS[tier]["name"], TIERS[tier]["points"]))
            body = {"videoUrl": cur, "duration": int(state["seconds"])}
            st, txt = http_json("POST", host + route_path(tier), key, body,
                                timeout=a.timeout)
            d = jloads(txt) or {}
            if st not in (200, 201):
                msg = err_text(st, txt)
                entry["status"] = "failed"
                entry["error"] = msg
                save_state(a.workdir, state)
                raise Fail("call", "第 %d 步提交失败（HTTP %s）：%s" % (entry["i"], st, msg),
                           EXIT_CALL)
            if isinstance(d.get("data"), dict) and d.get("code") in (1, 200):
                d = d["data"]
            task_id = d.get("taskId") or d.get("task_id") or d.get("id")
            if not task_id:
                entry["status"] = "failed"
                entry["error"] = err_text(st, txt)
                save_state(a.workdir, state)
                raise Fail("call", "第 %d 步没拿到 taskId：%s"
                           % (entry["i"], txt.replace("\n", " ")[:300]), EXIT_CALL)
            entry.update({"taskId": task_id, "status": "submitted",
                          "endpoint": route_path(tier),
                          "submittedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "frozen": d.get("cost")})
            save_state(a.workdir, state)
            say("  taskId=%s（预冻结 %s 点）" % (task_id, d.get("cost", "-")))
            if a.no_wait:
                out = {"ok": True, "preset": state["preset"], "submitted": True,
                       "step": entry, "workdir": a.workdir,
                       "next": "python3 scripts/run.py resume --workdir %s" % a.workdir}
                if a.json:
                    print(json.dumps(out, ensure_ascii=False))
                else:
                    print("已提交第 %d 步，不等待。" % entry["i"])
                    print("  taskId：%s" % task_id)
                    print("  接着跑：python3 scripts/run.py resume --workdir %s" % a.workdir)
                return 0
        else:
            say("第 %d/%d 步：%s 已有任务 %s，先查不重提…" % (
                entry["i"], len(steps), tier, task_id))

        t = poll(a, key, host, tier, task_id)
        st = t["_terminal"]
        entry["points"] = t.get("cost") or (TIERS[tier]["points"] * int(state["seconds"]))
        entry["finalStatus"] = st
        if st in TERMINAL_BAD:
            entry["status"] = "failed"
            entry["error"] = str(t.get("error") or t.get("message") or st)
            entry["refund"] = t.get("refund")
            save_state(a.workdir, state)
            raise Fail("call",
                       "第 %d 步（%s）报 %s：%s\n"
                       "任务没丢，taskId 还在 state.json 里。先把 `resume --workdir %s` 再跑一次"
                       "（只查不重提，免费）—— 平台会自动重试，重提等于再付一次。"
                       % (entry["i"], tier, st, entry["error"], a.workdir), EXIT_CALL)

        url = _find_url(t)
        entry["resultUrl"] = url
        dest = os.path.join(a.workdir, "%02d-%s.mp4" % (entry["i"], tier))
        if url and not a.no_download:
            try:
                size = download(url, dest)
                entry["file"] = dest
                entry["bytes"] = size
                say("  产物已落盘：%s（%s 字节）" % (dest, fmt_pts(size)))
            except Fail as e:
                say("  下载失败（%s），这一步的链接仍然可用" % e.message)
                entry["file"] = None
        entry["status"] = "completed"
        entry["completedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_state(a.workdir, state)
        if url:
            ok, kind = url_allowed(url)
            cur = url if ok else _pick_url(tier, entry, a, key, host)
            entry["feedUrl"] = cur
            save_state(a.workdir, state)

    spent = sum(int(e.get("points") or 0) for e in steps)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "chain",
                "preset": state["preset"], "input": state.get("input"),
                "steps": [e["tier"] for e in steps], "points": spent,
                "workdir": a.workdir})
    last = steps[-1]
    out = {"ok": True, "preset": state["preset"], "seconds": state["seconds"],
           "steps": steps, "spentPoints": spent, "yuan": yuan(spent),
           "output": last.get("file"), "resultUrl": last.get("resultUrl"),
           "workdir": a.workdir}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print()
    print("一条龙跑完：%d 步 · 实扣 %s 点（%s 元）" % (len(steps), fmt_pts(spent), money(spent)))
    for e in steps:
        print("  第%d步 %-11s %-10s %s" % (
            e["i"], e["tier"], e.get("finalStatus") or "-",
            ("%s 点" % fmt_pts(e.get("points") or 0))))
    print()
    if last.get("file"):
        print("  成片：%s（%s 字节）" % (last["file"], fmt_pts(last.get("bytes") or 0)))
    if last.get("resultUrl"):
        print("  链接：%s（约 30 分钟有效，及时转存）" % last["resultUrl"])
    print("  台账：python3 scripts/run.py log")
    return 0


def cmd_run(a, key, host):
    steps = resolve_steps(a)
    seconds, src = resolve_seconds(a)
    _rows, cost = chain_cost(steps, seconds)
    basis = "%s（时长来源：%s）" % (basis_text(steps, seconds), src)

    path = a.file
    if not a.video_url and not path:
        raise Fail("usage", "必须给 --file（本地片子）或 --video-url（已托管的地址）", EXIT_USAGE)
    if path and not a.video_url and not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    if a.video_url:
        ok, kind = url_allowed(a.video_url)
        if not ok and not a.allow_any_url:
            raise Fail("usage",
                       "上游只收本站托管的地址（%s 不在白名单）。三条可用路子：\n"
                       "  · 先传再跑（推荐，免费）：python3 scripts/run.py upload --file 老片.mp4\n"
                       "  · 本站成片地址：https://vr.a7w.cn/result/xxx.mp4\n"
                       "  · 本站七牛：https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4" % kind,
                       EXIT_USAGE)

    gate(a, cost, basis)                      # 5 → 一个请求都不发；4 → 缺 --yes

    preset = a.preset or "custom"
    state = {"version": 1, "preset": preset, "seconds": seconds,
             "input": path, "videoUrl": a.video_url,
             "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "estimatedPoints": cost, "steps": [
                 {"i": i, "tier": t, "status": "pending",
                  "pointsPerSecond": TIERS[t]["points"],
                  "points": TIERS[t]["points"] * seconds,
                  "endpoint": route_path(t)}
                 for i, t in enumerate(steps, 1)]}

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "preset": preset, "seconds": seconds,
               "steps": state["steps"], "estimatedPoints": cost, "yuan": yuan(cost),
               "basis": basis, "upload": {"path": UPLOAD_PATH, "free": True},
               "requests": [
                   {"method": "POST", "path": UPLOAD_PATH, "note": "multipart，免费"},
               ] + [{"method": "POST", "path": s["endpoint"],
                     "body": {"videoUrl": "<上一步产物>", "duration": seconds}}
                    for s in state["steps"]]
               + [{"method": "GET", "path": query_hint(s["tier"]),
                   "note": "轮询，免费"} for s in state["steps"]]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不提交、不冻结、不扣费）")
        print("  流水线：%s（%s）· %d 秒 · 预计 %s 点（%s 元）" % (
            preset, " → ".join(steps), seconds, fmt_pts(cost), money(cost)))
        print()
        print("  将要发出的请求：")
        if not a.video_url:
            print("    POST %s%s   （multipart，免费）" % (host, UPLOAD_PATH))
        for s in state["steps"]:
            print("    POST %s%s  {\"videoUrl\": \"<上一步产物>\", \"duration\": %d}"
                  % (host, s["endpoint"], seconds))
            print("    GET  %s%s  （轮询，免费）" % (host, query_hint(s["tier"])))
        print()
        print("  去掉 --dry-run、加上 --yes 就真跑。")
        return 0

    os.makedirs(a.workdir, exist_ok=True)
    save_state(a.workdir, state)
    say("状态文件：%s" % state_path(a.workdir))

    if a.video_url:
        cur = a.video_url
    else:
        cur, _data = do_upload(a, key, host, path)
    return _run_chain(a, key, host, state, cur)


def cmd_resume(a, key, host):
    state = load_state(a.workdir)
    steps = state["steps"]
    pending = [e for e in steps if e.get("status") != "completed"]
    if not pending:
        last = steps[-1]
        out = {"ok": True, "alreadyDone": True, "preset": state["preset"],
               "output": last.get("file"), "resultUrl": last.get("resultUrl")}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("这条流水线已经跑完了，没有要补的步。")
        print("  成片：%s" % (last.get("file") or last.get("resultUrl") or "-"))
        print("  重跑一条新的：python3 scripts/run.py run --file 老片.mp4 --preset standard --yes")
        return 0
    remain = sum(int(e.get("points") or TIERS[e["tier"]]["points"] * state["seconds"])
                 for e in pending)
    gate(a, remain, "剩余 %d 步，共 %s 点" % (len(pending), fmt_pts(remain)))
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "preset": state["preset"],
               "remaining": pending, "remainingPoints": remain, "yuan": yuan(remain)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（只查不提交）：%d 步待补，预计 %s 点（%s 元）" % (
            len(pending), fmt_pts(remain), money(remain)))
        for e in pending:
            print("  第%d步 %-11s %s" % (e["i"], e["tier"],
                                         "已提交 " + str(e.get("taskId"))
                                         if e.get("taskId") else "还没提交"))
        return 0
    save_state(a.workdir, state)
    cur = state.get("videoUrl")
    for e in steps:
        if e.get("status") == "completed":
            cur = e.get("feedUrl") or e.get("resultUrl") or cur
        else:
            break
    if not cur:
        p = state.get("input")
        if not p or not os.path.isfile(p):
            raise Fail("usage", "状态里没有可用的起点地址，也没找到原片：%s" % (p or "（未记录）"),
                       EXIT_USAGE)
        cur, _data = do_upload(a, key, host, p)
    return _run_chain(a, key, host, state, cur)


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    tier = a.tier or "superres"
    d = fetch_task(a, key, host, tier, a.task_id)
    st = str(d.get("status") or "").lower()
    url = _find_url(d)
    cost = d.get("cost")
    out = {"ok": True, "taskId": a.task_id, "tier": tier, "query": query_path(tier, a.task_id),
           "status": st, "message": d.get("message"), "resultUrl": url,
           "cost": cost, "refund": d.get("refund"), "error": d.get("error")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s（按 %s 查）" % (a.task_id, tier))
    print("  查询：GET %s（免费）" % query_path(tier, a.task_id))
    print("  状态：%s" % (st or "?"))
    if cost is not None:
        print("  实扣：%s 点" % cost)
    if d.get("refund") is not None:
        print("  退回：%s 点" % d.get("refund"))
    if d.get("message"):
        print("  说明：%s" % str(d.get("message"))[:300])
    if url:
        print("  成片：%s" % url)
    if d.get("error"):
        print("  错误：%s" % json.dumps(d.get("error"), ensure_ascii=False)[:300])
    if st in TERMINAL_BAD:
        print()
        print("  这条报了 %s。平台会自动重试，过几分钟再查一次这条命令（免费）；"
              "重提等于再付一次。" % st)
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
        if e.get("mode") == "upload":
            print("  %s  %-6s upload  %-40s %s" % (
                e.get("at"), "ok" if e.get("ok") else "fail",
                os.path.basename(e.get("file") or "-"), e.get("url") or ""))
        else:
            print("  %s  %-6s %-8s %-11s %s 点" % (
                e.get("at"), "ok" if e.get("ok") else "fail",
                e.get("preset") or "-", " → ".join(e.get("steps") or []),
                fmt_pts(e.get("points") or 0)))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 老片转高清一条龙（超分 / 校色 / 增强 / 修复 串成一条流水线）",
        epilog="端点：POST %s/api/v1/video/restore（修复）· "
               "POST %s/api/v1/video/viapi/<tier>（其余 6 档）· "
               "POST %s/api/v1/upload（先传后跑）· "
               "GET %s/api/v1/video/viapi/result/<taskId>（查询，免费）"
               % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="7 档工序 + 5 套预设 + 实际路径（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：5 套预设与 7 档单步（免费）", allow_abbrev=False)
    p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                   help="按多少秒算（默认 %d）" % DEFAULT_SECONDS)
    p.set_defaults(fn=cmd_cost)

    def add_chain(p):
        p.add_argument("--preset", choices=PRESET_ORDER, default=DEFAULT_PRESET,
                       help="预设流水线（默认 %s：超分 → 校色 → 增强）" % DEFAULT_PRESET)
        p.add_argument("--steps", help="自定义工序，逗号分隔，最多 4 步，"
                                       "例如 colorize,superres,enhance（给了就覆盖 --preset）")
        p.add_argument("--seconds", type=int, default=None,
                       help="片长秒数（默认读文件头，读不到按 %d 秒）" % DEFAULT_SECONDS)

    p = sub.add_parser("plan", help="打印流水线计划与每一步请求体（本地，免费）",
                       allow_abbrev=False)
    add_chain(p)
    p.add_argument("--file", help="本地片子（用来自动读时长）")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("doctor", help="自检 Key / 7 个端点 / 价目表 / 查询 / 上传（免费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="上传本地片子，拿一个能直接提交的地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    def add_run(p):
        add_chain(p)
        p.add_argument("--file", help="本地老片（和 --video-url 二选一）")
        p.add_argument("--video-url", help="已托管的视频地址（先用 upload 拿，或本站成片链接）")
        p.add_argument("--workdir", default=DEFAULT_WORKDIR,
                       help="产物与状态目录（默认 %s）" % DEFAULT_WORKDIR)
        p.add_argument("--allow-any-url", action="store_true",
                       help="跳过本地白名单预检，把地址直接交给上游判断")
        p.add_argument("--reupload", action="store_true",
                       help="每步成片都重新上传一次（成片链接快过期时用）")
        p.add_argument("--no-download", action="store_true",
                       help="只跑不落盘（产物链接直接往下一步喂）")
        p.add_argument("--no-wait", action="store_true",
                       help="只提交第一步，拿 taskId 就走")
        p.add_argument("--wait", type=int, default=1800, help="单步等待上限秒数（默认 1800）")
        p.add_argument("--every", type=int, default=10, help="轮询间隔秒数（默认 10）")
        p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数（默认 120）")
        p.add_argument("--yes", action="store_true", help="确认真跑并冻结点数")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("run", help="起一条流水线（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    add_run(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("resume", help="断点续跑（已完成的步不重跑、已提交的任务不重提）",
                       allow_abbrev=False)
    p.add_argument("--workdir", default=DEFAULT_WORKDIR, help="状态目录（默认 %s）"
                   % DEFAULT_WORKDIR)
    p.add_argument("--reupload", action="store_true", help="每步成片都重新上传一次")
    p.add_argument("--no-download", action="store_true", help="只跑不落盘")
    p.add_argument("--no-wait", action="store_true", help="只提交下一个待跑步，拿 taskId 就走")
    p.add_argument("--wait", type=int, default=1800, help="单步等待上限秒数（默认 1800）")
    p.add_argument("--every", type=int, default=10, help="轮询间隔秒数（默认 10）")
    p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数（默认 120）")
    p.add_argument("--yes", action="store_true", help="确认真跑并冻结点数")
    p.add_argument("--dry-run", action="store_true", help="只打印要补的步，不提交")
    p.set_defaults(fn=cmd_resume)

    p = sub.add_parser("status", help="查单个任务（免费，走 result 路由）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 taskId")
    p.add_argument("--tier", choices=TIER_ORDER, default="superres",
                   help="是哪一档（决定查哪条路由，默认 superres）")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            if _n in _sp._option_string_actions:
                continue
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_log")

DEFAULTS = (("budget", DEFAULT_BUDGET), ("max_tokens", 0), ("json", False))


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in DEFAULTS:
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
        say("已中断。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
