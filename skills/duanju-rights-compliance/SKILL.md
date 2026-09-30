---
name: duanju-rights-compliance
slug: duanju-rights-compliance
displayName: 三剪客 · 短剧二创授权与合规自查
description: "短剧二创的版权授权核验与内容合规自查：授权四关门禁、留痕模板、音色与音乐字体肖像授权要点、平台原创性要求、AI 内容标注、短剧推广高危话术扫描。适用于开工前判断一部剧能不能做二创、发布前扫描解说稿与推广文案是否踩线，以及被投诉时整理授权链条。自带 `scripts/run.py` 真接算力：给一批文案，先离线正则粗筛、再走 `POST /api/v1/chat/completions` 逐条判风险等级（high/medium/low/pass）并给出可直接用的改写文案。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.1.7
summary: "短剧二创开工前的授权门禁与发布前的合规自检工具：3 份作业规范 + 4 个脚本（离线正则扫描 + 零依赖客户端 + 大模型批量初筛 `POST /api/v1/chat/completions`；离线扫描覆盖全集承诺、独家宣称、擦边引流、暴力血腥、盗版导流、收益诱导、极限词七类，模型补谐音与规避写法的语义判定并给改写建议）。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 短剧二创
  - 版权授权
  - 内容合规
  - 广告法
  - 违禁词
---

# 短剧二创授权与合规自查

短剧二创和普通内容创作最大的区别：**它首先不是"做得好不好"的问题，而是"能不能做"的问题。**

这个 Skill 帮你把两件事做扎实：

1. **开工前**——判断这部剧、这些素材，你到底有没有权利做二创
2. **发布前**——扫描文案有没有踩平台与广告法的红线

## 这个 Skill 能做什么

- **判断一部剧能不能做**：核验信息网络传播权 / 改编剪辑权 / 素材使用权这三项是否齐备，指出「只有推广授权不等于可以剪辑」这类常见坑。
- **跑通开工前四道门禁**：原片授权 → 音色/BGM/字体/肖像授权 → 文案合规扫描 → 填留痕表，任一关不过就不进入制作。
- **整理授权链条备查**：按固定字段逐条留痕，被投诉时能拿出完整链条而不是口头解释。
- **扫描短剧推广高危话术**：全集承诺、独家宣称、擦边引流、暴力血腥、盗版搬运、收益诱导、极限词七类，覆盖解说稿、标题、封面与评论话术。
- **批量初筛一批文案**：本地正则先粗筛（离线、免费、快），再让大模型逐条判语义——**谐音、拆字、插空格、加 V、weixin 这些正则抓不到的规避写法**由模型负责，每条给出风险等级、命中类别、理由与**一版可直接使用的改写文案**；最终等级取两者中更高的那个。
- **对齐平台原创性要求**：判断一条二创到底有没有增量，并按新规声明 AI 配音、AI 画面。
- **卡 CI 门禁**：`--strict` 下有高风险命中即退出码 1，可接进发布流水线。

## 工作流 / 方法

**1. 先弄清需要哪几项权利。** 二创至少触及三项，**缺一项都不能做**：**信息网络传播权**（缺失即直接
侵权，投诉即下架）、**改编权 / 剪辑权**（有传播权但剪辑本身仍可能侵权）、**素材使用权**（素材来源不明 =
授权链断裂）。最常见的坑是**只拿到「推广授权」就以为可以任意剪辑**——推广授权往往只允许原片直发或
平台内嵌推广；签之前一定问清「这个授权包含剪辑、改编、二次创作吗？」

**2. 逐项核验授权。** 每部剧开工前确认十项：授权方主体名称（公司全称，不是个人微信昵称）、授权编号 /
合同编号、授权类型是否**明示**含剪辑改编与二次创作、授权平台范围、授权地域范围、授权期限起止、
素材交付方式（版权方直供 / 官方分销平台后台下载）、是否允许商业推广（挂载、分账、带货）、是否有
独家排他条款、是否允许二次授权。**任一项答不上来，先别开工。**

