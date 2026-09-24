# 快速开始与核心概念

从空目录走到一个能播放的 MP4，以及渲染失败时该往哪看。

---

## 一、它到底是怎么工作的

先建立正确的心智模型，后面所有行为都能解释得通。

```
你的 React 代码
   ↓ 打包（Webpack / Vite）
一个静态站点产物
   ↓ 起一个本地 HTTP 服务
无头 Chrome 打开它
   ↓ 逐帧：把时间设成第 N 帧 → 截图
一叠 PNG / JPEG
   ↓ 交给自带的 FFmpeg
MP4
```

由此推出三条必须记住的结论：

1. **你写的是网页，不是视频**。任何能在浏览器里显示的东西都能进画面；反过来，浏览器不支持的东西也进不去。
2. **时间是帧号，不是秒**。组件不会「播放」，它被反复以不同帧号求值。`useCurrentFrame()` 返回的就是「现在是第几帧」。
3. **每一帧都是独立求值的结果**。所以同一帧必须每次算出一样的东西，否则并行渲染拼接出来的片子会出现画面跳变。所有随机、时间、顺序依赖都是雷区。

「渲染」这个词在上游有两层含义，别混：**Studio 里拖动时间轴叫预览**，几乎瞬时、不产出文件；**跑渲染命令产出文件才叫 Render**，这一步在许可条款里是有计量意义的（详见 `SKILL.md` 的许可段落）。

---

## 二、项目结构

```text
my-video/
├─ package.json
├─ remotion.config.ts        # 渲染与打包的全局默认值
├─ tsconfig.json
├─ public/                   # 静态资源，用 staticFile() 引用
│  ├─ logo.png
│  └─ bgm.mp3
├─ data/                     # 批量任务的 props 数据（自己建的）
│  ├─ item-001.json
│  └─ item-002.json
├─ out/                      # 渲染产物（自己建的，记得进 .gitignore）
└─ src/
   ├─ index.ts               # 入口：registerRoot()
   ├─ Root.tsx               # 注册所有 Composition
   ├─ ProductCard.tsx        # 一个具体画面
   └─ components/            # 可复用零件
```

`src/` 不是硬性规定，但上游模板默认用它，跟着走省事。

---

## 三、两步搭起骨架

### 入口：只做一件事

```ts
// src/index.ts
import {registerRoot} from 'remotion';
import {Root} from './Root';

registerRoot(Root);
```

`registerRoot()` 告诉 Remotion「从哪个组件开始找 Composition」。一个项目只有一个入口，`Root` 里可以挂任意多个 Composition。

### 注册表：所有 Composition 都在这里

```tsx
// src/Root.tsx
import React from 'react';
import {Composition, Folder} from 'remotion';
import {ProductCard} from './ProductCard';
import {EpisodeIntro} from './EpisodeIntro';

export const Root: React.FC = () => {
  return (
    <>
      <Folder name="竖屏-商品">
        <Composition
          id="ProductCard"
          component={ProductCard}
          durationInFrames={150}
          fps={30}
          width={1080}
          height={1920}
          defaultProps={{title: '新品', price: '¥199'}}
        />
      </Folder>

      <Folder name="横屏-片头">
        <Composition
          id="EpisodeIntro"
          component={EpisodeIntro}
          durationInFrames={90}
          fps={25}
          width={1920}
          height={1080}
          defaultProps={{episode: 1, guest: '张三'}}
        />
      </Folder>
    </>
  );
};
```

**`id` 是渲染时的唯一抓手**，`npx remotion render` 后面跟的就是它。改名会同时打断所有 CI 脚本和批量任务，定下来就别动。

`<Folder>` 纯粹是给 Studio 侧边栏分类用的，不影响渲染。Composition 一多（几十个）就必须归类，否则侧边栏翻不动。

### 四个必填元数据

| 字段 | 含义 | 常见坑 |
|---|---|---|
| `durationInFrames` | 总帧数 | 它是**帧数不是秒**。要 5 秒 @ 30fps 就写 150 |
| `fps` | 帧率 | 改动会同时改变时长（帧数不变时）。国内投放常见 25/30，动画类常用 60 |
| `width` / `height` | 像素尺寸 | 竖屏 1080×1920，横屏 1920×1080，方屏 1080×1080 |

秒数换算很简单：`帧数 = 秒数 × fps`。给一个 `seconds()` 小工具能少犯错：

```ts
// src/lib/timing.ts
export const seconds = (s: number, fps: number) => Math.round(s * fps);
```

---

