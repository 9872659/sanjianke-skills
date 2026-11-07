# 图文转视频：一篇 2000 字文章，10 元出一条 60 秒成片

**2000 字公众号文章进，12 镜、60 秒、带旁白与配乐的成片出。** 分镜在本地切（0 点），出图 6 点/张，图生视频 480P 14 点/秒，旁白约 0.18 点/字，配乐 50 点起 —— 全套 **1,027 点 = 10.27 元**。

最后一刀拼接在本机跑 ffmpeg：包内给出 `concat.txt` 和可直接粘的混音命令，零依赖、不用装服务端。

---

## 它替你做的五件事

| 工序 | 用什么 | 做什么 | 单价 |
|---|---|---|---|
| 分镜 | 本地规则 | 剥 Markdown → 按句读切句 → 按 170 字一镜均匀抽样 | **0 点** |
| 出图 | gpt-image-2.6 | 每镜一张，b64 自动落盘 | **6 点/张** |
| 动起来 | full_video | 图当首帧，出 4~15 秒片段 | **14 点/秒**（480P） |
| 旁白 | voice_tts | 按 450 字切块合成，句间自动补句号 | 约 **0.18 点/字** |
| 配乐 | media_services_33 | Suno 生成一首纯音乐 | **50 点起** |

改图另有一条：`image --ref 参考图.png` 会切到 nano-banana（72 点/次），拿参考图统一画风。

---

## 一篇 2000 字，钱花在哪

| 档位 | 分镜 | 片长 | 旁白 | 合计 |
|---|---|---|---|---|
| **精华版（默认）** | 12 镜 × 5 秒 | 60 秒 | 360 字 | **1,027 点 = 10.27 元** |
| 全文照念 | 67 镜 × 5 秒 | 335 秒 | 2,000 字 | 5,502 点 = 55.02 元 |

精华版拆开：出图 72 + 图生视频 840 + 旁白 65 + 配乐 50。

同一篇换分辨率（12 镜 × 5 秒）：

| 分辨率 | 点数 | 折合 |
|---|---|---|
| 480P | 1,027 | 10.27 元 |
| 768P | 1,867 | 18.67 元 |
| 1080P | 3,787 | 37.87 元 |
| 2K / 4K | 4,987 | 49.87 元 |

`cost` 会把这两档和五档分辨率一次算清；**每加 1 镜 = 76 点（0.76 元）**。

---

## 三条规矩：钱是这样省下来的

### 一、查进度只走 `GET /api/v1/tasks/<id>`

应用层的 `/query` 每查一次就是一次的钱。nano_banana 这类 72 点/次的接口，历史上有账号靠轮询烧掉 **15,552 点**。

本包 `wait_task` 只打 `GET /api/v1/tasks/<id>` —— 价目表里这条是 `cost:0`，等十分钟也是 0 点。

### 二、`GET /api/v1/apps/<app>` 是收费的

它命中 `/api/v1/apps/<app>/*` 的通配计价，按该应用 flat 单价**即时扣费、不退**。实测流水：

```
19:35:08  -200  sync:/api/v1/apps/dressing_diffusion
19:35:11   -72  sync:/api/v1/apps/nano_banana
19:35:34  -200  sync:/api/v1/apps/dressing_diffusion
```

要目录，本包只看 `GET /api/v1/apps`（列表，cost:0）和 `GET /api/v1/pricing`（cost:0）。

### 三、图地址有域名白名单

本地图直接塞给视频接口会 `400 url_not_allowed`，只认本站、本站七牛和 `oss.gpu.likeadmin.cn/openapi/`。

本包在每个镜头提交前自动 `POST /api/v1/upload`（免费）换地址，`videoUrl` / `image_url` 不会带错。

---

## 快速开始

```bash
# 1) 填 Key（三选一：--key / 环境变量 / 本地配置）
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"
python3 scripts/a7w.py login --key sk-你的key

# 2) 自检（7 个请求，全停在扣费之前）
python3 scripts/run.py doctor

# 3) 先算钱
python3 scripts/run.py cost --chars 2000

# 4) 分镜（0 点，先看看切得对不对）
python3 scripts/run.py plan --article article.md

# 5) 四步出片
python3 scripts/run.py image  --yes
python3 scripts/run.py render --yes
python3 scripts/run.py voice  --yes
python3 scripts/run.py music  --yes
```

想一步到位：

```bash
python3 scripts/run.py make --article article.md --budget 2000 --yes
```

