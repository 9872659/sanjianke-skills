# 三剪客 · 数据库智能问答 Skill

接上数据库与 CSV / Excel，用自然语言提问，让 AI 自己写 SQL、跑分析、出图表和结论。本 Skill 覆盖 DB-GPT 的安装路径选择、服务启动、CLI 知识库与模型管理，以及端口、路径、容器持久化相关的真实坑点。

---

## 前置条件

- Python **3.10+**，推荐安装 `uv`。
- 一个可用的模型来源：本地 GPU + 模型权重，或至少一个云端模型 API Key。
- 一键安装脚本当前面向 macOS / Linux；Windows 建议 WSL 或 Docker。
- 走 Docker 需要本机 Docker；走 GPU 容器还需 NVIDIA Container Toolkit。
- 若要连业务数据库，请准备只读、最小权限的数据库账号。

---

## 使用

本 Skill 的正文按「先判断该不该用 → 再选安装路径 → 再动手操作 → 最后查坑」的顺序组织：

1. **什么时候用 / 不用**：先说清它不是一个小库，而是一整套自托管应用，避免方向性误判。
2. **安装**：三条真实路径——一键脚本（macOS / Linux）、PyPI（`dbgpt-app`）、Docker（无 GPU 的代理模型模式 / 有 GPU 的本地模型模式）。
3. **常用操作**：`dbgpt start webserver|controller|apiserver`、`dbgpt knowledge load|list|delete`、`dbgpt model start|list|chat`，都是可直接粘贴执行的命令。
4. **常见坑**：端口不一致、仓库被装到 `~/.dbgpt/DB-GPT`、PyPI 包名是 `dbgpt-app`、`--local_doc_path` 的默认值指向别人机器、CLI 默认连 5670、容器路径必须是 `/app/...`、容器数据不持久化。

典型调用链：

```bash
uv pip install dbgpt-app
dbgpt start                      # 首次运行走交互向导，配模型与 Key
# 浏览器打开日志里打印的监听地址

dbgpt knowledge load --space_name default --local_doc_path /path/to/docs
dbgpt knowledge list --space_name default --show_content --output json
```

---

## 依赖

- 运行环境：Python 3.10+；Docker 为可选路径。
- 模型侧：本地 GPU 推理或第三方模型 API，二者至少要有一个。
- 向量库：知识库功能默认使用 ChromaDB，可切换其他后端。
- 官方安装文档：<http://docs.dbgpt.cn/docs/installation>。

---

## 安全

- 不内嵌任何密钥
- 模型 API Key 由使用者自行提供，写在环境变量或本机配置里，不要提交进版本库
- 一键安装脚本会下载并执行远程脚本，建议先 `curl -o install.sh` 落地后自行过一遍再执行
- 连接业务数据库时使用只读、最小权限账号，不要给管理员权限
- 代码执行走沙箱机制，但沙箱是风险控制手段而非绝对隔离承诺；生产环境请限制可访问的数据范围
- Docker 部署时明确挂载与持久化哪些目录，避免敏感数据散落在容器内

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`DB-GPT`
- 仓库：https://github.com/eosphoros-ai/DB-GPT

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
