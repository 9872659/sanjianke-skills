#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短剧二创作业手册 · 算力版（台词转写 + 悬念解说稿）。

二创流水线里有两步以前必须自建环境，现在直接走 api.a7w.cn：

    台词转写     POST /api/v1/apps/voice_tts/stt     （multipart 上传本地音视频，
                 拿回台词稿 + **字级时间戳**，用来对齐字幕与取材）
    解说稿生成   POST /api/v1/chat/completions       （OpenAI 兼容，换 model 即换模型；
                 按「四条差异化」的第 1 条，一个片子一条稿）

只用 Python 标准库（同目录 `a7w.py` 也是零依赖）。真正发出请求的端点写在
`STT_ENDPOINT` / `CHAT_ENDPOINT` 两个常量里，可逐行核对。

用法
    # 1) 转写：出台词稿 + 字级时间戳字幕
    python3 scripts/run.py transcribe 第3集.mp4 --lang zh --srt
    python3 scripts/run.py transcribe 第3集.mp4 --out 台词稿.txt --srt-out 第3集.srt

    # 2) 解说稿：按目标时长写，一次写多条互不重复的版本
    python3 scripts/run.py narration --file 台词稿.txt --target-min 5
    python3 scripts/run.py narration --file 台词稿.txt --target-min 5 --variants 3

    # 3) 一条龙：转写 → 出字幕 → 写解说稿 → 落盘
    python3 scripts/run.py pipeline 第3集.mp4 --target-min 5 --variants 2 --out-dir ./出片

    # 不花钱先看提示词到底怎么写的
    python3 scripts/run.py narration --file 台词稿.txt --show-prompt

第一次使用要配 Key（三种方式任选一种）：
    --key sk-xxxx ／ 环境变量 A7W_API_KEY ／ https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json

计费口径：1 元 = 100 点；语音转写按次固定价（实测一次 40 点，与要不要时间戳无关）；
大模型按 token 计费，响应里的 `usage` 会给 token 数。失败全额退回。

能力边界
    · 转写不做说话人分离：只给「说了什么、什么时候」，不给「谁说的」。
    · 平台返回的是**字符级**时间戳（一个字一条），本脚本会合并成正常人能读的字幕行。
    · 大模型的解说稿是**草稿**：必须过一遍 `scripts/duanju_compliance.py` 再配音；
      本脚本会自动跑一次本地扫描并把命中项报出来，但它不替代人工判断。
    · 本脚本只做「转写 + 撰稿」，不做剪辑合成与批量调度。
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
import a7w                      # noqa: E402
import duanju_compliance as dc  # noqa: E402

SLUG = "duanju-remix-playbook"

# ---- 真实调用的两个端点（发布校验看的就是这两个字面量）--------------------
STT_APP, STT_API = "voice_tts", "stt"
STT_ENDPOINT = a7w.HOST + "/api/v1/apps/voice_tts/stt"      # 语音转文字（multipart / audio_url）
CHAT_ENDPOINT = a7w.HOST + "/api/v1/chat/completions"       # 大模型（OpenAI 兼容）

DEFAULT_MODEL = "DeepSeek-V4-Flash"   # 可换 DeepSeek-V3.2 / qwen3.6-plus / GLM-5.2 …
CHARS_PER_SEC = 4.5                   # 中文 TTS 语速经验值：约 4.5 字/秒
RETRIES = 5                           # 大模型调用遇到 5xx / 网络抖动的重试次数
MEDIA_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
             ".mp4", ".mov", ".mkv", ".webm", ".flv", ".ts", ".avi"}

PUNCT_HINT = "，。！？、；：,.!?;:…·—－~～「」『』（）()《》〈〉【】“”‘’\"'"


