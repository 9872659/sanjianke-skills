---
name: sanjianke-phone-agent-kit
slug: sanjianke-phone-agent-kit
displayName: 三剪客 · 手机自动化控制
description: "让 AI Agent 直接看屏、点击、输入，操作你的真手机。 遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "phone-harness 把 iPhone（macOS 镜像窗口）与安卓（adb）统一成一组 Python 助手函数：截图、取屏幕文字、按标签点击、输入、滑动与滚动，Agent 用脚本逐步操作真机并回读屏幕验证结果。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 手机自动化
  - RPA
---

# 三剪客 · 手机自动化控制

让 AI Agent 直接看屏、点击、输入，操作你的真手机。

有一类活，电脑和 API 都替不了：只在小程序或 App 里才有的入口、绑在手机号上的验证码、必须先登录的手机端后台、以及「这件事在真机上到底长什么样」。phone-harness 把一台真手机接成 Agent 的手和眼——iPhone 走 macOS 自带的 iPhone Mirroring 窗口，安卓走 adb，两条路共用同一套 Python 助手函数。

Agent 的循环很朴素：读屏 → 决定点哪 → 点下去 → 再读一次屏确认。`ocr()` 或安卓的无障碍树把屏幕上每一段可见文字连同可点击的中心坐标交回来，`tap_text()` / `tap_ui()` 按标签下手，`screenshot()` 补上文字读不到的东西（图标、图片、选中态）。这里没有 DOM，也没有一个「操作成功」的返回值——adb 对空点一下也报成功，所以每一步都得自己验证。

它适合：需要在真机上跑重复操作、做手机端端到端验收、替用户走一遍手机流程的团队。它不适合：只想抓网页数据、或在电脑上就能做完的事——那种情况别碰手机，快得多也安全得多。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 视需要 | 本 Skill 自身不发起任何请求。上游默认开启匿名使用统计，用 `phone-harness config set telemetry false` 关掉。安卓无线调试走的是本机与手机之间的局域网。 |
| 读取文件 | 是 | 读取你积累的任务助手 `agent-workspace/agent_helpers.py`、`phone-harness config` 的配置，以及截图产生的临时图片。 |
| 写入文件 | 视需要 | 把截图落盘备查；把验证过的可复用步骤写回 `agent-workspace/agent_helpers.py`。 |
| 凭证 | 否 | 本 Skill 不内嵌、不索取、不存储任何 Key / Token / Cookie。手机解锁用的 PIN 或密码由用户本人输入，Agent 不代输、不记录。 |
| 子进程 / 后台常驻 | 是 | 通过 shell 调用 `phone-harness` 与 `adb`。长任务用 `phone-harness android awake --bg` 让手机保持不休眠，任务结束用 `phone-harness android rest` 收尾。 |
| **读取屏幕内容** | 是（核心能力） | `screenshot()` 抓取手机画面；iPhone 再用 Apple Vision 做 OCR，安卓读无障碍树取文字与控件。**屏幕上出现的一切都会进入 Agent 的上下文**——通知、聊天记录、短信验证码、账号名、余额，抓什么就带什么。 |
| **模拟输入** | 是（核心能力） | 点击、长按、滑动、滚动、输入文字、按键。这些动作在真机上**等同于用户本人操作**，会被 App 当成真实用户行为。 |
| **连接与解锁手机** | 否（由用户完成） | 配对 iPhone Mirroring、开启 USB / 无线调试、点「允许」、解锁手机，全部由用户亲手完成。Agent 不代做，也永远不会替你输 PIN。 |

**这是一项高权限能力，请如实对待**：接入之后，Agent 能看见你手机屏幕上的内容，也能在你手机上点、滑、打字。它会把你看到的屏幕文字发回模型做判断，因此敏感界面（支付、银行、私密聊天）不该出现在被操作的屏幕上。误点可能造成真实后果：误发消息、误下单、误删数据、误改设置。**任何对外发送、下单、删除、改设置的动作，必须先经用户确认再执行。**

**零凭证**：本 Skill 不内嵌任何密钥，不代理转发，也不代收费用。它只是一份原创的操作规范，真正的程序由你按上游项目自行安装（MIT 许可）。

## 触发场景

