---
name: sanjianke-litemall
slug: sanjianke-litemall
displayName: 三剪客 · 小程序商城全栈系统
description: "litemall：小程序商城全栈系统 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "litemall：小程序商城全栈系统 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 电商
  - 运营
---

# 三剪客 · 小程序商城全栈系统

一个能整套下载下来跑通的小商城：**Spring Boot 后端 + Vue 管理后台 + 微信小程序前端 + Vue 移动端**四个部分放在同一个仓库里，数据库脚本也一起给了。适合想读完一整套电商代码、或者想拿它当自己项目的骨架来改的人和团队。

**上游项目**：`litemall`　**仓库**：https://github.com/linlinjava/litemall

## 什么时候用 / 不用

**用它**：

- 「我想拿一套完整的小程序商城源码来读，前后端都要有」——四端在同一仓库，接口、后台、前端能对着看。
- 「学生作业 / 内部练手项目，要能跑通的电商全栈」——数据库脚本、种子数据、登录页面都给全了。
- 「拿它当骨架，改出自己的商城」——Spring Boot 分层清楚，Vue 后台与小程序前端都可独立替换。
- 「公司内网做个简单的商品下单系统」——不需要接微信支付也能把商品、购物车、订单流程跑起来。
- 「我想看看电商系统的数据库该怎么设计」——建表脚本与初始数据都在版本库里，可以直接对照。

**不要用它**：

- 要直接面向消费者上线营业：作者明确写了本项目仅用于学习练习、仍处在开发中、不承担任何使用后果。
- 需要长期有人维护的商用系统：用一套声明「不完善」的学习项目承载真实交易，风险自负。
- 你的团队只写 Java 不想碰前端：小程序端与管理后台都在这个仓库里，绕不开 Node 与小程序构建。
- 需要多商户入驻、分账结算：这套是单商城的结构，多商户要自己从数据模型改起。
- 只是想要个静态商品页：上四端就是把运维成本乘以四。

## 安装

最小开发环境：**MySQL**、**JDK 1.8 或以上**、**Maven**、**Node.js**，以及调试小程序用的**微信开发者工具**。

第一步，导入数据库。按顺序导入 `litemall-db/sql/` 下的三个文件（顺序不能换）：

```bash
mysql -u root -p < litemall-db/sql/litemall_schema.sql   # 建库
mysql -u root -p < litemall-db/sql/litemall_table.sql    # 建表
mysql -u root -p < litemall-db/sql/litemall_data.sql     # 初始数据
```

默认连接信息写在 `litemall-db/src/main/resources/application-db.yml`：库名 `litemall`、账号 `litemall`、密码 `litemall123456`、端口 `3306`。这三项建议随脚本一起改成你自己的。

第二步，构建并启动后端（小商场接口与后台接口是同一个服务）：

```bash
mvn install
mvn clean package
java -Dfile.encoding=UTF-8 -jar litemall-all/target/litemall-all-0.1.0-exec.jar
```

后端默认监听 **8080**，小程序端接口前缀是 `/wx/`，管理后台接口前缀是 `/admin/`。

第三步，启动 Vue 管理后台，浏览器访问 `http://localhost:9527`：

```bash
cd litemall-admin
npm install --registry=https://registry.npm.taobao.org
npm run dev
```

第四步，用微信开发者工具导入小程序前端 `litemall-wx`（仓库里另有 `renard-wx` 可对比），在项目配置里勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」，点「编译」即可预览。小程序端要连的后端地址在 `litemall-wx/config/api.js`，默认是本机：

```js
// litemall-wx/config/api.js
var WxApiRoot = 'http://localhost:8080/wx/';       // 本机开发
// var WxApiRoot = 'http://192.168.1.3:8080/wx/';  // 局域网真机测试
```

第五步（可选），启动 Vue 移动端，浏览器用手机模式访问 `http://localhost:6255`：

```bash
cd litemall-vue
npm install --registry=https://registry.npm.taobao.org
npm run dev
```

注意：这里只是最简启动方式。小商城的微信登录、微信支付等功能需要开发者自行配置后才能运行；更详细的方案以项目文档为准。

## 常用操作

