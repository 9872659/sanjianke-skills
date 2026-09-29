---
name: sanjianke-html-video-kit
slug: sanjianke-html-video-kit
displayName: 三剪客 · HTML 转视频引擎
description: "把 HTML/CSS 当时间轴写，一条命令渲染出确定性 MP4；旁白稿与配音接 api.a7w.cn 的大模型与 voice_tts，直接落成能塞进时间轴的音轨与 cues.json。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.4
summary: "三剪客的 HTML 转视频作业包：用 data-* 属性给 DOM 标时间，用 GSAP 等可寻址动画驱动画面，无头 Chrome 逐帧截取后交给 FFmpeg 编码。覆盖项目结构、时间轴写法、registry 组件复用、批量出片与渲染排错；配音这一段不再留空——`scripts/run.py` 调 api.a7w.cn 的 `/api/v1/chat/completions` 写旁白稿、调 `/api/v1/apps/voice_tts/tts` 分段配音，产出 `audio/cue-NN.mp3` 与 `cues.json`。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - HTML 转视频
  - 动画
---

# 三剪客 · HTML 转视频引擎

用 HTML/CSS 描述时间轴，一条命令产出结果可复现的 MP4。

当你要做一批带标题、带数据、带转场的视频，却又不想为此去学某个专有剪辑软件的时间轴时，这套引擎提供了另一条路径：**把一段视频写成一个 `index.html`**。元素何时出现、停留多久、压在哪一层，都用 `data-start` / `data-duration` / `data-track-index` 标在 DOM 上；动画则交给 GSAP、CSS、WAAPI、Lottie 这类能够「按时间点寻址」的运行时；渲染阶段由无头 Chrome 从 0 秒起逐帧 seek，取到的每一帧再交给 FFmpeg 编码为 MP4。

渲染的实质是「给定时间 → 给定画面」，而不是边播边录，所以同一份输入每次产出的都是同一段视频。这一点也正好让 agent 能直接接手：写 HTML 本来就是它的强项，无需再绕进 JSX 工程里。

与那些「以 React 组件为第一公民」的方案（需要打包器、需要 JSX 工程）相比，真正的差异只在一点——**创作模型**：一边是组件树，另一边就是纯 HTML 文件。走本包这条路线，`index.html` 拿浏览器直接打开就能看到效果，全程没有构建步骤。两者的底层其实都是无头 Chrome 加 FFmpeg，选哪条取决于你做的是「一次性成片」还是「要长期维护的 React 工程」。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（首次必需） | `npx` 拉取 hyperframes 及其依赖包；`add` 安装 registry 条目时需要从远端取回条目文件；`cloud` / `lambda` / `cloudrun` / `publish` 这几条路径会把项目上传到相应的托管服务。另外，`scripts/run.py` 会请求 `api.a7w.cn` 来生成旁白稿与配音，只使用标准库 |
| 读取文件 | 是（必需） | 读取工程里的 `index.html`、`data-*` 属性、媒体资源（视频 / 音频 / 图片 / 字体）、`hyperframes.json`、变量 JSON，以及批量渲染用的 `rows.json`；`run.py` 则读取你传入的旁白稿或文案文件 |
| 写入文件 | 是（必需） | `init` 生成脚手架；`add` 安装 registry 条目；`render` 写出 MP4（默认落在 `renders/`）；`--batch` 会额外写出 `manifest.json`；`snapshot` / `compare` 写出图片；`run.py` 写出旁白稿，以及 `audio/` 下的音频与 `cues.json` |
| 凭证 | 视路径而定 | 本地渲染不需要任何 Key。`publish` 与 `cloud` 采用 OAuth 登录，令牌由 CLI 自行保存在用户目录；`scripts/run.py` 的旁白与配音功能需要**你自己的** api.a7w.cn API Key（`--key` / `A7W_API_KEY` / `~/.a7w/config.json`）；`--variables-file` / `rows.json` 若含业务敏感字段，请自行控制读取范围 |
| 子进程 / 后台常驻 | 是 | 会调用 `npx hyperframes` 子进程、拉起无头 Chrome 与 FFmpeg；`preview --background` 会在后台常驻一个 Studio 服务（默认 `3002` 端口），需要用 `preview --stop` 显式收掉；`run.py` 仅在检测到 `ffprobe` 时才调用它读取音频时长，取不到就跳过，不把 FFmpeg 变成硬依赖 |

