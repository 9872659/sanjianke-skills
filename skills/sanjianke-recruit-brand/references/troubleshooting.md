# 排错：按报错找原因

先跑 `python3 scripts/run.py doctor`。9 个请求全部 0 点，红了哪一条就照下表对。

---

## 一、Key 与权限

| 现象 | 原因 | 处理 |
|---|---|---|
| `失败：没有 API Key。三选一…`，退 `2` | 三条来源都没取到 | `--key` / `export A7W_API_KEY=sk-…` / `python3 scripts/a7w.py login --key sk-…` |
| `HTTP 401` | Key 无效或少字符 | 重新 `login --key`；`~/.a7w/config.json` 里的 `key` 字段也检查一下 |
| `HTTP 402`，报错里有本次所需点数 | 点数不够 | 到 [api.a7w.cn](https://api.a7w.cn/) 充值；先 `cost` 看要多少点 |
| 余额显示 999,997,393,470 点 | 平台用户 / Key 级余额口径，不是「你真有钱」 | 以 `/api/v1/me/billing` 的 `netConsumedPoints` 为准（`sanjianke-billing` 包能摊开） |

---

## 二、两道闸门（这两个不是报错，是设计）

| 退出码 | 提示 | 意思 | 怎么过 |
|---|---|---|---|
| `4` | `这会真实扣费约 N 点（X.XX 元）：…确认请加 --yes。` | 少了 `--yes` | 加 `--yes`；想先看不花钱的请求加 `--dry-run` |
| `5` | `预计 N 点（X.XX 元）超过 --budget M 点…一个请求都没发。` | 预算不够 | 调大 `--budget`（单位是点，1 元 = 100 点），或缩短秒数 / 降到 480P |

`--budget 100` 配 `avatar --seconds 30`（450 点）一定退 5，这是对的：**预算闸门在发请求之前就拦下**。

---

## 三、数字人 `avatar`

| 现象 | 原因 | 处理 |
|---|---|---|
| `text 模式要一条参考音色音频` | text 模式 `audio_url` 也是必填 | 先 `voice --clone` 建企业音色，再 `voice --text` 出一条音频，把它当 `--voice-url` |
| `请提供 image_url` | 人像没传或上传失败 | 给 `--image 本地路径`（自动 upload）或平台地址 |
| 任务一直 `processing` | 上游排队 | 正常水位 1~6 分钟，用 `status` 反复查（0 点） |
| 口型对不上 / 脸糊 | 图片侧脸、太小、多人 | 换正脸、单人、脸部占画面 1/3 以上的图 |
| 提交成功但扣了比预估更多的点 | 按**上游实际音频时长**结算，`--seconds` 只是预估 | 以返回里的 `usage.points_cost` 为准；脚本里的 `--seconds` 往宽了给 |
| 钱包短暂少了 250 点又回来 | `reserve_sync` 先冻结再结算 | 正常，看 `GET /user/balance/logs` 的净额 |

---

## 四、空镜 `film`

| 现象 | 原因 | 处理 |
|---|---|---|
| `400 url_not_allowed` | 首帧图不在白名单 | 给本地路径（`film` 自动 upload），或 `https://oss.gpu.likeadmin.cn/openapi/…`、`https://vr.a7w.cn/…`、`https://cdn2.jiujiushuyuan.cn/vr/…` |
| `full_video 单段 4~15 秒；N 秒分 X+Y 两段提交` | 超过单段上限 | 按提示拆两段，各自 `film`，合成时接上 |
| `秒数越界`、退 `2` | `--seconds` 小于 4 或大于 15 | 改到 4~15 |
| 成片没扣费但任务失败 | 任务失败全额退 | `status` 看 `refund` 字段；重提一次即可 |

---

## 五、出图 `cover`

| 现象 | 原因 | 处理 |
|---|---|---|
| `422 prompt: String should have at least 1 character` | 提示词为空（这其实是 `doctor` 的预期返回） | `cover` 的 prompt 由 `plan` 生成，用 `--kind` 选图种 |
| 返回里没有 `data` 数组 | `n` 越界或参数不合规 | `--n` 取 1~4 |
| 拿到的是 `b64_json` 不是链接 | 返回默认为 b64 | 本包自动解码落盘，文件在 `~/.a7w/recruit/out/` |
| 链接 3 小时后失效 | 图片链接短期有效 | 出图后立刻下载 / 转存 |

---

## 六、配乐 `music`

| 现象 | 原因 | 处理 |
|---|---|---|
| 只回了 `task_id` 没有音频 | 上游异步 | `status --task-id` 查（0 点） |
| 扣的点比 50 多 | 通配口径：上游 x2，50 点只是下限 | 以 `usage.points_cost` 为准，`cost` 里给的 50 是保底 |

---

## 七、查任务 `status`

| 现象 | 原因 | 处理 |
|---|---|---|
| `状态：not_found`，`说明：任务不存在` | 通用 `GET /api/v1/tasks/<id>` 看不到应用层任务 | 加 `--app pic_lipsync --yes` 走应用自己的 `/query`；这条口径在价目表里与 submit 同 path，先确认再发 |
| `查询失败（HTTP 404）` | taskId 写错 | 从提交返回里复制，别手打 |
| 反复查会不会花钱 | 不会 | `GET /api/v1/tasks/<id>` 价目表 `cost:0` |

---

## 八、合规检查 `qc` 不过

`qc` 退 `3` 时会逐条列出「要改的地方」，按这条改：

| 检查项 | 报什么 | 怎么改 |
|---|---|---|
| 歧视性限定 | `限男、年龄、25-35、已婚、已育` | 换成能力描述：「能独立负责一条业务线」「3 年以上服务端经验，能主导一次完整上线」 |
| 正向表述 | `岗位要求没写成「能做什么」` | 用 `负责 / 独立 / 熟悉 / 掌握 / 精通 / 参与 / 具备` 开头 |
| 夸大与承诺 | `急招、高薪诚聘、包进` | 换成可核对数字：团队 18 人、平均 2.5 年、11 月 30 日截止 |
| 负面表述 | `吃苦耐劳、抗压能力强` | 换成机制描述：导师带教、双周复盘、晋升窗口每年两次 |
| 薪资口径 | `没看到薪资区间` | 写 `15-25K·14薪`，「薪资面议」这类写法换掉 |
| 招聘主体 | `公司全称没进文案` | `--company` 给全称，比对公司官网写法 |
| 岗位事实 | `没看到工作地点` | `--city` 给城市，或文案里写园区 / 地铁站 |
| 成长路径 | `没看到成长路径` | 给 `--level` / `--next` / `--program`，或文案里写「导师一对一带教」 |
| 投递方式 | `没看到投递方式` | `--apply` 给邮箱 / 网申入口，`--deadline` 给截止日期 |
| 平台规格 | `单条 N 秒超过 X 的 Y 秒` | 改 `--seconds`，或换 `--platform`（小红书 90 秒、校招官网 120 秒） |

---

## 九、Windows 控制台中文（GBK）

**症状**：管道 / 重定向时 `UnicodeEncodeError: 'gbk' codec can't encode character '\u221a'`。

**本包的处理**（`scripts/run.py` 顶部）：

```python
sys.dont_write_bytecode = True
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # 中文控制台不因个别符号崩掉
    except Exception:
        pass
```

再叠一条：输出里的对勾用 `√`（U+221A）、叉用 `×`（U+00D7），这两个字符 cp936 里有；
金额一律写「元」或全角 `￥`（cp936 里半角那个符号宽度会错位，表格会对不齐）。

**实测**：

```
$env:PYTHONIOENCODING="gbk"
python -u scripts\run.py doctor > out.txt 2>&1
exit = 0        # 1,701 字节，cp936 解码后 √ × · 「」 全部可读
```

---

## 十、`--max-tokens` / `--json` / `--budget` 写在子命令前后

三种写法等价：

```bash
python3 scripts/run.py --json cost --track social
python3 scripts/run.py cost --json --track social
python3 scripts/run.py cost --track social --json
```

子命令上的全局选项用 `default=argparse.SUPPRESS`，没写就不覆盖父级的值。
副作用：`--json` 只在**真出错**时给 JSON；`--help` 永远是纯文本（退出码 0）。

---

## 十一、选项缩写

```bash
python3 scripts/run.py catal          # 退 2：allow_abbrev=False，不认缩写
python3 scripts/run.py cover --kin all # 退 2：--kin 也不认
```

父 parser 和**每一个**子 parser 都加了 `allow_abbrev=False`（只加父级无效，实测）。
写成完整名字即可：`catalog`、`--kind`。
