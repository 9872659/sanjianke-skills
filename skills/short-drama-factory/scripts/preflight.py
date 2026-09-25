#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 短剧工厂 · 出片前体检（preflight）
====================================================================
零依赖，只用 Python 标准库。不内嵌任何密钥。

它做四件事：
  1. 验证 API Key 能不能用（真调一次余额接口）
  2. 报出点数余额，并按实测单价估「这集够不够」
  3. 拉可用模型清单（接口不可用时如实说明，不假装成功）
  4. 校验一批镜头参数是否合法（分辨率 / 时长 / 参考图数），
     把会在上游 400 的请求在本地就拦下来

单位口径：1 元 = 100 点。

用法
--------------------------------------------------------------------
    # 0. 先配一次 Key（写进 ~/.a7w/config.json，权限 600）
    python3 preflight.py login --key sk-你的key

    # 1. 体检（Key + 余额 + 模型清单 + 音色）
    python3 preflight.py check

    # 2. 估一集的预算
    python3 preflight.py budget --shots 13 --avg-seconds 5 --tier mixed

    # 3. 离线校验镜头参数（不联网）
    python3 preflight.py lint --shots shots.json

Key 的读取顺序
--------------------------------------------------------------------
    1. --key 参数
    2. 环境变量 A7W_API_KEY / A7W_KEY / A7WCN_API_KEY
    3. ~/.a7w/config.json

**配置文件字段名不止一种。** 线上实测已有 `{"key":..., "host":...}` 这种形态，
也有 `{"api_key":...}`。本脚本按 `api_key` / `key` / `apikey` / `token` / `apiKey`
依次找。`login` 写入时也**合并**而不是整份覆盖，不会抹掉别的工具写的字段。

想确认 Key 是从哪读到的（不联网、不打印 Key）：`check --print-source`

退出码
--------------------------------------------------------------------
    0  全部通过
    1  参数 / 用法错误
    2  Key 无效、缺失或无权限（401/403）
    3  网络不可达
    4  余额不足（按 budget 的估算）
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://api.a7w.cn/api/v1"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".a7w")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def _force_utf8():
    """
    Windows 控制台默认是 GBK，中文与符号会抛 UnicodeEncodeError。
    这里把 stdout/stderr 切成 UTF-8 并改成不因编码失败而中断。
    只影响本进程的输出，不改系统设置。
    """
    for stream in ("stdout", "stderr"):
        s = getattr(sys, stream, None)
        if s is None:
            continue
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8()

# ---------------------------------------------------------------- 实测单价
# 来源：真实扣费记录。平台会调价，且租户实收价可能与公示价不同 —— 只用于估算。
PRICE_PER_IMAGE = 20          # 点/张（gpt-image-2-pro 实测）
PRICE_VIDEO = {               # 点/秒
    "h3-video":     {"768P": 50, "2K": 50},
    "wan3.0-video": {"480P": 28, "720P": 55},
}
PRICE_VIDEO_DEFAULT = 28
PRICE_TTS = 0                 # 零样本克隆实测 0 点
PRICE_COMPOSE = 0             # 字幕 / 水印 / 剪辑 / 合成实测 0 点

# ------------------------------------------------- 模型参数约束（探测所得）
# 这些是会在上游被判「取值不在允许范围」的值，必须本地拦住。
H3_RESOLUTIONS = {"768P", "2K"}
H3_DURATIONS = {"4", "5", "6", "7", "8", "10", "12", "15"}   # 且必须是字符串
H3_RATIOS = {"16:9", "9:16", "1:1", "4:3"}

WAN_RESOLUTIONS = {"480P", "720P"}
WAN_DURATION_MIN = 3
WAN_DURATION_MAX = 30

IMAGE_REF_LIMIT = {"qwen-image": 3, "gpt-image": 12, "nano-banana": 12}
SINGLE_IMAGE_VIDEO = ("veo", "grok")     # 这两族只吃单张图

# 已上架但实测不可用 —— 别再选
DEAD_MODELS = [
    "seedance", "full-video", "happy-horse", "wan", "flashvsr",
    "Wan-AI/Wan2.2-T2V-A14B", "Wan-AI/Wan2.2-I2V-A14B",
]

VIDEO_ALLROUND = "h3-video"


# ---------------------------------------------------------------- 小工具
def die(msg, code=1):
    print("✗ " + msg)
    sys.exit(code)


