---
name: sanjianke-cross-app-kit
slug: sanjianke-cross-app-kit
displayName: 三剪客 · 跨端 App 开发
description: "一套代码同时出 iOS、Android、Web，含原生能力与上架发布。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "围绕 Expo 的跨端工程作业规范：三端边界与降级点、相机通知存储等原生能力的申请与封装、EAS 构建与商店提交流程，以及让 Agent 改项目时少踩坑的约束与自检清单。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 跨端
  - 自动化
---

# 三剪客 · 跨端 App 开发

用 Expo 写跨端 App，坑几乎都不在写页面，而在三件事上：**一个 API 在三端的可用性不一样**、**原生能力需要构建期配置而不是运行时调用**、**改完 JS 到底要不要重新出包**。

这个 Skill 把这些判断固化成可执行的顺序：先确认当前项目处于哪条工作流，再决定动哪一层，最后用固定命令验证。它同时是给 Agent 看的施工约束——`app.json`、`android/`、`ios/` 这三个地方改错了，队友的本地环境和 CI 会一起坏。

适用对象：已经或准备用 Expo（SDK 54 及以上）做 iOS / Android / Web 三端产品的团队；也适用于让 Agent 接手一个已有 Expo 仓库、需要安全改动的时候。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是 | 读取 Expo 官方文档、npm registry 版本号与 React Native Directory 兼容性标签；EAS 相关命令需要联网 |
| 读取文件 | 是 | 读 `package.json`、`app.json`/`app.config.js`、`eas.json`、`src/app/` 与 `references/` 下的资料 |
| 写入文件 | 是 | 新增页面与组件、改 app 配置、写 `eas.json` 构建档位；默认不覆盖既有原生工程文件 |
| 凭证 | 否（不内嵌） | 本 Skill 不含任何 token、keystore、证书或 `.env` 真值；EAS 登录态与签名材料由使用者自己的账号体系提供 |
| 子进程 / 后台常驻 | 是 | 执行 `npx expo *`、`npx expo-doctor`、`eas *` 等 CLI；本地编译会长时间占用终端，但不注册常驻服务 |

本 Skill 不内嵌任何密钥，也不上传项目代码。EAS 是 Expo 的托管服务，是否使用、是否上传源码到构建服务器，由项目方按自身合规要求决定；不使用 EAS 同样可以完成全部构建与发布（见 `references/03-build-release-and-troubleshooting.md` 的本地构建路径）。

## 触发场景

- 「这个 App 要 iOS 和安卓都能装，网页版也要能打开，怎么组织代码？」
- 「相机扫描 / 推送通知在 Web 上不能用，怎么优雅降级？」
- 「`npx expo start` 跑起来是好的，`eas build` 出来的包里权限弹窗不出现。」
- 「我只是改了个页面文案，为什么还要重新出包？OTA 更新怎么发？」
- 「让 Agent 帮我加一个原生依赖，它把 `android/` 和 `ios/` 都改了，现在 prebuild 冲突。」
- 「要上架 App Store 和 Google Play，签名、证书、提交流程要准备什么？」

## 快速开始

```sh
# 1) 建项目（默认模板已含 Expo Router + TypeScript）
npx create-expo-app@latest my-app
cd my-app

# 2) 判断项目类型：有 android/ ios/ 目录 = 手工原生工程；没有 = CNG
npx expo config --type public

# 3) 起开发服务器（按 A / I / W 分别开安卓、iOS、Web）
npx expo start

# 4) 装依赖必须走 expo install，它会挑与当前 react-native 匹配的版本
npx expo install expo-camera expo-notifications expo-secure-store

# 5) 体检
npx expo-doctor
npx expo install --check
```

跑通上面五步之后，再按下面这张表决定深入哪一层：

- 只改 JS/TS 和样式 → 不用重新构建，保存即刷新。
- 改了 `app.json` 里影响原生的字段（图标、权限文案、包名）→ 必须重新 prebuild + 重新出包。
- 装了带原生代码的库 → 必须做 development build，Expo Go 里跑不出来。
- 改了三端差异逻辑 → 先在两端各跑一次，再看 `references/02`。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 搭环境、看懂目录、判断 CNG 还是手工原生工程、升级 SDK | `references/01-environment-and-project-structure.md` |
| 一套代码出三端、分平台文件、原生能力（相机/通知/存储）、降级方案 | `references/02-cross-platform-and-native-capabilities.md` |
| 出包、EAS 档位、OTA 更新、上架提交、构建失败怎么查 | `references/03-build-release-and-troubleshooting.md` |
| Agent 改这个仓库时的允许范围、必跑验证、回滚点 | 本文件「自检清单」+ `references/01` 的目录约束 |

## 能力边界

**覆盖**：

