---
name: sanjianke-ffmpeg-python
slug: sanjianke-ffmpeg-python
displayName: 三剪客 · FFmpeg 的 Python 绑定
description: "在 Python 里用可读的链式写法拼装 FFmpeg 命令，尤其是多路输入、多路输出和复杂滤镜图（filter graph）这类手写命令行极难维护的场景：提供 input/output/filter/run 的调用方式、自定义滤镜与特殊参数写法，以及音频流丢失、命令拼错等常见排错手段。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "把 FFmpeg 命令行搬进 Python：安装与 FFmpeg 本体依赖、链式语法与滤镜图写法、多输入多输出、特殊参数名与字符串表达式、用 get_args/compile 自查生成的命令，以及音频流被丢、装错包等典型坑。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 内容创作
  - 素材
---

# 三剪客 · FFmpeg 的 Python 绑定

FFmpeg 几乎什么都能干，但它的命令行在滤镜图上会迅速失控——一旦要把几路输入裁剪、拼接、再叠一层水印，那条 `-filter_complex` 字符串就会长到没人敢改。ffmpeg-python 干的事很单纯：**用 Python 把这条命令拼出来**。你按函数链写清楚「输入 → 滤镜 → 输出」，它负责生成对应的命令行参数并调用 FFmpeg。

它是个**纯 Python 封装**，自己不含任何编解码能力，FFmpeg 本体必须另外装好并在 `PATH` 里。它的长处也不是「支持更多格式」——格式多少完全取决于你装的 FFmpeg——而是**让复杂信号图变得可读、可组合、可复用**。

**上游项目**：`ffmpeg-python`　**仓库**：https://github.com/kkroening/ffmpeg-python

## 什么时候用 / 不用

**用它**：

- 要在 Python 流程里跑 FFmpeg，而且**命令是动态生成的**（输入输出路径、时长、码率由程序算出来）。
- 命令里有**复杂滤镜图**：多路输入、裁剪拼接、叠加水印、拆流再合并。
- 想把转码 / 裁剪 / 抽帧这类固定操作**封装成可复用的 Python 函数**，而不是到处拼字符串再 `subprocess` 调用。
- 需要**多输出**：从一个输入同时产出多个文件（比如一次转出不同分辨率或格式）。
- 想在真正执行之前先看看到底会跑哪条命令，用来排查参数拼错的问题。

**不要用它**：

- **机器上没装 FFmpeg 本体**。它明确不负责下载或安装 FFmpeg；装了这个库但没有 `ffmpeg` 可执行文件，一样跑不起来。
- **只是要在终端敲一条固定命令**。直接敲 FFmpeg 更快，没必要中间加一层。
- **需要极高性能或零拷贝流水线**。它最终还是要启动一个 FFmpeg 进程；高吞吐场景请直接用 FFmpeg 或原生编解码库。
- **想要的是「一键完成剪辑」的高级功能**。它只做命令拼装，不做自动剪辑、自动卡点、智能识别这类事情。
- **需要严格的类型安全与官方长期维护承诺**。它是个轻量封装库，接口边界就是老老实实生成参数。

## 安装

### 1. 装 Python 包

```bash
pip install ffmpeg-python
```

从源码装：

```bash
git clone git@github.com:kkroening/ffmpeg-python.git
pip install -e ./ffmpeg-python
```

⚠️ **装错包是最高频的错误**。上游特别说明：请确认装的是 `ffmpeg-python`，**不是** `ffmpeg`，也**不是** `python-ffmpeg`。

### 2. 装 FFmpeg 本体

`ffmpeg-python` 是纯 Python 封装，**不会**替你下载或安装 FFmpeg。FFmpeg 的安装方式按平台而定：

```bash
# Debian / Ubuntu
sudo apt install ffmpeg

# macOS（Homebrew）
brew install ffmpeg
```

Windows 请从 FFmpeg 官方下载页面获取构建版本，并把可执行文件目录加入 `PATH`。