def ok(msg):
    print("✓ " + msg)


def warn(msg):
    print("! " + msg)


def info(msg):
    print("  " + msg)


def load_key(explicit=None, trace=False):
    """
    Key 读取顺序：显式参数 → 环境变量 → 配置文件 → 环境变量 A7W_KEY。

    配置文件字段名**不止一种**（实测线上已有 `{"key":..., "host":...}` 这种形态，
    也有 `{"api_key":...}`）。所以按候选字段名依次找，别只认一个。

    trace=True 时返回 (key, 来源说明)。来源说明**只写字段名与变量名，不含 Key 本身**。
    """
    def _ret(k, src):
        return (k, src) if trace else k

    if explicit:
        return _ret(explicit.strip(), "--key 参数")
    for var in ("A7W_API_KEY", "A7W_KEY", "A7WCN_API_KEY"):
        v = os.environ.get(var, "").strip()
        if v:
            return _ret(v, "环境变量 %s" % var)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if isinstance(cfg, dict):
                for field in ("api_key", "key", "apikey", "token", "apiKey"):
                    k = str(cfg.get(field, "") or "").strip()
                    if k:
                        return _ret(k, "%s 的 \"%s\" 字段" % (CONFIG_FILE, field))
        except Exception as e:
            warn("配置文件读取失败：%s" % e)
    return _ret("", "(未找到)")


def mask(key):
    if len(key) <= 10:
        return key[:2] + "****"
    return key[:6] + "****" + key[-4:]


def request(method, path, key=None, body=None, timeout=30):
    """返回 (status, parsed_json_or_None, raw_text)。不抛异常，由调用方判断。"""
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw), raw
            except ValueError:
                return r.status, None, raw
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        try:
            return e.code, json.loads(raw), raw
        except ValueError:
            return e.code, None, raw
    except urllib.error.URLError as e:
        return None, None, str(e.reason)
    except Exception as e:
        return None, None, str(e)


def unwrap(js):
    """
    平台有两种响应形态：
      · 套信封 {code, msg, data}
      · 不套信封（/user/balance、/chat/completions 直接返回业务对象）
    **不能强制要求 code==1** —— 那会把 HTTP 200 的正常响应判成失败。
    """
    if not isinstance(js, dict):
        return js
    if "code" in js:
        return js.get("data")
    return js


# ---------------------------------------------------------------- login
def cmd_login(args):
    key = (args.key or "").strip()
    if not key:
        die("请用 --key 提供 Key（形如 sk-xxxxxxxx）", 1)
    if not key.startswith("sk-"):
        warn("这个 Key 不是 sk- 开头 —— api.a7w.cn 的 Key 形如 sk-xxxxxxxx，先确认一下")

    print("正在用该 Key 真调一次余额接口校验 …")
    status, js, raw = request("GET", "/user/balance", key=key)
    if status is None:
        die("网络不可达：%s" % raw, 3)
    if status == 401 or status == 403:
        die("Key 校验失败（HTTP %d）：%s" % (status, raw[:200]), 2)
    if status >= 400:
        die("余额接口返回 HTTP %d：%s" % (status, raw[:200]), 2)

    ok("Key 有效（HTTP %d）" % status)
    show_balance(js)

    os.makedirs(CONFIG_DIR, exist_ok=True)
    # **合并写，不要整份覆盖** —— 已有配置里可能有别的工具写的字段
    # （实测线上就是 {"key":..., "host":...} 这种形态）。
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, dict):
                cfg = old
        except Exception:
            warn("原配置解析失败，将重建（原文件已备份为 config.json.bak）")
            try:
                import shutil
                shutil.copyfile(CONFIG_FILE, CONFIG_FILE + ".bak")
            except Exception:
                pass
    # 同时写两个字段名，兼容不同读取方
    cfg["api_key"] = key
    cfg.setdefault("key", key)
    cfg.setdefault("host", "https://api.a7w.cn")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass
    ok("已保存到 %s（权限 600，已保留原有其它字段）" % CONFIG_FILE)
    info("Key 等同于余额：不要提交进 Git，不要写进代码。")


