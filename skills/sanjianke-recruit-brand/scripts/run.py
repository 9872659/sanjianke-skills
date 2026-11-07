#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三剪客 · 招聘雇主品牌（sanjianke-recruit-brand）

HR 的招聘视频与雇主品牌素材。本包不新造接口，把 api.a7w.cn 上已有的五条能力
按「HR 一天 / 一周要交的东西」重新排了顺序：

  图片数字人  pic_lipsync         POST /api/v1/apps/pic_lipsync/submit        15 点/秒（保底 50）
  企业音色    voice_tts           POST /api/v1/apps/voice_tts/tts             约 0.18 点/字
  音色克隆    voice_tts           POST /api/v1/apps/voice_tts/clone_voice     600 点/次
  出图        gpt-image-2.6       POST /api/v1/images/generations             6 点/张
  配乐        media_services_33   POST /api/v1/apps/media_services_33/music_generate  50 点起/首
  成片        full_video          POST /api/v1/apps/full_video/submit          按秒 x 分辨率
  查进度      GET /api/v1/tasks/<task_id>                                      0 点
  传图/传音频 POST /api/v1/upload                                              0 点

## 单价怎么来的（GET /api/v1/pricing 2026-11-08 现查，1 元 = 100 点）

  full_video/submit        per_second   480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80
  pic_lipsync/submit       flat cost:0  markupPercent 400（= 上游 x 5）minPoints 50（声明值）
                           note 里写明：上游 standard 档固定 3 点/秒 => 对外 15 点/秒
  voice_tts/*              flat cost:0  markupPercent 200（= 上游 x 3）
                           实测 tts_live 33 字 -> 上游 1.98 点 -> 我方 5.94 点 => 0.18 点/字
  images/generations       6 点/张（Images API 计价，与尺寸无关）
  media_services_33/*      落通配「*」：markupPercent 100（= 上游 x 2），单笔保底 50 点
  /api/v1/upload           flat cost:0（站主 2026-10-04 批准，上传不计费）

## 三条用钱换来的规矩（都做成了默认动作）

  1. 数字人不要 GET /api/v1/apps/pic_lipsync 去「看一眼 schema」。这条会命中
     /apps/<app>/* 的通配计价，按应用 flat 单价即时扣费、不退（实测 dressing_diffusion
     200 点、nano_banana 72 点各一笔）。本包只读 /api/v1/apps 列表 + /api/v1/pricing
     两条来验证 pic_lipsync 在架，都是 cost:0。
  2. 也不要用「缺必填参数」的 /submit 探针。pic_lipsync 的 !submit 是 reserve_sync
     口径：先按秒冻结点数，再参数校验、再全额退 —— 净额 0，但钱包被短暂动过。
     本包的 doctor 一条 submit 都不发。
  3. 轮询只走 GET /api/v1/tasks/<task_id>（价目表 cost:0）。应用层 /query 的计价
     口径在价目表里与 submit 同 path，查一次算不算钱说不清，本包不拿它轮询。

## 本地零成本的部分（0 点，不联网）

  plan  一个岗位的完整交付：校招 / 社招两套四段结构、口播、标题、平台描述、标签、
        6 张图 prompt、员工见证九宫格排版、一周内容排期、命名规范、成本单
  qc    交付前合规八项：歧视性限定、正向表述、夸大与承诺、薪资口径、岗位事实、
        成长路径、投递方式、平台规格

## 合规口径（HR 最在意的一条）

  招聘信息里的年龄 / 性别 / 婚育 / 户籍 / 身高体重 / 形象限定，本包按「零出现」处理，
  qc 逐条扫；岗位要求一律写成「能做什么」而不是「是什么人」。

## 子命令

  catalog  五条能力 + 端点 + 现查单价 + 平台尺寸（免费）
  cost     一条 / 六条 / 一周要多少钱（免费）
  plan     一个岗位的脚本、文案、见证排版、排期与交付单（免费，纯本地）
  qc       合规与交付检查（免费，纯本地）
  cover    出图：办公场景 / 招聘海报 / 校招展台，6 点/张（要 --yes）
  avatar   图片数字人口播，15 点/秒（要 --yes）
  voice    企业音色 TTS（0.18 点/字）或音色克隆（600 点/次）（要 --yes）
  music    配乐，50 点起（要 --yes）
  film     空镜 / 氛围成片，按秒计费（要 --yes）
  upload   上传本地图片或音频，拿白名单地址（免费）
  status   查任务进度（免费）
  doctor   自检 Key / 应用 / 价目 / 端点（免费，不扣费）
  log      本地台账

## 用法

  python3 scripts/run.py catalog
  python3 scripts/run.py cost --track social --jobs 1
  python3 scripts/run.py plan --track social --job "后端开发工程师" --city 杭州 \\
      --salary "15-25K·14薪" --company "示例科技" --platform douyin
  python3 scripts/run.py qc --plan ~/.a7w/recruit/social-20261108/plan.json
  python3 scripts/run.py cover --kind all --job "后端开发工程师" --yes
  python3 scripts/run.py avatar --image hr.png --voice-url "https://oss.gpu.likeadmin.cn/openapi/r.mp3" \\
      --text "我们在招后端开发工程师……" --seconds 30 --yes
  python3 scripts/run.py film --text "竖屏办公区空镜，键盘特写推窗……" --image office.png --yes
  python3 scripts/run.py status --task-id tsk_xxx

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

sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # 中文控制台不因个别符号崩掉
    except Exception:                        # noqa: BLE001
        pass

VERSION = "1.0.0"
DEFAULT_HOST = "https://api.a7w.cn"
API_PREFIX = "/api/v1"

HOME_DIR = os.path.join(os.path.expanduser("~"), ".a7w", "recruit")
LEDGER = os.path.join(HOME_DIR, "ledger.json")
OUT_ROOT = os.path.join(HOME_DIR, "out")

EXIT_USAGE, EXIT_GATE, EXIT_CONFIRM, EXIT_BUDGET, EXIT_CALL, EXIT_INTERNAL = 2, 3, 4, 5, 6, 1

UA = "sanjianke-recruit-brand/%s" % VERSION

# ── 五条能力 ─────────────────────────────────────────────────────────────────
APP_LIPSYNC = "pic_lipsync"
APP_TTS = "voice_tts"
APP_VIDEO = "full_video"
APP_IMAGE = "gpt-image-2.6"
APP_MUSIC = "media_services_33"

LIPSYNC_PATH = API_PREFIX + "/apps/" + APP_LIPSYNC + "/submit"
LIPSYNC_QUERY = API_PREFIX + "/apps/" + APP_LIPSYNC + "/query"
TTS_PATH = API_PREFIX + "/apps/" + APP_TTS + "/tts"
CLONE_PATH = API_PREFIX + "/apps/" + APP_TTS + "/clone_voice"
VIDEO_PATH = API_PREFIX + "/apps/" + APP_VIDEO + "/submit"
IMAGE_PATH = API_PREFIX + "/images/generations"
MUSIC_PATH = API_PREFIX + "/apps/" + APP_MUSIC + "/music_generate"
UPLOAD_PATH = API_PREFIX + "/upload"

# ── 单价（GET /api/v1/pricing 2026-11-08 现查）───────────────────────────────
POINTS_PER_YUAN = 100
LIPSYNC_UPSTREAM_PER_SECOND = 3      # 上游 standard 档，价目 note 里写死
LIPSYNC_MARKUP = 5                   # markupPercent 400 => 上游 x 5
LIPSYNC_PER_SECOND = LIPSYNC_UPSTREAM_PER_SECOND * LIPSYNC_MARKUP      # 15 点/秒
LIPSYNC_FLOOR = 50                   # minPoints 声明值（价目 note：通用计费不读）
LIPSYNC_MODEL = "super-lipsync-pro"
LIPSYNC_QUALITIES = ["standard", "fast", "max"]

TTS_PER_CHAR = 0.18                  # 点/字（上游 x 3，实测 33 字 = 5.94 点）
TTS_MAX_CHARS = 500
TTS_MODEL = "s2-pro"
CLONE_POINTS = 600                   # 音色克隆：上游固定 200 点 x 3
CLONE_MIN_SECONDS = 10               # 参考音频 10 秒 ~ 5 分钟

IMG_POINTS = 6                       # 点/张，与尺寸无关
IMG_SIZE = "1024x1536"

VIDEO_RATES = {"480P": 14, "768P": 28, "1080P": 60, "2K": 80, "4K": 80}
VIDEO_CLIP_MIN = 4
VIDEO_CLIP_MAX = 15
RESOLUTIONS = ["480P", "768P", "1080P", "2K", "4K"]
RATIOS = ["9:16", "16:9", "3:4", "1:1", "adaptive"]

MUSIC_FLOOR = 50                     # 通配：上游 x 2，单笔保底 50 点
MUSIC_MODEL = "V6"

DEFAULT_BUDGET = 10000               # 点 = 100 元，一周的默认上限

# ── 平台尺寸（发布页当期口径）───────────────────────────────────────────────
PLATFORMS = {
    "douyin": dict(name="抖音", ratio="9:16", size="1080x1920", maxSeconds=60, tag="#招聘"),
    "shipinhao": dict(name="视频号", ratio="9:16", size="1080x1920", maxSeconds=60,
                      tag="#招聘"),
    "xiaohongshu": dict(name="小红书", ratio="3:4", size="1080x1440", maxSeconds=90,
                        tag="#求职"),
    "campus": dict(name="校招官网 / 宣讲会", ratio="16:9", size="1920x1080",
                   maxSeconds=120, tag="#校招"),
}
PLATFORM_KEYS = list(PLATFORMS)

# ── 两套话术：社招 45 秒（岗位亮点 -> 团队氛围 -> 成长路径 -> 投递方式）──────
# seg: avatar = 图片数字人出镜（pic_lipsync）；broll = 空镜 / 定格（full_video）
# w: 占全片时长百分比，同一 seg 的 w 相加就是该段的占比
SOCIAL_BEATS = [
    dict(key="highlight", name="岗位亮点", seg="avatar", w=34,
         shot="HR 正面半身像，浅色办公背景，胸前工牌可见，画面左侧留岗位字幕位",
         line="{company}{dept}在招{job}，工作地点{city}，薪资{salary}，{contract}。"
              "岗位负责{scope}，入职后有三个月带教期。",
         short="{company}在招{job}，{city}，{salary}。"),
    dict(key="team", name="团队氛围", seg="broll", w=20,
         shot="开放办公区横移，两人对着双屏讨论，白板上有手写排期",
         line="团队 {teamSize} 人，直接向{reportTo}汇报，{collab}。",
         short="团队 {teamSize} 人，向{reportTo}汇报。"),
    dict(key="growth", name="成长路径", seg="avatar", w=33,
         shot="HR 切到第二个机位，身后是职级公示墙与导师辅导位",
         line="晋升通道写在{level}职级表里，三步到{next}，每年两次评审。去年有 "
              "{growthCases} 位同事走过，平均 {growthYears} 年。",
         short="{level} 起三步到 {next}，去年 {growthCases} 位同事走过。"),
    dict(key="apply", name="投递方式", seg="broll", w=13,
         shot="招聘海报定格，二维码与投递入口居中，底部留截止日期",
         line="投递入口 {apply}，{deadline}截止，初筛三个工作日内回复。",
         short="投递 {apply}，{deadline}截止。"),
]

# ── 校招 30 秒：公司介绍 -> 培养体系 -> 成长故事 -> 投递方式 ────────────────
CAMPUS_BEATS = [
    dict(key="company", name="公司介绍", seg="broll", w=25,
         shot="前台 LOGO 墙推到工位区，展台与校招立牌入画",
         line="{company}，{companySize} 人，{city}，校招年包{salary}。今年开放 {job} 等 "
              "{openRoles} 个岗位。",
         short="{company} 校招 {job}，年包{salary}。"),
    dict(key="program", name="培养体系", seg="avatar", w=25,
         shot="HR 正面半身像，身后是训练营课表与导师牌",
         line="培养体系「{program}」：导师带教，前 {rotateMonths} 个月轮岗，"
              "之后能独立负责一条业务线。",
         short="「{program}」导师带教，轮岗 {rotateMonths} 个月，之后能独立负责模块。"),
    dict(key="story", name="成长故事", seg="broll", w=25,
         shot="员工工位实拍 + 见证卡片叠化（头像 / 岗位 / 入职年限）",
         line="去年校招生{storyName}，{storyYears} 年做到{storyRole}，带 {storyTeam} 人。",
         short="{storyName}{storyYears} 年做到{storyRole}，带 {storyTeam} 人。"),
    dict(key="apply", name="投递方式", seg="avatar", w=25,
         shot="HR 收尾，右下角网申入口与内推码常驻",
         line="网申入口 {apply}，{deadline}截止，笔试线上，面试可线上或到公司。",
         short="网申 {apply}，{deadline}截止。"),
]

BEATS = {"social": SOCIAL_BEATS, "campus": CAMPUS_BEATS}
TRACK_NAMES = {"social": "社招", "campus": "校招"}
TRACK_SECONDS = {"social": 45, "campus": 30}

# 一单两条片：主片走全结构，快切版只留投递引导
CUTS = {
    "social": [
        dict(key="full", name="社招 JD 主片", keys=["highlight", "team", "growth", "apply"]),
        dict(key="short", name="投递引导快切", keys=["highlight", "apply"]),
    ],
    "campus": [
        dict(key="full", name="校招 JD 主片", keys=["company", "program", "story", "apply"]),
        dict(key="short", name="投递引导快切", keys=["program", "apply"]),
    ],
}

# ── 出图清单：办公场景 6 张（含招聘海报主视觉）──────────────────────────────
IMAGE_SETS = [
    dict(kind="office", name="开放办公区",
         prompt="手机竖屏实拍，明亮开放办公区，长桌与双屏工位，两人对着屏幕讨论，"
                "绿植与窗外自然光，真实公司环境质感，画面无文字水印"),
    dict(kind="meeting", name="会议室讨论",
         prompt="手机竖屏实拍，玻璃会议室里的方案讨论，白板上有手写流程图，"
                "三人围坐，笔记本与马克杯，午后侧光，真实公司环境质感，画面无文字水印"),
    dict(kind="coffee", name="茶水间休息区",
         prompt="手机竖屏实拍，公司茶水间吧台，咖啡机与马克杯，两名同事站着聊天，"
                "暖色灯光，真实公司环境质感，画面无文字水印"),
    dict(kind="mentor", name="一对一辅导",
         prompt="手机竖屏实拍，资深同事在工位旁给新人讲代码，双屏上打开着编辑器，"
                "俯拍肩后视角，白天自然光，真实公司环境质感，画面无文字水印"),
    dict(kind="poster", name="招聘海报主视觉",
         prompt="招聘海报竖版主视觉，{job} 岗位主标题，浅色几何背景配公司主色调块，"
                "中间留人物留白，底部留二维码与投递入口留白区，扁平设计，无真实文字"),
    dict(kind="campus", name="校招宣讲展台",
         prompt="手机竖屏实拍，高校宣讲会现场展台，易拉宝与签到桌，学生排队咨询，"
                "室内灯光，真实活动质感，画面无文字水印"),
]

# ── 员工见证九宫格：3 条见证 x 3 个元素 ─────────────────────────────────────
WITNESS_LAYOUT = dict(
    size="1080x1080", grid="3x3",
    cells=[
        "第 1 格 头像（正方形裁切，正面，肩线在格内 2/3 处）",
        "第 2 格 姓名 + 岗位 + 入职年限（一行放得下：小林｜后端开发｜入职 2 年）",
        "第 3 格 一句话见证（14 字内，写具体的事，不写形容词）",
        "第 4~6 格 = 第 2 位见证的同一组三格",
        "第 7~9 格 = 第 3 位见证的同一组三格",
    ],
    rows=["第 2 位：入职 1 年的新人（讲上手速度）",
          "第 1 位：入职 3 年的骨干（讲成长与晋升）",
          "第 3 位：应届转正的校招生（讲培养体系）"],
)

# ── 一周内容排期（周一到周日）──────────────────────────────────────────────
WEEK_PLAN = [
    dict(day="周一", what="校招 JD 30 秒（岗位一）", how="plan --track campus -> avatar + film + voice",
         deliver="1 条 30 秒 + 投递快切", points="约 1,250 点"),
    dict(day="周二", what="社招 JD 45 秒（岗位二）", how="plan --track social -> avatar + film + voice",
         deliver="1 条 45 秒 + 投递快切", points="约 1,450 点"),
    dict(day="周三", what="员工见证 20 秒 + 九宫格", how="film + 九宫格排版",
         deliver="1 条 20 秒 + 1 张九宫格", points="约 1,220 点"),
    dict(day="周四", what="办公场景图 6 张 + 招聘海报", how="cover --kind all --n 1",
         deliver="6 张 png + 1 张海报", points="36 点"),
    dict(day="周五", what="团队氛围空镜 15 秒", how="film --seconds 15",
         deliver="1 条 15 秒空镜", points="900 点"),
    dict(day="周六", what="成长路径 30 秒（数字人为主）", how="avatar --seconds 30",
         deliver="1 条 30 秒", points="450 点"),
    dict(day="周日", what="数据复盘 + 下周 JD 排期", how="qc + plan（纯本地）",
         deliver="1 份复盘 + 下周排期", points="0 点"),
]

# ── 合规词表 ─────────────────────────────────────────────────────────────────
DISCRIM_WORDS = [
    "限男", "限女", "仅限男", "仅限女", "男性优先", "女性优先", "男生优先", "女生优先",
    "年龄", "岁以下", "岁以上", "岁左右", "25-35", "18-30", "35岁", "30岁",
    "已婚", "未婚", "婚育", "已育", "未育", "育龄", "宝妈", "孕",
    "户籍", "本地户口", "本市户口", "本地人优先",
    "身高", "体重", "形象好", "气质佳", "五官端正", "相貌", "颜值",
]
HYPE_WORDS = [
    "高薪诚聘", "急招", "包吃住", "月入过万", "轻松", "躺赚", "无门槛", "不看学历",
    "包进", "包分配", "内定", "随便挑", "钱多事少",
]
NEGATIVE_WORDS = [
    "吃苦耐劳", "抗压能力强", "能承受", "狼性", "996", "大小周", "无经验勿扰",
    "非诚勿扰", "谢绝", "不接受",
]
ABILITY_WORDS = ["负责", "独立", "熟悉", "掌握", "精通", "参与", "具备", "能", "带过", "主导"]


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


def http_json(method, url, key, body=None, timeout=120, retries=3):
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


def http_multipart(url, key, fields, files, timeout=600, field_name="file"):
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
    """平台只收本站托管的地址。返回 (ok, 归属说明)。"""
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


def clips_for(seconds):
    """把总秒数拆成 4~15 秒的段（full_video 的单段上限）。"""
    out, left = [], int(seconds)
    while left > 0:
        take = min(VIDEO_CLIP_MAX, left)
        if 0 < left - take < VIDEO_CLIP_MIN and take > VIDEO_CLIP_MIN:
            take -= 1
        out.append(take)
        left -= take
    return out


def video_points(seconds, resolution):
    return VIDEO_RATES[resolution] * int(seconds)


def lipsync_points(seconds):
    """数字人按秒计费，声明保底 50 点（价目 note：minPoints 只是声明字段）。"""
    return max(LIPSYNC_FLOOR, int(round(LIPSYNC_PER_SECOND * float(seconds))))


# ───────────────────────── 一个岗位的脚本（纯本地，0 点）────────────────────
def _trim(v):
    v = round(float(v), 1)
    return int(v) if abs(v - int(v)) < 1e-6 else v


def _slug(s):
    s = re.sub(r"[\\/:*?\"<>|\s·]+", "", str(s or ""))
    return s[:24] or "未命名"


def _meta(a):
    m = dict(track=a.track, trackName=TRACK_NAMES[a.track],
             company=a.company, job=a.job, dept=a.dept, city=a.city,
             salary=a.salary, contract=a.contract, scope=a.scope,
             teamSize=str(a.team_size), reportTo=a.report_to, collab=a.collab,
             level=a.level, next=a.next, growthCases=str(a.growth_cases),
             growthYears=a.growth_years, apply=a.apply, deadline=a.deadline,
             industry=a.industry, companySize=str(a.company_size),
             openRoles=str(a.open_roles), program=a.program,
             rotateMonths=str(a.rotate_months), storyName=a.story_name,
             storyYears=str(a.story_years), storyRole=a.story_role,
             storyTeam=str(a.story_team),
             contact=("电话 " + a.phone) if a.phone else "站内私信",
             platform=PLATFORMS[a.platform]["name"],
             platformTag=PLATFORMS[a.platform]["tag"])
    return m


def _beats(track, m, seconds, keys=None, short=False):
    """按 w 百分比把秒数分给每一段，返回 [{key, seg, w, at, beat, shot, line}]。"""
    pool = BEATS[track]
    picked = [b for b in pool if (keys is None or b["key"] in keys)]
    tw = float(sum(b["w"] for b in picked)) or 1.0
    out, acc = [], 0.0
    for b in picked:
        start = acc
        acc += float(seconds) * b["w"] / tw
        raw = b.get("short") if short else b["line"]
        out.append({"key": b["key"], "seg": b["seg"], "w": b["w"],
                    "at": "%s-%s 秒" % (_trim(start), _trim(acc)),
                    "start": round(start, 2), "end": round(acc, 2),
                    "beat": b["name"], "shot": b["shot"],
                    "line": (raw or b["line"]).format(**m)})
    return out


def _seg_seconds(beats):
    av = sum(b["end"] - b["start"] for b in beats if b["seg"] == "avatar")
    br = sum(b["end"] - b["start"] for b in beats if b["seg"] == "broll")
    return int(round(av)), int(round(br))


def _titles(m, track, cut):
    if track == "social":
        pool = [
            "{company}在招{job}｜{city}｜{salary}",
            "{job}招聘｜团队 {teamSize} 人｜{level} 起三步到 {next}",
            "{city}｜{job}｜{salary}｜投递入口在片尾",
        ]
        if cut == "short":
            pool = [
                "{job}｜{city}｜{salary}｜15 秒看完全部",
                "{company}在招{job}，投递入口：{apply}",
                "{job}｜{level} 起，三步到 {next}",
            ]
    else:
        pool = [
            "{company} 2027 校招｜{job} 等 {openRoles} 个岗位",
            "校招｜{program}｜导师带教 + {rotateMonths} 个月轮岗",
            "{city}校招｜应届生 {storyYears} 年做到{storyRole}",
        ]
        if cut == "short":
            pool = [
                "{company} 校招｜{job}｜网申 {deadline} 截止",
                "应届生看这里｜{program}｜{openRoles} 个岗位",
                "校招 15 秒｜网申入口在片尾",
            ]
    return [t.format(**m) for t in pool]


def _description(m, track):
    if track == "social":
        return ("{company}｜{dept}｜{job}｜工作地点 {city}｜薪资 {salary}｜{contract}｜"
                "岗位：负责{scope}｜团队 {teamSize} 人，向{reportTo}汇报｜"
                "晋升：{level} 起三步到 {next}，去年 {growthCases} 位同事走过，"
                "平均 {growthYears} 年｜投递入口 {apply}，{deadline}截止").format(**m)
    return ("{company}｜{industry}｜{companySize} 人｜{city}｜校招年包 {salary}｜"
            "2027 校招开放 {job} 等 {openRoles} 个岗位｜岗位：负责{scope}｜"
            "培养体系「{program}」：导师一对一带教 + 前 {rotateMonths} 个月轮岗｜"
            "网申入口 {apply}，{deadline}截止").format(**m)


def _tags(m, track):
    if track == "social":
        return ["#%s招聘" % m["city"], "#%s" % m["job"], "#%s" % m["company"],
                "#%s" % m["dept"], "#%s" % m["salary"].replace("·", ""), m["platformTag"]]
    return ["#校招", "#%s校招" % m["city"], "#%s" % m["job"], "#%s" % m["company"],
            "#应届生求职", m["platformTag"]]


def _video_prompt(m, track, cut, seconds):
    if track == "social":
        focus = ("开放办公区横移，两人对屏讨论，白板排期特写，工位区推到招聘海报定格")
    else:
        focus = ("高校宣讲展台，前台 LOGO 墙，训练营课表特写，员工工位见证卡叠化")
    if cut == "short":
        focus = "招聘海报定格 + 二维码特写，节奏快，两段切换"
    return "竖屏公司实拍氛围空镜，%s，真实光线，镜头稳定，画面无文字与水印，整段 %d 秒内" % (
        focus, seconds)


def _naming(m, track, cut, seconds, platform_key):
    base = "%s_%s_%s_%s_%s_%ds" % (today(), m["trackName"], _slug(m["job"]),
                                   _slug(m["city"]), platform_key, seconds)
    if cut == "short":
        base += "_cta"
    return base


def build_plan(a):
    track = a.track
    m = _meta(a)
    plat = PLATFORMS[a.platform]
    seconds = int(a.seconds) if a.seconds else TRACK_SECONDS[track]
    if seconds < 15:
        raise Fail("usage", "--seconds 至少 15 秒（四个段落各占一段，太短塞不下）", EXIT_USAGE)
    videos = []
    for cut in CUTS[track]:
        if cut["key"] == "short" and int(a.short_seconds or 0) <= 0:
            continue
        sec = seconds if cut["key"] == "full" else max(15, int(a.short_seconds))
        beats = _beats(track, m, sec, cut["keys"], short=(cut["key"] == "short"))
        av, br = _seg_seconds(beats)
        voice = "".join([b["line"] for b in beats])
        base = _naming(m, track, cut["key"], sec, a.platform)
        videos.append({
            "no": len(videos) + 1, "cut": cut["key"], "cutName": cut["name"],
            "seconds": sec, "avatarSeconds": av, "brollSeconds": br,
            "beats": beats, "voiceover": voice, "voiceChars": len(voice),
            "titles": _titles(m, track, cut["key"]),
            "description": _description(m, track),
            "tags": _tags(m, track),
            "videoPrompt": _video_prompt(m, track, cut["key"], br or sec),
            "avatarPrompt": "正面半身像，浅色办公背景，工牌可见，目光看向镜头，表情自然",
            "filename": base + ".mp4", "coverName": base + "_cover.png",
            "voiceName": base + "_voice.mp3",
        })
    images = []
    for it in IMAGE_SETS:
        base = _naming(m, track, "full", seconds, a.platform)
        images.append({"kind": it["kind"], "name": it["name"],
                       "prompt": it["prompt"].format(**m),
                       "filename": "%s_%s.png" % (base, it["kind"]),
                       "size": IMG_SIZE})
    full = videos[0]
    av = full["avatarSeconds"]
    br = full["brollSeconds"]
    # 空镜旁白：只有空镜段需要单独出 TTS；数字人段由 pic_lipsync text 模式直接读文案
    broll_chars = sum(len(b["line"]) for b in full["beats"] if b["seg"] == "broll")
    av_pts = lipsync_points(av)
    br_pts = video_points(br, a.resolution) if br else 0
    tts_pts = int(round(broll_chars * TTS_PER_CHAR))
    img_pts = len(images) * IMG_POINTS
    mus_pts = MUSIC_FLOOR if a.music else 0
    total = av_pts + br_pts + tts_pts + img_pts + mus_pts
    totals = {"videos": len(videos), "videoSeconds": sum(v["seconds"] for v in videos),
              "resolution": a.resolution,
              "avatarSeconds": av, "brollSeconds": br,
              "avatarPoints": av_pts, "brollPoints": br_pts,
              "images": len(images), "imagePoints": img_pts,
              "brollChars": broll_chars, "ttsPoints": tts_pts,
              "musicPoints": mus_pts,
              "estimatedPoints": total, "yuan": yuan(total)}
    deliverables = [
        ("JD 主片", "%s / H.264 / %d 秒 / %s" % (plat["size"], full["seconds"], plat["ratio"]),
         1, full["filename"]),
    ]
    if len(videos) > 1:
        deliverables.append(
            ("投递引导快切", "%s / H.264 / %d 秒 / %s" % (plat["size"],
                                                    videos[1]["seconds"], plat["ratio"]),
             1, videos[1]["filename"]))
    deliverables += [
        ("办公场景图", "%s / png（可裁 %s 封面）" % (IMG_SIZE, plat["size"]),
         len(images), images[0]["filename"] if images else "-"),
        ("员工见证九宫格", WITNESS_LAYOUT["size"] + " / png（3x3，三位见证）", 1,
         "%s_witness_9grid.png" % _naming(m, track, "full", seconds, a.platform)),
        ("口播音频 + 配乐", "mp3 / 44.1kHz / 单条 %d 字内；配乐 30 秒循环"
         % TTS_MAX_CHARS, 2, "%s / bgm.mp3" % full["voiceName"]),
        ("文案包 + 交付单", "标题 3 条 + 平台描述 1 条 + 标签 6 个；结构 / 合规 / 成本 / 命名",
         2, "文案.md / 交付单.md"),
    ]
    return {"ok": True, "generatedAt": now_iso(), "track": track,
            "trackName": TRACK_NAMES[track],
            "platform": a.platform, "platformName": plat["name"],
            "ratio": plat["ratio"], "size": plat["size"],
            "maxSeconds": plat["maxSeconds"],
            "meta": m, "videos": videos, "images": images, "totals": totals,
            "witness": WITNESS_LAYOUT, "week": WEEK_PLAN,
            "deliverables": [{"name": n, "spec": s, "count": c, "naming": f}
                             for n, s, c, f in deliverables]}


def plan_markdown(plan, a):
    m = plan["meta"]
    L = []
    L.append("# %s · 交付单（%s）" % (plan["trackName"], today()))
    L.append("")
    L.append("岗位：%s　｜　公司：%s　｜　平台：%s（%s / %s）　｜　合计 %d 点 = %.2f 元"
             % (m["job"], m["company"], plan["platformName"], plan["size"],
                plan["ratio"], plan["totals"]["estimatedPoints"],
                plan["totals"]["yuan"]))
    L.append("")
    L.append("## 交付清单（一单）")
    L.append("")
    L.append("| # | 交付物 | 规格 | 数量 | 命名 |")
    L.append("|---|---|---|---|---|")
    for i, d in enumerate(plan["deliverables"], 1):
        L.append("| %d | %s | %s | %d | %s |" % (i, d["name"], d["spec"], d["count"],
                                                 d["naming"]))
    L.append("")
    L.append("## 分镜与口播")
    L.append("")
    for v in plan["videos"]:
        L.append("### %02d · %s（%d 秒 · 数字人 %d 秒 + 空镜 %d 秒）"
                 % (v["no"], v["cutName"], v["seconds"], v["avatarSeconds"],
                    v["brollSeconds"]))
        L.append("")
        L.append("| 时间 | 段落 | 谁在说 | 画面 | 口播 |")
        L.append("|---|---|---|---|---|")
        for b in v["beats"]:
            who = "数字人出镜" if b["seg"] == "avatar" else "空镜 / 定格"
            L.append("| %s | %s | %s | %s | %s |"
                     % (b["at"], b["beat"], who, b["shot"], b["line"]))
        L.append("")
        L.append("- 口播总字数：%d 字 / 片长 %d 秒 = %.1f 字/秒（短视频口播常见 4~6 字/秒）"
                 % (v["voiceChars"], v["seconds"],
                    v["voiceChars"] / float(max(1, v["seconds"]))))
        L.append("- 空镜拆分提交：%s（单段 4~15 秒）"
                 % " + ".join(str(x) for x in clips_for(v["brollSeconds"])))
        L.append("- 数字人段：`avatar --seconds %d --text \"…\"`（text 模式，参考音色）"
                 % v["avatarSeconds"])
        L.append("- 空镜提示词：%s" % v["videoPrompt"])
        L.append("")
    L.append("## 出图清单（%d 张，6 点/张）" % len(plan["images"]))
    L.append("")
    L.append("| # | 图 | 尺寸 | 命名 |")
    L.append("|---|---|---|---|")
    for i, im in enumerate(plan["images"], 1):
        L.append("| %d | %s | %s | %s |" % (i, im["name"], im["size"], im["filename"]))
    L.append("")
    L.append("## 员工见证九宫格（%s · %s）" % (plan["witness"]["grid"],
                                     plan["witness"]["size"]))
    L.append("")
    for cell in plan["witness"]["cells"]:
        L.append("- %s" % cell)
    L.append("")
    L.append("见证三选一：%s" % "；".join(plan["witness"]["rows"]))
    L.append("")
    L.append("## 一周内容排期")
    L.append("")
    L.append("| 星期 | 做什么 | 怎么跑 | 交什么 | 点数 |")
    L.append("|---|---|---|---|---|")
    for d in plan["week"]:
        L.append("| %s | %s | %s | %s | %s |"
                 % (d["day"], d["what"], d["how"], d["deliver"], d["points"]))
    L.append("")
    L.append("## 成本预估（1 元 = 100 点）")
    L.append("")
    L.append("| 项 | 点数 | 口径 |")
    L.append("|---|---|---|")
    t = plan["totals"]
    L.append("| 数字人 %d 秒 | %s | 15 点/秒（上游 3 点/秒 x5），保底 50 点 |"
             % (t["avatarSeconds"], fmt_pts(t["avatarPoints"])))
    L.append("| 空镜 %d 秒 | %s | %d 点/秒 x %d 秒（%s） |"
             % (t["brollSeconds"], fmt_pts(t["brollPoints"]),
                VIDEO_RATES[t["resolution"]], t["brollSeconds"], t["resolution"]))
    L.append("| 办公场景图 %d 张 | %s | 6 点/张 |"
             % (t["images"], fmt_pts(t["imagePoints"])))
    L.append("| 空镜旁白 %d 字 | %s | 0.18 点/字（上游 x3） |"
             % (t["brollChars"], fmt_pts(t["ttsPoints"])))
    L.append("| 配乐 | %s | 50 点起/首（通配：上游 x2，保底 50） |"
             % fmt_pts(t["musicPoints"]))
    L.append("| **合计** | **%s** | **%.2f 元** |"
             % (fmt_pts(t["estimatedPoints"]), t["yuan"]))
    L.append("")
    L.append("## 合规八项（qc 会逐条验）")
    L.append("")
    L.append("- 歧视性限定：年龄 / 性别 / 婚育 / 户籍 / 身高体重 / 形象，一条都不进文案")
    L.append("- 正向表述：岗位要求写成「能做什么」，用%s这类动词开头"
             % " / ".join(ABILITY_WORDS[:4]))
    L.append("- 薪资口径：写区间 + 发放结构（%s）" % m["salary"])
    L.append("- 岗位事实：工作地点 %s；合同主体 %s" % (m["city"], m["company"]))
    L.append("- 成长路径：%s 起三步到 %s" % (m["level"], m["next"]))
    L.append("- 投递方式：%s，%s截止" % (m["apply"], m["deadline"]))
    L.append("- 平台规格：%s，%s，%d 秒内" % (plan["platformName"], plan["size"],
                                       plan["maxSeconds"]))
    L.append("- 招聘主体：公司全称照写，内推码与官网入口一致")
    L.append("")
    return "\n".join(L) + "\n"


def copy_markdown(plan, a):
    L = []
    L.append("# %s · 文案包（%s）" % (plan["trackName"], today()))
    L.append("")
    for v in plan["videos"]:
        L.append("## %02d · %s" % (v["no"], v["cutName"]))
        L.append("")
        L.append("### 标题（三选一，平台里轮着用）")
        for i, t in enumerate(v["titles"], 1):
            L.append("%d. %s" % (i, t))
        L.append("")
        L.append("### 平台描述")
        L.append("")
        L.append(v["description"])
        L.append("")
        L.append("### 标签（6 个）")
        L.append("")
        L.append(" ".join(v["tags"]))
        L.append("")
        L.append("### 口播（%d 字 / %d 秒）" % (v["voiceChars"], v["seconds"]))
        L.append("")
        L.append(v["voiceover"])
        L.append("")
    L.append("## 出图 prompt（%d 张）" % len(plan["images"]))
    L.append("")
    for im in plan["images"]:
        L.append("### %s · %s" % (im["name"], im["filename"]))
        L.append("")
        L.append(im["prompt"])
        L.append("")
    return "\n".join(L) + "\n"


def cmd_plan(a, key, host):
    plan = build_plan(a)
    outdir = a.outdir or os.path.join(HOME_DIR, "%s-%s" % (a.track, today()))
    jp = os.path.join(outdir, "plan.json")
    dp = os.path.join(outdir, "交付单.md")
    cp = os.path.join(outdir, "文案.md")
    write_text(jp, json.dumps(plan, ensure_ascii=False, indent=1))
    write_text(dp, plan_markdown(plan, a))
    write_text(cp, copy_markdown(plan, a))
    out = {"ok": True, "mode": "plan", "track": plan["track"],
           "job": plan["meta"]["job"], "platform": plan["platform"],
           "videos": len(plan["videos"]), "images": len(plan["images"]),
           "avatarSeconds": plan["totals"]["avatarSeconds"],
           "brollSeconds": plan["totals"]["brollSeconds"],
           "estimatedPoints": plan["totals"]["estimatedPoints"],
           "yuan": plan["totals"]["yuan"],
           "files": {"plan": jp, "delivery": dp, "copy": cp}}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("一个岗位的完整脚本 · %s（%s，纯本地，0 点）"
          % (plan["meta"]["job"], plan["trackName"]))
    print("=" * 78)
    print("  %s %s %s %s" % (pad("#", 3), pad("版本", 18), pad("段落", 34), "命名"))
    print("  " + "-" * 74)
    for v in plan["videos"]:
        names = " / ".join(b["beat"] for b in v["beats"])
        print("  %s %s %s %s" % (pad(v["no"], 3),
                                 pad("%s %d 秒" % (v["cutName"], v["seconds"]), 18),
                                 pad(names[:32], 34), v["filename"]))
    print()
    print("  交付清单：%d 条成片 / %d 张图 / 1 张见证九宫格 / 口播 + 配乐 / 1 份交付单"
          % (len(plan["videos"]), len(plan["images"])))
    print("  预估成本：%s 点 = %.2f 元（数字人 %d 秒 + 空镜 %d 秒 @ %s）"
          % (fmt_pts(plan["totals"]["estimatedPoints"]), plan["totals"]["yuan"],
             plan["totals"]["avatarSeconds"], plan["totals"]["brollSeconds"],
             plan["totals"]["resolution"]))
    print()
    print("  已写：")
    print("    %s" % jp)
    print("    %s" % dp)
    print("    %s" % cp)
    print()
    print("  下一步：`qc --plan %s` 过一遍合规，再 cover / avatar / voice / film。" % jp)
    return 0


def cmd_qc(a, key, host):
    problems, failed = [], set()

    def bad(k, scope, what):
        failed.add(k)
        problems.append({"key": k, "scope": scope, "problem": what})

    if a.plan:
        if not os.path.isfile(a.plan):
            raise Fail("usage", "找不到 plan.json：%s（先跑 plan）" % a.plan, EXIT_USAGE)
        plan = json.load(io.open(a.plan, encoding="utf-8"))
        videos = plan.get("videos") or []
        meta = plan.get("meta") or {}
        plat = PLATFORMS.get(plan.get("platform") or "douyin") or PLATFORMS["douyin"]
    elif a.text:
        plat = PLATFORMS[a.platform]
        videos = [{"no": 1, "cutName": "手工文案", "seconds": a.seconds,
                   "titles": [a.text], "description": a.text, "tags": [],
                   "voiceover": a.text, "voiceChars": len(a.text), "beats": []}]
        meta = {"company": a.company or "", "city": a.city or "",
                "salary": a.salary or ""}
    else:
        raise Fail("usage", "给 --plan plan.json 或 --text \"一条文案\" 再检查", EXIT_USAGE)

    if not videos:
        raise Fail("usage", "这份 plan 里没有成片，先补 --short-seconds 再生成", EXIT_USAGE)

    company = str(meta.get("company") or "")
    for v in videos:
        blob = " ".join([str(x) for x in v.get("titles") or []])
        blob += " " + str(v.get("description") or "")
        blob += " " + " ".join(v.get("tags") or [])
        blob += " " + str(v.get("voiceover") or "")
        for b in v.get("beats") or []:
            blob += " " + str(b.get("line") or "")

        hits = [w for w in DISCRIM_WORDS if w in blob]
        if hits:
            bad("discrim", "%02d 文案" % v.get("no", 0),
                "歧视性限定：%s（改用岗位能力描述，年龄性别婚育户籍形象一律不写）"
                % "、".join(hits[:6]))
        if not any(w in blob for w in ABILITY_WORDS):
            bad("ability", "%02d 文案" % v.get("no", 0),
                "正向表述：岗位要求没写成「能做什么」（用负责 / 独立 / 熟悉 / 掌握 开头）")
        hype = [w for w in HYPE_WORDS if w in blob]
        if hype:
            bad("hype", "%02d 文案" % v.get("no", 0),
                "夸大与承诺：%s（换成可核对的数字：团队人数、晋升年限、截止日期）"
                % "、".join(hype[:6]))
        neg = [w for w in NEGATIVE_WORDS if w in blob]
        if neg:
            bad("negative", "%02d 文案" % v.get("no", 0),
                "负面表述：%s（换成正向说法：成长快、机制透明、配套齐全）" % "、".join(neg[:6]))
        if not re.search(r"\d+(\.\d+)?\s*[-~到]\s*\d+(\.\d+)?\s*[Kk万千]", blob):
            bad("salary", "%02d 薪资" % v.get("no", 0),
                "没看到薪资区间（写「15-25K」而不是「薪资面议」「有竞争力」）")
        if not company or company not in blob:
            bad("subject", "%02d 招聘主体" % v.get("no", 0),
                "公司全称没进文案（招聘主体照写，%s）" % (company or "先给 --company"))
        if not re.search(r"杭州|北京|上海|深圳|广州|成都|武汉|南京|苏州|西安|长沙|远程|\d+\s*号线|工作地点",
                         blob):
            bad("location", "%02d 岗位事实" % v.get("no", 0),
                "没看到工作地点（写城市或园区）")
        if not re.search(r"晋升|导师|培养|轮岗|训练营|职级|通道|带教", blob):
            bad("growth", "%02d 成长路径" % v.get("no", 0),
                "没看到成长路径（晋升通道 / 培养体系 / 导师带教，至少一个具体名词）")
        if not re.search(r"@|网申|官网|扫码|二维码|投递|内推|入口", blob):
            bad("apply", "%02d 投递方式" % v.get("no", 0),
                "没看到投递方式（邮箱 / 网申入口 / 内推码 + 截止日期）")
        if int(v.get("seconds") or 0) > plat["maxSeconds"]:
            bad("duration", "%02d 时长" % v.get("no", 0),
                "单条 %d 秒超过 %s 的 %d 秒" % (int(v.get("seconds") or 0),
                                              plat["name"], plat["maxSeconds"]))

    table = [
        ("discrim", "歧视性限定", "年龄 / 性别 / 婚育 / 户籍 / 形象，一条都不进文案"),
        ("ability", "正向表述", "岗位要求写成「能做什么」"),
        ("hype", "夸大与承诺", "高薪诚聘 / 急招 / 包进 换成具体数字"),
        ("negative", "负面表述", "吃苦耐劳 / 抗压 换成成长与机制"),
        ("salary", "薪资口径", "区间 + 发放结构，一处一个数字"),
        ("subject", "招聘主体", "公司全称照写，内推码与官网一致"),
        ("location", "岗位事实", "工作地点 + 合同主体写清楚"),
        ("growth", "成长路径", "晋升 / 培养 / 带教，至少一个具体名词"),
        ("apply", "投递方式", "投递入口 + 截止日期"),
        ("duration", "平台规格", "%s：%s，%d 秒内"
         % (plat["name"], plat["ratio"], plat["maxSeconds"])),
    ]
    checks = [(name, k not in failed, detail) for k, name, detail in table]
    out = {"ok": not problems, "platform": plat["name"], "checkedVideos": len(videos),
           "problems": problems,
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("交付前检查 · %d 条（纯本地，0 点）" % len(videos))
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 12), dd))
    if problems:
        print()
        print("  要改的地方：")
        for p in problems:
            print("    · %s：%s" % (p["scope"], p["problem"]))
        print()
        print("  改完重跑：qc --plan <plan.json>")
        return EXIT_GATE
    print()
    print("  10 项全过，可以按交付单开拍。")
    return 0


# ───────────────────────── 免费：目录与成本 ─────────────────────────
def cmd_catalog(a, key, host):
    st, txt = http_json("GET", host + API_PREFIX + "/apps", key, timeout=60)
    listing = (jloads(txt) or {}).get("data")
    listing = listing if isinstance(listing, list) else []
    online = {it.get("code"): it for it in listing if isinstance(it, dict)}
    st2, txt2 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt2) or {}).get("pricing") or {}
    vrule = pricing.get(VIDEO_PATH) or {}
    live = vrule.get("resolutionRates") or {}
    lrule = pricing.get(API_PREFIX + "/apps/" + APP_LIPSYNC + "/submit") or {}
    wild = pricing.get("*") or {}

    rows = [
        {"step": "数字人", "app": APP_LIPSYNC, "cmd": "avatar",
         "endpoint": "POST " + LIPSYNC_PATH,
         "price": "%d 点/秒" % LIPSYNC_PER_SECOND,
         "note": "markupPercent %s（上游 %d 点/秒 x %d），声明保底 %d 点"
                 % (lrule.get("markupPercent"), LIPSYNC_UPSTREAM_PER_SECOND,
                    LIPSYNC_MARKUP, LIPSYNC_FLOOR)},
        {"step": "出图", "app": APP_IMAGE, "cmd": "cover",
         "endpoint": "POST " + IMAGE_PATH,
         "price": "%d 点/张" % IMG_POINTS, "note": "办公场景 / 海报 / 展台，与尺寸无关"},
        {"step": "口播", "app": APP_TTS, "cmd": "voice",
         "endpoint": "POST " + TTS_PATH,
         "price": "约 %.2f 点/字" % TTS_PER_CHAR, "note": "企业音色 tts，上游真实点数 x3"},
        {"step": "克隆音色", "app": APP_TTS, "cmd": "voice --clone",
         "endpoint": "POST " + CLONE_PATH,
         "price": "%d 点/次" % CLONE_POINTS, "note": "上游固定 200 点 x3，一次克隆长期复用"},
        {"step": "配乐", "app": APP_MUSIC, "cmd": "music",
         "endpoint": "POST " + MUSIC_PATH,
         "price": "%d 点起/首" % MUSIC_FLOOR, "note": "落通配：上游 x2，保底 %d 点" % MUSIC_FLOOR},
        {"step": "空镜成片", "app": APP_VIDEO, "cmd": "film",
         "endpoint": "POST " + VIDEO_PATH,
         "price": "480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒",
         "note": "单段 4~15 秒"},
        {"step": "查进度", "app": "网关", "cmd": "status",
         "endpoint": "GET /api/v1/tasks/<task_id>",
         "price": "0 点", "note": "应用层 /query 的计价口径说不清，本包不拿它轮询"},
        {"step": "传图 / 传音频", "app": "网关", "cmd": "upload",
         "endpoint": "POST " + UPLOAD_PATH,
         "price": "0 点", "note": "换 oss.gpu.likeadmin.cn 白名单地址"},
        {"step": "脚本 / 检查", "app": "本地", "cmd": "plan / qc",
         "endpoint": "纯本地，不发请求", "price": "0 点", "note": "四段结构 / 合规十项 / 排期"},
    ]
    for r in rows:
        r["online"] = (r["app"] in online) or r["app"] in ("网关", "本地")
        r["apis"] = len(online.get(r["app"], {}).get("apis") or [])
    plats = [{"key": k, "name": v["name"], "ratio": v["ratio"], "size": v["size"],
              "maxSeconds": v["maxSeconds"]} for k, v in PLATFORMS.items()]
    out = {"ok": True, "rows": rows, "platforms": plats,
           "appsOnline": len(listing),
           "musicApis": len(online.get(APP_MUSIC, {}).get("apis") or []),
           "ttsApis": len(online.get(APP_TTS, {}).get("apis") or []),
           "videoRates": live or VIDEO_RATES,
           "lipsyncRule": {"markupPercent": lrule.get("markupPercent"),
                           "minPoints": lrule.get("minPoints")},
           "wildcard": {"markupPercent": wild.get("markupPercent"),
                        "minPoints": wild.get("minPoints")},
           "pricingRead": st2 == 200,
           "imageCount": len(IMAGE_SETS),
           "yuanPerPoint": 1.0 / POINTS_PER_YUAN}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("三剪客 · 招聘雇主品牌 —— 一个岗位用到的 9 个动作（1 元 = 100 点）")
    print()
    print("  %s %s %s %s" % (pad("动作", 12), pad("子命令", 14), pad("端点", 50), "单价"))
    print("  " + "-" * 110)
    for r in rows:
        print("  %s %s %s %s" % (pad(r["step"], 12), pad(r["cmd"], 14),
                                 pad(r["endpoint"], 50), r["price"]))
        print("        %s" % r["note"])
    print()
    print("  应用目录 %d 个；media_services_33 在架 %d 个接口；voice_tts 在架 %d 个接口。"
          % (len(listing), out["musicApis"], out["ttsApis"]))
    print("  full_video 现查按秒价：%s" % " · ".join(
        "%s %s" % (r, (live or VIDEO_RATES).get(r)) for r in RESOLUTIONS))
    print("  pic_lipsync 现查：markupPercent %s（= 上游 x5）、minPoints %s（声明值）"
          % (lrule.get("markupPercent"), lrule.get("minPoints")))
    print("  通配规则：markupPercent %s（= 上游 x2）、保底 %s 点"
          % (wild.get("markupPercent"), wild.get("minPoints")))
    print()
    print("  平台尺寸（发布页当期口径）")
    print("  %s %s %s %s %s" % (pad("--platform", 14), pad("平台", 16), pad("画幅", 8),
                                 pad("尺寸", 12), "时长上限"))
    print("  " + "-" * 64)
    for p in plats:
        print("  %s %s %s %s %d 秒" % (pad(p["key"], 14), pad(p["name"], 16),
                                       pad(p["ratio"], 8), pad(p["size"], 12),
                                       p["maxSeconds"]))
    print()
    print("  出图清单 %d 张（cover --kind all 一次出齐）。" % len(IMAGE_SETS))
    return 0


def cmd_cost(a, key, host):
    track = a.track
    jobs = max(1, int(a.jobs))
    seconds = int(a.seconds) if a.seconds else TRACK_SECONDS[track]
    avatar = int(a.avatar_seconds) if a.avatar_seconds else (
        30 if track == "social" else 15)
    if avatar >= seconds:
        raise Fail("usage", "--avatar-seconds 要小于 --seconds（数字人段之外还要留空镜）",
                   EXIT_USAGE)
    broll = seconds - avatar
    res = a.resolution
    imgs = max(0, a.images)
    tts_chars = max(0, a.tts_chars)
    music = 1 if a.music else 0
    witness = 1 if a.witness else 0
    wsec = max(VIDEO_CLIP_MIN, int(a.witness_seconds))
    wchars = max(0, a.witness_chars)
    clone = 1 if a.clone else 0

    av_pts = lipsync_points(avatar) * jobs
    br_pts = video_points(broll, res) * jobs
    ipts = imgs * IMG_POINTS * jobs
    tpts = int(round(tts_chars * jobs * TTS_PER_CHAR))
    mpts = MUSIC_FLOOR * music
    wv = video_points(wsec, res) * witness
    wt = int(round(wchars * witness * TTS_PER_CHAR))
    cpts = CLONE_POINTS * clone
    total = av_pts + br_pts + ipts + tpts + mpts + wv + wt + cpts

    items = [
        ("数字人 %d 条 x %d 秒" % (jobs, avatar), av_pts,
         "15 点/秒（上游 3 x5），单条保底 50 点"),
        ("空镜 %d 条 x %d 秒（%s）" % (jobs, broll, res), br_pts,
         "%d 点/秒 x %d 秒 x %d 条" % (VIDEO_RATES[res], broll, jobs)),
        ("场景图 %d 张" % (imgs * jobs), ipts, "6 点/张 x %d 条" % jobs),
        ("空镜旁白 %d 字" % (tts_chars * jobs), tpts, "%d 字/条 x 0.18 点/字" % tts_chars),
        ("配乐 %d 首" % music, mpts, "50 点起/首（通配：上游 x2，保底 50）"),
    ]
    if witness:
        items.append(("员工见证 %d 秒" % wsec, wv,
                      "%d 点/秒（%s）" % (VIDEO_RATES[res], res)))
        items.append(("见证旁白 %d 字" % wchars, wt, "0.18 点/字"))
    if clone:
        items.append(("企业音色克隆 1 次", cpts, "上游固定 200 点 x3，长期复用"))

    matrix = []
    for r in RESOLUTIONS:
        b = video_points(broll, r) * jobs
        w = video_points(wsec, r) * witness
        matrix.append({"resolution": r, "rate": VIDEO_RATES[r],
                       "total": av_pts + b + ipts + tpts + mpts + w + wt + cpts})
    out = {"ok": True, "track": track, "trackName": TRACK_NAMES[track],
           "jobs": jobs, "seconds": seconds, "avatarSeconds": avatar,
           "brollSeconds": broll, "clipsPerBroll": len(clips_for(broll)),
           "resolution": res, "images": imgs, "ttsChars": tts_chars,
           "music": music, "witness": witness, "witnessSeconds": wsec,
           "clone": clone,
           "items": [{"name": n, "points": p, "basis": b} for n, p, b in items],
           "total": total, "yuan": yuan(total),
           "yuanPerJob": yuan(total / float(jobs)),
           "matrix": matrix, "yuanPerPoint": 1.0 / POINTS_PER_YUAN,
           "unitPrice": {"avatar": LIPSYNC_PER_SECOND, "avatarFloor": LIPSYNC_FLOOR,
                         "image": IMG_POINTS, "ttsPerChar": TTS_PER_CHAR,
                         "clone": CLONE_POINTS, "musicFloor": MUSIC_FLOOR,
                         "video": VIDEO_RATES},
           "notes": [
               "1 元 = 100 点；单价取自 GET /api/v1/pricing（2026-11-08 现查）",
               "数字人 15 点/秒 = 上游 standard 档 3 点/秒 x5（markupPercent 400）",
               "价目表里 pic_lipsync 的 minPoints:50 只是声明字段，通用计费不读它",
               "空镜 1080P 60 点/秒 = 0.60 元/秒；480P 只要 14 点/秒",
               "口播按上游真实点数 x3，实测 33 字 5.94 点，按 0.18 点/字估",
               "数字人 text 模式自带口播，这条不用再单独出 TTS",
           ]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("%s %d 条要多少钱（1 元 = 100 点）" % (TRACK_NAMES[track], jobs))
    print()
    print("  每条 %d 秒 = 数字人 %d 秒 + 空镜 %d 秒（%s，空镜拆 %d 段）"
          % (seconds, avatar, broll, res, len(clips_for(broll))))
    print("  " + "-" * 82)
    for n, p, b in items:
        print("  %s %s 点   %s" % (pad(n, 30), pad(fmt_pts(p), 9, left=False), b))
    print("  " + "-" * 82)
    print("  %s %s 点   = %.2f 元（每条约 %.2f 元，一天 6 条按这条算）"
          % (pad("合计", 30), pad(fmt_pts(total), 9, left=False), yuan(total),
             yuan(total / float(jobs))))
    print()
    print("  同一批按分辨率（数字人 / 出图 / 口播 / 配乐不变，只有空镜变）")
    print("    %s %s" % (pad("分辨率", 10), pad("合计点数", 12, left=False) + "  元"))
    for r in matrix:
        print("    %s %s %.2f" % (pad(r["resolution"], 10),
                                  pad(fmt_pts(r["total"]), 12, left=False),
                                  yuan(r["total"])))
    print()
    for n in out["notes"]:
        print("  · %s" % n)
    return 0


# ───────────────────────── 出图（6 点/张）─────────────────────────
def _save_image(outdir, prefix, idx, item):
    ensure_dir(outdir)
    b64 = item.get("b64_json") or item.get("b64") or item.get("image_base64")
    url = item.get("url") or item.get("image_url")
    path = os.path.join(outdir, "%s-%02d.png" % (prefix, idx))
    if b64:
        raw = base64.b64decode(b64)
        with open(path, "wb") as fh:
            fh.write(raw)
        return path, None
    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                with open(path, "wb") as fh:
                    fh.write(r.read())
            return path, url
        except Exception:                                            # noqa: BLE001
            return None, url
    return None, None


def cmd_cover(a, key, host):
    m = _meta(a)
    if a.kind == "all":
        picked = IMAGE_SETS
    else:
        picked = [it for it in IMAGE_SETS if it["kind"] == a.kind]
        if not picked:
            raise Fail("usage", "--kind 取 all 或 %s"
                       % " / ".join([it["kind"] for it in IMAGE_SETS]), EXIT_USAGE)
    n = max(1, min(4, a.n))
    cost = IMG_POINTS * len(picked) * n
    gate(a, cost, "%d 张图 x 6 点/张（%s）"
         % (len(picked) * n, " / ".join([it["name"] for it in picked])))
    url = host + IMAGE_PATH
    if a.dry_run:
        body = {"model": APP_IMAGE, "n": n, "size": IMG_SIZE,
                "prompt": picked[0]["prompt"].format(**m)}
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "kinds": [it["kind"] for it in picked], "requests": len(picked),
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不出图、不扣费）")
        print("  端点：POST %s" % url)
        print("  张数：%d 个图种 x 每组 %d 张 = %d 张" % (len(picked), n, len(picked) * n))
        for it in picked:
            print("  · %s：%s" % (it["name"], it["prompt"].format(**m)[:70]))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    outdir = ensure_dir(a.outdir or OUT_ROOT)
    base = _naming(m, a.track, "full", int(a.seconds), a.platform)
    files, urls, done, billed = [], [], [], 0
    for it in picked:
        prompt = it["prompt"].format(**m)
        body = {"model": APP_IMAGE, "prompt": prompt, "n": n, "size": IMG_SIZE}
        say("正在出「%s」（%d 张）…" % (it["name"], n))
        st, txt = http_json("POST", url, key, body, timeout=600)
        d = jloads(txt) or {}
        items = []
        if isinstance(d.get("data"), list):
            items = d["data"]
        elif isinstance(d.get("data"), dict) and isinstance(d["data"].get("data"), list):
            items = d["data"]["data"]
        if st not in (200, 201) or not items:
            msg = err_text(st, txt)
            ledger_add({"at": now_iso(), "ok": False, "mode": "cover",
                        "kind": it["kind"], "http": st, "error": msg})
            raise Fail("call", "出图失败（%s，HTTP %s）：%s"
                       % (it["kind"], st, msg), EXIT_CALL)
        billed += IMG_POINTS * len(items)
        for i, one in enumerate(items, 1):
            p, u = _save_image(outdir, "%s_%s" % (base, it["kind"]), i, one)
            if p:
                files.append(p)
            if u:
                urls.append(u)
        done.append({"kind": it["kind"], "name": it["name"], "returned": len(items),
                     "prompt": prompt})
    ledger_add({"at": now_iso(), "ok": True, "mode": "cover", "track": a.track,
                "kinds": [x["kind"] for x in done], "files": files, "points": billed})
    out = {"ok": True, "mode": "cover", "kinds": done,
           "requested": len(picked) * n, "returned": len(files),
           "files": files, "urls": urls, "billedPoints": billed,
           "estimatedPoints": cost, "endpoint": IMAGE_PATH}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已出图（%d 张）" % len(files))
    for x in done:
        print("  · %s：%d 张" % (x["name"], x["returned"]))
    for p in files:
        print("  文件：%s" % p)
    for u in urls:
        print("  链接：%s（约 3 小时有效，及时下载）" % u)
    print()
    print("  下一步：`film --image %s --text \"...\" --yes` 让这张图动起来。"
          % (files[0] if files else "office.png"))
    return 0


# ───────────────────────── 数字人（15 点/秒）─────────────────────────
def cmd_avatar(a, key, host):
    text = (a.text or "").strip()
    if not text and a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到口播稿：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"口播文案\" 或 --script 稿子.txt；"
                   "也可以先 `plan` 生成 plan.json，把 voiceover 里数字人那几段粘过来",
                   EXIT_USAGE)
    if not a.image:
        raise Fail("usage", "给 --image HR 的正面半身照（本地路径会自动上传，免费）",
                   EXIT_USAGE)
    if not a.voice_url and not a.voice_file:
        raise Fail("usage",
                   "text 模式要一条参考音色音频：--voice-url 平台地址，或 --voice-file 本地 mp3。\n"
                   "  企业音色的做法：voice --clone --title \"企业音色\" --file 样本.mp3 --yes\n"
                   "  → voice --text \"口播文案\" --reference-id model_xxx --yes\n"
                   "  → 拿返回的 audio_url 喂给这里", EXIT_USAGE)
    seconds = max(1, int(a.seconds)) if a.seconds else 30
    cost = lipsync_points(seconds)
    gate(a, cost, "数字人 %d 秒 x 15 点/秒（上游 standard 3 点/秒 x5，保底 50 点）"
         % seconds)
    url = host + LIPSYNC_PATH
    quality = a.quality or "standard"
    body = {"mode": "text", "model": LIPSYNC_MODEL, "quality": quality,
            "content": text, "image_url": a.image if a.image.startswith("http") else "<上传后替换>",
            "audio_url": a.voice_url or "<上传后替换>"}
    if a.prompt:
        body["prompt"] = a.prompt
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "seconds": seconds, "chars": len(text),
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  模式：text（文案驱动，参考音色读 content）")
        print("  请求：%s" % json.dumps(body, ensure_ascii=False)[:400])
        print("  预估：%d 点（%.2f 元）· %d 秒 / %d 字" % (cost, yuan(cost), seconds, len(text)))
        if a.image and not a.image.startswith("http"):
            print("  人像：%s（会先 upload 换白名单地址，免费）" % a.image)
        return 0

    image_url = a.image
    voice_url = a.voice_url
    if not image_url.startswith("http"):
        r = upload_file(key, host, image_url, timeout=a.timeout)
        image_url = r["url"]
    if voice_file_needed(a):
        r = upload_file(key, host, a.voice_file, timeout=a.timeout)
        voice_url = r["url"]
    body["image_url"] = image_url
    body["audio_url"] = voice_url

    say("正在提交数字人（text 模式，%d 秒，%d 字）…" % (seconds, len(text)))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=180)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "avatar", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    billed = usage.get("points_cost") or data.get("points_cost")
    out = {"ok": True, "mode": "avatar", "taskId": task_id, "status": data.get("status"),
           "seconds": seconds, "chars": len(text), "quality": quality,
           "imageUrl": image_url, "voiceUrl": voice_url,
           "elapsed": round(dt, 1), "estimatedPoints": cost,
           "billedPoints": billed, "frozen": data.get("frozen_points"),
           "next": "python3 scripts/run.py status --task-id %s" % task_id}
    ledger_add({"at": now_iso(), "ok": True, "mode": "avatar", "taskId": task_id,
                "seconds": seconds, "points": billed if billed is not None else cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：text 模式 · %d 秒 · %d 字 · %s 档" % (seconds, len(text), quality))
    print("  参考音色：%s" % voice_url)
    if billed is not None:
        print("  实际点数：%s（返回里的 usage.points_cost）" % fmt_pts(billed))
    else:
        print("  预估点数：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


def voice_file_needed(a):
    return bool(a.voice_file) and not a.voice_url


# ───────────────────────── 企业音色（tts / clone）─────────────────────────
def cmd_voice(a, key, host):
    if a.clone:
        return _voice_clone(a, key, host)
    text = (a.text or "").strip()
    if not text and a.script:
        if not os.path.isfile(a.script):
            raise Fail("usage", "找不到口播稿：%s" % a.script, EXIT_USAGE)
        text = io.open(a.script, encoding="utf-8").read().strip()
    if not text:
        raise Fail("usage", "给 --text \"口播文案\" 或 --script 稿子.txt；"
                   "克隆音色用 --clone --title \"企业音色\" --file 样本.mp3", EXIT_USAGE)
    if len(text) > TTS_MAX_CHARS:
        raise Fail("usage", "这条 %d 字，同步 tts 建议 %d 字内；超过就按段落拆成两三条。"
                   % (len(text), TTS_MAX_CHARS), EXIT_USAGE)
    cost = max(1, int(round(len(text) * TTS_PER_CHAR)))
    gate(a, cost, "口播 %d 字 x 0.18 点/字（上游真实点数 x3，以 usage.points_cost 为准）"
         % len(text))
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
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（约 %.2f 元）· %d 字" % (cost, yuan(cost), len(text)))
        return 0

    say("正在合成口播（%d 字）…" % len(text))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=300)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d) if isinstance(d, dict) else {}
    audio = data.get("audio_url") or data.get("audioUrl") or data.get("url")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost") or data.get("actual_points")
    if st not in (200, 201) or not audio:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "voice", "http": st, "error": msg})
        raise Fail("call", "配音失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    outdir = ensure_dir(a.outdir or OUT_ROOT)
    txt_path = os.path.join(outdir, "%s-voice.txt" % (a.prefix or "recruit"))
    write_text(txt_path, text + "\n")
    out = {"ok": True, "mode": "voice", "audioUrl": audio, "chars": len(text),
           "elapsed": round(dt, 1), "textFile": txt_path,
           "referenceId": a.reference_id, "billedPoints": real,
           "estimatedPoints": cost, "yuan": yuan(cost), "endpoint": TTS_PATH}
    ledger_add({"at": now_iso(), "ok": True, "mode": "voice", "chars": len(text),
                "audio": audio, "points": real if real is not None else cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已合成（%.1fs）" % dt)
    print("  音频：%s" % audio)
    print("  稿子：%s" % txt_path)
    if real is not None:
        print("  实际点数：%s（返回里的 usage.points_cost）" % fmt_pts(real))
    else:
        print("  预估点数：%d 点（约 %.2f 元）" % (cost, yuan(cost)))
    print()
    print("  下一步：把这条 audio_url 作为 --voice-url 喂给 avatar（数字人参考音色）。")
    return 0


def _voice_clone(a, key, host):
    if not a.title:
        raise Fail("usage", "克隆音色要给 --title \"XX 企业音色\"（音色名，必填）", EXIT_USAGE)
    if not a.audio_url and not a.file:
        raise Fail("usage", "给 --audio-url 参考音频地址，或 --file 本地样本.mp3"
                   "（建议 %d 秒 ~ 5 分钟）" % CLONE_MIN_SECONDS, EXIT_USAGE)
    cost = CLONE_POINTS
    gate(a, cost, "音色克隆 1 次（上游固定 200 点 x3），克隆一次长期复用")
    url = host + CLONE_PATH
    if a.dry_run:
        body = {"title": a.title, "description": a.description or "",
                "audio_url": a.audio_url or ("<上传 %s 后替换>" % (a.file or ""))}
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不克隆、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    if not a.audio_url:
        if not os.path.isfile(a.file):
            raise Fail("usage", "找不到样本文件：%s" % a.file, EXIT_USAGE)
        say("正在上传样本 %s（免费）…" % os.path.basename(a.file))
        st, txt = http_multipart(url, key, {"title": a.title},
                                 [("voices", a.file)], timeout=a.timeout)
    else:
        say("正在克隆音色「%s」…" % a.title)
        st, txt = http_json("POST", url, key,
                            {"title": a.title, "description": a.description or "",
                             "audio_url": a.audio_url}, timeout=a.timeout)
    d = jloads(txt) or {}
    data = payload_of(d)
    model_id = None
    if isinstance(data, dict):
        model_id = data.get("model_id") or data.get("id") or data.get("modelId")
    if st not in (200, 201) or not model_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "clone", "http": st, "error": msg})
        raise Fail("call", "克隆失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    out = {"ok": True, "mode": "clone", "modelId": model_id, "title": a.title,
           "type": data.get("type"), "estimatedPoints": cost, "yuan": yuan(cost),
           "next": "python3 scripts/run.py voice --text \"...\" --reference-id %s --yes"
                   % model_id}
    ledger_add({"at": now_iso(), "ok": True, "mode": "clone", "modelId": model_id,
                "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已克隆（0 秒出结果时多半是复用了同名音色）")
    print("  音色名：%s" % a.title)
    print("  model_id：%s" % model_id)
    print("  预估点数：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  下一步：voice --text \"口播文案\" --reference-id %s --yes" % model_id)
    return 0


# ───────────────────────── 配乐（50 点起）─────────────────────────
MUSIC_STYLE = {
    "social": "轻快电子加清楚鼓点，112 BPM，适合 45 秒岗位介绍，中段留口播空隙",
    "campus": "明亮钢琴加弦乐拨奏，104 BPM，适合 30 秒校招片，结尾上扬",
}


def find_media_url(node, depth=0):
    if depth > 8:
        return None
    if isinstance(node, str):
        low = node.lower()
        if node.startswith("http") and any(x in low for x in (".mp3", ".wav", ".m4a", ".flac")):
            return node
        return None
    if isinstance(node, dict):
        for k in ("audio_url", "audioUrl", "audio", "url", "source_url", "sourceUrl"):
            v = node.get(k)
            if isinstance(v, str) and v.startswith("http"):
                if any(x in v.lower() for x in (".mp3", ".wav", ".m4a", ".flac")):
                    return v
        for v in node.values():
            got = find_media_url(v, depth + 1)
            if got:
                return got
    elif isinstance(node, list):
        for v in node:
            got = find_media_url(v, depth + 1)
            if got:
                return got
    return None


def cmd_music(a, key, host):
    prompt = a.style or MUSIC_STYLE[a.track]
    cost = MUSIC_FLOOR
    gate(a, cost, "配乐 1 首，通配保底 50 点（上游 x2，实际以 usage.points_cost 为准）")
    url = host + MUSIC_PATH
    body = {"model": a.music_model, "custom_mode": False,
            "instrumental": True, "prompt": prompt}
    if a.title:
        body["title"] = a.title
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不生成、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        print("  预估：%d 点起（%.2f 元起）" % (cost, yuan(cost)))
        return 0

    say("正在生成配乐…")
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=600)
    dt = time.time() - t0
    d = jloads(txt) or {}
    if st not in (200, 201) or (isinstance(d, dict) and d.get("code") == 0):
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "music", "http": st, "error": msg})
        raise Fail("call", "配乐失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    data = payload_of(d)
    audio = find_media_url(data) or find_media_url(d)
    task_id = data.get("task_id") or data.get("taskId") or d.get("task_id")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    real = usage.get("points_cost") or data.get("points_cost")
    out = {"ok": bool(audio or task_id), "mode": "music", "audioUrl": audio,
           "taskId": task_id, "elapsed": round(dt, 1), "style": prompt,
           "billedPoints": real, "estimatedPoints": cost, "yuan": yuan(cost)}
    ledger_add({"at": now_iso(), "ok": bool(audio or task_id), "mode": "music",
                "audio": audio, "taskId": task_id,
                "points": real if real is not None else cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if (audio or task_id) else EXIT_CALL
    if audio:
        print("已生成配乐（%.1fs）" % dt)
        print("  音频：%s" % audio)
    elif task_id:
        print("已提交配乐任务（%.1fs）" % dt)
        print("  任务：%s" % task_id)
        print("  查进度：python3 scripts/run.py status --task-id %s" % task_id)
    else:
        print("返回里没有音频地址，原始返回前 600 字：")
        print("  " + json.dumps(d, ensure_ascii=False)[:600])
        return EXIT_CALL
    if real is not None:
        print("  实际点数：%s" % fmt_pts(real))
    else:
        print("  预估点数：%d 点起（约 %.2f 元起）" % (cost, yuan(cost)))
    return 0


# ───────────────────────── 上传（免费）─────────────────────────
def upload_file(key, host, path, timeout=600, field_name="file"):
    if not path or not os.path.isfile(path):
        raise Fail("usage", "文件不存在：%s" % path, EXIT_USAGE)
    size = os.path.getsize(path)
    say("正在上传 %s（%d 字节，免费）…" % (os.path.basename(path), size))
    st, txt = http_multipart(host + UPLOAD_PATH, key, {}, [(field_name, path)],
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
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": host + UPLOAD_PATH, "file": a.file,
               "estimatedPoints": 0}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不上传、不扣费）")
        print("  端点：POST %s（multipart，字段名 file）" % (host + UPLOAD_PATH))
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
    print("  归属：%s（在上游白名单内，可以直接给 avatar / film 用）" % r["hostKind"])
    return 0


# ───────────────────────── 空镜成片（按秒计费）─────────────────────────
def cmd_film(a, key, host):
    text = (a.text or "").strip()
    if not text:
        raise Fail("usage", "给 --text \"画面与运镜描述\"（把 plan 里的空镜提示词粘过来）",
                   EXIT_USAGE)
    seconds = max(VIDEO_CLIP_MIN, int(a.seconds))
    if seconds > VIDEO_CLIP_MAX:
        raise Fail("usage", "full_video 单段 4~15 秒；%d 秒分 %s 两段提交。"
                   % (seconds, "+".join(str(x) for x in clips_for(seconds))), EXIT_USAGE)
    ratio = a.ratio or "9:16"
    cost = video_points(seconds, a.resolution)
    gate(a, cost, "空镜 %d 秒 x %d 点/秒（%s）"
         % (seconds, VIDEO_RATES[a.resolution], a.resolution))

    image_url = None
    if a.image:
        if a.image.startswith("http"):
            ok, kind = url_allowed(a.image)
            if not ok and not a.allow_any_url:
                raise Fail("usage",
                           "首帧图必须是平台托管地址（%s 不在白名单）。两种写法：\n"
                           "  · 本地图直接给路径：--image office.png（film 会自动 upload，免费）\n"
                           "  · 本站地址：https://oss.gpu.likeadmin.cn/openapi/…" % kind,
                           EXIT_USAGE)
            image_url = a.image
        elif not os.path.isfile(a.image):
            raise Fail("usage", "找不到首帧图：%s" % a.image, EXIT_USAGE)

    content = [{"type": "text", "text": text}]
    body = {"model": "full-video", "content": content, "duration": seconds,
            "resolution": a.resolution, "ratio": ratio, "aigc_watermark": False}
    if image_url:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})
    url = host + VIDEO_PATH
    if a.dry_run:
        out = {"ok": True, "dryRun": True, "url": url, "requestBody": body,
               "estimatedPoints": cost, "yuan": yuan(cost)}
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        print("干跑（不提交、不冻结、不扣费）")
        print("  端点：POST %s" % url)
        print("  请求：%s" % json.dumps(body, ensure_ascii=False))
        if a.image and not image_url:
            print("  首帧：%s（会先用 upload 换白名单地址，免费）" % a.image)
        print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
        return 0

    if a.image and not image_url:
        r = upload_file(key, host, a.image, timeout=a.timeout)
        image_url = r["url"]
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": image_url}})

    say("正在提交空镜（%s，%d 秒）…" % (a.resolution, seconds))
    t0 = time.time()
    st, txt = http_json("POST", url, key, body, timeout=180)
    dt = time.time() - t0
    d = jloads(txt) or {}
    data = payload_of(d)
    task_id = None
    if isinstance(data, dict):
        task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if st not in (200, 201) or not task_id:
        msg = err_text(st, txt)
        ledger_add({"at": now_iso(), "ok": False, "mode": "film", "http": st,
                    "error": msg, "seconds": seconds})
        raise Fail("call", "提交失败（HTTP %s）：%s" % (st, msg), EXIT_CALL)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    out = {"ok": True, "mode": "film", "taskId": task_id, "status": data.get("status"),
           "resolution": a.resolution, "seconds": seconds, "ratio": ratio,
           "firstFrame": image_url, "elapsed": round(dt, 1),
           "estimatedPoints": cost,
           "billedPoints": usage.get("points_cost") or data.get("points_cost")}
    ledger_add({"at": now_iso(), "ok": True, "mode": "film", "taskId": task_id,
                "seconds": seconds, "resolution": a.resolution, "points": cost})
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("已提交（%.1fs）" % dt)
    print("  任务：%s   状态：%s" % (task_id, data.get("status")))
    print("  规格：%s · %d 秒 · %s" % (a.resolution, seconds, ratio))
    if image_url:
        print("  首帧：%s" % image_url)
    print("  预估：%d 点（%.2f 元）" % (cost, yuan(cost)))
    print()
    print("  查进度（0 点）：python3 scripts/run.py status --task-id %s" % task_id)
    return 0


# ───────────────────────── 查任务（免费）─────────────────────────
def cmd_status(a, key, host):
    if not a.task_id:
        raise Fail("usage", "必须给 --task-id", EXIT_USAGE)
    path = API_PREFIX + "/tasks/" + a.task_id
    st, txt = http_json("GET", host + path, key, timeout=40)
    d = jloads(txt) or {}
    out = {"ok": True, "taskId": a.task_id, "path": path, "http": st,
           "status": None, "result": None, "estimatedPoints": 0}
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

    # 通用查询看不到应用层任务时，才走应用自己的 query（要先 --yes：口径说不清）
    if not found and a.app:
        if not a.yes and not a.dry_run:
            raise Fail("confirm",
                       "通用 GET /tasks 说任务不存在，要用 %s 的应用层 /query 再查一次。"
                       "这条路的计价口径在价目表里与 submit 同 path，说不清算不算钱，"
                       "确认请加 --yes。" % a.app, EXIT_CONFIRM)
        qpath = API_PREFIX + "/apps/" + a.app + "/query"
        if a.dry_run:
            out["dryRun"] = True
            out["appQuery"] = qpath
            out["requestBody"] = {"task_id": a.task_id}
        else:
            st2, txt2 = http_json("POST", host + qpath, key,
                                  {"task_id": a.task_id}, timeout=60)
            d2 = jloads(txt2) or {}
            data2 = payload_of(d2)
            data2 = data2 if isinstance(data2, dict) else {}
            out.update({"appQuery": qpath, "appHttp": st2,
                        "status": data2.get("status") or out.get("status"),
                        "videoUrl": data2.get("videoUrl") or data2.get("video_url")
                        or out.get("videoUrl"),
                        "audioUrl": data2.get("audioUrl") or data2.get("audio_url"),
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
    if out.get("cost") is not None:
        print("  实扣：%s 点" % fmt_pts(out["cost"]))
    if out.get("refund") is not None:
        print("  退回：%s 点" % fmt_pts(out["refund"]))
    if out.get("videoUrl"):
        print("  成片：%s（及时转存）" % out["videoUrl"])
    if out.get("audioUrl"):
        print("  音频：%s" % out["audioUrl"])
    if out.get("result") is not None:
        print("  结果：%s" % json.dumps(out["result"], ensure_ascii=False)[:600])
    if out.get("appQuery"):
        print("  应用层查询：POST %s（已加 --yes）" % out["appQuery"])
    if not found and not a.app:
        print()
        print("  通用查询看不到应用层任务时，加 `--app pic_lipsync --yes` 走应用自己的 query。")
    return 0


# ───────────────────────── 自检（0 点）─────────────────────────
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
    need = [APP_LIPSYNC, APP_TTS, APP_VIDEO, APP_MUSIC]
    miss = [c for c in need if c not in online]
    checks.append(("4 个底层应用在架（数字人 / 音色 / 成片 / 配乐）",
                   bool(listing) and not miss,
                   "目录 %d 个应用%s" % (len(listing),
                                        "，缺 " + ",".join(miss) if miss else "")))
    lipsync_apis = [x.get("code") for x in (online.get(APP_LIPSYNC, {}).get("apis") or [])]
    checks.append(("pic_lipsync 的 submit / query 两个接口都在",
                   "submit" in lipsync_apis and "query" in lipsync_apis,
                   "接口：%s（用 /apps 列表验证，不发 /apps/pic_lipsync 那条扣费 GET）"
                   % " / ".join(lipsync_apis)))
    music_apis = len(online.get(APP_MUSIC, {}).get("apis") or [])
    checks.append(("media_services_33 的 29 个接口齐全", music_apis >= 29,
                   "在架 %d 个接口（配乐取 music_generate）" % music_apis))

    st3, txt3 = http_json("GET", host + API_PREFIX + "/pricing", key, timeout=60)
    pricing = (jloads(txt3) or {}).get("pricing") or {}
    lrule = pricing.get(LIPSYNC_PATH) or {}
    vrule = pricing.get(VIDEO_PATH) or {}
    live = vrule.get("resolutionRates") or {}
    drift = ["%s 本地 %d / 线上 %s" % (r, p, live.get(r))
             for r, p in VIDEO_RATES.items() if int(live.get(r) or -1) != p]
    checks.append(("full_video 5 档按秒价与线上一致",
                   st3 == 200 and bool(live) and not drift,
                   "HTTP %s · %s" % (st3, "5 档全一致" if not drift else " / ".join(drift)[:110])))
    checks.append(("pic_lipsync 倍率 400（= 上游 x5）与本地口径一致",
                   int(lrule.get("markupPercent") or 0) == 400
                   and int(lrule.get("cost") if lrule.get("cost") is not None else 1) == 0,
                   "markupPercent %s · cost %s · minPoints %s（声明值）"
                   % (lrule.get("markupPercent"), lrule.get("cost"),
                      lrule.get("minPoints"))))

    wild = pricing.get("*") or {}
    up_rule = pricing.get(UPLOAD_PATH) or {}
    ok_price = (int(wild.get("minPoints") or 0) == MUSIC_FLOOR
                and int(up_rule.get("cost") if up_rule.get("cost") is not None else 999) == 0)
    checks.append(("配乐保底 50 点 + upload 0 点", ok_price,
                   "通配保底 %s · upload cost %s"
                   % (wild.get("minPoints"), up_rule.get("cost"))))

    st4, txt4 = http_json("POST", host + IMAGE_PATH, key,
                          {"model": APP_IMAGE, "prompt": ""}, timeout=60)
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

    st6, txt6 = http_json("GET", host + API_PREFIX + "/tasks/sanjianke-recruit-doctor-probe",
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

    first8 = _last_log(key, host)
    checks.append(("本轮没有新增流水（扣 0 点）", first0 == first8,
                   "自检前后最新一笔流水一致" if first0 == first8
                   else "出现新流水，请发出来排查"))

    st9, txt9 = http_json("GET", host + "/user/balance/logs?limit=1", key, timeout=40)
    d9 = jloads(txt9) or {}
    last = None
    if (d9.get("logs") or []):
        row = d9["logs"][0]
        last = {"at": row.get("at"), "type": row.get("type"),
                "points": row.get("points"), "balanceAfter": row.get("balanceAfter"),
                "reference": row.get("reference")}

    out = {"ok": all(c[1] for c in checks), "requests": 9,
           "estimatedPoints": 0, "yuan": 0.0, "lastLedger": last,
           "apps": need, "lipsyncApis": lipsync_apis,
           "videoRates": live or VIDEO_RATES,
           "lipsyncRule": {"markupPercent": lrule.get("markupPercent"),
                           "minPoints": lrule.get("minPoints"),
                           "perSecond": LIPSYNC_PER_SECOND},
           "platforms": [{"key": k, "name": v["name"], "ratio": v["ratio"],
                          "size": v["size"]} for k, v in PLATFORMS.items()],
           "endpoints": {"lipsync": host + LIPSYNC_PATH,
                         "tts": host + TTS_PATH,
                         "clone": host + CLONE_PATH,
                         "image": host + IMAGE_PATH,
                         "music": host + MUSIC_PATH,
                         "film": host + VIDEO_PATH,
                         "task": host + API_PREFIX + "/tasks/<task_id>",
                         "upload": host + UPLOAD_PATH},
           "checks": [{"name": n, "ok": o, "detail": dd} for n, o, dd in checks]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["ok"] else EXIT_GATE
    print("自检（只读 GET + 空 prompt 422 + 空 body 视频探针 + 缺 file 上传，"
          "全部停在扣费之前）")
    print()
    for n, o, dd in checks:
        print("  %s %s %s" % ("√" if o else "×", pad(n, 54), dd))
    print()
    if last:
        print("  最近一笔流水：%s  %s  %s 点  余额 %s"
              % (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime((last["at"] or 0) / 1000.0)),
                 last.get("type") or "-", fmt_pts(last.get("points") or 0),
                 fmt_pts(last.get("balanceAfter") or 0)))
    print("  本次自检 0 点、0 冻结：9 个请求里没有一条会建任务。")
    print()
    print("  数字人：POST /apps/pic_lipsync/submit（15 点/秒，保底 50 点声明值）")
    print("  成片：POST /apps/full_video/submit · 出图：POST /images/generations（6 点/张）")
    print("  音色：POST /apps/voice_tts/tts（0.18 点/字）· clone_voice（600 点/次）")
    print("  查询：GET /api/v1/tasks/<task_id>（0 点；应用层 /query 口径说不清）")
    return 0 if out["ok"] else EXIT_GATE


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
        mode = e.get("mode") or "-"
        what = e.get("taskId") or e.get("audio") or e.get("modelId") or e.get("error") or "-"
        pts = e.get("points")
        print("  %s  %-5s %-6s %-34s %s" % (
            e.get("at"), "ok" if e.get("ok") else "fail", mode,
            str(what)[:34], ("%s 点" % fmt_pts(pts)) if pts is not None else "-"))
    return 0


# ───────────────────────── CLI ─────────────────────────
def add_job_args(p):
    p.add_argument("--track", choices=["social", "campus"], default="social",
                   help="social 社招 / campus 校招（默认 social）")
    p.add_argument("--company", default="示例科技", help="公司全称（招聘主体，照写）")
    p.add_argument("--job", default="后端开发工程师", help="岗位名")
    p.add_argument("--dept", default="招聘中台", help="部门 / 团队名")
    p.add_argument("--city", default="杭州", help="工作地点（默认 杭州）")
    p.add_argument("--salary", default="15-25K·14薪", help="薪资区间 + 发放结构")
    p.add_argument("--contract", default="六险一金", help="合同与福利口径")
    p.add_argument("--scope", default="招聘链路的服务端设计与稳定性", help="一句话岗位职责")
    p.add_argument("--team-size", dest="team_size", type=int, default=18, help="团队人数")
    p.add_argument("--report-to", dest="report_to", default="技术负责人", help="汇报对象")
    p.add_argument("--collab", default="后端 8 人、前端 4 人同层办公", help="协作方式")
    p.add_argument("--level", default="P5", help="起点职级")
    p.add_argument("--next", default="P7", help="晋升终点职级")
    p.add_argument("--growth-cases", dest="growth_cases", type=int, default=12,
                   help="去年走通这条通道的同事数")
    p.add_argument("--growth-years", dest="growth_years", default="2.5",
                   help="平均几年走完（数字）")
    p.add_argument("--apply", default="hr@example.com 或官网 join.example.com",
                   help="投递入口（邮箱 / 网申 / 内推码）")
    p.add_argument("--deadline", default="11 月 30 日", help="投递截止日期")
    p.add_argument("--industry", default="企业服务 SaaS", help="行业（校招用）")
    p.add_argument("--company-size", dest="company_size", type=int, default=320,
                   help="公司人数（校招用）")
    p.add_argument("--open-roles", dest="open_roles", type=int, default=6,
                   help="校招开放岗位数")
    p.add_argument("--program", default="星火训练营", help="培养体系名称（校招用）")
    p.add_argument("--rotate-months", dest="rotate_months", type=int, default=3,
                   help="轮岗月数（校招用）")
    p.add_argument("--story-name", dest="story_name", default="小林", help="见证人名字")
    p.add_argument("--story-years", dest="story_years", type=int, default=2,
                   help="见证人入职年限")
    p.add_argument("--story-role", dest="story_role", default="小组长",
                   help="见证人现在岗位")
    p.add_argument("--story-team", dest="story_team", type=int, default=4,
                   help="见证人现在带几个人")
    p.add_argument("--phone", default="", help="联系方式（留空写「站内私信」）")
    p.add_argument("--platform", choices=PLATFORM_KEYS, default="douyin",
                   help="发布平台（默认 douyin 抖音）")
    p.add_argument("--seconds", type=int, default=0,
                   help="主片秒数（默认社招 45 / 校招 30）")
    p.add_argument("--short-seconds", dest="short_seconds", type=int, default=15,
                   help="投递引导快切秒数（默认 15；给 0 就只交主片）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="空镜分辨率（默认 1080P）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.add_argument("--outdir", help="输出目录（默认 ~/.a7w/recruit/<track>-<日期>）")


def _parser():
    ap = argparse.ArgumentParser(
        prog="run.py",
        description="三剪客 · 招聘雇主品牌（JD 视频化 / 校招社招两套话术 / 雇主品牌素材，"
                    "走 api.a7w.cn）",
        epilog="端点：POST %s/api/v1/apps/pic_lipsync/submit · "
               "POST %s/api/v1/apps/full_video/submit · "
               "POST %s/api/v1/apps/voice_tts/tts · "
               "POST %s/api/v1/apps/media_services_33/music_generate · "
               "POST %s/api/v1/images/generations · "
               "GET %s/api/v1/tasks/<task_id> · POST %s/api/v1/upload"
               % ((DEFAULT_HOST,) * 7),
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--key", help="API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）")
    ap.add_argument("--host", help="网关地址（默认 https://api.a7w.cn）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="点数上限（单位：点，默认 %d = 100 元）" % DEFAULT_BUDGET)
    ap.add_argument("--max-tokens", type=int, default=0, help="（本包不用；保持家族参数一致）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("catalog", help="五条能力 + 端点 + 现查单价 + 平台尺寸（免费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_catalog)

    p = sub.add_parser("cost", help="一条 / 六条 / 一周要多少钱（免费）", allow_abbrev=False)
    p.add_argument("--track", choices=["social", "campus"], default="social",
                   help="social 社招 45 秒 / campus 校招 30 秒（默认 social）")
    p.add_argument("--jobs", type=int, default=1, help="几条（默认 1，一天 6 条是常规量）")
    p.add_argument("--seconds", type=int, default=0, help="主片秒数（默认社招 45 / 校招 30）")
    p.add_argument("--avatar-seconds", dest="avatar_seconds", type=int, default=0,
                   help="数字人段秒数（默认社招 30 / 校招 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="空镜分辨率（默认 1080P）")
    p.add_argument("--images", type=int, default=6, help="每条几张场景图（默认 6）")
    p.add_argument("--tts-chars", dest="tts_chars", type=int, default=100,
                   help="每条空镜旁白字数（默认 100，和 plan 的空镜口播对齐）")
    p.add_argument("--music", type=int, default=1, choices=[0, 1], help="配乐 1 首（默认 1）")
    p.add_argument("--witness", type=int, default=0, choices=[0, 1],
                   help="加 1 条员工见证（默认 0）")
    p.add_argument("--witness-seconds", dest="witness_seconds", type=int, default=20,
                   help="员工见证秒数（默认 20，单段 4~15 会拆）")
    p.add_argument("--witness-chars", dest="witness_chars", type=int, default=100,
                   help="员工见证旁白字数（默认 100）")
    p.add_argument("--clone", type=int, default=0, choices=[0, 1],
                   help="加 1 次企业音色克隆（600 点，默认 0）")
    p.set_defaults(fn=cmd_cost)

    p = sub.add_parser("plan", help="一个岗位的脚本 / 文案 / 排期 / 交付单（免费，纯本地）",
                       allow_abbrev=False)
    add_job_args(p)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("qc", help="合规与交付检查（免费，纯本地）", allow_abbrev=False)
    p.add_argument("--plan", help="plan.json 路径")
    p.add_argument("--text", help="直接检查一条文案")
    p.add_argument("--platform", choices=PLATFORM_KEYS, default="douyin",
                   help="--text 模式下的平台（默认 douyin）")
    p.add_argument("--company", default="", help="--text 模式下的公司全称")
    p.add_argument("--city", default="", help="--text 模式下的工作地点")
    p.add_argument("--salary", default="", help="--text 模式下的薪资区间")
    p.add_argument("--seconds", type=int, default=45, help="--text 模式下的时长")
    p.set_defaults(fn=cmd_qc)

    p = sub.add_parser("cover", help="出图：办公场景 / 招聘海报 / 校招展台（6 点/张，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--kind", default="all",
                   help="all / office / meeting / coffee / mentor / poster / campus（默认 all）")
    p.add_argument("--n", type=int, default=1, help="每个图种出几张 1~4（默认 1）")
    add_job_args(p)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_cover)

    p = sub.add_parser("avatar", help="图片数字人口播（15 点/秒，要 --yes）",
                       allow_abbrev=False)
    p.add_argument("--image", help="HR 正面半身照：本地路径（自动上传）或平台地址")
    p.add_argument("--text", help="口播文案（text 模式，参考音色读它）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--voice-url", dest="voice_url", help="参考音色音频（平台地址）")
    p.add_argument("--voice-file", dest="voice_file", help="参考音色音频（本地，自动上传）")
    p.add_argument("--seconds", type=int, default=30, help="口播秒数（默认 30）")
    p.add_argument("--quality", choices=LIPSYNC_QUALITIES, default="standard",
                   help="standard / fast / max（默认 standard，按 15 点/秒估）")
    p.add_argument("--prompt", help="人物动作与画面提示词（可选）")
    p.add_argument("--allow-any-url", action="store_true", help="跳过本地白名单预检")
    p.add_argument("--timeout", type=int, default=600, help="提交超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_avatar)

    p = sub.add_parser("voice", help="企业音色 TTS（0.18 点/字）或克隆（600 点/次）",
                       allow_abbrev=False)
    p.add_argument("--text", help="口播文案（500 字内）")
    p.add_argument("--script", help="从文本文件读口播稿")
    p.add_argument("--reference-id", dest="reference_id", help="克隆音色的 model_id")
    p.add_argument("--clone", action="store_true", help="切到克隆模式（600 点/次）")
    p.add_argument("--title", help="音色名（--clone 必填）")
    p.add_argument("--description", help="音色描述（--clone 可选）")
    p.add_argument("--audio-url", dest="audio_url", help="参考音频地址（--clone）")
    p.add_argument("--file", help="参考音频本地路径（--clone，multipart 上传）")
    p.add_argument("--tts-model", dest="tts_model", default=TTS_MODEL, help="s1 / s2-pro")
    p.add_argument("--tts-format", dest="tts_format", default="mp3", help="mp3 / wav / opus")
    p.add_argument("--prefix", default="recruit", help="稿子文件名前缀")
    p.add_argument("--outdir", help="稿子目录（默认 ~/.a7w/recruit/out）")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="配乐（50 点起/首，要 --yes）", allow_abbrev=False)
    p.add_argument("--style", help="风格描述，例如「轻快电子 112 BPM」")
    p.add_argument("--title", help="曲名（可选）")
    p.add_argument("--track", choices=["social", "campus"], default="social",
                   help="按话术选默认风格（默认 social）")
    p.add_argument("--music-model", dest="music_model", default=MUSIC_MODEL,
                   help="Suno 模型（默认 %s）" % MUSIC_MODEL)
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("film", help="空镜 / 氛围成片（按秒计费，要 --yes）", allow_abbrev=False)
    p.add_argument("--text", help="画面与运镜描述（把 plan 的空镜提示词粘过来）")
    p.add_argument("--image", help="首帧图：本地路径（自动上传）或平台地址")
    p.add_argument("--seconds", type=int, default=15, help="单段秒数 4~15（默认 15）")
    p.add_argument("--resolution", choices=RESOLUTIONS, default="1080P",
                   help="分辨率（默认 1080P）")
    p.add_argument("--ratio", choices=RATIOS, default=None, help="画幅（默认 9:16）")
    p.add_argument("--allow-any-url", action="store_true",
                   help="跳过本地白名单预检，把地址交给上游判断")
    p.add_argument("--timeout", type=int, default=600, help="超时秒数（默认 600）")
    p.add_argument("--yes", action="store_true", help="确认真实扣费")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_film)

    p = sub.add_parser("upload", help="上传本地图片 / 音频，拿白名单地址（免费）",
                       allow_abbrev=False)
    p.add_argument("--file", help="本地文件路径")
    p.add_argument("--timeout", type=int, default=600, help="上传超时秒数（默认 600）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不上传")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("status", help="查任务进度（免费）", allow_abbrev=False)
    p.add_argument("--task-id", help="提交时返回的 task_id")
    p.add_argument("--app", help="通用查询看不到时，指定应用（如 pic_lipsync）走它的 /query")
    p.add_argument("--yes", action="store_true", help="确认应用层 /query（口径说不清）")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不提交")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("doctor", help="自检 Key / 应用 / 价目 / 端点（免费，不扣费）",
                       allow_abbrev=False)
    p.set_defaults(fn=cmd_doctor)

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


FREE = ("cmd_catalog", "cmd_cost", "cmd_plan", "cmd_qc", "cmd_log", "cmd_doctor")
LOCAL_ONLY = ("cmd_cost", "cmd_plan", "cmd_qc")


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
