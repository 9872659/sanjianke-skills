#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 素材库管家（sanjianke-asset-vault）

素材上传、打标签、复用、清理 —— 这一层所有生成类 Skill 都缺，本包补上。
**这是「素材管理」，不是「生成」**：默认动作全部 0 点，只有你显式加 --yes 才动钱。

## 实测事实（2026-11-08，GET /api/v1/pricing + GET /api/v1/apps，全部免费）

  上传     POST /api/v1/upload
           价目表规则：{"mode":"flat","cost":0,"markupPercent":0,
           "note":"★上传不计费（2026-10-04 站主批准）…"}
           返回 data.url / data.path / data.size / data.mime_type / data.type
           地址**最长 24 小时**，平台可提前回收（文档原文）
           缺 file 字段：HTTP 200 {"code":0,"msg":"请使用 file 字段提交一个文件","data":null}

  登记     11 个应用各有 create / remove 两条计价规则（/pricing 共 115 条里的 22 条）：
           dressing_diffusion create 200 点/次      remove 动态 ×2
           grok_video         create 300 点/次      remove 动态 ×2
           happy_horse        create 650 点/次      remove 动态 ×2
           image_human        create 10/15/30/60 点/输入秒（fast/standard/2k/4k）
                              remove 动态 ×2
           lipsync            create 动态 ×3（保底 1 点） remove 动态 ×3（保底 1 点）
           nano_banana        create 72 点/次（带 views[] 时 25 点 × 视角数）
                              remove 动态 ×2
           seedance           create 11,000 点/次    remove 动态 ×2
           seedsvc            create 220 点/次      remove 动态 ×2
           smart_clip         create 45 点/次       remove 动态 ×2
           wan                create 动态 ×3（保底 1 点） remove 动态 ×2
           watermark_removal  create 动态 ×2        remove **100 点/次固定**

  两个反直觉的事实（catalog 里逐条标出）：
     1) 「remove 清理」不是免费动作：10 个应用的 remove 是动态计价（上游实际点数 ×2），
        watermark_removal 的 remove 更是主业务「去水印」100 点/次。
     2) 价目表里有 create/remove 规则 ≠ 应用目录登记了这个接口。实测 /api/v1/apps
        只有 happy_horse / wan / seedance 登记了 create，只有 watermark_removal 登记了
        remove；其余 create 是 submit 的同价别名。bind 默认打「应用目录登记的那个入口」。

  素材入库  seedance 另有三件套（应用目录登记，价目表**没有专属规则**）：
           POST /api/v1/apps/seedance/createGroup   建素材分组（Name 必填）
           POST /api/v1/apps/seedance/createAsset   把 URL 入库（URL/GroupId/AssetType 必填）
           POST /api/v1/apps/seedance/deleteAsset   删素材
           这三条会命中 /api/v1/apps/seedance/* 这条通配规则 = **固定 11,000 点/次**
           （价目表字面如此；本包不替你花钱验证，catalog 把规则原文摆出来）。
           其余未定价接口命中全局通配 *：上游实际点数 ×2，单笔保底 50 点。
           → 这类单价只能从 GET /api/v1/me/tasks 的 actualPrice 反推（免费）：
             有历史成交就标 source=live，没有就标 baseline。

## 子命令（免费 / 付费分得很清）

  upload    批量上传本地素材 → 本地台账（免费；/upload 的规则 cost=0）
  catalog   11 个应用的 create / remove 两条路 + 单价 + 应用目录登记情况（免费）
  cost      先算钱：同一份素材投给多个应用，逐个报价（免费）
  doctor    自检 9 个只读端点 + 上传探针（免费，不扣费、不冻结）
  ls        本地台账：剩余有效期、标签、绑定（免费，不联网）
  tag       给台账条目打标签 / 写备注（免费，不联网）
  prune     清理过期台账条目（免费，不联网；不删远端）
  bind      把素材登记进某个应用（**付费**，要 --yes，受 --budget 管）
  release   从应用清理素材（**付费**，要 --yes，受 --budget 管）

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py upload --file 产品图.png --tag product --note "白底主图"
  python3 scripts/run.py ls
  python3 scripts/run.py cost --apps smart_clip,wan,seedance --seconds 10
  python3 scripts/run.py bind --app wan --id a1b2c3d4 \
      --param model=wan2.7 --param prompt="复古跑车沿海岸公路" \
      --param 'image_urls=["https://..."]' --seconds 10 --yes
  python3 scripts/run.py release --app wan --param task_id=task_xxx --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import hashlib
import io
import json
import mimetypes
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid


# ── GBK 编码兜底（2026-11-08 实测）──────────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8。
# 先加 errors='replace' 兜底；本包全部输出只用 cp936 编得出的字符：
# √ × · → 「」 与汉字，不用 ✓ ✗ ¥ ★ █ 这类 cp936 编不出的符号。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
UPLOAD_PATH = API_PREFIX + "/upload"
VAULT_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "asset-vault")
LEDGER = os.path.join(VAULT_DIR, "ledger.json")

TTL_HOURS = 24                         # 上传地址最长有效期（文档原文）
MAX_UPLOAD_BYTES = 512 * 1024 * 1024   # 单文件默认上限 512 MB（文档原文）
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 5000                  # 单位：点（= 50 元）
WILDCARD_MIN = 50                      # 全局通配 * 的保底点数
VIEWS_POINTS = 25                      # nano_banana 商品多角度：25 点/视角（价目表 note）

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-asset-vault/%s" % VERSION

# ───────────────────────── 11 个应用的素材入口 ─────────────────────────
# create / remove 的价格全部来自 GET /api/v1/pricing（2026-11-08 实测，免费）。
# entry = /api/v1/apps 目录里真正登记的创建入口；其余应用只登记了 submit。
# field = 素材 URL 默认落在哪个字段；None 表示素材要进数组/对象，必须用 --param 明确给。
APPS = {
    "dressing_diffusion": dict(
        name="AI 换装", entry="submit", field="image_url",
        what="把商品图 / 模特图交给换装应用"),
    "grok_video": dict(
        name="Grok 视频生成", entry="submit", field="image_url",
        what="图生视频，素材当参考帧"),
    "happy_horse": dict(
        name="快乐马视频", entry="create", field="media",
        what="文生 / 图生短视频，素材放 media（文档字段名）"),
    "image_human": dict(
        name="全驱动数字人", entry="submit", field="image_url",
        what="照片生成数字人，按输入秒计价"),
    "lipsync": dict(
        name="数字人对口型", entry="submit", field="image_url",
        what="给照片 / 视频配口型"),
    "nano_banana": dict(
        name="nano-banana 出图", entry="submit", field="image_url",
        what="AI 商品图，素材当参考图"),
    "seedance": dict(
        name="Seedance 2.0", entry="create", field=None,
        hint='--param \'content=[{"type":"image_url","image_url":{"url":"<素材地址>"}}]\'',
        what="多模态视频生成，素材放 content[]（文档字段）"),
    "seedsvc": dict(
        name="音色修改 / AI 翻唱", entry="submit", field="audio_url",
        what="把音频素材交给翻唱应用"),
    "smart_clip": dict(
        name="智能剪辑", entry="broadcast_mixcut", field="video_url",
        what="素材混剪 / 真人播报，素材当片源（没有 submit，入口是三项剪辑）"),
    "wan": dict(
        name="Wan 视频生成", entry="create", field=None,
        hint='--param \'image_urls=["<素材地址>"]\' 或 '
             '--param \'image_with_roles=[{"url":"<素材地址>","role":"reference_image"}]\'',
        what="角色参考生视频，素材放 image_urls[] / image_with_roles[]（文档字段）"),
    "watermark_removal": dict(
        name="水印消除", entry="remove", field="url",
        what="去水印 / 分享链解析，素材放 url（这个应用的入口就是 remove）"),
}
APP_ORDER = ["smart_clip", "nano_banana", "dressing_diffusion", "seedsvc", "grok_video",
             "lipsync", "wan", "happy_horse", "watermark_removal", "image_human",
             "seedance"]

# 价目表基线（GET /api/v1/pricing 2026-11-08 实测）。联网时以线上规则为准，
# 这里的值只在 --offline / 线上缺键时兜底，并在输出里标 source=baseline。
BASELINE = {
    "dressing_diffusion": dict(create=dict(kind="fixed", points=200),
                               remove=dict(kind="dynamic", markup=100)),
    "grok_video": dict(create=dict(kind="fixed", points=300),
                       remove=dict(kind="dynamic", markup=100)),
    "happy_horse": dict(create=dict(kind="fixed", points=650),
                        remove=dict(kind="dynamic", markup=100)),
    "image_human": dict(
        create=dict(kind="per_second", rates={"fast": 10, "standard": 15,
                                              "2k": 30, "4k": 60}, default="fast"),
        remove=dict(kind="dynamic", markup=100)),
    "lipsync": dict(create=dict(kind="dynamic", markup=200, minPoints=1),
                    remove=dict(kind="dynamic", markup=200, minPoints=1)),
    "nano_banana": dict(create=dict(kind="fixed", points=72),
                        remove=dict(kind="dynamic", markup=100)),
    "seedance": dict(create=dict(kind="fixed", points=11000),
                     remove=dict(kind="dynamic", markup=100)),
    "seedsvc": dict(create=dict(kind="fixed", points=220),
                    remove=dict(kind="dynamic", markup=100)),
    "smart_clip": dict(create=dict(kind="fixed", points=45),
                       remove=dict(kind="dynamic", markup=100)),
    "wan": dict(create=dict(kind="dynamic", markup=200, minPoints=1),
                remove=dict(kind="dynamic", markup=100)),
    "watermark_removal": dict(create=dict(kind="dynamic", markup=100),
                              remove=dict(kind="fixed", points=100)),
}

# seedance 素材库三件套：应用目录登记了，价目表没有专属规则
SEEDANCE_ASSETS = [
    dict(path=API_PREFIX + "/apps/seedance/createGroup", verb="createGroup",
         what="建素材分组", required="Name"),
    dict(path=API_PREFIX + "/apps/seedance/createAsset", verb="createAsset",
         what="把 URL 入库", required="URL / GroupId / AssetType"),
    dict(path=API_PREFIX + "/apps/seedance/deleteAsset", verb="deleteAsset",
         what="删素材", required="Id / GroupId"),
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


# ───────────────────────── HTTP ─────────────────────────
def http_json(method, url, key, body=None, timeout=120):
    """GET 遇到 5xx / 断连会退避重试 3 次；POST 只发一次（避免重复扣费）。"""
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    attempts = 3 if method == "GET" else 1
    last = None
    for i in range(attempts):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            if e.code >= 500 and i < attempts - 1:
                last = (e.code, txt)
                time.sleep(0.8 if i == 0 else 1.6)
                continue
            return e.code, txt
        except urllib.error.URLError as e:
            last = "连不上 %s：%s" % (url, e.reason)
        except Exception as e:                                   # noqa: BLE001
            last = "请求异常：%s: %s" % (type(e).__name__, e)
        if i < attempts - 1:
            time.sleep(0.8 if i == 0 else 1.6)
    if isinstance(last, tuple):
        return last
    raise Fail("call", last or "请求失败", EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=600):
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in (fields or {}).items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    for name, path in (files or []):
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
    if st and int(st) >= 500:
        return "网关 %s（临时故障，稍后重试）" % st
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code") not in (0, 1, None):
            return ("code=%s" % d.get("code"))[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


# ───────────────────────── 价格 ─────────────────────────
def path_create(app):
    return API_PREFIX + "/apps/%s/create" % app


def path_entry(app):
    return API_PREFIX + "/apps/%s/%s" % (app, APPS[app]["entry"])


def path_remove(app):
    return API_PREFIX + "/apps/%s/remove" % app


def rule_for(rules, path):
    """精确规则 → 应用通配 /api/v1/apps/<app>/* → 全局通配 *。返回 (rule, 命中键)。"""
    if not isinstance(rules, dict):
        return None, None
    if path in rules:
        return rules[path], path
    parts = path.split("/")
    if len(parts) > 5 and parts[3] == "apps":
        wild = "/".join(parts[:5] + ["*"])
        if wild in rules:
            return rules[wild], wild
    if "*" in rules:
        return rules["*"], "*"
    return None, None


def rule_shape(rule):
    """把一条 /pricing 规则翻成可计算的形状。"""
    if not isinstance(rule, dict):
        return dict(kind="none", note="价目表里没有这条规则")
    mode = rule.get("mode")
    cost = rule.get("cost")
    markup = float(rule.get("markupPercent") or 0)
    note = rule.get("note") or ""
    if mode == "flat":
        if cost is not None and float(cost) > 0:
            return dict(kind="fixed", points=float(cost),
                        minPoints=rule.get("minPoints"), markup=markup, note=note)
        if float(cost or 0) == 0 and markup > 0:
            return dict(kind="dynamic", markup=markup,
                        minPoints=rule.get("minPoints"), note=note)
        return dict(kind="free", points=0.0, markup=markup, note=note)
    if mode == "per_second":
        rate = rule.get("perSecond")
        rates = None
        mr = rule.get("modelRates")
        if isinstance(mr, dict) and mr:
            rates = {}
            for k, v in mr.items():
                rates[k] = (v.get("*") if isinstance(v, dict) else v)
            rate = rate if rate is not None else rates.get(rule.get("defaultModel") or "")
        return dict(kind="per_second", rate=rate, rates=rates,
                    default=rule.get("defaultModel"), minPoints=rule.get("minPoints"),
                    markup=markup, note=note)
    return dict(kind="other", mode=mode, markup=markup, note=note)


def estimate(shape, seconds=0, mode=None, views=0, count=1, app=None):
    """返回 dict(points / reserve / known / basis / unit)。

    points=None 表示动态计价：价目表不写死单价，只能事后看流水。
    reserve 是**预算预留**（动态时用规则 minPoints 或通配保底 50 点），不是报价。
    """
    kind = shape.get("kind")
    count = max(1, int(count or 1))
    if kind == "fixed":
        if app == "nano_banana" and views:
            pts = VIEWS_POINTS * int(views) * count
            return dict(points=float(pts), reserve=float(pts), known=True,
                        unit="点/次",
                        basis="%d 点/视角 × %d 视角 × %d 次（价目表 note 口径）"
                              % (VIEWS_POINTS, views, count))
        pts = float(shape["points"]) * count
        return dict(points=pts, reserve=pts, known=True, unit="点/次",
                    basis="固定 %s 点/次 × %d" % (fmt_pts(shape["points"]), count))
    if kind == "per_second":
        rate = shape.get("rate")
        label = "点/秒"
        if shape.get("rates"):
            use = mode or shape.get("default") or sorted(shape["rates"])[0]
            rate = shape["rates"].get(use) or rate
            label = "点/输入秒（mode=%s）" % use
        if rate is None:
            return dict(points=None, reserve=float(WILDCARD_MIN), known=False,
                        unit=label, basis="按秒计价但价目表没写费率")
        sec = max(1, int(seconds or 1))
        pts = float(rate) * sec * count
        minp = shape.get("minPoints")
        if minp is not None and pts < float(minp):
            return dict(points=float(minp), reserve=float(minp), known=True, unit=label,
                        basis="%s 点/秒 × %d 秒，不足保底 %s 点"
                              % (fmt_pts(rate), sec, fmt_pts(minp)))
        return dict(points=pts, reserve=pts, known=True, unit=label,
                    basis="%s %s × %d 秒 × %d 次" % (fmt_pts(rate), label, sec, count))
    if kind == "dynamic":
        markup = float(shape.get("markup") or 0)
        reserve = float(shape.get("minPoints") or WILDCARD_MIN)
        return dict(points=None, reserve=reserve, known=False, unit="动态",
                    basis="上游实际点数 × %.2f，价目表不写死单价"
                          % (1.0 + markup / 100.0))
    if kind == "free":
        return dict(points=0.0, reserve=0.0, known=True, unit="免费",
                    basis="规则 cost=0，不计费")
    return dict(points=None, reserve=float(WILDCARD_MIN), known=False, unit="未知",
                basis="这条规则不是 flat / per_second")


def shape_for(app, which, rules):
    """which = create / remove。返回 (shape, source, matchedPath)。"""
    path = path_create(app) if which == "create" else path_remove(app)
    if rules:
        rule, matched = rule_for(rules, path)
        sh = rule_shape(rule)
        if sh.get("kind") not in ("none", "other"):
            src = "pricing" if matched == path else "wildcard"
            return sh, src, matched
    base = dict(BASELINE[app][which])
    return base, "baseline", None


def fmt_pts(n):
    if n is None:
        return "-"
    try:
        f = float(n)
    except Exception:                                            # noqa: BLE001
        return "-"
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def pnum(v, dash="-"):
    return fmt_pts(v) if v is not None else dash


def yuan(points):
    try:
        return "%.2f" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                            # noqa: BLE001
        return "-"


# ── 显示宽度（中文算 2 列，表格才对得齐）─────────────────────────────────
def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def ms_text(ms):
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(float(ms) / 1000.0))
    except Exception:                                            # noqa: BLE001
        return "-"


def full_text(ms):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ms) / 1000.0))
    except Exception:                                            # noqa: BLE001
        return "-"


def fmt_size(n):
    try:
        n = float(n)
    except Exception:                                            # noqa: BLE001
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (int(n), unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "-"


def now_ms():
    return int(time.time() * 1000)


# ───────────────────────── 本地台账 ─────────────────────────
def ledger_load():
    if not os.path.isfile(LEDGER):
        return []
    try:
        with io.open(LEDGER, encoding="utf-8") as f:
            arr = json.load(f)
        return arr if isinstance(arr, list) else []
    except Exception:                                            # noqa: BLE001
        return []


def ledger_save(arr):
    try:
        if not os.path.isdir(VAULT_DIR):
            os.makedirs(VAULT_DIR)
        tmp = LEDGER + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-500:], ensure_ascii=False, indent=1))
        os.replace(tmp, LEDGER)
    except Exception as e:                                       # noqa: BLE001
        say("  本地台账写不进去（%s），本次结果仍然可用。" % e)


def find_entry(arr, sid):
    for e in arr:
        if e.get("id") == sid:
            return e
    return None


def is_expired(e, at=None):
    at = at if at is not None else now_ms()
    return float(e.get("expires") or 0) <= at


def hours_left(e, at=None):
    at = at if at is not None else now_ms()
    return (float(e.get("expires") or 0) - at) / 3600000.0


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def new_id(arr):
    used = {e.get("id") for e in arr}
    while True:
        sid = uuid.uuid4().hex[:8]
        if sid not in used:
            return sid


class Ctx(object):
    """一次运行内的共享缓存，同一个端点只拉一次。"""

    def __init__(self, key, host):
        self.key, self.host = key, host
        self._pricing = None
        self._apps = None
        self.requests = 0

    def pricing(self):
        if self._pricing is None:
            st, txt = http_json("GET", self.host + API_PREFIX + "/pricing",
                                self.key, timeout=40)
            self.requests += 1
            d = jloads(txt) or {}
            if st != 200 or not isinstance(d.get("pricing"), dict):
                raise Fail("call", "价目表拉取失败（HTTP %s）：%s"
                           % (st, err_text(st, txt)), EXIT_CALL)
            self._pricing = d
        return self._pricing

    def rules(self):
        return self.pricing().get("pricing") or {}

    def apps(self):
        if self._apps is None:
            st, txt = http_json("GET", self.host + API_PREFIX + "/apps",
                                self.key, timeout=40)
            self.requests += 1
            d = jloads(txt) or {}
            data = d.get("data")
            if st != 200 or not isinstance(data, list):
                raise Fail("call", "应用目录拉取失败（HTTP %s）：%s"
                           % (st, err_text(st, txt)), EXIT_CALL)
            self._apps = data
        return self._apps

    def actual(self, pages):
        """真实成交价：GET /api/v1/me/tasks 按 path 归集 actualPrice（免费）。"""
        agg = {}
        for pg in range(1, max(1, pages) + 1):
            st, txt = http_json("GET", self.host + API_PREFIX +
                                "/me/tasks?limit=2000&page=%d" % pg, self.key, timeout=40)
            self.requests += 1
            d = jloads(txt) or {}
            ts = d.get("tasks") or []
            if st != 200 or not ts:
                break
            for t in ts:
                p = t.get("path") or ""
                try:
                    v = float(t.get("actualPrice") or 0)
                except Exception:                                # noqa: BLE001
                    continue
                agg.setdefault(p, []).append(round(v, 2))
            if len(ts) < 20:
                break
        return agg


def app_registered(apps_catalog, app):
    """从 /api/v1/apps 目录看某个应用登记了哪些 api。"""
    for a in apps_catalog or []:
        if a.get("code") == app:
            return {(x.get("code") or "") for x in (a.get("apis") or [])}
    return set()


# ───────────────────────── 两道闸门 ─────────────────────────
def gate_confirm(a, est, what):
    """预算闸门 → 确认闸门。返回实际要预留的点数。"""
    reserve = est["reserve"] if not est["known"] else est["points"]
    if reserve is not None and float(reserve) > float(a.budget):
        raise Fail("budget",
                   "预计 %s 点超过 --budget %s 点（%s）。一个请求都没发。"
                   "调大 --budget 或改用更便宜的应用。"
                   % (fmt_pts(reserve), fmt_pts(a.budget), est["basis"]),
                   EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        if est["known"]:
            msg = "这会真实提交%s：预计 %s 点（%s 元）· %s。" % (
                what, fmt_pts(est["points"]), yuan(est["points"]), est["basis"])
        else:
            msg = "这会真实提交%s：按上游实际点数结算，价目表不写死单价（%s）。" \
                  "预算预留 %s 点。" % (what, est["basis"], fmt_pts(est["reserve"]))
        raise Fail("confirm", msg + " 确认请加 --yes。", EXIT_CONFIRM)
    return reserve


def gate_read(a, requests, what="本次"):
    """只读命令：0 点，但 --budget 0 仍然直接退 5（0 点预算 = 不授权任何调用）。"""
    if a.budget <= 0:
        raise Fail("budget", "--budget 是 %d 点（单位：点）。本组命令每个请求 0 点，"
                   "但 0 点预算等于不授权任何调用；给 1 点以上就放行。" % a.budget,
                   EXIT_BUDGET)
    if requests >= 30 and not a.yes and not a.dry_run:
        raise Fail("confirm", "%s要连发 %d 个只读 GET（花费 0 点，不会扣款）。"
                   "确认请加 --yes。" % (what, requests), EXIT_CONFIRM)


def plan(a, reqs, lines, note="干跑（一个请求都不发）"):
    out = {"ok": True, "dryRun": True, "requestCount": reqs,
           "requests": lines, "estimatedPoints": 0, "yuan": 0.0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print(note)
    print("  请求数：%d" % reqs)
    for ln in lines:
        print("  → %s" % ln)
    return 0


def split_multi(values):
    out = []
    for v in (values or []):
        out += [x.strip() for x in str(v).split(",") if x.strip()]
    return out


# ───────────────────────── upload ─────────────────────────
def collect_files(a):
    files = []
    for f in (a.file or []):
        if f:
            files.append(f)
    if a.dir:
        d = a.dir
        if not os.path.isdir(d):
            raise Fail("usage", "--dir 不是目录：%s" % d, EXIT_USAGE)
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                files.append(p)
    out, seen = [], set()
    for p in files:
        ap = os.path.abspath(p)
        if ap in seen:
            continue
        seen.add(ap)
        if not os.path.isfile(ap):
            raise Fail("usage", "文件不存在：%s" % p, EXIT_USAGE)
        size = os.path.getsize(ap)
        if size > MAX_UPLOAD_BYTES:
            raise Fail("usage", "%s 是 %s，超过单文件 512 MB 上限"
                       % (os.path.basename(ap), fmt_size(size)), EXIT_USAGE)
        out.append(ap)
    if not out:
        raise Fail("usage", "给 --file 或 --dir（要上传的素材路径）", EXIT_USAGE)
    return out


def cmd_upload(a, key, host):
    files = collect_files(a)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "endpoint": "POST " + UPLOAD_PATH,
               "count": len(files),
               "files": [{"file": p, "size": os.path.getsize(p)} for p in files],
               "estimatedPoints": 0, "yuan": 0.0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不扣费）")
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  价目表：%s 的规则是 cost=0，上传不计费" % UPLOAD_PATH)
        for p in files:
            print("  → %s（%s）" % (p, fmt_size(os.path.getsize(p))))
        return 0

    arr = ledger_load()
    items, failed = [], 0
    for idx, path in enumerate(files, 1):
        name = os.path.basename(path)
        size = os.path.getsize(path)
        digest = sha256_file(path)
        reuse = None
        if not a.force:
            for e in arr:
                if e.get("sha256") == digest and int(e.get("size") or -1) == size \
                        and not is_expired(e):
                    reuse = e
                    break
        if reuse is not None:
            items.append({"ok": True, "reused": True, "id": reuse.get("id"),
                          "file": path, "url": reuse.get("url"),
                          "expires": reuse.get("expires"),
                          "expiresText": reuse.get("expiresText")})
            say("  [%d/%d] %s 已在台账里且未过期，直接复用（0 点）"
                % (idx, len(files), name))
            continue
        say("  [%d/%d] 上传 %s（%s）…" % (idx, len(files), name, fmt_size(size)))
        t0 = time.time()
        st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
        dt = time.time() - t0
        d = jloads(txt) or {}
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        got = data.get("url")
        if d.get("code") != 1 or not got:
            failed += 1
            msg = err_text(st, txt)
            say("        失败（HTTP %s）：%s" % (st, msg))
            items.append({"ok": False, "file": path, "http": st, "error": msg})
            continue
        at = now_ms()
        exp = at + TTL_HOURS * 3600 * 1000
        rec = {
            "id": new_id(arr), "name": data.get("name") or name, "file": path,
            "size": data.get("size") or size, "sha256": digest,
            "url": got, "path": data.get("path"),
            "mime": data.get("mime_type"), "type": data.get("type"),
            "at": at, "atText": full_text(at),
            "expires": exp, "expiresText": full_text(exp),
            "ttlHours": TTL_HOURS,
            "tags": [str(t) for t in (a.tag or []) if str(t).strip()],
            "note": a.note or "", "bindings": [],
        }
        arr.append(rec)
        items.append({"ok": True, "reused": False, "id": rec["id"],
                      "file": path, "url": got, "size": rec["size"],
                      "type": rec["type"], "mime": rec["mime"],
                      "expires": exp, "expiresText": rec["expiresText"],
                      "elapsed": round(dt, 1)})
        say("        好了（%.1fs）" % dt)
    ledger_save(arr)

    out = {"ok": failed == 0, "count": len(items),
           "uploaded": len([x for x in items if x.get("ok") and not x.get("reused")]),
           "reused": len([x for x in items if x.get("reused")]),
           "failed": failed, "ttlHours": TTL_HOURS, "items": items,
           "estimatedPoints": 0, "yuan": 0.0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if failed == 0 else EXIT_CALL
    print()
    print("上传完成 · 成功 %d 个（新增 %d / 复用 %d）· 失败 %d 个 · 本轮 0 点"
          % (len(items) - failed, out["uploaded"], out["reused"], failed))
    for it in items:
        if it.get("ok"):
            print("  %s  %s" % (it["id"], it["url"]))
            print("       类型：%s · %s · %s" % (it.get("type") or "-",
                                               it.get("mime") or "-",
                                               fmt_size(it.get("size"))))
            print("       到期：%s（上传后最长 %d 小时，平台可提前回收）"
                  % (it["expiresText"], TTL_HOURS))
    print()
    print("下一步：先比价再登记 ——")
    print("  python3 scripts/run.py cost --apps smart_clip,wan,seedance")
    print("  python3 scripts/run.py bind --app smart_clip --id %s --param ... --yes"
          % (items[0]["id"] if items and items[0].get("id") else "<id>"))
    return 0 if failed == 0 else EXIT_CALL


# ───────────────────────── catalog ─────────────────────────
def cmd_catalog(a, key, host):
    only = split_multi(a.app)
    bad = [x for x in only if x not in APPS]
    if bad:
        raise Fail("usage", "未知应用：%s（可用：%s）"
                   % ("、".join(bad), "、".join(APP_ORDER)), EXIT_USAGE)
    order = only or APP_ORDER
    gate_read(a, 0 if a.offline else 2)
    rules, apps_catalog = {}, []
    if not a.offline:
        ctx = Ctx(key, host)
        rules = ctx.rules()
        apps_catalog = ctx.apps()
    rows = []
    for app in order:
        meta = APPS[app]
        csh, csrc, cmatch = shape_for(app, "create", rules)
        rsh, rsrc, _ = shape_for(app, "remove", rules)
        cest = estimate(csh, seconds=a.seconds, mode=a.mode, views=a.views, app=app)
        rest = estimate(rsh, seconds=a.seconds, mode=a.mode, app=app)
        reg = app_registered(apps_catalog, app)
        rows.append({
            "app": app, "name": meta["name"], "what": meta["what"],
            "createPath": path_create(app), "entryPath": path_entry(app),
            "entry": meta["entry"], "assetField": meta["field"],
            "assetHint": meta.get("hint"),
            "createKind": csh.get("kind"), "createSource": csrc,
            "createPoints": cest["points"], "createReserve": cest["reserve"],
            "createBasis": cest["basis"],
            "removePath": path_remove(app), "removeKind": rsh.get("kind"),
            "removeSource": rsrc, "removePoints": rest["points"],
            "removeReserve": rest["reserve"], "removeBasis": rest["basis"],
            "registeredCreate": "create" in reg,
            "registeredSubmit": "submit" in reg,
            "registeredRemove": "remove" in reg,
            "apis": sorted(reg),
        })
    out = {"ok": True, "count": len(rows), "apps": rows,
           "ttlHours": TTL_HOURS, "uploadFree": True,
           "seedanceAssets": [dict(p) for p in SEEDANCE_ASSETS],
           "estimatedPoints": 0, "yuan": 0.0,
           "note": "create/remove 单价取自 GET /api/v1/pricing；应用目录登记情况取自 "
                   "GET /api/v1/apps。本轮 0 点。"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("素材库管家 · 11 个应用的素材入口（价格单位：点，1 元 = 100 点）")
    print("=" * 98)
    print("  上传：POST %s 不计费（规则 cost=0）· 地址最长 %d 小时"
          % (UPLOAD_PATH, TTL_HOURS))
    print()
    for r in rows:
        print("  [%s] %s" % (r["app"], r["name"]))
        print("     用途    %s" % r["what"])
        ctext = ("%s 点" % fmt_pts(r["createPoints"])) if r["createPoints"] is not None \
            else "动态（预算预留 %s 点）" % fmt_pts(r["createReserve"])
        print("     create  %-46s %s" % (r["createPath"], ctext))
        print("             口径：%s%s" % (
            r["createBasis"],
            "" if r["createSource"] in ("pricing", "baseline")
            else "（命中应用通配规则）"))
        if r["createPoints"] is None:
            print("             动态计价：价目表不写死单价，实际按上游点数结算")
        rtext = ("%s 点" % fmt_pts(r["removePoints"])) if r["removePoints"] is not None \
            else "动态（预算预留 %s 点）" % fmt_pts(r["removeReserve"])
        print("     remove  %-46s %s%s"
              % (r["removePath"], rtext,
                 "" if r["registeredRemove"] else "  ← 应用目录未登记"))
        print("             口径：%s" % r["removeBasis"])
        if a.offline:
            print("     登记    -（--offline 没查应用目录）· 默认入口 %s" % r["entry"])
        else:
            print("     登记    该应用提供：%s" % ("、".join(r["apis"]) or "（目录里没有这个应用）"))
            print("             默认入口 %s（create=%s submit=%s remove=%s）"
                  % (r["entry"],
                     "有" if r["registeredCreate"] else "无",
                     "有" if r["registeredSubmit"] else "无",
                     "有" if r["registeredRemove"] else "无"))
        print("     素材字段 %s" % (r["assetField"] or ("需 --param：" + (r["assetHint"] or ""))))
        print()
    if "seedance" in order:
        print("  seedance 素材库三件套（应用目录登记、价目表没有专属规则）")
        for s in SEEDANCE_ASSETS:
            print("    %-44s %-12s 必填：%s" % (s["path"], s["what"], s["required"]))
        print("    按价目表字面，这三条命中 /api/v1/apps/seedance/* = 固定 11,000 点/次；")
        print("    其余未定价接口命中全局通配 *：上游点数 ×2，单笔保底 %d 点。"
              % WILDCARD_MIN)
        print()
    print("  两个反直觉的点：")
    print("    · remove 不等于免费：10 个应用是动态 ×2，watermark_removal 是 100 点/次的")
    print("      去水印主业务；本地清台账用 prune（免费），远端清理才用 release（计费）。")
    print("    · 价目表有 create 规则，不等于应用目录登记了 create：只有 happy_horse /")
    print("      wan / seedance 登记了 create，其余 create 是 submit 的同价别名。")
    print("  本轮 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── cost ─────────────────────────
def cmd_cost(a, key, host):
    only = split_multi(a.apps)
    bad = [x for x in only if x not in APPS]
    if bad:
        raise Fail("usage", "未知应用：%s（可用：%s）"
                   % ("、".join(bad), "、".join(APP_ORDER)), EXIT_USAGE)
    order = only or APP_ORDER
    reqs = 0 if a.offline else 1
    if a.live:
        reqs += max(1, a.pages)
    gate_read(a, reqs)
    if a.dry_run:
        lines = [] if a.offline else ["GET %s/pricing" % API_PREFIX]
        if a.live:
            lines += ["GET %s/me/tasks?limit=2000&page=%d" % (API_PREFIX, i)
                      for i in range(1, a.pages + 1)]
        return plan(a, reqs, lines, "干跑（不发请求）")

    rules, live = {}, {}
    if reqs:
        ctx = Ctx(key, host)
        if not a.offline:
            rules = ctx.rules()
        if a.live:
            live = ctx.actual(a.pages)

    rows = []
    for app in order:
        meta = APPS[app]
        csh, csrc, _ = shape_for(app, "create", rules)
        cest = estimate(csh, seconds=a.seconds, mode=a.mode, views=a.views,
                        count=a.count, app=app)
        rsh, rsrc, _ = shape_for(app, "remove", rules)
        rest = estimate(rsh, seconds=a.seconds, mode=a.mode, count=a.count, app=app)
        c_actual = live.get(path_create(app)) or live.get(path_entry(app)) or []
        r_actual = live.get(path_remove(app)) or []
        rows.append({
            "app": app, "name": meta["name"], "entry": meta["entry"],
            "entryPath": path_entry(app), "createPath": path_create(app),
            "createPoints": cest["points"], "createReserve": cest["reserve"],
            "createKnown": cest["known"], "createBasis": cest["basis"],
            "createSource": csrc,
            "removePath": path_remove(app), "removePoints": rest["points"],
            "removeReserve": rest["reserve"], "removeKnown": rest["known"],
            "removeBasis": rest["basis"], "removeSource": rsrc,
            "createActual": sorted(c_actual)[:20], "removeActual": sorted(r_actual)[:20],
            "createActualCount": len(c_actual), "removeActualCount": len(r_actual),
        })
    rows.sort(key=lambda r: (r["createPoints"] is None,
                             r["createPoints"] if r["createPoints"] is not None
                             else r["createReserve"]))
    total = sum(r["createPoints"] if r["createKnown"] else r["createReserve"]
                for r in rows)
    all_known = all(r["createKnown"] for r in rows)
    out = {"ok": True, "seconds": a.seconds, "mode": a.mode, "views": a.views,
           "count": a.count, "live": bool(a.live), "offline": bool(a.offline),
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "apps": rows,
           "totalPoints": round(total, 2) if all_known else None,
           "totalReserve": round(total, 2),
           "cheapest": rows[0]["app"] if rows else None,
           "estimatedPoints": 0, "yuan": 0.0,
           "note": "单价取自 GET /api/v1/pricing；动态项价目表不写死单价，"
                   "reserve 是预算预留不是报价；本轮 0 点。"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("先算钱 · 同一份素材投给不同应用（单位：点，1 元 = 100 点）")
    print("=" * 100)
    print("  条件：%d 秒 · mode=%s · 视角=%s · 次数=%d%s"
          % (a.seconds, a.mode, a.views or "-", a.count,
             " · 已带真实成交价" if a.live else ""))
    print()
    print("  %s %s %s %s %s %s" % (pad("--app", 20), pad("入口", 9),
                                   pad("create 价", 16, False), pad("元", 8, False),
                                   pad("remove 价", 14, False), "口径"))
    print("  " + "-" * 96)
    for r in rows:
        ctext = ("%s 点" % fmt_pts(r["createPoints"])) if r["createKnown"] \
            else "动态（预留 %s）" % fmt_pts(r["createReserve"])
        cy = yuan(r["createPoints"]) if r["createKnown"] else "-"
        rtext = ("%s 点" % fmt_pts(r["removePoints"])) if r["removeKnown"] \
            else "动态（预留 %s）" % fmt_pts(r["removeReserve"])
        print("  %s %s %s %s %s %s"
              % (pad(r["app"], 20), pad(r["entry"], 9), pad(ctext, 16, False),
                 pad(cy, 8, False), pad(rtext, 14, False), r["createBasis"][:36]))
    print()
    print("  从低到高（create 价）：")
    for i, r in enumerate(rows, 1):
        ctext = ("%s 点（%s 元）" % (fmt_pts(r["createPoints"]), yuan(r["createPoints"]))) \
            if r["createKnown"] else "动态，预算预留 %s 点" % fmt_pts(r["createReserve"])
        actual = ""
        if a.live:
            if r["createActualCount"]:
                s = r["createActual"]
                span = fmt_pts(s[0]) if s[0] == s[-1] else "%s - %s" % (
                    fmt_pts(s[0]), fmt_pts(s[-1]))
                actual = "  实测 %s 点 × %d 笔" % (span, r["createActualCount"])
            else:
                actual = "  实测 无历史成交"
        print("    %2d. %-18s %-30s%s" % (i, r["app"], ctext, actual))
    print()
    if only:
        print("  你选中 %d 个应用，合计 create 价 %s 点（%s 元）%s"
              % (len(rows), fmt_pts(total), yuan(total),
                 "" if all_known else "，其中动态项按预算预留计"))
    print("  口径：动态 = 上游实际点数 × 倍率，价目表不写死单价；实际以账单为准。")
    print("  本轮 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── ls / tag / prune ─────────────────────────
def cmd_ls(a, key, host):
    allarr = ledger_load()
    tags = [t for t in (a.tag or []) if t]
    arr = allarr
    if tags:
        arr = [e for e in arr if any(t in (e.get("tags") or []) for t in tags)]
    if not a.all:
        arr = [e for e in arr if not is_expired(e)]
    arr = sorted(arr, key=lambda e: -float(e.get("at") or 0))
    shown = arr[:a.limit] if a.limit else arr
    entries = []
    for e in shown:
        hl = hours_left(e)
        entries.append({
            "id": e.get("id"), "name": e.get("name"), "file": e.get("file"),
            "size": e.get("size"), "url": e.get("url"),
            "atText": e.get("atText"), "expiresText": e.get("expiresText"),
            "hoursLeft": round(hl, 2), "expired": hl <= 0,
            "tags": e.get("tags") or [], "note": e.get("note") or "",
            "bindings": e.get("bindings") or [],
        })
    expired_all = len([1 for e in allarr if is_expired(e)])
    out = {"ok": True, "count": len(entries), "totalInLedger": len(allarr),
           "expiredTotal": expired_all, "filterTags": tags,
           "includeExpired": bool(a.all), "ttlHours": TTL_HOURS, "entries": entries,
           "estimatedPoints": 0, "yuan": 0.0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("本地台账 · 显示 %d 条 / 共 %d 条（过期 %d 条）"
          % (len(entries), len(allarr), expired_all))
    print("=" * 100)
    if not entries:
        print("  台账还是空的。先上传：python3 scripts/run.py upload --file 素材.png")
        return 0
    print("  %s %s %s %s %s %s" % (pad("id", 10), pad("文件", 22), pad("大小", 10),
                                   pad("上传", 12), pad("剩余", 14), "标签 / 绑定"))
    print("  " + "-" * 100)
    for e in entries:
        left = "已过期" if e["expired"] else "%.1f 小时" % e["hoursLeft"]
        extra = ",".join(e["tags"]) or "-"
        if e["bindings"]:
            extra += " · " + ",".join(sorted({b.get("app") or "" for b in e["bindings"]}))
        print("  %s %s %s %s %s %s"
              % (pad(e["id"], 10), pad((e["name"] or "")[:21], 22),
                 pad(fmt_size(e["size"]), 10),
                 pad((e["atText"] or "-")[5:16], 12),
                 pad(left, 14), extra))
    print()
    soon = [e for e in entries if not e["expired"] and e["hoursLeft"] <= 6]
    if soon:
        print("  提醒：%d 条素材 6 小时内到期，到期前重传或转存：%s"
              % (len(soon), "、".join(e["id"] for e in soon)))
    if expired_all:
        print("  过期：%d 条的地址已不在有效期内，bind 会拒绝它们；"
              "python3 scripts/run.py prune 清掉本地记录" % expired_all)
    print("  上传地址最长 %d 小时，平台可提前回收；长期保存请下载转存。" % TTL_HOURS)
    return 0


def cmd_tag(a, key, host):
    ids = split_multi(a.id)
    if not ids:
        raise Fail("usage", "给 --id（台账里的 id，可多个，逗号分隔）", EXIT_USAGE)
    arr = ledger_load()
    hit, miss = [], []
    for sid in ids:
        e = find_entry(arr, sid)
        if e is None:
            miss.append(sid)
            continue
        if a.clear:
            e["tags"] = []
        for t in (a.tag or []):
            t = str(t).strip()
            if not t:
                continue
            tags = e.setdefault("tags", [])
            if t not in tags:
                tags.append(t)
        if a.note is not None:
            e["note"] = a.note
        hit.append({"id": sid, "name": e.get("name"), "tags": e.get("tags") or [],
                    "note": e.get("note") or ""})
    if hit:
        ledger_save(arr)
    if a.json:
        out = {"ok": not miss, "updated": hit, "missing": miss, "estimatedPoints": 0}
        if miss and not hit:
            print(json.dumps({"ok": False, "exit": EXIT_USAGE,
                              "error": {"kind": "usage",
                                        "message": "找不到这些 id：%s" % "、".join(miss)}},
                             ensure_ascii=False))
            return EXIT_USAGE
        print(json.dumps(out, ensure_ascii=False))
        return 0 if not miss else EXIT_USAGE
    for h in hit:
        print("  %s %s → 标签 %s%s" % (h["id"], h["name"] or "",
                                       ",".join(h["tags"]) or "-",
                                       (" · 备注 " + h["note"]) if h["note"] else ""))
    if miss:
        if not hit:
            raise Fail("usage", "找不到这些 id：%s" % "、".join(miss), EXIT_USAGE)
        say("已更新 %d 条；找不到这些 id：%s" % (len(hit), "、".join(miss)))
        return EXIT_USAGE
    return 0


def cmd_prune(a, key, host):
    arr = ledger_load()
    at = now_ms()
    older = None
    if a.older_than is not None:
        older = at - float(a.older_than) * 3600 * 1000
    keep, drop = [], []
    for e in arr:
        expired = is_expired(e, at)
        too_old = older is not None and float(e.get("at") or 0) <= older
        if expired or too_old:
            drop.append(e)
        else:
            keep.append(e)
    out = {"ok": True, "removed": len(drop), "kept": len(keep),
           "dryRun": bool(a.dry_run),
           "removedIds": [e.get("id") for e in drop],
           "estimatedPoints": 0, "yuan": 0.0,
           "note": "只清本地台账，不调用任何远端接口（remote remove 本身计费）。"}
    if a.dry_run:
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不改台账）")
        print("  将清掉 %d 条，保留 %d 条" % (len(drop), len(keep)))
        for e in drop:
            print("  → %s %s（%s）" % (e.get("id"), e.get("name"),
                                       "已过期" if is_expired(e, at) else "超期"))
        return 0
    if drop:
        ledger_save(keep)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("台账清理完成：清掉 %d 条，保留 %d 条（本轮 0 点）" % (len(drop), len(keep)))
    for e in drop:
        print("  - %s %s" % (e.get("id"), e.get("name")))
    print("  只动本地记录；远端清理要用 release（计费，见 catalog 单价）。")
    return 0


# ───────────────────────── bind / release ─────────────────────────
def parse_params(pairs):
    body = {}
    for kv in (pairs or []):
        if "=" not in kv:
            raise Fail("usage", "--param 要写成 key=value，收到：%s" % kv, EXIT_USAGE)
        k, v = kv.split("=", 1)
        k = k.strip()
        if not k:
            raise Fail("usage", "--param 的 key 不能为空：%s" % kv, EXIT_USAGE)
        try:
            body[k] = json.loads(v)
        except Exception:                                        # noqa: BLE001
            body[k] = v
    return body


def load_body(a):
    if not a.body:
        return {}
    raw = a.body
    if raw.startswith("@"):
        p = raw[1:]
        if not os.path.isfile(p):
            raise Fail("usage", "--body 文件不存在：%s" % p, EXIT_USAGE)
        with io.open(p, encoding="utf-8") as f:
            raw = f.read()
    d = jloads(raw)
    if not isinstance(d, dict):
        raise Fail("usage", "--body 要是 JSON 对象（或 @文件路径）", EXIT_USAGE)
    return d


def price_line(est):
    if est["known"]:
        return "%s 点（%s 元）" % (fmt_pts(est["points"]), yuan(est["points"]))
    return "动态，预算预留 %s 点" % fmt_pts(est["reserve"])


def cmd_bind(a, key, host):
    app = a.app
    meta = APPS[app]
    arr = ledger_load()
    entry = None
    url = (a.url or "").strip() or None
    if a.id:
        sid = a.id.strip()
        entry = find_entry(arr, sid)
        if entry is None:
            raise Fail("usage", "台账里没有 id=%s（先 python3 scripts/run.py ls）"
                       % sid, EXIT_USAGE)
        if is_expired(entry):
            raise Fail("usage",
                       "素材 %s 的地址已过期（上传后最长 %d 小时，到期 %s）。"
                       "地址过期后上游拉不到文件，先重新 upload 再 bind。"
                       % (sid, TTL_HOURS, entry.get("expiresText")), EXIT_USAGE)
        url = entry.get("url")
    if not url:
        raise Fail("usage", "给 --id（台账里的素材）或 --url（已有地址）", EXIT_USAGE)
    if not re.match(r"^https?://", url, re.I):
        raise Fail("usage", "素材地址要以 http:// 或 https:// 开头", EXIT_USAGE)

    body = load_body(a)
    body.update(parse_params(a.param))
    field = a.asset_field if a.asset_field is not None else meta["field"]
    if field:
        body.setdefault(field, url)
    elif url not in json.dumps(body, ensure_ascii=False):
        raise Fail("usage",
                   "%s 的素材要放进数组 / 对象字段，不能自动注入，免得白扣一次钱。"
                   "用 --param 明确给：%s" % (app, meta.get("hint") or "--param"),
                   EXIT_USAGE)

    kind = a.entry
    if kind == "auto":
        kind = meta["entry"]
    rules, reg = {}, set()
    if not a.offline:
        ctx = Ctx(key, host)
        rules = ctx.rules()
        reg = app_registered(ctx.apps(), app)
        if reg and kind not in reg:
            raise Fail("usage",
                       "%s 在应用目录里没有 %s 这个接口。它有：%s。用 --entry 指定其中一个。"
                       % (app, kind, "、".join(sorted(reg)) or "无"), EXIT_USAGE)
    path = API_PREFIX + "/apps/%s/%s" % (app, kind)
    full = host + path
    rule, matched = rule_for(rules, path) if rules else (None, None)
    shape = rule_shape(rule)
    if shape.get("kind") in ("none", "other"):
        shape = dict(BASELINE[app]["create"])
        source = "baseline"
    else:
        source = "pricing" if matched == path else "wildcard"
    est = estimate(shape, seconds=a.seconds, mode=a.mode, views=a.views, app=app)
    reserve = gate_confirm(a, est, "素材登记")

    req = {"url": path, "method": "POST", "body": body,
           "estimatedPoints": est["points"], "reservePoints": reserve,
           "known": est["known"], "basis": est["basis"], "source": source,
           "entry": kind, "app": app, "assetId": a.id, "assetUrl": url}
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "request": req, "estimatedPoints": 0,
               "yuan": 0.0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % path)
        print("  素材：%s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  价格：%s（%s，source=%s）" % (price_line(est), est["basis"], source))
        return 0

    say("正在提交 %s（%s）…" % (app, meta["name"]))
    t0 = time.time()
    st, txt = http_json("POST", full, key, body, timeout=a.timeout)
    dt = time.time() - t0
    parsed = jloads(txt) or {}
    code = parsed.get("code") if isinstance(parsed, dict) else None
    if st not in (200, 201) or code == 0:
        raise Fail("call", "提交失败（HTTP %s）：%s\n  先 --dry-run 看请求体，再对照该应用"
                   "文档确认字段名（素材字段当前是 %s）"
                   % (st, err_text(st, txt), field or "由 --param 给出"), EXIT_CALL)
    d = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
    task_id = (d.get("task_id") or d.get("taskId") or d.get("id")
               or d.get("TaskId") or d.get("RequestId"))
    status = d.get("status")
    if entry is not None:
        b = entry.setdefault("bindings", [])
        b.append({"app": app, "path": path, "taskId": task_id, "status": status,
                  "at": now_ms(), "atText": full_text(now_ms())})
        ledger_save(arr)
    out = {"ok": True, "app": app, "entry": kind, "path": path, "taskId": task_id,
           "status": status, "assetId": a.id, "assetUrl": url,
           "estimatedPoints": est["points"], "reservePoints": reserve,
           "known": est["known"], "basis": est["basis"], "source": source,
           "elapsed": round(dt, 1), "raw": d}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  应用：%s（%s）· 入口 %s" % (app, meta["name"], kind))
    print("  任务：%s   状态：%s" % (task_id or "-", status or "-"))
    if a.id:
        print("  素材：%s  %s" % (a.id, url))
    if est["known"]:
        print("  预冻结约 %s 点（%s 元）· %s" % (fmt_pts(est["points"]),
                                                 yuan(est["points"]), est["basis"]))
    else:
        print("  计费：%s（预算预留 %s 点，实际以账单为准）"
              % (est["basis"], fmt_pts(reserve)))
    if task_id:
        print()
        print("  查进度（免费）：GET %s/tasks/%s" % (API_PREFIX, task_id))
    if a.id:
        print("  台账已记下这次绑定，ls 里能看到它属于哪个应用。")
    return 0


def cmd_release(a, key, host):
    app = a.app
    meta = APPS[app]
    body = load_body(a)
    body.update(parse_params(a.param))
    path = path_remove(app)
    full = host + path

    ctx = None
    rules, reg = {}, set()
    if not a.offline:
        ctx = Ctx(key, host)
        rules = ctx.rules()
        reg = app_registered(ctx.apps(), app)
    rule, matched = rule_for(rules, path) if rules else (None, None)
    shape = rule_shape(rule)
    if shape.get("kind") in ("none", "other"):
        shape = dict(BASELINE[app]["remove"])
        source = "baseline"
    else:
        source = "pricing" if matched == path else "wildcard"
    est = estimate(shape, seconds=a.seconds, mode=a.mode, app=app)
    reserve = gate_confirm(a, est, "远端清理")

    if a.dry_run:
        out = {"ok": True, "dryRun": True,
               "request": {"url": path, "method": "POST", "body": body},
               "estimatedPoints": 0, "yuan": 0.0,
               "registered": ("remove" in reg) if not a.offline else None}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s" % path)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  价格：%s（%s，source=%s）" % (price_line(est), est["basis"], source))
        print("  提示：remove 不是免费动作 —— 10 个应用是动态 ×2，"
              "watermark_removal 是 100 点/次。")
        if not a.offline and "remove" not in reg:
            print("  并且：%s 的 remove 在应用目录里没有登记，路由是否可通未验证。" % app)
        return 0

    say("正在提交 %s 的 remove（%s）…" % (app, meta["name"]))
    t0 = time.time()
    st, txt = http_json("POST", full, key, body, timeout=a.timeout)
    dt = time.time() - t0
    if st not in (200, 201):
        raise Fail("call", "清理失败（HTTP %s）：%s\n  这个应用的 remove 在应用目录里%s登记，"
                   "路由是否可用未验证（本轮 0 点不探）。"
                   % (st, err_text(st, txt),
                      "" if ("remove" in reg or a.offline) else "没有"), EXIT_CALL)
    d = jloads(txt) or {}
    out = {"ok": True, "app": app, "path": path, "status": d.get("status"),
           "estimatedPoints": est["points"], "reservePoints": reserve,
           "known": est["known"], "basis": est["basis"], "source": source,
           "elapsed": round(dt, 1), "raw": d}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  应用：%s · 路径 %s" % (app, path))
    if est["known"]:
        print("  花费约 %s 点（%s 元）· %s" % (fmt_pts(est["points"]),
                                              yuan(est["points"]), est["basis"]))
    else:
        print("  计费：%s（预算预留 %s 点，实际以账单为准）"
              % (est["basis"], fmt_pts(reserve)))
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    gate_read(a, 10)
    if a.dry_run:
        return plan(a, 10, [
            "GET /user/balance",
            "GET %s/pricing" % API_PREFIX,
            "GET %s/apps" % API_PREFIX,
            "POST %s/upload（不带 file）" % API_PREFIX,
            "GET %s/tasks/probe-no-such-task" % API_PREFIX,
            "GET %s/me/tasks?limit=2000&page=1" % API_PREFIX,
            "GET /user/balance/logs?limit=1",
        ], "干跑（不发请求）")

    ctx = Ctx(key, host)
    checks = []

    # 1) Key + 余额
    try:
        st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
        ctx.requests += 1
        d = jloads(txt) or {}
        ok = st == 200 and ("available_points" in d or "points" in d)
        if ok:
            detail = "HTTP %s · 可用 %s 点 · 冻结 %s 点 · 1 元 = %s 点" % (
                st, fmt_pts(d.get("available_points") or d.get("points") or 0),
                fmt_pts(d.get("frozen") or 0), d.get("rate") or POINTS_PER_YUAN)
        else:
            detail = "HTTP %s · %s" % (st, err_text(st, txt))
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("Key + 余额 GET /user/balance", ok, detail))

    # 2) 价目表 + 22 条 create/remove 规则
    try:
        d = ctx.pricing()
        rules = d.get("pricing") or {}
        missing = []
        for app in APP_ORDER:
            for p in (path_create(app), path_remove(app)):
                if p not in rules:
                    missing.append(p.replace(API_PREFIX, "", 1))
        wild = rules.get("*") or {}
        ok = len(rules) >= 100 and not missing
        detail = "%d 条规则 · 22 条 create/remove %s · 通配保底 %s 点" % (
            len(rules), "全在" if not missing else "缺 %d 条" % len(missing),
            fmt_pts(wild.get("minPoints")))
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("价目表 GET /api/v1/pricing", ok, detail))

    # 3) 应用目录 + 11 个应用在架
    try:
        apps = ctx.apps()
        present = {x.get("code") for x in apps}
        miss = [x for x in APP_ORDER if x not in present]
        ok = len(apps) >= 20 and not miss
        detail = "%d 个应用 · 11 个目标应用%s" % (
            len(apps), "全在" if not miss else "缺 " + "、".join(miss))
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("应用目录 GET /api/v1/apps", ok, detail))

    # 4) 上传不计费（规则 cost=0）
    try:
        rule = (ctx.rules() or {}).get(UPLOAD_PATH) or {}
        ok = rule.get("cost") == 0 and rule.get("markupPercent") == 0
        detail = "规则 mode=%s cost=%s · %s" % (
            rule.get("mode"), rule.get("cost"),
            "不计费" if ok else (rule.get("note") or "价目表里没这条规则")[:44])
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("上传不计费（/pricing 里 /upload cost=0）", ok, detail))

    # 5) 上传接口：不带 file → 停在参数校验，不落文件
    try:
        st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
        ctx.requests += 1
        d = jloads(txt) or {}
        ok = st == 200 and d.get("code") == 0
        detail = "HTTP %s · code=%s · %s" % (
            st, d.get("code"),
            ((d.get("msg") or "") if ok else err_text(st, txt))[:40])
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("上传接口 POST /api/v1/upload（缺 file 停在参数校验）", ok, detail))

    # 6) 通用任务查询（假 id → 任务不存在，不扣费）
    try:
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task",
                            key, timeout=40)
        ctx.requests += 1
        d = jloads(txt) or {}
        ok = st == 200 and d.get("code") == 0
        detail = "HTTP %s · code=%s · %s" % (st, d.get("code"), (d.get("msg") or "")[:36])
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("任务查询 GET /api/v1/tasks/<id>（免费）", ok, detail))

    # 7) 我的任务：真实成交价的来源
    try:
        st, txt = http_json("GET", host + API_PREFIX + "/me/tasks?limit=2000&page=1",
                            key, timeout=40)
        ctx.requests += 1
        d = jloads(txt) or {}
        ok = st == 200 and isinstance(d.get("tasks"), list)
        detail = "台账 %s 条 · 本页 %d 条" % (d.get("total"), len(d.get("tasks") or []))
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("我的任务 GET /api/v1/me/tasks（真实成交价来源）", ok, detail))

    # 8) 流水：用来验「本轮到底扣没扣」
    try:
        st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
        ctx.requests += 1
        d = jloads(txt) or {}
        ok = st == 200 and isinstance(d.get("logs"), list)
        detail = "共 %s 条流水 · balanceMoving %s" % (
            fmt_pts(d.get("total")), fmt_pts(d.get("balanceMoving")))
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("流水 GET /user/balance/logs（验本轮 0 点）", ok, detail))

    # 9) create/remove 登记情况（只读目录，不发 POST）
    try:
        apps = ctx.apps()
        c = sum(1 for x in APP_ORDER if "create" in app_registered(apps, x))
        r = sum(1 for x in APP_ORDER if "remove" in app_registered(apps, x))
        ok = True
        detail = "目录登记 create 的 %d 个 / remove 的 %d 个（其余 create 是 submit 同价别名）" \
                 % (c, r)
    except Fail as e:
        ok, detail = False, e.message[:80]
    checks.append(("create/remove 登记核查（只读目录，不发 POST）", ok, detail))

    out = {"ok": all(x[1] for x in checks), "requests": ctx.requests,
           "estimatedPoints": 0, "yuan": 0.0, "ttlHours": TTL_HOURS,
           "writeRequests": 1,
           "writeNote": "唯一的 POST 是 /api/v1/upload 不带 file（参数校验层拦下，"
                        "不落文件、不计费）；create/remove 一律没探，避免 reserve_sync 冻结点数。",
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE

    print("自检（只读 GET + 1 次缺参上传探针；不建任务、不冻结、0 点）")
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 52), d))
    print()
    print("  端点：GET /pricing · GET /apps · POST /upload（缺 file）· GET /tasks/<id>")
    print("        GET /me/tasks · GET /user/balance · GET /user/balance/logs")
    print("  未探：22 条 create/remove —— 应用层提交会先 reserve_sync 冻结点数，")
    print("        本轮只用「价目表规则 + 应用目录登记」证明端点存在。")
    print("  上传地址最长 %d 小时；上传本身 0 点。" % TTL_HOURS)
    print("  本轮花费 0 点。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 素材库管家：上传 0 点，11 个应用的素材入口一张表看清",
        epilog="端点：POST %s/api/v1/upload（免费）· GET %s/api/v1/pricing · "
               "GET %s/api/v1/apps · GET %s/api/v1/me/tasks · "
               "POST %s/api/v1/apps/<app>/create|submit|remove（计费）"
               % ((DEFAULT_HOST,) * 5),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 50 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("upload", help="批量上传本地素材，写本地台账（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", action="append", help="素材路径，可重复给多个")
    p.add_argument("--dir", help="上传这个目录下的所有文件")
    p.add_argument("--tag", action="append", help="给这批素材打标签，可重复")
    p.add_argument("--note", help="备注")
    p.add_argument("--force", action="store_true",
                   help="同一文件已在台账里也重新上传（默认直接复用未过期的地址）")
    p.add_argument("--timeout", type=int, default=600, help="单文件上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("catalog", help="11 个应用的 create/remove 两条路 + 单价（免费）",
                       allow_abbrev=False)
    p.add_argument("--app", action="append", help="只看这些应用（逗号分隔，可重复）")
    p.add_argument("--seconds", type=int, default=10, help="按秒计价的应用按多少秒估（默认 10）")
    p.add_argument("--mode", default="fast", help="image_human 档位 fast/standard/2k/4k")
    p.add_argument("--views", type=int, default=0, help="nano_banana 视角数（>0 按 25 点/视角）")
    p.add_argument("--offline", action="store_true", help="不联网，用内置基线价")
    p.add_argument("--yes", action="store_true", help="确认（本命令 0 点）")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：同一素材投多个应用，逐个报价（免费）",
                       allow_abbrev=False)
    p.add_argument("--apps", action="append", help="要横评的应用（逗号分隔，可重复）")
    p.add_argument("--seconds", type=int, default=10, help="按秒计价的应用按多少秒估（默认 10）")
    p.add_argument("--mode", default="fast", help="image_human 档位 fast/standard/2k/4k")
    p.add_argument("--views", type=int, default=0, help="nano_banana 视角数")
    p.add_argument("--count", type=int, default=1, help="跑几次（默认 1）")
    p.add_argument("--live", action="store_true",
                   help="读 /api/v1/me/tasks 的真实成交价（免费）")
    p.add_argument("--pages", type=int, default=5, help="--live 时翻几页台账（默认 5）")
    p.add_argument("--offline", action="store_true", help="不联网，用内置基线价")
    p.add_argument("--yes", action="store_true", help="确认大批量只读扫描")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不发")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("ls", help="本地台账：剩余有效期 / 标签 / 绑定（免费，不联网）",
                       allow_abbrev=False)
    p.add_argument("--tag", action="append", help="只看这些标签")
    p.add_argument("--all", action="store_true", help="连已过期的也列出来")
    p.add_argument("--limit", type=int, default=30, help="最多列几条（默认 30，0 = 全部）")
    p.set_defaults(fn=cmd_ls)

    p = sub.add_parser("tag", help="给台账条目打标签 / 写备注（免费，不联网）",
                       allow_abbrev=False)
    p.add_argument("--id", action="append", help="台账 id（逗号分隔，可重复）")
    p.add_argument("--tag", action="append", help="要加的标签，可重复")
    p.add_argument("--note", help="备注（覆盖原备注）")
    p.add_argument("--clear", action="store_true", help="先清空原有标签")
    p.set_defaults(fn=cmd_tag)

    p = sub.add_parser("prune", help="清掉过期 / 超期的台账条目（免费，不联网）",
                       allow_abbrev=False)
    p.add_argument("--older-than", type=float, default=None,
                   help="上传时间超过多少小时也清掉")
    p.add_argument("--dry-run", action="store_true", help="只说要清哪几条，不改台账")
    p.set_defaults(fn=cmd_prune)

    p = sub.add_parser("bind", help="把素材登记进某个应用（计费，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--app", choices=APP_ORDER, required=True, help="目标应用，见 catalog")
    p.add_argument("--id", help="台账里的素材 id（bind 前会检查是否过期）")
    p.add_argument("--url", help="直接给一个素材地址（替代 --id）")
    p.add_argument("--body", help="请求体 JSON（或 @文件路径）；--param 会覆盖它")
    p.add_argument("--param", action="append", help="请求体参数 key=value，可重复")
    p.add_argument("--asset-field", default=None,
                   help="素材 URL 落在哪个字段（默认按应用，见 catalog）")
    p.add_argument("--entry", default="auto",
                   help="打哪个接口（默认 auto：用该应用登记的素材入口，见 catalog）")
    p.add_argument("--seconds", type=int, default=10, help="按秒计价的应用按多少秒估（默认 10）")
    p.add_argument("--mode", default="fast", help="image_human 档位 fast/standard/2k/4k")
    p.add_argument("--views", type=int, default=0, help="nano_banana 视角数")
    p.add_argument("--offline", action="store_true", help="不拉价目表，用内置基线价")
    p.add_argument("--timeout", type=int, default=120, help="提交超时秒数（默认 120）")
    p.add_argument("--yes", action="store_true", help="确认真实提交并冻结点数")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_bind)

    p = sub.add_parser("release", help="从应用清理素材（计费，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--app", choices=APP_ORDER, required=True, help="目标应用，见 catalog")
    p.add_argument("--body", help="请求体 JSON（或 @文件路径）")
    p.add_argument("--param", action="append", help="请求体参数 key=value，可重复")
    p.add_argument("--seconds", type=int, default=10, help="按秒计价时按多少秒估")
    p.add_argument("--mode", default="fast", help="image_human 档位")
    p.add_argument("--offline", action="store_true", help="不拉价目表，用内置基线价")
    p.add_argument("--timeout", type=int, default=120, help="超时秒数（默认 120）")
    p.add_argument("--yes", action="store_true", help="确认真实提交")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_release)

    p = sub.add_parser("doctor", help="自检 9 个只读端点 + 上传探针（免费，不扣费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=60, help="探针超时秒数（默认 60）")
    p.add_argument("--yes", action="store_true", help="确认")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不发")
    p.set_defaults(fn=cmd_doctor)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


# 不需要 Key 的子命令（纯本地台账）
NO_KEY_OK = ("cmd_ls", "cmd_tag", "cmd_prune")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    # 子命令上重复定义的全局选项 default=SUPPRESS，没写就不会覆盖父级的值
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("yes", False), ("dry_run", False), ("offline", False),
                       ("seconds", 10), ("mode", "fast"), ("views", 0),
                       ("count", 1), ("pages", 5), ("timeout", 120),
                       ("limit", 30), ("all", False), ("live", False),
                       ("app", None), ("apps", None), ("param", None), ("body", None),
                       ("id", None), ("url", None), ("tag", None), ("note", None),
                       ("force", False), ("clear", False), ("older_than", None),
                       ("entry", "auto"), ("asset_field", None), ("file", None),
                       ("dir", None)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    fn_name = getattr(a.fn, "__name__", "")
    try:
        key, host = load_conf(a.key, a.host)
        if not key and fn_name not in NO_KEY_OK:
            if not (fn_name in ("cmd_catalog", "cmd_cost") and a.offline):
                raise Fail("usage",
                           "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                           "`python3 scripts/a7w.py login --key …`。\n"
                           "注册领 Key：https://api.a7w.cn/", EXIT_USAGE)
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
