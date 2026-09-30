---
name: duanju-remix-playbook
slug: duanju-remix-playbook
displayName: 三剪客 · 短剧二创作业手册
description: "短剧二创的完整作业规范：授权核验门禁、成片口径锁定、四条差异化规则、批量成片抽帧查重、发布前合规扫描与质检清单。适用于一部剧批量出片前的流程搭建、成片互相雷同的排查、以及发布前的版权与违禁话术核验。自带 `scripts/run.py` 真接算力：台词转写走 `POST /api/v1/apps/voice_tts/stt`（拿回字级时间戳字幕），悬念解说稿走 `POST /api/v1/chat/completions`，只需一把 api.a7w.cn 的 API Key。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.3.7
summary: "短剧二创的可落地作业规范：五套示例口径（含分辨率、帧率、编码、响度、音量、时长结构、取材与转场的全套参数）、九步出片流程与实算例、四条差异化规则、批量成片抽帧查重、七类高危话术扫描。7 份资料 + 5 个脚本（3 个纯离线自检，2 个接 api.a7w.cn 算力：语音转写 `POST /api/v1/apps/voice_tts/stt` + 解说稿 `POST /api/v1/chat/completions`），示例口径可直接照抄开工。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 短剧二创
  - 批量出片
  - 内容质检
  - 版权合规
  - 视频创作
---

# 短剧二创作业手册

短剧二创的门槛不在剪辑技术，而在**流程管理**：授权、口径、成片雷同、发布前合规。本 Skill 把这些固化成可执行步骤，并给两个离线工具。

## 这个 Skill 能做什么

- 批量出片前，搭起「授权 → 口径 → 取材 → 合成 → 质检 → 发布」的流程
- 成片互相雷同时，算出**哪几条撞了**（抽帧相似度矩阵）
- 发布前扫解说稿、标题、封面文案与推广话术
- 给一套可照抄的示例口径（分辨率、帧率、编码、响度、音量、取材、转场）
- 核验原片、音色、BGM、字体、肖像授权
- **把流水线里最费环境的两步接上算力**：原片台词转写成带**字级时间戳**的字幕（`voice_tts/stt`），以及按「四条差异化」逐条生成悬念解说稿草稿（大模型）

## 工作流 / 方法

**先定口径，再动手**：成片几十个参数不独立，改一个会牵动另一个；同一件事有几套口径，混用就会打架。开工第一件事是锁定这一批的参数组合，**批次内不混用**：

`本批口径：<名字> ｜ 依据：<谁定的> ｜ 出片人：<谁>`

**九步流程**：① 授权核验（未通过不出片）→ ② 素材盘点 → ③ 目标确定 → ④ 口径锁定 → ⑤ 取材规划 → ⑥ 脚本解说（每条独立写）→ ⑦ 合成 → ⑧ 质检 → ⑨ 发布。取材三原则：**首尾要稳、中间要乱、复用要换段**。

> **接上算力的两个位置（零安装）**：⑤ 之前用 `scripts/run.py transcribe` 把原片台词转成带**字级时间戳**的字幕（`POST /api/v1/apps/voice_tts/stt`），取材与对齐都靠它；⑥ 的解说稿用 `scripts/run.py narration` 先出草稿（`POST /api/v1/chat/completions`，一次可出多条互不重复的版本）。**草稿只是草稿**——必须过 ⑧ 的合规扫描与人工复核才能配音，详见下面「怎么用（命令行）」。方法论的结论（口径、差异化、查重阈值）不因是否用模型而改变。

**时长**：不要用「集数 × 每集固定秒数」估时长（短剧单集 40s~95s 常见），先按目标时长取材再补差额——`TARGET_SEC = 目标分钟数 × 60 − 5`（留 CTA 与转场余量），成片总时长 = 主体 + 片头 + 片尾 + CTA。

**条数上限**：

```
最多条数 ≈ 可用素材总时长 ÷ 单条消耗 × 复用系数
```

