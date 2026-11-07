#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 数字人口播台（一张图 + 一段话 → 一个会说话、会对口型的人）

走 api.a7w.cn 的**三个**数字人应用，一条命令一个入口：

  talk    pic_lipsync   文案驱动口播：图 + 参考音色 + 文案 → 口播视频（最轻）
  drive   image_human   全驱动数字人：图 + 音频 → 数字人视频，四档可调
  dub     lipsync       已有视频对口型：视频 + 音频 → 重新对口型

## 权威口径（实测 + live 定价接口，2026-10-10 站主批准）

  接口根地址   https://api.a7w.cn/api/v1
  提交         POST /apps/{pic_lipsync|image_human|lipsync}/submit
  查询         GET  /api/v1/tasks/{task_id}
  应用级查询   POST /apps/{code}/query      body {"task_id": "..."}

  价格
    talk   15 点/秒（上游实扣 3 点/秒 ×5；quality 真名是 quality，默认 standard）
    drive  10 / 15 / 30 / 60 点/输入秒（fast / standard / 2k / 4k）
    dub    上游实际点数 ×3（xiaojiayu1.0 上游 0.9 点/秒 → 2.7 点/秒；
                           2.0 / 3.0 上游 4.5 点/秒 → 13.5 点/秒）

## 三个真会花错钱的坑（都做成了默认动作）

  ① image_human 不传 mode：**出片按 standard、收钱按 fast**（15 vs 10 点/秒）。
     schema 的 default 是 standard，计费卡的 defaultModel 是 fast —— 两边不一致。
     本包 `drive --mode` **必填**，永不下发省略 mode。
  ② pic_lipsync 的档位参数真名是 `quality`（不是 mode）：`mode` 只切 audio/text。
  ③ text 模式省掉录音，但省不掉「参考音色」：audio_url 必填，给一段 3–10 秒清晰人声。

## 子命令

  catalog  三种做法对照（免费）
  cost     先算钱（免费）
  doctor   自检 Key / 三个端点 / 速率卡一致性（免费，不扣费）
  talk     文案驱动口播（pic_lipsync mode=text，15 点/秒）
  drive    全驱动数字人（image_human，按输入秒计费，四档）
  dub      已有视频对口型（lipsync，上游实际×3）
  status   查任务
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --way drive --mode 4k --duration 30
  python3 scripts/run.py doctor
  python3 scripts/run.py talk --image face.png --voice-ref voice.mp3 \\
      --content "大家好，今天聊一件事…" --yes
  python3 scripts/run.py drive --image face.png --audio speech.mp3 \\
      --mode standard --duration 30 --yes
  python3 scripts/run.py dub --video old.mp4 --audio new.mp3 --seconds 30 --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题可加技术微信 9872659。
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
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

APP_TALK = "pic_lipsync"
APP_DRIVE = "image_human"
APP_DUB = "lipsync"

# 价格（点，1 元 = 100 点）—— 与本包内置速率卡一致，doctor 会用 live 定价接口核对
TALK_POINTS_PER_SEC = 15
TALK_MIN_POINTS = 50
DRIVE_RATES = {"fast": 10, "standard": 15, "2k": 30, "4k": 60}
DUB_UPSTREAM_RATE = {"xiaojiayu1.0": 0.9, "xiaojiayu2.0": 4.5, "xiaojiayu3.0": 4.5}
DUB_MARKUP = 3
CHARS_PER_SEC = 4.5          # 中文口播估算：约 4.5 字/秒

QUALITIES = ["standard", "fast", "max"]
DRIVE_MODES = ["fast", "standard", "2k", "4k"]

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "digital-host-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-digital-host/%s" % VERSION

TERMINAL_OK = ("completed", "succeeded", "success")
TERMINAL_BAD = ("failed", "cancelled", "canceled", "error")

MEDIA_RE = re.compile(r"\.(mp4|mov|webm|m4v)(\?|#|$)", re.I)
MEDIA_KEYS = ("video_url", "video_uri", "output_url", "result_url", "video")


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
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
    return txt.replace("\n", " ")[:240]


def envelope(d):
    """平台信封：{"code":1,"msg":"success","data":{…}}；出错时 code=0 且 data=null。"""
    if not isinstance(d, dict):
        return False, "响应不是 JSON", None
    code = d.get("code")
    msg = d.get("msg") or d.get("message") or ""
    ok = (code == 1 or code == "1" or code is True) and d.get("data") is not None
    return ok, str(msg), d.get("data")


