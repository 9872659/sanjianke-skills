# 三剪客 · 离线语音识别与合成的 ONNX 运行时 Skill

sherpa-onnx：离线语音识别与合成的 ONNX 运行时 的安装、常用命令与避坑要点

---

## 前置条件

本 Skill 为工具类技能包，按 SKILL.md 的「安装」一节准备运行环境即可。

## 使用

正文的「安装」与「常用操作」两节是最短可用路径。

```bash
./bin/sherpa-onnx-offline \
  --tokens=/path/to/tokens.txt \
  --encoder=/path/to/encoder.onnx \
  --decoder=/path/to/decoder.onnx \
  --joiner=/path/to/joiner.onnx \
  --num-threads=2 \
  /path/to/audio.wav
```

## 依赖

- 操作系统与架构：Linux（x64、aarch64）、macOS（universal2）、Windows（x64）、Android、iOS 及部分嵌入式平台，按官方发布物选择
- 运行时：ONNX Runtime（预编译包已内置对应版本，**不需要**另外装 PyTorch 或 TensorFlow）
- 模型文件：需另行下载，并按模型类型准备对应的词表/词典/规则文件；模型与二进制的版本要匹配
- 音频输入：单声道、16 位 PCM 的 wav 最稳；VAD 与麦克风链路要求 16 kHz，其它程序对采样率的容忍度更高，以各程序 `--help` 为准
- 可选系统运行库：麦克风场景需要 PortAudio；Linux 上部分功能需要 ALSA 相关模块
- 从源码编译时：CMake 与较新的 C/C++ 编译器；Go 绑定需要 CGO；可选功能要显式打开对应开关
- 账号/Key：不需要

## 安全

- 不内嵌任何密钥
- 不主动把任何内容发往外部地址
- 若正文涉及联网或读写文件，权限范围已在 SKILL.md 的「权限与用途说明」中逐项列明
- 能力边界见 SKILL.md 的「能力边界」一节

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`sherpa-onnx`
- 仓库：https://github.com/k2-fsa/sherpa-onnx

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
