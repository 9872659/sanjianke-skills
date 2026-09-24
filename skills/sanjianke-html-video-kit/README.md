# 三剪客 · HTML 转视频引擎 Skill

把 HTML/CSS 当时间轴写，一条命令渲染出确定性 MP4。

---

## 前置条件

- Node.js **22 及以上**（低版本直接跑不起来）。
- FFmpeg 与 ffprobe 在 PATH 中。
- 一个空目录作为工程根；首次运行需要联网拉取 `hyperframes` 包与固定版本的 Chrome。
- 需要跨机器逐字节一致时，另外准备可用的 Docker。

先体检再动手：

```bash
npx hyperframes doctor          # 人看
npx hyperframes doctor --json   # 机器看：恒定退出 0，要判 payload 里的 ok
npx hyperframes browser ensure  # 缺 Chrome 时补上
```

---

## 使用

三步走，最小可用路径：

```bash
npx hyperframes init my-video
cd my-video
npx hyperframes preview --background --port 3017   # 浏览器里实时预览 + 时间轴编辑
npx hyperframes lint                               # 边写边查
npx hyperframes check                              # 最终质量关卡
npx hyperframes render --quality high --output out.mp4
```

把文案抽成变量之后，一套模板可以批量出片：

```bash
npx hyperframes render --batch rows.json --output "renders/{name}.mp4" --strict-variables
```

三条约定记住就不会踩大坑：

1. 动画只能由时间值推导，禁止时钟、随机数与渲染期网络请求。
2. 每个 `<video>` / `<audio>` 都要有 `id`，都不要写 `crossorigin`。
3. 根上的 `data-duration` 是编译期常量；要变长度就改根元素本身。

详细步骤、`data-*` 属性全表与批量出片排错，看 `SKILL.md` 的「工作流路由」。

---

## 依赖

| 依赖 | 必需性 | 说明 |
|---|---|---|
| Node.js 22+ | 必需 | CLI 与渲染管线的运行时 |
| FFmpeg / ffprobe | 必需 | 帧编码与成片校验 |
| 固定版本 Chrome | 必需 | `browser ensure` 自动获取；锁版本是为了像素输出可复现 |
| Docker | 可选 | 仅 `render --docker` 的可复现渲染路径需要 |
| 网络 | 首次必需 | 拉包、安装 registry 条目；合成里引用的外部 CDN 脚本也在渲染时联网获取 |

---

## 安全

- 不内嵌任何密钥、Token 或账号。
- 本地渲染不需要任何凭据；`publish` 与 `cloud` 走 OAuth，令牌由 CLI 自行保管在用户目录，本 Skill 不读取、不转存。
- 不代理转发用户请求，不经手用户数据。
- 渲染会真实启动子进程（无头 Chrome + FFmpeg），并可能后台常驻一个 Studio 服务；用完请显式收掉：`npx hyperframes preview --stop`。
- 合成里引用的外部脚本与素材会在渲染时被拉取，涉及内网或敏感工程时请先本地化依赖。
- 批量渲染用的 `rows.json` / `--variables-file` 可能含业务敏感字段，请自行控制文件范围与权限。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：Hyperframes

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
