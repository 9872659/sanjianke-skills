# 批量出片与常见坑

本文要解决的是两件事：**一套模板如何稳定产出几十条**，以及**产不出来时按什么顺序排查**。

---

# 第一部分：批量出片

## 一、先决定"什么是变量"

批量出片的前提，是把模板里可变的成分抽干净。一条实用的分界线：

| 属于变量 | 属于模板（写死） |
|---|---|
| 文案：标题、副标题、数据、人名、日期 | 版式：网格、间距、层级 |
| 主色、强调色 | 字体族与字号阶梯（除非要按内容长度自适应） |
| 时长（当各条目长度确实不同时） | 动画曲线与节奏 |
| 图片 / 视频 / 音频路径 | 场景顺序与转场 |
| 开关类选项（要不要片尾、要不要水印） | 分辨率与帧率 |

判断方法就一句：**把这一项换掉，会不会改变设计决策**。如果只是换个字，它是变量；如果换完之后版式要重排，那它就不是变量，而是另一个模板。

## 二、声明变量

声明写在**主合成 `index.html` 的 `<html>` 上**，形状是一个**数组**：

```html
<html data-composition-variables='[
  {"id":"title",  "type":"string", "label":"标题",   "default":"默认标题", "maxLength":36},
  {"id":"kicker", "type":"string", "label":"引题",   "default":"数据周报"},
  {"id":"metric", "type":"number", "label":"数字",   "default":128, "unit":"万"},
  {"id":"accent", "type":"color",  "label":"强调色", "default":"#ff4d2e"},
  {"id":"logoOn", "type":"boolean","label":"显示标识","default":true}
]'>
```

而**取值的对象**（渲染时覆盖、宿主实例覆盖用）则是**按 id 索引的 JSON 对象**：

```json
{ "title": "四月复盘", "kicker": "增长月报", "metric": 342, "accent": "#22c55e", "logoOn": false }
```

这两种形状一旦混用**不会报错，只会静默不生效**——批量出片里最常见的"我明明传了值画面却没变"就是这么来的。

### 在画面里消费变量

优先走声明式绑定，不必写脚本：

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

布尔开关交给脚本读一次：

```js
const { logoOn, accent } = window.__hyperframes.getVariables();
document.getElementById("logo").style.display = logoOn ? "" : "none";
document.documentElement.style.setProperty("--accent", accent);
```

**在初始化阶段读一次就够。** 变量在一次渲染过程中不会变化，放进动画 tick 里反复读纯属浪费。

### 三条变量硬规矩

1. **每个变量都得有可用的 `default`。** 否则不通过 CLI 覆盖时预览直接是坏的，模板也没法由单人调试。
2. **带音频的媒体元素必须保留真实兜底 `src`。** 渲染时的音频抽取读的是作者写下的属性，变量只替换活 DOM 上的值——`lint` 会报 `media_variable_src_no_fallback`。
3. **`enum` 必须给 `options`。** 缺了它，Studio 的编辑 UI 与 `--strict-variables` 都不知道合法值域在哪。

## 三、批量渲染

### 数据文件

`--batch` 能接受两种输入形状：**JSON 数组**，或者**一个带 `rows` 数组的对象**：

```json
{
  "rows": [
    { "name": "alpha", "title": "四月复盘", "kicker": "增长月报", "metric": 342, "accent": "#22c55e" },
    { "name": "beta",  "title": "五月计划", "kicker": "排期",     "metric": 96,  "accent": "#3b82f6" }
  ]
}
```

`name` 不是保留字，它只是个普通行键，用来拼输出文件名。

### 跑起来

```bash
npx hyperframes render \
  --batch rows.json \
  --output "renders/{name}.mp4" \
  --batch-concurrency 1 \
  --strict-variables
```

### 输出模板规则

输出路径模板里有两类占位符可用：

- `{index}` —— 代表行序号。
- **任意行键** —— 不过键名只允许字母、数字、`_`、`.`、`-`；值只能是字符串、数字或布尔，`null`、对象、数组都不合法。

由此带来两条硬性后果：

