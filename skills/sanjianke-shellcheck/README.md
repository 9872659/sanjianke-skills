# 三剪客 · Shell 脚本静态检查 Skill

shellcheck：不运行脚本就能找出会咬人的写法——没加引号的变量、`[ ]` 与 `[[ ]]` 的坑、命令替换的单词拆分、`cd` 失败后继续往下跑

---

## 前置条件

- 目标脚本属于 Bourne 系方言（sh / bash / dash / ksh / busybox）；zsh、fish 等不在支持范围内
- 装好 shellcheck：走包管理器（apt / dnf / pacman / apk / brew）或官方 README 给出的其它入口；源码构建需要 GHC + Cabal 工具链
- 检查过程完全离线，不需要账号、Key 或网络
- 想省掉本地安装的话，需要可用的 Docker 环境来跑官方镜像
- 如果要用 `-x` 跟随 `source`，最好先确认那些被引用的文件在本地存在

---

## 使用

最短跑通路径：

```bash
shellcheck --version                    # 1. 确认装好并记下版本
shellcheck script.sh                    # 2. 检查一个脚本，看输出里的 SC#### 编号
echo 'echo $1' | shellcheck -           # 3. 快速试一段片段（- 表示从标准输入读）
echo $?                                 # 4. 看退出码：0 无问题，1 有问题
```

几个高频用法：

```bash
shellcheck -s bash lib/common.sh            # 没有 shebang 的脚本，显式指定方言
shellcheck -S warning scripts/*.sh          # 只关心 error 与 warning
shellcheck -x deploy.sh                     # 连 source 进来的文件一起看
shellcheck -e SC2086 script.sh              # 排除某条规则
shellcheck -f json1 scripts/*.sh            # 结构化输出，喂给 CI 或看板
shellcheck -f diff script.sh | git apply    # 生成补丁，审查后应用
```

排错顺序：报 `SC1091` → 加 `-x`；报 `SC1090` → 用 `# shellcheck source=...` 指令指明文件；一堆不相干的告警 → 先确认方言是不是推断错了（加 `-s`）；本地与 CI 结论不一致 → 检查 `.shellcheckrc` 与 `SHELLCHECK_OPTS`。

---

## 依赖

- **运行环境**：Windows / macOS / Linux，官方提供各架构预编译二进制
- **安装途径**：apt / dnf / pacman / apk / brew 等包管理器，或 Cabal 从源码构建（Haskell 工具链，编译阶段内存占用不小）
- **容器方式**：官方镜像可直接 `docker run`，适合不想本地安装的场景
- **无外部服务依赖**：不需要网络、账号或 API Key
- **配置文件**：按"脚本目录逐级向上 → 家目录兜底"的顺序查找 `.shellcheckrc` 或 `shellcheckrc`，只用找到的第一个；Windows 上家目录位置是 `%APPDATA%/shellcheckrc`
- **环境变量**：`SHELLCHECK_OPTS` 可预设默认参数，会按空格切分后追加到每次调用的命令行
- **语言**：输出目前仅有英文；文件按 UTF-8 宽松解码，非法字节序列回退 ISO-8859-1

---

## 安全

- 不内嵌任何密钥：本 Skill 不包含账号、token 或任何凭据
- **只读且不执行**：shellcheck 不会运行被检查的脚本、不启动子进程、不写任何文件，输出只到标准输出
- **读取范围会扩大**：开启 `-x`（`--external-sources`）后，它会跟随脚本里的 `source` 去打开任意文件；官方说明这项默认关闭，正是因为该项目最初是给"检查不受信任脚本"的在线服务用的，正常本地开发可以放心打开，但不要在来源不明的脚本上无条件开启
- **`-f diff` 只是生成补丁**：真正改动文件的是你后续执行的 `git apply` / `patch`，应用前务必人工审查补丁内容
- **CI 里要区分退出码**：1 表示"扫描完成但发现问题"，2/3/4 表示流程本身坏了（文件读不到、调用语法错、选项错），不要把两类混成同一个失败信号
- **Docker 场景注意挂载**：容器里只能看到挂载进去的文件，所以家目录下的配置文件不会被读取，需要显式把配置一起挂进去或改用 `--rcfile`

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`shellcheck`
- 仓库：https://github.com/koalaman/shellcheck

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
