# AI 短视频一键生成 Skill

给一个选题就能出片：**脚本 → 配音 → 画面 → 字幕 → BGM → 合成**，
七道工序全部走 [算力集市 api.a7w.cn](https://api.a7w.cn/)。

- 脚本走 OpenAI 兼容模型网关（75 个在架模型换 `model` 即换）
- 配音走 `voice_tts`，画面走 `nano_banana`，动感走 `full_video`
- 字幕时间轴给出「分段累计时长」与「`stt` 精确时间戳」两种可落地做法
- BGM 走 `music_generation` / `music_search`，口播号另有 `image_human` 一条路

**一把 Key、一个 Base URL 跑完全流程，不用自己部署任何模型。**

---

## 前置条件

一把 **api.a7w.cn 的 API Key**。完整的注册、充值、取 Key 步骤见
[`references/getting-started.md`](references/getting-started.md)，
或直接去 [算力集市 · 注册领 API Key](https://api.a7w.cn/)（新用户送点数）。

```bash
python3 scripts/a7w.py login --key sk-你的key
python3 scripts/a7w.py whoami
```

---

## 使用

拿到这个 Skill 后，Agent 会按这套顺序干活：

1. **先问清三件事**：选题、时长、画幅（`9:16` / `16:9` / `1:1`）—— 全流程锁一个画幅。
2. **写脚本**：让模型**按镜头分段**输出 JSON（`shot_id` / `line` / `visual`），后面全部按它对齐。
3. **逐段配音**：每句单独合成，方便字幕直接累加时长；用自己的声音就先 `clone_voice` 一次。
4. **出图**：每镜头一张，统一风格后缀；**静态画面就到此为止**，别继续出视频。
5. **只给需要动感的镜头出片**：`duration` 只能 4～15 秒整数。
6. **做字幕**：画面按镜头出 → 用「分段累计时长」；素材池混剪 → 用 `stt` 精确时间戳。
7. **本地合成**：ffmpeg 拼画面、拼配音、压低 BGM 混音、烧字幕；改一版不花钱。
8. **批量时控并发**：一个选题一个目录、一张 `tasks.csv`，并发 2～4 路起步。

```bash
# 看平台上有哪些应用、某个应用有哪些接口与参数
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py schema nano_banana

# 调接口（异步自动轮询到结束，--out 直接落盘）
python3 scripts/a7w.py call voice_tts tts --body '{"text":"……"}' --out dub/shot01.mp3
python3 scripts/a7w.py call nano_banana submit --body '{...}' --out imgs/shot01.png
python3 scripts/a7w.py call full_video submit --body '{...}' --out clips/shot01.mp4
```

脚本撰写走模型网关，用 `curl` 或任意 OpenAI SDK：

```bash
curl -sS -X POST "https://api.a7w.cn/api/v1/chat/completions" \
  -H "Authorization: Bearer $A7W_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash","messages":[{"role":"user","content":"……"}]}'
```

完整说明见 [`SKILL.md`](SKILL.md)，细节在 `references/`。

---

## 目录结构

```
sanjianke-short-video-maker/
├── SKILL.md                    主入口：七道工序、字幕两法、计费、常见坑
├── README.md                   本文件
├── LICENSE.md
├── references/
│   ├── 出片流水线.md            七道工序的衔接、每步参数与验收
│   ├── 字幕与合成.md            两种时间轴做法、SRT 生成脚本、ffmpeg 命令
│   ├── 批量出片.md              选题清单、并发、续跑、成本预估、对账
│   ├── 接口速查.md              全部用到的应用与接口参数
│   ├── getting-started.md      注册 / 充值 / 取 Key / 配置
│   └── 通用说明.md              响应信封、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行）
```

---

## 客户端命令

| 命令 | 作用 |
|---|---|
| `login --key sk-xxx` | 验证并保存 Key 到 `~/.a7w/config.json` |
| `whoami` | 验证 Key，看可用插件数 |
| `apps` | 列出这个 Key 能用的所有应用 |
| `schema <app>` | 看某应用的接口与参数 |
| `call <app> <api> --body '{...}'` | 调用接口（异步自动轮询） |
| `call ... --no-wait` | 只提交，不等结果 |
| `call ... --out 文件` | 把结果下载到本地 |
| `task <task_id>` | 查异步任务状态 |
| `points` | 看最近的用量 |

> 模型网关（`/chat/completions`）不走 `a7w.py`，用 `curl` 或任意 OpenAI SDK。

---

## 计费速查

| 工序 | 口径 | 参考价 |
|---|---|---|
| 脚本撰写 | 按 Token | 一条 60 秒口播稿约几角钱 |
| 配音 `voice_tts/tts` | 50 点/千 Token | 200 字约 10 点 = 0.10 元 |
| 克隆音色 | 按次 | 200 点/次（做一次长期用） |
| 出图 `nano_banana` | 按张 | 24 点/张（1K） |
| 图生视频 `full_video` | 按分辨率 × 秒 | 参考 20 点/秒（1080P） |
| 口播数字人 `image_human` | 按驱动音频秒 | `fast` 1.5 / `standard` 2 / `2k` 4 / `4k` 8 |
| 字幕 `voice_tts/stt` | 按次 | 30 点/次 |
| BGM `music_generation/create` | 按次 | 65 点/次 |
| 搜曲 `music_search/search` | 按次 | 10 点/次 |
| 查任务 | — | 免费 |

1 元 = 100 点。**一条 60 秒竖屏约 8～15 元**（含 30% 废片率），大头在画面。
**省钱按优先级：静态画面别出视频 → 少出图 → 分辨率锁够用档 → 音色克隆只做一次。**

---

## 依赖

- Python 3.8+，**仅标准库**（urllib / json / csv），无第三方包
- 需要能访问 `https://api.a7w.cn`
- 本地合成需要 ffmpeg 与 ffprobe

---

## 安全

- Key 存在本机 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY`
- 脚本只把 Key 发往 `api.a7w.cn`
- **不要**把 Key 提交到代码仓库；批量跑之前给 Key 设消费上限
- 素材与音乐授权、内容合规责任由使用者承担

---

## 许可证

MIT，见 `LICENSE.md`。

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
