# 批量出片与常见坑

这份文档解决两件事：**一套模板怎么稳定出几十条**，以及**出不来的时候按什么顺序查**。

---

# 第一部分：批量出片

## 一、先决定"什么是变量"

批量出片的前提是把模板里的可变成分抽干净。一条实用的分界：

| 属于变量 | 属于模板（写死） |
|---|---|
| 文案：标题、副标题、数据、人名、日期 | 版式：网格、间距、层级 |
| 主色、强调色 | 字体族与字号阶梯（除非按内容长度自适应） |
| 时长（当条目长度真的不同时） | 动画曲线与节奏 |
| 图片 / 视频 / 音频路径 | 场景顺序与转场 |
| 开关类选项（要不要片尾、要不要水印） | 分辨率与帧率 |

判断标准很简单：**这一项换掉会不会改变设计决策**。如果只是换个字，那它是变量；如果换了之后版式要重排，那它不是变量，是另一个模板。

## 二、声明变量

声明写在**主合成 `index.html` 的 `<html>` 上**，是一个**数组**：

```html
<html data-composition-variables='[
  {"id":"title",  "type":"string", "label":"标题",   "default":"默认标题", "maxLength":36},
  {"id":"kicker", "type":"string", "label":"引题",   "default":"数据周报"},
  {"id":"metric", "type":"number", "label":"数字",   "default":128, "unit":"万"},
  {"id":"accent", "type":"color",  "label":"强调色", "default":"#ff4d2e"},
  {"id":"logoOn", "type":"boolean","label":"显示标识","default":true}
]'>
```

而**取值的对象**（渲染时覆盖、宿主实例覆盖）是**按 id 索引的 JSON 对象**：

```json
{ "title": "四月复盘", "kicker": "增长月报", "metric": 342, "accent": "#22c55e", "logoOn": false }
```

这两种形状混了**不会报错，只会静默不生效**。这是批量出片最常见的"我明明传了值画面没变"。

### 在画面里消费变量

优先用声明式绑定，不用写脚本：

```html
<h1 class="clip" id="hero"
    data-start="0" data-duration="6"
    data-var-text="title">默认标题</h1>

<img class="clip" id="logo"
     data-start="0" data-duration="6"
     data-var-src="logoFile" src="assets/fallback-logo.png" />

<style>
  /* 每个标量变量都会自动成为根上的 --{id} 自定义属性 */
  .accent-bar { background: var(--accent); }
  /* 布尔型不适合直接进 CSS，用类名开关 */
</style>
```

布尔开关靠脚本读一次：

```js
const { logoOn, accent } = window.__hyperframes.getVariables();
document.getElementById("logo").style.display = logoOn ? "" : "none";
document.documentElement.style.setProperty("--accent", accent);
```

**在初始化时读一次就够了。** 变量在一次渲染里不会变，写在动画 tick 里读纯属浪费。

### 三条变量硬规矩

1. **每个变量都要有可用的 `default`。** 否则不开 CLI 覆盖时预览直接是坏的，模板也没法单人调试。
2. **带音频的媒体元素必须保留真实兜底 `src`。** 渲染的音频抽取读的是作者写的属性，变量只替换活 DOM 上的值——`lint` 会报 `media_variable_src_no_fallback`。
3. **`enum` 必须给 `options`。** 少了它 Studio 的编辑 UI 和 `--strict-variables` 都不知道合法值域。

## 三、批量渲染

### 数据文件

`--batch` 接受两种形状——**JSON 数组**，或者**带 `rows` 数组的对象**：

```json
{
  "rows": [
    { "name": "alpha", "title": "四月复盘", "kicker": "增长月报", "metric": 342, "accent": "#22c55e" },
    { "name": "beta",  "title": "五月计划", "kicker": "排期",     "metric": 96,  "accent": "#3b82f6" }
  ]
}
```

`name` 不是保留字，它只是一个普通行键，用来拼输出文件名。

### 跑起来

```bash
npx hyperframes render \
  --batch rows.json \
  --output "renders/{name}.mp4" \
  --batch-concurrency 1 \
  --strict-variables
```

### 输出模板规则

输出路径模板支持两类占位符：

