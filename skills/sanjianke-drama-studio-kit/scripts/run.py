#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · AI 短剧创作台 —— 创作台的四类算力接入层（零第三方依赖）。

`references/` 里那套方法论讲的是「要不要自建、选哪个底座、怎么搭起来」。
搭起来之后，创作台真正要花钱的就是四类算力：**出图、出片、配音、以及单价本身**。
这个文件把这三类生成能力 + 一份真实单价表接到 `api.a7w.cn` 上，
于是「先算钱、再投人」和「用一个镜头跑通全链路」这两步都不再是纸上功夫。

真实请求的端点（全部在 api.a7w.cn 上，逐条可核对）：

    出图（文生图 / 参考图编辑）
        POST /api/v1/apps/nano_banana/submit        # action=generate|edit，异步
        POST /api/v1/apps/nano_banana/query         # 查任务（本脚本自动轮询）
    出片（文生视频 / 首帧图生视频）
        POST /api/v1/apps/full_video/submit         # 必传 content 数组，异步
        POST /api/v1/apps/full_video/query
    配音（文字转语音）
        POST /api/v1/apps/voice_tts/tts             # 同步，音色参数是 reference_id
        POST /api/v1/apps/voice_tts/list_voices     # 拿音色 ID
    单价与模型清单
        GET  /api/v1/pricing                        # 计费规则表
        GET  /api/v1/apps/<app>                     # 逐接口 tenant_* 字段价
        GET  /api/v1/models                         # 在架模型清单

子命令

    pricing   拉一份**真实单价快照**（规则表 + tenant_* 字段价），可直接喂给
              `cost_estimate.py --price-file`；加 `--probe` 会真跑一次最便宜的生成，
              把实测扣点也记进快照
    models    列出平台在架模型（选型时别再靠猜）
    voices    列出可用音色 ID（配音要用）
    image     出一张图  → nano_banana/submit
    video     出一段片  → full_video/submit（可选首帧图）
    voice     出一段配音 → voice_tts/tts
    pilot     最小闭环：出图 → 首帧出片 → 配音，逐步打印真实扣点

用法

    python3 run.py pricing --out a7w-prices.json
    python3 run.py pricing --probe image --out a7w-prices.json
    python3 run.py image --prompt "雨夜霓虹街头，女主撑伞回头" --resolution 1K --out shot1.png
    python3 run.py video --prompt "镜头缓慢推近，雨丝落在伞面" --first-frame URL --out shot1.mp4
    python3 run.py voice --text "你终于回来了。" --reference-id 28d41f... --out line1.mp3
    python3 run.py pilot --topic "雨夜霓虹街头，女主撑伞回头" --out-dir pilot

配 Key（三种方式任选）

    python3 run.py pricing --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows: set A7W_API_KEY=sk-xxxx
    在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（`scripts/a7w.py login --key sk-xxxx`）

计费口径（自己核对，别背）
    · 平台的响应信封里 **`code == 1` 才算业务成功**（不是 0）；HTTP 200 不代表成功。
    · 实际扣费看 `usage.points_cost`；**1 元 = 100 点**，失败全额退回。
    · 已经实测到的两个数：`nano_banana/submit` 1K 文生图一次 **24 点**；
      `voice_tts/tts` 6 个字 **0.35 点**。视频按 `GET /api/v1/pricing` 的分辨率档位
      计费：480P 10 点/秒 · 768P 20 · 1080P/2K/4K 40。**单价跟着改，用 `pricing` 现拉现看。**

设计取舍
    · 视频任务又慢又贵：提交后自己轮询，**网络抖动只在查询侧重试，绝不重新提交**；
      断线或关终端后可以用 `--task-id` 把已提交的任务接着取回来，不会重复扣费。
    · `--dry-run` 只打印将要发出去的请求体，一分钱不花。
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

# ---------------------------------------------------------------------------
# 常量：都来自 `scripts/a7w.py schema <app>` 的现场输出，不是凭记忆写的
# ---------------------------------------------------------------------------

APP_IMAGE = "nano_banana"          # 出图
APP_VIDEO = "full_video"           # 出片
APP_VOICE = "voice_tts"            # 配音
APP_IMAGE_HUMAN = "image_human"    # 数字人（只用于拉价，本脚本不出数字人）
APP_MUSIC = "music_generation"     # 音乐（只用于拉价）

PRICING_APPS = (APP_IMAGE, APP_VIDEO, APP_VOICE, APP_IMAGE_HUMAN, APP_MUSIC)

