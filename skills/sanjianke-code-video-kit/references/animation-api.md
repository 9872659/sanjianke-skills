# 动画与合成 API

帧号怎么变成画面、图层怎么排时间、数据怎么驱动模板。

---

## 一、两个基础钩子

### `useCurrentFrame()`

返回当前帧号，从 `0` 开始。渲染时它被逐帧递增，Studio 里随播放头变化。

```tsx
const frame = useCurrentFrame();
```

整条动画链路就是「帧号 → 某个数值 → 某个样式」：

```tsx
const frame = useCurrentFrame();
const opacity = frame / 30;                  // 第 0 帧全透明，第 30 帧不透明
return <div style={{opacity}}>淡入</div>;
```

朴素除法够用但不优雅——它没有边界，超出范围会得到 `> 1` 或 `< 0` 的值。所以实际都配 `interpolate()`。

### `useVideoConfig()`

返回当前 Composition 的元信息：

```tsx
const {fps, durationInFrames, width, height, id} = useVideoConfig();
```

| 字段 | 用途 |
|---|---|
| `fps` | `spring()` 必传；把秒换算成帧 |
| `durationInFrames` | 算收尾动画的起点，例如「最后 20 帧淡出」 |
| `width` / `height` | 按比例算布局，或做响应式定位 |
| `id` | 在共享组件里区分是哪个 Composition 在用它 |

组件里**不要硬编码帧率**。写死 30 而 Composition 改成 60 之后，所有基于秒的动画都会快一倍。

---

## 二、`interpolate()`：把帧号映射成数值

签名是「把 `inputRange` 里的 `input`，按对应关系映射到 `outputRange`」。

```tsx
import {interpolate} from 'remotion';

const opacity = interpolate(frame, [0, 30], [0, 1]);
//  第 0 帧 → 0
//  第 15 帧 → 0.5
//  第 30 帧 → 1
```

### 边界处理

默认行为是**线性外推**，也就是第 60 帧会算出 `2`。这几乎永远不是你想要的：

```tsx
const opacity = interpolate(frame, [0, 30], [0, 1], {
  extrapolateLeft: 'clamp',    // 小于 0 帧时锁在 0
  extrapolateRight: 'clamp',   // 大于 30 帧时锁在 1
});
```

三个可选值：`'extend'`（默认，外推）、`'clamp'`（夹住）、`'identity'`（返回原值）。

**推荐习惯：所有 `interpolate()` 都显式写 `extrapolateRight: 'clamp'`。** 忘了写是「元素在动画结束后突然飞出画面」这类怪现象的常见原因。

### 非线性映射

`inputRange` 和 `outputRange` 长度必须一致，可以有多段，数值不必递增：

```tsx
// 0-15 帧从下往上进入，15-45 帧停在原地，45-60 帧继续上移
const y = interpolate(frame, [0, 15, 45, 60], [100, 0, 0, -60], {
  extrapolateLeft: 'clamp',
  extrapolateRight: 'clamp',
});

// 透明度先亮后暗再亮（做闪烁）
const blink = interpolate(frame, [0, 10, 20, 30], [0, 1, 0.2, 1], {
  extrapolateRight: 'clamp',
});
```

非单调的 `outputRange` 完全合法，做呼吸、闪烁、来回摆动都靠它。

### 缓动

```tsx
import {Easing, interpolate} from 'remotion';

const eased = interpolate(frame, [0, 30], [0, 1], {
  easing: Easing.bezier(0.25, 0.1, 0.25, 1),   // CSS 里那条 cubic-bezier
  extrapolateRight: 'clamp',
});

// 其他常用
Easing.in(Easing.cubic)       // 慢进快出
Easing.out(Easing.exp)        // 指数减速，入场很自然
Easing.inOut(Easing.quad)     // 两头慢中间快
Easing.elastic(1)             // 弹性抖动
Easing.bounce                 // 落地回弹
```

缓动是「看起来专业」和「看起来像 PPT」的分界线。默认的线性运动在视频里非常廉价，入场至少加一个 `Easing.out`。

---

## 三、`spring()`：物理感的入场

`interpolate()` 是匀速映射，`spring()` 是按弹簧物理算出来的衰减曲线。入场、弹出、缩放用它比缓动更自然。

```tsx
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';

const frame = useCurrentFrame();
const {fps} = useVideoConfig();

const scale = spring({
  frame,
  fps,                          // 必传
  config: {
    damping: 14,                // 默认 10。越大越不弹
    stiffness: 100,             // 默认 100。越大越快
    mass: 1,                    // 默认 1。越小越轻快
  },
});
```

