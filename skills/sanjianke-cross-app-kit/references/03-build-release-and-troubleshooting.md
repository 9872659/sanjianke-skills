# 构建发布与排错

本文对应 SKILL.md「工作流路由」的第三行。先把最容易混的一件事说清：

**Expo 里「构建」是两件独立的事。** 原生运行时（二进制）由 `expo run:*` 或 `eas build` 产出；JS 与静态资源由 `expo export` 产出。理解了这条分界，就能判断任何一次改动需要走哪条路——这也是「改个文案要不要重新出包」这类问题的唯一正确答案。

---

## 1. 两条构建路径的选择

| 场景 | 路径 | 命令 |
|---|---|---|
| 日常开发，改 JS | 不用构建，热重载 | `npx expo start` |
| 调试原生问题、写原生模块 | 本地编译 | `npx expo run:ios` / `npx expo run:android` |
| 团队协作、要装到别人手机上 | 云端构建 | `eas build --profile development` |
| 没有 Mac 却要出 iOS 包 | 云端构建（唯一选择） | `eas build -p ios` |
| 出上架包 | 云端或本地生产构建 | `eas build --profile production` |
| 只改 JS/图片，想立刻推给线上用户 | OTA 更新 | `eas update --channel production` |
| 出网页版 | 导出静态产物 | `npx expo export --platform web` |

---

## 2. 本地构建

前置：`android/`、`ios/` 目录存在。不存在的话，`run` 命令会自动先跑一次 `prebuild`。

```sh
# Android
npx expo run:android
npx expo run:android --variant debug            # 默认
npx expo run:android --variant debugOptimized   # SDK 54+；接近 release 性能，仍是 debug 流程
npx expo run:android --variant release          # 验证只在生产包出现的问题

# iOS（仅 macOS）
npx expo run:ios
npx expo run:ios --configuration Release
npx expo run:ios --device                        # 装到已连接的真机
npx expo run:ios --device generic --output ./build  # 只构建、不定向设备，适合 CI
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--no-build-cache` | 清原生缓存（iOS 的 DerivedData）后重编，用于排查陈旧缓存问题 |
| `--no-install` | 跳过依赖安装（iOS 同时也跳过 pod install） |
| `--no-bundler` | 不启 dev server；已有服务在跑时自动生效 |
| `-d, --device [name]` | 指定设备；不带值则弹出选择列表 |
| `-o, --output <path>` | 构建完成后把产物拷到指定目录 |
| `-p, --port` | dev server 端口，默认 8081 |

注意事项：

- `run:*` 产出的包**不用于上架**：Android release 包不会自动签名，iOS 也不做发布签名。要上架的包用 EAS Build 或自己配签名。
- Android 有 product flavor 时：`npx expo run:android --variant freeDebug --app-id dev.expo.myapp.free`。
- iOS 有多个 scheme 时：`npx expo run:ios --scheme <name>`。
- 编译过一次原生代码后，再改 JS 不需要重新编译；一旦动了 `app.json` 里的原生成分或新增原生依赖，必须重新编译。

### 只导出 JS/资源

```sh
npx expo export                       # 默认三端，产物进 dist/
npx expo export --platform ios        # 单独一端
npx expo export --platform web --output-dir web-dist
npx expo export -c                    # 先清缓存再导
npx expo export --no-bytecode         # 只用于分析包体积，别拿它出包
```

导出产物是 EAS Update 的输入之一，也是 Web 部署的产物。

---

## 3. EAS Build

### 3.1 首次配置

```sh
npm install --global eas-cli     # 或全程用 npx eas-cli@latest
eas login
eas whoami                       # 确认登录身份
eas build:configure              # 生成/更新 eas.json，写入 projectId
```

`eas build:configure` 之后检查两件事：`app.json` 里是否补上了 `extra.eas.projectId`，以及 `eas.json` 的三个档位是否符合团队需要。

### 3.2 `eas.json` 档位设计

三档起步，别只留一个 production：

