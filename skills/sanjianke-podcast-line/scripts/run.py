#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 播客生产线（sanjianke-podcast-line）

一段文稿 → 成品播客：**配音 + 配乐 + 逐句字幕 + 章节**，四个零件一个命令一个。

## 三条接口，一条形态（全部实测，2026-11-07）

  统一形态   POST /api/v1/apps/media_services_33/<接口code>     （JSON）
  任务查询   GET  /api/v1/tasks/<task_id>                        （只读，0 点）

  vo    配音   elevenlabs_text_to_speech_multilingual_v2   text / voice
  bgm   配乐   music_generate                              model / custom_mode / instrumental
  subs  字幕   music_timestamped_lyrics                    task_id / audio_id

## 价格口径（**必须诚实**）

`GET /api/v1/pricing` 共 115 条规则，**没有 `media_services_33` 的专属条目**，落通配：

    {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
     "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}

**实测每次 POST 先 `reserve_sync` 预冻结 60 点**（音乐类、TTS 类、歌词类都是 60，
见本包 `references/api-contract.md` 的流水原文），失败全额退。所以 `cost` 给的是
**下限估算 = 条数 × 60 点**，成交价要真跑一条、看任务详情里的 `usage` 才知道。

## 两道闸门

`--budget` 单位是「点」（1 元 = 100 点），`--yes` 是第二道。
缺 `--yes` → exit 4 并告诉你要花多少；预计超 `--budget` → exit 5，**一个请求都不发**。

## 免费子命令（先验 Key、先看价，一分钱不花）

  catalog  三条接口的必填项 / model 枚举 / 67 个音色 / 价格口径（现查 apps 列表，0 点）
  cost     先算钱：按文稿字数切片后给下限（纯本地算术，0 点）
  doctor   自检 Key / 余额 / 三条接口在架 / 通配价目 / 查询路由（只读 GET，0 点）
  chapters 文稿章节 + 字幕时间轴 → 章节目录（纯本地，0 点）
  task     查任务状态 / 补取结果（只读 GET，0 点）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --script ep01.md --bgm --subs
  python3 scripts/run.py doctor
  python3 scripts/run.py vo  --script ep01.md --voice EkK5I93UQWFDigLMpZcX --yes
  python3 scripts/run.py bgm --prompt "lo-fi 钢琴，温暖" --style "lo-fi piano, warm" --yes
  python3 scripts/run.py subs --task-id <bgm_task_id> --audio-id <bgm_audio_id> --yes
  python3 scripts/run.py chapters --script ep01.md --srt ep01.srt

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import difflib
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

# ── GBK 编码兜底（2026-11-07 实测修复，照抄家族参考实现）────────────────────
# Windows 上 stdout 被管道/重定向时 Python 用本地编码（cp936），
# 遇到 cp936 编不出的字符就 UnicodeEncodeError 崩掉。先加 replace 兜底，
# 本包再统一用 `√` / `×`（这两个 cp936 有），不用 `✓` / `✗`。
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
APP_PATH = API_PREFIX + "/apps/" + APP + "/"

VOICE_API = "elevenlabs_text_to_speech_multilingual_v2"
BGM_API = "music_generate"
SUBS_API = "music_timestamped_lyrics"

# 价格口径：通配规则（pricing 里没有 media_services_33 的专属条目）
UPSTREAM_MARKUP = 2          # 上游实际点数 × 2
MIN_POINTS = 50              # 单笔保底 50 点
RESERVE_POINTS = 60          # 实测每次 POST 先 reserve_sync 冻 60 点，失败全退
DEFAULT_BUDGET = 500         # 点（5 元）
POINTS_PER_YUAN = 100

TTS_MAX_CHARS = 5000         # schema: text maxLength 5000
DEFAULT_CHUNK = 4500         # 切片留 10% 余量，避免标点与空白顶到上限

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "podcast-line-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-podcast-line/%s" % VERSION

# ── 接口能力表（必填项来自网关 params_schema 原文）──────────────────────────
ENDPOINTS = {
    "vo": dict(code=VOICE_API, name="配音", engine="ElevenLabs 多语言 V2",
               required=["text", "voice"],
               optional=["speed", "style", "stability", "similarity_boost",
                         "timestamps", "language_code", "previous_text", "next_text"],
               desc="一段文稿出人声，100+ 语言，67 个预置音色"),
    "bgm": dict(code=BGM_API, name="配乐", engine="Suno 音乐",
                required=["model", "custom_mode", "instrumental"],
                optional=["style", "title", "lyrics", "prompt", "duration", "variety",
                          "negative_tags", "vocal_gender", "style_weight",
                          "weirdness_constraint", "audio_urls", "image_urls",
                          "video_urls", "persona_id", "persona_model"],
                desc="写给播客的片头 / 垫乐 / 转场，10–360 秒"),
    "subs": dict(code=SUBS_API, name="字幕", engine="Suno 时间戳歌词",
                 required=["task_id", "audio_id"], optional=[],
                 desc="把带人声的曲子拆成逐句时间轴，直接压字幕"),
}

GEN_MODELS = ["V6", "V6_MINI", "V6_WILD", "V5_5", "V5", "V4_5ALL", "V4_5PLUS", "V4_5", "V4"]
DEFAULT_MODEL = "V6"

# 67 个音色 ID（schema enum 原文）+ 名字（schema description 原文）
VOICES = (
    ("EkK5I93UQWFDigLMpZcX", "James - 沙哑、引人入胜、大胆"),
    ("Z3R5wn05IrDiVCyEkUrK", "Arabella - 神秘、富有情感"),
    ("NNl6r8mD7vthiJatiJt1", "Bradford - 富有表现力、口齿清晰"),
    ("YOq2y2Up4RgXP2HyXjE5", "Xavier - 霸气、金属感播音员"),
    ("B8gJV1IhpuegLxdpXFOE", "Kuon - 开朗、清晰、稳定"),
    ("2zRM7PkgwBPiau2jvVXc", "Monika Sogam - 低沉、自然"),
    ("1SM7GgM6IMuvQlz2BwM3", "Mark - 随意、放松、轻快"),
    ("5l5f8iK3YPeGga21rQIX", "Adeline - 女性化、对话式"),
    ("scOwDtmlUjD3prqpp97I", "Sam - 客服代理"),
    ("NOpBlnGInO9m6vDvFkFC", "Spuds Oxley - 睿智、平易近人"),
    ("BZgkqPqms7Kj9ulSkVzn", "Eve - 真实、充满活力、快乐"),
    ("wo6udizrrtpIxWGp2qJk", "Northern Terry"),
    ("gU0LNdkMOQCOrPrwtbee", "British Football Announcer - 英国足球解说员"),
    ("DGzg6RaUqxGRTHSBjfgF", "Brock - 威严、大声的军士"),
    ("x70vRnQBMBu4FAYhjJbO", "Nathan - 虚拟电台主持人"),
    ("Sm1seazb4gs7RSlUVw7c", "Anika - 活泼、友好、引人入胜"),
    ("P1bg08DkjqiVEzOn76yG", "Viraj - 丰富、柔和"),
    ("qDuRKMlYmrm8trt5QyBn", "Taksh - 平静、严肃、流畅"),
    ("qXpMhyvQqiRxWQs4qSSB", "Horatius - 充满活力的角色配音"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam - 充满活力、社交媒体创作者"),
    ("N2lVS1w4EtoT3dr4eOWO", "Callum - 沙哑的骗子"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura - 热情、古怪的态度"),
    ("kPzsL2i3teMYv0FxEYQ6", "Brittney - 社交媒体语音 - 有趣、年轻、信息丰富"),
    ("UgBBYS2sOqTuMpoF3BR0", "Mark - 自然对话"),
    ("hpp4J3VqNfWAUOO0d1Us", "Bella - 专业、明亮、温暖"),
    ("nPczCjzI2devNBz1zQrb", "Brian - 低沉、共鸣、令人安慰"),
    ("uYXf8XasLslADfZ2MB4u", "Hope - 活泼、八卦、少女感"),
    ("gs0tAILXbY5DNrJrsM6F", "Jeff - 优雅、共鸣、强劲"),
    ("DTKMou8ccj1ZaWGBiotd", "Jamahal - 年轻、充满活力、自然"),
    ("vBKc2FfBKJfcZNyEt1n6", "Finn - 年轻、热切、充满活力"),
    ("DYkrAHD8iwork3YSUBbs", "Tom - 对话与书籍"),
    ("56AoDkrOh6qfVPDXZ7Pt", "Cassidy - 清脆、直接、清晰"),
    ("eR40ATw9ArzDf9h3v7t7", "Addison 2.0 - 澳大利亚有声书与播客"),
    ("g6xIsTj2HwM6VR4iXFCw", "Jessica Anne Bogart - 健谈、友好"),
    ("lcMyyd2HUfFzxdCaC4Ta", "Lucy - 清新、随意"),
    ("6aDn1KB0hjpdcocrUkmq", "Tiffany - 自然、热情"),
    ("Sq93GQT4X1lKDXsQcixO", "Felix - 温暖、积极、现代RP"),
    ("flHkNRp1BlvT73UL6gyz", "Jessica Anne Bogart - 雄辩的反派"),
    ("9yzdeviXkFddZ4Oz8Mok", "Lutz - 咯咯笑、欢快"),
    ("pPdl9cQBQq4p6mRkZy2Z", "Emma - 可爱、积极向上"),
    ("zYcjlYFOd3taleS0gkk3", "Edward - 大声、自信、自负"),
    ("nzeAacJi50IvxcyDnMXa", "Marshal - 友好、幽默的教授"),
    ("ruirxsoakN0GWmGNIo04", "John Morgan - 粗犷、坚韧的牛仔"),
    ("TC0Zp7WVFzhA8zpTlRqV", "Aria - 性感反派"),
    ("ljo9gAlSqKOvF6D8sOsX", "Viking Bjorn - 史诗中世纪掠夺者"),
    ("PPzYpIqttlTYA83688JI", "Pirate Marshal - 海盗元帅"),
    ("8JVbfL6oEdmuxKn5DK2C", "Johnny Kid - 严肃、平静的旁白"),
    ("iCrDUkL56s3C8sCRl7wb", "Hope - 诗意、浪漫、迷人"),
    ("wJqPPQ618aTW29mptyoc", "Ana Rita - 流畅、富有表现力、明亮"),
    ("EiNlNiXeDU1pqqOPrYMO", "John Doe - 低沉"),
    ("4YYIPFl9wE5c4L2eu2Gb", "Burt Reynolds - 低沉、流畅、清晰"),
    ("6F5Zhi321D3Oq7v1oNT4", "Hank - 低沉、引人入胜的旁白"),
    ("YXpFCvM1S3JbWEJhoskW", "Wyatt - 睿智乡村牛仔"),
    ("LG95yZDEHg6fCZdQjLqj", "Phil - 爆发力、热情播音员"),
    ("CeNX9CMwmxDxUF5Q2Inm", "Johnny Dynamite - 复古电台DJ"),
    ("aD6riP1btT197c6dACmy", "Rachel M - 专业英国电台主持人"),
    ("mtrellq69YZsNwzUSyXh", "Rex Thunder - 低沉强硬"),
    ("dHd5gvgSOzSfduK4CvEg", "Ed - 深夜播音员"),
    ("eVItLK1UvXctxuaRV2Oq", "Jean - 迷人、俏皮的蛇蝎美人"),
    ("esy0r39YPLQjOczyOib8", "Britney - 冷静、算计的反派"),
    ("Tsns2HvNFKfGiNjllgqo", "Sven - 情感丰富、友善"),
    ("1U02n4nD6AdIZ9CjF053", "Viraj - 流畅、温柔"),
    ("AeRdCCKzvd23BpJoofzx", "Nathaniel - 引人入胜、英式、平静"),
    ("LruHrtVF6PSyGItzMNHS", "Benjamin - 低沉、温暖、平静"),
    ("1wGbFxmAM3Fgw63G1zZJ", "Allison - 平静、舒缓、冥想"),
    ("hqfrgApggtO1785R4Fsn", "Theodore HQ - 宁静、沉稳"),
    ("MJ0RnG71ty4LH3dvNfSd", "Leon - 舒缓、沉稳"),
)
VOICE_IDS = [v[0] for v in VOICES]
VOICE_NAME = dict(VOICES)

# 播客场景最常用的 8 个（catalog 默认只列这些）
PODCAST_VOICES = ["eR40ATw9ArzDf9h3v7t7", "8JVbfL6oEdmuxKn5DK2C", "6F5Zhi321D3Oq7v1oNT4",
                  "aD6riP1btT197c6dACmy", "x70vRnQBMBu4FAYhjJbO", "nPczCjzI2devNBz1zQrb",
                  "hpp4J3VqNfWAUOO0d1Us", "1SM7GgM6IMuvQlz2BwM3"]

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
    """发一次请求。网关会掐空闲连接（WinError 10054），网络类错误退避重试；
    4xx / 业务错误直接返回给调用方判断。"""
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
                last = "HTTP %s" % e.code
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = getattr(e, "reason", e)
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, last, retries - 1), EXIT_CALL)
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
    return (txt or "").replace("\n", " ")[:300]


def envelope(st, txt, url):
    """网关成功判据：HTTP 200 且 code ∈ {1,200}。校验失败也是 200，但 code=0。"""
    d = jloads(txt)
    if st != 200:
        raise Fail("call", "调用失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    if not isinstance(d, dict):
        raise Fail("call", "返回不是 JSON：%s" % (txt or "")[:200], EXIT_CALL)
    code = d.get("code")
    if code not in (1, 200, None):
        raise Fail("call", "上游拒绝（%s）：%s" % (url.rsplit("/", 1)[-1],
                                                 d.get("msg") or err_text(st, txt)), EXIT_CALL)
    return d.get("data")


def api_get(a, key, host, path, timeout=60):
    return envelope(*http_json("GET", host + path, key, None, timeout), url=path)


def api_post(a, key, host, code, body, timeout=120):
    url = host + APP_PATH + code
    return envelope(*http_json("POST", url, key, body, timeout), url=url)


# ───────────────────────── 价格与闸门 ─────────────────────────
def est_points(tasks=1):
    """下限估算：条数 × 60 点（实测每次 POST 先冻 60，失败全退）。"""
    return max(1, int(tasks)) * RESERVE_POINTS


def gate(a, tasks, what="本次"):
    """两道闸门：预算不够 → 5（不发请求）；没 --yes → 4（并告诉你花多少）。"""
    cost = est_points(tasks)
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点（%d 条 × %d 点下限）超过 --budget %d 点"
                   "（单位：点，1 元 = 100 点）。一个请求都没发，调大 --budget 再试。"
                   % (cost, tasks, RESERVE_POINTS, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实提交 %d 条任务，**下限 %d 点（%.2f 元）**，"
                   "成交价 = 上游实际点数 × %d、保底 %d 点，按任务详情结算。"
                   "确认请加 --yes。"
                   % (tasks, cost, cost / float(POINTS_PER_YUAN),
                      UPSTREAM_MARKUP, MIN_POINTS), EXIT_CONFIRM)
    return cost


def _need(a, *names):
    miss = []
    for n in names:
        val = getattr(a, n.replace("-", "_"), None)
        if val is None or (isinstance(val, str) and not val.strip()):
            miss.append("--" + n)
    if miss:
        raise Fail("usage", "缺必填参数：%s" % " ".join(miss), EXIT_USAGE)


def _check_range(name, val, lo, hi):
    if val is None:
        return
    if val < lo or val > hi:
        raise Fail("usage", "%s 必须在 %s–%s 之间（当前 %s）" % (name, lo, hi, val), EXIT_USAGE)


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                            # noqa: BLE001
        return str(n)


def _w(s):
    """显示宽度：中日韩字符算 2 列，表格才对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width):
    s = str(s)
    return s + " " * max(0, width - _w(s))


def rpad(s, width):
    s = str(s)
    return " " * max(0, width - _w(s)) + s


def read_text(path):
    """读文稿：UTF-8 优先，退 GB18030（Windows 记事本最常见的两种情况）。"""
    raw = io.open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except Exception:                                        # noqa: BLE001
            continue
    raise Fail("usage", "读不了 %s：请存成 UTF-8 或 GB18030" % path, EXIT_USAGE)


def chunk_text(text, limit):
    """按句子切片，保证每片 ≤ limit 字符（schema: text maxLength 5000）。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    units = []
    for para in re.split(r"\n+", text):
        para = para.strip()
        if not para:
            continue
        for s in re.findall(r"[^。！？!?；;…]+[。！？!?；;…]?", para):
            s = s.strip()
            while len(s) > limit:                  # 单句超长就硬切
                units.append(s[:limit])
                s = s[limit:]
            if s:
                units.append(s)
    chunks, cur = [], ""
    for u in units:
        if not cur:
            cur = u
            continue
        sep = "" if (cur[-1].isascii() is False or u[:1].isascii() is False) else " "
        if len(cur) + len(sep) + len(u) <= limit:
            cur += sep + u
        else:
            chunks.append(cur)
            cur = u
    if cur:
        chunks.append(cur)
    return chunks or [text[:limit]]


def estimate_script(text, chunk_chars):
    """按切片宽度算配音条数与每片字数（cost / 闸门都用它）。"""
    chunks = chunk_text(text, chunk_chars)
    return len(chunks), [len(c) for c in chunks]


# ───────────────────────── 结果解析 ─────────────────────────
def _walk_audio(node, rows, depth=0):
    if depth > 6:
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


def _num(v):
    try:
        return round(float(v), 3)
    except Exception:                                            # noqa: BLE001
        return None


def find_lines(data, depth=0):
    """从结果里挖出逐句时间轴：[{start, end, text}]。

    上游字段名不固定（start / start_time / startTime…），所以广度遍历，
    只收「有开始时间 + 有文本」的字典，按开始时间排序。
    """
    found = []
    if depth > 8:
        return found
    if isinstance(data, dict):
        st = None
        for k in ("start", "start_time", "startTime", "start_s", "from"):
            if k in data:
                st = _num(data.get(k))
                if st is not None:
                    break
        tx = None
        for k in ("text", "line", "sentence", "content", "word"):
            if isinstance(data.get(k), str) and data.get(k).strip():
                tx = data[k].strip()
                break
        if st is not None and tx:
            en = None
            for k in ("end", "end_time", "endTime", "end_s", "to"):
                if k in data:
                    en = _num(data.get(k))
                    if en is not None:
                        break
            found.append({"start": st, "end": en, "text": tx})
            return found
        for v in data.values():
            found.extend(find_lines(v, depth + 1))
    elif isinstance(data, list):
        for v in data:
            found.extend(find_lines(v, depth + 1))
    return found


def hhmmss(sec):
    try:
        sec = max(0.0, float(sec))
    except Exception:                                            # noqa: BLE001
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h:
        return "%d:%02d:%02d" % (h, m, int(s))
    return "%02d:%02d" % (m, int(s))


def srt_time(sec):
    sec = max(0.0, float(sec or 0))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


# ───────────────────────── 台账 ─────────────────────────
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
    for e in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4"):
        if e in url.split("?")[0].lower():
            ext = e
            break
    p = os.path.join(outdir, "%s-%02d%s" % (prefix, idx, ext))
    io.open(p, "wb").write(raw)
    return p


# ───────────────────────── 免费：catalog ─────────────────────────
def _app_apis(a, key, host):
    """GET /api/v1/apps —— pricing 里这条 cost:0，实测 0 点。"""
    d = api_get(a, key, host, API_PREFIX + "/apps", timeout=90)
    for app in (d or []):
        if isinstance(app, dict) and app.get("code") == APP:
            return app.get("apis") or []
    return []


def cmd_catalog(a, key, host):
    apis = _app_apis(a, key, host)
    by = {it.get("code"): it for it in apis if isinstance(it, dict)}
    rows = []
    for line in ("vo", "bgm", "subs"):
        m = ENDPOINTS[line]
        it = by.get(m["code"]) or {}
        rows.append({"line": line, "code": m["code"], "name": m["name"],
                     "engine": m["engine"], "path": APP_PATH + m["code"],
                     "required": m["required"], "optional": m["optional"],
                     "desc": m["desc"], "online": bool(it)})
    out = {"ok": True, "app": APP, "appApis": len(apis), "lines": rows,
           "voices": len(VOICES), "models": GEN_MODELS,
           "priceRule": {"markup": UPSTREAM_MARKUP, "minPoints": MIN_POINTS,
                         "reservePerCall": RESERVE_POINTS, "isLowerBound": True},
           "query": API_PREFIX + "/tasks/<task_id>"}
    if a.voices:
        out["voiceList"] = [{"id": i, "name": n} for i, n in VOICES]
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 播客生产线 —— 三条接口，一段文稿出成品播客")
    print()
    for r in rows:
        print("  %s %s  %s" % (pad(r["line"], 5), pad(r["name"], 12),
                               "%s（%s）" % (r["engine"], "在架 √" if r["online"] else "未在架 ×")))
        print("      路径  POST %s" % r["path"])
        print("      必填  %s" % " ".join(r["required"]))
        print("      说明  %s" % r["desc"])
        print()
    print("  --line 对应子命令：vo 配音 / bgm 配乐 / subs 字幕")
    print("  应用 %s：现查 %d 个接口，本包接其中 3 个（读 GET /api/v1/apps，0 点）"
          % (APP, len(apis)))
    print()
    print("  价格口径（诚实版）")
    print("    /api/v1/pricing 共 115 条规则，没有 %s 的专属条目，落通配：" % APP)
    print("    对外 = 上游实际点数 × %d，单笔保底 %d 点（1 元 = 100 点）"
          % (UPSTREAM_MARKUP, MIN_POINTS))
    print("    实测每次 POST 先 reserve_sync 冻 %d 点，失败全额退 —— 所以 cost 是下限估算。"
          % RESERVE_POINTS)
    print()
    print("  配音音色（%d 个，--voices 看全部）" % len(VOICES))
    for vid in PODCAST_VOICES:
        print("    %s  %s" % (vid, VOICE_NAME.get(vid, "")))
    if not a.voices:
        print("    … 其余 %d 个见 `catalog --voices`（含 67 行 id + 名字）"
              % (len(VOICES) - len(PODCAST_VOICES)))
    else:
        print()
        print("  全部 67 个音色（id  名字）")
        for i, n in VOICES:
            print("    %s  %s" % (i, n))
    print()
    print("  model（bgm）：%s —— 官方建议 V6 / V6_MINI / V6_WILD"
          % " / ".join(GEN_MODELS))
    print("  查询：GET %s（只读，0 点）" % out["query"])
    return 0


# ───────────────────────── 免费：cost ─────────────────────────
def cmd_cost(a, key, host):
    parts = []
    chars, src, voice_n = 0, None, 0
    if a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "文件不存在：%s" % a.script, EXIT_USAGE)
        text = read_text(a.script)
        chars = len(re.sub(r"\s+", "", text))
        src = a.script
    elif a.chars:
        chars = max(0, int(a.chars))
        src = "直接给字数"
    if a.lines:
        voice_n = max(1, int(a.lines))
        src = "直接给条数"
        parts.append({"part": "配音 vo", "tasks": voice_n, "chars": None})
    elif chars:
        voice_n, sizes = estimate_script("字" * chars, a.chunk_chars)
        parts.append({"part": "配音 vo", "tasks": voice_n, "chars": chars,
                      "chunkSizes": sizes})
    if a.bgm:
        parts.append({"part": "配乐 bgm", "tasks": 1})
    if a.subs:
        parts.append({"part": "字幕 subs", "tasks": 1})
    if not parts:
        parts = [{"part": "最少一次请求", "tasks": 1}]
    tasks = sum(p["tasks"] for p in parts)
    floor = est_points(tasks)
    alt = None
    if a.upstream:
        per = max(MIN_POINTS, int(round(float(a.upstream) * UPSTREAM_MARKUP)))
        alt = {"perTask": per, "tasks": tasks, "points": per * tasks,
               "yuan": round(per * tasks / float(POINTS_PER_YUAN), 2)}
    out = {"ok": True, "source": src, "chars": chars, "chunkChars": a.chunk_chars,
           "parts": parts, "tasks": tasks, "pointsFloor": floor,
           "yuan": round(floor / float(POINTS_PER_YUAN), 2),
           "isLowerBound": True, "minPoints": MIN_POINTS,
           "markup": UPSTREAM_MARKUP, "reservePerCall": RESERVE_POINTS,
           "upstreamAlt": alt,
           "basis": "pricing 无 %s 专属规则 → 落通配：上游实际点数 × %d，单笔保底 %d 点"
                    % (APP, UPSTREAM_MARKUP, MIN_POINTS)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("先算钱（1 元 = 100 点）")
    print()
    if src:
        print("  来源：%s（%d 字，按 %d 字一片 → 配音 %d 条）"
              % (src, chars, a.chunk_chars, voice_n))
    print("  %s %s %s" % (pad("零件", 26), rpad("条数", 6), rpad("下限(点)", 10)))
    print("  " + "-" * 46)
    for p in parts:
        print("  %s %s %s" % (pad(p["part"], 26), rpad(p["tasks"], 6),
                              rpad(fmt_pts(est_points(p["tasks"])), 10)))
    print("  " + "-" * 46)
    print("  %s %s %s" % (pad("合计", 26), rpad(tasks, 6), rpad(fmt_pts(floor), 10)))
    print()
    print("  = **%d 点 = %.2f 元**（下限）" % (floor, floor / float(POINTS_PER_YUAN)))
    if alt:
        print("  按你给的上游 %d 点换算：单条 %d 点 × %d 条 = **%d 点 = %.2f 元**"
              % (a.upstream, alt["perTask"], tasks, alt["points"], alt["yuan"]))
    print()
    for n in ("规则：/api/v1/pricing 里没有 %s 的专属条目，落通配「上游实际点数 × %d，"
              "单笔保底 %d 点」" % (APP, UPSTREAM_MARKUP, MIN_POINTS),
              "实测每次 POST 先 reserve_sync 冻 %d 点、失败全额退 —— 所以下限按 %d 点/条算"
              % (RESERVE_POINTS, RESERVE_POINTS),
              "成交价要真跑一条、看任务详情里的 usage；用 `cost --upstream 65` 按你观察到的"
              "上游点数换算",
              "配音单条上限 %d 字，长文稿本包自动切片（默认 %d 字/片）"
              % (TTS_MAX_CHARS, DEFAULT_CHUNK),
              "任务失败全额退回；成功那一单按上游实际点数结算"):
        print("  · %s" % n)
    return 0


# ───────────────────────── 免费：doctor ─────────────────────────
def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + "/user/balance", key, None, 40)
    d = jloads(txt) or {}
    checks.append(("Key 有效 + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(d.get("available_points") or 0),
                       fmt_pts(d.get("frozen") or 0))))

    apis = _app_apis(a, key, host)
    codes = {it.get("code") for it in apis if isinstance(it, dict)}
    miss = [m["code"] for m in ENDPOINTS.values() if m["code"] not in codes]
    checks.append(("应用在架 + 三条接口齐全", bool(apis) and not miss,
                   "GET /api/v1/apps · 该应用 %d 个接口%s"
                   % (len(apis), "，缺 " + ",".join(miss) if miss else "")))

    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, None, 40)
    d_p = jloads(txt_p) or {}
    pr = d_p.get("pricing") if isinstance(d_p.get("pricing"), dict) else {}
    star = pr.get("*") or {}
    dedicated = [k for k in pr if APP in str(k) or "music_generate" in str(k)
                 or "elevenlabs" in str(k)]
    ok_p = (st_p == 200 and not dedicated
            and int(star.get("minPoints") or 0) == MIN_POINTS
            and int(star.get("markupPercent") or 0) == 100)
    checks.append(("价目表一致 + 无专属规则（落通配）", ok_p,
                   "HTTP %s · 规则 %d 条 · 通配 minPoints=%s markup=%s%%%s"
                   % (st_p, len(pr), star.get("minPoints"), star.get("markupPercent"),
                      "，专属 " + str(dedicated) if dedicated else "")))

    st_a, txt_a = http_json("GET", host + API_PREFIX + "/apps", key, None, 60)
    d_a = jloads(txt_a) or {}
    checks.append(("GET /api/v1/apps 计价 = cost 0（免费读目录）",
                   st_a == 200 and (pr.get(API_PREFIX + "/apps") or {}).get("cost") == 0,
                   "HTTP %s · %s" % (st_a, "cost 0，实测 0 点")))

    st_t, txt_t = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-podcast-line-probe",
                            key, None, 40)
    d_t = jloads(txt_t) or {}
    checks.append(("查询路由 GET /tasks/<id> 可用（假 id 即正确）", 
                   st_t == 200 and d_t.get("code") == 0 and "不存在" in str(d_t.get("msg")),
                   "HTTP %s code=%s %s" % (st_t, d_t.get("code"), str(d_t.get("msg"))[:30])))

    if a.probe:
        probes = [
            (VOICE_API, {}, "配音端点"),
            (BGM_API, {}, "配乐端点"),
            (SUBS_API, {}, "字幕端点"),
        ]
        pts0, _txt0 = _balance(a, key, host)
        for code, body, label in probes:
            say("  探 %-46s …" % code)
            st2, txt2 = http_json("POST", host + APP_PATH + code, key, body, timeout=a.timeout)
            d2 = jloads(txt2) or {}
            ok2 = st2 == 200 and d2.get("code") == 0 and "缺少必填参数" in str(d2.get("msg"))
            checks.append(("%s 参数校验在位（缺必填即拦下）" % label, ok2,
                           "HTTP %s %s" % (st2, str(d2.get("msg"))[:60])))
        time.sleep(2)
        pts1, _t1 = _balance(a, key, host)
        checks.append(("探针净花费 = 0 点（冻 %d 全退）" % RESERVE_POINTS,
                       pts0 is not None and pts1 is not None and abs(pts1 - pts0) < 0.001,
                       "探前 %s 点 → 探后 %s 点" % (fmt_pts(pts0 or 0), fmt_pts(pts1 or 0))))

    out = {"ok": all(c[1] for c in checks), "app": APP, "host": host,
           "probe": bool(a.probe),
           "endpoint": host + APP_PATH + "<接口code>",
           "taskEndpoint": host + API_PREFIX + "/tasks/<task_id>",
           "priceRule": {"markup": UPSTREAM_MARKUP, "minPoints": MIN_POINTS,
                         "reservePerCall": RESERVE_POINTS, "isLowerBound": True},
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print()
    print("自检（默认全是只读 GET，0 点；加 --probe 才发 3 条空 body POST，冻 %d 全退）"
          % RESERVE_POINTS)
    print()
    for n, o, dt in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 44), dt))
    print()
    print("  端点：POST %s" % out["endpoint"])
    print("  查询：GET  %s" % out["taskEndpoint"])
    print("  价格：上游实际点数 × %d，单笔保底 %d 点；实测每条冻 %d 点（下限口径）"
          % (UPSTREAM_MARKUP, MIN_POINTS, RESERVE_POINTS))
    if not a.probe:
        print("  想看三条端点的参数校验？加 --probe（会冻 %d 点、立刻全退，净 0）。"
              % RESERVE_POINTS)
    return 0 if out["ok"] else EXIT_GATE


