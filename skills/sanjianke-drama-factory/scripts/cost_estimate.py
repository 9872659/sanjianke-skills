#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短剧出片成本测算 · 零依赖、不联网。

按「一集有多少个片段、片段多长、出图多少张、配音多少字」估算点数与金额。
所有单价都是**参考默认值**，不是报价 —— 请把当期真实单价传进来再采信结论。

    单价默认值来源（api.a7w.cn 当期配置，会变，可自行覆盖）：
      出图      24 点/张        应用 nano_banana 的 nano-banana · 1K
      视频      20 点/秒        应用 full_video 的 1080P 档（参考口径）
      配音      50 点/千 Token  应用 voice_tts 的 tts / tts_async（租户价）
      口型      2 点/秒         应用 lipsync / image_human（参考口径）
      BGM       65 点/首        应用 music_generation 的 create

用法
    python3 cost_estimate.py --episodes 30 --minutes 2
    python3 cost_estimate.py --minutes 2 --video-points-per-sec 20 --waste 0.4
    python3 cost_estimate.py --episodes 30 --minutes 2 --json
"""

import argparse
import json

POINTS_PER_YUAN = 100          # 1 元 = 100 点

# 每 1 分钟成片的内容密度（可按你的分镜习惯调整）
CLIPS_PER_MINUTE = 7.5         # 2 分钟一集约 15 个片段
IMAGES_PER_CLIP = 1.6          # 每个片段约 1.6 张图（首帧 + 角色图摊薄）
CHARS_PER_MINUTE = 900         # 2 分钟一集约 1800 字台词
TOKENS_PER_CHAR = 1.0          # 中文粗估：1 字 ≈ 1 Token


def estimate(episodes, minutes, args):
    clips_total = episodes * minutes * CLIPS_PER_MINUTE
    seconds_total = episodes * minutes * 60.0
    images_total = clips_total * IMAGES_PER_CLIP
    chars_total = episodes * minutes * CHARS_PER_MINUTE
    tts_tokens = chars_total * TOKENS_PER_CHAR

    img = images_total * args.img_points
    video = seconds_total * args.video_points_per_sec * (1.0 + args.waste)
    tts = tts_tokens / 1000.0 * args.tts_points_per_1k
    lipsync = seconds_total * args.lipsync_points_per_sec * args.lipsync_ratio
    bgm = episodes * args.bgm_points

    items = [
        ("出图（角色图 / 首帧）", images_total, "张", img),
        ("视频生成", seconds_total, "秒", video),
        ("配音（文字转语音）", tts_tokens, "Token", tts),
        ("口型 / 数字人", seconds_total * args.lipsync_ratio, "秒", lipsync),
        ("背景音乐", float(episodes), "首", bgm),
    ]
    total = sum(x[3] for x in items)
    return items, total


def main():
    ap = argparse.ArgumentParser(
        description="短剧出片成本测算（零依赖、不联网）。单价为参考默认值，请按当期报价覆盖。")
    ap.add_argument("--episodes", type=int, default=1, help="集数，默认 1")
    ap.add_argument("--minutes", type=float, default=2.0, help="单集时长（分钟），默认 2")
    ap.add_argument("--waste", type=float, default=0.3,
                    help="废片率（重生成比例），默认 0.3 即多备 30%%")
    ap.add_argument("--lipsync-ratio", type=float, default=0.5,
                    help="需要做口型的片段占比，默认 0.5")
    ap.add_argument("--img-points", type=float, default=24.0, help="出图单价 点/张，默认 24")
    ap.add_argument("--video-points-per-sec", type=float, default=20.0,
                    help="视频单价 点/秒，默认 20（1080P 参考口径）")
    ap.add_argument("--tts-points-per-1k", type=float, default=50.0,
                    help="配音单价 点/千 Token，默认 50")
    ap.add_argument("--lipsync-points-per-sec", type=float, default=2.0,
                    help="口型单价 点/秒，默认 2")
    ap.add_argument("--bgm-points", type=float, default=65.0, help="BGM 单价 点/首，默认 65")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    items, total = estimate(args.episodes, args.minutes, args)

    if args.json:
        print(json.dumps({
            "episodes": args.episodes,
            "minutes": args.minutes,
            "waste": args.waste,
            "items": [{"name": n, "qty": round(q, 2), "unit": u, "points": round(p, 2)}
                      for n, q, u, p in items],
            "total_points": round(total, 2),
            "total_yuan": round(total / POINTS_PER_YUAN, 2),
            "per_episode_yuan": round(total / POINTS_PER_YUAN / max(args.episodes, 1), 2),
        }, ensure_ascii=False, indent=1))
        return

    print("短剧出片成本测算（参考值，不是报价）")
    print("  规模：%s 集 × %s 分钟   废片率：%.0f%%" % (args.episodes, args.minutes, args.waste * 100))
    print()
    print("  %-24s %14s %-7s %12s %10s" % ("项目", "数量", "单位", "点数", "折合元"))
    print("  " + "-" * 72)
    for name, qty, unit, pts in items:
        print("  %-24s %14.1f %-7s %12.1f %10.2f" % (name, qty, unit, pts, pts / POINTS_PER_YUAN))
    print("  " + "-" * 72)
    print("  %-24s %14s %-7s %12.1f %10.2f" % ("合计", "", "", total, total / POINTS_PER_YUAN))
    print()
    if total > 0:
        print("  成本结构：")
        for name, _q, _u, pts in sorted(items, key=lambda x: -x[3]):
            print("    %-24s %5.1f%%" % (name, pts / total * 100))
    print()
    print("  单集：约 %.2f 元" % (total / POINTS_PER_YUAN / max(args.episodes, 1)))
    print()
    print("  >> 省钱的两个有效方向，按优先级：")
    print("     1) 减少要生成的视频秒数 —— 减镜头、复用镜头、拉长单镜头、")
    print("        把静态对话改成图片 + 口型（视频通常占总额八成）；")
    print("     2) 复用图片资产 —— 同一角色图反复做首帧，别每镜重出。")
    print()
    print("  >> 单价是参考默认值，不是报价。请用当期真实单价覆盖后重新测算。")


if __name__ == "__main__":
    main()
