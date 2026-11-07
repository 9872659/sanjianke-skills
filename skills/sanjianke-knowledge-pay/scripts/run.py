#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 知识付费招生（sanjianke-knowledge-pay）

课程 / 专栏 / 训练营一天要交的不是「一张海报」，是「一条招生链路」：
**5 个环节 x 3 个核心版位 = 15 条招生素材**，加上封面、学员见证、大纲图、
价格锚点卡，一整套 23 张静态；再加一条痛点视频、一段讲师背书、一首配乐，
就是一个知识付费运营一天（一单）的完整交付。

本包不新造接口，把 api.a7w.cn 上已有的五条能力按招生习惯重新排：

  出图     gpt-image-2.6      POST /api/v1/images/generations   6 点/张（n 1~4 一次多图）
  改图     gpt-image-2.6      POST /api/v1/images/edits         6 点/张（有讲师照 / 实拍图时用）
  参考图   nano_banana        POST /api/v1/apps/nano_banana/submit  72 点/次（讲师形象、见证合集）
  痛点视频 full_video         POST /api/v1/apps/full_video/submit  按秒 x 分辨率
  讲师口播 voice_tts          POST /api/v1/apps/voice_tts/tts      约 0.18 点/字
  配乐     media_services_33  POST /api/v1/apps/media_services_33/music_generate  50 点起
  查进度   GET /api/v1/tasks/<task_id>                             0 点
  传图     POST /api/v1/upload                                     0 点

## 招生链路（5 个环节，顺序就是转化顺序）

  L1 痛点     「会剪也会改，就是接不到单」        前 3 秒抓人
  L2 讲师背书 「8 年影视后期，带过 1200 名学员」  用资历换信任
  L3 课程大纲 「6 章 32 节，每节都留交付物」      让人看清拿什么
  L4 价格锚点 「早鸟 1280 元，原价 2980 元」      把价差摊成每节课
  L5 行动号召 「今天进群，先领 3 节试听课」      落到私域承接

## 一天（一单）到底多少钱（1 元 = 100 点，2026-11-08 现查价目）

  15 条链路素材 + 3 张封面 + 3 张见证 + 大纲图 + 价格卡 = 23 张  138 点 = 1.38 元
  再加一条 15 秒 1080P 痛点视频                          900 点
  60 字讲师背书                                         约 11 点
  一首 30 秒循环配乐                                     50 点起
  —— 整套 1,099 点 = 10.99 元