- **占位符缺失即错误。** 模板里写的键在某一行为不存在，直接报错，不会回落到空串。
- **输出冲突即错误。** 两行拼出同一个文件名会报错，不会静默覆盖。

省掉 `--output` 时，生成的文件名会带 `{index}`，以此保证行与行不撞。

### 互斥项

**`--batch` 不能与 `--variables` 或 `--variables-file` 同用。** 每一行自身就是那一次的完整变量集。

### 并发

`--batch-concurrency` **默认为 `1`**。往上调要保守：**单次渲染本身已经在用多个 worker**，而每个 worker 都会拉起一个 Chrome（约 256 MB 量级）。先看机器有多少可用内存再定倍数；内存吃紧就退回 `--batch-concurrency 1`，或者给单次渲染加 `--workers 2`。

### 失败策略

```bash
npx hyperframes render --batch rows.json --batch-fail-fast
```

- 加了 `--batch-fail-fast`：第一个失败出现后不再调度新行。
- 不加：其余独立行继续跑完，**失败也不会消失，仍然留在 manifest 里**。

批量场景通常**不加**这个开关更划算——一个数据坏了，不该让另外 99 条干等。但跑完之后必须检查 manifest。

### 变量预检

```bash
npx hyperframes render --batch rows.json --strict-variables
```

它会在**开始渲染之前**逐行校验声明契约（未声明的 key、类型不匹配、enum 值越界），一旦不通过，就在产出任何文件之前中止。批量务必加上——否则你要等一小时才发现第 40 行的类型写错了。

### manifest.json

该命令会在输出目录里写下 `manifest.json`，并在整个运行期间不断刷新。每一行记录的内容是：变量、状态、输出路径、错误与耗时。

**"完成"的定义不是"命令退出了"**，而是下面三件事同时成立：

1. manifest 里**不存在 failed 行**。
2. 每个已标记完成的行，其输出文件**确实存在**。
3. 每个输出都**非空**，并且时长**合理**。

可以这样校验：

```bash
# 用 jq 快速看有没有失败行
jq -e '[.rows[] | select(.status != "completed")] | length == 0' renders/manifest.json

# 逐条确认体积
find renders -name '*.mp4' -size -1k -print
```

`--json` 会输出适合 agent 与 CI 消费的进度事件。

## 四、批量出片的工程化建议

- **先让单条跑通，再放批量。** 先用一条真实数据 `render --variables '{...}'` 渲一条，确认版式扛得住最长与最短的文案，然后再批量。
- **数据里预备两行极端值**：最长的标题、最大的数字、空的可选字段。模板在极端值上崩掉，比在批量中途崩掉便宜得多。
- **对文案长度要有上限意识。** 版式扛不住，就让变量带 `maxLength`，或者对动态文本用 `window.__hyperframes.fitTextFontSize(text, { maxWidth, fontFamily, fontWeight })` 自适应字号。
- **中文必须显式指定字体。** 无头 Chrome 里的默认字体族未必有合适的中文字形。把字体放进 `assets/`，用 `@font-face` 指向本地文件，不要指望系统字体。
- **每条渲染后拿 `ffprobe` 抽一条确认时长**，而不是只看 manifest 的 completed 状态。
- **批量产物的命名带上业务键**（`{name}`），不要只靠 `{index}`——出错时看文件名就能直接定位到哪一行数据。

---

# 第二部分：常见坑

下面按**症状**来组织，每一项都给出定位顺序。排查之前先跑一次体检，很多问题一眼就能看出来：

```bash
npx hyperframes doctor
npx hyperframes lint
```

## 一、不要浪费时间的两个命令

- **`events`** 是技能上报**自己**被调用情况的遥测端点：匿名发一个事件然后退出 0，传什么参数都一样。它并非用来读回遥测，agent 没有任何理由手工调它。
- **`validate` / `inspect` / `layout`** 是给老脚本留的别名。仍在维护的那个叫 **`check`**，所有新流程都按 `check` 写。

## 二、成片没有声音

按下面的顺序排查，命中率从高到低：

