# 三剪客 · 云存储搬运与同步 Skill

rclone：云存储搬运与同步 的安装、常用命令与避坑要点

---

## 前置条件

- 至少一个可用的远端（云盘、对象存储、另一台机器的 SFTP/WebDAV 端点等），以及该远端对应的访问凭证。
- 网络能访问该远端端点；内网自建对象存储要保证端点从执行机器可达。
- 本地缓存/临时目录有足够空间：同步、加密上传与挂载都会用到。
- Windows 上若要用 `rclone mount`，需额外安装文件系统驱动（如 WinFsp），否则挂载不可用。
- 计划任务场景要确认：运行身份能读到配置文件，并且该身份有权限写日志与缓存目录。
- 无账号注册要求（凭证由你所连的服务商提供），也无需任何大模型 Key。

---

## 使用

最短跑通路径：

1. 安装并确认版本：

   ```bash
   rclone version
   ```

2. 配置一个远端（交互式，按问答填凭证）：

   ```bash
   rclone config
   ```

   配好后确认配置与缓存位置：

   ```bash
   rclone config file
   rclone config paths
   ```

3. 验证连通与列表：

   ```bash
   rclone lsd myremote:
   rclone ls myremote:some/path
   ```

4. 先做**不会删东西**的搬运（本地 → 远端）：

   ```bash
   rclone copy ./local-dir myremote:backup/local-dir -P
   ```

5. 确实需要镜像语义时，先空跑看删除清单：

   ```bash
   rclone sync ./local-dir myremote:mirror -P --dry-run
   ```

   确认清单无误后去掉 `--dry-run` 再执行。

6. 校验两端：

   ```bash
   rclone check ./local-dir myremote:mirror
   ```

7. 要挂载或做双向同步，先读官方文档对应章节再动手：

   ```bash
   rclone mount myremote: /mnt/mydata --vfs-cache-mode writes
   rclone bisync ./local-dir myremote:mirror --resync --dry-run
   ```

命令与后端选项以 `rclone <子命令> --help` 和官方文档为准；后端能力不整齐，不要跨服务商照搬参数。

---

## 依赖

- **本体**：单一可执行文件，无额外运行时依赖；可用官方脚本、包管理器或预编译包安装。
- **远端凭证**：每个远端需要该服务的访问密钥或令牌；**加密远端（`crypt`）额外需要口令与盐值**。
- **挂载（可选）**：Linux/macOS 走系统 FUSE，Windows 需要 WinFsp 之类的驱动。
- **磁盘**：本地缓存与临时目录要有余量，大文件传输时占用明显。
- **网络**：连通各远端端点；被服务商限流会直接影响吞吐。
- **无模型、无 API Key 依赖**：纯文件搬运与同步，不涉及大模型调用或 GPU 算力。

---

## 安全

- 不内嵌任何密钥；所有凭证都由你自行配置。
- 配置文件里保存着**所有远端的访问凭证**（密码字段以混淆形式存储，混淆不等于加密）。不要让该文件进入版本库、镜像层或共享盘；默认权限应仅限本人可读。
- `crypt` 远端的口令与盐值是解密的唯一凭据：云端只有密文，丢了无法找回。配置完立刻单独备份，并确认备份本身也是安全的。
- 破坏性操作要预演：涉及 `sync` 与 `bisync` 时一律先加 `--dry-run`，逐条核对将删除/覆盖的清单。
- 方向写错等于删错盘：`sync 源 目标` 的顺序在脚本里要显式核对，避免变量拼错。
- 云端数据的合规与授权由你负责：搬运不改变内容的版权归属，也可能触发服务商的条款与配额限制。
- 挂载会把云端内容暴露为本机文件路径：注意该路径的访问权限，避免同机其他用户越权读取。
- 日志里可能包含文件名与远端路径，共享日志前先排敏。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`rclone`
- 仓库：https://github.com/rclone/rclone

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
