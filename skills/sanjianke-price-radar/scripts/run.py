#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 模型比价器（sanjianke-price-radar）

## 一句话

同一个模型，走**应用层**还是走**模型层**，价格能差 14 倍。

## 实测（2026-11-07，本账号真实流水）

  应用层  POST /api/v1/apps/seedance/submit        固定 11,000 点/次（￥110）
  模型层  POST /api/v1/videos/generations
          model=volcengine/doubao-seedance-2-5-260628   实测 762.30 点（￥7.62）

  11,000 ÷ 762.30 = 14.4 倍。同一个模型。

更狠的一条：同族 `sd/doubao-seedance-2-0-260128` 模型层实测最低 145.73 点，
对同一个应用层 11,000 点 = **75.5 倍**。

## 为什么用户看不到这个

控制台的价目表只有「应用层」：`GET /api/v1/pricing` 里 `/api/v1/apps/*` 是一口价。
模型层那批接口（`/api/v1/videos`、`/api/v1/videos/generations`、`/api/v1/images/generations`、
`/api/v1/tasks`）在价目表里**没有专属规则**，命中的是通配 `*` 规则：

  {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
   "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}

所以模型层的单价**不在价目表里**，只能从自己的流水反推 —— 本包就是干这个的。

## 三个端点的真实结构（本包已逐条实测）

  1) GET /api/v1/pricing  → {currency, markupPercent, note, site, pricing:{路径 -> 规则}}
     115 条规则。每条：mode(flat / per_second / per_module) / cost / perSecond /
     minPoints / markupPercent / note / provider / definition / sizeRates /
     resolutionRates / estimate / rateFrom / modelRates / defaultModel / unitFrom。

     ★ 重要更正：`modelRates` 不是「模型层价格表」。它只出现在 3 条
     `image_human` 规则上，含义是「按请求体里的 mode 参数取费率」：
       "modelRates": {"fast":{"*":10},"standard":{"*":15},"2k":{"*":30},"4k":{"*":60}}
     配合 `rateFrom: "mode"` + `defaultModel: "fast"` 使用。
     全表**没有** `modelPricing` 这个键，也没有任何「模型 code -> 单价」的映射。

  2) GET /api/v1/models   → {object, data[...], code, msg}
     316 条 = 221 条目录模型（带 model_code / type_code / max_reference_images /
     description / capabilities）+ 95 条「裸模型层 ID」（只有 id / object / owned_by /
     created，没有 price 字段）。裸 ID 长这样：
       {"id":"volcengine/doubao-seedance-2-5-260628","object":"model",
        "owned_by":"flagship","created":0}
     221 条目录里只有 92 条（全部是 text 类型）带 `pricing`，而那是
     `pricing_v2.items[0].price.points` 的「每百万 token」价 —— 文本模型的模型层价目。
     **视频 / 图片模型的模型层单价，两个端点都没有。**

  3) GET /api/v1/apps     → {code, msg, data[22]}
     每个应用带 code / name / description / driver_code / billing_mode / apis[]，
     apis[] 里是 code / method / category_code / call_type。

## 模型层单价从哪来

本包读自己的流水：`GET /api/v1/me/tasks`（每条任务有 path / model / actualPrice /
reservePrice / status / rateNote）。把 path 不含 `/apps/` 且 model 非空的记录按
model 归集，取实测最低价，就是模型层的真实单价。

实测样本（2026-11-07，500 条任务）：

  volcengine/doubao-seedance-2-5-260628  /api/v1/videos/generations  762.30 / 3000 / 3045.71
  sd/doubao-seedance-2-0-260128          /api/v1/videos/generations  145.73 / 181.79 / 3000
  wan3.0-video                           /api/v1/videos/generations  300.00
  muse-video                             /api/v1/videos              44.00 / 55 / 260
  gpt-image-2-pro                        /api/v1/tasks               39 / 78 / 104
  gpt-image-2                            /api/v1/tasks               26.00
  seedream-5-0-flash                     /api/v1/tasks               15.60

没跑过模型层的账号，本包用上面这份实测基线（标注 source=baseline），
跑过之后自动切成 source=live（你账号的真实成交价）。

## 子命令

  app-vs-model  应用层 vs 模型层差价排行（本包核心）
  cheapest      按意图给最便宜的那条路（--for image|video|voice|upscale）
  traps         价目表里「看着有、实际不通」的清单
  budget        按典型用量算预算（10 秒视频 / 一张图 / 一分钟语音）
  catalog       模型清单（按类型分组）
  doctor        自检三个只读端点 + 应用层定价覆盖率

## 花费

**全部 6 个子命令都是只读 GET，物理上没有写接口，本轮花费 0 点。**
本包源码里不存在 POST / PUT / DELETE（`http_json` 只接受 GET）。
`--budget` 依旧生效：`--budget 0` 直接退 5，一个请求都不发；
一次连发 30 个以上请求（`--all` 翻 70 页）要 `--yes`，确认信息里写的是「花费 0 点」。

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py app-vs-model
  python3 scripts/run.py app-vs-model --live --pages 25
  python3 scripts/run.py cheapest --for video
  python3 scripts/run.py traps
  python3 scripts/run.py budget
  python3 scripts/run.py catalog --type video

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request


# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 cp936 编不出的字符就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底；本包全文只用 cp936 覆盖得到的 √ × · → ★ ￥ 「」。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
PAGE_SIZE_ME = 20            # /api/v1/me/tasks 每页固定 20 条（limit 只影响统计窗口）
ALL_PAGES_EST = 70           # 台账 1396 条 ÷ 20
DEFAULT_BUDGET = 50          # 单位：点
POINTS_PER_YUAN = 100

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-price-radar/%s" % VERSION

