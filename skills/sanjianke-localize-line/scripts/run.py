#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 多语言出海（一条中文视频，出 12 语版本）

一条中文视频：转写 -> 翻译 -> 外语配音 -> 外语字幕，四步一条命令跑完。
走 api.a7w.cn，一个 Key，零依赖。

## 四条线路（端点全部实测定死）

  转写  POST /api/v1/apps/voice_tts/stt
        本地文件 multipart（字段名 audio）或 audio_url；ignore_timestamps=false 才有字级时间轴。
  翻译  POST /api/v1/chat/completions        （OpenAI 兼容，按 token 计费）
  配音  POST /api/v1/apps/media_services_33/elevenlabs_text_to_speech_multilingual_v2
        必填 text（<=5000 字）、voice（67 个音色 ID 的枚举，不是名字）。
  字幕  本地纯 Python：字级时间轴合并成行 -> SRT / VTT，0 点、0 网络。

## 价格口径（1 元 = 100 点，取自 GET /api/v1/pricing 与实测流水）

  voice_tts/*          markupPercent=200 -> 对外 = 上游真实点数 x 3
                       stt 上游 40 点 -> 我方 120 点/次；预扣 150 点/次（失败全额退）
  media_services_33/*  没有专属规则，落通配「上游 x 2、单笔保底 50」-> 实测每次预扣 60 点
  chat/completions     平台不公布点数，本包只报 token，不编金额

## 探针禁区（2026-11-07 的教训）

  本包 doctor 一个 POST 都不发，只打 5 条只读 GET（/user/balance、/apps、/pricing、
  /models、/tasks/<假id>），所以 0 次冻结、0 点。
  一、不打 GET /api/v1/apps/<app>：命中通配计价，sync 即时扣、不退。
  二、打应用层 submit 缺必填：会先 reserve_sync 冻 60/150 点再退，净 0 但动钱包。
  三、连 GET /api/v1/apps/voice_tts/list_voices 也会 reserve 150 点，本包不碰。
  四、任务轮询一律 GET /api/v1/tasks/<task_id>（免费）；应用层 /query 一次就是一次的钱。

## 子命令

  catalog    4 条线路 + 12 种语言 + 67 个音色 + 价目（0 请求、免费）
  cost       先算钱：1/5/10/20/30/60 分钟价目（免费）
  doctor     自检 Key / 应用 / 价目 / 任务查询 / 模型目录（免费，5 条只读 GET）
  transcribe 原视频 -> 台词稿 + 字级时间轴 + 源语言 SRT（120 点/次）
  translate  台词稿 -> 目标语言台词稿（chat/completions，按 token）
  voice      目标语言台词稿 -> 外语配音（60 点/条起）
  subtitle   多语言字幕：SRT / VTT（本地，0 点）
  run        一条命令跑完整链路 + 多版本输出（转写 + 配音的点数先在本地算清）
  task       查任务（GET /api/v1/tasks/<id>，免费）
  log        本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py cost --minutes 10
  python3 scripts/run.py run --input 第03集.mp4 --to en --voice "Brian" --outdir ./出片 --yes
  python3 scripts/run.py transcribe --input 第03集.mp4 --outdir ./出片 --yes
  python3 scripts/run.py voice --in ./出片/localize-en.json --voice nPczCjzI2devNBz1zQrb --yes
  python3 scripts/run.py subtitle --in ./出片/localize-en.json --to en --outdir ./出片

Key：--key -> 环境变量 A7W_API_KEY -> ~/.a7w/config.json。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**
"""
import argparse
import io
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


# ── GBK 编码兜底（Windows 上 stdout 被重定向时用 cp936，编不出的字符会直接崩）──
# 先加 errors='replace'，再把 cp936 编不出的打勾 / 打叉 / 人民币符号从输出里换掉
# （本文件只用 √ 与 ×，金额一律写「元」）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

APP_STT = "voice_tts"
APP_TTS = "media_services_33"
STT_PATH = API_PREFIX + "/apps/voice_tts/stt"
VOICE_PATH = (API_PREFIX + "/apps/media_services_33/"
              "elevenlabs_text_to_speech_multilingual_v2")
CHAT_PATH = API_PREFIX + "/chat/completions"

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "localize-line-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1
POINTS_PER_YUAN = 100

UA = "sanjianke-localize-line/%s" % VERSION

DEFAULT_BUDGET = 600          # 点
DEFAULT_MODEL = "deepseek-chat"

# ── 价格（实测锚点，单位：点）────────────────────────────────────────────────
POINTS_STT = 120              # voice_tts/stt：上游 40 x 3
RESERVE_STT = 150             # voice_tts/* 预扣 150 点/次（失败全额退）
MAX_VOICE_CHARS = 5000        # elevenlabs 的 text maxLength
POINTS_VOICE_MIN = 60         # media_services_33 通配：上游 x 2、保底 50；实测预扣 60
RESERVE_VOICE = 60
CHARS_PER_MIN = 240           # 中文口播约 240 字/分钟（4 字/秒）
DEFAULT_RATIO = 3.0           # 中 -> 拉丁字母语言的字数膨胀系数（估预算用，宁多不少）

TERMINAL_OK = ("completed", "success", "succeeded", "done")
TERMINAL_BAD = ("failed", "error", "cancelled", "canceled", "timeout", "expired")

# ── 12 种目标语言（ElevenLabs m2 靠文本自身语言自动识别，这里只用于翻译与出片标注）──
LANGS = [
    ("en", "英语"), ("ja", "日语"), ("ko", "韩语"), ("es", "西班牙语"),
    ("pt", "葡萄牙语"), ("fr", "法语"), ("de", "德语"), ("ru", "俄语"),
    ("ar", "阿拉伯语"), ("th", "泰语"), ("vi", "越南语"), ("id", "印尼语"),
]
LANG_CODE = [c for c, _ in LANGS]
LANG_NAME = dict(LANGS)

# ── 67 个音色（网关 params_schema 的 voice.enum 原文 + 描述里的「名字 - 特点」）──
VOICES = [
    ("EkK5I93UQWFDigLMpZcX", "James", "沙哑、引人入胜、大胆"),
    ("Z3R5wn05IrDiVCyEkUrK", "Arabella", "神秘、富有情感"),
    ("NNl6r8mD7vthiJatiJt1", "Bradford", "富有表现力、口齿清晰"),
    ("YOq2y2Up4RgXP2HyXjE5", "Xavier", "霸气、金属感播音员"),
    ("B8gJV1IhpuegLxdpXFOE", "Kuon", "开朗、清晰、稳定"),
    ("2zRM7PkgwBPiau2jvVXc", "Monika Sogam", "低沉、自然"),
    ("1SM7GgM6IMuvQlz2BwM3", "Mark", "随意、放松、轻快"),
    ("5l5f8iK3YPeGga21rQIX", "Adeline", "女性化、对话式"),
    ("scOwDtmlUjD3prqpp97I", "Sam", "客服代理"),
    ("NOpBlnGInO9m6vDvFkFC", "Spuds Oxley", "睿智、平易近人"),
    ("BZgkqPqms7Kj9ulSkVzn", "Eve", "真实、充满活力、快乐"),
    ("wo6udizrrtpIxWGp2qJk", "Northern Terry", "北方口音"),
    ("gU0LNdkMOQCOrPrwtbee", "British Football Announcer", "英国足球解说员"),
    ("DGzg6RaUqxGRTHSBjfgF", "Brock", "威严、大声的军士"),
    ("x70vRnQBMBu4FAYhjJbO", "Nathan", "虚拟电台主持人"),
    ("Sm1seazb4gs7RSlUVw7c", "Anika", "活泼、友好、引人入胜"),
    ("P1bg08DkjqiVEzOn76yG", "Viraj", "丰富、柔和"),
    ("qDuRKMlYmrm8trt5QyBn", "Taksh", "平静、严肃、流畅"),
    ("qXpMhyvQqiRxWQs4qSSB", "Horatius", "充满活力的角色配音"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam", "充满活力、社交媒体创作者"),
    ("N2lVS1w4EtoT3dr4eOWO", "Callum", "沙哑的骗子"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura", "热情、古怪的态度"),
    ("kPzsL2i3teMYv0FxEYQ6", "Brittney", "社交媒体语音：有趣、年轻、信息丰富"),
    ("UgBBYS2sOqTuMpoF3BR0", "Mark 2", "自然对话"),
    ("hpp4J3VqNfWAUOO0d1Us", "Bella", "专业、明亮、温暖"),
    ("nPczCjzI2devNBz1zQrb", "Brian", "低沉、共鸣、令人安慰"),
    ("uYXf8XasLslADfZ2MB4u", "Hope", "活泼、八卦、少女感"),
    ("gs0tAILXbY5DNrJrsM6F", "Jeff", "优雅、共鸣、强劲"),
    ("DTKMou8ccj1ZaWGBiotd", "Jamahal", "年轻、充满活力、自然"),
    ("vBKc2FfBKJfcZNyEt1n6", "Finn", "年轻、热切、充满活力"),
    ("DYkrAHD8iwork3YSUBbs", "Tom", "对话与书籍"),
    ("56AoDkrOh6qfVPDXZ7Pt", "Cassidy", "清脆、直接、清晰"),
    ("eR40ATw9ArzDf9h3v7t7", "Addison 2.0", "澳大利亚有声书与播客"),
    ("g6xIsTj2HwM6VR4iXFCw", "Jessica Anne Bogart", "健谈、友好"),
    ("lcMyyd2HUfFzxdCaC4Ta", "Lucy", "清新、随意"),
    ("6aDn1KB0hjpdcocrUkmq", "Tiffany", "自然、热情"),
    ("Sq93GQT4X1lKDXsQcixO", "Felix", "温暖、积极、现代 RP"),
    ("flHkNRp1BlvT73UL6gyz", "Jessica Anne Bogart 2", "雄辩的反派"),
    ("9yzdeviXkFddZ4Oz8Mok", "Lutz", "咯咯笑、欢快"),
    ("pPdl9cQBQq4p6mRkZy2Z", "Emma", "可爱、积极向上"),
    ("zYcjlYFOd3taleS0gkk3", "Edward", "大声、自信、自负"),
    ("nzeAacJi50IvxcyDnMXa", "Marshal", "友好、幽默的教授"),
    ("ruirxsoakN0GWmGNIo04", "John Morgan", "粗犷、坚韧的牛仔"),
    ("TC0Zp7WVFzhA8zpTlRqV", "Aria", "性感反派"),
    ("ljo9gAlSqKOvF6D8sOsX", "Viking Bjorn", "史诗中世纪掠夺者"),
    ("PPzYpIqttlTYA83688JI", "Pirate Marshal", "海盗元帅"),
    ("8JVbfL6oEdmuxKn5DK2C", "Johnny Kid", "严肃、平静的旁白"),
    ("iCrDUkL56s3C8sCRl7wb", "Hope 2", "诗意、浪漫、迷人"),
    ("wJqPPQ618aTW29mptyoc", "Ana Rita", "流畅、富有表现力、明亮"),
    ("EiNlNiXeDU1pqqOPrYMO", "John Doe", "低沉"),
    ("4YYIPFl9wE5c4L2eu2Gb", "Burt Reynolds", "低沉、流畅、清晰"),
    ("6F5Zhi321D3Oq7v1oNT4", "Hank", "低沉、引人入胜的旁白"),
    ("YXpFCvM1S3JbWEJhoskW", "Wyatt", "睿智乡村牛仔"),
    ("LG95yZDEHg6fCZdQjLqj", "Phil", "爆发力、热情播音员"),
    ("CeNX9CMwmxDxUF5Q2Inm", "Johnny Dynamite", "复古电台 DJ"),
    ("aD6riP1btT197c6dACmy", "Rachel M", "专业英国电台主持人"),
    ("mtrellq69YZsNwzUSyXh", "Rex Thunder", "低沉强硬"),
    ("dHd5gvgSOzSfduK4CvEg", "Ed", "深夜播音员"),
    ("eVItLK1UvXctxuaRV2Oq", "Jean", "迷人、俏皮的蛇蝎美人"),
    ("esy0r39YPLQjOczyOib8", "Britney", "冷静、算计的反派"),
    ("Tsns2HvNFKfGiNjllgqo", "Sven", "情感丰富、友善"),
    ("1U02n4nD6AdIZ9CjF053", "Viraj 2", "流畅、温柔"),
    ("AeRdCCKzvd23BpJoofzx", "Nathaniel", "引人入胜、英式、平静"),
    ("LruHrtVF6PSyGItzMNHS", "Benjamin", "低沉、温暖、平静"),
    ("1wGbFxmAM3Fgw63G1zZJ", "Allison", "平静、舒缓、冥想"),
    ("hqfrgApggtO1785R4Fsn", "Theodore HQ", "宁静、沉稳"),
    ("MJ0RnG71ty4LH3dvNfSd", "Leon", "舒缓、沉稳"),
]
VOICE_IDS = [v[0] for v in VOICES]
VOICE_NAME = {v[0]: v[1] for v in VOICES}
DEFAULT_VOICE = "nPczCjzI2devNBz1zQrb"          # Brian：低沉、共鸣、纪录片旁白
RECOMMENDED = [
    ("nPczCjzI2devNBz1zQrb", "Brian", "纪录片 / 解说旁白，低沉有共鸣"),
    ("hpp4J3VqNfWAUOO0d1Us", "Bella", "品牌口播，专业明亮温暖"),
    ("eR40ATw9ArzDf9h3v7t7", "Addison 2.0", "有声书与播客，澳音自然"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam", "短视频口播，活力足"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura", "生活类内容，热情有个性"),
    ("1SM7GgM6IMuvQlz2BwM3", "Mark", "轻快随意，适合 Vlog"),
]

# 字幕断行：句末标点优先，其次停顿与长度
PUNCT_END = "。！？!?…"
PUNCT_SOFT = "，,、；;：:"
PUNCT_HINT = PUNCT_END + PUNCT_SOFT


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def dig(obj, *keys):
    cur = obj
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
        if cur is None:
            return None
    return cur


def fmt_pts(n):
    return "{:,}".format(int(round(n)))


def load_conf(explicit_key=None, explicit_host=None):
    key = (explicit_key or "").strip() or None
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


# ───────────────────────── HTTP ─────────────────────────
def http_json(method, url, key, body=None, timeout=120, retries=0):
    """发一次请求。

    **POST 默认不重试**：一次提交就是一次扣费，重试等于再扣一次。
    只读 GET 才退避重试（网关会重置空闲连接，实测 WinError 10054）。
    """
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    last = None
    for attempt in range(max(1, retries + 1)):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries:
                last = e
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)),
                       EXIT_CALL)
        except Exception as e:                                   # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=900):
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in (fields or {}).items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    for name, path in files or []:
        fn = os.path.basename(path)
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                   "Content-Type: %s\r\n\r\n"
                   % (boundary, name, fn, ctype)).encode("utf-8"))
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
        return "网关回了 HTML（HTTP %s），这条路径不存在" % st
    return txt.replace("\n", " ")[:300]


def app_data(st, txt, url):
    """生成应用的统一信封：HTTP 200 且 code in (1,200) 才算成功（校验失败也是 200 + code 0）。"""
    d = jloads(txt)
    if st >= 400 or not isinstance(d, dict):
        raise Fail("call", "调用失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    code = d.get("code")
    if code not in (1, 200, None):
        raise Fail("call", "上游拒绝（%s）：%s"
                   % (url.rsplit("/", 1)[-1], d.get("msg") or err_text(st, txt)),
                   EXIT_CALL)
    data = d.get("data")
    return (data if isinstance(data, dict) else {}), d


def poll_task(a, key, host, task_id):
    """轮询只用 GET /api/v1/tasks/<id>（免费）。应用层 /query 一次就是一次的钱。"""
    deadline = time.time() + max(30, a.wait)
    last, ticks = None, 0
    while time.time() < deadline:
        time.sleep(max(1, a.every))
        ticks += 1
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/"
                            + urllib.parse.quote(task_id), key, None, 60, retries=2)
        d = jloads(txt) or {}
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        status = str(data.get("status") or d.get("status") or "").lower()
        if status != last:
            say("  状态：%s" % (status or "?"))
            last = status
        if status in TERMINAL_OK:
            return data
        if status in TERMINAL_BAD:
            err = data.get("error") or d.get("error") or status
            raise Fail("call", "任务未成功（%s）：%s" % (task_id, err), EXIT_CALL)
    raise Fail("call", "等了 %d 秒还没完成。任务没丢——用 `task --task-id %s` 接着取，"
                       "**不要重新提交**（会再扣一次）。" % (a.wait, task_id), EXIT_CALL)


def find_url(node, depth=0):
    """在返回里找音频地址（上游键名偶有差异，逐层兜底）。"""
    if depth > 8:
        return None
    if isinstance(node, dict):
        for k in ("audio_url", "audioUrl", "audio", "url", "file_url", "download_url"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in node.values():
            got = find_url(v, depth + 1)
            if got:
                return got
    elif isinstance(node, list):
        for v in node:
            got = find_url(v, depth + 1)
            if got:
                return got
    return None


def find_timeline(node, out, depth=0):
    """逐词 / 逐字时间轴：抓带 start + end + 文本键的条目。"""
    if depth > 8:
        return
    if isinstance(node, dict):
        st, en = node.get("start"), node.get("end")
        if isinstance(st, (int, float)) and isinstance(en, (int, float)) and en >= st:
            tx = ""
            for k in ("text", "word", "character", "char", "value"):
                v = node.get(k)
                if isinstance(v, str) and v:
                    tx = v
                    break
            if tx:
                out.append({"start": float(st), "end": float(en), "text": tx})
                return
        for v in node.values():
            find_timeline(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            find_timeline(v, out, depth + 1)


# ───────────────────────── 时间轴 / 字幕 ─────────────────────────
def fmt_ts(sec, comma=True):
    ms = int(round(float(sec or 0) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d%s%03d" % (h, m, s, "," if comma else ".", ms)


def restore_punct(segments, full_text):
    """字级时间轴不带标点，标点只在全文里；两边对不齐就原样返回（宁可不补，也不补错位）。"""
    segs = []
    for seg in segments:
        st = dig(seg, "start") if dig(seg, "start") is not None else dig(seg, "start_time")
        en = dig(seg, "end") if dig(seg, "end") is not None else dig(seg, "end_time")
        tx = (dig(seg, "text") or dig(seg, "word") or dig(seg, "character") or "").strip()
        if tx:
            segs.append({"start": float(st or 0), "end": float(en or 0), "text": tx})
    plain = "".join(ch for ch in (full_text or "") if not ch.isspace())
    if not segs or not plain:
        return segs
    joined = "".join(s["text"] for s in segs)
    if not joined:
        return segs
    out = [dict(s) for s in segs]
    i = 0
    for ch in plain:
        if i < len(joined) and ch == joined[i]:
            i += 1
            continue
        if i == 0 or ch not in PUNCT_HINT:
            return segs
        out[i - 1]["text"] += ch
    if i != len(joined):
        return segs
    return out


def merge_segments(segments, gap=0.7, max_chars=18):
    """字级时间轴 -> 可读字幕行：句末断行、停顿断行、超长断行。"""
    out, cur = [], None
    for seg in segments:
        st, en, tx = float(seg.get("start") or 0), float(seg.get("end") or 0), \
            (seg.get("text") or "").strip()
        if not tx:
            continue
        if cur is None:
            cur = [st, en, tx]
            continue
        if (cur[2][-1] in PUNCT_END or st - cur[1] > gap
                or len(cur[2]) + len(tx) > max_chars):
            out.append(cur)
            cur = [st, en, tx]
        else:
            cur[1], cur[2] = en, cur[2] + tx
        if cur[2][-1] in PUNCT_END or (cur[2][-1] in PUNCT_SOFT and len(cur[2]) >= 8):
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [{"start": s, "end": e, "text": t} for s, e, t in out]


def to_srt(lines):
    rows = []
    for i, seg in enumerate(lines, 1):
        rows += [str(i), "%s --> %s" % (fmt_ts(seg["start"]), fmt_ts(seg["end"])),
                 seg.get("text") or "", ""]
    return "\n".join(rows)


def to_vtt(lines):
    rows = ["WEBVTT", ""]
    for i, seg in enumerate(lines, 1):
        rows += [str(i), "%s --> %s" % (fmt_ts(seg["start"], False),
                                        fmt_ts(seg["end"], False)),
                 seg.get("text") or "", ""]
    return "\n".join(rows)


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return path


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as x:
        raw = x.read()
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    io.open(path, "wb").write(raw)
    return path, len(raw)


# ───────────────────────── 价格 ─────────────────────────
def chunks_for(chars):
    return max(1, (int(chars) + MAX_VOICE_CHARS - 1) // MAX_VOICE_CHARS)


def voice_points(chars):
    return max(1, chunks_for(chars)) * POINTS_VOICE_MIN


def est_target_chars(src_chars, ratio):
    return int(round(int(src_chars) * float(ratio)))


def tokens_est(chars_in, chars_out):
    """字符 -> token 标定（同族实测值，是估算不是账单）：入 1 token 约 1.61 字、出 1 字约 1.11 token。"""
    return {"in": int(round(chars_in / 1.61)), "out": int(round(chars_out * 1.11))}


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


# ───────────────────────── 两道闸门 ─────────────────────────
def gate(a, points, what, extra=""):
    """预算 -> 确认。两道都在发请求之前拦。"""
    if points > a.budget:
        raise Fail("budget",
                   "%s预计 %d 点，超过 --budget %d 点（1 元 = 100 点）。"
                   "一个请求都没发。" % (what, points, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        if points <= 0:
            raise Fail("confirm",
                       "%s会真实调用文本模型（按 token 计费，平台不公布点数）。"
                       "确认请加 --yes。" % what, EXIT_CONFIRM)
        raise Fail("confirm",
                   "%s会真实计费：预计 %d 点（%.2f 元）%s。确认请加 --yes。"
                   % (what, points, points / float(POINTS_PER_YUAN), extra),
                   EXIT_CONFIRM)
    return points


# ───────────────────────── 参数校验 ─────────────────────────
def need(a, *names):
    miss = []
    for n in names:
        val = getattr(a, n.replace("-", "_"), None)
        if val is None or (isinstance(val, str) and not val.strip()):
            miss.append("--" + n)
    if miss:
        raise Fail("usage", "缺必填参数：%s" % " ".join(miss), EXIT_USAGE)


def check_lang(code):
    if code not in LANG_NAME:
        raise Fail("usage", "--to 只能是：%s" % " / ".join(LANG_CODE), EXIT_USAGE)
    return code


def resolve_voice(val):
    """voice 是 67 个 ID 的枚举。名字只做本地解析（精确且唯一才认），不让上游替你猜。"""
    val = (val or "").strip()
    if val in VOICE_IDS:
        return val
    hits = [v[0] for v in VOICES if v[1].lower() == val.lower()]
    if len(hits) == 1:
        say("  --voice %s -> %s（%s）" % (val, hits[0], VOICE_NAME[hits[0]]))
        return hits[0]
    more = [v for v in VOICES if val and val.lower() in v[1].lower()][:3]
    tip = ""
    if more:
        tip = "；相近的有：" + "、".join("%s=%s" % (v[1], v[0]) for v in more)
    raise Fail("usage",
               "--voice 要音色 ID（67 个枚举之一），不是任意名字。%s%s\n"
               "  全部音色：python3 scripts/run.py catalog --voices" % (val, tip),
               EXIT_USAGE)


def check_range(name, val, lo, hi):
    """范围校验（本地拦，别把不合规参数交给上游）。"""
    if val is None:
        return
    if val < lo or val > hi:
        raise Fail("usage", "%s 必须在 %s-%s 之间（当前 %s）" % (name, lo, hi, val),
                   EXIT_USAGE)


def check_voice_params(a):
    """m2 的四个数值参数都有上下界，本地先拦。"""
    check_range("--speed", getattr(a, "speed", None), 0.7, 1.2)
    check_range("--style", getattr(a, "style", None), 0, 1)
    check_range("--stability", getattr(a, "stability", None), 0, 1)
    check_range("--similarity", getattr(a, "similarity", None), 0, 1)


# ───────────────────────── 线路 1：转写 ─────────────────────────
def do_transcribe(a, key, host):
    """POST /api/v1/apps/voice_tts/stt（120 点/次，预扣 150）。"""
    fields = {"ignore_timestamps": "false"}
    if getattr(a, "language", None):
        fields["language"] = a.language
    url = host + STT_PATH
    if a.input:
        if not os.path.isfile(a.input):
            raise Fail("usage", "文件不存在：%s" % a.input, EXIT_USAGE)
        size = os.path.getsize(a.input)
        say("正在上传并转写 %s（%d 字节）…" % (os.path.basename(a.input), size))
        t0 = time.time()
        st, txt = http_multipart(url, key, fields, [("audio", a.input)],
                                 timeout=getattr(a, "timeout", 900))
    else:
        size = 0
        body = dict(fields, audio_url=a.audio_url)
        say("正在转写（audio_url）…")
        t0 = time.time()
        st, txt = http_json("POST", url, key, body, timeout=getattr(a, "timeout", 300))
    dt = time.time() - t0
    data, _ = app_data(st, txt, url)
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    text = (result.get("text") or data.get("text") or "").strip()
    segments = result.get("segments") or data.get("segments") or []
    if not text or not segments:
        raise Fail("call", "转写没返回可用时间轴（text=%d 字、segments=%d 条）。原始返回：%s"
                   % (len(text), len(segments),
                      json.dumps(data, ensure_ascii=False)[:300]), EXIT_CALL)
    segs = restore_punct(segments, text)
    lines = merge_segments(segs, gap=getattr(a, "gap", 0.7),
                           max_chars=getattr(a, "max_chars", 18))
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return {
        "text": text,
        "language": result.get("language_code") or result.get("language")
        or getattr(a, "language", None) or "?",
        "duration": result.get("duration") or data.get("duration"),
        "segments": lines,
        "raw_char_stamps": len(segments),
        "points": usage.get("points_cost") if usage.get("points_cost") is not None
        else usage.get("actual_points"),
        "elapsed": round(dt, 1),
        "bytes": size,
    }


# ───────────────────────── 线路 2：翻译 ─────────────────────────
def parse_json_array(s):
    """从模型输出里切第一个完整的 JSON 数组（括号配平，字符串内的括号不算）。"""
    if not s:
        return None
    start = s.find("[")
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        val = json.loads(s[start:i + 1])
                    except ValueError:
                        val = None
                    if isinstance(val, list):
                        return val
                    break
        start = s.find("[", start + 1)
    return None


def do_translate(a, key, host, lines, to):
    """POST /api/v1/chat/completions（OpenAI 兼容；按 token 计费，平台不公布点数）。"""
    n = len(lines)
    src = json.dumps([x.get("text") or "" for x in lines], ensure_ascii=False)
    prompt = (
        "你是影视本地化字幕翻译。把下面这个 JSON 数组里的 %d 条中文字幕逐条翻成%s。\n"
        "规则：\n"
        "1) 只输出一个 JSON 数组，长度必须正好 %d，顺序与输入完全一致；\n"
        "2) 每条是一个字符串，不带编号、不带解释、不带外层说明；\n"
        "3) 人名、品牌名、数字、单位原样保留；口语要像母语者说话，不要机器直译；\n"
        "4) 每条尽量短——它要压在屏幕上读。\n\n"
        "%s" % (n, LANG_NAME.get(to, to), n, src))
    body = {"model": getattr(a, "model", DEFAULT_MODEL),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": int(getattr(a, "max_tokens", 4096))}
    url = host + CHAT_PATH
    say("正在翻译 %d 条 -> %s（%s）…" % (n, to, body["model"]))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=int(getattr(a, "timeout", 180)),
                        retries=1)
    dt = time.time() - t0
    d = jloads(txt)
    if st != 200 or not isinstance(d, dict) or not d.get("choices"):
        raise Fail("call", "翻译失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    content = ((d["choices"][0] or {}).get("message") or {}).get("content") or ""
    arr = parse_json_array(content)
    out = []
    if isinstance(arr, list) and len(arr) == n:
        out = [str(x if not isinstance(x, (dict, list)) else json.dumps(x, ensure_ascii=False))
               for x in arr]
    else:
        # 兜底：一行一条（模型没给数组时），数量必须对得上，否则宁可不猜
        cand = [re.sub(r"^\s*(\d+[.、)]|[-*])\s*", "", x).strip()
                for x in content.splitlines() if x.strip()]
        cand = [x for x in cand if x]
        if len(cand) != n:
            raise Fail("call",
                       "翻译返回的条数对不上（要 %d 条，解析到 %d 条）。原文片段：%s"
                       % (n, len(cand), content[:200]), EXIT_CALL)
        out = cand
    usage = d.get("usage") if isinstance(d.get("usage"), dict) else {}
    return {"lines": out, "usage": usage, "model": body["model"],
            "elapsed": round(dt, 1), "charIn": len("".join(
                x.get("text") or "" for x in lines)),
            "charOut": len("".join(out))}


# ───────────────────────── 线路 3：外语配音 ─────────────────────────
def voice_body(a, text, voice_id):
    body = {"text": text, "voice": voice_id}
    for k, v in (("speed", getattr(a, "speed", None)),
                 ("style", getattr(a, "style", None)),
                 ("stability", getattr(a, "stability", None)),
                 ("similarity_boost", getattr(a, "similarity", None))):
        if v is not None:
            body[k] = float(v)
    if getattr(a, "timestamps", False):
        body["timestamps"] = True
    for k, v in (("previous_text", getattr(a, "prev_text", None)),
                 ("next_text", getattr(a, "next_text", None))):
        if v:
            body[k] = v
    return body


def split_chunks(lines, limit=MAX_VOICE_CHARS):
    """按行切块，每块 <= limit 字；单行超长再硬切。"""
    chunks, cur = [], ""
    for ln in lines:
        tx = (ln.get("text") if isinstance(ln, dict) else str(ln)) or ""
        tx = tx.strip()
        if not tx:
            continue
        while len(tx) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(tx[:limit])
            tx = tx[limit:]
        if cur and len(cur) + 1 + len(tx) > limit:
            chunks.append(cur)
            cur = tx
        else:
            cur = (cur + "\n" + tx) if cur else tx
    if cur:
        chunks.append(cur)
    return chunks


def do_voice(a, key, host, lines, voice_id, outdir=None, prefix=None):
    """POST elevenlabs multilingual v2（60 点/条起，预扣 60）。"""
    chunks = split_chunks(lines)
    url = host + VOICE_PATH
    audios = []
    t_all = time.time()
    for i, text in enumerate(chunks, 1):
        body = voice_body(a, text, voice_id)
        say("提交配音 %d/%d（%d 字）…" % (i, len(chunks), len(text)))
        st, txt = http_json("POST", url, key, body,
                            timeout=int(getattr(a, "timeout", 300)), retries=0)
        data, _ = app_data(st, txt, url)
        tid = data.get("task_id") or data.get("taskId")
        usage = {}
        if tid:
            say("  task_id=%s（轮询走 GET /api/v1/tasks/<id>，免费）" % tid)
            task = poll_task(a, key, host, tid)
            result = task.get("result") if isinstance(task.get("result"), dict) else {}
            usage = task.get("usage") if isinstance(task.get("usage"), dict) else {}
            if not result:
                result = task
        else:
            result = data
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        audio = find_url(result)
        stamps = []
        find_timeline(result, stamps)
        if stamps and not isinstance(stamps[0].get("text"), str):
            stamps = []
        item = {"chunk": i, "chars": len(text), "taskId": tid,
                "audioUrl": audio, "timingsCount": len(stamps),
                "points": usage.get("points_cost") if usage.get("points_cost") is not None
                else usage.get("actual_points")}
        if audio and outdir:
            p = os.path.join(outdir, "%s-dub-%02d%s" % (
                prefix or "localize", i,
                os.path.splitext(urllib.parse.urlsplit(audio).path)[1] or ".mp3"))
            try:
                p, n = download(audio, p)
                item.update({"file": p, "bytes": n})
            except Exception as e:                               # noqa: BLE001
                say("  下载失败（链接还能用）：%s" % e)
        if outdir and stamps:
            p = os.path.join(outdir, "%s-dub-%02d.timestamps.json" % (prefix or "localize", i))
            write_text(p, json.dumps({"chunk": i, "chars": len(text),
                                      "timeline": stamps}, ensure_ascii=False, indent=1))
            item["timestampsFile"] = p
        audios.append(item)
        if not audio:
            say("  这条没解析到音频地址，原始返回：%s"
                % json.dumps(result, ensure_ascii=False)[:240])
    return {"audios": audios, "chunks": len(chunks),
            "elapsed": round(time.time() - t_all, 1),
            "voice": voice_id, "voiceName": VOICE_NAME.get(voice_id, "")}


# ───────────────────────── 套餐：一条命令跑完 ─────────────────────────
def _read_lines(path):
    raw = io.open(path, encoding="utf-8").read().replace("\ufeff", "")
    return [x.strip() for x in raw.splitlines() if x.strip()]


def cmd_run(a, key, host):
    need(a, "input", "to")
    check_lang(a.to)
    if not os.path.isfile(a.input):
        raise Fail("usage", "文件不存在：%s" % a.input, EXIT_USAGE)
    voice_id = resolve_voice(a.voice or DEFAULT_VOICE)
    check_voice_params(a)
    ratio = a.ratio
    if a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "台词稿不存在：%s" % a.script, EXIT_USAGE)
        guess_chars = len("".join(_read_lines(a.script)))
        basis = "按自带台词稿 %d 字" % guess_chars
    else:
        guess_chars = int(a.chars) if a.chars else int(round(a.minutes * CHARS_PER_MIN))
        guess_chars = est_target_chars(guess_chars, ratio)
        basis = "按 %d 分钟约 %d 字 x%.1f 估" % (a.minutes,
                                                int(round(a.minutes * CHARS_PER_MIN)), ratio)
    chunks = chunks_for(guess_chars)
    cost = POINTS_STT + POINTS_VOICE_MIN * max(1, chunks)
    gate(a, cost, "整条链路（转写 + 配音）",
         "；翻译走 chat/completions，另按 token 计")
    outdir = a.outdir or "."
    prefix = a.prefix or "localize"
    plan = {"steps": ["transcribe", "translate" if not a.script else "script",
                      "voice", "subtitle"],
            "estimatePoints": cost, "chunks": max(1, chunks), "ratio": ratio,
            "basis": basis, "outdir": outdir, "prefix": prefix, "to": a.to,
            "voice": voice_id}
    if a.dry_run:
        return _out(a, {"ok": True, "dryRun": True, "mode": "run", **plan},
                    "干跑（不发请求、不扣费）", [
                        "  转写：POST %s（multipart，字段名 audio）" % (host + STT_PATH),
                        "  翻译：POST %s（%s）" % (host + CHAT_PATH, a.model),
                        "  配音：POST %s" % (host + VOICE_PATH),
                        "  预估：%s -> 配音 %d 条" % (basis, max(1, chunks)),
                        "  预计：转写 %d 点 + 配音 %d 条 x %d 点 = %d 点（%.2f 元起）"
                        % (POINTS_STT, max(1, chunks), POINTS_VOICE_MIN, cost,
                           cost / float(POINTS_PER_YUAN))])

    os.makedirs(outdir, exist_ok=True)
    info = do_transcribe(a, key, host)
    src_srt = write_text(os.path.join(outdir, prefix + "-source.srt"), to_srt(info["segments"]))
    write_text(os.path.join(outdir, prefix + "-source.txt"), info["text"] + "\n")
    say("  源语言字幕：%s（%d 行）" % (src_srt, len(info["segments"])))

    if not a.script:
        proj_chunks = chunks_for(est_target_chars(len(info["text"]), ratio))
        proj = POINTS_STT + POINTS_VOICE_MIN * proj_chunks
        if proj > a.budget:
            raise Fail("budget",
                       "转写完成：源文 %d 字，目标语言按 x%.1f 估 %d 字、%d 条配音，"
                       "预计 %d 点，超过 --budget %d 点。翻译与配音都没发"
                       "（转写已完成，本次已花 %d 点）。"
                       % (len(info["text"]), ratio,
                          est_target_chars(len(info["text"]), ratio), proj_chunks,
                          proj, a.budget, POINTS_STT), EXIT_BUDGET)

    if a.script:
        tgt = _read_lines(a.script)
        if len(tgt) != len(info["segments"]):
            raise Fail("usage",
                       "台词稿有 %d 行，源字幕有 %d 行，对不上（一行对一条）。"
                       % (len(tgt), len(info["segments"])), EXIT_USAGE)
        tlines = [{"start": s["start"], "end": s["end"], "text": tx}
                  for s, tx in zip(info["segments"], tgt)]
        tr = {"lines": tgt, "usage": {}, "model": "(自带台词稿)"}
    else:
        tr = do_translate(a, key, host, info["segments"], a.to)
        tlines = [{"start": s["start"], "end": s["end"], "text": tx}
                  for s, tx in zip(info["segments"], tr["lines"])]
    tchunks = chunks_for(len("".join(tr["lines"])))
    if POINTS_STT + POINTS_VOICE_MIN * tchunks > a.budget:
        raise Fail("budget",
                   "翻译后实际要配 %d 条（%d 字），预计 %d 点，超过 --budget %d 点。"
                   "配音请求没发。" % (tchunks, len("".join(tr["lines"])),
                                      POINTS_STT + POINTS_VOICE_MIN * tchunks, a.budget),
                   EXIT_BUDGET)
    vin = do_voice(a, key, host, tlines, voice_id, outdir, prefix)
    srt = write_text(os.path.join(outdir, "%s-%s.srt" % (prefix, a.to)), to_srt(tlines))
    vtt = write_text(os.path.join(outdir, "%s-%s.vtt" % (prefix, a.to)), to_vtt(tlines))
    txt = write_text(os.path.join(outdir, "%s-%s.txt" % (prefix, a.to)),
                     "\n".join(tr["lines"]) + "\n")
    tjson = write_text(os.path.join(outdir, "%s-%s.json" % (prefix, a.to)),
                       json.dumps({"to": a.to, "source": os.path.abspath(a.input),
                                   "segments": tlines}, ensure_ascii=False, indent=1))
    manifest = {"ok": True, "mode": "run", "to": a.to, "languageName": LANG_NAME[a.to],
                "input": os.path.abspath(a.input), "voice": vin["voice"],
                "voiceName": vin["voiceName"], "duration": info["duration"],
                "sourceChars": len(info["text"]), "targetChars": len("".join(tr["lines"])),
                "lines": len(tlines), "chunks": vin["chunks"],
                "srt": srt, "vtt": vtt, "text": txt, "targetJson": tjson,
                "sourceSrt": src_srt, "dub": vin["audios"],
                "pointsFloor": POINTS_STT + POINTS_VOICE_MIN * vin["chunks"],
                "translateUsage": tr["usage"], "model": tr.get("model"),
                "by": "sanjianke-localize-line"}
    mpath = write_text(os.path.join(outdir, prefix + "-manifest.json"),
                       json.dumps(manifest, ensure_ascii=False, indent=1))
    manifest["manifest"] = mpath
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "run", "to": a.to,
                "ok": True, "lines": len(tlines), "chunks": vin["chunks"],
                "pointsFloor": manifest["pointsFloor"], "srt": srt})
    lines = [
        "完成（转写 %.1fs + 配音 %.1fs）" % (info["elapsed"], vin["elapsed"]),
        "  语言：%s（%s）  音色：%s（%s）" % (a.to, LANG_NAME[a.to], vin["voiceName"],
                                           vin["voice"]),
        "  源语言：%d 字 / %d 行" % (len(info["text"]), len(info["segments"])),
        "  目标语言：%d 字 / %d 行" % (len("".join(tr["lines"])), len(tlines)),
        "  字幕：%s" % srt,
        "  字幕：%s" % vtt,
        "  配音稿：%s" % txt,
    ]
    for it in vin["audios"]:
        if it.get("file"):
            lines.append("  配音 %02d：%s（%d 字节）" % (it["chunk"], it["file"],
                                                        it.get("bytes") or 0))
        elif it.get("audioUrl"):
            lines.append("  配音 %02d：%s" % (it["chunk"], it["audioUrl"]))
    lines += ["  清单：%s" % mpath,
              "  点数：转写 %d + 配音 %d x %d = %d 点起（%.2f 元起），以账单为准"
              % (POINTS_STT, vin["chunks"], POINTS_VOICE_MIN,
                 manifest["pointsFloor"],
                 manifest["pointsFloor"] / float(POINTS_PER_YUAN))]
    return _out(a, manifest, lines[0], lines[1:])


def _out(a, obj, headline, lines):
    """统一输出：--json 只吐一个 JSON 文档；否则人读。"""
    if a.json:
        print(json.dumps(obj, ensure_ascii=False))
        return 0
    print(headline)
    for ln in lines:
        print(ln)
    return 0 if obj.get("ok", True) else EXIT_CALL


# ───────────────────────── 免费子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    lines = [
        {"key": "transcribe", "what": "转写", "endpoint": STT_PATH,
         "price": "%d 点/次" % POINTS_STT, "unit": "per_call"},
        {"key": "translate", "what": "翻译", "endpoint": CHAT_PATH,
         "price": "按 token（平台不报点数）", "unit": "token"},
        {"key": "voice", "what": "配音", "endpoint": VOICE_PATH,
         "price": "%d 点/条起（每条 <=%d 字）" % (POINTS_VOICE_MIN, MAX_VOICE_CHARS),
         "unit": "per_request"},
        {"key": "subtitle", "what": "字幕", "endpoint": "本地纯 Python",
         "price": "0 点", "unit": "local"},
    ]
    out = {"ok": True, "lines": lines,
           "languages": [{"code": c, "name": n} for c, n in LANGS],
           "voiceCount": len(VOICES), "defaultVoice": DEFAULT_VOICE,
           "recommended": [{"id": i, "name": n, "use": u} for i, n, u in RECOMMENDED],
           "pricing": {"voiceTTS": "markupPercent=200 -> 上游 x 3; stt 120 点/次",
                       "mediaServices33": "通配 上游 x 2、保底 50；实测预扣 60",
                       "subtitle": "本地 0 点"},
           "voices": [{"id": i, "name": n, "note": d} for i, n, d in VOICES]
           if getattr(a, "voices", False) else None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 多语言出海 —— 4 条线路，12 种语言，67 个音色")
    print()
    for r in lines:
        print("  [%s] %-11s %s" % (r["what"], r["key"], r["price"]))
        print("         POST %s" % r["endpoint"] if r["endpoint"].startswith("/")
              else "         %s" % r["endpoint"])
    print()
    print("  语言：%s" % " / ".join("%s %s" % (c, n) for c, n in LANGS))
    print()
    print("  推荐音色（--voice 填 ID；也可以填名字，本地唯一匹配才认）")
    for i, n, u in RECOMMENDED:
        print("    %-22s %-16s %s" % (i, n, u))
    if getattr(a, "voices", False):
        print()
        print("  全部 %d 个音色（ID / 名字 / 特点）" % len(VOICES))
        for i, n, d in VOICES:
            print("    %s  %-26s %s" % (i, n, d))
    else:
        print()
        print("  全部 %d 个音色：python3 scripts/run.py catalog --voices" % len(VOICES))
    print()
    print("  5 分钟以内的中文视频，转写 120 + 配音 60 = 180 点（1.80 元）起；")
    print("  10 分钟约 2 条配音，240 点（2.40 元）起。字幕本地生成，0 点。")
    return 0


def cmd_cost(a, key, host):
    per_min = a.minutes if a.minutes else None
    rows = []
    minutes = [1, 5, 10, 20, 30, 60] if not per_min else [per_min]
    for m in minutes:
        chars = int(round(m * CHARS_PER_MIN))
        tgt = est_target_chars(chars, a.ratio)
        c = chunks_for(tgt)
        pts = POINTS_STT + POINTS_VOICE_MIN * c
        tk = tokens_est(chars, tgt)
        rows.append({"minutes": m, "chars": chars, "targetChars": tgt, "chunks": c,
                     "sttPoints": POINTS_STT, "voicePoints": POINTS_VOICE_MIN * c,
                     "points": pts, "yuan": round(pts / float(POINTS_PER_YUAN), 2),
                     "tokensIn": tk["in"], "tokensOut": tk["out"]})
    out = {"ok": True, "to": a.to, "ratio": a.ratio,
           "priceRule": {"stt": POINTS_STT, "voiceMin": POINTS_VOICE_MIN,
                         "chunksBasis": "每条配音 <=%d 字" % MAX_VOICE_CHARS,
                         "translate": "按 token，平台不公布点数"},
           "rows": rows, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "speechRate": "%d 字/分钟（中文口播实测区间 220-260）" % CHARS_PER_MIN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("多语言出海 · 价目（1 元 = 100 点，目标语言：%s）" % LANG_NAME.get(a.to, a.to))
    print()
    for r in rows:
        print("  %d 分钟 · 源文约 %d 字 -> 目标语言约 %d 字（%d 条配音）"
              % (r["minutes"], r["chars"], r["targetChars"], r["chunks"]))
        print("    转写 %d 点 + 配音 %d 条 x %d 点 = %d 点 = %.2f 元起"
              % (r["sttPoints"], r["chunks"], POINTS_VOICE_MIN,
                 r["points"], r["yuan"]))
    print()
    print("  · 转写 %d 点/次（voice_tts/stt 实测上游 40 点 x 3，预扣 %d 点）"
          % (POINTS_STT, RESERVE_STT))
    print("  · 配音 %d 点/条起（media_services_33 通配：上游 x 2、保底 50；实测预扣 %d 点）"
          % (POINTS_VOICE_MIN, RESERVE_VOICE))
    print("  · 配音按条算：一条 <=%d 字，目标语言字数按源文 x%.1f 估（--ratio 可改）"
          % (MAX_VOICE_CHARS, a.ratio))
    print("  · 翻译按 token（入 1 token 约 1.61 字、出 1 字约 1.11 token），不在这道点数闸门里")
    print("  · 字幕（SRT/VTT）本地生成，0 点、0 网络")
    print("  · 60 点是每条配音的保底预扣；成交价 = 上游实际点数 x 2，以账单为准")
    return 0


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + "/user/balance", key, None, 40, retries=2)
    d = jloads(txt) or {}
    avail = d.get("available_points") if d.get("available_points") is not None else d.get("points")
    checks.append(("Key 有效 + 余额接口可达", st == 200,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(avail or 0), fmt_pts(d.get("frozen") or 0))))

    st2, txt2 = http_json("GET", host + API_PREFIX + "/apps", key, None, 60, retries=2)
    d2 = jloads(txt2) or {}
    apps = d2.get("data") if isinstance(d2.get("data"), list) else []
    by = {x.get("code"): x for x in apps if isinstance(x, dict)}
    tts = by.get(APP_STT) or {}
    media = by.get(APP_TTS) or {}
    tts_codes = {x.get("code") for x in (tts.get("apis") or []) if isinstance(x, dict)}
    media_codes = {x.get("code") for x in (media.get("apis") or []) if isinstance(x, dict)}
    want_tts = {"stt", "tts_async", "list_voices"}
    want_media = {"elevenlabs_text_to_speech_multilingual_v2"}
    miss = sorted(want_tts - tts_codes) + sorted(want_media - media_codes)
    checks.append(("应用目录里 %s 与 %s 都在架" % (APP_STT, APP_TTS),
                   bool(apps) and not miss,
                   "应用 %d 个 · voice_tts %d 接口 · media_services_33 %d 接口%s"
                   % (len(apps), len(tts.get("apis") or []),
                      len(media.get("apis") or []),
                      "，缺 " + ",".join(miss) if miss else "")))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, None, 40, retries=2)
    pr = jloads(txt3) or {}
    rules = pr.get("pricing") if isinstance(pr.get("pricing"), dict) else pr
    rule_tts = rules.get("/api/v1/apps/voice_tts/*") or {}
    rule_all = rules.get("*") or {}
    ok3 = (st3 == 200 and str(rule_tts.get("markupPercent")) == "200"
           and rule_all.get("minPoints") is not None)
    checks.append(("价目表两项对得上（voice_tts x3 + 通配保底）", ok3,
                   "HTTP %s · %d 条规则 · voice_tts markupPercent=%s · 通配 minPoints=%s"
                   % (st3, len(rules), rule_tts.get("markupPercent"),
                      rule_all.get("minPoints"))))

    st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-doctor-probe",
                          key, None, 40, retries=2)
    d4 = jloads(txt4) or {}
    ok4 = st4 == 200 and d4.get("code") == 0 and "不存在" in str(d4.get("msg") or "")
    checks.append(("任务查询 GET /tasks/<id> 在（假 id 返回「任务不存在」）", ok4,
                   "HTTP %s %s" % (st4, (d4.get("msg") or "")[:40])))

    st5, txt5 = http_json("GET", host + API_PREFIX + "/models", key, None, 60, retries=2)
    d5 = jloads(txt5) or {}
    lst5 = d5.get("data") if isinstance(d5.get("data"), list) else []
    checks.append(("文本模型目录可达（翻译线路用）", st5 == 200 and d5.get("code") in (1, 200, None),
                   "HTTP %s · 模型 %d 个" % (st5, len(lst5))))

    out = {"ok": all(c[1] for c in checks), "version": VERSION,
           "endpoints": {"transcribe": host + STT_PATH, "translate": host + CHAT_PATH,
                         "voice": host + VOICE_PATH, "poll": host + API_PREFIX + "/tasks/<id>"},
           "postRequests": 0, "reservedPoints": 0,
           "checks": [{"name": n, "ok": o, "detail": dt} for n, o, dt in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（只打 5 条只读 GET：余额 / 应用 / 价目 / 任务 / 模型）")
    print()
    for n, o, dt in checks:
        print("  %s %-44s %s" % ("√" if o else "×", n, dt))
    print()
    print("  POST 0 次 · 冻结 0 点 · 一个应用层提交都没发（缺必填也会先冻 60/150 点再退）")
    print("  轮询只走 GET /api/v1/tasks/<id>（免费）；应用层 /query 一次就是一次的钱")
    print("  线上：转写 %d 点/次 · 配音 %d 点/条起 · 字幕 0 点"
          % (POINTS_STT, POINTS_VOICE_MIN))
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 单步子命令 ─────────────────────────
def cmd_transcribe(a, key, host):
    if not a.input and not a.audio_url:
        raise Fail("usage", "给 --input 本地视频/音频，或 --audio-url 公网地址", EXIT_USAGE)
    if a.input and a.audio_url:
        raise Fail("usage", "--input 与 --audio-url 二选一", EXIT_USAGE)
    cost = gate(a, POINTS_STT, "转写")
    if a.dry_run:
        body = {"endpoint": host + STT_PATH,
                "fields": {"ignore_timestamps": "false",
                           "language": a.language or "(自动检测)"},
                "file": os.path.basename(a.input) if a.input else None,
                "audio_url": a.audio_url,
                "bytes": os.path.getsize(a.input) if a.input else 0,
                "estimatedPoints": cost}
        return _out(a, {"ok": True, "dryRun": True, "mode": "transcribe", **body},
                    "干跑（不上传、不提交）",
                    ["  端点：POST %s" % (host + STT_PATH),
                     "  形式：%s" % ("multipart，字段名 audio" if a.input
                                    else "JSON，audio_url"),
                     "  参数：ignore_timestamps=false（要字级时间轴）",
                     "  预估：%d 点（%.2f 元），预扣 %d 点"
                     % (cost, cost / float(POINTS_PER_YUAN), RESERVE_STT)])
    info = do_transcribe(a, key, host)
    out = {"ok": True, "mode": "transcribe", "language": info["language"],
           "duration": info["duration"], "chars": len(info["text"]),
           "charStamps": info["raw_char_stamps"], "lines": len(info["segments"]),
           "points": info["points"], "elapsed": info["elapsed"],
           "segments": info["segments"], "text": info["text"]}
    outdir = a.outdir or "."
    prefix = a.prefix or "localize"
    os.makedirs(outdir, exist_ok=True)
    out["srt"] = write_text(os.path.join(outdir, prefix + "-source.srt"),
                            to_srt(info["segments"]))
    out["txt"] = write_text(os.path.join(outdir, prefix + "-source.txt"),
                            info["text"] + "\n")
    out["segmentsFile"] = write_text(
        os.path.join(outdir, prefix + "-source.json"),
        json.dumps({"language": info["language"], "duration": info["duration"],
                    "text": info["text"], "segments": info["segments"]},
                   ensure_ascii=False, indent=1))
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "transcribe",
                "ok": True, "lines": len(info["segments"]), "points": info["points"]})
    return _out(a, out, "转写完成（%.1fs，%d 点）" % (info["elapsed"], info["points"] or cost),
                ["  语言：%s  时长：%s 秒" % (info["language"],
                                             info["duration"] if info["duration"] is not None
                                             else "?"),
                 "  字数：%d  字级时间戳：%d 条  字幕行：%d 行"
                 % (len(info["text"]), info["raw_char_stamps"], len(info["segments"])),
                 "  字幕：%s" % out["srt"],
                 "  台词稿：%s" % out["txt"],
                 "  片段数据：%s（下一步 translate 直接吃它）" % out["segmentsFile"]])


def cmd_translate(a, key, host):
    need(a, "to")
    check_lang(a.to)
    if a.input:
        if not os.path.isfile(a.input):
            raise Fail("usage", "文件不存在：%s" % a.input, EXIT_USAGE)
        raw = json.load(io.open(a.input, encoding="utf-8"))
        segs = raw.get("segments") if isinstance(raw, dict) else raw
        if not isinstance(segs, list) or not segs:
            raise Fail("usage", "%s 里没有 segments（要 transcribe 产出的 -source.json）"
                       % a.input, EXIT_USAGE)
        lines = [{"start": float(s.get("start") or 0), "end": float(s.get("end") or 0),
                  "text": (s.get("text") or "").strip()} for s in segs
                 if isinstance(s, dict) and (s.get("text") or "").strip()]
    elif a.text_file:
        lines = [{"start": 0.0, "end": 0.0, "text": x} for x in _read_lines(a.text_file)]
    elif a.text:
        lines = [{"start": 0.0, "end": 0.0, "text": a.text}]
    else:
        raise Fail("usage", "给 --in（转写产出的 -source.json）或 --text-file / --text",
                   EXIT_USAGE)
    if not lines:
        raise Fail("usage", "没有可翻的内容", EXIT_USAGE)
    gate(a, 0, "翻译", extra="（按 token 计费，平台不公布点数）")
    if a.dry_run:
        body = {"endpoint": host + CHAT_PATH, "model": a.model,
                "messages": [{"role": "user",
                              "content": "(把 %d 条字幕翻成 %s；完整提示词见源码 do_translate)"
                                         % (len(lines), LANG_NAME[a.to])}],
                "max_tokens": a.max_tokens, "lines": len(lines)}
        return _out(a, {"ok": True, "dryRun": True, "mode": "translate", **body},
                    "干跑（不调模型）",
                    ["  端点：POST %s" % (host + CHAT_PATH),
                     "  模型：%s  条数：%d  目标语言：%s"
                     % (a.model, len(lines), LANG_NAME[a.to]),
                     "  计费：按 token（平台不公布点数），实测 187 字 4 次调用共 6871 token"])
    tr = do_translate(a, key, host, lines, a.to)
    tlines = [{"start": s["start"], "end": s["end"], "text": tx}
              for s, tx in zip(lines, tr["lines"])]
    out = {"ok": True, "mode": "translate", "to": a.to, "lines": len(tlines),
           "model": tr["model"], "elapsed": tr["elapsed"], "usage": tr["usage"],
           "charIn": tr["charIn"], "charOut": tr["charOut"], "segments": tlines}
    outdir = a.outdir or "."
    prefix = a.prefix or "localize"
    os.makedirs(outdir, exist_ok=True)
    out["txt"] = write_text(os.path.join(outdir, "%s-%s.txt" % (prefix, a.to)),
                            "\n".join(tr["lines"]) + "\n")
    out["json"] = write_text(os.path.join(outdir, "%s-%s.json" % (prefix, a.to)),
                             json.dumps({"to": a.to, "segments": tlines},
                                        ensure_ascii=False, indent=1))
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "translate",
                "to": a.to, "ok": True, "lines": len(tlines),
                "tokens": tr["usage"].get("total_tokens")})
    return _out(a, out, "翻译完成（%.1fs，%d 条）" % (tr["elapsed"], len(tlines)),
                ["  台词稿：%s" % out["txt"],
                 "  带时间轴：%s（下一步 voice 直接吃它）" % out["json"],
                 "  token：%s" % json.dumps(tr["usage"], ensure_ascii=False)])


def cmd_voice(a, key, host):
    need(a, "voice")
    voice_id = resolve_voice(a.voice)
    check_voice_params(a)
    if a.input:
        if not os.path.isfile(a.input):
            raise Fail("usage", "文件不存在：%s" % a.input, EXIT_USAGE)
        raw = json.load(io.open(a.input, encoding="utf-8"))
        segs = raw.get("segments") if isinstance(raw, dict) else raw
        lines = [{"text": (s.get("text") or "").strip()} for s in segs
                 if isinstance(s, dict) and (s.get("text") or "").strip()]
    elif a.text_file:
        lines = [{"text": x} for x in _read_lines(a.text_file)]
    elif a.text:
        lines = [{"text": a.text}]
    else:
        raise Fail("usage", "给 --in（translate 产出的 -<lang>.json）或 --text / --text-file",
                   EXIT_USAGE)
    chunks = split_chunks(lines)
    chars = len("".join(x["text"] for x in lines))
    cost = voice_points(chars)
    gate(a, cost, "配音", extra="（%d 条，每条预扣 %d 点）" % (len(chunks), RESERVE_VOICE))
    if a.dry_run:
        bodies = [voice_body(a, tx, voice_id) for tx in chunks]
        return _out(a, {"ok": True, "dryRun": True, "mode": "voice",
                        "endpoint": host + VOICE_PATH, "voice": voice_id,
                        "voiceName": VOICE_NAME.get(voice_id, ""),
                        "chunks": len(bodies), "estimatedPoints": cost,
                        "requests": bodies},
                    "干跑（不提交）",
                    ["  端点：POST %s" % (host + VOICE_PATH),
                     "  音色：%s（%s）" % (VOICE_NAME.get(voice_id, ""), voice_id),
                     "  请求：%d 条，共 %d 字（每条 <=%d 字）"
                     % (len(bodies), chars, MAX_VOICE_CHARS),
                     "  预估：%d 点（%.2f 元），每条预扣 %d 点"
                     % (cost, cost / float(POINTS_PER_YUAN), RESERVE_VOICE)] +
                    ["  请求体：%s" % json.dumps(b, ensure_ascii=False)[:180] for b in bodies])
    outdir = a.outdir or "."
    prefix = a.prefix or "localize"
    os.makedirs(outdir, exist_ok=True)
    vin = do_voice(a, key, host, lines, voice_id, outdir, prefix)
    out = {"ok": True, "mode": "voice", "voice": vin["voice"],
           "voiceName": vin["voiceName"], "chunks": vin["chunks"],
           "chars": chars, "estimatedPoints": cost,
           "elapsed": vin["elapsed"], "audios": vin["audios"]}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "voice",
                "ok": True, "voice": voice_id, "chunks": vin["chunks"],
                "pointsFloor": cost})
    lines_out = ["  音色：%s（%s）" % (vin["voiceName"], vin["voice"]),
                 "  块数：%d  字数：%d" % (vin["chunks"], chars)]
    for it in vin["audios"]:
        if it.get("file"):
            lines_out.append("  %02d：%s（%d 字节）" % (it["chunk"], it["file"],
                                                       it.get("bytes") or 0))
        elif it.get("audioUrl"):
            lines_out.append("  %02d：%s" % (it["chunk"], it["audioUrl"]))
        if it.get("timestampsFile"):
            lines_out.append("      时间轴：%s" % it["timestampsFile"])
    lines_out.append("  点数：%d 点起（%.2f 元起），以账单为准"
                     % (cost, cost / float(POINTS_PER_YUAN)))
    return _out(a, out, "配音完成（%.1fs）" % vin["elapsed"], lines_out)


def cmd_subtitle(a, key, host):
    need(a, "input")
    if not os.path.isfile(a.input):
        raise Fail("usage", "文件不存在：%s" % a.input, EXIT_USAGE)
    raw = json.load(io.open(a.input, encoding="utf-8"))
    segs = raw.get("segments") if isinstance(raw, dict) else raw
    if not isinstance(segs, list) or not segs:
        raise Fail("usage", "%s 里没有 segments" % a.input, EXIT_USAGE)
    lines = [{"start": float(s.get("start") or 0), "end": float(s.get("end") or 0),
              "text": (s.get("text") or "").strip()} for s in segs
             if isinstance(s, dict) and (s.get("text") or "").strip()]
    align = "source"
    if a.align == "dub":
        if not a.dub:
            cand = a.input.replace(".json", ".timestamps.json")
            a.dub = cand if os.path.isfile(cand) else None
        if not a.dub:
            raise Fail("usage", "--align dub 要给 --dub（voice 产出的 -dub-01.timestamps.json）",
                       EXIT_USAGE)
        if not os.path.isfile(a.dub):
            raise Fail("usage", "时间轴文件不存在：%s" % a.dub, EXIT_USAGE)
        td = json.load(io.open(a.dub, encoding="utf-8"))
        timeline = td.get("timeline") if isinstance(td, dict) else td
        if not isinstance(timeline, list) or not timeline:
            raise Fail("usage", "%s 里没有 timeline" % a.dub, EXIT_USAGE)
        lines = merge_segments(timeline, gap=a.gap, max_chars=a.max_chars)
        align = "dub"
    outdir = a.outdir or "."
    prefix = a.prefix or "localize"
    os.makedirs(outdir, exist_ok=True)
    srt = write_text(os.path.join(outdir, "%s-%s.srt" % (prefix, a.to)), to_srt(lines))
    vtt = write_text(os.path.join(outdir, "%s-%s.vtt" % (prefix, a.to)), to_vtt(lines))
    txt = write_text(os.path.join(outdir, "%s-%s.txt" % (prefix, a.to)),
                     "\n".join(x["text"] for x in lines) + "\n")
    out = {"ok": True, "mode": "subtitle", "to": a.to, "lines": len(lines),
           "align": align, "srt": srt, "vtt": vtt, "txt": txt,
           "duration": lines[-1]["end"] if lines else 0, "points": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("字幕已生成（本地，0 点）")
    print("  对齐方式：%s" % ("配音时间轴" if align == "dub" else "原视频时间轴"))
    print("  行数：%d  覆盖：%s 秒" % (len(lines), out["duration"]))
    print("  SRT：%s" % srt)
    print("  VTT：%s" % vtt)
    print("  纯文本：%s" % txt)
    return 0


def cmd_task(a, key, host):
    need(a, "task_id")
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + a.task_id, key, None,
                        60, retries=2)
    d = jloads(txt) or {}
    if st != 200:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    task = d.get("data") if isinstance(d.get("data"), dict) else {}
    if not task:
        raise Fail("call", "任务不存在：%s（%s）"
                   % (a.task_id, d.get("msg") or "没有 data"), EXIT_CALL)
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    audio = find_url(result)
    out = {"ok": True, "mode": "task", "taskId": a.task_id,
           "status": task.get("status"), "error": task.get("error"),
           "audioUrl": audio, "usage": task.get("usage")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  状态：%s" % (task.get("status") or "?"))
    if task.get("error"):
        print("  错误：%s" % json.dumps(task["error"], ensure_ascii=False)[:300])
    if audio:
        print("  音频：%s" % audio)
    if task.get("usage"):
        print("  用量：%s" % json.dumps(task["usage"], ensure_ascii=False))
    print("  说明：轮询只走 GET /api/v1/tasks/<id>（免费）")
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
        print("  %s  %-10s %-4s %-24s %s" % (
            e.get("at"), e.get("mode") or "-", e.get("to") or "-",
            (e.get("srt") or e.get("lines") or ""),
            ("%s 点" % e.get("pointsFloor")) if e.get("pointsFloor") is not None
            else ("%s 点" % e.get("points")) if e.get("points") is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 多语言出海（一条中文视频 -> 12 语版本：转写 + 翻译 + 配音 + 字幕）",
        epilog="端点：POST %s%s（转写）· POST %s%s（翻译）· POST %s%s（配音）· "
               "GET %s/api/v1/tasks/<id>（轮询，免费）"
               % (DEFAULT_HOST, STT_PATH, DEFAULT_HOST, CHAT_PATH, DEFAULT_HOST,
                  VOICE_PATH, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，1 元 = 100 点，默认 %d）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=4096,
                    help="翻译输出上限（token，默认 4096）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="4 条线路 + 12 语言 + 67 音色 + 价目（免费）",
                       allow_abbrev=False)
    p.add_argument("--voices", action="store_true", help="把 67 个音色全列出来")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱：1/5/10/20/30/60 分钟价目（免费）",
                       allow_abbrev=False)
    p.add_argument("--to", default="en", choices=LANG_CODE, help="目标语言（默认 en）")
    p.add_argument("--minutes", type=int, default=0, help="只算这一档分钟数（默认出全表）")
    p.add_argument("--ratio", type=float, default=DEFAULT_RATIO,
                   help="目标语言字数 / 源码字数（默认 %.1f，估配音条数用）" % DEFAULT_RATIO)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 价目 / 任务查询（免费，0 点）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def add_out(p):
        p.add_argument("--outdir", default=".", help="产物目录（默认当前目录）")
        p.add_argument("--prefix", default="localize", help="文件名前缀（默认 localize）")

    def add_paid(p):
        p.add_argument("--yes", action="store_true", help="确认真实计费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
        p.add_argument("--timeout", type=int, default=300, help="单次请求超时秒数（默认 300）")

    p = sub.add_parser("transcribe", help="原视频 -> 台词稿 + 字级时间轴 + 源字幕（120 点/次）",
                       allow_abbrev=False)
    p.add_argument("--input", help="本地视频 / 音频路径")
    p.add_argument("--audio-url", dest="audio_url", help="公网音频地址（与 --input 二选一）")
    p.add_argument("--language", default=None, help="源语言代码（默认自动检测）")
    p.add_argument("--gap", type=float, default=0.7, help="停顿超过多少秒断行（默认 0.7）")
    p.add_argument("--max-chars", dest="max_chars", type=int, default=18,
                   help="单行最多多少字（默认 18）")
    add_out(p)
    add_paid(p)
    p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("translate", help="台词稿 -> 目标语言台词稿（按 token）",
                       allow_abbrev=False)
    p.add_argument("--in", dest="input", help="transcribe 产出的 -source.json")
    p.add_argument("--text-file", dest="text_file", help="纯文本台词稿（一行一条）")
    p.add_argument("--text", help="直接给一段文字")
    p.add_argument("--to", default="en", choices=LANG_CODE, help="目标语言（默认 en）")
    p.add_argument("--model", default=DEFAULT_MODEL, help="文本模型（默认 %s）" % DEFAULT_MODEL)
    add_out(p)
    add_paid(p)
    p.set_defaults(fn=cmd_translate)

    p = sub.add_parser("voice", help="目标语言台词稿 -> 外语配音（60 点/条起）",
                       allow_abbrev=False)
    p.add_argument("--in", dest="input", help="translate 产出的 -<lang>.json")
    p.add_argument("--text-file", dest="text_file", help="纯文本台词稿（一行一条）")
    p.add_argument("--text", help="直接给一段文字")
    p.add_argument("--voice", default=None,
                   help="音色 ID（67 个枚举之一；也可填名字，唯一匹配才认）")
    p.add_argument("--speed", type=float, default=None, help="语速 0.7-1.2（默认 1）")
    p.add_argument("--style", type=float, default=None, help="风格夸张 0-1（默认 0）")
    p.add_argument("--stability", type=float, default=None, help="稳定性 0-1（默认 0.5）")
    p.add_argument("--similarity", type=float, default=None, help="相似度 0-1（默认 0.75）")
    p.add_argument("--timestamps", action="store_true", help="要逐词时间轴（字幕对齐用）")
    p.add_argument("--prev-text", dest="prev_text", help="上一段文本（跨段连贯）")
    p.add_argument("--next-text", dest="next_text", help="下一段文本（跨段连贯）")
    p.add_argument("--every", type=int, default=3, help="轮询间隔秒数（默认 3）")
    p.add_argument("--wait", type=int, default=300, help="轮询上限秒数（默认 300）")
    add_out(p)
    add_paid(p)
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("subtitle", help="多语言字幕 SRT / VTT（本地，0 点）",
                       allow_abbrev=False)
    p.add_argument("--in", dest="input", required=True, help="带 segments 的 JSON")
    p.add_argument("--to", default="en", choices=LANG_CODE, help="语言代码（用于文件名）")
    p.add_argument("--align", default="source", choices=["source", "dub"],
                   help="按原视频时间轴（默认）或用配音逐词时间轴")
    p.add_argument("--dub", help="配音时间轴 JSON（--align dub 时用）")
    p.add_argument("--gap", type=float, default=0.7, help="停顿断行阈值（默认 0.7）")
    p.add_argument("--max-chars", dest="max_chars", type=int, default=18,
                   help="单行最多多少字（默认 18）")
    add_out(p)
    p.set_defaults(fn=cmd_subtitle)

    p = sub.add_parser("run", help="一条命令跑完整链路 + 多版本输出（要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--input", required=True, help="本地视频 / 音频路径")
    p.add_argument("--to", default="en", choices=LANG_CODE, help="目标语言（默认 en）")
    p.add_argument("--voice", default=None, help="音色 ID（默认 Brian）")
    p.add_argument("--script", help="自带目标语言台词稿（跳过翻译，一行对一条字幕）")
    p.add_argument("--minutes", type=int, default=10,
                   help="视频约多少分钟（估预算用，默认 10）")
    p.add_argument("--chars", type=int, default=0,
                   help="源文大约多少字（比 --minutes 更准，给了就优先）")
    p.add_argument("--ratio", type=float, default=DEFAULT_RATIO,
                   help="目标字数 / 源字数（默认 %.1f，估配音条数用）" % DEFAULT_RATIO)
    p.add_argument("--model", default=DEFAULT_MODEL, help="翻译模型（默认 %s）" % DEFAULT_MODEL)
    p.add_argument("--language", default=None, help="源语言代码（默认自动检测）")
    p.add_argument("--gap", type=float, default=0.7, help="停顿断行阈值（默认 0.7）")
    p.add_argument("--max-chars", dest="max_chars", type=int, default=18,
                   help="单行最多多少字（默认 18）")
    p.add_argument("--speed", type=float, default=None, help="语速 0.7-1.2")
    p.add_argument("--style", type=float, default=None, help="风格夸张 0-1")
    p.add_argument("--stability", type=float, default=None, help="稳定性 0-1")
    p.add_argument("--similarity", type=float, default=None, help="相似度 0-1")
    p.add_argument("--timestamps", action="store_true", help="配音同时取逐词时间轴")
    p.add_argument("--prev-text", dest="prev_text")
    p.add_argument("--next-text", dest="next_text")
    p.add_argument("--every", type=int, default=3, help="轮询间隔秒数（默认 3）")
    p.add_argument("--wait", type=int, default=300, help="轮询上限秒数（默认 300）")
    add_out(p)
    add_paid(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("task", help="查任务（GET /tasks/<id>，免费）", allow_abbrev=False)
    p.add_argument("--task-id", dest="task_id", help="提交时返回的 task_id")
    p.set_defaults(fn=cmd_task)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以（每一条都给 default=SUPPRESS，避免覆盖父级默认值）
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE_NO_KEY = (cmd_catalog, cmd_cost, cmd_subtitle, cmd_log)


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("budget", DEFAULT_BUDGET), ("max_tokens", 4096)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    if not hasattr(a, "json"):
        a.json = False
    key, host = load_conf(getattr(a, "key", None), getattr(a, "host", None))
    try:
        if not key and a.fn not in FREE_NO_KEY:
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