def _balance(a, key, host):
    st, txt = http_json("GET", host + "/user/balance", key, None, 40)
    d = jloads(txt) or {}
    try:
        return float(d.get("available_points")), txt
    except Exception:                                            # noqa: BLE001
        return None, txt


# ───────────────────────── 免费：chapters（本地）─────────────────────────
HEAD_RE = re.compile(r"^\s{0,3}#{1,3}\s+(.+?)\s*$")
CN_RE = re.compile(r"^\s*(第[一二三四五六七八九十百零〇\d]{1,6}[章集期部分节])\s*[：:、.．\-—]?\s*(.{0,40})$")


def parse_script_sections(path):
    text = read_text(path)
    sections, cur, pre = [], None, []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = HEAD_RE.match(line)
        m2 = CN_RE.match(line) if (not m and len(line.strip()) <= 44) else None
        if m:
            cur = {"title": m.group(1).strip(), "body": []}
            sections.append(cur)
            continue
        if m2:
            title = (m2.group(1) + (" " + m2.group(2).strip() if m2.group(2).strip() else "")).strip()
            cur = {"title": title, "body": []}
            sections.append(cur)
            continue
        if cur is None:
            pre.append(line)
        else:
            cur["body"].append(line)
    if pre and any(x.strip() for x in pre):
        sections.insert(0, {"title": "开场", "body": pre})
    for s in sections:
        s["text"] = "\n".join(s["body"]).strip()
        s["title"] = re.sub(r"^[#\s]+", "", s["title"]).strip()
    return [s for s in sections if s["title"] or s["text"]]


