---
name: sanjianke-garment-optimize
slug: sanjianke-garment-optimize
displayName: 服装优化 13.5点一次
description: "**服装优化，一次 13.5 点（0.135 元）。** 走 api.a7w.cn，按次调用、不用开机器。给素材（图片/视频/音频）和提示词，直接出成品。本包把它的 2 个参数翻成了中文对照表，常用入口只有 --image / --video / --audio / --text 四个。遇到问题可加技术微信 9872659。"
version: 1.0.2
summary: "服装优化 是 api.a7w.cn 上 69 个按次调用应用之一，**每次 13.5 点（0.135 元）**。它的原始参数名是节点 id（n255_image, n2_denoise 这种），本包翻成了人话：`--params` 打全表（参数名 / 含义 / 类型 / 必填 / 默认），`--image` / `--video` / `--audio` / `--text` 按类型自动匹配，`--set 名=值` 兜底任意参数。素材自动上传换 `asset://`，提交与轮询都封好了。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 图片
  - garment-optimize
  - api.a7w.cn
---

# 服装优化 13.5点一次

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**服装优化，一次 13.5 点 = 0.135 元。**

## 价目

| 项 | 值 |
|---|---|
| 类型 | 图片 |
| **每次** | **13.5 点（0.135 元）** |
| 参数 | 2 个（必填 2 个）|
| 端点 | `POST /api/v1/gpu/apps/wf_efb136a5bba015ced836/run` |

## 三步上手

```bash
# 1) 自检（免费）
python3 scripts/run.py info

# 2) 看参数表（免费）
python3 scripts/run.py params

# 3) 跑一次
python3 scripts/run.py run --image 你的图.png --yes
```

## 参数表（2 个）

| 参数名 | 含义 | 类型 | 必填 |
|---|---|---|---|
| `n255_image` | image | image_input | 是 |
| `n2_denoise` | denoise | float | 是 |

## 人话入口

| 参数 | 对应什么 |
|---|---|
| `--image 图.png` | 自动匹配第一个必填的图片参数（本地文件会自动上传）|
| `--video 视频.mp4` | 视频参数 |
| `--audio 音频.mp3` | 音频参数 |
| `--text "…"` | 文本 / 提示词 |
| `--set 名=值` | 兜底，任意参数（可重复）|

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `info` | 免费 | 应用信息 + 自检 |
| `params` | 免费 | 参数表（中文含义对照）|
| `run` | **13.5 点/次** | 提交任务（要 `--yes`）|

## 退出码

`0` 成功 · `2` 用法错 · `4` 需 `--yes` · `5` 预算不足（**不发请求**）· `6` 调用失败 ·
`7` 轮询超时（用 run_order_id 再查，**别重提**）· `1` 内部错 · `130` 中断

## 免责

- 批量跑请用 `--batch` 清单 + `--budget` 守卫。
- 生成内容的合规责任在使用者。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

