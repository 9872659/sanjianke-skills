---
name: sanjianke-code-video-kit
slug: sanjianke-code-video-kit
displayName: 三剪客 · 代码化视频生成
description: "用 React 组件写视频，参数化批量出片。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "把视频当成 React 组件来写：用帧号和动画函数驱动画面，先预览再渲染成 MP4，同一套模板换一份数据就能批量出片。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 设计多媒体
  - 代码生成视频
  - 动画
---

# 三剪客 · 代码化视频生成

用 React 组件写视频，参数化批量出片。

剪映、AE 这类工具能做出很漂亮的片子，但它们的瓶颈在「第二条」。一条 15 秒的促销视频手搓没问题，一千条标题各不相同的版本就要命了——改文案、对时间轴、导出、重命名，全是人工。代码化视频生成把这件事翻过来：画面是一段 React 组件，时间由帧号驱动，文案和数据是组件的 props。模板写一次，剩下的是喂数据。

Remotion 就是这条路线上最成熟的方案。它不做传统的视频编辑，而是让浏览器把每一帧当网页渲染出来，再把帧序列交给 FFmpeg 编码成 MP4。所以你能用上整套前端能力：CSS 动画、Flex/Grid 布局、字体、SVG、Canvas、Three.js、Tailwind，以及任意 npm 包。数据处理能力更是原生自带——从接口拉数据、循环数组生成列表、按条件切换镜头，这些都是写 JS，不需要在软件里点。

这个 Skill 覆盖从零建项目、掌握核心动画 API、把模板参数化成能批量跑的生产线，一直到渲染规模和许可合规的完整链路。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（必需） | 首次安装依赖、下载无头浏览器；`calculateMetadata()` 里拉取远程数据；云渲染方案会把打包产物上传到对象存储 |
| 读取文件 | 是（必需） | 读取 `src/` 下的组件与入口、`remotion.config.ts`、props JSON 文件、字幕/文案/商品数据源 |
| 写入文件 | 是（必需） | 生成项目骨架、写入中间帧序列、输出 `out/*.mp4`、写批量任务的 props 文件与渲染清单 |
| 凭证 | 视方案而定 | 本地渲染不需要任何 Key。接入云渲染（Lambda / Cloud Run）时从环境变量读取云厂商凭证；公司许可用户需要 `licenseKey`，一律走环境变量或 CI Secret |
| 子进程 / 后台常驻 | 是（必需） | `npx remotion studio` 起预览服务并常驻；`npx remotion render` 拉起无头浏览器 + FFmpeg；批量任务应放后台运行并落日志 |

**密钥与费用**：本 Skill 不内嵌任何密钥，不代理任何请求，也不代收费用。本地渲染除机器电费外没有额外开销；云渲染的算力账单和对象存储费用由使用者自己的云账号承担。公司许可的采购、telemetry 上报与 `licenseKey` 配置全部由使用者自己对上游完成，本 Skill 只负责把合规要求讲清楚并要求你在动手前确认。

## 触发场景

- 「我要把每周的销售数据自动做成一分钟的播报视频，数据换了画面跟着变」——参数化模板 + 定时批量渲染。
- 「一千个商品各出一条 15 秒短视频，标题和价格都不一样」——JSON/CSV 驱动批量出片。
- 「我会写 React，但不想学 AE，能不能直接用代码做动效」——帧驱动动画与 CSS 结合。
- 「同一套片头片尾，给不同客户换成各自的 Logo 和主色」——品牌变量注入 + 单个 Composition 复用。
- 「渲染出来的视频卡顿、丢字、字体变了、输出一片黑」——渲染管线与资源加载排查。
- 「团队二十个人，用 Remotion 做商业化产品，许可该怎么买」——许可门槛与 telemetry 义务确认。
- 「本地一台机器渲染太慢，想上云」——Lambda / Cloud Run 部署与并发调优。

## 快速开始

### 第 0 步：先确认许可

Remotion **不是开源软件**，是 source-available 商业许可。动手写代码前先确认自己落在哪一档，详见下文「已知限制」。个人、3 人及以下团队、非营利组织可直接免费用于商业场景；4 人及以上公司需要 Company License。这不是建议，是许可条款。

