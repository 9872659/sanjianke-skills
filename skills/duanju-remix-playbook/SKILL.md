---
name: duanju-remix-playbook
slug: duanju-remix-playbook
displayName: 三剪客 · 短剧二创作业手册
description: "短剧二创的完整作业规范：授权核验门禁、成片口径锁定、四条差异化规则、批量成片抽帧查重、发布前合规扫描与质检清单。适用于一部剧批量出片前的流程搭建、成片互相雷同的排查、以及发布前的版权与违禁话术核验。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.3.3
summary: "短剧二创的可落地作业规范：五套示例口径（含分辨率、帧率、编码、响度、音量、时长结构、取材与转场的全套参数）、九步出片流程与实算例、四条差异化规则、批量成片抽帧查重、七类高危话术扫描。7 份资料 + 2 个离线脚本，示例口径可直接照抄开工。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
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

## 工作流 / 方法

**先定口径，再动手**：成片几十个参数不独立，改一个会牵动另一个；同一件事有几套口径，混用就会打架。开工第一件事是锁定这一批的参数组合，**批次内不混用**：

`本批口径：<名字> ｜ 依据：<谁定的> ｜ 出片人：<谁>`

**九步流程**：① 授权核验（未通过不出片）→ ② 素材盘点 → ③ 目标确定 → ④ 口径锁定 → ⑤ 取材规划 → ⑥ 脚本解说（每条独立写）→ ⑦ 合成 → ⑧ 质检 → ⑨ 发布。取材三原则：**首尾要稳、中间要乱、复用要换段**。

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
| `scripts/duanju_compliance.py` | 七类高危话术扫描 + promotion、title、comment 三个类目 | `python3 scripts/duanju_compliance.py --file script.txt --strict`；有高风险时退出码 1 |
| `scripts/frame_dedup.py` | 抽帧查重：均匀抽帧 → 9×8 灰度 → dHash 64 位 → 贪心唯一配对，输出相似度矩阵 | `python3 scripts/frame_dedup.py --dir "输出目录" --threshold 0.40 --strict`；需 ffmpeg |
| `scripts/selftest.py` | 内置自测（不调 ffmpeg、不联网、不写盘） | `python3 scripts/selftest.py -v` |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 不申请 | 脚本完全离线，无网络调用 |
| 读取文件 | 仅用户指定路径 | 待检查文案与指定目录下的视频 |
| 写入文件 | 仅在传 `--out` 时 | 写结果；不传则不写盘 |
| 调用外部程序 | 仅 ffmpeg，且仅用于抽帧 | `frame_dedup.py` 读帧 |
| 凭证 / API Key | 不申请 | 不读取密钥或登录态 |

源码在 `scripts/`，可逐行审阅：无混淆、无动态下载、无遥测。

---

## 怎么用

本包是**纯文本 + 零依赖 Python 脚本**，不需要装任何第三方包：

1. **先读 [`SKILL.md`](SKILL.md)** —— 主入口：完整流程、判断标准、常见坑
2. **`references/` 里有 7 份细节文档** —— 需要展开某一步时再翻
3. **`scripts/` 里有 3 个可直接跑的脚本**（只用 Python 标准库，Python 3.8+）

```bash
# 每个脚本都能直接跑，先看它的参数说明
python3 scripts/duanju_compliance.py --help
python3 scripts/frame_dedup.py --help
python3 scripts/selftest.py --help
```

| 脚本 | 用途 |
|---|---|
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
