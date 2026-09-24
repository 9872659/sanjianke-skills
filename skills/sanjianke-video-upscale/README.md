# 三剪客 · 视频超分（糊片救 4K）

把拍糊的、被平台压花的老素材提升到 1080p / 2K / 4K。

**这个包最重要的部分不是"怎么超分"，而是"先判断该不该超分、该走哪条路"。** 选错了要么白花钱，要么白等。

---

## ⚠️ 用之前先拿 Key

**不填 Key 跑不起来。** 必须有一个 [api.a7w.cn](https://api.a7w.cn/) 的 API Key。

**第一步 · 注册**：到 https://api.a7w.cn/ 注册 → 控制台创建 Key（形如 `sk-xxx...`）→ 完整复制保存。

**第二步 · 填进你在用的地方**：

| 你在哪用 | 怎么填 |
|---|---|
| **AI 工具 / Agent 平台**（Kimi、扣子等） | 平台的**环境变量 / 凭证 / 插件配置**里加 `A7W_API_KEY=sk-你的key` |
| **本机命令行** | `export A7W_API_KEY=sk-你的key`（Windows 用 `$env:A7W_API_KEY="..."`） |
| **跑一次** | 命令加 `--key sk-你的key` |
| **长期本机** | `python3 scripts/a7w.py login --key sk-你的key` |

读取顺序：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。不填会有明确报错，不会静默失败。

---

---

## 效果实拍

**原片 854×480 → 超分 3840×2160**，同一条片、同一秒、同一区域，从源片和 4K 成片各裁一块 1:1 对比：

![原片 vs 4K 清晰度对比](https://vr.a7w.cn/demo/moments/compare-before-after.png)

差距集中在两个地方：

- **面部特写**：原片睫毛糊成一片、瞳仁发灰、牙齿粘连 → 超分后睫毛根根分离、瞳仁有高光、齿缝清楚
- **珠饰与缎面**：原片金纹消失、花瓣糊成一坨 → 超分后纹理清晰、层次分明

**对比视频**（逐帧对照，看动态下是否稳定）：

https://vr.a7w.cn/demo/moments/compare-before-after.mp4

### 「超分」和「放大」不是一回事

放大只是让马赛克跟着一起变大；超分是**逐帧推断并重建细节**，把丢掉的像素补回来。

![超分不是放大，是重画](https://vr.a7w.cn/demo/moments/moments-01.png)

> 这套科普图共 10 张，同目录下 `moments-01.png` ~ `moments-10.png`，逐条讲清楚超分能做什么、不能做什么。
>
> 合并版对比视频：`https://vr.a7w.cn/demo/moments/moments-merged.mp4`

---

## 内容

```
sanjianke-video-upscale/
├── SKILL.md                          主入口：判断标准、三条路线、计费限制、常见坑
├── README.md                         本文件
├── LICENSE.md                        MIT
├── references/
│   ├── routes-and-engines.md         三条路线详解 + 引擎差异 + 选型决策树
│   ├── api-flashvsr.md               api.a7w.cn 的 flashvsr 接口文档
│   ├── local-ffmpeg.md               本地 ffmpeg 参数详解 + 批量转档工程要点
│   └── 通用说明.md                    权限表、异步任务机制、错误码、计费口径
└── scripts/
    ├── a7w.py                        通用零依赖客户端（只用 Python 标准库）
    └── run.py                        超分执行器：--route api / --route local
```

---

## 三条路线

| 你的情况 | 走哪条 | 成本 |
|---|---|---|
| 就几条片子，最快看到结果 | **在线站** [vr.a7w.cn](https://vr.a7w.cn/) | 0.3 元/秒 |
| 几十上百条，要接进自己流程 | **`api.a7w.cn`** 的 `flashvsr` | 按平台计费 |
| 素材敏感不能出网 / 想零成本 | **本地 ffmpeg** | 零 |

---

## 快速开始

### 路线一：在线站

打开 https://vr.a7w.cn/ ，拖视频进去（可多选），点「全部开始超分」。

**限制**：MP4/MOV/WebM，单个 ≤200MB，**时长 ≤30 秒**，输出 4K。

### 路线二：走 api.a7w.cn

```bash
# 1. 配置你自己的 API Key（只需一次）
python3 scripts/a7w.py login --key sk-你的key

# 2. 提交并自动轮询到结束
python3 scripts/run.py --route api --url https://example.com/lowres.mp4

# 3. 想直接存到本地
python3 scripts/run.py --route api --url https://example.com/lowres.mp4 --out out.mp4
```

> `--url` **必须是公网可访问的地址**，不支持本地文件路径。

### 路线三：本地 ffmpeg

```bash
# 先看视频信息（分辨率、时长、体积）
python3 scripts/run.py --probe input.mp4

# 温和增强，放大到 1080p
python3 scripts/run.py --route local input.mp4 --height 1080

# 强力模式，放大到 1920
python3 scripts/run.py --route local input.mp4 --level 2 --height 1920

# 批量
python3 scripts/run.py --route local *.mp4 --out ./done
```

需要本机有 `ffmpeg` 和 `ffprobe`：

| 系统 | 命令 |
|---|---|
| Windows | `winget install Gyan.FFmpeg` |
| macOS | `brew install ffmpeg` |
| Linux | `sudo apt install ffmpeg` |

---

## 先做这一步判断

**把原片截图放大到 200%**：

- 还能看到**结构和边缘**（哪怕带着方块）→ 细节还在，**值得超分**
- 放大后是**一片平滑色块** → 细节已经没了，超分只会得到"更平滑的糊"
- 有**运动模糊 / 失焦** → **别做超分**，那是光学信息缺失，任何模型都救不了

详细判断表见 `references/routes-and-engines.md`。

---

## 这个包不承诺什么

- ❌ **不承诺把糊片变大片**。本地路线本质是插值 + 锐化，能改善观感，**造不出真实细节**
- ❌ **不救运动模糊与失焦**。那是拍摄问题，不是分辨率问题
- ❌ **不提供 API Key**。Key 需要使用者自己在 [api.a7w.cn](https://api.a7w.cn/) 获取
- ❌ **不代付费用**。调用消耗的是使用者自己账号的额度

---

## 一个实测出来的工程结论

服务器批量转档时，**线程数怎么给反直觉**。2 核机器实测：

```
-threads 2 × 2 并发  =  122 秒/条，load 9+     ← 更慢
-threads 1 × 2 并发  =  113 秒/条，load 6.6    ← 更快
```

**并发数 = 核数，单进程线程数给 1。** ffmpeg 内部线程间的同步开销会赔掉收益。详见 `references/local-ffmpeg.md`。

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