- `{index}` —— 行序号。
- **任意行键** —— 但键名只能含字母、数字、`_`、`.`、`-`；值必须是字符串、数字或布尔；`null`、对象、数组都非法。

两条硬性后果：

- **占位符缺失是错误。** 模板里写的键在某一行不存在，直接报错，不会回落到空串。
- **输出冲突是错误。** 两行拼出同一个文件名会报错，不会静默覆盖。

省掉 `--output` 时，生成的文件名里会带 `{index}`，保证行与行不撞。

### 互斥项

**`--batch` 不能和 `--variables` 或 `--variables-file` 同用。** 每一行自己就是那一次的完整变量集。

### 并发

`--batch-concurrency` **默认 `1`**。往上调要保守，因为**单次渲染本身已经在用多个 worker**，而且每个 worker 会拉一个 Chrome（约 256 MB 量级）。先看机器有多少可用内存，再决定倍数；内存吃紧时回到 `--batch-concurrency 1`，或者给单次渲染加 `--workers 2`。

### 失败策略

```bash
npx hyperframes render --batch rows.json --batch-fail-fast
```

- 加了 `--batch-fail-fast`：第一个失败之后不再调度新行。
- 不加：独立行继续跑完，**失败不会消失，仍然留在 manifest 里**。

批量场景一般**不加**这个开关更划算——一个数据坏了不该让另外 99 条白等。但要在跑完之后检查 manifest。

### 变量预检

```bash
npx hyperframes render --batch rows.json --strict-variables
```

它会在**开始渲染之前**逐行校验声明契约（未声明的 key、类型不匹配、enum 值越界），一旦违反就在产出任何文件之前中止。批量一定要加——否则你要等一小时才发现第 40 行的类型写错了。

### manifest.json

命令会在输出目录写下 `manifest.json`，并在整个运行过程中持续更新。每行记录：变量、状态、输出路径、错误、耗时。

**完成的定义不是"命令退出了"**，而是三件事同时成立：

1. manifest 里**没有 failed 行**。
2. 每个完成的行，输出文件**存在**。
3. 每个输出**非空**，且时长**合理**。

对应的校验：

```bash
# 用 jq 快速看有没有失败行
jq -e '[.rows[] | select(.status != "completed")] | length == 0' renders/manifest.json

# 逐条确认体积
find renders -name '*.mp4' -size -1k -print
```

`--json` 会输出适合 agent 和 CI 消费的进度事件。

## 四、批量出片的工程化建议

- **单条先跑通，再放批量。** 先用一条真实数据 `render --variables '{...}'` 渲一条，确认版式扛得住最长/最短文案，再批量。
- **数据里准备两行极端值**：最长的标题、最大的数字、空的可选字段。模板在极端值上崩掉比在批量中途崩掉便宜得多。
- **文案长度要有上限意识。** 版式扛不住就让变量带 `maxLength`，或者对动态文本用 `window.__hyperframes.fitTextFontSize(text, { maxWidth, fontFamily, fontWeight })` 自适应字号。
- **中文一定要指定字体。** 无头 Chrome 里默认字体族未必有合适的中文字形。字体放进 `assets/`，`@font-face` 指向本地文件，别指望系统字体。
- **每条渲染后用 `ffprobe` 抽一条确认时长**，而不是只看 manifest 的 completed 状态。
- **批量产物命名带业务键**（`{name}`），不要只靠 `{index}`——出错时按文件名能直接定位到哪一行数据。

---

# 第二部分：常见坑

下面按**症状**组织，每个都给定位顺序。查之前先跑一次体检，很多问题一眼就出来了：

```bash
npx hyperframes doctor
npx hyperframes lint
```

## 一、不要浪费时间的两个命令

- **`events`** 是技能上报**自己**被调用情况的遥测端点，匿名发一个事件然后退出 0，传什么参数都一样。它不是用来读回遥测的，agent 没有任何理由手调它。
- **`validate` / `inspect` / `layout`** 是给老脚本留的别名。维护中的那个叫 **`check`**，所有新流程都按 `check` 写。

## 二、成片没有声音

按这个顺序查，命中率从高到低：

