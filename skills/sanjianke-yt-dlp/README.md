# 三剪客 · 全网视频音频下载器 Skill

yt-dlp：从上千个站点下载视频与音频，按画质/编码挑格式、合并音视频轨、抽音频、抓字幕、批量备档。

---

## 前置条件

- Python 3.10+（CPython）或 3.11+（PyPy）；若用官方发行二进制，Linux/BSD 单文件方式仍需本机 Python。
- 强烈建议同时安装 `ffmpeg` 与 `ffprobe`：合并独立音视频轨、抽音频、按章节切分、重封装都依赖它们。需要的是 ffmpeg **可执行文件**，不是 PyPI 上同名的 `ffmpeg` 包。
- 站点完整支持（尤其视频站点）按官方说明还需要 `yt-dlp-ejs` 与一个受支持的 JavaScript 运行时（deno 优先且默认启用，其次 node、quickjs、bun）。
- 若目标内容需要登录才能解析，需准备浏览器 Cookie 或一个 `.netrc` 文件。
- 下载前请先确认你对该内容拥有下载与二次使用的权利。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
# 1) 安装（任选一种）
python3 -m pip install -U "yt-dlp[default]"     # Windows 用 python 或 py
winget install yt-dlp                            # Windows 包管理器
brew install yt-dlp                              # macOS / Linux（Homebrew）

# 2) 看这个视频有哪些格式
yt-dlp -F "https://example.com/watch?v=xxxx"

# 3) 下最高质量（音视频分轨时自动合并，需 ffmpeg）
yt-dlp "https://example.com/watch?v=xxxx"

# 4) 只要音频，转 mp3
yt-dlp -x --audio-format mp3 "https://example.com/watch?v=xxxx"
```

批量去重的写法：

```bash
yt-dlp --download-archive done.txt \
       --sleep-requests 1 --sleep-interval 5 \
       -P "D:/素材" -o "%(title)s.%(ext)s" \
       "https://example.com/playlist?list=xxxx"
```

命令行选项会随版本增减，`-f` 的格式码更是逐个视频不同；执行前请以当前版本的 `yt-dlp --help` 与上游仓库 README 的内容为准。

---

## 依赖

- Python 3.10+ / PyPy 3.11+（用官方二进制时自带运行时）
- ffmpeg + ffprobe（合并、抽音频、切分、重封装的前提）
- yt-dlp-ejs + 一个 JavaScript 运行时（完整站点支持）
- 可选：`curl_cffi`（`curl-cffi` extra，模拟浏览器 TLS 指纹）、`mutagen` 或 `AtomicParsley`（部分格式的封面嵌入）、`pycryptodomex`（AES-128 HLS 解密）、`secretstorage`（Linux 下解密 Chromium 系 Cookie）

---

## 安全

- 不内嵌任何密钥
- 需要登录态时优先用 `.netrc` 或 `--netrc-cmd`，避免把账号密码写进命令行参数、留在 shell 历史里
- `--cookies-from-browser` 会读取本机浏览器的 Cookie 数据库，属于敏感数据访问；只在必要时使用，并注意后续清理导出的 cookies 文件
- 下载内容可能受版权与站点条款限制：工具可用不代表获得授权，商用与二次分发前须自行确认权利来源
- `--exec` 会在下载完成后执行自定义命令，只应挂自己编写的命令，不要拼接来自外部的字符串
- 批量抓取请加 `--sleep-requests` / `--sleep-interval` 控制频率，避免对目标站点造成压力
- 只从官方发行页或官方包管理器渠道获取二进制；不同来源的构建没有经过同一套校验

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`yt-dlp`
- 仓库：https://github.com/yt-dlp/yt-dlp

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
