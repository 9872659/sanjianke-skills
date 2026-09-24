# 跨端能力与平台差异

本文对应 SKILL.md「工作流路由」的第二行。核心结论先给：**Expo 的跨端不是「一次编写处处相同」，而是「一次编写、三端各自收口」。**能不能跨端，取决于你选的那层抽象。选错了，Web 端就是靠一堆 `if (Platform.OS === 'web')` 硬撑。

---

## 1. 三端抽象的分层模型

从上到下，能复用的比例越来越低：

| 层 | iOS | Android | Web | 复用度 |
|---|---|---|---|---|
| React 组件与业务逻辑 | ✅ | ✅ | ✅ | 高 |
| RN 核心组件（`View`/`Text`/`Pressable`/`FlatList`） | ✅ | ✅ | ✅（走 react-native-web） | 高 |
| Expo Router 路由 | ✅ | ✅ | ✅（另有真实 URL） | 高 |
| 纯 JS 计算的库（日期、表单、状态机） | ✅ | ✅ | ✅ | 高 |
| Expo SDK 里标注了三端的模块 | ✅ | ✅ | ✅ | 中高 |
| 只标注 native 的模块（相机、通知、安全存储、文件系统） | ✅ | ✅ | ❌ | 需降级 |
| 原生 UI（原生标签栏、Widget、Live Activity） | 部分 | 部分 | ❌ | 需分平台实现 |
| 原生代码（自己写的模块） | ✅ | ✅ | ❌ | 需 Web 兜底实现 |

判断一个库能不能上 Web，看两处：官方 API 页顶部的平台标签、React Native Directory 上的平台徽章。**标了 native only 的模块装上去不一定报错，但一跑 Web 就白屏或抛异常**——所以要在引入前就决定降级方案。

---

## 2. 三端能力矩阵（常用模块）

| 能力 | 推荐模块 | iOS | Android | Web | Web 上的替代方案 |
|---|---|---|---|---|---|
| 相机预览与拍照 | `expo-camera` | ✅ 真机 | ✅ 真机 | ✅ 需 HTTPS | 直接复用，注意返回值差异 |
| 选图 / 拍照（系统 UI） | `expo-image-picker` | ✅ | ✅ | ✅ | 直接复用；Web 走 `<input type=file>` |
| 本地通知 / 定时通知 | `expo-notifications` | ✅ | ✅ | ❌ | 无。Web 用 Notification API 或干脆不做 |
| 远程推送 | `expo-notifications` | ✅ | ✅（需 dev build） | ❌ | Web Push，另一套体系 |
| 敏感键值存储 | `expo-secure-store` | ✅ | ✅ | ❌ | `localStorage`（安全性显著下降） |
| 普通键值存储 | `expo-sqlite/kv-store` | ✅ | ✅ | ✅ | 直接复用 |
| 关系型本地库 | `expo-sqlite` | ✅ | ✅ | ⚠️ alpha | 需 wasm + COOP/COEP 头 |
| 文件读写 | `expo-file-system` | ✅ | ✅ | ❌ | IndexedDB / Cache API |
| 媒体库存取 | `expo-media-library` | ✅ | ✅ | ❌ | 无 |
| 定位 | `expo-location` | ✅ | ✅ | ✅ 需 HTTPS | 浏览器 Geolocation |
| 打开外部链接 / 深链 | `expo-linking`、`expo-web-browser` | ✅ | ✅ | ✅ | 直接复用（Web 是普通 URL） |
| 触感反馈 | `expo-haptics` | ✅ | ✅ | ❌ | 空实现或 UI 反馈替代 |
| 剪贴板 | `expo-clipboard` | ✅ | ✅ | ✅ | 浏览器 Clipboard API |
| 分享 | `expo-sharing` | ✅ | ⚠️ 部分 | ❌ | `navigator.share` |
| 屏幕方向 | `expo-screen-orientation` | ✅ | ✅ | ❌ | CSS 媒体查询 |
| 生物识别 | `expo-local-authentication` | ✅ | ✅ | ❌ | WebAuthn（另一套） |
| 崩溃与监控 | Sentry / 自建 | ✅ | ✅ | ✅ | 直接复用 |

**用表的方法**：先在表里找到你要的能力，Web 列是 ❌ 的，就问自己「这个功能在网页版是必须的吗」。不是必须 → 直接不渲染入口。是必须 → 落到第 3 节的降级模式之一。

