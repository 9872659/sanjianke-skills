# 三剪客 · 代码化视频生成 Skill

用 React 组件写视频，参数化批量出片

---

## 前置条件

- **Node.js 18+**（建议 LTS 20/22），npm 或 pnpm 任一。
- **Chrome / Chromium**：渲染时由 Remotion 驱动无头浏览器逐帧截图。系统里没有会尝试自动下载，内网环境需预先指定可执行文件路径。
- **FFmpeg**：Remotion 自带，不要再单独装一份去干扰 PATH。
- **磁盘**：默认渲染是流式的，不落全量帧；用 `--sequence` 出 PNG 序列时才需要按「帧数 × 单帧体积」预留空间。
- **许可确认（重要）**：Remotion 是 source-available 商业许可，**不是开源软件**。个人、3 人及以下团队、非营利组织可免费用于商业场景；4 人及以上公司需要 Company License。动手前请先判定自己落在哪一档。

---

## 使用

1. 先读 `SKILL.md`，确认许可档位与「能力边界」。
2. 按 `SKILL.md` 的「快速开始」建项目，用 `--frames=0-2` 渲染几帧验通链路。
3. 按需进入 references：

| 你卡在哪一步 | 看哪份 |
|---|---|
| 建项目、注册 Composition、渲染出第一个 MP4、渲染报错 | `references/quickstart.md` |
| 写动画、控制图层时间、加字幕音视频、接数据 | `references/animation-api.md` |
| 批量出一千条、并发调优、出图序列、上云与定时任务 | `references/batch-and-deploy.md` |

核心命令速查：

```bash
npx create-video@latest my-video   # 建项目
npm run dev                        # 起 Studio 预览
npx remotion compositions          # 列出所有 Composition
npx remotion render <id> out/x.mp4 # 渲染成片
npx remotion still <id> out/x.png --frame=30   # 出静帧
```

---

## 依赖

| 类别 | 要求 |
|---|---|
| 运行时 | Node.js 18+；无头 Chrome/Chromium；FFmpeg（由 Remotion 分发） |
| 包 | `remotion`、`@remotion/cli`、`@remotion/bundler`、`@remotion/renderer`，`zod`（参数校验与控件生成） |
| 可选包 | `@remotion/lambda`、`@remotion/cloudrun`（云渲染）、`@remotion/player`（页面内嵌播放）、`@remotion/transitions`、`@remotion/captions`、`@remotion/media-utils` |
| 可选云资源 | AWS 账号 + S3 桶（走 Lambda）；GCP 项目 + Artifact Registry（走 Cloud Run） |
| 网络 | 首次安装依赖与下载浏览器需要能出网 |

---

## 安全

- 不内嵌任何密钥
- 云渲染的云厂商凭证、公司许可的 `licenseKey` 一律走环境变量或 CI Secret，不写进源码、不写进提交记录
- 本 Skill 不代理任何请求、不中转数据、不代收费用
- 渲染产物与中间帧序列的存储位置和访问权限由使用者自己控制，涉及未公开素材时先确认落地目录不在公开可访问路径下
- 许可与 telemetry 义务已在上游条款中定义，本 Skill 只做事实转述，不构成法律意见

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：Remotion

---

## 许可证

MIT，见 `LICENSE.md`。

> 注意区分两个「许可证」：本 Skill 文档本身是 MIT；被介绍的 Remotion 是独立的商业许可软件，两者互不相干。Remotion 的授权条款见 https://github.com/remotion-dev/remotion 仓库根目录的 `LICENSE.md`。

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