```bash
# 1) 一条命令构建整个多模块工程，并只启动聚合启动包
mvn -q install
java -Dfile.encoding=UTF-8 -jar litemall-all/target/litemall-all-0.1.0-exec.jar

# 2) 看后端是不是起来了（能看到 JSON 或错误响应就说明服务在）
curl -i http://localhost:8080/wx/home/index

# 3) 管理后台的开发模式（默认 9527，改端口看 vue.config.js）
cd litemall-admin && npm run dev

# 4) 管理后台打生产包（产物在 litemall-admin/dist）
cd litemall-admin && npm run build:prod

# 5) 小程序端换后端地址：改这里后重新编译
grep -n "WxApiRoot" litemall-wx/config/api.js

# 6) 数据库连接信息在哪（改账号密码、切环境都从这里入手）
grep -n "url:\|username:\|password:" litemall-db/src/main/resources/application-db.yml
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 启动报找不到表 / 字段 | 只导了建表脚本，或三个脚本没按顺序导 | 严格按 `litemall_schema.sql` → `litemall_table.sql` → `litemall_data.sql` 的顺序重新导入 |
| 连接数据库失败 | `.yml` 里的账号密码与你实际建的不是一套 | 要么把 `application-db.yml` 改成你自己的账号密码，要么按默认值 `litemall` / `litemall123456` 建好账号并授权 |
| 中文商品名变乱码 | 连接串字符集或启动参数不对 | 连接串保留 `useUnicode=true&characterEncoding=UTF-8`；启动 jar 时带 `-Dfile.encoding=UTF-8` |
| 导入数据时报时区或公钥相关错误 | JDBC 连接缺少时区与公钥参数 | 保持连接串里的 `serverTimezone=Asia/Shanghai` 与 `allowPublicKeyRetrieval=true` 不动 |
| `mvn install` 下载依赖极慢或失败 | 网络到中央仓库不稳 | 配国内 Maven 镜像源后重试，不要在同一个地址反复重试 |
| 后台页面能打开但接口全 404 | 后端没起，或后台请求的地址/代理与后端不一致 | 先确认 8080 上有服务，再看 `litemall-admin` 的接口地址与环境变量配置 |
| 小程序真机预览接口失败，或编译报「不合法的请求域名」 | 手机访问不到 `localhost`，域名也没加白名单；且没关域名校验 | 改成局域网 IP（如 `http://192.168.1.3:8080/wx/`）测试；在开发者工具「详情 → 本地设置」勾选「不校验合法域名、web-view、TLS 版本以及 HTTPS 证书」；发布前把域名加进服务器域名白名单并用 HTTPS |
| 后台登录密码不知道 | 示例账号随初始数据一起导入 | 从 `litemall_data.sql` 里的用户表查初始账号；生产使用必须改成自己的账号体系 |
| `npm install` 报证书过期或 404 | 用了已停服的旧 npm 镜像地址 | 换成当前可用的镜像源或官方源后重装 |
| 移动端页面打不开或报错 | 该模块作者标注仍处在开发阶段 | 把它当实验模块看待，不要依赖它的页面做验收 |
| 端口被占用导致起不来 | 8080 / 9527 / 6255 与本机其他服务冲突 | 改对应配置文件里的端口，或先停掉占用端口的进程 |
| 上传的商品图重启后没了 | 图片落在本地上传目录里 | 该目录不要放在临时路径，生产环境改用对象存储或挂载持久磁盘 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 申请 | Maven / npm 拉依赖，后端对外提供接口，小程序与管理后台访问后端 |
| 读取文件 | 申请 | 读取 SQL 脚本、Spring 配置文件、前端配置与日志，用于建库和排障 |
| 写入文件 | 申请 | 写入构建产物（`target/`、`dist/`）、日志、商品图片上传目录；导库会写入数据库 |
| 凭证 | 申请 | 数据库账号密码、后台管理员账号、微信 AppID 与支付参数；数据库口令随配置文件下发，换成自己的并限制访问 |
| 子进程 / 后台常驻 | 申请 | 需要常驻后端服务（8080）与两个前端开发服务，并调用 `mvn`、`java`、`npm`、`mysql` 等命令 |

## 触发场景

- 「有没有一套完整的小程序商城源码，前后端都带」
- 「litemall 怎么跑起来，先跑哪一步」
- 「数据库三个 sql 文件要按什么顺序导」
- 「后台端口是多少，登录账号在哪」
- 「小程序端怎么改后端地址」
- 「这套能不能直接上线商用」

## 能力边界

**覆盖**：

- 从导入数据库到四端各自启动的完整顺序，以及每一步的默认端口与接口前缀。
- 数据库连接、字符集、上传目录这些容易踩的环境配置在哪改。
- 常见故障的定位顺序（导库顺序 → 数据库连接 → 后端是否在跑 → 前端接口地址 → 域名校验）。
- 作为学习骨架的取舍判断：哪些模块可以放心改，哪些模块上游自己都标注为不稳定。

**不覆盖**：

- 微信登录、微信支付的开通、签约、证书配置与对账。
- 生产级部署：反向代理、HTTPS、容器化、监控告警、容量规划。
- 商品、订单、促销等业务运营动作与数据治理。
- 多商户入驻、分账结算一类需要在数据模型层重构的改造。

## 依赖条件

- MySQL（脚本默认连 `localhost:3306`，库名 `litemall`）、JDK **1.8 或以上**、Maven、Node.js。
- 微信开发者工具（调试小程序端）。
- 后端默认占用 **8080**，管理后台开发服务默认 **9527**，移动端开发服务默认 **6255**。
- 微信登录与微信支付相关功能需要自己的小程序账号与商户配置。
- 首次构建需要能访问 Maven 与 npm 的仓库（网络受限时需配镜像）。

## 已知限制

- 上游 README 明确声明本项目仅用于学习练习、仍处在开发中、不承担任何使用后果——不要直接承载真实交易。
- 四个模块版本与依赖会随上游演进，端口、默认口令等以仓库当前配置文件为准。
- 小程序端的微信登录、微信支付等功能必须开发者自行配置后才可用。
- 移动端（Vue）模块上游自己标注功能不稳定、处于开发阶段。
- 本 Skill 不提供从旧版本升级的迁移脚本，也不保证与上游各版本的库结构一致。

## 自检清单

- 动手前：确认 MySQL / JDK 1.8+ / Maven / Node.js 都在；确认这台机器跑的是学习演示还是真实业务——后者要先想清楚风险。
- 导库后必查：三个脚本按顺序导入无报错；连接信息与 `application-db.yml` 对得上；中文不乱码。
- 启动后必查：`http://localhost:8080/wx/home/index` 有响应；管理后台能打开并登录；小程序编译无报错且首页有商品数据。
- 改配置后必查：改了后端地址要同步 `litemall-wx/config/api.js`；改了后台端口要同步前端请求配置。
- 对外暴露前必做：换掉默认数据库口令与后台账号、给上传目录配持久化、按需要加 HTTPS 与访问控制。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/linlinjava/litemall | 上游仓库（安装与完整文档以它为准） |

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
