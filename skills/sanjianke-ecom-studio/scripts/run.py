#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 电商素材台（换装 / 出图 / 一套配齐）

一件衣服、一张商品图，出一整套能上架的电商素材。三条线，价格摆在一起让用户自己挑：

  ① 换装       dressing_diffusion   200 点/次   POST /api/v1/apps/dressing_diffusion/submit
  ② 出图       nano_banana           72 点/次    POST /api/v1/apps/nano_banana/submit
  ③ 主图       gpt-image-2.6          6 点/张    POST /api/v1/images/generations（同步）

## 权威规格（取自网关 /api/v1/apps 与 /api/v1/pricing，只读、免费）

  应用根地址   https://api.a7w.cn/api/v1

  dressing_diffusion/submit
     garment    object  必填  {"data":[{"category":"upper|bottom|full","url":"服装图URL"}]}
     model_url  string  必填  模特图 URL
     异步：返回 task_id；文档说 10~30 秒出图

  nano_banana/submit
     prompt     string  必填
     action     generate | edit（edit 时 image_urls 必填，最多 12 张参考图）
     model      nano-banana / nano-banana-2 / nano-banana-2-lite / nano-banana-pro
                / nano-banana:official / nano-banana-2:official / nano-banana-2-lite:official
                / nano-banana-pro:official
     resolution 1K | 2K | 4K      aspect_ratio auto|1:1|16:9|9:16|4:3|3:4|3:2|2:3|5:4|4:5|21:9
     异步：返回 task_id

  images/generations  gpt-image-2.6
     同步返回；6 点/张，按 data 里实际返回张数计费；b64_json 或 url 两种都要处理

## 这个包真正省钱的地方（都是实测/查表得来的）

  · **换装一次 200 点，出图一张 6 点** —— 同样一套主图，先换装再批量出图只要 218 点，
    全走 72 点的应用线是 4 位数的点。`catalog` 把三条线并排摆出来。
  · **两个应用层 submit 空 body 也会建单**（实测：空 JSON 直接返回 task_id）。所以本包
    **任何情况下都不会发空 body / 缺必填的 submit**，`dress` / `generate` 缺参数直接退 2。
  · **`GET /api/v1/apps/<app>` 不是免费读** —— 实测一次就是该应用的单价（200 / 72 点）。
    `doctor` 因此只用免费的 `/api/v1/models`、`/api/v1/apps`、`/api/v1/pricing`。
  · **轮询只走 `GET /api/v1/tasks/<task_id>`**（免费），不走 `apps/<app>/query`：价格表里
    `dressing_diffusion/*` 是 200、`nano_banana/*` 是 72，而它们的 `query` 没有单独标 0
    （同表的 `pic_lipsync/query`、`flashvsr/query` 都显式标了 0）。

## 子命令

  catalog   三条线的能力与价格对照（免费、离线）
  cost      先算钱（免费）
  doctor    自检 Key / 三个端点 / 价格表（免费，0 建单）
  dress     换装（200 点/次，要 --yes）
  generate  出图（nano 72 点/次，--engine gpt 则 6 点/张）
  batch     一条链路：换装 → 场景图 → 细节图（默认 218 点）
  status    查任务（免费）
  log       本地台账（免费）

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --dress 1 --scene 2 --detail 2
  python3 scripts/run.py doctor
  python3 scripts/run.py dress --model-url https://.../model.jpg \\
      --garment upper=https://.../shirt.jpg --yes
  python3 scripts/run.py generate --prompt "白底商品图，柔光棚拍，无文字" --engine gpt --yes
  python3 scripts/run.py batch --model-url https://.../model.jpg \\
      --garment upper=https://.../shirt.jpg --product "白色亚麻衬衫" --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题先跑 `doctor`，再对照 references/troubleshooting.md。
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid


# ── GBK 编码兜底（2026-11-07 实测修复）──────────────────────────────────────
# Windows 上 stdout 被管道/重定向时，Python 用本地编码（cp936）而不是 UTF-8，
# 遇到 `√`/`×` 这类 cp936 编不出的字符就 UnicodeEncodeError 崩掉。
# 先加 errors='replace' 兜底，再把这类字符换掉，输出才不会变 `?`。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

DEFAULT_MODEL = "gpt-image-2.6"
NANO_MODEL = "nano-banana"

POINTS_DRESS = 200          # 服务端价格表：/api/v1/apps/dressing_diffusion/submit 固定 200 点
POINTS_NANO = 72            # 服务端价格表：/api/v1/apps/nano_banana/submit 固定 72 点
POINTS_IMAGE = 6            # gpt-image-2.6 同步出图，6 点/张

TERMINAL_OK = ("completed", "complete", "done", "success", "succeeded")
TERMINAL_BAD = ("failed", "error", "canceled", "cancelled", "timeout")

LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "ecom-studio-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-ecom-studio/%s" % VERSION


