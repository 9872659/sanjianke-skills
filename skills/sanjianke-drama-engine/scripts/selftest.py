#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本 Skill 自带脚本的自测。改动任一脚本后先跑这个。

用法：
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/selftest.py -v

只在本机临时目录里跑，不联网、不改动任何已有文件。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
VERBOSE = "-v" in sys.argv

FAILED = []
PASSED = []


def run(script, *args):
    return subprocess.run([PY, str(HERE / script), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(HERE))


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print("  ok   {}".format(name))
    else:
        FAILED.append(name)
        print("  FAIL {}  {}".format(name, detail))


def t_cost():
    print("\n[cost_estimate.py]")
    r = run("cost_estimate.py", "--minutes", "2", "--json")
    check("默认参数能跑通", r.returncode == 0, r.stderr[:200])
    if r.returncode == 0:
        d = json.loads(r.stdout)
        check("复现官方 Demo 量级（¥120~145）", 120 <= d["合计"] <= 145, str(d["合计"]))
        check("视频模型占九成以上", d["视频模型"] / d["合计"] > 0.85,
              str(d["视频模型"] / d["合计"]))
        check("含三项成本", all(k in d for k in ("视频模型", "图片模型", "语言模型")))

    r = run("cost_estimate.py", "--minutes", "2", "--episodes", "30", "--json")
    check("按集数能算出单集成本",
          r.returncode == 0 and "单集成本" in json.loads(r.stdout))

    r = run("cost_estimate.py", "--waste", "1.5")
    check("废片率 >= 1 时报错退出", r.returncode == 2, "returncode={}".format(r.returncode))


def t_scaffold():
    print("\n[new_toonflow_skill.py]")
    with tempfile.TemporaryDirectory() as tmp:
        r = run("new_toonflow_skill.py", "--kind", "art", "--name", "2D_ink_wash", "--out", tmp)
        check("生成画风包成功", r.returncode == 0, r.stderr[:200])
        root = Path(tmp) / "2D_ink_wash"
        check("画风包 12 个文件都在",
              root.is_dir() and len([f for f in root.rglob("*") if f.is_file()]) == 12,
              str(len([f for f in root.rglob("*") if f.is_file()])))
        check("导演目录用上游拼写 driector_skills",
              (root / "driector_skills").is_dir())

        rc = run("check_toonflow_skill.py", str(root))
        check("刚生成的画风包结构校验通过", rc.returncode == 0, rc.stdout[-300:])

        # 重复生成不能覆盖
        r2 = run("new_toonflow_skill.py", "--kind", "art", "--name", "2D_ink_wash", "--out", tmp)
        check("同名目录已存在时拒绝覆盖", r2.returncode == 1)

        r3 = run("new_toonflow_skill.py", "--kind", "story", "--name", "Time_travel", "--out", tmp)
        check("生成题材包成功", r3.returncode == 0, r3.stderr[:200])
        sroot = Path(tmp) / "Time_travel"
        check("题材包 3 个文件都在",
              len([f for f in sroot.rglob("*") if f.is_file()]) == 3)
        check("题材包结构校验通过",
              run("check_toonflow_skill.py", str(sroot)).returncode == 0)

        r4 = run("new_toonflow_skill.py", "--kind", "art", "--name", "bad name!", "--out", tmp)
        check("非法名字被拒绝", r4.returncode == 2)


def t_checker():
    print("\n[check_toonflow_skill.py]")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Broken"
        (root / "art_prompt").mkdir(parents=True)
        (root / "README.md").write_text("# x\n", encoding="utf-8")
        (root / "prefix.md").write_text("# y\n", encoding="utf-8")
        r = run("check_toonflow_skill.py", str(root), "--json")
        d = json.loads(r.stdout)
        check("缺文件时校验不通过", r.returncode == 1 and not d["通过"])
        check("能列出缺了什么", len(d["缺失"]) > 0, str(d["缺失"]))

        # 拼错目录名要报警
        root2 = Path(tmp) / "Typo"
        for rel in ("README.md", "prefix.md"):
            (root2 / rel).parent.mkdir(parents=True, exist_ok=True)
            (root2 / rel).write_text("# x\n", encoding="utf-8")
        (root2 / "director_skills").mkdir(parents=True)
        for rel in ("art_prompt/art_character.md",):
            (root2 / rel).parent.mkdir(parents=True, exist_ok=True)
            (root2 / rel).write_text("# x\n", encoding="utf-8")
        r2 = run("check_toonflow_skill.py", str(root2), "--json")
        check("拼错导演目录名会报警", "director_skills" in r2.stdout)


def main():
    print("Toonflow Skill 自测")
    print("=" * 46)
    t_cost()
    t_scaffold()
    t_checker()
    print("\n" + "=" * 46)
    print("通过 {} 项，失败 {} 项".format(len(PASSED), len(FAILED)))
    if FAILED:
        for f in FAILED:
            print("  FAILED: {}".format(f))
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
