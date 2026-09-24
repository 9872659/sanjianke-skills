# 三剪客 · 老牌 OCR 引擎 Skill

把图片、扫描件里的印刷文字变成可复制、可搜索、可继续处理的文本；需要时直接产出带隐形文字层的可搜索 PDF，以及带词级坐标与置信度的 TSV / hOCR。

---

## 前置条件

- **输入必须是图片**。tesseract 只接受 Leptonica 能打开的图片格式（PNG / JPEG / TIFF / BMP 等），**不读 PDF / DOCX 等文档格式**。PDF 要先栅格化：`pdftoppm -r 300 -png input.pdf page`。
- 引擎和语言数据**分开安装**，装完引擎默认只有英文 `eng` 和方向检测 `osd`。简体中文是 `chi_sim`（不是 `chs`、不是 `zh`）。
- 装完先跑 `tesseract --list-langs` 确认语言可用，再开始处理数据。
- 全程**离线运行**：不需要账号、不需要 API Key、不产生费用，也不会上传任何图片。
- 图片质量决定精度上限：建议 ≥300 DPI、深字浅底、有适当白边、不倾斜。低于这个标准请先做图像预处理。

---

## 使用

最短路径：

```bash
# 1. 装引擎（三选一）
sudo apt install tesseract-ocr libtesseract-dev      # Ubuntu / Debian
brew install tesseract                               # macOS
winget search tesseract                              # Windows：查到包 ID 再装，并把安装目录加进 PATH

# 2. 装语言数据（示例：简体中文）
sudo apt install tesseract-ocr-chi-sim               # Linux
# Windows：把 chi_sim.traineddata 放进安装目录下的 tessdata

# 3. 自检
tesseract --version
tesseract --list-langs

# 4. 识别
tesseract scan.png out -l chi_sim+eng
tesseract scan.png out -l chi_sim+eng pdf            # 顺带出一份可搜索 PDF
tesseract scan.png out -l eng tsv                    # 每词一行，带坐标与置信度
```

几个高频变体：

```bash
# 结果直接打到终端
tesseract scan.png - -l eng

# 版面不是「一整页文字」时先换 PSM（7=单行，8=单词，6=均匀文本块，11=稀疏文字）
tesseract line.png out -l eng --psm 7

# 只认数字
tesseract num.png out -l eng -c tessedit_char_whitelist=0123456789

# 批量：清单文件 + 合并输出；批量时把线程压到 1
printf '%s\n' pages/*.png > list.txt
OMP_THREAD_LIMIT=1 tesseract list.txt combined -l chi_sim+eng pdf txt

# PDF 输入先栅格化
pdftoppm -r 300 -png input.pdf page
```

完整说明（13 种 PSM 取值、各输出格式的字段含义、批量与调参、常见坑全表）见 `SKILL.md`。

---

## 依赖

| 项 | 说明 |
|---|---|
| 主版本 | Tesseract 5.x（5.0.0 发布于 2021-11-30）；参数与 config 行为随版本变化，以实际版本为准 |
| 运行库 | Leptonica（读图必需，建议带 zlib / libpng / libtiff） |
| 语言数据 | `.traineddata` 放在 `tessdata` 目录，或用 `--tessdata-dir` / `TESSDATA_PREFIX` 指定（环境变量要指向 `tessdata` 的父目录） |
| 数据仓库选择 | `tessdata_fast` 快、只支持 LSTM；`tessdata_best` 慢而准、训练用它、只支持 LSTM；`tessdata` 同时支持 LSTM 与 legacy（`--oem 0`） |
| 平台 | Linux / macOS / Windows，另有 MSYS2、Cygwin、snap、AppImage 等安装方式 |
| 账号 / Key | 不需要；无费用 |
| CPU | 多线程版默认占 4 核，批量处理时建议 `OMP_THREAD_LIMIT=1` |

---

## 安全

- 不内嵌任何密钥。该工具本身不需要凭证。
- **完全离线**：识别过程不出网、不上传图片。处理合同、证件、病历等敏感材料时，请一并检查套在它外面的脚本有没有把结果发往别处。
- 中间产物会落盘：`get.images` config 会写出 `*.processed*.tif`，`logfile` config 会写 `tesseract.log`，调试参数也可另写文件。敏感场景记得清理。
- 输入支持 `stdin`/`-`、输出支持 `stdout`/`-`，可用管道避免中间文件落盘。
- 该工具做的是 OCR 转录，**不构成任何形式的合规审查或数据脱敏**；识别结果里可能仍含个人信息，落库前请自行处理。

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`tesseract`
- 仓库：https://github.com/tesseract-ocr/tesseract

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
