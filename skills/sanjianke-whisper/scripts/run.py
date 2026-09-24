#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语音转文字 / 生成字幕 —— 零安装版。

原先要用这个 Skill，得先 clone whisper、装 PyTorch、配 CUDA、下模型。
现在不需要了：音频直接上传到 api.a7w.cn 转写，本机只要求有 Python 3.8+。

用法
    python3 run.py 会议录音.mp3                     # 转成文字，直接打印
    python3 run.py 会议录音.mp3 --srt               # 顺便输出同名 .srt 字幕
    python3 run.py 会议录音.mp3 -o 文稿.txt          # 写入指定文件
    python3 run.py --url https://example.com/a.mp3  # 用公网音频地址（免上传）
    python3 run.py 录音.wav --lang zh               # 指定语言，默认自动检测

第一次使用需要配 Key（三种方式任选）：
    python3 run.py 音频.mp3 --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

计费：`voice_tts/stt` 按次固定价 30 点（以平台实时价为准）。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
API = "stt"
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
             ".mp4", ".mov", ".mkv", ".webm"}


def fmt_ts(sec):
    """秒 -> SRT 时间戳 00:00:00,000"""
    ms = int(round(float(sec or 0) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(h, m, s, ms)


def seg_bounds(seg):
    return (float(a7w.dig(seg, "start") or a7w.dig(seg, "start_time") or 0),
            float(a7w.dig(seg, "end") or a7w.dig(seg, "end_time") or 0),
            (a7w.dig(seg, "text") or "").strip())


PUNCT = set("，。！？；：、,.!?;:…—-（）()「」“”\"'《》〈〉【】")


def realign_punct(segments, text):
    """把整段文本里的标点回填到字符级时间戳上。

    平台返回的 segments 是**逐字**的、不带标点；而 text 里有标点。
    两者去掉标点与空白后能一一对上时，就把标点插回对应字后面，
    这样 merge_segments 才有句号/逗号可断，字幕行才是正常人读的样子。
    一旦对不齐（换行、多余空白、非逐字分段都可能造成）就原样返回，
    退回纯「停顿 + 长度」合并，**不会输出错位的时间轴**。
    """
    if not text or not segments:
        return segments
    chars = []
    for seg in segments:
        st, en, tx = seg_bounds(seg)
        for ch in tx:
            chars.append([st, en, ch])
    if not chars:
        return segments
    plain = "".join(c for c in text if c not in PUNCT and not c.isspace())
    if plain != "".join(c[2] for c in chars if not c[2].isspace()):
        return segments                       # 对不齐，放弃回填
    out, i = [], 0
    for ch in text:
        if ch in PUNCT or ch.isspace():
            if out:
                out[-1][2] += ch
            continue
        if i >= len(chars):
            return segments
        out.append(chars[i])
        i += 1
    return [{"start": s, "end": e, "text": t} for s, e, t in out] or segments


def merge_segments(segments, gap=0.7, max_chars=18):
    """平台返回的是**字符级**时间戳，直接做字幕会一字一行。

    这里按三条规则合并成正常人能读的字幕行：
      1. 遇到句末标点（。！？）断行
      2. 遇到逗号、顿号等停顿且已有一小段，也断行
      3. 与上一字间隔超过 gap 秒，或累计超过 max_chars，强制断行
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
        # 当前段开头若自己带着标点，说明它其实是上一句的结尾，先吃掉再判行。
        # 不这么做的话：max_chars 会先按字数把行切断，行尾落在内容字上，
        # realign_punct 补回来的标点就被推到下一行开头，照样是无标点硬切。
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


def to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = a7w.dig(seg, "start") or a7w.dig(seg, "start_time") or 0
        end = a7w.dig(seg, "end") or a7w.dig(seg, "end_time") or 0
        text = (a7w.dig(seg, "text") or "").strip()
        lines += [str(i), "{} --> {}".format(fmt_ts(start), fmt_ts(end)), text, ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="语音转文字（走 api.a7w.cn，零安装）")
    ap.add_argument("audio", nargs="?", help="本地音频/视频文件路径")
    ap.add_argument("--url", help="音频的公网 HTTP(S) 地址（与本地文件二选一）")
    ap.add_argument("--lang", help="语言代码，如 zh / en；不传自动检测")
    ap.add_argument("-o", "--out", help="把文字写入指定文件")
    ap.add_argument("--srt", action="store_true", help="同时生成 .srt 字幕")
    ap.add_argument("--timestamps", action="store_true",
                    help="带上分段时间戳（会多收一点费，字幕需要）")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    if not a.audio and not a.url:
        ap.error("请给一个本地音频文件，或用 --url 传公网地址")
    if a.audio and not Path(a.audio).is_file():
        ap.error("找不到文件：{}".format(a.audio))
    if a.audio and Path(a.audio).suffix.lower() not in AUDIO_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.audio))

    fields = {}
    if a.lang:
        fields["language"] = a.lang
    fields["ignore_timestamps"] = not (a.timestamps or a.srt)

    try:
        if a.url:
            fields["audio_url"] = a.url
            data = a7w.call(APP, API, fields, key=a.key)
        else:
            data = a7w.upload(APP, API, fields, file_field="audio",
                              file_path=a.audio, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    text = (a7w.dig(data, "text") or a7w.dig(data, "result", "text") or "").strip()
    segments = (a7w.dig(data, "segments") or a7w.dig(data, "result", "segments")
                or a7w.dig(data, "utterances") or [])
    lang = (a7w.dig(data, "result", "language") or a7w.dig(data, "language")
            or a7w.dig(data, "result", "language_code") or a.lang or "?")
    dur = a7w.dig(data, "result", "duration") or a7w.dig(data, "duration")

    print(text)
    sys.stderr.write("\n--- 语言 {}｜时长 {} 秒｜{} 字\n".format(
        lang, dur if dur is not None else "?", len(text)))

    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))
    if a.srt:
        if segments:
            merged = merge_segments(realign_punct(segments, text))
            srt_path = Path(a.out).with_suffix(".srt") if a.out \
                else Path(a.audio or "subtitle").with_suffix(".srt")
            srt_path.write_text(to_srt(merged), encoding="utf-8")
            sys.stderr.write("已写入 {}（{} 条字幕）\n".format(srt_path, len(merged)))
        else:
            sys.stderr.write("这条返回里没有分段时间戳，没生成 SRT。"
                             "加上 --timestamps 再试一次。\n")
    # 给 Agent 解析用的结构化结果
    print(json.dumps({"ok": True, "language": lang, "duration": dur,
                      "chars": len(text), "segments": len(segments)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
