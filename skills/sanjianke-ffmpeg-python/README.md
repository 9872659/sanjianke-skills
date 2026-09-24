# 三剪客 · FFmpeg 的 Python 绑定 Skill

在 Python 里用可读的链式写法拼装 FFmpeg 命令的安装、常用用法与避坑要点

---

## 前置条件

- **FFmpeg 本体已安装且在 `PATH` 中可调用**——这是硬前提。该库是纯 Python 封装，明确不负责下载或安装 FFmpeg。装完在终端敲 `ffmpeg` 能看到版本信息即可。
- **Python 环境**：用 pip 安装即可；上游 README 未强调特定的最低 Python 版本要求。
- **装对包名**：必须是 `ffmpeg-python`，不要装成 `ffmpeg` 或 `python-ffmpeg`。
- **Windows**：从 FFmpeg 官方下载页面获取构建版本，并把可执行文件目录加入 `PATH`。
- **可选**：Docker（自备带 FFmpeg 的基础镜像，再装这个包）。

---

## 使用

主体内容看 `SKILL.md`，那里有六块：一句话定位、什么时候用 / 不用、安装、常用操作、常见坑、能力边界。

最短路径：

```bash
pip install ffmpeg-python
```

```python
import ffmpeg

ffmpeg.input('input.mp4').hflip().output('output.mp4').run()
```

先确认实际会跑哪条命令，再决定执行：

```python
stream = ffmpeg.input('in.mp4').hflip().output('out.mp4')
print(stream.get_args())    # 传给 ffmpeg 的参数
print(stream.compile())     # 含可执行文件名
```

复杂滤镜图用链式写法表达，比手写 `-filter_complex` 可读得多：

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
    .output('out.mp4')
    .run()
)
```

滤镜名与参数以 FFmpeg 官方滤镜文档为准；这个库只做透传。

---

## 依赖

- `ffmpeg-python`（本库本体）
- FFmpeg 可执行文件（**必须单独安装**，不在本库依赖里）
- Python 运行环境
- 可选：Docker 基础镜像（需自带 FFmpeg）

---

## 安全

- 不内嵌任何密钥
- 库本身不联网；`run()` 会启动 FFmpeg 子进程，输入输出路径完全由调用方决定，处理不受信任来源前请自行校验路径
- 输出文件会按 `output()` 指定的路径直接写入或覆盖，注意不要指向重要目录
- 长转码任务会持续占用 CPU / GPU 资源，注意与同机其他任务错开
- 输入的媒体素材版权与授权由使用者自行确认

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`ffmpeg-python`
- 仓库：https://github.com/kkroening/ffmpeg-python

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
