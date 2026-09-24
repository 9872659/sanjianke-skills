# 环境与项目结构

本文对应 SKILL.md「工作流路由」的第一行。目标是在动手改代码之前，把三件事定下来：**工具链版本**、**项目属于哪条工作流**、**每个目录归谁管**。

---

## 1. 工具链最低要求与版本自查

| 组件 | 要求 | 自查命令 |
|---|---|---|
| Node.js | 20 LTS 或更高 | `node -v` |
| 包管理器 | npm 10+ / yarn 1.22+ / yarn 4+ / pnpm 9+ / bun | `npm -v`、`yarn -v`、`pnpm -v`、`bun -v` |
| Expo CLI | 由 `expo` 包自带，不用全局装 | `npx expo --version` |
| EAS CLI（可选） | 需要云端构建/提交时 | `npm i -g eas-cli && eas --version` |
| Java（本地安卓编译） | JDK 17 | `java -version` |
| Xcode（本地 iOS 编译） | 仅 macOS | `xcodebuild -version` |

**判断项目当前 SDK 版本**，用这三条命令交叉验证：

```sh
# a) 兼容版本表：expo 包声明的 react-native / react 版本
npx expo install --check

# b) 项目实际装了什么
npm ls expo react-native react expo-router

# c) 是否存在版本错配
npx expo-doctor
```

写作时的版本快照（仅作参照，不要硬编码进项目）：

| 包 | 参考版本 |
|---|---|
| `expo` | 57.x（SDK 57） |
| `react-native` | 0.87.x |
| `react` | 19.x |
| `expo-router` | 57.x（与 SDK 同号） |
| `expo-dev-client` | 57.x |
| `create-expo-app` | 4.x |
| `eas-cli` | 24.x |

拿到实际版本后，用 `npx expo install --fix` 把不匹配的包拉回兼容版本。**不要用 `npm install <pkg>@latest` 直接装带原生代码的包**——React Native 不做向后兼容，版本错配的报错通常在原生编译阶段才炸，很难定位。

---

## 2. 建项目与项目类型判定

```sh
npx create-expo-app@latest my-app      # 交互式；--template default 为默认模板
cd my-app
```

`create-expo-app` 默认会生成 `AGENTS.md`、`CLAUDE.md` 和 `.claude/settings.json`，为 AI 编码助手提供与项目 SDK 版本对齐的上下文。如果不想要，加 `--no-agents-md`。

可选模板：

| 模板 | 何时用 |
|---|---|
| `default` | 大多数情况。多页面 + Expo Router + TypeScript |
| `blank` | 只要最小依赖，导航自己搭 |
| `blank-typescript` | 同上但开 TS |
| `tabs` | 底部标签导航起步 |
| `bare-minimum` | 需要 `android/`、`ios/` 直接生成（等于建完再跑一次 prebuild） |

建完先判定项目属于哪一类，这决定了后面所有操作：

```sh
# 有 android/ 和 ios/ 目录 → 手工原生工程（bare），原生目录已被纳入版本管理
# 没有这两个目录      → CNG（Continuous Native Generation）
ls            # Windows PowerShell: Get-ChildItem
```

判定之后照下表走：

| 项目类型 | 原生配置改在哪 | prebuild 可用 | 升级 SDK 难度 |
|---|---|---|---|
| CNG（推荐） | `app.json` / `app.config.js` + config plugin | 可用，`--clean` 安全 | 低，改版本号重装即可 |
| 手工原生（bare） | 直接改 `android/`、`ios/` | 不可用，跑了会覆盖你的改动 | 高，需逐项手工迁移 |

CNG 的等价关系（这三条命令产出接近同一个项目）：

```sh
npx create-expo-app@latest MyApp && cd MyApp && npx expo prebuild
npx create-expo-app --template bare-minimum
npx @react-native-community/cli@latest init MyApp && cd MyApp && npx install-expo-modules
```

---

## 3. 目录职责（新项目）

```
my-app/
├── app.json              # 唯一的原生配置源（CNG 模式下）
├── app.config.js         # 需要按环境分支时才用；存在则与 app.json 合并
├── eas.json              # 构建/提交档位
├── package.json
├── tsconfig.json
├── babel.config.js       # 可选，非 Expo CLI 工具链时需要
├── metro.config.js       # 可选，需自定义打包行为时生成
├── assets/               # 图标、启动图、字体
├── public/               # Web 静态文件，导出时原样拷进 dist/
├── src/
│   ├── app/              # ← 只放路由，别的什么都不要放
│   │   ├── _layout.tsx   # 根布局，等于以前的 App.tsx
│   │   ├── index.tsx     # 初始路由，对应 URL /
│   │   ├── (tabs)/       # 括号目录不进 URL，用来分组
│   │   └── profile/[id].tsx
│   ├── components/       # 普通组件
│   ├── hooks/
│   └── constants/
├── android/              # 仅手工原生工程存在
└── ios/                  # 仅手工原生工程存在
```

**Expo Router 的硬规则**（违反了会出现「莫名其妙的空白页面」）：

