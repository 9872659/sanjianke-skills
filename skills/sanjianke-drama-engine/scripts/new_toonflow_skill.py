#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一个 Toonflow 技能包骨架（画风包 art_skills 或题材包 story_skills）。

为什么需要它：Toonflow 的画风包有 11 个文件、题材包有 3 个文件，文件名和目录名
必须完全一致才会被加载。手建很容易漏文件或拼错目录名——尤其注意上游把
director 拼成了 `driector_skills`，写错就静默不生效。

用法：
    python3 new_toonflow_skill.py --kind art   --name 2D_ink_wash --out ./my-skills
    python3 new_toonflow_skill.py --kind story --name Time_travel  --out ./my-skills

生成的结构与上游仓库 data/skills/ 保持一致，生成的是带 TODO 的空模板，
不含任何上游风格的具体内容。
"""
import argparse
import sys
from pathlib import Path

TODO = "<!-- TODO: 在这里填写 -->"

# 上游目录名就是这么拼的（director → driector），务必保持一致，否则 Toonflow 加载不到。
DIRECTOR_DIR = "driector_skills"

ART_TREE = [
    ("README.md", """# {name} 风格说明

本风格专为「{name}」题材打造，所有美术提示词、规范和生成内容均严格限定于：

- **一级风格**：（TODO 一句话）
- **二级风格**：（TODO 技法层，例如赛璐璐平涂 / 3D 渲染 / 实拍质感）
- **情感基调**：（TODO）
- **质感锚词**：（TODO 4~6 个词）

## 适用范围

- （TODO 适合哪些题材、哪些生成环节）

## 严禁内容

- （TODO 明确写出本风格不允许出现的画风漂移方向）

## 风格体验

在本风格下，您将体验到：

- （TODO 角色）
- （TODO 场景）
- （TODO 道具）
- （TODO 分镜与渲染）
"""),
    ("prefix.md", """# 全局美学基础 · {name}

---
必须严格、完整遵循下方全部风格约束与全局规则，并严格按提示词模板格式生成提示词；
仅输出提示词正文，不得附加任何解释、说明、注释、标题或其他额外文本。

## 一、风格基因

| 维度 | 定义 |
|---|---|
| **一级风格** | |
| **二级风格** | |
| **情感基调** | |
| **质感锚词** | |

---

## 二、全局色彩盘（风格基线）

### 色彩使用层级

| 层级 | 约束强度 | 说明 |
|---|---|---|
| L1 硬约束 | 高 | |
| L2 软约束 | 中 | |
| L3 例外机制 | 低 | |

### 核心色盘

| 序号 | 色名 | 色值 | 用途 |
|---|---|---|---|
| C1 | | | |
| C2 | | | |
| C3 | | | |
| C4 | | | |
| C5 | | | |
| C6 | | | |

### 硬约束色（默认锁定）

| 色项 | 对应 |
|---|---|
| | |
"""),
    ("art_prompt/art_character.md", """# 人物基础形象生成 · 约束规范

## 一、基础形象原则
{TODO}
## 二、面容约束
### 通用要求
{TODO}
## 三、肤感约束
### 女性
{TODO}
### 男性
{TODO}
## 四、体型约束
### 女性
{TODO}
### 男性
{TODO}
## 五、基础发型约束
### 女性
{TODO}
### 男性
{TODO}
## 六、基础服装约束
### 女性基础服装
{TODO}
### 男性基础服装
{TODO}
### 着装统一规则
{TODO}
## 七、四视图设定图规范
### 视图定义
{TODO}
### 画面规范
{TODO}
## 八、提示词模板
{TODO}
## 九、约束规则
### 必守
{TODO}
### 严禁
{TODO}
"""),
    ("art_prompt/art_character_derivative.md", """# 人物衍生资产生成 · 约束规范

## 一、叠加原则
{TODO}
## 二、叠加层级
{TODO}
## 三、妆容约束（L1）
### 底模到衍生妆造策略（关键）
{TODO}
### 线索分析与妆容决策
{TODO}
### 线索到妆容映射（执行口径）
{TODO}
## 四、发型造型约束（L2）
{TODO}
## 五、服饰约束（L3+L4）
{TODO}
## 六、配饰约束（L5）
{TODO}
## 七、服化组合速查
{TODO}
## 八、四视图设定图规范
### 视图定义
{TODO}
### 画面规范
{TODO}
## 九、提示词模板
{TODO}
## 十、约束规则
### 必守
{TODO}
### 严禁
{TODO}
"""),
    ("art_prompt/art_prop.md", """# 道具图像生成 · 约束规范

