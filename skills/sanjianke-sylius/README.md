# 三剪客 · 开源电商平台 Skill

Sylius：开源电商平台 的安装、常用命令与避坑要点

---

## 前置条件

- 类 Unix 环境：**macOS / Linux**，或 Windows 下的 **WSL**（官方给出的支持环境）。
- **PHP 8.2+**，且以下扩展齐全：`gd`、`exif`、`fileinfo`、`intl`、`sodium`。缺少扩展在 `sylius:install` 的环境检查步骤就会被拦下。
- **Composer**。
- 数据库之一：**MySQL 8.0+**、**MariaDB 10.4.10+**、**PostgreSQL 13.9+**。
- **Node.js ^20 或 ^22**，用于构建前端资源。构建必须在安装器之前完成。
- **Git**。
- 可写的 `var/cache`、`var/log`、`public/media` 目录。
- 走 Docker 路线时还需要 **Docker** 与 **make**。
- 不需要第三方大模型或算力服务。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

**最短跑通路径（不用 Docker）**

```bash
composer create-project sylius/sylius-standard AcmeStore
cd AcmeStore

# 前端资源必须先构建，安装器里有一步依赖它
npm install
npm run build
# 或者：yarn install && yarn build

# 配置数据库连接，写进 .env.local
# DATABASE_URL=mysql://<username>:<password>@<host>/<your_database_name>_%kernel.environment%?serverVersion=<your_db_version>&charset=utf8

# 交互式安装：检查环境 → 建库建表 → 是否导入演示数据 → 基础店铺配置 → 生成 API 令牌 → 安装资源
bin/console sylius:install

# 起本地服务
symfony server:start
```

浏览器访问 `https://127.0.0.1:8000`，后台在 `/admin`，用安装过程中你提供的凭证登录。

**Docker 路线**

```bash
git clone git@github.com:Sylius/Sylius-Standard.git your_project_name
cd your_project_name
make init
open http://localhost/
```

常用快捷命令：`make up` / `make down` / `make clean` / `make install` / `make php-shell` / `make node-shell` / `make node-watch` / `make docker-compose-check`。

**日常操作**

```bash
bin/console sylius:fixtures:load default      # 载入默认测试数据
bin/console sylius:fixtures:list              # 查看可用的 fixtures 套件
bin/console sylius:admin-user:create          # 交互式新建管理员（不接受非交互调用）
php bin/console messenger:consume main        # 跑异步任务，目录促销等功能依赖它
```

**两个容易忽略的隐含设定**

- 安装器默认货币是 **USD**、默认语言是 **English - US**，且价格会以该货币的整数形式入库。想改就在安装前于 `config/services.yaml` 里设置 `locale` 与 `sylius_installer_currency`，装完也可以在后台 Configuration > Channels 改。
- 邮件在 **test / dev / staging 环境默认不投递**，只有 prod 默认开启。配 `MAILER_DSN` 即可，别把"开发环境收不到邮件"当成故障。

具体子命令与选项以 `bin/console list sylius` 和官方文档为准。

---

## 依赖

- PHP 8.2+，扩展 `gd`、`exif`、`fileinfo`、`intl`、`sodium`
- Composer
- MySQL 8.0+ / MariaDB 10.4.10+ / PostgreSQL 13.9+
- Node.js ^20 或 ^22（构建前端资源）
- Git
- 可选：Docker 与 `make`（走 Docker 开发环境路线时必需）
- 运行期可选：Supervisor 之类的进程守护工具，用于常驻 `messenger:consume`

---

## 安全

- 不内嵌任何密钥
- 数据库连接串（`.env.local` 里的 `DATABASE_URL`）、邮件服务凭证、支付与配送网关密钥都属于敏感信息，不要提交进仓库
- **没有默认管理员账号**：管理员是你自己在安装过程中创建的，不要沿用任何示例口令
- `/admin` 是带完整管理权限的入口，公网部署前必须加访问控制与传输加密，不要直接暴露
- 邮件投递只在 prod 环境默认开启，上线前确认发信账号与收件行为符合预期，避免误发或泄露客户信息
- `public/media` 存放用户与运营上传的媒体文件，注意目录权限与文件类型校验，避免被当成可执行文件
- 消息消费者（`messenger:consume`）以服务进程身份长期运行，注意其运行账号的权限最小化
- 涉及消费者数据（订单、地址、邮箱）时，按适用的个人信息保护要求做脱敏、访问控制与留存策略

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Sylius`
- 仓库：https://github.com/Sylius/Sylius

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