返回值默认从 `0` 走到 `1`，可以改端点：

```tsx
const x = spring({frame, fps, from: -200, to: 0});   // 从左侧滑入
```

### 控制时长与延迟

```tsx
const v = spring({
  frame,
  fps,
  durationInFrames: 30,   // 把曲线拉伸成正好 30 帧，比调 config 好预测
  delay: 15,              // 第 15 帧才开始动，之前一直返回 from
});
```

**`durationInFrames` 是让动画「卡点」的关键。** 光调 `stiffness` 你没法精确知道它几帧结束，而视频里动画必须卡在确定的时间点上（比如配乐的重拍）。只要时长能定，就优先用 `durationInFrames`。

注意执行顺序：先按 `durationInFrames` 拉伸，再 `reverse`，最后 `delay`。

### 弹性的取舍

`damping` 默认 10 会明显回弹（overshoot），活泼但有时显得轻浮。企业宣传、数据播报这类场景把 `damping` 提到 20–30 就几乎不弹了。想要绝对不越界：

```tsx
spring({frame, fps, config: {damping: 200, overshootClamping: true}});
```

### 组合用法

弹簧和插值叠用是最常见的模式：

```tsx
const enter = spring({frame, fps, durationInFrames: 25});
const y = interpolate(enter, [0, 1], [80, 0]);        // 弹簧驱动位移
const blur = interpolate(enter, [0, 1], [8, 0]);      // 弹簧驱动模糊
```

因为 `enter` 本身就是 `0~1` 的曲线，把它当「进度条」喂给 `interpolate()`，就能让任何属性共享同一条物理曲线。

---

## 四、颜色与随机

### `interpolateColors()`

```tsx
import {interpolateColors} from 'remotion';

const bg = interpolateColors(frame, [0, 60], ['#0b1020', '#ff5722'], {
  extrapolateRight: 'clamp',
});
```

颜色在 RGB 空间插值。要做品牌色过渡，注意深色到亮色的中间态可能发灰，必要时拆成三段。

### `random()`

**绝对不要在组件里用 `Math.random()`。** 它每次求值都不同，同一帧渲染两次结果不一样，并行渲染出来的片段会跳变。

用确定性的 `random()`：

```tsx
import {random} from 'remotion';

const seed = random('particle-7');            // 传字符串或数字，同参数永远同结果
const position = random(`particle-${index}`); // 用索引区分不同元素
```

做粒子、随机排布、抖动时都靠它。同一个种子在每一帧、每一台机器上都返回同一个数。

---

## 五、图层与时间编排

### `<AbsoluteFill>`

铺满整个画面的绝对定位容器，是构图的基本单位。所有位置都是相对于它算的。

```tsx
<AbsoluteFill style={{backgroundColor: '#000', justifyContent: 'center', alignItems: 'center'}}>
  ...
</AbsoluteFill>
```

嵌套多个 `AbsoluteFill` 就是叠加图层，后面的盖在前面上面。

### `<Sequence>`：控制出现时段

`<Sequence>` 内的组件拿到的是**相对帧号**——`from` 是 20，那么内部第 0 帧对应整片的第 20 帧。

```tsx
import {Sequence} from 'remotion';

<Sequence from={0} durationInFrames={60}>
  <Title />          {/* 内部的 useCurrentFrame() 从 0 开始，持续 60 帧 */}
</Sequence>

<Sequence from={60} durationInFrames={90}>
  <Product />
</Sequence>
```

两个关键参数：

- `from`：从第几帧开始出现。
- `durationInFrames`：出现多少帧。**不写就是一直到结束。**
- `layout="none"`：不想被包一层绝对定位容器时用，适合只做帧偏移不做布局的场景。

这个「内部帧号重定位」的特性是整个时间编排的基础。有了它，写一个「5 秒入场动画」的组件不用关心它在片子里排第几秒。

### `<Series>`：顺序串场

比手写累加 `from` 更省心，按顺序依次排列：

```tsx
import {Series} from 'remotion';

<Series>
  <Series.Sequence durationInFrames={60}>
    <SceneA />
  </Series.Sequence>
  <Series.Sequence durationInFrames={90}>
    <SceneB />
  </Series.Sequence>
  <Series.Sequence durationInFrames={45} offset={-15}>
    <SceneC />   {/* offset 为负表示提前 15 帧开始，做重叠转场 */}
  </Series.Sequence>
</Series>
```

`offset` 是拉近镜头、制造叠化的常用手段。

### `<Loop>` 与 `<Freeze>`

