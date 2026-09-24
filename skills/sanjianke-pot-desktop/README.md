# 三剪客 · 跨平台划词翻译与截图 OCR Skill

把划词翻译、截图 OCR、截图翻译和多引擎对比收进一个常驻托盘的桌面工具，并开放本地 HTTP 接口给其他程序调用。

---

## 前置条件

- Windows 10/11、macOS 或主流 Linux 发行版桌面环境（含 Wayland，需要按 `SKILL.md` 做替代配置）
- Windows 需要 WebView2 运行时；缺失时改用 Release 页内置该运行时的安装包
- macOS 需要授予辅助功能权限，并先处理应用的隔离属性
- 要用在线引擎的话，先准备好对应平台的账号与 Key（百度、腾讯、火山、DeepL、OpenAI 等各不相同）
- 要让别的程序调用它的话，确认本机 `60828`（默认端口，可改）未被占用
- 从源码构建另需：Node.js >= 18.0.0、pnpm >= 8.5.0、Rust >= 1.80.0

---

## 使用

**安装**（按平台挑一条）：

```powershell
winget install Pylogmon.pot
```

```bash
brew tap pot-app/homebrew-tap && brew install --cask pot          # macOS
sudo apt-get install ./pot_{version}_amd64.deb                    # Debian/Ubuntu
yay -S pot-translation                                            # Arch AUR
```

**日常交互**：划词翻译（选中后按快捷键）、输入翻译（快捷键唤起后输入回车）、剪切板监听（在翻译面板点左上角图标开启）、截图 OCR / 截图翻译（快捷键后框选区域）。

**外部调用**：pot 监听 `127.0.0.1`，默认端口 `60828`。

```bash
curl "127.0.0.1:60828/selection_translate"     # 触发划词翻译
curl "127.0.0.1:60828/input_translate"         # 触发输入翻译
curl "127.0.0.1:60828/ocr_recognize"           # 触发截图 OCR
curl "127.0.0.1:60828/ocr_translate"           # 触发截图翻译
```

**不用软件内截图**：先用别的工具把图存到 `$CACHE/com.pot-app.desktop/pot_screenshot_cut.png`，再带 `screenshot=false` 调用：

```bash
curl "127.0.0.1:60828/ocr_recognize?screenshot=false"
```

**插件**：下载 `.potext` 文件，在「偏好设置 → 服务设置 → 添加外部插件 → 安装外部插件」中安装，之后如内置引擎一样选用。

完整步骤、Wayland 配置与故障表见 `SKILL.md`。

---

## 依赖

- 上游产品本体（Tauri 桌面应用，托盘常驻）
- Windows：WebView2 运行时；插件另需 VC++ 可再发行组件包
- macOS：辅助功能与屏幕录制权限；首次打开需处理隔离属性
- Linux：GTK / WebKit2Gtk / 托盘指示器 / librsvg 等系统库（源码构建时由官方命令一次性补齐）
- 在线引擎：各自平台的 AppID / Key
- 离线引擎：系统自带 OCR 可用，或本机已部署 Ollama
- 本机端口 `60828`（可改）用于对外提供 HTTP 接口

---

## 安全

- 不内嵌任何密钥：各引擎的 Key 由使用者在本机设置中填写，本包不含任何凭证
- 多引擎并行意味着同一次查询会把文本同时发往多个第三方服务，隐私面比单引擎工具更大，涉密内容请先脱敏
- 本地 HTTP 接口默认不带鉴权，虽然只监听本机，仍应确认端口不被其它本地程序滥用；不需要外部调用时不必让它保持暴露
- 需要辅助功能与剪贴板权限才能划词与监听复制，这是功能必需，不是可选项
- 第三方 `.potext` 插件是可执行能力的扩展，装之前确认来源可信
- 插件缺失 VC++ 运行库或架构不匹配会直接报错，装插件时按平台与架构选对版本

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pot-desktop`
- 仓库：https://github.com/pot-app/pot-desktop

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
