---
name: sanjianke-product-video
slug: sanjianke-product-video
displayName: 商品视频：一张商品图 2.4 元出一条带货短视频
description: "**一张商品图，2.4 元出一条 6 秒带货短视频**：nano-banana 换场景图（72 点）、full_video 按秒出片（768P 28 点/秒）、voice_tts 配口播（上游真实点数 × 3）、本地出 SRT 字幕（0 点），一条 `make` 跑完、零依赖。价格取自 `/api/v1/pricing` 实测：480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒，时长 4~15 秒。三件最容易白花钱的事写进默认动作：`GET /api/v1/apps/<app>` 按应用单价扣且不退，一次都不打；查进度只走 `GET /api/v1/tasks/<id>`；`--budget` 与 `--yes` 两道闸门，超预算一个请求都不发。`doctor` 4 个只读 GET 自检，0 点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "「一张商品图出带货短视频」链路上有 4 个应用、17 个接口，价格口径三套。**应用**（`GET /api/v1/apps` 实测）：nano_banana 2 个、full_video 2 个、voice_tts 6 个、seedance 7 个。**价目**（`GET /api/v1/pricing` 实测，1 元 = 100 点）：full_video/submit 480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒；nano_banana/submit 固定 72 点/次（真任务 `points_cost` = 24，站内 ×3）；voice_tts/tts 上游真实点数 × 3（实测 33 字 5.94 点）；seedance/create 固定 11,000 点/次；字幕本地 0 点。**链路**：商品图 →（免费 upload）→ 场景图 → 成片 → 配音 → 本地 SRT，`make` 一条命令。**闸门**：缺 `--yes` 退 4 并报金额，超 `--budget` 退 5 一个请求都不发。**免费件**：`catalog` / `cost` / `doctor`。需要自备 api.a7w.cn 的 API Key，注册见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 商品视频
  - 短视频带货
  - api.a7w.cn
---

# 商品视频：一张商品图 2.4 元出一条带货短视频

> **本包不内嵌 Key**：用你自己在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**一张商品图，2.4 元出一条 6 秒带货短视频。** AI 换场景图、AI 出成片、AI 配口播、本地出 SRT 字幕 —— 四步一条 `make` 命令，全部走 `api.a7w.cn`，零依赖。

## 价目表（1 元 = 100 点，`GET /api/v1/pricing` 实测）

| 工序 | 接口 | 单价 | 一条 6 秒 |
|---|---|---|---|
| 场景图 | `nano_banana/submit` | **72 点/次** | 72 点 |
| 成片 480P | `full_video/submit` | 14 点/秒 | 84 点 |
| 成片 768P | `full_video/submit` | **28 点/秒** | 168 点 |
| 成片 1080P | `full_video/submit` | 60 点/秒 | 360 点 |
| 成片 2K / 4K | `full_video/submit` | 80 点/秒 | 480 点 |
| 配音 | `voice_tts/tts` | 上游真实点数 × 3 | 约 4 点 |
| 字幕 | 本地生成 SRT | 0 点 | 0 点 |

一条 6 秒 768P = 72 + 168 + 4 + 0 = **244 点 = 2.44 元**。整条链路的四档参考价：4 秒 480P **1.31 元**、6 秒 768P **2.44 元**、10 秒 1080P **6.79 元**、15 秒 4K **12.83 元**（`cost` 会把 4/6/10/15 秒 × 5 档分辨率全打出来）。

seedance `create` 是另一条路：**11,000 点/次（110 元）**，与时长无关。够贵，够稳。

## 三条别人不会告诉你的

**一、查进度只走 `GET /api/v1/tasks/<task_id>`。** 价目表里 `/api/v1/apps/nano_banana/*` 是 72 点/次、`/api/v1/apps/seedance/*` 是 11,000 点/次 —— 连 `query` 查询口都落在这个通配价里。通用任务接口 `GET /api/v1/tasks/<id>` 是 `cost:0` 的免费路径，本包只用它；`status` 子命令就是它。

**二、`GET /api/v1/apps/<app>` 会按该应用的 flat 单价扣，且不退。** 目录信息走 `GET /api/v1/apps`（价目表写死 `cost:0`），价目走 `GET /api/v1/pricing`，两个都是只读免费。本包一次都不打 `apps/<app>`，`catalog` 与 `doctor` 全靠这两条。

**三、seedance 那 7 个接口里，只有 `create` 出片。** 另外 6 个是：`createGroup` 建素材分组、`createAsset` 素材入库、`getAsset` 查素材状态、`updateAsset` 改名、`deleteAsset` 删除、`query` 查任务 —— 5 个素材托管（全是 `multipart/form-data`）+ 1 个查询（GET）。做商品视频一张图当首帧就够，素材托管不是必需品。

## 完整链路

```
商品图（本机文件或 URL）
  └─ upload        免费   POST /api/v1/upload（字段名 file，价目表 cost:0）
      └─ 场景图    72 点   POST /api/v1/apps/nano_banana/submit   action=edit
          └─ 成片  28/秒   POST /api/v1/apps/full_video/submit    content=[text, first_frame]
              └─ 配音  ×3  POST /api/v1/apps/voice_tts/tts       同步返回 data.audio_url
                  └─ 字幕 0 点  本地切行生成 SRT（按字数分配时间轴）
```

