#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短剧二创授权与合规自查 · 算力版（违禁话术 / 广告法文案**批量初筛**）。

发布前要过的第 3 关是「文案合规扫描」。以前只有离线正则：**按子串匹配、不理解语义**，
「最近」里的「最」会误报，而「全 集」「加V」「vx」这种规避写法又会漏报。
本脚本把这一关升级成两步：

    第一步（本地，免费、离线）  scripts/duanju_compliance.py 的词表 + 正则规则先粗筛
    第二步（大模型，按 token 计费）POST /api/v1/chat/completions 逐条判语义

给一批文案，模型逐条给出：风险等级（high / medium / low / pass）、命中类别、
判定理由、**一版可直接使用的改写文案**。最终等级取「本地命中」与「模型判定」里更高的那个——
正则是底线，模型补语义，两者都不放过。

只用 Python 标准库（同目录 `a7w.py` 也是零依赖）。真实端点见 `CHAT_ENDPOINT` 常量。

用法
    # 批一批：一个文件一行一条
    python3 scripts/run.py screen --file 文案.txt
    python3 scripts/run.py screen --file 文案.txt --format csv --out 初筛结果.csv
    python3 scripts/run.py screen --text "全集免费，未删减完整版" --text "全网独播"
    python3 scripts/run.py screen --file 标题.csv --column title --category title
    python3 scripts/run.py screen --file 文案.txt --strict          # 有 high 就退出码 1，可接 CI

    # 不花钱也能用：只用本地正则，完全不联网
    python3 scripts/run.py screen --file 文案.txt --offline
    # 先看提示词怎么写的（不调用、不花钱）
    python3 scripts/run.py screen --file 文案.txt --show-prompt

Key 三种给法：--key sk-xxxx ／ 环境变量 A7W_API_KEY ／ https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json
计费：1 元 = 100 点，大模型按 token 计费（响应 usage 里有 token 数），失败全额退回。

等级口径（与本包离线脚本一致）
    high    必须改，不允许发布：全集承诺、无授权独家宣称、擦边暴力、站外导流与盗版、收益诱导、广告法绝对化用语
    medium  建议改或补真实依据
    low     需人工确认语境（例如「最」出现在「最近」里）
    pass    未发现问题
"""

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a7w                      # noqa: E402
import duanju_compliance as dc  # noqa: E402

SLUG = "duanju-rights-compliance"

# ---- 真实调用的端点（发布校验看的就是这个字面量）--------------------------
CHAT_ENDPOINT = a7w.HOST + "/api/v1/chat/completions"

DEFAULT_MODEL = "DeepSeek-V4-Flash"   # 可换 DeepSeek-V3.2 / qwen3.6-plus / GLM-5.2 …
RETRIES = 5                           # 5xx / 网络抖动的重试次数
LEVELS = ("pass", "low", "medium", "high")
ORDER = {"pass": 0, "low": 1, "medium": 2, "high": 3}
LABEL = {"pass": "通过", "low": "低", "medium": "中", "high": "高"}

SYSTEM_PROMPT = """你是「三剪客」短剧二创团队的合规初审员，按短视频平台规则与《中华人民共和国广告法》，对短剧推广文案逐条做风险初筛。

只输出**一个 JSON 数组**：不要 markdown 代码块、不要任何解释性文字、不要在数组外写东西。
数组每个元素对应一条输入文案，字段固定：
{"index": 输入里给的编号（整数）, "level": "high|medium|low|pass", "categories": ["命中类别，最多 3 个"], "reason": "判定理由，≤ 40 字，必须引用文案里的具体词句", "rewrite": "一版可直接使用的改写文案；level 为 pass 时给空字符串"}

