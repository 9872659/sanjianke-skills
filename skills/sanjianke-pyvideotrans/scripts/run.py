#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频转写 + 可选大模型翻译（零安装版的「第一步」）。

先说清楚这个脚本覆盖到哪里，因为 pyvideotrans 原本是四道工序：
    识别 → 翻译 → 配音 → 合回画面

    · 本脚本覆盖**第一道工序**：`run.py 视频.mp4 --lang zh` 先转写生成源语言 SRT。
    · **平台没有翻译接口**（api.a7w.cn 上没有通用翻译 app）。所以第二道工序
      「翻译」需要你自己接：本脚本给了 `--translate` 作为**可选的显式开关**，
      它只调用**你自己的** OpenAI 兼容接口或 DeepL，平台不参与。
      （想用大模型翻译，填 --api-base / --api-key / --model 即可；不填就不翻译。）
    · 第三、四道工序（多角色配音、音画合成）平台与这个脚本都不做。
      配音可以另配 `voice_tts/tts`，合成需要本地 ffmpeg。

用本项目原本跑法（本地 Whisper + 本地翻译 + 本地 TTS），下面是零安装替代路线的
第一段，专治「只想先拿到字幕」这件事。

用法
    python3 run.py 视频.mp4 --lang zh                  # 转写并生成 视频.srt
    python3 run.py 视频.mp4 --lang zh --transcript      # 只打印文稿，不出 SRT
    python3 run.py 视频.mp4 --lang zh -o 成片.srt       # 指定 SRT 落点
    python3 run.py 视频.mp4 --url https://x/v.mp4       # 用公网媒体（免上传）

    # 可选：转写完顺手用你自己的大模型接口翻一版双语字幕（平台不提供翻译）
    python3 run.py 视频.mp4 --lang zh --translate \
        --api-base https://api.deepseek.com/v1 --api-key sk-xxx --model deepseek-chat

第一次使用需要配 a7w Key（三种方式任选）：
    python3 run.py 视频.mp4 --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

计费：转写走 `voice_tts/stt`，按次 40 点（实测值，以平台实时价为准）。
      `--translate` 走你自己的接口，费用与配额由那家算，平台不参与。
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
API = "stt"
MEDIA_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
             ".mp4", ".mov", ".mkv", ".webm", ".avi", ".ts", ".flv"}
SRT_TS = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")

LANG_NAME = {
    "zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语", "fr": "法语",
    "de": "德语", "es": "西班牙语", "ru": "俄语", "pt": "葡萄牙语",
    "it": "意大利语", "ar": "阿拉伯语", "th": "泰语", "vi": "越南语",
}


def fmt_ts(sec):
    """秒 -> SRT 时间戳 00:00:00,000"""
    ms = int(round(float(sec or 0) * 1000))
    if ms < 0:
        ms = 0
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(h, m, s, ms)


