---
name: sanjianke-apache-echarts
slug: sanjianke-apache-echarts
displayName: 三剪客 · 数据可视化图表库
description: "Apache ECharts：数据可视化图表库 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Apache ECharts：数据可视化图表库 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 数据分析
  - 数据可视化

---

# 三剪客 · 数据可视化图表库

页面里要把一组数据画成能交互的图——折线、柱状、饼图、地图、关系图——不想从零写 Canvas 和坐标轴。它一个 JS 文件搞定：给一个配置对象，它负责渲染、缩放、悬浮提示、图例切换和动画。适合放进前端项目、报表页面，或者后端渲染成图片。

**上游项目**：`Apache ECharts`　**仓库**：https://github.com/apache/echarts

## 什么时候用 / 不用

**用它**：

- 用户要在网页里展示趋势、占比、分布、排名这类常规业务图表，希望有悬浮提示和图例交互。
- 需要的数据量大或图形复杂，普通图表库卡顿——它内置增量渲染与大数据量优化。
- 图表类型不常见：桑基图、主题河流、旭日图、关系图、日历图、矩阵图、平行坐标等。
- 要渲染成图片或做服务端渲染（SSR），给报告、海报、邮件用。
- 页面用的是 Vue / React 等框架，需要官方或社区现成的组件封装。
- 需要一个体积可控的按需引入版本，只打包用到的那几种图。

**不要用它**：

- 只是要在终端或日志里粗略看个数字，画图纯属多余。
- 需要的是统计建模与假设检验，那是数据分析库的活，它只负责把结果画出来。
- 要的是现成的整套 BI 平台（连库、权限、看板管理），它只是一个前端图表库，没有后端。
- 项目是静态图片报表且完全不涉及浏览器——虽然有 SSR 能力，但要额外配置，成本未必划算。
- 要的是 3D 地球、体绘制这类重图形场景，需要额外装 GL 扩展包，不是开箱即得。
- 团队已经重度依赖另一套图表体系且迁移成本高时，没必要为了单一图表引入第二套。

## 安装

**npm / pnpm / yarn**：

```bash
npm install echarts --save
```

**CDN（浏览器直接用，无需构建）**：

```html
<script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
```

官方给出的获取方式还有"从官网下载页下载"这一条；npm 包名就是 `echarts`，当前仓库 `package.json` 里的版本为 `6.1.0`（以安装到的实际版本为准）。

**从源码构建（改源码或调试用，需要 Node.js）**：

```bash
npm install          # 安装依赖
npm run dev          # watch 模式重建，并起测试页面
npm run checktype    # TypeScript 类型检查
npm run release      # 产出全部发布文件到 dist/
```

## 常用操作

**1. 最小可跑示例（浏览器）**

```html
<div id="chart" style="width: 600px; height: 400px;"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
<script>
  var chart = echarts.init(document.getElementById('chart'));
  chart.setOption({
    xAxis: { type: 'category', data: ['一月', '二月', '三月'] },
    yAxis: { type: 'value' },
    series: [{ type: 'line', data: [120, 200, 150] }]
  });
</script>
```

**2. 模块化项目里引入并渲染**

```js
import * as echarts from 'echarts';

const chart = echarts.init(document.getElementById('chart'));
chart.setOption({ /* 同上 */ });
```

**3. 换渲染器（默认 canvas，可切 SVG）**

```js
const chart = echarts.init(document.getElementById('chart'), null, {
  renderer: 'svg',
  width: 600,
  height: 400
});
```

`renderer` 只接受 `'canvas'` 或 `'svg'`；`init` 第三个参数还支持 `devicePixelRatio`、`locale`、`ssr` 等，具体字段以 `EChartsInitOpts` 类型定义和官方 API 文档为准。

**4. 容器尺寸变化时重绘**

```js
window.addEventListener('resize', () => { chart.resize(); });
// 也可以指定新尺寸
chart.resize({ width: 800, height: 500 });
```

**5. 复用实例更新数据**

```js
chart.setOption({ series: [{ data: [300, 120, 90] }] });          // 默认合并
chart.setOption(newOption, { notMerge: true });                    // 完全替换
chart.setOption(newOption, { lazyUpdate: true });                  // 下一帧再更新
```

`setOption` 第二个参数的完整可选项包括 `notMerge`、`lazyUpdate`、`silent`、`replaceMerge`、`transition`。

**6. 按需引入（减小打包体积）**

```js
import * as echarts from 'echarts/core';
import { LineChart, BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);
```

包内还暴露 `echarts/charts`、`echarts/components`、`echarts/features`、`echarts/renderers` 以及各图表的 `lib/chart/*` 入口；用错入口会得到"组件未注册"类的报错。

**7. 用完释放**

