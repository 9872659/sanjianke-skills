# 三剪客 · 任意文档转 Markdown Skill

markitdown：任意文档转 Markdown 的安装、常用命令与避坑要点

---

## 前置条件

- Python **3.10 及以上**（上游要求）。
- 建议先建独立虚拟环境，避免依赖冲突。
- 想省事就把可选依赖装齐：`pip install 'markitdown[all]'`。
- 需要 OCR / 图像理解时，另外准备一个 OpenAI 兼容的模型服务与客户端。
- 走 Azure 云能力时，需要 Azure 资源端点与凭证（按量计费）。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install 'markitdown[all]'
markitdown path-to-file.pdf -o document.md
```

嵌进 Python 流水线：

```python
from markitdown import MarkItDown

md = MarkItDown(enable_plugins=False)
result = md.convert("test.xlsx")
print(result.markdown)
```

命令行参数、可选依赖名称与 Python API 细节以 `markitdown --help` 和上游仓库 README 的当前内容为准。

---

## 依赖

- Python 3.10+
- 按格式选择的可选依赖：`pptx` / `docx` / `xlsx` / `xls` / `pdf` / `outlook` / `az-doc-intel` / `az-content-understanding` / `audio-transcription` / `youtube-transcription`，或一把梭 `all`
- 可选：`markitdown-ocr` 插件 + 一个 OpenAI 兼容客户端（扫描件 OCR）
- 可选：Docker（用官方 Dockerfile 构建镜像后管道转换）

---

## 安全

- 不内嵌任何密钥
- 该工具以当前进程的权限执行 I/O，等价于 `open()` 或 `requests.get()`；处理不受信任的输入前必须校验并限制文件路径、URI scheme 与网络目标，避免访问内网、回环、链路本地和元数据服务地址
- 按最小必要原则选接口：只读本地用 `convert_local()`，自己取回响应用 `convert_response()`，最可控是 `convert_stream()`
- 涉及云端转换（Azure）时注意每次调用都会计费，可用 `cu_file_types` 限制路由到云端的格式

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`markitdown`
- 仓库：https://github.com/microsoft/markitdown

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
