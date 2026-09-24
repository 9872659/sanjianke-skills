# 构建部署

面向「从源码把 iOS / Android 双端跑起来并出包」。所有路径相对仓库根目录。

## 1. 为什么不能直接点运行

这个项目把整套 Linux 沙箱塞进了 App 内部，因此四类原生依赖全部**在构建期由 `deps/` 下的脚本从源码编译**，仓库里不预置二进制：

| 依赖 | 作用 | 谁在用 |
|---|---|---|
| iSH | iOS 上的 Linux usermode 模拟 | iOS 沙箱内核 |
| PRoot | 用户态 chroot | Android 沙箱 |
| FFmpeg | 音视频处理 | 双端 |
| LAME | MP3 编码 | 双端 |
| Alpine minirootfs | 沙箱启动的根文件系统 | 双端 |

后果是：首次构建是一个**有先后顺序的多阶段流程**，不是一条 `build` 命令。预算 **30～60 分钟**；产物落盘缓存后，后续构建恢复正常速度。

## 2. 公共准备

```sh
git clone --recurse-submodules <OpenMinis 仓库地址>
cd OpenMinis
```

仓库地址见 `SKILL.md` 的「快速开始」一节。

仓库含两个子模块，缺了会在原生构建阶段报错：

| 子模块 | 用途 |
|---|---|
| `deps/ish` | iOS 沙箱内核 |
| `deps/proot` | Android 沙箱 |

补救办法：

```sh
git submodule update --init --recursive
```

### 构建期配置模板

有一批值**不在仓库里**，通过构建期注入。先复制模板：

```sh
cp src/ios/Configs/ProviderCustomization.xcconfig.example \
   src/ios/Configs/ProviderCustomization.xcconfig
cp src/android/app/provider-customization.properties.example \
   src/android/app/provider-customization.properties
```

留空是允许的：**App 能编译、能运行**。某个值只被用到它的那个功能需要，缺了会在运行时明确报错。纯 API Key 方式的登录不依赖任何定制项。

各值含义与 `ANTHROPIC_OAUTH_IDENTIFIER_PROMPT` 的特殊性，见 `02-features-config.md` 第 4 节。

## 3. iOS 构建

### 3.1 工具链

| 工具 | 版本 / 说明 |
|---|---|
| macOS | Apple Silicon 强烈推荐 |
| Xcode | 需含 iOS SDK；工程目标 **iOS 26.2**、**Swift 6.0** |
| Homebrew | `brew install ninja llvm libarchive pkg-config` |
| Python | `pip3 install meson` |

各包的分工：`llvm` 编译 guest VDSO；`libarchive` 解包 rootfs；Meson + Ninja 构建 iSH 内核。

### 3.2 编译原生依赖（顺序敏感）

从仓库根目录执行，**必须按此顺序**——FFmpeg 链接 LAME，LAME 不在前面 MP3 编码会被静默丢弃：

```sh
./deps/build_lame.sh              # → deps/lame-build/lib/libmp3lame.a
./deps/build_ffmpeg.sh            # → deps/frameworks/*.framework
./deps/build_ish.sh               # → deps/libs/*.a、deps/include/、deps/resources/
./deps/prepare_alpine_rootfs.sh   # → deps/resources/alpine-rootfs.zip
```

各脚本产出：

- **`build_lame.sh`** —— LAME **3.100**，arm64 静态库。
- **`build_ffmpeg.sh`** —— FFmpeg **6.1.2**，逐库 `.framework` 加一个伞形 `FFmpeg.framework`。配置为 **LGPL**：不要加 `--enable-gpl` 或 `--enable-nonfree`，否则许可层面出问题。
- **`build_ish.sh`** —— 从 `deps/ish` 子模块产出 `libish`、`libish_emu`、`libfakefs`，外加头文件与 VDSO。
- **`prepare_alpine_rootfs.sh`** —— 下载 Alpine aarch64 minirootfs 并转换成 iSH 的 fakefs 格式。

Xcode 工程是按相对路径引用 `deps/libs/`、`deps/include/`、`deps/frameworks/`、`deps/resources/` 的，所以**不需要手工拷贝**任何产物。

### 3.3 编译 App

```sh
open src/ios/Minis.xcodeproj
```

选 **Minis** scheme 构建。真机构建需在 *Signing & Capabilities* 里填自己的 team——工程出厂带的是空的 `DEVELOPMENT_TEAM`。

命令行等价写法：