## 一、道具设计原则
{TODO}
## 二、道具分类与美学约束
### 2.1 兵器类
{TODO}
### 2.2 饰品类
{TODO}
### 2.3 生活器物类
{TODO}
### 2.4 信物/关键道具类
{TODO}
## 三、多角度设定图规范
### 视图定义
{TODO}
### 画面规范
{TODO}
## 四、材质渲染约束
{TODO}
## 五、提示词模板
{TODO}
## 六、约束规则
### 必守
{TODO}
### 严禁
{TODO}
"""),
    ("art_prompt/art_prop_derivative.md", """# 道具衍生状态生成 · 约束规范

## 一、衍生原则
{TODO}
## 二、状态类型
### 2.1 使用状态
{TODO}
### 2.2 损伤状态
{TODO}
### 2.3 特殊状态
{TODO}
## 三、状态变体画面规范
### 单状态图
{TODO}
### 状态对比图
{TODO}
## 四、材质状态变化规则
{TODO}
## 五、提示词模板
### 单状态变体
{TODO}
## 六、约束规则
### 必守
{TODO}
### 严禁
{TODO}
"""),
    ("art_prompt/art_scene.md", """# 场景图生成 · 约束规范

## 一、场景美学原则
{TODO}
## 二、季节色调映射
{TODO}
## 三、室内场景
### 空间规范
{TODO}
### 室内类型速查
{TODO}
## 四、室外场景
### 空间规范
{TODO}
### 室外类型速查
{TODO}
## 五、主视图规范
### 视图定义
{TODO}
### 画面规范
{TODO}
## 六、提示词模板
{TODO}
## 七、约束规则
### 必守
{TODO}
### 严禁
{TODO}
"""),
    ("art_prompt/art_scene_derivative.md", """# 场景衍生资产生成 · 约束规范

## 一、衍生原则
{TODO}
## 二、景别变体
### 景别定义
{TODO}
### 景别衍生规范
{TODO}
## 三、时段变体
### 时段定义
{TODO}
### 时段衍生规范
{TODO}
## 四、天候变体
### 天候定义
{TODO}
### 天候衍生规范
{TODO}
## 五、角度变体
### 角度定义
{TODO}
### 角度衍生规范
{TODO}
## 六、提示词模板
{TODO}
## 七、约束规则
### 必守
{TODO}
### 严禁
{TODO}
"""),
    ("art_prompt/art_storyboard_video.md", """# 视频提示词 · 视觉风格约束

{TODO 写清本风格在「图生视频」环节必须携带的风格锚定词，以及不该出现的运动/画质问题}
"""),
    (DIRECTOR_DIR + "/director_planning_style.md", """# {name}约束 · 技法参考

## 一、色调体系与画面基调
{TODO}
## 二、光影方案体系
{TODO}
## 三、质感方向
{TODO}
## 四、场景空间元素
{TODO}
## 五、声音与环境音
### 乐器/音色选择
{TODO}
### 组合策略
{TODO}
### 环境音
{TODO}
"""),
    (DIRECTOR_DIR + "/director_storyboard.md", """# 分镜提示词 · {name} · 风格专属技法

## 适用范围
{TODO}
## 情绪 → 面容/眼神词映射
{TODO}
## 光影氛围词库
### 时间段光线
{TODO}
### 情绪光影
{TODO}
## 场景质感约束词（按场景类型）
{TODO}
## 固定风格锚定词（所有输出必须包含）
{TODO}
## 美学禁止项（生成时严格规避）
{TODO}
## 完整生成示例
### 输入（分镜表行数据）
{TODO}
### 示例输出
{TODO}
## 快速参考卡
### 情绪 → 画面词速查
{TODO}
"""),
    (DIRECTOR_DIR + "/director_storyboard_table_style.md", """# 分镜表风格约束 · {name} · 技法参考

## 一、分镜表定位
{TODO}
## 二、光影与氛围
{TODO}
## 三、环境动态
{TODO}
## 四、动作节奏
{TODO}
## 五、材质与质感约束
{TODO}
## 六、色彩约束
{TODO}
## 七、运镜禁忌
{TODO}
"""),
]

STORY_TREE = [
    ("README.md", """# {name} · 导演叙事手法技能包

## 简介

本技能包为 **{name}** 类型故事提供一套完整的导演叙事手法参考，
涵盖从宏观叙事规划到微观分镜执行的全流程指导。适用于任何视觉风格。

