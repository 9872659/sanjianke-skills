# 快速开始与渲染流程

这份文档解决「从零到一条能交付的 MP4」：装环境、看懂工程目录、写第一份合成、预览与检查、渲染与验收，以及输出格式怎么选。

---

## 一、环境准备

### 硬性要求

| 项目 | 要求 | 怎么确认 |
|---|---|---|
| Node.js | 22 或更高 | `node -v` |
| FFmpeg / ffprobe | 在 PATH 里 | `ffmpeg -version` |
| Chrome | 由 CLI 自己管理 | `npx hyperframes browser ensure` |
| Docker | 只在 `render --docker` 时需要 | `docker info` |

### 第一次体检

```bash
npx hyperframes doctor
```

它会逐项报告 ok / warn / fail：版本（本地 CLI 与 npm 上的最新版对比）、Node、CPU、内存、磁盘、影响渲染器的环境变量、FFmpeg 与 ffprobe（含版本与编解码器）、Chrome（自带的还是系统的、版本、路径）、Docker 与 Docker 是否在跑，容器里还会多报一项 `/dev/shm`。

给 agent 或 CI 用的时候要走 JSON，并且注意它**恒定退出 0**——退出码不含信息，必须判 payload：

```bash
npx hyperframes doctor --json | jq -e '.ok' >/dev/null
```

### Chrome 的固定版本

```bash
npx hyperframes browser ensure   # 找到或下载固定版本
npx hyperframes browser path     # 打印可执行文件路径
npx hyperframes browser clear    # 清掉缓存重来
```

它不用系统 Chrome，是因为**像素输出会随 Chrome 版本漂移**。锁住浏览器版本，同一份工程在不同机器、不同月份渲染出来的画面对得上。脚本里要拿路径就写 `$(npx hyperframes browser path)`。

### 什么情况下先跑 doctor

- `render` 报 Chrome 或 FFmpeg 相关错误。
- `preview` 能打开，但合成加载失败。
- 一台从没跑过这套引擎的新机器。
- 渲染突然变慢或频繁失败（先看内存和磁盘这两行）。

---

## 二、工程解剖

### 起一个工程

```bash
npx hyperframes init my-video
cd my-video
```

非交互式环境（agent、CI）里 `init` 需要显式指定示例：

```bash
npx hyperframes init my-video --non-interactive --example=<name>
```

也可以用现成示例起步：

```bash
npx hyperframes init my-clip --example <name>
```

### 目录长什么样

```
my-video/
├── index.html              # 主合成，默认渲染入口
├── hyperframes.json        # 工程配置（registry 地址、安装路径等）
├── compositions/           # 子合成与安装进来的 block
│   └── components/         # 安装进来的 component（片段）
├── assets/                 # 媒体：视频、音频、图片、字体
└── renders/                # 渲染产物，默认落在这里
```

`index.html` 是入口，但**它不必是唯一**。用 `render -c` 可以指定渲染任意一个合成文件：

```bash
npx hyperframes render -c compositions/intro.html -o intro.mp4
npx hyperframes compositions   # 列出当前工程里所有合成
```

### hyperframes.json

工程级配置，主要管两件事：registry 从哪拉、安装到哪去。

```json
{
  "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
  "paths": {
    "blocks": "compositions",
    "components": "compositions/components",
    "assets": "assets"
  }
}
```

`paths` 三项都可改。团队想把组件统一放到别的目录，改这里就行，`add` 会跟着走。

### 变量声明放在哪

放在**主合成 `index.html` 的 `<html>` 元素上**，不是配置文件里：

```html
<html data-composition-variables='[
  {"id":"title","type":"string","label":"标题","default":"示例标题"},
  {"id":"accent","type":"color","label":"主色","default":"#ff4d2e"}
]'>
```

注意这里有两种 JSON 形状，极易混淆，写错了会静默失效：

- `data-composition-variables` 是**声明数组**（schema）：`[{id, type, label, default}, ...]`
- `--variables` 与 `data-variable-values` 是**按 id 索引的对象**（取值）：`{"title":"Q4"}`

---

## 三、写第一份合成

### 骨架

