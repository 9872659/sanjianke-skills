#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频字幕提取（零安装版）—— 本脚本覆盖「有音轨的视频 → 文字/字幕」。

先把边界说清楚，免得白跑一趟：

    · **硬字幕（烧进画面里的字）需要 OCR**。要拿到那种字幕，必须逐帧截图、
      定位字幕区域、再做图像文字识别。
    · **平台没有 OCR 接口**（api.a7w.cn 上没有 OCR app），所以
      「硬字幕视频 → 文字」这件事，本脚本**不覆盖**，请用上游
      video-subtitle-extractor 的本地版（Python 3.12 + PaddlePaddle + CUDA）。
    · 本脚本真正零安装能做的是另一半：**视频里有人说话，就把话转成文字与 SRT**。
      这是绝大多数「视频 → 字幕」需求的实际形态，也是本脚本的定位。
    · 顺带说明：如果字幕是**独立字幕轨**（mkv/mp4 里可开关的那种），
      那不是 OCR 也不是语音，用 `ffmpeg -map 0:s:0` 直接抽最快。

用法
    python3 run.py 视频.mp4                    # 音轨转写，打印文字
    python3 run.py 视频.mp4 --srt              # 顺便输出同名 .srt
    python3 run.py 视频.mp4 --lang zh          # 指定语言，默认自动检测
    python3 run.py 视频.mp4 --srt -o 成片.srt   # 指定 SRT 落点
    python3 run.py 视频.mp4 --offset -0.5      # 时间轴整体提前 0.5 秒
    python3 run.py --url https://example.com/v.mp4   # 用公网媒体地址（免上传）

第一次使用需要配 Key（三种方式任选）：
    python3 run.py 视频.mp4 --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

计费：`voice_tts/stt` 按次 40 点（实测值，以平台实时价为准）。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
API = "stt"
MEDIA_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
             ".mp4", ".mov", ".mkv", ".webm", ".avi", ".ts", ".flv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"}


def fmt_ts(sec):
    """秒 -> SRT 时间戳 00:00:00,000"""
    ms = int(round(float(sec or 0) * 1000))
    if ms < 0:
        ms = 0
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(h, m, s, ms)


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
        start = float(item["start"]) + offset
        end = float(item["end"]) + offset
        lines += [str(i), "{} --> {}".format(fmt_ts(start), fmt_ts(end)),
                  item["text"], ""]
    return "\n".join(lines)


def looks_like_images(path):
    p = Path(path)
    return p.is_file() and p.suffix.lower() in IMAGE_EXT


def main():
    ap = argparse.ArgumentParser(
        description="有音轨的视频转文字 / 出 SRT（走 api.a7w.cn，零安装）。"
                    "硬字幕视频请看包内 SKILL.md 的「本脚本不覆盖」说明。",
        epilog="能力边界：硬字幕提取需要 OCR，平台没有 OCR 接口，本脚本不覆盖；"
               "内嵌字幕轨请用 ffmpeg 直接抽；本脚本只处理音轨。")
    ap.add_argument("media", nargs="?", help="本地视频（或音频）文件路径")
    ap.add_argument("--url", help="媒体的公网 HTTP(S) 地址（与本地文件二选一）")
    ap.add_argument("--lang", help="语言代码，如 zh / en；不传自动检测")
    ap.add_argument("--srt", action="store_true", help="输出 .srt 字幕（合并字符级时间戳）")
    ap.add_argument("-o", "--out", help="文稿或字幕的落点；给 .srt 后缀即视为要出字幕")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="整条时间轴平移秒数，可为负")
    ap.add_argument("--crop", metavar="ymin,ymax,xmin,xmax",
                    help="硬字幕区域（仅登记在结果里做参考，本脚本不截图、不做 OCR）")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    if not a.media and not a.url:
        ap.error("请给一个本地视频文件，或用 --url 传公网地址")
    if a.media and not Path(a.media).is_file():
        ap.error("找不到文件：{}".format(a.media))
    if a.media and looks_like_images(a.media):
        sys.stderr.write(
            "这不是视频，是一张图片：{}\n"
            "图片里的字需要 OCR，平台没有 OCR 接口，本脚本做不了。\n"
            "请用上游 video-subtitle-extractor 的本地版（Python 3.12 + PaddlePaddle）。\n"
            .format(a.media))
        return 3
    if a.media and Path(a.media).suffix.lower() not in MEDIA_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.media))
    if a.crop:
        sys.stderr.write(
            "注意：--crop={} 只登记为参考信息。本脚本走的是**音轨转写**，"
            "不截帧、不做画面 OCR；要用它真去裁字幕区域，请用上游本地版。\n".format(a.crop))

    out = Path(a.out) if a.out else None
    want_srt = bool(a.srt or (out and out.suffix.lower() == ".srt"))
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

    sys.stderr.write("语言 {}｜时长 {} 秒｜{} 字\n".format(
        lang, dur if dur is not None else "?", len(text)))

    if out and out.suffix.lower() != ".srt":
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
            if a.offset:
                sys.stderr.write("时间轴整体平移 {:+.3f} 秒\n".format(a.offset))
            srt_path = out if (out and out.suffix.lower() == ".srt") else Path(stem).with_suffix(".srt")
            if srt_path.parent and not srt_path.parent.exists():
                srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(to_srt(entries, a.offset), encoding="utf-8")
            srt_written, rows = str(srt_path), len(entries)
            sys.stderr.write("已写入 {}（{} 条字幕）\n".format(srt_path, rows))

    sys.stderr.write("再次确认：本次转的是**音轨**。视频里的硬字幕（烧进画面的字）"
                     "需要 OCR，平台没有 OCR 接口，本脚本不覆盖。\n")

    print(json.dumps({
        "ok": True,
        "source": "audio_track",
        "hardcoded_subtitle_supported": False,
        "language": lang,
        "duration": dur,
        "chars": len(text),
        "segments": len(segments),
        "srt": srt_written,
        "srt_rows": rows,
        "offset_applied": a.offset,
        "crop_hint": a.crop,
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