- 「帮我在这台手机上把 XX App 的每日签到点掉」——重复的固定路径操作。
- 「看看我手机设置里的系统版本和机型是什么」——只读式的取信息。
- 「在我们 App 里走一遍注册流程，看看哪一步会卡」——手机端流程验收。
- 「这个功能只有 App 里有，网页版没有，你去手机上帮我看看」——没有 Web 替代品的场景。
- 「把手机上的那条推送通知念给我听 / 截个图给我」——读屏取材。
- 「这个操作要重复 50 次，我不想手点」——批量重复动作。
- 「Agent 说点不动了 / 屏幕一直黑的 / 提示没连上」——连接与权限排障。

## 快速开始

### 0. 装上游程序（一次）

```bash
git clone https://github.com/ShawnPana/phone-harness ~/.phone-harness
cd ~/.phone-harness
pip install -e .            # 装出全局命令 phone-harness；iPhone 侧会拉 pyobjc
```

需要 Python 3.10 或更高。只想用 CLI 也可以 `pip install phone-harness`，但 checkout 装法才能改 `agent-workspace/agent_helpers.py`。装完把 `phone-harness skill > <你的技能目录>/SKILL.md` 跑一遍，让 Agent 拿到与当前代码匹配的说明；上游更新后要重跑这一行。

### 1. 验链路（先别写业务脚本）

```bash
phone-harness --doctor            # 检查默认手机
phone-harness --doctor ios        # 单独检查 iPhone
phone-harness --doctor android    # 单独检查安卓
```

`--doctor` 会按顺序走完整条依赖链，并点名缺哪一步。**先让它全绿，再动业务**——连接问题装成「点击没反应」是最常见的误判。

- **iPhone**：需要 macOS Sequoia 及以上，并先在「iPhone 镜像」App 里把手机配对好（这一步要动到实体手机）。再给**终端**两个权限：辅助功能（点击与键入，立即生效）和屏幕录制（看见手机，终端重启后生效）。System Settings → Privacy & Security 里开。
- **安卓**：`brew install android-platform-tools` 装 adb（可选 `brew install scrcpy` 看实时镜像）。手机上连点「版本号」7 次开出开发者选项。USB 路线开「USB 调试」、插线、在手机上点「允许」；无线路线（Android 11+，同一局域网）开「无线调试」→「使用配对码配对设备」，把屏幕上的 6 位码交给 `phone-harness android pair 123456`。

### 2. 选默认手机

```bash
phone-harness config                    # 看全部设置及其来源
phone-harness config set platform ios   # 或 android
PHONE_HARNESS_PLATFORM=android phone-harness --doctor   # 只对这一次生效
```

两台手机互不干扰：iPhone 走镜像窗口，安卓走 adb。可以都配好，再用默认值或环境变量切换。

### 3. 第一个只读脚本

```bash
phone-harness <<'PY'
# task: 读出当前手机屏幕上的文字，不做任何点击
# step: 截屏并列出可见文字
print([o["text"] for o in ocr()][:10])
PY
```

助手函数已预导入，多行脚本用 heredoc。每个脚本开头写两行注释：`# task:` 一句话复述用户要什么（同一个请求的所有脚本保持这一行完全一致），`# step:` 说明这一段在做什么。先把只读的读屏跑通，再放开写操作。

### 4. 一次带点击的完整动作

```bash
phone-harness <<'PY'
# task: 打开备忘录并写入一行文字
# step: 打开 App、新建、输入、回读确认
open_app("Notes")
wait_stable()
tap_text("新建")            # iPhone 用 tap_text；安卓用 tap_ui("标签")
type_text("hello from the harness")
print([o["text"] for o in ocr()][:10])   # 回读：这一步才是验证
PY
```

**动作之后必须回读**。点、滑、输入都只是「发出去了」，没有任何返回值能证明它生效；失败大多是静默的空操作。廉价的做法是 `ocr()` 循环里比对一处文字，卡住了再 `screenshot()` 看图片。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 装环境、配对手机、开权限、`--doctor` 报错怎么读、iPhone 黑屏 / 安卓 unauthorized | `references/setup-and-connection.md` |
| 具体能干哪些操作、助手函数怎么调、iPhone 与安卓的差异、坐标怎么换算 | `references/operations-and-examples.md` |
| 怎么验证才可靠、锁屏与焦点这类坑、隐私与安全红线、成本与节奏 | `references/stability-and-safety.md` |

## 能力边界

**覆盖**：

