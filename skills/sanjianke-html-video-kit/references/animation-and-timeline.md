# HTML 动画与时间轴写法

这份文档解决「画面为什么对不上帧」：`data-*` 每个属性的含义、clip 与轨道的真实语义、子合成怎么挂、变量怎么绑、不同动画运行时的时长从哪来，以及可寻址动画的硬规矩。

核心心智模型只有一句：**渲染器拿到一个时间值，产出一张像素图，中间没有「播放」这个概念**。任何依赖「先经过前一帧才到这一帧」的状态——定时器、累加变量、事件驱动的动画——都会在乱序或并行采样时错位。

---

## 一、data-* 属性全表

### 合成根元素

每个可渲染合成都需要一个根元素，承载画布与总长。

| 属性 | 必需 | 含义 |
|---|---|---|
| `data-composition-id` | 是 | 唯一 ID。**必须与 `window.__timelines` 上的动画注册 key 一致** |
| `data-width` / `data-height` | 是 | 像素画布尺寸。常见 `1920x1080`、`1080x1920`、`1080x1080` |
| `data-duration` | 视情况 | 渲染总长（秒），**不是** GSAP 时间轴的时长。**编译期读一次**——脚本 `setAttribute` 或 `--variables` 都改不动它。只有当根不写它时，运行时才在脚本执行后从活 DOM / 时间轴推断 |
| `data-fps` | 否 | 帧率提示。CLI 的 render 参数可以覆盖输出帧率 |
| `data-composition-variables` | 否 | 写在 `<html>` 上的变量声明 JSON 数组 |

根元素应当 `position: relative`、有明确像素尺寸，并且除非有意让内容溢出画框，否则隐藏溢出。

`data-duration` 什么时候可以省：runtime 能自动推断时长时就不必写——已注册的 GSAP 时间轴、有限次 CSS 动画、有限次 WAAPI `element.animate()`、已注册的 Lottie 动画。**必须写**的情况：用 Three.js（推不出来）、有无限/无界的 CSS 或 WAAPI 动画、或者整页既没有 GSAP 时间轴也没有任何动画信号。`lint` 用 `root_composition_missing_duration_source` 守这条。

### 时间元素（clip）

**`data-start` 就是「这是一个时间元素」的标记。** 运行时收集 `[data-start]`，并以此驱动可见性——任何带它的元素都是被计时的。

| 属性 | 必需 | 含义 |
|---|---|---|
| `id` | `<video>` / `<audio>` 上必需，其余建议 | 媒体缺 id 时 `lint` 报 `media_missing_id`，而且**没 id 的 `<audio>` 根本不会被混音，成片是静音的**。其余元素缺 id 是 warning（`studio_missing_editable_id`），因为 Studio 需要稳定的编辑目标 |
| `data-start` | 是 | 起始秒数，或受支持的 clip 时间引用。**就是它把元素标记成时间元素的** |
| `data-duration` | `div` / `img` / 子合成必需 | 时长（秒）。视频音频在已知媒体长度时可以省。**完全解析不出时长，元素就没有终点，会一直显示到合成结束** |
| `data-track-index` | 否 | **只是 Studio 的显示轨道，渲染从不读它**，同一轨道上的 clip 可以时间重叠。不写时解析器给默认值，Studio 一条 clip 排一条道。两个时间重叠的 `<audio>` 用同一个 index 会触发 warning |
| `data-media-start` | 否 | 媒体源内的偏移入点（秒） |
| `data-volume` | 否 | 静态增益，默认 `1`（0 dB）。`0` 是静音，大于 `1` 是提升，上限 `3.98`（+12 dB）。淡入淡出要在时间轴上动画 `volume`，不要来回改这个值 |
| `data-has-audio` | 否（仅 `<video>`） | 自动检测漏判时，写 `"true"` 声明这个视频带音轨 |

**`class="clip"` 是约定，不是要求。** 运行时从不读它。仍然要写，因为脚手架共享的 `.clip { position: absolute; inset: 0 }` 就是场景满帧盒子的来源，Studio 拿它当编辑提示，缺了会 warn。丢掉它就得自己补布局。`<video>` / `<audio>` 上不要加。

