#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toonflow 出片成本估算。

默认单价按官方 Demo 反推校准（约 2 分钟成片、约 ¥130）：
    Demo：成片约 2 分钟、原始素材 3 分钟；语言模型约 ¥10、视频模型约 ¥120、图片不足 ¥1。

用法：
    python3 cost_estimate.py --minutes 2
    python3 cost_estimate.py --episodes 30 --minutes 2 --video-price 1.2
    python3 cost_estimate.py --minutes 2 --json

只做估算，不联网、不读任何外部文件。
"""
import argparse
import json
import sys

# 元/秒：视频生成。按 Demo（3 分钟素材 ≈ ¥120）反推。
DEFAULT_VIDEO_PRICE = 0.67
# 元/张：单张出图。
DEFAULT_IMAGE_PRICE = 0.02
# 元/千字：语言模型（按 15 万字 ≈ ¥10 反推）。
DEFAULT_LLM_PER_1K = 0.067


def estimate(minutes, waste, video_price, shot_seconds, image_price,
             image_per_shot, words, llm_per_1k):
    finished_sec = minutes * 60.0
    # 废片率：生成出来的素材里被剪掉的比例，成片时长要除以 (1 - 废片率)
    if waste >= 1.0:
        raise ValueError("废片率必须小于 1")
    generated_sec = finished_sec / (1.0 - waste)
    shots = finished_sec / shot_seconds if shot_seconds > 0 else 0.0

    video_cost = generated_sec * video_price
    image_cost = shots * image_per_shot * image_price
    llm_cost = words / 1000.0 * llm_per_1k

    return {
        "成片秒数": round(finished_sec, 1),
        "需生成秒数": round(generated_sec, 1),
        "分镜数（估）": round(shots, 1),
        "视频模型": round(video_cost, 2),
        "图片模型": round(image_cost, 2),
        "语言模型": round(llm_cost, 2),
        "合计": round(video_cost + image_cost + llm_cost, 2),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Toonflow 出片成本估算")
    p.add_argument("--minutes", type=float, default=2.0, help="成片总时长（分钟），默认 2")
    p.add_argument("--episodes", type=int, default=0,
                   help="集数，用于另算单集成本；0 表示不按集算")
    p.add_argument("--waste", type=float, default=0.34,
                   help="废片率 0~1，默认 0.34（官方 Demo 是原始素材 3 分钟剪成 2 分钟）；"
                        "废片多就调高，成片秒数会按 1/(1-废片率) 放大")
    p.add_argument("--video-price", type=float, default=DEFAULT_VIDEO_PRICE,
                   help="视频生成 元/秒，默认 {}".format(DEFAULT_VIDEO_PRICE))
    p.add_argument("--shot-seconds", type=float, default=3.0,
                   help="平均每镜时长（秒），默认 3")
    p.add_argument("--image-price", type=float, default=DEFAULT_IMAGE_PRICE,
                   help="单张出图 元，默认 {}".format(DEFAULT_IMAGE_PRICE))
    p.add_argument("--image-per-shot", type=float, default=1.0,
                   help="每镜出图张数（含重试），默认 1")
    p.add_argument("--words", type=float, default=150000,
                   help="原著字数，默认 15 万")
    p.add_argument("--llm-per-1k", type=float, default=DEFAULT_LLM_PER_1K,
                   help="语言模型 元/千字，默认 {}".format(DEFAULT_LLM_PER_1K))
    p.add_argument("--json", action="store_true", help="输出 JSON")
    args = p.parse_args(argv)

    try:
        r = estimate(args.minutes, args.waste, args.video_price, args.shot_seconds,
                     args.image_price, args.image_per_shot, args.words, args.llm_per_1k)
    except ValueError as e:
        print("参数错误：{}".format(e), file=sys.stderr)
        return 2

    if args.episodes > 0:
        r["集数"] = args.episodes
        r["单集成本"] = round(r["合计"] / args.episodes, 2)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    print("Toonflow 出片成本估算")
    print("=" * 42)
    for k in ("成片秒数", "需生成秒数", "分镜数（估）"):
        print("  {:<12} {}".format(k, r[k]))
    print("-" * 42)
    for k in ("视频模型", "图片模型", "语言模型"):
        pct = r[k] / r["合计"] * 100 if r["合计"] else 0
        print("  {:<12} ¥{:>9.2f}   {:>5.1f}%".format(k, r[k], pct))
    print("-" * 42)
    print("  {:<12} ¥{:>9.2f}".format("合计", r["合计"]))
    if "单集成本" in r:
        print("  {:<12} ¥{:>9.2f}   （{} 集）".format("单集成本", r["单集成本"], r["集数"]))
    print()
    print("注：按官方 Demo 校准的默认单价推算，实际以你所用模型的实时报价为准。")
    print("    视频模型通常占九成以上成本 —— 想省钱先压生成秒数，不是压图片。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
