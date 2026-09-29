#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · HTML 转视频引擎 · 配音与旁白算力层（零第三方依赖）。

本包原来的能力边界里明写着「**不做素材生成**。配音、配乐、图片、图标这些要么你自己准备……」
——这个文件补上配音那一段，其余边界不变：出片仍然是 HTML 时间轴 + 无头 Chrome + FFmpeg，
这里只负责把**旁白稿**和**音轨**准备好，落到 `audio/` 里等你写进 `<audio>` 标签。

真实请求的端点（都在 api.a7w.cn 上）：

    旁白稿        POST https://api.a7w.cn/api/v1/chat/completions        （OpenAI 兼容协议）
    文字转语音    POST https://api.a7w.cn/api/v1/apps/voice_tts/tts       （同步，短文本）
    长文转语音    POST https://api.a7w.cn/api/v1/apps/voice_tts/tts_async （异步，自动轮询）
    音色列表      POST https://api.a7w.cn/api/v1/apps/voice_tts/list_voices
    语音转文字    POST https://api.a7w.cn/api/v1/apps/voice_tts/stt
    任务查询      GET  https://api.a7w.cn/api/v1/tasks/<task_id>

⚠️ 参数名坑：`voice_tts` 系列的音色参数叫 **`reference_id`**，不是 `voice_id`。
   本文件里的参数名全部来自 `python3 scripts/a7w.py schema voice_tts` 的实际输出，不是凭记忆写的。

用法
    # 1) 出旁白稿（按 cue 分段，直接能喂给 tts）
    python3 scripts/run.py narration --topic "新品上线第一天" --seconds 30 --out narration.md

    # 2) 把旁白稿合成配音，一段一个 mp3，外加 cues.json
    python3 scripts/run.py tts --file narration.md --outdir audio --voice <reference_id>

    # 3) 一步到位：写稿 + 配音 + 生成 cues.json
    python3 scripts/run.py dub --topic "新品上线第一天" --seconds 30 --outdir audio

    python3 scripts/run.py voices                  # 列出可用音色（免费）
    python3 scripts/run.py stt --audio audio/cue-01.mp3   # 复核念对了没有

配 Key（三种方式任选）
    python3 scripts/run.py ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx                    # Windows: set A7W_API_KEY=sk-xxxx
    在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（`scripts/a7w.py login --key sk-xxxx`）

落到时间轴上
    生成后 `audio/cues.json` 里每条 cue 有 `id` / `text` / `file` / `seconds`，
    `<audio>` 标签必须带 `id`（本包已知限制：混音器只挑 `audio[id][src]`，没 id 的音频
    不会被混进去，成片会**没声音且不报错**）。把 seconds 填进 clip 的 `data-duration` 即可。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
APP = "voice_tts"
API_TTS = "tts"
API_TTS_ASYNC = "tts_async"
API_VOICES = "list_voices"
API_STT = "stt"
SYNC_LIMIT = 500          # 同步 tts 的上限，超过自动切 tts_async
DEFAULT_MODEL = "deepseek-chat"
CUE_RE = re.compile(r"^##\s+(cue[-_]?\d+|\d+)\s*$", re.I)


class KitError(a7w.A7wError):
    """本包自己的可读错误。"""


# ---------------------------------------------------------------------------
# 大模型：旁白稿
# ---------------------------------------------------------------------------