---

## 3. 平台差异的四种处理模式

### 模式一：分平台文件（推荐，零运行时判断）

Metro 按平台解析后缀，同名文件互不干扰：

```
src/components/scanner.tsx          # Web：文件上传 / 手输编码
src/components/scanner.native.tsx   # iOS + Android：CameraView
```

业务代码永远只写：

```ts
import Scanner from '@/components/scanner';
```

好处：Web 打包产物里根本不会出现 `expo-camera` 的原生调用，也就不会出现「Web 上 import 就报错」的问题。**凡是替换整块实现的，都用这个模式。**

### 模式二：`Platform.select`（适合小差异）

```ts
import { Platform, StyleSheet } from 'react-native';

const hitSlop = Platform.select({ web: 0, default: 8 });
const elevation = Platform.select({
  web: { boxShadow: '0 2px 8px rgba(0,0,0,.12)' },
  android: { elevation: 4 },
  ios: { shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 8 },
});
```

规则：三端共用同一棵树、只有属性/数值不同时用它；一旦分支里要 `import` 不同模块，回到模式一。

### 模式三：能力探测后降级（适合「可能没有」的硬件）

```ts
import * as Camera from 'expo-camera';
import { Platform } from 'react-native';

export async function canUseCamera() {
  if (Platform.OS === 'web') {
    // Web 上要自己判断设备有没有摄像头
    return await Camera.isAvailableAsync();
  }
  const { granted, canAskAgain } = await Camera.getCameraPermissionsAsync();
  return granted || canAskAgain;
}
```

不要用「平台名」推断硬件是否存在：Android 模拟器没有可用相机、iOS 模拟器没有摄像头、桌面浏览器常常没有。**先探测，再申请，再降级。**

### 模式四：统一适配层（适合多个页面都要用）

把差异收在一个文件里，对外只暴露 Promise：

```ts
// src/platform/storage.ts —— 一个入口，三端各自实现
export interface KV {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}
```

- `storage.native.ts`：敏感字段走 `expo-secure-store`，其余走 `expo-sqlite/kv-store`。
- `storage.web.ts`：统一走 `localStorage`，并在注释里写清安全性下降的边界。

这样「Web 上不安全」这件事只在一处被声明，评审时一眼能看到。

---

## 4. 原生能力：构建期配置 + 运行期调用

这是最容易踩的坑，务必记住这条因果链：

```
app.json 里的权限配置  →  npx expo prebuild  →  原生工程文件  →  编译出二进制
                                                                    ↓
                                         运行期 JS 里的 requestPermissionAsync 才能成功
```

**只写运行期代码、不写构建期配置，结果是：本地 Expo Go 里能弹窗（因为 Expo Go 自己声明了权限），你自己出包后弹窗根本不出现，参数永远是 denied。**这是最典型的「提审前几天才发现」的问题。

### 4.1 权限配置对照

Android 侧重在 `AndroidManifest.xml`，通过 `app.json` 的 `android.permissions` 追加、`android.blockedPermissions` 移除：

```json
{
  "expo": {
    "android": {
      "permissions": ["android.permission.SCHEDULE_EXACT_ALARM"],
      "blockedPermissions": ["android.permission.RECORD_AUDIO"]
    }
  }
}
```

iOS 侧重在 `Info.plist` 的用途说明文案，通过 `ios.infoPlist` 或各模块的 config plugin 设置：

```json
{
  "expo": {
    "ios": {
      "infoPlist": {
        "NSCameraUsageDescription": "用于扫描工单二维码，只有按下扫码按钮时才会打开相机。"
      }
    }
  }
}
```

两者都不支持 OTA 更新。改文案 = 必须出新包。

### 4.2 相机：完整的两段式写法

构建期（`app.json`）：

```json
{
  "expo": {
    "plugins": [
      ["expo-camera", {
        "cameraPermission": "用于扫描工单二维码，只有按下扫码按钮时才会打开相机。",
        "microphonePermission": "录制现场视频时需要收音。",
        "recordAudioAndroid": true
      }]
    ]
  }
}
```

运行期：