**嵌套是允许的。** 时间元素里面的时间元素仍然被计时；**时间祖先会夹住后代**——祖先隐藏时后代不可能可见。根的直接子元素会拿到自动布局（下面说），**嵌套的不会**，所以要自己给定位。

### 子合成宿主

| 属性 | 必需 | 含义 |
|---|---|---|
| `data-composition-id` | 建议 | 被加载文件的合成 ID。惯例是写一致；写了不同 id 或不写也能跑，但**是静默解析**的 |
| `data-composition-src` | 是 | 子合成 HTML 的路径 |
| `data-width` / `data-height` | 否 | 这个实例的渲染尺寸。缺省时编译器从被加载文件的根元素回填 |
| `data-variable-values` | 否 | 按实例的变量覆盖，JSON 对象 |
| `data-var-src` | 否 | 把元素 `src` 绑到声明的变量 id（媒体/图片替换，作者写的 src 当兜底） |
| `data-var-text` | 否 | 把元素自身文本绑到标量变量 id；子元素保留 |

### 写作提示与布局豁免

| 属性 | 作用 |
|---|---|
| `id="root"` | 脚手架与转场目录的模板惯例，让 CSS 能用 `#root` 选中合成根，而不必写 `[data-composition-id="main"]`。运行时不要求，但生态里一致 |
| `data-root="true"` | 显式指定哪个是合成根。不写时运行时取最外层的 `[data-composition-id]`，绝大多数情况都对；合成嵌套、需要不含糊时再写 |
| `data-layout-allow-overflow` | 告诉 `check` 这里（及其子树）的溢出是有意的 |
| `data-layout-bleed="true"` | 只放行一处有意的正文裁切，比上面那个窄 |
| `data-layout-ignore` | 把这个元素整个排除在布局审计之外 |
| `data-layout-allow-caption-zone` | 对有意为之的下三分之一文案，退出 `--caption-zone` / `caption_zone_collision` 检查。它**不**抑制溢出、重叠、遮挡 |

关于 `data-layout-allow-overflow`，有三件必须知道的事：

1. **它沉默的范围比你想的大。** 属性沿子树继承（感知探针会向上找祖先），所以它同时压掉了 `text-clipping`、`content-cramped-container`、`foreground-over-panel` 这些渲染后感知检查。加在一个承载真实前景内容的常驻面板上，就等于把那个内容整个生命周期内的碰撞检查都关了。**尽量用最窄的范围**——绑到最小的装饰性包裹层，或者改用针对单个元素的 `data-layout-bleed="true"`。
2. **`overflow: hidden` 不能替代它。** 布局审计量的是采样时刻的 `getBoundingClientRect`，不是渲染像素；CSS 裁掉了视觉，但不会消掉布局 finding。
3. **两个画布/边缘检查不受它影响**：`primary-offscreen` 和 `foreground-over-panel` 是故意在 allow-overflow 下也跑的，所以它藏不住被画框切掉的标识，也藏不住压到面板边缘的文字。

当被指认的违规者是 `div.<comp>-root inside div.<comp>-root`（根把自己的子元素并集报成溢出）时，**修的是根，不是各个文字后代**——缩小字号是收敛不了的。

多场景 `group_wN.html` 这类续跑结构里，每个场景内的元素在其他场景的时间窗内都还留在 DOM 里，布局盒并集几乎必然在变形接缝处溢出画布。**在构造时**就给根和每个场景内主/辅元素打上这个属性，别等 `check` 报出来再补。

### 已废弃的名字

老工程和老示例里会见到这两个，写新代码用右边的：

| 旧名 | 用这个 |
|---|---|
| `data-layer` | `data-track-index` |
| `data-end` | `data-duration` |

### 两个特殊标记

- **`data-hidden`**：加在任意合成元素上，会在**预览和渲染里都**隐藏它，覆盖它的时间窗。它是非破坏性、可逆的，Studio 时间轴上的眼睛图标就是切它。
- **`data-hf-media-start-basis="global"`**：只给那些**故意**用根时间写媒体入点的老工程用。新合成一律用场景本地 `data-start`，**永远不要**靠数字是否重叠去猜基准。

