---
name: sanjianke-yt-dlp
slug: sanjianke-yt-dlp
displayName: 三剪客 · 全网视频音频下载器
description: "yt-dlp：从上千个站点下载视频与音频，按画质/编码挑格式、合并音视频轨、抽音频、抓字幕、批量备档。含多平台安装方式、可直接跑的命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "面向素材采集的命令行下载器：一条命令按需挑格式、合并音视频、抽音频、下载字幕并嵌入元数据，支持 Cookie 登录态、分段下载、断点续传与下载清单去重。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 素材
---

# 三剪客 · 全网视频音频下载器

做内容最费时间的环节之一，是把原始素材落到本地：想要一个能剪辑的视频、想要一段能转写的音频、想要一份现成的字幕，来源散在几十个站点上，每个站点的下载方式都不一样。yt-dlp 把这件事收成一条命令行——给一个链接，它自己解析出可用的清晰度与编码列表，按你的规则选、下、合并、转封装。

它真正省事的地方在**格式选择**和**后处理**：不是只能"下最高清"，而是能说"要 mp4 容器、H.264 编码、优先高帧率、音轨要 aac"，下完顺手把音视频轨合并、把字幕和封面写进文件、把元数据填上。素材进剪辑软件时不用再转一道。

它也是**批量化**的工具：播放列表、频道、下载清单去重、限速与请求间隔，都是内置选项，适合挂成夜间任务跑。

**上游项目**：`yt-dlp`　**仓库**：https://github.com/yt-dlp/yt-dlp

## 什么时候用 / 不用

**用它**：

- 用户说「把这个视频下下来」「这段音频抽出来我要转文字」，手上有一个具体链接。
- 需要**按画质或编码挑格式**，而不是碰运气下个最高清——比如"必须 H.264，剪辑软件才认"。
- 要批量：一整个播放列表、一个频道的历史视频，或者按清单增量下载、已下过的不重复下。
- 需要连带把**字幕、封面、章节、元数据**一起拿到或写进文件。
- 目标站点的资源需要登录态才能看，得带上浏览器 Cookie 才能解析。

**不要用它**：

- **要下载的内容你没有权利下载**。版权作品、付费课程、会员专享内容，工具能下不代表可以下；这类请求应当先回到授权问题，而不是先研究参数。
- **目标是纯网页或接口数据**。它做的是媒体流解析，不是爬虫；要抓页面里的结构化数据应该用别的工具。
- **要的是直播录制、实时推流**。它对正在进行的直播支持有限且不稳定，长时间无人值守的录制不是它的强项。
- **只想剪一刀、转个码**。手上已经有文件，只需要裁剪、拼接、压缩，直接用 ffmpeg 更直接。
- **环境里没有 Python 也没有 ffmpeg，且不允许装**。它本身是 Python 程序，且合并音视频、抽音频都依赖 ffmpeg。没有任何可安装条件时，这条路走不通。
- **需要图形界面给非技术同事用**。它只有命令行，GUI 属于第三方生态，不在本包范围内。

## 安装

官方推荐三种路径：直接下发行二进制、走 pip、走系统包管理器。第三方包管理器维护的版本可能滞后，出问题要找回对应维护方。

**方式一：发行二进制（单文件，最省依赖）**

Windows 直接在 `releases/latest` 下取 `yt-dlp.exe`；macOS 取 `yt-dlp_macos`；Linux/BSD 推荐取 `yt-dlp`（需要本机有 Python）。Linux/macOS 放进 `PATH` 的写法：

```bash
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/.local/bin/yt-dlp
chmod a+rx ~/.local/bin/yt-dlp
```

用发行二进制的话，升级就是自更新：

```bash
yt-dlp -U
```

**方式二：pip（便于固定版本、嵌进虚拟环境）**

```bash
python3 -m pip install -U "yt-dlp[default]"
# Windows 上把 python3 换成 python 或 py
```

只要裸包、不要任何可选依赖：

