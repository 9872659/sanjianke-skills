---
name: sanjianke-umi-ocr
slug: sanjianke-umi-ocr
displayName: 三剪客 · 离线批量 OCR
description: "Umi-OCR：离线批量 OCR 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "Umi-OCR：离线批量 OCR 的安装、常用命令与避坑要点。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 文档转换
---

# 三剪客 · 离线批量 OCR

Umi-OCR 是一个解压即用的离线 OCR 桌面程序：批量拖入几百张图、扫描版 PDF 抽文本、生成双层可搜索 PDF、扫码和造码，全程不联网。

它对 Agent 的价值不在 GUI，而在**两个可编程入口**：一条 `umi-ocr` 命令行，和一套跑在 `127.0.0.1:1224` 的本地 HTTP 接口。搞清楚「命令是转发给正在运行的 GUI 进程」这件事，后面就顺了。

**上游项目**：`Umi-OCR`　**仓库**：https://github.com/hiroi-sora/Umi-OCR

## 什么时候用 / 不用

**用它**：

- 「把这一文件夹的截图 / 扫描件全转成文字」——批量图片 OCR 是它的主场。
- 「这份 PDF 是扫描的，帮我搜得到字」——输出双层可搜索 PDF 或纯文本。
- 环境不允许把文件传到云端，或者干脆没有外网——它离线跑。
- 「去掉水印 / 页眉页脚再识别」——内置忽略区域功能。
- 「图片里的二维码批量读出来」或「把一批文本生成二维码图片」。
- 要把 OCR 接进自己的脚本或服务——走本地 HTTP 接口，不依赖 Python 包。

**不要用它**：

- 运行环境是 macOS，或者非 x64 架构——官方发行版只有 Windows 7 x64 与 Linux x64。
- 需要**高并发**的在线服务——官方文档明确说后端组件并发支持较差，会报 `ECONNREFUSED`。
- 要的是「表格图片还原成 Excel」「数学公式转 LaTeX」「图片翻译」——这些都在作者的远期计划里，尚未提供。
- 需要轻量库形式嵌入（`import` 一下就用）——这是 GUI 程序，不是一个 pip 包。
- 纯文本 PDF（本身有文字层），只需要抽取而不需要 OCR——用普通的 PDF 文本抽取更省事。

## 安装

官方发布包是 `.7z` 压缩包或 `.7z.exe` 自解压包，**解压即用，无需安装**：解压后双击 `Umi-OCR.exe` 启动。Linux 用包内的 `umi-ocr.sh` 启动。

```bash
# 下载（三个官方长期维护渠道，任选其一）
#   GitHub Releases: https://github.com/hiroi-sora/Umi-OCR/releases/latest
#   SourceForge:     https://sourceforge.net/projects/umi-ocr
#   蓝奏云（国内推荐）: 见上游 README「下载发行版」一节

# Windows + Scoop（命令行安装）
scoop bucket add extras
scoop install extras/umi-ocr          # 自带 Rapid-OCR 引擎，兼容性好
# 或（不要和上一条同时装，快捷方式会被覆盖）
scoop install extras/umi-ocr-paddle   # 自带 Paddle-OCR 引擎，速度稍快

# Linux：使用包内启动脚本
./umi-ocr.sh
```

命令行入口就是主程序 `Umi-OCR.exe` 本身，没有独立的 CLI 发行包，也不需要额外的 Python 环境。

## 常用操作

前置：**Umi-OCR 主程序必须已在运行**，且全局设置里允许 HTTP 服务（默认开启，主机选「仅本地」即可）。命令行只是把你的指令通过本地环回 HTTP 转发给后台进程。

```bash
# 0) 看帮助 / 控制程序
umi-ocr --help
umi-ocr --show                 # 弹出主窗口
umi-ocr --hide                 # 隐藏主窗口
umi-ocr --quit                 # 关闭软件
umi-ocr --reload               # 重新加载 ./UmiOCR-data/.settings（v2.1.5+）

# 1) 截屏识别（鼠标划选）
umi-ocr --screenshot

# 2) 范围截屏（无需鼠标划选）：screen 从 0 开始；rect=x,y,w,h
umi-ocr --screenshot screen=0
umi-ocr --screenshot screen=1 rect=50,100,300,200

# 3) 识别指定图片 / 整个文件夹（会递归搜索子目录），可一次传多个路径
umi-ocr --path "D:/xxx.png"
umi-ocr --path "D:/img1.png" "D:/img2.png" "D:/image/test"

# 4) 识别剪贴板里的图片
umi-ocr --clipboard

# 5) 结果输出：剪贴板 / 覆盖写文件 / 追加写文件
umi-ocr --path "D:/xxx.png" --clip
umi-ocr --path "D:/xxx.png" --output "result.txt"
umi-ocr --path "D:/xxx.png" --output_append "result.txt"
umi-ocr --path "D:/xxx.png" "-->" result.txt        # --> 等价 --output
umi-ocr --path "D:/xxx.png" "-->>" result.txt       # -->> 等价 --output_append

# 6) 二维码：识别 / 生成（生成可指定宽高）
umi-ocr --qrcode_read "D:/xxx.png"
umi-ocr --qrcode_create "要写入的文本" "D:/out.jpeg"
umi-ocr --qrcode_create "要写入的文本" "D:/out.jpeg" 128 256

# 7) 指令支持前几个字母简写，例如 --sc 等价 --screenshot
umi-ocr --sc
```