只看请求不花钱：

```bash
python3 scripts/run.py make --article article.md --dry-run
```

---

## 分镜怎么切（纯本地，跑一万次 0 点）

1. 去掉代码块、图片、链接地址、HTML 标签、`#` 与列表符号；
2. 按 `。！？；` 与换行切句，少于 8 字的碎片丢掉；
3. 按 170 字一镜算出镜数（上限 60），**均匀抽样**覆盖全文，首尾都取到；
4. 每镜旁白截到 30 字，优先在逗号处断；画面提示词 = 原句 + 风格词 + 画幅 + 「高清写实摄影」。

结果写进 `storyboard.json`，同时给一份 `narration.txt` 方便你手改。改完重跑 `image` 时，已经出过图的镜头会自动跳过。

---

## 产物长什么样

```
build/
├── storyboard.json     分镜 + 每镜的图/视频/任务号 + 合成命令
├── narration.txt       旁白脚本（一行一镜，可手改）
├── scene-01.png ...    每镜一张图（b64 自动解码落盘）
├── clip-01.mp4 ...     每镜一段视频
├── narration.mp3       旁白（超过 450 字会切成 narration-01/02…）
├── bgm.mp3             配乐
└── concat.txt          ffmpeg 的拼接清单
```

合成（本机跑，0 点）：

```bash
cd build
ffmpeg -f concat -safe 0 -i concat.txt -i narration.mp3 -i bgm.mp3 \
  -filter_complex "[1:a][2:a]amix=inputs=2:duration=first[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -shortest film.mp4
```

没有配乐就少一路输入：

```bash
ffmpeg -f concat -safe 0 -i concat.txt -i narration.mp3 -c:v copy -c:a aac -shortest film.mp4
```

旁白超过 450 字会被切成 `narration-01.mp3`、`narration-02.mp3`，先拼成一条再合成：

```bash
ffmpeg -f concat -safe 0 -i narration-concat.txt -c copy narration.mp3
```

---

## 断点续跑

每一步都会把结果写回 `storyboard.json`：

- `image` 只补没有图的镜头；
- `render` 只补没有片段的镜头；
- 中途 Ctrl-C，重跑同一条命令接着做，不会为已完成的那几镜再付一次。

`--force` 才会推翻重做。

---

## 命令一览

| 命令 | 扣费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 五段链路、端点、现查单价 |
| `cost` | 免费 | 精华版 / 全文版 / 五档分辨率 |
| `doctor` | 免费 | Key、应用、价目、出图端点、任务路由、上传 |
| `plan` | 免费 | 文章 → 分镜脚本 |
| `image` | 6 点/镜 | 出图；`--ref` 改走 nano-banana 72 点/次 |
| `render` | 14 点/秒起 | 图生视频 |
| `voice` | 约 0.18 点/字 | 旁白 |
| `music` | 50 点起 | 配乐一首 |
| `make` | 以上合计 | 一键全链路 |
| `task` | 免费 | 查任务 / 补取产物 |
| `log` | 免费 | 本地台账 |

完整参数与 `--json` 契约见 `SKILL.md`「规格」一节。

---

## 常见问题

**Q：能只要图不要视频吗？**
能。跑 `plan` 再跑 `image`，`build/scene-*.png` 就是整套配图，只付 6 点/张的出图钱。

**Q：必须用 ffmpeg 吗？**
成片拼接这一步在本机完成，装个 ffmpeg 最省事；不想装就把 `clip-*.mp4` 丢进剪映，按 `concat.txt` 的顺序拖进去。

**Q：能换成竖屏吗？**
`--ratio 9:16`。提示词里的构图词也会跟着变，`render` 与 `image` 保持一致即可。

**Q：旁白念不完怎么办？**
每镜旁白上限 30 字，12 镜就是 360 字，正好 60 秒。想让文章全念完，把 `--scenes` 调大（上限 60），`cost` 会先告诉你多少钱。

---

## 文件结构

```
sanjianke-article-to-video/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       五个接口的请求 / 返回 / 实测价（原文）
│   └── troubleshooting.md    按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层（11 个子命令）
```

---

## 免责

- 生成内容的合规责任在使用者一侧：伪造他人身份、侵权素材、违法用途都不适合用本包。
- `cost` 给的是按现查单价算出的预估；真实扣费以每笔响应里的实际结算为准。
- 图片与视频链接都是临时地址，`download` 会立刻落盘，别指望链接长期有效。

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
