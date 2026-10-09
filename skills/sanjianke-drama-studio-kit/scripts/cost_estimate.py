#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 短剧创作台 —— 存储、带宽与生成成本测算。

**默认纯本地计算**：不联网、不写文件，用于判断成本的量级与结构，不用于精确预算。
把这个脚本放进 CI 或离线环境里跑，行为与以前一致。

要按 **api.a7w.cn 的真实单价**算（推荐），两种方式任选：

    python cost_estimate.py --episodes 30 --minutes 2 --a7w-live
        # 现场拉一次真实单价：GET /api/v1/pricing + GET /api/v1/apps/<app> 的 tenant_* 字段价
    python scripts/run.py pricing --out a7w-prices.json
    python cost_estimate.py --episodes 30 --minutes 2 --price-file a7w-prices.json
        # 先把单价快照落下来（可留档、可进版本库、可离线复算），再按它算

真实单价怎么折算成「每次生成单价」：

    出图   nano_banana/submit   按次         1 点 = 0.01 元（1 元 = 100 点）
    出片   full_video/submit    按分辨率每秒，× --clip-seconds 得到每段单价
    配音   voice_tts/tts        按千字，× --tts-chars / 1000 得到每次单价

    快照里 image 的 tenant 价为 0（分档计费在上游结算），所以要拿实测值：
    `run.py pricing --probe image` 会真跑一次 1K 文生图，把 usage.points_cost 记进快照。

示例：

    # 30 集，每集 2 分钟，用示例单价完整测算
    python cost_estimate.py --episodes 30 --minutes 2

    # 只看存储与带宽，不计生成成本
    python cost_estimate.py --episodes 30 --minutes 2 \\
        --gen-image 0 --gen-video 0 --gen-tts 0

    # 缩短中间素材保存周期
    python cost_estimate.py --episodes 30 --minutes 2 --lifecycle-days 7

    # 按 1080P、每段 6 秒、每句 24 字的真实口径算
    python cost_estimate.py --episodes 30 --minutes 2 --a7w-live \\
        --a7w-video-resolution 1080P --clip-seconds 6 --tts-chars 24
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

POINTS_PER_YUAN = 100.0          # 平台口径：1 元 = 100 点，1 点 = 0.01 元