```json
{
  "cli": { "appVersionSource": "remote" },
  "build": {
    "base": {
      "node": "20.11.1",
      "env": { "EXPO_PUBLIC_API_BASE": "https://api.example.com" }
    },
    "development": {
      "extends": "base",
      "developmentClient": true,
      "distribution": "internal",
      "channel": "development",
      "android": { "buildType": "apk" },
      "ios": { "simulator": false }
    },
    "preview": {
      "extends": "base",
      "distribution": "internal",
      "channel": "preview",
      "android": { "buildType": "apk" }
    },
    "production": {
      "extends": "base",
      "autoIncrement": true,
      "channel": "production"
    }
  },
  "submit": {
    "production": {
      "android": { "track": "internal" }
    }
  }
}
```

关键字段的取舍：

| 字段 | 建议 | 理由 |
|---|---|---|
| `developmentClient` | development 档置 `true` | 必须同时装 `expo-dev-client`，否则构建失败 |
| `distribution` | 内测用 `internal` | `internal` 的可分享链接要求产物是 `.apk` / `.ipa`，所以配 `buildType: apk` 而不是默认的 `app-bundle` |
| `channel` | 每档独立 | 决定这个包会从哪个 channel 拉 OTA 更新，串了会把测试更新推给线上用户 |
| `autoIncrement` | production 置 `true` | 自动递增 `android.versionCode` 与 `ios.buildNumber`，避免手忘 |
| `node` / `pnpm` / `bun` | 按团队固定 | 构建环境与本地不一致是「本地能过、云端失败」的头号原因 |
| `env` | 只放可提交的值 | 密钥走 EAS 环境变量，不要写进 `eas.json` |

### 3.3 出包命令

```sh
# 开发构建（装了 expo-dev-client 才能用）
npx expo install expo-dev-client
eas build --profile development --platform android
eas build --profile development --platform ios

# 内测分发
eas build --profile preview --platform all --message "1.4.0 内测"

# 上架包
eas build --profile production --platform all

# 只看状态 / 下载
eas build:list
eas build:view <build-id>

# 不进云端：本机跑同一个流程（需本地环境齐全）
eas build --profile production --platform ios --local
```

首次为 iOS 出上架包时，EAS CLI 会引导创建 distribution certificate 与 provisioning profile；Android 会引导生成 keystore。**keystore 与证书丢了就再也无法给同一个应用发更新**，请立刻备份到团队密码库。

---

## 4. EAS Update（OTA）

OTA 能推的只有 JS 与资源，推不了原生代码和 `Info.plist` / `AndroidManifest.xml`。

### 4.1 配置

```sh
eas update:configure
```

它会写 `runtimeVersion` 与 `updates.url`，并确保 `extra.eas.projectId` 存在。同时确认 `eas.json` 里每个档位的 `channel` 已设。

`runtimeVersion` 是 OTA 的安全阀：二进制只接受 `runtimeVersion` 匹配的更新。默认策略跟随 SDK 版本，升 SDK 后老包不会收到新更新，这正是想要的行为。

### 4.2 发布

```sh
eas update --channel preview --message "修登录超时" --environment preview
eas update --channel production --message "1.4.1 热修" --environment production
```

- SDK 55 起 `--environment` 为必填，用于选定 EAS 环境变量集合。
- channel 里的分支默认与 channel 同名，可用 `--branch` 覆盖。
- 发布前先在 preview 上验证；直接推 production 等于把回滚压力留给自己。

### 4.3 验证更新是否生效

- development build：在应用内的 Extensions 页加载对应更新。
- release / preview 包：**杀掉进程再启动两次**——第一次下载，第二次应用。
- 也可以在应用内用 `expo-updates` 的 API 主动检查。

### 4.4 回滚

```sh
# 把某个 channel 指回上一个可用分支
eas update:republish --channel production --group <update-group-id>
```

发布前把当前 `update group id` 记下来，出事时才有得回。

---

## 5. 提交到商店

```sh
# 提交最近一次构建
eas submit --platform ios --latest
eas submit --platform android --latest

# 提交指定构建，或本地已有的产物
eas submit --platform android --path ./build/app-release.aab
eas submit --platform ios --path ./build/app.ipa

# CI 里用（跳过交互）
eas submit --platform android --latest --non-interactive
```

- `eas submit` 只上传二进制，**不管截图、描述、隐私标签**。商店信息要么在控制台手填，要么用 EAS Metadata。
- Android 新 App 默认进 internal 轨道，想直接进 production 要先在 Play Console 完成首次发布设置。
- iOS 上传后先进 TestFlight（处理通常 10–15 分钟），再到 App Store Connect 选构建、填元数据、提交审核。
- 上架前确认包名/包标识符与已发布版本一致，`version` 已递增。

