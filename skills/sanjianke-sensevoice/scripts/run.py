#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多语言语音理解（SenseVoice）—— 零安装版。

原先要用这个 Skill，得自己搭 Python + FunASR、下模型权重，想要 GGUF 单文件还得
自己编译 llama.cpp，要服务化还得起 FastAPI / Docker。现在这些都不用了：
音频直接上传到 api.a7w.cn 转写，本机只要求 Python 3.8+。

用法
    python3 run.py 会议录音.mp3                      # 转写 + 语言/时长（默认带时间戳）
    python3 run.py 会议录音.mp3 --srt                # 顺便输出同名 .srt 字幕
    python3 run.py 会议录音.mp3 -o 文稿.txt           # 把文字写入指定文件
    python3 run.py --url https://example.com/a.mp3   # 用公网音频地址（免上传）
    python3 run.py 录音.wav --lang zh                # 指定语言，默认自动检测
    python3 run.py 录音.wav --no-timestamps          # 不要时间戳，只要纯文本
    python3 run.py 录音.wav --raw                    # 把平台原始返回整个打到 stderr

第一次使用需要配 Key（三种方式任选）：
    python3 run.py 音频.mp3 --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

计费：走平台 `voice_tts/stt`，按次固定价（以平台实时价为准）。

能力边界（这条零安装路线做不到的，如实写在这里）
    · **拿不到情感标签和音频事件标签**。SenseVoice 上游那套「开心/难过/生气/中性」
      与「笑声/掌声/BGM/咳嗽」标记，平台 stt 接口不返回，返回体里只有
      text / language / language_code / duration / segments。别指望这里能出情绪分拣。
    · 说话人区分也没有：返回里没有 speaker 字段，说话人日志那套组合方案在平台上
      没有对应接口。
    · 不做词级强制对齐：带时间戳时给的是**逐字**时间戳（不是词级、也不是音素级）。
    · 不做逆文本归一化开关（itn）、不做标点开关：平台 text 自带标点，字符级
      时间戳里没有标点，本脚本在能精确对齐时把标点回填后合并成正常字幕行。
    · 不做流式实时识别，不做微调，不做服务化部署（FastAPI / Docker / GGUF 都没有）。
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
# 标点集合：用来把整段文本里的标点回填到字符时间轴上
PUNCT = set("。，、；：！？…—,.!?;:'\"“”‘’（）()《》〈〉【】[]{}·～~/\\-")
# 标准字段，其余标量字段当作「额外返回字段」一并抛给 Agent
KNOWN = {"text", "segments", "utterances", "duration", "language", "language_code"}


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


