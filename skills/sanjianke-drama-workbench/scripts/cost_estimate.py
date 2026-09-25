#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短剧制作工作台 · 成本测算（零依赖、不联网）。

按「出多少张图、生成多少秒视频、配多少字台词、做多少秒口型、要几首 BGM」估算点数与金额。
所有单价都是**参考默认值**，不是报价 —— 请把当期真实单价传进来再采信结论。

    单价默认值来源（api.a7w.cn 当期配置，会变，可自行覆盖）：
      出图   24 点/张        应用 nano_banana 的 nano-banana · 1K
      视频   20 点/秒        应用 full_video 的 1080P 档（参考口径）
      配音   50 点/千 Token  应用 voice_tts 的 tts / tts_async（租户价）
      口型    2 点/秒        应用 lipsync / image_human（参考口径）
      BGM    65 点/首        应用 music_generation 的 create

用法
    python3 cost_estimate.py --shots 15 --image 24 --duration 40 --tts-chars 1800
    python3 cost_estimate.py --duration 40 --video-points-per-sec 20 --waste 0.4
    python3 cost_estimate.py --shots 15 --json
"""

import argparse
import json

POINTS_PER_YUAN = 100          # 1 元 = 100 点
TOKENS_PER_CHAR = 1.0          # 中文粗估：1 字 ≈ 1 Token


def main():
    ap = argparse.ArgumentParser(
        description="短剧制作工作台成本测算（零依赖、不联网）。单价为参考默认值，请按当期报价覆盖。")
    ap.add_argument("--shots", type=int, default=15, help="镜头数，默认 15")
    ap.add_argument("--image", type=float, default=None,
                    help="出图张数；不传则按 镜头数 × 1.6 估算")
    ap.add_argument("--duration", type=float, default=None,
                    help="要生成的视频总秒数；不传则按 镜头数 × 5 估算")
    ap.add_argument("--tts-chars", type=float, default=None,
                    help="台词总字数；不传则按 镜头数 × 120 估算")
    ap.add_argument("--lipsync-ratio", type=float, default=0.5,
                    help="需要做口型的视频占比，默认 0.5")
    ap.add_argument("--bgm", type=int, default=1, help="BGM 首数，默认 1")
    ap.add_argument("--waste", type=float, default=0.3,
                    help="废片率（重生成比例），默认 0.3 即多备 30%%")
    ap.add_argument("--img-points", type=float, default=24.0, help="出图单价 点/张，默认 24")
    ap.add_argument("--video-points-per-sec", type=float, default=20.0,
                    help="视频单价 点/秒，默认 20（1080P 参考口径）")
    ap.add_argument("--tts-points-per-1k", type=float, default=50.0,
                    help="配音单价 点/千 Token，默认 50")
    ap.add_argument("--lipsync-points-per-sec", type=float, default=2.0,
                    help="口型单价 点/秒，默认 2")
    ap.add_argument("--bgm-points", type=float, default=65.0, help="BGM 单价 点/首，默认 65")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()

    images = a.image if a.image is not None else a.shots * 1.6
    seconds = a.duration if a.duration is not None else a.shots * 5.0
    chars = a.tts_chars if a.tts_chars is not None else a.shots * 120.0
    tokens = chars * TOKENS_PER_CHAR
    lip_seconds = seconds * a.lipsync_ratio

    items = [
        ("出图 nano_banana", images, "张", images * a.img_points),
        ("出片 full_video", seconds, "秒", seconds * a.video_points_per_sec * (1 + a.waste)),
        ("配音 voice_tts", tokens, "Token", tokens / 1000.0 * a.tts_points_per_1k),
        ("口型 lipsync / image_human", lip_seconds, "秒", lip_seconds * a.lipsync_points_per_sec),
        ("BGM music_generation", float(a.bgm), "首", a.bgm * a.bgm_points),
    ]
    total = sum(x[3] for x in items)

    if a.json:
        print(json.dumps({
            "shots": a.shots, "waste": a.waste, "lipsync_ratio": a.lipsync_ratio,
            "items": [{"app": n, "qty": round(q, 2), "unit": u, "points": round(p, 2)}
                      for n, q, u, p in items],
            "total_points": round(total, 2),
            "total_yuan": round(total / POINTS_PER_YUAN, 2),
            "per_shot_yuan": round(total / POINTS_PER_YUAN / max(a.shots, 1), 2),
        }, ensure_ascii=False, indent=1))
        return

    print("短剧制作工作台 · 成本测算（参考值，不是报价）")
    print("  规模：%d 个镜头   废片率：%.0f%%   口型覆盖率：%.0f%%"
          % (a.shots, a.waste * 100, a.lipsync_ratio * 100))
    print()
    print("  %-28s %12s %-7s %12s %10s" % ("应用 / 项目", "数量", "单位", "点数", "折合元"))
    print("  " + "-" * 76)
    for name, qty, unit, pts in items:
        print("  %-28s %12.1f %-7s %12.1f %10.2f" % (name, qty, unit, pts, pts / POINTS_PER_YUAN))
    print("  " + "-" * 76)
    print("  %-28s %12s %-7s %12.1f %10.2f" % ("合计", "", "", total, total / POINTS_PER_YUAN))
    print()
    if total > 0:
        print("  成本结构：")
        for name, _q, _u, pts in sorted(items, key=lambda x: -x[3]):
            print("    %-28s %5.1f%%" % (name, pts / total * 100))
    print()
    print("  平均每镜头：约 %.2f 元" % (total / POINTS_PER_YUAN / max(a.shots, 1)))
    print()
    print("  >> 省钱按优先级：")
    print("     1) 静态对话戏别整段生成视频 —— 用「首帧图 + 口型」，比重生成便宜得多；")
    print("     2) 复用图片资产 —— 同一角色图反复做首帧，别每镜重出；")
    print("     3) 分辨率锁在够用档 —— 竖屏短剧 720P 通常够，平台还会二次压缩。")
    print()
    print("  >> 单价是参考默认值，不是报价。请用当期真实单价覆盖后重新测算。")


if __name__ == "__main__":
    main()