`make --scene-prompt "原木桌面，晨光，浅景深"` 出场景图；给 `--no-scene` 就让商品图直接当首帧，省 72 点。

## 三步上手

```bash
# 1) 自检：Key / 4 个应用 / 17 个接口 / 5 档按秒价 / 查询路由，全免费（4 个只读 GET）
python3 scripts/run.py doctor

# 2) 先算钱：4/6/10/15 秒 × 5 档分辨率，0 请求
python3 scripts/run.py cost --duration 6 --resolution 768P --chars 24

# 3) 一条命令出片（要 --yes，超 --budget 一个请求都不发）
python3 scripts/run.py make --image 商品图.jpg \
    --text "轻到 0.9 克，戴一天忘了它在耳朵里。开放式不堵耳，跑步也不掉。" \
    --duration 6 --resolution 768P --ratio 9:16 \
    --scene-prompt "原木桌面，晨光，浅景深" --out ./out --yes
```

## 常用命令

```bash
python3 scripts/run.py catalog                                     # 4 个应用 17 个接口 + 单价
python3 scripts/run.py cost --duration 15 --resolution 4K --no-scene
python3 scripts/run.py script --text "轻到 0.9 克，戴一天忘了它。" --duration 6 --out shop.srt
python3 scripts/run.py upload --file 商品图.jpg                     # 免费，拿可提交地址
python3 scripts/run.py scene --image 商品图.jpg --prompt "原木桌面" --yes
python3 scripts/run.py clip --image "https://…/scene.png" --text "…" --duration 6 --yes
python3 scripts/run.py voice --text "轻到 0.9 克。" --out ./out --yes
python3 scripts/run.py make --image 商品图.jpg --text "…" --dry-run   # 只看 3 个请求
python3 scripts/run.py seedance --action create --text "…" --budget 12000 --yes
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py log --limit 10
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--image` | — | 商品图：本机路径（自动免费上传）或 http(s) 地址 |
| `--text` | — | 口播文案，同时当画面描述（`make` / `clip` / `voice`） |
| `--duration` | 6 | 成片秒数，**只收 4~15 的整数** |
| `--resolution` | 768P | 480P / 768P / 1080P / 2K / 4K（按秒单价不同） |
| `--ratio` | 9:16 | 9:16 / 16:9 / 1:1 / 4:3 / 3:4 / adaptive |
| `--scene-prompt` | — | 给了就去 nano-banana 出场景图（多 72 点） |
| `--no-scene` | — | 商品图直接当首帧，省 72 点 |
| `--chars` | 4 字/秒 | `cost` 用：估口播字数 |
| `--out` / `--prefix` | — / shop | 产物落盘目录与文件名前缀 |
| `--budget` | 3000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

## 子命令

| 子命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 4 个应用 17 个接口 + 单价（2 个只读 GET） |
| `cost` | 免费 | 4/6/10/15 秒 × 5 档分辨率价目（0 请求） |
| `doctor` | 免费 | 自检 Key / 应用 / 按秒价 / 查询路由（4 个只读 GET） |
| `script` | 免费 | 口播文案切行 + 生成 SRT（0 请求） |
| `upload` | 免费 | 商品图上传拿地址（价目表 cost:0） |
| `scene` | 72 点/次 | nano-banana 出场景图 |
| `clip` | 按秒 | full_video 一键成片 |
| `voice` | 上游×3 | voice_tts 配音（同步） |
| `make` | 全链路合计 | 场景图 → 成片 → 配音 → SRT |
| `seedance` | 11,000 点/次 | 7 个接口：create 生成 / 5 个素材管理 |
| `status` | 免费 | 查任务（`GET /api/v1/tasks/<id>`） |
| `log` | 免费 | 本地台账 |

## 退出码

| 码 | 含义 |
|---|---|
| `0` / `2` | 成功 / 用法错（缺必填、秒数越界、选项缩写） |
| `3` / `4` | `doctor` 出现 × / 没给 `--yes` |
| `5` / `6` | 预算不足（**一个请求都不发**）/ 调用失败 |
| `1` / `130` | 内部错误 / 被 Ctrl-C 中断 |

## `--json` 契约

```json
{"ok": true, "videoUrl": "https://…/clip.mp4", "audioUrl": "https://…/voice.mp3",
 "srt": "./out/shop.srt", "clipTaskId": "task_xxx", "estimatedPoints": 244, "yuan": 2.44}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`；`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 计费口径

- 按秒档：提交时按 `duration` 预冻结，完成后按实际时长结算；任务失败全额退回。
- 按次档：nano-banana 72 点/次（2K/4K 只对 `:official` 档生效，价目表同价）；seedance 11,000 点/次。
- 配音：上游真实点数 × 3，单笔保底 1 点；实测 33 字 = 5.94 点。字幕本地生成 0 点，烧进画面用 `ffmpeg -vf subtitles=…`（在你本机跑）。
- 成片链接约 30 分钟有效，`--out` 会顺手落盘。

## 文件结构

`sanjianke-product-video/{SKILL.md, README.md, LICENSE.md, references/{api-contract.md, troubleshooting.md}, scripts/{a7w.py, run.py}}` —— 正好 7 个文件。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