## 核心理念

- **（TODO 理念一）** —— （一句话解释）
- **（TODO 理念二）** —— （一句话解释）
- **（TODO 理念三）** —— （一句话解释）

## 文件结构

```
{name}/
├── README.md                                          ← 本文件
└── driector_skills/
    ├── director_planning_narrative.md                 ← 叙事规划手法
    └── director_storyboard_table_narrative.md         ← 分镜表叙事手法
```

## 技能文件说明

### 1. 叙事规划手法 (`director_planning_narrative.md`)

导演在 **叙事规划阶段** 使用的技法参考。

| 章节 | 内容概要 |
|---|---|
| 主题立意与内核 | |
| 叙事结构与节奏 | |
| 分场景情绪设计 | |
| 声音与音乐方向 | |
| 构图与景别叙事 | |
| 镜头运动与节奏 | |

### 2. 分镜表叙事手法 (`director_storyboard_table_narrative.md`)

导演在 **分镜表制作阶段** 使用的技法参考。

| 章节 | 内容概要 |
|---|---|
| 分镜表定位 | |
| 景别选择 | |
| 运镜节奏 | |
| 时长把控 | |
| 关键镜头设计 | |
| 台词处理 | |
| 转场设计 | |

## 使用方式

本技能包作为 Toonflow 导演 AI 的叙事手法参考，在故事创作流程中自动加载，指导：

1. **叙事规划** —— 确定内核、节奏曲线、场景情绪与音乐爆发时机
2. **分镜表生成** —— 根据叙事规划输出具体的景别、运镜、时长与转场方案
"""),
    (DIRECTOR_DIR + "/director_planning_narrative.md", """# 叙事手法 · {name} · 技法参考

## 一、主题立意与内核
### {name}叙事要点
{TODO}
## 二、叙事结构与节奏
### {name}叙事要点
{TODO}
## 三、分场景情绪设计
### {name}叙事要点
{TODO}
## 四、声音与音乐方向
### {name}叙事要点
{TODO}
## 五、构图与景别叙事
### {name}叙事要点
{TODO}
## 六、镜头运动与节奏
### {name}叙事要点
{TODO}
"""),
    (DIRECTOR_DIR + "/director_storyboard_table_narrative.md", """# 分镜表叙事手法 · {name} · 技法参考

## 一、分镜表定位
{TODO}
## 二、景别选择
{TODO}
## 三、运镜节奏
{TODO}
## 四、时长把控
{TODO}
## 五、关键镜头设计
{TODO}
## 六、台词处理
{TODO}
## 七、转场设计
{TODO}
"""),
]


def build(tree, name, out):
    root = out / name
    if root.exists():
        print("目录已存在，未覆盖：{}".format(root), file=sys.stderr)
        return None, []
    written = []
    for rel, tpl in tree:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(tpl.replace("{TODO}", TODO.rstrip("\n")).replace("{name}", name),
                     encoding="utf-8")
        written.append(rel)
    (root / "images").mkdir(exist_ok=True)
    return root, written


def main(argv=None):
    p = argparse.ArgumentParser(description="生成 Toonflow 技能包骨架")
    p.add_argument("--kind", choices=["art", "story"], required=True,
                   help="art = 画风包（放 art_skills），story = 题材包（放 story_skills）")
    p.add_argument("--name", required=True, help="目录名，建议用英文+下划线，如 2D_ink_wash")
    p.add_argument("--out", default=".", help="输出到哪个父目录，默认当前目录")
    args = p.parse_args(argv)

    if not args.name.replace("_", "").replace("-", "").isalnum():
        print("名字建议只用英文、数字、下划线，避免 Toonflow 读取异常", file=sys.stderr)
        return 2
    if "__" in args.name or args.name.startswith((".", "_")):
        print("名字里不要有双下划线或前导下划线", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tree = ART_TREE if args.kind == "art" else STORY_TREE
    where = "art_skills" if args.kind == "art" else "story_skills"

    root, written = build(tree, args.name, out)
    if root is None:
        return 1

    print("已生成 {} 技能包：{}".format("画风" if args.kind == "art" else "题材", root))
    print("  文件 {} 个：".format(len(written)))
    for w in written:
        print("    " + w)
    print("    images/")
    print()
    print("安装：把整个 {} 目录复制到 Toonflow 的 data/skills/{}/ 下，重启或刷新即可。".format(
        args.name, where))
    print("注意：导演目录名是 {}（上游就是这么拼的，别改成 director_skills）。".format(DIRECTOR_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
