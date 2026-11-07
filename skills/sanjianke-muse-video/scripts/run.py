#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · Muse Video 出片台

走 api.a7w.cn 的 **muse-video**（Meta Muse 视频模型）：**720P、带声音、4–180 秒**，
接口与 OpenAI 视频接口一致（`POST /api/v1/videos`），异步三步：提交 → 查询 → 下载。

## 权威规格（取自网关文档 /docs/muse-video-xt）

  接口根地址   https://api.a7w.cn/api/v1
  提交任务     POST /api/v1/videos           （兼容 /api/v1/videos/generations）
  查询任务     GET  /api/v1/videos/{id}
  模型名       muse-video
  价格         **11 点/秒（¥0.11）**，按**请求**秒数计费
  时长         4–180 秒；出片 5/6/8/10 或 15–180 的 5 的倍数
  尺寸         1280x720（横，默认）/ 720x1280（竖）—— **不支持方形，不支持 1080P**
  图片         input_reference（1 张＝首帧）或 images[]（最多 4 张，第 1 张＝开头）
  成品         720P MP4，**带声音**；平台**只保留 24 小时**

## 这个包替你处理的四件事

  1. **「按请求秒数计费」不是笔糊涂账** —— `cost --seconds 30` 先报 330 点，`--budget` 兜底
  2. **时长会「凑档」但不多收** —— 填 17 秒出 20 秒，只收 17 秒；本包会把这个差价标出来
  3. **等待可能很久**（61–180 秒要 8–15 分钟）—— 默认不等完，给你 task id；
     要等就 `--wait`，但**超时后绝不自动重提**（重提会再扣一次钱）
  4. **成品只有 24 小时** —— `--wait` 成功就立刻下载，并打印过期时间

## 子命令

  models   视频模型清单（免费）
  cost     先算钱（免费，11 点/秒）
  doctor   自检 Key / 端点 / 模型（免费，不扣费）
  gen      提交任务（要 --yes）；--wait 则等到完成并下载
  status   查任务状态
  wait     等一个任务完成并下载
  log      本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --seconds 10
  python3 scripts/run.py gen --prompt "金色的枫叶在微风中飘落，阳光穿过树梢，电影感" --seconds 5 --yes
  python3 scripts/run.py gen --prompt "..." --seconds 8 --size 720x1280 --first-frame girl.jpg --yes --wait
  python3 scripts/run.py status task_xxxx
  python3 scripts/run.py wait task_xxxx --outdir .

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题可加技术微信 9872659。
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
import urllib.parse
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
DEFAULT_MODEL = "muse-video"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
POINTS_PER_SECOND = 11
MIN_SEC, MAX_SEC = 4, 180
SIZES = ("1280x720", "720x1280")
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "muse-video-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1
EXIT_TIMEOUT = 7

UA = "sanjianke-muse-video/%s" % VERSION


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(m):
    sys.stderr.write(m + "\n")


def load_conf(explicit_key=None, explicit_host=None):
    key = (explicit_key or "").strip() or \
        (os.environ.get("A7W_API_KEY") or "").strip() or None
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


def http(method, url, key, body=None, timeout=120):
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


def http_multipart(url, key, fields, file_path, timeout=180):
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in fields.items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    fn = os.path.basename(file_path)
    ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
    buf.write(("--%s\r\nContent-Disposition: form-data; name=\"input_reference\"; "
               "filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
               % (boundary, fn, ctype)).encode("utf-8"))
    buf.write(open(file_path, "rb").read())
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
            s = " · ".join([x for x in (e.get("message"), e.get("code")) if x])
            if s:
                return s[:300]
        for k in ("message", "msg", "detail"):
            if d.get(k):
                return str(d[k])[:300]
    return txt.replace("\n", " ")[:240]


