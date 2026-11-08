# 医疗合规素材 一条 9.35 元 · 出片前先过合规

**一条 30 秒医美短视频 9.35 元，合规检查 0 元。** 走 [api.a7w.cn](https://api.a7w.cn/) 的四条接口：出图 `gpt-image-2.6`、配音 `voice_tts`、口播 `pic_lipsync`、成片 `full_video`。零依赖，只用 Python 标准库。

这个包的顺序和别的包相反：**先合规，再花钱**。文案在本地扫 15 类红线表述、补齐 6 项必标，过了才允许调接口。改文案 0 元，重出一条 9.35 元。

---

## 为什么需要这一层

医美、口腔、健康管理的内容，最贵的不是出片，是**发错了被罚、被下架、被要求删稿重拍**。而真正会踩的坑集中在三处：

- 口播稿里一句「一次见效」或「永久不反弹」，就属于疗效保证性承诺；
- 片子为了好看剪了「术前术后」，属于以患者形象作效果对比；
- 图片是 AI 生成的，画面却在暗示「做完就是这样」，属于以 AI 示意疗效。

这三类都不是「再改一版文案」能解决的，是重拍。所以本包把这三类做成**一票否决**：命中就退出口码 2，**一个请求都不发**。

---

## 合规检查器（`check`，纯本地 0 点）

15 类表述、226 条词与正则，分两级：

| 级别 | 类别 | 处理 |
|---|---|---|
| 一票否决（9 类） | 疗效承诺 / 疗效数据 / 术前术后 / 患者名义 / 绝对化 / 容貌焦虑 / 未成年人 / 免费 0 元引流 / AI 作疗效示意 | 命中即拦，退 2 |
| 待改写（6 类） | 低价引流 / 代言背书 / 疾病药品 / 进口资质 / 名词炒作 / 分期诱导 | 打印替代写法，可继续 |

```bash
python3 scripts/run.py check --text "一次见效，永久不反弹，有效率 98%，术前术后对比" --asset video --review
```

输出会给到「哪一类、命中原句、第几个字、改成什么」。同时检查 6 项必标：执业许可证登记号、广告审查文号、广告标识、风险提示、机构全称与项目、项目与价格；`--asset image|video` 时再加一项「AI 生成素材标识」。

```
  一票否决（9 类）：3 条
    × 疗效承诺  命中「一次见效、永久」  第 1 字
        改成：「按疗程评估，效果因人而异」，把结论交给面诊与个体差异
  必标项：0/6
    × 医疗广告审查证明文号
        补：医疗广告审查证明文号（X）医广【2026】第 03-15-0123 号
```

`--strict` 把待改写与必标缺失也升级成拦截，适合发布前最后一跑。

---

## 价格（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 出图 | `POST /api/v1/images/generations` | **6 点/张**（与尺寸、格式无关） |
| 配音 | `POST /api/v1/apps/voice_tts/tts` | 约 **0.18 点/字** |
| 图片口播 | `POST /api/v1/apps/pic_lipsync/submit` | **15 点/秒** |
| 成片 | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒 |
| 上传 | `POST /api/v1/upload` | **0 点**（cost:0） |
| 查任务 | `GET /api/v1/tasks/<task_id>` | **0 点** |
| 合规检查 | `check` / `checklist` | **0 点、0 请求** |

一单 30 秒 = 935 点 = 9.35 元；一天 3 条 = 2,805 点 = 28.05 元；一周 15 条 = 14,025 点 = 140.25 元。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key        # Windows: $env:A7W_API_KEY="sk-你的key"
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费：自检、算钱、过合规、拿必标模板
python3 scripts/run.py doctor
python3 scripts/run.py cost --avatar-seconds 20 --broll-seconds 10
python3 scripts/run.py check --file 口播稿.txt --asset video --review
python3 scripts/run.py checklist

# 3) 按交付清单花钱
python3 scripts/run.py image --prompt "暖光诊室前台，浅色木质，绿植，无人物" --n 4 --yes
```

`doctor` 会打印 12 项检查，并且在跑之前和跑之后各读一次流水 —— **两次一致就证明本轮 0 点**。

---

## 用法示例

```bash
# 只改文案，先看命中什么（0 点）
python3 scripts/run.py check --text "水光项目，一次见效，永久不反弹" --asset video

# 4 张环境图（24 点）
python3 scripts/run.py image --prompt "诊室器械托盘特写，不锈钢，浅景深，无人物" --n 4 --yes

# 旁白 60 字（约 11 点）
python3 scripts/run.py tts --text "水光项目单次 680 元，含麻醉与复诊，效果因人而异。" --yes

# 医师形象口播 20 秒（300 点）
python3 scripts/run.py lipsync --image 医师.png \
    --voice-url "https://oss.gpu.likeadmin.cn/openapi/…" \
    --text "水光项目单次 680 元，含麻醉与复诊，效果因人而异。" --seconds 20 --yes

# 空镜 10 秒 1080P（600 点，AI 标识默认留在画面里）
python3 scripts/run.py video --text "竖屏空镜：暖光诊室横移，器械托盘特写，无人物" \
    --seconds 10 --resolution 1080P --yes

# 只看请求不花钱
python3 scripts/run.py video --text "暖光诊室横移" --seconds 10 --dry-run
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--asset` | `copy` | `copy` / `image` / `video` / `voice`；image、video 加查 AI 标识 |
| `--text` / `--file` | — | `check` 的输入，二选一 |
| `--n` | 1 | 出图张数 **1–4** |
| `--seconds` | 20（口播）/ 10（成片） | 口播秒数；成片单段 **4–15 秒** |
| `--resolution` | `1080P` | `480P` / `768P` / `1080P` / `2K` / `4K` |
| `--quality` | `standard` | 口播档位 `standard` / `fast` / `max` |
| `--no-aigc-mark` | — | 关掉画面里的 AI 生成标识（默认开着） |
| `--budget` | 5000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |
| `--strict` / `--review` | — | 严格拦截 / 带上人工复核 8 条 |

---

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 四条能力 + 现查单价 + 平台尺寸 + 7 项交付 |
| `cost` | 免费 | 一条 / 一天 3 条 / 一周 15 条要多少钱 |
| `check` | 免费 | 15 类表述 + 6 项必标，命中给替代写法 |
| `checklist` | 免费 | 必标模板 + 人工复核 8 条 + 交付清单 7 项 |
| `doctor` | 免费 | 自检 Key / 应用 / 价目 / 5 个端点，前后比对流水 |
| `upload` | 免费 | 图 / 音频转白名单地址 |
| `image` | **6 点/张** | 环境 / 器械 / 空间图 |
| `tts` | **约 0.18 点/字** | 旁白、片头片尾口播 |
| `lipsync` | **15 点/秒** | 医师形象口播（text 模式） |
| `video` | **按秒 x 分辨率** | 空镜 / 整片 |
| `status` | 免费 | 查任务（轮询只走这条） |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错，或合规未过 —— **一个请求都不发** |
| `3` | 自检未过 |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 响应里没有产物 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "mode": "image", "model": "gpt-image-2.6", "requested": 4,
 "returned": 4, "files": ["…/20261108_img-01.png"], "billedPoints": 24,
 "complianceMissing": ["医疗机构执业许可证登记号"]}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-medical-compliance/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（文档 + 现查价目 + 实测）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 实测记录

```
2026-11-08  只读与探针（本轮真实花费 0 点）
  GET  /api/v1/pricing      115 个键；full_video 五档与本地一致
  GET  /api/v1/apps         22 个应用；pic_lipsync submit/query 都在
  POST /images/generations  {"model":"gpt-image-2.6","prompt":""} → 422，0 点
  POST /video/viapi/enhance {} → 400 empty_url，0 点
  GET  /tasks/<假 id>       200「任务不存在」，0 点
  POST /upload（无 file）    200「请使用 file 字段提交一个文件」，0 点
  流水前后一致：最近一笔仍是 01:46:12 的 -6（sync:/api/v1/images/generations）
```

---

## 免责

- 合规检查是**机检辅助**，替代不了机构法务与属地卫健、市场监管的审查口径；发布前请走 `checklist` 里的人工复核 8 条并签字。
- 真实扣费以接口返回的 `usage.points_cost` 为准，`cost` 给的是预估。
- 生成内容的合规责任在使用者：用于伪造他人身份、侵权素材或违法用途时的后果自负。

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
