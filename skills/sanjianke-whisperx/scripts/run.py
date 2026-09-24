#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhisperX · 音视频转写 / 逐词对轴 —— 零安装版（不含说话人分离）。

原先要用这个 Skill，得装 PyTorch、faster-whisper/CTranslate2、pyannote 一串组件，
配 CUDA 12.8 与匹配驱动，再下识别模型 + 音素对齐模型 + 分离模型，
分离模型还要 Hugging Face 令牌和接受用户协议。现在不需要：音视频直接上传到
api.a7w.cn 转写，本机只要求有 Python 3.8+。

用法
    python3 run.py 访谈.mp4                      # 转成文字
    python3 run.py 访谈.mp4 --srt                # 顺便生成同名 .srt 字幕
    python3 run.py 访谈.mp4 -o 文稿.txt           # 把文字写入指定文件
    python3 run.py 访谈.mp4 --words 逐字.tsv      # 导出逐字时间轴（字符级）
    python3 run.py 访谈.mp4 --lang zh            # 指定语言，不传则自动检测
    python3 run.py 访谈.mp4 --srt --max-chars 16 --gap 0.5

第一次使用需要配 Key（三种方式任选）：
    python3 run.py 音频.mp4 --key sk-xxxx
    set A7W_API_KEY=sk-xxxx            # Windows；Linux/macOS 用 export
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

输出约定
    · stdout：一行 JSON（给 Agent / 程序解析），字段含 ok / text / language / chars / segments / srt / words
    · stderr：文字稿本身与人类可读的进度、统计信息

计费：`voice_tts/stt` 按次固定价（实测一次 40 点，与是否要时间戳无关，
      以平台实时价为准）。

能力边界（务必先看，WhisperX 最有名的两个能力这条链路上没有了）
    · **不做说话人分离**：平台 `voice_tts/stt` 接口不提供 diarization，也没有
      `--diarize` / `--min_speakers` / `--max_speakers` / `--hf_token` 这些参数。
      要区分「谁说了哪句」，本脚本给不了；只能拿到文字＋时间，再自己接分离工具。
    · **不是音素级强制对齐**：平台返回的是**字符级**时间戳（识别模型自身给出的
      分段时间），不是 WhisperX 那种 wav2vec2 音素模型 forced alignment。
      逐字时间轴可以用来做粗颗粒的对轴与逐字高亮，精度低于本地 WhisperX。
    · 不做 `--highlight_words` / `--max_line_width` / `--max_line_count` 的字幕排版，
      这些依赖对齐结果；本脚本用 --max-chars / --gap 做等价的合并排版。
    · 不能选模型、不能选对齐模型、不能用 `--suppress_numerals`、`--hotwords`、
      `--initial_prompt` 这些本地参数；平台固定模型。
    · 不做实时流式、不做声纹建档或跨文件比对。
    · 只有「转写」与「翻成英文」之外，平台不提供任意语向翻译。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
API = "stt"
SLUG = "sanjianke-whisperx"
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
        start = a7w.dig(seg, "start") or 0
        end = a7w.dig(seg, "end") or 0
        text = (a7w.dig(seg, "text") or "").strip()
        lines += [str(i), "{} --> {}".format(fmt_ts(start), fmt_ts(end)), text, ""]
    return "\n".join(lines)


def to_words_tsv(segments):
    """逐字时间轴：每行一个字符/词 + 起止时间。

    注意这是**字符级**时间戳（识别模型自带的），不是音素级强制对齐，
    精度低于本地 WhisperX 的 forced alignment，只适合粗颗粒对轴。
    """
    lines = ["start\tend\ttext"]
    for seg in segments:
        st, en, tx = seg_bounds(seg)
        if not tx:
            continue
        lines.append("{:.3f}\t{:.3f}\t{}".format(st, en, tx))
    return "\n".join(lines) + "\n"


def build_parser():
    ap = argparse.ArgumentParser(
        description="WhisperX 音视频转写 / 逐词对轴（走 api.a7w.cn，零安装）",
        epilog="注意：这一版**不做说话人分离**，逐字时间轴是字符级而非音素级对齐。"
               "详见 SKILL.md 的「能力边界 / 已知限制」。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?", help="本地音频/视频文件路径")
    ap.add_argument("--lang", help="语言代码，如 zh / de；不传由平台自动检测")
    ap.add_argument("-o", "--out", help="把文字稿写入指定文件")
    ap.add_argument("--srt", action="store_true", help="生成 .srt 字幕文件")
    ap.add_argument("--srt-out", help="显式指定 .srt 输出路径（默认与音视频同名）")
    ap.add_argument("--words", metavar="TSV",
                    help="导出逐字时间轴 TSV（字符级，不是音素级强制对齐）")
    ap.add_argument("--no-timestamps", action="store_true",
                    help="不要时间戳，只要纯文本（默认就要时间戳，方便出字幕/对轴）")
    ap.add_argument("--max-chars", type=int, default=18,
                    help="字幕单行最多字符数，默认 18")
    ap.add_argument("--gap", type=float, default=0.7,
                    help="相邻字符间隔超过多少秒就断行，默认 0.7")
    ap.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")
    return ap