def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.8,
         max_tokens=2048, key=None, timeout=180, retries=3):
    """调一次 https://api.a7w.cn/api/v1/chat/completions（OpenAI 兼容）。"""
    key = a7w.load_key(key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json",
               "Accept": "application/json"}

    last_exc = None
    for attempt in range(retries):
        req = urllib.request.Request(CHAT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            break
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (502, 503, 504) and attempt < retries - 1:
                last_exc = exc
                sys.stderr.write("上游 {}，{}s 后重试…\n".format(exc.code, 2 * (attempt + 1)))
                time.sleep(2 * (attempt + 1))
                continue
            try:
                msg = json.loads(text).get("msg") or text[:200]
            except ValueError:
                msg = text[:200]
            if exc.code == 401:
                raise KitError("鉴权失败（401）：Key 无效或已过期。\n" + str(msg))
            if exc.code == 402:
                raise KitError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            raise KitError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试…\n".format(
                    getattr(exc, "reason", exc), 2 * (attempt + 1)))
                time.sleep(2 * (attempt + 1))
                continue
    else:
        raise KitError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), retries, CHAT_URL))

    choices = payload.get("choices") or a7w.dig(payload, "data", "choices") or []
    if not choices:
        raise KitError("返回里没有 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:400]))
    msg = choices[0].get("message") or {}
    text = (msg.get("content") or "").strip() or (msg.get("reasoning_content") or "").strip()
    if not text:
        raise KitError("模型返回了空内容（推理类模型请调大 --max-tokens）")
    return text, (payload.get("usage") or a7w.dig(payload, "data", "usage") or {})


NARRATION_SYSTEM = """你是「三剪客」的视频旁白撰稿人。成片是用 HTML 时间轴逐帧渲染的，
所以你的稿子必须**按镜头分 cue**，每个 cue 就是一条独立的音轨。

输出格式（严格遵守，`## cue-NN` 这一行一个字都不能改，脚本靠它切音轨）：

# 旁白稿
## cue-01
<这一段的旁白文本，只写要念的字，不要写括号、不要写舞台提示、不要写时长>
## cue-02
<下一段>
……

## 时长建议
表格：cue | 镜头内容 | 建议秒数 | 累计秒数

硬性要求：
1. cue 总数 4–8 段，每段 8–40 字，念起来约 2–6 秒；中文口播按每秒 4–5 字估算。
2. 每段只讲一件事，段落之间要有推进关系——按「钩子 → 展开 → 证据 → 转折 → 收束」走。
3. 只写能念出口的话：不写「画面中」「如图所示」「点击下方」这种做不到的词，
   不写 emoji、不写 Markdown 加粗、不写书名号。
4. 总字数按用户给的目标秒数换算（每秒 4–5 字），不要超。
5. 不出现极限词与绝对化用语，不做疗效与收益承诺。
6. 除 `# 旁白稿` 与 `## 时长建议` 外，不要有别的标题。"""


# ---------------------------------------------------------------------------
# a7w 应用调用：TTS / 音色 / STT
# ---------------------------------------------------------------------------

def pick_audio(res):
    """在返回结构里找音频地址——上游字段名不完全一致，逐个试。"""
    for path in (("result", "audio_url"), ("result", "url"), ("audio_url",),
                 ("url",), ("result", "data", "audio_url"),
                 ("data", "audio_url"), ("data", "url"), ("output_url",)):
        v = a7w.dig(res, *path)
        if v:
            return v
    return None


def pick_text(res):
    """STT 的识别文本：可能是字符串，也可能挂在 text / result.text 上。"""
    if isinstance(res, str):
        return res
    for path in (("result", "text"), ("text",), ("result", "transcript"),
                 ("transcript",), ("data", "text"), ("result", "data", "text")):
        v = a7w.dig(res, *path)
        if isinstance(v, str) and v.strip():
            return v
    return None


def tts_one(text, out_path, voice=None, fmt="mp3", key=None, quiet=False):
    """合成一段配音并落盘。返回 (路径, 音频URL, usage)。长文自动走异步接口。"""
    body = {"text": text, "format": fmt}
    if voice:
        body["reference_id"] = voice          # ← 实测参数名，不是 voice_id
    api = API_TTS_ASYNC if len(text) > SYNC_LIMIT else API_TTS
    if not quiet:
        sys.stderr.write("  {} 字 → POST /api/v1/apps/{}/{}\n".format(len(text), APP, api))
    res = a7w.call(APP, api, body, key=key, quiet=quiet)
    url = pick_audio(res)
    if not url:
        raise KitError("没从返回里找到音频地址：{}".format(
            json.dumps(res, ensure_ascii=False)[:400]))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    a7w.save(url, str(out_path))
    usage = res.get("usage") if isinstance(res, dict) else None
    return str(out_path), url, (usage or {})


def probe_seconds(path):
    """有 ffprobe 就顺手读个时长，没有就返回 None（不把它变成硬依赖）。"""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=30)
        return round(float(out.stdout.strip()), 3)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------------
# 旁白稿解析
# ---------------------------------------------------------------------------