---

## 二、可见性与布局语义

### 时间窗是左闭右开

元素在 `start ≤ t < start + duration` 期间显示，在 `t = start + duration` 那一刻已经隐藏。

由此推出两条实用结论：

1. **动画的收尾状态要落在 `data-duration` 之前一点点**，别压在边界上，否则最后一帧永远出不来。
2. 两个 clip 可以**背靠背**写（`b.start === a.start + a.duration`），中间不会多出一帧重叠。

### 根的直接子元素自动布局

对合成根的**直接子元素**、且带 `data-start` 的，运行时会强制 `position: absolute` 并锚到 `top: 0; left: 0`，在没有计算尺寸时撑到 100%，让各场景叠在同一个视口层里。

**没有 `data-start` 的元素会被完全跳过。** 一个不加计时的满幅背景必须自己写 `position: absolute; inset: 0`，否则它会塌成零高。

### data-track-index 的真实作用

它**不是时间约束**，渲染从读不读。它决定 Studio 时间轴上这条 clip 排在哪一栏，以及谁在前面（index 越大越靠前）。

实践含义：

- 给一个新增 clip 设 `data-start` / `data-duration` 时，要**有意识地参照周围 clip**去定；`data-track-index` 不需要找空位，它不约束时间。
- 两条时间重叠的 `<audio>` 放在同一个 index 上会 warn，但技术上仍然能渲。

### z 轴怎么办

运行时不管 z 序，交给 CSS。要严格分层就显式写 `z-index`。注意在用了 shader 转场或 HDR 媒体的**分层合成**路径上，引擎会把每个合成根强制透明，好让下层透出来——所以**满幅底色不要画在合成根上，画在一个满幅子元素上**（`position: absolute; inset: 0`）。普通渲染路径下根上的满幅填充是没问题的。

### 有一个静默陷阱：inline 元素的 transform 无效

`transform` / `scaleX` / `scaleY` 作用在 inline `<span>` 上是**空操作**；缩放一个 auto 宽度（0px）的元素**什么都看不到**——进度条、填充条就这样消失了。

规矩：**被 transform 的元素必须同时是块级（或 inline-block / flex item）且有真实宽高**（比如放在有尺寸的父元素里、自己 `width: 100%`）。这类问题自动检查未必抓得到。

同理，**绝对定位的装饰物如果要脉冲或回弹**（`yoyo` 缩放、`back.out`），要按它**峰值**尺寸留出净空，并且不能横跨 `overflow: hidden` 的边——否则要么压到邻居，要么被切掉。按最大帧定位，不是按静止帧。

---

## 三、动画运行时与时长契约

引擎在采集任何一帧之前，必须知道一个正的总时长——推不出来直接报 `Composition has zero duration.`。不同运行时这个时长从哪来，差别很大。

| 运行时 | 时长从哪来 | 能否自动推断 |
|---|---|---|
| GSAP | 时间轴对象自己提供 | 可以 |
| CSS | 所有动画元素里最长的 `animation-delay` + `animation-duration` × 有限 `animation-iteration-count`，再按各自 `data-start` 偏移 | 有限次可以；`iteration-count: infinite` **不行** |
| WAAPI | 最长的 `element.animate()` 效果的 `getComputedTiming().endTime` | 有限次可以；`iterations: infinite` **不行** |
| Lottie | 注册动画的原生长度（`totalFrames / frameRate`，或播放器自带 `duration`） | 总是有限，无论 `loop` |
| Three.js | **推不出来**。adapter 只通过 `hf-seek` 转发时间，没有 `AnimationClip` / `AnimationMixer` 的检视能力 | **不行** |

所以根上的 `data-duration`：当页面上所有非 GSAP 动画都有限时可选；当存在无限/无界的 CSS 或 WAAPI 动画、用了 Three.js、或者整页既没有 GSAP 时间轴也没有任何 adapter 能发现的动画信号时，**必填**。

