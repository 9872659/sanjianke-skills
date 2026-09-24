---
name: sanjianke-sylius
slug: sanjianke-sylius
displayName: 三剪客 · 开源电商平台
description: "Sylius：开源电商平台 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Sylius：开源电商平台 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · 开源电商平台

Sylius 是一个基于 Symfony 的电商框架：它把商品、订单、结算、支付、配送、促销、多通道多货币这些电商概念做成了可配置的"资源"，你写的是配置与少量业务类，而不是从零实现一套购物车。它替用户解决的问题是"我要一个能长期演进、而不是买来就改不动的商城底座"——业务规则留在你的代码与配置里，框架提供模型、后台、API 与状态机。

**上游项目**：`Sylius`　**仓库**：https://github.com/Sylius/Sylius

## 什么时候用 / 不用

**用它**：

- 你的团队本来就是 Symfony / PHP 技术栈，要在同一套框架里做商城，不希望引入第二种后端生态。
- 你要建的是需要长期迭代的业务：复杂的促销规则、多通道定价、多货币、B2B 客户分组价、订阅或目录促销这类玩法。
- 你要拿一个成熟的开源电商底座做二次开发，且看重它的资源（Resource）体系与状态机：商品的上下架、订单的流转都能配置出来而不是硬编码。
- 你要前后端分离：前台自己写，后台用现成的管理面板，中间通过接口对接。
- 你需要快速起一个可演示的商城来验证业务假设，用 Docker 一条命令把环境拉起来。

**不要用它**：

- 你的技术栈是 Java / Node / Python，不愿意为了商城引入 PHP 运行时与 Symfony 生态。
- 你要的是"开箱即用的 SaaS 商城"，装完就能收单：支付网关、配送、邮件这些都需要你自己配置和接入。
- 你的业务只需要一个极简的商品展示与下单表单，整套电商框架的建模成本远高于收益。
- 你没有 Composer、Node.js 工具链和可写的数据库环境——它的安装流程这三样都要用。
- 你的环境是原生 Windows 命令行而不用 WSL：官方给出的支持环境是 macOS / Linux 与 WSL。
- 你打算把它当纯前端或静态站点使用。

## 安装

官方给出两条路径：不用 Docker 的传统安装，和基于 Docker Compose 的开发环境。

**A. 传统安装（不用 Docker）**

```bash
# 1. 用官方项目模板创建工程
composer create-project sylius/sylius-standard AcmeStore
cd AcmeStore
```

```bash
# 2. 先构建前端资源，再执行安装
npm install
npm run build
```

用 yarn 也可以：

```bash
yarn install
yarn build
```

```bash
# 3. 配置数据库连接，写进 .env.local
# MySQL
DATABASE_URL=mysql://<username>:<password>@<host>/<your_database_name>_%kernel.environment%?serverVersion=<your_db_version>&charset=utf8
# MariaDB
# DATABASE_URL=mysql://<username>:<password>@<host>/<your_database_name>_%kernel.environment%?serverVersion=mariadb-<your_db_version>&charset=utf8
# PostgreSQL
# DATABASE_URL=pgsql://<username>:<password>@<host>/<your_database_name>_%kernel.environment%?serverVersion=<your_db_version>&charset=utf8
```

```bash
# 4. 跑交互式安装器
bin/console sylius:install
```

安装器会依次做：检查系统是否满足要求 → 建库建表 → 询问是否导入演示数据 → 走一遍基础店铺配置 → 生成 API 令牌 → 自动安装各 bundle / plugin 的静态资源。

```bash
# 5. 本地起服务并访问
symfony server:start
# 浏览器访问 https://127.0.0.1:8000
```

后台在 `/admin`，用安装过程中你提供的凭证登录。

**B. Docker 开发环境**

```bash
git clone git@github.com:Sylius/Sylius-Standard.git your_project_name
cd your_project_name
make init
open http://localhost/
```

需要本机已安装 Docker 与 `make`。首次构建镜像与初始化容器比较耗时，取决于机器性能与网络。

**可选：固定 Symfony 版本**

```bash
composer config extra.symfony.require "^7.0"
composer update
```

不固定时容易装上与当前 Sylius 版本不匹配的 Symfony 组件版本。

## 常用操作

**1. 交互式安装**

```bash
bin/console sylius:install
```

安装器里的每一步也都有独立子命令可用，例如检查环境、建库、导入示例数据、基础配置、安装资源这些步骤各自对应 `sylius:install:` 前缀的子命令；是否可用以及具体选项以 `bin/console list sylius` 与官方文档为准。

**2. 载入测试数据（fixtures）**

```bash
bin/console sylius:fixtures:load default
```

想看有哪些可用的 fixtures 套件：

```bash
bin/console sylius:fixtures:list
```

**3. 新建管理员账号**

```bash
bin/console sylius:admin-user:create
```

