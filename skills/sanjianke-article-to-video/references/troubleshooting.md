# 排错：按报错找原因

> 先跑 `python3 scripts/run.py doctor`。8 个探针全绿还出问题，再往下按报错对号。
> 所有命令都建议带上 `$env:PYTHONIOENCODING="utf-8"`（Windows PowerShell）看清中文。

---

## 一、先看退出码

| 码 | 含义 | 先做什么 |
|---|---|---|
| `0` | 成功 | — |
| `2` | 用法错 | 看 stderr 那行「失败：…」，检查参数拼写与取值 |
| `3` | `doctor` 有项没过 | 看哪一行是 `×`，按下面第二~五节处理 |
| `4` | 缺 `--yes` | 确认金额后补 `--yes` |
| `5` | 超 `--budget` | **一个请求都没发**；调大 `--budget`（单位是点）或减 `--scenes` |
| `6` | 调用失败 | 看 `--json` 里的 `error.message`，对照下面 |
| `1` | 内部错 | 把 traceback 最后 5 行发出来 |
| `130` | 被 Ctrl-C | 直接重跑，已完成的镜头会跳过 |

`--budget` 单位是**点**，1 元 = 100 点。填 20 的意思是 20 点（0.2 元），不是 20 元。

---

## 二、Key 与权限

### `HTTP 401` / `{"code":0,"msg":"无效的 API Key"}`

- Key 没读到：`--key` → 环境变量 `A7W_API_KEY` → `~/.a7w/config.json`，按这个顺序找。
- Windows 上 `export` 不管用，用 `$env:A7W_API_KEY="sk-..."`。
- 最省事的写法：`python3 scripts/a7w.py login --key sk-你的key`。

### `HTTP 403` | `{"message":"Forbidden"}`

- 常见于**下载图片 / 音频**时没带 `User-Agent`。本包 `download` 已自带；
  你自己用 `urllib` 拉链接时加一个 `User-Agent` 就行。

### `{"code":0,"msg":"应用或 API 不可用或未配置价格"}`

- 这是应用层的**兜底话术**，不可信 —— 假的应用代号也返回同一句。
- 先用 `catalog` 确认应用在架：本包依赖 `full_video` / `voice_tts` / `nano_banana` /
  `media_services_33` 四个应用，目录里都应有。
- 再确认接口代号拼写：`music_generate`，不是 `music-generate`。

---

## 三、出图（gpt-image-2.6）

### `422 prompt: String should have at least 1 character`

- **这是 `doctor` 期望的结果**，代表端点与模型都对，不用处理。
- 如果你在 `image` 里看到它：说明某一镜的 `imagePrompt` 是空的。跑 `plan` 重生成分镜，
  或手工补 `storyboard.json` 里的 `imagePrompt`。

### `404` + HTML

- 打到 `/v1/images/generations`（少了 `/api`）会落到另一套旧路由，`model` 被静默忽略，
  还会按 `nano_banana` 的 72 点/次扣。确认 `--host` 是 `https://api.a7w.cn`，别手拼路径。

### `400 size ...` / `width/height must be multiples of 16`

- 自定义尺寸四条：16 的倍数、长短边比 ≤ 3:1、单边 ≤ 3840、总像素 655,360–8,294,400。
- 默认 `1536x1024` 满足全部四条，先用默认值跑通再调。

### 返回成功但没图

- 返回里既没有 `b64_json` 也没有 `url`：把整段 JSON 发出来。
- 内容审核拒绝也会返回错误并说明原因，这类**不扣费**，改提示词重试即可。

### 中文提示词出图偏题

- 画面提示词里少用抽象词（「氛围感」「故事感」），多用可拍的名词与光线（「雨后清晨」「侧逆光」）。
- `--style` 是全局风格词，会拼进每一镜，换风格改它一次就够。

---

## 四、出片（full_video）

### `400 url_not_allowed`

```
videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）
或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）
```

- `render` 会自动 `POST /api/v1/upload` 换地址，出现这个说明 `imageUrl` 被手工改过外站链接。
- 清掉 `storyboard.json` 里该镜的 `imageUrl` 字段，重跑 `render` 就会重新上传。

### `400 empty_url` / `duration must be between 4 and 15`

- `duration` 只吃 **4–15 的整数秒**。`--seconds 3` 或 `20` 都会被拒；
  本包在 `plan` / `render` 两处都做了夹取，手工改 JSON 时要自己守住这个区间。

### `400 当前请求未命中可用计费规格`

- `resolution` 拼错，或者用了不在 `480P/768P/1080P/2K/4K` 里的值。
- `ratio` 只认 `16:9 / 9:16 / 1:1 / 4:3 / 3:4 / adaptive`。

