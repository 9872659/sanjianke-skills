#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文生视频（ShortGPT 场景）—— 零安装版。

原先要用这个 Skill，得 Docker / Colab 起一套框架，再备齐脚本生成、配音、素材检索
三类外部服务的密钥。现在不需要：提示词直接提交到 api.a7w.cn 出片，
本机只要求 Python 3.8+。

用法
    python3 run.py "一只金毛犬在海边奔跑，夕阳西下" --out dog.mp4
    python3 run.py "城市清晨延时，镜头缓慢推进" --ratio 9:16 --duration 5 --out v.mp4
    python3 run.py "产品展示：白色耳机悬浮旋转" --res 1080P --out product.mp4
    python3 run.py --task-id task_xxxx --out again.mp4    # 只取已提交任务的成片，不重复花钱

配 Key（三种方式任选）
    python3 run.py "主题" --key sk-xxxx
    export A7W_API_KEY=sk-xxxx
    或在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json

视频任务又慢又贵，所以这个脚本做了两件额外的事：
    · 提交后自己轮询，**查询遇到网络抖动会自动重试**，不会因为一次连接被重置就丢任务；
    · 断线或关掉终端后，用 --task-id 可以把已提交的任务接着取回来，**不会重复扣费**。

能力边界（务必先看）
    · 走的是平台 `full_video` 应用（全能视频生成），**只覆盖「文本 → 视频」这一段**。
    · ShortGPT 原项目那条「自动写稿 + 配音 + 素材检索匹配 + 字幕对齐 + 渲染成片」
      的流水线，**平台不提供**：平台没有脚本生成、没有素材站检索、不做字幕烧入，
      也不做整片翻译配音。想要完整流水线，得自己把这里的出片结果接回 ShortGPT。
    · 单条时长 4~15 秒整数，分辨率 480P / 768P / 1080P / 2K / 4K；
      768P、1080P、2K 的文本最多 5000 字，其他分辨率最多 7000 字。
    · 计费按「分辨率 × 秒数」计量，**视频比图片贵得多**，先用 480P / 4 秒试通再放大。

计费：走平台 `full_video/submit`（异步任务），以平台实时价为准。
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "full_video"
API = "submit"
MODEL = "full-video"
RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "adaptive"]
TERMINAL = ("completed", "failed", "error", "cancelled")
RETRY_WAIT = 5


def fetch_task(key, task_id, tries=5):
    """查一次任务状态；网络抖动（连接被重置、超时）时重试，不让付费任务白丢。"""
    last = None
    for i in range(tries):
        try:
            return a7w._unwrap(a7w._request(
                "GET", "{}/api/v1/tasks/{}".format(a7w.HOST, task_id), key))
        except a7w.A7wError as exc:
            last = exc
            if i < tries - 1:
                sys.stderr.write("  查询失败：{}　{} 秒后重试…\n".format(exc, RETRY_WAIT))
                time.sleep(RETRY_WAIT)
    raise last


def wait_task(key, task_id, timeout=a7w.POLL_TIMEOUT):
    """轮询到任务结束。中途断线只在 fetch_task 内部重试，绝不重新提交。"""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        time.sleep(a7w.POLL_INTERVAL)
        t = fetch_task(key, task_id)
        status = a7w.dig(t, "status")
        if status != last:
            sys.stderr.write("  状态：{}\n".format(status))
            last = status
        if status in TERMINAL:
            if status != "completed":
                raise a7w.A7wError("任务未成功：{}  {}".format(
                    status, a7w.dig(t, "error") or ""))
            return {"task_id": task_id, "status": status,
                    "result": a7w.dig(t, "result"), "usage": a7w.dig(t, "usage")}
    raise a7w.A7wError(
        "轮询超时。任务可能还在跑，用 --task-id {} 接着取，不要重新提交。".format(task_id))