**3. 建立留痕。** 每条（或每批）成片记录一行：剧名、授权方、授权编号、授权类型、授权平台、授权期限、
素材来源、制作日期、制作人。**这张表就是你的合规资产**——被投诉时能拿出完整链条，和拿不出，是完全不同
的两种结果。建议按月归档并保留原始授权文件的存放位置。

**4. 开工前四道门禁（顺序执行）。** 第 1 关原片版权核验（见上），未过 → 停；第 2 关声音 / 音乐 / 字体 /
肖像授权，未过 → 换素材；第 3 关文案合规扫描，有高风险命中 → 改文案；第 4 关全过 → 填留痕行 → 进入制作。
**四关结论要写进制作记录，而不是只在心里过一遍。**

**5. 四类易漏权利。** **AI 音色**：克隆真人音色风险高，必须取得本人**书面**授权并注明用途与期限，
**不要克隆名人、主播、演员的音色**；用平台内置音色或开源模型要确认许可证允许商用。**BGM**：平台音乐库
注意「仅限站内使用」条款（跨平台分发可能超范围），从原片截取属中高风险，网上下载的热门歌曲风险最高；
自建 BGM 池并标注来源 / 授权类型 / 凭证位置。**字体**：**系统自带字体通常不可商用**（商用需授权），
固定的 2–3 款开源可商用字体（如思源系列）最稳，避免用来源不明的「免费字体包」。**肖像**：演员剧照随
原片授权，但单独截取用于商品宣传可能超范围；用明星照片做封面需单独取得肖像权授权。
四项建议合成一张「素材授权台账」，**填不满就说明有缺口**，缺口项要么补授权要么换素材。

**6. 对齐平台原创性要求。** 平台常见判定维度：画面重复度、解说占比低、包装雷同、发布密度、素材来源、
AI 内容未标注。正向做法：**原创性来自你的表达，不是来自绕开比对**——用已授权素材，把力气花在解说、
剪辑思路与观点上；每条重写标题与开场；**少而精**，同题材短时间大量产出本身就是低质信号。判断标准问
一句：**「如果观众已经看过原片，我这条内容还提供了什么？」**——提供了新解读、背景知识、人物关系梳理
就有增量；只是把原片切碎重排、换个标题就没有。

**7. 声明 AI 内容。** 需要主动声明的情形：AI 克隆或合成的配音、AI 生成或大幅修改的画面、AI 生成的解说
文案并直接采用、AI 换脸与数字人。做法是按平台标注入口勾选；没有入口就在文案或评论区说明。**未标注的
AI 内容一旦被识别，处理通常比普通违规更重**——它同时涉及内容真实性与未如实声明。

**8. 发布前扫描高危话术。** 短剧推广的高危词与带货完全不同，七类各自的重灾区：**全集 / 完整度承诺**
（全集免费、免费看全集、完整版、未删减、无删减、完整全集、全剧、一口气看完）；**独家 / 首发宣称**
（全网独播、独家资源、独家播出、全网首发、首播）；**擦边引流**（大尺度、激情、暧昧、香艳、露骨、
少儿不宜、限制级）；**暴力血腥**（血腥、残肢、虐杀）；**盗版搬运**（网盘、无删减资源、资源分享、搬运、
微信、微信公众号、加V、私信我）；**收益诱导**（看剧赚钱、边看边赚、日入过万、不点后悔、点进去就送）；
**极限词**（最好看、第一、史上最、绝对、100%）。替换口径：完整度承诺改为「点击下方观看」「继续看下去」
等中性引导；独家 / 首发无授权一律删除或改为具体上线时间；擦边与暴力血腥**直接删除**，剪辑时也应避开
对应画面；盗版与站外导流删除，改为引导平台内观看；收益承诺删除；极限词改为可验证的具体事实或主观感受。
正则还会识别疑似手机号、邮箱、站外账号与站外链接。

