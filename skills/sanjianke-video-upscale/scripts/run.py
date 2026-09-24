#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频超分执行器 —— 两条路线。

  路线 api   走 api.a7w.cn 的 flashvsr 插件（需要公网可访问的视频 URL + API Key）
  路线 local 本地 ffmpeg：降噪去块 → lanczos 放大 → 自适应锐化（离线、零成本）

用法：

  # 路线一：在线超分（走 api.a7w.cn）
  python3 run.py --route api --url https://example.com/low.mp4
  python3 run.py --route api --url https://example.com/low.mp4 --out out.mp4
  python3 run.py --route api --url https://example.com/low.mp4 --no-wait   # 只提交

  # 路线二：本地增强（不花钱，但造不出细节）
  python3 run.py --route local input.mp4
  python3 run.py --route local *.mp4 --level 2 --height 1080 --out ./done

  # 只想看视频信息
  python3 run.py --probe input.mp4
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import a7w
except ImportError:
    a7w = None

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

# 实测可用的两条滤镜链（来自我们线上的转档与增强脚本）
FILTERS = {
    1: "hqdn3d=1.0:1.0:4:4,scale=-2:{h}:flags=lanczos,cas=0.35",
    2: ("deblock=filter=weak:block=8,hqdn3d=1.5:1.5:6:6,"
        "scale=-2:{h}:flags=lanczos,cas=0.5,unsharp=5:5:0.6:5:5:0.0"),
}

# 视频超分单条时长上限（在线站与平台侧一致）
MAX_DURATION = 30


def which(name):
    return shutil.which(name)


