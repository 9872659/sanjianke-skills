# 三剪客 · AI 短剧量产引擎 Skill

把一本小说变成能投放的短剧——一整套跑通「策划 → 编剧 → 分镜 → 出片」的工业化流程。
[Toonflow](https://gitee.com/HBAI-Ltd/Toonflow-app)——开源 AI 短剧漫剧工具（Apache-2.0）。

---

## 前置条件

**不需要任何 Key，本 Skill 全程离线。**

要真正出片，需要你自己准备：

- 本机或服务器装好 Toonflow（见 `references/quickstart.md`）
- 文本 / 图像 / 视频三类模型的 API Key

---

## 使用

问它这些问题：

- 「这本小说能不能改成短剧？」
- 「帮我审一下这份故事骨架」
- 「分镜表里人物消失了是什么原因？」
- 「Toonflow 怎么部署到云服务器？」
- 「我想做一个水墨风的画风包」

---

## 脚本

三个离线工具，零依赖（仅 Python 标准库）：

```bash
# 成本估算（默认参数复现官方 Demo 的 ¥130 量级）
python3 scripts/cost_estimate.py --episodes 30 --minutes 2

# 生成画风包 / 题材包骨架
python3 scripts/new_toonflow_skill.py --kind art   --name 2D_ink_wash --out ./my-skills
python3 scripts/new_toonflow_skill.py --kind story --name Time_travel  --out ./my-skills

# 校验技能包结构
python3 scripts/check_toonflow_skill.py ./my-skills/2D_ink_wash
```

---

## 目录结构

```
toonflow-playbook/
├── SKILL.md                      入口：路由、六条工作流、能力边界
├── README.md                     本文件
├── LICENSE.md                    MIT + 上游声明
├── references/
│   ├── quickstart.md             部署与模型配置
│   ├── pipeline.md               全流程与推进顺序
│   ├── script-stage.md           编剧阶段规范
│   ├── storyboard-stage.md       制片阶段规范
│   ├── builtin-skills.md         内置技能体系
│   ├── custom-skills.md          自建技能包
│   ├── models-and-cost.md        模型与成本
│   └── troubleshooting.md        排错
└── scripts/
    ├── cost_estimate.py          成本估算
    ├── new_toonflow_skill.py     技能包脚手架
    ├── check_toonflow_skill.py   结构校验
    └── selftest.py               自测
```

---

## 自测

改动脚本后先跑：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/selftest.py -v
```

> 本机运行会生成 `scripts/__pycache__/*.pyc`，交付前删除。

---

## 依赖

- Python 3.8+，**仅标准库**（`argparse` / `json` / `pathlib` / `subprocess`），无第三方包
- 不联网、不读写工作目录以外的文件

---

## 安全

- 不读取、不存储任何 API Key
- 不发起任何网络请求
- 脚手架脚本只在 `--out` 指定的目录下创建文件，同名目录存在时拒绝覆盖

---

## 版权

本 Skill 由三剪客出品，独立编写，不包含第三方项目的源代码。


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
