#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 教育课件（sanjianke-edu-courseware）

一门课的课件交付，不是「生成一条视频」，而是把**一节课拆成岗位能交的 5 样东西**：
分节讲稿、16:9 课件图、配音、口播视频、字幕与章节索引。本包把这件事做成一条
可核对、可续跑、能算钱的流水线。

## 四条能力线（全部为已有接口，本包只做行业包装）

  课件图   POST /api/v1/images/generations      gpt-image-2.6   6 点/张
  分节配音 POST /api/v1/apps/voice_tts/tts_async  按上游实际点数 ×3，约 0.18 点/字
  一图口播 POST /api/v1/apps/pic_lipsync/submit   mode=text，15 点/秒，单笔 50 点起
  课件出片 POST /api/v1/apps/image_human/submit   四档 10 / 15 / 30 / 60 点/输入秒

## 行业流程（本包自己的价值）

  lesson  大纲 Markdown → lesson.json：知识点 / 分节 / 讲稿 / 配图提示 / 字幕 / 章节索引 / 测验点
  deck    风格卡 + 每节配图提示词（一套课件一个色板、一个字体、一个 16:9 构图）
  board   交付清单：这个行业一节课要交哪几张图、哪几条视频、什么尺寸、什么命名
  upload  本地图片 / 音频 → 平台托管地址（免费，submit 类接口要公网可拉）
  art     出课件图（6 点/张，要 --yes）
  narrate 分节配音（要 --yes）
  talk    一图口播：image_url + 参考音色 audio_url + 文案（要 --yes）
  screen  课件图 + 配音 → 数字人视频（mode 必填，要 --yes）

## 三条实测出来的「钱与坑」

1. pic_lipsync 的档位参数真名是 `quality`（standard / fast / max），不是 mode；
   mode 只切 audio / text。text 模式省掉录音，但**省不掉参考音色** —— audio_url 仍必填。
   不传 quality 时上游按 standard 3 点/秒 收，我方 ×5 = 15 点/秒。
2. image_human 的 schema 默认是 standard、计费默认是 fast：省略 mode 会出现
   「出片按 standard、收钱按 fast」。本包 `screen --mode` 必填，永不下发省略 mode 的请求。
3. 应用层 `/query` 每轮询一次就是一次的钱（历史流水 nano_banana/query 72 点/次，
   108 次 = 7,776 点）。本包在 http 层把任何 `/query` 地址拦死，轮询只走
   GET /api/v1/tasks/{id}（只读、免费）。

## 免费子命令

  catalog  四条能力线 + 交付物矩阵 + 价目（免费）
  cost     整门课先算钱（免费）
  doctor   只读自检 Key / 应用 / 价目 / 任务查询 / 上传 / 文生图 422（免费，0 点）
  lesson / deck / board   本地拆课、风格卡、交付清单（免费，不发请求）
  upload   本地素材转托管地址（免费）
  status   查任务（免费）
  log      本地台账（免费）

## 用法

  python3 scripts/run.py lesson --outline 课程大纲.md --out lesson.json
  python3 scripts/run.py deck --lesson lesson.json
  python3 scripts/run.py board --lesson lesson.json
  python3 scripts/run.py cost --sections 8 --seconds 180
  python3 scripts/run.py art --lesson lesson.json --outdir ./课件 --yes
  python3 scripts/run.py narrate --lesson lesson.json --section 1 --outdir ./音频 --yes
  python3 scripts/run.py talk --image-url "https://oss.gpu.likeadmin.cn/openapi/..." \\
      --audio-url "https://oss.gpu.likeadmin.cn/openapi/..." --content "本节口播文案" \\
      --quality standard --yes
  python3 scripts/run.py screen --image-url "..." --audio-url "..." --duration 180 \\
      --mode fast --yes
  python3 scripts/run.py status --task-id task_xxx

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
import io
import json
import math
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

# ── GBK 编码兜底（Windows 控制台 / 管道重定向实测）────────────────────────────
# Windows 上 stdout 被重定向时按本地编码（cp936）写，个别符号编不出就整条命令崩掉。
# 这里先加 errors="replace" 兜底，正文又只用 √ / × / · 这类 GBK 也有的字符。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "edu-courseware-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-edu-courseware/%s" % VERSION
POINTS_PER_YUAN = 100

# 四条能力线的价目（2026-11-07 现查 /api/v1/pricing + 实测）
ART_MODEL = "gpt-image-2.6"
ART_POINTS = 6                      # 6 点/张，与尺寸 / 质量 / 格式无关
NARRATE_PER_CHAR = 0.18             # 0.18 点/字（33 字上游 1.98 点，我方 ×3 = 5.94）
NARRATE_MIN = 6                     # 单笔保底 6 点
TALK_PER_SEC = 15                   # pic_lipsync：standard 3 点/秒 ×5
TALK_MIN = 50                       # 单笔 50 点下限
TALK_QUALITIES = ("standard", "fast", "max")
SCREEN_RATES = {"fast": 10, "standard": 15, "2k": 30, "4k": 60}
SCREEN_MODES = ("fast", "standard", "2k", "4k")
DEFAULT_SECTION_SECONDS = 180
DEFAULT_ART_SIZE = "1536x864"       # 16:9，16 的倍数，总像素在文生图允许区间内
UPLOAD_PATH = API_PREFIX + "/upload"

# 一套课件共用一张风格卡：色板、字体、构图、禁用元素都在这里定死
STYLE = {
    "name": "黑板暖白（教研通用）",
    "palette": ["深蓝 #1F3A5F", "暖黄 #F5C542", "白色 #FFFFFF", "浅灰蓝 #E8EEF5"],
    "font": "思源黑体（商用免费）",
    "ratio": "16:9",
    "prefix": ("扁平矢量课件插画，16:9，深蓝 + 暖黄主色，浅灰蓝背景，"
               "简洁几何，无文字，无真实人脸，右上角留出标题区"),
}


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


def guard_path(method, path):
    """两条「花钱的读」在发请求之前就拦死。

    实测：GET /api/v1/apps/<app> 命中 /apps/<app>/* 的通配计价，按该应用 flat
    单价即时扣、且不退（nano_banana 72 点、dressing_diffusion 200 点）。
    应用层 /query 也是每调一次算一次钱，轮询必须走 GET /tasks/{id}。
    """
    p = (path or "").split("?")[0].rstrip("/")
    if p.endswith("/query"):
        raise Fail("usage",
                   "应用层 /query 每轮询一次就是一次的钱，本包只走 GET /api/v1/tasks/{id}"
                   "（只读、免费）。", EXIT_USAGE)
    if method.upper() == "GET" and re.match(r"^/api/v1/apps/[^/]+$", p):
        raise Fail("usage",
                   "GET 单个应用会按该应用的 flat 单价即时扣费且不退，已拦下。"
                   "要看在架能力用 GET /api/v1/apps 列表（免费）。", EXIT_USAGE)


def http_json(method, url, key, body=None, timeout=120):
    guard_path(method, urllib.parse.urlsplit(url).path)
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    # 只读 GET 带 3 次重试：网关偶尔掐连接（WinError 10054 / RemoteDisconnected）。
    # POST 一次都不重试 —— 响应丢了再发一次就可能变成两笔扣费。
    attempts = 3 if method.upper() == "GET" else 1
    last = "请求失败"
    for i in range(attempts):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except urllib.error.URLError as e:
            last = "连不上 %s：%s" % (url, e.reason)
        except Exception as e:                                   # noqa: BLE001
            last = "请求异常：%s: %s" % (type(e).__name__, e)
        if i < attempts - 1:
            time.sleep(0.5 if i == 0 else 1.2)
    raise Fail("call", last, EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=600):
    guard_path("POST", urllib.parse.urlsplit(url).path)
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