level 判定口径（四选一，不要发明别的值）：
- high：违反平台禁止项或广告法禁止项，**必须改才能发布**。包括但不限于：
  ① 承诺完整度 / 全集：全集免费、免费看全集、完整版、未删减、无删减、完整全集、全剧、一口气看完；
  ② 无授权的独家 / 首发宣称：全网独播、独家资源、全网首发、首播；
  ③ 擦边色情与暴力血腥：大尺度、激情、暧昧、露骨、限制级、血腥、虐杀；
  ④ 站外导流与盗版暗示：网盘、资源分享、搬运、加微信、公众号、加V、私信我；
  ⑤ 收益承诺与诱导：看剧赚钱、边看边赚、日入过万、不点后悔、点进去就送；
  ⑥ 广告法绝对化用语与虚假限时：最好看、第一、史上最、绝对、100%、仅此一天（无依据）。
- medium：有风险，需补真实依据或改写。例如无法核实的对比、模糊的效果承诺、可能被误读为导流的表述。
- low：需要人工确认语境。例如「最」出现在「最近」这类普通词里、单独一个「第一集」。
- pass：确实没有发现问题。

必须识别的规避写法（正则做不到，这是你的主要价值）：谐音字、拆字、拼音首字母、全角/半角混排、
中间插空格或符号、用 emoji 代替关键词，例如「全 集」「v x」「加 V」「weixin」「最 好 看」
——这类一律按原风险等级判定，并在 reason 里点明是规避写法。

不要编造文案里没有的问题；不要因为文案短或没有标点就判 high。
"""


# ---------------------------------------------------------------- 大模型调用
def llm_chat(messages, model, key, temperature=None, timeout=240):
    """POST /api/v1/chat/completions（OpenAI 兼容协议）。

    实测：返回体就是标准 OpenAI 结构（`choices[0].message.content`）；
    上游偶发 `502 {"code":"upstream_error","message":"upstream timeout"}`——瞬时故障，
    必须重试，否则一次抖动就让整批文案白扫。
    """
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}

    payload, last = None, None
    for attempt in range(RETRIES):
        req = urllib.request.Request(CHAT_ENDPOINT, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            break
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (429, 502, 503, 504) and attempt < RETRIES - 1:
                last = exc
                sys.stderr.write("大模型瞬时故障（HTTP {}），{}s 后重试 {}/{}…\n".format(
                    exc.code, 2 * (attempt + 1), attempt + 1, RETRIES - 1))
                time.sleep(2 * (attempt + 1))
                continue
            try:
                obj = json.loads(text)
                msg = obj.get("msg") or obj.get("error") or obj.get("message") or text[:300]
            except ValueError:
                msg = text[:300]
            if exc.code == 401:
                raise a7w.A7wError("大模型鉴权失败（401）：Key 无效或已过期。{}".format(msg))
            if exc.code == 402:
                raise a7w.A7wError("点数不足（402）：{}  请到 https://api.a7w.cn/ 充值。".format(msg))
            raise a7w.A7wError("大模型请求失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < RETRIES - 1:
                sys.stderr.write("大模型网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 2 * (attempt + 1), attempt + 1, RETRIES - 1))
                time.sleep(2 * (attempt + 1))
                continue
            raise a7w.A7wError("大模型网络错误：{}（确认能访问 {}）".format(
                getattr(exc, "reason", exc), CHAT_ENDPOINT))
    if payload is None:
        raise a7w.A7wError("大模型请求失败（已重试 {} 次）：{}".format(RETRIES, last))

    if isinstance(payload, dict) and "choices" not in payload:
        if payload.get("code") not in (None, 1, 200, "1", "200"):
            raise a7w.A7wError("接口返回失败：{}".format(payload.get("msg") or payload))
        inner = payload.get("data")
        if isinstance(inner, dict):
            payload = inner
    choices = (payload or {}).get("choices") if isinstance(payload, dict) else None
    if not choices:
        raise a7w.A7wError("大模型返回结构不认识：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        if message.get("reasoning") or message.get("reasoning_content"):
            raise a7w.A7wError("模型只返回了思维链、没有正文（finish_reason={}）。"
                               "调大 --batch-size 分批重试或换模型。".format(choice.get("finish_reason")))
    return content, (payload.get("usage") or {})


def parse_json_array(text):
    """从模型输出里抠出一个 JSON 数组。

    实测踩坑：模型偶尔在合法 JSON 后面多吐字符，所以不能只靠 `json.loads`，
    也不能用「第一个 `[` 到最后一个 `]`」硬截（会把垃圾一起切进来）。
    这里用 `JSONDecoder.raw_decode` 从每个 `[` 起试解析，只吃第一个完整数组；
    模型如果把数组包在 `{"items":[...]}` 里也能抠出来。
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return obj
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    start = raw.find("[")
    while start >= 0:
        try:
            obj, _ = decoder.raw_decode(raw[start:])
            if isinstance(obj, list):
                return obj
        except ValueError:
            pass
        start = raw.find("[", start + 1)
    return None


