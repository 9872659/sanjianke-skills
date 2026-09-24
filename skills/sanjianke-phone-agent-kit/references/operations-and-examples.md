# 操作能力与调用示例

这一份是「接上之后能干什么、怎么写脚本」。所有助手函数都已预导入，脚本通过 `phone-harness` 的 heredoc 执行。

---

## 一、调用形态

```bash
phone-harness <<'PY'
# task: 一句话复述用户要什么
# step: 这一段脚本在做什么
print([o["text"] for o in ocr()][:10])
PY
```

- 每个脚本开头两行注释：`# task:`（同一请求的所有脚本保持逐字一致）与 `# step:`。
- 多行逻辑一律走 heredoc，不要拼成一行 `-c`。
- 所有坐标都是**全局屏幕点**（iPhone）或**设备像素**（安卓），不是截图里的像素。

---

## 二、能力总表

### 看

| 函数 | 返回 | 说明 |
|---|---|---|
| `screenshot()` | 图像 | 抓当前画面。锁屏时仍可用（安卓也是），适合拿给用户看 |
| `screen_info()` | 屏幕与窗口几何 | 换算坐标的唯一正确来源 |
| `ocr()` | `[{text, confidence, x, y, w, h}]` | 每段可见文字 + 可直接点的中心点。iPhone 走 Vision；安卓走无障碍树（`source: "tree"`），精确无错字 |
| `ui()` | 无障碍节点 | 仅安卓。能看到没有可见文字的图标、以及按 resource-id 定位的控件 |
| `find_nodes()` | 节点集合 | 仅安卓。按属性筛控件 |
| `ocr_pixels()` | — | 仅 iPhone。安卓上不支持 |

### 点

| 函数 | 说明 |
|---|---|
| `tap_text("Weather")` | 按标签点。失败时抛出的信息里会带上**当前实际可见的内容**，先读它再决定重试 |
| `tap(x, y)` | 按坐标点。要的是屏幕点 / 设备像素，**不是截图像素** |
| `long_press(x, y)` | 长按 |
| `tap_ui("Got it")` | 仅安卓。按无障碍树的精确标签点 |
| `tap_ui("url_bar")` | 仅安卓。按 resource-id 点，输入框这类无文字控件靠它 |
| `tap_image_point(x, y, image_size=...)` | 用截图里量到的坐标点。它负责换算 |
| `image_point(x, y)` | 手动换算：把截图像素转成当前 `screen_info()` 下的屏幕点 |
| `tap_icon("Weather")` | Agent 侧助手。桌面图标专用，因为桌面图标标签本身不是点击目标 |

### 输入

| 函数 | 说明 |
|---|---|
| `type_text("...")` | 写入**已聚焦**的输入框。默认走粘贴（避免 iOS 自动更正改写），文字会留在 Mac 剪贴板；`keystrokes=True` 走真实按键事件 |
| `press("return")` | 单键。iPhone 支持 `return` / `tab`；安卓另有 `back`。组合键不支持 |

### 移动

| 函数 | 说明 |
|---|---|
| `scroll(direction, amount, at=...)` | 一次滚动手势。**`direction` 说的是内容方向**：`scroll("down")` = 让我看到更下面的内容 |
| `scroll_screen()` | 单步原语，返回 `before` / `after` / `boxes`；算不算「滚成功」由你判断 |
| `scroll_until(done)` | 用你对可见文字的判断决定何时停 |
| `scroll_collect(extract, key=...)` | 边走列表边提取并去重，返回 `{items, stop, scrolls}`，`stop` 为 `'reached-end'` 或 `'max-scrolls'` |
| `swipe("up")` | 手指方向：`up` = 手指上滑。横向翻页与轮播用它 |
| `home()` / `app_switcher()` / `back()` | 系统导航。`back()` 仅安卓 |
| `open_app("Notes")` | iPhone 走 Spotlight；安卓匹配已安装包名并返回实际启动的那个 |