### GSAP 的具体契约

```js
// 只建一条，必须 paused
const tl = gsap.timeline({ paused: true });

tl.fromTo("#title", { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: .8 }, 1);
tl.to("#rule", { scaleX: 1, duration: .6 }, 1.2);

// key = 根上的 data-composition-id
window.__timelines["main"] = tl;
```

- **异步构建是支持的**（`document.fonts.ready` 就是官方推荐路径）。要守的是：**构建完成之后才赋值**。提前把 key 建好会被当成已就绪并空嵌套，画面全空，`lint` 报 `gsap_timeline_registered_before_async_build`。
- 如果 key 与根的 `data-composition-id` 不一致，运行时在**它是唯一注册的时间轴**时仍然会绑上。注册了两条以上还不一致，渲染就冻在 t=0。
- **不要**为了渲染关键动效去调 `tl.play()`。
- **不要**为了凑时长建空 tween，改在 clip 上写 `data-duration`。
- 别手写 `window.__timelines = window.__timelines || {}`——运行时在你的内联脚本之前就建好了这个注册表。

---

## 四、五条硬规矩

这五条违反后**不一定报错**，但渲染结果会错，或者不可复现。

### 1. 视觉状态不能来自时钟、随机数和网络

禁止用于视觉状态的：

- `Date.now()`、`performance.now()`、任何渲染期时钟。
- 未播种的 `Math.random()`。要随机感的排布就用**固定种子**的 PRNG。
- 为必需资源做渲染期网络请求。内联或预打包它们。
- hover、滚动、指针、focus 状态。渲染器没有输入事件。

### 2. 没有无限循环

`repeat: -1` 要换成有限次数：

```js
// floor，不是 ceil；ceil 会冲过 data-duration，lint 报 gsap_repeat_ceil_overshoot
// max(0, …) 避免算出负数，负 repeat 等于无限
const cycle = 1.2;
const reps = Math.max(0, Math.floor(duration / cycle) - 1);
tl.to("#pulse", { scale: 1.08, duration: cycle / 2, yoyo: true, repeat: reps });
```

### 3. 不要接管 clip 的可见性

Hyperframes 的时间机制拥有 clip 可见性，所以：

- **不要 tween clip 元素的 `display` 或裸 `visibility`**，`lint` 会拒。
- 要淡出用 `autoAlpha`（它插值 opacity，只在隐藏端点翻 visibility）。
- 要确定性硬切，用零时长 `tl.set(..., { visibility: "hidden" })` 落在明确节拍上。

注意边界：**动 clip 元素的普通视觉属性**（`opacity`、transform、`filter`……）**完全没问题**，官方目录里大量这么做。被禁止的只是接管它的可见性。

也**没有**「可动属性白名单」。`lint` 执行的是**黑名单**，所以 `filter`、`clipPath`、`strokeDashoffset`、`width`、`height` 都是合法目标。在可选的情况下优先用 transform 和 opacity——那是性能考虑，不是正确性考虑。

还有一条：**同一个元素的同一个属性，不要同时被多条时间轴驱动**。GSAP 的覆盖行为依赖顺序，会在两次渲染之间翻转。

### 4. 先写静态终态，再从它动画

先用 HTML + CSS 把可见的**终态**搭出来，再用 tween 从别处来或回去。

配套规矩：

- 合成根有固定像素尺寸。
- 场景容器填满场景：`width: 100%; height: 100%; box-sizing: border-box`。
- 用 padding / flex / grid / `max-width` 做布局。能用布局容器解决时，**别用硬编码 `top` / `left` 定位主内容**。
- `position: absolute` 留给图层与装饰元素，不要当默认的内容布局策略。
- 动画优先用 transform 与 opacity。
- 文字要留在它该在的容器里。动态文本用 `max-width`、换行，或 `window.__hyperframes.fitTextFontSize(text, { maxWidth, fontFamily, fontWeight })`。
- **正文里不要用 `<br>`**。强制断行忽略真实渲染字宽，自然换行时还会多断一次，造成重叠。让文本靠 `max-width` 自己换。例外：短展示标题里每个词有意独占一行。

