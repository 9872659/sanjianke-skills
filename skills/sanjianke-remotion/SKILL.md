---
name: sanjianke-remotion
slug: sanjianke-remotion
displayName: 三剪客 · 用 React 写代码生成视频
description: "把视频当成网页来渲染：用 React 组件描述画面，用帧号驱动动画，用命令行批量出片。含 create-video 脚手架、Studio 预览、render/still/bundle 真实参数、Chrome 与 FFmpeg 依赖、参数化批量渲染，以及许可证的商业使用边界。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "同一套 React 代码，既能预览又能出片，还能改个参数就批量生成上千条不同内容的视频。这份技能讲清 Remotion 怎么装、怎么建项目、怎么渲染、怎么用 Input Props 做参数化量产，以及 Chrome 下载、字体加载、时间轴错位这些一上手就撞上的坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 素材
---

# 三剪客 · 用 React 写代码生成视频

要给一千个商品各出一条 15 秒短片，每条只换标题、价格和封面图；或者要做一个数据一周一更新就自动重渲染的榜单视频——这类需求用剪辑软件做就是人肉苦力，用 Remotion 就是写一个 React 组件再循环调用一次。

它的思路是把「视频」还原成「一串按帧绘制的网页」：你用 `<Composition>` 声明画布尺寸、帧率、总帧数，用 `useCurrentFrame()` 拿到当前帧号，用 `interpolate()` / `spring()` 把帧号映射成位移、缩放、透明度。剩下的交给它——它会启动一个无头浏览器逐帧截图，再用内置的 FFmpeg 编码成 MP4。所以它**不是剪辑工具，而是渲染引擎**：素材要提前备好，时间轴要在代码里算。

**上游项目**：`Remotion`　**仓库**：https://github.com/remotion-dev/remotion

## 什么时候用 / 不用

**用它**：

- 要**批量出片**：同一套版式换文案、图片、数据，生成几十上百条视频。这是它最不可替代的场景。
- 视频内容由**数据驱动**：周榜、财报、比分、跑马灯字幕，数据一更新就重渲染，不需要人工重剪。
- 想要**像素级可控**的动效：字体、间距、缓动曲线、蒙版都用代码精确指定，不受手工拖拽的手感影响。
- 团队的**版式系统要进版本管理**：字幕条、下三分之一、片头片尾做成可复用组件，走 Git 与 Code Review。
- 要把出片能力**做成产品**：在网页里嵌 Player 做预览，后端接渲染任务队列，用户点一下生成自己的视频。

**不要用它**：

- **一次性的素材剪辑**。就剪一条片子、拼几个片段、卡个点，用剪辑软件几分钟的事，写代码反而慢十倍。
- **处理长时间、大体积的实拍素材**。逐帧过浏览器渲染，长视频的时间与内存开销都很大，不是它的主场。
- **需要专业调色、多轨混音、复杂特效合成**。它输出的是网页能画出来的东西，专业后期能力不在它的范围内。
- **想零代码、可视化拖拽完成**。它本质是写代码，学习曲线就是 React + CSS；不接受写代码的团队用不起来。
- **组织规模或用量已到许可证门槛却不打算付费**。这是硬约束，不是技术问题——商用前必须先确认自己落在哪一档。

## 安装

前置条件是 **Node.js**（版本下限以官方文档当前说明为准）和一个**包管理器**（npm / Yarn / pnpm / Bun 都行）。

不需要手动装 FFmpeg 和 Chrome：Remotion 自带一份平台相关的 FFmpeg 二进制，也会在本机找不到兼容 Chrome 时自动下载一份；本机已有 Chrome 时会优先复用。

新建项目（用官方脚手架，而不是手动 `npm init`）：

```bash
# 交互式，会问你选哪个模板
npx create-video@latest

# 非交互式：直接建一个最小空项目 my-video
npx create-video --yes --blank my-video

# 非交互式 + 不装 TailwindCSS
npx create-video --yes --blank --no-tailwind my-video
```

`--yes` 是「全部用默认值、不问问题」，适合脚本和 Agent 调用；它要求同时给出一个模板 flag 和一个目录名，并且在已经处于某个 Git 仓库内部时会直接失败。可用模板见 `npx create-video --help`（`--blank`、`--hello-world`、`--tiktok`、`--audiogram`、`--three`、`--skia` 等）。

把 Remotion 加进一个已有前端项目：

```bash
npm i remotion @remotion/cli
```

依赖版本必须**完全一致**——`remotion`、`@remotion/cli` 以及任何 `@remotion/*` 包版本号不一致会直接报错。官方为此提供了命令：