```bash
python3 -m pip install --no-deps -U yt-dlp
```

**方式三：系统包管理器**

```bash
brew install yt-dlp            # macOS / Linux（Homebrew）
winget install yt-dlp          # Windows
scoop install yt-dlp           # Windows
choco install yt-dlp           # Windows
sudo pacman -Syu yt-dlp        # Arch Linux
```

**必须一起装的 ffmpeg**

官方说明：除了核心包，`ffmpeg`、`ffprobe`、`yt-dlp-ejs` 和一个受支持的 JavaScript 运行时是**强烈推荐**项；其中 ffmpeg / ffprobe 是合并独立视频与音频轨、以及各类后处理的前提。

```bash
sudo apt update && sudo apt install ffmpeg   # Ubuntu / Debian
brew install ffmpeg                          # macOS
winget install ffmpeg                        # Windows（或从 ffmpeg 官网取构建）
```

注意：需要的是 **ffmpeg 可执行文件**，不是 PyPI 上同名的 Python 包。找不到时可用 `--ffmpeg-location PATH` 指定二进制或其所在目录。

## 常用操作

**1. 下最高质量（音视频分轨时会自动合并，需要 ffmpeg）**

```bash
yt-dlp "https://example.com/watch?v=xxxx"
```

**2. 先看清楚有哪些格式，再决定下哪个**

```bash
yt-dlp -F "https://example.com/watch?v=xxxx"
```

`-F` / `--list-formats` 列出该视频所有可用格式；选好后用 `-f` 指定格式码。

**3. 抽音频：转成 mp3**

```bash
yt-dlp -x --audio-format mp3 "https://example.com/watch?v=xxxx"
```

`-x` / `--extract-audio` 转成纯音频，`--audio-format` 支持 `best`（默认）、`aac`、`alac`、`flac`、`m4a`、`mp3`、`opus`、`vorbis`、`wav`。音质用 `--audio-quality` 调，填 0（最好）到 10（最差），或直接写码率如 `128K`。

**4. 指定容器与编码偏好，输出到指定目录**

```bash
yt-dlp -S "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac" \
       --merge-output-format mp4 \
       -P "D:/素材/%(playlist_title)s" \
       -o "%(upload_date>%Y-%m-%d)s_%(title)s.%(ext)s" \
       "https://example.com/watch?v=xxxx"
```

`-S` / `--format-sort` 排的是"同档次里优先谁"，比硬写 `-f` 更耐站点改版；`-P` 定目录、`-o` 定文件名模板。

**5. 带上字幕，并写进容器**

```bash
yt-dlp --write-subs --write-auto-subs --sub-langs "zh-Hans,en.*" \
       --embed-subs --embed-metadata --embed-thumbnail \
       "https://example.com/watch?v=xxxx"
```

`--embed-subs` 只对 mp4 / webm / mkv 有效。字幕语言用 `--sub-langs` 控制，支持正则写法。

**6. 只要信息不要文件（适合脚本里先做判断）**

```bash
yt-dlp --skip-download --print "%(title)s|%(duration)s|%(upload_date)s" \
       "https://example.com/watch?v=xxxx"

# 整条播放列表一次性输出 JSON
yt-dlp -J --flat-playlist "https://example.com/playlist?list=xxxx"
```

`-O` / `--print` 会隐含 `--quiet` 并隐含模拟下载（除非显式 `--no-simulate`）；`-J` / `--dump-single-json` 输出整条播放列表的单行 JSON。

**7. 批量且去重：下载清单 + 请求间隔**

```bash
yt-dlp --download-archive done.txt \
       --sleep-requests 1 --sleep-interval 5 --max-sleep-interval 15 \
       -N 4 \
       -P "D:/素材" -o "%(playlist_index)03d_%(title)s.%(ext)s" \
       "https://example.com/playlist?list=xxxx"
```

`--download-archive` 记录已下过的 ID，重跑时跳过，适合定时任务；`-N` / `--concurrent-fragments` 提高分片并发；`--sleep-*` 控制请求与下载间隔，降低被限流的概率。

