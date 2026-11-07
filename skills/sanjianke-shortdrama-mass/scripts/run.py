#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 短剧量产台（sanjianke-shortdrama-mass）

一个短剧团队「一天 10 条日更」的排产台：选题 -> 脚本 -> 配音 -> 数字人口播
-> 配乐 -> 卡点字幕 -> 封面 -> 分发交付，8 个工位一条排产单管到底。

## 这个包不新增接口，它把 4 条已有能力线按「日更流水线」重新组织

  voice_tts/tts_async              旁白配音（长文本异步）
  pic_lipsync/submit (mode=text)   数字人口播（图 + 文案 + 参考音色）
  media_services_33/music_generate 配乐
  media_services_33/music_timestamped_lyrics  卡点字幕（带时间戳的歌词）
  full_video/submit                封面片头 / 预告片（一键成片，按分辨率单独定价）

## 价目（2026-11-08 现查 GET /api/v1/pricing，单位：点，1 元 = 100 点）

  full_video/submit   per_second  480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80
  voice_tts/*         markup 200  对外价 = 上游实际点数 x 3（本包按 0.18 点/字估算）
  pic_lipsync/*       markup 400  对外价 = 上游实际点数 x 5（standard 档实测 3 点/秒
                                  -> 对外 15 点/秒；minPoints 50 是声明性字段）
  media_services_33   未配价      每次调用先冻 60 点（实测 4 条流水各 60 冻 + 60 退）
  /api/v1/upload      flat 0      上传不计费

一条 45 秒 / 350 字 / 1 条配乐 / 1 条卡点、封面用本地截帧的日更条目 = 858 点。
一天 10 条 = 8,580 点 = 85.80 元。秒数是唯一的大杠杆：口播 15 点/秒占全条 79%。

## 三条实测口径（都做成了默认动作）

一、应用层 query 按次计费。nano_banana/query 实测 72 点/次，轮询一次就是一张图的钱。
   本包查任务只走免费的 GET /api/v1/tasks/<task_id>，「应用层 query 一律不碰」。

二、media_services_33 的 29 个接口一条都没配价。每次调用先冻 60 点再校验，
   实测 4 条流水（music_generate / music_extend / music_sounds /
   music_timestamped_lyrics）各冻 60、退 60。所以配乐与卡点在本包里
   按 60 点/条入账，多跑一条就是 60 点，别把它当免费接口。

三、文档写「免费」的两个口子会先冻再退：voice_tts/list_voices 每次冻 150 点
   （实测 15 条 reserve_sync 流水各 150），应用层 submit 缺参数会先 reserve_sync
   再全额退（净 0，但钱包被短暂动过）。所以 doctor 一次 list_voices 都不发，
   所有提交都先本地预检 + --dry-run。

## 闸门

  --budget 单位是「点」，默认 10000 点（100 元），超了 exit 5 且一个请求都不发；
  付费子命令缺 --yes exit 4，并直接告诉你这一趟要花多少点。

## 子命令

  catalog  8 个工位 + 4 条能力线 + 单价 + 一天 10 条的三种走法（免费）
  cost     先算钱：一条 / 一天 / 三种走法对照（免费）
  plan     出排产单：10 条 x 8 工位 + 钩子 + 分镜 + 命名 + 点数（免费，只写本地）
  doctor   自检 Key / 应用注册表 / 价目表 / 查询路由 / 上传（免费，0 点）
  upload   本地素材先传平台，拿白名单地址（免费）
  check    交付清单验收：文件齐不齐 / 命名 / 封面像素 / 体积（免费，只读本地）
  run      跑一条的一条工位或全链（要 --yes，受 --budget 管）
  batch    跑一天的多条（要 --yes，受 --budget 管）
  status   查任务（免费，只走 GET /api/v1/tasks/<id>）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --episodes 10 --seconds 45 --chars 350
  python3 scripts/run.py doctor
  python3 scripts/run.py plan --project SD --episodes 10 --outdir ./out
  python3 scripts/run.py check --dir ./out --plan ./out/plan.json
  python3 scripts/run.py run --plan ./out/plan.json --ep S01E03 --step avatar \
      --image-url https://... --voice-ref https://... --yes

Key：`--key` -> 环境变量 `A7W_API_KEY` -> `~/.a7w/config.json`。
需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。
遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import mimetypes
import os
import re
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
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "shortdrama-mass-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-shortdrama-mass/%s" % VERSION

POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 10000          # 点（100 元）

# ── 单价（GET /api/v1/pricing 现查，单位：点）──────────────────────────────
TTS_POINTS_PER_CHAR = 0.18      # voice_tts 上游 x3 之后的每字估算（200 字 = 36 点）
AVATAR_POINTS_PER_SECOND = 15   # pic_lipsync standard = 上游 3 点/秒 x5
MEDIA33_POINTS_PER_CALL = 60    # media_services_33 未配价，实测预冻 60 点/次
UPLOAD_POINTS = 0               # /api/v1/upload flat cost 0

# full_video/submit 的 resolutionRates（pricing 原文，点/秒）
FULL_VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}
VIDEO_MIN_SECONDS, VIDEO_MAX_SECONDS = 4, 15

DEFAULT_EPISODES = 10
DEFAULT_SECONDS = 45
DEFAULT_CHARS = 350
DEFAULT_COVER_SECONDS = 4

# ── 4 条能力线（端点全部实测存在）────────────────────────────────────────
VOICE_PATH = API_PREFIX + "/apps/voice_tts/tts_async"
AVATAR_PATH = API_PREFIX + "/apps/pic_lipsync/submit"
MUSIC_PATH = API_PREFIX + "/apps/media_services_33/music_generate"
BEAT_PATH = API_PREFIX + "/apps/media_services_33/music_timestamped_lyrics"
VIDEO_PATH = API_PREFIX + "/apps/full_video/submit"
UPLOAD_PATH = API_PREFIX + "/upload"
TASKS_PATH = API_PREFIX + "/tasks/"

# ── 8 个工位（行业顺序，不是接口顺序）──────────────────────────────────────
STATIONS = [
    dict(key="topic", name="选题", channel="本地", path="", unit="免费",
         per=0, hint="钩子池里挑一句，先定这一条要给谁看"),
    dict(key="script", name="脚本", channel="本地", path="", unit="免费",
         per=0, hint="按 0-3 / 3-15 / 15-30 / 30-40 / 40-45 秒分镜"),
    dict(key="voice", name="旁白配音", channel="voice_tts", path=VOICE_PATH,
         unit="点/字", per=TTS_POINTS_PER_CHAR, hint="tts_async 长文本异步，出 mp3"),
    dict(key="avatar", name="数字人口播", channel="pic_lipsync", path=AVATAR_PATH,
         unit="点/秒", per=AVATAR_POINTS_PER_SECOND, hint="mode=text，图 + 文案 + 参考音色"),
    dict(key="music", name="配乐", channel="media_services_33", path=MUSIC_PATH,
         unit="点/条", per=MEDIA33_POINTS_PER_CALL, hint="music_generate，一次一条"),
    dict(key="beat", name="卡点字幕", channel="media_services_33", path=BEAT_PATH,
         unit="点/条", per=MEDIA33_POINTS_PER_CALL, hint="timestamped_lyrics，出字级时间轴"),
    dict(key="cover", name="封面 / 片头", channel="full_video", path=VIDEO_PATH,
         unit="点/秒", per=None, hint="本地截帧 0 点；要动态片头走 full_video 4-15 秒"),
    dict(key="deliver", name="分发交付", channel="本地", path="", unit="免费",
         per=0, hint="按命名规范改名 + 过交付清单"),
]
STATION_KEYS = [s["key"] for s in STATIONS]
# --all 按这个顺序跑；封面默认本地截帧，要走 full_video 时显式 --step cover
PAID_STEPS = ["voice", "avatar", "music", "beat"]
VALID_STEPS = PAID_STEPS + ["cover"]
STATION_MAP = {s["key"]: s for s in STATIONS}

# ── 交付清单：这个行业一天/一单要交的东西（工位 / 扩展名 / 必交 / 规格 / MB 上限 / 说明）
DELIVER = [
    ("avatar", "mp4", True, "1080x1920", 200, "口播成片"),
    ("voice", "mp3", True, "", 20, "旁白音轨"),
    ("music", "mp3", True, "", 20, "配乐"),
    ("beat", "srt", True, "", 2, "卡点字幕"),
    ("cover", "jpg", True, "1080x1920", 2, "封面"),
    ("promo", "mp4", False, "1080x1920", 200, "预告片（选交）"),
]
COVER_SIZE = (1080, 1920)

# 命名规范：<项目>_S<两位季>E<两位集>_<工位>_<规格>_v<两位版本>.<扩展名>
NAME_RE = re.compile(
    r"^(?P<proj>[A-Za-z][A-Za-z0-9]{1,7})_S(?P<season>\d{2})E(?P<ep>\d{2})"
    r"_(?P<station>[a-z]+)(?:_(?P<spec>[0-9a-zA-Zx]+))?_v(?P<ver>\d{2})"
    r"\.(?P<ext>[a-z0-9]{2,4})$")

# ── 选题钩子池（行业话术，不是接口）────────────────────────────────────────
HOOKS = [
    ("身份反差", "她扫了三年地，转身在董事会上叫出了全场人的名字"),
    ("当场打脸", "签约现场被换人，她把合同翻到第 9 页，指着自己签名笑了"),
    ("二次反转", "所有人都以为她是来求情的，只有门口那辆车没熄火"),
    ("极限救场", "手术还剩 40 秒，他推开门说自己才是主刀"),
    ("隐藏身份", "外卖箱里掉出一张证件，收件人从此不敢再喊他小哥"),
    ("时间倒流", "她重生在订婚宴前一小时，这一次她先摔了杯子"),
    ("替身文学", "他找了七年的白月光，站在面前说自己只是个替身"),
    ("豪门争产", "遗嘱念到第三条，全家人的目光一起落到她身上"),
    ("追妻火葬场", "离婚协议签完第 90 天，他把公司股权全转给了她"),
    ("萌宝助攻", "四岁女儿指着电视里的总裁喊了一声爸爸，全网都听见了"),
    ("误会梗", "她听见他说「不过是颗棋子」，没听见下一句「我舍不得」"),
    ("双强对峙", "他在查账，她在改账，两个人隔着玻璃同时抬头"),
]

BEATS = [
    ("0-3 秒", "钩子", "第一句就把冲突甩出来，别做铺垫"),
    ("3-15 秒", "冲突", "说清谁要什么、谁挡着，一个动作代替一句台词"),
    ("15-30 秒", "反转", "把上一段最肯定的判断推翻一次"),
    ("30-40 秒", "悬念", "留一个没答的问句，或者一个没开的门"),
    ("40-45 秒", "引导", "一句话收尾 + 下一集钩子，字幕压在最后 3 秒"),
]


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def _w(s):
    """显示宽度：中日韩字符算 2 列，表格才对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def fmt_pts(n):
    if isinstance(n, float) and abs(n - round(n)) > 1e-9:
        return "{:,.2f}".format(n)
    return "{:,}".format(int(round(n)))


def fmt_yuan(pts):
    return "{:,.2f} 元".format(float(pts) / POINTS_PER_YUAN)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


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


def url_allowed(u):
    """上游对视频 / 图片地址的白名单。返回 (ok, 说明)。"""
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


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            with open(LEDGER, encoding="utf-8") as f:
                arr = json.load(f)
        arr.append(rec)
        with io.open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-300:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


# ───────────────────────── 算钱（纯本地，免费）─────────────────────────
def episode_cost(chars, seconds, music, beat, cover, cover_seconds, promo,
                 promo_seconds):
    """一条的账。返回 (items, total)，items 里每项带 basis 口径。"""
    items = []

    v = round(chars * TTS_POINTS_PER_CHAR, 2)
    items.append({"step": "voice", "name": "旁白配音", "points": v,
                  "basis": "%d 字 × %s 点/字（上游实际点数 x 3）"
                           % (chars, TTS_POINTS_PER_CHAR)})

    a = round(seconds * AVATAR_POINTS_PER_SECOND, 2)
    items.append({"step": "avatar", "name": "数字人口播", "points": a,
                  "basis": "%d 秒 × %d 点/秒（standard，上游 3 点/秒 x 5）"
                           % (seconds, AVATAR_POINTS_PER_SECOND)})

    m = round(music * MEDIA33_POINTS_PER_CALL, 2)
    items.append({"step": "music", "name": "配乐", "points": m,
                  "basis": "%d 条 × %d 点/条（media_services_33 未配价，按预冻口径）"
                           % (music, MEDIA33_POINTS_PER_CALL)})

    b = round(beat * MEDIA33_POINTS_PER_CALL, 2)
    items.append({"step": "beat", "name": "卡点字幕", "points": b,
                  "basis": "%d 条 × %d 点/条（同上）" % (beat, MEDIA33_POINTS_PER_CALL)})

    if cover == "local":
        c = 0.0
        cbasis = "本地截帧，0 点（封面不必走生成线）"
    else:
        c = round(FULL_VIDEO_RATES[cover] * cover_seconds, 2)
        cbasis = "%s %d 点/秒 × %d 秒（full_video 一键成片）" % (
            cover, FULL_VIDEO_RATES[cover], cover_seconds)
    items.append({"step": "cover", "name": "封面 / 片头", "points": c, "basis": cbasis})

    p = 0.0
    if promo != "none":
        p = round(FULL_VIDEO_RATES[promo] * promo_seconds, 2)
    items.append({"step": "promo", "name": "预告片", "points": p,
                  "basis": ("不出，0 点" if promo == "none" else
                            "%s %d 点/秒 × %d 秒" % (promo, FULL_VIDEO_RATES[promo],
                                                    promo_seconds))})

    total = round(sum(i["points"] for i in items), 2)
    return items, total


def cfg_of(a):
    return dict(chars=int(a.chars), seconds=int(a.seconds), music=int(a.music),
                beat=int(a.beat), cover=a.cover,
                cover_seconds=int(a.cover_seconds), promo=a.promo,
                promo_seconds=int(a.promo_seconds))


# ───────────────────────── 闸门 ─────────────────────────
def gate(a, cost, what):
    """两道闸门：超预算先退 5（一个请求都不发），再要 --yes 退 4。"""
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点超过 --budget %d 点（%s）。调大 --budget 或缩短秒数。"
                   % (cost, a.budget, what), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "%s预计 %s 点（%s）。这会真实提交并冻结点数，确认请加 --yes。"
                   % (what, fmt_pts(cost), fmt_yuan(cost)), EXIT_CONFIRM)


def fmt_ep(project, season, n):
    return "S%02dE%02d" % (int(season), int(n))


def fname(project, season, n, station, spec="", ver=1, ext="mp4"):
    out = "%s_S%02dE%02d_%s" % (project, int(season), int(n), station)
    if spec:
        out += "_" + spec
    return "%s_v%02d.%s" % (out, int(ver), ext)


def step_costs(cfg):
    """每个付费工位自己的点数，给 run / batch 精确加总用。"""
    items, _total = episode_cost(**cfg)
    return {i["step"]: i["points"] for i in items}


def sum_steps(cfg, steps, episodes=1):
    sc = step_costs(cfg)
    return round(sum(sc.get(s, 0) for s in steps) * episodes, 2)


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    cfg = cfg_of(a)
    items, one = episode_cost(**cfg)
    day = round(one * a.episodes, 2)

    rows = []
    for s in STATIONS:
        rows.append({"step": s["key"], "name": s["name"], "channel": s["channel"],
                     "endpoint": s["path"] or "本地", "unit": s["unit"],
                     "points": s["per"], "hint": s["hint"]})
    out = {"ok": True, "stations": rows, "fullVideoRates": FULL_VIDEO_RATES,
           "unitPoints": {"ttsPerChar": TTS_POINTS_PER_CHAR,
                          "avatarPerSecond": AVATAR_POINTS_PER_SECOND,
                          "media33PerCall": MEDIA33_POINTS_PER_CALL},
           "perEpisode": {"items": items, "points": one},
           "perDay": {"episodes": a.episodes, "points": day},
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("短剧量产台 · 8 个工位 4 条能力线（单价现查 GET /api/v1/pricing）")
    print()
    print("  %s %s %s %s %s" % (pad("--step", 8), pad("工位", 12), pad("端点", 40),
                                pad("单价", 11), "一句话"))
    print("  " + "-" * 112)
    for r in rows:
        price = ("%s %s" % (r["points"], r["unit"])) if r["points"] not in (None, 0) \
            else ("按分辨率" if r["step"] == "cover" else "免费")
        ep_short = r["endpoint"].replace(API_PREFIX + "/apps/", "apps/") \
            .replace(API_PREFIX + "/", "")
        print("  %s %s %s %s %s" % (
            pad(r["step"], 8), pad(r["name"], 12), pad(ep_short[:40], 40),
            pad(price, 11), r["hint"]))
    print()
    print("  一条 %d 秒 / %d 字 / 配乐 %d 条 / 卡点 %d 条 / 封面 %s："
          % (cfg["seconds"], cfg["chars"], cfg["music"], cfg["beat"], cfg["cover"]))
    for i in items:
        if i["points"]:
            print("    %s %s 点  %s" % (pad(i["name"], 14),
                                        pad(fmt_pts(i["points"]), 8, left=False),
                                        i["basis"]))
    print("    %s %s 点 = %s" % (pad("合计", 14), pad(fmt_pts(one), 8, left=False),
                                 fmt_yuan(one)))
    print()
    print("  一天 %d 条 = %s 点 = %s。" % (a.episodes, fmt_pts(day), fmt_yuan(day)))
    print("  1 元 = 100 点。full_video 五档：480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒。")
    print("  秒数是唯一的大杠杆：口播 15 点/秒占全条 79%%，45 秒降到 30 秒一天省 %s 点。"
          % fmt_pts(int(15 * 15 * a.episodes)))
    return 0


def cmd_cost(a, key, host):
    cfg = cfg_of(a)
    items, one = episode_cost(**cfg)
    day = round(one * a.episodes, 2)

    ways = []
    for label, override in (
            ("全配（默认）", {}),
            ("只口播（配音/配乐/卡点复用现成素材）",
             dict(chars=0, music=0, beat=0)),
            ("口播 30 秒（其余同默认）", dict(seconds=30)),
            ("封面走 full_video 480P 4 秒", dict(cover="480P")),
            ("加一条 15 秒 1080P 预告片", dict(promo="1080P", promo_seconds=15))):
        c = dict(cfg)
        c.update(override)
        _it, tot = episode_cost(**c)
        ways.append({"way": label, "points": tot, "yuan": round(tot / POINTS_PER_YUAN, 2),
                     "perDay": round(tot * a.episodes, 2),
                     "perDayYuan": round(tot * a.episodes / POINTS_PER_YUAN, 2)})

    out = {"ok": True, "episodes": a.episodes, "config": cfg, "items": items,
           "perEpisode": one, "perDay": day, "perDayYuan": round(day / POINTS_PER_YUAN, 2),
           "ways": ways, "estimatedPoints": day,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-08 现查）",
               "voice_tts 对外价 = 上游实际点数 x 3，本包按 0.18 点/字估算，真实扣费看 usage.points_cost",
               "pic_lipsync 对外价 = 上游实际点数 x 5，standard 档实测 3 点/秒，对外 15 点/秒",
               "media_services_33 的 29 个接口都还没配价，每次调用先冻 60 点，按 60 点/条入账",
               "封面用本地截帧是 0 点；要动态片头才走 full_video（4-15 秒整数）",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("预估成本（1 元 = 100 点）· 一天 %d 条" % a.episodes)
    print()
    print("  %s %s %s  %s" % (pad("工位", 18), pad("一条(点)", 12, left=False),
                              pad("一天(点)", 12, left=False), "口径"))
    print("  " + "-" * 96)
    for i in items:
        print("  %s %s %s  %s" % (
            pad(i["name"], 18), pad(fmt_pts(i["points"]), 12, left=False),
            pad(fmt_pts(round(i["points"] * a.episodes, 2)), 12, left=False),
            i["basis"]))
    print("  " + "-" * 96)
    print("  %s %s %s  %s / 天" % (
        pad("合计", 18), pad(fmt_pts(one), 12, left=False),
        pad(fmt_pts(day), 12, left=False), fmt_yuan(day)))
    print()
    print("  五种走法对照")
    for w in ways:
        print("    %s 一条 %s 点 · 一天 %s 点（%.2f 元）"
              % (pad(w["way"], 36), pad(fmt_pts(w["points"]), 9, left=False),
                 pad(fmt_pts(w["perDay"]), 11, left=False), w["perDayYuan"]))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


def cmd_doctor(a, key, host):
    checks = []
    t0 = time.time()

    # 1) 余额（开账）
    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    bal0 = d.get("available_points")
    checks.append(("Key + 余额 /user/balance", st == 200 and bal0 is not None,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(bal0 or 0), fmt_pts(d.get("frozen") or 0))))

    # 2) 流水（只读，limit=1）
    st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("流水 /user/balance/logs", st == 200 and isinstance(d.get("logs"), list),
                   "HTTP %s · 共 %s 条 · 净变动 %s"
                   % (st, fmt_pts(d.get("total") or 0), d.get("balanceMoving"))))

    # 3) 价目表：4 条能力线的价格规则都在
    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
    pr = {}
    if st == 200:
        pr = (jloads(txt) or {}).get("pricing") or {}
    fv = pr.get(VIDEO_PATH) or {}
    rates = fv.get("resolutionRates") or {}
    rate_ok = all(int(rates.get(k, -1)) == v for k, v in FULL_VIDEO_RATES.items())
    checks.append(("价目 full_video 五档齐全（480P 14 / 2K 80）", st == 200 and rate_ok,
                   "HTTP %s · %s" % (st, json.dumps(rates, ensure_ascii=False)[:80])))

    mk = pr.get(API_PREFIX + "/apps/pic_lipsync/*") or {}
    up = pr.get(UPLOAD_PATH) or {}
    m33 = [k for k in pr if "media_services_33" in k]
    checks.append(("价目 pic_lipsync x5 · upload 0 点",
                   (int(mk.get("markupPercent") or 0) == 400
                    and int(up.get("cost") or 0) == 0 and not m33),
                   "pic_lipsync markup=%s · upload cost=%s · media33 配价规则 %d 条"
                   % (mk.get("markupPercent"), up.get("cost"), len(m33))))

    # 4) 应用注册表：4 个应用都在，media_services_33 的 29 个音频接口在
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    apps = (jloads(txt) or {}).get("data") or []
    by = {x.get("code"): x for x in apps if isinstance(x, dict)}
    need = ("full_video", "voice_tts", "pic_lipsync", "media_services_33")
    miss = [c for c in need if c not in by]
    n33 = len((by.get("media_services_33") or {}).get("apis") or [])
    checks.append(("应用注册表 4 个应用齐（media33 29 口）",
                   st == 200 and not miss and n33 == 29,
                   "HTTP %s · %d 个应用 · media33=%d%s"
                   % (st, len(apps), n33, (" · 缺 " + ",".join(miss)) if miss else "")))

    # 5) 任务查询路由：假 id 返回结构化「任务不存在」，不收钱
    st, txt = http_json("GET", host + TASKS_PATH + "probe-no-such-task", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("查询路由 GET /tasks/{id}（本包唯一轮询口）",
                   st == 200 and d.get("code") == 0,
                   "HTTP %s · %s" % (st, (d.get("msg") or "")[:40])))

    # 6) 上传（免费）：不带 file，停在校验层
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
    d = jloads(txt) or {}
    checks.append(("上传 POST /upload（免费，flat cost 0）",
                   st in (200, 400, 422) and d.get("code") in (0, 1, None),
                   "HTTP %s · %s" % (st, (d.get("msg") or err_text(st, txt))[:40])))

    # 7) 余额复采：与开账一致才算真 0 点
    st2, txt2 = http_json("GET", host + "/user/balance", key, timeout=40)
    d2 = jloads(txt2) or {}
    bal1 = d2.get("available_points")
    same = (st2 == 200 and bal0 is not None and bal1 is not None
            and abs(float(bal1) - float(bal0)) < 1e-6)
    checks.append(("余额前后一致 = 本轮 0 点", same,
                   "%.2f -> %.2f（%.1fs）"
                   % (float(bal0 or 0), float(bal1 or 0), time.time() - t0)))

    ok = all(c[1] for c in checks)
    out = {"ok": ok, "host": host, "estimatedPoints": 0, "yuan": 0.0,
           "stationCount": len(STATIONS), "appCount": len(apps),
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok else EXIT_GATE
    print()
    print("自检（7 个请求全部免费：只读 GET + 空表单上传，0 条任务、冻结 0 点）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 46), dd))
    print()
    print("  一个应用层 submit 都没发，一次 list_voices 都没调 —— 这两个口子会先冻再退。")
    print("  4 条能力线：tts_async 配音 · pic_lipsync mode=text 口播 · "
          "media_services_33 配乐与卡点 · full_video 片头封面")
    return 0 if ok else EXIT_GATE


# ───────────────────────── 排产单（免费，只写本地）─────────────────────────
def cmd_plan(a, key, host):
    cfg = cfg_of(a)
    items, one = episode_cost(**cfg)
    n = int(a.episodes)
    if n < 1 or n > 60:
        raise Fail("usage", "--episodes 取 1 到 60（一天的量）", EXIT_USAGE)
    proj = (a.project or "SD").strip()
    if not re.match(r"^[A-Za-z][A-Za-z0-9]{1,7}$", proj):
        raise Fail("usage", "--project 要 2 到 8 位字母数字，首字母开头（命名规范第一位）",
                   EXIT_USAGE)
    season = int(a.season)

    slate = []
    for i in range(1, n + 1):
        hook_key, hook_line = HOOKS[(i - 1) % len(HOOKS)]
        ep = fmt_ep(proj, season, i)
        steps = []
        for s in STATIONS:
            pts = STATION_MAP[s["key"]]["per"]
            if s["key"] == "voice":
                pts = round(cfg["chars"] * TTS_POINTS_PER_CHAR, 2)
            elif s["key"] == "avatar":
                pts = round(cfg["seconds"] * AVATAR_POINTS_PER_SECOND, 2)
            steps.append({"step": s["key"], "name": s["name"],
                          "endpoint": s["path"] or "本地",
                          "points": pts if pts is not None else 0, "unit": s["unit"]})
        files = []
        for st_name, ext, must, spec, _mb, label in DELIVER:
            files.append({"station": st_name, "label": label, "required": must,
                          "name": fname(proj, season, i, st_name, spec, 1, ext)})
        slate.append({"ep": ep, "index": i, "hookType": hook_key, "title": hook_line,
                      "genre": a.genre, "seconds": cfg["seconds"],
                      "chars": cfg["chars"], "beats": [list(b) for b in BEATS],
                      "stations": steps, "points": one,
                      "yuan": round(one / POINTS_PER_YUAN, 2), "files": files})

    total = round(one * n, 2)
    plan = {"ok": True, "project": proj, "season": season, "episodes": n,
            "genre": a.genre, "config": cfg,
            "naming": "%s_S<季两位>E<集两位>_<工位>_<规格>_v<版本两位>.<扩展名>" % proj,
            "deliver": [{"station": s, "ext": e, "required": m, "spec": sp,
                         "maxMb": mb, "label": lb}
                        for s, e, m, sp, mb, lb in DELIVER],
            "stations": [{"step": s["key"], "name": s["name"],
                          "endpoint": s["path"] or "本地"} for s in STATIONS],
            "slate": slate, "perEpisode": one, "estimatedPoints": total,
            "yuan": round(total / POINTS_PER_YUAN, 2)}

    outdir = a.outdir or "."
    if a.json and not a.write:
        print(json.dumps(plan, ensure_ascii=False))
        return 0
    if a.write:
        try:
            os.makedirs(outdir, exist_ok=True)
            with io.open(os.path.join(outdir, "plan.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(plan, ensure_ascii=False, indent=1))
            with io.open(os.path.join(outdir, "slate.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(render_slate(plan))
        except OSError as e:
            raise Fail("usage", "写不进 %s：%s" % (outdir, e), EXIT_USAGE)
    if a.json:
        print(json.dumps(plan, ensure_ascii=False))
        return 0

    print("排产单 · %s 第 %d 季 · %d 条 · %s" % (proj, season, n, a.genre))
    print()
    print("  %s %s %s" % (pad("集号", 10), pad("钩子类型", 12), pad("第一句", 48) + "点数"))
    print("  " + "-" * 92)
    for e in slate:
        print("  %s %s %s %s" % (pad(e["ep"], 10), pad(e["hookType"], 12),
                                  pad(e["title"][:46], 48), fmt_pts(e["points"])))
    print()
    print("  一条 %s 点（%s）· 一天 %d 条 %s 点（%s）"
          % (fmt_pts(one), fmt_yuan(one), n, fmt_pts(total), fmt_yuan(total)))
    print("  命名：%s" % plan["naming"])
    print("  交付：%d 件必交 + 1 件选交 / 条（口径见 SKILL.md 的「交付清单」）"
          % len([x for x in DELIVER if x[2]]))
    if a.write:
        print()
        print("  已写：%s\\plan.json" % outdir)
        print("  已写：%s\\slate.md（可直接打印贴在排产板上）" % outdir)
        print("  下一步：check --dir %s --plan %s\\plan.json" % (outdir, outdir))
    else:
        print()
        print("  加 --write 才会落盘（默认只打印，不写文件）。")
    return 0


def render_slate(plan):
    lines = ["# %s 日更排产单 · 第 %d 季 · %d 条"
             % (plan["project"], plan["season"], plan["episodes"]), "",
             "类型：%s　一条 %s 点（%.2f 元）　一天 %s 点（%.2f 元）"
             % (plan["genre"], fmt_pts(plan["perEpisode"]),
                plan["perEpisode"] / POINTS_PER_YUAN, fmt_pts(plan["estimatedPoints"]),
                plan["yuan"]), "",
             "## 交付清单（每条）", "",
             "| 工位 | 说明 | 必交 | 规格 | 命名 |", "|---|---|---|---|---|"]
    for d in plan["deliver"]:
        nm = fname(plan["project"], plan["season"], 1, d["station"], d["spec"], 1, d["ext"])
        lines.append("| %s | %s | %s | %s | `%s` |"
                     % (d["station"], d["label"], "是" if d["required"] else "选",
                        d["spec"] or "-", nm))
    for e in plan["slate"]:
        lines += ["", "## %s　%s" % (e["ep"], e["title"]), "",
                  "钩子类型：%s　时长：%d 秒　文案：%d 字　点数：%s"
                  % (e["hookType"], e["seconds"], e["chars"], fmt_pts(e["points"])), "",
                  "| 时间 | 段落 | 怎么拍 |", "|---|---|---|"]
        for b in e["beats"]:
            lines.append("| %s | %s | %s |" % (b[0], b[1], b[2]))
        lines += ["", "文件："]
        for f in e["files"]:
            lines.append("- `%s`（%s%s）" % (f["name"], f["label"],
                                            "" if f["required"] else "，选交"))
    return "\n".join(lines) + "\n"


# ───────────────────────── 上传（免费）─────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要传到平台的素材：图 / 音频 / 视频）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": path, "size": size,
               "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传）")
        print("  端点：POST %s（multipart，字段名 file，flat cost 0）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        return 0
    say("正在上传 %s（%d 字节）…" % (os.path.basename(path), size))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") not in (1, 0) or not got:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                    "mode": "upload", "file": path, "http": st, "error": msg})
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    ok_url, kind = url_allowed(got)
    out = {"ok": True, "url": got, "size": data.get("size"), "mime": data.get("mime_type"),
           "type": data.get("type"), "hostKind": kind, "urlAllowed": ok_url,
           "elapsed": round(dt, 1), "estimatedPoints": 0}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "upload",
                "file": path, "size": size, "url": got, "elapsed": round(dt, 1)})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs，0 点）" % dt)
    print("  地址：%s" % got)
    print("  归属：%s（白名单内，可直接给 avatar 的 --image-url / --voice-ref 用）" % kind)
    return 0


# ───────────────────────── 付费：一条 / 一天 ─────────────────────────
def load_plan(path):
    if not path:
        return None
    if not os.path.isfile(path):
        raise Fail("usage", "排产单不存在：%s（先跑 plan --write）" % path, EXIT_USAGE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("usage", "排产单读不了：%s: %s" % (type(e).__name__, e), EXIT_USAGE)


def pick_ep(plan, want):
    if not plan:
        return None
    for e in plan.get("slate") or []:
        if e.get("ep") == want or str(e.get("index")) == str(want):
            return e
    return None


def need_http_url(flag, val):
    if not val:
        raise Fail("usage", "必须给 %s（先用 upload 上传，或填平台已有地址）" % flag,
                   EXIT_USAGE)
    if not re.match(r"^https?://", val, re.I):
        raise Fail("usage", "%s 要以 http:// 或 https:// 开头" % flag, EXIT_USAGE)
    return val


def body_for(step, a, ep):
    text = a.text or (ep or {}).get("title") or ""
    if step == "voice":
        body = {"text": text, "format": "mp3"}
        if a.voice_id:
            body["reference_id"] = a.voice_id
        return body
    if step == "avatar":
        return {"mode": "text", "model": "super-lipsync-pro",
                "quality": a.quality, "content": text,
                "audio_url": a.voice_ref, "image_url": a.image_url}
    if step == "music":
        return {"model": a.music_model, "custom_mode": False, "instrumental": True,
                "title": (ep or {}).get("ep") or "BGM",
                "prompt": a.music_prompt or (text + " · 短剧配乐"),
                "duration": int(a.seconds)}
    if step == "beat":
        return {"task_id": a.music_task, "audio_id": a.music_audio}
    if step == "cover":
        res = a.cover if a.cover != "local" else "480P"
        return {"model": "full-video", "ratio": "9:16",
                "duration": int(a.cover_seconds), "resolution": res,
                "content": [{"type": "text", "text": text}]}
    raise Fail("usage", "不认识的工位 %s" % step, EXIT_USAGE)


def preflight_step(step, a):
    if step == "avatar":
        need_http_url("--image-url（人物图）", a.image_url)
        need_http_url("--voice-ref（参考音色音频）", a.voice_ref)
        if not (a.text or a.plan):
            raise Fail("usage", "avatar 要一段文案：--text，或先 plan --write 再 --plan",
                       EXIT_USAGE)
    elif step == "voice":
        if not (a.text or a.plan):
            raise Fail("usage", "voice 要一段文案：--text，或先 plan --write 再 --plan",
                       EXIT_USAGE)
    elif step == "music":
        if not a.music_model:
            raise Fail("usage", "music 要 --music-model（平台音乐线的模型代号）", EXIT_USAGE)
    elif step == "beat":
        if not a.music_task or not a.music_audio:
            raise Fail("usage",
                       "beat 要 --music-task 与 --music-audio（配乐那一步返回的 task_id "
                       "与 audio_id，同一批流水里先跑 music）", EXIT_USAGE)
    elif step == "cover":
        if a.cover == "local":
            raise Fail("usage",
                       "cover 现在走的是「本地截帧」（0 点），不需要提交。"
                       "要做动态片头就加 --cover 480P（或 768P/1080P/2K/4K）",
                       EXIT_USAGE)
        if not (VIDEO_MIN_SECONDS <= int(a.cover_seconds) <= VIDEO_MAX_SECONDS):
            raise Fail("usage", "full_video 的 duration 只收 %d-%d 秒整数"
                       % (VIDEO_MIN_SECONDS, VIDEO_MAX_SECONDS), EXIT_USAGE)


def run_one(a, key, host, step, ep=None):
    path = STATION_MAP[step]["path"]
    url = host + path
    body = body_for(step, a, ep)
    mode = a.json
    say("正在提交 %s %s …" % (ep["ep"] if ep else "", step))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    flat = dict(data) if data else d
    tid = flat.get("task_id") or flat.get("taskId") or flat.get("id")
    ok = st in (200, 201) and d.get("code") in (1, 0) and bool(tid)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": ok, "mode": "run",
           "ep": (ep or {}).get("ep"), "step": step, "taskId": tid,
           "status": flat.get("status"), "endpoint": path, "elapsed": round(dt, 1)}
    if not ok:
        msg = err_text(st, txt)
        rec["error"] = msg
        ledger_add(rec)
        raise Fail("call", "%s 提交失败（HTTP %s）：%s" % (step, st, msg), EXIT_CALL)
    ledger_add(rec)
    usage = flat.get("usage") if isinstance(flat.get("usage"), dict) else {}
    return {"step": step, "taskId": tid, "status": flat.get("status"),
            "audioId": flat.get("audio_id"), "url": flat.get("url")
            or flat.get("videoUrl") or flat.get("audio_url"),
            "pointsCost": usage.get("points_cost"), "endpoint": path,
            "elapsed": round(dt, 1)}


def steps_of(a):
    if a.all:
        return list(PAID_STEPS)
    out = []
    for s in (a.step or "").split(","):
        s = s.strip()
        if s:
            out.append(s)
    if not out:
        raise Fail("usage", "要么 --step voice|avatar|music|beat|cover，要么 --all",
                   EXIT_USAGE)
    bad = [s for s in out if s not in VALID_STEPS]
    if bad:
        raise Fail("usage", "不认识的工位：%s（可选 %s）"
                   % (",".join(bad), " / ".join(VALID_STEPS)), EXIT_USAGE)
    return out


def cmd_run(a, key, host):
    plan = load_plan(a.plan)
    steps = steps_of(a)
    ep = pick_ep(plan, a.ep) if a.ep else None
    cfg = cfg_of(a)
    total = sum_steps(cfg, steps, 1)
    what = "一条 %s 的 %d 个工位（%s）" % (
        (ep or {}).get("ep") or "（未指定集号）", len(steps), ",".join(steps))
    gate(a, total, what)
    for s in steps:
        preflight_step(s, a)

    reqs = [{"step": s, "endpoint": STATION_MAP[s]["path"],
             "requestBody": body_for(s, a, ep)} for s in steps]
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "ep": (ep or {}).get("ep"), "steps": reqs,
               "estimatedPoints": total, "yuan": round(total / POINTS_PER_YUAN, 2)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  集号：%s　工位：%s" % ((ep or {}).get("ep") or "-", ",".join(steps)))
        for r in reqs:
            print("  → POST %s" % r["endpoint"])
            print("    %s" % json.dumps(r["requestBody"], ensure_ascii=False)[:300])
        print("  预估：%s 点（%s）" % (fmt_pts(total), fmt_yuan(total)))
        return 0

    done = []
    for s in steps:
        done.append(run_one(a, key, host, s, ep))
    out = {"ok": True, "ep": (ep or {}).get("ep"), "steps": done,
           "estimatedPoints": total, "yuan": round(total / POINTS_PER_YUAN, 2)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交 %d 个工位" % len(done))
    for r in done:
        print("  %-8s %s  状态 %s%s" % (r["step"], r["taskId"], r["status"],
                                        ("　实扣 %s 点" % r["pointsCost"])
                                        if r["pointsCost"] is not None else ""))
    print()
    print("  查进度：python3 scripts/run.py status --task-id <taskId>")
    print("  下一步：配乐出了 task_id 与 audio_id 后再跑 --step beat；"
          "全跑完 check 一遍交付清单")
    return 0


def parse_eps(spec, total):
    spec = (spec or "all").strip().lower()
    if spec in ("all", ""):
        return list(range(1, total + 1))
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = chunk.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(chunk))
    return [x for x in out if 1 <= x <= total]


def cmd_batch(a, key, host):
    plan = load_plan(a.plan)
    if not plan or not plan.get("slate"):
        raise Fail("usage", "batch 要 --plan（先跑 plan --write 出排产单）", EXIT_USAGE)
    n = len(plan["slate"])
    eps = parse_eps(a.episodes, n)
    if not eps:
        raise Fail("usage", "--episodes 里没有落在 1-%d 之内的集号" % n, EXIT_USAGE)
    steps = list(PAID_STEPS) if a.all else steps_of(a)
    cfg = cfg_of(a)
    total = sum_steps(cfg, steps, len(eps))
    what = "一天 %d 条 × %d 个工位" % (len(eps), len(steps))
    gate(a, total, what)
    for s in steps:
        preflight_step(s, a)

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "episodes": len(eps), "steps": steps,
               "requests": len(eps) * len(steps), "estimatedPoints": total,
               "yuan": round(total / POINTS_PER_YUAN, 2),
               "plan": [{"ep": fmt_ep(plan["project"], plan["season"], i),
                         "endpoints": [STATION_MAP[s]["path"] for s in steps]}
                        for i in eps]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  %d 条 × %d 工位 = %d 个请求" % (len(eps), len(steps),
                                                  len(eps) * len(steps)))
        for s in steps:
            print("  → POST %s" % STATION_MAP[s]["path"])
        print("  预估：%s 点（%s）" % (fmt_pts(total), fmt_yuan(total)))
        return 0

    done, failed = [], []
    for i in eps:
        ep = pick_ep(plan, fmt_ep(plan["project"], plan["season"], i))
        for s in steps:
            try:
                done.append(run_one(a, key, host, s, ep))
            except Fail as e:
                failed.append({"ep": (ep or {}).get("ep"), "step": s,
                               "error": e.message[:200]})
                ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False,
                            "mode": "batch", "ep": (ep or {}).get("ep"),
                            "step": s, "error": e.message[:200]})
                if not a.keep_going:
                    out = {"ok": False, "exit": EXIT_CALL, "episodes": len(eps),
                           "done": done, "failed": failed,
                           "estimatedPoints": total,
                           "error": {"kind": "call",
                                     "message": "第 %s 条 %s 失败：%s"
                                                % ((ep or {}).get("ep"), s,
                                                   e.message[:200])}}
                    if a.json:
                        print(json.dumps(out, ensure_ascii=False))
                    else:
                        say("失败：%s" % out["error"]["message"])
                    return EXIT_CALL

    out = {"ok": not failed, "episodes": len(eps), "steps": steps,
           "done": done, "failed": failed, "estimatedPoints": total,
           "yuan": round(total / POINTS_PER_YUAN, 2)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if not failed else EXIT_CALL
    print("批量提交完成：%d 条 × %d 工位，成功 %d 个任务，失败 %d 个"
          % (len(eps), len(steps), len(done), len(failed)))
    for f in failed:
        print("  × %s %s：%s" % (f["ep"], f["step"], f["error"][:120]))
    print()
    print("  查进度：python3 scripts/run.py status --task-id <taskId>")
    return 0 if not failed else EXIT_CALL


# ───────────────────────── 交付验收（免费，只读本地）─────────────────────────
def image_size(path):
    """只读文件头拿像素，不装第三方库。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return (int.from_bytes(head[16:20], "big"),
                        int.from_bytes(head[20:24], "big"))
            if head[:2] != b"\xff\xd8":
                return None
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                while b == b"\xff":
                    b = f.read(1)
                if not b:
                    return None
                marker = b[0]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    continue
                ln = f.read(2)
                if len(ln) < 2:
                    return None
                seg = int.from_bytes(ln, "big")
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    data = f.read(5)
                    if len(data) < 5:
                        return None
                    return (int.from_bytes(data[3:5], "big"),
                            int.from_bytes(data[1:3], "big"))
                f.seek(seg - 2, 1)
    except OSError:
        return None


def cmd_check(a, key, host):
    root = a.dir or "."
    if not os.path.isdir(root):
        raise Fail("usage", "目录不存在：%s" % root, EXIT_USAGE)
    plan = load_plan(a.plan)
    proj = (plan or {}).get("project") or a.project or "SD"
    season = int((plan or {}).get("season") or a.season)

    files = []
    for base, _dirs, names in os.walk(root):
        for nm in names:
            files.append((os.path.join(base, nm), nm))
    files.sort()

    # 按 SxxExx 归集
    eps = {}
    bad_names = []
    for full, nm in files:
        m = NAME_RE.match(nm)
        if not m:
            if nm.lower().endswith((".mp4", ".mp3", ".srt", ".jpg", ".png")):
                bad_names.append(nm)
            continue
        key_ep = "%s_S%sE%s" % (m.group("proj"), m.group("season"), m.group("ep"))
        eps.setdefault(key_ep, {})[m.group("station")] = (full, nm, m)

    eps_want = []
    if plan and plan.get("slate"):
        eps_want = [e["ep"] for e in plan["slate"]]
    else:
        eps_want = sorted(eps)
    if not eps_want:
        raise Fail("gate", "在 %s 里没找到任何符合命名规范的文件，先跑 plan --write 再出片"
                   % root, EXIT_GATE)

    rows, problems = [], []
    for ep in eps_want:
        have = eps.get(ep) or {}
        row = {"ep": ep, "items": [], "ok": True}
        for st_name, ext, must, spec, mb, label in DELIVER:
            hit = have.get(st_name)
            item = {"station": st_name, "label": label, "required": must,
                    "file": None, "ok": True, "detail": ""}
            if not hit:
                if must:
                    item["ok"] = False
                    item["detail"] = "缺文件"
                    problems.append("%s 缺 %s（%s）" % (ep, st_name, label))
                else:
                    item["detail"] = "选交，未出"
                row["items"].append(item)
                continue
            full, nm, m = hit
            item["file"] = nm
            size_mb = os.path.getsize(full) / 1048576.0
            det = []
            if spec and (m.group("spec") or "") not in (spec, ""):
                item["ok"] = False
                det.append("规格写的是 %s，规范要 %s" % (m.group("spec"), spec))
            if size_mb > mb:
                item["ok"] = False
                det.append("体积 %.1f MB 超过 %d MB" % (size_mb, mb))
            if st_name == "cover" and ext in ("jpg", "jpeg", "png"):
                wh = image_size(full)
                item["pixels"] = list(wh) if wh else None
                if not wh:
                    item["ok"] = False
                    det.append("读不出像素")
                elif wh != COVER_SIZE:
                    item["ok"] = False
                    det.append("封面 %dx%d，规范要 %dx%d"
                               % (wh[0], wh[1], COVER_SIZE[0], COVER_SIZE[1]))
            if ext == "srt":
                try:
                    with open(full, encoding="utf-8") as f:
                        f.read(2048)
                except UnicodeDecodeError:
                    item["ok"] = False
                    det.append("SRT 不是 UTF-8")
            item["sizeMb"] = round(size_mb, 2)
            item["detail"] = "；".join(det) if det else "ok"
            if not item["ok"]:
                problems.append("%s %s：%s" % (ep, st_name, item["detail"]))
            row["items"].append(item)
        row["ok"] = all(x["ok"] for x in row["items"] if x["required"])
        rows.append(row)

    if bad_names:
        problems.append("%d 个文件命名不合规范" % len(bad_names))
    ok = not problems

    out = {"ok": ok, "dir": root, "project": proj, "season": season,
           "episodes": len(rows), "requiredPerEpisode": len([d for d in DELIVER if d[2]]),
           "rows": rows, "badNames": bad_names[:20], "problems": problems,
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok else EXIT_GATE

    print("交付清单验收 · %s · 第 %d 季 · %d 条" % (root, season, len(rows)))
    print()
    head = "  " + pad("集号", 10)
    for st_name, _e, must, _s, _m, _l in DELIVER:
        head += " " + pad(st_name + ("" if must else "?"), 7)
    print(head)
    print("  " + "-" * (10 + 8 * len(DELIVER)))
    for r in rows:
        line = "  " + pad(r["ep"], 10)
        for it in r["items"]:
            mark = "√" if it["ok"] and (it["file"] or it["required"]) \
                else ("×" if not it["ok"] else "-")
            line += " " + pad(mark, 7)
        print(line)
    print()
    if bad_names:
        print("  命名不合规范（%d 个）：" % len(bad_names))
        for nm in bad_names[:6]:
            print("    %s" % nm)
        print("    规范：%s_S<季两位>E<集两位>_<工位>_<规格>_v<版本两位>.<扩展名>" % proj)
        print()
    if problems:
        print("  × %d 处要修：" % len(problems))
        for p in problems[:15]:
            print("    %s" % p)
        print()
        print("  本轮花费 0 点（只读本地文件）。")
        return EXIT_GATE
    print("  √ %d 条全部过关：必交 %d 件齐、命名合规、封面 1080x1920、体积在线上限内。"
          % (len(rows), len([d for d in DELIVER if d[2]])))
    print("  本轮花费 0 点（只读本地文件）。")
    return 0


# ───────────────────────── 查任务 / 台账 ─────────────────────────
def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    # 只走免费的通用查询。应用层 query 按次计费（nano_banana/query 实测 72 点/次）。
    st, txt = http_json("GET", host + TASKS_PATH + tid, key, timeout=60)
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    flat = dict(data) if data else d
    missing = (d.get("code") == 0 and not data) or "不存在" in str(d.get("msg") or "")
    if st == 404 or missing:
        raise Fail("call", "查不到任务 %s：%s（刚提交可能还没落库，等 30 秒再查）"
                   % (tid, (d.get("msg") or "")[:80]), EXIT_CALL)
    if st not in (200, 201):
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    usage = flat.get("usage") if isinstance(flat.get("usage"), dict) else {}
    out = {"ok": True, "taskId": tid, "status": flat.get("status"),
           "message": flat.get("message"),
           "videoUrl": flat.get("videoUrl") or flat.get("video_url"),
           "audioUrl": flat.get("audio_url") or flat.get("audioUrl"),
           "audioId": flat.get("audio_id"),
           "pointsCost": usage.get("points_cost"), "endpoint": TASKS_PATH + tid,
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  状态：%s" % (flat.get("status") or "-"))
    if out["pointsCost"] is not None:
        print("  实扣：%s 点" % out["pointsCost"])
    if out["audioId"]:
        print("  audio_id：%s（配乐跑完拿它给 --step beat 用）" % out["audioId"])
    if out["videoUrl"]:
        print("  成片：%s" % out["videoUrl"])
        print("  提示：成片链接有效期不长，拿到就转存到本地再分发。")
    if out["audioUrl"]:
        print("  音频：%s" % out["audioUrl"])
    if flat.get("message"):
        print("  说明：%s" % str(flat.get("message"))[:300])
    print()
    print("  本轮花费 0 点（只读 GET /tasks/{id}）。")
    return 0


def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        with open(LEDGER, encoding="utf-8") as f:
            arr = json.load(f)
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        what = e.get("taskId") or (e.get("file") and os.path.basename(e["file"])) \
            or (e.get("error") or "")[:40] or "-"
        print("  %s  %-4s %-7s %-8s %-8s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            e.get("ep") or "-", e.get("step") or "-", str(what)[:44]))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 短剧量产台：一天 10 条日更的排产、出片、交付验收",
        epilog="端点：POST %s/api/v1/apps/voice_tts/tts_async · "
               "POST %s/api/v1/apps/pic_lipsync/submit · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "POST %s/api/v1/apps/media_services_33/music_timestamped_lyrics · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/upload · GET %s/api/v1/tasks/<id>" % ((DEFAULT_HOST,) * 7),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 100 元；超了退 5 且不发请求）"
                         % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    def add_slate_args(p, with_episodes=True):
        if with_episodes:
            p.add_argument("--episodes", type=int, default=DEFAULT_EPISODES,
                           help="一天几条（默认 %d）" % DEFAULT_EPISODES)
        p.add_argument("--seconds", type=int, default=DEFAULT_SECONDS,
                       help="口播秒数（默认 %d；这是全条最大的成本项）" % DEFAULT_SECONDS)
        p.add_argument("--chars", type=int, default=DEFAULT_CHARS,
                       help="旁白字数（默认 %d）" % DEFAULT_CHARS)
        p.add_argument("--music", type=int, default=1, help="配乐条数（默认 1）")
        p.add_argument("--beat", type=int, default=1, help="卡点字幕条数（默认 1）")
        p.add_argument("--cover", choices=["local", "480P", "768P", "1080P", "2K", "4K"],
                       default="local",
                       help="封面/片头：local 本地截帧 0 点（默认），其余走 full_video")
        p.add_argument("--cover-seconds", type=int, default=DEFAULT_COVER_SECONDS,
                       help="封面片头秒数 4-15（默认 %d）" % DEFAULT_COVER_SECONDS)
        p.add_argument("--promo", choices=["none", "480P", "768P", "1080P", "2K", "4K"],
                       default="none", help="另出预告片（默认不出）")
        p.add_argument("--promo-seconds", type=int, default=15,
                       help="预告片秒数 4-15（默认 15）")

    p = sub.add_parser("catalog", help="8 工位 + 4 条能力线 + 单价（免费）",
                       allow_abbrev=False)
    add_slate_args(p)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：一条 / 一天 / 五种走法（免费）",
                       allow_abbrev=False)
    add_slate_args(p)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="出排产单：10 条 × 8 工位 + 命名 + 点数（免费）",
                       allow_abbrev=False)
    add_slate_args(p)
    p.add_argument("--project", default="SD", help="项目代号 2-8 位字母数字（命名第一位）")
    p.add_argument("--season", type=int, default=1, help="第几季（默认 1）")
    p.add_argument("--genre", default="都市逆袭",
                   help="题材，写进排产单（默认 都市逆袭）")
    p.add_argument("--outdir", default="./out", help="落盘目录（默认 ./out）")
    p.add_argument("--write", action="store_true", help="真的写 plan.json 与 slate.md")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("doctor", help="自检 Key / 应用表 / 价目 / 查询 / 上传（0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="本地素材先传平台，拿白名单地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径（图 / 音频 / 视频）")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("check", help="交付清单验收：文件 / 命名 / 封面像素（免费）",
                       allow_abbrev=False)
    p.add_argument("--dir", default="./out", help="交付目录（默认 ./out）")
    p.add_argument("--plan", help="排产单 plan.json（给了就按单子验收集号）")
    p.add_argument("--project", help="没给 --plan 时用这个项目代号")
    p.add_argument("--season", type=int, default=1, help="没给 --plan 时用这一季")
    p.set_defaults(fn=cmd_check)

    def add_paid(p, with_episodes=True):
        p.add_argument("--plan", help="排产单 plan.json（plan --write 生成的）")
        p.add_argument("--ep", help="集号，例如 S01E03 或 3")
        p.add_argument("--step", help="工位：voice / avatar / music / beat / cover（逗号可多选）")
        p.add_argument("--all", action="store_true", help="按顺序跑全部付费工位")
        p.add_argument("--text", help="这一条的口播文案（不给就取排产单的标题）")
        p.add_argument("--image-url", help="人物图地址（avatar 必填）")
        p.add_argument("--voice-ref", help="参考音色音频地址（avatar 必填）")
        p.add_argument("--voice-id", help="音色模型 ID（voice 可选，reference_id）")
        p.add_argument("--quality", choices=["standard", "fast", "max"], default="standard",
                       help="口播档位（默认 standard = 15 点/秒）")
        p.add_argument("--music-model", default="suno",
                       help="配乐的模型代号（平台音乐线文档给的，默认 suno）")
        p.add_argument("--music-prompt", help="配乐提示词（不给就用标题拼）")
        p.add_argument("--music-task", help="配乐任务的 task_id（beat 必填）")
        p.add_argument("--music-audio", help="配乐任务的 audio_id（beat 必填）")
        p.add_argument("--timeout", type=int, default=120, help="提交超时秒数（默认 120）")
        p.add_argument("--yes", action="store_true", help="确认真实提交并冻结点数")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        add_slate_args(p, with_episodes=with_episodes)

    p = sub.add_parser("run", help="跑一条的一条工位或全链（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    add_paid(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("batch", help="跑一天的多条（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    add_paid(p, with_episodes=False)
    p.add_argument("--episodes", default="all",
                   help="跑哪几条：all / 1-10 / 1,3,5（默认 all）")
    p.add_argument("--keep-going", action="store_true", help="一条失败也继续跑后面的")
    p.set_defaults(fn=cmd_batch)

    p = sub.add_parser("status", help="查任务（免费，只走 GET /tasks/{id}）",
                       allow_abbrev=False)
    p.add_argument("--task-id", help="提交返回的 task_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近多少条（默认 20）")
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_check", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    # 子命令上重复定义的全局选项 default=SUPPRESS，没写就不覆盖父级的值
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    fn_name = getattr(a.fn, "__name__", "")
    try:
        key, host = load_conf(a.key, a.host)
        if not key and fn_name not in FREE:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n"
                       "注册领 Key：https://api.a7w.cn/", EXIT_USAGE)
        return a.fn(a, key, host)
    except Fail as e:
        if getattr(a, "json", False):
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