def parse_cues(text):
    """从旁白稿里抽出 [(cue_id, 文本)]。

    只认 `## cue-NN` 这种二级标题下的内容；碰到别的标题（比如「## 时长建议」）
    就停手，所以稿子末尾的时长表不会混进音轨里。
    """
    cues, cur, buf = [], None, []
    for raw in text.splitlines():
        line = raw.rstrip()
        m = CUE_RE.match(line.strip())
        if m:
            if cur and buf:
                cues.append((cur, " ".join(x.strip() for x in buf if x.strip())))
            cur, buf = m.group(1), []
            continue
        if line.startswith("#"):
            if cur and buf:
                cues.append((cur, " ".join(x.strip() for x in buf if x.strip())))
            cur, buf = None, []
            continue
        if cur is not None and line.strip():
            buf.append(line)
    if cur and buf:
        cues.append((cur, " ".join(x.strip() for x in buf if x.strip())))
    return [(cid, t) for cid, t in cues if t]


def norm_cue_id(cid, index):
    """cue-1 / cue_1 / 1 → cue-01，保证文件名排序稳定。"""
    digits = re.sub(r"\D", "", cid or "")
    return "cue-{:02d}".format(int(digits) if digits else index + 1)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_narration(a):
    seconds = a.seconds
    lo, hi = int(seconds * 4), int(seconds * 5)
    detail = ["目标成片时长：约 {} 秒".format(seconds),
              "对应旁白总字数：{}–{} 字（中文口播每秒 4–5 字）".format(lo, hi),
              "主题 / 内容：" + a.topic]
    if a.tone:
        detail.append("语气：" + a.tone)
    if a.audience:
        detail.append("受众：" + a.audience)
    if a.points:
        detail.append("必须讲到的点：" + a.points)
    if a.cues:
        detail.append("希望分 {} 段（cue 数）".format(a.cues))
    prompt = "写一段用于 HTML 视频成片的旁白稿。\n" + "\n".join(detail)
    sys.stderr.write("调用 {} · model={}\n".format(CHAT_URL, a.model))
    text, usage = chat(prompt, NARRATION_SYSTEM, model=a.model,
                       temperature=a.temperature, max_tokens=a.max_tokens, key=a.key)
    cues = parse_cues(text)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}（{} 段 cue）\n".format(a.out, len(cues)))
    if a.json:
        print(json.dumps({"ok": True, "out": a.out, "cues": len(cues),
                          "script": text, "model": a.model, "usage": usage},
                         ensure_ascii=False, indent=1))
    else:
        print(text)
    if not cues:
        sys.stderr.write("警告：没解析出 `## cue-NN` 段落，tts 子命令会吃不下这份稿子。\n")
    return 0


