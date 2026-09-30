#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小红书带货直播作战包 · 算力接入层（零第三方依赖）。

本包原有的选品测算 / 时间轴 / 笔记评分 / 合规扫描四个脚本都是**纯离线**的确定性工具，
它们负责「算账」和「卡规则」。这个文件补上另一半：**出稿**。

    商品笔记出稿   run.py note      —— 按本包 `references/note-formulas.md` 的交付契约生成
    直播脚本出稿   run.py live      —— 按本包 `references/live-script-playbook.md` 的五段式生成
    违禁词预检     run.py compliance —— 大模型语义预检，和离线 compliance_check.py 互补
    文本模型清单   run.py models    —— 列出平台当前在架的文本模型

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions     （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py note --product "便携榨汁杯" --price 89 --usp "一杯一袋、USB 充电" --out note.md
    python3 run.py live --minutes 30 --products "便携榨汁杯,收纳盒" --out live.md
    python3 run.py compliance --file note.md --category appliance
    python3 run.py compliance --text "全网最低价，7 天见效" --json
    python3 run.py models --type text

配 Key（三种方式任选）
    python3 run.py note ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx                       # Windows: set A7W_API_KEY=sk-xxxx
    在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（`scripts/a7w.py login --key sk-xxxx`）

设计取舍
    · 离线脚本仍是**第一道闸**：`compliance_check.py` 按子串匹配、零成本、可进 CI 卡门禁；
      这里的大模型预检是**第二道**，能读懂语义与谐音，但会花钱、也有误判，不能替代人工复核，
      更不等于平台官方审核规则，也不构成法律意见。
    · 归因纪律不变——脚本只负责出稿，一次只改一个变量这条规矩由人来守。
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"
DEFAULT_MODEL = "deepseek-chat"      # 实测可用；也可换成 /api/v1/models 里任意 text 模型
CHAT_RETRIES = 3
TERMINAL = ("completed", "failed", "error", "cancelled")


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用
# ---------------------------------------------------------------------------

class ChatError(a7w.A7wError):
    """大模型调用失败。"""


# 最近一次模型调用的 `finish_reason`。**必须记它**，且**初值不猜**（None）。
# 它是区分「该加大 --max-tokens」（=length）与「模型自己写错了 / 响应在路上断了」
# （stop / None）的**唯一**依据 —— 拿 content 长度去猜是错的：
# 同一端点实测在 2989 / 3898 / 3984 字符都能返回完整内容（finish_reason='stop'）。
_LAST_FINISH = {"reason": None, "chars": None}


def _fr_hint():
    """按 `_LAST_FINISH` 给出可执行的处置建议。只认 finish_reason，不认长度。"""
    fr = _LAST_FINISH.get("reason")
    if fr == "length":
        return ("；finish_reason=length —— 输出**确实**被 max_tokens 截断了，"
                "加大 --max-tokens 重试")
    return ("；finish_reason={!r}（**不是 length**）—— **加大 --max-tokens 没用**："
            "这是模型写错了或响应在路上断了，换模型或把这一稿拆段跑".format(fr))


