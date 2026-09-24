# 三剪客 · 开源跨境电商独立站系统 Skill

bagisto：开源跨境电商独立站系统 的安装、常用命令与避坑要点

---

## 前置条件

- 走 Composer 方式：本机有 **PHP 8.3 或 8.4**（8.5 及以上暂不支持）、**Composer 2.5+**、**MySQL 8.0.32+**，并事先建好一个空库和账号。
- 走 Docker 方式：本机装好 Docker；镜像里数据库、PHP、Web 服务器都是自带的，不需要另外装。
- Web 服务器（Apache / Nginx）的站点根目录要指向项目的 `public/` 目录；本地调试可直接用 `php artisan serve`。
- 准备一个域名和 HTTPS 证书（生产环境必需，容器本身只提供 HTTP，需要前面放反向代理）。
- 用内置 AI 内容/图片生成功能时，需要准备模型服务的 API Key。

---

## 使用

最短路径（Composer）：

```bash
composer create-project bagisto/bagisto my-bagisto-store
cd my-bagisto-store
php artisan bagisto:install     # 交互式：填数据库、建管理员
php artisan serve               # http://localhost:8000
```

最短路径（Docker，一条命令得到一个装好种子数据的商店）：

```bash
docker run -d --name bagisto -p 80:80 webkul/bagisto:latest
```

后台入口 `/admin/login`，默认账号 `admin@example.com` / `admin123`——登录后第一件事就是改密码。完整的部署方式、常用命令与排障顺序见 `SKILL.md`。

---

## 依赖

- PHP 8.3 / 8.4 + 常用扩展（由官方安装文档列出），Composer 2.5+。
- MySQL 8.0.32+（Docker 方式由镜像自带，也可改为外接数据库）。
- Redis / Elasticsearch 为可选组件：前者用于缓存与队列，后者用于搜索；不接也能跑。
- 前端资源构建依赖 Node.js（改主题时需要）。
- 运行期依赖：Web 服务器 + 数据库 + 可写目录 `storage/`、`bootstrap/cache/`。

---

## 安全

- 不内嵌任何密钥；数据库密码、支付与物流密钥、模型服务 API Key 全部放 `.env`，不提交到版本库。
- 默认管理员凭据是公开的，上线前必须修改，并考虑改掉默认的后台路径。
- 容器只监听 HTTP，公网部署请在前面用反向代理终止 SSL，并给 `APP_URL` 填真实 HTTPS 地址。
- 数据库端口不要暴露到公网；自托管意味着补丁要及时跟、备份要定期做并验证可恢复。
- 商品图与用户上传文件属于业务数据，删除容器前先确认数据卷已备份。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`bagisto`
- 仓库：https://github.com/bagisto/bagisto

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
