# 图片一键去背景 · 换底出图 Skill

把图片的主体从背景里干净分离：商品图换纯白底、人像抠成透明底、
把主体换到另一张背景图上。上传一张公网图片 URL，写清要什么底，约 30 秒拿回成图。

**不用装环境、不用买显卡。** 所有 AI 能力都走 [算力集市 api.a7w.cn](https://api.a7w.cn/)，
只需要一把你自己的 API Key。

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

1. **先问清要什么底**：纯白底 / 纯色底 / 透明底 / 换场景 —— 四种提示词写法不同。
2. **确认素材是公网 URL**：本地文件先传对象存储或图床，拿到匿名可访问的直链。
3. **跑最小示例**：`action=edit` + `image_urls` 一图 + 一条提示词，先出 1 张验证效果。
4. **按用途选档位**：社媒/主图用 `nano-banana` · 1K（24 点）；要高清换 `:official` 模型。
5. **批量时先提交再收结果**：用 `--no-wait` 批量提交并记 `task_id`，之后统一下载。
6. **出图后本地说**：统一尺寸、统一色调、检查边缘残留 —— 都比逐张重生成便宜。

```bash
# 看这个插件有哪些接口、参数是什么
python3 scripts/a7w.py schema nano_banana

# 去背景换白底（自动轮询到结束并落盘）
python3 scripts/a7w.py call nano_banana submit \
  --body '{"action":"edit","prompt":"去掉背景，换成纯白背景 #FFFFFF，主体保留完整，边缘干净","image_urls":["https://你的存储/商品图.jpg"]}' \
  --out 白底图.png

# 只提交不等结果
python3 scripts/a7w.py call nano_banana submit --body '{...}' --no-wait

# 按 task_id 查任务
python3 scripts/a7w.py task <task_id>
```

接口清单与参数表见 [`SKILL.md`](SKILL.md)，细节在 `references/`。

---

## 目录结构

```
sanjianke-bg-remover/
├── SKILL.md                    主入口：四种要法、三步跑通、计费、常见坑
├── README.md                   本文件
├── LICENSE.md
├── references/
│   ├── 去背景指南.md            提示词模板、素材要求、批量做法、出图后处理
│   ├── api-nano_banana.md      submit / query 完整参数与返回
│   ├── getting-started.md      注册 / 充值 / 取 Key / 配置
│   └── 通用说明.md              响应信封、异步机制、错误码、计费口径
└── scripts/
    └── a7w.py                  零依赖客户端（库 + 命令行）
```

---

## 客户端命令

| 命令 | 作用 |
|---|---|
| `login --key sk-xxx` | 验证并保存 Key 到 `~/.a7w/config.json` |
| `whoami` | 验证 Key，看可用插件数 |
| `apps` | 列出这个 Key 能用的所有插件 |
| `schema <app>` | 看某插件的接口与参数 |
| `call <app> <api> --body '{...}'` | 调用接口（异步自动轮询） |
| `call ... --no-wait` | 只提交，不等结果 |
| `call ... --out 文件` | 把结果下载到本地 |
| `task <task_id>` | 查异步任务状态 |
| `points` | 看最近的用量 |

---

## 计费速查

| 动作 | 点数 | 折合 |
|---|---|---|
| 去背景 / 换底（`nano-banana` · 1K） | 24 | 0.24 元 |
| `nano-banana-2` · 1K | 38 | 0.38 元 |
| `nano-banana-pro` · 1K | 45 | 0.45 元 |
| 官方高清 `:official` 系列 | 28.03 起 | 按 1K / 2K / 4K 分档 |
| `query` 查任务 | 免费 | — |

1 元 = 100 点，按张计费、没有月费。实际扣费以 `data.usage.points_cost` 为准。

---

## 依赖

- Python 3.8+，**仅标准库**（urllib / json / mimetypes），无第三方包
- 需要能访问 `https://api.a7w.cn`

---

## 安全

- Key 存在本机 `~/.a7w/config.json`（权限 600）或环境变量 `A7W_API_KEY`
- 脚本只把 Key 发往 `api.a7w.cn`
- **不要**把 Key 提交到代码仓库
- 处理他人图片用于商用前，请自行确认授权

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
