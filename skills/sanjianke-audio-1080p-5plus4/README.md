# 【1080P】5+4返璞归真版 13.5点一次

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**【1080P】5+4返璞归真版，一次 13.5 点 = 0.135 元。**

## 价目

| 项 | 值 |
|---|---|
| 类型 | 音频 |
| **每次** | **13.5 点（0.135 元）** |
| 参数 | 12 个（必填 4 个）|
| 端点 | `POST /api/v1/gpu/apps/wf_ee4fd4f17551c5357ce9/run` |

## 三步上手

```bash
# 1) 自检（免费）
python3 scripts/run.py info

# 2) 看参数表（免费）
python3 scripts/run.py params

# 3) 跑一次
python3 scripts/run.py run --image 你的图.png --yes
```

## 参数表（12 个）

| 参数名 | 含义 | 类型 | 必填 |
|---|---|---|---|
| `node_282_aspect_ratio` | 宽高比【竖屏格式写：9:16 (Portrait Widescreen)】 | string | 是 |
| `node_284_Number` | 时间长【4-15S】 | string | 是 |
| `node_283_text` | 提示词 | string | 是 |
| `node_269_image` | image | image_input | 是 |
| `node_270_image` | image | image_input | - |
| `node_271_image` | image | image_input | - |
| `node_272_image` | image | image_input | - |
| `node_273_image` | image | image_input | - |
| `node_274_image` | image | image_input | - |
| `node_248_audio` | audio | audio_input | - |
| `node_249_audio` | audio | audio_input | - |
| `node_250_audio` | audio | audio_input | - |

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

## 许可证

MIT，见 `LICENSE.md`。

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
