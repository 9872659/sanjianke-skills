# 三剪客 · 小程序商城全栈系统 Skill

litemall：小程序商城全栈系统 的安装、常用命令与避坑要点

---

## 前置条件

- **MySQL**：本机可连的实例，脚本默认连 `localhost:3306`，库名 `litemall`。
- **JDK 1.8 或以上**、**Maven**：用于构建并启动后端聚合包。
- **Node.js**：用于管理后台与移动端两个 Vue 前端。
- **微信开发者工具**：用于调试小程序端。
- 端口准备：后端 8080、管理后台开发服务 9527、移动端开发服务 6255 不要被占用。
- 首次构建需要能访问 Maven 与 npm 的仓库，网络受限时先配好镜像源。

---

## 使用

最短路径（四步走通）：

```bash
# 1) 按顺序导入数据库（顺序不能换）
mysql -u root -p < litemall-db/sql/litemall_schema.sql
mysql -u root -p < litemall-db/sql/litemall_table.sql
mysql -u root -p < litemall-db/sql/litemall_data.sql

# 2) 构建并启动后端（默认 8080）
mvn install
mvn clean package
java -Dfile.encoding=UTF-8 -jar litemall-all/target/litemall-all-0.1.0-exec.jar

# 3) 启动管理后台（http://localhost:9527）
cd litemall-admin
npm install --registry=https://registry.npm.taobao.org
npm run dev

# 4) 微信开发者工具导入 litemall-wx，勾选「不校验合法域名...」，点编译
```

小程序端要连的后端地址在 `litemall-wx/config/api.js`，本机开发用 `http://localhost:8080/wx/`，真机测试改成局域网 IP。更完整的命令与排障顺序见 `SKILL.md`。

---

## 依赖

- MySQL、JDK 1.8+、Maven、Node.js、微信开发者工具。
- 仓库自带 SQL 脚本（建库 / 建表 / 初始数据），无需额外准备数据文件。
- 后端是 Spring Boot 多模块工程，聚合启动包在 `litemall-all/target/` 下。
- 两个 Vue 前端（管理后台、移动端）各自有独立依赖，需要分别 `npm install`。
- 微信登录与微信支付功能需要自己的小程序账号与商户配置，模板不包含这部分凭据。

---

## 安全

- 不内嵌任何密钥；但示例数据库口令（`litemall` / `litemall123456`）是公开的，任何对外可达的环境必须立刻改掉。
- 初始数据里带有示例后台账号，上线前必须换掉并建立自己的权限体系。
- 商品图片上传目录不要放在临时路径，避免重启丢数据；生产环境建议改用对象存储。
- 上游明确声明本项目仅用于学习练习、仍处在开发中、不承担任何使用后果；不要直接用它承载真实交易。
- 后端接口默认没有面向公网的防护，暴露到公网前需自行加鉴权、限流、HTTPS 与访问日志。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`litemall`
- 仓库：https://github.com/linlinjava/litemall

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
