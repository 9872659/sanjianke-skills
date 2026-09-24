# 三剪客 · 离线批量 OCR Skill

教你用 Umi-OCR 做离线批量 OCR：怎么装、怎么用命令行和本地 HTTP 接口调用、扫描 PDF 怎么转双层可搜索 PDF，以及几个踩过才知道的坑。

---

## 前置条件

- 平台限 **Windows 7 x64** 或 **Linux x64**（官方发行版口径）。
- 程序是解压即用的桌面程序，**不需要安装 Python**，也不需要账号或 Key。
- 用命令行或 HTTP 接口前，必须先启动 Umi-OCR 主程序，并允许 HTTP 服务（默认开启，主机建议「仅本地」）。
- 默认接口端口 `1224`，可在全局设置中修改。

---

## 使用

1. 下载发布包（`.7z` 或 `.7z.exe` 自解压包），解压后启动 `Umi-OCR.exe`；Linux 用 `umi-ocr.sh`。
2. 图形界面里可以直接用：截图 OCR、批量 OCR、文档识别、二维码。
3. 要脚本化，用命令行：`umi-ocr --path "D:/img.png" --output result.txt`。
4. 要接进程序，用本地 HTTP 接口：`POST http://127.0.0.1:1224/api/ocr`。
5. 扫描 PDF 走五步流程（上传 / 轮询 / 生成 / 下载 / 清理），细节见 `references/http-api.md`。

完整操作步骤、常见坑、能力边界见 `SKILL.md`。

---

## 依赖

- Umi-OCR 主程序（自带离线 OCR 引擎插件：PaddleOCR-json 或 RapidOCR-json）。
- Windows / Linux 运行库由官方随包提供，位于独立仓库。
- HTTP 调用方任意语言皆可，示例用 Python + `requests`。
- 不需要联网，OCR 全程本地运行。

---

## 安全

- 不内嵌任何密钥。
- 命令行与 HTTP 接口走 `127.0.0.1` 本地环回，不经过物理网卡；只有主动把主机改为「任何可用地址」才暴露到局域网，默认不要这么改。
- 文档识别会在本机保存上传文件与中间产物，任务默认 24 小时后自动清理；建议任务完成后主动调用 `/api/doc/clear/<id>`。
- 关闭软件前先断开 HTTP 调用方连接，否则网络子线程可能导致进程不退出。
- Skill 本体只包含文档，不含上游项目的源代码；上游代码的问题请走上游仓库的 Issues。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Umi-OCR`
- 仓库：https://github.com/hiroi-sora/Umi-OCR

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