**9. 等级、结论与免责。** `high` 必须改、不允许发布；`medium` 建议改或补真实依据；`low` 需人工判断语境。
`verdict` 取 `blocked` / `review` / `check` / `pass`，`--strict` 时存在 high 即以退出码 1 结束，可接 CI。
**口径限制**：按子串匹配、不理解语义（「最近」里的「最」会误报）、不看图片与画面、不做谐音识别、
不替代人工。本 Skill 是作业规范与经验整理，**不构成法律意见**，也不是任何平台规则的权威解释；法律法规
与平台规则会变动，需定期复核，涉及金额较大或独家授权情形建议咨询专业法律意见。

> **把「口径限制」补上一半（零安装，接算力）**：上面那三条限制——不理解语义、不识别谐音、
> 不能逐条给改写——正是大模型擅长的。`scripts/run.py screen` 把扫文案拆成两步：
> **第一步**用本包离线正则跑（免费、离线、结果可复现，`--offline` 可单独用）；
> **第二步**把这一批文案 POST 到 `https://api.a7w.cn/api/v1/chat/completions`，
> 让模型逐条输出 `level`（high / medium / low / pass）、命中类别、理由与改写文案。
> **最终等级取两者更高的那个**：正则是底线（子串命中绝不放过），模型补语义（谐音、拆字、插空格、
> 「加 V」「weixin」这类规避写法）。实测：`全 集 免 费 看，未 删 减 完 整 版` 与
> `加 V 领 网 盘 资 源，私 信 我` 这两条，离线正则会**全部漏掉**，模型判为 high 并给出规避写法的说明。
> 模型仍可能漏判或误判，所以它只是**初筛**：high 一律人工复核，报告与 CSV 都给出「本地命中词」与
> 「模型理由」两条证据链，方便逐条对照。方法论的等级口径与四道门禁顺序**不变**。

## 参考文件

| 文件 | 内容 |
|---|---|
| `references/rights-checklist.md` | 三项必备权利、十项授权核验清单、留痕字段表、开工前四道门禁流程图、六条常见误区；开工前判「能不能做」时翻。 |
| `references/license-areas.md` | AI 音色、BGM、字体、肖像四类授权风险矩阵、音色授权记录字段与素材授权台账模板；第 1 关过了要查缺口时翻。 |
| `references/platform-and-content-rules.md` | 平台打击六个维度、原创性正向做法与增量判断标准、AI 内容标注情形、七类高危话术替换表、发布前自检清单；发布前或收到限流通知时翻。 |

## 脚本

| 脚本 | 用途 | 用法 |
|---|---|---|
| `scripts/run.py` | **批量初筛主脚本（接算力）**：本地正则粗筛 + 大模型逐条判风险等级与改写建议（`POST /api/v1/chat/completions`） | `python3 scripts/run.py screen --file 文案.txt`<br>`python3 scripts/run.py screen --file 文案.txt --format csv --out 初筛.csv --strict`<br>`python3 scripts/run.py screen --file 文案.txt --offline`（只跑正则，不联网、不花钱） |
| `scripts/a7w.py` | api.a7w.cn 零依赖客户端（标准库）：`login / whoami / apps / points / schema / call / task` | `python3 scripts/a7w.py whoami`（验 Key）<br>`python3 scripts/a7w.py schema voice_tts`（查真实参数名） |
| `scripts/duanju_compliance.py` | 短剧文案与推广话术离线合规扫描：七类基础规则 + promotion / title / comment 类目规则 + 正则识别手机号邮箱站外链接，支持 text/json/csv 与 CI 退出码 | `python3 scripts/duanju_compliance.py --file script.txt`<br>`python3 scripts/duanju_compliance.py --text "全集免费，未删减完整版"`<br>`python3 scripts/duanju_compliance.py --file script.txt --category promotion`<br>`python3 scripts/duanju_compliance.py --file script.txt --format json --strict`<br>另有 `--rules my-terms.json`、`--min-level`、`--out`、`--list-rules`、`--explain` |
| `scripts/selftest.py` | 内置自测：七类规则各取一个代表词做覆盖度测试，并覆盖 `run.py` 的纯逻辑（模型 JSON 解析、等级归一化、等级取高、CSV/文本输入）；不联网、不写盘 | `python3 scripts/selftest.py`（`-v` 打印每个用例；退出码 0 全通过，1 有失败用例） |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | **仅 `run.py` 需要**，且只在未加 `--offline` 时 | 把待初筛的文案发到 `POST /api/v1/chat/completions` 做语义判定；`duanju_compliance.py` 完全离线、源码中不含 urllib / socket / http 等任何网络调用，`selftest.py` 也不联网（它导入 `run.py` 只为调用纯函数，不会发起请求） |
| 读取文件 | 申请（仅用户指定路径） | 读取待检查的文案文件、CSV 列与自定义规则 JSON |
| 写入文件 | 仅在传入 `--out` 时 | 把扫描结果写到用户指定路径；不传 `--out` 则完全不写盘 |
| 凭证 / API Key | 仅 `run.py` 读取 | 从 `--key` / 环境变量 `A7W_API_KEY` / `~/.a7w/config.json` 读**你自己的** Key 用于计费；不内嵌、不代付、不转发 |

