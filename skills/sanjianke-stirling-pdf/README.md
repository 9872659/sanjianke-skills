# 三剪客 · 本地 PDF 工具箱 Skill

把 50 多个 PDF 工具装进自己机器：一条 docker run 起服务，浏览器点着用，脚本走 REST API，重复流程用流水线一次跑完。文档不出本地。

---

## 前置条件

- 一台能跑 Docker 的机器（本地、内网服务器都可以）。
- 至少给 `/configs` 准备一个持久化目录，否则配置和数据库会随容器消失。
- 要 OCR 就再准备一个 tessdata 目录并放到 `/usr/share/tessdata`。
- 完整版镜像建议预留 4G 级别内存。
- 不做源码开发的话，不必装 JDK / Node.js。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
docker run -d --name stirling-pdf -p 8080:8080 \
  -v ./stirling-data:/configs \
  docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest
```

浏览器打开 `http://localhost:8080`。默认会创建管理员 `admin` / `stirling`，**登录后立刻改密码**。

脚本调用：

```bash
curl -X POST "http://localhost:8080/api/v1/security/add-watermark" \
     -H "Content-Type: multipart/form-data" \
     -F "fileInput=@sample.pdf" \
     -F "watermarkType=text" \
     -F "watermarkText=DRAFT" \
     -o output.pdf
```

完整的端点清单以你的实例上的 `/swagger-ui/index.html` 为准；这类文档随版本变化，不要凭记忆写参数。

---

## 依赖

- Docker（推荐）；源码开发需要 JDK 25、Node.js 22+、Task
- 容器内已含 Tesseract（OCR）；高级 OCR 预处理需要 OCRmyPDF
- Office 格式转换依赖 LibreOffice；PDF 优化依赖 qpdf；AI 文档创建依赖 WeasyPrint
- 要接入 AI 助手时可启用内置 MCP 服务，需要一个 MCP 客户端

---

## 安全

- 不内嵌任何密钥
- 登录默认是开启的，默认口令 `admin` / `stirling` 是公开信息，首次登录必须改
- 对公网暴露前务必确认安全设置、API Key 策略与端口访问范围
- 容器内会调用 LibreOffice、Tesseract、qpdf 等外部组件处理你上传的文件；只处理可信来源的文档，并注意这类组件本身的历史安全公告
- 生产环境建议用环境变量注入 API Key，不要把 Key 写进脚本或镜像

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Stirling-PDF`
- 仓库：https://github.com/Stirling-Tools/Stirling-PDF

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