def find_media(obj, out=None):
    """递归找视频地址。平台把结果塞在 data / data.result / data.result.data 都可能。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.match(r"^https?://", v):
                if MEDIA_RE.search(v) or k in MEDIA_KEYS:
                    if v not in out:
                        out.append(v)
            else:
                find_media(v, out)
    elif isinstance(obj, list):
        for it in obj:
            find_media(it, out)
    return out


def find_points(obj):
    """从 usage 里取实际点数（points_cost / actual_points）。"""
    if isinstance(obj, dict):
        u = obj.get("usage")
        if isinstance(u, dict):
            for k in ("points_cost", "actual_points", "points"):
                v = u.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        pass
        for v in obj.values():
            got = find_points(v)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for it in obj:
            got = find_points(it)
            if got is not None:
                return got
    return None


def dig_task(d):
    """返回 (status, payload)。兼容「结果里也有一个 result」的双重身份字段。"""
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, dict):
        return None, data
    status = data.get("status")
    node = data
    if not status:
        r = data.get("result")
        if isinstance(r, dict):
            if "code" in r:                       # 中转包装层 → 剥掉
                r2 = r.get("data")
                if isinstance(r2, dict):
                    node = r2
                    status = r2.get("status")
                else:
                    node = r2 if r2 is not None else r
            else:
                node = r
                status = r.get("status")
        elif isinstance(r, str):
            node = data
    return status, node


def ledger_load():
    if not os.path.isfile(LEDGER):
        return []
    try:
        arr = json.load(io.open(LEDGER, encoding="utf-8"))
        return arr if isinstance(arr, list) else []
    except Exception:                                            # noqa: BLE001
        return []


def ledger_add(rec):
    try:
        arr = ledger_load()
        arr.append(rec)
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


# ───────────────────────── 价格 ─────────────────────────
def talk_seconds(a):
    if getattr(a, "seconds", None):
        return float(a.seconds)
    txt = re.sub(r"\s+", "", getattr(a, "content", "") or "")
    if not txt:
        return 0.0
    return round(len(txt) / CHARS_PER_SEC, 1)


def talk_points(sec):
    """15 点/秒，单笔按 50 点下限预估（公开文档写的保底价，取上限不低估）。"""
    return max(TALK_MIN_POINTS, int(round(sec * TALK_POINTS_PER_SEC)))


def drive_points(mode, seconds):
    return int(round(DRIVE_RATES[mode] * float(seconds)))


def dub_points(model, seconds):
    return int(round(DUB_UPSTREAM_RATE[model] * DUB_MARKUP * float(seconds)))


def yuan(points):
    return round(points / 100.0, 2)


# ───────────────────────── 通用流程 ─────────────────────────
def _gate(a, points, what):
    """两道闸门：预算（5）→ 确认（4）。任何请求都还没发。"""
    if points > a.budget:
        raise Fail("budget",
                   "预计 %d 点（%.2f 元）超过 --budget %d 点。%s\n"
                   "调大 --budget（单位：点，1 元 = 100 点）或缩短时长。"
                   % (points, yuan(points), a.budget, what), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会产生真实扣费：%s，预计 **%d 点（%.2f 元）**。确认请加 --yes；"
                   "只想看请求体用 --dry-run。" % (what, points, yuan(points)), EXIT_CONFIRM)
    return points


def _materialize(a, key, host, flag_value, label, field):
    """URL 直接用；本地文件先传平台临时地址（上传不计费，0 点/次）。"""
    v = flag_value
    if re.match(r"^https?://", v or ""):
        return v
    if not os.path.isfile(v):
        raise Fail("usage", "%s 既不是 URL 也不是存在的文件：%s" % (label, v), EXIT_USAGE)
    if not getattr(a, "upload", False):
        raise Fail("usage",
                   "%s 是本地文件。加 --upload 先传到平台临时地址（上传不计费），"
                   "或自己换成公网 URL。" % label, EXIT_USAGE)
    if getattr(a, "dry_run", False):
        return "<dry-run：本地文件 %s 未上传>" % os.path.basename(v)
    say("正在上传 %s（%s，不计费）…" % (label, os.path.basename(v)))
    st, txt = http_multipart(host + API_PREFIX + "/upload", key, {}, [("file", v)])
    if st not in (200, 201):
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    d = jloads(txt) or {}
    urls = []
    find_media(d, urls)
    if not urls:
        cand = d.get("data") if isinstance(d, dict) else None
        if isinstance(cand, dict):
            for k in ("url", "file_url", "path"):
                if isinstance(cand.get(k), str) and cand[k].startswith("http"):
                    urls.append(cand[k])
    if not urls:
        raise Fail("call", "上传返回里没有 url：%s" % txt.replace("\n", " ")[:300], EXIT_CALL)
    say("  已上传：%s（24 小时内有效）" % urls[0])
    return urls[0]


def _poll(a, key, host, task_id):
    deadline = time.time() + max(60, a.timeout)
    interval = max(2, a.interval)
    last = None
    while True:
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + str(task_id), key,
                            timeout=60)
        d = jloads(txt) or {}
        status, node = dig_task(d)
        if status != last:
            if not a.json:
                say("  [%s] %s" % (time.strftime("%H:%M:%S"), status or "?"))
            last = status
        if status and str(status).lower() in TERMINAL_OK:
            return True, status, node, d, txt
        if status and str(status).lower() in TERMINAL_BAD:
            return False, status, node, d, txt
        if time.time() >= deadline:
            raise Fail("call",
                       "等待超时（%d 秒），任务可能仍在跑。用 `status --task-id %s` 继续查。"
                       % (a.timeout, task_id), EXIT_CALL)
        time.sleep(interval)


def _save(url, outdir, prefix, ext="mp4"):
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "%s.%s" % (prefix, ext))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=300) as x:
            raw = x.read()
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "下载失败：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    open(p, "wb").write(raw)
    return p


def _submit_flow(a, key, host, app, body, label, points):
    """talk / drive / dub 共用：干跑 → 提交 → 轮询 → 落地。"""
    url = host + API_PREFIX + "/apps/%s/submit" % app
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "app": app, "url": url,
               "requestBody": body, "estimatedPoints": points, "yuan": yuan(points)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (points, yuan(points)))
        return 0

    say("正在提交%s（%s）…" % (label, app))
    st, txt = http_json("POST", url, key, body, timeout=120)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    if not ok or st not in (200, 201):
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "app": app,
                    "label": label, "http": st, "error": msg or err_text(st, txt),
                    "billedPoints": 0})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg or err_text(st, txt)), EXIT_CALL)

    task_id = data.get("task_id") if isinstance(data, dict) else None
    frozen = data.get("frozen_points") if isinstance(data, dict) else None
    if not task_id:
        raise Fail("call", "提交成功但没有拿到 task_id：%s" % txt.replace("\n", " ")[:300],
                   EXIT_CALL)
    if not a.json:
        say("  task_id = %s%s" % (task_id, ("（预扣 %s 点）" % frozen) if frozen else ""))

    if a.no_wait:
        out = {"ok": True, "app": app, "taskId": task_id, "frozenPoints": frozen,
               "status": "submitted", "estimatedPoints": points}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("已提交，不等待结果")
        print("  应用：%s（%s）" % (app, label))
        print("  task_id：%s" % task_id)
        print("  继续查：python3 scripts/run.py status --task-id %s" % task_id)
        return 0

    done, status, node, d2, txt2 = _poll(a, key, host, task_id)
    urls = find_media(node)
    if not urls:
        urls = find_media(d2)
    billed = find_points(d2)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(done and urls),
           "app": app, "label": label, "taskId": task_id, "status": status,
           "urls": urls, "points": billed if billed is not None else points}
    ledger_add(rec)

    files = []
    if done and urls and a.save:
        try:
            files.append(_save(urls[0], a.outdir, "%s-%s" % (app, task_id)))
        except Fail as e:
            say("  （下载没成功：%s）" % e.message)

    out = {"ok": bool(done and urls), "app": app, "taskId": task_id, "status": status,
           "urls": urls, "files": files,
           "points": billed if billed is not None else points,
           "estimatedPoints": points}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if done else EXIT_CALL

    if not done:
        say("任务失败（status=%s）：%s" % (status, json.dumps(node, ensure_ascii=False)[:400]))
        return EXIT_CALL
    print("完成（%s）" % status)
    print("  task_id：%s" % task_id)
    if billed is not None:
        print("  实际点数：%.2f 点（%.2f 元）" % (billed, yuan(billed)))
    for u in urls:
        print("  成片：%s" % u)
    for p in files:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    return 0


# ───────────────────────── 子命令：免费 ─────────────────────────
def cmd_catalog(a, key, host):
    out = {
        "ok": True,
        "talk": {"app": APP_TALK, "driving": "文案（text 模式）", "pointsPerSecond": TALK_POINTS_PER_SEC,
                 "minPoints": TALK_MIN_POINTS, "quality": QUALITIES, "defaultQuality": "standard",
                 "params": ["image_url", "audio_url（参考音色）", "content（文案）", "quality", "prompt"]},
        "drive": {"app": APP_DRIVE, "driving": "音频（全驱动）", "ratesPerSecond": DRIVE_RATES,
                  "params": ["file_url", "ref_file_url", "duration", "mode", "prompt"]},
        "dub": {"app": APP_DUB, "driving": "已有视频 + 新音频", "upstreamPerSecond": DUB_UPSTREAM_RATE,
                "markup": DUB_MARKUP,
                "pointsPerSecond": dict((k, round(v * DUB_MARKUP, 2))
                                        for k, v in DUB_UPSTREAM_RATE.items()),
                "params": ["video_url", "audio_url", "model", "fps", "video_params"]},
        "query": {"task": "GET /api/v1/tasks/{task_id}",
                  "appLevel": "POST /api/v1/apps/{code}/query"},
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("数字人口播台 · 三种做法对照（1 元 = 100 点）")
    print()
    print("  ① talk   文案驱动   pic_lipsync   15 点/秒（单笔按 50 点下限预估）")
    print("     一段文案 + 一张图 + 一段参考音色 → 直接出人说话的视频")
    print("     参数：image_url · audio_url（参考音色，必填）· content · quality(standard/fast/max)")
    print()
    print("  ② drive  全驱动     image_human   10 / 15 / 30 / 60 点/输入秒")
    print("     快速 10 · 标准 15 · 2K 30 · 4K 60，按**输入音频秒数**计费")
    print("     参数：file_url · ref_file_url · duration（秒）· mode（四档，必填）· prompt")
    print()
    print("  ③ dub    已有视频   lipsync       上游实际点数 ×3")
    print("     xiaojiayu1.0 2.7 点/秒 · 2.0 13.5 点/秒 · 3.0 13.5 点/秒")
    print("     参数：video_url · audio_url · model · fps · video_params")
    print()
    print("  三个应用都只有 submit + query 两个接口；任务状态统一查 GET /api/v1/tasks/{id}")
    print()
    print("  下一步：python3 scripts/run.py cost --way talk --content \"你的文案\"")
    print("           python3 scripts/run.py cost --way drive --mode 4k --duration 30")
    return 0


def cmd_cost(a, key, host):
    way = a.way
    if way == "talk":
        if not a.content and not a.seconds:
            raise Fail("usage", "talk 要算钱，给 --content \"文案\" 或 --seconds 秒数", EXIT_USAGE)
        sec = talk_seconds(a)
        pts = talk_points(sec)
        detail = "文案 %d 字 ÷ 4.5 字/秒 ≈ %.1f 秒" % (
            len(re.sub(r"\s+", "", a.content or "")), sec) if a.content else "给定时长 %.1f 秒" % sec
        basis = "15 点/秒（上游实扣 3 点/秒 ×5；quality 默认 standard）"
        extra = "单笔按 50 点下限预估（公开文档写的保底价）"
    elif way == "drive":
        if not a.mode:
            raise Fail("usage",
                       "drive 要算钱必须显式给 --mode fast|standard|2k|4k（本包不替你猜档位）",
                       EXIT_USAGE)
        if not a.duration:
            raise Fail("usage", "drive 要算钱必须给 --duration 秒数（输入音频时长）", EXIT_USAGE)
        sec = float(a.duration)
        pts = drive_points(a.mode, sec)
        detail = "输入音频 %.1f 秒 × %d 点/秒（%s 档）" % (sec, DRIVE_RATES[a.mode], a.mode)
        basis = "10 / 15 / 30 / 60 点/输入秒（fast / standard / 2k / 4k）"
        extra = "带上 duration 时价格被费率卡锁死 = 费率 × 秒数，预算可以精确到点"
    elif way == "dub":
        if not a.seconds:
            raise Fail("usage", "dub 要算钱必须给 --seconds 秒数（音频或视频时长）", EXIT_USAGE)
        sec = float(a.seconds)
        pts = dub_points(a.model, sec)
        detail = "%.1f 秒 × 上游 %.2f 点/秒 × %d = %d 点" % (
            sec, DUB_UPSTREAM_RATE[a.model], DUB_MARKUP, pts)
        basis = "上游实际点数 ×3（上游费率 %s 点/秒）" % DUB_UPSTREAM_RATE[a.model]
        extra = "lipsync 按上游实际点数结算，这里给的是同口径预估"
    else:
        raise Fail("usage", "未知的 --way：%s（talk / drive / dub）" % way, EXIT_USAGE)

    out = {"ok": True, "way": way, "seconds": sec, "points": pts, "yuan": yuan(pts),
           "basis": basis, "detail": detail, "budget": a.budget,
           "overBudget": pts > a.budget}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本 · %s" % way)
    print("  %s" % detail)
    print("  = **%d 点 = %.2f 元**" % (pts, yuan(pts)))
    print("  口径：%s" % basis)
    print("  %s" % extra)
    if pts > a.budget:
        print()
        print("  ⚠ 已超过 --budget %d 点，真实执行会退 5（一个请求都不发）" % a.budget)
    return 0


def cmd_doctor(a, key, host):
    """只跑**四个免费 GET**：apps / pricing / tasks / balance。

    为什么一个 submit 探针都不发 —— 实测：应用层 submit 会**先同步预扣再验参**，
    缺必填的请求也会产生「冻结/预扣 −N → 退款 +N」的一对流水（净额 0，但钱包被短暂动过）。
    自检不该动钱包，所以这里只用定价表证明三个端点已配价。
    """
    checks = []

    # ① Key + 应用目录（定价表：/api/v1/apps cost:0，免费）
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    apps = data if isinstance(data, list) else (
        (data or {}).get("apps") if isinstance(data, dict) else None)
    checks.append(("Key 有效性 + 应用目录可达", st == 200 and ok,
                   "HTTP %s %s · %s 个应用" % (st, msg[:20],
                                               len(apps) if isinstance(apps, list) else "?")))

    # ② 定价表（免费，裸对象不套 code/data）→ 三个 submit 端点是否已配价
    st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing?type=app_api&app_code=%s"
                          "&api_code=submit" % APP_DRIVE, key, timeout=60)
    d2 = jloads(txt2) or {}
    rows = d2.get("pricing") if isinstance(d2.get("pricing"), dict) else {}
    want = ["/api/v1/apps/%s/submit" % x for x in (APP_TALK, APP_DRIVE, APP_DUB)]
    missing = [p for p in want if p not in rows]
    checks.append(("三个 submit 端点已在网关配价", (not missing) and bool(rows),
                   "缺 %s" % "、".join(missing) if missing
                   else "命中 %d 条计价规则" % len(rows)))

    # ③ image_human 四档速率卡
    ih = rows.get("/api/v1/apps/image_human/submit") or {}
    rates = ih.get("modelRates") or {}
    live = dict((k, (v or {}).get("*")) for k, v in rates.items()) if rates else {}
    match = bool(live) and all(live.get(k) == v for k, v in DRIVE_RATES.items())
    checks.append(("速率卡一致（image_human 10/15/30/60）", match,
                   ("live=%s" % json.dumps(live, ensure_ascii=False)) if live
                   else "HTTP %s 没读到 modelRates" % st2))

    # ④ lipsync ×3 / pic_lipsync ×5
    ls = rows.get("/api/v1/apps/lipsync/submit") or {}
    talks = rows.get("/api/v1/apps/pic_lipsync/submit") or {}
    checks.append(("速率卡一致（lipsync ×3 / pic_lipsync ×5）",
                   ls.get("markupPercent") == 200 and talks.get("markupPercent") == 400,
                   "lipsync markup=%s · pic_lipsync markup=%s"
                   % (ls.get("markupPercent"), talks.get("markupPercent"))))

    # ⑤ 任务查询线（免费）：一个不存在的 id 应回「任务不存在」，而不是 404
    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/0", key, timeout=60)
    d4 = jloads(txt4) or {}
    ok4 = st4 == 200 and "任务不存在" in str(d4.get("msg") or "")
    checks.append(("任务查询 GET /api/v1/tasks/{id} 可用", ok4,
                   "HTTP %s %s" % (st4, str(d4.get("msg") or txt4.replace("\n", " "))[:40])))

    # ⑥ 余额可读（免费）
    st5, txt5 = http_json("GET", host + "/user/balance", key, timeout=60)
    d5 = jloads(txt5) or {}
    pts = d5.get("available_points") or d5.get("points")
    checks.append(("余额可读", st5 == 200 and pts is not None,
                   "%.2f 点（%.2f 元）" % (float(pts), yuan(float(pts)))
                   if pts is not None else "HTTP %s" % st5))

    out = {"ok": all(c[1] for c in checks),
           "freeSurface": ["GET /api/v1/apps", "GET /api/v1/pricing",
                           "GET /api/v1/tasks/{task_id}", "GET /user/balance"],
           "endpoints": ["POST %s/apps/%s/submit" % (API_PREFIX, APP_TALK),
                         "POST %s/apps/%s/submit" % (API_PREFIX, APP_DRIVE),
                         "POST %s/apps/%s/submit" % (API_PREFIX, APP_DUB)],
           "rates": {"talk": TALK_POINTS_PER_SEC, "drive": DRIVE_RATES,
                     "dub": dict((k, round(v * DUB_MARKUP, 2))
                                 for k, v in DUB_UPSTREAM_RATE.items())},
           "balance": pts,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（全程免费：四个只读 GET，一个 submit 都不发）")
    print()
    for n, o, dd in checks:
        print("  %s %-36s %s" % ("√" if o else "×", n, dd))
    print()
    print("  三个入口：talk pic_lipsync · drive image_human · dub lipsync")
    print("  价目：talk 15 点/秒 · drive 10/15/30/60 点/秒 · dub 上游×3")
    print("  坑：image_human 不传 mode 会「出片按 standard、收钱按 fast」，本包 --mode 必填")
    print("  实测记一笔：应用层 submit 会先同步预扣再验参，所以自检只用定价表证明端点已配价")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 子命令：三路 ─────────────────────────
def cmd_talk(a, key, host):
    if not a.image:
        raise Fail("usage", "必须给 --image（人物图片 URL，或本地文件 + --upload）", EXIT_USAGE)
    if not a.voice_ref:
        raise Fail("usage",
                   "text 模式仍需 --voice-ref（参考音色，3–10 秒单人清晰人声）。"
                   "文案驱动省掉的是录音，不是音色样本。", EXIT_USAGE)
    if not a.content:
        raise Fail("usage", "必须给 --content（要念的文案）", EXIT_USAGE)
    if a.quality not in QUALITIES:
        raise Fail("usage", "--quality 只能是 %s" % " / ".join(QUALITIES), EXIT_USAGE)

    sec = talk_seconds(a)
    pts = talk_points(sec)
    _gate(a, pts, "文案 %d 字 ≈ %.1f 秒口播" % (
        len(re.sub(r"\s+", "", a.content)), sec))

    image_url = _materialize(a, key, host, a.image, "--image", "image_url")
    audio_url = _materialize(a, key, host, a.voice_ref, "--voice-ref", "audio_url")
    body = {"image_url": image_url, "audio_url": audio_url, "content": a.content,
            "mode": "text", "quality": a.quality,
            "model": a.model}
    if a.prompt:
        body["prompt"] = a.prompt
    return _submit_flow(a, key, host, APP_TALK, body, "文案驱动口播", pts)


def cmd_drive(a, key, host):
    if not a.image:
        raise Fail("usage", "必须给 --image（人物图片 URL，或本地文件 + --upload）", EXIT_USAGE)
    if not a.audio:
        raise Fail("usage", "必须给 --audio（驱动音频 URL，或本地文件 + --upload）", EXIT_USAGE)
    if not a.mode:
        raise Fail("usage",
                   "必须显式给 --mode fast|standard|2k|4k。\n"
                   "不传 mode 时：出片按 standard、收钱按 fast（15 vs 10 点/秒），"
                   "档位与账单对不上，所以本包不替你猜。", EXIT_USAGE)
    if not a.duration:
        raise Fail("usage",
                   "必须给 --duration（输入音频的**真实秒数**）。\n"
                   "带上它价格才被费率卡锁死 = 费率 × 秒数，预算才能精确到点；"
                   "不给则由平台按上游冻结点计费，估不准。", EXIT_USAGE)

    pts = drive_points(a.mode, a.duration)
    _gate(a, pts, "输入 %.1f 秒 × %s 档 %d 点/秒" % (
        float(a.duration), a.mode, DRIVE_RATES[a.mode]))

    file_url = _materialize(a, key, host, a.image, "--image", "file_url")
    ref_url = _materialize(a, key, host, a.audio, "--audio", "ref_file_url")
    body = {"file_url": file_url, "ref_file_url": ref_url,
            "duration": float(a.duration), "mode": a.mode}
    if a.resolution:
        body["resolution"] = a.resolution
    if a.prompt:
        body["prompt"] = a.prompt
    return _submit_flow(a, key, host, APP_DRIVE, body, "%s 档全驱数字人" % a.mode, pts)


def cmd_dub(a, key, host):
    if not a.video:
        raise Fail("usage", "必须给 --video（已有视频 URL，或本地文件 + --upload）", EXIT_USAGE)
    if not a.audio:
        raise Fail("usage", "必须给 --audio（新配音音频 URL，或本地文件 + --upload）", EXIT_USAGE)
    if a.model not in DUB_UPSTREAM_RATE:
        raise Fail("usage", "--model 只能是 %s" % " / ".join(DUB_UPSTREAM_RATE), EXIT_USAGE)
    if not a.seconds:
        raise Fail("usage",
                   "必须给 --seconds（音频/视频秒数）—— lipsync 按上游实际点数结算，"
                   "没有时长就算不出钱。", EXIT_USAGE)

    pts = dub_points(a.model, a.seconds)
    _gate(a, pts, "%.1f 秒 × %s（上游 %.2f 点/秒 ×%d）" % (
        float(a.seconds), a.model, DUB_UPSTREAM_RATE[a.model], DUB_MARKUP))

    video_url = _materialize(a, key, host, a.video, "--video", "video_url")
    audio_url = _materialize(a, key, host, a.audio, "--audio", "audio_url")
    body = {"video_url": video_url, "audio_url": audio_url, "model": a.model}
    if a.fps:
        body["fps"] = a.fps
    if a.video_params:
        vp = jloads(a.video_params)
        if vp is None:
            raise Fail("usage", "--video-params 要是 JSON 对象，例如 '{\"watermark\": false}'",
                       EXIT_USAGE)
        body["video_params"] = vp
    return _submit_flow(a, key, host, APP_DUB, body, "视频对口型", pts)


# ───────────────────────── 子命令：查 / 台账 ─────────────────────────
def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    if a.app:
        st, txt = http_json("POST", host + API_PREFIX + "/apps/%s/query" % a.app, key,
                            {"task_id": a.task_id}, timeout=90)
    else:
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + str(a.task_id), key,
                            timeout=90)
    d = jloads(txt) or {}
    ok, msg, data = envelope(d)
    if not ok:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, msg or err_text(st, txt)), EXIT_CALL)
    status, node = dig_task(d)
    urls = find_media(node)
    if not urls:
        urls = find_media(d)
    billed = find_points(d)
    files = []
    if a.save and urls:
        files.append(_save(urls[0], a.outdir, "dh-%s" % a.task_id))
    out = {"ok": True, "taskId": a.task_id, "status": status, "urls": urls,
           "files": files, "points": billed, "raw": node}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (status or "未知"))
    if billed is not None:
        print("  点数：%.2f 点（%.2f 元）" % (billed, yuan(billed)))
    for u in urls:
        print("  成片：%s" % u)
    for p in files:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    if not urls and str(status).lower() in TERMINAL_OK:
        print("  提示：刚 completed 时结果地址偶尔是空串，隔几秒再查一次")
    return 0


def cmd_log(a, key, host):
    arr = ledger_load()
    entries = arr[-a.limit:] if a.limit else arr
    out = {"ok": True, "count": len(arr), "entries": entries}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(entries), len(arr)))
    if not arr:
        print("  还没有记录。跑一次 talk / drive / dub 就会写进来。")
        return 0
    total = 0.0
    for e in entries:
        try:
            total += float(e.get("points") or 0)
        except (TypeError, ValueError):
            pass
        print("  %s  %-5s %-12s %s  %s 点" % (
            e.get("at") or "-", "OK" if e.get("ok") else "FAIL",
            e.get("app") or "-", e.get("status") or e.get("error") or "-",
            e.get("points") if e.get("points") is not None else "-"))
    print("  本页合计：%.2f 点（%.2f 元）" % (total, yuan(total)))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 数字人口播台（一张图 + 一段话 → 一个会说话、会对口型的人）",
        epilog="端点：POST %s/api/v1/apps/{pic_lipsync|image_human|lipsync}/submit · "
               "GET %s/api/v1/tasks/{task_id}" % (DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=500, help="点数上限（单位：点，默认 500，1 元 = 100 点）")
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="三种做法对照（免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱（免费）", allow_abbrev=False)
    p.add_argument("--way", default="talk", choices=["talk", "drive", "dub"],
                   help="算哪一路（默认 talk）")
    p.add_argument("--content", help="talk：要念的文案（按 4.5 字/秒估时长）")
    p.add_argument("--seconds", type=float, help="talk/dub：直接给秒数")
    p.add_argument("--duration", type=float, help="drive：输入音频秒数")
    p.add_argument("--mode", choices=DRIVE_MODES,
                   help="drive：档位 fast/standard/2k/4k（必填，本包不替你猜）")
    p.add_argument("--model", default="xiaojiayu1.0",
                   choices=list(DUB_UPSTREAM_RATE), help="dub：数字人模型")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 三个端点 / 速率卡（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_common(p):
        p.add_argument("--image", help="人物图片：公网 URL，或本地文件 + --upload")
        p.add_argument("--audio", help="驱动音频：公网 URL，或本地文件 + --upload")
        p.add_argument("--video", help="已有视频：公网 URL，或本地文件 + --upload")
        p.add_argument("--prompt", help="人物动作、表情、画面风格提示词（可选）")
        p.add_argument("--upload", action="store_true",
                       help="本地文件先传平台临时地址（上传不计费，0 点/次）")
        p.add_argument("--outdir", default=".", help="成片保存目录（配合 --save）")
        p.add_argument("--save", action="store_true", help="完成后把成片下载到 --outdir")
        p.add_argument("--no-wait", action="store_true", help="只提交，不等待结果")
        p.add_argument("--timeout", type=int, default=900, help="等待上限秒数（默认 900）")
        p.add_argument("--interval", type=int, default=5, help="轮询间隔秒数（默认 5）")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("talk", help="文案驱动口播（pic_lipsync mode=text，15 点/秒）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--voice-ref", help="参考音色音频：3–10 秒单人清晰人声（text 模式必填）")
    p.add_argument("--content", help="要念的文案")
    p.add_argument("--quality", default="standard", choices=QUALITIES,
                   help="standard（默认）/ fast / max（档位真名是 quality）")
    p.add_argument("--model", default="super-lipsync-pro", help="图片数字人模型")
    p.set_defaults(fn=cmd_talk)

    p = sub.add_parser("drive", help="全驱动数字人（image_human，按输入秒计费）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--mode", required=True, choices=DRIVE_MODES,
                   help="档位 fast 10 / standard 15 / 2k 30 / 4k 60 点/输入秒（必填；"
                        "schema 默认 standard、计费卡默认 fast，不传会导致出片档位与计费档位不一致）")
    p.add_argument("--duration", type=float, help="输入音频的真实秒数（必填，锁死价格）")
    p.add_argument("--resolution", choices=["2k", "4k"], help="兼容别名，等价于同档 mode")
    p.set_defaults(fn=cmd_drive)

    p = sub.add_parser("dub", help="已有视频对口型（lipsync，上游实际×3）",
                       allow_abbrev=False)
    add_common(p)
    p.add_argument("--model", default="xiaojiayu1.0", choices=list(DUB_UPSTREAM_RATE),
                   help="xiaojiayu1.0（2.7 点/秒）/ 2.0 / 3.0（13.5 点/秒）")
    p.add_argument("--seconds", type=float, help="音频或视频秒数（必填，用来算钱）")
    p.add_argument("--fps", help="输出帧率（可选，如 25）")
    p.add_argument("--video-params", help='video_params JSON，例如 \'{"watermark": false}\'')
    p.set_defaults(fn=cmd_dub)

    p = sub.add_parser("status", help="查任务", allow_abbrev=False)
    p.add_argument("--task-id", help="提交返回的 task_id")
    p.add_argument("--app", choices=[APP_TALK, APP_DRIVE, APP_DUB],
                   help="改用应用级查询 POST /apps/{code}/query")
    p.add_argument("--save", action="store_true", help="把成片下载到 --outdir")
    p.add_argument("--outdir", default=".", help="成片保存目录")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近几条（默认 20）")
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


LOCAL_CMDS = (cmd_catalog, cmd_cost, cmd_log)


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key, host = load_conf(a.key, a.host)
    if not key and a.fn not in LOCAL_CMDS:
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
    except KeyboardInterrupt:
        raise


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
