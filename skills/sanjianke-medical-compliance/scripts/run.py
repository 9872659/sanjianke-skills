#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 医疗合规素材（sanjianke-medical-compliance）

医美 / 健康 / 口腔机构的日常素材：一条 30 秒竖版短视频 + 一套图文。本包的重点
不是产能，是**开工前那道合规闸门**：任何一条 prompt、一段口播、一条文案，先过
本地检查器（0 点、0 请求），过了才允许花钱调接口。

## 四条底层能力（价目 2026-11-08 现查 GET /api/v1/pricing）

  出图    gpt-image-2.6  POST /api/v1/images/generations            6 点/张
  配音    voice_tts      POST /api/v1/apps/voice_tts/tts            x3（约 0.18 点/字）
  口播    pic_lipsync    POST /api/v1/apps/pic_lipsync/submit       15 点/秒（声明保底 50）
  成片    full_video     POST /api/v1/apps/full_video/submit        480P 14 / 768P 28 /
                                                                    1080P 60 / 2K 80 / 4K 80 点/秒
  上传    /api/v1/upload                                             0 点（cost:0）
  查任务  GET /api/v1/tasks/<id>                                     0 点

  images/generations 不在价目表里（pricing 115 个键里没有它），单价来自文档
  6 点/张 + 流水实证：2026-11-08 01:45:25 / 01:46:12 两笔
  `-6  sync:/api/v1/images/generations`。