```html
<!doctype html>
<html lang="zh-CN"
      data-composition-variables='[
        {"id":"title","type":"string","label":"标题","default":"默认标题"}
      ]'>
<head>
  <meta charset="utf-8" />
  <style>
    html, body { margin: 0; background: #0b0b10; }
    #stage {
      position: relative; width: 1920px; height: 1080px;
      overflow: hidden; box-sizing: border-box;
    }
    /* 约定：给可见的时间元素一个满帧盒子 */
    .clip { position: absolute; inset: 0; }
  </style>
</head>
<body>
  <div id="stage"
       data-composition-id="main"
       data-width="1920" data-height="1080"
       data-duration="8">

    <!-- 场景：直接子元素，运行时会自动给绝对定位和满帧尺寸 -->
    <div class="clip" data-start="0" data-duration="8" data-track-index="0">
      <h1 id="hero" data-var-text="title"
          style="margin:0;padding:180px 140px;color:#fff;font:800 132px/1.15 'Noto Sans SC',sans-serif">
        默认标题
      </h1>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
    <script>
      const tl = gsap.timeline({ paused: true });
      tl.fromTo("#hero", { opacity: 0, y: 70 }, { opacity: 1, y: 0, duration: 1.0, ease: "power3.out" }, 0.3);
      // 收尾留出余量，不要压着 data-duration 的右开边界
      tl.to("#hero", { opacity: 0, duration: 0.6 }, 6.8);
      window.__timelines["main"] = tl;
    </script>
  </div>
</body>
</html>
```

### 骨架里每一处为什么这么写

**`#stage` 有明确像素尺寸，且 `position: relative`。**
根元素必须有能被解析出来的高度。如果根是 auto 高度，而里面有个 `height: 100%` 的 flex 子元素，子元素会塌成 0 高，所有内容堆到左上角——这是静默 bug，自动检查未必抓得到。写完一定用 `snapshot` 看一眼。

**`data-composition-id="main"` 与 `window.__timelines["main"]` 一致。**
只注册一条时间轴时，key 不匹配还能兜住；注册两条以上还不匹配，画面会冻在第 0 帧。

**`.clip` 是约定，不是运行时要求。**
运行时从不读这个 class。那为什么还要写？因为脚手架的共享规则 `.clip { position: absolute; inset: 0 }` 就是场景满帧盒子的来源，Studio 也把它当编辑提示；缺了它 `lint` 会 warn（`timed_element_missing_clip_class`）。**去掉 class 就得自己把那套布局补上**。`<video>` / `<audio>` 上不要加。

**`data-duration="8"` 写在根上，是编译期读一次的。**
脚本里 `root.setAttribute("data-duration", ...)` 改不动它，`--variables` 也不行。要按不同长度出片，就改根上的字面量。（**clip 自己的 `data-duration` 不一样**，那个是从活 DOM 重读的，脚本和变量能驱动。）

**`data-var-text="title"` 做声明式替换。**
不需要写 JS。同理 `data-var-src="heroImage"` 替换图片 `src`，作者写的 `src` 当兜底。所有标量变量还会自动应用成根上的 `--{id}` CSS 自定义属性，所以 `color: var(--accent)` 也能直接被覆盖。

**动画用 `fromTo` 把初值写进 tween。**
不要用 CSS 写 `transform: translateY(70px)` 再用 GSAP tween 同一个属性——两者会打架，`lint` 报 `gsap_css_transform_conflict`。

**收尾留余量。**
可见性窗口是左闭右开 `[start, start + duration)`，在 `t == start + duration` 那一刻已经隐藏。动画的**终态要落在 `data-duration` 之前**一点点，压着边界收，最后一帧永远不会被渲染。

**paused 是必须的。**
渲染是逐帧 seek，没有「播放」这回事。不要 `tl.play()`。

### 一条时间轴原则

每个合成**只注册一条** `gsap.timeline({ paused: true })`。异步构建是支持的，比如等字体：

```js
document.fonts.ready.then(() => {
  const tl = gsap.timeline({ paused: true });
  tl.fromTo("#hero", { opacity: 0 }, { opacity: 1, duration: 1 });
  // 关键：构建完成之后才赋值
  window.__timelines["main"] = tl;
});
```

**必须等 tweens 加完再赋值。** 提前注册一个空 timeline，运行时认为它已经就绪并把它当空嵌套进去，画面就是空的；`lint` 会给 `gsap_timeline_registered_before_async_build`。

顺带一提，`window.__timelines = window.__timelines || {}` 这行**不需要**写，运行时在你的内联脚本执行前就建好注册表了。

---

## 四、检查 → 预览 → 渲染

### 开发循环

```bash
npx hyperframes lint                    # 第一遍 HTML 写完就跑；结构大改后再跑
npx hyperframes check                   # 最终关卡，它内部会先跑 lint
npx hyperframes snapshot --at 1,3,5     # 抓关键帧成图，人眼看
npx hyperframes preview --background    # 起 Studio，交给人 review
npx hyperframes render --quality high --output out.mp4
```

### lint 与 check 的分工

`lint` 是**静态**检查，快，适合边写边跑：

```bash
npx hyperframes lint ./my-composition
npx hyperframes lint --json       # 机器可读：errorCount / warningCount / infoCount / findings
npx hyperframes lint --verbose    # 连 info 级也显示（比如外部脚本依赖提醒）
```

