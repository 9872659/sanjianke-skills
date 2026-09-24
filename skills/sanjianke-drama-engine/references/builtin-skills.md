# 内置技能体系

Toonflow 的提示词不是硬编码在代码里的，而是**外化成 Markdown 文件**放在
`data/skills/` 下。这是它最值得学的设计——调提示词不用改源码、不用重新编译。

一共三类，各管一件事：

| 类型 | 位置 | 影响什么 | 数量 |
|---|---|---|---|
| **Agent 提示词技能** | `data/skills/*.md`（平铺） | 每个 Agent 怎么思考、怎么执行 | 13 |
| **画风技能包** | `data/skills/art_skills/<风格>/` | **画面长什么样** | 11 |
| **题材技能包** | `data/skills/story_skills/<题材>/` | **故事怎么讲** | 12 |

关键区别：**画风包管视觉，题材包管叙事**。选错画风是画面不对味；选错题材包是节奏不对味。

---

## 一、13 个 Agent 提示词技能

按「编剧 / 制片」两条线 × 「决策 / 执行 / 监督」三层排列：

### ScriptAgent（编剧）

| 文件 | 标题 | 层级 |
|---|---|---|
| `script_agent_decision.md` | 决策层 Agent 技能指令 | 决策 |
| `script_execution_skeleton.md` | 故事骨架搭建 Agent | 执行 |
| `script_execution_adaptation.md` | 改编策略制定 Agent | 执行 |
| `script_execution_script.md` | 剧本编写 Agent | 执行 |
| `script_agent_supervision.md` | 监督层 Agent 技能指令 | 监督 |

### ProductionAgent（制片）

| 文件 | 标题 | 层级 |
|---|---|---|
| `production_agent_decision.md` | 决策层 Agent 技能指令 | 决策 |
| `production_execution_director_plan.md` | 导演规划 | 执行 |
| `production_execution_storyboard_table.md` | 分镜表 | 执行 |
| `production_execution_storyboard_panel.md` | 执行层 — 分镜面板写入 | 执行 |
| `production_execution_storyboard_gen.md` | 执行层 — 分镜图生成 | 执行 |
| `production_execution_derive_assets.md` | 执行层 — 衍生资产分析与信息写入 | 执行 |
| `production_execution_generate_assets.md` | 执行层 — 衍生资产图片生成 | 执行 |
| `production_agent_supervision.md` | 监督层 Agent 技能指令 | 监督 |

**体量差异很说明问题**：`script_execution_skeleton.md`（故事骨架）11802 字、
`script_execution_script.md`（剧本）10394 字，而 `production_execution_generate_assets.md`
只有 624 字。

骨架和剧本的提示词之所以最长，是因为方法论密度最高——矛盾四级阶梯、三大密度、
付费点比例公式这些全在里面。而「资产生成」只是把已有数据落成图片，规则本来就少。

> **所以要调优的话，先调骨架和剧本这两份，收益最大。**

### 决策层在干什么

决策层不产出内容，它做的是**项目初始化和流水线派发**：读项目配置（集数、单集时长、
付费策略），决定按什么顺序派发执行层任务，以及把监督层的意见回派给谁。

### 监督层在干什么

监督层负责**审核任务识别 → 执行流程 → 通用规范 → 总评**。它是这套系统能做到
「多轮创作不崩」的关键：每阶段产出先过审核，有问题当场打回，而不是等到出片才发现
人物换脸了。

---

## 二、11 个画风技能包

| 目录名 | 大致风格 |
|---|---|
| `2D_90s_japanese_anime` | 90 年代日式动画 |
| `2D_chinese_guofeng` | 国风二次元新国潮 |
| `2D_flat_design` | 2D 扁平设计 |
| `2D_mature_urban_romance` | 2D 成熟都市恋爱 |
| `3D_anime_render` | 3D 动漫渲染 |
| `3D_chinese_traditional` | 3D 中式传统 |
| `3D_clay_stopmotion` | 3D 黏土定格 |
| `3D_guofeng_cyber` | 3D 国风赛博 |
| `realpeople_ancient_chinese` | 真人古装 |
| `realpeople_modern_city` | 真人现代都市 |
| `realpeople_urban_modern` | 真人都市现代 |

### 每个画风包固定 12 个文件

