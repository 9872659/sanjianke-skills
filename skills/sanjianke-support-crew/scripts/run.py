#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 客诉处置小组 —— 四个角色的**处置流程**（零第三方依赖）。

这是 **L3 多智能体分工互审** 的第九种形态：**处置式（disposition）**。
与已有的八种都不同——它既不是"评价内容"，也不是"角色竞争"：
它处理的是一张**工单**，而且**每一步都带时效与权限约束**。

    接报 → 技术判断 → 授权（受权限矩阵约束）→ 复盘

和内容类小组的**结构性差别只有一条**，但这条决定了整个包的样子：

    内容类小组对"一份稿子"做评价，评价**不花钱**，说错了顶多是意见不合；
    本包对"一张工单"做处置，处置**要花钱**（补偿/退款/延期/赠额），
    而且**不是每个角色都有权花这笔钱** —— 所以必须有权限矩阵、必须有时效、
    必须有升级路径。这三件事在内容类包里**结构上不存在**。

九个子命令：

    roles        列出四个角色的职权、产出契约与否决权（零成本、不联网）
    policy       打印权限矩阵与补偿枚举（零成本、不联网）——**本包的核心口径**
    intake       接报：分类 + 定级（P0~P3）+ 承诺时限 + 影响面
    diagnose     技术判断：产品缺陷 / 用户误用 / 环境问题 + 可复现步骤 + 证据
    settle       处置方案：补偿项与金额，**受权限矩阵硬约束**
    review       复盘：根因 + 改文档/改产品 + 同类工单预警
    run          一条命令跑完四步，出处置建议 + 话术
    log          把 run 落下的处置台账读出来（零成本）
    cost         报价：这次处置大概花多少 token（金额要你自己填单价）
    models       列出 api.a7w.cn 当前在架的模型（现查，别写死）

真实请求的端点（都在 api.a7w.cn 上）：

    大模型     POST https://api.a7w.cn/api/v1/chat/completions   （OpenAI 兼容协议）
    模型清单   GET  https://api.a7w.cn/api/v1/models

用法
    python3 run.py roles
    python3 run.py policy
    python3 run.py intake    --file 工单.md
    python3 run.py diagnose  --file 工单.md --card 工单卡.json
    python3 run.py settle    --file 工单.md --card 工单卡.json --diag 判定.json
    python3 run.py settle    --file 工单.md --card 工单卡.json --diag 判定.json --grant-cap 0
    python3 run.py review    --file 工单.md --card 工单卡.json --diag 判定.json --settle 处置.json
    python3 run.py run       --file 工单.md --outdir 处置输出
    python3 run.py cost      --file 工单.md
    python3 run.py run --file 工单.md --dry-run      # 只看提示词，不花钱

配 Key（三种方式任选，代码与文档里都不含任何 Key）
    python3 run.py run --file 工单.md --key sk-xxxx
    export A7W_API_KEY=sk-xxxx        # Windows PowerShell: $env:A7W_API_KEY="sk-xxxx"
    到 https://api.a7w.cn/ 注册后写入 ~/.a7w/config.json（scripts/a7w.py login --key sk-xxxx）

⚠️ 本包**不接真实支付 / 工单系统，也不联网去改任何后台数据**（网关只用来调大模型）。
它产出的是**处置建议与话术**：真的要退款、要赠额、要延期，必须由人工在后台执行。

设计取舍（为什么是"处置式"，而不是又一个"评审委员会"）
    · **权限是硬的，不是提示**：一线可以批多少、二线可以批多少写在 `POLICY` 里。
      模型给出一笔超出当前权限的补偿 → **本地硬闸门 exit=3**，并要求它给出 `escalate_to`。
      它不许"自作主张"地把钱批出去。这是本包唯一不可替代的机制。
    · **补偿项是枚举**：不许自创补偿（"送个定制玩偶"这种）。枚举之外一律拦。
    · **时效是硬指标**：P0/P1 的承诺时限来自 `policy`，不是模型随口写的；
      超出承诺时限给出处置 → 标红。
    · **结论必须引用工单原文**：每条判定与处置都要锚定到工单里真实存在的句子，
      编造引文（"用户说他很生气要起诉"）一律剔出。
    · **不许承诺**："保证解决""一定赔偿""永久免费"这类承诺类话术进合规闸门。
    · **本包不接真实支付/工单系统**：它给的是处置建议与话术，落地要人工在后台做。
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 不许往包里写 .pyc。跑一次就会在 scripts/__pycache__/ 留下 .pyc，而 Skill 包的上传
# 白名单里没有它（CLI 的排除清单里就有 .pyc，**不会导致上传被拒**，
# 但包内多出一堆二进制垃圾没意义）。在 import a7w **之前**关掉字节码写入。
sys.dont_write_bytecode = True
import a7w  # noqa: E402

CHAT_URL = a7w.HOST + "/api/v1/chat/completions"
MODELS_URL = a7w.HOST + "/api/v1/models"

# 实测可用：这个别名会路由到 deepseek-flash。注意它**不在** /api/v1/models 的返回列表里，
# 所以别拿"列表里没有"当"不能用"。要换模型用 `run.py models` 现查在架的名字。
DEFAULT_MODEL = "deepseek-chat"
CHAT_RETRIES = 4

# 退出码（与同族对齐）：
EXIT_OK = 0            # 跑完且没有任何硬闸门命中
EXIT_USAGE = 2         # 参数/配置错（文件不存在、--outdir 在包内、--policy 不合法）
EXIT_GATE = 3          # 硬闸门命中（合规/占位符/照抄示例/锚点/**越权**/时效/完整性/成本）
EXIT_CALL = 4          # 调用失败（网络 / 鉴权 / 点数 / 模型名）
EXIT_BUDGET = 5        # 预算超限，已就地中止（**未发起那次调用**）
EXIT_INTERRUPT = 130   # 用户中断

# 口径版本号：**必须进断点 key**。
# 事故复盘（同族踩过）：改了提示词或某个闸门口径却不改 key，续跑会把上一版口径的旧产物
# 当成"已完成"直接复用，产出对不上文档。加版本号是最省事的根治办法。
CREW_VERSION = "support-crew-1.0.0"
PROMPT_VERSION = "support-prompt-1.0.0"
GATE_VERSION = "support-gate-1.0.0"
POLICY_VERSION = "support-policy-1.0.0"

ROLE_ORDER = ("intake", "diagnose", "settle", "review")


# ===========================================================================
# 权限矩阵与补偿枚举（本包的**核心口径**）
#
# 【为什么写死在包里】内容类小组的口径（"这段文案好不好"）是软的，可以商量；
# 本包的口径（"谁能批多少钱"）是**制度**：一线 50、二线 300 这种数字，
# 不能由模型每次自己发挥，否则同一个工单两次跑出两个数，账就对不上。
# 所以矩阵是常量，`--policy` 只能**覆盖**它，并且覆盖后的矩阵会原样打进产物，
# 让读报告的人一眼看出这份处置是按哪套权限算出来的。
#
# 【金额单位】统一用「点」（平台口径 1 元 = 100 点），与 --budget 同一单位。
# 单位混用是同族踩过的坑：一个说元、一个说点，1 元被当成 1 点，差 100 倍。
# ===========================================================================

POINTS_PER_YUAN = 100.0

# 补偿项枚举。**不许自创补偿**：枚举之外一律判越权（闸门五）。
# `cash` 标记它是不是"真金白银出账"——它决定越权判定时的严格程度口径说明。
COMPENSATION_TYPES = {
    "refund_full": {
        "label": "全额退款",
        "cash": True,
        "desc": "把该笔订单的实付金额全额退回原支付渠道",
        "note": "出账最大，最需要权限；一线一般没有这个权限",
    },
    "refund_partial": {
        "label": "部分退款",
        "cash": True,
        "desc": "按比例或按金额退回一部分实付金额",
        "note": "要在金额里写清退多少点",
    },
    "extend_service": {
        "label": "服务延期",
        "cash": False,
        "desc": "延长会员/订阅/交付周期，不涉及现金出账",
        "note": "金额字段填**折算的点数**（比如一个月会员 ≈ 3000 点）",
    },
    "grant_credit": {
        "label": "赠额",
        "cash": False,
        "desc": "向账户发放可消费的点数余额",
        "note": "本包最常见的补偿形态",
    },
    "coupon": {
        "label": "优惠券",
        "cash": False,
        "desc": "发放下单可用的满减/折扣券",
        "note": "要写清面额与有效期",
    },
    "free_retry": {
        "label": "免费重试一次",
        "cash": False,
        "desc": "让用户免费重跑一次失败的任务/生成",
        "note": "成本可忽略时优先用它，而不是直接发点",
    },
    "manual_repair": {
        "label": "人工修复数据",
        "cash": False,
        "desc": "由后台人工修正用户侧的脏数据（订单状态、额度、任务记录）",
        "note": "只修数据不给钱，通常成本最低、用户接受度也高",
    },
    "apology_only": {
        "label": "仅致歉不改动",
        "cash": False,
        "desc": "确认无责或责任在用户侧/环境侧，只做致歉与说明",
        "note": "选它的时候**理由必须写清**（闸门七）",
    },
}

COMPENSATION_KEYS = tuple(COMPENSATION_TYPES.keys())

# 权限阶梯：谁能批到什么额度（单位：点）。
#   cap            本级可批的**单张工单累计**补偿上限
#   need_below     低于这个额度本级可**自主**批；达到或超过就要**上一级确认**
#   escalate_to    超权限时升给谁（闸门五要求输出它）
#   sla_minutes    本级承诺的处置时限（分钟）——对应 severity 的 SLA
AUTHORITY_LEVELS = {
    "L1_一线客服": {
        "rank": 1,
        "cap": 5000,
        "need_below": 5000,
        "escalate_to": "L2_二线主管",
        "sla_minutes": {"P0": 15, "P1": 60, "P2": 240, "P3": 1440},
        "note": "自主额度 50 元以内；超过就得升级，不许先批后报",
    },
    "L2_二线主管": {
        "rank": 2,
        "cap": 30000,
        "need_below": 30000,
        "escalate_to": "L3_运营负责人",
        "sla_minutes": {"P0": 15, "P1": 30, "P2": 120, "P3": 720},
        "note": "自主额度 300 元以内；涉及全额退款或批量影响必须升级",
    },
    "L3_运营负责人": {
        "rank": 3,
        "cap": 200000,
        "need_below": 50000,
        "escalate_to": "L4_公司决策",
        "sla_minutes": {"P0": 10, "P1": 30, "P2": 120, "P3": 480},
        "note": "500 元以上要公司决策；2000 元以上本级也批不了",
    },
    "L4_公司决策": {
        "rank": 4,
        "cap": 100000000,
        "need_below": 100000000,
        "escalate_to": "",
        "sla_minutes": {"P0": 10, "P1": 30, "P2": 120, "P3": 480},
        "note": "兜底层级，不再往上升",
    },
}

AUTHORITY_KEYS = tuple(AUTHORITY_LEVELS.keys())
DEFAULT_AUTHORITY = "L1_一线客服"

# 定级：等级 → 影响面、承诺时限的口径来源。
# ⚠️ 承诺时限**必须来自这里**（闸门六），不是模型随口写的数字。
SEVERITY_LEVELS = {
    "P0": {
        "label": "P0 · 资金/数据事故",
        "desc": "涉及资金错误、用户数据丢失或账号被盗，且仍在持续",
        "impact_floor": "受影响用户数未知或 ≥ 10",
        "sla_note": "最高优先级：先止血（冻结/回滚/限流），再谈补偿",
        "examples": "重复扣款且持续、任务把用户素材删了、账号被盗且能下单",
    },
    "P1": {
        "label": "P1 · 功能不可用",
        "desc": "核心功能整段不可用或结果完全不可用，用户无法完成主流程",
        "impact_floor": "单用户或小批量，但阻塞主流程",
        "sla_note": "高优先级：当天必须给出可执行的处置",
        "examples": "生成任务必然失败、付款后额度不到账、导出全是坏文件",
    },
    "P2": {
        "label": "P2 · 体验受损",
        "desc": "能用但不好用：慢、偶发失败、结果质量不达预期、文案与事实不符",
        "impact_floor": "单用户，可绕过",
        "sla_note": "常规优先级",
        "examples": "偶发超时、字幕断句差、界面误导导致多花了点",
    },
    "P3": {
        "label": "P3 · 咨询/建议",
        "desc": "不是故障：用法咨询、功能建议、吐槽、重复提问",
        "impact_floor": "无实际损失",
        "sla_note": "低优先级：可批量回复",
        "examples": "问怎么换音色、建议加一个功能、觉得价格贵",
    },
}

SEVERITY_KEYS = ("P0", "P1", "P2", "P3")

# 工单分类枚举。**枚举是刻意的**：自由文本没法做闸门，也说不清"该谁处理"。
TICKET_TYPES = {
    "billing": {"label": "计费与扣费", "owner": "财务对账 + 网关"},
    "entitlement": {"label": "额度与权益", "owner": "账号/权益后台"},
    "task_failure": {"label": "任务执行失败", "owner": "算力网关 + 上游模型"},
    "quality": {"label": "产出质量不达预期", "owner": "产品与提示词"},
    "account_security": {"label": "账号与安全", "owner": "安全 + 风控"},
    "usability": {"label": "易用性与文档", "owner": "产品与文档"},
    "consult": {"label": "咨询与建议", "owner": "客服一线"},
}

TICKET_TYPE_KEYS = tuple(TICKET_TYPES.keys())

# 技术判断的归因枚举：产品缺陷 / 用户误用 / 环境问题。
# 这条三分类是本包"技术判断"角色的核心：**责任归属不同，处置口径完全不同**。
ROOT_CAUSE_CLASSES = {
    "product_defect": {
        "label": "产品缺陷",
        "desc": "我们自己代码/配置/口径错了，与用户无关，必然可复现",
        "responsibility": "我们全责",
        "compensation_bias": "应给补偿，且要复盘防复发",
    },
    "user_misuse": {
        "label": "用户误用",
        "desc": "产品行为符合设计与文档，用户用法与文档不符",
        "responsibility": "用户侧，但要检查文档是否说清楚了",
        "compensation_bias": "通常只做引导；文档确实没写清才给少量补偿",
    },
    "environment_issue": {
        "label": "环境问题",
        "desc": "用户侧网络/浏览器/客户端版本，或上游第三方临时故障",
        "responsibility": "不在双方，属外部因素",
        "compensation_bias": "按商誉酌情，通常给免费重试而非现金",
    },
    "insufficient_evidence": {
        "label": "证据不足",
        "desc": "现有信息无法判定归属，需要用户补充材料或后台查证",
        "responsibility": "待定",
        "compensation_bias": "先不做补偿承诺，先取证",
    },
}

ROOT_CAUSE_KEYS = tuple(ROOT_CAUSE_CLASSES.keys())

# 可复现性枚举（技术判断必须给这个，否则等于没判断）
REPRODUCIBILITY = {
    "always": "必然复现（每一步都一样）",
    "sometimes": "偶发复现（有时好有时坏）",
    "once": "只出现过一次，无法复现",
    "not_attempted": "尚无信息可供复现（等用户补材料）",
}
REPRO_KEYS = tuple(REPRODUCIBILITY.keys())

# 处置方案的四档结论文径（枚举，便于闸门判定）
DISPOSITION_CHOICES = ("当场可批", "需升级", "不予补偿", "待补证")

# 话术：**送给用户的那段字**（面客字段，零豁免）；内部说明（审类字段，开排除）
VOICE_MAX_CHARS = 600          # 面客话术的长度上限（客服场景没人读 1000 字）


def default_policy():
    """包里写死的默认权限矩阵。返回的是**拷贝**，调用方随便改。"""
    return {
        "policy_version": POLICY_VERSION,
        "points_per_yuan": POINTS_PER_YUAN,
        "compensation_types": {k: v["label"] for k, v in COMPENSATION_TYPES.items()},
        "severity_levels": list(SEVERITY_KEYS),
        "authority_levels": {
            k: {"rank": v["rank"], "cap": v["cap"], "need_below": v["need_below"],
                "escalate_to": v["escalate_to"], "sla_minutes": dict(v["sla_minutes"])}
            for k, v in AUTHORITY_LEVELS.items()
        },
        "sla_source": "authority_levels[本级].sla_minutes[severity]",
    }


def load_policy(path=None):
    """读 `--policy` 覆盖文件并做**严格校验**；不合法一律 exit=2（配置错，不是闸门）。

    校验点（少一个都可能让越权闸门形同虚设）：
      · authority_levels 非空，且每级必须有 rank/cap/sla_minutes
      · sla_minutes 必须覆盖全部 P0~P3（否则时效闸门无口径可用）
      · escalate_to 必须指向存在的层级，或为空串（最高层）
      · __levels 只能收窄：覆盖文件里**不能新增**补偿项枚举
        （能新增就等于把"不许自创补偿"这条闸门关掉了）
    """
    base = default_policy()
    if not path:
        return base
    p = Path(path)
    if not p.is_file():
        raise UsageError("--policy 文件不存在：{}".format(path))
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("--policy 不是合法 JSON（{}）：{}".format(exc, path))
    if not isinstance(raw, dict):
        raise UsageError("--policy 顶层必须是对象")

    merged = base
    merged["policy_version"] = str(raw.get("policy_version") or POLICY_VERSION)
    merged["policy_file"] = str(p)

    # 补偿项：只允许**收窄**，不许新增
    ct = raw.get("compensation_types")
    if ct is not None:
        if not isinstance(ct, dict) or not ct:
            raise UsageError("--policy.compensation_types 必须是非空对象")
        extra = [k for k in ct if k not in COMPENSATION_TYPES]
        if extra:
            raise UsageError(
                "补偿项枚举**不许扩充**（覆盖文件里新增了 {}）。"
                "能新增就等于把「不许自创补偿」这条硬闸门关掉了；"
                "只能从包里写死的这 {} 项里收窄。".format(
                    "、".join(extra), len(COMPENSATION_TYPES)))
        merged["compensation_types"] = {k: str(ct[k]) for k in ct}

    al = raw.get("authority_levels")
    if al is not None:
        if not isinstance(al, dict) or not al:
            raise UsageError("--policy.authority_levels 必须是非空对象")
        levels = {}
        for k, v in al.items():
            if not isinstance(v, dict):
                raise UsageError("authority_levels.{} 必须是对象".format(k))
            try:
                cap = float(v.get("cap"))
                rank = int(v.get("rank"))
            except (TypeError, ValueError):
                raise UsageError("authority_levels.{} 的 cap/rank 必须是数字".format(k))
            sla = v.get("sla_minutes") or {}
            if not isinstance(sla, dict):
                raise UsageError("authority_levels.{}.sla_minutes 必须是对象".format(k))
            miss = [s for s in SEVERITY_KEYS if s not in sla]
            if miss:
                raise UsageError(
                    "authority_levels.{}.sla_minutes 缺 {} —— 时效闸门口径来自这里，"
                    "缺了就没法判「超时」".format(k, "、".join(miss)))
            levels[k] = {
                "rank": rank, "cap": cap,
                "need_below": float(v.get("need_below", cap)),
                "escalate_to": str(v.get("escalate_to") or ""),
                "sla_minutes": {s: float(sla[s]) for s in SEVERITY_KEYS},
            }
        for k, v in levels.items():
            up = v["escalate_to"]
            if up and up not in levels:
                raise UsageError(
                    "authority_levels.{}.escalate_to 指向不存在的层级「{}」"
                    "——升级路径断了，越权就无处可去".format(k, up))
        merged["authority_levels"] = levels
    return merged


def policy_level(pol, key):
    """取一个层级的权限定义；层级名不存在 → exit=2 并列出可选层级。"""
    lv = (pol.get("authority_levels") or {}).get(key)
    if not lv:
        raise UsageError("层级「{}」不在权限矩阵里。可选：{}".format(
            key, "、".join(pol.get("authority_levels") or {})))
    return lv


def policy_cap(pol, level_key):
    """本级的**单张工单累计**补偿上限（点）。"""
    return float(policy_level(pol, level_key).get("cap") or 0)


def policy_sla_minutes(pol, level_key, severity):
    """承诺时限（分钟）：**必须来自 policy**（闸门六的判据来源）。"""
    lv = policy_level(pol, level_key)
    sla = lv.get("sla_minutes") or {}
    if severity not in sla:
        raise UsageError("权限矩阵里没有 {} 对 {} 的承诺时限".format(level_key, severity))
    return float(sla[severity])


def policy_escalate_to(pol, level_key):
    """本级超权限时该升给谁。"""
    return str(policy_level(pol, level_key).get("escalate_to") or "")


def policy_compensation_keys(pol):
    return tuple(pol.get("compensation_types") or {})


def points_to_yuan(pol, pts):
    r = float(pol.get("points_per_yuan") or POINTS_PER_YUAN)
    return round(float(pts) / r, 4) if r else None


def fmt_points(pol, pts):
    """把点数打印成人看得懂的形式（带元折算）。"""
    v = float(pts or 0)
    # 兜底层级给的是「批不完」的大数，打 1e+08 既难看又没意义
    if v >= 1e7:
        return "不设上限"
    y = points_to_yuan(pol, v)
    if y is None:
        return "{:g} 点".format(v)
    return "{:g} 点 ≈ ¥{:g}".format(v, y)


# ===========================================================================
# 四个角色（本包的骨架）
#
# 【为什么这四个】客诉处置是一条**权限逐级收紧**的链：
#   接报要快（先接住、先定级），技术判断要准（定错了后面全错），
#   授权要守规矩（它手里有钱，最容易越权），复盘要防复发（否则同类工单无限来）。
#   四者目标函数不同：接报要"尽快定级"，技术要"定位真因"，
#   授权要"既让用户满意又不越权"，复盘要"让它别再发生"。
#
# 【谁有权限】只有**授权**这一席手里有权，而且被权限矩阵硬约束。
#   这是本包与所有内容类小组的结构性差别：那三个角色**没有花钱的权限**。
# ===========================================================================

ROLE_INFO = [
    {
        "key": "intake",
        "name": "接报",
        "objective": "用最快的时间把工单接住：它是什么类型、多严重、承诺多久回、影响多大",
        "deliverable": "工单卡：类型 / 等级（P0~P3）/ **承诺时限** / 影响面 / 一句话概述 / 用户诉求",
        "authority": "只有**定级权**。不能给任何补偿，也不能替用户下结论",
        "sees": "工单原文（用户提交的原始文字与时间）",
        "cannot_see": "（它是第一个角色，没有上游）",
    },
    {
        "key": "diagnose",
        "name": "技术判断",
        "objective": "定位真因并给出**可复现步骤**：是产品缺陷、用户误用、环境问题，还是证据不足",
        "deliverable": "判定 + 归因 + 可复现性 + 复现步骤 + 证据链 + 责任归属",
        "authority": "**无**。它只能说「是什么问题」，不能说「赔多少」",
        "sees": "工单原文 + 工单卡的**类型/等级/影响面**（不给接报的整套论述）",
        "cannot_see": "接报的自评、任何补偿口径与权限信息（免得它替授权做决定）",
    },
    {
        "key": "settle",
        "name": "授权",
        "objective": "在**权限矩阵之内**决定给什么补偿：补偿项、金额、口径、给用户的话术",
        "deliverable": "处置方案：是否补偿 / 补偿项（枚举内）/ 金额（点）/ 结论 / 话术 / 升级对象",
        "authority": "**受权限矩阵硬约束**。超权限必须升级，不许自作主张",
        "sees": "工单原文 + 工单卡 + 技术判定 + **本级权限额度**（它必须知道自己的额度）",
        "cannot_see": "其他层级同事的额度明细（只知道自己的额度与升给谁）",
    },
    {
        "key": "review",
        "name": "复盘",
        "objective": "让同类工单别再发生：根因、要不要改文档/改产品、同类预警",
        "deliverable": "复盘：根因（含引文）/ 改进项（改文档/改产品/改口径）/ 同类预警 / 责任部门 / 复发监控指标",
        "authority": "无。它不能改这次处置的金额，只能提改进项",
        "sees": "工单原文 + 工单卡 + 技术判定 + 处置方案（三份都在它手上）",
        "cannot_see": "各角色的自评与内部打分（只给产出物本身）",
    },
]
ROLE_BY_KEY = {r["key"]: r for r in ROLE_INFO}


def role_label(key):
    return (ROLE_BY_KEY.get(key) or {}).get("name") or key


