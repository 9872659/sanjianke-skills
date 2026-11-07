---
name: sanjianke-shortdrama-remix
slug: sanjianke-shortdrama-remix
displayName: 短剧二创一条龙 · 60 秒片 18 元跑完全链
description: "**一条 60 秒短剧素材，从认演员表到出二创成片，1,796 点（17.96 元）一条命令跑完。** 认演员表 25 点/次、去台标 25 点/次、擦硬字幕 9 点/秒、画质提一档 15 点/秒、解说配音按上游点数 ×3、模板混剪 4.5 点/秒 —— 六个工位全走 api.a7w.cn，异步两步、零依赖。本包把三件真会白跑的事做成默认动作：videoUrl 只认平台托管地址，所以先 upload 拿地址；castcrew 只出 SRT，成片在别处；应用层 submit 与部分免费 GET 会先冻结再全额退，所以 doctor 只查应用注册表。`cost` 先算钱，`--budget`（单位：点，1 元 = 100 点）与 `--yes` 两道闸门，`--step` 单跑一步、`--all` 全链跑完。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "短剧二创的六个工位散在三个通道：视频工位在 /api/v1/video/viapi/<step>，配音在 voice_tts/tts_async，混剪在 smart_clip/broadcast_mixcut。**价目**（1 元 = 100 点）：castcrew 25 点/次、delogo 25 点/次、subtitle 9 点/秒、enhance 15 点/秒、tts 上游实际点数 ×3、mixcut 4.5 点/秒（保底 45 点）。**链路**：upload（免费）→ castcrew → delogo → subtitle → enhance → tts → mixcut；--step 单跑一步，--all 自动接上一步成片。**地址**：videoUrl 只认 vr.a7w.cn、cdn2.jiujiushuyuan.cn/vr/、oss.gpu.likeadmin.cn/openapi/ 三种。**查询**：视频走 /video/viapi/result/{id}，应用走 /tasks/{id}。**计费**：按秒工位先冻结后结算，失败全额退；castcrew 价签「点/次」而规则是 per_second，本包按价签计一次。需要自备 api.a7w.cn 的 Key（注册见 https://api.a7w.cn/ ）。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 短剧二创
  - 视频处理
  - api.a7w.cn
---

# 短剧二创一条龙 · 60 秒片 18 元跑完全链

> **本包不内嵌 Key**：用你自己在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**一条 60 秒短剧素材，6 个工位一条命令跑完：认演员表 → 去台标 → 擦硬字幕 → 提画质 → 解说配音 → 模板混剪成片。全套 1,796 点 = 17.96 元。**

## 价目表（1 元 = 100 点，取自 `GET /api/v1/pricing`）

| 工位 | `--step` | 单价 | 60 秒片 | 干什么 |
|---|---|---|---|---|
| 认演员表 / 硬字幕 OCR | `castcrew` | **25 点/次** | 25 点 | 抽硬字幕与滚动演职员表，附 SRT |
| 去台标 / Logo | `delogo` | **25 点/次** | 25 点 | 擦台标、平台 logo，最多 2 个区域 |
| 擦硬字幕 | `subtitle` | **9 点/秒** | 540 点 | 把原片硬字幕抹干净，换字幕第一步 |
| 画质提一档 | `enhance` | 15 点/秒 | 900 点 | 清晰度 / 对比度 / 细节整体提一档 |
| 解说配音 | `tts` | 上游 ×3（约 0.18 点/字） | 200 字 = 36 点 | 长文本异步合成，出解说音频 |
| 模板混剪成片 | `mixcut` | 4.5 点/秒（保底 45） | 270 点 | 按模板把素材与解说拼成成片 |

`castcrew` / `delogo` 的价签写「点/次」，引擎规则却是 `per_second` —— 本包按价签计一次，`cost` 会把两种口径都打出来，最终以账单为准。

## 三条别人不会告诉你的

**一、`videoUrl` 只认三种平台地址。** 实测往 `/api/v1/video/viapi/subtitle` 发外站地址，返回 `400 url_not_allowed`，原文三选一：本站 `vr.a7w.cn`、本站七牛 `cdn2.jiujiushuyuan.cn/vr/`、本站上传接口 `oss.gpu.likeadmin.cn/openapi/`。所以 `upload` 是标配：传完拿 `data.url` 直接喂 `run`，全程免费，地址最长 24 小时。

**二、`castcrew` 没有成片。** 它 `completed` 时 `videoUrl` 为空，演员表与 SRT 在 `result` 与 `artifactUrl`（30 分钟有效）。所以链上它是旁路：认完演员表，主视频继续走 `delogo`。

