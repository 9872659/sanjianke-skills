# 三剪客 · 终端 Docker 管理面板 Skill

lazydocker：终端 Docker 管理面板 的安装、常用命令与避坑要点

---

## 前置条件

- 本机已安装 Docker，且当前用户有权限访问 Docker 守护进程（套接字权限 / 已加入 docker 组）。
- 使用 compose 相关功能需要安装 Compose（可选）。注意环境里到底是 `docker compose`（插件式）还是 `docker-compose`（独立二进制），决定后面配置怎么写。
- 需要在交互式终端里运行；它不是可以在脚本里无人值守执行的命令。
- 用容器方式运行它自己时，需要能把宿主机 `/var/run/docker.sock` 挂进去，并准备一个持久化配置目录。
- 从源码构建时需要对应的 Go 工具链；包管理器安装则不需要。
- 不需要任何账号、Token 或 API Key。

---

## 使用

最短跑通路径：

```sh
# 1) 安装（选一种）
brew install jesseduffield/lazydocker/lazydocker   # macOS / Linux
scoop install lazydocker                           # Windows
yay -S lazydocker                                  # Arch（AUR）

# 2) 确认宿主 Docker 可用
docker ps

# 3) 启动面板
lazydocker
```

面板里所有操作都是「选中对象 + 一次按键」，完整键位以仓库 `docs/` 下的键位文档和界面底部提示行为准。
命令名偏长，建议挂个别名：

```sh
echo "alias lzd='lazydocker'" >> ~/.zshrc
```

改配置：在面板里选中左上角 project 面板，按 `o` 打开配置（默认编辑器是 vim 时按 `e`）。
配置文件位置按平台不同：

```text
Linux:   ~/.config/lazydocker/config.yml
macOS:   ~/Library/Application Support/jesseduffield/lazydocker/config.yml
Windows: C:\Users\<User>\AppData\Roaming\lazydocker\config.yml
```

**改完必须关闭并重新打开 lazydocker 才生效。** 最常见的两处改动：

```yaml
# 日志默认只看最近一小时，看不到日志时先改这里
logs:
  since: ''      # '' 表示全部；也可写 '24h'
  tail: 200      # 只看最后 200 行

# 环境里用的是哪个 compose 命令，面板里所有 compose 动作都基于它
commandTemplates:
  dockerCompose: docker compose
```

自定义一条常用命令（例如一键进容器 shell）：

```yaml
customCommands:
  containers:
    - name: bash
      attach: true
      command: 'docker exec -it {{ .Container.ID }} bash'
      serviceNames: []
```

容器化运行（把宿主 Docker 套接字挂进去）：

```sh
docker run --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /yourpath:/.config/jesseduffield/lazydocker \
  lazyteam/lazydocker
```

`/yourpath` 换成你实际存放配置的目录。注意：在容器内运行时有已知缺陷，看不到日志与 CPU 占用。

更多配置项、模板变量与键位说明见 SKILL.md 与上游仓库文档。

---

## 依赖

- 运行期：本机 Docker（必需）；Compose（使用 compose 功能时必需）。
- 可选：Go 工具链（仅源码构建时需要）。
- 容器化运行：可访问宿主机 Docker 套接字的权限，以及一个配置持久化目录。
- 无第三方服务依赖，无需 API Key，运行期不主动联网（只与本机 Docker 守护进程通信）。

---

## 安全

- 不内嵌任何密钥。
- 通过挂载的 Docker 套接字与守护进程通信，继承宿主机 Docker 客户端的权限与认证上下文（包括已登录的镜像仓库凭据）。
- 对容器、镜像、卷的写操作（restart / down / rebuild / prune 等）会**真实生效**；`prune` 与 `down --volumes` 类操作会永久删除数据，执行前务必确认选中范围与备份。
- 容器化运行时把 `/var/run/docker.sock` 挂进容器，等于把宿主 Docker 的控制权交给该容器，请只使用自己构建或可信来源的镜像。
- 一键安装脚本来自网络，执行前建议先下载查看内容；`curl ... | bash` 这种形式本身就带着执行远端代码的风险。
- `config.yml` 里的 `commandTemplates` 与 `customCommands` 会被当作命令执行，不要粘贴来源不明的配置片段。
- 没有多用户权限隔离与审计日志：谁能在终端里跑它，谁就拥有当前 Docker 权限下的全部操作能力。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`lazydocker`
- 仓库：https://github.com/jesseduffield/lazydocker

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
