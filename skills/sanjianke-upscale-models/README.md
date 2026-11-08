# 超分模型台 · 3 条线比价，1080P 一分钟 5.4 元

三条视频超分线 + 4 个模型层超分模型，放进一个命令。

一条 10 分钟 1080P 老片：VIAPI 现可用 **54 元**；腾讯同规格 **12 元**，当前 502（失败全额退）；模型层 **50 点起**（按次保底）。

## 价目表（1 元 = 100 点）

| 线路 | 档位 | 单价 | 60 秒 | 现状 |
|---|---|---|---|---|
| VIAPI | 标准超分 1080P | 9 点/秒 | 540 点 = 5.40 元 | 可用 |
| VIAPI | 高清超分 2K | 15 点/秒 | 900 点 = 9.00 元 | 可用 |
| VIAPI | 超清 4K | 20 点/秒 | 1,200 点 = 12.00 元 | 可用 |
| 腾讯 MPS | 1080P | 2 点/秒 | 120 点 = 1.20 元 | 暂时不通，502 InvalidMpsUser |
| 腾讯 MPS | 2K | 4 点/秒 | 240 点 = 2.40 元 | 暂时不通 |
| 腾讯 MPS | 4K | 8 点/秒 | 480 点 = 4.80 元 | 暂时不通 |
| FlashVSR 应用 | 超分 | 10 点/秒 | 600 点 = 6.00 元 | 可用，实测 settled 72.348 点 |
| 4K 旗舰 | `/video/upscale` | 30 点/秒 | 1,800 点 = 18.00 元 | 待验证 |
| 模型层 | Topaz 视频优化 | 50 点/次起 | 按次 | 未授权，404 model_not_found |
| 模型层 | Topaz 图像优化 | 50 点/次起 | 按次 | 待验证，需 image_url |
| 模型层 | Recraft 图像优化 | 50 点/次起 | 按次 | 待验证，需 image |
| 模型层 | 放大 Grok 视频 | 50 点/次起 | 按次 | 待验证，需本账号 task_id |

## 三条干货

**① 腾讯 502 是上游凭据坏了，不是价格问题。**
完整参数提交 → `502 FailedOperation.InvalidMpsUser`。本账号 3 条腾讯 4K 任务全部 `refunded`、`chargedPoints=0`、`refundedPoints=120/48`。钱全额退回，路暂时走不通；空 body 仍回 `400 video_url_required`，端点本身在架。

**② 模型层单价不在价目表里。**
`/api/v1/pricing` 的 115 条规则没有 `/videos`、`/videos/generations`、`/images/generations`，只命中通配「上游点数 x 2、单笔保底 50 点」。真实价从 `/api/v1/me/tasks` 的 `actualPrice` 反推；有样本标 `source=live`，没有标 `source=baseline`，不编单价。

**③ 目录里有，不等于当前 Key 能调。**
`POST /api/v1/videos {"model":"topaz-video-upscale"}` → `404 model_not_found`；`recraft-crisp-upscale` 端点流水里出现过先冻 20 点再全额退。`catalog` 把「在架」和「可调」分开标。

## 用法

```bash
# 免费：12 条路线 + 单价 + 状态（不用 Key）
python3 scripts/run.py catalog

# 免费：先算钱
python3 scripts/run.py cost --seconds 600
python3 scripts/run.py cost --tier superres4k --seconds 600

# 免费：三线比价 + 推荐
python3 scripts/run.py compare --target 1080p --seconds 60
python3 scripts/run.py compare --target 4k --seconds 600

# 免费：同一需求多模型横评（要 Key，只读 /me/tasks）
python3 scripts/run.py models --models topaz-video-upscale,recraft-crisp-upscale

# 免费：自检
python3 scripts/run.py doctor

# 免费：上传素材
python3 scripts/run.py upload --file low.mp4

# 真提交（要 --yes，受 --budget 管）
python3 scripts/run.py submit --tier superres --video-url "https://..." --seconds 60 --yes

# 查任务（免费）
python3 scripts/run.py status --task-id task_xxx --tier superres
```

全局选项写在子命令前后都可以：`--json` / `--key` / `--host` / `--budget` / `--max-tokens`。

## 三步上手

1. **看**：`python3 scripts/run.py catalog` —— 先看「状态」列，√ 才是现可用的。
2. **算**：`python3 scripts/run.py compare --target 1080p --seconds 60` —— 一行给推荐和「腾讯修好后省多少」。
3. **跑**：`python3 scripts/run.py submit --tier superres --video-url "你的地址" --seconds 60 --yes`。

## 规格

- 输入：mp4 / mov / mkv 公网地址，或先 `upload` 拿平台托管地址。
- 输出：`taskId` + 状态；查询免费，成片链接有时效，及时转存。
- 计费：1 元 = 100 点；按秒线按输入秒数；腾讯保底 10 点、FlashVSR 保底 20 点；失败全额退。
- 双闸门：缺 `--yes` → exit 4；超 `--budget` → exit 5，一个请求都不发。
- 退出码：0 / 2 用法 / 3 自检 / 4 需 --yes / 5 预算 / 6 调用 / 1 内部 / 130 中断。
- 零依赖，只用 Python 标准库；不内嵌 Key。

## 文件结构

```text
sanjianke-upscale-models/
├── SKILL.md
├── README.md
├── LICENSE.md
├── references/
│   ├── api-contract.md
│   ├── troubleshooting.md
│   └── model-pricing.md
└── scripts/
    ├── a7w.py
    └── run.py
```

## 和已有超分包的分工

| 包 | 管什么 | 什么时候用它 |
|---|---|---|
| `sanjianke-vr-superres` / `-2k` / `-4k` | VIAPI 单档深做 | 已确定走 VIAPI 某一档 |
| `sanjianke-mps-upscale` | 腾讯 MPS 三档 | 腾讯 502 修好后 |
| `a7w-flashvsr` | FlashVSR 应用单档 | 只跑 FlashVSR |
| `sanjianke-vr-upscale-4k` | 4K 旗舰单档 | 明确要 4K 旗舰版 |
| **本包** | 三线比价 + 模型层横评 + 状态标记 | 还不知道选哪条，先比价 |

本包不替代任何单档专包：单档深做看专包，跨线选型看本包。

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
