# 商品视频：一张商品图 2.4 元出一条带货短视频

**一张商品图，2.4 元出一条 6 秒带货短视频。** 场景图、成片、口播、SRT 字幕四步一条命令 —— 全部走 [api.a7w.cn](https://api.a7w.cn/)，零依赖、只用标准库。

| 工序 | 接口 | 单价 | 一条 6 秒 |
|---|---|---|---|
| 场景图 | `nano_banana/submit` | **72 点/次** | 72 点 |
| 成片 768P | `full_video/submit` | **28 点/秒** | 168 点 |
| 配音 | `voice_tts/tts` | 上游真实点数 × 3 | 约 4 点 |
| 字幕 | 本地生成 SRT | 0 点 | 0 点 |

1 元 = 100 点。6 秒 768P 合计 **244 点 = 2.44 元**；4 秒 480P 是 **131 点 = 1.31 元**；15 秒 4K 是 **1,283 点 = 12.83 元**。

---

## 完整链路

```
商品图（本机文件或 URL）
  └─ upload        免费   POST /api/v1/upload（字段名 file，价目表 cost:0）
      └─ 场景图    72 点   POST /api/v1/apps/nano_banana/submit   action=edit
          └─ 成片  28/秒   POST /api/v1/apps/full_video/submit    content=[text, first_frame]
              └─ 配音  ×3  POST /api/v1/apps/voice_tts/tts       同步返回 data.audio_url
                  └─ 字幕 0 点  本地切行生成 SRT
```

---

## 三条别人不会告诉你的

### 一、查进度只走 `GET /api/v1/tasks/<task_id>`

价目表里 `/api/v1/apps/nano_banana/*` 是 **72 点/次**、`/api/v1/apps/seedance/*` 是 **11,000 点/次** —— 连它们自己的 `query` 查询口都落在这个通配价里。通用任务接口 `GET /api/v1/tasks/<id>` 是 `cost:0` 的免费路径，本包只用它。

### 二、`GET /api/v1/apps/<app>` 会按该应用的 flat 单价扣，且不退

目录信息走 `GET /api/v1/apps`（价目表写死 `cost:0`），价目走 `GET /api/v1/pricing`，两个都只读免费。本包一次都不打 `apps/<app>` —— `catalog` 与 `doctor` 全靠这两条，各一次请求就把 4 个应用、17 个接口、5 档按秒价全拿到。

### 三、seedance 那 7 个接口里，只有 `create` 出片

| 接口 | 分工 | 形态 |
|---|---|---|
| `create` | 生成视频（唯一出片口） | JSON，11,000 点/次 |
| `createGroup` / `createAsset` / `getAsset` / `updateAsset` / `deleteAsset` | **素材托管**：建分组 / 入库 / 查状态 / 改名 / 删除 | `multipart/form-data` |
| `query` | 查任务（等价 `/api/v1/tasks/<id>`） | GET |

做商品视频一张图当首帧就够，5 个素材托管接口不是必需品；`seedance` 子命令把它们收在 `--action` 后面，`--action create` 才是出片。

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key
# 或者：python3 scripts/a7w.py login --key sk-你的key

# 2) 免费自检：Key / 4 个应用 / 17 个接口 / 5 档按秒价 / 查询路由（4 个只读 GET）
python3 scripts/run.py doctor

# 3) 先算钱（0 请求）
python3 scripts/run.py cost --duration 6 --resolution 768P --chars 24

# 4) 一条命令出片
python3 scripts/run.py make --image 商品图.jpg \
    --text "轻到 0.9 克，戴一天忘了它在耳朵里。开放式不堵耳，跑步也不掉。" \
    --duration 6 --resolution 768P --ratio 9:16 \
    --scene-prompt "原木桌面，晨光，浅景深" --out ./out --yes

# 5) 查任务 / 看台账
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py log
```

`make` 跑完会打印成片地址、配音地址、SRT 路径，以及一行合成命令（在你本机跑，不走接口）：

```bash
ffmpeg -i clip.mp4 -i voice.mp3 -vf subtitles=shop.srt -c:v libx264 -c:a aac out.mp4
```

---

## 常用命令

```bash
python3 scripts/run.py catalog                                     # 4 个应用 17 个接口 + 单价
python3 scripts/run.py cost                                        # 4/6/10/15 秒 × 5 档分辨率
python3 scripts/run.py cost --duration 15 --resolution 4K --no-scene
python3 scripts/run.py script --text "轻到 0.9 克，戴一天忘了它。" --duration 6 --out shop.srt
python3 scripts/run.py upload --file 商品图.jpg                     # 免费
python3 scripts/run.py scene --image 商品图.jpg --prompt "原木桌面" --out ./out --yes
python3 scripts/run.py clip --image "https://…/scene.png" --text "…" --duration 6 --yes
python3 scripts/run.py voice --text "轻到 0.9 克。" --out ./out --yes
python3 scripts/run.py make --image 商品图.jpg --text "…" --dry-run   # 只看请求
python3 scripts/run.py seedance --action create --text "…" --budget 12000 --yes
python3 scripts/run.py seedance --action group --name shop-assets --dry-run
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py log --limit 10
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--image` | — | 商品图：本机路径（自动免费上传）或 http(s) 地址 |
| `--text` | — | 口播文案，同时当画面描述 |
| `--duration` | 6 | 成片秒数，**只收 4~15 的整数** |
| `--resolution` | 768P | 480P / 768P / 1080P / 2K / 4K |
| `--ratio` | 9:16 | 9:16 / 16:9 / 1:1 / 4:3 / 3:4 / adaptive |
| `--scene-prompt` | — | 给了就去 nano-banana 出场景图（多 72 点） |
| `--no-scene` | — | 商品图直接当首帧，省 72 点 |
| `--chars` | 4 字/秒 | `cost` 用：估口播字数 |
| `--out` / `--prefix` | — / shop | 产物落盘目录与文件名前缀 |
| `--budget` | 3000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` / `--dry-run` | — | 确认真实扣费 / 只打印请求 |

---

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

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、秒数越界、选项缩写） |
| `3` | 自检没过（`doctor` 出现 ×） |
| `4` | 需要确认 —— 没给 `--yes`，并报出这次要花多少点 |
| `5` | 预算不足 —— **一个请求都不发** |
| `6` | 调用失败 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "videoUrl": "https://…/clip.mp4", "audioUrl": "https://…/voice.mp3",
 "srt": "./out/shop.srt", "clipTaskId": "task_xxx", "estimatedPoints": 244, "yuan": 2.44}
