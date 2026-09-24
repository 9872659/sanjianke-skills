# 三剪客 · 跨平台 AI Agent 应用 Skill

开源跨平台 AI Agent 客户端应用的构建、配置与二次开发指南

---

## 前置条件

| 项 | 要求 |
|---|---|
| 构建 iOS 端 | macOS（Apple Silicon 强烈推荐）+ 含 iOS SDK 的 Xcode |
| 构建 Android 端 | JDK 17、Android SDK（compileSdk 36 / targetSdk 35 / minSdk 26）、Android NDK r28+、CMake 3.22.1 |
| 通用依赖 | Homebrew 的 `ninja`、`llvm`、`libarchive`、`pkg-config`；Python 3 + `meson`；`curl`、`tar`、`make`、`awk`、`sed` |
| 网络 | 可访问 GitHub 与 Alpine 官方镜像（首次构建需下载 minirootfs） |
| 时间与磁盘 | 首次构建约 **30～60 分钟**；需预留充足的磁盘空间用于原生依赖产物 |

首次构建必须按依赖顺序执行 `deps/` 下的脚本，并带 `--recurse-submodules` 克隆。细节见 `references/01-build-deploy.md`。

---

## 使用

1. 阅读 `SKILL.md`，按「工作流路由」表选择要看的参考文件。
2. 只想把项目跑起来 → `references/01-build-deploy.md`。
3. 想知道它有什么能力、怎么接自己的模型 → `references/02-features-config.md`。
4. 想改代码或正在排错 → `references/03-extend-troubleshoot.md`。

最小可用路径：

```sh
git clone --recurse-submodules <OpenMinis 仓库地址>
cd OpenMinis

# iOS
./deps/build_lame.sh && ./deps/build_ffmpeg.sh
./deps/build_ish.sh && ./deps/prepare_alpine_rootfs.sh
open src/ios/Minis.xcodeproj

# Android（需 NDK r28+）
./deps/build_proot.sh && ./scripts/prepare_android_sandbox.sh
cd src/android && ./gradlew :app:assembleDebug
```

验收要求：在应用内**实际执行一条命令并确认退出码为 0**。沙箱能启动不等于能执行。

---

## 依赖

本 Skill 自身只依赖阅读与文档能力，不引入任何运行时库、不调用任何外部接口。

它所描述的操作对象（上游开源工程）依赖：macOS / Xcode、JDK 17、Android SDK 与 NDK r28+、CMake 3.22.1，以及构建期从源码编译的 iSH、PRoot、FFmpeg、LAME 与 Alpine minirootfs。完整版本表见 `SKILL.md` 的「依赖条件」。

---

## 安全

- 不内嵌任何密钥
- 不读取、不存储、不转发使用者的模型 API Key 或 OAuth 凭证；所有凭证都在使用者一侧
- 不代理任何网络请求，也不代替使用者向任何模型供应商发起调用
- 构建过程会从 GitHub 与 Alpine 官方镜像下载源码与 rootfs，请自行确认网络可达与合规要求
- 需要自行提供 `ANTHROPIC_OAUTH_IDENTIFIER_PROMPT` 时，该内容由使用者自行判断合规性，本 Skill 不提供该值

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：OpenMinis（GPL-3.0）

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