**8. 需要登录态时读浏览器 Cookie**

```bash
yt-dlp --cookies-from-browser chrome "https://example.com/watch?v=xxxx"
# 或用一个现成的 cookies.txt（Netscape 格式）
yt-dlp --cookies cookies.txt "https://example.com/watch?v=xxxx"
```

支持的浏览器名以 `--help` 当前输出为准（常见为 brave、chrome、chromium、edge、firefox、opera、safari、vivaldi、whale）。

**9. 只下某一段（依赖 ffmpeg）**

```bash
yt-dlp --download-sections "*00:01:30-00:03:00" "https://example.com/watch?v=xxxx"
```

`--download-sections` 接正则；以 `*` 开头表示按时间区间而不是按章节名，负时间戳从结尾算，`*from-url` 表示用链接里带的起止时间。

**10. 配置一次、以后都省参数**

把常用选项写进配置文件即可全局生效（Windows 推荐 `${APPDATA}/yt-dlp/config`，Linux/macOS 推荐 `${XDG_CONFIG_HOME}/yt-dlp/config`），写法与命令行完全一致，`-` 或 `--` 后不能有空格。临时想忽略所有配置加 `--ignore-config`。

```conf
# Always extract audio
-x
# Save all videos under YouTube directory in your home directory
-o ~/YouTube/%(title)s.%(ext)s
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 下到一半报错，或只落下一个没有声音的视频 | 音视频是分开的流，合并需要 ffmpeg；没装或找不到就会失败 | 先装 ffmpeg 并确认在 `PATH` 里；不行就用 `--ffmpeg-location` 指定可执行文件或其所在目录。切记要的是 ffmpeg **二进制**，不是 PyPI 上同名的 `ffmpeg` 包 |
| 明明装了 ffmpeg，仍然提示找不到 | 装的是 pip 包，或者 ffmpeg 只装在某虚拟环境里、不在当前 shell 的 `PATH` | 用 `ffmpeg -version` 验证；Windows 上把 ffmpeg 目录加进系统 `PATH`，或改用 `--ffmpeg-location` |
| 站点突然解析失败、报一堆提取器错误 | 站点改版了。官方明确说明 `stable` 通道发布偏慢、容易跟不上站点变化 | 官方建议普通用户走 `nightly` 通道。二进制：`yt-dlp --update-to nightly`；pip：`python3 -m pip install -U --pre "yt-dlp[default]"` |
| 部分站点的完整支持受限（尤其视频站点的签名/JS 挑战） | 除了核心包，官方强烈推荐 `yt-dlp-ejs` 与一个 JavaScript 运行时（deno 优先级最高且默认启用，其次 node、quickjs、bun） | 装上 `yt-dlp-ejs` 和一个运行时；用 `--js-runtimes` 添加非默认运行时，具体取值以 `--help` 当前输出为准。确认不了就按官方 README 的依赖章节操作 |
| `-f` 里的格式码报 `Requested format is not available` | 格式码是**每个视频各不相同**的，不能照抄别人命令里的数字 | 先 `yt-dlp -F <URL>` 看这个视频实际有哪些格式；或者改用 `-S` 按偏好排序，别写死格式码 |
| `-f "bestvideo+bestaudio"` 在 shell 里被拆开或报参数错误 | 格式表达式里有 `+`、`[`、`]`、`/` 这类 shell 特殊字符 | 整个表达式加引号：`-f "bv*+ba/b"`。Windows PowerShell 下同样要引号 |
| 下载速度极慢、频繁 403 或需要验证 | 请求过密触发了站点的频率限制 | 加 `--sleep-requests`、`--sleep-interval`、`--max-sleep-interval`；需要登录态时用 `--cookies-from-browser` 或 `--cookies`，不要靠增加并发硬冲 |
| 读浏览器 Cookie 失败 | 浏览器正在运行、Cookie 库被独占锁；或 Chromium 系在 Linux 上需要 keyring 才能解密 | 先完全退出浏览器再试；Linux 上按 `--cookies-from-browser BROWSER+KEYRING` 的形式补 keyring 参数。原文代价太高时，改用一个已导出的 `cookies.txt` |
| 文件名里带特殊字符，落盘后打不开或播放器读不到 | 站点标题里可能有空格、`&`、Unicode 字符，不同系统容忍度不同 | 加 `--windows-filenames` 保证跨平台兼容，或 `--restrict-filenames` 限制成纯 ASCII；再配 `--trim-filenames LENGTH` 控制长度。用 `-o` 模板时可用 `%(title)S` 之类的清洗转换 |
| 播放列表只想要其中一条，结果整条队列都在下 | 链接同时指向视频和播放列表时，默认行为会把播放列表一起处理 | 加 `--no-playlist` 只下当前视频；反过来要整条列表就写 `--yes-playlist` |
| 定时任务重跑时整个列表又下一遍 | 没有开启去重记录 | 每类任务一个独立的 `--download-archive` 清单文件，跑完保留，不要删 |
| 老版本每次运行都提示更新 | 上游对超过一定天数的版本会提示；该天数阈值以实际版本为准 | 加 `--no-update` 抑制提示，或直接升级。注意 pip 装的不能用 `-U` 自更新，要重跑原来的 pip 安装命令 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 访问视频页面、调用站点接口解析出可用格式与直链，再下载媒体流；可配置 `--proxy` |
| 读取文件 | 是 | 读取配置文件与 `--cookies` 指定的 cookies 文件；`--cookies-from-browser` 会读取本机浏览器数据库；`--load-info-json` 会读入 JSON |
| 写入文件 | 是 | 把媒体文件、字幕、封面、`--write-info-json` 的元数据、`--download-archive` 的清单写进磁盘；`--print-to-file` 会追加写日志 |
| 凭证 | 视情况 | 需要登录态时才涉及：`--cookies` / `--cookies-from-browser` / `--username` / `--password` / `--netrc`。官方建议用 `.netrc` 或 `--netrc-cmd` 而不是把密码写进命令行，以免留在 shell 历史里。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是（间接） | 合并音视频、转码、抽音频、按章节切分都要调用 ffmpeg / ffprobe；`--exec` 可以在下载后执行自定义命令。`--exec` 只允许有限的模板转换（`i`/`d`、`f`、`q`），但仍应只对自己的命令使用 |

## 触发场景

- 「把这个视频下下来，我要做二创」
- 「这段音频帮我抽出来，我拿去做字幕」
- 「这个播放列表批量下，已经下过的别重复下」
- 「要 mp4 格式的，能直接丢进剪辑软件」
- 「把中文字幕一起抓下来，最好嵌到视频里」
- 「这个链接是会员内容，我用浏览器登录了，怎么下」

## 能力边界

**覆盖**：

- 媒体下载：站点支持列表覆盖上千个站点，具体清单以上游 `supportedsites.md` 与 `--list-extractors` 的当前输出为准。
- 格式选择：`-F` 列出可用格式，`-f` 精确指定，`-S` 按视频编码 / 音频编码 / 语言 / 画质 / 分辨率 / 帧率 / HDR 等字段排序偏好。
- 后处理：音视频合并、容器重封装（`--remux-video`）、重编码（`--recode-video`）、抽音频、字幕格式转换与嵌入、封面与元数据嵌入、按章节切分或删除、SponsorBlock 标记或删除片段。
- 信息与自动化：`--print` / `-J` 输出结构化信息、`--download-archive` 增量去重、`--batch-file` 批量清单、`--exec` 下载后挂钩子。
- 访问控制配合：Cookie 文件与浏览器 Cookie、`.netrc`、代理、限速与请求间隔、并发分片数。
- 配置：命令行、配置文件、`--config-locations` 多层叠加。

**不覆盖**：

- 不做剪辑、拼接、调色、加字幕特效——那属于剪辑软件；本包只负责把素材拿到手并做好基础封装。
- 不做网页抓取或接口数据采集，它面向媒体流解析。
- 不提供图形界面，也不提供托管下载服务。
- 不解决版权与授权问题：能不能下、能不能二次使用，取决于你是否有相应权利。
- 不支持所有站点的一切内容：站点改版、DRM 保护内容、直播长录制都可能失败。
- 不同发行渠道（官方二进制、PyPI 包、第三方包管理器）功能与更新节奏不一致，第三方包的问题不由上游处理。

## 依赖条件

- Python 3.10+（CPython）或 3.11+（PyPy）；用发行二进制时自带运行时，但 Linux/BSD 的 `yt-dlp` 单文件仍需本机 Python。
- `ffmpeg` 与 `ffprobe` 强烈推荐，且是合并音视频、抽音频、按章节切分、重封装等一系列功能的前提。官方说明需要的是 ffmpeg 二进制，不是同名 PyPI 包。
- `yt-dlp-ejs` 与一个受支持的 JavaScript 运行时，官方列为获取完整站点支持（尤其视频站点）所需；运行时优先级为 deno > node > quickjs > bun，仅 deno 默认启用。
- 可选依赖：`curl_cffi`（`curl-cffi` extra，用于伪装浏览器 TLS 指纹）、`mutagen` / `AtomicParsley`（封面嵌入的部分格式）、`pycryptodomex`（AES-128 HLS 解密）、`secretstorage`（Linux 下 Chromium 系 Cookie 解密）等。
- 部分站点需要账号登录态，通过 Cookie 或 `.netrc` 提供；本包不需要任何付费 Key。

## 已知限制

- 站点适配是持续对抗的过程：任何时刻都可能有站点暂时不可用，官方提供 `nightly` / `master` 通道用于尽快拿到修复。
- 格式码不跨视频通用，必须逐个视频查询；把别人命令里的格式码当成模板是典型误用。
- 官方直白提示：`stable` 通道的发布常被形容为偏旧、易受站点侧改动影响，因此建议常规使用者用 `nightly`。
- 正式版与夜间版的可用选项会随版本增减；本包给出的选项均取自上游当前文档，具体到某个版本请以该版本的 `yt-dlp --help` 为准。
- 具体的版本号、发布日期与 star 数请以仓库页面实时信息为准，此处不做断言。

## 自检清单

- [ ] 已确认对该内容有下载与使用的权利，而不是"技术上能下"。
- [ ] `yt-dlp --version` 能跑通，版本不过旧。
- [ ] `ffmpeg -version` 能跑通；Python 的 `ffmpeg` 包不算。
- [ ] 需要合并或抽音频时，已确认 ffmpeg 就在当前 shell 的 `PATH` 里，或已备好 `--ffmpeg-location`。
- [ ] 目标站点的完整支持依赖 `yt-dlp-ejs` 与 JS 运行时，已按官方依赖章节确认。
- [ ] 用了 `-f` 时，先跑过 `-F` 确认该视频确实有这些格式码。
- [ ] 含 `+`、`[`、`]`、`/` 的参数都加了引号。
- [ ] 输出目录与文件名模板已确认：跨平台就加 `--windows-filenames`，长标题加 `--trim-filenames`。
- [ ] 批量任务已配 `--download-archive` 并保留清单文件，重跑验证过确实会跳过。
- [ ] 需要登录态时优先用 `.netrc` 或 `--netrc-cmd`，避免把密码写进命令行历史。
- [ ] 加了限速与请求间隔，避免给站点造成压力。
- [ ] 下载完成后抽查：文件能播放、有声音、字幕/元数据按预期写入。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/yt-dlp/yt-dlp | 上游仓库（安装与完整文档以它为准） |
| https://github.com/yt-dlp/yt-dlp/wiki/Installation | 上游安装说明（含各包管理器写法） |

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
