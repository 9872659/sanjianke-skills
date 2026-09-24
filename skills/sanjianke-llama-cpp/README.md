# 三剪客 · 本地 LLM 推理引擎 Skill

用 C/C++ 写的本地大模型推理引擎，把 GGUF 量化模型跑在 CPU、Apple 芯片或自家显卡上，并能对外提供 OpenAI 兼容接口。

---

## 前置条件

- 一份 **GGUF 格式**模型权重；非 GGUF 的需要先用仓库自带工具转换。
- 足够的内存（以及可选显存）：模型体积 + KV cache + 运行时开销都要算进去。
- 源码编译需要 CMake 与 C++ 工具链；Windows 上需要 Visual Studio 2022 并勾选「使用 C++ 的桌面开发」。
- Docker 方式需要本机 Docker；用 GPU 还需要宿主机的 nvidia-container-toolkit（Linux）。

---

## 使用

先确认这一版的可执行文件名，再选入口：

```bash
llama --help          # 新版统一入口：llama cli / llama serve
llama-cli --help      # 旧版二进制名，大量现存脚本与 Docker 文档仍是这套
```

从 Hugging Face 直接下载并对话 / 起服务：

```sh
llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF
```

用本地 GGUF 文件跑，并把层放进显存：

```bash
llama-cli -m model.gguf -ngl auto -c 32768 -ctk q8_0 -ctv q8_0
```

完整的六块内容（定位 / 什么时候用·不用 / 安装 / 常用操作 / 常见坑 / 能力边界）见 `SKILL.md`。

---

## 依赖

- GGUF 模型权重（自行获取，遵守其许可）。
- 可选：CMake + C++ 工具链（源码构建）；Docker（容器方式）；OpenSSL 开发库（要 HTTPS/TLS 时）。
- 可选：CUDA / ROCm / Vulkan / SYCL / Metal 等后端对应的驱动与运行库。
- 具体版本与发布节奏以仓库 Releases 页面为准（正式 tag 与 `b` 开头的 nightly 并存）。

---

## 安全

- 不内嵌任何密钥
- `llama-server` 会占用端口；对公网暴露前必须自己加鉴权与访问控制（它本身面向本地/内网使用）
- 拉取模型时注意权重许可与来源可信度，不要执行来源不明的转换脚本
- `-hf` 会联网下载并以本地进程权限写盘，路径与仓库名来自外部输入时先校验

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`llama.cpp`
- 仓库：https://github.com/ggml-org/llama.cpp

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
