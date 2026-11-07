#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 带货素材侦察（sanjianke-ecom-spy）

从抖音 / 小红书找到爆款，拆出结构，给出仿写与出图方案。
8 个接口全部走 api.a7w.cn 的应用层 `watermark_removal`（水印消除 应用），
**同步返回**（call_type=1，没有 task_id，不用轮询）。

## 权威规格（2026-11-07 只读核对）

  接口根    https://api.a7w.cn/api/v1/apps/watermark_removal/<接口code>
  方法      POST，JSON body
  返回      {"code":1,"msg":"success","data":{...}}；业务数据在 result.data
  名单      GET /api/v1/apps 实测该应用 8 个接口，本包全接

## 价格（GET /api/v1/pricing 实测原文）

  "/api/v1/apps/watermark_removal/*":
      {"mode":"flat","cost":100,"markupPercent":0,
       "note":"去水印/分享链解析：固定 100 点/次（上游按请求 20 点，失败亦计）"}

  也就是：**8 个接口一律 100 点/次 = 1 元/次，与条数、时长、返回条数都无关。**
  上游侧成本 20 点/次 —— 对外价是上游的 5 倍，这个倍数写在规则里，不是估算。

## 两道闸门

  `--budget` 单位是「点」（1 元 = 100 点）；`--yes` 是第二道。
  缺 `--yes` → exit 4 并告诉你这次要花多少点；
  预计点数 > `--budget` → exit 5，**一个请求都不发**。

## 探针纪律（本包专属）

  `doctor` **只发只读 GET**，一次 POST 都不发。原因写在价格规则里：
  「失败亦计」—— 参数不全被拦下也照样按次计。所以本包不做 POST 探针，
  端点存在性用「GET /api/v1/apps 的接口名单」来证明，一样硬。

## 子命令（免费）

  catalog    8 个接口 + 必填项 + 单价（本地表）
  cost       先算钱：单次 / 组合 / 按预算能跑几次
  doctor     只读自检：Key / 应用 / 8 个接口 / 价目 / 余额 / 流水（0 点）
  rank       把快照按热度排序，出爆款榜
  breakdown  拆结构：标题公式 / 钩子 / 时长 / 节奏
  clone      仿写：3 条标题 + 3 个口播钩子 + 分镜骨架
  cover      出图方案：3 条封面 prompt + 该走哪条出图线 + 实际单价
  log        本地台账

## 子命令（100 点/次）

  hunt            搜索 + 当场拆结构（1 次调用办完整条链）
  dy-search       抖音搜索
  dy-video        抖音视频详情
  dy-user         抖音用户作品
  xhs-search      小红书笔记搜索
  xhs-note        小红书笔记详情
  xhs-user        小红书用户详情
  xhs-user-notes  小红书用户笔记
  strip           分享链接 → 无水印地址

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --search 1 --detail 3
  python3 scripts/run.py doctor
  python3 scripts/run.py hunt --platform dy --keyword "收纳盒" --yes
  python3 scripts/run.py breakdown
  python3 scripts/run.py clone --count 3
  python3 scripts/run.py cover

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


# ── GBK 编码兜底（照 video-lab 的写法）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到个别符号就 UnicodeEncodeError 崩掉。先加 errors='replace' 兜底，
# 再把记号统一换成 cp936 里有的 `√` / `×`（GBK 有这两个，没有 ✓ / ✗）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
APP = "watermark_removal"
APP_NAME = "水印消除"

# 计价（GET /api/v1/pricing 实测）：8 个接口一律 flat 100 点/次
POINTS_PER_CALL = 100
UPSTREAM_POINTS = 20          # 规则 note 原文：上游按请求 20 点
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 1000         # 10 次调用

# 出图线的实际单价（同一份 /api/v1/pricing 实测，供 cover 报价）
IMAGE_LINES = (
    ("nano_banana", "AI 商品图（nano-banana）", 72,
     "商品图 / 封面图，固定 72 点/次；带 views[] 时按 25 点 × 视角数"),
    ("aigc_qwen_image", "通义万相出图（qwen-image）", 78,
     "通用出图，78 点/次"),
    ("aigc_wan_image", "万相出图（wan）", 203,
     "写实场景图，203 点/次"),
)

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "ecom-spy")
SNAP_DIR = os.path.join(HOME_DIR, "snapshots")
LATEST = os.path.join(HOME_DIR, "latest.json")
LEDGER = os.path.join(HOME_DIR, "ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-ecom-spy/%s" % VERSION

# ── 8 个接口：参数名逐字照 params_schema（大小写敏感，别改） ────────────────
#   args = (属性名, 命令行开关, 类型, 是否必填, help)
APIS = {
    "douyin_search_video": dict(
        name="抖音搜索", cmd="dy-search", platform="douyin", kind="search",
        desc="按关键词搜作品，回列表（点赞 / 评论 / 收藏 / 时长）",
        args=[("keyword", "--keyword", str, True, "搜索关键词"),
              ("page", "--page", str, False, "页码（先不传，翻页再传）"),
              ("searchId", "--search-id", str, False, "搜索会话标识，翻页时带上更稳")]),
    "douyin_video_detail": dict(
        name="抖音视频详情", cmd="dy-video", platform="douyin", kind="detail",
        desc="按作品 ID 取单条详情（标题 / 时长 / 互动数）",
        args=[("videoId", "--video-id", str, True, "作品 ID（分享链接里的那串数字）")]),
    "douyin_user_video_list": dict(
        name="抖音用户作品", cmd="dy-user", platform="douyin", kind="list",
        desc="按 secUid 拉某个号的公开作品列表",
        args=[("secUid", "--sec-uid", str, True, "用户 secUid（主页链接里的 MS4wLjAB…）"),
              ("maxCursor", "--max-cursor", str, False, "翻页游标，取自上一页")]),
    "xhs_search_note": dict(
        name="小红书笔记搜索", cmd="xhs-search", platform="xhs", kind="search",
        desc="按关键词搜笔记，可配排序 / 类型 / 时间筛选",
        args=[("keyword", "--keyword", str, True, "搜索关键词"),
              ("page", "--page", str, False, "页码，默认 1"),
              ("sort", "--sort", str, False,
               "排序：general / popularity_descending / time_descending / "
               "comment_descending / collect_descending"),
              ("noteType", "--note-type", str, False, "笔记类型：_0 通用 / _1 视频 / _2 图文"),
              ("noteTime", "--note-time", str, False, "发布时间筛选（按上游约定传值）")]),
    "xhs_note_detail": dict(
        name="小红书笔记详情", cmd="xhs-note", platform="xhs", kind="detail",
        desc="按笔记 ID 取单条详情（标题 / 正文 / 互动数）",
        args=[("noteId", "--note-id", str, True, "笔记 ID（分享链接 /explore/ 后面那串）")]),
    "xhs_user_detail": dict(
        name="小红书用户详情", cmd="xhs-user", platform="xhs", kind="user",
        desc="按用户 ID 取账号资料（昵称 / 简介 / 粉丝）",
        args=[("userId", "--user-id", str, True, "小红书用户 ID（userid）")]),
    "xhs_user_note_list": dict(
        name="小红书用户笔记", cmd="xhs-user-notes", platform="xhs", kind="list",
        desc="按用户 ID 拉笔记列表，用来盘一个号的选题结构",
        args=[("userId", "--user-id", str, True, "小红书用户 ID（userid）"),
              ("cursor", "--cursor", str, False, "翻页游标，取自上一页笔记项"),
              ("lastCursor", "--last-cursor", str, False, "上一页末条目的游标")]),
    "remove": dict(
        name="去除水印", cmd="strip", platform="any", kind="media",
        desc="分享链接 → 无水印地址（视频 / 图集）",
        args=[("url", "--url", str, True, "短视频 / 图文分享链接")]),
}
ORDER = ["douyin_search_video", "douyin_video_detail", "douyin_user_video_list",
         "xhs_search_note", "xhs_note_detail", "xhs_user_detail",
         "xhs_user_note_list", "remove"]
CMD_ORDER = [APIS[c]["cmd"] for c in ORDER]
BY_CMD = dict((APIS[c]["cmd"], c) for c in ORDER)


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
        except Exception:                                    # noqa: BLE001
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
        except Exception as e:                               # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                        # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        for k in ("msg", "message", "error"):
            v = d.get(k)
            if isinstance(v, dict):
                v = v.get("message") or v.get("code")
            if v:
                return str(v)[:300]
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def api_path(code):
    return API_PREFIX + "/apps/" + APP + "/" + code


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                        # noqa: BLE001
        return str(n)


def fmt_yuan(pts):
    return "%.2f" % (float(pts) / POINTS_PER_YUAN)


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


# ───────────────────────── 闸门 ─────────────────────────
def gate(a, calls, what):
    """两道闸门：预算不够 → 5（不发请求）；没 --yes → 4。"""
    cost = int(calls) * POINTS_PER_CALL
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点超过 --budget %d 点（%s %d 次 × %d 点/次）。"
                   "一个请求都没发；调大 --budget（单位：点，1 元 = 100 点）再试。"
                   % (cost, a.budget, what, calls, POINTS_PER_CALL), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实调用 %s，扣 %d 点（%.2f 元，%d 次 × %d 点/次）。"
                   "确认请加 --yes。" % (what, cost, cost / float(POINTS_PER_YUAN),
                                        calls, POINTS_PER_CALL), EXIT_CONFIRM)
    return cost