# ===========================================================================
# 闸门一：合规（违禁词 + **承诺类话术**）
#
# 事故复盘（同族）：一刀切的违禁词表在客服场景会**大面积误报** ——
# 客服话术里"最迟 24 小时内回复""最高可申请 300 元"全是正常表述，
# 但它们都含「最X」。误报会让人把整个闸门关掉，那比漏报更糟。
# 所以口径与同族一致：**可枚举上下文豁免 + 句首不豁免**。
#
# 本包增补的重点是**承诺类话术**：客服最容易在气头上写出"保证解决""一定赔偿"
# "永久免费"这类**公司兜不住的承诺**。它不是"绝对化广告用语"，是**合同级承诺**。
# ===========================================================================

# 「最X」后面接可枚举的程度/比较词，且**不在句首** → 判为普通中文用法，不拦。
SUPERLATIVE_OK_AFTER = (
    "不同", "区别", "差异", "共同", "相同", "相似", "常见", "容易", "重要",
    "关键", "主要", "先", "后", "基本", "简单", "难", "麻烦", "省事", "常用",
    "合适", "适合", "保险", "稳妥", "低", "高", "多", "少", "大", "小", "早", "晚",
    "迟", "快", "慢", "长", "短", "近", "远", "新", "旧",
    # 客服场景的**时限口径**：这不是"最高级宣称"，是 SLA 表述。
    # 「最迟 24 小时」「最长 3 个工作日」在客服话术里到处都是，
    # 一刀切拦下就等于把客服话术整篇判死。
    "迟", "长", "短", "少", "晚", "多",
    # 内部测算/额度口径
    "高可", "低可", "高不", "多可", "少可", "大额", "小额",
)
SUPERLATIVE_OK_RE = re.compile(r"^\s*的?\s*(?:" + "|".join(SUPERLATIVE_OK_AFTER) + r")")

# ---------------------------------------------------------------------------
# SLA 时限表述的**独立豁免**（本包增补，且是一条真的判据 —— 不是凑数的表项）
#
# 事故复盘（本包自测用例逼出来的）：客服话术里最常见的一句是
#     「最迟 24 小时内回复」「最长 3 个工作日」「最快 2 小时出片」
# 它含「最X」，但**不是最高级商品宣称**，是**承诺时限**。
#
# 为什么不能只把「迟 / 长 / 短」加进上面那张表：那张表比的是「最X」**紧后面**的字，
# 而「最迟 24 小时」里「迟」后面跟的是空格和数字 —— 表里放「迟」永远匹配不上。
# 试过把「迟」写成「 迟」塞进表里，结果是正则回溯到零空格、在位置 0 上匹配那个
# 带前导空格的候选项，`m.group(0)` 就不再以「最」开头 → 被这道闸门自己的
# 「必须以最开头」守卫拒掉。所以它必须是一条**独立判据**，不能混进那张表。
#
# 代价（诚实说明）：只认「最迟/最长/最短/最快 + 数字 + 时间单位」这一种形态。
# 「最迟明天」「最迟下周一」这类**不带数字**的写法不豁免，会照拦 —— 宁可让人工
# 看一眼，也不要把「最早」「最新」这些真宣称放出去。
# ---------------------------------------------------------------------------
SLA_TIME_UNITS = ("秒", "分钟", "分", "小时", "个小时", "钟头", "工作日", "天",
                  "个工作日", "周", "个星期", "个星期天", "月", "个月", "季度", "年")
SLA_SUPERLATIVE_RE = re.compile(
    r"^最(?:迟|长|短|快|多|少)\s*\d+(?:\.\d+)?\s*(?:" + "|".join(SLA_TIME_UNITS) + r")")
_SENT_END_RE = re.compile(r"[\n。！？!?；;：:]\s*$")

# 「第一」的可枚举上下文豁免：长文里「第一年」「第一步」是**序数**，不是排他性宣称。
FIRST_ORDINAL_AFTER = (
    "次|年|天|步|个|条|款|批|周|月|季|轮|种|点|部|遍|章|节|课|集|届|期|流|层|类"
    "|句|段|行|件|桶|手|版|稿|封|笔|单|场|局|盘|组|队|线|环|圈|代|世|阶|时|印|梯|眼"
    "|时间|反应|现场"
)


# 「100%」后面的**指标名词**（真机第二次全跑抓到的假警报）：
#   「失败任务自动退点率 100%。」是**内部监控指标**（目标值），
#   不是对用户承诺「100% 有效」。判据是「100% + 指标名词」这个可枚举形态。
#   「100% 有效 / 100% 达标 / 100% 恢复」照拦 —— 那才是承诺。
METRIC_AFTER_100 = ("率", "比", "命中", "覆盖", "占比", "达成")
METRIC_100_RE = re.compile(r"^(?:\s|的)*(?:" + "|".join(METRIC_AFTER_100) + r")")
# 指标名词在数字**前面**的形态（真机实测就是这个形态：「退点率 100%」）：
#   取命中前 8 个字符，去掉空白与标点，看结尾是不是指标名词。
METRIC_BEFORE_100_RE = re.compile(
    r"(?:" + "|".join(METRIC_AFTER_100) + r")[\s，,、:：的]*$")

# 「第一」的**列举序号**判据（真机第二次全跑抓到的另一个假警报）：
#   话术写「现在给你两件事：第一，…… 第二，……」—— 这里的「第一」是列举，
#   不是「行业第一」。原判据只认名称后缀（第一年/第一步），认不出标点后缀。
#   所以补一条：命中处**后面是标点**，且**同一段里出现后续序号**（第二/第三…）
#   → 判为列举。两个条件缺一不可：`行业第一。` 虽然后缀也是标点，
#   但它所在段里不会有「第二」，所以照拦。
FIRST_PUNCT_RE = re.compile(r"^\s*[，,、：:。．.]")
NEXT_ORDINAL_RE = re.compile(r"第(?:二|三|四|五|六|七|八|九|十)")


def _percent_is_metric(text, m):
    """「100%」处在**指标口径**里 → 不拦。

    两种可枚举形态（任一即算）：
        A. 指标名词在前：「退点率 100%」「达成率 100%」「占比 100%」
        B. 指标名词在后：「100% 达成」「100% 覆盖」
    「100% 有效 / 100% 恢复 / 100% 保证」都不落在 A/B 里，照拦。
    """
    t = text or ""
    if METRIC_100_RE.match(t[m.end():]):
        return True
    return bool(METRIC_BEFORE_100_RE.search(t[max(0, m.start() - 8):m.start()]))


def _first_is_enumeration(text, m):
    """「第一」是列举序号而不是排他性宣称？"""
    t = text or ""
    if not FIRST_PUNCT_RE.match(t[m.end():]):
        return False
    # 同一段里必须有后续序号（第二/第三…）
    start = t.rfind("\n", 0, m.start()) + 1
    end = t.find("\n", m.end())
    if end < 0:
        end = len(t)
    return bool(NEXT_ORDINAL_RE.search(t[start:end]))


def _superlative_is_normal_usage(text, m):
    """「最X」后面接的是比较/程度词，**且不在句首** → 判为普通用法，不拦。

    两个条件缺一不可：后文落在豁免表里；命中处不在句首。
    句首的「最大区别是…」是标题式宣称，**照拦**。
    """
    if _percent_is_metric(text, m):
        return True
    if _first_is_enumeration(text, m):
        return True
    if not m.group(0).startswith("最"):
        return False
    before = (text or "")[:m.start()]
    if not before.strip() or _SENT_END_RE.search(before):
        return False                       # 句首 → 不豁免
    # SLA 时限口径优先判（判据形态与上面那张表完全不同，理由见 SLA_SUPERLATIVE_RE）
    if SLA_SUPERLATIVE_RE.match((text or "")[m.start():]):
        return True
    return bool(SUPERLATIVE_OK_RE.match((text or "")[m.end():]))


BANNED_PATTERNS = [
    (r"最(好|佳|优|低|便宜|快|强|大|高|先进|新|流行|受欢迎|划算|迟|长|短)", "高",
     "广告法第九条禁止「最高级」用语"),
    (r"全网(最低|最便宜|第一)|史上(最低|最便宜)|全国(最低|第一)", "高",
     "绝对化价格承诺，无法举证"),
    (r"第一(?!" + FIRST_ORDINAL_AFTER + r")", "高",
     "「第一」类排他性表述"),
    (r"排名第一|销量第一|口碑第一|行业第一|全国第一|全网第一|全球第一", "高",
     "「第一」类排他性表述"),
    (r"No\.?\s*1|TOP\s*1", "高", "「第一」类排他性表述"),
    (r"国家级|世界级|全球级|国际级", "高", "「国家级」等权威性词汇属明令禁止"),
    (r"100\s*%|百分之百|百分百", "高", "绝对化效果承诺"),
    (r"无法举证|不可举证|无从考证", "中", "无法举证的宣称"),
    (r"根治|治愈|痊愈|药到病除|包治|无副作用|零副作用", "高",
     "医疗功效宣称，非药品/医疗器械不得使用"),
    (r"零风险|稳赚|躺赚|包赚|稳赚不赔|一本万利|高回报", "高", "投资类收益承诺"),
    (r"央视(推荐|上榜)|国家(认证|认可)|权威认证|官方推荐|官方认证", "高",
     "不得虚构权威背书"),
    (r"点击链接|加微信|私信我|扫码(加|进)|微信号", "中", "站外导流，平台普遍限制"),
    (r"震惊|惊呆|不看后悔|错过再等一年|速看|删前必看", "中", "标题党式诱导"),

    # ---- 本包增补：**承诺类话术**（客服场景的头号风险，不是广告法问题，是合同风险）----
    (r"保证(解决|处理|满意|退款|赔偿|到账|修复|恢复|能用|可用|成功|通过)", "高",
     "承诺类话术：公司兜不住的合同级承诺，赔付与时限都不能这样写"),
    (r"一定(赔偿|退款|解决|到账|处理|恢复|满足|可以|能)", "高",
     "承诺类话术：把「一定」写进客服话术＝无条件担保"),
    (r"永久(免费|有效|可用|保用|服务)|终身(免费|保用|有效)", "高",
     "承诺类话术：无期限承诺，后续无法履约"),
    (r"无条件(退款|赔偿|退货|满足)|无论如何(都|也)(赔|退|给)", "高",
     "承诺类话术：放弃了责任认定的空间"),
    (r"绝不|永远不会|绝对不会|100% ?(解决|恢复|到账)", "高",
     "承诺类话术：绝对化保证"),
    (r"双倍(赔偿|退款|赔付)|三倍(赔偿|退款|赔付)", "中",
     "赔偿倍数需与实际政策一致，不得随口承诺"),
]

BANNED_RE = [(re.compile(p), lvl, why) for p, lvl, why in BANNED_PATTERNS]
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}


def compliance_scan(text, levels=None):
    """扫一遍违禁/承诺类表述，返回 (命中列表, 豁免列表)。被豁免的**不静默放过**。

    去重按**位置**做，不按词：`我们是销量第一。` 会同时被两条模式命中
    （重叠覆盖同一处文字），同一次出现只该报一条。
    """
    hits, exempted, seen = [], [], set()
    spans = []
    t = text or ""
    for rx, lvl, why in BANNED_RE:
        if levels is not None and lvl not in levels:
            continue
        for m in rx.finditer(t):
            if _superlative_is_normal_usage(t, m):
                exempted.append({"word": m.group(0), "level": lvl,
                                 "why_exempt": "「最X」后接可枚举的程度/时限词，且不在句首 "
                                               "→ 判为普通中文用法（客服的 SLA 口径），"
                                               "不是最高级商品宣称",
                                 "context": t[max(0, m.start() - 12):m.end() + 12]})
                continue
            word = m.group(0)
            key = (word, lvl)
            if key in seen:
                continue
            if any(m.start() < e and s < m.end() for s, e in spans):
                continue             # 与已报过的命中重叠 → 同一次出现，不重复报
            seen.add(key)
            spans.append((m.start(), m.end()))
            hits.append({"word": word, "level": lvl, "why": why,
                         "context": t[max(0, m.start() - 12):m.end() + 12]})
    hits.sort(key=lambda h: LEVEL_ORDER.get(h["level"], 9))
    return hits, exempted


# ---------------------------------------------------------------------------
# 「提到/引用」的语境排除（**只在内部说明/裁决文书侧用**）
#
# 事故复盘（同族 review-board 踩过两轮，结论直接沿用）：
#   1. **引用**：复盘会引工单里的问题表述（「『保证解决』是承诺，不能这么回」）
#   2. **提到**：复盘会写「明确禁止承诺赔偿」「不可能 100% 恢复」
#      —— 这是**在禁止它、在指出风险**，不是自己在做承诺
#
# ⚠️ **产出侧与材料侧口径分开，是本包的硬要求**：
#   · **材料侧**（用户提交的工单原文）：全档全查、**只报不拦**。
#     用户骂人、用户自己写"你们必须赔我 1000 块"，那是用户的话，不是我们的产出。
#     拦它等于"用户一生气就没法处理"，毫无意义。
#   · **面客字段**（送给用户的话术 `voice` / 短信 / 邮件）：**零豁免**。
#     这段字真的要发给用户，没有任何"引用/提到"的存在理由。
#   · **审类字段**（内部说明 / 升级理由 / 复盘）：开引用/提到排除，
#     被排除的**必须留下原因**，照样列在案上可复查。
# ---------------------------------------------------------------------------

META_CONTEXT_RE = re.compile(
    "禁止|严禁|不得|不许|不能|不可|避免|杜绝|防范|防止|违规|风险|涉嫌|属于|构成|"
    "无出处|无法举证|不可举证|举证|撤回|删除|删掉|去掉|不实|虚假|夸大|诱导|"
    "不构成|不算|不是|未|没|缺|整改|改为|改成|替换|风险点|红线|合规问题|"
    "承诺类|话术风险|不能这么写|不许写")
_SENT_BOUND = re.compile(r"[。！？!?；;\n]")
META_WINDOW = 24

# 「审类字段」的字段名特征：职责是**审/说明**，不是面客文案。
REVIEW_FIELD_LABELS = ("理由", "依据", "说明", "缺口", "待补", "升级", "复盘",
                       "根因", "改进", "预警", "责任", "风险", "内部",
                       "cannot", "note", "why", "escalate")


def _label_is_review(label):
    """这个字段是不是「审类字段」（内部说明，不是发给用户的字）？"""
    return any(x in (label or "") for x in REVIEW_FIELD_LABELS)


def _ctx_window(text, pos, width=META_WINDOW):
    """命中位置前后各 width 个字符（**不跨句末标点**）。

    为什么用"窗口"而不是"整句"：中文里逗号顿号极多，按标点切成小句会把
    「明确禁止承诺赔偿、不许写永久免费」切碎，标记词正好被切掉。
    也不跨句末标点：跨句取词会把上一句的"禁止"借给下一句的真承诺。
    """
    start = 0
    for m in _SENT_BOUND.finditer(text):
        if m.end() <= pos:
            start = m.end()
        else:
            break
    m = _SENT_BOUND.search(text, pos)
    end = m.start() if m else len(text)
    return text[max(start, pos - width):min(end, pos + width)]


def _scan_prose_with_context(prose, material, label=""):
    """审类字段扫描：高风险命中再做「引用 / 提到」两道排除，**被排除的留下原因**。

    返回 (fresh, quoted, mentioned, soft, exempted)。
    """
    hi_all, exempted = compliance_scan(prose, levels=("高",))
    mat_words = {h["word"] for h in compliance_scan(material or "")[0]}
    fresh, quoted, mentioned = [], [], []
    for h in hi_all:
        if h["word"] in mat_words:
            h = dict(h)
            h["not_counted_reason"] = ("该词在**工单原文**里已出现 → 判为引用材料/引述用户原话，"
                                       "不是处置方自己新做的承诺")
            quoted.append(h)
            continue
        pos = prose.find(h["word"])
        if pos < 0:
            fresh.append(h)
            continue
        ctx = _ctx_window(prose, pos)
        m = META_CONTEXT_RE.search(ctx)
        if m:
            h = dict(h)
            h["not_counted_reason"] = (
                "命中前后 {} 字内有「{}」这类标记词 → 判为**提到/在禁止**它，"
                "不是处置方自己在做承诺".format(META_WINDOW, m.group(0)))
            h["context_window"] = ctx[:60]
            mentioned.append(h)
        else:
            fresh.append(h)
    soft, _ = compliance_scan(prose, levels=("中", "低"))
    if label:
        for h in fresh:
            h["in"] = label
    return fresh, quoted, mentioned, soft, exempted


def compliance_scan_material(text):
    """**材料侧**（用户提交的工单原文）：全档全查，**只报不拦**。

    用户生气时写的"你们就是骗子""必须赔我 1000"是**用户的话**，
    不是我们的产出。拦它等于"用户一情绪激动就没法处理"。
    所以这里只把命中列出来供人工看，不改退出码。
    """
    hits, exempted = compliance_scan(text)
    return {"side": "material", "hits": hits, "exempted": exempted,
            "ok": not hits,
            "note": ("工单原文命中 {} 处违禁/承诺类表述：**只报不拦**"
                     "（那是用户说的话，不是我们要发出去的字）".format(len(hits))
                     if hits else "")}


def compliance_scan_voice(text, label):
    """**面客字段**（发给用户的话术）：全档全查，**一个豁免口子都不开**。

    这些字真的要发给用户，没有"引用"或"提到"的存在理由。
    """
    hits, exempted = compliance_scan(text)
    return {"side": "creator", "label": label, "hits": hits, "exempted": exempted,
            "ok": not hits,
            "why": ("{} 命中 {} 处违禁/承诺类表述".format(label, len(hits)) if hits else "")}


def scan_disposition_field(label, text, material):
    """扫一个处置产出字段：面客字段零豁免，审类字段开引用/提到排除。

    命中一律带上 `in`（字段名）与 `field_kind`：出问题时必须一眼看出**是哪一处的字**。
    """
    if not _label_is_review(label):
        r = compliance_scan_voice(text, label)
        for h in r["hits"]:
            h["in"] = label
            h["field_kind"] = "面客字段（零豁免）"
        return r["hits"], [], [], r["exempted"]
    fresh, quoted, mentioned, _soft, exempted = _scan_prose_with_context(
        text, material, label)
    for h in fresh:
        h["in"] = label
        h["field_kind"] = "审类字段（已开引用/提到排除后仍然命中）"
    for h in quoted + mentioned:
        h["in"] = label
    return fresh, quoted, mentioned, exempted


# ===========================================================================
# 闸门二：占位符残留
# 模板没替换干净的典型形态：`{}` / `[待填]` / `XXX` / `（此处省略）` / `TODO`。
# `[1]`（引用序号）、`[图 2]`（配图位）是**正常写法**，不按括号内容一刀切。
# ===========================================================================

PLACEHOLDER_PATTERNS = [
    # 双层/单层都必须**里面有内容**；空的 `{}` 一律放过（它是 json.dumps({}) 的正常产物）。
    # 代价（诚实说明）：`{{}}` / `{ }` 这种**没有内容的**占位符抓不到。
    (re.compile(r"\{\{\s*[\u4e00-\u9fffA-Za-z0-9_]+\s*\}\}"
                r"|\{\s*[\u4e00-\u9fffA-Za-z0-9_]+\s*\}"), "{}",
     "残留了模板占位符 `{}`，模板没被替换干净"),
    (re.compile(r"[\[【（(]\s*(待填|填空|待补充|待完善|待定)\s*[\]】）)]"), "[]",
     "残留了占位符 `[待填]`，模型给自己留的空档没补"),
    (re.compile(r"[\[【]\s*(略|此处省略)\s*[\]】]"), "[]",
     "残留了「此处省略」类占位"),
    (re.compile(r"[(（]\s*此处省略[^)）]{0,12}[)）]"), "（此处省略）",
     "残留了「（此处省略）」——该写的内容被省略了"),
    (re.compile(r"(?<![A-Za-z0-9])X{3,}(?![A-Za-z0-9])"), "XXX",
     "残留了占位符 `XXX`，忘了替换"),
    (re.compile(r"待补充|待完善|后续补充|此处略|TODO|TBD"), "待补充",
     "残留了「待补充」类字样，内容没写完"),
]


def placeholder_hits(text):
    """扫占位符残留，返回命中列表（可能为空）。"""
    hits = []
    t = text or ""
    for rx, label, why in PLACEHOLDER_PATTERNS:
        m = rx.search(t)
        if m:
            hits.append({"kind": label, "word": m.group(0)[:40], "why": why})
    return hits


# ===========================================================================
# 闸门三：照抄提示词示例（prompt_echo）
#
# 三条命中判据（任一即命中）：
#   exact    去掉标点后完全相同
#   jaccard  字符二元组 Jaccard ≥ ECHO_SIM（长度相当的同构改写）
#   contain  示例的二元组**覆盖度 ≥ ECHO_CONTAIN**（示例被夹带进更长的句子里）
#
# 【为什么必须有第三条】Jaccard 的分母是两份二元组的**并集**，产出越长，
# 示例那一侧被摊薄得越狠 —— 示例原样嵌进去也会掉到 0.75 以下侥幸放行。
#
# ⚠️ 【为什么第三条必须有适用窗口】覆盖度只看"示例被抄了多少"，不看产出有多长，
# 所以对**短示例**会饱和：示例归一后只有 3~5 字时，长文本被动凑齐两个二元组
# 就有 0.5 的覆盖度。所以 contain 只在**两个条件都满足**时适用：
#   1. 目标片段长度 ≤ 示例长度 × ECHO_CONTAIN_MAX_RATIO（长度比窗口）
#   2. 示例归一后长度 ≥ ECHO_CONTAIN_MIN_SAMPLE（二元组数量够用）
# 不适用的地方记进 `contain_skipped`，**不静默略过**。
# ===========================================================================

ECHO_SIM = 0.75
ECHO_CONTAIN = 0.60
ECHO_MIN_LEN_FLOOR = 6          # 长度守卫的绝对下限，防极短串的二元组噪声
ECHO_CONTAIN_MAX_RATIO = 3.0    # contain 适用窗口：目标长度 ≤ 示例长度 × 该系数
ECHO_CONTAIN_MIN_SAMPLE = 8     # contain 适用窗口：示例归一后至少这么长

# 提示词里出现过的**跨主题**示例（正常不该被抄）。
# 跨主题 = 与任何真实客诉工单都不搭（停车场道闸、健身房退款），
# 模型不会主动抄过去；万一抄了，prompt_echo 会兜住并让整份产出停下（退出码 3）。
PROMPT_SAMPLES = [
    "停车场道闸抬不起来，先看是不是车牌识别没读到",
    "健身房年卡退款要按剩余月份折算",
    "先确认是不是网络问题，再谈补偿",
]