1. **`<audio>` 有没有 `id`？** 混音器选的是 `audio[id][src]`，没有 id 的音频永远不会被混进去，**而且不报错**。这是排第一的原因。
2. **声音是不是挂在 `<video>` 上了？** 画面元素的音频不参与混音——`<video>` 必须 `muted`，声音单独写一个 `<audio>`，哪怕源文件是同一个。
3. **`data-volume` 是不是 `0`？** 或者被某条 tween 改成了 0，而你没注意到。
4. **`data-volume` 和 volume tween 打架了？** tween 的值是**替换**基线而不是在基线上缩放。若某个 clip 的基线不是 `1`，你要缩放的就是 tween 的目标值。`lint` 会报 `audio_volume_tween_overrides_gain`。
5. **`<audio>` 的时间窗是不是掉到合成总长之外了？** 确认一下 `data-start + data-duration` 没有超过根上的 `data-duration`。
6. **是不是导出成 GIF 了？** GIF **不带音频**，这是格式限制，不是 bug。
7. **用了变量的媒体元素丢了兜底 `src`？** 音频抽取读的是作者写下的属性，`lint` 报 `media_variable_src_no_fallback`。

## 三、画面全黑 / 内容全空

1. **时间轴 key 对不上？** `window.__timelines["<id>"]` 的 key 必须等于根上的 `data-composition-id`。注册两条以上仍不匹配，渲染就会冻在 t=0。只注册一条时尚能兜住，所以这类 bug 往往表现为"加了个子合成之后才出现"。
2. **时间轴提前注册了？** 异步构建（`document.fonts.ready` 之类）时，**必须在 tweens 全部加完之后**才赋值。提前建一个空对象会被当成已就绪并作空嵌套，画面全空。`lint` 报 `gsap_timeline_registered_before_async_build`。
3. **内容是不是全堆在左上角？** 那是根缺少可解析的高度。根要有明确的像素尺寸，并且从根到 `height: 100%` 之间每一层祖先都得有已解析高度，否则 flex / `100%` 子元素会塌成 0 高。这个静默 bug 自动检查未必抓得到——**用 `snapshot` 看图**。
4. **子合成被包错了？** 顶层 `index.html` 的根**不能**被包在 `<template>` 里，`lint` 报 `standalone_composition_wrapped_in_template`。
5. **templated 子合成里的 `<style>` / `<script>` 放错位置了？** 汇编器会丢掉文件自身 `<head>` 里的这两样，**必须放进 template 内部**（`<link>` 两种位置都会被提升）。
6. **是不是走在分层合成路径上？** 用到 shader 转场或 HDR 媒体时，引擎会把每个合成根强制为透明，好让下层透出来。满幅底色要画在**满幅子元素**上（`position: absolute; inset: 0`），画在根上会被抹掉。

## 四、lint 报错（这些属于"第一次构建必踩"）

写的时候就顺手避开，比报了错再去查便宜：

| 报错 | 怎么修 |
|---|---|
| `gsap_css_transform_conflict` | CSS 写了初始 `transform`，GSAP 又去 tween 同一属性，两边打架。**把初值写进 tween**：`gsap.fromTo(el, { x: -40 }, { x: 0 })` |
| `media_crossorigin_breaks_preview` | `<video>` / `<audio>` 上带了 `crossorigin`。**删掉**。没有抑制开关，因为它会让预览静默失败而渲染却正常 |
| `video_nested_in_timed_element` | `<video data-start>` 的祖先也带 `data-start`。把时间写在**包裹层或视频**上，不要两边都写。子合成宿主不受影响 |
| `media_missing_id` | `<audio>` 缺 `id`。补上，否则没有声音 |
| `gsap_timeline_registered_before_async_build` | 异步构建里先注册后加 tween。把赋值挪到**构建完成之后** |
| `root_composition_missing_duration_source` | 既没有可推断的时长来源，根上也没有 `data-duration`。补上根 `data-duration` |
| `gsap_repeat_ceil_overshoot` | `repeat` 用 `ceil` 算出来并冲过了 `data-duration`。换成 `Math.max(0, Math.floor(duration / cycle) - 1)` |
| `timed_element_missing_clip_class` | 时间元素缺 `class="clip"`（warn）。要么补上 class，要么自己实现那套满帧布局 |
| `standalone_composition_wrapped_in_template` | 独立合成的根被包进了 template。把 template 去掉 |
| `studio_missing_editable_id` | 元素缺 id（warn）。Studio 需要一个稳定的编辑目标 |

