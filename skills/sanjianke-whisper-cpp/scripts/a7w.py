#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a7w 算力网关 · 零依赖客户端（Skill 内置版）。

设计约束
    · 只用 Python 标准库（urllib / json / mimetypes），**不装任何第三方包**
    · **不内嵌任何密钥**：Key 由使用者自己提供
    · Key 读取顺序：--key 参数 → 环境变量 A7W_API_KEY → ~/.a7w/config.json

为什么要有这个文件
    上游开源工具往往要装 CUDA、下模型、配环境，用户复制 Skill 后用不起来。
    这里把「模型与算力」统一换成走 api.a7w.cn：用户填一个 Key 就能跑。

常用
    a7w.upload(app, api, fields, file_field, file_path)   # 带本地文件的多段上传
    a7w.call(app, api, body)                              # 纯 JSON 调用（自动轮询异步任务）
    a7w.save(url, path)                                   # 把结果 URL 落盘
"""

import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HOST = os.environ.get("A7W_HOST", "https://api.a7w.cn").rstrip("/")
CONFIG = Path.home() / ".a7w" / "config.json"
TERMINAL = ("completed", "failed", "error", "cancelled")
POLL_INTERVAL = 5
POLL_TIMEOUT = 1800
RETRIES = 4          # 网络类错误的退避重试次数（长异步任务轮询会被网关重置连接）
QUIET = False        # 设 True 可关掉重试提示


class A7wError(RuntimeError):
    """带用户可读提示的调用错误。"""


def load_key(explicit=None):
    key = explicit or os.environ.get("A7W_API_KEY")
    if key:
        return key.strip()
    if CONFIG.is_file():
        try:
            return (json.loads(CONFIG.read_text(encoding="utf-8")).get("key") or "").strip()
        except (OSError, ValueError):
            pass
    raise A7wError(
        "没有找到 API Key。三种方式任选一种：\n"
        "  1) 命令行加 --key sk-xxxx\n"
        "  2) 设置环境变量 A7W_API_KEY\n"
        "  3) 到 https://api.a7w.cn/ 注册领取 Key（新用户有赠送点数）")


def _request(method, url, key, body=None, raw=None, content_type=None, timeout=180):
    """发一次请求。

    **为什么要重试**：视频/长异步任务的轮询会被网关重置连接
    （`WinError 10054 远程主机强迫关闭了一个现有的连接`），视频类任务几乎必踩。
    如果不重试，一次抖动就会让已经预冻结点数的付费任务白丢。
    这里对网络类错误做退避重试，对 5xx 也重试；4xx 是业务错误，不重试。
    """
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    data = None
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_exc = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            if exc.code in (502, 503, 504) and attempt < RETRIES - 1:
                last_exc = exc
                time.sleep(2 * (attempt + 1))
                continue
            try:
                payload = json.loads(text)
            except ValueError:
                payload = {"msg": text[:300]}
            code = payload.get("code")
            msg = payload.get("msg") or payload.get("error") or text[:200]
            if exc.code == 401:
                raise A7wError("鉴权失败（401）：Key 无效或已过期。" + str(msg))
            if exc.code == 402 or code == 402:
                raise A7wError("点数不足（402）：{}  请到 https://api.a7w.cn/ 充值后重试。".format(msg))
            raise A7wError("请求失败（HTTP {}）：{}".format(exc.code, msg))
        except (urllib.error.URLError, ConnectionResetError, TimeoutError,
                OSError) as exc:
            last_exc = exc
            if attempt < RETRIES - 1:
                if not QUIET:
                    sys.stderr.write("网络抖动（{}），{:.0f}s 后重试 {}/{}…\n".format(
                        getattr(exc, "reason", exc), 2 * (attempt + 1),
                        attempt + 1, RETRIES - 1))
                time.sleep(2 * (attempt + 1))
                continue
    raise A7wError("网络错误：{}（已重试 {} 次；确认能访问 {}）".format(
        getattr(last_exc, "reason", last_exc), RETRIES, url))


def _unwrap(payload):
    code = payload.get("code")
    ok = code in (1, 200, "1", "200") or code is None
    if not ok:
        raise A7wError("接口返回失败：{}".format(payload.get("msg") or payload))
    return payload.get("data")


def _multipart(fields, file_field, file_path):
    """手工拼 multipart/form-data（不依赖 requests）。"""
    boundary = "----a7w" + uuid.uuid4().hex
    buf = bytearray()

    def part(name, value, filename=None, ctype=None):
        buf.extend(("--" + boundary + "\r\n").encode())
        if filename:
            buf.extend(('Content-Disposition: form-data; name="{}"; filename="{}"\r\n'
                        .format(name, filename)).encode("utf-8"))
        else:
            buf.extend(('Content-Disposition: form-data; name="{}"\r\n'.format(name)).encode())
        buf.extend(("Content-Type: {}\r\n\r\n".format(ctype or "text/plain")).encode())
        buf.extend(value if isinstance(value, bytes) else str(value).encode("utf-8"))
        buf.extend(b"\r\n")

    for k, v in (fields or {}).items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        part(k, v)
    if file_path:
        p = Path(file_path)
        if not p.is_file():
            raise A7wError("找不到文件：{}".format(p))
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        part(file_field, p.read_bytes(), filename=p.name, ctype=ctype)
    buf.extend(("--" + boundary + "--\r\n").encode())
    return bytes(buf), "multipart/form-data; boundary=" + boundary


def call(app, api, body=None, key=None, wait=True, timeout=POLL_TIMEOUT, quiet=False):
    """调用一个 app 的接口。异步任务自动轮询到结束。"""
    key = load_key(key)
    url = "{}/api/v1/apps/{}/{}".format(HOST, app, api)
    data = _unwrap(_request("POST", url, key, body=body))
    task_id = (data or {}).get("task_id")
    if not task_id:
        return data                      # 同步接口，直接给结果
    if not wait:
        return {"task_id": task_id, "status": "submitted"}
    if not quiet:
        sys.stderr.write("task_id={} 已提交，等待完成…\n".format(task_id))
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        t = _unwrap(_request("GET", "{}/api/v1/tasks/{}".format(HOST, task_id), key))
        status = (t or {}).get("status")
        if status != last and not quiet:
            sys.stderr.write("  状态：{}\n".format(status))
            last = status
        if status in TERMINAL:
            if status != "completed":
                raise A7wError("任务未成功：{}  {}".format(status, (t or {}).get("error") or ""))
            return {"task_id": task_id, "status": status,
                    "result": (t or {}).get("result"),
                    "usage": (t or {}).get("usage")}
    raise A7wError("轮询超时。任务可能还在跑，用 task_id={} 稍后查询。".format(task_id))


def upload(app, api, fields=None, file_field="file", file_path=None,
           key=None, wait=True, timeout=POLL_TIMEOUT, quiet=False):
    """带本地文件的多段上传。其余同 call()。"""
    key = load_key(key)
    raw, ctype = _multipart(fields, file_field, file_path)
    url = "{}/api/v1/apps/{}/{}".format(HOST, app, api)
    data = _unwrap(_request("POST", url, key, raw=raw, content_type=ctype))
    task_id = (data or {}).get("task_id")
    if not task_id or not wait:
        return data if not task_id else {"task_id": task_id, "status": "submitted"}
    return call(app, api, None, key=key, wait=True, timeout=timeout, quiet=quiet) \
        if False else _poll(key, task_id, timeout, quiet)


def _poll(key, task_id, timeout, quiet):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        t = _unwrap(_request("GET", "{}/api/v1/tasks/{}".format(HOST, task_id), key))
        status = (t or {}).get("status")
        if status != last and not quiet:
            sys.stderr.write("  状态：{}\n".format(status))
            last = status
        if status in TERMINAL:
            if status != "completed":
                raise A7wError("任务未成功：{}  {}".format(status, (t or {}).get("error") or ""))
            return {"task_id": task_id, "status": status,
                    "result": (t or {}).get("result"), "usage": (t or {}).get("usage")}
    raise A7wError("轮询超时。用 task_id={} 稍后查询。".format(task_id))


def save(url, path):
    """把结果 URL 下载到本地。"""
    if not url:
        raise A7wError("没有可下载的地址")
    req = urllib.request.Request(url, headers={"User-Agent": "a7w-skill/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    Path(path).write_bytes(data)
    return path


def dig(obj, *keys):
    """在嵌套 dict/list 里按顺序找第一个非空值——上游返回结构偶有差异。"""
    cur = obj
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
        if cur is None:
            return None
    return cur
