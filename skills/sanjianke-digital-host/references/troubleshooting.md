# 排错：按报错找原因

先跑一次免费的 `doctor`，六项全 ✓ 说明 Key、三个端点是否已配价、两张速率卡、任务查询线、余额都通：

```bash
python3 scripts/run.py doctor
```

---

## 一、提交阶段的报错

| 报错原文 | 原因 | 怎么办 |
|---|---|---|
| `请提供 image_url` | talk 少了人物图 | `--image` 给公网 URL，或本地文件加 `--upload` |
| `text 模式请提供 audio_url 作为参考音色` | talk 少了参考音色 | `--voice-ref` 给一段 3–10 秒单人清晰人声 |
| `无法从该地址下载媒体…Could not resolve host` | 图片/音频地址平台拉不到 | 换成公网可直链；OSS 私有桶要开读权限；防盗链要放行平台服务器 |
| `当前请求未命中可用计费规格` | dub 缺 video_url / audio_url，或 model 写错 | 两个地址都要给；`--model` 只能是 `xiaojiayu1.0/2.0/3.0` |
| `未在请求中找到可用的时长字段（如 duration）…` | image_human 既没给 duration、也探测不到媒体 | 显式 `--duration 秒数` |
| `点数余额不足` / `insufficient_points` | Key 余额不够 | 到 api.a7w.cn 充值；先 `cost` 算一遍再跑 |

### 「地址拉不到」是最常见的一条

平台是**服务器去拉你的文件**，不是你本机读。所以：

- `localhost`、`127.0.0.1`、内网 IP 一律拉不到
- `https://example.invalid/...` 这类占位地址会立刻报 `Could not resolve host`
- 分享链接带登录态的（网盘、微信临时链接）会 403
- 最稳的办法：本地文件加 `--upload`，先传平台临时地址（**上传不计费，0 点/次**，24 小时有效）

### 提交失败也会看到一对「冻结 −250 → 退款 +250」

应用层 `submit` 是**先同步预扣、再校验参数**。哪怕请求因为缺字段被拒，流水里也会出现
`reserve_sync:/api/v1/apps/<app>/submit` 与 `refund:sync:/api/v1/apps/<app>/submit` 一对记录。
净额 0，任务也不会建。想核对自己的流水：

```
GET /user/balance/logs?limit=100
```

---

## 二、三路各自的坑

### talk（pic_lipsync）

**「文案驱动」不等于零素材。** `mode=text` 时 `audio_url` 仍然必填，它代表**用谁的声音念**。
少这一条会直接报 `text 模式请提供 audio_url 作为参考音色`。

- 参考音色要求：单人、无背景音乐、3–10 秒、语速自然、别是变声/电音
- 参考音色越干净，出来的口型和音色越稳
- 档位参数真名是 `quality`（`standard/fast/max`），不是 `mode`；`mode` 只切 `audio`/`text`

### drive（image_human）

**`--mode` 必填，这是故意做成必填的。**
schema 的默认是 `standard`，计费卡的默认是 `fast` —— 不传时出片按标准档、收钱按快速档，
档位和账单对不上。本包宁可报错也不替你猜。

**`--duration` 必填，这也是故意的。**
带上它，价格被费率卡锁死 = 费率 × 秒数，预算能精确到点；不给则由平台按上游冻结点计费，
`cost` 只能估。`duration` 填**输入音频的真实秒数**，从播放器里看一眼就行。

### dub（lipsync）

- 先解析计费规格、后校验参数，所以缺参时看到的是「未命中可用计费规格」这句
- `xiaojiayu1.0` 便宜（2.7 点/秒），`2.0/3.0` 贵 5 倍（13.5 点/秒）；先用 1.0 试效果
- 视频里的人脸要清晰、正脸或小角度侧脸；遮挡、快速运动、多人同框都不稳

---

## 三、查询阶段的报错

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `任务不存在` | task_id 写错，或这个任务不是本 Key 建的 | 任务只能由创建它的 Key 所在租户查 |
| `GET /api/v1/videos/{id}` 返回 `task_not_exist` | 走错线了 | 平台线是 `GET /api/v1/tasks/{id}` |
| `status=completed` 但没有成片地址 | 结果地址偶尔是空串（实测竞态） | 隔几秒再 `status` 一次 |
| 一直 `pending` / `processing` | 队列排队 | 数字人视频常见 2–10 分钟，`--timeout` 默认 900 秒 |

本包 `--task-id` 查询命令：

```bash
python3 scripts/run.py status --task-id task_xxx
python3 scripts/run.py status --task-id task_xxx --app pic_lipsync    # 走应用级查询
python3 scripts/run.py status --task-id task_xxx --save               # 顺便下载成片
```

---

## 四、退出码

| 码 | 含义 | 常见触发 |
|---|---|---|
| `0` | 成功 | — |
| `2` | 用法错 | 缺 `--image` / 缺 `--mode` / 缺 `--duration` / 选项写缩写 |
| `3` | 自检没全过 | `doctor` 有 ✗ |
| `4` | 需要确认 | 没给 `--yes`，会告诉你这次要花多少点 |
| `5` | 预算不足 | 预计点数 > `--budget`，**一个请求都不发** |
| `6` | 调用失败 | 提交被拒、任务失败、等待超时 |
| `1` | 内部错 | 见 traceback |
| `130` | 被 Ctrl-C 中断 | — |

`--json` 时失败也会给结构化信封：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "预计 1800 点超过 --budget 500 点…"}}
```

---

## 五、Key 相关

```bash
python3 scripts/a7w.py login --key sk-你的key     # 验证并保存
python3 scripts/a7w.py whoami                     # 看当前用的是哪个 Key
```

没有 Key 时任何付费命令都会退 `2` 并提示三选一：
`--key` / 环境变量 `A7W_API_KEY` / `~/.a7w/config.json`。

注册领 Key：<https://api.a7w.cn/> 。