def _norm(s):
    """去掉空白与标点，只留字，便于两边对齐。"""
    return re.sub(r"[\s\u3000-\u303f\uff00-\uffef\W_]+", "", s or "", flags=re.UNICODE)


def parse_srt(path):
    text = read_text(path)
    cues = []
    tline = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
    for block in re.split(r"\n\s*\n", text):
        lines = [x for x in block.split("\n") if x.strip()]
        if not lines:
            continue
        idx, tl = 0, None
        for i, ln in enumerate(lines[:3]):
            m = tline.search(ln)
            if m:
                idx, tl = i, m
                break
        if not tl:
            continue
        start = int(tl.group(1)) * 3600 + int(tl.group(2)) * 60 + int(tl.group(3)) + \
            int(tl.group(4).ljust(3, "0")) / 1000.0
        end = int(tl.group(5)) * 3600 + int(tl.group(6)) * 60 + int(tl.group(7)) + \
            int(tl.group(8).ljust(3, "0")) / 1000.0
        body = " ".join(x.strip() for x in lines[idx + 1:]).strip()
        if body:
            cues.append({"start": round(start, 3), "end": round(end, 3), "text": body})
    return cues


def load_cues(a):
    if a.srt:
        if not os.path.isfile(a.srt):
            raise Fail("usage", "文件不存在：%s" % a.srt, EXIT_USAGE)
        return parse_srt(a.srt), a.srt
    if a.subs:
        if not os.path.isfile(a.subs):
            raise Fail("usage", "文件不存在：%s" % a.subs, EXIT_USAGE)
        d = jloads(read_text(a.subs))
        if d is None:
            raise Fail("usage", "%s 不是 JSON；字幕也可以用 --srt 给" % a.subs, EXIT_USAGE)
        rows = d.get("lines") if isinstance(d, dict) else d
        if not isinstance(rows, list):
            rows = find_lines(d)
        cues = []
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            cues.append({"start": _num(r.get("start")) or 0.0,
                         "end": _num(r.get("end")), "text": str(r.get("text") or "")})
        return [c for c in cues if c["text"]], a.subs
    return [], None


