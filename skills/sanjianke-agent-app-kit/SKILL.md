---
name: sanjianke-agent-app-kit
slug: sanjianke-agent-app-kit
displayName: 三剪客 · 跨平台 AI Agent 应用
description: "开源跨平台 AI Agent 客户端应用的构建、配置与二次开发指南。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "拆解 OpenMinis 这类端侧 AI Agent 客户端：iOS/Android 双端原生架构、内置 Linux 沙箱、模型接入与权限体系、从零构建与排错，以及技能包与二次开发路径。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 多智能体
  - 应用编排
---

# 三剪客 · 跨平台 AI Agent 应用

开源跨平台 AI Agent 客户端应用的构建、配置与二次开发指南。

OpenMinis 把大模型装进手机，同时在手机里塞进一个完整的 Linux 沙箱——模型能装包、跑脚本、操作真实文件，还能调用日历、健康、蓝牙这类系统能力。本 Skill 帮你把它从源码跑起来、按自己的模型接好、并且改得动。

它适合三类场景：评估「端侧 AI Agent 客户端」这个产品形态到底怎么落地；在本地从零构建 iOS / Android 双端并打包；在别人已经写好的骨架上接入自建模型网关、增加一项系统能力或自定义技能包。

需要先接受一个前提：这个项目不是「打开工程按运行」。它把 iSH、PRoot、FFmpeg、LAME 和 Alpine rootfs 全部做成**构建期从源码编译**，不做二进制预置。第一次构建要排好依赖顺序，跳一步就会在链接阶段炸出很难懂的报错。本 Skill 的第一份参考文件就是为这件事写的。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 申请 | 克隆上游仓库与 git 子模块；下载 Alpine aarch64 minirootfs；应用运行时访问你自行配置的模型供应商接口 |
| 读取文件 | 申请 | 读取仓库源码、`deps/` 下的原生依赖构建脚本、Xcode 与 Gradle 工程配置、`docs/specs/` 规格文件 |
| 写入文件 | 申请 | 生成 `ProviderCustomization.xcconfig`、`provider-customization.properties` 等构建期配置文件；落地 `deps/libs/`、`deps/frameworks/`、`assets/`、`jniLibs/` 等构建产物 |
| 凭证 | 不申请 | 本 Skill 自身不读取、不存储、不转发任何密钥；模型 API Key 与 OAuth 凭证由你在应用内或本地配置文件中自行提供 |
| 子进程 / 后台常驻 | 申请 | 执行 `git`、`brew`、`pip3`、`deps/*.sh`、`xcodebuild`、`./gradlew` 等命令；首次构建属于长时任务，会持续占用 CPU 与磁盘 |

补充说明：

- 本 Skill 不内嵌任何第三方服务的 API Key、Token 或账号，所有凭证都在使用者一侧。
- 正文中的 `api.a7w.cn` 等链接属于「三剪客」自有服务，与本 Skill 的构建和排错流程**没有强制依赖**，按需取用即可。
- 构建过程会向 GitHub 与 Alpine 官方镜像发起下载，请自行确认网络可达与合规要求。

## 触发场景

- 「我想在手机上跑一个自己的 AI Agent，有哪些开源客户端？帮我看看它到底怎么实现的。」
- 「OpenMinis 这个项目怎么从源码编译到 iPhone / Android 上？步骤是什么？」
- 「Android 端能装能启动，但一执行命令就报 `[Shell not running]`，从哪查？」
- 「我要把模型换成自建网关 / 中转站，得改哪些配置？」
- 「想让 Agent 能读写我的日历、提醒事项和健康数据，需要动哪一层？」
- 「iOS 模拟器编译报链接错误，说 object file built for 'iOS'，什么原因？」

## 快速开始

先克隆，**必须带子模块**——iSH 与 PRoot 两个 fork 是子模块，漏掉会在原生构建阶段失败：

```sh
git clone --recurse-submodules https://github.com/OpenMinis/OpenMinis.git
cd OpenMinis
```

已经克隆过但忘了 `--recurse-submodules`：

```sh
git submodule update --init --recursive
```