**三、应用层会先冻结再全额退。** 两个应用工位走 `reserve_sync`：缺参数先冻结再退。实测连免费的 `GET /apps/smart_clip/template`（冻 50 点）与 `GET /apps/voice_tts/list_voices`（冻 150 点）都会先冻后退 —— 净 0，但钱包会动。所以 `doctor` 只查 `GET /api/v1/apps` 注册表，把 6 个端点在参数校验层验完，不碰应用层。

## 完整链路

```
upload（免费，拿白名单地址）
  → castcrew  25 点/次 → 演员表 + SRT（旁路，不改主视频）
  → delogo    25 点/次 → 无台标视频
  → subtitle   9 点/秒 → 无硬字幕视频
  → enhance   15 点/秒 → 高清视频
  → tts       上游×3   → 解说音频（--text）
  → mixcut   4.5 点/秒 → 最终成片（--style-id + enhance 的片子 + tts 的音频）
```

每一步都能单独跑；`--all` 自动把上一步的 `videoUrl` 接给下一步，也可以 `--skip castcrew,tts` 跳过不想要的工位。

## 三步上手

```bash
# 1) 自检（免费）：Key / 价目 / 6 个端点 / 两条查询路由 / 上传 / 应用注册表
python3 scripts/run.py doctor

# 2) 先算钱：改秒数与字数，看这一趟要多少点
python3 scripts/run.py cost --seconds 60 --chars 200
#   → 1,796 点 = 17.96 元

# 3) 单步或全链
python3 scripts/run.py run --step subtitle \
  --video-url "https://oss.gpu.likeadmin.cn/openapi/18/20261107/xxxx.mp4" --yes

python3 scripts/run.py run --all --file 素材.mp4 \
  --script "三十秒带你看完这集反转" \
  --style-id 6ac8981c20d5010033eee1b7 --yes
```

**不加 `--yes` 退 `4`** 并告诉你这次要花多少；**预计点数 > `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 3000 = 30 元）。想先看不花钱的请求：`--dry-run`。

## 常用命令

```bash
python3 scripts/run.py catalog                      # 6 个工位 + 单价 + 端点
python3 scripts/run.py cost --step enhance --seconds 90
python3 scripts/run.py upload --file 素材.mp4       # 免费，拿白名单地址
python3 scripts/run.py template --page-size 5       # 拿 styleId（冻 50 退 50，净 0）
python3 scripts/run.py run --step castcrew --video-url "..." --yes
python3 scripts/run.py run --step delogo --video-url "..." --boxes 0.05,0.05,0.2,0.1 --yes
python3 scripts/run.py run --step tts --text "解说词" --voice-id <音色> --yes
python3 scripts/run.py run --all --file 素材.mp4 --script "解说词" --style-id <模板> --yes
python3 scripts/run.py status --task-id task_xxx --step enhance
python3 scripts/run.py log --limit 10
```

## 规格

- 端点：视频工位 `POST /api/v1/video/viapi/<castcrew|delogo|subtitle|enhance>`；配音 `POST /api/v1/apps/voice_tts/tts_async`；混剪 `POST /api/v1/apps/smart_clip/broadcast_mixcut`；上传 `POST /api/v1/upload`（multipart，字段名 `file`）。
- 查询：视频 `GET /api/v1/video/viapi/result/{taskId}`；应用 `GET /api/v1/tasks/{taskId}`；`status` 两条都试。
- 按秒工位先按 `duration` 冻结、完成后按实际时长结算；任务失败平台全额退回。
- 成片链接约 **30 分钟**有效，拿到就转存；`castcrew` 的 SRT 同样是 30 分钟。
- `tts` 对外价 = 上游实际点数 × 3，`cost` 给的是按字数的估算；真实扣费看 `usage.points_cost`。
- 零依赖：只要 Python 3.7+，不需要 `pip install`。

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺参数、`--step` 与 `--all` 同时给、选项缩写） |
| `3` | `doctor` 出现 × |
| `4` | 需要确认 —— 没给 `--yes`（会告诉你要花多少） |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 / 任务 failed |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

## `--json` 契约

```json
{"ok": true, "mode": "all", "seconds": 60, "chars": 200,
 "estimatedPoints": 1796, "yuan": 17.96,
 "steps": [{"step": "subtitle", "taskId": "task_xxx", "status": "completed",
            "billedPoints": 540, "videoUrl": "https://vr.a7w.cn/result/xxx.mp4"}],
 "videoUrl": "https://vr.a7w.cn/result/xxx.mp4", "finalVideoUrl": "..."}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`；`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 文件结构

```
sanjianke-shortdrama-remix/{SKILL.md, README.md, LICENSE.md,
  references/{api-contract.md, troubleshooting.md},
  scripts/{a7w.py, run.py}}
```

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