def _norm_anchor(s):
    """归一化：只留中文、字母、数字，丢掉所有标点与空白。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def _echo_min_len(sample):
    """比对这个示例时的目标长度门槛：max(6, len(示例)//2)。**相对阈值**。

    绝对阈值（比如 12）在示例只有 15~17 字时占了示例长度的七成以上，
    会把「≤11 字的截断照抄」整档放过。
    """
    return max(ECHO_MIN_LEN_FLOOR, len(_norm_anchor(sample)) // 2)


def _bigrams(s):
    s = _norm_anchor(s)
    if len(s) < 2:
        return set(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _similarity(a, b):
    """字符二元组 Jaccard 相似度，0~1。"""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(len(ba | bb))


def _overlap(a, b):
    """较短一侧被另一侧覆盖的比例。用于"两条理由是不是同一句"。"""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / float(min(len(ba), len(bb)))


def prompt_echo(text, samples=None):
    """文本是否与提示词里的示例"抄得太近"。

    返回 (是否命中, 分数, 撞上的示例, 判据, 被窗口跳过的判据列表)。
    """
    target = _norm_anchor(text)
    if not target:
        return False, 0.0, "", "", []
    best_score, best_sample, best_rule = 0.0, "", ""
    skipped = []
    for s in (samples if samples is not None else PROMPT_SAMPLES):
        ns = _norm_anchor(s)
        if target == ns:
            return True, 1.0, s, "exact", skipped
        if len(target) < _echo_min_len(s):
            continue
        sim = _similarity(text, s)
        if sim >= ECHO_SIM and sim >= best_score:
            best_score, best_sample, best_rule = sim, s, "jaccard"
        # contain 的适用窗口：长度比 + 示例长度，两个都满足才用它
        if len(target) > ECHO_CONTAIN_MAX_RATIO * max(1, len(ns)):
            skipped.append({"rule": "contain",
                            "why": "目标长度 {} > 示例长度 {} × {}".format(
                                len(target), len(ns), ECHO_CONTAIN_MAX_RATIO)})
            continue
        if len(ns) < ECHO_CONTAIN_MIN_SAMPLE:
            skipped.append({"rule": "contain",
                            "why": "示例归一后仅 {} 字 < {}，二元组太少、覆盖度会饱和"
                                   .format(len(ns), ECHO_CONTAIN_MIN_SAMPLE)})
            continue
        base = _bigrams(s)
        contain = (len(_bigrams(text) & base) / float(len(base))) if base else 0.0
        if contain >= ECHO_CONTAIN and contain >= best_score:
            best_score, best_sample, best_rule = contain, s, "contain"
    if best_rule:
        return True, best_score, best_sample, best_rule, skipped
    return False, best_score, best_sample, "", skipped


# 拆句：中文句末标点 + 换行。用于**逐句**比对与逐句定位。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")


def split_sentences(text):
    """把正文拆成句子列表（保序、去空白项）。"""
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def split_paras(text):
    """把正文拆成段落列表。段落 = 一个或连续多个非空行。"""
    paras, cur = [], []
    for line in (text or "").splitlines():
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append("\n".join(cur))
            cur = []
    if cur:
        paras.append("\n".join(cur))
    return paras


def _dedupe_skips(skips):
    """把「contain 判据被适用窗口跳过」的记录按原因合并（一条产出会有上百次）。"""
    agg = {}
    for s in skips or []:
        key = s.get("why") or s.get("rule")
        agg[key] = agg.get(key, 0) + 1
    return [{"why": k, "times": v} for k, v in sorted(agg.items(), key=lambda x: -x[1])]


def prompt_echo_scan(text, samples=None, label="产出"):
    """在长文本里逐句找「照抄提示词示例」的地方，返回 (命中列表, 被跳过的窗口记录)。"""
    hits, skips = [], []
    whole_hit, score, sample, rule, sk = prompt_echo(text, samples)
    skips.extend(sk)
    if whole_hit and rule != "contain":
        hits.append({"segment": (text or "")[:40], "rule": rule, "sim": round(score, 3),
                     "sample": sample,
                     "why": ("与提示词示例去掉标点后完全相同（照抄示例）" if rule == "exact"
                             else "与提示词示例相似度 {:.2f}，属同构照抄".format(score))})
        return hits, skips
    for seg in split_sentences(text):
        hit, score, sample, rule, sk = prompt_echo(seg, samples)
        skips.extend(sk)
        if not hit:
            continue
        if rule == "contain":
            why = ("{}里的「{}」有 {:.0f}% 的内容来自提示词示例「{}」"
                   "（覆盖度 ≥ {:.2f} 即判照抄；Jaccard 会随句子变长被摊薄）"
                   .format(label, seg[:20], score * 100, sample[:24], ECHO_CONTAIN))
        elif rule == "exact":
            why = "{}里的「{}」与提示词示例去掉标点后完全相同（照抄示例）".format(label, seg[:20])
        else:
            why = "{}里的「{}」与提示词示例相似度 {:.2f}，属同构照抄".format(label, seg[:20], score)
        hits.append({"segment": seg[:40], "rule": rule, "sim": round(score, 3),
                     "sample": sample, "why": why})
        break                      # 一处命中足够拦截，不用把整篇列完
    return hits, skips


# ===========================================================================
# 闸门四：锚点校验（每条判定/处置必须引用**工单原文**，编造引文剔出）
#
# 一份客诉处置最没用的形态，是通篇"经核实属产品问题，已为用户申请补偿"：
# 经核实**是什么**？产品问题是**哪一处**？用户**原话是什么**？
# 所以本包不采信模型的引文，而是**本地校验**：它引的那句话在不在工单原文里？
#
# 三级递进：exact / substring / fuzzy（统计判据，高门槛）。
# 未锚定率 > ANCHOR_MAX_MISS → 判「定位失败」，压分 + 标红 + 退出码 3。
# ===========================================================================

ANCHOR_MIN_SUBSTR = 4     # 精确子串匹配的最低长度（低风险判据，门槛可以矮）
ANCHOR_MIN_CHARS = 8      # 模糊匹配的最低长度（二元组太少会虚高，门槛必须高）
ANCHOR_SIM = 0.55         # 模糊匹配阈值
ANCHOR_MAX_MISS = 0.40    # 未锚定率超过它就判「定位失败」

# 为什么两种匹配用**两个不同的长度门槛**：「引文恰好是某句的连续片段」是**精确**判断，
# 短一点也几乎不会误伤；而「最像的那一句」是**统计**判断，短串的二元组集合太小，
# 相似度会虚高。一个门槛管两件事，就会把"6 个字的真实引文被判成幻觉"。


def verify_anchor(quote, sentences, norms=None):
    """把引文锚定到目标文本的某一句话上。返回 (ok, rule, index)。"""
    q = _norm_anchor(quote)
    if not q:
        return False, "unverified", -1
    if norms is None:
        norms = [_norm_anchor(s) for s in sentences]
    for i, n in enumerate(norms):
        if n and n == q:
            return True, "exact", i
    if len(q) >= ANCHOR_MIN_SUBSTR:
        for i, n in enumerate(norms):
            if n and (q in n or n in q) and min(len(q), len(n)) >= ANCHOR_MIN_SUBSTR:
                return True, "substring", i
    best_i, best = -1, 0.0
    if len(q) >= ANCHOR_MIN_CHARS:
        for i, s in enumerate(sentences):
            sim = _similarity(quote, s)
            if sim > best:
                best_i, best = i, sim
        if best >= ANCHOR_SIM:
            return True, "fuzzy", best_i
    return False, "unverified", -1


def anchor_records(records, text, quote_field="quote", label=""):
    """给一批记录的引文做锚点校验，返回 (锚定成功的, 未锚定的, 统计)。

    锚定成功的那条会把引文**就地修正成工单原文里的真实句子**（`sentence` 字段）。
    """
    sents = split_sentences(text)
    norms = [_norm_anchor(s) for s in sents]
    ok_list, bad_list = [], []
    for it in records or []:
        if not isinstance(it, dict):
            continue
        quote = str(it.get(quote_field) or "").strip()
        good, rule, idx = verify_anchor(quote, sents, norms)
        item = dict(it)
        item["anchor_rule"] = rule
        if label:
            item.setdefault("in", label)
        if good:
            item["sentence"] = sents[idx]
            item["sent_no"] = idx + 1
            ok_list.append(item)
        else:
            item["why_unverified"] = ("引文在**工单原文**里找不到（归一化后不匹配任一整句，"
                                      "模糊相似度 < {:.2f}）——判为锚点幻觉，不作为交付内容"
                                      .format(ANCHOR_SIM))
            bad_list.append(item)
    total = len(ok_list) + len(bad_list)
    stat = {
        "ok": True, "total": total, "verified": len(ok_list), "unanchored": len(bad_list),
        "miss_rate": round(len(bad_list) / float(total), 3) if total else 0.0,
        "rules": {},
    }
    for it in ok_list:
        r = it.get("anchor_rule") or "-"
        stat["rules"][r] = stat["rules"].get(r, 0) + 1
    if total and stat["miss_rate"] > ANCHOR_MAX_MISS:
        stat["ok"] = False
        stat["why"] = ("{} 条判定/处置里 {} 条的引文在**工单原文**里找不到"
                       "（未锚定率 {:.0%} > {:.0%}）—— 模型在编引文，"
                       "这份处置的依据不可信".format(
                           total, len(bad_list), stat["miss_rate"], ANCHOR_MAX_MISS))
    return ok_list, bad_list, stat


# ===========================================================================
# 闸门五：**越权拦截**（本包核心）
#
# 三条判据，任一命中即拦（exit=3）：
#   5a **补偿项不在枚举里** —— 自创补偿（"送个定制玩偶"），不许
#   5b **金额超出本级权限** —— 一线上限 50 元却批了 200 元
#   5c **越权却没给升级对象** —— 拦下之后必须说清"升给谁"，否则这张工单挂死
#
# 【为什么是硬闸门而不是提示】内容类小组说错了顶多意见不合；本包说错了是
# **真的把钱批出去了**。所以本地算完直接拦，并且要求输出 escalate_to。
# ===========================================================================

def check_authority(settle, pol, severity=None, level_key=None, effective_cap=None):
    """越权校验。返回 (ok, issues, detail)。

    · `level_key` 不传就用处置方案自己声明的 `authority_level`
    · `effective_cap` 不传就用矩阵里那级的 cap
      （`--grant-cap` 只覆盖"本级实际可批额度"，**不绕过**矩阵的层级判定）
    """
    issues = []
    s = settle if isinstance(settle, dict) else {}
    level_key = level_key or str(s.get("authority_level") or DEFAULT_AUTHORITY)
    keys = policy_compensation_keys(pol)
    # 层级名不在矩阵里 → 这也是越权的一种（拿一个不存在的权限去批钱）
    lv = (pol.get("authority_levels") or {}).get(level_key)
    if not lv:
        issues.append({
            "code": "unknown_authority",
            "why": "处置方案声明的层级「{}」**不在权限矩阵里** —— 用一个不存在的权限批钱"
                   "就是越权".format(level_key),
        })
        return False, issues, {"level": level_key, "cap": None, "total": None}

    cap = float(effective_cap) if effective_cap is not None else float(lv.get("cap") or 0)
    up = str(lv.get("escalate_to") or "")

    items = s.get("compensation_items") or []
    if not isinstance(items, list):
        items = []
    total = 0.0
    norm_items = []
    for it in items:
        if not isinstance(it, dict):
            continue
        key = str(it.get("type") or "").strip()
        try:
            amt = float(it.get("amount_points") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        norm_items.append({"type": key, "amount_points": amt,
                           "label": (pol.get("compensation_types") or {}).get(key) or key})
        # 5a 补偿项不在枚举里 → 拦
        if key and key not in keys:
            issues.append({
                "code": "unknown_compensation",
                "why": "补偿项「{}」**不在枚举里**（枚举只有 {}）—— 不许自创补偿"
                       .format(key, "、".join(keys)),
                "item": key,
            })
        total += amt

    detail = {"level": level_key, "cap": cap, "total_points": round(total, 2),
              "escalate_to": up, "items": norm_items}

    needs = bool(s.get("needs_compensation"))
    claimed_escalate = bool(s.get("requires_escalation")) or \
        str(s.get("escalate_to") or "").strip() not in ("", "无", "none", "None")

    # 5b 金额超出本级权限 → 拦
    if total > cap + 1e-9:
        issues.append({
            "code": "over_authority",
            "why": "补偿合计 {} 超出「{}」的可批额度 {} —— **越权**。"
                   "超权限的补偿不许自作主张，必须升给「{}」".format(
                       fmt_points(pol, total), level_key, fmt_points(pol, cap),
                       up or "（本级已是最高层，需公司决策）"),
            "total_points": round(total, 2), "cap": cap,
        })
        # 5c 越权却没给升级对象 → 拦
        if not up:
            issues.append({
                "code": "no_escalation_path",
                "why": "越权了，但权限矩阵里「{}」没有再上一级可升 —— "
                       "这张工单必须走公司决策，不能就这么批出去".format(level_key),
            })
        elif not claimed_escalate:
            issues.append({
                "code": "missing_escalate_to",
                "why": "越权了却没在处置方案里写 `escalate_to`（应升给「{}」）"
                       "—— 拦下之后必须说清升给谁，否则这张工单挂死".format(up),
            })

    ok = not issues
    detail["needs_compensation"] = needs
    detail["authority_cap_points"] = cap
    detail["within_authority"] = (total <= cap + 1e-9)
    return ok, issues, detail


# ===========================================================================
# 闸门六：时效
#
# 两个判据：
#   6a **等级与时限的对应必须来自 policy**：工单卡里声明的 `sla_minutes`
#      必须等于矩阵里那级对那个等级的承诺时限。模型自己编一个"24 小时"→ 拦。
#   6b **P0/P1 未在承诺时限内给出处置 → 标红**。
#      时限基准是工单的创建时间 T0，判据是处置方案声明的处置时刻 T1。
#      超时不一定判死，但 **P0/P1 超时必须标红**（本包的硬要求）。
# ===========================================================================

# 处置时刻的解析容错：工单里的时间是人工写的，格式不会统一。
TIME_PATTERNS = [
    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日 %H:%M", "%Y年%m月%d日",
]
SLA_HARD_SEVERITIES = ("P0", "P1")     # 这两个等级超时必须标红


def parse_time(text):
    """尽力解析一个时间字符串，失败返回 None（**不猜**）。"""
    s = str(text or "").strip()
    if not s:
        return None
    s = s.replace("T", " ").strip()
    for fmt in TIME_PATTERNS:
        try:
            return time.strptime(s, fmt)
        except ValueError:
            continue
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if m:
        try:
            return time.strptime("{}-{}-{}".format(m.group(1), m.group(2), m.group(3)),
                                 "%Y-%m-%d")
        except ValueError:
            return None
    return None


def minutes_between(t0, t1):
    """两个 time.struct_time 之间相差多少分钟（t1 - t0）。"""
    if not t0 or not t1:
        return None
    a = time.mktime(t0)
    b = time.mktime(t1)
    return round((b - a) / 60.0, 1)


def check_sla(card, settle, pol, ticket_created=None):
    """时效校验。返回 (ok, issues, detail)。

    `ticket_created` 是工单原文里解析出来的 T0；取不到就用工单卡的 created_at。
    """
    issues = []
    c = card if isinstance(card, dict) else {}
    s = settle if isinstance(settle, dict) else {}
    severity = str(c.get("severity") or "").strip()
    level_key = str(s.get("authority_level") or c.get("handled_by") or DEFAULT_AUTHORITY)

    detail = {"severity": severity, "level": level_key, "source": "policy"}

    if severity not in SEVERITY_KEYS:
        issues.append({"code": "unknown_severity",
                       "why": "等级「{}」不是 P0~P3，无法判时效".format(severity)})
        return False, issues, detail
    if level_key not in (pol.get("authority_levels") or {}):
        issues.append({"code": "unknown_authority",
                       "why": "层级「{}」不在权限矩阵里，无法判时效".format(level_key)})
        return False, issues, detail

    want = policy_sla_minutes(pol, level_key, severity)
    declared = c.get("sla_minutes")
    try:
        declared = float(declared) if declared is not None else None
    except (TypeError, ValueError):
        declared = None
    detail["policy_sla_minutes"] = want
    detail["declared_sla_minutes"] = declared

    # 6a 承诺时限必须来自 policy
    if declared is None:
        issues.append({
            "code": "sla_missing",
            "why": "工单卡没写承诺时限 —— 定级不给时限等于没定级",
        })
    elif abs(declared - want) > 1e-9:
        issues.append({
            "code": "sla_not_from_policy",
            "why": "工单卡声明的承诺时限是 {:g} 分钟，但权限矩阵里「{}」对 {} "
                   "的承诺时限是 **{:g} 分钟** —— 等级与时限的对应必须来自 policy，"
                   "不许自己编一个时限".format(declared, level_key, severity, want),
            "declared": declared, "policy": want,
        })

    # 6b 是否在承诺时限内给出处置
    t0_str = ticket_created or c.get("created_at")
    t1_str = s.get("handled_at")
    t0, t1 = parse_time(t0_str), parse_time(t1_str)
    detail["ticket_created_at"] = str(t0_str or "")
    detail["handled_at"] = str(t1_str or "")
    elapsed = minutes_between(t0, t1)
    detail["elapsed_minutes"] = elapsed
    detail["sla_minutes_used"] = want

    if t0 is None or t1 is None:
        detail["timing_checked"] = False
        detail["timing_note"] = ("工单时间（{}）或处置时间（{}）解析不了，"
                                 "**未做超时判定**（不猜）".format(t0_str or "空", t1_str or "空"))
    else:
        detail["timing_checked"] = True
        over = elapsed is not None and elapsed > want + 1e-9
        detail["within_deadline"] = not over
        if over:
            hard = severity in SLA_HARD_SEVERITIES
            issues.append({
                "code": "sla_breach",
                "why": "**超时**：{} 用了 {:g} 分钟处置，承诺时限（{}，来自 policy）是 "
                       "{:g} 分钟，超出 {:g} 分钟{}".format(
                           severity, elapsed, level_key, want, round(elapsed - want, 1),
                           " —— P0/P1 超时**标红**" if hard else ""),
                "hard": hard, "elapsed": elapsed, "limit": want,
            })
    # 口径：出任何一条 issues 就算没过（超时也要拦，P0/P1 尤其）
    ok = not issues
    return ok, issues, detail


# ===========================================================================
# 闸门七：处置完整性
#
# 客服体系里最贵的两种"看起来处理了"：
#   7a 判"需要补偿"却没写补偿项 → 用户什么也没拿到，工单却被关了
#   7b 判"无需补偿"却没写理由 → 用户被拒了，但没人知道凭什么
# 再加一条：面客话术不能为空或超长（客服场景没人读 1000 字）。
# ===========================================================================

def check_settlement_complete(settle, pol):
    """处置完整性。返回 (ok, issues, detail)。"""
    issues = []
    s = settle if isinstance(settle, dict) else {}
    needs = bool(s.get("needs_compensation"))
    items = [it for it in (s.get("compensation_items") or []) if isinstance(it, dict)]
    reason = str(s.get("no_compensation_reason") or "").strip()
    voice = str(s.get("voice_to_user") or "").strip()
    concl = str(s.get("conclusion") or "").strip()

    # 7a 判"需要补偿"却没写补偿项
    if needs and not items:
        issues.append({
            "code": "missing_compensation_items",
            "why": "判定**需要补偿**，却没写任何补偿项 —— 用户什么也没拿到，"
                   "这张工单等于被关掉了",
        })
    # 7b 判"无需补偿"却没写理由
    if (not needs) and not reason:
        issues.append({
            "code": "missing_no_compensation_reason",
            "why": "判定**无需补偿**，却没写理由 —— 拒了用户，但没人知道凭什么",
        })
    # 结论必须是枚举里的档位
    if concl and concl not in DISPOSITION_CHOICES:
        issues.append({
            "code": "bad_conclusion",
            "why": "结论「{}」不在允许的档位里（{}）".format(
                concl, "、".join(DISPOSITION_CHOICES)),
        })
    if not concl:
        issues.append({"code": "missing_conclusion", "why": "处置方案没有结论"})
    # 面客话术
    if not voice:
        issues.append({"code": "missing_voice",
                       "why": "没有给用户的**话术** —— 处置方案没有这一步就落不了地"})
    elif len(voice) > VOICE_MAX_CHARS:
        issues.append({
            "code": "voice_too_long",
            "why": "面客话术 {} 字，超过 {} 字上限 —— 客服场景没人读这么长，"
                   "而且长文里最容易混进承诺类表述".format(len(voice), VOICE_MAX_CHARS),
        })

    detail = {"needs_compensation": needs, "items": len(items),
              "conclusion": concl, "voice_chars": len(voice),
              "voice_max_chars": VOICE_MAX_CHARS}
    return (not issues), issues, detail


# ===========================================================================
# 成本：token 标定 + 预算闸门
#
# 字符 → token 的标定比例（**是同族实测值**，不是厂商文档）：
CHARS_PER_TOKEN_IN = 1.61       # 输入侧沿用同族实测均值
TOKENS_PER_CHAR_OUT = 1.11      # 输出侧按「1 个原始字符 ≈ 多少 token」
# 平台口径：1 元 = 100 点（POINTS_PER_YUAN 已在权限矩阵那段定义）
# ===========================================================================

# 各角色一次调用的输出 token 经验值（用于报价）
ROLE_OUT_TOKENS = {"intake": 900, "diagnose": 1200, "settle": 1200, "review": 1400}
ROLE_SYSTEM_TOKENS = 300        # system + 提示词骨架的固定开销（粗略）


def estimate_tokens_in(text):
    """估输入 token（用**原始字符数**，含换行——换行也要花 token）。只用于预算。"""
    n = len(text or "")
    return max(1, int(round(n / CHARS_PER_TOKEN_IN))) if n else 0


def estimate_calls(raw, rounds=1):
    """一次处置的调用清单（用于报价，越清楚越好）。

    处置是**一条直线**（接报 → 技术判断 → 授权 → 复盘），没有"打回重跑"，
    所以默认就是 4 次调用；`rounds` 只是预留的余量倍数。
    """
    src = estimate_tokens_in(raw)
    rounds = max(1, int(rounds or 1))
    prev = 0
    calls = []
    for key, note in (("intake", "接报：分类 + 定级 + 承诺时限"),
                      ("diagnose", "技术判断：归因 + 可复现步骤 + 证据"),
                      ("settle", "授权：补偿项与金额（受权限矩阵约束）"),
                      ("review", "复盘：根因 + 改进项 + 同类预警")):
        calls.append({
            "stage": "{}（1 次）".format(role_label(key)),
            "calls": rounds,
            "tokens_in": (src + ROLE_SYSTEM_TOKENS + prev) * rounds,
            "tokens_out": ROLE_OUT_TOKENS[key] * rounds,
            "note": note,
        })
        prev += ROLE_OUT_TOKENS[key]
    return calls


def compute_cost(tokens_in, tokens_out, price_in=None, price_out=None):
    """算钱。单价单位：点 / 百万 token。缺单价时诚实返回 None，**不编价**。"""
    rec = {
        "tokens_in": int(tokens_in or 0),
        "tokens_out": int(tokens_out or 0),
        "price_in": price_in, "price_out": price_out,
        "unit": "点/百万 token",
        "points": None, "yuan": None, "notes": [],
    }
    if price_in is None or price_out is None:
        rec["notes"].append(
            "没给单价，无法给出金额：文本模型网关**不公布单价**（models 列表里也没有价格字段）。"
            "用 --price-in / --price-out 指定你账号的单价（点/百万 token）即可算出点数与金额。")
        return rec
    pts = (rec["tokens_in"] / 1e6) * float(price_in) + \
          (rec["tokens_out"] / 1e6) * float(price_out)
    rec["points"] = round(pts, 4)
    rec["yuan"] = round(pts / POINTS_PER_YUAN, 4)
    rec["notes"].append("按你给的单价线性折算；真实扣费以账户流水为准。")
    return rec


def fmt_cost(rec):
    if rec.get("points") is None:
        return "无法估算金额（{}）".format("；".join(rec.get("notes") or []))
    return "{} in + {} out tokens = {:g} 点 = ¥{:g}".format(
        rec["tokens_in"], rec["tokens_out"], rec["points"], rec["yuan"])


class CostTracker:
    """累计真实 usage（token），实时核预算。超了就地停（闸门：成本上限）。

    ⚠️ `--budget` 单位统一是**点**，与权限矩阵里的补偿金额同一单位（避免元/点混用）。
    """

    def __init__(self, budget=None, price_in=None, price_out=None):
        self.budget = budget
        self.price_in = price_in
        self.price_out = price_out
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.estimated_flags = 0
        self.stages = []

    @property
    def has_price(self):
        return self.price_in is not None and self.price_out is not None

    def add(self, usage, label=""):
        """记一次真实 usage；usage 缺失时**如实计数**并标注（不假装精确）。"""
        u = usage or {}
        p, c = u.get("prompt_tokens"), u.get("completion_tokens")
        if not isinstance(p, int) or not isinstance(c, int):
            p, c = 0, 0
            self.estimated_flags += 1
        self.calls += 1
        self.prompt_tokens += p
        self.completion_tokens += c
        self.stages.append({"stage": label, "prompt_tokens": p, "completion_tokens": c,
                            "usage_present": bool(u)})

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def points(self):
        if not self.has_price:
            return None
        return ((self.prompt_tokens / 1e6) * float(self.price_in)
                + (self.completion_tokens / 1e6) * float(self.price_out))

    def over_budget(self, extra_in=0, extra_out=0):
        """预算核验。给了单价才可能超（没单价时金额未知 → 只报 token）。"""
        if self.budget is None or not self.has_price:
            return False
        pts = (((self.prompt_tokens + extra_in) / 1e6) * float(self.price_in)
               + ((self.completion_tokens + extra_out) / 1e6) * float(self.price_out))
        return pts > self.budget

    def line(self, prefix="已用"):
        s = "{} {} 次文本调用 · token prompt={} completion={} total={}".format(
            prefix, self.calls, self.prompt_tokens, self.completion_tokens,
            self.total_tokens)
        if self.estimated_flags:
            s += "（含 {} 次没有真实 usage 的调用）".format(self.estimated_flags)
        if not self.has_price:
            s += " · 金额：网关不公布文本单价，**未折算**（要折算请传 --price-in / --price-out）"
        else:
            s += " · 估算 {:g} 点 ≈ ¥{:g}（按你填的单价）".format(
                self.points or 0, (self.points or 0) / POINTS_PER_YUAN)
        return s


def usage_dict(tracker, raw_usages=None):
    """把整轮的真实 usage 汇总成可展示的 dict（**只报 token，不编金额**）。"""
    d = {
        "calls": tracker.calls,
        "prompt_tokens": tracker.prompt_tokens,
        "completion_tokens": tracker.completion_tokens,
        "total_tokens": tracker.total_tokens,
        "estimated_flags": tracker.estimated_flags,
        "per_call": list(tracker.stages),
        "priced": tracker.has_price,
        "points": (None if tracker.points is None else round(tracker.points, 4)),
        "yuan": (None if tracker.points is None
                 else round(tracker.points / POINTS_PER_YUAN, 4)),
        "gateway_note": ("文本模型网关不公布单价，本包只报 token；"
                         "要折算金额请传 --price-in / --price-out。"),
    }
    if raw_usages:
        d["raw_usage"] = raw_usages
    return d


# ===========================================================================
# 断点续跑
#
# 事故复盘（同族踩过三次）：
#   · 内容截断没进 key   → 把 8000 字截成 4000 字重跑，key 没变，静默复用了旧产物
#   · 分辨率没进 key     → 换了档位重跑，命中的还是上一档的产物
#   · 死参数没进 key     → 参数调了但没生效，用户以为改过了
# 结论：**断点 key 必须含全部影响产出的维度**。
# 本包的做法更彻底：不看参数名，而是把「这一阶段的**全部输入**」序列化后取摘要。
# 本包影响产出的维度**特别多**：工单原文 + 等级 + 层级 + 权限矩阵 + 承诺时限。
# 少写任何一个（尤其是权限矩阵），续跑就会拿旧权限下的产物当已完成 —— 那可能是一次越权。
# ===========================================================================

STATE_NAME = "state.json"
STATE_VERSION = 1


def json_sha(obj):
    """一份 JSON 的稳定摘要（key 排序，保证同内容同 key）。"""
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True,
                   default=str).encode("utf-8")).hexdigest()[:16]


def text_sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def file_sha(path):
    p = Path(path)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def state_key(stage, **dims):
    """一个阶段的断点 key：口径版本 + 该阶段的**全部输入**。"""
    payload = {"v": STATE_VERSION, "crew": CREW_VERSION, "prompt": PROMPT_VERSION,
               "gate": GATE_VERSION, "stage": stage}
    payload.update(dims)
    return json_sha(payload)


def state_path(outdir):
    return Path(outdir) / STATE_NAME


def load_state(outdir):
    if not outdir:
        return {}
    p = state_path(outdir)
    if not p.is_file():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(obj, dict) or obj.get("state_version") != STATE_VERSION:
        return {}
    return obj.get("stages") or {}


def save_state(outdir, stages):
    if not outdir:
        return
    p = state_path(outdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"state_version": STATE_VERSION, "crew": CREW_VERSION,
                             "stages": stages}, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")


# ===========================================================================
# 闸门八：产出不许进包
# ===========================================================================

def pkg_dir():
    return Path(__file__).resolve().parent.parent


def ensure_outside_pkg(target, what="输出路径", example="support-crew-out"):
    """路径在包内 → 抛 PackagePathError（退出码 2）。"""
    root = pkg_dir()
    t = Path(target).resolve()
    try:
        t.relative_to(root)
    except ValueError:
        return
    raise PackagePathError(
        "{} {} 在 Skill 包内（{}）。包内只允许白名单文本后缀，**产出不许进包**"
        "（也不许有任何图片），请换到包外，例如 {}".format(
            what, t, root, Path(os.environ.get("TEMP") or ".") / example))


def check_cost_opts(a):
    """预算参数的合法性前置校验（零成本，不联网）。

    ⚠️ **每个会花钱的子命令的第一步都要调它**。事故复盘（同族踩过）：
    校验只写在 `cost` 子命令里，于是 `run --budget 0.5` 一路跑到报价之后才拦
    —— 自测就真花了钱。
    """
    budget = getattr(a, "budget", None)
    pin, pout = getattr(a, "price_in", None), getattr(a, "price_out", None)
    if budget is not None and budget <= 0:
        raise UsageError("--budget 必须大于 0（给的是 {}）。单位是**点**，不是元".format(budget))
    if (pin is None) != (pout is None):
        raise UsageError("--price-in 与 --price-out 要么都给、要么都不给：只给一个算不出金额。")
    if budget is not None and pin is None:
        sys.stderr.write(
            "提示：你给了 --budget {}（点）但没给单价。文本模型网关**不公布单价**，"
            "因此这次的金额无法折算、预算也无法核验；本包只报真实 token，"
            "不会编一个金额出来。要真正核预算请同时给 --price-in / --price-out。\n".format(budget))


def read_text(path, what="文件"):
    p = Path(path)
    if not p.is_file():
        raise UsageError("{}不存在：{}".format(what, path))
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError("{}不是 UTF-8 文本（{}）。请另存为 UTF-8。".format(what, exc))


def read_json(path, what="文件"):
    p = Path(path)
    if not p.is_file():
        raise UsageError("{}不存在：{}".format(what, path))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("{}不是合法 JSON（{}）：{}".format(what, exc, path))


def load_artifact(path, key, what="产物"):
    """读一份别的子命令落下的 JSON 产物，并把信封脱掉。

    `--json` 的输出外面包了 `{"ok": true, ...}`；顶层是数组时包成
    `{"ok": true, "data": [...]}`。下游子命令要的是**里面的那份产物**。
    """
    if not path:
        return None
    obj = read_json(path, what)
    if isinstance(obj, dict) and key in obj and isinstance(obj.get(key), (dict, list)):
        return obj[key]
    if isinstance(obj, dict) and set(obj.keys()) <= {"ok", "data"} and "data" in obj:
        return obj["data"]
    return obj


def write_text(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def write_json(path, obj):
    """JSON 产物一律不写 `ensure_ascii`（中文要能直接读），缩进 1。"""
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


# ===========================================================================
# 调用层：chat / parse_first_json
# ===========================================================================

class SupportError(a7w.A7wError):
    """本包的统一异常基类（退出码由子类给）。"""
    exit_code = EXIT_CALL


class UsageError(SupportError):
    exit_code = EXIT_USAGE


class PackagePathError(UsageError):
    """输出路径落在包内。"""


class GateFail(SupportError):
    exit_code = EXIT_GATE


class BudgetStop(SupportError):
    exit_code = EXIT_BUDGET


# 最近一次模型调用的 `finish_reason` 与 content 长度。
# **必须记它**：区分"该加大 max_tokens"（length）与"模型自己写错了 / 路上断了"
# （stop 或 None）的唯一依据。同族最初漏了它，才把坏 JSON 误归因成"固定长度截断"。
_LAST_FINISH = {"reason": None, "chars": None}


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.7,
         max_tokens=8192, key=None, timeout=300, json_mode=True):
    """调一次 POST /api/v1/chat/completions，返回 (正文, usage)。

    ⚠️ 本函数**故意不走** `a7w._request`：那边有个 `raw` 参数，是**原始请求体字节**
    （用于 multipart 上传），**不是**"要原始响应"。同族有人把它当成后者用过，
    结果崩在**钱已经扣之后**。本包一律自己发 urllib 请求，语义只有一种。

    为什么必须带退避重试：网关的 `upstream timeout` / HTTP 502 实测很常见，
    一次处置是四次连续调用，被一次抖动打断要重跑整轮，很亏。
    5xx 与网络类错误退避重试；4xx 是业务错误，直接报出来不浪费额度。
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
    payload = None
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
                sys.stderr.write("上游 {}，{}s 后重试 {}/{}…\n".format(
                    exc.code, 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
            try:
                err = json.loads(text)
            except ValueError:
                err = {}
            msg = ((err.get("error") or {}).get("message")
                   if isinstance(err.get("error"), dict) else None)
            msg = msg or err.get("msg") or text[:200]
            if exc.code == 401:
                raise SupportError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402:
                raise SupportError(
                    "点数不足（402）：{}  到 https://api.a7w.cn/ 充值后重试。".format(msg))
            if exc.code == 404:
                raise SupportError("模型不存在（404）：{}  "
                                   "用 `run.py models` 看平台在架的模型名。".format(msg))
            if exc.code in (429, 503) and attempt < CHAT_RETRIES - 1:
                last_exc = exc
                sys.stderr.write("限流/不可用 {}，{}s 后重试…\n".format(
                    exc.code, 3 * (attempt + 1)))
                time.sleep(3 * (attempt + 1))
                continue
            raise SupportError("调用失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < CHAT_RETRIES - 1:
                sys.stderr.write("网络抖动（{}），{}s 后重试 {}/{}…\n".format(
                    getattr(exc, "reason", exc), 3 * (attempt + 1),
                    attempt + 1, CHAT_RETRIES - 1))
                time.sleep(3 * (attempt + 1))
                continue
    else:
        raise SupportError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
            getattr(last_exc, "reason", last_exc), CHAT_RETRIES, CHAT_URL))

    # 成功响应**不带** `code` 字段；网关有时把它包一层 {"code":1,"data":{...}}，两种形态都认。
    # ⚠️ 别拿 `code` 判成败 —— 成功响应里根本没有它。
    data_obj = payload
    if isinstance(payload, dict) and "choices" not in payload \
            and isinstance(payload.get("data"), dict):
        data_obj = payload["data"]
    choices = (data_obj or {}).get("choices") or []
    if not choices:
        raise SupportError("模型没返回 choices：{}".format(
            json.dumps(payload, ensure_ascii=False)[:300]))
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    finish_reason = (choices[0] or {}).get("finish_reason")
    usage = (data_obj or {}).get("usage") or (payload or {}).get("usage") or {}
    _LAST_FINISH["reason"] = finish_reason
    _LAST_FINISH["chars"] = len(content)

    # ⚠️ 上游返回的 JSON **可能是坏的**，而且不只一种坏法：
    #   1. **输出被 max_tokens 截断** —— content 没有正常收尾，`finish_reason == "length"`
    #   2. **模型偶发吐出语法错的 JSON** —— content 有正常收尾，坏在中间某处，
    #      此时 `finish_reason == "stop"`：上游说它写完了，是它自己写错了
    #   3. **响应在传输层被切断** —— 同样没有正常收尾，但 finish_reason 可能仍报 stop
    #
    # ❌ **不要用 content 长度判断是哪一种**（同族的错误归因就是这么来的）。
    # ✅ 正确判据是**结构**（能不能按括号配平切出一个完整顶层值）+ `finish_reason`。
    if json_mode and content and not _json_is_complete(content):
        by_length = (finish_reason == "length")
        hint = ("输出被 max_tokens 截断（finish_reason=length）" if by_length else
                "上游返回的 JSON 坏了（finish_reason={!r}，**不是长度问题**）"
                .format(finish_reason))
        if attempt < CHAT_RETRIES - 1:
            sys.stderr.write("{}（收到 {} 字符），{}s 后重试 {}/{}…\n".format(
                hint, len(content), 3 * (attempt + 1), attempt + 1, CHAT_RETRIES - 1))
            time.sleep(3 * (attempt + 1))
            return chat(prompt, system=system, model=model, temperature=temperature,
                        max_tokens=max_tokens, key=key, timeout=timeout,
                        json_mode=json_mode)
        sys.stderr.write("!! 上游连续 {} 次返回坏 JSON（最后一次 {} 字符，"
                         "finish_reason={!r}）—— {}\n".format(
                             CHAT_RETRIES, len(content), finish_reason,
                             "加大 --max-tokens 才管用。" if by_length else
                             "**加大 --max-tokens 没用**：这是模型写错了或响应在路上"
                             "断了，换模型重试，或把工单拆短分几段跑。"))
    return content, usage


def _json_is_complete(text):
    """文本里有没有一个**括号配平**的 JSON 值（忽略字符串里的括号）。

    ⚠️ 这是**结构判据**，不是长度判据。配平配上不等于内容对（语法错也可能配上），
    所以它是"便宜的第一道筛"，最终仍要 `json.loads` / `raw_decode` 说了算。
    """
    if not text:
        return False
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    for cand in ([fenced.group(1)] if fenced else []) + [text]:
        start = None
        for i, ch in enumerate(cand):
            if ch in "{[":
                start = i
                break
        if start is None:
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(cand)):
            ch = cand[i]
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
                    return True
    return False


def _bracket_span(cand):
    """按括号配平切出第一个完整顶层值的结束位置；切不出来返回 None。"""
    start = None
    for i, ch in enumerate(cand):
        if ch in "{[":
            start = i
            break
    if start is None:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(cand)):
        ch = cand[i]
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
                return start, i + 1
    return None