1. **`<audio>` 有没有 `id`？** 混音器选的是 `audio[id][src]`。没 id 的音频永远不会被混进去，**而且不报错**。这是第一位的原因。
2. **声音是不是放在 `<video>` 上了？** 画面元素的音频不参与混音——`<video>` 必须 `muted`，声音单独写一个 `<audio>`，哪怕源文件是同一个。
3. **`data-volume` 是不是 `0`？** 或者被某条 tween 改成了 0 而你没注意。
4. **`data-volume` 和 volume tween 打架了？** tween 的值**替换**基线而不是缩放。在一个基线不是 `1` 的 clip 上，你要缩放的是 tween 的目标值。`lint` 会报 `audio_volume_tween_overrides_gain`。
5. **`<audio>` 的时间窗是不是落在合成总长之外？** 记得确认 `data-start + data-duration` 没超根上的 `data-duration`。
6. **导出成 GIF 了？** GIF 格式**不带音频**，这是格式限制，不是 bug。
7. **用了变量的媒体元素丢了兜底 `src`？** 音频抽取读的是作者写的属性，`lint` 报 `media_variable_src_no_fallback`。

## 三、画面全黑 / 内容全空

1. **时间轴 key 对不上？** `window.__timelines["<id>"]` 的 key 必须等于根的 `data-composition-id`。注册了两条以上还不匹配，渲染冻在 t=0。只注册一条时能兜住，所以这类 bug 往往"加了个子合成之后才出现"。
2. **时间轴提前注册了？** 异步构建（`document.fonts.ready` 之类）时，**必须在 tweens 加完之后**才赋值。提前建一个空对象会被当成已就绪并空嵌套，画面全空。`lint` 报 `gsap_timeline_registered_before_async_build`。
3. **内容是不是全堆在左上角？** 那是根没有可解析高度。根要明确像素尺寸，且从根到 `height: 100%` 的每一层祖先都要有已解析高度，否则 flex / `100%` 子元素塌成 0 高。这个静默 bug 自动检查未必抓得到——**用 `snapshot` 看图**。
4. **子合成被包错了？** 顶层 `index.html` 的根**不能**包在 `<template>` 里，`lint` 报 `standalone_composition_wrapped_in_template`。
5. **templated 子合成里的 `<style>` / `<script>` 放错位置了？** 汇编器会丢掉文件自己 `<head>` 里的这两样，**必须放进 template 里面**（`<link>` 两种位置都会被提升）。
6. **在分层合成路径上？** 用了 shader 转场或 HDR 媒体时，引擎会把每个合成根强制透明，好让下层透出来。满幅底色要画在**满幅子元素**上（`position: absolute; inset: 0`），画在根上会被抹掉。

## 四、lint 报错（这些是"第一次构建必踩"）

写的时候就直接避开，比报错再查便宜：

| 报错 | 怎么修 |
|---|---|
| `gsap_css_transform_conflict` | CSS 写初始 `transform`、GSAP 又 tween 同一属性，两者打架。**把初值写进 tween**：`gsap.fromTo(el, { x: -40 }, { x: 0 })` |
| `media_crossorigin_breaks_preview` | `<video>` / `<audio>` 上有 `crossorigin`。**删掉**。没有抑制开关，因为它在预览里静默失败而渲染却正常 |
| `video_nested_in_timed_element` | `<video data-start>` 的祖先也有 `data-start`。把时间写在**包裹层或视频**上，不要两边都写。子合成宿主不受影响 |
| `media_missing_id` | `<audio>` 缺 `id`。补上，否则没声音 |
| `gsap_timeline_registered_before_async_build` | 异步构建里先注册后加 tween。把赋值移到**构建完成之后** |
| `root_composition_missing_duration_source` | 没有可推断的时长来源，也没有根 `data-duration`。补根 `data-duration` |
| `gsap_repeat_ceil_overshoot` | `repeat` 用了 `ceil` 算出并冲过 `data-duration`。换 `Math.max(0, Math.floor(duration / cycle) - 1)` |
| `timed_element_missing_clip_class` | 时间元素缺 `class="clip"`（warn）。要么补 class，要么自己实现那套满帧布局 |
| `standalone_composition_wrapped_in_template` | 独立合成的根被包进 template。把 template 去掉 |
| `studio_missing_editable_id` | 元素缺 id（warn）。Studio 需要稳定的编辑目标 |

