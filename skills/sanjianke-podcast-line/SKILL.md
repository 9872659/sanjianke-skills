---
name: sanjianke-podcast-line
slug: sanjianke-podcast-line
displayName: 播客生产线 · 3 条请求出一期成品播客
version: 1.0.0
license: MIT
tags:
  - 三剪客
  - 音频生成
  - 播客
  - api.a7w.cn
---

# 播客生产线 · 3 条请求出一期成品播客

> **先申请你自己的 API Key**：本包不内嵌任何 Key，用的是**你自己**在
> [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。
> 登录：`python3 scripts/a7w.py login --key sk-你的key`

## 一句话

**3 条请求、下限 180 点，把一份 20 分钟的文稿变成一期能上架的播客。** 配音、配乐、逐句字幕、章节目录，四个零件一个命令一个，异步提交 + 自动轮询，零依赖。

## 价目表

| 零件 | 子命令 | 接口 | 一条请求下限 | 一条给你什么 |
|---|---|---|---|---|
| **配音** | `vo` | `elevenlabs_text_to_speech_multilingual_v2` | 60 点 | 一条人声，5000 字以内，67 个音色可选 |
| **配乐** | `bgm` | `music_generate` | 60 点 | 一条 10–360 秒的片头 / 垫乐 / 转场 |
| **字幕** | `subs` | `music_timestamped_lyrics` | 60 点 | 逐句时间轴，顺手落一份 SRT |
| **章节** | `chapters` | 本地算 | **0 点** | 章节块，`00:00 第 1 章 …` 直接贴 |

- **1 元 = 100 点。** 一期标配套餐（1 条配音 + 1 条配乐 + 1 条字幕）= **3 条 = 180 点 = 1.80 元**起。
- 30 分钟口播约 7000 字，按 4500 字一片 → **2 条配音**，整期 4 条 = **240 点 = 2.40 元**起。
- 任务失败**全额退回**，不占你的预算。

## 三条干货

1. **5000 字是整个 ElevenLabs 通道的单条硬上限**，超了上游直接拒。`vo --script` 按句子切 4500 字一片，一篇 7000 字长稿自动变 2 条请求、2 个 `task_id`，断句在句号处、气口不会莫名其妙断在半句。
2. **音色填 ID，不填名字。** 67 个 ID 已内置在包里（`catalog --voices` 一屏看完，带中文性格描述）。给名字会被当场退 2 并告诉你最接近的 ID —— 猜错会真的提交一条任务、真的冻结点数。
3. **章节不用另外买。** `chapters` 把文稿的 `## 第 N 章` 标题按字数比例对到字幕时间轴，纯本地算、0 点。字幕改了重跑一次就行，不用重新提交任务。

## 完整链路

```
文稿.md ──vo──▶ 配音任务 ─┐
                          ├─▶ 拼成整期（ffmpeg concat，按片序）
配乐 prompt ─bgm─▶ 垫乐 ──┘
                          │
带人声的曲子 ─subs─▶ 逐句时间轴 ──chapters──▶ 章节目录 ──▶ 发布后台
```

```bash
# 1) 配音：一段文稿，自动切片，逐片轮询
python3 scripts/run.py vo --script ep01.md --voice eR40ATw9ArzDf9h3v7t7 --yes

# 2) 配乐：一条纯音乐垫乐，180 秒
python3 scripts/run.py bgm --prompt "lo-fi 钢琴，温暖，无人声" \
    --style "lo-fi piano, warm" --duration 180 --yes

# 3) 字幕：拿上一步的 task_id + audio_id 出逐句时间轴，顺手落 SRT
python3 scripts/run.py subs --task-id <bgm_task_id> --audio-id <bgm_audio_id> \
    --srt-out ep01.srt --yes

# 4) 章节：文稿标题 × 字幕时间轴，本地算，0 点
python3 scripts/run.py chapters --script ep01.md --srt ep01.srt --out ep01.chapters.txt
```

`vo` 一次提交多片时会写一份清单（`--manifest vo.json`），断了用 `task --task-id …` 免费续查，**同一条结果不会重复提交**。

## 三步上手

```bash
# 1) 自检（全只读 GET，0 点）：Key、余额、三条接口在架、通配价目、查询路由
python3 scripts/run.py doctor

# 2) 先看价（纯本地算术，0 点）：按你的文稿字数算要几条、下限多少点
python3 scripts/run.py cost --script ep01.md --bgm --subs

# 3) 出配音
python3 scripts/run.py vo --script ep01.md --voice eR40ATw9ArzDf9h3v7t7 --yes
```

缺 `--yes` 退 `4` 并写明下限是多少点；下限超 `--budget` 退 `5`，**一个请求都不发**。
先看不花钱的请求体：任意付费子命令加 `--dry-run`。

## 常用命令

```bash
python3 scripts/run.py catalog                     # 三条接口 + 8 个播客常用音色 + 价格口径
python3 scripts/run.py catalog --voices            # 67 个音色 ID + 中文性格
python3 scripts/run.py cost --chars 12000 --bgm --subs          # 直接给字数
python3 scripts/run.py cost --script ep01.md --upstream 65      # 按你观察到的上游点数换算
python3 scripts/run.py vo --text "这一期聊聊播客。" --voice 8JVbfL6oEdmuxKn5DK2C --yes
python3 scripts/run.py vo --script ep01.md --voice x70vRnQBMBu4FAYhjJbO --no-wait --manifest vo.json
python3 scripts/run.py bgm --custom --style "city pop" --title "片头" --duration 30 --yes
python3 scripts/run.py subs --task-id t_xxx --audio-id a_xxx --srt-out ep01.srt --yes
python3 scripts/run.py chapters --script ep01.md --subs subs.json
python3 scripts/run.py task --task-id t_xxx --out ./podcast       # 免费续查 / 下载
python3 scripts/run.py log                                        # 本地台账
python3 scripts/run.py doctor --probe          # 三条端点参数校验（冻 60 全退，净 0）
```

## 规格

| 项 | 值 |
|---|---|
| 端点 | `POST /api/v1/apps/media_services_33/<接口code>`，JSON |
| 查询 | `GET /api/v1/tasks/<task_id>`，只读、0 点 |
| 配音 | `text` ≤5000 字、`voice` 限 67 个 ID；`--speed` 0.7–1.2、`--style`/`--stability`/`--similarity` 0–1 |
| 配乐 | `model` 九档（默认 `V6`）、`custom_mode`、`instrumental` 必填；`--duration` 10–360 秒 |
| 字幕 | `task_id` + `audio_id` 必填，都来自配乐任务的返回 |
| 依赖 | Python 标准库，零第三方 |
| 退出码 | `0` 成功 / `2` 用法错 / `4` 缺 `--yes` / `5` 超预算 / `6` 调用失败 / `1` 内部错 / `130` 中断 |
| `--json` | 成功 `{"ok":true,…}`；失败 `{"ok":false,"exit":N,"error":{"kind":"gate\|budget\|confirm\|usage\|call\|interrupt\|internal","message":"…"}}` |

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。明细见
`references/api-contract.md`（schema 原文 + 实测返回）与 `references/troubleshooting.md`（按报错找原因）。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