def parse_first_json(text):
    """从模型输出里抠出第一个完整的 JSON 值。

    ⚠️ **必须优先取最外层括号配平的完整值**（同族真机实测踩到的一次，代价是一次调用）：
    外层 JSON **坏掉**时（被截断或语法错），如果逐个 `{` 试 `raw_decode`，
    循环会往后挪，**从内层对象的 `{` 解出一个小字典**，然后当成"模型的返回"交出去 ——
    上层报"返回里没有 X 字段"，而真因（外层坏了）被这个"成功解出一个对象"盖住。
    **报错指向了错误的方向**，这比坏响应本身更麻烦。
    所以：先按**括号配平**切出第一个完整的顶层值再解；切不出来才退回逐个 `{` 试。
    """
    if not text:
        raise SupportError("模型返回空内容")
    dec = json.JSONDecoder()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text)
    for cand in candidates:
        span = _bracket_span(cand)
        if span:
            start, end = span
            try:
                obj = json.loads(cand[start:end])
                if isinstance(obj, (dict, list)):
                    return obj
            except ValueError:
                pass
    # 退回：逐个 `{` / `[` 试 raw_decode（只在配平切不出来时走到这里）
    for cand in candidates:
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    raise SupportError("模型返回的不是合法 JSON：{}（finish_reason={!r}；"
                       "`length` 才表示被截断，其它值说明是模型写错了）"
                       .format(text[:300].replace("\n", " "), _LAST_FINISH.get("reason")))


# ===========================================================================
# 工单解析与定级
# ===========================================================================

TICKET_LABELS = {
    "ticket_id": ("工单号", "case_id", "id"),
    "created_at": ("提交时间", "创建时间", "工单时间"),
    "channel": ("渠道", "来源渠道", "入口"),
    "customer": ("客户", "用户", "客户名"),
    "order": ("订单", "订单号", "订单信息"),
    "amount": ("金额", "实付", "订单金额"),
}


def parse_ticket(text):
    """把工单原文解析成**结构化字段**（`键：值` 一行一条 + 自由正文）。

    为什么要解析：时效闸门需要 T0（提交时间），影响面与定级需要订单信息。
    解析不到就如实留空，**不猜**。
    """
    t = text or ""
    fields, body, seen = {}, [], set()
    for line in t.splitlines():
        s = line.strip()
        m = re.match(r"^([\u4e00-\u9fffA-Za-z_ ]{2,12})\s*[:：]\s*(.+)$", s)
        if not m:
            body.append(line)
            continue
        k, v = m.group(1).strip(), m.group(2).strip()
        key = None
        for canon, aliases in TICKET_LABELS.items():
            if k in aliases:
                key = canon
                break
        if key and key not in seen:
            fields[key] = v
            seen.add(key)
        else:
            body.append(line)
    return {"fields": fields, "body": "\n".join(body).strip(),
            "raw": t, "chars": len(t)}


def ticket_block(tk):
    """把工单喂给模型时的统一格式（保留原文，逐句可锚定）。"""
    f = tk.get("fields") or {}
    lines = []
    for k, label in (("ticket_id", "工单号"), ("created_at", "提交时间"),
                     ("channel", "渠道"), ("customer", "客户"),
                     ("order", "订单"), ("amount", "实付金额")):
        if f.get(k):
            lines.append("{}：{}".format(label, f[k]))
    if lines:
        lines.append("")
    return "\n".join(lines), "工单原文：\n" + (tk.get("raw") or "")


def ticket_created_at(tk):
    """工单的 T0：优先字段，其次从正文里找第一个时间。"""
    v = (tk.get("fields") or {}).get("created_at")
    if v and parse_time(v):
        return v
    m = re.search(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?"
                  r"(\s+\d{1,2}:\d{2}(:\d{2})?)?", tk.get("raw") or "")
    return m.group(0) if m else ""


def intake_policy_block(pol):
    """接报角色能看到的 policy 口径：类型、等级、时限。**不给权限额度**。"""
    lines = ["【类型枚举】"]
    for k, v in TICKET_TYPES.items():
        lines.append("  {} = {}（归口：{}）".format(k, v["label"], v["owner"]))
    lines.append("")
    lines.append("【等级与承诺时限】（时限来自权限矩阵，**不许自己编**）")
    for sev in SEVERITY_KEYS:
        s = SEVERITY_LEVELS[sev]
        lines.append("  {} = {}｜{}\n      影响面起点：{}｜承诺时限：{}".format(
            sev, s["label"], s["desc"], s["impact_floor"],
            "、".join("{} {} 分钟".format(lk, policy_sla_minutes(pol, lk, sev))
                     for lk in (pol.get("authority_levels") or {}))))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 提示词里的**跨主题示例**（正常不该被抄；登记进 PROMPT_SAMPLES 供 prompt_echo 兜）
# ---------------------------------------------------------------------------

SCHEMA_INTAKE = """{
  "ticket_type": "枚举内的一项",
  "severity": "P0|P1|P2|P3",
  "severity_reason": "为什么定这个级（引用工单原文）",
  "sla_minutes": 数字,
  "impact_scope": "影响面：几个人、影响什么、是否仍在持续",
  "summary": "一句话说清这张工单是什么事",
  "user_demand": "用户明确提出的诉求",
  "quotes": [{"quote": "工单原文里的一句真实句子"}],
  "pending_info": ["要用户补的材料，没有就给空数组"],
  "key_facts": ["从工单里抽出的客观事实，每条一个短句"]
}"""

SCHEMA_DIAGNOSE = """{
  "root_cause_class": "product_defect|user_misuse|environment_issue|insufficient_evidence",
  "responsibility": "责任归属：我们全责 / 用户侧 / 外部因素 / 待定",
  "reproducibility": "always|sometimes|once|not_attempted",
  "repro_steps": ["可复现步骤，按 1. 2. 3. 编号写"],
  "verdict": "技术结论，一两句，说清到底是什么问题",
  "evidence": [{"quote": "工单原文里的一句真实句子", "why": "它证明了什么"}],
  "ruled_out": ["排除掉的可能与排除理由"],
  "need_more": ["还需要什么信息才能定论，没有就给空数组"],
  "compensation_bias": "按归因，补偿口径应当偏紧还是偏松（只说倾向，不说金额）"
}"""

SCHEMA_SETTLE = """{
  "conclusion": "当场可批|需升级|不予补偿|待补证",
  "authority_level": "你当前所处的层级名（原样抄上下文里给的那个）",
  "needs_compensation": true,
  "compensation_items": [{"type": "枚举内的补偿项", "amount_points": 数字, "why": "凭什么给这一项"}],
  "total_points": 数字,
  "no_compensation_reason": "needs_compensation=false 时必填，否则给空串",
  "requires_escalation": false,
  "escalate_to": "需要升级时写升给谁；不需要就给空串",
  "escalate_reason": "为什么要升级（越权时必填）",
  "handled_at": "本次处置时刻，格式 YYYY-MM-DD HH:MM",
  "voice_to_user": "要发给用户的**话术**，口语化、不超过 600 字",
  "internal_note": "内部说明：口径依据、风险、后续动作",
  "quotes": [{"quote": "工单原文里的一句真实句子"}]
}"""

SCHEMA_REVIEW = """{
  "root_cause": "根因：为什么会发生这件事（不是复述现象）",
  "root_cause_evidence": [{"quote": "工单原文里的一句真实句子", "why": "它支撑了什么根因判断"}],
  "improvements": [{"kind": "doc|product|process|policy", "what": "要改什么", "owner": "归口部门"}],
  "similar_alert": "同类工单预警：还有哪类用户/哪种场景会遇到同一个问题",
  "recurrence_metric": "复发监控指标：看哪个数字能知道有没有防住",
  "doc_gap": "文档哪里没写清（没有就给空串）",
  "product_gap": "产品哪里该改（没有就给空串）",
  "quotes": [{"quote": "工单原文里的一句真实句子"}]
}"""


def build_intake_prompt(tk, pol):
    head, raw = ticket_block(tk)
    return (
        "你是**接报**角色：客诉处置的第一步，只做一件事 —— **用最快的时间把工单接住**。\n"
        "你要输出：类型、等级（P0~P3）、**承诺时限（分钟）**、影响面、用户诉求。\n\n"
        + intake_policy_block(pol) + "\n\n"
        "【硬规矩】\n"
        "1. `sla_minutes` **必须等于**上面矩阵里「你这一级 + 你定的等级」对应的分钟数。\n"
        "   自己编一个时限（比如顺手写 1440）会被本地闸门拦下。\n"
        "2. 定级要**引用工单原文**里支撑这个级别的那句话（放 `quotes`）。\n"
        "3. **不要给补偿、不要给金额**：接报没有花钱的权限。\n"
        "4. `impact_scope` 要能回答「几个人受影响、影响什么、是否仍在持续」。\n"
        "5. 工单里没写的信息，放 `pending_info`，**不要猜**。\n\n"
        "【示例格式（示例内容与本次工单无关，照抄会被拦）】\n"
        "  " + PROMPT_SAMPLES[0] + "\n"
        "  " + PROMPT_SAMPLES[1] + "\n\n"
        + head + raw + "\n\n"
        "只返回一个 JSON 对象，结构如下（字段名不许改）：\n" + SCHEMA_INTAKE
    )


def build_diagnose_prompt(tk, card, pol):
    head, raw = ticket_block(tk)
    c = card if isinstance(card, dict) else {}
    return (
        "你是**技术判断**角色：定位真因，并给出**可复现步骤**。\n"
        "你只能说「是什么问题」，**不能说「赔多少」** —— 补偿不在你的职责范围内。\n\n"
        "【归因枚举】\n"
        + "\n".join("  {} = {}｜{}｜补偿倾向：{}".format(
            k, v["label"], v["desc"], v["compensation_bias"])
            for k, v in ROOT_CAUSE_CLASSES.items()) + "\n\n"
        "【可复现性枚举】\n"
        + "\n".join("  {} = {}".format(k, v) for k, v in REPRODUCIBILITY.items()) + "\n\n"
        "【上游给你的工单卡（只有结构化字段，没有接报的论述）】\n"
        "  类型：{}｜等级：{}｜影响面：{}｜承诺时限：{} 分钟\n\n".format(
            c.get("ticket_type") or "（缺）", c.get("severity") or "（缺）",
            c.get("impact_scope") or "（缺）", c.get("sla_minutes") or "（缺）")
        + "【硬规矩】\n"
        "1. `root_cause_class` 必须是上面枚举里的一项。\n"
        "2. `repro_steps` 要**别人照着能重跑一遍**：写清前置条件、操作、预期与实际。\n"
        "   复现不了就老实写 `reproducibility` 并说明缺什么 —— 编一套步骤比说「复现不了」更糟。\n"
        "3. 每条 `evidence` 的 `quote` 必须是**工单原文里真实存在的句子**，编造引文会被剔出。\n"
        "4. `ruled_out` 写清你**排除掉**了哪些可能，以及凭什么排除。\n"
        "5. **不要写补偿金额、不要写补偿项**。\n\n"
        "【示例格式（示例内容与本次工单无关，照抄会被拦）】\n"
        "  " + PROMPT_SAMPLES[2] + "\n\n"
        + head + raw + "\n\n"
        "只返回一个 JSON 对象，结构如下（字段名不许改）：\n" + SCHEMA_DIAGNOSE
    )


