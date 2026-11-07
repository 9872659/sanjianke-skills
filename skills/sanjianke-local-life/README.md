# 本地生活视频 一天 5 条门店矩阵

**一天 5 条门店探店片，76 元。** 门头 3 秒抓同城刷到的人，环境交代「几个人来合适」，招牌菜怼馋点，价格摆出团购与单点的差，最后一句行动号召落到 POI 和团购链接。

一个门店一天正好五条，五个角度轮着发：**门头钩子、招牌菜特写、价格锚点、老板出镜、老客回头**。

---

## 一个门店一天要交什么

| # | 交付物 | 规格 | 数量 | 命名 |
|---|---|---|---|---|
| 1 | 竖版成片 | 1080x1920 / H.264 / 25 秒 / 9:16 | 5 | `20261108_老灶门火锅_01_门头_dy_25s.mp4` |
| 2 | 封面图 | 1080x1440 / 3:4 / png | 5 | `*_01_cover.png` |
| 3 | 口播音频 | mp3 / 44.1kHz / 单条 20~30 秒 | 5 | `*_01_voice.mp3` |
| 4 | 团购文案 | 标题 3 条 + 卖点 3 条 + 价格锚 1 条 | 5 组 | `文案.md` |
| 5 | 同城标签 | 抖音 6 个 / 小红书 6 个 | 5 组 | `文案.md` |
| 6 | 配乐 | 一首 30 秒循环 | 1 | `bgm.mp3` |
| 7 | 当天交付单 | 拍摄 / 剪辑 / 发布状态 | 1 | `当天交付单.md` |

`plan` 一条命令把 7 项里的**脚本部分**全部写好（五段分镜、口播、3 条标题、团购文案、6 个同城标签、封面 prompt、文件命名），落在 `~/.a7w/local-life/<城市>-<日期>/`，纯本地、不联网、0 点。

---

## 这个包和底层能力包的分工

| 你手上要的东西 | 用哪个包 | 它交付什么 |
|---|---|---|
| 一张门店图 / 菜品图 | `sanjianke-gpt-image` | 6 点一张，文生图 / 图生图 / GIF |
| 一段 4~15 秒的镜头 | `a7w-full-video` | 首帧 + 运镜，按秒 x 分辨率计费 |
| 一条口播 | `a7w-voice-tts` | 同步 tts / 长文 tts_async / 克隆音色 |
| 一首配乐 | `a7w-music-generation` | Suno 线接口与参数表 |
| 同城爆款的结构拆解 | `sanjianke-ecom-spy` | 搜索 + 标题公式 + 分镜骨架 |
| **一个门店一天要交的 5 条片 + 5 张封面 + 5 条口播 + 团购文案 + 标签 + 交付单** | **本包** | 岗位流程、五段结构、文案模板、合规检查、成本单 |

底层包做单步，本包做「一个岗位一天要交的东西」：先在本地把 5 条的角度、口播、文案、标签、命名排好，再决定哪几条值得花钱。

---

## 探店 25 秒的五段结构

| 时间 | 段落 | 画面 | 口播干什么 |
|---|---|---|---|
| 0-3 秒 | 门头 | 街边推到招牌，门口排队或热气 | 一句话报店名和位置，让人知道在哪条街 |
| 3-8 秒 | 环境 | 推门进店，桌椅、明档、后厨窗口 | 说清楚几个人来合适、要不要等位 |
| 8-16 秒 | 招牌菜 | 出锅特写，筷子夹起、拉丝、汤滚 | 报菜名 + 份量，这一段决定完播 |
| 16-22 秒 | 价格 | 团购页 + 菜量对比 + 账单 | 报团购价与单点差价，差价就是转化理由 |
| 22-25 秒 | 行动号召 | 招牌定格 + POI 定位 | 报口令、指左下角、说可用时间窗 |

秒数按比例分配，`--seconds 30` 或 `45` 时五段自动缩放，不用手改脚本。

---

## 价目表（1 元 = 100 点，2026-11-08 现查 `GET /api/v1/pricing`）

| 工序 | 接口 | 单价 |
|---|---|---|
| 同城参考 | `POST /api/v1/apps/watermark_removal/douyin_search_video` | **100 点/次**（flat，失败亦计） |
| 出图 | `POST /api/v1/images/generations` | **6 点/张** |
| 口播 | `POST /api/v1/apps/voice_tts/tts` | 约 **0.18 点/字**（上游真实点数 x 3） |
| 配乐 | `POST /api/v1/apps/media_services_33/music_generate` | **50 点起/首**（上游 x 2，保底 50） |
| 成片 | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / **1080P 60** / 2K 80 / 4K 80 点/秒 |
| 查进度 | `GET /api/v1/tasks/<task_id>` | **0 点** |
| 传图 | `POST /api/v1/upload` | **0 点** |
| 脚本 / 检查 | `plan` / `qc`（纯本地） | **0 点** |

### 一条 25 秒多少钱

| 分辨率 | 单条成片 | 一天 5 条（含封面 + 口播 + 配乐） |
|---|---|---|
| 480P | 350 点 = 3.50 元 | 1,911 点 ≈ 19.11 元 |
| 768P | 700 点 = 7.00 元 | 3,661 点 ≈ 36.61 元 |
| **1080P** | **1,500 点 = 15.00 元** | **7,661 点 ≈ 76.61 元** |

