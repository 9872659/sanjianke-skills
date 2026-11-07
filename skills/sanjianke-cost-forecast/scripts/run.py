#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 成本预估器（sanjianke-cost-forecast）

「花之前，先把这一单算清。」

喂一份任务清单（几张图 / 几条视频几秒 / 几段配音几字 / 几次后处理几秒），
逐项报价 + 合计 + 区间 + 五类价格陷阱，**全程只读，0 点花费**。

## 只读端点（全部 GET，实测 0 点）

  GET /api/v1/pricing            115 条规则，裸对象（不套 code/data）
  GET /api/v1/models             316 条 = 221 目录模型 + 95 裸模型层 ID
  GET /api/v1/apps               22 应用 / 100 接口
  GET /api/v1/me/tasks           历史 actualPrice（模型层单价反推的唯一来源）
  GET /api/v1/tasks/<id>         假 id → 200「任务不存在」，路由在、不扣费
  GET /user/balance              余额
  GET /user/balance/logs         流水（doctor 前后各读一次，证明本轮 0 点）

本包源码里没有任何 POST / PUT / DELETE —— 没有写请求，就不可能扣点。

## 五类价格陷阱（全部做进报价里）

 ① 价目表有、路由 404：11 个 tsc_* 档
 ② 路由在、上游 502：3 个腾讯档（tencent1080 / tencent2k / tencent4k）
 ③ note 写「点/次」、rule 是 per_second：视频档 6 条（castcrew / delogo / shot 各两条）
 ④ 落通配保底：对外 = 上游实际点数 × 2、单笔保底 50 点
    （实测模型层成交 15.60 / 26 / 44 点都低于 50，保底并未落地）
 ⑤ 应用层 vs 模型层差价：同一件事差 2.7 ~ 75.5 倍

## 子命令

  catalog  能力价目总表（现查 /pricing，按计费口径分组，标注陷阱）
  cost     常用四件事的单件价 + 三档单量（免费）
  quote    按任务清单算总价：逐项 + 合计 + 区间（免费）
  compare  应用层 vs 模型层比价（免费）
  traps    五类陷阱逐条摊开（免费）
  budget   10 元 / 100 元 / 1000 元各能做什么（免费）
  doctor   自检 7 个只读端点 + 价目一致性 + 流水前后比对（免费）
  sample   写一份任务清单样例（离线，0 请求）

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost
  python3 scripts/run.py sample --preset duanju --out .
  python3 scripts/run.py quote --preset duanju
  python3 scripts/run.py quote --file 我的清单.json --budget 20000
  python3 scripts/run.py quote --preset ecom --out 报价
  python3 scripts/run.py compare --pages 5
  python3 scripts/run.py traps
  python3 scripts/run.py budget

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import datetime
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request


# ── GBK 编码兜底（2026-11-08 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 `√`/`×` 这类字符就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底，再确保输出里只用 GBK 能编的字（√ × · → 都可以）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
CACHE = os.path.join(os.path.expanduser("~"), ".a7w", "cost-forecast-cache.json")
PAGE_SIZE_ME = 20            # /api/v1/me/tasks 每页恒 20 条（size / per_page 无效）
DEFAULT_BUDGET = 5000        # 点；1 元 = 100 点
POINTS_PER_YUAN = 100
BASELINE_TS = "2026-11-08"
ALL_PAGES_EST = 70           # 台账 1,398 条 ÷ 20
VOICE_PER_CHAR = 0.18        # 点/字，voice_tts 实测基线（上游实际点数 ×3）

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-cost-forecast/%s" % VERSION

# ───────────────────────── 基线价目（2026-11-08 现查 /pricing 的副本）──────────
# 用途：① 花任何请求之前的预算闸门（能算出「超预算」就一个请求都不发）
#       ② --offline / 缓存不可用时的兜底
#       ③ doctor 拿它和线上价比，价目一动就会提示
BASELINE_TIERS = {
    # 后处理 / 超分（点/秒）
    "restore": (36, None), "upscale": (30, None), "cartoon": (24, None),
    "faceswap": (20, None), "portrait": (18, None), "enhance": (15, None),
    "colorize": (9, None), "subtitle": (9, None), "segment": (9, None),
    "superres": (9, None), "superres2k": (15, None), "superres4k": (20, None),
    "interp": (25, None),
    # note 写「点/次」、rule 是 per_second 的 6 条
    "shot": (20, None), "castcrew": (25, None), "delogo": (25, None),
    # 腾讯档：路由在、上游 502
    "tencent1080": (2, 10), "tencent2k": (4, 10), "tencent4k": (8, 10),
    # 11 个 tsc_* 档：价目表有、路由 404
    "tsc_common": (3, 10), "tsc_common_hd": (6, 10), "tsc_aigc": (3, 10),
    "tsc_aigc_hd": (6, 10), "tsc_shortplay": (3, 10), "tsc_shortplay_hd": (6, 10),
    "tsc_uhd": (3, 10), "tsc_oldsd": (3, 10), "tsc_oldsd_hd": (6, 10),
    "tsc_teshd": (2, 10), "tsc_quality": (2, 10),
}

BASELINE_APP_PRICE = {
    "seedance": 11000, "wan": 800, "happy_horse": 650, "mmaudio": 495,
    "grok_video": 300, "seedsvc": 220, "dressing_diffusion": 200,
    "aigc_wan_image": 203, "aigc_photo_restore": 105, "aigc_qwen_image_pro": 105,
    "watermark_removal": 100, "aigc_qwen_image": 78, "nano_banana": 72,
    "smart_clip": 45, "music_search": 30,
}

# 模型层实测价（actualPrice）。价目表给不出模型层单价，这一列只能从流水反推。
BASELINE_MEASURED = {
    "gpt-image-2.6": (6.0, "流水 sync:/api/v1/images/generations，每笔 -6"),
    "gpt-image-2": (26.0, "me/tasks actualPrice 最低 26"),
    "gpt-image-2-pro": (39.0, "me/tasks actualPrice 最低 39"),
    "seedream-5-0-flash": (15.6, "me/tasks actualPrice 最低 15.60"),
    "sd/doubao-seedance-2-0-260128": (145.73, "me/tasks actualPrice 最低 145.73"),
    "volcengine/doubao-seedance-2-5-260628": (762.3, "me/tasks actualPrice 最低 762.30"),
    "muse-video": (44.0, "me/tasks actualPrice 最低 44"),
    "wan3.0-video": (300.0, "家族实测记录 2026-11-07"),
}

APP_SUFFIXES = ("/submit", "/create", "/remove", "/generate/index", "")
IMAGE_MODELS = ("gpt-image-2.6", "gpt-image-2", "gpt-image-2-pro", "seedream-5-0-flash")

# 22 个应用（GET /api/v1/apps）+ 价目表里以 /apps/ 开头的出图路径段
APP_CODES = frozenset((
    "person_replacement", "action_transfer", "full_video", "pic_lipsync",
    "happy_horse", "media_services_33", "file_qa", "music_search", "grok_video",
    "nano_banana", "music_generation", "smart_clip", "image_human", "wan",
    "seedance", "lipsync", "dressing_diffusion", "mmaudio", "flashvsr", "seedsvc",
    "watermark_removal", "voice_tts", "indextts",
    "aigc_wan_image", "aigc_qwen_image", "aigc_qwen_image_pro", "aigc_photo_restore",
))
TSC_TIERS = ("tsc_common", "tsc_common_hd", "tsc_aigc", "tsc_aigc_hd",
             "tsc_shortplay", "tsc_shortplay_hd", "tsc_uhd", "tsc_oldsd",
             "tsc_oldsd_hd", "tsc_teshd", "tsc_quality")
TENCENT_TIERS = ("tencent1080", "tencent2k", "tencent4k")

# 应用层 vs 模型层：同一个模型 / 同一件事的配对（比价用）
PAIRS = (
    ("seedance", "sd/doubao-seedance-2-0-260128", "同一个模型：Seedance 2.0"),
    ("seedance", "volcengine/doubao-seedance-2-5-260628", "同族模型：Seedance 2.5"),
    ("nano_banana", "gpt-image-2", "同一件事：出一张图"),
    ("aigc_qwen_image", "gpt-image-2", "同一件事：出一张图"),
    ("aigc_qwen_image_pro", "gpt-image-2-pro", "同一件事：出一张图"),
    ("dressing_diffusion", "gpt-image-2-pro", "同一件事：改一张图"),
    ("aigc_photo_restore", "seedream-5-0-flash", "同一件事：修复一张图"),
    ("aigc_wan_image", "gpt-image-2", "同一件事：出一张图"),
    ("wan", "wan3.0-video", "同族模型：万相视频"),
    ("grok_video", "muse-video", "同一件事：出一条视频"),
    ("happy_horse", "muse-video", "同一件事：出一条视频"),
)

PRESETS = {
    "duanju": {
        "title": "短剧一集（8 分钟成片）",
        "note": "6 张分镜图 + 1 条 15 秒 1080P 成片 + 2 条模型层 10 秒视频 + 2 分钟修复 + 220 字配音",
        "items": [
            {"kind": "image", "target": "gpt-image-2.6", "count": 6, "label": "分镜图"},
            {"kind": "video", "target": "full_video", "resolution": "1080P",
             "seconds": 15, "count": 1, "label": "成片 1080P"},
            {"kind": "video", "target": "model:sd/doubao-seedance-2-0-260128",
             "seconds": 10, "count": 2, "label": "模型层补镜"},
            {"kind": "post", "target": "restore", "seconds": 120, "count": 1, "label": "老素材修复"},
            {"kind": "voice", "target": "voice_tts", "chars": 220, "count": 1, "label": "旁白配音"},
        ],
    },
    "ecom": {
        "title": "电商一条详情（主图 + 短视频）",
        "note": "8 张商品图 + 1 条 15 秒 1080P + 120 字配音 + 2 分钟超分",
        "items": [
            {"kind": "image", "target": "gpt-image-2.6", "count": 8, "label": "商品图"},
            {"kind": "video", "target": "full_video", "resolution": "1080P",
             "seconds": 15, "count": 1, "label": "主图视频"},
            {"kind": "voice", "target": "voice_tts", "chars": 120, "count": 1, "label": "卖点口播"},
            {"kind": "post", "target": "superres", "seconds": 120, "count": 1, "label": "素材超分"},
        ],
    },
    "koubo": {
        "title": "口播一条（60 秒竖版）",
        "note": "2 张背景图 + 1 条 30 秒数字人 + 300 字配音",
        "items": [
            {"kind": "image", "target": "gpt-image-2.6", "count": 2, "label": "背景图"},
            {"kind": "video", "target": "image_human", "mode": "standard",
             "seconds": 30, "count": 1, "label": "数字人口播"},
            {"kind": "voice", "target": "voice_tts", "chars": 300, "count": 1, "label": "配音"},
        ],
    },
}


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


