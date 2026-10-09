"""三剪客 · 4K 旗舰版 —— api.a7w.cn 单档零依赖客户端。

    4K 旗舰版（upscale）  30 点/秒（¥0.30/秒）  单条上限 30 秒  素材：任意公网地址

单档独立包：只做这一件事，所以参数与提示都收窄到这一档。

    info                   看本档单价 / 上限 / 素材要求 / 输入规格（免费）
    login --key sk-xxxx    验证并保存 Key
    whoami                 确认 Key 有效
    points                 查点数余额
    doctor [--url <地址>]  环境体检：Key / 上传入口 / 素材入口判据（零成本实测）/
                           素材可达性 / 本机 ffprobe（免费，不建任务）
    cost <秒数>            只算钱：这一条要多少点（纯本地，一次请求都不发）
    upload <文件>          传到本网关（免费，不建任务）
    enhance --url <地址> --duration 12 --dry-run    白验全部免费闸门，不花钱
    enhance --url <地址> --duration 12 --yes        真提交
    status <taskId>        查状态；成片转存完成后可下载
    tasks                  本包提交过的任务（本地台账）

设计要点（全部是实测踩出来的）
----------------------------------------------------------------------------
1) **`duration` 一定显式传**。服务端逻辑是：
       let d = ceil(Number(payload.duration)||0); if(!d) d = ceil(await probeVideoDuration(url));
       if(!(d>0)) d = 5;
   → 不传就多一次服务端 ffprobe 探测；探测失败**按 5 秒收费**。
   本包一律先本地 ffprobe；拿不到就要求 `--duration`，**绝不静默按 5 秒提交**。
2) **可达性要在扣费之前验**。**它不校验素材可达性**（喂 404 地址也会建任务并扣费），所以本包在扣费前先替你探素材
3) **闸门顺序**（线上服务端）：空 URL → 素材入口判据 → ffprobe 时长 → 输入规格预检 → 冻结扣费。
   → 参数错、入口判据不过、规格不符，**全部在扣费之前返回，天然免费**。
   本包的 `--dry-run` 把扣费之前能验的全验掉。
4) **查询用 `GET <提交路径>/<taskId>`**。不要用 `GET /api/v1/tasks/<id>` ——
   那是网关自有层，查不到这一档的任务。
5) **单价来自 `api.a7w.cn` 在架能力**。免鉴权的 `GET /api/v1/video/viapi/tools`
   目前**不可达**（早先免鉴权 200，后来 401/404）。本包不假装在线值是权威：
   `info` 会如实打印来源，在线可读时自动采用线上值，不可读时退回内置值。
   **价格与规格以线上为准。**

零依赖（只用标准库 + 同目录 `a7w.py`）。不内嵌任何密钥。
Key 来源：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。

素材要求：本档收**任意公网视频地址**（没有入口判据限制）

退出码
    0 成功 · 1 内部错误 · 2 用法错误 · 3 闸门没过 · 4 需要 --yes · 5 预算超限 · 130 中断
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import a7w
except ImportError:                                                 # pragma: no cover
    a7w = None

# ── 常量 ────────────────────────────────────────────────────────────────────
HOST = os.environ.get("A7W_HOST", "https://api.a7w.cn").rstrip("/")
TOOLS_URL = HOST + "/api/v1/video/viapi/tools"
UPLOAD_URL = HOST + "/api/v1/upload"
LEDGER = Path.home() / ".a7w" / "video-vr-tasks.json"

POINTS_PER_YUAN = 100

# 素材入口判据：`viapi/*` 本档只收「本网关素材」（必须 https）
#   · `https://oss.gpu.likeadmin.cn/openapi/` —— 本网关 `POST /api/v1/upload`
#     （字段名 file）返回的地址，也就是 `upload` 子命令拿到的地址（推荐路径）
#   · 本站素材地址（服务端另有入口判据，细节以线上为准）
# `doctor` 会用下面这个「上传域前缀下、但绝不可能存在的路径」去**零成本实测**线上放行了哪些前缀：
# 放行 → 走到素材镜像并 502；未放行 → 400。两条路都在冻结扣费之前，都不花钱。
# ★ 路径里带一段不可能存在的目录名 + 不存在的文件名，**镜像绝不可能成功**，
#   所以这个探针**没有任何**建任务/扣费的路径。
WHITELIST = (
    "https://oss.gpu.likeadmin.cn/openapi/",
    "https://cdn2.jiujiushuyuan.cn/vr/",
    "https://cdn2.jiujiushuyuan.cn/vr2/",
)
GATEWAY_PROBE_URL = ("https://oss.gpu.likeadmin.cn/openapi/"
                     "__a7w_ingress_probe_never_exists__/probe-does-not-exist.mp4")

# 档位表（单档；`info --online` 能读到线上权威值时会覆盖这里的 rate/note）
TIERS = {
    "upscale": dict(
        tier="upscale", path="/api/v1/video/upscale", rate=30, maxsec=30, name="4K 旗舰版",
        viapi=False, action="pixverse/pixverse-upscale",
        spec="生成式；**无输入分辨率门槛**", scene="展示型成片、社媒/广告，观感最强"),
}
TIER_ORDER = ["upscale"]

# `error.code` → 人话（报错必须说人话，并且指向解决办法）
ERR_HUMAN = {
    "empty_url": "没有给 videoUrl。",
    "pixverse_empty_url": "没有给 videoUrl。",
    "url_not_allowed": (
        "这一档**只收本网关素材**：先用 `upload <文件>` 传到本网关，"
        "再把返回的地址交给 --url。任意第三方地址会被服务端拒（在扣费之前，不花钱）。"),
    "invalid_resolution": "`upscale` 当前只支持 targetResolution=4k。",
    "superres_input_too_large": "超分输入需 <1920×1080，请先降分辨率或改用 upscale 档。",
    "interp_input_too_large": "插帧仅支持 ≤720P 输入（该档已下线）。",
    "oss_mirror_failed": (
        "素材转存阿里云上海 OSS 失败（**未扣费**）。常见原因：地址取不到（404）、"
        "不是视频、或需要鉴权。请确认地址可直接下载。"),
    "insufficient_points": "点数余额不足。请到 https://api.a7w.cn/ 充值后重试。",
    "tool_not_launched": "该档位尚未开放。",
    "unauthorized": "Key 无效或未提供。用 `login --key sk-xxx` 保存，或设 A7W_API_KEY。",
    "not_found": "任务不存在（taskId 写错了？或不是这个档位提交的）。",
    "unknown_tool": "平台不认识这个档位 id。用 `info` 看本档。",
    "viapi_not_configured": "平台侧 VIAPI 凭据未配置（服务端问题，不是你的问题）。",
}

# 退出码语义
EXIT_OK, EXIT_INTERNAL, EXIT_USAGE, EXIT_GATE, EXIT_NEED_YES, EXIT_BUDGET, EXIT_INTERRUPT = (
    0, 1, 2, 3, 4, 5, 130)


class VrError(RuntimeError):
    """带 exit code 与 kind 的业务错误。"""

    def __init__(self, message, kind="gate", exit_code=EXIT_GATE):
        RuntimeError.__init__(self, message)
        self.kind = kind
        self.exit_code = exit_code


# ── 输出层：人类可读 / --json 双轨 ──────────────────────────────────────────
class Out(object):
    def __init__(self, as_json=False):
        self.as_json = as_json

    def ok(self, human=None, **data):
        if self.as_json:
            payload = {"ok": True}
            payload.update(data)
            print(json.dumps(payload, ensure_ascii=False, indent=1))
        elif human is not None:
            print(human)
        return EXIT_OK

    def fail(self, message, kind="gate", exit_code=EXIT_GATE, **data):
        if self.as_json:
            payload = {"ok": False, "exit": exit_code,
                       "error": {"kind": kind, "message": message}}
            payload.update(data)
            print(json.dumps(payload, ensure_ascii=False, indent=1))
        else:
            sys.stderr.write("✗ %s\n" % message)
        return exit_code


def _err_payload(text):
    """从上游返回里抠 (code, message)。relay 用 {"error":{...}}，网关自有层用 {"code":,"msg":}。"""
    try:
        j = json.loads(text)
    except (ValueError, TypeError):
        return "", (text or "")[:300]
    if isinstance(j, dict):
        e = j.get("error")
        if isinstance(e, dict):
            return (e.get("code") or ""), (e.get("message") or e.get("msg") or "")
        code = j.get("code")
        if code not in (0, 1, 200, "0", "1", "200", None):
            return str(code), str(j.get("msg") or "")
        if j.get("msg"):
            return str(code), str(j.get("msg"))
    return "", (text or "")[:300]


def _humanize(code, message):
    if code and code in ERR_HUMAN:
        base = ERR_HUMAN[code]
        if message and message not in base:
            return "%s（上游原话：%s）" % (base, message)
        return base
    return message or "上游返回了错误，但没给原因"


def _extract_code(msg):
    for k in ("url_not_allowed", "oss_mirror_failed", "invalid_resolution",
              "superres_input_too_large", "tool_not_launched", "not_found"):
        if k in msg:
            return k
    return ""


# ── 网络层 ──────────────────────────────────────────────────────────────────
def api(method, path_or_url, key=None, body=None, raw=None, ctype=None,
        timeout=120, need_key=True, where=None):
    """发一次请求，返回解析后的 dict；失败抛 VrError。

    `need_key=False`（例如免鉴权的 `/api/v1/video/viapi/tools`）时**不带** Authorization 头 ——
    绝不能塞一个假 Key：网关见到伪 Key 会回 401，把本来可用的免费接口变成"不可用"。
    """
    if a7w is None:
        raise VrError("找不到同目录的 a7w.py，无法调用接口。", "internal", EXIT_INTERNAL)
    url = path_or_url if path_or_url.startswith("http") else (HOST + path_or_url)
    try:
        if key:
            return a7w._request(method, url, key, body=body, raw=raw,
                                content_type=ctype, timeout=timeout)
        # 无鉴权：手工发（a7w._request 强制要求 key 并总带 Authorization 头）
        headers = {"Accept": "application/json", "User-Agent": "a7w-skill/1.0"}
        data = None
        if raw is not None:
            data, headers["Content-Type"] = raw, ctype
        elif body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        code, message = _err_payload(text)
        if exc.code == 402 or code == "insufficient_points":
            raise VrError("%s：%s" % (where or "请求", _humanize("insufficient_points", message)),
                          "budget", EXIT_BUDGET)
        if exc.code == 401 or code == "unauthorized":
            raise VrError("%s：%s" % (where or "请求", _humanize("unauthorized", message)),
                          "usage", EXIT_USAGE)
        raise VrError("%s：%s" % (where or "请求", _humanize(code, message)),
                      "gate", EXIT_GATE)
    except VrError:
        raise
    except Exception as exc:                                        # noqa: BLE001
        msg = str(exc)
        low = msg.lower()
        if "401" in msg or "鉴权失败" in msg or "unauthorized" in low:
            raise VrError("%s：%s" % (where or "请求", _humanize("unauthorized", msg)),
                          "usage", EXIT_USAGE)
        if "402" in msg or "点数不足" in msg or "insufficient" in low:
            raise VrError("%s：%s" % (where or "请求", _humanize("insufficient_points", msg)),
                          "budget", EXIT_BUDGET)
        code = _extract_code(msg)
        if code:
            raise VrError("%s：%s" % (where or "请求", _humanize(code, msg)),
                          "gate", EXIT_GATE)
        raise VrError("%s：%s" % (where or "请求", msg), "call", EXIT_INTERNAL)


def probe_http(url, timeout=25):
    """探素材可达性。返回 (status, content_type, size)。"""
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "a7w-skill/1.0",
                                          "Range": "bytes=0-1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
            crange = r.headers.get("Content-Range") or ""
            clen = r.headers.get("Content-Length")
            if "/" in crange:
                clen = crange.split("/")[-1]
            return r.status, ctype, int(clen) if (clen or "").isdigit() else None
    except urllib.error.HTTPError as exc:
        return exc.code, "", None
    except Exception as exc:                                        # noqa: BLE001
        return 0, str(exc)[:80], None


# ── 本地 ffprobe ────────────────────────────────────────────────────────────
FFPROBE = os.environ.get("FFPROBE", "ffprobe")


def probe_local(path):
    """探测 {duration,width,height,codec}；探测不到返回 {}。"""
    if not shutil.which(FFPROBE):
        return {}
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json", "-show_streams",
             "-show_format", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120).stdout
        d = json.loads(out.decode("utf-8", "replace") or "{}")
    except Exception:                                               # noqa: BLE001
        return {}
    info = {"duration": 0.0, "width": 0, "height": 0, "codec": ""}
    for s in d.get("streams") or []:
        if s.get("codec_type") == "video" and not info["width"]:
            info["width"] = int(s.get("width") or 0)
            info["height"] = int(s.get("height") or 0)
            info["codec"] = s.get("codec_name") or ""
    try:
        info["duration"] = float((d.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        pass
    if not info["duration"]:
        for s in d.get("streams") or []:
            try:
                info["duration"] = float(s.get("duration") or 0)
            except (TypeError, ValueError):
                info["duration"] = 0.0
            if info["duration"]:
                break
    return info if (info["duration"] or info["width"]) else {}


def probe_remote(url, timeout=180):
    """抓远端素材的头 512 KB 到临时文件再 ffprobe（HTTP 上直接 ffprobe 极慢且常失败）。

    MP4 通常 moov 在前，512 KB 足够拿到时长与分辨率。
    返回 (info, 失败原因)。
    """
    if not shutil.which(FFPROBE):
        return {}, "没装 ffprobe（装 ffmpeg 即可），或用 --duration 显式给时长"
    tmp = None
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "a7w-skill/1.0", "Range": "bytes=0-524287"})
        fd, tmp = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as fh, urllib.request.urlopen(req, timeout=timeout) as r:
            fh.write(r.read(524288))
        info = probe_local(tmp)
        if not info:
            return {}, "ffprobe 没能从这个素材读出信息（可能不是视频，或 moov 在文件尾部）"
        return info, ""
    except Exception as exc:                                        # noqa: BLE001
        return {}, "抓取素材失败：%s" % str(exc)[:120]
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── 计费（与中继完全一致） ──────────────────────────────────────────────────
def bill_seconds(duration):
    """先把时长向上取整到整秒，再乘费率（中继就是这么算的）。"""
    return max(1, int(math.ceil(float(duration or 0))))


def cost_points(tier, duration, tiers=None):
    t = (tiers or TIERS)[tier]
    return bill_seconds(duration) * t["rate"]


def yuan(points):
    return round(float(points) / POINTS_PER_YUAN, 2)


def fmt_cost(tier, duration, tiers=None):
    t = (tiers or TIERS)[tier]
    secs = bill_seconds(duration)
    pts = secs * t["rate"]
    return "%d 点（¥%.2f）＝ ceil(%.2fs)=%ds × %d 点/秒" % (
        pts, yuan(pts), float(duration or 0), secs, t["rate"])


# ── 本地台账 ────────────────────────────────────────────────────────────────
def ledger_read():
    if not LEDGER.is_file():
        return {"tasks": []}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"tasks": []}


def ledger_write(doc):
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def ledger_add(rec):
    doc = ledger_read()
    doc.setdefault("tasks", [])
    doc["tasks"] = [t for t in doc["tasks"] if t.get("taskId") != rec.get("taskId")]
    doc["tasks"].append(rec)
    ledger_write(doc)


def ledger_find(task_id):
    for t in ledger_read().get("tasks") or []:
        if t.get("taskId") == task_id:
            return t
    return None


def ledger_update(task_id, **fields):
    doc = ledger_read()
    for t in doc.get("tasks") or []:
        if t.get("taskId") == task_id:
            t.update(fields)
            break
    ledger_write(doc)
    return doc


# ── 档位表：在线取权威值，失败退回内置 ──────────────────────────────────────
def fetch_tiers():
    """返回 (tiers_dict, source)。单档包只有本档一条；**在线权威源当前不可达**。

    历史：2026-10-01 免鉴权 `GET /api/v1/video/viapi/tools` 曾可读（实测 200，1294 B），
    所以旧的十档合一包把它当权威来源。**同一天它就变了**：
        · 无 Key   → 401 `Missing or invalid relay API key.`
        · 有效 Key → 404（落到前端 Nuxt 页面，说明 relay 的 GET 路由不再接它）
    所以这里**仍然尝试**，失败就优雅降级到内置值，并把「在线不可用」如实打出来，
    不假装内置值就是在线的权威值。
    """
    try:
        j = api("GET", TOOLS_URL, need_key=False, timeout=30, where="取档位表")
    except VrError as exc:
        return dict(TIERS), (
            "内置档位表 —— 在线 `%s` 当前不可达（%s）。内置单价取自 api.a7w.cn 在架能力；"
            "**价格与规格以线上为准**。"
            % (TOOLS_URL, str(exc)[:70]))
    online = {}
    for t in (j.get("tools") or []):
        tid = t.get("tool")
        if tid not in TIERS:
            continue
        rec = dict(TIERS[tid])
        rec["rate"] = t.get("perSecond", TIERS[tid]["rate"])
        if t.get("note"):
            rec["note"] = t["note"]
        if t.get("action"):
            rec["action"] = t["action"]
        rec["costPerSecond"] = t.get("costPerSecond")
        online[tid] = rec
    if not online:
        return dict(TIERS), "内置档位表（在线返回为空或没有本档）"
    return online, "在线 GET %s（免鉴权、零成本）" % TOOLS_URL

# ── info（单档包没有多档价目表，只报自己这一档） ──────────────────────────
def cmd_tiers(o, a):
    tid = TIER_ORDER[0]
    if getattr(a, "online", False):
        tiers, source = fetch_tiers()
    else:
        tiers, source = dict(TIERS), (
            "内置档位表（免鉴权在线档位表当前不可达；`info --online` 会再试一次并如实报结果）")
    t = tiers[tid]
    pts = bill_seconds(5) * t["rate"]
    data = dict(tier=tid, name=t["name"], path=t["path"],
                pointsPerSecond=t["rate"], yuanPerSecond=yuan(t["rate"]),
                maxSeconds=t["maxsec"], needsOwnUrl=bool(t["viapi"]),
                spec=t["spec"], scene=t["scene"], action=t.get("action", ""),
                source=source)
    if o.as_json:
        return o.ok(**data)
    L = ["", "本档：%s（%s）" % (t["name"], tid), "=" * 84,
         "  提交路径 : POST %s" % t["path"],
         "  上游动作 : %s" % t.get("action", "-"),
         "  单价     : %d 点/秒（¥%.2f/秒）" % (t["rate"], yuan(t["rate"])),
         "  单条上限 : %ds" % t["maxsec"],
         "  计费口径 : ceil(时长秒) × 单价；1 元 = 100 点",
         "  5 秒样例 : %d 点（¥%.2f）" % (pts, yuan(pts)),
         "  素材要求 : %s" % ("**本网关素材**（先 `upload`）" if t["viapi"] else "任意公网地址"),
         "  输入规格 : %s" % t["spec"],
         "  典型场景 : %s" % t["scene"]]
    if t["viapi"]:
        L.append("")
        L.append("  ⚠️ 本档**只收本网关素材** —— 先用 `upload <文件>` 上传，再用返回的地址提交。")
        L.append("     本包放行的前缀（必须 https）：")
        for p in WHITELIST:
            L.append("       %s" % p)
        L.append("     不再需要任何第三方站点。`doctor` 会**零成本实测**线上到底放行了哪些前缀：")
        L.append("       未放行 → 400 `url_not_allowed`；已放行 → 502 `oss_mirror_failed`。")
        L.append("     → 若线上未放行：改用入口判据内的素材地址，或换 `%s`（收任意公网地址）。"
                 % 'sanjianke-vr-upscale-4k')
    else:
        L.append("")
        L.append("  ⚠️ 本档**不校验素材可达性** —— 喂一个 404 地址它也会 201 并扣费，")
        L.append("     所以本包在扣费前先替你把素材探一遍，探不到就拒提交。")
    L.append("")
    L.append("  来源：%s" % source)
    return o.ok("\n".join(L), **data)


# ── login / whoami / doctor ─────────────────────────────────────────────────
def _resolve_key(explicit):
    if a7w is None:
        raise VrError("找不到同目录的 a7w.py。", "internal", EXIT_INTERNAL)
    try:
        return a7w.load_key(explicit)
    except Exception as exc:                                        # noqa: BLE001
        raise VrError("%s" % exc, "usage", EXIT_USAGE)


def cmd_login(o, a):
    if not a.key:
        return o.fail("`login` 需要 --key sk-xxxx。", "usage", EXIT_USAGE)
    if a7w is None:
        return o.fail("找不到同目录的 a7w.py。", "internal", EXIT_INTERNAL)
    try:
        a7w.cmd_login(a.key)
    except Exception as exc:                                        # noqa: BLE001
        return o.fail("Key 验证失败：%s" % exc, "usage", EXIT_USAGE)
    return o.ok("✓ Key 已验证并保存到 %s（本包不内嵌任何密钥）" % a7w.CONFIG,
                saved=str(a7w.CONFIG))


def cmd_whoami(o, a):
    key = _resolve_key(a.key)
    j = api("GET", "/api/v1/apps", key=key, where="验 Key")
    apps = j.get("data")
    n = len(apps) if isinstance(apps, list) else 0
    return o.ok("✓ Key 有效。\n"
                "  网关自有 app：%d 个\n"
                "  本档走 relay 的 /api/v1/video/upscale，与 app 数无关\n"
                "  Key 来源：--key / A7W_API_KEY / ~/.a7w/config.json" % n,
                apps=n)


def _multipart_probe():
    """构造一个**带真实小文件**的 multipart 探针（免费、不建任务）。

    为什么不带 `file` 字段：那样服务端只回「请使用 file 字段提交一个文件」，拿不到地址。
    而 `doctor` 要回答的正是「`upload` 之后返回的地址长什么样、能不能用」，
    所以这里真上传 1 KB 占位字节，只为拿回一个**真实**的返回地址。
    上传不是建任务、**不扣费**；文件很小（1 KB）。
    """
    import uuid
    b = "----a7wdoctor" + uuid.uuid4().hex
    return (("--%s\r\n" % b).encode("utf-8")
            + ('Content-Disposition: form-data; name="file"; '
               'filename="a7w_doctor_probe.mp4"\r\n'
               'Content-Type: video/mp4\r\n\r\n').encode("utf-8")
            + (b"\x00" * 1024)
            + ("\r\n--%s--\r\n" % b).encode("utf-8"),
            "multipart/form-data; boundary=" + b)


def _post_raw(path, key, body, timeout=60):
    """原始 POST，返回 (http_status, error_code, payload_or_message)。**不抛异常、不重试。**

    为什么不复用 `api()`：`a7w._request` 对 5xx 会退避重试，
    而入口判据探针的正常结果是 `502 oss_mirror_failed` —— 会被重试 4 次。
    这里只要一次，且要拿到机器可判的 `error.code`。
    """
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        HOST + path, data=data, method="POST",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, "", json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        code, message = _err_payload(exc.read().decode("utf-8", "replace"))
        return exc.code, code, message
    except Exception as exc:                                        # noqa: BLE001
        return 0, type(exc).__name__, str(exc)


def _ingress_check(key, chk):
    """**零成本实测**「本网关上传域」是否已进入口判据。

    ★ 只对 `viapi` 档做，**绝不对 `upscale` 做** —— `upscale` 不校验素材可达性，
      探针会真的建任务并冻结 60 点。这里靠 `TIERS[n]["viapi"]` 判断，绝不靠档位名猜。

    ★ 探针地址是「上传域前缀下、但**绝对不可能存在**的路径」
      （`__a7w_ingress_probe_never_exists__/probe-does-not-exist.mp4`）：
        · 未放行 → 400 `url_not_allowed`
        · 已放行 → 素材镜像去取这个文件 → 必然 404 → 502 `oss_mirror_failed`
      两条路都停在**冻结扣费之前**，所以**没有**建任务、也没有扣费的路径。
      本函数**刻意不写「万一建了任务」的兜底分支** —— 那等于承认探针可能花钱。
    """
    probe_tier = next((n for n in TIER_ORDER if TIERS[n]["viapi"]), None)
    if not key:
        chk("入口白名单", "warn", "Key 不可用，无法实测入口判据",
            "先修好「Key 有效性」这一项")
        return
    if not probe_tier:
        chk("入口白名单", "ok",
            "本档**不需要**素材入口判据（收任意公网地址），这一项不影响你")
        return
    status, code, extra = _post_raw(TIERS[probe_tier]["path"], key,
                                    {"videoUrl": GATEWAY_PROBE_URL, "duration": 2})
    if code == "oss_mirror_failed":
        chk("入口白名单", "ok",
            "本网关上传域 `oss.gpu.likeadmin.cn/openapi/` **已放行**"
            "（探针被素材镜像挡在 HTTP %s，**未扣费**）—— "
            "`upload` 返回的地址可以直接提交本档" % status)
    elif code == "url_not_allowed":
        chk("入口白名单", "warn",
            "本网关上传域 `oss.gpu.likeadmin.cn/openapi/` **当前未放行**"
            "（探针被 HTTP %s 拒，**未扣费**）" % status,
            "① 改用本档入口判据内的素材地址（例如本站素材）；"
            "② 或改用 `upscale` 档（不需要判据，收任意公网地址）；"
            "③ 平台侧放行该前缀后，本包**无需改动即刻可用**")
    else:
        # 探针本不该走到这里（既不是 400 也不是 502）。若 HTTP 是 2xx，说明线上行为
        # 与本包假设不符，必须立刻核对 —— 这里只如实报，不做任何"兜底"处理。
        chk("入口白名单", "warn",
            "实测未得出结论：HTTP %s %s" % (status, code or str(extra)[:80]),
            "探针地址是必定不存在的路径，正常只会有 400/502；"
            "若 HTTP 是 2xx，请立刻 `tasks` 核对并向平台反馈")


def cmd_doctor(o, a):
    """零成本体检：Key / 档位表 / 上传入口 / 素材入口判据 / 本机 ffprobe。不建任何任务。"""
    checks = []

    def chk(name, state, detail, fix=""):
        checks.append({"check": name, "state": state, "detail": detail, "fix": fix})

    key = None
    try:
        key = _resolve_key(a.key)
        api("GET", "/api/v1/apps", key=key, timeout=30, where="验 Key")
        chk("Key 有效性", "ok", "Key 可用（GET /api/v1/apps → 200）")
    except VrError as exc:
        chk("Key 有效性", "fail", str(exc),
            "python3 scripts/run.py login --key sk-你的key；或 set A7W_API_KEY=sk-...；"
            "注册领 Key 见 https://api.a7w.cn/")

    if a7w is None:
        chk("客户端", "fail", "同目录找不到 a7w.py", "确认 scripts/ 下有 a7w.py 与 run.py 两个文件")
    else:
        try:
            j = api("GET", TOOLS_URL, need_key=False, timeout=30, where="档位表")
            names = [t.get("tool") for t in (j.get("tools") or [])]
            live = [n for n in TIER_ORDER if n in names]
            if live:
                chk("档位在线", "ok", "免鉴权在线档位表当前**可读**，本档 %s 在线" % ",".join(live))
            else:
                chk("档位在线", "warn",
                    "免鉴权在线档位表当前可读，但**没有返回本档**（%s）" % TIER_ORDER[0],
                    "该档可能已下线或改名；提交会回 404 unknown_tool / 501 tool_not_launched")
        except VrError as exc:
            chk("档位在线", "warn",
                "免费档位表 `GET %s` 当前不可达（将退回内置档位表，功能不受影响）：%s"
                % (TOOLS_URL, str(exc)[:80]))

    up_url = ""
    if key:
        try:
            raw, ctype = _multipart_probe()
            j = api("POST", UPLOAD_URL, key=key, raw=raw, ctype=ctype, timeout=60,
                    where="上传入口")
            up_url = ((j.get("data") or {}).get("url") or "") if isinstance(j, dict) else ""
            chk("上传入口", "ok", "POST /api/v1/upload 可用（带 Key；匿名 401 是正常的）")
        except VrError as exc:
            chk("上传入口", "fail", str(exc), "确认 Key 有效、网络可达")

    if up_url:
        dom = up_url.split("/")[2] if "//" in up_url else up_url
        allowed = any(up_url.startswith(p) for p in WHITELIST)
        if allowed:
            chk("上传地址", "ok",
                "`upload` 返回 %s —— 这就是本档 `--url` 该收的素材地址" % dom)
        else:
            chk("上传地址", "warn",
                "`upload` 返回 %s，不在本包的放行前缀里" % dom,
                "确认用的是本网关 `upload` 原样返回的地址（别自己改写域名）")
    else:
        chk("上传地址", "ok",
            "上传接口已通；真实上传用 `upload <文件>`，它返回的地址即可直接提交")

    _ingress_check(key, chk)

    # 单档包新增：直接吃 --url，把「素材可达性 + 素材入口判定」一起验掉
    if getattr(a, "url", None):
        url = a.url
        if not url.startswith(("http://", "https://")):
            chk("素材可达性", "fail", "--url 必须是 HTTP/HTTPS 地址",
                "本地文件请先 `upload`，再把返回的地址给 --url")
        else:
            status, ctype, nbytes = probe_http(url)
            if status and status < 400:
                chk("素材可达性", "ok", "HTTP %s  %s  %s" % (
                    status, ctype or "-", ("%s B" % nbytes) if nbytes else ""))
            else:
                chk("素材可达性", "fail", "取不到素材（HTTP %s）" % (status or "连接失败"),
                    "确认地址可直接下载（不要带鉴权/防盗链）；提交会白扣费，所以本包先拦")
            chk("素材入口判定", "ok",
                "本档**不需要**素材入口判据（收任意公网地址），这条不影响你")
    if shutil.which(FFPROBE):
        chk("本机 ffprobe", "ok", "%s 可用（能自动取 duration 与分辨率）" % FFPROBE)
    else:
        chk("本机 ffprobe", "warn", "没装 ffprobe",
            "装 ffmpeg（自带 ffprobe）；或在提交时显式传 --duration"
            "（本包不会静默按 5 秒提交）")

    worst = "ok"
    for c in checks:
        if c["state"] == "fail":
            worst = "fail"
            break
        if c["state"] == "warn":
            worst = "warn"

    if o.as_json:
        return o.ok(checks=checks, verdict=worst)
    L = ["", "视频增强台 · 环境体检（全程零成本，不建任务）", "=" * 84]
    mark = {"ok": "✓", "warn": "!", "fail": "✗"}
    for c in checks:
        L.append("  %s %s" % (mark[c["state"]], c["check"]))
        L.append("      %s" % c["detail"])
        if c["fix"]:
            L.append("      → %s" % c["fix"])
    L.append("")
    if worst == "fail":
        L.append("  结论：✗ 有硬性阻碍，先按上面的 → 处理后再说（详见 `info`）。")
    elif worst == "warn":
        L.append("  结论：! 能用，但有注意事项（见上）。")
    else:
        L.append("  结论：✓ 环境就绪。下一步：`cost <秒数>` 先算钱 → `enhance --dry-run` 白验 → 加 --yes 提交。")
    return o.ok("\n".join(L), checks=checks, verdict=worst)


# ── cost ────────────────────────────────────────────────────────────────────
def cmd_cost(o, a):
    """只算钱，一次请求都不发（默认用内置单价；--online 才拉在线权威值）。"""
    if a.online:
        tiers, source = fetch_tiers()
    else:
        tiers, source = dict(TIERS), "内置档位表（免鉴权在线档位表当前不可达）"

    if a.tier != TIER_ORDER[0]:
        return o.fail(
            "本包只做 `%s` 这一档；--tier 给的是 %r。\n"
            "    → 用 `cost <秒数>`，或 `cost --for %s:<秒数>`。"
            % (TIER_ORDER[0], a.tier, TIER_ORDER[0]), "usage", EXIT_USAGE)
    specs = list(a.inputs or []) + list(getattr(a, "for_specs", None) or [])
    if not specs:
        specs = [None]                      # 没给时长：只报单价与样例

    items = []
    for spec in specs:
        tid, dur = a.tier, None
        if spec is None:
            pass
        elif isinstance(spec, tuple):
            tid, dur = spec
        elif ":" in spec and spec.split(":")[0] == TIER_ORDER[0]:
            tid, raw = spec.split(":", 1)
            try:
                dur = float(raw)
            except ValueError:
                return o.fail("--for 的格式是 <档位>:<秒数>，例如 --for superres:12",
                              "usage", EXIT_USAGE)
        else:
            try:
                dur = float(spec)
            except ValueError:
                return o.fail("位置参数只接受秒数，或用 --for <档位>:<秒数>；"
                              "档位用 --tier 指定。", "usage", EXIT_USAGE)
        if tid not in TIERS:
            return o.fail(
                "本包只做 `%s` 这一档；`--for` 里给了别的档位（%r）。\n"
                "    → 用 `cost <秒数>`，或 `cost --for %s:<秒数>`。"
                % (TIER_ORDER[0], tid, TIER_ORDER[0]), "usage", EXIT_USAGE)
        t = tiers.get(tid, TIERS[tid])
        rate = t["rate"]
        if dur is None:
            items.append({"tier": tid, "name": t["name"], "pointsPerSecond": rate,
                          "yuanPerSecond": yuan(rate), "maxSeconds": t["maxsec"],
                          "duration": None,
                          "samples": [{"seconds": s, "points": s * rate, "yuan": yuan(s * rate)}
                                      for s in (5, 10, 30, 60)],
                          "note": "未给时长：只报单价与样例，不编总价"})
            continue
        secs = bill_seconds(dur)
        pts = secs * rate
        warn = None
        if secs > t["maxsec"]:
            warn = ("超过单条上限 %ds（本次计费 %ds）—— 本档 %d 点/秒，提交会被拒，请先切片" % (t["maxsec"], secs, rate))
        items.append({"tier": tid, "name": t["name"], "duration": dur,
                      "billedSeconds": secs, "pointsPerSecond": rate,
                      "points": pts, "yuan": yuan(pts), "maxSeconds": t["maxsec"],
                      "needsOwnUrl": bool(t["viapi"]), "warning": warn})

    total = sum(x.get("points") or 0 for x in items)
    if o.as_json:
        return o.ok(items=items, totalPoints=total, totalYuan=yuan(total), source=source)

    L = ["", "费用估算（纯本地计算，一次请求都没发）", "=" * 84]
    for x in items:
        if x["duration"] is None:
            L.append("  %s（%s）：%d 点/秒（¥%.2f/秒），单条上限 %ds"
                     % (x["tier"], x["name"], x["pointsPerSecond"],
                        x["yuanPerSecond"], x["maxSeconds"]))
            for s in x["samples"]:
                L.append("      %2ds → %6d 点（¥%7.2f）"
                         % (s["seconds"], s["points"], s["yuan"]))
            continue
        L.append("  %s（%s）" % (x["tier"], x["name"]))
        L.append("      时长 %.2fs → 计费 %ds × %d 点/秒 = %d 点（¥%.2f）"
                 % (x["duration"], x["billedSeconds"], x["pointsPerSecond"],
                    x["points"], x["yuan"]))
        if x["needsOwnUrl"]:
            L.append("      ⚠️ 本档只收**本网关素材**（先 `upload`，见 `info` / `doctor`）")
        if x["warning"]:
            L.append("      ✗ %s" % x["warning"])
    if total:
        L.append("")
        L.append("  合计：%d 点（¥%.2f）" % (total, yuan(total)))
    L.append("")
    L.append("  口径：先把时长向上取整到整秒再乘单价（与中继完全一致）；1 元 = 100 点。")
    L.append("  ⚠️ `upscale` **不校验素材可达性** —— 本包会在扣费前先探素材，探不到就拒提交。")
    return o.ok("\n".join(L), items=items, totalPoints=total, totalYuan=yuan(total),
                source=source)


# ── upload ──────────────────────────────────────────────────────────────────
def _upload_raw(key, path):
    """手工打 multipart 到 /api/v1/upload（POST /api/v1/upload，字段名 file）。"""
    if a7w is None:
        raise VrError("找不到同目录的 a7w.py。", "internal", EXIT_INTERNAL)
    raw, ctype = a7w._multipart({}, "file", str(path))
    return a7w._request("POST", UPLOAD_URL, key, raw=raw, content_type=ctype, timeout=900)


def cmd_upload(o, a):
    p = Path(a.file)
    if not p.is_file():
        return o.fail("找不到文件：%s" % p, "usage", EXIT_USAGE)
    key = _resolve_key(a.key)
    info = probe_local(p)
    size = p.stat().st_size
    if not info and not shutil.which(FFPROBE):
        sys.stderr.write("! 没装 ffprobe，无法自动取时长（提交时请显式传 --duration）\n")
    try:
        j = _upload_raw(key, p)
    except VrError as exc:
        return o.fail(str(exc), exc.kind, exc.exit_code)
    except Exception as exc:                                        # noqa: BLE001
        return o.fail("上传失败：%s" % exc, "call", EXIT_INTERNAL)

    data = (j.get("data") or {}) if isinstance(j, dict) else {}
    url = data.get("url") or ""
    if not url:
        return o.fail("上传返回里没有 url：%s" % json.dumps(j, ensure_ascii=False)[:250],
                      "call", EXIT_INTERNAL)
    in_wl = any(url.startswith(pref) for pref in WHITELIST)
    human = ("✓ 上传完成（%d B）\n  url  = %s\n  时长 = %s\n"
             "  这个地址可以直接当 --url 用（本档素材入口判据是否已放行 → 跑 `doctor`）" % (
                 size, url,
                 ("%.2f 秒" % info["duration"]) if info.get("duration") else "未知（装 ffprobe）"))
    if not in_wl:
        human += ("\n  ⚠️ 返回域名不在本包的放行前缀里 —— 请原样使用，不要改写域名。")
    return o.ok(human, url=url, size=size, duration=info.get("duration") or 0,
                width=info.get("width") or 0, height=info.get("height") or 0,
                whitelisted=in_wl)


# ── enhance（主链路，闸门最密） ─────────────────────────────────────────────
def cmd_enhance(o, a):
    if a.tier not in TIERS:
        return o.fail(
            "未知档位 %r；本包只做 `%s` 这一档（独立包）。\n"
            "    → 其它档位请用对应的独立包（例如 `%s`）。"
            % (a.tier, TIER_ORDER[0], 'sanjianke-vr-upscale-4k'), "usage", EXIT_USAGE)
    t = TIERS[a.tier]

    if a.budget is not None and a.budget < 0:
        return o.fail("--budget 不能是负数（单位：点）。", "usage", EXIT_USAGE)
    if not a.url:
        return o.fail("需要 --url <视频地址>（或先 `upload` 拿地址）。", "usage", EXIT_USAGE)
    if not a.url.startswith(("http://", "https://")):
        return o.fail("--url 必须是 HTTP/HTTPS 地址；本地文件请先 `upload`。",
                      "usage", EXIT_USAGE)

    # 闸门 1：Key
    key = _resolve_key(a.key)

    # 闸门 2（仅 viapi 档）：素材入口判据 —— 在扣费之前，免费
    if t["viapi"] and not any(a.url.startswith(pref) for pref in WHITELIST):
        return o.fail(
            "**%s**（`%s`）只收**本网关素材**，你的地址不在入口判据内；提交必然被拒"
            "（好在服务端是在扣费之前拒的，不会花钱）。\n"
            "    → 先把本地文件传上来，再用它返回的地址：\n"
            "        python3 scripts/run.py upload 你的视频.mp4\n"
            "    → 本包只做这一档；想换收任意公网地址的档位，用 `upscale`（4K旗舰版）。\n"
            "    → 或跑 `doctor` 看「入口白名单」这一项的零成本实测结果。" % (
                t["name"], a.tier),
            "gate", EXIT_GATE, tier=a.tier, hint="url_not_allowed")

    # 闸门 3：素材可达性（**每一档都查** —— upscale 自己不查，所以我们替它查）
    status, ctype, nbytes = probe_http(a.url)
    reach = {"status": status, "contentType": ctype, "bytes": nbytes}
    if status == 0 or status >= 400:
        msg = ("素材取不到（HTTP %s），**这样提交会白扣费**：\n"
               "    %s\n"
               "    → `upscale` 档不校验素材可达性，传一个 404 地址它也会 201 并扣钱；\n"
               "      所以本包在这里先拦住。请确认地址可直接下载（不要带鉴权/防盗链）。"
               % (status or "连接失败", a.url[:110]))
        if a.force:
            sys.stderr.write("! --force：素材不可达仍然继续（后果自负）\n")
        else:
            return o.fail(msg + "\n    → 确认要继续就加 --force。", "gate", EXIT_GATE,
                          tier=a.tier, reachable=reach)
    elif ctype and not (ctype.startswith("video/")
                        or ctype in ("application/octet-stream", "binary/octet-stream")):
        sys.stderr.write("! 素材 Content-Type = %s，不像是视频，继续（可不理会）\n" % ctype)

    # 闸门 4：时长（**必须显式**，绝不静默按 5 秒）
    info = {}
    duration = a.duration
    if duration is None:
        if status and status < 400:
            info, why = probe_remote(a.url)
        else:
            info, why = {}, "素材不可达"
        if info.get("duration"):
            duration = info["duration"]
        else:
            return o.fail(
                "拿不到素材时长，**本包不会静默按 5 秒提交**"
                "（那会让你为未知时长付费）。\n"
                "    原因：%s\n"
                "    → 装 ffmpeg/ffprobe 让本包自动探测，或显式传 --duration <秒>。\n"
                "    → 服务端逻辑：不传 duration 时它自己 ffprobe，探测不到就**按 5%% 的计费口径收费**。"
                % (why or "探测失败"),
                "gate", EXIT_GATE, tier=a.tier)
    width = info.get("width") or 0
    height = info.get("height") or 0

    # 闸门 5：单条时长上限
    secs = bill_seconds(duration)
    if secs > t["maxsec"]:
        return o.fail(
            "超过单条上限：本档 %ds，本次计费 %ds（时长 %.2fs 向上取整）。\n"
            "    → 先用 ffmpeg 把片子切片，每段不超过 %ds 再提交。"
            % (t["maxsec"], secs, float(duration), t["maxsec"]),
            "gate", EXIT_GATE, tier=a.tier, maxSeconds=t["maxsec"], billedSeconds=secs)

    # 闸门 6：输入规格预检（服务端也会查，但同样在扣费之前；我们先给一句人话）
    maxdim = max(width, height)
    if maxdim:
        if a.tier.startswith("superres") and maxdim >= 1920:
            return o.fail(
                "超分输入需 <1920×1080（当前 %d×%d）。服务端会回 `superres_input_too_large`。\n"
                "    → 先降分辨率（本档不接受 ≥1920×1080 的输入）。" % (width, height),
                "gate", EXIT_GATE, tier=a.tier)
        if a.tier == "portrait" and maxdim >= 1920:
            return o.fail("人像增强输入需 <1920×1080（当前 %d×%d）。" % (width, height),
                          "gate", EXIT_GATE, tier=a.tier)

    # 闸门 7：预算（单位：点）
    pts = cost_points(a.tier, duration)
    if a.budget is not None and pts > a.budget:
        return o.fail(
            "预算不够：本次需要 %d 点，--budget 只给了 %g 点。\n"
            "    → 调大 --budget（单位：点），或先跑 `cost <秒数>` 看清单价。"
            % (pts, a.budget),
            "budget", EXIT_BUDGET, tier=a.tier, costPoints=pts, budgetPoints=a.budget)

    body = {"videoUrl": a.url, "duration": secs}
    if a.tier == "upscale":
        body["targetResolution"] = "4k"
    if a.callback:
        body["callback_url"] = a.callback

    summary = {"tier": a.tier, "name": t["name"], "path": t["path"],
               "videoUrl": a.url, "durationSeconds": float(duration), "billedSeconds": secs,
               "pointsPerSecond": t["rate"], "costPoints": pts, "costYuan": yuan(pts),
               "width": width, "height": height, "reachable": reach,
               "needsOwnUrl": bool(t["viapi"]), "requestBody": body}

    # --dry-run：把能免费验的全验掉，然后**不发提交请求**
    if a.dry_run:
        L = ["", "DRY-RUN —— 未提交、未扣费；所有免费闸门已通过", "=" * 84,
             "  档位     : %s（%s）" % (a.tier, t["name"]),
             "  路径     : POST %s" % t["path"],
             "  素材     : %s" % a.url[:110],
             "  可达性   : HTTP %s  %s  %s" % (reach["status"], reach["contentType"] or "-",
                                               ("%s B" % reach["bytes"]) if reach["bytes"] else ""),
             "  分辨率   : %s" % (("%d×%d" % (width, height)) if maxdim else "未知"),
             "  计费     : %s" % fmt_cost(a.tier, duration),
             "  素材入口 : %s" % ("需要（已通过）" if t["viapi"] else "不需要"),
             "  请求体   : %s" % json.dumps(body, ensure_ascii=False),
             "",
             "  剩下唯一会花钱的一步就是 POST 上去（上游能不能处理，要花了才知道）。",
             "  正式提交：去掉 --dry-run，加上 --yes。"]
        return o.ok("\n".join(L), dryRun=True, **summary)

    # 闸门 8：需要 --yes 才真花钱
    if not a.yes:
        msg = ("提交会冻结 %d 点（¥%.2f），需要 --yes。\n"
               "  档位：%s（%s）\n  计费：%s\n  素材：%s\n"
               "  → 只是想看流程就加 --dry-run（不花钱）。"
               % (pts, yuan(pts), a.tier, t["name"], fmt_cost(a.tier, duration),
                  a.url[:100]))
        if o.as_json:
            print(json.dumps({"ok": False, "exit": EXIT_NEED_YES,
                              "error": {"kind": "confirm", "message": msg},
                              "dryRunHint": "加 --dry-run 可零成本走一遍全部闸门",
                              **summary}, ensure_ascii=False, indent=1))
            return EXIT_NEED_YES
        sys.stderr.write("✗ " + msg + "\n")
        return EXIT_NEED_YES

    # ── 真提交 ──
    try:
        j = api("POST", t["path"], key=key, body=body, timeout=180,
                where="提交 %s" % a.tier)
    except VrError as exc:
        return o.fail(str(exc), exc.kind, exc.exit_code)

    data = j.get("data") if isinstance(j.get("data"), dict) else {}
    task_id = j.get("taskId") or j.get("task_id") or (data or {}).get("taskId")
    if not task_id:
        return o.fail("提交返回里没有 taskId：%s" % json.dumps(j, ensure_ascii=False)[:300],
                      "call", EXIT_INTERNAL)

    rec = {"taskId": task_id, "tier": a.tier, "name": t["name"], "path": t["path"],
           "videoUrl": a.url, "duration": secs, "costPoints": pts,
           "reservedPoints": j.get("costIn", j.get("cost", pts)),
           "status": j.get("status") or "PENDING", "createdAt": int(time.time()),
           "out": a.out or "", "balance": j.get("balance")}
    ledger_add(rec)

    if a.wait:
        sys.stderr.write("\n已提交，开始轮询（--wait）…\n")
        return _poll_until_done(o, a, key, rec, task_id)

    human = ["", "✓ 已提交", "=" * 84,
             "  taskId : %s" % task_id,
             "  档位   : %s（%s）" % (a.tier, t["name"]),
             "  冻结   : %d 点（¥%.2f）" % (pts, yuan(pts)),
             "  余额   : %s" % (rec["balance"] if rec["balance"] is not None else "未返回"),
             "  状态   : %s" % rec["status"],
             "",
             "  下一步：python3 %s status %s%s" % (
                 _prog(), task_id, " --out %s" % a.out if a.out else " --out out.mp4"),
             "  （成片要先转存到本站 CDN，第一次查询可能仍是 processing，属正常）",
             "  也可加 --wait 让它一次轮询到出片。"]
    return o.ok("\n".join(human), taskId=task_id, status=rec["status"],
                costPoints=pts, costYuan=yuan(pts), reservedPoints=rec["reservedPoints"],
                balance=rec["balance"])


def _prog():
    return "scripts/run.py"


def _finish(o, a, key, rec, task_id, j):
    """统一的收尾：写台账、可选下载、打印结果。"""
    st = j.get("status") or "unknown"
    video = j.get("videoUrl") or ""
    ledger_update(task_id, status=st, videoUrl=video, costPoints=j.get("cost"))
    saved = ""
    if a.out and video:
        try:
            a7w.save(video, a.out)
            saved = a.out
            ledger_update(task_id, savedTo=saved)
        except Exception as exc:                                    # noqa: BLE001
            sys.stderr.write("! 下载失败：%s\n" % exc)

    if st in ("failed", "transfer_failed"):
        return o.fail(
            "任务未成功：status=%s  %s\n    → 失败会自动全额退款"
            "（到 https://api.a7w.cn/ 查流水；`status %s` 可复查）。"
            % (st, j.get("note") or j.get("message") or "", task_id),
            "gate", EXIT_GATE, taskId=task_id, status=st)

    L = ["", "✓ 完成" if st in ("completed", "settled") else "… 处理中", "=" * 84,
         "  taskId : %s" % task_id,
         "  档位   : %s（%s）" % (rec.get("tier"), rec.get("name")),
         "  状态   : %s" % st,
         "  成片   : %s" % (video or "（还没转存好，稍后再查）"),
         "  备注   : %s" % (j.get("note") or "-"),
         "  时长   : %s 秒" % j.get("duration", "-"),
         "  实扣   : %s 点" % j.get("cost", "-")]
    if saved:
        L.append("  已保存 : %s" % saved)
    return o.ok("\n".join(L), taskId=task_id, tier=rec.get("tier"), status=st,
                videoUrl=video or None, posterUrl=j.get("posterUrl") or None,
                duration=j.get("duration"), costPoints=j.get("cost"),
                note=j.get("note"), savedTo=saved or None, raw=j)


def _poll_until_done(o, a, key, rec, task_id):
    deadline = time.time() + a.timeout
    last = None
    while time.time() < deadline:
        time.sleep(a.interval)
        try:
            j = api("GET", "%s/%s" % (rec["path"], task_id), key=key, timeout=60, where="查询")
        except VrError as exc:
            return o.fail(str(exc), exc.kind, exc.exit_code, taskId=task_id)
        st = j.get("status") or "unknown"
        if st != last:
            sys.stderr.write("  状态：%s%s\n" % (st, ("  %s" % j.get("note")) if j.get("note") else ""))
            last = st
        if st in ("completed", "failed", "transfer_failed", "settled"):
            return _finish(o, a, key, rec, task_id, j)
    return o.fail("轮询超时（%ds）。任务可能还在跑，用 `status %s` 稍后查。"
                  % (a.timeout, task_id), "call", EXIT_INTERNAL, taskId=task_id)


# ── status / tasks ──────────────────────────────────────────────────────────
def cmd_status(o, a):
    key = _resolve_key(a.key)
    tier = a.tier
    rec = ledger_find(a.task_id)
    if not tier and rec:
        tier = rec.get("tier")
    if not tier:
        return o.fail(
            "不知道这个 taskId 属于哪个档位。查询路径是 `<提交路径>/<taskId>`，所以需要 --tier。\n"
            "    → 本包提交过的任务会记在 %s，能自动找到；查不到就显式加 --tier %s。"
            % (LEDGER, TIER_ORDER[0]), "usage", EXIT_USAGE)
    if tier not in TIERS:
        return o.fail("未知档位 %r；本包只做 `%s` 这一档。" % (tier, TIER_ORDER[0]),
                      "usage", EXIT_USAGE)

    try:
        j = api("GET", "%s/%s" % (TIERS[tier]["path"], a.task_id), key=key,
                timeout=60, where="查询")
    except VrError as exc:
        return o.fail(str(exc), exc.kind, exc.exit_code)
    return _finish(o, a, key, rec or {"tier": tier, "name": TIERS[tier]["name"]}, a.task_id, j)


def cmd_points(o, a):
    """查点数余额（免费，不建任务）。余额字段名做过兼容；拿不到就如实说。"""
    key = _resolve_key(a.key)
    j = api("GET", "/api/v1/apps", key=key, timeout=30, where="查余额")
    bal = None
    if isinstance(j, dict):
        for k in ("balance", "points", "score", "money", "quota"):
            if isinstance(j.get(k), (int, float)):
                bal = j[k]
                break
        if bal is None:
            for container in (j.get("data"), j.get("user"), j.get("account")):
                if isinstance(container, dict):
                    for k in ("balance", "points", "score", "money", "quota"):
                        if isinstance(container.get(k), (int, float)):
                            bal = container[k]
                            break
                if bal is not None:
                    break
    if bal is None:
        return o.ok("! Key 有效，但网关没有在这个端点返回余额字段。\n"
                    "  → 余额请到 https://api.a7w.cn/ 控制台查看。\n"
                    "  → 提交成功后返回体里的 `balance` 也会被本包记进本地台账。",
                    balance=None, tier=TIER_ORDER[0])
    return o.ok("✓ 点数余额：%s 点（≈ ¥%.2f）" % (bal, yuan(bal)),
                balance=bal, tier=TIER_ORDER[0])


def cmd_tasks(o, a):
    doc = ledger_read()
    rows = (doc.get("tasks") or [])[-a.limit:]
    if o.as_json:
        return o.ok(tasks=rows, ledger=str(LEDGER))
    L = ["", "本包提交过的任务（本地台账 %s）" % LEDGER, "=" * 84]
    if not rows:
        L.append("  （空。`enhance` 提交过的任务会自动记到这里）")
    else:
        L.append("  %-34s %-11s %-12s %7s  %s" % ("taskId", "档位", "状态", "点", "成片"))
        for r in rows:
            L.append("  %-34s %-11s %-12s %7s  %s" % (
                r.get("taskId"), r.get("tier"), r.get("status"), r.get("costPoints"),
                (r.get("videoUrl") or r.get("savedTo") or "")[:42]))
        L.append("")
        L.append("  共 %d 条；冻结/实扣以服务端为准（`status <taskId>` 复查）。" % len(rows))
    return o.ok("\n".join(L), tasks=rows, ledger=str(LEDGER))


# ── CLI ─────────────────────────────────────────────────────────────────────
def _add_common(p, want_key=True):
    """让 `--json` / `--key` 写在子命令**前后都能用**。

    只在父级定义时，argparse 只认「子命令之前」的位置，于是
    `run.py tiers --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补同 dest 的开关，并用 `default=argparse.SUPPRESS`
    保证父级已经设过的值不会被覆盖。

    ⚠️ `want_key=False`（login 自己定义 required 的 `--key`）时**不能再加一次**，
    否则 argparse 会在 `build_parser()` 里就抛
    `ArgumentError: argument --key: conflicting option string: --key`
    —— 那会让**每一个** `--help` 都崩（这正是"py_compile 过、--help 崩"的典型）。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="输出机读 JSON（写在子命令前后都可以）")
    if want_key:
        p.add_argument("--key", default=argparse.SUPPRESS,
                       help="api.a7w.cn 的 API Key（默认 A7W_API_KEY → ~/.a7w/config.json）")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py", allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="三剪客 · 4K 旗舰版 —— api.a7w.cn 单档客户端（upscale，零依赖）",
        epilog="退出码：0 成功 · 1 内部错误 · 2 用法错误 · 3 闸门没过 · "
               "4 需要 --yes · 5 预算超限 · 130 中断")
    ap.add_argument("--json", action="store_true",
                    help="输出机读 JSON（成功 {\"ok\":true,...}；失败 "
                         "{\"ok\":false,\"exit\":N,\"error\":{\"kind\":...}}）")
    ap.add_argument("--key", default=None,
                    help="api.a7w.cn 的 API Key（也可写在子命令后面；默认 "
                         "A7W_API_KEY → ~/.a7w/config.json）")

    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help_text, want_key=True):
        """`want_key=False` 给自己定义 `--key`（required）的子命令用，避免重复注册。"""
        p = sub.add_parser(name, help=help_text, allow_abbrev=False)
        _add_common(p, want_key=want_key)
        return p

    p = add("info", "看本档：单价 / 单条上限 / 素材要求 / 输入规格（免费）")
    p.add_argument("--online", action="store_true",
                   help="再试一次免鉴权的在线档位表（当前不可达，会如实报结果）")
    p.set_defaults(func=cmd_tiers)

    p = add("login", "验证并保存 API Key 到 ~/.a7w/config.json（免费）", want_key=False)
    p.add_argument("--key", required=True, help="sk-xxxx（必填）")
    p.set_defaults(func=cmd_login)

    p = add("whoami", "确认 Key 有效（免费）")
    p.set_defaults(func=cmd_whoami)

    p = add("points", "查点数余额（免费，不建任务）")
    p.set_defaults(func=cmd_points)

    p = add("doctor", "环境体检：Key / 上传入口 / 素材入口判据 / 可达性 / ffprobe（免费，不建任务）")
    p.add_argument("--url", help="（可选）顺手验一个素材地址的可达性与素材入口判定")
    p.set_defaults(func=cmd_doctor)

    p = add("cost", "只算钱，一次请求都不发（单位：点，1 元 = 100 点）")
    p.add_argument("inputs", nargs="*", metavar="SECONDS",
                   help="秒数（配合 --tier）；不传则只报单价与样例")
    p.add_argument("--tier", default=TIER_ORDER[0],
                   help="档位 id（本包只有 %s；保留该参数便于脚本复用）" % TIER_ORDER[0])
    p.add_argument("--for", dest="for_specs", action="append", default=[],
                   help="<秒数> 或 <%s>:<秒数>（兼容多档包写法，可重复）" % TIER_ORDER[0])
    p.add_argument("--online", action="store_true",
                   help="先拉在线权威档位表与单价（免费 GET）")
    p.set_defaults(func=cmd_cost)

    p = add("upload", "把本地视频传到本网关，拿到一个可用地址（免费，不建任务）")
    p.add_argument("file", help="本地视频文件")
    p.set_defaults(func=cmd_upload)

    p = add("enhance", "提交 %s 任务（真花钱；先用 --dry-run 白验一遍）" % TIER_ORDER[0])
    p.add_argument("--url", help="视频地址（%s）" % (
        "本档要求本网关素材地址（先 upload）" if TIERS[TIER_ORDER[0]]["viapi"]
        else "任意公网可下载地址"))
    p.add_argument("--tier", default=TIER_ORDER[0],
                   help="档位 id（本包只有 %s；保留该参数便于脚本复用）" % TIER_ORDER[0])
    p.add_argument("--duration", type=float, default=None,
                   help="素材时长（秒）。强烈建议给：不给会尝试本地 ffprobe，"
                        "拿不到就报错 —— 绝不静默按 5 秒提交")
    p.add_argument("--out", help="完成后把成片下载到这个文件")
    p.add_argument("--budget", type=float, default=None,
                   help="本次花费上限，**单位：点**（1 元 = 100 点）。超出则 exit=5，"
                        "不发提交请求")
    p.add_argument("--dry-run", action="store_true",
                   help="把能免费验的全验掉（素材入口判据/可达性/时长/上限/规格/预算），**不提交**")
    p.add_argument("--yes", action="store_true",
                   help="确认花钱（不加它只会打印报价并 exit=4）")
    p.add_argument("--force", action="store_true",
                   help="素材探不到也照样提交（默认拒绝；后果自负）")
    p.add_argument("--wait", action="store_true", help="提交后一次轮询到出片/失败")
    p.add_argument("--timeout", type=int, default=3600, help="--wait 的轮询总超时（秒）")
    p.add_argument("--interval", type=int, default=15, help="--wait 的轮询间隔（秒）")
    p.add_argument("--callback", help="任务完成回调地址（可选）")
    p.set_defaults(func=cmd_enhance)

    p = add("status", "查任务状态（成片转存完成后带下载地址）")
    p.add_argument("task_id", help="taskId")
    p.add_argument("--tier", help="档位 id（本包提交过的可不填，会自动从本地台账找）")
    p.add_argument("--out", help="成片就绪后下载到这个文件")
    p.set_defaults(func=cmd_status)

    p = add("tasks", "列出本包提交过的任务（读本地台账）")
    p.add_argument("--limit", type=int, default=20, help="显示条数，默认 20")
    p.set_defaults(func=cmd_tasks)

    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not hasattr(a, "key"):
        a.key = None
    o = Out(as_json=getattr(a, "json", False))
    try:
        return a.func(o, a)
    except KeyboardInterrupt:
        return o.fail("已中断（任务可能已经提交，用 `tasks` / `status` 复查）",
                      "interrupt", EXIT_INTERRUPT)
    except VrError as exc:
        return o.fail(str(exc), exc.kind, exc.exit_code)
    except SystemExit:
        raise
    except Exception as exc:                                        # noqa: BLE001
        return o.fail("内部错误：%s: %s" % (type(exc).__name__, exc),
                      "internal", EXIT_INTERNAL)


if __name__ == "__main__":
    sys.exit(main())