### 第 1 步：建项目

环境要求：Node.js 18 以上（当前上游主版本为 4.x，最新发布在 `4.0.5xx` 一线）、本机有可用的 Chrome/Chromium（没有会自动下载一份）、FFmpeg 由 Remotion 自带，不需要单独装。

```bash
npx create-video@latest my-video
cd my-video
npm install
npm run dev          # 等价于 npx remotion studio，默认 http://localhost:3000
```

### 第 2 步：最小可用模板

入口文件用 `registerRoot()` 告诉 Remotion 从哪开始，再注册一个 Composition：

```tsx
// src/index.ts
import {registerRoot} from 'remotion';
import {Root} from './Root';

registerRoot(Root);
```

```tsx
// src/Root.tsx
import React from 'react';
import {Composition} from 'remotion';
import {z} from 'zod';
import {ProductCard, productSchema} from './ProductCard';

export const Root: React.FC = () => {
  return (
    <Composition
      id="ProductCard"
      component={ProductCard}
      durationInFrames={150}      // 5 秒 @ 30fps
      fps={30}
      width={1080}
      height={1920}               // 竖屏
      schema={productSchema}
      defaultProps={{
        title: '新品上架',
        price: '¥199',
        accent: '#ff5722',
      }}
    />
  );
};
```

组件本身是一个普通 React 组件，画面完全由「当前第几帧」推导：

```tsx
// src/ProductCard.tsx
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {z} from 'zod';

export const productSchema = z.object({
  title: z.string(),
  price: z.string(),
  accent: z.string(),
});

export const ProductCard: React.FC<z.infer<typeof productSchema>> = ({title, price, accent}) => {
  const frame = useCurrentFrame();          // 当前帧号
  const {fps, durationInFrames} = useVideoConfig();

  // 入场用弹簧，收尾用线性淡出
  const enter = spring({frame, fps, config: {damping: 14}, durationInFrames: 25});
  const exit = interpolate(frame, [durationInFrames - 20, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#111',
        justifyContent: 'center',
        alignItems: 'center',
        color: '#fff',
        fontFamily: 'sans-serif',
      }}
    >
      <div
        style={{
          transform: `translateY(${interpolate(enter, [0, 1], [60, 0])}px) scale(${enter})`,
          opacity: enter * exit,
          textAlign: 'center',
          padding: 48,
        }}
      >
        <div style={{fontSize: 88, fontWeight: 800}}>{title}</div>
        <div style={{fontSize: 64, color: accent, marginTop: 24}}>{price}</div>
      </div>
    </AbsoluteFill>
  );
};
```

`spring()` 和 `interpolate()` 都返回 `0~1` 或你指定区间内的数值，直接拿去喂 `opacity`、`transform`、`scale`、`width` 都行。这个「帧 → 数值 → 样式」的链条就是全部动画原理，没有别的黑魔法。

### 第 3 步：预览

```bash
npx remotion studio                 # 打开可视化预览，右侧能实时改 props
npx remotion studio --port 3333     # 换端口
npx remotion compositions           # 只列出所有 Composition，确认 ID 与时长
```

Studio 是本地开发的主要工作台：拖动时间轴逐帧看、改 defaultProps 立刻看效果、按空格播放。**改 props 时 `calculateMetadata()` 会重新执行**，所以数据拉取不要写在这里之外的地方。

### 第 4 步：渲染成 MP4

```bash
# 最简：渲染全片
npx remotion render ProductCard out/product.mp4

# 带数据：从文件读 props（Windows shell 下不要用内联 JSON，引号会被吃掉）
npx remotion render ProductCard out/product.mp4 --props=./data/item-001.json

# 控制质量与速度
npx remotion render ProductCard out/product.mp4 \
  --codec=h264 \
  --crf=18 \
  --concurrency=4 \
  --image-format=jpeg \
  --log=verbose

# 只出一张封面图（比渲染整片快两个数量级）
npx remotion still ProductCard out/cover.png --frame=30

# 先出图序列再自行编码，便于中间质检
npx remotion render ProductCard out/frames --sequence --image-format=png
```