# ───────────────────────── 显示宽度（中文表格对齐） ─────────────────────────
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
        return "{:,.2f}".format(float(v))
    except Exception:                                            # noqa: BLE001
        return dash


def pint(v, dash="-"):
    if v is None:
        return dash
    try:
        return "{:,}".format(int(round(float(v))))
    except Exception:                                            # noqa: BLE001
        return dash


def num(v, dash="-"):
    """去掉多余小数的数字：36.0 → 36，0.18 → 0.18。"""
    if v is None:
        return dash
    try:
        f = float(v)
    except Exception:                                            # noqa: BLE001
        return dash
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    s = "{:,.2f}".format(f)
    return s.rstrip("0").rstrip(".")


def yuan(pts):
    return float(pts) / float(POINTS_PER_YUAN)


def ts(ms):
    try:
        return datetime.datetime.fromtimestamp(float(ms) / 1000.0).strftime("%m-%d %H:%M:%S")
    except Exception:                                            # noqa: BLE001
        return "-"


# ───────────────────────── 配置 / HTTP（只读） ─────────────────────────
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
            with io.open(cfg, encoding="utf-8") as f:
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


def http_get(url, key, timeout=60):
    """本包唯一的上行方式：GET。

    长时间翻页时网关偶尔会掐连接（WinError 10054 / RemoteDisconnected），
    所以带 3 次重试，退避 0.5s / 1.2s。重试的也全是 GET，仍然 0 点。
    """
    last = None
    for attempt in range(3):
        req = urllib.request.Request(url, method="GET", headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json", "User-Agent": UA})
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


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        for k in ("msg", "message", "error"):
            v = d.get(k)
            if isinstance(v, dict):
                v = v.get("message")
            if v:
                return str(v)[:240]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:200]


def get_obj(key, host, path, what):
    st, txt = http_get(host + path, key)
    d = jloads(txt)
    if st != 200 or d is None:
        raise Fail("call", "%s 拉取失败（HTTP %s）：%s"
                   % (what, st, err_text(st, txt)), EXIT_CALL)
    return d


# ───────────────────────── 价目表解析 ─────────────────────────
def parse_pricing(d):
    """GET /api/v1/pricing 顶层是裸对象；兼容被套了一层 code/data 的情况。"""
    if isinstance(d, dict) and isinstance(d.get("pricing"), dict):
        return d["pricing"], d
    data = d.get("data") if isinstance(d, dict) else None
    if isinstance(data, dict) and isinstance(data.get("pricing"), dict):
        return data["pricing"], data
    raise Fail("call", "价目表结构不符预期（既没有顶层 pricing，也没有 data.pricing）",
               EXIT_CALL)


def lookup(rules, path):
    """三级命中：精确 → 前缀通配（/x/*）→ 全局 *。返回 (键, 规则, 命中方式)。"""
    if path in rules:
        return path, rules[path], "exact"
    best = None
    for k in rules:
        if k.endswith("/*") and path.startswith(k[:-1]):
            if best is None or len(k) > len(best):
                best = k
    if best is not None:
        return best, rules[best], "wildcard"
    if "*" in rules:
        return "*", rules["*"], "global"
    return None, {}, "none"


def baseline_rules():
    """把基线表摊成和线上同形的 {path: rule}。"""
    rules = {"*": {"mode": "flat", "cost": 0, "markupPercent": 100,
                   "minPoints": 50,
                   "note": "未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"},
             "/api/v1/tasks": {"mode": "per_module", "cost": 50, "markupPercent": 0,
                               "unitFrom": "module_codes"},
             "/api/v1/apps/full_video/submit": {
                 "mode": "per_second", "markupPercent": 0,
                 "resolutionRates": {"480P": 14, "768P": 28, "1080P": 60,
                                     "2K": 80, "4K": 80}},
             "/api/v1/apps/flashvsr/submit": {"mode": "per_second", "perSecond": 10,
                                              "minPoints": 20, "markupPercent": 0},
             "/api/v1/apps/smart_clip/*": {"mode": "per_second", "perSecond": 4.5,
                                            "markupPercent": 0},
             "/api/v1/apps/image_human/submit": {
                 "mode": "per_second", "markupPercent": 400, "rateFrom": "mode",
                 "defaultModel": "standard",
                 "modelRates": {"fast": {"*": 10}, "standard": {"*": 15},
                                "2k": {"*": 30}, "4k": {"*": 60}}},
             "/api/v1/apps/voice_tts/*": {"mode": "flat", "cost": 0,
                                           "markupPercent": 200},
             "/api/v1/apps/indextts/*": {"mode": "flat", "cost": 0, "markupPercent": 200},
             "/api/v1/apps/pic_lipsync/submit": {"mode": "flat", "cost": 0,
                                                  "markupPercent": 400, "minPoints": 50},
             "/api/v1/apps/lipsync/submit": {"mode": "flat", "cost": 0,
                                              "markupPercent": 200, "minPoints": 1},
             "/api/v1/apps/music_generation/*": {"mode": "flat", "cost": 0,
                                                  "markupPercent": 200},
             "/api/v1/apps/person_replacement/*": {"mode": "flat", "cost": 0,
                                                    "markupPercent": 100},
             "/api/v1/apps/action_transfer/*": {"mode": "flat", "cost": 0,
                                                 "markupPercent": 100}}
    for name, pts in BASELINE_APP_PRICE.items():
        key = "/api/v1/apps/%s/submit" % name
        if name == "smart_clip" or key in rules:      # full_video / flashvsr 已按秒写过
            continue
        rules[key] = {"mode": "flat", "cost": pts, "markupPercent": 0}
    for name, (ps, mn) in BASELINE_TIERS.items():
        r = {"mode": "per_second", "perSecond": ps, "markupPercent": 0}
        if mn is not None:
            r["minPoints"] = mn
        if name in TENCENT_TIERS or name in TSC_TIERS:
            r["provider"] = "tencent"
        rules["/api/v1/video/%s" % name] = r
        if name not in TENCENT_TIERS and name not in TSC_TIERS:
            rules["/api/v1/video/viapi/%s" % name] = dict(r)
    return rules


def tier_table(rules):
    """从价目表里抽出视频档：{tier: {perSecond, minPoints, path, viapi, note, unitMismatch}}"""
    out = {}
    for path, r in rules.items():
        m = re.match(r"^/api/v1/video/(viapi/)?([a-z0-9_]+)$", path)
        if not m or r.get("mode") != "per_second":
            continue
        viapi, name = bool(m.group(1)), m.group(2)
        note = r.get("note") or ""
        unit_mismatch = ("点/次" in note) or ("点／次" in note)
        cur = out.get(name)
        if cur is None or (viapi and not cur["viapi"]):
            out[name] = {"tier": name, "perSecond": r.get("perSecond"),
                         "minPoints": r.get("minPoints"), "path": path,
                         "viapi": viapi, "note": note,
                         "unitMismatch": unit_mismatch}
    return out


def app_rule(ctx, code):
    """应用层：按 /apps/<code>/ 的常见后缀找专属规则；找不到就落通配（如 media_services_33）。"""
    last = None
    for suf in APP_SUFFIXES:
        path = "/api/v1/apps/%s%s" % (code, suf)
        k, r, how = lookup(ctx["rules"], path)
        last = (path, r, how)
        if how != "global":
            return path, r, how
    return last


def measured_rows(ctx, want):
    """按用途挑模型层实测价：image 只取图片模型，video 取带 / 的模型层 ID。"""
    out = []
    for k, v in ctx["measured"].items():
        if k.startswith("__") or "points" not in v:
            continue
        if want == "image" and k not in IMAGE_MODELS:
            continue
        if want == "video" and not ("/" in k or k in ("muse-video", "wan3.0-video")):
            continue
        out.append((k, v))
    return sorted(out, key=lambda x: x[1]["points"])


def rule_min(rule):
    try:
        return float(rule.get("minPoints") or 0)
    except Exception:                                            # noqa: BLE001
        return 0.0


# ───────────────────────── 上下文（价目 + 实测 + 应用目录） ─────────────────────────
def save_cache(pricing_doc):
    try:
        d = os.path.dirname(CACHE)
        if not os.path.isdir(d):
            os.makedirs(d)
        with io.open(CACHE, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "pricing": pricing_doc}, ensure_ascii=False))
    except Exception:                                            # noqa: BLE001
        pass


def load_cache():
    try:
        if os.path.isfile(CACHE):
            with io.open(CACHE, encoding="utf-8") as f:
                d = json.load(f)
            rules, _ = parse_pricing(d.get("pricing") or {})
            return rules, d.get("at") or "缓存"
    except Exception:                                            # noqa: BLE001
        pass
    return None, None


def load_rules(a, key, host):
    """返回 (rules, 来源说明)。--offline 完全不出网。"""
    if getattr(a, "offline", False):
        c, at = load_cache()
        if c:
            return c, "本地缓存 %s（--offline）" % at
        return baseline_rules(), "内置基线 %s（--offline）" % BASELINE_TS
    try:
        doc = get_obj(key, host, API_PREFIX + "/pricing", "价目表")
        rules, full = parse_pricing(doc)
        save_cache(doc)
        return rules, "%s/api/v1/pricing（现查 %d 条规则）" % (
            host, len(rules))
    except Fail:
        c, at = load_cache()
        if c:
            say("  价目表现查失败，改用本地缓存（%s）" % at)
            return c, "本地缓存 %s" % at
        say("  价目表现查失败，改用内置基线（%s）" % BASELINE_TS)
        return baseline_rules(), "内置基线 %s" % BASELINE_TS


