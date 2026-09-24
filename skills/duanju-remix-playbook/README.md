# 短剧二创作业手册

把短剧二创从「打开剪辑软件就干」变成**有流程、有口径、有质检**的作业方式。

短剧二创的门槛不在剪辑技术，而在流程管理：授权有没有、口径乱不乱、一批片子
做出来是不是互相的复制品、发布前有没有过合规。

---

## 内容

```
duanju-remix-playbook/
├── SKILL.md                                 主入口：五条工作流、脚本、边界、自检清单
├── README.md                                本文件
├── LICENSE.md                               MIT
├── references/
│   ├── rights-checklist.md                  授权核验清单、留痕模板、开工四关
│   ├── license-areas.md                     AI 音色 / BGM / 字体 / 肖像授权
│   ├── platform-and-content-rules.md        平台原创性要求、AI 标注、七类高危话术
│   ├── workflow-overview.md                 九步出片流程、口径管理、时间预算
│   ├── differentiation-rules.md             四条差异化、复用系数、自检表
│   └── quality-checklist.md                 发布前质检项
└── scripts/
    ├── duanju_compliance.py                 七类高危话术扫描
    ├── frame_dedup.py                       批量成片抽帧查重
    └── selftest.py                          内置自测
```

---

## 快速开始

```bash
# 发布前扫文案
python3 scripts/duanju_compliance.py --file script.txt --strict

# 批量成片查重
python3 scripts/frame_dedup.py --dir "输出目录" --threshold 0.40

# 自测
python3 scripts/selftest.py -v
```

---

## 两个脚本

**`duanju_compliance.py`** —— 七类高危话术扫描（全集承诺 / 独家宣称 / 擦边引流 /
暴力血腥 / 盗版搬运 / 收益诱导 / 极限词）。Python 3.8+、仅标准库、完全离线。
支持自定义词表与 JSON / CSV 输出，`--strict` 时高风险即退出码 1，可接发布流水线。

**`frame_dedup.py`** —— 批量成片抽帧查重。每条按时间均匀抽帧 → 9×8 灰度 →
dHash 64 位 → 贪心唯一配对统计相似度。**相似度与顺序无关**，输出的相似度矩阵
直接告诉你哪几条片子撞了。

需要 ffmpeg（`--ffmpeg` 或环境变量 `FFMPEG_PATH` 指定；也会自动从 PATH 查找）。
**帧数据处理是纯标准库实现，不需要 numpy / PIL。**

已验证：同一条片自比 = 100%；素材不重叠的两条片 = 0%。

---

## 依赖

- Python 3.8+
- `duanju_compliance.py`：无任何外部依赖
- `frame_dedup.py`：需要 ffmpeg（用于抽帧）

---

## 适用客户端

SkillHub / OpenSkills / Claude Code 兼容客户端，以及任何能读取 `SKILL.md` 的 Agent 运行时。

---

## 开发

```bash
# 改动任一脚本后先跑自测
PYTHONDONTWRITEBYTECODE=1 python3 scripts/selftest.py -v

# 发布前做包级校验（校验器在上级目录）
python3 ../validate_skillhub_package.py .
```

> 本机运行脚本会生成 `scripts/__pycache__/*.pyc`，**发布前删除**。

---

## 能力边界

- 不提供绕过平台审核或规避判定的写法
- 不提供具体的剪辑参数配方（参数取决于素材与目标，需自行锁定口径）
- 不抓取平台数据、不涉及自动发布
- 不替代法律意见

---

## 许可证

MIT，见 `LICENSE.md`。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