def cmd_tts(a):
    if a.file:
        try:
            src = Path(a.file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            sys.stderr.write("读不到旁白稿 {}：{}\n".format(a.file, exc))
            return 2
    else:
        src = (a.text or "").strip()
    if not src:
        sys.stderr.write("没有内容：给 --file 旁白稿，或用 --text 一段文字。\n")
        return 2

    cues = parse_cues(src)
    if not cues:
        # 没按 cue 分段：就把整篇当成一段
        cues = [("cue-01", " ".join(x.strip() for x in src.splitlines() if x.strip()))]
        sys.stderr.write("没有 `## cue-NN` 结构，按单段处理。\n")

    outdir = Path(a.outdir or "audio")
    outdir.mkdir(parents=True, exist_ok=True)
    manifest, total, fails = [], 0.0, 0

    for i, (cid, body) in enumerate(cues, 1):
        name = norm_cue_id(cid, i - 1)
        target = outdir / "{}.{}".format(name, a.format)
        sys.stderr.write("[{}/{}] {}\n".format(i, len(cues), name))
        try:
            path, url, usage = tts_one(body, target, voice=a.voice, fmt=a.format,
                                       key=a.key, quiet=a.quiet)
        except a7w.A7wError as exc:
            sys.stderr.write("  失败：{}\n".format(exc))
            fails += 1
            manifest.append({"id": name, "text": body, "file": None, "error": str(exc)})
            continue
        secs = a7w.dig(usage, "audio_seconds") or probe_seconds(path)
        manifest.append({
            "id": name, "text": body, "file": str(target), "url": url,
            "seconds": secs, "chars": len(body),
            "points_cost": a7w.dig(usage, "points_cost"),
        })
        if secs:
            total += float(secs)
        sys.stderr.write("  → {}{}\n".format(
            target, "  {:.2f}s".format(secs) if secs else ""))

    sheet = {
        "app": APP,
        "apis": {"sync": "/api/v1/apps/{}/{}".format(APP, API_TTS),
                 "async": "/api/v1/apps/{}/{}".format(APP, API_TTS_ASYNC)},
        "voice": a.voice,
        "format": a.format,
        "cues": manifest,
        "total_seconds": round(total, 3) or None,
        "failed": fails,
        "note": ("每条 cue 一个音频文件。写进 HTML 合成时，每个 <audio> 必须带 id（"
                 "混音器只挑 audio[id][src]，缺 id 会静默丢掉声音），"
                 "把 seconds 填进对应 clip 的 data-duration，注意时间窗左闭右开。"),
    }
    if not getattr(a, "no_cues_json", False):
        sheet_path = Path(a.cues_json) if a.cues_json else outdir / "cues.json"
        sheet_path.parent.mkdir(parents=True, exist_ok=True)
        sheet_path.write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
        sheet["cues_json"] = str(sheet_path)
        sys.stderr.write("音轨清单：{}\n".format(sheet_path))

    if a.json:
        print(json.dumps(sheet, ensure_ascii=False, indent=1))
    else:
        print("合成 {} 段，失败 {} 段，总时长 {}{}".format(
            len(manifest), fails,
            "{:.2f}s".format(total) if total else "未知",
            "（装 ffprobe 可自动填时长）" if not total else ""))
    return 1 if fails else 0


def cmd_dub(a):
    """写稿 → 配音 → 出 cues.json，一条命令。"""
    ns = argparse.Namespace(**vars(a))
    ns.out = a.script or "narration.md"
    ns.json = False
    rc = cmd_narration(ns)
    if rc != 0:
        return rc
    try:
        script = Path(ns.out).read_text(encoding="utf-8")
    except OSError as exc:
        sys.stderr.write("旁白稿没落盘：{}\n".format(exc))
        return 2
    cues = parse_cues(script)
    if not cues:
        sys.stderr.write("旁白稿里没有 `## cue-NN` 段落，无法分段配音。\n")
        return 2
    ts = argparse.Namespace(**vars(a))
    ts.file, ts.text = ns.out, None
    ts.format = a.format
    ts.quiet = a.quiet
    return cmd_tts(ts)


def cmd_voices(a):
    try:
        data = a7w.call(APP, API_VOICES, {"page_size": a.page_size}, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("拉音色列表失败：{}\n".format(exc))
        return 4
    items = data if isinstance(data, list) else (
        a7w.dig(data, "lists") or a7w.dig(data, "items") or a7w.dig(data, "data")
        or a7w.dig(data, "voices") or [])
    if not isinstance(items, list):
        items = []
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return 0
    print("共 {} 个音色（POST /api/v1/apps/{}/{}）\n".format(len(items), APP, API_VOICES))
    for it in items:
        rid = a7w.dig(it, "reference_id") or a7w.dig(it, "model_id") or a7w.dig(it, "id")
        title = a7w.dig(it, "title") or a7w.dig(it, "name") or "-"
        lang = a7w.dig(it, "language") or ""
        if isinstance(lang, list):
            lang = ",".join(str(x) for x in lang)
        print("  {:<34} {:<22} {}".format(str(rid or "-"), str(title), str(lang)))
    if not items:
        sys.stderr.write("当前账号没有自建音色；不传 --voice 就用平台默认音色（免费试）。\n")
    print("\n把 reference_id 传给：run.py tts --file narration.md --voice <reference_id>")
    return 0


def cmd_stt(a):
    body = {}
    if a.audio_url:
        body["audio_url"] = a.audio_url
    if a.language:
        body["language"] = a.language
    body["ignore_timestamps"] = not a.timestamps
    try:
        if a.audio:
            # 多段上传时字段是纯字符串，布尔要显式写成 true/false；
            # 文件字段名是 `audio`（不是 `file`）——与平台其它 STT 接入保持一致。
            up = dict(body)
            up["ignore_timestamps"] = "true" if not a.timestamps else "false"
            res = a7w.upload(APP, API_STT, up, file_field="audio",
                             file_path=a.audio, key=a.key, quiet=False)
        else:
            res = a7w.call(APP, API_STT, body, key=a.key, quiet=False)
    except a7w.A7wError as exc:
        sys.stderr.write("识别失败：{}\n".format(exc))
        return 4
    text = pick_text(res)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif text:
        print(text)
    else:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out and text:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    if not a.no_compare and a.expect:
        want = re.sub(r"\s+", "", a.expect)
        got = re.sub(r"\s+", "", text or "")
        same = want and (want in got or got in want)
        sys.stderr.write("与原文比对：{}\n".format("一致" if same else "有出入，人工听一遍"))
        return 0 if same else 1
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _common(p):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="文本模型，默认 {}（`scripts/a7w.py apps` 看全部）".format(DEFAULT_MODEL))
    p.add_argument("--key", help="临时指定 A7W API Key")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="HTML 转视频引擎 · 旁白稿与配音（走 api.a7w.cn）",
        epilog="端点：/api/v1/chat/completions · /api/v1/apps/voice_tts/tts · "
               "/api/v1/apps/voice_tts/tts_async · /api/v1/apps/voice_tts/list_voices · "
               "/api/v1/apps/voice_tts/stt")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("narration", help="按 cue 分段写旁白稿（大模型）")
    _common(p)
    p.add_argument("--topic", required=True, help="视频主题 / 要讲的内容")
    p.add_argument("--seconds", type=int, default=30, help="目标成片时长（秒），默认 30")
    p.add_argument("--cues", type=int, help="希望分几段（cue 数）")
    p.add_argument("--tone", help="语气，如 冷静克制 / 热情种草 / 悬念解说")
    p.add_argument("--audience", help="受众")
    p.add_argument("--points", help="必须讲到的点，逗号分隔")
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--max-tokens", type=int, default=2048, dest="max_tokens")
    p.add_argument("--out", help="旁白稿保存路径，推荐 narration.md")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_narration)

    p = sub.add_parser("tts", help="把旁白稿逐段合成配音（voice_tts）")
    p.add_argument("--file", help="旁白稿路径（含 `## cue-NN` 段）")
    p.add_argument("--text", help="直接给一段文字（没分段时按单段处理）")
    p.add_argument("--outdir", default="audio", help="音频输出目录，默认 audio/")
    p.add_argument("--voice", help="音色 reference_id（不传用平台默认音色）")
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus", "pcm"],
                   help="音频格式，默认 mp3")
    p.add_argument("--cues-json", dest="cues_json", default=None,
                   help="音轨清单路径，默认 <outdir>/cues.json")
    p.add_argument("--no-cues-json", dest="no_cues_json", action="store_true",
                   help="不写音轨清单")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--quiet", action="store_true", help="少打日志")
    p.add_argument("--json", action="store_true", help="JSON 输出清单")
    p.set_defaults(func=cmd_tts)

    p = sub.add_parser("dub", help="一条命令：写旁白稿 + 分段配音 + 出 cues.json")
    _common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--cues", type=int)
    p.add_argument("--tone")
    p.add_argument("--audience")
    p.add_argument("--points")
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--max-tokens", type=int, default=2048, dest="max_tokens")
    p.add_argument("--script", default="narration.md", help="旁白稿落盘路径")
    p.add_argument("--outdir", default="audio")
    p.add_argument("--voice")
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus", "pcm"])
    p.add_argument("--cues-json", dest="cues_json", default=None)
    p.add_argument("--no-cues-json", dest="no_cues_json", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_dub)

    p = sub.add_parser("voices", help="列出可用音色（免费）")
    p.add_argument("--page-size", type=int, default=20, dest="page_size")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("stt", help="语音转文字，复核配音念对了没有")
    p.add_argument("audio", nargs="?", help="本地音频文件")
    p.add_argument("--audio-url", dest="audio_url", help="音频 URL（与本地文件二选一）")
    p.add_argument("--language", help="识别语言，不传自动检测（中文填 zh）")
    p.add_argument("--timestamps", action="store_true", help="要精确时间戳（默认不要）")
    p.add_argument("--expect", help="期望的原文，用来做一致性比对")
    p.add_argument("--no-compare", action="store_true", dest="no_compare")
    p.add_argument("--out", help="把识别文本写到文件")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stt)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4


if __name__ == "__main__":
    sys.exit(main())
