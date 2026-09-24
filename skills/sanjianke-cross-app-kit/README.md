# 三剪客 · 跨端 App 开发 Skill

一套代码同时出 iOS、Android、Web，含原生能力与上架发布

---

## 前置条件

| 项 | 要求 | 说明 |
|---|---|---|
| Node.js | 20 LTS 起 | 版本过旧会在 Metro 阶段报难以定位的语法错 |
| 包管理器 | npm / yarn 1 / yarn 2+ / pnpm / bun 任选其一 | 选定后不要混用 lockfile；yarn 2+ 必须设 `nodeLinker: node-modules` |
| Expo SDK | 54 及以上为佳 | 更早的版本原生能力与目录约定不同，需先升级 |
| 本地 iOS 编译 | macOS + Xcode | Windows 上只能靠 `eas build -p ios` 出包 |
| 本地 Android 编译 | Android Studio + JDK | 否则用 EAS Build 或只跑 Web |
| EAS（可选） | Expo 账号 + `npm i -g eas-cli` | 用于云端构建、提交、OTA；不用也可本地构建 |
| 商店账号 | Google Play（一次性 25 USD）/ Apple Developer Program（99 USD/年） | 仅在上架时必需 |

如果你只是想让 Agent 读这个 Skill 来改一个已有的 Expo 仓库，本地只需要装好 Node 与那个仓库自己的包管理器即可，其余按需。

---

## 使用

把 `SKILL.md` 作为入口，按「工作流路由」表跳到对应资料：

1. **认清项目类型**——`references/01-environment-and-project-structure.md`，先判定是 CNG 还是手工原生工程，这决定后面所有操作。
2. **处理跨端与原生能力**——`references/02-cross-platform-and-native-capabilities.md`，能力矩阵 + 四种平台差异处理模式 + 相机/通知/存储的完整两段式写法。
3. **出包与上架**——`references/03-build-release-and-troubleshooting.md`，本地构建、EAS 档位、OTA、提交、排错对照表。

最小自检（改完代码必跑）：

```sh
npx expo install --check     # CI 里用 CI=1 前缀让它非零退出
npx expo-doctor
npx tsc --noEmit             # 若启用 TypeScript
npx expo lint
```

---

## 依赖

本 Skill 本身**不需要安装任何 Python / npm 包**，不包含脚本，全部内容为可执行的命令说明与判断准则。它描述的操作依赖：

- Expo CLI（随项目里的 `expo` 包，无需全局安装）
- EAS CLI（可选，`npm install --global eas-cli`）
- 项目自身的 Node 运行时与包管理器

内容中的版本号（SDK 57 / react-native 0.87 / eas-cli 24 等）是写作时的快照，请以项目实际安装版本为准，用 `npx expo install --check` 与 `npx expo-doctor` 核对。

---

## 安全

- 不内嵌任何密钥、token、证书或 `.env` 真值
- 不主动把任何内容发往外部地址；所有联网行为都由你在终端里显式执行的 Expo / EAS 命令产生
- 明确提醒 `EXPO_PUBLIC_` 前缀的变量会被明文编译进客户端包，不得存放私密信息
- EAS 是托管服务，是否上传源码到构建服务器由项目方决定；文档同时给出不依赖 EAS 的本地构建路径
- 权限范围已在 `SKILL.md` 的「权限与用途说明」中逐项列明，能力边界见「能力边界」一节

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：Expo（MIT），https://github.com/expo/expo

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
