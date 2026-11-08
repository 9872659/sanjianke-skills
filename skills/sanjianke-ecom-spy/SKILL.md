---
name: sanjianke-ecom-spy
slug: sanjianke-ecom-spy
displayName: 带货素材侦察 1 元拆一条爆款
description: "**1 元（100 点）扒一条爆款，30 秒拆出标题公式、3 秒钩子、时长节奏和 3 条能直接换词的仿写标题。** 抖音搜索、小红书笔记搜索、两条详情、三个用户与作品列表、去水印取地址 —— 8 个接口一个命令，走 api.a7w.cn，同步返回、零依赖。三件最容易白花钱的事写进了默认动作：8 个接口**一律 100 点/次**（规则原文 `flat cost:100`），所以「搜 1 次 + 本地拆结构」比「逐条看详情」便宜一个数量级；规则 note 明写**失败亦计**，所以 `doctor` 只发只读 GET、必填缺了本地退 `2`；**结构分析不花钱**，快照落盘后 `rank` / `breakdown` / `clone` / `cover` 全在本地跑。`hunt` 一条命令发 1 次搜索（100 点），当场给热度榜、标题公式、分镜骨架与封面 prompt。遇到问题可加技术微信 9872659。"
version: 1.0.0
summary: "带货对标的价值在结构：同一套「身份 + 痛点 + 价格锚 + 数字」的骨架，换个品类就能用。**价目**（1 元 = 100 点）：`/api/v1/pricing` 里 `/api/v1/apps/watermark_removal/*` 是 `{"mode":"flat","cost":100}`，8 个接口同价、与返回条数无关，note 写明「失败亦计」。**接口**（`GET /api/v1/apps` 实测 8 个 code 齐全）：搜索 `douyin_search_video` / `xhs_search_note`，详情 `douyin_video_detail` / `xhs_note_detail`，列表 `douyin_user_video_list` / `xhs_user_note_list`，用户 `xhs_user_detail`，地址 `remove`；参数大小写逐字照 `params_schema`，同步返回、没有 task_id。**本地**：`rank` 按「赞 1 + 藏 2 + 评 3 + 转 4」排序；`breakdown` 拆标题六要素、钩子类型、时长档与逐段节奏；`clone` 出 3 条标题 + 5 段分镜；`cover` 出 3 条封面 prompt 并按实价提示走 nano_banana（72 点/张）。**闸门**：缺 `--yes` 退 `4`，超 `--budget` 退 `5` 且一个请求都不发。需要自备 api.a7w.cn 的 API Key，注册领 Key 见 https://api.a7w.cn/ 。遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - 带货侦察
  - 素材结构分析
  - api.a7w.cn
---

# 带货素材侦察 1 元拆一条爆款

