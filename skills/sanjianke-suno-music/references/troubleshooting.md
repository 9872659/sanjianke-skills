# 排错 · 按报错找原因

> 先记住这件事：这个网关**参数校验失败也回 HTTP 200**。
> 看 `{"code":0,"msg":"…","data":null}` 里的 `msg`，不要只看状态码。

---

## 1. 一眼定位

| `msg` 里出现 | 含义 | 怎么处理 |
|---|---|---|
| `input.xxx: 缺少必填参数` | 少了 `xxx` | 报错点名的字段就是必填项，按名字补 |
| `input.model: 不在允许选项内` | 模型名不在枚举 | `run.py catalog` 看枚举；`music_generate`/`music_extend` 用 `V6`/`V6_MINI`/`V6_WILD`，`music_sounds` 用 `V5`/`V5_5`/`V6` 系 |
| `input.xxx: 类型不正确` | 传了错的 JSON 类型 | 布尔传 `true`/`false`，数字别加引号 |
| `input.xxx: 数值超出范围` | 超出 schema 的 min/max | 见下表 |
| `input.xxx: 不在允许选项内`（非 model） | 枚举值写错 | 例如 `sound_key` 只有 24 个调性 + `Any` |
| `请使用本平台返回的任务或资源标识` | `audio_id` 不是本平台产出的 | 用 `song` / `extend` 打出来的 `audio_id`；手写的假 id 会被拦 |
| `音色操作步骤无效` | `action` 不是 `prepare` / `create` | 音色是两步：先 `prepare` 拿短句，录完再 `create` |
| `任务不存在` | `task_id` 不存在或已被清理 | `run.py log` 查台账里记的 `task_id` |

### 常见数值边界

| 字段 | 范围 |
|---|---|
| `duration` | 10–360（秒） |
| `variety` | 0–4（整数） |
| `sound_tempo` | 1–300 |
| `style_weight` / `audio_weight` / `weirdness_constraint` | 0–1，两位小数 |
| `vocal_end − vocal_start`（Persona） | 10–30 秒 |

---

## 2. 音效接口的特殊坑：`sound_tempo`

```
POST music_sounds {"model":"V6","prompt":"probe","sound_key":"Zzz"}
→ input.sound_tempo: 类型不正确；input.sound_key: 不在允许选项内
```

只给了另外两个字段时，`sound_tempo` 也会报「类型不正确」——**省略它就等于失败**。
所以本包 `sound` 永远显式传 `--tempo`（默认 120）。schema 里写的「不传就是 Auto」在这个网关上走不通。

---

## 3. 生成音乐的两个隐藏前提

schema 原文写了两条「至少一项」，但网关的**参数校验阶段不会拦**（实测只报我故意写错的字段）。
也就是说这类请求可能提交成功、在上游失败 —— 本包因此在本地先拦：

| 模式 | 至少要给 |
|---|---|
| `--custom`（`custom_mode=true`） | `--style` / `--lyrics` / `--negative-tags` 之一，**外加 `--title`** |
| 灵感模式（`custom_mode=false`） | `--prompt` / `--style` / `--lyrics` 之一 |

`extend --instrumental` 同理：schema 明确「为真时禁止传 `lyrics` / `prompt` / `vocal_gender`」，
本包在本地直接退 `2`。

---

## 4. 调用类错误

| 现象 | 原因 | 处理 |
|---|---|---|
| `HTTP 401` | Key 无效 / 过期 | 重新 `python3 scripts/a7w.py login --key …` |
| `HTTP 402` 或 `点数不足` | 余额不够 | 到 https://api.a7w.cn/ 充值 |
| `连不上 …` | 网络 / 代理 | 确认能访问 `api.a7w.cn`；`doctor` 会先探一遍 |
| `返回不是 JSON` | 落到了别的路由或网关页 | 检查 `--host` 是否被改过；端点必须是 `/api/v1/apps/media_services_33/<code>` |
| `轮询超时` | 歌比预期慢 | **不要重新提交**（会再扣一次）；用 `task --task-id <id>` 接着取 |

### 轮询超时的正确姿势

```bash
python3 scripts/run.py song --prompt "…" --yes --wait 900   # 等更久
# 或者先只提交
python3 scripts/run.py song --prompt "…" --no-wait --yes
python3 scripts/run.py task --task-id <task_id>             # 免费续查
```

`task` 是**只读 GET**，反复查不产生费用。

---

## 5. 结果与文件

| 现象 | 原因 | 处理 |
|---|---|---|
| 完成但打印不出音频 | 返回结构里没有能识别的 `audio_url` | 本包会原样打印 JSON；把这段贴出来即可定位 |
| 下载失败 | 链接过期 / 网络 | 用 `recover --task-id <id>` 再取一次，或直接 `--out` 重下 |
| 想事后找 `task_id` / `audio_id` | — | `run.py log`（本地台账 `~/.a7w/suno-ledger.json`） |
| `--out` 目录没有文件 | 任务还没完成 | 先 `task --task-id <id> --out ./suno` |

---

## 6. 退出码对照

| 码 | 含义 | 典型触发 |
|---|---|---|
| `0` | 成功 | — |
| `2` | 用法错 | 缺必填、`model` 不在枚举、数值越界、选项缩写 |
| `3` | `doctor` 有项目没过 | Key / 端点 / 任务查询异常 |
| `4` | 没有 `--yes` | 真实计费前的确认闸门 |
| `5` | 下限超 `--budget` | **一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 轮询超时 | 见上面各节 |
| `1` | 内部错误 | 带 traceback，把最后几行贴出来 |
| `130` | Ctrl-C 中断 | 已提交的任务用 `task` 续查 |

---

## 7. 自检

一条命令把 9 项检查跑完（全部零扣费）：

```bash
python3 scripts/run.py doctor
```

它只用两类请求：**只读 GET**（`/models`、`/apps/media_services_33`、`/tasks/<假id>`）和
**必然被参数校验拦下的 POST**（缺必填 / 假 `audio_id` / 非法枚举），不会创建任务。
