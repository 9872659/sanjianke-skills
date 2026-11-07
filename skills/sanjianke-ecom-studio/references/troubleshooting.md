# 排错：按报错找原因

先跑一遍免费自检，八成的配置问题一眼就能看出来：

```bash
python3 scripts/run.py doctor
```

`doctor` 只读 `/models`、`/apps`、`/pricing`，再发一次 `prompt=""` 的 422 探针，
**0 建单、0 扣费**。

---

## 命令层的报错

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `失败：没有 API Key。三选一…`（退出 2） | 三种来源都没配 | `--key` / `A7W_API_KEY` / `python3 scripts/a7w.py login --key sk-xxx` |
| `失败：必须给 --model-url`（退出 2） | `dress` / `batch` 缺模特图 | 给一个 http(s) 链接，别给本地路径 |
| `失败：必须给至少一个 --garment`（退出 2） | 没有服装图 | `--garment upper=URL`；套装就再来一条 `--garment bottom=URL` |
| `失败：--garment 的服装图必须是 http(s) 链接`（退出 2） | 传了本地文件路径 | 先上传拿到 URL，或换成公网可访问的图床链接 |
| `失败：换装要真实扣约 200 点…确认请加 --yes`（退出 4） | 没给 `--yes` | 确认要花钱就加 `--yes`；想先看请求加 `--dry-run` |
| `失败：…预计 N 点，超过 --budget M 点`（退出 5） | 超预算 | 调大 `--budget`、减少张数；**这条不会发任何请求** |
| `run.py: error: unrecognized arguments: --dry`（退出 2） | 选项缩写 | 本包父子 parser 都关了缩写，写全 `--dry-run` |
| `失败：拒绝发送空 body`（退出 2） | 内部兜底触发了 | 说明某个必填没填到 body 里，检查 `--garment` / `--prompt` |

---

## 换装线（dressing_diffusion）

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 提交后 `task_id` 有了，但任务一直 `processing` | 上游排队或卡住 | `status <task_id>` 再查；本包 `--timeout`（默认 300 秒）到点会报出来并保留 task_id |
| 任务 `failed`，`error.code = missing_input` | 模特图或服装图取不到 / 打不开 | 换一个稳定可访问的 URL，别用带鉴权的私有链接 |
| 换装结果的脸和原模特差很多 | 换装只保证服装贴合，不保证人脸一致 | 模特图正脸、光线均匀、主体清晰的成功率更高 |
| 上下套装只换了上衣 | `garment.data` 里只给了一件 | 上衣 `{"category":"upper"}` + 裤子 `{"category":"bottom"}` 两条都给 |
| 服装图边缘糊成一团 | 平铺图背景太花 | 服装图用白底或纯色背景平铺，效果明显更稳 |

---

## 出图线（nano_banana）

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| `code: 0`「当前请求未命中可用计费规格」 | 普通模型配了非 1K 分辨率 | 普通 `nano-banana` 走 `1K`；2K/4K 换 `nano-banana-2:official` 之类 |
| `code: 0`「任务不存在或不属于当前租户」 | `task_id` 写错，或换了 Key | 用提交时那个 Key 和那条 task_id |
| `action=edit` 报参数错 | 没给参考图 | `--image https://…`（最多 12 张） |
| 出图很慢 | 1K 单张实测 5~30 秒，2K/4K 更久 | `--timeout` 给大一点；先用 `status` 看是不是还在 processing |
| 出图和提示词差很远 | 提示词里塞了太多互相冲突的要求 | 一次只讲一个主体 + 一个场景 + 一种光位；把「不要文字」写成「画面干净、无文字元素」 |
| 想更便宜 | 72 点/次是应用线价 | 改用 `--engine gpt`（6 点/张），或直接 `generate --engine gpt` |

---

## 主图线（gpt-image-2.6）

| 现象 / 报错 | 原因 | 怎么办 |
|---|---|---|
| 返回里没有 `data[0].url` | 默认返回 `b64_json` | 本包两种都处理，会直接落盘成文件 |
| HTTP 404 / 图片打不开 | 链接过期（约 3 小时）或追加了查询参数 | 原样用链接，别加参数；过期就重出 |
| HTTP 422「String should have at least 1 character」 | `prompt` 是空串 | 这就是 `doctor` 的探针形态，正常；真出图要给 `--prompt` |
| 传了不存在的模型名也出图了 | 端点少写 `/api` 前缀，被路由到网关默认应用 | 用 `https://api.a7w.cn/api/v1/images/generations`，`doctor` 会验这条 |
| `n` 传 5 报错 | 文档限 1–4 | 分两批出 |
| 尺寸报错 | 自定义尺寸有硬约束 | 宽高 16 的倍数、长短边 ≤3:1、单边 ≤3840、总像素 655,360–8,294,400 |

---

## 任务与轮询

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `status` 报「任务不存在」 | task_id 不对，或不属于当前 Key | 用提交时的 Key 查 |
| 轮询到超时 | `--timeout` 太短 | 调大；`task_id` 不会丢，`status <id>` 随时能接着查 |
| 想省着查 | — | `GET /api/v1/tasks/<id>` 免费；**别用 `apps/<app>/query`**，价格表里它会命中 `<app>/*`（200 / 72 点） |

---

## 账目对不上

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 报价 224 点，实际扣得不一样 | 换装按次、gpt 按**实际返回张数** | 以 `usage.points_cost` 为准；`log` 里记着每笔的 `billedPoints` |
| 任务失败了还扣钱 | 失败会按平台规则退回，退回有时滞后 | 过几分钟看 `/user/balance/logs`；`refund:task_failed:<task_id>` 就是退款流水 |
| 只读了一次 schema 就少了 200 / 72 点 | `GET /api/v1/apps/<app>` 按该应用单价计费 | 免费看能力用 `GET /api/v1/apps`（`cost: 0`），本包 `doctor` 已经这么做了 |
| 想复盘每一笔 | — | `python3 scripts/run.py log --limit 50`，台账在 `~/.a7w/ecom-studio-ledger.json` |

---

## 环境

| 现象 | 原因 | 怎么办 |
|---|---|---|
| Windows 控制台中文乱码 | 代码页不是 UTF-8 | `chcp 65001`，或设 `PYTHONIOENCODING=utf-8` |
| 跑一次多出 `__pycache__` | 没关字节码 | 命令前加 `PYTHONDONTWRITEBYTECODE=1` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | 系统证书链不全 | 换 Python 3.9+，或给 `SSL_CERT_FILE` 指一份 ca 证书 |
| 公司网络连不上 | 出站被拦 | 确认能访问 `https://api.a7w.cn`；`doctor` 第一步就会暴露这个问题 |

**收集排错信息时请附上**：完整命令、`--json` 的输出、原始报错文本。
**报错截图与日志里请不要带 API Key。**