装好之后在终端直接敲 `ffmpeg` 验证：

```bash
ffmpeg
```

出现版本信息就说明 `PATH` 配好了；如果提示 `ffmpeg: command not found`，说明没装成功或者没进 `PATH`。具体版本信息随系统而异，以你本机实际输出为准。

这个库本身**没有官方 Docker 方案**；要在容器里用，自己基于带 FFmpeg 的基础镜像装这个包即可。

## 常用操作

**1. 最短的例子：把视频水平翻转（两种写法等价）**

```python
import ffmpeg

stream = ffmpeg.input('input.mp4')
stream = ffmpeg.hflip(stream)
stream = ffmpeg.output(stream, 'output.mp4')
ffmpeg.run(stream)
```

链式写法读起来更顺：

```python
import ffmpeg

(
    ffmpeg
    .input('input.mp4')
    .hflip()
    .output('output.mp4')
    .run()
)
```

**2. 复杂滤镜图：裁剪拼接后再叠加水印**

手写这条命令的 `-filter_complex` 参数会非常难读，用链式写法是这样的：

```python
import ffmpeg

in_file = ffmpeg.input('input.mp4')
overlay_file = ffmpeg.input('overlay.png')

(
    ffmpeg
    .concat(
        in_file.trim(start_frame=10, end_frame=20),
        in_file.trim(start_frame=30, end_frame=40),
    )
    .overlay(overlay_file.hflip())
    .drawbox(50, 50, 120, 120, color='red', thickness=5)
    .output('out.mp4')
    .run()
)
```

**3. 用内置简写之外的滤镜：`.filter()`**

库内只给一部分常用滤镜做了函数简写，其余滤镜统一走 `.filter()`：

```python
stream = ffmpeg.input('dummy.mp4')
stream = ffmpeg.filter(stream, 'fps', fps=25, round='up')
stream = ffmpeg.output(stream, 'dummy2.mp4')
ffmpeg.run(stream)
```

链式版本：

```python
(
    ffmpeg
    .input('dummy.mp4')
    .filter('fps', fps=25, round='up')
    .output('dummy2.mp4')
    .run()
)
```

**4. 特殊参数名：`:v` / `:a` 这类后缀**

像 `-qscale:v`、`-b:v` 这种带冒号的参数名不能直接当关键字参数写，要用字典展开：

```python
(
    ffmpeg
    .input('in.mp4')
    .output('out.mp4', **{'qscale:v': 3})
    .run()
)
```

**5. 多输入滤镜：把两路流传给同一个滤镜**

```python
main = ffmpeg.input('main.mp4')
logo = ffmpeg.input('logo.png')

(
    ffmpeg
    .filter([main, logo], 'overlay', 10, 10)
    .output('out.mp4')
    .run()
)
```

**6. 多输出滤镜：`.filter_multi_output()` / `.split()`**

拆分出来的多路可以用下标分别引用：

```python
split = (
    ffmpeg
    .input('in.mp4')
    .filter_multi_output('split')
)

(
    ffmpeg
    .concat(split[0], split[1].reverse())
    .output('out.mp4')
    .run()
)
```

这种场景下 `.split()` 是等价的简写；通用写法适用于其他多输出滤镜。

**7. 字符串表达式：直接引用 FFmpeg 的变量名**

需要 FFmpeg 自己求值的表达式，就当字符串传进去：

```python
(
    ffmpeg
    .input('in.mp4')
    .filter('crop', 'in_w-2*10', 'in_h-2*20')
    .input('out.mp4')
)
```

**8. 先看会执行什么命令，再决定跑不跑**

```python
stream = ffmpeg.input('in.mp4').hflip().output('out.mp4')
print(stream.get_args())    # 只列出传给 ffmpeg 的参数
print(stream.compile())     # 第一个元素是可执行文件名
```

实测输出形态如下，`compile()` 比 `get_args()` 多了最前面的可执行文件名：