```tsx
import {Freeze, Loop} from 'remotion';

// 让一个 30 帧的动画循环 4 次
<Loop durationInFrames={30} times={4}>
  <Pulse />
</Loop>

// 定格在第 60 帧的画面，持续 45 帧
<Freeze frame={60} durationInFrames={45}>
  <Scene />
</Freeze>
```

`<Freeze>` 在「最后一帧停住做结尾板」这类需求上很好用，比手动截帧省事。

---

## 六、音视频与素材

### 素材引用：`staticFile()`

`public/` 下的文件用 `staticFile()` 引用，路径从根算起：

```tsx
import {Audio, Img, staticFile} from 'remotion';

<Img src={staticFile('logo.png')} style={{width: 200}} />
<Audio src={staticFile('bgm.mp3')} volume={0.6} />
```

**`<Img>` 会阻塞渲染直到图片解码完成。** 这是刻意的设计——否则截图时图片还没解码，画面就是一个空洞。所以能用 `<Img>` 就别用原生 `<img>`。

### 视频：用 `<OffthreadVideo>`

```tsx
import {OffthreadVideo, staticFile} from 'remotion';

<OffthreadVideo src={staticFile('clip.mp4')} volume={0} />
```

它比原生 `<video>` 快得多，因为它把解码放到渲染线程之外，而且逐帧精确——原生 `<video>` 在逐帧截图时会因为 seek 精度不足而出现错帧。**凡是渲染成片，就用 `<OffthreadVideo>`。**

常用属性：

- `startFrom` / `endAt`：裁剪片段（单位是帧）。
- `volume`：音量，可为函数实现随帧变化。
- `playbackRate`：变速。
- `muted`：静音。

### 按帧控制音量

`volume` 可以是函数，用来做淡入淡出：

```tsx
<Audio
  src={staticFile('bgm.mp3')}
  volume={(f) =>
    interpolate(f, [0, 30, durationInFrames - 30, durationInFrames], [0, 0.6, 0.6, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    })
  }
/>
```

这是「配乐在片尾自然收掉」的标准写法。

### 音画对齐

音频时长决定了画面节奏。用 `@remotion/media-utils` 拿音频真实时长：

```tsx
import {getAudioDurationInSeconds} from '@remotion/media-utils';
import {calculateMetadata, staticFile} from 'remotion';

// 在 calculateMetadata 里读音频时长，再决定视频总长
const calculateMetadata = async () => {
  const dur = await getAudioDurationInSeconds(staticFile('voice.mp3'));
  return {durationInFrames: Math.ceil(dur * 30) + 15};   // 留 15 帧尾巴
};
```

这比手工填时长靠谱，尤其是配音长度由 TTS 生成的场景。

### 字幕

`@remotion/captions` 提供字幕数据结构与 TikTok 风格的字幕组件，配合 Whisper 系列包可以先把音频转成带时间戳的字幕，再用它渲染。走这条链路时注意：转写是异步且可能很慢的，务必在 `calculateMetadata()` 里完成，不要在渲染帧里做。

---

## 七、参数化：让模板能被数据驱动

这是把「做一个视频」变成「做一条生产线」的关键。

### 三层数据来源

| 层 | 定义位置 | 作用 |
|---|---|---|
| 默认 props | `<Composition defaultProps={...}>` | 定义数据形状，让 Studio 能脱离真实数据设计画面 |
| 输入 props | `--props=./data/x.json` 或 `renderMedia({inputProps})` | 渲染时覆盖默认值，批量任务靠它 |
| 计算后 props | `calculateMetadata()` 的返回值 | 拉取远程数据、做二次加工、动态决定元信息 |

解析顺序是「默认 props ← 输入 props 覆盖 ← `calculateMetadata` 再加工」，最终结果交给组件。

### 用 Zod 定义形状并自动生成控件

```tsx
import {z} from 'zod';
import {Composition} from 'remotion';

export const itemSchema = z.object({
  title: z.string(),
  price: z.string(),
  accent: z.string(),
  tags: z.array(z.string()),
  showBadge: z.boolean(),
});

export const itemDefaultProps: z.infer<typeof itemSchema> = {
  title: '新品上架',
  price: '¥199',
  accent: '#ff5722',
  tags: ['限时', '包邮'],
  showBadge: true,
};

<Composition
  id="ProductCard"
  component={ProductCard}
  durationInFrames={150}
  fps={30}
  width={1080}
  height={1920}
  schema={itemSchema}
  defaultProps={itemDefaultProps}
/>
```

