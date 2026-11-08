---
name: sanjianke-article-to-video
slug: sanjianke-article-to-video
displayName: 一篇 2000 字文章，10 元出一条 60 秒成片
description: "**一篇 2000 字公众号文章，10 元出 60 秒成片**：自动切 12 个分镜 → 每镜 6 点出图（gpt-image-2.6，比 nano-banana 的 72 点省 12 倍）→ 图生视频（full_video 480P 14 点/秒）→ 旁白（voice_tts 约 0.18 点/字）→ 配乐 → 一条 ffmpeg 拼接清单，`make` 一条命令跑完，1,027 点 = 10.27 元。分镜本地，四步都能单跑、能续跑。三条用钱换来的规矩写进默认动作：查进度只走 `GET /api/v1/tasks/<id>`（免费），从不 `GET /api/v1/apps/<app>`（按通配即时扣费），图先 `POST /api/v1/upload` 换成白名单地址。`cost` 先算钱，`--budget` 与 `--yes` 是两道闸门。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "把「一篇写好的文章」变成「一条能发的片子」，五段全走 api.a7w.cn。分镜由本地规则完成：剥 Markdown、按句读切句、按 170 字一镜均匀抽样，0 点、不联网，`plan` 输出 storyboard.json 与 narration.txt。出图走 gpt-image-2.6（6 点/张，与尺寸无关，比 nano-banana 的 72 点省 12 倍），`--ref` 才切到 nano_banana 改风格。出片走 full_video/submit，图当首帧，480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒，4~15 秒一段。旁白走 voice_tts/tts，上游真实点数 x 3，实测 33 字 5.94 点，本包按 0.18 点/字估。配乐走 media_services_33 的 music_generate，落通配：上游 x 2、保底 50 点。查任务一律 GET /api/v1/tasks/<id>（cost:0），应用层 /query 每查一次都是钱；应用详情 GET /api/v1/apps/<app> 按 flat 单价即时扣费，本包一次都不打。最后一刀拼接走本机 ffmpeg，包内给 concat 清单与混音命令。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 图文转视频
  - 分镜
  - api.a7w.cn
---

# 一篇 2000 字文章，10 元出一条 60 秒成片

> **先申请你自己的 API Key。** 本包不内嵌任何 Key，用的是你在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣的是你自己账户的余额。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 一句话

**2000 字 → 12 镜 → 60 秒成片，1,027 点（10.27 元）**：分镜本地切（0 点）、每镜 6 点出图、图生视频 480P 14 点/秒、旁白约 0.18 点/字、配乐 50 点起。

## 价目表（1 元 = 100 点，2026-11-07 现查 `GET /api/v1/pricing`）

| 工序 | 用谁 | 端点 | 单价 |
|---|---|---|---|
| 分镜 | 本地 | 不发请求 | **0 点** |
| 出图 | gpt-image-2.6 | `POST /api/v1/images/generations` | **6 点/张** |
| 改图 | nano-banana | `POST /api/v1/apps/nano_banana/submit` | 72 点/次 |
| 动起来 | full_video | `POST /api/v1/apps/full_video/submit` | 480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80 点/秒 |
| 旁白 | voice_tts | `POST /api/v1/apps/voice_tts/tts` | 约 0.18 点/字 |
| 配乐 | media_services_33 | `POST /api/v1/apps/media_services_33/music_generate` | 50 点起/首 |

## 一篇 2000 字到底多少钱

| 档位 | 分镜 | 片长 | 旁白 | 合计 |
|---|---|---|---|---|
| **精华版（默认）** | 12 镜 × 5 秒 | 60 秒 | 360 字 | **1,027 点 = 10.27 元** |
| 全文照念 | 67 镜 × 5 秒 | 335 秒 | 2,000 字 | 5,502 点 = 55.02 元 |

拆开看精华版：出图 72 点 + 图生视频 840 点 + 旁白 65 点 + 配乐 50 点。

**每加 1 镜 = 76 点（0.76 元）**；换 768P 变 18.67 元，换 1080P 变 37.87 元。`cost` 会把两档、五档分辨率都列出来。

## 三条干货（别人不写进文档的）

**一、轮询一次就是一次的钱。** 应用层的 `/query` 每查一次都按该应用的单价结算，nano_banana 这种 72 点/次的接口，历史上有账号靠轮询烧掉 15,552 点。本包 `wait_task` 只打 `GET /api/v1/tasks/<id>`，价目表里这条是 cost:0，等十分钟也是 0 点。

**二、`GET /api/v1/apps/<app>` 是收费的。** 它命中 `/api/v1/apps/<app>/*` 的通配计价，按该应用 flat 单价**即时扣费、不退**（实测 dressing_diffusion 200 点、nano_banana 72 点各一笔）。本包要目录只看 `GET /api/v1/apps` 列表和 `GET /api/v1/pricing`，两条都是 cost:0。

