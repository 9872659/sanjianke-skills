#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · AI 配乐（给一条视频自动配乐）

一条视频进来，四步出去：**分析节奏 -> 生成音乐 -> 配到时长 -> 混音清单**。
走 api.a7w.cn 的 Official 音频与辅助服务（应用代号 `media_services_33`），
本包只接配乐需要的 4 个接口，其余 25 个不碰。

## 接口（POST /api/v1/apps/media_services_33/<code>，JSON）

  music_generate            model / custom_mode / instrumental     生成音乐
  music_extend              model / audio_id                       延长到目标时长
  music_sounds              model / prompt（+ sound_tempo）        环境音 / 音效
  music_timestamped_lyrics  task_id / audio_id                     带时间戳歌词（要压字幕时用）

  model 枚举（generate / extend 共 9 档）：V4 V4_5 V4_5PLUS V4_5ALL V5 V5_5 V6 V6_MINI V6_WILD
  官方建议 V6 / V6_MINI / V6_WILD，本包默认 V6。
  duration 10-360 秒**只在自定义模式 + V6 系生效**，本包会自动把模式切对。

## 价格口径（必须诚实）

`/api/v1/pricing` 里**没有 media_services_33 的专属规则**，落通配 `*`：

    {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
     "note":"未单独定价的接口：对外 = 上游实际点数 x 2，单笔保底 50 点"}

**2026-11-07 实测**：一次空 body 的提交，账户流水 +60 点 / -60 点（净 0），
也就是说**每笔真会冻结 60 点（对应上游 30 点 x 2），不是规则写的 50 点**。
所以 `cost` 默认按 60 点/次给**下限**，`--upstream` 可以按你观察到的数字换算。

## 探针禁区（本轮 0 点花费换来的结论）

  GET /api/v1/apps/<app>       同步计价，按该应用单价直接扣、**不退** -> 本包从不调用
  POST /apps/<app>/submit      缺必填也会先冻结再退（净 0 但动钱包）
  POST /apps/<app>/<code>      实测同款：空 body 也冻结 60 点再全额退回
  POST /apps/<app>/query       **轮询一次就是一次的钱** -> 本包轮询只走
                               GET /api/v1/tasks/<id>（免费）

  所以 doctor 默认**一个 POST 都不发**：只用 /models /apps /pricing /tasks / 余额
  这些只读接口把 Key、应用、4 个接口、价目、查询路由验一遍，0 冻结。
  想看提交路由是否可达，加 `doctor --probe-post`（会明说冻结 60 点再退回）。

## 子命令

  catalog  现查 29 个音频接口 + 本包 4 个的必填项与 model 枚举（免费）
  cost     先算钱：1 / 3 / 5 条配乐的下限（免费，不联网）
  doctor   自检 Key / 应用 / 4 个接口 / 价目 / 查询路由（免费，0 冻结）
  plan     给时长和 BPM，出分段与卡点方案（免费，不联网，这是"分析节奏"）
  gen      生成配乐（要 --yes，受 --budget 管）
  extend   延长到目标时长（要 --yes，受 --budget 管）
  mix      出 ffmpeg 混音清单（免费，不联网，这是"混音清单"）
  task     查任务 / 取音频直链（免费轮询 GET /api/v1/tasks/<id>）
  log      本地台账

## 用法

  python3 scripts/run.py plan --duration 180 --bpm 92 --style "tension strings"
  python3 scripts/run.py gen  --prompt "紧张的弦乐配乐，低频推进" --duration 180 --yes
  python3 scripts/run.py extend --audio-id <audio_id> --continue-at 180 --yes
  python3 scripts/run.py mix  --video input.mp4 --audio seg-1.mp3 --duration 180
  python3 scripts/run.py task --task-id <task_id> --wait 600