# ---------------------------------------------------------------- 大模型调用
def llm_chat(messages, model, key, temperature=None, timeout=180):
    """POST /api/v1/chat/completions（OpenAI 兼容协议）。

    实测：返回体就是标准 OpenAI 结构（`choices[0].message.content`），
    `code == 1` 的网关信封在 chat 端点上不出现；这里两种都兼容。
    实测踩坑：长提示词偶发 `HTTP 502 {"code":"upstream_error","message":"upstream timeout"}`，
    这是瞬时故障，重试即可——不做重试会让一次抖动直接毁掉整条流水线。
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
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        if reasoning:
            raise a7w.A7wError(
                "模型只返回了思维链、没有正文（finish_reason={}）。"
                "换一个模型或把目标篇幅调小再试。".format(choice.get("finish_reason")))
    return content, (payload.get("usage") or {})


def parse_json_object(text):
    """从模型输出里抠出一个 JSON 对象。

    实测踩坑：模型偶尔会在合法 JSON **后面**多吐一两个字符（例如结尾多一个 `"}`），
    这时 `json.loads` 报 `Extra data`，而按「第一个 `{` 到最后一个 `}`」截取的写法同样会失败。
    正确做法是用 `JSONDecoder.raw_decode` 从每个 `{` 起试解析，只吃第一个完整对象。
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    start = raw.find("{")
    while start >= 0:
        try:
            obj, _ = decoder.raw_decode(raw[start:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        start = raw.find("{", start + 1)
    return None


# ---------------------------------------------------------------- 提示词
BAN_LIST = ("全集免费 / 免费看全集 / 完整版 / 未删减 / 无删减 / 完整全集 / 全剧 / 一口气看完 / "
            "全网独播 / 独家资源 / 独家播出 / 全网首发 / 首播 / 大尺度 / 激情 / 暧昧 / 香艳 / "
            "露骨 / 少儿不宜 / 限制级 / 血腥 / 残肢 / 虐杀 / 网盘 / 资源分享 / 搬运 / "
            "微信公众号 / 微信 / 加V / 私信我 / 看剧赚钱 / 边看边赚 / 日入过万 / 不点后悔 / "
            "点进去就送 / 最好看 / 第一 / 史上最 / 绝对 / 100%")

SYSTEM_PROMPT = """你是「三剪客」短剧二创团队的解说撰稿人，按二创作业规范写悬念型解说稿，供后续 TTS 配音、再与画面剪辑对齐。

硬性要求：
1. 只输出**一个 JSON 对象**：不要 markdown 代码块、不要前后解释、不要注释。
2. 每条稿子必须**独立成篇**：切入角度、悬念落点、段落展开顺序都不能与其它版本重复。
   判断标准是「观众已经看过原片，我这条还提供了什么」——给出新解读、人物动机、伏笔关系才有增量。
3. 前 3 秒钩子：一句话，不超过 20 字，制造悬念但**不编造剧情、不剧透结局**。
4. 禁用话术（平台红线，写进去会被打回，也不要用近义词绕）：""" + BAN_LIST + """
5. 播出引导只写中性表述，例如「点击下方继续观看」。
6. 不要出现具体平台名之外的站外联系方式、链接、手机号。

JSON 结构（字段名固定，不要增删顶层字段）：
{"title": "标题，≤ 20 字", "angle": "本条切入角度，一句话",
 "hook": "前 3 秒钩子，≤ 20 字",
 "paragraphs": [{"text": "这一段的解说词", "emotion": "紧张/温情/悬疑/爽感", "est_sec": 12}],
 "cta": "结尾引导，≤ 20 字"}
"""


def build_user_prompt(transcript, target_min, variant_index, variants, angle):
    target_body = max(15.0, target_min * 60.0 - 5.0)      # 留片头片尾与 CTA 余量
    target_chars = int(round(target_body * CHARS_PER_SEC))
    lines = [
        "目标成片时长：{} 分钟（解说主体目标约 {:.0f} 秒 ≈ {} 字）。".format(
            int(target_min) if float(target_min).is_integer() else target_min,
            target_body, target_chars),
        "本批共 {} 条解说稿，这是第 {} 条。".format(variants, variant_index),
    ]
    if angle:
        lines.append("这条指定切入角度：{}。".format(angle))
    else:
        lines.append("切入角度自定，但必须与本批其它条明显不同。")
    if variants > 1 and variant_index > 1:
        lines.append("前面的版本已经用过「顺叙＋结尾反转」，这一条请换一种结构（例如先抛结果再回填原因）。")
    lines += ["", "台词稿如下（来自语音转写，可能有错别字，按语义理解即可）：", "", transcript.strip()[:12000]]
    return "\n".join(lines)


def normalize_narration(obj):
    """把模型给的 JSON 收敛成固定结构；给不出有效内容时返回 None。"""
    if not isinstance(obj, dict):
        return None
    paras = []
    for item in (obj.get("paragraphs") or []):
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if text:
                paras.append({"text": text,
                              "emotion": str(item.get("emotion") or "").strip(),
                              "est_sec": item.get("est_sec")})
        elif isinstance(item, str) and item.strip():
            paras.append({"text": item.strip(), "emotion": "", "est_sec": None})
    hook = str(obj.get("hook") or "").strip()
    if not hook and not paras:
        return None
    return {"title": str(obj.get("title") or "").strip(),
            "angle": str(obj.get("angle") or "").strip(),
            "hook": hook, "paragraphs": paras,
            "cta": str(obj.get("cta") or "").strip()}


def narration_text(draft):
    parts = [draft.get("hook") or ""] + [p["text"] for p in draft.get("paragraphs") or []]
    if draft.get("cta"):
        parts.append(draft["cta"])
    return "\n".join(p for p in parts if p)


def estimate_seconds(text):
    return round(len(re.sub(r"\s", "", text or "")) / CHARS_PER_SEC, 1)


def compliance_of(text):
    findings = dc.scan(text)
    counts = dc.summarize(findings)
    code, desc = dc.verdict(findings)
    return {"verdict": code, "note": desc, "high": counts["high"],
            "medium": counts["medium"], "low": counts["low"],
            "terms": sorted({f["term"] for f in findings if f["level"] == "high"})}


def render_narration_md(draft, index, target_min, model, comp):
    out = ["# 解说稿 {}（目标 {} 分钟）".format(index, target_min), ""]
    if draft.get("title"):
        out += ["**标题**：{}".format(draft["title"])]
    if draft.get("angle"):
        out += ["**角度**：{}".format(draft["angle"])]
    out += ["**钩子（前 3 秒）**：{}".format(draft.get("hook") or "（模型没给）"), ""]
    out += ["## 分段（供 TTS 分段配音）", ""]
    for n, p in enumerate(draft.get("paragraphs") or [], 1):
        tag = " ｜".join(x for x in [p.get("emotion") or "", 
                                     "约 {} 秒".format(estimate_seconds(p["text"]))] if x)
        out.append("{}. {}".format(n, p["text"]))
        if tag:
            out.append("   > {}".format(tag))
    out += ["", "## 结尾引导", "", draft.get("cta") or "（模型没给）", "",
            "## 自检", "",
            "- 解说总字数：{} 字，估算配音时长约 {} 秒".format(
                len(re.sub(r"\s", "", narration_text(draft))),
                estimate_seconds(narration_text(draft))),
            "- 本地违禁话术扫描：{}（high {} / medium {} / low {}）".format(
                comp["verdict"], comp["high"], comp["medium"], comp["low"]),
            "- 模型：{}".format(model),
            "",
            "> 提示：本稿是草稿。配音前请再过一遍 `scripts/duanju_compliance.py --strict`，",
            "> 并按 `references/differentiation-rules.md` 核对四条差异化是否都生效。"]
    return "\n".join(out)


# ---------------------------------------------------------------- 转写
def fmt_ts(sec):
    ms = int(round(float(sec or 0) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(h, m, s, ms)


def _seg_bounds(seg):
    return (float(a7w.dig(seg, "start") or a7w.dig(seg, "start_time") or 0),
            float(a7w.dig(seg, "end") or a7w.dig(seg, "end_time") or 0),
            (a7w.dig(seg, "text") or "").strip())


def restore_punctuation(segments, full_text):
    """把整段文本里的标点补回字符级 segments。

    实测（`voice_tts/stt` + `ignore_timestamps=false`）：`result.segments` 是**一字一条**
    且**不带标点**，标点只出现在 `result.text` 里；不补的话合并出来的字幕一句标点都没有。
    两边对不齐时原样返回——宁可不补，也不补错位。
    """
    segs = []
    for seg in segments:
        st, en, tx = _seg_bounds(seg)
        if tx:
            segs.append({"start": st, "end": en, "text": tx})
    plain = "".join(ch for ch in (full_text or "") if not ch.isspace())
    if not segs or not plain:
        return segments
    joined = "".join(s["text"] for s in segs)
    if not joined:
        return segments
    out = [dict(s) for s in segs]
    i = 0
    for ch in plain:
        if i < len(joined) and ch == joined[i]:
            i += 1
            continue
        if i == 0 or ch not in PUNCT_HINT:
            return segments
        out[i - 1]["text"] += ch
    if i != len(joined):
        return segments
    return out


def merge_segments(segments, gap=0.7, max_chars=18):
    """字符级时间戳 → 可读字幕行：句末标点断行、停顿断行、超长断行。"""
    END = "。！？!?…"
    SOFT = "，,、；;：:"
    out, cur = [], None
    for seg in segments:
        st, en, tx = _seg_bounds(seg)
        if not tx:
            continue
        if cur is None:
            cur = [st, en, tx]
            continue
        if (cur[2][-1] in END or st - cur[1] > gap or len(cur[2]) + len(tx) > max_chars):
            out.append(cur)
            cur = [st, en, tx]
        else:
            cur[1], cur[2] = en, cur[2] + tx
        if cur[2][-1] in END or (cur[2][-1] in SOFT and len(cur[2]) >= 8):
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [{"start": s, "end": e, "text": t} for s, e, t in out]


def to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        lines += [str(i),
                  "{} --> {}".format(fmt_ts(seg["start"]), fmt_ts(seg["end"])),
                  seg["text"], ""]
    return "\n".join(lines)


def run_transcribe(media, url, lang, key, gap, max_chars):
    """调 POST /api/v1/apps/voice_tts/stt 拿台词稿 + 字级时间戳。"""
    fields = {"ignore_timestamps": False}        # 必须为 false 才有字级时间戳
    if lang:
        fields["language"] = lang
    sys.stderr.write("转写端点：POST {}\n".format(STT_ENDPOINT))
    if url:
        data = a7w.call(STT_APP, STT_API, dict(fields, audio_url=url), key=key)
    else:
        data = a7w.upload(STT_APP, STT_API, fields, file_field="audio",
                          file_path=media, key=key)

    result = a7w.dig(data, "result") or data
    text = (a7w.dig(result, "text") or "").strip()
    segments = a7w.dig(result, "segments") or []
    if not text:
        raise a7w.A7wError("转写没有返回文字，原始返回：{}".format(
            json.dumps(data, ensure_ascii=False)[:400]))
    lang_out = (a7w.dig(result, "language_code") or a7w.dig(result, "language") or lang or "?")
    duration = a7w.dig(result, "duration")
    cost = a7w.dig(data, "usage", "points_cost") or a7w.dig(data, "usage", "actual_points")

    restored = restore_punctuation(segments, text)
    merged = merge_segments(restored, gap=gap, max_chars=max_chars)
    rate = None
    if duration:
        try:
            rate = round(len(re.sub(r"\s", "", text)) / float(duration), 2)
        except (TypeError, ValueError, ZeroDivisionError):
            rate = None
    sys.stderr.write("转写完成：{} 字｜{} 秒｜字符级时间戳 {} 条 → 合并 {} 条字幕行{}\n".format(
        len(text), duration if duration is not None else "?",
        len(segments), len(merged),
        "｜消耗 {} 点".format(cost) if cost else ""))
    return {"text": text, "segments": merged, "raw_segments": len(segments),
            "language": lang_out, "duration": duration, "points_cost": cost,
            "speech_rate": rate}


# ---------------------------------------------------------------- 主流程
def resolve_key(explicit):
    try:
        return a7w.load_key(explicit)
    except a7w.A7wError as exc:
        sys.stderr.write("{}\n".format(exc))
        raise SystemExit(3)


def cmd_transcribe(a):
    key = resolve_key(a.key)
    if not a.url:
        if not a.media:
            raise SystemExit("请给一个本地音视频路径，或用 --url 传公网音频地址")
        if not Path(a.media).is_file():
            raise SystemExit("找不到文件：{}".format(a.media))
        if Path(a.media).suffix.lower() not in MEDIA_EXT:
            sys.stderr.write("提示：{} 不是常见音视频扩展名，仍会尝试上传。\n".format(a.media))
    info = run_transcribe(a.media, a.url, a.lang, key, a.gap, a.max_chars)

    out = {"ok": True, "slug": SLUG, "kind": "transcribe",
           "source": a.url or str(Path(a.media).resolve()),
           "language": info["language"],
           "duration": info["duration"] if info["duration"] is None else float(info["duration"]),
           "chars": len(info["text"]), "speech_rate": info["speech_rate"],
           "char_stamps": info["raw_segments"], "srt_lines": len(info["segments"]),
           "points_cost": info["points_cost"], "text": info["text"]}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(info["text"] + "\n", encoding="utf-8")
        out["transcript_out"] = str(Path(a.out).resolve())
        sys.stderr.write("台词稿已写入 {}\n".format(a.out))
    if a.srt or a.srt_out:
        if a.srt_out:
            srt_path = Path(a.srt_out)
        elif a.out:
            srt_path = Path(a.out).with_suffix(".srt")
        else:
            srt_path = Path(a.media).with_suffix(".srt")
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text(to_srt(info["segments"]), encoding="utf-8")
        out["srt_out"] = str(srt_path.resolve())
        sys.stderr.write("字幕已写入 {}（{} 条）\n".format(srt_path, len(info["segments"])))
    print(json.dumps(out, ensure_ascii=False))
    return 0


def write_narrations(drafts, out_dir, target_min, model, stem):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, draft in enumerate(drafts, 1):
        path = out / "{}.解说稿-{}.md".format(stem, i)
        path.write_text(render_narration_md(draft, i, target_min, model,
                                            compliance_of(narration_text(draft))),
                        encoding="utf-8")
        paths.append(str(path.resolve()))
    return paths


def generate_narrations(transcript, a, key):
    """按「四条差异化」的第 1 条：一个片子 N 条稿，逐条独立生成。

    实测：网关上游偶发 `502 upstream_error / upstream timeout`（不是我们的参数问题）。
    所以这里**单条失败不影响整批**——失败的那条记进 errors，其余照常出稿；
    只有一条都没成，才算整批失败。
    """
    drafts, usages, warnings, errors = [], [], [], []
    for i in range(1, a.variants + 1):
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",
                     "content": build_user_prompt(transcript, a.target_min, i,
                                                  a.variants, a.angle)}]
        if a.show_prompt:
            print("===== 第 {} 条 · POST {} · model={} =====".format(i, CHAT_ENDPOINT, a.model))
            print(messages[0]["content"])
            print("----- user -----")
            print(messages[1]["content"])
            continue
        sys.stderr.write("第 {}/{} 条解说稿：POST {} model={}…\n".format(
            i, a.variants, CHAT_ENDPOINT, a.model))
        try:
            content, usage = llm_chat(messages, a.model, key, temperature=a.temperature)
        except a7w.A7wError as exc:
            errors.append({"index": i, "error": str(exc)})
            sys.stderr.write("！第 {} 条生成失败：{}\n".format(i, exc))
            continue
        usages.append(usage)
        draft = normalize_narration(parse_json_object(content))
        if draft is None:
            warnings.append("第 {} 条：模型没有返回可解析的 JSON，原文已按纯文本保存".format(i))
            drafts.append({"title": "", "angle": "", "hook": "",
                           "paragraphs": [{"text": content, "emotion": "", "est_sec": None}],
                           "cta": "", "parse_failed": True, "index": i})
        else:
            drafts.append(draft)
    if a.show_prompt:
        raise SystemExit(0)
    return drafts, usages, warnings, errors


def report_narrations(drafts, warnings, target_min):
    results, worst = [], 0
    for i, draft in enumerate(drafts, 1):
        text = narration_text(draft)
        comp = compliance_of(text)
        worst = max(worst, comp["high"])
        chars = len(re.sub(r"\s", "", text))
        secs = estimate_seconds(text)
        target_body = max(15.0, target_min * 60.0 - 5.0)
        results.append({"index": i, "title": draft.get("title") or "",
                        "angle": draft.get("angle") or "",
                        "hook": draft.get("hook") or "",
                        "paragraphs": len(draft.get("paragraphs") or []),
                        "cta": draft.get("cta") or "",
                        "chars": chars, "est_sec": secs,
                        "target_body_sec": round(target_body, 1),
                        "length_ok": 0.6 <= secs / target_body <= 1.6,
                        "compliance": comp,
                        "parse_failed": bool(draft.get("parse_failed"))})
        if comp["high"]:
            sys.stderr.write("！第 {} 条命中 {} 个高风险话术：{} —— 必须改后再配音\n".format(
                i, comp["high"], "、".join(comp["terms"])))
        if draft.get("parse_failed"):
            sys.stderr.write("！第 {} 条模型输出不是 JSON，已按纯文本保存\n".format(i))
    for w in warnings:
        sys.stderr.write("！{}\n".format(w))
    return results, worst


def cmd_narration(a):
    key = None if a.show_prompt else resolve_key(a.key)
    if a.text is not None:
        transcript = a.text
    elif a.file:
        transcript = Path(a.file).read_text(encoding="utf-8", errors="replace")
    else:
        transcript = sys.stdin.read()
    if not transcript.strip():
        raise SystemExit("台词稿是空的：用 --file 指定文件、--text 直接给，或从 stdin 传入")
    drafts, usages, warnings, errors = generate_narrations(transcript, a, key)
    if a.show_prompt:
        return 0
    if not drafts:
        sys.stderr.write("失败：{} 条稿子一条都没生成成功（上游故障时换模型或稍后再试）\n".format(a.variants))
        return 4
    results, worst = report_narrations(drafts, warnings, a.target_min)
    payload = {"ok": not errors, "slug": SLUG, "kind": "narration", "model": a.model,
               "target_min": a.target_min, "variants": a.variants,
               "generated": len(results), "errors": errors,
               "llm_usage": usages, "drafts": results}
    if a.out_dir:
        payload["files"] = write_narrations(drafts, a.out_dir, a.target_min, a.model, a.stem)
        sys.stderr.write("解说稿已写入 {}\n".format(a.out_dir))
    print(json.dumps(payload, ensure_ascii=False))
    if a.strict and worst:
        sys.stderr.write("--strict：存在高风险话术命中，退出码 1\n")
        return 1
    return 0


def cmd_pipeline(a):
    key = resolve_key(a.key)
    if not a.media and not a.url:
        raise SystemExit("请给一个本地音视频路径，或用 --url 传公网音频地址")
    if a.media and not Path(a.media).is_file():
        raise SystemExit("找不到文件：{}".format(a.media))
    out_dir = Path(a.out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(a.media).stem if a.media else "remote"

    info = run_transcribe(a.media, a.url, a.lang, key, a.gap, a.max_chars)
    transcript_path = out_dir / "{}.台词稿.txt".format(stem)
    transcript_path.write_text(info["text"] + "\n", encoding="utf-8")
    srt_path = out_dir / "{}.srt".format(stem)
    srt_path.write_text(to_srt(info["segments"]), encoding="utf-8")
    sys.stderr.write("台词稿 → {}\n字幕 → {}\n".format(transcript_path, srt_path))

    a.show_prompt = getattr(a, "show_prompt", False)
    drafts, usages, warnings, errors = generate_narrations(info["text"], a, key)
    if not drafts:
        sys.stderr.write("转写成功，但解说稿一条都没生成成功（上游故障时换模型或稍后再试）\n")
        return 4
    results, worst = report_narrations(drafts, warnings, a.target_min)
    files = write_narrations(drafts, out_dir, a.target_min, a.model, stem)
    total_chars = sum(r["chars"] for r in results)
    payload = {"ok": not errors, "slug": SLUG, "kind": "pipeline",
               "source": a.url or str(Path(a.media).resolve()),
               "transcribe": {"language": info["language"], "duration": info["duration"],
                              "chars": len(info["text"]), "speech_rate": info["speech_rate"],
                              "points_cost": info["points_cost"],
                              "transcript_out": str(transcript_path.resolve()),
                              "srt_out": str(srt_path.resolve())},
               "narration": {"model": a.model, "target_min": a.target_min,
                             "variants": a.variants, "llm_usage": usages,
                             "generated": len(results), "errors": errors,
                             "total_chars": total_chars,
                             "drafts": results, "files": files},
               "next_steps": ["配音：走 voice_tts 的 tts_async 分段合成",
                              "合成：本地剪辑按字幕时间戳对齐",
                              "过闸：scripts/duanju_compliance.py --strict",
                              "查重：scripts/frame_dedup.py --dir <成片目录> --threshold 0.40"]}
    print(json.dumps(payload, ensure_ascii=False))
    if a.strict and worst:
        sys.stderr.write("--strict：存在高风险话术命中，退出码 1\n")
        return 1
    return 0


def build_parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="短剧二创作业手册 · 算力版：台词转写（voice_tts/stt）+ 悬念解说稿"
                    "（chat/completions），全部走 api.a7w.cn，零依赖。",
        epilog="费用：转写按次固定价（实测 40 点/次）；大模型按 token 计费。1 元 = 100 点。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd")

    def add_key(p):
        p.add_argument("--key", help="临时指定 API Key（默认读 A7W_API_KEY 或 ~/.a7w/config.json）")

    def add_llm(p):
        add_key(p)
        p.add_argument("--model", default=DEFAULT_MODEL,
                       help="大模型名，默认 {}（可换 DeepSeek-V3.2 / qwen3.6-plus / GLM-5.2 等）".format(
                           DEFAULT_MODEL))
        p.add_argument("--temperature", type=float, default=0.85,
                       help="采样温度，默认 0.85（多条差异化稿子需要一点随机性）")

    def add_asr(p):
        p.add_argument("--lang", help="转写语言代码，如 zh / en；不传由平台自动检测")
        p.add_argument("--gap", type=float, default=0.7, help="相邻字间隔超过多少秒断行，默认 0.7")
        p.add_argument("--max-chars", type=int, default=18, help="字幕单行最多字数，默认 18")

    p = sub.add_parser("transcribe", help="语音转文字：台词稿 + 字级时间戳字幕", allow_abbrev=False)
    p.add_argument("media", nargs="?", help="本地音视频文件路径")
    p.add_argument("--url", help="公网音频地址（与本地文件二选一，走 audio_url 参数）")
    p.add_argument("-o", "--out", help="台词稿写入路径")
    p.add_argument("--srt", action="store_true", help="生成 .srt 字幕")
    p.add_argument("--srt-out", help="显式指定 .srt 路径")
    add_key(p)
    add_asr(p)
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("narration", help="大模型写悬念解说稿（可一次多条，互不重复）", allow_abbrev=False)
    p.add_argument("--file", help="台词稿文件（不传则读 stdin）")
    p.add_argument("--text", help="直接给台词文本")
    p.add_argument("--target-min", type=float, default=5.0, help="目标成片分钟数，默认 5")
    p.add_argument("--variants", type=int, default=1, help="一次生成几条差异化稿子，默认 1")
    p.add_argument("--angle", help="指定切入角度（如「反转」「动机」「伏笔」）")
    p.add_argument("--out-dir", help="把解说稿写成 markdown 到这里")
    p.add_argument("--stem", default="解说", help="输出文件名前缀，默认「解说」")
    p.add_argument("--show-prompt", action="store_true",
                   help="只打印真正会发出去的提示词与端点，不调用、不花钱")
    p.add_argument("--strict", action="store_true", help="命中高风险话术时退出码 1")
    add_llm(p)
    p.set_defaults(func=cmd_narration)

    p = sub.add_parser("pipeline", help="一条龙：转写 → 字幕 → 多条解说稿 → 落盘", allow_abbrev=False)
    p.add_argument("media", nargs="?", help="本地音视频文件路径")
    p.add_argument("--url", help="公网音频地址")
    p.add_argument("--target-min", type=float, default=5.0, help="目标成片分钟数，默认 5")
    p.add_argument("--variants", type=int, default=1, help="生成几条解说稿，默认 1")
    p.add_argument("--angle", help="指定切入角度")
    p.add_argument("--out-dir", default=".", help="输出目录，默认当前目录")
    p.add_argument("--strict", action="store_true", help="命中高风险话术时退出码 1")
    add_llm(p)
    add_asr(p)
    p.set_defaults(func=cmd_pipeline)
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