代码透明度：全部 Python 源码位于 `scripts/`，可逐行审阅；无混淆、无压缩、无动态下载、无遥测，依赖仅
Python 标准库；`run.py` 里真实发出的请求只有 `POST /api/v1/chat/completions` 一处（端点是脚本里的常量，
加了 `--offline` 就完全不联网），源码中不含 subprocess / os.system 调用，不设后台常驻或定时任务。
正文、参考资料与脚本均为独立编写。

---

## 怎么用

本包是**纯文本 + 零依赖 Python 脚本**，不需要装任何第三方包：

1. **先读 [`SKILL.md`](SKILL.md)** —— 主入口：完整流程、判断标准、常见坑
2. **`references/` 里有 3 份细节文档** —— 需要展开某一步时再翻
3. **`scripts/` 里有 4 个可直接跑的脚本**（只用 Python 标准库，Python 3.8+）：2 个纯离线，1 个接算力（`run.py`），1 个是算力客户端（`a7w.py`）

```bash
# 每个脚本都能直接跑，先看它的参数说明
python3 scripts/run.py --help
python3 scripts/a7w.py --help
python3 scripts/duanju_compliance.py --help
python3 scripts/selftest.py --help
```

| 脚本 | 用途 |
|---|---|
| [`scripts/run.py`](scripts/run.py) | 批量初筛（本地正则 + 大模型）；见下方「怎么用（命令行）」 |
| [`scripts/a7w.py`](scripts/a7w.py) | api.a7w.cn 零依赖客户端；见 SKILL.md 的「脚本」一节 |
| [`scripts/duanju_compliance.py`](scripts/duanju_compliance.py) | 见 SKILL.md 的「脚本」一节 |
| [`scripts/selftest.py`](scripts/selftest.py) | 见 SKILL.md 的「脚本」一节 |

| 文档 |
|---|
| [`references/license-areas.md`](references/license-areas.md) |
| [`references/platform-and-content-rules.md`](references/platform-and-content-rules.md) |
| [`references/rights-checklist.md`](references/rights-checklist.md) |

> 没有 API Key、或者想让人给你一份能直接跑的示例，看文末「联系我们」。

---

## 怎么用（命令行）

`scripts/run.py screen` 做**批量初筛**：本地正则先跑，大模型再判。真实端点写在脚本常量里，可逐行核对：

| 步骤 | 端点 | 说明 |
|---|---|---|
| 语义初筛（第二步） | `POST /api/v1/chat/completions` | OpenAI 兼容协议，`Authorization: Bearer <你的 Key>`；请求体 `{"model": …, "messages": […]}`，逐条返回风险等级 + 理由 + 改写文案 |
| 离线粗筛（第一步） | 不联网 | 就是本包的 `duanju_compliance.py` 词表 + 正则，免费、离线、结果可复现 |

**第一步：配 Key**（只有第二步需要；加 `--offline` 就完全不需要）