不重排测量文本可以走 `window.__hyperframes.pretext`：`pretext.prepare(text, font)` 然后 `pretext.layout(prepared, maxWidth, lineHeight)` 拿到 `{ lineCount, height }`。它在 canvas 上测量，不往页面里写再读回来，所以不会触发重排。`font` 是 CSS 字体简写串，如 `"700 90px Inter"`。要收缩包裹（按文字尺寸定容器）用 `prepareWithSegments` + `measureNaturalWidth`；要 `{ lineCount, maxLineWidth }` 用 `measureLineStats`。`clearCache` 与 `setLocale` 是**故意不暴露**的——它们会改跨合成共享的状态，让渲染结果取决于之前跑过什么。

### 5. id 在组装后必须唯一

组装后整页的 `id` 要唯一。子合成的 id 加自己的合成前缀（`#<comp-id>-hero`），这样你自己的 `#id` CSS 和 `getElementById` 才能解析到。

顺带说明：帧注入已经不再依赖 id 了——编译器会给每个 `video[src]` / `audio[src]` / `img[src]` 打一个文档内唯一的 `data-hf-render-id`。但**用 `<source>` 子元素而不是 `src` 属性的媒体不会被盖章**，那种情况下唯一 id 依然重要。

---

## 五、子合成

### 两种根形态，不能互换

- **独立合成**（顶层 `index.html`）：根 `<div data-composition-id="…">` 直接放在 `<body>` 里，**不要 `<template>` 包裹**。把独立根包进 template 会让内容全被藏住，`lint` 直接拒（`standalone_composition_wrapped_in_template`，error）。
- **子合成**（用 `data-composition-src` 加载）：把根包在 `<template>` 里。这是**该写的形态**——加载器也接受普通完整文档并回落到它的 `<body>`，但示例和工具都假定 templated 形态。

### 传输规则（容易踩）

对 **templated** 子合成，汇编器会丢掉文件自己 `<head>` 里的 `<style>` / `<script>`，所以**把 `<style>` / `<script>` 放进 template 里面**。`<link>` 两种情况下都会被提升出去。

### host-id 惯例

让宿主槽位、内部 template、`window.__timelines["<id>"]` 的 key **都用同一个 id**。用不同的局部 id 是支持的（汇编器会回落到文件里第一个根），但**失配是静默的**，没理由就别这么做。

### 挂载示例

子合成文件 `compositions/lower-third.html`：

```html
<template>
  <div data-composition-id="lower-third"
       data-width="1920" data-height="240" data-duration="5">
    <style>
      .lt { position: absolute; inset: 0; display: flex; align-items: center;
            padding: 0 80px; background: rgba(12,12,18,.82); color: #fff;
            font: 600 72px/1.2 "Noto Sans SC", sans-serif; }
    </style>
    <div class="lt" id="lower-third-box" data-start="0" data-duration="5">嘉宾姓名</div>
    <script>
      const tl = gsap.timeline({ paused: true });
      tl.fromTo("#lower-third-box", { x: -120, opacity: 0 },
                                    { x: 0, opacity: 1, duration: .5 });
      window.__timelines["lower-third"] = tl;
    </script>
  </div>
</template>
```

宿主 `index.html` 里挂：

```html
<div data-composition-id="lower-third"
     data-composition-src="compositions/lower-third.html"
     data-start="2"
     data-duration="5"
     data-track-index="2"
     data-width="1920"
     data-height="240"></div>
```

### 媒体可以任意深度

`<video>` / `<audio>` 在任何嵌套深度都能被框架找到——运行时用扁平查询取 `video, audio`，再沿 `element.closest("[data-composition-id]")` 找它所属的合成，并把它的本地 `data-start` 按所有祖先合成的累计绝对起点重定基准。所以宿主在 `2`、里面媒体在 `2`，那段媒体就在根时间的 `4` 开始；预览、snapshot、抽帧、渲染四处一致。

**新合成一律用场景本地 `data-start`。**

### 真正的限制在时间轴，不在媒体位置