def url_allowed(u):
    """平台托管地址白名单（上传接口返回的 oss.gpu.likeadmin.cn 直通）。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                            # noqa: BLE001
        return False, "URL 解析失败"
    host = (p.hostname or "").lower()
    path = p.path or ""
    if host == "oss.gpu.likeadmin.cn" and path.startswith("/openapi/"):
        return True, "本站上传接口"
    if host == "vr.a7w.cn" or host.endswith(".a7w.cn"):
        return True, "本站"
    if host == "cdn2.jiujiushuyuan.cn" and path.startswith("/vr/"):
        return True, "本站七牛"
    return False, host or u[:60]


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


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                            # noqa: BLE001
        return str(n)


def yuan(n):
    return "%.2f 元" % (float(n) / float(POINTS_PER_YUAN))


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


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


def read_json(path, what):
    if not os.path.isfile(path):
        raise Fail("usage", "找不到%s：%s（先跑 lesson 生成）" % (what, path), EXIT_USAGE)
    try:
        d = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        raise Fail("usage", "%s 不是合法 JSON：%s（%s）" % (what, path, e), EXIT_USAGE)
    if not isinstance(d, dict) or not d.get("sections"):
        raise Fail("usage", "%s 里没有 sections，先用 lesson 生成" % path, EXIT_USAGE)
    return d


# ───────────────────────── 两道闸门 + 干跑 ─────────────────────────
def gate(a, cost, label, detail=""):
    """--budget 是点数上限；超了退 5，一个请求都不发；没 --yes 退 4。

    顺序：先算钱、先卡预算，再要确认 —— 这样用户看到的永远是「差多少点」，
    而不是「先答应再发现超预算」。
    """
    cost = int(math.ceil(cost))
    if cost > a.budget:
        raise Fail("budget",
                   "%s 预计 %d 点（%s）超过 --budget %d 点。一个请求都没发；"
                   "调大 --budget 或缩小时长 / 张数。%s"
                   % (label, cost, yuan(cost), a.budget, detail), EXIT_BUDGET)
    if not a.dry_run and not a.yes:
        raise Fail("confirm",
                   "%s 预计 %d 点（%s）。确认请加 --yes；只想看请求用 --dry-run。"
                   % (label, cost, yuan(cost)), EXIT_CONFIRM)
    return cost


def plan(a, endpoint, body, cost, label, extra=None):
    """--dry-run：打印将要发出的请求，一个都不发。"""
    out = {"ok": True, "dryRun": True, "endpoint": endpoint, "requestBody": body,
           "estimatedPoints": int(cost), "yuan": round(cost / float(POINTS_PER_YUAN), 2)}
    if extra:
        out.update(extra)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不冻结、不扣费）")
    print("  端点：POST %s" % endpoint)
    print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:600])
    print("  预估：%d 点（%s）" % (cost, yuan(cost)))
    if extra and extra.get("basis"):
        print("  口径：%s" % extra["basis"])
    return 0


# ───────────────────────── 本地：拆课 ─────────────────────────
SEC_RE = re.compile(r"^##\s+(.+?)\s*$")
ITEM_RE = re.compile(r"^[-*+]\s*(知识点|讲稿|配图|时长|测验|进度)\s*[:：]\s*(.*)$")


def clean_title(t):
    t = t.strip()
    t = re.sub(r"^第\s*[0-9一二三四五六七八九十]+\s*[节讲课]\s*[·:：.\-]?\s*", "", t)
    t = re.sub(r"^(Lesson|Chapter|Section)\s*\d+\s*[:：.\-]?\s*", "", t, flags=re.I)
    return t.strip() or "未命名分节"


def parse_seconds(txt):
    nums = re.findall(r"\d+(?:\.\d+)?", txt or "")
    if not nums:
        return None
    v = float(nums[0])
    if "分" in (txt or "") and "秒" not in (txt or ""):
        v *= 60
    return int(round(v)) if v > 0 else None


def parse_quiz(txt):
    parts = [p.strip() for p in re.split(r"[|｜]", txt or "") if p.strip()]
    if not parts:
        return None
    q = {"question": parts[0], "options": [], "answer": ""}
    for p in parts[1:]:
        m = re.match(r"^(答案|正确答案)\s*[:：]?\s*(.+)$", p)
        if m:
            q["answer"] = m.group(2).strip()
        else:
            q["options"].append(p)
    return q


def parse_outline(text, default_seconds):
    title, sections, cur = "", [], None
    for raw in text.replace("\r\n", "\n").split("\n"):
        s = raw.strip()
        if not s:
            continue
        m = SEC_RE.match(s)
        if m:
            cur = {"title": clean_title(m.group(1)), "points": [], "script": [],
                   "image": "", "seconds": None, "quiz": None, "progress": ""}
            sections.append(cur)
            continue
        if s.startswith("# ") and not title and cur is None:
            title = s[2:].strip()
            continue
        if cur is None:
            continue
        m2 = ITEM_RE.match(s)
        if m2:
            k, v = m2.group(1), m2.group(2).strip()
            if k == "知识点":
                cur["points"].extend([p.strip(" 。.；;") for p in
                                      re.split(r"[、,，;；]", v) if p.strip(" 。.；;")])
            elif k == "讲稿":
                cur["script"].append(v)
            elif k == "配图":
                cur["image"] = v
            elif k == "时长":
                cur["seconds"] = parse_seconds(v)
            elif k == "测验":
                cur["quiz"] = parse_quiz(v)
            elif k == "进度":
                cur["progress"] = v
            continue
        cur["script"].append(s)
    if not sections:
        raise Fail("usage", "大纲里没有 `## 分节` 标题，至少给一节（示例见 README）", EXIT_USAGE)
    return title, sections


def split_chunks(text, limit=16):
    """把讲稿切成字幕行：先按句末标点，再按 16 字硬切，尽量落在逗号上。"""
    parts = re.split(r"(?<=[。！？；!?;])", text or "")
    chunks = []
    for p in parts:
        p = p.strip()
        while len(p) > limit:
            cut = p[:limit]
            idx = max(cut.rfind("，"), cut.rfind(","), cut.rfind("、"))
            if idx < limit // 2:
                idx = limit
            chunks.append(p[:idx].strip())
            p = p[idx:].strip()
        if p:
            chunks.append(p)
    return chunks


def build_subtitles(script, seconds):
    """按字数比例分配时长，凑成 SRT 能直接用的时间轴。"""
    chunks = split_chunks(script)
    if not chunks:
        return []
    total = max(1, int(seconds))
    weights = [max(1, len(c)) for c in chunks]
    unit = float(total) / float(sum(weights))
    out, t = [], 0.0
    for c, w in zip(chunks, weights):
        dur = max(1.2, unit * w)
        out.append({"start": round(t, 2), "end": round(t + dur, 2), "text": c})
        t += dur
    return out


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def chapter_time(sec):
    sec = int(round(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))


def slugify(s):
    s = re.sub(r"[^0-9A-Za-z]+", "-", s or "").strip("-").lower()
    return s or "edu"


def cmd_lesson(a, key, host):
    if not a.outline:
        raise Fail("usage", "必须给 --outline（Markdown 大纲，用 `## 第1节 标题` 分节）",
                   EXIT_USAGE)
    if not os.path.isfile(a.outline):
        raise Fail("usage", "大纲文件不存在：%s" % a.outline, EXIT_USAGE)
    text = io.open(a.outline, encoding="utf-8").read()
    title, secs = parse_outline(text, a.seconds)
    title = a.title or title or os.path.splitext(os.path.basename(a.outline))[0]
    slug = a.slug or slugify(title)

    out_sections, t0, chars = [], 0.0, 0
    for i, s in enumerate(secs, 1):
        script = "\n".join([x for x in s["script"] if x]).strip()
        if not script:
            script = "；".join(s["points"]) or ("本节讲 %s。" % s["title"])
        seconds = s["seconds"] or a.seconds
        subs = build_subtitles(script, seconds)
        chars += len(script)
        points = s["points"] or [s["title"]]
        visual = s["image"] or ("要点：" + "、".join(points[:3]))
        image_prompt = "%s；主题：%s；画面：%s" % (
            a.style_prefix or STYLE["prefix"], s["title"], visual)
        out_sections.append({
            "no": i, "title": s["title"], "points": points, "script": script,
            "seconds": seconds, "chars": len(script),
            "imagePrompt": image_prompt,
            "subtitles": subs, "srt": "\n".join(
                ["%d\n%s --> %s\n%s\n" % (n, srt_time(x["start"]), srt_time(x["end"]), x["text"])
                 for n, x in enumerate(subs, 1)]),
            "quiz": s["quiz"] or {"question": "本节要点：%s" % points[0],
                                  "options": [], "answer": ""},
            "progress": s["progress"] or (
                "第 %d 节 · 看完本节解锁第 %d 节" % (i, i + 1)
                if i < len(secs) else "第 %d 节 · 全课完成，进入结课测验" % i),
            "chapter": chapter_time(t0),
            "files": {"image": "%s-s%02d.png" % (slug, i),
                      "audio": "%s-s%02d.mp3" % (slug, i),
                      "video": "%s-s%02d.mp4" % (slug, i),
                      "srt": "%s-s%02d.srt" % (slug, i)},
        })
        t0 += seconds
    data = {
        "version": 1, "slug": slug, "course": title,
        "audience": a.audience or "通用学员", "level": a.level or "入门",
        "updatedAt": stamp(), "totalSeconds": int(round(t0)),
        "totalChars": chars,
        "chapterIndex": [{"no": s["no"], "at": s["chapter"], "title": s["title"]}
                         for s in out_sections],
        "style": {"name": STYLE["name"], "palette": STYLE["palette"],
                  "font": STYLE["font"], "ratio": STYLE["ratio"],
                  "prefix": a.style_prefix or STYLE["prefix"]},
        "sections": out_sections,
    }
    out = a.out
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    res = {"ok": True, "lesson": out, "course": title, "slug": slug,
           "sections": len(out_sections), "totalSeconds": data["totalSeconds"],
           "totalChars": chars, "imageCount": len(out_sections) + 1,
           "quizCount": len(out_sections)}
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("已拆课 → %s" % out)
    print("  课程：%s（%s · %s）" % (title, data["audience"], data["level"]))
    print("  分节：%d 节 · 总时长 %s · 讲稿 %d 字" % (
        len(out_sections), chapter_time(t0), chars))
    print()
    print("  %-3s %-18s %-7s %-6s %s" % ("#", "分节", "时长", "字数", "章节索引"))
    print("  " + "-" * 62)
    for s in out_sections:
        print("  %02d  %-18s %-7s %-6d %s" % (
            s["no"], s["title"][:18], chapter_time(s["seconds"]), s["chars"], s["chapter"]))
    print()
    print("  下一步：deck 出风格卡 / board 出交付清单 / cost 先算钱")
    return 0


def cmd_deck(a, key, host):
    d = read_json(a.lesson or "lesson.json", "lesson.json")
    slug = d.get("slug") or "edu"
    style = d.get("style") or {}
    rows = []
    for s in d["sections"]:
        rows.append({"no": s["no"], "title": s["title"],
                     "file": "%s-s%02d.png" % (slug, s["no"]),
                     "prompt": s["imagePrompt"]})
    if a.write:
        outdir = a.outdir
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        lines = ["# %s · 课件图风格卡" % d.get("course", ""), "",
                 "- 色板：%s" % " / ".join(style.get("palette") or STYLE["palette"]),
                 "- 字体：%s" % (style.get("font") or STYLE["font"]),
                 "- 画幅：%s · 建议 %s" % (style.get("ratio") or STYLE["ratio"], DEFAULT_ART_SIZE),
                 "- 统一前缀：%s" % (style.get("prefix") or STYLE["prefix"]), "",
                 "## 逐节提示词", ""]
        for r in rows:
            lines.append("### 第 %d 节 %s" % (r["no"], r["title"]))
            lines.append("")
            lines.append("- 文件：`%s`" % r["file"])
            lines.append("- 提示词：%s" % r["prompt"])
            lines.append("")
        path = os.path.join(outdir, "%s-deck.md" % slug)
        io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    else:
        path = ""
    res = {"ok": True, "lesson": a.lesson or "lesson.json", "style": style,
           "count": len(rows), "images": rows, "written": path}
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("课件图风格卡（一套课件只用一套视觉）")
    print("  色板：%s" % " / ".join(style.get("palette") or STYLE["palette"]))
    print("  字体：%s" % (style.get("font") or STYLE["font"]))
    print("  画幅：%s · 建议 %s" % (style.get("ratio") or STYLE["ratio"], DEFAULT_ART_SIZE))
    print("  前缀：%s" % (style.get("prefix") or STYLE["prefix"]))
    print()
    print("  %-3s %-18s %-16s %s" % ("#", "分节", "文件名", "提示词（截断）"))
    print("  " + "-" * 76)
    for r in rows:
        print("  %02d  %-18s %-16s %s" % (r["no"], r["title"][:18], r["file"],
                                          r["prompt"][:34]))
    if path:
        print()
        print("  已写入：%s" % path)
    print()
    print("  出图：python3 scripts/run.py art --lesson %s --outdir ./课件 --yes"
          % (a.lesson or "lesson.json"))
    return 0


COMPLIANCE = [
    "字体用商用免费字体（思源黑体），授权页截图与字体文件一起留档",
    "配图素材授权留档；学员人脸 / 声音素材单独签一份授权",
    "未成年人出镜素材，监护人书面同意与素材一起归档",
    "测验答案与解析写进 lesson.json，教研复核后再上线",
    "课程页标注讲师资质、课时数与有效期，与章节索引逐条对齐",
    "支付与退款条款在课程页明示，客服话术与之一致",
    "版权声明与二次分发范围写进课程页，渠道版本同源",
]


def cmd_board(a, key, host):
    d = read_json(a.lesson or "lesson.json", "lesson.json")
    slug = d.get("slug") or "edu"
    secs = d["sections"]
    n = len(secs)
    images = n + 1
    rate = SCREEN_RATES.get(a.mode, SCREEN_RATES["fast"])
    chars = sum(int(s.get("chars") or 0) for s in secs)
    total_secs = sum(int(s.get("seconds") or 0) for s in secs)
    narrate = sum(max(NARRATE_MIN, int(math.ceil(int(s.get("chars") or 0) * NARRATE_PER_CHAR)))
                  for s in secs)
    talk = sum(max(TALK_MIN, TALK_PER_SEC * int(s.get("seconds") or 0)) for s in secs)
    screen = rate * total_secs
    art = ART_POINTS * images
    total = art + narrate + screen
    rows = [
        {"item": "拆课 / 讲稿 / 字幕 / 章节索引", "count": "%d 节" % n, "spec": "lesson.json + srt",
         "name": "%s-s01.srt …" % slug, "unit": "0", "points": 0},
        {"item": "课件图", "count": "%d 张" % images, "spec": "1536x864 PNG 16:9",
         "name": "%s-cover.png / %s-s01.png" % (slug, slug), "unit": "6 点/张", "points": art},
        {"item": "分节配音", "count": "%d 条" % n, "spec": "mp3，48 kHz",
         "name": "%s-s01.mp3 …" % slug, "unit": "0.18 点/字", "points": narrate},
        {"item": "口播视频", "count": "%d 条" % n, "spec": "1080p mp4，%s 档" % a.mode,
         "name": "%s-s01.mp4 …" % slug, "unit": "%d 点/秒" % rate, "points": screen},
        {"item": "一图口播（替换方案）", "count": "%d 条" % n, "spec": "1080p mp4，quality=standard",
         "name": "%s-talk-s01.mp4 …" % slug, "unit": "15 点/秒", "points": talk},
    ]
    res = {"ok": True, "course": d.get("course"), "slug": slug, "sections": n,
           "totalSeconds": total_secs, "totalChars": chars,
           "deliverables": rows, "totalPoints": total,
           "totalYuan": round(total / float(POINTS_PER_YUAN), 2),
           "compliance": COMPLIANCE, "chapterIndex": d.get("chapterIndex") or []}
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("交付清单 · %s" % d.get("course", ""))
    print("  %d 节 · %s · 讲稿 %d 字" % (n, chapter_time(total_secs), chars))
    print()
    print("  %-22s %-6s %-24s %-11s %s" % ("交付物", "数量", "规格", "单价", "小计"))
    print("  " + "-" * 84)
    for r in rows:
        print("  %-22s %-6s %-24s %-11s %s" % (
            r["item"], r["count"], r["spec"], r["unit"], fmt_pts(r["points"]) + " 点"))
    print("  " + "-" * 84)
    print("  主方案合计：%s 点（%s）· 用一图口播替换口播视频时 %s 点" % (
        fmt_pts(total), yuan(total), fmt_pts(art + narrate + talk)))
    print()
    print("  命名：%s-cover.png / %s-s01.png / %s-s01.mp3 / %s-s01.mp4 / %s-s01.srt"
          % (slug, slug, slug, slug, slug))
    print("  章节索引：%s" % " · ".join("%s %s" % (c["at"], c["title"])
                                       for c in d.get("chapterIndex") or []))
    print()
    print("  合规检查（交付前逐条打勾）")
    for i, c in enumerate(COMPLIANCE, 1):
        print("   %d. %s" % (i, c))
    print()
    print("  学员进度：%s" % (secs[0].get("progress") if secs else "-"))
    print("  测验点：每节 1 个，答案写在 lesson.json 的 quiz 字段")
    print()
    print("  先算钱：python3 scripts/run.py cost --sections %d --seconds %d"
          % (n, (secs[0].get("seconds") or DEFAULT_SECTION_SECONDS)))
    return 0


# ───────────────────────── 免费：价目与自检 ─────────────────────────
def cmd_catalog(a, key, host):
    lines = [
        {"key": "image", "name": "课件图", "endpoint": "POST /api/v1/images/generations",
         "model": ART_MODEL, "unit": "6 点/张", "free": False,
         "use": "逐节 16:9 课件图、课程封面"},
        {"key": "narrate", "name": "分节配音", "endpoint": "POST /api/v1/apps/voice_tts/tts_async",
         "model": "fish_audio s2-pro", "unit": "0.18 点/字（单笔 6 点起）", "free": False,
         "use": "每节讲稿转 mp3，供口播与字幕对轴"},
        {"key": "talk", "name": "一图口播", "endpoint": "POST /api/v1/apps/pic_lipsync/submit",
         "model": "super-lipsync-pro", "unit": "15 点/秒（单笔 50 点起）", "free": False,
         "use": "一张讲师图 + 参考音色 + 文案 → 口播，省录音"},
        {"key": "screen", "name": "课件出片", "endpoint": "POST /api/v1/apps/image_human/submit",
         "model": "全驱数字人", "unit": "10 / 15 / 30 / 60 点/输入秒", "free": False,
         "use": "课件图 + 本节配音 → 1080p 口播视频"},
    ]
    local = [
        {"key": "lesson", "name": "拆课", "output": "lesson.json",
         "use": "知识点 / 分节 / 讲稿 / 配图提示 / 字幕 / 章节索引 / 测验点"},
        {"key": "deck", "name": "风格卡", "output": "*-deck.md",
         "use": "一套课件一个色板、一个字体、一个 16:9 构图"},
        {"key": "board", "name": "交付清单", "output": "终端 + JSON",
         "use": "图片 / 音频 / 视频 / 字幕的规格、命名、合计点数"},
    ]
    out = {"ok": True, "capabilities": lines, "local": local,
           "pointsPerYuan": POINTS_PER_YUAN,
           "deliverablesPerSection": 5}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("教育课件 · 四条能力线（都是已有接口，本包按岗位流程组织）")
    print()
    print("  %-8s %-10s %-42s %s" % ("--step", "能力", "端点", "单价"))
    print("  " + "-" * 88)
    for r in lines:
        print("  %-8s %-10s %-42s %s" % (r["key"], r["name"], r["endpoint"], r["unit"]))
    print()
    print("  本地三步（0 点，不发请求）")
    for r in local:
        print("  %-8s %-10s %-16s %s" % (r["key"], r["name"], r["output"], r["use"]))
    print()
    print("  一节 60 分钟的课拆成 5 样交付物：课件图（含封面）/ 配音 / 口播视频 /")
    print("  字幕 / 章节索引。1 元 = 100 点；整门课先用 cost 算，再一节一节过 --yes。")
    return 0


def estimate_lesson(sections, seconds, images, chars, mode):
    rate = SCREEN_RATES.get(mode, SCREEN_RATES["fast"])
    art = ART_POINTS * images
    narrate = max(NARRATE_MIN, int(math.ceil(chars * NARRATE_PER_CHAR)))
    talk = max(TALK_MIN, int(math.ceil(seconds * TALK_PER_SEC)))
    screen = rate * seconds
    return {
        "art": art, "narrate": narrate, "talk": talk, "screen": screen,
        "perSection": narrate + talk + screen,
        "course": art + (narrate + talk + screen) * sections,
    }


def cmd_cost(a, key, host):
    sections = max(1, a.sections)
    seconds = max(1, a.seconds)
    images = a.images if a.images else sections + 1
    chars = max(1, a.chars)
    e = estimate_lesson(sections, seconds, images, chars, a.mode)
    out = {"ok": True, "sections": sections, "seconds": seconds, "images": images,
           "charsPerSection": chars, "screenMode": a.mode,
           "pointsPerYuan": POINTS_PER_YUAN,
           "perImage": ART_POINTS, "perChar": NARRATE_PER_CHAR,
           "talkPerSecond": TALK_PER_SEC, "screenPerSecond": SCREEN_RATES[a.mode],
           "perSection": e["perSection"], "course": e["course"],
           "yuan": round(e["course"] / float(POINTS_PER_YUAN), 2),
           "notes": [
               "课件图 6 点/张，与尺寸 / 质量 / 格式无关；按实际返回张数计费",
               "配音按上游实际点数 ×3，约 0.18 点/字，单笔 6 点起",
               "一图口播 15 点/秒（quality=standard），单笔 50 点起",
               "课件出片按输入音频秒数计费：fast 10 / standard 15 / 2k 30 / 4k 60 点/秒",
               "各单节任务失败全额退回；本包先卡 --budget，再要 --yes",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("整门课预估（1 元 = 100 点）")
    print("  %d 节 × %d 秒 · 课件图 %d 张 · 每节讲稿 %d 字 · 出片 %s 档"
          % (sections, seconds, images, chars, a.mode))
    print()
    print("  %-16s %-22s %10s %10s" % ("环节", "口径", "每节", "整门课"))
    print("  " + "-" * 64)
    rows = [
        ("课件图", "%d 点/张 × %d 张" % (ART_POINTS, images), None, e["art"]),
        ("分节配音", "%.2f 点/字 × %d 字" % (NARRATE_PER_CHAR, chars), e["narrate"],
         e["narrate"] * sections),
        ("一图口播", "%d 点/秒 × %d 秒" % (TALK_PER_SEC, seconds), e["talk"],
         e["talk"] * sections),
        ("课件出片", "%d 点/秒 × %d 秒" % (SCREEN_RATES[a.mode], seconds), e["screen"],
         e["screen"] * sections),
    ]
    for name, basis, one, alln in rows:
        print("  %-16s %-22s %10s %10s" % (
            name, basis, "-" if one is None else fmt_pts(one), fmt_pts(alln)))
    print("  " + "-" * 64)
    print("  %-16s %-22s %10s %10s" % ("合计（主方案）", "", fmt_pts(e["perSection"]),
                                      fmt_pts(e["course"])))
    print()
    print("  换算：%d 点 = %s（整门课）；单节约 %s" % (
        e["course"], yuan(e["course"]), yuan(e["perSection"])))
    print("  主方案 = 课件图 + 配音 + 课件出片；一图口播是替换方案（二选一，不叠加）。")
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


def cmd_doctor(a, key, host):
    checks = []
    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    avail = d.get("available_points")
    if avail is None:
        avail = d.get("points") or 0
    checks.append(("Key + 余额接口可达", st == 200,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(avail), fmt_pts(d.get("frozen") or 0))))

    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=40)
    dd = jloads(txt) or {}
    apps = dd.get("data") if isinstance(dd.get("data"), list) else []
    codes = set()
    api_map = {}
    for x in apps:
        if isinstance(x, dict) and x.get("code"):
            codes.add(x["code"])
            api_map[x["code"]] = [y.get("code") for y in (x.get("apis") or [])
                                  if isinstance(y, dict)]
    need = {"image_human": "submit", "pic_lipsync": "submit", "voice_tts": "tts_async"}
    miss = ["%s/%s" % (k, v) for k, v in need.items()
            if k not in codes or v not in (api_map.get(k) or [])]
    checks.append(("四条能力线在架（%d 个应用）" % len(apps), not miss,
                   "全在架" if not miss else "缺 " + " / ".join(miss)))

    st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
    pr = jloads(txt) or {}
    pr = pr.get("pricing") if isinstance(pr.get("pricing"), dict) else {}
    pic = pr.get("/api/v1/apps/pic_lipsync/submit") or {}
    hum = pr.get("/api/v1/apps/image_human/submit") or {}
    tts = pr.get("/api/v1/apps/voice_tts/*") or {}
    rates = (hum.get("modelRates") or {}).get("fast") or {}
    ok_p = bool(pic) and bool(hum) and bool(tts) and int(rates.get("*") or 0) == 10
    checks.append(("价目规则与本地单价一致", ok_p,
                   "pic_lipsync ×%s · image_human fast=%s 点/秒 · voice_tts ×%s" % (
                       pic.get("markupPercent") or "?", rates.get("*") or "?",
                       tts.get("markupPercent") or "?")))

    st, txt = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task", key, timeout=40)
    d4 = jloads(txt) or {}
    checks.append(("任务查询 GET /tasks/{id} 可用", st == 200 and d4.get("code") == 0,
                   "HTTP %s %s（轮询只走这条，免费）" % (st, (d4.get("msg") or "")[:30])))

    st, txt = http_json("POST", host + API_PREFIX + "/images/generations", key,
                        {"model": ART_MODEL, "prompt": ""}, timeout=40)
    d5 = jloads(txt) or {}
    e5 = d5.get("error") if isinstance(d5.get("error"), dict) else {}
    checks.append(("文生图端点可用（422 即正确，0 点）", st == 422,
                   "HTTP %s %s" % (st, (e5.get("message") or "")[:46])))

    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=a.timeout)
    d6 = jloads(txt) or {}
    checks.append(("上传接口 POST /upload 可用（免费）", st == 200 and d6.get("code") == 0,
                   "HTTP %s %s" % (st, (d6.get("msg") or "")[:36])))

    st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d7 = jloads(txt) or {}
    logs = d7.get("logs") or []
    latest = ""
    if logs:
        at = logs[0].get("at")
        try:
            latest = time.strftime("%m-%d %H:%M:%S", time.localtime(float(at) / 1000.0))
        except Exception:                                        # noqa: BLE001
            latest = str(at)
    checks.append(("流水可读（用来核对本轮花费）", st == 200,
                   "共 %s 条 · 最新一条 %s" % (fmt_pts(d7.get("total") or 0), latest)))

    out = {"ok": all(c[1] for c in checks), "host": host,
           "endpoints": ["POST /api/v1/images/generations",
                         "POST /api/v1/apps/voice_tts/tts_async",
                         "POST /api/v1/apps/pic_lipsync/submit",
                         "POST /api/v1/apps/image_human/submit"],
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks],
           "pointsSpent": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print()
    print("自检（只读 + 一次空 prompt 422，0 点；不发任何 submit）")
    print()
    for n, o, dt in checks:
        print("  %s %-38s %s" % ("√" if o else "×", n, dt))
    print()
    print("  四条链路：文生图 / voice_tts / pic_lipsync / image_human")
    print("  轮询：GET /api/v1/tasks/{id}（唯一路径；应用层 /query 已拦死）")
    print("  本轮花费：0 点（上面流水时间可复核）")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 免费：上传 ─────────────────────────
def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（本地课件图 / 配音 / 参考音色）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "endpoint": url, "file": path, "size": size}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传）")
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        return 0
    say("正在上传 %s（%d 字节）…" % (os.path.basename(path), size))
    t0 = time.time()
    st, txt = http_multipart(url, key, {}, [("file", path)], timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    got = data.get("url")
    if d.get("code") != 1 or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    ok_url, kind = url_allowed(got)
    out = {"ok": True, "url": got, "file": path, "size": data.get("size") or size,
           "mime": data.get("mime_type"), "hostKind": kind, "urlAllowed": ok_url,
           "elapsed": round(dt, 1)}
    ledger_add({"at": stamp(), "ok": True, "mode": "upload", "file": path,
                "size": size, "url": got})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs）" % dt)
    print("  地址：%s" % got)
    print("  归属：%s（%s）" % (kind, "平台托管，可直给 submit" if ok_url else "按需核对"))
    print("  有效期约 24 小时；课件图 / 配音 / 参考音色先传再提交。")
    return 0


# ───────────────────────── 付费：课件图 ─────────────────────────
def check_size(size):
    """文生图尺寸四条硬约束（不合规会在上游 400，本地先拦）。"""
    if size in ("auto", "1k", "2k", "4k"):
        return
    m = re.match(r"^(\d{2,4})x(\d{2,4})$", size or "")
    if not m:
        raise Fail("usage", "--size 只收 auto / 1k / 2k / 4k / 宽x高，收到 %r" % size,
                   EXIT_USAGE)
    w, h = int(m.group(1)), int(m.group(2))
    reasons = []
    if w % 16 or h % 16:
        reasons.append("宽高都要是 16 的倍数")
    if max(w, h) > 3840:
        reasons.append("单边不超过 3840")
    if max(w, h) / float(min(w, h)) > 3.0:
        reasons.append("长短边不超过 3:1")
    if not 655360 <= w * h <= 8294400:
        reasons.append("总像素 655,360–8,294,400")
    if reasons:
        raise Fail("usage", "--size %s 不合规：%s" % (size, "；".join(reasons)),
                   EXIT_USAGE)


def cmd_art(a, key, host):
    prompts = []
    if a.lesson:
        d = read_json(a.lesson, "lesson.json")
        secs = d["sections"]
        if a.section:
            secs = [s for s in secs if int(s.get("no") or 0) == a.section]
            if not secs:
                raise Fail("usage", "--section %d 不在 lesson.json 里" % a.section,
                           EXIT_USAGE)
        for s in secs:
            prompts.append((int(s.get("no") or 0), s.get("title") or "",
                            s.get("imagePrompt") or ""))
        if a.cover:
            prompts.insert(0, (0, "课程封面",
                               "%s；主题：%s 课程封面，标题区留白" % (
                                   (d.get("style") or {}).get("prefix") or STYLE["prefix"],
                                   d.get("course") or "")))
    elif a.prompt:
        prompts.append((a.section or 0, "自定义", a.prompt))
    if not prompts:
        raise Fail("usage", "给 --prompt（单张）或 --lesson（逐节出图）", EXIT_USAGE)
    if any(not p[2] for p in prompts):
        raise Fail("usage", "有分节的 imagePrompt 是空的，先跑 lesson 生成", EXIT_USAGE)
    n = max(1, a.n)
    if n > 4:
        raise Fail("usage", "--n 一次最多 4 张（多节请用 --lesson 逐节跑）", EXIT_USAGE)
    check_size(a.size)
    cost = ART_POINTS * len(prompts) * n
    gate(a, cost, "课件图 %d 张" % (len(prompts) * n),
         "6 点/张 × %d 次请求 × %d 张" % (len(prompts), n))
    body = {"model": ART_MODEL, "prompt": prompts[0][2], "n": n,
            "size": a.size, "output_format": "png"}
    if a.dry_run:
        reqs = [dict(body, prompt=p[2]) for p in prompts]
        out = {"ok": True, "dryRun": True, "requests": reqs,
               "count": len(prompts) * n, "estimatedPoints": cost,
               "yuan": round(cost / float(POINTS_PER_YUAN), 2)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：POST %s/api/v1/images/generations" % host)
        print("  模型：%s · %s · 每次 %d 张 · 共 %d 张" % (
            ART_MODEL, a.size, n, len(prompts) * n))
        for p in reqs:
            print("  → %s" % p["prompt"][:120])
        print("  预估：%d 点（%s）" % (cost, yuan(cost)))
        return 0

    outdir = a.outdir
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    files, urls, saved = [], [], 0
    t0 = time.time()
    for no, title, prompt in prompts:
        say("正在出图：%s …" % (title or prompt[:30]))
        st, txt = http_json("POST", host + API_PREFIX + "/images/generations", key,
                            dict(body, prompt=prompt), timeout=a.timeout)
        d = jloads(txt) or {}
        if st != 200 or not isinstance(d.get("data"), list):
            ledger_add({"at": stamp(), "ok": False, "mode": "art", "no": no,
                        "http": st, "error": err_text(st, txt)})
            raise Fail("call", "出图失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
        for idx, item in enumerate(d["data"], 1):
            if not isinstance(item, dict):
                continue
            name = "%s-%s.png" % (a.prefix, ("cover" if no == 0 else "s%02d-%d" % (no, idx)))
            if item.get("b64_json"):
                raw = item["b64_json"]
                if isinstance(raw, str) and raw.startswith("data:"):
                    raw = raw.split(",", 1)[-1]
                with open(os.path.join(outdir, name), "wb") as fh:
                    fh.write(base64.b64decode(raw))
                files.append(os.path.join(outdir, name))
                saved += 1
            elif item.get("url"):
                urls.append(item["url"])
    dt = time.time() - t0
    res = {"ok": True, "model": ART_MODEL, "count": len(files) + len(urls),
           "files": files, "urls": urls, "outdir": outdir,
           "estimatedPoints": cost, "elapsed": round(dt, 1), "size": a.size}
    ledger_add({"at": stamp(), "ok": True, "mode": "art", "files": files,
                "urls": urls, "estimatedPoints": cost, "elapsed": round(dt, 1)})
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("已出图（%.1fs）" % dt)
    for f in files:
        print("  文件：%s" % f)
    for u in urls:
        print("  链接：%s（约 3 小时有效，及时转存）" % u)
    print("  张数：%d（按实际返回计费，约 %d 点）" % (len(files) + len(urls), cost))
    print("  下一步：上传配音与图片 → talk / screen")
    return 0


# ───────────────────────── 付费：配音 ─────────────────────────
def cmd_narrate(a, key, host):
    text = a.text
    if a.lesson:
        d = read_json(a.lesson, "lesson.json")
        secs = d["sections"]
        if a.section:
            secs = [s for s in secs if int(s.get("no") or 0) == a.section]
            if not secs:
                raise Fail("usage", "--section %d 不在 lesson.json 里" % a.section,
                           EXIT_USAGE)
        text = "\n".join((s.get("script") or "") for s in secs)
    if not text:
        raise Fail("usage", "给 --text，或 --lesson + --section 取本节讲稿", EXIT_USAGE)
    chars = len(re.sub(r"\s+", "", text))
    cost = max(NARRATE_MIN, int(math.ceil(chars * NARRATE_PER_CHAR)))
    gate(a, cost, "配音 %d 字" % chars, "0.18 点/字，单笔 6 点起")
    body = {"text": text, "model": a.model, "format": "mp3", "normalize": True}
    if a.voice:
        body["reference_id"] = a.voice
    if a.speed:
        body["prosody"] = {"speed": a.speed}
    endpoint = host + API_PREFIX + "/apps/voice_tts/tts_async"
    if a.dry_run:
        return plan(a, endpoint, dict(body, text=text[:120] + ("…" if chars > 120 else "")),
                    cost, "配音")
    say("正在提交配音（%d 字）…" % chars)
    t0 = time.time()
    st, txt = http_json("POST", endpoint, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    if d.get("code") != 1 or not task_id:
        ledger_add({"at": stamp(), "ok": False, "mode": "narrate", "http": st,
                    "error": err_text(st, txt)})
        raise Fail("call", "配音提交失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    res = {"ok": True, "taskId": task_id, "status": data.get("status"),
           "chars": chars, "voice": a.voice or "默认音色", "estimatedPoints": cost,
           "elapsed": round(dt, 1), "query": API_PREFIX + "/tasks/" + str(task_id)}
    ledger_add({"at": stamp(), "ok": True, "mode": "narrate", "taskId": task_id,
                "chars": chars, "estimatedPoints": cost})
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("已提交配音（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  字数：%d · 预估 %d 点（以 usage.points_cost ×3 结算为准）" % (chars, cost))
    print("  查进度：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 付费：一图口播 ─────────────────────────
def need_urls(*pairs):
    for name, u in pairs:
        if not re.match(r"^https?://", u or "", re.I):
            raise Fail("usage", "%s 要以 http:// 或 https:// 开头（本地文件先 upload）" % name,
                       EXIT_USAGE)


def cmd_talk(a, key, host):
    if not a.image_url:
        raise Fail("usage", "必须给 --image-url（讲师图，先 upload 成托管地址）", EXIT_USAGE)
    if not a.audio_url:
        raise Fail("usage",
                   "必须给 --audio-url 作为参考音色 —— text 模式省掉录音，但省不掉参考音色",
                   EXIT_USAGE)
    need_urls(("--image-url", a.image_url), ("--audio-url", a.audio_url))
    content = a.content
    if a.script_file:
        if not os.path.isfile(a.script_file):
            raise Fail("usage", "讲稿文件不存在：%s" % a.script_file, EXIT_USAGE)
        content = io.open(a.script_file, encoding="utf-8").read().strip()
    if not content:
        raise Fail("usage", "必须给 --content，或用 --script-file 指定本节讲稿", EXIT_USAGE)
    if not a.quality:
        raise Fail("usage",
                   "必须显式给 --quality（standard / fast / max）。档位参数真名是 quality，"
                   "省略时按 standard 收，账单和预期会错位。", EXIT_USAGE)
    secs = a.duration or max(1, int(math.ceil(len(re.sub(r"\s+", "", content)) / 4.5)))
    cost = max(TALK_MIN, TALK_PER_SEC * secs)
    gate(a, cost, "一图口播 %d 秒" % secs,
         "15 点/秒 × %d 秒，单笔 %d 点起" % (secs, TALK_MIN))
    body = {"image_url": a.image_url, "audio_url": a.audio_url, "mode": "text",
            "content": content, "quality": a.quality}
    if a.prompt:
        body["prompt"] = a.prompt
    endpoint = host + API_PREFIX + "/apps/pic_lipsync/submit"
    if a.dry_run:
        return plan(a, endpoint, dict(body, content=content[:100] + "…"), cost, "一图口播",
                    {"basis": "按 %d 秒估；实际以语音时长结算，失败全额退回" % secs})
    say("正在提交一图口播（%d 秒，quality=%s）…" % (secs, a.quality))
    t0 = time.time()
    st, txt = http_json("POST", endpoint, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    if d.get("code") != 1 or not task_id:
        ledger_add({"at": stamp(), "ok": False, "mode": "talk", "http": st,
                    "error": err_text(st, txt)})
        raise Fail("call", "口播提交失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    res = {"ok": True, "taskId": task_id, "status": data.get("status"),
           "quality": a.quality, "seconds": secs, "estimatedPoints": cost,
           "frozenPoints": data.get("frozen_points"), "elapsed": round(dt, 1)}
    ledger_add({"at": stamp(), "ok": True, "mode": "talk", "taskId": task_id,
                "quality": a.quality, "estimatedPoints": cost})
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  档位：quality=%s · 预估 %d 点 · 冻结 %s 点" % (
        a.quality, cost, data.get("frozen_points") or "-"))
    print("  查进度：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 付费：课件出片 ─────────────────────────
def cmd_screen(a, key, host):
    if not a.image_url:
        raise Fail("usage", "必须给 --image-url（课件图 / 讲师图托管地址）", EXIT_USAGE)
    if not a.audio_url:
        raise Fail("usage", "必须给 --audio-url（本节配音托管地址）", EXIT_USAGE)
    need_urls(("--image-url", a.image_url), ("--audio-url", a.audio_url))
    if not a.mode:
        raise Fail("usage",
                   "必须显式给 --mode（fast / standard / 2k / 4k）。schema 默认 standard、"
                   "计费默认 fast，省略时出片与收钱会走两个档。", EXIT_USAGE)
    if not a.duration:
        raise Fail("usage",
                   "必须给 --duration（本节配音秒数）。带上它价格才被费率卡锁死，"
                   "预算才算得准。", EXIT_USAGE)
    cost = SCREEN_RATES[a.mode] * int(a.duration)
    gate(a, cost, "课件出片 %d 秒（%s 档）" % (a.duration, a.mode),
         "%d 点/秒 × %d 秒" % (SCREEN_RATES[a.mode], a.duration))
    body = {"file_url": a.image_url, "ref_file_url": a.audio_url,
            "duration": int(a.duration), "mode": a.mode}
    if a.prompt:
        body["prompt"] = a.prompt
    endpoint = host + API_PREFIX + "/apps/image_human/submit"
    if a.dry_run:
        return plan(a, endpoint, body, cost, "课件出片")
    say("正在提交课件出片（%d 秒，%s 档）…" % (a.duration, a.mode))
    t0 = time.time()
    st, txt = http_json("POST", endpoint, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    if d.get("code") != 1 or not task_id:
        ledger_add({"at": stamp(), "ok": False, "mode": "screen", "http": st,
                    "error": err_text(st, txt)})
        raise Fail("call", "出片提交失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    res = {"ok": True, "taskId": task_id, "status": data.get("status"),
           "mode": a.mode, "seconds": int(a.duration), "estimatedPoints": cost,
           "frozenPoints": data.get("frozen_points"), "elapsed": round(dt, 1)}
    ledger_add({"at": stamp(), "ok": True, "mode": "screen", "taskId": task_id,
                "mode2": a.mode, "seconds": int(a.duration), "estimatedPoints": cost})
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  档位：%s · %d 秒 · 预估 %d 点 · 冻结 %s 点" % (
        a.mode, a.duration, cost, data.get("frozen_points") or "-"))
    print("  查进度：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 免费：查任务 / 台账 ─────────────────────────
def find_urls(obj, acc=None):
    if acc is None:
        acc = []
    if isinstance(obj, dict):
        for v in obj.values():
            find_urls(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            find_urls(v, acc)
    elif isinstance(obj, str) and re.match(r"^https?://", obj) and len(acc) < 20:
        acc.append(obj)
    return acc


def cmd_status(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + tid
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if d.get("code") == 0 and not d.get("data"):
        raise Fail("call", "查不到任务 %s：%s" % (tid, d.get("msg") or "任务不存在"),
                   EXIT_CALL)
    data = d.get("data") if isinstance(d.get("data"), dict) else d
    urls = find_urls(data)
    cost = data.get("cost")
    if cost is None and isinstance(data.get("usage"), dict):
        cost = data["usage"].get("points_cost")
    res = {"ok": True, "taskId": tid, "status": data.get("status"),
           "cost": cost, "refund": data.get("refund"), "urls": urls,
           "error": data.get("error"), "message": data.get("message")}
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  状态：%s" % data.get("status"))
    if cost is not None:
        print("  实扣：%s 点" % cost)
    if data.get("refund") is not None:
        print("  退回：%s 点" % data.get("refund"))
    if data.get("message"):
        print("  说明：%s" % str(data.get("message"))[:240])
    for u in urls:
        mark = "成片" if u.lower().endswith((".mp4", ".mov")) else (
            "音频" if u.lower().endswith((".mp3", ".wav", ".m4a")) else "文件")
        print("  %s：%s" % (mark, u))
    print("  查询路径：%s（只读，免费）" % path)
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
        what = e.get("taskId") or e.get("url") or (e.get("error") or "")[:40] or "-"
        print("  %s  %-5s %-8s %-9s %-40s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            e.get("mode2") or "-", str(what)[:40],
            ("%s 点" % e.get("estimatedPoints")) if e.get("estimatedPoints") else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 教育课件（一节课拆成讲稿 / 课件图 / 配音 / 口播 / 字幕）",
        epilog="端点：POST %s/api/v1/images/generations · POST %s/api/v1/apps/voice_tts/tts_async · "
               "POST %s/api/v1/apps/pic_lipsync/submit · POST %s/api/v1/apps/image_human/submit · "
               "GET %s/api/v1/tasks/{taskId}（轮询只走这条）" % (
                   DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（stdout 只有一个文档）")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=5000,
                    help="点数上限（单位：点，1 元 = 100 点，默认 5000）")
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="四条能力线 + 本地三步 + 价目（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="整门课先算钱（免费）", allow_abbrev=False)
    p.add_argument("--sections", type=int, default=8, help="分节数（默认 8）")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECTION_SECONDS,
                   help="每节秒数（默认 180）")
    p.add_argument("--images", type=int, default=0,
                   help="课件图张数（默认 = 分节数 + 1 张封面）")
    p.add_argument("--chars", type=int, default=450, help="每节讲稿字数（默认 450）")
    p.add_argument("--mode", choices=SCREEN_MODES, default="fast",
                   help="课件出片档位（默认 fast，10 点/秒）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="只读自检四条链路 + 价目 + 流水（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=60, help="单次探针超时秒数（默认 60）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("lesson", help="大纲 Markdown → lesson.json（免费，本地）",
                       allow_abbrev=False)
    p.add_argument("--outline", help="Markdown 大纲（用 `## 第1节 标题` 分节）")
    p.add_argument("--out", default="lesson.json", help="输出 JSON（默认 lesson.json）")
    p.add_argument("--title", help="课程名（默认取大纲一级标题）")
    p.add_argument("--slug", help="文件名前缀（默认由课程名生成）")
    p.add_argument("--audience", help="学员画像（默认「通用学员」）")
    p.add_argument("--level", help="难度（默认「入门」）")
    p.add_argument("--seconds", type=int, default=DEFAULT_SECTION_SECONDS,
                   help="每节默认秒数（默认 180）")
    p.add_argument("--style-prefix", help="覆盖统一风格前缀（默认黑板暖白）")
    p.set_defaults(fn=cmd_lesson)

    p = sub.add_parser("deck", help="课件图风格卡 + 逐节提示词（免费，本地）",
                       allow_abbrev=False)
    p.add_argument("--lesson", default="lesson.json", help="lesson.json 路径")
    p.add_argument("--write", action="store_true", help="把风格卡写成 *-deck.md")
    p.add_argument("--outdir", default="./课件", help="风格卡输出目录（配 --write）")
    p.set_defaults(fn=cmd_deck)

    p = sub.add_parser("board", help="交付清单：图 / 音 / 视频 / 命名 / 合规（免费，本地）",
                       allow_abbrev=False)
    p.add_argument("--lesson", default="lesson.json", help="lesson.json 路径")
    p.add_argument("--mode", choices=SCREEN_MODES, default="fast",
                   help="口播视频档位（默认 fast）")
    p.set_defaults(fn=cmd_board)

    p = sub.add_parser("upload", help="本地素材转平台托管地址（免费）", allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径（课件图 / 配音 / 参考音色）")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("art", help="出课件图 6 点/张（要 --yes）", allow_abbrev=False)
    p.add_argument("--prompt", help="单张提示词（与 --lesson 二选一）")
    p.add_argument("--lesson", help="按 lesson.json 逐节出图")
    p.add_argument("--section", type=int, help="只出这一节（默认全部）")
    p.add_argument("--cover", action="store_true", help="同时出课程封面")
    p.add_argument("--n", type=int, default=1, help="每次请求张数 1–4（默认 1）")
    p.add_argument("--size", default=DEFAULT_ART_SIZE,
                   help="尺寸（默认 %s，16:9）" % DEFAULT_ART_SIZE)
    p.add_argument("--outdir", default="./课件", help="图片目录（默认 ./课件）")
    p.add_argument("--prefix", default="edu", help="文件名前缀（默认 edu）")
    p.add_argument("--timeout", type=int, default=180, help="单次出图超时秒数（默认 180）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_art)

    p = sub.add_parser("narrate", help="分节配音 0.18 点/字（要 --yes）", allow_abbrev=False)
    p.add_argument("--text", help="直接给文本")
    p.add_argument("--lesson", help="从 lesson.json 取讲稿")
    p.add_argument("--section", type=int, help="只配这一节（默认全部合并）")
    p.add_argument("--voice", help="音色模型 ID（reference_id）")
    p.add_argument("--model", default="s2-pro", help="s1 / s2-pro（默认 s2-pro）")
    p.add_argument("--speed", type=float, help="语速（prosody.speed）")
    p.add_argument("--timeout", type=int, default=120, help="提交超时秒数（默认 120）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_narrate)

    p = sub.add_parser("talk", help="一图口播，文案驱动（要 --yes）", allow_abbrev=False)
    p.add_argument("--image-url", help="讲师图托管地址（先 upload）")
    p.add_argument("--audio-url", help="参考音色地址（text 模式必填）")
    p.add_argument("--content", help="本节口播文案")
    p.add_argument("--script-file", help="从文件读文案")
    p.add_argument("--quality", choices=TALK_QUALITIES, help="standard / fast / max（必填）")
    p.add_argument("--duration", type=int,
                   help="按多少秒预估（默认按文案字数 ÷4.5）")
    p.add_argument("--prompt", help="人物动作 / 表情提示")
    p.add_argument("--timeout", type=int, default=180, help="提交超时秒数（默认 180）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_talk)

    p = sub.add_parser("screen", help="课件图 + 配音 → 数字人视频（要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--image-url", help="课件图 / 讲师图托管地址")
    p.add_argument("--audio-url", help="本节配音托管地址")
    p.add_argument("--duration", type=int, help="配音秒数（必填，费率卡靠它锁定）")
    p.add_argument("--mode", choices=SCREEN_MODES, help="fast / standard / 2k / 4k（必填）")
    p.add_argument("--prompt", help="画面提示词")
    p.add_argument("--timeout", type=int, default=180, help="提交超时秒数（默认 180）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_screen)

    p = sub.add_parser("status", help="查任务 GET /tasks/{id}（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示条数（默认 20）")
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以（default=SUPPRESS：不覆盖前面已经解析到的值）
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_lesson", "cmd_deck", "cmd_board", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    fn_name = getattr(a.fn, "__name__", "")
    if not key and fn_name not in FREE:
        msg = ("没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
               "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/")
        if getattr(a, "json", False):
            print(json.dumps({"ok": False, "exit": EXIT_USAGE,
                              "error": {"kind": "usage", "message": msg}},
                             ensure_ascii=False))
            return EXIT_USAGE
        say("失败：" + msg)
        return EXIT_USAGE
    try:
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