def find_points(js):
    """从余额响应里找出点数。字段名不统一，按候选顺序探。"""
    d = unwrap(js)
    if isinstance(d, dict):
        for k in ("points", "balance", "point", "remaining_points",
                  "available_points", "total_points", "points_balance"):
            v = d.get(k)
            if isinstance(v, (int, float)):
                return v, k
        # 嵌套一层
        for k, v in d.items():
            if isinstance(v, dict):
                for k2 in ("points", "balance", "available_points"):
                    v2 = v.get(k2)
                    if isinstance(v2, (int, float)):
                        return v2, "%s.%s" % (k, k2)
    if isinstance(d, (int, float)):
        return d, "(裸值)"
    return None, None


def show_balance(js):
    pts, field = find_points(js)
    if pts is None:
        warn("认不出余额字段，原始响应：")
        info(json.dumps(unwrap(js), ensure_ascii=False)[:300])
        return None
    ok("可用点数：%s 点（字段 %s）· 约 %.2f 元" % (pts, field, pts / 100.0))
    return pts


# ---------------------------------------------------------------- check
def cmd_check(args):
    key, source = load_key(args.key, trace=True)
    if not key:
        die("没找到 Key。先跑：python3 preflight.py login --key sk-xxxx\n"
            "  或设环境变量 A7W_API_KEY", 2)

    info("Base：%s" % BASE)
    info("Key ：%s" % mask(key))
    info("来源：%s" % source)
    if args.print_source:
        ok("只报告 Key 来源，不发起任何网络请求。")
        return 0
    print("")

    # --- 1. 余额 ---
    print("[1/4] 余额")
    status, js, raw = request("GET", "/user/balance", key=key)
    points = None
    if status is None:
        die("网络不可达：%s" % raw, 3)
    elif status == 401 or status == 403:
        die("Key 无效（HTTP %d）" % status, 2)
    elif status >= 400:
        # 已知：部分账号的余额接口不可用。如实报告，不假装成功。
        warn("余额接口返回 HTTP %d —— 这个接口在部分账号上不可用。" % status)
        info("原始响应：%s" % raw[:200].replace("\n", " "))
        info("不影响出片，只是本脚本估不了预算。")
    else:
        ok("余额接口 HTTP %d" % status)
        points = show_balance(js)

    # --- 2. 模型清单 ---
    print("\n[2/4] 可用模型")
    models = try_models(key)
    if models is None:
        warn("模型清单接口不可用（这是已知情况，不是你的 Key 有问题）。")
        info("界面侧的模型选项请以 https://api.a7w.cn 站内为准。")
    else:
        ok("拉到 %d 个模型" % len(models))
        by_type = {}
        for m in models:
            t = (m.get("type") or "未分类").lower()
            by_type.setdefault(t, []).append(m)
        for t in sorted(by_type):
            ids = [x["id"] for x in by_type[t]]
            info("%-10s %3d 个：%s" % (t, len(ids), ", ".join(ids[:8]) +
                                       (" …" if len(ids) > 8 else "")))
        # 死模型检查
        ids_all = {m["id"].lower() for m in models}
        hits = sorted(ids_all & {d.lower() for d in DEAD_MODELS})
        if hits:
            warn("清单里有「已上架但实测不可用」的模型，请从选择器过滤掉：")
            for h in hits:
                info("· %s" % h)
        else:
            ok("没有发现已知死模型")

    # --- 3. 音色 ---
    print("\n[3/4] 音色")
    status, js, raw = request("GET", "/apps/voice_tts/list_voices", key=key)
    if status is None or status >= 400:
        warn("音色列表取不到（HTTP %s）" % status)
        info("已知：voice_tts/list_voices 只返回**当前用户自己克隆的**音色，")
        info("预设音色库在 API 侧没有直接入口。")
    else:
        d = unwrap(js)
        n = len(d) if isinstance(d, list) else (
            len(d.get("list", [])) if isinstance(d, dict) and isinstance(d.get("list"), list) else None)
        if n is None:
            info("拿到响应但认不出条数：%s" % json.dumps(d, ensure_ascii=False)[:200])
        else:
            ok("拿到 %d 个音色（都是你自己克隆的）" % n)

    # --- 4. 结论 ---
    print("\n[4/4] 结论")
    if points is not None:
        est = estimate(12, 5, "mixed")
        info("按 12 镜 × 5 秒的 mixed 档估，一集约 %d 点。" % est["total"])
        if points >= est["total"]:
            ok("余额看起来够跑一集。")
        else:
            warn("余额可能不够：有 %s 点 / 估需 %d 点 / 差 %.1f 点。"
                 % (points, est["total"], est["total"] - points))
            info("开工前先算总账是正确姿势 —— 那时候一个镜头都没生成，一分钱没花。")
    ok("体检完成。")
    return 0