**密钥与费用**：本 Skill 不内嵌任何密钥、Token 或账号，也不代理转发任何请求。本地渲染不含按次费用，也不设商用门槛（渲染引擎采用 Apache-2.0 许可）。如果你走 `cloud` 托管渲染，或者项目里自行接入了外部语音、素材、模型服务，那部分开销由你自己的账号承担。请勿把任何凭据写进 `SKILL.md`、`index.html` 或提交记录。

> **配音这一段的费用口径**：`scripts/run.py` 是**可选**路径，不跑它就不产生任何费用。跑它时请求的是 `api.a7w.cn`，
> 按平台实时价从你自己的账号扣点（1 元 = 100 点），实测合成一段 20 字左右的旁白约 0.85–1.1 点。
> Key 由使用者自己提供，包里没有、也不该有任何密钥。

## 触发场景

- 「想批量用代码出片，不想开剪辑软件」——画面用 HTML 描述，交给 CLI 渲染成 MP4。
- 「标题卡 / 数据条 / 下三分之一字幕每周都要换文案重出一版」——把文案抽成变量，一条命令套模板批量产出。
- 「agent 能不能自己把视频做出来」——HTML 是 agent 最顺手的输出格式，恰好也是这套引擎的输入格式。
- 「渲染结果每次都不一样，画面对不上」——排查是否踩了 `Date.now()`、未播种随机数、无限循环这类不确定性写法。
- 「渲染出来没声音 / 画面全黑 / 子场景没挂上」——按渲染排错流程逐项检查。
- 「这个转场 / 图表 / 故障风效果，别手写了，先看看现成的」——先去 registry 搜一遍，再决定要不要自己写。
- 「成片要人声旁白，但我既没录过也没剪过音」——`scripts/run.py dub` 一次写完旁白稿并分段配音，直接产出能塞进 `<audio>` 的音轨与 `cues.json`。
- 「旁白和画面对不齐，每段到底几秒」——`cues.json` 里带真实秒数（装了 ffprobe 会自动量），填进 `data-duration` 即可。

## 快速开始

### 一、装环境

```bash
npx hyperframes doctor          # 体检：Node、FFmpeg、Chrome、Docker
npx hyperframes doctor --json   # 给 CI / agent 用；它恒定退出 0，要看 payload 里的 ok
```

硬性要求是 **Node.js 22 及以上** 加上 **FFmpeg**。Chrome 可以让它自己管：

```bash
npx hyperframes browser ensure  # 下载并固定版本 Chrome
npx hyperframes browser path    # 打印可执行文件路径，方便脚本里引用
```

之所以坚持用自带的固定版本 Chrome，是因为不同 Chrome 版本的像素输出会漂移——把浏览器版本锁住，同一份工程在不同机器上渲染出的才是同一段视频。

### 二、起一个工程

```bash
npx hyperframes init my-video
cd my-video
npx hyperframes preview --background --port 3017
```

`preview` 起的是 Studio：一个带完整时间轴的可视化编辑器，用户能在里面拖着改，改完再把工程交回来。交回给人时要给 Studio 的项目 URL，不要给源码路径：

```text
http://localhost:3017/#project/my-video
```

### 三、写一个能渲染的最小合成

