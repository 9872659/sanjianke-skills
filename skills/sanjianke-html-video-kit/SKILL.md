---
name: sanjianke-html-video-kit
slug: sanjianke-html-video-kit
displayName: 三剪客 · HTML 转视频引擎
description: "把 HTML/CSS 当时间轴写，一条命令渲染出确定性 MP4。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
version: 1.0.2
summary: "Hyperframes 用 data-* 属性给 DOM 标时间，用 GSAP 等可寻址动画驱动画面，无头 Chrome 逐帧截取后交给 FFmpeg 编码。本包覆盖项目结构、时间轴写法、registry 组件复用、批量出片与渲染排错。包内含完整操作文档（`SKILL.md` + `references/`）。更多 AI 算力与插件见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - HTML 转视频
  - 动画
---

# 三剪客 · HTML 转视频引擎

把 HTML/CSS 当时间轴写，一条命令渲染出确定性 MP4。

你要出一批带标题、带数据、带转场的视频，又不想为此学一套专有剪辑软件的时间轴。Hyperframes 换了个思路：**一段视频就是一个 `index.html`**。DOM 上用 `data-start` / `data-duration` / `data-track-index` 标出每个元素什么时候出现、出现多久、压在哪一层；动画交给 GSAP、CSS、WAAPI、Lottie 这些能「按时间点寻址」的运行时；渲染时无头 Chrome 从 0 秒开始逐帧 seek，取到的每帧交给 FFmpeg 编码成 MP4。

因为渲染是「给定时间 → 给定画面」，不是播放录制，同一份输入每次出来的是同一段视频。这也正是 agent 能接手的原因：它本来就会写 HTML，不需要在 JSX 里绕一圈。

和 Remotion 那类方案的核心差别只有一个——**authoring 模型**。Remotion 以 React 组件为第一公民，要打包器、要 JSX 工程；Hyperframes 就是纯 HTML 文件，`index.html` 直接用浏览器打开就能看效果，没有构建步骤。两者底层都是无头 Chrome + FFmpeg，怎么选取决于你的产出是「一次性成片」还是「长期维护的 React 工程」。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（首次必需） | `npx` 拉取 hyperframes 及其依赖包；`add` 安装 registry 条目时从远端拉取条目文件；`cloud` / `lambda` / `cloudrun` / `publish` 路径会把项目上传到对应托管服务 |
| 读取文件 | 是（必需） | 读取项目里的 `index.html`、`data-*` 属性、媒体资源（视频 / 音频 / 图片 / 字体）、`hyperframes.json`、变量 JSON 与批量渲染用的 `rows.json` |
| 写入文件 | 是（必需） | `init` 生成脚手架；`add` 安装 registry 条目；`render` 写出 MP4（默认落在 `renders/`）；`--batch` 额外写出 `manifest.json`；`snapshot` / `compare` 写出图片 |
| 凭证 | 视路径而定 | 本地渲染不需要任何 Key。`publish` 与 `cloud` 走 OAuth 登录，令牌由 CLI 自己保存在用户目录；`--variables-file` / `rows.json` 里如含业务敏感字段，请自行控制读取范围 |
| 子进程 / 后台常驻 | 是 | 调用 `npx hyperframes` 子进程、拉起无头 Chrome 与 FFmpeg；`preview --background` 会在后台常驻一个 Studio 服务（默认 `3002` 端口），需要 `preview --stop` 显式收掉 |

**密钥与费用**：本 Skill 不内嵌任何密钥、Token 或账号，也不代理转发任何请求。本地渲染不含按次费用，也不设商用门槛（上游主项目为 Apache-2.0）。如果你走 `cloud` 托管渲染，或项目里接入了外部语音、素材、模型服务，那部分开销由你自己的账号承担。请勿把任何凭据写进 `SKILL.md`、`index.html` 或提交记录。

## 触发场景

- 「我想用代码批量出片，不想开剪辑软件」——用 HTML 描述画面，CLI 渲染成 MP4。
- 「这套标题卡 / 数据条 / 下三分之一字幕，每周都要换文案重出一版」——把文案抽成变量，一行命令批量套模板。
- 「agent 能不能自己把视频做出来」——HTML 是 agent 最熟的输出格式，正好是这套引擎的输入格式。
- 「渲染结果每次都不一样，画面对不上」——检查有没有踩到 `Date.now()`、未播种随机数、无限循环这类不确定性写法。
- 「渲染出来没有声音 / 画面全黑 / 子场景没挂上」——按渲染排错流程逐项过。
- 「这个转场 / 图表 / 故障风效果，别手写了，先看看现成的」——搜 registry 再决定是否自己写。