```bash
# 列出并校验各 Remotion 包版本是否一致
npx remotion versions

# 把所有 Remotion 包升到同一版本
npx remotion upgrade

# 按当前版本安装指定的 Remotion 包
npx remotion add @remotion/media
```

## 常用操作

**1. 列出项目里有哪些 composition（最容易踩坑的第一步）**

```bash
npx remotion compositions
npx remotion compositions src/index.ts
```

只打印 ID 列表、不带其他输出：

```bash
npx remotion compositions --quiet
```

渲染报「找不到 composition」时，先用它确认 ID 到底叫什么——ID 只允许字母、数字和 `-`。

**2. 起本地预览界面（Studio）**

```bash
npx remotion studio
npx remotion studio src/index.ts
```

Studio 里可以拖时间轴、实时改 props、点按钮出片，是调动画的主要工作台。

**3. 渲染一条视频**

```bash
# 最简：composition ID + 输出路径
npx remotion render HelloWorld out/video.mp4

# 不写 ID 会弹交互式选择器
npx remotion render
```

常用参数（均为官方 CLI 文档中真实存在的 flag）：

```bash
# 换编码器：h264（默认）/ h265 / vp8 / vp9 / av1 / prores / gif 等
npx remotion render HelloWorld out/video.webm --codec=vp8

# 覆盖画布尺寸与帧率（不改代码，临时试不同规格）
npx remotion render HelloWorld out/v.mp4 --width=1080 --height=1920 --fps=30

# 只渲染片段：区间、区间拼接
npx remotion render HelloWorld out/part.mp4 --frames=0-99
npx remotion render HelloWorld out/part.mp4 --frames=0-99,150-199

# 输出图片序列而不是视频
npx remotion render HelloWorld out/frames --sequence

# 放大输出：720p 画布按 1.5 倍渲成 1080p，矢量元素更清晰
npx remotion render HelloWorld out/v.mp4 --scale=1.5

# 提速：并发线程数，也可以给百分比
npx remotion render HelloWorld out/v.mp4 --concurrency=4
npx remotion render HelloWorld out/v.mp4 --concurrency=50%

# 质量与体积：CRF 越低越清晰，与 --video-bitrate 互斥
npx remotion render HelloWorld out/v.mp4 --crf=18

# 硬件编码（需显卡支持）：disable / if-possible / required
npx remotion render HelloWorld out/v.mp4 --hardware-acceleration=if-possible

# 排查卡住：单帧等待 delayRender 的超时，单位毫秒，默认 30000
npx remotion render HelloWorld out/v.mp4 --timeout=60000
```

其余常用 flag 还有 `--props`、`--pixel-format`、`--image-format`、`--jpeg-quality`、`--audio-bitrate`、`--video-bitrate`、`--muted`、`--log`（`error`/`warn`/`info`/`verbose`）、`--config`、`--env-file`、`--browser-executable`、`--chrome-mode`、`--overwrite`。完整清单以 `npx remotion render --help` 与官方 CLI 文档为准。

**4. 渲染一张静态图（做封面图很省事）**

```bash
npx remotion still HelloWorld out/cover.png
npx remotion still HelloWorld out/cover.png --frame=45
```

**5. 参数化渲染：一套代码出 N 条不同的片子**

在组件里用 `getInputProps()` 读取外部传入的参数：

```tsx
import {Composition, getInputProps, useCurrentFrame} from 'remotion';

const MyComp = () => {
  const {title} = getInputProps() as {title: string};
  const frame = useCurrentFrame();
  return <h1 style={{opacity: Math.min(1, frame / 30)}}>{title}</h1>;
};

export const Root = () => (
  <Composition
    id="Ad"
    component={MyComp}
    durationInFrames={150}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{title: '默认标题'}}
  />
);
```

渲染时用 `--props` 传参：

```bash
npx remotion render Ad out/a.mp4 --props=./props-a.json
```

> **Windows 上不要写内联 JSON**：`--props='{"title":"x"}'` 里的双引号会被 shell 吃掉。写成 JSON 文件再用 `--props=./props.json` 是各平台都稳的做法。

批量出片就是在 Node 脚本里循环调用渲染 API，或多次执行上面的命令并每次换 `--props` 文件。

**6. 打包出可部署的 bundle**

```bash
npx remotion bundle
npx remotion bundle src/index.ts --out-dir=build
```