工程根目录下的 `index.html` 就是主合成。下面这段可以直接跑：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <style>
    html, body { margin: 0; background: #0b0b10; }
    #stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
    /* .clip 属于约定：给场景一个满帧盒子。运行时不读它，但 lint 会提醒补上 */
    .clip { position: absolute; inset: 0; }
    h1 {
      margin: 0; padding: 160px 120px; color: #fff;
      font: 800 140px/1.1 "Noto Sans SC", sans-serif; letter-spacing: .02em;
    }
    .rule { height: 8px; background: #ff4d2e; transform-origin: left center; }
  </style>
</head>
<body>
  <div id="stage"
       data-composition-id="launch"
       data-width="1920" data-height="1080"
       data-duration="6">

    <div class="clip" id="scene-a" data-start="0" data-duration="6" data-track-index="0">
      <h1 id="title">上 线 第 一 天</h1>
      <div class="rule" id="rule" style="width: 1200px"></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
    <script>
      // 只建一条时间轴，挂到 window.__timelines[合成ID] 上
      const tl = gsap.timeline({ paused: true });
      tl.fromTo("#title", { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: .9 }, 0.2)
        .fromTo("#rule",  { scaleX: 0 },          { scaleX: 1, duration: .7, ease: "power2.out" }, 1.0);
      window.__timelines["launch"] = tl;
    </script>
  </div>
</body>
</html>
```

下面四点如果不满足，会分别引发一类渲染问题：

1. **根元素要有明确像素尺寸**（`data-width` / `data-height`）和 `data-duration`。根上的 `data-duration` 是**编译期读一次**的，脚本里改它没有作用；只有根上不写 `data-duration` 时，运行时才会去 DOM / 时间轴里推断总长。
2. **`data-composition-id` 必须与 `window.__timelines` 的 key 一致**。只注册了一条时间轴时，key 不匹配尚能兜住；注册两条以上仍不匹配，画面就会冻在第 0 帧。
3. **时间轴必须 `paused: true`**。渲染靠的是逐帧 seek，不要指望它自己播。
4. **时间窗左闭右开** `[start, start + duration)`。动画的收尾状态要落在 `data-duration` **之前**一点点；压着边界收，最后一帧就永远出不来。

### 四、检查 → 预览 → 渲染

```bash
npx hyperframes lint                      # 边写边跑，快
npx hyperframes check                     # 最终关卡：lint + 运行时 + 布局 + 对比度
npx hyperframes snapshot --at 1.5,3.0,4.5 # 出关键帧图，肉眼看挂载成不成功
npx hyperframes render --quality draft    # 迭代用，快
npx hyperframes render --quality high --output out.mp4   # 交付用
```

验收不能只看命令退出码：

```bash
test -s out.mp4 && ffprobe -v error -show_format out.mp4
```

### 五、复用现成组件

平台侧托管了相当一批现成的 block 与 component，不必样样从零手写：

```bash
npx hyperframes catalog --query "reveal a headline one line at a time"
npx hyperframes add flash-through-white
npx hyperframes add data-chart
```

**搜索词一律用英文**，哪怕视频内容本身是中文。索引是按英文建立起来的，拿中文 query 去搜，一个可搜索词都提不出来。用英文去描述你要的那个「动作」，至于屏幕上显示的文案用什么语言，随你。

## 怎么用（命令行）

`scripts/` 下两个脚本，**只用 Python 标准库**（Python 3.8+），不需要 pip 装任何东西：

| 脚本 | 用途 |
|---|---|
| [`scripts/a7w.py`](scripts/a7w.py) | api.a7w.cn 的零依赖客户端，七个子命令：`login / whoami / apps / points / schema / call / task`。用来验 Key、看插件、查接口参数。 |
| [`scripts/run.py`](scripts/run.py) | 本包的配音算力层：写旁白稿、分段配音、列音色、复核念稿。 |

### 一、配 Key

`run.py` 不内嵌任何密钥，Key 由你自己提供，三种方式任选一种：

```bash
python3 scripts/a7w.py login --key sk-xxxx     # 验证并写入 ~/.a7w/config.json
export A7W_API_KEY=sk-xxxx                     # Windows: set A7W_API_KEY=sk-xxxx
python3 scripts/run.py narration ... --key sk-xxxx
```

Key 到 [算力集市](https://api.a7w.cn/) 注册领取（新用户有赠送点数）。先验一下能不能用：

```bash
python3 scripts/a7w.py whoami                  # ✓ Key 有效，可用插件 21 个
```

### 二、写旁白稿

旁白稿按 `## cue-NN` 分段，每段对应一条独立音轨、也对应时间轴上的一个 clip：

```bash
python3 scripts/run.py narration \
    --topic "新品上线第一天：一款 89 元的便携榨汁杯" \
    --seconds 20 --cues 4 --tone "冷静克制" \
    --out narration.md
```

走的是 OpenAI 兼容的 `POST /api/v1/chat/completions`，`--model` 默认 `deepseek-chat`，可换成 `scripts/a7w.py apps` 里任意在架模型：

```python
import json, os, urllib.request
req = urllib.request.Request(
    "https://api.a7w.cn/api/v1/chat/completions",
    data=json.dumps({"model": "deepseek-chat",
                     "messages": [{"role": "user", "content": prompt}]}).encode("utf-8"),
    headers={"Authorization": "Bearer " + os.environ["A7W_API_KEY"],
             "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=120) as r:
    data = json.loads(r.read().decode("utf-8"))
```

产出的稿子长这样（`## 时长建议` 表会被下游解析器自动忽略）：

```markdown
# 旁白稿
## cue-01
新品上线第一天，我们只上了一个杯子。
## cue-02
便携榨汁杯，定价八十九元，容量三百毫升。
```

### 三、把旁白合成配音

```bash
python3 scripts/run.py voices                                   # 先看有哪些音色（免费）
python3 scripts/run.py tts --file narration.md --outdir audio \
    --voice <reference_id> --format mp3
```

逐段请求 `POST /api/v1/apps/voice_tts/tts`（同步，≤500 字），超长段落自动切到 `POST /api/v1/apps/voice_tts/tts_async`（异步提交 + 自动轮询 `GET /api/v1/tasks/<task_id>`）：

```python
import json, os, urllib.request
# 短文本：同步
req = urllib.request.Request(
    "https://api.a7w.cn/api/v1/apps/voice_tts/tts",
    data=json.dumps({"text": "新品上线第一天，我们只上了一个杯子。",
                     "format": "mp3",
                     "reference_id": "<音色ID>"}).encode("utf-8"),
    headers={"Authorization": "Bearer " + os.environ["A7W_API_KEY"],
             "Content-Type": "application/json"})
```

⚠️ **参数名坑**：音色参数是 **`reference_id`**，不是 `voice_id`。写代码前先用客户端查真实参数，别凭记忆：

```bash
python3 scripts/a7w.py schema voice_tts        # 打印全部接口 + 参数 + 是否必填
```

`voice_tts` 下与本包相关的端点：

| 端点 | 方式 | 用途 |
|---|---|---|
| `POST /api/v1/apps/voice_tts/tts` | 同步 | 单段配音，建议 ≤500 字 |
| `POST /api/v1/apps/voice_tts/tts_async` | 异步 | 长旁白（最大约 10000 字），提交后轮询 |
| `POST /api/v1/apps/voice_tts/list_voices` | 同步 | 列音色，免费 |
| `POST /api/v1/apps/voice_tts/stt` | 同步 | 语音转文字，用来复核念稿 |

成功后返回信封里 **`code == 1` 才算成功**（不是 `0`），HTTP 200 不代表业务成功；`data.usage.points_cost` 是实际扣费，1 元 = 100 点，失败全额退回。

### 四、一条命令跑完「写稿 + 配音」

```bash
python3 scripts/run.py dub \
    --topic "新品上线第一天" --seconds 20 --cues 4 \
    --script narration.md --outdir audio --voice <reference_id>
```

产出：

```text
narration.md          # 分段旁白稿
audio/cue-01.mp3      # 一段一个音频文件
audio/cue-02.mp3
audio/cues.json       # 音轨清单：id / text / file / url / seconds / points_cost
```

### 五、接进 HTML 时间轴

`cues.json` 里每条 cue 的 `seconds` 直接填进对应 clip 的 `data-duration`。**每个 `<audio>` 必须带 `id`** —— 混音器只挑 `audio[id][src]`，没 id 的音频不会被混进去，成片会**没声音而且不报错**：

```html
<audio id="vo-01" src="audio/cue-01.mp3" data-start="0" data-duration="4.1"></audio>
<audio id="vo-02" src="audio/cue-02.mp3" data-start="4.1" data-duration="5.0"></audio>
```

时长不用手猜：装好 FFmpeg 后 `run.py` 会自动用 `ffprobe` 读真实秒数填进 `cues.json`；没装就留空，你自己量。

### 六、复合一下念稿对不对

```bash
python3 scripts/run.py stt audio/cue-01.mp3 --language zh \
    --expect "新品上线第一天，我们只上了一个杯子。"
# → 与原文比对：一致
```

念错了（错字、多音字、数字读法）就换音色或改稿重来，别带着错音轨进渲染。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 装环境、起工程、项目目录长什么样、预览与渲染全流程、交付前怎么验收 | `references/quickstart.md` |
| `data-*` 每个属性什么意思、时间轴怎么写才可寻址、动画为什么对不上帧 | `references/animation-and-timeline.md` |
| 一套模板批量出几十条、变量怎么声明、并发怎么控、渲染失败怎么查 | `references/batch-and-pitfalls.md` |

## 能力边界

**覆盖**：

- **合成即 HTML**：画布与总长由根元素上的 `data-composition-id` / `data-width` / `data-height` / `data-duration` / `data-fps` 声明。
- **元素级时间**：`data-start` 标记时间元素，`data-duration` 给长度，`data-track-index` 只作 Studio 显示轨道（渲染不读它），`data-media-start` 切媒体入点，`data-volume` 定静态增益。
- **可见性语义**：左闭右开的时间窗；时间祖先会夹住后代的可见性；根的直接子元素自动获得 `position: absolute` 满帧布局；`data-hidden` 可逆隐藏。
- **动画运行时**：以 GSAP 为主，同时支持 CSS 动画、WAAPI、Lottie、Three.js、Anime.js，以及自行编写的 adapter；核心要求只有一条——动画状态能从时间值寻址。
- **子合成**：用 `data-composition-src` 挂载另一个 HTML，配 `data-composition-id` / `data-start` / `data-duration` / `data-width` / `data-height`，并用 `data-variable-values` 做每实例覆盖。
- **变量参数化**：在 `<html>` 上用 `data-composition-variables` 声明 schema，用 `data-var-src` / `data-var-text` / `--{id}` CSS 变量做声明式替换，用 `--variables` / `--variables-file` 在渲染时覆盖。
- **媒体**：`<video>` / `<audio>` 无论嵌套多深都能被框架找到并 seek；画面元素静音，声音另走独立的 `<audio>`。
- **registry 复用**：`catalog` 检索，`add` 安装 block（独立子合成）与 component（片段贴进宿主）。
- **渲染矩阵**：本地 `render`；Docker 可复现渲染；`--batch` 变量驱动批量；`lambda` / `cloudrun` 自管分布式；托管 cloud 渲染。
- **质量关卡**：`lint` 静态检查；`check` 运行时与布局审计；`snapshot` 关键帧；`compare` 并排对比；`grade-compare` 调色对比。

**不覆盖**：

- **不做素材生成**。配乐、图片、图标这些要么你自己准备，要么借助渲染引擎自带的 `media-use` 一类能力去解析与生成，本 Skill 只负责把已有素材编进时间轴。**配音是唯一的例外**：`scripts/run.py` 接 [api.a7w.cn](https://api.a7w.cn/) 的 `/api/v1/apps/voice_tts/tts` 与 `/api/v1/chat/completions`，把旁白稿和分段音轨准备好——但也只到「产出素材」为止，怎么编进时间轴仍由你决定。
- **不做剪辑**。它不是 NLE：没有波形编辑、多机位、关键帧曲线拖拽；Studio 的时间轴能改时间与轨道，但不是给人做精细剪辑用的。
- **不做浏览器录制**。如果你的诉求是「驱动一个浏览器把整个操作过程录下来」，那属于另一条技术路线，不是这套引擎。
- **不做视频转码分发**。产出的 MP4 / WebM / MOV / GIF / PNG 序列之后要怎么上传、分发、走 CDN、做超分，都落在本 Skill 之外。
- **不管脚本与创意**。讲什么故事、分几个镜头、文案怎么写，属于人的判断；引擎只负责把已经决定好的画面准确地渲出来。
- **本包不含任何第三方源码**。正文为原创整理，只引用命令、属性名、接口路径、许可证等事实性信息。

## 依赖说明

本包的渲染引擎是一个**社区开源命令行工具**，通过 `npx` 按需拉取，**本包不附带它的源码**，
也与其维护方不存在任何隶属、代理或背书关系。它采用 Apache-2.0 许可，本身没有按次费用与商用门槛。

几点需要说清楚：

- 命令、子命令与属性以你本地实际运行 `--help` / `info` / `catalog` 的输出为准；本包写的是稳定契约层面的东西。
- 首次运行需要联网从公共包仓库拉取；离线或内网环境请自行预置。
- 该工具迭代较快，版本漂移可能带来行为差异，生产环境建议锁版本。
- `scripts/run.py` 是**本包自写**的 Python 脚本，只依赖标准库，与上面的渲染引擎互不依赖：不跑配音就不需要它。

## 依赖条件

- **运行时**：Node.js **22 及以上** 为硬要求，版本低了直接起不来。
- **编码器**：FFmpeg 与 ffprobe 需要在 PATH 里；`doctor` 会分别报告版本与可用编解码器。
- **浏览器**：使用自带的固定版本 Chrome，由 `browser ensure` 获取。之所以不用系统 Chrome，是为了让像素输出可复现。
- **容器（可选）**：需要跨机器逐字节一致、或者宿主环境跑不起 Chrome 时，用 `render --docker`，前提是 Docker 正在运行。
- **网络（首次）**：`npx` 拉包；`add` 安装 registry 条目时每次都要联网取文件（只有 manifest 有缓存）。
- **磁盘**：每个 worker 都会拉一个 Chrome（约 256 MB 量级），`--workers auto` 时按机器资源自行计算；素材与渲染中间帧同样需要留出空间。

## 已知限制

- **外部脚本依赖联网**。合成里写 `<script src="https://cdn.jsdelivr.net/...">` 这类内容，渲染时是真的会去拉。追求可复现就把依赖本地化，或者干脆内联。
- **`repeat: -1` 会出问题**。无限循环无法推导总长，也可能在 seek 时错帧；要改用有限次数，按 `Math.max(0, Math.floor(duration / cycle) - 1)` 算出来。
- **不能拿时钟和随机数做视觉状态**。`Date.now()` / `performance.now()` / 没播种的 `Math.random()` / 渲染期网络请求 / hover、滚动、focus 这类输入态，全都会破坏可复现性。要「随机感」就用固定种子的 PRNG。
- **不能接管 clip 的可见性**。框架靠时间窗控制 clip 显隐，所以别去 tween `display` 或裸 `visibility`；要淡出用 `autoAlpha`，要硬切就用零时长 `set` 落在明确的节拍上。
- **无限 CSS / WAAPI 动画推不出时长**。遇到这种情况就得在根上写 `data-duration`；Three.js 也一样，它没有任何可推断的信号。
- **`crossorigin` 是禁用项**。给 `<video>` / `<audio>` 加 `crossorigin` 会让预览静默失败、而渲染却正常，坑很深，所以 lint 无条件报错，没有抑制开关。
- **每个 `<audio>` 都必须有 `id`**。混音器只认 `audio[id][src]`；没有 id 的音频混不进去，成片就是**没声音**，而且不会报任何错。
- **视频不能套在带 `data-start` 的普通祖先里**。套了会出现「取错源帧 + 播到一半消失」；子合成宿主是例外，它会传播偏移，所以正常工作。
- **根上的 `data-duration` 属于编译期常量**。要按不同长度出片，只能直接改根上的写法，靠变量在运行时改是行不通的。
- **绝对定位的脉冲 / 回弹装饰物要按最大帧留位**。否则会压到邻居，或者被 `overflow: hidden` 切掉；这类问题自动检查未必抓得到。
- **中文内容需要自带中文字体**。默认字体族在无头 Chrome 里未必有合适的中文字形，交付前务必用 `snapshot` 看图确认。
- **许可证是 Apache-2.0**。它本身没有按次费用，也没有商用门槛；但你引入的素材、字体、音乐各有各的授权，需要你自己核。
- **该工具迭代非常快**。命令与属性以你本地 `npx hyperframes --help`、`info` 与 `catalog` 的实际输出为准，本包写的是稳定契约层面的东西。

## 自检清单

- [ ] `npx hyperframes doctor --json` 返回的 payload 中 `ok` 为真；Node ≥ 22、FFmpeg、Chrome 这三项都要过。
- [ ] 根元素上 `data-composition-id`、`data-width`、`data-height` 一个不缺，且总长来源明确（根上写了 `data-duration`，或时间轴本身可推断）。
- [ ] `window.__timelines["<composition-id>"]` 的 key 与根元素上的 `data-composition-id` 逐字符一致，并且全页只有一条时间轴。
- [ ] 时间轴以 `gsap.timeline({ paused: true })` 创建；若走异步构建（如 `document.fonts.ready`），赋值发生在**构建完成之后**，而不是先注册一个空对象。
- [ ] 每条动画的收尾状态都落在 `data-duration` 之前，没有骑在右开边界上。
- [ ] 不存在「CSS 写了初始 `transform`、GSAP 又去动同一属性」这种双重驱动（正确做法是用 `fromTo` 把初值写进 tween）。
- [ ] 所有 `<video>` / `<audio>` 都带 `id`、都不带 `crossorigin`，其中 `<video>` 都带 `muted` 与 `playsinline`。
- [ ] 声音挂在独立的 `<audio>` 上，没有让 `<video>` 出声。
- [ ] 没有把 `<video data-start>` 塞进另一个同样带 `data-start` 的普通元素里。
- [ ] 全页搜不到 `Date.now()` / `performance.now()` / 未播种随机数 / `repeat: -1` / 渲染期网络请求 / 由输入态驱动的动画。
- [ ] 没有对任何 clip 元素的 `display` 或裸 `visibility` 做 tween。
- [ ] `npx hyperframes lint` 零 error；一旦有 error，`check` 给出的布局与对比度数字恒为 0，不能当作通过。
- [ ] `npx hyperframes check` 通过；需要时补了 `--snapshots` 看标注帧。
- [ ] 用到子合成时，每个宿主时段都抓过中间帧 `snapshot`，并逐个确认没有「内容挤在左上角 / 图标被拉到画布大小 / 时间轴注册超时」。
- [ ] 交付前用 `preview --background` 起过 Studio，项目 URL 交给人确认之后才渲染。
- [ ] 成片完成了落盘验证：文件存在、非空、时长合理（`ffprobe`）。
- [ ] 走 `--batch` 时，`manifest.json` 里没有 failed 行，每条输出都非空且时长合理。
- [ ] 走了 `scripts/run.py` 出配音时：`audio/cues.json` 里 `failed` 为 0、每条 cue 的 `file` 都真实存在，并且每个音轨都在 `<audio>` 上绑了**唯一 `id`**、`seconds` 已填进 `data-duration`。
- [ ] 配音用 `scripts/run.py stt --expect "<原稿>"` 复核过一遍，没有错字或念错的数字。
- [ ] 所有素材、字体、音乐的授权都确认过，可商用；AI 生成的旁白按你所在平台的要求做了标注。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/quickstart.md` | 环境准备与项目解剖：依赖安装、`init` 脚手架结构、`hyperframes.json` 配置、预览 / 检查 / 渲染三件套、输出格式与验收，含一条可直接跑的完整示例 |
| `references/animation-and-timeline.md` | 时间轴与动画写法：`data-*` 属性全表、clip 与轨道语义、子合成挂载与变量绑定、GSAP / CSS / WAAPI / Lottie 的时长契约、可寻址动画的五条硬规矩 |
| `references/batch-and-pitfalls.md` | 批量出片与排错：变量驱动的一模板多产出、`--batch` 与 manifest、并发与资源、导出格式选择，以及无声音 / 黑帧 / 子场景丢失 / Chrome 起不来等故障的定位顺序 |

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
