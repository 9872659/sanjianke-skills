# 三剪客 · 电子书管理与转换 Skill

calibre：电子书管理与转换 的安装、常用命令与避坑要点

---

## 前置条件

- 一台能装官方安装包的机器（Linux / macOS 14.0+ / Windows 10 1809+），或 Windows 便携版。
- Linux 官方安装脚本要求 `xdg-utils`、`wget`、`xz-utils`、Python。
- 服务器上要跑命令行工具时，需补齐 Qt 依赖的 X 相关库。
- 源文件**不含 DRM**；否则工具从设计上就不会打开它。

---

## 使用

主体是 `SKILL.md`，建议按顺序读：

1. **什么时候用 / 不用** —— 先分清「格式转换」「书库管理」「精修」三件事，以及 DRM 与 PDF 输入这两个硬边界。
2. **安装** —— Linux 官方脚本与参数、macOS/Windows 安装包形态、命令行工具的完整路径、常用环境变量。
3. **常用操作** —— 转换、转 Kindle、带元数据转换、读写元数据、精修、书库增删导出、内容服务器、补元数据、调试、脚本批量。
4. **常见坑** —— DRM、发行版包、无头服务器的 Qt 缺失、PDF 输入、输出名缺扩展名、Kindle 目录与邮件投递、GPLv3。

最短的两次调用：

```bash
ebook-convert book.epub book.mobi --output-profile kindle
calibredb add --with-library /path/to/library book.epub
```

---

## 依赖

- Linux：官方安装脚本会自动带上运行时；GLIBC 与 libstdc++ 需达到官方要求。
- 服务器无头环境：按报错补装 `libxcb-cursor0`、`libxcb-xinerama0`、`libegl1`、`libopengl0` 等。
- 补元数据依赖在线数据源。
- 不需要账号或 Key；连接远程内容服务器时才需要用户名与密码。

---

## 安全

- 不内嵌任何密钥、Token 或 Cookie。
- 不处理 DRM：不提供、也不协助任何绕过 DRM 的做法。
- 会读写用户指定的书库目录；原地修改类操作（精修不指定输出、改元数据）前务必先备份。
- 内容服务器对外提供服务时，注意开启鉴权与必要的 SSL 配置，不要裸露在公网。
- 本体为 GPLv3：用于商业产品前先做许可证评估。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`calibre`
- 仓库：https://github.com/kovidgoyal/calibre

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