```tsx
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Text, View, Button } from 'react-native';

export default function ScanScreen() {
  const [permission, requestPermission] = useCameraPermissions();

  if (!permission) return <View />;                    // 权限状态还在读
  if (!permission.granted) {
    return (
      <View>
        <Text>需要相机权限才能扫码</Text>
        <Button
          title={permission.canAskAgain ? '授予权限' : '去设置里开启'}
          onPress={requestPermission}
          disabled={!permission.canAskAgain}
        />
      </View>
    );
  }

  return (
    <CameraView
      style={{ flex: 1 }}
      facing="back"
      barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
      onBarcodeScanned={({ data }) => console.log(data)}
    />
  );
}
```

要点：

- **同一时刻只能有一个相机预览**。多页面时需要在该屏失焦时卸载 `CameraView`，否则会黑屏。
- 原生上 `takePictureAsync()` 给的是 `file://` 缓存路径，**缓存会被清掉**，要留存必须自己拷到 document 目录。
- Web 上 `takePictureAsync()` 返回的 `uri` 就是 base64，没有文件路径。
- Web 上必须在用户手势（点击）里调用，否则浏览器静默拦截。
- 跨域 iframe 里用相机，iframe 需要 `allow="microphone; camera;"`。

### 4.3 通知：Android 13 的顺序陷阱

构建期：

```json
{
  "expo": {
    "plugins": [
      ["expo-notifications", {
        "icon": "./assets/notification-icon.png",
        "color": "#1F6FEB",
        "defaultChannel": "default",
        "enableBackgroundRemoteNotifications": false
      }]
    ]
  }
}
```

运行期，**顺序不能颠倒**：

```ts
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

// 1) Android 13 起，必须先建 channel，否则权限弹窗不会出现
if (Platform.OS === 'android') {
  await Notifications.setNotificationChannelAsync('default', {
    name: '默认通知',
    importance: Notifications.AndroidImportance.MAX,
  });
}

// 2) 再拿权限
const current = await Notifications.getPermissionsAsync();
let status = current.status;
if (status !== 'granted') {
  status = (await Notifications.requestPermissionsAsync()).status;
}

// 3) 最后才拿 token
const token = status === 'granted'
  ? (await Notifications.getExpoPushTokenAsync({ projectId })).data
  : null;
```

- iOS 的授权状态要看 `ios.status`，不要只看根 `status`：`PROVISIONAL`（临时授权）能发但不会响铃，`DENIED` 才需要引导去设置。
- 前台收到通知默认不展示，要 `Notifications.setNotificationHandler({...})` 明确声明 `shouldShowBanner` / `shouldShowList`。
- Android 上要精确时间触发定时通知，需要在 `android.permissions` 里显式加 `SCHEDULE_EXACT_ALARM`。
- 点通知跳转页面：在根 `_layout.tsx` 里监听 `addNotificationResponseReceivedListener` 与 `getLastNotificationResponse()`，读 `content.data.url` 后 `router.push(url)`——这样通知跳转和深链走的是同一套路由。
- Android 从推送冷启动时，debug 包的启动屏可能不显示（约七成概率），这是已知问题，release 包不复现；要验证就 `npx expo run:android --variant release`。

### 4.4 存储：先分敏感度，再选模块

| 数据 | 存哪 | Web 兜底 | 注意 |
|---|---|---|---|
| token、refresh token、支付凭据 | `expo-secure-store` | `localStorage`（不安全，需在代码里标注） | iOS Keychain 卸载重装后可能还在；Android 卸载即清 |
| 用户偏好、草稿、缓存 | `expo-sqlite/kv-store` | 同模块，Web 也支持 | 是 AsyncStorage 的替代，API 同名 |
| 结构化数据（离线队列、日志） | `expo-sqlite` | alpha，需 wasm + COOP/COEP | Web 端见下方 |

SecureStore 的硬约束：

```ts
import * as SecureStore from 'expo-secure-store';

await SecureStore.setItemAsync('refresh_token', token);
const t = await SecureStore.getItemAsync('refresh_token');
```

- **值不要太大**。历史上部分 iOS 版本拒绝超过约 2048 字节的值，Expo 不做限制，超限会由原生层报错，所以要 `try/catch`。
- 开了 `requireAuthentication: true` 后，用户新增指纹或改人脸会**直接让已存的值失效**，读出来是 `null`，业务要能接受重新登录。
- keys 只允许字母数字和 `.`、`-`、`_`。