1. `src/app/` 下的每个文件都是一个有 URL 的页面，默认导出即页面组件。
2. `_layout.tsx` 是例外，它定义该层级的导航容器，不产生 URL。
3. 别的目录不要出现在 `src/app/` 里；只要放进去，Router 就把它当路由处理。
4. 根 `_layout.tsx` 是放字体加载、主题 Provider、启动屏控制的地方。
5. 文件名带 `[id]` 是动态段；`(group)` 只做分组不进 URL。

**平台分文件命名**（Metro 按平台自动选择）：

```
src/components/chart.tsx         # Web
src/components/chart.native.tsx  # iOS + Android
src/components/chart.ios.tsx     # 只要 iOS 单独实现时才加
src/components/chart.android.tsx
```

导入时统一写 `import Chart from '@/components/chart'`，不要自己判断平台去 import 具体文件。

---

## 4. 原生目录何时生成、何时重生成

```sh
# 首次生成（CNG 项目）
npx expo prebuild

# 改了 app.json 里影响原生的字段，或加了新的原生依赖后（推荐）
npx expo prebuild --clean

# 只重生成某一个平台
npx expo prebuild -p ios --clean
npx expo prebuild -p android --clean
```

判断「要不要重新 prebuild」的准则：这次改动是否改变了**原生工程文件内容**。

| 改了什么 | 要不要 prebuild | 要不要重新出包 |
|---|---|---|
| 页面、组件、样式、JS 逻辑 | 否 | 否（OTA 可推） |
| `app.json` 的 `name`、`icon`、`splash`、`ios.bundleIdentifier`、`android.package` | 是 | 要 |
| 权限文案（`ios.infoPlist`、插件里的 `*Permission`） | 是 | 要 |
| 新增带原生代码的依赖 | 是 | 要 |
| 环境变量 `EXPO_PUBLIC_*` 的值 | 否 | 否（重新 export/update 即可） |
| 仅 `eas.json` 的构建参数 | 否 | 只看是否影响产物 |

带 `--clean` 会删掉已有原生目录再生成。**手工原生工程绝对不能跑带 `--clean` 的 prebuild**，那等于丢弃团队的原生改动。

---

## 5. 环境变量与配置的分层

三层，别混：

| 层 | 写在哪 | 何时生效 | 能不能放密钥 |
|---|---|---|---|
| 构建期公开变量 | 根目录 `.env`，名字必须 `EXPO_PUBLIC_` 开头 | 打包时内联进 JS | **不能**，会明文进包 |
| 运行期读取的公开配置 | `app.json` 的 `extra`，用 `Constants.expoConfig.extra` 读 | 随二进制/manifest | 不能 |
| 服务端密钥 | EAS 环境变量（服务端）或自建后端 | 只在服务端使用 | 可以 |

```sh
# .env（可提交；.env*.local 应进 .gitignore）
EXPO_PUBLIC_API_BASE=https://api.example.com
```

```ts
// 必须用点号静态引用，解构或 [] 取值不会被内联
const base = process.env.EXPO_PUBLIC_API_BASE;   // ✅
// const { EXPO_PUBLIC_API_BASE } = process.env; // ❌ 拿不到值
```

排查变量不生效：

```sh
EXPO_NO_DOTENV=1 npx expo start        # 关掉 .env 自动加载，看是否还读得到
EXPO_NO_CLIENT_ENV_VARS=1 npx expo start  # 关掉客户端内联
```

EAS 构建时用 `eas env:pull` 拉取对应环境的变量，不要靠 `NODE_ENV` 切 `.env` 文件——`npx expo export` 会强制 `NODE_ENV=production`。

---

## 6. 升级 SDK 的顺序

1. 先在同一分支上把工作区改干净，确认 `git status` 没有未提交改动。
2. 改 `package.json` 里的 `expo` 版本，然后 `npx expo install --fix` 让全部 Expo 包对齐。
3. `npx expo-doctor`，逐条处理报错。
4. CNG 项目：`npx expo prebuild --clean` 重生成原生工程。
5. 手工原生工程：参照官方升级说明逐项改原生文件，**不要**用 prebuild 覆盖。
6. 三端各跑一次；再出一次 development build 验证原生层。
7. 阅读本次 SDK 的变更说明，重点看被废弃的 API（`npx expo-doctor` 常能提前发现）。

---

## 7. Agent 改这个仓库时的目录约束

- `src/app/` 下**只能**新增页面文件与 `_layout.tsx`；不要往里放工具函数、类型、常量。
- 不要手改 `android/`、`ios/`；需要原生配置就改 `app.json` 或加 config plugin。
- 不要手改 `package.json` 里的 Expo 相关依赖版本；一律用 `npx expo install <pkg>`。
- 不要新增第二个 lockfile；先看仓库里已存在哪个。
- 不要动 `README.md` 里已有的版权/许可证段落。
- 每次改完必须跑：`npx expo install --check` → `npx expo-doctor` → `npx tsc --noEmit`（若有 TS）。