## 四、配置文件：把常用选项固化下来

`remotion.config.ts` 里的值会被所有渲染命令继承，CLI 上传同类参数时以 CLI 为准。

```ts
// remotion.config.ts
import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');   // 视频帧用 jpeg，比 png 快很多
Config.setJpegQuality(90);
Config.setCodec('h264');
Config.setCrf(18);                    // 画质优先。与 setVideoBitrate 不能同时设
Config.setConcurrency(4);             // 与机器内存匹配，不是越大越好
Config.setOverwriteOutput(true);
Config.setPixelFormat('yuv420p');     // 兼容性最好的像素格式
```

需要临时改就传 CLI 参数，不要为了试一次去改文件——改了容易忘记改回来，然后某天批量任务全用错参数。

---

## 五、一条完整的端到端命令流

```bash
# 1) 建项目并进目录
npx create-video@latest my-video
cd my-video && npm install

# 2) 起来看看
npm run dev                       # 或 npx remotion studio；默认 3000 端口
npx remotion compositions         # 打印所有 Composition 的 id / 时长 / 尺寸

# 3) 先渲染 3 帧，确认环境没问题（几十秒内出结果）
npx remotion render ProductCard out/probe.mp4 --frames=0-2 --log=verbose

# 4) 正式渲染
npx remotion render ProductCard out/product.mp4

# 5) 带外部数据渲染
npx remotion render ProductCard out/product-001.mp4 --props=./data/item-001.json

# 6) 出封面静帧
npx remotion still ProductCard out/cover.png --frame=45
```

### 渲染命令的标志位速查

| 标志 | 作用 | 默认 / 注意 |
|---|---|---|
| `--props` | 传入数据 | 必须是 JSON 文件路径或 JSON 字符串。**Windows 下必须用文件** |
| `--codec` | 编码格式 | `h264`（默认）、`h265`、`vp8`、`vp9`、`av1`、`prores`、`gif`、`mp3`、`aac`、`wav` 等 |
| `--crf` | 恒定质量 | 数值越小画质越好体积越大。与 `--video-bitrate` 互斥 |
| `--video-bitrate` | 目标码率 | 需要控制体积，或开了硬件加速时用 |
| `--concurrency` | 并行标签页数 | 默认约等于 CPU 线程数。内存是真正的天花板 |
| `--image-format` | 中间帧格式 | `jpeg`（默认，快）、`png`（无损，含透明通道）、`none` |
| `--jpeg-quality` | JPEG 质量 | 0–100，用 PNG 时不生效 |
| `--scale` | 缩放倍数 | 用 1.5 可以把 720p 工程输出成 1080p，矢量元素更清晰 |
| `--frames` | 只渲染部分帧 | `0-2` 是范围，`100-` 是从 100 到结尾，`0,30,60` 是挑帧 |
| `--sequence` | 输出图序列而非视频 | 输出目录给成文件夹；默认 JPEG |
| `--timeout` | 单帧最长等待 | 毫秒，默认 30000。数据请求慢时往上调 |
| `--pixel-format` | 像素格式 | `yuv420p` 兼容性最好 |
| `--log` | 日志级别 | `error` / `warn` / `info` / `verbose` |
| `--overwrite` | 覆盖已有文件 | 默认开启，用 `--overwrite=false` 关掉 |
| `--muted` | 静音输出 | 只用于视频 |
| `--enforce-audio-track` | 强制保留（静音）音轨 | 分片渲染后拼接时有用 |
| `--browser-executable` | 指定 Chrome 路径 | 内网或自定义安装位置时用 |
| `--chrome-mode` | 无头模式 | `headless-shell`（默认）/ `chrome-for-testing` |
| `--hardware-acceleration` | 硬件编码 | `disable`（默认）/ `if-possible` / `required` |
| `--x264-preset` | x264 预设 | 默认 `medium`；`veryfast` 明显更快 |
| `--gop` | 关键帧间隔 | 映射到 FFmpeg 的 `-g` |
| `--env-file` | 指定 dotenv 文件 | 默认读 `.env` |
| `--bundle-cache` | 打包缓存 | 默认开，调试打包问题时关掉 |

---

## 六、渲染失败排查路线

按发生频率从高到低排。

### 1. 输出一片黑 / 画面缺元素

**根因几乎总是资源没加载完就截图了。** 渲染器不会等你，它按帧号截图，慢的网络请求和字体加载会被直接跳过。

修法是显式告诉渲染器「等一下」：