SQLite 上 Web 的前置条件（缺一样就跑不起来）：

```js
// metro.config.js —— 需要支持 .wasm
const { getDefaultConfig } = require('expo/metro-config');
const config = getDefaultConfig(__dirname);
config.resolver.assetExts.push('wasm');
module.exports = config;
```

```json
// app.json —— 部署时服务端必须带这两个响应头，否则 SharedArrayBuffer 不可用
{
  "expo": {
    "plugins": [["expo-router", {
      "headers": {
        "Cross-Origin-Embedder-Policy": "credentialless",
        "Cross-Origin-Opener-Policy": "same-origin"
      }
    }]]
  }
}
```

自建静态托管时，这两个头要自己在 Nginx / CDN 上配，否则 SQLite 一到 Web 就抛错。

### 4.5 文件与网络

- 路径分三类，别混用：`Paths.cache`（可被系统清）、`Paths.document`（长期）、`Paths.appleSharedContainers`（iOS 共享容器）。
- `new File(...)` / `new Directory(...)` 这套是同步风格类 API，**只在原生可用**；老的 `FileSystem.readAsStringAsync` 一类方法已废弃，调用会直接抛错，历史代码要用 `expo-file-system/legacy` 才能跑。
- 上传大文件用 `fetch` from `expo/fetch`，可以直接把 `File` 当 body 或塞进 `FormData`，不用手搓 base64。
- 下载有 `DownloadTask`，支持暂停/恢复；`savable()` 存的状态可以持久化后再 `fromSavable()` 恢复，适合做断点续传。

---

## 5. Web 端独有的三件事

### 5.1 安全上下文

相机、定位、剪贴板等能力只在 `https://` 或 `http://localhost` 下可用。局域网用 IP 地址访问（`http://192.168.x.x:8081`）时这些能力**一律不可用**，这不是 bug。要真机测 Web 相机，用 `npx expo start --tunnel` 拿一个 https 域名。

### 5.2 路由即 URL

Expo Router 的每个页面在三端都有一个地址：原生是 `myapp://profile/42`，Web 是 `https://site/profile/42`。这意味着：

- 深链、分享、SEO 都白拿，但页面必须能处理**直接打开子路由**（没有前置导航栈）。
- 鉴权守卫要写在根 `_layout.tsx`，不能只写在首页。

### 5.3 打包产物

```sh
npx expo export --platform web          # 产物进 dist/，可丢任意静态托管
npx expo export --platform web --no-ssg # 不生成静态 HTML，只要 SPA
npx expo export                          # 默认三端都导
```

`dist/` 里是纯静态文件；`public/` 目录的内容会原样拷进去。部署到子路径时给 `app.json` 设 `experiments.baseUrl`，并注意 `<a>` 直接写的链接不会被自动加前缀。

---

## 6. 跨端组件与样式的实操约定

- **布局**：只用 flex。不要用 `width: '100vw'`、`position: fixed`、`float` 这类只对 Web 生效的写法。
- **滚动**：用 `ScrollView` / `FlatList`。不要用 `overflow: scroll` + 自定义滚动条。
- **点击**：用 `Pressable`。`onClick` 在原生不存在。
- **文本**：所有文本必须包在 `<Text>` 里，Web 上裸字符串能渲染、原生上会直接崩。
- **阴影**：三端写法不同，收进一个 `shadow` 常量（见模式二）。
- **安全区**：用 `react-native-safe-area-context`，Web 上它退化为普通 padding，成本可接受。
- **长列表**：`FlashList` 三端可用，优先于 `FlatList`。
- **动画**：`react-native-reanimated` 三端可用；避免用 `LayoutAnimation`（Web 行为不一致）。

---

## 7. 三端验证的最小清单

每次改动涉及平台差异时，按这个顺序过：

```sh
npx expo start          # 一次起服务
# 按 W → 浏览器打开，检查 Web 是否有 white screen / import 报错
# 按 A → Android 模拟器或真机
# 按 I → iOS 模拟器（仅 macOS）
npx expo export --platform web   # 确认 Web 能真正打包出产物，而不只是 dev 能跑
```

最后一条最容易被跳过：**dev 能跑不等于 build 能过**。Web 端引用到 native-only 模块的问题，常常只在 export 阶段暴露。