构建期配置模板要先复制一份，否则部分功能会在运行时抛缺值异常（留空也能编译通过）：

```sh
cp src/ios/Configs/ProviderCustomization.xcconfig.example \
   src/ios/Configs/ProviderCustomization.xcconfig
cp src/android/app/provider-customization.properties.example \
   src/android/app/provider-customization.properties
```

iOS —— **顺序不能换**，FFmpeg 要链接 LAME，LAME 不存在时 MP3 编码会被静默丢弃：

```sh
./deps/build_lame.sh              # → deps/lame-build/lib/libmp3lame.a
./deps/build_ffmpeg.sh            # → deps/frameworks/*.framework（LGPL 配置）
./deps/build_ish.sh               # → deps/libs/*.a、deps/include/、deps/resources/
./deps/prepare_alpine_rootfs.sh   # → deps/resources/alpine-rootfs.zip
open src/ios/Minis.xcodeproj
```

Android —— 需要 NDK r28+：

```sh
./deps/build_proot.sh                  # → assets/proot-aarch64、jniLibs/arm64-v8a/*.so
./scripts/prepare_android_sandbox.sh   # → assets/alpine-minirootfs.tar.gz
cd src/android && ./gradlew :app:assembleDebug
```

首次构建请按 **30～60 分钟**做预算；产物落盘后会被缓存，后续构建很快。详细工具链要求、逐脚本产出物清单和失败模式，见 `references/01-build-deploy.md`。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 从零编译 iOS / Android 双端、配工具链、打包出包 | `references/01-build-deploy.md` |
| 搞清有哪些功能、怎么接模型、`minis://` 资源怎么用、权限怎么给 | `references/02-features-config.md` |
| 改代码加功能、理解源码结构、按症状排错 | `references/03-extend-troubleshoot.md` |

## 能力边界

**覆盖**：

- 上游项目的双端技术栈、模块划分与沙箱实现思路的**可操作拆解**。
- iOS 与 Android 的完整首次构建流程，含工具链版本、脚本执行顺序、各步产出物路径。
- 构建期配置注入（供应商定制文件）与 `ANTHROPIC_OAUTH_IDENTIFIER_PROMPT` 这类特殊变量的作用与填法。
- 模型供应商接入方式（API Key 与账号登录两条路径）、系统能力清单、`minis://` 资源寻址模型。
- 常见构建失败与运行时失败的症状→原因→处置对应关系。

**不覆盖**：

- 不代为申请任何模型账号、不发任何 API Key，也不做请求代理。
- 不提供源码分发或二进制分发；正文与参考文件均为原创描述，不含上游代码。
- 不覆盖 Windows 侧构建 iOS 端——该路径在物理上不存在，见「已知限制」。
- 不承诺上游工程的兼容性；上游为闭源开发树的镜像，结构与脚本可能随时变动。
- 不涉及上架流程、商店审核合规、企业签名与分发的法律意见。
- 不做性能调优或耗电优化的保证，相关设计文档需以上游实际内容为准。

## 依赖条件

| 项 | 要求 |
|---|---|
| 操作系统（iOS 端） | macOS，Apple Silicon 强烈推荐（模拟器构建另有约束） |
| Xcode | 需含 iOS SDK；工程目标为 **iOS 26.2** 与 **Swift 6.0** |
| Homebrew 包 | `brew install ninja llvm libarchive pkg-config` |
| Python | Python 3 + `pip3 install meson`（`llvm` 编译 guest VDSO，`libarchive` 解包 rootfs，Meson/Ninja 构建 iSH 内核） |
| 操作系统（Android 端） | macOS / Linux / Windows 均可 |
| JDK | **17**（`sourceCompatibility` / `targetCompatibility` 均为 17） |
| Android SDK | compileSdk **36**、targetSdk **35**、minSdk **26** |
| Android NDK | **r28+**，设置 `$ANDROID_NDK_HOME`，或用 Android Studio 安装 |
| CMake | **3.22.1**（通过 SDK Manager 安装） |
| Shell 工具 | `curl`、`tar`、`make`、`awk`、`sed` |
| 构建工具链 | Gradle 8.11.1、AGP 8.7.3、Kotlin 2.1.0 —— 均由 wrapper 提供，**不要**另行安装 |
| 网络 | 可访问 GitHub 与 Alpine 官方镜像 |
| 磁盘 | 仓库本体约 35 MB，不含量子模块与原生依赖构建产物；实际占用远大于此，请预留充足空间 |