> **本包不内嵌 Key**：用你自己在 [api.a7w.cn](https://api.a7w.cn/) 注册的 Key，扣你自己的余额。填 Key：`python3 scripts/a7w.py login --key sk-你的key`。

## 一句话

**1 元（100 点）扒一条爆款，30 秒拆出标题公式、3 秒钩子、时长节奏和 3 条能直接换词的仿写标题。** 从抖音 / 小红书找到对标，把「它为什么火」写成结构，再把结构换成你的选题、你的镜头、你的封面。

## 价目表（8 个接口同价，1 元 = 100 点）

| 能力 | 子命令 | 接口 code | 必填 |
|---|---|---|---|
| 抖音搜索 | `hunt --platform dy` / `dy-search` | `douyin_search_video` | `keyword` |
| 小红书搜索 | `hunt --platform xhs` / `xhs-search` | `xhs_search_note` | `keyword` |
| 抖音视频详情 | `dy-video` | `douyin_video_detail` | `videoId` |
| 小红书笔记详情 | `xhs-note` | `xhs_note_detail` | `noteId` |
| 抖音用户作品 | `dy-user` | `douyin_user_video_list` | `secUid` |
| 小红书用户笔记 | `xhs-user-notes` | `xhs_user_note_list` | `userId` |
| 小红书用户详情 | `xhs-user` | `xhs_user_detail` | `userId` |
| 去水印取地址 | `strip` | `remove` | `url` |

**每一行都是 100 点/次 = ¥1.00**，flat 计费，与返回几十条还是 1 条、素材多长都无关。
规则原文：`{"mode":"flat","cost":100,"note":"去水印/分享链解析：固定 100 点/次"}`。

## 三条干货

**一、8 个接口同一个价，所以「少搜、挑着看」才是省钱姿势。** 搜索一次就把几十条对标的标题、时长、点赞、收藏、评论一并带回来 —— 这些字段本身就够拆结构。钱在「详情」上，而详情也是一次 100 点：搜 1 次 + 本地拆结构 = 100 点；搜 1 次 + 20 条全看详情 = 2,100 点，差 21 倍。

**三、结构分析不用再花一分钱。** 搜索结果存进本地快照，`rank` / `breakdown` / `clone` / `cover` 全是读文件：排序按「赞 1 + 藏 2 + 评 3 + 转 4」（带货看的是想买，不是路过点赞）；拆结构给标题六要素、钩子类型、时长档与逐段节奏；仿写给 3 条标题 + 3 个钩子 + 5 段分镜；出图给 3 条 prompt 并按实价提示走 nano_banana（72 点/张）。

## 完整链路

```
① 搜索   hunt --platform dy --keyword "收纳盒"      100 点
② 排序   rank --by heat --top 10                      0 点
③ 拆结构 breakdown --top 3                            0 点
④ 仿写   clone --count 3                              0 点
⑤ 出图   cover + nano_banana 封面                     72 点
```

**一条链路 172 点 = ¥1.72**：采集 100 点，封面 72 点，中间三步全免费，想复看几遍都行。

## 三步上手

```bash
# 1) 填 Key（三选一：--key / A7W_API_KEY / a7w.py login）
export A7W_API_KEY=sk-你的key

# 2) 免费：自检 + 先算钱
python3 scripts/run.py doctor
python3 scripts/run.py cost --search 1 --detail 3

# 3) 一条命令跑完整条链（1 次调用 = 100 点）
python3 scripts/run.py hunt --platform dy --keyword "收纳盒" --yes
```

## 常用命令

```bash
python3 scripts/run.py catalog                                     # 8 个接口 + 必填 + 单价
python3 scripts/run.py cost --search 1 --detail 3 --strip 1         # 先算钱
python3 scripts/run.py doctor                                      # 只读自检，0 点
python3 scripts/run.py hunt --platform xhs --keyword "通勤穿搭" --yes
python3 scripts/run.py hunt --platform dy --keyword "小家电" --dry-run   # 只看请求
python3 scripts/run.py xhs-search --keyword "通勤穿搭" --sort popularity_descending --yes
python3 scripts/run.py dy-video --video-id 7000000000000000000 --yes
python3 scripts/run.py strip --url "https://v.douyin.com/xxxxxxx/" --yes
python3 scripts/run.py rank --by collects --top 10                  # 本地 0 点
python3 scripts/run.py breakdown --top 3
python3 scripts/run.py clone --count 3
python3 scripts/run.py cover
python3 scripts/run.py log
```

**不加 `--yes` 退 `4`** 并告诉你这次要花多少点；**预计点数超 `--budget` 退 `5`，一个请求都不发**（`--budget` 单位是点，默认 1000 = 10 次调用）。

## 规格

| 项 | 值 |
|---|---|
| 端点 | `POST https://api.a7w.cn/api/v1/apps/watermark_removal/<接口code>` |
| 名单 | `GET /api/v1/apps`（应用 code `watermark_removal`，8 个接口） |
| 价目 | `GET /api/v1/pricing` → `/api/v1/apps/watermark_removal/*` = `flat 100` |
| 返回 | `{"code":1,"msg":"success","data":{…}}`，业务数据在 `result.data`，同步返回 |
| 依赖 | 只用 Python 标准库（`urllib` / `json` / `re`），零安装 |
| 快照 | `~/.a7w/ecom-spy/snapshots/*.json`，最新一份指针在 `~/.a7w/ecom-spy/latest.json` |
| 台账 | `~/.a7w/ecom-spy/ledger.json`（`log` 读它） |

| 退出码 | 含义 |
|---|---|
| `0` / `2` | 成功 / 用法错（缺必填、快照不存在、选项缩写） |
| `3` / `4` | `doctor` 出现 × / 没给 `--yes`（会报要花多少点） |
| `5` / `6` | 预算不足（**一个请求都不发**）/ 调用失败 |
| `1` / `130` | 内部错误 / 被 Ctrl-C 中断 |

`--json` 成功给 `{"ok":true,…}`，失败给 `{"ok":false,"exit":N,"error":{"kind":"…","message":"…"}}`，`kind` 取 `usage|gate|confirm|budget|call|interrupt|internal`。

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--keyword` | 必填 | 搜索关键词 |
| `--platform` | `dy` | `dy` 抖音 / `xhs` 小红书（只 `hunt`） |
| `--video-id` / `--note-id` / `--sec-uid` / `--user-id` / `--url` | 必填 | 对应接口的主键 |
| `--sort` / `--note-type` | — | 小红书排序与笔记类型（`_0` 通用 / `_1` 视频 / `_2` 图文） |
| `--page` / `--cursor` / `--max-cursor` / `--search-id` | — | 翻页游标，取自上一页 |
| `--snapshot` / `--by` / `--top` / `--count` | 最新 / `heat` / 10 / 3 | 本地分析的读哪份、怎么排、几条 |
| `--budget` / `--yes` / `--dry-run` | 1000 / — / — | 点数上限、确认扣费、只打印请求 |

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。
