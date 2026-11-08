# Suno 音乐台 一句话出一首歌
**给人一句话，它给你一首完整的歌 —— 带人声、带伴奏、带时间戳歌词。**

走 [api.a7w.cn](https://api.a7w.cn/) 的 Official 音频与辅助服务（应用代号 `media_services_33`），
本包接通其中 **7 个 Suno 音乐接口**，一个命令一个，异步提交 + 自动轮询，零依赖。

---

## 一句话

**一句话进，一首歌出。** 提交后自动等结果，完成时把 `audio_id`、时长、音频直链、歌词一起打出来。

```bash
python3 scripts/run.py song --prompt "夏夜霓虹的温暖合成器流行" --yes
#   #1 夜行
#       audio_id：audio_xxxxxxxx  ← 延长 / 取歌词 / 建 Persona 都要它
#       时长：152 秒
#       音频：https://…/song.mp3
```

那串 `audio_id` 是整套流程的钥匙：**延长**、**取时间戳歌词**、**建 Persona** 都靠它。

---

## 能干什么

| 能力 | 一条具体用法 | 你会拿到 |
|---|---|---|
| **出歌** | `song --prompt "夏夜霓虹的温暖合成器流行"` | 一首完整歌：人声 + 伴奏 + 歌名 |
| **写词出歌** | `song --custom --style "dream pop" --lyrics "[主歌]…" --title 夜行` | 歌词严格照唱 |
| **纯音乐** | `song --prompt "钢琴独白" --instrumental` | 无人声的伴奏曲 |
| **延长** | `extend --audio-id <audio_id> --lyrics "…"` | 在原曲后面再接一段 |
| **音效** | `sound --prompt "雨打铁皮棚，远处闷雷" --tempo 90 --loop` | 一段可循环音效 |
| **自建音色** | `voice --action prepare --voice-url <样本> --start 3 --end 18` | 验证短句 → `create` 出你的音色 |
| **时间戳歌词** | `lyrics --task-id <id> --audio-id <id>` | 逐句时间轴，直接压字幕 |
| **恢复** | `recover --task-id <id>` | 链接过期后把音频再取一次 |
| **Persona** | `persona --name 夜行嗓 --task-id <id> --audio-id <id> --description "…"` | 可复用的风格模板 |

---

## 怎么串起来

```
写词  →  出歌  →  不满意就延长  →  要字幕就取时间戳歌词  →  要自己的声音就建音色
```

```bash
# 1) 自己写词，直接出歌
python3 scripts/run.py song --custom --style "city pop" \
    --lyrics "[主歌]霓虹把街角点亮" --title "夜行" --yes

# 2) 副歌没唱够？拿上一首的 audio_id 接着写
python3 scripts/run.py extend --audio-id <audio_id> --lyrics "…" --yes

# 3) 要字幕？把逐句时间轴取出来
python3 scripts/run.py lyrics --task-id <task_id> --audio-id <audio_id> --yes

# 4) 想要自己的声音？先 prepare 拿验证短句，录完再 create
python3 scripts/run.py voice --action prepare --voice-url https://…/me.wav \
    --start 3 --end 18 --voice-name "我的声音" --yes
python3 scripts/run.py voice --action create --verify-url https://…/record.wav --yes
```

`--no-wait` 只提交拿 `task_id` 就走，之后 `task --task-id …` 免费续查：
**同一条结果不会被重复提交**，也就不会重复计费。

---

## 价格口径（诚实版）

`/api/v1/pricing` 里**没有 `media_services_33` 的专属规则**，落通配：

```json
```

上游真实点数要真跑一条才看得到，所以 **`cost` 给的是下限估算**，不是报价：

```bash
python3 scripts/run.py cost                    # 上游未知 → 至少 50 点（¥0.50）
python3 scripts/run.py cost --upstream 65      # 上游 65 点 → 130 点（¥1.30）
python3 scripts/run.py cost --upstream 65 --tasks 3
```

|---|---|---|
| 未知 | 50 点 | ¥0.50 |
| 60 | 120 点 | ¥1.20 |
| 65 | 130 点 | ¥1.30 |
| 90 | 180 点 | ¥1.80 |
| 230 | 460 点 | ¥4.60 |

---

## 快速开始

```bash
# 1) 填 Key（三选一）
export A7W_API_KEY=sk-你的key            # Linux / macOS
$env:A7W_API_KEY="sk-你的key"            # Windows PowerShell

# 2) 免费自检：Key、应用、7 个端点、任务查询
python3 scripts/run.py doctor

# 3) 免费看价（下限）
python3 scripts/run.py cost

# 4) 出歌
python3 scripts/run.py song --prompt "夏夜霓虹的温暖合成器流行" --yes
```

---

## 常用命令

```bash
# 纯音乐 + 指定时长 + 更敢玩
python3 scripts/run.py song --prompt "钢琴独白" --instrumental --duration 90 --model V6_WILD --yes

# 轻快省一档
python3 scripts/run.py song --prompt "清晨咖啡店" --model V6_MINI --yes

# 只要音效
python3 scripts/run.py sound --prompt "雨打铁皮棚，远处闷雷" --tempo 90 --loop --yes

# 只提交，不等待
python3 scripts/run.py song --prompt "城市夜行" --no-wait --yes
python3 scripts/run.py task --task-id <task_id> --out ./suno

# 顺手下载音频
python3 scripts/run.py song --prompt "城市夜行" --out ./suno --yes

# 只看请求，不花钱
python3 scripts/run.py song --prompt "城市夜行" --dry-run
```

---

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--model` | `V6` | `V6` / `V6_MINI` / `V6_WILD` / `V5_5` / `V5` / `V4_5ALL` / `V4_5PLUS` / `V4_5` / `V4` |
| `--prompt` | — | 灵感模式的一句话描述；`sound` 里是声音描述（≤500 字符） |
| `--custom` | — | 自定义模式（配 `--style` / `--lyrics` / `--title`） |
| `--style` | — | 风格标签，例如 `dream pop` / `国风` / `爵士` |
| `--lyrics` | — | 歌词，V6 系最多 5000 字符 |
| `--title` | — | 歌名，**自定义模式下必填**，≤80 字符 |
| `--instrumental` | — | 纯音乐 |
| `--duration` | — | 目标时长 10–360 秒（`V6` 系与 `custom_mode=true` 下有效） |
| `--variety` | 1 | 多样性 0–4 |
| `--tempo` | 120 | 音效速度 1–300 BPM |
| `--sound-key` | `Any` | 音效调性，`Any` 为自动 |
| `--out` | — | 把音频下载到这个目录 |
| `--budget` | 500 | 点数上限，**单位是点**（1 元 = 100 点） |
| `--upstream` | 0 | 你观察到的上游点数，用来换算实际价 |
| `--yes` | — | 确认真实计费 |
| `--dry-run` | — | 只打印请求，不提交 |
| `--no-wait` | — | 只提交，拿 `task_id` 就走 |

---

## 子命令

| 子命令 | 计费 | 干什么 |
|---|---|---|
| `catalog` | 免费 | 现查 7 个接口的必填项与 `model` 枚举 |
| `doctor` | 免费 | 自检 Key / 应用 / 7 个端点 / 任务查询 |
| `cost` | 免费 | 先算钱（下限） |
| `song` | 上游×2 保底 50 点 | 生成音乐 |
| `extend` | 同上 | 延长音乐 |
| `sound` | 同上 | 生成音效 |
| `voice` | 同上 | 自建音色（prepare → create） |
| `lyrics` | 同上 | 带时间戳歌词 |
| `recover` | 同上 | 恢复音频 |
| `persona` | 同上 | 生成 Persona |
| `task` | 免费 | 查状态 / 补取结果 |
| `log` | 免费 | 本地台账 |

---

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 用法错（缺必填、`model` 不在枚举、数值越界） |
| `3` | `doctor` 有检查项没过 |
| `4` | 没有 `--yes` |
| `5` | 下限超 `--budget`，**一个请求都不发** |
| `6` | 调用失败 / 任务失败 / 轮询超时 |
| `1` | 内部错误 |
| `130` | 被 Ctrl-C 中断 |

---

## `--json` 契约

```json
{"ok": true, "api": "music_generate", "task_id": "task_xxx", "status": "completed",
 "audios": [{"audio_id": "audio_xxx", "audio_url": "https://…", "title": "夜行"}],
 "pointsFloor": 50, "usage": {"points_cost": 65}}
```

失败：

```json
{"ok": false, "exit": 5, "error": {"kind": "budget", "message": "…"}}
```

`--json` 写在子命令**前面或后面都可以**，stdout 只有一个 JSON 文档。

---

## 文件结构

```
sanjianke-suno-music/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md       接口契约（schema 原文 + 实测）
│   └── troubleshooting.md    排错：按报错找原因
└── scripts/
    ├── a7w.py                零依赖客户端（全家族共用，逐字节一致 16,797 B）
    └── run.py                本包命令层
```

---

## 排错速查

| 你看到的 | 原因 | 怎么办 |
|---|---|---|
| `input.model: 不在允许选项内` | 模型名不在枚举里 | `catalog` 看枚举，或直接用 `V6` |
| `input.sound_tempo: 类型不正确` | 音效接口漏传速度 | 本包总是显式传 `--tempo`，默认 120 |
| `input.xxx: 缺少必填参数` | 少了必填项 | 报错里点名了字段，按名字补 |
| `请使用本平台返回的任务或资源标识` | `audio_id` 不是本平台产出的 | 用 `song` / `extend` 打出来的 `audio_id` |
| `音色操作步骤无效` | `--action` 只收 `prepare` / `create` | 先 `prepare` 再 `create` |
| `任务不存在` | `task_id` 写错或已过期 | 用台账 `log` 里的 `task_id` |

更细的按报错找原因见 `references/troubleshooting.md`，接口原文见 `references/api-contract.md`。

---

## 许可证

MIT，见 `LICENSE.md`。

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