def cmd_chapters(a, key, host):
    if not a.script:
        raise Fail("usage", "缺必填参数：--script（带章节标题的文稿）", EXIT_USAGE)
    if not a.script or not os.path.isfile(a.script):
        raise Fail("usage", "文件不存在：%s" % (a.script or ""), EXIT_USAGE)
    sections = parse_script_sections(a.script)
    if not sections:
        raise Fail("usage", "文稿里没找到标题行（形如 `## 第 1 章 开场`）", EXIT_USAGE)
    cues, src = load_cues(a)
    if not cues:
        raise Fail("usage", "缺时间轴：给 --srt（SRT/VTT）或 --subs（本包 subs 出的 JSON）",
                   EXIT_USAGE)

    # 字幕累计字数 → 每个字落在第几秒
    bounds, acc = [], 0.0
    for c in cues:
        n = len(_norm(c["text"]))
        if n <= 0:
            n = 1
        acc += n
        bounds.append(acc)
    total_cue = acc
    # 文稿：只算正文（标题不会被念出来），章节起点按正文累计字数
    marks, total_script = [], 0.0
    for s in sections:
        marks.append(total_script)
        total_script += max(1, len(_norm(s["text"])))
    if total_script <= 0:
        raise Fail("usage", "文稿正文是空的", EXIT_USAGE)
    # 真实的「念出来的字数」和「字幕字数」不会完全相等，按比例缩放到时间轴
    scale = (total_cue / total_script) if total_script else 1.0

    def cue_start_at(target_chars):
        target = target_chars * scale
        lo, hi = 0, len(bounds) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if bounds[mid] > target:
                if mid == 0 or bounds[mid - 1] <= target:
                    return cues[mid]["start"]
                hi = mid - 1
            else:
                lo = mid + 1
        return cues[-1]["start"]

    chapters = []
    for i, s in enumerate(sections):
        start = 0.0 if i == 0 else cue_start_at(marks[i])
        if i + 1 < len(sections):
            end = cue_start_at(marks[i + 1])
        else:
            end = cues[-1].get("end") or cues[-1]["start"]
        if end is None or end < start:
            end = start
        chapters.append({"index": i + 1, "title": s["title"] or ("第 %d 段" % (i + 1)),
                         "start": round(start, 3), "end": round(end, 3),
                         "duration": round(max(0.0, end - start), 3),
                         "at": hhmmss(start)})

    lines = ["%s %s" % (c["at"], c["title"]) for c in chapters]
    out = {"ok": True, "script": a.script, "timeline": src, "chapterCount": len(chapters),
           "scriptChars": int(total_script), "timelineChars": int(total_cue),
           "chapters": chapters, "text": "\n".join(lines)}
    if a.out:
        io.open(a.out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        out["file"] = a.out
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("章节目录（本地算，0 点）")
    print("  文稿：%s（%d 段 / %d 字）" % (a.script, len(sections), int(total_script)))
    print("  时间轴：%s（%d 句 / %d 字）" % (src, len(cues), int(total_cue)))
    print()
    print("  %s %s %s %s %s" % (pad("#", 4), pad("开始", 8), pad("结束", 8),
                                pad("时长", 8), "章节"))
    print("  " + "-" * 64)
    for c in chapters:
        print("  %s %s %s %s %s" % (pad(c["index"], 4), pad(c["at"], 8),
                                    pad(hhmmss(c["end"]), 8),
                                    pad(hhmmss(c["duration"]), 8), c["title"]))
    print()
    print("  直接贴到发布后台的章节块（复制即用）")
    for ln in lines:
        print("    %s" % ln)
    if a.out:
        print()
        print("  已写：%s" % a.out)
    return 0


# ───────────────────────── 任务 ─────────────────────────
def get_task(a, key, host, task_id):
    d = api_get(a, key, host, API_PREFIX + "/tasks/" + urllib.parse.quote(task_id))
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
            say("  状态：%s" % (st or "?"))
            last = st
        if st in TERMINAL_OK or st in TERMINAL_BAD:
            return d
    raise Fail("call", "等了 %d 秒还没完成。任务没丢 —— 用 `task --task-id %s` 接着取，"
                       "**不要重新提交**（会再扣一次）。" % (a.wait, task_id), EXIT_CALL)


def _submit(a, key, host, line):
    code = ENDPOINTS[line]["code"]
    url = host + APP_PATH + code
    body = a.body
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "line": line, "code": code, "url": url,
               "requestBody": body, "requestCount": a.tasks,
               "estimatedPoints": a.cost, "isLowerBound": True,
               "requests": a.planned}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return None
        print("干跑（不提交、不冻结、不扣费）")
        print("  条数：%d · 下限 %d 点（%.2f 元）"
              % (a.tasks, a.cost, a.cost / float(POINTS_PER_YUAN)))
        for i, item in enumerate(a.planned, 1):
            print("  #%d %s" % (i, url))
            print("      请求：%s" % json.dumps(item, ensure_ascii=False)[:400])
        return None
    say("正在提交 %s（%s）…" % (line, ENDPOINTS[line]["name"]))
    t0 = time.time()
    data = api_post(a, key, host, code, body, timeout=max(60, a.timeout))
    dt = time.time() - t0
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    return {"data": data, "task_id": task_id, "elapsed": round(dt, 1)}


