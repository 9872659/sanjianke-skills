#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 批量调度（sanjianke-batch-runner）

1000 条任务排一队，4 路并发跑完；断了接着跑，失败自动重试，钱花到线就停。

## 它不产生内容

本包只管「把别人的任务按清单跑完」：每一行是一个已经决定好的提交请求（端点 + body + 预估点数），
本包负责排队、并发、轮询、重试、落盘、算钱、守预算。出图 / 出片 / 配音的参数与提示词，仍归各能力包。

## 清单长这样（JSONL，一行一个任务）

  {"id": "img-0001", "endpoint": "/api/v1/images/generations",
   "body": {"model": "gpt-image-2.6", "prompt": "……"}, "points": 6}
  {"id": "enh-0001", "endpoint": "/api/v1/video/viapi/enhance",
   "body": {"videoUrl": "https://oss.gpu.likeadmin.cn/openapi/…", "duration": 15}, "points": 225}

`id` 必须唯一；`points` 不给就按 catalog 的价目现算（按秒 × duration、按张 × n、按字 × 字数）。

## 三条花钱的线（2026-11-07 用 472 点换来的）

  GET  /api/v1/apps/<app>              命中通配计价，按该应用 flat 单价扣，sync 不退
  POST /api/v1/apps/<app>/query        应用层查询一次就是一次的钱
  POST /api/v1/apps/<app>/submit 缺参  先 reserve_sync 冻结，再校验，再退，钱包被短暂动过

所以本包的放行表只有 **POST 提交端点**：`/api/v1/video/…`、`/api/v1/images/…`、
`/api/v1/apps/<app>/{submit,create,generate/index}`、`/api/v1/apps/media_services_33/<code>`。
清单里写了别的路径（GET、/apps/<app> 裸路径、*/query、/api/v1/tasks），当场退 2，一个请求不发。

## 轮询只走免费查询

  GET /api/v1/tasks/<id>              通用任务视图        0 点
  GET /api/v1/video/viapi/result/<id> 视频后处理结果视图  0 点

应用层的 /query 一次一扣，本包**不自动轮询**：这类任务提交成功就记 submitted，
出片以后去对应能力包或 `sanjianke-billing` 的台账里取。

## 预算守卫

- 跑之前：清单预估合计 + 已花 > `--budget` → 退 5，一个请求都不发
- 跑之中：每条发出前比一次，累计要超线就停手、状态落盘，剩下的留给下次
- `--budget` 单位是「点」，1 元 = 100 点

## 断点续跑与中断安全

状态文件（默认 `<清单名>.state.json`）记录每条任务的 taskId / 状态 / 实扣点数，
每完成一条用「临时文件 + os.replace + fsync」原子写一次。Ctrl-C / SIGTERM 只置停止位，
在飞的任务收尾后落盘，退出码 130；重跑同一条命令自动跳过已完成的。

## 子命令

  catalog  可批量的提交端点 + 单价 + 轮询方式（免费，不出网）
  cost     清单报价：合计点数、按端点分组、预计耗时（免费，不出网）
  plan     清单体检：逐行校验 + 打印将发出的请求（免费，不出网）
  doctor   自检 Key / 余额 / 价目 / 查询路由 / 提交探针 + 流水前后比对（免费）
  upload   上传本地文件换平台托管地址（免费），给 videoUrl 用
  run      真正开跑（要 --yes，受 --budget 管）
  status   看断点状态：完成 / 已提交 / 失败 / 剩余（免费，不出网）

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --file batch.jsonl
  python3 scripts/run.py plan --file batch.jsonl
  python3 scripts/run.py doctor
  python3 scripts/run.py run --file batch.jsonl --concurrency 4 --retry 2 --yes
  python3 scripts/run.py status --file batch.jsonl
  python3 scripts/run.py run --file batch.jsonl --dry-run

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import mimetypes
import os
import re
import signal
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid

# ── GBK 编码兜底（2026-11-07 实测修复，全家族一致）──────────────────────────
# Windows 上 stdout 被管道 / 重定向时按本地编码（cp936）走，`√`/`×` 这类字符编不出来
# 就会 UnicodeEncodeError 崩掉；先加 errors='replace'，输出最多变 `?`，进程不崩。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
POINTS_PER_YUAN = 100
DEFAULT_BUDGET = 10000            # 点；默认 100 元
DEFAULT_CONCURRENCY = 4           # 保守值：先跑稳，再往上加
MAX_CONCURRENCY = 16
DEFAULT_RETRY = 2
DEFAULT_POLL = 5                  # 秒
DEFAULT_WAIT = 1800               # 单条任务最多等 30 分钟
DEFAULT_ETA = 45                  # 秒/条，报工期用
UPLOAD_PATH = API_PREFIX + "/upload"

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-batch-runner/%s" % VERSION

# ───────────────────────── 端点目录：只放行 POST 提交端点 ─────────────────────
# unit: per_second / per_image / per_char / per_call
# poll: tasks（通用任务视图）/ video（后处理结果视图）/ none（应用层，查询另计费）
VIDEO_TIERS = {
    "colorize":   ("视频校色 / 黑白上色", 9, "viapi"),
    "subtitle":   ("字幕擦除", 9, "viapi"),
    "segment":    ("人像抠像 / 绿幕", 9, "viapi"),
    "superres":   ("视频超分", 9, "viapi"),
    "enhance":    ("画质综合增强", 15, "viapi"),
    "superres2k": ("视频超分 2K", 15, "viapi"),
    "portrait":   ("人像增强", 18, "viapi"),
    "faceswap":   ("换脸 / 人脸融合", 20, "viapi"),
    "shot":       ("镜头检测", 20, "viapi"),
    "superres4k": ("视频超分 4K", 20, "viapi"),
    "cartoon":    ("人像卡通化", 24, "viapi"),
    "interp":     ("视频插帧", 25, "viapi"),
    "castcrew":   ("硬字幕 / 演职员表 OCR", 25, "viapi"),
    "delogo":     ("台标 / Logo 擦除", 25, "viapi"),
    "upscale":    ("视频放大", 30, "flat"),
    "restore":    ("视频修复（老片抢救）", 36, "flat"),
}