```
get_args()  -> ['-i', 'in.mp4', '-filter_complex', '[0]hflip[s0]', '-map', '[s0]', 'out.mp4']
compile()   -> ['ffmpeg', '-i', 'in.mp4', '-filter_complex', '[0]hflip[s0]', '-map', '[s0]', 'out.mp4']
```

排查「参数怎么拼成这样」的时候，这两个方法比翻文档快。

**9. 处理音视频两路（避免音频被滤镜丢掉）**

用 `.audio` / `.video` 分别取出一路，各自处理后再合并，是最稳的写法：

```python
input_video = ffmpeg.input('input.mp4')
input_audio = input_video.audio

processed_video = input_video.video.hflip()

(
    ffmpeg
    .output(processed_video, input_audio, 'out.mp4')
    .run()
)
```

具体哪些滤镜会丢音频流属于 FFmpeg 本身的行为，需要对照 FFmpeg 官方滤镜文档确认。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `import ffmpeg` 报导入 / 属性错误 | 装错包了：装成 `ffmpeg` 或 `python-ffmpeg`，而不是 `ffmpeg-python` | 卸载装错的包，改装 `pip install ffmpeg-python` |
| 脚本跑起来报找不到可执行文件 | 这个库是纯封装，FFmpeg 本体没装或不在 `PATH` 里 | 先在终端敲 `ffmpeg` 验证；没有就按平台装好并配置 `PATH` |
| 输出视频没有声音 | 某些 FFmpeg 滤镜会丢掉音频流，这是 FFmpeg 本身的行为 | 用 `.audio` / `.video` 分别引用后重新合并；对照 FFmpeg 官方文档确认该滤镜对音频的影响 |
| 参数名带冒号（`-b:v`、`-qscale:v`）写不出来 | Python 关键字参数不允许冒号 | 用字典展开：`output('out.mp4', **{'qscale:v': 3})` |
| 调 `.filter()` 时提示没有这个属性 | 只有部分常用滤镜有函数简写，其余要走通用入口 | 用 `ffmpeg.filter(stream, '滤镜名', 参数...)`；滤镜名与参数以 FFmpeg 官方滤镜文档为准 |
| 多输出滤镜的结果取不出来 | 多输出要用 `filter_multi_output` 才能拿到可下标引用的对象 | 改用 `.filter_multi_output('split')` 或对应的 `.split()` 简写，再用 `split[0]` / `split[1]` 引用 |
| 命令行为跟预期不符，但看不出哪里错 | 生成的参数是动态拼出来的，肉眼不好判断 | 先 `get_args()` 看参数，再 `compile()` 看完整命令（含可执行文件名），确认无误再 `run()` |
| 路径里有空格或特殊字符导致失败 | 参数是原样传给 FFmpeg 的 | 不要手工拼引号，直接把完整路径作为 Python 字符串传入，交给它处理 |
| 升级 FFmpeg 后原来能跑的脚本报滤镜参数错误 | 滤镜的参数名与可用性随 FFmpeg 版本变化，这个库只做透传 | 对照你当前 FFmpeg 版本的官方滤镜文档核对参数；必要时锁住 FFmpeg 版本 |
| 想调的滤镜在这个库里找不到 | 库内只封装了部分滤镜简写 | 用 `.filter()` 直接按 FFmpeg 的滤镜名调用即可，不必等封装补上 |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 否 | 库本身不联网；只有你自己在流程里下载素材或安装 FFmpeg 时才需要网络 |
| 读取文件 | 是 | 通过 FFmpeg 读取输入的音视频、图片等素材 |
| 写入文件 | 是 | 通过 FFmpeg 写出输出文件，路径由 `output()` 指定 |
| 凭证 | 否 | 不需要账号或 API Key。本 Skill 不内嵌任何密钥 |
| 子进程 / 后台常驻 | 是 | `run()` 会启动 FFmpeg 子进程；长转码任务会持续占用 CPU / GPU 直到结束 |