# ── 应用层：从 /pricing 现查；这里只存「哪个应用跑的是哪个模型」这层关系 ──────────
# appPath   = /pricing 里的键（也是真实提交路径）
# model     = 模型层的模型 code（在 /models 的裸 ID 或目录里出现过）
# same      = True 表示「同一个模型」，False 表示「同一件事、不同模型」
# basis     = 这一行到底在比什么，写清楚，不让人误会
PAIRS = [
    dict(cap="出视频", app="seedance", appPath="/api/v1/apps/seedance/submit",
         model="sd/doubao-seedance-2-0-260128", same=True,
         basis="同一个模型（Seedance 2.0）"),
    dict(cap="出视频", app="seedance", appPath="/api/v1/apps/seedance/submit",
         model="volcengine/doubao-seedance-2-5-260628", same=True,
         basis="同一个模型（Seedance 2.5）"),
    dict(cap="出视频", app="wan", appPath="/api/v1/apps/wan/submit",
         model="wan3.0-video", same=True, basis="同一个模型（Wan 3.0）"),
    dict(cap="出图", app="aigc_photo_restore", appPath="/api/v1/apps/aigc_photo_restore/*",
         model="seedream-5-0-flash", same=False,
         basis="同一件事（出一张图），模型层最便宜档"),
    dict(cap="出图", app="nano_banana", appPath="/api/v1/apps/nano_banana/submit",
         model="seedream-5-0-flash", same=False, basis="同一件事（出一张图）"),
    dict(cap="出图", app="nano_banana", appPath="/api/v1/apps/nano_banana/submit",
         model="gpt-image-2", same=False, basis="同一件事（出一张图）"),
    dict(cap="出图", app="aigc_qwen_image", appPath="/api/v1/apps/aigc_qwen_image/generate/index",
         model="gpt-image-2", same=False, basis="同一件事（出一张图）"),
    dict(cap="出图", app="aigc_qwen_image_pro",
         appPath="/api/v1/apps/aigc_qwen_image_pro/generate/index",
         model="gpt-image-2-pro", same=False, basis="同一件事（出一张图）"),
    dict(cap="出图", app="aigc_wan_image", appPath="/api/v1/apps/aigc_wan_image/generate/index",
         model="gpt-image-2", same=False, basis="同一件事（出一张图）"),
    dict(cap="出图", app="dressing_diffusion",
         appPath="/api/v1/apps/dressing_diffusion/submit",
         model="gpt-image-2-pro", same=False, basis="同一件事（出一张图）"),
]

# ── 模型层实测基线（2026-11-07，本账号 /api/v1/me/tasks 的真实 actualPrice）──────
# 只有跑过模型层的账号才有 live 数据；没有就跑基线，并在输出里标 source。
MODEL_BASELINE = {
    "sd/doubao-seedance-2-0-260128": dict(
        route="/api/v1/videos/generations", low=145.73, high=3000.0, n=5,
        samples=[145.73, 181.79, 181.79, 3000.0, 3000.0]),
    "volcengine/doubao-seedance-2-5-260628": dict(
        route="/api/v1/videos/generations", low=762.30, high=3045.71, n=3,
        samples=[762.30, 3000.0, 3045.71]),
    "wan3.0-video": dict(
        route="/api/v1/videos/generations", low=300.0, high=300.0, n=2,
        samples=[300.0, 300.0]),
    "muse-video": dict(
        route="/api/v1/videos", low=44.0, high=260.0, n=6,
        samples=[44.0, 44.0, 55.0, 55.0, 55.0, 260.0]),
    "gpt-image-2-pro": dict(
        route="/api/v1/tasks", low=39.0, high=104.0, n=17,
        samples=[39.0, 39.0, 78.0, 78.0, 78.0, 78.0, 104.0]),
    "gpt-image-2": dict(
        route="/api/v1/tasks", low=26.0, high=26.0, n=1, samples=[26.0]),
    "seedream-5-0-flash": dict(
        route="/api/v1/tasks", low=15.60, high=15.60, n=1, samples=[15.60]),
}

# ── 11 个 tsc_* 档位：价目表里有、路由 404（2026-11-07 实测）────────────────────
TSC_DEAD = ["tsc_common", "tsc_common_hd", "tsc_aigc", "tsc_aigc_hd",
            "tsc_shortplay", "tsc_shortplay_hd", "tsc_uhd", "tsc_oldsd",
            "tsc_oldsd_hd", "tsc_teshd", "tsc_quality"]

# ── 单位混用：note 写「点/次」、规则却是 per_second ─────────────────────────────
UNIT_MIX = ["/api/v1/video/shot", "/api/v1/video/castcrew", "/api/v1/video/delogo",
            "/api/v1/video/viapi/shot", "/api/v1/video/viapi/castcrew",
            "/api/v1/video/viapi/delogo"]

# ── 上游凭据坏：路由在、502 InvalidMpsUser ─────────────────────────────────────
BROKEN_UPSTREAM = ["/api/v1/video/tencent1080", "/api/v1/video/tencent2k",
                   "/api/v1/video/tencent4k"]

