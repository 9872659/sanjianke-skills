---
name: sanjianke-yq
slug: sanjianke-yq
displayName: 三剪客 · YAML 命令行处理
description: "yq：YAML 命令行处理 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "yq：YAML 命令行处理 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - CLI
  - 开发工具
---

# 三剪客 · YAML 命令行处理

改一个 K8s 清单里的镜像 tag、批量改 CI 配置里的版本号、把一份 JSON 转成 YAML——这些事用 `sed` 容易改坏缩进和注释，用编辑器一个个开又太慢。这个工具用一套类似 `jq` 的表达式来读写结构化配置：能定位到深层字段、原地更新，还能在 YAML / JSON / XML / INI / CSV 之间互转。

它服务的是「结构化配置文件的命令行读写与格式转换」这个场景，前提是文件本身是合法 YAML / JSON / XML 之类，而不是随意的文本。

**上游项目**：`yq`　**仓库**：https://github.com/mikefarah/yq

## 什么时候用 / 不用

**用它**：

- 要在命令行读一个 YAML 里的深层字段：`yq '.spec.template.spec.containers[0].image' deploy.yaml`。
- 要原地改配置里的某个值，又不想破坏文件里已有的注释和整体结构：`yq -i '.a.b = "x"' f.yaml`。
- 要批量改一批同类文件里的同一个字段（配合 shell 的 glob）。
- 要在 YAML / JSON / XML / INI / props / CSV / TSV 之间互转：`yq -o=json f.yaml`、`yq -p=xml f.xml`。
- 要合并多个 YAML、按条件筛选数组元素并更新，或者从环境变量取值写进配置。

**不要用它**：

- 要编辑正文文本、Markdown、代码文件：它只理解结构化数据格式，当成通用文本编辑器用会出错。
- 要处理带自定义标签、锚点嵌套很深，而且要求「一个字节都不能变」的文件：更新时它会重排部分注释与空白。
- 要做集群运维（apply、rollout、查 Pod）：那是集群客户端工具的职责，这个工具只读写文件。
- 要处理超大文件或做流式处理：它是把文档整份读进内存再处理的。
- 要当任意格式的通用解析器：非标准 YAML 方言（比如模板语法混在 YAML 里）会直接解析失败。

## 安装

它是单个静态二进制，不依赖运行时。下面按平台列常用装法（完整清单以官方文档为准：https://mikefarah.gitbook.io/yq/）。

```bash
# 直接下二进制（Linux amd64 示例；把 latest 换成具体版本号可锁定版本）
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && \
  chmod +x /usr/local/bin/yq

# Go 工具链
go install github.com/mikefarah/yq/v4@latest

# macOS / Linuxbrew
brew install yq

# Windows
winget install --id MikeFarah.yq
scoop install main/yq
choco install yq

# Linux 发行版
snap install yq                 # Snapcraft（strict confinement，读根目录文件受限）
sudo pacman -S go-yq            # Arch
apk add yq-go                   # Alpine 3.20+
nix profile install nixpkgs#yq-go

# 确认装上了
yq --version
yq --help
```

官方也提供容器镜像，适合不想在宿主机装东西的场景：

```bash
# 处理当前目录下的文件（挂载工作目录）
docker run --rm -v "${PWD}":/workdir mikefarah/yq '.a.b[0].c' file.yaml

# 从 stdin 读数据时必须加 -i（--interactive），否则容器拿不到管道输入
docker run -i --rm mikefarah/yq '.this.thing' < myfile.yml
```

## 常用操作

下面每条都可以直接改路径和文件名跑。表达式里的路径写法与 `jq` 接近。

