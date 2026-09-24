# 本地 ffmpeg 路线：参数详解与工程要点

## 一、滤镜链

```
降噪去块 → lanczos 放大 → 自适应锐化 → 高质量编码
```

三个滤镜各司其职：

| 滤镜 | 作用 | 为什么是它 |
|---|---|---|
| `hqdn3d` | 时域 + 空域降噪 | 压花的片子噪点和块效应混在一起，先降噪能让后面的锐化不放大噪点 |
| `deblock` | 去块效应（仅 level 2） | 低码率片的方块边界很硬，不先去块，放大后方块跟着变大 |
| `scale=...:flags=lanczos` | 重采样放大 | lanczos 是「锐利但不产生明显振铃」的经典选择，比默认 bicubic 好 |
| `cas` | 对比度自适应锐化 | 比 `unsharp` 聪明：只在低对比区域锐化，不会把噪点也锐化出来 |
| `unsharp` | 传统锐化（仅 level 2） | 块效应严重时补一刀 |

### 两档强度

| 档位 | 滤镜链 |
|---|---|
| **level 1（温和，默认）** | `hqdn3d=1.0:1.0:4:4,scale=-2:{H}:flags=lanczos,cas=0.35` |
| **level 2（强力）** | `deblock=filter=weak:block=8,hqdn3d=1.5:1.5:6:6,scale=-2:{H}:flags=lanczos,cas=0.5,unsharp=5:5:0.6:5:5:0.0` |

**怎么选**：先跑 level 1。如果放大后**方块边界还是很明显**，再上 level 2。

> level 2 的 `hqdn3d` 参数更强（1.5 vs 1.0），**降噪过头会让画面发"蜡"**——细节被抹平，看起来像塑料。所以别默认上 level 2。

---

## 二、手写命令

```bash
# level 1：温和
ffmpeg -y -hide_banner -nostdin -i input.mp4 \
  -vf "hqdn3d=1.0:1.0:4:4,scale=-2:1920:flags=lanczos,cas=0.35" \
  -c:v libx264 -preset veryfast -threads 1 -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart output.mp4

# level 2：强力
ffmpeg -y -hide_banner -nostdin -i input.mp4 \
  -vf "deblock=filter=weak:block=8,hqdn3d=1.5:1.5:6:6,scale=-2:1920:flags=lanczos,cas=0.5,unsharp=5:5:0.6:5:5:0.0" \
  -c:v libx264 -preset veryfast -threads 1 -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart output.mp4

# 没有音轨时用 -an，避免 ffmpeg 报 "does not contain any stream"
ffmpeg -y -i silent.mp4 -vf "..." -c:v libx264 -an output.mp4
```

### 参数说明

| 参数 | 值 | 为什么 |
|---|---|---|
| `scale=-2:{H}` | H = 1080 / 1440 / 1920 | `-2` 表示宽度按比例自动算并**取偶数**（libx264 要求宽高都是偶数，写 `-1` 会因奇数宽度失败） |
| `flags=lanczos` | — | 重采样算法，不写默认 bicubic，锐度差一截 |
| `-preset veryfast` | — | 质量/速度平衡点。再快（ultrafast）质量掉得明显 |
| `-crf 18` | 18 | 视觉无损附近。**再低没有意义**——源片信息量是瓶颈，不是编码 |
| `-pix_fmt yuv420p` | — | 兼容性最好，播放器和平台都认 |
| `-threads 1` | 1 | 见下节，**这不是笔误** |
| `-movflags +faststart` | — | 把 moov 移到文件头，边下边播，上传到网页也更快开始 |
| `-nostdin` | — | 批量跑时防止 ffmpeg 抢标准输入导致循环卡住 |

---

## 三、一个实测出来的并转档参数（重要）

服务器上批量转档时，**线程数怎么给**这件事反直觉。

我们自己线上是 2 核机器，实测结果：

```
-threads 2 × 2 并发  =  122 秒/条，load 9+     ← 更慢
-threads 1 × 2 并发  =  113 秒/条，load 6.6    ← 更快
```

**结论：线程超卖会让整体更慢。**

2 核的机器，让**每个 ffmpeg 只吃 1 个线程**，靠 **2 个进程并排**吃满 2 核，吞吐反而最高。因为 ffmpeg 内部线程之间有同步开销，2 个 2 线程进程抢 2 个核，光在上下文切换上就赔掉了。

**推而广之**：并发数应该等于**核数**，单进程线程数给 **1**。

```
并发数 = CPU 核数
-threads 1
```

---

## 四、工程要点（都是从坑里换来的）

### 1. 产物大小必须校验

```python
if not out.exists() or out.stat().st_size < 10240:
    out.unlink()
    raise RuntimeError("转档产物异常(文件过小)")
```

**10 KB 是个经验阈值。** 没有这道校验，ffmpeg 因参数错误产出空文件时，流水线会把它当成功——然后你在下游花几个小时排查"为什么这条片子是黑的"。

### 2. 上游已经达标时跳过重编码

如果上游（AI 模型）输出的分辨率**已经达到目标**，不要再走一遍 libx264 编码：

```bash
ffmpeg -y -i src.mp4 -c copy -movflags +faststart out.mp4
```

`-c copy` 是**流拷贝**，不解码不编码，CPU 消耗几乎为零。实测能省掉整条转档时间。

### 3. 必须加超时护栏

```bash
timeout 900 ffmpeg -y -nostdin -i ...
```

大视频转档可能跑很久。**没有超时护栏，一个卡死的进程能拖垮整台机器。** 900 秒是我们在 30 秒片长上限下调出来的值。

### 4. `ffprobe` 探测失败要有兜底

探时长失败时不要直接崩——给一个保守的默认值继续走，否则一条探测不了的片子会中断整个批次。

### 5. 批量时把 `-nostdin` 加上

不加的话，ffmpeg 会去抢标准输入。在循环里跑是经典的"跑着跑着卡住"的来源。

---

## 五、ffmpeg 怎么装

| 系统 | 命令 |
|---|---|
| Windows | `winget install Gyan.FFmpeg` |
| macOS | `brew install ffmpeg` |
| Ubuntu / Debian | `sudo apt install ffmpeg` |
| CentOS / RHEL | `sudo yum install ffmpeg`（需先配 EPEL + RPM Fusion） |

装完 `ffmpeg -version` 和 `ffprobe -version` 都要能跑（有些精简包只带 ffmpeg 不带 ffprobe）。