def build_prompt(batch, start_index):
    lines = ["逐条判定下面 {} 条短剧推广文案，index 从 {} 开始，"
             "返回的 JSON 数组长度必须等于 {}。".format(len(batch), start_index, len(batch))]
    for offset, item in enumerate(batch):
        idx = start_index + offset
        lines.append("")
        lines.append("{}. 文案：{}".format(idx, item["text"]))
        if item["local"]["terms"]:
            hits = "、".join("{}（{}）".format(t, lv) for t, lv in item["local"]["terms"][:6])
            lines.append("   本地正则已命中：{}".format(hits))
        else:
            lines.append("   本地正则未命中（请重点看语义、谐音与规避写法）")
    return "\n".join(lines)


def normalize_judgment(raw, index):
    """把模型给的一条判定收敛成固定结构；给不出等级时按 low（需人工确认）处理。"""
    if not isinstance(raw, dict):
        return None
    level = str(raw.get("level") or "").strip().lower()
    ok_level = level in ORDER
    if not ok_level:
        level = "low"
    cats = raw.get("categories")
    if isinstance(cats, str):
        cats = [cats]
    cats = [str(c).strip() for c in (cats or []) if str(c).strip()][:3]
    rewrite = str(raw.get("rewrite") or "").strip()
    return {"index": index, "level": level, "level_ok": ok_level,
            "categories": cats,
            "reason": str(raw.get("reason") or "").strip()[:200],
            "rewrite": "" if level == "pass" else rewrite}


# ---------------------------------------------------------------- 输入
def read_items(a):
    """支持 txt（一行一条）/ csv（--column 指定列）/ json（字符串数组或对象数组）/ --text / stdin。"""
    items = []
    if a.text:
        items += [t for t in a.text]
    sources = []
    if a.file:
        path = Path(a.file)
        if not path.is_file():
            raise SystemExit("找不到文件：{}".format(a.file))
        sources.append(str(path.resolve()))
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with io.open(path, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.reader(fh))
            if not rows:
                raise SystemExit("CSV 是空的：{}".format(a.file))
            header, body = rows[0], rows[1:]
            col = 0
            if a.column:
                if a.column in header:
                    col = header.index(a.column)
                elif a.column.isdigit():
                    col = int(a.column) - 1
                else:
                    raise SystemExit("CSV 里找不到列「{}」，表头是：{}".format(
                        a.column, "、".join(header)))
            for row in body:
                if col < len(row) and row[col].strip():
                    items.append(row[col].strip())
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                data = data.get("items") or data.get("texts") or []
            for row in (data or []):
                if isinstance(row, str) and row.strip():
                    items.append(row.strip())
                elif isinstance(row, dict) and str(row.get("text") or "").strip():
                    items.append(str(row["text"]).strip())
        else:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    items.append(line)
    elif not a.text:
        for line in sys.stdin.read().splitlines():
            line = line.strip()
            if line:
                items.append(line)
    if not items:
        raise SystemExit("没有读到任何文案：用 --file / --text，或从 stdin 一行一条传入")
    if a.max_chars:
        items = [t[:a.max_chars] for t in items]
    return items, sources