def authority_block(pol, level_key, severity):
    """给授权角色的**本级**权限块：只知道自己的额度与升给谁。

    ⚠️ **故意不给它别级的额度明细** —— 知道自己"只能批 50"就够了，
    知道"主管能批 300"会诱导它去"帮用户想个办法绕过"。
    """
    lv = policy_level(pol, level_key)
    lines = [
        "【你当前的权限】",
        "  层级：{}".format(level_key),
        "  单张工单累计可批补偿上限：{}".format(fmt_points(pol, lv.get("cap"))),
        "  低于 {} 可自主批；达到或超过需上一级确认".format(
            fmt_points(pol, lv.get("need_below"))),
        "  超出上限时必须升级给：{}".format(lv.get("escalate_to") or "（本级已是最高层，需公司决策）"),
        "",
        "【可用的补偿项（枚举，**不许自创**）】",
    ]
    for k, v in COMPENSATION_TYPES.items():
        if k not in policy_compensation_keys(pol):
            continue
        lines.append("  {} = {}｜{}｜{}".format(k, v["label"], v["desc"], v["note"]))
    lines += [
        "",
        "【本级的承诺时限（分钟，来自权限矩阵）】",
        "  " + "｜".join("{} {}".format(s, policy_sla_minutes(pol, level_key, s))
                        for s in SEVERITY_KEYS),
    ]
    return "\n".join(lines)


def build_settle_prompt(tk, card, diag, pol, level_key):
    head, raw = ticket_block(tk)
    c = card if isinstance(card, dict) else {}
    d = diag if isinstance(diag, dict) else {}
    return (
        "你是**授权**角色：在**权限矩阵之内**决定给什么补偿，并写出给用户的话术。\n"
        "你手里有权，所以这是本流程里**最需要守规矩**的一步。\n\n"
        + authority_block(pol, level_key, c.get("severity") or "") + "\n\n"
        "【上游给你的工单卡】\n"
        "  类型：{}｜等级：{}｜影响面：{}｜承诺时限：{} 分钟\n\n".format(
            c.get("ticket_type") or "（缺）", c.get("severity") or "（缺）",
            c.get("impact_scope") or "（缺）", c.get("sla_minutes") or "（缺）")
        + "【上游给你的技术判定】\n"
        "  归因：{}｜责任：{}｜可复现性：{}\n  结论：{}\n\n".format(
            d.get("root_cause_class") or "（缺）", d.get("responsibility") or "（缺）",
            d.get("reproducibility") or "（缺）", d.get("verdict") or "（缺）")
        + "【硬规矩（越权会被本地闸门直接拦下，退出码 3）】\n"
        "1. `authority_level` 必须**原样**写上面给你的那个层级名。\n"
        "2. 每一项 `compensation_items[].type` 必须是上面枚举里的一项，**不许自创补偿**。\n"
        "3. `amount_points` 单位是**点**（1 元 = 100 点）。合计**不许超过你的上限**。\n"
        "   如果按责任该赔的金额**超过你的上限**：不要自己批，也不要拆成两笔绕过去 ——\n"
        "   老实设 `requires_escalation=true`、`escalate_to` 写上升给谁、"
        "   `conclusion` 写「需升级」，并把你**建议**的额度写在 `escalate_reason` 里。\n"
        "   这是**正确**的做法，不是失败。\n"
        "4. `needs_compensation=false` 时 `no_compensation_reason` **必填**（拒了用户要有理由）。\n"
        "5. `needs_compensation=true` 时 `compensation_items` **不许为空**。\n"
        "6. `voice_to_user` 是**要发给用户的字**：口语化、不超过 600 字、**不许承诺**\n"
        "   （「保证解决」「一定赔偿」「永久免费」这类会被合规闸门拦下）。\n"
        "   越权时话术要写「已为你申请，需要主管确认」，**不许写「已经批了」**。\n"
        "7. `quotes` 必须是**工单原文里真实存在的句子**。\n"
        "8. `handled_at` 写本次处置时刻（格式 YYYY-MM-DD HH:MM），时效闸门用它算有没有超时。\n\n"
        + head + raw + "\n\n"
        "只返回一个 JSON 对象，结构如下（字段名不许改）：\n" + SCHEMA_SETTLE
    )


def build_review_prompt(tk, card, diag, settle, pol):
    head, raw = ticket_block(tk)
    c = card if isinstance(card, dict) else {}
    d = diag if isinstance(diag, dict) else {}
    s = settle if isinstance(settle, dict) else {}
    return (
        "你是**复盘**角色：让同类工单**别再发生**。\n"
        "你不改这次处置的金额（那已经定了），你只回答「下次怎么不出现」。\n\n"
        "【上游给你的三份材料】\n"
        "  工单卡：类型 {}｜等级 {}｜影响面 {}\n"
        "  技术判定：归因 {}｜责任 {}｜可复现性 {}\n"
        "  处置方案：结论 {}｜补偿项 {} 项｜合计 {}｜升级给 {}\n\n".format(
            c.get("ticket_type") or "（缺）", c.get("severity") or "（缺）",
            c.get("impact_scope") or "（缺）",
            d.get("root_cause_class") or "（缺）", d.get("responsibility") or "（缺）",
            d.get("reproducibility") or "（缺）",
            s.get("conclusion") or "（缺）",
            len(s.get("compensation_items") or []),
            s.get("total_points") or s.get("total") or 0,
            s.get("escalate_to") or "（未升级）")
        + "【硬规矩】\n"
        "1. `root_cause` 是**根因**，不是复述现象（「用户任务失败了」不是根因）。\n"
        "2. `improvements` 每项要写清 `kind`（doc / product / process / policy）、"
        "**改什么**、**谁改**。至少给一条。\n"
        "3. `similar_alert` 要具体到**哪类用户、哪种场景**会遇到同一个问题。\n"
        "4. `recurrence_metric` 要是一个**能看的数字**（不是「加强监控」）。\n"
        "5. 每条 `quotes` 的 `quote` 必须是**工单原文里真实存在的句子**，编造会被剔出。\n"
        "6. 归因是「用户误用」时，也要检查**文档是不是没写清**（`doc_gap`）—— \n"
        "   很多「用户误用」其实是文档没写好，那仍然是我们的问题。\n\n"
        + head + raw + "\n\n"
        "只返回一个 JSON 对象，结构如下（字段名不许改）：\n" + SCHEMA_REVIEW
    )


# ===========================================================================
# 产出校验与归一化
#
# 模型给的 JSON 不能直接信：枚举可能越界、数字可能是字符串、必填可能是空。
# 归一化**不静默修补**：修了什么、默认了什么，都记进 `normalized` 供人复查。
# ===========================================================================

def _as_str(v, default=""):
    if v is None:
        return default
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _as_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _records_with_quote(obj, keys):
    """从若干可能的字段里收集所有带 `quote` 的记录（锚点校验的输入）。"""
    out = []
    for k in keys:
        for it in _as_list(obj.get(k)):
            if isinstance(it, dict) and _as_str(it.get("quote")):
                out.append(dict(it, _from=k))
            elif isinstance(it, str) and it.strip():
                out.append({"quote": it.strip(), "_from": k})
    return out


def normalize_intake(raw, pol, level_key):
    """接报产出的归一化 + 枚举校验。"""
    o = raw if isinstance(raw, dict) else {}
    notes = []
    tt = _as_str(o.get("ticket_type"))
    if tt not in TICKET_TYPE_KEYS:
        notes.append("ticket_type「{}」不在枚举里 → 归为 consult".format(tt or "空"))
        tt = "consult"
    sev = _as_str(o.get("severity")).upper()
    if sev not in SEVERITY_KEYS:
        notes.append("severity「{}」不是 P0~P3 → 归为 P2".format(sev or "空"))
        sev = "P2"
    want_sla = policy_sla_minutes(pol, level_key, sev)
    sla = o.get("sla_minutes")
    try:
        sla = float(sla) if sla is not None else None
    except (TypeError, ValueError):
        sla = None
    if sla is None or abs(sla - want_sla) > 1e-9:
        notes.append("sla_minutes「{}」与权限矩阵口径（{} 分钟）不一致 → "
                     "**按 policy 为准**，闸门会拦下这次不一致".format(
                         o.get("sla_minutes"), want_sla))
    return {
        "ticket_type": tt,
        "ticket_type_label": TICKET_TYPES[tt]["label"],
        "type_owner": TICKET_TYPES[tt]["owner"],
        "severity": sev,
        "severity_label": SEVERITY_LEVELS[sev]["label"],
        "severity_reason": _as_str(o.get("severity_reason")),
        "sla_minutes": sla,
        "sla_minutes_policy": want_sla,
        "sla_source": "policy",
        "handled_by": level_key,
        "impact_scope": _as_str(o.get("impact_scope")),
        "summary": _as_str(o.get("summary")),
        "user_demand": _as_str(o.get("user_demand")),
        "key_facts": [_as_str(x) for x in _as_list(o.get("key_facts")) if _as_str(x)],
        "pending_info": [_as_str(x) for x in _as_list(o.get("pending_info")) if _as_str(x)],
        "created_at": _as_str(o.get("created_at")),
        "quotes": _records_with_quote(o, ("quotes",)),
        "normalized": notes,
    }


def normalize_diagnose(raw, pol):
    """技术判断产出的归一化 + 枚举校验。"""
    o = raw if isinstance(raw, dict) else {}
    notes = []
    rc = _as_str(o.get("root_cause_class"))
    if rc not in ROOT_CAUSE_KEYS:
        notes.append("root_cause_class「{}」不在枚举里 → 归为 insufficient_evidence"
                     .format(rc or "空"))
        rc = "insufficient_evidence"
    rp = _as_str(o.get("reproducibility"))
    if rp not in REPRO_KEYS:
        notes.append("reproducibility「{}」不在枚举里 → 归为 not_attempted".format(rp or "空"))
        rp = "not_attempted"
    steps = [_as_str(x) for x in _as_list(o.get("repro_steps")) if _as_str(x)]
    return {
        "root_cause_class": rc,
        "root_cause_label": ROOT_CAUSE_CLASSES[rc]["label"],
        "responsibility": _as_str(o.get("responsibility"))
                          or ROOT_CAUSE_CLASSES[rc]["responsibility"],
        "reproducibility": rp,
        "reproducibility_label": REPRODUCIBILITY[rp],
        "repro_steps": steps,
        "verdict": _as_str(o.get("verdict")),
        "evidence": _records_with_quote(o, ("evidence",)),
        "ruled_out": [_as_str(x) for x in _as_list(o.get("ruled_out")) if _as_str(x)],
        "need_more": [_as_str(x) for x in _as_list(o.get("need_more")) if _as_str(x)],
        "compensation_bias": _as_str(o.get("compensation_bias")),
        "quotes": _records_with_quote(o, ("quotes",)),
        "normalized": notes,
    }


def normalize_settle(raw, pol, level_key):
    """授权产出的归一化。**金额与补偿项在这里不改语义，越权校验原样吃它**。"""
    o = raw if isinstance(raw, dict) else {}
    notes = []
    concl = _as_str(o.get("conclusion"))
    if concl not in DISPOSITION_CHOICES:
        notes.append("conclusion「{}」不在允许档位里 → 原样保留，闸门会拦".format(concl or "空"))
    declare_level = _as_str(o.get("authority_level")) or level_key
    if declare_level != level_key:
        notes.append("authority_level「{}」与本次运行层级「{}」不一致 → "
                     "**越权校验用声明值**（拿一个不是自己的权限批钱就是越权）"
                     .format(declare_level, level_key))
    items = []
    for it in _as_list(o.get("compensation_items")):
        if isinstance(it, dict):
            items.append({
                "type": _as_str(it.get("type")),
                "amount_points": _as_float(it.get("amount_points") or it.get("amount")),
                "why": _as_str(it.get("why")),
            })
    total = _as_float(o.get("total_points"), sum(i["amount_points"] for i in items))
    return {
        "conclusion": concl,
        "authority_level": declare_level,
        "needs_compensation": bool(o.get("needs_compensation")),
        "compensation_items": items,
        "total_points": round(total, 2),
        "no_compensation_reason": _as_str(o.get("no_compensation_reason")),
        "requires_escalation": bool(o.get("requires_escalation")),
        "escalate_to": _as_str(o.get("escalate_to")),
        "escalate_reason": _as_str(o.get("escalate_reason")),
        "handled_at": _as_str(o.get("handled_at")),
        "voice_to_user": _as_str(o.get("voice_to_user")),
        "internal_note": _as_str(o.get("internal_note")),
        "quotes": _records_with_quote(o, ("quotes",)),
        "normalized": notes,
    }


def normalize_review(raw, pol):
    """复盘产出的归一化 + 改进项 kind 枚举校验。"""
    o = raw if isinstance(raw, dict) else {}
    notes = []
    imps = []
    for it in _as_list(o.get("improvements")):
        if not isinstance(it, dict):
            it = {"what": _as_str(it)}
        kind = _as_str(it.get("kind")).lower()
        if kind not in ("doc", "product", "process", "policy"):
            if kind:
                notes.append("improvements.kind「{}」不在 doc/product/process/policy 里 → "
                             "归为 process".format(kind))
            kind = "process"
        imps.append({"kind": kind, "what": _as_str(it.get("what")),
                     "owner": _as_str(it.get("owner")) or "待指派"})
    imps = [i for i in imps if i["what"]]
    return {
        "root_cause": _as_str(o.get("root_cause")),
        "root_cause_evidence": _records_with_quote(o, ("root_cause_evidence",)),
        "improvements": imps,
        "similar_alert": _as_str(o.get("similar_alert")),
        "recurrence_metric": _as_str(o.get("recurrence_metric")),
        "doc_gap": _as_str(o.get("doc_gap")),
        "product_gap": _as_str(o.get("product_gap")),
        "quotes": _records_with_quote(o, ("quotes",)),
        "normalized": notes,
    }


# ===========================================================================
# 闸门总评估（本地、确定性）
# ===========================================================================

GATE_CATALOG = (
    ("compliance", "闸门一 · 合规（违禁词 + 承诺类话术）"),
    ("placeholder", "闸门二 · 占位符残留"),
    ("prompt_echo", "闸门三 · 照抄提示词示例"),
    ("anchor", "闸门四 · 锚点到工单原文"),
    ("authority", "闸门五 · 越权拦截（本包核心）"),
    ("sla", "闸门六 · 时效"),
    ("complete", "闸门七 · 处置完整性"),
)
GATE_KEYS = tuple(k for k, _ in GATE_CATALOG)


def _collect_texts(card, diag, settle, review):
    """产出侧文本清单：`(side, label, text)`。

    side 取 `material` / `creator`（面客，零豁免）/ `review`（审类，开排除）。
    ⚠️ **面客与审类分开是本包的硬要求**：`voice_to_user` 是发给用户的字，
    零豁免；`internal_note` / `escalate_reason` / 复盘是内部说明，开排除。
    """
    specs = []
    c = card if isinstance(card, dict) else {}
    d = diag if isinstance(diag, dict) else {}
    s = settle if isinstance(settle, dict) else {}
    v = review if isinstance(review, dict) else {}

    for label, text in (("工单卡·概述", c.get("summary")),
                        ("工单卡·定级理由", c.get("severity_reason")),
                        ("工单卡·影响面", c.get("impact_scope")),
                        ("工单卡·用户诉求", c.get("user_demand"))):
        specs.append(("creator", label, _as_str(text)))
    for i, x in enumerate(_as_list(c.get("key_facts")), 1):
        specs.append(("creator", "工单卡·事实{}".format(i), _as_str(x)))

    specs.append(("creator", "技术判定·结论", _as_str(d.get("verdict"))))
    for i, x in enumerate(_as_list(d.get("repro_steps")), 1):
        specs.append(("creator", "技术判定·复现步骤{}".format(i), _as_str(x)))
    for i, x in enumerate(_as_list(d.get("ruled_out")), 1):
        specs.append(("review", "技术判定·排除{}".format(i), _as_str(x)))
    specs.append(("review", "技术判定·补偿倾向", _as_str(d.get("compensation_bias"))))

    # ⚠️ 面客字段：零豁免
    specs.append(("creator", "处置·给用户的话术", _as_str(s.get("voice_to_user"))))
    # 审类字段
    specs.append(("review", "处置·无需补偿理由", _as_str(s.get("no_compensation_reason"))))
    specs.append(("review", "处置·升级理由", _as_str(s.get("escalate_reason"))))
    specs.append(("review", "处置·内部说明", _as_str(s.get("internal_note"))))
    for i, it in enumerate(_as_list(s.get("compensation_items")), 1):
        if isinstance(it, dict):
            specs.append(("review", "处置·补偿项{}理由".format(i), _as_str(it.get("why"))))

    specs.append(("review", "复盘·根因", _as_str(v.get("root_cause"))))
    specs.append(("review", "复盘·同类预警", _as_str(v.get("similar_alert"))))
    specs.append(("review", "复盘·文档缺口", _as_str(v.get("doc_gap"))))
    specs.append(("review", "复盘·产品缺口", _as_str(v.get("product_gap"))))
    specs.append(("review", "复盘·监控指标", _as_str(v.get("recurrence_metric"))))
    for i, it in enumerate(_as_list(v.get("improvements")), 1):
        if isinstance(it, dict):
            specs.append(("review", "复盘·改进项{}".format(i), _as_str(it.get("what"))))
    return specs


def _compliance_gate(specs, material_text):
    """`specs` = [(side, label, text)]；side 取 material / creator / review。

    · **material**（用户提交的工单原文）：全档全查；命中**只报不拦**。
    · **creator**（面客字段，真的发给用户）：零豁免。
    · **review**（内部说明/复盘）：高风险 + 引用/提到排除。

    【材料侧为什么不拦】工单是**用户写的字**：用户生气时会写"你们就是骗子"
    "必须赔我 1000"，那是用户的诉求表达。如果因为用户话难听就把整张工单判死，
    这闸门永远过不去 —— 而它恰恰是**唯一把事情说清楚的那份材料**。
    """
    fresh, quoted, mentioned, soft, exempted = [], [], [], [], []
    material_hits = []
    for side, label, text in specs:
        if not str(text or "").strip():
            continue
        if side == "material":
            r = compliance_scan_material(text)
            material_hits.extend([dict(h, side="material", in_field=label)
                                  for h in r["hits"]])
            exempted.extend(r["exempted"])
        elif side == "review":
            f, q, m, s, ex = _scan_prose_with_context(text, material_text, label)
            for h in f:
                h["field_kind"] = "审类字段（已开引用/提到排除后仍然命中）"
            fresh.extend(f)
            quoted.extend(q)
            mentioned.extend(m)
            soft.extend(s)
            exempted.extend(ex)
        else:
            f, q, m, ex = scan_disposition_field(label, text, material_text)
            fresh.extend(f)
            quoted.extend(q)
            mentioned.extend(m)
            exempted.extend(ex)
    return {
        "ok": not fresh,
        "hits": fresh,
        "material_hits": material_hits,
        "material_note": ("工单原文命中 {} 处违禁/承诺类表述：**只报不拦**"
                          "（那是用户写的字，不是我们要发出去的字）"
                          .format(len(material_hits)) if material_hits else ""),
        "quoted_from_material": quoted,
        "mentioned_as_warning": mentioned,
        "contextual_only": soft,
        "exempted": exempted,
        "why": ("产出侧命中 {} 处违禁/承诺类表述".format(len(fresh)) if fresh else ""),
    }


def evaluate_gates(*, material_text, card=None, diag=None, settle=None, review=None,
                   pol=None, anchors=None, level_key=None, effective_cap=None,
                   ticket_created=None, severity=None):
    """跑全部**本地**闸门，返回结构化 gates dict。

    每一项的形态都是 `{"ok": bool, ...}`；除此之外还带
    `quoted_from_material` / `mentioned_as_warning` / `skipped_windows`
    —— **被排除的不静默丢弃**。
    """
    pol = pol or default_policy()
    specs = [("material", "工单原文", material_text)]
    specs.extend(_collect_texts(card, diag, settle, review))

    g = {}
    g["compliance"] = _compliance_gate(specs, material_text)

    ph = []
    for side, label, text in specs:
        for h in placeholder_hits(text):
            ph.append(dict(h, **{"in": label, "side": side}))
    g["placeholder"] = {"ok": not ph, "hits": ph,
                        "why": ("残留 {} 处占位符".format(len(ph)) if ph else "")}

    echo, skips = [], []
    for side, label, text in specs:
        if side == "material":
            continue
        hits, sk = prompt_echo_scan(text, label=label)
        skips.extend(sk)
        echo.extend(hits)
    g["prompt_echo"] = {"ok": not echo, "hits": echo, "samples": list(PROMPT_SAMPLES),
                        "contain_window": {"max_ratio": ECHO_CONTAIN_MAX_RATIO,
                                           "min_sample_chars": ECHO_CONTAIN_MIN_SAMPLE},
                        "skipped_windows": _dedupe_skips(skips),
                        "why": ("命中 {} 处照抄提示词示例".format(len(echo)) if echo else "")}

    if anchors is not None:
        g["anchor"] = anchors

    if settle is not None:
        # ⚠️ `effective_cap` 必须真的传进去：`--grant-cap` 收窄的是**本级额度**，
        # 只在 run 里生效、单跑 settle 时静默无效，就是同族踩过的"死参数"。
        ok, issues, detail = check_authority(settle, pol, severity=severity,
                                             level_key=level_key,
                                             effective_cap=effective_cap)
        g["authority"] = {"ok": ok, "issues": issues, "detail": detail,
                          "why": "；".join(i.get("why") or "" for i in issues)}

    if card is not None:
        ok, issues, detail = check_sla(card, settle or {}, pol,
                                       ticket_created=ticket_created)
        g["sla"] = {"ok": ok, "issues": issues, "detail": detail,
                    "why": "；".join(i.get("why") or "" for i in issues)}

    if settle is not None:
        ok, issues, detail = check_settlement_complete(settle, pol)
        g["complete"] = {"ok": ok, "issues": issues, "detail": detail,
                         "why": "；".join(i.get("why") or "" for i in issues)}
    return g


def gate_hits(gates):
    """列出没过的闸门（按 GATE_KEYS 的顺序），返回 [(key, obj)]。"""
    out = []
    for k in GATE_KEYS:
        v = gates.get(k)
        if v and not v.get("ok", True):
            out.append((k, v))
    return out


def gate_failed(gates):
    return bool(gate_hits(gates))


# 本地确定性压分：越权/超时的峰值由本地定，模型给多高都压下来。
DIMENSION_KEYS = ("accuracy", "authority", "timeliness", "actionability", "evidence")


def apply_local_caps(dims, gates):
    """本地压分。返回 (dims, deductions)。

    `authority` 这一维是**本包特有**的：越权直接封 0 分 —— 不是"扣分"，
    是这一单的处置**不成立**（钱批错比话说错严重得多）。
    """
    dims = dict(dims)
    ded = []
    a = gates.get("authority") or {}
    if a and not a.get("ok", True):
        codes = [i.get("code") for i in (a.get("issues") or [])]
        if "over_authority" in codes or "unknown_compensation" in codes:
            cap = 0
        else:
            cap = 3
        if dims.get("authority", 10) > cap:
            ded.append({"kind": "authority", "dim": "authority",
                        "from": dims.get("authority"), "to": cap,
                        "why": "越权（{}）→ 权限分封顶 {}".format(
                            "、".join(codes) or "未说明", cap)})
            dims["authority"] = cap
    s = gates.get("sla") or {}
    if s and not s.get("ok", True):
        hard = any(i.get("hard") for i in (s.get("issues") or []))
        cap = 2 if hard else 5
        if dims.get("timeliness", 10) > cap:
            ded.append({"kind": "sla", "dim": "timeliness",
                        "from": dims.get("timeliness"), "to": cap,
                        "why": "{} → 时效分封顶 {}".format(
                            "、".join(i.get("code") or "?" for i in (s.get("issues") or [])),
                            cap)})
            dims["timeliness"] = cap
    c = gates.get("complete") or {}
    if c and not c.get("ok", True):
        if dims.get("actionability", 10) > 4:
            ded.append({"kind": "complete", "dim": "actionability",
                        "from": dims.get("actionability"), "to": 4,
                        "why": "处置不完整（{}）→ 可执行分封顶 4".format(
                            (c.get("issues") or [{}])[0].get("code", ""))})
            dims["actionability"] = 4
    an = gates.get("anchor") or {}
    if an and not an.get("ok", True):
        if dims.get("evidence", 10) > 4:
            ded.append({"kind": "anchor", "dim": "evidence",
                        "from": dims.get("evidence"), "to": 4,
                        "why": "未锚定率 {:.0%} > {:.0%} → 依据分封顶 4".format(
                            an.get("miss_rate", 0), ANCHOR_MAX_MISS)})
            dims["evidence"] = 4
    cm = gates.get("compliance") or {}
    if cm and not cm.get("ok", True):
        hi = [h for h in cm.get("hits", []) if h.get("level") == "高"]
        cap = 1 if hi else 4
        if dims.get("accuracy", 10) > cap:
            ded.append({"kind": "compliance", "dim": "accuracy",
                        "from": dims.get("accuracy"), "to": cap,
                        "why": "命中违禁/承诺类表述「{}」→ 准确分封顶 {}".format(
                            (cm.get("hits") or [{}])[0].get("word", "?"), cap)})
            dims["accuracy"] = cap
    return dims, ded


