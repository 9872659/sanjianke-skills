# 排错：按报错找原因

先看退出码，再看 HTTP，再看状态文件。90% 的问题在前两步就能定位。

---

## 一分钟定位

| 现象 | 先查 | 多半是 |
|---|---|---|
| `exit 2` 失败：第 N 行… | `plan --file 清单` | 清单行格式 / 端点不在放行表 / 缺 points / id 重复 / videoUrl 外站 |
| `exit 4` 失败：这次要发… | 加 `--yes` | 没给确认 |
| `exit 5` 失败：清单还有… | `cost --file 清单` | 预估合计超 `--budget`，一个请求都没发 |
| `exit 6` 跑完一轮有失败 | `status --file 清单` | 逐条错误在失败明细里 |
| `exit 3` 自检有 × | `doctor` | Key / 价目 / 应用目录 / 探针有一项没通 |
| `exit 130` | 重跑同一条命令 | 你按了 Ctrl-C，状态已落盘，接着跑即可 |

```
python3 scripts/run.py status --file 1000条.jsonl
python3 scripts/run.py run --file 1000条.jsonl --retry-failed --yes
```

---

## 清单类（exit 2）

| 报错原文 | 原因 | 改法 |
|---|---|---|
| `第 3 行不是合法 JSON` | 一行写了多行 JSON、或尾随逗号 | 一条任务压成一行；用 `plan` 逐行定位 |
| `第 3 行缺 id` | 少了唯一名字 | 加 `"id": "img-0003"` |
| `id 重复：img-0001（第 1 行与第 2 行）` | 同一个 id 出现两次 | 改 id；状态文件按 id 落盘，重复会互相覆盖 |
| `端点 … 不在放行表` | 写了 GET、`/apps/<app>` 裸路径、`*/query`、`/api/v1/tasks` 或拼错档位 | 用 `catalog` 里的端点，提交只走 POST 子路径 |
| `写的是 /api/v1/apps/nano_banana：应用层裸路径…` | `/apps/<app>` 命中通配计价 | 改成 `/api/v1/apps/nano_banana/submit` |
| `写的是 /api/v1/apps/nano_banana/query：应用层查询一次一扣…` | 把查询写进了清单 | 查询交给免费视图，结果去 billing 台账取 |
| `端点按实际结算、价目表里没有公开单价` | 音频接口 / 图片数字人 / 视频对口型没写 points | 在这一行补 `"points": <预估点数>` |
| `按秒计费，请在 body 里给 duration` | 视频档没有时长 | `body.duration` 或行内 `seconds` |
| `按字计费，请在清单里给 chars` | 语音档没有字数 | 行内 `chars`，或 `body.text` 让本包数 |
| `videoUrl 不在平台白名单（example.invalid）` | 外站地址 | `upload --file 素材.mp4` 换地址；确要外站加 `--allow-any-url` |
| `--concurrency 取 1~16` | 并发写超了 | 先 4，稳了再加 |
| `unrecognized arguments: --tier` / `invalid choice: 'cat'` | 选项或子命令缩写 | 写全：`--budget`、`catalog`（本包关掉了缩写） |

---

## 调用类（exit 6）

| HTTP / 报错 | 含义 | 改法 |
|---|---|---|
| `400 empty_url` | 视频后处理档没收到 videoUrl | `body.videoUrl` 必填，先用 upload 换地址 |
| `400 pixverse_empty_url` | restore 档没收到 videoUrl | 同上 |
| `400 url_not_allowed` | 地址不在白名单 | 只用 `oss.gpu.likeadmin.cn/openapi/…`、`vr.a7w.cn`、`cdn2.jiujiushuyuan.cn/vr/` |
| `401` / `403` | Key 无效或没权限 | `python3 scripts/a7w.py login --key sk-…`，再 `doctor` |
| `404` + HTML | 端点没注册（SPA 兜底） | 对照 `catalog` 的路径，档位名多半拼错 |
| `404` + `not_found` | 查询视图还没建 | 等几秒重查；本包轮询 6 次见不到会记 `submitted` |
| `422` + 字段名 | 参数校验失败 | 按报错里的字段补 body；这类不重试，直接记失败 |
| `429` | 限流 | 降 `--concurrency`（4 → 2），`--retry` 留 2 次即可 |
| `500` / `502` / `504` | 上游抖动 | 本包会自动退避重试 2 次；连续失败看 `/user/balance/logs` 是否已退 |
| `502 InvalidMpsUser` | 路由在、上游凭据坏了 | 换同能力的另一档（`catalog` 里有等价项），或等平台修 |