def need(a, code):
    """必填检查：缺参数 → exit 2，一个请求都不发。"""
    miss = []
    for dest, flag, _t, req, _h in APIS[code]["args"]:
        if not req:
            continue
        v = getattr(a, dest, None)
        if v is None or (isinstance(v, str) and not v.strip()):
            miss.append(flag)
    if miss:
        raise Fail("usage", "%s 缺必填参数：%s（见 `catalog` 的必填列）"
                   % (APIS[code]["name"], " ".join(miss)), EXIT_USAGE)


def build_body(a, code):
    body = {}
    for dest, _flag, _t, _req, _h in APIS[code]["args"]:
        v = getattr(a, dest, None)
        if v is None:
            continue
        if isinstance(v, str):
            if not v.strip():
                continue
            v = v.strip()
        body[dest] = v
    return body


# ───────────────────────── 返回体解析 ─────────────────────────
def payload_of(d):
    """拆信封。文档写「业务数据位于 result.data」，其余几种形态一并兜住。"""
    if not isinstance(d, dict):
        return d
    r = d.get("result")
    if isinstance(r, dict) and isinstance(r.get("data"), (dict, list)):
        return r["data"]
    if isinstance(d.get("data"), (dict, list)):
        return d["data"]
    if isinstance(r, (dict, list)):
        return r
    return d


ID_KEYS = ("aweme_id", "awemeId", "note_id", "noteId", "video_id", "videoId",
           "item_id", "itemId", "id")
TITLE_KEYS = ("desc", "title", "display_title", "displayTitle", "caption",
              "content", "note_title", "share_title")
STAT_GROUPS = ("statistics", "stats", "interact_info", "interactInfo",
               "count", "counts")
LIKE_KEYS = ("digg_count", "liked_count", "like_count", "likeCount", "likes",
             "diggCount", "likedCount", "praise_count")
COL_KEYS = ("collect_count", "collected_count", "collectCount", "collects",
            "collectedCount")
CMT_KEYS = ("comment_count", "commentCount", "comments", "comments_count")
SHR_KEYS = ("share_count", "shareCount", "shared_count", "sharedCount",
            "shares", "forward_count")
AUTHOR_KEYS = ("nickname", "author_name", "authorName", "user_name", "userName",
               "nick_name", "name", "author")


