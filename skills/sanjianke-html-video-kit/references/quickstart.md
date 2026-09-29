# 快速开始与渲染流程

本文覆盖从零到一条可交付 MP4 的全过程：装环境、认清工程目录、写出第一份合成、预览与检查、渲染与验收，以及输出格式如何取舍。

---

## 一、环境准备

### 硬性要求

| 项目 | 要求 | 怎么确认 |
|---|---|---|
| Node.js | 22 或更高 | `node -v` |
| FFmpeg / ffprobe | 在 PATH 里 | `ffmpeg -version` |
| Chrome | 交给 CLI 自行管理 | `npx hyperframes browser ensure` |
| Docker | 仅 `render --docker` 场景需要 | `docker info` |

### 第一次体检

```bash
npx hyperframes doctor
```

它会把每一项按 ok / warn / fail 报出来：CLI 版本（本地与 npm 最新版做个比对）、Node、CPU、内存、磁盘、会影响渲染器的环境变量、FFmpeg 与 ffprobe（含版本与编解码器）、Chrome（用的是自带的还是系统的，以及版本与路径）、Docker 及其是否在运行；在容器里还会多报一项 `/dev/shm`。

供 agent 或 CI 调用时务必走 JSON 输出，并且要记住它**退出码恒为 0** —— 退出码本身不携带信息，必须判读 payload：

```bash
npx hyperframes doctor --json | jq -e '.ok' >/dev/null
```

### Chrome 的固定版本

```bash
npx hyperframes browser ensure   # 找到或下载固定版本
npx hyperframes browser path     # 打印可执行文件路径
npx hyperframes browser clear    # 清掉缓存重来
```

之所以放着系统 Chrome 不用，是因为**像素输出会随 Chrome 版本漂移**。把浏览器版本锁住之后，同一份工程在不同机器、不同时间渲染出的画面才能对得上。脚本里需要路径时写 `$(npx hyperframes browser path)`。

### 什么情况下该先跑一次 doctor

- `render` 抛出 Chrome 或 FFmpeg 相关的错误。
- `preview` 打得开，但合成加载不起来。
- 一台从未跑过这套引擎的新机器。
- 渲染忽然变慢，或开始频繁失败（先看内存与磁盘这两行）。

---

## 二、工程解剖

### 起一个工程

```bash
npx hyperframes init my-video
cd my-video
```

在非交互式环境（agent、CI）里，`init` 必须显式指定示例：

```bash
npx hyperframes init my-video --non-interactive --example=<name>
```

也可以直接拿现成示例起步：

```bash
npx hyperframes init my-clip --example <name>
```

### 目录长什么样

```
my-video/
├── index.html              # 主合成，默认的渲染入口
├── hyperframes.json        # 工程配置（registry 地址、安装路径等）
├── compositions/           # 子合成，以及安装进来的 block
│   └── components/         # 安装进来的 component（片段）
├── assets/                 # 媒体：视频、音频、图片、字体
└── renders/                # 渲染产物默认落在这个目录
```

`index.html` 是入口，但**并非只能有这一个**。想渲染别的合成文件，用 `render -c` 指定：

```bash
npx hyperframes render -c compositions/intro.html -o intro.mp4
npx hyperframes compositions   # 列出当前工程里所有合成
```

### hyperframes.json

这是工程级配置，管的主要是两件事：registry 从哪里拉、装到哪个目录去。

```json
{
  "registry": "https://<你的 registry 地址>/registry",
  "paths": {
    "blocks": "compositions",
    "components": "compositions/components",
    "assets": "assets"
  }
}
```

> `registry` 填什么以你本地 `init` 生成的默认值为准（`npx ... info` 也会打印当前值）。
> 这里刻意不写死任何真实地址：registry 是第三方托管源，写进包里既有失效风险，
> 也会把外部仓库地址带进交付物。团队要自建 registry 时换成自己的域名即可。

`paths` 里的三项都可以改。团队希望把组件集中放到别的目录，改这里即可，`add` 会跟着走。

### 变量声明放在哪

位置在**主合成 `index.html` 的 `<html>` 元素上**，不在配置文件里：

```html
<html data-composition-variables='[
  {"id":"title","type":"string","label":"标题","default":"示例标题"},
  {"id":"accent","type":"color","label":"主色","default":"#ff4d2e"}
]'>
```

这里有个极易混淆、写错还会静默失效的地方 —— 两种 JSON 形状完全不是一回事：