def try_models(key):
    for p in ("/models", "/user/models", "/model/list"):
        status, js, raw = request("GET", p, key=key)
        if status is None or status >= 400:
            continue
        d = unwrap(js)
        arr = d if isinstance(d, list) else (
            d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), list) else [])
        if not arr:
            continue
        out = []
        for x in arr:
            if not isinstance(x, dict):
                continue
            mid = x.get("id") or x.get("model_code") or x.get("name") or x.get("model")
            if not mid:
                continue
            caps = x.get("capabilities") or {}
            out.append({
                "id": str(mid),
                "type": str(x.get("type") or x.get("type_code") or
                            x.get("typeName") or x.get("modality") or "").lower(),
                "max_ref": caps.get("max_reference_images") or x.get("max_reference_images") or 0,
            })
        if out:
            return out
    return None


# ---------------------------------------------------------------- budget
def price_of_video(model, resolution):
    m = PRICE_VIDEO.get(model)
    if m:
        if resolution in m:
            return m[resolution]
        return list(m.values())[0]
    return PRICE_VIDEO_DEFAULT


def estimate(shots, avg_seconds, tier, anchors=0):
    """
    tier: cheap  全部用 wan 480P（28 点/秒）
          quality 全部用 h3 768P（50 点/秒）
          mixed   一半远景/中景用 h3，一半近景/特写用 wan（默认，最接近实际）
    """
    if tier == "cheap":
        sec_price = price_of_video("wan3.0-video", "480P")
        plan = {"wan3.0-video": {"480P": shots}}
    elif tier == "quality":
        sec_price = price_of_video("h3-video", "768P")
        plan = {"h3-video": {"768P": shots}}
    else:
        half = (shots + 1) // 2
        plan = {"h3-video": {"768P": half}, "wan3.0-video": {"480P": shots - half}}
        sec_price = None

    video_points = 0
    for model, resmap in plan.items():
        for res, n in resmap.items():
            video_points += n * avg_seconds * price_of_video(model, res)

    image_points = (shots + anchors) * PRICE_PER_IMAGE
    total = video_points + image_points + PRICE_TTS * shots + PRICE_COMPOSE

    return {
        "shots": shots,
        "avg_seconds": avg_seconds,
        "tier": tier,
        "video_points": video_points,
        "image_points": image_points,
        "tts_points": PRICE_TTS * shots,
        "compose_points": PRICE_COMPOSE,
        "total": int(round(total)),
        "video_share": (video_points / total * 100.0) if total else 0.0,
        "plan": plan,
        "_sec_price": sec_price,
    }


def cmd_budget(args):
    if args.shots <= 0:
        die("--shots 必须为正整数", 1)
    if args.avg_seconds <= 0:
        die("--avg-seconds 必须为正数", 1)

    e = estimate(args.shots, args.avg_seconds, args.tier, anchors=args.anchors)

    print("预算估算（口径：实测单价 · 1 元 = 100 点）")
    print("=" * 60)
    info("镜头数        %d" % e["shots"])
    info("平均单镜时长  %ss" % e["avg_seconds"])
    info("档位策略      %s" % e["tier"])
    for model, resmap in e["plan"].items():
        for res, n in resmap.items():
            info("  · %-14s %-6s %d 镜 × %ss × %d 点/秒"
                 % (model, res, n, e["avg_seconds"], price_of_video(model, res)))
    print("-" * 60)
    info("出图          %6d 点   （%d 镜 + %d 锚点）"
         % (e["image_points"], e["shots"], args.anchors))
    info("视频          %6d 点   ← 占 %.0f%%" % (e["video_points"], e["video_share"]))
    info("配音          %6d 点   （零样本克隆实测 0 点）" % e["tts_points"])
    info("合成          %6d 点   （字幕 / 剪辑 / 合成实测 0 点）" % e["compose_points"])
    print("-" * 60)
    print("合计 ≈ %d 点  ≈ %.2f 元" % (e["total"], e["total"] / 100.0))
    print("")
    warn("这是**估算**。平台会调价，且你所在租户的实收价可能与公示价不同。")
    info("做预算一律用接口里的 tenant_* 字段，最终以实际扣费为准。")
    if args.avg_seconds > 8:
        print("")
        warn("平均单镜 %ss > 8s —— 同一角色超过 8 秒脸会开始漂移。" % args.avg_seconds)
        info("建议拆到 4~8 秒短镜拼接（这也正好符合短视频节奏）。")
    info("省钱的唯一有效方向是减少视频秒数（少几镜 / 短一点 / 低分辨率），")
    info("而不是省图片钱 —— 出图占总成本不到一成。")
    return 0


