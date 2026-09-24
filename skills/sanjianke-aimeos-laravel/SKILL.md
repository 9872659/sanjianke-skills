---
name: sanjianke-aimeos-laravel
slug: sanjianke-aimeos-laravel
displayName: 三剪客 · Laravel 电商套件
description: "aimeos-laravel：Laravel 电商套件 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "aimeos-laravel：Laravel 电商套件 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · Laravel 电商套件

`aimeos-laravel` 是给 Laravel 应用加一整套电商能力的方式：商品目录、购物车、结算、订单、支付与配送服务、优惠券、多语言多站点后台，以及面向单页应用和移动端的 JSON REST API 与管理端的 GraphQL API。它替你解决的问题是"我已有的 Laravel 站点要长出商城，而不是把商城重写一遍"——装进去、跑一次初始化、建一个管理员账号，前后台就都有了。

**上游项目**：`aimeos-laravel`　**仓库**：https://github.com/aimeos/aimeos-laravel

## 什么时候用 / 不用

**用它**：

- 你手上已经是一个 Laravel 应用，要往里加商品、购物车、结算、订单这些商城能力，而不想另起一个系统。
- 你要前后端分离：前台自己用 Vue / React 写，后台用现成的管理端，靠 JSON REST API 与 GraphQL API 对接。
- 你要做多语言、多货币、多站点甚至多商户的商城，需要一个已经把这些概念做进数据模型的基座。
- 你要从零起一个独立的 Laravel 商城项目，用官方发行包一条命令拿到含演示数据的完整站点。
- 你在选型阶段，想判断"这套电商模型能不能承载我们复杂的商品类型（组合、虚拟、订阅、阶梯价）"。

**不要用它**：

- 你的技术栈不是 PHP / Laravel。它是一个 Laravel 包，脱离 Laravel 就没有意义。
- 你只要一个简单的产品展示页或静态下单表单，引入整套电商框架会带来远超需求的复杂度。
- 你的环境没有 Composer、没有可写的数据库、也没法配置定时任务——初始化、后台和定时作业都依赖这些。
- 你要的是"装完就能对外收单"的成品商城：支付与配送服务需要你自己配置并接上真实网关，默认不带可用收款通道。
- 你的数据库是 SQLite：这个项目不支持 SQLite。
- 你只需要一个后台管理界面而不需要电商业务逻辑。

## 安装

前置要求（取自官方发行包说明）：

- Linux / Unix、WAMP / XAMPP 或 macOS 环境
- **PHP >= 8.2**（发行包要求；包本身要求 PHP >= 8.1），以及必需的 PHP 扩展——缺哪个 Composer 会直接告诉你
- 数据库：MySQL >= 5.7.8、MariaDB >= 10.2.2、PostgreSQL 9.6+ 或 SQL Server 2019+ 之一，**不支持 SQLite**
- **Composer 2.2+**
- 一个已有的 Laravel 应用（走"包接入"路径时），框架版本需在包支持的范围内

**A. 起一个独立的商城项目（最快路径）**

```bash
wget https://getcomposer.org/download/latest-stable/composer.phar -O composer
php composer create-project aimeos/aimeos myshop
```

安装过程会交互式询问数据库与邮件服务器参数，以及用于创建管理账号的邮箱和密码。

```bash
cd myshop
php artisan serve
```

- 前台：http://127.0.0.1:8000
- 后台：http://127.0.0.1:8000/admin

**B. 把电商能力加进已有的 Laravel 应用**

官方给出的方式是在 `composer.json` 里加依赖并执行更新，而不是一条 `require` 命令：

- 在 `require` 中加上 `"aimeos/aimeos-laravel": "~2025.10"`（版本约束以官方 README 当前内容为准）
- 按官方说明补上 `prefer-stable`、`minimum-stability` 与 `post-update-cmd` 脚本（其中包括发布资源与执行 Aimeos 的 Composer 脚本）
- 然后执行：

```bash
php composer update -W
```

装完之后按顺序执行这三步，把配置、数据表与基础数据都准备好：

```bash
php artisan vendor:publish --tag=config --tag=public
php artisan migrate
php artisan aimeos:setup
```

`aimeos:setup` 的实际参数形态是 `aimeos:setup {site?} {tplsite=default} {--q} {--v=v} {--option=*}`：

- 想要演示数据：`php artisan aimeos:setup --option=setup/default/demo:1`
- **生产环境不要带 `--option` 的演示数据开关**
- 多站点：`php artisan aimeos:setup <站点代码> [<模板站点>]`，模板站点可选 `default` / `unittest` / `unitperf`
- 具体选项以 `php artisan aimeos:setup --help` 为准

**C. 数据库与 .env 配置**

