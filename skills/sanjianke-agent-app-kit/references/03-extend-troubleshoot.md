# 二次开发与排错

面向「读懂源码结构、找到该改的那一层、按症状把问题定位掉」。

## 1. 仓库结构

```
src/ios/          iOS App（Swift / SwiftUI）+ 分享、小组件、文件提供者扩展
src/android/      Android App（Kotlin / Compose）+ JNI 原生代码
src/shared/       双端共享资源
deps/             原生依赖构建脚本与随源码附带的第三方源码
docs/specs/       架构与接口规格
scripts/          rootfs 准备与开发者工具
```

改动前的判断顺序：**能力属于「通用计算」还是「平台相关」？** 通用计算放沙箱与提示层；平台相关放原生卸载。这条界线决定了你该动 `src/ios/Agent/` 还是 `src/ios/NativeOffloads/`。

## 2. 该动哪一层

### 2.1 `src/ios/Agent/` —— Agent 运行时

| 子目录 | 负责 |
|---|---|
| `Chat/` | 对话主流程 |
| `Session/` | 会话生命周期与持久化 |
| `Shell/`、`ISH/` | shell 工具与 iSH 集成 |
| `BrowserUse/` | 浏览器自动化 |
| `Offload/` | 原生卸载的调度层 |
| `Backup/`、`Sync/` | 备份与同步 |
| `Background/` | 后台任务 |
| `Intents/` | 系统快捷指令 / 意图集成 |
| `Markdown/`、`MessageList/` | 渲染与消息列表 |
| `Speech/` | 语音 |

顶层还有一个 `ToolLoopDetector.swift`——工具循环检测。改工具调用逻辑时留意它，很容易在自测里被它拦下来而误判为功能没生效。

### 2.2 `src/ios/NativeOffloads/` —— 平台能力

命名规律是 `XxxOffload.h` + `XxxOffload.m`，需要与 Swift 交互的再加一个 `XxxOffloadBridge.swift`。现有覆盖范围如下（可直接对照 `src/ios/Providers/` 之外的这份清单判断某项能力是否已存在）：

| 分类 | 已具备 |
|---|---|
| 健康与生活 | HealthKit、Calendar、Reminders、Contacts、Weather、HomeKit、Photos、Location、Maps |
| 设备与通信 | Bluetooth、NFC、Notification、Alarm、Clipboard、Device、Media、Player、Speak、Speech |
| 感知与模型 | Vision、NLP、ModelUse |
| 媒体处理 | FFmpeg |
| 系统与调试 | Config、Debug、Open、Sessions、BrowserUse |

**新增一项系统能力的标准动作**：在这两个目录下按上述命名规律补齐 `.h` / `.m`（必要时加 bridge），再在 Agent 的卸载调度层注册成工具。不要绕过卸载层直接调系统 API，否则沙箱与原生的一致性约定会被打破。

### 2.3 `src/android/`

`app/src/main/` 下：`AndroidManifest.xml`、`assets/`（沙箱资产）、`cpp/`（JNI）、`java/`、`jniLibs/`（proot 加载器）、`res/`、`resources/`。

`assets/` 与 `jniLibs/` 的内容都是构建产物，被 gitignore。**要改就改生成它们的脚本，不要把产物提交进去。**

## 3. 排错对照表

### 3.1 构建期

| 症状 | 原因 | 处置 |
|---|---|---|
| `deps/ish` 或 `deps/proot` 为空 | 子模块未初始化 | `git submodule update --init --recursive` |
| iOS：`Undefined symbols … _vstats_version` / `symbol(s) not found` | FFmpeg 没编，或与当前链接目标的架构不一致 | 重跑 `./deps/build_ffmpeg.sh`，并改用 device 目标构建 |
| iOS：`linking in object file built for 'iOS'`（模拟器构建） | 原生依赖建的是 device arm64 | 改用 device 目标，或为模拟器 SDK 重编依赖 |
| iOS：MP3 编码不可用 | `build_lame.sh` 没在 `build_ffmpeg.sh` 之前跑 | 按顺序重跑两个脚本 |
| Android：`Android NDK not found` | `ANDROID_NDK_HOME` 未设置 | 指向 r28+ 安装路径，例如 `export ANDROID_NDK_HOME=~/Library/Android/sdk/ndk/28.0.12433566` |
| Android：App 能起，shell 起不来 | 沙箱资产缺失 | 重跑 `./deps/build_proot.sh` 与 `./scripts/prepare_android_sandbox.sh`，然后重新构建 |
| 某个功能抛「缺配置值」 | 定制文件里的值没填 | 见 `02-features-config.md` 第 4 节 |