`--concurrency` 是并行渲染的标签页数量，默认约等于 CPU 线程数。它调太高会把内存吃满然后崩溃，调太低则跑不满机器，详见 `references/batch-and-deploy.md`。

### 第 5 步：验证链路真的通了

先渲染 3 帧而不是整片，几十秒内就能知道环境有没有问题：

```bash
npx remotion render ProductCard out/probe.mp4 --frames=0-2 --log=verbose
```

跑通之后再放开全量渲染和批量任务。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 从零建项目、理解 Composition 与组件怎么接、把 MP4 渲染出来、排渲染故障 | `references/quickstart.md` |
| 写动画：帧号、插值、弹簧、序列与图层、字幕音视频、数据驱动 | `references/animation-api.md` |
| 参数化模板、批量出一千条、并发与内存调优、上云与定时任务 | `references/batch-and-deploy.md` |

## 能力边界

**覆盖**：

- **项目搭建**：`create-video` 起模板、入口注册、`Root.tsx` 组织多 Composition、`remotion.config.ts` 全局配置。
- **组件化画面**：用普通 React 组件 + CSS 描述任何能写出来的画面；布局、字体、SVG、Canvas、Three.js、Tailwind、Lottie、任意 npm 包都能用。
- **帧驱动动画**：`useCurrentFrame()` 取帧号、`useVideoConfig()` 取 fps/尺寸/时长、`interpolate()` 区间映射与缓动、`spring()` 物理入场、`interpolateColors()` 颜色过渡、`random()` 确定性随机。
- **时间与图层**：`<AbsoluteFill>` 铺满层、`<Sequence>` 控制出现时段与偏移、`<Series>` 顺序串场、`<Loop>` 循环、`<Freeze>` 定格、`<Folder>` 归类。
- **音视频与素材**：`<OffthreadVideo>` 高性能嵌入视频、`<Img>` 图片（等待解码后才出帧）、`<Audio>` 音轨、`staticFile()` 引用 `public/` 资源、转场与字幕包。
- **参数化与数据驱动**：`defaultProps` 定义形状、`schema` 用 Zod 校验并自动生成可视化控件、`getInputProps()` 在组件里读输入、`calculateMetadata()` 异步拉数据并动态决定时长/尺寸/帧率。
- **渲染与部署**：CLI 与 Node API（`renderMedia()` / `renderStill()` / `renderFrames()`）、图序列输出、Lambda 与 Cloud Run 云渲染、按数据循环批量出片、CI 定时任务。
- **许可合规**：个人 / 小团队 / 公司的许可分档判定、telemetry 义务、编码器专利风险提示。

**不覆盖**：

- **不做视频剪辑**。这里没有时间轴拖拽、没有素材箱、没有关键帧曲线编辑器。素材拼接、裁切、调色的传统后期仍在剪辑软件里做。
- **不做 AI 生成画面**。本 Skill 只负责「把已有的文案、图片、视频、音频编排成成片」，不生成素材本身。
- **不做实时推流与直播**。渲染是离线的批处理，产物是文件。
- **不替代前端工程能力**。「把视频写成代码」不等于「随便写写就好看」，动效审美和排版功底仍然是你自己的。
- **不提供许可证代购或法律意见**。许可档位、条款解释、编码器专利适用性一律以上游官方条款为准，本 Skill 只做转述并提示你去确认。
- **不含任何可复制的上游源码**。正文为原创整理，仅引用 API 名称、命令、参数名、许可事实等描述性信息。

## 依赖条件

- **Node.js** 18 以上（建议 LTS 20/22），npm 或 pnpm 任一。
- **Chrome / Chromium**：渲染时由 Remotion 驱动无头浏览器逐帧截图。系统里没有会尝试自动下载，内网环境需要预先指定可执行文件路径（`--browser-executable`）。
- **FFmpeg**：由 Remotion 自带，**不要**再单独装一份去干扰 PATH。
- **磁盘**：默认渲染是流式的，不落全量帧。但用 `--sequence` 出 PNG 序列时，帧数 × 单帧体积就是磁盘占用，1080p PNG 一秒 30 帧大约 40–80 MB，长片要预留几十 GB。
- **内存**：主要消耗在无头浏览器标签页。`--concurrency` 越高内存越大，8 核机器建议 4–6。
- **可选云资源**：走 Lambda 需要 AWS 账号与 S3 桶；走 Cloud Run 需要 GCP 项目与 Artifact Registry。
- **curl / 网络**：首次 `npm install` 与浏览器下载需要能出网。