```bash
# 1) 读一个深层字段
yq '.a.b[0].c' file.yaml

# 2) 从标准输入读（不给文件名时默认读 stdin，按 YAML 解析）
cat file.yaml | yq '.a.b[0].c'
yq '.a.b[0].c' < file.yaml

# 3) 原地更新（-i 作用于第一个给的文件）；要写成字符串就显式加引号
yq -i '.a.b[0].c = "cool"' file.yaml

# 4) 一次改多处（用 | 串起来），值来自环境变量用 strenv
NAME=mike yq -i '
  .a.b[0].c = "cool" |
  .x.y.z = "foobar" |
  .person.name = strenv(NAME)
' file.yaml

# 5) 按条件筛选数组元素并更新（select 的写法）
yq -i '(.[] | select(.name == "foo") | .address) = "12 cat st"' data.yaml

# 6) 格式转换：JSON → YAML（-P 表示 pretty print）、YAML → JSON
yq -Poy sample.json              # 等价于 -P -o=yaml，输出成排好版的 YAML
yq -o=json file.yaml
yq -p=xml -o=yaml file.xml       # 输入是 XML 时要显式指定 -p

# 7) 合并两个文件：* 会把两个文档深合并
yq -n 'load("file1.yaml") * load("file2.yaml")'

# 8) 合并一批文件（ea = eval-all，先把所有文档读进来再执行一次表达式）
yq ea '. as $item ireduce ({}; . * $item )' path/to/*.yml

# 9) 新建一份文档（-n 不读输入）
yq -n '.a.b.c = "cat"'

# 10) 按每个结果拆成独立文件（表达式必须返回字符串，可用 $index 做序号）
yq -s '"out-" + $index + ".yml"' multi-doc.yaml
```

写进脚本时，配合退出码判断更稳：

```bash
# -e：没有匹配项、或结果是 null / false 时返回非零退出码
yq -e '.a.b' file.yaml > /dev/null && echo "字段存在" || echo "字段不存在或为 null"
# -N：不要打印多文档之间的 --- 分隔符
yq -N '.items[]' multi-doc.yaml
```

参数全集以 `yq --help` 与官方文档为准：https://mikefarah.gitbook.io/yq/

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 照着一篇老文章敲 `yq r file.yaml a.b`、`yq w -i ...`，直接报语法错误 | 那是一个**同名的 Python 版实现**的语法；Go 版的 v4 已经把 `r` / `w` 子命令删掉了 | 用表达式写法：读是 `yq '.a.b' f.yaml`，写是 `yq -i '.a.b = "x"' f.yaml`。先 `yq --version` 确认装的是哪个 |
| 报错 `cannot index array with 'xxx'` 或路径取到空 | 表达式没加引号，被 shell 先展开或改写了 | 表达式一律用单引号包住（Unix / macOS）。PowerShell 下引号规则不同，官方 Tips 页有专门说明；不确定就先 `yq --help` 对照 |
| 值写进去变成 `true` / 数字，但我要的是字符串 | YAML 里裸写的 `true`、`123` 会被当布尔或数字 | 要字符串就显式加引号：`yq -i '.a = "123"' f.yaml` |
| `-i` 之后文件里一堆注释没了、缩进被重排 | 更新时会重新序列化，无法保留所有注释位置与空白 | 改前先用版本控制兜底，或输出到临时文件比对；不要对「必须逐字节不动」的文件用 `-i` |
| 加了 `-i` 却仍然打印到标准输出、文件没变 | `-i / --inplace` 只作用于**第一个**文件参数，且与 `-o` 搭配时有额外限制 | 确认目标文件就是第一个位置参数；需要输出到别处时别用 `-i`，改成重定向 |
| 多文档 YAML 合并结果不对，只剩一份文档 | 默认的 `eval` 是「对每个文档依次执行」，跨文档合并必须在 `eval-all` 下做 | 跨文件/跨文档操作用 `yq ea ...`；单文档转换用 `yq e ...` 就够 |
| `yes` / `no` 被当成字符串而不是布尔值 | YAML 1.2 把 `yes`/`no` 归为字符串，而它按 1.2 处理 | 需要布尔就写 `true` / `false` |
| 输出 JSON 带缩进换行，塞给别的工具不方便 | `-o=json` 默认会排版 | 用 `-I=0` 输出紧凑 JSON：`yq -o=json -I=0 f.yaml` |
| Windows 下表达式里的引号总是被吃掉 | PowerShell 对引号有自己的处理规则，和 POSIX shell 不同 | 优先用单引号；需要在双引号里写字面量时转义 `\"`；细节以官方 Tips 页为准 |
| 用 `load()` / `strenv()` 时提示文件或环境变量操作被禁用 | 这两类能力受安全开关控制 | 检查是否带了 `--security-disable-file-ops` / `--security-disable-env-ops`，按需调整 |
| 管道给 `head` 之后出现 broken pipe 报错 | 下游提前关闭了管道 | 不是数据错误，可以忽略；或调低输出详细程度 |
| 表达式明明看着对，却被当成文件名去读了 | 参数检测把它误判成了文件路径 | 用 `--expression` 强制指定表达式，或把表达式写在文件名前面 |
| 从 stdin 读 XML / JSON 时按 YAML 解析了 | 不给文件名就无法靠扩展名判断格式，默认按 YAML 处理 | 显式指定 `-p=xml` / `-p=json`；可用的格式列表以 `yq --help` 为准 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 纯本地文件处理，不联网（安装阶段除外） |
| 读取文件 | 是 | 读取用户指定的 YAML / JSON / XML / INI / props / CSV 等；`load()` 会读表达式里点名的其它文件 |
| 写入文件 | 是 | `-i / --inplace` 直接改写目标文件；`-s / --split-exp` 会按表达式结果在磁盘上新建文件与目录 |
| 凭证 | 否 | 不需要账号或 Key。但配置文件里可能含密钥，读出来的内容会进入命令输出 |
| 子进程 / 后台常驻 | 否 | 一次性进程，不驻留；容器方式下会启动一个容器，用完即退出 |