单条失败不影响整批：状态文件里记 `failed`，其余照跑；收工后 `--retry-failed` 只补失败的。

---

## 轮询类

| 现象 | 原因 | 处理 |
|---|---|---|
| 视频任务一直 `submitted` | `GET /api/v1/tasks/<id>` 本来就不返回视频后处理任务 | 本包已按端点分流到 `/video/viapi/result/<id>`；查不到就等下一轮 `status` |
| 应用层任务永远 `submitted` | `/query` 按次计费，本包默认不自动轮询 | 出片后到对应能力包或 `sanjianke-billing` 台账取结果 |
| 轮询到 `--wait` 上限还是 `processing` | 任务确实慢 | 记 `submitted`，不重复提交；稍后 `status` 或去 billing 看 |
| 刚提交就 404 `not_found` | 视图有延迟 | 本包连续 6 次（约 30 秒）见不到才放弃 |

**轮询永远只打两条免费视图**，`/query` 一次都不发。

---

## 断点 / 状态类

| 现象 | 原因 | 处理 |
|---|---|---|
| `状态文件读不出来` | 文件被手改坏、或不是本包写的 | 挪走旧文件重跑；`--state` 指一份新的 |
| `状态文件格式不对` | 缺 `tasks` 对象 | 同上 |
| 重跑时全部跳过 | `done` / `submitted` 都算完成 | 正常；要看清单里的总数用 `status`（会显示未开始几条） |
| 想重跑某一条 | id 在状态里已 done | 从清单删掉这一行，或换 `--state` 开新档 |
| `unknown` 状态 | 上次中断时正在提交，可能已建任务 | 先看 billing 台账同时间的记录；确认没有再加 `--retry-failed` |
| 同一批跑了两遍，钱花了两份 | 换了 `--state` 或删了状态文件 | 状态文件就是账本，别删；重跑永远用同一份 |

状态文件写入是原子的（临时文件 + `os.replace` + `fsync`），断电最多丢正在写的那一条。

---

## 预算类

| 现象 | 原因 | 处理 |
|---|---|---|
| `exit 5` 且提示「一个请求都没发」 | 开跑前合计就超预算 | 调大 `--budget`，或把清单拆小 |
| 跑到一半 `exit 5` | 实扣比预估高（按秒档按实际时长结算） | 状态已落盘，调大预算后重跑接着跑 |
| 想先报价再决定 | — | `cost --file 清单 --concurrency 4`（0 点） |
| 预算余量怎么算的 | `--budget − 已花` | 已花取响应里的 `cost`，没有就用清单 `points` |

`--budget 0` 等于不授权任何调用：`run` 会直接退 5。

---

## 控制台 / 编码

| 现象 | 原因 | 处理 |
|---|---|---|
| `UnicodeEncodeError: 'gbk' codec` | Windows 重定向时按 cp936 输出 | 本包已 `reconfigure(errors="replace")`；仍个别乱码就 `set PYTHONIOENCODING=utf-8` |
| 输出的 `√` / `×` 变 `?` | GBK 控制台里这两个符号可用，个别符号（`─`）会降级 | 不影响退出码；管道里看 JSON 用 `--json` |
| 进度和结果混在一起 | 进度走 stderr | 要机器可读就加 `--json`，stdout 只有一个文档 |

---

## 自己证明「这轮花了多少」

```bash
# 跑前
curl -s -H "Authorization: Bearer $A7W_API_KEY" \
  "https://api.a7w.cn/user/balance/logs?limit=1"
# 跑后
curl -s -H "Authorization: Bearer $A7W_API_KEY" \
  "https://api.a7w.cn/user/balance/logs?limit=1"
```

两次最近一笔的 `at` 与 `points` 完全一致 → 期间没有任何冻结或扣费。`doctor` 就是自动做这件事：
9 项检查里有一项专门叫「本轮 0 点（跑后最近一笔与跑前相同）」。

---

## 调参与容量

| 场景 | 建议 |
|---|---|
| 首次放量 | `--concurrency 2 --retry 2`，跑 20 条看成功率再放 |
| 按秒档任务多 | 并发 4 足够；瓶颈在单条出片时长，不在并发 |
| 图生图 / 出图 | 并发可以到 8；先看 `429` 有没有出现 |
| 音频接口 | 单价按上游结算，清单里 `points` 给足，避免跑中触预算 |
| 超大批次（>5,000 条） | 拆成多个清单、共用一份 `--state` 目录，按天归档报告 |

---

## 还搞不定

先收集三样：`doctor` 全量输出、`status --file 清单`、失败那一条的 `id` 与报错原文。
然后到 SKILL.md 末尾「联系我们」。
