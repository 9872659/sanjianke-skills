# 排错：按报错找原因

> 先跑 `python3 scripts/run.py doctor` —— 11 项全 √ 说明 Key、价目、6 个端点、两条查询路由、上传都通。
> 下面按「你会看到的原文」组织，**左边是报错，右边是原因与处理**。

---

## 一、提交阶段

### `400 {"error":{"code":"empty_url","message":"videoUrl 不能为空"}}`

请求里没有 `videoUrl`。四个视频工位都必填。

```bash
run --step subtitle --video-url "https://oss.gpu.likeadmin.cn/openapi/…" --yes
```

`doctor` 里看到 `400 empty_url` 是**正确结果**：说明端点存在，且停在了参数校验层（不建任务、不冻结）。

### `400 {"error":{"code":"url_not_allowed", …}}`

`videoUrl` 不在平台白名单内。原文给的三选一：

| 可用来源 | 形态 |
|---|---|
| 本站成片 | `https://vr.a7w.cn/result/xxx.mp4` |
| 本站七牛 | `https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4` |
| 本站上传接口 | `https://oss.gpu.likeadmin.cn/openapi/<租户>/<日期>/<hash>.mp4` |

本地素材先传：

```bash
python3 scripts/run.py upload --file 素材.mp4
```

`run` 会在发请求前做同样的预检，不合格直接退 `2`。

### `404 {"error":{"code":"unknown_tool"}}`

路径拼错了。本包只用 `/api/v1/video/viapi/<castcrew|delogo|subtitle|enhance>` 这一条前缀；`restore` 之类的能力属于别的包。

### `unsupported_speaker_branch`

混剪请求里带了 `content` 或 `speakerId`。`smart_clip/broadcast_mixcut` 当前只走 `audioUrl` 或素材链路 ——
解说词先走 `tts` 出音频，再把音频地址填进 `audioUrl`。

### 混剪返回参数错误

先确认 `styleId` 来自 `scene=oralMixCutting` 的模板：

```bash
python3 scripts/run.py template
```

模板与场景一一对应：`oralMixCutting` 的模板只能提交给 `broadcast_mixcut`。

### `code 0` +「任务不存在」/ `404 not_found`

刚提交就查，可能还没落库。`run` 会自动轮询；手工查时等 5–10 秒重试：

```bash
python3 scripts/run.py status --task-id task_xxx --step enhance
```

### `200 {"code":0,"msg":"任务不存在"}`（`/tasks/{id}`）

这条路由服务的是**应用工位**（tts / mixcut）。视频工位要用：

```
GET /api/v1/video/viapi/result/{taskId}
```

`status` 两条都试，`--step` 填上会少绕一圈。

---

## 二、上传阶段

### `{"code":0,"msg":"请使用 file 字段提交一个文件"}`

multipart 字段名必须是 `file`。本包 `upload` 已固定；自己用 curl 时：

```bash
curl -X POST https://api.a7w.cn/api/v1/upload \
  -H "Authorization: Bearer $A7W_API_KEY" -F "file=@素材.mp4"
```

### 上传成功但地址过期

上传返回的地址**最长 24 小时**。当天跑完链路；跨天就重新 `upload`。

### 文件太大

单文件默认上限 512 MB。先压一道再用。

---

## 三、计费与冻结

### 余额突然少了几十点，几秒后又回来了

`reserve_sync` 的**冻结 → 全额退回**。应用层（`apps/*`）的提交与部分免费 GET 都会这样：
先按 `estimate` 冻结，再校验 / 执行，失败或只读就退回。

实测：`GET /apps/smart_clip/template` 冻 50 点、`GET /apps/voice_tts/list_voices` 冻 150 点，都在几秒到十几秒内全额退。

### 任务 `failed` 了，钱扣了吗？

没扣。平台全额退回，`status` 里能看到 `refund` 字段。

### 看到 `failed` 别急着重提

视频工位实测过「`failed` + `refund` → 几分钟后自动变 `processing`」（平台自动重试）。
`run` 会等 30 秒再确认一次；手工排查也用 `status` 多看一次，重提会再扣一次。

### 想先确认要花多少

```bash
python3 scripts/run.py cost --seconds 60 --chars 200
```

### 退码 `5`：预算不足

预计点数 > `--budget`，**一个请求都没发**。调大 `--budget`（单位：点，1 元 = 100 点）或缩小 `--seconds` / `--chars`。

### 退码 `4`：需要确认

没给 `--yes`。提示里已经写了这一趟要花多少点，确认后补 `--yes`。

---

## 四、参数与命令

### `unrecognized arguments: --bud`

全家族 `allow_abbrev=False`，选项要写全：`--budget 100`。

### `--step` 与 `--all` 同时给

二选一。全链用 `--all`；单步用 `--step <名字>`。

### `--step mixcut` 报缺 `--style-id`

先 `template` 拿模板 ID；再把素材与解说音频一起给它：

```bash
run --step mixcut --video-url "..." --audio-url "..." --style-id <模板> --yes
```

### 全链跑完发现没出成片

`--all` 只跑「输入齐全」的工位：给了 `--text` 才有 `tts`，给了 `--style-id` 才有 `mixcut`。
想确认会跑哪几步，先 `--dry-run` 看一眼。

---

## 五、环境

### Windows 控制台中文乱码 / 打勾变问号

本包已做 GBK 兜底（`sys.stdout.reconfigure(errors="replace")`），输出只用 `√` / `×`。
还是乱码就设一下：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

### 跑一次多出 `.pyc`

加环境变量：

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
```

本包 `run.py` 里也设了 `sys.dont_write_bytecode = True`。

### `401` / `403` / 没 Key

Key 三选一：`--key` → `A7W_API_KEY` → `~/.a7w/config.json`。

```bash
python3 scripts/a7w.py login --key sk-你的key
```
