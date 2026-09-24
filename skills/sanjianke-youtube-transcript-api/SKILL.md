---
name: sanjianke-youtube-transcript-api
slug: sanjianke-youtube-transcript-api
displayName: 三剪客 · YouTube 字幕与转写抓取
description: "不用无头浏览器就能按视频 ID 取回 YouTube 人工字幕或自动生成字幕，支持多语言优先级、翻译、格式化导出与代理绕行。含 Python API、命令行、代理配置与常见坑。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "给一个视频 ID，把它的字幕/转写按你要的语言取回来，并导出成纯文本、JSON、SRT 或 WebVTT：安装、API 与命令行用法、代理绕行和常见报错处理。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 素材
---

# 三剪客 · YouTube 字幕与转写抓取

做海外视频二创、素材检索、跨语言内容整理时，最头疼的一步是「先把人家说了什么拿到手」。自己搭无头浏览器去点开字幕面板，既慢又脆。这个库把这件事收成了一次函数调用：给视频 ID，直接拿回带时间轴的字幕片段列表，人工字幕和自动生成字幕都能取。

它原样保留了每条字幕的起始时间与持续时长，所以拿回来的东西可以直接当剪辑打点的时间依据——这是纯文本抓取工具给不了的。

**上游项目**：`youtube-transcript-api`　**仓库**：https://github.com/jdepoix/youtube-transcript-api

## 什么时候用 / 不用

**用它**：

- 用户说「把这个 YouTube 视频的文案 / 字幕扒下来」，你手上能拿到视频 ID。
- 需要**带时间轴**的字幕数据，用于卡点剪辑、分镜打点或对齐配音。
- 视频有**多语言字幕**，要按优先级取（比如优先德语、没有就退英语）。
- 只要**自动生成字幕**，或者反过来只要**人工校对过的字幕**。
- 要把字幕转成 **SRT / WebVTT / JSON / 纯文本** 再喂给下游流程。
- 需要把某条字幕**翻译**成另一种语言。

**不要用它**：

- **拿不到视频 ID、只有页面内容或标题**。它按 ID 取数，不做搜索、不做频道遍历、不做推荐流抓取。
- **要下载视频或音频本体**。它只取字幕轨，媒体下载是另一个工具的活。
- **给的是受限视频**（年龄限制等）。基于 Cookie 的认证在当前实现里已经不可用，这类视频取不到。
- **部署在云主机上批量跑**。YouTube 屏蔽了大量云厂商 IP 段，很容易直接撞上封锁异常。
- **要抓取平台上的其他信息**（评论、点赞、观看量）。它的能力范围就是字幕轨。
- **希望它是稳定契约**。上游明确说明它调用的是未公开接口，随时可能失效，不能当长期稳定依赖来设计系统。

## 安装

```bash
pip install youtube-transcript-api
```

装完有两条用法：作为库嵌进程序，或者直接用命令行工具。

## 常用操作

**1. 最小取字幕：拿视频 ID，不要给网址**

对 `https://www.youtube.com/watch?v=12345` 这样的链接，要传的 ID 是 `12345`。

```python
from youtube_transcript_api import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()
ytt_api.fetch(video_id)
```

默认取英语字幕。返回的是一个 `FetchedTranscript` 对象，带 `snippets`、`video_id`、`language`、`language_code`、`is_generated` 等字段，每条片段有 `text`、`start`、`duration`。这个对象基本按列表用：可迭代、可索引、有长度。

```python
ytt_api = YouTubeTranscriptApi()
fetched_transcript = ytt_api.fetch(video_id)

for snippet in fetched_transcript:
    print(snippet.text)

last_snippet = fetched_transcript[-1]
snippet_count = len(fetched_transcript)
```

要原始字典列表就调 `to_raw_data()`：

```python
[
    {"text": "Hey there", "start": 0.0, "duration": 1.54},
    {"text": "how are you", "start": 1.54, "duration": 4.16},
]
```

**2. 指定语言优先级，或保留 HTML 格式标记**

`languages` 是按优先级降序的列表，前面的取不到才往后退；只想要一种语言也要写成列表。想保留 `<i>`、`<b>` 这类格式元素就加 `preserve_formatting`。

```python
# 先德语，失败再退英语
YouTubeTranscriptApi().fetch(video_id, languages=['de', 'en'])

# 只接受德语
YouTubeTranscriptApi().fetch(video_id, languages=['de'])

# 保留斜体、粗体等格式标记
YouTubeTranscriptApi().fetch(video_id, languages=['de', 'en'], preserve_formatting=True)
```

**3. 先列出可用字幕，再按类型挑**

不确定有哪些语言时先列清单。默认行为是：如果请求的语言同时有人工和自动生成，优先选人工的；要打破这个默认就用下面的类型过滤方法。每个 `Transcript` 对象都带元信息：`video_id`、`language`、`language_code`、`is_generated`、`is_translatable`、`translation_languages`，并可用 `.fetch()` 取数据。

