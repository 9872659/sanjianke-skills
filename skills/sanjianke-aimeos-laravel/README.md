# 三剪客 · Laravel 电商套件 Skill

aimeos-laravel：Laravel 电商套件 的安装、常用命令与避坑要点

---

## 前置条件

- **PHP >= 8.2**（官方发行包的要求；包本身最低 PHP 8.1），以及项目需要的 PHP 扩展——缺哪个扩展 Composer 会直接报出来。
- **Composer 2.2+**。没有的话可以先取官方安装器：

  ```bash
  wget https://getcomposer.org/download/latest-stable/composer.phar -O composer
  ```

- 数据库之一：**MySQL >= 5.7.8**、**MariaDB >= 10.2.2**、**PostgreSQL 9.6+**、**SQL Server 2019+**。**不支持 SQLite**。数据库账号需要建表权限，建议库用 `utf8` 字符集、表用 InnoDB 引擎。
- 运行环境：Linux / Unix、WAMP / XAMPP 或 macOS。
- Web 服务器：Apache、Nginx，测试时也可以直接用 PHP 自带的开发服务器。
- 虚拟主机的 **document root 必须指向项目的 `public/` 目录**，否则前台静态资源会全部取不到。
- 生产环境必须把 `.env` 里的 `APP_URL` 改成不带端口的正式域名；`APP_URL` 不对时商品图片也会取不到。
- 会话驱动必须是 `file`，否则购物车里的东西存不住。
- 作为包接入已有应用时，Laravel 框架版本需落在包支持的区间内。
- 不需要第三方大模型或算力服务。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短跑通路径（独立起一个商城项目）：

```bash
wget https://getcomposer.org/download/latest-stable/composer.phar -O composer
php composer create-project aimeos/aimeos myshop
cd myshop
php artisan serve
```

安装过程会交互式询问数据库与邮件服务器参数，以及用于创建管理账号的邮箱和密码。启动后：

- 前台：http://127.0.0.1:8000
- 后台：http://127.0.0.1:8000/admin

把电商能力加进**已有** Laravel 应用（官方方式是改 `composer.json` 后执行更新，不是一条 `require` 命令）：

1. 在 `require` 中加入 `"aimeos/aimeos-laravel": "~2025.10"`（版本约束以官方 README 当前内容为准）；
2. 按官方说明补齐 `prefer-stable`、`minimum-stability` 与 `post-update-cmd` 脚本；
3. 执行 `php composer update -W`；
4. 然后按顺序初始化：

```bash
php artisan vendor:publish --tag=config --tag=public
php artisan migrate
php artisan aimeos:setup
```

需要演示数据时（仅限非生产环境）：

```bash
php artisan aimeos:setup --option=setup/default/demo:1
```

创建管理员账号（没有默认口令，必须自己建）：

```bash
php artisan aimeos:account --super <email>
```

上线前必做：

```bash
# 1. Web 服务器 document root 指到 public/ 目录
# 2. .env 里改成不带端口的正式域名
APP_URL=http://myhostingdomain.com
# 3. 会话驱动用文件，否则购物车不落地
SESSION_DRIVER=file
```

生产环境的三个定时作业条目、升级时的注意事项，以及更细的定制（主题、结算流程、支付与配送服务），见 `SKILL.md` 与官方 Setup 文档。

---

## 依赖

- PHP >= 8.2 及项目所需扩展
- Composer 2.2+
- MySQL >= 5.7.8 / MariaDB >= 10.2.2 / PostgreSQL 9.6+ / SQL Server 2019+
- 已有的 Laravel 应用（仅"包接入"路径需要），版本需在包支持范围内
- Web 服务器（Apache / Nginx / PHP 自带开发服务器），document root 指向 `public/`
- 可写的 `public/`（含 `public/aimeos`、`public/vendor`）、缓存与日志目录
- 生产环境：crontab 定时调度

---

## 安全

- 不内嵌任何密钥
- 安装时创建的**管理员账号密码、数据库口令、邮件服务器账号**都属于敏感信息，不要提交进仓库，也不要写进示例配置
- `.env` 里保存数据库与邮件凭证，务必确保它不被版本控制收录，并限制文件权限
- 支付与配送网关的密钥同样只放在环境变量或密钥管理系统中
- 后台路径固定在 `/admin`，公网部署时建议再加一层访问控制，别让它裸奔
- 项目**不带默认管理员口令**，账号由你自行创建；也不要把演示数据导入生产环境
- 商品图片与用户上传内容会落盘（`public/` 下），注意上传目录的权限与文件类型校验，避免被当成可执行文件
- 定时作业会批量导出订单、发送客户邮件、做数据清理，配置前先确认收件人、导出目标与留存策略符合你的合规要求
- 涉及消费者数据（收货地址、订单、邮箱）时，按适用的个人信息保护要求做脱敏、访问控制与留存策略

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`aimeos-laravel`
- 仓库：https://github.com/aimeos/aimeos-laravel

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