def realign_punct(segments, text):
    """把整段文本里的标点回填到字符级时间戳上。

    平台返回的 segments 是**逐字**的、不带标点；而 `text` 里有标点。
    两者去掉标点与空白后能一一对上时，就把标点插回对应字后面，
    这样 merge_segments 才有句号/逗号可断，字幕行才是正常人读的样子。
    一旦对不齐（换行、多余空白、非逐字分段都可能造成）就原样返回，
    退回纯「停顿 + 长度」合并，不会输出错位的时间轴。
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
    fixed = [{"start": s, "end": e, "text": t} for s, e, t in out]
    return fixed or segments


def merge_segments(segments, gap=0.7, max_chars=18):
    """把逐字时间戳合并成正常人能读的字幕行。

    规则（与 whisper 试点包同一套算法）：
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
    ap = argparse.ArgumentParser(
        description="多语言语音理解 / 转写 / 出字幕（走 api.a7w.cn，零安装）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例：python3 run.py 粤语访谈.mp3 --srt\n"
               "    python3 run.py 录音.wav --lang zh --raw")
    ap.add_argument("audio", nargs="?", help="本地音频/视频文件路径")
    ap.add_argument("--url", help="音频的公网 HTTP(S) 地址（与本地文件二选一）")
    ap.add_argument("--lang", help="语言代码，如 zh / yue / en；不传自动检测")
    ap.add_argument("-o", "--out", help="把文字写入指定文件（.srt 与之同名）")
    ap.add_argument("--srt", action="store_true", help="同时生成 .srt 字幕")
    ap.add_argument("--no-timestamps", action="store_true",
                    help="不要时间戳，只要纯文本（更快、返回更小）")
    ap.add_argument("--raw", action="store_true",
                    help="把平台原始返回整个打到 stderr（排查字段用）")
    ap.add_argument("--gap", type=float, default=0.7,
                    help="字幕断行的停顿阈值，秒（默认 0.7）")
    ap.add_argument("--max-chars", type=int, default=18,
                    help="单条字幕最长字数（默认 18）")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    if not a.audio and not a.url:
        ap.error("请给一个本地音频文件，或用 --url 传公网地址")
    if a.audio and not Path(a.audio).is_file():
        ap.error("找不到文件：{}".format(a.audio))
    if a.audio and Path(a.audio).suffix.lower() not in AUDIO_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.audio))

    # 默认就要时间戳：这样 --srt 随时能用，不用记得再加参数
    want_ts = not a.no_timestamps
    fields = {"ignore_timestamps": not want_ts}
    if a.lang:
        fields["language"] = a.lang

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

    if a.raw:
        sys.stderr.write("--- 平台原始返回 ---\n")
        sys.stderr.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    res = a7w.dig(data, "result") or data or {}
    text = (a7w.dig(res, "text") or a7w.dig(data, "text") or "").strip()
    segments = (a7w.dig(res, "segments") or a7w.dig(data, "segments")
                or a7w.dig(res, "utterances") or [])
    lang = a7w.dig(res, "language") or a.lang or "?"
    lang_code = a7w.dig(res, "language_code")
    dur = a7w.dig(res, "duration")
    cost = a7w.dig(data, "usage", "points_cost") or a7w.dig(res, "usage", "points_cost")
    # 「额外返回字段」：平台除标准字段外还给了什么，一并交给 Agent，别私吞
    extra = {k: v for k, v in (res or {}).items()
             if k not in KNOWN and isinstance(v, (str, int, float, bool))} \
        if isinstance(res, dict) else {}

    if not text:
        sys.stderr.write("平台返回里没有 text 字段，原始返回：\n")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 5

    # 人类可读信息一律走 stderr
    sys.stderr.write(text + "\n")
    sys.stderr.write("\n--- 语言 {}{}｜时长 {} 秒｜{} 字｜{} 段{}".format(
        lang, "（{}）".format(lang_code) if lang_code else "",
        dur if dur is not None else "?", len(text), len(segments),
        "｜消耗 {} 点".format(cost) if cost else ""))
    sys.stderr.write("\n")
    if extra:
        sys.stderr.write("额外返回字段：{}\n".format(
            json.dumps(extra, ensure_ascii=False)))
    else:
        sys.stderr.write("本接口不返回情感标签与音频事件标签。\n")

    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(a.out))

    srt_path = None
    if a.srt:
        if segments:
            merged = merge_segments(realign_punct(segments, text),
                                    gap=a.gap, max_chars=a.max_chars)
            srt_path = Path(a.out).with_suffix(".srt") if a.out \
                else Path(a.audio or "subtitle").with_suffix(".srt")
            srt_path.write_text(to_srt(merged), encoding="utf-8")
            sys.stderr.write("已写入 {}（{} 条字幕，原始 {} 个时间戳）\n".format(
                srt_path, len(merged), len(segments)))
        else:
            sys.stderr.write("这条返回里没有分段时间戳，没生成 SRT。\n")

    # 给 Agent 解析用：stdout 只有这一行 JSON
    sys.stdout.write(json.dumps({
        "ok": True, "text": text, "language": lang, "language_code": lang_code,
        "duration": dur, "chars": len(text), "segments": len(segments),
        "extra": extra,
        "srt": str(srt_path) if srt_path else None,
        "out": a.out, "points_cost": cost,
    }, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