def local_disposition_plan(pol, level_key, severity, total_points, needs, authorize=True):
    """本地算一份**确定性的**处置口径（与模型的建议并列显示，用来对照）。

    为什么要本地再算一份：**权限不能被模型的话术影响**。本地这份只吃三样东西 ——
    该给多少（模型建议的额度）、本级能批多少（policy）、该升给谁（policy）。
    这样读报告的人能一眼看出"模型的建议"与"制度的边界"差在哪。
    """
    lv = policy_level(pol, level_key)
    cap = float(lv.get("cap") or 0)
    up = str(lv.get("escalate_to") or "")
    total = float(total_points or 0)
    plan = {
        "policy_version": pol.get("policy_version"),
        "level": level_key, "level_cap_points": cap,
        "severity": severity,
        "sla_minutes": policy_sla_minutes(pol, level_key, severity),
        "suggested_points": round(total, 2),
        "within_authority": total <= cap + 1e-9,
        "decision": "当场可批" if total <= cap + 1e-9 else "需升级",
        "escalate_to": up,
    }
    if total > cap + 1e-9:
        plan["why"] = ("建议额度 {} 超出本级上限 {} → 本地判**必须升级**给「{}」。"
                       "超出部分不许由本级批出。".format(
                           fmt_points(pol, total), fmt_points(pol, cap),
                           up or "公司决策"))
    else:
        plan["why"] = "建议额度在本级权限内（{} ≤ {}），可当场批".format(
            fmt_points(pol, total), fmt_points(pol, cap))
    if not needs:
        plan["decision"] = "不予补偿"
        plan["why"] = "技术判定倾向无需补偿；若判无需补偿，理由必须写进处置方案（闸门七）"
    return plan


# ===========================================================================
# 人读渲染（Markdown）
# ===========================================================================

def _red(s, force_plain=False):
    """标红：终端里加 ANSI，重定向到文件时不加（免得文件里全是转义符）。"""
    if force_plain or not sys.stderr.isatty():
        return s
    return "\033[31m{}\033[0m".format(s)


def _yesno(v):
    return "是" if v else "否"


def render_roles_md():
    lines = ["# 三剪客 · 客诉处置小组：四个角色", "",
             "L3 多智能体分工互审的**处置式**形态：处理的是**一张工单**，"
             "每一步都带**时效与权限约束**。", "",
             "| 角色 | 目标函数 | 产出物 | 权限 |", "|---|---|---|---|"]
    for r in ROLE_INFO:
        lines.append("| **{}** | {} | {} | {} |".format(
            r["name"], r["objective"], r["deliverable"], r["authority"]))
    lines += ["", "## 谁看得见什么（信息隔离）", "",
              "| 角色 | 看得到 | 看不到 |", "|---|---|---|"]
    for r in ROLE_INFO:
        lines.append("| **{}** | {} | {} |".format(r["name"], r["sees"], r["cannot_see"]))
    lines += ["", "## 处置流程", "",
              "```text",
              "接报 → 技术判断 → 授权（受权限矩阵约束）→ 复盘",
              " │        │            │                  │",
              " │        │            └─ 超权限 → 升级（exit=3）",
              " │        └─ 产品缺陷 / 用户误用 / 环境问题 / 证据不足",
              " └─ 类型 + P0~P3 + 承诺时限（时限来自 policy）",
              "```", "",
              "**只有「授权」这一席手里有钱**，而且被权限矩阵硬约束 —— "
              "这是本包与所有内容类小组的结构性差别：那三个角色没有花钱的权限。", ""]
    return "\n".join(lines) + "\n"


def render_policy_md(pol):
    lines = ["# 权限矩阵与补偿枚举", "",
             "> 口径版本：`{}`".format(pol.get("policy_version")), ""]
    if pol.get("policy_file"):
        lines.append("> 本次用 `--policy {}` **覆盖**了包内默认口径。".format(
            pol["policy_file"]))
        lines.append("")
    lines += ["## 一、谁能批多少（单位：点；1 元 = {:g} 点）".format(
        float(pol.get("points_per_yuan") or POINTS_PER_YUAN)), "",
        "| 层级 | 级别 | 单张工单可批上限 | 需上级确认起点 | 超权限升给 |",
        "|---|---|---|---|---|"]
    for k, v in (pol.get("authority_levels") or {}).items():
        lines.append("| **{}** | {} | {} | {} | {} |".format(
            k, v.get("rank"), fmt_points(pol, v.get("cap")),
            fmt_points(pol, v.get("need_below")),
            v.get("escalate_to") or "（最高层）"))
    lines += ["", "## 二、各层级的承诺时限（分钟）", "",
              "| 层级 | P0 | P1 | P2 | P3 |", "|---|---|---|---|---|"]
    for k, v in (pol.get("authority_levels") or {}).items():
        sla = v.get("sla_minutes") or {}
        lines.append("| **{}** | {} | {} | {} | {} |".format(
            k, sla.get("P0"), sla.get("P1"), sla.get("P2"), sla.get("P3")))
    lines += ["", "## 三、补偿项枚举（**不许自创补偿**）", "",
              "| 补偿项 | 名称 | 现金出账 | 说明 |", "|---|---|---|---|"]
    for k, v in COMPENSATION_TYPES.items():
        if k not in policy_compensation_keys(pol):
            continue
        lines.append("| `{}` | {} | {} | {} |".format(
            k, v["label"], "是" if v["cash"] else "否", v["desc"]))
    lines += ["", "## 四、等级口径", "",
              "| 等级 | 名称 | 判据 |", "|---|---|---|"]
    for sev in SEVERITY_KEYS:
        s = SEVERITY_LEVELS[sev]
        lines.append("| **{}** | {} | {} |".format(sev, s["label"], s["desc"]))
    lines += ["", "## 五、越权会发生什么", "",
              "补偿合计超过本级上限，或补偿项不在枚举里 → **硬闸门 exit=3**，"
              "并在 stderr 汇总原因、要求输出 `escalate_to`。",
              "",
              "本地还会独立算一份「制度边界」（与模型的建议并列显示）：",
              "**权限不受模型话术影响** —— 模型说「建议赔 300」而本级只能批 50，",
              "本地照样判「必须升级」。", ""]
    return "\n".join(lines) + "\n"


def render_card_md(card, tk=None):
    c = card or {}
    lines = ["## 一、工单卡（接报）", ""]
    if tk:
        f = (tk.get("fields") or {})
        meta = [("工单号", f.get("ticket_id")), ("提交时间", f.get("created_at")),
                ("渠道", f.get("channel")), ("客户", f.get("customer")),
                ("订单", f.get("order")), ("实付金额", f.get("amount"))]
        meta = [(k, v) for k, v in meta if v]
        if meta:
            lines.append("| 字段 | 值 |")
            lines.append("|---|---|")
            for k, v in meta:
                lines.append("| {} | {} |".format(k, v))
            lines.append("")
    lines += [
        "| 项 | 值 |", "|---|---|",
        "| 类型 | **{}**（`{}`）｜归口：{} |".format(
            c.get("ticket_type_label"), c.get("ticket_type"), c.get("type_owner")),
        "| 等级 | **{}**（`{}`） |".format(c.get("severity_label"), c.get("severity")),
        "| **承诺时限** | **{:g} 分钟**（来源：`{}`） |".format(
            float(c.get("sla_minutes_policy") or 0), c.get("sla_source")),
        "| 模型写的时限 | {} |".format(
            "（缺）" if c.get("sla_minutes") is None else "{:g} 分钟".format(
                float(c["sla_minutes"]))),
        "| 处理层级 | {} |".format(c.get("handled_by")),
        "| 影响面 | {} |".format(c.get("impact_scope") or "（缺）"),
        "| 用户诉求 | {} |".format(c.get("user_demand") or "（缺）"),
        "",
        "**一句话**：{}".format(c.get("summary") or "（缺）"),
        "",
        "**定级理由**：{}".format(c.get("severity_reason") or "（缺）"),
        "",
    ]
    if c.get("key_facts"):
        lines.append("**从工单里抽出的事实**：")
        for x in c["key_facts"]:
            lines.append("- {}".format(x))
        lines.append("")
    if c.get("pending_info"):
        lines.append("**待用户补的材料**：")
        for x in c["pending_info"]:
            lines.append("- {}".format(x))
        lines.append("")
    if c.get("normalized"):
        lines.append("> 本地归一化提示：")
        for x in c["normalized"]:
            lines.append("> - {}".format(x))
        lines.append("")
    return "\n".join(lines) + "\n"


def render_diag_md(diag, anchored=None, unanchored=None):
    d = diag or {}
    lines = ["## 二、技术判断", "",
             "| 项 | 值 |", "|---|---|",
             "| 归因 | **{}**（`{}`） |".format(
                 d.get("root_cause_label"), d.get("root_cause_class")),
             "| 责任归属 | {} |".format(d.get("responsibility") or "（缺）"),
             "| 可复现性 | {}（`{}`） |".format(
                 d.get("reproducibility_label"), d.get("reproducibility")),
             "| 补偿倾向 | {} |".format(d.get("compensation_bias") or "（缺）"),
             "", "**技术结论**：{}".format(d.get("verdict") or "（缺）"), ""]
    if d.get("repro_steps"):
        lines.append("**可复现步骤**：")
        for i, s in enumerate(d["repro_steps"], 1):
            lines.append("{}. {}".format(i, s))
        lines.append("")
    lines.append("**证据链**（引工单原文）：")
    lines.append("")
    lines.append("| 引文 | 证明什么 | 锚定 |")
    lines.append("|---|---|---|")
    for it in (anchored if anchored is not None else (d.get("evidence") or [])):
        if not isinstance(it, dict):
            continue
        lines.append("| 「{}」 | {} | {} |".format(
            it.get("sentence") or it.get("quote"), it.get("why") or "-",
            it.get("anchor_rule") or "-"))
    if unanchored:
        lines.append("")
        lines.append("**⚠️ 编造的引文（已剔出，不作为交付内容）**：")
        lines.append("")
        lines.append("| 引文 | 为什么不算 |")
        lines.append("|---|---|")
        for it in unanchored:
            lines.append("| 「{}」 | {} |".format(
                str(it.get("quote"))[:60], it.get("why_unverified") or "-"))
    lines.append("")
    if d.get("ruled_out"):
        lines.append("**已排除的可能**：")
        for x in d["ruled_out"]:
            lines.append("- {}".format(x))
        lines.append("")
    if d.get("need_more"):
        lines.append("**还缺什么才能定论**：")
        for x in d["need_more"]:
            lines.append("- {}".format(x))
        lines.append("")
    return "\n".join(lines) + "\n"


def render_settle_md(settle, pol, plan=None, auth=None):
    s = settle or {}
    lines = ["## 三、处置方案（授权，**受权限矩阵约束**）", "",
             "| 项 | 值 |", "|---|---|",
             "| 结论 | **{}** |".format(s.get("conclusion") or "（缺）"),
             "| 处理层级 | {} |".format(s.get("authority_level") or "（缺）"),
             "| 是否需要补偿 | {} |".format(_yesno(s.get("needs_compensation"))),
             "| 补偿合计 | **{}** |".format(fmt_points(pol, s.get("total_points") or 0)),
             "| 本级上限 | {} |".format(
                 fmt_points(pol, (auth or {}).get("cap") or 0)),
             "| 是否在权限内 | {} |".format(
                 _yesno((auth or {}).get("within_authority"))),
             "| 是否需升级 | {} |".format(_yesno(s.get("requires_escalation"))),
             "| 升级给 | {} |".format(s.get("escalate_to") or "（未升级）"),
             "| 处置时刻 | {} |".format(s.get("handled_at") or "（缺）"),
             ""]
    if s.get("compensation_items"):
        lines.append("**补偿项**（枚举内）：")
        lines.append("")
        lines.append("| 补偿项 | 名称 | 金额（点） | 凭什么给 |")
        lines.append("|---|---|---|---|")
        for it in s["compensation_items"]:
            lines.append("| `{}` | {} | {:g} | {} |".format(
                it.get("type"), (pol.get("compensation_types") or {}).get(
                    it.get("type")) or "-", float(it.get("amount_points") or 0),
                it.get("why") or "-"))
        lines.append("")
    if s.get("no_compensation_reason"):
        lines.append("**无需补偿的理由**：{}".format(s["no_compensation_reason"]))
        lines.append("")
    if s.get("escalate_reason"):
        lines.append("**升级理由**：{}".format(s["escalate_reason"]))
        lines.append("")
    lines.append("### 给用户的话术（**面客字段，零豁免**）")
    lines.append("")
    voice = s.get("voice_to_user") or "（缺）"
    for para in split_paras(voice):
        lines.append("> {}".format(para.replace("\n", "\n> ")))
    lines.append("")
    if s.get("internal_note"):
        lines.append("**内部说明**：{}".format(s["internal_note"]))
        lines.append("")
    if plan:
        lines.append("### 本地算的制度边界（与模型的建议并列，用来对照）")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("|---|---|")
        lines.append("| 模型建议额度 | {} |".format(
            fmt_points(pol, plan.get("suggested_points") or 0)))
        lines.append("| 本级上限 | {} |".format(
            fmt_points(pol, plan.get("level_cap_points") or 0)))
        lines.append("| 本地判定 | **{}** |".format(plan.get("decision")))
        lines.append("| 超权限时升给 | {} |".format(
            plan.get("escalate_to") or "（本级已是最高层）"))
        lines.append("")
        lines.append("> {}".format(plan.get("why") or ""))
        lines.append("")
    return "\n".join(lines) + "\n"


def render_review_md(review, anchored=None, unanchored=None):
    v = review or {}
    lines = ["## 四、复盘（防复发）", "",
             "**根因**：{}".format(v.get("root_cause") or "（缺）"), ""]
    if anchored:
        lines.append("**根因依据**（引工单原文）：")
        lines.append("")
        lines.append("| 引文 | 支撑什么 | 锚定 |")
        lines.append("|---|---|---|")
        for it in anchored:
            lines.append("| 「{}」 | {} | {} |".format(
                it.get("sentence") or it.get("quote"), it.get("why") or "-",
                it.get("anchor_rule") or "-"))
        lines.append("")
    if unanchored:
        lines.append("**⚠️ 编造的引文（已剔出）**：")
        lines.append("")
        for it in unanchored:
            lines.append("- 「{}」—— {}".format(
                str(it.get("quote"))[:60], it.get("why_unverified") or "-"))
        lines.append("")
    if v.get("improvements"):
        lines.append("**改进项**：")
        lines.append("")
        lines.append("| 类型 | 改什么 | 谁改 |")
        lines.append("|---|---|---|")
        kind_cn = {"doc": "改文档", "product": "改产品", "process": "改流程",
                   "policy": "改口径"}
        for it in v["improvements"]:
            lines.append("| {} | {} | {} |".format(
                kind_cn.get(it.get("kind"), it.get("kind")), it.get("what"),
                it.get("owner")))
        lines.append("")
    for k, label in (("similar_alert", "同类工单预警"),
                     ("recurrence_metric", "复发监控指标"),
                     ("doc_gap", "文档缺口"),
                     ("product_gap", "产品缺口")):
        if v.get(k):
            lines.append("**{}**：{}".format(label, v[k]))
            lines.append("")
    if v.get("normalized"):
        lines.append("> 本地归一化提示：")
        for x in v["normalized"]:
            lines.append("> - {}".format(x))
        lines.append("")
    return "\n".join(lines) + "\n"


def render_usage_section(usage, tracker=None):
    lines = ["## 五、这次处置花了多少", "",
             "| 项 | 值 |", "|---|---|",
             "| 调用次数 | {} |".format(usage.get("calls")),
             "| prompt token | {} |".format(usage.get("prompt_tokens")),
             "| completion token | {} |".format(usage.get("completion_tokens")),
             "| **总 token** | **{}** |".format(usage.get("total_tokens")),
             "| 无真实 usage 的调用 | {} |".format(usage.get("estimated_flags")),
             ""]
    if usage.get("per_call"):
        lines.append("| 调用 | prompt | completion | finish_reason |")
        lines.append("|---|---|---|---|")
        for c in usage["per_call"]:
            lines.append("| {} | {} | {} | `{}` |".format(
                c.get("stage"), c.get("prompt_tokens"), c.get("completion_tokens"),
                c.get("finish_reason") if c.get("finish_reason") is not None else "-"))
        lines.append("")
        lines.append("> `finish_reason` 记在这里是有用的：**`length` 才表示被 max_tokens "
                     "截断**（那就加大 `--max-tokens`）；其它值（`stop` / `None`）说明"
                     "是模型自己写错了或响应在路上断了，**加大 max-tokens 没用**，"
                     "该换模型重试或把工单拆短。")
        lines.append("")
    lines.append("> {}".format(usage.get("gateway_note") or ""))
    lines.append("")
    return "\n".join(lines) + "\n"


def render_gates_section(gates):
    hits = gate_hits(gates)
    lines = ["## 六、硬闸门", ""]
    if not hits:
        lines.append("**全部通过**（{} 道本地闸门）。".format(len(GATE_KEYS)))
    else:
        lines.append("**命中 {} 道**：".format(len(hits)))
        lines.append("")
        lines.append("| 闸门 | 为什么没过 |")
        lines.append("|---|---|")
        for k, v in hits:
            name = dict(GATE_CATALOG).get(k, k)
            why = v.get("why") or ""
            if k == "authority":
                why = "；".join(i.get("why") or "" for i in (v.get("issues") or []))
            elif k in ("sla", "complete"):
                why = "；".join(i.get("why") or "" for i in (v.get("issues") or []))
            lines.append("| {} | {} |".format(name, why or "命中"))
        lines.append("")
    cm = gates.get("compliance") or {}
    if cm.get("material_hits"):
        lines.append("> **工单原文**里有 {} 处违禁/承诺类表述：**只报不拦**"
                     "（那是用户写的字，不是我们要发出去的字）—— {}"
                     .format(len(cm["material_hits"]),
                             "、".join("「{}」".format(h.get("word"))
                                      for h in cm["material_hits"][:8])))
        lines.append("")
    if cm.get("exempted"):
        lines.append("> 本地放过 {} 处「最X」疑似命中（判为普通中文用法 / SLA 口径，"
                     "**不静默丢弃**）—— {}".format(
                         len(cm["exempted"]),
                         "、".join("「{}」".format(e.get("word"))
                                  for e in cm["exempted"][:8])))
        lines.append("")
    pe = gates.get("prompt_echo") or {}
    if pe.get("skipped_windows"):
        lines.append("> contain 判据被适用窗口跳过 {} 类（**不静默略过**）：".format(
            len(pe["skipped_windows"])))
        for s in pe["skipped_windows"][:3]:
            lines.append("> - {} —— {} 次".format(s.get("why"), s.get("times")))
        lines.append("")
    return "\n".join(lines) + "\n"


def render_report_md(result):
    """把整套处置拼成一份可读的报告。"""
    lines = ["# 客诉处置报告", "",
             "> 口径版本：`{}`｜提示词 `{}`｜闸门 `{}`".format(
                 result.get("crew_version"), result.get("prompt_version"),
                 result.get("gate_version")), ""]
    b = result.get("brief") or {}
    lines += ["| 项 | 值 |", "|---|---|",
              "| 工单来源 | {} |".format(b.get("path") or "（--text 直接给）"),
              "| 工单字数 | {} |".format(b.get("chars")),
              "| 处理层级 | {} |".format(result.get("authority_level")),
              "| 结论 | {} |".format(result.get("overall") or "-"),
              ""]
    if result.get("card"):
        lines.append(render_card_md(result["card"], result.get("ticket")))
    if result.get("diagnose"):
        anchors = result.get("anchors") or {}
        lines.append(render_diag_md(result["diagnose"],
                                    anchored=(anchors.get("diagnose") or {}).get("ok"),
                                    unanchored=(anchors.get("diagnose") or {}).get("bad")))
    if result.get("settle"):
        lines.append(render_settle_md(result["settle"], result.get("policy_obj") or {},
                                      plan=result.get("local_plan"),
                                      auth=(result.get("authority") or {}).get("detail")))
    if result.get("review"):
        anchors = result.get("anchors") or {}
        lines.append(render_review_md(result["review"],
                                      anchored=(anchors.get("review") or {}).get("ok"),
                                      unanchored=(anchors.get("review") or {}).get("bad")))
    if result.get("usage"):
        lines.append(render_usage_section(result["usage"]))
    if result.get("gates"):
        lines.append(render_gates_section(result["gates"]))
    lines += ["---", "",
              "> ⚠️ **本包不接真实支付 / 工单系统，也不联网去改任何后台数据。**",
              "> 它产出的是**处置建议与话术** —— 真的要退款、要赠额、要延期，",
              "> 必须由人工在后台执行。补偿金额只是口径，不是已发生的账。", ""]
    return "\n".join(lines) + "\n"


def render_cost_md(rec):
    lines = ["# 处置成本估算", "",
             "| 项 | 值 |", "|---|---|",
             "| 工单字数 | {} |".format(rec.get("source_chars")),
             "| 调用次数 | {} |".format(rec.get("total_calls")),
             "| 输入 token | {} |".format(rec.get("tokens_in")),
             "| 输出 token | {} |".format(rec.get("tokens_out")),
             "| 金额 | {} |".format(
                 "无法估算（没给单价）" if rec.get("points") is None
                 else "{:g} 点 ≈ ¥{:g}".format(rec["points"], rec["yuan"])),
             "", "> 单位统一是**点**（与权限矩阵里的补偿金额同一单位，"
             "1 元 = {:g} 点）。".format(POINTS_PER_YUAN), ""]
    if rec.get("calls"):
        lines.append("| 阶段 | 次数 | 输入 token | 输出 token | 说明 |")
        lines.append("|---|---|---|---|---|")
        for c in rec["calls"]:
            lines.append("| {} | {} | {} | {} | {} |".format(
                c.get("stage"), c.get("calls"), c.get("tokens_in"),
                c.get("tokens_out"), c.get("note")))
        lines.append("")
    for n in (rec.get("notes") or []):
        lines.append("> {}".format(n))
    lines.append("")
    return "\n".join(lines) + "\n"


# ===========================================================================
# 角色调用的统一封装
# ===========================================================================

def _tracker(a):
    return CostTracker(budget=getattr(a, "budget", None),
                       price_in=getattr(a, "price_in", None),
                       price_out=getattr(a, "price_out", None))


def role_call(role_key, prompt, a, tracker, label=None):
    """调一次模型并记账。**预算核验在调用之前**（超了就 exit=5，不发起那次调用）。"""
    est_in = estimate_tokens_in(prompt) + ROLE_SYSTEM_TOKENS
    est_out = ROLE_OUT_TOKENS.get(role_key, 1200)
    if tracker.over_budget(extra_in=est_in, extra_out=est_out):
        raise BudgetStop(
            "预算超限：已用 {}，本次「{}」预估还要 {} in + {} out token，"
            "**未发起这次调用**。加大 --budget 或先跑 --dry-run 看提示词。".format(
                tracker.line(), role_label(role_key), est_in, est_out))
    if getattr(a, "dry_run", False):
        return "__DRYRUN__", {}
    content, usage = chat(prompt, model=a.model, temperature=a.temperature,
                          max_tokens=a.max_tokens, key=a.key,
                          json_mode=not getattr(a, "no_json_mode", False))
    tracker.add(usage, label or role_label(role_key))
    if tracker.stages:
        tracker.stages[-1]["finish_reason"] = _LAST_FINISH.get("reason")
        tracker.stages[-1]["content_chars"] = _LAST_FINISH.get("chars")
    return content, usage


SYSTEM_PROMPT = (
    "你是三剪客客诉处置小组里的一个角色。严格遵守给你的角色边界与输出契约："
    "只做你这个角色该做的事，不越界到别的角色；"
    "只输出一个合法 JSON 对象，不要解释、不要 Markdown 代码块之外的任何文字。"
    "你引用的每一句原文都必须真实存在于用户给你的材料里，不许编造引文。"
)


def _dry(a, role_key, prompt):
    """`--dry-run`：把将发送的提示词打出来，不花钱。"""
    sys.stderr.write("\n===== [dry-run] {} 的提示词（未发送，未花钱） =====\n".format(
        role_label(role_key)))
    sys.stderr.write("--- system ---\n{}\n--- user ---\n{}\n===== 结束 =====\n\n".format(
        SYSTEM_PROMPT, prompt))