默认只显示 error 和 warning。

`check` 是**最终关卡**，它先跑 lint，然后用一个浏览器会话、一遍 seek 通过，审计运行时错误、失败请求、布局、motion 断言和 WCAG 对比度，最后才开浏览器。

```bash
npx hyperframes check
npx hyperframes check --snapshots      # 附标注过的总览帧与问题裁切图
npx hyperframes check --strict         # warning 也计入退出码
```

**有一个坑必须记住**：只要还有 lint **error**，布局与对比度审计就被关掉了，`check` 会报 `0 sample(s)` 和 `0/0 text checks`。这看起来像「干净通过」，实际上什么都没跑。**先清干净 lint error，再信那些数字。**

另外三个命令名 `validate` / `inspect` / `layout` 是给老脚本留的兼容别名，新写的流程一律用 `check`。

### preview 的两种界面不要搞混

| 界面 | 什么时候开 | 用途 |
|---|---|---|
| Storyboard 看板 | 合成检查通过之前，且 `storyboard: yes` 时 | 看计划卡片与线框草图。地址 `?view=storyboard#project/<name>` |
| 最终合成预览 | `check` 通过之后 | 看组装好的时间轴。地址 `#project/<name>` |

早期的看板**不等于**成片批准。渲染永远要等最终那次确认。

### 后台常驻的预览

```bash
npx hyperframes preview --background --port 3017
npx hyperframes preview --status
npx hyperframes preview --list
npx hyperframes preview --stop
npx hyperframes preview --kill-all
```

在 TTY 里 `preview` 会一直挂着直到 Ctrl+C；在 agent 这类非交互 shell 里，它会自动变成受管的后台会话，命令返回后进程还活着。想明确控制就加 `--background` 或 `--foreground`。受管生命周期的命令加 `--json` 会输出机器可读结果。

**交回给人的是 Studio 项目 URL，不是 `index.html` 路径**：

```text
http://localhost:<port>/#project/<project-name>
```

两个最容易翻车的点：URL 少了 `#project/<project-name>` 那段（Studio 起来了但没工程可开），或者服务其实没在跑。**给出去之前先确认那个 URL 返回 200**，review 全程别关，结束再 `preview --stop`。

### 子合成的挂载冒烟

静态审计抓不到所有挂载失败。工程用了子合成时，每个宿主时段至少抓一张可见的中间帧：

```bash
npx hyperframes snapshot --at 2.5,7.5,12.5
```

看到**内容异常小且没样式、图标被拉到画布大小、主角元素缺失、时间轴注册超时**，一律当阻塞渲染的挂载缺陷处理，不要带着往下走。

### 用 Studio 选区来定位「这个元素」

用户说「把这个改大一点」「刚才点的那个卡片」时，别靠截图猜：

```bash
npx hyperframes preview --context --json --context-fields selection
```

优先用返回的 `selection.target.hfId`；没有稳定 id 时退到 `selection.target.selector`。返回 `no-selection` 就请用户先在 Studio 里点一下再跑。只取需要的切片，`--context-detail full` 只在真需要计算样式或可编辑文本元数据时用。

---

## 五、渲染

### 基本命令

```bash
npx hyperframes render                                   # 用 cwd 里的工程
npx hyperframes render ./my-video --output ./out.mp4     # 在工程目录外跑
npx hyperframes render -c compositions/intro.html -o intro.mp4
```

`dir` 这个位置参数是**工程目录**，不是文件。默认输出路径带时间戳：`renders/<工程名>_<YYYY-MM-DD>_<HH-MM-SS>.<ext>`，所以连续渲染不会互相覆盖；要稳定文件名就显式传 `--output`。

### 质量档位

| 场景 | 命令 |
|---|---|
| 快速迭代 | `npx hyperframes render --quality draft` |
| 常规评审 | `npx hyperframes render`（默认 standard） |
| 最终交付 | `npx hyperframes render --quality high --output out.mp4` |
| 跨主机逐字节一致 | `npx hyperframes render --docker --strict --output out.mp4` |

### 常用参数