子合成的时间轴**够不到宿主元素**——`document.querySelector("#host-id")` 和 gsap 选择器串都跨不过边界，它只能驱动自己那棵子树。

推论：如果媒体元素放在**宿主根**上，它的逐场景动效（缩放/透明度/变形/倾斜/呼吸）必须在 `index.html` 的主时间轴上、按**全局时间**写（场景本地时间 + 该场景槽位的 `data-start`）。把媒体放进场景子合成里，就能让子合成自己的时间轴用本地时间驱动它。没有透视父元素要做 3D 倾斜时，用 gsap 的 `transformPerspective`。

### 子合成挂载失败的四种表现

抓到这几类，当阻塞渲染的缺陷处理，不要带着往下走：

- 内容异常小且**没样式**（说明 template 里的 style 没生效或被丢了）。
- 图标被撑成画布大小。
- 主角元素缺失。
- 时间轴注册超时。

---

## 六、变量绑定

### 声明（写在 `<html>` 上）

```html
<html data-composition-variables='[
  {"id":"title","type":"string","label":"标题","default":"示例","maxLength":40},
  {"id":"accent","type":"color","label":"主色","default":"#66d9ef"},
  {"id":"speed","type":"number","label":"速度","default":1,"min":0.5,"max":3,"step":0.1,"unit":"x"},
  {"id":"dark","type":"boolean","label":"暗色","default":true},
  {"id":"mood","type":"enum","label":"基调","default":"calm",
   "options":[{"value":"calm","label":"平静"},{"value":"hype","label":"高能"}]}
]'>
```

各类型可选参数：`string` 支持 `placeholder` / `maxLength`；`number` 支持 `min` / `max` / `step` / `unit`；`color`、`boolean` 无额外参数；**`enum` 必须给 `options`**（`[{value, label}, ...]`）。

**始终给有意义的 `default`**，这样不开 CLI 覆盖也能预览。

### 声明式绑定（不用写脚本）

```html
<img class="clip" data-start="0" data-duration="5" data-var-src="heroImage" src="fallback.jpg" />
<h1  class="clip" data-start="0" data-duration="5" data-var-text="title">兜底文本</h1>
<style>
  .card { color: var(--accent); }   /* 每个标量变量自动成为根上的 --{id} */
</style>
```

- `data-var-src="id"` 替换元素 `src`（URL 字符串或图片对象）；作者写的 `src` 是兜底。
- `data-var-text="id"` 替换元素自身文本；子元素（嵌套 clip、带动画的 span）会保留。
- **带音频的媒体要保留真实兜底 `src`**——渲染的音频抽取读的是作者写的属性，`lint` 会报 `media_variable_src_no_fallback`。

超出直接替换的逻辑（循环、条件、派生值），在初始化时读一次：

```js
const { title, accent } = window.__hyperframes.getVariables();
document.getElementById("title").textContent = title;
```

**在初始化时读一次，不要在每帧动画回调里读**——变量在一次渲染中不会变。

### 覆盖

```bash
npx hyperframes render --variables '{"title":"Q4 报告"}'
npx hyperframes render --variables-file vars.json
npx hyperframes render --variables '{"title":"Q4"}' --strict-variables
```

`--strict-variables` 在 CI 里很有用：未声明的 key、类型不匹配、enum 值不在 `options` 里，全都从 warning 升级成 error。

子合成宿主上的每实例覆盖：

```html
<div data-composition-id="card" data-composition-src="compositions/card.html"
     data-start="0" data-duration="4"
     data-variable-values='{"title":"第一章","accent":"#ff4d2e"}'></div>
```

### 再强调一次两种 JSON 形状

- `data-composition-variables` → **声明数组**（schema）：`[{id, type, label, default}, ...]`
- `--variables` 与 `data-variable-values` → **按 id 索引的对象**（取值）：`{"title":"Q4"}`

混了不会报错，只会静默不生效。

### 变量也能进调色