def _first_num(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip().isdigit():
            return float(v.strip())
    return None


def _first_str(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def is_item(node):
    if not isinstance(node, dict):
        return False
    if not _first_str(node, TITLE_KEYS):
        return False
    return bool(_first_str(node, ID_KEYS)) or any(
        isinstance(node.get(g), dict) for g in STAT_GROUPS)


def walk_items(node, out, depth=0):
    """容错递归：见到像「一条作品 / 一篇笔记」的 dict 就收下，不再往里钻。"""
    if depth > 8:
        return
    if isinstance(node, dict):
        if is_item(node):
            out.append(node)
            return
        for v in node.values():
            walk_items(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            walk_items(v, out, depth + 1)


def norm_item(node):
    stats = {}
    for g in STAT_GROUPS:
        v = node.get(g)
        if isinstance(v, dict):
            stats.update(v)
    flat = dict(node)
    flat.update({k: v for k, v in stats.items() if k not in flat})
    dur = _first_num(flat, ("duration", "video_duration", "durationSec"))
    if dur is None:
        vv = node.get("video")
        if isinstance(vv, dict):
            dur = _first_num(vv, ("duration", "duration_ms", "durationMs"))
    if dur is not None and dur > 1000:      # 毫秒 → 秒
        dur = dur / 1000.0
    author = _first_str(flat, AUTHOR_KEYS)
    au = node.get("author") or node.get("user")
    if isinstance(au, dict):
        author = _first_str(au, AUTHOR_KEYS) or author
        if not author:
            author = _first_str(au, ("unique_id", "red_id", "sec_uid"))
    return {"id": _first_str(flat, ID_KEYS),
            "title": _first_str(flat, TITLE_KEYS) or "",
            "author": author or "",
            "likes": _first_num(flat, LIKE_KEYS),
            "collects": _first_num(flat, COL_KEYS),
            "comments": _first_num(flat, CMT_KEYS),
            "shares": _first_num(flat, SHR_KEYS),
            "duration": round(dur, 1) if dur else None,
            "raw": node}


def collect_urls(node, out, depth=0):
    if depth > 10:
        return
    if isinstance(node, str):
        if node.startswith("http") and node not in out:
            out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            collect_urls(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            collect_urls(v, out, depth + 1)


def save_snapshot(code, body, raw, items, elapsed):
    try:
        os.makedirs(SNAP_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(SNAP_DIR, "%s-%s.json" % (stamp, code))
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": code,
               "name": APIS[code]["name"], "platform": APIS[code]["platform"],
               "request": body, "elapsed": round(elapsed, 1),
               "items": items, "raw": raw}
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(rec, ensure_ascii=False, indent=1))
        io.open(LATEST, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"path": path, "at": rec["at"], "api": code,
                        "name": rec["name"], "platform": rec["platform"],
                        "count": len(items), "request": body},
                       ensure_ascii=False, indent=1))
        return path
    except Exception:                                        # noqa: BLE001
        return None


def ledger_add(rec):
    try:
        os.makedirs(HOME_DIR, exist_ok=True)
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                        # noqa: BLE001
        pass


def load_snapshot(arg):
    """读快照。不带参数就是最新那份。"""
    path = arg
    meta = {}
    if not path or path == "latest":
        if not os.path.isfile(LATEST):
            raise Fail("usage",
                       "还没有快照。先跑一次：`run.py hunt --platform dy --keyword 你的词 --yes`"
                       "（100 点/次），或者 `run.py dy-search --keyword … --yes`。", EXIT_USAGE)
        try:
            meta = json.load(io.open(LATEST, encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            raise Fail("usage", "最新快照指针坏了：%s" % LATEST, EXIT_USAGE)
        path = meta.get("path")
    if not path or not os.path.isfile(path):
        raise Fail("usage", "快照文件不存在：%s" % path, EXIT_USAGE)
    try:
        d = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:                                   # noqa: BLE001
        raise Fail("usage", "快照读不出来：%s（%s）" % (path, e), EXIT_USAGE)
    d["_path"] = path
    return d


# ───────────────────────── 免费：catalog ─────────────────────────
def cmd_catalog(a, key, host):
    rows = []
    for code in ORDER:
        m = APIS[code]
        req = [f for d, f, _t, r, _h in m["args"] if r]
        opt = [f for d, f, _t, r, _h in m["args"] if not r]
        rows.append({"api": code, "name": m["name"], "command": m["cmd"],
                     "platform": m["platform"], "required": req, "optional": opt,
                     "points": POINTS_PER_CALL, "yuan": fmt_yuan(POINTS_PER_CALL),
                     "path": api_path(code), "desc": m["desc"]})
    out = {"ok": True, "app": APP, "appName": APP_NAME, "count": len(rows),
           "pointsPerCall": POINTS_PER_CALL, "yuanPerCall": fmt_yuan(POINTS_PER_CALL),
           "upstreamPoints": UPSTREAM_POINTS,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "apis": rows}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 带货素材侦察 —— %d 个接口，一律 %d 点/次（%s 元）"
          % (len(rows), POINTS_PER_CALL, fmt_yuan(POINTS_PER_CALL)))
    print()
    print("  %s %s %s %s %s" % (pad("子命令", 16), pad("接口 code", 24),
                                pad("平台", 8), pad("必填", 14), "干什么"))
    print("  " + "-" * 106)
    for r in rows:
        print("  %s %s %s %s %s"
              % (pad(r["command"], 16), pad(r["api"], 24),
                 pad(r["platform"], 8), pad(" ".join(r["required"]) or "-", 14),
                 r["desc"]))
    print()
    print("  1 元 = 100 点。价格来自 GET /api/v1/pricing 的")
    print("  /api/v1/apps/watermark_removal/* = flat 100 点/次（上游按请求 %d 点，"
          "失败亦计）" % UPSTREAM_POINTS)
    print("  8 个接口同价：与返回条数、素材时长都无关，一次调用就是 100 点。")
    print()
    print("  免费先看：`cost`（先算钱）· `doctor`（只读自检，0 点）· `rank` / `breakdown`")
    print("  / `clone` / `cover`（读本地快照，0 点）")
    return 0


# ───────────────────────── 免费：cost ─────────────────────────
def cmd_cost(a, key, host):
    parts = (("search", a.search, "搜索"), ("detail", a.detail, "详情"),
             ("list", a.list, "列表"), ("strip", a.strip, "去水印"))
    calls = sum(v for _k, v, _n in parts)
    if calls <= 0:
        calls = 1
    total = calls * POINTS_PER_CALL
    combos = [
        {"name": "最小验证：1 次搜索", "calls": 1},
        {"name": "一条链：搜索 1 + 详情 3 + 去水印 1", "calls": 5},
        {"name": "盘一个号：用户作品 1 + 详情 8 + 去水印 3", "calls": 12},
    ]
    for c in combos:
        c["points"] = c["calls"] * POINTS_PER_CALL
        c["yuan"] = fmt_yuan(c["points"])
    out = {"ok": True, "pointsPerCall": POINTS_PER_CALL,
           "yuanPerCall": fmt_yuan(POINTS_PER_CALL),
           "upstreamPoints": UPSTREAM_POINTS, "budget": a.budget,
           "calls": calls, "estimate": total, "yuan": fmt_yuan(total),
           "withinBudget": total <= a.budget,
           "affordableCalls": int(a.budget // POINTS_PER_CALL),
           "breakdown": [{"kind": n, "calls": v, "points": v * POINTS_PER_CALL}
                         for _k, v, n in parts if v > 0],
           "combos": combos}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("先算钱（1 元 = 100 点，1 次调用 = %d 点）" % POINTS_PER_CALL)
    print()
    print("  本次：%d 次调用 = %d 点 = %s 元" % (calls, total, fmt_yuan(total)))
    for b in out["breakdown"]:
        print("    · %s %d 次 → %d 点" % (b["kind"], b["calls"], b["points"]))
    print()
    print("  --budget %d 点 = 最多 %d 次；%s"
          % (a.budget, out["affordableCalls"],
             "本次预算够" if out["withinBudget"] else "本次会退 5，一个请求都不发"))
    print()
    print("  三档跑法：")
    for c in combos:
        print("    %s → %d 点（%s 元）" % (pad(c["name"], 46), c["points"], c["yuan"]))
    print()
    print("  口径：价格规则是 flat，8 个接口同价，失败按规则 note 也计一次。")
    print("  所以「先少搜、再挑着看详情」比一次拉满省 —— 搜索 1 次就能排出榜，")
    print("  详情只为要看的那 3 条付钱。")
    return 0


# ───────────────────────── 免费：doctor（只读） ─────────────────────────
def cmd_doctor(a, key, host):
    checks = []

    # 1) Key + 余额
    st, txt = http_json("GET", host + "/user/balance", key, None, 40)
    d = jloads(txt) or {}
    checks.append(("Key 有效 + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点" % (st, fmt_pts(d.get("available_points") or 0))))

    # 2) 模型目录（Key 的另一种验证，只读免费）
    st, txt = http_json("GET", host + API_PREFIX + "/models", key, None, 60)
    d = jloads(txt) or {}
    n_models = len(d.get("data") or []) if isinstance(d, dict) else 0
    checks.append(("模型目录 GET /api/v1/models 可达", st == 200 and n_models > 0,
                   "HTTP %s · %d 个模型" % (st, n_models)))

    # 3) 应用在架 + 8 个接口齐全（用名单证明端点存在，不发 POST）
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, None, 60)
    d = jloads(txt) or {}
    found, codes = None, set()
    for app in (d.get("data") or []) if isinstance(d, dict) else []:
        if isinstance(app, dict) and app.get("code") == APP:
            found = app
            codes = {x.get("code") for x in (app.get("apis") or []) if isinstance(x, dict)}
            break
    miss = [c for c in ORDER if c not in codes]
    checks.append(("应用 %s 在架 + 8 个接口齐全" % APP,
                   st == 200 and found is not None and not miss,
                   "HTTP %s · 命中 %d 个%s" % (st, len(codes),
                                              "，缺 " + ",".join(miss) if miss else "")))

    # 4) 价目表：本地 100 点 vs 线上规则
    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, None, 60)
    d = jloads(txt) or {}
    rules = d.get("pricing") if isinstance(d.get("pricing"), dict) else {}
    rule = rules.get("/api/v1/apps/" + APP + "/*") or {}
    live_cost = rule.get("cost")
    checks.append(("单价 = %d 点/次（与 /api/v1/pricing 一致）" % POINTS_PER_CALL,
                   st == 200 and live_cost == POINTS_PER_CALL,
                   "HTTP %s · 线上 %s 点/次 · note：%s"
                   % (st, live_cost, (rule.get("note") or "-")[:46])))

    # 5) 任务查询路由（本包 8 个接口是同步的，这条只为证明网关常在线）
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-ecom-probe",
                        key, None, 40)
    d = jloads(txt) or {}
    checks.append(("任务查询 GET /tasks/{id} 可达（假 id 返回「任务不存在」）",
                   st == 200 and d.get("code") == 0,
                   "HTTP %s %s" % (st, str(d.get("msg") or "")[:40])))

    # 6) 流水（用来核对「这一轮到底花了多少」）
    st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, None, 40)
    d = jloads(txt) or {}
    checks.append(("余额流水可达（对账用）", st == 200 and isinstance(d.get("logs"), list),
                   "HTTP %s · 共 %s 条 · balanceMoving %s"
                   % (st, fmt_pts(d.get("total") or 0), d.get("balanceMoving"))))

    out = {"ok": all(c[1] for c in checks), "app": APP,
           "endpoint": host + api_path("<接口code>"),
           "pointsPerCall": POINTS_PER_CALL, "upstreamPoints": UPSTREAM_POINTS,
           "probeMode": "read-only-get", "estimatedPoints": 0, "yuan": "0.00",
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json and not out["ok"]:
        bad = [n for n, o, _d in checks if not o]
        out = {"ok": False, "exit": EXIT_GATE,
               "error": {"kind": "gate",
                         "message": "自检有 %d 项没过：%s" % (len(bad), " / ".join(bad))},
               "app": APP, "estimatedPoints": 0, "yuan": "0.00",
               "checks": out["checks"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（%d 项 · 全部只读 GET · 本轮花费 0 点）" % len(checks))
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 44), dt))
    print()
    print("  端点：POST %s" % out["endpoint"])
    print("  名单：GET  %s/apps 现查 8 个 code（这就是端点存在的证据）" % API_PREFIX)
    print("  单价：100 点/次（1.00 元），8 个接口同价；上游 20 点/次")
    print("  本包一次 POST 都不发：规则原文写「失败亦计」，所以探针只走 GET。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 采集（100 点/次） ─────────────────────────
def do_call(a, key, host, code):
    need(a, code)
    body = build_body(a, code)
    calls = 1
    what = "%s（%s）" % (APIS[code]["name"], code)
    cost = gate(a, calls, what)
    url = host + api_path(code)

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "api": code, "url": url,
               "requestBody": body, "estimatedPoints": cost,
               "yuan": fmt_yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  价格：%d 点（%s 元），一次调用就是一次" % (cost, fmt_yuan(cost)))
        return 0

    say("正在调用 %s（%d 点）…" % (what, cost))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt)
    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": code, "ok": False,
                    "http": st, "error": msg, "request": body, "points": cost})
        raise Fail("call", "%s 调用失败（HTTP %s）：%s"
                   % (APIS[code]["name"], st, msg), EXIT_CALL)
    if not isinstance(d, dict):
        raise Fail("call", "%s 返回不是 JSON：%s"
                   % (APIS[code]["name"], (txt or "")[:200]), EXIT_CALL)
    code_v = d.get("code")
    if code_v not in (1, 200, None):
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": code, "ok": False,
                    "http": st, "error": msg, "request": body, "points": cost})
        raise Fail("call", "%s 被上游拒绝（code=%s）：%s"
                   % (APIS[code]["name"], code_v, msg), EXIT_CALL)

    payload = payload_of(d)
    nodes = []
    walk_items(payload, nodes)
    items = [norm_item(n) for n in nodes]
    seen, uniq = set(), []
    for it in items:
        k = it.get("id") or it.get("title")
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    path = save_snapshot(code, body, d, uniq, dt)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "api": code, "ok": True,
                "http": st, "request": body, "points": cost, "elapsed": round(dt, 1),
                "items": len(uniq), "snapshot": path})
    return {"d": d, "payload": payload, "items": uniq, "raw": d, "elapsed": dt,
            "cost": cost, "path": path, "url": url, "code": code}