```
<风格>/
├── README.md                                       风格定位、适用范围、严禁内容
├── prefix.md                                       ★ 全局美学基础：风格基因 + 色彩盘
├── art_prompt/
│   ├── art_character.md                            人物基础形象
│   ├── art_character_derivative.md                 人物衍生（妆容/发型/服饰/配饰）
│   ├── art_prop.md                                 道具图像
│   ├── art_prop_derivative.md                      道具衍生状态
│   ├── art_scene.md                                场景图
│   ├── art_scene_derivative.md                     场景衍生（景别/时段/天候/角度）
│   └── art_storyboard_video.md                     视频提示词的视觉风格约束
├── driector_skills/
│   ├── director_planning_style.md                  叙事规划阶段的风格技法
│   ├── director_storyboard.md                      分镜提示词的风格专属技法
│   └── director_storyboard_table_style.md          分镜表的风格约束
└── images/                                         风格示例图
```

> ⚠️ 注意目录名是 **`driector_skills`** —— 上游把 director 拼错了，但**必须照抄**。
> 写成 `director_skills` 不会报错，只会静默不加载，你会以为风格没生效。

**`prefix.md` 是画风包的核心**。它定义「风格基因」和「全局色彩盘」：一级/二级风格、
情感基调、质感锚词，以及带色值的核心色盘（如月白 `#E8EAF5`、朱红 `#C93752`）。
所有其他文件都从它派生。改风格先改它。

画风包还分三层约束强度：

| 层级 | 强度 | 说明 |
|---|---|---|
| L1 硬约束 | 高 | 不可突破的风格基线 |
| L2 软约束 | 中 | 可按情绪微调 |
| L3 例外 | 低 | 特殊场景可临时突破局部 |

---

## 三、12 个题材技能包

| 目录名 | 大致题材 |
|---|---|
| `Comedy_humor` | 喜剧幽默 |
| `Coming_of_age` | 成长 |
| `Family_warmth` | 家庭温情 |
| `Historical_epic` | 历史史诗 |
| `Horror_supernatural` | 恐怖灵异 |
| `Hot_blooded_action` | 热血少年 |
| `Mystery_thriller` | 悬疑惊悚 |
| `Psychological_drama` | 心理剧 |
| `Scifi_post_apocalypse` | 科幻末世 |
| `Sweet_romance_novel` | 甜宠言情 |
| `Urban_workplace_drama` | 都市职场 |
| `Xianxia_fantasy` | 仙侠 |

### 每个题材包只有 4 个文件

```
<题材>/
├── README.md
├── driector_skills/
│   ├── director_planning_narrative.md                 叙事规划手法
│   └── director_storyboard_table_narrative.md         分镜表叙事手法
└── images/title.png
```

比画风包轻得多，因为**题材不改变画面，只改变怎么讲故事**。

以「热血少年」为例，它的核心理念是：

- **燃点递进** —— 热血不是一直高燃，而是从低谷一步步攀升到爆发，落差越大燃感越强
- **信念可视化** —— 抽象的信念要用具象的动作、眼神、伤痕外化
- **以弱胜强** —— 核心魅力来自「明知不可为而为之」
- **伙伴共振** —— 伙伴的信任、牺牲与回归是最强催泪燃点

这些理念会具体落成六节叙事要点：主题立意、燃点节奏、分场景情绪、声音与音乐方向、
构图与景别叙事、镜头运动与节奏。

---

## 四、改提示词的正确姿势

1. **改前先备份**：`data/skills/` 整个目录拷一份。改坏了能回滚。
2. **一次只改一处**：同时改骨架和分镜表，出了问题不知道是谁的。
3. **改完拿同一段原著重跑**：前后对比才看得出效果。
4. **重启或刷新**：技能清单由后端读取（`src/routes/setting/skillManagement/getSkillList.ts`），
   改完文件后刷新页面让列表重载。

**不建议改的**：13 个 Agent 提示词里的「严格线性、不可回退」标注和「红线」清单。
那些是上游用大量真实跑批换来的约束，删掉短期看不出问题，长期产出会明显变差。

---

## 五、自己做一个

画风包和题材包都可以自己加。完整规范见 `custom-skills.md`，
脚手架脚本见 `scripts/new_toonflow_skill.py`。