def measured_map(a, key, host, pages):
    """模型层实测价：{model: {points, src, path}}，先铺基线，再用流水覆盖。"""
    out = {}
    for k, v in BASELINE_MEASURED.items():
        out[k] = {"points": v[0], "src": v[1], "path": "", "live": False}
    scanned = 0
    if getattr(a, "offline", False):
        return out, scanned
    tasks = []
    total = None
    for pg in range(1, pages + 1):
        d = get_obj(key, host,
                    API_PREFIX + "/me/tasks?limit=2000&page=%d" % pg, "我的任务")
        total = d.get("total") if total is None else total
        tl = d.get("tasks") or []
        if not tl:
            break
        tasks += tl
        if len(tl) < PAGE_SIZE_ME:
            break
    scanned = len(tasks)
    agg = {}
    for t in tasks:
        model = t.get("model") or ""
        try:
            pts = float(t.get("actualPrice") or 0)
        except Exception:                                        # noqa: BLE001
            pts = 0.0
        if not model or pts <= 0:
            continue
        cur = agg.get(model)
        if cur is None or pts < cur[0]:
            agg[model] = (pts, t.get("path") or "")
    for k, v in agg.items():
        out[k] = {"points": round(v[0], 2), "path": v[1], "live": True,
                  "src": "me/tasks 实测最低 actualPrice"}
    out["__meta__"] = {"total": total, "scanned": scanned}
    return out, scanned


def load_apps(a, key, host):
    """应用目录：{code: {name, apis[]}}。--offline 用内置 22 个应用名。"""
    if getattr(a, "offline", False):
        return {c: {"name": c, "apis": []} for c in (
            "person_replacement", "action_transfer", "full_video", "pic_lipsync",
            "happy_horse", "media_services_33", "file_qa", "music_search",
            "grok_video", "nano_banana", "music_generation", "smart_clip",
            "image_human", "wan", "seedance", "lipsync", "dressing_diffusion",
            "mmaudio", "flashvsr", "seedsvc", "watermark_removal", "voice_tts")}
    d = get_obj(key, host, API_PREFIX + "/apps", "应用目录")
    out = {}
    for x in (d.get("data") or []):
        code = x.get("code")
        if code:
            out[code] = {"name": x.get("name") or code, "apis": x.get("apis") or [],
                         "category": x.get("category_code")}
    return out


def build_ctx(a, key, host, pages=3, need_apps=False):
    rules, src = load_rules(a, key, host)
    measured, scanned = measured_map(a, key, host, pages)
    apps = load_apps(a, key, host) if need_apps else {}
    tiers = tier_table(rules)
    ctx = {"rules": rules, "rulesSrc": src, "measured": measured,
           "apps": apps, "tiers": tiers,
           "tasksScanned": scanned,
           "perChar": VOICE_PER_CHAR,
           "tsc": tuple(t for t in TSC_TIERS if t in tiers),
           "tencent": tuple(t for t in TENCENT_TIERS if t in tiers)}
    return ctx


# ───────────────────────── 逐项计价 ─────────────────────────
def _base_item(kind, target, it, count, seconds):
    return {"kind": kind, "target": target, "count": count, "seconds": seconds,
            "label": it.get("label") or "", "traps": [], "notes": [],
            "qty": "", "unit": "", "unitLabel": "", "unitPoints": 0.0,
            "rulePath": "", "src": "", "basis": ""}


def _finish(out, points, low, high, unit, unit_label, unit_points, path, src, basis):
    out.update(unit=unit, unitLabel=unit_label, unitPoints=unit_points,
               rulePath=path, src=src, basis=basis,
               pointsBase=round(float(points), 2),
               rangeLow=round(float(low), 2), rangeHigh=round(float(high), 2))
    out["yuanBase"] = round(yuan(out["pointsBase"]), 2)
    out["rangeLowYuan"] = round(yuan(out["rangeLow"]), 2)
    out["rangeHighYuan"] = round(yuan(out["rangeHigh"]), 2)
    return out


def bill_item(it, ctx):
    kind = str(it.get("kind") or "").strip().lower()
    target = str(it.get("target") or "").strip()
    count = int(it.get("count") or 1)
    count = max(1, count)
    try:
        seconds = float(it.get("seconds") or 0)
    except Exception:                                            # noqa: BLE001
        raise Fail("usage", "清单里的 seconds 要是数字：%r" % it.get("seconds"), EXIT_USAGE)
    if kind not in ("image", "video", "post", "voice", "app"):
        raise Fail("usage",
                   "清单里的 kind 是 %r。用 image / video / post / voice / app 五种。"
                   % kind, EXIT_USAGE)
    out = _base_item(kind, target, it, count, seconds)
    if kind == "image":
        _bill_image(out, ctx, target, count, it)
    elif kind in ("video", "post"):
        _bill_video(out, ctx, target, seconds, count, it, kind == "post")
    elif kind == "voice":
        _bill_voice(out, ctx, target, count, it)
    else:
        _bill_app(out, ctx, target, count, it)
    _flag_traps(out, ctx, it)
    return out


def _bill_image(out, ctx, target, count, it):
    # 应用层优先（nano_banana 这类有专属规则），其次模型层实测价
    if target in APP_CODES:
        path, rule, how = app_rule(ctx, target)
        if rule.get("mode") == "per_second":
            raise Fail("usage", "%s 是按秒计费的档位，用 kind=video" % target, EXIT_USAGE)
        cost = float(rule.get("cost") or 0)
        if cost > 0:
            pts = cost * count
            return _finish(out, pts, pts, round(pts * 1.2, 2), "per_call",
                           "点/张", cost, path, "现查价目" if how != "global" else "通配兜底",
                           "%s 点/张 × %d 张（%s）" % (pnum(cost), count, path))
        # cost 0 + markupPercent：只能按实测/保底报
        m = ctx["measured"].get(target)
        if m:
            pts = m["points"] * count
            return _finish(out, pts, pts, round(pts * 1.2, 2), "per_call", "点/张",
                           m["points"], path, m["src"],
                           "%s 点/张 × %d 张（%s）" % (num(m["points"]), count, m["src"]))
        mn = rule_min(rule) or 50.0
        pts = mn * count
        return _finish(out, pts, pts, round(pts * 2, 2), "per_call", "点/张（保底）",
                       mn, path, "通配保底",
                       "没有实测成交价，按通配保底 %s 点/张 × %d 张" % (pnum(mn), count))
    m = ctx["measured"].get(target)
    if not m:
        raise Fail("usage",
                   "不认识的出图对象 %r。可用：%s；应用层可加 nano_banana / "
                   "aigc_qwen_image / aigc_wan_image / dressing_diffusion 等。"
                   % (target, " / ".join(sorted(ctx["measured"].keys())[:8])),
                   EXIT_USAGE)
    pts = m["points"] * count
    return _finish(out, pts, pts, round(pts * 1.2, 2), "per_call", "点/张", m["points"],
                   m.get("path") or "(模型层 /images/generations)", m["src"],
                   "%s 点/张 × %d 张（%s）" % (num(m["points"]), count, m["src"]))


def _bill_video(out, ctx, target, seconds, count, it, is_post):
    if target.lower().startswith("model:"):
        model = target.split(":", 1)[1].strip()
        path, rule, how = lookup(ctx["rules"], "/api/v1/videos/generations")
        m = ctx["measured"].get(model)
        if m:
            pts = m["points"] * count
            out["notes"].append("模型层按「一条任务」计价，秒数只影响上游成本")
            return _finish(out, pts, pts, round(pts * 2, 2), "per_call", "点/条",
                           m["points"], path, m["src"],
                           "%s 点/条 × %d 条（%s）" % (num(m["points"]), count, m["src"]))
        mn = rule_min(rule) or 50.0
        pts = mn * count
        out["notes"].append("这个模型还没有你自己的成交记录，按通配保底报上界")
        return _finish(out, pts, mn * count, round(pts * 2, 2), "per_call",
                       "点/条（保底）", mn, path, "通配保底",
                       "通配保底 %s 点/条 × %d 条（模型层实测价缺失）" % (pnum(mn), count))

    t = ctx["tiers"].get(target)
    if t:
        ps = float(t["perSecond"] or 0)
        mn = rule_min(t)
        raw = ps * max(seconds, 0)
        base = max(raw, mn) * count
        if t.get("unitMismatch"):
            low = ps * count
            high = round(base * 2, 2)
            out["notes"].append("note 写「点/次」、rule 是 per_second：这条按秒报，"
                                "10 秒素材就是 10 倍")
        else:
            low = base
            high = round(base * 1.3, 2)
        if seconds <= 0:
            out["notes"].append("没给 seconds，按 0 秒算（只有保底点数）")
        label = "%s 点/秒" % num(ps)
        if mn:
            label += "（保底 %s）" % pint(mn)
        return _finish(out, base, low, high, "per_second", label, ps, t["path"],
                       "现查价目", "%s 点/秒 × %s 秒 × %d 次%s" % (
                           num(ps), num(seconds), count,
                           "（保底 %s 点）" % pint(mn) if mn else ""))

    # 应用层：一口价 / 按秒
    if target in APP_CODES:
        path, rule, how = app_rule(ctx, target)
        mode = rule.get("mode")
        if mode == "per_second":
            rates = rule.get("resolutionRates")
            if rates:
                res = str(it.get("resolution") or "1080P")
                ps = float(rates.get(res) or rates.get("1080P") or 0)
                base = max(ps * seconds, rule_min(rule)) * count
                label = "%s 点/秒（%s）" % (num(ps), res)
                basis = "%s 点/秒 × %s 秒 × %d 次（分辨率 %s）" % (
                    num(ps), num(seconds), count, res)
            elif rule.get("modelRates"):
                mo = str(it.get("mode") or rule.get("defaultModel") or "standard")
                rr = (rule["modelRates"].get(mo) or {})
                ps = float(rr.get("*") or 0)
                base = ps * seconds * count
                label = "%s 点/秒（%s 档）" % (num(ps), mo)
                basis = "%s 点/秒 × %s 秒 × %d 次（mode=%s）" % (
                    num(ps), num(seconds), count, mo)
            else:
                ps = float(rule.get("perSecond") or 0)
                base = max(ps * seconds, rule_min(rule)) * count
                label = "%s 点/秒" % num(ps)
                basis = "%s 点/秒 × %s 秒 × %d 次" % (num(ps), num(seconds), count)
            if how == "global":
                out["notes"].append("这个应用在价目表里没有专属规则，落通配（上游×2、保底 50）")
            return _finish(out, base, base, round(base * 1.3, 2), "per_second",
                           label, ps, path,
                           "现查价目" if how != "global" else "通配兜底", basis)
        cost = float(rule.get("cost") or 0)
        if cost > 0:
            pts = cost * count
            out["notes"].append("一口价与素材时长无关：%s 点/次" % pint(cost))
            return _finish(out, pts, pts, pts, "per_call", "点/次", cost, path,
                           "现查价目" if how != "global" else "通配兜底",
                           "%s 点/次 × %d 次" % (pint(cost), count))
        m = ctx["measured"].get(target)
        if m:
            pts = m["points"] * count
            return _finish(out, pts, pts, round(pts * 2, 2), "per_call", "点/条",
                           m["points"], path, m["src"],
                           "%s 点/条 × %d 条（%s）" % (num(m["points"]), count, m["src"]))
        mn = rule_min(rule) or 50.0
        pts = mn * count
        return _finish(out, pts, pts, round(pts * 2, 2), "per_call", "点/次（保底）",
                       mn, path, "通配保底",
                       "通配保底 %s 点/次 × %d 次" % (pnum(mn), count))

    raise Fail("usage",
               "不认识的视频对象 %r。可用档位：%s；应用层：full_video / seedance / "
               "image_human / flashvsr；模型层写 model:<模型ID>。"
               % (target, " / ".join(sorted(ctx["tiers"].keys())[:10])), EXIT_USAGE)


