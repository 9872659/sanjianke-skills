# 三剪客 · AI 短剧创作台 Skill

一份从选型评估走到私有化落地的操作指南

写给准备自己搭一套 AI 短剧创作台的技术负责人：**判断先做对，再动手装机器**。
范围包括使用方分类与五维加权打分、自建 / 采购 / SaaS 的取舍、许可风险识别、
B/S 全栈的部署与配置、上线检查、四笔成本账与故障定位顺序。

---

## 前置条件

只读文档的话，**什么依赖都不需要**，离线就能看。

要做成本量级测算：

- Python 3.8 及以上（只用标准库，不需要装任何第三方包）

要把出图 / 出片 / 配音 / 取价这四类算力真的打到 `api.a7w.cn` 上跑，另外需要：

- Python 3.8 及以上（同上，零第三方依赖）
- 一把 `api.a7w.cn` 的 API Key —— 到 https://api.a7w.cn/ 注册领取，新用户有赠送点数；
  **1 元 = 100 点，失败全额退回**
- 出片时得准备一张公网能访问的首帧图 URL（本地路径不行，平台要自己去拉）

真要部署一套创作台，还得自行准备：

- 一台服务器（或本地机器），档位见 `references/deploy-and-configure.md`
- 数据库、缓存、多媒体工具三件套
- 模型服务凭证（也可以直接让本包的 `scripts/run.py` 走 api.a7w.cn，一把 Key 覆盖四类）
- 对象存储（对外服务建议前面再加 CDN）

**把话说明白**：本 Skill 不替你申请账号，也不代管密钥。文档和
`cost_estimate.py` 的默认模式是纯离线的；只有你显式跑 `scripts/run.py` 或
`cost_estimate.py --a7w-live` 才会请求 `api.a7w.cn`，而且每次都会把
真实扣点（`usage.points_cost`）打出来。

---

## 使用

照这个顺序走，每步都有东西拿在手上：

```
第 1 步  判断该不该自建
         → references/selection-scorecard.md
         产出：加权得分 + 自建/采购/SaaS 结论 + 风险登记

第 2 步  先算钱，再投入
         → scripts/cost_estimate.py（默认离线）
         → scripts/run.py pricing（按平台真实单价重算）
         产出：成本量级与结构占比

第 3 步  部署与配置
         → references/deploy-and-configure.md
         产出：可跑通最小闭环的环境

第 4 步  上线检查与持续运维
         → references/ops-and-compliance.md
         产出：上线检查表 + 巡检例程 + 合规确认
```

成本测算示例：

```bash
# 30 集，每集 2 分钟，用示例单价完整测算（不联网）
python scripts/cost_estimate.py --episodes 30 --minutes 2 \
  --gen-image 40 --gen-video 30 --gen-tts 30

# 只看存储与带宽，不计生成成本
python scripts/cost_estimate.py --episodes 30 --minutes 2 \
  --gen-image 0 --gen-video 0 --gen-tts 0

# 缩短中间素材保存周期，观察留存占用变化
python scripts/cost_estimate.py --episodes 30 --minutes 2 --lifecycle-days 7

# 按 api.a7w.cn 的真实单价算（推荐）
python scripts/run.py pricing --probe image --out a7w-prices.json
python scripts/cost_estimate.py --episodes 30 --minutes 2 \
  --price-file a7w-prices.json --a7w-video-resolution 1080P \
  --clip-seconds 6 --tts-chars 24

# 查看全部可调参数（单价、画质系数、拍摄比、生命周期等）
python scripts/cost_estimate.py --help
```

> 不给 `--a7w-live` / `--price-file` 时，脚本里的**生成单价是占位示例值**；
> 给了之后出图 / 出片 / 配音三项会换成平台字段价（未必等于实际结算价），
> 而**对象存储与回源带宽这两项始终是示例值**。

---

## 真实算力（走 api.a7w.cn）