## 三条用钱换来的规矩（都做成了默认动作）

  1. 轮询只走 GET /api/v1/tasks/<id>（cost:0）。应用层 /query 每查一次按该应用单价结算，
     nano_banana/query 实测 72 点/次，盯一天进度就能把预算吃光。
  2. 要目录只看 GET /api/v1/apps 列表和 GET /api/v1/pricing。GET /api/v1/apps/<app>
     命中 /apps/<app>/* 通配计价，按 flat 单价即时扣费、不退（实测 dressing_diffusion
     200 点、nano_banana 72 点各一笔）。
  3. 首帧图与参考图必须是平台托管地址。外站地址一律 400 url_not_allowed，只认
     vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。
     本地图先 POST /api/v1/upload（免费）换地址，本包 film / img --ref 会自动做。

## 本地零成本的部分（0 点，不联网）

  plan  招生矩阵：5 个环节 x 版位、招生话术、命名、交付清单、私域承接话术、一周排期
  qc    交付前检查：承诺用语、价格锚点、环节差异、私域承接、封面字重、命名、尺寸、链路完整

## 子命令

  catalog  五条能力 + 端点 + 现查单价 + 版位表（免费）
  cost     一天要多少钱，四种走法对比（免费）
  plan     招生矩阵与交付清单（免费，纯本地）
  qc       交付前检查（免费，纯本地）
  img      出招生素材，6 点/张（nano 72 点；要 --yes）
  film     痛点短视频，按秒计费（要 --yes）
  voice    讲师背书口播，约 0.18 点/字（要 --yes）
  music    招生配乐，50 点起（要 --yes）
  upload   上传本地图，拿白名单地址（免费）
  status   查任务进度（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --courses 1
  python3 scripts/run.py plan --course "AI 短剧变现训练营"
  python3 scripts/run.py qc --plan ~/.a7w/knowledge-pay/20261108/plan.json
  python3 scripts/run.py img --kind cover --size 3x4 --yes
  python3 scripts/run.py img --link L1 --size 9x16 --n 2 --yes
  python3 scripts/run.py film --link L1 --seconds 15 --yes
  python3 scripts/run.py voice --text "8 年影视后期，带过 1200 名学员" --yes
  python3 scripts/run.py music --style "轻钢琴，渐强，适合招生短片" --yes
  python3 scripts/run.py status --task-id tsk_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
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

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "knowledge-pay")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-knowledge-pay/%s" % VERSION

# ── 五条能力（单价：GET /api/v1/pricing 与流水实测，2026-11-08）────────────────
APP_IMAGE = "gpt-image-2.6"
IMG_POINTS = 6                        # 点/张，与尺寸 / 质量 / 格式无关（实测扣 6 点）
IMAGE_PATH = API_PREFIX + "/images/generations"
EDIT_PATH = API_PREFIX + "/images/edits"

APP_NANO = "nano_banana"
NANO_POINTS = 72                      # 点/次，flat（价目表 /apps/nano_banana/* cost 72）
NANO_VIEW_POINTS = 25                 # 讲师形象多角度：25 点 x 选中视角数
NANO_PATH = API_PREFIX + "/apps/nano_banana/submit"
NANO_MODEL = "nano-banana"

APP_VIDEO = "full_video"
VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}   # 点/秒
VIDEO_CLIP_MIN, VIDEO_CLIP_MAX = 4, 15

APP_TTS = "voice_tts"
TTS_PER_CHAR = 0.18                   # 点/字（上游真实点数 x 3）
TTS_MAX_CHARS = 500

APP_MUSIC = "media_services_33"
MUSIC_FLOOR = 50                      # 点/首（落通配：上游 x 2、保底 50）
MUSIC_MODEL = "V6"

UPLOAD_PATH = API_PREFIX + "/upload"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 3000                 # 点 = 30 元，一天招生素材的默认上限

RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]

# ── 五个版位（requests 都是 gpt-image 合法尺寸）────────────────────────────────
SIZES = {
    "3x4": dict(ratio="3:4", req="1152x1536", publish="1242x1660",
                platforms="小红书笔记封面 / 公众号内页",
                safe="上 1/3 放主标，中段放讲师或课程画面，底部 15% 留白放行动号召"),
    "9x16": dict(ratio="9:16", req="720x1280", publish="1080x1920",
                 platforms="视频号 / 抖音 / 快手",
                 safe="顶部 12% 放栏目标签，底部 18% 留白放进度与行动号召"),
    "1x1": dict(ratio="1:1", req="1024x1024", publish="1080x1080",
                platforms="社群 / 朋友圈 / 私域承接页",
                safe="主体居中偏上，四角留白放价格角标与名额"),
    "16x9": dict(ratio="16:9", req="1280x720", publish="1920x1080",
                 platforms="直播封面 / 公众号头图 / B 站",
                 safe="主体居中，左侧 1/4 留白给课程名"),
    "4x5": dict(ratio="4:5", req="1024x1280", publish="1080x1350",
                platforms="朋友圈广告 / 视频号动态",
                safe="中心构图，顶部与底部各留 10% 给标题与价格"),
}
SIZE_ORDER = ["3x4", "9x16", "1x1", "16x9", "4x5"]
CORE_SIZES = ["3x4", "9x16", "1x1"]     # 一天必交的三个版位

# ── 五个招生环节：顺序就是转化顺序，一条都不能少 ───────────────────────────────
LINKS = [
    dict(code="L1", name="痛点", focus="把学员当下的处境说出来",
         why="痛点在前 3 秒，决定这条素材有没有人看完"),
    dict(code="L2", name="讲师背书", focus="资历、作品量、带过的学员数",
         why="知识付费卖的是人，先让人相信你做过"),
    dict(code="L3", name="课程大纲", focus="几章几节、每节交付什么",
         why="大纲是「我到底拿到什么」的唯一答案，比形容词有用"),
    dict(code="L4", name="价格锚点", focus="原价、早鸟价、摊到每节课多少",
         why="把总价摊成单节价，价格才不吓人"),
    dict(code="L5", name="行动号召", focus="加微 / 进群 / 领试听",
         why="知识付费的成交发生在私域，公域只负责把门推开"),
]
LINK_ORDER = ["L1", "L2", "L3", "L4", "L5"]

# 知识付费招生的合规雷区（收益承诺 / 绝对化）
FORBIDDEN_WORDS = ["保过", "包过", "包就业", "包分配", "包会", "月入过万", "月入十万",
                   "躺赚", "稳赚", "零风险", "无条件退款", "保证", "100%", "稳赚不赔",
                   "最", "第一", "唯一", "绝对", "全网", "国家级", "永久", "秒杀"]
CTA_WORDS = ["加微", "进群", "领", "试听", "报名", "私信", "咨询", "扫码", "名额"]

PRIVATE_TOPICS = [
    ("加微", "第一次加微，先给东西再说话"),
    ("进群", "进群动作要一句话能执行"),
    ("试听", "用一节具体的课筛人"),
    ("催单", "只报事实与名额，不逼单"),
    ("复购", "结营后 30 天的回访与转介绍"),
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
            d = json.load(io.open(cfg, encoding="utf-8"))
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                            # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120, retries=3):
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
        except Exception as e:                                       # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


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
    except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
        raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
    except Exception as e:                                           # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """平台只收本站托管的地址。返回 (ok, 归属说明)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                                # noqa: BLE001
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


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                                # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            s = " · ".join([b for b in (e.get("message") or "", e.get("code") or "") if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def payload_of(d):
    """拆信封：{"code":1,"data":{…}} / {"data":{…}} / 裸对象，三种都兜住。"""
    if not isinstance(d, dict):
        return {}
    if d.get("code") in (0, 1) and isinstance(d.get("data"), (dict, list)):
        return d["data"]
    return d


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                                # noqa: BLE001
        return str(n)


def yuan(pts):
    return round(float(pts) / POINTS_PER_YUAN, 2)


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def today():
    return time.strftime("%Y%m%d")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dir(p):
    try:
        os.makedirs(p, exist_ok=True)
        return p
    except Exception as e:                                           # noqa: BLE001
        raise Fail("internal", "建目录失败：%s（%s）" % (p, e), EXIT_INTERNAL)


def write_text(path, text):
    ensure_dir(os.path.dirname(path) or ".")
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return path


def ledger_add(rec):
    try:
        ensure_dir(HOME_DIR)
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                                # noqa: BLE001
        pass


def gate(a, cost, basis):
    """两道闸门：超预算退 5（一个请求都不发）；没 --yes 退 4（并报要花多少）。"""
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点（%.2f 元）超过 --budget %d 点：%s。"
                   "一个请求都没发。调大 --budget（单位：点，1 元 = 100 点）再试。"
                   % (cost, yuan(cost), a.budget, basis), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实扣费约 %d 点（%.2f 元）：%s。确认请加 --yes。"
                   % (cost, yuan(cost), basis), EXIT_CONFIRM)
    return cost


def clips_for(seconds):
    """把总秒数拆成 4~15 秒的段（full_video 的单段上限）。"""
    out, left = [], int(seconds)
    while left > 0:
        take = min(VIDEO_CLIP_MAX, left)
        out.append(take)
        left -= take
    return out


def video_points(seconds, resolution):
    return VIDEO_RATES[resolution] * int(seconds)


def size_problem(req):
    """校验 gpt-image 的请求尺寸：16 的倍数 / 3:1 / 单边 3840 / 总像素区间。"""
    try:
        w, h = [int(x) for x in str(req).lower().split("x")]
    except Exception:                                                # noqa: BLE001
        return "尺寸读不出来（要写成 宽x高，例如 1152x1536）"
    if w % 16 or h % 16:
        return "宽高都要是 16 的倍数（%dx%d）" % (w, h)
    if max(w, h) / float(min(w, h)) > 3.0:
        return "长短边超过 3:1（%dx%d）" % (w, h)
    if max(w, h) > 3840:
        return "单边超过 3840（%dx%d）" % (w, h)
    total = w * h
    if total < 655360 or total > 8294400:
        return "总像素 %d 不在 655,360 ~ 8,294,400 之间（%dx%d）" % (total, w, h)
    return None


# ───────────────────────── 招生矩阵（纯本地，0 点）─────────────────────────
def _link_meta(code):
    for h in LINKS:
        if h["code"] == code:
            return h
    raise Fail("usage", "--link 取 %s" % " / ".join(LINK_ORDER), EXIT_USAGE)


def parse_sizes(s):
    s = (s or "core").strip().lower().replace("，", ",")
    if s in ("core", ""):
        return list(CORE_SIZES)
    if s == "all":
        return list(SIZE_ORDER)
    out = []
    for part in s.split(","):
        k = part.strip().lower()
        if not k:
            continue
        if k not in SIZES:
            raise Fail("usage", "--sizes 取 core / all / %s（可逗号分隔）"
                       % " / ".join(SIZE_ORDER), EXIT_USAGE)
        if k not in out:
            out.append(k)
    if not out:
        raise Fail("usage", "--sizes 不能为空（core / all / %s）"
                   % " / ".join(SIZE_ORDER), EXIT_USAGE)
    return out


def _course_meta(a, course, no):
    price = float(a.price)
    listprice = float(a.list)
    if listprice <= price:
        listprice = round(price * 1.6)
    lessons = max(1, int(a.lessons))
    per_lesson = price / float(lessons)
    return dict(no="KP%02d" % no, course=course,
                teacher=a.teacher, students=a.students, outcome=a.outcome,
                pain=a.pain, proof=a.proof, audience=a.audience,
                price="%d" % int(round(price)),
                list="%d" % int(round(listprice)),
                save="%d" % int(round(listprice - price)),
                perLesson="%d" % int(round(per_lesson)),
                offer=a.offer, chapters=int(a.chapters), lessons=lessons,
                days=int(a.days), platform=a.platform)


def _copy(c, link):
    """一门课 x 一个环节 = 一条招生素材的招生话术（前 3 秒 / 主标 / 副标 / 行动号召）。"""
    if link["code"] == "L1":
        return dict(line="%s，卡在哪一步说不清" % c["pain"],
                    headline="%s" % c["pain"][:12],
                    subline="缺的不是技术，是接单流程",
                    cta="先领 3 节试听")
    if link["code"] == "L2":
        return dict(line="%s，带过 %s 名学员" % (c["teacher"], c["students"]),
                    headline="%s" % c["teacher"][:12],
                    subline="带过 %s 名学员" % c["students"],
                    cta="私信领讲师作品集")
    if link["code"] == "L3":
        return dict(line="%d 章 %d 节，每节都留交付物" % (c["chapters"], c["lessons"]),
                    headline="%d 章 %d 节" % (c["chapters"], c["lessons"]),
                    subline="每节都有交付物，做完就是作品",
                    cta="领完整大纲")
    if link["code"] == "L4":
        return dict(line="早鸟 %s 元，原价 %s 元" % (c["price"], c["list"]),
                    headline="早鸟 %s 元" % c["price"],
                    subline="原价 %s，摊到每节 %s 元" % (c["list"], c["perLesson"]),
                    cta="锁早鸟名额")
    return dict(line="今天进群，先领 3 节试听课",
                headline="今天进群领试听",
                subline="%s，先到先得" % c["offer"],
                cta="加微信进群")


def _link_prompt(c, link, size):
    scene = {
        "L1": "一个人对着电脑停住的瞬间，情绪真实不夸张，画面上方留白放标题",
        "L2": "讲师半身像，工作场景背景，专业但不端着，光源在一侧",
        "L3": "课程大纲的排版构图，章节条从上到下，留出可以叠字的空白区块",
        "L4": "价格牌构图，主价格居中，两侧留白放原价与单节价",
        "L5": "手机屏幕里的社群入口构图，二维码位留白，桌面散落笔记",
    }[link["code"]]
    return ("知识付费招生素材，%s，%s，%s 比例，真实质感，主体占画面六成，"
            "画面无文字无水印（文字后期排版叠上去），%s"
            % (c["course"], scene, size["ratio"], size["safe"]))


def _cover_prompt(c, size):
    return ("知识付费课程封面，%s，主题「%s」，一个人物剪影或讲师半身，"
            "强对比光线，%s 比例，画面无文字无水印，%s"
            % (c["course"], c["outcome"], size["ratio"], size["safe"]))


def _witness_prompt(c, size, no):
    return ("学员见证配图第 %d 张，%s 的学员真实状态，桌面有线稿与笔记，"
            "构图偏左留出右侧竖排版位放引用语与结果数字，%s 比例，"
            "画面无文字无水印，光线自然" % (no, c["course"], size["ratio"]))


def _outline_prompt(c, size):
    return ("课程大纲长图底版，%s，%d 章 %d 节的结构化版式，分章色块从上到下，"
            "每章留出标题与要点两行空白，%s 比例，画面无文字无水印，留白充足"
            % (c["course"], c["chapters"], c["lessons"], size["ratio"]))


def _price_prompt(c, size):
    return ("知识付费价格锚点卡底版，%s，中间一个价格牌位，左侧放原价、右侧放单节价，"
            "背景干净渐层，%s 比例，画面无文字无水印，留出叠字空间"
            % (c["course"], size["ratio"]))


def _video_prompt(c, link, size, seconds):
    s = int(seconds)
    head = "0-3 秒 %s 的真实处境特写，人物动作与表情" % c["pain"]
    mid = "3-9 秒 课程交付物与大纲界面特写，%d 章 %d 节逐条出现" % (c["chapters"],
                                                              c["lessons"])
    tail = "9-%d 秒 讲师出镜说一句话，画面定格在课程封面" % s
    return ("竖屏招生短视频，%s，%s，%s，镜头稳定，真实质感，画面无文字无水印，"
            "整段 %d 秒内" % (head, mid, tail, s))


def private_scripts(c):
    """私域承接话术 5 条：加微 / 进群 / 试听 / 催单 / 复购。"""
    return [
        dict(topic="加微", when="第一次加上好友的 10 分钟内",
             say="你好，我是 %s 的助教。刚给你发了 3 节试听课，先看第 1 节，"
                 "看完回我一句「看完第 1 节」，我给你标一下你的起点。" % c["course"]),
        dict(topic="进群", when="对方回了第一句话之后",
             say="训练营群 %d 天内每天 20:00 有答疑，进群先把昵称改成「行业-目标」，"
                 "助教按这个分组，作业也按组批。" % c["days"]),
        dict(topic="试听", when="对方说「再看看」的时候",
             say="试听不用全看完，先看第 2 节（%s 的关键一步），那一节决定你适不适合"
                 "这套方法，不合适我不劝。" % c["outcome"]),
        dict(topic="催单", when="开营前 48 小时",
             say="%s 还剩最后几个名额，%s 开营后回到原价 %s 元；"
                 "不确定就先领试听，看完再定。" % (c["offer"], c["course"], c["list"])),
        dict(topic="复购", when="结营后第 30 天",
             say="结营第 30 天回访，把作品发我，我按接单难度给你排下一条；"
                 "老学员带一个新学员，双方各加 1 次作业批改。"),
    ]


WEEK = [
    ("D1", "周一", "小红书", "3x4", "痛点封面 + L1 图文", "封面 1 张 + L1 一张",
     "评论置顶领试听", "点击 / 收藏"),
    ("D2", "周二", "视频号", "9x16", "痛点短视频 + L2 讲师背书", "视频 1 条 + L2 一张",
     "私信发大纲", "完播 / 私信数"),
    ("D3", "周三", "社群 / 朋友圈", "1x1", "L4 价格锚点", "L4 一张",
     "锁早鸟名额", "咨询数"),
    ("D4", "周四", "小红书", "3x4", "学员见证合集", "见证 3 张",
     "引导看评论区", "收藏 / 关注"),
    ("D5", "周五", "视频号", "9x16", "课程大纲图 + 直播预约", "大纲图 1 张",
     "预约直播", "预约数"),
    ("D6", "周六", "社群", "1x1", "L5 行动号召 + 开营倒计时", "L5 一张",
     "加微进群", "进群数"),
    ("D7", "周日", "全平台", "-", "复盘：留两条跑量，其余换新", "复用已交付素材",
     "换 2 条承接话术", "转化率 / 客单价"),
]


def build_plan(a):
    courses = [s.strip() for s in (a.course or []) if s.strip()]
    if not courses:
        raise Fail("usage", "先给 --course（课程 / 专栏 / 训练营名，可重复给多个），例如 "
                   "--course \"AI 短剧变现训练营\"", EXIT_USAGE)
    links = [_link_meta(h) for h in (a.links.split(",") if a.links else LINK_ORDER)]
    sizes = parse_sizes(a.sizes)
    version = max(1, int(a.version))
    seconds = max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, int(a.seconds)))
    witnesses = max(0, min(9, int(a.witness)))

    assets, no = [], 0
    for i, course in enumerate(courses, 1):
        c = _course_meta(a, course, i)
        for lk in links:
            cp = _copy(c, lk)
            for key in sizes:
                no += 1
                size = SIZES[key]
                name = "%s-%s_%s_v%d" % (c["no"], lk["code"], key, version)
                assets.append({
                    "no": no, "kind": "link", "courseNo": c["no"], "course": course,
                    "link": lk["code"], "linkName": lk["name"], "linkWhy": lk["why"],
                    "size": key, "ratio": size["ratio"], "requestSize": size["req"],
                    "publishSize": size["publish"], "platforms": size["platforms"],
                    "safe": size["safe"], "version": "v%d" % version,
                    "headline": cp["headline"], "subline": cp["subline"],
                    "line": cp["line"], "cta": cp["cta"],
                    "imagePrompt": _link_prompt(c, lk, size),
                    "videoPrompt": _video_prompt(c, lk, size, seconds),
                    "seconds": seconds,
                    "filename": name + ".png",
                    "videoName": name + ".mp4",
                    "voiceName": name + "_voice.mp3",
                })
        # 封面：三个核心版位，各一张
        for key in CORE_SIZES:
            no += 1
            size = SIZES[key]
            assets.append({
                "no": no, "kind": "cover", "courseNo": c["no"], "course": course,
                "link": "L1", "linkName": "封面", "size": key, "ratio": size["ratio"],
                "requestSize": size["req"], "publishSize": size["publish"],
                "platforms": size["platforms"], "safe": size["safe"],
                "version": "v%d" % version,
                "headline": c["pain"][:12], "subline": c["outcome"][:20],
                "line": "封面 3 秒：先给处境再给结果", "cta": "评论区领试听",
                "imagePrompt": _cover_prompt(c, size), "videoPrompt": "",
                "seconds": seconds,
                "filename": "cover_%s_v%d.png" % (key, version),
                "videoName": "", "voiceName": "",
            })
        # 学员见证：3 张 3:4 排版
        for w in range(1, witnesses + 1):
            no += 1
            size = SIZES["3x4"]
            assets.append({
                "no": no, "kind": "witness", "courseNo": c["no"], "course": course,
                "link": "L2", "linkName": "学员见证", "size": "3x4",
                "ratio": size["ratio"], "requestSize": size["req"],
                "publishSize": size["publish"], "platforms": "小红书 / 社群",
                "safe": size["safe"], "version": "v%d" % version,
                "headline": "学员第 %d 条" % w, "subline": c["proof"][:20],
                "line": c["proof"], "cta": "私信看完整复盘",
                "imagePrompt": _witness_prompt(c, size, w), "videoPrompt": "",
                "seconds": seconds,
                "filename": "witness%02d_3x4_v%d.png" % (w, version),
                "videoName": "", "voiceName": "",
            })
        # 大纲图 + 价格锚点卡
        for kind, key, name, prompt, head in (
                ("outline", "9x16", "outline_9x16_v%d.png" % version, _outline_prompt,
                 "%d 章 %d 节" % (c["chapters"], c["lessons"])),
                ("price", "1x1", "price_1x1_v%d.png" % version, _price_prompt,
                 "早鸟 %s 元" % c["price"])):
            no += 1
            size = SIZES[key]
            assets.append({
                "no": no, "kind": kind, "courseNo": c["no"], "course": course,
                "link": "L3" if kind == "outline" else "L4",
                "linkName": "课程大纲" if kind == "outline" else "价格锚点",
                "size": key, "ratio": size["ratio"], "requestSize": size["req"],
                "publishSize": size["publish"], "platforms": size["platforms"],
                "safe": size["safe"], "version": "v%d" % version,
                "headline": head, "subline": c["outcome"][:20],
                "line": c["outcome"], "cta": "领大纲" if kind == "outline" else "锁名额",
                "imagePrompt": prompt(c, size), "videoPrompt": "",
                "seconds": seconds, "filename": name,
                "videoName": "", "voiceName": "",
            })

    n_matrix = len(courses) * len(links) * len(sizes)
    static_pts = IMG_POINTS * len(assets)
    vid_pts = video_points(seconds, a.resolution) * len(courses)
    tts_chars = int(a.tts_chars)
    tts_pts = int(round(tts_chars * TTS_PER_CHAR)) * len(courses)
    music_pts = MUSIC_FLOOR * len(courses)
    full = static_pts + vid_pts + tts_pts + music_pts

    deliverables = [
        ("招生素材", "%d 环节 x %d 版位 / png / 上架尺寸见矩阵" % (len(links), len(sizes)),
         n_matrix, "%s-L1_%s_v%d.png" % (courses and "KP01", sizes[0], version)),
        ("封面（3 秒抓人）", "3:4 / 9:16 / 1:1 各一张", 3 * len(courses),
         "cover_%s_v%d.png" % (CORE_SIZES[0], version)),
        ("学员见证排版", "3:4 / 头像 + 一句话 + 结果数字", witnesses * len(courses),
         "witness01_3x4_v%d.png" % version),
        ("课程大纲图", "9:16 / 章节条 + 每章交付物", len(courses),
         "outline_9x16_v%d.png" % version),
        ("价格锚点卡", "1:1 / 原价 + 早鸟价 + 每节价", len(courses),
         "price_1x1_v%d.png" % version),
        ("痛点短视频", "9:16 / H.264 / %d 秒 / %s" % (seconds, a.resolution),
         len(courses), "pain_9x16_v%d.mp4" % version),
        ("讲师背书口播", "mp3 / 单条约 %d 字" % tts_chars, len(courses),
         "teacher_voice.mp3"),
        ("招生配乐", "30 秒循环 / 一条素材复用", 1, "bgm.mp3"),
        ("私域承接话术", "加微 / 进群 / 试听 / 催单 / 复购", 5, "私域承接话术.md"),
        ("一周内容排期", "7 天 x 平台 x 素材 x 承接动作", 1, "一周排期.csv"),
        ("招生链路看板", "5 环节的素材 / 成本 / 缺口一览", 1, "招生链路.md"),
    ]
    return {"ok": True, "generatedAt": now_iso(), "courses": courses,
            "links": [h["code"] for h in links], "sizes": sizes,
            "version": "v%d" % version, "seconds": seconds,
            "resolution": a.resolution, "witnessPer": witnesses,
            "assets": assets,
            "deliverables": [{"name": n, "spec": s, "count": c, "naming": f}
                             for n, s, c, f in deliverables],
            "privateScripts": private_scripts(_course_meta(a, courses[0], 1)),
            "week": [dict(day=d, weekday=w, platform=p, size=s, theme=t, asset=ast,
                          action=act, metric=m)
                     for d, w, p, s, t, ast, act, m in WEEK],
            "totals": {"assets": len(assets), "matrix": n_matrix,
                       "courses": len(courses), "links": len(links),
                       "sizes": len(sizes), "seconds": seconds,
                       "resolution": a.resolution,
                       "imagePoints": static_pts, "videoCount": len(courses),
                       "videoPoints": vid_pts, "ttsChars": tts_chars,
                       "ttsPoints": tts_pts, "musicPoints": music_pts,
                       "estimatedPoints": static_pts, "yuan": yuan(static_pts),
                       "fullPoints": full, "fullYuan": yuan(full)}}


def plan_markdown(plan):
    L = []
    L.append("# 知识付费招生 · 当天交付单（%s）" % today())
    L.append("")
    L.append("课程：%s　｜　环节：%s　｜　版位：%s　｜　版本：%s"
             % ("、".join(plan["courses"]), " / ".join(plan["links"]),
                " / ".join(plan["sizes"]), plan["version"]))
    L.append("")
    t = plan["totals"]
    L.append("静态素材 %d 张（链路 %d 条 + 封面 3 + 见证 %d + 大纲 1 + 价格卡 1），"
             "视频 1 条 %d 秒" % (t["assets"], t["matrix"], plan["witnessPer"],
                                 t["seconds"]))
    L.append("")
    L.append("## 交付清单")
    L.append("")
    L.append("| # | 交付物 | 规格 | 数量 | 命名 |")
    L.append("|---|---|---|---|---|")
    for i, d in enumerate(plan["deliverables"], 1):
        L.append("| %d | %s | %s | %d | %s |"
                 % (i, d["name"], d["spec"], d["count"], d["naming"]))
    L.append("")
    L.append("## 招生链路矩阵（5 环节 x 版位）")
    L.append("")
    L.append("| # | 课程 | 环节 | 版位 | 平台 | 上架尺寸 | 命名 |")
    L.append("|---|---|---|---|---|---|---|")
    for x in plan["assets"]:
        if x["kind"] != "link":
            continue
        L.append("| %d | %s | %s %s | %s | %s | %s | %s |"
                 % (x["no"], x["course"], x["link"], x["linkName"], x["size"],
                    x["platforms"], x["publishSize"], x["filename"]))
    L.append("")
    L.append("## 每条素材的招生话术（前 3 秒 / 主标 / 副标 / 行动号召）")
    L.append("")
    for x in plan["assets"]:
        if x["kind"] != "link":
            continue
        L.append("### %02d · %s · %s %s · %s"
                 % (x["no"], x["course"], x["link"], x["linkName"], x["size"]))
        L.append("")
        L.append("- 前 3 秒：%s" % x["line"])
        L.append("- 主标：%s（不超过 12 字）" % x["headline"])
        L.append("- 副标：%s（不超过 20 字）" % x["subline"])
        L.append("- 行动号召：%s" % x["cta"])
        L.append("- 出图提示词：%s" % x["imagePrompt"])
        L.append("- 视频提示词：%s" % x["videoPrompt"])
        L.append("")
    L.append("## 封面 / 见证 / 大纲 / 价格卡（同一门课的第二层素材）")
    L.append("")
    L.append("| 类型 | 版位 | 命名 | 出图提示词 |")
    L.append("|---|---|---|---|")
    for x in plan["assets"]:
        if x["kind"] == "link":
            continue
        L.append("| %s | %s | %s | %s |"
                 % (x["linkName"], x["size"], x["filename"], x["imagePrompt"]))
    L.append("")
    L.append("## 私域承接话术（5 条，按顺序发）")
    L.append("")
    for i, p in enumerate(plan["privateScripts"], 1):
        L.append("**%d. %s** —— 时机：%s" % (i, p["topic"], p["when"]))
        L.append("")
        L.append("> %s" % p["say"])
        L.append("")
    L.append("## 成本预估（1 元 = 100 点）")
    L.append("")
    L.append("| 项 | 本次计入 | 全量 | 口径 |")
    L.append("|---|---|---|---|")
    L.append("| 静态素材 %d 张 | %s | %s | 6 点/张（与尺寸无关） |"
             % (t["assets"], fmt_pts(t["imagePoints"]), fmt_pts(t["imagePoints"])))
    L.append("| 痛点视频 %d 条 x %d 秒 | 0 | %s | %d 点/秒 x %d 秒 |"
             % (t["videoCount"], t["seconds"], fmt_pts(t["videoPoints"]),
                VIDEO_RATES[t["resolution"]], t["seconds"]))
    L.append("| 讲师口播 %d 条 | 0 | %s | %d 字 x 0.18 点/字 |"
             % (t["videoCount"], fmt_pts(t["ttsPoints"]), t["ttsChars"]))
    L.append("| 配乐 1 首 | 0 | %s | 50 点起/首 |"
             % fmt_pts(t["musicPoints"]))
    L.append("| **合计** | **%s（%.2f 元）** | **%s（%.2f 元）** | 本次 = 只做图文；"
             "全量 = 加视频、口播、配乐 |"
             % (fmt_pts(t["estimatedPoints"]), t["yuan"],
                fmt_pts(t["fullPoints"]), t["fullYuan"]))
    L.append("")
    L.append("本次只计图文：%d 张 x 6 点 = %s 点 = %.2f 元。"
             % (t["assets"], fmt_pts(t["imagePoints"]), yuan(t["imagePoints"])))
    L.append("整套招生包（含 15 秒视频、%d 字口播、配乐）= %s 点 = %.2f 元。"
             % (t["ttsChars"], fmt_pts(t["fullPoints"]), t["fullYuan"]))
    L.append("")
    L.append("## 一周内容排期")
    L.append("")
    L.append("| 日 | 周 | 平台 | 版位 | 主题 | 素材 | 承接动作 | 观察指标 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for w in plan["week"]:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (w["day"], w["weekday"], w["platform"], w["size"], w["theme"],
                    w["asset"], w["action"], w["metric"]))
    L.append("")
    return "\n".join(L) + "\n"


def matrix_csv(plan):
    L = ["素材名,类型,课程编号,课程,环节,环节名,版位,比例,请求尺寸,上架尺寸,平台,版本,"
         "主标,副标,行动号召,状态"]
    for x in plan["assets"]:
        L.append(",".join(['"%s"' % str(v).replace('"', "'") for v in (
            x["filename"], x["kind"], x["courseNo"], x["course"], x["link"],
            x["linkName"], x["size"], x["ratio"], x["requestSize"],
            x["publishSize"], x["platforms"], x["version"], x["headline"],
            x["subline"], x["cta"], "待出图")]))
    return "\n".join(L) + "\n"


def week_csv(plan):
    L = ["日期,星期,平台,版位,主题,素材,承接动作,观察指标"]
    for w in plan["week"]:
        L.append(",".join(['"%s"' % str(w[k]).replace('"', "'") for k in (
            "day", "weekday", "platform", "size", "theme", "asset", "action",
            "metric")]))
    return "\n".join(L) + "\n"


def private_md(plan):
    L = ["# 私域承接话术（%s）" % today(), ""]
    for i, p in enumerate(plan["privateScripts"], 1):
        L.append("## %d. %s" % (i, p["topic"]))
        L.append("")
        L.append("- 时机：%s" % p["when"])
        L.append("- 原话：%s" % p["say"])
        L.append("")
    L.append("> 五条按顺序发：加微给东西、进群给规则、试听给筛子、催单给事实、复购给路径。")
    L.append("")
    return "\n".join(L) + "\n"


def linkboard_md(plan):
    t = plan["totals"]
    L = ["# 招生链路看板（%s）" % today(), ""]
    L.append("| 环节 | 一句话作用 | 素材数 | 单价 | 小计 |")
    L.append("|---|---|---|---|---|")
    for code in LINK_ORDER:
        meta = _link_meta(code)
        n = len([x for x in plan["assets"]
                 if x["kind"] == "link" and x["link"] == code])
        if n == 0:
            continue
        L.append("| %s %s | %s | %d | 6 点/张 | %s 点 |"
                 % (code, meta["name"], meta["why"], n, fmt_pts(n * IMG_POINTS)))
    cover_n = len([x for x in plan["assets"] if x["kind"] == "cover"])
    wit_n = len([x for x in plan["assets"] if x["kind"] == "witness"])
    other_n = len([x for x in plan["assets"] if x["kind"] in ("outline", "price")])
    L.append("| 封面 | 3 秒抓人，决定点不点进来 | %d | 6 点/张 | %s 点 |"
             % (cover_n, fmt_pts(cover_n * IMG_POINTS)))
    L.append("| 学员见证 | 用别人的结果换信任 | %d | 6 点/张 | %s 点 |"
             % (wit_n, fmt_pts(wit_n * IMG_POINTS)))
    L.append("| 大纲 + 价格卡 | 看清拿什么、多少钱 | %d | 6 点/张 | %s 点 |"
             % (other_n, fmt_pts(other_n * IMG_POINTS)))
    L.append("")
    L.append("合计 %d 张 = %s 点 = %.2f 元；加视频、口播、配乐整套 %s 点 = %.2f 元。"
             % (t["assets"], fmt_pts(t["imagePoints"]), t["yuan"],
                fmt_pts(t["fullPoints"]), t["fullYuan"]))
    L.append("")
    L.append("缺环节时先补素材再投流：链路少一环，转化就在那一环断掉。")
    L.append("")
    return "\n".join(L) + "\n"


def cmd_plan(a, key, host):
    plan = build_plan(a)
    outdir = a.outdir or os.path.join(HOME_DIR, today())
    jp = os.path.join(outdir, "plan.json")
    dp = os.path.join(outdir, "交付清单.md")
    mp = os.path.join(outdir, "招生素材矩阵.csv")
    wp = os.path.join(outdir, "一周排期.csv")
    pp = os.path.join(outdir, "私域承接话术.md")
    lp = os.path.join(outdir, "招生链路.md")
    write_text(jp, json.dumps(plan, ensure_ascii=False, indent=1))
    write_text(dp, plan_markdown(plan))
    write_text(mp, matrix_csv(plan))
    write_text(wp, week_csv(plan))
    write_text(pp, private_md(plan))
    write_text(lp, linkboard_md(plan))
    out = {"ok": True, "mode": "plan", "courses": len(plan["courses"]),
           "assets": len(plan["assets"]), "matrix": plan["totals"]["matrix"],
           "version": plan["version"],
           "estimatedPoints": plan["totals"]["estimatedPoints"],
           "yuan": plan["totals"]["yuan"],
           "fullPoints": plan["totals"]["fullPoints"],
           "fullYuan": plan["totals"]["fullYuan"],
           "files": {"plan": jp, "delivery": dp, "matrix": mp, "week": wp,
                     "private": pp, "linkboard": lp}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    t = plan["totals"]
    print("招生矩阵 · %d 条链路素材（%d 课程 x %d 环节 x %d 版位，%s），"
          "静态素材共 %d 张"
          % (t["matrix"], t["courses"], t["links"], t["sizes"], plan["version"],
             t["assets"]))
    print("=" * 92)
    print("  %s %s %s %s %s" % (pad("#", 3), pad("课程", 16), pad("环节", 14),
                                pad("版位", 8), "命名"))
    print("  " + "-" * 88)
    rows = [x for x in plan["assets"] if x["kind"] == "link"]
    for i, x in enumerate(rows[:15], 1):
        print("  %s %s %s %s %s" % (pad(i, 3), pad(x["course"][:14], 16),
                                    pad("%s %s" % (x["link"], x["linkName"]), 14),
                                    pad(x["size"], 8), x["filename"]))
    if len(rows) > 15:
        print("  …… 其余 %d 条见 招生素材矩阵.csv" % (len(rows) - 15))
    print()
    cnt = {}
    for x in plan["assets"]:
        cnt[x["kind"]] = cnt.get(x["kind"], 0) + 1
    print("  交付：%d 张静态（链路 %d + 封面 %d + 见证 %d + 大纲 %d + 价格卡 %d）"
          % (t["assets"], cnt.get("link", 0), cnt.get("cover", 0),
             cnt.get("witness", 0), cnt.get("outline", 0), cnt.get("price", 0)))
    print("        %d 条 %d 秒痛点视频 / %d 段讲师口播 / %d 首配乐 / 5 条私域话术 / 一周排期"
          % (t["videoCount"], t["seconds"], t["videoCount"], t["courses"]))
    print("  本次预算：%s 点 = %.2f 元（只算静态，6 点/张）"
          % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    print("  整套含视频口播配乐：%s 点 = %.2f 元"
          % (fmt_pts(t["fullPoints"]), t["fullYuan"]))
    print()
    print("  已写：")
    for p in (jp, dp, mp, wp, pp, lp):
        print("    %s" % p)
    print()
    print("  下一步（0 点）：`qc --plan %s` 过一遍检查，再 `img` / `film` 按矩阵出。" % jp)
    return 0


def cmd_qc(a, key, host):
    problems = []

    def bad(scope, what, tag):
        problems.append({"scope": scope, "problem": what, "tag": tag})

    plan = None
    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "找不到 plan.json：%s（先跑 plan）" % a.plan, EXIT_USAGE)
        plan = json.load(io.open(a.plan, encoding="utf-8"))
        assets = plan.get("assets") or []
    elif a.text:
        assets = [{"no": 1, "kind": "link", "course": "手工文案", "courseNo": "KP01",
                   "link": "L1", "linkName": "痛点", "size": "3x4",
                   "requestSize": "1152x1536", "version": "v1",
                   "headline": a.text, "subline": a.text, "line": a.text,
                   "cta": a.text, "filename": "KP01-L1_3x4_v1.png"}]
    else:
        raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\" 再检查", EXIT_USAGE)
    if not assets:
        raise Fail("usage", "这份 plan 里没有素材，先补 --course 再生成", EXIT_USAGE)

    # 1) 收益承诺 / 绝对化用语（知识付费招生的高压线）
    for x in assets:
        blob = " ".join([x.get("headline") or "", x.get("subline") or "",
                         x.get("line") or "", x.get("cta") or ""])
        hits = [w for w in FORBIDDEN_WORDS if w in blob]
        if hits:
            bad("%02d 文案" % x.get("no", 0), "收益承诺或绝对化用语：%s" % "、".join(hits),
                "promise")

    # 2) 价格锚点：每门课至少一条带「N 元」
    by_course = {}
    for x in assets:
        by_course.setdefault(x.get("courseNo") or x.get("course") or "-", []).append(x)
    for k, group in (by_course.items() if plan is not None else []):
        has = False
        for x in group:
            blob = " ".join([x.get("headline") or "", x.get("subline") or "",
                             x.get("line") or ""])
            if re.search(r"\d+\s*元|早鸟|原价", blob):
                has = True
                break
        if not has:
            bad("%s 课程" % k, "没有一条素材报价格（价格锚点环节要带「N 元」）", "price")

    # 3) 环节差异 + 前 3 秒长度
    seen_lines = {}
    for x in assets:
        if x.get("kind") != "link":
            continue
        ln = (x.get("line") or "").strip()
        if ln and ln in seen_lines and seen_lines[ln] != x.get("link"):
            bad("环节 %s" % x.get("link"),
                "台词和 %s 完全一样，五个环节会互相打架" % seen_lines[ln], "link")
        if ln:
            seen_lines[ln] = x.get("link")
        if len(ln) > 24:
            bad("%02d 前 3 秒" % x.get("no", 0),
                "台词 %d 字，3 秒念不完（控制在 24 字内）" % len(ln), "link")

    # 4) 私域承接：每条要有动作词，plan 里 5 条话术齐全
    for x in assets:
        if not any(w in (x.get("cta") or "") for w in CTA_WORDS):
            bad("%02d 行动号召" % x.get("no", 0),
                "结尾没有承接动作（加微 / 进群 / 领 / 试听 / 扫码）", "private")
    if plan is not None:
        ps = plan.get("privateScripts") or []
        topics = set(p.get("topic") for p in ps)
        need = set(t for t, _ in PRIVATE_TOPICS)
        if len(ps) < 5 or not need.issubset(topics):
            bad("私域", "承接话术只有 %d 条，缺：%s"
                % (len(ps), "、".join(sorted(need - topics)) or "无"), "private")

    # 5) 封面字重：主标 12 字内、副标 20 字内
    for x in assets:
        if len(x.get("headline") or "") > 12:
            bad("%02d 主标" % x.get("no", 0),
                "主标 %d 字，封面上超过 12 字就挤（改成更短的一句）"
                % len(x.get("headline") or ""), "copy")
        if len(x.get("subline") or "") > 20:
            bad("%02d 副标" % x.get("no", 0),
                "副标 %d 字，超过 20 字会在小尺寸上糊成一团"
                % len(x.get("subline") or ""), "copy")

    # 6) 命名规范
    PATTERNS = {
        "link": r"^KP\d{2}-L\d_\d+x\d+_v\d+\.(png|jpg|jpeg|webp)$",
        "cover": r"^cover_\d+x\d+_v\d+\.(png|jpg|jpeg|webp)$",
        "witness": r"^witness\d{2}_\d+x\d+_v\d+\.(png|jpg|jpeg|webp)$",
        "outline": r"^outline_\d+x\d+_v\d+\.(png|jpg|jpeg|webp)$",
        "price": r"^price_\d+x\d+_v\d+\.(png|jpg|jpeg|webp)$",
    }
    for x in assets:
        pat = PATTERNS.get(x.get("kind") or "link")
        fn = x.get("filename") or ""
        if pat and not re.match(pat, fn):
            bad("%02d 命名" % x.get("no", 0), "不符合命名规范：%s" % fn, "naming")

    # 7) 尺寸合规
    for x in assets:
        prob = size_problem(x.get("requestSize"))
        if prob:
            bad("%02d 尺寸" % x.get("no", 0), prob, "size")
        if not SIZES.get(x.get("size")):
            bad("%02d 尺寸" % x.get("no", 0), "版位代号 %s 不在五档里" % x.get("size"),
                "size")

    # 8) 链路完整：每个课程 x 环节 x 版位都要有一条，版本统一
    if plan is not None:
        courses = plan.get("courses") or []
        sizes = plan.get("sizes") or []
        links = plan.get("links") or []
        rows = [x for x in assets if x.get("kind") == "link"]
        need = len(courses) * len(sizes) * len(links)
        if len(rows) != need:
            bad("矩阵", "应有 %d 条链路素材（%d 课程 x %d 版位 x %d 环节），实际 %d 条"
                % (need, len(courses), len(sizes), len(links), len(rows)), "matrix")
        seen = set((x.get("courseNo"), x.get("size"), x.get("link")) for x in rows)
        for i in range(1, len(courses) + 1):
            for s in sizes:
                for h in links:
                    if ("KP%02d" % i, s, h) not in seen:
                        bad("矩阵", "缺一条：KP%02d / %s / %s" % (i, s, h), "matrix")
        if len(set(x.get("version") for x in assets)) > 1:
            bad("版本", "同一批里混了多个版本，排期会串味", "matrix")
        if not (plan.get("week") or []):
            bad("排期", "一周排期是空的，投手拿不到发布节奏", "week")

    checks = [
        ("承诺用语", not any(p["tag"] == "promise" for p in problems),
         "月入过万 / 包就业 / 最 / 第一 换成可验证的事实"),
        ("价格锚点", not any(p["tag"] == "price" for p in problems),
         "每门课至少一条带「N 元」「早鸟」「原价」"),
        ("环节差异", not any(p["tag"] == "link" for p in problems),
         "五个环节五套说法，前 3 秒 24 字内"),
        ("私域承接", not any(p["tag"] == "private" for p in problems),
         "加微 / 进群 / 领 / 试听 / 扫码；话术 5 条齐全"),
        ("封面字重", not any(p["tag"] == "copy" for p in problems),
         "主标 12 字内、副标 20 字内"),
        ("命名规范", not any(p["tag"] == "naming" for p in problems),
         "环节码-版位_v版本，例如 KP01-L1_3x4_v1.png"),
        ("尺寸合规", not any(p["tag"] == "size" for p in problems),
         "16 的倍数 / 3:1 / 单边 3840 / 总像素 655,360~8,294,400"),
        ("链路完整", not any(p["tag"] in ("matrix", "week") for p in problems),
         "5 个环节一条不少，版本统一，一周排期在"),
    ]
    out = {"ok": not problems, "checkedAssets": len(assets),
           "problems": problems,
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("交付前检查 · %d 条（纯本地，0 点）" % len(assets))
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 12), d))
    if problems:
        print()
        print("  要改的地方：")
        for p in problems[:20]:
            print("    · %s：%s" % (p["scope"], p["problem"]))
        if len(problems) > 20:
            print("    …… 共 %d 处" % len(problems))
        print()
        print("  改完重跑：qc --plan <plan.json>")
        return EXIT_GATE
    print()
    print("  8 项全过，可以按矩阵开跑。")
    return 0


# ───────────────────────── 免费：目录与成本 ─────────────────────────
def _read_pricing(host, key):
    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    d = jloads(txt) or {}
    pr = d.get("pricing") if isinstance(d.get("pricing"), dict) else {}
    return st, pr


def _read_apps(host, key):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d = jloads(txt) or {}
    lst = d.get("data") if isinstance(d.get("data"), list) else []
    return st, lst


def _flat(pr, path):
    return (pr.get(path) or {}).get("cost")


def cmd_catalog(a, key, host):
    st, pr = _read_pricing(host, key)
    st2, apps = _read_apps(host, key)
    online = {it.get("code"): it for it in apps if isinstance(it, dict)}
    vrule = pr.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}

    rows = [
        {"step": "出图", "app": APP_IMAGE, "cmd": "img",
         "endpoint": "POST %s/images/generations" % API_PREFIX,
         "price": "%d 点/张" % IMG_POINTS,
         "note": "招生海报 / 封面 / 大纲图 / 价格卡，n 1~4 一次多图"},
        {"step": "改图", "app": APP_IMAGE, "cmd": "img --ref",
         "endpoint": "POST %s/images/edits" % API_PREFIX,
         "price": "%d 点/张" % IMG_POINTS,
         "note": "有讲师照 / 教室实拍时走这条，人脸与场景不走样"},
        {"step": "参考图", "app": APP_NANO, "cmd": "img --engine nano",
         "endpoint": "POST %s/apps/nano_banana/submit" % API_PREFIX,
         "price": "%d 点/次" % NANO_POINTS,
         "note": "异步；多机位 %d 点 x 视角数" % NANO_VIEW_POINTS},
        {"step": "痛点视频", "app": APP_VIDEO, "cmd": "film",
         "endpoint": "POST %s/apps/full_video/submit" % API_PREFIX,
         "price": "480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒",
         "note": "单段 4~15 秒，15 秒一条 1080P = 900 点"},
        {"step": "讲师口播", "app": APP_TTS, "cmd": "voice",
         "endpoint": "POST %s/apps/voice_tts/tts" % API_PREFIX,
         "price": "约 %.2f 点/字" % TTS_PER_CHAR,
         "note": "上游真实点数 x 3，以 usage.points_cost 为准"},
        {"step": "招生配乐", "app": APP_MUSIC, "cmd": "music",
         "endpoint": "POST %s/apps/media_services_33/music_generate" % API_PREFIX,
         "price": "%d 点起/首" % MUSIC_FLOOR,
         "note": "落通配：上游 x 2，保底 50 点"},
        {"step": "查进度", "app": "网关", "cmd": "status",
         "endpoint": "GET %s/tasks/<task_id>" % API_PREFIX,
         "price": "0 点", "note": "应用层 query 每查一次都是钱"},
        {"step": "传图", "app": "网关", "cmd": "upload",
         "endpoint": "POST %s/upload" % API_PREFIX,
         "price": "0 点", "note": "换 oss.gpu.likeadmin.cn 白名单地址"},
        {"step": "矩阵 / 检查", "app": "本地", "cmd": "plan / qc",
         "endpoint": "纯本地，不发请求", "price": "0 点",
         "note": "矩阵 / 话术 / 命名 / 合规 / 一周排期"},
    ]
    for r in rows:
        r["online"] = (r["app"] in online) or r["app"] in ("网关", "本地")
        r["apis"] = len(online.get(r["app"], {}).get("apis") or [])
    out = {"ok": True, "rows": rows, "appsOnline": len(apps),
           "pricingRead": st == 200,
           "nanoCost": _flat(pr, API_PREFIX + "/apps/nano_banana/submit") or NANO_POINTS,
           "uploadCost": _flat(pr, API_PREFIX + "/upload"),
           "musicFloor": (pr.get("*") or {}).get("minPoints") or MUSIC_FLOOR,
           "videoRates": live or VIDEO_RATES,
           "sizes": {k: dict(SIZES[k]) for k in SIZE_ORDER},
           "coreSizes": CORE_SIZES,
           "links": [dict(code=h["code"], name=h["name"], focus=h["focus"])
                     for h in LINKS],
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 知识付费招生 —— 一条招生链路要用的 9 个动作（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("动作", 12), pad("子命令", 19), pad("端点", 50), "单价"))
    print("  " + "-" * 116)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 12), pad(r["cmd"], 19),
                                  pad(r["endpoint"], 50), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  五个招生环节（顺序就是转化顺序）")
    for h in LINKS:
        print("    %s %s  %s" % (pad(h["code"], 4), pad(h["name"], 10), h["focus"]))
    print()
    print("  五个版位（requests 都在 gpt-image 的合法区间内）")
    print("    %s %s %s %s" % (pad("--size", 8), pad("比例", 7),
                                pad("请求 / 上架", 24), "平台"))
    print("    " + "-" * 92)
    for k in SIZE_ORDER:
        s = SIZES[k]
        mark = "  ← 一天必交" if k in CORE_SIZES else ""
        print("    %s %s %s %s%s" % (pad(k, 8), pad(s["ratio"], 7),
                                     pad("%s / %s" % (s["req"], s["publish"]), 24),
                                     s["platforms"], mark))
    print()
    print("  本站应用目录 %d 个；media_services_33 在架 %d 个接口。"
          % (len(apps), len(online.get(APP_MUSIC, {}).get("apis") or [])))
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, (live or VIDEO_RATES).get(r)) for r in RESOLUTIONS))
    print("  一天图文包 23 张 = 138 点 = 1.38 元；整套含视频口播配乐 1,099 点 = 10.99 元。")
    return 0


def cmd_cost(a, key, host):
    courses = max(1, int(a.courses))
    n_sizes = max(1, min(5, int(a.sizes)))
    n_links = max(1, min(5, int(a.links)))
    matrix = courses * n_links * n_sizes
    cover = 3 * courses
    witness = max(0, int(a.witness)) * courses
    other = 2 * courses
    images = matrix + cover + witness + other
    seconds = max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, int(a.seconds)))
    res = a.resolution
    kind = a.kind
    if kind == "image":
        videos, voices, music = 0, 0, 0
    else:
        videos = courses if kind in ("video", "mixed") else 0
        voices = max(0, int(a.voices))
        music = 1 if a.music else 0
    nano = max(0, int(a.nano))

    ipts = IMG_POINTS * (images if kind in ("image", "mixed") else 0)
    vpts = video_points(seconds, res) * videos
    tpts = int(round(voices * a.tts_chars * TTS_PER_CHAR))
    mpts = MUSIC_FLOOR * music
    npts = nano * NANO_POINTS
    total = ipts + vpts + tpts + mpts + npts

    items = [
        ("静态素材 %d 张" % (images if kind in ("image", "mixed") else 0), ipts,
         "6 点/张（与尺寸无关）"),
        ("痛点视频 %d 条 x %d 秒" % (videos, seconds), vpts,
         "%d 点/秒 x %d 秒" % (VIDEO_RATES[res], seconds)),
        ("讲师口播 %d 条" % voices, tpts,
         "%d 字/条 x 0.18 点/字" % a.tts_chars),
        ("招生配乐 %d 首" % music, mpts, "50 点起/首"),
        ("参考图 %d 次" % nano, npts, "nano_banana 72 点/次"),
    ]

    # 同一批 23 张，四种走法（知识付费最常问的一句话：图文包多少钱）
    batch = max(1, images)
    ways = [
        {"name": "全静态图文包 6 点/张", "count": batch, "points": batch * IMG_POINTS},
        {"name": "全视频 15 秒 1080P", "count": batch,
         "points": batch * video_points(min(15, VIDEO_CLIP_MAX), "1080P")},
        {"name": "一半图文 + 一半 15 秒视频", "count": batch,
         "points": (batch // 2) * IMG_POINTS
                   + (batch - batch // 2) * video_points(min(15, VIDEO_CLIP_MAX), "1080P")},
        {"name": "一半图文 + 一半 nano 参考图", "count": batch,
         "points": (batch // 2) * IMG_POINTS + (batch - batch // 2) * NANO_POINTS},
    ]
    for w in ways:
        w["yuan"] = yuan(w["points"])

    out = {"ok": True, "courses": courses, "sizes": n_sizes, "links": n_links,
           "matrix": matrix, "images": images, "videos": videos, "kind": kind,
           "seconds": seconds, "clipsPerVideo": len(clips_for(seconds)),
           "resolution": res, "voices": voices, "music": music, "nano": nano,
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": total, "yuan": yuan(total),
           "yuanPerCourse": yuan(total / float(courses)),
           "batchWays": ways,
           "unitPrice": {"image": IMG_POINTS, "nano": NANO_POINTS,
                         "ttsPerChar": TTS_PER_CHAR, "musicFloor": MUSIC_FLOOR,
                         "video": VIDEO_RATES},
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing 与流水实测（2026-11-08）",
                     "gpt-image 按张计费，与尺寸、质量、输出格式无关",
                     "full_video 按总秒数 x 分辨率计费，单段 4~15 秒",
                     "口播按上游真实点数 x 3，实测 33 字 5.94 点，按 0.18 点/字估",
                     "配乐落通配规则，50 点是下限，实际以 usage.points_cost 为准",
                     "nano_banana 72 点/次是 flat，带 views 时 25 点 x 视角数"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("招生素材要多少钱（1 元 = 100 点）")
    print()
    print("  %d 课程 x %d 环节 x %d 版位 = %d 条链路素材，静态共 %d 张；"
          "视频 %d 条 x %d 秒，%s"
          % (courses, n_links, n_sizes, matrix, images, videos, seconds, res))
    print("  " + "-" * 82)
    for n, p, b in items:
        if p:
            print("  %s %s 点   %s" % (pad(n, 30), pad(fmt_pts(p), 9, left=False), b))
    print("  " + "-" * 82)
    print("  %s %s 点   = %.2f 元"
          % (pad("合计", 30), pad(fmt_pts(total), 9, left=False), yuan(total)))
    print()
    print("  同一批 %d 张，四种走法（知识付费最常问的一句话）" % batch)
    print("    %s %s %s %s" % (pad("走法", 30), pad("数量", 6, left=False),
                                pad("点数", 10, left=False), pad("元", 10, left=False)))
    print("    " + "-" * 68)
    for w in ways:
        print("    %s %s %s %s" % (pad(w["name"], 30), pad(w["count"], 6, left=False),
                                    pad(fmt_pts(w["points"]), 10, left=False),
                                    pad("%.2f" % w["yuan"], 10, left=False)))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 出图（6 点/张 · nano 72 点/次）─────────────────────────
def _save_images(d, outdir, prefix, timeout=180):
    """把返回里的 b64 / url 落成 png。返回 (文件列表, 张数, 来源)。"""
    items = []
    data = d.get("data")
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("data"), list):
        items = data["data"]
    ensure_dir(outdir)
    files, src = [], None
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            continue
        b64 = it.get("b64_json") or it.get("b64") or it.get("image_base64")
        url = it.get("url") or it.get("image_url")
        path = os.path.join(outdir, "%s-%02d.png" % (prefix, i))
        if b64:
            try:
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(b64))
                files.append(path)
                src = src or "b64_json"
                continue
            except Exception:                                        # noqa: BLE001
                pass
        if url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    with open(path, "wb") as fh:
                        fh.write(r.read())
                files.append(path)
                src = src or "url"
            except Exception:                                        # noqa: BLE001
                src = src or "url"
    return files, len(files), src


def _kind_prompt(a, meta, link, size):
    """按素材类型挑提示词。"""
    kind = a.kind
    if a.prompt:
        return a.prompt.strip()
    if kind == "cover":
        return _cover_prompt(meta, size)
    if kind == "witness":
        return _witness_prompt(meta, size, max(1, int(a.witness_no)))
    if kind == "outline":
        return _outline_prompt(meta, size)
    if kind == "price":
        return _price_prompt(meta, size)
    return _link_prompt(meta, link, size)


def _kind_prefix(a, link, version):
    kind = a.kind
    if kind == "cover":
        return "cover_%s_%s" % (a.size, version)
    if kind == "witness":
        return "witness%02d_%s_%s" % (max(1, int(a.witness_no)), "3x4", version)
    if kind == "outline":
        return "outline_%s_%s" % ("9x16", version)
    if kind == "price":
        return "price_%s_%s" % ("1x1", version)
    return "%s-%s_%s_%s" % (a.course_no, link["code"], a.size, version)


def cmd_img(a, key, host):
    size = SIZES.get(a.size)
    if not size:
        raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
    link = _link_meta(a.link)
    prob = size_problem(size["req"])
    if prob:
        raise Fail("internal", "尺寸表配错了：%s" % prob, EXIT_INTERNAL)
    n = 1 if a.engine == "nano" else max(1, min(4, int(a.n)))
    meta = _course_meta(a, a.course, 1)
    prompt = _kind_prompt(a, meta, link, size)
    if not prompt:
        raise Fail("usage", "给 --course 或 --prompt（提示词不能为空）", EXIT_USAGE)
    ref_ok = None
    if a.ref:
        if a.ref.startswith("http"):
            ok, kindn = url_allowed(a.ref)
            if not ok:
                raise Fail("usage",
                           "参考图必须是平台托管地址（%s 不在白名单）。"
                           "本地图直接给路径：--ref 讲师照.jpg（会自动 upload，免费）"
                           % kindn, EXIT_USAGE)
            ref_ok = a.ref
        elif not os.path.isfile(a.ref):
            raise Fail("usage", "找不到参考图：%s" % a.ref, EXIT_USAGE)

    if a.engine == "nano":
        cost = NANO_POINTS
        basis = "参考图 1 次 x %d 点/次（nano_banana，flat）" % NANO_POINTS
        endpoint = NANO_PATH
        body = {"prompt": prompt, "model": NANO_MODEL,
                "resolution": a.nano_resolution, "aspect_ratio": size["ratio"]}
    else:
        cost = IMG_POINTS * n
        basis = "出图 %d 张 x %d 点/张（%s，%s）" % (n, IMG_POINTS, a.size, size["req"])
        endpoint = EDIT_PATH if (a.ref or ref_ok) else IMAGE_PATH
        body = {"model": APP_IMAGE, "prompt": prompt, "n": n, "size": size["req"],
                "output_format": a.output_format}
    gate(a, cost, basis)
    url = host + endpoint

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "engine": a.engine, "url": url,
               "requestBody": body, "estimatedPoints": cost, "yuan": yuan(cost),
               "kind": a.kind, "size": a.size, "requestSize": size["req"],
               "publishSize": size["publish"]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  版位：%s -> 请求 %s，上架 %s" % (a.size, size["req"], size["publish"]))
        print("  预估：%d 点（%.2f 元）· %s" % (cost, yuan(cost), basis))
        return 0

    # 本地参考图：先 upload 换白名单地址（免费）
    if a.ref and not ref_ok:
        r = upload_file(key, host, a.ref, timeout=a.timeout)
        ref_ok = r["url"]

    say("正在出招生素材（%s，%s）…" % (a.size, a.engine))
    t0 = time.time()
    if a.engine == "nano":
        if ref_ok:
            body["action"] = "edit"
            body["image_urls"] = [ref_ok]
        st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    elif ref_ok:
        fields = {"model": APP_IMAGE, "prompt": prompt, "n": str(n),
                  "size": size["req"], "output_format": a.output_format}
        st, txt = http_multipart(url, key, fields, [("image", a.ref)],
                                 timeout=a.timeout)
    else:
        st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}

    if a.engine == "nano":
        flat = payload_of(d) if isinstance(d, dict) else {}
        flat = flat if isinstance(flat, dict) else {}
        tid = flat.get("task_id") or flat.get("taskId") or flat.get("id")
        if st not in (200, 201) or not tid:
            msg = err_text(st, txt)
            ledger_add({"at": now_iso(), "ok": False, "mode": "img", "engine": "nano",
                        "http": st, "error": msg})
            raise Fail("call", "参考图提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
        ledger_add({"at": now_iso(), "ok": True, "mode": "img", "engine": "nano",
                    "taskId": tid, "size": a.size, "points": cost})
        out = {"ok": True, "engine": "nano", "taskId": tid,
               "status": flat.get("status"), "size": a.size,
               "endpoint": endpoint, "elapsed": round(dt, 1),
               "estimatedPoints": cost, "yuan": yuan(cost),
               "next": "python3 scripts/run.py status --task-id %s" % tid}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("已提交参考图任务（%.1fs）" % dt)
        print("  任务：%s   状态：%s" % (tid, flat.get("status")))
        print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % tid)
        return 0

    if st not in (200, 201):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "img", "http": st,
                    "error": msg, "size": a.size})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = a.outdir or OUT_ROOT
    prefix = _kind_prefix(a, link, "v%d" % a.version)
    files, got, src = _save_images(d, outdir, prefix, timeout=a.timeout)
    if not got:
        raise Fail("call", "响应里没有图：%s" % (txt or "")[:300], EXIT_CALL)
    billed = IMG_POINTS * got
    out = {"ok": True, "engine": "gpt", "mode": "img", "kind": a.kind,
           "size": a.size, "requestSize": size["req"],
           "publishSize": size["publish"], "requested": n, "returned": got,
           "files": files, "source": src, "prompt": prompt,
           "elapsed": round(dt, 1), "billedPoints": billed,
           "estimatedPoints": cost, "endpoint": endpoint}
    ledger_add({"at": now_iso(), "ok": True, "mode": "img", "files": files,
                "size": a.size, "points": billed, "engine": "gpt"})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%.1fs · %d 点）" % (dt, billed))
    for p in files:
        print("  文件：%s" % p)
    print("  版位：请求 %s，上架 %s（%s）"
          % (size["req"], size["publish"], size["platforms"]))
    print("  提示词：%s" % prompt)
    print()
    print("  下一步：文字用排版层叠上去（AI 出中文容易错字），再把这张交给 `film` 当首帧。")
    return 0


# ───────────────────────── 口播（约 0.18 点/字）─────────────────────────
def cmd_voice(a, key, host):
    text = (a.text or "").strip()
    if not text and a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到口播稿：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"讲师背书口播\" 或 --script 稿子.txt；"
                   "也可以先 `plan` 生成交付清单再粘过来", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；"
                   "超过就按「背书 / 大纲 / 价格」拆成两三条。"
                   % (len(text), TTS_MAX_CHARS), EXIT_USAGE)
    cost = max(1, int(round(len(text) * TTS_PER_CHAR)))
    gate(a, cost, "口播 %d 字 x 0.18 点/字（上游真实点数 x 3，以 usage.points_cost 为准）"
         % len(text))
    url = host + API_PREFIX + "/apps/" + APP_TTS + "/tts"
    body = {"text": text, "model": a.tts_model, "format": a.tts_format}
    if a.reference_id:
        body["reference_id"] = a.reference_id
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "chars": len(text), "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不合成、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（约 %.2f 元）· %d 字" % (cost, yuan(cost), len(text)))
        return 0

    say("正在合成讲师口播（%d 字）…" % len(text))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=300)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d) if isinstance(d, dict) else {}
    audio = data.get("audio_url") or data.get("audioUrl") or data.get("url")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost") or data.get("actual_points")
    if st not in (200, 201) or not audio:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "voice", "http": st,
                    "error": msg})
        raise Fail("call", "配音失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = ensure_dir(a.outdir or OUT_ROOT)
    txt_path = os.path.join(outdir, "%s-voice.txt" % (a.prefix or "teacher"))
    write_text(txt_path, text + "\n")
    out = {"ok": True, "mode": "voice", "audioUrl": audio, "chars": len(text),
           "elapsed": round(dt, 1), "textFile": txt_path,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost),
           "endpoint": API_PREFIX + "/apps/" + APP_TTS + "/tts"}
    ledger_add({"at": now_iso(), "ok": True, "mode": "voice", "chars": len(text),
                "audio": audio, "points": real if real is not None else cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已合成（%.1fs）" % dt)
    print("  音频：%s" % audio)
    print("  稿子：%s" % txt_path)
    if real is not None:
        print("  实际点数：%s（返回里的 usage.points_cost）" % fmt_pts(real))
    else:
        print("  预估点数：%d 点（约 %.2f 元）" % (cost, yuan(cost)))
    return 0


# ───────────────────────── 配乐（50 点起）─────────────────────────
def find_media_url(node, depth=0):
    if depth > 8:
        return None
    if isinstance(node, str):
        low = node.lower()
        if node.startswith("http") and any(
                x in low for x in (".mp3", ".wav", ".m4a", ".flac")):
            return node
        return None
    if isinstance(node, dict):
        for k in ("audio_url", "audioUrl", "audio", "url", "source_url", "sourceUrl"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                if any(x in v.lower() for x in (".mp3", ".wav", ".m4a", ".flac")):
                    return v
        for v in node.values():
            got = find_media_url(v, depth + 1)
            if got:
                return got
    elif isinstance(node, list):
        for v in node:
            got = find_media_url(v, depth + 1)
            if got:
                return got
    return None


def cmd_music(a, key, host):
    prompt = a.style or "轻钢琴渐强，温暖，适合 30 秒招生短片"
    cost = MUSIC_FLOOR
    gate(a, cost, "配乐 1 首，通配保底 50 点（上游 x 2，实际以 usage.points_cost 为准）")
    url = host + API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate"
    body = {"model": a.music_model, "custom_mode": False,
            "instrumental": True, "prompt": prompt}
    if a.title:
        body["title"] = a.title
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不生成、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点起（%.2f 元起）" % (cost, yuan(cost)))
        return 0

    say("正在生成招生配乐…")
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=600)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201) or (isinstance(d, dict) and d.get("code") == 0):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "music", "http": st,
                    "error": msg})
        raise Fail("call", "配乐失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    data = payload_of(d)
    audio = find_media_url(data) or find_media_url(d)
    task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost")
    out = {"ok": bool(audio or task_id), "mode": "music", "audioUrl": audio,
           "taskId": task_id, "elapsed": round(dt, 1), "style": prompt,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost)}
    ledger_add({"at": now_iso(), "ok": bool(audio or task_id), "mode": "music",
                "audio": audio, "taskId": task_id,
                "points": real if real is not None else cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if (audio or task_id) else EXIT_CALL
    if audio:
        print("已生成配乐（%.1fs）" % dt)
        print("  音频：%s" % audio)
    elif task_id:
        print("已提交配乐任务（%.1fs）" % dt)
        print("  任务：%s" % task_id)
        print("  查进度：python3 scripts/run.py status --task-id %s" % task_id)
    else:
        print("返回里没有音频地址，原始返回前 600 字：")
        print("  " + json.dumps(d, ensure_ascii=False)[:600])
        return EXIT_CALL
    if real is not None:
        print("  实际点数：%s" % fmt_pts(real))
    else:
        print("  预估点数：%d 点起（约 %.2f 元起）" % (cost, yuan(cost)))
    return 0


# ───────────────────────── 上传（免费）─────────────────────────
def upload_file(key, host, path, timeout=600):
    if not path or not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    say("正在上传 %s（%d 字节，免费）…" % (os.path.basename(path), size))
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [("file", path)],
                             timeout=timeout)
    d = jloads(txt) or {}
    data = payload_of(d)
    got = (data.get("url") or data.get("path")) if isinstance(data, dict) else None
    if st not in (200, 201) or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)),
                   EXIT_CALL)
    ok, kind = url_allowed(got)
    return {"url": got, "size": data.get("size") or size,
            "mime": data.get("mime_type"), "allowed": ok, "hostKind": kind}


def cmd_upload(a, key, host):
    if not a.file:
        raise Fail("usage", "必须给 --file（本地图片 / 视频路径）", EXIT_USAGE)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": host + UPLOAD_PATH,
               "file": a.file, "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不扣费）")
        print("  端点：POST %s（multipart，字段名 file）" % (host + UPLOAD_PATH))
        print("  文件：%s" % a.file)
        return 0
    r = upload_file(key, host, a.file, timeout=a.timeout)
    out = {"ok": True, "url": r["url"], "size": r["size"], "mime": r["mime"],
           "urlAllowed": r["allowed"], "hostKind": r["hostKind"],
           "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（0 点）")
    print("  地址：%s" % r["url"])
    print("  归属：%s（在上游白名单内，可以直接给 img --ref / film --image 用）"
          % r["hostKind"])
    return 0


# ───────────────────────── 痛点短视频（按秒计费）─────────────────────────
def cmd_film(a, key, host):
    size = SIZES.get(a.size)
    if not size:
        raise Fail("usage", "--size 取 %s" % " / ".join(SIZE_ORDER), EXIT_USAGE)
    link = _link_meta(a.link)
    meta = _course_meta(a, a.course, 1)
    text = (a.text or _video_prompt(meta, link, size, a.seconds)).strip()
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    if seconds > VIDEO_CLIP_MAX:
        raise Fail("usage", "full_video 单段 4~15 秒；%d 秒分 %s 两段提交。"
                   % (seconds, "+".join(str(x) for x in clips_for(seconds))),
                   EXIT_USAGE)
    cost = video_points(seconds, a.resolution)
    gate(a, cost, "痛点视频 %d 秒 x %d 点/秒（%s）"
         % (seconds, VIDEO_RATES[a.resolution], a.resolution))

    image_url = None
    if a.image:
        if a.image.startswith("http"):
            ok, kindn = url_allowed(a.image)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "首帧图必须是平台托管地址（%s 不在白名单）。两种写法：\n"
                           "  · 本地图直接给路径：--image cover.png"
                           "（film 会自动 upload，免费）\n"
                           "  · 本站地址：https://oss.gpu.likeadmin.cn/openapi/…"
                           % kindn, EXIT_USAGE)
            image_url = a.image
        elif not os.path.isfile(a.image):
            raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)

    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": size["ratio"],
            "aigc_watermark": False}
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    url = host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost), "size": a.size}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        if a.image and not image_url:
            print("  首帧：%s（会先用 upload 换白名单地址，免费）" % a.image)
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    if a.image and not image_url:
        r = upload_file(key, host, a.image, timeout=a.timeout)
        image_url = r["url"]
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})

    say("正在提交痛点视频（%s，%d 秒）…" % (a.resolution, seconds))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=180)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "film", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    out = {"ok": True, "mode": "film", "taskId": task_id,
           "status": data.get("status"), "resolution": a.resolution,
           "seconds": seconds, "size": a.size, "clips": clips_for(seconds),
           "firstFrame": image_url, "elapsed": round(dt, 1),
           "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost"),
           "next": "python3 scripts/run.py status --task-id %s" % task_id}
    ledger_add({"at": now_iso(), "ok": True, "mode": "film", "taskId": task_id,
                "seconds": seconds, "resolution": a.resolution, "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%s · %d 秒 · %s（%s）"
          % (a.resolution, seconds, a.size, size["ratio"]))
    if image_url:
        print("  首帧：%s" % image_url)
    print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 查任务（免费）─────────────────────────
def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + a.task_id
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    out = {"ok": True, "taskId": a.task_id, "path": path, "http": st,
           "status": None, "result": None}
    if st == 200 and d.get("code") == 0 and not d.get("data"):
        out.update({"status": "not_found", "message": d.get("msg") or "任务不存在"})
    elif st == 200:
        data = payload_of(d) if isinstance(d, dict) else {}
        data = data if isinstance(data, dict) else {}
        out.update({"status": data.get("status"), "message": data.get("message"),
                    "videoUrl": data.get("videoUrl") or data.get("video_url"),
                    "audioUrl": data.get("audioUrl") or data.get("audio_url"),
                    "cost": data.get("cost"), "refund": data.get("refund"),
                    "result": data.get("result")})
    else:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)),
                   EXIT_CALL)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  查询端点：GET %s（0 点）" % path)
    print("  状态：%s" % out.get("status"))
    if out.get("message"):
        print("  说明：%s" % str(out["message"])[:200])
    if out.get("cost") is not None:
        print("  实扣：%s 点" % fmt_pts(out["cost"]))
    if out.get("refund") is not None:
        print("  退回：%s 点" % fmt_pts(out["refund"]))
    if out.get("videoUrl"):
        print("  成片：%s（及时转存）" % out["videoUrl"])
    if out.get("audioUrl"):
        print("  音频：%s" % out["audioUrl"])
    if out.get("result") is not None:
        print("  结果：%s" % json.dumps(out["result"], ensure_ascii=False)[:600])
    return 0


# ───────────────────────── 自检（0 点）─────────────────────────
def cmd_doctor(a, key, host):
    checks = []

    st0, txt0 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d0 = jloads(txt0) or {}
    logs0 = d0.get("logs") or []
    first0 = None
    if logs0:
        row = logs0[0]
        first0 = (row.get("at"), row.get("points"), row.get("reference"))

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(d.get("available_points") or 0),
                      fmt_pts(d.get("frozen") or 0))))

    st2, txt2 = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d2 = jloads(txt2) or {}
    listing = d2.get("data") if isinstance(d2.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    need = [APP_VIDEO, APP_TTS, APP_MUSIC, APP_NANO]
    miss = [c for c in need if c not in online]
    checks.append(("4 个底层应用在架（视频 / 口播 / 配乐 / 参考图）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    music_apis = len(online.get(APP_MUSIC, {}).get("apis") or [])
    checks.append(("media_services_33 的 29 个接口齐全", music_apis >= 29,
                   "在架 %d 个接口（配乐取 music_generate）" % music_apis))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    vrule = pricing.get(API_PREFIX + "/apps/full_video/submit") or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致",
                   st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s"
                   % (st3, "5 档全一致" if not drift else " / ".join(drift)[:110])))

    nano_rule = pricing.get(API_PREFIX + "/apps/nano_banana/*") or {}
    wild = pricing.get("*") or {}
    up_rule = pricing.get(API_PREFIX + "/upload") or {}
    ok_price = (int(nano_rule.get("cost") or 0) == NANO_POINTS
                and int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost")
                        if up_rule.get("cost") is not None else 999) == 0)
    checks.append(("参考图 72 点 + 配乐保底 50 点 + upload 0 点", ok_price,
                   "nano %s · 通配保底 %s · upload %s"
                   % (nano_rule.get("cost"), wild.get("minPoints"),
                      up_rule.get("cost"))))

    st4, txt4 = http_json("POST", host + IMAGE_PATH, key,
                          {"model": APP_IMAGE, "prompt": ""}, timeout=60)
    d4 = jloads(txt4) or {}
    e4 = d4.get("error") if isinstance(d4.get("error"), dict) else {}
    msg4 = (e4.get("message") or err_text(st4, txt4))
    checks.append(("出图端点可用（422 即正确，零扣费）",
                   st4 == 422 and "prompt" in str(msg4).lower(),
                   "HTTP %s %s" % (st4, str(msg4)[:52])))

    st5, txt5 = http_json("POST", host + API_PREFIX + "/video/viapi/shot", key, {},
                          timeout=60)
    d5 = jloads(txt5) or {}
    e5 = d5.get("error") if isinstance(d5.get("error"), dict) else {}
    code5 = e5.get("code") or ""
    checks.append(("视频线在参数校验就停（400 empty_url 即正确）",
                   st5 == 400 and code5 == "empty_url",
                   "HTTP %s %s" % (st5, code5 or err_text(st5, txt5)[:40])))

    st6, txt6 = http_json("GET",
                          host + API_PREFIX + "/tasks/sanjianke-kp-doctor-probe",
                          key, timeout=40)
    d6 = jloads(txt6) or {}
    checks.append(("任务查询 GET /tasks/<id> 可用（假 id 说任务不存在）",
                   st6 == 200 and d6.get("code") == 0,
                   "HTTP %s %s" % (st6, (d6.get("msg") or "")[:40])))

    st7, txt7 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=60)
    d7 = jloads(txt7) or {}
    checks.append(("上传口 POST /upload 可用（缺 file 时提示补字段）",
                   st7 == 200 and d7.get("code") == 0,
                   "HTTP %s %s" % (st7, (d7.get("msg") or "")[:40])))

    st8, txt8 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d8 = jloads(txt8) or {}
    logs8 = d8.get("logs") or []
    first8 = None
    if logs8:
        row = logs8[0]
        first8 = (row.get("at"), row.get("points"), row.get("reference"))
    checks.append(("本轮没有新增流水（扣 0 点）", first0 == first8,
                   "自检前后最新一笔流水一致" if first0 == first8
                   else "出现新流水，请发出来排查"))

    last = None
    if logs8:
        row = logs8[0]
        last = {"at": row.get("at"), "type": row.get("type"),
                "typeName": row.get("typeName"),
                "points": row.get("points"), "balanceAfter": row.get("balanceAfter"),
                "reference": row.get("reference")}

    out = {"ok": all(c[1] for c in checks), "requests": 10,
           "estimatedPoints": 0, "yuan": 0.0, "lastLedger": last,
           "apps": need, "videoRates": live or VIDEO_RATES,
           "endpoints": {"image": host + IMAGE_PATH,
                         "edit": host + EDIT_PATH,
                         "nano": host + NANO_PATH,
                         "film": host + API_PREFIX + "/apps/" + APP_VIDEO + "/submit",
                         "tts": host + API_PREFIX + "/apps/" + APP_TTS + "/tts",
                         "music": host + API_PREFIX + "/apps/" + APP_MUSIC
                                  + "/music_generate",
                         "task": host + API_PREFIX + "/tasks/<task_id>",
                         "upload": host + UPLOAD_PATH},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（5 个只读 GET + 1 个空 prompt 422 + 1 个空 body 视频探针 + "
          "1 个缺 file 上传，全部停在扣费之前）")
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 60), dt))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("typeName") or last.get("type") or "-",
                 fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
    print("  本次自检 0 点、0 冻结：10 个请求里没有一条会建任务。")
    print()
    print("  端点：POST /images/generations（出图）· /images/edits（改图）")
    print("        POST /apps/nano_banana/submit（参考图）· "
          "/apps/full_video/submit（痛点视频）")
    print("        POST /apps/voice_tts/tts（讲师口播）· "
          "/apps/media_services_33/music_generate（配乐）")
    print("  查询：GET /api/v1/tasks/<task_id>（0 点；应用层 /query 每次都是钱）")
    return 0 if out["ok"] else EXIT_GATE


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
        mode = e.get("mode") or "-"
        what = e.get("taskId") or e.get("audio") or e.get("error") or "-"
        pts = e.get("points")
        print("  %s  %-5s %-6s %-34s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", mode,
            str(what)[:34], ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 知识付费招生（5 环节 x 3 版位 = 15 条链路素材，"
                    "走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/nano_banana/submit · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "GET %s/api/v1/tasks/<task_id>" % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 30 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="五条能力 + 端点 + 现查单价 + 版位表（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一天（一单）要多少钱，四种走法（免费）",
                       allow_abbrev=False)
    p.add_argument("--courses", type=int, default=1, help="课程数（默认 1）")
    p.add_argument("--links", type=int, default=5, help="每门课几个环节（1~5，默认 5）")
    p.add_argument("--sizes", type=int, default=3, help="每环节几个版位（1~5，默认 3）")
    p.add_argument("--witness", type=int, default=3, help="学员见证张数（默认 3）")
    p.add_argument("--kind", choices=["image", "video", "mixed"], default="image",
                   help="image 全图文 / video 全视频 / mixed 一半一半")
    p.add_argument("--seconds", type=int, default=15, help="视频单条秒数（4~15，默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="视频分辨率（默认 1080P）")
    p.add_argument("--voices", type=int, default=1, help="口播条数（默认 1）")
    p.add_argument("--tts-chars", dest="tts_chars", type=int, default=60,
                   help="每条口播字数（默认 60，约 15 秒）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1],
                   help="配乐 1 首（默认 1）")
    p.add_argument("--nano", type=int, default=0, help="nano 参考图几次（72 点/次）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="招生矩阵与交付清单（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--course", action="append",
                   help="课程 / 专栏 / 训练营名，可重复给多个")
    p.add_argument("--teacher", default="8 年影视后期讲师",
                   help="讲师背书（默认「8 年影视后期讲师」）")
    p.add_argument("--students", default="1200", help="带过的学员数（默认 1200）")
    p.add_argument("--outcome", default="30 天做出可以接单的片子",
                   help="学员拿到的结果")
    p.add_argument("--pain", default="会剪也会改，就是接不到单", help="痛点")
    p.add_argument("--proof", default="学员第 3 周接到 800 元的活",
                   help="可验证的学员结果")
    p.add_argument("--audience", default="做了 3 年剪辑的独立创作者", help="人群")
    p.add_argument("--price", type=float, default=1280, help="早鸟价（元，默认 1280）")
    p.add_argument("--list", type=float, default=2980, help="原价（元，默认 2980）")
    p.add_argument("--offer", default="早鸟价限 50 名", help="优惠形式")
    p.add_argument("--chapters", type=int, default=6, help="章节数（默认 6）")
    p.add_argument("--lessons", type=int, default=32, help="节数（默认 32）")
    p.add_argument("--days", type=int, default=30, help="训练营周期天数（默认 30）")
    p.add_argument("--platform", default="视频号 + 微信社群", help="主投平台与私域")
    p.add_argument("--witness", type=int, default=3, help="学员见证张数（默认 3）")
    p.add_argument("--sizes", default="core",
                   help="版位：core（3 个必交）/ all / 逗号列表，默认 core")
    p.add_argument("--links", default=",".join(LINK_ORDER),
                   help="环节，逗号分隔，默认 %s" % " / ".join(LINK_ORDER))
    p.add_argument("--version", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--seconds", type=int, default=15, help="视频单条秒数（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成本预估用分辨率（默认 1080P）")
    p.add_argument("--tts-chars", dest="tts_chars", type=int, default=60,
                   help="讲师口播字数（默认 60）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/knowledge-pay/<日期>）")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="交付前检查：8 项（免费，纯本地）", allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.set_defaults(fn=cmd_qc)

    def add_course_args(p):
        p.add_argument("--course", default="AI 短剧变现训练营",
                       help="课程名（拼进提示词）")
        p.add_argument("--course-no", dest="course_no", default="KP01",
                       help="课程编号，进文件名（默认 KP01）")
        p.add_argument("--teacher", default="8 年影视后期讲师", help="讲师背书")
        p.add_argument("--students", default="1200", help="带过的学员数")
        p.add_argument("--outcome", default="30 天做出可以接单的片子",
                       help="学员拿到的结果")
        p.add_argument("--pain", default="会剪也会改，就是接不到单", help="痛点")
        p.add_argument("--proof", default="学员第 3 周接到 800 元的活",
                       help="可验证的学员结果")
        p.add_argument("--audience", default="做了 3 年剪辑的独立创作者", help="人群")
        p.add_argument("--price", type=float, default=1280, help="早鸟价（元）")
        p.add_argument("--list", type=float, default=2980, help="原价（元）")
        p.add_argument("--offer", default="早鸟价限 50 名", help="优惠形式")
        p.add_argument("--chapters", type=int, default=6, help="章节数")
        p.add_argument("--lessons", type=int, default=32, help="节数")
        p.add_argument("--days", type=int, default=30, help="训练营周期天数")
        p.add_argument("--platform", default="视频号 + 微信社群", help="主投平台与私域")

    p = sub.add_parser("img", help="出招生素材（6 点/张，nano 72 点/次，要 --yes）",
                       allow_abbrev=False)
    add_course_args(p)
    p.add_argument("--kind", choices=["link", "cover", "witness", "outline", "price"],
                   default="link",
                   help="link 链路素材 / cover 封面 / witness 见证 / outline 大纲 / "
                        "price 价格卡")
    p.add_argument("--size", default="3x4",
                   help="版位：%s（默认 3x4）" % " / ".join(SIZE_ORDER))
    p.add_argument("--link", default="L1",
                   help="环节：L1 痛点 / L2 讲师背书 / L3 大纲 / L4 价格 / L5 号召")
    p.add_argument("--witness-no", dest="witness_no", type=int, default=1,
                   help="见证第几张（1~9，默认 1）")
    p.add_argument("--prompt", help="直接给提示词，覆盖内置模板")
    p.add_argument("--engine", choices=["gpt", "nano"], default="gpt",
                   help="gpt 同步 6 点/张 / nano 异步 72 点/次")
    p.add_argument("--n", type=int, default=1, help="张数 1~4（默认 1）")
    p.add_argument("--ref", help="参考图：本地路径（自动上传）或平台地址")
    p.add_argument("--output-format", dest="output_format", default="png",
                   help="png / jpeg / webp")
    p.add_argument("--nano-resolution", dest="nano_resolution", default="1K",
                   help="nano 分辨率：1K / 2K / 4K")
    p.add_argument("--version", type=int, default=1, help="版本号（默认 1）")
    p.add_argument("--outdir", help="图片目录（默认 ~/.a7w/knowledge-pay/out）")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_img)

    p = sub.add_parser("film", help="痛点短视频（按秒计费，要 --yes）",
                       allow_abbrev=False)
    add_course_args(p)
    p.add_argument("--size", default="9x16",
                   help="版位：%s（默认 9x16）" % " / ".join(SIZE_ORDER))
    p.add_argument("--link", default="L1", help="环节：L1 / L2 / L3 / L4 / L5")
    p.add_argument("--text", help="画面与运镜描述，覆盖内置模板")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_film)

    p = sub.add_parser("voice", help="讲师背书口播（约 0.18 点/字，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--text", help="口播文案（500 字内）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--tts-model", dest="tts_model", default="s2-pro", help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3",
                   help="mp3 / wav / opus")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 ID（可选）")
    p.add_argument("--prefix", default="teacher", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/knowledge-pay/out）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="招生配乐（50 点起/首，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「轻钢琴渐强，温暖」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("upload", help="上传本地图，拿白名单地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("status", help="查任务进度（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 价目 / 端点（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_qc", "cmd_log", "cmd_doctor")
LOCAL_ONLY = ("cmd_plan", "cmd_qc", "cmd_cost")      # 纯本地，没有 Key 也能跑


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    try:
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in LOCAL_ONLY:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n"
                       "注册领 Key：https://api.a7w.cn/", EXIT_USAGE)
        return a.fn(a, key or "", host)
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