---

## 6. 排错对照表

| 现象 | 大概率原因 | 处理 |
|---|---|---|
| 出包后权限弹窗不出现，`requestPermission` 一直返回 denied | 只写了运行期调用，没配构建期权限 | 补 `app.json` 的 plugin / `infoPlist` / `android.permissions`，重新 prebuild 并重新出包 |
| Web 白屏，控制台报 `Cannot find module` 或原生模块为空 | 引了 native-only 模块 | 用 `.web.tsx` 分平台文件，或改成能力探测后不渲染 |
| `npx expo prebuild` 后原生目录的改动消失了 | 在手工原生工程上跑了 prebuild（尤其带 `--clean`） | 从版本库恢复；这类项目应停用 CNG，不要跑 prebuild |
| 装了新库，`npx expo start` 报版本不匹配 | 用 `npm install` 而非 `npx expo install` 装的 | `npx expo install --fix`，再 `npx expo-doctor` 复查 |
| 云端构建失败，本地能过 | Node/包管理器/环境变量与云端不一致 | 在 `eas.json` 固定 `node` 版本，密钥放 EAS 环境变量；看构建日志的 Build Annotations |
| `eas build` 报找不到 projectId | 没跑过 `eas build:configure` | 运行它，或手工补 `extra.eas.projectId` |
| OTA 推了但用户没变化 | runtimeVersion 不匹配、channel 配错、或改动含原生变更 | `eas update:list` 核对 channel 与 runtimeVersion；原生变更必须出新包 |
| `expo export` 报 wasm 相关错误（用了 SQLite Web） | Metro 未开 wasm 支持 | `metro.config.js` 里 `config.resolver.assetExts.push('wasm')` |
| Web 上 SQLite 报 SharedArrayBuffer 不可用 | 缺 COOP/COEP 响应头 | 服务端加 `Cross-Origin-Embedder-Policy: credentialless` 与 `Cross-Origin-Opener-Policy: same-origin` |
| iOS 模拟器上相机/生物识别不工作 | 模拟器没有这些硬件 | 用真机验证，不要当 bug 查 |
| Android 从推送冷启动时启动屏异常 | 已知的 debug 包问题 | 用 `--variant release` 验证；不要为此改业务代码 |
| 本地改了 `.env` 但打包后值没变 | 变量没有以 `EXPO_PUBLIC_` 开头，或用了非点号取值 | 改成 `process.env.EXPO_PUBLIC_X` 形式；重启 dev server |
| 大文件上传失败 | 走了 base64 序列化 | 改用 `expo/fetch` 直接把 `File` 作为 body 或塞进 `FormData` |
| 忘记备份 keystore，换电脑后无法更新已上架应用 | 签名材料只在原机器上 | 从 EAS 或团队密码库取回；取不回只能换包名重发 |

**排查通用起手式**：

```sh
npx expo-doctor                    # 依赖与配置体检
npx expo install --check           # CI 里加 CI=1 让它非零退出
npx expo start --clear             # 清 Metro 缓存
DEBUG=expo:* npx expo start        # 打开 CLI 调试日志（PowerShell: $env:DEBUG='expo:*'）
npx expo config --type public      # 看最终生效的公开配置里有没有你要的字段
npx expo config --type introspect  # 看 prebuild 会往 Info.plist / AndroidManifest 写什么
```

最后一条尤其有用：**在跑 prebuild 之前就能确认权限字段被正确写入了**，不必等出包才发现。

---

## 7. 发布前的固定动作

```sh
npx expo install --check
npx expo-doctor
npx tsc --noEmit          # 若启用 TypeScript
npx expo lint
npx expo export --platform web      # 确认 Web 能出产物
eas build --profile production --platform all
# 记录当前 channel 上的 update group id，作为回滚点
eas submit --platform ios --latest
eas submit --platform android --latest
```

出包之后、提交之前，用 preview 包在真机上把「权限申请、深链、通知点击跳转、离线态」这四条路径各走一遍。这四类问题在开发环境里全部是隐藏的。