POINTS_PER_YUAN = 100.0
IMAGE_RESOLUTIONS = ["1K", "2K", "4K"]
VIDEO_RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
VIDEO_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "adaptive"]
IMAGE_RATIOS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]
TERMINAL = ("completed", "failed", "error", "cancelled")
RETRY_WAIT = 5


# ---------------------------------------------------------------------------
# 底层：请求、轮询、取结果
# ---------------------------------------------------------------------------

def fetch_task(key, task_id, tries=5):
    """查一次任务状态。网络抖动（连接被重置、超时）时重试，不让付费任务白丢。"""
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
    """轮询到任务结束。中途断线只在 fetch_task 内部重试，**绝不重新提交**。"""
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


def submit_and_wait(app, api, body, key, wait=True, label=""):
    """提交一个异步任务。wait=False 时只返回 task_id。"""
    sub = a7w.call(app, api, body, key=key, wait=False)
    task_id = a7w.dig(sub, "task_id") if isinstance(sub, dict) else None
    if not task_id:
        # 少数情况下平台直接同步返回了结果
        return sub if isinstance(sub, dict) else {}
    if not wait:
        return {"task_id": task_id, "status": "submitted"}
    if label:
        sys.stderr.write("{} task_id={} 已提交，等待完成…\n".format(label, task_id))
    else:
        sys.stderr.write("task_id={} 已提交，等待完成…\n".format(task_id))
    return wait_task(key, task_id)


def pick_url(result, *names):
    """在任务结果里找产物地址——返回结构在图片/视频/音频间不一致，逐个试。"""
    if isinstance(result, dict):
        for name in names:
            v = a7w.dig(result, "data", name) or a7w.dig(result, name)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for seq_key in ("data", "results", "outputs", "images", "videos"):
            seq = a7w.dig(result, seq_key)
            if isinstance(seq, list) and seq:
                first = seq[0]
                if isinstance(first, str) and first.startswith("http"):
                    return first
                if isinstance(first, dict):
                    found = pick_url(first, *names)
                    if found:
                        return found
            if isinstance(seq, dict):
                found = pick_url(seq, *names)
                if found:
                    return found
    elif isinstance(result, str) and result.startswith("http"):
        return result
    return None


def points_of(res):
    """把实际扣点抓出来。同步接口见过 `actual_points`，异步任务见过 `points_cost`。"""
    for holder in (a7w.dig(res, "usage"), res, a7w.dig(res, "result", "usage")):
        if not isinstance(holder, dict):
            continue
        for k in ("points_cost", "actual_points", "points", "cost"):
            v = holder.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    return None


def money(points):
    return None if points is None else points / POINTS_PER_YUAN


def download(url, path):
    if not url:
        raise a7w.A7wError("没有可下载的地址")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    a7w.save(url, path)
    return str(Path(path).resolve())


# ---------------------------------------------------------------------------
# 单价快照：真实单价从平台现拉，不写死在文档里
# ---------------------------------------------------------------------------

def _get(path, key, timeout=60):
    """GET 一个管理端点。

    **坑**：平台大多数端点带 `{code,msg,data}` 信封，但 `GET /api/v1/pricing`
    是**裸对象**（`{currency,markupPercent,note,pricing}`，没有 code / data）。
    直接套 `a7w._unwrap` 会拿到 `None` 而不报错——这里两种形态都认。
    """
    payload = a7w._request("GET", a7w.HOST + path, key, timeout=timeout)
    if not isinstance(payload, dict):
        return payload
    if "code" in payload:
        return a7w._unwrap(payload)
    if "data" in payload and len(payload) <= 3:
        return payload["data"]
    return payload