这是一个**纯交互式**命令，会依次询问邮箱、用户名、姓、名、密码（隐藏输入）、语言、是否启用，需要你逐项回答。此外还可以在 `sylius:install` 的数据库步骤里用 `--fixture-suite=<套件名>` 指定自定义 fixtures 套件。

**4. 跑异步任务**

目录促销（Catalog Promotions）这类异步处理需要单独起一个消费者进程：

```bash
php bin/console messenger:consume main
```

生产环境建议交给 Supervisor 这类进程守护工具，避免进程挂掉后没人拉起来。

**5. Docker 环境下的常用快捷命令**

```bash
make up                     # 启动全部容器（后台运行）
make down                   # 停止并移除全部容器
make clean                  # 停止容器并删除数据卷，重置环境
make install                # 以非交互模式跑一次 Sylius 安装器
make php-shell              # 进入 PHP 容器，方便执行 bin/console
make node-shell             # 进入 Node 容器，方便执行 npm install 这类命令
make node-watch             # 在 Node 容器里跑 npm run watch，前端资源自动重建
make docker-compose-check   # 检查 Docker Compose 是否可用并打印版本
```

`make init` 是首次初始化的入口，会构建镜像并拉起容器。

**6. 配置邮件发送**

在 `.env` 里配 `MAILER_DSN` 即可，推荐用 Symfony Mailer。注意**邮件在 test / dev / staging 环境默认不发**，只有 prod 环境默认开启投递。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 安装到一半报找不到静态资源或页面样式全丢 | 前端资源还没构建就跑了安装器 | 先 `npm install && npm run build`（或 `yarn install && yarn build`），再执行 `bin/console sylius:install` |
| 装完之后报 Symfony 组件版本冲突 | 没有固定 Symfony 版本，Composer 装上了不匹配的组合 | 先 `composer config extra.symfony.require "^7.0"` 再 `composer update`；版本要求以当前 Sylius 版本为准 |
| `make init` 时容器反复退出 | 宿主机上 80 / 3306 / 8025 端口已被占用（Nginx、本机 MySQL、其他邮件工具） | 用 `lsof -i :80`、`lsof -i :3306` 查出占用者并停掉，或在 `compose.override.yml` 里改端口映射 |
| 改了 Docker 里的 Nginx 端口后页面打不开 | 访问地址还是默认的 `http://localhost/` | 端口改成 8080 就访问 `http://localhost:8080` |
| 页面报缓存或日志目录不可写 | `var/cache`、`var/log` 权限不足 | 给这两个目录（以及上传媒体目录）正确的写权限，或按部署文档修正属主 |
| 价格全是美元、商品名必须填美式英语 | 安装器默认货币是 USD、默认语言是 English - US | 想改就提前在 `config/services.yaml` 里设置 `locale` 与 `sylius_installer_currency` 参数，再跑安装；装完也可以在后台的 Configuration > Channels 与 `config/services.yaml` 里改 |
| 促销生效不了、异步任务不执行 | 目录促销这类逻辑依赖消息队列消费者，但没起消费者进程 | 单独运行 `php bin/console messenger:consume main`，生产环境用 Supervisor 守护 |
| 到了 `sylius:install` 建库这一步连不上数据库 | `.env.local` 里的 `DATABASE_URL` 没写对，或数据库版本/驱动不符 | 对照 MySQL / MariaDB / PostgreSQL 三种格式逐段核对用户名、库名、`serverVersion` 与 charset |
| 环境检查不通过 | 缺少 PHP 扩展或数据库版本过低 | 补齐 `gd`、`exif`、`fileinfo`、`intl`、`sodium` 等扩展，并把数据库升到 MySQL 8.0+ / MariaDB 10.4.10+ / PostgreSQL 13.9+ 之一 |
| 想直接建库建表，却找不到期望的命令 | 不同版本提供的子命令并不完全一致 | 以 `bin/console list sylius` 和官方文档为准，不要照搬别的版本的命令名 |
| 开发环境收不到邮件却以为是配置错了 | test / dev / staging 环境默认关闭投递 | 这是预期行为；要验证就把环境切到 prod，或按 Symfony Mailer 的方式单独测试 |
| 上传商品图片后前台显示不出来 | 媒体目录没有写权限 | 确认 `public/media`（以及 `var/cache`、`var/log`）对运行用户可写 |
| 在 Windows 命令行里安装到一半各种失败 | 官方支持的环境是 macOS / Linux 与 WSL | 换到 WSL 或 Linux 环境里操作 |
| 依赖安装或安装器中途被内存打断 | PHP 进程可用内存不足 | 提高 PHP 的 `memory_limit` 后重试 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | Composer 拉取依赖、npm / yarn 拉取前端包；运行时向支付、配送、邮件等外部服务发起请求 |
| 读取文件 | 是 | 读取项目源码、`config/` 配置、`.env` / `.env.local`、`var/log` 日志 |
| 写入文件 | 是 | 写入 `var/cache`、`var/log`、`public/media` 上传媒体与前端构建产物 |
| 凭证 | 是 | 数据库连接串、邮件服务凭证、支付与配送网关密钥；这些必须由你自建并保管，不要提交进仓库 |
| 子进程 / 后台常驻 | 是 | 执行 `composer`、`npm`、`bin/console`、`make` 等命令；生产环境需要常驻的 Web 服务与消息队列消费者 |

