# AI 短剧制作工作台 Skill

把 [算力集市 api.a7w.cn](https://api.a7w.cn/) 上的 21 个生成应用搭成一张
**短剧制作工作台** —— 面向真正要出片的人，只讲工具侧：**传什么、调哪个接口、拿回什么、怎么验收**。

- **应用能力矩阵与选型打分表** —— 出图 / 出片 / 配音 / 口型 / 音乐 / 音效 / 超分各挑哪个、为什么
- **六套现成组合配方** —— 静态对话戏、动作戏、旁白戏、快剪混剪、老片修复、数字人口播
- **一个镜头的六步 SOP** —— 每步的参数、验收标准与异常处理
- **多项目排产与对账** —— 任务表断点续跑、按应用汇总扣点、成片抽检清单

**一把 Key、一个 Base URL 调全部应用，不用自己部署模型。**

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

1. **先看手上有什么**：一句描述 / 一张图 / 一段视频 / 一句台词 —— 对照应用矩阵选应用。
2. **先算钱**：`python3 scripts/cost_estimate.py --shots 15 --duration 40`
3. **挑一套配方**：静态对话一律走配方 A（图片 + 口型），动作戏才走配方 B。
4. **跑一个镜头验证**：六步 SOP 走一遍，确认画幅、音色、口型都对。
5. **铺开批量**：每个镜头每步都写 `tasks.csv`，并发 2～4 路起步。
6. **出完就抽检**：缺镜、口型、画幅、音量、衔接，五项过一遍再进下一集。

```bash
# 看平台上有哪些应用、某个应用有哪些接口与参数
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema nano_banana
python3 scripts/a7w.py schema voice_tts
python3 scripts/a7w.py schema lipsync

# 先算钱（也可以不传规模参数，用默认值快速估）
python3 scripts/cost_estimate.py --shots 15 --image 24 --duration 40 --tts-chars 1800

# 调接口（异步自动轮询到结束，--out 直接落盘）
python3 scripts/a7w.py call nano_banana submit --body '{...}' --out shot01.png
python3 scripts/a7w.py call full_video submit --body '{...}' --out shot01.mp4
python3 scripts/a7w.py call lipsync submit --body '{...}' --out shot01-lip.mp4
```

完整说明见 [`SKILL.md`](SKILL.md)，细节在 `references/`。

---

## 目录结构

```
sanjianke-drama-workbench/
├── SKILL.md                    主入口：应用矩阵、选型表、六套配方、六步 SOP、排产
├── README.md                   本文件
├── LICENSE.md
├── references/
│   ├── 应用矩阵与选型.md        按输入形态选应用、五个视频应用打分、决策树
│   ├── 组合配方.md              六套配方的逐步调用、关键参数、成本量级、验收点
│   ├── 单镜头SOP.md             六步 SOP 的参数、验收与异常速查
│   ├── 排产与对账.md            任务表、断点续跑、并发建议、按应用对账、抽检清单
│   ├── getting-started.md      注册 / 充值 / 取 Key / 配置
│   └── 通用说明.md              响应信封、异步机制、错误码、计费口径
└── scripts/
    ├── a7w.py                  零依赖客户端（库 + 命令行）
    └── cost_estimate.py        工作台成本测算（零依赖、不联网）
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

成本测算：

```bash
python3 scripts/cost_estimate.py --shots 15
python3 scripts/cost_estimate.py --shots 15 --image 24 --duration 40 --tts-chars 1800
python3 scripts/cost_estimate.py --shots 15 --lipsync-ratio 1.0 --waste 0.4
python3 scripts/cost_estimate.py --shots 15 --json
```

---

## 计费速查

| 项目 | 口径 | 参考价 |
|---|---|---|
| 出图 `nano_banana` | 按张 | 24 点/张 |
| 出片 `full_video` | 按分辨率 × 秒 | 参考 20 点/秒（1080P） |
| 出片 `happy_horse` | 按秒 | 720P 0.9 点/秒；1080P 1.6 点/秒 |
| 配音 `voice_tts` | 按 Token | 输入 50 点/千 Token |
| 克隆音色 | 按次 | 200 点/次 |
| 口型 `image_human` | 按驱动音频秒 | `fast` 1.5 / `standard` 2 / `2k` 4 / `4k` 8 |
| BGM | 按次 | 65 点/次 |
| 搜曲 | 按次 | 10 点/次 |
| 查任务 | — | 免费 |

1 元 = 100 点。**逐接口真实价用 `schema <应用代号>` 读 `tenant_*` 字段**，
最终以 `data.usage.points_cost` 的实际扣费为准。

---

## 依赖

- Python 3.8+，**仅标准库**（urllib / json / csv / argparse），无第三方包
- 需要能访问 `https://api.a7w.cn`
- 本地拼接与混音需要 ffmpeg（可选）

---

## 安全

- Key 存在本机 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY`
- 脚本只把 Key 发往 `api.a7w.cn`
- **不要**把 Key 提交到代码仓库；跑批量前给 Key 设消费上限
- 素材授权与内容合规责任由使用者承担

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
