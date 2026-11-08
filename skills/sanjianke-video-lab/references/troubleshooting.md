# 视频后处理台 —— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、不扣费，16 项一次排掉大半问题。

---

## 一、Key 相关

### `失败：没有 API Key`（exit 2）

三处都没读到。按优先级检查：

1. `--key sk-...`
2. `echo $env:A7W_API_KEY`（PowerShell） / `echo $A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `Key + 余额接口可达` 打 ×，HTTP 401 / 403

Key 本身的问题。到 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

> 平台会直接 403 并告诉你该用哪个（`upstream_account_scope_blocked`）。

---

## 二、报错 → 原因 → 处理

### `{"error":{"code":"empty_url","message":"videoUrl 不能为空"}}`（HTTP 400）

`videoUrl` 没传或传了空串。本包不会走到这一步（本地就拦了）。

### `{"error":{"code":"pixverse_empty_url"}}`（HTTP 400，只在 `/api/v1/video/restore`）

restore 这条线的空 body 报错码和其它 10 档不同，含义一样：`videoUrl` 为空。
`doctor` 就是靠这个码确认「扁平 restore 端点正确」。

### `{"error":{"code":"unknown_tool","message":"未知的视频工具：restore"}}`（HTTP 404）

把 `restore` 打到了 `/api/v1/video/viapi/restore`。viapi 那条路里**没有** restore，
只有扁平 `/api/v1/video/restore`。

**本包默认就走对**；手工 curl 时注意。

### HTTP 404 + `<!DOCTYPE html>`（前端 SPA 兜底页）

路径根本不存在。典型：`/api/v1/video/faceswap`、`/api/v1/video/segment`、`/api/v1/video/cartoon`
—— 这三档只有 viapi 那条通：`/api/v1/video/viapi/<tier>`。

### `{"error":{"code":"url_not_allowed", ...}}`（HTTP 400）

`videoUrl` 不在平台白名单。原文：

> videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
> 或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）

**处理**：

```bash
python3 scripts/run.py upload --file input.mp4
# 拿 data.url 再提交
```

本包 `submit` 会先本地预检一遍，不合格直接退 `2` 并给出三种可用写法，不发请求。
确定要交给上游判断时加 `--allow-any-url`。

### `{"code":0,"msg":"请使用 file 字段提交一个文件"}`（HTTP 200）

`upload` 没带文件字段。字段名必须叫 **`file`**，`multipart/form-data`。

### `{"error":{"code":"not_found","message":"Task not found."}}`（HTTP 404）

视频后处理查询路由找不到这个 taskId。三种可能：

1. taskId 打错（`task_` 前缀别丢）
2. 任务属于别的 Key / 别的租户
3. 查错了路由 —— `GET /api/v1/videos/{id}` 是**视频生成**家族的，不查后处理任务

先试通用查询：`GET /api/v1/tasks/{taskId}`（免费，全站任务都能查）。

### `{"code":0,"msg":"任务不存在","data":null}`（HTTP 200）

打到了通用任务查询 `GET /api/v1/tasks/{id}` —— 它只认**模型任务 / 应用任务**，
视频后处理的任务查不到（实测两个真 taskId 都返回这个）。

**处理**：换后处理自己的查询路由：

```bash
curl -s "https://api.a7w.cn/api/v1/video/viapi/result/<taskId>" \
  -H "Authorization: Bearer $A7W_API_KEY"
```

`status` 子命令已经按这个顺序试，直接用它就行。

### 查出来是 `failed` + `refund`，过一会儿又变成 `processing`

**平台把失败的自动重试了。** 实测同一 taskId：先 `failed` + `refund: 45`，
几分钟后再查就是 `processing`（`note` 写「正在转存到本站，请稍候…」）。

**处理**：隔 30 秒再查一次；余额和流水才是最终口径，`status` 单次结果只当快照。

### `{"code":"task_not_exist"}`（HTTP 400）

打到了 `/api/v1/videos/{id}` —— 那是**视频生成**（muse-video / Seedance 那一族）的查询路径，
不服务视频后处理任务。

### `402 insufficient balance`

余额不够。去 [api.a7w.cn](https://api.a7w.cn/) 充值。注意按秒档会先冻结，余额要够冻结额度。

---

## 三、`fail` 里都是些什么

### `失败：预计 N 点超过 --budget M 点`（exit 5）

闸门在工作。`--budget` 单位是**点**（1 元 = 100 点），默认 5000。

```bash
python3 scripts/run.py cost --tier restore --seconds 600   # 先看要多少
python3 scripts/run.py submit --tier restore --video-url "..." \
    --duration 600 --budget 25000 --yes
```

**一个请求都没发**，不花钱。

### `失败：这会真实提交视频任务并预冻结约 N 点`（exit 4）

缺 `--yes`。想先看请求：

```bash
python3 scripts/run.py submit --tier colorize --video-url "..." --dry-run
```

### `失败：上游只收本站托管的地址`（exit 2）

`videoUrl` 不在白名单。先 `upload`，或用 `--allow-any-url` 交给上游判断。

### `--route flat` 之后报 `unknown_tool` / 404

`--route` 是给排查用的逃生口。`restore` 走 `flat`、其余走 `viapi` 才是实测通的路：
把 `--route` 去掉，回到 `auto`。

---

## 四、慢 / 超时

- `viapi/cartoon` **冷启动**会慢：第一次探针见过 45 秒读超时，重试立刻 400。
  `doctor` 默认探针超时 90 秒，就是为它留的。
- 提交是**异步**的，POST 只负责受理，正常几秒内返回；处理进度看 `status`。
- 长片子按秒计费，`--duration` 传准一点，别让预冻结额度卡住余额。

### `status` 一直 `processing`

正常。建议 2–5 秒轮询一次，`completed` / `failed` / `cancelled` 再停。
成品链接有效期约 **30 分钟**，拿到就转存。

---

## 五、钱相关

### 实际扣费比 `cost` 预估多

按秒档是**预估 vs 实际时长**的差别。`cost` 用 `--seconds`（默认 60）估算，
真实结算按上游读出来的实际时长。想算准就把 `--duration` 传成真实秒数。

按次档（`shot` / `castcrew` / `delogo`）不会超：一次就是一次。

### 失败了会扣钱吗

**不会。** 文档写明「任务失败全额退回」，提交时只是冻结。

### 想确认自己到底花没花

```bash
python3 scripts/run.py log              # 本地台账（提交 / 上传都记）
```

再看服务端流水（免费）：

```bash
curl -s "https://api.a7w.cn/user/balance/logs?limit=100" -H "Authorization: Bearer $A7W_API_KEY"
```

`type=charge` / `reserve` 是扣与冻，`refund` 是退回；`reference` 里带实际路径，
`sync:/api/v1/video/...` 就是视频线。

---

## 六、想更省事

```bash
python3 scripts/run.py doctor \
  && python3 scripts/run.py upload --file input.mp4 \
  && python3 scripts/run.py submit --tier colorize --video-url "<上一步的 url>" --yes
```

`doctor` 通过才继续 —— 省掉一次白跑。

---

## 七、联系

照 `SKILL.md` 末尾的「联系我们」找技术微信，附上 `doctor` 的整屏输出和 `log` 里的那一行，
基本一句话就能定位。