# ---------------------------------------------------------------- lint
def lint_shot(s, idx):
    """返回 (errors, warnings) 两个字符串列表。"""
    errs, warns = [], []
    tag = "镜头 #%d" % (idx + 1)

    model = str(s.get("model", "")).lower()

    # 死模型
    if model in {d.lower() for d in DEAD_MODELS}:
        errs.append("%s：模型 %s 在平台列表里但实测不可用，换掉" % (tag, model))

    # 时长
    dur = s.get("duration")
    if dur is not None:
        try:
            d = float(dur)
        except (TypeError, ValueError):
            errs.append("%s：duration 不是数字（%r）" % (tag, dur))
            d = None
        if d is not None:
            if d > 15:
                warns.append("%s：时长 %.1fs > 15s，超长镜头人物必漂移，建议 ≤8s" % (tag, d))
            elif d > 8:
                warns.append("%s：时长 %.1fs > 8s，同角色脸会开始变，建议拆到 4~8s" % (tag, d))

    # 参考图数
    refs = s.get("reference_images") or s.get("referenceImages") or []
    nref = len(refs) if isinstance(refs, (list, tuple)) else 0

    if model.startswith("qwen-image"):
        if nref > IMAGE_REF_LIMIT["qwen-image"]:
            errs.append("%s：qwen-image 参考图上限 %d 张，给了 %d 张"
                        % (tag, IMAGE_REF_LIMIT["qwen-image"], nref))
        warns.append("%s：qwen-image 必须显式带 parameters.n = 1，否则被判「n 必须为 1」" % tag)
    elif model.startswith("gpt-image") or model.startswith("nano-banana"):
        if nref > IMAGE_REF_LIMIT["gpt-image"]:
            errs.append("%s：%s 参考图上限 %d 张，给了 %d 张"
                        % (tag, model.split("-")[0], IMAGE_REF_LIMIT["gpt-image"], nref))
        warns.append("%s：参考图走**顶层 `image_urls` 数组**，不是 input.messages —— 放错了会凭空编人物" % tag)

    # 视频族
    if model.startswith("h3-") or "minimax" in model:
        res = str(s.get("resolution", ""))
        if res and res not in H3_RESOLUTIONS:
            errs.append("%s：h3 的 resolution 只认 %s，给了 %r（720P/1080P/4K 全被拒）"
                        % (tag, "/".join(sorted(H3_RESOLUTIONS)), res))
        if dur is not None:
            ds = str(s.get("duration"))
            if ds not in H3_DURATIONS:
                errs.append("%s：h3 的 duration 只认 %s，给了 %r —— 要吸附到最近的合法值"
                            % (tag, "/".join(sorted(H3_DURATIONS, key=float)), ds))
            if isinstance(dur, (int, float)):
                errs.append("%s：h3 的 duration **必须是字符串**，传数字 %r 会被拒" % (tag, dur))
        ratio = str(s.get("ratio", ""))
        if ratio and ratio not in H3_RATIOS:
            warns.append("%s：h3 的 ratio 只认 %s，%r 会被回落" % (tag, "/".join(sorted(H3_RATIOS)), ratio))

    elif model.startswith("wan") or model == "wan3.0-video":
        res = str(s.get("resolution", ""))
        if res in ("768P", "1080P", "2K", "4K"):
            errs.append("%s：wan 不认 %s（那是 h3 的取值），被拒「未命中可用计费规格」；"
                        "请映射成 720P 或 480P" % (tag, res))
        elif res and res not in WAN_RESOLUTIONS:
            warns.append("%s：wan 常见可用档位是 %s，%r 请实测确认"
                         % (tag, "/".join(sorted(WAN_RESOLUTIONS)), res))
        if dur is not None:
            if float(dur) != int(float(dur)):
                errs.append("%s：wan 的 duration 必须取整（%.1fs 会让任务「处理失败」）" % (tag, float(dur)))
            if float(dur) < WAN_DURATION_MIN:
                errs.append("%s：wan 的 duration 下限 %ds（%.1fs 会失败）"
                            % (tag, WAN_DURATION_MIN, float(dur)))
        # 首尾帧 + 参考图混用
        has_frame = bool(s.get("first_frame") or s.get("firstFrame") or
                         s.get("last_frame") or s.get("lastFrame"))
        if has_frame and nref > 0:
            errs.append("%s：wan 的**首尾帧模式不能与参考图混用**（官方硬约束）。"
                        "拆成「首帧出图带参考图」+「视频只吃首帧」" % tag)

    for fam in SINGLE_IMAGE_VIDEO:
        if model.startswith(fam) and nref > 1:
            errs.append("%s：%s 只吃 1 张图，给了 %d 张会被判参数不符" % (tag, fam, nref))

    return errs, warns


