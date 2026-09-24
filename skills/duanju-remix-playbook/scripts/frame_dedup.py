#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成片抽帧指纹查重自检。

批量出片时，同一条素材常被多条成片复用，画面容易雷同；肉眼逐条比对不现实，
而画面重复正是平台判定「搬运 / 重复」的主要依据。本脚本把「哪几条撞了」
变成可查的数字。

做法：对每条成片按时间均匀抽 N 帧（默认 24），转 9x8 灰度后算 dHash（64 位），
两条片之间用「贪心唯一配对」统计有多少帧能在对方片子里找到近似帧，
相似度 = 配对帧数 / 两片较短者的帧数。

相似度衡量的是「两条片子用了多少相同的画面」，**与顺序无关**——这正是平台
判定搬运 / 重复时看的东西。

依赖：一个可用的 ffmpeg（ffprobe 可选，缺失时自动降级）。
纯 Python 标准库处理帧数据，不需要 numpy / PIL。

用法：
    python3 frame_dedup.py --dir "输出/我的剧集"
    python3 frame_dedup.py --dir <目录> --threshold 0.40 --strict
    python3 frame_dedup.py --a a.mp4 --b b.mp4
    python3 frame_dedup.py --dir <目录> --json --out report.json
    python3 frame_dedup.py --dir <目录> --frames 32 --hamming 10
    python3 frame_dedup.py --dir <目录> --ffmpeg /path/to/ffmpeg

退出码：0 正常；1 有超阈值的对（配合 --strict）；2 用法或环境错误。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".m4v", ".ts"}
HASH_W, HASH_H = 9, 8          # 9x8 灰度 → 64 位 dHash
FRAME_BYTES = HASH_W * HASH_H


# ---------------------------------------------------------------- 二进制定位
def find_binary(name, explicit=None):
    """按 显式参数 → 环境变量 → PATH 的顺序定位二进制。"""
    if explicit:
        return explicit
    env_key = "FFMPEG_PATH" if name == "ffmpeg" else "FFPROBE_PATH"
    if os.environ.get(env_key):
        return os.environ[env_key]
    return shutil.which(name) or name
    return shutil.which(name) or name


# ---------------------------------------------------------------- 抽帧与哈希
def binary_usable(exe):
    """判断一个二进制是否真的可用（裸名字走 PATH，路径走文件存在性）。"""
    if not exe:
        return False
    if os.sep in exe or "/" in exe:
        return Path(exe).is_file()
    return shutil.which(exe) is not None


DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _run(cmd, timeout):
    """统一用 UTF-8 + replace 解码子进程输出。

    中文 Windows 上 ffmpeg 的 stderr 用 GBK 解码会抛 UnicodeDecodeError，
    而这个异常发生在读取线程里，会把整个分析流程带崩，必须显式指定编码。
    """
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _duration_by_ffprobe(path, ffprobe):
    if not binary_usable(ffprobe):
        return None
    cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    try:
        out = _run(cmd, 120)
        return float((out.stdout or "").strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _duration_by_ffmpeg(path, ffmpeg):
    """降级路径：客户端只自带 ffmpeg 时，从 ffmpeg -i 的 stderr 里解析时长。"""
    if not binary_usable(ffmpeg):
        return None
    cmd = [ffmpeg, "-nostdin", "-i", str(path)]
    try:
        out = _run(cmd, 120)
    except (subprocess.SubprocessError, OSError, ValueError):
        return None
    m = DURATION_RE.search(out.stderr or "")
    if not m:
        return None
    hours, minutes, seconds = m.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def video_duration(path, ffprobe, ffmpeg):
    """取时长（秒）：优先 ffprobe，缺失时降级用 ffmpeg -i。"""
    return _duration_by_ffprobe(path, ffprobe) or _duration_by_ffmpeg(path, ffmpeg)


def dhash(frame_bytes):
    """9x8 灰度 → 64 位差分哈希：每行相邻像素左>右 记 1，共 8 行 × 8 位 = 64 位。"""
    bits = 0
    bit_index = 0
    for row in range(HASH_H):
        base = row * HASH_W
        for col in range(HASH_W - 1):
            if frame_bytes[base + col] > frame_bytes[base + col + 1]:
                bits |= 1 << bit_index
            bit_index += 1
    return bits


def extract_hashes(path, ffmpeg, ffprobe, frames):
    """抽 frames 帧并返回 (hashes, duration, error)。"""
    duration = video_duration(path, ffprobe, ffmpeg)
    if not duration or duration <= 0:
        return [], None, "无法读取时长（ffmpeg/ffprobe 不可用或文件损坏）"
    fps = frames / duration
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "frames.raw"
        cmd = [
            ffmpeg, "-v", "error", "-nostdin",
            "-skip_frame", "nokey",              # 只解码关键帧，抽帧快一个数量级
            "-i", str(path),
            "-vf", "fps={:.6f},scale={}:{},format=gray".format(fps, HASH_W, HASH_H),
            "-frames:v", str(frames),
            "-f", "rawvideo", "-y", str(raw),
        ]
        try:
            proc = _run(cmd, 900)
        except subprocess.TimeoutExpired:
            return [], duration, "抽帧超时"
        except (OSError, ValueError) as exc:
            return [], duration, "无法执行 ffmpeg：{}".format(exc)
        if not raw.is_file():
            return [], duration, "ffmpeg 未产出帧数据：{}".format(
                (proc.stderr or "").strip().splitlines()[-1:] or "")
        data = raw.read_bytes()
    count = len(data) // FRAME_BYTES
    if count == 0:
        return [], duration, "未抽到任何帧"
    return [dhash(data[i * FRAME_BYTES:(i + 1) * FRAME_BYTES]) for i in range(count)], duration, None


def hamming(a, b):
    return bin(a ^ b).count("1")


def similarity(hashes_a, hashes_b, tol):
    """贪心唯一配对：A 的每帧至多在 B 中找到一帧近似帧。返回 (相似度, 配对帧数)。"""
    if not hashes_a or not hashes_b:
        return 0.0, 0
    used = [False] * len(hashes_b)
    matched = 0
    for ha in hashes_a:
        best, best_idx = None, -1
        for j, hb in enumerate(hashes_b):
            if used[j]:
                continue
            d = hamming(ha, hb)
            if d <= tol and (best is None or d < best):
                best, best_idx = d, j
        if best_idx >= 0:
            used[best_idx] = True
            matched += 1
    return matched / min(len(hashes_a), len(hashes_b)), matched


# ---------------------------------------------------------------- 主流程
def collect_videos(directory):
    root = Path(directory)
    if not root.is_dir():
        raise SystemExit("不是目录：{}".format(root))
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT)


def analyze(files, ffmpeg, ffprobe, frames, jobs):
    results, errors = {}, {}
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = {pool.submit(extract_hashes, f, ffmpeg, ffprobe, frames): f for f in files}
        for fut, f in futures.items():
            hashes, duration, err = fut.result()
            if err:
                errors[str(f)] = err
            else:
                results[str(f)] = {"hashes": hashes, "duration": duration}
    return results, errors