def _print_collect(a, res, title=None):
    code, items = res["code"], res["items"]
    if a.json:
        print(json.dumps({"ok": True, "api": code, "name": APIS[code]["name"],
                          "count": len(items), "items": items,
                          "estimatedPoints": res["cost"], "yuan": fmt_yuan(res["cost"]),
                          "elapsed": round(res["elapsed"], 1),
                          "snapshot": res["path"],
                          "next": "python3 scripts/run.py rank" if items else None},
                         ensure_ascii=False))
        return 0
    print("%s（%.1fs · %d 点）" % (title or APIS[code]["name"], res["elapsed"], res["cost"]))
    if code == "remove":
        urls = []
        collect_urls(res["payload"], urls)
        if urls:
            for u in urls[:8]:
                print("  地址：%s" % u)
        else:
            print("  这条返回里没解析到地址，原始返回：")
            print("  " + json.dumps(res["payload"], ensure_ascii=False)[:600])
        if res["path"]:
            print("  快照：%s" % res["path"])
        return 0
    if not items:
        print("  这次没解析出条目。原始返回（前 800 字）如下，按 troubleshooting 的")
        print("  「解析不到条目」一节处理；`--json` 能拿到完整 raw：")
        print("  " + json.dumps(res["payload"], ensure_ascii=False)[:800])
        if res["path"]:
            print("  快照：%s" % res["path"])
        return 0
    ranked = sort_items(items, "heat")
    print("  解析到 %d 条，热度前 3：" % len(items))
    for i, it in enumerate(ranked[:3], 1):
        print("  %d. %s" % (i, (it["title"] or "(无标题)")[:52]))
        print("     %s" % hot_line(it))
    if res["path"]:
        print("  快照：%s" % res["path"])
    print()
    print("  下一步（都免费）：`rank` 出榜 · `breakdown` 拆结构 · `clone` 给仿写 ·")
    print("  `cover` 给封面 prompt")
    return 0