def build_parser():
    p = argparse.ArgumentParser(
        description='AI 短剧创作台 —— 成本量级测算（默认不联网；'
                    '--a7w-live / --price-file 可按 api.a7w.cn 真实单价算）',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    g = p.add_argument_group('产出规模')
    g.add_argument('--episodes', type=int, default=30, help='集数')
    g.add_argument('--minutes', type=float, default=2.0, help='单集时长（分钟）')

    g = p.add_argument_group('画质与素材比例')
    g.add_argument('--quality', type=float, default=1.0,
                   help='画质系数，1.0 约等于 1080p / 4 Mbps')
    g.add_argument('--shoot-ratio', type=float, default=1.6,
                   help='实际生成量 / 最终采用量，用于计入废片')
    g.add_argument('--intermediate-ratio', type=float, default=2.0,
                   help='中间素材相对生成量的额外占比')

    g = p.add_argument_group('存储与带宽单价（占位示例值）')
    g.add_argument('--storage-per-gb', type=float, default=0.12,
                   help='对象存储单价（元 / GB / 月）')
    g.add_argument('--egress-per-gb', type=float, default=0.50,
                   help='回源带宽单价（元 / GB）')
    g.add_argument('--preview-count', type=float, default=3.0,
                   help='每集成片平均被完整回源 / 预览的次数')
    g.add_argument('--lifecycle-days', type=int, default=30,
                   help='中间素材保留天数，用于折算留存占用')

    g = p.add_argument_group('生成次数（每集）')
    g.add_argument('--gen-image', type=float, default=40.0, help='每集图片生成次数')
    g.add_argument('--gen-video', type=float, default=30.0, help='每集视频生成次数')
    g.add_argument('--gen-tts', type=float, default=30.0, help='每集配音生成次数')

    g = p.add_argument_group('生成单价（占位示例值；给了真实单价来源时会被覆盖）')
    g.add_argument('--image-unit', type=float, default=0.04, help='单张图片单价（元）')
    g.add_argument('--video-unit', type=float, default=2.00, help='单段视频单价（元）')
    g.add_argument('--tts-unit', type=float, default=0.01, help='单次配音单价（元）')

    g = p.add_argument_group('真实单价来源（api.a7w.cn）')
    g.add_argument('--a7w-live', action='store_true',
                   help='现场联网拉真实单价：GET /api/v1/pricing + GET /api/v1/apps/<app>')
    g.add_argument('--price-file', metavar='JSON',
                   help='读取 `run.py pricing --out` 生成的单价快照（离线复算，推荐）')
    g.add_argument('--price-out', metavar='JSON',
                   help='把本次实际采用的单价快照写出来留档')
    g.add_argument('--key', help='--a7w-live 用的 API Key（默认 A7W_API_KEY 或 ~/.a7w/config.json）')
    g.add_argument('--a7w-image-resolution', default='1K',
                   choices=['1K', '2K', '4K'], help='出图档位（价格分档）')
    g.add_argument('--a7w-video-resolution', default='480P',
                   choices=['480P', '768P', '1080P', '2K', '4K'],
                   help='出片分辨率档位（按秒计费，档位差价很大）')
    g.add_argument('--clip-seconds', type=float, default=5.0,
                   help='单段视频平均时长，用于把「点/秒」折成「每段单价」')
    g.add_argument('--tts-chars', type=float, default=20.0,
                   help='每次配音的平均字数，用于把「点/千字」折成「每次单价」')

    return p


# ---------------------------------------------------------------------------
# 真实单价：快照读取 / 现场拉取 / 折算
# ---------------------------------------------------------------------------

def _load_run_module():
    """按路径加载同目录的 run.py（单价快照器），不依赖 sys.path 里有没有它。"""
    path = Path(__file__).resolve().parent / 'run.py'
    if not path.is_file():
        raise RuntimeError('同目录下找不到 run.py（单价快照器），无法取真实单价')
    spec = importlib.util.spec_from_file_location('sanjianke_drama_run', str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_price_snapshot(args):
    """返回 (快照 dict, 说明行 list)。失败时抛 RuntimeError，由 main 兜住。"""
    run = _load_run_module()
    if args.price_file:
        path = Path(args.price_file)
        if not path.is_file():
            raise RuntimeError('找不到单价快照：{}'.format(path))
        snap = json.loads(path.read_text(encoding='utf-8'))
        if not snap.get('derived'):
            snap['derived'] = run.derive_units(snap)     # 手改过的快照也能用
        return snap, ['单价快照：{}（拉取时间 {}）'.format(path, snap.get('fetched_at') or '未记录')]
    # --a7w-live
    key = run.a7w.load_key(args.key)
    snap = run.fetch_prices(key, quiet=True)
    snap['derived'] = run.derive_units(snap)
    return snap, ['单价快照：现拉 {}（{}）'.format(run.a7w.HOST, snap.get('fetched_at'))]


def units_from_snapshot(snap, args):
    """把快照折算成本脚本要的三个「元 / 次」单价，并返回来源说明。

    折算公式（都可复核）：
        出图  点/次  ÷ 100
        出片  点/秒 × clip-seconds ÷ 100
        配音  点/千字 × tts-chars ÷ 1000 ÷ 100
    """
    d = snap.get('derived') or {}
    got, lines = {}, []

    img = d.get('image') or {}
    by_res = img.get('by_resolution') or {}
    pts = by_res.get(args.a7w_image_resolution)
    if pts is None:
        pts = img.get('points_per_call')
    if pts:
        got['image'] = pts / POINTS_PER_YUAN
        lines.append('出图  nano_banana/submit {}  实测 {} 点/张 → {:.4f} 元/张'
                     .format(args.a7w_image_resolution, pts, got['image']))

    vid = d.get('video') or {}
    rates = vid.get('points_per_second') or {}
    rate = rates.get(args.a7w_video_resolution)
    if rate:
        pts = rate * args.clip_seconds
        got['video'] = pts / POINTS_PER_YUAN
        lines.append('出片  full_video/submit {}  {} 点/秒 × {} 秒 = {} 点/段 → {:.4f} 元/段'
                     .format(args.a7w_video_resolution, rate, args.clip_seconds,
                             round(pts, 3), got['video']))

    tts = d.get('tts') or {}
    per_k = tts.get('points_per_1k_chars')
    if per_k:
        pts = per_k * args.tts_chars / 1000.0
        got['tts'] = pts / POINTS_PER_YUAN
        lines.append('配音  voice_tts/tts  {} 点/千字 × {} 字 = {} 点/次 → {:.4f} 元/次'
                     .format(per_k, args.tts_chars, round(pts, 4), got['tts']))
    return got, lines


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # ---------- 真实单价：给了来源就用它，命令行显式给的单价仍然优先 ----------
    price_lines, price_warn = [], []
    real, snapshot = {}, None
    if args.a7w_live or args.price_file:
        try:
            snapshot, price_lines = load_price_snapshot(args)
            real, more = units_from_snapshot(snapshot, args)
            price_lines += more
            for k, label in (('image', '出图'), ('video', '出片'), ('tts', '配音')):
                if k not in real and getattr(args, k + '_unit') == parser.get_default(k + '_unit'):
                    price_warn.append(
                        '快照里没有{}的真实单价（{} 的 tenant 价常为 0，需 '
                        '`run.py pricing --probe {}` 实测），该项仍用示例值 {:.4f} 元。'
                        .format(label, {'image': 'nano_banana', 'video': 'full_video',
                                        'tts': 'voice_tts'}[k], k, getattr(args, k + '_unit')))
        except Exception as exc:                      # noqa: BLE001 - 只报错不崩
            sys.stderr.write('取真实单价失败：{}\n'.format(exc))
            return 3

    def pick(name):
        """命令行显式给的值 > 真实单价 > 示例默认值。"""
        val = getattr(args, name + '_unit')
        if val != parser.get_default(name + '_unit'):
            return val, '命令行指定'
        if name in real:
            return real[name], 'api.a7w.cn 真实单价'
        return val, '示例占位值'

    image_unit, image_src = pick('image')
    video_unit, video_src = pick('video')
    tts_unit, tts_src = pick('tts')

    # ---------- 基础换算 ----------
    base_bitrate_mbps = 4.0                       # 1080p 基准码率
    bitrate_mbps = base_bitrate_mbps * args.quality
    bitrate_mb_per_min = bitrate_mbps * 60 / 8    # Mbps -> MB/分钟

    total_minutes = args.episodes * args.minutes
    final_video_mb = total_minutes * bitrate_mb_per_min
    generated_video_mb = final_video_mb * args.shoot_ratio

    image_count = args.episodes * args.gen_image
    image_mb = image_count * 2.0                  # 每张约 2 MB
    audio_mb = total_minutes * 1.0                # 每分钟约 1 MB
    intermediate_mb = (generated_video_mb + image_mb) * args.intermediate_ratio

    peak_mb = (final_video_mb + generated_video_mb + image_mb
               + audio_mb + intermediate_mb)

    lifecycle_factor = min(1.0, args.lifecycle_days / 30.0)
    retained_mb = final_video_mb + (
        (generated_video_mb + image_mb + audio_mb + intermediate_mb)
        * lifecycle_factor)

    # ---------- 带宽 ----------
    # 只有已发布的成片会被反复回源；中间素材与废片不对外分发
    egress_gb = (final_video_mb * args.preview_count) / 1024

    # ---------- 生成成本 ----------
    image_cost = image_count * image_unit
    video_count = args.episodes * args.gen_video
    video_cost = video_count * video_unit
    tts_count = args.episodes * args.gen_tts
    tts_cost = tts_count * tts_unit
    gen_total = image_cost + video_cost + tts_cost

    # ---------- 平台成本 ----------
    storage_monthly = (retained_mb / 1024) * args.storage_per_gb
    egress_cost = egress_gb * args.egress_per_gb

    grand_total = gen_total + storage_monthly + egress_cost
    per_episode = grand_total / args.episodes if args.episodes else 0.0
    per_minute = grand_total / total_minutes if total_minutes else 0.0

    # ---------- 合理性校验 ----------
    warnings = []
    if args.episodes < 1:
        warnings.append('集数小于 1，结果无意义。请传 --episodes 至少为 1。')
    if args.minutes <= 0:
        warnings.append('单集时长非正数，结果无意义。请传 --minutes 大于 0。')
    if args.shoot_ratio < 1.0:
        warnings.append('拍摄比 {:.2f} 小于 1.0，意味着生成量少于采用量，'
                        '不符合实际。'.format(args.shoot_ratio))
    if args.lifecycle_days < 1:
        warnings.append('生命周期小于 1 天，中间素材将全部即时清除，'
                        '请确认是否符合预期。')
    if args.preview_count > 8:
        warnings.append('每集预览次数超过 8 次，回源流量将显著高于成片体积，'
                        '请确认是否符合预期。')
    if args.gen_video > 0 and video_unit <= 0:
        warnings.append('视频单价为 0，生成成本将被低估，请填入真实单价。')
    if args.clip_seconds <= 0 and video_src == 'api.a7w.cn 真实单价':
        warnings.append('--clip-seconds 非正数，按秒计费的视频单价折算为 0。')
    if args.tts_chars <= 0 and tts_src == 'api.a7w.cn 真实单价':
        warnings.append('--tts-chars 非正数，按千字计费的配音单价折算为 0。')
    warnings += price_warn

    # ---------- 留档 ----------
    if args.price_out:
        kept = snapshot or {'source': None, 'note': '本次用的是示例单价，未取真实价'}
        kept = dict(kept)
        kept['applied'] = {
            'episodes': args.episodes, 'minutes': args.minutes,
            'image_unit_yuan': image_unit, 'image_src': image_src,
            'video_unit_yuan': video_unit, 'video_src': video_src,
            'tts_unit_yuan': tts_unit, 'tts_src': tts_src,
            'a7w_image_resolution': args.a7w_image_resolution,
            'a7w_video_resolution': args.a7w_video_resolution,
            'clip_seconds': args.clip_seconds, 'tts_chars': args.tts_chars,
        }
        try:
            Path(args.price_out).write_text(
                json.dumps(kept, ensure_ascii=False, indent=1), encoding='utf-8')
            price_lines.append('单价快照已留档：{}'.format(args.price_out))
        except OSError as exc:
            price_warn.append('写 --price-out 失败：{}'.format(exc))

    # ---------- 输出 ----------
    out = []
    w = out.append
    w('')
    w('========================================')
    w(' AI 短剧创作台 · 成本量级测算')
    w('========================================')
    w('')
    w('产出规模 : {} 集 / 每集 {} 分钟 / 共 {} 分钟'.format(
        args.episodes, args.minutes, total_minutes))
    w('画质系数 : {}  →  约 {:.1f} Mbps'.format(args.quality, bitrate_mbps))
    w('拍摄比   : {}  （含废片）'.format(args.shoot_ratio))
    w('')

    w('---- 采用的生成单价 ----')
    if price_lines:
        for line in price_lines:
            w('  {}'.format(line))
        w('  口径：1 元 = 100 点（1 点 = 0.01 元）；平台按点数计费，失败全额退回')
    else:
        w('  未指定真实单价来源，下面三项均为**示例占位值**：')
    w('  出图 {:.4f} 元/张   ← {}'.format(image_unit, image_src))
    w('  出片 {:.4f} 元/段   ← {}'.format(video_unit, video_src))
    w('  配音 {:.4f} 元/次   ← {}'.format(tts_unit, tts_src))
    w('')

    w('---- 素材体积 ----')
    w('成片        : {:>10,.1f} MB'.format(final_video_mb))
    w('生成片段    : {:>10,.1f} MB'.format(generated_video_mb))
    w('图片 ({:>4.0f} 张) : {:>10,.1f} MB'.format(image_count, image_mb))
    w('音频        : {:>10,.1f} MB'.format(audio_mb))
    w('中间素材    : {:>10,.1f} MB'.format(intermediate_mb))
    w('峰值占用    : {:>10,.2f} GB'.format(peak_mb / 1024))
    w('留存占用    : {:>10,.2f} GB   （生命周期 {} 天）'.format(
        retained_mb / 1024, args.lifecycle_days))
    w('')

    w('---- 平台成本 ----')
    w('对象存储    : {:>10,.2f} 元 / 月'.format(storage_monthly))
    w('回源带宽    : {:>10,.1f} GB  →  {:>8,.2f} 元'.format(
        egress_gb, egress_cost))
    w('平台小计    : {:>10,.2f} 元'.format(storage_monthly + egress_cost))
    w('')

    w('---- 生成成本 ----')
    w('图片 {:>4.0f} 次 : {:>10,.2f} 元'.format(image_count, image_cost))
    w('视频 {:>4.0f} 次 : {:>10,.2f} 元'.format(video_count, video_cost))
    w('配音 {:>4.0f} 次 : {:>10,.2f} 元'.format(tts_count, tts_cost))
    w('生成小计    : {:>10,.2f} 元'.format(gen_total))
    w('')

    w('---- 结论 ----')
    w('合计        : {:>10,.2f} 元'.format(grand_total))
    w('单集成本    : {:>10,.2f} 元'.format(per_episode))
    w('单分钟成本  : {:>10,.2f} 元'.format(per_minute))

    if grand_total > 0:
        w('')
        w('---- 结构占比 ----')
        w('视频生成    : {:>6.1f}%'.format(video_cost / grand_total * 100))
        w('图片生成    : {:>6.1f}%'.format(image_cost / grand_total * 100))
        w('配音生成    : {:>6.1f}%'.format(tts_cost / grand_total * 100))
        w('对象存储    : {:>6.1f}%'.format(storage_monthly / grand_total * 100))
        w('回源带宽    : {:>6.1f}%'.format(egress_cost / grand_total * 100))

    w('')
    w('----------------------------------------')
    if price_lines:
        w(' 生成单价来自 api.a7w.cn 实测 / 现拉，')
        w(' 平台调价后请重跑 --a7w-live 或重拉快照。')
    else:
        w(' 提示：以上单价均为占位示例值，请替换为')
        w(' 当期真实报价后再采信结论。')
    w(' 对象存储与回源带宽仍是示例价，未联网核对。')
    w(' 本测算未计入重试、失败重跑与人工返工消耗。')
    w('----------------------------------------')

    if warnings:
        w('')
        w('---- 参数提醒 ----')
        for item in warnings:
            w('  · {}'.format(item))
    w('')

    sys.stdout.write('\n'.join(out))
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(main())