- **连接与体检**：`phone-harness --doctor [ios|android]`、`phone-harness config` / `config set platform ios|android`、`PHONE_HARNESS_PLATFORM` 单次覆盖、`phone-harness android` 列出已知手机与当前连接、`connection_state()` 返回 `ready` / `blocked` / `no-window` / `not-running`。
- **看**：`screenshot()` 抓画面；`screen_info()` 取屏幕与窗口几何；`ocr()` 返回 `[{text, confidence, x, y, w, h}]`（iPhone 走 Vision，安卓走无障碍树，`source: "tree"`）；`ui()` / `find_nodes()` 在安卓上连无文字的图标（content-description）和按 resource-id 定位的输入框也能找到。
- **点**：`tap(x, y)`、`tap_text("标签")`、`long_press(x, y)`；安卓另有 `tap_ui("标签")` 与 `tap_ui("url_bar")` 这种按资源 ID 的命中；桌面图标要用 `tap_icon("Weather")`（Agent 侧助手），因为桌面图标标签本身不是点击目标。
- **输入**：`type_text("...")` 写入已聚焦的输入框，`press("return")` / `press("tab")` 单键，安卓另有 `press("back")`。
- **移动**：`scroll("down")` 系列（`scroll_screen()` 单步、`scroll_until(判断)` 到条件停、`scroll_collect(提取)` 边滚边收集并去重）、`swipe("up")` 翻页与轮播、`home()`、`app_switcher()`、`back()`。
- **等**：`wait_stable()`、`wait_for_app("com.android.chrome")`、`wait_for_text("Got it")`。
- **保持唤醒**：`phone-harness android awake --bg` 让手机在整个任务期间不休眠（不改任何手机设置），`phone-harness android rest` 结束。
- **积累**：把验证过的判断与修好的步骤写进 `agent-workspace/agent_helpers.py`，下一个任务从更高的起点开始。

**不覆盖**：

- **不连手机、不解锁**。配对、点「允许」、锁屏解屏都是用户的物理动作。Agent 不该点 `Connect` / `Continue`，也不该轮询等连接——那只会白烧时间。
- **不输 PIN、不碰密码**。iPhone 解锁会打断镜像会话；安卓锁屏后 `tap()` 和 `ocr()` 会直接拒绝。这两种情况都停下来请用户本人处理。
- **不做多点触控**。没有捏合缩放，没有双指手势。
- **不覆盖相机与 Face ID 流程**，DRM 视频在镜像窗口里是黑的。
- **不保证识别图标**。OCR 只认文字；没有文字的可点控件必须靠截图交给有视觉能力的模型，Agent 自己看。
- **不做网页抓取**。要抓网页数据用专门的采集 Skill，别绕手机。
- **不替你做合规判断**。只操作你自己或已获明确授权的设备。
- **本 Skill 不含任何第三方源码**。正文为原创整理，只引用命令、函数名、错误码、许可证这类事实信息。

## 依赖条件

- **运行时**：Python 3.10+；上游包 `phone-harness`（当前 0.2.0，`pip install -e .` 安装，入口命令即 `phone-harness`）。
- **iPhone 路线**：macOS Sequoia 及以上 + 已配对的「iPhone 镜像」；终端获得**辅助功能**与**屏幕录制**两个权限；Python 侧需要 pyobjc 的 Quartz / Vision / Cocoa / ApplicationServices（`pip install -e .` 会带上）。
- **安卓路线**：adb（`android-platform-tools`），可选 scrcpy 看实时镜像；手机已开 USB 调试并授权，或已开启无线调试并配对；两端在同一局域网（无线时）。
- **系统**：上游 `pyproject.toml` 把环境标为 macOS，iPhone 路线只能跑在 Mac 上；安卓路线通过 adb，Windows / Linux 也能用 adb 那条链。
- **网络**：不需要访问公网；关闭匿名统计后无任何出网行为。

## 已知限制