- `data-composition-variables` 是**声明用的数组**（schema）：`[{id, type, label, default}, ...]`
- `--variables` 与 `data-variable-values` 是**按 id 索引的对象**（实际取值）：`{"title":"Q4"}`

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
    /* 约定：可见的时间元素都套一个满帧盒子 */
    .clip { position: absolute; inset: 0; }
  </style>
</head>
<body>
  <div id="stage"
       data-composition-id="main"
       data-width="1920" data-height="1080"
       data-duration="8">

    <!-- 场景直接作为子元素，运行时会给它绝对定位和满帧尺寸 -->
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
      // 结尾要留余量，别贴着 data-duration 的右开边界收
      tl.to("#hero", { opacity: 0, duration: 0.6 }, 6.8);
      window.__timelines["main"] = tl;
    </script>
  </div>
</body>
</html>
```

### 骨架里每一处为什么这么写

**`#stage` 有明确像素尺寸，且 `position: relative`。**
根元素的高度必须能被解析出来。若根是 auto 高度、内部又有一个 `height: 100%` 的 flex 子元素，子元素会塌成 0 高，内容全部堆到左上角 —— 这属于静默 bug，自动检查不一定抓得到。写完务必拿 `snapshot` 看一眼。

**`data-composition-id="main"` 与 `window.__timelines["main"]` 保持一致。**
只注册一条时间轴时，key 对不上尚可容忍；一旦注册两条以上仍然对不上，画面就会冻在第 0 帧。

**`.clip` 是约定，不是运行时要求。**
运行时压根不读这个 class。那为什么还要写？因为脚手架的共享规则 `.clip { position: absolute; inset: 0 }` 正是场景满帧盒子的来源，Studio 也把它当成编辑提示；缺了它，`lint` 会给出 warn（`timed_element_missing_clip_class`）。**一旦去掉这个 class，就得自己把那套布局补回来**。`<video>` / `<audio>` 上不要加。

**`data-duration="8"` 写在根上，只在编译期读一次。**
脚本里用 `root.setAttribute("data-duration", ...)` 改不动它，`--variables` 同样不行。要按不同长度出片，就得改根上的字面量。（**clip 自身的 `data-duration` 不受此限**：那个从活 DOM 重读，脚本与变量都能驱动。）

**`data-var-text="title"` 完成声明式替换。**
不需要写 JS。同理，`data-var-src="heroImage"` 用来替换图片 `src`，作者写的 `src` 充当兜底。所有标量变量还会自动应用成根上的 `--{id}` CSS 自定义属性，因此 `color: var(--accent)` 也能被直接覆盖。

**动画用 `fromTo`，把初值写进 tween 里。**
不要一边用 CSS 写 `transform: translateY(70px)`、一边又用 GSAP 去 tween 同一个属性 —— 两边会打架，`lint` 报 `gsap_css_transform_conflict`。

**收尾留余量。**
可见性窗口左闭右开 `[start, start + duration)`，到 `t == start + duration` 那一刻元素已经隐藏。动画的**终态要落在 `data-duration` 之前**一点点；压着边界收的话，最后一帧永远不会被渲染出来。

**paused 是必须的。**
渲染走的是逐帧 seek，根本没有「播放」这回事。不要写 `tl.play()`。

### 一条时间轴原则

每个合成**只注册一条** `gsap.timeline({ paused: true })`。异步构建是被支持的，比如等字体就绪：

```js
document.fonts.ready.then(() => {
  const tl = gsap.timeline({ paused: true });
  tl.fromTo("#hero", { opacity: 0 }, { opacity: 1, duration: 1 });
  // 要点：赋值必须放在构建完成之后
  window.__timelines["main"] = tl;
});
```

**必须等 tweens 全部加完再赋值。** 若提前注册一个空 timeline，运行时会认为它已就绪，并把它当成空的嵌套进去，画面就是空的；`lint` 会给出 `gsap_timeline_registered_before_async_build`。

另外，`window.__timelines = window.__timelines || {}` 这行**不需要写**：运行时在你的内联脚本执行之前，就已经把注册表建好了。

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

`lint` 属于**静态**检查，速度快，适合边写边跑：

```bash
npx hyperframes lint ./my-composition
npx hyperframes lint --json       # 机器可读：errorCount / warningCount / infoCount / findings
npx hyperframes lint --verbose    # 连 info 级也显示（比如外部脚本依赖提醒）
```

默认只输出 error 与 warning。

`check` 是**最终关卡**：它先跑一遍 lint，然后开一个浏览器会话、只 seek 一遍，完成对运行时错误、失败请求、布局、motion 断言与 WCAG 对比度的审计，浏览器则在最后才打开。

