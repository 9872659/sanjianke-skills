# 三剪客 · Python 视频剪辑库 Skill

MoviePy：Python 视频剪辑库 的安装、常用命令与避坑要点

---

## 前置条件

- Python 3.9+（上游 `pyproject.toml` 中为 `requires-python=">=3.9"`，README 与 PyPI 表述一致）
- 装的是 **2.x** 版本：v2 与 v1 的 API 不兼容，代码必须与版本对应；v1 已不再维护
- ffmpeg 用于视频读写，通常由 imageio 首次使用时自动下载；若要完全离线或指定路径，预先装好并设 `FFMPEG_BINARY`
- 只有需要 `preview()` 预览播放时才需要 ffplay（通过 `FFPLAY_BINARY` 指定）
- 需要写字的场景准备一个 OpenType 字体文件（`.ttf` / `.otf`），v2 的 `TextClip` 要的是字体文件路径
- 服务器环境注意：预览不可用，只能导出；长任务用后台方式跑

---

## 使用

这个 Skill 教 Agent 做四件事：

1. **判断该不该用**——纯转码/切一刀请直接用 ffmpeg；需要流式或逐帧算法（如视频稳定）也不用它
2. **装对并写对版本**——确认装的是 2.x，导入路径用 `from moviepy import ...`，方法名用 `subclipped` / `resized` / `cropped` / `rotated`
3. **跑通最小流程**——读入 → 切/拼/合成 → `write_videofile` 导出，并掌握 `fps` / `codec` / `bitrate` / `preset` / `threads` / `ffmpeg_params` 几个关键参数
4. **避开典型报错**——没有时长的 clip 写不出去、奇数分辨率兼容性差、v1 示例照抄必崩、Windows 下句柄不释放

典型请求：

- "这批视频统一加片头片尾，写个脚本批量跑"
- "把一组图片合成视频"
- "视频上加标题和角标"
- "做个画中画 / 四宫格"
- "把音频单独抽出来"
- "我就想转个格式，为什么这么慢？"

具体示例见 `SKILL.md` 的「安装」「常用操作」「常见坑」三节。所有命令、参数名与版本信息取自上游 README、官方文档站与 PyPI 页面；不同版本可能调整，执行前请对照官方文档。

---

## 依赖

- `moviepy`（本体，PyPI 可装，当前 2.x 主线）
- `pillow`（v2 起承担图像处理）
- 外部件：**ffmpeg**（视频读写必需，通常由 imageio 自动获取）、**ffplay**（仅预览需要）
- 可选 extras：`doc`（构建文档）、`test`、`lint`
- 容器：官方文档站提供 Docker 使用方式，镜像与标签以官方文档为准
- 账号 / Key：不需要，纯本地库
- 硬件：CPU 即可，无 GPU 强依赖；耗时可观，与分辨率、时长、合成层数成正比

---

## 安全

- 不内嵌任何密钥：本 Skill 只记录命令与参数，工具本身不需要账号或 Key
- 首次使用若未装 ffmpeg，会由 imageio 联网下载二进制；对网络受限或需要审计的环境，请预先自行安装 ffmpeg 并用 `FFMPEG_BINARY` 指定路径
- 会起子进程调用 ffmpeg，并写入临时音频文件；在共享机器上注意临时目录与并发任务互不干扰
- 渲染任务 CPU 与内存占用较高，长批量任务建议后台执行并限制并发，避免把机器拖死
- 输入素材与输出成片可能含未公开内容，注意目录权限与清理中间产物

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`MoviePy`
- 仓库：https://github.com/Zulko/moviepy

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