```js
chart.dispose();
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 图表不显示，控制台也没报错 | 容器 div 没有高度。DOM 元素默认高度由内容撑开，而图表容器里没有内容 | 给容器显式设高，例如 `style="width:600px;height:400px"`，或用 CSS 类固定尺寸 |
| 切换标签页 / 折叠面板回来图表变小或错位 | 隐藏时容器尺寸为 0，`init` 时取的尺寸就是错的 | 容器可见后再调 `chart.resize()`，或容器尺寸变化时主动 `resize` |
| 组件不生效，比如图例、提示框、网格线全没出来 | 用了按需引入却漏注册对应组件 | 把用到的 `*Component` 和 `*Chart`、`*Renderer` 都加进 `echarts.use([...])` |
| 同一个容器反复 `init`，报"已有实例"或图表残影 | 同一个 DOM 上重复初始化，旧实例没销毁 | 先 `echarts.getInstanceByDom(el)` 判断，或对旧实例 `dispose()` 再初始化；框架里把实例存在 ref 上并在卸载时 dispose |
| 数据变了画面没变 | 只改了原数据数组，没有重新 `setOption`；或用了 `lazyUpdate` 而渲染时机还没到 | 改完数据调一次 `setOption`；注意 `lazyUpdate` 会把更新推迟到下一帧 |
| `notMerge` 用错导致配置被清空 | 默认是合并，写 `notMerge: true` 是整体替换，没在新 option 里带的项会消失 | 只改局部就用默认合并；确实要整体换再开 `notMerge`，或改用 `replaceMerge` 精确指定 |
| 服务端渲染出图空白 | 没走 SSR 专用入口与 `ssr: true` 初始化 | 用包里的 SSR 客户端入口（`echarts/ssr/client`）配合 `init` 的 `ssr` 选项，具体流程以官方文档为准 |
| 引了两个 echarts 副本导致互相干扰 | 依赖树里存在多个版本 | 用包管理器的去重/提升能力统一版本，或配别名指向同一份 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 仅安装时 | 从 npm 或 CDN 拉取库文件；图表渲染本身不需要联网 |
| 读取文件 | 否 | 纯前端库，运行时不需要读本地文件 |
| 写入文件 | 否 | 除 `npm run release` 产出 `dist/` 外不写文件；导出图片由浏览器下载行为完成 |
| 凭证 | 否 | 库本身不需要任何 Key 或账号 |
| 子进程 / 后台常驻 | 否 | 浏览器内运行；只有改源码构建时才跑构建进程 |

## 触发场景

- "帮我用 echarts 画一个折线图 / 柱状图 / 饼图"
- "echarts 图表显示不出来，容器里是空的"
- "怎么让 echarts 跟着窗口大小自适应"
- "echarts 按需引入该怎么写"
- "用 echarts 做个能缩放的大数据量折线图"
- "echarts 怎么导出成图片"

## 能力边界

**覆盖**：

- 常规统计图表与大量专业图表类型（折线、柱状、饼、散点、K 线、雷达、漏斗、桑基、树图、旭日、主题河流、日历、矩阵、平行坐标、关系图等）
- Canvas 与 SVG 两种渲染器
- 大数据量下的增量渲染、渐进渲染与脏矩形等性能手段
- 数据集与数据转换（`dataset` / `transform`）、视觉映射（`visualMap`）、区域缩放（`dataZoom`）
- 服务端渲染出图能力
- 主题与国际化资源（`theme/*`、`i18n/*`）
- 通过 `echarts.use` 注册的按需打包与自定义系列扩展

**不覆盖**：

- 不提供后端服务、数据库连接、看板权限管理，它不是 BI 平台
- 不做数据统计与建模，只负责把给定数据画出来
- 不做地图数据的采集与合规处理，使用地图底图需自行确认资质与来源
- 3D / WebGL 图形需另装扩展包，不在核心包里
- 不提供具体业务图表的成品页面，业务封装要自己写
- 不替代前端框架，页面结构与状态管理仍归框架负责

## 依赖条件

- 浏览器环境；SSR 场景需要 Node.js
- 运行时依赖 `zrender`（随 npm 包自动安装，版本与主包同步）
- 从源码构建需要 Node.js 与 npm
- 按需引入需要支持 ESM 的打包器（Vite / webpack 等）

## 已知限制

- 默认渲染器是 canvas；容器必须有确定尺寸，否则渲染区域为 0
- 核心包不含 3D、水球图、字符云等扩展，需单独安装对应扩展包
- 地图类图表的底图数据来源与使用许可需自行核实
- 大数据量性能与浏览器、硬件、图形复杂度强相关，没有通用的"一定能跑到多少万点"结论
- 版本之间存在 API 与默认行为差异，跨大版本升级需查官方升级说明
- 本包不包含该库源码，构建与调试细节以上游仓库为准

## 自检清单

- 执行前：确认容器元素已有确定宽高；确认引入方式（CDN / npm）与项目构建体系匹配
- 执行前：确认用到的图表类型、组件、渲染器都已注册（按需引入时尤其重要）
- 执行后：图表正常渲染；缩放窗口或容器尺寸变化后画面正确
- 执行后：组件卸载时调用了 `dispose()`，没有实例泄漏
- 执行后：如果做了按需引入，验证打包产物里确实没打进未使用的图表类型

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/apache/echarts | 上游仓库（安装与完整文档以它为准） |

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