```bash
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=your_database
DB_USERNAME=your_user
DB_PASSWORD=your_password
```

- `APP_URL` 必须设置正确，否则商品图片等资源会取不到。
- 购物车依赖会话，**`SESSION_DRIVER` 必须是 `file`**。
- 如果 `.env` 方式读不到数据库配置，可以改为在 `config/shop.php` 的 resource/db 段里直接配置。

**D. 生产部署的两个硬性动作**

1. 虚拟主机的 document root 必须指向项目的 `public/` 目录。
2. 修改 `.env` 里的 `APP_URL`，写不带端口号的域名。

## 常用操作

**1. 初始化 / 重新初始化数据结构**

```bash
php artisan aimeos:setup
```

带演示数据（仅限非生产环境）：

```bash
php artisan aimeos:setup --option=setup/default/demo:1
```

**升级时必须对每一个站点都重跑一次**，否则可能有必需记录缺失、已有数据不被迁移。

**2. 创建管理员账号**

```bash
php artisan aimeos:account --super <email>
```

该命令的实际签名是 `aimeos:account {email?} {site?} {--password=} {--super} {--admin} {--editor}`：邮箱是位置参数，`--super` 是标志位，随后会提示输入密码。项目**没有默认管理员口令**，账号必须自己建。

**3. 跑定时作业**

定时作业用 `aimeos:jobs` 驱动，官方给出三条 crontab 条目（路径按实际项目改）：

```bash
* * * * * php /path/to/artisan aimeos:jobs "order/export/csv order/email/delivery order/email/payment order/email/voucher order/service/delivery subscription/export/csv customer/email/account"
30 * * * * php /path/to/artisan aimeos:jobs "customer/email/watch order/cleanup/unfinished order/service/async order/service/payment"
0 1 * * * php /path/to/artisan aimeos:jobs "admin/cache admin/log basket/cleanup catalog/export/sitemap catalog/import/csv order/cleanup/unfinished order/cleanup/unpaid order/service/transfer product/import/csv product/bought index/rebuild index/optimize product/export/sitemap subscription/process/begin subscription/process/renew subscription/process/end"
```

**4. 清缓存**

```bash
php artisan aimeos:clear
```

升级流程里通常还会配合：

```bash
php artisan route:clear
php artisan view:clear
```

**5. 发布资源**

```bash
php artisan vendor:publish --tag=config --tag=public
```

**6. 后台与前台入口**

- 后台固定在 `/admin`（本地：http://127.0.0.1:8000/admin ）
- 前台商品搜索等页面在 `/shop/...` 路径下

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 商品图片、样式都取不到 | `APP_URL` 没配对，或 document root 没指向 `public/` | 改 `.env` 里的 `APP_URL`；把虚拟主机根目录指到 `public/` |
| 购物车加了商品就丢 | 会话驱动不是文件驱动 | 把 `SESSION_DRIVER` 设为 `file` |
| 建表时报 `Specified key was too long; max key length is 767 bytes` | MySQL 版本低于 5.7.8，或字符集/排序规则不对 | 升级数据库到满足要求的版本；使用 `utf8` 字符集与 `utf8_unicode_ci` 排序规则建库 |
| 外键约束不生效、数据出现孤儿记录 | 表引擎用了 MyISAM | 改用 InnoDB |
| 静态资源 404、发布资源失败 | `public/` 目录不可写 | 确保 `public/` 可写，必要时手动创建 `public/aimeos` 与 `public/vendor` 目录并给写权限 |
| 登录成功却进不了后台 | 当前会话已经是另一个非管理员账号，Laravel 不会自动切换 | 先退出登录，再重新打开 `/admin` |
| 换了数据库后满屏表不存在 | 新库上没重新初始化 | 在新库上重新执行 `php artisan vendor:publish` → `migrate` → `aimeos:setup` 三步 |
| 升级大版本后功能异常或数据没迁移 | 升级需要对每个站点重跑初始化 | 逐站点执行 `php artisan aimeos:setup <站点代码>`，并配合清理路由、视图与 Aimeos 缓存 |
| 订单邮件、清理、导入索引这些作业从不执行 | 没配 crontab | 按上面三条 `aimeos:jobs` 条目配置计划任务 |
| 想清 Aimeos 缓存却找不到对应命令 | 当前版本只有清理命令，没有单独的缓存命令 | 用 `php artisan aimeos:clear`；命令清单以 `php artisan list` 的实际输出为准 |
| `.env` 里的数据库配置不生效 | 配置读取路径与预期不一致 | 改为在 `config/shop.php` 的 resource/db 段配置数据库连接 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | Composer 拉取依赖包；前台结算与后台管理需要对接支付、配送等外部服务 |
| 读取文件 | 是 | 读取 Laravel 项目源码、`.env`、`config/shop.php`、Composer 配置与缓存目录 |
| 写入文件 | 是 | 写入 `vendor/`、`public/aimeos`、`public/vendor`、缓存与日志目录、上传的商品媒体文件 |
| 凭证 | 是 | 数据库账号密码、邮件服务器账号、支付与配送网关密钥；这些必须由你自建并保管，不要提交进仓库 |
| 子进程 / 后台常驻 | 是 | 执行 `composer`、`php artisan` 等命令；生产环境需要一个常驻的 Web 服务进程，以及 crontab 定时调度 |

