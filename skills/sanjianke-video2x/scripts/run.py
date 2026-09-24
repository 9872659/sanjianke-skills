#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频超分 / 补帧 —— 零安装版（提交弹性任务 + 轮询结果）。

原先要用这个 Skill，得先满足一串硬条件：CPU 支持 AVX2、GPU 支持 Vulkan、
装好驱动、下 Real-ESRGAN / Real-CUGAN / RIFE / Anime4K 的模型，或者干脆
上 Docker + GPU 运行时。机器不达标就是跑不起来。

现在本机只要求 Python 3.8+：超分任务提交到 api.a7w.cn 的弹性算力上跑，
本机不再需要显卡和 Vulkan。

=====================  必读前提（一条条都是实测的）  =====================

【1】schema 里 `flashvsr/submit` **没有任何参数**：required 为空、properties 为空；
     `flashvsr/query` 同样没有参数（只有固定 0.1 点的查询费）。
     平台文档原话：「需平台侧【弹性部署】对应应用配置默认策略后，调用本接口创建
     `ai_elastic_task`」。输入视频从哪来、放大倍数多少、走哪个模型，
     **主要由平台侧那份默认策略决定**。

【2】但后端实际上认字段——这一点 schema 里看不出来，是实测出来的：
     · `{"url": "<可探测的媒体地址>"}`  → 提交成功，返回 task_id，并冻结点数
     · `{"duration": <秒数>}`           → 提交成功，返回 task_id，并冻结点数
     · 空 body / `{"video":...}` / `{"src":...}` → 被拒：
       「未在请求中找到可用的时长字段（如 duration）或可探测的媒体地址，无法按输入时长计费。」
     所以本脚本把 `--url` 与 `--duration` 做成了正式参数（而不是只让你手写 --json）。

【3】即使提交成功，**查询阶段实测会返回失败**：
     `flashvsr/query` 的响应是「任务处理失败，请稍后重试」。
     本次交付时用 `{"url": "https://download.samplelib.com/mp4/sample-5s.mp4"}`
     与 `{"duration": 10}` 各提交了一次，都拿到了 task_id
     （task_89a79ef175b0fcbdb5696e14 / task_2e2018ceb1a52b89de52b294），
     随后查询两个都是「任务处理失败」。
     **这说明弹性后端没有真正跑起来——前置条件就是平台侧那份弹性部署策略还没配。**
     本脚本如实把这条报出来，不编造成功输出。

用法
    python3 run.py --url https://example.com/in.mp4   # 提交超分任务并轮询到结束
    python3 run.py --duration 10                      # 只给输入时长（用于计费）
    python3 run.py --url ... --no-wait                # 只提交，立刻返回 task_id
    python3 run.py --task-id task_xxxx                # 续取已提交的任务（不重复扣费）
    python3 run.py --task-id task_xxxx --out up.mp4   # 取回成片并下载到本地
    python3 run.py --json '{"url":"https://...","scale":2}'   # 透传任意额外字段

第一次使用需要配 Key（三种方式任选）：
    python3 run.py --url ... --key sk-xxxx
    set A7W_API_KEY=sk-xxxx            # Windows；Linux/macOS 用 export
    或在 https://api.a7w.cn/ 注册后把 Key 写入 ~/.a7w/config.json

视频任务又慢又贵，所以这个脚本额外做了两件事：
    · 查询失败（网络抖动、网关重置连接）会自动重试若干次，不会因为一次抖动丢任务；
    · 断线或关掉终端后，用 --task-id 可以把已提交的任务接着取回来，**不会重复扣费**。

计费：`flashvsr/submit` 按输入媒体时长计费（实测 5 秒的素材冻结 23.04 点、
      `--duration 10` 冻结 40 点，以平台实时价为准）；
      `flashvsr/query` 固定 0.1 点/次。别拿查询费去估总价。

能力边界（平台接口做不到的）
    · 不能选超分模型：Anime4K / Real-ESRGAN / Real-CUGAN / RIFE 这些档位是本地
      推理才有的选项；平台侧用固定策略，本脚本没有 --model 参数。
    · 不能指定放大倍数、编码器、码率、GOP、像素格式等本地参数（同上，由平台侧策略定）。
    · 不做补帧倍数、场景切换阈值的细调。
    · 不做剪辑、拼接、转场、调速、语音识别——它只做超分/补帧。
    · 不负责修复解码不了的源视频。
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

APP = "flashvsr"
SLUG = "sanjianke-video2x"
RETRY_WAIT = 5                     # 查询失败后的重试等待秒数
QUERY_TRIES = 4                    # 单次查询最多尝试次数
PENDING_LIMIT = 6                  # 连续这么多次查询都失败就判定任务失败
ELASTIC_HINT = ("如果一直失败：这是平台侧的问题，不是脚本的问题——"
                "flashvsr 需要一个已经配好默认策略的「弹性部署」，"
                "输入视频、放大倍数与模型都由那份策略决定。"
                "请先在平台侧把弹性部署配好，或改用 https://vr.a7w.cn/ 的在线超分。")


