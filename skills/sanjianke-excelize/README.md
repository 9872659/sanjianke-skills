# 三剪客 · Go 操作 Excel Skill

excelize：Go 操作 Excel 的安装、常用命令与避坑要点

---

## 前置条件

- 一个 Go 工程（go modules 管理依赖）
- Go 工具链版本满足上游要求（当前仓库 README 写的是 1.25.0 或更高）
- 能执行 `go get github.com/xuri/excelize/v2`
- 不需要安装 Office、不需要 CGO、不需要任何外部服务

---

## 使用

在 Go 项目里引库，按需挑一套 API：

| 场景 | 入口 |
|---|---|
| 新建一个工作簿并写入 | `excelize.NewFile()` + `SetCellValue` / `SetSheetRow` + `SaveAs` |
| 打开已有文件读数据 | `excelize.OpenFile()` + `GetRows` |
| 几十万行的大表写入 | `NewStreamWriter` + 循环 `SetRow` + `Flush` |
| 大表顺序读取 | `f.Rows(sheet)` 迭代器 + `rows.Close()` |
| 读密码文件 | `excelize.OpenFile(name, excelize.Options{Password: "..."})` |
| 定义单元格样式 | `NewStyle` 拿 styleID，再 `SetCellStyle` 应用 |

要点：`NewFile()` 自带一张 `Sheet1`；每个文件都要 `defer f.Close()`。
完整示例、参数与避坑见 `SKILL.md` 和 `references/` 下两份速查。

---

## 依赖

- `github.com/xuri/excelize/v2`（纯 Go，无 CGO）
- 标准库 `encoding/xml`、`archive/zip` 等，由库自己引入
- 插入图片时需要按格式注册解码器：`import _ "image/png"` 等
- 写宏工作簿需要自备 `vbaProject.bin`

---

## 安全

- 不内嵌任何密钥
- 库本身不联网，不上传文档内容
- 打开密码保护的工作簿时，密码由调用方传入，不要写死在代码或配置里
- 流式读写会在系统临时目录生成 `excelize-*` 文件，处理完请确保 `Close()` 已调用
- 处理不可信来源的 xlsx 时注意解压体积上限（`Options.UnzipSizeLimit` 默认 16GB），
  必要时按业务收紧，避免解压炸弹

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`excelize`
- 仓库：https://github.com/qax-os/excelize

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