# 应用层提交端点：路径 → (名字, 点数, 附加)。点数为 None 的按实际结算，清单里写 points。
APP_SUBMITS = [
    (API_PREFIX + "/apps/nano_banana/submit", "nano-banana 出图", 72, {}),
    (API_PREFIX + "/apps/aigc_qwen_image/generate/index", "通义万相出图", 78, {}),
    (API_PREFIX + "/apps/aigc_qwen_image_pro/generate/index", "通义万相出图 Pro", 105, {}),
    (API_PREFIX + "/apps/aigc_photo_restore/generate/index", "老照片修复 1K", 105,
     {"rates": {"1K": 105, "2K": 203}}),
    (API_PREFIX + "/apps/aigc_wan_image/generate/index", "万相出图", 203, {}),
    (API_PREFIX + "/apps/dressing_diffusion/submit", "AI 换装", 200, {}),
    (API_PREFIX + "/apps/grok_video/submit", "Grok 视频生成", 300, {}),
    (API_PREFIX + "/apps/happy_horse/submit", "快乐马视频", 650, {}),
    (API_PREFIX + "/apps/mmaudio/submit", "MMAudio 自动配音", 495, {}),
    (API_PREFIX + "/apps/seedance/create", "Seedance 2.0 视频创作", 11000, {}),
    (API_PREFIX + "/apps/seedance/submit", "Seedance 提交", 11000, {}),
    (API_PREFIX + "/apps/seedsvc/submit", "角色修改 / AI 换脸", 220, {}),
    (API_PREFIX + "/apps/wan/submit", "通义万相视频创作", 800, {}),
    (API_PREFIX + "/apps/smart_clip/submit", "智能剪辑", 45, {}),
    (API_PREFIX + "/apps/pic_lipsync/submit", "图片对口型（保底 50 点）", 50,
     {"minPoints": 50, "note": "保底 50 点，实际按上游结算"}),
    (API_PREFIX + "/apps/action_transfer/submit", "动作迁移（预扣 300）", 300,
     {"note": "预扣 300 点，成片按秒结算，多冻的退回"}),
    (API_PREFIX + "/apps/person_replacement/submit", "人物替换（预扣 300）", 300,
     {"note": "预扣 300 点，成片按秒结算，多冻的退回"}),
    (API_PREFIX + "/apps/flashvsr/submit", "FlashVSR 视频超分", 10,
     {"unit": "per_second", "minPoints": 20, "note": "10 点/秒，单笔保底 20 点"}),
    (API_PREFIX + "/apps/full_video/submit", "一键成片", None,
     {"unit": "per_second", "rates": {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80},
      "note": "按分辨率乘秒数，默认 1080P"}),
    (API_PREFIX + "/apps/image_human/submit", "图片数字人", None,
     {"note": "按档位结算，清单里写 points"}),
    (API_PREFIX + "/apps/lipsync/submit", "视频对口型", None,
     {"note": "按上游结算，清单里写 points"}),
]

VOICE_SUBMITS = [
    (API_PREFIX + "/apps/voice_tts/tts_async", "语音合成·长文本", None,
     {"unit": "per_char", "perChar": 0.18}),
    (API_PREFIX + "/apps/voice_tts/tts_live", "语音合成·实时", None,
     {"unit": "per_char", "perChar": 0.18}),
    (API_PREFIX + "/apps/indextts/submit", "IndexTTS 配音", None,
     {"unit": "per_char", "perChar": 0.18}),
    (API_PREFIX + "/apps/voice_tts/clone_voice", "音色克隆", 600, {}),
]

# media_services_33：29 个音频接口，价目表里 fixed_price 全是 0.0000 占位，
# 单价按上游 ×3 结算，清单里写 points 最稳；查询走应用层 /query（另计费），默认不轮询。
AUDIO33 = [
    ("google_gemini_3_8_flash_lite_tts", "Gemini 3.8 Flash Lite 文生语音"),
    ("google_gemini_3_8_flash_tts", "Gemini 3.8 Flash 文生语音"),
    ("google_gemini_2_5_pro_tts", "Gemini 2.5 Pro 文生语音"),
    ("gemini_omni_audio", "Gemini Omni Audio 生语音"),
    ("gemini_omni_character", "Gemini Omni Character 生角色"),
    ("elevenlabs_text_to_dialogue_v3", "ElevenLabs 对话文生语音 V3"),
    ("elevenlabs_text_to_speech_multilingual_v2", "ElevenLabs 多语言 V2"),
    ("elevenlabs_text_to_speech_turbo_2_5", "ElevenLabs Turbo 2.5"),
    ("music_generate_voice", "Suno Voice 自建音色"),
    ("music_generate", "生成音乐"),
    ("music_recovery_audio", "恢复音频"),
    ("music_extend", "延长音乐"),
    ("music_sounds", "生成声音"),
    ("music_timestamped_lyrics", "带时间戳歌词"),
    ("music_check_voice", "Suno Voice 可用性检查"),
    ("music_generate_persona", "生成 Persona"),
    ("music_replace_section", "替换音乐分区"),
    ("music_generate_lyrics", "生成歌词"),
    ("music_boost_music_style", "提升音乐风格"),
    ("music_cover_generate", "生成音乐封面"),
    ("music_add_vocals", "添加人声"),
    ("music_separate_vocals", "人声乐器分离"),
    ("music_generate_midi_from_audio", "音频转 MIDI"),
    ("music_mashup", "生成混音音乐"),
    ("music_create_music_video", "创建音乐视频"),
    ("music_upload_and_extend_audio", "上传并扩展音乐"),
    ("music_upload_and_cover_audio", "上传并翻唱音乐"),
    ("music_add_instrumental", "添加伴奏"),
    ("music_convert_to_wav_format", "转 WAV"),
]

KIND_NAMES = {"video": "视频后处理", "image": "图片", "app": "应用", "voice": "语音",
              "audio": "音频 / 音乐"}
POLL_NAMES = {"tasks": "通用任务视图", "video": "后处理结果视图", "none": "不自动轮询"}

# 价目表里有、GET /api/v1/apps 目录里没有的 5 条历史路径：
# 账单上出现过（billing 的 path 翻译表里有），catalog 保留、可照常批量，
# doctor 只把它们报成「历史路径」计数，不判红。
LEGACY_APPS = {"aigc_photo_restore", "aigc_qwen_image", "aigc_qwen_image_pro",
               "aigc_wan_image", "indextts"}

CATALOG = {}


def _add(path, name, kind, unit="per_call", points=None, min_points=None, per_char=None,
         rates=None, poll="none", note="", app=None):
    CATALOG[path] = dict(path=path, name=name, kind=kind, unit=unit, points=points,
                         minPoints=min_points, perChar=per_char, rates=rates,
                         poll=poll, note=note, app=app)


for _tier, (_name, _pps, _route) in VIDEO_TIERS.items():
    _p = (API_PREFIX + "/video/" + _tier) if _route == "flat" else \
         (API_PREFIX + "/video/viapi/" + _tier)
    _add(_p, _name, "video", "per_second", _pps, poll="video",
         note="%d 点/秒，按 duration 估" % _pps)

_add(API_PREFIX + "/images/generations", "文生图（Images API）", "image", "per_image", 6,
     poll="tasks", note="6 点/张，按实际返回张数计费")
_add(API_PREFIX + "/images/edits", "图生图 / 改图", "image", "per_image", 6,
     poll="tasks", note="6 点/张，multipart")

for _p, _n, _pts, _extra in APP_SUBMITS:
    _add(_p, _n, "app", _extra.get("unit", "per_call"), _pts,
         min_points=_extra.get("minPoints"), rates=_extra.get("rates"),
         poll="none", note=_extra.get("note", ""), app=_p.split("/")[4])

for _p, _n, _pts, _extra in VOICE_SUBMITS:
    _add(_p, _n, "voice", _extra.get("unit", "per_call"), _pts,
         per_char=_extra.get("perChar"), poll="none", app="voice_tts")

for _code, _name in AUDIO33:
    _add(API_PREFIX + "/apps/media_services_33/" + _code, _name, "audio", "per_call",
         None, poll="none", app="media_services_33",
         note="价目表是 0.0000 占位，按上游 ×3 结算，写 points")

# 这些路径出现过，但一条都不许进清单 —— 命中就是真扣费或预冻结
FORBIDDEN_HINTS = (
    ("/query", "应用层查询一次一扣，结果等出片后去 billing 台账取"),
    ("/api/v1/apps/", "应用层裸路径（/apps/<app>）命中通配计价，走 submit 子路径"),
    ("/api/v1/tasks", "通用任务入口走 per_module 50 点，属于查询不属于提交"),
)

STOP = threading.Event()
RUN_FLAGS = {"interrupted": False, "budgetStop": False}


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ───────────────────────── 通用小工具 ─────────────────────────
def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                        # noqa: BLE001
        return None


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def fmt(n):
    """点数：整数不摆小数点，小数留两位。"""
    try:
        f = float(n)
    except Exception:                                        # noqa: BLE001
        return "-"
    if abs(f - round(f)) < 0.005:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def yuan(points):
    return round(float(points) / float(POINTS_PER_YUAN), 2)