def fetch_prices(key, apps=PRICING_APPS, quiet=False):
    """拉一份真实单价快照。

    两个来源，缺一不可：
        GET /api/v1/pricing        全局计费规则（含 full_video 按分辨率的每秒价）
        GET /api/v1/apps/<app>     逐接口的 tenant_* 字段价（未必等于实际结算价；预算以返回的 usage.points_cost 为准）
    注意 `pricing` 只覆盖少数接口，`voice_tts` / `nano_banana` 都不在里面。
    """
    snap = {
        "source": a7w.HOST,
        "points_per_yuan": POINTS_PER_YUAN,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rules": None,
        "apps": {},
        "measured": {},
        "notes": [],
    }
    try:
        snap["rules"] = _get("/api/v1/pricing", key)
    except a7w.A7wError as exc:
        snap["notes"].append("取计费规则表 GET /api/v1/pricing 失败：{}".format(exc))

    for app in apps:
        try:
            data = _get("/api/v1/apps/" + app, key)
        except a7w.A7wError as exc:
            snap["notes"].append("取 GET /api/v1/apps/{} 失败：{}".format(app, exc))
            continue
        apis = {}
        for a in (data.get("apis") or []):
            code = a.get("code")
            if not code:
                continue
            apis[code] = {
                "name": a.get("name"),
                "endpoint": "/api/v1/apps/{}/{}".format(app, code),
                "call_type": a.get("call_type"),
                "fixed_price": a.get("fixed_price"),
                "tenant_fixed_points": a.get("tenant_fixed_points"),
                "tenant_points_per_1k_input": a.get("tenant_points_per_1k_input"),
                "tenant_points_per_1k_output": a.get("tenant_points_per_1k_output"),
            }
        snap["apps"][app] = {"name": (data.get("app") or {}).get("name"), "apis": apis}
    if not quiet:
        sys.stderr.write("已拉取 {} 个应用的接口价与计费规则表\n".format(len(snap["apps"])))
    return snap


def _rule_for(rules, endpoint):
    if not isinstance(rules, dict):
        return None
    table = rules.get("pricing") or {}
    if not isinstance(table, dict):
        return None
    if endpoint in table:
        return table[endpoint]
    app_prefix = "/".join(endpoint.split("/")[:5]) + "/*"
    for k, v in table.items():
        if k.endswith("/*") and endpoint.startswith(k[:-1]):
            return v
        if k == app_prefix:
            return v
    return table.get("*")