```python
from youtube_transcript_api import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()
transcript_list = ytt_api.list(video_id)

for transcript in transcript_list:
    print(
        transcript.video_id,
        transcript.language,
        transcript.language_code,
        transcript.is_generated,
        transcript.is_translatable,
        transcript.translation_languages,
    )

# 按语言挑
transcript = transcript_list.find_transcript(['de', 'en'])
# 只要人工创建的
transcript = transcript_list.find_manually_created_transcript(['de', 'en'])
# 只要自动生成的
transcript = transcript_list.find_generated_transcript(['de', 'en'])
```

**4. 翻译字幕**

平台自带字幕自动翻译能力，这里也能用上：`translate()` 返回一个新的 `Transcript` 对象。

```python
transcript = transcript_list.find_transcript(['en'])
translated_transcript = transcript.translate('de')
print(translated_transcript.fetch())
```

**5. 用格式化器导出成 SRT / WebVTT / JSON / 纯文本**

```python
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter, SRTFormatter, WebVTTFormatter, TextFormatter

ytt_api = YouTubeTranscriptApi()
transcript = ytt_api.fetch(video_id)

# 转成 JSON 字符串；因为底层是 json.dumps，还能透传 indent 之类的参数
json_formatted = JSONFormatter().format_transcript(transcript)
json_formatted = JSONFormatter().format_transcript(transcript, indent=2)

# 其他内置格式
srt_formatted = SRTFormatter().format_transcript(transcript)
vtt_formatted = WebVTTFormatter().format_transcript(transcript)
text_formatted = TextFormatter().format_transcript(transcript)

with open('your_filename.srt', 'w', encoding='utf-8') as f:
    f.write(srt_formatted)
```

内置格式化器有 JSON、PrettyPrint、Text、WebVTT、SRT 五种。想要自己的格式就继承基类，实现 `format_transcript` 和 `format_transcripts` 两个方法，都返回字符串。

**6. 命令行：一次取多个、切语言、换格式**

```bash
# 基本用法，结果打到终端
youtube_transcript_api <first_video_id> <second_video_id>

# 指定语言顺序
youtube_transcript_api <first_video_id> --languages de en

# 排除自动生成 / 排除人工创建
youtube_transcript_api <first_video_id> --languages de en --exclude-generated
youtube_transcript_api <first_video_id> --languages de en --exclude-manually-created

# 输出 JSON 并落盘
youtube_transcript_api <first_video_id> --languages de en --format json > transcripts.json

# 翻译
youtube_transcript_api <first_video_id> --languages en --translate de

# 先看有哪些语言
youtube_transcript_api --list-transcripts <first_video_id>
```

**7. 撞上 IP 封锁时走代理**

云主机上跑大概率遇到封锁异常，本机请求太频繁也会。代理配置在库和命令行两边都支持：

```python
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig, GenericProxyConfig

# 住宅轮换代理（需要自备该服务商的账号与套餐）
ytt_api = YouTubeTranscriptApi(
    proxy_config=WebshareProxyConfig(
        proxy_username="<proxy-username>",
        proxy_password="<proxy-password>",
        filter_ip_locations=["de", "us"],   # 可选：限定出口 IP 的地区
    )
)
ytt_api.fetch(video_id)

# 任意 HTTP/HTTPS/SOCKS 代理
ytt_api = YouTubeTranscriptApi(
    proxy_config=GenericProxyConfig(
        http_url="http://user:pass@my-custom-proxy.org:port",
        https_url="https://user:pass@my-custom-proxy.org:port",
    )
)
```

```bash
# 命令行走代理
youtube_transcript_api <first_video_id> --webshare-proxy-username "username" --webshare-proxy-password "password"
youtube_transcript_api <first_video_id> --http-proxy http://user:pass@domain:port --https-proxy https://user:pass@domain:port
```

用了代理也不保证不被封：对方永远可以封掉代理的 IP，所以要用能轮换地址池的方案。

**8. 自定义 HTTP 会话**

初始化时它会建一个 `requests.Session` 供所有请求复用（这样能缓存 Cookie）。想共享 Cookie、换默认头、指定证书文件，就自己传一个进去：