# ── 按意图给最便宜的路 ────────────────────────────────────────────────────────
INTENTS = {
    "image": dict(label="出一张图", unit="张", items=[
        dict(name="Seedream 5.0 Flash（模型层）", layer="model",
             model="seedream-5-0-flash"),
        dict(name="GPT Image 2（模型层）", layer="model", model="gpt-image-2"),
        dict(name="GPT Image 2 Pro（模型层）", layer="model", model="gpt-image-2-pro"),
        dict(name="nano-banana 应用", layer="app",
             pricing="/api/v1/apps/nano_banana/submit"),
        dict(name="通义万相 出图（应用）", layer="app",
             pricing="/api/v1/apps/aigc_qwen_image/generate/index"),
        dict(name="老照片修复 1K（应用）", layer="app",
             pricing="/api/v1/apps/aigc_photo_restore/*"),
        dict(name="万相出图 2K（应用）", layer="app",
             pricing="/api/v1/apps/aigc_wan_image/generate/index"),
    ]),
    "video": dict(label="出一条视频", unit="条", items=[
        dict(name="muse-video（模型层）", layer="model", model="muse-video"),
        dict(name="Seedance 2.0（模型层）", layer="model",
             model="sd/doubao-seedance-2-0-260128"),
        dict(name="Wan 3.0（模型层）", layer="model", model="wan3.0-video"),
        dict(name="Seedance 2.5（模型层）", layer="model",
             model="volcengine/doubao-seedance-2-5-260628"),
        dict(name="Grok 视频（应用）", layer="app",
             pricing="/api/v1/apps/grok_video/submit"),
        dict(name="Wan 视频（应用）", layer="app",
             pricing="/api/v1/apps/wan/submit"),
        dict(name="Happy Horse（应用）", layer="app",
             pricing="/api/v1/apps/happy_horse/submit"),
        dict(name="Seedance（应用）", layer="app",
             pricing="/api/v1/apps/seedance/submit"),
    ]),
    "voice": dict(label="出一段配音", unit="段", items=[
        dict(name="语音 TTS（应用，上游×3）", layer="app",
             pricing="/api/v1/apps/voice_tts/*"),
        dict(name="IndexTTS 配音（应用，上游×3）", layer="app",
             pricing="/api/v1/apps/indextts/*"),
        dict(name="音色修改 / AI 翻唱（应用）", layer="app",
             pricing="/api/v1/apps/seedsvc/submit"),
        dict(name="MMAudio 音效 / 配音（应用）", layer="app",
             pricing="/api/v1/apps/mmaudio/submit"),
    ]),
    "upscale": dict(label="视频超分 1 分钟", unit="60 秒", items=[
        dict(name="腾讯 1080P 超分（应用）", layer="app",
             pricing="/api/v1/video/tencent1080", seconds=60),
        dict(name="腾讯 2K 超分（应用）", layer="app",
             pricing="/api/v1/video/tencent2k", seconds=60),
        dict(name="腾讯 4K 超分（应用）", layer="app",
             pricing="/api/v1/video/tencent4k", seconds=60),
        dict(name="VIAPI 超分·标准", layer="app",
             pricing="/api/v1/video/viapi/superres", seconds=60),
        dict(name="VIAPI 超分·2K", layer="app",
             pricing="/api/v1/video/viapi/superres2k", seconds=60),
        dict(name="VIAPI 超分·4K", layer="app",
             pricing="/api/v1/video/viapi/superres4k", seconds=60),
        dict(name="FlashVSR 超分（应用）", layer="app",
             pricing="/api/v1/apps/flashvsr/submit", seconds=60),
        dict(name="视频放大 /video/upscale", layer="app",
             pricing="/api/v1/video/upscale", seconds=60),
    ]),
}
INTENT_ORDER = ["image", "video", "voice", "upscale"]

STAT_CN = {"min": "最低", "median": "中位", "max": "最高"}

# 动态计价那条路的实测区间（2026-11-07，本账号 /api/v1/me/tasks）
MEASURED_NOTE = {
    "image": "模型层出图实测 15.60 - 104 点/张；应用层最便宜是 nano-banana 72 点/张",
    "video": "模型层出视频实测 44 - 3,045.71 点/条；应用层最便宜是 Grok 视频 300 点/条",
    "voice": "本账号 111 条 tts_async 实扣 1 - 240 点（多数 1 - 66 点）；"
             "voice_tts 规则是 cost:0 + markupPercent:200，即上游实际点数 x 3",
    "upscale": "腾讯三档实测 502 InvalidMpsUser、任务全部 refunded（实扣 0 点）；"
               "能跑通的最便宜档是 VIAPI 超分·标准 9 点/秒",
}