def _collect(a, key, host, line, manifest):
    """对已提交的 (task_id, body) 逐个取结果。返回 (rows, failed)。"""
    rows, bad = [], []
    for i, item in enumerate(manifest, 1):
        tid = item["task_id"]
        say("  [%d/%d] task_id=%s" % (i, len(manifest), tid))
        if a.no_wait:
            rows.append({"index": i, "task_id": tid, "submitted": True,
                         "chars": item.get("chars"),
                         "next": "python3 scripts/run.py task --task-id %s" % tid})
            continue
        try:
            t = wait_task(a, key, host, tid)
        except Fail as e:
            bad.append({"index": i, "task_id": tid, "error": e.message})
            continue
        st = str(t.get("status") or "").lower()
        audio = find_audio(t)
        lines = find_lines(t) if line == "subs" else []
        paths = []
        if a.out and audio:
            for j, r in enumerate(audio, 1):
                try:
                    paths.append(download(r["audio_url"], a.out, "%s-%02d" % (a.prefix, i), j))
                except Exception as e:                           # noqa: BLE001
                    say("  下载失败（%s）：%s" % (r["audio_url"], e))
        rec = {"index": i, "task_id": tid, "status": st, "chars": item.get("chars"),
               "audios": audio, "lines": lines, "files": paths,
               "usage": t.get("usage") if isinstance(t.get("usage"), dict) else {},
               "error": t.get("error")}
        rows.append(rec)
        if st in TERMINAL_BAD:
            bad.append(rec)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "line": line, "ok": st in TERMINAL_OK,
                    "task_id": tid, "status": st, "chars": item.get("chars"),
                    "pointsFloor": RESERVE_POINTS,
                    "audio_ids": [r["audio_id"] for r in audio if r["audio_id"]],
                    "audio_urls": [r["audio_url"] for r in audio],
                    "lineCount": len(lines), "usage": rec["usage"], "files": paths})
    return rows, bad


