# 三剪客 · 音视频转码与处理 Skill

FFmpeg：音视频转码与处理 的安装、常用命令与避坑要点

---

## 前置条件

- 一套可用的 FFmpeg 构建（建议同时具备 `ffmpeg` 与 `ffprobe`，两者通常一起分发）。
- `ffmpeg`、`ffprobe` 在 `PATH` 里可直接调用；装完用 `ffmpeg -version` 验证。
- 确认这份构建**包含你要用的编码器与滤镜**：`ffmpeg -encoders`、`ffmpeg -filters`、`ffmpeg -hwaccels`。发行版构建与静态构建包含的编码器不同，这是「别人能跑我不能跑」的最常见原因。
- 用硬件编码时额外需要：对应显卡与已安装的驱动（NVIDIA / Intel / AMD 各自的加速后端），并确认构建编进了该后端。
- 磁盘空间：至少能放下输出文件，批量任务要按总量预留；转码过程本身也会写临时数据。
- 无账号、无 Key、无需联网（除你要访问网络源或推流的情况）。

---

## 使用

最短跑通路径：

1. 确认工具可用：

   ```bash
   ffmpeg -version
   ```

2. 先探测输入，别凭想象写参数：

   ```bash
   ffprobe -v error -show_entries stream=index,codec_name,codec_type,width,height -of default=noprint_wrappers=1 input.mp4
   ```

3. 只想换封装、不动编码（最快最安全）：

   ```bash
   ffmpeg -i input.mp4 -c copy output.mkv
   ```

4. 要压体积或换编码格式：

   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k output.mp4
   ```

5. 给网页播放用的 mp4，把索引前置：

   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -crf 23 -movflags +faststart output.mp4
   ```

6. 跑完一定抽查结果（时长、流数量、能播放）：

   ```bash
   ffprobe -v error -show_format -show_streams output.mp4
   ```

7. 批量目录时用脚本循环调用，单个文件失败不影响整批：

   ```bash
   for f in *.mkv; do ffmpeg -v error -i "$f" -c:v libx264 -crf 23 -c:a aac "out/${f%.mkv}.mp4" || echo "失败: $f"; done
   ```

参数细节以 `ffmpeg -h full` 与官方文档为准，不同版本的可选项有增删，不要照搬旧教程里的写法。

---

## 依赖

- **运行时**：FFmpeg 本体（含 `ffprobe`）。包管理器安装即可，或使用静态构建包。
- **编码/滤镜**：取决于构建配置。专利受限编码器是否被编入，各发行版与各构建不同，动手前先查。
- **硬件编码（可选）**：需要对应 GPU 与驱动，且构建需包含 `nvenc` / `qsv` / `amf` / `vaapi` 等后端。纯软件编码不需要 GPU。
- **字体（可选）**：烧录字幕或画文字水印时需要系统字体可被找到。
- **无模型、无 API Key 依赖**：本 Skill 不涉及大模型调用；纯 CPU 或本地 GPU 转码。

---

## 安全

- 不内嵌任何密钥；示例里没有需要填写的凭证。
- 输出文件会**直接覆盖同名文件**。批量脚本里务必用独立输出目录，或先加 `-n` 之类的保护再确认。
- 参数来自外部输入（文件名、时长、滤镜字符串）时要做校验：滤镜图字符串会被解析执行，不要把不可信字符串原样拼进命令。
- 处理来源不明的媒体文件时，注意解码器历史上的安全漏洞——保持 FFmpeg 为较新版本，别用多年未更新的旧构建。
- 读取网络地址（`http(s)://`）或推流时才会联网；纯本地转码建议在不需要网络的环境里跑。
- 处理他人素材与版权内容前，先确认你拥有相应授权；转码不改变版权归属。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`FFmpeg`
- 仓库：https://github.com/FFmpeg/FFmpeg

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
