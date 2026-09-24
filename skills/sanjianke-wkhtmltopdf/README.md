# 三剪客 · HTML 转 PDF Skill

wkhtmltopdf：HTML 转 PDF 的安装、常用命令与避坑要点

---

## 前置条件

- 安装对应平台的官方包（Windows installer/7z、macOS pkg、Linux 的 deb/rpm/pkg.tar.xz），
  或使用发行版仓库里的版本
- 想用页眉页脚、目录、大纲：必须是**打了 Qt 补丁**的构建，
  用 `wkhtmltopdf --version` 确认输出里有 `(with patched qt)`
- 系统里要有可用字体（fontconfig / freetype + 实际字体文件），中文场景需另装中文字体
- 容器里注意基础镜像用 glibc 系；Alpine（musl）跑不起来
- 渲染的 HTML 必须是你自己控制的，或已经过消毒

## 使用

一条命令把 HTML 变成 PDF：

```bash
wkhtmltopdf --enable-local-file-access input.html output.pdf
```

| 目标 | 关键参数 |
|---|---|
| 本地图片/CSS 能用 | `--enable-local-file-access` 或 `--allow <目录>` |
| 纸张与边距 | `-s A4`、`-O Landscape`、`-T/-B/-L/-R <尺寸>` |
| 页眉页脚 | `--header-center "..."`、`--footer-center "第 [page] / [topage] 页"`、`--header-html` |
| 封面与目录 | `cover cover.html toc --xsl-style-sheet my.xsl body.html out.pdf` |
| JS 渲染的页面 | `--javascript-delay <毫秒>`、必要时 `--no-stop-slow-scripts` |
| 打印样式 | `--print-media-type`；尺寸对不上时加 `--disable-smart-shrinking` |
| 资源缺失别中断 | `--load-error-handling ignore` |
| 批量 | `--read-args-from-stdin < cmds` |
| 出图片 | `wkhtmltoimage --width 1200 input.html output.png` |

完整选项分组见 `SKILL.md` 与 `references/options.md`，
目录定制、批量与 Serverless 运行见 `references/toc-and-batch.md`。

## 依赖

- wkhtmltopdf / wkhtmltoimage 可执行文件（当前稳定系列 0.12.6）
- 运行期依赖系统库与字体；官方包按发行版分别构建
- 无需显示器；不需要常驻服务
- 上游许可是 LGPL-3.0

## 安全

- 不内嵌任何密钥
- **不要用它渲染不可信的用户 HTML**：官方警告其中的 JS 可以完全接管所在服务器；
  必须用的话先消毒内容，并配合 AppArmor / SELinux 之类的强制访问控制
- 它默认**禁止**本地文件互相读取（`--disable-local-file-access`），
  只有显式加 `--enable-local-file-access` 或 `--allow <目录>` 才放开，不要无脑全开
- 会按页面里的引用主动访问远程地址；内网环境注意用 `--proxy` 与 `--bypass-proxy-for` 控制走向
- HTTP 认证与 Cookie（`--username`/`--password`/`--cookie`/`--custom-header`）属于业务参数，
  不要写死在脚本或配置里

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`wkhtmltopdf`
- 仓库：https://github.com/wkhtmltopdf/wkhtmltopdf

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
