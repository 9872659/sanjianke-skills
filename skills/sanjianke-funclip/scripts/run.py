#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""识别文字自动剪视频 —— 零安装版（转写 + 按文字定位）。

原先要用这个 Skill，得 clone FunClip、建独立虚拟环境、装匹配平台的
PyTorch/torchaudio、下好几 G 的识别模型权重、还要有显卡或忍受 CPU 慢速；
界面还要求你把素材上传到本地起的 Gradio 服务上。

现在本机只要求 Python 3.8+：素材送到 api.a7w.cn 做带时间戳的识别，
拿回文稿后在本机按文字定位出该剪的时间区间。

用法
    python3 run.py 口播.mp4                          # 转写成文稿（人类可读的走 stderr）
    python3 run.py 口播.mp4 --srt                    # 顺便生成同名 .srt 字幕
    python3 run.py 口播.mp4 --find "AI 行业"         # 按文字定位，给出该保留的时间区间
    python3 run.py 口播.mp4 --find "AI" --find "剪辑" --cutlist cut.txt
    python3 run.py --url https://example.com/a.mp4   # 用公网素材地址（免上传）
    python3 run.py 访谈.mp4 --srt --max-chars 16 --gap 0.6
    python3 run.py 素材.mp4 --find "你好" --key sk-xxxx

第一次使用需要配 Key（三种方式任选）：
    python3 run.py 素材.mp4 --key sk-xxxx
    set A7W_API_KEY=sk-xxxx            # Windows；Linux/macOS 用 export
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

输出约定
    · stdout：一行 JSON（给 Agent / 程序解析），含 text / transcript / clips / srt / cutlist
    · stderr：文稿、定位结果、可直接复制的 ffmpeg 命令与进度信息

计费：`voice_tts/stt` 按次固定价（实测一次 40 点，与是否要时间戳无关，
      以平台实时价为准）。定位完全在本机做，不额外计费。

能力边界（平台接口做不到的，别被上游项目的宣传带偏）
    · 平台**不提供**「给一句文稿就自动找出对应片段并切片」的接口。
      FunClip 上游那套「按文字点段落 → 自动裁片」是它自己本地实现的：
      识别给时间戳，裁剪由它按时间戳调 ffmpeg 完成。
    · 本脚本因此做两件能真做到的事：①出带时间戳的文稿与 SRT；
      ②在本机按文字在文稿里定位出时间区间（--find），交给你或 ffmpeg 去裁。
      `--find` 是**关键词子串匹配**，不是语义理解；上游「让大模型挑高光段落」
      那条路本脚本不做，也不假装做了。
    · 平台侧确实有剪辑应用 `smart_clip`，但它做的是**模板化口播/混剪渲染**：
      `smart_clip/realman_broadcast` 必填 `styleId`（模板 id）与 `videoUrl`（公网视频），
      `processRules.resourcePreprocessMethod=sliceMerge` 能按你给的 `subtitle`
      时间戳去掉不连续片段——**但时间区间仍然要你自己先算出来**，
      它没有「按文稿文本定位」这一层。本脚本不自称能替你做这件事。
    · 不做说话人分离：只给「说了什么、什么时候」，不给「谁说的」；
      上游按说话人编号裁剪的能力，平台没有对应接口。
    · 不做热词注入、不支持选模型档位（这些是本地推理才有的参数）。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
API = "stt"
SLUG = "sanjianke-funclip"
MEDIA_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
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


def locate(lines, keywords):
    """在合并出来的字幕行里按文字找命中行（大小写不敏感的子串匹配）。

    说白：这是**关键词子串匹配**，不是语义理解。
    """
    hits = []
    kws = [k.strip().lower() for k in keywords if k and k.strip()]
    for idx, seg in enumerate(lines):
        text = seg["text"]
        low = text.lower()
        for kw in kws:
            if kw in low:
                hits.append({"index": idx, "keyword": kw, "start": seg["start"],
                             "end": seg["end"], "text": text})
                break
    return hits