| 复用系数 | 建议 |
|---|---|
| 1–2 | 安全，产出少 |
| 3 | 需四条差异化全部生效 |
| 5 | 风险明显上升，不建议 |
| 8+ | 不要做 |

**四条差异化**：① 解说稿每条独立写（这条讲动机、那条讲反转、另一条讲伏笔）；② 配乐按段落情绪切换，同条内不重复；③ 顺序首尾固定、中间打乱；④ 开头三秒保证不同。判断标准：**「观众已经看过原片，我这条还提供了什么？」** 只切碎重排 = 没有增量。

**发布前四关**：原片版权（信息网络传播权 / 改编剪辑权 / 素材使用权，缺一项都不能做）→ 音色 / BGM / 字体 / 肖像授权 → 文案合规扫描 → 填留痕行。最常见的坑是只拿到「推广授权」就以为可以任意剪辑。

**质检关键项**：单视频轨 / 单音频轨、音视频时长差 **< 0.05s**、`yuv420p`、音频 **48 kHz** 立体声；响度 **-14 LUFS 左右**不削波；开头三秒有钩子；有超阈值相似对就**重做**。

> **音量坑**：淡入淡出与区域音量串联时，最终音量是几个系数的**乘积**——改完必须导出听一遍。

**发布节奏**：超阈值的两条**不要都发**；每批留一行记录，下一批开工前先看上一批。

## 参考文件

| 文件 | 内容 |
|---|---|
| `references/rights-checklist.md` | 三项权利、核验清单、留痕模板、开工四关 |
| `references/license-areas.md` | 音色 / BGM / 字体 / 肖像授权与台账 |
| `references/platform-and-content-rules.md` | 平台判定维度、正向做法、七类高危话术 |
| `references/workflow-overview.md` | 九步流程、口径管理、时间预算、记录表 |
| `references/differentiation-rules.md` | 四条差异化、复用系数风险表、自检表 |
| `references/params-example.md` | 五套口径总表、视频音频参数、音量相乘坑、字幕转场 CTA、时长实算例、高燃片头算法、过时黑名单 |
| `references/quality-checklist.md` | 封装 / 声音 / 画面 / 内容 / 合规五组质检项 |

## 脚本

| 脚本 | 用途 | 用法 |
|---|---|---|
| `scripts/run.py` | **算力版主脚本**：台词转写（`POST /api/v1/apps/voice_tts/stt`，出字级时间戳字幕）+ 悬念解说稿（`POST /api/v1/chat/completions`，可一次多条） | `python3 scripts/run.py transcribe 第3集.mp4 --srt`<br>`python3 scripts/run.py narration --file 台词稿.txt --target-min 5 --variants 3`<br>`python3 scripts/run.py pipeline 第3集.mp4 --target-min 5 --out-dir ./出片` |
| `scripts/a7w.py` | api.a7w.cn 零依赖客户端（标准库）：`login / whoami / apps / points / schema / call / task` | `python3 scripts/a7w.py schema voice_tts`（查真实参数名）<br>`python3 scripts/a7w.py whoami`（验 Key） |
| `scripts/duanju_compliance.py` | 七类高危话术扫描 + promotion、title、comment 三个类目 | `python3 scripts/duanju_compliance.py --file script.txt --strict`；有高风险时退出码 1 |
| `scripts/frame_dedup.py` | 抽帧查重：均匀抽帧 → 9×8 灰度 → dHash 64 位 → 贪心唯一配对，输出相似度矩阵 | `python3 scripts/frame_dedup.py --dir "输出目录" --threshold 0.40 --strict`；需 ffmpeg |
| `scripts/selftest.py` | 内置自测（不调 ffmpeg、不联网、不写盘）；含 `run.py` 的纯逻辑用例（补标点、字幕合并、SRT 格式、模型 JSON 解析） | `python3 scripts/selftest.py -v` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **仅 `run.py` / `a7w.py` 需要**，且只在显式调用时 | 台词转写 `POST /api/v1/apps/voice_tts/stt`、解说稿 `POST /api/v1/chat/completions`；`duanju_compliance.py` / `frame_dedup.py` 完全离线、源码里没有任何网络调用，`selftest.py` 也不联网（它导入 `run.py` 只为调用纯函数，不会发起请求） |
| 读取文件 | 仅用户指定路径 | 待检查文案、指定目录下的视频、待上传的音视频 |
| 写入文件 | 仅在传 `--out` / `--srt` / `--out-dir` 时 | 写结果；不传则不写盘 |
| 调用外部程序 | 仅 ffmpeg，且仅用于抽帧 | `frame_dedup.py` 读帧 |
| 凭证 / API Key | 仅 `run.py` 读取 | 从 `--key` / 环境变量 `A7W_API_KEY` / `~/.a7w/config.json` 读**你自己的** Key 用于计费；不内嵌、不代付、不转发 |