def cmd_lint(args):
    path = args.shots
    if not os.path.exists(path):
        die("找不到文件：%s" % path, 1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        die("JSON 解析失败：%s" % e, 1)

    if isinstance(data, dict):
        data = data.get("shots") or data.get("list") or [data]
    if not isinstance(data, list) or not data:
        die("需要一个镜头数组，或含 shots 字段的对象", 1)

    all_errs, all_warns = [], []
    for i, s in enumerate(data):
        if not isinstance(s, dict):
            all_errs.append("镜头 #%d：不是对象" % (i + 1))
            continue
        e, w = lint_shot(s, i)
        all_errs += e
        all_warns += w

    print("镜头参数体检（离线，不联网）· 共 %d 个镜头" % len(data))
    print("=" * 60)
    if all_errs:
        print("✗ %d 个会 400 的错误：" % len(all_errs))
        for x in all_errs:
            print("   " + x)
    else:
        ok("没有发现会在上游 400 的参数")
    if all_warns:
        print("\n! %d 条建议：" % len(all_warns))
        for x in all_warns:
            print("   " + x)
    print("")
    info("镜头 JSON 形状示例：")
    print(json.dumps([{
        "id": "sg_001",
        "model": "wan3.0-video",
        "resolution": "480P",
        "duration": 5,
        "ratio": "9:16",
        "first_frame": "https://.../sg001.png",
        "reference_images": [],
        "line": "我见过你。"
    }], ensure_ascii=False, indent=2))
    return 0 if not all_errs else 1


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(
        prog="preflight.py",
        description="AI 短剧工厂 · 出片前体检（零依赖，不内嵌任何密钥）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例子：\n"
            "  preflight.py login --key sk-你的key\n"
            "  preflight.py check\n"
            "  preflight.py check --print-source\n"
            "  preflight.py budget --shots 13 --avg-seconds 5 --tier mixed\n"
            "  preflight.py lint --shots my-shots.json\n"
            "\n"
            "退出码：0 通过 / 1 用法错误 / 2 Key 无效或缺失 / 3 网络不可达 / 4 余额不足\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("login", help="校验并保存 Key 到 ~/.a7w/config.json")
    sp.add_argument("--key", help="形如 sk-xxxxxxxx")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("check", help="体检：Key + 余额 + 模型 + 音色")
    sp.add_argument("--key", help="临时指定 Key，不读配置文件")
    sp.add_argument("--print-source", action="store_true",
                    help="只报告 Key 是从哪读到的（不联网、不显示 Key 本身）")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("budget", help="估一集的预算")
    sp.add_argument("--shots", type=int, default=12, help="镜头数（默认 12）")
    sp.add_argument("--avg-seconds", type=float, default=5, help="平均单镜时长秒（默认 5）")
    sp.add_argument("--tier", choices=["cheap", "mixed", "quality"], default="mixed",
                    help="档位策略：cheap=全 480P / mixed=按景别混合（默认）/ quality=全 768P")
    sp.add_argument("--anchors", type=int, default=0, help="资产锚点图数量（默认 0，即复用已有）")
    sp.set_defaults(func=cmd_budget)

    sp = sub.add_parser("lint", help="离线校验镜头参数（不联网）")
    sp.add_argument("--shots", required=True, help="镜头 JSON 文件路径")
    sp.set_defaults(func=cmd_lint)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)