def coalesce(hits, gap=1.0):
    """把时间上相邻/重叠的命中行合并成连续的裁剪区间。"""
    clips = []
    for h in sorted(hits, key=lambda x: x["start"]):
        if clips and h["start"] - clips[-1]["end"] <= gap:
            clips[-1]["end"] = max(clips[-1]["end"], h["end"])
            clips[-1]["text"] += h["text"]
            if h["keyword"] not in clips[-1]["keywords"]:
                clips[-1]["keywords"].append(h["keyword"])
        else:
            clips.append({"start": h["start"], "end": h["end"],
                          "text": h["text"], "keywords": [h["keyword"]]})
    for c in clips:
        c["duration"] = round(c["end"] - c["start"], 3)
        c["start_ts"] = fmt_ts(c["start"])
        c["end_ts"] = fmt_ts(c["end"])
    return clips


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="识别文字自动剪视频：转写 + 按文字定位时间区间（走 api.a7w.cn，零安装）",
        epilog="注意：平台只提供语音识别；定位在本机做，最终裁剪用 ffmpeg 或剪辑软件完成。"
               "详见 SKILL.md 的「能力边界 / 已知限制」。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media", nargs="?", help="本地音频/视频文件路径")
    ap.add_argument("--url", help="素材的公网 HTTP(S) 地址（与本地文件二选一，免上传）")
    ap.add_argument("--lang", help="语言代码，如 zh / en；不传由平台自动检测")
    ap.add_argument("--find", action="append", metavar="文字",
                    help="按文字定位：给一个关键词，可重复传多次（多个关键词是「或」的关系）")
    ap.add_argument("-o", "--out", help="把文稿写入指定文件")
    ap.add_argument("--srt", action="store_true", help="生成 .srt 字幕文件")
    ap.add_argument("--srt-out", help="显式指定 .srt 输出路径（默认与素材同名）")
    ap.add_argument("--max-chars", type=int, default=18,
                    help="字幕单行最多字符数，默认 18")
    ap.add_argument("--gap", type=float, default=0.7,
                    help="相邻字符间隔超过多少秒就断行，默认 0.7")
    ap.add_argument("--merge-gap", type=float, default=1.0,
                    help="定位到的相邻命中间隔不超过多少秒就并成一段，默认 1.0")
    ap.add_argument("--cutlist", metavar="文件",
                    help="把定位到的裁剪区间写成每行一条的 -ss/-to 清单，方便直接喂 ffmpeg")
    ap.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")
    return ap


