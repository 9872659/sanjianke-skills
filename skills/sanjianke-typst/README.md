# 三剪客 · 现代排版出 PDF Skill

用一份纯文本源文件编出排版规整的 PDF：公式、目录、图表、参考文献、页眉页脚、页码编号都由排版系统负责，人只写内容。适合"模板 + 数据 → 批量出 PDF"这类需求。

---

## 前置条件

- 装好 `typst` 命令行后先跑 `typst --version`；**包管理器里的版本可能落后于最新 release**，遇到不认识的语法或参数先对版本。
- **CJK 文档必须自备中文字体**：系统装好，或用 `--font-path` 指定字体目录；`typst fonts` 可以确认它到底发现了哪些字体。容器镜像里通常只有极少数西文字体。
- 只有 `typst update` 与引用 `@preview/...` 模板/包时才需要联网；纯本地文档可完全离线。
- 文档里引用的图片、CSV/JSON、`.bib` 默认必须在项目根之内；要跨目录得用 `--root` 重新划定根。
- 不需要 TeX 发行版、不需要账号、不需要 API Key。

---

## 使用

最短路径：

```bash
# 1. 装（任选其一）
brew install typst                                # macOS
winget install --id Typst.Typst                   # Windows
cargo install --locked typst-cli                  # 有 Rust 工具链
docker run --rm ghcr.io/typst/typst:latest --help # 只想在容器里跑

# 2. 自检
typst --version
typst info
typst fonts

# 3. 编译
typst compile file.typ                  # 生成 file.pdf
typst compile src.typ out/report.pdf    # 指定输出
typst watch file.typ                    # 边写边自动重编

# 4. 按需：只导出部分页 / PNG 插图 / PDF 合规
typst compile --pages 2,3-6 doc.typ out.pdf
typst compile --format png --ppi 300 doc.typ "page-{0p}-of-{t}.png"
typst compile --pdf-standard a-2b,ua-1 doc.typ out.pdf

# 5. 模板化：把参数传进文档
typst compile -i title=季度报告 doc.typ out.pdf
# 文档里用 sys.inputs.at("title") 读（读出来是字符串）

# 6. 从模板起步
typst init @preview/charged-ieee my-paper
```

语言写法（标题、公式、表格、读 CSV 铺数据、set/show 规则）见 `references/typst-syntax.md`。

---

## 依赖

| 项 | 说明 |
|---|---|
| 操作系统 | Windows / macOS / Linux，官方提供预编译二进制 |
| 运行时 | 预编译二进制零依赖，**不需要 TeX 发行版**；cargo 路线才需要 Rust |
| 字体 | 必需项。CJK 文档要自备中文字体，用 `--font-path` 或 `TYPST_FONT_PATHS` 指路 |
| 网络 | 仅 `typst update` 与 `@preview/...` 包/模板需要；可用 `--package-path` / `--package-cache-path` 指向本地缓存 |
| 磁盘 | 二进制很小；包缓存与字体目录另行占用 |
| Docker（可选） | 官方镜像 `ghcr.io/typst/typst`；容器内缺字体，需挂载字体目录 |
| 账号 / Key | 不需要，无费用 |
| 上游仓库 | https://github.com/typst/typst （Apache-2.0，独立于本 Skill 的第三方项目） |

本 Skill 只提供使用说明与流程编排，**不打包、不修改、不重新分发上游的任何代码或二进制**。

---

## 安全

- 不内嵌任何密钥。该工具不需要凭证。
- 网络出口只有两处：`typst update` 拉二进制、渲染时下载 `@preview/...` 包/模板。企业代理或自签证书环境用 `--cert`（或 `TYPST_CERT`）指定 CA。
- `typst watch` 会常驻监听文件变化；HTML 导出场景可能额外起一个本地 HTTP 服务（默认在 3000–3005 中挑空闲端口），不需要时用 `--no-serve` 关掉。
- 文档编译会读取本地文件（图片、CSV/JSON、文献库、字体目录）。文件访问默认限定在项目根内，跨目录要用 `--root` 显式放开——**不要为了图省事把根设到整个用户目录或根目录**。
- 输出 PDF/PNG/SVG 可能包含完整文档内容，敏感材料的输出目录记得清理。
- 本 Skill 不代理任何在线编译服务，不转发请求，不代收费用。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`typst`
- 仓库：https://github.com/typst/typst

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