```tsx
import {useEffect, useState} from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';

export const WithFont: React.FC = () => {
  const [handle] = useState(() => delayRender('加载字体'));

  useEffect(() => {
    const font = new FontFace('MyFont', `url(${staticFile('font.woff2')})`);
    font.load()
      .then((loaded) => {
        document.fonts.add(loaded);
        continueRender(handle);          // 必须被调用，否则 30 秒后超时
      })
      .catch((err) => {
        // 失败也要放行，否则整条渲染卡死
        console.error('字体加载失败', err);
        continueRender(handle);
      });
  }, [handle]);

  return <div style={{fontFamily: 'MyFont'}}>字体加载完成前不会截图</div>;
};
```

同一套机制适用于：远程图片、音视频元数据、远程数据、任何异步准备。

**必须成对出现**：每一个 `delayRender()` 都要有一条 `continueRender(handle)` 的路径，包括失败分支。漏了就是 30 秒超时 + 报出卡住的帧号。

### 2. 报「Timeout / A frame took too long」

- 看错误里报的帧号，定位到那一帧在等什么。
- 数据接口慢就加 `--timeout=60000`，但更好的做法是加请求超时并在超时后 `continueRender()` 放行。
- 偶尔是死循环：检查组件里有没有在渲染期间 `setState` 又依赖帧号的写法。

### 3. 字体渲染出来跟预览不一样

除了上面的 `delayRender()`，还要注意：**渲染机器上必须能访问到字体文件**。用 Google Fonts 这类远程字体时，内网渲染机会静默回退到系统字体。生产环境一律把字体文件放进 `public/`。

### 4. 图片/视频不显示，控制台报 CORS

无头浏览器对跨域资源的限制和普通浏览器一样。两个解法：

- 把素材下载到 `public/`，用 `staticFile('xxx.png')` 引用（推荐，还能顺带解决加载速度问题）。
- 让素材服务器返回正确的 `Access-Control-Allow-Origin`。

### 5. 卡在打包/启动，或报 download 相关错误

首次使用要下载一份无头浏览器。内网或代理环境下会失败：

```bash
# 指定已有 Chrome
npx remotion render ProductCard out/x.mp4 --browser-executable="/path/to/chrome"

# 或把浏览器拉取地址指向内网镜像（视你的网络环境而定）
```

### 6. 崩在 `Target closed` / 进程被 kill

**这是并发超配的典型症状**，不是代码 bug。每个并发单元都要占一份浏览器标签页内存，标签页被系统 OOM 杀掉就报这个。

处理顺序：先把 `--concurrency` 减半试，再考虑降 `--image-format` 到 `jpeg`、关掉 `--disallow-parallel-encoding`（如果开了）、或者升级内存。

经验值：1080p 竖屏工程，8 核 16G 机器上 `--concurrency=4` 是比较稳的起点。

### 7. 渲染很慢

按收益排序：

1. `--image-format=jpeg`（默认已是，确认没被改成 png）。PNG 无损但慢得多。
2. 降 `--x264-preset` 到 `veryfast`。画质损失通常肉眼不可见，速度提升明显。
3. 用 `--scale` 渲染小尺寸再放大，或直接按目标尺寸建工程，别做过采样。
4. 减少每帧的计算量：把昂贵的计算提到组件外，或用 `useMemo`。
5. 开硬件加速 `--hardware-acceleration=if-possible`（注意此时不能用 `--crf`）。
6. 真到瓶颈了再上多机分布式渲染（见 `references/batch-and-deploy.md`）。

### 8. Windows 上 `--props` 传不进去

```powershell
# 错：PowerShell 会吃掉双引号，收到的是坏 JSON
npx remotion render ProductCard out/x.mp4 --props='{"title":"A"}'

# 对：写文件
'{"title":"A","price":"¥199"}' | Set-Content -Encoding UTF8 .\data\item-001.json
npx remotion render ProductCard out/x.mp4 --props=./data/item-001.json
```

注意 `Set-Content -Encoding UTF8`。中文内容用错编码会变成乱码，而且报错信息不会提示这一点。

---

## 七、上手当天该做的四件事

1. `npx remotion compositions` 看一遍输出，确认 Composition 的 id、时长、尺寸全都符合预期。时长写错是最高频的低级错误。
2. 用 `--frames=0-2` 渲染三帧，而不是直接渲染整片。
3. 把 `out/` 和 `node_modules/` 加进 `.gitignore`，别把成片提交进仓库。
4. 确认许可档位（见 `SKILL.md`），尤其是团队人数已经超过 3 人的情况。
