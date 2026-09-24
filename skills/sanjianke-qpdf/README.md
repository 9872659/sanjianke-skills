# 三剪客 · PDF 无损变换 Skill

qpdf：PDF 结构级无损变换的安装、常用命令与避坑要点。
合并、拆分、旋转、加密解密、线性化、压体积、结构体检——全部离线，全部不重新渲染内容。

---

## 前置条件

- 能装命令行工具的 Linux / macOS / Windows 环境。
- 待处理的 PDF 是本地文件、可读且可 seek（不支持从标准输入读 PDF）。
- 若涉及加密或解密，需知道对应密码。

---

## 使用

1. 安装：发行版包管理器（`apt-get install qpdf` / `dnf install qpdf` / `pacman -S qpdf` / `brew install qpdf`），
   或从 GitHub Releases 取 Windows 二进制包并加入 `PATH`。
2. `qpdf --version` 确认可用，`qpdf --help` 看选项总览。
3. 在 Agent 会话里说明目标（合并 / 抽页 / 加密 / 压体积 / 体检）并给出文件路径，
   具体命令套路见 `SKILL.md` 的「常用操作」六段示例。
4. 检查类选项（`--check`、`--show-npages`、`--json`）不产生输出文件，别和输出路径写在一起。

---

## 依赖

- 运行时：无需额外依赖，qpdf 自带 zlib / libjpeg 能力（部分发行版会拆出 `libqpdf` 共享库包）。
- 源码构建：C++-20 编译器、CMake 3.16+、zlib、libjpeg；可选 GnuTLS / OpenSSL。
- 不需要任何账号或 API Key。

---

## 安全

- 不内嵌任何密钥
- 运行时完全离线，无网络请求
- 密码优先用 `--password-file` 或 `@参数文件` 传入，避免出现在命令行历史与进程列表
- 涉及有损操作（`--optimize-images`）或原地覆盖（`--replace-input`）前先备份原文件
- 不提供绕过密码的能力：加密文件必须提供正确密码

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`qpdf`
- 仓库：https://github.com/qpdf/qpdf

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