## 已知限制

### 许可：这是本 Skill 最需要你停下来确认的一条

- **Remotion 是 source-available 商业许可，不是开源软件**。源码公开可见，但不满足 OSI 的开源定义，使用受其自有许可条款约束。把它当 MIT 用会直接踩线。
- **免费档范围**：个人（个人用途或商业用途都算）、**3 人及以下**的组织或团队、非营利组织，以及「尚未商业化、正在评估」的场景。免费档功能与付费档**完全一致**，没有功能阉割，差别只在授权范围。
- **付费档门槛**：组织人数达到 **4 人及以上**就必须升级 Company License。判定看的是**人数**，不看营收、不看是否盈利。
- **Company License 按两种口径计价，可单买也可叠加**：
  - **Creators 口径**：面向「给自己公司做视频、没有搭自动化」的场景，按 **席位** 计价（约 $25/席/月），席位对应亲手写 Remotion 代码或用 AI 编码工具操作它的人。
  - **Automators 口径**：面向「做视频产品、搭自动化管线、嵌入 Player」的场景，按 **渲染次数** 计价（约 **$0.01/次**），并有 **$100/月** 的最低消费。写自动化代码的开发者本身不占席位。
- **什么算一次 Render**：成功产出一个视频、音频、GIF、PDF 或静图。**Studio 与 Player 里的预览不算**。
- **什么算 automation**：凡是你自己的代码或命令**程序化调用**渲染入口，都算。被点名的包括 `renderMedia()`、`renderStill()`、`renderFrames()`、各类云渲染封装，以及 `npx remotion render` / `npx remotion still` 命令行。换句话说，**只要你用 CLI 渲染过成片，就已经在做 automation 了**，别再自我判断为「手动低频」。
- **telemetry（自 5.0 起对公司档强制）**：Automators 与 Enterprise 档必须从许可平台取 `licenseKey` 并配置到渲染里，每次渲染上报一个匿名事件。上报内容仅限触发渲染机器的 IP、是否生产环境、是视频还是静图；**不采集任何画面内容、元数据或用户数据**。客户端渲染（`renderMediaOnWeb()` 那条路）对**所有人**都强制上报。免费档与 Creators 档的服务端渲染属自愿，不配 `licenseKey` 就不发。若因防火墙无法上报，需要走 Enterprise 定制协议并提供可核验的月度渲染报告。telemetry **不会**限流、阻断或让渲染失败。
- **商业使用的红线**：允许「用户基于你的模板生成自己的视频」；**不允许**「让用户把自己的 Remotion 工程上传到你的服务器渲染」。用 LLM 生成 Remotion 代码再渲染是允许的，但同样不接受用户自带代码。
- **代理与外包**：如果客户只拿成片文件、不接触工程代码，客户人数不计入你的门槛；如果客户拥有或继续开发这个工程，或者你引入了外部工作室/自由职业者协作同一工程，**双方人数合并计算**。
- **编码器专利不含在许可内**。H.264/AVC、HEVC、AAC 等编码的专利授权是另一回事，是否需要额外付费取决于你的使用方式与司法辖区，责任在你自己，不要拿 Remotion 的许可当挡箭牌。
- **没有退款**。上游明确理由是「可以先评估再商用」。
- 本 Skill 只做事实转述。价格与条款会变，动手前请以官方 [License & Pricing](https://www.remotion.dev/docs/license/pricing)、[License FAQ](https://www.remotion.dev/docs/license/faq) 与仓库根目录的 `LICENSE.md` 为最终依据。

### 工程上的硬约束

- **每一帧都必须是确定性的**。同一帧号渲染两次必须完全一样，否则并行渲染出来的片段会拼接错乱。所以不要在组件里用 `Math.random()`（用 `random()`）、不要用 `Date.now()` 或 `performance.now()`、不要依赖真实时钟或网络时序。
- **props 必须可 JSON 序列化**。函数、类实例、DOM 节点都进不去，渲染时会静默丢失或直接报错。例外是 `Date`、`Map`、`Set` 和 `staticFile()` 的返回值。
- **`calculateMetadata()` 只执行一次**，独立于渲染并发，在单独的标签页里跑，并且必须在 `delayRender()` 的默认超时（30 秒）内完成。超时长的数据请求要么加超时，要么在组件里用 `delayRender()` 自己控制。
- **`calculateMetadata()` 返回的字段优先级高于 Composition 上的静态 props**，但低于命令行或 `renderMedia()` 显式传入的同名选项。
- **`<Img>` 会阻塞渲染直到图片解码完成**，这是特性不是 bug——少了它就会渲染出空白帧。远程图片要么 CORS 允许，要么先下载到 `public/`。
- **字体必须等加载完**。用 web 字体时套 `delayRender()` + `continueRender()`，否则会出现字体回退（渲染出来是默认宋体/无衬线）或整段文字消失。这是最常见的「预览正常、渲染翻车」原因。
- **每帧渲染有时间上限**，默认 30 秒（`--timeout`）。`delayRender()` 没被 `continueRender()` 兑现就会超时失败并报出是哪一帧卡住。
- **stdout 保持干净**。渲染时任何 `console.log` 都会混进进度输出，`--log=verbose` 下尤其难读。要打日志写文件或走 stderr。
- **Windows 下不要用内联 `--props='{...}'`**。shell 会吃掉引号。统一写 JSON 文件用 `--props=./path.json`。
- **`--crf` 与 `--video-bitrate` 互斥**；开启硬件加速后也不能用 `--crf`，只能指定码率。
- **`--concurrency` 不是越高越好**。瓶颈通常在内存和浏览器标签页调度，超配会导致 `Target closed` 之类的崩溃而不是更快。
- **x264 预设默认 `medium`**，追求速度可以降到 `veryfast`，画质敏感再往上调，但收益与耗时不成正比。

## 自检清单

- [ ] 已确认组织人数落在哪一档许可，4 人及以上已购买 Company License，并判断清楚是走 Creators 还是 Automators 口径。
- [ ] 若属公司档 automation 场景，`licenseKey` 已从环境变量注入，telemetry 能正常上报。
- [ ] 组件里没有 `Math.random()`、`Date.now()`、`performance.now()` 等不确定源，同一帧两次渲染结果一致。
- [ ] 所有传入的 props 都是纯 JSON 可序列化的，没有函数或类实例。
- [ ] 远程数据只在 `calculateMetadata()` 里拉取，并且加了超时与失败兜底。
- [ ] 用 web 字体时已用 `delayRender()` 等待字体加载完成。
- [ ] 远程图片与视频已确认 CORS 或已落地到 `public/`。
- [ ] 先用 `--frames=0-2` 渲染几帧验通链路，再跑全量。
- [ ] 批量任务的 props 一律走 JSON 文件，没有在 Windows 上用内联 JSON。
- [ ] 批量脚本记录了每条任务的成功与失败，单条失败不会静默变成空文件。
- [ ] `--concurrency` 与机器内存匹配，长批量任务已放后台并落日志。
- [ ] 输出编码与容器格式匹配（`h264` → `.mp4`，`vp8/vp9` → `.webm`），播放器与目标平台都能识别。
- [ ] 已评估 H.264/HEVC/AAC 等编码的专利授权是否需要额外处理。
- [ ] 云渲染方案已知晓算力与存储账单由自己的云账号承担，并配置了生命周期清理。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/quickstart.md` | 从零到第一个 MP4：项目结构、入口注册、Composition 注册、Studio 预览、渲染命令、常见渲染故障排查 |
| `references/animation-api.md` | 动画与合成 API：帧号与配置钩子、interpolate/spring/颜色与随机、Sequence/Series/Loop 图层编排、字幕音视频、参数化与数据驱动 |
| `references/batch-and-deploy.md` | 批量出片与渲染部署：props 文件组织、Node API 循环渲染、并发与内存调优、图序列与转码、Lambda/Cloud Run 上云与定时任务 |

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
