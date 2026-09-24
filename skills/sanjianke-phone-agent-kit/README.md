# 三剪客 · 手机自动化控制 Skill

让 AI Agent 直接看屏、点击、输入，操作你的真手机

---

## 前置条件

- **Python 3.10+**，以及可执行的 `phone-harness` 命令。
- **iPhone 路线**：macOS Sequoia 及以上，已在「iPhone 镜像」App 里完成手机配对（需要实体手机操作）；终端获得**辅助功能**与**屏幕录制**两个权限，屏幕录制要重启终端才生效。
- **安卓路线**：adb（`android-platform-tools`，可选 scrcpy 看实时镜像）；手机已开 USB 调试并授权，或已开无线调试并完成配对。
- **一台同意被操作的手机**。连接、解锁、点「允许」都由用户亲手完成，Agent 不代做、不代输 PIN。

---

## 使用

最省的路径是四步：

1. **体检**：`phone-harness --doctor`（或 `--doctor ios` / `--doctor android`）走完整条依赖链，务必先让它全绿。
2. **选默认手机**：`phone-harness config set platform ios|android`；单次覆盖用 `PHONE_HARNESS_PLATFORM=android`。
3. **只读验证**：先跑一次 `print([o["text"] for o in ocr()][:10])`，确认看得见屏幕。
4. **再放开写操作**：点击、输入之后一定回读屏幕确认——这里没有「操作成功」的返回值。

```bash
phone-harness <<'PY'
# task: 打开备忘录并写入一行文字
# step: 打开、新建、输入、回读确认
open_app("Notes")
wait_stable()
tap_text("新建")
type_text("hello from the harness")
print([o["text"] for o in ocr()][:10])
PY
```

完整内容看 `SKILL.md`，三份 references 分别覆盖环境搭建与连接、操作能力与调用示例、稳定性与安全边界。

---

## 依赖

- **上游程序**：`phone-harness`（MIT，当前 0.2.0），`pip install -e .` 从 checkout 安装；iPhone 侧会带上 pyobjc 的 Quartz / Vision / Cocoa / ApplicationServices。
- **系统工具**：iPhone 路线依赖 macOS 自带的「iPhone 镜像」；安卓路线依赖 adb。
- **可选**：scrcpy（长任务时开实时镜像窗口）。
- **网络**：不需要访问公网。上游默认开启匿名使用统计，`phone-harness config set telemetry false` 可关闭。
- 本 Skill 自身不依赖任何第三方库，也不发起网络请求。

---

## 安全

- 不内嵌任何密钥，不含 Token / Cookie，不代理转发请求。
- **控制手机是高权限能力**：它会读取屏幕内容（截屏 + OCR / 无障碍树，看到什么就带进模型上下文），并模拟真实输入（点击、滑动、输入），动作等同于用户本人操作。
- **可能造成真实后果**：误发消息、误下单、误删数据、误改设置。对外发送、下单、删除、改设置前必须先经用户确认。
- **永远不输 PIN、不代解锁**；连接与配对不同由 Agent 代做，连接失败时停下转述，不点 `Connect`、不轮询重试。
- 只操作自有或已获明确授权的设备；敏感界面（支付、私密聊天、验证码）尽量不进入被读取的流程。
- 安卓长任务结束记得 `phone-harness android rest`，不要让手机一直常亮。
- 落盘的截图请及时清理。

---

## 版权

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

上游项目：phone-harness（MIT）

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