def cmd_hunt(a, key, host):
    code = "douyin_search_video" if a.platform == "dy" else "xhs_search_note"
    res = do_call(a, key, host, code)
    if a.dry_run:
        return res
    if a.json:
        print(json.dumps({"ok": True, "api": code, "platform": a.platform,
                          "keyword": a.keyword, "count": len(res["items"]),
                          "items": res["items"], "estimatedPoints": res["cost"],
                          "yuan": fmt_yuan(res["cost"]),
                          "snapshot": res["path"]}, ensure_ascii=False))
        return 0
    print("侦察报告 · %s「%s」（%.1fs · %d 点）"
          % ("抖音" if a.platform == "dy" else "小红书", a.keyword,
             res["elapsed"], res["cost"]))
    print("=" * 78)
    if not res["items"]:
        print("  这次没解析出条目。原始返回（前 700 字）：")
        print("  " + json.dumps(res["payload"], ensure_ascii=False)[:700])
        if res["path"]:
            print("  快照：%s" % res["path"])
        return 0
    ranked = sort_items(res["items"], a.by)
    top = ranked[:max(1, a.top)]
    print("  解析到 %d 条，按「%s」取前 %d 条：" % (len(res["items"]), a.by, len(top)))
    for i, it in enumerate(top, 1):
        print("  %d. %s" % (i, (it["title"] or "(无标题)")[:56]))
        print("     %s" % hot_line(it))
    print()
    for i, it in enumerate(top, 1):
        print("── 拆结构 #%d ──────────────────────────────────────────────" % i)
        for ln in breakdown_lines(it):
            print("  " + ln)
        print()
    print("── 仿写（第 1 条） ────────────────────────────────────────")
    for ln in clone_lines(top[0], a.count):
        print("  " + ln)
    print()
    print("── 出图方案 ───────────────────────────────────────────────")
    for ln in cover_lines(top[0]):
        print("  " + ln)
    if res["path"]:
        print()
        print("  快照已存：%s" % res["path"])
        print("  离线复看（0 点）：`rank` / `breakdown` / `clone` / `cover`")
    return 0


# ───────────────────────── 本地分析（0 点） ─────────────────────────
def heat_of(it):
    return ((it.get("likes") or 0) * 1.0 + (it.get("collects") or 0) * 2.0
            + (it.get("comments") or 0) * 3.0 + (it.get("shares") or 0) * 4.0)


SORT_KEYS = {"heat": ("热度（赞1+藏2+评3+转4）", heat_of),
             "likes": ("点赞", lambda it: it.get("likes") or 0),
             "collects": ("收藏", lambda it: it.get("collects") or 0),
             "comments": ("评论", lambda it: it.get("comments") or 0),
             "shares": ("转发", lambda it: it.get("shares") or 0),
             "short": ("时长（短的在前，适合快节奏）",
                       lambda it: -(it.get("duration") or 9999))}


def sort_items(items, by):
    _label, fn = SORT_KEYS.get(by, SORT_KEYS["heat"])
    return sorted(items, key=fn, reverse=True)


def fmt_hot(n):
    if n is None:
        return "-"
    try:
        v = float(n)
    except Exception:                                        # noqa: BLE001
        return "-"
    if v >= 100000000:
        return "%.1f亿" % (v / 100000000.0)
    if v >= 10000:
        return "%.1f万" % (v / 10000.0)
    return "%d" % int(v)


def hot_line(it):
    d = it.get("duration")
    return "赞 %s · 藏 %s · 评 %s · 转 %s · 时长 %s" % (
        fmt_hot(it.get("likes")), fmt_hot(it.get("collects")),
        fmt_hot(it.get("comments")), fmt_hot(it.get("shares")),
        ("%.0fs" % d) if d else "-")


RE_DIGIT = re.compile(r"\d")
RE_PRICE = re.compile(r"元|块|¥|￥|折|价|便宜|贵|省|划算|性价比|预算|券")
RE_QUESTION = re.compile(r"？|\?|吗|怎么|为什么|哪|多少|有没有|如何")
RE_CONTRAST = re.compile(r"但|却|反而|其实|别再|不如|不是.{0,8}而是|从.{1,8}到|对比|之前|以前")
RE_IDENTITY = re.compile(r"女生|男生|宝妈|上班族|学生|租房|小个子|微胖|油皮|干皮|新手|"
                         r"懒人|打工人|独居|宿舍|新手|新手党|手残")
RE_PAIN = re.compile(r"难|累|烦|尴尬|后悔|踩坑|翻车|冤枉钱|不好用|鸡肋|浪费|翻不了|"
                     r"总是|老是|每次")
RE_PROMISE = re.compile(r"教你|一招|三招|闭眼|后悔没早|看完|终于|实测|亲测|收藏|必看|"
                        r"搞定|学会|直接|一次")
RE_TAG = re.compile(r"#[^#\s]{1,24}")
RE_HOOK = (
    ("悬念", re.compile(r"最后|结尾|第.{1,3}[个种条款点]|没想到|才知道|真相|居然|竟然|"
                        r"秘密|偷偷")),
    ("反差", RE_CONTRAST),
    ("价格", RE_PRICE),
    ("痛点", RE_PAIN),
    ("身份", RE_IDENTITY),
    ("数字", re.compile(r"\d+\s*(?:个|种|步|招|天|元|块|件|秒|分钟|倍)")),
)