- **没有「成功」返回值**。所有助手交回的是观察结果，不是判定。判定只能由你按预期内容自己做。
- **文字读得到，图标读不到**。`ocr()` 给你文字与坐标；图标、图片、是否高亮只能看 `screenshot()`。
- **坐标不能跨调用缓存**。镜像窗口会移动，`ocr()` 和 `swipe()` 每次都重新取窗口边界。截图里的像素坐标**不能**直接喂给 `tap()`（`tap()` 要的是屏幕点），必须先按当前 `screen_info()` 换算。
- **`type_text` 是粘贴不是逐键输入**，这是刻意的——iOS 的自动更正会把逐键输入改写掉。代价是文字会留在 Mac 剪贴板里。需要真实按键事件时传 `keystrokes=True`。另外它**必须先有聚焦的输入框**，否则静默失败：字要么进了别的控件，要么哪都没去。
- **列表和信息流要用 `scroll()`，不要用竖向 `swipe()`**。在新版 macOS 上竖向的触摸拖拽会被丢弃，`swipe("up")` / `swipe("down")` 在列表里什么都不动；横向仍可用，所以翻桌面和轮播还是用 `swipe("left")` / `swipe("right")`。
- **`scroll` 说的是内容方向，`swipe` 说的是手指方向**，两者故意相反：`scroll("down")` = 想看更下面的内容，`swipe("up")` = 手指上滑（大家口中的「下一个」）。
- **焦点会偷走输入**。Agent 自己发的原始事件、以及 `PHONE_HARNESS_BACKGROUND=0` 那条经典路径，都需要窗口在最前；手势毫无反应时先查焦点，别急着换理论。默认构建走后台投递，除滚动外不会夺走用户焦点。
- **桌面图标标签不是点击目标**，图标大致在标签上方 35 点处。
- **安卓无障碍树在持续动画的界面上取不到**（`uiautomator` 等不到 idle），这时改用 `screenshot()` 或换一个会静止的界面。安卓树一次调用约 2–3 秒，截图约 0.5 秒，`wait_for_app` 每次轮询约 0.1 秒——所以把已经看过的步骤打包成一次调用很值，但打包的必须是验证过的步骤。
- **锁屏是硬边界**。安卓锁屏后点击与读屏被拒，iPhone 解锁会暂停镜像会话（提示「iPhone 在使用中」）。只能请用户解锁 / 锁定，等待不会有结果。
- **上游自标 Alpha**（Development Status: 3 - Alpha），接口可能变动；拉取更新后要重跑 `phone-harness skill` 让说明与代码对齐。
- **匿名使用统计默认开启**，介意就 `phone-harness config set telemetry false`。

## 自检清单

- [ ] 跑过 `phone-harness --doctor`（必要时加 `ios` / `android`），链路全绿才开始写业务脚本。
- [ ] 每个脚本都有 `# task:` 和 `# step:` 两行注释，同一请求的 `# task:` 完全一致。
- [ ] 动作之前先说清「什么该变」，动作之后**回读屏幕**确认它变了。
- [ ] 至少先跑通一个只读脚本（`ocr()` / `screenshot()`），再放开写操作。
- [ ] 用了 `ocr()` 做廉价检查，只在卡住或答案本身是视觉的时候才上 `screenshot()`。
- [ ] 没有把截图像素坐标直接传给 `tap()`；需要时走了 `image_point()` 换算。
- [ ] 没有跨调用缓存坐标。
- [ ] `type_text` 之前确认输入框已聚焦、键盘已出现。
- [ ] 列表和feed 用的是 `scroll()`，不是竖向 `swipe()`。
- [ ] 遇到连接失败时**停下并转述**提示，没有点 `Connect`、没有轮询重试。
- [ ] 没有试图输入 PIN，没有替用户解锁手机。
- [ ] 对外发送、下单、删除、改设置这类动作前，已经征得用户同意。
- [ ] 敏感界面（支付、私密聊天、验证码）没有让它停留在被读取的屏幕上。
- [ ] 长任务用了 `phone-harness android awake --bg`，并在结束时 `phone-harness android rest`。
- [ ] 跑完把可复用的判断与修好的步骤写进了 `agent-workspace/agent_helpers.py`。
- [ ] 只操作了自有或已获授权的设备。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/setup-and-connection.md` | 环境搭建与连接：iPhone 镜像配对与两个权限、安卓 USB / 无线两条路线、`config` 与 `--doctor` 用法、连接状态机与常见报错对照 |
| `references/operations-and-examples.md` | 操作能力与调用示例：读屏 / 定位 / 点击 / 输入 / 滚动 / 等待的函数清单，iPhone 与安卓的差异，坐标系换算，可直接改用的脚本片段 |
| `references/stability-and-safety.md` | 稳定性与安全边界：验证循环怎么写、锁屏与焦点这类静默失败、权限与隐私红线、该停下来问用户的时机、节奏与成本 |

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