def _outermost_json(text):
    """按**括号配平**从 text 里切出最外层那个完整的 JSON 值，切不出来返回 None。

    为什么不用 `find("{")` / `rfind("}")`：
    外层 JSON 坏掉时（被截断 / 模型吐了语法错），那种切法会把
    **靠后的** `}` 也圈进来，或者相反地切掉一段；更要紧的是原实现
    「逐个 { 试」会从嵌套结构里解出一个**内层**对象交出去，
    上层于是报「缺字段」——**报错指向了错误的方向**。
    配平切法保证：要么给出真正的顶层值，要么老实返回 None。
    """
    if not text:
        return None
    start = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start is None:
        return None
    depth, in_str, esc, end = 0, False, False, None
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    try:
        return json.loads(text[start:end])
    except ValueError:
        return None


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=2048, key=None, timeout=180, json_mode=False):
    """调一次 https://api.a7w.cn/api/v1/chat/completions，返回 (正文, usage)。

    只用标准库。网络抖动与 5xx 退避重试——出稿虽然比视频便宜，
    但半路断掉让人重跑一遍提示词同样烦人。
    """
    key = a7w.load_key(key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json",
               "Accept": "application/json"}

    last_exc = None
    for attempt in range(CHAT_RETRIES):
        req = urllib.request.Request(CHAT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            break
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (502, 503, 504) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("上游 {}，{}s 后重试…\n".format(exc.code, 2 * (attempt + 1)))
                time.sleep(2 * (attempt + 1))
                continue
            try:
                msg = json.loads(text).get("msg") or text[:200]
            except ValueError:
                msg = text[:200]
            if exc.code == 401:
                raise ChatError("鉴权失败（401）：Key 无效或已过期。\n" + str(msg))
            if exc.code == 402:
                raise ChatError("点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise ChatError("模型不存在（404）：{}  "
                                "用 `run.py models` 看平台在架的模型名。".format(msg))
            raise ChatError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试…\n".format(
                    getattr(exc, "reason", exc), 2 * (attempt + 1)))
                time.sleep(2 * (attempt + 1))
                continue
    else:
        raise ChatError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 兼容两种信封：OpenAI 标准 choices / 平台信封 data.choices
    choices = payload.get("choices") or a7w.dig(payload, "data", "choices") or []
    if not choices:
        raise ChatError("返回里没有 choices：{}".format(json.dumps(payload, ensure_ascii=False)[:400]))
    msg = choices[0].get("message") or {}
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    text = (msg.get("content") or "").strip()
    if not text:
        text = (msg.get("reasoning_content") or "").strip()
    if not text:
        raise ChatError("模型返回了空内容（推理类模型请调大 --max-tokens）")
    usage = payload.get("usage") or a7w.dig(payload, "data", "usage") or {}
    return text, usage


def cost_of(usage):
    """把 usage 里的实际扣费抓出来（1 元 = 100 点）。"""
    if not isinstance(usage, dict):
        return None
    return usage.get("points_cost") or usage.get("points") or usage.get("cost")


def read_text(args, required=True):
    """--text / --file / 位置参数三选一。required=False 时允许为空串。"""
    if getattr(args, "file", None):
        try:
            return Path(args.file).read_text(encoding="utf-8").strip(), None
        except OSError as exc:
            return None, "读不到文件 {}：{}".format(args.file, exc)
    t = (getattr(args, "text", None) or getattr(args, "brief", None) or "").strip()
    if not t and required:
        return None, "没有输入内容：给一句话，或用 --text / --file 指定内容。"
    return t, None


def emit(args, text, default_out=None, extra=None):
    """统一收尾：写文件 + 打印摘要 JSON。"""
    out = getattr(args, "out", None)
    if out:
        try:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            sys.stderr.write("写盘失败：{}\n".format(exc))
            return 3
    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "out": out or default_out, "content": text,
                          **(extra or {})}, ensure_ascii=False, indent=1))
    else:
        print(text)
    if out:
        sys.stderr.write("已写入 {}（{} 字）\n".format(out, len(text)))
    return 0


# ---------------------------------------------------------------------------
# 提示词：把本包的交付契约原文搬进 system，保证出稿能被 note_score.py 解析
# ---------------------------------------------------------------------------

NOTE_SYSTEM = """你是小红书电商带货的资深内容操盘手，为本团队「三剪客」工作。
产出必须严格遵守下面的交付契约，四个二级标题一个字都不能改，顺序也不能变：

## 标题候选
5 条，分别属于 痛点型 / 对比型 / 攻略型 / 反常识型 / 价格型，每条一行、≤20 字、
至少含 1 个搜索词、不许用极限词。

## 正文
三段式，纯文本、不用 Markdown 列表：
开头 2 行讲「关我什么事」，禁止以「本产品」开头；
中间 3–6 段给证据，一个卖点一段，具体 > 形容词，每 3–4 行断句，单行 ≤60 字；
结尾 2 行给行动指令。
必须至少写 1 处「不适合谁」的反向说明。

## 标签
一行，1 个大词（最多 2 个）+ 2–3 个精准词 + 1 个长尾词 + 1–2 个品牌词，以 # 开头。

## 封面大字
≤9 字、最多 2 行，3:4 竖构图（1242×1660）用。

红线（违反即作废）：不承诺疗效、不写极限词与绝对化用语、不虚构价格与销量、
不贬低竞品、不诱导私下交易、不诱导好评返现、不留站外联系方式。
证据优先级：实拍 > 检测报告 > 参数 > 形容词；没给的证据不要编。"""

