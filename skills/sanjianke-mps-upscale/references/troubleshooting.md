# 腾讯云超分台 —— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、不扣费，能一次排掉一半问题。

```
✓ Key 有效 + 余额可读                            HTTP 200 · 余额 … 点
✓ 提交端点 tencent1080 可用（400 duration_unknown 即正确） HTTP 400 duration_unknown
✓ 提交端点 tencent2k 可用（400 duration_unknown 即正确）   HTTP 400 duration_unknown
✓ 提交端点 tencent4k 可用（400 duration_unknown 即正确）   HTTP 400 duration_unknown
✓ 查询路由 /api/v1/videos/{task_id} 可用         HTTP 400 task_not_exist
```

`doctor` 的三档探针发的是 `{"video_url": "https://example.invalid/probe.mp4"}`
（**带地址、不带时长**），上游规定返回 `400 duration_unknown`，停在扣费之前。

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

### `Key 有效 + 余额可读  ✗ HTTP 401`

Key 本身的问题。去 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

---

## 二、提交阶段的四个报错

### `提交失败（HTTP 400）：请提供 video_url（可公网访问的视频地址）`

`--url` 是空的，或者不是 `http(s)://` 开头。本包在本地就会拦（exit 2），
正常走不到上游。腾讯云 MPS 要能拉到这个地址，**内网地址 / `file://` / 本地路径都拉不到**。

### `提交失败（HTTP 400）：无法探测视频时长，请显式传 duration（秒）`

`--duration` 没给或给的不是数字。本包把它做成必填，本地就拦（exit 2）。
这是**设计如此**：`duration` 决定扣多少点，让平台去猜等于把账单交给运气。

用 ffprobe 量：

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 low.mp4
```

### `提交失败（HTTP 502）：[FailedOperation.InvalidMpsUser] invalid mps user`

**腾讯云侧拒了这次提交**，属于平台侧凭据问题，不是你的参数问题。特征：

- 返回体里带 `"code":"FailedOperation.InvalidMpsUser"`
- **没有 `task_id`**，所以**没有建单、没有冻结点数**

遇到这个报错：拿同一份请求等平台侧恢复后重试即可，**不会重复扣费**。
（2026-11-07 实测就是这个返回。）

### `提交失败（HTTP 502）` 其他 `FailedOperation.*`

腾讯云 MPS 侧的另一个错误码。把 `message` 原文贴出来对照腾讯云 MPS 文档；
同样**没有 `task_id` 就不扣费**。

---

## 三、查询阶段

### `查不到任务 xxx（试过：…→404 · …→400）`（exit 6）

`status` 的三级回退全都落空。三个可能：

1. **`task_id` 抄错**了（`task_` 后面那一串区分大小写）
2. **`--tier` 和提交时不一致**（`4k` 的任务用 `--tier 1080p` 查，第一级路由会 404，
   但第二、三级仍能查到 —— 所以这条只会造成慢，不会查不到）
3. **任务太老**，已经不在 `/me/tasks` 的第一页（整页上限 20 条）——
   直接 `python3 scripts/run.py status <task_id> --tier 4k`，
   走的是 `/api/v1/videos/{task_id}`，不受列表页数限制

### 已知：文档写的那条 GET 路由当前 404

`GET /api/v1/video/{tier}/{task_id}` 是网关文档写的查询接口，
实测当前返回的是 **SPA 的 HTML 404**（不是 JSON 的「任务不存在」）。
判据：同网关里存在的 GET 路由返回 JSON，不存在的返回 HTML。

所以 `status` 会自动往下试 `GET /api/v1/videos/{task_id}`（实测通）和 `/api/v1/me/tasks`
（本人台账）。`--json` 输出里的 `route` 字段会告诉你**这次是哪条路由给的答案**。

### `400 {"code":"task_not_exist"}`

这条路由是通的，纯粹是这个 id 不存在。核对 `task_id`。

---

## 四、任务失败与退款

### `status` 显示 `failed` / `提交后轮询到 failed`

- **失败全额退回**，`status --json` 里看 `chargedPoints` / `netPoints`
- `tasks` 里这条的 `status` 是 `refunded`，`netPoints` 是 0

### 冻结了但还没结算

任务的 `frozenPoints` 会先扣住，成功才 `settled`，失败 `refunded`。
`tasks` 命令把 `status` 与 `netPoints` 一起列出来，对账看这两列。

---

## 五、花钱相关

### `失败：预计 4800 点超过 --budget 100 点`（exit 5）

闸门在工作，**一个请求都没发**。调大 `--budget`、降档，或者先切片。

**`--budget` 单位是「点」**（1 元 = 100 点），默认 6000 点（60 元）。

### `失败：这会真实提交超分并扣约 4800 点（48.00 元）`（exit 4）

缺 `--yes`。**故意的**：按秒计费的单子必须显式确认。

想先看请求：

```bash
python3 scripts/run.py submit --url ... --tier 4k --duration 600 --dry-run
```

### 实际扣费比预估少

正常。单笔**保底 10 点**，所以只会「补到 10」，不会多收；
预估按 `ceil(duration × 单价)` 算，秒数带小数时是**上限**。

### 请求失败了，会扣钱吗？

**不会。** 参数错 400、凭据错 502、任务 failed，都不产生扣费；
失败已冻结的部分全额退回。

---

## 六、慢 / 超时

- 超分是**异步任务**：10 分钟 4K 片子通常要几分钟到十几分钟
- 本包 `submit` 默认轮询到完成，`--timeout` 默认 `3600` 秒
- 长片子建议 `--no-wait` 只提交，稍后 `status` 查 —— 断网也不影响任务
- 轮询间隔 `--interval` 默认 10 秒，别调太小（查询免费但也别刷）

### 轮询超时了怎么办

**任务还在跑，钱已经按提交时的秒数冻结。** 直接 `status <task_id>` 接着查，
不要重新提交（重新提交会再冻一笔）。

---

## 七、成品链接

### 链接 24 小时后打不开

平台只保留 **24 小时**。`--out` 可以让本包在完成时直接下载落盘：

```bash
python3 scripts/run.py submit --url ... --tier 4k --duration 600 --out out.mp4 --yes
```

### 用 `urllib` 下载 403

下载要自设 `User-Agent`（本包内部已经设了）。自己写脚本时注意：

```python
import urllib.request
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=600).read
```

---

## 八、`tsc_*` 档位

`tsc_teshd`（短剧增强）、`tsc_shortplay` 等 11 档在价目表里，但路由还没上：
`/api/v1/video/tsc_teshd` 及各种变体都是 404，
`/api/v1/apps/tsc_teshd/submit` 返回 `{"code":0,"msg":"应用或 API 不可用或未配置价格"}`
（应用层兜底话术，意思是该应用不在架）。

本包只接 `tencent1080` / `tencent2k` / `tencent4k`。网关开放后本包同步接上。

---

## 九、还想更省事

```bash
python3 scripts/run.py doctor && \
python3 scripts/run.py cost --tier 4k --duration 600 && \
python3 scripts/run.py submit --url ... --tier 4k --duration 600 --yes
```

`doctor` 通过才继续 —— 省掉一次白跑。

---

## 十、联系

加技术微信的方式见 `SKILL.md` 的 `## 联系我们`。
提问题时带上这三样，定位会快很多：

1. `python3 scripts/run.py doctor` 的完整输出
2. `--json` 的报错原文（`error.kind` + `error.message`）
3. `--duration` 与 `--tier`