def title_features(title):
    t = title or ""
    return {"length": len(t), "digit": bool(RE_DIGIT.search(t)),
            "price": bool(RE_PRICE.search(t)), "question": bool(RE_QUESTION.search(t)),
            "contrast": bool(RE_CONTRAST.search(t)), "identity": bool(RE_IDENTITY.search(t)),
            "pain": bool(RE_PAIN.search(t)), "promise": bool(RE_PROMISE.search(t)),
            "tags": len(RE_TAG.findall(t))}


def hook_labels(title):
    t = title or ""
    hits = [name for name, rx in RE_HOOK if rx.search(t)]
    return hits or ["直给"]


def formula_of(feat):
    parts = []
    if feat["identity"]:
        parts.append("身份词")
    if feat["pain"]:
        parts.append("痛点")
    if feat["price"]:
        parts.append("价格锚")
    if feat["digit"]:
        parts.append("数字")
    if feat["promise"]:
        parts.append("结果承诺")
    if feat["question"]:
        parts.append("提问")
    return " + ".join(parts) if parts else "场景 + 结果 + 行动"


def duration_band(d):
    if not d:
        return ("未知", "按 30 秒设计：3s 钩子 / 7s 痛点 / 15s 演示 / 5s 行动")
    if d <= 15:
        return ("15 秒内（快节奏）", "0-3s 钩子直接出结果 / 3-10s 演示 / 10-15s 价格与行动")
    if d <= 30:
        return ("15-30 秒（主流）", "0-3s 钩子 / 3-8s 痛点 / 8-20s 演示 / 20-30s 价格与行动")
    if d <= 60:
        return ("30-60 秒（讲透）", "0-3s 钩子 / 3-10s 痛点 / 10-35s 演示 2 轮 / 35-50s 对比"
                                   " / 50-60s 价格与行动")
    return ("60 秒以上（长讲解）",
            "0-3s 钩子 / 3-15s 痛点 / 15-40s 演示第 1 轮 / 40-55s 演示第 2 轮 / "
            "55-70s 对比 / 末 10s 价格与行动")


def breakdown_lines(it):
    feat = title_features(it["title"])
    band, pace = duration_band(it.get("duration"))
    hooks = hook_labels(it["title"])
    tags = RE_TAG.findall(it["title"] or "")
    mark = lambda b: "√" if b else "×"     # noqa: E731
    out = ["标题：%s" % (it["title"] or "(无标题)")[:70],
           "互动：%s" % hot_line(it),
           "时长：%s · %s" % (("%.0f 秒" % it["duration"]) if it.get("duration")
                             else "未返回", band),
           "标题：%d 字 · 数字%s · 价格%s · 疑问%s · 身份%s · 痛点%s · 承诺%s · 话题 %d 个"
           % (feat["length"], mark(feat["digit"]), mark(feat["price"]),
              mark(feat["question"]), mark(feat["identity"]), mark(feat["pain"]),
              mark(feat["promise"]), feat["tags"]),
           "公式：%s" % formula_of(feat),
           "钩子：%s" % " / ".join(hooks),
           "节奏：%s" % pace]
    if tags:
        out.append("话题：%s" % " ".join(tags[:6]))
    out.append("热度：%s（赞 1 + 藏 2 + 评 3 + 转 4，收藏和评论权重更高）"
               % fmt_hot(round(heat_of(it))))
    return out


def _category_word(it):
    tags = RE_TAG.findall(it["title"] or "")
    if tags:
        w = tags[0].lstrip("#")
        if w:
            return w
    t = (it["title"] or "").strip()
    t = re.sub(r"[，。！？、,.!?：:\s].*$", "", t)
    return t[:8] or "这个东西"


def _number_word(it):
    m = re.search(r"(\d+)\s*(?:个|种|步|招|天|元|块|件|秒|分钟|倍)", it["title"] or "")
    if m:
        return m.group(1)
    return "3"


def _price_word(it):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块)", it["title"] or "")
    return ("%s 元" % m.group(1)) if m else "一顿外卖的钱"


def clone_lines(it, count=3):
    cat = _category_word(it)
    num = _number_word(it)
    price = _price_word(it)
    feat = title_features(it["title"])
    same = [k for k, v in (("身份词", feat["identity"]), ("痛点", feat["pain"]),
                           ("价格锚", feat["price"]), ("数字", feat["digit"]))
            if v]
    if "价格锚" in same and "数字" in same:
        t1 = "%s别乱买，%s 的%s，实测够用" % (cat, num, price)
    elif "痛点" in same:
        t1 = "%s总踩坑？%s 步挑出对的%s" % (cat, num, cat)
    else:
        t1 = "%s用了 %s 天，我把方法拆成 %s 步" % (cat, num, num)
    t2 = "为什么带货榜单上的%s，都在用这 %s 个开头" % (cat, num)
    t3 = "先说结论：%s值得买，%s 个细节别忽略" % (cat, num)
    titles = [t1, t2, t3][:max(1, min(3, count))]
    hooks = [
        "价格前置：这个%s只要%s，我一开始也不信。先看 3 秒效果。" % (cat, price),
        "痛点前置：买%s最烦的就是挑不对，我试了 %s 种才敢说这句。" % (cat, num),
        "结论前置：先说结论 —— %s能处，%s 个细节看完再决定。" % (cat, num),
    ]
    band, _pace = duration_band(it.get("duration"))
    out = ["沿用公式：%s" % formula_of(feat),
           "主词：%s · 数字：%s · 价格锚：%s" % (cat, num, price), ""]
    for i, t in enumerate(titles, 1):
        out.append("标题 %d：%s" % (i, t))
    out.append("")
    for i, h in enumerate(hooks, 1):
        out.append("钩子 %d：%s" % (i, h))
    out.append("")
    out.append("分镜骨架（按原片 %s）：" % band)
    beats = [("0-3s", "钩子：开口第一句就是上面某个钩子，画面直接给结果"),
             ("3-8s", "痛点：说出观众正在经历的那件事，给一个反常识判断"),
             ("8-18s", "演示：只演示 1 个动作，镜头不切走，字幕给关键数字"),
             ("18-25s", "对比：前后 / 用与不用，一屏放两格"),
             ("25-30s", "价格与行动：报价格锚，给一句明确动作")]
    for t, d in beats:
        out.append("  %s  %s" % (pad(t, 7), d))
    out.append("")
    out.append("自用备注：以上是结构参考，正文与画面请自己拍、自己写。")
    return out