def parse_ts(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def seg_bounds(seg):
    return (float(a7w.dig(seg, "start") or a7w.dig(seg, "start_time") or 0),
            float(a7w.dig(seg, "end") or a7w.dig(seg, "end_time") or 0),
            (a7w.dig(seg, "text") or "").strip())


PUNCT_HINT = "，。！？、；：,.!?;:…·—－~～「」『』（）()《》〈〉【】“”‘’\"'"


def restore_punctuation(segments, full_text):
    """把整段 text 里的标点补回 segments。

    实测：平台 `segments[].text` 是**不带标点**的（标点只出现在整段 `text` 里），
    所以直接合并出来的字幕会一句标点都没有，merge_segments 的「按标点断行」
    规则也就永远触发不了。这里把整段文本逐字对齐回 segments：对得上的是正常字，
    对不上的只有标点时，就补到它前面那个字所在的 segment 末尾。

    两边文本对不齐（出现非标点字符对不上）时**原样返回**，宁可不补也不补错位。
    """
    segs = []
    for seg in segments:
        st, en, tx = seg_bounds(seg)
        if tx:
            segs.append({"start": st, "end": en, "text": tx})
    plain = "".join(ch for ch in (full_text or "") if not ch.isspace())
    if not segs or not plain:
        return segments
    joined = "".join(s["text"] for s in segs)
    if not joined:
        return segments
    out = [dict(s) for s in segs]
    i = 0
    for ch in plain:
        if i < len(joined) and ch == joined[i]:
            i += 1
            continue
        if i == 0 or ch not in PUNCT_HINT:
            return segments          # 对不上，保守放弃
        out[i - 1]["text"] += ch
    if i != len(joined):
        return segments
    return out


def merge_segments(segments, gap=0.7, max_chars=18):
    """平台返回的是**字符级**时间戳，直接做字幕会一字一行。

    这里按三条规则合并成正常人能读的字幕行：
      1. 遇到句末标点（。！？）断行
      2. 遇到逗号、顿号等停顿且已有一小段，也断行
      3. 与上一字间隔超过 gap 秒，或累计超过 max_chars，强制断行

    注意：分段文本本身**不带标点**（见 restore_punctuation），所以标点要靠
    调用方先补回来，否则规则 1/2 只在原文自带标点的模型输出上才生效。
    """
    END = "。！？!?…"
    SOFT = "，,、；;：:"
    out, cur = [], None
    for seg in segments:
        st, en, tx = seg_bounds(seg)
        if not tx:
            continue
        if cur is None:
            cur = [st, en, tx]
            continue
        prev_end = cur[1]
        joined_len = len(cur[2]) + len(tx)
        too_far = st - prev_end > gap
        # 当前段开头若自己带着标点，说明它其实是上一句的结尾，先吃掉再判行
        if tx[0] in END + SOFT and joined_len <= max_chars + 2:
            cur[1] = en
            cur[2] += tx
            if cur[2][-1] in END or (cur[2][-1] in SOFT and len(cur[2]) >= 8):
                out.append(cur)
                cur = None
            continue
        if cur[2][-1] in END or too_far or joined_len > max_chars:
            out.append(cur)
            cur = [st, en, tx]
        else:
            cur[1] = en
            cur[2] += tx
        if cur[2][-1] in END or (cur[2][-1] in SOFT and len(cur[2]) >= 8):
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [{"start": s, "end": e, "text": t} for s, e, t in out]


def to_srt(entries, offset=0.0):
    lines = []
    for i, item in enumerate(entries, 1):
        start = float(a7w.dig(item, "start") or 0) + offset
        end = float(a7w.dig(item, "end") or 0) + offset
        lines += [str(i), "{} --> {}".format(fmt_ts(start), fmt_ts(end)),
                  (a7w.dig(item, "text") or "").strip(), ""]
    return "\n".join(lines)


def read_srt(path):
    raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    entries = []
    for block in re.split(r"\r?\n\s*\r?\n", raw):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        hit, text_start = None, 0
        for idx, ln in enumerate(lines):
            m = SRT_TS.search(ln)
            if m:
                hit, text_start = m, idx + 1
                break
        if not hit:
            continue
        text = "\n".join(lines[text_start:]).strip()
        if text:
            entries.append({"start": parse_ts(*hit.group(1, 2, 3, 4)),
                            "end": parse_ts(*hit.group(5, 6, 7, 8)),
                            "text": text})
    return entries


# --------------------------------------------------------------------------
# 可选：调用**用户自己的**大模型 / 翻译接口（平台不提供翻译能力）
# --------------------------------------------------------------------------

def _chat(url, key, body, timeout=180):
    req = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 401:
            raise a7w.A7wError("翻译接口鉴权失败（401）：--api-key 无效。{}".format(detail))
        if exc.code == 402:
            raise a7w.A7wError("翻译接口余额不足（402）：请到该服务商充值。{}".format(detail))
        raise a7w.A7wError("翻译接口请求失败（HTTP {}）：{}".format(exc.code, detail))
    except urllib.error.URLError as exc:
        raise a7w.A7wError("翻译接口网络错误：{}（确认能访问 {}）".format(exc.reason, url))


def _deepl(texts, key, target, timeout=180):
    data = urllib.parse.urlencode(
        [("auth_key", key), ("target_lang", target.upper())]
        + [("text", t) for t in texts]).encode()
    req = urllib.request.Request(
        "https://api-free.deepl.com/v2/translate", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code in (401, 403):
            raise a7w.A7wError("DeepL 鉴权失败（{}）：--api-key 无效。{}".format(exc.code, detail))
        if exc.code == 456:
            raise a7w.A7wError("DeepL 额度用尽（456）：请充值后再试。{}".format(detail))
        raise a7w.A7wError("DeepL 请求失败（HTTP {}）：{}".format(exc.code, detail))
    except urllib.error.URLError as exc:
        raise a7w.A7wError("DeepL 网络错误：{}".format(exc.reason))
    return [it.get("text", "") for it in payload.get("translations") or []]


def translate_entries(entries, to_lang, opts):
    """把每条字幕的文本翻成目标语言。失败就抛错——不假装翻好了。"""
    texts = [(a7w.dig(e, "text") or "").strip() for e in entries]
    if not texts:
        return []
    target_name = LANG_NAME.get(to_lang, to_lang)

    if opts.provider == "deepl":
        if not opts.api_key:
            raise a7w.A7wError("用 --provider deepl 时必须给 --api-key（你的 DeepL Key）。")
        out = []
        for i in range(0, len(texts), 50):          # DeepL 单请求 50 段上限
            out += _deepl(texts[i:i + 50], opts.api_key, to_lang)
        return out

    if not opts.api_base or not opts.api_key or not opts.model:
        raise a7w.A7wError(
            "平台没有翻译接口，翻译要用你自己的大模型。请补齐三个参数：\n"
            "  --api-base https://api.deepseek.com/v1   （任意 OpenAI 兼容端点，\n"
            "       也可以是本地 http://127.0.0.1:11434/v1）\n"
            "  --api-key  sk-xxxx\n"
            "  --model    deepseek-chat")
    url = opts.api_base.rstrip("/") + "/chat/completions"
    if opts.verbose:
        sys.stderr.write("翻译接口：{}｜模型：{}\n".format(url, opts.model))

    out = []
    for i in range(0, len(texts), 20):              # 分批，避免超长与超时
        batch = texts[i:i + 20]
        numbered = "\n".join("{}. {}".format(n + 1, t) for n, t in enumerate(batch))
        payload = {
            "model": opts.model,
            "temperature": 0,
            "messages": [
                {"role": "system",
                 "content": "你是字幕翻译。把每行译成{}，只输出 “序号. 译文” 的行，"
                            "序号与原行一一对应，不要合并、不要解释、不要加空行。"
                            .format(target_name)},
                {"role": "user", "content": numbered},
            ],
        }
        body = _chat(url, opts.api_key, payload)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise a7w.A7wError("翻译接口返回结构不认识：{}".format(
                json.dumps(body, ensure_ascii=False)[:300]))
        got = {}
        for line in content.splitlines():
            m = re.match(r"\s*(\d+)\s*[.、:：)]\s*(.+?)\s*$", line)
            if m:
                got[int(m.group(1))] = m.group(2)
        if len(got) < len(batch):
            sys.stderr.write("警告：这一批 {}/{} 条译文没对齐，缺的按原文占位。\n"
                             .format(len(got), len(batch)))
        for n, t in enumerate(batch, 1):
            out.append(got.get(n, t))
    return out


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="视频音轨转写生成源语言 SRT（走 api.a7w.cn，零安装）；"
                    "翻译可选、且只用你自己的大模型接口。",
        epilog="能力边界：平台没有翻译接口，翻译必须你自备接口（--api-base/--api-key/--model "
               "或 --provider deepl）；多角色配音与音画合成本脚本不做。")
    ap.add_argument("media", nargs="?", help="本地视频（或音频）文件路径")
    ap.add_argument("--url", help="媒体的公网 HTTP(S) 地址（与本地文件二选一）")
    ap.add_argument("--lang", help="源语言代码，如 zh / en；不传自动检测")
    ap.add_argument("--srt", action="store_true", help="输出 .srt（默认 --lang 给定时就输出）")
    ap.add_argument("-o", "--out", help="SRT 落点，默认与媒体同名同目录")
    ap.add_argument("--transcript", action="store_true", help="只打印文稿，不写 SRT")
    ap.add_argument("--offset", type=float, default=0.0, help="时间轴整体平移秒数")
    ap.add_argument("--key", help="a7w 的 API Key（转写用）")
    # 翻译相关：全部是「你自己的接口」，平台不提供
    ap.add_argument("--translate", action="store_true",
                    help="开启翻译（需要你自己提供接口参数；平台无翻译接口）")
    ap.add_argument("--to", default="en", help="目标语言，默认 en")
    ap.add_argument("--provider", choices=["openai", "deepl"], default="openai",
                    help="翻译接口类型，默认 openai（兼容端点）")
    ap.add_argument("--api-base", help="OpenAI 兼容端点，如 https://api.deepseek.com/v1")
    ap.add_argument("--api-key", help="翻译接口的 Key（与 a7w 的 --key 是两回事）")
    ap.add_argument("--model", help="翻译用的模型名，如 deepseek-chat")
    ap.add_argument("--bilingual", action="store_true",
                    help="译文与原句两行都留在字幕里")
    ap.add_argument("--verbose", action="store_true", help="打印更多过程信息")
    a = ap.parse_args()

    if not a.media and not a.url:
        ap.error("请给一个本地视频文件，或用 --url 传公网地址")
    if a.media and not Path(a.media).is_file():
        ap.error("找不到文件：{}".format(a.media))
    if a.media and Path(a.media).suffix.lower() not in MEDIA_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.media))

    out = Path(a.out) if a.out else None
    want_srt = not a.transcript
    fields = {"ignore_timestamps": False} if want_srt else {"ignore_timestamps": True}
    if a.lang:
        fields["language"] = a.lang

    try:
        if a.url:
            fields["audio_url"] = a.url
            data = a7w.call(APP, API, fields, key=a.key)
        else:
            data = a7w.upload(APP, API, fields, file_field="audio",
                              file_path=a.media, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    text = (a7w.dig(data, "text") or a7w.dig(data, "result", "text") or "").strip()
    segments = (a7w.dig(data, "segments") or a7w.dig(data, "result", "segments")
                or a7w.dig(data, "utterances") or [])
    lang = a7w.dig(data, "language") or a.lang or "?"
    dur = a7w.dig(data, "duration")
    stem = Path(a.media).stem if a.media else "subtitle"

    sys.stderr.write("转写完成：语言 {}｜时长 {} 秒｜{} 字\n".format(
        lang, dur if dur is not None else "?", len(text)))

    srt_written, rows, translated, translation = None, 0, False, None
    if want_srt and not segments:
        sys.stderr.write("这条返回里没有分段时间戳，没生成 SRT。\n")
        want_srt = False
    elif want_srt:
        entries = merge_segments(restore_punctuation(segments, text))
        if a.translate:
            try:
                translated_text = translate_entries(entries, a.to, a)
            except a7w.A7wError as exc:
                sys.stderr.write("翻译失败：{}\n".format(exc))
                sys.stderr.write("已保留源语言 SRT，翻译环节请你自行接上。\n")
                translation = {"ok": False, "error": str(exc)}
            else:
                for e, t in zip(entries, translated_text):
                    e["source"] = e["text"]
                    e["text"] = (e["source"] + "\n" + t) if a.bilingual else t
                translated = True
                translation = {"ok": True, "to": a.to, "provider": a.provider,
                               "model": a.model or "deepl", "bilingual": a.bilingual}
                sys.stderr.write("翻译完成：{} 条 -> {}\n".format(len(entries), a.to))
        else:
            sys.stderr.write("未翻译（平台没有翻译接口；要翻请加 --translate 并给出你自己的接口）。\n")

        srt_path = out if (out and out.suffix.lower() == ".srt") else Path(stem).with_suffix(".srt")
        if srt_path.parent and not srt_path.parent.exists():
            srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text(to_srt(entries, a.offset), encoding="utf-8")
        srt_written, rows = str(srt_path), len(entries)
        sys.stderr.write("已写入 {}（{} 条字幕）\n".format(srt_path, rows))

    if a.offset and srt_written:
        sys.stderr.write("时间轴整体平移 {:+.3f} 秒\n".format(a.offset))

    sys.stderr.write("说明：配音与音画合成不在本脚本范围内；配音可另配 voice_tts/tts，"
                     "合成需要本地 ffmpeg。\n")

    print(json.dumps({
        "ok": True,
        "language": lang,
        "duration": dur,
        "chars": len(text),
        "segments": len(segments),
        "srt": srt_written,
        "srt_rows": rows,
        "platform_translation": False,
        "translated": translated,
        "translation": translation,
        "text": text,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