## 触发场景

- 「用 Symfony 做一个电商网站」
- 「Sylius 怎么安装 / 装完后台进不去」
- 「Sylius 和别的电商框架比，适合复杂促销吗」
- 「目录促销不生效 / 异步任务没跑」
- 「bin/console sylius:install 报错怎么排查」
- 「Sylius 的 Docker 环境起不来，端口被占了」

## 能力边界

**覆盖**：

- 两条官方安装路径的完整命令序列：传统安装（建工程 → 构建前端 → 配数据库 → 安装器 → 起服务）与 Docker 路线（克隆 → `make init` → 访问）。
- 安装过程中每一步的实际作用、默认货币与默认语言这两个容易踩的隐含设定，以及如何提前改。
- 后台入口、管理员账号创建方式、fixtures 载入、异步消费者进程这些日常操作。
- 环境要求（PHP 版本与扩展、数据库版本、Node 版本、支持的系统）与常见故障的定位顺序。
- Docker 环境下的 `make` 快捷命令与端口冲突的处理办法。

**不覆盖**：

- 具体业务建模：自定义资源、状态机配置、支付与配送服务商的实现，这些要读官方 Customize / Extend 文档。
- 主题与前台模板的深度改造。
- 真实收款通道的开通、合同与合规。
- 生产部署拓扑（负载均衡、数据库高可用、对象存储、备份）与性能调优。
- 具体版本的完整命令清单与选项——它们随版本变化，以 `bin/console list` 和官方文档为准。
- 任何性能指标与并发能力的承诺。

## 依赖条件

- 类 Unix 环境：macOS / Linux，或 Windows 下的 WSL
- PHP 8.2+，扩展：`gd`、`exif`、`fileinfo`、`intl`、`sodium`
- Composer
- 数据库之一：MySQL 8.0+、MariaDB 10.4.10+、PostgreSQL 13.9+
- Node.js ^20 或 ^22
- Git
- 可写的 `var/cache`、`var/log`、`public/media` 目录
- 走 Docker 路线时：Docker 与 `make`
- 生产环境：常驻的 Web 服务与消息队列消费者（建议 Supervisor 守护）

## 已知限制

- 框架版本与 Symfony 版本强耦合，升级前必须先确认兼容矩阵，否则会出现组件版本冲突。
- 安装器的默认货币（USD）与默认语言（English - US）会影响价格在库中的存储方式，后期改动成本不低，最好开始就定好。
- 邮件投递在非 prod 环境默认关闭，容易误判为配置错误。
- 目录促销等功能依赖异步消费者进程，没有守护进程时会表现为"功能没生效"。
- Docker 路线的默认端口固定，宿主机上已有 Nginx / MySQL 时必然冲突，需要改映射。
- 本文不锁定具体命令选项与版本号，这些以官方文档与 `bin/console` 的实际输出为准。

## 自检清单

执行前：

- [ ] `php -v` 是否 >= 8.2，扩展 `gd` / `exif` / `fileinfo` / `intl` / `sodium` 是否齐全。
- [ ] 数据库版本是否满足要求，账号是否有建库建表权限。
- [ ] `node -v` 是否在 ^20 或 ^22 范围内。
- [ ] `var/cache`、`var/log`、`public/media` 是否可写。
- [ ] 走 Docker 路线时，80 / 3306 / 8025 是否已被本机服务占用（`lsof -i :80`）。
- [ ] 是否已决定默认货币与默认语言（需要就先改 `config/services.yaml` 再安装）。

执行后：

- [ ] `bin/console sylius:install` 是否完整跑完全部步骤。
- [ ] `symfony server:start` 后能否在 `https://127.0.0.1:8000` 打开店铺前台。
- [ ] `/admin` 能否用安装时提供的凭证登录。
- [ ] 若需要演示数据，`bin/console sylius:fixtures:load default` 是否成功。
- [ ] 异步功能是否需要常驻进程，`messenger:consume` 是否已按需启动并纳入守护。
- [ ] 生产环境的 `MAILER_DSN` 是否已配置（非 prod 环境默认不投递，别误判）。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/Sylius/Sylius | 上游仓库（安装与完整文档以它为准） |
| https://docs.sylius.com/public/getting-started/sylius-ce-installation | 不用 Docker 的安装步骤 |
| https://docs.sylius.com/public/getting-started/sylius-ce-installation-with-docker | Docker 安装步骤与 make 命令清单 |

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
