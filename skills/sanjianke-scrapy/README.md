# 三剪客 · Python 网页抓取框架 Skill

scrapy：Python 网页抓取框架 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.10 或以上（CPython 或 PyPy）
- 一个独立虚拟环境（官方明确不建议装到系统环境里）
- Windows 走 pip 时需先装 Microsoft C++ Build Tools（含 MSVC 与 Windows SDK）；官方更推荐 conda-forge 渠道
- Ubuntu / Debian 需先装 `python3-dev`、`libxml2-dev`、`libxslt1-dev`、`zlib1g-dev`、`libffi-dev`、`libssl-dev`
- macOS 需 `xcode-select --install` 装好命令行工具，并建议用 homebrew 装新 Python
- 抓取前确认目标站点的 robots.txt 与使用条款允许抓取

---

## 使用

1. 建环境：`python -m venv venv` 激活后 `pip install Scrapy`；Windows 也可以 `conda install -c conda-forge scrapy`。
2. 建项目：`scrapy startproject myproject`，进入目录后即可使用项目内命令。
3. 生成爬虫：`scrapy genspider example example.com`，或按官方示例直接手写一个继承 `scrapy.Spider` 的类。
4. 写解析逻辑：用 `response.css` / `response.xpath` 提字段，`response.follow` 翻页；不确定表达式就先进 `scrapy shell` 试。
5. 运行：项目内 `scrapy crawl <name>`，或脱离项目 `scrapy runspider <文件>`；用 `-O` 覆盖导出、`-o` 追加导出。
6. 验证与调试：`scrapy check` 跑契约、`scrapy list` 列出爬虫、`scrapy fetch --headers` 看实际请求、`scrapy parse -c <回调>` 单测某个回调。
7. 各命令的完整选项以 `scrapy <command> -h` 与官方命令行文档为准。

---

## 依赖

- 核心 Python 依赖：lxml（XML/HTML 解析）、parsel（基于 lxml 的提取库）、w3lib（URL 与编码处理）、Twisted（异步网络框架）、cryptography 与 pyOpenSSL（网络层安全）
- 其中 lxml 与 cryptography 本身依赖非 Python 组件，各平台需按官方说明预装
- 可选 extras：`bpython`、`color`、`gcs`、`httpx`、`images`、`ipython`、`ptpython`、`robotparser`、`s3`、`twisted-http2`、`uvloop`
- 图片与媒体下载、S3/GCS 导出等功能需要对应 extras
- 长期运行部署通常还需额外的调度与监控组件

---

## 安全

- 不内嵌任何密钥
- 抓取目标站点的登录凭证、S3/GCS 等云端存储密钥放在环境变量或本地配置里，不要提交进版本库
- 抓取前确认已获授权并符合目标站点的 robots.txt 与使用条款；工具本身不改变抓取的合规性
- 配置合理的下载延迟与单域名并发上限，或启用自动限速，避免对目标站点造成压力
- 抓取到的内容可能包含个人信息与受版权保护的材料，二次使用前需自行做合规评估
- 注意 SSRF 风险：不要把不可信的外部输入直接拼成被抓取的 URL
- 结果文件与日志里可能落有敏感字段，输出目录与日志的访问权限要控制好

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`scrapy`
- 仓库：https://github.com/scrapy/scrapy

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