def derive_units(snap):
    """从快照里归一化出三类算力的「真实单价」，供成本测算直接用。

    video 用规则表的按秒价；tts 用 tenant 的每千字价；image 的 tenant 价为 0
    （分档计费在上游结算），所以只认 `--probe` 实测出来的数。
    """
    out = {"image": {}, "video": {}, "tts": {}}
    rules = snap.get("rules")

    # --- 视频：按分辨率每秒价 ---
    rule = _rule_for(rules, "/api/v1/apps/full_video/submit")
    rates = (rule or {}).get("resolutionRates") if isinstance(rule, dict) else None
    if isinstance(rates, dict) and rates:
        out["video"] = {
            "mode": "per_second",
            "points_per_second": {str(k).upper(): float(v) for k, v in rates.items()},
            "endpoint": "/api/v1/apps/full_video/submit",
            "source": "GET /api/v1/pricing → resolutionRates",
            "note": (rule or {}).get("note") or "",
        }

    # --- 配音：tenant 每千字价 ---
    tts = a7w.dig(snap, "apps", APP_VOICE, "apis", "tts") or {}
    unit = tts.get("tenant_points_per_1k_input") or tts.get("input_price")
    try:
        unit_f = float(unit)
    except (TypeError, ValueError):
        unit_f = None
    if unit_f:
        out["tts"] = {
            "mode": "per_1k_chars",
            "points_per_1k_chars": unit_f,
            "endpoint": "/api/v1/apps/voice_tts/tts",
            "source": "GET /api/v1/apps/voice_tts → tenant_points_per_1k_input",
        }

    # --- 出图：只认实测 ---
    by_res = {}
    for k, v in (snap.get("measured") or {}).items():
        if k.startswith("nano_banana/submit@"):
            by_res[k.split("@", 1)[1]] = float(v.get("points"))
    if by_res:
        out["image"] = {
            "mode": "per_call",
            "points_per_call": by_res.get("1K") or sorted(by_res.values())[0],
            "by_resolution": by_res,
            "endpoint": "/api/v1/apps/nano_banana/submit",
            "source": "实测 usage.points_cost（tenant_fixed_points 为 0，分档价在上游结算）",
        }
    return out


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_pricing(a):
    try:
        key = a7w.load_key(a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    snap = fetch_prices(key)
    if a.probe in ("image", "all"):
        try:
            res = do_image(key, prompt="a7w 单价探针：白色背景上一个黄色香蕉",
                           resolution="1K", aspect_ratio="1:1", action="generate",
                           wait=True, dry=False)
            pts = points_of(res)
            if pts is not None:
                snap["measured"]["nano_banana/submit@1K"] = {
                    "points": pts, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "note": "实测一次 1K 文生图（真实扣费）"}
                sys.stderr.write("出图实测：1K 文生图 = {} 点\n".format(pts))
        except a7w.A7wError as exc:
            snap["notes"].append("出图探针失败：{}".format(exc))
    if a.probe in ("voice", "all"):
        ref = a.reference_id
        if not ref:
            try:
                ref = first_voice_id(key)
            except a7w.A7wError as exc:
                ref = None
                snap["notes"].append("取出音色失败：{}".format(exc))
        if ref:
            try:
                text = "你终于回来了。"
                res = do_voice(key, text=text, reference_id=ref, fmt="mp3", dry=False)
                pts = points_of(res)
                if pts is not None:
                    snap["measured"]["voice_tts/tts"] = {
                        "points": pts, "sample_chars": len(text),
                        "points_per_1k_chars": round(pts * 1000.0 / len(text), 2),
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "note": "实测一次 {} 字配音（真实扣费）".format(len(text))}
                    sys.stderr.write("配音实测：{} 字 = {} 点（≈ {:.1f} 点/千字）\n".format(
                        len(text), pts, pts * 1000.0 / len(text)))
            except a7w.A7wError as exc:
                snap["notes"].append("配音探针失败：{}".format(exc))
    if a.probe == "video":
        snap["notes"].append(
            "视频探针要 4 秒起、按分辨率每秒计费，本命令不代跑；"
            "要验就用 `run.py video --resolution 480P --duration 4`，"
            "它会把 usage.points_cost 打在屏幕上。")

    snap["derived"] = derive_units(snap)
    if a.out:
        Path(a.out).write_text(json.dumps(snap, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        sys.stderr.write("单价快照已写入 {}（可直接喂 cost_estimate.py --price-file）\n".format(a.out))
    if a.json:
        print(json.dumps(snap, ensure_ascii=False, indent=1))
        return 0
    _print_prices(snap)
    return 0


def _print_prices(snap):
    """把快照讲成人能读的样子（1 元 = 100 点）。"""
    d = snap.get("derived") or {}
    print("api.a7w.cn 真实单价快照（{}，拉取时间 {}）"
          .format(snap.get("source"), snap.get("fetched_at") or "未记录"))
    print("口径：1 元 = 100 点（1 点 = 0.01 元）；先冻结后结算，失败全额退回。")
    print()
    vid = d.get("video") or {}
    if vid.get("points_per_second"):
        print("出片  POST /api/v1/apps/full_video/submit   按分辨率每秒计费：")
        for res in VIDEO_RESOLUTIONS:
            rate = (vid.get("points_per_second") or {}).get(res)
            if rate:
                print("      %-6s %5s 点/秒   （4 秒 = %s 点 ≈ %.2f 元）"
                      % (res, rate, rate * 4, rate * 4 / POINTS_PER_YUAN))
    else:
        print("出片  未取到按秒价：GET /api/v1/pricing 里没有 full_video 条目")
    print()
    tts = d.get("tts") or {}
    if tts.get("points_per_1k_chars"):
        print("配音  POST /api/v1/apps/voice_tts/tts      按千字计费：{} 点/千字"
              "（20 字 ≈ {} 点）".format(tts["points_per_1k_chars"],
                                      round(tts["points_per_1k_chars"] * 20 / 1000.0, 3)))
    else:
        print("配音  未取到每千字价")
    print()
    img = d.get("image") or {}
    if img.get("by_resolution"):
        print("出图  POST /api/v1/apps/nano_banana/submit  实测按次：")
        for res, pts in img["by_resolution"].items():
            print("      %-6s %5s 点/张 ≈ %.2f 元" % (res, pts, pts / POINTS_PER_YUAN))
    else:
        print("出图  tenant_fixed_points 为 0（分档价在上游结算），需要用实测值补：")
        print("      python scripts/run.py pricing --probe image")
    print()
    by_app = snap.get("apps") or {}
    if by_app:
        print("已取到下列应用的 tenant_* 字段价（未必等于实际结算价；预算以返回的 usage.points_cost 为准）：")
        for app, info in by_app.items():
            print("  %-16s %-14s %d 个接口" % (app, info.get("name") or "", len(info.get("apis") or {})))
    if snap.get("notes"):
        print()
        print("提示：")
        for n in snap["notes"]:
            print("  · {}".format(n))
    print()
    print("要落成文件喂给成本测算：加 `--out prices.json`；要看原始 JSON：加 `--json`。")


def cmd_models(a):
    try:
        key = a7w.load_key(a.key)
        d = _get("/api/v1/models", key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    lst = d.get("data") if isinstance(d, dict) and "data" in d else d
    if isinstance(lst, dict):
        lst = lst.get("list") or lst.get("models") or []
    if a.filter:
        kw = a.filter.lower()
        lst = [m for m in lst
               if kw in str(m.get("model_code", "")).lower()
               or kw in str(m.get("model_name", "")).lower()]
    if a.json:
        print(json.dumps(lst, ensure_ascii=False, indent=1))
        return 0
    print("在架模型 %d 个（GET /api/v1/models）：" % len(lst))
    for m in lst:
        if isinstance(m, dict):
            print("  %-34s %-26s %s"
                  % (m.get("model_code"), m.get("model_name") or "",
                     m.get("type_name") or m.get("call_type_desc") or ""))
    return 0


def first_voice_id(key):
    d = a7w.call(APP_VOICE, "list_voices", {"page_size": 20}, key=key)
    items = a7w.dig(d, "items") or d.get("items") if isinstance(d, dict) else None
    for it in (items or []):
        if isinstance(it, dict) and it.get("model_id"):
            return it["model_id"]
    raise a7w.A7wError("这个账号下还没有可用音色，先用 voice_tts/clone_voice 克隆一个。")


def cmd_voices(a):
    try:
        key = a7w.load_key(a.key)
        d = a7w.call(APP_VOICE, "list_voices",
                     {"page_size": a.page_size, "page_number": a.page}, key=key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0
    items = (d or {}).get("items") or []
    print("可用音色 %s 个（POST /api/v1/apps/voice_tts/list_voices）："
          % (d or {}).get("total", len(items)))
    for it in items:
        print("  %-34s %-20s %s" % (it.get("model_id"), it.get("title") or "",
                                    it.get("state") or ""))
    print("\n配音时把 model_id 填给 voice_tts/tts 的 `reference_id`（不是 voice_id）。")
    return 0


def do_image(key, prompt, resolution="1K", aspect_ratio="9:16", action="generate",
             image_urls=None, wait=True, dry=False, callback_url=None, model=None):
    """POST /api/v1/apps/nano_banana/submit —— action=generate 文生图 / edit 参考图编辑。"""
    body = {"action": action, "prompt": prompt, "resolution": resolution}
    if model:
        body["model"] = model
    if aspect_ratio:
        body["aspect_ratio"] = aspect_ratio
    if image_urls:
        body["image_urls"] = image_urls
    if callback_url:
        body["callback_url"] = callback_url
    if dry:
        return body
    return submit_and_wait(APP_IMAGE, "submit", body, key, wait=wait)


def cmd_image(a):
    try:
        key = a7w.load_key(a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    if a.action == "edit" and not a.image_url:
        sys.stderr.write("失败：action=edit 必须给 --image-url（参考图，公网可访问）。\n")
        return 2
    try:
        res = do_image(key, a.prompt, a.resolution, a.aspect_ratio, a.action,
                       a.image_url, wait=not a.no_wait, dry=a.dry_run,
                       callback_url=a.callback_url, model=a.model)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    if a.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/api/v1/apps/nano_banana/submit",
                          "body": res}, ensure_ascii=False, indent=1))
        return 0
    return _finish(res, ("image_url", "url", "output_url"), a.out, a.task_id, "图")


def do_video(key, prompt, first_frame=None, last_frame=None, reference_images=None,
             ratio="9:16", resolution="480P", duration=4, watermark=False,
             wait=True, dry=False):
    """POST /api/v1/apps/full_video/submit。

    **坑**：这个接口不吃 `first_frame_url` + `prompt`，它只认 `content` 数组，
    而且数组里**必须有一条 `{"type": "text"}`**。首帧写成
    `{"role": "first_frame", "type": "image_url", "image_url": {"url": ...}}`。
    """
    content = []
    if first_frame:
        content.append({"role": "first_frame", "type": "image_url",
                        "image_url": {"url": first_frame}})
    if last_frame:
        content.append({"role": "last_frame", "type": "image_url",
                        "image_url": {"url": last_frame}})
    for u in (reference_images or []):
        content.append({"role": "reference_image", "type": "image_url",
                        "image_url": {"url": u}})
    content.append({"type": "text", "text": prompt})
    body = {"model": "full-video", "ratio": ratio, "resolution": resolution,
            "duration": duration, "aigc_watermark": bool(watermark),
            "content": content}
    if dry:
        return body
    return submit_and_wait(APP_VIDEO, "submit", body, key, wait=wait)


def cmd_video(a):
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
                sys.stderr.write("失败：--duration 只支持 4 到 15 秒的整数。\n")
                return 2
            res = do_video(key, a.prompt, a.first_frame, a.last_frame,
                           a.reference_image, a.ratio, a.resolution, a.duration,
                           a.watermark, wait=not a.no_wait, dry=a.dry_run)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    if a.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/api/v1/apps/full_video/submit",
                          "body": res}, ensure_ascii=False, indent=1))
        return 0
    return _finish(res, ("video_url", "videoUrl", "url", "output_url"),
                   a.out, a.task_id, "片")