def cover_lines(it):
    cat = _category_word(it)
    price = _price_word(it)
    prompts = [
        "白底商品图：%s居中，45 度俯拍，柔光箱打光，浅灰纯色背景，"
        "留右上角 1/4 空白放价格「%s」，画面干净无文字堆叠" % (cat, price),
        "使用场景图：%s放在真实使用场景里（桌面 / 手边 / 出门携带），"
        "自然光，浅景深，人物手部入镜一小块，营造「已经在用」的现场感" % cat,
        "对比图：左右两格，左边「用之前」的常见困扰，右边「用之后」的整齐结果，"
        "同机位同光线，中间留 8px 白缝，右下角留价格标签位",
    ]
    out = ["封面 3 个方向（复制 prompt 到出图接口跑，本包不代下单）："]
    for i, p in enumerate(prompts, 1):
        out.append("  %d. %s" % (i, p))
    out.append("")
    out.append("该走哪条线（单价取自 GET /api/v1/pricing，实测）：")
    for code, name, pts, note in IMAGE_LINES:
        out.append("  %s %s  %d 点/张（%s 元）  %s"
                   % (pad(code, 18), pad(name, 22), pts, fmt_yuan(pts), note))
    out.append("")
    out.append("  封面图建议走 nano_banana（72 点/张）：商品图是它的主场，比通用出图便宜。")
    out.append("  一条爆款 100 点 + 一张封面 72 点 = 172 点（1.72 元）跑完一条完整链路。")
    out.append("  标题字压在留白区，不要压在产品上 —— 竖版 3:4，第一屏只放一句主张。")
    return out


def _load_items(a):
    d = load_snapshot(a.snapshot)
    items = d.get("items") or []
    if not items:
        raise Fail("usage",
                   "这份快照里没有条目（%s）。换一份：`--snapshot <路径>`，"
                   "或重新跑一次 hunt。" % (d.get("_path") or "-"), EXIT_USAGE)
    return d, items