class Fail(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind, self.message, self.exit_code = kind, message, exit_code


def say(msg):
    sys.stderr.write(msg + "\n")


def load_conf(explicit_key=None, explicit_host=None):
    key = None
    if explicit_key:
        key = explicit_key.strip()
    if not key:
        key = (os.environ.get("A7W_API_KEY") or "").strip() or None
    host = (explicit_host or "").strip().rstrip("/") or None
    cfg = os.path.join(os.path.expanduser("~"), ".a7w", "config.json")
    if (not key or not host) and os.path.isfile(cfg):
        try:
            d = json.load(io.open(cfg, encoding="utf-8"))
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                        # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=240):
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=300):
    boundary = "----sanjianke" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, val in fields.items():
        if val is None:
            continue
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                   % (boundary, name, val)).encode("utf-8"))
    for name, path in files:
        fn = os.path.basename(path)
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        buf.write(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                   "Content-Type: %s\r\n\r\n" % (boundary, name, fn, ctype)).encode("utf-8"))
        buf.write(open(path, "rb").read())
        buf.write(b"\r\n")
    buf.write(("--%s--\r\n" % boundary).encode("utf-8"))
    payload = buf.getvalue()
    req = urllib.request.Request(url, method="POST", data=payload, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json",
        "Content-Type": "multipart/form-data; boundary=" + boundary,
        "Content-Length": str(len(payload)), "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise Fail("call", "连不上 %s：%s" % (url, e.reason), EXIT_CALL)
    except Exception as e:                                       # noqa: BLE001
        raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                            # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:300]
        e = d.get("error")
        if isinstance(e, dict):
            bits = [e.get("message") or "", e.get("code") or "", e.get("param") or ""]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:300]
        if isinstance(e, str) and e:
            return e[:300]
    return txt.replace("\n", " ")[:240]


def unwrap(st, txt, what):
    """网关信封：code == 1 才是成功（0 是失败，别写反）。返回 data。"""
    if st != 200:
        raise Fail("call", "%s失败（HTTP %s）：%s" % (what, st, err_text(st, txt)), EXIT_CALL)
    d = jloads(txt)
    if not isinstance(d, dict):
        raise Fail("call", "%s返回不是 JSON：%s" % (what, txt[:200]), EXIT_CALL)
    code = d.get("code")
    if code not in (1, "1"):
        raise Fail("call", "%s失败：%s" % (what, err_text(st, txt)), EXIT_CALL)
    return d.get("data") if "data" in d else d


# ───────────────────────── 价格与闸门 ─────────────────────────
def _lines(a):
    """把 --dress/--scene/--detail/--nano/--gpt 归一成一个计费篮子。"""
    dress = getattr(a, "dress", 0) or 0
    nano = getattr(a, "nano", 0) or 0
    gpt = getattr(a, "gpt", 0) or 0
    scene = getattr(a, "scene", 0) or 0
    detail = getattr(a, "detail", 0) or 0
    return {"dress": dress, "nano": nano, "gpt": gpt + scene + detail, "scene": scene,
            "detail": detail}


def _total(basket):
    return (basket["dress"] * POINTS_DRESS + basket["nano"] * POINTS_NANO
            + basket["gpt"] * POINTS_IMAGE)


def _gate(a, cost, what):
    """两道闸门：预算（exit 5，一个请求都不发）→ 确认（exit 4）。"""
    if cost > a.budget:
        raise Fail("budget", "%s预计 %d 点，超过 --budget %d 点。调大 --budget 或减少张数；"
                             "一个请求都没发。" % (what, cost, a.budget), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm", "%s要真实扣约 %d 点（%.2f 元）。确认请加 --yes；"
                              "想先看请求加 --dry-run。" % (what, cost, cost / 100.0),
                   EXIT_CONFIRM)


# ───────────────────────── 任务轮询与落盘 ─────────────────────────
def _image_urls(node, out=None, hint=""):
    """从任意嵌套里收集图片链接（顺序稳定、去重）。

    只看键名像图片/输出的分支；`callback_url` 这类回调地址不收集。
    """
    if out is None:
        out = []
    if isinstance(node, str):
        h = hint.lower()
        if node.startswith("http") and "callback" not in h and any(
                s in h for s in ("image", "url", "output", "result")):
            if node not in out:
                out.append(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            _image_urls(v, out, str(k))
    elif isinstance(node, list):
        for v in node:
            _image_urls(v, out, hint)
    return out


def _guess_ext(raw, ctype=""):
    if raw[:3] == b"GIF":
        return "gif"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:2] == b"\xff\xd8":
        return "jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if "jpeg" in ctype or "jpg" in ctype:
        return "jpg"
    if "webp" in ctype:
        return "webp"
    if "gif" in ctype:
        return "gif"
    return "png"