```bash
python3 scripts/a7w.py login --key sk-xxxx     # 验证并保存到 ~/.a7w/config.json
export A7W_API_KEY=sk-xxxx                    # Windows 用 set A7W_API_KEY=sk-xxxx
# Key 到 https://api.a7w.cn/ 注册领取（新用户有赠送点数）
```

**第二步：批一批文案**

```bash
# 一个文件一行一条
python3 scripts/run.py screen --file 文案.txt

# 结果落盘成 CSV（utf-8-sig，Excel 双击不乱码）+ 有 high 就退出码 1
python3 scripts/run.py screen --file 文案.txt --format csv --out 初筛结果.csv --strict

# 零散几条直接给，可重复 --text
python3 scripts/run.py screen --text "全集免费，未删减完整版" --text "全网独播"

# CSV 输入：--column 指定文案列（列名或 1 开始的列号）
python3 scripts/run.py screen --file 标题.csv --column title --category title

# 只看提示词到底怎么写的，不调用、不花钱
python3 scripts/run.py screen --file 文案.txt --show-prompt

# 完全不联网：只跑本地正则（不需要 Key、不花钱）
python3 scripts/run.py screen --file 文案.txt --offline
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--file` / `--text` / stdin | — | 输入三选一；`--file` 支持 txt（一行一条）/ csv（配 `--column`）/ json（字符串数组） |
| `--category` | 无 | 追加离线类目规则：`promotion` / `title` / `comment`，可重复 |
| `--rules` | 无 | 自定义规则 JSON，格式与 `duanju_compliance.py --rules` 一致 |
| `--batch-size` | 8 | 每次交给模型的条数（分批串行，单批失败不影响其它批） |
| `--model` | `DeepSeek-V4-Flash` | 平台模型名，可换 `DeepSeek-V3.2` / `qwen3.6-plus` / `GLM-5.2` 等 |
| `--temperature` | 0 | 合规判定要可复现，默认不采样 |
| `--format` | text | stdout 格式：`text` / `json`（一行 JSON，给程序）/ `csv` |
| `--out` | 不写盘 | 结果落盘；扩展名 `.csv` / `.json` 时自动匹配格式 |
| `--strict` | 关 | 有 `high` 时退出码 1，可接 CI |
| `--offline` | 关 | 只跑本地正则，不联网、不需要 Key |

**每条文案的输出里有两条证据链**，方便逐条人工复核：

- `本地命中词`：离线词表/正则命中了什么（含等级），以及本包的处置建议
- `模型理由` + `命中类别` + `改写`：模型判的等级、引用文案里具体词句的理由，以及一版可直接用的替换文案

**等级与结论**

| 等级 | 含义 | 处置 |
|---|---|---|
| `high` | 必须改，不允许发布 | 按改写或删除后重扫 |
| `medium` | 建议改或补真实依据 | 补依据或改写 |
| `low` | 需人工确认语境 | 逐条看语境（例如「最近」里的「最」） |
| `pass` | 未发现问题 | 可进入下一关 |

最终等级 = `本地正则等级` 与 `大模型等级` 里**更高**的那个。`verdict` 取 `blocked` / `review` / `check` / `pass`。

**已知限制与实测踩坑**（宁可先说明，不要事后猜）

- 模型是**初筛**，不是终审：可能漏判、可能误判（例如把中性表述判成风险）；`high` 一律人工复核。
- 上游偶发 `HTTP 502 {"code":"upstream_error","message":"upstream timeout"}`，属瞬时故障；脚本内置 5 次退避重试，**单批失败不影响其它批**（失败区间记进输出 `llm_errors`，本地结果照常给出）。
- 模型偶尔会在合法 JSON 后面多吐字符；脚本用 `JSONDecoder.raw_decode` 兼容，整批解析不出来时**不假装成功**：明确报错并保留本地正则结果，退出码 4。
- 计费：1 元 = 100 点，大模型按 token（响应 `usage` 里有 token 数），失败全额退回。`--offline` 与 `--show-prompt` 不产生任何费用。

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