### 任务卡在 `pending` 很久

- 不是失败。`GET /api/v1/tasks/<id>` 是免费的，等就行；`render --wait 1800` 可以把等待上限拉长。
- 超时退出**不会**丢任务：`task --task-id <id>` 接着取，不要重新提交（会再扣一次）。
- 单条任务超过 30 分钟仍是 `pending`，把 `taskId` 发给技术微信看看。

### 任务 `failed` 且没有 `refund`

- 正常情况下失败会全额退回。先看返回里的 `refund` 字段；
  连续两次「失败但没退」再把 `taskId` 与流水截图一起发出来。

---

## 五、旁白（voice_tts）

### 念到一半断了 / 只出了前几句

- 同步 `tts` 建议单次 500 字以内；本包按 450 字切块，切成 `narration-01.mp3`、`narration-02.mp3`。
- 如果你手工把 `narration` 写得很长，`plan` 阶段就会被截到 `--narration-chars`（默认 30 字/镜）。

### 音频链接打不开

- 音频链接是临时地址，`download` 会立刻落盘到 `build/`；
  拿链接去别处用之前先确认还有效。

### 费用和预估差得多

---

## 六、配乐（media_services_33）

### `{"code":0,"msg":"缺少必填参数"}`

- `music_generate` 必填三个：`model` / `custom_mode` / `instrumental`。
- 本包固定传 `model: "V6"`、`custom_mode: false`、`instrumental: true`。
  想改成有人声，把 `instrumental` 传给 `false` 并补 `style` 与 `lyrics`。

### 只扣了 50 点，比预估高

- 看任务返回的 `usage` 或流水里的 `reference` 字段确认。

---

## 七、分镜与产物

### 切出来的镜头不像一条片子

- 规则是按 170 字一镜均匀抽样，句子的顺序被保留、中间的过渡句会被跳过。
- 想要更细：`--scenes 24`；想要更像预告片：`--scenes 8 --seconds 6`。
- 也可以手改 `storyboard.json` 的 `narration` / `imagePrompt`，再跑 `image --force`。

### 重跑 `image` 没反应

- 已出图的镜头会被跳过，这是设计如此。要推翻重做加 `--force`。

### `image` 报「找不到分镜文件」

- 默认路径是 `build/storyboard.json`。先跑 `plan --article ...`，
  或用 `--storyboard` 指到你自己的路径。

### 拼接后没有声音 / 音画不同步

- 检查 `concat.txt` 里的片段顺序与镜头号一致（`clip-01、clip-02…`）。
- 有配乐时用 `-filter_complex "[1:a][2:a]amix=inputs=2:duration=first[a]"`，
  `duration=first` 保证以旁白长度为准；漏了它，短的那一路会把整条拉短。
- `-c:v copy` 只搬流不重编码，速度快；要重编码就换成 `-c:v libx264 -crf 20`。

### ffmpeg 报 `Unknown encoder 'aac'`

- 换个 ffmpeg 构建（带 `aac` 的），或把 `-c:a aac` 改成 `-c:a libmp3lame -b:a 192k`。

---

## 八、环境与编码

### Windows 控制台中文变问号 / 报 `UnicodeEncodeError`

- `run.py` 已经 `sys.stdout.reconfigure(errors="replace")`，且输出里的对勾与叉号都用
  cp936 编得出的写法，GBK 控制台下不会崩。要看清楚中文，跑之前加：

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u scripts\run.py doctor
```

- 文件本身是 UTF-8；`plan` 读文章时依次试 `utf-8-sig` / `utf-8` / `gb18030`，
  老公众号导出的 GBK 文本也能读。

### `python` 不是内部或外部命令

- 用 `py -3 scripts/run.py ...`，或把 Python 加进 PATH。

### 跑一次多出 `__pycache__`

- 加 `$env:PYTHONDONTWRITEBYTECODE="1"`，或始终用 `python -B`。

### 提示「没有 API Key」

- `catalog` / `doctor` 及以上都要 Key；只有 `cost` / `plan` / `log` 是纯本地，能在没 Key 时跑。

---

## 九、看到这些数字先别慌

| 现象 | 解释 |
|---|---|
| 提交后余额少了 70 点，任务 `failed` 后又回来 70 点 | 预冻结 + 失败退款，净 0 |
| 流水的 `count` 一直在涨 | 别人也在用同一个 Key，或你在别处跑过 |
| `available_points` 是 9 位数 | 测试账号的历史余额，跟本轮花费无关 |
| `cost` 算 1,027 点，实际扣 1,031 点 | 旁白按上游真实点数结算，差几十分之一是正常的 |