## 触发场景

- 「给我的 Laravel 项目加一个商城」
- 「aimeos 怎么安装 / 装完后台进不去」
- 「Laravel 电商包怎么做前后端分离」
- 「要支持多语言 / 多商户的 Laravel 商城选型」
- 「商品图不显示 / 购物车丢数据怎么排查」
- 「aimeos 的定时任务怎么配、aimeos:setup 什么时候要重跑」

## 能力边界

**覆盖**：

- 两种接入方式：独立起一个商城项目，或把电商包加进已有 Laravel 应用（含官方的 composer.json 改法与后续三步初始化）。
- 安装前置条件、数据库配置项、初始化命令的真实参数形态、后台与前台入口、生产部署必改的两项配置。
- 三个定时作业条目的实际内容与创建管理员账号的命令签名。
- 多语言多站点、多商户、多货币这些能力的存在与数据模型层面的支持。
- 常见故障的定位顺序：扩展 → 数据库版本与引擎 → `APP_URL` 与 document root → 会话驱动 → 目录权限 → 初始化与升级。

**不覆盖**：

- 具体业务定制：主题改造、结算流程改写、自定义商品类型与定价规则，这些要读官方 Customize / Extend 文档。
- 支付与配送服务商的开通、合同与真实收款通道联调。
- 多语言多站点、多商户这些开关在 `.env` 中的具体项名与配置步骤（本文不锁定，避免给错参数）。
- 服务器运维：PHP-FPM、Nginx、数据库调优、证书与备份。
- 具体版本的依赖清单与完整命令选项——以官方文档与 `php artisan list` / `--help` 为准。
- 任何性能指标与并发能力的承诺。

## 依赖条件

- PHP >= 8.2（发行包要求）与所需扩展
- Composer 2.2+
- MySQL >= 5.7.8 / MariaDB >= 10.2.2 / PostgreSQL 9.6+ / SQL Server 2019+ 之一（不支持 SQLite）
- Laravel 框架（作为包接入已有应用时需落在包支持的版本区间内）
- Apache / Nginx 等 Web 服务器，document root 指向 `public/`
- 会话驱动设为 `file`
- 可写的 `public/`、缓存与日志目录
- 生产环境需要 crontab 定时调度

## 已知限制

- 包与 Laravel 框架版本强绑定，升级任一方都要先确认兼容矩阵。
- 不支持 SQLite，本地开发也要准备 MySQL / MariaDB / PostgreSQL 之一。
- 后台与前台模板体系自成一套，深度定制需要先理解它的目录结构。
- 没有默认管理员账号口令，每次部署都要自己创建。
- 定时作业必须由 crontab 驱动，不配就会表现为"邮件、清理、索引都不工作"。
- 具体命令选项与可用支付配送服务列表会随版本变化，本文不锁定这些细节。

## 自检清单

执行前：

- [ ] `php -v` 是否满足版本要求，`composer --version` 是否 >= 2.2。
- [ ] 数据库是否满足版本要求、账号是否有建表权限、库的字符集与引擎是否正确（utf8 / InnoDB）。
- [ ] `.env` 的 `APP_URL`、数据库连接项是否已配置；`SESSION_DRIVER` 是否为 `file`。
- [ ] Web 服务器的 document root 是否指向 `public/`，该目录是否可写。

执行后：

- [ ] `vendor:publish` → `migrate` → `aimeos:setup` 三步是否都成功。
- [ ] 前台首页能否打开，商品图片是否正常加载。
- [ ] 是否已用 `php artisan aimeos:account --super <email>` 建好管理员账号，且 `/admin` 能登录。
- [ ] 购物车加商品后是否还在（验证会话驱动）。
- [ ] 生产环境的 crontab 是否已按三条 `aimeos:jobs` 条目配置。
- [ ] 非生产环境没有再带演示数据开关；升级后是否已对每个站点重跑初始化。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/aimeos/aimeos-laravel | 上游仓库（安装与完整文档以它为准） |
| https://aimeos.org/docs/latest/laravel/setup/ | 安装、升级与计划任务的官方说明 |

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
