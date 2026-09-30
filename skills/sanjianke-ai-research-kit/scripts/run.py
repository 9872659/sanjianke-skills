#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · AI 科研全流程 —— 算力接入层（零第三方依赖）。

`references/` 那四份资料管的是**流程纪律**：选题怎么收敛、文献怎么筛、
实验怎么设计、稿子怎么自查。这个文件补上另一半：流程里那些「要动手做」的动作
——**抽取、摘要、对比、文档问答**——直接走 `api.a7w.cn`，本机只要求 Python 3.8+。

真实请求的端点（全部在 api.a7w.cn 上，逐条可核对）：

    大模型（OpenAI 兼容协议）
        POST https://api.a7w.cn/api/v1/chat/completions
        GET  https://api.a7w.cn/api/v1/models              # 模型名先查再猜
    文档问答（平台先把文档解析好，再交给大模型）
        POST https://api.a7w.cn/api/v1/apps/file_qa/chat    # 同步；mode=async 可转异步

子命令

    extract    从一份材料里抽结构化字段（研究问题 / 方法 / 数据 / 结论 / 局限 …）
    summarize  把长材料压成可复核的摘要；要求逐条标出来源段落
    matrix     多份材料横向对比，产出综述矩阵（Markdown 表）——找空白点用
    review     审稿人视角预演：把稿子按「可能被拒的理由」挑一遍
    doc-qa     就着一份**公网**文档提问 → file_qa/chat
    models     列出平台在架的文本模型（别猜模型名）
    chat       裸调一次大模型（自己给 system / prompt）

用法

    python3 run.py models --filter deepseek
    python3 run.py extract --file 01-文献卡/paper-2024-x.md --out card.json
    python3 run.py extract --text "$(cat note.md)" --fields "主张,变量,样本量,结论,局限"
    python3 run.py summarize --file 长综述.md --length medium --out 摘要.md
    python3 run.py matrix --file a.md --file b.md --file c.md --out 02-综述矩阵.md
    python3 run.py review --file 04-草稿/正文.md --venue "目标会议"
    python3 run.py doc-qa --url https://example.org/paper.pdf "这篇的核心主张是什么？"
    python3 run.py chat --system "只输出 JSON" --prompt "给我 3 个字段名"

配 Key（三种方式任选）

    python3 run.py ... --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows: set A7W_API_KEY=sk-xxxx
    在 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（`scripts/a7w.py login --key sk-xxxx`）

计费与口径

    · 大模型按 **点 / 百万 Token** 计，输入输出**分别计价**；1 元 = 100 点，失败全额退回。
      实测：一次极小的问答（`max_tokens=64`）在 1 点以内。
    · `file_qa/chat` 同样按 Token 计（输入 2,600 点/百万 Token、输出 13,000 点/百万 Token）。
      实测：124 输入 + 36 输出 = **0.79 点 ≈ 0.008 元**。
    · 平台响应信封里 **`code == 1` 才算业务成功**（不是 0）；HTTP 200 不代表成功。
      实际扣费看 `usage.points_cost`。

边界（和方法论部分保持一致，别越界）
    · 这里的大模型只做**整理与表达**：抽取的是材料里已有的事实，不生成、不补全、
      **不猜测参考文献**。材料里没有的字段一律写「未提供」，由你回原文核对。
    · `file_qa/chat` 只吃**公网 HTTP(S) 文档地址**（`file_urls`，1~8 个），
      不支持本地文件；要问本地文件先把内容贴进 `--text`。
    · 模型输出**不构成结论**。选题价值、引用真伪、实验解释、录用与否，都由人负责。
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"
FILE_QA_ENDPOINT = "/api/v1/apps/file_qa/chat"
FILE_QA_APP, FILE_QA_API = "file_qa", "chat"
DEFAULT_MODEL = "deepseek-chat"      # 实测可用；等价于模型清单里的 DeepSeek-V4-Flash
CHAT_RETRIES = 3
TERMINAL = ("completed", "failed", "error", "cancelled")