def _stage_state(a, state, key, payload, label):
    """断点：命中就复用旧产物（0 调用），否则记下来等落盘。"""
    if getattr(a, "force", False):
        return None
    return state.get(key)


# ===========================================================================
# 子命令：roles / policy（零成本）
# ===========================================================================

def run_roles(a):
    obj = {
        "mode": "roles",
        "crew_version": CREW_VERSION,
        "form": "L3 · 处置式（disposition）",
        "difference": ("内容类小组对**一份稿子**做评价，评价不花钱；本包对**一张工单**做处置，"
                       "处置要花钱，而且不是每个角色都有权花这笔钱 —— "
                       "所以必须有权限矩阵、必须有时效、必须有升级路径。"
                       "这三件事在内容类包里结构上不存在。"),
        "not_integrated": ("本包**不接真实支付 / 工单系统**，也不联网去改任何后台数据；"
                           "它产出的是处置建议与话术，落地要人工在后台执行。"),
        "roles": [{k: r[k] for k in ("key", "name", "objective", "deliverable",
                                     "authority", "sees", "cannot_see")}
                  for r in ROLE_INFO],
    }
    if _json_out(obj, a, indent=2):
        return EXIT_OK
    print(render_roles_md(), end="")
    return EXIT_OK


def run_policy(a):
    pol = load_policy(getattr(a, "policy", None))
    a._pol = pol
    obj = {
        "mode": "policy",
        "policy_version": pol.get("policy_version"),
        "policy_file": pol.get("policy_file"),
        "points_per_yuan": pol.get("points_per_yuan"),
        "unit": "点（1 元 = {} 点）".format(pol.get("points_per_yuan")),
        "authority_levels": pol.get("authority_levels"),
        "compensation_types": {k: dict(v, key=k)
                               for k, v in COMPENSATION_TYPES.items()
                               if k in policy_compensation_keys(pol)},
        "severity_levels": SEVERITY_LEVELS,
        "escalation": ("补偿合计超出本级上限，或用了枚举外的补偿项 → "
                       "硬闸门 exit=3，并要求输出 escalate_to"),
        "not_integrated": ("本包不接真实支付 / 工单系统：补偿金额只是口径，"
                           "不是已发生的账；真的要退款/赠额必须人工在后台执行。"),
    }
    if _json_out(obj, a, indent=2):
        return EXIT_OK
    print(render_policy_md(pol), end="")
    return EXIT_OK


# ===========================================================================
# 子命令：intake / diagnose / settle / review
# ===========================================================================

def _load_ticket(a):
    if getattr(a, "text", None):
        raw = a.text
        path = None
    elif getattr(a, "file", None):
        raw = read_text(a.file, "工单")
        path = a.file
    else:
        raise UsageError("给 `--file 工单.md` 或 `--text \"...\"` 都行，二选一")
    tk = parse_ticket(raw)
    return tk, path


def _emit_stage(a, role_key, obj, md_text, name, outdir=None, extra=None):
    """阶段产物的统一出口：`--out` 落文件，非 --out 时 `--json` 打 stdout。"""
    payload = dict(obj)
    if extra:
        payload.update(extra)
    if getattr(a, "out", None):
        ensure_outside_pkg(a.out, "--out")
        write_json(a.out, _json_payload(payload, True))
        sys.stderr.write("已写入 {}\n".format(a.out))
        if _json_want(a):
            _json_write(_json_text(payload, indent=2, ok=True))
        else:
            print(md_text if md_text.endswith("\n") else md_text + "\n")
        return EXIT_OK
    if _json_out(payload, a, indent=2):
        return EXIT_OK
    print(md_text if md_text.endswith("\n") else md_text + "\n")
    return EXIT_OK


def run_intake(a):
    check_cost_opts(a)
    pol = load_policy(getattr(a, "policy", None))
    a._pol = pol
    level_key = getattr(a, "as_role", None) or DEFAULT_AUTHORITY
    policy_level(pol, level_key)                    # 层级名不合法 → exit=2
    tk, path = _load_ticket(a)
    prompt = build_intake_prompt(tk, pol)
    if getattr(a, "dry_run", False):
        _dry(a, "intake", prompt)
        return EXIT_OK
    tracker = _tracker(a)
    content, _u = role_call("intake", prompt, a, tracker)
    card = normalize_intake(parse_first_json(content), pol, level_key)
    card["created_at"] = card.get("created_at") or ticket_created_at(tk)

    anchored, bad, stat = anchor_records(card.get("quotes") or [], tk.get("raw") or "",
                                        label="工单卡·定级理由")
    card["quotes_anchored"] = anchored
    card["quotes_unanchored"] = bad
    card["anchor_stat"] = stat

    sk = anchors_stat_for_card(card, stat)
    gates = evaluate_gates(material_text=tk.get("raw") or "", card=card, pol=pol,
                           anchors=sk, level_key=level_key,
                           ticket_created=ticket_created_at(tk))
    md = render_card_md(card, tk) + "\n" + render_gates_section(gates)
    extra = {"usage": usage_dict(tracker), "gates": gates, "ticket_chars": tk["chars"]}
    return _finish_stage(a, "intake", "card", card, md, gates, extra)


def anchors_stat_for_card(card, stat):
    """工单卡的锚点是**定级理由**的锚点；它单独过闸门，附带 `label`。"""
    s = dict(stat)
    s["label"] = "工单卡·定级理由"
    return s


def _finish_stage(a, role_key, payload_key, obj, md, gates, extra):
    """阶段收尾：闸门汇总到 stderr；命中 → 退出码 3。"""
    _gate_stderr("{} 阶段".format(role_label(role_key)), gates,
                 getattr(a, "_pol", None))
    tracker_line = (extra or {}).get("usage") or {}
    if tracker_line.get("calls") is not None:
        sys.stderr.write("（本次 {} token：prompt={} completion={} total={}）\n".format(
            tracker_line.get("calls"), tracker_line.get("prompt_tokens"),
            tracker_line.get("completion_tokens"), tracker_line.get("total_tokens")))
    rc = EXIT_OK
    if gate_failed(gates):
        rc = EXIT_GATE
        _fail(rc, "gate", "{} 阶段命中硬闸门（见 stderr 汇总）".format(
            role_label(role_key)), {"gates": list(k for k, _ in gate_hits(gates))})
    payload = {payload_key: obj}
    payload.update(extra or {})
    if getattr(a, "out", None):
        ensure_outside_pkg(a.out, "--out")
        write_json(a.out, _json_payload(payload, rc == EXIT_OK))
        sys.stderr.write("已写入 {}\n".format(a.out))
        if _json_want(a):
            _json_write(_json_text(payload, indent=2, ok=(rc == EXIT_OK)))
        else:
            print(md if md.endswith("\n") else md + "\n")
        return rc
    if _json_out(payload, a, indent=2, ok=(rc == EXIT_OK)):
        return rc
    print(md if md.endswith("\n") else md + "\n")
    return rc


def run_diagnose(a):
    check_cost_opts(a)
    pol = load_policy(getattr(a, "policy", None))
    a._pol = pol
    level_key = getattr(a, "as_role", None) or DEFAULT_AUTHORITY
    policy_level(pol, level_key)
    tk, path = _load_ticket(a)
    card = load_artifact(getattr(a, "card", None), "card", "工单卡 JSON")
    if not isinstance(card, dict):
        raise UsageError("`--card 工单卡.json` 必须是 `intake --json --out` 落下的产物")
    prompt = build_diagnose_prompt(tk, card, pol)
    if getattr(a, "dry_run", False):
        _dry(a, "diagnose", prompt)
        return EXIT_OK
    tracker = _tracker(a)
    content, _u = role_call("diagnose", prompt, a, tracker)
    diag = normalize_diagnose(parse_first_json(content), pol)

    anchored, bad, stat = anchor_records(diag.get("evidence") or [],
                                        tk.get("raw") or "", label="技术判定·证据")
    diag["evidence_anchored"] = anchored
    diag["evidence_unanchored"] = bad
    stat["label"] = "技术判定·证据"
    gates = evaluate_gates(material_text=tk.get("raw") or "", card=card, diag=diag,
                           pol=pol, anchors=stat, level_key=level_key,
                           ticket_created=ticket_created_at(tk))
    md = render_diag_md(diag, anchored=anchored, unanchored=bad) \
        + "\n" + render_gates_section(gates)
    extra = {"usage": usage_dict(tracker), "gates": gates}
    return _finish_stage(a, "diagnose", "diagnose", diag, md, gates, extra)


def run_settle(a):
    # ⚠️ 会花钱的子命令，**第一步**就核预算参数（灾备：同族曾在跑完报价后才拦）
    check_cost_opts(a)
    pol = load_policy(getattr(a, "policy", None))
    a._pol = pol
    level_key = getattr(a, "as_role", None) or DEFAULT_AUTHORITY
    policy_level(pol, level_key)
    tk, path = _load_ticket(a)
    card = load_artifact(getattr(a, "card", None), "card", "工单卡 JSON")
    if not isinstance(card, dict):
        raise UsageError("`--card 工单卡.json` 必须是 `intake --json --out` 落下的产物")
    diag = load_artifact(getattr(a, "diag", None), "diagnose", "技术判定 JSON")

    prompt = build_settle_prompt(tk, card, diag, pol, level_key)
    if getattr(a, "dry_run", False):
        _dry(a, "settle", prompt)
        return EXIT_OK
    tracker = _tracker(a)
    content, _u = role_call("settle", prompt, a, tracker)
    settle = normalize_settle(parse_first_json(content), pol, level_key)

    # `--grant-cap`：把本级**实际可批额度**临时调低，用来复现越权拦截。
    # 真实场景就是新人不熟练、额度被临时收紧；它**不绕过**层级判定本身。
    grant = getattr(a, "grant_cap", None)
    effective_cap = float(grant) if grant is not None else None

    anchored, bad, stat = anchor_records(settle.get("quotes") or [],
                                        tk.get("raw") or "", label="处置方案·依据")
    settle["quotes_anchored"] = anchored
    settle["quotes_unanchored"] = bad
    stat["label"] = "处置方案·依据"
    gates = evaluate_gates(material_text=tk.get("raw") or "", card=card, diag=diag,
                           settle=settle, pol=pol, anchors=stat, level_key=level_key,
                           effective_cap=effective_cap,
                           severity=(card or {}).get("severity"),
                           ticket_created=ticket_created_at(tk))
    plan = local_disposition_plan(pol, level_key, (card or {}).get("severity") or "P2",
                                 settle.get("total_points") or 0,
                                 settle.get("needs_compensation"))
    md = render_settle_md(settle, pol, plan=plan,
                          auth=(gates.get("authority") or {}).get("detail")) \
        + "\n" + render_gates_section(gates)
    extra = {"usage": usage_dict(tracker), "gates": gates, "local_plan": plan,
             "authority_level": level_key,
             "effective_cap_points": (gates.get("authority") or {}).get(
                 "detail", {}).get("cap")}
    return _finish_stage(a, "settle", "settle", settle, md, gates, extra)


def run_review(a):
    check_cost_opts(a)
    pol = load_policy(getattr(a, "policy", None))
    a._pol = pol
    level_key = getattr(a, "as_role", None) or DEFAULT_AUTHORITY
    policy_level(pol, level_key)
    tk, path = _load_ticket(a)
    card = load_artifact(getattr(a, "card", None), "card", "工单卡 JSON")
    if not isinstance(card, dict):
        raise UsageError("`--card 工单卡.json` 必须是 `intake --json --out` 落下的产物")
    diag = load_artifact(getattr(a, "diag", None), "diagnose", "技术判定 JSON")
    settle = load_artifact(getattr(a, "settle", None), "settle", "处置方案 JSON")

    prompt = build_review_prompt(tk, card, diag, settle, pol)
    if getattr(a, "dry_run", False):
        _dry(a, "review", prompt)
        return EXIT_OK
    tracker = _tracker(a)
    content, _u = role_call("review", prompt, a, tracker)
    review = normalize_review(parse_first_json(content), pol)

    recs = list(review.get("root_cause_evidence") or []) + list(review.get("quotes") or [])
    anchored, bad, stat = anchor_records(recs, tk.get("raw") or "", label="复盘·根因依据")
    review["evidence_anchored"] = anchored
    review["evidence_unanchored"] = bad
    stat["label"] = "复盘·根因依据"
    grant = getattr(a, "grant_cap", None)
    gates = evaluate_gates(material_text=tk.get("raw") or "", card=card, diag=diag,
                           settle=settle, review=review, pol=pol, anchors=stat,
                           level_key=level_key,
                           effective_cap=(float(grant) if grant is not None else None),
                           severity=(card or {}).get("severity"),
                           ticket_created=ticket_created_at(tk))
    md = render_review_md(review, anchored=anchored, unanchored=bad) \
        + "\n" + render_gates_section(gates)
    extra = {"usage": usage_dict(tracker), "gates": gates}
    return _finish_stage(a, "review", "review", review, md, gates, extra)


def gate_summary_lines(gates):
    """给 stderr 用的闸门摘要（一次调用只汇总一次）。"""
    out = []
    for k, v in gate_hits(gates):
        name = dict(GATE_CATALOG).get(k, k)
        if k == "authority":
            for i in (v.get("issues") or []):
                out.append("[{}] {}".format(name, i.get("why")))
        elif k in ("sla", "complete"):
            for i in (v.get("issues") or []):
                out.append("[{}] {}".format(name, i.get("why")))
        elif k == "compliance":
            out.append("[{}] 产出侧命中 {}".format(
                name, "、".join("「{}」({}，{})".format(
                    h.get("word"), h.get("level"), h.get("in") or "-")
                    for h in (v.get("hits") or [])[:8])))
        elif k == "placeholder":
            out.append("[{}] {}".format(
                name, "；".join("{}（{}）".format(h.get("why"), h.get("in") or "-")
                                for h in (v.get("hits") or [])[:5])))
        elif k == "prompt_echo":
            out.append("[{}] {}".format(
                name, "；".join(h.get("why") or "" for h in (v.get("hits") or [])[:3])))
        elif k == "anchor":
            out.append("[{}] {}".format(name, v.get("why") or "未锚定率过高"))
        else:
            out.append("[{}] {}".format(name, v.get("why") or "命中"))
    return out


def _red_gate_stderr(label, gates, pol=None):
    """硬闸门汇总到 stderr（标红 + 逐条原因）。返回是否命中。"""
    pol = pol or default_policy()
    lines = gate_summary_lines(gates)
    if not lines:
        return False
    sys.stderr.write("\n{}\n".format(_red(
        "{}：{} 项硬闸门命中".format(label, len(lines)))))
    for ln in lines:
        sys.stderr.write("   {}\n".format(ln))
    cm = gates.get("compliance") or {}
    ex = cm.get("exempted") or []
    if ex:
        sys.stderr.write("   提示：本地放过 {} 处「最X」疑似命中（判为普通中文用法 / "
                         "SLA 口径，**不静默丢弃**，明细在结果的 gates.compliance.exempted）："
                         "{}\n".format(len(ex),
                                       "、".join("「{}」".format(e.get("word")) for e in ex[:8])))
    mh = cm.get("material_hits") or []
    if mh:
        sys.stderr.write("   提示：**工单原文**里有 {} 处违禁/承诺类表述（{}）——"
                         "**只报不拦**，因为那是用户写的字；"
                         "真要发给用户的话术（voice_to_user）走零豁免口径。\n".format(
                             len(mh), "、".join("「{}」".format(h.get("word")) for h in mh[:8])))
    q = cm.get("quoted_from_material") or []
    m = cm.get("mentioned_as_warning") or []
    if q or m:
        sys.stderr.write("   提示：产出侧另有 {} 处判为**引用工单原文**、{} 处判为**提到/在禁止**"
                         "（都在结果的 gates 里留了原因，未静默丢弃）。\n".format(len(q), len(m)))
    au = gates.get("authority") or {}
    if au and not au.get("ok", True):
        d = au.get("detail") or {}
        sys.stderr.write("   {} 权限矩阵结论：本级 {} 上限 {}，本单合计 {} → {}\n".format(
            _red("[越权]"), d.get("level"),
            fmt_points(pol, d.get("cap") or 0),
            fmt_points(pol, d.get("total_points") or 0),
            "**超出，必须升级**" if not d.get("within_authority") else "在权限内"))
        if d.get("escalate_to"):
            sys.stderr.write("   {} 应升级给：{}\n".format(
                _red("[升级]"), d.get("escalate_to")))
    return True


# 统一的闸门汇总入口（`evaluate_gates` 只算，这里只报）
_gate_stderr = _red_gate_stderr


# ===========================================================================
# 子命令：run（一条命令跑完四步）
#
# 处置是**一条直线**：接报 → 技术判断 → 授权 → 复盘。没有"打回重跑"，
# 因为工单不像稿子 —— 稿子可以改十遍，一笔补偿批出去就收不回来了。
# 所以这里不做循环，只做**一次到底 + 每步都过闸门**。
#
# 唯一会"提前结束"的情形是**越权**：授权这一步被拦下（exit=3），
# 复盘仍然照跑（复盘的价值在于防复发，不该因为一次越权就丢掉）。
# ===========================================================================

def run_run(a):
    check_cost_opts(a)
    pol = load_policy(getattr(a, "policy", None))
    a._pol = pol
    level_key = getattr(a, "as_role", None) or DEFAULT_AUTHORITY
    policy_level(pol, level_key)
    tk, path = _load_ticket(a)
    if not getattr(a, "file", None) and not getattr(a, "text", None):
        raise UsageError("给 `--file 工单.md` 或 `--text \"...\"` 都行")

    outdir = getattr(a, "outdir", None)
    if outdir:
        ensure_outside_pkg(outdir, "--outdir")
    grant = getattr(a, "grant_cap", None)
    effective_cap = float(grant) if grant is not None else None

    state = {} if getattr(a, "force", False) else load_state(outdir)
    created = ticket_created_at(tk)
    tracker = _tracker(a)
    raw_usages = []
    result = {
        "mode": "run",
        "crew_version": CREW_VERSION, "prompt_version": PROMPT_VERSION,
        "gate_version": GATE_VERSION, "policy_version": pol.get("policy_version"),
        "authority_level": level_key,
        "policy_obj": pol,
        "effective_cap_points": (effective_cap if effective_cap is not None
                                 else policy_cap(pol, level_key)),
        "brief": {"path": path, "chars": tk["chars"],
                  "fields": tk.get("fields"), "created_at": created},
        "ticket": tk,
        "anchors": {},
        "not_integrated": ("本包**不接真实支付 / 工单系统**，也不联网去改任何后台数据；"
                           "它产出的是处置建议与话术，落地要人工在后台执行。"),
    }

    def _key(stage, **dims):
        payload = {"ticket": text_sha(tk.get("raw")), "level": level_key,
                   "cap": effective_cap, "policy": pol.get("policy_version"),
                   "policy_levels": pol.get("authority_levels")}
        payload.update(dims)
        return state_key(stage, **payload)

    # ---- 1) 接报 ---------------------------------------------------------
    k1 = _key("intake")
    card = state.get(k1)
    if card:
        sys.stderr.write("断点命中：接报（0 调用）\n")
    else:
        prompt = build_intake_prompt(tk, pol)
        if getattr(a, "dry_run", False):
            _dry(a, "intake", prompt)
            return EXIT_OK
        content, u = role_call("intake", prompt, a, tracker)
        raw_usages.append({"stage": "intake", "usage": u})
        card = normalize_intake(parse_first_json(content), pol, level_key)
        card["created_at"] = card.get("created_at") or created
        state[k1] = card
        save_state(outdir, state)
    result["card"] = card
    anchored, bad, stat = anchor_records(card.get("quotes") or [],
                                        tk.get("raw") or "", label="工单卡·定级理由")
    card["quotes_anchored"], card["quotes_unanchored"] = anchored, bad
    stat["label"] = "工单卡·定级理由"
    result["anchors"]["card"] = {"ok": anchored, "bad": bad, "stat": stat}

    # ---- 2) 技术判断 -----------------------------------------------------
    k2 = _key("diagnose", card_sha=json_sha(card))
    diag = state.get(k2)
    if diag:
        sys.stderr.write("断点命中：技术判断（0 调用）\n")
    else:
        prompt = build_diagnose_prompt(tk, card, pol)
        if getattr(a, "dry_run", False):
            _dry(a, "diagnose", prompt)
            return EXIT_OK
        content, u = role_call("diagnose", prompt, a, tracker)
        raw_usages.append({"stage": "diagnose", "usage": u})
        diag = normalize_diagnose(parse_first_json(content), pol)
        state[k2] = diag
        save_state(outdir, state)
    result["diagnose"] = diag
    anchored, bad, stat = anchor_records(diag.get("evidence") or [],
                                        tk.get("raw") or "", label="技术判定·证据")
    diag["evidence_anchored"], diag["evidence_unanchored"] = anchored, bad
    stat["label"] = "技术判定·证据"
    result["anchors"]["diagnose"] = {"ok": anchored, "bad": bad, "stat": stat}

    # ---- 3) 授权（受权限矩阵约束） ---------------------------------------
    k3 = _key("settle", card_sha=json_sha(card), diag_sha=json_sha(diag))
    settle = state.get(k3)
    if settle:
        sys.stderr.write("断点命中：授权（0 调用）\n")
    else:
        prompt = build_settle_prompt(tk, card, diag, pol, level_key)
        if getattr(a, "dry_run", False):
            _dry(a, "settle", prompt)
            return EXIT_OK
        content, u = role_call("settle", prompt, a, tracker)
        raw_usages.append({"stage": "settle", "usage": u})
        settle = normalize_settle(parse_first_json(content), pol, level_key)
        state[k3] = settle
        save_state(outdir, state)
    result["settle"] = settle
    anchored, bad, stat = anchor_records(settle.get("quotes") or [],
                                        tk.get("raw") or "", label="处置方案·依据")
    settle["quotes_anchored"], settle["quotes_unanchored"] = anchored, bad
    stat["label"] = "处置方案·依据"
    result["anchors"]["settle"] = {"ok": anchored, "bad": bad, "stat": stat}

    # 越权校验（**在复盘之前**：越权结论要进复盘的材料）
    auth_ok, auth_issues, auth_detail = check_authority(
        settle, pol, level_key=level_key, effective_cap=effective_cap)
    result["authority"] = {"ok": auth_ok, "issues": auth_issues, "detail": auth_detail}
    plan = local_disposition_plan(pol, level_key, card.get("severity") or "P2",
                                 settle.get("total_points") or 0,
                                 settle.get("needs_compensation"))
    result["local_plan"] = plan

    # ---- 4) 复盘 ---------------------------------------------------------
    k4 = _key("review", card_sha=json_sha(card), diag_sha=json_sha(diag),
              settle_sha=json_sha(settle), auth_ok=auth_ok)
    review = state.get(k4)
    if review:
        sys.stderr.write("断点命中：复盘（0 调用）\n")
    else:
        prompt = build_review_prompt(tk, card, diag, settle, pol)
        if getattr(a, "dry_run", False):
            _dry(a, "review", prompt)
            return EXIT_OK
        content, u = role_call("review", prompt, a, tracker)
        raw_usages.append({"stage": "review", "usage": u})
        review = normalize_review(parse_first_json(content), pol)
        state[k4] = review
        save_state(outdir, state)
    result["review"] = review
    recs = list(review.get("root_cause_evidence") or []) + list(review.get("quotes") or [])
    anchored, bad, stat = anchor_records(recs, tk.get("raw") or "", label="复盘·根因依据")
    review["evidence_anchored"], review["evidence_unanchored"] = anchored, bad
    stat["label"] = "复盘·根因依据"
    result["anchors"]["review"] = {"ok": anchored, "bad": bad, "stat": stat}

    # ---- 全部闸门（材料齐了，一次算清） ---------------------------------
    anchor_all = _merge_anchor_stats(result["anchors"])
    gates = evaluate_gates(material_text=tk.get("raw") or "", card=card, diag=diag,
                           settle=settle, review=review, pol=pol, anchors=anchor_all,
                           level_key=level_key, effective_cap=effective_cap,
                           severity=(card or {}).get("severity"),
                           ticket_created=created)

    dims = _local_dims(card, diag, settle, review, gates)
    dims, deductions = apply_local_caps(dims, gates)
    result["gates"] = gates
    result["dims"] = dims
    result["deductions"] = deductions
    result["usage"] = usage_dict(tracker, raw_usages)
    if tracker.stages:
        for i, st in enumerate(tracker.stages):
            if i < len(raw_usages):
                raw_usages[i]["finish_reason"] = st.get("finish_reason")

    hits = gate_hits(gates)
    rc = EXIT_GATE if hits else EXIT_OK
    result["ok"] = not hits
    result["overall"] = _overall_line(settle, hits, pol)
    result["md"] = render_report_md(result)

    # ---- 落盘 ------------------------------------------------------------
    if outdir:
        d = Path(outdir)
        d.mkdir(parents=True, exist_ok=True)
        write_json(d / "result.json", _json_payload(result, rc == EXIT_OK))
        write_text(d / "REPORT.md", result["md"])
        sys.stderr.write("已写入 {} 与 {}\n".format(d / "result.json", d / "REPORT.md"))

    _gate_stderr("run", gates, pol)
    if hits:
        _fail(rc, "gate", "run 命中硬闸门：{}".format(
            "、".join(dict(GATE_CATALOG).get(k, k) for k, _ in hits)),
            {"gates": [k for k, _ in hits],
             "authority": result.get("authority")})

    if _json_want(a):
        out = dict(result)
        out.pop("md", None)
        out.pop("ticket", None)
        _json_write(_json_text(out, indent=2, ok=(rc == EXIT_OK)))
        return rc
    print(result["md"] if result["md"].endswith("\n") else result["md"] + "\n")
    return rc