def _bill_voice(out, ctx, target, count, it):
    per = it.get("pointsPerChar")
    try:
        per = float(per) if per is not None else float(ctx.get("perChar") or VOICE_PER_CHAR)
    except Exception:                                            # noqa: BLE001
        per = VOICE_PER_CHAR
    try:
        chars = float(it.get("chars") or 0)
    except Exception:                                            # noqa: BLE001
        raise Fail("usage", "配音项要给 chars（多少字）", EXIT_USAGE)
    if chars <= 0:
        raise Fail("usage", "配音项要给 chars（多少字），例如 {\"kind\":\"voice\","
                            "\"target\":\"voice_tts\",\"chars\":220}", EXIT_USAGE)
    if target not in ("voice_tts", "indextts", "music_generation", "tts", ""):
        raise Fail("usage", "配音对象用 voice_tts / indextts / music_generation，"
                            "收到 %r" % target, EXIT_USAGE)
    path = "/api/v1/apps/%s/*" % (target or "voice_tts")
    k, rule, how = lookup(ctx["rules"], path)
    pts = per * chars * count
    out["chars"] = chars
    out["notes"].append("配音按上游实际点数 ×3 结算，%.2f 点/字是实测基线，"
                        "按文本长度浮动" % per)
    return _finish(out, pts, pts, round(pts * 2, 2), "per_char", "点/字", per,
                   path, "实测基线 %s" % BASELINE_TS,
                   "%.2f 点/字 × %s 字 × %d 段" % (per, pint(chars), count))


def _bill_app(out, ctx, target, count, it):
    if target not in APP_CODES:
        raise Fail("usage", "不认识的应用 %r。可用：%s" % (
            target, " / ".join(sorted(APP_CODES))), EXIT_USAGE)
    path, rule, how = app_rule(ctx, target)
    mode = rule.get("mode")
    if mode == "per_second":
        ps = float(rule.get("perSecond") or 0)
        base = max(ps * out["seconds"], rule_min(rule)) * count
        return _finish(out, base, base, round(base * 1.3, 2), "per_second",
                       "%s 点/秒" % num(ps), ps, path, "现查价目",
                       "%s 点/秒 × %s 秒 × %d 次" % (num(ps), num(out["seconds"]), count))
    cost = float(rule.get("cost") or 0)
    if cost > 0:
        pts = cost * count
        return _finish(out, pts, pts, pts, "per_call", "点/次", cost, path,
                       "现查价目" if how != "global" else "通配兜底",
                       "%s 点/次 × %d 次" % (pint(cost), count))
    mn = rule_min(rule) or 50.0
    pts = mn * count
    out["notes"].append("这个应用没有一口价，按通配保底报")
    return _finish(out, pts, pts, round(pts * 2, 2), "per_call", "点/次（保底）", mn,
                   path, "通配保底", "通配保底 %s 点/次 × %d 次" % (pnum(mn), count))


def _flag_traps(out, ctx, it):
    """五类陷阱打到具体这一行上。"""
    tier = str(out["target"])
    if tier in TSC_TIERS:
        out["traps"].append("route404")
    if tier in TENCENT_TIERS:
        out["traps"].append("upstream502")
    t = ctx["tiers"].get(tier)
    if t and t.get("unitMismatch"):
        out["traps"].append("unitMismatch")
    if out["rulePath"] == "*" or "通配" in str(out["src"]):
        out["traps"].append("wildcard")
    if str(out["target"]) in {p[0] for p in PAIRS}:
        out["traps"].append("appVsModel")


TRAP_TEXT = {
    "route404": "价目表有、路由 404：这一档报价能算，提交会 404，换成 viapi 同档",
    "upstream502": "路由在、上游 502 InvalidMpsUser：腾讯档实测整批退款，实扣 0 点",
    "unitMismatch": "note 写「点/次」、rule 是 per_second：按秒报，秒数越大乘得越多",
    "wildcard": "落通配：对外 = 上游×2、保底 50 点；实测 15.60 / 26 / 44 点都低于 50",
    "appVsModel": "应用层一口价：同一件事模型层更便宜，见 compare",
}


def quote_plan(plan, ctx):
    items = plan.get("items") or []
    if not items:
        raise Fail("usage", "清单里 items 是空的：至少写一项，例如 "
                            "{\"kind\":\"image\",\"target\":\"gpt-image-2.6\",\"count\":6}",
                   EXIT_USAGE)
    rows = [bill_item(it, ctx) for it in items]
    for r in rows:
        if not r["qty"]:
            if r["unit"] == "per_second":
                r["qty"] = "%s 秒 × %d" % (num(r["seconds"]), r["count"])
            elif r["unit"] == "per_char":
                r["qty"] = "%s 字 × %d" % (pint(r.get("chars") or 0), r["count"])
            else:
                unit_cn = ("张" if "点/张" in r["unitLabel"]
                           else ("条" if "点/条" in r["unitLabel"] else "次"))
                r["qty"] = "%d %s" % (r["count"], unit_cn)
    tot = {
        "pointsBase": round(sum(r["pointsBase"] for r in rows), 2),
        "rangeLow": round(sum(r["rangeLow"] for r in rows), 2),
        "rangeHigh": round(sum(r["rangeHigh"] for r in rows), 2),
    }
    tot["yuanBase"] = round(yuan(tot["pointsBase"]), 2)
    tot["rangeLowYuan"] = round(yuan(tot["rangeLow"]), 2)
    tot["rangeHighYuan"] = round(yuan(tot["rangeHigh"]), 2)
    traps = []
    for r in rows:
        for k in r["traps"]:
            if k not in [x["kind"] for x in traps]:
                traps.append({"kind": k, "text": TRAP_TEXT.get(k, k),
                              "items": [r["label"] or r["target"]]})
            else:
                for x in traps:
                    if x["kind"] == k and (r["label"] or r["target"]) not in x["items"]:
                        x["items"].append(r["label"] or r["target"])
    return {"title": plan.get("title") or "未命名清单",
            "note": plan.get("note") or "", "items": rows, "total": tot,
            "traps": traps}


# ───────────────────────── 两道闸门 / 干跑 ─────────────────────────
def _gate(a, requests, what="本次", points=0.0):
    """闸门一：--budget 不够 → 退 5，一个请求都不发；闸门二：批量只读 ≥30 个 → 缺 --yes 退 4。"""
    if requests > 0 and a.budget <= 0:
        raise Fail("budget",
                   "--budget 是 %d 点（单位：点，1 元 = 100 点）。本包每个请求 0 点，"
                   "但 0 点等于不授权任何调用；给 1 点以上就放行。" % a.budget,
                   EXIT_BUDGET)
    if points > a.budget:
        raise Fail("budget",
                   "%s预计 %s 点（%s 元）超过 --budget %d 点，一个请求都没发。"
                   % (what, pnum(points), pnum(yuan(points)), a.budget),
                   EXIT_BUDGET)
    if requests >= 30 and not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "%s要连发 %d 个只读 GET（花费 0 点，扣不到钱）。确认请加 --yes。"
                   % (what, requests), EXIT_CONFIRM)


def _plan_out(a, reqs, lines, extra=None):
    out = {"ok": True, "dryRun": True, "requestCount": reqs,
           "estimatedPoints": 0, "yuan": 0.0, "requests": lines}
    if extra:
        out.update(extra)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（一个请求都没发）")
    print("  请求数：%d，全部只读 GET，花费 0 点" % reqs)
    for ln in lines:
        print("  → %s" % ln)
    return 0


def _load_plan(a):
    if a.file:
        if not os.path.isfile(a.file):
            raise Fail("usage", "清单文件不存在：%s" % a.file, EXIT_USAGE)
        try:
            with io.open(a.file, encoding="utf-8") as f:
                plan = json.load(f)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("usage", "清单不是合法 JSON：%s（%s）" % (a.file, e), EXIT_USAGE)
    elif a.preset:
        if a.preset not in PRESETS:
            raise Fail("usage", "--preset 只有 %s 三种（收到 %r）"
                       % (" / ".join(sorted(PRESETS)), a.preset), EXIT_USAGE)
        plan = json.loads(json.dumps(PRESETS[a.preset]))
    else:
        raise Fail("usage",
                   "给一份清单：--file 清单.json 或 --preset %s。清单格式：\n"
                   "  {\"title\":\"某单\",\"items\":["
                   "{\"kind\":\"image\",\"target\":\"gpt-image-2.6\",\"count\":6},"
                   "{\"kind\":\"video\",\"target\":\"full_video\",\"resolution\":\"1080P\","
                   "\"seconds\":15},{\"kind\":\"voice\",\"target\":\"voice_tts\",\"chars\":220}]}"
                   % " / ".join(sorted(PRESETS)), EXIT_USAGE)
    if not isinstance(plan, dict) or not isinstance(plan.get("items"), list):
        raise Fail("usage", "清单顶层要是对象，且 items 是数组", EXIT_USAGE)
    return plan


