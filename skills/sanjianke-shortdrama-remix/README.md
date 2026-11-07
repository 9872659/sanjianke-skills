# 短剧二创一条龙

> **一条 60 秒短剧素材，从认演员表到出二创成片，六个工位一条命令跑完：1,796 点 = 17.96 元。**

二创作者拿到一集短剧，真正要干的活是固定的：先认演员表和硬字幕，再擦掉台标与原字幕，把画质提一档，配一段解说，最后套模板混剪成片。这六步以前要开六个页面、抄六个 taskId、手动把上一步的成片地址贴给下一步。

本包把它们串成一条链：**每一步都能单独跑，一条命令也能全跑完**。走 `api.a7w.cn`，异步两步（提交拿 taskId → 轮询取结果），零依赖、只用 Python 标准库。

## 价目表（1 元 = 100 点，取自 `GET /api/v1/pricing`）

| 工位 | `--step` | 单价 | 60 秒片 | 干什么 |
|---|---|---|---|---|
| 认演员表 / 硬字幕 OCR | `castcrew` | **25 点/次** | 25 点 | 抽硬字幕与滚动演职员表，附 SRT |
| 去台标 / Logo | `delogo` | **25 点/次** | 25 点 | 擦台标、平台 logo，最多 2 个区域 |
| 擦硬字幕 | `subtitle` | **9 点/秒** | 540 点 | 把原片硬字幕抹干净，换字幕第一步 |
| 画质提一档 | `enhance` | 15 点/秒 | 900 点 | 清晰度 / 对比度 / 细节整体提一档 |
| 解说配音 | `tts` | 上游 ×3（约 0.18 点/字） | 200 字 = 36 点 | 长文本异步合成，出解说音频 |
| 模板混剪成片 | `mixcut` | 4.5 点/秒（保底 45） | 270 点 | 按模板把素材与解说拼成成片 |

一趟 60 秒片 + 200 字解说：**25 + 25 + 540 + 900 + 36 + 270 = 1,796 点 = 17.96 元**。

只想要其中一步也划算：单擦字幕 60 秒 540 点（5.40 元），单提画质 900 点（9 元），单去台标 25 点（0.25 元）。

## 六个工位怎么串

```
素材.mp4
  │  POST /api/v1/upload（免费，multipart 字段名 file）
  ▼
oss.gpu.likeadmin.cn/openapi/…（白名单地址，最长 24 小时）
  │
  ├─→ castcrew  25 点/次  → 演员表 + SRT（旁路，不改主视频）
  ├─→ delogo    25 点/次  → 无台标视频
  ├─→ subtitle   9 点/秒  → 无硬字幕视频
  ├─→ enhance   15 点/秒  → 高清视频
  ├─→ tts       上游×3    → 解说音频（--text）
  └─→ mixcut   4.5 点/秒  → 最终成片（--style-id + 高清视频 + 解说音频）
```

- **单步**：`run --step subtitle --video-url "上一步的成片" --yes`
- **全链**：`run --all --file 素材.mp4 --script "解说词" --style-id <模板> --yes`
- **跳过**：`--skip castcrew,tts`（只跑想跑的工位）

`--all` 会把上一步拿到的 `videoUrl` 自动接给下一步；`castcrew` 只出 SRT，主视频仍然从原片继续走 `delogo`。

## 三步上手

```bash
# 1) 填 Key（不内嵌任何 Key，用你自己的）
python3 scripts/a7w.py login --key sk-你的key

# 2) 自检（免费，不扣点）
python3 scripts/run.py doctor

# 3) 先算钱，再跑
python3 scripts/run.py cost --seconds 60 --chars 200
python3 scripts/run.py run --all --file 素材.mp4 --script "解说词" \
    --style-id 6ac8981c20d5010033eee1b7 --yes
```

没有 Key？到 [算力集市 api.a7w.cn](https://api.a7w.cn/) 注册、充值、创建 Key，注册即送点数，可以先拿 `cost` 与 `doctor` 把价格和端点看明白。

## 自检长什么样

```
自检（不扣费：只读 GET + 空 body 探针，任务 0 条、冻结 0 点）

  √ Key + 余额接口可达                        HTTP 200 · 可用 999,997,393,482 点 · 冻结 0 点
  √ 价目表 GET /pricing 可达                  HTTP 200 · 115 条规则
  √ 6 个工位单价与 /api/v1/pricing 一致        全一致
  √ 视频工位 castcrew  可用（400 empty_url 即正确）  HTTP 400 empty_url
  √ 视频工位 delogo    可用（400 empty_url 即正确）  HTTP 400 empty_url
  √ 视频工位 subtitle  可用（400 empty_url 即正确）  HTTP 400 empty_url
  √ 视频工位 enhance   可用（400 empty_url 即正确）  HTTP 400 empty_url
  √ 视频查询 GET /video/viapi/result/{id} 可达（404 not_found 即正确）
  √ 应用查询 GET /tasks/{id} 可达（200 code 0「任务不存在」即正确）
  √ 上传 POST /upload 可达（不带 file 回 code 0 即正确）
  √ 应用注册表 GET /apps：smart_clip/broadcast_mixcut + voice_tts/tts_async 在架
```

`doctor` 只打只读接口与空 body 探针，**不提交任务、不冻结、不扣点**。应用层两个 `submit` 会走 `reserve_sync`（缺参数先冻结再全额退），所以自检只查 `GET /api/v1/apps` 注册表。

## 和手搓比

| 手搓 | 这条链 |
|---|---|
| 六个页面来回切，六个 taskId 抄进备忘录 | 一个 `run --all`，每步 taskId 自动记进台账 |
| 上一步成片地址手动贴给下一步 | 自动接 `videoUrl`，`castcrew` 旁路不打断主线 |
| 每步都要自己去 `/pricing` 算钱 | `cost` 一次算清，`--budget` 兜底 |
| 外站地址提交后被 400 退回，不知道为什么 | 本地先按白名单预检，`upload` 一步拿合法地址 |
| 忘了 `--yes` 的代价是白扣一次钱 | 缺 `--yes` 退 4 并报出要花多少点 |
| 以为模板列表免费就随便刷 | 实测它会先冻 50 点再全额退，本包提前写清楚 |

## 常见问题

**Q：一定要先 `upload` 吗？**
A：外站地址会被 `400 url_not_allowed` 挡下，所以本地素材先 `upload`（免费）；已经是本站成片（`vr.a7w.cn/result/...`）或本站七牛（`cdn2.jiujiushuyuan.cn/vr/...`）的地址可以直接用。

**Q：`castcrew` 出来的成片在哪？**
A：它只出演员表与 SRT，`completed` 时 `videoUrl` 为空，结果在 `result` 与 `artifactUrl`（30 分钟有效）。

**Q：混剪的 `styleId` 从哪来？**
A：`python3 scripts/run.py template` 列 `scene=oralMixCutting` 的模板；查询本身免费，平台会先冻 50 点再全额退。

**Q：任务失败了钱去哪了？**
A：平台全额退回。`status --task-id` 能看到 `refund` 字段；视频工位偶尔会先报 `failed` 再由平台自动重试，`run` 会等 30 秒再确认一次。

**Q：`--budget` 单位是什么？**
A：点。1 元 = 100 点，默认 3000 = 30 元。预计超过就退 `5`，**一个请求都不发**。

## 文件结构

```
sanjianke-shortdrama-remix/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（实测原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致）
    └── run.py                本包命令层
```

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
