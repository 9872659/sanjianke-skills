#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 高保真语音台（8 个语音接口，一个命令）

走 api.a7w.cn 的 Official 音频与辅助服务（应用代号 `media_services_33`），
本包接其中 **8 个语音接口** —— ElevenLabs 三条音色线 + Gemini 五条对话 / 造音线。
（同一应用里另外 21 个 Suno 音乐接口在 sanjianke-suno-music，本包不接。）

## 统一形态

    POST /api/v1/apps/media_services_33/<接口code>    JSON
    GET  /api/v1/tasks/<task_id>                      只读、免费

## 8 条线（--line）

  v2            elevenlabs_text_to_speech_multilingual_v2   单人，行业标杆音质
  turbo         elevenlabs_text_to_speech_turbo_2_5         单人，极速档
  v3            elevenlabs_text_to_dialogue_v3              多人对白，每句自带 voice
  gemini38      google_gemini_3_8_flash_tts                 对话式，70 音色，逐句可给语气
  gemini38lite  google_gemini_3_8_flash_lite_tts            同上，轻量档
  gemini25pro   google_gemini_2_5_pro_tts                   30 音色 + 口音 / 语速 / 情感
  omni          gemini_omni_audio                           音色设计（描述换音色）
  character     gemini_omni_character                       角色设计（图片换角色）

## 参数形态（实测，不是猜的）

  voice（ElevenLabs）= **音色 ID**，不是名字，67 个 ID 全在枚举里。
      实测 {"text":"hi","voice":"bogus"} ->
      {"code":0,"msg":"input.voice: 不在允许选项内","data":null}
  dialogue（V3）= **数组**，每项 {"text","voice"}。
      实测 {"dialogue":"x"} -> {"code":0,"msg":"input.dialogue: 类型不正确","data":null}
  speakers（Gemini）= **数组**，每项 {"speaker_id","voice_name"}；
      dialogue_turns = **数组**，每项 {"speaker_id","text"}。
      类型不对时该线回 HTTP 500「服务内部错误」，同样不建单（60 点冻结后原路退回）。

## 校验返回：HTTP 状态码不可信

  参数校验失败也是 **HTTP 200** + {"code":0,"msg":"input.xxx: …","data":null}。
  所以判断成功只能看 `code == 1`。

## 价格口径（诚实）

  `GET /api/v1/pricing` 的 115 条规则里**没有 media_services_33**，也没有
  elevenlabs_* / gemini*_tts 的任何专属规则（逐条查过），全部落通配：

      {"mode":"flat","cost":0,"markupPercent":100,"minPoints":50,
       "note":"未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"}

  实测每次 POST 先预冻结 **60 点**（50 保底 × 站点 20% 加价），按上游实际结算。
  所以本包 `cost` 给的是**下限估算：60 点/条** —— 一条到底多少钱，真跑一次才知道。

## 两道闸门

  `--budget` 单位是「点」（1 元 = 100 点）；`--yes` 是第二道。
  缺 `--yes` -> exit 4 并告诉你下限；下限 > `--budget` -> exit 5，**一个请求都不发**。

## 子命令

  catalog    8 条线 + 必填项 + 音色数（免费）
  voices     音色库：ElevenLabs 67 个 ID / Gemini 3.8 70 / 2.5 Pro 30 / Omni 30（免费）
  cost       先算钱，给下限（免费）
  doctor     自检 Key / 应用 / 8 个端点 / 价目口径 / 查询路由（默认零 POST、不冻不扣）
  speak      单人配音（v2 / turbo）
  dialogue   多人对白（v3）
  scene      场景对话（gemini38 / gemini38lite / gemini25pro）
  design     设计音色（omni）
  character  造角色（character）
  task       查任务（免费）
  log        本地台账

## 用法

  python3 scripts/run.py doctor
  python3 scripts/run.py voices --line v2
  python3 scripts/run.py speak --line v2 --text "你终于来了。" --voice James --yes
  python3 scripts/run.py dialogue --voices "1=James,2=Arabella" \\
      --turn "1: 你终于来了。" --turn "2: 我一直在等你。" --yes
  python3 scripts/run.py scene --line gemini38 --cast "1=Kore,2=Fenrir" \\
      --turn "1: 门外有人。" --turn "2: <whispering> 别开门。" --filler-words --yes
  python3 scripts/run.py task --task-id task_xxx

