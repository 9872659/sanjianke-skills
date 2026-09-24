# 三剪客 · 桌面划词翻译与文本润色 Skill

划词即译的跨平台桌面翻译与浏览器插件：翻译 / 润色 / 总结三模式、截图翻译、生词本。

---

## 前置条件

- 一台 Windows / macOS / Linux 桌面环境；macOS 需在「辅助功能」中授权，截图翻译另需屏幕录制权限
- 一个可用的模型服务与凭证：OpenAI API Key、Azure OpenAI Service 的端点与 Key，或其它 OpenAI 兼容入口
- 走浏览器插件路线时：Chrome 或 Firefox 的较新版本
- 走源码构建路线时：Node.js、`pnpm@9.1.3`（仓库锁定版本）、Rust 工具链
- 能访问所选服务商的接口域名（必要时自备代理或网关）

---

## 使用

1. 按平台安装桌面端或浏览器插件，安装包与产物文件以 Release 页面为准。
2. 打开设置，选服务商并填入 API Key。Azure OpenAI Service 按三段式拼装：

   ```text
   https://{resourceName}.openai.azure.com
   /openai/deployments/{deployName}/chat/completions?api-version={apiVersion}
   ```

3. 绑定划词翻译快捷键，在任意软件中选中文本按快捷键取译文。
4. 按需要切换「翻译 / 润色 / 总结」；按截图翻译快捷键框选屏幕区域做识图翻译。
5. 查过的词进生词本，之后可基于生词本生成帮助记忆的内容。
6. macOS 用 PopClip、Windows 用 SnipDo 的扩展实现更顺手的划词入口（Release 页可下载对应扩展文件）。

完整步骤、常见故障与权限说明见 `SKILL.md`。

---

## 依赖

- 上游产品本体（自带的只是外壳与交互，模型能力来自你配置的服务商）
- 一个 OpenAI 兼容或 Azure OpenAI 形态的接口入口与有效凭证
- 桌面端外壳：Tauri（源码构建时需要 Rust 工具链）
- 浏览器插件构建：Vite（源码构建时需要 Node.js 与 pnpm）
- 系统授权：辅助功能 / 无障碍、剪贴板、屏幕截图（按平台与功能分别授予）

---

## 安全

- 不内嵌任何密钥：API Key 由使用者在本地设置中填写，本包不含任何凭证
- 文本与截图会发往你配置的服务商，涉密内容请先脱敏或改接内网 / 本地兼容端点
- 桌面端需要常驻后台与全局快捷键，会注册系统级快捷键并读取其他应用中的选中文本
- 密钥保存在本机配置里，共享电脑上使用前请注意配置文件的可见范围
- 依赖清单中含分析类与错误上报类组件，介意的话在设置或系统层面确认后再长期使用
- 上游为社区开源项目，本项目不为其提供任何担保与技术支持

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`nextai-translator`
- 仓库：https://github.com/nextai-translator/nextai-translator

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
