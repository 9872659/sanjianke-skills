# 排错：按返回找原因

先记住一条：**这 8 条接口的参数校验失败也回 HTTP 200。**
所以看到 200 别急着高兴，先看 `code` 是不是 `1`、`msg` 是不是 `success`。

```json
{"code":1,"msg":"success","data":{…}}          <- 成功
{"code":0,"msg":"input.xxx: …","data":null}    <- 没建单，钱包退回来了
```

---

## 一、按 `msg` 原文对号

| 返回原文 | 真实原因 | 怎么改 |
|---|---|---|
| `input.voice: 不在允许选项内` | `voice` 传了名字或别的 ID | `voice` 要 67 个 20 位 ID 之一；`voices --line v2` 列全表，`--voice James` 本包会自动换 ID |
| `input.dialogue: 类型不正确` | `dialogue` 传了字符串 | 必须是数组：`[{"text":"…","voice":"<ID>"}]`，用 `dialogue` 子命令 |
| `input.text: 缺少必填参数` | 没给 `text` | `speak --text "…"` 或 `--text-file` |
| `input.audio_id: 缺少必填参数` / `input.name: 缺少必填参数` | `design` 少了必填 | `design --name "…" --audio-id achernar` |
| `input.image_urls: 缺少必填参数` / `input.descriptions: 缺少必填参数` | `character` 少了必填 | `character --image-url https://… --description "…"` |
| `input.model: 不在允许选项内` | 这不是本包的接口（那是 Suno 音乐线） | 音乐去 `sanjianke-suno-music` |
| `服务内部错误`（HTTP 500） | Gemini 三条线的参数类型没通过，或上游临时抽风 | 先 `--dry-run` 看请求体：`speakers` / `dialogue_turns` 必须是数组；重试一次 |

### `服务内部错误` 到底会不会扣钱

不会。流水是「`reserve_sync` 冻 60 → `refund:sync_error` 退 60」，净 0：

```
20:57:07  charge  -60  reserve_sync:/api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
20:57:11  refund  +60  refund:sync_error:/api/v1/apps/media_services_33/google_gemini_3_8_flash_tts
```

但**别拿它当免费试探**：正常请求在 500 之前没人保证不往下走。想先看请求体就用 `--dry-run`。

---

## 二、本包自己拦下来的（不会发请求）

这几条是本地预检，报错时**一个请求都没发**，不冻不扣：

| 报错 | 原因 |
|---|---|
| `找不到音色「xxx」` | `--voice` 既不是 ID 也不匹配任何名字 |
| `「xxx」不在这条线的音色表里` | `--cast` 用了另一条线的音色名（3.8 有 70 个、2.5 Pro 只有 30 个） |
| `这条线的单次上限是 5000 字符` | `v2` / `turbo` 的 `text` 上限；`v3` 是所有台词加起来 |
| `对话总字符 N 超过 5000 上限` | `v3` 逐句相加超限 |
| `这些角色还没分音色` | `--voices` / `--cast` 漏了某个角色 |
| `--style-turn 只用于 3.8 两条线` | 2.5 Pro 用 `--emotion`（六种固定风格） |
| `强制语言只有 turbo 支持` | `v2` 传 `--language-code` 会被上游打回，本地先拦 |
| `参考图最多 2 张` | `character` 的 `image_urls` 是 `minItems:1 / maxItems:2` |

---

## 三、闸门与退出码

| 退出码 | 场景 | 说明 |
|---|---|---|
| `4` | 没给 `--yes` | stderr 会写「这会真实建单，先预冻结约 60 点」；加 `--yes` |
| `5` | `60 > --budget` | **一个请求都不发**；调大 `--budget`（单位是点） |
| `2` | 用法错 | 缺参数、选项缩写、文件不存在 |
| `6` | 调用失败 | 上面 `msg` 表里的情况，或网络断 |
| `3` | `doctor` 出现 `×` | 逐行看哪条没过 |
| `130` | Ctrl-C | — |

---

## 四、编码

Windows 控制台默认 cp936。包里已经做了兜底（`reconfigure(errors="replace")`），
`PYTHONIOENCODING=gbk python run.py doctor` 实测 **exit=0**，不会因为符号崩掉。

要输出到文件再读，建议显式指定：

```powershell
$env:PYTHONIOENCODING="utf-8"; python run.py doctor | Out-File -Encoding utf8 doctor.txt
```

剧本文件必须是 **UTF-8**（不是 GBK、不是带 BOM 的 ANSI），否则中文台词会读成乱码。

---

## 五、查不到任务

```json
GET /api/v1/tasks/task_xxx  ->  {"code":0,"msg":"任务不存在","data":null}
```

- 刚提交就查，等 2 秒再试；
- 任务号要连 `task_` 前缀一起复制，别只拷后半段；
- 通用 `/api/v1/tasks/<id>` 只服务模型与应用任务；本包这 8 条都属于应用任务，走它是对的。

---

## 六、别踩的坑

| 别做 | 为什么 |
|---|---|
| `GET /api/v1/apps/media_services_33` | 命中 `/apps/<app>/*` 通配计价，`sync:` 即时扣、**不退**（2026-11-07 实测此坑烧掉 472 点） |
| 把 `--budget` 当「元」填 | 单位是**点**，1 元 = 100 点；填 10 其实是 0.1 元 |
| 用 `voice` 名字直接打接口 | 上游要 ID；用本包的 `--voice James` 或 `voices --line v2` 拿 ID |
| 拿 `data` 里没有就判定失败 | 成功结构还没被公开文档固定；先看 `speak` 打出的原始返回，再用 `task` 追 |