```

失败：`{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`

`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`；`--json` 写在子命令**前后都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-product-video/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（文档原文 + 实测返回 + 价目原文）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 计费口径

- 按秒档：提交时按 `duration` 预冻结，完成后按**实际时长**结算；任务失败全额退回。
- 按次档：`nano_banana/submit` 72 点/次（真任务 `usage.points_cost` = 24，站内 ×3）；`seedance/create` 11,000 点/次。
- 配音：上游真实点数 × 3，单笔保底 1 点。实测同一 `task_id`：上游 `points_cost` = 2.64，站内流水 `settle` = −7.92。
- 字幕：本地生成 SRT，0 点；烧进画面在你本机跑 ffmpeg。
- 成片链接约 30 分钟有效，`--out` 会顺手落盘；上传返回的地址最长 24 小时。
- `--budget` 与 `--yes` 是本地闸门：预算内才发请求，`--yes` 到了才提交。`--dry-run` 只打印请求，两道闸门都放行。

---

## 合规与边界

- 生成内容的合规责任在使用者：请用于有授权的素材与合法用途。
- 真实扣费以任务完成时返回的 `usage.points_cost`（或 `cost`）为准，`cost` 给的是预估。
- 上传接口仅作临时中转，返回地址最长 24 小时，请及时转存到自己的存储。

---

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
