#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字幕时间轴处理（零安装版）—— 视频/音频转写出 SRT，外加偏移与合并。

原先要用这个 Skill，得先装 Subtitle Edit（Windows 10 22H2+ / macOS 12+ / Linux
加 mpv 与 ffmpeg），它才有波形对轴、格式互转、批量处理那一整套。

现在最常用的那件事——**把视频里的话变成一份带时间轴的 SRT**——不需要装任何东西了：
媒体文件直接上传到 api.a7w.cn 转写，本机只要求有 Python 3.8+。

**平台不提供的能力（仍需本地做，别指望这个脚本）**：
    · 波形／频谱对轴（拖波形逐句校准）
    · 时间轴精细校对（点入点出点、吸附、镜头切换线）
    · 字幕格式互转（ass / vtt / ssa / sup / 380+ 种格式）
    · 图形字幕 OCR、批量规则修正、多人协作

用法
    python3 run.py 视频.mp4                       # 转写，打印文稿
    python3 run.py 视频.mp4 --srt                 # 顺便输出同名 .srt
    python3 run.py 视频.mp4 --srt -o 成片.srt      # 指定 SRT 落点
    python3 run.py 视频.mp4 --lang zh             # 指定语言，默认自动检测
    python3 run.py 视频.mp4 --srt --offset 1.2    # 全片时间轴整体推后 1.2 秒
    python3 run.py 视频.mp4 --srt --merge 机翻.srt # 用机翻文本替换自动转写文本
    python3 run.py --url https://example.com/a.mp4  # 用公网媒体地址（免上传）

第一次使用需要配 Key（三种方式任选）：
    python3 run.py 视频.mp4 --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

计费：`voice_tts/stt` 按次 40 点（实测值，以平台实时价为准）。
"""

import argparse
import json
import re
import sys
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


# --------------------------------------------------------------------------
# 时间轴基础工具
# --------------------------------------------------------------------------

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
        start = float(a7w.dig(item, "start") or a7w.dig(item, "start_time") or 0) + offset
        end = float(a7w.dig(item, "end") or a7w.dig(item, "end_time") or 0) + offset
        text = (a7w.dig(item, "text") or "").strip()
        lines += [str(i), "{} --> {}".format(fmt_ts(start), fmt_ts(end)), text, ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 已有的 SRT：读回来 + 合并文本
# --------------------------------------------------------------------------

def read_srt(path):
    """读一份 SRT 成 [{start, end, text}]。只认标准时间码行，容错跳过垃圾块。"""
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
        if not text:
            continue
        entries.append({
            "start": parse_ts(*hit.group(1, 2, 3, 4)),
            "end": parse_ts(*hit.group(5, 6, 7, 8)),
            "text": text,
        })
    return entries


def merge_text(base, other):
    """把 other 的**文本**按顺序贴到 base 的**时间轴**上，产出双语字幕。

    这是「平台没翻译接口」之后的接续动作：你在别处（本地模型 / 在线翻译）
    把自动转写稿翻好存成一份 SRT，再用这里把两份合起来。
    条数不一致时取两者较小的条数，并在结果里报出来，不假装对齐成功。
    """
    n = min(len(base), len(other))
    merged = []
    for i in range(n):
        merged.append({
            "start": base[i]["start"],
            "end": base[i]["end"],
            "text": base[i]["text"] + "\n" + other[i]["text"],
        })
    return merged


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="视频/音频转写生成 SRT，并可对时间轴做整体偏移与文本合并（走 api.a7w.cn，零安装）",
        epilog="注意：平台不做波形对轴、时间轴精细校对、字幕格式互转，也不做图形字幕 OCR；"
               "这些仍需要本地的 Subtitle Edit / ffsubsync 之类工具。")
    ap.add_argument("media", nargs="?", help="本地视频或音频文件路径")
    ap.add_argument("--url", help="媒体的公网 HTTP(S) 地址（与本地文件二选一）")
    ap.add_argument("--lang", help="语言代码，如 zh / en；不传自动检测")
    ap.add_argument("--srt", action="store_true", help="输出 .srt 字幕（含字符级时间戳合并）")
    ap.add_argument("-o", "--out", help="文稿或字幕的落点；给 .srt 后缀即视为要出字幕")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="整条时间轴平移秒数，可为负；用于修正整体提前/延后")
    ap.add_argument("--merge", metavar="外挂.srt",
                    help="把这份 SRT 的文本按顺序合到自动转写的时间轴上（做双语字幕）")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    if not a.media and not a.url:
        ap.error("请给一个本地视频/音频文件，或用 --url 传公网地址")
    if a.media and not Path(a.media).is_file():
        ap.error("找不到文件：{}".format(a.media))
    if a.media and Path(a.media).suffix.lower() not in MEDIA_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.media))

    out = Path(a.out) if a.out else None
    want_srt = bool(a.srt or (out and out.suffix.lower() == ".srt") or a.merge)
    if a.merge and not Path(a.merge).is_file():
        ap.error("--merge 指定的文件不存在：{}".format(a.merge))

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
    base = a.media or a.url or "subtitle"
    stem = Path(base).stem if a.media else "subtitle"

    sys.stderr.write("语言 {}｜时长 {} 秒｜{} 字\n".format(
        lang, dur if dur is not None else "?", len(text)))

    # 文稿落点（--merge 模式下文稿不做交付，只出字幕）
    if a.out and not a.merge:
        if out.suffix.lower() == ".srt":
            if out.is_file():
                sys.stderr.write("提示：将覆盖已存在的 {}\n".format(out))
        else:
            if out.parent and not out.parent.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text + "\n", encoding="utf-8")
            sys.stderr.write("已写入文稿 {}\n".format(out))

    srt_written, rows = None, 0
    if want_srt:
        if not segments:
            sys.stderr.write("这条返回里没有分段时间戳，没生成 SRT。\n")
        else:
            entries = merge_segments(restore_punctuation(segments, text))
            note = ""
            if a.merge:
                other = read_srt(a.merge)
                if not other:
                    sys.stderr.write("--merge 的文件没解析出任何字幕条目，已按单语输出。\n")
                else:
                    before = len(entries)
                    entries = merge_text(entries, other)
                    note = "已与 {} 合并（自动 {} 条 / 外挂 {} 条，取 {} 条）".format(
                        Path(a.merge).name, before, len(other), len(entries))
                    sys.stderr.write(note + "\n")
            if a.offset:
                sys.stderr.write("时间轴整体平移 {:+.3f} 秒\n".format(a.offset))
            srt_path = out if (out and out.suffix.lower() == ".srt") else Path(stem).with_suffix(".srt")
            if srt_path.parent and not srt_path.parent.exists():
                srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(to_srt(entries, a.offset), encoding="utf-8")
            srt_written, rows = str(srt_path), len(entries)
            sys.stderr.write("已写入 {}（{} 条字幕）\n".format(srt_path, rows))

    sys.stderr.write("提醒：波形对轴、时间轴精细校对、格式互转、图形字幕 OCR 平台都不做，"
                     "需要本地工具。\n")

    print(json.dumps({
        "ok": True,
        "language": lang,
        "duration": dur,
        "chars": len(text),
        "segments": len(segments),
        "srt": srt_written,
        "srt_rows": rows,
        "offset_applied": a.offset,
        "merged_with": a.merge,
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
