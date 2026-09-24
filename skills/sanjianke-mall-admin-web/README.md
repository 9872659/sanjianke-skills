# 三剪客 · 电商后台管理前端 Skill

mall-admin-web：电商后台管理前端 的安装、常用命令与避坑要点

---

## 前置条件

- **Node.js v20 及以上**（官方建议用 v20.x 的 LTS 版）。版本不够会在装依赖或启动阶段直接报错。
- 一个可访问的后端服务。默认按 `http://localhost:8080` 联调；只想看界面可以用官方文档里提到的在线 API（仅有查看权限）。
- 可用的 npm 源。国内网络建议先执行 `npm config set registry https://registry.npmmirror.com`。
- 磁盘与网络能支撑一次完整的依赖安装（首次 `npm install` 会拉取较多包）。
- 可选：Nginx 或其他静态文件服务器，用于托管构建产物。
- 不需要任何账号或 Key。本工程不内嵌密钥，登录凭证来自你部署的后端。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短跑通路径：

```bash
git clone https://github.com/macrozheng/mall-admin-web.git
cd mall-admin-web
npm config set registry https://registry.npmmirror.com   # 国内网络建议
npm install
```

启动前先改根目录 `.env.development` 里的后端地址：

```bash
# 后端API基础路径
# 不搭建后端，使用在线API可修改为（仅有查看权限）：https://admin-api.macrozheng.com
VITE_BASE_SERVER_URL = http://localhost:8080
```

然后启动开发服务器并访问 http://localhost:5173 ：

```bash
npm run dev
```

生产构建：

```bash
npm run build
```

产物默认在 `dist/`。官方也提供 GitHub Releases 的发行包，解压放到 Nginx 的 `html` 目录下（命名为 `admin`）后访问 `http://localhost/admin/` 即可。

具体的构建脚本名称、产物目录与发行包地址，以仓库当前 `package.json` 与 Releases 页为准。

---

## 依赖

- Node.js v20+
- npm（随 Node.js 安装）或 yarn
- 项目自身的前端依赖，由仓库的 `package.json` 声明，通过 `npm install` 安装
- 运行时的后端接口（本 Skill 不提供）
- 可选：Nginx，用于生产环境静态托管

---

## 安全

- 不内嵌任何密钥
- 登录账号密码来自你自己部署的后端，不要提交到仓库；`.env` 类文件里也不要写真实生产凭证
- `.env.development` 里配置的后端地址会被浏览器直接请求，上线前确认暴露的是预期的公网或内网地址，避免把内部管理接口暴露到公网
- 直接 `npm run dev` 起的开发服务器面向本机调试，不要当生产服务器使用；生产请用构建产物 + 静态服务器
- 部署到公网前必须自行补齐鉴权、HTTPS、跨域白名单与访问日志，默认配置不含这些
- 执行 `npm install` 会运行依赖包的生命周期脚本，只在你信任的源与网络环境下安装

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`mall-admin-web`
- 仓库：https://github.com/macrozheng/mall-admin-web

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