LIVE_SYSTEM = """你是小红书直播间的排品与话术操盘手，为本团队「三剪客」工作。
按下面的固定结构输出直播脚本，五段式比例**不可调换**：

开场留人 10% ｜ 痛点共鸣 17% ｜ 产品引入 23% ｜ 信任建立 23% ｜ 逼单转化 27%

先解决「为什么留下」，再解决「为什么买」。输出格式：

# 直播脚本（N 分钟）
## 时间轴总览
表格：时段 | 分钟区间 | 段落 | 目标 | 关键动作
## 主推品：<商品名>
按单品七步讲解法展开，每步给出**可直接照念的口播**：
痛点提问 20s → 外观展示 15s → 卖点一 40s → 卖点二 40s → 演示验证 60s → 价格锚点 30s → 下单指令 20s
**每个单品只讲 3 个卖点。**
## 排品顺序与上架节奏
引流款 → 利润款 → 形象款 → 清仓款；90 分钟以上循环 2–3 轮；上架时间与主播口播对齐。
## 助播 / 中控配合
## 红线自查
逐条确认没有：承诺疗效、虚构价格、诱导私下交易、虚构库存与销量、贬低竞品、诱导好评返现。
憋单只允许「给等待一个真实理由」，不允许编造倒计时、假装卡顿、虚构「最后 3 件」。"""

COMPLIANCE_SYSTEM = """你是电商带货文案的广告法与平台规则预检员，为本团队「三剪客」工作。
按五类规则逐条检查用户给的文案：
1) 极限词 / 绝对化用语  2) 医疗功效承诺  3) 金融收益承诺  4) 站外导流  5) 平台敏感操作

只输出一个 JSON 对象，不要任何解释文字、不要 Markdown 代码围栏：
{
  "verdict": "blocked | review | check | pass",
  "items": [
    {"level": "high | medium | low", "term": "命中的原文片段",
     "rule": "规则类别", "why": "为什么有风险", "fix": "改成什么"}
  ],
  "notes": "一句话总结，说明这是语义预检、不等于平台官方审核、也不构成法律意见"
}
判定口径：high 必须改、不允许发布；medium 建议改或补真实依据；low 逐条确认。
没有任何命中时 items 为空数组、verdict 为 pass。
不要为了凑数把中性词判成风险；但谐音改写、拼音缩写、拆字这类规避写法要按原意判 high。"""


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_note(a):
    brief, err = read_text(a, required=False)
    if err:
        sys.stderr.write(err + "\n")
        return 2
    detail = []
    if a.product:
        detail.append("商品名：{}".format(a.product))
    if a.price is not None:
        detail.append("售价：{} 元".format(a.price))
    if a.cost is not None:
        detail.append("成本：{} 元".format(a.cost))
    if a.usp:
        detail.append("卖点/证据：{}".format(a.usp))
    if a.audience:
        detail.append("人群：{}".format(a.audience))
    if a.category:
        detail.append("类目：{}".format(a.category))
    if a.evidence:
        detail.append("可用的真实证据：{}".format(a.evidence))
    if not detail and not brief:
        sys.stderr.write("没有任何输入：至少给 --product，或用 --text / --file 描述要写的商品。\n")
        return 2
    if not detail and brief:
        detail.append("商品信息（自由描述）：" + brief)
        brief = ""
    prompt = "写一组小红书商品笔记。\n" + "\n".join(detail)
    if brief:
        prompt += "\n\n补充说明：\n" + brief
    sys.stderr.write("调用 {} · model={}\n".format(CHAT_URL, a.model))
    text, usage = chat(prompt, NOTE_SYSTEM, model=a.model, temperature=a.temperature,
                       max_tokens=a.max_tokens, key=a.key)
    return emit(a, text, extra={"model": a.model, "usage": usage,
                                "points_cost": cost_of(usage), "chars": len(text)})