def billed_seconds(sec):
    """文档：5/6/8/10，以及 15–180 之间 5 的倍数；其他值也能用，按**填的**收钱。"""
    if sec <= 10:
        return {4: 5, 5: 5, 6: 6, 7: 8, 8: 8, 9: 10, 10: 10}.get(sec, sec)
    return ((sec + 4) // 5) * 5


def check_seconds(sec):
    if sec is None:
        return 4, ""
    if not isinstance(sec, int):
        return None, "seconds 必须是整数（文档：不支持小数，如 8.5）"
    if sec < MIN_SEC or sec > MAX_SEC:
        return None, "seconds 只支持 %d 到 %d 的整数" % (MIN_SEC, MAX_SEC)
    return sec, ""


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


# ───────────────────────── 子命令 ─────────────────────────
def cmd_models(a, key, host):
    st, txt = http("GET", host + API_PREFIX + "/models", key)
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
    vids = [it for it in items if isinstance(it, dict) and it.get("type_code") == "video"]
    rows = [{"model_code": it.get("model_code"),
             "model_name": it.get("model_name"),
             "参考图上限": it.get("max_reference_images"),
             "说明": (it.get("description") or "")[:44]} for it in vids]
    out = {"ok": True, "count": len(rows), "models": rows}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("api.a7w.cn 在架视频模型（%d 个）" % len(rows))
    print()
    print("  %-26s %-22s %-7s %s" % ("model_code", "名称", "参考图", "说明"))
    print("  " + "-" * 92)
    for r in rows:
        mark = "  ← 本包默认" if r["model_code"] == DEFAULT_MODEL else ""
        print("  %-26s %-22s %-7s %s%s" % (r["model_code"], (r["model_name"] or "")[:20],
                                           r["参考图上限"], r["说明"][:30], mark))
    return 0


def cmd_cost(a, key, host):
    sec, why = check_seconds(a.seconds)
    if sec is None:
        raise Fail("usage", why, EXIT_USAGE)
    total = sec * POINTS_PER_SECOND
    got = billed_seconds(sec)
    out = {"ok": True, "requestedSeconds": sec, "billedSeconds": sec,
           "pointsPerSecond": POINTS_PER_SECOND, "totalPoints": total,
           "yuan": round(total / 100.0, 2),
           "actualDurationSeconds": got,
           "note": "按**请求**秒数计费；凑档出片不额外收费"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本")
    print("  模型：%s（11 点/秒）" % a.model)
    print("  时长：%d 秒 × %d 点 = **%d 点 = ¥%.2f**" % (sec, POINTS_PER_SECOND, total,
                                                     total / 100.0))
    if got != sec:
        print("  出片：约 %d 秒（凑档不加钱，仍只收 %d 秒）" % (got, sec))
    print()
    print("  秒数价目（文档原文）：")
    for s in (4, 5, 6, 8, 10, 15, 30, 60):
        print("    %3d 秒  →  %4d 点  ¥%.2f" % (s, s * POINTS_PER_SECOND,
                                              s * POINTS_PER_SECOND / 100.0))
    print()
    print("  失败全额退回；参数错（秒数/尺寸/图片不合规）直接 400，不创建任务、不扣费。")
    return 0


def cmd_doctor(a, key, host):
    checks = []
    st, txt = http("GET", host + API_PREFIX + "/models", key)
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
    # 提交端点：**空 body 不够** —— 它会先抱怨 model 缺失（"Model name not specified"）。
    # 带上合法 model 才会走到 prompt 校验。
    # ⚠️ 这条路的错误结构有两套：缺 model 时是 `{"error":{"message":…}}`，
    #    缺 prompt 时是**顶层** `{"code":"plugin_request_invalid","message":"field prompt is required"}`。
    st2, txt2 = http("POST", host + API_PREFIX + "/videos", key,
                     {"model": DEFAULT_MODEL})
    d2 = jloads(txt2) or {}
    e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
    msg2 = (e2.get("message") or d2.get("message") or d2.get("msg") or "")[:70]
    ok2 = st2 == 400 and "prompt" in msg2.lower()
    checks.append(("提交端点可用（400 缺 prompt 即正确）", ok2,
                   "HTTP %s %s" % (st2, msg2[:52])))
    out = {"ok": all(c[1] for c in checks),
           "endpoint": host + API_PREFIX + "/videos",
           "pointsPerSecond": POINTS_PER_SECOND,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（不扣费：只读接口 + 空 body 触发参数校验）")
    print()
    for n, o, d in checks:
        print("  %s %-34s %s" % ("√" if o else "×", n, d))
    print()
    print("  端点：%s" % out["endpoint"])
    print("  单价：%d 点/秒（¥%.2f/秒）· 时长 4–180 秒 · 只出 720P" %
          (POINTS_PER_SECOND, POINTS_PER_SECOND / 100.0))
    return 0 if out["ok"] else EXIT_GATE


def _submit(a, key, host):
    sec, why = check_seconds(a.seconds)
    if sec is None:
        raise Fail("usage", why, EXIT_USAGE)
    if not a.prompt:
        raise Fail("usage", "必须给 --prompt", EXIT_USAGE)
    if len(a.prompt) > 4000:
        raise Fail("usage", "prompt 不能超过 4000 个字（当前 %d）" % len(a.prompt), EXIT_USAGE)
    if a.size not in SIZES:
        raise Fail("usage", "只支持横屏 1280x720 或竖屏 720x1280（你给的是 %s）" % a.size,
                   EXIT_USAGE)
    refs = list(a.ref or [])
    if a.first_frame:
        if refs:
            raise Fail("usage", "首帧用 --first-frame；多图参考用 --ref。两者别同时给"
                       "（文档：多张图全放进 images，不要再另传 input_reference）", EXIT_USAGE)
        refs = [a.first_frame]
    if len(refs) > 4:
        raise Fail("usage", "参考图最多 4 张（当前 %d）" % len(refs), EXIT_USAGE)

    cost = sec * POINTS_PER_SECOND
    if cost > a.budget:
        raise Fail("budget", "预计 %d 点超过 --budget %d 点。调大 --budget 或减少 --seconds。"
                   % (cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实出片并预扣约 %d 点（¥%.2f），失败才全额退回。"
                   "确认请加 --yes。" % (cost, cost / 100.0), EXIT_CONFIRM)
    return sec, refs, cost


def cmd_gen(a, key, host):
    sec, refs, cost = _submit(a, key, host)
    url = host + API_PREFIX + "/videos"
    body = {"model": a.model, "prompt": a.prompt, "seconds": str(sec), "size": a.size}

    if a.dry_run:
        preview = dict(body)
        if refs:
            preview["images"] = ["<本地图 → data URL>" if not r.startswith(
                ("http", "data:")) else r for r in refs]
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": preview,
               "estimatedPoints": cost, "yuan": round(cost / 100.0, 2),
               "actualDurationSeconds": billed_seconds(sec)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：%s" % url)
        print("  请求：%s" % json.dumps(preview, ensure_ascii=False))
        print("  预估：%d 点（¥%.2f）· 出片约 %d 秒" %
              (cost, cost / 100.0, billed_seconds(sec)))
        return 0

    say("正在提交（%s，%d 秒，%s）…" % (a.model, sec, a.size))
    t0 = time.time()
    if a.first_frame and os.path.isfile(a.first_frame):
        # 本地首帧文件 → multipart（文档支持）
        fields = {"model": a.model, "prompt": a.prompt, "seconds": str(sec), "size": a.size}
        st, txt = http_multipart(url, key, fields, a.first_frame, timeout=180)
    else:
        if refs:
            body["images"] = [to_ref(r) for r in refs]
        st, txt = http("POST", url, key, body, timeout=max(120, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "http": st,
                    "error": msg, "seconds": sec})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)

    vid = d.get("id") or d.get("task_id") or ""
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "id": vid,
           "model": a.model, "seconds": sec, "size": a.size, "refs": len(refs),
           "reservedPoints": cost, "submitSeconds": round(dt, 1)}
    ledger_add(rec)

    if a.json and not a.wait:
        print(json.dumps({"ok": True, "id": vid, "status": d.get("status"),
                          "seconds": sec, "size": a.size, "reservedPoints": cost,
                          "next": "用 `wait %s` 或 `status %s` 跟踪，别重复提交" % (vid, vid)},
                         ensure_ascii=False))
        return 0
    if not a.wait:
        print("已提交（%.1fs）" % dt)
        print("  任务 ID：%s" % vid)
        print("  状态：%s" % d.get("status"))
        print("  预扣：%d 点（¥%.2f）—— 失败全额退回" % (cost, cost / 100.0))
        print()
        print("  这是异步任务，**不会自动完成下载**。跟踪它：")
        print("    python3 scripts/run.py status %s" % vid)
        print("    python3 scripts/run.py wait %s --outdir ." % vid)
        print()
        print("  ⚠️ **不要重复提交** —— 重提会再扣一次钱。")
        return 0

    # --wait：轮询到完成
    say("已提交 %s，开始等待（每 %d 秒查一次，上限 %d 分钟）…"
        % (vid, a.every, a.limit // 60))
    return _wait_and_download(a, key, host, vid, a.every, a.limit)


def _wait_and_download(a, key, host, vid, every, limit):
    url = "%s%s/videos/%s" % (host, API_PREFIX, urllib.parse.quote(vid))
    end = time.time() + limit
    last = None
    while time.time() < end:
        st, txt = http("GET", url, key, timeout=60)
        if st == 404:
            raise Fail("call", "任务不存在（task_not_exist）：%s" % vid, EXIT_CALL)
        if st >= 500:
            time.sleep(every)
            continue
        if st != 200:
            raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
        s = jloads(txt) or {}
        status = s.get("status")
        prog = s.get("progress")
        if status != last:
            say("  状态：%s（进度 %s%%）" % (status, prog))
            last = status
        if status == "completed":
            return _finish(a, s, vid)
        if status == "failed":
            e = s.get("error") or {}
            raise Fail("call", "任务失败：%s（%s）—— 预扣金额会全额退回"
                       % (e.get("message") or "无说明", e.get("code") or "-"), EXIT_CALL)
        time.sleep(every)
    raise Fail("interrupt",
               "等待超时（%d 分钟）—— 任务**可能仍在生成**。\n"
               "  **不要重新提交**（重提会再扣一次钱）。稍后用：\n"
               "    python3 scripts/run.py wait %s --outdir %s"
               % (limit // 60, vid, a.outdir), EXIT_TIMEOUT)


def _finish(a, s, vid):
    vurl = s.get("video_url") or ""
    exp = s.get("expires_at")
    exp_txt = ""
    if isinstance(exp, (int, float)) and exp > 0:
        exp_txt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp))
    out = {"ok": bool(vurl), "id": vid, "status": s.get("status"),
           "seconds": s.get("seconds"), "size": s.get("size"),
           "videoUrl": vurl, "expiresAt": exp_txt}

    path = ""
    if vurl:
        os.makedirs(a.outdir, exist_ok=True)
        path = os.path.join(a.outdir, "%s-%s.mp4" % (a.prefix, vid[-8:] if vid else "out"))
        try:
            req = urllib.request.Request(vurl, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=900) as r, open(path, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            out["file"] = path
            out["bytes"] = os.path.getsize(path)
        except Exception as e:                                   # noqa: BLE001
            out["downloadError"] = "%s: %s" % (type(e).__name__, e)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(vurl), "id": vid,
                "done": True, "file": path, "seconds": s.get("seconds")})

    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if vurl else EXIT_CALL
    if not vurl:
        say("  已完成，但响应里没有 video_url。原始：%s" % json.dumps(s, ensure_ascii=False)[:400])
        return EXIT_CALL
    print()
    print("出片完成")
    print("  任务：%s" % vid)
    print("  规格：%s · %s 秒 · 720P 带声音" % (s.get("size"), s.get("seconds")))
    if out.get("file"):
        print("  文件：%s（%d 字节）" % (out["file"], out["bytes"]))
    if out.get("downloadError"):
        print("  ⚠️ 下载失败：%s" % out["downloadError"])
        print("     链接仍可用，手动下载：%s" % vurl)
    print("  线上链接：%s" % vurl)
    if exp_txt:
        print("  ⚠️ 链接 %s 过期（平台成品只保留 24 小时，请转存）" % exp_txt)
    return 0


def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给任务 ID", EXIT_USAGE)
    url = "%s%s/videos/%s" % (host, API_PREFIX, urllib.parse.quote(a.task_id))
    st, txt = http("GET", url, key, timeout=60)
    d = jloads(txt) or {}
    if st == 404:
        raise Fail("call", "任务不存在（task_not_exist）：%s" % a.task_id, EXIT_CALL)
    if st != 200:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if a.json:
        print(json.dumps({"ok": True, "task": d}, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    for k in ("status", "progress", "seconds", "size", "created_at",
              "completed_at", "video_url", "expires_at"):
        if d.get(k) not in (None, ""):
            v = d.get(k)
            if k in ("created_at", "completed_at", "expires_at") and isinstance(v, (int, float)):
                v = "%s（%d）" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(v)), v)
            print("  %-13s %s" % (k, v))
    if d.get("error"):
        print("  %-13s %s" % ("error", json.dumps(d["error"], ensure_ascii=False)))
    return 0


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
        print("  %s  %-22s %-5s  %s 秒  %s 点" % (
            e.get("at"), e.get("id") or "-", "完成" if e.get("done") else "提交",
            e.get("seconds"), e.get("reservedPoints") or ""))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · Muse Video 出片台（api.a7w.cn · 720P 带声音 · 4–180 秒 · 11 点/秒）",
        epilog="端点：POST %s/api/v1/videos · GET %s/api/v1/videos/{id} · "
               "GET %s/api/v1/models" % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=2000,
                    help="点数上限（单位：点；默认 2000，约 181 秒）")
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("models", help="列出在架视频模型（免费）", allow_abbrev=False)
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser("cost", help="先算钱（免费，11 点/秒）", allow_abbrev=False)
    p.add_argument("--seconds", type=int, default=5, help="秒数 4–180")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 端点 / 模型（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_common(p, with_refs=False):
        p.add_argument("--prompt", help="提示词（≤4000 字；写清主体、怎么动、镜头怎么走）")
        p.add_argument("--seconds", type=int, default=5, help="秒数 4–180（默认 5）")
        p.add_argument("--size", default="1280x720", choices=list(SIZES),
                       help="1280x720 横屏（默认）/ 720x1280 竖屏")
        p.add_argument("--model", default=DEFAULT_MODEL)
        p.add_argument("--outdir", default=".", help="视频保存目录")
        p.add_argument("--prefix", default="muse", help="文件名前缀")
        p.add_argument("--timeout", type=int, default=180, help="**提交**请求超时（秒）")
        p.add_argument("--wait", action="store_true",
                       help="提交后等到完成并下载（可能 1–15 分钟）")
        p.add_argument("--every", type=int, default=15, help="轮询间隔秒数（默认 15）")
        p.add_argument("--limit", type=int, default=3600, help="等待上限秒数（默认 3600）")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        if with_refs:
            p.add_argument("--first-frame", help="本地首帧图文件（走 multipart）")
            p.add_argument("--ref", action="append",
                           help="参考图（URL 或本地路径，可重复，最多 4 张）")

    p = sub.add_parser("gen", help="提交任务（要 --yes；--wait 则等到完成）",
                       allow_abbrev=False)
    add_common(p, with_refs=True)
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("status", help="查任务状态", allow_abbrev=False)
    p.add_argument("task_id", nargs="?", help="任务 ID")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("wait", help="等任务完成并下载", allow_abbrev=False)
    p.add_argument("task_id", nargs="?", help="任务 ID")
    p.add_argument("--outdir", default=".", help="视频保存目录")
    p.add_argument("--prefix", default="muse")
    p.add_argument("--every", type=int, default=15)
    p.add_argument("--limit", type=int, default=3600)
    p.set_defaults(fn=cmd_wait)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

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
        say("已中断。任务可能仍在生成 —— 用 `status <id>` 查，**别重提**。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
