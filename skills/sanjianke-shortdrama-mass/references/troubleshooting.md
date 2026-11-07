# 排错：按报错找原因

先跑一次自检，多数问题它当场就说清：

```bash
python3 scripts/run.py doctor
```

七项全 √ 说明 Key、价目、应用注册表、查询路由、上传都通。哪项 × 就看下面。

---

## 一、退出码对照

| 退出码 | 含义 | 先看哪 |
|---|---|---|
| `0` | 成功 | — |
| `2` | 用法错：缺参数、选项写错、`--step` 名字不对、`--project` 不合规范 | 报错原文里写了可选值 |
| `3` | `doctor` 或 `check` 没过 | 看逐行 × 的那一条 |
| `4` | 需要 `--yes`（消息里写清了要花多少点） | 确认后加 `--yes` |
| `5` | 预算不足：预计点数 > `--budget`，**一个请求都没发** | 调大 `--budget` 或缩秒数 |
| `6` | 调用失败：网关报错、任务不存在、提交被拒 | 看下面第二到第五节的报错原文 |
| `1` | 内部错（脚本 bug） | 带 traceback，贴出来 |
| `130` | 被 Ctrl-C 中断 | 重跑即可，已提交的任务在 `status` 里 |

`--json` 下失败也是一个 JSON：`{"ok":false,"exit":5,"error":{"kind":"budget","message":"…"}}`，
`kind` 取 `usage` / `gate` / `confirm` / `budget` / `call` / `interrupt` / `internal`。

---

## 二、Key 与账号