def pick_video(result):
    """任务结果里挑出视频地址——返回字段不完全一致，逐个试。"""
    if not isinstance(result, dict):
        return None
    for path in (("data", "video_url"), ("data", "videoUrl"), ("data", "url"),
                 ("video_url",), ("videoUrl",), ("url",),
                 ("output", "video_url"), ("result", "video_url")):
        v = a7w.dig(result, *path)
        if v:
            return v
    for key in ("videos", "outputs"):
        seq = a7w.dig(result, key) or a7w.dig(result, "data", key)
        if isinstance(seq, list) and seq:
            first = seq[0]
            return first if isinstance(first, str) else (first or {}).get("url")
    return None


def main():
    ap = argparse.ArgumentParser(
        prog="run.py", description="文生视频（走 api.a7w.cn，零安装）")
    ap.add_argument("prompt", nargs="?", help="主题 / 画面提示词：主体、动作、镜头、光线、风格")
    ap.add_argument("--task-id", metavar="ID",
                    help="已有任务的 ID：只轮询并下载，不重新提交（断线后续取，不会再扣一次费）")
    ap.add_argument("--out", default="output.mp4", help="保存路径")
    ap.add_argument("--ratio", default="16:9", choices=RATIOS, help="画幅比例")
    ap.add_argument("--duration", type=int, default=4, metavar="秒",
                    help="时长，4~15 秒整数，默认 4（越长约贵）")
    ap.add_argument("--res", default="480P", choices=RESOLUTIONS,
                    help="输出分辨率，默认 480P（越清晰越贵）")
    ap.add_argument("--watermark", action="store_true", help="加上生成标识（AIGC 水印）")
    ap.add_argument("--key", help="临时指定 API Key")
    a = ap.parse_args()

    if not a.prompt and not a.task_id:
        ap.error("请给一段提示词；或用 --task-id 取回已提交的任务")
    try:
        key = a7w.load_key(a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    try:
        if a.task_id:
            sys.stderr.write("接着取任务 {}（不重新提交）…\n".format(a.task_id))
            res = wait_task(key, a.task_id)
        else:
            if not (4 <= a.duration <= 15):
                ap.error("--duration 只支持 4 到 15 秒的整数，当前 {}".format(a.duration))
            prompt = a.prompt.strip()
            if not prompt:
                ap.error("提示词不能为空")
            body = {
                "model": MODEL,
                "ratio": a.ratio,
                "resolution": a.res,
                "duration": a.duration,
                "aigc_watermark": bool(a.watermark),
                "content": [{"type": "text", "text": prompt}],
            }
            sys.stderr.write("分辨率={} 比例={} 时长={}s 水印={}\n".format(
                a.res, a.ratio, a.duration, "开" if a.watermark else "关"))
            sub = a7w.call(APP, API, body, key=key, wait=False)
            task_id = a7w.dig(sub, "task_id")
            if not task_id:
                # 少数情况下平台直接同步返回了结果
                res = sub if isinstance(sub, dict) else {}
            else:
                sys.stderr.write("task_id={} 已提交，等待完成…\n".format(task_id))
                res = wait_task(key, task_id)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4

    url = pick_video(res.get("result") if isinstance(res, dict) else None)
    cost = a7w.dig(res, "usage", "points_cost")
    task_id = a7w.dig(res, "task_id") or a.task_id
    if not url:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.stderr.write("任务完成但没从返回里找到视频地址，上面是原始返回。"
                         "如已扣费，用 --task-id {} 可以再取一次。\n".format(task_id or "?"))
        return 5

    try:
        a7w.save(url, a.out)
    except a7w.A7wError as exc:
        sys.stderr.write("出片成功但下载失败：{}（地址：{}）\n".format(exc, url))
        return 6

    sys.stderr.write("已保存 {}{}\n".format(
        a.out, "  消耗 {} 点".format(cost) if cost else ""))
    print(json.dumps({"ok": True, "out": str(Path(a.out).resolve()), "url": url,
                      "task_id": task_id, "model": MODEL, "resolution": a.res,
                      "ratio": a.ratio, "duration": a.duration,
                      "points_cost": cost}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