def _report(a, line, rows, bad, manifest):
    ok = not bad
    out = {"ok": ok, "line": line, "api": ENDPOINTS[line]["code"],
           "requestCount": len(manifest), "tasks": rows,
           "estimatedPoints": a.cost, "isLowerBound": True,
           "manifest": [{"index": m["index"], "task_id": m["task_id"], "chars": m.get("chars")}
                        for m in manifest]}
    if a.manifest:
        io.open(a.manifest, "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, ensure_ascii=False, indent=1))
        out["manifestFile"] = a.manifest
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if ok else EXIT_CALL
    print()
    print("结果（%d 条，下限 %d 点；成交价看每条任务的 usage）"
          % (len(rows), a.cost))
    for r in rows:
        print()
        print("  #%d  task_id=%s  状态=%s%s"
              % (r["index"], r["task_id"], r.get("status") or "submitted",
                 "  （%d 字）" % r["chars"] if r.get("chars") else ""))
        if r.get("submitted"):
            print("      接着取：%s" % r["next"])
            continue
        for au in r.get("audios") or []:
            if au.get("audio_id"):
                print("      audio_id：%s  ← subs 要用它" % au["audio_id"])
            if au.get("duration"):
                print("      时长：%s 秒" % au["duration"])
            print("      音频：%s" % au["audio_url"])
        for ln in (r.get("lines") or [])[:12]:
            print("      %8.2fs  %s" % (ln["start"], ln["text"][:60]))
        if len(r.get("lines") or []) > 12:
            print("      … 还有 %d 句（--out 下载 / --json 看全量）"
                  % (len(r["lines"]) - 12))
        if not r.get("audios") and not r.get("lines"):
            print("      这条还没解析到音频 / 时间轴（没完成就是正常的）")
        for p in r.get("files") or []:
            print("      已存：%s" % p)
        if r.get("usage"):
            print("      上游用量：%s" % json.dumps(r["usage"], ensure_ascii=False)[:200])
        if r.get("error"):
            print("      错误：%s" % json.dumps(r["error"], ensure_ascii=False)[:200])
    if bad:
        print()
        print("  %d 条失败（失败任务全额退回，不占预算）" % len(bad))
    if a.manifest:
        print()
        print("  提交清单已写：%s" % a.manifest)
    return 0 if ok else EXIT_CALL


# ───────────────────────── vo：配音 ─────────────────────────
def _resolve_voice(val):
    """只收 67 个精确 ID。名字 / 模糊输入一律退 2 —— 本包不替用户猜，
    因为猜错会真的提交一条任务、真的预扣点数（实测这个坑很贵）。"""
    v = (val or "").strip()
    if not v:
        raise Fail("usage", "缺必填参数：--voice（67 个音色 ID 见 `catalog --voices`）",
                   EXIT_USAGE)
    if v in VOICE_IDS:
        return v
    by_name = [vid for vid, name in VOICES if v.lower() in name.lower()]
    hint = ""
    if by_name:
        hint = "；按名字你可能要的是 %s" % " / ".join(
            "%s（%s）" % (i, VOICE_NAME[i]) for i in by_name[:3])
    else:
        cand = difflib.get_close_matches(v, VOICE_IDS, n=2, cutoff=0.5)
        if cand:
            hint = "；最接近的 ID 是 %s" % " / ".join(cand)
    raise Fail("usage",
               "voice 要填音色 ID（67 个之一），本包不按名字猜、也不自动替换 —— "
               "猜错会真的提交一条任务。你给的是 %r%s。全部 ID 见 `catalog --voices`。"
               % (v, hint), EXIT_USAGE)


def cmd_vo(a, key, host):
    text = None
    if a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "文件不存在：%s" % a.script, EXIT_USAGE)
        text = read_text(a.script)
    elif a.text:
        text = a.text
    if not text or not text.strip():
        raise Fail("usage", "缺必填参数：--text 或 --script（要配音的文稿）", EXIT_USAGE)
    _check_range("--speed", a.speed, 0.7, 1.2)
    _check_range("--style", a.style, 0, 1)
    _check_range("--stability", a.stability, 0, 1)
    _check_range("--similarity", a.similarity, 0, 1)
    _check_range("--chunk-chars", a.chunk_chars, 200, TTS_MAX_CHARS)
    voice = _resolve_voice(a.voice)

    chunks = [text.strip()] if a.no_split else chunk_text(text, a.chunk_chars)
    if not chunks:
        raise Fail("usage", "文稿是空的", EXIT_USAGE)
    a.tasks = len(chunks)
    a.cost = gate(a, a.tasks)
    base = {"voice": voice}
    for k, v in (("speed", a.speed), ("style", a.style), ("stability", a.stability),
                 ("similarity_boost", a.similarity), ("previous_text", a.previous_text),
                 ("next_text", a.next_text)):
        if v is not None and v != "":
            base[k] = v
    if a.timestamps:
        base["timestamps"] = True
    a.planned = [dict(base, text=c) for c in chunks]
    a.body = a.planned[0]

    if a.dry_run:
        return _dry_many(a, "vo", chunks, base)

    manifest = []
    for i, ch in enumerate(chunks, 1):
        say("  [%d/%d] 提交 %d 字…" % (i, len(chunks), len(ch)))
        got = _post_one(a, key, host, "vo", dict(base, text=ch))
        if not got or not got.get("task_id"):
            raw = json.dumps((got or {}).get("data"), ensure_ascii=False)[:400]
            ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "line": "vo", "ok": False,
                        "chars": len(ch), "error": raw})
            raise Fail("call", "第 %d 片提交失败（没拿到 task_id）：%s" % (i, raw), EXIT_CALL)
        manifest.append({"index": i, "task_id": got["task_id"], "chars": len(ch)})

    rows, bad = _collect(a, key, host, "vo", manifest)
    return _report(a, "vo", rows, bad, manifest)