| 参数 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `--fps` | 24 / 30 / 60 | 30 | 60fps 渲染耗时翻倍 |
| `--format` | mp4 / webm / mov / gif / png-sequence | mp4 | 见下方格式选择 |
| `--resolution` | landscape / portrait / landscape-4k / square 等（含 `1080p`、`4k` 别名） | — | 通过 Chrome 的 `deviceScaleFactor` 超采样；宽高比必须与合成一致，倍率必须是整数；不能和 `--hdr` 同用 |
| `--crf` | 0–51 | — | 越低画质越高；与 `--video-bitrate` 互斥 |
| `--video-bitrate` | 如 `10M`、`5000k` | — | 与 `--crf` 互斥 |
| `--hdr` / `--sdr` | 开关 | 关 | 强制 HDR / SDR；仅 MP4 |
| `--workers` | 数字或 `auto` | auto | 每个 worker 拉一个 Chrome（约 256 MB 量级） |
| `--gpu` | 开关 | 关 | FFmpeg 走 GPU 编码（NVENC / VideoToolbox / VAAPI / QSV） |
| `--browser-gpu` / `--no-browser-gpu` | 开关 | 本地 auto、docker 关 | Chrome / WebGL 是否用宿主 GPU |
| `--browser-timeout` | 0.001–86400 秒 | 60 | Puppeteer 导航超时；重合成（多视频 / 多字体 / 远程资源）到不了 `domcontentloaded` 时调大 |
| `--strict` | 开关 | 关 | lint error 直接判失败 |
| `--strict-all` | 开关 | 关 | lint error 与 warning 都判失败 |
| `--quiet` | 开关 | 关 | 少输出 |

### 输出格式怎么选

| 格式 | 什么时候用 | 注意 |
|---|---|---|
| `mp4` | 绝大多数交付 | 默认档；`--hdr` 只在这个格式上有效 |
| `webm` | 要透明通道嵌网页 | 带透明度 |
| `mov` | 要透明通道进后期软件 | 带透明度 |
| `gif` | 贴 PR / README / 文档里自动播放 | 两遍调色板编码；fps 上限 30，建议 `--fps 15`；**无音频**；只支持 1-bit 透明；HDR 会回落 SDR；循环次数用 `--gif-loop`（0 表示无限） |
| `png-sequence` | 交给 AE / Nuke / Fusion 合成 | 写出 RGBA 帧序列到目录 |

### 验收，不要只看退出码

```bash
test -s out.mp4
ffprobe -v error -show_format out.mp4
```

同时确认三件事：**文件存在、非空、时长合理**。渲染完成不等于渲染正确——先跑 `snapshot` 肉眼过一遍关键帧，再相信成片。

### 渲染前的自查

- [ ] `npx hyperframes check` 通过（lint / 运行时 / 布局 / motion / 对比度 全 0 findings）。
- [ ] 用了子合成的，每个宿主时段都看过 `snapshot`。
- [ ] `preview --background` 起过，项目 URL 返回 200，人已经确认过时间轴。
- [ ] 成片落盘验证过（存在、非空、`ffprobe` 时长合理）。
- [ ] 交付用的稳定文件名是显式 `--output` 指定的，不是时间戳默认值。

---

## 六、渲染受管与云路径

当本地跑不动、或者要一次出很多条时：

| 需求 | 命令 | 什么时候选它 |
|---|---|---|
| Docker 可复现 | `npx hyperframes render --docker` | 要跨主机逐字节一致，或宿主装不了 Chrome |
| 托管零基础设施 | `npx hyperframes cloud render` | 本地没有 Chrome / FFmpeg，也不想碰 AWS |
| 自管 AWS 分布式 | `npx hyperframes lambda render <project> --width 1920 --height 1080 --wait` | AWS 归属是硬要求 |
| 自管 GCP 分布式 | `npx hyperframes cloudrun render <project> --width 1920 --height 1080 --wait` | GCP 归属是硬要求 |

跑任何云路径之前，先读对应参考。另外注意托管云的工程上传有体积上限，快接近时用 `cloud render --dry-run --json` 查清楚是什么把体积撑大了，**不要因为某个素材大就随手忽略它**。

> 非本地渲染路径涉及账号、上传与费用，本 Skill 只描述桌面本地渲染的完整闭环；云路径请以上游当前文档为准。

---

## 七、什么时候不该往下走

如果你在一个**屏蔽 Chromium 的沙箱**里（典型是 macOS 上的 seatbelt 类沙箱，`workspace-write` 模式），任何 Chrome——自带的、系统的、headless shell——都会在启动时直接死掉，报 `MachPortRendezvous` 一类错误。这是宿主级封锁，不是引擎或 Chrome 安装的问题：编译检查、音频处理都还正常，**只有渲染不可用**。

正确处置是：**说清这个阻塞，把手头已检查过的合成交付出去**，把渲染交给 `--docker`、云渲染或用户本人。**不要**自己搭一套替代光栅化管线（magick / PIL / SVG 拼帧那一类）出来——被封锁的机器上，交付物就是「检查通过的合成 + 这个阻塞说明」。并且要在识别出阻塞的那一刻就把结论写出来，别等后续某个可选兜底步骤失败，把已经做完的工作报告一起冲掉。