def local_scan(text, categories, extra_terms, extra_regexes):
    """第一步：本包离线正则粗筛（免费、离线、快）。"""
    findings = dc.scan(text, categories=categories, extra_terms=extra_terms,
                       extra_regexes=extra_regexes)
    counts = dc.summarize(findings)
    level = "pass"
    for lv in ("high", "medium", "low"):
        if counts[lv]:
            level = lv
            break
    return {"level": level,
            "terms": [(f["term"], f["level"]) for f in findings],
            "advice": [f["advice"] for f in findings if f["level"] == "high"][:3],
            "categories": sorted({f["category"] for f in findings})}


def merge(local, llm):
    final = local["level"]
    sources = ["本地正则"] if local["level"] != "pass" else []
    if llm:
        if ORDER[llm["level"]] > ORDER[final]:
            final = llm["level"]
        if llm["level"] != "pass":
            sources.append("大模型")
    return final, sources


# ---------------------------------------------------------------- 渲染
def scan_line(item):
    lv = item["final_level"]
    bits = ["[{}] {}".format(item["index"], LABEL[lv]),
            "本地 {}｜大模型 {}".format(
                LABEL[item["local"]["level"]],
                LABEL[item["llm"]["level"]] if item["llm"] else "未判定")]
    return "  ".join(bits)


def render_text(items, summary, errors, source, model, offline):
    out = ["=" * 66,
           "短剧文案批量初筛报告",
           "来源：{}｜条数：{}｜判定方式：{}".format(
               source, len(items),
               "只跑本地正则（--offline，未联网）" if offline else
               "本地正则 + 大模型语义（{}）".format(model)),
           "统计：high {} / medium {} / low {} / pass {}".format(
               summary["high"], summary["medium"], summary["low"], summary["pass"]),
           "=" * 66]
    for it in items:
        if it["final_level"] == "pass":
            continue
        out.append("")
        out.append("[{}] {}｜{}".format(it["index"], LABEL[it["final_level"]],
                                        " + ".join(it["sources"]) or "本地正则"))
        out.append("    文案：{}".format(it["text"][:120]))
        if it["llm"]:
            if it["llm"]["categories"]:
                out.append("    命中类别：{}".format("、".join(it["llm"]["categories"])))
            if it["llm"]["reason"]:
                out.append("    理由：{}".format(it["llm"]["reason"]))
            if it["llm"]["rewrite"]:
                out.append("    改写：{}".format(it["llm"]["rewrite"]))
        if it["local"]["terms"]:
            out.append("    本地命中词：{}".format(
                "、".join("{}（{}）".format(t, LABEL[lv]) for t, lv in it["local"]["terms"][:8])))
        if it["local"]["advice"]:
            out.append("    处置建议：{}".format("；".join(it["local"]["advice"])))
    clean = [it["index"] for it in items if it["final_level"] == "pass"]
    if clean:
        out.append("")
        out.append("未发现问题：第 {} 条".format("、".join(str(i) for i in clean)))
    if errors:
        out.append("")
        for err in errors:
            out.append("！第 {}–{} 条大模型判定失败（已保留本地结果）：{}".format(
                err["from"], err["to"], err["error"]))
    out += ["", "=" * 66,
            "结论：{}   {}".format(summary["verdict"], summary["verdict_desc"]),
            "口径：{}".format(dc.DISCLAIMER),
            "规则与等级说明：python3 scripts/duanju_compliance.py --explain",
            "=" * 66]
    return "\n".join(out)


CSV_COLUMNS = ["index", "level", "source", "local_level", "llm_level",
               "llm_categories", "llm_reason", "llm_rewrite", "local_terms", "text"]


def render_csv(items):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for it in items:
        llm = it["llm"] or {}
        writer.writerow([
            it["index"], it["final_level"], " + ".join(it["sources"]),
            it["local"]["level"], llm.get("level") or "",
            "、".join(llm.get("categories") or []),
            llm.get("reason") or "", llm.get("rewrite") or "",
            "、".join("{}（{}）".format(t, LABEL[lv]) for t, lv in it["local"]["terms"]),
            it["text"]])
    return buf.getvalue()


