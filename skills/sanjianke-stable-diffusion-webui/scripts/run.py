#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文生图 / 图生图 —— 零安装版。

原先要用这个 Skill，得装 WebUI、配 Python 环境、下几个 G 的模型、还要有显卡。
现在不需要：提示词直接提交到 api.a7w.cn 出图，本机只要求 Python 3.8+。

用法
    python3 run.py "一只穿宇航服的柴犬，棚拍，白背景" --out dog.png
    python3 run.py "赛博朋克城市夜景" --ratio 16:9 --res 2K --out city.png
    python3 run.py --edit https://example.com/room.jpg "把白天改成黄昏" --out dusk.png
    python3 run.py "产品图" --model nano-banana-pro --res 4K --out pro.png

配 Key（三种方式任选）
    python3 run.py "提示词" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json

说明
    · 走的是平台 `nano_banana` 应用（文生图 / 图生图 / 多规格模型）
    · 异步任务，脚本会自动轮询到出图再下载
    · `--edit` 的参考图必须是**公网可访问的 URL**（平台按 URL 取图）
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "nano_banana"
API = "submit"
MODELS = ["nano-banana", "nano-banana-2", "nano-banana-2-lite", "nano-banana-pro",
          "nano-banana:official", "nano-banana-2-lite:official",
          "nano-banana-2:official", "nano-banana-pro:official"]
RATIOS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
          "5:4", "4:5", "21:9"]


def pick_url(result):
    """任务结果里挑出图片地址——不同模型返回字段不完全一致，逐个试。"""
    if not isinstance(result, dict):
        return None
    for path in (("data", "image_url"), ("data", "imageUrl"), ("data", "url"),
                 ("image_url",), ("imageUrl",), ("url",)):
        v = a7w.dig(result, *path)
        if v:
            return v
    imgs = a7w.dig(result, "data", "images") or a7w.dig(result, "images")
    if isinstance(imgs, list) and imgs:
        first = imgs[0]
        return first if isinstance(first, str) else (first or {}).get("url")
    return None


def main():
    ap = argparse.ArgumentParser(description="文生图 / 图生图（走 api.a7w.cn，零安装）")
    ap.add_argument("prompt", help="画面描述：主体、风格、光线、构图、细节")
    ap.add_argument("--edit", metavar="参考图URL",
                    help="图生图：给一张公网参考图 URL，做编辑而非从零生成")
    ap.add_argument("--model", default="nano-banana", choices=MODELS, help="模型规格")
    ap.add_argument("--res", default="1K", choices=["1K", "2K", "4K"], help="输出分辨率")
    ap.add_argument("--ratio", default="auto", choices=RATIOS, help="宽高比")
    ap.add_argument("-o", "--out", default="output.png", help="保存路径")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    body = {"prompt": a.prompt, "model": a.model, "resolution": a.res}
    if a.ratio and a.ratio != "auto":
        body["aspect_ratio"] = a.ratio
    if a.edit:
        body["action"] = "edit"
        body["image_urls"] = [a.edit]

    sys.stderr.write("模型={} 分辨率={} 比例={} 模式={}\n".format(
        a.model, a.res, a.ratio, "图生图" if a.edit else "文生图"))
    try:
        res = a7w.call(APP, API, body, key=a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    url = pick_url(res.get("result") if isinstance(res, dict) else None)
    cost = a7w.dig(res, "usage", "points_cost")
    if not url:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.stderr.write("任务完成但没从返回里找到图片地址，上面是原始返回。\n")
        return 5

    try:
        a7w.save(url, a.out)
    except a7w.A7wError as exc:
        sys.stderr.write("出图成功但下载失败：{}（地址：{}）\n".format(exc, url))
        return 6

    sys.stderr.write("已保存 {}{}\n".format(
        a.out, "  消耗 {} 点".format(cost) if cost else ""))
    print(json.dumps({"ok": True, "out": str(Path(a.out).resolve()),
                      "url": url, "model": a.model, "resolution": a.res,
                      "points_cost": cost}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
