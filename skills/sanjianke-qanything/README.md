# 三剪客 · 本地知识库问答 Skill

把本地文件变成能问答的知识库：PDF / Word / PPT / Excel / Markdown / 邮件 / 图片 / CSV / 网页丢进去就能问，走两阶段检索（向量召回 + 重排），支持完全离线内网部署。本 Skill 覆盖版本选型、启动参数、知识库 REST 接口与真实坑点。

---

## 前置条件

- **Docker 版**（生产推荐）：NVIDIA 显存 ≥ 4GB（用云端 LLM 时可低至 GTX 1050Ti 档，推荐 RTX 3090）、NVIDIA 驱动 ≥ 525.105.17、Docker ≥ 20.10.5、docker compose ≥ 2.23.3、git-lfs。
- **Windows**：需 WSL Ubuntu 子系统、GeForce Experience ≥ 546.33、Docker Desktop ≥ 4.26.1，全部命令在 WSL2 里执行。
- **Python 版**（快速体验 / 纯 CPU / Mac）：见仓库 `qanything-python` 分支的 README，官方说明其不适用于生产环境。
- 模型权重从 ModelScope / wisemodel / Hugging Face 获取；离线环境需提前下载并放进 `assets/custom_models`。
- 走 `-c cloud` 需要 OpenAI 兼容的模型服务与 Key。
- 端口 8777 需可用。

---

## 使用

正文按「先选版本 → 再看前置条件 → 再选启动命令 → 再用接口 → 最后查坑」组织：

1. **什么时候用 / 不用**：先排除「只是想 import 一个 RAG 库」「没有 GPU 也没有 Key」这类误判。
2. **安装**：Docker 版完整流程（前置表格、`git clone` + `bash run.sh`、`run.sh` 全部参数表、按显存给出的四档启动命令、模型下载、离线安装的打包 / load 流程）；Python 版指向官方指引。
3. **常用操作**：建库 → 上传文件 → 传网页 → 非流式问答 → 流式问答 → 查状态 / 清理 / 删除，全部是可直接跑的最小代码。
4. **常见坑**：版本功能不对等、文档信息差、OCR 在部分显卡上返回空、显存降配四步法、上传状态 `red`/`yellow`、`user_id` 隔离、跨接口参数名不一致、离线镜像 tag、WSL 环境。

典型调用链：

```bash
git clone https://github.com/netease-youdao/QAnything.git
cd QAnything
bash ./run.sh -c cloud -i 0 -b default     # 显存紧时：本地检索 + 云端 LLM
# 前端 http://<host>:8777/qanything/   接口 http://<host>:8777/api/
```

```python
# 建库 → 上传 → 提问
POST /api/local_doc_qa/new_knowledge_base   {"user_id": "zzp", "kb_name": "kb_test"}
POST /api/local_doc_qa/upload_files         files + {user_id, kb_id, mode}
POST /api/local_doc_qa/local_doc_chat       {user_id, kb_ids, question, rerank, streaming}
```

---

## 依赖

- Docker 与 docker compose、NVIDIA 驱动、git-lfs（Docker 版）。
- 依赖组件容器：Milvus（向量库）、MinIO、etcd、MySQL —— 离线安装时必须一并打包。
- 模型权重：内置问答模型或公开模型，需自行下载。
- 检索侧使用的嵌入与重排模型随镜像 / 代码提供。
- 具体依赖与版本要求以仓库和官方启动用法文档为准。

---

## 安全

- 不内嵌任何密钥
- 云端模型 Key 由使用者自行配置在 `.env` 里，不要提交进版本库
- 服务默认监听 8777，建议只在内网暴露，不要直接映射到公网
- 上传接口有 `user_id` 隔离，但这不是权限系统；多租户场景要在网关层自行加鉴权
- 上传的文档会落盘到本机并写入向量库，涉及敏感数据时先确认存储位置与备份策略
- 删除类接口是批量生效的：按状态清理会一次删掉该状态下全部文件，删库接口一次可删多个 `kb_ids`，调用前先确认目标
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明
- 能力边界见 SKILL.md 的「能力边界」一节

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`QAnything`
- 仓库：https://github.com/netease-youdao/QAnything

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