**一个致命组合**：只要还有 lint **error**，布局与对比度审计就是关着的，`check` 会报 `0 sample(s)` 和 `0/0 text checks`。**这看起来像干净通过，其实什么都没跑。** 先清 error，再信那些数字。

## 五、`check` 报了布局溢出

1. **先分清是真的还是并集误差。** 当被指认的违规者是 `div.<comp>-root inside div.<comp>-root`（根把自己的子元素并集报成溢出），**修的是根**——缩小字号是收敛不了的。
2. **多场景续跑结构（`group_wN.html`）几乎必然报。** 每个场景内的元素在其他场景的时间窗里仍然留在 DOM 中，布局盒并集在变形接缝处溢出画布。**在构造时**就给根和每个场景内主/辅元素打 `data-layout-allow-overflow`，别等报出来才补。
3. **`overflow: hidden` 不能消掉 finding。** 审计量的是采样时刻的 `getBoundingClientRect`，不是渲染像素。
4. **要豁免就用最窄的范围。** `data-layout-allow-overflow` 沿子树继承，还会连带压掉 `text-clipping`、`content-cramped-container`、`foreground-over-panel`。绑到最小的装饰性包裹层，或者改用单元素的 `data-layout-bleed="true"`。
5. **两个检查不受豁免影响**：`primary-offscreen` 和 `foreground-over-panel` 在 allow-overflow 下照样跑。被画框切掉的标识、压到面板边缘的文字，藏不住。

## 六、看不到某个元素 / 元素闪一下就没了

1. **inline 元素上的 transform 是空操作。** `transform` / `scaleX` / `scaleY` 作用在 inline `<span>` 上什么都不做；缩放一个 auto 宽度（0px）的元素显示不出任何东西——进度条、填充条就是这么消失的。给它们 `display: block` / `inline-block` 或作为 flex item，**并且给真实宽高**。
2. **`data-duration` 解析不出来。** 那样元素**没有终点**，会一直显示到合成结束；反过来如果时长写短了，它会提前消失。
3. **时间祖先夹住了。** 祖先隐藏时后代不可能可见——检查祖先的时间窗。
4. **被 `data-hidden` 标了。** 它覆盖时间窗，在预览和渲染里都隐藏。Studio 时间轴的眼睛图标就是切它。
5. **收尾动画压在右开边界上。** 可见性是 `[start, start + duration)`，在 `t = start + duration` 那一刻已经隐藏。动画终态要**落在 `data-duration` 之前一点点**。
6. **绝对定位的脉冲装饰物被 `overflow: hidden` 切了。** 要按**峰值**尺寸留净空，不是静止尺寸。

## 七、渲染结果每次都不一样

渲染的可复现性有三个契约共同保证。出现漂移就逐条排：

1. **有没有用渲染期时钟？** `Date.now()`、`performance.now()`，任何依赖"墙钟"的写法。
2. **有没有未播种的 `Math.random()`？** 要随机感的排布必须用**固定种子**的 PRNG。
3. **有没有无限循环？** `repeat: -1`。换成 `Math.max(0, Math.floor(duration / cycle) - 1)`。
4. **有没有渲染期网络请求？** 合成里 `<script src="https://cdn.jsdelivr.net/...">` 这类写法在渲染时是真去拉的。追求可复现就**本地化或内联**依赖。
5. **有没有拿输入态驱动动画？** hover、滚动、指针、focus——渲染器**没有输入事件**。
6. **有没有让同一元素的同一属性被多条时间轴同时驱动？** GSAP 的覆盖行为依赖顺序，会在两次渲染之间翻转。
7. **是不是在等字体但没锁？** `document.fonts.ready` 是推荐路径，但字体本身要随工程走——**把字体文件放进 `assets/` 并 `@font-face` 指向本地**，不要依赖系统字体或远程 CDN。
8. **跨机器要比对？** 用 `render --docker`。宿主 Chrome 版本不同，像素输出就会漂——这也是浏览器版本被固定的原因。

**一条心态建议**：想驱动视觉却伸手去拿 `setTimeout` / `requestAnimationFrame` / `addEventListener` 的时候，停下来。把它重写成时间轴上的一条 tween。

## 八、Chrome / FFmpeg 起不来

