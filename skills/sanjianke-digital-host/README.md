# 数字人口播台 · 一张图 + 一段话 → 一个人开口

**不用出镜、不用录音、不用剪辑。** 一张照片 + 一段话，三分钟一条口播视频。

三个数字人应用，一条命令一个入口：

| 你要的效果 | 命令 | 应用 | 你给什么 | 价格 |
|---|---|---|---|---|
| 一张图 + 一段文案 → 人开口念 | `talk` | `pic_lipsync` | 图 + 参考音色 + 文案 | **15 点/秒** |
| 一张图 + 一段录音 → 人对口型 | `drive` | `image_human` | 图 + 音频 + 秒数 + 档位 | **10 / 15 / 30 / 60 点/秒** |
| 已有视频 + 新配音 → 重新对口型 | `dub` | `lipsync` | 视频 + 音频 + 秒数 | **上游实际 ×3** |

三者一句话分清楚：**文案驱动最轻（talk），全驱动最稳可调档（drive），已有视频换口型最省（dub）。**

---

## 三个真会花错钱的坑，都做成了默认动作

### 坑一：`image_human` 不传 `mode`，出片和账单对不上

| 来源 | 默认档 |
|---|---|
| `GET /api/v1/apps/image_human` 的 `default_params.mode` | `standard` |
| `GET /api/v1/pricing` 的 `defaultModel` + note「缺省 mode=fast（=10）」 | `fast` |

不传 `mode` 时：**按 standard 出片、按 fast 收钱**（15 vs 10 点/秒）。
所以本包的 `drive --mode` **是必填参数**，宁可报错也不让档位和账单对不上。

```bash
python3 scripts/run.py drive --image face.png --audio speech.mp3 \
    --mode standard --duration 30 --yes
```

### 坑二：`pic_lipsync` 的档位参数真名是 `quality`

`mode` 只负责切 `audio` / `text`；真正的档位是 `quality`（`standard` / `fast` / `max`）。
按 `mode=max` 传的人不少，上游会安静地按 `standard` 收费。

### 坑三：`text` 模式省掉录音，但省不掉「参考音色」

`mode=text` 时 `audio_url` 仍然必填，它代表**用谁的声音念**：

```json
{"code":0,"msg":"text 模式请提供 audio_url 作为参考音色","data":null}
```

给一段 3–10 秒、单人、无背景音乐的清晰人声即可。

---

## 价格（2026-10-10 站主批准）

| 做法 | 档位 | 价格 | 30 秒 |
|---|---|---|---|
| `talk` | 标准（默认） | **15 点/秒** | 450 点 = ¥4.50 |
| `drive` | `fast` 快速 | **10 点/秒** | 300 点 = ¥3.00 |
| `drive` | `standard` 标准 | **15 点/秒** | 450 点 = ¥4.50 |
| `drive` | `2k` | **30 点/秒** | 900 点 = ¥9.00 |
| `drive` | `4k` | **60 点/秒** | 1800 点 = ¥18.00 |
| `dub` | `xiaojiayu1.0` | 2.7 点/秒 | 81 点 = ¥0.81 |
| `dub` | `xiaojiayu2.0` / `3.0` | 13.5 点/秒 | 405 点 = ¥4.05 |

**1 元 = 100 点。** `talk` 按公开文档的 50 点保底下限预估。

- `talk`：上游实扣 3 点/秒 ×5（`/api/v1/apps/pic_lipsync/submit`，markup 400%，minPoints 50）
- `drive`：上游成本 2 / 3 / 6 / 12 点/秒 ×5，四档锁死
- `dub`：上游实际点数 ×3（`xiaojiayu1.0` 上游 0.9 点/秒、`2.0/3.0` 上游 4.5 点/秒，30 秒 ×0.9 = 27 点正是历史文档里那个「27 点/次」）

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 自检（免费，四个只读 GET，一个 submit 都不发）
python3 scripts/run.py doctor

# 3) 先算钱（免费）
python3 scripts/run.py cost --way talk --content "大家好，今天聊一个很多人关心的问题…"
python3 scripts/run.py cost --way drive --mode 4k --duration 30     # 1800 点
python3 scripts/run.py cost --way dub --seconds 30                  # 81 点

# 4) 出片
python3 scripts/run.py talk --image face.png --voice-ref voice.mp3 \
    --content "大家好，今天聊一个很多人关心的问题…" --upload --save --yes
```

---

## 用法示例

```bash
# 最轻：图 + 文案 + 参考音色（本地文件直接上传，上传不计费）
python3 scripts/run.py talk --image https://cdn/face.jpg --voice-ref https://cdn/voice.mp3 \
    --content "大家好，今天聊一个很多人关心的问题。" --quality standard --yes

# 全驱动：四档任选，指定秒数把价格锁死
python3 scripts/run.py drive --image https://cdn/face.jpg --audio https://cdn/speech.mp3 \
    --mode 2k --duration 45 --yes