产出的静态 bundle 可以丢到任意静态托管，配合 Player 在网页里播放，或交给渲染服务消费。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 渲染报「找不到 composition」 | 传的 ID 与 `<Composition id="...">` 里的不一致；ID 只允许字母数字和 `-`，写成中文或下划线就会对不上 | 先跑 `npx remotion compositions` 看真实 ID，再照抄进 render 命令 |
| 升级某个 `@remotion/*` 包后满屏版本冲突报错 | Remotion 的所有官方包必须同版本，单独升级一个就破坏了约束 | 用 `npx remotion versions` 定位不一致的包，再用 `npx remotion upgrade` 或 `npx remotion add` 统一版本，别手改单个包 |
| 首次渲染卡很久或直接超时失败 | 本机没有兼容的 Chrome，正在后台下载浏览器；或某个资源（字体、图片、接口）一直没加载完 | 等首次下载完成；确认是网络问题就配 `--browser-executable` 指向本机 Chrome；用 `--log=verbose` 看卡在哪一帧，把该资源的等待超时配 `--timeout` 调大 |
| 动画一开渲染就错位 / 内容闪烁 | 组件里有基于 `Date.now()`、`Math.random()` 或真实时间的逻辑，每帧结果都不一样 | 帧号只能来自 `useCurrentFrame()`；随机数用帧号随机函数；所有动画必须是帧号的纯函数 |
| 服务器上渲染出来是黑屏 / 缺字体 | 无头浏览器环境缺字体，中文尤其容易变成方块 | 把字体文件放进 `public/` 用 `staticFile()` 引入并显式等它加载完，不要依赖系统字体 |
| 组件里请求外部接口，偶发渲染失败 | 渲染逐帧并行，多帧会同时打同一个接口，容易被限流或超时 | 数据在渲染前一次性取好，通过 `--props` 或 `calculateMetadata()` 传入，别放在逐帧渲染过程里请求 |
| `--crf` 和 `--video-bitrate` 同时给出报错 | 两者是互斥的码率控制模式 | 只留一个：画质优先用 `--crf`，控体积用 `--video-bitrate`。注意开了硬件加速就不能用 `--crf` |
| Windows 下 `--props` 传内联 JSON 报解析错误 | Windows shell 会剥掉内联 JSON 里的双引号 | 把 props 写成 `.json` 文件，传 `--props=./props.json` |
| 大批量渲染把机器内存吃满 | 并发过高，且 `<OffthreadVideo>` 的帧缓存默认按可用内存的一半分配 | 降低 `--concurrency`，或调小 `--offthreadvideo-cache-size-in-bytes`；内存紧张时加 `--disallow-parallel-encoding` |
| 想商用但不清楚要不要买许可证 | 许可证按组织规模与用量分档，不是纯 MIT 随便用 | 动手前先读官方 License & Pricing 页确认自己落在哪一档（个人及 3 人以内组织免费，4 人及以上需要公司许可证），这是合规问题不是技术问题 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 首次运行会下载 Chrome Headless Shell；组件里常需拉取远程字体、图片、素材；升级包版本走 npm 源 |
| 读取文件 | 是 | 读取项目源码与 `public/` 下的素材、`--props` 指定的 JSON、`.env` / `--env-file` 指定的环境变量文件 |
| 写入文件 | 是 | 写出渲染产物（MP4 / WebM / GIF / 图片序列 / 静帧）、bundle 目录，以及 Webpack 缓存目录 |
| 凭证 | 否 | 本地渲染不需要任何 Key。只有用到云端渲染（Lambda / Cloud Run）或对象存储时才需要各家云厂商凭证 |
| 子进程 / 后台常驻 | 是 | 会拉起无头 Chrome 与自带的 FFmpeg 二进制；`remotion studio` 会常驻并开一个本地 HTTP 服务 |

## 触发场景

- 「用代码批量生成视频」
- 「同一套模板换文案，出 100 条短视频」
- 「视频内容要跟着数据自动更新」
- 「用 React 写动画，导出 MP4」
- 「搭一个网页上的视频编辑器 / 预览播放器」
- 「数据周报做成视频，每周自动重渲染」

## 能力边界

**覆盖**：

- 用 React + CSS 描述画面，逐帧渲染成 MP4 / WebM / GIF / 图片序列 / 单张静帧，支持 H.264、H.265、VP8、VP9、AV1、ProRes 等编码。
- 声明式时间轴：`<Sequence>` 定片段时长与偏移、`<Series>` 串接、`<Loop>` 循环、`<Freeze>` 定格，配合 `interpolate()`、`spring()`、`Easing` 做缓动。
- 参数化渲染：`defaultProps` + `--props` 传入外部数据，`calculateMetadata()` 按数据动态算时长与尺寸，这是批量量产的基础。
- 音频能力：加背景音乐与音效、按帧对齐、单独导出音轨、导出带字幕的成片（字幕相关能力有一组独立包）。
- 多种运行方式：本地 CLI、Studio 图形预览、Node.js 服务端渲染 API、浏览器端渲染、AWS Lambda 与 Google Cloud Run 分布式渲染、GitHub Actions。
- 生态包：Google Fonts 与本地字体、Lottie、GIF、Three.js、Skia、Tailwind、转场、波形与媒体工具等。