def main():
    ap = build_parser()
    a = ap.parse_args()

    if a.srt_out:
        a.srt = True                     # 给了路径就等于要出字幕
    if not a.media and not a.url:
        ap.error("请给一个本地音视频文件，或用 --url 传公网地址")
    if a.cutlist and not a.find:
        ap.error("--cutlist 要配合 --find 用：先告诉我要找什么文字")
    if a.media and not Path(a.media).is_file():
        ap.error("找不到文件：{}".format(a.media))
    if a.media and Path(a.media).suffix.lower() not in MEDIA_EXT:
        sys.stderr.write("提示：{} 不在常见音视频扩展名里，仍会尝试上传。\n".format(a.media))

    # 定位必须要有时间戳，所以这里固定要时间戳（与是否出字幕无关）
    fields = {"ignore_timestamps": False}
    if a.lang:
        fields["language"] = a.lang

    sys.stderr.write("第 1 步：提交语音识别（定位要时间戳，所以固定要时间戳）…\n")
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
    raw_segments = (a7w.dig(data, "segments") or a7w.dig(data, "result", "segments")
                    or a7w.dig(data, "utterances") or [])
    lang = (a7w.dig(data, "language_code") or a7w.dig(data, "result", "language_code")
            or a7w.dig(data, "language") or a7w.dig(data, "result", "language")
            or a.lang or "?")
    dur = a7w.dig(data, "duration") or a7w.dig(data, "result", "duration")
    cost = a7w.dig(data, "usage", "points_cost") or a7w.dig(data, "usage", "actual_points")

    if not text and not raw_segments:
        sys.stderr.write("接口没返回文稿，原始返回：\n{}\n".format(
            json.dumps(data, ensure_ascii=False)[:1500]))
        return 5

    punct_ok = False
    if raw_segments:
        restored = realign_punct(raw_segments, text)
        punct_ok = restored is not raw_segments
        lines = merge_segments(restored, gap=a.gap, max_chars=a.max_chars)
    else:
        # 万一这条返回没有分段，就按整段一行处理，文稿与定位仍然可用
        lines = [{"start": 0.0, "end": float(dur or 0), "text": text}]

    sys.stderr.write("\n----- 文稿 ｜ 语言 {} ｜ 时长 {} 秒 ｜ {} 字 ｜ 字幕 {} 行 -----\n".format(
        lang, round(float(dur), 2) if dur is not None else "?", len(text), len(lines)))
    for i, seg in enumerate(lines, 1):
        sys.stderr.write("[{:>3}] {} --> {}  {}\n".format(
            i, fmt_ts(seg["start"]), fmt_ts(seg["end"]), seg["text"]))
    sys.stderr.write("-----\n")
    sys.stderr.write("标点{}｜字符级时间戳 {} 条｜消耗 {} 点\n".format(
        "已按整段文本补回" if punct_ok else "未补（分段里没标点或与整段文本对不齐）",
        len(raw_segments), cost if cost is not None else "?"))

    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write("文稿已写入 {}\n".format(a.out))

    srt_path = None
    if a.srt:
        if lines:
            if a.srt_out:
                srt_path = Path(a.srt_out)
            elif a.out:
                srt_path = Path(a.out).with_suffix(".srt")
            elif a.media:
                srt_path = Path(a.media).with_suffix(".srt")
            else:
                srt_path = Path("subtitle.srt")
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(to_srt(lines), encoding="utf-8")
            srt_path = str(srt_path.resolve())
            sys.stderr.write("字幕已写入 {}（{} 条）\n".format(srt_path, len(lines)))
        else:
            sys.stderr.write("没有可用的分段，没生成 SRT。\n")

    clips = []
    if a.find:
        sys.stderr.write("\n第 2 步：在本机按文字定位（关键词子串匹配，非语义理解）…\n")
        hits = locate(lines, a.find)
        clips = coalesce(hits, gap=a.merge_gap)
        if not clips:
            sys.stderr.write("文稿里没有匹配 {!r} 的文字。可换更短的词，"
                             "或先看上面的文稿确认平台真实转写结果。\n".format(a.find))
        for c in clips:
            sys.stderr.write("  命中 {!r}：{} → {}（{} 秒）\n    {}\n".format(
                "/".join(c["keywords"]), c["start_ts"], c["end_ts"],
                c["duration"], c["text"]))
            sys.stderr.write("    ffmpeg -ss {:.3f} -to {:.3f} -i 素材 -c copy 片段.mp4\n"
                             .format(c["start"], c["end"]))
        if a.cutlist and clips:
            body = "\n".join("-ss {:.3f} -to {:.3f}\t{}".format(
                c["start"], c["end"], c["text"]) for c in clips)
            Path(a.cutlist).write_text(body + "\n", encoding="utf-8")
            sys.stderr.write("裁剪清单已写入 {}（{} 段）\n".format(a.cutlist, len(clips)))

    result = {
        "ok": True,
        "slug": SLUG,
        "language": lang,
        "duration": float(dur) if dur is not None else None,
        "chars": len(text),
        "segments": len(raw_segments),
        "subtitle_lines": len(lines),
        "punctuation_restored": punct_ok,
        "points_cost": cost,
        "text": text,
        "transcript": lines,
        "srt": srt_path,
        "cutlist": a.cutlist if (a.cutlist and clips) else None,
        "clips": clips,
    }
    if a.out:
        result["out"] = str(Path(a.out).resolve())
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
