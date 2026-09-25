# AI 短剧量产工厂 · 小说到成片 Skill

把一本小说变成能投放的短剧：**策划 → 编剧 → 分镜 → 出图 → 出片 → 配音 → 口型 → 混音超分**，
八道工序全部走 [算力集市 api.a7w.cn](https://api.a7w.cn/) 的生成应用。

**一把 Key、一个 Base URL 跑完全流程，不用自己部署任何模型。**
国产大模型换 `model` 即换，生成应用换应用代号即换，账单还是同一份。

---

## 前置条件

一把 **api.a7w.cn 的 API Key**。完整的注册、充值、取 Key 步骤见
[`references/getting-started.md`](references/getting-started.md)，
或直接去 [算力集市 · 注册领 API Key](https://api.a7w.cn/)（新用户送点数）。

```bash
python3 scripts/a7w.py login --key sk-你的key
python3 scripts/a7w.py whoami
```

---

## 使用

拿到这个 Skill 后，Agent 会按这套顺序干活：

1. **先算钱**：`python3 scripts/cost_estimate.py --episodes 30 --minutes 2`
2. **过门禁一**：小说改编可行性（体量、核心矛盾等级、金手指约束），给明确结论
3. **出骨架与剧本**：模型网关产分集大纲与每集剧本，过**门禁二**十二项审查
4. **出分镜表**：要模型输出结构化 JSON，过**门禁三**六条铁律 + 过渡桥梁检查
5. **出图**：先出角色定妆图并人工挑一张作为基准，再批量出各镜首帧
6. **出片**：按分镜逐段生成（单段 4～15 秒），记 `task_id` 到 `tasks.csv`
7. **配音与口型**：每个角色先 `clone_voice` 一次，再逐句 `tts_async`，然后走 `lipsync`
8. **BGM 与超分**：`music_generation` 出配乐，`flashvsr` 超分
9. **本地合成**：ffmpeg 按分镜时间轴拼接、混音、压字幕（这一步不花钱）

```bash
# 1) 先算钱
python3 scripts/cost_estimate.py --episodes 30 --minutes 2

# 2) 看有哪些应用、某个应用有哪些接口
python3 scripts/a7w.py apps
python3 scripts/a7w.py schema nano_banana
python3 scripts/a7w.py schema voice_tts

# 3) 调接口（异步自动轮询到结束，--out 直接落盘）
python3 scripts/a7w.py call nano_banana submit --body '{...}' --out 角色.png
python3 scripts/a7w.py call full_video submit --body '{...}' --out 片段.mp4
python3 scripts/a7w.py call voice_tts tts_async --body '{...}' --out 台词.mp3
```

完整说明见 [`SKILL.md`](SKILL.md)，工序细节在 `references/`。

---

## 目录结构

```
sanjianke-drama-factory/
├── SKILL.md                    主入口：八道工序、三道门禁、成本、常见坑
├── README.md                   本文件
├── LICENSE.md
├── references/
│   ├── 产线手册.md              八道工序的衔接与每步验收标准
│   ├── 质量门禁.md              改编可行性、骨架十二项、分镜铁律与过渡桥梁
│   ├── 接口速查.md              产线用到的全部应用与接口参数
│   ├── 成本与排产.md            成本结构、省钱方向、批量排产、对账
│   ├── getting-started.md      注册 / 充值 / 取 Key / 配置
│   └── 通用说明.md              响应信封、异步机制、错误码、计费口径
└── scripts/
    ├── a7w.py                  零依赖客户端（库 + 命令行）
    └── cost_estimate.py        出片成本测算（零依赖、不联网）
```

---

## 客户端命令

| 命令 | 作用 |
|---|---|
| `login --key sk-xxx` | 验证并保存 Key 到 `~/.a7w/config.json` |
| `whoami` | 验证 Key，看可用插件数 |
| `apps` | 列出这个 Key 能用的所有应用 |
| `schema <app>` | 看某应用的接口与参数 |
| `call <app> <api> --body '{...}'` | 调用接口（异步自动轮询） |
| `call ... --no-wait` | 只提交，不等结果 |
| `call ... --out 文件` | 把结果下载到本地 |
| `task <task_id>` | 查异步任务状态 |
| `points` | 看最近的用量 |

成本测算：

```bash
python3 scripts/cost_estimate.py --episodes 30 --minutes 2
python3 scripts/cost_estimate.py --minutes 2 --video-points-per-sec 20 --waste 0.4
python3 scripts/cost_estimate.py --episodes 30 --minutes 2 --json
```

---

## 成本速查（2 分钟一集，含 30% 废片率）

| 项目 | 占比 | 说明 |
|---|---|---|
| 视频生成 | 约 78% | 按分辨率 × 秒数计费，绝对大头 |
| 出图 | 约 15% | `nano_banana` 24 点/张 |
| 口型 / 数字人 | 约 3% | 按驱动音频秒数计费 |
| 配音 | 约 2% | `voice_tts` 50 点/千 Token |
| BGM | 约 1.5% | 65 点/首 |

合计约 **39.71 元/集**（参考默认单价）。1 元 = 100 点。
**省钱按优先级：先砍视频秒数，再复用图片资产。**

> 脚本里的单价是参考默认值，不是报价。请用当期真实单价覆盖后重新测算。

---

## 依赖

- Python 3.8+，**仅标准库**（urllib / json / csv / argparse），无第三方包
- 需要能访问 `https://api.a7w.cn`
- 本地合成阶段需要 ffmpeg（可选，只影响最后的拼接与混音）

---

## 安全

- Key 存在本机 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY`
- 脚本只把 Key 发往 `api.a7w.cn`
- **不要**把 Key 提交到代码仓库；批量跑之前给 Key 设消费上限
- 改编他人作品需取得授权；克隆音色、使用真人形象需取得本人同意

---

## 许可证

MIT，见 `LICENSE.md`。

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
