# 三剪客 · 读写 Word 文档 Skill

用 Python 批量生成、修改、抽取 `.docx` 文档：模板填数、报告出稿、表格写入、正文与表格文本提取。
不需要装 Office，也不依赖任何在线服务。

---

## 前置条件

- Python 3.6 以上（建议 3.8+），`pip` 可用。
- 待处理文件必须是 `.docx`；`.doc` 需先用 LibreOffice 等转换。
- 若要用自定义样式（如 `Intense Quote`、列表样式），先在 Word 里把样式做好并另存为模板。

---

## 使用

1. 安装：`pip install python-docx`
2. 在 Agent 会话里说明任务类型——生成、批量替换、还是内容抽取，并给出输入文件/模板路径。
3. 关键代码套路见 `SKILL.md` 的「常用操作」六段示例，可直接照用。
4. 产出建议写到新文件名，确认无误后再替换原始素材。

---

## 依赖

- `python-docx`（导入名为 `docx`）
- `lxml`（`pip` 会自动安装）
- 可选：LibreOffice（仅用于 `.doc` → `.docx` 转换或导出 PDF，本 Skill 不覆盖导出）

---

## 安全

- 不内嵌任何密钥
- 不联网运行：除 `pip install` 外无网络请求
- 只读写用户显式指定的文件路径，不会扫描或上传文档内容
- 批量处理前建议先备份原目录，避免原地覆盖

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`python-docx`
- 仓库：https://github.com/python-openxml/python-docx

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