```sh
xcodebuild -project src/ios/Minis.xcodeproj -scheme Minis \
           -configuration Debug -destination 'generic/platform=iOS' \
           CODE_SIGNING_ALLOWED=NO build
```

> **模拟器构建需要模拟器架构的依赖。** 上面的脚本编译的是 **device arm64**；用模拟器目标链接它们会报
> `building for 'iOS-simulator', but linking in object file built for 'iOS'`，
> Intel Mac 上则是 x86_64 缺符号。要么构建 device 目标，要么为模拟器 SDK 重新编译一遍原生依赖。

### 3.4 工程目标

| Target | 说明 |
|---|---|
| `Minis` | 主 App |
| `MinisShare` | 分享扩展 |
| `AgentWidgetExtension` | 小组件扩展 |
| `MinisFileProvider` | 文件提供者扩展 |
| `MinisTests` / `MinisUITests` | 测试 |

## 4. Android 构建

### 4.1 工具链

| 工具 | 版本 / 说明 |
|---|---|
| JDK | **17** |
| Android SDK | compileSdk **36**、targetSdk **35**、minSdk **26** |
| Android NDK | **r28+**，设置 `$ANDROID_NDK_HOME` 或用 Android Studio 装 |
| CMake | **3.22.1**（通过 SDK Manager 装） |
| Shell 工具 | `curl`、`tar`、`make`、`awk`、`sed` |

Gradle 由 wrapper 提供（**Gradle 8.11.1 / AGP 8.7.3 / Kotlin 2.1.0**），不要另行安装。

只构建 `arm64-v8a`（`abiFilters` 限制），必须用 arm64 真机或对应镜像。

### 4.2 编译原生依赖

```sh
./deps/build_proot.sh                  # → assets/proot-aarch64、jniLibs/arm64-v8a/*.so
./scripts/prepare_android_sandbox.sh   # → assets/alpine-minirootfs.tar.gz
```

**`build_proot.sh`** 用 NDK 交叉编译一个静态 `libtalloc` 和 `deps/proot` 这个 fork，然后安装进 App 的 `assets/` 与 `jniLibs/arm64-v8a/`：proot 本体，加上 **`libproot-loader.so` 和 `libproot-loader32.so`**。脚本结尾会逐个校验，缺任何一个就让构建失败。

**`prepare_android_sandbox.sh`** 下载 Alpine aarch64 minirootfs 到 `assets/`。

两个脚本都写入 `src/android/app/src/main/`，产物已被 gitignore——**它们是构建产物，重跑脚本而不是提交进去**。

`src/main/cpp/` 下的小型 JNI 库（`pty_bridge`、崩溃处理、`jieba_jni`）由 CMake 在正常 Gradle 构建中编译，不需要单独步骤。

### 4.3 编译与安装

```sh
cd src/android
./gradlew :app:assembleDebug          # → app/build/outputs/apk/debug/
./gradlew :app:installDebug           # 装到已连接设备
```

Release 构建沿用 debug 签名配置，本地出包**不需要 keystore**。

### 4.4 测试

```sh
./gradlew :app:testDebugUnitTest        # JVM 单元测试
./gradlew :app:connectedAndroidTest     # 仪器化测试，需要设备/模拟器
```

## 5. 为什么 Android 必须有那两个 `.so` 加载器

这一条值得单独讲，因为它解释了构建脚本里一段看起来多余的逻辑。

Android 10+ 对 `untrusted_app` 强制 W^X：任何标记为 `app_data_file` 的内容都不可执行——而解包到 App `files/` 目录下的整个 Alpine rootfs 正是这个标签。唯一可执行的位置是 `nativeLibraryDir`，它由 APK 里的 `lib/**/*.so` 填充。

于是加载器必须住在那里，并自己映射 guest 二进制，而不能依赖内核的 `execve`。proot 本身能在运行时解出一个内嵌加载器，但在 Android 上它会写进 App 的临时目录，撞上同一堵 W^X 墙。这也解释了为什么这两个文件明明是**可执行文件**却带 `.so` 后缀——只有 `*.so` 会被解包。

另一个容易踩的点：**这些产物在不同 NDK 版本之间不是逐字节一致的**，加载器代码随工具链代际变化。功能等价即可，不要拿校验和去和别人比对。

## 6. 验收标准

构建成功不等于沙箱可用。**必须实际执行一条命令并断言退出码为 0**——沙箱能启动不足以证明它能执行。理由与判别方法见 `03-extend-troubleshoot.md` 第 3 节。
