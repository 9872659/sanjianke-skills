# 三剪客 · 数据可视化图表库 Skill

Apache ECharts：数据可视化图表库 的安装、常用命令与避坑要点

---

## 前置条件

- 一个网页环境（或支持 ESM 的打包工程）；服务端渲染出图需要 Node.js
- 一个已有确定宽高的容器元素——图表画在它的尺寸里
- npm 项目需能访问 npm 源；用 CDN 则需浏览器能访问对应 CDN
- 想按需引入时，打包器要支持 ESM 与 tree-shaking
- 如果要改源码或本地调试，另需 Node.js 与 npm

---

## 使用

1. 安装：`npm install echarts --save`，或在 HTML 里用 CDN 引入 `echarts.min.js`。
2. 准备一个带固定宽高的容器 `div`。
3. `echarts.init(容器)` 拿到实例，必要时在第三个参数里指定 `renderer`、`width`、`height` 等。
4. 构造 option 调 `chart.setOption(...)` 渲染；数据更新时再调一次 `setOption` 即可复用实例。
5. 容器尺寸变化时调 `chart.resize()`；组件卸载或页面销毁时调 `chart.dispose()`。
6. 体积敏感的项目改用 `echarts/core` + `echarts.use([...])` 按需注册。
7. 具体 option 字段非常多，以官方配置项文档与示例为准；本 Skill 只覆盖装、用、避坑的主干。

---

## 依赖

- 运行时依赖 `zrender`，随 npm 包一起安装，版本与主包保持同步
- 按需引入依赖 ESM 打包器（Vite / webpack / Rollup 等）
- 从源码构建依赖 Node.js、npm，以及仓库 devDependencies 里的构建工具链
- 3D、水球图、字符云、地图扩展等属于独立扩展包，需要单独引入

---

## 安全

- 不内嵌任何密钥
- 库本身不发起网络请求，图表数据完全由调用方提供，注意不要把敏感数据渲染到公开分享的页面上
- 渲染用户可控的文本标签时做好转义，避免把不可信内容当 HTML 插入
- 使用 CDN 引入时建议锁定版本，避免上游被替换带来的供应链风险
- 使用地图类图表前，确认底图数据的来源与使用授权
- 本包不包含该库源码，也不内置任何构建产物，依赖一律从官方渠道获取

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Apache ECharts`
- 仓库：https://github.com/apache/echarts

---

## 许可证

MIT，见 `LICENSE.md`。

---

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
