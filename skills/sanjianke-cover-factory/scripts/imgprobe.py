#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图片文件探针 · 零依赖（只用标准库 struct）。

为什么单独一个模块
    `scripts/a7w.py` 是**所有 Skill 包共用的零依赖客户端**，
    我们靠「包内副本 SHA256 == 规范版」来批量校验 60+ 个包的客户端有没有被改坏。
    所以任何包都**不许**为了自己的业务往 a7w.py 里加东西——需要额外能力就放独立模块，
    客户端保持逐字节一致。

这个模块解决的是什么问题
    配图工厂的比例闸门要判「请求 3:4，拿到的图真是 3:4 吗」。
    唯一可信的凭据是**图片文件本身的像素**，不是接口返回里自报的 aspect_ratio——
    我们吃过「只信自报值」的亏（标题工坊上一版因为只信模型自报的 formula 字段，
    闸门成了假绿）。而 PIL 不是标准库、不许依赖，
    所以这里直接读文件头把宽高还原出来。

只读
    本模块**只读**图片、不写图片。裁剪（--snap）是写操作，留在调用方 run.py 里。

用法
    image_size("a.png")     -> (1024, 768, 'png')
    parse_ratio("3:4")      -> 0.75
    ratio_label(864, 1152)  -> '3:4'
"""

import struct
from math import gcd
from pathlib import Path

__all__ = ["image_size", "parse_ratio", "ratio_label", "image_ratio"]


# ---------------------------------------------------------------------------
# 文件头解析
# ---------------------------------------------------------------------------

def _png_size(head):
    """PNG：IHDR 紧跟 8 字节签名 + 4 字节长度 + 4 字节类型，宽高是大端 32 位。"""
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return [w, h]


def _jpeg_size(path):
    """JPEG：扫段找 SOF，宽高在前两个字节之后。

    必须扫段而不是取固定偏移——EXIF/缩略图会让 SOF 的位置不固定。
    """
    data = Path(path).read_bytes()
    i, n = 2, len(data)
    while i < n - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0..SOF15，排除 DHT(C4) / JPG(C8) / DAC(CC)
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return [w, h]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        if seg < 2:
            return None
        i += 2 + seg
    return None


def _gif_size(head):
    if head[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    w, h = struct.unpack("<HH", head[6:10])
    return [w, h]


def _webp_size(path):
    """WebP 三种子格式：VP8X（扩展）/ VP8（有损）/ VP8L（无损）。"""
    data = Path(path).read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        # RIFF(4) size(4) WEBP(4) VP8X(4) chunk_size(4) flags(1) reserved(3)
        # → 画布宽高是 24 位小端，从第 24 字节开始
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return [w, h]
    if chunk == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return [w & 0x3FFF, h & 0x3FFF]
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return [(bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1]
    return None


def image_size(path):
    """读图片真实像素，返回 (宽, 高, 格式)。

    支持 png / jpeg / gif / webp —— 出图结果实测是 png。
    认不出来时返回 (None, None, '?')，**不猜、不报错**：
    调用方据此判「读不出真实像素」并把这条判为不合格。
    """
    p = Path(path)
    if not p.is_file():
        return None, None, "?"
    head = p.open("rb").read(33)
    if not head:
        return None, None, "?"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        wh = _png_size(head)
        return (wh[0], wh[1], "png") if wh else (None, None, "png?")
    if head[:3] == b"\xff\xd8\xff":
        wh = _jpeg_size(p)
        return (wh[0], wh[1], "jpeg") if wh else (None, None, "jpeg?")
    if head[:6] in (b"GIF87a", b"GIF89a"):
        wh = _gif_size(head)
        return (wh[0], wh[1], "gif") if wh else (None, None, "gif?")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        wh = _webp_size(p)
        return (wh[0], wh[1], "webp") if wh else (None, None, "webp?")
    return None, None, "?"


# ---------------------------------------------------------------------------
# 比例换算
# ---------------------------------------------------------------------------

def parse_ratio(text):
    """'3:4' / '3/4' / '3x4' / '3×4' → 0.75。解析不了返回 None。"""
    import re
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[:/x×]\s*(\d+(?:\.\d+)?)\s*$", str(text or ""))
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if b == 0:
        return None
    return a / b


def ratio_label(w, h):
    """把像素还原成最简比例标签：864x1152 → '3:4'；1152x896 → '9:7'。"""
    if not w or not h:
        return "?"
    g = gcd(int(w), int(h))
    return "%d:%d" % (w // g, h // g)


def image_ratio(path):
    """一步到位：给文件返回 (宽, 高, 数值比例, 比例标签, 格式)。

    读不出像素时宽高与比例为 None，标签为 '?'。
    """
    w, h, fmt = image_size(path)
    if not w or not h:
        return w, h, None, "?", fmt
    return w, h, w / float(h), ratio_label(w, h), fmt


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        w, h, r, label, fmt = image_ratio(f)
        print("%s  %sx%s  %s  ratio=%s  (%s)" % (f, w, h, label, r, fmt))