def download(url, outdir, prefix, idx):
    os.makedirs(outdir, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as x:
        raw = x.read()
        ctype = x.headers.get("Content-Type") or ""
    ext = _guess_ext(raw, ctype)
    p = os.path.join(outdir, "%s-%02d.%s" % (prefix, idx, ext))
    open(p, "wb").write(raw)
    return p


def save_payload(data, outdir, prefix):
    """把任务结果/同步响应里的图都落盘。返回 (文件, 链接)。"""
    urls = _image_urls(data)
    files = []
    for i, u in enumerate(urls):
        try:
            files.append(download(u, outdir, prefix, i + 1))
        except Exception as e:                                    # noqa: BLE001
            say("  下载失败：%s（%s）" % (u, e))
    return files, urls


def get_task(key, host, task_id):
    st, txt = http_json("GET", host + API_PREFIX + "/tasks/" + task_id, key)
    return unwrap(st, txt, "查询任务")


def poll_task(a, key, host, task_id, timeout=None):
    """只走 /api/v1/tasks/<id>（免费）。绝不走 apps/<app>/query。"""
    deadline = time.time() + (timeout or a.timeout)
    last = None
    while time.time() < deadline:
        time.sleep(3)
        d = get_task(key, host, task_id) or {}
        st = str(d.get("status") or "").lower()
        if st != last:
            say("  状态：%s" % (st or "unknown"))
            last = st
        if st in TERMINAL_OK:
            return d
        if st in TERMINAL_BAD:
            err = d.get("error")
            msg = err.get("message") if isinstance(err, dict) else (err or "")
            raise Fail("call", "任务失败（%s）：%s" % (task_id, msg or "上游未给原因"), EXIT_CALL)
    raise Fail("call", "等任务超时（%s）。任务可能还在跑：python3 scripts/run.py status %s"
               % (task_id, task_id), EXIT_CALL)


# ───────────────────────── 子命令 ─────────────────────────
def cmd_catalog(a, key, host):
    rows = [
        {"line": "dress", "name": "换装 dressing_diffusion", "points": POINTS_DRESS,
         "unit": "次", "endpoint": "POST /api/v1/apps/dressing_diffusion/submit",
         "async": True,
         "does": "模特图 + 服装平铺图 → 穿在身上的效果图",
         "when": "有模特图、要把衣服穿上去；一次一张效果图"},
        {"line": "nano", "name": "出图 nano_banana", "points": POINTS_NANO,
         "unit": "次", "endpoint": "POST /api/v1/apps/nano_banana/submit",
         "async": True,
         "does": "文生图 / 参考图编辑，1K·2K·4K，最多 12 张参考图",
         "when": "要 2K/4K 或要拿参考图改画面；一次一张"},
        {"line": "gpt", "name": "主图 gpt-image-2.6", "points": POINTS_IMAGE,
         "unit": "张", "endpoint": "POST /api/v1/images/generations",
         "async": False,
         "does": "同步出图，一次可要 1~4 张，白底/场景/细节都行",
         "when": "批量场景图与细节图；一张 6 点，最划算"},
    ]
    out = {"ok": True, "prices": {"dress": POINTS_DRESS, "nano": POINTS_NANO,
                                  "gpt": POINTS_IMAGE},
           "lines": rows,
           "sets": [
               {"name": "全 gpt（最快最省）", "detail": "6 张主图/场景/细节",
                "points": 6 * POINTS_IMAGE},
               {"name": "换装 + gpt", "detail": "1 次换装 + 4 张场景/细节",
                "points": POINTS_DRESS + 4 * POINTS_IMAGE},
               {"name": "换装 + nano", "detail": "1 次换装 + 2 次 nano",
                "points": POINTS_DRESS + 2 * POINTS_NANO},
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三条线对照（价格来自服务端价格表，1 元 = 100 点）")
    print()
    print("  %-22s %-10s %-46s %s" % ("线", "单价", "端点", "适合"))
    print("  " + "-" * 112)
    for r in rows:
        print("  %-22s %-10s %-46s %s" % (r["name"], "%d 点/%s" % (r["points"], r["unit"]),
                                          r["endpoint"], r["when"]))
    print()
    print("  一套素材要多少点（同一套：1 张换装 + 2 张场景 + 2 张细节）")
    print("    全 gpt       6 张 × 6 点  =     36 点 = 0.36 元   ← 最划算")
    print("    换装 + gpt   200 + 4 × 6   =    224 点 = 2.24 元")
    print("    换装 + nano  200 + 2 × 72  =    344 点 = 3.44 元")
    print("    全 nano      6 次 × 72 点  =    432 点 = 4.32 元")
    print()
    print("  一句话：换装只买「衣服穿上去」这一张（200 点），其余批量图走 gpt 的 6 点/张。")
    print()
    print("  计费口径：换装 200 点/次、nano 72 点/次是服务端 flat 定价；gpt 按实际返回张数。")
    print("  最终以任务返回的 usage.points_cost 为准，本包把每笔真实扣费记进 `log`。")
    return 0


def cmd_cost(a, key, host):
    b = _lines(a)
    if not (b["dress"] or b["nano"] or b["gpt"]):
        # 什么都不给就按「一套标准素材」算：1 次换装 + 2 张场景 + 2 张细节
        b = {"dress": 1, "nano": 0, "gpt": 4, "scene": 2, "detail": 2}
        defaulted = True
    else:
        defaulted = False
    total = _total(b)
    over = total > a.budget
    out = {"ok": True, "basket": b, "defaulted": defaulted, "overBudget": over,
           "prices": {"dress": POINTS_DRESS, "nano": POINTS_NANO, "gpt": POINTS_IMAGE},
           "total": total, "yuan": round(total / 100.0, 2), "budget": a.budget}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return EXIT_BUDGET if over else 0
    print("预估成本（单位：点，1 元 = 100 点）%s" % ("　按一套标准素材默认" if defaulted else ""))
    print("  换装 × %d  × %d 点 = %d 点" % (b["dress"], POINTS_DRESS, b["dress"] * POINTS_DRESS))
    print("  nano × %d  × %d 点 = %d 点" % (b["nano"], POINTS_NANO, b["nano"] * POINTS_NANO))
    print("  gpt  × %d  × %d 点 = %d 点（场景 %d + 细节 %d + 其它）"
          % (b["gpt"], POINTS_IMAGE, b["gpt"] * POINTS_IMAGE, b["scene"], b["detail"]))
    print("  " + "-" * 40)
    print("  合计 **%d 点 = %.2f 元**（--budget %d 点）" % (total, total / 100.0, a.budget))
    print()
    print("  计费口径：换装 / nano 按次，gpt 按实际返回张数；预算不够时一个请求都不发。")
    print("  同一套全走 gpt 只要 %d 点 —— 见 `catalog` 的三条线对照。" % (6 * POINTS_IMAGE))
    if over:
        say("  超预算：%d 点 > --budget %d 点（真跑会被闸门拦下，不会发请求）"
            % (total, a.budget))
        return EXIT_BUDGET
    return 0


def _apps_index(key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key)
    data = unwrap(st, txt, "拉应用目录")
    lst = data.get("list") if isinstance(data, dict) else data
    idx = {}
    for it in (lst or []):
        if isinstance(it, dict) and it.get("code"):
            idx[it["code"]] = {ap.get("code"): (ap.get("method") or "").upper()
                               for ap in (it.get("apis") or []) if isinstance(ap, dict)}
    return idx


def _price_of(pricing, path):
    p = pricing.get(path) if isinstance(pricing, dict) else None
    if isinstance(p, dict) and p.get("mode") == "flat":
        return p.get("cost")
    return None


def cmd_doctor(a, key, host):
    """全部免费：/models、/apps、/pricing 都是 0 点；gpt 端点用空 prompt 换 422。

    这里刻意**不** GET /api/v1/apps/<app>（实测按应用单价计费：200 / 72 点），
    也**不**向两个应用的 submit 发任何请求（空 body 就会建单）。
    """
    checks = []

    st, txt = http_json("GET", host + API_PREFIX + "/models", key)
    checks.append(("Key 有效 + 模型目录可达", st == 200, "HTTP %s" % st))

    apps = {}
    try:
        apps = _apps_index(key, host)
        checks.append(("换装应用在架（submit）",
                       "submit" in apps.get("dressing_diffusion", {}),
                       "apis: %s" % ",".join(sorted(apps.get("dressing_diffusion", {})))))
        checks.append(("出图应用在架（submit）",
                       "submit" in apps.get("nano_banana", {}),
                       "apis: %s" % ",".join(sorted(apps.get("nano_banana", {})))))
    except Fail as e:
        checks.append(("应用目录可读", False, e.message[:60]))

    try:
        st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key)
        d3 = jloads(txt3) or {}
        # /api/v1/pricing 是**裸对象**（不套 code/data 信封）：{"currency":…, "pricing":{…}}
        pricing = d3.get("pricing") if isinstance(d3, dict) else None
        if pricing is None:
            pricing = (unwrap(st3, txt3, "拉价格表") or {}).get("pricing")
        d_cost = _price_of(pricing, "/api/v1/apps/dressing_diffusion/submit")
        n_cost = _price_of(pricing, "/api/v1/apps/nano_banana/submit")
        checks.append(("价格表：换装 200 点/次", d_cost == POINTS_DRESS,
                       "价格表写 %s 点" % (d_cost,)))
        checks.append(("价格表：出图 72 点/次", n_cost == POINTS_NANO,
                       "价格表写 %s 点" % (n_cost,)))
    except Fail as e:
        checks.append(("价格表可读", False, e.message[:60]))
        checks.append(("价格表口径", False, "未能读取，按本地价目（200/72/6）展示"))

    # gpt-image 端点：带 model + 空 prompt → 文档规定 422（String should have at least 1 character）
    st2, txt2 = http_json("POST", host + API_PREFIX + "/images/generations", key,
                          {"model": DEFAULT_MODEL, "prompt": ""})
    d2 = jloads(txt2) or {}
    e2 = d2.get("error") if isinstance(d2.get("error"), dict) else {}
    ok2 = st2 == 422 and "at least 1 character" in (e2.get("message") or "")
    checks.append(("gpt-image 端点可用（422 即正确）", ok2,
                   "HTTP %s %s" % (st2, (e2.get("message") or "")[:46])))

    try:
        st4, txt4 = http_json("GET", host + API_PREFIX + "/tasks/__probe_not_exist__", key)
        d4 = jloads(txt4) or {}
        checks.append(("任务轮询端点可达（只读）", st4 == 200 and "不存在" in str(d4.get("msg")),
                       "HTTP %s %s" % (st4, (d4.get("msg") or "")[:20])))
    except Fail as e:
        checks.append(("任务轮询端点可达（只读）", False, e.message[:60]))

    out = {"ok": all(c[1] for c in checks),
           "endpoints": {"dress": host + API_PREFIX + "/apps/dressing_diffusion/submit",
                         "nano": host + API_PREFIX + "/apps/nano_banana/submit",
                         "gpt": host + API_PREFIX + "/images/generations"},
           "prices": {"dress": POINTS_DRESS, "nano": POINTS_NANO, "gpt": POINTS_IMAGE},
           "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（全免费：只读目录 + 价格表 + 一次 422 参数校验探针；0 建单、0 扣费）")
    print()
    for n, o, d in checks:
        print("  %s %-34s %s" % ("√" if o else "×", n, d))
    print()
    print("  端点：%s" % out["endpoints"]["dress"])
    print("        %s" % out["endpoints"]["nano"])
    print("        %s（同步）" % out["endpoints"]["gpt"])
    print("  单价：换装 %d 点/次 · 出图 %d 点/次 · 主图 %d 点/张"
          % (POINTS_DRESS, POINTS_NANO, POINTS_IMAGE))
    print()
    print("  说明：两个应用层 submit 一次都不探（空 body 也会建单），端点存在性由"
          " /api/v1/apps 目录与价格表证明。")
    return 0 if out["ok"] else EXIT_GATE


def _url_ok(u):
    return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))