def do_voice(key, text, reference_id=None, fmt="mp3", model="s2-pro",
             dry=False, speed=None):
    """POST /api/v1/apps/voice_tts/tts。

    **坑**：音色参数叫 `reference_id`（值是 list_voices 的 model_id），不是 `voice_id`。
    同步接口建议单次不超过 500 字符；长台词用 tts_async 或 tts_live。
    """
    body = {"text": text, "model": model, "format": fmt}
    if reference_id:
        body["reference_id"] = reference_id
    if speed:
        body["prosody"] = {"speed": speed}
    if dry:
        return body
    return a7w.call(APP_VOICE, "tts", body, key=key, wait=True)


def cmd_voice(a):
    try:
        key = a7w.load_key(a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    ref = a.reference_id
    if not ref and not a.no_reference:
        try:
            ref = first_voice_id(key)
            sys.stderr.write("未指定音色，自动选用 {}（可用 `run.py voices` 看全部）\n".format(ref))
        except a7w.A7wError as exc:
            sys.stderr.write("取默认音色失败：{}\n".format(exc))
    try:
        res = do_voice(key, a.text, ref, a.format, speed=a.speed, dry=a.dry_run)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    if a.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/api/v1/apps/voice_tts/tts",
                          "body": res}, ensure_ascii=False, indent=1))
        return 0
    return _finish(res, ("audio_url", "url", "output_url"), a.out, None, "配音")