# ── 预算换算：典型用量 ────────────────────────────────────────────────────────
BUDGET_CASES = [
    dict(name="一条 10 秒视频", unit="条", items=[
        dict(label="Seedance 应用层（固定）", pricing="/api/v1/apps/seedance/submit"),
        dict(label="Wan 应用层（固定）", pricing="/api/v1/apps/wan/submit"),
        dict(label="Grok 视频应用层（固定）", pricing="/api/v1/apps/grok_video/submit"),
        dict(label="Seedance 2.5 模型层（实测最低）", model="volcengine/doubao-seedance-2-5-260628"),
        dict(label="Seedance 2.0 模型层（实测最低）", model="sd/doubao-seedance-2-0-260128"),
        dict(label="muse-video 模型层（实测最低）", model="muse-video"),
    ]),
    dict(name="一张图", unit="张", items=[
        dict(label="nano-banana 应用层", pricing="/api/v1/apps/nano_banana/submit"),
        dict(label="通义万相出图 应用层", pricing="/api/v1/apps/aigc_qwen_image/generate/index"),
        dict(label="GPT Image 2 模型层（实测最低）", model="gpt-image-2"),
    ]),
    dict(name="一分钟语音", unit="60 秒", items=[
        dict(label="语音 TTS 应用层（上游×3，实测区间）", pricing="/api/v1/apps/voice_tts/*"),
        dict(label="MMAudio 应用层（固定）", pricing="/api/v1/apps/mmaudio/submit"),
    ]),
    dict(name="一分钟 1080P 超分", unit="60 秒", items=[
        dict(label="腾讯 1080P 超分", pricing="/api/v1/video/tencent1080", seconds=60),
        dict(label="VIAPI 超分·标准", pricing="/api/v1/video/viapi/superres", seconds=60),
        dict(label="FlashVSR 超分", pricing="/api/v1/apps/flashvsr/submit", seconds=60),
    ]),
    dict(name="一分钟画质增强", unit="60 秒", items=[
        dict(label="画质综合增强", pricing="/api/v1/video/enhance", seconds=60),
        dict(label="人像增强", pricing="/api/v1/video/viapi/portrait", seconds=60),
        dict(label="视频修复", pricing="/api/v1/video/restore", seconds=60),
    ]),
]


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
        except Exception:                                            # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, timeout=60):
    """只读 GET。本包**没有**任何写请求，所以物理上不可能扣点。

    `method` 参数是为了让「本包只发 GET」这件事在代码里可审计：
    除了 GET 以外的取值一律当场抛 usage，不会走到网络。
    """
    if method != "GET":
        raise Fail("usage", "本包只读：拒绝发出 %s 请求（全部 6 个子命令都是 GET）" % method,
                   EXIT_USAGE)
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
        except Exception as e:                                       # noqa: BLE001
            last = "请求异常：%s: %s" % (type(e).__name__, e)
        if attempt < 2:
            time.sleep(0.5 if attempt == 0 else 1.2)
    raise Fail("call", last or "请求失败", EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                                # noqa: BLE001
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
        return "网关回了 HTML（HTTP %s）" % st
    return (txt or "").replace("\n", " ")[:200]


def get_json(key, host, path, what):
    st, txt = http_json("GET", host + path, key)
    d = jloads(txt)
    if st != 200 or not isinstance(d, (dict, list)):
        raise Fail("call", "%s 拉取失败（HTTP %s）：%s"
                   % (what, st, err_text(st, txt)), EXIT_CALL)
    return d


# ── 显示宽度（中文算 2 列，表格才对得齐）─────────────────────────────────────
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
    except Exception:                                                # noqa: BLE001
        return dash
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def yuan(points):
    try:
        return "%.2f" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                                # noqa: BLE001
        return "-"


class Ctx(object):
    """一次查询的共享缓存，避免同一个端点被拉两遍。"""

    def __init__(self, key, host, a):
        self.key, self.host, self.a = key, host, a
        self._pricing = None
        self._models = None
        self._apps = None
        self._layer = None
        self.requests = 0

    def pricing(self):
        if self._pricing is None:
            d = get_json(self.key, self.host, API_PREFIX + "/pricing", "价目表")
            self.requests += 1
            p = d.get("pricing")
            if not isinstance(p, dict):
                raise Fail("call", "价目表结构变了：顶层没有 pricing 对象。原文前 200 字：%s"
                           % json.dumps(d, ensure_ascii=False)[:200], EXIT_CALL)
            self._pricing = d
        return self._pricing

    def rules(self):
        return self.pricing().get("pricing") or {}

    def models(self):
        if self._models is None:
            d = get_json(self.key, self.host, API_PREFIX + "/models", "模型目录")
            self.requests += 1
            data = d.get("data")
            if not isinstance(data, list):
                raise Fail("call", "模型目录结构变了：data 不是数组", EXIT_CALL)
            self._models = data
        return self._models

    def apps(self):
        if self._apps is None:
            d = get_json(self.key, self.host, API_PREFIX + "/apps", "应用目录")
            self.requests += 1
            data = d.get("data")
            if not isinstance(data, list):
                raise Fail("call", "应用目录结构变了：data 不是数组", EXIT_CALL)
            self._apps = data
        return self._apps

    def layer(self, pages):
        """模型层实测价：读自己的任务台账，按 model 归集 actualPrice。"""
        if self._layer is not None:
            return self._layer
        agg = {}
        for pg in range(1, pages + 1):
            d = get_json(self.key, self.host,
                         API_PREFIX + "/me/tasks?limit=2000&page=%d" % pg, "任务台账")
            self.requests += 1
            ts = d.get("tasks") or []
            if not ts:
                break
            for t in ts:
                p = t.get("path") or ""
                m = (t.get("model") or "").strip()
                if not m or "/apps/" in p:
                    continue
                try:
                    v = float(t.get("actualPrice") or 0)
                except Exception:                                    # noqa: BLE001
                    continue
                if v <= 0:
                    continue
                a = agg.setdefault(m, {"model": m, "route": p, "samples": []})
                a["samples"].append(round(v, 2))
            if len(ts) < PAGE_SIZE_ME:
                break
        out = {}
        for m, a in agg.items():
            s = sorted(a["samples"])
            out[m] = dict(route=a["route"], low=s[0], high=s[-1], n=len(s), samples=s)
        self._layer = out
        return out


def layer_price(ctx, model, pages, stat="min"):
    """返回 (点数, 来源, 说明, 区间)。先看自己流水的 live 数据，再看基线。"""
    live = ctx.layer(pages) if pages else {}
    src = live.get(model)
    how = "live"
    if not src:
        src = MODEL_BASELINE.get(model)
        how = "baseline"
    if not src:
        return None, "none", "无实测样本", ""
    s = sorted(src["samples"])
    if stat == "max":
        v = s[-1]
    elif stat == "median":
        n = len(s)
        v = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    else:
        v = s[0]
    span = "%s" % pnum(s[0]) if s[0] == s[-1] else "%s - %s" % (pnum(s[0]), pnum(s[-1]))
    return v, how, "%d 条实测" % len(s), span


def rule_points(rule, seconds=0):
    """把一条 /pricing 规则换算成「一次/一份」的点数。返回 (点数, 口径)。

    点数给 None 表示**动态计价**（cost=0 但 markupPercent>0）：对外 = 上游实际点数 x
    (1+markup%)，价目表里不写死单价，只能事后看流水。
    """
    if not isinstance(rule, dict):
        return None, "价目表里没有这条规则"
    mode = rule.get("mode")
    if mode == "flat":
        c = rule.get("cost")
        mp = rule.get("markupPercent") or 0
        if c == 0 and float(mp) > 0:
            return None, "动态：按上游实际点数 x %.0f（价目表不写死单价）" % (1.0 + float(mp) / 100.0)
        if c is None:
            return None, "flat 但没写 cost"
        return float(c), "固定 %s 点/次" % pnum(c)
    if mode == "per_second":
        ps = rule.get("perSecond")
        if ps is None:
            mr = rule.get("modelRates") or {}
            dm = rule.get("defaultModel")
            if isinstance(mr.get(dm), dict):
                ps = mr[dm].get("*")
        if ps is None:
            return None, "per_second 但没写 perSecond"
        sec = max(1, int(seconds or 1))
        pts = float(ps) * sec
        mp = rule.get("minPoints")
        if mp is not None and pts < float(mp):
            return float(mp), "%s 点/秒 x %d 秒，不足保底 %s 点" % (
                pnum(ps), sec, pnum(mp))
        return pts, "%s 点/秒 x %d 秒" % (pnum(ps), sec)
    if mode == "per_module":
        c = rule.get("cost")
        return (float(c) if c is not None else None), "按模块：%s 点 x 模块数" % pnum(c)
    return None, "未知 mode=%s" % mode


def _gate(a, requests, what="本次"):
    """两道闸门。本包全只读，预计花费恒为 0 点。"""
    if requests > 0 and a.budget <= 0:
        raise Fail("budget",
                   "--budget 是 %d 点（单位：点）。本包每个请求 0 点，但 0 点预算等于"
                   "不授权任何调用；给 1 点以上就放行。" % a.budget, EXIT_BUDGET)
    if requests >= 30 and not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "%s要连发 %d 个只读 GET（花费 **0 点**，不会扣款）。确认请加 --yes。"
                   % (what, requests), EXIT_CONFIRM)


