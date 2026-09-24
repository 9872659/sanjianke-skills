# 三剪客 · PDF 页面整理 Skill

用鼠标合并、拆分、拖拽排序、旋转、裁剪 PDF 页面的 GTK 桌面程序。**它是图形界面工具，没有命令行选项，不适合 Agent 无人值守调用。**

---

## 前置条件

- **必须有图形界面与显示服务（X 或 Wayland）**，并且有人在屏幕前操作。无头服务器、CI、容器里无法使用
- 从源码安装时要求 **pikepdf >= 6**；涉及「保留书签与链接」的偏好项需要 pikepdf >= 8.0
- 需要 Python 3、PyGObject、GTK 3、poppler-glib、libhandy 等系统库
- 图片导入功能需额外安装 `img2pdf`（透明图片需 >= 0.4.2）
- 不需要账号、Key 或在线服务

---

## 使用

它是图形程序，命令行部分只有「启动时把文件路径传进去」这一件事：

```bash
pdfarranger report.pdf              # 打开一个 PDF 进入界面
pdfarranger a.pdf b.pdf c.pdf       # 启动时就带上多个文件
```

界面里的高频操作：

- 合并：`Open`（新实例打开）/ `Import`（追加到当前实例）/ 从文件管理器拖拽
- 重排：拖拽排序、复制粘贴、颠倒顺序、交换奇数/偶数页
- 页面级：旋转（90 度步进）、删除、复制、插入空白页、拆页、合页
- 版面：自动裁白边、手工裁边距、隐藏边距、按百分比或毫米改页尺寸
- 导出：保存全部为一个 PDF；或只导出选中页为一个或多个 PDF；也可导出 png / jpeg / 栅格化 PDF

`SKILL.md` 里有各平台安装命令、完整界面功能说明，以及书签链接丢失条件等避坑要点。

**Agent 场景请改用命令行方案**（本工具无法脚本化）：

```bash
pdfunite a.pdf b.pdf out.pdf        # 合并（poppler）
qpdf --pages a.pdf 1-5 -- out.pdf   # 取页、重排
pdfseparate a.pdf page-%d.pdf       # 拆分（poppler）
```

Python 里可直接用 `pikepdf` 编程——PDF Arranger 本身就是它的前端。

---

## 依赖

- 图形环境：GTK 3 + X / Wayland 显示服务（**必需**）
- 系统库：PyGObject、GTK 3、poppler-glib、libhandy、gettext 等
- Python 库：`pikepdf >= 6`（保留文档信息功能需 >= 8.0）、dateutil
- 可选：`img2pdf`（图片导入，透明图需 >= 0.4.2）
- 从源码装进虚拟环境必须带 `--system-site-packages`，否则看不到系统的 GTK 绑定

---

## 安全

- 不内嵌任何密钥
- 全程本地处理，不上传任何文档
- 整理是只读源文件 + 另存新文件的模式，但仍建议操作前留备份
- 部分操作（改页尺寸、小册子、合并页面、隐藏边距、叠加粘贴）会丢失书签与内部链接，重要文档操作前先确认
- 导出会自动在文件名末尾加自增数字，注意目标目录不要混入旧结果
- 本包不建议、也不支持在无人值守环境中自动调用本工具

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`pdfarranger`
- 仓库：https://github.com/pdfarranger/pdfarranger

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