def cmd_live(a):
    brief, err = read_text(a, required=False)
    if err:
        sys.stderr.write(err + "\n")
        return 2
    products = [p.strip() for p in (a.products or "").split(",") if p.strip()]
    detail = ["直播总时长：{} 分钟".format(a.minutes)]
    if products:
        detail.append("本场商品（按上架顺序）：" + "、".join(products))
    if a.audience:
        detail.append("人群：{}".format(a.audience))
    if a.price is not None:
        detail.append("主推品售价：{} 元".format(a.price))
    if a.usp:
        detail.append("主推品卖点/证据：{}".format(a.usp))
    if not products and not brief and not a.usp:
        sys.stderr.write("没有任何输入：至少给 --products，或用 --text / --file 描述这场直播。\n")
        return 2
    prompt = "排一场小红书带货直播的分钟级脚本。\n" + "\n".join(detail)
    if brief:
        prompt += "\n\n补充说明：\n" + brief
    sys.stderr.write("调用 {} · model={}\n".format(CHAT_URL, a.model))
    text, usage = chat(prompt, LIVE_SYSTEM, model=a.model, temperature=a.temperature,
                       max_tokens=a.max_tokens, key=a.key)
    return emit(a, text, extra={"model": a.model, "usage": usage,
                                "points_cost": cost_of(usage), "chars": len(text)})


def parse_json_loose(text):
    """模型偶尔会带围栏或前后废话，这里逐层剥。"""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
        t = t.strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    # ⚠️ 先按括号配平取**最外层**完整值 —— 别用 find/rfind，
    # 也别逐个 { 试（那会解出内层对象，把报错引向错误的方向）。
    return _outermost_json(t)


def cmd_compliance(a):
    text, err = read_text(a)
    if err:
        sys.stderr.write(err + "\n")
        return 2
    head = "以下是待预检的文案"
    if a.category:
        head += "（类目：{}，请额外按该类目规则判断）".format(a.category)
    prompt = head + "：\n\n" + text
    sys.stderr.write("调用 {} · model={}（语义预检，与离线 compliance_check.py 互补）\n".format(
        CHAT_URL, a.model))
    raw, usage = chat(prompt, COMPLIANCE_SYSTEM, model=a.model, temperature=0.2,
                      max_tokens=a.max_tokens, key=a.key, json_mode=a.json_mode)
    data = parse_json_loose(raw)
    if data is None:
        sys.stderr.write("模型没有返回可解析的 JSON{}，下面是原文。\n".format(_fr_hint()))
        return emit(a, raw, extra={"model": a.model, "usage": usage,
                                   "points_cost": cost_of(usage), "parsed": False})

    items = data.get("items") if isinstance(data.get("items"), list) else []
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: order.get(str((x or {}).get("level", "")).lower(), 3))
    data["items"] = items
    data["model"] = a.model
    data["usage"] = usage
    data["points_cost"] = cost_of(usage)

    if a.format == "json":
        payload = json.dumps(data, ensure_ascii=False, indent=1)
    elif a.format == "csv":
        rows = ["level,term,rule,fix"]
        for it in items:
            cells = [str((it or {}).get(k, "")).replace('"', '""') for k in ("level", "term", "rule", "fix")]
            rows.append(",".join('"{}"'.format(c) for c in cells))
        payload = "\n".join(rows)
    else:
        lines = ["预检结论：**{}**".format(data.get("verdict") or "-"),
                 "", "命中 {} 条：".format(len(items))]
        for it in items:
            lines.append("- [{}] {} —— {}；改法：{}".format(
                (it or {}).get("level", "-"), (it or {}).get("term", "-"),
                (it or {}).get("why", "-"), (it or {}).get("fix", "-")))
        if not items:
            lines.append("- （无）")
        if data.get("notes"):
            lines += ["", "> " + str(data["notes"])]
        payload = "\n".join(lines)

    rc = emit(a, payload, extra={"verdict": data.get("verdict"),
                                 "hits": len(items), "parsed": True,
                                 "points_cost": cost_of(usage)})
    levels = {str((it or {}).get("level", "")).lower() for it in items}
    if not a.quiet_exit:
        if "high" in levels:
            return 1
        if a.strict and levels:
            return 1
    return rc