def ffprobe_json(path):
    """返回 {width, height, duration, has_audio}；探测失败返回 {}。"""
    if not which(FFPROBE):
        return {}
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", str(path)],
            capture_output=True, text=True, timeout=120).stdout
        d = json.loads(out)
    except Exception:
        return {}
    info = {"width": 0, "height": 0, "duration": 0.0, "has_audio": False, "codec": ""}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and not info["width"]:
            info["width"] = int(s.get("width") or 0)
            info["height"] = int(s.get("height") or 0)
            info["codec"] = s.get("codec_name") or ""
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
    try:
        info["duration"] = float((d.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        pass
    return info


def fmt_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f TB" % n


def do_probe(paths):
    for p in paths:
        info = ffprobe_json(p)
        if not info:
            print("%s：探测失败（没装 ffprobe？）" % p)
            continue
        sz = os.path.getsize(p) if os.path.isfile(p) else 0
        print("%s" % p)
        print("   分辨率 : %dx%d" % (info["width"], info["height"]))
        print("   时长   : %.2f 秒" % info["duration"])
        print("   编码   : %s" % (info["codec"] or "未知"))
        print("   音轨   : %s" % ("有" if info["has_audio"] else "无"))
        print("   体积   : %s" % fmt_size(sz))
        if info["height"] >= 2160:
            print("   ⚠️  源片已达 4K，再超分不会有提升")
        if info["duration"] > MAX_DURATION:
            print("   ⚠️  超过 %d 秒，走在线/AI 路线会直接被拒，需先切片" % MAX_DURATION)
        print()


def run_ffmpeg(cmd, timeout=4 * 3600):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg 超时（>%ds）" % timeout)
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError("ffmpeg 失败：\n    " + "\n    ".join(tail))
    return r


def route_local(files, out_dir, level, height, crf, threads, quiet):
    if not which(FFMPEG):
        print("找不到 ffmpeg。装一个再来：", file=sys.stderr)
        print("  Windows: winget install Gyan.FFmpeg", file=sys.stderr)
        print("  macOS  : brew install ffmpeg", file=sys.stderr)
        print("  Linux  : apt install ffmpeg", file=sys.stderr)
        return 2

    vf = FILTERS[level].format(h=height)
    out_dir = Path(out_dir) if out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    ok = fail = 0
    for f in files:
        src = Path(f)
        if not src.is_file():
            print("跳过（文件不存在）：%s" % f, file=sys.stderr)
            fail += 1
            continue

        info = ffprobe_json(src)
        if info and info["height"] >= height:
            print("⚠️  %s 已经是 %dp，目标 %dp —— 放大不会增加真实细节"
                  % (src.name, info["height"], height))

        dst = (out_dir / (src.stem + "_up%d.mp4" % height)) if out_dir \
            else src.with_name(src.stem + "_up%d.mp4" % height)

        cmd = [FFMPEG, "-y", "-hide_banner", "-nostdin",
               "-i", str(src), "-vf", vf,
               "-c:v", "libx264", "-preset", "veryfast",
               "-threads", str(threads),
               "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if info.get("has_audio"):
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-an"]
        cmd += ["-movflags", "+faststart", str(dst)]

        if not quiet:
            print("→ %s" % src.name)
            print("  滤镜 : %s" % vf)
            print("  输出 : %s" % dst)
        try:
            run_ffmpeg(cmd)
        except RuntimeError as e:
            print("  ✗ %s" % e, file=sys.stderr)
            fail += 1
            continue

        # 产物校验：小于 10 KB 一律判失败（空文件被当成功是最坑的）
        if not dst.exists() or dst.stat().st_size < 10240:
            print("  ✗ 产物异常（文件过小或不存在），已删除", file=sys.stderr)
            if dst.exists():
                dst.unlink()
            fail += 1
            continue

        print("  ✓ %s（%s）" % (dst.name, fmt_size(dst.stat().st_size)))
        ok += 1

    print("\n成功 %d，失败 %d" % (ok, fail))
    return 0 if fail == 0 else 1


def route_api(url, out, key, wait, quiet, timeout):
    if a7w is None:
        print("找不到同目录的 a7w.py，无法走 API 路线。", file=sys.stderr)
        return 2
    if not url.startswith(("http://", "https://")):
        print("--url 必须是公网可访问的 HTTP/HTTPS 地址；本地文件请先上传，"
              "或改用 --route local", file=sys.stderr)
        return 2

    body = {"input_url": url}
    try:
        res = a7w.call("flashvsr", "submit", body, key=key, wait=wait,
                       timeout=timeout, quiet=quiet)
    except Exception as e:
        print("提交失败：%s" % e, file=sys.stderr)
        return 1

    if not wait:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    result = res.get("result") if isinstance(res, dict) else None
    print(json.dumps(res, ensure_ascii=False, indent=2)[:1200])

    # 上游返回结构偶有差异，按常见键逐个找
    vurl = None
    if a7w is not None:
        for k in ("video_url", "output_url", "url", "result_url", "output"):
            vurl = a7w.dig(result, k) or vurl
            if vurl:
                break
    if out:
        if not vurl:
            print("没在返回里找到可下载的视频地址，无法保存。上面是完整返回。",
                  file=sys.stderr)
            return 1
        a7w.save(vurl, out)
        print("已保存：%s（%s）" % (out, fmt_size(os.path.getsize(out))))
    elif vurl:
        print("成片地址：%s" % vurl)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="视频超分执行器：走 api.a7w.cn，或用本地 ffmpeg 增强",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--route", choices=("api", "local"), help="路线")
    ap.add_argument("files", nargs="*", help="路线 local：待处理的视频文件")
    ap.add_argument("--url", help="路线 api：公网可访问的视频地址")
    ap.add_argument("--out", help="api 路线为输出文件；local 路线为输出目录")
    ap.add_argument("--key", help="api.a7w.cn 的 API Key（默认读 ~/.a7w/config.json）")
    ap.add_argument("--level", type=int, choices=(1, 2), default=1,
                    help="local 路线强度：1 温和（默认）／2 强力")
    ap.add_argument("--height", type=int, default=1920, help="local 路线目标高度，默认 1920")
    ap.add_argument("--crf", type=int, default=18, help="local 路线质量，默认 18（越小越好）")
    ap.add_argument("--threads", type=int, default=1,
                    help="每进程线程数。实测 2 核机器用 1 更快（默认 1）")
    ap.add_argument("--no-wait", action="store_true", help="api 路线：只提交不轮询")
    ap.add_argument("--timeout", type=int, default=1800, help="api 路线轮询超时（秒）")
    ap.add_argument("--probe", action="store_true", help="只探测视频信息，不做处理")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.probe:
        if not args.files:
            ap.error("--probe 需要至少一个文件")
        do_probe(args.files)
        return 0

    if not args.route:
        ap.error("必须指定 --route api 或 --route local")

    if args.route == "local":
        if not args.files:
            ap.error("路线 local 需要至少一个视频文件")
        return route_local(args.files, args.out, args.level, args.height,
                           args.crf, args.threads, args.quiet)

    if not args.url:
        ap.error("路线 api 需要 --url")
    return route_api(args.url, args.out, args.key, not args.no_wait,
                     args.quiet, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