**方向为什么相反**：英文里「scroll down the page」和「swipe up for the next video」说的是同一个结果。所以 `scroll` 一律取内容方向，只有 `swipe` 取手指方向。`left` / `right` 两边同义。

**竖向别用 swipe**：新版 macOS 会丢弃竖向触摸拖拽，`swipe("up")` / `swipe("down")` 在列表和信息流里什么都不动（在设置和短视频上实测如此）。列表、feed、任何可滚区域都用 `scroll()`；横向的 `swipe("left")` / `swipe("right")` 依然有效。

### 等

| 函数 | 说明 |
|---|---|
| `wait_stable()` | 等界面稳定下来 |
| `wait_for_app("com.android.chrome")` | 仅安卓。等指定包在前台，每次轮询约 0.1 秒 |
| `wait_for_text("Got it")` | 返回文字框或 `None`。判断「出现了吗」用它，比整屏 OCR 便宜 |
| `interruption(before, after)` | 报告这期间有没有被别的东西打断。iPhone 后台路径下永远报未打扰 |

### 状态与连接

| 函数 | 说明 |
|---|---|
| `ensure_mirroring()` | 拉起镜像窗口并对连接把关。没接通就抛清晰错误 |
| `connection_state()` | `ready` / `blocked` / `no-window` / `not-running` |
| `current_app()` / `list_apps()` | 仅安卓。当前前台包、已安装列表 |

---

## 三、坐标系：最容易搞错的一处

| 平台 | `tap(x, y)` 要什么 | 截图坐标关系 |
|---|---|---|
| iPhone | macOS 全局屏幕点 | 截图是窗口图，**像素 ≠ 屏幕点**。必须先 `image_point()` 换算，或直接用 `tap_image_point(..., image_size=...)` |
| 安卓 | 设备像素 | 截图与 `tap(x, y)` 是 1:1，可以直接用 |

iPhone 上**绝不要**把截图里的像素坐标直接喂给 `tap()`，也**绝不要**自己估窗口偏移量——窗口位置是会变的，用 `image_point()` 按当前 `screen_info()` 换算。同理，不要在多次调用之间缓存坐标。

---

## 四、示例

### 4.1 只读：把当前屏幕的文字读回来

```bash
phone-harness <<'PY'
# task: 报告当前手机屏幕上显示的内容
# step: 只读，列出前 15 段可见文字
rows = ocr()
for r in rows[:15]:
    print(round(r["confidence"], 2), r["text"])
PY
```

先跑通这个。任何写操作之前都该有一次成功的只读。

### 4.2 打开 App → 输入 → 回读验证

```bash
phone-harness <<'PY'
# task: 在备忘录里写下一条待办
# step: 打开、新建、输入、回读同一处文字确认落地
open_app("Notes")
wait_stable()
tap_text("新建")
wait_stable()
type_text("买咖啡豆")
wait_stable()
texts = [o["text"] for o in ocr()]
assert any("买咖啡豆" in t for t in texts), texts[:20]
print("verified")
PY
```

要点：**输入之后一定回读**。`type_text` 在输入框没聚焦时是静默失败的——字可能进了别的控件，也可能哪都没去。

### 4.3 安卓：按资源 ID 点输入框再说话

```bash
PHONE_HARNESS_PLATFORM=android phone-harness <<'PY'
# task: 在 Chrome 里访问一个网址
# step: 打开 Chrome，点地址栏，输入，回车，等页面稳定
open_app("chrome")
wait_stable()
tap_ui("url_bar")            # 按 resource-id 命中，无文字控件也能点
type_text("example.com")
press("enter")
wait_stable()
print([o["text"] for o in ocr()][:8])
PY
```

安卓的 `ocr()` 就是无障碍树，文字精确，优先用 `ui()` / `find_nodes()` / `tap_ui()`，它们连没有可见文字的元素也能看见。