def _parse_garments(items):
    data = []
    for it in items:
        s = (it or "").strip()
        if not s:
            raise Fail("usage", "--garment 不能为空。写法：upper=https://…/shirt.jpg", EXIT_USAGE)
        cat, url = "upper", s
        if "=" in s:
            left, right = s.split("=", 1)
            if left.strip().lower() in ("upper", "bottom", "full"):
                cat, url = left.strip().lower(), right.strip()
        if not _url_ok(url):
            raise Fail("usage", "--garment 的服装图必须是 http(s) 链接：%s" % s, EXIT_USAGE)
        data.append({"category": cat, "url": url})
    return data


def _ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-300:], ensure_ascii=False, indent=1))
    except Exception:                                            # noqa: BLE001
        pass


def _submit_app(a, key, host, app, body, what):
    """向应用层 submit 发请求。**空 body / 缺必填一律在本地拦下**：这两个应用空 body 会建单。"""
    if not isinstance(body, dict) or not body:
        raise Fail("usage", "拒绝发送空 body —— %s 空 body 也会建单扣费。" % what, EXIT_USAGE)
    url = host + API_PREFIX + "/apps/%s/submit" % app
    if a.dry_run:
        return None, url
    say("正在提交%s…" % what)
    st, txt = http_json("POST", url, key, body, timeout=max(60, a.timeout))
    data = unwrap(st, txt, "提交%s" % what)
    if not isinstance(data, dict) or not data.get("task_id"):
        raise Fail("call", "提交%s没拿到 task_id：%s" % (what, txt[:200]), EXIT_CALL)
    say("  task_id=%s（冻结 %s 点）" % (data.get("task_id"), data.get("frozen_points")))
    return data, url


