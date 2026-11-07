#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 对账台（sanjianke-billing）

「跑了 100 次调用，账户少了 300 块 —— 到底花在哪了？」

网关其实把账都记好了，只是没有一个包把它读出来、算清、摆成表。
本包只用 **7 个只读 GET**，把 a7w 的账摊开：

  GET /api/v1/me/tasks              我的任务（带 path / actualPrice / refundedPoints / netPoints）
  GET /api/v1/tasks                 全量任务台账（27218 条，per_page 最大 100，status 可筛）
  GET /user/balance                 余额（available_points / frozen / yuan / rate=100）
  GET /user/usage?days=30           30 天汇总（calls / chargedPoints / refundedPoints / netPoints / byPath）
  GET /api/v1/me/billing            账户总账（grossChargedPoints / refundedPoints / netConsumedPoints / check）
  GET /user/balance/logs            流水（logs[] / inPoints / outPoints / balanceMoving）
  GET /api/v1/recharge/packages     充值档位 + rate=100

## 实测出来的三个「账面上的坑」（都做成了默认动作）

坑一：`/user/usage` 的 `byPath` 只回 **一个桶**
  实测 1/7/30/90/365 天全部只回 `{"(任务冻结/结算)": 420306.1851}` —— 一个中文标签，
  不是 URL 路径。所以「按路径花在哪」必须自己从 `/api/v1/me/tasks` 的 `path` 字段归集，
  本包的 `by-path` 就是干这个的，并给出 **覆盖了多少**。

坑二：`refunded` 不等于「没花钱」，`netPoints` 也不等于「标价」
  实测一个任务：actualPrice=72 / refund=122 / chargedPoints=72 / refundedPoints=72 / netPoints=0。
  真扣是 `netPoints`，标价是 `actualPrice`，`refund` 是流水里 refund 类型之和（会偏大）。
  全量实测：标价合计 1,614,513 点，真扣 104,829 点 —— 差 15 倍。

坑三：流水页的 `netPoints` 是「流水口径」，不是「净花」
  实测：logs.netPoints=-403,970（预扣+退款来回都算），logs.balanceMoving=-174,805 才是真净。
  而 `usage.netPoints` == `billing.netConsumedPoints` == `logs.balanceMoving` 三方一致，
  这才是可以用来对账的一条线。`doctor` 每次都会验这三方。

## 子命令

  overview  30 天总览（花了 / 退了 / 净花 / 日均 / 余额 / Top5 路径）
  by-path   按路径分组排序 + 中文翻译 + 占比（自己归集，附覆盖率）
  tasks     任务列表（可筛 --status failed，逐条看 actual_points）
  logs      流水明细（类型 / 点数 / 路径 / 余额）
  balance   余额 / 冻结 / 折合元 / 充值档位
  doctor    自检 7 个只读端点 + 三方口径一致性（不扣费）

## 花费

**全部只读 GET，任何子命令都是 0 点。** `--budget` 依旧生效（`--budget 0` 直接退 5，
一个请求都不发）；`--all` 这类一次连发 20 个以上请求的批量扫描要 `--yes`，确认信息里
写的是「花费 0 点」。

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py overview --days 30
  python3 scripts/run.py by-path --pages 10
  python3 scripts/run.py tasks --status failed --pages 2
  python3 scripts/run.py logs --limit 30
  python3 scripts/run.py balance

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

