# 三剪客 · AI 短剧创作画布 Skill

把一部短剧从想法做到能发：**无限画布排布分镜 → AI Agent 拆剧本 → 逐镜出图 → 首尾帧出片 →
配音配乐 → 导出成片**。图像、视频、语音、音乐全部走 `api.a7w.cn`，一把 Key 打通。

---

## 前置条件

| 项 | 要求 |
|---|---|
| **API Key** | **必须自备**。[算力集市 api.a7w.cn](https://api.a7w.cn/) 注册后创建，形如 `sk-...`，新用户有赠送点数 |
| Python | 3.8+，**只用标准库**（`urllib` / `json`） |
| ffmpeg | 合成阶段需要（拼接 / 字幕 / 混音 / 转码）。`ffmpeg -version` 能出版本号即可 |
| 网络 | 能访问 `api.a7w.cn` |

```bash
export A7W_API_KEY=sk-你的key      # Windows: $env:A7W_API_KEY="sk-你的key"
python3 scripts/a7w.py whoami      # 应返回「Key 有效，可用插件 N 个」
```

> **本包不内嵌任何密钥，也不代付费用。** 请勿使用他人提供的 Key。
> 完整的注册、充值、取 Key 步骤见 [`references/getting-started.md`](references/getting-started.md)。

---

## 使用

拿到这个 Skill 后，按七步流水线走：

1. **拆剧本**。把剧情丢给模型网关 `chat/completions`，要它输出分场、人物小传与情绪曲线。
2. **写分镜表**。让它按固定字段出表：镜号 / 景别 / 运镜 / 时长 / 画面 / 台词 / 音效。
   模板与词表见 [`references/分镜方法.md`](references/分镜方法.md)。
3. **定人物**。每个角色先出一张**定妆图**（`nano_banana` 文生图），这张图是全片人物一致性的锚点。
4. **出关键帧**。逐镜出首帧：`action=edit` + 把定妆图放进 `image_urls`，人物才不会跑形。
   做法见 [`references/人物一致性.md`](references/人物一致性.md)。
5. **生成视频**。首帧（必要时加尾帧）驱动 `full_video` / `happy_horse` / `seedance` / `wan`。
   提示词范式见 [`references/提示词范式.md`](references/提示词范式.md)。
6. **配音配乐**。`voice_tts` 出台词、`music_generation` 出 BGM、`mmaudio` 出音效。
   见 [`references/配音与配乐.md`](references/配音与配乐.md)。
7. **合成成片**。本地 ffmpeg 拼接、烧字幕、混音、转码；需要母版再走 `flashvsr` 超分。
   逐条可复制的命令见 [`references/合成与导出.md`](references/合成与导出.md)。

> **画布上的排布顺序就是第 2 步产出的分镜表** —— 镜号即节点编号，
> 改哪一镜就只重跑那一个节点，不用整片重来。

### 最小闭环（四条命令）

```bash
export A7W_API_KEY=sk-你的key

# 1) 首帧（锁角色就加 "action":"edit" 与 "image_urls":["<定妆图 URL>"]）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"prompt":"雨夜街头，女主撑伞站在路灯下，中景，冷色调，写实电影感","aspect_ratio":"9:16"}' \
  --out shot01.png

# 2) 台词（音色先克隆一次，拿 reference_id）
python3 scripts/a7w.py call voice_tts tts_async \
  --body '{"text":"这雨，下了整整十年。","reference_id":"<音色 ID>"}' \
  --out shot01.mp3

# 3) 出片（content 里必须有一项 text）
python3 scripts/a7w.py call full_video submit \
  --body '{"content":[{"type":"text","text":"镜头缓慢推近，女主抬头看向路灯"}],"ratio":"9:16","resolution":"720P","duration":6}' \
  --out shot01.mp4

# 4) 合成（示例，完整命令见 references/合成与导出.md）
ffmpeg -y -f concat -safe 0 -i list.txt -c copy ep01.mp4
```

---

## 目录结构

```
sanjianke-canvas-drama/
├── SKILL.md                    七步流水线 + 最小闭环 + 十三个常见坑
├── README.md                   本文件
├── LICENSE.md                  MIT
├── references/
│   ├── 分镜方法.md              分镜表模板、景别与运镜词表、上下文连贯校验
│   ├── 人物一致性.md            定妆图 → 参考图 → 首尾帧的三层锁定
│   ├── 提示词范式.md            图像 / 视频提示词结构与正反例
│   ├── 配音与配乐.md            音色克隆、分段配音、BGM 与音效
│   ├── 合成与导出.md            ffmpeg 拼接、SRT 生成、字幕烧录、混音、转码、超分
│   ├── 成本估算.md              各环节点数、一集预算、省钱顺序
│   ├── api-模型网关.md          OpenAI 兼容入口、查模型、错误码
│   ├── api-生成应用.md          图像 / 视频 / 语音 / 数字人 / 音乐接口速查
│   ├── getting-started.md       注册、领 Key、配置
│   └── 通用说明.md              权限、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行，只用 Python 标准库）
```

---

## 客户端命令

`scripts/a7w.py` 零依赖，可以直接当库 `import a7w`，也可以直接跑命令行。
它会把异步任务**自动轮询到结束**再返回。

| 命令 | 作用 |
|---|---|
| `login --key sk-xxx` | 验证并保存 Key 到 `~/.a7w/config.json`（权限 600） |
| `whoami` | 验证 Key，看可用插件数 |
| `apps` | 列出这把 Key 能用的全部插件 |
| `schema <app>` | 看某个插件有哪些接口、每个参数是什么 |
| `call <app> <api> --body '{...}'` | 调用接口（异步自动轮询） |
| `call ... --no-wait` | 只提交，不等结果 |
| `call ... --out 文件` | 把结果 URL 下载到本地 |
| `task <task_id>` | 查异步任务状态与真实扣点 |
| `points` | 看最近的任务用量 |

```bash
# 动手前先现查一遍参数与真实价，不要照抄任何文档
python3 scripts/a7w.py schema nano_banana
python3 scripts/a7w.py schema full_video
python3 scripts/a7w.py schema voice_tts
```

> 键顺序：`--key` 参数 > 环境变量 `A7W_API_KEY` > `~/.a7w/config.json`。

---

## 计费速查

**1 元 = 100 点。按点数计费，用多少扣多少，没有月费。**
**先冻结后结算，失败全额退回**；查询类接口免费；每次返回的
`data.usage.points_cost` 就是本次真实扣费。

| 环节 | 应用 | 计费口径 | 量级（快照） |
|---|---|---|---|
| 剧本 / 分镜 | 模型网关 | 点 / 百万 tokens | 一次问答约 1 点 |
| 出图 | `nano_banana` / `submit` | 点 / 张（按模型与分辨率档） | 24 ~ 61.5 点/张 |
| 出片 | `full_video` / `submit` | 点 / 秒（按分辨率分档） | 480P 10 · 768P 20 · 1080P/2K/4K 40 |
| 出片 | `happy_horse` / `submit` | 点 / 秒 | 720P 0.9 · 1080P 1.6 |
| 出片 | `wan` / `seedance` | 按秒或按 tokens 分档 | `schema` 现查 |
| 数字人 | `image_human` / `submit` | 点 / 秒（按 `mode` 档） | fast 1.5 · standard 2 · 2k 4 · 4k 8 |
| 对口型 | `lipsync` / `submit` | 以站内计费为准 | `schema lipsync` 现查 |
| 音色克隆 | `voice_tts` / `clone_voice` | 点 / 次 | 200 点 |
| 台词合成 | `voice_tts` / `tts` · `tts_async` | 点 / 千 tokens | 50 点 / 1k |
| BGM | `music_generation` / `create` | 点 / 次 | 65 点 |
| 音效 | `mmaudio` / `submit` | 点 / 次 | 0.1 点 |
| 超分 | `flashvsr` / `submit` | 固定 + 按用量 | 0.1 + 3 点/单位 |
| 查询 | 各应用的 `query` | **免费** | — |

一集 2 分钟（约 25 镜）的完整测算与省钱顺序见
[`references/成本估算.md`](references/成本估算.md)。

> 平台同时给出**标准价**（`fixed_price` / `input_price`）与
> **租户实际结算价**（`tenant_*`）。**做预算一律用 `tenant_*`，最终以实际扣费为准** ——
> 上表是某次快照，你自己的真实价用 `python3 scripts/a7w.py schema <app>` 现场读。

---

## 依赖

- **Python 3.8+**，**仅标准库**（`urllib` / `json` / `mimetypes`），无需 `pip install`
- **ffmpeg**：合成阶段用（拼接、字幕、混音、转码）。`ffmpeg` 与 `ffprobe` 都要在 `PATH` 里
- **网络**：`api.a7w.cn`
- 素材入参一律用**公网可访问的 URL**，不支持本地路径

---

## 安全

- **不内嵌任何密钥。** Key 从环境变量或 `~/.a7w/config.json` 读取，只发往 `api.a7w.cn`
- 不要把 Key 写进代码、截图或提交到仓库；泄露等于余额泄露，发现异常立即**吊销重建**
- 每个 Key 可以单独设**消费上限（quota）**，批量开跑前设成预算的 1.2 倍用于止损
- **版权与授权**：剧本、素材、形象与音色的使用授权由使用者自行取得
- **内容合规**：生成内容的使用与合规责任由使用者承担，本 Skill 不替代审查

---

## 许可证

MIT，见 [`LICENSE.md`](LICENSE.md)。

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