- 用 Expo SDK 57 / Expo Router 组织一套 React 代码，输出 iOS、Android、Web 三端。
- CNG（Continuous Native Generation）工作流：`app.json` + `npx expo prebuild` 生成原生工程，以及手工原生工程的取舍判断。
- 原生能力的**构建期配置 + 运行期调用**两段式写法：相机、通知、安全存储、本地数据库、文件、媒体库。
- 平台差异处理：`.native.tsx` / `.web.tsx` 分平台文件、`Platform.select`、能力探测后降级。
- EAS Build / EAS Submit / EAS Update 的命令与 `eas.json` 档位设计，以及不使用 EAS 时的本地构建替代路径。
- 给 Agent 的施工约束：哪些文件不许直接改、改完必须跑什么命令、怎么回滚。

**不覆盖**：

- 原生语言（Swift / Kotlin / Objective-C / Java）本身的写法，也不展开自定义原生模块的开发流程。
- 具体业务实现：UI 设计系统、状态管理选型、后端接口设计。
- 商店侧的运营事务：美区/国区资质、隐私政策法律文本、ASO、投放与买量。
- 用其他跨端方案（Flutter、Taro、uni-app、React Native CLI 纯裸工程）的项目，本包的判断不适用。
- 具体的账号、费用与配额决策。

## 依赖条件

| 项 | 要求 | 说明 |
|---|---|---|
| Node.js | 20 LTS 起 | 版本过旧会在 Metro 阶段报难以定位的语法错 |
| 包管理器 | npm / yarn 1 / yarn 2+ / pnpm / bun 任选其一 | 选定后不要混用 lockfile；yarn 2+ 必须设 `nodeLinker: node-modules` |
| Expo SDK | 54 及以上为佳 | 更早的版本原生能力与目录约定不同，需先升级 |
| 本地 iOS 编译 | macOS + Xcode | Windows 上只能靠 `eas build -p ios` 出包 |
| 本地 Android 编译 | Android Studio + JDK | 否则用 EAS Build 或只跑 Web |
| EAS（可选） | Expo 账号 + `npm i -g eas-cli` | 用于云端构建、提交、OTA；不用也可本地构建 |
| 商店账号 | Google Play（一次性 25 USD）/ Apple Developer Program（99 USD/年） | 仅在上架时必需 |

## 已知限制

- **`npx expo prebuild` 会重写 `android/` 与 `ios/`**。手工改过原生目录后再跑 prebuild 会丢改动；这类项目要把原生目录纳入版本管理并停用 CNG。
- **权限弹窗文案改不了 OTA**。iOS 的 `Info.plist` 与 Android 的 `AndroidManifest.xml` 变更只随新二进制生效，`eas update` 推不动。
- **Expo Go 不是生产环境**。它只带一部分原生代码，带原生依赖的库、远程推送（Android SDK 53 起）在其内不可用；正式开发请用 development build。
- **`expo-secure-store` 与 `expo-notifications` 不支持 Web**。Web 上得走 `localStorage` / `sessionStorage` 与 Web Push 的替代实现。
- **Web 端权限有安全上下文要求**。相机、定位在非 `https://`（或非 `localhost`）下无法申请。
- **文件级 API 有平台差异**。例如 `expo-camera` 在 Web 上返回 base64 而不是文件路径；`expo-file-system` 的 `File` / `Directory` 类只在原生可用。
- **本 Skill 里的版本号是写作时的快照**，`references/01` 给了自查命令，请以项目实际安装版本为准。
- **命令与配置项随 SDK 演进**。执行前用 `npx expo <cmd> --help` 与 `eas <cmd> --help` 核对当前参数。

## 自检清单

改完代码，按顺序过一遍；任何一条不通过都不要提交：

- [ ] `npx expo install --check` 无「版本不匹配」提示（CI 里用 `CI=1 npx expo install --check`，有不匹配就非零退出）。
- [ ] `npx expo-doctor` 全绿；它对依赖兼容性与 `app.json` 同步做检查。
- [ ] 新增依赖是否带原生代码？是 → 走 development build，不要假设 Expo Go 能跑。
- [ ] 有没有直接手改 `android/` 或 `ios/`？是 → 确认该项目已停用 CNG，且改动已提交到版本库。
- [ ] 三端至少各验证一次：`npx expo start` 后按 A / I / W，或在真机 development build 上验证。
- [ ] 本次改动是否碰到权限或包名/图标？是 → 必须在新的二进制里验证，不能只靠热重载。
- [ ] 权限申请文案是否写清了真实用途？含糊的文案会被商店退回。
- [ ] 是否误把私密信息写进 `EXPO_PUBLIC_` 变量？这些值会明文编译进客户端包。
- [ ] 类型与语法：`npx tsc --noEmit`（若项目启用 TypeScript）、`npx expo lint`。
- [ ] 出包前确认 `version` 与 `ios.buildNumber` / `android.versionCode` 已递增，或用 `autoIncrement`。
- [ ] 发布前记录回滚点：当前线上 `runtimeVersion` 与 channels 上的更新 ID。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/01-environment-and-project-structure.md` | 工具链与版本自查、目录职责、CNG vs 手工原生工程、升级路径 |
| `references/02-cross-platform-and-native-capabilities.md` | 三端能力矩阵、分平台文件、相机/通知/存储/数据库的完整写法与降级 |
| `references/03-build-release-and-troubleshooting.md` | 本地构建、EAS 档位与命令、OTA 更新、提交流程、常见报错对照表 |

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