def api(api_name, body, key):
    """裸调一个接口并解信封——不走 a7w.call 的自动轮询。

    原因：这个 app 有自己的 `query` 接口，轮询节奏由本脚本控制，
    不能让 a7w.call 把 query 返回里可能带上的 task_id 又拿去二次轮询。
    """
    key = a7w.load_key(key)
    url = "{}/api/v1/apps/{}/{}".format(a7w.HOST, APP, api_name)
    return a7w._unwrap(a7w._request("POST", url, key, body=body or {}))


def query_task(task_id, key, tries=QUERY_TRIES, interval=RETRY_WAIT, quiet=False):
    """查一次任务：网络抖动或网关重置连接时重试，绝不用重新提交来「重试」。"""
    last = None
    for i in range(tries):
        try:
            return api("query", {"task_id": task_id}, key)
        except a7w.A7wError as exc:
            last = exc
            if i < tries - 1:
                if not quiet:
                    sys.stderr.write("  查询失败：{}　{} 秒后重试（{}/{}）…\n".format(
                        exc, interval, i + 1, tries - 1))
                time.sleep(interval)
    raise last


def pick_video_url(result):
    """从结果里挑出视频地址——字段名各 app 不完全一致，逐个试。"""
    if not isinstance(result, dict):
        return None
    for path in (("video_url",), ("videoUrl",), ("url",),
                 ("data", "video_url"), ("data", "videoUrl"), ("data", "url"),
                 ("output", "video_url")):
        v = a7w.dig(result, *path)
        if isinstance(v, str) and v:
            return v
    for name in ("videos", "outputs"):
        seq = a7w.dig(result, name) or a7w.dig(result, "data", name)
        if isinstance(seq, list) and seq:
            first = seq[0]
            return first if isinstance(first, str) else (first or {}).get("url")
    return None


def status_of(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get("status") or a7w.dig(payload, "data", "status")


def result_of(payload):
    return a7w.dig(payload, "result") or a7w.dig(payload, "data", "result")


def usage_of(payload):
    return a7w.dig(payload, "usage") or a7w.dig(payload, "data", "usage")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="视频超分 / 补帧：提交弹性算力任务并轮询结果（走 api.a7w.cn，零安装）",
        epilog="前提：平台侧需为 flashvsr 配好『弹性部署』默认策略。"
               "详见 SKILL.md 的「零安装用法」与「能力边界」。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", metavar="媒体地址",
                    help="待超分视频的公网 HTTP(S) 地址（平台会探测它拿时长用于计费）")
    ap.add_argument("--duration", type=float, metavar="秒",
                    help="只告诉平台输入时长（用于计费），不传媒体地址时用")
    ap.add_argument("--task-id", metavar="ID",
                    help="已有任务的 ID：只轮询并取回结果，不重新提交（断线后续取，不会再扣一次费）")
    ap.add_argument("--json", dest="body", metavar="JSON",
                    help="透传给 submit 的额外 JSON 字段（与 --url/--duration 合并，后者优先）")
    ap.add_argument("--no-wait", action="store_true", help="提交后立即返回 task_id，不轮询")
    ap.add_argument("--interval", type=float, default=float(a7w.POLL_INTERVAL),
                    help="轮询间隔秒数，默认 %(default)s")
    ap.add_argument("--retries", type=int, default=QUERY_TRIES,
                    help="单次查询失败时的重试次数，默认 %(default)s")
    ap.add_argument("--timeout", type=float, default=float(a7w.POLL_TIMEOUT),
                    help="轮询上限秒数，默认 %(default)s")
    ap.add_argument("--out", metavar="文件", help="把结果视频下载到本地路径")
    ap.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")
    return ap


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


