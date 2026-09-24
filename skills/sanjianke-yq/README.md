# 三剪客 · YAML 命令行处理 Skill

yq：YAML 命令行处理 的安装、常用命令与避坑要点

---

## 前置条件

- 先确认要处理的是**结构化配置文件**（YAML / JSON / XML / INI / props / CSV 等），不是随意文本。正文类文件不要用这个工具。
- 先确认本机装的是哪一个同名实现：`yq --version`。市面上存在语法不互通的其它同名实现，老文章里的 `yq r` / `yq w` 写法在新版上会直接报错。
- 用预编译二进制或包管理器安装：不需要任何运行时。
- 用 `go install github.com/mikefarah/yq/v4@latest` 安装：需要可用的 Go 工具链。
- 用容器方式运行：需要 Docker 或 Podman，并且要挂载工作目录。
- 计划用 `-i` 原地改文件时，**先确认这些文件已纳入版本控制或有备份**。

## 使用

最短跑通路径：

```bash
# 1) 装（按自己的平台选一条）
brew install yq                                        # macOS / Linuxbrew
winget install --id MikeFarah.yq                       # Windows
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && chmod +x /usr/local/bin/yq

# 2) 先只读地看一眼字段，确认路径写对了
yq '.a.b[0].c' file.yaml

# 3) 确认无误后再原地改（表达式用单引号包住；字符串要显式加引号）
yq -i '.a.b[0].c = "cool"' file.yaml

# 4) 改完复核
yq '.a.b[0].c' file.yaml
```

格式转换与合并：

```bash
yq -Poy sample.json                              # JSON → 排好版的 YAML
yq -o=json file.yaml                             # YAML → JSON
yq -p=xml -o=yaml file.xml                       # XML → YAML（输入格式要显式指定）
yq -n 'load("a.yaml") * load("b.yaml")'          # 两文件深合并
yq ea '. as $item ireduce ({}; . * $item )' path/to/*.yml   # 合并一批文件
```

容器方式：

```bash
docker run --rm -v "${PWD}":/workdir mikefarah/yq '.a.b[0].c' file.yaml
docker run -i --rm mikefarah/yq '.this.thing' < myfile.yml    # 走 stdin 时必须加 -i
```

参数全集以 `yq --help` 与官方文档为准：https://mikefarah.gitbook.io/yq/

## 依赖

- **运行时**：无。单个静态二进制，下载即可用。
- **可选工具链**：
  - Go 工具链 —— 仅 `go install` 装法需要。
  - Docker / Podman —— 仅容器方式需要；从 stdin 读数据时容器要额外加 `-i`。
- **可选环境**：
  - Snap 装法处于 strict confinement 下，读写根目录文件需要先 `sudo cat` 出来再处理。
  - 容器镜像默认不带时区数据，用到日期时间运算时需自行补齐。
- **不需要**：网络（除安装阶段）、账号、API Key、GPU。

## 安全

- 不内嵌任何密钥：本 Skill 与脚本里没有 Token、密码或私钥。
- **会改写文件**：`-i / --inplace` 是直接覆盖目标文件；`-s / --split-exp` 会在磁盘上新建文件与目录。执行前请确保目标已纳入版本控制或有备份。
- **读取范围**：用户指定的文件，加上表达式里通过 `load()` 点名的其它文件。如果配置里含明文密钥，读出来的值会进入命令输出，注意不要粘进聊天记录或日志。
- **不会保留逐字节原样**：更新时它会重新序列化，注释位置与空白可能被重排，不要把它当作「只改一个字符」的精确编辑器。
- **文件与环境变量操作可关闭**：需要收窄能力时用 `--security-disable-file-ops` / `--security-disable-env-ops` 关掉 `load()` 与 `strenv()` 一类操作。
- **不要用于集群/服务端操作**：它只读写本地文件与标准输入输出，没有任何远程执行语义。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`yq`
- 仓库：https://github.com/mikefarah/yq

---

## 许可证

MIT，见 `LICENSE.md`。

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
