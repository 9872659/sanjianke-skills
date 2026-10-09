# 变更记录

本文件自 `1.0.3` 起建立；`1.0.2` 及更早版本没有归档明细，这里只标注区间。

## 1.0.4

**正文原创化重写。**

- `references/selection-scorecard.md`、`references/deploy-and-configure.md`、
  `references/ops-and-compliance.md` 三份方法论全文重写：章节划分、标题、
  叙述、类比、表格列定义全部重写，不再沿用此前的行文。
- `SKILL.md`、`README.md` 的叙述段同步重写（开头、权限说明、触发场景、
  快速开始、工作区三条路线、能力边界、已知限制、自检清单等）。
- **保留不变**（事实层，不受改写影响）：接口端点与路径、参数名、
  命令与参数、实测单价、版本号与端口、检查项条目、清单结构与判定阈值。
- `image_human` 的价格口径补齐：四档 `fast` / `standard` / `2k` / `4k`
  各真打一次实测，按驱动音频时长结算得 **2 / 3 / 6 / 12 点/秒**
  （2.64 秒音频分别扣 5.28 / 7.92 / 15.74 / 31.49 点）。
  此前文档里沿用的档位价与租户字段都不是结算价，本次以实测扣点为准，
  并在文中注明了「租户字段未必等于结算价」这一坑。
- 新增 `CHANGELOG.md`。
- 验证：`full_video/submit` 的 `content` 数组首帧写法
  （`{"role":"first_frame","type":"image_url","image_url":{"url":...}}` 加一条
  `{"type":"text"}`）经真实调用验证可用；`run.py pilot` 全链路
  （出图 24 点 + 首帧出片 40 点 + 配音 0.35 点 = 64.35 点）跑通并落盘三个产物。
- 校验方式：对重写前后做了两轮自动比对——① 事实清单（行内代码、代码块命令、
  标识符、数字）逐项比对，确认无丢失；② 表达层字符 n-gram 与逐句重合度比对，
  确认叙述已换写。

## 1.0.3

**接入真实算力。**

- 新增 `scripts/a7w.py`：零依赖客户端，`login / whoami / apps / points / schema / call / task`。
- 新增 `scripts/run.py`：`pricing / models / voices / image / video / voice / pilot`，
  真调 `api.a7w.cn` 的出图、出片、配音与取价接口。
- `scripts/cost_estimate.py` 改造：默认仍为离线纯计算；新增 `--a7w-live` 与
  `--price-file`，可按平台 `tenant_*` 字段价折算成本；新增
  `--a7w-image-resolution` / `--a7w-video-resolution` / `--clip-seconds` /
  `--tts-chars` / `--price-out`。
- `SKILL.md` 增补「怎么用（命令行）」与「接入 api.a7w.cn 的真实端点」，
  并补入实测单价表。
- 文档中原有的「全程离线 / 不访问任何外部地址」表述按实际情况更正为
  「仅在你显式调用时才联网」。

## 1.0.2 及更早

历史版本。定位为纯方法论文档（选型决策 + 私有化部署 + 运维合规），
无算力接入，无版本明细归档。