`full_video` 单段 4~15 秒，25 秒拆成 15 + 10 两段提交，按总秒数计费；`--shops 3` 就是三家店 15 条，成本按条线性放大。

---

## 快速开始

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 2) 免费：自检 + 算钱
python3 scripts/run.py doctor
python3 scripts/run.py cost --shops 1 --seconds 25 --resolution 1080P

# 3) 免费：出当天脚本与交付单，再过一遍合规
python3 scripts/run.py plan --shop "老灶门火锅" --city 成都 --district 春熙路 \
    --category 火锅 --dish "牛油锅底" --price 88 --offer "双人餐"
python3 scripts/run.py qc --plan ~/.a7w/local-life/成都-20261108/plan.json

# 4) 按交付单花钱
python3 scripts/run.py shop  --kind cover --shop "老灶门火锅" --dish "牛油锅底" --yes
python3 scripts/run.py voice --text "在成都春熙路，这家老灶门火锅……" --yes
python3 scripts/run.py music --style "轻快城市探店 vlog" --yes
python3 scripts/run.py film  --text "竖屏探店，门头推到招牌……" --image cover-01.png --yes
python3 scripts/run.py status --task-id tsk_xxx
```

---

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 八个动作 + 端点 + 现查单价 |
| `cost --shops 3 --per-shop 5` | 免费 | 三家店 15 条要多少钱 |
| `plan --shop "A" --shop "B"` | 免费 | 多店矩阵，一次出全部脚本与交付单 |
| `qc --plan plan.json` | 免费 | 五道合规：绝对化用语 / 价格 / 标签 / 行动号召 / 时长 |
| `ref --keyword "成都 火锅 探店"` | **100 点/次** | 同城爆款，看时长分布与钩子词 |
| `shop --kind dish --n 2` | **6 点/张** | 招牌菜图、门头图、团购封面 |
| `voice --script 口播.txt` | **约 0.18 点/字** | 口播，500 字内一条 |
| `music --style "…"` | **50 点起** | 30 秒循环配乐 |
| `film --seconds 15` | **按秒** | 单段成片，首帧图自动 upload |
| `upload --file cover.png` | 免费 | 换 `oss.gpu.likeadmin.cn` 白名单地址 |
| `log` | 免费 | 本地台账 |

**不加 `--yes` 退 `4`** 并告诉你这次要花多少点；**预计点数超 `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 6000 = 60 元）。

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--shop` | 必填（`plan`） | 门店名，可重复给多家店 |
| `--city` / `--district` / `--category` | 成都 / 春熙路 / 火锅 | 同城标签与文案的城市字段 |
| `--dish` / `--price` / `--offer` | 招牌锅底 / 88 / 双人餐 | 招牌菜、团购价（元）、团购内容 |
| `--bonus` / `--window` / `--years` | 一份冰粉 / 21:00 / 5 | 到店赠品、团购时间窗、开店年数 |
| `--per-shop` | 5 | 每家店几条（1~5） |
| `--seconds` | 25 | 单条时长；`film` 单段 4~15 |
| `--resolution` | 1080P | 480P / 768P / 1080P / 2K / 4K |
| `--kind` | cover | storefront / dish / cover / environment |
| `--budget` | 6000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺 `--shop` / `--text`、秒数越界、选项缩写） |
| `3` | 自检或合规检查没过 |
| `4` | 需要确认 —— 没给 `--yes` |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档；`--json` 写在子命令前后都可以。

---

## 文件结构

```
sanjianke-local-life/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文 + 计费口径）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

运行时产生的脚本、封面、稿子都落在 `~/.a7w/local-life/`，不往包目录里写。

---

## 三条用钱换来的规矩

**一、轮询一次就是一次的钱。** 应用层的 `/query` 每查一次按该应用单价结算，`nano_banana/query` 实测 72 点/次。本包只打 `GET /api/v1/tasks/<id>`，价目表里这条是 cost:0，等十分钟也是 0 点。

**二、`GET /api/v1/apps/<app>` 是收费的。** 它命中 `/api/v1/apps/<app>/*` 的通配计价，按该应用 flat 单价即时扣费、不退（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔）。要目录只看 `/api/v1/apps` 列表和 `/api/v1/pricing`，两条都是 cost:0。

**三、首帧图有域名白名单。** 外站地址一律 400 `url_not_allowed`，只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/。`film --image 本地图.png` 会自动先 `POST /api/v1/upload`（免费）换地址。

---

## 合规检查（`qc` 已经做成默认动作）

- **宣传语用可验证描述**：「牛油锅底现熬 4 小时」比「全城第一」更稳，也更有画面。
- **价格三处对齐**：口播里的数字、团购标题、菜单实价保持一致。
- **门店信息对齐**：地址、营业时间、电话与平台 POI 一致，导航搜得到。
- **同城标签六个**：城市 + 商圈 + 品类 + 店名 + 招牌菜 + 团购，抖音与小红书各一组。
- **素材来源**：门店自有素材优先；同城爆款只借结构，画面自己拍。
- **背景音乐**：用授权曲库，或用本包 `music` 生成的配乐。
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