**一个致命组合**：只要还存在 lint **error**，布局与对比度审计就一直是关着的，`check` 会报 `0 sample(s)` 与 `0/0 text checks`。**这看上去像干净通过，实际什么都没跑。** 先把 error 清完，再去相信那些数字。

## 五、`check` 报了布局溢出

1. **先分清是真的溢出还是并集误差。** 当被指认的违规者是 `div.<comp>-root inside div.<comp>-root`（根把自己的子元素并集报成了溢出），**要修的是根**——靠缩小字号收敛不了。
2. **多场景续跑结构（`group_wN.html`）几乎必然报。** 每个场景内的元素在其他场景的时间窗里依旧留在 DOM 中，布局盒并集就会在变形接缝处溢出画布。**在构造阶段**就给根以及每个场景内的主/辅元素打上 `data-layout-allow-overflow`，别等报出来再补。
3. **`overflow: hidden` 消不掉 finding。** 审计量的是采样时刻的 `getBoundingClientRect`，不是渲染出来的像素。
4. **要豁免就用最窄的范围。** `data-layout-allow-overflow` 会沿子树继承，还会连带压掉 `text-clipping`、`content-cramped-container`、`foreground-over-panel`。把它绑到最小的装饰性包裹层，或者改用单元素的 `data-layout-bleed="true"`。
5. **有两个检查不受豁免影响**：`primary-offscreen` 与 `foreground-over-panel` 在 allow-overflow 下照样会跑。被画框切掉的标识、压到面板边缘的文字，都藏不住。

## 六、看不到某个元素 / 元素闪一下就没了

1. **inline 元素上的 transform 是空操作。** `transform` / `scaleX` / `scaleY` 作用在 inline `<span>` 上什么也不做；去缩放一个 auto 宽度（0px）的元素同样显示不出任何东西——进度条、填充条就是这样消失的。给它们 `display: block` / `inline-block`，或者作为 flex item，**并且给真实宽高**。
2. **`data-duration` 解析不出来。** 那样元素**没有终点**，会一直显示到合成结束；反过来说，时长写短了它就会提前消失。
3. **被时间祖先夹住了。** 祖先隐藏时后代不可能可见——去检查祖先的时间窗。
4. **被 `data-hidden` 标了。** 它会覆盖时间窗，在预览与渲染里都隐藏。Studio 时间轴上那个眼睛图标切的就是它。
5. **收尾动画压在右开边界上了。** 可见性是 `[start, start + duration)`，到 `t = start + duration` 那一刻已经隐藏。动画终态要**落在 `data-duration` 之前一点点**。
6. **绝对定位的脉冲装饰物被 `overflow: hidden` 切了。** 要按**峰值**尺寸留净空，不是按静止尺寸。

## 七、渲染结果每次都不一样

渲染的可复现性由三个契约共同保证。一旦出现漂移，逐条排查：

1. **是否用了渲染期时钟？** 例如 `Date.now()`、`performance.now()`，以及任何依赖"墙钟"的写法。
2. **有没有未播种的 `Math.random()`？** 想要随机感的排布，必须用**固定种子**的 PRNG。
3. **是否留下了无限循环？** 也就是 `repeat: -1`。把它改为 `Math.max(0, Math.floor(duration / cycle) - 1)`。
4. **有没有渲染期网络请求？** 合成里 `<script src="https://cdn.jsdelivr.net/...">` 这类写法在渲染时是真的会去拉的。追求可复现就**本地化或内联**依赖。
5. **是否用输入态驱动了动画？** hover、滚动、指针、focus 都算——渲染器**没有输入事件**。
6. **是否让同一元素的同一属性被多条时间轴同时驱动？** GSAP 的覆盖行为取决于顺序，会在两次渲染之间翻来覆去。
7. **是不是在等字体却没锁住它？** `document.fonts.ready` 是推荐路径，但字体本身要随工程走——**把字体文件放进 `assets/` 并用 `@font-face` 指向本地**，不要依赖系统字体或远程 CDN。
8. **要跨机器比对？** 用 `render --docker`。宿主 Chrome 版本不同，像素输出就会漂——这也是浏览器版本被固定的原因。