```bash
npx hyperframes check
npx hyperframes check --snapshots      # 附标注过的总览帧与问题裁切图
npx hyperframes check --strict         # warning 也计入退出码
```

**有一个坑必须记住**：只要还存在 lint **error**，布局与对比度审计就会被关掉，`check` 会报出 `0 sample(s)` 与 `0/0 text checks`。看上去像是「干净通过」，实际上什么都没跑。**务必先把 lint error 清干净，再去相信那些数字。**

另外三个命令名 `validate` / `inspect` / `layout` 是留给老脚本的兼容别名；新写的流程一律用 `check`。

### preview 的两种界面不要搞混

| 界面 | 什么时候开 | 用途 |
|---|---|---|
| Storyboard 看板 | 合成检查通过之前，且 `storyboard: yes` 时 | 看计划卡片与线框草图。地址 `?view=storyboard#project/<name>` |
| 最终合成预览 | `check` 通过之后 | 看组装好的时间轴。地址 `#project/<name>` |

早期的看板**不等于**成片批准；渲染永远要等最终那一次确认。

### 后台常驻的预览

```bash
npx hyperframes preview --background --port 3017
npx hyperframes preview --status
npx hyperframes preview --list
npx hyperframes preview --stop
npx hyperframes preview --kill-all
```

在 TTY 里 `preview` 会一直挂着，直到你按 Ctrl+C；而在 agent 这类非交互 shell 中，它会自动转为受管的后台会话，命令返回之后进程仍在运行。想明确控制，就加 `--background` 或 `--foreground`。受管生命周期的命令加上 `--json` 会给出机器可读的结果。

**交回给人的是 Studio 项目 URL，而不是 `index.html` 路径**：

```text
http://localhost:<port>/#project/<project-name>
```

最容易翻车的有两点：URL 丢掉了 `#project/<project-name>` 这一段（Studio 起来了却没有工程可开），或者服务其实并没在跑。**把 URL 给出去之前先确认它返回 200**，review 全程别关，结束之后再 `preview --stop`。

### 子合成的挂载冒烟

静态审计抓不全挂载失败。工程用到了子合成时，每个宿主时段至少抓一张可见的中间帧：

```bash
npx hyperframes snapshot --at 2.5,7.5,12.5
```

一旦看到**内容异常小又没有样式、图标被拉到画布大小、主角元素缺失、时间轴注册超时**，就一律当成会阻塞渲染的挂载缺陷来处理，不要带着问题继续往下走。

### 用 Studio 选区来定位「这个元素」

用户说「把这个改大一点」「刚才点的那个卡片」时，不要靠截图去猜：

```bash
npx hyperframes preview --context --json --context-fields selection
```

优先用返回的 `selection.target.hfId`；没有稳定 id 时退到 `selection.target.selector`。若返回 `no-selection`，就请用户先在 Studio 里点一下再跑。只取需要的切片，`--context-detail full` 仅在确实需要计算样式或可编辑文本元数据时才用。

---

## 五、渲染

### 基本命令

```bash
npx hyperframes render                                   # 用 cwd 里的工程
npx hyperframes render ./my-video --output ./out.mp4     # 在工程目录外跑
npx hyperframes render -c compositions/intro.html -o intro.mp4
```

位置参数 `dir` 指的是**工程目录**，不是文件。默认输出路径带时间戳：`renders/<工程名>_<YYYY-MM-DD>_<HH-MM-SS>.<ext>`，所以连续渲染不会互相覆盖；想要稳定的文件名就显式传 `--output`。

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
| `--fps` | 24 / 30 / 60 | 30 | 选 60fps 会让渲染耗时翻倍 |
| `--format` | mp4 / webm / mov / gif / png-sequence | mp4 | 取舍见下方「输出格式怎么选」 |
| `--resolution` | landscape / portrait / landscape-4k / square 等（含 `1080p`、`4k` 别名） | — | 借助 Chrome 的 `deviceScaleFactor` 做超采样；宽高比必须与合成一致，倍率必须取整数；不可与 `--hdr` 同用 |
| `--crf` | 0–51 | — | 数值越低画质越高；与 `--video-bitrate` 互斥 |
| `--video-bitrate` | 如 `10M`、`5000k` | — | 与 `--crf` 互斥 |
| `--hdr` / `--sdr` | 开关 | 关 | 强制 HDR / SDR；仅在 MP4 上可用 |
| `--workers` | 数字或 `auto` | auto | 每个 worker 会拉起一个 Chrome（约 256 MB 量级） |
| `--gpu` | 开关 | 关 | 让 FFmpeg 走 GPU 编码（NVENC / VideoToolbox / VAAPI / QSV） |
| `--browser-gpu` / `--no-browser-gpu` | 开关 | 本地 auto、docker 关 | Chrome / WebGL 是否使用宿主 GPU |
| `--browser-timeout` | 0.001–86400 秒 | 60 | Puppeteer 导航超时；重合成（视频多、字体多、含远程资源）到不了 `domcontentloaded` 时调大 |
| `--strict` | 开关 | 关 | 出现 lint error 就直接判失败 |
| `--strict-all` | 开关 | 关 | lint error 与 warning 都判失败 |
| `--quiet` | 开关 | 关 | 减少输出 |

