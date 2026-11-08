#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 文本模型台（sanjianke-text-models）

## 一句话

同一句话，92 个文本模型先报价再开口；最便宜的每百万 token 输出 40 点（0.40 元），
最贵的 claude-fable-5 每百万 token 输出 15,840 点（158.40 元）—— 差 396 倍。

## 第一步就把「文本层到底走哪条路」探清楚（2026-11-08，零花费探针）

  POST /api/v1/chat/completions        → 422 missing field `messages`   ← 唯一能用的入口
  POST /v1/chat/completions            → 422 同上（少了 /api 也落到同一条）
  POST /api/chat/completions           → 422 同上
  POST /api/v1/messages                → 404 HTML（站点首页）
  POST /v1/messages                    → 404 {"code":"unknown_endpoint"}
  POST /api/v1/embeddings              → 404 HTML（站点首页）

结论：**文本只有一个入口 `/api/v1/chat/completions`**。目录里 13 个 claude 变体
只声明 `anthropic_messages` 协议，本网关没有对应端点 —— 打 chat 入口回
`{"code":0,"msg":"模型不存在或未上架"}`。

## 单价从哪来（这次不用反推）

`GET /api/v1/models` 的 92 条 text 模型**自带 pricing**：
`pricing.per_1k_input` / `per_1k_output` 是**每百万 token 的点数**
（`usage_unit_size: 1000000`，`price_view.summary` 写「按百万 Token X 点/百万 Token」）。
字段名带 1k、数值却是 1M —— 按 1K 算会错 1000 倍，这是本包第一个坑。

价目表 `GET /api/v1/pricing` 的 115 条规则里**没有** `/api/v1/chat/completions`，
它命中通配 `*`：对外 = 上游点数 x 2、单笔保底 50 点、markupPercent 100。
实测每次调用**先冻 60 点**（`reserve_sync:/api/v1/chat/completions`），
失败自动全额退回（`refund:sync`）—— 所以短对话的真实下限是 60 点，不是 token 算出来的那几分。

`pricing_v2.items[0].reference_price` 还给官方参考价与省钱比例：
claude-sonnet-4-5 官方 $3 / $15 每百万，本站 674 / 3,386 点（6.74 / 33.86 元），省 66.8%。

## 目录里有价、不等于这条路通（实测 21 个）

  ok    kimi-k3 · Qwen3.5-Flash · Qwen3.8-Omni-Flash · GLM-5.2 · Kimi-K2.6 ·
        MiniMax-M3 · LegalOne-8B · AutoGLM-Phone-9B-Multilingual · KAT-Dev ·
        Sinong1.0-32B · deepseek-chat（历史别名，不在目录里）
  gone  claude-sonnet-4-5（200 code 0）· Qwen3.7-Max（404）· ERNIE-5.0-Thinking（401）
  dead  DeepSeek-V3.2（400 已停用）· DeepSeek-V4-Flash（404 HTML）·
        MiMo-V2.5-Pro（404 HTML）· gpt-5.5（403 上游欠费）·
        gemini-3-pro（503）· gemma-4-26B-A4B-it（503 无渠道）

## 子命令

  catalog  92 个文本模型 + 每百万 token 单价 + 实测可调性（免费，可离线）
  check    一个模型通不通，先免费问一句（messages 为空，停在校验层，净 0）
  cost     同一句话多模型报价：token 估算 + 60 点保底（免费）
  doctor   自检 6 个只读端点 + 2 个探针 + 余额前后对比（免费）
  chat     同一句话多模型横评，落盘 + manifest + 对比清单（要 --yes，受 --budget 管）
  log      本地台账（免费）

## 用法

  python3 scripts/run.py catalog --family claude
  python3 scripts/run.py check --models kimi-k3,Qwen3.5-Flash
  python3 scripts/run.py cost --models kimi-k3,GLM-5.2 --prompt "给一条 15 秒护肤口播写脚本"
  python3 scripts/run.py doctor
  python3 scripts/run.py chat --models kimi-k3,GLM-5.2,Qwen3.5-Flash \
      --prompt "给一条 15 秒护肤口播写脚本" --yes
  python3 scripts/run.py log

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# ── GBK 编码兜底（家族统一写法）──────────────────────────────────────────────
# Windows 上 stdout 被管道重定向时 Python 用本地编码（cp936），
# 遇到 cp936 编不出的字符就 UnicodeEncodeError 崩掉。
# 先加 errors="replace" 兜底；本包全文只用 cp936 覆盖得到的
# √ × · → ★ 「」 ① 这类字符，金额一律写成「元」。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

sys.dont_write_bytecode = True

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"
CHAT_PATH = API_PREFIX + "/chat/completions"
MODELS_PATH = API_PREFIX + "/models"
PRICING_PATH = API_PREFIX + "/pricing"
ME_TASKS = API_PREFIX + "/me/tasks"
TASKS_PATH = API_PREFIX + "/tasks"

POINTS_PER_YUAN = 100
MIN_POINTS = 60            # 实测每次调用先冻 60 点（reserve_sync:/api/v1/chat/completions）
PRICING_MIN = 50           # 价目表通配 *：minPoints 50 / markupPercent 100
DEFAULT_BUDGET = 600       # 单位：点 = 6 元；够默认 5 个模型各跑一次（60 点保底）
DEFAULT_OUT = 900          # 默认输出 token 上限
DEFAULT_MODELS = ["kimi-k3", "GLM-5.2", "Qwen3.5-Flash", "MiniMax-M3", "LegalOne-8B"]
PROBE_MODEL = "deepseek-chat"     # 历史别名，实测可调；探针只发 messages:[]
LEDGER = os.path.join(os.path.expanduser("~"), ".a7w", "text-models-ledger.json")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-text-models/%s" % VERSION