## 快速开始

### 一、装环境

```bash
npx hyperframes doctor          # 体检：Node、FFmpeg、Chrome、Docker
npx hyperframes doctor --json   # 给 CI / agent 用；它恒定退出 0，要看 payload 里的 ok
```

硬性要求是 **Node.js 22 及以上** 加上 **FFmpeg**。Chrome 可以交给它自己管：

```bash
npx hyperframes browser ensure  # 下载并固定版本 Chrome
npx hyperframes browser path    # 打印可执行文件路径，方便脚本里引用
```

它坚持用自带的固定版本 Chrome，是因为不同 Chrome 版本的像素输出会漂移——锁住浏览器版本，同一份工程在不同机器上才渲染出同一段视频。

### 二、起一个工程

```bash
npx hyperframes init my-video
cd my-video
npx hyperframes preview --background --port 3017
```

`preview` 起的是 Studio：带完整时间轴的可视化编辑器，用户能在里面拖着改，再把工程交回来。交回给人时给 Studio 的项目 URL，不要给源码路径：

```text
http://localhost:3017/#project/my-video
```

### 三、写一个能渲染的最小合成

工程根目录的 `index.html` 就是主合成。下面这段可以直接跑：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <style>
    html, body { margin: 0; background: #0b0b10; }
    #stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
    /* .clip 是约定，给场景一个满帧盒子；运行时不读它，但 lint 会提醒你补 */
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
      // 只建一条时间轴，并挂到 window.__timelines[合成ID]
      const tl = gsap.timeline({ paused: true });
      tl.fromTo("#title", { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: .9 }, 0.2)
        .fromTo("#rule",  { scaleX: 0 },          { scaleX: 1, duration: .7, ease: "power2.out" }, 1.0);
      window.__timelines["launch"] = tl;
    </script>
  </div>
</body>
</html>
```

四个要点，每一个都对应一类渲染事故：

1. **根元素要有明确像素尺寸**（`data-width` / `data-height`）和 `data-duration`。根上的 `data-duration` 是**编译期读一次**的，脚本里改它没用；只有根不写 `data-duration` 时，运行时才会去 DOM / 时间轴里推断总长。
2. **`data-composition-id` 必须和 `window.__timelines` 的 key 一致**。只注册了一条时间轴时，key 不匹配还能兜住；注册了两条以上还不匹配，画面会冻在第 0 帧。
3. **时间轴必须 `paused: true`**。渲染是逐帧 seek，不要指望它自己播。
4. **时间窗是左闭右开** `[start, start + duration)`。动画的收尾状态要落在 `data-duration` **之前**一点点，压着边界收，最后一帧就永远出不来。

### 四、检查 → 预览 → 渲染

```bash
npx hyperframes lint                      # 边写边跑，快
npx hyperframes check                     # 最终关卡：lint + 运行时 + 布局 + 对比度
npx hyperframes snapshot --at 1.5,3.0,4.5 # 出关键帧图，肉眼看挂载成不成功
npx hyperframes render --quality draft    # 迭代用，快
npx hyperframes render --quality high --output out.mp4   # 交付用
```

验收不要只看命令退出码：

```bash
test -s out.mp4 && ffprobe -v error -show_format out.mp4
```

### 五、复用现成组件

大约四百个已托管的 block 和 component，别急着从零手写：

```bash
npx hyperframes catalog --query "reveal a headline one line at a time"
npx hyperframes add flash-through-white
npx hyperframes add data-chart
```

**搜索词必须用英文**，即使视频内容是中文。索引是按英文建的，中文 query 一个可搜索词都提不出来。用英文描述你要的「动作」，屏幕上的文案该是什么语言就写什么语言。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 装环境、起工程、项目目录长什么样、预览与渲染全流程、交付前怎么验收 | `references/quickstart.md` |
| `data-*` 每个属性什么意思、时间轴怎么写才可寻址、动画为什么对不上帧 | `references/animation-and-timeline.md` |
| 一套模板批量出几十条、变量怎么声明、并发怎么控、渲染失败怎么查 | `references/batch-and-pitfalls.md` |

## 能力边界

**覆盖**：

- **合成即 HTML**：根元素用 `data-composition-id` / `data-width` / `data-height` / `data-duration` / `data-fps` 声明画布与总长。
- **元素级时间**：`data-start` 标记时间元素，`data-duration` 给长度，`data-track-index` 只做 Studio 显示轨道（渲染不读它），`data-media-start` 切媒体入点，`data-volume` 定静态增益。
- **可见性语义**：左闭右开时间窗、时间祖先会夹住后代可见性、根的直接子元素自动获得 `position: absolute` 满帧布局、`data-hidden` 可逆隐藏。
- **动画运行时**：GSAP 为主，同时也支持 CSS 动画、WAAPI、Lottie、Three.js、Anime.js，以及自写 adapter；核心要求只有一条——动画状态能从时间值寻址。
- **子合成**：`data-composition-src` 挂载另一个 HTML，配 `data-composition-id` / `data-start` / `data-duration` / `data-width` / `data-height`，用 `data-variable-values` 做每实例覆盖。
- **变量参数化**：`<html>` 上 `data-composition-variables` 声明 schema，`data-var-src` / `data-var-text` / `--{id}` CSS 变量做声明式替换，`--variables` / `--variables-file` 在渲染时覆盖。
- **媒体**：`<video>` / `<audio>` 任意嵌套深度都能被框架找到并 seek；画面元素静音，声音走独立 `<audio>`。
- **registry 复用**：`catalog` 检索、`add` 安装 block（独立子合成）与 component（片段贴进宿主）。
- **渲染矩阵**：本地 `render`、Docker 可复现渲染、`--batch` 变量驱动批量、`lambda` / `cloudrun` 自管分布式、托管 cloud 渲染。
- **质量关卡**：`lint` 静态检查、`check` 运行时与布局审计、`snapshot` 关键帧、`compare` 并排对比、`grade-compare` 调色对比。

**不覆盖**：

- **不做素材生成**。配音、配乐、图片、图标这些要么你自己准备，要么走上游的 `media-use` 一类能力去解析和生成，本 Skill 只管把已有素材编进时间轴。
- **不做剪辑**。它不是 NLE，没有波形编辑、多机位、关键帧曲线拖拽；Studio 的时间轴能改时间与轨道，但不是给人做精细剪辑的。
- **不做浏览器录制**。如果你的诉求是「驱动一个浏览器把整个操作过程录下来」，那是另一条技术路线，不是这套引擎。
- **不做视频转码分发**。输出 MP4 / WebM / MOV / GIF / PNG 序列之后的上传、分发、CDN、超分，都在本 Skill 之外。
- **不管脚本与创意**。讲什么故事、分几个镜头、文案怎么写，属于人的判断；引擎只负责把决定好的画面准确地渲出来。
- **本 Skill 不包含任何上游源码**。正文为原创整理，只引用命令、属性名、接口路径、许可证等事实性信息。

## 依赖条件

- **运行时**：Node.js **22 及以上**（硬要求，低版本直接跑不起来）。
- **编码器**：FFmpeg 与 ffprobe 在 PATH 里；`doctor` 会分别报告版本与可用编解码器。
- **浏览器**：自带的固定版本 Chrome，用 `browser ensure` 获取。不用系统 Chrome 是为了让像素输出可复现。
- **容器（可选）**：需要跨机器逐字节一致、或者宿主环境跑不起 Chrome 时，用 `render --docker`，这需要 Docker 正在运行。
- **网络（首次）**：`npx` 拉包；`add` 安装 registry 条目时每次都要联网拉文件（只有 manifest 有缓存）。
- **磁盘**：每个 worker 会拉一个 Chrome（约 256 MB 量级），`--workers auto` 时按机器资源自己算；素材和渲染中间帧也需要留空间。

## 已知限制

- **外部脚本依赖联网**。合成里 `<script src="https://cdn.jsdelivr.net/...">` 这种写法在渲染时是真去拉的。追求可复现就把依赖本地化，或干脆内联。
- **`repeat: -1` 会出事**。无限循环没法推导总长，也可能在 seek 时错帧；要用有限次数，按 `Math.max(0, Math.floor(duration / cycle) - 1)` 算出来。
- **不能拿时钟和随机数做视觉状态**。`Date.now()` / `performance.now()` / 没播种的 `Math.random()` / 渲染期网络请求 / hover、滚动、focus 这类输入态，全部会破坏可复现性。要「随机感」就用固定种子的 PRNG。
- **不能接管 clip 的可见性**。框架靠时间窗控制 clip 显隐，所以别去 tween `display` 或裸 `visibility`；要淡出用 `autoAlpha`，要硬切用零时长 `set` 落在明确的节拍上。
- **无限 CSS / WAAPI 动画推不出时长**。这种情况必须在根上写 `data-duration`；Three.js 同理，它没有可推断的信号。
- **`crossorigin` 是禁用项**。给 `<video>` / `<audio>` 加 `crossorigin` 会让预览静默失败而渲染却正常，坑很深，所以 lint 无条件报错，没有抑制开关。
- **每个 `<audio>` 必须有 `id`**。混音器只挑 `audio[id][src]`，没 id 的音频不会被混进去，结果就是成片**没声音**，而且不会报错。
- **视频不能套在带 `data-start` 的普通祖先里**。套了会出现「取错源帧 + 播到一半消失」，而子合成宿主是例外，它传播偏移所以正常工作。
- **根上的 `data-duration` 是编译期常量**。想按不同长度出片，得直接改根上的写法，不能靠变量在运行时改。
- **绝对定位的脉冲 / 回弹装饰物要按最大帧留位**。不然会压到邻居或者被 `overflow: hidden` 切掉，这类问题自动检查未必抓得到。
- **中文内容需要自带中文字体**。默认字体族在无头 Chrome 里未必有合适的中文字形，交付前一定用 `snapshot` 看图确认。
- **许可证是 Apache-2.0**。它本身没有按次费用和商用门槛；但你引入的素材、字体、音乐各有各的授权，需要你自己核。
- **上游迭代非常快**。命令与属性以你本地 `npx hyperframes --help`、`info` 与 `catalog` 的实际输出为准，本包写的是稳定契约层面的东西。

## 自检清单

- [ ] `npx hyperframes doctor --json` 的 payload 里 `ok` 为真；Node ≥ 22、FFmpeg、Chrome 三项都过。
- [ ] 根元素写了 `data-composition-id`、`data-width`、`data-height`，并且总长有明确来源（根上 `data-duration`，或可推断的时间轴）。
- [ ] `window.__timelines["<composition-id>"]` 的 key 与根上的 `data-composition-id` 完全一致，且只有一条时间轴。
- [ ] 时间轴用 `gsap.timeline({ paused: true })`；异步构建（如 `document.fonts.ready`）时是在**构建完成后**才赋值，不是先注册空对象。
- [ ] 每个动画元素的收尾状态落在 `data-duration` 之前，没有压着右开边界。
- [ ] 没有 CSS 初始 `transform` 和 GSAP 对同一属性同时下手（该用 `fromTo` 把初值写进 tween）。
- [ ] 每个 `<video>` / `<audio>` 都有 `id`，都没有 `crossorigin`，`<video>` 都带 `muted` 和 `playsinline`。
- [ ] 声音放在独立的 `<audio>` 上，没有用 `<video>` 出声。
- [ ] 没有把 `<video data-start>` 放进另一个带 `data-start` 的普通元素里。
- [ ] 全页没有 `Date.now()` / `performance.now()` / 未播种随机数 / `repeat: -1` / 渲染期网络请求 / 输入态驱动的动画。
- [ ] 没有 tween 任何 clip 元素的 `display` 或裸 `visibility`。
- [ ] `npx hyperframes lint` 零 error；有 error 时 `check` 的布局与对比度数字是 0，不能当通过看。
- [ ] `npx hyperframes check` 通过，需要时加了 `--snapshots` 看标注帧。
- [ ] 用了子合成时，给每个宿主时段抓了中间帧 `snapshot`，逐个确认没有「内容挤在左上角 / 图标被拉到画布大小 / 时间轴注册超时」。
- [ ] 交付前用 `preview --background` 起了 Studio，把项目 URL 交给人确认过，再渲染。
- [ ] 成片做了落盘验证：文件存在、非空、时长合理（`ffprobe`）。
- [ ] 用了 `--batch` 时，`manifest.json` 里没有 failed 行，每条输出都非空且时长合理。
- [ ] 所有素材、字体、音乐的授权都确认过，可商用。

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