def _post_one(a, key, host, line, body):
    if a.dry_run:
        return None
    code = ENDPOINTS[line]["code"]
    t0 = time.time()
    data = api_post(a, key, host, code, body, timeout=max(60, a.timeout))
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    return {"data": data, "task_id": task_id, "elapsed": round(time.time() - t0, 1)}


def _dry_many(a, line, chunks, base):
    url = (getattr(a, "host", None) or DEFAULT_HOST) + APP_PATH + ENDPOINTS[line]["code"]
    reqs = [dict(base, text=c) for c in chunks]
    out = {"ok": True, "dryRun": True, "line": line,
           "code": ENDPOINTS[line]["code"], "url": url,
           "requestCount": len(reqs), "estimatedPoints": a.cost, "isLowerBound": True,
           "requests": [{"chars": len(c), "body": b} for c, b in zip(chunks, reqs)]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("干跑（不提交、不冻结、不扣费）")
    print("  条数：%d · 下限 %d 点（%.2f 元）"
          % (len(reqs), a.cost, a.cost / float(POINTS_PER_YUAN)))
    for i, b in enumerate(reqs, 1):
        if i > 3:
            print("  … 其余 %d 条同形（每片 ≤ %d 字）" % (len(reqs) - 3, a.chunk_chars))
            break
        print("  #%d POST %s" % (i, url))
        print("      请求：%s" % json.dumps(b, ensure_ascii=False)[:400])
    return 0


# ───────────────────────── bgm：配乐 ─────────────────────────
def cmd_bgm(a, key, host):
    if a.model not in GEN_MODELS:
        raise Fail("usage", "bgm 的 model 只能是：%s" % " / ".join(GEN_MODELS), EXIT_USAGE)
    if not (a.prompt or a.style or a.lyrics):
        raise Fail("usage",
                   "缺必填参数：--prompt / --style / --lyrics 至少给一项"
                   "（非自定义模式下这几项至少一项非空，否则上游拒绝）。", EXIT_USAGE)
    if a.custom:
        if not (a.style or a.lyrics or a.negative_tags):
            raise Fail("usage", "--custom 模式下 --style / --lyrics / --negative-tags "
                               "至少给一项（schema 原文）。", EXIT_USAGE)
        if not a.title:
            raise Fail("usage", "--custom 模式下 --title 是必填（≤80 字符）。", EXIT_USAGE)
    if a.title and len(a.title) > 80:
        raise Fail("usage", "--title 最多 80 字符（当前 %d）。" % len(a.title), EXIT_USAGE)
    _check_range("--duration", a.duration, 10, 360)
    _check_range("--variety", a.variety, 0, 4)

    body = {"model": a.model, "custom_mode": bool(a.custom),
            "instrumental": not a.vocal}
    for k, v in (("style", a.style), ("prompt", a.prompt), ("title", a.title),
                 ("lyrics", a.lyrics if (a.vocal or a.custom) else None),
                 ("negative_tags", a.negative_tags), ("duration", a.duration),
                 ("variety", a.variety)):
        if v is not None and v != "":
            body[k] = v
    a.tasks = 1
    a.cost = gate(a, a.tasks)
    a.body = body
    a.planned = [body]
    if a.dry_run:
        return _submit(a, key, host, "bgm") or 0
    got = _post_one(a, key, host, "bgm", body)
    if not got or not got.get("task_id"):
        raw = json.dumps((got or {}).get("data"), ensure_ascii=False)[:400]
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "line": "bgm", "ok": False,
                    "error": raw})
        raise Fail("call", "提交失败（没拿到 task_id）：%s" % raw, EXIT_CALL)
    manifest = [{"index": 1, "task_id": got["task_id"]}]
    rows, bad = _collect(a, key, host, "bgm", manifest)
    return _report(a, "bgm", rows, bad, manifest)


# ───────────────────────── subs：字幕 ─────────────────────────
def cmd_subs(a, key, host):
    _need(a, "task-id", "audio-id")
    body = {"task_id": a.task_id, "audio_id": a.audio_id}
    a.tasks = 1
    a.cost = gate(a, a.tasks)
    a.body = body
    a.planned = [body]
    if a.dry_run:
        return _submit(a, key, host, "subs") or 0
    got = _post_one(a, key, host, "subs", body)
    if not got or not got.get("task_id"):
        raw = json.dumps((got or {}).get("data"), ensure_ascii=False)[:400]
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "line": "subs", "ok": False,
                    "error": raw})
        raise Fail("call", "提交失败（没拿到 task_id）：%s" % raw, EXIT_CALL)
    manifest = [{"index": 1, "task_id": got["task_id"]}]
    rows, bad = _collect(a, key, host, "subs", manifest)
    # 顺手写一份 SRT，chapters 可以直接吃
    for r in rows:
        if r.get("lines"):
            srt = []
            for i, ln in enumerate(r["lines"], 1):
                st = ln["start"] or 0.0
                en = ln["end"] if ln.get("end") is not None else st + 2.0
                srt.append("%d\n%s --> %s\n%s\n" % (i, srt_time(st), srt_time(en), ln["text"]))
            body_txt = "\n".join(srt)
            r["srt"] = body_txt
            if a.srt_out:
                io.open(a.srt_out, "w", encoding="utf-8", newline="\n").write(body_txt)
    if a.srt_out and any(r.get("srt") for r in rows):
        say("  已写 SRT：%s" % a.srt_out)
    return _report(a, "subs", rows, bad, manifest)