技术支持见 SKILL.md 的「联系我们」。
"""
import argparse
import datetime
import json
import os
import sys
import time
import unicodedata
import urllib.error
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
PAGE_SIZE_ME = 20          # /api/v1/me/tasks 每页固定 20，size/per_page 无效
PAGE_SIZE_TASKS = 100      # /api/v1/tasks per_page 上限 100（传 200 会被夹到 100）
LOGS_MAX = 1000            # /user/balance/logs 的 limit 上限，传 20000 也只回 1000
ALL_PAGES_EST = 70         # --all 的估算页数（台账实测 1389 条 ÷ 20）
DEFAULT_BUDGET = 50

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-billing/%s" % VERSION


# ───────────────────────── 路径翻译表（本包的核心价值） ─────────────────────────
# 键是接口路径，值是「人话」。实测 1389 条任务里出现过 32 个真实路径，全部收录。
PATH_NAMES = {
    # 数字人 / 对口型
    "/api/v1/apps/pic_lipsync/submit": "图片对口型（照片开口说话）",
    "/api/v1/apps/lipsync/submit": "视频对口型（换成别人的嘴型）",
    "/api/v1/apps/image_human/submit": "图片数字人（照片生成数字人）",
    "/api/v1/apps/smart_clip/realman_broadcast": "真人播报（数字人口播成片）",
    "/api/v1/apps/smart_clip/broadcast_mixcut": "播报混剪",
    "/api/v1/apps/smart_clip/news_mixcut": "新闻混剪",
    "/api/v1/apps/smart_clip/template": "混剪模板（多为探测，0 点）",
    # 语音
    "/api/v1/apps/voice_tts/tts_async": "语音合成·长文本（异步）",
    "/api/v1/apps/voice_tts/tts_live": "语音合成·实时（流式）",
    "/api/v1/apps/voice_tts/clone_voice": "音色克隆",
    "/api/v1/apps/voice_tts/list_voices": "音色列表（多为探测，0 点）",
    "/api/v1/apps/indextts/submit": "IndexTTS 配音",
    "/api/v1/apps/mmaudio/submit": "MMAudio 自动配音",
    # 图片
    "/api/v1/apps/nano_banana/submit": "nano-banana 出图",
    "/api/v1/apps/nano_banana/query": "nano-banana 查结果",
    "/api/v1/apps/aigc_photo_restore/generate/index": "老照片修复",
    "/api/v1/apps/aigc_wan_image/generate/index": "万相出图",
    "/api/v1/apps/aigc_qwen_image_pro/generate/index": "通义万相出图 Pro",
    "/api/v1/apps/dressing_diffusion/submit": "AI 换装",
    "/api/v1/images/generations": "文生图（Images API）",
    "/api/v1/images/edits": "图生图 / 改图",
    # 视频
    "/api/v1/apps/full_video/submit": "一键成片（全流程）",
    "/api/v1/apps/wan/create": "通义万相·视频创作",
    "/api/v1/apps/seedance/create": "豆包 Seedance·视频创作",
    "/api/v1/apps/grok_video/submit": "Grok 视频生成",
    "/api/v1/apps/happy_horse/submit": "快乐马视频",
    "/api/v1/apps/action_transfer/submit": "动作迁移（把 A 的动作搬到 B）",
    "/api/v1/apps/person_replacement/submit": "人物替换（换人 / 换脸）",
    "/api/v1/apps/flashvsr/submit": "FlashVSR 视频超分",
    "/api/v1/videos": "视频任务（参考图生视频）",
    "/api/v1/videos/generations": "视频生成·多模态（万相 / 豆包）",
    "/api/v1/video/generations": "视频生成（通用）",
    "/api/v1/video/upscale": "视频放大",
    "/api/v1/video/tencent4k": "腾讯 4K 超分",
    "/api/v1/video/viapi/superres": "视频超分·标准",
    "/api/v1/video/viapi/colorize": "视频上色",
    # 音频 / 其他
    "/api/v1/apps/music_generation/create": "AI 音乐生成",
    "/api/v1/apps/file_qa/parse": "文档解析问答",
    "/api/v1/tasks": "通用任务入口（文生图 / 图片编辑）",
    "/api/v1/chat/completions": "大模型对话",
    "/api/v1/embeddings": "向量化",
    # 少了 /api 前缀的老调用 —— 网关照样记账，本包照样翻得出来
    "/v1/videos": "视频任务（少了 /api 前缀）",
    "/v1/images/generations": "文生图（少了 /api 前缀）",
}

# 路径没收录时按前缀兜底，取不到精确名也不至于显示一串英文
PATH_PREFIX = (
    ("/api/v1/apps/media_services_33/", "音乐工作台（33 号应用）"),
    ("/api/v1/apps/nano_banana/", "nano-banana 出图"),
    ("/api/v1/apps/smart_clip/", "智能剪辑"),
    ("/api/v1/apps/voice_tts/", "语音合成"),
    ("/api/v1/apps/aigc_", "AIGC 应用"),
    ("/api/v1/apps/", "应用"),
    ("/api/v1/videos/", "视频生成"),
    ("/api/v1/videos", "视频任务"),
    ("/api/v1/video/", "视频处理"),
    ("/api/v1/images/", "图片生成"),
    ("/api/v1/chat/", "大模型对话"),
    ("/api/v1/", "网关接口"),
)


def path_name(p):
    """把接口路径翻成人话。"""
    if not p:
        return "（无路径）"
    if p in PATH_NAMES:
        return PATH_NAMES[p]
    for pre, name in PATH_PREFIX:
        if p.startswith(pre):
            tail = p[len(pre):].strip("/")
            return "%s · %s" % (name, tail) if tail else name
    return "其他路径"


def _w(s):
    """显示宽度：中日韩字符算 2 列，表格才对得齐。"""
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
        return "{:,}".format(int(float(v)))
    except Exception:                                            # noqa: BLE001
        return dash


def ts(ms):
    """毫秒时间戳 → 本地时间字符串。"""
    try:
        return datetime.datetime.fromtimestamp(float(ms) / 1000.0).strftime("%m-%d %H:%M:%S")
    except Exception:                                            # noqa: BLE001
        return "-"


def bar(share, width=10):
    n = int(round(share / 100.0 * width))
    return "█" * max(0, min(width, n))


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
        except Exception:                                        # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, timeout=60):
    """本包只发 GET —— 没有任何写接口，所以不可能扣点。

    长时间翻页时网关偶尔会掐连接（WinError 10054 / RemoteDisconnected），
    所以这里带 3 次重试，退避 0.5s / 1.2s。重试的也全是 GET，仍然 0 点。
    """
    last = None
    for attempt in range(3):
        req = urllib.request.Request(url, method=method, headers={
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
    return (txt or "").replace("\n", " ")[:200]


def get_json(key, host, path, what):
    """一次只读 GET，返回 dict。失败抛 Fail（kind=call）。"""
    st, txt = http_json("GET", host + path, key)
    d = jloads(txt)
    if st != 200 or not isinstance(d, (dict, list)):
        raise Fail("call", "%s 拉取失败（HTTP %s）：%s" % (what, st, err_text(st, txt)), EXIT_CALL)
    return d


def _gate(a, requests, what="本次"):
    """两道闸门。本包全是只读 GET，预计花费恒为 0 点。"""
    cost = 0
    if requests > 0 and a.budget <= 0:
        raise Fail("budget",
                   "--budget 是 %d 点（单位：点）。本包每个请求 0 点，但 0 点预算等于"
                   "不授权任何调用；给 1 点以上就放行。" % a.budget, EXIT_BUDGET)
    if cost > a.budget:
        raise Fail("budget", "预计 %d 点超过 --budget %d 点，一个请求都没发。"
                   % (cost, a.budget), EXIT_BUDGET)
    if cost > 0 and not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实扣费约 %d 点（%.2f 元）。确认请加 --yes。"
                   % (cost, cost / 100.0), EXIT_CONFIRM)
    if requests >= 30 and not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "%s要连发 %d 个只读请求（花费 **0 点**，不会扣款）。确认请加 --yes。"
                   % (what, requests), EXIT_CONFIRM)


def _plan(a, reqs, lines):
    """--dry-run：打印将要发出的请求，一个都不发。"""
    out = {"ok": True, "dryRun": True, "requests": lines,
           "requestCount": reqs, "estimatedPoints": 0, "yuan": 0.0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不扣费）")
    print("  请求数：%d" % reqs)
    print("  预估：0 点（¥0.00）—— 全部是只读 GET")
    for ln in lines:
        print("  → %s" % ln)
    return 0


# ───────────────────────── 数据拉取 ─────────────────────────
def me_tasks_page(key, host, page):
    return get_json(key, host, API_PREFIX + "/me/tasks?limit=2000&page=%d" % page, "我的任务")


def collect_me_tasks(a, key, host, pages):
    """翻 /api/v1/me/tasks。

    实测：size / per_page 无效，每页恒 20 条；`limit` 是「统计最近 N 条」的窗口，
    默认 1000，给 2000 才能覆盖账户全部 1389 条。所以统一带 limit=2000 翻页。
    """
    tasks, seen, total = [], set(), None
    for pg in range(1, pages + 1):
        d = me_tasks_page(key, host, pg)
        total = d.get("total") if total is None else total
        tl = d.get("tasks") or []
        if not tl:
            break
        new = 0
        for t in tl:
            tid = t.get("taskId")
            if tid in seen:
                continue
            seen.add(tid)
            tasks.append(t)
            new += 1
        if new == 0 or len(tl) < PAGE_SIZE_ME:
            break
    return tasks, total


def path_rows(tasks):
    """把任务列表按 path 归集。

    占比的分母是「支出方向的净额之和」（只看 net>0 的行）—— 因为异步任务跨期结算
    会产生负 net（退回多于本期新增），拿它当分母会把占比算成 76% + 64% 这种怪数。
    """
    agg = {}
    for t in tasks:
        k = t.get("path") or ""
        a = agg.setdefault(k, {"path": k, "name": path_name(k), "count": 0,
                               "net": 0.0, "actual": 0.0, "refunded": 0.0})
        a["count"] += 1
        a["net"] += float(t.get("netPoints") or 0)
        a["actual"] += float(t.get("actualPrice") or 0)
        a["refunded"] += float(t.get("refundedPoints") or 0)
    rows = sorted(agg.values(), key=lambda r: -r["net"])
    tot = sum(r["net"] for r in rows)
    denom = sum(r["net"] for r in rows if r["net"] > 0)
    for r in rows:
        r["share"] = round((r["net"] / denom * 100.0) if denom else 0.0, 2)
        r["net"] = round(r["net"], 2)
        r["actual"] = round(r["actual"], 2)
        r["refunded"] = round(r["refunded"], 2)
    return rows, round(tot, 2)


def authoritative(key, host, days):
    """三方权威口径：usage / billing / 流水 balanceMoving。"""
    us = get_json(key, host, "/user/usage?days=%d" % days, "用量汇总")
    bl = get_json(key, host, API_PREFIX + "/me/billing", "账户总账")
    lg = get_json(key, host, "/user/balance/logs?limit=1", "余额流水")
    return us, bl, lg


# ───────────────────────── 子命令 ─────────────────────────
def cmd_doctor(a, key, host):
    _gate(a, 9)
    if a.dry_run:
        return _plan(a, 9, ["GET /api/v1/me/tasks",
                            "GET /api/v1/tasks?per_page=1",
                            "GET /user/balance",
                            "GET /user/usage?days=30",
                            "GET /api/v1/me/billing",
                            "GET /user/balance/logs?limit=1",
                            "GET /api/v1/recharge/packages",
                            "GET /user/usage（复采一次做三方比对）",
                            "GET /api/v1/me/billing（复采一次做三方比对）"])
    checks = []

    def probe(name, path, want, detail):
        try:
            d = get_json(key, host, path, name)
        except Fail as e:
            checks.append((name, False, e.message[:70]))
            return None
        ok = want(d)
        checks.append((name, ok, detail(d) if ok else "返回里没有预期字段"))
        return d

    def _dig(d, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    probe("我的任务 /api/v1/me/tasks", API_PREFIX + "/me/tasks?limit=2000",
          lambda d: isinstance(d.get("tasks"), list),
          lambda d: "台账 %s 条" % d.get("total"))
    probe("全量任务 /api/v1/tasks", API_PREFIX + "/tasks?per_page=1",
          lambda d: isinstance(_dig(d, "data", "lists"), list),
          lambda d: "全账 %s 条" % _dig(d, "data", "total"))
    probe("余额 /user/balance", "/user/balance",
          lambda d: "available_points" in d,
          lambda d: "可用 %s 点 · 冻结 %s" % (pint(d.get("available_points")), pint(d.get("frozen"))))
    probe("用量 /user/usage", "/user/usage?days=30",
          lambda d: "netPoints" in d,
          lambda d: "30 天净花 %s 点" % pnum(d.get("netPoints")))
    probe("总账 /api/v1/me/billing", API_PREFIX + "/me/billing",
          lambda d: "netConsumedPoints" in d,
          lambda d: "全量净消费 %s 点" % pnum(d.get("netConsumedPoints")))
    probe("流水 /user/balance/logs", "/user/balance/logs?limit=1",
          lambda d: isinstance(d.get("logs"), list),
          lambda d: "共 %s 条流水" % pint(d.get("total")))
    probe("充值档位 /api/v1/recharge/packages", API_PREFIX + "/recharge/packages",
          lambda d: isinstance(d.get("packages"), list) and d.get("rate"),
          lambda d: "%d 档 · rate=%s" % (len(d.get("packages") or []), d.get("rate")))

    # 三方口径一致性：usage / billing / 流水 balanceMoving
    try:
        us, bl, lg = authoritative(key, host, 30)
        u = float(us.get("netPoints") or 0)
        b = float(bl.get("netConsumedPoints") or 0)
        m = abs(float(lg.get("balanceMoving") or 0))
        spread = max(u, b, m) - min(u, b, m)
        tol = max(2.0, max(u, b, m) * 0.01)
        checks.append(("三方口径一致（usage = billing = 流水）", spread <= tol,
                       "usage %s / billing %s / 流水 %s，最大差 %s 点"
                       % (pnum(u), pnum(b), pnum(m), pnum(spread))))
    except Fail as e:
        checks.append(("三方口径一致（usage = billing = 流水）", False, e.message[:70]))

    out = {"ok": all(c[1] for c in checks),
           "estimatedPoints": 0, "yuan": 0.0,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（全部只读 GET，扣 0 点）")
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 40), d))
    print()
    print("  7 个端点全部只读，本轮花费 **0 点**。")
    return 0 if out["ok"] else EXIT_GATE


def cmd_overview(a, key, host):
    pages = 200 if a.all else a.pages          # 循环硬上限
    est = ALL_PAGES_EST if a.all else a.pages  # 闸门与干跑的估算
    reqs = 4 + est
    _gate(a, reqs)
    if a.dry_run:
        return _plan(a, reqs, [
            "GET /user/usage?days=%d" % a.days,
            "GET /user/balance",
            "GET %s/me/billing" % API_PREFIX,
            "GET /user/balance/logs?limit=1",
        ] + ["GET %s/me/tasks?limit=2000&page=%d" % (API_PREFIX, i) for i in range(1, est + 1)])

    us, bl, lg = authoritative(key, host, a.days)
    bal = get_json(key, host, "/user/balance", "余额")

    charged = float(us.get("chargedPoints") or 0)
    refunded = float(us.get("refundedPoints") or 0)
    net = float(us.get("netPoints") or 0)
    calls = us.get("calls") or 0
    days = us.get("days") or a.days

    tasks, total = ([], None)
    if pages:
        tasks, total = collect_me_tasks(a, key, host, pages)
    rows, tnet = path_rows(tasks)
    top = [r for r in rows if r["net"] > 0][:a.top]
    spend = round(sum(r["net"] for r in rows if r["net"] > 0), 2)

    out = {"ok": True, "window": {"days": days, "calls": calls,
                                  "chargedPoints": round(charged, 2),
                                  "refundedPoints": round(refunded, 2),
                                  "netPoints": round(net, 2),
                                  "yuan": round(net / 100.0, 2),
                                  "perDayPoints": round(net / days, 2) if days else 0,
                                  "byPath": us.get("byPath") or {}},
           "balance": {"availablePoints": bal.get("available_points"),
                       "frozen": bal.get("frozen"),
                       "yuan": bal.get("yuan"), "rate": bal.get("rate")},
           "reconcile": {"usageNet": round(net, 2),
                         "billingNet": round(float(bl.get("netConsumedPoints") or 0), 2),
                         "ledgerNet": round(abs(float(lg.get("balanceMoving") or 0)), 2)},
           "topPaths": top,
           "coverage": {"tasksScanned": len(tasks), "taskTableTotal": total,
                        "spendInTable": spend, "netInTable": tnet,
                        "pct": round(spend / net * 100.0, 1) if net else 0},
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("对账总览 · 最近 %d 天" % days)
    print("=" * 72)
    print("  %s %s 次" % (pad("调用次数", 16), pad(pint(calls), 13, left=False)))
    print("  %s %s 点（¥%s）" % (pad("花掉 charged", 16),
                                pad(pnum(charged), 13, left=False), pnum(charged / 100.0)))
    print("  %s %s 点" % (pad("退回 refunded", 16), pad(pnum(refunded), 13, left=False)))
    print("  %s %s 点（¥%s）  ← 这才是真花"
          % (pad("净花 net", 16), pad(pnum(net), 13, left=False), pnum(net / 100.0)))
    print("  %s %s 点 / 天（¥%s）"
          % (pad("日均", 16), pad(pnum(net / days if days else 0), 13, left=False),
             pnum(net / days / 100.0 if days else 0)))
    print()
    print("余额")
    print("  可用 %s 点 · 冻结 %s 点 · 折合 ¥%s（rate=%s）"
          % (pint(bal.get("available_points")), pint(bal.get("frozen")),
             pnum(bal.get("yuan")), bal.get("rate")))
    print()
    print("对账校验（三方口径）")
    print("  usage.netPoints %s · billing.netConsumedPoints %s · 流水 balanceMoving %s"
          % (pnum(net), pnum(bl.get("netConsumedPoints")), pnum(abs(float(lg.get("balanceMoving") or 0)))))
    print("  %s 一致" % ("√" if abs(net - abs(float(lg.get("balanceMoving") or 0))) <= max(2.0, net * 0.01) else "≈"))
    print()
    print("钱花在哪（Top %d · 按 task 台账的 path 归集，扫描 %d 条）"
          % (len(top), len(tasks)))
    print("  %s %s %s %s %s" % (pad("#", 3), pad("路径", 34), pad("次数", 6),
                                pad("净花(点)", 12), pad("占比", 8)))
    print("  " + "-" * 68)
    for i, r in enumerate(top, 1):
        print("  %s %s %s %s %s %s" % (pad(i, 3), pad(r["name"], 34), pad(r["count"], 6),
                                       pad(pnum(r["net"]), 12), pad("%.2f%%" % r["share"], 8),
                                       bar(r["share"])))
    print()
    if net:
        print("  这 %d 条里支出方向合计 %s 点 = 权威净花的 %.1f%%"
              % (len(tasks), pnum(spend), spend / net * 100.0))
        print("  （byPath 只回 1 个桶「%s」，所以这张表是本包自己按 path 归集出来的）"
              % next(iter((us.get("byPath") or {"-": 0}))))
    print()
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


def cmd_by_path(a, key, host):
    pages = 200 if a.all else a.pages
    est = ALL_PAGES_EST if a.all else a.pages
    _gate(a, est + 1)
    if a.dry_run:
        return _plan(a, est + 1,
                     ["GET %s/me/tasks?limit=2000&page=%d" % (API_PREFIX, i) for i in range(1, est + 1)]
                     + ["GET /user/usage?days=%d" % a.days])
    if pages > 10:
        say("正在翻任务台账（最多 %d 页 × 20 条）…" % est)
    tasks, total = collect_me_tasks(a, key, host, pages)
    if not tasks:
        raise Fail("call", "一条任务都没拿到，先跑 doctor 看看 Key 和端点。", EXIT_CALL)
    us = get_json(key, host, "/user/usage?days=%d" % a.days, "用量汇总")
    net = float(us.get("netPoints") or 0)
    rows, tnet = path_rows(tasks)
    shown = rows[:a.top]
    actual_all = round(sum(r["actual"] for r in rows), 2)
    refunded_all = round(sum(r["refunded"] for r in rows), 2)
    spend = round(sum(r["net"] for r in rows if r["net"] > 0), 2)

    out = {"ok": True, "days": a.days, "tasksScanned": len(tasks),
           "taskTableTotal": total, "paths": shown, "pathCount": len(rows),
           "netInTable": tnet, "spendInTable": spend, "actualInTable": actual_all,
           "refundedInTable": refunded_all,
           "authoritativeNet": round(net, 2),
           "coveragePct": round(spend / net * 100.0, 1) if net else 0,
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("按路径对账 · 扫描 %d 条任务（台账共 %s 条，%d 个路径）"
          % (len(tasks), pint(total), len(rows)))
    print("=" * 92)
    print("  %s %s %s %s %s %s %s" % (pad("#", 3), pad("路径（人话）", 30), pad("接口路径", 34),
                                      pad("次数", 5), pad("净花", 11), pad("已退", 10), pad("占比", 7)))
    print("  " + "-" * 88)
    for i, r in enumerate(shown, 1):
        print("  %s %s %s %s %s %s %s"
              % (pad(i, 3), pad(r["name"], 30), pad(r["path"][:33] or "-", 34),
                 pad(r["count"], 5), pad(pnum(r["net"]), 11), pad(pnum(r["refunded"]), 10),
                 pad("%.2f%%" % r["share"], 7)))
    print()
    print("  合计（全部 %d 个路径）：净花 %s 点 / 标价 %s 点 / 已退 %s 点"
          % (len(rows), pnum(tnet), pnum(actual_all), pnum(refunded_all)))
    print("  占比分母 = 支出方向净额之和；负值行是异步任务跨期结算的冲回。")
    print("  支出方向合计 %s 点 ÷ 权威净花 %s 点 = 覆盖 %.1f%%"
          % (pnum(spend), pnum(net), (spend / net * 100.0) if net else 0))
    if a.all or len(tasks) >= (total or 0):
        print("  已扫完全部 %s 条任务台账；剩下的 %.1f%% 是台账之外的调用（直连接口 / 更早的调用）。"
              % (pint(total), max(0.0, 100.0 - (spend / net * 100.0 if net else 0))))
    else:
        print("  台账共 %s 条，本次扫了 %d 条；加 `--all --yes` 可以把 1389 条全扫一遍（仍然 0 点）。"
              % (pint(total), len(tasks)))
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


def cmd_tasks(a, key, host):
    _gate(a, a.pages + 1)
    q = "%s/tasks?per_page=%d" % (API_PREFIX, min(a.per_page, PAGE_SIZE_TASKS))
    if a.status:
        q += "&status=" + a.status
    if a.dry_run:
        return _plan(a, a.pages + 1,
                     ["GET %s&page=%d" % (q, i) for i in range(1, a.pages + 1)])
    items, total = [], None
    for pg in range(1, a.pages + 1):
        d = get_json(key, host, "%s&page=%d" % (q, pg), "任务台账")
        data = d.get("data") or {}
        total = data.get("total") if total is None else total
        ls = data.get("lists") or []
        if not ls:
            break
        items += ls
        if len(ls) < min(a.per_page, PAGE_SIZE_TASKS):
            break

    def f(it):
        return {"taskId": it.get("task_id"), "model": it.get("model_code"),
                "status": it.get("status"), "points": float(it.get("actual_points") or 0),
                "channel": it.get("channel_code"), "type": it.get("type_code"),
                "createdAt": it.get("created_at"),
                "completedAt": ts(it.get("completed_at") * 1000) if it.get("completed_at") else ""}

    rows = [f(it) for it in items]
    bad = [r for r in rows if (r["status"] or "") != "completed"]
    out = {"ok": True, "count": len(rows), "tableTotal": total,
           "statusFilter": a.status, "items": rows,
           "summary": {"notCompleted": len(bad),
                       "pointsOnNotCompleted": round(sum(r["points"] for r in bad), 2),
                       "pointsOnAll": round(sum(r["points"] for r in rows), 2)},
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("任务台账 · 本次 %d 条（全账 %s 条）%s"
          % (len(rows), pint(total), (" · status=%s" % a.status) if a.status else ""))
    print("=" * 96)
    print("  %s %s %s %s %s %s" % (pad("创建时间", 20), pad("模型", 30), pad("状态", 11),
                                   pad("点数", 10), pad("渠道", 9), "任务号"))
    print("  " + "-" * 92)
    for r in rows:
        print("  %s %s %s %s %s %s"
              % (pad(r["createdAt"] or "-", 20), pad((r["model"] or "-")[:29], 30),
                 pad(r["status"] or "-", 11), pad(pnum(r["points"]), 10),
                 pad(r["channel"] or "-", 9), r["taskId"]))
    print()
    print("  未完成（status≠completed）%d 条，合计 %s 点 —— 失败任务 actual_points 实测为 0.00，钱没扣。"
          % (len(bad), pnum(sum(r["points"] for r in bad))))
    print("  本页合计 %s 点。本轮花费 0 点（全部只读 GET）。" % pnum(sum(r["points"] for r in rows)))
    return 0

def cmd_logs(a, key, host):
    _gate(a, 1)
    lim = max(1, min(a.limit, LOGS_MAX))
    if a.dry_run:
        return _plan(a, 1, ["GET /user/balance/logs?limit=%d" % lim])
    d = get_json(key, host, "/user/balance/logs?limit=%d" % lim, "余额流水")
    lg = d.get("logs") or []
    entries = []
    for it in lg:
        ref = it.get("reference") or ""
        p = it.get("path") or ""
        if not p and ":" in ref:
            cand = ref.split(":")
            for c in cand:
                if c.startswith("/"):
                    p = c
                    break
        entries.append({"at": it.get("at"), "time": ts(it.get("at")),
                        "type": it.get("type"), "typeName": it.get("typeName"),
                        "kind": it.get("kind"), "points": float(it.get("points") or 0),
                        "balanceAfter": it.get("balanceAfter"),
                        "path": p, "pathName": path_name(p) if p else "（流水未记路径）",
                        "reference": ref, "isSettle": it.get("isSettle")})
    inn = sum(e["points"] for e in entries if e["points"] > 0)
    outt = sum(-e["points"] for e in entries if e["points"] < 0)
    out = {"ok": True, "count": len(entries), "tableTotal": d.get("total"),
           "currency": d.get("currency"), "rate": d.get("rate"),
           "inPoints": d.get("inPoints"), "outPoints": d.get("outPoints"),
           "flowNetPoints": d.get("netPoints"),
           "balanceMoving": d.get("balanceMoving"),
           "consumePoints": d.get("consumePoints"),
           "entries": entries,
           "thisPage": {"in": round(inn, 2), "out": round(outt, 2),
                        "net": round(inn - outt, 2)},
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("余额流水 · 本次 %d 条 / 全账 %s 条（limit 上限 %d）"
          % (len(entries), pint(d.get("total")), LOGS_MAX))
    print("=" * 100)
    print("  %s %s %s %s %s" % (pad("时间", 15), pad("类型", 14), pad("点数", 11),
                                pad("路径", 30), "余额"))
    print("  " + "-" * 96)
    for e in entries:
        print("  %s %s %s %s %s"
              % (pad(e["time"], 15), pad(e["typeName"] or e["type"] or "-", 14),
                 pad(("+" if e["points"] > 0 else "") + pnum(e["points"]), 11),
                 pad(e["pathName"][:29], 30), pnum(e["balanceAfter"])))
    print()
    print("  本页：入 %s 点 / 出 %s 点 / 净 %s 点"
          % (pnum(inn), pnum(outt), pnum(inn - outt)))
    print("  全账口径：入 %s / 出 %s" % (pnum(d.get("inPoints")), pnum(d.get("outPoints"))))
    print("  流水 netPoints = %s（预扣 + 退款来回都算，会偏大）" % pnum(d.get("netPoints")))
    print("  balanceMoving = %s（真实净变动，和 /user/usage 的 netPoints 对得上）"
          % pnum(d.get("balanceMoving")))
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


def cmd_balance(a, key, host):
    _gate(a, 3)
    if a.dry_run:
        return _plan(a, 3, ["GET /user/balance", "GET %s/me/billing" % API_PREFIX,
                            "GET %s/recharge/packages" % API_PREFIX])
    bal = get_json(key, host, "/user/balance", "余额")
    bl = get_json(key, host, API_PREFIX + "/me/billing", "账户总账")
    pk = get_json(key, host, API_PREFIX + "/recharge/packages", "充值档位")
    packs = []
    for p in (pk.get("packages") or []):
        yuan = float(p.get("yuan") or 0)
        pts = float(p.get("points") or 0) + float(p.get("bonus") or 0)
        packs.append({"id": p.get("id"), "yuan": yuan, "points": p.get("points"),
                      "bonus": p.get("bonus"), "tag": p.get("tag"),
                      "pointsPerYuan": round(pts / yuan, 2) if yuan else 0})
    out = {"ok": True,
           "balance": {"availablePoints": bal.get("available_points"),
                       "frozen": bal.get("frozen"), "yuan": bal.get("yuan"),
                       "rate": bal.get("rate"), "currency": bal.get("currency")},
           "account": {"phone": bl.get("phone"), "userId": bl.get("userId"),
                       "rechargeYuan": bl.get("rechargeYuan"),
                       "rechargePoints": bl.get("rechargePoints"),
                       "creditPoints": bl.get("creditPoints"),
                       "grossChargedPoints": bl.get("grossChargedPoints"),
                       "refundedPoints": bl.get("refundedPoints"),
                       "netConsumedPoints": bl.get("netConsumedPoints"),
                       "netConsumedYuan": bl.get("netConsumedYuan"),
                       "paidOrders": bl.get("paidOrders"),
                       "check": bl.get("check"), "note": bl.get("note")},
           "packages": packs, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("余额")
    print("=" * 66)
    print("  %s %s 点" % (pad("可用（available）", 22), pint(bal.get("available_points"))))
    print("  %s %s 点" % (pad("冻结（frozen）", 22), pint(bal.get("frozen"))))
    print("  %s ¥%s（rate=%s，1 元 = %s 点）"
          % (pad("折合", 22), pnum(bal.get("yuan")), bal.get("rate"), bal.get("rate")))
    print()
    print("账户")
    print("  %s %s" % (pad("手机号", 22), bl.get("phone") or "-"))
    print("  %s %s" % (pad("累计充值", 22), "¥%s（%s 点）"
                        % (pnum(bl.get("rechargeYuan")), pint(bl.get("rechargePoints")))))
    print("  %s %s 点" % (pad("赠送（credit）", 22), pint(bl.get("creditPoints"))))
    print("  %s %s 点" % (pad("全量花费", 22), pnum(bl.get("grossChargedPoints"))))
    print("  %s %s 点" % (pad("全量退回", 22), pnum(bl.get("refundedPoints"))))
    print("  %s %s 点（¥%s）" % (pad("全量净消费", 22), pnum(bl.get("netConsumedPoints")),
                                 pnum(bl.get("netConsumedYuan"))))
    print()
    chk = bl.get("check") or {}
    print("  验算：%s" % (bl.get("note") or "-"))
    print("    expected %s · actual %s · diff %s"
          % (pnum(chk.get("expected")), pnum(chk.get("actual")), pnum(chk.get("diff"))))
    print("    diff = 充值 + 赠送 之外的额度（活动赠送 / 测试额度 / 历史手工调整），")
    print("    expected 只按「充值到手 − 净消费」算，所以有额外额度时 diff 必然不为 0。")
    print()
    print("充值档位")
    print("  %s %s %s %s %s" % (pad("档位", 10), pad("价格", 10), pad("点数", 10),
                                pad("赠送", 8), "点/元"))
    print("  " + "-" * 50)
    for p in packs:
        print("  %s %s %s %s %s"
              % (pad(p["tag"] or p["id"], 10), pad("¥" + pnum(p["yuan"]), 10),
                 pad(pint(p["points"]), 10), pad(pint(p["bonus"]), 8),
                 "%.2f" % p["pointsPerYuan"]))
    print()
    print("  本轮花费 0 点（全部只读 GET）。")
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 对账台：我的钱到底花在哪（7 个只读端点，0 点花费）",
        epilog="端点：GET %s/api/v1/me/tasks · GET %s/api/v1/tasks · GET %s/user/balance · "
               "GET %s/user/usage?days=30 · GET %s/api/v1/me/billing · "
               "GET %s/user/balance/logs · GET %s/api/v1/recharge/packages"
               % ((DEFAULT_HOST,) * 7),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d；本包每个请求 0 点，给 0 会直接退 5）"
                         % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("overview", help="30 天总览：花了 / 退了 / 净花 / 日均 / 余额（免费）",
                       allow_abbrev=False)
    p.add_argument("--days", type=int, default=30, help="统计窗口天数（默认 30）")
    p.add_argument("--pages", type=int, default=20, help="为 Top5 翻几页任务台账（每页 20 条，默认 20）")
    p.add_argument("--all", action="store_true", help="翻完全部任务台账（约 70 个请求，要 --yes）")
    p.add_argument("--top", type=int, default=5, help="Top N 路径（默认 5）")
    p.add_argument("--yes", action="store_true", help="确认大批量只读扫描")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_overview)

    p = sub.add_parser("by-path", help="按路径分组 + 中文翻译 + 占比（本包核心）",
                       allow_abbrev=False)
    p.add_argument("--days", type=int, default=30, help="和 /user/usage 对账用的窗口（默认 30）")
    p.add_argument("--pages", type=int, default=25, help="翻几页任务台账（每页 20 条，默认 25 = 500 条）")
    p.add_argument("--all", action="store_true", help="翻完全部任务台账（约 70 个请求，要 --yes）")
    p.add_argument("--top", type=int, default=25, help="显示前 N 个路径（默认 25）")
    p.add_argument("--yes", action="store_true", help="确认大批量只读扫描")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_by_path)

    p = sub.add_parser("tasks", help="任务列表（--status failed 逐条对账）", allow_abbrev=False)
    p.add_argument("--status", default=None,
                   help="筛状态：completed / failed / cancelled（不传则不筛）")
    p.add_argument("--per-page", type=int, default=50, help="每页条数，上限 100（默认 50）")
    p.add_argument("--pages", type=int, default=1, help="翻几页（默认 1）")
    p.add_argument("--yes", action="store_true", help="确认大批量只读扫描")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_tasks)

    p = sub.add_parser("logs", help="流水明细（类型 / 点数 / 路径 / 余额）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="取最近多少条，上限 1000（默认 20）")
    p.add_argument("--yes", action="store_true", help="确认大批量只读扫描")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_logs)

    p = sub.add_parser("balance", help="余额 / 冻结 / 折合元 / 充值档位", allow_abbrev=False)
    p.add_argument("--yes", action="store_true", help="确认")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_balance)

    p = sub.add_parser("doctor", help="自检 7 个只读端点 + 三方口径（不扣费）", allow_abbrev=False)
    p.add_argument("--yes", action="store_true", help="确认")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
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
    # 子命令上重复定义的全局选项，default=SUPPRESS，没写就不会覆盖父级的值
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
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
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