## 三条用钱换来的规矩（都做成了默认动作）

  1. 不要 GET /api/v1/apps/<app> 去看 schema。这条命中 /apps/<app>/* 的通配计价，
     按该应用单价**即时扣费、不退**（实测 dressing_diffusion 200 点、nano_banana
     72 点各一笔）。本包只读 GET /api/v1/apps 列表（cost:0）+ GET /api/v1/pricing。
  2. 也不要用「缺必填参数」的 /submit 当探针。pic_lipsync / full_video 是
     reserve_sync 口径：先冻结点数、再参数校验、再全额退 —— 净额 0，但钱包被
     短暂动过。本包 doctor 一条应用层 submit 都不发。
  3. 轮询只走 GET /api/v1/tasks/<task_id>（cost:0）。应用层 /query 与 submit 同
     path 计价，查一次算不算钱说不清，本包不拿它轮询。

## 合规检查器（本包的核心，全部本地）

  COMPLIANCE_GROUPS  15 类表述，分两级：
                     一票否决（9 类）疗效承诺 / 有效率 / 术前术后 / 患者名义 /
                     绝对化 / 容貌焦虑 / 未成年 / 免费引流 / AI 作疗效示意
                     待改写（6 类）低价引流 / 代言背书 / 疾病药品 / 进口资质 /
                     名词炒作 / 分期诱导
  REQUIRED           6 项必标：执业许可证登记号 / 广告审查文号 / 广告标识 /
                     风险提示 / 机构全称与项目 / 项目与价格
  AI_REQUIRED        AI 素材再加一项：画面角标「AI 生成 · 场景示意，非真人案例」

  命中一票否决 → 出口码 2，一个请求都不发；只命中待改写 → 打印替代写法继续。
  `--strict` 把待改写与必标项缺失也升级成拦截。

## 子命令

  catalog    四条能力 + 现查单价 + 五档分辨率（免费）
  cost       一条 / 一天 3 条 / 一周 15 条要多少钱（免费，纯本地）
  check      合规检查器：15 类表述 + 6 项必标 + 人工复核清单（免费，纯本地）
  checklist  必标项模板 + 人工复核 8 条 + 交付清单 7 项（免费，纯本地）
  doctor     自检 Key / 应用 / 价目 / 5 个端点，前后比对流水证 0 点（免费）
  upload     上传本地图/音频，拿白名单地址（免费）
  image      出图，6 点/张（要 --yes，先过合规）
  tts        配音，约 0.18 点/字（要 --yes，先过合规）
  lipsync    图片口播，15 点/秒（要 --yes，先过合规）
  video      成片空镜 / 整片，按秒 x 分辨率（要 --yes，先过合规）
  status     查任务（免费）
  log        本地台账

## 用法

  python3 scripts/run.py check --text "一次见效，永久不反弹" --asset video
  python3 scripts/run.py checklist
  python3 scripts/run.py cost --avatar-seconds 20 --broll-seconds 10
  python3 scripts/run.py image --prompt "暖光诊室环境，器械特写，无人物" --n 4 --yes

Key：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`。
**需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。**

遇到问题看 SKILL.md 末尾「联系我们」。
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
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

IMG_PATH = API_PREFIX + "/images/generations"
TTS_PATH = API_PREFIX + "/apps/voice_tts/tts"
LIPSYNC_PATH = API_PREFIX + "/apps/pic_lipsync/submit"
VIDEO_PATH = API_PREFIX + "/apps/full_video/submit"
UPLOAD_PATH = API_PREFIX + "/upload"

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "compliance")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-medical-compliance/%s" % VERSION

# ── 单价（GET /api/v1/pricing 2026-11-08 现查，1 元 = 100 点）────────────────
POINTS_PER_YUAN = 100
IMG_MODEL = "gpt-image-2.6"
IMG_POINTS = 6                       # 点/张，与尺寸无关（文档 + 流水实证 -6）
IMG_SIZE = "1024x1536"

TTS_MODEL = "s2-pro"
TTS_PER_CHAR = 0.18                  # 点/字：voice_tts/* markupPercent 200（上游 x3）
TTS_MAX_CHARS = 500

LIPSYNC_MODEL = "super-lipsync-pro"
LIPSYNC_PER_SECOND = 15              # 上游 standard 3 点/秒 x5（markupPercent 400）
LIPSYNC_FLOOR = 50                   # 价目 minPoints 声明值
LIPSYNC_QUALITIES = ["standard", "fast", "max"]

VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}
RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["9:16", "16:9", "3:4", "1:1", "adaptive"]
VIDEO_CLIP_MIN, VIDEO_CLIP_MAX = 4, 15

DEFAULT_BUDGET = 5000                # 点 = 50 元

ASSETS = ["video", "image", "voice", "copy"]

# ── 平台尺寸（发布页当期口径）───────────────────────────────────────────────
PLATFORMS = {
    "douyin": dict(name="抖音", ratio="9:16", size="1080x1920", maxSeconds=60),
    "shipinhao": dict(name="视频号", ratio="9:16", size="1080x1920", maxSeconds=60),
    "xiaohongshu": dict(name="小红书", ratio="3:4", size="1080x1440", maxSeconds=90),
    "dianping": dict(name="点评 / 团购页", ratio="3:4", size="1080x1440", maxSeconds=30),
}
PLATFORM_KEYS = list(PLATFORMS)

# ── 合规检查器：15 类表述（level=block 一票否决 / warn 待改写）───────────────
# 依据：《广告法》第九条与第十六条、《医疗广告管理办法》、《医疗美容广告执法指南》
#       （2021）、《互联网广告管理办法》。terms 走子串匹配，patterns 走正则。
COMPLIANCE_GROUPS = [
    dict(key="efficacy", name="疗效承诺", level="block",
         terms=["一次见效", "一次就好", "立竿见影", "马上变美", "立刻变美", "秒变",
                "三天见效", "七天见效", "一周见效", "永久", "终生", "一劳永逸",
                "根治", "彻底解决", "彻底消除", "绝不复发", "不再复发", "包好",
                "保证有效", "保证效果", "100% 有效", "百分之百有效", "零风险",
                "绝对安全", "无副作用", "无毒副作用", "无任何风险", "无恢复期",
                "随做随走", "一次到位", "一步到位", "当天上班"],
         patterns=[r"\d+\s*天\s*(见效|变美|恢复)"],
         fix="「按疗程评估，效果因人而异」，把结论交给面诊与个体差异"),
    dict(key="efficacy_rate", name="疗效数据", level="block",
         terms=["有效率", "治愈率", "成功率", "满意度", "好评率", "复购率",
                "临床验证", "临床证明", "临床数据显示", "九成以上"],
         patterns=[r"\d+\s*%\s*(有效|见效|满意|成功)"],
         fix="把百分比换成可核对的服务数据：接诊量、复诊率口径、医生执业年限"),
    dict(key="before_after", name="术前术后 / 前后对比", level="block",
         terms=["前后对比", "术前术后", "术前", "术后", "对比图", "对比照",
                "效果对比", "蜕变", "逆袭", "华丽转身", "判若两人", "案例对比",
                "真人对比", "before", "after"],
         fix="「项目过程 / 器械 / 环境」的画面，把对比留给面诊室里的私下沟通"),
    dict(key="patient", name="患者名义 / 见证", level="block",
         terms=["患者", "病友", "求美者", "案例分享", "素人改造", "真人反馈",
                "我做了", "我在这里做的", "亲历", "亲身经历", "见证人",
                "我的主治", "医生说我"],
         fix="机构视角的客观描述；用户评价走平台原生评价区，不剪进广告"),
    dict(key="absolute", name="绝对化用语", level="block",
         terms=["最好", "最佳", "最优", "最强", "最高级", "最权威", "最专业",
                "全网最", "史上最", "全国最", "第一品牌", "全国第一", "行业第一",
                "销量第一", "排名第一", "第一选择", "唯一", "独家", "顶级",
                "顶尖", "国家级", "世界级", "首选", "王牌", "权威专家",
                "领先品牌", "领导者"],
         fix="去掉排序词，写清比较维度与时间点：哪一年、哪个范围、谁统计"),
    dict(key="anxiety", name="容貌焦虑 / 负面关联", level="block",
         terms=["容貌焦虑", "颜值焦虑", "长得丑", "太丑", "变丑", "低能", "懒惰",
                "贫穷", "影响运势", "面相", "旺夫", "克夫", "招财", "改运",
                "改变命运", "嫁得好", "嫁不出去", "找不到对象", "面试失败",
                "被嫌弃", "自卑", "没自信", "毁一生", "丑小鸭"],
         fix="写「为什么现在方便做」而不是「不做会怎样」：时间、恢复期、复诊安排"),
    dict(key="minor", name="未成年人相关", level="block",
         terms=["未成年", "未满18", "未满十八", "学生党", "学生优惠", "高中生",
                "中学生", "初中生", "青少年", "少女", "校园"],
         fix="成年求美者口径；涉及未成年人的内容走监护人同意与线下告知"),
    dict(key="free_bait", name="免费 / 0 元引流", level="block",
         terms=["免费体验", "免费领取", "免费做", "免费送", "0元", "零元",
                "免费名额", "白送", "不要钱"],
         fix="把价格写成「项目名 + 计价单位 + 适用范围」，体验价注明包含项与不含项"),
    dict(key="ai_efficacy", name="AI 素材作疗效示意", level="block",
         terms=["疗效示意", "疗效展示", "效果示意", "术后效果", "前后效果",
                "变美效果", "案例效果", "效果对比图", "模拟术后", "预见效果",
                "AI 效果图"],
         fix="AI 图只做场景 / 器械 / 环境示意，画面标「AI 生成 · 场景示意，非真人案例」"),
    dict(key="price_bait", name="低价引流", level="warn",
         terms=["秒杀", "限时抢", "抢购", "团购", "砍价", "低价", "9.9", "99元",
                "史上最低价", "冰点价"],
         fix="标注原价、活动期与服务范围，价格与实际结算一致"),
    dict(key="endorser", name="代言 / 专家背书", level="warn",
         terms=["代言", "明星同款", "网红同款", "达人推荐", "博主推荐",
                "医生推荐", "专家推荐", "名医", "院长亲诊", "主任医师",
                "教授团队", "院士", "军医", "公立医院专家", "三甲专家"],
         fix="只写本院执业医师的姓名与执业范围，资质进机构介绍，不进广告主张"),
    dict(key="disease", name="疾病 / 药品表述", level="warn",
         terms=["治疗", "治愈", "诊断", "处方", "药物", "抗生素", "激素",
                "适应症", "临床", "医学级", "医用级", "药妆", "消炎", "抗炎"],
         fix="医疗美容项目按注册名写「改善 / 维护」，医疗行为放到院内知情同意书"),
    dict(key="origin", name="进口 / 资质背书", level="warn",
         terms=["进口", "原装进口", "韩国技术", "日本技术", "德国设备",
                "美国设备", "国际认证", "FDA认证", "CE认证", "专利认证",
                "独家引进", "全球首发", "三甲"],
         fix="写器械注册证编号与厂家，去掉「哪国技术」这类暗示"),
    dict(key="hype_tech", name="名词炒作", level="warn",
         terms=["干细胞", "基因", "纳米", "细胞再生", "生长因子", "逆龄",
                "冻龄", "返老还童", "童颜", "量子", "生物科技", "胎盘素",
                "人胎素"],
         fix="用项目注册名与作用层次描述，机制讲不清就不写"),
    dict(key="loan", name="分期 / 诱导消费", level="warn",
         terms=["0首付", "零首付", "医美贷", "分期", "免息", "白条", "花呗",
                "先美后付", "轻松付"],
         fix="把支付方式放到成单页，广告里只写项目与总价"),
]

# ── 必标项（6 项，缺一项就在 check 里点名）──────────────────────────────────
REQUIRED = [
    dict(key="license", name="医疗机构执业许可证登记号",
         pat=r"(执业许可|许可证|登记号|PDY|MA)[^\n，。；]{0,12}\d{4,}",
         fix="正文末尾写《医疗机构执业许可证》登记号 PDY…，与副本逐字一致"),
    dict(key="adreview", name="医疗广告审查证明文号",
         pat=r"(医广|广审|广告审查|审查证明)",
         fix="医疗广告审查证明文号（X）医广【2026】第 03-15-0123 号"),
    dict(key="admark", name="广告标识",
         pat=r"广告",
         fix="标题或首帧标「广告」，正文首行再标一次"),
    dict(key="risk", name="风险提示与个体差异",
         pat=r"(风险|个体差异|因人而异|面诊|医嘱|医生评估|以实际)",
         fix="效果因人而异，具体方案需面诊评估；并列出该项目常见风险"),
    dict(key="org", name="机构全称与项目",
         pat=r"(医院|门诊部|门诊|诊所|医疗美容|整形|口腔|医美)",
         fix="机构全称照写（与执业许可证一致），项目用注册名"),
    dict(key="price", name="项目与价格口径",
         pat=r"(\d+\s*元|价格|起价|套餐|计价|疗程|单次)",
         fix="写项目名 + 计价单位 + 价格区间，如实标价，加项单列"),
]

AI_REQUIRED = dict(
    key="ai", name="AI 生成素材标识",
    pat=r"(AI\s*生成|AI\s*合成|人工智能生成|合成画面|AI\s*示意|AI\s*图)",
    fix="画面角标标「AI 生成 · 场景示意，非真人案例」，交付单登记素材来源")

# ── 人工复核 8 条（机检查不出来的，必须有人看一眼）──────────────────────────
REVIEW = [
    "执业许可证登记号与机构全称逐字核对（对副本原件，不是对上一版文案）",
    "广告审查证明文号在有效期内，且审查范围覆盖本条片子里的项目",
    "出镜人物有书面肖像授权：范围、期限、平台、可否二次剪辑",
    "出镜的「医生」是本单位执业医师，姓名与执业证书一致；数字人标注合成",
    "每张图 / 每段片都能对上素材来源：实拍 / AI 生成 / 授权图库（交付单登记）",
    "风险提示与个体差异在片尾和文案各出现一次，字够大、停留不少于 3 秒",
    "价格与服务范围一致：套餐外的加项、麻醉、复诊、药费写清",
    "发布前由机构合规负责人签字，check 输出与本单一起留档",
]

# ── 交付清单（一单 = 一条 30 秒竖版短视频，`checklist` 原样打印）─────────────
DELIVERY = [
    dict(no=1, name="主片", spec="1080x1920 / H.264 / 30 秒 / 9:16", qty="1",
         file="20261108_水光_示例医疗美容门诊部_douyin_30s.mp4"),
    dict(no=2, name="竖版钩子切片", spec="1080x1920 / H.264 / 15 秒", qty="1",
         file="*_15s_hook.mp4"),
    dict(no=3, name="环境 / 器械图", spec="1024x1536 / png（AI 生成须标角标）", qty="4",
         file="*_clinic.png · *_device.png · *_reception.png · *_detail.png"),
    dict(no=4, name="口播音频", spec="mp3 / 44.1kHz / 单条 500 字内", qty="1",
         file="*_voice.mp3"),
    dict(no=5, name="封面", spec="1080x1440 / png（可裁 3:4）", qty="1",
         file="*_cover.png"),
    dict(no=6, name="文案包", spec="标题 3 条 + 简介 1 条 + 标签 6 个", qty="1",
         file="*_copy.md"),
    dict(no=7, name="合规单", spec="check 输出 + 6 项必标 + 复核签字", qty="1",
         file="*_compliance.md"),
]


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
        except Exception:                                            # noqa: BLE001
            pass
    return key, (host or DEFAULT_HOST)


def http_json(method, url, key, body=None, timeout=120, retries=2):
    data, hdr = None, {"Authorization": "Bearer " + key,
                       "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                return x.status, x.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries - 1:
                last = e
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise Fail("call", "连不上 %s：%s（已重试 %d 次）"
                       % (url, getattr(e, "reason", e), retries - 1), EXIT_CALL)
        except Exception as e:                                       # noqa: BLE001
            raise Fail("call", "请求异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)
    raise Fail("call", "连不上 %s：%s" % (url, last), EXIT_CALL)


def http_multipart(url, key, fields, files, timeout=600):
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
        with open(path, "rb") as fh:
            buf.write(fh.read())
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
    except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
        raise Fail("call", "连不上 %s：%s" % (url, getattr(e, "reason", e)), EXIT_CALL)
    except Exception as e:                                           # noqa: BLE001
        raise Fail("call", "上传异常：%s: %s" % (type(e).__name__, e), EXIT_CALL)


def url_allowed(u):
    """平台只收本站托管的地址（videoUrl / image_url 白名单）。返回 (ok, 归属)。"""
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:                                                # noqa: BLE001
        return False, "URL 解析失败"
    host = (p.hostname or "").lower()
    path = p.path or ""
    if host == "vr.a7w.cn" or host.endswith(".a7w.cn"):
        return True, "本站"
    if host == "cdn2.jiujiushuyuan.cn" and path.startswith("/vr/"):
        return True, "本站七牛"
    if host == "oss.gpu.likeadmin.cn" and path.startswith("/openapi/"):
        return True, "本站上传接口"
    return False, host or u[:60]


def jloads(t):
    try:
        return json.loads(t)
    except Exception:                                                # noqa: BLE001
        return None


def err_text(st, txt):
    d = jloads(txt)
    if isinstance(d, dict):
        e = d.get("error")
        if isinstance(e, dict):
            s = " · ".join([b for b in (e.get("message") or "", e.get("code") or "") if b])
            if s:
                return s[:300]
        for k in ("message", "msg"):
            if d.get(k):
                return str(d[k])[:300]
        if d.get("code"):
            return str(d["code"])[:300]
    if (txt or "").lstrip().startswith("<"):
        return "网关回了 HTML（HTTP %s），这条前缀下没有该端点" % st
    return (txt or "").replace("\n", " ")[:240]


def payload_of(d):
    """拆信封：{"code":1,"data":{…}} / {"data":{…}} / 裸对象，三种都兜住。"""
    if not isinstance(d, dict):
        return {}
    if d.get("code") in (0, 1) and isinstance(d.get("data"), (dict, list)):
        return d["data"]
    return d


def find_media_url(d):
    """从任意层级里捞第一个 http 开头的结果地址。"""
    if isinstance(d, dict):
        for k in ("audio_url", "audioUrl", "video_url", "videoUrl", "url", "artifactUrl"):
            v = d.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in d.values():
            u = find_media_url(v)
            if u:
                return u
    elif isinstance(d, list):
        for v in d:
            u = find_media_url(v)
            if u:
                return u
    return None


def fmt_pts(n):
    try:
        return "{:,}".format(int(round(float(n))))
    except Exception:                                                # noqa: BLE001
        return str(n)


def yuan(pts):
    return round(float(pts) / POINTS_PER_YUAN, 2)


def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width, left=True):
    s = str(s)
    gap = " " * max(0, width - _w(s))
    return s + gap if left else gap + s


def today():
    return time.strftime("%Y%m%d")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dir(p):
    try:
        os.makedirs(p, exist_ok=True)
        return p
    except Exception as e:                                           # noqa: BLE001
        raise Fail("internal", "建目录失败：%s（%s）" % (p, e), EXIT_INTERNAL)


def write_text(path, text):
    ensure_dir(os.path.dirname(path) or ".")
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return path


def ledger_add(rec):
    try:
        ensure_dir(HOME_DIR)
        arr = []
        if os.path.isfile(LEDGER):
            arr = json.load(io.open(LEDGER, encoding="utf-8"))
        arr.append(rec)
        io.open(LEDGER, "w", encoding="utf-8", newline="\n").write(
            json.dumps(arr[-200:], ensure_ascii=False, indent=1))
    except Exception:                                                # noqa: BLE001
        pass


def gate(a, cost, basis):
    """两道闸门：超预算退 5（一个请求都不发）；没 --yes 退 4（并报要花多少）。"""
    if cost > a.budget:
        raise Fail("budget",
                   "预计 %d 点（%.2f 元）超过 --budget %d 点：%s。"
                   "一个请求都没发。调大 --budget（单位：点，1 元 = 100 点）再试。"
                   % (cost, yuan(cost), a.budget, basis), EXIT_BUDGET)
    if not a.yes and not a.dry_run:
        raise Fail("confirm",
                   "这会真实扣费约 %d 点（%.2f 元）：%s。确认请加 --yes。"
                   % (cost, yuan(cost), basis), EXIT_CONFIRM)
    return cost


# ───────────────────────── 合规检查器（本地，0 点 0 请求）────────────────────
def scan_compliance(text, asset=None, strict=False):
    text = text or ""
    low = text.lower()
    blocked, warned = [], []
    for g in COMPLIANCE_GROUPS:
        found = []
        for t in g.get("terms") or []:
            pos = low.find(t.lower())
            if pos >= 0:
                found.append((t, pos))
        for pat in g.get("patterns") or []:
            for m in re.finditer(pat, text):
                found.append((m.group(0), m.start()))
        if not found:
            continue
        seen, row = set(), []
        for term, pos in sorted(found, key=lambda x: x[1]):
            if term in seen:
                continue
            seen.add(term)
            row.append(term)
        item = dict(key=g["key"], name=g["name"], level=g["level"],
                    terms=row[:8], at=min(pos for _, pos in found) + 1,
                    fix=g["fix"])
        (blocked if g["level"] == "block" else warned).append(item)

    missing = []
    for r in REQUIRED:
        if not re.search(r["pat"], text):
            missing.append(dict(key=r["key"], name=r["name"], fix=r["fix"]))
    ai_missing = False
    if asset in ("image", "video"):
        if not re.search(AI_REQUIRED["pat"], text, re.I):
            ai_missing = True
            missing.append(dict(key=AI_REQUIRED["key"], name=AI_REQUIRED["name"],
                                fix=AI_REQUIRED["fix"]))

    ok = not blocked and not (strict and missing)
    return dict(ok=ok, blocked=blocked, warned=warned, missing=missing,
                asset=asset or "copy", chars=len(text),
                strict=bool(strict), aiRequired=asset in ("image", "video"),
                requiredTotal=len(REQUIRED) + (1 if asset in ("image", "video") else 0),
                requiredPresent=len(REQUIRED) + (1 if asset in ("image", "video") else 0)
                - len(missing))


def compliance_gate(text, asset=None, label="文案", strict=False):
    """生成前先过一遍：命中一票否决 → 退 2，一个请求都不发。"""
    r = scan_compliance(text, asset, strict)
    if r["blocked"]:
        lines = ["合规闸门拦下（%s，%d 字）：这次一个请求都没发。" % (label, len(text))]
        for h in r["blocked"][:6]:
            lines.append("  · %s：%s → %s"
                         % (h["name"], "、".join(h["terms"][:4]), h["fix"]))
        if len(r["blocked"]) > 6:
            lines.append("  · 还有 %d 类，跑 check 看完整清单" % (len(r["blocked"]) - 6))
        lines.append("  先改文案：python3 scripts/run.py check --text \"…\"")
        raise Fail("usage", "\n".join(lines), EXIT_USAGE)
    if r["warned"]:
        say("合规提示（可继续）：%s"
            % " / ".join("%s：%s" % (h["name"], "、".join(h["terms"][:3]))
                         for h in r["warned"][:4]))
    return r


def cmd_check(a, key, host):
    text = (a.text or "").strip()
    if not text and a.file:
        if not os.path.isfile(a.file):
            raise Fail("usage", "找不到文件：%s" % a.file, EXIT_USAGE)
        text = io.open(a.file, encoding="utf-8").read()
    if not text:
        raise Fail("usage", "给 --text \"文案\" 或 --file 文案.md 再检查", EXIT_USAGE)
    r = scan_compliance(text, a.asset, a.strict)
    out = {"ok": r["ok"], "chars": r["chars"], "asset": r["asset"],
           "strict": r["strict"],
           "blocked": r["blocked"], "warned": r["warned"], "missing": r["missing"],
           "required": {"present": r["requiredPresent"], "total": r["requiredTotal"]},
           "review": REVIEW if a.review else [],
           "estimatedPoints": 0, "requests": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if r["ok"] else EXIT_USAGE
    print("合规检查 · 本地 · 0 点 0 请求")
    print()
    print("  材料：%d 字 · 素材：%s%s" % (r["chars"], r["asset"],
                                       " · strict" if r["strict"] else ""))
    print()
    print("  一票否决（9 类）：%d 条" % len(r["blocked"]))
    if not r["blocked"]:
        print("    √ 一条都没命中")
    for h in r["blocked"]:
        print("    × %s  命中「%s」  第 %d 字" % (h["name"], "、".join(h["terms"][:4]),
                                                h["at"]))
        print("        改成：%s" % h["fix"])
    print()
    print("  待改写（6 类）：%d 条" % len(r["warned"]))
    if not r["warned"]:
        print("    √ 一条都没命中")
    for h in r["warned"]:
        print("    ! %s  命中「%s」" % (h["name"], "、".join(h["terms"][:4])))
        print("        改成：%s" % h["fix"])
    print()
    print("  必标项：%d/%d" % (r["requiredPresent"], r["requiredTotal"]))
    for m in r["missing"]:
        print("    × %s" % m["name"])
        print("        补：%s" % m["fix"])
    if not r["missing"]:
        print("    √ 全齐")
    print()
    if r["blocked"]:
        print("  结论：先改上面 %d 条一票否决，再提交生成（改了不花钱，重出了才花钱）。"
              % len(r["blocked"]))
    elif r["missing"]:
        print("  结论：红线干净，补 %d 项必标就能发；人工复核 %d 条见 checklist。"
              % (len(r["missing"]), len(REVIEW)))
    else:
        print("  结论：机检全过。人工复核 %d 条走一遍再签字。" % len(REVIEW))
    return 0 if r["ok"] else EXIT_USAGE


def cmd_checklist(a, key, host):
    out = {"ok": True, "required": [{"key": r["key"], "name": r["name"],
                                     "example": r["fix"]} for r in REQUIRED],
           "aiRequired": dict(key=AI_REQUIRED["key"], name=AI_REQUIRED["name"],
                              example=AI_REQUIRED["fix"]),
           "review": REVIEW,
           "delivery": DELIVERY, "estimatedPoints": 0, "requests": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("必标项模板（6 + 1 项，直接抄进发布文案与片尾）· 0 点")
    print()
    for r in REQUIRED:
        print("  □ %s" % r["name"])
        print("      %s" % r["fix"])
    print("  □ %s（AI 图 / AI 片才有）" % AI_REQUIRED["name"])
    print("      %s" % AI_REQUIRED["fix"])
    print()
    print("人工复核 8 条（机检替代不了的部分）")
    for i, s in enumerate(REVIEW, 1):
        print("  %d. %s" % (i, s))
    print()
    print("交付清单（一单 = 一条 30 秒竖版短视频）")
    print("  %-3s %-16s %-44s %-4s %s" % ("#", "交付物", "规格", "数量", "命名"))
    print("  " + "-" * 108)
    for d in DELIVERY:
        print("  %-3d %-16s %-44s %-4s %s"
              % (d["no"], d["name"], d["spec"], d["qty"], d["file"]))
    print()
    print("  一单 7 项，命名用「日期_项目_机构_平台_秒数」，一个项目一个目录。")
    return 0


# ───────────────────────── 免费：目录与成本 ─────────────────────────
CAPS = [
    dict(key="image", name="出图", path=IMG_PATH, model=IMG_MODEL,
         price="6 点/张", note="环境 / 器械 / 空间示意，与尺寸无关"),
    dict(key="tts", name="配音", path=TTS_PATH, model=TTS_MODEL,
         price="约 0.18 点/字", note="空镜旁白、片头片尾口播（上游 x3）"),
    dict(key="lipsync", name="图片口播", path=LIPSYNC_PATH, model=LIPSYNC_MODEL,
         price="15 点/秒", note="医师形象 / 数字人口播，声明保底 50 点"),
    dict(key="video", name="成片", path=VIDEO_PATH, model="full-video",
         price="60 点/秒（1080P）", note="空镜、整片，按秒 x 分辨率"),
    dict(key="upload", name="上传", path=UPLOAD_PATH, model="-",
         price="0 点", note="图 / 音频转白名单地址，喂给口播与成片"),
    dict(key="task", name="查任务", path=API_PREFIX + "/tasks/<task_id>", model="-",
         price="0 点", note="轮询只走这条，别碰应用层 /query"),
    dict(key="check", name="合规检查", path="本地（不发请求）", model="-",
         price="0 点", note="15 类表述 + 6 项必标 + 人工复核清单"),
]


def cmd_catalog(a, key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    listing = (jloads(txt) or {}).get("data")
    listing = listing if isinstance(listing, list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt2) or {}).get("pricing") or {}
    rates = (pricing.get(VIDEO_PATH) or {}).get("resolutionRates") or {}
    rows = []
    for c in CAPS:
        row = dict(c)
        if c["key"] == "video" and rates:
            row["price"] = " / ".join("%s %d" % (r, int(rates[r] or 0)) for r in RESOLUTIONS
                                      if rates.get(r) is not None)
        rows.append(row)
    out = {"ok": True, "appsHttp": st, "pricingHttp": st2, "appCount": len(listing),
           "capabilities": rows, "videoRates": rates or VIDEO_RATES,
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "platforms": [dict(key=k, name=v["name"], ratio=v["ratio"],
                              size=v["size"], maxSeconds=v["maxSeconds"])
                         for k, v in PLATFORMS.items()],
           "delivery": DELIVERY, "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 医疗合规素材 —— 四条能力 + 三项免费")
    print()
    print("  %-10s %-38s %-24s %s" % ("工序", "端点", "单价", "用在哪"))
    print("  " + "-" * 100)
    for r in rows:
        print("  %-10s %-38s %-24s %s" % (r["name"], r["path"], r["price"], r["note"]))
    print()
    print("  在架应用 %d 个（GET /apps，cost:0）· 价目表 %d 个键（GET /pricing）"
          % (len(online) or len(listing), len(pricing)))
    print("  成片按秒 x 分辨率：%s" % " / ".join(
        "%s %d" % (r, VIDEO_RATES[r]) for r in RESOLUTIONS))
    print()
    print("  一单 7 项：主片 · 钩子切片 · 4 张环境图 · 口播音频 · 封面 · 文案包 · 合规单")
    print("  平台：%s" % " · ".join("%s %s" % (v["name"], v["size"])
                                   for v in PLATFORMS.values()))
    print()
    print("  先跑 check（0 点）再开拍：15 类红线表述 + 6 项必标，命中的直接给替代写法。")
    return 0


def build_cost(avatar_seconds, broll_seconds, images, tts_chars, resolution,
               jobs, music=0):
    img = IMG_POINTS * max(0, int(images))
    tts = max(0, int(round(float(tts_chars) * TTS_PER_CHAR)))
    lip = max(LIPSYNC_FLOOR, int(round(LIPSYNC_PER_SECOND * float(avatar_seconds)))) \
        if avatar_seconds else 0
    vid = VIDEO_RATES[resolution] * max(0, int(broll_seconds))
    one = img + tts + lip + vid + int(music)
    return dict(image=img, tts=tts, lipsync=lip, video=vid, music=int(music),
                one=one, jobs=one * max(1, int(jobs)),
                day=one * 3, week=one * 15)


def cmd_cost(a, key, host):
    b = build_cost(a.avatar_seconds, a.broll_seconds, a.images, a.tts_chars,
                   a.resolution, a.jobs, a.music)
    out = {"ok": True, "resolution": a.resolution, "avatarSeconds": a.avatar_seconds,
           "brollSeconds": a.broll_seconds, "images": a.images, "ttsChars": a.tts_chars,
           "breakdown": b, "oneJob": b["one"], "billedJobs": b["jobs"],
           "day3": b["day"], "week15": b["week"],
           "yuan": {"one": yuan(b["one"]), "jobs": yuan(b["jobs"]),
                    "day3": yuan(b["day"]), "week15": yuan(b["week"])},
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "compliancePoints": 0,
           "notes": ["1 元 = 100 点；单价取自 GET /api/v1/pricing 2026-11-08",
                     "check / checklist 全在本地，0 点 0 请求",
                     "口播按 15 点/秒，声明保底 50 点（价目 minPoints）",
                     "配音按 0.18 点/字估（voice_tts 上游 x3，以 usage.points_cost 为准）",
                     "成片按秒 x 分辨率，单段 4~15 秒"]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("预估成本（1 元 = 100 点）· 合规检查 0 点")
    print()
    print("  一单 = %d 秒竖版（口播 %d 秒 + 空镜 %d 秒 + 图 %d 张 + 旁白 %d 字）"
          % (a.avatar_seconds + a.broll_seconds, a.avatar_seconds,
             a.broll_seconds, a.images, a.tts_chars))
    print("  %-14s %s" % ("出图", "%d 张 x 6 = %s 点" % (a.images, fmt_pts(b["image"]))))
    print("  %-14s %s" % ("配音", "%d 字 x 0.18 ≈ %s 点" % (a.tts_chars, fmt_pts(b["tts"]))))
    print("  %-14s %s" % ("图片口播", "%d 秒 x 15 = %s 点（保底 50）"
                        % (a.avatar_seconds, fmt_pts(b["lipsync"]))))
    print("  %-14s %s" % ("成片空镜", "%d 秒 x %d 点/秒（%s）= %s 点"
                        % (a.broll_seconds, VIDEO_RATES[a.resolution], a.resolution,
                           fmt_pts(b["video"]))))
    print("  " + "-" * 44)
    print("  一单：%s 点 = %.2f 元" % (fmt_pts(b["one"]), yuan(b["one"])))
    print("  一天 3 条：%s 点 = %.2f 元" % (fmt_pts(b["day"]), yuan(b["day"])))
    print("  一周 15 条：%s 点 = %.2f 元" % (fmt_pts(b["week"]), yuan(b["week"])))
    if a.jobs > 1:
        print("  本次 %d 条：%s 点 = %.2f 元"
              % (a.jobs, fmt_pts(b["jobs"]), yuan(b["jobs"])))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 自检（0 点）────────────────────────
def _last_log(key, host):
    st, txt = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d = jloads(txt) or {}
    logs = d.get("logs") or []
    if not logs:
        return None
    row = logs[0]
    return (row.get("at"), row.get("points"), row.get("reference"))


def cmd_doctor(a, key, host):
    checks = []
    first0 = _last_log(key, host)

    st, txt = http_json("GET", host + "/user/balance", key, timeout=40)
    d = jloads(txt) or {}
    checks.append(("Key + 余额接口可达", st == 200 and "available_points" in d,
                   "HTTP %s · 可用 %s 点 · 冻结 %s 点"
                   % (st, fmt_pts(d.get("available_points") or 0),
                      fmt_pts(d.get("frozen") or 0))))

    st2, txt2 = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    d2 = jloads(txt2) or {}
    listing = d2.get("data") if isinstance(d2.get("data"), list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    need = ["full_video", "voice_tts", "pic_lipsync"]
    miss = [c for c in need if c not in online]
    checks.append(("3 个底层应用在架（成片 / 配音 / 口播）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    lip_apis = [x.get("code") for x in (online.get("pic_lipsync", {}).get("apis") or [])]
    tts_apis = [x.get("code") for x in (online.get("voice_tts", {}).get("apis") or [])]
    checks.append(("pic_lipsync 的 submit / query 都在",
                   "submit" in lip_apis and "query" in lip_apis,
                   "接口：%s（读 /apps 列表，不发那条扣费 GET）" % " / ".join(lip_apis)))
    checks.append(("voice_tts 的 tts / tts_async / list_voices 都在",
                   all(x in tts_apis for x in ("tts", "tts_async", "list_voices")),
                   "接口 %d 个：%s" % (len(tts_apis), " / ".join(tts_apis[:4]))))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    vrule = pricing.get(VIDEO_PATH) or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 五档按秒价与线上一致",
                   st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "五档全一致" if not drift else " / ".join(drift)[:110])))

    lrule = pricing.get(LIPSYNC_PATH) or {}
    checks.append(("pic_lipsync 倍率 400（= 上游 x5）与本地口径一致",
                   int(lrule.get("markupPercent") or 0) == 400
                   and int(lrule.get("minPoints") or 0) == LIPSYNC_FLOOR,
                   "markupPercent %s · minPoints %s · 本地 %d 点/秒"
                   % (lrule.get("markupPercent"), lrule.get("minPoints"),
                      LIPSYNC_PER_SECOND)))

    trule = pricing.get(API_PREFIX + "/apps/voice_tts/*") or {}
    up_rule = pricing.get(UPLOAD_PATH) or {}
    apps_rule = pricing.get(API_PREFIX + "/apps") or {}
    checks.append(("免费口径没变：upload 0 点 · /apps 0 点 · voice_tts 倍率 200",
                   int(up_rule.get("cost") if up_rule.get("cost") is not None else 999) == 0
                   and int(apps_rule.get("cost") if apps_rule.get("cost") is not None
                           else 999) == 0
                   and int(trule.get("markupPercent") or 0) == 200,
                   "upload cost %s · /apps cost %s · voice_tts markup %s"
                   % (up_rule.get("cost"), apps_rule.get("cost"),
                      trule.get("markupPercent"))))

    st4, txt4 = http_json("POST", host + IMG_PATH, key,
                          {"model": IMG_MODEL, "prompt": ""}, timeout=60)
    d4 = jloads(txt4) or {}
    e4 = d4.get("error") if isinstance(d4.get("error"), dict) else {}
    msg4 = (e4.get("message") or err_text(st4, txt4))
    checks.append(("出图端点可用（422 即正确，零扣费）",
                   st4 == 422 and "prompt" in str(msg4).lower(),
                   "HTTP %s %s" % (st4, str(msg4)[:52])))

    st5, txt5 = http_json("POST", host + API_PREFIX + "/video/viapi/enhance", key, {},
                          timeout=60)
    d5 = jloads(txt5) or {}
    e5 = d5.get("error") if isinstance(d5.get("error"), dict) else {}
    code5 = e5.get("code") or ""
    checks.append(("视频线在参数校验就停（400 empty_url 即正确）",
                   st5 == 400 and code5 == "empty_url",
                   "HTTP %s %s" % (st5, code5 or err_text(st5, txt5)[:40])))

    st6, txt6 = http_json("GET", host + API_PREFIX + "/tasks/med-compliance-probe",
                          key, timeout=40)
    d6 = jloads(txt6) or {}
    checks.append(("任务查询 GET /tasks/<id> 可用（假 id 说任务不存在）",
                   st6 == 200 and d6.get("code") == 0,
                   "HTTP %s %s" % (st6, (d6.get("msg") or "")[:40])))

    st7, txt7 = http_multipart(host + UPLOAD_PATH, key, {}, [], timeout=60)
    d7 = jloads(txt7) or {}
    checks.append(("上传口 POST /upload 可用（缺 file 时提示补字段）",
                   st7 == 200 and d7.get("code") == 0,
                   "HTTP %s %s" % (st7, (d7.get("msg") or "")[:40])))

    second = _last_log(key, host)
    checks.append(("本轮没有新增流水（扣 0 点）", first0 == second,
                   "自检前后最新一笔流水一致" if first0 == second
                   else "出现新流水，请发出来排查"))

    st8, txt8 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d8 = jloads(txt8) or {}
    last = None
    if d8.get("logs"):
        row = d8["logs"][0]
        last = {"at": row.get("at"), "type": row.get("type"),
                "points": row.get("points"), "balanceAfter": row.get("balanceAfter"),
                "reference": row.get("reference")}

    out = {"ok": all(c[1] for c in checks), "requests": 10, "estimatedPoints": 0,
           "yuan": 0.0, "lastLedger": last, "apps": need,
           "videoRates": live or VIDEO_RATES,
           "lipsyncRule": {"markupPercent": lrule.get("markupPercent"),
                           "minPoints": lrule.get("minPoints"),
                           "perSecond": LIPSYNC_PER_SECOND},
           "ttsRule": {"markupPercent": trule.get("markupPercent"),
                       "perChar": TTS_PER_CHAR},
           "endpoints": {"image": host + IMG_PATH, "tts": host + TTS_PATH,
                         "lipsync": host + LIPSYNC_PATH, "video": host + VIDEO_PATH,
                         "upload": host + UPLOAD_PATH,
                         "task": host + API_PREFIX + "/tasks/<task_id>"},
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（只读 GET + 空 prompt 422 + 空 body 视频探针 + 缺 file 上传，"
          "全部停在扣费之前）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 44), dd))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("type") or "-", fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
    print("  本次自检 0 点、0 冻结：10 个请求里没有一条会建任务。")
    print("  应用层 /submit 探针 0 条：reserve_sync 口径会先冻结再退还，本包不碰。")
    print()
    print("  出图：POST /images/generations（6 点/张）")
    print("  配音：POST /apps/voice_tts/tts（约 0.18 点/字）· 上传：POST /upload（0 点）")
    print("  口播：POST /apps/pic_lipsync/submit（15 点/秒）")
    print("  成片：POST /apps/full_video/submit（按秒 x 分辨率）")
    return 0 if out["ok"] else EXIT_GATE


# ───────────────────────── 上传（免费）────────────────────────
def upload_file(key, host, path, timeout=600):
    if not path or not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    say("正在上传 %s（%d 字节，免费）…" % (os.path.basename(path), size))
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [("file", path)],
                            timeout=timeout)
    d = jloads(txt) or {}
    data = payload_of(d)
    got = (data.get("url") or data.get("path")) if isinstance(data, dict) else None
    if st not in (200, 201) or not got:
        raise Fail("call", "上传失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)
    ok, kind = url_allowed(got)
    return {"url": got, "size": data.get("size") or size,
            "mime": data.get("mime_type"), "allowed": ok, "hostKind": kind}


def cmd_upload(a, key, host):
    if not a.file:
        raise Fail("usage", "必须给 --file（本地图片 / 音频路径）", EXIT_USAGE)
    url = host + UPLOAD_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "file": a.file,
               "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不扣费）")
        print("  端点：POST %s（multipart，字段名 file）" % url)
        print("  文件：%s" % a.file)
        return 0
    r = upload_file(key, host, a.file, timeout=a.timeout)
    out = {"ok": True, "url": r["url"], "size": r["size"], "mime": r["mime"],
           "urlAllowed": r["allowed"], "hostKind": r["hostKind"], "estimatedPoints": 0}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已上传（0 点）")
    print("  地址：%s" % r["url"])
    print("  归属：%s（在上游白名单内，可以直接给 lipsync / video 用）" % r["hostKind"])
    return 0


# ───────────────────────── 出图（6 点/张）────────────────────────
def save_images(d, outdir, prefix, fallback_ext="png"):
    os.makedirs(outdir, exist_ok=True)
    paths, urls, src = [], [], "none"
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, list):
        return paths, urls, src
    for i, it in enumerate(data):
        if not isinstance(it, dict):
            continue
        raw = None
        if it.get("b64_json"):
            raw = base64.b64decode(it["b64_json"])
            src = "b64_json"
        elif it.get("url"):
            u = it["url"]
            # 文档：链接原样使用；urllib 必须自设 UA，否则 403
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as x:
                raw = x.read()
            src = "url"
        if not raw:
            continue
        ext = fallback_ext or "png"
        if raw[:3] == b"GIF":
            ext = "gif"
        p = os.path.join(outdir, "%s-%02d.%s" % (prefix, i + 1, ext))
        with open(p, "wb") as fh:
            fh.write(raw)
        paths.append(p)
        if it.get("url"):
            urls.append(it["url"])
    return paths, urls, src


def cmd_image(a, key, host):
    prompt = (a.prompt or "").strip()
    if not prompt:
        raise Fail("usage", "必须给 --prompt（画面描述）；文案先跑 check 再出图",
                   EXIT_USAGE)
    n = max(1, min(4, int(a.n)))
    comp = compliance_gate(prompt, "image", "出图 prompt")
    cost = IMG_POINTS * n
    gate(a, cost, "%d 张 x 6 点/张" % n)
    url = host + IMG_PATH
    body = {"model": IMG_MODEL, "prompt": prompt, "n": n, "size": a.size}
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost),
               "compliance": {"blocked": 0, "warned": len(comp["warned"]),
                              "missing": [m["name"] for m in comp["missing"]]}}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  合规：一票否决 0 条 · 待改写 %d 条 · 必标项缺 %d 项"
              % (len(comp["warned"]), len(comp["missing"])))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    outdir = ensure_dir(a.outdir or OUT_ROOT)
    prefix = a.prefix or ("%s_%s" % (today(), "img"))
    say("正在出图（%d 张，%s）…" % (n, a.size))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(180, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    items = d.get("data") if isinstance(d.get("data"), list) else []
    if st not in (200, 201) or not items:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "image", "http": st,
                    "error": msg})
        raise Fail("call", "出图失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    paths, urls, src = save_images(d, outdir, prefix, "png")
    billed = IMG_POINTS * len(items)
    ledger_add({"at": now_iso(), "ok": True, "mode": "image", "requested": n,
                "returned": len(items), "files": paths, "points": billed,
                "complianceWarned": [h["key"] for h in comp["warned"]]})
    out = {"ok": True, "mode": "image", "model": IMG_MODEL, "requested": n,
           "returned": len(items), "source": src, "files": paths, "urls": urls,
           "billedPoints": billed, "elapsed": round(dt, 1),
           "complianceMissing": [m["name"] for m in comp["missing"]],
           "endpoint": IMG_PATH}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("出图完成（%.1fs）" % dt)
    print("  请求 %d 张 / 实际返回 %d 张 · 计费 %d 点（%.2f 元）"
          % (n, len(items), billed, yuan(billed)))
    for p in paths:
        print("  文件：%s（%d 字节）" % (p, os.path.getsize(p)))
    for u in urls:
        print("  链接：%s（约 3 小时有效，及时下载）" % u)
    if comp["missing"]:
        print()
        print("  交付前还差：%s" % "、".join(m["name"] for m in comp["missing"]))
    print()
    print("  下一步：checklist 看必标模板；口播 lipsync / 空镜 video 各走一次。")
    return 0


# ───────────────────────── 配音（约 0.18 点/字）────────────────────────
def _read_text(a, what="文案"):
    text = (getattr(a, "text", None) or "").strip()
    if not text and getattr(a, "script", None):
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到稿子：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"%s\" 或 --script 稿子.txt" % what, EXIT_USAGE)
    return text


def cmd_tts(a, key, host):
    text = _read_text(a, "旁白")
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，单条落到 %d 字内（超了按段落拆两条）"
                   % (len(text), TTS_MAX_CHARS), EXIT_USAGE)
    comp = compliance_gate(text, "voice", "配音稿")
    cost = max(1, int(round(len(text) * TTS_PER_CHAR)))
    gate(a, cost, "%d 字 x 0.18 点/字（以 usage.points_cost 为准）" % len(text))
    url = host + TTS_PATH
    body = {"text": text, "model": a.tts_model, "format": a.tts_format}
    if a.reference_id:
        body["reference_id"] = a.reference_id
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "chars": len(text), "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不合成、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:300])
        print("  预估：%d 点（约 %.2f 元）· %d 字" % (cost, yuan(cost), len(text)))
        return 0

    say("正在合成配音（%d 字）…" % len(text))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(120, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d) if isinstance(d, dict) else {}
    audio = find_media_url(data) or find_media_url(d)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost")
    if st not in (200, 201) or not audio:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "tts", "http": st,
                    "error": msg})
        raise Fail("call", "配音失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = ensure_dir(a.outdir or OUT_ROOT)
    txt_path = write_text(os.path.join(outdir, "%s-voice.txt" % (a.prefix or today())),
                          text + "\n")
    ledger_add({"at": now_iso(), "ok": True, "mode": "tts", "chars": len(text),
                "audio": audio, "points": real if real is not None else cost})
    out = {"ok": True, "mode": "tts", "audioUrl": audio, "chars": len(text),
           "elapsed": round(dt, 1), "textFile": txt_path,
           "billedPoints": real, "estimatedPoints": cost,
           "complianceMissing": [m["name"] for m in comp["missing"]]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已合成（%.1fs）" % dt)
    print("  音频：%s" % audio)
    print("  稿子：%s" % txt_path)
    if real is not None:
        print("  实际点数：%s" % fmt_pts(real))
    else:
        print("  预估点数：%d 点（约 %.2f 元）" % (cost, yuan(cost)))
    print()
    print("  下一步：拿这条 audio_url 当 lipsync 的 --voice-url（参考音色）。")
    return 0


# ───────────────────────── 图片口播（15 点/秒）────────────────────────
def cmd_lipsync(a, key, host):
    text = _read_text(a, "口播稿")
    if not a.image:
        raise Fail("usage", "给 --image 出镜形象（本地路径会自动上传，免费）", EXIT_USAGE)
    if not a.voice_url and not a.voice_file:
        raise Fail("usage",
                   "text 模式要一条参考音色：--voice-url 平台地址，或 --voice-file 本地 mp3。\n"
                   "  顺序：tts --text … --yes 拿 audio_url → 再喂 --voice-url", EXIT_USAGE)
    seconds = max(1, int(a.seconds)) if a.seconds else 20
    comp = compliance_gate(text, "video", "口播稿")
    cost = max(LIPSYNC_FLOOR, int(round(LIPSYNC_PER_SECOND * float(seconds))))
    gate(a, cost, "口播 %d 秒 x 15 点/秒（声明保底 50 点）" % seconds)
    url = host + LIPSYNC_PATH
    body = {"mode": "text", "model": LIPSYNC_MODEL, "quality": a.quality or "standard",
            "content": text,
            "image_url": a.image if a.image.startswith("http") else "<上传后替换>",
            "audio_url": a.voice_url or "<上传后替换>"}
    if a.prompt:
        body["prompt"] = a.prompt
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "seconds": seconds, "chars": len(text), "estimatedPoints": cost,
               "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:400])
        print("  预估：%d 点（%.2f 元）· %d 秒 / %d 字"
              % (cost, yuan(cost), seconds, len(text)))
        return 0

    image_url, voice_url = a.image, a.voice_url
    if not image_url.startswith("http"):
        image_url = upload_file(key, host, image_url, timeout=a.timeout)["url"]
    if not voice_url and a.voice_file:
        voice_url = upload_file(key, host, a.voice_file, timeout=a.timeout)["url"]
    body["image_url"] = image_url
    body["audio_url"] = voice_url

    say("正在提交图片口播（%d 秒，%d 字）…" % (seconds, len(text)))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(120, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "lipsync", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    billed = usage.get("points_cost") or data.get("points_cost")
    ledger_add({"at": now_iso(), "ok": True, "mode": "lipsync", "taskId": task_id,
                "seconds": seconds, "points": billed if billed is not None else cost})
    out = {"ok": True, "mode": "lipsync", "taskId": task_id, "status": data.get("status"),
           "seconds": seconds, "chars": len(text), "imageUrl": image_url,
           "voiceUrl": voice_url, "elapsed": round(dt, 1),
           "billedPoints": billed, "estimatedPoints": cost,
           "complianceMissing": [m["name"] for m in comp["missing"]],
           "next": API_PREFIX + "/tasks/" + str(task_id)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：text 模式 · %d 秒 · %d 字 · 输出约 480x832 / 24fps"
          % (seconds, len(text)))
    if billed is not None:
        print("  实际点数：%s" % fmt_pts(billed))
    else:
        print("  预估点数：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 成片（按秒 x 分辨率）────────────────────────
def cmd_video(a, key, host):
    text = _read_text(a, "画面与运镜描述")
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds or VIDEO_CLIP_MIN))
    if seconds > VIDEO_CLIP_MAX:
        raise Fail("usage", "full_video 单段 4~15 秒；%d 秒按 %d 秒一段分两条提交。"
                   % (seconds, VIDEO_CLIP_MAX), EXIT_USAGE)
    comp = compliance_gate(text, "video", "成片描述")
    cost = VIDEO_RATES[a.resolution] * seconds
    gate(a, cost, "%d 秒 x %d 点/秒（%s）"
         % (seconds, VIDEO_RATES[a.resolution], a.resolution))
    image_url = None
    if a.image:
        if a.image.startswith("http"):
            ok, kind = url_allowed(a.image)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "首帧图要在白名单内（%s）。两种写法：\n"
                           "  · 本地图给路径：--image clinic.png（自动 upload，免费）\n"
                           "  · 本站地址：https://oss.gpu.likeadmin.cn/openapi/…" % kind,
                           EXIT_USAGE)
            image_url = a.image
        elif not os.path.isfile(a.image):
            raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)
    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": a.ratio or "9:16",
            "aigc_watermark": not a.no_aigc_mark}
    url = host + VIDEO_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost),
               "aigcMark": not a.no_aigc_mark}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  AI 标识：%s" % ("留在画面里（合规口径）" if not a.no_aigc_mark
                                else "不加（自己负责标注）"))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    if a.image and not image_url:
        image_url = upload_file(key, host, a.image, timeout=a.timeout)["url"]
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})

    say("正在提交成片（%s，%d 秒）…" % (a.resolution, seconds))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=max(120, a.timeout))
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "video", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    ledger_add({"at": now_iso(), "ok": True, "mode": "video", "taskId": task_id,
                "seconds": seconds, "resolution": a.resolution, "points": cost})
    out = {"ok": True, "mode": "video", "taskId": task_id, "status": data.get("status"),
           "seconds": seconds, "resolution": a.resolution, "ratio": a.ratio or "9:16",
           "firstFrame": image_url, "elapsed": round(dt, 1),
           "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost"),
           "complianceMissing": [m["name"] for m in comp["missing"]],
           "next": API_PREFIX + "/tasks/" + str(task_id)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%s · %d 秒 · %s · AI 标识 %s"
          % (a.resolution, seconds, a.ratio or "9:16",
             "开" if not a.no_aigc_mark else "关"))
    print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 查任务（免费）────────────────────────
def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + a.task_id
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    out = {"ok": True, "taskId": a.task_id, "path": path, "http": st,
           "status": None, "estimatedPoints": 0}
    found = True
    if st == 200 and d.get("code") == 0 and not d.get("data"):
        found = False
        out.update({"status": "not_found", "message": d.get("msg") or "任务不存在"})
    elif st == 200:
        data = payload_of(d) if isinstance(d, dict) else {}
        data = data if isinstance(data, dict) else {}
        out.update({"status": data.get("status"), "message": data.get("message"),
                    "videoUrl": data.get("videoUrl") or data.get("video_url"),
                    "audioUrl": data.get("audioUrl") or data.get("audio_url"),
                    "cost": data.get("cost"), "refund": data.get("refund"),
                    "result": data.get("result")})
    else:
        raise Fail("call", "查询失败（HTTP %s）：%s" % (st, err_text(st, txt)), EXIT_CALL)

    if not found and a.app:
        if not a.yes and not a.dry_run:
            raise Fail("confirm",
                       "通用 GET /tasks 说任务不存在，要用 %s 的应用层 /query 再查一次。"
                       "这条路的计价口径与 submit 同 path，说不清算不算钱，确认请加 --yes。"
                       % a.app, EXIT_CONFIRM)
        qpath = API_PREFIX + "/apps/" + a.app + "/query"
        if a.dry_run:
            out.update({"dryRun": True, "appQuery": qpath})
        else:
            st2, txt2 = http_json("POST", host + qpath, key,
                                  {"task_id": a.task_id}, timeout=60)
            data2 = payload_of(jloads(txt2) or {})
            data2 = data2 if isinstance(data2, dict) else {}
            out.update({"appQuery": qpath, "appHttp": st2,
                        "status": data2.get("status") or out.get("status"),
                        "videoUrl": data2.get("videoUrl") or data2.get("video_url")
                        or out.get("videoUrl"),
                        "audioUrl": data2.get("audioUrl") or out.get("audioUrl"),
                        "result": data2.get("result") or out.get("result"),
                        "message": data2.get("message") or out.get("message")})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("任务 %s" % a.task_id)
    print("  查询端点：GET %s（0 点）" % path)
    print("  状态：%s" % out.get("status"))
    if out.get("message"):
        print("  说明：%s" % str(out["message"])[:200])
    for k, label in (("cost", "实扣"), ("refund", "退回")):
        if out.get(k) is not None:
            print("  %s：%s 点" % (label, fmt_pts(out[k])))
    if out.get("videoUrl"):
        print("  成片：%s（约 30 分钟有效，及时转存）" % out["videoUrl"])
    if out.get("audioUrl"):
        print("  音频：%s" % out["audioUrl"])
    if out.get("result") is not None:
        print("  结果：%s" % json.dumps(out["result"], ensure_ascii=False)[:600])
    if not found and not a.app:
        print()
        print("  应用层任务看不到时，加 `--app pic_lipsync --yes` 走它的 /query。")
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
        what = e.get("taskId") or e.get("audio") or (e.get("error") or "")[:40] or "-"
        pts = e.get("points")
        print("  %s  %-5s %-8s %-30s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", e.get("mode") or "-",
            str(what)[:30], ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 医疗合规素材（医美 / 健康 / 口腔：先过合规再花钱，"
                    "走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/images/generations · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/pic_lipsync/submit · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/upload · GET %s/api/v1/tasks/<task_id>"
               % ((DEFAULT_HOST,) * 6),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 50 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="四条能力 + 现查单价 + 平台尺寸（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一条 / 一天 3 条 / 一周 15 条要多少钱（免费）",
                       allow_abbrev=False)
    p.add_argument("--avatar-seconds", dest="avatar_seconds", type=int, default=20,
                   help="口播秒数（默认 20）")
    p.add_argument("--broll-seconds", dest="broll_seconds", type=int, default=10,
                   help="空镜秒数（默认 10）")
    p.add_argument("--images", type=int, default=4, help="几张图（默认 4）")
    p.add_argument("--tts-chars", dest="tts_chars", type=int, default=60,
                   help="空镜旁白字数（默认 60）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="成片分辨率（默认 1080P）")
    p.add_argument("--jobs", type=int, default=1, help="几条（默认 1；一天常规 3 条）")
    p.add_argument("--music", type=int, default=0, help="配乐点数（默认 0，不加配乐）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("check", help="合规检查器：15 类表述 + 6 项必标（免费，纯本地）",
                       allow_abbrev=False)
    p.add_argument("--text", help="要检查的文案 / prompt / 口播稿")
    p.add_argument("--file", help="从文本文件读")
    p.add_argument("--asset", choices=ASSETS, default="copy",
                   help="素材类型：copy / image / video / voice（image、video 加查 AI 标识）")
    p.add_argument("--review", action="store_true", help="顺带打印人工复核 8 条")
    p.add_argument("--strict", action="store_true",
                   help="待改写与必标项缺失也拦截（退 2）")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("checklist", help="必标模板 + 人工复核 8 条 + 交付清单（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_checklist)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 价目 / 端点（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("upload", help="上传本地图 / 音频，拿白名单地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("image", help="出图 6 点/张（要 --yes，先过合规）", allow_abbrev=False)
    p.add_argument("--prompt", help="画面描述（环境 / 器械 / 空间示意）")
    p.add_argument("--n", type=int, default=1, help="张数 1~4（默认 1）")
    p.add_argument("--size", default=IMG_SIZE, help="尺寸（默认 %s）" % IMG_SIZE)
    p.add_argument("--outdir", help="保存目录（默认 ~/.a7w/compliance/out）")
    p.add_argument("--prefix", help="文件名前缀")
    p.add_argument("--timeout", type=int, default=240, help="超时秒数（默认 240）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_image)

    p = sub.add_parser("tts", help="配音约 0.18 点/字（要 --yes，先过合规）",
                       allow_abbrev=False)
    p.add_argument("--text", help="旁白文字（500 字内）")
    p.add_argument("--script", help="从文本文件读")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色 model_id（可选）")
    p.add_argument("--tts-model", dest="tts_model", default=TTS_MODEL,
                   help="s1 / s2-pro（默认 %s）" % TTS_MODEL)
    p.add_argument("--tts-format", dest="tts_format", default="mp3",
                   help="mp3 / wav / opus")
    p.add_argument("--prefix", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/compliance/out）")
    p.add_argument("--timeout", type=int, default=300, help="超时秒数（默认 300）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_tts)

    p = sub.add_parser("lipsync", help="图片口播 15 点/秒（要 --yes，先过合规）",
                       allow_abbrev=False)
    p.add_argument("--image", help="出镜形象：本地路径（自动上传）或平台地址")
    p.add_argument("--text", help="口播稿（text 模式，参考音色读它）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--voice-url", dest="voice_url", help="参考音色音频（平台地址）")
    p.add_argument("--voice-file", dest="voice_file", help="参考音色音频（本地，自动上传）")
    p.add_argument("--seconds", type=int, default=20, help="口播秒数（默认 20）")
    p.add_argument("--quality", choices=LIPSYNC_QUALITIES, default="standard",
                   help="standard / fast / max（默认 standard，按 15 点/秒估）")
    p.add_argument("--prompt", help="人物动作提示词（可选）")
    p.add_argument("--timeout", type=int, default=180, help="超时秒数（默认 180）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_lipsync)

    p = sub.add_parser("video", help="成片按秒 x 分辨率（要 --yes，先过合规）",
                       allow_abbrev=False)
    p.add_argument("--text", help="画面与运镜描述")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=10, help="单段秒数 4~15（默认 10）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--ratio", choices=RATIOS, default=None, help="画幅（默认 9:16）")
    p.add_argument("--no-aigc-mark", dest="no_aigc_mark", action="store_true",
                   help="关掉画面里的 AI 生成标识（默认开着，合规口径）")
    p.add_argument("--allow-any-url", action="store_true", help="跳过本地白名单预检")
    p.add_argument("--timeout", type=int, default=180, help="超时秒数（默认 180）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_video)

    p = sub.add_parser("status", help="查任务进度（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
    p.add_argument("--app", help="通用查询看不到时，指定应用走它的 /query")
    p.add_argument("--yes", action="store_true", help="确认应用层 /query（口径说不清）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("log", help="本地台账", allow_abbrev=False)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_log)

    # 全局选项写在子命令前后都可以
    for _sp in sub.choices.values():
        for _n, _kw in (("--json", dict(action="store_true")), ("--key", dict()),
                        ("--host", dict()), ("--budget", dict(type=int)),
                        ("--max-tokens", dict(type=int))):
            _sp.add_argument(_n, default=argparse.SUPPRESS, help=argparse.SUPPRESS, **_kw)
    return ap


LOCAL_ONLY = ("cmd_cost", "cmd_check", "cmd_checklist", "cmd_log")
FREE = LOCAL_ONLY + ("cmd_catalog", "cmd_doctor", "cmd_upload", "cmd_status")


def main(argv):
    ap = _parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return EXIT_USAGE
    for name, dflt in (("json", False), ("key", None), ("host", None),
                       ("budget", DEFAULT_BUDGET), ("max_tokens", 0)):
        if not hasattr(a, name):
            setattr(a, name, dflt)
    try:
        key, host = load_conf(a.key, a.host)
        fn_name = getattr(a.fn, "__name__", "")
        if not key and fn_name not in LOCAL_ONLY:
            raise Fail("usage",
                       "没有 API Key。三选一：--key / 环境变量 A7W_API_KEY / "
                       "`python3 scripts/a7w.py login --key …`。\n注册领 Key：https://api.a7w.cn/",
                       EXIT_USAGE)
        return a.fn(a, key or "", host)
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
    except Exception:                                                # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(EXIT_INTERNAL)
