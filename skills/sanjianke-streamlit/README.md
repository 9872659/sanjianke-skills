# 三剪客 · 纯 Python 数据应用框架 Skill

不用写前端就把 Python 脚本变成能给同事点着用的网页应用

---

## 前置条件

- 装好 Python 3 并能使用 pip
- 想清楚要展示什么：数据从哪来（本地文件、数据库、API）、用户能改哪些参数
- 密钥类配置准备好（数据库密码、第三方 API Key），后续放进 `.streamlit/secrets.toml` 或环境变量
- 要对外访问的话，规划好端口、反向代理与访问控制；本地开发只需浏览器

---

## 使用

1. 安装并验证：

   ```bash
   pip install streamlit
   streamlit version
   streamlit hello
   ```

2. 写应用脚本（最小示例）：

   ```python
   import streamlit as st

   x = st.slider("选一个数", 0, 100, 10)
   st.write(x, "的平方是", x * x)
   ```

3. 运行：

   ```bash
   streamlit run streamlit_app.py
   ```

4. 基本纪律：慢函数加 `@st.cache_data`（返回数据）或 `@st.cache_resource`（连接、模型），需要跨重跑保留的值放 `st.session_state`
5. 密钥统一走 `st.secrets`，本地 `.streamlit/secrets.toml` 要加进 `.gitignore`
6. 部署：官方托管平台，或自托管容器；容器里以 `streamlit run` 为启动命令
7. 完整的控件用法、缓存选型判据、命令行清单与坑位对照表，见 `SKILL.md`

关键约定：脚本每次交互都会从头再跑一遍，缓存与状态是基本功而不是可选优化。

---

## 依赖

- Python 3 与 pip
- `streamlit` 本体
- 应用自身依赖：pandas、绘图库、数据库驱动、模型推理库等，按需装
- 可监听端口的环境；自托管部署时通常还需要容器运行时与反向代理
- 外部服务的凭证，通过 `st.secrets` 或环境变量注入

---

## 安全

- 不内嵌任何密钥
- 所有密钥只走 `st.secrets` 或环境变量；`.streamlit/secrets.toml` 必须进 `.gitignore`，不要提交进仓库
- `@st.cache_data` 内部用 pickle 序列化，官方明确提示不要缓存来源不可信的数据
- `@st.cache_resource` 的返回值是所有会话共享的单例，改它会影响所有人；多用户场景要确认返回对象线程安全
- 上传文件只在服务端内存或临时目录处理，不要把用户上传的原始文件长期留在可公开访问的路径
- 对外提供服务时要放在反向代理之后，配 HTTPS 与访问控制，不要直接把应用端口裸暴露到公网
- 数据库账号用只读或最小权限；查询接口不要把用户输入直接拼进 SQL
- 处理他人数据时注意合规：只接已获授权的数据源，页面与下载结果不要包含不必要的个人标识字段

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`streamlit`
- 仓库：https://github.com/streamlit/streamlit

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