源码在 `scripts/`，可逐行审阅：无混淆、无动态下载、无遥测。

---

## 怎么用

本包是**纯文本 + 零依赖 Python 脚本**，不需要装任何第三方包：

1. **先读 [`SKILL.md`](SKILL.md)** —— 主入口：完整流程、判断标准、常见坑
2. **`references/` 里有 7 份细节文档** —— 需要展开某一步时再翻
3. **`scripts/` 里有 5 个可直接跑的脚本**（只用 Python 标准库，Python 3.8+）：3 个纯离线，2 个接 `api.a7w.cn` 算力（需自备 Key）

```bash
# 每个脚本都能直接跑，先看它的参数说明
python3 scripts/run.py --help
python3 scripts/a7w.py --help
python3 scripts/duanju_compliance.py --help
python3 scripts/frame_dedup.py --help
python3 scripts/selftest.py --help
```

| 脚本 | 用途 |
|---|---|
| [`scripts/run.py`](scripts/run.py) | 台词转写 + 解说稿（接算力）；见下方「怎么用（命令行）」 |
| [`scripts/a7w.py`](scripts/a7w.py) | api.a7w.cn 零依赖客户端；见 SKILL.md 的「脚本」一节 |
| [`scripts/duanju_compliance.py`](scripts/duanju_compliance.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/frame_dedup.py`](scripts/frame_dedup.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/selftest.py`](scripts/selftest.py) | 见 SKILL.md 的「脚本」一节 |

| 文档 |
|---|
| [`references/differentiation-rules.md`](references/differentiation-rules.md) |
| [`references/license-areas.md`](references/license-areas.md) |
| [`references/params-example.md`](references/params-example.md) |
| [`references/platform-and-content-rules.md`](references/platform-and-content-rules.md) |
| [`references/quality-checklist.md`](references/quality-checklist.md) |
| [`references/rights-checklist.md`](references/rights-checklist.md) |
| [`references/workflow-overview.md`](references/workflow-overview.md) |

> 没有 API Key、或者想让人给你一份能直接跑的示例，看文末「联系我们」。

---

## 怎么用（命令行）

`scripts/run.py` 是**真接算力**的那个脚本：它在本机只要求 Python 3.8+（只用标准库），
把转写与撰稿送到 `api.a7w.cn` 执行。两个真实端点写在脚本常量里，可逐行核对：

| 步骤 | 端点 | 说明 |
|---|---|---|
| 台词转写 | `POST /api/v1/apps/voice_tts/stt` | multipart 上传本地音视频（文件字段 `audio`）或传 `audio_url`；返回台词稿 + **字级时间戳** |
| 解说稿 | `POST /api/v1/chat/completions` | OpenAI 兼容协议，`Authorization: Bearer <你的 Key>`；换 `model` 即换模型 |

**第一步：配 Key**（三种方式任选一种，脚本不内嵌任何 Key）

```bash
python3 scripts/run.py transcribe 第3集.mp4 --key sk-xxxx     # 临时指定
export A7W_API_KEY=sk-xxxx          # Windows 用 set A7W_API_KEY=sk-xxxx
# 或到 https://api.a7w.cn/ 注册领 Key 后执行：python3 scripts/a7w.py login --key sk-xxxx
```