| 报错 | 原因 | 处理 |
|---|---|---|
| `没有 API Key` | 三处都没读到 | `python3 scripts/a7w.py login --key sk-...`，或设 `A7W_API_KEY`，或 `--key` |
| `401` / 鉴权失败 | Key 无效或已吊销 | 重新创建 Key 再 login |
| `402` / 点数不足 | 余额不够本次调用 | 报错里带本次所需点数，去 [算力中心](https://api.a7w.cn/) 充值 |
| `403` / 无权限 | 这个 Key 所属账号没有该应用权限 | 部分应用是邀请制，需单独申请 |
| `请先配置API Key` | 客户端没读到 Key | 同第一条 |

`doctor` 第 1 项就是余额接口，它过了说明 Key 没问题。

---

## 三、余额 / 冻结 / 退款怎么读

**现象：`doctor` 显示「冻结 N 点」，但不是 0。**

`冻结` 是**正在跑的任务预扣的点**，任务结算后自动解冻。`doctor` 的判定条件是
「余额前后一致」，不是「冻结为 0」—— 有别的任务在跑时冻结本来就不会是 0。

**净额 0 但余额被扣过又退回**，说明命中了「先冻再退」的口子，看流水：

```bash
python3 scripts/run.py status --task-id <taskId>     # 实扣多少看 usage.points_cost
curl -H "Authorization: Bearer $A7W_API_KEY" \
  "https://api.a7w.cn/user/balance/logs?limit=20"    # 冻结与退款成对出现
```

流水里成对出现的 `reserve_sync:…  -N` 与 `refund:sync:…  +N`，就是「先冻再退」。
净额 0，但钱包被短暂动过 —— 本包的 `doctor` 因此一次应用层 `submit` 都不发。

**现象：一条任务的预扣比 `cost` 算的高。**

`cost` 给的是**估价**，真实扣费看返回里的 `usage.points_cost`。
配音是「上游实际点数 × 3」，口播是「上游实际点数 × 5」，都是按上游结算值乘倍率，
字数 / 秒数只是估算依据。

---

## 四、提交被拒（`exit 6`）

### 4.1 `400 url_not_allowed`

```
videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）
```

地址不在白名单。三种可用写法：

```bash
# 推荐：先传再提交（免费）
python3 scripts/run.py upload --file 人物图.jpg        # 拿 data.url
python3 scripts/run.py run --step avatar --image-url "<上一步的 url>" ...
```

本站成片地址 `https://vr.a7w.cn/result/xxx.mp4`、本站七牛
`https://cdn2.jiujiushuyuan.cn/vr/xxx.mp4` 也可以直接用。`oss.gpu.likeadmin.cn/openapi/`
的地址有效期约 **24 小时**，别存着第二天再用。

### 4.2 `400` + 字段名（参数校验）

本包每个工位都会先本地预检，所以正常走流程不会撞到这里。撞到了说明手写的 body 有问题：

| 工位 | 必填 |
|---|---|
| `voice` | `text` |
| `avatar` | `image_url`、`audio_url`、`content`（`mode=text` 时） |
| `music` | `model`、`custom_mode`、`instrumental` |
| `beat` | `task_id`、`audio_id` |
| `cover` | `content`（数组，含文本项）、`duration` 4–15 整数 |

### 4.3 `beat` 报「要 --music-task 与 --music-audio」

`beat` 的输入是**配乐那一步的输出**。先跑 `music`，拿返回里的 `task_id` 与 `audio_id`：

```bash
python3 scripts/run.py status --task-id <配乐 taskId>   # 打 audio_id
python3 scripts/run.py run --step beat --music-task <taskId> --music-audio <audioId> --yes
```

### 4.4 `cover` 报「现在走的是本地截帧」

默认封面是本地截帧（0 点），不做提交。要动态片头就显式给分辨率：

```bash
python3 scripts/run.py run --step cover --cover 480P --cover-seconds 4 --yes
```

`duration` 只收 **4–15 秒整数**，给了 3 或 16 会在本地就被退回。

### 4.5 `400 empty_url` / `400 pixverse_empty_url`

视频后处理线（`/api/v1/video/*`）的参数校验，说明请求到了端点但缺 `videoUrl`。
本包不用这几条线，看到它就是端点探针打错了路径。

### 4.6 `404` + HTML

网关 SPA 兜底，**这个前缀下没有这个端点**。检查路径前缀：
应用层是 `/api/v1/apps/<app>/<api>`，视频线是 `/api/v1/video/<tier>`。

### 4.7 `502` + `InvalidMpsUser`

路由存在，上游凭据坏了 —— 不是你的问题，换时间重试或联系技术支持。

### 4.8 `200` + `{"code":0,"msg":"应用或 API 不可用或未配置价格"}`

应用层兜底话术。**假代号也返回同一句**，所以这句话不能当「端点存在」的证据。
换用 `GET /api/v1/apps` 看应用是否注册。

---

## 五、查不到任务

```
失败：查不到任务 task_xxx：任务不存在（刚提交可能还没落库，等 30 秒再查）
```

- 刚提交的前 30 秒可能还没落库，等一会儿再查。
- 本包只查 `GET /api/v1/tasks/{id}`。视频后处理线的任务在 `/api/v1/video/viapi/result/{id}`，
  那是另一个包的事。
- 应用层 `query` 也能查，但它按次计费（`nano_banana/query` 72 点/次），本包不走。

**现象：`status` 显示 `completed` 但成片地址是空串。**

实测竞态：任务刚 `completed` 时结果字段还没落全，过 30 秒再查就有。
成片链接有效期很短（约 30 分钟），拿到就转存。

---

## 六、钱和预算

**现象：一条算出来 858 点，实际扣得不一样。**

逐项核对：

| 工位 | 本包估价 | 实际结算 |
|---|---|---|
| `voice` | 0.18 点/字 | 上游实际点数 × 3 |
| `avatar` | 15 点/秒 | 上游实际点数 × 5（standard 档 = 3 点/秒 × 5） |
| `music` / `beat` | 60 点/条 | media_services_33 未配价，预冻 60，按结算 |
| `cover` | `resolutionRates` × 秒数 | 同左（480P 14 / 768P 28 / 1080P 60 / 2K 80 / 4K 80） |

**现象：`--budget` 拦住了我。**

`--budget` 单位是**点**，默认 10000 点（100 元）。一天 10 条全配是 8,580 点，默认值刚好够。
只跑几条：`--budget 3000` 就够 3 条。估算法是「选中的工位点数之和 × 条数」，
闸门在**整批开始前**就卡，不会跑一半没钱。

**现象：`batch` 跑到一半失败。**

默认第一条失败就停（已提交的进台账，`log` 能看到）。要跑完剩下的加 `--keep-going`。

---

## 七、Windows / 编码

| 现象 | 原因 | 处理 |
|---|---|---|
| 控制台里 `√` `×` 变成 `?` | 老控制台代码页不是 UTF-8 | 本包已用 `reconfigure(errors="replace")` 兜底；要看原样输出就 `set PYTHONIOENCODING=utf-8` |
| `UnicodeEncodeError: 'gbk'` | 同上，但被兜底了 | 已经不会崩：实测 `PYTHONIOENCODING=gbk python run.py doctor` 退出码 0 |
| 中文文件名乱码 | 控制台代码页 | PowerShell 里 `chcp 65001`，或把输出重定向到文件再看 |
| `run.py: error: ambiguous option` | 选项简写 | 本包父命令与每个子命令都关了缩写（`allow_abbrev=False`），写全名 |
| 生成了一堆 `.pyc` | 没关字节码 | 每个命令前加 `$env:PYTHONDONTWRITEBYTECODE="1"`（脚本内也已设 `sys.dont_write_bytecode`） |

---

## 八、`check` 没过（`exit 3`）

| 提示 | 原因 | 处理 |
|---|---|---|
| `缺 avatar（口播成片）` 等 | 该集没出这一件 | 跑对应 `--step`，或确认文件在这一级目录下 |
| `命名不合规范` | 文件名不是 `<项目>_SxxExx_<工位>_<规格>_vxx.<ext>` | 按 `plan.json` 里的文件名改 |
| `封面 720x1280，规范要 1080x1920` | 封面尺寸不对 | 重出封面，或本地裁到 1080×1920 |
| `体积 12.3 MB 超过 2 MB` | 超过该工位的上限 | 压缩；口播成片上限 200 MB，封面 2 MB |
| `SRT 不是 UTF-8` | 字幕文件编码不对 | 转成 UTF-8（无 BOM 也行） |
| `读不出像素` | 文件坏了或不是真图 | 换文件；`check` 读的是文件头，改扩展名骗不过去 |

`check` 只读本地文件，**0 点**。验收通过给 `0`，不通过给 `3`。