def main():
    ap = build_parser()
    a = ap.parse_args()

    body = {}
    if a.body:
        try:
            body = json.loads(a.body)
        except ValueError as exc:
            ap.error("--json 不是合法 JSON：{}".format(exc))
        if not isinstance(body, dict):
            ap.error("--json 必须是一个 JSON 对象（花括号包起来）")
    if a.url:
        body["url"] = a.url
    if a.duration is not None:
        body["duration"] = a.duration
    if not a.task_id and not body:
        ap.error("请给 --url（待超分视频的公网地址）或 --duration（输入时长秒数）；"
                 "想续取已提交的任务就用 --task-id。\n"
                 "注：flashvsr/submit 的 schema 里没有参数，但后端实测认 url 与 duration。")

    task_id = a.task_id
    submit_response = None

    if not task_id:
        sys.stderr.write("提交 flashvsr 弹性任务，body={}\n".format(
            json.dumps(body, ensure_ascii=False)))
        sys.stderr.write("前提提醒：输入视频/放大倍数/模型由平台侧『弹性部署』默认策略决定；"
                         "该策略没配好，任务会在平台侧失败。\n")
        try:
            submit_response = api("submit", body, a.key)
        except a7w.A7wError as exc:
            sys.stderr.write("提交失败：{}\n".format(exc))
            sys.stderr.write(ELASTIC_HINT + "\n")
            emit({"ok": False, "slug": SLUG, "stage": "submit", "task_id": None,
                  "error": str(exc), "body": body, "hint": ELASTIC_HINT})
            return 4
        task_id = (submit_response or {}).get("task_id")
        st = status_of(submit_response)
        frozen = a7w.dig(submit_response, "frozen_points")
        sys.stderr.write("已提交：task_id={} status={}{}\n".format(
            task_id if task_id is not None else "(无)", st,
            " 冻结 {} 点".format(frozen) if frozen else ""))
        if not task_id:
            sys.stderr.write("平台没返回 task_id。原始返回：\n{}\n".format(
                json.dumps(submit_response, ensure_ascii=False, indent=2)))
            emit({"ok": False, "slug": SLUG, "stage": "submit", "task_id": None,
                  "status": st, "submit_response": submit_response,
                  "hint": ELASTIC_HINT})
            return 5

    if a.no_wait:
        emit({"ok": True, "slug": SLUG, "task_id": task_id, "status": "submitted",
              "submit_response": submit_response,
              "note": "已提交未等待；用 --task-id {} 稍后续取".format(task_id)})
        return 0

    sys.stderr.write("轮询 flashvsr/query，间隔 {} 秒，上限 {} 秒，单次查询最多试 {} 次…\n"
                     .format(a.interval, a.timeout, a.retries))
    deadline = time.time() + a.timeout
    last_status = None
    payload = None
    consecutive_fail = 0
    last_err = None

    while True:
        try:
            payload = query_task(task_id, a.key, tries=a.retries)
            consecutive_fail = 0
            last_err = None
        except a7w.A7wError as exc:
            consecutive_fail += 1
            last_err = str(exc)
            sys.stderr.write("  第 {} 次查询连续失败：{}\n".format(consecutive_fail, exc))
            if consecutive_fail >= PENDING_LIMIT:
                sys.stderr.write("连续 {} 次查询都失败，判定任务侧不可用。{}\n".format(
                    consecutive_fail, ELASTIC_HINT))
                emit({"ok": False, "slug": SLUG, "stage": "query", "task_id": task_id,
                      "status": "failed", "error": last_err,
                      "submit_response": submit_response, "hint": ELASTIC_HINT})
                return 7
            if time.time() >= deadline:
                break
            time.sleep(a.interval)
            continue

        st = status_of(payload)
        if st != last_status:
            sys.stderr.write("  状态：{}\n".format(st))
            last_status = st
        if st in a7w.TERMINAL:
            break
        if time.time() >= deadline:
            sys.stderr.write("轮询超时。任务可能还在跑，用 --task-id {} 接着取，"
                             "不要重新提交。\n".format(task_id))
            emit({"ok": False, "slug": SLUG, "stage": "poll", "task_id": task_id,
                  "status": st, "last_response": payload,
                  "hint": "轮询超时；用 --task-id {} 继续取，别重新提交".format(task_id)})
            return 6
        time.sleep(a.interval)

    if last_status is None and last_err:
        sys.stderr.write("查询始终失败，一直没拿到任务状态：{}\n{}\n".format(
            last_err, ELASTIC_HINT))
        emit({"ok": False, "slug": SLUG, "stage": "query", "task_id": task_id,
              "status": "unknown", "error": last_err,
              "submit_response": submit_response, "hint": ELASTIC_HINT})
        return 9

    if last_status != "completed":
        err = (a7w.dig(payload, "error") or a7w.dig(payload, "message")
               or a7w.dig(payload, "data", "error") or last_err)
        sys.stderr.write("任务未成功：{}  {}\n{}\n".format(last_status, err or "", ELASTIC_HINT))
        emit({"ok": False, "slug": SLUG, "title": "任务未成功", "task_id": task_id,
              "status": last_status, "error": err, "response": payload,
              "submit_response": submit_response, "hint": ELASTIC_HINT})
        return 7

    result = result_of(payload)
    usage = usage_of(payload)
    url = pick_video_url(result)
    saved = None
    if a.out:
        if url:
            try:
                a7w.save(url, a.out)
                saved = str(Path(a.out).resolve())
                sys.stderr.write("已保存 {}\n".format(saved))
            except a7w.A7wError as exc:
                sys.stderr.write("任务成功但下载失败：{}（地址：{}）\n".format(exc, url))
                emit({"ok": False, "slug": SLUG, "stage": "download", "task_id": task_id,
                      "status": "completed", "video_url": url, "error": str(exc)})
                return 8
        else:
            sys.stderr.write("任务完成但结果里没找到视频地址，没法下载。原始结果：\n{}\n"
                             .format(json.dumps(result, ensure_ascii=False, indent=2)))

    cost = a7w.dig(usage or {}, "points_cost") or a7w.dig(usage or {}, "actual_points")
    sys.stderr.write("完成。task_id={} 点数：{}{}\n".format(
        task_id, cost if cost is not None else "?",
        "  视频：{}".format(url) if url else ""))

    emit({"ok": True, "slug": SLUG, "task_id": task_id, "status": "completed",
          "video_url": url, "out": saved, "points_cost": cost,
          "usage": usage, "result": result})
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