def cmd_dress(a, key, host):
    if not _url_ok(a.model_url):
        raise Fail("usage", "必须给 --model-url（模特图 http/https 链接）", EXIT_USAGE)
    if a.garment_json:
        try:
            garment = json.loads(a.garment_json)
        except ValueError as e:
            raise Fail("usage", "--garment-json 不是合法 JSON：%s" % e, EXIT_USAGE)
    else:
        if not a.garment:
            raise Fail("usage",
                       "必须给至少一个 --garment（服装图）。写法：--garment upper=URL，"
                       "category 可选 upper / bottom / full。", EXIT_USAGE)
        garment = {"data": _parse_garments(a.garment)}
    if not isinstance(garment, dict) or not garment.get("data"):
        raise Fail("usage", "--garment-json 里要有 data 数组（[{category,url}]）", EXIT_USAGE)
    for g in garment["data"]:
        if not _url_ok((g or {}).get("url")):
            raise Fail("usage", "服装图 URL 不是 http(s)：%s" % (g or {}), EXIT_USAGE)

    _gate(a, POINTS_DRESS, "换装")
    body = {"model_url": a.model_url, "garment": garment}

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "line": "dress",
               "url": host + API_PREFIX + "/apps/dressing_diffusion/submit",
               "requestBody": body, "estimatedPoints": POINTS_DRESS,
               "yuan": round(POINTS_DRESS / 100.0, 2)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：%s" % out["url"])
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (POINTS_DRESS, POINTS_DRESS / 100.0))
        return 0

    t0 = time.time()
    data, url = _submit_app(a, key, host, "dressing_diffusion", body, "换装任务")
    task_id = data["task_id"]
    say("  等待换装结果（文档说 10~30 秒）…")
    task = poll_task(a, key, host, task_id)
    dt = time.time() - t0
    files, urls = save_payload(task, a.outdir, a.prefix)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "line": "dress",
           "taskId": task_id, "elapsed": round(dt, 1), "files": files, "urls": urls,
           "billedPoints": POINTS_DRESS, "requested": 1, "returned": len(files)}
    _ledger_add(rec)
    out = {"ok": True, "line": "dress", "taskId": task_id, "elapsed": round(dt, 1),
           "files": files, "urls": urls, "billedPoints": POINTS_DRESS}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("换装完成（%.1fs）" % dt)
    print("  task：%s" % task_id)
    print("  计费：%d 点（%.2f 元）" % (POINTS_DRESS, POINTS_DRESS / 100.0))
    for p in files:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    if not files:
        print("  上游没回图片链接，原始结果：%s" % json.dumps(task, ensure_ascii=False)[:500])
    return 0


