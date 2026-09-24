---
name: sanjianke-qpdf
slug: sanjianke-qpdf
displayName: 三剪客 · PDF 无损变换
description: "qpdf：PDF 结构级无损变换 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "qpdf：PDF 结构级无损变换 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档处理
---

# 三剪客 · PDF 无损变换

qpdf 是一个命令行工具，做的是「不碰内容、只改结构」的 PDF 操作：合并、拆分、重新排序、旋转、
加密解密、线性化（网页快速打开）、压体积、检查文件是否有结构错误。

它最值钱的地方在于**不重新渲染**。它不会把你的 PDF 拆成像素再拼回去，字体、矢量、书签、链接、
表单都按原样搬过去，所以合同、票据、公文这类不能有任何视觉损耗的文件，用它是安全的。

反过来说，它完全不懂内容：不认表格、不认文字，也不做转换。要提文字、要转 Word、要做 OCR，得换别的工具。

**上游项目**：`qpdf`　**仓库**：https://github.com/qpdf/qpdf

## 什么时候用 / 不用

**用它**：

- 用户说「把这十几个 PDF 按顺序合成一本」或「只要第 3 到 8 页，单独存一个文件」。
- 用户说「这份 PDF 打开太慢，能不能优化」——`--linearize` 就是干这个的。
- 用户说「给它加个密码 / 把密码去掉 / 限制打印和复制」。
- 用户说「这个 PDF 打不开或有问题，帮我看看哪儿坏了」——`--check` 直接报结构问题。
- 需要在脚本、CI、定时任务里无人值守跑 PDF 批处理，不想装 GUI、JVM 或 Office。
- 要拆页但必须保留文档级内容（书签、标签）——用 `--pages` 而不是 `--split-pages`。

**不要用它**：

- 要从 PDF 里抽文字、表格、图片——它不做文本抽取，也不解析页面内容语义。
- 要 PDF 转 Word / Excel / Markdown / HTML——它不做格式转换。
- 要给 PDF 加水印、页码、页眉页脚——它没有画内容的接口，得用专门的库或工具。
- 要处理扫描件、做 OCR——它只认 PDF 结构，图片里的字它看不见。
- 要压体积却主要是图片占空间——`--optimize-images` 有损，先确认能接受画质变化；只想去掉冗余结构用 `--object-streams=generate` 加 `--recompress-flate`。

## 安装

```bash
# Debian / Ubuntu
sudo apt-get install qpdf

# Fedora / RHEL
sudo dnf install qpdf

# Arch
sudo pacman -S qpdf

# macOS（Homebrew）
brew install qpdf

# MSYS2 / mingw64（Windows）
pacman -S mingw-w64-x86_64-qpdf
```