def _merge_anchor_stats(anchors):
    """把四个阶段各自的锚点统计合并成**一个**闸门对象。

    为什么合并而不是各算各的：一条"编造引文"在哪个阶段出现都是同一个问题，
    读报告的人只想知道"这份处置总共引了多少句、其中几句是编的"。
    """
    ok_all, bad_all, total, verified = [], [], 0, 0
    per = {}
    for stage, blk in (anchors or {}).items():
        st = blk.get("stat") or {}
        per[stage] = st
        ok_all.extend(blk.get("ok") or [])
        bad_all.extend(blk.get("bad") or [])
        total += int(st.get("total") or 0)
        verified += int(st.get("verified") or 0)
    miss = (len(bad_all) / float(total)) if total else 0.0
    out = {
        "ok": miss <= ANCHOR_MAX_MISS,
        "total": total, "verified": verified, "unanchored": len(bad_all),
        "miss_rate": round(miss, 3),
        "per_stage": per,
        "rules": {},
    }
    for it in ok_all:
        r = it.get("anchor_rule") or "-"
        out["rules"][r] = out["rules"].get(r, 0) + 1
    if total and not out["ok"]:
        out["why"] = ("{} 条判定/处置里 {} 条的引文在**工单原文**里找不到"
                      "（未锚定率 {:.0%} > {:.0%}）—— 模型在编引文，"
                      "这份处置的依据不可信".format(total, len(bad_all), miss,
                                                    ANCHOR_MAX_MISS))
    return out


def _local_dims(card, diag, settle, review, gates):
    """本地给五个维度的**上限**分（不采信模型自评，避免"模型瞎给高分"）。

    本包的五个维度是按**处置质量**定的，不是按文笔：
      accuracy      判得对不对（定级/归因是否与工单事实吻合）
      authority     守不守权限（本包特有；越权直接封 0）
      timeliness    快不快（是否在承诺时限内）
      actionability 落不落得了地（补偿项/话术/升级对象是否齐）
      evidence      有没有依据（引文是否真实）
    """
    d = {"accuracy": 8, "authority": 10, "timeliness": 10,
         "actionability": 8, "evidence": 8}
    if isinstance(diag, dict) and diag.get("root_cause_class") == "insufficient_evidence":
        d["accuracy"] = min(d["accuracy"], 6)
    if isinstance(review, dict) and not (review.get("improvements") or []):
        d["actionability"] = min(d["actionability"], 5)
    return d


def _overall_line(settle, hits, pol):
    s = settle if isinstance(settle, dict) else {}
    if hits:
        keys = [k for k, _ in hits]
        if "authority" in keys:
            return ("**越权，本单处置不成立** —— 补偿超出本级权限，必须升级后再执行"
                    "（本地闸门已拦下）")
        return "**有硬闸门未过**（{}），先按 stderr 汇总整改".format("、".join(keys))
    concl = s.get("conclusion") or "（缺结论）"
    return "{}｜补偿合计 {}｜{}".format(
        concl, fmt_points(pol, s.get("total_points") or 0),
        ("需升级给 " + str(s.get("escalate_to"))) if s.get("escalate_to") else "无需升级")


# ===========================================================================
# 子命令：log（零成本）
# ===========================================================================

def run_log(a):
    path = getattr(a, "result", None)
    if not path and getattr(a, "outdir", None):
        path = str(Path(a.outdir) / "result.json")
    if not path:
        raise UsageError("给 `--result result.json` 或 `--outdir 处置输出目录`")
    obj = read_json(path, "result.json")
    if isinstance(obj, dict) and "ok" in obj and "card" in obj:
        r = obj
    elif isinstance(obj, dict) and isinstance(obj.get("data"), dict):
        r = obj["data"]
    else:
        r = obj if isinstance(obj, dict) else {}
    lines = ["# 处置台账", "",
             "| 阶段 | 结论摘要 |", "|---|---|"]
    c = r.get("card") or {}
    d = r.get("diagnose") or {}
    s = r.get("settle") or {}
    v = r.get("review") or {}
    lines.append("| 接报 | {} / {} / 承诺 {:g} 分钟 |".format(
        c.get("ticket_type_label") or "-", c.get("severity") or "-",
        float(c.get("sla_minutes_policy") or 0)))
    lines.append("| 技术判断 | {}｜可复现性 {}｜{} |".format(
        d.get("root_cause_label") or "-", d.get("reproducibility") or "-",
        (d.get("verdict") or "-")[:60]))
    lines.append("| 授权 | {}｜补偿 {}｜{} |".format(
        s.get("conclusion") or "-", fmt_points(r.get("policy_obj") or {},
                                              s.get("total_points") or 0),
        ("升级给 " + str(s.get("escalate_to"))) if s.get("escalate_to") else "无需升级"))
    lines.append("| 复盘 | {} |".format((v.get("root_cause") or "-")[:60]))
    anchors = r.get("anchors") or {}
    bad = sum(len((anchors.get(k) or {}).get("bad") or []) for k in anchors)
    lines += ["", "| 项 | 值 |", "|---|---|",
              "| 工单字数 | {} |".format((r.get("brief") or {}).get("chars")),
              "| 处理层级 | {} |".format(r.get("authority_level")),
              "| 编造的引文 | {} 条 |".format(bad),
              "| 总 token | {} |".format((r.get("usage") or {}).get("total_tokens")),
              "| 总调用 | {} |".format((r.get("usage") or {}).get("calls")),
              ""]
    for k, blk in (anchors or {}).items():
        for it in (blk.get("bad") or []):
            lines.append("- ⚠️ {} 的编造引文：「{}」".format(
                k, str(it.get("quote"))[:60]))
    if _json_out({"mode": "log", "source": path, "summary": {
            "card": c, "diagnose": d, "settle": s, "review": v,
            "authority": r.get("authority"), "usage": r.get("usage"),
            "anchors_bad": bad}}, a, indent=2):
        return EXIT_OK
    print("\n".join(lines) + "\n")
    return EXIT_OK


# ===========================================================================
# 子命令：cost（零成本）
# ===========================================================================

def run_cost(a):
    check_cost_opts(a)
    if getattr(a, "text", None):
        raw, path = a.text, None
    elif getattr(a, "file", None):
        raw, path = read_text(a.file, "工单"), a.file
    else:
        raise UsageError("给 `--file 工单.md` 或 `--text \"...\"` 才能估算")
    calls = estimate_calls(raw, getattr(a, "rounds", 1) or 1)
    tin = sum(int(c["tokens_in"]) for c in calls)
    tout = sum(int(c["tokens_out"]) for c in calls)
    rec = compute_cost(tin, tout, a.price_in, a.price_out)
    rec.update({
        "mode": "cost", "path": path, "source_chars": len(raw or ""),
        "calls": calls, "total_calls": sum(int(c["calls"]) for c in calls),
        "crew_version": CREW_VERSION,
        "calibration": {"chars_per_token_in": CHARS_PER_TOKEN_IN,
                        "tokens_per_char_out": TOKENS_PER_CHAR_OUT},
        "note": ("处置是**一条直线**（接报 → 技术判断 → 授权 → 复盘），"
                 "所以就是 4 次调用，没有「打回重跑」。"),
    })
    rec["notes"].append(rec.pop("note"))
    rec["notes"].append("单位是**点**：与权限矩阵里的补偿金额同一单位（1 元 = {:g} 点）。"
                        .format(POINTS_PER_YUAN))
    if _json_out(rec, a, indent=2):
        return EXIT_OK
    print(render_cost_md(rec))
    return EXIT_OK


# ===========================================================================
# 子命令：models（免费）
# ===========================================================================

def run_models(a):
    url = MODELS_URL + ("" if not a.type or a.type == "all" else "?type=" + str(a.type))
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + a7w.load_key(a.key), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except Exception as exc:                       # noqa: BLE001 —— 拉清单失败就是失败
        return _fail(EXIT_CALL, "call", "拉取模型清单失败（网络 / 鉴权 / Key）：{}".format(exc))
    lst = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(lst, dict):
        lst = lst.get("data") or lst.get("list") or []
    lst = [m for m in (lst or []) if isinstance(m, dict)]
    if _json_out(lst, a, indent=1):
        return EXIT_OK
    print("在架模型 {} 个（{}）\n".format(len(lst), MODELS_URL))
    for m in lst:
        print("  {:<26} {:<8} call_type={}  {:<28} {}".format(
            str(m.get("model_code")), str(m.get("type_code") or "-"),
            m.get("call_type"), str(m.get("vendor_name") or "-"),
            str(m.get("model_name") or "")[:24]))
    print("")
    print("提示：模型名会变，以本命令现查为准，别写死在脚本里。")
    print("      `{}` 实测可用（路由到 deepseek-flash），但它**不在**上面这份列表里，"
          .format(DEFAULT_MODEL))
    print("      所以「列表里没有」不等于「不能用」。")
    print("      另外：文本模型**没有单价字段**，所以本包只报 token、不报金额。")
    print("用法：run.py run --file 工单.md --model <model_code>")
    return EXIT_OK


# ===========================================================================
# `--json` 输出契约（给流水线与 agent 消费）
#
#   · 成功：结果对象里多一个 `"ok": true`；顶层是数组时包成 `{"ok": true, "data": [...]}`
#   · 失败：stdout 输出 `{"ok": false, "exit": <码>, "error": {"kind": ..., "message": ...}}`
#     只有在**本次还没吐过任何 JSON 结果**时才补信封
#   · 人读文案照旧走 stderr；**退出码语义一个都不变**；非 `--json` 模式输出一个字符不变
#
# 信封必须落在**真 stdout**：所有 JSON 文本都经 `_json_write` 写，绕开任何临时重定向。
# ===========================================================================

_JSON = {"stdout": None, "want": False, "emitted": False, "reason": None}

_KIND_BY_EXIT = {1: "internal", 2: "usage", 3: "gate", 4: "call", 5: "budget", 130: "interrupt"}


def _json_payload(obj, ok=True):
    """结果对象补 ok；顶层是数组时包成 {"ok": …, "data": […] }。"""
    if isinstance(obj, dict):
        out = {"ok": bool(ok)}
        out.update(obj)
        return out
    return {"ok": bool(ok), "data": obj}


def _json_text(obj, indent=1, ok=True):
    return json.dumps(_json_payload(obj, ok), ensure_ascii=False, indent=indent)


def _json_write(text):
    """把 JSON 文本写到**真 stdout**并记账。"""
    (_JSON["stdout"] or sys.stdout).write(text + "\n")
    _JSON["emitted"] = True


def _json_want(a=None):
    if a is not None:
        return bool(getattr(a, "json", False))
    return bool(_JSON["want"])


def _json_out(obj, a=None, indent=1, ok=True):
    """`--json` 模式的成功出口。返回是否已输出。"""
    if not _json_want(a):
        return False
    _json_write(_json_text(obj, indent=indent, ok=ok))
    return True


def _json_fail(rc, kind=None, message=None, detail=None, a=None):
    """`--json` 模式的失败出口：只在本次还没输出过 JSON 结果时补信封。"""
    if _JSON["emitted"] or not _json_want(a):
        return
    err = {"kind": kind or _KIND_BY_EXIT.get(rc, "call"),
           "message": message or "命令以退出码 {} 结束（人读原因见 stderr）".format(rc)}
    if detail is not None:
        err["detail"] = detail
    _json_write(json.dumps({"ok": False, "exit": rc, "error": err},
                           ensure_ascii=False, indent=1))


def _json_internal(exc):
    """未预料异常的兜底信封 —— **报 bug，不藏 bug**。

    只写 stdout（真 stdout）；完整 traceback 由 main() 的兜底层原样打到 stderr，
    这里不重复、也不吞。`detail.where` 只取**最后一帧**的文件名:行号，整条栈不进 JSON。
    如果本次已经吐过结果，就**不再补信封**（守住"stdout 永远只有一个 JSON"这条不变量）。
    """
    if _JSON["emitted"]:
        return
    tb = sys.exc_info()[2]
    frames = traceback.extract_tb(tb) if tb else []
    detail = {"type": type(exc).__name__}
    if frames:
        last = frames[-1]
        detail["where"] = "{}:{}".format(os.path.basename(last.filename), last.lineno)
    err = {"kind": "internal",
           "message": "{}: {}".format(type(exc).__name__, exc),
           "detail": detail}
    _json_write(json.dumps({"ok": False, "exit": 1, "error": err},
                           ensure_ascii=False, indent=1))


def _fail(rc, kind, message, detail=None):
    """命令函数决定失败时调它：记下原因，返回原退出码（退出码语义不变）。"""
    if _JSON["reason"] is None:
        _JSON["reason"] = {"kind": kind, "message": message, "detail": detail}
    return rc


# ===========================================================================
# 入口
# ===========================================================================

def _add_json(p):
    """让 `--json` 写在子命令**前后都能用**。

    只在父级定义 `--json` 时，argparse 只认「子命令之前」的位置，
    于是文档里常见的 `run.py run --file x --json` 会报 `unrecognized arguments` 并退出 2。
    这里给每个子命令补一个同 dest 的开关，`default=argparse.SUPPRESS` 保证
    父级已经设过的值不会被子命令的默认值覆盖。
    """
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="以 JSON 输出（写在子命令前后都可以）")


def _add_model_opts(p, out=True):
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="模型名，默认 {}（实测可用；用 `run.py models` 现查在架模型）".format(
                       DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.5, help="采样温度，默认 0.5")
    p.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens",
                   help="最大输出 token，默认 4096")
    p.add_argument("--key", help="临时指定 A7W API Key")
    if out:
        p.add_argument("--out", help="把结果写到这个文件（**必须在包外**）")
    _add_json(p)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="只打印将发送的提示词，不调模型不花钱")
    p.add_argument("--no-json-mode", action="store_true", dest="no_json_mode",
                   help="不要求上游返回 JSON 对象（个别模型不支持 response_format 时用）")


def _add_cost_opts(p):
    p.add_argument("--price-in", type=float, dest="price_in",
                   help="输入单价，单位「点/百万 token」。不给我就不给金额（不编价）")
    p.add_argument("--price-out", type=float, dest="price_out",
                   help="输出单价，单位「点/百万 token」")
    p.add_argument("--budget", type=float,
                   help="预算上限（**点**，不是元）。超了就地中止且**不发起那次调用**，"
                        "退出码 5；用 --budget 最好同时给单价（网关不公布单价，"
                        "没单价核不了预算）")


def _add_policy_opts(p):
    p.add_argument("--policy", help="权限矩阵覆盖文件（JSON）。"
                                    "只能**收窄**补偿项枚举，不许新增；"
                                    "层级必须给全 P0~P3 的 sla_minutes")
    p.add_argument("--as-role", dest="as_role", default=None,
                   help="以哪个层级身份处置，默认 {}。"
                        "**这就是「权限矩阵真的起作用了吗」的开关**".format(DEFAULT_AUTHORITY))


def _add_ticket_opts(p, required=True):
    p.add_argument("--file", required=required, help="工单原文（.md / .txt，UTF-8）")
    p.add_argument("--text", help="或直接给工单文本（与 --file 二选一）")


def _parser(**kw):
    """统一构造 ArgumentParser，**关掉长选项前缀缩写**（`allow_abbrev=False`）。

    事故复盘（同族自测时踩到的真实坑）：`run` 上同时有 `--outdir`，用户写
    `--out report.json` 想输出结果文件，argparse 默认允许**前缀缩写**，于是 `--out`
    被当成 `--outdir` 的缩写匹配上了 —— 结果产出目录变成了一个叫 `report.json` 的目录，
    而且**不报任何错**。这类"参数被静默吃成另一个参数"的错误最难查。
    关掉缩写后 `--out` 直接报 unrecognized arguments（退出码 2），一眼就能看出问题。
    """
    kw.setdefault("allow_abbrev", False)
    return argparse.ArgumentParser(**kw)


def _main(argv_eff):
    ap = _parser(
        prog="run.py",
        description="三剪客 · 客诉处置小组（L3 处置式：接报 / 技术判断 / 授权 / 复盘）",
        epilog="端点：POST https://api.a7w.cn/api/v1/chat/completions · "
               "GET https://api.a7w.cn/api/v1/models")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出（写在子命令前后都可以）")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=partial(_parser))

    p = sub.add_parser("roles", help="列出四个角色的职权、产出与权限（零成本、不联网）")
    _add_json(p)
    p.set_defaults(func=run_roles)

    p = sub.add_parser("policy", help="打印权限矩阵与补偿枚举（零成本、不联网）")
    p.add_argument("--policy", help="权限矩阵覆盖文件（JSON）")
    _add_json(p)
    p.set_defaults(func=run_policy)

    p = sub.add_parser("intake", help="接报：分类 + 定级 + 承诺时限 + 影响面")
    _add_ticket_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_policy_opts(p)
    p.set_defaults(func=run_intake)

    p = sub.add_parser("diagnose", help="技术判断：归因 + 可复现步骤 + 证据")
    _add_ticket_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_policy_opts(p)
    p.add_argument("--card", required=True,
                   help="工单卡 JSON（`intake --json --out`）")
    p.set_defaults(func=run_diagnose)

    p = sub.add_parser("settle", help="授权：补偿项与金额，**受权限矩阵硬约束**")
    _add_ticket_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_policy_opts(p)
    p.add_argument("--card", required=True, help="工单卡 JSON")
    p.add_argument("--diag", required=True, help="技术判定 JSON（`diagnose --json --out`）")
    p.add_argument("--grant-cap", type=float, dest="grant_cap", default=None,
                   help="把本级**实际可批额度**临时改成这个点数（用于复现越权拦截 / "
                        "模拟新人额度收紧）。它不绕过层级判定，只改本级额度。")
    p.set_defaults(func=run_settle)

    p = sub.add_parser("review", help="复盘：根因 + 改进项 + 同类工单预警")
    _add_ticket_opts(p)
    _add_model_opts(p)
    _add_cost_opts(p)
    _add_policy_opts(p)
    p.add_argument("--card", required=True, help="工单卡 JSON")
    p.add_argument("--diag", required=True, help="技术判定 JSON")
    p.add_argument("--settle", required=True, help="处置方案 JSON（`settle --json --out`）")
    p.add_argument("--grant-cap", type=float, dest="grant_cap", default=None,
                   help="同 settle：临时改本级额度，用来复现越权拦截")
    p.set_defaults(func=run_review)

    p = sub.add_parser("run", help="一条命令跑完：接报 → 技术判断 → 授权 → 复盘")
    _add_ticket_opts(p)
    _add_model_opts(p, out=False)
    _add_cost_opts(p)
    _add_policy_opts(p)
    p.add_argument("--grant-cap", type=float, dest="grant_cap", default=None,
                   help="同 settle：临时改本级额度，用来复现越权拦截")
    p.add_argument("--outdir",
                   default=str(Path(os.environ.get("TEMP") or ".") / "support-crew-out"),
                   help="产物目录（**必须在包外**）：result.json / REPORT.md / state.json")
    p.add_argument("--force", action="store_true", help="忽略断点，从头重跑（会重新花钱）")
    p.set_defaults(func=run_run)

    p = sub.add_parser("log", help="把 run 落下的处置台账读出来（零成本）")
    p.add_argument("--result", help="run 的 result.json")
    p.add_argument("--outdir", help="或给 run 的 --outdir（读里面的 result.json）")
    _add_json(p)
    p.add_argument("--out", help="把台账写到这个文件")
    p.set_defaults(func=run_log)

    p = sub.add_parser("cost", help="报价：这次处置大概花多少 token（金额要你填单价）")
    p.add_argument("--file", help="按这份工单估")
    p.add_argument("--text", help="或直接给工单文本")
    p.add_argument("--rounds", type=int, default=1, help="余量倍数，默认 1（处置没有重跑）")
    _add_cost_opts(p)
    _add_json(p)
    p.add_argument("--out", help="把报价写到这个文件")
    p.set_defaults(func=run_cost)

    p = sub.add_parser("models", help="列出 api.a7w.cn 当前在架的模型（免费）")
    p.add_argument("--type", default="text", help="模型类型，默认 text；传 all 看全部")
    p.add_argument("--key", help="临时指定 A7W API Key")
    _add_json(p)
    p.set_defaults(func=run_models)

    try:
        a = ap.parse_args(argv_eff)
    except SystemExit as exc:
        # argparse 的参数错（退出码 2）也要给信封；--help（0）不算失败
        if exc.code not in (0, None):
            _json_fail(exc.code, "usage", "命令行参数错误（用法见 stderr）")
        raise
    # 补默认值（子命令用 set_defaults 声明过的字段在各命令里都能读到）
    for k, v in (("json", False), ("out", None), ("dry_run", False),
                 ("no_json_mode", False), ("key", None),
                 ("budget", None), ("price_in", None), ("price_out", None),
                 ("force", False), ("rounds", 1),
                 ("outdir", None), ("model", DEFAULT_MODEL), ("temperature", 0.5),
                 ("max_tokens", 4096), ("file", None), ("text", None),
                 ("card", None), ("diag", None), ("settle", None),
                 ("result", None), ("type", "text"), ("policy", None),
                 ("as_role", None), ("grant_cap", None)):
        if not hasattr(a, k):
            setattr(a, k, v)
    a._pol = None
    kind, msg, detail = None, None, None
    rc = EXIT_OK
    try:
        rc = a.func(a)
    except (UsageError, PackagePathError) as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc = EXIT_USAGE
        kind, msg = "usage", str(exc)
    except GateFail as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc = EXIT_GATE
        kind, msg = "gate", str(exc)
    except BudgetStop as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc = EXIT_BUDGET
        kind, msg = "budget", str(exc)
    except SupportError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc = getattr(exc, "exit_code", EXIT_CALL)
        kind, msg = _KIND_BY_EXIT.get(rc, "call"), str(exc)
    except a7w.A7wError as exc:
        sys.stderr.write("失败：{}\n".format(exc))
        rc, kind, msg = EXIT_CALL, "call", str(exc)
    except KeyboardInterrupt:
        sys.stderr.write("已中断\n")
        rc, kind, msg = EXIT_INTERRUPT, "interrupt", "用户中断（Ctrl+C）"
    if rc:
        reason = _JSON["reason"] or {}
        _json_fail(rc, reason.get("kind") or kind,
                   reason.get("message") or msg, reason.get("detail"), a)
    return rc


def main(argv=None):
    """顶层入口。

    只在这一层兜异常：`--json` 下把**没预料到的异常**也变成信封（kind=internal，
    退出码 1），同时把完整 traceback **原样**写到 stderr —— 报 bug，不藏 bug。
    非 `--json` 时异常照旧冒泡，行为与以前完全一致。
    """
    argv_eff = list(argv) if argv is not None else sys.argv[1:]
    _JSON["stdout"] = sys.stdout          # 记住真 stdout（信封不许被重定向吞掉）
    _JSON["want"] = "--json" in argv_eff  # argparse 失败时还没有 a，先按命令行判断
    _JSON["emitted"] = False
    _JSON["reason"] = None
    try:
        return _main(argv_eff)
    except Exception as exc:                      # noqa: BLE001 —— 故意的：契约要求给信封
        if not _JSON["want"]:
            raise                                 # 非 --json：原样冒泡
        traceback.print_exc()                     # 完整栈 → stderr（不吞、不截断）
        _json_internal(exc)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    sys.exit(main())