def render_text(results, pairs, errors, threshold, frames, hamming_tol=8):
    out = ["=" * 66, "成片抽帧指纹查重", "=" * 66,
           "样本 {} 条 ｜ 每条抽帧 {} ｜ 帧判同汉明距离 ≤{} ｜ 判重阈值 {:.0%}".format(
               len(results), frames, hamming_tol, threshold), ""]
    if errors:
        out.append("读取失败 {} 条：".format(len(errors)))
        for path, err in list(errors.items())[:10]:
            out.append("  - {}：{}".format(Path(path).name, err))
        out.append("")
    if not results:
        out.append("没有可分析的有效样本。")
        return "\n".join(out)

    if len(results) <= 24:
        names = [Path(p).name for p in results]
        out.append("相似度矩阵（行/列同名，仅显示大于 0 的部分）：")
        out.append("")
        for i, a in enumerate(results):
            row = []
            for j, b in enumerate(results):
                if j <= i:
                    row.append("  --  ")
                else:
                    sim, _ = similarity(results[a]["hashes"], results[b]["hashes"], hamming_tol)
                    row.append("{:5.0%}".format(sim))
            out.append("  {:<34} {}".format(names[i][:32], " ".join(row)))
        out.append("")

    if not pairs:
        out.append("未发现超过阈值的相似对。")
        out.append("注意：本检查只看画面指纹，不覆盖音频、解说文案与包装差异。")
        return "\n".join(out)

    out.append("超过阈值的相似对（{} 对，按相似度降序）：".format(len(pairs)))
    out.append("")
    out.append("  {:<38} {:<38} {:>7} {:>6}".format("成片 A", "成片 B", "相似度", "配对帧"))
    for a, b, sim, matched in pairs:
        out.append("  {:<38} {:<38} {:>6.0%} {:>6}".format(
            Path(a).name[:36], Path(b).name[:36], sim, matched))
    out.append("")
    out.append("处理建议：")
    out.append("  1. 相似度越高的两条，越应该重新剪其中一条：换一段素材、换个切入时间点，")
    out.append("     而不是把同一条片子改个标题再发")
    out.append("  2. 同一段素材被多条复用是结构性问题：提高解说稿差异，或扩大素材来源")
    out.append("  3. 高相似度的两条不要放在同一个账号发布")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="frame_dedup.py",
        description="成片抽帧指纹查重：输出相似度矩阵，找出复用同一批画面的成片对",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", "-d", help="成片目录（递归扫描视频文件）")
    src.add_argument("--a", help="单对比较：视频 A")
    parser.add_argument("--b", help="单对比较：视频 B（与 --a 配对）")
    parser.add_argument("--frames", type=int, default=24, help="每条成片抽帧数（默认 24）")
    parser.add_argument("--hamming", type=int, default=8, help="帧判同的汉明距离阈值（默认 8/64 位）")
    parser.add_argument("--threshold", type=float, default=0.40, help="相似度告警阈值（默认 0.40）")
    parser.add_argument("--jobs", type=int, default=4, help="并发抽帧进程数（默认 4）")
    parser.add_argument("--limit", type=int, default=0, help="只分析前 N 条（0 = 全部，用于快速抽样）")
    parser.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径")
    parser.add_argument("--ffprobe", help="ffprobe 可执行文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--out", help="结果写入文件")
    parser.add_argument("--strict", action="store_true", help="存在超阈值相似对时以退出码 1 结束")
    args = parser.parse_args(argv)

    if args.a and not args.b:
        parser.error("--a 必须与 --b 一起使用")

    ffmpeg = find_binary("ffmpeg", args.ffmpeg)
    ffprobe = find_binary("ffprobe", args.ffprobe)
    if shutil.which(ffmpeg) is None and not Path(ffmpeg).is_file():
        print("找不到 ffmpeg。请安装 ffmpeg 并加入 PATH，"
              "或用 --ffmpeg 指定路径，或设置环境变量 FFMPEG_PATH。", file=sys.stderr)
        return 2

    if args.a:
        # 单对模式：必须支持 A、B 是同一条片（阳性对照），所以不能用路径做字典键去重
        files = [Path(args.a), Path(args.b)]
        for f in files:
            if not f.is_file():
                print("找不到文件：{}".format(f), file=sys.stderr)
                return 2
        labels = ["A", "B"]
        results, errors = {}, {}
        for label, path in zip(labels, files):
            hashes, duration, err = extract_hashes(path, ffmpeg, ffprobe, max(2, args.frames))
            key = "{}｜{}".format(label, path)
            if err:
                errors[key] = err
            else:
                results[key] = {"hashes": hashes, "duration": duration}
        keys = list(results)
        pairs = []
        if len(keys) == 2:
            sim, matched = similarity(results[keys[0]]["hashes"], results[keys[1]]["hashes"],
                                      args.hamming)
            pairs.append((keys[0], keys[1], sim, matched))
            if sim < args.threshold:
                pairs = []
    else:
        if not Path(args.dir).is_dir():
            print("不是目录：{}".format(args.dir), file=sys.stderr)
            return 2
        files = collect_videos(args.dir)
        if args.limit > 0:
            files = files[:args.limit]
        if not files:
            print("目录里没有视频文件：{}".format(args.dir), file=sys.stderr)
            return 2
        results, errors = analyze(files, ffmpeg, ffprobe, max(2, args.frames), max(1, args.jobs))
        keys = list(results)
        pairs = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                sim, matched = similarity(results[keys[i]]["hashes"], results[keys[j]]["hashes"],
                                          args.hamming)
                if sim >= args.threshold:
                    pairs.append((keys[i], keys[j], sim, matched))
        pairs.sort(key=lambda p: -p[2])

    if args.json:
        payload = {
            "ffmpeg": ffmpeg,
            "threshold": args.threshold,
            "frames": args.frames,
            "hamming": args.hamming,
            "videos": [{
                "path": p, "name": Path(p).name,
                "duration": round(results[p]["duration"], 2) if results[p]["duration"] else None,
                "frames": len(results[p]["hashes"]),
            } for p in keys],
            "errors": errors,
            "pairs": [{"a": a, "b": b, "similarity": round(s, 4), "matchedFrames": m}
                      for a, b, s, m in pairs],
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        rendered = render_text(results, pairs, errors, args.threshold, args.frames)

    print(rendered)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
        print("\n结果已写入：{}".format(args.out), file=sys.stderr)

    if args.strict and pairs:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