def fmt_dur(sec):
    sec = int(max(0, sec))
    if sec < 60:
        return "%d 秒" % sec
    if sec < 3600:
        return "%d 分 %02d 秒" % (sec // 60, sec % 60)
    return "%d 小时 %02d 分" % (sec // 3600, (sec % 3600) // 60)


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
    if txt.lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s）" % st
    return (txt or "").replace("\n", " ")[:240]


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
        except Exception:                                    # noqa: BLE001
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
    except Exception as e:                                   # noqa: BLE001
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
    except Exception as e:                                   # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """上游对 videoUrl 的白名单（实测报错原文）。返回 (ok, 说明)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                        # noqa: BLE001
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


# ───────────────────────── 清单解析与报价 ─────────────────────────
def check_endpoint(ep, lineno, tid):
    if not ep:
        raise Fail("usage", "第 %d 行（%s）缺 endpoint" % (lineno, tid), EXIT_USAGE)
    if ep in CATALOG:
        return
    if ep.startswith("/api/v1/video/viapi/"):
        tier = ep.rsplit("/", 1)[-1]
        raise Fail("usage", "第 %d 行（%s）的档位 %s 不在放行表；可用档位见 catalog"
                   % (lineno, tid, tier), EXIT_USAGE)
    for pre, why in FORBIDDEN_HINTS:
        if ep.startswith(pre) or pre in ep:
            raise Fail("usage", "第 %d 行（%s）写的是 %s：%s。提交请用 catalog 里的端点。"
                       % (lineno, tid, ep, why), EXIT_USAGE)
    if ep.startswith("/api/v1/apps/"):
        raise Fail("usage", "第 %d 行（%s）的 %s 没进放行表；提交端点形如 "
                   "/api/v1/apps/<app>/submit 或 /api/v1/apps/media_services_33/<code>。"
                   % (lineno, tid, ep), EXIT_USAGE)
    raise Fail("usage", "第 %d 行（%s）的端点 %s 不在放行表（只放 POST 提交端点，见 catalog）"
               % (lineno, tid, ep), EXIT_USAGE)


def estimate_points(meta, task, body, lineno):
    """返回 (点数, 口径说明)。清单里写了 points 就以清单为准。"""
    if task.get("points") is not None:
        try:
            return float(task["points"]), "清单给定"
        except Exception:                                    # noqa: BLE001
            raise Fail("usage", "第 %d 行（%s）的 points 不是数字" % (lineno, task.get("id")),
                       EXIT_USAGE)
    unit = meta["unit"]
    if unit == "per_second":
        sec = body.get("duration")
        if sec is None:
            sec = task.get("seconds")
        try:
            sec = float(sec)
        except Exception:                                    # noqa: BLE001
            raise Fail("usage", "第 %d 行（%s）按秒计费，请在 body 里给 duration 或在这一行给 "
                       "seconds" % (lineno, task.get("id")), EXIT_USAGE)
        rates = meta.get("rates")
        if rates:
            res = str(body.get("resolution") or task.get("resolution") or "1080P").upper()
            rate = rates.get(res) or rates.get("1080P")
            pts = rate * sec
            basis = "%s 点/秒 × %s 秒（%s）" % (rate, fmt(sec), res)
        else:
            pts = float(meta["points"] or 0) * sec
            basis = "%s 点/秒 × %s 秒" % (fmt(meta["points"]), fmt(sec))
        if meta.get("minPoints"):
            pts = max(pts, float(meta["minPoints"]))
        return pts, basis
    if unit == "per_image":
        n = body.get("n") or task.get("count") or 1
        try:
            n = int(n)
        except Exception:                                    # noqa: BLE001
            raise Fail("usage", "第 %d 行（%s）的 n 不是整数" % (lineno, task.get("id")),
                       EXIT_USAGE)
        return float(meta["points"] or 0) * n, "%s 点/张 × %d 张" % (fmt(meta["points"]), n)
    if unit == "per_char":
        chars = task.get("chars")
        if chars is None:
            txt = body.get("text") or body.get("prompt") or ""
            chars = len(str(txt))
        try:
            chars = float(chars)
        except Exception:                                    # noqa: BLE001
            raise Fail("usage", "第 %d 行（%s）按字计费，请在清单里给 chars"
                       % (lineno, task.get("id")), EXIT_USAGE)
        if chars <= 0:
            raise Fail("usage", "第 %d 行（%s）按字计费，chars 要大于 0（或给 body.text）"
                       % (lineno, task.get("id")), EXIT_USAGE)
        return float(meta["perChar"] or 0) * chars, "%s 点/字 × %s 字" % (
            fmt(meta["perChar"]), fmt(chars))
    if meta.get("points") is None:
        raise Fail("usage", "第 %d 行（%s）的端点按实际结算、价目表里没有公开单价：请在这一行写 "
                   "\"points\": <预估点数>，预算守卫用它。" % (lineno, task.get("id")), EXIT_USAGE)
    return float(meta["points"]), "%s 点/次" % fmt(meta["points"])


def load_manifest(path, allow_any_url=False):
    if not path:
        raise Fail("usage", "必须给 --file（JSONL 清单，一行一个任务）", EXIT_USAGE)
    if not os.path.isfile(path):
        raise Fail("usage", "清单文件不存在：%s" % path, EXIT_USAGE)
    tasks, seen = [], {}
    with io.open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            try:
                obj = json.loads(s)
            except Exception:                                # noqa: BLE001
                raise Fail("usage", "第 %d 行不是合法 JSON：%s" % (lineno, s[:80]), EXIT_USAGE)
            if not isinstance(obj, dict):
                raise Fail("usage", "第 %d 行不是 JSON 对象" % lineno, EXIT_USAGE)
            tid = str(obj.get("id") or "").strip()
            if not tid:
                raise Fail("usage", "第 %d 行缺 id（每条任务要有一个唯一名字）" % lineno, EXIT_USAGE)
            if tid in seen:
                raise Fail("usage", "id 重复：%s（第 %d 行与第 %d 行）"
                           % (tid, seen[tid], lineno), EXIT_USAGE)
            seen[tid] = lineno
            ep = str(obj.get("endpoint") or "").strip()
            check_endpoint(ep, lineno, tid)
            body = obj.get("body")
            if body is None:
                body = {}
            if not isinstance(body, dict):
                raise Fail("usage", "第 %d 行（%s）的 body 要是 JSON 对象" % (lineno, tid),
                           EXIT_USAGE)
            vu = body.get("videoUrl") or body.get("video_url")
            if vu:
                ok, kind = url_allowed(str(vu))
                if not ok and not allow_any_url:
                    raise Fail("usage",
                               "第 %d 行（%s）的 videoUrl 不在平台白名单（%s）。三种可用写法：\n"
                               "  · 先上传再提交：python3 scripts/run.py upload --file 素材.mp4\n"
                               "  · 本站成片地址：https://vr.a7w.cn/result/xxx.mp4\n"
                               "  · 本站七牛：https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4"
                               % (lineno, tid, kind), EXIT_USAGE)
            meta = CATALOG[ep]
            pts, basis = estimate_points(meta, obj, body, lineno)
            poll = obj.get("poll") or meta["poll"]
            if poll not in ("tasks", "video", "none"):
                raise Fail("usage", "第 %d 行（%s）的 poll 只能是 tasks / video / none"
                           % (lineno, tid), EXIT_USAGE)
            tasks.append({"id": tid, "endpoint": ep, "body": body, "points": pts,
                          "basis": basis, "poll": poll, "kind": meta["kind"],
                          "path": meta["path"], "name": meta["name"],
                          "line": lineno, "note": obj.get("note") or ""})
    if not tasks:
        raise Fail("usage", "清单里一条任务都没有：%s" % path, EXIT_USAGE)
    return tasks


def group_tasks(tasks):
    rows = {}
    for t in tasks:
        r = rows.setdefault(t["endpoint"], {"endpoint": t["endpoint"], "name": t["name"],
                                            "kind": t["kind"], "count": 0, "points": 0.0})
        r["count"] += 1
        r["points"] += t["points"]
    return sorted(rows.values(), key=lambda r: (-r["points"], r["endpoint"]))


# ───────────────────────── 状态文件（原子写） ─────────────────────────
def atomic_write_json(path, obj):
    d = os.path.dirname(os.path.abspath(path)) or "."
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def state_path_for(a):
    if getattr(a, "state", None):
        return a.state
    return a.file + ".state.json"


def count_manifest_lines(path):
    """只数清单里有几行任务，不做校验。"""
    try:
        n = 0
        with io.open(path, encoding="utf-8") as fh:
            for raw in fh:
                s = raw.strip()
                if s and not s.startswith("#"):
                    n += 1
        return n
    except Exception:                                        # noqa: BLE001
        return None


def new_state(path, manifest):
    try:
        sha = hashlib.sha256(open(manifest, "rb").read()).hexdigest()
    except Exception:                                        # noqa: BLE001
        sha = ""
    return {"version": 1, "manifest": os.path.abspath(manifest), "manifestSha256": sha,
            "path": path, "createdAt": now(), "updatedAt": now(),
            "spent": 0.0, "budget": None, "tasks": {}}


def load_state(path, manifest):
    if not os.path.isfile(path):
        return new_state(path, manifest)
    try:
        st = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:                                   # noqa: BLE001
        raise Fail("usage", "状态文件读不出来（%s）：%s。换 --state 指一份新的，或把这个文件挪走。"
                   % (path, e), EXIT_USAGE)
    if not isinstance(st, dict) or not isinstance(st.get("tasks"), dict):
        raise Fail("usage", "状态文件格式不对：%s" % path, EXIT_USAGE)
    st["path"] = path
    st.setdefault("spent", 0.0)
    st.setdefault("tasks", {})
    # 上次在飞的那条可能已经建了任务，默认不重发，避免重复扣费
    for tid, rec in st["tasks"].items():
        if isinstance(rec, dict) and rec.get("status") == "running":
            rec["status"] = "unknown"
            rec["reason"] = "上次中断时正在提交，可能已经建了任务"
    return st


def save_state(st):
    st["updatedAt"] = now()
    atomic_write_json(st["path"], st)


# ───────────────────────── catalog / cost / plan ─────────────────────────
def cmd_catalog(a, key, host):
    rows = [dict(meta) for meta in CATALOG.values()]
    rows.sort(key=lambda m: (m["kind"], m["path"]))
    out = {"ok": True, "count": len(rows), "endpoints": rows,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "notes": ["只放行 POST 提交端点；GET /apps/<app>、*/query、/api/v1/tasks 不在表里",
                     "poll=tasks 走 GET /api/v1/tasks/<id>，poll=video 走 /video/viapi/result/<id>，都是 0 点",
                     "应用层任务默认不自动轮询：/query 每问一次扣一次"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 批量调度 —— 可批量的提交端点（%d 个）" % len(rows))
    print()
    print("  %s %s %s %s" % (pad("端点", 62), pad("能力", 30), pad("单价", 14), "轮询"))
    print("  " + "-" * 118)
    for kind in ("video", "image", "app", "voice", "audio"):
        print("  ── %s ──" % KIND_NAMES[kind])
        for m in rows:
            if m["kind"] != kind:
                continue
            if m["unit"] == "per_second" and m.get("rates"):
                price = "按分辨率 %s" % "/".join(
                    "%s=%s" % (k, fmt(v)) for k, v in sorted(m["rates"].items()))
            elif m["unit"] == "per_second":
                price = "%s 点/秒" % fmt(m["points"])
            elif m["unit"] == "per_image":
                price = "%s 点/张" % fmt(m["points"])
            elif m["unit"] == "per_char":
                price = "%s 点/字" % fmt(m["perChar"])
            elif m["points"] is None:
                price = "按实际（写 points）"
            else:
                price = "%s 点/次" % fmt(m["points"])
            print("  %s %s %s %s" % (pad(m["path"], 62),
                                     pad(m["name"] + (" · 历史路径"
                                                      if m.get("app") in LEGACY_APPS else ""),
                                         30),
                                     pad(price, 14), POLL_NAMES[m["poll"]]))
    print()
    print("  最便宜：视频校色 / 字幕擦除 / 抠像 9 点/秒（0.09 元/秒）；文生图 6 点/张（0.06 元）。")
    print("  1 元 = 100 点。清单里写 points 就以清单为准，catalog 只负责给默认价。")
    return 0


def cmd_cost(a, key, host):
    tasks = load_manifest(a.file, getattr(a, "allow_any_url", False))
    rows = group_tasks(tasks)
    total = sum(t["points"] for t in tasks)
    sec = (len(tasks) + max(1, a.concurrency) - 1) // max(1, a.concurrency) * a.eta_per_task
    over = total > a.budget
    out = {"ok": True, "tasks": len(tasks), "endpoints": len(rows),
           "totalPoints": round(total, 2), "yuan": yuan(total), "overBudget": over,
           "budget": a.budget, "concurrency": a.concurrency,
           "etaSeconds": sec, "eta": fmt_dur(sec),
           "groups": [{"endpoint": r["endpoint"], "name": r["name"], "count": r["count"],
                       "points": round(r["points"], 2)} for r in rows]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("清单报价 · %d 条任务 / %d 个端点" % (len(tasks), len(rows)))
    print("=" * 86)
    print("  %-56s %8s %12s" % ("端点", "条数", "点数"))
    print("  " + "-" * 82)
    for r in rows[:max(1, a.top)]:
        print("  %-56s %8d %12s" % (r["endpoint"], r["count"], fmt(r["points"])))
    if len(rows) > a.top:
        print("  … 其余 %d 个端点合计 %s 点" % (
            len(rows) - a.top, fmt(sum(r["points"] for r in rows[a.top:]))))
    print("  " + "-" * 82)
    print("  %-56s %8d %12s" % ("合计", len(tasks), fmt(total)))
    print("  " + "-" * 82)
    print("  = %s 点 = %s 元（1 元 = 100 点）" % (fmt(total), fmt(yuan(total))))
    print("  %d 并发 × %d 秒/条 ≈ %s" % (a.concurrency, a.eta_per_task, fmt_dur(sec)))
    if over:
        print("  ! 超过 --budget %s 点：真跑会退 5，一个请求都不发。报价本身 0 点。"
              % fmt(a.budget))
    else:
        print("  余量 %s 点（%s 元）。" % (fmt(a.budget - total), fmt(yuan(a.budget - total))))
    print("  本轮花费 0 点（本地算，不出网）。")
    return 0


def cmd_plan(a, key, host):
    tasks = load_manifest(a.file, getattr(a, "allow_any_url", False))
    total = sum(t["points"] for t in tasks)
    by_poll = {"tasks": 0, "video": 0, "none": 0}
    for t in tasks:
        by_poll[t["poll"]] = by_poll.get(t["poll"], 0) + 1
    shown = tasks[:max(1, a.limit)]
    out = {"ok": True, "dryRun": True, "tasks": len(tasks),
           "totalPoints": round(total, 2), "yuan": yuan(total),
           "byPoll": by_poll, "requests": [{"id": t["id"], "endpoint": t["endpoint"],
                                            "points": t["points"], "poll": t["poll"],
                                            "body": t["body"]} for t in shown]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("清单体检（不出网、不发请求）")
    print("  文件：%s" % a.file)
    print("  任务：%d 条 · 合计 %s 点 = %s 元" % (len(tasks), fmt(total), fmt(yuan(total))))
    print("  轮询：通用任务视图 %d 条 · 后处理结果视图 %d 条 · 不自动轮询 %d 条"
          % (by_poll["tasks"], by_poll["video"], by_poll["none"]))
    print()
    print("  将发出的请求（前 %d 条）：" % len(shown))
    for t in shown:
        b = json.dumps(t["body"], ensure_ascii=False)
        print("  [%s] POST %s" % (t["id"], t["endpoint"]))
        print("        %s" % (b[:150] + ("…" if len(b) > 150 else "")))
        print("        %s 点 · %s · %s" % (fmt(t["points"]), t["basis"],
                                          POLL_NAMES[t["poll"]]))
    print()
    print("  下一步：python3 scripts/run.py run --file %s --yes" % a.file)
    return 0


# ───────────────────────── doctor / upload ─────────────────────────
def _rule_price(pricing, path):
    rule = pricing.get(path) if isinstance(pricing, dict) else None
    if not isinstance(rule, dict):
        return None
    for k in ("perSecond", "cost"):
        if rule.get(k) is not None:
            return float(rule[k])
    return None


def cmd_doctor(a, key, host):
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "requests": [
            "GET /user/balance", "GET /user/balance/logs?limit=1",
            "GET /api/v1/pricing", "GET /api/v1/apps",
            "GET /api/v1/tasks/probe-no-such-task",
            "POST /api/v1/video/viapi/enhance {}",
            "POST /api/v1/video/viapi/shot {}",
            "POST /api/v1/video/restore {}",
            "GET /user/balance/logs?limit=1（跑完复采一次做比对）"],
            "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不检查、不扣费）")
        for ln in out["requests"]:
            print("  → %s" % ln)
        return 0

    checks = []

    def add(name, ok, detail):
        checks.append((name, bool(ok), detail))

    log_before = None
    try:
        st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
        d = jloads(txt) or {}
        add("Key + 余额接口", st == 200 and "available_points" in d,
            "HTTP %s · 可用 %s 点 · 冻结 %s 点"
            % (st, fmt(d.get("available_points") or 0), fmt(d.get("frozen") or 0)))
    except Fail as e:
        add("Key + 余额接口", False, e.message[:70])

    try:
        st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
        d = jloads(txt) or {}
        lg = (d.get("logs") or [{}])[0]
        log_before = (lg.get("at"), lg.get("points"), lg.get("reference"))
        add("流水基线（跑前最近一笔）", st == 200 and bool(log_before[0]),
            "%s · %s 点 · %s" % (time.strftime("%m-%d %H:%M:%S",
                                               time.localtime((log_before[0] or 0) / 1000.0)),
                                 fmt(log_before[1] or 0), (log_before[2] or "-")[:36]))
    except Fail as e:
        add("流水基线（跑前最近一笔）", False, e.message[:70])

    pricing = {}
    try:
        st, txt = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=40)
        pricing = jloads(txt) or {}
        rules = pricing.get("pricing") if isinstance(pricing.get("pricing"), dict) else {}
        drift = []
        for tier, (name, pps, route) in VIDEO_TIERS.items():
            path = (API_PREFIX + "/video/" + tier) if route == "flat" else \
                   (API_PREFIX + "/video/viapi/" + tier)
            live = _rule_price(rules, path)
            if live is None:
                drift.append("%s 无规则" % tier)
            elif abs(live - pps) > 0.001:
                drift.append("%s 本地 %s / 线上 %s" % (tier, pps, fmt(live)))
        add("价目表 /pricing（%d 条规则）" % len(rules), st == 200 and not drift,
            "HTTP %s · %s" % (st, "16 档全一致" if not drift else " / ".join(drift)[:90]))
    except Fail as e:
        add("价目表 /pricing", False, e.message[:70])

    try:
        st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=40)
        d = jloads(txt) or {}
        apps = d.get("data") if isinstance(d.get("data"), list) else []
        codes = set()
        apis = {}
        for x in apps:
            code = str(x.get("code") or "")
            codes.add(code)
            apis[code] = set(str(e.get("code") or "") for e in (x.get("apis") or []))
        want = set()
        for path in CATALOG:
            if path.startswith(API_PREFIX + "/apps/"):
                bits = path.split("/")
                want.add(bits[4])
        missing = sorted(want - codes - LEGACY_APPS)
        legacy = sorted(want & LEGACY_APPS)
        audio = apis.get("media_services_33") or set()
        add("应用目录 /apps（%d 应用）对得上 catalog" % len(apps),
            st == 200 and not missing and len(audio) == 29,
            "HTTP %s · %s · 音频 %d 个接口 · 历史路径 %d 条"
            % (st, "catalog 里的应用都在" if not missing else "缺 " + " ".join(missing),
               len(audio), len(legacy)))
    except Fail as e:
        add("应用目录 /apps", False, e.message[:70])

    try:
        st, txt = http_json("GET", host + API_PREFIX + "/tasks/probe-no-such-task", key,
                            timeout=40)
        d = jloads(txt) or {}
        add("通用任务查询 /tasks/<id>", st == 200 and d.get("code") == 0,
            "HTTP %s · %s" % (st, (d.get("msg") or "")[:40]))
    except Fail as e:
        add("通用任务查询 /tasks/<id>", False, e.message[:70])

    probes = [("视频后处理探针 enhance", "/api/v1/video/viapi/enhance", "empty_url"),
              ("视频后处理探针 shot", "/api/v1/video/viapi/shot", "empty_url"),
              ("视频修复探针 restore", "/api/v1/video/restore", "pixverse_empty_url")]
    for label, path, want in probes:
        try:
            st, txt = http_json("POST", host + path, key, {}, timeout=a.timeout)
            d = jloads(txt) or {}
            e = d.get("error") if isinstance(d.get("error"), dict) else {}
            code = e.get("code") or ""
            add(label + "（空 body → 400）", st == 400 and code == want,
                "HTTP %s %s" % (st, code or err_text(st, txt)[:50]))
        except Fail as e:
            add(label, False, e.message[:70])

    log_after = None
    try:
        st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
        d = jloads(txt) or {}
        lg = (d.get("logs") or [{}])[0]
        log_after = (lg.get("at"), lg.get("points"), lg.get("reference"))
        same = log_before is not None and log_after == log_before
        add("本轮 0 点（跑后最近一笔与跑前相同）", same,
            "跑前 %s / 跑后 %s · 流水共 %s 条"
            % (fmt((log_before or [0, 0])[1] or 0), fmt(log_after[1] or 0),
               fmt(d.get("total") or 0)))
    except Fail as e:
        add("本轮 0 点（跑后比对）", False, e.message[:70])

    out = {"ok": all(c[1] for c in checks), "estimatedPoints": 0, "actualPoints": 0,
           "catalogEndpoints": len(CATALOG),
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（只读 + 空 body 探针，任务 0 条、本轮花费 0 点）")
    print()
    for n, o, d in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 44), d))
    print()
    print("  端点：%d 条提交端点；轮询走 /tasks/<id> 与 /video/viapi/result/<id>，都是 0 点。"
          % len(CATALOG))
    print("  预算：--budget 单位是点（1 元 = 100 点），超线在发请求之前退 5。")
    print("  本轮花费 0 点：跑前跑后最近一笔流水完全一致。")
    return 0 if out["ok"] else EXIT_GATE


def cmd_upload(a, key, host):
    path = a.file
    if not path:
        raise Fail("usage", "必须给 --file（要上传的视频 / 图片路径）", EXIT_USAGE)
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
        print("  端点：POST %s（multipart/form-data，字段名 file）" % url)
        print("  文件：%s（%d 字节）" % (path, size))
        print("  价格：0 点（价目表 /api/v1/upload 规则 cost=0）")
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
    out = {"ok": True, "url": got, "path": data.get("path"), "size": data.get("size"),
           "mime": data.get("mime_type"), "hostKind": kind, "urlAllowed": ok_url,
           "elapsed": round(dt, 1), "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（%.1fs，0 点）" % dt)
    print("  地址：%s" % got)
    print("  归属：%s（白名单内，可直接写进清单的 body.videoUrl）" % kind)
    return 0


# ───────────────────────── 状态 ─────────────────────────
def cmd_status(a, key, host):
    if not a.file and not a.state:
        raise Fail("usage", "给 --file（清单）或 --state（状态文件）", EXIT_USAGE)
    if not a.file:
        a.file = a.state[:-len(".state.json")] if a.state.endswith(".state.json") else a.state
    path = state_path_for(a)
    if not os.path.isfile(path):
        out = {"ok": True, "state": path, "exists": False, "counts": {}, "tasks": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("还没有状态文件：%s" % path)
        print("  先跑：python3 scripts/run.py plan --file %s" % a.file)
        return 0
    st = load_state(path, a.file)
    tasks = st["tasks"]
    counts = {}
    for rec in tasks.values():
        k = rec.get("status") or "pending"
        counts[k] = counts.get(k, 0) + 1
    total = len(tasks)
    in_manifest = count_manifest_lines(a.file) if os.path.isfile(a.file) else None
    not_started = (in_manifest - total) if in_manifest is not None else 0
    failed = [{"id": k, "error": v.get("error"), "attempts": v.get("attempts"),
               "taskId": v.get("taskId")} for k, v in tasks.items()
              if v.get("status") == "failed"]
    out = {"ok": True, "state": path, "exists": True, "spentPoints": round(st["spent"], 2),
           "counts": counts, "tasks": total, "manifestTasks": in_manifest,
           "notStarted": max(0, not_started), "failed": failed[:20],
           "updatedAt": st.get("updatedAt")}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("断点状态 · %s" % path)
    print("  清单：%s" % st.get("manifest"))
    print("  落盘任务：%d 条 · 已花 %s 点 · 更新于 %s"
          % (total, fmt(st["spent"]), st.get("updatedAt")))
    if in_manifest is not None:
        print("  清单共 %d 条 · 已落盘 %d 条 · 未开始 %d 条"
              % (in_manifest, total, max(0, not_started)))
    print()
    for k in ("done", "submitted", "failed", "unknown", "running", "pending"):
        if counts.get(k):
            print("  %-10s %d 条" % (k, counts[k]))
    rest = counts.get("unknown", 0) + counts.get("running", 0) + counts.get("pending", 0)
    if rest:
        print()
        print("  还差 %d 条；重跑同一条 run 命令会从断点接着跑。" % rest)
        if counts.get("unknown"):
            print("  其中 %d 条是上次中断时在飞的（可能已建任务）：先核对 billing 台账，"
                  "再决定加 --retry-failed 补跑。" % counts["unknown"])
    if failed:
        print()
        print("  失败明细（前 %d 条）：" % len(out["failed"]))
        for f in out["failed"]:
            print("    %-22s %s" % (f["id"], (f.get("error") or "")[:80]))
    print()
    print("  本轮花费 0 点（只读本地状态文件）。")
    return 0


# ───────────────────────── run ─────────────────────────
SUCCESS_STATES = ("completed", "complete", "succeeded", "success", "done", "finished",
                  "partial_success")
FAIL_STATES = ("failed", "fail", "error", "cancelled", "canceled", "timeout", "expired",
               "rejected")


def unwrap(d):
    if isinstance(d, dict) and isinstance(d.get("data"), dict):
        return d["data"]
    return d if isinstance(d, dict) else {}


def status_of(d):
    b = unwrap(d)
    for k in ("status", "state", "task_status", "taskStatus"):
        if b.get(k):
            return str(b[k]).strip().lower()
    return ""


def task_id_of(d):
    b = unwrap(d)
    for k in ("taskId", "task_id", "taskNo", "jobId", "id"):
        if b.get(k):
            return str(b[k])
    return None


def task_cost_of(d):
    b = unwrap(d)
    for k in ("cost", "points", "pointsCost", "points_cost"):
        if b.get(k) is not None:
            try:
                return float(b[k])
            except Exception:                                # noqa: BLE001
                pass
    u = b.get("usage") if isinstance(b.get("usage"), dict) else {}
    if u.get("points_cost") is not None:
        try:
            return float(u["points_cost"])
        except Exception:                                    # noqa: BLE001
            pass
    return None


def poll_path(task, task_id):
    if task["poll"] == "video":
        if task["endpoint"].endswith("/restore"):
            return API_PREFIX + "/video/restore/" + task_id
        return API_PREFIX + "/video/viapi/result/" + task_id
    return API_PREFIX + "/tasks/" + task_id


def poll_one(a, key, host, task, task_id):
    """返回 (状态, 点数, 说明)。只打免费查询视图。"""
    path = poll_path(task, task_id)
    deadline = time.time() + a.wait
    misses = 0
    last = ""
    while time.time() < deadline:
        if STOP.is_set():
            return "submitted", None, "收到停止信号，已提交未等结果"
        try:
            st, txt = http_json("GET", host + path, key, timeout=40)
        except Fail as e:
            last = e.message
            STOP.wait(a.poll_interval)
            continue
        d = jloads(txt) or {}
        s = status_of(d)
        if s in SUCCESS_STATES:
            return "done", task_cost_of(d), "查询 %s" % path
        if s in FAIL_STATES:
            return "failed", task_cost_of(d), "任务状态 %s" % s
        miss = (st == 404) or (st == 200 and d.get("code") == 0
                               and not unwrap(d) and "不存在" in str(d.get("msg") or ""))
        if miss:
            misses += 1
            last = "查询说任务不存在（%d 次）" % misses
            if misses >= 6:
                return "submitted", None, "查询视图还没建，已提交（交给 billing 台账核对）"
        else:
            misses = 0
            last = "状态 %s" % (s or "未知")
        STOP.wait(a.poll_interval)
    return "submitted", None, "等了 %s 还没出结果，已提交：%s" % (fmt_dur(a.wait), last)


def run_one(a, key, host, task, st, lock, done_box, t0):
    if STOP.is_set():
        return
    with lock:
        if st["spent"] + task["points"] > a.budget + 1e-9:
            RUN_FLAGS["budgetStop"] = True
            STOP.set()
            return
        rec = st["tasks"].setdefault(task["id"], {})
        rec["status"] = "running"
        rec["attempts"] = int(rec.get("attempts") or 0) + 1
        rec["points"] = round(task["points"], 2)
        rec["endpoint"] = task["endpoint"]
        save_state(st)

    task_id, resp, http_code, err = None, None, 0, None
    for attempt in range(a.retry + 1):
        if STOP.is_set():
            break
        try:
            http_code, txt = http_json("POST", host + task["endpoint"], key, task["body"],
                                       timeout=a.timeout)
        except Fail as e:
            http_code, txt = 0, ""
            err = e.message
            if attempt < a.retry:
                STOP.wait(min(30, 2 * (2 ** attempt)))
            continue
        d = jloads(txt) or {}
        task_id = task_id_of(d)
        if 200 <= http_code < 300 and task_id:
            resp = d
            err = None
            break
        err = "HTTP %s %s" % (http_code, err_text(http_code, txt))
        if http_code in (400, 401, 402, 403, 404, 409, 422):
            break
        if attempt < a.retry:
            STOP.wait(min(30, 2 * (2 ** attempt)))

    if task_id and resp is not None:
        cost = task_cost_of(resp)
        if task["poll"] == "none":
            final, poll_cost, why = "submitted", None, "应用层查询另计费，不自动轮询"
        else:
            final, poll_cost, why = poll_one(a, key, host, task, task_id)
            cost = poll_cost if poll_cost is not None else cost
        if cost is None:
            cost = task["points"]
    elif STOP.is_set():
        final, cost, why = "unknown", 0.0, "收到停止信号时正在提交，结果未知（可能已建任务）"
    else:
        final, cost, why = "failed", 0.0, (err or "没有拿到 taskId")

    with lock:
        rec = st["tasks"].setdefault(task["id"], {})
        rec["status"] = final
        rec["http"] = http_code
        rec["taskId"] = task_id
        rec["points"] = round(float(cost or 0), 2)
        rec["estimatedPoints"] = round(task["points"], 2)
        rec["why"] = why
        rec["at"] = now()
        if final in ("failed", "unknown"):
            rec["error"] = why
        else:
            rec.pop("error", None)
        st["spent"] = round(st["spent"] + float(cost or 0), 2)
        save_state(st)
        done_box["finished"] += 1
        idx = done_box["finished"]
        done_box["counts"][final] = done_box["counts"].get(final, 0) + 1
        elapsed = max(0.001, time.time() - t0)
        rate = idx / elapsed * 60.0
        total = done_box["total"]
        eta = (total - idx) / rate * 60.0 if rate > 0 else 0
        say("[%d/%d] %5.1f%% · 完成 %d · 已提交 %d · 失败 %d · 已用 %s 点 · "
            "%s 条/分 · 剩余 %s"
            % (idx, total, idx * 100.0 / max(1, total), done_box["counts"].get("done", 0),
               done_box["counts"].get("submitted", 0), done_box["counts"].get("failed", 0),
               fmt(st["spent"]), "%.1f" % rate, fmt_dur(eta)))


def _sig(signum, frame):                                     # noqa: ARG001
    RUN_FLAGS["interrupted"] = True
    STOP.set()


def _should_run(task, rec, a):
    s = (rec or {}).get("status")
    if s in ("done", "submitted"):
        return False
    if s in ("failed", "unknown"):
        return bool(a.retry_failed)
    return True


def cmd_run(a, key, host):
    tasks = load_manifest(a.file, a.allow_any_url)
    path = state_path_for(a)
    st = load_state(path, a.file)
    st["budget"] = a.budget

    todo = [t for t in tasks if _should_run(t, st["tasks"].get(t["id"]), a)]
    skipped = len(tasks) - len(todo)
    remaining_pts = sum(t["points"] for t in todo)
    projected = st["spent"] + remaining_pts

    if not todo:
        left = [t for t in tasks
                if (st["tasks"].get(t["id"]) or {}).get("status") in ("failed", "unknown")]
        code = EXIT_CALL if left else 0
        out = {"ok": code == 0, "done": code == 0, "tasks": len(tasks), "skipped": skipped,
               "spentPoints": round(st["spent"], 2), "state": path,
               "counts": {"failed": len(left)}}
        if code != 0:
            out["exit"] = code
            out["error"] = {"kind": "call",
                            "message": "%d 条是失败 / 中断在飞状态，补跑加 --retry-failed。"
                                       % len(left)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return code
        if code == 0:
            print("全部跑完了：%d 条，已花 %s 点，状态在 %s"
                  % (len(tasks), fmt(st["spent"]), path))
        else:
            print("还剩 %d 条失败 / 中断在飞（跳过 %d 条已完成）· 已花 %s 点"
                  % (len(left), skipped, fmt(st["spent"])))
            print("  补跑：python3 scripts/run.py run --file %s --retry-failed --yes" % a.file)
        return code

    if projected > a.budget + 1e-9:
        raise Fail("budget",
                   "清单还有 %d 条、%s 点，加上已花 %s 点 = %s 点，超过 --budget %s 点。"
                   "一个请求都没发。调大 --budget 或先跑一部分。"
                   % (len(todo), fmt(remaining_pts), fmt(st["spent"]), fmt(projected),
                      fmt(a.budget)), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这次要发 %d 条提交请求（跳过已完成 / 已提交 %d 条），预计 %s 点（%s 元）。"
                   "确认请加 --yes。"
                   % (len(todo), skipped, fmt(remaining_pts), fmt(yuan(remaining_pts))),
                   EXIT_CONFIRM)

    if a.dry_run:
        shown = todo[:max(1, a.limit)]
        out = {"ok": True, "dryRun": True, "state": path, "tasks": len(tasks),
               "pending": len(todo), "skipped": skipped,
               "estimatedPoints": round(remaining_pts, 2), "yuan": yuan(remaining_pts),
               "spentPoints": round(st["spent"], 2),
               "requests": [{"id": t["id"], "endpoint": t["endpoint"], "points": t["points"],
                             "poll": t["poll"], "body": t["body"]} for t in shown],
               "pollPaths": ["(不轮询：应用层查询另计费)" if t["poll"] == "none"
                             else poll_path(t, "<taskId>") for t in shown]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  清单：%s（%d 条）" % (a.file, len(tasks)))
        print("  待跑：%d 条 · 跳过：%d 条 · 预计 %s 点（%s 元）"
              % (len(todo), skipped, fmt(remaining_pts), fmt(yuan(remaining_pts))))
        print("  状态：%s" % path)
        print()
        for t in shown:
            print("  POST %s" % t["endpoint"])
            print("    %s · %s 点 · %s" % (t["id"], fmt(t["points"]), t["basis"]))
            print("    轮询 %s" % ("（不自动轮询，应用层查询另计费）" if t["poll"] == "none"
                                  else poll_path(t, "<taskId>")))
        return 0

    # Ctrl-C（SIGINT）、kill（SIGTERM）、Windows 的 Ctrl-Break（SIGBREAK）都只置停止位
    for _name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        _sig_no = getattr(signal, _name, None)
        if _sig_no is None:
            continue
        try:
            signal.signal(_sig_no, _sig)
        except Exception:                                    # noqa: BLE001
            pass

    total = len(todo)
    done_box = {"finished": 0, "total": total, "counts": {}}
    lock = threading.Lock()
    t0 = time.time()
    say("开跑：%d 条待跑（共 %d 条，跳过 %d 条）· %d 并发 · 预算 %s 点 · 状态 %s"
        % (total, len(tasks), skipped, a.concurrency, fmt(a.budget), path))

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        futs = [ex.submit(run_one, a, key, host, t, st, lock, done_box, t0) for t in todo]
        for f in concurrent.futures.as_completed(futs):
            try:
                f.result()
            except Fail as e:
                say("  单条异常：%s" % e.message[:120])
            except Exception as e:                           # noqa: BLE001
                say("  单条异常：%s: %s" % (type(e).__name__, e))

    with lock:
        save_state(st)
    elapsed = time.time() - t0
    counts = done_box["counts"]
    failed = counts.get("failed", 0)
    pending_left = sum(1 for t in tasks
                       if (st["tasks"].get(t["id"]) or {}).get("status") not in
                       ("done", "submitted", "failed", "unknown"))
    if RUN_FLAGS["budgetStop"]:
        code = EXIT_BUDGET
        msg = ("累计已花 %s 点，再发就过 --budget %s 点，停手了；状态已落盘，"
               "重跑接着跑剩下的。" % (fmt(st["spent"]), fmt(a.budget)))
    elif RUN_FLAGS["interrupted"]:
        code = 130
        msg = "收到中断信号；在飞的任务已收尾，状态已落盘，重跑接着跑。"
    elif failed:
        code = EXIT_CALL
        msg = "%d 条失败（状态已落盘，重跑只补失败的）。" % failed
    else:
        code = 0
        msg = ""

    out = {"ok": code == 0, "state": path, "tasks": len(tasks), "ran": done_box["finished"],
           "skipped": skipped, "counts": counts, "pendingLeft": pending_left,
           "spentPoints": round(st["spent"], 2), "budget": a.budget,
           "elapsed": round(elapsed, 1), "elapsedText": fmt_dur(elapsed),
           "concurrency": a.concurrency, "report": None}
    if a.report:
        out["report"] = write_report(a, st, tasks, out)
    if code != 0:
        out["exit"] = code
        out["error"] = {"kind": "budget" if code == EXIT_BUDGET else
                        ("interrupt" if code == 130 else "call"), "message": msg}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return code

    print("跑完一轮 · %s" % fmt_dur(elapsed))
    print("  完成 %d · 已提交 %d · 失败 %d · 本轮发了 %d 条"
          % (counts.get("done", 0), counts.get("submitted", 0), failed,
             done_box["finished"]))
    print("  已花 %s 点（%s 元）· 预算余量 %s 点 · 还剩 %d 条"
          % (fmt(st["spent"]), fmt(yuan(st["spent"])),
             fmt(max(0.0, a.budget - st["spent"])), pending_left))
    print("  状态：%s" % path)
    if out["report"]:
        print("  报告：%s" % out["report"])
    print()
    if msg:
        print("  %s" % msg)
    print("  下一步：python3 scripts/run.py status --file %s" % a.file)
    return code


def write_report(a, st, tasks, summary):
    base = os.path.splitext(os.path.basename(a.file))[0]
    outdir = a.report
    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    rows = []
    for t in tasks:
        rec = st["tasks"].get(t["id"]) or {}
        rows.append({"id": t["id"], "endpoint": t["endpoint"], "status": rec.get("status"),
                     "taskId": rec.get("taskId"), "points": rec.get("points"),
                     "estimatedPoints": t["points"], "error": rec.get("error"),
                     "at": rec.get("at")})
    res = os.path.join(outdir, base + ".result.json")
    atomic_write_json(res, {"summary": summary, "state": st["path"], "rows": rows})
    fail = os.path.join(outdir, base + ".failed.jsonl")
    with io.open(fail, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            if r["status"] == "failed":
                f.write(json.dumps({"id": r["id"], "endpoint": r["endpoint"],
                                    "error": r["error"]}, ensure_ascii=False) + "\n")
    return res


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 批量调度：1000 条任务排队跑完，断点续跑 / 失败重试 / 预算守卫",
        epilog="端点：POST %s/api/v1/video/viapi/<tier> · POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/<app>/submit · GET %s/api/v1/tasks/<taskId>（免费轮询）"
               % ((DEFAULT_HOST,) * 4),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 100 元；超线在发请求前退 5）"
                         % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="可批量提交端点 + 单价 + 轮询方式（免费，不出网）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="清单报价：合计点数 + 分组 + 预计耗时（免费，不出网）",
                       allow_abbrev=False)
    p.add_argument("--file", help="JSONL 清单路径（一行一个任务）")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help="并发数（默认 %d，报工期用）" % DEFAULT_CONCURRENCY)
    p.add_argument("--eta-per-task", type=int, default=DEFAULT_ETA,
                   help="每条任务估多少秒（默认 %d）" % DEFAULT_ETA)
    p.add_argument("--top", type=int, default=10, help="按点数显示前 N 个端点（默认 10）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过 videoUrl 白名单本地预检（交给上游判断）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="清单体检：逐行校验 + 打印请求（免费，不出网）",
                       allow_abbrev=False)
    p.add_argument("--file", help="JSONL 清单路径")
    p.add_argument("--limit", type=int, default=5, help="打印前几条（默认 5）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过 videoUrl 白名单本地预检")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("doctor", help="自检 Key / 余额 / 价目 / 查询 / 提交探针（免费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=60, help="单次探针超时秒数（默认 60）")
    p.add_argument("--dry-run", action="store_true", help="只打印探针清单，不发请求")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="上传本地文件换平台托管地址（免费，0 点）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径（单文件 512 MB 以内）")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("run", help="开跑：并发 / 重试 / 断点 / 预算守卫（要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--file", help="JSONL 清单路径（一行一个任务）")
    p.add_argument("--state", help="状态文件路径（默认 <清单>.state.json）")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help="并发数（默认 %d，最大 %d）" % (DEFAULT_CONCURRENCY, MAX_CONCURRENCY))
    p.add_argument("--retry", type=int, default=DEFAULT_RETRY,
                   help="单条提交失败重试几次（默认 %d，退避 2s/4s/8s…）" % DEFAULT_RETRY)
    p.add_argument("--retry-failed", action="store_true",
                   help="把上次失败 / 中断在飞的任务也补跑（先核对台账）")
    p.add_argument("--poll-interval", type=int, default=DEFAULT_POLL,
                   help="轮询间隔秒数（默认 %d，查询免费）" % DEFAULT_POLL)
    p.add_argument("--wait", type=int, default=DEFAULT_WAIT,
                   help="单条任务最多等多少秒（默认 %d）" % DEFAULT_WAIT)
    p.add_argument("--timeout", type=int, default=120, help="单次提交超时秒数（默认 120）")
    p.add_argument("--limit", type=int, default=5, help="干跑打印前几条（默认 5）")
    p.add_argument("--report", help="把结果写成 <清单>.result.json + <清单>.failed.jsonl 的目录")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过 videoUrl 白名单本地预检")
    p.add_argument("--yes", action="store_true", help="确认真实提交（要花钱）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("status", help="看断点状态：完成 / 已提交 / 失败 / 剩余（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="JSONL 清单路径（用来推状态文件位置）")
    p.add_argument("--state", help="直接指定状态文件")
    p.set_defaults(fn=cmd_status)

    # 全局选项写在子命令前后都可以：每个子 parser 补一份，default=SUPPRESS 不覆盖父级
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_status")


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
        _conc = getattr(a, "concurrency", DEFAULT_CONCURRENCY)
        if _conc is not None and not (1 <= int(_conc) <= MAX_CONCURRENCY):
            raise Fail("usage", "--concurrency 取 1~%d（默认 %d）"
                       % (MAX_CONCURRENCY, DEFAULT_CONCURRENCY), EXIT_USAGE)
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        need_key = fn_name not in FREE and not getattr(a, "dry_run", False)
        if need_key and not key:
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