Windows 上还可以从 [GitHub Releases](https://github.com/qpdf/qpdf/releases) 下载官方二进制包，
解压后把 `bin` 目录加进 `PATH` 即可。各发行版的包管理器命令以其官方文档为准。

从源码构建（qpdf 11 起改用 CMake）：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build
cmake --install build
```

构建依赖：支持 C++-20 的编译器、CMake 3.16 以上、zlib、libjpeg 兼容库；
想要更好的加密实现可选装 GnuTLS 或 OpenSSL。

```bash
# 确认装好了、看版本
qpdf --version

# 看当前可用的加密后端
qpdf --show-crypto
```

## 常用操作

**1. 合并多个 PDF（推荐写法，文档级信息来自第一个文件）**

```bash
qpdf in.pdf --pages . a.pdf b.pdf -- out.pdf

# 从空文件开始，按顺序拼所有页
qpdf --empty --pages a.pdf b.pdf c.pdf -- merged.pdf

# 只要 b.pdf 的偶数页
qpdf in.pdf --pages . a.pdf b.pdf 1-z:even -- out.pdf
```

说明：`--pages` 与 `--` 之间是一个个「文件 [页范围]」；`.` 代表主输入文件 `in.pdf`。

**2. 抽取指定页 / 反序 / 拆分单页**

```bash
# 只保留第 3 到 8 页
qpdf in.pdf --pages . 3-8 -- part.pdf

# 整本倒序
qpdf in.pdf --pages . z-1 -- reversed.pdf

# 每页一个文件，输出 out-01.pdf、out-02.pdf …（文件名会按页数补零）
qpdf --split-pages in.pdf out.pdf

# 每 2 页一个文件
qpdf --split-pages=2 in.pdf out.pdf
```

**3. 加密与解密**

```bash
# 256 位加密：用户密码 user123，所有者密码 owner456
qpdf --encrypt --user-password=user123 --owner-password=owner456 --bits=256 -- in.pdf out.pdf

# 禁止打印和文本提取
qpdf --encrypt --user-password=user123 --owner-password=owner456 --bits=256 \
     --print=none --extract=n -- in.pdf out.pdf

# 去掉加密（需要提供能打开文件的密码）
qpdf --password=user123 --decrypt in.pdf out.pdf
```

注意：256 位是官方推荐的默认选择；40 位、以及不带 AES 的 128 位属于弱加密，
从 11.0 起必须显式加 `--allow-weak-crypto` 才允许生成。

**4. 体检与信息查询（这些选项都不产生输出文件）**

```bash
# 检查结构是否合法，并把信息打到标准输出
qpdf --check in.pdf

# 只看页数（脚本里最好用）
qpdf --show-npages in.pdf

# 看加密参数
qpdf --show-encryption in.pdf

# 用退出码判断：是否加密 / 是否需要密码（静默，不打印）
qpdf --is-encrypted in.pdf;   echo $?   # 0=已加密，2=未加密
qpdf --requires-password in.pdf; echo $?   # 0=需要密码，2=未加密，3=密码正确
```

**5. 优化与压体积**

```bash
# 线性化：网页端可以边下边看
qpdf --linearize in.pdf web.pdf

# 结构性压体积：生成对象流 + 重新压缩 flate
qpdf --object-streams=generate --recompress-flate --compression-level=9 in.pdf small.pdf

# 有损压图（会重编码 JPEG，务必人工核对画质）
qpdf --optimize-images --jpeg-quality=75 in.pdf light.pdf
```

**6. 旋转与页面标签**

```bash
# 第 2、4、6 页顺时针转 90 度；第 7-8 页转 180 度
qpdf in.pdf out.pdf --rotate=+90:2,4,6 --rotate=+180:7-8

# 把旋转写进页面内容（应对不认 /Rotate 的阅读器）
qpdf --flatten-rotation in.pdf out.pdf

# 前 4 页用罗马数字，从第 5 页起用阿拉伯数字
qpdf --set-page-labels 1:r 5:D -- in.pdf out.pdf
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 脚本里 `if qpdf ...` 判断成失败，其实文件没问题 | qpdf 的退出码有 4 档：0 无警告、2 有错误、**3 表示只有警告**、1 从不使用 | 只把 `2` 当失败；想彻底忽略警告就加 `--warning-exit-0`，或再加 `--no-warn` |
| 用 `--split-pages` 拆出来的文件书签、标签全没了 | 该选项对每一页新建空 PDF 再拷一页，文档级内容不保留 | 需要保留就改用 `--pages` 逐页跑：`qpdf in.pdf --pages . 5 -- p5.pdf` |
| `--rotate=90` 后方向跟预期相反 | 不带 `+`/`-` 是**绝对**设置角度，不是叠加 | 一律写相对角度：`--rotate=+90`（顺时针）或 `--rotate=-90`（逆时针） |
| 想把结果写回原文件，结果多出两个文件 | `--replace-input` 会写临时文件，有警告时原文件存为 `*.~qpdf-orig` | 正常现象；确认无需回滚后再删掉 `~qpdf-orig`，或用输出到新文件名的写法 |
| 报错说有密码却打不开 | 文件已加密，qpdf 不会去猜密码 | 用 `--password=...` 或 `--password-file=...`（后者取文件第一行，不裁空格；用 `@filename` 传参可避免密码出现在进程列表里） |
| 管道里 `cat a.pdf \| qpdf - out.pdf` 失败 | 输入文件必须可 seek，qpdf 不支持从标准输入读 | 先把内容落成临时文件再传路径；只有 `@-`（读参数）走标准输入 |
| 生成 40 位或 RC4 加密时报错被拒 | 11.0 起默认拒绝写出弱加密文件 | 确有必要才加 `--allow-weak-crypto`；能改就改 `--bits=256` |
| `--optimize-images` 之后文件小了但画质变糊 | 该选项会把图片重编码为 JPEG，属于有损操作 | 先备份原文件；用 `--jpeg-quality` 提高质量，或用 `--oi-min-area` 排除小图 |
| 把检查类选项和输出文件写在一起，命令报用法错误 | 检查类（`--check`、`--show-*`、`--json`）与帮助类选项不允许给输出文件 | 拆成两步：先查，再单独跑变换 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 仅安装时需要 | 通过包管理器或 GitHub Releases 获取程序；运行时完全离线 |
| 读取文件 | 是 | 读取待处理的 PDF；`--pages` 会同时读多个输入文件 |
| 写入文件 | 是 | 写出结果 PDF；`--split-pages` 会批量生成多个文件 |
| 凭证 | 视需要 | 加密/解密时的用户密码与所有者密码；建议用 `--password-file` 或参数文件传，别写进脚本明文 |
| 子进程 / 后台常驻 | 否 | 单次执行的命令行程序，跑完即退，无常驻服务 |

## 触发场景

- 「帮我把这份年报的封面去掉，从第 2 页开始另存一份」
- 「这几张发票 PDF 合成一个文件，按文件名排序」
- 「这个 PDF 加了密码打不开，密码是 xxxx，帮我解密」
- 「给这份标书加密码，禁止修改和复制」
- 「PDF 打开特别慢，几十兆，能不能压一压」
- 「文件传过去对方说打不开，帮我查一下是不是坏了」

## 能力边界

**覆盖**：

- 结构级操作：合并、拆分、抽取页、重排、倒序、旋转、线性化。
- 加密与权限：设置用户/所有者密码，控制打印、复制、修改、装配等权限；解密与去限制。
- 结构与元数据治理：删掉 /Info、/Metadata、页面标签、结构树、交互表单字典。
- 附件：列出、导出、增删嵌入式文件。
- 体积优化：对象流生成、flate 重压缩、压缩级别、JPEG 重编码。
- 检查与取证：结构合法性检查、页数、加密参数、交叉引用表、单个对象内容、JSON 形式导出。
- 表单相关：生成外观流、把注释压平进页面内容。

**不覆盖**：

- 文本与图片抽取、表格结构还原、版面理解。
- 任何格式转换（PDF ↔ Word / Excel / HTML / 图片）。
- 渲染、打印、缩略图生成、OCR。
- 添加水印、页码、页眉页脚等「画新内容」的操作。
- 生成完整 PDF/A 合规文件：它只能在已合规的文件上尽量不破坏合规性。
- 数字签名：可以移除限制，但会作废签名，不负责重新签名。

## 依赖条件

- 命令行环境：Linux、macOS、Windows 均可；无图形界面依赖。
- 预编译包由各发行版/包管理器提供，无需自行编译。
- 源码构建需 C++-20 编译器 + CMake 3.16+ + zlib + libjpeg；可选 GnuTLS / OpenSSL。
- 不需要任何账号或 API Key。
- 处理加密文件时，需要用户自己提供密码。

## 已知限制

1. 输入必须是可 seek 的本地文件，不能从标准输入读 PDF。
2. 检查只覆盖「语法结构」层面：页面内容是否正确、语义是否合理，它一概不判断。
3. `--optimize-images` 与 JPEG 重编码是有损的，且可能已经压缩过的图片被二次压缩、画质再降。
4. 同一份输出在不同版本的 qpdf 之间不保证逐字节一致，需要可复现时用 `--deterministic-id`（但该选项与加密创建不兼容）。
5. 不同阅读器对权限位的执行程度不一样，加密限制只能"声明"，不能强制。

## 自检清单

- [ ] `qpdf --version` 能跑通，确认版本与预期一致。
- [ ] 输入文件路径正确、不是软链断链，且确实可读。
- [ ] 输出是写到新文件名，而不是直接覆盖素材？要覆盖是否确知 `--replace-input` 的行为？
- [ ] 脚本里的退出码判断是否只把 `2` 当失败（`3` 是仅警告）？
- [ ] 加密时选的是 256 位？密码是否避免明文出现在脚本或命令行历史里？
- [ ] 涉及有损操作（`--optimize-images`）前是否已备份原文件并人工核对画质？
- [ ] 拆分场景是否确认过文档级内容（书签、标签）需要保留？需要就用 `--pages`。
- [ ] 产出文件是否用真实阅读器打开验证过页数、方向、可打印性？

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/qpdf/qpdf | 上游仓库（安装与完整文档以它为准） |
| https://qpdf.readthedocs.io/en/stable/cli.html | 官方命令行选项参考（含页范围、加密、检查、JSON 各节） |

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