```python
from requests import Session

http_client = Session()
http_client.headers.update({"Accept-Encoding": "gzip, deflate"})
http_client.verify = "/path/to/certfile"

ytt_api = YouTubeTranscriptApi(http_client=http_client)
ytt_api.fetch(video_id)

# 两个实例共享同一个会话，Cookie 就通了
ytt_api_2 = YouTubeTranscriptApi(http_client=http_client)
```

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 传了整条视频网址却报取不到视频 | 接口收的是视频 ID，不是 URL | 从链接里把 `v=` 后面的 ID 抠出来；`https://www.youtube.com/watch?v=12345` 的 ID 就是 `12345` |
| 报请求被封锁 / IP 被封锁 | 对方屏蔽了大量云厂商 IP 段；本机请求太频繁也会触发 | 配轮换住宅代理或通用代理；别在无代理的云主机上做高频批量 |
| 明明有字幕却拿不到 | 可能只存在自动生成字幕而你要求了人工字幕，或者目标语言根本没有 | 先 `list()` / `--list-transcripts` 看清单，再决定语言顺序与字幕类型过滤 |
| 升级后取值方式全变了 | 较新版本改成了「先实例化、再 `.fetch()`」的对象式接口，老的类方法式写法不再适用 | 按当前官方 README 的写法改；这个库有过一次明显的接口大改，迁移时别只改一半 |
| 视频 ID 以连字符开头时命令报错 | 命令行把它当成了参数名 | 用反斜杠转义，例如 `youtube_transcript_api "\-abc123"` |
| 想给受限视频做认证 | 平台接口近期变更已让基于 Cookie 的认证失效，官方说明该功能当前不可用 | 换其他可行来源；不要指望 `--cookies` 参数能解决 |
| 拿到的文本里混着 `<i>`、`<b>` 标签 | 默认会剥掉这些格式元素，但你传了保留格式的开关，或者用了原始数据通道 | 不需要格式就别开保留开关；需要干净文本时用纯文本格式化器输出 |
| 输出 JSON 时中文变成转义序列 | 底层 JSON 序列化的默认行为 | 按底层序列化函数的参数调整（例如 `ensure_ascii`），格式化器支持透传关键字参数 |
| 哪天突然整个不能用了 | 它调用的是未公开接口，对方随时可能改 | 别把它当稳定契约；在业务里做降级与重试，并关注上游仓库的更新 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 访问视频平台换取字幕轨数据；启用代理时全部请求经代理转发 |
| 读取文件 | 否 | 命令行传 Cookie 文件的参数在当前实现下不可用；本 Skill 常规用法不读本地文件 |
| 写入文件 | 否 | 输出走标准输出或由调用方自行落盘（重定向、写文件都在你的脚本里） |
| 凭证 | 视情况 | 使用代理服务商时需要其账号与用户名密码；这些凭据由你自行管理与注入，本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 否 | 每次调用都是短时网络请求，不需要常驻进程 |

## 触发场景

- 「把这个 YouTube 视频的字幕扒下来」
- 「这个视频有没有中文字幕，先帮我列一下有哪些语言」
- 「要它自动生成的那版字幕，别要人工的」
- 「把字幕导成 srt，我要拿去剪片」
- 「把这几个视频的字幕批量取回来存成 JSON」
- 「字幕翻译成德语再给我」
- 「在服务器上跑一直报被封，怎么办」

## 能力边界

**覆盖**：

- 按视频 ID 取回字幕/转写片段，含文本、起始时间、持续时长。
- 人工字幕与自动生成字幕两条来源，并可分别过滤。
- 多语言优先级选择、可用语言清单查询。
- 字幕自动翻译（走平台自带能力）。
- 格式化导出：JSON、PrettyPrint、Text、WebVTT、SRT，也可以自定义格式化器。
- 通过住宅轮换代理或通用 HTTP/HTTPS/SOCKS 代理绕开 IP 封锁。
- 自定义 HTTP 会话（共享 Cookie、改请求头、指定证书）。
- 库与命令行两种使用形态，命令行支持一次传多个视频 ID。

**不覆盖**：

- 不做视频/音频下载，不处理媒体流本身。
- 不做视频搜索、频道遍历、播放列表解析。
- 不抓评论、点赞、观看量等平台元数据。
- 当前不支持受限视频的 Cookie 认证。
- 没有无头浏览器兜底——这是它的设计取向（轻量），也意味着平台结构一改就可能受影响。
- 不保证长期可用性：上游明确说用的是未公开接口。

## 依赖条件

- Python 环境，通过 pip 安装。
- 运行环境能访问对应视频平台；网络受限时需要自备代理服务。
- 若使用代理功能，需要代理服务商提供的用户名与密码（或自建代理地址）。
- 从源码开发需要 Poetry 与相关任务运行器，并按仓库说明装测试与开发依赖组；日常使用不需要这些。

## 已知限制

- 调用未公开接口，随时可能因对方改动而失效，稳定性不由使用方掌控。
- 云厂商 IP 段被大面积封锁，服务器端批量使用必须配代理，成本与复杂度都在使用方。
- Cookie 认证功能当前不可用，受限视频取不到。
- 字段与类名在历史版本间发生过破坏性变化，老代码迁移要整体核对。
- 具体版本号、发布日期与 star 数请以仓库页面实时信息为准，此处不做断言。

## 自检清单

- [ ] 传给接口的是视频 ID，不是完整网址。
- [ ] 明确要人工字幕还是自动生成字幕，必要时先列清单确认。
- [ ] `languages` 传的是列表，且按真实优先级排好序。
- [ ] 需要保留 `<i>`、`<b>` 之类格式时才开保留开关。
- [ ] 输出落盘时指定了文件扩展名与目标编码。
- [ ] 命令行里以连字符开头的视频 ID 已转义。
- [ ] 批量任务前先确认出口 IP 是否会被封锁，必要时配好代理并确认凭据从环境注入、不写进代码。
- [ ] 业务侧准备了失败降级路径，不把输出当成永久可用的数据源。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/jdepoix/youtube-transcript-api | 上游仓库（安装与完整文档以它为准） |

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
