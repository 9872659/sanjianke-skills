#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · Suno 音乐台

走 api.a7w.cn 的 **Official 音频与辅助服务**（应用代号 `media_services_33`），
本包接的是里面全部 **Suno 音乐**接口（剩下 22 个 Gemini TTS / ElevenLabs 接口不属本包）。

## 权威规格（取自网关 `GET /api/v1/apps/media_services_33` 的 params_schema）

  接口根地址   https://api.a7w.cn/api/v1
  统一形态     POST /api/v1/apps/media_services_33/<接口code>   （JSON）
  任务查询     GET  /api/v1/tasks/<task_id>                      （只读，免费）
  生成音乐     music_generate            model / custom_mode / instrumental
  延长音乐     music_extend              model / audio_id
  生成音效     music_sounds              model / prompt
  自建音色     music_generate_voice      action=prepare → create
  时间戳歌词   music_timestamped_lyrics  task_id / audio_id
  恢复音频     music_recovery_audio      task_id
  生成 Persona music_generate_persona    name / task_id / audio_id / description

  model 枚举   music_generate / music_extend：V4 V4_5 V4_5PLUS V4_5ALL V5 V5_5 V6 V6_MINI V6_WILD
               music_sounds：V5 V5_5 V6 V6_MINI V6_WILD
               官方建议用 V6 / V6_MINI / V6_WILD，其余已废弃
  返回         `{"code":1,"msg":"success","data":{...}}`；**校验失败也是 HTTP 200**，
               只是 `code=0` + `data=null` —— 所以判断成功必须看 `code`，不能只看状态码

## 价格口径（**必须诚实**）