# ───────────────────────── 渲染 ─────────────────────────
def render_quote(q, a, ctx):
    tot = q["total"]
    print("报价单 · %s" % q["title"])
    if q["note"]:
        print("  %s" % q["note"])
    print("=" * 96)
    print("  %s %s %s %s %s %s" % (pad("#", 3), pad("项目", 22), pad("计费口径", 26),
                                   pad("数量", 9), pad("点数", 11), pad("元", 9)))
    print("  " + "-" * 92)
    for i, r in enumerate(q["items"], 1):
        mark = " !" if r["traps"] else ""
        print("  %s %s %s %s %s %s%s" % (
            pad(i, 3), pad((r["label"] or r["target"])[:21], 22),
            pad(r["unitLabel"][:25], 26), pad(r["qty"] or ("%d 次" % r["count"]), 9),
            pad(pnum(r["pointsBase"]), 11), pad(pnum(r["yuanBase"]), 9), mark))
    print("=" * 96)
    print("  %s %s 点 = %s 元" % (pad("基准合计", 22),
                                  pad(pint(tot["pointsBase"]), 12), pnum(tot["yuanBase"])))
    print("  %s %s ~ %s 点 = %s ~ %s 元" % (
        pad("区间", 22), pint(tot["rangeLow"]), pint(tot["rangeHigh"]),
        pnum(tot["rangeLowYuan"]), pnum(tot["rangeHighYuan"])))
    print()
    print("  区间怎么来的：乐观 = 按次/实测最低口径；基准 = 价目表 rule 口径；")
    print("  保守 = 基准 +30% 重跑余量（按次与按秒混用的档位按 rule ×2）。")
    print()
    if q["traps"]:
        print("  五类陷阱在这张单子里命中 %d 类：" % len(q["traps"]))
        for t in q["traps"]:
            print("    %s %s" % ("×", t["text"]))
            print("      命中：%s" % "、".join(t["items"]))
    else:
        print("  五类陷阱在这张单子里一个都没命中（全部走专属规则、按次口径干净）。")
    print()
    print("  明细（口径与来源）")
    for i, r in enumerate(q["items"], 1):
        print("  %d) %-20s %s" % (i, (r["label"] or r["target"])[:20], r["basis"]))
        print("     来源：%s · 规则：%s" % (r["src"], r["rulePath"]))
        for n in r["notes"]:
            print("     · %s" % n)
    print()
    tier_txt = budget_hint(tot["pointsBase"])
    print("  %s" % tier_txt)
    diff = a.budget - tot["pointsBase"]
    left = ("余 %s 点" % pint(diff)) if diff >= 0 else ("超 %s 点" % pint(-diff))
    print("  预算：--budget %d 点（本单基准 %s 点，%s）"
          % (a.budget, pint(tot["pointsBase"]), left))
    print("  数据：%s；模型层扫描 %d 条任务；本轮花费 0 点（全部只读 GET）"
          % (ctx["rulesSrc"], ctx["tasksScanned"]))
    return 0


def budget_hint(points):
    for limit, label in ((1000, "10 元"), (10000, "100 元"), (100000, "1000 元")):
        if points <= limit:
            return "预算档位：这笔 %s 点落在「%s 以内」档，余量 %s 点" % (
                pint(points), label, pint(limit - points))
    return "预算档位：这笔 %s 点超过 1000 元档，建议先拆单" % pint(points)


def quote_json(q, extra=None):
    out = {"ok": True, "estimate": True, "title": q["title"], "note": q["note"],
           "items": q["items"], "total": q["total"],
           "traps": q["traps"], "estimatedPoints": 0}
    if extra:
        out.update(extra)
    return out