# 抽取/对比的公共纪律，写进 system prompt —— 与方法论里的「不编造引用」一致
DISCIPLINE = (
    "你是一个严谨的科研助手，只做**材料整理**，不做价值判断。硬性要求：\n"
    "1. 只使用给定材料中出现的信息；材料里没有的字段，值写「未提供」，"
    "并在该项后加「(需回原文核对)」。\n"
    "2. 绝对不生成、不补全、不猜测参考文献条目、作者、年份、DOI、数据与数字。\n"
    "3. 引用材料原话时用 > 引用块，并标明它出自哪份材料（文件名或标题）。\n"
    "4. 材料之间冲突时，把冲突原样列出并标明各自出处，不要替它们下结论。\n"
    "5. 不写「研究表明」「众所周知」这类没有出处的断言。\n"
)


class ChatError(a7w.A7wError):
    """大模型 / 文档问答调用失败。"""


# ---------------------------------------------------------------------------
# 底层：OpenAI 兼容的大模型调用
# ---------------------------------------------------------------------------

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


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.3,
         max_tokens=2048, key=None, timeout=300, json_mode=False, stream=False):
    """调一次 https://api.a7w.cn/api/v1/chat/completions。

    返回 (正文, usage)。流式模式下正文边收边写到 stdout，同时把全文返回。
    只用标准库；网络抖动与 5xx 退避重试——半路断掉重跑一遍提示词同样烦人。
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
    if stream:
        body["stream"] = True
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json",
               "Accept": "application/json"}

    last_exc = None
    for attempt in range(CHAT_RETRIES):
        req = urllib.request.Request(CHAT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if stream:
                    return _read_sse(resp)
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
            if exc.code == 400:
                raise ChatError("参数错误（400）：{}  "
                                "模型名与参数以 `run.py models` 和各接口 schema 为准。".format(msg))
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
        raise ChatError("返回里没有 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:400]))
    msg = choices[0].get("message") or {}
    finish_reason = (choices[0] or {}).get("finish_reason")
    _LAST_FINISH["reason"] = finish_reason
    text = (msg.get("content") or "").strip()
    if not text:
        # 推理类模型的思维链字段名在两条线路上不一致，两个都试
        text = ((msg.get("reasoning_content") or msg.get("reasoning") or "")).strip()
    if not text:
        raise ChatError("模型返回了空内容（推理类模型请调大 --max-tokens）")
    usage = payload.get("usage") or a7w.dig(payload, "data", "usage") or {}
    return text, usage


def _read_sse(resp):
    """读 SSE 流：逐行 `data: {...}`，取 choices[0].delta.content，`[DONE]` 结束。"""
    chunks, usage = [], {}
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        body = line[5:].strip()
        if body == "[DONE]":
            break
        try:
            obj = json.loads(body)
        except ValueError:
            continue
        if isinstance(obj.get("usage"), dict):
            usage = obj["usage"]
        choices = obj.get("choices") or a7w.dig(obj, "data", "choices") or []
        if choices:
            piece = ((choices[0].get("delta") or {}).get("content")
                     or (choices[0].get("message") or {}).get("content") or "")
            if piece:
                chunks.append(piece)
                sys.stdout.write(piece)
                sys.stdout.flush()
    sys.stdout.write("\n")
    return "".join(chunks), usage


# ---------------------------------------------------------------------------
# 底层：文档问答（file_qa/chat）
# ---------------------------------------------------------------------------

def doc_qa(file_urls, question, key=None, mode=None, stream=False,
           metadata=None, timeout=600):
    """POST /api/v1/apps/file_qa/chat —— 公网文档问答。

    **坑**：参数是 `file_urls`（数组，1~8 个公网 HTTP(S) 地址）+ `question`，
    不支持本地路径。响应正文在 `result.answer`，token 用量在 `result.usage`。
    """
    key = a7w.load_key(key)
    body = {"file_urls": list(file_urls), "question": question}
    if mode:
        body["mode"] = mode
    if metadata:
        body["metadata"] = metadata
    if stream:
        return _doc_qa_stream(body, key, timeout)

    res = a7w.call(FILE_QA_APP, FILE_QA_API, body, key=key, wait=True, quiet=True,
                   timeout=timeout)
    if not isinstance(res, dict):
        return {"answer": str(res), "usage": None, "points_cost": None, "raw": res}
    answer = a7w.dig(res, "result", "answer") or a7w.dig(res, "answer") or ""
    # 异步模式可能返回 task_id：a7w.call 已轮询过，这里再兜一次
    if not answer and a7w.dig(res, "task_id"):
        t = a7w._unwrap(a7w._request(
            "GET", "{}/api/v1/tasks/{}".format(a7w.HOST, a7w.dig(res, "task_id")), key))
        answer = a7w.dig(t, "result", "answer") or a7w.dig(t, "answer") or ""
    return {"answer": answer,
            "usage": a7w.dig(res, "result", "usage") or a7w.dig(res, "usage"),
            "points_cost": points_of(res),
            "raw": res}


def _doc_qa_stream(body, key, timeout):
    """`stream: true` 时接口返回 SSE。逐行取，几种可能的正文键都认。"""
    body = dict(body)
    body["stream"] = True
    req = urllib.request.Request(
        a7w.HOST + FILE_QA_ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream"}, method="POST")
    chunks, usage, raw = [], None, []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            raw.append(text)
            if not text.startswith("data:"):
                continue
            payload = text[5:].strip()
            if payload in ("", "[DONE]"):
                continue
            try:
                obj = json.loads(payload)
            except ValueError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("usage"), dict):
                usage = obj["usage"]
            piece = (a7w.dig(obj, "answer") or a7w.dig(obj, "result", "answer")
                     or a7w.dig(obj, "content") or a7w.dig(obj, "text"))
            if not isinstance(piece, str) or not piece:
                choices = obj.get("choices") or a7w.dig(obj, "data", "choices") or []
                if choices:
                    piece = ((choices[0].get("delta") or {}).get("content")
                             or (choices[0].get("message") or {}).get("content") or "")
            if isinstance(piece, str) and piece:
                chunks.append(piece)
                sys.stdout.write(piece)
                sys.stdout.flush()
    sys.stdout.write("\n")
    return {"answer": "".join(chunks), "usage": usage, "points_cost": None,
            "raw": "\n".join(raw)}


def points_of(res):
    """把实际扣点抓出来（同步接口见过 `actual_points`，异步任务见过 `points_cost`）。"""
    for holder in (a7w.dig(res, "usage"), res, a7w.dig(res, "result", "usage")):
        if not isinstance(holder, dict):
            continue
        for k in ("points_cost", "actual_points", "points", "cost"):
            v = holder.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    return None


def money(points):
    return None if points is None else points / 100.0     # 1 元 = 100 点


def usage_line(usage, points):
    """一行把用量讲清楚：token 与扣点。"""
    bits = []
    if isinstance(usage, dict) and usage:
        bits.append("token {}→{}（共 {}）".format(
            usage.get("input_tokens", usage.get("prompt_tokens", "?")),
            usage.get("output_tokens", usage.get("completion_tokens", "?")),
            usage.get("total_tokens", "?")))
    if points is not None:
        bits.append("扣点 {} ≈ {:.4f} 元".format(points, money(points)))
    return "　".join(bits) if bits else "（平台未返回用量）"


# ---------------------------------------------------------------------------
# 材料读取与输出
# ---------------------------------------------------------------------------

def read_material(path):
    p = Path(path)
    if not p.is_file():
        raise ChatError("找不到材料：{}".format(p))
    text = p.read_text(encoding="utf-8", errors="replace")
    return p.name, text


def collect_materials(a):
    """把 --file / --text 收成 [(名字, 正文)]。"""
    items = []
    for f in (a.file or []):
        items.append(read_material(f))
    if a.text:
        items.append(("(命令行文本)", a.text))
    if a.dir:
        root = Path(a.dir)
        if not root.is_dir():
            raise ChatError("找不到目录：{}".format(root))
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".csv", ".json"):
                items.append(read_material(p))
    if not items:
        raise ChatError("没有材料。用 --file / --text / --dir 给一份。")
    return items


def as_block(items, per_item_limit=24000):
    """把材料拼成带编号的引用块——编号是后面让模型标出处用的。"""
    out = []
    for i, (name, text) in enumerate(items, 1):
        clipped = text[:per_item_limit]
        if len(text) > per_item_limit:
            clipped += "\n…（材料过长已截断，共 {} 字符）".format(len(text))
        out.append("【材料 {}｜{}】\n{}".format(i, name, clipped))
    return "\n\n".join(out)


def stripped_json(text):
    """把模型返回里的 ```json 围栏去掉再解析；失败返回 None。"""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    # ⚠️ 先按括号配平取**最外层**完整值 —— 别用 find/rfind，
    # 也别逐个 { 试（那会解出内层对象，把报错引向错误的方向）。
    return _outermost_json(t)


def emit(obj, out, text_mode=False):
    """统一输出：给 --out 就写文件，否则打印。"""
    payload = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(payload if payload.endswith("\n") else payload + "\n",
                             encoding="utf-8")
        sys.stderr.write("已写入 {}\n".format(out))
    if not out or text_mode:
        print(payload)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

DEFAULT_FIELDS = ("研究问题", "方法", "数据与样本", "主要结论", "局限", "可复用点", "待核对项")


def cmd_extract(a):
    items = collect_materials(a)
    fields = [f.strip() for f in (a.fields or ",".join(DEFAULT_FIELDS)).split(",") if f.strip()]
    prompt = (
        "从下面的材料里抽取结构化字段。只输出一个 JSON 对象，键就是下列字段名，"
        "值尽量是一句话或短列表：\n"
        "  {}\n\n"
        "材料里没有的字段，值写「未提供」并在末尾加「(需回原文核对)」。\n\n"
        "{}"
    ).format("、".join(fields), as_block(items))
    text, usage = chat(prompt, system=DISCIPLINE, model=a.model,
                       temperature=0.0, max_tokens=a.max_tokens, key=a.key)
    data = stripped_json(text)
    pts = None
    result = {"fields": fields, "materials": [n for n, _ in items],
              "extracted": data, "raw": None if data else text,
              "usage": usage}
    emit(result, a.out)
    sys.stderr.write("用量：" + usage_line(usage, pts) + "\n")
    if data is None:
        sys.stderr.write("模型没有直接给出可解析的 JSON，原文放在 raw 里，供人工核对{}。\n".format(_fr_hint()))
        return 0
    return 0


def cmd_summarize(a):
    items = collect_materials(a)
    budget = {"short": "150 字以内", "medium": "400 字左右", "long": "800 字左右"}[a.length]
    prompt = (
        "把下面的材料压成一份摘要，{}。要求：\n"
        "1. 先给 3~5 条要点，每条后面用【材料 N】标出出处；\n"
        "2. 再给一段「这份材料没有回答的问题」；\n"
        "3. 不添加材料里没有的数字、结论或引用。\n\n{}"
    ).format(budget, as_block(items))
    text, usage = chat(prompt, system=DISCIPLINE, model=a.model,
                       temperature=0.2, max_tokens=a.max_tokens, key=a.key)
    emit(text, a.out, text_mode=True)
    sys.stderr.write("用量：" + usage_line(usage, None) + "\n")
    return 0


def cmd_matrix(a):
    items = collect_materials(a)
    columns = a.columns or "编号,来源,研究问题,方法,数据与样本,主要结论,局限,可复用点,待核对项"
    prompt = (
        "把下列材料横向摊开成一张 Markdown 对比表，表头固定为：\n"
        "  {}\n\n"
        "规则：\n"
        "1. 每份材料一行，「来源」用材料的标题或文件名；\n"
        "2. 单元格只填材料里写明的信息，没写的填「未提供」；\n"
        "3. 表后另起一节「### 可能的空白点」，逐条写明它是「确认没人做」还是"
        "「本次材料里没搜到」，并注明判据来自哪几份材料；\n"
        "4. 材料之间结论冲突时，另起一节「### 冲突与分歧」原样列出，不要替它们裁决。\n\n{}"
    ).format(columns, as_block(items))
    text, usage = chat(prompt, system=DISCIPLINE, model=a.model,
                       temperature=0.2, max_tokens=a.max_tokens, key=a.key)
    emit(text, a.out, text_mode=True)
    sys.stderr.write("用量：" + usage_line(usage, None) + "\n")
    return 0


def cmd_review(a):
    items = collect_materials(a)
    venue = a.venue or "目标期刊 / 会议"
    prompt = (
        "你现在是{}的审稿人，请用**挑刺**的方式过一遍下面的稿子。按这个顺序输出：\n"
        "1. 一句话复述作者的主张（如果我复述错了，说明主张没写清）；\n"
        "2. 可能直接导致拒稿的问题，按严重度排序，每条注明稿子里的位置；\n"
        "3. 主张与证据不匹配的地方（哪些结论超出了数据支持的范围）；\n"
        "4. 缺失的对照、消融、统计或重复；\n"
        "5. 引用与事实层面的疑点清单——**只列疑点，不要替我补引用**；\n"
        "6. 如果要救这篇稿子，最小改动是什么。\n\n"
        "凡是你无法从稿子本身判断的，写「需作者补充」。不要客气，也不要编造审稿意见里的事实。\n\n{}"
    ).format(venue, as_block(items))
    text, usage = chat(prompt, system=DISCIPLINE, model=a.model,
                       temperature=0.4, max_tokens=a.max_tokens, key=a.key)
    emit(text, a.out, text_mode=True)
    sys.stderr.write("用量：" + usage_line(usage, None) + "\n")
    return 0


def cmd_doc_qa(a):
    urls = list(a.url or [])
    if not urls:
        raise ChatError("至少给一个 --url（公网 HTTP(S) 文档地址，1~8 个）。")
    if len(urls) > 8:
        raise ChatError("file_qa/chat 一次最多 8 个文档地址，当前 {} 个。".format(len(urls)))
    question = a.question or a.question_positional
    if not question:
        raise ChatError('请给问题，例如：run.py doc-qa --url U "核心主张是什么？"')
    res = doc_qa(urls, question, key=a.key, mode=a.mode, stream=a.stream,
                 metadata={"source": "sanjianke-ai-research-kit"} if a.metadata else None,
                 timeout=a.timeout)
    answer = res.get("answer") or ""
    if a.stream:
        if not answer:
            sys.stderr.write("流式返回里没抓到正文，检查 url 是否是公网可访问的文档地址。\n")
        return 0
    emit(answer if answer else res.get("raw"), a.out, text_mode=True)
    sys.stderr.write("用量：" + usage_line(res.get("usage"), res.get("points_cost")) + "\n")
    if not answer:
        sys.stderr.write("平台没返回 answer，上面是原始返回。"
                         "确认 url 是公网可访问的文档地址（本地文件不支持）。\n")
    return 0


def cmd_models(a):
    key = a7w.load_key(a.key)
    payload = a7w._request("GET", MODELS_URL, key)
    lst = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    if isinstance(lst, dict):
        lst = lst.get("list") or lst.get("models") or []
    if a.filter:
        kw = a.filter.lower()
        lst = [m for m in lst
               if kw in str(m.get("model_code", "")).lower()
               or kw in str(m.get("model_name", "")).lower()]
    if a.category:
        lst = [m for m in lst if str(m.get("type_code", "")) == a.category]
    if a.json:
        print(json.dumps(lst, ensure_ascii=False, indent=1))
        return 0
    print("在架模型 %d 个（GET /api/v1/models）：" % len(lst))
    for m in lst:
        if isinstance(m, dict):
            print("  %-34s %-26s %-10s %s"
                  % (m.get("model_code"), m.get("model_name") or "",
                     m.get("type_name") or "", m.get("call_type_desc") or ""))
    print("\n模型名别猜——上架很快，用这个命令现查（`--filter` 过滤、`--json` 原始输出）。")
    return 0


def cmd_chat(a):
    text, usage = chat(a.prompt, system=a.system, model=a.model,
                       temperature=a.temperature, max_tokens=a.max_tokens,
                       key=a.key, json_mode=a.json_mode, stream=a.stream)
    if not a.stream:
        if a.json:
            print(json.dumps({"content": text, "usage": usage}, ensure_ascii=False, indent=1))
        else:
            print(text)
    sys.stderr.write("用量：" + usage_line(usage, None) + "\n")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="AI 科研全流程的算力接入层：抽取 / 摘要 / 对比 / 审稿预演 / 文档问答"
                    "（全部走 api.a7w.cn，零第三方依赖）",
        epilog="端点：POST /api/v1/chat/completions · POST /api/v1/apps/file_qa/chat · "
               "GET /api/v1/models",
        allow_abbrev=False)
    ap.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_material_args(p):
        p.add_argument("--file", action="append", help="材料文件路径（可重复）")
        p.add_argument("--dir", help="目录：递归读入 .md/.txt/.csv/.json")
        p.add_argument("--text", help="直接给材料正文")
        p.add_argument("--out", help="结果同时写入这个文件（留档用；终端照常打印）")
        p.add_argument("--model", default=DEFAULT_MODEL, help="模型名（用 `models` 现查）")
        p.add_argument("--max-tokens", type=int, default=4096, help="输出上限，也是控成本的主旋钮")

    p = sub.add_parser("extract", help="抽结构化字段（JSON）", allow_abbrev=False)
    add_material_args(p)
    p.add_argument("--fields", help="字段名，逗号分隔。默认：" + ",".join(DEFAULT_FIELDS))
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("summarize", help="生成带出处的摘要", allow_abbrev=False)
    add_material_args(p)
    p.add_argument("--length", default="medium", choices=["short", "medium", "long"])
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("matrix", help="多份材料横向对比 → 综述矩阵", allow_abbrev=False)
    add_material_args(p)
    p.add_argument("--columns", help="自定义表头，逗号分隔")
    p.set_defaults(func=cmd_matrix)

    p = sub.add_parser("review", help="审稿人视角预演（挑刺）", allow_abbrev=False)
    add_material_args(p)
    p.add_argument("--venue", help="目标期刊 / 会议")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("doc-qa", help="公网文档问答 → file_qa/chat", allow_abbrev=False)
    p.add_argument("--url", action="append", help="公网 HTTP(S) 文档地址（1~8 个，可重复）")
    p.add_argument("--question", help="针对文档的问题")
    p.add_argument("question_positional", nargs="?", help="问题（也可以直接写在 --url 后面）")
    p.add_argument("--mode", choices=["sync", "async", "task"],
                   help="async 返回 task_id 后轮询；长文档建议 async")
    p.add_argument("--stream", action="store_true", help="同步模式下的 SSE 流式响应")
    p.add_argument("--metadata", action="store_true", help="带上业务关联字段")
    p.add_argument("--timeout", type=int, default=600, help="轮询超时（秒）")
    p.add_argument("--out", help="答案写入的文件")
    p.set_defaults(func=cmd_doc_qa)

    p = sub.add_parser("models", help="列出平台在架的文本模型", allow_abbrev=False)
    p.add_argument("--filter", help="按关键词过滤")
    p.add_argument("--category", help="按类型过滤，如 text / image / video")
    p.add_argument("--json", action="store_true", help="输出原始 JSON")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("chat", help="裸调一次大模型", allow_abbrev=False)
    p.add_argument("--prompt", required=True)
    p.add_argument("--system", help="system 提示词")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--json", action="store_true", help="把正文与 usage 一起输出为 JSON")
    p.add_argument("--json-mode", action="store_true", help="要求模型返回 JSON 对象")
    p.add_argument("--stream", action="store_true", help="SSE 流式，边收边打")
    p.set_defaults(func=cmd_chat)

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (a7w.A7wError, OSError) as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        return 130


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
