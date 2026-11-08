---
name: sanjianke-muse-video
slug: sanjianke-muse-video
displayName: muse video单条支持3分钟视频 0.11元一秒
description: "**单条最长 3 分钟（180 秒）的 720P 带声音视频，0.11 元一秒。** 走 api.a7w.cn 的 muse-video，接口与 OpenAI 视频接口一致，文字或图片进、带声音的 MP4 出。四件事本包替你挡住：①**按请求秒数计费**不是糊涂账，`cost --seconds 30` 先报 330 点、`--budget` 兜底；②**凑档不加钱** —— 填 17 秒出 20 秒只收 17 秒，本包会把这个差价标出来；③**等待可能 8–15 分钟**，所以默认不等完、只给你 task id，要等就 `--wait`；④**任务会自己跑完** —— 关终端、断网都不影响，随时回来取。遇到问题可加技术微信 9872659。"
version: 1.1.2
license: MIT
tags:
  - 三剪客
  - 视频生成
  - Muse-Video
  - api.a7w.cn
---

# muse video单条支持3分钟视频 0.11元一秒

> ## 先申请你自己的 API Key
>
> 本包不内嵌任何 Key，用的是**你自己**在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，
> 扣的是你自己账户的余额。注册、充值、创建 Key 都在 [api.a7w.cn](https://api.a7w.cn/)。
>
> ```bash
> python3 scripts/a7w.py login --key sk-你的key
> ```

## 3 分钟一条带声音的片子，19 块 8

| 秒数 | 价格 | 秒数 | 价格 |
|---|---|---|---|
| 4 秒 | 44 点（¥0.44）| 10 秒 | 110 点（¥1.10）|
| 5 秒 | **55 点（¥0.55）** | 30 秒 | 330 点（¥3.30）|
| 6 秒 | 66 点（¥0.66）| 60 秒 | 660 点（¥6.60）|
| 8 秒 | 88 点（¥0.88）| **180 秒** | **1,980 点（¥19.80）** |

**720P、带声音、MP4，单条 4–180 秒。**

## 三个别人不会告诉你的点

### 一、凑档不加钱 —— 白拿的 3 秒

填 7 秒出 8 秒、填 17 秒出 20 秒，**但只按你填的秒数收钱**。

```bash
$ python3 scripts/run.py cost --seconds 17
时长：17 秒 × 11 点 = 187 点 = ¥1.87
出片：约 20 秒（凑档不加钱，仍只收 17 秒）
```

**要准确时长就买整档**：5、6、8、10，以及 15–180 之间 5 的倍数。

### 二、片子会自己跑完，你回来取就行

任务**一旦创建就会一直跑到完成** —— 你可以关终端、断网、去干别的。
本包默认**提交完就返回 task id**，随时回来取：

```bash
python3 scripts/run.py wait task_xxxx --outdir .
```

要一次跑完就加 `--wait`。

### 三、出片自动下载到本地

`--wait` 成功就**立刻下载到本地**，同时打印线上链接与过期时间 —— 转存一步到位。

## 三步上手

```bash
# 1) 自检（不扣费）
python3 scripts/run.py doctor

# 2) 先算钱
python3 scripts/run.py cost --seconds 10

# 3) 出片
python3 scripts/run.py gen --prompt "金色的枫叶在微风中飘落，阳光穿过树梢，电影感" \
    --seconds 5 --yes --wait --outdir .
```

## 最常用的四条

```bash
# 竖屏 8 秒，本地图当首帧
python3 scripts/run.py gen --prompt "女孩在海边转身走向镜头，海风吹起头发" \
    --seconds 8 --size 720x1280 --first-frame girl.jpg --yes --wait

# 多图参考（第 1 张开头，其余当人物/场景/画风参考）
python3 scripts/run.py gen --prompt "镜头跟着人物走进森林小屋，人物照第二张图" \
    --seconds 10 --ref first-frame.jpg --ref character.jpg --yes

# 30 秒长片
python3 scripts/run.py gen --prompt "..." --seconds 30 --budget 400 --yes --wait

# 只看请求，不花钱
python3 scripts/run.py gen --prompt "..." --seconds 5 --dry-run
```

## 规格

| 项 | 值 |
|---|---|
| 提交 / 查询 | `POST /api/v1/videos` · `GET /api/v1/videos/{id}` |
| 输出 | **720P MP4，带声音** |
| 时长 | **4–180 秒**（＝ 3 分钟） |
| 尺寸 | `1280x720` 横（默认）/ `720x1280` 竖 |
| 价格 | **11 点/秒（¥0.11）**，按**请求**秒数计费 |
| 图片输入 | `--first-frame`（1 张＝首帧）或 `--ref`（最多 4 张，第 1 张＝开头画面） |
| 成品 | 出片后可直接下载转存 |

**图片输入**：单张 ≤10 MB、合计 ≤24 MB（本地文件本包自动转成 data URL）；PNG / JPEG / WebP 都行；首帧横竖和 `--size` 一致效果最好。

## 参数速查

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` | 必填 | ≤4000 字；写清**主体、怎么动、镜头怎么走** |
| `--seconds` | 5 | 4–180 整数；出片凑档，按填的收钱 |
| `--size` | `1280x720` | `1280x720` 横 / `720x1280` 竖 |
| `--first-frame` | — | 本地首帧图 |
| `--ref` | — | 参考图（URL 或本地路径，可重复，最多 4 张） |
| `--wait` | — | 提交后等到完成并下载 |
| `--budget` | 2000 | 点数上限（**单位：点**，1 元 = 100 点） |
| `--yes` | — | 确认真实扣费 |
| `--dry-run` | — | 只打印请求，不提交 |

## 子命令与退出码

`models` · `cost` · `doctor` · `gen` · `status` · `wait` · `log` —— **除 `gen` 外全部免费**。

`0` 成功 · `2` 用法错 · `4` 需 `--yes` · `5` 预算不足（**不发请求**）· `6` 失败 ·
`7` 等待超时（用 `wait` 接着取）· `1` 内部错 · `130` 中断

`--json` 写在子命令前后都可以，stdout 只有一个 JSON 文档。

## 更多细节

- 完整的接口契约、参数语义、错误码：`references/api-contract.md`
- 按报错找原因：`references/troubleshooting.md`
- 镜头结构、时长档位、任务状态机：同上两篇

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