## 触发场景

- 「用 Python 批量转码一批视频」
- 「把这条复杂滤镜命令改写成 Python」
- 「一次输出多个不同分辨率的版本」
- 「在 Python 里给视频加水印和裁切」
- 「生成的 ffmpeg 命令不对，帮我看看实际拼成了什么」
- 「wrap ffmpeg in python for our pipeline」

## 能力边界

**覆盖**：

- 用 Python 表达式拼装 FFmpeg 调用：输入、输出、滤镜、参数。
- 复杂有向无环滤镜图，包括多输入与多输出场景。
- 常用滤镜的函数简写（如裁剪、翻转、叠加、绘制、拼接、拆流等），以及通过 `.filter()` 调用任意 FFmpeg 滤镜。
- 带冒号的特殊参数名（字典展开）与交给 FFmpeg 求值的字符串表达式。
- 音视频分流处理（`.audio` / `.video`）后再合并。
- 命令自查：`get_args()` 与 `compile()`。
- 链式与逐步两种等价写法。

**不覆盖**：

- 不包含 FFmpeg 本体，也不负责下载或安装它；编解码能力完全取决于你装的 FFmpeg。
- 不做任何自动化的剪辑决策（自动卡点、智能裁切、场景识别等）。
- 不解析媒体文件内容，不是 `ffprobe` 的替代品（需要探测信息就用 `ffprobe`）。
- 不封装 FFmpeg 的全部选项；未封装的部分要自己用通用参数写法或 `.filter()` 表达。
- 不保证跨 FFmpeg 版本的兼容性：滤镜参数随 FFmpeg 变化，它只做透传。
- 不提供图形界面或服务端形态。

## 依赖条件

- Python 环境（用 pip 安装即可；上游 README 未强调特定的最低 Python 版本要求）。
- **FFmpeg 本体**必须已安装且在 `PATH` 中可调用——这是硬前提。
- 安装的包名必须是 `ffmpeg-python`，不要装错成 `ffmpeg` 或 `python-ffmpeg`。
- Windows 上需要从 FFmpeg 官方下载页面获取构建并配置 `PATH`。
- 用 Docker 时需自备带 FFmpeg 的基础镜像。

## 已知限制

- 它只是命令行的封装层：FFmpeg 能做什么由你的 FFmpeg 决定，FFmpeg 的坑它也照旧转达。
- 音频流被滤镜丢弃是 FFmpeg 的固有行为，这个库有意不插手，需要使用者自己处理。
- 内置滤镜简写只是子集，其余必须走 `.filter()`，参数正确性靠使用者对照 FFmpeg 文档保证。
- 上游 README 正文中没有给出确定的版本号与发布日期；本 Skill 也不对 star 数、发布时间作断言，请以仓库页面实时信息为准。
- 该库接口稳定但演进较慢；遇到问题时以仓库 Issue 区与 FFmpeg 官方文档为准。

## 自检清单

- [ ] 在终端敲 `ffmpeg` 能出版本信息，确认 FFmpeg 已装且在 `PATH` 中。
- [ ] `pip show ffmpeg-python` 能查到，确认没装错成 `ffmpeg` / `python-ffmpeg`。
- [ ] 输入文件路径存在且可读；输出目录可写。
- [ ] 涉及滤镜的操作，先 `get_args()` / `compile()` 看生成的命令是否合理。
- [ ] 涉及会丢音频的滤镜时，用 `.audio` / `.video` 分流再合并，并在输出上确认音轨存在。
- [ ] 带冒号的参数用字典展开写法，不要试图当关键字参数。
- [ ] 用到的滤镜名与参数已对照当前 FFmpeg 版本的官方滤镜文档。
- [ ] 长任务注意子进程的退出码与错误输出，不要只看有没有生成文件。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| https://github.com/kkroening/ffmpeg-python | 上游仓库（安装与完整文档以它为准） |

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
