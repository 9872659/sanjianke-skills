# GPT Image 2.6 六分钱出图工作台
**6 点一张图（¥0.06）。** 走 [api.a7w.cn](https://api.a7w.cn/) 的 `gpt-image-2.6`，OpenAI Images API 兼容、**同步**出图、零依赖。

实测：`1024×1024` 一张图 **43.6 秒**，产出 **1.6 MB PNG**，扣 **6 点**。

---

## 三个真会花错钱的坑，都做成了默认动作

### 坑一：端点少写一个 `/api`，你的模型被静默忽略

```
✅ POST https://api.a7w.cn/api/v1/images/generations    ← 认 model
❌ POST https://api.a7w.cn/v1/images/generations        ← 也出图，但忽略 model
```

**实测**：往错误的那条路传 `model: "gpt-image-2.6"`、甚至传一个根本不存在的模型名，
**都会路由到网关默认应用 `nano_banana`（72 点/次）**，而且**不报错**。你以为用上了 2.6，其实没有。

所以 `doctor` 专门探这条：发 `{"model":"gpt-image-2.6","prompt":""}` ——
文档规定缺 prompt 返回 **422**「String should have at least 1 character」，**零扣费**。

```
✓ 文生图端点可用（422 即正确）   HTTP 422 prompt: String should have at least 1 characte
```

### 坑二：返回默认是 `b64_json`，不是 URL

直接找 `["data"][0]["url"]` 会拿到空。本包两种都处理，自动解码落盘成文件。

```bash
# 想要 URL 就加 --want-url（有效期约 3 小时）
python3 scripts/run.py gen --prompt "..." --want-url --yes
```

### 坑三：不知道一张几毛钱，不敢试

**6 点/张 = ¥0.06。** 4 张才 0.24 元。`cost` 先算，`--budget` 兜底。

---

## 价格

| 张数 | 价格 |
|---|---|
| 1 张 | **6 点（¥0.06）** |
| 2 张 | 12 点（¥0.12） |
| 3 张 | 18 点（¥0.18） |
| 4 张 | 24 点（¥0.24） |

- **按张计费**，与尺寸、质量、输出格式**都无关**
- 按 `data` 里**实际返回的张数**计费（`n=2` 只回 1 张就收 1 张）
- 参数错误、请求失败、没返回图片 → **不扣费**
- 客户端中途断开 → 仍按请求张数计费

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --n 4

# 4) 出图
python3 scripts/run.py gen --prompt "一只橘猫坐在窗台上晒太阳，写实风格" \
    --size 1024x1024 --yes
```

---

## 用法示例

```bash
# 一次 4 张
python3 scripts/run.py gen --prompt "四种风格的猫" --n 4 --budget 30 --yes

# 图生图：把帽子戴到猫头上
python3 scripts/run.py edit --prompt "把第二张图里的帽子戴到第一张图的猫头上" \
    --image cat.png --image hat.png --yes

# GIF 动图（按一张计费）
python3 scripts/run.py gen --prompt "一只橘猫在挥手" --gif --yes

# 透明背景（只能配 png / webp）
python3 scripts/run.py gen --prompt "一个图标" --background transparent --yes

# 2K
python3 scripts/run.py gen --prompt "风景" --size 2k --yes

# 只看请求不花钱
python3 scripts/run.py gen --prompt "一只橘猫" --dry-run
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` | 必填 | 提示词 |
| `--n` | 1 | **1–4**，超范围直接拒 |
| `--size` | `auto` | `auto` / `1k` / `2k` / `4k` / `宽x高` |
| `--output-format` | `png` | `png` / `jpeg` / `webp` / `gif` |
| `--gif` | — | 等价于 `--output-format gif` |
| `--background` | `auto` | `auto` / `transparent` / `opaque` |
| `--quality` | `auto` | `auto`/`low`/`medium`/`high`/`xhigh`/`max`，**不影响价格** |
| `--compression` | — | 0–100，只对 jpeg/webp 生效 |
| `--want-url` | — | 返回 url 而不是 b64_json |
| `--outdir` | `.` | 图片保存目录 |
| `--prefix` | `gptimg` | 文件名前缀 |
| `--budget` | 500 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实扣费 |

### 自定义尺寸的四条硬约束（不合规 → 400，不扣费）

- 宽高都是 **16 的倍数**
- 长边 / 短边 **不超过 3:1**
- 单边 **不超过 3840**
- 总像素 **655,360 – 8,294,400**

**本包在本地就校验这四条**，不合格直接退 `2`，一个请求都不发。

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `models` | 免费 | 列出在架图片模型 |
| `cost` | 免费 | 先算钱（6 点/张） |
| `doctor` | 免费 | 自检 Key / 模型 / 端点 |
| `gen` | **6 点/张** | 文生图（要 `--yes`） |
| `edit` | **6 点/张** | 图生图（multipart，要 `--yes`） |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺 `--prompt`、尺寸不合规、`n` 越界、选项缩写） |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 响应里没有图 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "mode": "gen", "model": "gpt-image-2.6", "elapsed": 43.6,
 "requested": 1, "returned": 1, "source": "b64_json",
 "files": ["./gptimg-01.png"], "urls": [], "billedPoints": 6,
 "size": "1024x1024", "output_format": "png"}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-gpt-image/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（文档原文 + 实测）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 实测记录

```
2026-11-07  gpt-image-2.6  1024x1024  n=1
  出图   43.6 秒
  返回   1 张（b64_json）
  产物   1,639,194 字节 PNG（1024×1024）
  扣费   6 点（¥0.06）
```

---

## 已知限制

1. **图片链接有效期约 3 小时**，请及时下载；链接请**原样使用**（追加查询参数会 404）
2. **`quality` 只是提示**，不影响价格，也别指望它切换画质档位
3. **不支持 SVG**（传 `output_format=svg` 返回 400）
4. **`transparent` 不能配 jpeg/gif**（400）；透明不保证每次成功，以响应为准
5. **GIF 的尺寸和帧数由模型决定**（约 8–16 帧，边长 170–900），`size` 对 GIF 不生效
6. **流式（`stream: true`）本包未实现** —— 文档支持，但目前用不到

---

## 免责

- 生成内容的合规责任在使用者：不得用于伪造他人身份、侵权素材或违法用途。
- 真实扣费以响应里**实际返回的张数**为准，`cost` 给的是预估。

---

## 许可证

MIT，见 `LICENSE.md`。

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