### 输出格式怎么选

| 格式 | 什么时候用 | 注意 |
|---|---|---|
| `mp4` | 绝大多数交付场景 | 默认档；`--hdr` 仅在这个格式上生效 |
| `webm` | 需要透明通道嵌入网页 | 支持透明度 |
| `mov` | 需要透明通道进后期软件 | 支持透明度 |
| `gif` | 贴进 PR / README / 文档里自动播放 | 走两遍调色板编码；fps 上限 30，建议 `--fps 15`；**没有音频**；只支持 1-bit 透明；HDR 会回落为 SDR；循环次数用 `--gif-loop`（0 表示无限） |
| `png-sequence` | 交给 AE / Nuke / Fusion 合成 | 把 RGBA 帧序列写进目录 |

### 验收，不要只看退出码

```bash
test -s out.mp4
ffprobe -v error -show_format out.mp4
```

同时确认三件事：**文件存在、非空、时长合理**。渲染完成不等于渲染正确 —— 先跑 `snapshot` 把关键帧肉眼过一遍，再去相信成片。

### 渲染前的自查

- [ ] `npx hyperframes check` 通过（lint / 运行时 / 布局 / motion / 对比度 全 0 findings）。
- [ ] 只要用了子合成，每个宿主时段都看过 `snapshot`。
- [ ] `preview --background` 起过，项目 URL 返回 200，并且人已经确认过时间轴。
- [ ] 成片做了落盘验证（存在、非空、`ffprobe` 时长合理）。
- [ ] 交付用的稳定文件名是显式 `--output` 给的，而不是时间戳默认值。

---

## 六、渲染受管与云路径

本地跑不动，或者要一次出很多条的时候：

| 需求 | 命令 | 什么时候选它 |
|---|---|---|
| Docker 可复现 | `npx hyperframes render --docker` | 要跨主机逐字节一致，或宿主装不了 Chrome |
| 托管零基础设施 | `npx hyperframes cloud render` | 本地没有 Chrome / FFmpeg，也不想碰 AWS |
| 自管 AWS 分布式 | `npx hyperframes lambda render <project> --width 1920 --height 1080 --wait` | AWS 归属是硬要求 |
| 自管 GCP 分布式 | `npx hyperframes cloudrun render <project> --width 1920 --height 1080 --wait` | GCP 归属是硬要求 |

(table 说明 col reworded)

走任何云路径之前，先读对应的参考。另外，托管云上传工程时有体积上限；快接近上限时用 `cloud render --dry-run --json` 查清到底是什么把体积撑大了，**不要因为某单个素材大就随手放过**。

> 非本地渲染路径牵涉账号、上传与费用，本 Skill 只把桌面本地渲染的完整闭环讲透；云路径请以该工具自身的最新文档为准。

---

## 七、什么时候不该往下走

如果你身处一个**屏蔽 Chromium 的沙箱**（典型是 macOS 上的 seatbelt 类沙箱，`workspace-write` 模式），那么任何 Chrome —— 自带的、系统的、headless shell —— 都会在启动时直接死掉，报 `MachPortRendezvous` 一类错误。这是宿主层面的封锁，既不是引擎的问题，也不是 Chrome 装得不对：编译检查、音频处理都照常，**只有渲染用不了**。

正确的处置方式：**把这个阻塞讲清楚，把已经检查过的合成交付出去**，渲染交给 `--docker`、云渲染或者用户本人。**不要**自己搭一套替代的光栅化管线（magick / PIL / SVG 拼帧那一类）出来 —— 在这类被封锁的机器上，交付物就是「检查通过的合成 + 一份阻塞说明」。并且要在确认阻塞的那一刻就把结论写出来，别等到后续某个可选兜底步骤失败，把已经做完的工作报告一起冲掉。
