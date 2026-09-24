# 三剪客 · 本地语音转文字与字幕 Skill

把语音识别模型的推理做成一个不依赖框架的 C/C++ 程序，在本机 CPU 上离线跑完，直接产出 SRT / VTT / LRC / JSON 等格式的字幕与文字稿。

---

## 前置条件

- **构建工具链**：CMake 与一个 C/C++ 编译器。
- **模型文件**：仓库不含权重，必须单独下载 ggml 格式模型。`.en` 后缀是英文专用模型，做中文要选多语言版本。模型默认从模型托管站下载，网络不通时需要手动取回文件放到位。
- **音频素材**：命令行例子稳妥支持的是 16-bit WAV。MP3 / MP4 / M4A 等建议先用 FFmpeg 转成 `16000 Hz` 单声道 PCM：`ffmpeg -i input.mp3 -ar 16000 -ac 1 -c:a pcm_s16le output.wav`。
- **内存**：要装得下所选模型。官方对照：tiny ~273 MB、base ~388 MB、small ~852 MB、medium ~2.1 GB、large ~3.9 GB。
- **可选组件**：GPU 后端需要对应驱动与 SDK（CUDA / ROCm / Vulkan）；实时麦克风转写需要 SDL2；卡拉OK视频生成与服务的格式转换需要 FFmpeg。

---

## 使用

最短路径：

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
sh ./models/download-ggml-model.sh base.en     # Windows 用 .\models\download-ggml-model.cmd base.en
cmake -B build && cmake --build build -j --config Release
./build/bin/whisper-cli -f samples/jfk.wav
```

出字幕：

```bash
# 中文素材必须显式指定语言
./build/bin/whisper-cli -m models/ggml-base.bin -f input.wav -l zh -osrt

# 逐词时间戳，做逐字字幕
./build/bin/whisper-cli -m models/ggml-base.bin -f input.wav -l zh -ml 1 -ojf
```

起服务给别的程序调：

```bash
./build/bin/whisper-server -m models/ggml-base.bin --host 127.0.0.1 --port 8080
```

完整参数清单跑 `./build/bin/whisper-cli -h`；六块正文（什么时候用 / 不用、安装、常用操作、常见坑、权限与用途说明、能力边界）见 `SKILL.md`。

---

## 依赖

- **构建**：CMake + C/C++ 编译器。可选加速后端：`GGML_CUDA`、`GGML_HIP`、`GGML_VULKAN`、`GGML_BLAS`、`WHISPER_COREML`、`WHISPER_OPENVINO`、`WHISPER_VITISAI`、`GGML_CANN`、`GGML_MUSA`。
- **模型**：ggml 格式的识别模型（必需）与 VAD 模型（开启 `--vad` 时必需）。量化模型可用仓库自带的 `quantize` 工具自行生成。
- **音频解码**：默认用内置的轻量解码库；更宽的格式支持需以 `WHISPER_COMMON_FFMPEG=yes` 编译，并安装 FFmpeg 开发库。
- **运行时绑定**（可选）：官方提供 JavaScript、Go、Rust、Java、.NET、Python、Swift、Unity 等绑定，另有独立维护的第三方封装。
- **硬件**：CPU 即可运行；有 NVIDIA / AMD / 支持 Vulkan 的显卡或特定加速卡时可显著提速。

---

## 安全

- 不内嵌任何密钥，本包只有文字说明。
- 转写全程可离线完成：模型下载完成后，推理不需要任何网络连接，音频不会离开本机。
- `whisper-server` 会接收用户上传的文件，`--convert` 还会调用 FFmpeg 做格式转换。官方对该示例给出了明确的安全警告：**不要用管理员权限运行**，放在沙箱或内网中，并对上传做大小限制与输入校验。
- `-owts` 会生成一个 shell 脚本，脚本内容是拼好的 FFmpeg 命令。执行前先看一眼生成结果，不要无脑 `source` 来源不明的脚本。
- 从第三方地址下载模型文件时，注意核对来源与文件完整性。
- 生成的中间文件、模型文件体积较大，注意别误提交进版本库或打进发布包。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`whisper.cpp`
- 仓库：https://github.com/ggerganov/whisper.cpp
- 模型说明：https://github.com/ggerganov/whisper.cpp/blob/master/models/README.md
- HTTP 服务示例：https://github.com/ggerganov/whisper.cpp/tree/master/examples/server

---

## 许可证

MIT，见 `LICENSE.md`。

> 上游项目自身亦以 MIT 许可证发布；具体条款以仓库中的许可证文件为准。

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