`/api/v1/pricing` 里**没有 `media_services_33` 的专属规则**，落通配：

    {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
     "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}

也就是说：**一条歌对外点数 = 上游实际点数 × 2，单笔保底 50 点。**
上游真实点数要真跑一次才看得到，所以 `cost` 给的是**下限估算**（默认 50 点起）。

## 两道闸门

  `--budget` 单位是「点」（1 元 = 100 点）；`--yes` 是第二道。
  缺 `--yes` → exit 4 并告诉你下限是多少；下限 > `--budget` → exit 5，**一个请求都不发**。

## 子命令

  catalog  现查 7 个接口的必填项与 model 枚举（免费）
  doctor   自检 Key / 应用 / 7 个端点（免费，全部用「必然被校验拦下」的 body）
  cost     先算钱（免费，给下限）
  song     生成音乐
  extend   延长音乐
  sound    生成音效
  voice    自建音色（prepare → create）
  lyrics   取带时间戳歌词
  recover  恢复音频
  persona  生成 Persona
  task     查任务状态 / 补取结果（免费读取）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --tasks 1
  python3 scripts/run.py song --prompt "夏夜城市霓虹的温暖合成器流行" --yes
  python3 scripts/run.py song --custom --style "dream pop" --lyrics "[主歌]..." --title "夜行" --yes
  python3 scripts/run.py extend --audio-id <audio_id> --lyrics "..." --yes
  python3 scripts/run.py sound --prompt "雨打铁皮棚，远处雷声" --tempo 90 --yes
  python3 scripts/run.py lyrics --task-id <task_id> --audio-id <audio_id> --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题可加技术微信 技术微信。
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


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
APP = "media_services_33"
DEFAULT_MODEL = "V6"

# 价格口径：通配规则（无 media_services_33 专属规则）
UPSTREAM_MARKUP = 2      # 上游点数 × 2
MIN_POINTS = 50          # 单笔保底 50 点
DEFAULT_BUDGET = 500

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "suno-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-suno-music/%s" % VERSION

# 接口代号 → 中文名（本包接的 7 个）
CORE = [
    ("music_generate", "生成音乐"),
    ("music_extend", "延长音乐"),
    ("music_sounds", "生成音效"),
    ("music_generate_voice", "自建音色"),
    ("music_timestamped_lyrics", "带时间戳歌词"),
    ("music_recovery_audio", "恢复音频"),
    ("music_generate_persona", "生成 Persona"),
]
CORE_CODES = [c for c, _ in CORE]
CORE_NAME = dict(CORE)

GEN_MODELS = ["V6", "V6_MINI", "V6_WILD", "V5_5", "V5", "V4_5ALL", "V4_5PLUS", "V4_5", "V4"]
SOUND_MODELS = ["V6", "V6_MINI", "V6_WILD", "V5_5", "V5"]
SOUND_KEYS = ["Any", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
              "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "A#m", "Bm"]
VOICE_LANGS = ["zh", "en", "es", "fr", "pt", "de", "ja", "ko", "hi", "ru"]
SKILL_LEVELS = ["beginner", "intermediate", "advanced", "professional"]

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
    """发一次请求。网关会重置空闲连接（WinError 10054），所以网络类错误退避重试；
    4xx 是业务错误，直接返回给调用方判断。"""
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


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        if d.get("msg"):
            return str(d["msg"])[:400]
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or "", e.get("param") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:400]
        for k in ("message", "error"):
            if d.get(k):
                return str(d[k])[:400]
    return txt.replace("\n", " ")[:300]


def envelope(st, txt, url):
    """网关成功判据：HTTP 200 且 code ∈ {1,200}。校验失败也是 200，但 code=0。"""
    d = jloads(txt)
    if st != 200:
        raise Fail("call", "调用失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if not isinstance(d, dict):
        raise Fail("call", "返回不是 JSON：%s" % txt[:200], EXIT_CALL)
    code = d.get("code")
    if code not in (1, 200, None):
        raise Fail("call", "上游拒绝（%s）：%s" % (url.rsplit("/", 1)[-1],
                                                d.get("msg") or err_text(st, txt)), EXIT_CALL)
    return d.get("data")


def api_get(a, key, host, path, timeout=60):
    return envelope(*http_json("GET", host + path, key, None, timeout), url=path)


def api_post(a, key, host, api, body, timeout=120):
    url = host + API_PREFIX + "/apps/" + APP + "/" + api
    return envelope(*http_json("POST", url, key, body, timeout), url=url)


# ───────────────────────── 价格 ─────────────────────────
def est_points(tasks=1, upstream=0):
    """下限估算：max(保底 50, 上游点数 × 2) × 条数。"""
    per = max(MIN_POINTS, int(round(float(upstream) * UPSTREAM_MARKUP)))
    return per * tasks


def gate(a, tasks=1):
    """两道闸门：预算不够 → 5（不发请求）；没 --yes → 4。"""
    cost = est_points(tasks, a.upstream)
    if cost > a.budget:
        raise Fail("budget", "下限就要 %d 点，超过 --budget %d 点。一个请求都没发。"
                              "调大 --budget（单位：点）再试。" % (cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实生成并计费，**下限 %d 点（¥%.2f）**，"
                              "上游实际点数 × 2、按实际结算。确认请加 --yes。"
                              % (cost, cost / 100.0), EXIT_CONFIRM)
    return cost


# ───────────────────────── 免费子命令 ─────────────────────────
def _app_detail(a, key, host):
    d = api_get(a, key, host, API_PREFIX + "/apps/" + APP)
    return (d or {}).get("apis") or []


def cmd_catalog(a, key, host):
    apis = _app_detail(a, key, host)
    by = {it.get("code"): it for it in apis if isinstance(it, dict)}
    rows = []
    for code, name in CORE:
        it = by.get(code) or {}
        sch = it.get("params_schema") or {}
        req = [k for k, v in sch.items() if isinstance(v, dict) and v.get("required")]
        opt = [k for k, v in sch.items() if isinstance(v, dict) and not v.get("required")]
        models = ((sch.get("model") or {}).get("enum")) or []
        rows.append({"api": code, "name": name, "在线": bool(it),
                     "required": req, "optional": opt, "models": models})
    out = {"ok": True, "app": APP, "apis_total": len(apis),
           "core": rows, "other_apis": len(apis) - len(CORE)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("Official 音频与辅助服务（%s）· 共 %d 个接口，本包接其中 %d 个 Suno 音乐接口"
          % (APP, len(apis), len(CORE)))
    print()
    for r in rows:
        print("  %-26s %s" % (r["api"], r["name"]))
        print("      必填  %s" % (", ".join(r["required"]) or "（无）"))
        print("      常用  %s" % (", ".join(r["optional"][:8]) or "（无）"))
        if r["models"]:
            print("      model %s" % " / ".join(r["models"]))
    print()
    print("  剩下 %d 个是 Gemini TTS / ElevenLabs 语音接口，属另一条线。" % out["other_apis"])
    return 0


def cmd_cost(a, key, host):
    rows = []
    for up in (0, 60, 65, 90, 230):
        rows.append({"upstream": up, "points": est_points(a.tasks, up)})
    floor = est_points(a.tasks, a.upstream)
    out = {"ok": True, "tasks": a.tasks, "upstreamPoints": a.upstream,
           "markup": UPSTREAM_MARKUP, "minPoints": MIN_POINTS,
           "estimate": floor, "yuan": round(floor / 100.0, 2),
           "isLowerBound": True,
           "basis": "pricing 无 media_services_33 专属规则 → 落通配：上游实际点数 × 2，单笔保底 50 点"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("价格口径（诚实版）")
    print("  规则：**上游实际点数 × 2，单笔保底 50 点**（1 元 = 100 点）")
    print("  依据：/api/v1/pricing 里没有 media_services_33 的专属规则，落通配 `*`")
    print()
    print("  本次：%d 条 × 下限 = **%d 点 = %.2f 元**" % (a.tasks, floor, floor / 100.0))
    print("  ⚠️ 这是**下限估算**。上游真实点数要真跑一次才知道，实际按任务详情结算。")
    print()
    print("  不同上游点数的对照（下限口径）：")
    for r in rows:
        if not r["upstream"]:
            print("    上游点数未知  →  至少 %d 点（¥%.2f，保底）"
                  % (r["points"], r["points"] / 100.0))
        else:
            print("    上游 %-4d 点  →  对外 %-4d 点（¥%.2f）"
                  % (r["upstream"], r["points"], r["points"] / 100.0))
    print()
    print("  用你自己观察到的上游点数算：`cost --upstream 65 --tasks 1`")
    return 0


def _probe(a, key, host, api, body):
    """发一个必然被参数校验拦下的请求，返回 (code, msg, data)。不建任务、不扣费。"""
    url = host + API_PREFIX + "/apps/" + APP + "/" + api
    st, txt = http_json("POST", url, key, body, timeout=60)
    d = jloads(txt) or {}
    return st, d.get("code"), str(d.get("msg") or ""), d.get("data")


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/models", key, None, 60)
    d = jloads(txt) or {}
    checks.append(("Key 有效 + 模型目录可达", st == 200 and d.get("code") in (1, 200),
                   "HTTP %s code=%s" % (st, d.get("code"))))

    detail = api_get(a, key, host, API_PREFIX + "/apps/" + APP)
    apis = (detail or {}).get("apis") or []
    codes = {it.get("code") for it in apis if isinstance(it, dict)}
    miss = [c for c in CORE_CODES if c not in codes]
    checks.append(("应用在架 + 7 个接口齐全", bool(apis) and not miss,
                   "接口 %d 个%s" % (len(apis), "，缺 " + ",".join(miss) if miss else "")))

    probes = [
        ("music_generate", {}, "Suno 生成音乐端点",
         "缺少必填参数"),
        ("music_extend", {"model": DEFAULT_MODEL, "audio_id": "sanjianke-doctor-probe"},
         "Suno 延长音乐端点", "请使用本平台返回的任务或资源标识"),
        ("music_sounds", {"model": DEFAULT_MODEL, "prompt": "probe",
                          "sound_key": "Zzz", "sound_tempo": 120},
         "Suno 音效端点", "不在允许选项内"),
        ("music_generate_voice", {"action": "probe"}, "Suno 自建音色端点", "音色操作步骤无效"),
        ("music_timestamped_lyrics", {}, "时间戳歌词端点", "缺少必填参数"),
        ("music_recovery_audio", {}, "恢复音频端点", "缺少必填参数"),
        ("music_generate_persona", {}, "Persona 端点", "缺少必填参数"),
    ]
    for api, body, label, needle in probes:
        st, code, msg, data = _probe(a, key, host, api, body)
        ok = st == 200 and code == 0 and data is None and needle in msg
        checks.append((label + "（参数校验拦下即正确）", ok,
                       "HTTP %s code=%s %s" % (st, code, msg[:44])))

    st, txt = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe", key, None, 60)
    d = jloads(txt) or {}
    ok = st == 200 and d.get("code") == 0 and "不存在" in str(d.get("msg") or "")
    checks.append(("任务查询接口在（假 task_id 返回「任务不存在」）", ok,
                   "HTTP %s %s" % (st, d.get("msg"))))

    out = {"ok": all(c[1] for c in checks), "app": APP,
           "endpoint": host + API_PREFIX + "/apps/" + APP + "/<接口code>",
           "taskEndpoint": host + API_PREFIX + "/tasks/<task_id>",
           "priceRule": {"markup": UPSTREAM_MARKUP, "minPoints": MIN_POINTS,
                         "isLowerBound": True},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（不扣费：只读接口 + 必然被参数校验拦下的 POST）")
    print()
    for n, o, dt in checks:
        print("  %s %-40s %s" % ("√" if o else "×", n, dt))
    print()
    print("  端点：POST %s" % out["endpoint"])
    print("  查询：GET  %s" % out["taskEndpoint"])
    print("  价格：上游点数 × %d，单笔保底 %d 点（下限，实际按任务详情结算）"
          % (UPSTREAM_MARKUP, MIN_POINTS))
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 任务与结果 ─────────────────────────
def get_task(a, key, host, task_id):
    d = api_get(a, key, host, API_PREFIX + "/tasks/" + urllib.parse.quote(task_id))
    if not isinstance(d, dict):
        raise Fail("call", "任务 %s 查不到（返回为空）。" % task_id, EXIT_CALL)
    return d


def wait_task(a, key, host, task_id):
    deadline = time.time() + max(30, a.wait)
    last, ticks = None, 0
    while time.time() < deadline:
        time.sleep(max(1, a.every))
        ticks += 1
        d = get_task(a, key, host, task_id)
        st = str(d.get("status") or "").lower()
        if st != last:
            say("  状态：%s" % (st or "?"))
            last = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            return d
    raise Fail("call", "等了 %d 秒还没完成。任务没丢——用 `task --task-id %s` 接着取，"
                       "**不要重新提交**（会再扣一次）。" % (a.wait, task_id), EXIT_CALL)


def _walk_audio(node, rows, depth=0):
    if depth > 5:
        return
    if isinstance(node, dict):
        url = None
        for k in ("audio_url", "audioUrl", "source_audio_url", "stream_audio_url", "url"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                url = v
                break
        if url:
            aid = None
            for k in ("audio_id", "audioId", "clip_id", "id"):
                v = node.get(k)
                if isinstance(v, str) and v and not v.startswith("http"):
                    aid = v
                    break
            rows.append({"audio_url": url, "audio_id": aid,
                         "title": node.get("title") or node.get("name"),
                         "duration": node.get("duration"),
                         "lyric": node.get("lyric") or node.get("lyrics")})
            return
        for v in node.values():
            _walk_audio(v, rows, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _walk_audio(v, rows, depth + 1)


def find_audio(data):
    rows = []
    _walk_audio(data, rows)
    seen, out = set(), []
    for r in rows:
        if r["audio_url"] in seen:
            continue
        seen.add(r["audio_url"])
        out.append(r)
    return out


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


def download(url, outdir, prefix, idx):
    os.makedirs(outdir, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as x:
        raw = x.read()
    ext = ".mp3"
    for e in (".mp3", ".wav", ".m4a", ".mp4", ".flac", ".ogg"):
        if e in url.split("?")[0].lower():
            ext = e
            break
    p = os.path.join(outdir, "%s-%02d%s" % (prefix, idx, ext))
    io.open(p, "wb").write(raw)
    return p


def _finish(a, key, host, api, body, cost, t0):
    say("已提交（%s）… 等结果" % api)
    data = api_post(a, key, host, api, body, timeout=max(60, a.timeout))
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if not task_id:
        out = {"ok": True, "api": api, "sync": True, "data": data,
               "estimatedPoints": cost}
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": api, "ok": True,
                    "task_id": None, "model": body.get("model"),
                    "pointsFloor": cost})
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print(json.dumps(data, ensure_ascii=False, indent=1)[:3000])
        print()
        print("  这条接口没返回 task_id，按同步结果处理。")
        return 0

    say("  task_id=%s" % task_id)
    if a.no_wait:
        out = {"ok": True, "api": api, "task_id": task_id, "submitted": True,
               "estimatedPoints": cost,
               "next": "python3 scripts/run.py task --task-id %s" % task_id}
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": api, "ok": True,
                    "task_id": task_id, "model": body.get("model"),
                    "pointsFloor": cost, "status": "submitted"})
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("已提交，不等待。")
        print("  task_id：%s" % task_id)
        print("  接着取：python3 scripts/run.py task --task-id %s" % task_id)
        return 0

    t = wait_task(a, key, host, task_id)
    dt = time.time() - t0
    st = str(t.get("status") or "").lower()
    rows = find_audio(t)
    paths = []
    if a.out and rows:
        for i, r in enumerate(rows, 1):
            try:
                paths.append(download(r["audio_url"], a.out, a.prefix, i))
            except Exception as e:                               # noqa: BLE001
                say("  下载失败（%s）：%s" % (r["audio_url"], e))

    usage = t.get("usage") if isinstance(t.get("usage"), dict) else {}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": api, "ok": st in TERMINAL_OK,
           "task_id": task_id, "model": body.get("model"), "status": st,
           "audio_ids": [r["audio_id"] for r in rows if r["audio_id"]],
           "audio_urls": [r["audio_url"] for r in rows],
           "elapsed": round(dt, 1), "pointsFloor": cost,
           "usage": usage, "files": paths}
    ledger_add(rec)

    out = {"ok": st in TERMINAL_OK, "api": api, "task_id": task_id, "status": st,
           "elapsed": round(dt, 1), "audios": rows, "files": paths,
           "pointsFloor": cost, "usage": usage, "error": t.get("error")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        if st in TERMINAL_BAD:
            return EXIT_CALL
        return 0 if rows or st in TERMINAL_OK else EXIT_CALL

    if st in TERMINAL_BAD:
        say("任务失败：%s" % (t.get("error") or t.get("failReason") or st))
        return EXIT_CALL
    print("完成（%.1fs）" % dt)
    print("  task_id：%s" % task_id)
    if not rows:
        print("  这条返回里没解析到音频地址，原始返回如下（用 `task --task-id` 可再看）：")
        print(json.dumps(t, ensure_ascii=False, indent=1)[:2500])
        return EXIT_CALL
    for i, r in enumerate(rows, 1):
        print()
        print("  #%d %s" % (i, r.get("title") or ""))
        if r.get("audio_id"):
            print("      audio_id：%s  ← 延长 / 取歌词 / 建 Persona 都要它" % r["audio_id"])
        if r.get("duration"):
            print("      时长：%s 秒" % r["duration"])
        print("      音频：%s" % r["audio_url"])
        if r.get("lyric"):
            print("      歌词：%s" % str(r["lyric"]).replace("\n", " / ")[:80])
    for p in paths:
        print("  已存：%s（%d 字节）" % (p, os.path.getsize(p)))
    if usage:
        print()
        print("  上游用量：%s" % json.dumps(usage, ensure_ascii=False))
    print("  计费：按上游实际点数 × %d 结算，下限 %d 点" % (UPSTREAM_MARKUP, cost))
    return 0


# ───────────────────────── 参数校验 ─────────────────────────
def _need(a, *names):
    miss = []
    for n in names:
        val = getattr(a, n.replace("-", "_"), None)
        if val is None or (isinstance(val, str) and not val.strip()):
            miss.append("--" + n)
    if miss:
        raise Fail("usage", "缺必填参数：%s" % " ".join(miss), EXIT_USAGE)


def _check_model(model, allowed, api):
    if model not in allowed:
        raise Fail("usage", "%s 的 model 只能是：%s" % (api, " / ".join(allowed)), EXIT_USAGE)


def _check_range(name, val, lo, hi):
    if val is None:
        return
    if val < lo or val > hi:
        raise Fail("usage", "%s 必须在 %d–%d 之间（当前 %s）" % (name, lo, hi, val), EXIT_USAGE)


# ───────────────────────── 生成类子命令 ─────────────────────────
def cmd_song(a, key, host):
    _check_model(a.model, GEN_MODELS, "music_generate")
    if not a.custom and a.instrumental is None:
        a.instrumental = False
    if a.custom and not (a.style or a.lyrics or a.negative_tags):
        raise Fail("usage", "自定义模式（--custom）下 style / lyrics / negative_tags "
                            "至少给一项，否则上游会拒（schema 原文）。", EXIT_USAGE)
    if a.custom and not a.title:
        raise Fail("usage", "自定义模式（--custom）下 --title 是必填（schema 原文，≤80 字符）。",
                   EXIT_USAGE)
    if a.title and len(a.title) > 80:
        raise Fail("usage", "--title 最多 80 字符（当前 %d）。" % len(a.title), EXIT_USAGE)
    if not a.custom and not (a.prompt or a.style or a.lyrics):
        raise Fail("usage", "非自定义模式下 prompt / style / lyrics 至少给一项"
                            "（例如 --prompt \"夏夜霓虹的合成器流行\"）。", EXIT_USAGE)
    _check_range("--duration", a.duration, 10, 360)
    _check_range("--variety", a.variety, 0, 4)
    _check_range("--style-weight", a.style_weight, 0, 1)
    _check_range("--weirdness", a.weirdness, 0, 1)

    body = {"model": a.model, "custom_mode": bool(a.custom),
            "instrumental": bool(a.instrumental)}
    for k, v in (("style", a.style), ("title", a.title), ("lyrics", a.lyrics),
                 ("prompt", a.prompt), ("negative_tags", a.negative_tags),
                 ("vocal_gender", a.vocal_gender), ("persona_id", a.persona_id),
                 ("duration", a.duration), ("variety", a.variety),
                 ("style_weight", a.style_weight), ("weirdness_constraint", a.weirdness)):
        if v is not None and v != "":
            body[k] = v

    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_generate", body, cost)
    return _finish(a, key, host, "music_generate", body, cost, time.time())


def cmd_extend(a, key, host):
    _need(a, "audio-id")
    _check_model(a.model, GEN_MODELS, "music_extend")
    if a.instrumental and (a.lyrics or a.prompt):
        raise Fail("usage", "--instrumental 时不能带 --lyrics / --prompt（schema 原文）。",
                   EXIT_USAGE)
    if a.continue_at is not None and a.continue_at <= 0:
        raise Fail("usage", "--continue-at 必须大于 0（从原曲第几秒接下去）。", EXIT_USAGE)
    _check_range("--variety", a.variety, 0, 4)

    body = {"model": a.model, "audio_id": a.audio_id}
    for k, v in (("style", a.style), ("title", a.title), ("lyrics", a.lyrics),
                 ("prompt", a.prompt), ("continue_at", a.continue_at),
                 ("variety", a.variety), ("persona_id", a.persona_id),
                 ("negative_tags", a.negative_tags), ("vocal_gender", a.vocal_gender)):
        if v is not None and v != "":
            body[k] = v
    if a.instrumental:
        body["instrumental"] = True

    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_extend", body, cost)
    return _finish(a, key, host, "music_extend", body, cost, time.time())


def cmd_sound(a, key, host):
    _need(a, "prompt")
    _check_model(a.model, SOUND_MODELS, "music_sounds")
    if len(a.prompt) > 500:
        raise Fail("usage", "--prompt 最多 500 字符（当前 %d）。" % len(a.prompt), EXIT_USAGE)
    _check_range("--tempo", a.tempo, 1, 300)
    # 网关把「不传 sound_tempo」判成类型错误（实测），所以这里必须显式给。
    body = {"model": a.model, "prompt": a.prompt,
            "sound_key": a.sound_key, "sound_tempo": a.tempo}
    if a.loop:
        body["sound_loop"] = True
    if a.grab_lyrics:
        body["grab_lyrics"] = True

    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_sounds", body, cost)
    return _finish(a, key, host, "music_sounds", body, cost, time.time())


def cmd_voice(a, key, host):
    if a.action == "prepare":
        _need(a, "voice-url", "start", "end")
        if a.end <= a.start:
            raise Fail("usage", "--end 必须大于 --start（用于验证的人声片段）。", EXIT_USAGE)
    elif a.action == "create":
        _need(a, "verify-url")
    else:
        raise Fail("usage", "--action 只能是 prepare 或 create。", EXIT_USAGE)

    body = {"action": a.action}
    for k, v in (("voice_url", a.voice_url), ("verify_url", a.verify_url),
                 ("voice_name", a.voice_name), ("language", a.language),
                 ("style", a.style), ("description", a.description),
                 ("singer_skill_level", a.skill_level), ("task_id", a.task_id)):
        if v is not None and v != "":
            body[k] = v
    if a.action == "prepare":
        body["vocal_start_s"] = a.start
        body["vocal_end_s"] = a.end

    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_generate_voice", body, cost)
    return _finish(a, key, host, "music_generate_voice", body, cost, time.time())


def cmd_lyrics(a, key, host):
    _need(a, "task-id", "audio-id")
    body = {"task_id": a.task_id, "audio_id": a.audio_id}
    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_timestamped_lyrics", body, cost)
    return _finish(a, key, host, "music_timestamped_lyrics", body, cost, time.time())


def cmd_recover(a, key, host):
    _need(a, "task-id")
    body = {"task_id": a.task_id}
    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_recovery_audio", body, cost)
    return _finish(a, key, host, "music_recovery_audio", body, cost, time.time())


def cmd_persona(a, key, host):
    _need(a, "name", "task-id", "audio-id", "description")
    if a.vocal_start is not None and a.vocal_end is not None:
        gap = a.vocal_end - a.vocal_start
        if gap < 10 or gap > 30:
            raise Fail("usage", "vocal_end − vocal_start 必须在 10–30 秒之间（当前 %.1f 秒）。"
                       % gap, EXIT_USAGE)
    body = {"name": a.name, "task_id": a.task_id, "audio_id": a.audio_id,
            "description": a.description}
    for k, v in (("style", a.style), ("vocal_start", a.vocal_start),
                 ("vocal_end", a.vocal_end)):
        if v is not None and v != "":
            body[k] = v
    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_generate_persona", body, cost)
    return _finish(a, key, host, "music_generate_persona", body, cost, time.time())


def _dry(a, host, api, body, cost):
    url = host + API_PREFIX + "/apps/" + APP + "/" + api
    out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
           "estimatedPoints": cost, "isLowerBound": True}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不扣费）")
    print("  端点：%s" % url)
    print("  请求：%s" % json.dumps(body, ensure_ascii=False))
    print("  下限：%d 点（%.2f 元）—— 上游实际点数 × %d，单笔保底 %d"
          % (cost, cost / 100.0, UPSTREAM_MARKUP, MIN_POINTS))
    return 0


def cmd_task(a, key, host):
    _need(a, "task-id")
    t = get_task(a, key, host, a.task_id)
    st = str(t.get("status") or "").lower()
    rows = find_audio(t)
    paths = []
    if a.out and rows:
        for i, r in enumerate(rows, 1):
            try:
                paths.append(download(r["audio_url"], a.out, a.prefix, i))
            except Exception as e:                               # noqa: BLE001
                say("  下载失败：%s" % e)
    out = {"ok": True, "task_id": a.task_id, "status": st, "audios": rows,
           "files": paths, "usage": t.get("usage"), "raw": t if a.json else None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (st or "?"))
    if rows:
        for i, r in enumerate(rows, 1):
            print("  #%d %s" % (i, r.get("title") or ""))
            if r.get("audio_id"):
                print("      audio_id：%s" % r["audio_id"])
            print("      音频：%s" % r["audio_url"])
    else:
        print("  这部还没解析到音频（没完成就是正常的）。")
    for p in paths:
        print("  已存：%s" % p)
    if t.get("usage"):
        print("  上游用量：%s" % json.dumps(t["usage"], ensure_ascii=False))
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
        print("  %s  %-26s %-10s %s  %s" % (
            e.get("at"), e.get("api") or "-", e.get("status") or "-",
            (e.get("task_id") or "")[:22], "下限 %s 点" % e.get("pointsFloor")))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · Suno 音乐台（走 api.a7w.cn 的 Official 音频与辅助服务 media_services_33）",
        epilog="端点：POST %s/api/v1/apps/media_services_33/<接口code> · "
               "GET %s/api/v1/tasks/<task_id>" % (DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--upstream", type=int, default=0,
                    help="上游点数（用于算下限；默认 0 = 只看保底 %d 点）" % MIN_POINTS)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="现查 7 个接口的必填项与 model 枚举（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱（免费，给的是下限）", allow_abbrev=False)
    p.add_argument("--tasks", type=int, default=1, help="几条任务（默认 1）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 7 个端点（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_common(p, models=None, with_model=True):
        if with_model:
            p.add_argument("--model", default=DEFAULT_MODEL,
                           help="model：%s（默认 %s）" % ("/".join(models or GEN_MODELS),
                                                          DEFAULT_MODEL))
        p.add_argument("--yes", action="store_true", help="确认真实计费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.add_argument("--no-wait", action="store_true", help="只提交，拿 task_id 就走")
        p.add_argument("--wait", type=int, default=600, help="等结果的上限秒数（默认 600）")
        p.add_argument("--every", type=int, default=5, help="轮询间隔秒数（默认 5）")
        p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数")
        p.add_argument("--out", default=None, help="把音频下载到这个目录（可选）")
        p.add_argument("--prefix", default="suno", help="下载文件名前缀")

    p = sub.add_parser("song", help="生成音乐（一句话出一首歌）", allow_abbrev=False)
    add_common(p)
    p.add_argument("--prompt", help="灵感模式的一句话描述（custom_mode=false）")
    p.add_argument("--custom", action="store_true", help="自定义模式（自己给风格/歌词）")
    p.add_argument("--style", help="音乐风格，例如 dream pop / 国风 / 爵士")
    p.add_argument("--lyrics", help="歌词（V6 最多 5000 字符）")
    p.add_argument("--title", help="歌名（自定义模式下必填，≤80 字符）")
    p.add_argument("--instrumental", action="store_true", help="纯音乐（无人声）")
    p.add_argument("--duration", type=int, default=None, help="目标时长秒数 10–360")
    p.add_argument("--variety", type=int, default=None, help="多样性 0–4（默认 1）")
    p.add_argument("--negative-tags", dest="negative_tags", help="要避开的风格")
    p.add_argument("--vocal-gender", dest="vocal_gender", choices=["m", "f"],
                   help="人声性别偏好")
    p.add_argument("--persona-id", dest="persona_id", help="套用某个 Persona / Voice")
    p.add_argument("--style-weight", dest="style_weight", type=float, default=None,
                   help="风格遵循强度 0–1")
    p.add_argument("--weirdness", type=float, default=None, help="创意偏离 0–1")
    p.set_defaults(fn=cmd_song)

    p = sub.add_parser("extend", help="延长音乐（接着一首歌往下写）", allow_abbrev=False)
    add_common(p)
    p.add_argument("--audio-id", dest="audio_id", help="要延长的 audio_id（必填）")
    p.add_argument("--style", help="延续的风格")
    p.add_argument("--lyrics", help="续写的歌词")
    p.add_argument("--prompt", help="续写歌词（不给 --lyrics 时用它）")
    p.add_argument("--title", help="歌名")
    p.add_argument("--continue-at", dest="continue_at", type=float, default=None,
                   help="从原曲第几秒接下去")
    p.add_argument("--instrumental", action="store_true", help="续写纯音乐")
    p.add_argument("--variety", type=int, default=None, help="多样性 0–4")
    p.add_argument("--negative-tags", dest="negative_tags", help="要避开的风格")
    p.add_argument("--vocal-gender", dest="vocal_gender", choices=["m", "f"])
    p.add_argument("--persona-id", dest="persona_id", help="套用某个 Persona / Voice")
    p.set_defaults(fn=cmd_extend)

    p = sub.add_parser("sound", help="生成音效（一条提示词出一个音效）", allow_abbrev=False)
    add_common(p, SOUND_MODELS)
    p.add_argument("--prompt", help="声音描述，≤500 字符（必填）")
    p.add_argument("--sound-key", dest="sound_key", default="Any", choices=SOUND_KEYS,
                   help="调性（默认 Any = 自动）")
    p.add_argument("--tempo", type=int, default=120,
                   help="速度 BPM 1–300（默认 120；本包总是显式传，见 references）")
    p.add_argument("--loop", action="store_true", help="可循环")
    p.add_argument("--grab-lyrics", dest="grab_lyrics", action="store_true",
                   help="顺手抓歌词字幕")
    p.set_defaults(fn=cmd_sound)

    p = sub.add_parser("voice", help="自建音色（prepare → create 两步）", allow_abbrev=False)
    add_common(p, with_model=False)
    p.add_argument("--action", default="create", choices=["prepare", "create"],
                   help="prepare 拿验证短句 / create 提交验证音频（默认 create）")
    p.add_argument("--voice-url", dest="voice_url", help="prepare：本人人声样本 URL")
    p.add_argument("--verify-url", dest="verify_url", help="create：读验证短句的录音 URL")
    p.add_argument("--voice-name", dest="voice_name", help="音色名称")
    p.add_argument("--start", type=int, default=None, help="prepare：片段起始秒")
    p.add_argument("--end", type=int, default=None, help="prepare：片段结束秒")
    p.add_argument("--language", default="zh", choices=VOICE_LANGS, help="验证短句语言")
    p.add_argument("--style", help="音色风格")
    p.add_argument("--description", help="音色描述")
    p.add_argument("--skill-level", dest="skill_level", default=None,
                   choices=SKILL_LEVELS, help="歌手技能等级")
    p.add_argument("--task-id", dest="task_id", help="既有任务的 task_id（可选）")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("lyrics", help="取带时间戳的歌词（做字幕用）", allow_abbrev=False)
    add_common(p, with_model=False)
    p.add_argument("--task-id", dest="task_id", help="生成音乐/延长音乐返回的 task_id")
    p.add_argument("--audio-id", dest="audio_id", help="那首歌的 audio_id")
    p.set_defaults(fn=cmd_lyrics)

    p = sub.add_parser("recover", help="恢复音频（结果过期了再取一次）", allow_abbrev=False)
    add_common(p, with_model=False)
    p.add_argument("--task-id", dest="task_id", help="原任务的 task_id")
    p.set_defaults(fn=cmd_recover)

    p = sub.add_parser("persona", help="生成 Persona（把一首歌的味道存成模板）",
                       allow_abbrev=False)
    add_common(p, with_model=False)
    p.add_argument("--name", help="Persona 名称")
    p.add_argument("--task-id", dest="task_id", help="原任务 task_id")
    p.add_argument("--audio-id", dest="audio_id", help="原曲 audio_id")
    p.add_argument("--description", help="流派 / 情绪 / 乐器 / 人声特质")
    p.add_argument("--style", help="补充风格标签")
    p.add_argument("--vocal-start", dest="vocal_start", type=float, default=None)
    p.add_argument("--vocal-end", dest="vocal_end", type=float, default=None)
    p.set_defaults(fn=cmd_persona)

    p = sub.add_parser("task", help="查任务状态 / 补取结果（免费读取）", allow_abbrev=False)
    p.add_argument("--task-id", dest="task_id", help="task_id")
    p.add_argument("--out", default=None, help="把音频下载到这个目录（可选）")
    p.add_argument("--prefix", default="suno", help="下载文件名前缀")
    p.set_defaults(fn=cmd_task)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--upstream", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            if _n in _sp._option_string_actions:
                continue
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("budget", DEFAULT_BUDGET), ("upstream", 0), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    if not hasattr(a, "json"):
        a.json = False
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    if not key and a.fn is not cmd_catalog:
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