Key：`--key` -> 环境变量 `A7W_API_KEY` -> `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题可加技术微信 9872659。
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# ── GBK 编码兜底 ────────────────────────────────────────────────────────────
# Windows 控制台/管道下 stdout 用本地编码（cp936）。先把 errors 改成 replace，
# 输出里的 √ / × 这类符号才不会把进程带崩（实测 PYTHONIOENCODING=gbk 必须 exit 0）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                             # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
APP = "media_services_33"

POINTS_PER_YUAN = 100
MIN_POINTS = 50            # 通配规则 minPoints
SITE_MARKUP = 20           # /api/v1/pricing 顶层 markupPercent
TASK_FLOOR = 60            # 实测：每次 POST 预冻结 60 点（50 × 1.2）
DEFAULT_BUDGET = 600

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "pro-voice-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-pro-voice/%s" % VERSION

# ── 8 条线 ──────────────────────────────────────────────────────────────────
LINES = {
    "v2": dict(code="elevenlabs_text_to_speech_multilingual_v2",
               name="多语言 V2", family="elevenlabs", kind="single",
               desc="行业标杆音质，67 个音色，情绪 / 稳定性 / 相似度都能调"),
    "turbo": dict(code="elevenlabs_text_to_speech_turbo_2_5",
                  name="Turbo 2.5", family="elevenlabs", kind="single",
                  desc="同一条文本更快出，唯一支持强制指定语言的 ElevenLabs 档"),
    "v3": dict(code="elevenlabs_text_to_dialogue_v3",
               name="对话 V3", family="elevenlabs", kind="dialogue",
               desc="多人对白，每句自带音色，一次出整段对手戏"),
    "gemini38": dict(code="google_gemini_3_8_flash_tts",
                     name="Gemini 3.8 Flash 对话", family="gemini", kind="scene",
                     desc="70 音色 + 逐句语气描述，会接话、会加语气词"),
    "gemini38lite": dict(code="google_gemini_3_8_flash_lite_tts",
                         name="Gemini 3.8 Flash Lite 对话", family="gemini", kind="scene",
                         desc="与 3.8 同一套音色和参数，轻量档"),
    "gemini25pro": dict(code="google_gemini_2_5_pro_tts",
                        name="Gemini 2.5 Pro 对话", family="gemini", kind="scene",
                        desc="30 音色 + 8 种口音 / 4 档语速 / 6 种情感，适合有声书"),
    "omni": dict(code="gemini_omni_audio",
                 name="Omni 音色设计", family="gemini", kind="design",
                 desc="给一段音色描述，造一个可复用的音色"),
    "character": dict(code="gemini_omni_character",
                      name="Omni 角色设计", family="gemini", kind="character",
                      desc="给 1~2 张参考图 + 人设，造一个带声音的角色"),
}
SINGLE_LINES = ["v2", "turbo"]
SCENE_LINES = ["gemini38", "gemini38lite", "gemini25pro"]
LINE_ORDER = ["v2", "turbo", "v3", "gemini38", "gemini38lite", "gemini25pro",
              "omni", "character"]

# ── ElevenLabs 音色：67 个 ID（params_schema 里的枚举，逐条解析出来）─────────
ELEVEN_VOICES = [
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
    ("wo6udizrrtpIxWGp2qJk", "Northern Terry", ""),
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
    ("kPzsL2i3teMYv0FxEYQ6", "Brittney", "社交媒体语音 - 有趣、年轻、信息丰富"),
    ("UgBBYS2sOqTuMpoF3BR0", "Mark", "自然对话"),
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
    ("Sq93GQT4X1lKDXsQcixO", "Felix", "温暖、积极、现代RP"),
    ("flHkNRp1BlvT73UL6gyz", "Jessica Anne Bogart", "雄辩的反派"),
    ("9yzdeviXkFddZ4Oz8Mok", "Lutz", "咯咯笑、欢快"),
    ("pPdl9cQBQq4p6mRkZy2Z", "Emma", "可爱、积极向上"),
    ("zYcjlYFOd3taleS0gkk3", "Edward", "大声、自信、自负"),
    ("nzeAacJi50IvxcyDnMXa", "Marshal", "友好、幽默的教授"),
    ("ruirxsoakN0GWmGNIo04", "John Morgan", "粗犷、坚韧的牛仔"),
    ("TC0Zp7WVFzhA8zpTlRqV", "Aria", "性感反派"),
    ("ljo9gAlSqKOvF6D8sOsX", "Viking Bjorn", "史诗中世纪掠夺者"),
    ("PPzYpIqttlTYA83688JI", "Pirate Marshal", "海盗元帅"),
    ("8JVbfL6oEdmuxKn5DK2C", "Johnny Kid", "严肃、平静的旁白"),
    ("iCrDUkL56s3C8sCRl7wb", "Hope", "诗意、浪漫、迷人"),
    ("wJqPPQ618aTW29mptyoc", "Ana Rita", "流畅、富有表现力、明亮"),
    ("EiNlNiXeDU1pqqOPrYMO", "John Doe", "低沉"),
    ("4YYIPFl9wE5c4L2eu2Gb", "Burt Reynolds™", "低沉、流畅、清晰"),
    ("6F5Zhi321D3Oq7v1oNT4", "Hank", "低沉、引人入胜的旁白"),
    ("YXpFCvM1S3JbWEJhoskW", "Wyatt", "睿智乡村牛仔"),
    ("LG95yZDEHg6fCZdQjLqj", "Phil", "爆发力、热情播音员"),
    ("CeNX9CMwmxDxUF5Q2Inm", "Johnny Dynamite", "复古电台DJ"),
    ("aD6riP1btT197c6dACmy", "Rachel M", "专业英国电台主持人"),
    ("mtrellq69YZsNwzUSyXh", "Rex Thunder", "低沉强硬"),
    ("dHd5gvgSOzSfduK4CvEg", "Ed", "深夜播音员"),
    ("eVItLK1UvXctxuaRV2Oq", "Jean", "迷人、俏皮的蛇蝎美人"),
    ("esy0r39YPLQjOczyOib8", "Britney", "冷静、算计的反派"),
    ("Tsns2HvNFKfGiNjllgqo", "Sven", "情感丰富、友善"),
    ("1U02n4nD6AdIZ9CjF053", "Viraj", "流畅、温柔"),
    ("AeRdCCKzvd23BpJoofzx", "Nathaniel", "引人入胜、英式、平静"),
    ("LruHrtVF6PSyGItzMNHS", "Benjamin", "低沉、温暖、平静"),
    ("1wGbFxmAM3Fgw63G1zZJ", "Allison", "平静、舒缓、冥想"),
    ("hqfrgApggtO1785R4Fsn", "Theodore HQ", "宁静、沉稳"),
    ("MJ0RnG71ty4LH3dvNfSd", "Leon", "舒缓、沉稳"),
]
ELEVEN_IDS = [v[0] for v in ELEVEN_VOICES]

# ── Gemini 音色（3.8 与 2.5 Pro 的 voice_name 枚举）─────────────────────────
GEMINI38_VOICES = [
    "Bodi", "Lumi", "Sadaltager", "Sola", "Sulafat", "Varo", "Zephyr", "Koda",
    "Kore", "Nika", "Tavi", "Zeno", "Algenib", "Despina", "Erinome", "Kira",
    "Ludo", "Mako", "Rasalgethi", "Rina", "Alnilam", "Brio", "Jori", "Laomedeia",
    "Rami", "Veda", "Achird", "Enzo", "Riko", "Sami", "Zali", "Zubenelgenubi",
    "Algieba", "Aoede", "Autonoe", "Callirrhoe", "Enceladus", "Gero", "Iapetus",
    "Neno", "Olin", "Tari", "Umbriel", "Achernar", "Charon", "Daro", "Fola",
    "Hali", "Milo", "Puck", "Arlo", "Cleo", "Fenrir", "Finn", "Leda", "Lora",
    "Orus", "Enya", "Jett", "Knox", "Nyla", "Sadachbia", "Vindemiatrix", "Cruz",
    "Elio", "Gacrux", "Pulcherrima", "Schedar", "Tova", "Zuri",
]
GEMINI25_VOICES = [
    "Achernar", "Achird", "Algenib", "Algieba", "Alnilam", "Aoede", "Autonoe",
    "Callirrhoe", "Charon", "Despina", "Enceladus", "Erinome", "Fenrir", "Gacrux",
    "Iapetus", "Kore", "Laomedeia", "Leda", "Orus", "Puck", "Pulcherrima",
    "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar", "Sulafat", "Umbriel",
    "Vindemiatrix", "Zephyr", "Zubenelgenubi",
]
GEMINI38_DEFAULT_VOICE = "Fola"
ACCENTS = ["Neutral", "American (Gen)", "American (Valley)", "American (South)",
           "British (RP)", "British (Brixton)", "Transatlantic", "Australian"]
PACES = ["Natural", "Rapid Fire", "The Drift", "Staccato"]
STYLES = ["Vocal Smile", "Newscaster", "Whisper", "Empathetic", "Promo/Hype", "Deadpan"]

# ── Omni audio_id：30 个预设音色 ────────────────────────────────────────────
OMNI_VOICES = [
    ("achernar", "女声，柔和，高音调"), ("achird", "男声，友好，中音调"),
    ("algenib", "男声，沙哑，低音调"), ("algieba", "男声，随和，中低音调"),
    ("alnilam", "男声，沉稳，中低音调"), ("aoede", "女声，轻快，中音调"),
    ("autonoe", "女声，明亮，中音调"), ("callirrhoe", "女声，随和，中音调"),
    ("charon", "男声，知性，低音调"), ("despina", "女声，流畅，中音调"),
    ("enceladus", "男声，气声，低音调"), ("erinome", "女声，清晰，中音调"),
    ("fenrir", "男声，活泼，偏年轻音调"), ("gacrux", "女声，成熟，中音调"),
    ("iapetus", "男声，清晰，中低音调"), ("kore", "女声，干练，中音调"),
    ("laomedeia", "女声，欢快，中高音调"), ("leda", "女声，年轻，中高音调"),
    ("orus", "男声，沉稳，中低音调"), ("puck", "男声，欢快，中音调"),
    ("pulcherrima", "无性别，前置感，中高音调"), ("rasalgethi", "男声，知性，中音调"),
    ("sadachbia", "男声，生动，低音调"), ("sadaltager", "男声，博学，中音调"),
    ("schedar", "男声，平稳，中低音调"), ("sulafat", "女声，温暖，中音调"),
    ("umbriel", "男声，流畅，低音调"), ("vindemiatrix", "女声，温柔，中音调"),
    ("zephyr", "女声，明亮，中高音调"), ("zubenelgenubi", "男声，随性，中低音调"),
]
OMNI_IDS = [v[0] for v in OMNI_VOICES]

# 3.8 的台词里可插的语气标签（官网 40 个，实测取自 params_schema 原文）
VOICE_TAGS = [
    "argh", "breath", "cackle", "cheer", "chuckle", "chuckles", "cough", "cry",
    "exhales", "gasp", "giggle", "groan", "growl", "grr", "grunt", "heavy breath",
    "hiss", "laugh", "laughter", "long pause", "moan", "pant", "pff", "phew",
    "scream", "short pause", "shout", "shriek", "sigh", "sighs", "sneeze",
    "snicker", "snort", "sob", "throat-clearing", "tsk", "whimper", "whispering",
    "whispers", "yawn",
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
        except Exception:                                         # noqa: BLE001
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
    except Exception as e:                                        # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                             # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        if d.get("msg"):
            return str(d["msg"])[:300]
        e = d.get("error")
        if isinstance(e, dict) and e.get("message"):
            return str(e["message"])[:300]
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条路径下没有该端点" % st
    return txt.replace("\n", " ")[:240]


def fmt_pts(n):
    return "{:,}".format(int(round(float(n))))


def endpoint(code):
    return API_PREFIX + "/apps/" + APP + "/" + code


def find_urls(obj, out=None, depth=0):
    """把返回里所有 http(s) 地址挖出来（成功结构还没实测过，两种都兼容）。"""
    if out is None:
        out = []
    if depth > 6 or len(out) >= 8:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("http"):
                if k.lower().endswith(("url", "urls", "uri")) or "audio" in k.lower():
                    if v not in out:
                        out.append(v)
            else:
                find_urls(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            find_urls(v, out, depth + 1)
    return out


def resolve_eleven_voice(name):
    """--voice 收 ID 或名字（名字可重复：Mark / Hope / Viraj 各两个）。"""
    raw = (name or "").strip()
    if not raw:
        raise Fail("usage", "--voice 必填：填 67 个音色 ID 之一，或音色名（如 James）。"
                   "`voices --line v2` 列全表。", EXIT_USAGE)
    if raw in ELEVEN_IDS:
        return raw, None
    low = raw.lower()
    hits = [v for v in ELEVEN_VOICES if v[1].lower() == low]
    if not hits:
        hits = [v for v in ELEVEN_VOICES if low in v[1].lower()]
    if not hits:
        raise Fail("usage", "找不到音色「%s」。用 `voices --line v2` 看全表；"
                   "也可以直接填 20 位音色 ID。" % raw, EXIT_USAGE)
    note = None
    if len(hits) > 1:
        note = "「%s」对应 %d 个 ID，本包取第一个 %s（%s）" % (
            raw, len(hits), hits[0][0], hits[0][2] or hits[0][1])
    return hits[0][0], note


def resolve_gemini_voice(name, line):
    pool = GEMINI38_VOICES if line != "gemini25pro" else GEMINI25_VOICES
    low = (name or "").strip().lower()
    for v in pool:
        if v.lower() == low:
            return v
    raise Fail("usage", "「%s」不在这条线的音色表里。用 `voices --line %s` 看 %d 个名字"
               "（大小写不敏感，但必须是表里的名字）。" % (name, line, len(pool)),
               EXIT_USAGE)


def parse_turns(raw_turns, script_path):
    """剧本行 / --turn 都按「角色: 台词」解析，角色按出现顺序映射到 Speaker N。

    Gemini 的 speaker_id 必须是「Speaker N」；名字只是给人看的标签，
    本包自动编号并把映射打出来，`--cast` / `--voices` 里写名字或数字都认。
    """
    lines = []
    if script_path:
        if not os.path.isfile(script_path):
            raise Fail("usage", "剧本文件不存在：%s" % script_path, EXIT_USAGE)
        try:
            txt = io.open(script_path, encoding="utf-8").read()
        except Exception as e:                                    # noqa: BLE001
            raise Fail("usage", "读不了剧本文件（要 UTF-8）：%s: %s"
                       % (script_path, e), EXIT_USAGE)
        lines.extend(txt.splitlines())
    lines.extend(raw_turns or [])
    if not lines:
        raise Fail("usage", "还没给台词。用 --turn \"1: 第一句\" 重复给，"
                   "或用 --script 剧本.txt（每行「角色: 台词」，# 开头是注释）。",
                   EXIT_USAGE)
    order, turns = [], []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        sep = ":" if ":" in s else ("：" if "：" in s else None)
        if sep is None:
            raise Fail("usage", "这行没有「角色: 台词」的分隔：%s" % s[:60], EXIT_USAGE)
        label, text = s.split(sep, 1)
        label, text = label.strip(), text.strip()
        if not label or not text:
            raise Fail("usage", "这行角色或台词是空的：%s" % s[:60], EXIT_USAGE)
        if label not in order:
            order.append(label)
        turns.append((label, text))
    mapping = {}
    for i, label in enumerate(order, 1):
        m = re.match(r"^(?:speaker\s*)?(\d+)$", label, re.I)
        mapping[label] = "Speaker %s" % (m.group(1) if m else i)
    return turns, mapping, order


def label_sid(label, mapping, order):
    if label in mapping:
        return mapping[label]
    raise Fail("usage", "角色「%s」不在台词里。台词里出现的角色：%s"
               % (label, "、".join(order)), EXIT_USAGE)


def parse_map(raw_list, mapping, order):
    """把 "1=xxx" / "林晚=xxx" 这种映射解析成 {Speaker N: value}。"""
    out = {}
    for item in raw_list or []:
        if "=" not in item:
            raise Fail("usage", "映射要写成 角色=值（例：1=James 或 林晚=James），收到「%s」"
                       % item, EXIT_USAGE)
        k, v = item.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            raise Fail("usage", "映射缺左边或右边：「%s」" % item, EXIT_USAGE)
        out[label_sid(k, mapping, order)] = v
    return out


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                             # noqa: BLE001
        pass


# ───────────────────────── 免费子命令 ─────────────────────────
def line_voice_count(ln):
    """这条线可选多少个音色 —— 表格里一眼能看出哪条线音色多。"""
    kind = LINES[ln]["kind"]
    if kind in ("design", "character"):
        return len(OMNI_IDS)
    if LINES[ln]["family"] == "elevenlabs":
        return len(ELEVEN_IDS)
    return len(GEMINI25_VOICES) if ln == "gemini25pro" else len(GEMINI38_VOICES)


def cmd_catalog(a, key, host):
    rows = []
    for ln in LINE_ORDER:
        m = LINES[ln]
        rows.append({"line": ln, "code": m["code"], "name": m["name"],
                     "family": m["family"], "kind": m["kind"],
                     "endpoint": host + endpoint(m["code"]), "desc": m["desc"],
                     "voices": line_voice_count(ln)})
    out = {"ok": True, "count": len(rows), "app": APP, "lines": rows,
           "taskFloorPoints": TASK_FLOOR, "minPoints": MIN_POINTS,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 高保真语音台 —— 8 条线（同一条 POST，换 code 就换音色线）")
    print()
    print("  %-13s %-46s %-6s %s" % ("--line", "接口 code", "音色", "干什么"))
    print("  " + "-" * 116)
    for r in rows:
        print("  %-13s %-46s %-6s %s" % (r["line"], r["code"], r["voices"], r["desc"]))
    print()
    print("  端点：POST %s/api/v1/apps/%s/<code>  （JSON，一次一条任务）" % (host, APP))
    print("  查询：GET  %s/api/v1/tasks/<taskId>  （免费）" % host)
    print("  价格：pricing 里没有 media_services_33 的规则，落通配「上游 × 2，保底 50 点」；")
    print("        实测每次 POST 预冻结 %d 点，这就是下单下限（1 元 = 100 点）。" % TASK_FLOOR)
    print()
    print("  三条线一句话对照：v2 = 音质标杆；turbo = 同样能打但更快；")
    print("                    v3 = 多人对白；gemini38 / 2.5pro = 会接话、带语气。")
    return 0


def cmd_voices(a, key, host):
    want = a.line
    data = {"elevenlabs": [{"id": v[0], "name": v[1], "note": v[2]}
                           for v in ELEVEN_VOICES],
            "gemini38": GEMINI38_VOICES, "gemini25pro": GEMINI25_VOICES,
            "omni": [{"id": v[0], "note": v[1]} for v in OMNI_VOICES]}
    if a.json:
        keep = data if not want else {k: v for k, v in data.items()
                                      if (k == "elevenlabs" and want in ("v2", "turbo", "v3"))
                                      or (k == "gemini38" and want in ("gemini38",
                                                                       "gemini38lite"))
                                      or (k == "gemini25pro" and want == "gemini25pro")
                                      or (k == "omni" and want == "omni")}
        print(json.dumps({"ok": True, "voices": keep, "tags": VOICE_TAGS},
                         ensure_ascii=False))
        return 0
    if want is None or want in ("v2", "turbo", "v3"):
        print("ElevenLabs 音色 %d 个 —— --voice 填 ID 或名字（大小写不敏感）" % len(ELEVEN_IDS))
        print()
        for vid, name, note in ELEVEN_VOICES:
            print("  %-31s %s  %s" % (name, vid, note))
        print()
    if want is None or want in ("gemini38", "gemini38lite"):
        print("Gemini 3.8 音色 %d 个 —— --cast 1=<名字>，默认 %s"
              % (len(GEMINI38_VOICES), GEMINI38_DEFAULT_VOICE))
        print()
        line = []
        for i, v in enumerate(GEMINI38_VOICES, 1):
            line.append("%-14s" % v)
            if i % 5 == 0:
                print("  " + "".join(line))
                line = []
        if line:
            print("  " + "".join(line))
        print()
        print("  台词里可插语气标签（尖括号）：%s" % "、".join("<%s>" % t for t in VOICE_TAGS[:12]))
        print("  全套 40 个：<laugh> <sigh> <whispering> <long pause> <gasp> <cry> …")
        print()
    if want is None or want == "gemini25pro":
        print("Gemini 2.5 Pro 音色 %d 个 —— 另需 accent（默认 Neutral）" % len(GEMINI25_VOICES))
        print()
        print("  " + "  ".join(GEMINI25_VOICES))
        print()
        print("  口音：%s" % " / ".join(ACCENTS))
        print("  语速：%s" % " / ".join(PACES))
        print("  情感：%s" % " / ".join(STYLES))
        print()
    if want is None or want == "omni":
        print("Gemini Omni audio_id %d 个 —— design --audio-id <id>" % len(OMNI_IDS))
        print()
        for vid, note in OMNI_VOICES:
            print("  %-16s %s" % (vid, note))
        print()
    return 0


def cmd_cost(a, key, host):
    n = max(1, int(a.tasks))
    pts = TASK_FLOOR * n
    detail = {"tasks": n, "points": pts, "yuan": round(pts / float(POINTS_PER_YUAN), 2),
              "basis": "%d 点/条 × %d 条 = %d 点（预冻结口径）" % (TASK_FLOOR, n, pts)}
    if a.line:
        m = LINES[a.line]
        detail.update({"line": a.line, "code": m["code"], "name": m["name"]})
    rows = []
    for ln in LINE_ORDER:
        m = LINES[ln]
        rows.append({"line": ln, "name": m["name"], "code": m["code"],
                     "floorPoints": TASK_FLOOR,
                     "floorYuan": round(TASK_FLOOR / float(POINTS_PER_YUAN), 2)})
    out = {"ok": True, "yuanPerPoint": 1.0 / POINTS_PER_YUAN, "floorPoints": TASK_FLOOR,
           "minPoints": MIN_POINTS, "siteMarkupPercent": SITE_MARKUP,
           "table": rows, "detail": detail,
           "notes": [
               "这是下限估算：pricing 里没有 media_services_33 / elevenlabs / gemini TTS "
               "的专属规则，落通配「上游实际点数 × 2，单笔保底 50 点」",
               "实测每次 POST 预冻结 60 点（50 保底 × 站点 20% 加价），任务失败原路退回",
               "一条到底多少钱 = 上游按字数 / 时长计的真实点数 × 2，真跑一次才看得到",
               "一次请求 = 一条任务：多人对白里 10 句也是 1 条，不是 10 条",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）")
    print()
    print("  %s" % detail["basis"])
    print("  = %d 点 = %.2f 元（下限；实际以上游真实点数为准）"
          % (detail["points"], detail["yuan"]))
    print()
    print("  %-13s %-24s %-46s %s" % ("--line", "路线", "接口 code", "每条下限"))
    print("  " + "-" * 102)
    for r in rows:
        print("  %-13s %-24s %-46s %d 点（￥%.2f）"
              % (r["line"], r["name"], r["code"], r["floorPoints"], r["floorYuan"]))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


def cmd_doctor(a, key, host):
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点" % (
                       st, fmt_pts(d.get("available_points") or d.get("points") or 0),
                       fmt_pts(d.get("frozen") or 0))))

    # 应用目录（文件里写明 cost:0，只读免费）：确认 8 个端点都注册在同一应用下
    st_a, txt_a = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    live = {}
    app_ok = False
    if st_a == 200:
        apps = jloads(txt_a) or {}
        arr = apps.get("data") if isinstance(apps.get("data"), list) else []
        for it in arr:
            if str(it.get("code")) == APP:
                app_ok = True
                for api in it.get("apis") or []:
                    live[api.get("code")] = api.get("method", "POST")
    miss = [LINES[ln]["code"] for ln in LINE_ORDER if LINES[ln]["code"] not in live]
    checks.append(("应用 %s 已上架，8 个端点全在目录里" % APP, app_ok and not miss,
                   "HTTP %s · 应用 %s · 缺 %s" % (
                       st_a, "在" if app_ok else "没找到",
                       "、".join(miss) if miss else "0 条")))

    # 价目：确认没有专属规则（有的话 doctor 会把它打出来，让你改用真实价）
    st_p, txt_p = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    rules, wildcard, hit = {}, {}, []
    if st_p == 200:
        pr = jloads(txt_p) or {}
        rules = pr.get("pricing") or {}
        wildcard = rules.get("*") or {}
        hit = [k for k in rules
               if "media_services_33" in str(k)
               or "elevenlabs" in str(k).lower()
               or (str(k).startswith("/api/v1/apps/") and "tts" in str(k).lower()
                   and "media" in str(k))]
    has_rule = bool(hit)
    checks.append(("价目口径：8 条线走通配（上游 × 2、保底 50 点）", st_p == 200,
                   "HTTP %s · %d 条规则 · 专属规则 %s · 通配 minPoints=%s" % (
                       st_p, len(rules), ("、".join(hit) if hit else "0 条"),
                       wildcard.get("minPoints"))))

    # 查询路由：假 id -> code 0「任务不存在」，路由在且免费
    st_t, txt_t = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task",
                            key, timeout=40)
    d_t = jloads(txt_t) or {}
    checks.append(("任务查询 GET /tasks/{id} 可用", st_t == 200 and d_t.get("code") == 0,
                   "HTTP %s · %s" % (st_t, (d_t.get("msg") or "")[:40])))

    # 深探（可选）：故意坏参数 POST 8 条，全部停在校验/上游之前
    deeper = []
    if a.probe_post:
        st_b0, txt_b0 = http_json("GET", host + API_PREFIX + "/user/balance", key,
                                  timeout=40)
        b0 = jloads(txt_b0) or {}
        for ln in LINE_ORDER:
            code = LINES[ln]["code"]
            say("  深探 %-13s %s …" % (ln, code))
            st2, txt2 = http_json("POST", host + endpoint(code), key,
                                  PROBE_BODY[ln], timeout=a.timeout)
            d2 = jloads(txt2) or {}
            made = bool(d2.get("data"))
            checks.append(("端点 %-13s 可达（坏参数未建单）" % ln, not made,
                           "HTTP %s %s" % (st2, (d2.get("msg") or err_text(st2, txt2))[:60])))
            deeper.append({"line": ln, "code": code, "http": st2,
                           "msg": d2.get("msg"), "created": made})
        st_b1, txt_b1 = http_json("GET", host + API_PREFIX + "/user/balance", key,
                                  timeout=40)
        b1 = jloads(txt_b1) or {}
        delta = float(b1.get("points") or 0) - float(b0.get("points") or 0)
        checks.append(("深探后余额净变化为 0", abs(delta) < 1e-6,
                       "%s 点（冻结 60 点/条，校验失败原路退回）" % fmt_pts(delta)))

    out = {"ok": all(c[1] for c in checks), "host": host, "app": APP,
           "lineCount": len(LINE_ORDER), "probePost": bool(a.probe_post),
           "probes": deeper, "pricingSource": host + API_PREFIX + "/pricing",
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print()
    print("自检（默认零 POST：只读接口，不冻不扣；--probe-post 才会碰端点）")
    print()
    for n, o, dd in checks:
        print("  %s %-44s %s" % ("√" if o else "×", n, dd))
    print()
    print("  端点：POST %s/api/v1/apps/%s/<code> · 一次一条任务" % (host, APP))
    print("  音色：ElevenLabs %d 个 ID / Gemini 3.8 %d / 2.5 Pro %d / Omni %d"
          % (len(ELEVEN_IDS), len(GEMINI38_VOICES), len(GEMINI25_VOICES), len(OMNI_IDS)))
    print("  价格：通配「上游 × 2，保底 50 点」；实测每次 POST 预冻结 %d 点" % TASK_FLOOR)
    return 0 if out["ok"] else EXIT_GATE


# 深探用的坏参数：每条线只坏在一个字段上，必然停在建单之前。
#   v2 / turbo  过期音色 ID -> "input.voice: 不在允许选项内"（实测）
#   v3          dialogue 给字符串 -> "input.dialogue: 类型不正确"（实测）
#   gemini*     speakers 给字符串 -> 该线回 HTTP 500「服务内部错误」（实测，冻结后退回）
#   omni / character  只给空 body -> 缺必填，最保守的一种坏法
PROBE_BODY = {
    "v2": {"text": "hi", "voice": "bogus"},
    "turbo": {"text": "hi", "voice": "bogus"},
    "v3": {"dialogue": "x"},
    "gemini38": {"speakers": "x"},
    "gemini38lite": {"speakers": "x"},
    "gemini25pro": {"speakers": "x"},
    "omni": {},
    "character": {},
}


# ───────────────────────── 闸门 + 提交 ─────────────────────────
def _gate(a, body, line):
    cost = TASK_FLOOR
    if cost > a.budget:
        raise Fail("budget", "下限 %d 点超过 --budget %d 点（%d 点/条）。"
                   "调大 --budget 再跑，这次一个请求都没发。"
                   % (cost, a.budget, TASK_FLOOR), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "这会真实建单，先预冻结约 %d 点（%.2f 元），完成后按上游实际"
                   "点数 × 2 结算、保底 50 点。确认请加 --yes。"
                   % (cost, cost / float(POINTS_PER_YUAN)), EXIT_CONFIRM)
    return cost


def _submit(a, key, host, line, body):
    code = LINES[line]["code"]
    cost = _gate(a, body, line)
    url = host + endpoint(code)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "line": line, "code": code, "url": url,
               "requestBody": body, "estimatedPoints": cost,
               "yuan": round(cost / float(POINTS_PER_YUAN), 2)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（￥%.2f）下限" % (cost, cost / float(POINTS_PER_YUAN)))
        return 0

    say("正在提交 %s（%s）…" % (line, LINES[line]["name"]))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=a.timeout)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if d.get("code") != 1:
        msg = err_text(st, txt)
        ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "mode": "submit",
                    "line": line, "http": st, "error": msg, "endpoint": endpoint(code)})
        raise Fail("call", "提交被挡下（HTTP %s）：%s" % (st, msg), EXIT_CALL)

    data = d.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict):
        data = {}
    task_id = (data.get("task_id") or data.get("taskId") or data.get("id")
               or d.get("task_id") or d.get("taskId"))
    urls = find_urls(data) or find_urls(d)
    out = {"ok": True, "line": line, "code": code, "taskId": task_id,
           "status": data.get("status"), "audioUrls": urls,
           "estimatedPoints": cost, "elapsed": round(dt, 1),
           "query": API_PREFIX + "/tasks/" + str(task_id or "<taskId>")}
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "mode": "submit",
                "line": line, "taskId": task_id, "status": data.get("status"),
                "audioUrls": urls[:3], "estimatedPoints": cost,
                "elapsed": round(dt, 1), "endpoint": endpoint(code)})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  线路：%s（%s）" % (line, LINES[line]["name"]))
    if task_id:
        print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    if urls:
        print("  音频：%s" % urls[0])
        for u in urls[1:4]:
            print("        %s" % u)
    if not task_id and not urls:
        say("  返回里没看到 task_id 也没看到音频地址，原始返回（前 600 字）：")
        print(txt[:600])
    print()
    if task_id:
        print("  查进度：python3 scripts/run.py task --task-id %s" % task_id)
    return 0


# ───────────────────────── 5 个出片命令 ─────────────────────────
def _read_text(a):
    if a.text and a.text_file:
        raise Fail("usage", "--text 和 --text-file 只给一个", EXIT_USAGE)
    if a.text_file:
        if not os.path.isfile(a.text_file):
            raise Fail("usage", "文本文件不存在：%s" % a.text_file, EXIT_USAGE)
        try:
            return io.open(a.text_file, encoding="utf-8").read().strip()
        except Exception as e:                                    # noqa: BLE001
            raise Fail("usage", "读不了文本文件（要 UTF-8）：%s: %s" % (a.text_file, e),
                       EXIT_USAGE)
    return (a.text or "").strip()


def cmd_speak(a, key, host):
    line = a.line
    text = _read_text(a)
    if not text:
        raise Fail("usage", "还没给台词。--text \"你终于来了。\" 或 --text-file 台词.txt",
                   EXIT_USAGE)
    if len(text) > 5000:
        raise Fail("usage", "这条线的单次上限是 5000 字符，现在是 %d。拆成两段，"
                   "第二段用 --previous-text 接上一段的尾巴，连续性会更好。" % len(text),
                   EXIT_USAGE)
    if line == "v2" and a.language_code:
        raise Fail("usage", "强制语言只有 turbo 支持；V2 传 language_code 会被上游打回。"
                   "换 --line turbo 再来。", EXIT_USAGE)
    vid, note = resolve_eleven_voice(a.voice)
    if note:
        say("  " + note)
    body = {"text": text, "voice": vid}
    if a.speed is not None:
        body["speed"] = a.speed
    if a.style_level is not None:
        body["style"] = a.style_level
    if a.stability is not None:
        body["stability"] = a.stability
    if a.similarity is not None:
        body["similarity_boost"] = a.similarity
    if a.language_code:
        body["language_code"] = a.language_code
    if a.timestamps:
        body["timestamps"] = True
    if a.previous_text:
        body["previous_text"] = a.previous_text
    if a.next_text:
        body["next_text"] = a.next_text
    return _submit(a, key, host, line, body)


def cmd_dialogue(a, key, host):
    turns, mapping, order = parse_turns(a.turn, a.script)
    if not a.voices:
        raise Fail("usage", "多人对白要给每个角色分音色："
                   "--voices \"%s=%s\" 重复给。角色：%s"
                   % (order[0], "James", "、".join(order)), EXIT_USAGE)
    vmap = parse_map(a.voices, mapping, order)
    need = [lb for lb in order]
    lacking = [lb for lb in need if mapping[lb] not in vmap]
    if lacking:
        raise Fail("usage", "这些角色还没分音色：%s（用 --voices 角色=音色）"
                   % "、".join(lacking), EXIT_USAGE)
    items, total = [], 0
    for label, text in turns:
        vid, note = resolve_eleven_voice(vmap[mapping[label]])
        if note:
            say("  " + note)
        items.append({"text": text, "voice": vid})
        total += len(text)
    if total > 5000:
        raise Fail("usage", "对话总字符 %d 超过 5000 上限。删台词或拆成两次。"
                   % total, EXIT_USAGE)
    body = {"dialogue": items}
    if a.stability is not None:
        body["stability"] = a.stability
    if a.language_code:
        body["language_code"] = a.language_code
    if not a.json:
        print("角色映射：%s" % "、".join("%s→%s" % (lb, mapping[lb]) for lb in order))
        print()
    return _submit(a, key, host, "v3", body)


def cmd_scene(a, key, host):
    line = a.line
    turns, mapping, order = parse_turns(a.turn, a.script)
    if not a.cast:
        raise Fail("usage", "要给每个角色指定音色名字：--cast \"%s=%s\" 重复给。"
                   "角色：%s；音色表用 voices --line %s"
                   % (order[0], GEMINI38_VOICES[8] if line != "gemini25pro"
                      else GEMINI25_VOICES[15], "、".join(order), line), EXIT_USAGE)
    cmap = parse_map(a.cast, mapping, order)
    lacking = [lb for lb in order if mapping[lb] not in cmap]
    if lacking:
        raise Fail("usage", "这些角色还没配音色：%s（用 --cast 角色=音色名）"
                   % "、".join(lacking), EXIT_USAGE)
    speakers = []
    for lb in order:
        sid = mapping[lb]
        vname = resolve_gemini_voice(cmap[sid], line)
        item = {"speaker_id": sid, "voice_name": vname}
        if line == "gemini25pro":
            item["accent"] = resolve_choice(a.accent, ACCENTS, "--accent")
            if a.pace:
                item["pace"] = resolve_choice(a.pace, PACES, "--pace")
            if a.emotion:
                item["style"] = resolve_choice(a.emotion, STYLES, "--emotion")
        speakers.append(item)
    styles = {}
    for raw in a.style_turn or []:
        if "=" not in raw:
            raise Fail("usage", "--style-turn 要写成 角色=语气（例：1=Whisper）", EXIT_USAGE)
        k, v = raw.split("=", 1)
        styles[label_sid(k.strip(), mapping, order)] = v.strip()
    if styles and line == "gemini25pro":
        raise Fail("usage", "逐句语气只用于 3.8 两条线；2.5 Pro 用 --emotion（六种固定风格）",
                   EXIT_USAGE)
    dts = []
    for label, text in turns:
        sid = mapping[label]
        if len(text) > 10000:
            raise Fail("usage", "单句 %s 超过 10000 字符上限" % sid, EXIT_USAGE)
        item = {"speaker_id": sid, "text": text}
        if sid in styles and line != "gemini25pro":
            item["style"] = styles[sid]
        dts.append(item)
    body = {"speakers": speakers, "dialogue_turns": dts}
    if a.temperature is not None:
        body["temperature"] = a.temperature
    if line != "gemini25pro" and a.filler_words:
        body["filler_words"] = True
    if line == "gemini25pro":
        if a.scene_desc:
            body["scene"] = a.scene_desc
        if a.sample_context:
            body["sample_context"] = a.sample_context
    if not a.json:
        print("角色映射：%s" % "、".join(
            "%s→%s(%s)" % (lb, mapping[lb], cmap[mapping[lb]]) for lb in order))
        print()
    return _submit(a, key, host, line, body)


def resolve_choice(val, pool, flag):
    if val is None:
        return pool[0]
    for v in pool:
        if v.lower() == str(val).strip().lower():
            return v
    raise Fail("usage", "%s「%s」不在可选值里：%s" % (flag, val, " / ".join(pool)),
               EXIT_USAGE)


def cmd_design(a, key, host):
    if not a.name:
        raise Fail("usage", "要给音色起个名字：--name \"深夜电台-阿岚\"", EXIT_USAGE)
    if not a.audio_id:
        raise Fail("usage", "要选一个底子音色：--audio-id <id>，30 个见 voices --line omni",
                   EXIT_USAGE)
    if a.audio_id not in OMNI_IDS:
        raise Fail("usage", "audio_id「%s」不在 30 个预设里：%s"
                   % (a.audio_id, "、".join(OMNI_IDS)), EXIT_USAGE)
    body = {"name": a.name, "audio_id": a.audio_id}
    if a.example:
        body["example_dialogue"] = a.example
    if a.description:
        body["voice_description"] = a.description
    return _submit(a, key, host, "omni", body)


def cmd_character(a, key, host):
    urls = a.image_url or []
    if not urls:
        raise Fail("usage", "要给 1~2 张参考图地址：--image-url https://… "
                   "（第 1 张是头像，第 2 张可选全身）", EXIT_USAGE)
    if len(urls) > 2:
        raise Fail("usage", "参考图最多 2 张（索引 0 头像、索引 1 全身），收到 %d 张"
                   % len(urls), EXIT_USAGE)
    for u in urls:
        if not re.match(r"^https?://", u, re.I):
            raise Fail("usage", "--image-url 要以 http:// 或 https:// 开头：%s" % u,
                       EXIT_USAGE)
    if not a.description:
        raise Fail("usage", "要给角色描述：--description \"银白短发、未来风机能夹克…\"",
                   EXIT_USAGE)
    body = {"image_urls": urls, "descriptions": a.description}
    if a.audio_ids:
        for aid in a.audio_ids:
            if aid not in OMNI_IDS:
                raise Fail("usage", "audio_id「%s」不在 30 个预设里" % aid, EXIT_USAGE)
        body["audio_ids"] = list(a.audio_ids)
    if a.character_name:
        body["character_name"] = a.character_name
    return _submit(a, key, host, "character", body)


# ───────────────────────── 查询 / 台账 ─────────────────────────
def cmd_task(a, key, host):
    tid = a.task_id
    if not tid:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + tid
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    if st != 200 or d.get("code") != 1:
        raise Fail("call", "查不到任务 %s：%s（刚提交的话等 2 秒再查）"
                   % (tid, err_text(st, txt)), EXIT_CALL)
    data = d.get("data") if isinstance(d.get("data"), dict) else {}
    urls = find_urls(data) or find_urls(d)
    out = {"ok": True, "taskId": tid, "path": path, "status": data.get("status"),
           "audioUrls": urls, "data": data}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % tid)
    print("  查询路径：%s" % path)
    for k in ("status", "state", "message", "tool", "model", "cost", "points_cost",
              "refund", "duration", "progress"):
        if data.get(k) is not None:
            print("  %-10s %s" % (k, str(data.get(k))[:200]))
    if urls:
        print("  音频：%s" % urls[0])
        for u in urls[1:5]:
            print("        %s" % u)
    if not data:
        print("  （返回里没有 data；原始返回前 400 字）")
        print("  " + txt[:400])
    else:
        print("  结果：%s" % json.dumps(data, ensure_ascii=False)[:800])
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
        what = e.get("taskId") or ((e.get("audioUrls") or [""])[0]) or \
            (e.get("error") or "")[:40] or "-"
        print("  %s  %-4s %-6s %-13s %-38s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            e.get("line") or "-", str(what)[:38],
            ("%s 点" % e.get("estimatedPoints")) if e.get("estimatedPoints") else "-"))
    if not out["entries"]:
        print("  （还没有记录；跑一次 speak / dialogue / scene 就有了）")
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 高保真语音台（8 个语音接口一个命令，走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/apps/%s/<code> · 查询 GET %s/api/v1/tasks/<taskId>"
               % (DEFAULT_HOST, APP, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = %.1f 元）"
                         % (DEFAULT_BUDGET, DEFAULT_BUDGET / 100.0))
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="8 条线 + 必填项 + 音色数（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("voices", help="音色库：ElevenLabs 67 / Gemini 3.8 70 / 2.5 Pro 30 / Omni 30（免费）",
                       allow_abbrev=False)
    p.add_argument("--line", choices=LINE_ORDER, help="只看这条线的音色")
    p.set_defaults(fn=cmd_voices)

    p = sub.add_parser("cost", help="先算钱：给下限（免费）", allow_abbrev=False)
    p.add_argument("--line", choices=LINE_ORDER, help="只看这条线")
    p.add_argument("--tasks", type=int, default=1, help="跑几条任务（默认 1）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 端点 / 价目（免费，默认零 POST）",
                       allow_abbrev=False)
    p.add_argument("--probe-post", action="store_true",
                   help="深探：对 8 个端点各打一次坏参数（每条冻 60 点后原路退回，净 0）")
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数（默认 90）")
    p.set_defaults(fn=cmd_doctor)

    def add_common(p):
        p.add_argument("--timeout", type=int, default=180, help="提交超时秒数（默认 180）")
        p.add_argument("--yes", action="store_true", help="确认真实建单")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("speak", help="单人配音（v2 / turbo）", allow_abbrev=False)
    p.add_argument("--line", choices=SINGLE_LINES, default="v2",
                   help="v2 = 多语言 V2（默认）/ turbo = Turbo 2.5")
    p.add_argument("--text", help="要念的台词（≤ 5000 字符）")
    p.add_argument("--text-file", help="从 UTF-8 文本文件读台词")
    p.add_argument("--voice", help="音色 ID 或名字（James / Arabella / …，见 voices）")
    p.add_argument("--speed", type=float, help="语速 0.7~1.2（默认 1.0）")
    p.add_argument("--style-level", type=float, help="风格夸张度 0~1（默认 0）")
    p.add_argument("--stability", type=float, help="稳定性 0~1（默认 0.5）")
    p.add_argument("--similarity", type=float, help="相似度提升 0~1（默认 0.75）")
    p.add_argument("--language-code", help="强制语言 ISO 639-1（只有 turbo 支持）")
    p.add_argument("--timestamps", action="store_true",
                   help="顺便要逐词时间戳（对齐字幕用）")
    p.add_argument("--previous-text", help="上一段文本，跨段连续用")
    p.add_argument("--next-text", help="下一段文本，跨段连续用")
    add_common(p)
    p.set_defaults(fn=cmd_speak)

    p = sub.add_parser("dialogue", help="多人对白（v3，每句自带音色）", allow_abbrev=False)
    p.add_argument("--turn", action="append", metavar="角色:台词",
                   help="重复给：--turn \"1: 你终于来了。\"")
    p.add_argument("--script", help="剧本文件（UTF-8，每行「角色: 台词」，# 是注释）")
    p.add_argument("--voices", action="append", metavar="角色=音色",
                   help="重复给：--voices \"1=James\" --voices \"2=Arabella\"")
    p.add_argument("--stability", type=float, choices=[0.0, 0.5, 1.0],
                   help="稳定性，只能是 0 / 0.5 / 1")
    p.add_argument("--language-code", help="语言代码（74 种，不填自动识别）")
    add_common(p)
    p.set_defaults(fn=cmd_dialogue)

    p = sub.add_parser("scene", help="场景对话（gemini38 / gemini38lite / gemini25pro）",
                       allow_abbrev=False)
    p.add_argument("--line", choices=SCENE_LINES, default="gemini38",
                   help="gemini38（默认）/ gemini38lite / gemini25pro")
    p.add_argument("--turn", action="append", metavar="角色:台词",
                   help="重复给；台词里可插 <laugh> <sigh> 这类语气标签")
    p.add_argument("--script", help="剧本文件（UTF-8，每行「角色: 台词」）")
    p.add_argument("--cast", action="append", metavar="角色=音色名",
                   help="重复给：--cast \"1=Kore\" --cast \"2=Fenrir\"")
    p.add_argument("--style-turn", action="append", metavar="角色=语气",
                   help="逐句语气（只 3.8）：--style-turn \"2=Low whisper, close mic\"")
    p.add_argument("--temperature", type=float, help="采样温度 0~2（默认 1）")
    p.add_argument("--filler-words", action="store_true",
                   help="两人对话时自动加语气词（只 3.8）")
    p.add_argument("--accent", help="口音（只 2.5 Pro，默认 Neutral）")
    p.add_argument("--pace", help="语速档（只 2.5 Pro：Natural / Rapid Fire / The Drift / Staccato）")
    p.add_argument("--emotion", help="情感（只 2.5 Pro：Whisper / Deadpan / Newscaster …）")
    p.add_argument("--scene", dest="scene_desc", help="场景描述（只 2.5 Pro）")
    p.add_argument("--sample-context", help="整体基调（只 2.5 Pro）")
    add_common(p)
    p.set_defaults(fn=cmd_scene)

    p = sub.add_parser("design", help="设计音色（omni：描述换音色）", allow_abbrev=False)
    p.add_argument("--name", help="音色名（≤ 210 字符）")
    p.add_argument("--audio-id", help="底子音色 id，30 个见 voices --line omni")
    p.add_argument("--example", help="示例台词（≤ 120 字符）")
    p.add_argument("--description", help="音色特征描述（≤ 20000 字符）")
    add_common(p)
    p.set_defaults(fn=cmd_design)

    p = sub.add_parser("character", help="造角色（character：图片 + 人设）",
                       allow_abbrev=False)
    p.add_argument("--image-url", action="append",
                   help="参考图地址，1~2 张（第 1 张头像，第 2 张全身）")
    p.add_argument("--description", help="角色描述（外观 / 身份 / 性格）")
    p.add_argument("--audio-id", action="append", dest="audio_ids",
                   help="关联的音色 id（可重复，来自 design 的产物）")
    p.add_argument("--character-name", help="角色名")
    add_common(p)
    p.set_defaults(fn=cmd_character)

    p = sub.add_parser("task", help="查任务（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
    p.set_defaults(fn=cmd_task)

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


FREE = ("cmd_catalog", "cmd_voices", "cmd_cost", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key, host = load_conf(a.key, a.host)
    fn_name = getattr(a.fn, "__name__", "")
    if not key and fn_name not in FREE:
        raise Fail("usage",
                   "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                   "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                   EXIT_USAGE)
    try:
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
    except Exception:                                             # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
