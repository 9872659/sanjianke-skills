# 三剪客 · 用 React 写代码生成视频 Skill

用 React 组件描述画面、用帧号驱动动画，再用命令行把结果渲染成 MP4 / WebM / GIF / 图片序列。同一套代码既能本地预览，也能改参数批量出片。

---

## 前置条件

- **Node.js**：必须。具体版本下限以官方文档当前说明为准。
- **包管理器**：npm / Yarn / pnpm / Bun 任选其一。
- **无头浏览器**：不需要你手动装。本机没有兼容的 Chrome 时，Remotion 会自行下载一份 Chrome Headless Shell；本机已有 Chrome 时会优先复用，也可以用 `--browser-executable` 显式指定路径。
- **FFmpeg**：不需要你手动装。Remotion 自带一份平台相关的 FFmpeg / FFprobe 二进制。
- **许可证**：这是使用前必须先确认的一件事。个人与 3 人以内组织可在官方条款下免费使用；4 人及以上组织需要公司许可证，自动化批量渲染按次计费。商用前请自行核对官方 License & Pricing 页面。

---

## 使用

1. 建项目：

   ```bash
   npx create-video --yes --blank my-video
   ```

2. 进目录起预览界面，改动画：

   ```bash
   npx remotion studio
   ```

3. 确认 composition 的 ID：

   ```bash
   npx remotion compositions
   ```

4. 渲染成片：

   ```bash
   npx remotion render <composition-id> out/video.mp4
   ```

5. 批量出片：把可变内容做成 props，循环调用渲染命令或渲染 API，每次换一份 props 文件。

```bash
npx remotion render Ad out/a.mp4 --props=./props-a.json
```

Windows 下不要把内联 JSON 直接写在 `--props` 后面，双引号会被 shell 吃掉；统一落成 `.json` 文件最稳。

六块正文（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

- **运行时**：Node.js。
- **npm 包**：`remotion`、`@remotion/cli`，以及按需安装的其它 `@remotion/*` 扩展包。所有 Remotion 官方包**必须同版本**，用 `npx remotion versions` 校验、`npx remotion upgrade` 统一升级。
- **浏览器**：Remotion 管理的 Chrome Headless Shell，或本机已安装的 Chrome / Chromium。
- **编码器**：随包分发的 FFmpeg 二进制。
- **硬件**：渲染耗时与总帧数成正比，分辨率越高、并发越高，对 CPU、内存和磁盘的要求越高。要用硬件编码需要显卡支持，对应 `--hardware-acceleration` 参数。
- **可选云服务**：使用 Lambda 或 Cloud Run 分布式渲染时，需要相应云账号、权限与存储桶。

---

## 安全

- 不内嵌任何密钥。本包只有文字说明，不含任何账号、Token 或证书。
- 渲染过程会启动本地无头浏览器并访问组件里引用的远程资源（字体、图片、接口）。在隔离环境里跑渲染前，先确认组件不会访问内网地址或携带凭证。
- `--disable-web-security` 与 `--ignore-certificate-errors` 会关闭 CORS 与证书校验，仅在明确知道后果时临时使用，不要放进常规构建流程。
- 渲染产物与 bundle 会写到工程目录，注意别把构建缓存目录提交进版本库或打进发布包。
- 涉及商用前，务必先确认许可证档位；这是合规要求，与代码质量无关。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Remotion`
- 仓库：https://github.com/remotion-dev/remotion
- 官方文档：https://www.remotion.dev/docs/
- 官方 CLI 参考：https://www.remotion.dev/docs/cli/

---

## 许可证

MIT，见 `LICENSE.md`。

> 注意区分：本 Skill 包的许可是 MIT；上游项目 Remotion 自身另有商业许可证条款，两者不是一回事。上游的使用许可请以 https://www.remotion.dev/docs/license/pricing 为准。

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
