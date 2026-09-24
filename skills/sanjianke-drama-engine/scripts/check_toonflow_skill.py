#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验一个 Toonflow 技能包目录结构是否完整。

用法：
    python3 check_toonflow_skill.py <技能包目录>
    python3 check_toonflow_skill.py <目录> --json

覆盖两类：
    画风包 art_skills/<风格>/    需 11 个文件
    题材包 story_skills/<题材>/  需 3 个文件

只读文件系统，不联网。
"""
import argparse
import json
import sys
from pathlib import Path

DIRECTOR_DIR = "driector_skills"   # 上游的拼写，不是 director_skills

ART_REQUIRED = [
    "README.md",
    "prefix.md",
    "art_prompt/art_character.md",
    "art_prompt/art_character_derivative.md",
    "art_prompt/art_prop.md",
    "art_prompt/art_prop_derivative.md",
    "art_prompt/art_scene.md",
    "art_prompt/art_scene_derivative.md",
    "art_prompt/art_storyboard_video.md",
    DIRECTOR_DIR + "/director_planning_style.md",
    DIRECTOR_DIR + "/director_storyboard.md",
    DIRECTOR_DIR + "/director_storyboard_table_style.md",
]

STORY_REQUIRED = [
    "README.md",
    DIRECTOR_DIR + "/director_planning_narrative.md",
    DIRECTOR_DIR + "/director_storyboard_table_narrative.md",
]


def detect(root):
    """按已有文件判断这是画风包还是题材包。"""
    has_prefix = (root / "prefix.md").is_file()
    has_art = (root / "art_prompt").is_dir()
    if has_prefix or has_art:
        return "art", ART_REQUIRED
    return "story", STORY_REQUIRED


def check(root):
    kind, required = detect(root)
    missing = [r for r in required if not (root / r).is_file()]
    empty = []
    for r in required:
        p = root / r
        if p.is_file() and p.stat().st_size == 0:
            empty.append(r)

    # 常见错误：目录名拼成 director_skills
    warn = []
    if (root / "director_skills").is_dir() and not (root / DIRECTOR_DIR).is_dir():
        warn.append("发现 director_skills 目录，但 Toonflow 读的是 {}，请改名".format(DIRECTOR_DIR))

    # TODO 未填
    todos = []
    for r in required:
        p = root / r
        if p.is_file() and "TODO" in p.read_text(encoding="utf-8"):
            todos.append(r)

    return {
        "目录": str(root),
        "类型": "画风包 art_skills" if kind == "art" else "题材包 story_skills",
        "应有文件": len(required),
        "缺失": missing,
        "空文件": empty,
        "仍是TODO": todos,
        "警告": warn,
        "通过": not missing and not empty and not warn,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="校验 Toonflow 技能包目录结构")
    p.add_argument("path", help="技能包目录")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.path)
    if not root.is_dir():
        print("不是目录：{}".format(root), file=sys.stderr)
        return 2

    r = check(root)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["通过"] else 1

    print("目录：{}".format(r["目录"]))
    print("类型：{}".format(r["类型"]))
    print("应有文件：{} 个".format(r["应有文件"]))
    for key in ("缺失", "空文件", "警告"):
        if r[key]:
            print("\n[!] {}：".format(key))
            for m in r[key]:
                print("    " + m)
    if r["仍是TODO"]:
        print("\n[i] 还是 TODO 的文件 {} 个（结构没问题，只是内容没填）：".format(len(r["仍是TODO"])))
        for m in r["仍是TODO"]:
            print("    " + m)
    print()
    if r["通过"]:
        print("结构校验通过。")
        return 0
    print("结构校验未通过。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