```bash
npx hyperframes doctor              # 先看是哪一项 fail
npx hyperframes browser ensure      # 缺自带 Chrome 时补
```

对照常见原因：

| 症状 | 处理 |
|---|---|
| FFmpeg 缺失 | 按平台装：macOS `brew install ffmpeg`，其余用对应包管理器。装完重跑 `doctor` |
| 自带 Chrome 缺失 | `npx hyperframes browser ensure` |
| 内存不足 | 关掉其他 Chrome；降 `--workers`；改 `--quality draft` |
| 重合成导航超时 | 调大 `--browser-timeout`（默认 60 秒）；多视频、多字体、远程资源的合成到不了 `domcontentloaded` |
| 容器里跑 | 注意 `/dev/shm` 那一项，容器内专用 |
| 宿主跑不了 Chrome | 换 `render --docker`，或走云渲染 |

### 一个特殊局面：沙箱屏蔽 Chromium

在 macOS 上的 seatbelt 类沙箱（比如 `workspace-write`）里，Chromium 的 Mach port 引导被拦，**任何 Chrome**——自带的、系统的、headless shell——都会在启动时直接死掉，报 `MachPortRendezvous` 一类错误。

这是**宿主级封锁**，不是引擎或 Chrome 安装的问题。典型表现是：编译检查、音频处理都正常，**只有渲染不可用**。

正确处置：

1. **立刻把阻塞说清楚**，交出已经检查通过的合成。渲染交给 `--docker`、云渲染或用户本人。
2. **不要自己搭替代光栅化管线**（magick / PIL / SVG 拼帧那一类）。在被封锁的机器上，交付物就是"检查通过的合成 + 这个阻塞说明"。
3. **在识别出阻塞的那一刻就把结论写出来**，别等后续某个可选兜底步骤失败，把已经做完的工作报告一起冲掉。

## 九、渲染慢

- **`--quality draft` 迭代，`high` 只用于交付。** 别用交付档位做迭代。
- **60fps 让渲染耗时翻倍。** 只在真的需要时用。
- **`--workers` 的瓶颈常常是内存，不是 CPU。** 每个 worker 拉一个 Chrome（约 256 MB 量级），把它调高可能反而更慢。
- **`--resolution` 超采样会成倍加大工作量。** 只在交付档需要时开。
- **先量再优化。** `npx hyperframes benchmark ./my-composition.html` 给出基线，改完再量一次，不要凭感觉调。
- **确认没有在渲染期拉远程资源。** 网络抖动会直接变成渲染时间的方差。

## 十、render 报"没有时长"

`Composition has zero duration.` 意思是采集引擎在开始前拿不到正的总时长。

- 有 GSAP 时间轴时：说明时间轴**没有注册成功**，或者注册 key 对不上。查 `window.__timelines`。
- 没有 GSAP 时：CSS / WAAPI 的 `iteration-count: infinite`、`iterations: infinite` **推不出时长**；Three.js **根本推不出来**。这些情况**必须在根上写 `data-duration`**。

## 十一、验收不要只看退出码

```bash
test -s out.mp4
ffprobe -v error -show_format out.mp4
```

渲染完成 ≠ 渲染正确。三件事同时成立才算数：**文件存在、非空、时长合理**。在这之前，先用 `snapshot` 把关键帧肉眼看一遍。

---

## 十二、一页速查

| 症状 | 第一刀切哪 |
|---|---|
| 没声音 | `<audio>` 有没有 `id` |
| 全黑 / 全空 | `window.__timelines` 的 key 对不对 |
| 内容堆左上角 | 根有没有可解析高度 |
| 元素闪一下没 | 有没有动 inline 元素的 transform |
| 每次不一样 | 有没有时钟 / 未播种随机 / `repeat: -1` / 渲染期网络 |
| 布局报溢出 | 是不是多场景并集，用最窄的 allow-overflow |
| Chrome 起不来 | `doctor`，然后 `browser ensure` 或改 `--docker` |
| 没有时长 | 是否无限动画或 Three.js，补根 `data-duration` |
| 批量有失败 | 看 `manifest.json` 的 failed 行，不是看退出码 |
| 变量没生效 | 声明是数组、取值是对象，两种形状别混 |