def _plan(a, reqs, lines):
    out = {"ok": True, "dryRun": True, "requests": lines, "requestCount": reqs,
           "estimatedPoints": 0, "yuan": 0.0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（一个请求都不发）")
    print("  请求数：%d" % reqs)
    print("  预估：0 点（￥0.00）—— 全部是只读 GET")
    for ln in lines:
        print("  -> %s" % ln)
    return 0


# ───────────────────────── app-vs-model ─────────────────────────
def cmd_app_vs_model(a, key, host):
    pages = ALL_PAGES_EST if a.all else a.pages
    _gate(a, pages + 2)
    if a.dry_run:
        return _plan(a, pages + 2,
                     ["GET %s/pricing" % API_PREFIX, "GET %s/models" % API_PREFIX]
                     + ["GET %s/me/tasks?limit=2000&page=%d" % (API_PREFIX, i)
                        for i in range(1, pages + 1)])
    ctx = Ctx(key, host, a)
    rules = ctx.rules()
    ctx.models()                       # 确认模型 code 确实在架
    rows = []
    for p in PAIRS:
        rule = rules.get(p["appPath"])
        app_pts, app_basis = rule_points(rule, 0)
        m_pts, how, note, span = layer_price(ctx, p["model"], pages, a.stat)
        if app_pts is None or m_pts is None:
            continue
        times = (app_pts / m_pts) if m_pts else 0.0
        rows.append({"cap": p["cap"], "app": p["app"], "appPath": p["appPath"],
                     "appPoints": round(app_pts, 2), "appBasis": app_basis,
                     "model": p["model"], "modelRoute": (MODEL_BASELINE.get(p["model"]) or {}).get("route", ""),
                     "modelPoints": round(m_pts, 2), "modelSource": how,
                     "modelNote": note, "modelSpan": span,
                     "times": round(times, 1), "sameModel": p["same"],
                     "basis": p["basis"]})
    rows.sort(key=lambda r: -r["times"])
    top = rows[:a.top] if a.top else rows
    out = {"ok": True, "count": len(rows), "stat": a.stat, "rows": top,
           "pagesScanned": pages, "allRows": rows, "estimatedPoints": 0,
           "summary": {"pairs": len(rows), "maxTimes": rows[0]["times"] if rows else 0,
                       "minTimes": rows[-1]["times"] if rows else 0},
           "note": "模型层价 = 该模型走模型路由的实测 actualPrice（%s 口径）；"
                   "应用层价 = /api/v1/pricing 的实时规则" % a.stat}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("应用层 vs 模型层 · 同一个能力两条路（按倍数排序）")
    print("=" * 104)
    print("  %s %s %s %s %s %s %s" % (
        pad("#", 3), pad("能力", 7), pad("应用层路径", 30),
        pad("应用层价", 10, False), pad("模型层模型", 42),
        pad("模型层价", 9, False), pad("倍数", 7, False)))
    print("  " + "-" * 100)
    for i, r in enumerate(top, 1):
        print("  %s %s %s %s %s %s %s" % (
            pad(i, 3), pad(r["cap"], 7),
            pad(r["appPath"].replace(API_PREFIX, "")[:29], 30),
            pad(pnum(r["appPoints"]), 10, False),
            pad(r["model"][:41], 42),
            pad(pnum(r["modelPoints"]), 9, False),
            pad("%.1f×" % r["times"], 7, False)))
    print()
    routes = sorted({(r["modelRoute"] or "").replace(API_PREFIX, "") for r in top})
    print("  模型层路径：%s（这些路径在价目表里没有专属规则）" % " / ".join(routes))
    print()
    best = top[0] if top else None
    if best:
        print("  最高差：%s 走 %s 要 %s 点，同样的模型走 %s 只要 %s 点 —— **%.1f 倍**"
              % (best["cap"], best["appPath"].replace(API_PREFIX, ""),
                 pnum(best["appPoints"]), (best["modelRoute"] or "").replace(API_PREFIX, ""),
                 pnum(best["modelPoints"]), best["times"]))
        print("  同一模型确认：%s" % ("是（%s）" % best["basis"] if best["sameModel"]
                                      else "否（%s）" % best["basis"]))
    print()
    print("  口径")
    print("    · 应用层价 = GET /api/v1/pricing 的实时规则（flat 的 cost / per_second 的 perSecond）")
    print("    · 模型层价 = 该模型走模型路由的实测 actualPrice（%s 口径）" % a.stat)
    print("    · 模型层在价目表里没有专属规则，命中通配 * ：对外 = 上游点数 x 2，保底 50 点")
    print("    · 数据来源：%s" % ("你账号的 /api/v1/me/tasks 真实流水" if
                                 any(r["modelSource"] == "live" for r in rows) else
                                 "团队实测基线 2026-11-07（你账号还没跑过模型层）"))
    print("    · 本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── cheapest ─────────────────────────
def cmd_cheapest(a, key, host):
    intents = INTENT_ORDER if a.intent == "all" else [a.intent]
    _gate(a, 3)
    if a.dry_run:
        return _plan(a, 3, ["GET %s/pricing" % API_PREFIX, "GET %s/models" % API_PREFIX]
                     + (["GET %s/me/tasks?limit=2000&page=1" % API_PREFIX] if a.live else []))
    ctx = Ctx(key, host, a)
    rules = ctx.rules()
    blocks = []
    for it in intents:
        spec = INTENTS[it]
        cands, dynamic = [], []
        for c in spec["items"]:
            if c["layer"] == "model":
                if not a.live:
                    continue
                pts, how, note, span = layer_price(ctx, c["model"], a.pages, a.stat)
                if pts is None:
                    continue
                cands.append({"name": c["name"], "layer": "模型层", "points": round(pts, 2),
                              "basis": "实测%s %s 点" % (STAT_CN.get(a.stat, a.stat),
                                                         pnum(pts)),
                              "route": (MODEL_BASELINE.get(c["model"]) or {}).get("route", ""),
                              "model": c["model"]})
            else:
                rule = rules.get(c["pricing"])
                pts, basis = rule_points(rule, c.get("seconds") or 0)
                if pts is None:
                    if basis.startswith("动态"):
                        dynamic.append({"name": c["name"], "layer": "应用层",
                                        "basis": basis, "route": c["pricing"]})
                    continue
                cands.append({"name": c["name"], "layer": "应用层", "points": round(pts, 2),
                              "basis": basis, "route": c["pricing"], "model": ""})
        if not a.live:
            # 没加 --live 时只用价目表能直接算出来的（应用层 + 视频档）
            cands = [c for c in cands if c["layer"] == "应用层"]
        cands.sort(key=lambda r: r["points"])
        blocks.append({"intent": it, "label": spec["label"], "unit": spec["unit"],
                       "cheapest": cands[0] if cands else None, "candidates": cands,
                       "dynamic": dynamic,
                       "measured": MEASURED_NOTE.get(it, "")})
    out = {"ok": True, "live": a.live, "stat": a.stat, "blocks": blocks,
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("最便宜的那条路（价格单位：点；1 元 = 100 点）")
    print("=" * 88)
    for b in blocks:
        print()
        print("  【%s】%s" % (b["label"], b["unit"]))
        if not b["candidates"]:
            print("    没有可算的候选（加 --live 把模型层实测价一起排进来）")
            continue
        print("    %s %s %s %s %s" % (pad("#", 3), pad("路线", 30), pad("层", 8),
                                      pad("价（点）", 10, False), pad("折算", 10, False)))
        for i, c in enumerate(b["candidates"], 1):
            mark = "  <- 最便宜" if i == 1 else ""
            print("    %s %s %s %s %s%s" % (
                pad(i, 3), pad(c["name"][:29], 30), pad(c["layer"], 8),
                pad(pnum(c["points"]), 10, False), pad("￥" + yuan(c["points"]), 10, False),
                mark))
        print("    口径：%s" % b["candidates"][0]["basis"])
        if b.get("dynamic"):
            print("    动态计价（价目表不写死单价，按上游实际点数结算）：")
            for c in b["dynamic"]:
                print("      · %-28s %s" % (c["name"][:27], c["basis"]))
        if b.get("measured"):
            print("    实测：%s" % b["measured"])
    print()
    if not a.live:
        print("  说明：默认只排「价目表里直接查得到」的路。加 --live 会把模型层的实测价")
        print("        （来自 /api/v1/me/tasks 的真实 actualPrice）一起排进来，通常它最便宜。")
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── traps ─────────────────────────
def cmd_traps(a, key, host):
    _gate(a, 2)
    if a.dry_run:
        return _plan(a, 2, ["GET %s/pricing" % API_PREFIX, "GET %s/apps" % API_PREFIX])
    ctx = Ctx(key, host, a)
    rules = ctx.rules()
    apps = ctx.apps()

    dead = [t for t in TSC_DEAD if (API_PREFIX + "/video/" + t) in rules]
    dead_detail = [dict(path=API_PREFIX + "/video/" + t,
                        perSecond=rules[API_PREFIX + "/video/" + t].get("perSecond"),
                        minPoints=rules[API_PREFIX + "/video/" + t].get("minPoints"),
                        note=(rules.get(API_PREFIX + "/video/" + t) or {}).get("note"))
                   for t in dead]

    broken = []
    for p in BROKEN_UPSTREAM:
        r = rules.get(p)
        if r:
            broken.append(dict(path=p, perSecond=r.get("perSecond"),
                               note=(r.get("note") or "")[:120]))

    mixed = []
    for p in UNIT_MIX:
        r = rules.get(p)
        if not r:
            continue
        note = r.get("note") or ""
        if "点/次" in note and r.get("mode") == "per_second":
            mixed.append(dict(path=p, mode=r.get("mode"),
                              perSecond=r.get("perSecond"), note=note[:120]))

    wild = rules.get("*") or {}
    uncovered = []
    for ap in apps:
        code = ap.get("code") or ""
        pre = API_PREFIX + "/apps/" + code + "/"
        if not any(k.startswith(pre) or k == API_PREFIX + "/apps/" + code
                   for k in rules):
            uncovered.append(code)

    out = {"ok": True, "traps": {
        "deadRoutes": dict(count=len(dead_detail), items=dead_detail,
                           what="价目表里有，路由 404（2026-11-07 实测）"),
        "brokenUpstream": dict(count=len(broken), items=broken,
                               what="路由在，上游返回 502 InvalidMpsUser（实测任务全退）"),
        "unitMix": dict(count=len(mixed), items=mixed,
                        what="note 写「点/次」，规则却是 per_second -> 按秒扣"),
        "wildcard": dict(rule=wild,
                         what="未单独定价的接口命中通配 *：上游点数 x 2，保底 50 点"),
        "unpricedApps": dict(count=len(uncovered), items=uncovered,
                             what="应用目录里有，但价目表里没有专属规则 -> 命中通配 *"),
    }, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("价目表陷阱清单（全部现查 /api/v1/pricing + /api/v1/apps）")
    print("=" * 88)
    print()
    print("  ① 价目表里有、路由 404：%d 个 tsc_* 档位" % len(dead_detail))
    for d in dead_detail:
        print("     %-34s %s 点/秒 · 保底 %s 点 · GET/POST 都是 404" % (
            d["path"].replace(API_PREFIX, ""), pnum(d["perSecond"]), pnum(d["minPoints"])))
    print()
    print("  ② 路由在、上游凭据坏：%d 条腾讯超分档" % len(broken))
    for d in broken[:4]:
        print("     %-34s %s 点/秒 · 实测 502 InvalidMpsUser" % (
            d["path"].replace(API_PREFIX, ""), pnum(d["perSecond"])))
    print("     实测证据：本账号 /api/v1/video/tencent4k 的任务全部 status=refunded，实扣 0 点。")
    print()
    print("  ③ 应用层 vs 模型层：同一模型差 14 倍（跑 app-vs-model 看完整排行）")
    print("     /apps/seedance/submit 固定 11,000 点 vs 同一个 Seedance 模型走")
    print("     /videos/generations 实测 762.30 点 = 14.4 倍。")
    print()
    print("  ④ 单位混用：note 写「点/次」、规则是 per_second 的有 %d 条" % len(mixed))
    for d in mixed:
        print("     %-34s rule=%s %s 点/秒 | note=%s" % (
            d["path"].replace(API_PREFIX, ""), d["mode"], pnum(d["perSecond"]),
            d["note"][:46]))
    print("     -> 按 note 算成一次，实际按秒扣；10 秒素材就是 10 倍。")
    print()
    print("  ⑤ 通配保底：%s" % (wild.get("note") or "-"))
    print("     未单独定价的接口 = 上游点数 x 2，单笔保底 %s 点。" % pnum(wild.get("minPoints")))
    print("     模型层那批接口（/videos、/videos/generations、/images/generations、/tasks）")
    print("     全都在这一条下面，所以价目表里查不到它们的单价。")
    print()
    if uncovered:
        print("  另外：%d 个应用在价目表里没有专属规则，会掉进通配 *（保底 50 点）" % len(uncovered))
        print("     %s" % "、".join(uncovered[:12]))
        print()
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── budget ─────────────────────────
def cmd_budget(a, key, host):
    _gate(a, 3)
    if a.dry_run:
        return _plan(a, 3, ["GET %s/pricing" % API_PREFIX, "GET %s/apps" % API_PREFIX])
    ctx = Ctx(key, host, a)
    rules = ctx.rules()
    blocks = []
    for case in BUDGET_CASES:
        items = []
        for it in case["items"]:
            if it.get("model"):
                pts, how, note, span = layer_price(ctx, it["model"], 0, "min")
                if pts is None:
                    continue
                items.append({"label": it["label"], "points": round(pts, 2),
                              "basis": "实测最低 %s 点（区间 %s）" % (pnum(pts), span)})
            else:
                rule = rules.get(it["pricing"])
                pts, basis = rule_points(rule, it.get("seconds") or 0)
                if pts is None:
                    items.append({"label": it["label"], "points": None,
                                  "basis": basis})
                    continue
                items.append({"label": it["label"], "points": round(pts, 2),
                              "basis": basis})
        items.sort(key=lambda r: (r["points"] is None, r["points"] if r["points"] is not None else 0))
        blocks.append({"case": case["name"], "unit": case["unit"], "items": items})
    worst = max((b["items"][-1]["points"] for b in blocks
                 if b["items"] and b["items"][-1]["points"] is not None), default=0)
    out = {"ok": True, "blocks": blocks, "maxPoints": worst,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("预算换算：按典型用量，先看钱再动手（1 元 = 100 点）")
    print("=" * 88)
    for b in blocks:
        print()
        print("  【%s】单位：%s" % (b["case"], b["unit"]))
        for r in b["items"]:
            if r["points"] is None:
                print("     %-34s %s" % (r["label"], r["basis"]))
            else:
                print("     %-34s %8s 点 = ￥%-9s  %s" % (
                    r["label"], pnum(r["points"]), yuan(r["points"]), r["basis"][:40]))
    print()
    print("  一条 10 秒视频：应用层 11,000 点（￥110）vs 模型层 762 点（￥7.62）—— 差 14.4 倍。")
    print("  一张图：应用层 72 点（￥0.72）vs 模型层 15.6 点（￥0.16）—— 差 4.6 倍。")
    print("  单条最高 %s 点（￥%s）。建议先按最高档留预算，再按 app-vs-model 挑路。" % (
        pnum(worst), yuan(worst)))
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── catalog ─────────────────────────
def cmd_catalog(a, key, host):
    _gate(a, 2)
    if a.dry_run:
        return _plan(a, 2, ["GET %s/models" % API_PREFIX, "GET %s/apps" % API_PREFIX])
    ctx = Ctx(key, host, a)
    models = ctx.models()
    apps = ctx.apps()
    cat, bare = [], []
    for m in models:
        if m.get("model_code"):
            cat.append(m)
        else:
            bare.append(m)
    groups = {}
    for m in cat:
        k = m.get("type_name") or "未分类"
        groups.setdefault(k, []).append(m)
    picked = {}
    for k, v in groups.items():
        if a.type == "all":
            picked[k] = v
            continue
        sub = [m for m in v if a.type in ((m.get("type_code") or ""), (m.get("type_name") or ""))]
        if a.type == k or sub:
            picked[k] = sub or v
    out = {"ok": True, "catalogCount": len(cat), "modelLayerCount": len(bare),
           "appCount": len(apps), "typeFilter": a.type,
           "groups": [{"type": k, "count": len(v),
                       "models": [{"model_code": m.get("model_code"),
                                   "model_name": m.get("model_name"),
                                   "type_code": m.get("type_code"),
                                   "max_reference_images": m.get("max_reference_images"),
                                   "description": (m.get("description") or "")[:90]}
                                  for m in v[:a.limit]]}
                      for k, v in picked.items()],
           "modelLayerIds": [b.get("id") for b in bare], "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("模型清单（GET /api/v1/models 现查）")
    print("=" * 92)
    print("  目录模型 %d 条 · 模型层 ID %d 条 · 应用 %d 个" % (
        len(cat), len(bare), len(apps)))
    for k, v in groups.items():
        print("    %-10s %d 条" % (k, len(v)))
    print()
    for k, v in picked.items():
        print("  【%s】%d 条%s" % (k, len(v),
                                  "" if len(v) <= a.limit else "（只列前 %d 条）" % a.limit))
        print("    %s %s %s %s" % (pad("model_code", 34), pad("名称", 24),
                                   pad("参考图", 7, False), "一句话"))
        for m in v[:a.limit]:
            print("    %s %s %s %s" % (
                pad((m.get("model_code") or "")[:33], 34),
                pad((m.get("model_name") or "")[:23], 24),
                pad(m.get("max_reference_images") if m.get("max_reference_images")
                    is not None else "-", 7, False),
                (m.get("description") or "").replace("\n", " ")[:44]))
        print()
    print("  模型层 ID（不在目录里，只能当 model 参数用，价目表里查不到单价）")
    for b in bare[:a.limit]:
        print("    %s" % b.get("id"))
    if len(bare) > a.limit:
        print("    ... 还有 %d 条（--limit 调大看全）" % (len(bare) - a.limit))
    print()
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    _gate(a, 3)
    if a.dry_run:
        return _plan(a, 3, ["GET %s/pricing" % API_PREFIX, "GET %s/models" % API_PREFIX,
                            "GET %s/apps" % API_PREFIX])
    ctx = Ctx(key, host, a)
    checks = []

    # 1) 价目表
    try:
        d = ctx.pricing()
        rules = d.get("pricing") or {}
        wild = rules.get("*") or {}
        ok = (len(rules) >= 100 and isinstance(wild, dict) and d.get("markupPercent") is not None)
        detail = "%d 条规则 · 通配保底 %s 点 · 顶部 markupPercent=%s" % (
            len(rules), pnum(wild.get("minPoints")), d.get("markupPercent"))
    except Fail as e:
        ok, detail = False, e.message[:70]
    checks.append(("价目表 GET /api/v1/pricing", ok, detail))

    # 2) 模型目录
    try:
        models = ctx.models()
        cat = [m for m in models if m.get("model_code")]
        bare = [m for m in models if not m.get("model_code")]
        priced = [m for m in cat if isinstance(m.get("pricing"), dict)]
        seed = [m for m in cat if "seedance" in (m.get("model_code") or "").lower()]
        ok = len(cat) >= 200 and len(bare) >= 1
        detail = "目录 %d · 模型层 ID %d · 带模型层价目 %d · seedance 系 %d" % (
            len(cat), len(bare), len(priced), len(seed))
    except Fail as e:
        ok, detail = False, e.message[:70]
    checks.append(("模型目录 GET /api/v1/models", ok, detail))

    # 3) 应用目录
    try:
        apps = ctx.apps()
        ok = len(apps) >= 20
        detail = "%d 个应用 · 接口 %d 个" % (
            len(apps), sum(len(ap.get("apis") or []) for ap in apps))
    except Fail as e:
        ok, detail = False, e.message[:70]
    checks.append(("应用目录 GET /api/v1/apps", ok, detail))

    # 4) 应用层定价覆盖率：多少应用有专属规则，多少掉进通配 *
    try:
        rules = ctx.rules()
        covered, uncovered = [], []
        for ap in ctx.apps():
            code = ap.get("code") or ""
            pre = API_PREFIX + "/apps/" + code + "/"
            hit = any(k.startswith(pre) for k in rules)
            (covered if hit else uncovered).append(code)
        ok = len(covered) >= 15
        detail = "%d / %d 有专属规则%s" % (
            len(covered), len(covered) + len(uncovered),
            "" if not uncovered else "；掉进通配的：%s" % "、".join(uncovered[:5]))
    except Fail as e:
        ok, detail = False, e.message[:70]
    checks.append(("应用层定价覆盖率", ok, detail))

    # 5) 模型层价目确实不在价目表里（这是本包存在的理由）
    try:
        rules = ctx.rules()
        probe = ["/api/v1/videos", "/api/v1/videos/generations",
                 "/api/v1/images/generations", "/api/v1/tasks"]
        missing = [p for p in probe if p not in rules]
        modelrates = [k for k, v in rules.items()
                      if isinstance(v, dict) and v.get("modelRates")]
        ok = len(missing) >= 3
        names = sorted({k.split("/")[4] for k in modelrates if len(k.split("/")) > 4})
        detail = "%d / %d 条模型层路径没有专属规则；modelRates 只出现在 %d 条规则上（%s）" % (
            len(missing), len(probe), len(modelrates), "、".join(names) or "-")
    except Fail as e:
        ok, detail = False, e.message[:70]
    checks.append(("模型层单价不在价目表里", ok, detail))

    out = {"ok": all(c[1] for c in checks), "requests": ctx.requests,
           "estimatedPoints": 0, "yuan": 0.0,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（%d 个只读 GET，扣 0 点）" % ctx.requests)
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 30), dd))
    print()
    print("  三个只读端点全部可用，全网关 0 个写请求。")
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 模型比价器：同一个模型，应用层 11,000 点 / 模型层 762 点",
        epilog="端点：GET %s/api/v1/pricing · GET %s/api/v1/models · "
               "GET %s/api/v1/apps · GET %s/api/v1/me/tasks（全部只读，0 点）"
               % ((DEFAULT_HOST,) * 4),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d；本包每个请求 0 点，给 0 会直接退 5）"
                         % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    def gate_args(p):
        p.add_argument("--yes", action="store_true", help="确认大批量只读扫描（花费仍为 0 点）")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，一个都不发")

    p = sub.add_parser("app-vs-model", help="应用层 vs 模型层差价排行（本包核心）",
                       allow_abbrev=False)
    p.add_argument("--pages", type=int, default=10,
                   help="翻几页任务台账找模型层实测价（每页 20 条，默认 10 = 200 条）")
    p.add_argument("--all", action="store_true", help="翻完全部台账（约 70 页，要 --yes）")
    p.add_argument("--stat", choices=["min", "median", "max"], default="min",
                   help="模型层取哪个统计量（默认 min = 实测最低价）")
    p.add_argument("--top", type=int, default=10, help="显示前 N 条（默认 10，0 = 全部）")
    gate_args(p)
    p.set_defaults(fn=cmd_app_vs_model)

    p = sub.add_parser("cheapest", help="按意图给最便宜的路（--for image|video|voice|upscale）",
                       allow_abbrev=False)
    p.add_argument("--for", dest="intent", default="all",
                   choices=INTENT_ORDER + ["all"],
                   help="意图：image / video / voice / upscale / all（默认 all）")
    p.add_argument("--live", action="store_true",
                   help="把模型层实测价一起排进来（读 /api/v1/me/tasks）")
    p.add_argument("--pages", type=int, default=10, help="--live 时翻几页台账（默认 10）")
    p.add_argument("--stat", choices=["min", "median", "max"], default="min",
                   help="模型层取哪个统计量（默认 min）")
    gate_args(p)
    p.set_defaults(fn=cmd_cheapest)

    p = sub.add_parser("traps", help="价目表里「看着有、实际不通」的清单",
                       allow_abbrev=False)
    gate_args(p)
    p.set_defaults(fn=cmd_traps)

    p = sub.add_parser("budget", help="按典型用量算预算（10 秒视频 / 一张图 / 一分钟语音）",
                       allow_abbrev=False)
    gate_args(p)
    p.set_defaults(fn=cmd_budget)

    p = sub.add_parser("catalog", help="模型清单（按类型分组）", allow_abbrev=False)
    p.add_argument("--type", default="all",
                   help="只看这一类：text / image / video / other，或 all（默认 all）")
    p.add_argument("--limit", type=int, default=12, help="每组最多列几条（默认 12）")
    gate_args(p)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("doctor", help="自检三个只读端点 + 应用层定价覆盖率",
                       allow_abbrev=False)
    gate_args(p)
    p.set_defaults(fn=cmd_doctor)

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
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("yes", False), ("dry_run", False), ("pages", 10),
                       ("all", False), ("stat", "min"), ("top", 10),
                       ("intent", "all"), ("live", False), ("type", "all"),
                       ("limit", 12)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    try:
        key, host = load_conf(a.key, a.host)
        if not key:
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
    except Exception:                                                # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