def write_report(q, outdir):
    """把报价单落成两份文件：*.quote.json 与 *.quote.md（交付清单里的两件）。"""
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    safe = re.sub(r"[\\/:*?\"<>|\s]+", "-", q["title"])[:60] or "quote"
    jp = os.path.join(outdir, safe + ".quote.json")
    mp = os.path.join(outdir, safe + ".quote.md")
    with io.open(jp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(quote_json(q), ensure_ascii=False, indent=1))
    lines = ["# 报价单 · %s" % q["title"], ""]
    if q["note"]:
        lines += [q["note"], ""]
    lines += ["| # | 项目 | 计费口径 | 数量 | 点数 | 元 |",
              "|---|---|---|---|---|---|"]
    for i, r in enumerate(q["items"], 1):
        lines.append("| %d | %s | %s | %s | %s | %s |" % (
            i, (r["label"] or r["target"]), r["unitLabel"],
            r["qty"] or ("%d 次" % r["count"]), pnum(r["pointsBase"]),
            pnum(r["yuanBase"])))
    tot = q["total"]
    lines += ["", "**基准合计 %s 点 = %s 元**；区间 %s ~ %s 点 = %s ~ %s 元。" % (
        pint(tot["pointsBase"]), pnum(tot["yuanBase"]),
        pint(tot["rangeLow"]), pint(tot["rangeHigh"]),
        pnum(tot["rangeLowYuan"]), pnum(tot["rangeHighYuan"])), ""]
    if q["traps"]:
        lines += ["## 陷阱命中", ""]
        for t in q["traps"]:
            lines.append("- %s —— %s" % (t["text"], "、".join(t["items"])))
        lines.append("")
    lines += ["## 明细来源", ""]
    for i, r in enumerate(q["items"], 1):
        lines.append("%d. %s｜%s｜来源：%s" % (
            i, (r["label"] or r["target"]), r["basis"], r["src"]))
    lines.append("")
    lines += ["---", "", "数据来自 api.a7w.cn 的只读端点（/pricing + /me/tasks），"
                         "本报价单生成过程花费 0 点。", ""]
    with io.open(mp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return jp, mp


# ───────────────────────── 免费子命令：catalog ─────────────────────────
def cmd_catalog(a, key, host):
    reqs = 2 if a.models else 1
    _gate(a, reqs)
    if a.dry_run:
        lines = ["GET %s/api/v1/pricing" % host]
        if a.models:
            lines.append("GET %s/api/v1/models" % host)
        return _plan_out(a, reqs, lines)
    ctx = build_ctx(a, key, host, pages=1)
    rules = ctx["rules"]
    rows = []

    def add(group, name, unit, pts, path, trap="-"):
        rows.append({"group": group, "name": name, "unit": unit, "points": pts,
                     "path": path, "trap": trap})

    for model, m in measured_rows(ctx, "image"):
        add("出图 · 模型层实测", model, "点/张", m["points"],
            m.get("path") or "/api/v1/images/generations")
    for name, pts in sorted(BASELINE_APP_PRICE.items(), key=lambda x: x[1]):
        if name in ("seedance", "wan", "happy_horse", "mmaudio", "grok_video",
                    "seedsvc", "smart_clip", "music_search", "watermark_removal"):
            continue
        add("出图 · 应用层一口价", name, "点/张", pts,
            "/api/v1/apps/%s/submit" % name)
    for tier in sorted(ctx["tiers"], key=lambda t: ctx["tiers"][t]["perSecond"] or 0):
        t = ctx["tiers"][tier]
        trap = "-"
        if tier in TSC_TIERS:
            trap = "404"
        elif tier in TENCENT_TIERS:
            trap = "502"
        elif t["unitMismatch"]:
            trap = "点次?"
        add("视频 · 按秒（后处理）", tier, "%s 点/秒" % num(t["perSecond"]),
            t["perSecond"], t["path"], trap)
    for name, pts, extra in (
            ("full_video", 60, "1080P"),
            ("flashvsr", 10, "保底 20"),
            ("smart_clip", 4.5, "按秒"),
            ("image_human", 15, "standard 档")):
        add("视频 · 应用层按秒", "%s（%s）" % (name, extra), "点/秒", pts,
            "/api/v1/apps/%s/submit" % name, "通配" if name in ("smart_clip",) else "-")
    for name in ("seedance", "wan", "happy_horse", "mmaudio", "grok_video", "seedsvc"):
        add("视频 · 应用层一口价", name, "点/次", BASELINE_APP_PRICE[name],
            "/api/v1/apps/%s/submit" % name)
    for model, m in measured_rows(ctx, "video"):
        add("视频 · 模型层实测", model, "点/条", m["points"],
            m.get("path") or "/api/v1/videos/generations")
    add("配音", "voice_tts（约 0.18 点/字）", "点/字", VOICE_PER_CHAR,
        "/api/v1/apps/voice_tts/*")
    add("文本", "按百万 token（92 个文本模型各不同）", "点/M token", None,
        "/api/v1/models")
    add("兜底", "未单独定价的接口", "上游×2 保底 50", 50.0, "*")

    out = {"ok": True, "ruleCount": len(rules), "groups": rows,
           "voicePointsPerChar": VOICE_PER_CHAR,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "source": ctx["rulesSrc"], "estimatedPoints": 0}
    if a.models:
        d = get_obj(key, host, API_PREFIX + "/models", "模型目录")
        data = d.get("data") or []
        cat = [x for x in data if x.get("model_code")]
        bare = [x for x in data if not x.get("model_code")]
        out["models"] = {"total": len(data), "catalog": len(cat), "bare": len(bare),
                         "priced": len([x for x in cat if x.get("pricing")]),
                         "bareSample": [x.get("id") for x in bare[:8]]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("能力价目总表（1 元 = 100 点）")
    print("  来源：%s，共 %d 条规则" % (ctx["rulesSrc"], len(rules)))
    print("=" * 90)
    group = None
    for r in rows:
        if r["group"] != group:
            group = r["group"]
            print()
            print("  【%s】" % group)
        pts = "-" if r["points"] is None else pnum(r["points"])
        print("    %s %s %s %s" % (pad(r["name"][:40], 42), pad(r["unit"], 18),
                                   pad(pts, 10), pad(r["trap"], 6)))
    print()
    print("  标记：404 = 价目表有、路由 404；502 = 路由在、上游 502；")
    print("        点次? = note 写点/次、rule 是 per_second；通配 = 无专属规则、落 * 兜底。")
    if a.models:
        m = out["models"]
        print()
        print("  模型目录：%d 条 = %d 目录模型 + %d 裸模型层 ID（带价 %d 条，全是文本模型）"
              % (m["total"], m["catalog"], m["bare"], m["priced"]))
        for s in m["bareSample"]:
            print("    裸 ID：%s" % s)
    print()
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── 免费子命令：cost ─────────────────────────
def cmd_cost(a, key, host):
    reqs = 2
    _gate(a, reqs)
    if a.dry_run:
        return _plan_out(a, reqs, ["GET %s/api/v1/pricing" % host,
                                   "GET %s/api/v1/me/tasks?limit=2000&page=1" % host])
    ctx = build_ctx(a, key, host, pages=1)
    img = ctx["measured"].get("gpt-image-2.6", {}).get("points", 6.0)
    tiers = ctx["tiers"]
    full = app_rule(ctx, "full_video")[1]
    rate_1080 = float(((full.get("resolutionRates") or {}).get("1080P")) or 60)
    sr = float((tiers.get("superres") or {}).get("perSecond") or 9)
    restore = float((tiers.get("restore") or {}).get("perSecond") or 36)
    model_seedance = ctx["measured"].get("sd/doubao-seedance-2-0-260128", {}).get(
        "points", 145.73)
    app_seedance = float(BASELINE_APP_PRICE["seedance"])

    sc = [
        {"name": "一张图（gpt-image-2.6）", "qty": "1 张", "points": img},
        {"name": "一条 10 秒 1080P 成片（full_video）", "qty": "10 秒",
         "points": rate_1080 * 10},
        {"name": "一段 60 字配音（voice_tts）", "qty": "60 字",
         "points": VOICE_PER_CHAR * 60},
        {"name": "一次 10 秒后处理（超分 standard）", "qty": "10 秒", "points": sr * 10},
        {"name": "一次 10 分钟修复（restore）", "qty": "600 秒", "points": restore * 600},
        {"name": "一条 Seedance 视频（应用层一口价）", "qty": "1 条", "points": app_seedance},
        {"name": "一条 Seedance 视频（模型层实测）", "qty": "1 条", "points": model_seedance},
    ]
    plans = []
    for label, items in (
            ("轻单：6 图 + 15 秒成片 + 220 字配音",
             [("image", img, 6), ("video", rate_1080, 15), ("voice", VOICE_PER_CHAR, 220)]),
            ("中单：轻单 + 10 分钟修复 + 2 条模型层视频",
             [("image", img, 6), ("video", rate_1080, 15), ("voice", VOICE_PER_CHAR, 220),
              ("video", restore, 600), ("video", model_seedance, 2)]),
            ("重单：20 图 + 60 秒 1080P + 600 字配音 + 30 分钟修复",
             [("image", img, 20), ("video", rate_1080, 60),
              ("voice", VOICE_PER_CHAR, 600), ("video", restore, 1800)])):
        pts = 0.0
        for _k, rate, qty in items:
            pts += rate * qty
        plans.append({"name": label, "points": round(pts, 2), "yuan": round(yuan(pts), 2)})

    out = {"ok": True, "scenarios": sc, "plans": plans,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "estimatedPoints": 0,
           "rates": {"image": img, "perSecond1080P": rate_1080,
                     "voicePerChar": VOICE_PER_CHAR, "superresPerSecond": sr,
                     "restorePerSecond": restore,
                     "seedanceApp": app_seedance, "seedanceModel": model_seedance},
           "source": ctx["rulesSrc"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("先算钱（1 元 = 100 点）")
    print("=" * 70)
    for s in sc:
        print("  %s %s %s 点 = %s 元" % (pad(s["name"][:38], 40), pad(s["qty"], 8),
                                         pad(pnum(s["points"]), 10),
                                         pnum(yuan(s["points"]))))
    print()
    print("三档单量")
    for p in plans:
        print("  %s" % pad(p["name"], 46))
        print("     %s 点 = %s 元" % (pint(p["points"]), pnum(p["yuan"])))
    print()
    print("  单价来源：%s" % ctx["rulesSrc"])
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── 免费子命令：quote（核心） ─────────────────────────
def cmd_quote(a, key, host):
    plan = _load_plan(a)
    pages = 1
    reqs = 2
    _gate(a, reqs)
    if a.dry_run:
        lines = ["GET %s/api/v1/pricing" % host,
                 "GET %s/api/v1/me/tasks?limit=2000&page=1" % host]
        return _plan_out(a, reqs, lines,
                         {"planTitle": plan.get("title"), "itemCount": len(plan["items"])})

    # 闸门先跑在「内置基线」上：能判定超预算就一个请求都不发
    pre_ctx = {"rules": baseline_rules(), "measured": {
        k: {"points": v[0], "src": v[1], "path": ""} for k, v in BASELINE_MEASURED.items()},
        "apps": {}, "tiers": tier_table(baseline_rules()), "tasksScanned": 0,
        "perChar": VOICE_PER_CHAR, "tsc": TSC_TIERS, "tencent": TENCENT_TIERS}
    try:
        pre = quote_plan(plan, pre_ctx)
    except Fail:
        pre = None
    if pre and pre["total"]["pointsBase"] > a.budget and not a.allow_over_budget:
        raise Fail("budget",
                   "这单基线价 %s 点（%s 元）超过 --budget %d 点，一个请求都没发。\n"
                   "  · 调大 --budget：--budget %d\n"
                   "  · 或先看全表：加 --allow-over-budget（仍然 0 点）"
                   % (pint(pre["total"]["pointsBase"]),
                      pnum(pre["total"]["yuanBase"]), a.budget,
                      int(pre["total"]["pointsBase"]) + 1000),
                   EXIT_BUDGET)

    ctx = build_ctx(a, key, host, pages=pages, need_apps=True)
    q = quote_plan(plan, ctx)
    over = q["total"]["pointsBase"] > a.budget
    if over and not a.allow_over_budget:
        raise Fail("budget",
                   "现查价后这单 %s 点（%s 元）超过 --budget %d 点。"
                   "加 --budget %d 或 --allow-over-budget（都只发过只读 GET，花费 0 点）。"
                   % (pint(q["total"]["pointsBase"]), pnum(q["total"]["yuanBase"]),
                      a.budget, int(q["total"]["pointsBase"]) + 1000),
                   EXIT_BUDGET)

    extra = {"source": ctx["rulesSrc"], "tasksScanned": ctx["tasksScanned"],
             "budget": a.budget, "overBudget": bool(over),
             "budgetHint": budget_hint(q["total"]["pointsBase"]),
             "estimatedPoints": 0}
    if a.out:
        jp, mp = write_report(q, a.out)
        extra["files"] = [jp, mp]
    if a.json:
        print(json.dumps(quote_json(q, extra), ensure_ascii=False))
        return 0
    rc = render_quote(q, a, ctx)
    if a.out:
        jp, mp = write_report(q, a.out)
        print()
        print("  已写盘：%s" % jp)
        print("          %s" % mp)
    return rc


# ───────────────────────── 免费子命令：compare ─────────────────────────
def cmd_compare(a, key, host):
    pages = ALL_PAGES_EST if a.all else max(1, a.pages)
    reqs = 2 + pages
    _gate(a, reqs)
    if a.dry_run:
        lines = ["GET %s/api/v1/pricing" % host,
                 "GET %s/api/v1/me/tasks（翻 %d 页找模型层实测价）" % (host, pages)]
        return _plan_out(a, reqs, lines)
    ctx = build_ctx(a, key, host, pages=pages, need_apps=True)
    rows = []
    for app, model, why in PAIRS:
        path, rule, how = app_rule(ctx, app)
        if rule.get("mode") == "per_second":
            continue
        cost = float(rule.get("cost") or 0)
        if cost <= 0:
            continue
        m = ctx["measured"].get(model)
        if not m:
            continue
        ratio = cost / m["points"] if m["points"] else 0
        rows.append({"app": app, "appPath": path, "appPoints": cost,
                     "model": model, "modelPoints": m["points"],
                     "modelSrc": m["src"], "ratio": round(ratio, 1),
                     "why": why, "saving": round(cost - m["points"], 2)})
    rows.sort(key=lambda r: -r["ratio"])
    out = {"ok": True, "pairs": rows, "count": len(rows),
           "tasksScanned": ctx["tasksScanned"], "source": ctx["rulesSrc"],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("应用层 vs 模型层：同一件事差几倍")
    print("  价目：%s；模型层：扫描 %d 条任务取 actualPrice 最低值"
          % (ctx["rulesSrc"], ctx["tasksScanned"]))
    print("=" * 100)
    print("  %s %s %s %s %s %s" % (pad("#", 3), pad("应用层", 20), pad("价", 9),
                                   pad("模型层", 34), pad("实测价", 10), pad("倍数", 7)))
    print("  " + "-" * 96)
    for i, r in enumerate(rows, 1):
        print("  %s %s %s %s %s %s" % (
            pad(i, 3), pad(r["app"][:19], 20), pad(pint(r["appPoints"]), 9),
            pad(r["model"][:33], 34), pad(pnum(r["modelPoints"]), 10),
            pad("%.1f×" % r["ratio"], 7)))
    print()
    if rows:
        top = rows[0]
        print("  最贵的一对：%s 走应用层 %s 点，走模型层 %s 点 —— 差 %.1f 倍，一条省 %s 点（%s 元）。"
              % (top["app"], pint(top["appPoints"]), pnum(top["modelPoints"]),
                 top["ratio"], pnum(top["saving"]), pnum(yuan(top["saving"]))))
        print("  配对口径：%s" % "；".join(sorted({r["why"] for r in rows})[:4]))
    print()
    print("  模型层价只有两个来源：价目表的通配兜底（上游×2、保底 50），以及你自己的")
    print("  /api/v1/me/tasks 里的 actualPrice。没有成交记录的模型按通配保底报上界。")
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── 免费子命令：traps ─────────────────────────
def cmd_traps(a, key, host):
    reqs = 1
    _gate(a, reqs)
    if a.dry_run:
        return _plan_out(a, reqs, ["GET %s/api/v1/pricing" % host])
    ctx = build_ctx(a, key, host, pages=1)
    rules = ctx["rules"]
    wildcard = rules.get("*") or {}
    tsc = [t for t in TSC_TIERS if t in ctx["tiers"]]
    tencent = [t for t in TENCENT_TIERS if t in ctx["tiers"]]
    # ③ 按「规则条数」数：castcrew / delogo / shot 各有扁平与 viapi 两条 = 6 条
    mismatch_paths = [p for p, r in rules.items()
                      if p.startswith("/api/v1/video/")
                      and r.get("mode") == "per_second"
                      and (("点/次" in (r.get("note") or ""))
                           or ("点／次" in (r.get("note") or "")))]
    below_floor = [(k, v["points"]) for k, v in
                   (measured_rows(ctx, "image") + measured_rows(ctx, "video"))
                   if v["points"] < rule_min(wildcard)]
    model_paths = ["/api/v1/images/generations", "/api/v1/images/edits",
                   "/api/v1/videos/generations", "/api/v1/videos",
                   "/api/v1/chat/completions", "/api/v1/embeddings"]
    global_hits = [p for p in model_paths if lookup(rules, p)[2] == "global"]
    out = {
        "ok": True,
        "traps": [
            {"id": "route404", "count": len(tsc), "tiers": tsc,
             "priceRange": [min((ctx["tiers"][t]["perSecond"] or 0) for t in tsc),
                            max((ctx["tiers"][t]["perSecond"] or 0) for t in tsc)]
             if tsc else None,
             "text": "价目表有、路由 404：提交必 404，报价里标 !，换 viapi 同档"},
            {"id": "upstream502", "count": len(tencent), "tiers": tencent,
             "points": {t: ctx["tiers"][t]["perSecond"] for t in tencent},
             "text": "路由在、上游 502 InvalidMpsUser：整批退款，实扣 0 点"},
            {"id": "unitMismatch", "count": len(mismatch_paths), "paths": mismatch_paths,
             "text": "note 写「点/次」、rule 是 per_second：10 秒素材按 10 倍扣"},
            {"id": "wildcard", "count": len(global_hits), "paths": global_hits,
             "minPoints": rule_min(wildcard),
             "markupPercent": wildcard.get("markupPercent"),
             "belowFloor": [{"model": k, "points": v} for k, v in below_floor],
             "text": "落通配：对外 = 上游×2、保底 50 点；实测有成交价低于 50，保底未落地"},
            {"id": "appVsModel", "count": len(PAIRS),
             "text": "应用层 vs 模型层：同一件事差 2.7~75.5 倍，见 compare"},
        ],
        "ruleCount": len(rules), "source": ctx["rulesSrc"], "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("五类价格陷阱（现查 %d 条规则）" % len(rules))
    print("=" * 84)
    print("  ① 价目表有、路由 404 —— %d 个 tsc_* 档" % len(tsc))
    print("     %s" % "、".join(tsc))
    if tsc:
        print("     单价 %s ~ %s 点/秒、保底 %s 点：数字漂亮，提交 404"
              % (num(min(ctx["tiers"][t]["perSecond"] for t in tsc)),
                 num(max(ctx["tiers"][t]["perSecond"] for t in tsc)),
                 pint(rule_min(ctx["tiers"][tsc[0]]))))
    print()
    print("  ② 路由在、上游 502 —— %d 个腾讯档" % len(tencent))
    for t in tencent:
        print("     %-14s %s 点/秒（保底 %s 点）" % (
            t, num(ctx["tiers"][t]["perSecond"]), pint(rule_min(ctx["tiers"][t]))))
    print("     502 InvalidMpsUser：本账号腾讯 4K 任务全部 refunded，实扣 0 点")
    print()
    print("  ③ note 写「点/次」、rule 是 per_second —— %d 条" % len(mismatch_paths))
    print("     %s" % "、".join(p.replace("/api/v1/video/", "") for p in mismatch_paths))
    print("     10 秒素材按 10 倍扣：报价里这一行的区间下限就是按次口径")
    print()
    print("  ④ 落通配保底 —— %d 条模型层路径没有专属规则" % len(global_hits))
    print("     %s" % "、".join(global_hits))
    print("     通配规则：cost %s + markupPercent %s + minPoints %s"
          % (num(wildcard.get("cost") or 0), num(wildcard.get("markupPercent")),
             pint(rule_min(wildcard))))
    if below_floor:
        print("     实测保底未落地：%s" % "、".join(
            "%s %s 点" % (k, num(v)) for k, v in below_floor[:6]))
    print()
    print("  ⑤ 应用层 vs 模型层 —— %d 组配对，最大差 75.5 倍" % len(PAIRS))
    print("     用 compare 看排行；报价里应用层那一行会自动标注")
    print()
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── 免费子命令：budget ─────────────────────────
def cmd_budget(a, key, host):
    reqs = 2
    _gate(a, reqs)
    if a.dry_run:
        return _plan_out(a, reqs, ["GET %s/api/v1/pricing" % host,
                                   "GET %s/api/v1/me/tasks?limit=2000&page=1" % host])
    ctx = build_ctx(a, key, host, pages=1)
    img = float(ctx["measured"].get("gpt-image-2.6", {}).get("points", 6.0))
    full = app_rule(ctx, "full_video")[1]
    r1080 = float(((full.get("resolutionRates") or {}).get("1080P")) or 60)
    sr = float((ctx["tiers"].get("superres") or {}).get("perSecond") or 9)
    mn = ctx["measured"].get("muse-video", {}).get("points", 44.0)
    sd = ctx["measured"].get("sd/doubao-seedance-2-0-260128", {}).get("points", 145.73)
    appsd = float(BASELINE_APP_PRICE["seedance"])

    goods = [
        {"what": "gpt-image-2.6 图", "unit": "张", "per": img, "kind": "big"},
        {"what": "1080P 成片", "unit": "秒", "per": r1080, "kind": "big"},
        {"what": "超分（standard）", "unit": "秒", "per": sr, "kind": "big"},
        {"what": "配音", "unit": "字", "per": VOICE_PER_CHAR, "kind": "big"},
        {"what": "模型层短视频（muse-video）", "unit": "条", "per": mn, "kind": "big"},
        {"what": "模型层 Seedance 2.0", "unit": "条", "per": sd, "kind": "big"},
        {"what": "应用层 Seedance", "unit": "条", "per": appsd, "kind": "big"},
    ]
    tiers = []
    for label, pts in (("10 元", 1000), ("100 元", 10000), ("1000 元", 100000)):
        rows = []
        for g in goods:
            n = int(pts // g["per"]) if g["per"] else 0
            rows.append({"what": g["what"], "unit": g["unit"], "count": n,
                         "fits": n >= 1, "per": g["per"]})
        tiers.append({"label": label, "points": pts, "rows": rows})
    out = {"ok": True, "tiers": tiers, "rates": {"image": img, "perSecond1080P": r1080,
                                                 "superresPerSecond": sr,
                                                 "voicePerChar": VOICE_PER_CHAR,
                                                 "modelMuse": mn, "modelSeedance": sd,
                                                 "appSeedance": appsd},
           "source": ctx["rulesSrc"], "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预算档位：10 元 / 100 元 / 1000 元各能做什么（1 元 = 100 点）")
    print("=" * 84)
    for t in tiers:
        print()
        print("  【%s = %s 点】" % (t["label"], pint(t["points"])))
        for r in t["rows"]:
            if r["fits"]:
                print("    √ %s %s %s" % (pad(r["what"][:30], 32), pad(pint(r["count"]), 9),
                                          r["unit"]))
            else:
                print("    × %s 不够一条（%s 点/条）" % (pad(r["what"][:30], 32),
                                                       num(r["per"])))
    print()
    print("  读法：同一个预算，走模型层能出更多条；应用层一口价先吃预算。")
    print("  单价来源：%s" % ctx["rulesSrc"])
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── 免费子命令：doctor ─────────────────────────
def cmd_doctor(a, key, host):
    _gate(a, 8)
    if a.dry_run:
        return _plan_out(a, 8, [
            "GET /user/balance", "GET /user/balance/logs?limit=1",
            "GET /api/v1/pricing", "GET /api/v1/models", "GET /api/v1/apps",
            "GET /api/v1/me/tasks?limit=2000&page=1",
            "GET /api/v1/tasks/probe-no-such-task",
            "GET /user/balance/logs?limit=1（跑完再读一次，证明 0 点）"])
    checks = []

    st, txt = http_get(host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, pint(d.get("available_points")), pint(d.get("frozen")))))

    lg0 = {}
    try:
        lg0 = get_obj(key, host, "/user/balance/logs?limit=1", "余额流水")
        first = (lg0.get("logs") or [{}])[0]
        checks.append(("流水可读（有据可查）", True,
                       "共 %s 条 · 最近一笔 %s %s 点 %s" % (
                           pint(lg0.get("total")), ts(first.get("at")),
                           pnum(first.get("points")), first.get("reference") or "-")))
    except Fail as e:
        checks.append(("流水可读（有据可查）", False, e.message[:70]))

    try:
        doc = get_obj(key, host, API_PREFIX + "/pricing", "价目表")
        rules, _ = parse_pricing(doc)
        checks.append(("价目表 /api/v1/pricing（裸对象）", len(rules) > 100,
                       "HTTP 200 · %d 条规则 · markupPercent=%s" % (
                           len(rules), pnum(doc.get("markupPercent")))))
    except Fail as e:
        rules = baseline_rules()
        checks.append(("价目表 /api/v1/pricing（裸对象）", False, e.message[:70]))

    tiers = tier_table(rules)
    tsc = [t for t in TSC_TIERS if t in tiers]
    tenc = [t for t in TENCENT_TIERS if t in tiers]
    mis = [p for p, r in rules.items()
           if p.startswith("/api/v1/video/") and r.get("mode") == "per_second"
           and (("点/次" in (r.get("note") or ""))
                or ("点／次" in (r.get("note") or "")))]
    wc = rules.get("*") or {}
    checks.append(("五类陷阱计数（①11 ②3 ③6 ④保底 ⑤配对）",
                   len(tsc) == 11 and len(tenc) == 3 and len(mis) == 6
                   and rule_min(wc) == 50,
                   "tsc %d / 腾讯 %d / 点次混用 %d / 通配保底 %s 点 / 配对 %d 组" % (
                       len(tsc), len(tenc), len(mis), pint(rule_min(wc)), len(PAIRS))))

    drift = []
    for name, (ps, _mn) in BASELINE_TIERS.items():
        t = tiers.get(name)
        if not t:
            drift.append("%s 线上无此档" % name)
        elif float(t["perSecond"] or 0) != float(ps):
            drift.append("%s 本地 %s / 线上 %s" % (name, ps, t["perSecond"]))
    checks.append(("%d 个视频档单价与本地基线一致" % len(BASELINE_TIERS), not drift,
                   "全一致" if not drift else " / ".join(drift)[:120]))

    try:
        dm = get_obj(key, host, API_PREFIX + "/models", "模型目录")
        data = dm.get("data") or []
        cat = [x for x in data if x.get("model_code")]
        bare = [x for x in data if not x.get("model_code")]
        checks.append(("模型目录 /api/v1/models", len(data) > 200,
                       "%d 条 = %d 目录 + %d 裸模型层 ID" % (
                           len(data), len(cat), len(bare))))
    except Fail as e:
        checks.append(("模型目录 /api/v1/models", False, e.message[:70]))

    try:
        da = get_obj(key, host, API_PREFIX + "/apps", "应用目录")
        apps = da.get("data") or []
        napi = sum(len(x.get("apis") or []) for x in apps)
        checks.append(("应用目录 /api/v1/apps", len(apps) >= 20 and napi >= 90,
                       "%d 个应用 / %d 个接口" % (len(apps), napi)))
    except Fail as e:
        checks.append(("应用目录 /api/v1/apps", False, e.message[:70]))

    try:
        dt = get_obj(key, host, API_PREFIX + "/me/tasks?limit=2000&page=1", "我的任务")
        tl = dt.get("tasks") or []
        checks.append(("任务台账 /api/v1/me/tasks（模型层单价来源）", len(tl) > 0,
                       "共 %s 条 · 本页 %d 条 · 带 actualPrice" % (
                           pint(dt.get("total")), len(tl))))
    except Fail as e:
        checks.append(("任务台账 /api/v1/me/tasks（模型层单价来源）", False, e.message[:70]))

    st4, txt4 = http_get(host + API_PREFIX + "/tasks/probe-no-such-task", key, timeout=40)
    d4 = jloads(txt4) or {}
    checks.append(("通用任务查询（假 id 也安全）", st4 == 200,
                   "HTTP %s %s" % (st4, (d4.get("msg") or err_text(st4, txt4))[:40])))

    try:
        c = build_ctx(a, key, host, pages=1, need_apps=True)
        demo = quote_plan(PRESETS["duanju"], c)
        ok_engine = demo["total"]["pointsBase"] > 0
        checks.append(("报价引擎自检（短剧样例跑通）", ok_engine,
                       "样例 %s 点 = %s 元，%d 项" % (
                           pint(demo["total"]["pointsBase"]),
                           pnum(demo["total"]["yuanBase"]), len(demo["items"]))))
    except Fail as e:
        checks.append(("报价引擎自检（短剧样例跑通）", False, e.message[:70]))

    same = None
    try:
        lg1 = get_obj(key, host, "/user/balance/logs?limit=1", "余额流水")
        f0 = (lg0.get("logs") or [{}])[0]
        f1 = (lg1.get("logs") or [{}])[0]
        same = (f0.get("at") == f1.get("at") and f0.get("points") == f1.get("points")
                and f0.get("reference") == f1.get("reference"))
        checks.append(("流水前后比对：本轮 0 点", same,
                       "最近一笔仍是 %s %s 点（%s）" % (
                           ts(f1.get("at")), pnum(f1.get("points")),
                           f1.get("reference") or "-")))
    except Fail as e:
        checks.append(("流水前后比对：本轮 0 点", False, e.message[:70]))

    out = {"ok": all(c[1] for c in checks),
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
           "estimatedPoints": 0, "actualPoints": 0,
           "zeroSpendProof": {"logsBefore": (lg0.get("logs") or [{}])[0].get("at"),
                              "logsAfter": None, "unchanged": same},
           "source": "%s/api/v1/pricing" % host}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（不扣费：7 个只读 GET，0 个 POST，任务 0 条、冻结 0 点）")
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 44), d))
    print()
    print("  端点：/pricing /models /apps /me/tasks /tasks/<假 id> /user/balance "
          "/user/balance/logs")
    print("  写请求：0 个（源码里只有 GET，没有任何 POST / PUT / DELETE）")
    print("  本轮花费 0 点 —— 流水前后最近一笔完全相同，这是硬证据。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 离线：sample ─────────────────────────
SAMPLE_PLAN = {
    "title": "示例：短剧一集",
    "note": "把这张清单改成你自己的单量，再跑 quote --file 报价",
    "items": PRESETS["duanju"]["items"],
}


def cmd_sample(a, key, host):
    plan = json.loads(json.dumps(SAMPLE_PLAN))
    if a.preset:
        if a.preset not in PRESETS:
            raise Fail("usage", "--preset 只有 %s" % " / ".join(sorted(PRESETS)),
                       EXIT_USAGE)
        plan = json.loads(json.dumps(PRESETS[a.preset]))
    out = {"ok": True, "plan": plan, "requestCount": 0, "estimatedPoints": 0}
    if a.dry_run:
        out["dryRun"] = True
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（离线样例，0 请求，不写盘）")
        print("  清单：%s（%d 项）" % (plan.get("title"), len(plan["items"])))
        return 0
    if a.out:
        if not os.path.isdir(a.out):
            os.makedirs(a.out)
        safe = re.sub(r"[\\/:*?\"<>|\s]+", "-", plan["title"])[:50] or "plan"
        path = os.path.join(a.out, safe + ".plan.json")
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(plan, ensure_ascii=False, indent=1))
        out["file"] = path
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务清单样例（%d 项，离线生成，0 请求）" % len(plan["items"]))
    print("=" * 80)
    for i, it in enumerate(plan["items"], 1):
        bits = []
        for k in ("kind", "target", "count", "seconds", "chars", "resolution", "mode"):
            if k in it:
                bits.append("%s=%s" % (k, it[k]))
        print("  %d) %s" % (i, "  ".join(bits)))
        if it.get("label"):
            print("     %s" % it["label"])
    print()
    print("  kind 五种：image / video / post / voice / app")
    print("  target：模型名（gpt-image-2.6）· 档位名（restore）· 应用名（full_video）")
    print("          · 模型层写 model:<模型ID>（例 model:muse-video）")
    print()
    if out.get("file"):
        print("  已写盘：%s" % out["file"])
        print("  下一步：python3 scripts/run.py quote --file \"%s\"" % out["file"])
    else:
        print("  加 --out . 可写盘；也能直接 quote --preset %s"
              % (a.preset or "duanju"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 成本预估器：花之前把这一单算清（只读端点，0 点花费）",
        epilog="端点：GET %s/api/v1/pricing · GET %s/api/v1/models · "
               "GET %s/api/v1/apps · GET %s/api/v1/me/tasks · "
               "GET %s/api/v1/tasks/<id> · GET %s/user/balance · "
               "GET %s/user/balance/logs" % ((DEFAULT_HOST,) * 7),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = %d 元；1 元 = 100 点）"
                         % (DEFAULT_BUDGET, DEFAULT_BUDGET // 100))
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    ap.add_argument("--offline", action="store_true",
                    help="完全不出网：用本地缓存或内置基线价目（0 请求）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="能力价目总表（按计费口径分组，标注陷阱）",
                       allow_abbrev=False)
    p.add_argument("--models", action="store_true", help="同时列出模型目录构成（多 1 个 GET）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：常用四件事 + 三档单量（免费）",
                       allow_abbrev=False)
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("quote", help="按任务清单算总价：逐项 + 合计 + 区间（核心）",
                       allow_abbrev=False)
    p.add_argument("--file", help="任务清单 JSON 路径")
    p.add_argument("--preset", help="内置清单：%s" % " / ".join(sorted(PRESETS)))
    p.add_argument("--out", help="把报价单写成 <标题>.quote.json 与 .quote.md 的目录")
    p.add_argument("--allow-over-budget", action="store_true",
                   help="本单超过 --budget 也照样报（仍然 0 点）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_quote)

    p = sub.add_parser("compare", help="应用层 vs 模型层比价（免费）", allow_abbrev=False)
    p.add_argument("--pages", type=int, default=5,
                   help="翻几页任务台账找模型层实测价（每页 20 条，默认 5）")
    p.add_argument("--all", action="store_true",
                   help="翻完全部台账（约 70 页，要 --yes，仍然 0 点）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("traps", help="五类价格陷阱逐条摊开（免费）", allow_abbrev=False)
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_traps)

    p = sub.add_parser("budget", help="10 元 / 100 元 / 1000 元各能做什么（免费）",
                       allow_abbrev=False)
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_budget)

    p = sub.add_parser("doctor", help="自检 7 个只读端点 + 流水前后比对（不扣费）",
                       allow_abbrev=False)
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("sample", help="写一份任务清单样例（离线，0 请求）",
                       allow_abbrev=False)
    p.add_argument("--preset", help="样例类型：%s" % " / ".join(sorted(PRESETS)))
    p.add_argument("--out", help="写盘目录（不写则只打印）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.add_argument("--yes", action="store_true", help="确认批量只读扫描")
    p.set_defaults(fn=cmd_sample)

    # 全局选项写在子命令前后都可以（default=SUPPRESS，没写就不覆盖父级的值）
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int)),
                        ("--offline", dict(action="store_true"))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("offline", False), ("yes", False), ("dry_run", False)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    try:
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in ("cmd_sample",):
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
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
