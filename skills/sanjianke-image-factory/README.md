# 三剪客 · 新媒体配图工厂

给一篇文稿或一个主题，**自动产出整套新媒体配图**——封面与内文配图一次到位，
按各平台比例出图，**跑之前先告诉你花多少钱**。

```
plan  →  出配图方案（只花文本钱）
gen   →  按方案批量出图（真花钱，先报价再确认）
cost  →  只算钱不出图
models →  列出在架应用与模型
```

## 30 秒上手

```bash
# 1) 拿 Key（新用户有赠送点数）
#    到 https://api.a7w.cn/ 注册，创建一个 API Key

# 2) 配 Key
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 3) 确认网关通（免费）
python3 scripts/run.py models

# 4) 出方案（只花文本钱）
python3 scripts/run.py plan --topic "便携榨汁杯" --count 6 --out plan.json

# 5) 先看要花多少钱
python3 scripts/run.py cost --count 6
#   预估成本：6 张 × 24 点 = 144 点 = 1.44 元

# 6) 出图（先不带 --yes 报价，确认了再加）
python3 scripts/run.py gen --plan plan.json --outdir ./out
python3 scripts/run.py gen --plan plan.json --outdir ./out --yes --snap
```

**零依赖**，只要 Python 3.7+，不用 `pip install` 任何东西。

`scripts/a7w.py` 是**所有 Skill 包共用**的零依赖客户端（我们靠 SHA256 校验各包副本是否一致），
本包没有改它；「读图片真实像素」这个私有能力放在独立模块 `scripts/imgprobe.py` 里。

## 支持的比例 preset

| preset | 平台 | 比例 |
|---|---|---|
| `xiaohongshu` | 小红书 | 3:4 |
| `wechat` | 公众号头图 | 2.35:1 |
| `douyin` | 抖音 | 9:16 |
| `toutiao` | 头条 | 16:9 |
| `square` | 通用方图 | 1:1 |

## 四道硬闸门

闸门都**拦截**（不是警告），因为配图是按次扣费的：

1. **比例真伪** —— 把图下载回来**读文件头真实像素**再算比例，不信接口自报字段
2. **成本上限** —— 超 `--budget` 不提交任何任务
3. **广告法违禁词** —— 绝对化用语/医疗功效/虚假背书
4. **`prompt_echo`** —— 出图提示词与提示词里的示例**去标点后相等**、
   **Jaccard ≥ 0.75**、或**示例二元组覆盖度 ≥ 0.60**，三条任一命中即拦
   （模型会照抄提示词里的示例，哪怕示例标着"这是错的写法"）。
   第三条是补漏：提示词动辄 60~120 字而示例只有 25 字，Jaccard 会被长度差摊薄——
   示例原样嵌进 102 字的提示词里实测只有 0.245（放行），而覆盖度是 1.00（拦下）。
   覆盖度只看"示例被抄了多少"，不看提示词有多长。

## 成本

| 项 | 实测 |
|---|---|
| `nano_banana` 1K 出图 | **24 点/张** = 0.24 元 |
| 充值 | 1 元 = 100 点 |

**只信任务返回的 `usage.points_cost`。** 平台的 `pricing_matrix` / `tenant_*` 字段
我们验证过半数不可信（`image_human` 写 1.5/2/4/8 点/秒、实测 2/3/6/12）。

## 断点续跑

出图中断后原样重跑即可，**提示词没变就不会重复扣费**（断点 key 含提示词，改了会重出重扣）：

```
[1/3] #1 已完成，跳过（上次扣费 24.0 点，不再重复扣）
[2/3] #3 发现未完成的 task_id=task_xxx，续查而不重新提交
```

## 图片放哪里

**必须放在 Skill 包外**（默认 `%TEMP%\image-factory-out`）。包只收文本文件，
图片会让上传 400——脚本也会拒绝把 `--outdir` 指到包内（退出码 2）。

## 文档

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 完整操作文档（子命令、参数、闸门、排错） |
| `references/platform-specs.md` | 各平台尺寸规范、安全区、上游 32 对齐实测 |
| `references/prompt-writing.md` | 出图提示词写法与各平台视觉风格 |
| `references/cost-and-troubleshooting.md` | 计费口径、实测数据、排错与对账 |

## 脚本

| 文件 | 说明 |
|---|---|
| `scripts/run.py` | 四个子命令 + 四道闸门 + 断点续跑 |
| `scripts/imgprobe.py` | 图片头探针：读 PNG/JPEG/GIF/WebP 真实像素（只读，纯标准库） |
| `scripts/a7w.py` | 共用零依赖客户端，**逐字节等于规范版，本包不改动** |

## 更新记录

| 版本 | 变更 |
|---|---|
| 1.0.8 | 断点续跑补上成本条件：断点 key 含提示词，改提示词会重出重扣（排错表「重跑又扣了一次钱」一行同步补上 `cost` 前置核价）；README 尾部对齐全库主流模板（许可证 / 联系我们 / 相关链接 三段）。1.0.2~1.0.7 未逐版登记，本行归档至当前状态。 |
| 1.0.1 | 把「读图片像素」从 `a7w.py` 拆到独立模块 `imgprobe.py`，`a7w.py` 还原成规范版逐字节副本（SHA256 `EACD2E4F…`）。行为不变。 |
| 1.0.0 | 首个版本。 |

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