def cmd_models(a):
    key = a7w.load_key(a.key)
    try:
        payload = a7w._request("GET", MODELS_URL, key, timeout=60)
    except a7w.A7wError as exc:
        sys.stderr.write("拉模型清单失败：{}\n".format(exc))
        return 4
    lst = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(lst, dict):
        lst = lst.get("data") or lst.get("list") or []
    if a.type:
        lst = [m for m in (lst or []) if str((m or {}).get("type_code")) == a.type]
    if a.json:
        print(json.dumps(lst, ensure_ascii=False, indent=1))
        return 0
    print("共 {} 个模型（{}）\n".format(len(lst or []), MODELS_URL))
    for m in (lst or []):
        if not isinstance(m, dict):
            continue
        print("  {:<38} {:<16} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            str(m.get("model_name") or "")[:40]))
    print("\n用法：run.py note --model <model_code> ...")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _add_common(p, with_text=True):
    if with_text:
        p.add_argument("brief", nargs="?",
                       help="一句话描述 / 待处理文案（也可用 --text 或 --file）")
        p.add_argument("--text", dest="text", help="与位置参数等价，便于脚本里书写")
        p.add_argument("--file", help="从文件读输入（与位置参数、--text 三选一）")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="文本模型，默认 {}（用 `run.py models` 看全部）".format(DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度，默认 0.7")
    p.add_argument("--max-tokens", type=int, default=2048, dest="max_tokens",
                   help="最大输出 token，默认 2048")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--out", help="把结果写到这个文件（.md 推荐）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出结果")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="小红书带货直播作战包 · 出稿与预检（走 api.a7w.cn）",
        epilog="端点：POST /api/v1/chat/completions · GET /api/v1/models",
        allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("note", help="按交付契约生成商品笔记（大模型）", allow_abbrev=False)
    _add_common(p)
    p.add_argument("--product", help="商品名")
    p.add_argument("--price", type=float, help="售价（元）")
    p.add_argument("--cost", type=float, help="成本（元）")
    p.add_argument("--usp", help="卖点，逗号分隔")
    p.add_argument("--audience", help="目标人群")
    p.add_argument("--category", help="类目，如 appliance / cosmetics")
    p.add_argument("--evidence", help="可用的真实证据（实拍 / 检测报告 / 参数），没写就不许编")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("live", help="生成五段式分钟级直播脚本（大模型）", allow_abbrev=False)
    _add_common(p)
    p.add_argument("--minutes", type=int, default=30, help="直播总时长（分钟），默认 30")
    p.add_argument("--products", help="本场商品，逗号分隔，按上架顺序")
    p.add_argument("--audience", help="目标人群")
    p.add_argument("--price", type=float, help="主推品售价（元）")
    p.add_argument("--usp", help="主推品卖点/证据")
    p.set_defaults(func=cmd_live)

    p = sub.add_parser("compliance", help="大模型语义违禁词 / 广告法预检", allow_abbrev=False)
    _add_common(p)
    p.add_argument("-c", "--category", help="类目，叠加类目规则")
    p.add_argument("--format", default="md", choices=["md", "json", "csv"], help="输出格式")
    p.add_argument("--strict", action="store_true", help="任何命中都以退出码 1 结束（CI 用）")
    p.add_argument("--quiet-exit", action="store_true", dest="quiet_exit",
                   help="不按命中等级改退出码，只输出结果")
    p.add_argument("--json-mode", action="store_true", dest="json_mode",
                   help="额外要求上游按 JSON 对象返回（部分模型不支持，失败可去掉）")
    p.set_defaults(func=cmd_compliance)

    p = sub.add_parser("models", help="列出平台在架的文本模型（免费）", allow_abbrev=False)
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    p.add_argument("--json", action="store_true", help="原始 JSON")
    p.set_defaults(func=cmd_models)

    a = ap.parse_args(argv)
    if getattr(a, "type", None) == "all":
        a.type = None
    try:
        return a.func(a)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4


if __name__ == "__main__":
    sys.exit(main())