**一条心态建议**：当你想驱动视觉、手却伸向 `setTimeout` / `requestAnimationFrame` / `addEventListener` 的时候，先停下来，把它重写成时间轴上的一条 tween。

## 八、Chrome / FFmpeg 起不来

```bash
npx hyperframes doctor              # 先看是哪一项 fail
npx hyperframes browser ensure      # 缺自带 Chrome 时补
```

对照下面这些常见原因：

| 症状 | 处理 |
|---|---|
| FFmpeg 缺失 | 按平台安装：macOS 用 `brew install ffmpeg`，其余用对应包管理器。装完重跑 `doctor` |
| 自带 Chrome 缺失 | `npx hyperframes browser ensure` |
| 内存不足 | 关掉其他 Chrome；调低 `--workers`；改用 `--quality draft` |
| 重合成导航超时 | 调大 `--browser-timeout`（默认 60 秒）；多视频、多字体、远程资源的合成到不了 `domcontentloaded` |
| 容器里跑 | 留意 `/dev/shm` 那一项，它是容器内专用的 |
| 宿主跑不了 Chrome | 换 `render --docker`，或者走云渲染 |

### 一个特殊局面：沙箱屏蔽 Chromium

在 macOS 上的 seatbelt 类沙箱（比如 `workspace-write`）里，Chromium 的 Mach port 引导会被拦掉，**任何 Chrome**——自带的、系统的、headless shell——都会在启动时直接死掉，报 `MachPortRendezvous` 一类错误。

这属于**宿主级封锁**，不是引擎的问题，也不是 Chrome 安装的问题。典型表现是：编译检查、音频处理都正常，**唯独渲染不可用**。

正确的做法是：

1. **立刻把阻塞讲清楚**，交出已经检查通过的合成。渲染交给 `--docker`、云渲染或者用户本人。
2. **不要自己搭一套替代的光栅化管线**（magick / PIL / SVG 拼帧那一类）。在被封锁的机器上，交付物就是"检查通过的合成 + 这份阻塞说明"。
3. **一旦确认阻塞，就在那一刻把结论写下来**，不要等到后面某个可选兜底步骤也失败，连已经做完的工作报告一并作废。

## 九、渲染慢

- **迭代用 `--quality draft`，`high` 只留给交付。** 别拿交付档位做迭代。
- **60fps 会让渲染耗时翻倍。** 只在确实需要时用。
- **`--workers` 的瓶颈常常是内存而不是 CPU。** 每个 worker 都会拉起一个 Chrome（约 256 MB 量级），调高它可能反而更慢。
- **`--resolution` 超采样会成倍放大工作量。** 只在交付档需要时开。
- **先量，再优化。** 用 `npx hyperframes benchmark ./my-composition.html` 拿一个基线，改动之后再量一次，别凭感觉调。
- **确认没有在渲染期拉远程资源。** 网络抖动会直接变成渲染耗时的方差。

## 十、render 报"没有时长"

`Composition has zero duration.` 的意思是采集引擎在开始之前拿不到正的总时长。

- 有 GSAP 时间轴时：说明时间轴**没有注册成功**，或者注册的 key 对不上。去查 `window.__timelines`。
- 没有 GSAP 时：CSS / WAAPI 的 `iteration-count: infinite`、`iterations: infinite` **推不出时长**；Three.js **根本推不出来**。这两种情况都**必须在根上写 `data-duration`**。

## 十一、验收不要只看退出码

```bash
test -s out.mp4
ffprobe -v error -show_format out.mp4
```

渲染完成不等于渲染正确。必须三件事同时成立才作数：**文件存在、非空、时长合理**。在据此下判断之前，先用 `snapshot` 把关键帧肉眼看一遍。

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