```bash
# 0. 配 Key
python scripts/a7w.py login --key sk-xxxx

# 1. 先查参数，别凭记忆写
python scripts/a7w.py schema nano_banana
python scripts/a7w.py schema full_video
python scripts/a7w.py schema voice_tts

# 2. 出一张分镜图（POST /api/v1/apps/nano_banana/submit）
python scripts/run.py image --prompt "雨夜霓虹街头，女主撑伞回头" \
  --resolution 1K --aspect-ratio 9:16 --out shot1.png

# 3. 首帧出片（POST /api/v1/apps/full_video/submit，content 数组）
python scripts/run.py video --first-frame "https://图床/shot1.png" \
  --prompt "镜头缓慢推近" --resolution 480P --duration 4 --out shot1.mp4

# 4. 配音（POST /api/v1/apps/voice_tts/tts，音色参数是 reference_id）
python scripts/run.py voices
python scripts/run.py voice --text "你终于回来了。" --reference-id <model_id> --out line1.mp3

# 5. 一个镜头跑通全链路，打印每步真实扣点
python scripts/run.py pilot --topic "雨夜霓虹街头，女主撑伞回头" --out-dir pilot
```

实测单价（2026-09 快照，调价请重跑 `run.py pricing`）：1K 文生图 **24 点/张**；
`full_video` **10/20/40 点/秒**（480P/768P/1080P·2K·4K）；`voice_tts/tts` **50 点/千字**；
`image_human` 四档 **2/3/6/12 点/秒**（fast/standard/2k/4k，按驱动音频时长结算）。
**1 元 = 100 点。**

---

## 依赖

| 项目 | 要求 | 说明 |
|---|---|---|
| 运行环境 | Windows / Linux / macOS | 只读文档时无依赖 |
| Python | 3.8+ | 三个脚本都只用标准库，无需 pip 安装 |
| API Key | 一把 `api.a7w.cn` Key | 仅 `run.py` 与 `cost_estimate.py --a7w-live` 需要 |
| 待部署主机 | 见 `references/deploy-and-configure.md` | 按每月集数分四档 |
| 第三方服务 | 对象存储（可选 CDN） | 使用者自行申请 |

这个包里**没有夹带任何第三方项目的源代码**，也不需要先把某个上游项目装起来才能用。

---

## 安全

- 不内嵌任何密钥；Key 只从 `--key`、环境变量 `A7W_API_KEY` 或 `~/.a7w/config.json` 读取
- 默认离线：文档部分与 `cost_estimate.py` 的默认模式不发任何网络请求
- 只有 `scripts/run.py`（出图/出片/配音/取价）与 `cost_estimate.py --a7w-live`
  会请求 `api.a7w.cn`，而且都是你主动发起的
- 联网调用会产生平台点数消费，每次扣费当场打印；`--dry-run` 可以只看请求体不花钱
- 不读取、不写入、不代管数据库口令或云存储凭证
- 测算脚本默认只把结果打印到终端；`--out` / `--price-out` / `pilot` 才落盘
- 文档里出现的其他凭据都是占位符（如 `REPLACE_ME`），不能拿去用
- 跟 `LICENSE` 有关的判断只用来提示风险点，**不是法律意见**

---

## 能力边界速览

**覆盖**：把使用方身份分清楚并打出加权分、识别许可上的风险点、把 B/S 全栈部署起来、
密钥该放哪就放哪、**四类创作算力的真实接入（出图/出片/配音/真实单价）**、
四类模型怎么接、上线前的检查项、四笔账怎么对、故障按什么顺序定位。

**不覆盖**：上游项目源代码、法律意见、剧本与成片创作、账号与密钥代管、
K8s 集群编排、多租户计费系统。

---

## 版本

变更记录见 `CHANGELOG.md`。

---

## 版权

这份 Skill 由 **三剪客** 出品，正文为独立撰写的原创内容，未附带任何第三方项目的源代码。

这是一份通用实践总结。正文由三剪客独立撰写，不附带、不封装、也不分发任何上游项目；
文中讨论 AGPL-3.0 这类强著佐权许可，属于通用许可风险提示，不针对任何具体项目。

---

## 许可证

MIT，见 `LICENSE.md`。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