### 4.4 滚动收集一列条目

```bash
phone-harness <<'PY'
# task: 收集列表里前 20 个条目
# step: 边滚边提取，去重，到端或到上限即停
def extract(rows):
    return [r["text"] for r in rows if len(r["text"]) > 3]

result = scroll_collect(extract, key=lambda t: t)
print(result["stop"], len(result["items"]), result["scrolls"])
for t in result["items"][:20]:
    print(t)
PY
```

`scroll_collect` 是**按你的提取器**判断有没有新东西的：提取器漏行，遍历就会提前结束。先确认提取器稳健，再去怀疑滚动。

### 4.5 等一个东西出现

```bash
phone-harness <<'PY'
# task: 等页面加载完成后读出标题
# step: 轮询目标文字，出现后整屏读一次
box = wait_for_text("Got it")
print("found" if box else "not found")
if box:
    print(box)
    print([o["text"] for o in ocr()][:5])
PY
```

### 4.6 目标在截图里可见但 OCR 读不到

```bash
phone-harness <<'PY'
# task: 点一个没有文字的图标
# step: 先截图，人工/视觉确认坐标后换算点击
shot = screenshot()
info = screen_info()
print(info)
# 看过图片、量到截图坐标 (x, y) 之后再执行：
# tap_image_point(x, y, image_size=<截图尺寸>)
PY
```

先看图片，再用 `tap_image_point()`。不要凭感觉估坐标。

---

## 五、两个平台的差异一览

| 项目 | iPhone | 安卓 |
|---|---|---|
| 取文字 | Vision OCR，可能有识别误差 | 无障碍树，精确；`ocr_pixels()` 不支持 |
| 点击定位 | `tap_text` / `tap_icon` / 坐标 | `tap_text` / `tap_ui`（支持标签与 resource-id） |
| 无文字控件 | 只能靠截图 + 视觉模型 | `ui()` / `find_nodes()` 直接看得到 |
| 坐标单位 | 全局屏幕点（需换算） | 设备像素（1:1） |
| 焦点 | 默认后台投递；滚动会短暂抢焦点 | 无焦点概念，Mac 上什么都不用置前 |
| 键盘 | 必须先聚焦输入框 | 同样必须先聚焦输入框 |
| 按键 | `return` / `tab` | 另有 `back`；组合键不支持 |
| 应用 | `open_app()` 走 Spotlight | `open_app()` 匹配包名，返回启动的那个 |
| 连接 | 镜像窗口 + 两个系统权限 | adb（USB / 无线）+ 手机侧授权 |
| 长时间任务 | 保持 Mac 不睡、手机不解锁 | `android awake --bg` / `android rest` |

所有助手名两边通用，只是个别能力单边缺失。

---

## 六、失败信号速查

| 你看到的 | 很可能是 |
|---|---|
| 手势发出去了，屏幕毫无变化 | 焦点被抢（自己发的原始事件 / `BACKGROUND=0` 路径），或该用 `scroll()` 却用了竖向 `swipe()` |
| `tap_text("X")` 抛错，错误里列出一堆别的文字 | 目标不在当前屏——先看错误里实际可见的内容，再决定滚动还是换屏 |
| 桌面上点标签没反应 | 桌面标签不是点击目标，图标在标签上方约 35 点，用 `tap_icon()` |
| `type_text` 后内容不见或跑错地方 | 输入框没聚焦；先 `tap()` 那个框，等键盘出现 |
| 文字被改写 | 逐键输入撞上了 iOS 自动更正；默认的粘贴路径就是为避开它，别随手加 `keystrokes=True` |
| 安卓读屏拿不到节点 | 该界面持续动画，`uiautomator` 等不到静止；改 `screenshot()` |
| 点击 / 读屏直接报锁屏 | 手机锁了。请用户解锁，Agent 不输 PIN |
| 列表滚到底却少了条目 | 提取器漏行导致提前停；先修提取器 |