def render_json(items, summary, errors, meta):
    return json.dumps({"ok": meta["ok"], "slug": SLUG, "kind": "screen",
                       "source": meta["source"], "offline": meta["offline"],
                       "model": None if meta["offline"] else meta["model"],
                       "count": len(items), "summary": summary,
                       "llm_errors": errors, "llm_usage": meta["usage"],
                       "results": items}, ensure_ascii=False)


def summarize(items, errors):
    counts = {"high": 0, "medium": 0, "low": 0, "pass": 0}
    for it in items:
        counts[it["final_level"]] += 1
    if counts["high"]:
        code, desc = "blocked", "存在高风险文案，必须改后才能发布"
    elif counts["medium"]:
        code, desc = "review", "存在中风险文案，需补真实依据或改写"
    elif counts["low"]:
        code, desc = "check", "存在待确认项，请逐条确认语境"
    else:
        code, desc = "pass", "未发现问题"
    counts["verdict"] = code
    counts["verdict_desc"] = desc
    counts["llm_failed_items"] = sum(e["count"] for e in errors)
    return counts


def cmd_screen(a):
    items_raw, sources = read_items(a)
    source = "、".join(sources) if sources else "命令行/stdin"

    extra_terms, extra_regexes = ([], [])
    if a.rules:
        extra_terms, extra_regexes = dc.load_custom_rules(Path(a.rules))

    items = []
    for i, text in enumerate(items_raw, 1):
        local = local_scan(text, a.category, extra_terms, extra_regexes)
        items.append({"index": i, "text": text, "local": local, "llm": None,
                      "final_level": local["level"],
                      "sources": ["本地正则"] if local["level"] != "pass" else []})

    usage = []
    errors = []
    if a.offline:
        sys.stderr.write("--offline：只跑本地正则，不联网、不需要 Key。\n")
    else:
        key = None if a.show_prompt else resolve_key(a.key)
        batches = [items[i:i + a.batch_size] for i in range(0, len(items), a.batch_size)]
        for bi, batch in enumerate(batches, 1):
            messages = [{"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",
                         "content": build_prompt(batch, batch[0]["index"])}]
            if a.show_prompt:
                print("===== 第 {}/{} 批 · POST {} · model={} =====".format(
                    bi, len(batches), CHAT_ENDPOINT, a.model))
                print(messages[0]["content"])
                print("----- user -----")
                print(messages[1]["content"])
                continue
            sys.stderr.write("第 {}/{} 批（第 {}–{} 条）：POST {} model={}…\n".format(
                bi, len(batches), batch[0]["index"], batch[-1]["index"],
                CHAT_ENDPOINT, a.model))
            try:
                content, u = llm_chat(messages, a.model, key, temperature=a.temperature)
            except a7w.A7wError as exc:
                errors.append({"from": batch[0]["index"], "to": batch[-1]["index"],
                               "count": len(batch), "error": str(exc)})
                sys.stderr.write("！这一批判定失败：{}\n".format(exc))
                continue
            usage.append(u)
            parsed = parse_json_array(content)
            if parsed is None:
                errors.append({"from": batch[0]["index"], "to": batch[-1]["index"],
                               "count": len(batch),
                               "error": "模型没有返回可解析的 JSON 数组"})
                sys.stderr.write("！第 {}–{} 条：模型输出不是 JSON 数组，已保留本地结果\n".format(
                    batch[0]["index"], batch[-1]["index"]))
                continue
            by_index = {}
            for row in parsed:
                if isinstance(row, dict) and str(row.get("index", "")).strip().isdigit():
                    by_index[int(str(row["index"]).strip())] = row
            for offset, it in enumerate(batch):
                row = by_index.get(it["index"])
                if row is None and offset < len(parsed) and isinstance(parsed[offset], dict):
                    row = parsed[offset]          # 模型没回 index 就按顺序对齐
                judge = normalize_judgment(row, it["index"])
                if judge is None:
                    continue
                if not judge["level_ok"]:
                    sys.stderr.write("！第 {} 条：模型给的等级不是 high/medium/low/pass，"
                                     "已按 low（需人工确认）处理\n".format(it["index"]))
                it["llm"] = judge
                it["final_level"], it["sources"] = merge(it["local"], judge)
    if a.show_prompt:
        return 0

    summary = summarize(items, errors)
    offline = bool(a.offline)
    if not offline and errors and all(it["llm"] is None for it in items):
        sys.stderr.write("失败：大模型一条都没判成（上游故障时换模型或稍后再试）\n")

    meta = {"ok": not errors, "source": source, "offline": offline,
            "model": a.model, "usage": usage}
    if a.format == "json":
        text_out = render_json(items, summary, errors, meta)
    elif a.format == "csv":
        text_out = render_csv(items)
    else:
        text_out = render_text(items, summary, errors, source, a.model, offline)
    print(text_out)

    if a.out:
        out_path = Path(a.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # CSV 落盘用 utf-8-sig：Excel 双击打开不乱码
        if out_path.suffix.lower() == ".csv" or a.format == "csv":
            out_path.write_text(render_csv(items), encoding="utf-8-sig")
        elif out_path.suffix.lower() == ".json":
            out_path.write_text(render_json(items, summary, errors, meta), encoding="utf-8")
        else:
            out_path.write_text(render_text(items, summary, errors, source, a.model, offline),
                                encoding="utf-8")
        sys.stderr.write("结果已写入 {}\n".format(out_path))

    if not offline and errors and all(it["llm"] is None for it in items):
        return 4
    if a.strict and summary["high"]:
        sys.stderr.write("--strict：存在 {} 条高风险文案，退出码 1\n".format(summary["high"]))
        return 1
    return 0


def resolve_key(explicit):
    try:
        return a7w.load_key(explicit)
    except a7w.A7wError as exc:
        sys.stderr.write("{}\n".format(exc))
        raise SystemExit(3)


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="短剧文案批量初筛：本地正则粗筛（离线免费）+ 大模型逐条判语义与改写建议"
                    "（POST /api/v1/chat/completions）。",
        epilog="等级：high 必须改 / medium 建议改 / low 人工确认 / pass 未发现问题；"
               "最终等级取本地正则与大模型里更高的那个。计费：1 元 = 100 点，按 token 计。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("screen", help="批量初筛一批文案", allow_abbrev=False)
    p.add_argument("--file", help="文案文件：txt 一行一条 / csv 用 --column 指定列 / json 字符串数组")
    p.add_argument("--text", action="append", help="直接给一条文案，可重复多次")
    p.add_argument("--column", help="CSV 里放文案的列名（或 1 开始的列号）")
    p.add_argument("--category", action="append",
                   choices=sorted(dc.CATEGORY_TERMS), help="追加本地正则类目，可重复")
    p.add_argument("--rules", help="自定义规则 JSON（与 duanju_compliance.py --rules 同格式）")
    p.add_argument("--offline", action="store_true",
                   help="只跑本地正则：不联网、不需要 Key、不花钱")
    p.add_argument("--batch-size", type=int, default=8, help="每次交给模型的条数，默认 8")
    p.add_argument("--max-chars", type=int, default=400, help="单条文案截断长度，默认 400 字")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="大模型名，默认 {}（可换 DeepSeek-V3.2 / qwen3.6-plus / GLM-5.2 等）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.0,
                   help="采样温度，默认 0（合规判定要可复现）")
    p.add_argument("--format", choices=("text", "json", "csv"), default="text",
                   help="stdout 输出格式，默认 text")
    p.add_argument("--out", help="把结果写入文件（扩展名 .csv/.json 时自动匹配对应格式）")
    p.add_argument("--strict", action="store_true", help="有 high 时退出码 1，可接 CI")
    p.add_argument("--show-prompt", action="store_true",
                   help="只打印真正会发出去的提示词与端点，不调用、不花钱")
    p.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")
    p.set_defaults(func=cmd_screen)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    try:
        return args.func(args)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        return 4


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
