#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多情感多音色语音合成（EmotiVoice 场景）—— 零安装版。

原先要用这个 Skill，得先备 NVIDIA 显卡、装 PyTorch、手工摆好两套权重目录。
现在不需要：文本直接送到 api.a7w.cn 合成，本机只要求 Python 3.8+。

用法
    python3 run.py "要合成的台词" --out line.mp3
    python3 run.py "要合成的台词" --voice <reference_id> --out line.mp3
    python3 run.py "要合成的台词" --speed 1.15 --volume 1.1 --out line.mp3
    python3 run.py --file 台词.txt --out 台词.mp3        # 长文自动切异步接口
    python3 run.py voices                               # 列出可用音色（免费）

第一次使用需要配 Key（三种方式任选）：
    python3 run.py "文本" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

能力边界（务必先看）
    · 平台的「语调 / 语速」用 `prosody` 对象控制：speed（语速倍率）、volume（音量）、
      normalize_loudness（响度归一，仅 s2-pro）。**这就是零安装版能调的全部韵律维度。**
    · **EmotiVoice 那种「用提示词指定情绪」（Happy / Sad / Angry / Excited…）
      平台不直接支持**：接口里没有情绪 / 风格提示词字段，别把情绪标签拼进文本
      指望它变调——要情绪化演绎，只能用音色 + 语速/音量绕，或回到下面的本地装法。

计费：走平台 `voice_tts` 应用 —— `tts`（同步，≤500 字）/ `tts_async`（长文本），
按次固定价 0.02 点 + 输入 50 点/千字；`list_voices` 免费（以平台实时价为准）。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "voice_tts"
SYNC_LIMIT = 500          # 超过这个字数自动切 tts_async


def pick_audio(res):
    """在返回结构里找音频地址——不同上游字段名不完全一致，逐个试。"""
    for path in (("result", "audio_url"), ("result", "url"), ("audio_url",),
                 ("url",), ("result", "data", "audio_url"),
                 ("data", "audio_url"), ("data", "url")):
        v = a7w.dig(res, *path)
        if v:
            return v
    return None


def do_tts(a):
    if a.file:
        try:
            text = Path(a.file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            sys.stderr.write("读不到文本文件：{}\n".format(exc))
            return 2
        if not text:
            sys.stderr.write("文件是空的：{}\n".format(a.file))
            return 2
    else:
        text = (a.text or "").strip()
    if not text:
        sys.stderr.write("没有文本可合成。给一句话，或用 --file 指定文本文件。\n")
        return 2

    body = {"text": text, "format": a.format}
    if a.voice:
        body["reference_id"] = a.voice

    # 语调 / 语速：平台只认 prosody 对象（没有情绪标签字段）
    prosody = {}
    if a.speed is not None:
        prosody["speed"] = a.speed
    if a.volume is not None:
        prosody["volume"] = a.volume
    if prosody:
        body["prosody"] = prosody

    long_text = len(text) > SYNC_LIMIT
    api = "tts_async" if long_text else "tts"
    sys.stderr.write("{} 字 → 走 {}（{}）｜prosody={}\n".format(
        len(text), api, "长文本，异步" if long_text else "短文本，同步",
        json.dumps(prosody, ensure_ascii=False) if prosody else "未指定"))
    try:
        res = a7w.call(APP, api, body, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    url = pick_audio(res)
    cost = a7w.dig(res, "usage", "points_cost") or a7w.dig(res, "points_cost")
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
                      "chars": len(text), "api": api, "voice": a.voice,
                      "prosody": prosody or None, "points_cost": cost},
                     ensure_ascii=False))
    return 0


def do_voices(argv):
    ap = argparse.ArgumentParser(prog="run.py voices", description="列出账号下可用音色（免费）")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args(argv)
    try:
        data = a7w.call(APP, "list_voices", {}, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    items = data if isinstance(data, list) else (
        a7w.dig(data, "lists") or a7w.dig(data, "items")
        or a7w.dig(data, "data") or a7w.dig(data, "voices") or [])
    if not isinstance(items, list):
        items = []
    if not items:
        sys.stderr.write("当前账号还没有创建过音色（不传 --voice 就用平台默认音色）。\n")
    for it in items:
        rid = a7w.dig(it, "reference_id") or a7w.dig(it, "model_id") or a7w.dig(it, "id") or "-"
        title = a7w.dig(it, "title") or a7w.dig(it, "name") or "-"
        lang = a7w.dig(it, "language") or a7w.dig(it, "languages") or ""
        if isinstance(lang, list):
            lang = ",".join(str(x) for x in lang)
        print("{:<32} {:<20} {}".format(str(rid), str(title), str(lang)))
    print(json.dumps({"ok": True, "count": len(items)}, ensure_ascii=False))
    return 0


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "voices":
        return do_voices(argv[1:])

    ap = argparse.ArgumentParser(
        prog="run.py", description="多情感多音色语音合成（走 api.a7w.cn，零安装）")
    ap.add_argument("text", nargs="?", help="要合成的文本")
    ap.add_argument("--file", help="从文本文件读（超过 500 字自动走异步接口）")
    ap.add_argument("--voice", metavar="ID", help="音色 reference_id（先跑 voices 查）")
    ap.add_argument("--speed", type=float, metavar="倍率",
                    help="语速倍率，走 prosody.speed（如 1.15；不传用平台默认）")
    ap.add_argument("--volume", type=float, metavar="倍率",
                    help="音量倍率，走 prosody.volume（如 1.1；不传用平台默认）")
    ap.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus", "pcm"],
                    help="输出格式，默认 mp3")
    ap.add_argument("-o", "--out", default="speech.mp3", help="保存路径")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args(argv)
    if a.speed is not None and a.speed <= 0:
        ap.error("--speed 要大于 0")
    if a.volume is not None and a.volume <= 0:
        ap.error("--volume 要大于 0")
    return do_tts(a)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