**媒体调色**可以在 `data-color-grading` 的 JSON 里用精确的变量引用：把 `$gradingPreset` 或 `${gradingIntensity}` 作为整个字段值，运行时会用当前合成的变量解析它，再应用着色器调整、收尾细节、模糊/像素化效果和自定义 LUT。

---

## 七、媒体写法

```html
<video
  id="a-roll"
  class="clip"
  src="assets/demo.mp4"
  data-start="0"
  data-duration="12"
  data-track-index="0"
  muted
  playsinline
></video>

<audio
  id="a-roll-audio"
  src="assets/demo.mp4"
  data-start="0"
  data-duration="12"
  data-track-index="10"
  data-volume="1"
></audio>
```

**画面元素必须静音并 inline；声音永远走独立的 `<audio>`**，即使源文件是同一个。

### 媒体的六条规矩

1. **不要在合成代码里调 `video.play()` / `audio.play()` / pause / seek。** 播放归框架管。
2. **不要用子合成时间轴驱动宿主根的媒体。** 跨不过子树边界，完全没效果。
3. **不要动画"有时间标记的"媒体元素尺寸。** 要动就动一个不带时间标记的包裹层。
4. **不要把视频嵌进带时间标记的包裹层。** `lint` 报 `video_nested_in_timed_element`（error），而失败是真实的：抽帧器按视频自己的 `data-start` 解析起点、不叠加包裹层偏移，可见性却按包裹层的时间窗算，于是先取错源帧、再在槽位中途消失。**时间写在包裹层上或者写在媒体元素上，绝不两边都写。** 子合成宿主是例外，它传播偏移所以正常工作。
5. **永远不要给 `<video>` / `<audio>` 加 `crossorigin`。** `lint` 无条件拒绝（`media_crossorigin_breaks_preview`，error）。原因是：一个不带 `Access-Control-Allow-Origin` 的媒体主机在预览里会**静默失败**，而渲染却照常成功，把 bug 藏起来。没有抑制开关，即使为了 canvas / WebGL / WebAudio 读回也不行。唯一的替代是把资源放到你自己的同源路径下。
6. **每个 `<audio>` 都要有 `id`。** 混音器选的是 `audio[id][src]`，没 id 的永远不会被混进去，**成片静音**。

### 音量

静态基线用 `data-volume`（默认 `1`；`0` 静音；大于 `1` 提升到 `3.98` 即 +12 dB 上限）。

**淡入淡出和闪避在时间轴上动画 `volume`**，不要来回改 `data-volume`：

```js
tl.to("#bgm", { volume: 0, duration: 1 }, "outro");
```

运行时探测时间轴上的 volume 关键帧，并在预览与渲染里一致地应用。

有一个反直觉点：**tween 里的值会替换基线，而不是按基线缩放**。所以在一个增益不是 `1` 的 clip 上，要缩放的是 tween 的目标值（写 `{ volume: 1.95 }`，不是 `{ volume: 1 }`）。两者不一致时 `lint` 给 `audio_volume_tween_overrides_gain`。

### 时长与编码

`<video>` / `<audio>` 在媒体自带长度已知、且你要用整段时可以省 `data-duration`。

输入编码方面：渲染走 FFmpeg 解码，帧是预抽取后注入的，所以 **HEVC / H.265（8bit 与 10bit）在任何平台上都能正确渲染**。实时预览会自动给浏览器不友好的素材做代理（首次使用时转码并缓存一份 H.264 副本，可用 `--no-proxy` 或 `media.autoProxy: false` 关掉），并且 `lint` 会给出 info 级的 `hevc_preview_codec` 提示，点名受影响的素材。

---

## 八、改现有合成的时候

- **先读文件。** 保留无关的时间、轨道、ID、变量、媒体路径。
- 对上现有的合成 ID 与时间轴 key。
- 加一条 clip：它的 `data-start` / `data-duration` 要**有意识地参照周围 clip** 去定。`data-track-index` 是 Studio 显示道，不是时间约束，**不必找空位**。
- 加子合成前，先确认它内部的 `data-composition-id`。
- 写完之后按第一节的自查走一遍：`lint` → `snapshot`（有子合成时）→ `preview` → 得到批准再 `render`。