**不覆盖**：

- 不是剪辑软件：没有多轨时间线 UI、没有转场拖拽、没有调色台和混音台。
- 不做视频理解与素材生成：不负责语音识别、抠像、AI 生成画面这些事（官方虽有语音转写相关的辅助包，那是调用外部模型的胶水，不是它自己会听）。
- 不替你做素材管理与版权清理：用到的字体、音乐、图片、视频授权要自己解决。
- 不做推理加速：渲染速度取决于本机 CPU、内存和是否用得上硬件编码器，它本身没有「提速魔法」。
- 不提供免费的商用授权：许可证分档收费，免费边界与计价方式以官方 License & Pricing 页面当时的说明为准。

## 依赖条件

- **Node.js**：必须有，版本下限以官方文档当前说明为准。包管理器用 npm / Yarn / pnpm / Bun 均可（Bun 与 Deno 有各自的专用入口与限制，见官方 CLI 文档）。
- **Chrome / Chromium**：渲染时需要一个无头浏览器。本机没装兼容版本时它会下载一份 Chrome Headless Shell；也可以用 `--browser-executable` 或 `--chrome-mode` 指定。
- **FFmpeg**：不用自己装，Remotion 会带一份平台相关二进制，通过 `--binaries-directory` 可以覆盖位置。
- **磁盘与内存**：渲染中间产物、帧缓存和 bundle 都占空间；大分辨率长视频对内存要求明显更高。
- **许可证**：个人与 3 人以内组织免费（须遵守官方条款），4 人及以上组织需要公司许可证，自动化批量渲染按次计费。商用前务必自行核对官方定价页。
- **可选云资源**：要用 Lambda 或 Cloud Run 渲染，需要相应的云账号、权限与存储桶。

## 已知限制

- 渲染本质是「无头浏览器逐帧截图 + 编码」，耗时基本与总帧数成正比；长视频用 CLI 单机渲染会非常慢，属于架构性限制。
- 组件必须是纯函数式的帧渲染：任何跨帧状态、随机性、当前时间依赖都会破坏可复现性。
- 无头环境没有系统字体可供依赖，中文与特殊字体必须显式加载并等待就绪。
- 版本耦合很紧，所有 `@remotion/*` 包必须同版本，在与其它的依赖共存的老项目里需要额外协调。
- 上游迭代很快，CLI flag 与包名（例如某些包被标记为 deprecated、某些 flag 在 v4 被移除）会变化；执行前以 `npx remotion help` 与官方文档当前内容为准。
- 具体版本号、发布日期与 star 数请以仓库页面实时信息为准，此处不做断言。

## 自检清单

- [ ] Node.js 已就绪，且项目里所有 Remotion 包版本一致（`npx remotion versions` 无告警）。
- [ ] 已用 `npx remotion compositions` 确认要渲染的 composition ID 拼写正确。
- [ ] composition 的 `width` / `height` / `fps` / `durationInFrames` 与目标投放规格一致（竖屏短视频通常是 1080×1920）。
- [ ] 组件内没有 `Date.now()`、`Math.random()` 这类非帧号随机源；随机用官方帧号随机函数。
- [ ] 字体、图片、音视频素材都能被加载，远程资源已考虑加载等待与超时。
- [ ] 需要外部数据时，数据在渲染前取好并通过 `--props` 或 `calculateMetadata()` 注入，没有在逐帧渲染里请求接口。
- [ ] `--crf` 与 `--video-bitrate` 没有同时使用；用硬件加速时没有设 `--crf`。
- [ ] 大批量渲染前先用一小段 `--frames` 试跑，确认画质、音量电平与时长都符合预期。
- [ ] 确认所在组织规模与使用方式落在许可证允许的范围内。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/remotion-dev/remotion | 上游仓库（安装与完整文档以它为准） |
| https://www.remotion.dev/docs/cli/ | 官方 CLI 参考（本包命令与 flag 的来源） |
| https://www.remotion.dev/docs/license/pricing | 官方许可证与计价说明（商用前必读） |

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