**三、图地址有域名白名单。** 本地图直接塞给视频接口会 400 `url_not_allowed`，只认本站、本站七牛和 `oss.gpu.likeadmin.cn/openapi/`。本包在每个镜头提交前自动 `POST /api/v1/upload`（免费）换地址，你不必操心。

## 完整链路（五段 + 最后一刀）

```
文章.md
  └─ plan    剥 Markdown → 切句 → 按 170 字一镜抽样 → storyboard.json      0 点
      └─ image   每镜 6 点出图，b64 自动落盘 scene-01.png ...              6 点/镜
          └─ render  图免费上传换地址 → full_video submit → 轮询 GET /tasks  14 点/秒
              └─ voice   旁白按 450 字切块 → tts → narration.mp3           0.18 点/字
                  └─ music   Suno 生成一首 → bgm.mp3                        50 点起
                      └─ 本机 ffmpeg 合成 film.mp4                          0 点
```

## 三步上手

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"
python3 scripts/a7w.py login --key sk-你的key

# 2) 自检 + 算钱（都不扣费）
python3 scripts/run.py doctor
python3 scripts/run.py cost --chars 2000

# 3) 出片
python3 scripts/run.py plan --article article.md
python3 scripts/run.py image  --yes
python3 scripts/run.py render --yes
python3 scripts/run.py voice  --yes
python3 scripts/run.py music  --yes
```

想一步到位：

```bash
python3 scripts/run.py make --article article.md --budget 2000 --yes
```

跑完会把 `storyboard.json`、`scene-01.png…`、`clip-01.mp4…`、`narration.mp3`、`bgm.mp3`、`concat.txt` 一起放在 `build/`，并打印可直接粘的合成命令：

```bash
cd build
ffmpeg -f concat -safe 0 -i concat.txt -i narration.mp3 -i bgm.mp3 \
  -filter_complex "[1:a][2:a]amix=inputs=2:duration=first[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -shortest film.mp4
```

## 常用命令

| 命令 | 扣费吗 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 五段链路的能力、端点、现查单价 |
| `cost --chars 2000` | 免费 | 精华版 / 全文版 / 五档分辨率一起算 |
| `doctor` | 免费 | 自检 Key、应用、价目、出图端点、查询路由、上传 |
| `plan --article a.md` | 免费 | 出分镜脚本，先看 12 镜长什么样 |
| `image --ref 参考图.png` | **72 点/镜** | 拿参考图改风格（默认走 6 点的 gpt-image） |
| `render --resolution 768P` | **28 点/秒** | 换分辨率重出片 |
| `task --task-id t_xxx` | 免费 | 查进度 / 补取产物 |
| `log` | 免费 | 本地台账 |

## 和同类包的分工

| 你手上有什么 | 用哪个包 | 它替你做什么 |
|---|---|---|
| **一篇写好的文章** | **本包** | 分镜 → 图 → 动 → 旁白 → 配乐 → 拼接清单 |
| 只有一个选题，脚本也还没写 | `sanjianke-short-video-maker` | 先写脚本，再走七道工序出片 |
| 一张商品图 + 一句卖点 | `sanjianke-product-video` | 6 秒带货短视频，一条 `make` |
| 要点的是整套新媒体配图 | `sanjianke-image-factory` | 多平台尺寸的配图方案与批量出图 |
| 只要一张图 | `sanjianke-gpt-image` | 单张 6 点，文生图 / 图生图 / GIF |

## 规格

| 参数 | 默认 | 说明 |
|---|---|---|
| `--scenes` | 0（自动） | 切几镜；0 = 按 170 字一镜算，上限 60 |
| `--seconds` | 5 | 每镜秒数 **4~15**（`plan` / `make` 默认 5；`render` 用分镜里的值） |
| `--resolution` | 480P | 480P / 768P / 1080P / 2K / 4K |
| `--ratio` | 16:9 | 16:9 / 9:16 / 1:1 / 4:3 / 3:4 / adaptive |
| `--narration-chars` | 30 | 每镜旁白上限字数 |
| `--budget` | 2000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实扣费 |
| `--dry-run` | — | 只打印请求，不提交（预算超了照样先拦） |

退出码：`0` 成功 / `2` 用法错 / `3` 自检有项没过 / `4` 缺 `--yes` / `5` 超预算且一个请求都没发 / `6` 调用失败 / `1` 内部错 / `130` 中断。

`--json` 成功是 `{"ok": true, ...}`，失败是 `{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}`，stdout 只有一个 JSON 文档；`--json` 写在子命令前后都可以。

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
