# 三剪客 · JS 创建修改 PDF Skill

pdf-lib：JS 创建修改 PDF 的安装、常用命令与避坑要点

---

## 前置条件

- 有 Node.js 环境（或目标运行时是浏览器 / Deno / React Native）。
- 项目里已安装 `pdf-lib`（`npm install --save pdf-lib`）。
- 需要中文等非拉丁文字时，额外安装 `@pdf-lib/fontkit` 并自备字体文件。

---

## 使用

把本目录作为 Skill 交给 Agent，Agent 会按 `SKILL.md` 里的示例代码组织生成/修改 PDF 的脚本。
常见任务：

- 从零生成带中文的 PDF；
- 在既有 PDF 上叠加文字或图片；
- 跨文档拷贝页面并重排；
- 按字段名填写并压平表单。

---

## 依赖

- `pdf-lib`（npm / yarn 安装，或用 UMD 构建）。
- 选装：`@pdf-lib/fontkit`（嵌入自定义字体）。
- 无原生扩展、无外部二进制、无 JVM。

---

## 安全

- 不内嵌任何密钥
- 不支持加密文档，也不提供解密；遇到加密文件请先用有权限的工具处理。
- 处理含个人信息的 PDF 时注意落盘位置与清理策略。
- 只为你有权处理的文档做修改、盖戳或表单填充。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pdf-lib`
- 仓库：https://github.com/Hopding/pdf-lib

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