def _finish(res, url_keys, out, task_id, label):
    """统一的收尾：取地址 → 下载 → 打印真实扣点。"""
    result = res.get("result") if isinstance(res, dict) else None
    url = pick_url(result, *url_keys)
    pts = points_of(res)
    task_id = (res.get("task_id") if isinstance(res, dict) else None) or task_id
    if not url:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        sys.stderr.write("任务完成但没从返回里找到{}地址，上面是原始返回。"
                         "如已扣费，用 --task-id {} 可以再取一次。\n".format(label, task_id or "?"))
        return 5
    saved = None
    if out:
        try:
            saved = download(url, out)
        except (a7w.A7wError, OSError) as exc:
            sys.stderr.write("{}生成成功但下载失败：{}（地址：{}）\n".format(label, exc, url))
            print(json.dumps({"ok": True, "url": url, "task_id": task_id,
                              "points_cost": pts, "saved": None},
                             ensure_ascii=False))
            return 6
    sys.stderr.write("完成：{}{}{}\n".format(
        saved or url,
        "  消耗 {} 点".format(pts) if pts is not None else "",
        "（≈ {:.2f} 元）".format(money(pts)) if pts is not None else ""))
    print(json.dumps({"ok": True, "url": url, "saved": saved, "task_id": task_id,
                      "points_cost": pts, "yuan": money(pts)},
                     ensure_ascii=False))
    return 0