def _gpt_generate(a, key, host, prompt, outdir, prefix, n=None):
    """同步出图，6 点/张。返回 (files, urls, got)。

    `a` 可能是 generate，也可能是 batch（batch 没有 --size/--output-format），
    所以这两个参数一律 getattr 取默认值。
    """
    n = n or 1
    fmt = getattr(a, "output_format", None) or "png"
    size = getattr(a, "size", None) or "auto"
    url = host + API_PREFIX + "/images/generations"
    body = {"model": DEFAULT_MODEL, "prompt": prompt, "n": n,
            "output_format": fmt, "response_format": "b64_json"}
    if size and size != "auto":
        body["size"] = size
    st, txt = http_json("POST", url, key, body, timeout=max(180, a.timeout))
    d = unwrap(st, txt, "出图")
    data = d.get("data") if isinstance(d, dict) else None
    files = []
    if isinstance(data, list):
        os.makedirs(outdir, exist_ok=True)
        for i, it in enumerate(data):
            if not isinstance(it, dict):
                continue
            b64 = it.get("b64_json")
            if b64:
                raw = base64.b64decode(b64)
                ext = _guess_ext(raw)
                p = os.path.join(outdir, "%s-%02d.%s" % (prefix, i + 1, ext))
                open(p, "wb").write(raw)
                files.append(p)
    urls = [it.get("url") for it in data if isinstance(it, dict) and it.get("url")] \
        if isinstance(data, list) else []
    for u in urls:
        try:
            files.append(download(u, outdir, prefix, len(files) + 1))
        except Exception as e:                                    # noqa: BLE001
            say("  下载失败：%s（%s）" % (u, e))
    return files, urls, (len(data) if isinstance(data, list) else 0)


def cmd_generate(a, key, host):
    if not (a.prompt or "").strip():
        raise Fail("usage", "必须给 --prompt（画面描述）", EXIT_USAGE)
    if a.engine == "nano":
        cost = POINTS_NANO
        _gate(a, cost, "出图")
        body = {"prompt": a.prompt, "model": a.model, "resolution": a.resolution,
                "action": "edit" if a.image else "generate"}
        if a.aspect_ratio and a.aspect_ratio != "auto":
            body["aspect_ratio"] = a.aspect_ratio
        if a.image:
            body["image_urls"] = list(a.image)
        if a.dry_run:
            out = {"ok": True, "dryRun": True, "line": "nano",
                   "url": host + API_PREFIX + "/apps/nano_banana/submit",
                   "requestBody": body, "estimatedPoints": cost}
            if a.json:
                print(json.dumps(out, ensure_ascii=False))
                return 0
            print("干跑（不提交、不扣费）")
            print("  端点：%s" % out["url"])
            print("  请求：%s" % json.dumps(body, ensure_ascii=False))
            print("  预估：%d 点（%.2f 元）" % (cost, cost / 100.0))
            return 0
        t0 = time.time()
        data, url = _submit_app(a, key, host, "nano_banana", body, "出图任务")
        task_id = data["task_id"]
        say("  等待出图结果…")
        task = poll_task(a, key, host, task_id)
        dt = time.time() - t0
        files, urls = save_payload(task, a.outdir, a.prefix)
        _ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "line": "nano",
                     "taskId": task_id, "elapsed": round(dt, 1), "files": files,
                     "urls": urls, "billedPoints": cost})
        out = {"ok": True, "line": "nano", "taskId": task_id, "elapsed": round(dt, 1),
               "files": files, "urls": urls, "billedPoints": cost}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("出图完成（%.1fs）" % dt)
        print("  task：%s" % task_id)
        print("  计费：%d 点（%.2f 元）" % (cost, cost / 100.0))
        for p in files:
            print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
        if not files:
            print("  上游没回图片链接，原始结果：%s" % json.dumps(task, ensure_ascii=False)[:500])
        return 0

    # gpt 线：6 点/张
    n = a.n
    if not (1 <= n <= 4):
        raise Fail("usage", "n 必须是 1–4（文档：expected an integer in [1, 4]）", EXIT_USAGE)
    cost = POINTS_IMAGE * n
    _gate(a, cost, "出图")
    if a.dry_run:
        body = {"model": DEFAULT_MODEL, "prompt": a.prompt, "n": n,
                "output_format": a.output_format, "response_format": "b64_json"}
        if a.size and a.size != "auto":
            body["size"] = a.size
        out = {"ok": True, "dryRun": True, "line": "gpt",
               "url": host + API_PREFIX + "/images/generations",
               "requestBody": body, "estimatedPoints": cost}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）")
        print("  端点：%s" % out["url"])
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (cost, cost / 100.0))
        return 0
    say("正在出图（%s，%d 张，同步）…" % (DEFAULT_MODEL, n))
    t0 = time.time()
    files, urls, got = _gpt_generate(a, key, host, a.prompt, a.outdir, a.prefix, n)
    dt = time.time() - t0
    billed = POINTS_IMAGE * got
    _ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(got), "line": "gpt",
                 "elapsed": round(dt, 1), "requested": n, "returned": got,
                 "files": files, "urls": urls, "billedPoints": billed})
    out = {"ok": bool(got), "line": "gpt", "elapsed": round(dt, 1), "requested": n,
           "returned": got, "files": files, "urls": urls, "billedPoints": billed}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if got else EXIT_CALL
    if not got:
        say("  响应里没有图。")
        return EXIT_CALL
    print("出图完成（%.1fs）" % dt)
    print("  请求 %d 张 / 实际返回 %d 张，计费 %d 点（%.2f 元）"
          % (n, got, billed, billed / 100.0))
    for p in files:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    return 0


