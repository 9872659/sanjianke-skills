# 医疗合规素材 —— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、不扣费，10 个请求能排掉一半问题。

---

## 一、Key 相关

### `失败：没有 API Key`（exit 2）

三处都没读到。按优先级检查：

1. `--key sk-...`
2. `echo $env:A7W_API_KEY`（PowerShell） / `echo $A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `HTTP 401`

Key 本身的问题。去 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

---

## 二、合规闸门（exit 2）

### `合规闸门拦下（出图 prompt，16 字）：这次一个请求都没发`

这是本包的设计：命中一票否决就不许花钱。

```
失败：合规闸门拦下（出图 prompt，16 字）：这次一个请求都没发。
  · 疗效承诺：一次见效 → 改成「按疗程评估，效果因人而异」
  · 术前术后 / 前后对比：术前、术后 → 换成「项目过程 / 器械 / 环境」的画面
  · AI 素材作疗效示意：效果示意 → AI 图只做场景 / 器械 / 环境示意
```

**怎么改**：

1. 把结论换成过程：「水光项目，单次 40 分钟，含麻醉与复诊」比「一次见效」安全且更有信息量；
2. 把对比换成场景：术前术后图留给面诊室，广告里放器械、诊室、操作台；
3. AI 图明确标注，并且画面本身不出现人脸特写、皮肤前后状态。

### `check` 说必标项缺 N 项，但我想先出片

缺必标项**只提示、不拦**（`--strict` 才拦）。片子可以先出，发布前把 6 项补齐：

```bash
python3 scripts/run.py checklist   # 必标模板，直接抄
```

### `待改写` 是什么意思

6 类「说了容易被盯上但不必然违法」的表述：低价引流、代言背书、疾病药品、进口资质、名词炒作、分期诱导。打印替代写法后继续跑，不会拦。

---

## 三、两道闸门

### `失败：这会真实扣费约 6 点（0.06 元）`（exit 4）

缺 `--yes`。**故意的**：出片要花钱，必须显式确认。

```bash
python3 scripts/run.py image --prompt "…" --dry-run     # 只看请求
```

### `失败：预计 24 点（0.24 元）超过 --budget 1 点`（exit 5）

**一个请求都没发。** 调大 `--budget`（单位是**点**，1 元 = 100 点）或减少张数/秒数。

---

## 四、出图

### `422 prompt: String should have at least 1 character`

`--prompt` 空了。这条同时是 `doctor` 验端点的方式：带 `model` + 空 prompt 拿到 422，说明路由正确且不扣费。

### `400 … size …`

自定义尺寸要同时满足：宽高 16 的倍数、长边/短边 ≤ 3:1、单边 ≤ 3840、总像素 655,360–8,294,400。本包默认 `1024x1536`，合规。

### 出图成功但扣了 72 点而不是 6 点

端点写错了。`/v1/images/generations`（少了 `/api`）会忽略 `model`，落到网关默认应用 `nano_banana`（72 点/次），而且不报错。本包固定用 `/api/v1/images/generations`。

### 拿到了 `url`，自己下载 403

`urllib` 必须自设 `User-Agent`。本包下载时已带 `UA`，直接落盘成文件。

### 链接 404

两个原因：超过约 3 小时；或者给链接追加了查询参数（原样使用）。

---

## 五、上传与地址白名单

### `400 url_not_allowed`

`image_url` / `audio_url` / `videoUrl` 只收三类地址：

- `*.a7w.cn`（含 `vr.a7w.cn`）
- `cdn2.jiujiushuyuan.cn/vr/`
- `oss.gpu.likeadmin.cn/openapi/`（`POST /api/v1/upload` 返回的）

本包在本地就拦，报错里会写清归属。本地文件直接给路径，`lipsync` / `video` 会自动先上传（免费）。

### `上传失败（HTTP …）`

单文件 512 MB 内；字段名固定 `file`；`--timeout` 默认 600 秒，大文件可调大。

---

## 六、配音 / 口播 / 成片

### `配音失败（HTTP 200）` 但响应里没有音频

看返回体：可能是内容审核拦了（一般带说明、不扣费），也可能结构变了。用 `--json` 看完整字段。

### `这条 520 字，单条落到 500 字内`

`voice_tts/tts` 是同步接口，按段落拆两条，或换 `tts_async`（长文本异步）。

### 口播提交成功但 `status` 查不到

`GET /api/v1/tasks/<id>` 对应用层任务可能返回「任务不存在」（这是正常返回，0 点）。要确认时：

```bash
python3 scripts/run.py status --task-id tsk_xxx --app pic_lipsync --yes
```

应用层 `/query` 的计价口径与 submit 同 path，所以才要 `--yes`。

### 口播成片只有 480x832

实测输出就是这个规格（24fps）。剪辑时放大到 1080x1920，注意别把字幕压在安全区外。

### `400 empty_url` / `pixverse_empty_url`

视频线在参数校验就停 —— 说明端点活着，只是没给视频地址。这是 `doctor` 期望的结果，不是故障。

### 成片单段超 15 秒

`full_video` 单段 4–15 秒。30 秒的片子按 15+15 或 10+10+10 拆，每段一次提交、各自计费。

---

## 七、为什么会「冻结了又退回来」

`/submit` 这类应用层接口是 `reserve_sync` 口径：先按预估价冻结点数，再参数校验，失败就全额退。净额 0，但钱包被短暂动过。

所以本包 `doctor` **一条应用层 submit 都不发**，估时直接按价目算。看到 `reserve_sync: …` 与 `refund:submit_failed: …` 成对出现，就是这条路。

---

## 八、中文乱码

### Windows 控制台输出 `?` 或直接崩 `UnicodeEncodeError`

`run.py` 已经做了兜底（`reconfigure(errors="replace")`，并把符号换成 `√` / `×`，金额一律写「元」，不出现人民币符号）。仍然乱码时：

```powershell
$env:PYTHONIOENCODING="utf-8"
chcp 65001
python scripts/run.py doctor
```

`PYTHONIOENCODING=gbk` 也应 exit 0：本包输出里没有 cp936 编不出的字符。

### 生成的 `.md` / `.txt` 打开是乱码

本包写文件统一 UTF-8 + `\n`。用 VS Code、Typora、记事本（Win10 以上）都能直接打开。

---

## 九、钱与流水

### 怎么确认某一轮真的没花钱

```bash
python3 scripts/run.py doctor            # 第 12 项：本轮没有新增流水（扣 0 点）
```

`doctor` 在跑之前和跑之后各读一次 `/user/balance/logs?limit=1`，两次一致就是 0 点。

### 想自己核对

```bash
# 最近 5 笔流水（0 点）
curl -H "Authorization: Bearer $A7W_API_KEY" "https://api.a7w.cn/user/balance/logs?limit=5"
```

看 `type`（charge / refund / reserve_sync）、`points`、`reference`。`reference` 里的路径就是那笔钱花在哪。

### 实际扣费比预估多

不会超过预估价（出图 6×n、口播 15 点/秒、成片 单价×秒数）。比预估少是正常的：出图按实际返回张数、口播按实际时长结算。

---

## 十、合规口径 FAQ

### 广审文号长什么样

`（京）医广【2026】第 03-15-0123 号` —— 省级简称 + 医广 + 年份 + 序号。`check` 只验「有没有写」，具体号码要人工核对是否在有效期内、是否覆盖本片项目。

### 机构没有广审文号怎么办

医疗美容属于医疗广告，需要《医疗广告审查证明》。没有文号的内容只能走机构自有场地内的展示与到店沟通，对外投放平台会驳回。

### AI 生成的图能当环境图用吗

能，条件是三条：只做环境 / 器械 / 空间示意；画面角标标「AI 生成 · 场景示意，非真人案例」；交付单登记素材来源。人脸、皮肤前后状态不进 AI 图。

### 「效果因人而异」写在哪

片尾字幕一次（停留 3 秒以上）、发布文案一次（正文可见位置）。两处都要有。

### `check` 过了就一定能发吗

机检只覆盖可枚举的表述与必标项。人工复核 8 条（`checklist` 打印）仍然要走一遍并签字：肖像授权、医师资质、素材来源、价格范围、留档。

---

## 十一、还想更省事

```bash
python3 scripts/run.py check --file 口播稿.txt --asset video && \
python3 scripts/run.py doctor && \
python3 scripts/run.py image --prompt "…" --n 4 --yes
```

合规过了、自检过了，再花那 24 点。

---

## 十二、联系

加技术微信 见 SKILL.md「联系我们」 时说一下是从 `sanjianke-medical-compliance` 找过来的，
直接给你配套的 API Key 与能跑的示例。
