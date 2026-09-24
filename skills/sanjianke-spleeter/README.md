# 三剪客 · 人声伴奏分离 Skill

Spleeter：把人声、伴奏、鼓、贝斯、钢琴拆成独立音轨的本地命令行工具，含安装、真实命令与避坑要点。

---

## 前置条件

- Python 3.8 ～ 3.11（含），推荐 `3.9` 或 `3.10`；3.12 及以上无法直接安装依赖
- 系统已装 `ffmpeg` 与 `libsndfile`（Conda 一条命令：`conda install -c conda-forge ffmpeg libsndfile`）
- 建议新建独立虚拟环境，不要装进主力环境
- 磁盘留出空间：预训练模型权重会下载到本地缓存，首次运行需要联网
- 不需要账号、Key 或登录

---

## 使用

本 Skill 面向「一条命令把人声拆出来」这类需求，主要走命令行：

```bash
spleeter separate -p spleeter:2stems -o output 你的音频.mp3
```

结果在 `output/<文件名>/` 下，得到 `vocals.wav` 与 `accompaniment.wav`。四轨 / 五轨把 `-p` 换成 `spleeter:4stems` 或 `spleeter:5stems`。

需要嵌进自己的程序时，可以用同名的 Python 库入口：

```python
from spleeter.separator import Separator
Separator("spleeter:2stems").separate_to_file("你的音频.mp3", "output")
```

完整的参数说明、档位选择、批量处理写法和排查表都在 `SKILL.md` 里。

---

## 依赖

- 运行时：Python `>=3.8,<3.12`
- Python 包（由上游声明）：`tensorflow==2.12.1`、`numpy<2.0.0`、`ffmpeg-python`、`typer`、`pandas`、`norbert`、`httpx[http2]`、`tensorflow-io-gcs-filesystem==0.32.0`
- 系统命令：`ffmpeg`；音频读写还需要 `libsndfile`
- 可选：`pip install spleeter[evaluation]` 拉入 `musdb` 与 `museval`，仅在跑自训练模型的评估时需要
- 其他安装方式：官方 Docker 镜像，或按仓库 README 用 Poetry 从源码装

---

## 安全

- 不内嵌任何密钥
- 全程本地推理，素材不会上传到任何第三方服务；仅在首次运行时联网下载预训练权重
- 需要读入原始音频并写出分离结果文件，请自行确认读写目录范围
- 内部会调用 `ffmpeg` 解码，并默认起多进程池并行写盘
- 对受版权保护的素材，使用前请自行取得权利人授权；上游明确声明不对非法用途负责

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`Spleeter`
- 仓库：https://github.com/deezer/spleeter

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