## 已知限制

1. **iOS 端必须在 macOS 上构建**，且原生依赖脚本编译的是 **device arm64**。模拟器构建链接这些产物会失败（`building for 'iOS-simulator', but linking in object file built for 'iOS'`，Intel Mac 上是 x86_64 缺符号）。要么改用 device 目标，要么为模拟器 SDK 重新编译原生依赖。
2. **Android 只构建 `arm64-v8a`**（由 `abiFilters` 决定），必须用 arm64 真机或对应模拟器镜像。
3. **Android 10+ 的 W^X 限制**决定了沙箱加载器必须放在 `nativeLibraryDir`：标记为 `app_data_file` 的内容（含解包到 `files/` 的整个 Alpine rootfs）一律不可执行，只有 APK 里 `lib/**/*.so` 解出来的才可执行。因此 `libproot-loader.so` 与 `libproot-loader32.so` 是**必需项而非可选项**，它们带 `.so` 后缀只是因为只有 `*.so` 会被解包。
4. **OAuth 登录路径需要自备变量**：走 Claude OAuth 凭证时，上游端点要求 system prompt 以特定标识行开头，该行由 `ANTHROPIC_OAUTH_IDENTIFIER_PROMPT` 在构建期注入，而上游**不提供该值**。用 API Key 以及其它所有供应商都不受影响。
5. **上游仓库是私有开发树的镜像，不接受 Pull Request**，反馈只能走 Issue。
6. **许可为 GPLv3**（因为链接了 GPLv3 的 iSH 与 GPLv2 的 PRoot）。二次分发需遵守 GPLv3；若改动原生依赖构建方式，必须保留 FFmpeg 的 LGPL 配置与随源码附带的 `LICENSE` 文件。
7. **源码结构可能变动**，本 Skill 描述的路径与脚本名以上游当前 `main` 分支为准，实际使用时以仓库现状复核。

## 自检清单

构建前：

- [ ] 克隆时带了 `--recurse-submodules`，`deps/ish` 与 `deps/proot` 均非空
- [ ] 两份 build-time 配置模板已从 `.example` 复制为正式文件
- [ ] iOS 侧已安装 `ninja`、`llvm`、`libarchive`、`pkg-config` 与 `meson`
- [ ] Android 侧 JDK 为 17、NDK 为 r28+ 且 `ANDROID_NDK_HOME` 已设置
- [ ] 目标设备或模拟器镜像为 arm64

构建后：

- [ ] `deps/lame-build/lib/libmp3lame.a`、`deps/frameworks/*.framework`、`deps/libs/*.a` 均已生成
- [ ] `deps/resources/alpine-rootfs.zip` 存在（iOS）
- [ ] `src/android/app/src/main/jniLibs/arm64-v8a/` 下有 `libproot-loader.so` 与 `libproot-loader32.so`
- [ ] `assets/proot-aarch64` 与 `assets/alpine-minirootfs.tar.gz` 存在（Android）
- [ ] iOS 选择 **Minis** scheme、device 目标构建

验收：

- [ ] 在应用内**实际执行一条命令并确认退出码为 0**——沙箱能启动不等于能执行，见 `references/03-extend-troubleshoot.md`
- [ ] 配置好至少一个模型供应商，能完成一轮真实对话

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/01-build-deploy.md` | 构建部署：双端工具链、脚本依赖顺序、产出物路径、打包与安装 |
| `references/02-features-config.md` | 功能与配置：模型接入、系统能力清单、`minis://` 资源模型、配置注入 |
| `references/03-extend-troubleshoot.md` | 二次开发与排错：源码结构、扩展点、症状对照表 |

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
