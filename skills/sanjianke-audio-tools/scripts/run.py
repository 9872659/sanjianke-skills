#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 音频工具台（sanjianke-audio-tools）

一条二创素材的完整链路，全部走 api.a7w.cn：

    本地音频 --upload（0 点）--> 平台地址 --upload_audio（39 点）--> audio_id
             --vox（42 点）--> 人声 / 伴奏两条轨
             --mashup_lyrics（36 点）--> 重新填过词的版本
    本地视频 --upload（0 点）--> 平台地址 --interp（25 点/秒）--> 60fps

## 三个接口的真实归属（2026-11-08 GET /api/v1/apps 现查，22 个应用 100 个接口）

`vox` / `mashup_lyrics` / `upload_audio` 属于 **music_generation**（13 个接口，
drive=suno_music），路径是 `/api/v1/apps/music_generation/<code>`。
`media_services_33` 是另一个应用（29 个接口，drive=official），装的是 ElevenLabs
配音与音乐生成那一批，里面没有这三个 code。

    music_generation  mashup_lyrics  call_type=1（同步）
    music_generation  vox           call_type=2（异步，回 task_id）
    music_generation  upload_audio  call_type=1（同步，回 audio_id）

## 价目表怎么说（GET /api/v1/pricing 实测，115 条规则）

    /api/v1/apps/music_generation/*
        {"mode":"flat","cost":0,"markupPercent":200,
         "note":"…统一按上游**真实**点数计价，对外 = 上游实际点数 × 3；query/余额等 0 点…"}
    /api/v1/video/viapi/interp
        {"mode":"per_second","perSecond":25,"note":"视频插帧 60fps"}
    /api/v1/upload
        {"mode":"flat","cost":0,"note":"…上传不计费…"}
    *（通配）{"mode":"flat","cost":0,"markupPercent":100,"minPoints":50}

所以：music_generation 三件套没有价目表单价，只有「上游 × 3」这一条口径；
平台官方 schema 写的 14 / 12 / 13 点就是上游价，本包按 42 / 36 / 39 点估，
真实成交价只在返回体 `data.usage.points_cost` 里。**本包不编单价**：
本账号没有 `create` 的稳定价时就显示「待实测」，不填一个好看的数字。

## 本账号实测（2026-11-08，/api/v1/me/tasks 1398 条全量扫描）

    /api/v1/apps/music_generation/create   8 条   84.50 - 325.00 点
    /api/v1/video/viapi/interp             0 条   （还没跑过）
    /api/v1/apps/music_generation/vox      0 条   （还没跑过）

## 探针纪律（这轮 0 点，钱包一次没动）

    ✅ POST /api/v1/video/viapi/interp {}            → 400 empty_url
    ✅ POST /api/v1/video/viapi/interp {"videoUrl":"https://example.invalid/a.mp4"}
                                                    → 400 url_not_allowed
    ✅ POST /api/v1/upload 不带 file                 → 200 code 0（免费）
    ✅ GET  /api/v1/pricing /apps /models /me/tasks /tasks/<id> /user/balance
    ✅ GET  /user/balance/logs（limit=N）             ← 流水，用来证明花了多少
    ⛔ GET  /api/v1/apps/<app>                        ← 命中通配计价，sync: 即时扣、不退
    ⚠️ POST /api/v1/apps/music_generation/<code> 缺参 ← 先 reserve_sync 冻 60 点再退
       → 所以本包 **doctor 一次都不 POST 这三个接口**，只用 /apps + /pricing 证明它们在架。

## 子命令

  catalog  8 条路线：单价 / 调用形态 / 路径（免费，不用 Key）
  cost     先算钱：单次价 + 60 秒链路总价（免费，不用 Key）
  doctor   自检 Key / 价目表 / 三个接口在架 / interp 探针 / 流水（免费，0 点）
  upload   本地文件 → 平台地址（免费）
  audio-id 平台地址 → audio_id（39 点起，要 --yes）
  split    audio_id → 人声 / 伴奏（42 点起，要 --yes）
  mashup   两段歌词 → 一段新的（36 点起，要 --yes）
  interp   视频补到 60fps（25 点/秒，要 --yes）
  chain    一条二创素材跑完全链路（--dry-run 先看总价）
  models   同一需求多模型横评（--need relabel|split|interp）
  status   查任务（免费，只打 GET /tasks/<id>）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --seconds 60
  python3 scripts/run.py doctor
  python3 scripts/run.py upload --file hook.mp3
  python3 scripts/run.py audio-id --audio-url "https://oss.gpu.likeadmin.cn/openapi/..."
  python3 scripts/run.py split --audio-id audio_xxx --start 0 --end 30 --yes
  python3 scripts/run.py mashup --a-file a.txt --b-file b.txt --yes
  python3 scripts/run.py interp --video-url "https://..." --seconds 30 --yes
  python3 scripts/run.py chain --file hook.mp3 --seconds 30 --dry-run

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
import unicodedata
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
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 6000                      # 单位：点 = 60 元
APP_AUDIO = "music_generation"
MARKUP = 3                                 # pricing: markupPercent 200 -> 上游 × 3
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "audio-tools-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-audio-tools/%s" % VERSION

# ── GBK 兜底：编不出的字符换成 '-'，不留下半角问号。────────────────────────
# Windows 上 stdout 被管道/重定向时 Python 用 cp936 输出；半角日元符号这类字符
# 会变成问号，GBK 严格解码后就是脏字符。emit() 统一走 safe()，问号数恒为 0。
_GBK_CACHE = {}


def _gbk_ok(ch):
    v = _GBK_CACHE.get(ch)
    if v is None:
        try:
            ch.encode("gbk")
            v = True
        except Exception:                                        # noqa: BLE001
            v = False
        _GBK_CACHE[ch] = v
    return v


def safe(s):
    s = str(s)
    try:
        s.encode("gbk")
        return s
    except Exception:                                            # noqa: BLE001
        return "".join(c if _gbk_ok(c) else "-" for c in s)


def emit(line=""):
    sys.stdout.write(safe(line) + "\n")


def jout(obj):
    emit(json.dumps(obj, ensure_ascii=False))


def say(msg):
    sys.stderr.write(safe(msg) + "\n")


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def pnum(v, dash="-"):
    if v is None:
        return dash
    try:
        f = float(v)
    except Exception:                                            # noqa: BLE001
        return dash
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def yuan(points):
    try:
        return "%.2f" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                            # noqa: BLE001
        return "-"


# ── 路线表 ─────────────────────────────────────────────────────────────────
# upstream = 平台官方 schema 里写的「按次固定价」（= 上游价），乘 3 才是对外价。
# live_path = 在 /api/v1/me/tasks 里按 path 归集 actualPrice 用的键。
# status: ok=能在价目表/文档里直接定；watch=路由在架但线上档位说明写过「已下线」；
#         free=不扣费；local=不联网。
ROUTES = {
    "vox": dict(
        name="人声分离 Vox", code="vox", app=APP_AUDIO, kind="audio",
        mode="per_call", upstream=14, async_=True, status="ok",
        path=API_PREFIX + "/apps/music_generation/vox",
        desc="把一首歌拆成人声 / 伴奏两条轨，可只取副歌那一段"),
    "mashup_lyrics": dict(
        name="混搭歌词", code="mashup_lyrics", app=APP_AUDIO, kind="audio",
        mode="per_call", upstream=12, async_=False, status="ok",
        path=API_PREFIX + "/apps/music_generation/mashup_lyrics",
        desc="两段歌词融成一段新的，自带 [singer A] / [transition] 分段"),
    "upload_audio": dict(
        name="音频换 audio_id", code="upload_audio", app=APP_AUDIO, kind="audio",
        mode="per_call", upstream=13, async_=False, status="ok",
        path=API_PREFIX + "/apps/music_generation/upload_audio",
        desc="把公网音频地址换成 audio_id，后续接口都吃这个 ID"),
    "create_stems": dict(
        name="整曲分离（create stems）", code="create", app=APP_AUDIO, kind="audio",
        mode="per_call", upstream=None, async_=True, status="ok",
        form={"type": "stems"},
        live_path=API_PREFIX + "/apps/music_generation/create",
        path=API_PREFIX + "/apps/music_generation/create",
        desc="一次拿到人声 / 伴奏两条轨；价随 type 变，只认实测"),
    "create_all_stems": dict(
        name="四轨分离（create all_stems）", code="create", app=APP_AUDIO, kind="audio",
        mode="per_call", upstream=None, async_=True, status="ok",
        form={"type": "all_stems"},
        live_path=API_PREFIX + "/apps/music_generation/create",
        path=API_PREFIX + "/apps/music_generation/create",
        desc="人声 + 鼓 + 贝斯 + 其他，配乐重编用"),
    "interp": dict(
        name="视频插帧 60fps", code="interp", app=None, kind="video",
        mode="per_second", points=25, status="watch",
        path=API_PREFIX + "/video/viapi/interp",
        desc="25 点/秒补到 60fps；空 body 与坏 URL 两种探针都停在参数校验"),
    "upload": dict(
        name="上传本地文件", code=None, app=None, kind="file",
        mode="free", points=0, status="free",
        path=API_PREFIX + "/upload",
        desc="multipart 字段名 file，最长 24 小时，免费"),
    "local": dict(
        name="本机 ffmpeg 补帧", code=None, app=None, kind="local",
        mode="free", points=0, status="local",
        path="-",
        desc="minterpolate 补帧，0 点，慢；给出命令自己跑"),
}
ROUTE_ORDER = ["upload_audio", "vox", "mashup_lyrics", "create_stems",
               "create_all_stems", "interp", "upload", "local"]

STATUS_CN = {"ok": "可用", "watch": "待验证", "free": "免费", "local": "本机"}
STATUS_MARK = {"ok": "√", "watch": "≈", "free": "√", "local": "√"}

DEFAULT_DURATION = 5      # 视频线 duration 缺省 5 秒（预冻结用）


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


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


def http_json(method, url, key, body=None, timeout=120):
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=hdr)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except urllib.error.URLError as e:
            last = "连不上 %s：%s" % (url, e.reason)
        except Exception as e:                                   # noqa: BLE001
            last = "请求异常：%s: %s" % (type(e).__name__, e)
        if attempt < 2:
            time.sleep(0.5 if attempt == 0 else 1.2)
    raise Fail("call", last or "请求失败", EXIT_CALL)


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
        for k in ("message", "msg", "failReason", "error"):
            v = d.get(k)
            if isinstance(v, dict):
                v = v.get("message") or v.get("code")
            if v:
                return str(v)[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该 JSON 端点" % st
    return (txt or "").replace("\n", " ")[:240]


def url_allowed(u):
    """视频线只收本站托管的地址（实测报错原文）。返回 (ok, 说明)。"""
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


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


# ── 报价 ───────────────────────────────────────────────────────────────────
def quote(route, seconds=0, live_path=None):
    """返回 dict(points, low, high, source, basis, unit)。

    points=None 表示「本账号还没有可用的价格」——不填数字，显示待实测。
    """
    r = ROUTES[route]
    if r["mode"] == "free":
        return dict(points=0.0, low=0.0, high=0.0, source="free", unit="点/次",
                    basis="不计费")
    if r["mode"] == "per_second":
        secs = max(1, int(seconds or 1))
        pts = float(r["points"]) * secs
        return dict(points=pts, low=pts, high=pts, source="pricing", unit="点/秒",
                    basis="%d 点/秒 x %d 秒" % (r["points"], secs))
    lp = r.get("live_path")
    hit = (live_path or {}).get(lp) if lp else None
    if hit:
        return dict(points=hit["low"], low=hit["low"], high=hit["high"],
                    source="live", unit="点/次",
                    basis="本账号实测 %s - %s 点（%d 条）"
                          % (pnum(hit["low"]), pnum(hit["high"]), hit["n"]))
    if r.get("upstream"):
        pts = float(r["upstream"]) * MARKUP
        return dict(points=pts, low=pts, high=pts, source="pricing×doc", unit="点/次",
                    basis="上游 %d 点 x 3（pricing 的 markupPercent=200）"
                          % r["upstream"])
    return dict(points=None, low=None, high=None, source="unknown", unit="点/次",
                basis="价随 type 变，本账号还没有这一路的流水，不做估算")


def gate_points(q):
    """预算闸门用上界：有实测区间就按最高价卡。"""
    return q["high"] if q.get("high") is not None else q.get("points")


def _gate(a, cost, requests=1, what="本次"):
    """两道闸门：预算先拦，再要 --yes。超预算时一个请求都不发。"""
    if requests > 0 and a.budget <= 0:
        raise Fail("budget",
                   "--budget 是 %d 点（单位：点）。0 点预算等于不授权任何调用；"
                   "给 1 点以上就放行。" % a.budget, EXIT_BUDGET)
    if cost and cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点超过 --budget %d 点（%s），一个请求都没发。"
                   "调大 --budget 或减小时长。" % (cost, a.budget, what), EXIT_BUDGET)
    if cost and not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实提交，预计 / 冻结 %d 点（%s 元，%s）。确认请加 --yes。"
                   % (cost, yuan(cost), what), EXIT_CONFIRM)


def _plan(a, reqs, lines, total=0):
    out = {"ok": True, "dryRun": True, "requests": lines, "requestCount": reqs,
           "estimatedPoints": round(total, 2), "yuan": round(total / POINTS_PER_YUAN, 2)}
    if a.json:
        jout(out)
        return 0
    emit("干跑（一个请求都不发）")
    emit("  请求数：%d" % reqs)
    emit("  预估：%s 点（%s 元）" % (pnum(total), yuan(total)))
    for ln in lines:
        emit("  -> %s" % ln)
    return 0


# ── 免费子命令 ─────────────────────────────────────────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for rid in ROUTE_ORDER:
        r = ROUTES[rid]
        q = quote(rid, a.seconds, None)
        # 按秒档的 catalog 只显示单价，不显示「× 秒」后的总价
        pts = float(r["points"]) if r["mode"] == "per_second" else q["points"]
        rows.append(dict(route=rid, name=r["name"], path=r["path"],
                         unit=q["unit"], points=pts, source=q["source"],
                         status=r["status"], statusCn=STATUS_CN[r["status"]],
                         form=r.get("form"), desc=r["desc"]))
    out = {"ok": True, "count": len(rows), "routes": rows,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "pricingSource": "GET /api/v1/pricing（2026-11-08 实测，115 条规则）",
           "roundPoints": 0}
    if a.json:
        jout(out)
        return 0
    emit("三剪客 · 音频工具台 —— 8 条路线（按链路顺序排）")
    emit()
    emit("  %s %s %s %s %s" % (pad("--route", 17), pad("能力", 26),
                                pad("调用形态", 13), pad("单价", 14), "状态"))
    emit("  " + "-" * 104)
    for x in rows:
        how = ("按次异步" if (x["unit"] == "点/次" and ROUTES[x["route"]].get("async_"))
               else "按次同步" if x["unit"] == "点/次" else
               "按秒" if x["unit"] == "点/秒" else "免费")
        price = ("%s %s" % (pnum(x["points"]), x["unit"])) if x["points"] is not None \
            else "待实测"
        emit("  %s %s %s %s %s" % (pad(x["route"], 17), pad(x["name"], 26),
                                    pad(how, 13), pad(price, 14),
                                    "%s %s" % (STATUS_MARK[x["status"]], x["statusCn"])))
    emit()
    emit("  一条素材的链路")
    emit("    本地音频 -> upload（0 点）-> audio_id（39 点）-> vox（42 点）")
    emit("             -> 人声 / 伴奏两条轨 -> mashup_lyrics（36 点，可选）")
    emit("    本地视频 -> upload（0 点）-> interp（25 点/秒）-> 60fps")
    emit()
    emit("  口径")
    emit("    · music_generation 三件套没有专属单价，只有「上游实际点数 x 3」")
    emit("      平台 schema 的 14 / 12 / 13 点就是上游价，所以对外 42 / 36 / 39 点")
    emit("    · interp 是价目表里唯一直接写死的：25 点/秒（1 元 = 100 点）")
    emit("    · create 的价随 type 变，只认 /api/v1/me/tasks 的实测值，不估算")
    emit("    · 失败任务全额退回；按秒档先冻结、完成后按实际时长结算")
    return 0


def cmd_cost(a, key, host):
    detail = None
    if a.route:
        q = quote(a.route, a.seconds, None)
        detail = {"route": a.route, "name": ROUTES[a.route]["name"],
                  "seconds": a.seconds, "points": q["points"],
                  "yuan": round((q["points"] or 0) / float(POINTS_PER_YUAN), 2),
                  "basis": q["basis"], "source": q["source"]}
    rows = []
    for rid in ROUTE_ORDER:
        r = ROUTES[rid]
        q = quote(rid, a.seconds, None)
        row = {"route": rid, "name": r["name"], "unit": q["unit"],
               "points": q["points"], "source": q["source"], "basis": q["basis"]}
        if r["mode"] == "per_second":
            row["cols"] = [r["points"] * 1, r["points"] * 15, r["points"] * 30,
                           r["points"] * 60, r["points"] * 180]
        else:
            row["cols"] = [q["points"]] * 5
        rows.append(row)
    chain = 0.0
    chain_parts = []
    for rid, secs in (("upload", 0), ("upload_audio", 0), ("vox", 0),
                      ("mashup_lyrics", 0), ("interp", a.seconds)):
        q = quote(rid, secs, None)
        if q["points"] is not None:
            chain += q["points"]
            chain_parts.append("%s %s 点" % (rid, pnum(q["points"])))
    out = {"ok": True, "seconds": a.seconds, "detail": detail, "routes": rows,
           "chain": {"points": round(chain, 2), "yuan": round(chain / 100.0, 2),
                     "parts": chain_parts, "secondsVision": a.seconds},
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "notes": [
               "1 元 = 100 点；interp 单价取自 GET /api/v1/pricing 的 perSecond=25",
               "music_generation 三件套 = 上游实际点数 x 3（pricing 的 markupPercent=200）",
               "42 / 36 / 39 点是按平台 schema 的上游价 14 / 12 / 13 折算，不是编的",
               "create 两档不给数字：价随 type 变，只在 /api/v1/me/tasks 有实测时报价",
               "按次档一次请求就是一条任务；按秒档按输入视频秒数计，最小 1 秒",
           ]}
    if a.json:
        jout(out)
        return 0
    emit("预估成本（1 元 = 100 点；单位：点）")
    emit()
    if detail:
        emit("  --route %s（%s）" % (a.route, detail["name"]))
        emit("  %s" % detail["basis"])
        emit("  = %s 点 = %s 元" % (pnum(detail["points"]), yuan(detail["points"])))
        emit()
    emit("  %s %s %s %s %s %s %s" % (pad("--route", 17), pad("1 秒", 9, False),
                                      pad("15 秒", 10, False), pad("30 秒", 10, False),
                                      pad("60 秒", 10, False), pad("3 分钟", 10, False),
                                      "口径"))
    emit("  " + "-" * 96)
    for r in rows:
        cells = [pnum(v) if v is not None else "待实测" for v in r["cols"]]
        emit("  %s %s %s %s %s %s %s" % (
            pad(r["route"], 17), pad(cells[0], 9, False), pad(cells[1], 10, False),
            pad(cells[2], 10, False), pad(cells[3], 10, False),
            pad(cells[4], 10, False), r["basis"][:34]))
    emit()
    emit("  一条素材跑完整链路（%d 秒视频）：%s 点 = %s 元"
          % (a.seconds, pnum(chain), yuan(chain)))
    emit("    %s" % " + ".join(chain_parts))
    emit()
    for n in out["notes"]:
        emit("  · %s" % n)
    return 0


def cmd_doctor(a, key, host):
    # 10 个请求，全部只读 GET 或用空 body 停在参数校验
    reqs = 10
    _gate(a, 0, reqs, "自检")
    if a.dry_run:
        return _plan(a, reqs, [
            "GET /user/balance",
            "GET %s/pricing" % API_PREFIX,
            "GET %s/apps" % API_PREFIX,
            "GET %s/models" % API_PREFIX,
            "GET %s/me/tasks（limit=2000）" % API_PREFIX,
            "GET %s/tasks/probe-no-such-task" % API_PREFIX,
            "POST %s/video/viapi/interp {}" % API_PREFIX,
            "POST %s/video/viapi/interp 坏 URL" % API_PREFIX,
            "POST %s/upload 不带 file" % API_PREFIX,
            "GET /user/balance/logs（limit=20）",
        ])
    checks = []

    def chk(name, ok, detail):
        checks.append((name, bool(ok), detail))

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    chk("Key + 余额接口可达", st == 200,
        "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
            st, pnum(d.get("available_points") or d.get("points") or 0),
            pnum(d.get("frozen") or 0)))

    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
    pricing = {}
    if st_p == 200:
        pricing = (jloads(txt_p) or {}).get("pricing") or {}
    interp_rule = pricing.get(API_PREFIX + "/video/viapi/interp") or {}
    mg_rule = pricing.get(API_PREFIX + "/apps/music_generation/*") or {}
    ok_price = (interp_rule.get("perSecond") == 25
                and int(mg_rule.get("markupPercent") or 0) == 200)
    chk("价目表：interp 25 点/秒 + music_generation 上游 x3",
        st_p == 200 and ok_price,
        "HTTP %s · %d 条规则 · interp perSecond=%s · mg markup=%s%%" % (
            st_p, len(pricing), interp_rule.get("perSecond"),
            mg_rule.get("markupPercent")))

    st_a, txt_a = http_json("GET", host + API_PREFIX + "/apps", key, timeout=40)
    aps = (jloads(txt_a) or {}).get("data") or []
    mg = [x for x in aps if (x.get("code") or "") == APP_AUDIO]
    codes = set()
    for x in mg:
        for api in (x.get("apis") or []):
            codes.add(api.get("code"))
    want = ("vox", "mashup_lyrics", "upload_audio")
    hit = [c for c in want if c in codes]
    chk("三个接口在 music_generation 名下（%d / 3）" % len(hit),
        st_a == 200 and len(hit) == 3,
        "应用 %d 个 · music_generation 接口 %d 个 · 命中 %s" % (
            len(aps), len(codes), "、".join(hit) or "-"))

    st_m, txt_m = http_json("GET", host + API_PREFIX + "/models", key, timeout=60)
    ms = (jloads(txt_m) or {}).get("data") or []
    text_priced = [m for m in ms
                   if (m.get("type_code") or "").lower() == "text"
                   and isinstance(m.get("pricing"), dict)
                   and m["pricing"].get("per_1k_input") is not None]
    chk("文本模型单价可读（横评用）", st_m == 200 and len(text_priced) >= 20,
        "目录 %d 条 · 带 per_1k 单价的文本模型 %d 个" % (len(ms), len(text_priced)))

    st_t, txt_t = http_json("GET", host + API_PREFIX + "/me/tasks?limit=2000",
                            key, timeout=60)
    td = jloads(txt_t) or {}
    chk("我的任务 /api/v1/me/tasks 可达", st_t == 200 and isinstance(td.get("tasks"), list),
        "台账 %s 条 · 本页 %d 条" % (td.get("total"), len(td.get("tasks") or [])))

    say("  探 interp 空 body …")
    st1, txt1 = http_json("POST", host + API_PREFIX + "/video/viapi/interp",
                          key, {}, timeout=a.timeout)
    e1 = (jloads(txt1) or {}).get("error") if isinstance(jloads(txt1), dict) else {}
    c1 = (e1 or {}).get("code") or ""
    chk("interp 空 body 停在参数校验（400 empty_url）", st1 == 400 and c1 == "empty_url",
        "HTTP %s %s" % (st1, c1 or err_text(st1, txt1)[:40]))

    say("  探 interp 坏 URL …")
    st2, txt2 = http_json("POST", host + API_PREFIX + "/video/viapi/interp", key,
                          {"videoUrl": "https://example.invalid/a.mp4"}, timeout=a.timeout)
    e2 = (jloads(txt2) or {}).get("error") if isinstance(jloads(txt2), dict) else {}
    c2 = (e2 or {}).get("code") or ""
    chk("interp 素材白名单生效（400 url_not_allowed）", st2 == 400 and c2 == "url_not_allowed",
        "HTTP %s %s" % (st2, c2 or err_text(st2, txt2)[:40]))

    st3, txt3 = http_multipart(host + API_PREFIX + "/upload", key, {}, [],
                               timeout=a.timeout)
    d3 = jloads(txt3) or {}
    chk("上传口 POST /upload 免费可达", st3 == 200 and d3.get("code") == 0,
        "HTTP %s %s" % (st3, (d3.get("msg") or "")[:40]))

    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task",
                          key, timeout=40)
    d4 = jloads(txt4) or {}
    chk("任务查询 GET /tasks/{id} 可达（免费）", st4 == 200 and d4.get("code") == 0,
        "HTTP %s %s" % (st4, (d4.get("msg") or "")[:30]))

    st5, txt5 = http_json("GET", host + "/user/balance/logs?limit=20", key, timeout=40)
    d5 = jloads(txt5) or {}
    logs = d5.get("logs") or []
    win = [x for x in logs
           if int(x.get("at") or 0) >= int(time.time() * 1000) - 3600000]
    net = sum(float(x.get("points") or 0) for x in win)
    chk("流水接口可达 + 近 1 小时净额", st5 == 200 and isinstance(logs, list),
        "%d 条流水 · 近 1 小时 %s 点" % (len(logs), pnum(net)))

    out = {"ok": all(c[1] for c in checks), "host": host,
           "routeCount": len(ROUTE_ORDER),
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks],
           "estimatedPoints": 0, "yuan": 0.0,
           "note": "10 项检查全都是只读 GET 或空 body POST；三个 music_generation "
                   "接口一律不 POST（缺参会先冻 60 点再退），用 /apps + /pricing 证明在架"}
    if not out["ok"]:
        out["exit"] = EXIT_GATE
        out["error"] = {"kind": "gate", "message": "自检有 %d 项未通过"
                        % sum(1 for c in checks if not c[1])}
    if a.json:
        jout(out)
        return 0 if out["ok"] else EXIT_GATE
    emit()
    emit("自检（不扣费：只读 GET + 2 个 interp 空 body 探针 + 1 个空上传）")
    emit()
    for n, o, dd in checks:
        emit("  %s %s %s" % ("√" if o else "×", pad(n, 44), dd))
    emit()
    emit("  三个音频接口一次都没 POST：缺参的 POST 会先 reserve_sync 冻 60 点再退，")
    emit("  钱包会被动一下。在架与否用 /api/v1/apps + /api/v1/pricing 两个只读接口证明。")
    emit("  本轮花费 0 点（没有建任何任务）。")
    return 0 if out["ok"] else EXIT_GATE


# ── 上传 / audio_id ────────────────────────────────────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（本地音频或视频）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + API_PREFIX + "/upload"
    _gate(a, 0, 1)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path,
               "size": size, "estimatedPoints": 0}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不上传）")
        emit("  端点：POST %s（multipart，字段名 file）" % url)
        emit("  文件：%s（%s 字节）" % (path, pnum(size)))
        emit("  花费：0 点（上传不计费）")
        return 0
    say("正在上传 %s（%s 字节）…" % (os.path.basename(path), pnum(size)))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    out = {"ok": True, "url": got, "size": data.get("size"), "name": data.get("name"),
           "mime": data.get("mime_type"), "type": data.get("type"),
           "elapsed": round(dt, 1), "estimatedPoints": 0}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "upload",
                "file": path, "size": size, "url": got})
    if a.json:
        jout(out)
        return 0
    emit("已上传（免费，%.1fs）" % dt)
    emit("  地址：%s" % got)
    emit("  类型：%s · %s · %s 字节" % (data.get("type"), data.get("mime_type"),
                                        pnum(data.get("size") or size)))
    emit("  有效期：约 24 小时，尽快接下一步")
    emit()
    emit("  下一步：python3 scripts/run.py audio-id --audio-url \"%s\" --yes" % got)
    return 0


def cmd_audio_id(a, key, host):
    u = (a.audio_url or "").strip()
    if not u:
        raise Fail("usage", "必须给 --audio-url（可公网访问的音频地址；本地文件先 upload）",
                   EXIT_USAGE)
    if not (u.startswith("http://") or u.startswith("https://")):
        raise Fail("usage", "--audio-url 要以 http:// 或 https:// 开头", EXIT_USAGE)
    q = quote("upload_audio")
    _gate(a, gate_points(q), 1, q["basis"])
    url = host + ROUTES["upload_audio"]["path"]
    body = {"audio_url": u}
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": q["points"], "source": q["source"], "basis": q["basis"]}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不提交、不扣费）")
        emit("  端点：%s" % url)
        emit("  请求：%s" % json.dumps(body, ensure_ascii=False))
        emit("  预估：%s 点（%s 元）· %s" % (pnum(q["points"]), yuan(q["points"]), q["basis"]))
        return 0
    say("正在换 audio_id …")
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    inner = result.get("data") if isinstance(result.get("data"), dict) else {}
    audio_id = (result.get("audio_id") or inner.get("audio_id")
                or data.get("audio_id") or d.get("audio_id"))
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("actual_points") or usage.get("points_cost")
    if d.get("code") != 1 or not audio_id:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "audio-id", "http": st, "error": msg})
        raise Fail("call", "换 audio_id 失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    out = {"ok": True, "audioId": audio_id, "audioUrl": result.get("audio_url") or u,
           "duration": result.get("duration") or inner.get("duration"),
           "actualPoints": real, "estimatedPoints": q["points"],
           "source": q["source"], "endpoint": ROUTES["upload_audio"]["path"]}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "audio-id",
                "audioId": audio_id, "actualPoints": real,
                "estimatedPoints": q["points"]})
    if a.json:
        jout(out)
        return 0
    emit("已拿到 audio_id")
    emit("  audio_id：%s" % audio_id)
    if out.get("duration"):
        emit("  时长：%s 秒" % pnum(out["duration"]))
    if real is not None:
        emit("  实扣：%s 点（预估 %s 点）" % (pnum(real), pnum(q["points"])))
    emit()
    emit("  下一步：python3 scripts/run.py split --audio-id %s --start 0 --end 30 --yes"
         % audio_id)
    return 0


# ── 人声分离 ───────────────────────────────────────────────────────────────
def find_urls(obj, out=None, depth=0):
    if out is None:
        out = []
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("http"):
                out.append((k, v))
            elif isinstance(v, (dict, list)):
                find_urls(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            find_urls(v, out, depth + 1)
    return out


def poll(a, key, host, task_id, video=False):
    """轮询只用 GET /api/v1/tasks/<id>（免费）。视频线再补一条 viapi 视图。"""
    deadline = time.time() + max(5, a.wait)
    paths = [API_PREFIX + "/tasks/" + task_id]
    if video:
        paths.append(API_PREFIX + "/video/viapi/result/" + task_id)
    last = None
    while True:
        for p in paths:
            st, txt = http_json("GET", host + p, key, timeout=40)
            d = jloads(txt) or {}
            data = d.get("data") if isinstance(d.get("data"), dict) else {}
            if st == 200 and (d.get("code") == 1 or d.get("status")
                              or data.get("status") or d.get("taskId")):
                last = (p, d, data)
                stt = (data.get("status") or d.get("status") or "")
                if str(stt).lower() in ("completed", "success", "succeeded",
                                        "failed", "error", "canceled", "cancelled"):
                    return p, d, data
            elif st not in (200,):
                last = (p, d, data)
        if time.time() >= deadline:
            return last if last else (paths[0], {}, {})
        time.sleep(max(1, min(5, a.interval)))


def cmd_split(a, key, host):
    aid = (a.audio_id or "").strip()
    if not aid:
        raise Fail("usage", "必须给 --audio-id（先用 audio-id 换；生成的音乐也能拿到）",
                   EXIT_USAGE)
    body = {"audio_id": aid}
    if a.start is not None:
        body["vocal_start"] = a.start
    if a.end is not None:
        body["vocal_end"] = a.end
    if a.callback_url:
        body["callback_url"] = a.callback_url
    q = quote("vox")
    _gate(a, gate_points(q), 1, q["basis"])
    url = host + ROUTES["vox"]["path"]
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": q["points"], "source": q["source"], "basis": q["basis"]}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不提交、不冻结）")
        emit("  端点：%s" % url)
        emit("  请求：%s" % json.dumps(body, ensure_ascii=False))
        emit("  预估：%s 点（%s 元）· %s" % (pnum(q["points"]), yuan(q["points"]), q["basis"]))
        return 0
    say("正在提交人声分离 …")
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = d.get("task_id") or d.get("taskId") or data.get("task_id") or data.get("taskId")
    if d.get("code") != 1 or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "split", "http": st, "error": msg})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    out = {"ok": True, "route": "vox", "taskId": task_id,
           "status": data.get("status") or d.get("status"),
           "frozenPoints": data.get("frozen_points"),
           "estimatedPoints": q["points"], "source": q["source"],
           "endpoint": ROUTES["vox"]["path"]}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "split",
                "taskId": task_id, "estimatedPoints": q["points"]})
    if a.wait and not a.no_wait and not a.json:
        say("已提交，开始轮询（GET /api/v1/tasks/%s，免费）…" % task_id)
        p, dd, data2 = poll(a, key, host, task_id, video=False)
        urls = find_urls(data2 or dd)
        out.update({"status": (data2 or {}).get("status") or dd.get("status"),
                    "queryPath": p, "urls": [{"key": k, "url": v} for k, v in urls]})
    if a.json:
        jout(out)
        return 0
    emit("已提交（异步）")
    emit("  能力：vox 人声分离")
    emit("  任务：%s   状态：%s" % (task_id, out.get("status")))
    if out.get("frozenPoints") is not None:
        emit("  预冻结：%s 点（完成按实际结算，失败全额退）" % pnum(out["frozenPoints"]))
    if out.get("urls"):
        emit("  产物：")
        for x in out["urls"][:6]:
            emit("    %-16s %s" % (x["key"], x["url"]))
    elif out.get("queryPath"):
        emit("  产物：这一轮还没出（用 status 再看一次）")
    emit()
    emit("  查进度：python3 scripts/run.py status --task-id %s --video" % task_id)
    return 0


# ── 混搭歌词 ───────────────────────────────────────────────────────────────
def _read_text(direct, path, what):
    if path:
        if not os.path.isfile(path):
            raise Fail("usage", "--%s-file 不存在：%s" % (what, path), EXIT_USAGE)
        with io.open(path, encoding="utf-8") as f:
            return f.read().strip()
    return (direct or "").strip()


def cmd_mashup(a, key, host):
    la = _read_text(a.a, a.a_file, "a")
    lb = _read_text(a.b, a.b_file, "b")
    if not la or not lb:
        raise Fail("usage", "必须给两段歌词：--a / --b（直接写）或 --a-file / --b-file"
                   "（UTF-8 文本，中文歌词建议用文件，省得命令行转义）", EXIT_USAGE)
    body = {"lyrics_a": la, "lyrics_b": lb}
    q = quote("mashup_lyrics")
    _gate(a, gate_points(q), 1, q["basis"])
    url = host + ROUTES["mashup_lyrics"]["path"]
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url,
               "requestBody": {"lyrics_a": la[:60] + ("…" if len(la) > 60 else ""),
                               "lyrics_b": lb[:60] + ("…" if len(lb) > 60 else "")},
               "estimatedPoints": q["points"], "source": q["source"], "basis": q["basis"]}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不提交、不扣费）")
        emit("  端点：%s" % url)
        emit("  请求：lyrics_a %d 字 / lyrics_b %d 字" % (len(la), len(lb)))
        emit("  预估：%s 点（%s 元）· %s" % (pnum(q["points"]), yuan(q["points"]), q["basis"]))
        return 0
    say("正在混合两段歌词 …")
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    inner = result.get("data") if isinstance(result.get("data"), dict) else {}
    text = inner.get("text") or result.get("text") or data.get("text")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("actual_points") or usage.get("points_cost")
    if d.get("code") != 1 or not text:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "mashup", "http": st, "error": msg})
        raise Fail("call", "混合失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    out = {"ok": True, "route": "mashup_lyrics", "title": inner.get("title") or result.get("title"),
           "text": text, "actualPoints": real, "estimatedPoints": q["points"],
           "chars": len(text), "endpoint": ROUTES["mashup_lyrics"]["path"]}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "mashup",
                "chars": len(text), "actualPoints": real,
                "estimatedPoints": q["points"]})
    if a.json:
        jout(out)
        return 0
    emit("混合好了（同步返回，%d 字）" % len(text))
    if out.get("title"):
        emit("  标题：%s" % out["title"])
    if real is not None:
        emit("  实扣：%s 点（预估 %s 点）" % (pnum(real), pnum(q["points"])))
    emit()
    for ln in text.splitlines():
        emit("  " + ln)
    emit()
    emit("  下一步：把这段词交给 create（type=cover / upload_cover）重唱；")
    emit("  或者先 split 拿伴奏，再 mouth 上去。")
    return 0


# ── 视频插帧 ───────────────────────────────────────────────────────────────
def cmd_interp(a, key, host):
    u = (a.video_url or "").strip()
    if not u:
        raise Fail("usage", "必须给 --video-url（本网关托管的视频地址；本地文件先 upload）",
                   EXIT_USAGE)
    if not (u.startswith("http://") or u.startswith("https://")):
        raise Fail("usage", "--video-url 要以 http:// 或 https:// 开头", EXIT_USAGE)
    ok_url, kind = url_allowed(u)
    if not ok_url and not a.allow_any_url:
        raise Fail("usage",
                   "视频线只收本站托管的地址（%s 不在白名单，实测会回 400 url_not_allowed）。\n"
                   "  · 先 upload 再提交（推荐）：python3 scripts/run.py upload --file 你的片子.mp4\n"
                   "  · 本站成片：https://vr.a7w.cn/result/xxx.mp4\n"
                   "  · 本站上传接口：https://oss.gpu.likeadmin.cn/openapi/..." % kind,
                   EXIT_USAGE)
    secs = int(a.seconds) if a.seconds else DEFAULT_DURATION
    body = {"videoUrl": u, "duration": secs}
    q = quote("interp", secs)
    _gate(a, gate_points(q), 1, q["basis"])
    url = host + ROUTES["interp"]["path"]
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": q["points"], "source": q["source"],
               "basis": q["basis"], "status": ROUTES["interp"]["status"]}
        if a.json:
            jout(out)
            return 0
        emit("干跑（不提交、不冻结）")
        emit("  端点：%s" % url)
        emit("  请求：%s" % json.dumps(body, ensure_ascii=False))
        emit("  预估：%s 点（%s 元）· %s" % (pnum(q["points"]), yuan(q["points"]), q["basis"]))
        emit("  状态：待验证 —— 价目表有 25 点/秒，线上档位说明写过「已下线」，")
        emit("        两种空探针都停在参数校验；真跑一条才知道结不结算。")
        return 0
    say("正在提交插帧任务 …")
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = d.get("taskId") or d.get("task_id") or data.get("taskId") or data.get("task_id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "interp", "http": st, "error": msg})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    out = {"ok": True, "route": "interp", "taskId": task_id,
           "status": d.get("status") or data.get("status"),
           "duration": d.get("duration") or secs,
           "cost": d.get("cost"), "estimatedPoints": q["points"],
           "endpoint": ROUTES["interp"]["path"]}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "interp",
                "taskId": task_id, "estimatedPoints": q["points"]})
    if a.wait and not a.no_wait and not a.json:
        say("已提交，开始轮询（GET /api/v1/tasks/%s，免费）…" % task_id)
        p, dd, data2 = poll(a, key, host, task_id, video=True)
        urls = find_urls(data2 or dd)
        out.update({"status": (data2 or {}).get("status") or dd.get("status"),
                    "queryPath": p, "urls": [{"key": k, "url": v} for k, v in urls]})
    if a.json:
        jout(out)
        return 0
    emit("已提交")
    emit("  能力：视频插帧 60fps（%s 秒）" % pnum(secs))
    emit("  任务：%s   状态：%s" % (task_id, out.get("status")))
    if out.get("cost") is not None:
        emit("  冻结：%s 点" % pnum(out["cost"]))
    if out.get("urls"):
        emit("  产物：")
        for x in out["urls"][:6]:
            emit("    %-16s %s" % (x["key"], x["url"]))
    emit()
    emit("  查进度：python3 scripts/run.py status --task-id %s --video" % task_id)
    return 0


# ── 全链路 ─────────────────────────────────────────────────────────────────
def chain_plan(a):
    """整条链路的步骤与估价。步骤顺序就是执行顺序。"""
    items = []
    q_aid = quote("upload_audio")
    q_vox = quote("vox")
    items.append(("1 upload", 0.0, "本地文件 -> 平台地址（免费）",
                  "POST %s" % (API_PREFIX + "/upload")))
    items.append(("2 audio-id", q_aid["points"], q_aid["basis"],
                  "POST %s" % ROUTES["upload_audio"]["path"]))
    items.append(("3 split", q_vox["points"], q_vox["basis"],
                  "POST %s" % ROUTES["vox"]["path"]))
    total = (q_aid["points"] or 0) + (q_vox["points"] or 0)
    if a.with_mashup:
        q = quote("mashup_lyrics")
        items.append(("4 mashup", q["points"], q["basis"],
                      "POST %s" % ROUTES["mashup_lyrics"]["path"]))
        total += q["points"] or 0
    if a.with_interp:
        secs = int(a.seconds or DEFAULT_DURATION)
        q = quote("interp", secs)
        items.append(("5 interp", q["points"], "%d 点/秒 x %d 秒" % (25, secs),
                      "POST %s" % ROUTES["interp"]["path"]))
        total += q["points"] or 0
    return items, total


def cmd_chain(a, key, host):
    # 先把所有输入校验完，再发第一个请求 —— 不能传完文件才发现缺参数
    if not a.file:
        raise Fail("usage", "必须给 --file（要分离的本地音频/视频）", EXIT_USAGE)
    if not os.path.isfile(a.file):
        raise Fail("usage", "文件不存在：%s" % a.file, EXIT_USAGE)
    la = lb = ""
    if a.with_mashup:
        la = _read_text(a.a, a.a_file, "a")
        lb = _read_text(a.b, a.b_file, "b")
        if not la or not lb:
            raise Fail("usage", "--with-mashup 要两段歌词：--a / --b 或 --a-file / --b-file",
                       EXIT_USAGE)
    if a.with_interp:
        if not a.video_url:
            raise Fail("usage", "--with-interp 还要 --video-url（要补帧的片子，本网关托管地址）",
                       EXIT_USAGE)
        ok_url, kind = url_allowed(a.video_url)
        if not ok_url and not a.allow_any_url:
            raise Fail("usage",
                       "视频线只收本站托管的地址（%s 不在白名单）。先 upload --file 拿到地址再填。"
                       % kind, EXIT_USAGE)
    items, total = chain_plan(a)
    _gate(a, total, 3 + (1 if a.with_mashup else 0) + (1 if a.with_interp else 0),
          "整条链路")
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "file": a.file, "steps": [
            {"step": n, "points": pts, "basis": b, "endpoint": e}
            for n, pts, b, e in items],
            "estimatedPoints": round(total, 2), "yuan": round(total / 100.0, 2)}
        if a.json:
            jout(out)
            return 0
        emit("干跑 · 一条二创素材的完整链路（不提交、不冻结）")
        emit()
        for n, pts, b, e in items:
            emit("  %-12s %-46s %s 点" % (n, e.replace(API_PREFIX, ""), pnum(pts)))
            emit("  %-12s %s" % ("", b))
        emit()
        emit("  合计：%s 点 = %s 元" % (pnum(total), yuan(total)))
        emit("  真正跑：加 --yes（第 1 步免费，2 起开始扣点）")
        return 0

    note = []

    say("[1] 上传 %s …" % os.path.basename(a.file))
    st, txt = http_multipart(host + API_PREFIX + "/upload", key, {},
                             [("file", a.file)], timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    audio_url = data.get("url")
    if d.get("code") != 1 or not audio_url:
        raise Fail("call", "第 1 步上传失败（HTTP %s）：%s" % (st, err_text(st, txt)),
                   EXIT_CALL)
    emit("  平台地址：%s" % audio_url)

    say("[2] 换 audio_id …")
    st, txt = http_json("POST", host + ROUTES["upload_audio"]["path"], key,
                        {"audio_url": audio_url}, timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    inner = result.get("data") if isinstance(result.get("data"), dict) else {}
    audio_id = result.get("audio_id") or inner.get("audio_id") or data.get("audio_id")
    if d.get("code") != 1 or not audio_id:
        raise Fail("call", "第 2 步失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    emit("  audio_id：%s" % audio_id)

    body = {"audio_id": audio_id}
    if a.start is not None:
        body["vocal_start"] = a.start
    if a.end is not None:
        body["vocal_end"] = a.end
    say("[3] 人声分离 …")
    st, txt = http_json("POST", host + ROUTES["vox"]["path"], key, body, timeout=a.timeout)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = d.get("task_id") or d.get("taskId") or data.get("task_id") or data.get("taskId")
    if d.get("code") != 1 or not task_id:
        raise Fail("call", "第 3 步失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    emit("  vox 任务：%s" % task_id)
    status, urls = None, []
    if not a.no_wait and a.wait:
        say("轮询 GET /api/v1/tasks/%s（免费）…" % task_id)
        p, dd, data2 = poll(a, key, host, task_id, video=False)
        status = (data2 or {}).get("status") or dd.get("status")
        urls = find_urls(data2 or dd)
        emit("  状态：%s" % status)
        for k, v in urls[:6]:
            emit("    %-16s %s" % (k, v))

    mashup_text = None
    if a.with_mashup:
        say("[4] 混搭歌词 …")
        st, txt = http_json("POST", host + ROUTES["mashup_lyrics"]["path"], key,
                            {"lyrics_a": la, "lyrics_b": lb}, timeout=a.timeout)
        d = jloads(txt) or {}
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        r2 = data.get("result") if isinstance(data.get("result"), dict) else {}
        i2 = r2.get("data") if isinstance(r2.get("data"), dict) else {}
        mashup_text = i2.get("text") or r2.get("text") or data.get("text")
        if d.get("code") != 1 or not mashup_text:
            raise Fail("call", "第 4 步失败（HTTP %s）：%s" % (st, err_text(st, txt)),
                       EXIT_CALL)
        emit("  新词 %d 字" % len(mashup_text))

    interp_task = None
    if a.with_interp:
        say("[5] 视频插帧 …")
        secs = int(a.seconds or DEFAULT_DURATION)
        st, txt = http_json("POST", host + ROUTES["interp"]["path"], key,
                            {"videoUrl": a.video_url, "duration": secs},
                            timeout=a.timeout)
        d = jloads(txt) or {}
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        interp_task = (d.get("taskId") or d.get("task_id")
                       or data.get("taskId") or data.get("task_id"))
        if st not in (200, 201) or not interp_task:
            raise Fail("call", "第 5 步失败（HTTP %s）：%s" % (st, err_text(st, txt)),
                       EXIT_CALL)
        emit("  interp 任务：%s" % interp_task)

    out = {"ok": True, "file": a.file, "audioUrl": audio_url, "audioId": audio_id,
           "taskId": task_id, "status": status,
           "urls": [{"key": k, "url": v} for k, v in urls],
           "mashupText": mashup_text, "interpTaskId": interp_task,
           "estimatedPoints": round(total, 2), "yuan": round(total / 100.0, 2),
           "steps": [{"step": n, "points": pts} for n, pts, b, e in items]}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "chain",
                "file": a.file, "taskId": task_id, "interpTaskId": interp_task,
                "estimatedPoints": round(total, 2)})
    if a.json:
        jout(out)
        return 0
    emit()
    emit("链路跑完：预估 %s 点 = %s 元" % (pnum(total), yuan(total)))
    if mashup_text:
        emit("  新词：")
        for ln in mashup_text.splitlines()[:12]:
            emit("    " + ln)
    if interp_task:
        emit("  补帧任务：%s（用 status --video 看进度）" % interp_task)
    if not a.with_interp:
        emit("  想补到 60fps：python3 scripts/run.py interp --video-url <地址> "
             "--seconds %d --yes" % int(a.seconds or 30))
    return 0


# ── 横评 ───────────────────────────────────────────────────────────────────
NEED_LABEL = {"relabel": "两段歌词融成一段", "split": "一条曲子拆人声 / 伴奏",
              "interp": "30fps 补到 60fps"}


def text_models(key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/models", key, timeout=60)
    d = jloads(txt) or {}
    out = []
    for m in (d.get("data") or []):
        if (m.get("type_code") or "").lower() != "text":
            continue
        p = m.get("pricing")
        if not isinstance(p, dict):
            continue
        pi, po = p.get("per_1k_input"), p.get("per_1k_output")
        if pi is None or po is None:
            continue
        out.append({"code": m.get("model_code"), "name": m.get("model_name"),
                    "per1kIn": float(pi), "per1kOut": float(po),
                    "ctx": m.get("context_length")})
    return out


def cmd_models(a, key, host):
    need = a.need
    pages = 70 if a.all else a.pages
    reqs = (1 if need == "relabel" else 0) + pages
    _gate(a, 0, reqs, "横评")
    if a.dry_run:
        return _plan(a, reqs, ["GET %s/models（文本模型单价）" % API_PREFIX]
                     + ["GET %s/me/tasks（limit=2000 page=%d）" % (API_PREFIX, i)
                        for i in range(1, pages + 1)], 0)
    # /me/tasks 按 path 归集（免费）
    live = {}
    for pg in range(1, pages + 1):
        st, txt = http_json("GET", host + API_PREFIX + "/me/tasks?limit=2000&page=%d" % pg,
                            key, timeout=60)
        d = jloads(txt) or {}
        ts = d.get("tasks") or []
        if not ts:
            break
        for t in ts:
            p = t.get("path") or ""
            try:
                v = float(t.get("actualPrice") or 0)
            except Exception:                                    # noqa: BLE001
                continue
            if v <= 0:
                continue
            x = live.setdefault(p, {"n": 0, "low": v, "high": v})
            x["n"] += 1
            x["low"] = min(x["low"], v)
            x["high"] = max(x["high"], v)
        if len(ts) < 20:
            break

    cands = []
    if need == "split":
        picks = ("vox", "create_stems", "create_all_stems")
        if a.models:
            picks = tuple(x.strip() for x in a.models.split(",") if x.strip())
        for rid in picks:
            if rid not in ("vox", "create_stems", "create_all_stems"):
                raise Fail("usage", "split 横评只认 vox / create_stems / create_all_stems",
                           EXIT_USAGE)
            r = ROUTES[rid]
            q = quote(rid, 0, live)
            cands.append(dict(id=rid, name=r["name"],
                              route=r["path"].replace(API_PREFIX, ""),
                              points=q["points"], source=q["source"],
                              basis=q["basis"], note=r["desc"]))
    elif need == "interp":
        picks = ("interp", "local")
        if a.models:
            picks = tuple(x.strip() for x in a.models.split(",") if x.strip())
        for rid in picks:
            if rid not in ("interp", "local"):
                raise Fail("usage", "interp 横评只认 interp / local", EXIT_USAGE)
            secs = int(a.seconds or 30)
            q = quote(rid, secs, live)
            cands.append(dict(id=rid, name=ROUTES[rid]["name"],
                              route=ROUTES[rid]["path"].replace(API_PREFIX, ""),
                              points=q["points"], source=q["source"],
                              basis=q["basis"] if rid == "interp"
                              else "本机 ffmpeg minterpolate，不联网、不扣点",
                              note=ROUTES[rid]["desc"]))
    else:
        secs = int(a.seconds or 0)
        qm = quote("mashup_lyrics")
        cands.append(dict(id="mashup_lyrics", name=ROUTES["mashup_lyrics"]["name"],
                          route=ROUTES["mashup_lyrics"]["path"].replace(API_PREFIX, ""),
                          points=qm["points"], source=qm["source"], basis=qm["basis"],
                          note=ROUTES["mashup_lyrics"]["desc"]))
        tm = text_models(key, host)
        chars = int(a.chars or 2000)
        tin = chars * 1.5
        tout = chars * 0.8
        for m in tm:
            pts = tin / 1000.0 * m["per1kIn"] + tout / 1000.0 * m["per1kOut"]
            cands.append(dict(id=m["code"], name=m["name"] or m["code"],
                              route="/api/v1/chat/completions",
                              points=round(pts, 2), source="rate",
                              basis="%s / %s 点每 1k token x %d 字（约 %d in / %d out token）"
                                    % (pnum(m["per1kIn"]), pnum(m["per1kOut"]), chars,
                                       int(tin), int(tout)),
                              note="模型层文本，按 token 计；调用形态 chat/completions"))
        if a.models:
            want = [x.strip() for x in a.models.split(",") if x.strip()]
            idx = {c["id"]: c for c in cands}
            missing = [w for w in want if w not in idx]
            if missing:
                raise Fail("usage", "不认识的模型：%s。可从 /api/v1/models 里挑，"
                           "例如 %s" % ("、".join(missing),
                                        "、".join([c["id"] for c in cands[1:4]])), EXIT_USAGE)
            cands = [idx[w] for w in want]
        else:
            # 默认：mashup 一条 + 最便宜的 3 个文本模型
            others = sorted([c for c in cands[1:] if c["points"] is not None],
                            key=lambda c: c["points"])[:3]
            cands = [cands[0]] + others

    cands.sort(key=lambda c: (c["points"] is None, c["points"] or 0))
    out = {"ok": True, "need": need, "needLabel": NEED_LABEL[need],
           "seconds": a.seconds, "chars": a.chars, "candidates": cands,
           "cheapest": cands[0]["id"] if cands else None,
           "pagesScanned": pages, "estimatedPoints": 0,
           "note": "live = 你账号 /api/v1/me/tasks 的 actualPrice；"
                   "rate = /api/v1/models 的官方每千 token 单价；"
                   "pricing×doc = 上游价 x 3；unknown = 不给数字"}
    if a.json:
        jout(out)
        return 0
    emit("同一需求多模型横评 · %s（扫描 %d 页任务台账）" % (NEED_LABEL[need], pages))
    emit("=" * 104)
    emit("  %s %s %s %s %s" % (pad("候选", 26), pad("调用路径", 36),
                                pad("报价", 11, False), pad("来源", 12), "口径"))
    emit("  " + "-" * 100)
    for c in cands:
        price = ("%s 点" % pnum(c["points"])) if c["points"] is not None else "待实测"
        emit("  %s %s %s %s %s" % (
            pad(c["name"][:25], 26), pad(c["route"][:35], 36),
            pad(price, 11, False), pad(c["source"], 12), c["basis"][:40]))
    emit()
    if out["cheapest"]:
        emit("  最便宜：%s" % out["cheapest"])
    if need == "relabel":
        emit("  读法：mashup_lyrics 是专做「两段词融合」的应用接口，按次；")
        emit("  文本模型按 token 计，2000 字输入就上万 token，单价看着低、总价反而高。")
        emit("  默认按价格取最便宜的 3 个，专做翻译 / 嵌入的模型也会被算进来；")
        emit("  要指定用 --models DeepSeek-V4-Flash,Qwen3.8-Omni-Flash 这样点名。")
    elif need == "split":
        emit("  读法：vox 按次固定，create 的价随 type 变；本账号有 create 流水就按实测区间报。")
    else:
        emit("  读法：interp 25 点/秒是价目表里写死的；本机 ffmpeg 补帧 0 点但要自己等。")
    emit("  本轮花费 0 点（只读 GET）。")
    return 0


# ── 查任务 / 台账 ──────────────────────────────────────────────────────────
def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    _gate(a, 0, 3)
    cands = [API_PREFIX + "/tasks/" + tid]
    if a.video:
        cands.append(API_PREFIX + "/video/viapi/result/" + tid)
    hit = None
    for p in cands:
        st, txt = http_json("GET", host + p, key, timeout=40)
        d = jloads(txt) or {}
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        empty = (st == 200 and d.get("code") == 0 and not d.get("data")
                 and not d.get("status") and not data)
        if empty and p != cands[-1]:
            continue
        hit = (p, st, txt, d, data)
        break
    p, st, txt, d, data = hit
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    urls = find_urls(data or d)
    usage = (data.get("usage") if isinstance(data.get("usage"), dict) else {})
    out = {"ok": True, "taskId": tid, "path": p,
           "status": data.get("status") or d.get("status"),
           "tool": data.get("tool"), "cost": data.get("cost") or usage.get("points_cost"),
           "refund": data.get("refund"), "message": data.get("message") or d.get("msg"),
           "urls": [{"key": k, "url": v} for k, v in urls],
           "result": data.get("result") if isinstance(data.get("result"), (dict, list))
           else None}
    if a.json:
        jout(out)
        return 0
    emit("任务 %s" % tid)
    emit("  查询路径：%s" % p)
    emit("  状态：%s" % out["status"])
    if out.get("tool"):
        emit("  能力：%s" % out["tool"])
    if out.get("cost") is not None:
        emit("  点数：%s" % pnum(out["cost"]))
    if out.get("refund") is not None:
        emit("  退回：%s 点" % pnum(out["refund"]))
    for x in out["urls"][:8]:
        emit("  %-16s %s" % (x["key"], x["url"]))
    if out.get("message"):
        emit("  说明：%s" % str(out["message"])[:200])
    return 0


def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        arr = json.load(open(LEDGER, encoding="utf-8"))
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        jout(out)
        return 0
    emit("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        emit("  %s  %-4s %-9s %-24s %s 点" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            (e.get("taskId") or e.get("audioId")
             or os.path.basename(e.get("file") or "-"))[:24],
            pnum(e.get("actualPoints") if e.get("actualPoints") is not None
                 else e.get("estimatedPoints"))))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 音频工具台：人声分离 42 点、混搭歌词 36 点、补帧 25 点/秒",
        epilog="端点：POST %s/api/v1/apps/music_generation/<vox|mashup_lyrics|"
               "upload_audio> · POST %s/api/v1/video/viapi/interp · "
               "POST %s/api/v1/upload · GET %s/api/v1/tasks/<id>（查任务，免费）"
               % ((DEFAULT_HOST,) * 4),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 60 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    def gate_args(p):
        p.add_argument("--yes", action="store_true", help="确认真实提交并冻结点数")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("catalog", help="8 条路线：单价 / 调用形态 / 路径（免费）",
                       allow_abbrev=False)
    p.add_argument("--seconds", type=int, default=30, help="按秒档按多少秒显示（默认 30）")
    gate_args(p)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：单次价 + 整条链路总价（免费）",
                       allow_abbrev=False)
    p.add_argument("--route", choices=ROUTE_ORDER, help="只看这一条（默认全部）")
    p.add_argument("--seconds", type=int, default=60, help="按秒档/链路按多少秒算（默认 60）")
    gate_args(p)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 价目表 / 接口在架 / 流水（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    gate_args(p)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="本地文件 -> 平台地址（免费）", allow_abbrev=False)
    p.add_argument("--file", help="本地音频/视频路径（单文件 512 MB 上限）")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    gate_args(p)
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("audio-id", help="平台地址 -> audio_id（39 点起，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--audio-url", help="可公网访问的音频地址（先 upload）")
    p.add_argument("--timeout", type=int, default=180, help="超时秒数（默认 180）")
    gate_args(p)
    p.set_defaults(fn=cmd_audio_id)

    p = sub.add_parser("split", help="audio_id -> 人声 / 伴奏（42 点起，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--audio-id", help="audio-id 换来的 ID，或生成音乐的 audio_id")
    p.add_argument("--start", type=float, default=None, help="人声起点（秒），只取副歌就填")
    p.add_argument("--end", type=float, default=None, help="人声终点（秒）")
    p.add_argument("--callback-url", help="完成回调地址（可选）")
    p.add_argument("--wait", type=int, default=90, help="提交后最多等多少秒（默认 90）")
    p.add_argument("--interval", type=int, default=3, help="轮询间隔秒数（默认 3）")
    p.add_argument("--no-wait", action="store_true", help="提交完立刻返回，不轮询")
    p.add_argument("--timeout", type=int, default=180, help="提交超时秒数（默认 180）")
    gate_args(p)
    p.set_defaults(fn=cmd_split)

    p = sub.add_parser("mashup", help="两段歌词 -> 一段新的（36 点起，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--a", help="第一段歌词（直接写）")
    p.add_argument("--b", help="第二段歌词（直接写）")
    p.add_argument("--a-file", help="第一段歌词文件（UTF-8，中文建议用文件）")
    p.add_argument("--b-file", help="第二段歌词文件（UTF-8）")
    p.add_argument("--timeout", type=int, default=180, help="超时秒数（默认 180）")
    gate_args(p)
    p.set_defaults(fn=cmd_mashup)

    p = sub.add_parser("interp", help="视频补到 60fps（25 点/秒，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--video-url", help="本网关托管的视频地址（先 upload）")
    p.add_argument("--seconds", type=int, default=DEFAULT_DURATION,
                   help="视频秒数（按秒计费，缺省 %d）" % DEFAULT_DURATION)
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--wait", type=int, default=120, help="提交后最多等多少秒（默认 120）")
    p.add_argument("--interval", type=int, default=4, help="轮询间隔秒数（默认 4）")
    p.add_argument("--no-wait", action="store_true", help="提交完立刻返回，不轮询")
    p.add_argument("--timeout", type=int, default=180, help="提交超时秒数（默认 180）")
    gate_args(p)
    p.set_defaults(fn=cmd_interp)

    p = sub.add_parser("chain", help="一条素材跑完整链路（--dry-run 先看总价）",
                       allow_abbrev=False)
    p.add_argument("--file", help="要分离的本地音频/视频")
    p.add_argument("--start", type=float, default=None, help="人声起点（秒）")
    p.add_argument("--end", type=float, default=None, help="人声终点（秒）")
    p.add_argument("--with-mashup", dest="with_mashup", action="store_true",
                   help="链路里加上 mashup_lyrics（改词，+36 点）")
    p.add_argument("--with-interp", dest="with_interp", action="store_true",
                   help="链路里加上 interp 补帧（+25 点/秒）")
    p.add_argument("--a", help="--with-mashup 时第一段歌词（直接写）")
    p.add_argument("--b", help="--with-mashup 时第二段歌词（直接写）")
    p.add_argument("--a-file", help="--with-mashup 时第一段歌词文件（UTF-8）")
    p.add_argument("--b-file", help="--with-mashup 时第二段歌词文件（UTF-8）")
    p.add_argument("--video-url", help="--with-interp 时要补帧的片子地址")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过视频素材白名单预检，把地址交给上游判断")
    p.add_argument("--seconds", type=int, default=30, help="视频秒数（默认 30）")
    p.add_argument("--wait", type=int, default=120, help="提交后最多等多少秒（默认 120）")
    p.add_argument("--interval", type=int, default=3, help="轮询间隔秒数（默认 3）")
    p.add_argument("--no-wait", action="store_true", help="不轮询，提交完就返回")
    p.add_argument("--timeout", type=int, default=600, help="单步超时秒数（默认 600）")
    gate_args(p)
    p.set_defaults(fn=cmd_chain)

    p = sub.add_parser("models", help="同一需求多模型横评（--need relabel|split|interp）",
                       allow_abbrev=False)
    p.add_argument("--need", choices=["relabel", "split", "interp"], default="relabel",
                   help="需求：relabel 改词 / split 分离 / interp 补帧（默认 relabel）")
    p.add_argument("--models", help="逗号分隔的候选（relabel 填文本模型 code，"
                                    "split 填 vox,create_stems）")
    p.add_argument("--chars", type=int, default=2000, help="relabel 时按多少字估 token（默认 2000）")
    p.add_argument("--seconds", type=int, default=30, help="interp 时按多少秒算（默认 30）")
    p.add_argument("--pages", type=int, default=10, help="翻几页任务台账（默认 10）")
    p.add_argument("--all", action="store_true", help="翻完全部台账（约 70 页，要 --yes）")
    gate_args(p)
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser("status", help="查任务（免费，只打 GET /tasks/<id>）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 taskId")
    p.add_argument("--video", action="store_true", help="视频线，再补一条 viapi 视图")
    gate_args(p)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    gate_args(p)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


LOCAL_OK = ("cmd_catalog", "cmd_cost", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("yes", False), ("dry_run", False), ("seconds", 30),
                       ("route", None), ("timeout", 90), ("limit", 20),
                       ("file", None), ("audio_url", None), ("audio_id", None),
                       ("start", None), ("end", None), ("callback_url", None),
                       ("wait", 120), ("interval", 3), ("no_wait", False),
                       ("a", None), ("b", None), ("a_file", None), ("b_file", None),
                       ("video_url", None), ("allow_any_url", False),
                       ("with_mashup", False), ("with_interp", False),
                       ("chain_seconds", None), ("need", "relabel"),
                       ("models", None), ("chars", 2000), ("pages", 10),
                       ("all", False), ("video", False)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    try:
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in LOCAL_OK:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
        return a.fn(a, key, host)
    except Fail as e:
        if a.json:
            jout({"ok": False, "exit": e.exit_code,
                  "error": {"kind": e.kind, "message": e.message}})
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