Key：`--key` -> 环境变量 `A7W_API_KEY` -> `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ── GBK 编码兜底 ────────────────────────────────────────────────────────────
# Windows 上 stdout 被管道/重定向时用的是本地编码（cp936），遇到编不出的字符
# 会 UnicodeEncodeError 直接崩。errors='replace' 让它降级成 '?'，不再中断；
# 全包只用 √ / × / 元 这些 cp936 里有的字符，正常情况不会真的被替换。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
APP = "media_services_33"
DEFAULT_MODEL = "V6"

# 价格：通配规则 upstream x 2、保底 50 点；实测每笔冻结 60 点（上游 30）
UPSTREAM_MARKUP = 2
MIN_POINTS = 50
OBSERVED_FREEZE = 60
DEFAULT_UPSTREAM = OBSERVED_FREEZE // UPSTREAM_MARKUP      # 30
DEFAULT_BUDGET = 600          # 点；10 条配乐的下限
MAX_GEN_SECONDS = 360         # duration 上限（schema：10-360）
DEFAULT_BPM = 90

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "soundtrack-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-ai-soundtrack/%s" % VERSION

GEN_MODELS = ["V6", "V6_MINI", "V6_WILD", "V5_5", "V5", "V4_5ALL", "V4_5PLUS", "V4_5", "V4"]
V6_FAMILY = ["V6", "V6_MINI", "V6_WILD"]
SOUND_MODELS = ["V6", "V6_MINI", "V6_WILD", "V5_5", "V5"]
SOUND_KEYS = ["Any", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
              "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "A#m", "Bm"]

# 本包接的 4 个接口：必填项来自应用目录（29 个接口）与 schema 原文
CORE = [
    ("music_generate", "生成音乐", ["model", "custom_mode", "instrumental"],
     "一句风格描述出一段配乐，或按歌词严格唱"),
    ("music_extend", "延长音乐", ["model", "audio_id"],
     "同一首接着往下写，把配乐接到视频时长"),
    ("music_sounds", "生成声音", ["model", "prompt"],
     "环境音 / 转场音效，混音时铺在底下"),
    ("music_timestamped_lyrics", "带时间戳歌词", ["task_id", "audio_id"],
     "逐句时间轴，压字幕或做卡点都靠它"),
]
CORE_CODES = [c[0] for c in CORE]
CORE_NAME = {c[0]: c[1] for c in CORE}

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
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
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


def endpoint(host, api):
    return host + API_PREFIX + "/apps/" + APP + "/" + api


# ───────────────────────── 价格与闸门 ─────────────────────────
def est_points(calls=1, upstream=None):
    """下限：max(保底 50, 上游点数 x 2) x 次数。默认按实测冻结的 60 点/次。"""
    up = DEFAULT_UPSTREAM if upstream is None else int(upstream)
    per = max(MIN_POINTS, int(round(float(up) * UPSTREAM_MARKUP)))
    return per * max(1, int(calls))


def per_call(upstream=None):
    return est_points(1, upstream)


def point_basis(upstream=None):
    up = DEFAULT_UPSTREAM if upstream is None else int(upstream)
    per = max(MIN_POINTS, int(round(float(up) * UPSTREAM_MARKUP)))
    if per == MIN_POINTS:
        return "上游 %d 点 x %d = %d 点，低于通配保底 %d 点，按保底算" % (
            up, UPSTREAM_MARKUP, up * UPSTREAM_MARKUP, MIN_POINTS)
    return "上游 %d 点 x %d = %d 点" % (up, UPSTREAM_MARKUP, per)


def gate(a, calls=1):
    """两道闸门：预算不够 -> 5（一个请求都不发）；没 --yes -> 4。"""
    cost = est_points(calls, getattr(a, "upstream", None))
    if cost > a.budget:
        raise Fail("budget", "下限就要 %d 点，超过 --budget %d 点。一个请求都没发。"
                              "调大 --budget（单位：点，1 元 = 100 点）再试。"
                   % (cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实提交 %d 次配乐生成，**下限 %d 点（%.2f 元）**，"
                              "按上游实际点数 x %d 结算。确认请加 --yes。"
                   % (calls, cost, cost / 100.0, UPSTREAM_MARKUP), EXIT_CONFIRM)
    return cost


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


# ───────────────────────── 免费：catalog ─────────────────────────
def live_codes(a, key, host):
    """GET /api/v1/apps 是应用目录，pricing 里 cost:0，免费。返回 (codes, total)。"""
    if not key:
        return None, None
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, None, 60)
    d = jloads(txt) or {}
    rows = d.get("data") if isinstance(d.get("data"), list) else []
    for r in rows:
        if isinstance(r, dict) and r.get("code") == APP:
            codes = [x.get("code") for x in (r.get("apis") or []) if isinstance(x, dict)]
            return codes, len(rows)
    return [], len(rows)


def cmd_catalog(a, key, host):
    codes, apps_total = None, None
    try:
        codes, apps_total = live_codes(a, key, host)
    except Fail:
        codes = None
    src = "live" if codes is not None else "local"
    rows = []
    for code, name, req, desc in CORE:
        if codes is None:
            online = None
        else:
            online = code in codes
        models = []
        if code in ("music_generate", "music_extend"):
            models = GEN_MODELS
        elif code == "music_sounds":
            models = SOUND_MODELS
        rows.append({"api": code, "name": name, "required": req, "online": online,
                     "models": models, "desc": desc})
    out = {"ok": True, "app": APP, "source": src, "apps_total": apps_total,
           "apis_total": (len(codes) if codes is not None else None),
           "core": rows, "note": "media_services_33 是官方音频与辅助服务，共 29 个接口；"
                                 "本包只接配乐需要的 4 个"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("Official 音频与辅助服务（%s）" % APP)
    if codes is not None:
        print("  现查：%d 个应用，本应用 %d 个接口（GET /api/v1/apps，免费）"
              % (apps_total, len(codes)))
    else:
        print("  离线：没读到 Key，下面是本包内置的契约表（加 --key 可现查）")
    print()
    for r in rows:
        mark = "√" if r["online"] else ("×" if r["online"] is False else "-")
        print("  %s %-26s %s" % (mark, r["api"], r["name"]))
        print("      必填  %s" % ", ".join(r["required"]))
        if r["models"]:
            print("      model %s" % " / ".join(r["models"]))
        print("      用途  %s" % r["desc"])
    print()
    print("  剩下 25 个是 Gemini TTS / ElevenLabs 语音与翻唱类接口，属另一条线。")
    print("  配乐只认这 4 个：一句风格 -> 延长到时长 -> 音效铺底 -> 时间戳做卡点。")
    return 0


# ───────────────────────── 免费：cost ─────────────────────────
def cmd_cost(a, key, host):
    up = getattr(a, "upstream", None)
    calls = a.calls
    floor = est_points(calls, up)
    table = []
    for u in (0, 30, 65, 90):
        table.append({"upstream": u, "per": est_points(1, u),
                      "one": est_points(1, u), "three": est_points(3, u),
                      "five": est_points(5, u)})
    out = {"ok": True, "calls": calls, "upstream": (DEFAULT_UPSTREAM if up is None else up),
           "markup": UPSTREAM_MARKUP, "minPoints": MIN_POINTS,
           "observedFreeze": OBSERVED_FREEZE,
           "estimate": floor, "yuan": round(floor / 100.0, 2), "isLowerBound": True,
           "basis": "pricing 通配：上游实际点数 x 2，单笔保底 50 点；实测每笔冻结 60 点",
           "table": table}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("价格口径（1 元 = 100 点）")
    print("  /api/v1/pricing 里没有 media_services_33 的专属规则，落通配 `*`：")
    print("    对外点数 = 上游实际点数 x %d，单笔保底 %d 点" % (UPSTREAM_MARKUP, MIN_POINTS))
    print("  **实测**：空 body 提交一次，流水 +%d 点 / -%d 点（净 0），"
          % (OBSERVED_FREEZE, OBSERVED_FREEZE))
    print("  所以真会冻结的是 %d 点，比规则写的 %d 点保底高。" % (OBSERVED_FREEZE, MIN_POINTS))
    print()
    print("  本次：%d 次 x 下限 = **%d 点 = %.2f 元**" % (calls, floor, floor / 100.0))
    print("  依据：%s" % point_basis(up))
    print()
    print("  不同上游点数的对照（下限口径）：")
    print("    %-12s %-10s %-10s %-10s %-10s" % ("上游点数", "1 次", "3 次", "5 次", "备注"))
    print("    " + "-" * 54)
    for r in table:
        note = "保底" if r["upstream"] == 0 else ("实测冻结口径" if r["upstream"] == 30 else "")
        print("    %-12s %-10s %-10s %-10s %s" % (
            ("未知" if not r["upstream"] else "%d 点" % r["upstream"]),
            "%d 点" % r["one"], "%d 点" % r["three"], "%d 点" % r["five"], note))
    print()
    print("  这是**下限**：上游真实点数只有真跑一次才看得到，按任务详情结算。")
    print("  换成你观察到的数字：cost --upstream 65 --calls 3")
    return 0


# ───────────────────────── 免费：doctor ─────────────────────────
def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/models", key, None, 60)
    d = jloads(txt) or {}
    ok1 = st == 200 and isinstance(d.get("data"), list)
    checks.append(("Key 有效 + 模型目录可达", ok1,
                   "HTTP %s，目录 %d 条" % (st, len(d.get("data") or []))))

    codes, apps_total = [], 0
    try:
        codes, apps_total = live_codes(a, key, host)
    except Fail as e:
        checks.append(("应用目录可达（GET /api/v1/apps，免费）", False, e.message[:60]))
        codes = None
    if codes is not None:
        miss = [c for c in CORE_CODES if c not in codes]
        checks.append(("应用在架 + 4 个配乐接口齐全", bool(APP) and not miss,
                       "%d 个应用；本应用 %d 个接口%s"
                       % (apps_total, len(codes), "，缺 " + ",".join(miss) if miss else "")))

    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, None, 60)
    d = jloads(txt) or {}
    pr = d.get("pricing") if isinstance(d.get("pricing"), dict) else {}
    wild = pr.get("*") or {}
    dedicated = [k for k in pr if "media_services_33" in k]
    ok3 = (st == 200 and int(wild.get("markupPercent") or 0) == (UPSTREAM_MARKUP - 1) * 100
           and int(wild.get("minPoints") or 0) == MIN_POINTS and not dedicated)
    checks.append(("价目表：落通配（x2，保底 50 点，无专属规则）", ok3,
                   "HTTP %s，通配 markup %s%%，保底 %s 点%s"
                   % (st, wild.get("markupPercent"), wild.get("minPoints"),
                      "，专属规则 " + ",".join(dedicated) if dedicated else "")))

    st, txt = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe",
                        key, None, 60)
    d = jloads(txt) or {}
    ok4 = st == 200 and d.get("code") == 0 and "不存在" in str(d.get("msg") or "")
    checks.append(("任务查询 GET /tasks/<id> 可用（假 id 返回「任务不存在」）", ok4,
                   "HTTP %s %s" % (st, (d.get("msg") or "")[:30])))

    st, txt = http_json("GET", host + API_PREFIX + "/user/balance", key, None, 60)
    d = jloads(txt) or {}
    st2, txt2 = http_json("GET", host + API_PREFIX + "/me/billing", key, None, 60)
    d2 = jloads(txt2) or {}
    ok5 = st == 200 and d.get("available_points") is not None
    checks.append(("余额 / 账单口径可达", ok5,
                   "可用 %s 点，冻结 %s 点，净消费 %s 点"
                   % (fmt_pts(d.get("available_points") or 0), fmt_pts(d.get("frozen") or 0),
                      fmt_pts(d2.get("netConsumedPoints") or 0))))

    if a.probe_post:
        for api in CORE_CODES:
            say("  探 %s（会冻结 %d 点再全额退回）…" % (api, OBSERVED_FREEZE))
            st, txt = http_json("POST", endpoint(host, api), key, {}, a.timeout)
            d = jloads(txt) or {}
            msg = str(d.get("msg") or "")
            ok = st == 200 and d.get("code") == 0 and "缺少必填参数" in msg
            checks.append(("提交路由 %-26s 可达（校验拦下即正确）" % api, ok,
                           "HTTP %s %s" % (st, msg[:60])))

    out = {"ok": all(c[1] for c in checks), "app": APP,
           "endpoint": host + API_PREFIX + "/apps/" + APP + "/<接口code>",
           "taskEndpoint": host + API_PREFIX + "/tasks/<task_id>",
           "probePost": bool(a.probe_post),
           "priceRule": {"markup": UPSTREAM_MARKUP, "minPoints": MIN_POINTS,
                         "observedFreeze": OBSERVED_FREEZE, "isLowerBound": True},
           "frozenPoints": (OBSERVED_FREEZE if a.probe_post else 0),
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（默认 0 个 POST：只读 /models /apps /pricing /tasks / 余额，0 冻结）")
    print()
    for n, o, dt in checks:
        print("  %s %-46s %s" % ("√" if o else "×", n, dt))
    print()
    print("  端点：POST %s" % out["endpoint"])
    print("  查询：GET  %s（轮询只走这条，免费）" % out["taskEndpoint"])
    print("  价格：上游点数 x %d，保底 %d 点；实测每笔冻结 %d 点（下限，按任务详情结算）"
          % (UPSTREAM_MARKUP, MIN_POINTS, OBSERVED_FREEZE))
    if a.probe_post:
        print("  提醒：本次开了 --probe-post，%d 条提交路由各冻结过 %d 点，已全额退回。"
              % (len(CORE_CODES), OBSERVED_FREEZE))
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 免费：plan（分析节奏） ─────────────────────────
def bar_seconds(bpm):
    """4/4 拍：一小节 = 4 拍。"""
    return 60.0 / float(max(20, min(300, int(bpm)))) * 4.0


def _fmt_sec(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def cmd_plan(a, key, host):
    dur = float(a.duration or 0)
    if dur <= 0:
        raise Fail("usage", "给个视频时长：--duration 180（秒）。"
                              "拿不到时长就先 ffprobe -show_entries format=duration。", EXIT_USAGE)
    bpm = int(a.bpm)
    bar = bar_seconds(bpm)
    bars = max(1, int(round(dur / bar)))
    snapped = bars * bar
    up = getattr(a, "upstream", None)

    cuts = []
    if a.shots:
        for tok in a.shots.replace(";", ",").split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                t = float(tok)
            except ValueError:
                raise Fail("usage", "--shots 要逗号分隔的秒数，例如 12,34,56.5（当前 %s）"
                           % tok, EXIT_USAGE)
            k = max(0, int(round(t / bar)))
            boundary = k * bar
            cuts.append({"at": round(t, 2), "bar": k, "snapped": round(boundary, 2),
                         "offset": round(boundary - t, 2)})

    segs = []
    n = 1 if dur <= MAX_GEN_SECONDS else int(math.ceil(dur / float(MAX_GEN_SECONDS)))
    chunk = dur / float(n)
    for i in range(n):
        s = round(i * chunk, 2)
        e = round(dur if i == n - 1 else (i + 1) * chunk, 2)
        role = "整段" if n == 1 else ("前奏" if i == 0 else ("尾声" if i == n - 1 else "主体"))
        segs.append({"index": i + 1, "role": role, "start": s, "end": e,
                     "seconds": round(e - s, 2),
                     "bars": max(1, int(round((e - s) / bar))),
                     "call": "music_generate" if i == 0 else "music_extend",
                     "style": a.style or a.prompt or "（同第一段，保持同一首）"})

    calls = len(segs)
    cost = est_points(calls, up)
    fade_in = round(min(1.5, max(0.5, dur / 40.0)), 2)
    fade_out = round(min(3.0, max(1.0, dur / 30.0)), 2)
    files = ["seg-%d.mp3" % s["index"] for s in segs]
    mix = build_mix(dur, files, a.video, a.out, a.level, fade_in, fade_out)

    out = {"ok": True, "duration": dur, "bpm": bpm, "barSeconds": round(bar, 3),
           "bars": bars, "snappedSeconds": round(snapped, 2),
           "segments": segs, "calls": calls, "estimatePoints": cost,
           "yuan": round(cost / 100.0, 2), "isLowerBound": True,
           "basis": point_basis(up), "cuts": cuts,
           "fade": {"in": fade_in, "out": fade_out},
           "mix": mix}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("配乐方案（不联网、不花钱，先看结构再决定跑不跑）")
    print()
    print("  视频   %s 秒（%d 分 %d 秒）" % (_fmt_sec(dur), int(dur // 60), int(dur % 60)))
    print("  节奏   %d BPM，4/4 拍，一小节 %.3f 秒" % (bpm, bar))
    print("  对齐   %d 小节 = %.2f 秒（差 %.2f 秒，剪辑时按这个收口最顺）"
          % (bars, snapped, snapped - dur))
    print()
    print("  分段   %-4s %-6s %-9s %-9s %-6s %s"
          % ("#", "角色", "起", "止", "小节", "调用"))
    print("  " + "-" * 66)
    for s in segs:
        print("  %-5s %-7s %-9s %-9s %-6s %s" % (
            s["index"], s["role"], _fmt_sec(s["start"]), _fmt_sec(s["end"]),
            s["bars"], s["call"]))
    print()
    if cuts:
        print("  卡点   切点 -> 最近小节边界（把切点吸到边界，鼓点才咬得住画面）")
        for c in cuts[:12]:
            print("    %7.2f 秒 -> 第 %2d 小节 = %8.2f 秒  偏移 %+.2f 秒"
                  % (c["at"], c["bar"], c["snapped"], c["offset"]))
        if len(cuts) > 12:
            print("    … 另有 %d 个切点，用 --json 取全量" % (len(cuts) - 12))
        print()
    print("  花费   下限 %d 次 x %d 点 = **%d 点 = %.2f 元**（%s）"
          % (calls, per_call(up), cost, cost / 100.0, point_basis(up)))
    print("  淡入淡出  %.2f 秒 / %.2f 秒" % (fade_in, fade_out))
    print()
    print("  下一步：")
    if a.style or a.prompt:
        print("    python3 scripts/run.py gen --prompt \"%s\" --duration %d --yes"
              % (a.style or a.prompt, min(int(dur), MAX_GEN_SECONDS)))
    else:
        print("    python3 scripts/run.py gen --prompt \"你的风格描述\" --duration %d --yes"
              % min(int(dur), MAX_GEN_SECONDS))
    if calls > 1:
        print("    python3 scripts/run.py extend --audio-id <上一段 audio_id> --continue-at %d --yes"
              % MAX_GEN_SECONDS)
    print("    python3 scripts/run.py mix --video %s --audio %s --duration %s"
          % (a.video or "input.mp4", " --audio ".join(files), _fmt_sec(dur)))
    return 0


# ───────────────────────── 免费：mix（混音清单） ─────────────────────────
def build_mix(duration, audios, video=None, out="out.mp4", level=0.35,
              fade_in=1.5, fade_out=2.5):
    """拼一条 ffmpeg 命令：逐段淡入 -> concat -> 控音量 -> 循环/裁剪到视频时长 -> 尾部淡出。"""
    n = max(1, len(audios))
    chains = []
    for i in range(n):
        fi = fade_in if i == 0 else 0.5
        chains.append("[%d:a]asetpts=N/SR/TB,afade=t=in:st=0:d=%.2f[a%d]" % (i + 1, fi, i + 1))
    labels = "".join("[a%d]" % (i + 1) for i in range(n))
    if n > 1:
        chains.append("%sconcat=n=%d:v=0:a=1,volume=%.2f[am]" % (labels, n, level))
    else:
        chains.append("%svolume=%.2f[am]" % (labels, level))
    st_out = max(0.0, duration - fade_out)
    chains.append("[am]aloop=loop=-1:size=2e9,atrim=0:%.2f,asetpts=N/SR/TB,"
                  "afade=t=out:st=%.2f:d=%.2f[aout]"
                  % (duration, st_out, fade_out))
    fc = ";".join(chains)
    ins = " ".join('-i "%s"' % p for p in audios)
    cmd = ('ffmpeg -y -i "%s" %s -filter_complex "%s" '
           '-map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -shortest "%s"'
           % (video or "input.mp4", ins, fc, out))
    steps = [
        "每条音轨先按 start 对齐（asetpts），起播不拖拍",
        "第 1 条淡入 %.2f 秒，其余 %.2f 秒，接缝不炸" % (fade_in, 0.5),
        "concat 按顺序拼接，全程统一音量 %.2f" % level,
        "不够长就 aloop 循环，最后 atrim 到 %.2f 秒（= 视频时长，画面不动声音刚好收口）" % duration,
        "尾部 %.2f 秒淡出，落在 %s 秒" % (fade_out, _fmt_sec(st_out)),
        "视频流 copy 不重编码，只编音频（aac 192k），10 分钟片子几十秒跑完",
    ]
    return {"cmd": cmd, "filter": fc, "steps": steps, "duration": duration,
            "inputs": n, "level": level, "fadeIn": fade_in, "fadeOut": fade_out,
            "out": out, "video": video or "input.mp4"}


def cmd_mix(a, key, host):
    dur = float(a.duration or 0)
    if dur <= 0:
        raise Fail("usage", "给视频时长：--duration 180（秒）", EXIT_USAGE)
    audios = list(a.audio or [])
    if not audios:
        audios = ["seg-1.mp3"]
    for p in audios:
        if not os.path.isfile(p) and not a.allow_missing:
            raise Fail("usage", "找不到音频 %s。先把生成的配乐下载到本地，"
                                  "或加 --allow-missing 只出清单不校验文件。" % p, EXIT_USAGE)
    m = build_mix(dur, audios, a.video, a.out, a.level, a.fade_in, a.fade_out)
    out = {"ok": True, "kind": "mix-plan", "dryRun": True, **m}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("混音清单（只出命令，不执行、不花钱）")
    print()
    print("  视频  %s（%.2f 秒）" % (m["video"], dur))
    print("  音频  %s" % " + ".join(audios))
    print("  输出  %s" % m["out"])
    print()
    print("  ffmpeg 命令：")
    print()
    print("  " + m["cmd"])
    print()
    print("  每一步在干什么：")
    for i, s in enumerate(m["steps"], 1):
        print("    %d. %s" % (i, s))
    print()
    print("  想要更贴画面：mix --duration %.0f --audio seg-1.mp3 --level 0.28"
          " --fade-out 3" % dur)
    return 0


# ───────────────────────── 任务与结果 ─────────────────────────
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


def get_task(a, key, host, task_id):
    """只走 GET /api/v1/tasks/<id>。应用层 /query 每调一次就算一次钱，全包不碰。"""
    d = api_get(a, key, host, API_PREFIX + "/tasks/" + urllib.parse.quote(task_id, safe=""))
    if not isinstance(d, dict):
        raise Fail("call", "任务 %s 查不到（返回为空）。" % task_id, EXIT_CALL)
    return d


def wait_task(a, key, host, task_id):
    deadline = time.time() + max(30, a.wait)
    last = None
    while time.time() < deadline:
        time.sleep(max(1, a.every))
        d = get_task(a, key, host, task_id)
        st = str(d.get("status") or "").lower()
        if st != last:
            say("  状态：%s（轮询走 GET /tasks/<id>，免费）" % (st or "?"))
            last = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            return d
    raise Fail("call", "等了 %d 秒还没完成。任务没丢——用 `task --task-id %s` 接着取，"
                       "**不要重新提交**（会再冻结一次）。" % (a.wait, task_id), EXIT_CALL)


def _finish(a, key, host, api, body, cost, t0):
    say("已提交（%s）… 等结果" % api)
    data = api_post(a, key, host, api, body, timeout=max(60, a.timeout))
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if not task_id:
        out = {"ok": True, "api": api, "sync": True, "data": data,
               "estimatedPoints": cost, "isLowerBound": True}
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": api, "ok": True,
                    "task_id": None, "model": body.get("model"), "pointsFloor": cost})
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
               "estimatedPoints": cost, "isLowerBound": True,
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
    usage = t.get("usage") if isinstance(t.get("usage"), dict) else {}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": api, "ok": st in TERMINAL_OK,
           "task_id": task_id, "model": body.get("model"), "status": st,
           "audio_ids": [r["audio_id"] for r in rows if r["audio_id"]],
           "audio_urls": [r["audio_url"] for r in rows],
           "elapsed": round(dt, 1), "pointsFloor": cost, "usage": usage}
    ledger_add(rec)
    out = {"ok": st in TERMINAL_OK, "api": api, "task_id": task_id, "status": st,
           "elapsed": round(dt, 1), "audios": rows, "pointsFloor": cost,
           "usage": usage, "error": t.get("error")}
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
        print("  这条返回里没解析到音频地址，原始返回如下（用 task --task-id 可再看）：")
        print(json.dumps(t, ensure_ascii=False, indent=1)[:2500])
        return EXIT_CALL
    for i, r in enumerate(rows, 1):
        print()
        print("  #%d %s" % (i, r.get("title") or ""))
        if r.get("audio_id"):
            print("      audio_id：%s  <- 延长 / 取时间戳歌词都要它" % r["audio_id"])
        if r.get("duration"):
            print("      时长：%s 秒" % r["duration"])
        print("      音频：%s" % r["audio_url"])
    if usage:
        print()
        print("  上游用量：%s" % json.dumps(usage, ensure_ascii=False))
    print("  计费：按上游实际点数 x %d 结算，下限 %d 点（实测每笔冻结 %d 点）"
          % (UPSTREAM_MARKUP, cost, OBSERVED_FREEZE))
    return 0


def cmd_task(a, key, host):
    _need(a, "task-id")
    t = get_task(a, key, host, a.task_id)
    st = str(t.get("status") or "").lower()
    rows = find_audio(t)
    out = {"ok": True, "task_id": a.task_id, "status": st, "audios": rows,
           "usage": t.get("usage")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (st or "?"))
    if rows:
        for i, r in enumerate(rows, 1):
            print("  #%d %s" % (i, r.get("title") or ""))
            if r.get("audio_id"):
                print("      audio_id：%s  <- 延长时给 --audio-id" % r["audio_id"])
            if r.get("duration"):
                print("      时长：%s 秒" % r["duration"])
            print("      音频：%s" % r["audio_url"])
    else:
        print("  还没解析到音频（任务没完成时属正常）。")
    if t.get("usage"):
        print("  上游用量：%s" % json.dumps(t["usage"], ensure_ascii=False))
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
        raise Fail("usage", "%s 要在 %d–%d 之间（当前 %s）" % (name, lo, hi, val), EXIT_USAGE)


def _dry(a, host, api, body, cost, calls=1):
    url = endpoint(host, api)
    out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
           "estimatedPoints": cost, "isLowerBound": True, "calls": calls}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不冻结、不扣费）")
    print("  端点：%s" % url)
    print("  请求：%s" % json.dumps(body, ensure_ascii=False))
    print("  下限：%d 点（%.2f 元）—— 上游实际点数 x %d，实测每笔冻结 %d 点"
          % (cost, cost / 100.0, UPSTREAM_MARKUP, OBSERVED_FREEZE))
    return 0


# ───────────────────────── gen ─────────────────────────
def cmd_gen(a, key, host):
    _check_model(a.model, GEN_MODELS, "music_generate")
    if a.duration is not None:
        _check_range("--duration", a.duration, 10, MAX_GEN_SECONDS)
        if a.model not in V6_FAMILY:
            raise Fail("usage", "--duration 只在 V6 系生效（%s），当前 %s。"
                                  "加 --model V6，或去掉 --duration 让上游按默认时长出。"
                       % (" / ".join(V6_FAMILY), a.model), EXIT_USAGE)
        if not a.custom:
            a.custom = True
            say("  --duration 只在自定义模式下生效，已自动切到 --custom")
    if a.custom:
        if not (a.style or a.lyrics or a.prompt):
            raise Fail("usage", "自定义模式要给 --style（风格标签），"
                                  "例如 --style \"tension strings, low pulse\"。", EXIT_USAGE)
        if not a.style and a.prompt:
            a.style, a.prompt = a.prompt, None      # 自定义模式下 style 才是风格标签
        if not a.title:
            a.title = "配乐-%s" % time.strftime("%H%M%S")
    elif not (a.prompt or a.style or a.lyrics):
        raise Fail("usage", "给一句提示词：--prompt \"紧张的弦乐配乐，低频推进\"。", EXIT_USAGE)
    if a.title and len(a.title) > 80:
        raise Fail("usage", "--title 最多 80 字符（当前 %d）。" % len(a.title), EXIT_USAGE)
    _check_range("--variety", a.variety, 0, 4)
    _check_range("--style-weight", a.style_weight, 0, 1)
    _check_range("--weirdness", a.weirdness, 0, 1)

    body = {"model": a.model, "custom_mode": bool(a.custom),
            "instrumental": (not a.vocal)}
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


# ───────────────────────── extend ─────────────────────────
def cmd_extend(a, key, host):
    _need(a, "audio-id")
    _check_model(a.model, GEN_MODELS, "music_extend")
    if a.continue_at is not None and a.continue_at <= 0:
        raise Fail("usage", "--continue-at 要大于 0（从原曲第几秒接下去）。", EXIT_USAGE)
    _check_range("--variety", a.variety, 0, 4)

    body = {"model": a.model, "audio_id": a.audio_id}
    if not (a.vocal or a.lyrics or a.prompt):
        body["instrumental"] = True        # 配乐线的默认：续写纯音乐
    for k, v in (("style", a.style), ("title", a.title), ("lyrics", a.lyrics),
                 ("prompt", a.prompt), ("continue_at", a.continue_at),
                 ("variety", a.variety), ("persona_id", a.persona_id),
                 ("negative_tags", a.negative_tags), ("vocal_gender", a.vocal_gender)):
        if v is not None and v != "":
            body[k] = v

    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_extend", body, cost)
    return _finish(a, key, host, "music_extend", body, cost, time.time())


# ───────────────────────── sound ─────────────────────────
def cmd_sound(a, key, host):
    _need(a, "prompt")
    _check_model(a.model, SOUND_MODELS, "music_sounds")
    if len(a.prompt) > 500:
        raise Fail("usage", "--prompt 最多 500 字符（当前 %d）。" % len(a.prompt), EXIT_USAGE)
    _check_range("--tempo", a.tempo, 1, 300)
    # sound_tempo 在 schema 里标「可选、默认 Auto」，上游却按类型校验 ——
    # 实测省掉它直接报「input.sound_tempo: 类型不正确」，所以本包总是显式传。
    body = {"model": a.model, "prompt": a.prompt,
            "sound_key": a.sound_key, "sound_tempo": a.tempo}
    if a.loop:
        body["sound_loop"] = True
    cost = gate(a, 1)
    if a.dry_run:
        return _dry(a, host, "music_sounds", body, cost)
    return _finish(a, key, host, "music_sounds", body, cost, time.time())


# ───────────────────────── log ─────────────────────────
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
        print("  %s  %-26s %-10s %-22s 下限 %s 点" % (
            e.get("at"), e.get("api") or "-", e.get("status") or "-",
            (e.get("task_id") or "-")[:22], e.get("pointsFloor")))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · AI 配乐（分析节奏 -> 生成音乐 -> 配到时长 -> 混音清单）",
        epilog="端点：POST %s/api/v1/apps/media_services_33/<接口code> · "
               "GET %s/api/v1/tasks/<task_id>（轮询只走这条，免费）"
               % (DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--upstream", type=int, default=None,
                    help="上游点数（算下限用；默认 %d = 实测冻结 %d 点）"
                         % (DEFAULT_UPSTREAM, OBSERVED_FREEZE))
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="现查 29 个音频接口 + 本包 4 个的契约（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：1/3/5 次配乐的下限（免费，不联网）",
                       allow_abbrev=False)
    p.add_argument("--calls", type=int, default=1, help="要跑几次（默认 1）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 4 个接口 / 价目（免费，0 冻结）",
                       allow_abbrev=False)
    p.add_argument("--probe-post", dest="probe_post", action="store_true",
                   help="额外探 4 条提交路由（每条冻结 %d 点后全额退回）" % OBSERVED_FREEZE)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("plan", help="给时长和 BPM，出分段与卡点方案（免费，不联网）",
                       allow_abbrev=False)
    p.add_argument("--duration", type=float, help="视频时长秒数（必填）")
    p.add_argument("--bpm", type=int, default=DEFAULT_BPM, help="节奏 BPM（默认 90）")
    p.add_argument("--shots", help="镜头切点秒数，逗号分隔，例如 12,34,56.5")
    p.add_argument("--style", help="风格标签，写进方案的调用建议")
    p.add_argument("--prompt", help="一句风格描述（同 --style，二选一）")
    p.add_argument("--video", help="视频文件名（写进 mix 命令，默认 input.mp4）")
    p.add_argument("--out", default="out.mp4", help="成片文件名（默认 out.mp4）")
    p.add_argument("--level", type=float, default=0.35, help="配乐音量 0-1（默认 0.35）")
    p.set_defaults(fn=cmd_plan)

    def add_paid(p, with_model=True, models=None):
        if with_model:
            p.add_argument("--model", default=DEFAULT_MODEL,
                           help="model：%s（默认 %s）"
                                % ("/".join(models or GEN_MODELS), DEFAULT_MODEL))
        p.add_argument("--yes", action="store_true", help="确认真实计费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.add_argument("--no-wait", action="store_true", help="只提交，拿 task_id 就走")
        p.add_argument("--wait", type=int, default=600, help="等结果的上限秒数（默认 600）")
        p.add_argument("--every", type=int, default=5, help="轮询间隔秒数（默认 5）")
        p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数")

    p = sub.add_parser("gen", help="生成配乐（一句话出一段，要 --yes）", allow_abbrev=False)
    add_paid(p)
    p.add_argument("--prompt", help="一句风格描述（非自定义模式）")
    p.add_argument("--custom", action="store_true", help="自定义模式（自己给风格/歌词）")
    p.add_argument("--style", help="风格标签，例如 tension strings / 国风 / lo-fi")
    p.add_argument("--lyrics", help="歌词（自定义模式下用）")
    p.add_argument("--title", help="标题（自定义模式下给，缺省自动生成）")
    p.add_argument("--duration", type=int, default=None,
                   help="目标时长 10-%d 秒（只在 V6 系 + 自定义模式生效）" % MAX_GEN_SECONDS)
    p.add_argument("--vocal", action="store_true",
                   help="带人声（默认纯音乐，配乐用 instrumental=true）")
    p.add_argument("--variety", type=int, default=None, help="多样性 0-4（默认 1）")
    p.add_argument("--negative-tags", dest="negative_tags", help="要避开的风格")
    p.add_argument("--vocal-gender", dest="vocal_gender", choices=["m", "f"],
                   help="人声性别偏好")
    p.add_argument("--persona-id", dest="persona_id", help="套用某个 Persona")
    p.add_argument("--style-weight", dest="style_weight", type=float, default=None,
                   help="风格遵循强度 0-1")
    p.add_argument("--weirdness", type=float, default=None, help="创意偏离 0-1")
    p.set_defaults(fn=cmd_gen)

    p = sub.add_parser("extend", help="延长到目标时长（接上一段往下写，要 --yes）",
                       allow_abbrev=False)
    add_paid(p)
    p.add_argument("--audio-id", dest="audio_id", help="要延长的 audio_id（必填）")
    p.add_argument("--continue-at", dest="continue_at", type=float, default=None,
                   help="从原曲第几秒接下去")
    p.add_argument("--style", help="延续的风格")
    p.add_argument("--lyrics", help="续写的歌词")
    p.add_argument("--prompt", help="续写描述")
    p.add_argument("--title", help="标题")
    p.add_argument("--vocal", action="store_true", help="续写带人声（默认纯音乐）")
    p.add_argument("--variety", type=int, default=None, help="多样性 0-4")
    p.add_argument("--negative-tags", dest="negative_tags", help="要避开的风格")
    p.add_argument("--vocal-gender", dest="vocal_gender", choices=["m", "f"])
    p.add_argument("--persona-id", dest="persona_id", help="套用某个 Persona")
    p.set_defaults(fn=cmd_extend)

    p = sub.add_parser("sound", help="环境音 / 转场音效（要 --yes）", allow_abbrev=False)
    add_paid(p, models=SOUND_MODELS)
    p.add_argument("--prompt", help="声音描述，<=500 字符（必填）")
    p.add_argument("--sound-key", dest="sound_key", default="Any", choices=SOUND_KEYS,
                   help="调性（默认 Any = 自动）")
    p.add_argument("--tempo", type=int, default=120,
                   help="速度 BPM 1-300（默认 120；本包总是显式传，见 references）")
    p.add_argument("--loop", action="store_true", help="可循环")
    p.set_defaults(fn=cmd_sound)

    p = sub.add_parser("mix", help="出 ffmpeg 混音清单（免费，不联网）", allow_abbrev=False)
    p.add_argument("--video", help="视频文件名（默认 input.mp4）")
    p.add_argument("--audio", action="append", help="音频文件，可重复给多次，按顺序拼")
    p.add_argument("--duration", type=float, help="视频时长秒数（必填）")
    p.add_argument("--out", default="out.mp4", help="成片文件名（默认 out.mp4）")
    p.add_argument("--level", type=float, default=0.35, help="配乐音量 0-1（默认 0.35）")
    p.add_argument("--fade-in", dest="fade_in", type=float, default=1.5,
                   help="开头淡入秒数（默认 1.5）")
    p.add_argument("--fade-out", dest="fade_out", type=float, default=2.5,
                   help="结尾淡出秒数（默认 2.5）")
    p.add_argument("--allow-missing", dest="allow_missing", action="store_true",
                   help="不校验音频文件是否存在，只出清单")
    p.set_defaults(fn=cmd_mix)

    p = sub.add_parser("task", help="查任务 / 取音频直链（免费，GET /tasks/<id>）",
                       allow_abbrev=False)
    p.add_argument("--task-id", dest="task_id", help="提交时返回的 task_id")
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


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_mix", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("budget", DEFAULT_BUDGET), ("upstream", None),
                       ("max_tokens", 0), ("json", False)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
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
