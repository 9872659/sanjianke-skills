# 环境搭建与连接

这一份解决「怎么把一台真手机接上，并确认它真的接通了」。连接问题看起来很像点击失效，先读完这份再怀疑操作。

---

## 一、前提清单

| 项目 | iPhone 路线 | 安卓路线 |
|---|---|---|
| 主机系统 | macOS Sequoia 及以上 | 任意能跑 adb 的系统 |
| 手机侧前提 | 与 Mac 完成配对（需实体手机操作） | 开发者选项已开 |
| 传输方式 | macOS 自带「iPhone 镜像」窗口 | adb（USB 或无线） |
| 终端权限 | 辅助功能 + 屏幕录制 | 无（USB 授权在手机侧） |
| Python | 3.10+ | 3.10+ |
| 可选工具 | — | scrcpy（长任务时看实时镜像） |

Python 侧只有 iPhone 路线需要额外依赖（pyobjc 的 Quartz / Vision / Cocoa / ApplicationServices），`pip install -e .` 会自动带上。装法：

```bash
# 上游仓库地址见 SKILL.md 的「快速开始」；约定俗成的落地目录是 ~/.phone-harness
git clone <上游仓库> ~/.phone-harness
cd ~/.phone-harness
pip install -e .
```

**只用命令行也可以** `pip install phone-harness`，但只有 checkout 装法才能改 `agent-workspace/agent_helpers.py`——想让 Agent 把验证过的步骤沉淀下来，就用 checkout。

装完立刻把 Agent 侧说明对齐一次：

```bash
phone-harness skill > <你的技能目录>/SKILL.md
```

上游代码更新后要重跑这一行，否则 Agent 按旧说明调用新代码。

---

## 二、iPhone 路线

### 2.1 用户必须亲手做的两件事

1. **配对「iPhone 镜像」**。打开这个 App，跟着它的配对提示走完。这一步要动到实体手机，Agent 代不了。
2. **给终端开两个权限**，在 System Settings → Privacy & Security：

| 权限 | 作用 | 生效时机 |
|---|---|---|
| 辅助功能 Accessibility | 点击与键入 | 立即生效 |
| 屏幕录制 Screen Recording | 看见手机画面 | **终端重启之后**才生效 |