# ── 92 个文本模型（GET /api/v1/models 2026-11-08 快照）─────────────────────────
# i / o = 每百万 token 的点数（输入 / 输出），1 元 = 100 点
# chat  = 目录协议里是否有 openai_chat（1 有 / 0 只有 anthropic_messages 或 openai_responses）
# st    = 2026-11-08 实测：ok 能调 · gone 未上架 · dead 上游停用/欠费/无渠道 · ? 未测
TEXT_MODELS = {
    "gpt-5.5": dict(fam="gpt", name="GPT-5.5", i=500, o=3000, ctx=400000, vis=0, rsn=0,
                    p="chat", st="dead", note="403 上游欠费"),
    "DeepSeek-V4-Pro": dict(fam="deepseek", name="DeepSeek-V4-Pro", i=1200, o=2400, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "DeepSeek-V4-Flash": dict(fam="deepseek", name="DeepSeek-V4-Flash", i=100, o=200, ctx=0, vis=0, rsn=0,
                    p="chat", st="dead", note="404 站点首页"),
    "Qwen3.7-Max": dict(fam="qwen", name="Qwen3.7-Max", i=1200, o=3600, ctx=0, vis=0, rsn=0,
                    p="chat", st="gone", note="404 未上架"),
    "Qwen3.7-Plus": dict(fam="qwen", name="Qwen3.7-Plus", i=200, o=105, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "GLM-5.2": dict(fam="glm", name="GLM-5.2", i=800, o=105, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 参数校验"),
    "MiniMax-M2.7": dict(fam="minimax", name="MiniMax-M2.7", i=210, o=105, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3.8-Omni-Flash": dict(fam="qwen", name="Qwen3.8-Omni-Flash", i=90, o=280, ctx=1000000, vis=1, rsn=1,
                    p="chat", st="ok", note="400 参数校验"),
    "gemini-3-pro": dict(fam="gemini", name="Gemini 3 Pro (openai)", i=396, o=2772, ctx=0, vis=1, rsn=1,
                    p="chat", st="dead", note="503 上游不可用"),
    "gemini-2.5-pro": dict(fam="gemini", name="Gemini 2.5 Pro (openai)", i=301, o=2376, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "claude-opus-4-5": dict(fam="claude", name="Claude Opus 4.5", i=1129, o=5663, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-sonnet-4-5": dict(fam="claude", name="Claude Sonnet 4.5", i=674, o=3386, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="gone", note="200 但 code=0 模型不存在或未上架"),
    "gpt-5-2": dict(fam="gpt", name="GPT 5.2", i=347, o=2772, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "gemini-3.1-pro": dict(fam="gemini", name="Gemini 3.1 Pro (openai)", i=396, o=2772, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "claude-haiku-4-5": dict(fam="claude", name="Claude Haiku 4.5", i=218, o=1129, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-opus-4-6-official": dict(fam="claude", name="Claude Opus 4.6", i=1129, o=5663, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-sonnet-4-6-official": dict(fam="claude", name="Claude Sonnet 4.6", i=674, o=3386, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "gpt-5-5": dict(fam="gpt", name="GPT 5.5 (response)", i=1109, o=6653, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "claude-opus-4-7-official": dict(fam="claude", name="Claude Opus 4.7", i=1129, o=5663, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-opus-4-8-official": dict(fam="claude", name="Claude Opus 4.8", i=1584, o=7920, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-fable-5-official": dict(fam="claude", name="Claude Fable 5", i=3168, o=15840, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-sonnet-5-official": dict(fam="claude", name="Claude Sonnet 5", i=674, o=3386, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "grok-4-5": dict(fam="grok", name="Grok 4.5", i=634, o=1901, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "gpt-5-6-terra": dict(fam="gpt", name="GPT 5.6 Terra", i=444, o=2662, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "gpt-5-6-luna": dict(fam="gpt", name="GPT 5.6 Luna", i=45, o=267, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "gpt-5-6-sol": dict(fam="gpt", name="GPT 5.6 Sol", i=1109, o=6653, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "claude-opus-5": dict(fam="claude", name="Claude Opus 5", i=1584, o=7920, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "grok-4-6": dict(fam="grok", name="Grok 4.6", i=634, o=1901, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "gemini-3-7-flash-openai": dict(fam="gemini", name="Gemini 3.7 Flash (openai)", i=179, o=891, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "gemini-3-7-flash": dict(fam="gemini", name="Gemini 3.7 Flash", i=179, o=891, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "gemini-3-8-flash-openai": dict(fam="gemini", name="Gemini 3.8 Flash (openai)", i=179, o=891, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "gemini-3-8-flash": dict(fam="gemini", name="Gemini 3.8 Flash", i=179, o=891, ctx=0, vis=1, rsn=1,
                    p="chat", st="?", note=""),
    "gpt-6-astra": dict(fam="gpt", name="Gpt 6 Astra", i=2218, o=11088, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "grok-4-7": dict(fam="grok", name="Grok 4.7", i=634, o=1901, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "gpt-6-sol": dict(fam="gpt", name="GPT 6 Sol", i=476, o=2376, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "gpt-6-luna": dict(fam="gpt", name="GPT 6 Luna", i=24, o=119, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "deepseek-v4-1-flash": dict(fam="deepseek", name="DeepSeek V4.1 Flash", i=96, o=377, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "kimi-k3-official": dict(fam="kimi", name="Kimi K3", i=1901, o=9504, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "claude-opus-5-5": dict(fam="claude", name="Claude Opus 5.5", i=1268, o=6336, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "gpt-6-1-sol": dict(fam="gpt", name="GPT 6.1 Sol", i=476, o=2376, ctx=0, vis=0, rsn=1,
                    p="responses", st="?", note=""),
    "claude-sonnet-5-5": dict(fam="claude", name="Claude Sonnet 5.5", i=634, o=3168, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "claude-haiku-5-5": dict(fam="claude", name="Claude Haiku 5.5", i=48, o=238, ctx=0, vis=0, rsn=1,
                    p="anthropic", st="?", note=""),
    "gpt-5.6-sol": dict(fam="gpt", name="GPT-5.6 Sol", i=500, o=3000, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "gpt-5.6-luna": dict(fam="gpt", name="GPT-5.6 Luna", i=20, o=120, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "gpt-5.6-terra": dict(fam="gpt", name="GPT-5.6 Terra", i=200, o=1200, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "kimi-k3": dict(fam="kimi", name="kimi-k3", i=2000, o=10000, ctx=0, vis=1, rsn=0,
                    p="chat", st="ok", note="400 参数校验"),
    "Qwen3.6-35B-A3B": dict(fam="qwen", name="Qwen3.6-35B-A3B", i=50, o=330, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3.6-27B": dict(fam="qwen", name="Qwen3.6-27B", i=60, o=480, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3.5-Flash": dict(fam="qwen", name="Qwen3.5-Flash", i=30, o=210, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 参数校验"),
    "Qwen3.6-Flash": dict(fam="qwen", name="Qwen3.6-Flash", i=130, o=730, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Hy-MT2-30B-A3B": dict(fam="tencent", name="Hy-MT2-30B-A3B", i=80, o=130, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "HY-MT2-7B": dict(fam="tencent", name="HY-MT2-7B", i=40, o=40, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "MiniMax-M3": dict(fam="minimax", name="MiniMax-M3", i=430, o=1690, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 invalid params, messages is empty"),
    "MiMo-V2.5-Pro": dict(fam="mimo", name="MiMo-V2.5-Pro", i=710, o=2110, ctx=0, vis=0, rsn=0,
                    p="chat", st="dead", note="404 站点首页"),
    "Kimi-K2.7-Code": dict(fam="kimi", name="Kimi-K2.7-Code", i=550, o=2200, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "LegalOne-8B": dict(fam="legal", name="LegalOne-8B", i=210, o=210, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 list index out of range"),
    "Qwen3-Coder-Next": dict(fam="qwen", name="Qwen3-Coder-Next", i=410, o=410, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "GLM-5": dict(fam="glm", name="GLM-5", i=410, o=1810, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "MiniMax-M2.5": dict(fam="minimax", name="MiniMax-M2.5", i=220, o=850, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3.5-35B-A3B": dict(fam="qwen", name="Qwen3.5-35B-A3B", i=50, o=330, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3.5-27B": dict(fam="qwen", name="Qwen3.5-27B", i=70, o=490, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3.5-122B-A10B": dict(fam="qwen", name="Qwen3.5-122B-A10B", i=150, o=1010, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "GLM-5.1": dict(fam="glm", name="GLM-5.1", i=810, o=2810, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "gemma-4-26B-A4B-it": dict(fam="gemma", name="gemma-4-26B-A4B-it", i=60, o=60, ctx=0, vis=0, rsn=0,
                    p="chat", st="dead", note="503 暂无可用渠道"),
    "Kimi-K2.6": dict(fam="kimi", name="Kimi-K2.6", i=500, o=2000, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 参数校验"),
    "Qwen3.6-Plus": dict(fam="qwen", name="Qwen3.6-Plus", i=810, o=4810, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3-Coder-30B-A3B-Instruct": dict(fam="qwen", name="Qwen3-Coder-30B-A3B-Instruct", i=110, o=410, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "ERNIE-5.0-Thinking": dict(fam="ernie", name="ERNIE-5.0-Thinking", i=410, o=1610, ctx=0, vis=0, rsn=1,
                    p="chat", st="gone", note="401 invalid_model"),
    "DeepSeek-V3.2": dict(fam="deepseek", name="DeepSeek-V3.2", i=210, o=310, ctx=0, vis=0, rsn=0,
                    p="chat", st="dead", note="400 该模型已停用"),
    "AutoGLM-Phone-9B-Multilingual": dict(fam="autoglm", name="AutoGLM-Phone-9B-Multilingual", i=45, o=150, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 list index out of range"),
    "KAT-Dev": dict(fam="kat", name="KAT-Dev", i=110, o=410, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 list index out of range"),
    "GLM-4.7": dict(fam="glm", name="GLM-4.7", i=360, o=1410, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "MiniMax-M2.1": dict(fam="minimax", name="MiniMax-M2.1", i=220, o=850, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "HY-MT1.5-7B": dict(fam="tencent", name="HY-MT1.5-7B", i=40, o=40, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Sinong1.0-32B": dict(fam="sinong", name="Sinong1.0-32B", i=810, o=810, ctx=0, vis=0, rsn=0,
                    p="chat", st="ok", note="400 list index out of range"),
    "MAI-UI-8B": dict(fam="mai", name="MAI-UI-8B", i=150, o=150, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Kimi-K2.5": dict(fam="kimi", name="Kimi-K2.5", i=290, o=1600, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "PaddleOCR-VL-1.5": dict(fam="paddle", name="PaddleOCR-VL-1.5", i=290, o=290, ctx=0, vis=1, rsn=0,
                    p="chat", st="?", note=""),
    "Hunyuan-MT-Chimera-7B": dict(fam="tencent", name="Hunyuan-MT-Chimera-7B", i=40, o=40, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3-Next-80B-A3B-Instruct": dict(fam="qwen", name="Qwen3-Next-80B-A3B-Instruct", i=110, o=410, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3-VL-30B-A3B-Instruct": dict(fam="qwen", name="Qwen3-VL-30B-A3B-Instruct", i=80, o=290, ctx=0, vis=1, rsn=0,
                    p="chat", st="?", note=""),
    "ERNIE-4.5-Turbo-VL": dict(fam="ernie", name="ERNIE-4.5-Turbo-VL", i=310, o=910, ctx=0, vis=1, rsn=0,
                    p="chat", st="?", note=""),
    "ERNIE-4.5-Turbo": dict(fam="ernie", name="ERNIE-4.5-Turbo", i=90, o=330, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "QwQ-32B": dict(fam="other", name="QwQ-32B", i=110, o=410, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Fin-R1": dict(fam="fin", name="Fin-R1", i=210, o=810, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "GLM-4-32B": dict(fam="glm", name="GLM-4-32B", i=199, o=199, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "DianJin-R1-32B": dict(fam="dianjin", name="DianJin-R1-32B", i=210, o=810, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen3-32B": dict(fam="qwen", name="Qwen3-32B", i=110, o=410, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "Qwen2.5-7B-Instruct": dict(fam="qwen", name="Qwen2.5-7B-Instruct", i=45, o=45, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "DeepSeek-R1-Distill-Qwen-32B": dict(fam="deepseek", name="DeepSeek-R1-Distill-Qwen-32B", i=136, o=136, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "gpt-5.4-mini": dict(fam="gpt", name="GPT-5.4 Mini", i=75, o=450, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
    "gpt-5.4": dict(fam="gpt", name="GPT-5.4", i=250, o=1500, ctx=0, vis=0, rsn=0,
                    p="chat", st="?", note=""),
}

FAMILY_CN = {
    "claude": "Claude 13 变体", "qwen": "通义千问", "gpt": "GPT", "gemini": "Gemini",
    "deepseek": "DeepSeek", "glm": "智谱 GLM", "kimi": "Kimi", "minimax": "MiniMax",
    "ernie": "文心 ERNIE", "grok": "Grok", "tencent": "腾讯混元", "gemma": "Gemma",
    "mimo": "小米 MiMo", "legal": "LegalOne", "autoglm": "AutoGLM", "kat": "KAT",
    "sinong": "司农 Sinong", "mai": "MAI", "paddle": "PaddleOCR", "fin": "金融 Fin",
    "dianjin": "点金 DianJin", "other": "其他",
}
FAMILY_ORDER = ["claude", "qwen", "kimi", "glm", "deepseek", "gpt", "gemini", "minimax",
                "ernie", "grok", "tencent", "gemma", "mimo", "legal", "autoglm", "kat",
                "sinong", "mai", "paddle", "fin", "dianjin", "other"]

STATUS_CN = {"ok": "能调", "gone": "未上架", "dead": "上游不可用", "?": "未测"}


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
            with io.open(cfg, encoding="utf-8") as f:
                d = json.load(f)
            if not key:
                k = d.get("key") or d.get("api_key")
                if k:
                    key = str(k).strip()
            if not host and d.get("host"):
                host = str(d["host"]).rstrip("/")
        except Exception:                                    # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120):
    """只读 GET 带 3 次重试（网关偶尔掐连接）；POST 只发一次，绝不重发。

    POST 重发等于第二次预冻，所以这里按方法区分重试次数。
    """
    attempts = 3 if method == "GET" else 1
    last = None
    for i in range(attempts):
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
            last = "连不上 %s：%s" % (url, e.reason)
        except Exception as e:                               # noqa: BLE001
            last = "请求异常：%s: %s" % (type(e).__name__, e)
        if i + 1 < attempts:
            time.sleep(0.6 if i == 0 else 1.4)
    raise Fail("call", last or "请求失败", EXIT_CALL)


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                        # noqa: BLE001
        return None


def err_text(st, txt):
    """把上游返回压成一行人话。HTML 一律说清楚是站点首页。"""
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            bits = [str(e.get("message") or ""), str(e.get("code") or "")]
            s = " · ".join([b for b in bits if b])
            if s:
                return s[:240]
        for k in ("msg", "message"):
            if d.get(k):
                return str(d[k])[:240]
        if d.get("code") is not None:
            return "code=%s" % d.get("code")
    if (txt or "").lstrip().startswith("<"):
        return "HTTP %s 返回站点首页 HTML（这条路没配模型）" % st
    return (txt or "").replace("\n", " ")[:200]


def _w(s):
    """显示宽度：中日韩字符算 2 列。"""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def pnum(v, dash="-"):
    if v is None:
        return dash
    try:
        f = float(v)
    except Exception:                                        # noqa: BLE001
        return dash
    if abs(f - round(f)) < 1e-9:
        return "{:,}".format(int(round(f)))
    return "{:,.2f}".format(f)


def money(points):
    try:
        return "%.2f 元" % (float(points) / POINTS_PER_YUAN)
    except Exception:                                        # noqa: BLE001
        return "-"


def parse_models(raw):
    if not raw:
        return []
    out = []
    for x in re.split(r"[,，\s]+", raw.strip()):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


def resolve(models):
    """把 --models 解析成 [(code, meta)]；不在内置表里也放行（交给上游判断）。"""
    out = []
    for m in models:
        meta = TEXT_MODELS.get(m)
        if meta is None:
            for code, mm in TEXT_MODELS.items():
                if code.lower() == m.lower():
                    meta, m = mm, code
                    break
        out.append((m, meta))
    return out


def est_tokens(text):
    """粗估 token：汉字按 1 个算、拉丁字母按 0.3 个算。

    锚点：一节 1,500 - 3,000 字的讲义，实测 2,480 token（本团队课程包的真实计数），
    所以汉字 1:1 已是偏保守的估计，误差主要落在长英文串上。
    """
    han = sum(1 for c in text if ord(c) > 0x2E7F)
    rest = len(text) - han
    return int(round(han * 1.0 + rest * 0.3)) + 1


def cost_of(meta, in_tok, out_tok):
    """返回 (闸门点数, token 算出的点数, 口径说明)。

    闸门 = max(60, token 价)：60 点是实测预冻值，也是短对话的真实下限。
    """
    if not meta:
        return float(MIN_POINTS), None, "内置价目表里没有这个型号，按 60 点保底"
    tok = (in_tok / 1000000.0) * meta["i"] + (out_tok / 1000000.0) * meta["o"]
    gate = max(float(MIN_POINTS), tok)
    if gate > tok + 1e-9:
        basis = "%s token = %s 点，按 60 点保底" % (pnum(in_tok + out_tok),
                                              pnum(round(tok, 2)))
    else:
        basis = "%s token = %s 点（超过 60 点保底）" % (pnum(in_tok + out_tok),
                                                pnum(round(tok, 2)))
    return round(gate, 2), round(tok, 2), basis


def classify(st, txt, d):
    """把一次探针/调用的返回判定成 ok / gone / dead / route，并给一句原文。"""
    if isinstance(d, dict) and d.get("choices"):
        return "ok", "已出话"
    if isinstance(d, dict) and d.get("code") == 0:
        msg = str(d.get("msg") or "")
        if "不存在" in msg or "未上架" in msg:
            return "gone", "200 但 code=0：" + msg[:60]
        if "不能为空" in msg:
            return "route", "200 但 code=0：" + msg[:60]
        return "gone", "200 但 code=0：" + msg[:60]
    e = d.get("error") if isinstance(d, dict) else None
    code = str((e or {}).get("code") or "") if isinstance(e, dict) else ""
    msg = str((e or {}).get("message") or "") if isinstance(e, dict) else ""
    blob = (msg + " " + code).lower()
    if st == 422 and "missing field" in blob:
        return "route", "422 缺 messages（入口在、模型未校验）"
    if "已停用" in msg:
        return "dead", "该模型已停用：" + msg[:50]
    if "insufficient_balance" in blob or "余额不足" in msg:
        return "dead", "上游欠费：" + msg[:44]
    if st == 401 or "invalid_model" in blob:
        return "gone", "未上架：" + msg[:50]
    if "does not exist" in blob or "不存在" in msg:
        return "gone", "未上架：" + msg[:50]
    if "no available" in blob or "暂无可用渠道" in msg or "service_rejected" in blob:
        return "dead", "上游无渠道：" + msg[:44]
    if st in (404,) and not isinstance(d, dict):
        return "dead", "站点首页 HTML（这条路没配模型）"
    if st in (500, 502, 503, 504):
        return "dead", "上游不可用：" + msg[:44]
    if st in (200, 201) and not isinstance(d, dict):
        return "dead", "返回非 JSON"
    if st and 400 <= st < 500:
        if "empty input messages" in blob or "role must be" in blob \
                or "list index out of range" in blob or "messages is empty" in blob \
                or "参数" in msg:
            return "ok", "停在参数校验：" + msg[:46]
        return "route", msg[:56]
    return "?", "%s %s" % (st, (msg or err_text(st, txt))[:56])


def chat_body(model, prompt, system=None, out_tokens=DEFAULT_OUT,
              temperature=0.7, extra=None):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": int(out_tokens), "temperature": float(temperature)}
    if system:
        body["messages"].insert(0, {"role": "system", "content": system})
    if extra:
        if not isinstance(extra, dict):
            raise Fail("usage", "--extra 要是 JSON 对象，例如 '{\"top_p\":0.9}'", EXIT_USAGE)
        body.update(extra)
    return body


def answer_of(d):
    """从返回里掏正文：OpenAI 形态优先，兼容 Anthropic 与纯文本。"""
    if not isinstance(d, dict):
        return ""
    ch = d.get("choices")
    if isinstance(ch, list) and ch:
        c0 = ch[0] if isinstance(ch[0], dict) else {}
        msg = c0.get("message") if isinstance(c0.get("message"), dict) else {}
        for v in (msg.get("content"), c0.get("text"), c0.get("content")):
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, list):
                parts = [p.get("text") or "" for p in v if isinstance(p, dict)]
                s = "".join(parts).strip()
                if s:
                    return s
    for k in ("content", "output_text", "text"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    data = d.get("data")
    if isinstance(data, dict):
        return answer_of(data)
    return ""


def usage_of(d):
    u = d.get("usage") if isinstance(d, dict) else None
    if not isinstance(u, dict):
        return dict(inTok=0, outTok=0, total=0)
    it = u.get("prompt_tokens", u.get("input_tokens", 0))
    ot = u.get("completion_tokens", u.get("output_tokens", 0))
    tt = u.get("total_tokens", (it or 0) + (ot or 0))
    return dict(inTok=int(it or 0), outTok=int(ot or 0), total=int(tt or 0))


def ledger_add(rec):
    try:
        arr = []
        if os.path.isfile(LEDGER):
            with io.open(LEDGER, encoding="utf-8") as f:
                arr = json.load(f)
        arr.append(rec)
        with io.open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                        # noqa: BLE001
        pass


def settle(key, host, t0_ms):
    """读流水，算出 t0 之后文本线的净额（负=真花）。免费 GET。"""
    st, txt = http_json("GET", host + "/user/balance/logs?limit=200", key, timeout=45)
    d = jloads(txt) or {}
    logs = d.get("logs") or []
    net, charge, refund, n = 0.0, 0.0, 0.0, 0
    for x in logs:
        ref = str(x.get("reference") or "")
        if "chat/completions" not in ref:
            continue
        try:
            at = float(x.get("at") or 0)
        except Exception:                                    # noqa: BLE001
            continue
        if at < t0_ms:
            continue
        pts = float(x.get("points") or 0)
        net += pts
        n += 1
        if pts < 0:
            charge += pts
        else:
            refund += pts
    return dict(entries=n, net=round(net, 2), charged=round(charge, 2),
                refunded=round(refund, 2), ok=st == 200)


def settle_safe(key, host, t0_ms):
    """settle 的容错版：流水查不到也不让整次调用崩掉。"""
    try:
        return settle(key, host, t0_ms)
    except Fail as e:
        return dict(entries=0, net=0.0, charged=0.0, refunded=0.0, ok=False,
                    err=e.message[:80])


# ───────────────────────── catalog ─────────────────────────
def _live_models(key, host, timeout):
    """GET /api/v1/models 现查：返回 {code: dict(i,o,...)} 或 None。"""
    try:
        st, txt = http_json("GET", host + MODELS_PATH, key, timeout=timeout)
    except Fail:
        return None
    if st != 200:
        return None
    d = jloads(txt) or {}
    out = {}
    for m in (d.get("data") or []):
        if not isinstance(m, dict) or not isinstance(m.get("pricing"), dict):
            continue
        p = m["pricing"]
        v2 = p.get("pricing_v2") or {}
        it = ((v2.get("items") or [{}])[0]) if isinstance(v2, dict) else {}
        rc = it.get("effective_rate_config") or {}
        code = m.get("model_code")
        if not code:
            continue
        out[code] = dict(i=int(rc.get("input") or p.get("per_1k_input") or 0),
                         o=int(rc.get("output") or p.get("per_1k_output") or 0),
                         ctx=int(m.get("context_length") or 0),
                         vis=int(m.get("supports_vision") or 0),
                         unit=int(it.get("usage_unit_size") or 1000000))
    return out


def cmd_catalog(a, key, host):
    live = None
    if a.live:
        if not key:
            raise Fail("usage", "catalog --live 需要一个 Key（--key / A7W_API_KEY）", EXIT_USAGE)
        live = _live_models(key, host, a.timeout)
        if live is None:
            raise Fail("call", "拉不到 GET /api/v1/models", EXIT_CALL)
    rows = []
    for code, m in TEXT_MODELS.items():
        i, o = m["i"], m["o"]
        src = "快照"
        if live is not None and code in live:
            i, o = live[code]["i"], live[code]["o"]
            src = "现查"
        rows.append(dict(model=code, family=m["fam"], name=m["name"], inPoints=i,
                         outPoints=o, ctx=m["ctx"], vision=m["vis"], reasoning=m["rsn"],
                         status=m["st"], statusCN=STATUS_CN.get(m["st"], m["st"]),
                         note=m["note"], proto=m["p"],
                         chat=(m["p"] == "chat"), priceSource=src,
                         inYuan=round(i / float(POINTS_PER_YUAN), 2),
                         outYuan=round(o / float(POINTS_PER_YUAN), 2)))
    if a.family != "all":
        rows = [r for r in rows if r["family"] == a.family]
    if a.sort == "in":
        rows.sort(key=lambda r: (r["inPoints"], r["outPoints"]))
    elif a.sort == "name":
        rows.sort(key=lambda r: r["model"].lower())
    else:
        rows.sort(key=lambda r: (r["outPoints"], r["inPoints"]))
    shown = rows[:a.limit] if a.limit else rows
    groups = {}
    for r in rows:
        groups.setdefault(r["family"], []).append(r)
    out = {"ok": True, "count": len(rows), "shown": len(shown), "family": a.family,
           "sort": a.sort, "rows": shown, "families": [
               {"family": f, "label": FAMILY_CN.get(f, f), "count": len(v),
                "minOut": min(x["outPoints"] for x in v),
                "maxOut": max(x["outPoints"] for x in v)}
               for f, v in sorted(groups.items(),
                                  key=lambda kv: FAMILY_ORDER.index(kv[0])
                                  if kv[0] in FAMILY_ORDER else 99)],
           "pointsPerYuan": POINTS_PER_YUAN, "priceSource": "GET " + MODELS_PATH,
           "note": "单价 = 每百万 token 的点数；字段名叫 per_1k_*，单位其实是 1,000,000"}

    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("文本模型台 · %d 个文本模型（每百万 token 的点数，1 元 = 100 点）" % len(rows))
    print("  价目来源：%s" % ("GET %s%s（现查）" % (host, MODELS_PATH) if live is not None
                            else "内置快照 2026-11-08（--live 现查）"))
    print()
    print("  %s %s %s %s %s %s" % (pad("model", 34), pad("输入/百万", 10, False),
                                   pad("输出/百万", 10, False), pad("折算输出", 11, False),
                                   pad("实测", 9), "一句话"))
    print("  " + "-" * 104)
    for r in shown:
        flag = {"ok": "√ 能调", "gone": "× 未上架", "dead": "× 上游断",
                "?": "- 未测"}.get(r["status"], r["status"])
        tail = r["note"][:34] if r["note"] else (
            "目录只声明 anthropic_messages，本站无该端点" if r["proto"] == "anthropic"
            else ("目录只声明 openai_responses，本包走 chat 入口" if r["proto"] == "responses"
                  else "目录声明 openai_chat，未实测"))
        print("  %s %s %s %s %s %s" % (
            pad(r["model"][:34], 34), pad(pnum(r["inPoints"]), 10, False),
            pad(pnum(r["outPoints"]), 10, False),
            pad(money(r["outPoints"]), 11, False), pad(flag, 9), tail))
    if a.limit and len(rows) > a.limit:
        print("  ... 还有 %d 条（--limit 调大看全）" % (len(rows) - a.limit))
    print()
    print("  家族分布：")
    for g in out["families"]:
        print("    %-14s %2d 个 · 输出 %s - %s 点/百万" % (
            g["label"], g["count"], pnum(g["minOut"]), pnum(g["maxOut"])))
    print()
    lo = min(rows, key=lambda r: r["outPoints"]) if rows else None
    hi = max(rows, key=lambda r: r["outPoints"]) if rows else None
    if lo and hi and lo["outPoints"]:
        print("  最便宜：%s 输出 %s 点/百万（%s）；最贵：%s %s 点/百万（%s）—— %.0f 倍"
              % (lo["model"], pnum(lo["outPoints"]), money(lo["outPoints"]),
                 hi["model"], pnum(hi["outPoints"]), money(hi["outPoints"]),
                 float(hi["outPoints"]) / float(lo["outPoints"])))
    print("  文本只有一个入口：POST %s%s" % (host, CHAT_PATH))
    print("  先免费验一句：check --models %s" % ",".join(DEFAULT_MODELS[:2]))
    return 0


# ───────────────────────── check（免费探针）─────────────────────────
def cmd_check(a, key, host):
    models = parse_models(a.models) or list(DEFAULT_MODELS)
    if len(models) > 12:
        raise Fail("usage", "一次最多探 12 个模型（当前 %d）" % len(models), EXIT_USAGE)
    freeze = MIN_POINTS * len(models)
    if freeze > a.budget:
        raise Fail("budget",
                   "本次要连续探 %d 个模型，每个先冻 %d 点，合计 %d 点 > --budget %d 点。"
                   "探针失败会自动全额退回（净 0 点），但预冻额度要留够：加 --budget %d。"
                   % (len(models), MIN_POINTS, freeze, a.budget, freeze),
                   EXIT_BUDGET)
    if not key:
        raise Fail("usage", "check 需要一个 Key（--key / A7W_API_KEY）", EXIT_USAGE)
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "requests": len(models),
               "estimatedPoints": 0, "transientFreeze": freeze,
               "requestsPlan": [{"model": m, "path": CHAT_PATH,
                                 "body": {"model": m, "messages": []}} for m in models]}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（一个请求都不发）")
        print("  将对 %d 个模型各发一次 POST %s，body 是 {\"model\": ..., \"messages\": []}"
              % (len(models), CHAT_PATH))
        print("  messages 为空 -> 上游一律停在参数校验，不生成、不按 token 结算")
        print("  预冻：每个 %d 点 x %d = %d 点，失败自动全额退回，净 0 点"
              % (MIN_POINTS, len(models), freeze))
        for m in models:
            print("  -> %s" % m)
        return 0

    t0 = int(time.time() * 1000)
    rows = []
    for m in models:
        say("  探 %-34s …" % m)
        try:
            st, txt = http_json("POST", host + CHAT_PATH, key,
                                {"model": m, "messages": []}, timeout=a.timeout)
        except Fail as e:
            st, txt = -1, str(e.message)
        d = jloads(txt)
        verdict, note = classify(st, txt, d)
        meta = TEXT_MODELS.get(m) or {}
        rows.append(dict(model=m, http=st, verdict=verdict,
                         verdictCN=STATUS_CN.get(verdict, "入口在"),
                         note=note, raw=txt[:300],
                         inPoints=meta.get("i"), outPoints=meta.get("o")))
        print("    %s HTTP %-4s %s" % (
            {"ok": "√", "route": "-"}.get(verdict, "×"), st, note))
    s = settle_safe(key, host, t0)
    okn = sum(1 for r in rows if r["verdict"] in ("ok", "route"))
    out = {"ok": True, "models": rows, "usable": okn, "probeCount": len(rows),
           "endpoint": CHAT_PATH, "transientFreeze": freeze,
           "estimatedPoints": 0, "settle": s,
           "note": "messages 为空 -> 停在参数校验；预冻 %d 点已自动退回" % freeze}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print()
    print("  结论：%d / %d 个模型这条路能通（其余看上面原文）" % (okn, len(rows)))
    print("  预冻：%d 个 x %d 点 = %d 点，流水净额 %s 点（已全额退回）"
          % (len(rows), MIN_POINTS, freeze,
             pnum(s["net"]) if s["ok"] else "查询失败"))
    print("  本次花费 0 点：messages 为空，上游停在参数校验，没有生成。")
    return 0


# ───────────────────────── cost ─────────────────────────
def cmd_cost(a, key, host):
    models = parse_models(a.models) or list(DEFAULT_MODELS)
    pairs = resolve(models)
    prompt = a.prompt or ""
    in_tok = a.in_tokens if a.in_tokens else est_tokens(prompt)
    out_tok = a.out_tokens
    rows = []
    for code, meta in pairs:
        gate, tok, basis = cost_of(meta, in_tok, out_tok)
        rows.append(dict(model=code, name=(meta or {}).get("name") or code,
                         family=(meta or {}).get("fam") or "?",
                         inPoints=(meta or {}).get("i"),
                         outPoints=(meta or {}).get("o"),
                         tokenPoints=tok, gatePoints=gate, basis=basis,
                         status=(meta or {}).get("st", "?"),
                         statusCN=STATUS_CN.get((meta or {}).get("st", "?"), "未测")))
    rows.sort(key=lambda r: (r["gatePoints"], r["tokenPoints"] or 0))
    total = round(sum(float(r["gatePoints"]) for r in rows), 2)
    out = {"ok": True, "models": rows, "inTokens": in_tok, "outTokens": out_tok,
           "promptChars": len(prompt), "totalPoints": total,
           "totalYuan": round(total / float(POINTS_PER_YUAN), 2),
           "minPointsPerCall": MIN_POINTS, "pointsPerYuan": POINTS_PER_YUAN,
           "cheapest": rows[0]["model"] if rows else None,
           "mostExpensive": rows[-1]["model"] if rows else None,
           "estimatedPoints": 0,
           "note": "闸门点数 = max(60 点保底, 按 token 算的点数)；实际以流水为准"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("同一句话，%d 个模型逐个报价（1 元 = 100 点）" % len(rows))
    print("=" * 96)
    print("  输入约 %s token（%d 字推算）· 输出上限 %s token"
          % (pnum(in_tok), len(prompt), pnum(out_tok)))
    print()
    print("  %s %s %s %s %s" % (pad("model", 34), pad("输入/百万", 10, False),
                                 pad("输出/百万", 10, False), pad("这次要花", 11, False),
                                 "口径"))
    print("  " + "-" * 92)
    for r in rows:
        mark = "  <- 最省" if r is rows[0] else ""
        print("  %s %s %s %s %s%s" % (
            pad(r["model"][:34], 34), pad(pnum(r["inPoints"]), 10, False),
            pad(pnum(r["outPoints"]), 10, False),
            pad("%s 点" % pnum(r["gatePoints"]), 11, False),
            r["basis"][:44], mark))
    print()
    print("  合计（按闸门）：%s 点 = %s" % (pnum(total), money(total)))
    gates = [float(r["gatePoints"]) for r in rows]
    if len(rows) > 1 and gates[0] != gates[-1]:
        print("  最省 %s %s 点 · 最贵 %s %s 点 · 相差 %.1f 倍"
              % (rows[0]["model"], pnum(rows[0]["gatePoints"]),
                 rows[-1]["model"], pnum(rows[-1]["gatePoints"]),
                 gates[-1] / gates[0] if gates[0] else 0.0))
    else:
        print("  同一句话，每个模型都落在 60 点保底 —— 短对话比的是谁答得好，不是单价")
    bad = [r for r in rows if r["status"] in ("gone", "dead")]
    if bad:
        print("  先验一句再花钱：%s 实测这条入口回不上（%s），用 check 逐个复核"
              % ("、".join(r["model"] for r in bad[:4]),
                 "、".join(sorted({r["statusCN"] for r in bad}))))
    print()
    print("  口径（短对话的账单长什么样）")
    print("    · 价目按「每百万 token」标价，字段名却叫 per_1k_*：数值本身就是 1M 的价")
    print("    · 每次调用先冻 60 点、失败全额退回；900 token 的一问一答")
    print("      按 token 算只有 0.1 - 9 点，所以真实下限就是这 60 点")
    print("    · 单价差异到大量才显形：同样输出 100 万 token，")
    print("      最便宜 40 点（0.40 元），最贵 15,840 点（158.40 元）")
    print("    · 所以横评看的是「同一句话谁答得好」，省的是试错时间")
    print()
    print("  开跑：chat --models %s --prompt \"...\" --yes" % rows[0]["model"])
    print("  全跑：chat --models %s --prompt \"...\" --yes"
          % ",".join(r["model"] for r in rows))
    return 0


# ───────────────────────── doctor ─────────────────────────
def cmd_doctor(a, key, host):
    if not key:
        raise Fail("usage", "doctor 需要一个 Key：--key / A7W_API_KEY / a7w.py login",
                   EXIT_USAGE)
    checks = []
    t0 = int(time.time() * 1000)
    before = 0.0

    def one(label, method, path, body=None, timeout=None, want=None, detail=None):
        """一项自检。任何一项挂了只记 ×，不让整次自检崩掉。

        502 / 503 / 504 是网关抖动（实测会回站点首页 HTML），探针重试一次；
        重试的这一次也失败会自动退款，净额仍是 0。
        """
        st = txt = d = None
        for attempt in (0, 1):
            try:
                st, txt = http_json(method, host + path, key, body,
                                    timeout=timeout or a.timeout)
            except Fail as e:
                checks.append((label, False, e.message[:80]))
                return None
            d = jloads(txt)
            if st in (502, 503, 504) and attempt == 0:
                time.sleep(1.2)
                continue
            break
        ok = want(st, d, txt) if want else (st == 200)
        checks.append((label, bool(ok), detail(st, d, txt) if detail else "HTTP %s" % st))
        return st, d, txt

    def d_balance(st, d, txt):
        return ("HTTP %s · 可用 %s 点 · 冻结 %s 点 · 1 元 = %s 点"
                % (st, pnum((d or {}).get("available_points")),
                   pnum((d or {}).get("frozen") or 0), (d or {}).get("rate")))

    r = one("Key + 余额 GET /user/balance", "GET", "/user/balance", timeout=40,
            want=lambda st, d, t: st == 200 and isinstance(d, dict), detail=d_balance)
    if r:
        before = float((r[1] or {}).get("available_points")
                       or (r[1] or {}).get("points") or 0)

    def d_models(st, d, txt):
        allm = (d or {}).get("data") or []
        texts = [m for m in allm if isinstance(m, dict) and isinstance(m.get("pricing"), dict)]
        big = [m for m in texts
               if int((((m.get("pricing") or {}).get("pricing_v2") or {})
                       .get("items") or [{}])[0].get("usage_unit_size") or 0) == 1000000]
        return "HTTP %s · 共 %d 条 · 文本模型 %d 个 · 计价单位 1M 的 %d 个" % (
            st, len(allm), len(texts), len(big))

    one("模型目录 GET /api/v1/models", "GET", MODELS_PATH, timeout=90,
        want=lambda st, d, t: st == 200 and len((d or {}).get("data") or []) >= 200,
        detail=d_models)

    def d_pricing(st, d, txt):
        rules = (d or {}).get("pricing") or {}
        wild = rules.get("*") or {}
        return "HTTP %s · %d 条规则 · 文本入口%s专属规则 · 通配保底 %s 点 / markup %s%%" % (
            st, len(rules), "有" if CHAT_PATH in rules else "没有",
            pnum(wild.get("minPoints")), pnum(wild.get("markupPercent")))

    one("价目表 GET /api/v1/pricing（文本层无专属规则）", "GET", PRICING_PATH, timeout=40,
        want=lambda st, d, t: (st == 200 and len(((d or {}).get("pricing") or {})) >= 100
                               and CHAT_PATH not in ((d or {}).get("pricing") or {})),
        detail=d_pricing)

    one("任务台账 GET /api/v1/me/tasks", "GET", ME_TASKS + "?limit=2000&page=1", timeout=45,
        want=lambda st, d, t: st == 200 and isinstance(d, dict),
        detail=lambda st, d, t: "HTTP %s · 本页 %d 条 · 累计 %s 条" % (
            st, len((d or {}).get("tasks") or []), pnum((d or {}).get("total"))))

    def d_logs(st, d, txt):
        logs = (d or {}).get("logs") or []
        n = len([x for x in logs if "chat/completions" in str(x.get("reference") or "")])
        return "HTTP %s · 最近 100 条里文本线 %d 笔 · 余额口径 %s 点" % (
            st, n, pnum((d or {}).get("balanceMoving")))

    one("流水 GET /user/balance/logs", "GET", "/user/balance/logs?limit=100", timeout=45,
        want=lambda st, d, t: st == 200 and bool((d or {}).get("logs")), detail=d_logs)

    # 探针 1：空 body -> 网关层拦下（模型参数为空），不落上游
    one("入口探针 1：POST %s 空 body" % CHAT_PATH, "POST", CHAT_PATH, {},
        want=lambda st, d, t: st == 200 and (d or {}).get("code") == 0,
        detail=lambda st, d, t: "HTTP %s · %s" % (
            st, str((d or {}).get("msg") or err_text(st, t))[:44]))

    # 探针 2：合法 model、缺 messages -> 上游 422，停在校验层
    def d_probe2(st, d, txt):
        v, n = classify(st, txt, d)
        return "HTTP %s · %s" % (st, n[:56])

    one("入口探针 2：%s 缺 messages（422 即正确）" % PROBE_MODEL, "POST", CHAT_PATH,
        {"model": PROBE_MODEL}, want=lambda st, d, t: st == 422, detail=d_probe2)

    # 探针 3：anthropic 专线确认没有独立端点
    def d_probe3(st, d, txt):
        code = str(((d or {}).get("error") or {}).get("code") or "") \
            if isinstance((d or {}).get("error"), dict) else ""
        return "HTTP %s · %s" % (st, code or err_text(st, txt)[:40])

    one("/v1/messages 无独立端点（404 unknown_endpoint）", "POST", "/v1/messages",
        {"model": "claude-sonnet-4-5"},
        want=lambda st, d, t: st == 404 and isinstance(d, dict)
        and ((d.get("error") or {}).get("code") == "unknown_endpoint"),
        detail=d_probe3)

    after = before
    r = one("余额前后对比（本轮 0 点）", "GET", "/user/balance", timeout=40,
            want=lambda st, d, t: st == 200 and isinstance(d, dict)
            and (d.get("available_points") is not None),
            detail=lambda st, d, t: ("前 %s -> 后 %s · 差 %s 点"
                                     % (pnum(before), pnum((d or {}).get("available_points")),
                                        pnum(round(float((d or {}).get("available_points")
                                                         or 0) - before, 4)))))
    if r and r[1]:
        after = float(r[1].get("available_points") or 0)
        delta = round(after - before, 4)
        checks[-1] = ("余额前后对比（本轮 0 点）", abs(delta) < 1e-6,
                      "前 %s -> 后 %s · 差 %s 点" % (pnum(before), pnum(after), pnum(delta)))
    elif not r or not r[1]:
        checks[-1] = ("余额前后对比（本轮 0 点）", False,
                      "余额查询失败（网关抖动），本轮无法对比；重跑一次 doctor")

    s = settle_safe(key, host, t0)
    checks.append(("本轮文本线流水净额（应为 0 点）", bool(s["ok"]) and abs(s["net"]) < 1e-6,
                   "预扣 %s 点 · 退回 %s 点 · 净 %s 点（%d 笔）"
                   % (pnum(s["charged"]), pnum(s["refunded"]), pnum(s["net"]),
                      s["entries"])))

    out = {"ok": all(c[1] for c in checks), "host": host, "endpoint": host + CHAT_PATH,
           "transientFreeze": MIN_POINTS * 3,
           "settle": s, "estimatedPoints": 0,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE

    print("自检（5 个只读端点 + 3 个探针，全部停在校验层）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 50), dd))
    print()
    print("  文本入口：POST %s%s（唯一一条；/v1/messages 实测 404）" % (host, CHAT_PATH))
    print("  单价来源：GET %s%s 的 pricing.per_1k_*（单位是「每百万 token」）"
          % (host, MODELS_PATH))
    print("  查询：文本同步返回，没有 taskId；异步变体用 GET %s%s/<id>（免费）"
          % (host, TASKS_PATH))
    print("  预冻：2 次 POST 探针各冻 %d 点，失败自动全额退回；流水净额 %s 点"
          % (MIN_POINTS, pnum(s["net"]) if s["ok"] else "查询失败"))
    print("  本轮花费 0 点：探针全部停在参数校验，没有生成、没有按 token 结算。")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── chat ─────────────────────────
def _slug(model):
    return re.sub(r"[^0-9A-Za-z]+", "_", model).strip("_").lower()[:40] or "model"


def _gate_chat(a, rows, in_tok, out_tok):
    cost = 0.0
    for code, meta in rows:
        cost += cost_of(meta, in_tok, out_tok)[0]
    cost = round(cost, 2)
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %s 点（%s）超过 --budget %d 点，一个请求都不发。"
                   "减少 --models、调小 --out-tokens，或把 --budget 提到 %d。"
                   % (pnum(cost), money(cost), a.budget, int(cost)),
                   EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实调用 %d 个模型，每个先冻 %d 点，预计 %s 点（%s）。"
                   "确认请加 --yes。" % (len(rows), MIN_POINTS, pnum(cost), money(cost)),
                   EXIT_CONFIRM)
    return cost


def cmd_chat(a, key, host):
    pairs = resolve(parse_models(a.models) or list(DEFAULT_MODELS))
    if not pairs:
        raise Fail("usage", "必须给 --models（逗号分隔）", EXIT_USAGE)
    if len(pairs) > 8:
        raise Fail("usage", "一次最多横评 8 个模型（当前 %d），拆两次更稳" % len(pairs),
                   EXIT_USAGE)
    prompt = (a.prompt or "").strip()
    if not prompt:
        raise Fail("usage", "必须给 --prompt（这次要问所有模型的那句话）", EXIT_USAGE)
    if len(prompt) > 8000:
        raise Fail("usage", "--prompt 最多 8000 字（当前 %d）" % len(prompt), EXIT_USAGE)
    out_tok = int(a.out_tokens or DEFAULT_OUT)
    if not (16 <= out_tok <= 8192):
        raise Fail("usage", "--out-tokens 支持 16 - 8192（当前 %d）" % out_tok, EXIT_USAGE)
    in_tok = a.in_tokens if a.in_tokens else est_tokens(
        prompt + (a.system or ""))
    cost = _gate_chat(a, pairs, in_tok, out_tok)
    extra = None
    if a.extra:
        try:
            extra = json.loads(a.extra)
        except Exception:                                    # noqa: BLE001
            raise Fail("usage", "--extra 要是 JSON 对象，例如 '{\"top_p\":0.9}'", EXIT_USAGE)

    if a.dry_run:
        plan = []
        for code, meta in pairs:
            gate, tok, basis = cost_of(meta, in_tok, out_tok)
            plan.append({"model": code, "points": gate, "tokenPoints": tok,
                         "basis": basis,
                         "body": chat_body(code, prompt, a.system, out_tok,
                                           a.temperature, extra)})
        out = {"ok": True, "dryRun": True, "endpoint": host + CHAT_PATH,
               "requests": plan, "totalPoints": cost,
               "totalYuan": round(cost / float(POINTS_PER_YUAN), 2),
               "inTokens": in_tok, "outTokens": out_tok}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（一个请求都不发）")
        print("  端点：POST %s" % (host + CHAT_PATH))
        print("  提问：%s" % prompt[:120])
        print("  输入约 %s token · 输出上限 %s token" % (pnum(in_tok), pnum(out_tok)))
        for p in plan:
            print("  -> %-30s 预计 %s 点 · %s" % (p["model"], pnum(p["points"]),
                                                 p["basis"][:60]))
        print("  合计：%s 点 = %s" % (pnum(cost), money(cost)))
        print("  每个模型先冻 %d 点，失败自动全额退回。" % MIN_POINTS)
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(a.outdir or ".", "text-models-%s" % stamp)
    try:
        os.makedirs(run_dir)
    except OSError as e:
        raise Fail("internal", "建不了输出目录 %s：%s" % (run_dir, e), EXIT_INTERNAL)

    t0 = int(time.time() * 1000)
    rows = []
    for idx, (code, meta) in enumerate(pairs, 1):
        say("  [%d/%d] %s …" % (idx, len(pairs), code))
        gate, tok, basis = cost_of(meta, in_tok, out_tok)
        body = chat_body(code, prompt, a.system, out_tok, a.temperature, extra)
        t1 = time.time()
        try:
            st, txt = http_json("POST", host + CHAT_PATH, key, body, timeout=a.timeout)
        except Fail as e:
            st, txt = -1, str(e.message)
        dt = time.time() - t1
        d = jloads(txt)
        answer = answer_of(d)
        usage = usage_of(d)
        verdict, note = classify(st, txt, d)
        ok = bool(answer)
        rec = dict(index=idx, model=code, name=(meta or {}).get("name") or code,
                   http=st, ok=ok, verdict=verdict, note=note, answer=answer,
                   usage=usage, elapsed=round(dt, 1),
                   inPoints=(meta or {}).get("i"), outPoints=(meta or {}).get("o"),
                   estimatePoints=gate, tokenPoints=tok, basis=basis,
                   raw=txt[:1500])
        rows.append(rec)
        if ok:
            fn = "%02d-%s.md" % (idx, _slug(code))
            with io.open(os.path.join(run_dir, fn), "w", encoding="utf-8",
                         newline="\n") as f:
                f.write("# %s\n\n" % code)
                f.write("- 输入约 %s token · 实际用量 %s\n"
                        % (pnum(in_tok), pnum(usage["total"])))
                f.write("- 单价：每百万 token 输入 %s 点 / 输出 %s 点\n"
                        % (pnum((meta or {}).get("i")), pnum((meta or {}).get("o"))))
                f.write("- 本次预计 %s 点（%s）\n\n" % (pnum(gate), basis))
                f.write("## 问题\n\n%s\n\n## 回答\n\n%s\n" % (prompt, answer))
            rec["file"] = fn
        else:
            print("    ! %s：%s" % (code, note[:80]))

    s = settle_safe(key, host, t0)
    real = s["net"]
    man = {"ok": any(r["ok"] for r in rows), "generatedAt": stamp,
           "endpoint": host + CHAT_PATH, "prompt": prompt, "system": a.system or "",
           "inTokens": in_tok, "outTokens": out_tok, "temperature": a.temperature,
           "models": rows, "estimatePoints": cost,
           "settle": s, "actualPoints": real,
           "actualYuan": round(real / float(POINTS_PER_YUAN), 2),
           "costBasis": "预计按 60 点保底 + 每百万 token 单价；实际取流水净额"}
    with io.open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8",
                 newline="\n") as f:
        f.write(json.dumps(man, ensure_ascii=False, indent=1))
    _write_sheet(run_dir, man, rows)
    ledger_add({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "dir": run_dir,
                "models": [r["model"] for r in rows],
                "ok": sum(1 for r in rows if r["ok"]),
                "estimatePoints": cost, "actualPoints": real,
                "actualYuan": man["actualYuan"], "settle": s})

    out = dict(ok=man["ok"], dir=run_dir, prompt=prompt,
               models=[{k: r[k] for k in ("model", "ok", "http", "verdict", "note",
                                          "usage", "elapsed", "estimatePoints",
                                          "answer", "file")
                        if k in r} for r in rows],
               estimatePoints=cost, actualPoints=real, actualYuan=man["actualYuan"],
               settle=s, manifest=os.path.join(run_dir, "manifest.json"),
               sheet=os.path.join(run_dir, "对比清单.md"))
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if man["ok"] else EXIT_CALL

    print()
    print("横评完成（%d 个模型）" % len(rows))
    print("  %s %s %s %s %s" % (pad("model", 30), pad("状态", 8),
                                 pad("用时", 7), pad("token", 9), "说明"))
    print("  " + "-" * 88)
    for r in rows:
        print("  %s %s %s %s %s" % (
            pad(r["model"][:30], 30), pad("√ 出话" if r["ok"] else "× 没出", 8),
            pad("%.1fs" % r["elapsed"], 7),
            pad(pnum(r["usage"]["total"]), 9), r["note"][:40]))
    print()
    print("  预计：%s 点（%s）" % (pnum(cost), money(cost)))
    if s["ok"]:
        print("  实际：%s 点（%s）—— 取流水净额：预扣 %s 点、退回 %s 点"
              % (pnum(real), money(real), pnum(s["charged"]), pnum(s["refunded"])))
    else:
        print("  实际：流水查询失败，以控制台账单为准")
    print("  目录：%s" % run_dir)
    best = [r for r in rows if r["ok"]]
    if len(best) > 1:
        fast = min(best, key=lambda r: r["elapsed"])
        long = max(best, key=lambda r: len(r["answer"]))
        print("  最快：%s（%.1fs）· 最长：%s（%d 字）"
              % (fast["model"], fast["elapsed"], long["model"], len(long["answer"])))
    print("  看对比：%s" % os.path.join(run_dir, "对比清单.md"))
    return 0 if man["ok"] else EXIT_CALL


def _write_sheet(run_dir, man, rows):
    L = []
    L.append("# 同一句话，%d 个模型横评" % len(rows))
    L.append("")
    L.append("> 生成时间：%s · 入口：`POST %s` · 输入约 %s token · 输出上限 %s"
             % (man["generatedAt"], CHAT_PATH, pnum(man["inTokens"]),
                pnum(man["outTokens"])))
    L.append("")
    L.append("## 问题")
    L.append("")
    L.append("```")
    L.append(man["prompt"])
    L.append("```")
    L.append("")
    L.append("## 一张表看完")
    L.append("")
    L.append("| # | 模型 | 状态 | 用时 | token | 预计点 | 回答字数 | 文件 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append("| %d | `%s` | %s | %.1fs | %s | %s | %d | %s |" % (
            r["index"], r["model"], "√" if r["ok"] else "×", r["elapsed"],
            pnum(r["usage"]["total"]), pnum(r["estimatePoints"]),
            len(r["answer"]), r.get("file") or "-"))
    L.append("")
    L.append("## 花费")
    L.append("")
    L.append("- 预计：%s 点（%s）" % (pnum(man["estimatePoints"]),
                                   money(man["estimatePoints"])))
    s = man.get("settle") or {}
    if s.get("ok"):
        L.append("- 实际：%s 点（%s）—— 流水净额，预扣 %s / 退回 %s"
                 % (pnum(man.get("actualPoints")), money(man.get("actualPoints")),
                    pnum(s.get("charged")), pnum(s.get("refunded"))))
    L.append("- 口径：每次调用先冻 60 点；价目按每百万 token 的点数")
    L.append("")
    L.append("## 逐个回答")
    for r in rows:
        L.append("")
        L.append("### %s" % r["model"])
        L.append("")
        if r["ok"]:
            L.append(r["answer"])
        else:
            L.append("未出话：%s" % r["note"])
    L.append("")
    with io.open(os.path.join(run_dir, "对比清单.md"), "w", encoding="utf-8",
                 newline="\n") as f:
        f.write("\n".join(L))


# ───────────────────────── log ─────────────────────────
def cmd_log(a, key, host):
    if not os.path.isfile(LEDGER):
        out = {"ok": True, "count": 0, "entries": []}
    else:
        with io.open(LEDGER, encoding="utf-8") as f:
            arr = json.load(f)
        out = {"ok": True, "count": len(arr), "entries": arr[-a.limit:]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("本地台账（显示 %d / 共 %d 条）" % (len(out["entries"]), out["count"]))
    for e in out["entries"]:
        ms = e.get("models") or []
        print("  %s  %-3s %-30s 预计 %-6s 实际 %-6s %s" % (
            e.get("at"), "%d/%d" % (e.get("ok") or 0, len(ms)),
            (e.get("dir") or "-")[-30:], pnum(e.get("estimatePoints")),
            pnum(e.get("actualPoints")), ",".join(ms)[:40]))
    if not out["entries"]:
        print("  （还没有记录；先跑一次 chat）")
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 文本模型台：同一句话，92 个文本模型先报价再开口",
        epilog="端点：POST %s/api/v1/chat/completions（唯一文本入口，每百万 token 计价）· "
               "GET %s/api/v1/models（92 条文本模型带价）· "
               "GET %s/api/v1/pricing · GET %s/user/balance/logs" % (
                   DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST, DEFAULT_HOST),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = %d 元）"
                         % (DEFAULT_BUDGET, DEFAULT_BUDGET // POINTS_PER_YUAN))
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="（保持家族参数一致；本包用 --out-tokens 控制输出）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="92 个文本模型 + 每百万 token 单价（免费）",
                       allow_abbrev=False)
    p.add_argument("--family", default="all",
                   help="只看这一族：claude / qwen / kimi / glm / deepseek / gemini / all")
    p.add_argument("--sort", choices=["out", "in", "name"], default="out",
                   help="排序：按输出价 / 输入价 / 名字（默认 out）")
    p.add_argument("--limit", type=int, default=30, help="最多列几条（默认 30，0 = 全部）")
    p.add_argument("--live", action="store_true", help="现查 /api/v1/models 刷新单价")
    p.add_argument("--timeout", type=int, default=60, help="单次请求超时秒数")
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("check", help="一个模型通不通，先免费问一句（净 0 点）",
                       allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔，默认 %s" % ",".join(DEFAULT_MODELS[:2]))
    p.add_argument("--timeout", type=int, default=60, help="单个探针超时秒数")
    p.add_argument("--dry-run", action="store_true", help="只打印探针，不发请求")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("cost", help="同一句话多模型报价（免费）", allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔，默认 %s" % ",".join(DEFAULT_MODELS))
    p.add_argument("--prompt", default="", help="要问的那句话（用来估算输入 token）")
    p.add_argument("--in-tokens", type=int, default=0, help="直接指定输入 token（默认按字数估）")
    p.add_argument("--out-tokens", type=int, default=DEFAULT_OUT,
                   help="输出 token 上限（默认 %d）" % DEFAULT_OUT)
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("doctor", help="自检 5 个只读端点 + 3 个探针（免费）",
                       allow_abbrev=False)
    p.add_argument("--timeout", type=int, default=90, help="单次探针超时秒数")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("chat", help="同一句话多模型横评（要 --yes，受 --budget 管）",
                       allow_abbrev=False)
    p.add_argument("--models", help="逗号分隔，默认 %s" % ",".join(DEFAULT_MODELS))
    p.add_argument("--prompt", help="这次要问所有模型的那句话")
    p.add_argument("--system", help="可选的系统提示词（所有模型共用）")
    p.add_argument("--out-tokens", type=int, default=DEFAULT_OUT,
                   help="每个模型输出上限（默认 %d，16 - 8192）" % DEFAULT_OUT)
    p.add_argument("--in-tokens", type=int, default=0, help="直接指定输入 token（默认按字数估）")
    p.add_argument("--temperature", type=float, default=0.7, help="采样温度（默认 0.7）")
    p.add_argument("--extra", help="附加请求字段的 JSON，例如 '{\"top_p\":0.9}'")
    p.add_argument("--outdir", help="输出目录（默认当前目录）")
    p.add_argument("--timeout", type=int, default=180, help="单次调用超时秒数")
    p.add_argument("--yes", action="store_true", help="确认真实调用并冻结点数")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不调用")
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("log", help="本地台账（免费）", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20, help="显示最近几条")
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以：每个子 parser 都补一份，default=SUPPRESS
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


FREE = ("cmd_catalog", "cmd_cost", "cmd_log")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0),
                       ("family", "all"), ("sort", "out"), ("limit", 30),
                       ("live", False), ("timeout", 90), ("models", None),
                       ("prompt", ""), ("system", None), ("out_tokens", DEFAULT_OUT),
                       ("in_tokens", 0), ("temperature", 0.7), ("extra", None),
                       ("outdir", None), ("yes", False), ("dry_run", False)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    key, host = load_conf(a.key, a.host)
    fn_name = getattr(a.fn, "__name__", "")
    try:
        if not key and fn_name not in FREE:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n"
                       "注册领 Key：https://api.a7w.cn/", EXIT_USAGE)
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
    except Exception:                                        # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