## 触发场景

- 「把这个 YAML 里的镜像 tag 改掉」
- 「帮我看一下这个配置里 xxx 字段是什么值」
- 「这堆 JSON 转成 YAML」
- 「把目录下所有这类配置文件里的版本号一起改了」
- 「把两个 YAML 合并成一个」
- 「找出数组里 name 等于 xxx 的那一项，改它的某个字段」

## 能力边界

**覆盖**：

- 读取与更新 YAML、JSON、XML、INI、properties、CSV / TSV 等结构化格式，支持多文档 YAML 与 front matter。
- 表达式能力：路径导航、`select` 筛选、`ireduce` 归约、`load` 载入其它文件、`strenv`/`env` 取环境变量、字符串插值、排序、注释与样式操作、锚点与别名、编解码、日期时间运算。
- 原地更新（`-i`）、格式互转（`-p` / `-o`）、按表达式拆分成多文件（`-s`）、多文档分隔控制（`-N`）、退出码控制（`-e`）、shell 补全脚本生成。
- 提供容器镜像与 CI 集成用法。

**不覆盖**：

- 不保证逐字节保留原文件（注释位置与空白可能被重排）。
- 不做集群/服务端操作，没有「远程 apply」类语义，只读写本地文件与标准输入输出。
- 不做流式处理，文档是整份读入内存的。
- 不做通用文本替换、不做代码重构、不做语法检查之外的语义校验。
- 不支持非标准 YAML 方言与模板语法混排的文件。

## 依赖条件

- 单二进制发行，无需额外运行时；容器方式需要 Docker 或 Podman。
- 用 `go install` 装需要 Go 工具链；从源码构建需要 Go。
- Snap 装法处于 strict confinement 下，读写根目录文件需要绕行（先 `sudo cat` 出来再处理）。
- 不需要账号、Key 或网络连接。

## 已知限制

- 更新时无法保留全部注释与空白，源文件需要版本控制兜底。
- 跨文档操作必须显式使用 `eval-all`，默认的 `eval` 是逐文档执行的。
- 同类工具存在多个实现，参数并不互通，混用会直接报语法错误。
- 容器内运行需要额外传 `-i` 才能接收标准输入。
- 容器镜像默认不带时区数据，用到日期时间运算时需要自行补齐。

## 自检清单

执行前：

- [ ] 已确认这台机器上装的是哪一个同名实现：`yq --version` 看一眼，避免把 `r` / `w` 老语法直接用上去。
- [ ] 表达式已用正确引号包住（POSIX 用单引号），Windows 下按官方说明处理。
- [ ] 要写字符串就先想好引号，要写数字/布尔就不要加引号。
- [ ] 用 `-i` 之前确认目标文件已纳入版本控制，或有备份。

执行后：

- [ ] 用一次只读查询复核改动结果：`yq '.改过的路径' 文件`。
- [ ] 检查多文档文件的分隔符与文档数量是否符合预期（必要时用 `-N`）。
- [ ] 如果是拆分输出，确认新生成的目录与文件名落在预期位置。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/mikefarah/yq | 上游仓库（安装与完整文档以它为准） |
| https://mikefarah.gitbook.io/yq/commands/evaluate | `eval` 命令的用法与全部参数 |
| https://mikefarah.gitbook.io/yq/usage/tips-and-tricks | 引号、Windows 等常见陷阱的官方说明 |

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