HTTP 接口（默认端口 `1224`，可在全局设置里改）：图片识别一个请求就够。

```python
import base64, json, requests

# 图片 OCR：POST /api/ocr，base64 不带 data:image/... 前缀
with open("page.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

res = requests.post("http://127.0.0.1:1224/api/ocr", json={
    "base64": b64,
    "options": {
        "data.format": "text",           # 只要纯文本；dict 则带位置与置信度
        "tbpu.parser": "multi_para",     # 排版解析：多栏-按自然段换行
        "ocr.limit_side_len": 4320,      # 大图/长图调高边长上限
    },
}).json()
print(res["code"], res["data"])          # code 100 成功，101 无文本，其余为失败
```

扫描 PDF 走 5 步流程（上传 → 轮询 → 生成 → 下载 → 清理），完整端点与参数见 `references/http-api.md`。

## 常见坑

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 命令行报错 / 完全没反应 | 命令行依赖 HTTP 服务通信，服务被关闭或主机设置不允许访问 | 全局设置页允许 HTTP 服务（默认开启），主机选「仅本地」；确认端口没被改过 |
| 找不到 `umi-ocr` 这个命令 | 命令行入口就是主程序 `Umi-OCR.exe`，靠系统把 `Umi-OCR.exe` 关联成小写名 | 直接用完整路径调用 `Umi-OCR.exe`；用备用启动器 `UmiOCR-data/RUN_GUI.bat` 时命令行不可用 |
| 先跑命令再开程序，任务丢失 | 命令是跨进程转发给后台 GUI 进程的 | 先启动 Umi-OCR 主程序，再执行命令行任务 |
| 用 `>` 或管道拿不到输出 | 官方明确说明暂时无法重定向输出流 | 用 `--output` / `-->` 写文件；程序化调用改用 HTTP 转发命令行 |
| 长图 / 大图识别缺字、精度差 | 默认「限制图像边长」为 960，大图被压缩 | 页面设置里调高该值；HTTP 传 `ocr.limit_side_len`（可选 960 / 2880 / 4320 / 999999） |
| 水印、页眉页脚混进结果 | 没有配置忽略区域 | 批量 OCR 页用忽略区域编辑器画框；HTTP 传 `tbpu.ignoreArea`。注意只忽略**完全落在框内的整个文本块**，框要画大 |
| 并发调用出现 `ECONNREFUSED` 或结果错乱 | 后端组件并发支持差，官方建议不要并发 | 串行调用，失败就重发一次；不要开线程池 / 并发队列打接口 |
| 关掉软件后进程还在 | 仍有 HTTP 连接未断开，网络子线程不退出 | 先断开所有调用方连接再关软件；实在不行进任务管理器结束进程 |
| 返回的 JSON 解析失败 | 某些 http 库把返回值里的转义换行 `\n` 还原成了真实换行 | 先把真实换行替换回 `\\n` 再交给 JSON 解析；非英文字符是 `\uXXXX`，正常解析即可 |
| 高级指令传路径报参数错误 | Windows 解析命令行参数的规则限制 | 路径里 `\` 改成 `/`；PowerShell 里最外层用单引号且左双引号前留空格，终端里最外层用双引号 |
| Scoop 装完快捷方式不对 | `umi-ocr` 与 `umi-ocr-paddle` 同时装会互相覆盖 | 只装一个，想换引擎就装插件切换 |
| 一次 `--path` 传了文件夹后卡很久 | 文件夹会被递归搜索，所有图片都要识别 | 多图任务耗时本来就长，**一次命令结束前不要发下一条指令** |

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 仅本地 | 命令行与 HTTP 接口走 `127.0.0.1` 本地环回，不经物理网卡；只有主动把主机改成「任何可用地址」才会暴露到局域网。OCR 本身不联网 |
| 读取文件 | 是 | 读取待识别的图片、PDF / epub 等文档、二维码图片 |
| 写入文件 | 是 | 写识别结果（txt / jsonl / md / csv）、双层可搜索 PDF、下载链接产物、生成的二维码图片 |
| 凭证 | 否 | 不需要账号、Key 或登录 |
| 子进程 / 后台常驻 | 是 | GUI 主程序必须常驻；命令行与 HTTP 请求都转发给它。任务结束应关闭程序释放资源 |

## 触发场景

- 「把这个文件夹的截图全部 OCR 成 txt。」
- 「这份扫描版 PDF 帮我转成能搜到字的 PDF。」
- 「识别结果里老是带上水印文字，怎么去掉？」
- 「把图片里的二维码内容批量读出来。」
- 「我要在自己的 Python 脚本里调 OCR，不想装 paddle。」
- 「公司内网不能传文件到云端，有没有离线的识别方案？」

## 能力边界

**覆盖**：

- 截图 OCR（鼠标划选、指定屏幕与区域）、剪贴板图片识别。
- 批量图片 OCR，支持 `jpg / jpe / jpeg / jfif / png / webp / bmp / tif / tiff`，输出 `txt / jsonl / md / csv`，数量无上限。
- 排版解析（多栏 / 单栏、按自然段换行 / 总是换行 / 无换行 / 保留缩进 / 不处理），自动处理横排与竖排顺序。
- 忽略区域，排除水印、LOGO、页眉页脚。
- 文档识别：`pdf / xps / epub / mobi / fb2 / cbz`，输出双层可搜索 PDF、纯文本等。
- 二维码：识别（一图多码，19 种协议）与生成（可指定格式、宽高、纠错等级）。
- 可编程入口：`umi-ocr` 命令行、本地 HTTP 接口（图片 / 文档 / 二维码 / 命令行转发）、以及可调用任意模块函数的高级指令。
- 可切换 OCR 引擎插件（PaddleOCR-json / RapidOCR-json）。

**不覆盖**：

- 不做表格结构还原（识别表格输出 Excel 仍在远期计划）。
- 不做独立数学公式识别 / LaTeX 渲染。
- 不做图片翻译、离线翻译。
- 不做手写体专项优化，也没有云端大模型兜底。
- 不提供 macOS 或非 x64 架构的官方发行包。
- 不是库：不能被 `import` 进 Python 项目，也不是 pip 包。

## 依赖条件

- 平台：**Windows 7 x64** 或 **Linux x64**（官方发行版口径）。
- 解压即用，无需安装 Python；自带运行库（Windows / Linux 运行库在独立仓库）。
- 命令行与 HTTP 调用的前提：主程序在运行，且全局设置中 HTTP 服务已开启（默认开启）。
- 默认端口 `1224`，可在全局设置中修改。
- 文档识别功能需要 `v2.1.4` 及以上版本；`--reload` 需要 `v2.1.5` 及以上。
- 不需要账号或 Key。

## 已知限制

- 后端组件并发支持差，不适合做成高并发服务；官方建议不要并发调用。
- 长时间、大批量连续调用有小概率出现 `Error: connect ECONNREFUSED` 之类 HTTP 报错，重发请求即可。
- 命令行无法重定向输出流，`>` 与 `|` 可能失效。
- 任务默认 24 小时后自动清理；软件被意外关闭时，重启会清理上次遗留的所有任务。
- 多数 `ocr.*` 参数（如 `ocr.language`、`ocr.cls`、`ocr.limit_side_len`）只对 PaddleOCR 插件生效，换引擎必须自己调 `get_options` 确认参数规则。
- 忽略区域按「整个文本块」生效，不是字符级裁剪。

## 自检清单

执行前：

- [ ] Umi-OCR 主程序已启动，全局设置里 HTTP 服务已开启（主机建议「仅本地」）。
- [ ] 确认实际端口（默认 `1224`）与调用方一致。
- [ ] 待处理文件的格式在支持列表内（图片或 pdf / xps / epub / mobi / fb2 / cbz）。
- [ ] 大图 / 长图先确认「限制图像边长」够不够大。
- [ ] 有水印或页眉页脚的批量任务，先配置忽略区域。

执行后：

- [ ] 检查返回 `code`：`100` 成功、`101` 无文本、其余按错误处理。
- [ ] 抽查识别文本，确认中文没有乱码、排版顺序正确。
- [ ] 输出文件确实生成（用 `--output` 而不是 `>`）。
- [ ] HTTP 文档任务完成后调用 `/api/doc/clear/<id>` 释放临时文件。
- [ ] 不需要时关闭主程序，避免残留连接导致进程不退出。

## 参考文件

| 文件 | 用途 |
|---|---|
| `README.md` | 包说明 |
| `references/http-api.md` | HTTP 接口速查：图片 OCR、文档识别 5 步流程、二维码识别与生成 |
| https://github.com/hiroi-sora/Umi-OCR | 上游仓库（安装与完整文档以它为准） |

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