# 已有视频换口型
python3 scripts/run.py dub --video https://cdn/old.mp4 --audio https://cdn/new.mp3 \
    --seconds 30 --model xiaojiayu1.0 --yes

# 只看请求不花钱
python3 scripts/run.py talk --image face.png --voice-ref voice.mp3 --content "…" --dry-run

# 查任务 + 下载
python3 scripts/run.py status --task-id task_xxx --save
python3 scripts/run.py log
```

---

## 参数

| 参数 | 适用 | 说明 |
|---|---|---|
| `--image` | 全部 | 人物图片：公网 URL，或本地文件 + `--upload`（对应 `image_url` / `file_url`）|
| `--voice-ref` | `talk` | 参考音色，3–10 秒单人清晰人声（text 模式必填，对应 `audio_url`）|
| `--audio` | `drive` / `dub` | 驱动音频 / 新配音（对应 `ref_file_url` / `audio_url`）|
| `--video` | `dub` | 已有视频（对应 `video_url`）|
| `--content` | `talk` | 要念的文案（按 4.5 字/秒估时长）|
| `--quality` | `talk` | `standard`（默认）/ `fast` / `max` |
| `--mode` | `drive` | **必填**：`fast` / `standard` / `2k` / `4k` |
| `--duration` | `drive` | **必填**：输入音频真实秒数 |
| `--resolution` | `drive` | `2k` / `4k`，`mode` 的兼容别名 |
| `--model` | `talk` / `dub` | talk 固定 `super-lipsync-pro`；dub 三选一 |
| `--seconds` | `dub` | **必填**：音频或视频秒数，用来算钱 |
| `--fps` / `--video-params` | `dub` | 输出帧率 / 画面参数字典 |
| `--upload` | 全部 | 本地文件先传平台临时地址（**上传不计费**，24 小时有效）|
| `--save` / `--outdir` | 全部 | 完成后下载成片 / 保存目录 |
| `--no-wait` | 全部 | 只提交，不轮询 |
| `--timeout` / `--interval` | 全部 | 等待上限（默认 900 秒）/ 轮询间隔（默认 5 秒）|
| `--budget` | 全部 | 点数上限（**单位：点**，默认 500，1 元 = 100 点）|
| `--yes` | 付费命令 | 确认真实扣费 |
| `--dry-run` | 付费命令 | 只打印请求，不提交 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 三种做法对照（参数 + 价格）|
| `cost` | 免费 | 三路各自算钱 |
| `doctor` | 免费 | 六项自检（四个只读 GET）|
| `talk` | **15 点/秒** | 文案驱动口播 |
| `drive` | **10/15/30/60 点/秒** | 全驱动数字人 |
| `dub` | **上游 ×3** | 已有视频对口型 |
| `status` | 免费 | 查任务、可下载成片 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺 `--image`、缺 `--mode`、缺 `--duration`、选项写缩写）|
| `3` | 自检没全过 |
| `4` | 需要确认 —— 没给 `--yes`，会告诉你这次要花多少点 |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 等待超时 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

成功：

```json
{"ok": true, "app": "pic_lipsync", "taskId": "task_xxx", "status": "completed",
 "urls": ["https://…/x.mp4"], "files": ["./pic_lipsync-task_xxx.mp4"],
 "points": 181.5, "estimatedPoints": 450}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-digital-host/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       三个应用的参数表、实测报错原文、定价接口原文
│   └── troubleshooting.md    按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 实测记录（2026-11-07）

```
探针前  GET /api/v1/tasks → 20 条，最新 completed_at 09:51:39Z
探针    7 发「缺一个必填」的 submit（全部被参数校验拦下，没有 task_id，没有建任务）
探针后  GET /api/v1/tasks → 仍是 20 条，task_id 一条不差
流水    10 对「冻结 −N → 退款 +N」：pic_lipsync 250 点 ×N、image_human 250 点 ×N、lipsync 150 点 ×N
净花费  0 点
```

**顺带实测到一条硬规则：应用层 `submit` 先同步预扣、再校验参数。**
连「缺 image_url」这种必然被拒的请求也会先冻一笔再退回，所以本包的 `doctor` 一个 submit 都不发，
端点存在性改用定价表里已配价的三条规则来证明。

---

## 已知限制

1. **`dub` 的 `xiaojiayu2.0` / `3.0` 比 `1.0` 贵 5 倍**（13.5 vs 2.7 点/秒），先用 1.0 试效果
2. **`drive` 的 `duration` 要填输入音频的真实秒数**，填小了会被平台按实际音频纠正，预算就不准了
3. **任务刚 `completed` 时结果地址偶尔是空串**（实测竞态），本包取不到地址时会提示隔几秒再查
4. **`--upload` 的临时地址 24 小时内有效**，平台可能提前回收，别把它当持久素材地址
5. **`cost` 是预估**，真实扣费以平台结算的 `usage` 为准

---

## 免责

- 人像合成请自备**肖像权授权**；用真人形象、真人声音前，确保你拿到了对方同意。
- 生成内容的合规责任在使用者：不用于伪造他人身份、侵权素材或违法用途。


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
