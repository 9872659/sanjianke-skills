# 三剪客 · 在线 PPT 编辑器 Skill

PPTist：在线 PPT 编辑器 的安装、常用命令与避坑要点

---

## 前置条件

- **Node.js ≥ 20**
- 一个包管理器（官方脚本按 npm 写，换 pnpm / yarn 也行）
- 这是**源码级二次开发底座**，不是开箱即用的工具，也不做成 npm 包
- 默认没有后端：不保存数据、无账号、无协作；持久化要自己接
- 许可证 **AGPL-3.0**：闭源商用与网络服务都受约束，商用前先定路线

---

## 使用

```bash
git clone https://github.com/pipipi-pikachu/PPTist.git
cd PPTist

npm install
npm run dev
# 浏览器访问 http://127.0.0.1:5173/
```

构建与检查：

```bash
npm run build        # 类型检查 + 生产构建
npm run type-check   # vue-tsc
npm run preview      # 预览构建产物
npm run lint         # eslint 检查并修复
```

接后端时改 `src/store/slides.ts`（Pinia store），需要持久化的字段：
`title`、`slides`、`theme`、`viewportSize`、`viewportRatio`、`templates`。

完整的「什么时候用 / 不用、安装、常用操作、常见坑、能力边界」见 `SKILL.md`。

---

## 依赖

| 依赖 | 是否必须 | 用途 |
|---|---|---|
| Node.js ≥ 20 | 必须 | 运行与构建环境 |
| Vue 3.5 + TypeScript ~5.3 | 必须 | 前端框架与类型 |
| Vite 5 | 必须 | 开发服务器与构建 |
| Pinia 3 | 必须 | 状态管理（幻灯片数据在 `store/slides.ts`） |
| Sass | 必须 | 样式 |
| pptxtojson | 必须 | 导入 PPTX |
| pptxgenjs | 必须 | 导出 PPTX |
| echarts | 必须 | 图表元素 |
| ProseMirror 系列 | 必须 | 富文本编辑 |
| dexie | 必须 | 浏览器本地存储 |
| 后端服务 | 按需 | 项目自身不提供，持久化与账号要自行实现 |

---

## 安全

- 不内嵌任何密钥
- 幻灯片数据默认只在浏览器内存 / 本地存储中，**刷新即丢**，不要当正式存储用
- 本地图片默认走 Base64 内联，会导致数据体积与卡顿；生产环境要改成上传 + URL 引用
- 导入 JSON 的入口**不要直接暴露给终端用户**（官方建议在服务端实现并做好数据校验）
- 接入 AI 能力时，Key 必须放服务端，不能写进前端代码或构建产物
- AGPL-3.0：对外提供网络服务同样触发开源义务，商用前务必确认合规路线

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`PPTist`
- 仓库：https://github.com/pipipi-pikachu/PPTist

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