def main():
    ap = build_parser()
    a = ap.parse_args()

    if a.srt_out:
        a.srt = True          # 显式给了 .srt 路径，就不用再加一个 --srt
    if a.no_timestamps and (a.srt or a.words):
        ap.error("--no-timestamps 和 --srt/--srt-out/--words 不能一起用："
                 "出字幕与逐字时间轴都必须有时间戳（别白花一次调用）")

    if not a.video:
        ap.error("请给一个本地音频/视频文件路径（例：run.py 访谈.mp4）")
    if not Path(a.video).is_file():
        ap.error("找不到文件：{}".format(a.video))
    if Path(a.video).suffix.lower() not in AUDIO_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.video))

    fields = {"ignore_timestamps": bool(a.no_timestamps)}
    if a.lang:
        fields["language"] = a.lang

    try:
        data = a7w.upload(APP, API, fields, file_field="audio",
                          file_path=a.video, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    text = (a7w.dig(data, "text") or a7w.dig(data, "result", "text") or "").strip()
    segments = (a7w.dig(data, "segments") or a7w.dig(data, "result", "segments") or [])
    lang = (a7w.dig(data, "language_code") or a7w.dig(data, "result", "language_code")
            or a7w.dig(data, "language") or a7w.dig(data, "result", "language")
            or a.lang or "?")
    dur = a7w.dig(data, "duration") or a7w.dig(data, "result", "duration")
    cost = a7w.dig(data, "usage", "points_cost") or a7w.dig(data, "usage", "actual_points")
    if not text:
        sys.stderr.write("接口没返回文字，原始返回：\n{}\n".format(
            json.dumps(data, ensure_ascii=False)[:1500]))
        return 5

    sys.stderr.write("\n===== 转写结果 =====\n{}\n====================\n".format(text))
    sys.stderr.write("语言 {}｜时长 {} 秒｜{} 字｜字符级时间戳 {} 条{}\n".format(
        lang, round(float(dur), 2) if dur is not None else "?",
        len(text), len(segments),
        "｜消耗 {} 点".format(cost) if cost else ""))
    sys.stderr.write("提醒：说话人分离平台接口不提供，本结果不含 speaker 编号。\n")

    restored = restore_punctuation(segments, text)
    punct_ok = restored is not segments
    words_src = restored

    result = {"ok": True, "slug": SLUG, "language": lang,
              "duration": float(dur) if dur is not None else None,
              "chars": len(text), "segments": len(segments),
              "points_cost": cost, "diarization": False,
              "punctuation_restored": punct_ok, "text": text}

    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        result["out"] = str(Path(a.out).resolve())
        sys.stderr.write("文字稿已写入 {}\n".format(a.out))

    if a.words:
        if segments:
            wpath = Path(a.words)
            wpath.parent.mkdir(parents=True, exist_ok=True)
            wpath.write_text(to_words_tsv(words_src), encoding="utf-8")
            result["words"] = str(wpath.resolve())
            sys.stderr.write("逐字时间轴已写入 {}（{} 条，字符级{}）\n".format(
                wpath, len(words_src),
                "，标点已补回" if punct_ok else ""))
        else:
            result["words"] = None
            result["words_warning"] = "平台未返回 segments"
            sys.stderr.write("没拿到字符级时间戳，没生成逐字文件（去掉 --no-timestamps）。\n")

    if a.srt:
        if not segments:
            sys.stderr.write("没拿到字符级时间戳，无法生成 SRT（去掉 --no-timestamps 再试）。\n")
            result["srt"] = None
            result["srt_warning"] = "平台未返回 segments"
        else:
            merged = merge_segments(restored, gap=a.gap, max_chars=a.max_chars)
            if a.srt_out:
                srt_path = Path(a.srt_out)
            elif a.out:
                srt_path = Path(a.out).with_suffix(".srt")
            else:
                srt_path = Path(a.video).with_suffix(".srt")
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(to_srt(merged), encoding="utf-8")
            result["srt"] = str(srt_path.resolve())
            result["srt_lines"] = len(merged)
            sys.stderr.write("字幕已写入 {}（{} 条{}）\n".format(
                srt_path, len(merged),
                "，标点已按整段文本补回" if punct_ok else "，标点未补（平台分段里没有标点）"))

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