### 3.2 Android 的隐蔽失败：`[Shell not running] (exit code: -1)`

每条命令都返回这个，说明 **proot 的 ELF 加载器没进 APK**。

排查：

```sh
# 1) 目录里应当同时有这两个文件
ls src/android/app/src/main/jniLibs/arm64-v8a/libproot-loader.so \
   src/android/app/src/main/jniLibs/arm64-v8a/libproot-loader32.so

# 2) 打包后确认三个 .so 都在 APK 里
unzip -l app-debug.apk | grep libproot
```

缺失就重跑 `./deps/build_proot.sh`（该脚本会做校验）再重新构建。

**为什么这个故障值得单独列一节**：它从外部极难察觉。proot 本身仍然会启动，还会打印 `native_offload` 的初始化日志，所以沙箱看起来是健康的，任何「它能起来吗」的检查都会通过。真正失败的只有第一次 `execve("/bin/sh")`，logcat 里在 `PRootStderr` 标签下报 `Permission denied`。

因此本 Skill 的验收标准是：**跑一条命令并断言退出码为 0**。启动沙箱不算数。

根因是 Android 10+ 的 W^X 策略，机制见 `01-build-deploy.md` 第 5 节。

## 4. 规格与工具

### 4.1 `docs/specs/` 下的规格文件

| 文件 | 内容 |
|---|---|
| `minis-url-scheme.md` | `minis://` 资源寻址规格（会话作用域、命名空间、解析语义） |
| `ios-sandbox-ish-summary.md` | iOS 沙箱与 iSH 的集成摘要 |
| `debug-server-api.md` | 调试服务 API |

> `minis-url-scheme.md` 的状态标记为 **Draft**，接口仍可能调整，落地前以仓库现状为准。

`docs/` 下另有两份设计文档，涉及备份的流式打包方案与 iSH 后台 CPU 调控，做性能或后台相关改动时值得先读。

### 4.2 `deps/ISH_INTEGRATION.md`

iSH 集成说明。改动 iOS 沙箱、VDSO 或 rootfs 格式前必读。

### 4.3 上游仓库 `scripts/` 下的开发工具

> 下表的脚本属于**被介绍的上游项目仓库**，不在本 Skill 包内；跑之前先按前文克隆仓库。

| 脚本 | 用途 |
|---|---|
| `gen_debug_skill.sh` / `gen_debug_skill_android.sh` | 生成调试用技能包（iOS / Android 各一份） |
| `install_alpine.sh` | 安装 Alpine |
| `prepare_rootfs.sh` / `prepare_android_sandbox.sh` | rootfs 与 Android 沙箱资产准备 |
| `optimize_rootfs.sh` | 精简 rootfs |
| `add_locale.py` / `add_localization.py` / `register_locale.py` / `check_locale_batch.py` | 本地化批量增补与校验 |
| `symbolicate_hang.py` | 卡死现场符号化 |
| `test_ish_jit_fault_recovery.py` | iSH JIT 故障恢复测试 |
| `update_models_dev.sh` / `verify_models_dev_resolution.py` | 模型清单更新与解析校验 |

调试技能包那两个脚本是**排查 Agent 行为问题最快的入口**——它直接生成一个可加载的技能，用来观察工具调用与沙箱交互。

## 5. 贡献与许可注意事项

1. **上游仓库是私有开发树的镜像，不接受 Pull Request**——没有落地的地方。问题反馈走 Issue。
2. 项目为 **GPLv3**：因为它链接了 GPLv3 的 iSH 与 GPLv2 的 PRoot，组合作品整体以 GPLv3 分发。
3. **改动原生依赖构建方式时**：保持 FFmpeg 的 LGPL 配置（不要加 `--enable-gpl` / `--enable-nonfree`），并保留随源码附带的 `LICENSE` 文件。
4. 第三方组件的版本与许可条款有独立清单文件，做分发前应逐项核对。
5. 二次分发（包括内部大规模部署）需自行履行 GPLv3 义务，本 Skill 不提供法律意见。

## 6. 改动前的最小验证回路

1. 只改一层，别同时动 `Agent/` 与 `NativeOffloads/`。
2. 先保证原生依赖没有重编（产物已缓存），缩短单次验证时间。
3. 改沙箱相关行为后，**跑命令断言退出码 0**，不要只看「沙箱启动成功」。
4. 改模型供应商相关逻辑后，至少走通一轮真实对话与一次工具调用。
5. 改本地化后跑上游仓库的 `scripts/check_locale_batch.py` 做批量校验。
