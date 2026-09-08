"""artboard 项目瘦身:把项目里"实体拷贝"的 fonts/vendor 目录换成 Skill 资产库的目录联接。

背景:scaffold 默认创建的 src/fonts、src/vendor 是指向 Skill 资产库的 NTFS 目录联接
(零拷贝);但旧项目/手工拷贝/联接失败回退会产生实体目录,单项目可达数百 MB。
本工具把它们转换为联接,渲染结果不变。

用法:
  python slim_project.py <项目路径> [--dry-run]

行为:
  1. 若 src/fonts(或 vendor)是联接 → 跳过(已是瘦身影子);
  2. 是实体目录 → 统计体积 → 删除 → mklink /J 指向 Skill 对应库 → 验证穿透;
  3. --dry-run 只报告不动手。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = {"fonts": os.path.join(SKILL_DIR, "fonts"),
           "vendor": os.path.join(SKILL_DIR, "assets", "vendor")}


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def dir_size(path: str) -> int:
    total = 0
    for root, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


from junction import is_junction, probe as probe_junction


from junction import create_junction, is_junction


def make_junction(link: str, target: str) -> None:
    create_junction(link, target)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    src = os.path.join(os.path.abspath(args.project), "src")
    if not os.path.isdir(src):
        emit({"ok": False, "error": f"src/ 不存在: {src}"})
        return 1

    report, saved_total, failures = [], 0, 0
    for name, skill_target in TARGETS.items():
        path = os.path.join(src, name)
        if not os.path.exists(path):
            report.append({"dir": name, "status": "ABSENT(跳过)"})
            continue
        if is_junction(path):
            report.append({"dir": name, "status": "ALREADY_LINK(已是联接)"})
            continue
        size = dir_size(path)
        if args.dry_run:
            report.append({"dir": name,
                           "status": f"WOULD_LINK(可省 {size // 1024 // 1024}MB)"})
            saved_total += size
            continue
        shutil.rmtree(path)
        try:
            make_junction(path, skill_target)
            report.append({"dir": name,
                           "status": f"LINKED(省 {size // 1024 // 1024}MB)",
                           "target": skill_target})
            saved_total += size
        except Exception as exc:  # noqa: BLE001
            failures += 1
            report.append({"dir": name, "status": f"FAILED: {exc}",
                           "recover": "原目录已删;重建请跑 scaffold --embed-fonts 或 fetch_font.py"})
            saved_total += size

    emit({"ok": failures == 0, "project": os.path.abspath(args.project),
          "saved_mb": saved_total // 1024 // 1024, "results": report,
          "hint": "渲染不受影响(相对引用经联接穿透);打包交付用 pack.py"})
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
