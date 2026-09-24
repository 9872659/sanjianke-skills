# 三剪客 · hyperfine 命令行基准测试 Skill

把「哪个写法更快」变成可复现的数字：多轮执行、统计分析、离群值检测、多命令对比与结果导出。

---

## 前置条件

- 能装二进制的机器；各主流包管理器与 Homebrew 均已收录
- 要被测量的命令能在本机正常执行
- **被测命令不能有副作用**：它会被真实执行很多轮，删除、写入、发请求都会重复发生
- 不需要账号、API Key 或联网

---

## 使用

最短跑通路径：

```bash
brew install hyperfine            # 或使用你的发行版包管理器安装 hyperfine 包
hyperfine --version

# 单命令基准测试
hyperfine 'find . -name todo.txt'

# 多命令对比 + 预热 + 命名
hyperfine --warmup 3 -n 'with cache' 'cmd --cache' -n 'no cache' 'cmd --no-cache'

# 参数扫描
hyperfine -P threads 1 8 'make -j {threads}'

# 导出结果
hyperfine --export-json result.json 'cmd-a' 'cmd-b'
```

关键提醒：换 shell 用 `-S`（`--shell`），`-s` 是 `--setup`；不要 shell 用 `-N`。

`SKILL.md` 里有四条钩子（`--setup` / `--prepare` / `--conclude` / `--cleanup`）的语义差别、参数扫描与参数列表的用法、输出重定向对测量结果的影响，以及常见坑对照表。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| 运行时 | 无。单个二进制，不需要额外运行时 |
| 安装方式 | Homebrew、MacPorts、nix、Chocolatey、Scoop，以及各 Linux 发行版仓库（Debian/Ubuntu 侧源码包名为 `rust-hyperfine`，二进制包名 `hyperfine`） |
| shell | 默认经由系统 shell 执行被测命令；也可用 `--shell` 指定，或用 `-N` / `--shell=none` 完全绕过 shell |
| 网络 | 不需要（除非被测命令自己联网） |
| 凭证 | 不需要 |

---

## 安全

- 不内嵌任何密钥，也不收集任何数据
- **被测命令会被真实、反复执行**：带副作用的命令（删文件、写数据库、调接口、发消息）会重复产生实际效果，先确认命令是幂等或安全的再开测
- 参数扫描会把命令跑很多遍，避免用它去压真实线上服务或触发计费接口
- 导出文件（`--export-json` 等）可能包含完整的命令原文，分享前留意是否含有敏感路径或内部地址
- 测量本身会占用 CPU 与磁盘，在生产机器上跑长轮次测试前先确认不影响他人

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`hyperfine`
- 仓库：https://github.com/sharkdp/hyperfine

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