两个面板可以直接跳：

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
```

**这两个是已知必需的，不代表只有这两个。** 全新机器上第一次真正执行动作时，macOS 可能追加弹出别的授权框。典型症状：`--doctor` 全绿，但点击 / 输入 / 截屏静默地什么都没发生——这时候去屏幕上找有没有没处理的授权弹窗。

### 2.2 截屏黑的三种原因

- 屏幕录制给了，但**终端没重启**。
- 镜像窗口上盖着提示层（「iPhone 在使用中」/「连接」/「Mac 已锁定」）。在 Mac 侧把它处理掉；如果提示说手机正在被使用，把 iPhone 锁屏。
- iPhone 被解锁了——解锁会暂停镜像会话。

### 2.3 焦点与后台投递

默认构建**不夺走用户焦点**：截屏按窗口 ID 走，点击和键入直接投递给目标 App。唯一例外是滚动——macOS 会把滚轮事件路由到指针下那个窗口，所以滚动期间镜像窗口会被抬到前面，手势结束立刻还回去。预期表现是滚动时闪一下，其他操作不闪。

`PHONE_HARNESS_BACKGROUND=0` 会强制走经典路径：每个动作前先把窗口激活。只在排查焦点问题时才用。

---

## 三、安卓路线

### 3.1 装 adb

```bash
brew install android-platform-tools      # adb
brew install scrcpy                      # 可选，实时镜像窗口
```

### 3.2 开开发者选项

设置 → 关于手机 → 连点「版本号」**7 次** → 设置 → 系统 → 开发者选项。

### 3.3 USB 路线

1. 开发者选项 → 打开「USB 调试」。
2. 插线。
3. 手机上弹出「允许 USB 调试？」→ 点「允许」，勾上「一直允许来自这台计算机」。

### 3.4 无线路线（Android 11+，手机与主机同一局域网）

1. 开发者选项 → 打开「无线调试」。
2. 点进「无线调试」那一行 → 「使用配对码配对设备」。
3. 把屏幕上显示的 **6 位码**读给命令：

```bash
phone-harness android pair 123456
```

手机按名称被记住，之后程序自己找、自己连，不需要再指定序列号。**注意无线调试在手机重启后会自己关掉**，这是「昨天还好好的今天连不上」的头号原因。

### 3.5 长任务保持唤醒

默认手机到点自己锁屏，一锁屏点击和读屏就全被拒。任务超过一分钟时：

```bash
phone-harness android awake --bg     # 任务期间保持不休眠；装了 scrcpy 会顺便开镜像窗口
phone-harness android rest           # 结束，让手机正常睡觉
```

它**不改任何手机设置**，只在这一个会话里有效。任务收尾一定要调 `rest`，否则等于替用户常亮屏幕。

### 3.6 看当前连接

```bash
phone-harness android                # 已知手机 + 当前接着哪台
adb devices                          # 看 adb 自己看见了什么
```

插着 USB 的手机永远优先于无线。

---

## 四、选择默认手机

设置分两层，另有单次覆盖：

```bash
phone-harness config                       # 列出全部设置及各项来源
phone-harness config set platform ios      # 或 android
PHONE_HARNESS_PLATFORM=android phone-harness <<'PY' ... PY   # 只对这一次生效
```

优先级：单次环境变量 > `config set` 的持久值 > 内置默认。

两条路互不干扰——iPhone 走镜像窗口，安卓走 adb，所以两台都配好、用上面三种方式切换是完全正常的用法。

关掉匿名使用统计：

```bash
phone-harness config set telemetry false
```

---

## 五、`--doctor`：先体检，再干活

```bash
phone-harness --doctor             # 默认手机
phone-harness --doctor ios         # 单独查 iPhone
phone-harness --doctor android     # 单独查安卓
```

它会按顺序走完整条依赖链并点名缺哪一步。**把它当成唯一的连接判据**：`--doctor` 通过后，再做一次只读验证（截一张图，把屏幕内容念回给用户），这一步通过才算真的接通。

### 5.1 报错对照

| 现象 / 报错 | 真实原因 | 处置 |
|---|---|---|
| 安卓 `no-device` | USB 调试没开、线或口有问题；无线调试因重启关闭；手机与主机不同网段 | 开调试、换线换口、重开无线调试、对齐网络；`adb devices` 看 adb 视角 |
| 安卓 `unauthorized` | 手机的授权弹窗没点，或没勾「一直允许」 | 解锁手机点「允许」；弹窗不出现就重新插拔 |
| 安卓 `locked` | 手机锁屏了 | 请用户解锁；长任务先 `android awake --bg` |
| 安卓无障碍树取不到 | 该界面一直在动画，`uiautomator` 等不到静止 | 改用 `screenshot()`，或换到会静止的界面 |
| iPhone 截屏全黑 | 终端未重启；镜像窗口有提示层；手机被解锁 | 重启终端；清掉提示层；把 iPhone 锁屏 |
| iPhone 点击无反应 | 缺辅助功能权限；或有别的窗口抢了焦点 | 补权限；检查是否弹出系统授权框；手动 `activate()` 一次 |
| `--doctor` 报 pyobjc 缺失但明明装过 | 跑的是另一个 Python 解释器 | 用 `pip install -e .` 时那个解释器，或给它单独装 pyobjc 三个 framework 包 |
| 提示 iPhone 在使用中 | 实体手机被解锁，镜像会话暂停 | 请用户锁屏；**不要**去点恢复界面上的按钮 |

### 5.2 连接状态机

`connection_state()` 返回四种状态，处置完全不同：

| 状态 | 含义 | Agent 该做什么 |
|---|---|---|
| `ready` | 可用 | 继续干活 |
| `blocked` | 有东西挡住（提示层 / 被占用） | 停下，转述，请用户处理 |
| `no-window` | 镜像窗口不在 | 停下，请用户打开 App |
| `not-running` | App 没运行 | 停下，请用户启动 |

**连接是用户的活。** 遇到非 `ready`：停下、转述原文、等用户确认做好了再重试一次。不要点 `Connect` / `Continue`，也不要循环轮询等它自己好——手机锁着的时候点「连接」什么也不会发生，轮询只是白烧时间。

---

## 六、搭建自检

- [ ] `--doctor` 对目标手机全绿。
- [ ] 完成过一次只读验证：截屏 + 把屏幕文字念回给用户。
- [ ] 确认了当前默认平台（`phone-harness config`），并知道怎么单次覆盖。
- [ ] iPhone：终端两个权限都给了，且给完之后重启过终端。
- [ ] 安卓：确认是 USB 还是无线，无线的话知道重启后会掉。
- [ ] 长任务记得 `awake --bg` 开头、`rest` 收尾。
- [ ] 不介意统计的话确认了 telemetry 的开关状态。
- [ ] 权限与隐私的边界已经和用户讲清（见 `stability-and-safety.md`）。