def _scene_prompt(a, kind, i):
    product = a.product or "商品"
    if kind == "scene":
        base = a.scene_prompt or (
            "%s的使用场景图：真实室内环境，自然光，主体居中占画面 60%%，"
            "背景干净有生活感，电商详情页质感，画面里不出现文字、水印、logo" % product)
    else:
        base = a.detail_prompt or (
            "%s的细节特写：微距，材质纹理与做工清晰，浅景深，纯色背景，"
            "柔光棚拍，画面里不出现文字、水印、logo" % product)
    return base if i == 0 else "%s（第 %d 张，换一个构图与光位）" % (base, i + 1)


def cmd_batch(a, key, host):
    if not _url_ok(a.model_url):
        raise Fail("usage", "必须给 --model-url（模特图 http/https 链接）", EXIT_USAGE)
    if not a.garment:
        raise Fail("usage", "必须给 --garment（服装图），写法：--garment upper=URL", EXIT_USAGE)
    if a.scene < 1 and a.detail < 1 and not a.with_dress:
        raise Fail("usage", "一套里至少要有场景图、细节图或换装中的一项", EXIT_USAGE)
    garment = {"data": _parse_garments(a.garment)}
    cost = ((POINTS_DRESS if a.with_dress else 0)
            + (a.scene + a.detail) * POINTS_IMAGE)
    _gate(a, cost, "一套素材")
    plan = []
    if a.with_dress:
        plan.append(("dress", {"model_url": a.model_url, "garment": garment}, POINTS_DRESS))
    for i in range(a.scene):
        plan.append(("scene", {"prompt": _scene_prompt(a, "scene", i)}, POINTS_IMAGE))
    for i in range(a.detail):
        plan.append(("detail", {"prompt": _scene_prompt(a, "detail", i)}, POINTS_IMAGE))

    if a.dry_run:
        out = {"ok": True, "dryRun": True, "line": "batch", "estimatedPoints": cost,
               "steps": [{"kind": k, "body": b, "points": p} for k, b, p in plan]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不扣费）：一套 %d 步，共 %d 点（%.2f 元）"
              % (len(plan), cost, cost / 100.0))
        for i, (k, b, p) in enumerate(plan):
            print("  [%d/%d] %-6s %d 点  %s" % (i + 1, len(plan), k, p,
                                                json.dumps(b, ensure_ascii=False)[:110]))
        return 0

    say("一套素材：%d 步，共 %d 点（%.2f 元）" % (len(plan), cost, cost / 100.0))
    done, files, spent, dress_file = [], [], 0, None
    for i, (kind, body, pts) in enumerate(plan):
        say("[%d/%d] %s…" % (i + 1, len(plan), kind))
        try:
            if kind == "dress":
                data, _ = _submit_app(a, key, host, "dressing_diffusion", body, "换装")
                task = poll_task(a, key, host, data["task_id"])
                fs, urls = save_payload(task, a.outdir, a.prefix + "-dress")
                if fs:
                    dress_file = fs[0]
                done.append({"kind": kind, "taskId": data["task_id"], "files": fs,
                             "urls": urls, "points": pts})
                files += fs
                spent += pts
            else:
                fs, urls, got = _gpt_generate(a, key, host, body["prompt"], a.outdir,
                                              "%s-%s" % (a.prefix, kind), 1)
                spent += POINTS_IMAGE * got
                done.append({"kind": kind, "files": fs, "urls": urls,
                             "points": POINTS_IMAGE * got, "prompt": body["prompt"]})
                files += fs
                if not got:
                    say("  %s 这一张没出图，停止后续步骤（不再花点）。" % kind)
                    break
        except Fail:
            raise
    _ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(files), "line": "batch",
                 "steps": len(done), "files": files, "billedPoints": spent,
                 "product": a.product or ""})
    out = {"ok": bool(files), "line": "batch", "steps": [d["kind"] for d in done],
           "files": files, "billedPoints": spent, "estimatedPoints": cost,
           "dressFile": dress_file}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if files else EXIT_CALL
    print("一套素材完成：%d/%d 步，实际计费 %d 点（%.2f 元）"
          % (len(done), len(plan), spent, spent / 100.0))
    for p in files:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    if not files:
        return EXIT_CALL
    return 0


def cmd_status(a, key, host):
    task_id = a.task_id
    if not task_id:
        raise Fail("usage", "必须给 task_id：python3 scripts/run.py status task_xxx", EXIT_USAGE)
    d = get_task(key, host, task_id) or {}
    st = str(d.get("status") or "").lower()
    files, urls = ([], [])
    if st in TERMINAL_OK and a.outdir:
        files, urls = save_payload(d, a.outdir, a.prefix)
    elif st in TERMINAL_OK:
        urls = _image_urls(d)
    out = {"ok": True, "taskId": task_id, "status": st, "files": files, "urls": urls,
           "error": d.get("error"), "raw": d if a.verbose else None}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % task_id)
    print("  状态：%s" % (st or "unknown"))
    if d.get("error"):
        print("  错误：%s" % json.dumps(d["error"], ensure_ascii=False)[:300])
    for u in urls:
        print("  图片：%s" % u)
    for p in files:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    return 0