def cmd_pilot(a):
    """最小闭环：一个镜头从提示词走到「图 + 片 + 配音」。

    这正是 `SKILL.md` 里那条「最低成本验证法」——先用一个镜头跑通全链路，
    再批量投入。脚本把每一步的真实扣点单独打出来，方便你判断钱花在哪。
    """
    try:
        key = a7w.load_key(a.key)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    out_dir = Path(a.out_dir or "pilot")
    out_dir.mkdir(parents=True, exist_ok=True)
    spent = []
    report = {"topic": a.topic, "steps": []}

    # 1) 出图 —— 本镜首帧
    sys.stderr.write("\n[1/3] 出图 → POST /api/v1/apps/nano_banana/submit\n")
    try:
        img = do_image(key, a.image_prompt or a.topic, a.resolution, "9:16",
                       "generate", None, wait=True, dry=a.dry_run)
    except a7w.A7wError as exc:
        sys.stderr.write("出图失败：{}\n".format(exc))
        return 4
    if a.dry_run:
        print(json.dumps({"dry_run": True, "steps": [
            {"endpoint": "/api/v1/apps/nano_banana/submit", "body": img}]},
            ensure_ascii=False, indent=1))
        return 0
    img_url = pick_url(img.get("result"), "image_url", "url")
    img_pts = points_of(img)
    img_path = None
    if img_url:
        try:
            img_path = download(img_url, out_dir / "shot1.png")
        except (a7w.A7wError, OSError) as exc:
            sys.stderr.write("  下载失败：{}\n".format(exc))
    sys.stderr.write("  首帧图：{}  扣点 {}\n".format(img_url, img_pts))
    spent.append(("出图 nano_banana/submit", img_pts))
    report["steps"].append({"step": "image", "endpoint": "/api/v1/apps/nano_banana/submit",
                            "task_id": img.get("task_id"), "url": img_url,
                            "saved": img_path, "points_cost": img_pts})

    # 2) 出片 —— 首帧图 + 运镜描述
    video_url = video_path = video_pts = None
    if not a.no_video:
        sys.stderr.write("\n[2/3] 出片 → POST /api/v1/apps/full_video/submit"
                         "（content 数组：first_frame + text）\n")
        try:
            vid = do_video(key, a.motion_prompt or "镜头缓慢推近，人物轻微转头",
                           img_url, None, None, "9:16", a.video_resolution,
                           a.duration, a.watermark, wait=True)
            video_url = pick_url(vid.get("result"), "video_url", "videoUrl", "url")
            video_pts = points_of(vid)
            if video_url:
                try:
                    video_path = download(video_url, out_dir / "shot1.mp4")
                except (a7w.A7wError, OSError) as exc:
                    sys.stderr.write("  下载失败：{}\n".format(exc))
            sys.stderr.write("  成片：{}  扣点 {}\n".format(video_url, video_pts))
            spent.append(("出片 full_video/submit", video_pts))
            report["steps"].append({"step": "video",
                                    "endpoint": "/api/v1/apps/full_video/submit",
                                    "task_id": vid.get("task_id"), "url": video_url,
                                    "saved": video_path, "points_cost": video_pts})
        except a7w.A7wError as exc:
            sys.stderr.write("  出片失败（首帧可能还没被上游拉到）：{}\n".format(exc))
            report["steps"].append({"step": "video", "error": str(exc)})

    # 3) 配音 —— 本镜台词
    sys.stderr.write("\n[3/3] 配音 → POST /api/v1/apps/voice_tts/tts"
                     "（音色参数是 reference_id）\n")
    ref = a.reference_id
    if not ref:
        try:
            ref = first_voice_id(key)
        except a7w.A7wError as exc:
            sys.stderr.write("  取默认音色失败：{}\n".format(exc))
    audio_url = audio_path = audio_pts = None
    if ref:
        try:
            aud = do_voice(key, a.line, ref, "mp3")
            audio_url = pick_url(aud.get("result"), "audio_url", "url")
            audio_pts = points_of(aud)
            if audio_url:
                try:
                    audio_path = download(audio_url, out_dir / "line1.mp3")
                except (a7w.A7wError, OSError) as exc:
                    sys.stderr.write("  下载失败：{}\n".format(exc))
            sys.stderr.write("  配音：{}  扣点 {}\n".format(audio_url, audio_pts))
            spent.append(("配音 voice_tts/tts", audio_pts))
            report["steps"].append({"step": "voice",
                                    "endpoint": "/api/v1/apps/voice_tts/tts",
                                    "url": audio_url, "saved": audio_path,
                                    "points_cost": audio_pts})
        except a7w.A7wError as exc:
            sys.stderr.write("  配音失败：{}\n".format(exc))
            report["steps"].append({"step": "voice", "error": str(exc)})

    known = [p for _, p in spent if p is not None]
    total = sum(known) if known else None
    report["points_total"] = total
    report["yuan_total"] = money(total)
    report["out_dir"] = str(out_dir.resolve())
    print()
    print("---- 一个镜头的真实开销 ----")
    for name, p in spent:
        print("  %-28s %s 点" % (name, "?" if p is None else p))
    print("  %-28s %s 点%s" % ("合计", "?" if total is None else round(total, 3),
                               "" if total is None else "  ≈ {:.3f} 元".format(money(total))))
    print("  产物目录：{}".format(out_dir.resolve()))
    print("  把上面这个单镜头成本 × 分镜数 × 拍摄比，就是全剧的生成成本量级；"
          "正式测算用 `python scripts/cost_estimate.py --a7w-live`。")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="AI 短剧创作台的算力接入层：出图 / 出片 / 配音 / 真实单价"
                    "（全部走 api.a7w.cn，零第三方依赖）",
        epilog="端点：POST /api/v1/apps/nano_banana/submit · "
               "POST /api/v1/apps/full_video/submit · POST /api/v1/apps/voice_tts/tts · "
               "GET /api/v1/pricing")
    ap.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pricing", help="拉真实单价快照（可喂 cost_estimate.py --price-file）")
    p.add_argument("--out", help="快照写入的 JSON 路径")
    p.add_argument("--probe", choices=["none", "image", "voice", "video", "all"],
                   default="none", help="真跑一次最便宜的生成，把实测扣点也记进快照")
    p.add_argument("--reference-id", help="配音探针用的音色 ID")
    p.add_argument("--json", action="store_true", help="输出原始 JSON（默认打印可读摘要）")
    p.set_defaults(func=cmd_pricing)

    p = sub.add_parser("models", help="列出平台在架模型")
    p.add_argument("--filter", help="按关键词过滤")
    p.add_argument("--json", action="store_true", help="输出原始 JSON")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("voices", help="列出可用音色 ID")
    p.add_argument("--page-size", type=int, default=20)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("image", help="出一张图 → nano_banana/submit")
    p.add_argument("--prompt", required=True, help="画面描述")
    p.add_argument("--action", choices=["generate", "edit"], default="generate",
                   help="generate 文生图 / edit 基于参考图编辑")
    p.add_argument("--image-url", action="append", help="参考图公网 URL（edit 必填，可重复）")
    p.add_argument("--resolution", default="1K", choices=IMAGE_RESOLUTIONS)
    p.add_argument("--aspect-ratio", default="9:16", choices=IMAGE_RATIOS)
    p.add_argument("--model", help="模型规格，如 nano-banana-pro / nano-banana-2:official")
    p.add_argument("--callback-url", help="任务完成回调地址")
    p.add_argument("--out", help="图片保存路径，如 shot1.png")
    p.add_argument("--task-id", help="只取已提交任务的产物，不重新提交（不重复扣费）")
    p.add_argument("--no-wait", action="store_true", help="只提交，拿 task_id")
    p.add_argument("--dry-run", action="store_true", help="只打印请求体，不真的调用")
    p.set_defaults(func=cmd_image)

    p = sub.add_parser("video", help="出一段片 → full_video/submit")
    p.add_argument("--prompt", help="运镜 / 画面描述（content 里的 text 项）")
    p.add_argument("--first-frame", help="首帧图公网 URL")
    p.add_argument("--last-frame", help="尾帧图公网 URL")
    p.add_argument("--reference-image", action="append", help="参考图 URL（可重复）")
    p.add_argument("--ratio", default="9:16", choices=VIDEO_RATIOS)
    p.add_argument("--resolution", default="480P", choices=VIDEO_RESOLUTIONS,
                   help="480P 最便宜，先用它试通再放大")
    p.add_argument("--duration", type=int, default=4, help="4~15 秒的整数")
    p.add_argument("--watermark", action="store_true", help="加 AIGC 生成标识")
    p.add_argument("--out", help="视频保存路径，如 shot1.mp4")
    p.add_argument("--task-id", help="只取已提交任务的产物，不重新提交")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_video)

    p = sub.add_parser("voice", help="出一段配音 → voice_tts/tts")
    p.add_argument("--text", required=True, help="台词；同步接口建议 ≤500 字")
    p.add_argument("--reference-id", help="音色 ID（list_voices 的 model_id）")
    p.add_argument("--no-reference", action="store_true", help="不使用指定音色")
    p.add_argument("--format", default="mp3", choices=["mp3", "wav", "pcm", "opus"])
    p.add_argument("--speed", type=float, help="语速（prosody.speed）")
    p.add_argument("--out", help="音频保存路径，如 line1.mp3")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_voice)

    p = sub.add_parser("pilot", help="最小闭环：一个镜头 出图→出片→配音")
    p.add_argument("--topic", required=True, help="这一镜要什么画面")
    p.add_argument("--image-prompt", help="覆盖出图提示词")
    p.add_argument("--motion-prompt", help="覆盖运镜提示词")
    p.add_argument("--line", default="你终于回来了。", help="本镜台词")
    p.add_argument("--reference-id", help="配音音色 ID")
    p.add_argument("--resolution", default="1K", choices=IMAGE_RESOLUTIONS)
    p.add_argument("--video-resolution", default="480P", choices=VIDEO_RESOLUTIONS)
    p.add_argument("--duration", type=int, default=4)
    p.add_argument("--watermark", action="store_true")
    p.add_argument("--no-video", action="store_true", help="跳过出片，只验图与配音")
    p.add_argument("--out-dir", default="pilot", help="产物目录")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_pilot)

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。付费任务可能仍在跑，用 --task-id 可以接着取。\n")
        return 130


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
