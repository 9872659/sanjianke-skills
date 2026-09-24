#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语音合成 / 语音识别 —— 零安装版。

原先要用这个 Skill，得装 PaddleSpeech、拖一堆音频依赖、下模型、还要对版本。
现在不需要：文字和音频直接走 api.a7w.cn，本机只要求 Python 3.8+。

用法
    # 文字转语音（短文本，同步返回）
    python3 run.py tts "你好，这里是三剪客的语音测试。" --out hello.mp3

    # 长文本（异步，自动轮询到出音频）
    python3 run.py tts --file 解说稿.txt --out 解说.mp3

    # 语音转文字
    python3 run.py asr 会议录音.wav
    python3 run.py asr 会议录音.wav --text-only

    # 看看有哪些可用音色（免费接口）
    python3 run.py voices

配 Key（三种方式任选）
    python3 run.py tts "你好" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json

说明
    · 走平台 `voice_tts` 应用：`tts`（同步，≤500 字）/ `tts_async`（长文本）/ `stt` / `list_voices`
    · `--voice <reference_id>` 可以指定自己训练/克隆的音色（先 `voices` 查 ID）
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
SYNC_LIMIT = 500


def pick_audio(res):
    for path in (("result", "audio_url"), ("result", "url"), ("audio_url",),
                 ("url",), ("result", "data", "audio_url")):
        v = a7w.dig(res, *path)
        if v:
            return v
    return None


def do_tts(a):
    if a.file:
        text = Path(a.file).read_text(encoding="utf-8").strip()
        if not text:
            sys.stderr.write("文件是空的：{}\n".format(a.file))
            return 2
    else:
        text = a.text or ""
    if not text:
        sys.stderr.write("没有文本可合成。给一句话，或用 --file 指定文本文件。\n")
        return 2

    body = {"text": text, "format": a.format}
    if a.voice:
        body["reference_id"] = a.voice
    long_text = len(text) > SYNC_LIMIT
    api = "tts_async" if long_text else "tts"
    sys.stderr.write("{} 字 → 走 {}（{}）\n".format(
        len(text), api, "长文本，异步" if long_text else "短文本，同步"))
    try:
        res = a7w.call(APP, api, body, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    url = pick_audio(res)
    cost = a7w.dig(res, "usage", "points_cost")
    if not url:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.stderr.write("没从返回里找到音频地址，上面是原始返回。\n")
        return 5
    try:
        a7w.save(url, a.out)
    except a7w.A7wError as exc:
        sys.stderr.write("合成成功但下载失败：{}（地址：{}）\n".format(exc, url))
        return 6
    sys.stderr.write("已保存 {}{}\n".format(
        a.out, "  消耗 {} 点".format(cost) if cost else ""))
    print(json.dumps({"ok": True, "out": str(Path(a.out).resolve()), "url": url,
                      "chars": len(text), "api": api, "points_cost": cost},
                     ensure_ascii=False))
    return 0


def do_asr(a):
    if not a.audio:
        sys.stderr.write("请给一个音频文件。\n")
        return 2
    if not Path(a.audio).is_file():
        sys.stderr.write("找不到文件：{}\n".format(a.audio))
        return 2
    fields = {"ignore_timestamps": True}
    if a.lang:
        fields["language"] = a.lang
    try:
        data = a7w.upload(APP, "stt", fields, file_field="audio",
                          file_path=a.audio, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    text = (a7w.dig(data, "text") or a7w.dig(data, "result", "text") or "").strip()
    print(text)
    sys.stderr.write("\n--- {} 字\n".format(len(text)))
    if not a.text_only:
        print(json.dumps({"ok": True, "chars": len(text)}, ensure_ascii=False))
    return 0


def do_voices(a):
    try:
        data = a7w.call(APP, "list_voices", {}, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    items = data if isinstance(data, list) else (
        a7w.dig(data, "lists") or a7w.dig(data, "items") or a7w.dig(data, "data") or [])
    if not items:
        sys.stderr.write("当前账号还没有创建过音色。\n")
    for it in items:
        print("{:<28} {:<16} {}".format(
            str(a7w.dig(it, "reference_id") or a7w.dig(it, "id") or "-"),
            str(a7w.dig(it, "title") or a7w.dig(it, "name") or "-"),
            str(a7w.dig(it, "language") or "")))
    print(json.dumps({"ok": True, "count": len(items)}, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description="语音合成 / 识别（走 api.a7w.cn，零安装）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tts", help="文字转语音")
    t.add_argument("text", nargs="?", help="要合成的文本")
    t.add_argument("--file", help="从文本文件读（长文自动走异步接口）")
    t.add_argument("--voice", help="音色 reference_id（先跑 voices 查）")
    t.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus", "pcm"])
    t.add_argument("-o", "--out", default="speech.mp3")
    t.add_argument("--key")

    s = sub.add_parser("asr", help="语音转文字")
    s.add_argument("audio", help="本地音频文件")
    s.add_argument("--lang", help="语言代码，如 zh / en")
    s.add_argument("--text-only", action="store_true", help="只输出文字，不输出 JSON")
    s.add_argument("--key")

    v = sub.add_parser("voices", help="列出可用音色")
    v.add_argument("--key")

    a = ap.parse_args()
    if a.cmd == "tts":
        return do_tts(a)
    if a.cmd == "asr":
        return do_asr(a)
    return do_voices(a)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