**第二步：转写台词（出字幕）**

```bash
python3 scripts/run.py transcribe 第3集.mp4                          # 台词稿打到 stdout（JSON）
python3 scripts/run.py transcribe 第3集.mp4 --lang zh --srt          # 顺手写同名 .srt 字幕
python3 scripts/run.py transcribe 第3集.mp4 -o 台词稿.txt --srt-out 第3集.srt
python3 scripts/run.py transcribe --url https://…/ep3.mp3 --lang zh  # 公网音频走 audio_url
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--lang` | 自动检测 | 识别语言，如 `zh` / `en` |
| `--srt` / `--srt-out` | 不写盘 | 生成 .srt（默认与音频同名） |
| `-o/--out` | 不写盘 | 台词稿落盘路径 |
| `--gap` / `--max-chars` | 0.7 / 18 | 字幕断行口径：停顿超过多少秒断行、单行最多多少字 |

> 平台返回的是**字符级**时间戳（实测：`result.segments` 一个字一条、且不带标点，
> 标点只在整段 `result.text` 里）。脚本会自动把标点补回去再合并成正常字幕行，
> 所以你不必自己写合并逻辑。转写按次固定价（**实测一次 40 点**，要不要时间戳同价）。
> 实测口径：不做说话人分离，只给「说了什么、什么时候」。

**第三步：让大模型写解说稿草稿**

```bash
python3 scripts/run.py narration --file 台词稿.txt --target-min 5                  # 1 条
python3 scripts/run.py narration --file 台词稿.txt --target-min 5 --variants 3     # 3 条差异化
python3 scripts/run.py narration --file 台词稿.txt --target-min 8 --angle "伏笔" --out-dir ./解说稿
python3 scripts/run.py narration --file 台词稿.txt --show-prompt                   # 只看提示词，不花钱
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--file` / `--text` / stdin | — | 台词稿来源三选一 |
| `--target-min` | 5 | 目标成片分钟数；脚本按 `目标秒数 ≈ 分钟×60−5`、中文 TTS 约 4.5 字/秒算出目标字数写进提示词 |
| `--variants` | 1 | 一次出几条稿子（对应「四条差异化」第 1 条：每条独立写），串行调用、逐条独立 |
| `--angle` | 自定 | 指定切入角度（反转 / 动机 / 伏笔） |
| `--model` | `DeepSeek-V4-Flash` | 平台模型名，完整列表见 `GET https://api.a7w.cn/api/v1/models`（换 `model` 即换模型）；实测 `DeepSeek-V4-Flash` 与旧别名 `deepseek-chat` 都能正常返回 |
| `--strict` | 关 | 生成稿命中高风险话术时退出码 1 |

脚本对每一条草稿都会**自动跑一遍本包离线词表**做自检，并把命中项写进输出与 markdown 文件——
模型不保证不写红线话术，这一层是兜底。

**第四步：一条龙**

```bash
python3 scripts/run.py pipeline 第3集.mp4 --target-min 5 --variants 2 --out-dir ./出片
# 产出：<stem>.台词稿.txt、<stem>.srt、<stem>.解说稿-1.md、<stem>.解说稿-2.md
```

**已知限制与实测踩坑**（宁可先说明，不要事后猜）

- 上游偶发 `HTTP 502 {"code":"upstream_error","message":"upstream timeout"}`，属瞬时故障；脚本内置 5 次退避重试，**单条稿子失败不影响整批**（失败项记进输出的 `errors`）。
- 模型偶尔会在合法 JSON 后面多吐一两个字符；脚本用 `JSONDecoder.raw_decode` 兼容，解析不出来时**不假装成功**，会明确报出来并保留原文。
- 转写不做说话人分离、不能选本地模型档位；解说稿是**草稿**，配音前必须过 `scripts/duanju_compliance.py --strict`。
- 计费：1 元 = 100 点；转写按次固定价，大模型按 token（响应 `usage` 里给 token 数）；失败全额退回。

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