def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        arr = json.load(io.open(LEDGER, encoding="utf-8"))
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        if e.get("line") == "batch":
            print("  %s  batch  %d 步  %s 点" % (e.get("at"), e.get("steps") or 0,
                                                 e.get("billedPoints")))
            continue
        print("  %s  %-5s 请求%s/回%s  %s 点  %s 秒" % (
            e.get("at"), e.get("line") or "-", e.get("requested", "-"),
            e.get("returned", "-"), e.get("billedPoints"), e.get("elapsed") or 0))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 电商素材台（换装 200 点/次 · 出图 72 点/次 · 主图 6 点/张）",
        epilog="端点：POST %s/api/v1/apps/dressing_diffusion/submit · "
               "POST %s/api/v1/apps/nano_banana/submit · "
               "POST %s/api/v1/images/generations" % (DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=600, help="点数上限（单位：点，默认 600）")
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="三条线的能力与价格对照（免费、离线）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="先算钱（免费）", allow_abbrev=False)
    p.add_argument("--dress", type=int, default=0, help="换装次数（200 点/次）")
    p.add_argument("--nano", type=int, default=0, help="nano_banana 次数（72 点/次）")
    p.add_argument("--gpt", type=int, default=0, help="gpt-image 张数（6 点/张）")
    p.add_argument("--scene", type=int, default=0, help="场景图张数（= --gpt 的一部分）")
    p.add_argument("--detail", type=int, default=0, help="细节图张数（= --gpt 的一部分）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 Key / 端点 / 价格表（免费，0 建单）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    def _bill_args(p):
        p.add_argument("--outdir", default=".", help="图片保存目录（默认当前目录）")
        p.add_argument("--prefix", default="shot", help="文件名前缀")
        p.add_argument("--timeout", type=int, default=300, help="单步超时秒数")
        p.add_argument("--yes", action="store_true", help="确认真实扣费")
        p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")

    p = sub.add_parser("dress", help="换装（dressing_diffusion，200 点/次）",
                       allow_abbrev=False)
    p.add_argument("--model-url", required=False, help="模特图 http(s) 链接（必填）")
    p.add_argument("--garment", action="append",
                   help="服装图，可重复：upper=URL / bottom=URL / full=URL（category 可省，默认 upper）")
    p.add_argument("--garment-json", help="高级：直接给 garment 对象 JSON（{\"data\":[...]}）")
    _bill_args(p)
    p.set_defaults(fn=cmd_dress)

    p = sub.add_parser("generate", help="出图（nano 72 点/次；--engine gpt 则 6 点/张）",
                       allow_abbrev=False)
    p.add_argument("--engine", choices=["nano", "gpt"], default="nano",
                   help="nano=72 点/次（默认）；gpt=6 点/张")
    p.add_argument("--prompt", help="画面描述（必填）")
    p.add_argument("--model", default=NANO_MODEL, help="nano 模型（默认 nano-banana）")
    p.add_argument("--resolution", default="1K", choices=["1K", "2K", "4K"],
                   help="nano 分辨率（默认 1K）")
    p.add_argument("--aspect-ratio", default="auto",
                   help="auto / 1:1 / 3:4 / 4:5 / 16:9 …（默认 auto）")
    p.add_argument("--image", action="append",
                   help="nano 参考图 URL（可重复，action 自动转 edit）")
    p.add_argument("--n", type=int, default=1, help="gpt 张数 1–4（默认 1）")
    p.add_argument("--size", default="auto", help="gpt 尺寸：auto / 1024x1024 / 1k …")
    p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
    _bill_args(p)
    p.set_defaults(fn=cmd_generate)

    p = sub.add_parser("batch", help="一条链路：换装 → 场景图 → 细节图", allow_abbrev=False)
    p.add_argument("--model-url", required=False, help="模特图 http(s) 链接（必填）")
    p.add_argument("--garment", action="append", help="服装图：upper=URL / bottom=URL / full=URL")
    p.add_argument("--product", default="", help="商品名（写进提示词）")
    p.add_argument("--scene", type=int, default=2, help="场景图张数（默认 2，6 点/张）")
    p.add_argument("--detail", type=int, default=2, help="细节图张数（默认 2，6 点/张）")
    p.add_argument("--scene-prompt", help="覆盖场景图提示词")
    p.add_argument("--detail-prompt", help="覆盖细节图提示词")
    p.add_argument("--no-dress", dest="with_dress", action="store_false",
                   help="跳过换装那一步（省 200 点）")
    p.set_defaults(with_dress=True)
    _bill_args(p)
    p.set_defaults(fn=cmd_batch)

    p = sub.add_parser("status", help="查任务（免费）", allow_abbrev=False)
    p.add_argument("task_id", nargs="?", help="任务 ID（task_xxx 或纯数字 ID）")
    p.add_argument("--outdir", help="给了就顺手把结果图下载到这个目录")
    p.add_argument("--prefix", default="shot", help="下载文件名前缀")
    p.add_argument("--verbose", action="store_true", help="把完整原始返回也打进 JSON")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


NO_KEY_NEEDED = (cmd_catalog, cmd_cost, cmd_log)


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    key, host = load_conf(a.key, a.host)
    if not key and a.fn not in NO_KEY_NEEDED:
        raise Fail("usage",
                   "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                   "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                   EXIT_USAGE)
    try:
        return a.fn(a, key, host)
    except Fail as e:
        if a.json:
            print(json.dumps({"ok": False, "exit": e.exit_code,
                              "error": {"kind": e.kind, "message": e.message}},
                             ensure_ascii=False))
        else:
            say("失败：%s" % e.message)
        return e.exit_code


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        say("已中断。")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
