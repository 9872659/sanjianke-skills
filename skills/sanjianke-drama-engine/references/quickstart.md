# 上手与部署

Toonflow 是 Electron 桌面应用 + Express 后端一体的，安装方式选一条即可。三种跑法
面向不同的人，先选对再动手。

| 你的情况 | 选哪种 | 大概耗时 |
|---|---|---|
| 只想用，不想碰代码 | 下 Release 安装包 | 5 分钟 |
| 要接自己的模型、改提示词 | `yarn dev:gui`（Electron 桌面端） | 20 分钟 |
| 要在服务器上跑给团队用 | 云服务器 + PM2，或 Docker | 30~60 分钟 |

---

## 一、安装包（普通用户）

到 Release 页下载对应系统的安装包。Windows / Linux / macOS 都有。

> **macOS 特别注意**：首次打开可能被证书拦下，要去「设置 → 隐私与安全性」放行，
> 否则双击没反应。

Gitee 因 Release 附件大小限制不提供安装包下载，国内用户从它指向的 GitHub Release 取。

**首次登录**：账号 `admin`，密码 `admin123`。**登进去第一件事就是改密码**——这个默认
口令是公开写在上游 README 里的。

---

## 二、本机开发 / 自定义（推荐给要调提示词的人）

### 环境

| 项目 | 要求 |
|---|---|
| Node.js | **23.11.1 以上**，推荐 24.x |
| 包管理器 | Yarn |
| 内存 | 2GB 以上 |

Node 版本这块最容易踩坑：低一个主版本会在装原生依赖（`better-sqlite3`、`sharp`）时编译失败。

### 命令

```bash
git clone https://gitee.com/HBAI-Ltd/Toonflow-app.git   # 国内走 Gitee
cd Toonflow-app
yarn install
```

装完按需要选启动方式：

| 命令 | 起来什么 | 说明 |
|---|---|---|
| `yarn dev` | 只有后端 API，端口 10588 | **没有网页界面**，直接访问只能调接口 |
| `yarn dev:gui` | 后端 + Electron 桌面窗口 | 自带内置前端，开箱即用，**日常用这个** |
| `yarn start` | 生产模式跑编译产物 | 要先 `yarn build` |

打包：

```bash
yarn build          # 编译 TypeScript
yarn dist:win       # 打 Windows 安装包
yarn dist:mac
yarn dist:linux
yarn lint           # 类型检查
yarn debug:ai       # AI SDK 可视化调试面板，调提示词时很有用
```

### 改前端界面

前端是独立仓库 **Toonflow-web**。本仓库自带编译好的前端资源，普通使用不用管。
要改界面就改前端仓库，构建后把 `dist` 目录内容复制到本项目的 `data/web/`。

---

## 三、Docker

```bash
git clone https://gitee.com/HBAI-Ltd/Toonflow-app.git
cd Toonflow-app
yarn docker:local
```

或者手动：

```bash
docker build -t toonflow .
docker run -d -p <本地端口>:10588 -v <本地数据路径>:/app/data toonflow
```

起来后访问 `http://localhost:<本地端口>/web/index.html`。

**注意路径结尾是 `/web/index.html`**，直接开根路径看不到界面。

`-v` 那个挂载别省：数据库、素材、模型缓存全在 `/app/data` 下，不挂容器一删全没。

---

## 四、云服务器（团队使用）

### 环境要求

- Ubuntu 20.04+ / CentOS 7+
- Node.js 24.x（最低 23.11.1+）
- 内存 2GB+

### 部署

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 24
npm install -g yarn pm2

cd /opt
git clone https://gitee.com/HBAI-Ltd/Toonflow-app.git
cd Toonflow-app
yarn install
yarn build
```

### PM2 配置

建 `pm2.json`：

```json
{
  "name": "toonflow-app",
  "script": "data/serve/app.js",
  "instances": "max",
  "exec_mode": "cluster",
  "env": {
    "NODE_ENV": "prod",
    "PORT": 10588,
    "OSSURL": "http://127.0.0.1:10588/"
  }
}
```

```bash
pm2 start pm2.json
pm2 startup
pm2 save
```

常用命令：`pm2 list` 看进程、`pm2 logs toonflow-app` 看日志、`pm2 restart all` 重启、
`pm2 monit` 监控面板。

> `OSSURL` 要填**外部能访问到的地址**。填 `127.0.0.1` 时本机能用，但生成的图片/视频
> 链接在别人浏览器里打不开——这是云端部署最常见的「图裂了」原因。

### 环境变量

| 变量 | 说明 |
|---|---|
| `NODE_ENV` | `prod` 为生产环境 |
| `PORT` | 服务端口，默认 10588 |
| `OSSURL` | 静态资源访问地址 |

### 端口

| 端口 | 用途 |
|---|---|
| `10588` | 软件界面 + API |

---

## 六、启动后第一件事：配模型

界面进去是空的，因为还没接模型。**模型服务**里配三类：

| 类型 | 用途 | 上游 Demo 用的 |
|---|---|---|
| 文本模型 | 拆事件、写骨架、出剧本、生成提示词 | Claude Opus 4.6 |
| 图像模型 | 角色/场景/道具/分镜图 | GPT Image 2 |
| 视频模型 | 图生视频 | Seedance 2.0 |

支持 OpenAI 标准接口，所以任何兼容 OpenAI 协议的网关都能接。厂商预设覆盖
OpenAI / Anthropic / Google / DeepSeek / 智谱 / MiniMax / 通义千问 / xAI。

配完**务必检查两处**，漏一处就会出现「模型配了但不生效」：

1. **模型服务**里的三个调用开关是否都开着；
2. **Agent 配置**里各 Agent 引用的模型是否和你刚配的一致（不一致就点开改）。

供应商还支持**直接写 TypeScript 逻辑**并在设置中心即时生效，不用改源码、不用重启。
私有化部署或接自建网关时用这个。

---

## 七、项目结构（改东西时看）

```
data/
├─ models/    本地推理模型（ONNX）
├─ oss/       对象存储：素材 / 角色 / 场景
├─ serve/     生产环境入口
├─ skills/    ★ Agent 技能提示词，改提示词就改这里
└─ web/       前端编译产物（内置）
src/
├─ agents/
│  ├─ scriptAgent/       剧本 Agent
│  └─ productionAgent/   制片 Agent
├─ routes/               各模块 REST 路由
├─ socket/               WebSocket 实时通信
└─ app.ts                入口
```

技术栈：Node.js 23.11.1+ / TypeScript 5 / Express 5 / SQLite（better-sqlite3 + knex）/
Vercel AI SDK / ONNX 本地推理 / Socket.IO / Electron 40 / Sharp。

---

## 八、多语言

界面支持简体中文、繁體中文、English、ไทย、Tiếng Việt、日本語、Русский。
默认界面语言不对时，去设置里改。