def cmd_rank(a, key, host):
    d, items = _load_items(a)
    ranked = sort_items(items, a.by)
    shown = ranked[:max(1, a.top)]
    out = {"ok": True, "snapshot": d.get("_path"), "api": d.get("api"),
           "recordedAt": d.get("at"), "count": len(items), "by": a.by,
           "top": [{"rank": i, "id": it["id"], "title": it["title"],
                    "author": it["author"], "likes": it["likes"],
                    "collects": it["collects"], "comments": it["comments"],
                    "shares": it["shares"], "duration": it["duration"],
                    "heat": round(heat_of(it), 1)}
                   for i, it in enumerate(shown, 1)],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("爆款榜 · %d 条里取前 %d（按 %s）" % (len(items), len(shown), a.by))
    print("  快照：%s（%s 采集，本地分析 0 点）" % (d.get("_path"), d.get("at")))
    print()
    print("  %s %s %s %s %s" % (pad("#", 3), pad("标题", 40), pad("时长", 7),
                                pad("热度", 8), "赞 / 藏 / 评 / 转"))
    print("  " + "-" * 96)
    for i, it in enumerate(shown, 1):
        print("  %s %s %s %s %s"
              % (pad(i, 3), pad((it["title"] or "-")[:38], 40),
                 pad(("%.0fs" % it["duration"]) if it.get("duration") else "-", 7),
                 pad(fmt_hot(round(heat_of(it))), 8),
                 "%s / %s / %s / %s" % (fmt_hot(it["likes"]), fmt_hot(it["collects"]),
                                        fmt_hot(it["comments"]), fmt_hot(it["shares"]))))
    print()
    print("  下一步：`breakdown` 拆第 1 条的结构 · `clone` 给仿写 · `cover` 给封面")
    return 0


def cmd_breakdown(a, key, host):
    d, items = _load_items(a)
    ranked = sort_items(items, a.by)
    shown = ranked[:max(1, a.top)]
    out = {"ok": True, "snapshot": d.get("_path"), "count": len(items),
           "by": a.by, "items": []}
    for it in shown:
        feat = title_features(it["title"])
        band, pace = duration_band(it.get("duration"))
        out["items"].append({"title": it["title"], "author": it["author"],
                             "duration": it["duration"], "band": band,
                             "features": feat, "formula": formula_of(feat),
                             "hooks": hook_labels(it["title"]),
                             "pace": pace, "heat": round(heat_of(it), 1)})
    out["estimatedPoints"] = 0
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("拆结构 · 前 %d 条（本地分析，0 点）" % len(shown))
    print()
    for i, it in enumerate(shown, 1):
        print("── #%d ────────────────────────────────────────────────────" % i)
        for ln in breakdown_lines(it):
            print("  " + ln)
        print()
    print("  记号：√ 有 / × 没有。公式是按标题里实际出现的元素拼的，不是模板套话。")
    return 0


def cmd_clone(a, key, host):
    d, items = _load_items(a)
    it = sort_items(items, a.by)[0]
    lines = clone_lines(it, a.count)
    out = {"ok": True, "snapshot": d.get("_path"), "source": it["title"],
           "count": a.count,
           "titles": [ln.split("：", 1)[1] for ln in lines if ln.startswith("标题 ")],
           "hooks": [ln.split("：", 1)[1] for ln in lines if ln.startswith("钩子 ")],
           "formula": formula_of(title_features(it["title"])),
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("仿写 · 参照：%s" % (it["title"] or "")[:56])
    print()
    for ln in lines:
        print("  " + ln if ln else "")
    return 0


def cmd_cover(a, key, host):
    d, items = _load_items(a)
    it = sort_items(items, a.by)[0]
    out = {"ok": True, "snapshot": d.get("_path"), "source": it["title"],
           "lines": cover_lines(it),
           "imageLines": [{"code": c, "name": n, "points": p, "yuan": fmt_yuan(p),
                           "note": note} for c, n, p, note in IMAGE_LINES],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("出图方案 · 参照：%s" % (it["title"] or "")[:56])
    print()
    for ln in cover_lines(it):
        print("  " + ln if ln else "")
    return 0


def cmd_log(a, key, host):
    arr = []
    if os.path.isfile(LEDGER):
        try:
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            arr = []
    entries = arr[-a.limit:]
    spent = sum(e.get("points") or 0 for e in arr if e.get("ok"))
    out = {"ok": True, "count": len(arr), "entries": entries,
           "pointsSpent": spent, "yuan": fmt_yuan(spent), "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条 · 累计 %d 点 = %s 元）"
          % (len(entries), len(arr), spent, fmt_yuan(spent)))
    if not entries:
        print("  还没有记录。跑一次 `hunt` 或 `dy-search` 就会记上。")
        return 0
    print()
    print("  %s %s %s %s %s" % (pad("时间", 20), pad("接口", 24),
                                pad("结果", 6), pad("点数", 7), "条数 / 快照"))
    print("  " + "-" * 92)
    for e in entries:
        print("  %s %s %s %s %s"
              % (pad(e.get("at") or "-", 20), pad(e.get("api") or "-", 24),
                 pad("ok" if e.get("ok") else "fail", 6),
                 pad("%d" % (e.get("points") or 0), 7),
                 ("%s 条 · %s" % (e.get("items"), os.path.basename(e.get("snapshot") or "")))
                 if e.get("ok") else str(e.get("error") or "")[:40]))
    print()
    print("  核对真实花费：`curl` 或浏览器看 GET /user/balance/logs（免费），")
    print("  sync:/api/v1/apps/watermark_removal/... 每次 -100 点。")
    return 0


# ───────────────────────── CLI ─────────────────────────
class CliError(Exception):
    """argparse 的用法错改成异常，这样 `--json` 下也能给一个 JSON 文档。"""


class CliParser(argparse.ArgumentParser):
    def error(self, message):                                # noqa: D102
        raise CliError(message)


def _parser():
    ap = CliParser(
        prog="run.py",
        description="三剪客 · 带货素材侦察（8 个接口 / 100 点一次 / 结构分析在本地跑）",
        epilog="端点：POST %s/api/v1/apps/watermark_removal/<接口code> · "
               "名单：GET %s/api/v1/apps · 价目：GET %s/api/v1/pricing"
               % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d = %d 次调用）"
                         % (DEFAULT_BUDGET, DEFAULT_BUDGET // POINTS_PER_CALL))
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="8 个接口 + 必填项 + 单价（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：单次 / 组合 / 按预算能跑几次（免费）",
                       allow_abbrev=False)
    p.add_argument("--search", type=int, default=0, help="搜索调用次数")
    p.add_argument("--detail", type=int, default=0, help="详情调用次数")
    p.add_argument("--list", type=int, default=0, help="列表调用次数")
    p.add_argument("--strip", type=int, default=0, help="去水印调用次数")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="只读自检：Key / 应用 / 8 个接口 / 价目（免费，0 点）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("rank", help="把快照按热度排序，出爆款榜（免费）", allow_abbrev=False)
    p.add_argument("--snapshot", help="快照路径（默认最新那份）")
    p.add_argument("--by", default="heat", choices=sorted(SORT_KEYS),
                   help="排序口径（默认 heat）")
    p.add_argument("--top", type=int, default=10, help="显示前几条（默认 10）")
    p.set_defaults(fn=cmd_rank)

    p = sub.add_parser("breakdown", help="拆结构：标题公式 / 钩子 / 时长 / 节奏（免费）",
                       allow_abbrev=False)
    p.add_argument("--snapshot", help="快照路径（默认最新那份）")
    p.add_argument("--by", default="heat", choices=sorted(SORT_KEYS),
                   help="排序口径（默认 heat）")
    p.add_argument("--top", type=int, default=1, help="拆前几条（默认 1）")
    p.set_defaults(fn=cmd_breakdown)

    p = sub.add_parser("clone", help="仿写：标题 + 口播钩子 + 分镜骨架（免费）",
                       allow_abbrev=False)
    p.add_argument("--snapshot", help="快照路径（默认最新那份）")
    p.add_argument("--by", default="heat", choices=sorted(SORT_KEYS),
                   help="参照哪条（默认热度第 1）")
    p.add_argument("--count", type=int, default=3, help="几条标题（默认 3，最多 3）")
    p.set_defaults(fn=cmd_clone)

    p = sub.add_parser("cover", help="出图方案：3 条封面 prompt + 单价（免费）",
                       allow_abbrev=False)
    p.add_argument("--snapshot", help="快照路径（默认最新那份）")
    p.add_argument("--by", default="heat", choices=sorted(SORT_KEYS),
                   help="参照哪条（默认热度第 1）")
    p.set_defaults(fn=cmd_cover)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近几条（默认 20）")
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("hunt", help="搜索 + 当场拆结构（1 次调用办完整条链，100 点）",
                       allow_abbrev=False)
    p.add_argument("--platform", default="dy", choices=["dy", "xhs"],
                   help="dy = 抖音搜索 / xhs = 小红书搜索（默认 dy）")
    p.add_argument("--keyword", required=True, help="搜索关键词")
    p.add_argument("--page", default=None, help="页码（小红书用）")
    p.add_argument("--sort", default=None,
                   help="排序（只小红书写）：general / popularity_descending / "
                        "time_descending / comment_descending / collect_descending")
    p.add_argument("--note-type", dest="noteType", default=None,
                   help="笔记类型（只小红书写）：_0 通用 / _1 视频 / _2 图文")
    p.add_argument("--top", type=int, default=3, help="拆前几条（默认 3）")
    p.add_argument("--by", default="heat", choices=sorted(SORT_KEYS),
                   help="排序口径（默认 heat）")
    p.add_argument("--count", type=int, default=3, help="仿写几条标题（默认 3）")
    p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数（默认 120）")
    p.add_argument("--yes", action="store_true", help="确认真实调用并扣点")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_hunt)

    for code in ORDER:
        m = APIS[code]
        p = sub.add_parser(m["cmd"],
                           help="%s —— %s（%d 点/次）" % (m["name"], m["desc"],
                                                         POINTS_PER_CALL),
                           allow_abbrev=False)
        for dest, flag, typ, req, h in m["args"]:
            kw = dict(dest=dest, required=req, help=h)
            if typ is not str:
                kw["type"] = typ
            p.add_argument(flag, **kw)
        p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数（默认 120）")
        p.add_argument("--yes", action="store_true", help="确认真实调用并扣点")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.set_defaults(fn=_make_cmd(code))

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            if _n in _sp._option_string_actions:
                continue
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


def _make_cmd(code):
    def _run(a, key, host):
        res = do_call(a, key, host, code)
        if a.dry_run:
            return res
        return _print_collect(a, res)
    _run.__name__ = "cmd_" + APIS[code]["cmd"].replace("-", "_")
    return _run


# 纯本地、不需要 Key 的子命令
FREE = ("cmd_catalog", "cmd_cost", "cmd_rank", "cmd_breakdown", "cmd_clone",
        "cmd_cover", "cmd_log")


def main(argv):
    ap = _parser()
    want_json = "--json" in argv
    try:
        a = ap.parse_args(argv)
    except CliError as e:
        msg = "%s（`run.py --help` 有全部参数）" % e
        if want_json:
            print(json.dumps({"ok": False, "exit": EXIT_USAGE,
                              "error": {"kind": "usage", "message": msg}},
                             ensure_ascii=False))
        else:
            say("用法错误：%s" % msg)
        return EXIT_USAGE
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    fn_name = getattr(a.fn, "__name__", "")
    try:
        key, host = load_conf(a.key, a.host)
        if not key and fn_name not in FREE and not getattr(a, "dry_run", False):
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
    except Exception:                                        # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
