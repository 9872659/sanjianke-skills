# 排错：按报错找原因

先做这三件（都免费、都不扣费）：

```bash
python3 scripts/run.py doctor                     # Key / 7 个端点 / 价目表 / 查询路由 / 上传
python3 scripts/run.py run --file 老片.mp4 --dry-run   # 看会发出什么请求
python3 scripts/run.py resume --workdir oldfilm-work --dry-run   # 看还差几步
```

---

## 1. 按报错速查

| 你看到的 | 谁给的 | 原因 | 怎么修 |
|---|---|---|---|
| `失败：没有 API Key…` 退 `2` | 本包 | 三处都没配 | `--key` / `A7W_API_KEY` / `a7w.py login --key …` |
| `这会真实跑完整条流水线…` 退 `4` | 本包 | 缺 `--yes` | 确认后加 `--yes`；只想看请求加 `--dry-run` |
| `…超过 --budget N 点。一个请求都没发` 退 `5` | 本包 | 预估点数超预算 | 调大 `--budget`（单位「点」，1 元 = 100 点）或换更短的链 |
| `文件不存在：…` 退 `2` | 本包 | `--file` 路径不对 | 换成绝对路径，或先 `upload --file` 拿地址 |
| `--steps 里有不认识的工序` 退 `2` | 本包 | 工序名拼错 | 用 `catalog` 里的 7 个名字 |
| `--preset 只能是…` 退 `2` | 本包 | 预设名拼错 | `quick / standard / repair / portrait / cinema` |
| `提交失败（HTTP 400）… url_not_allowed` | 上游 | 地址不在白名单，本地预检被 `--allow-any-url` 跳过了 | 去掉 `--allow-any-url`，先 `upload` |
| `提交失败（HTTP 400）… empty_url` | 上游 | `videoUrl` 是空串 | 检查 `state.json` 里上一步的 `resultUrl` / `feedUrl` |
| `提交失败（HTTP 404）… unknown_tool` | 上游 | 路径拼错（`restore` 打成 viapi 版） | 本包已按实测表固定路径，`catalog` 可核对 |
| `提交失败（HTTP 402）… 点数不足` | 上游 | 余额不够预冻结 | 到 [api.a7w.cn](https://api.a7w.cn/) 充值 |
| `提交失败（HTTP 401）` | 上游 | Key 无效或过期 | 重新创建 Key 再 `login` |
| `任务 … 查不到（查询路由说 not_found）` 退 `6` | 本包 | taskId 抄错 / 不是这条线的任务 | 核对 `state.json` 里的 `taskId` |
| `等了 N 秒还没完成…` 退 `6` | 本包 | 超过 `--wait` | `resume` 接着等（**只查不重提**），或 `--wait 3600` |
| `查询失败（HTTP 502/503/504）` | 网关 | 抖动 | 本包已退避重试 3 次；再跑一次 `resume` 即可 |
| `连不上 … WinError 10054` | 网络 | 网关重置了空闲连接 | 同上；本包已重试，长任务建议 `--every 30` |
| `下载回来的是一张网页，不是视频` | 本包 | 成片链接过期或要鉴权 | 用 `status --task-id … --tier …` 重新取链接 |
| `任务 (x) 报 failed：…` 退 `6` | 上游 | 这一步失败 | **别重提**：`resume` 会再查一次（免费），平台会自动重试 |

---

## 2. 四个最容易白花钱的误解

### 误解一：`GET /api/v1/tasks/<id>` 能查这条线的任务

```
GET /api/v1/tasks/<id>  → 200 {"code":0,"msg":"任务不存在","data":null}
```

视频后处理任务不在里面。真正的视图是
`GET /api/v1/video/viapi/result/<id>`（6 档）和 `GET /api/v1/video/restore/<id>`（修复）。
两个都免费，且同源。

### 误解二：看到 `failed` 就重新提交

上游会**自动重试**：同一个 taskId 可能先 `failed` + `refund`，几分钟后回到 `processing`
再走到 `completed`。重新提交等于再付一次钱。正确做法是：

```bash
python3 scripts/run.py status --task-id task_xxx --tier superres   # 只查，免费
python3 scripts/run.py resume --workdir oldfilm-work               # 只查不重提
```

`resume` 的判断很简单：`state.json` 里有 `taskId` 就只查，没有才提交。

### 误解三：上一步的成片链接能直接喂给下一步

多数时候能（本站链接在白名单内），但外部签发的链接会被 400 `url_not_allowed` 挡回来。
本包的处理是「先落盘、再看链接」：链接不在白名单就 `POST /api/v1/upload` 换一个，
上传免费。`--reupload` 可以强制每步都换。

### 误解四：流水线断了＝钱白花了

已经 `completed` 的步产物在 `oldfilm-work/` 里，`state.json` 里有点数与链接；
`resume` 从第一个没完成的步接着跑，**已完成的步不重跑**。

---

## 3. 按阶段排查

### 提交前

- `doctor` 有一条红：先解决那一条，别的都会跟着好；
- `--budget` 不够：`cost --seconds <片长>` 看真实价，`--budget` 单位是「点」；
- 时长读错：`--seconds 600` 显式给，`plan` 会打印「时长来源」。

### 提交时

- `400 empty_url`：`videoUrl` 空 → 上一个产物没拿到；
- `400 url_not_allowed`：域名不对 → 先 `upload`；
- `404 unknown_tool`：路径错 → `restore` 走扁平，其余走 viapi；
- `402`：余额不足 → 充值。

### 等待时

- 状态一直是 `processing`：给 `--wait` 调大，或用 `resume` 分次等；
- 状态跳 `failed` 又回 `processing`：这是自动重试，等它走完。

### 完成后

- 成片链接约 **30 分钟**有效，及时转存（本包默认已经落盘到 `oldfilm-work/`）；
- 实扣与预估不一致：按秒档按**实际时长**结算，`state.json` 里每步都有 `points`；
- 想看总账：`python3 scripts/run.py log`。

---

## 4. 核对自己这轮花了多少

```bash
# 余额（免费）
curl -H "Authorization: Bearer $A7W_API_KEY" https://api.a7w.cn/api/v1/user/balance

# 流水（免费）—— 路径里没有 /api/v1
curl -H "Authorization: Bearer $A7W_API_KEY" "https://api.a7w.cn/user/balance/logs?limit=20"
```

带 `/api/v1` 打 `/api/v1/user/balance/logs` 会命中余额路由，返回的还是余额对象，
`logs` 字段永远为空 —— 这是实测踩过的坑。