传了 `schema` 之后，Studio 侧边栏会按 schema 生成对应的编辑控件（文本输入、开关、列表），运营同学可以不改代码调参数。Zod 里加 `.describe('...')` 能给出中文提示。

### `getInputProps()`

在组件里直接读输入，适合组件不在 Composition 直属链路里的场合：

```tsx
import {getInputProps} from 'remotion';

const {title} = getInputProps();   // 读到的就是 --props 传进来的内容
```

多数情况下不需要它——把值当 props 传下去更清晰。

### `calculateMetadata()`：异步准备与动态元信息

这是唯一应该做远程请求的地方。

```tsx
import {CalculateMetadataFunction, staticFile} from 'remotion';
import {z} from 'zod';

const schema = z.object({sku: z.string()});

export const calculateMetadata: CalculateMetadataFunction<z.infer<typeof schema>> = async ({
  props,
  abortSignal,
}) => {
  const res = await fetch(`https://api.example.com/products/${props.sku}`, {signal: abortSignal});
  if (!res.ok) throw new Error(`取商品失败：${props.sku}`);
  const product = await res.json();

  return {
    // 用返回的数据替换/补充 props
    props: {...props, ...product},
    // 按文案长度动态决定时长
    durationInFrames: 90 + Math.ceil(product.title.length / 4) * 15,
    // 每条产品的输出文件名
    defaultOutName: `product-${props.sku}`,
  };
};
```

它能返回的字段：

| 字段 | 用途 |
|---|---|
| `props` | 最终传给组件的 props |
| `durationInFrames` | 动态时长 |
| `width` / `height` | 动态尺寸（一条模板同时出竖屏和横屏） |
| `fps` | 动态帧率 |
| `defaultCodec` | 该 Composition 的默认编码 |
| `defaultOutName` | 默认输出文件名（不含扩展名） |
| `defaultVideoImageFormat` | `png` / `jpeg` / `none` |
| `defaultPixelFormat` | 像素格式 |
| `defaultProResProfile` | ProRes 档位 |
| `defaultSampleRate` | 音频采样率 |

返回值优先级：**高于 Composition 上的静态 props，低于命令行或 `renderMedia()` 显式传入的同名选项**。所以命令行给 `--width` 依然能覆盖它。

### `calculateMetadata()` 的约束

- **只执行一次**，独立于渲染并发，跑在单独的标签页里。别在这里做「每帧都要跑」的事。
- **必须在超时内返回**，默认 30 秒。慢接口要么自己加超时，要么在组件里用 `delayRender()` 承担等待。
- **返回值必须是纯 JSON 可序列化对象**（`Date`、`Map`、`Set`、`staticFile()` 除外）。
- **每次 props 变化都会重新执行。** 在 Studio 里改一个输入框就会触发一次请求，注意别把接口打爆。
- 用 `abortSignal` 取消过期请求，否则快速连续改 props 会导致旧响应覆盖新响应。

### 可序列化边界

props 无论如何流转，最终都要能被 JSON 化：

| 能传 | 不能传 |
|---|---|
| 字符串、数字、布尔、null | 函数、类实例 |
| 数组、普通对象 | DOM 节点、React 元素 |
| `Date`、`Map`、`Set`（特例） | `undefined`（会被丢掉） |
| `staticFile()` 的返回值 | 循环引用对象 |

传颜色统一用字符串。传格式化函数这种需求，改成传「格式类型标识」，在组件内部查表。

---

## 八、踩坑清单

- [ ] 每个 `interpolate()` 都写了 `extrapolateRight: 'clamp'`（左边界同理）。
- [ ] 没有硬编码 fps，一律从 `useVideoConfig()` 取。
- [ ] 没有用 `Math.random()` / `Date.now()` / `performance.now()`。
- [ ] `<Sequence>` 里的组件用的是相对帧号，没有误把全局帧号当时间基准。
- [ ] `<Sequence>` 该写 `durationInFrames` 的地方都写了，没有依赖「到片尾为止」的默认行为。
- [ ] 视频一律用 `<OffthreadVideo>`，图片一律用 `<Img>`。
- [ ] `delayRender()` 与 `continueRender()` 成对，失败分支也放行。
- [ ] 远程请求只在 `calculateMetadata()` 里做，且用了 `abortSignal`。
- [ ] props 全部可 JSON 序列化。
- [ ] 入场动画至少加了一层缓动或弹簧，没有裸线性运动。
- [ ] 动画结束时间点用了 `durationInFrames` / 显式帧区间，而不是「大概差不多」的 `stiffness` 调参。