# ───────────────────────── task / log ─────────────────────────
def cmd_task(a, key, host):
    _need(a, "task-id")
    t = get_task(a, key, host, a.task_id)
    st = str(t.get("status") or "").lower()
    audio = find_audio(t)
    lines = find_lines(t)
    paths = []
    if a.out and audio:
        for i, r in enumerate(audio, 1):
            try:
                paths.append(download(r["audio_url"], a.out, a.prefix, i))
            except Exception as e:                               # noqa: BLE001
                say("  下载失败：%s" % e)
    out = {"ok": True, "taskId": a.task_id, "status": st, "audios": audio,
           "lineCount": len(lines), "lines": lines[:200], "files": paths,
           "usage": t.get("usage"), "error": t.get("error")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (st or "?"))
    if audio:
        for i, r in enumerate(audio, 1):
            print("  #%d %s" % (i, r.get("title") or ""))
            if r.get("audio_id"):
                print("      audio_id：%s" % r["audio_id"])
            print("      音频：%s" % r["audio_url"])
    else:
        print("  这条还没解析到音频（没完成就是正常的）。")
    if lines:
        print("  逐句时间轴：%d 句（--json 看全量，`subs --srt-out` 可直接落 SRT）" % len(lines))
        for ln in lines[:8]:
            print("      %8.2fs  %s" % (ln["start"], ln["text"][:60]))
    for p in paths:
        print("  已存：%s" % p)
    if t.get("usage"):
        print("  上游用量：%s" % json.dumps(t["usage"], ensure_ascii=False)[:300])
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
        what = e.get("task_id") or e.get("error") or "-"
        print("  %s  %-5s %-5s  %-24s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("line") or "-",
            str(what)[:24], "下限 %s 点" % e.get("pointsFloor", "-")))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 播客生产线：一段文稿出成品播客（配音 + 配乐 + 字幕 + 章节）",
        epilog="端点：POST %s/api/v1/apps/media_services_33/<接口code>（vo/bgm/subs）· "
               "GET %s/api/v1/tasks/<task_id>（查询，0 点）"
               % (DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d = 5 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="三条接口 + 67 个音色 + 价格口径（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--voices", action="store_true", help="列出全部 67 个音色 ID + 名字")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：按文稿字数切片后给下限（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--script", help="文稿路径（按字数估配音条数）")
    p.add_argument("--chars", type=int, default=0, help="直接给字数（不想给文件时用）")
    p.add_argument("--lines", type=int, default=0, help="直接给配音条数")
    p.add_argument("--chunk-chars", dest="chunk_chars", type=int, default=DEFAULT_CHUNK,
                   help="配音切片字数，上限 %d（默认 %d）" % (TTS_MAX_CHARS, DEFAULT_CHUNK))
    p.add_argument("--bgm", action="store_true", help="把配乐那一条算进来")
    p.add_argument("--subs", action="store_true", help="把字幕那一条算进来")
    p.add_argument("--upstream", type=int, default=0,
                   help="你观察到的上游点数（换算成交价 = 上游 × 2，保底 50）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 三条接口 / 价目 / 查询路由（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--probe", action="store_true",
                   help="额外发 3 条空 body POST 验参数校验（冻 %d 点、立刻全退，净 0）"
                        % RESERVE_POINTS)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("chapters", help="文稿章节 + 字幕时间轴 → 章节目录（免费，0 点，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--script", help="带章节标题的文稿（`## 第 1 章 xxx` 或 `第1章 xxx`）")
    p.add_argument("--srt", help="字幕文件（SRT / VTT 文本）")
    p.add_argument("--subs", help="本包 subs 出的 JSON（含 lines）")
    p.add_argument("--out", help="把章节块写到这个文件（UTF-8）")
    p.set_defaults(fn=cmd_chapters)

    def add_wait(p):
        p.add_argument("--yes", action="store_true", help="确认真实计费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.add_argument("--no-wait", action="store_true", help="只提交，拿 task_id 就走")
        p.add_argument("--wait", type=int, default=600, help="等结果的上限秒数（默认 600）")
        p.add_argument("--every", type=int, default=5, help="轮询间隔秒数（默认 5）")
        p.add_argument("--timeout", type=int, default=120, help="单次请求超时秒数")
        p.add_argument("--out", default=None, help="把音频下载到这个目录（可选）")
        p.add_argument("--prefix", default="podcast", help="下载文件名前缀")
        p.add_argument("--manifest", default=None,
                       help="把 task_id 清单写到这个 JSON（断了也能接着取）")

    p = sub.add_parser("vo", help="配音：一段文稿出人声，自动按 4500 字切片（要 --yes）",
                       allow_abbrev=False)
    add_wait(p)
    p.add_argument("--text", help="直接给要配音的文本（≤%d 字）" % TTS_MAX_CHARS)
    p.add_argument("--script", help="文稿文件路径（超长自动切片）")
    p.add_argument("--voice", help="音色 ID（67 个见 `catalog --voices`），必填")
    p.add_argument("--chunk-chars", dest="chunk_chars", type=int, default=DEFAULT_CHUNK,
                   help="每片字数，上限 %d（默认 %d）" % (TTS_MAX_CHARS, DEFAULT_CHUNK))
    p.add_argument("--no-split", dest="no_split", action="store_true",
                   help="不切片，整篇一次提交（超过 %d 字上游会拒）" % TTS_MAX_CHARS)
    p.add_argument("--speed", type=float, default=None, help="语速 0.7–1.2")
    p.add_argument("--style", type=float, default=None, help="风格夸张度 0–1")
    p.add_argument("--stability", type=float, default=None, help="稳定性 0–1")
    p.add_argument("--similarity", type=float, default=None, help="相似度提升 0–1")
    p.add_argument("--timestamps", action="store_true",
                   help="让上游回逐词时间戳（做字幕用）")
    p.add_argument("--previous-text", dest="previous_text",
                   help="上一片文本，改善跨片连贯")
    p.add_argument("--next-text", dest="next_text", help="下一片文本，改善跨片连贯")
    p.set_defaults(fn=cmd_vo)

    p = sub.add_parser("bgm", help="配乐：给播客写片头 / 垫乐 / 转场（要 --yes）",
                       allow_abbrev=False)
    add_wait(p)
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="model：%s（默认 %s）" % ("/".join(GEN_MODELS), DEFAULT_MODEL))
    p.add_argument("--prompt", help="一句话描述想要的音乐")
    p.add_argument("--style", help="风格标签，例如 lo-fi piano / 国风 / 爵士")
    p.add_argument("--title", help="曲名（--custom 下必填，≤80 字符）")
    p.add_argument("--lyrics", help="歌词（--custom 或 --vocal 时用）")
    p.add_argument("--custom", action="store_true", help="自定义模式（自己给风格 / 歌词）")
    p.add_argument("--vocal", action="store_true", help="要人声（默认纯音乐垫乐）")
    p.add_argument("--duration", type=int, default=None, help="目标时长 10–360 秒")
    p.add_argument("--variety", type=int, default=None, help="多样性 0–4")
    p.add_argument("--negative-tags", dest="negative_tags", help="要避开的风格")
    p.set_defaults(fn=cmd_bgm)

    p = sub.add_parser("subs", help="字幕：带人声的曲子出逐句时间轴（要 --yes）",
                       allow_abbrev=False)
    add_wait(p)
    p.add_argument("--task-id", dest="task_id", help="生成音乐 / 延长音乐返回的 task_id")
    p.add_argument("--audio-id", dest="audio_id", help="那首曲子的 audio_id")
    p.add_argument("--srt-out", dest="srt_out", default=None,
                   help="顺手把逐句时间轴写成 SRT（chapters 可以直接吃）")
    p.set_defaults(fn=cmd_subs)

    p = sub.add_parser("task", help="查任务状态 / 补取结果（免费，0 点）", allow_abbrev=False)
    p.add_argument("--task-id", dest="task_id", help="task_id")
    p.add_argument("--out", default=None, help="把音频下载到这个目录（可选）")
    p.add_argument("--prefix", default="podcast", help="下载文件名前缀")
    p.set_defaults(fn=cmd_task)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以（default=SUPPRESS，不覆盖父级的值）
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            if _n in _sp._option_string_actions:
                continue
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE_NO_KEY = ("cmd_cost", "cmd_chapters", "cmd_log")


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
        a.host = host
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in FREE_NO_KEY:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
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
