"""artboard 脚本索引生成器(08 迭代 D-08-3):registry.json + docs/scripts.md。

为什么存在:脚本信息曾"三处并存"(SKILL 12 条 / README ~40 条 / 各册零散)= 多真相源。
本生成器把"哪个脚本在哪册被提到"变成**机器可读的生成物**:
- purpose = 脚本自身 docstring 首行(权威说明就是 --help,分册只写用途不抄参数);
- used_by = 扫 SKILL.md / README.md / references/**/*.md / docs/*.md / fonts/*.md 里的
  脚本名出现(就近索引,允许跨册重复);
- internal 白名单:`_*.py` 内部模块 + 维护/配置工具(junction/config_gui/gen_script_index/selfcheck)。

用法:
  python scripts/gen_script_index.py           # 重新生成 scripts/registry.json + docs/scripts.md
  python scripts/gen_script_index.py --check   # 校验生成物与当前状态一致(CI 用;退出码 1 = 过期)

只生成,不手改:registry.json / docs/scripts.md 由本工具重建。
"""

from __future__ import annotations

import datetime
import glob
import io
import json
import os
import re
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPTS)
INTERNAL = {"junction.py", "config_gui.py", "gen_script_index.py", "selfcheck.py"}
SCAN_GLOBS = ["SKILL.md", "README.md", "references/**/*.md", "docs/*.md", "fonts/*.md",
              "tools/**/*.md"]


def docstring_purpose(path: str) -> str:
    """docstring 首个非空行(模块 docstring 优先;取到 80 字)。"""
    with io.open(path, encoding="utf-8", errors="replace") as f:
        text = f.read(4000)
    m = re.match(r'^\s*(?:#.*\n)*\s*"""(.*?)"""', text, re.S)
    if not m:
        m = re.match(r"^\s*(?:#.*\n)*\s*'''(.*?)'''", text, re.S)
    if m:
        for line in m.group(1).strip().splitlines():
            line = line.strip()
            if line:
                return line[:80]
    return ""


def scan_mentions() -> dict[str, list[str]]:
    """脚本名 → 提到它的文档列表(相对技能根;去重排序)。"""
    used: dict[str, list[str]] = {}
    files: list[str] = []
    for g in SCAN_GLOBS:
        files.extend(glob.glob(os.path.join(SKILL, g), recursive=True))
    script_names = [fn for fn in sorted(os.listdir(SCRIPTS)) if fn.endswith(".py")]
    for doc in sorted(set(files)):
        try:
            with io.open(doc, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        rel = os.path.relpath(doc, SKILL).replace("\\", "/")
        for fn in script_names:
            if fn in text:
                used.setdefault(fn, []).append(rel)
    return used


def build() -> dict:
    used = scan_mentions()
    entries = []
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py"):
            continue
        internal = fn.startswith("_") or fn in INTERNAL
        entries.append({
            "name": fn,
            "group": "内部/维护" if internal else "脚本",
            "internal": internal,
            "purpose": docstring_purpose(os.path.join(SCRIPTS, fn)),
            "used_by": sorted(used.get(fn, [])),
        })
    return {"_comment": "generated, do not edit — 由 scripts/gen_script_index.py 重建",
            "generated_at": datetime.date.today().isoformat(),
            "scripts": entries}


def write_outputs(reg: dict) -> tuple[str, str]:
    reg_path = os.path.join(SCRIPTS, "registry.json")
    with io.open(reg_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    lines = ["# artboard 脚本总表(生成物)",
             "",
             f"> 由 `scripts/gen_script_index.py` 生成 @ {reg['generated_at']};**不要手改**。",
             "> 权威参数 = 各脚本 `--help`;分册末尾「本册用到的脚本」是就近索引。",
             ""]
    for internal, label in ((False, "脚本"), (True, "内部 / 维护(白名单,不进 Agent 上下文)")):
        rows = [e for e in reg["scripts"] if e["internal"] == internal]
        lines += [f"## {label}({len(rows)}个)", "",
                  "| 脚本 | 用途(=docstring 首行) | 被哪些文档提到 |", "|---|---|---|"]
        for e in rows:
            docs = "、".join(e["used_by"][:6]) + ("…" if len(e["used_by"]) > 6 else "")
            purpose = e["purpose"].replace("python", "")  # 防生成物行被判为「python … .py」调用(selfcheck refs)
            lines.append(f"| {e['name']} | {purpose} | {docs or '—'} |")
        lines.append("")
    docs_path = os.path.join(SKILL, "docs", "scripts.md")
    with io.open(docs_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return reg_path, docs_path


def main() -> int:
    check = "--check" in sys.argv
    reg = build()
    reg_path = os.path.join(SCRIPTS, "registry.json")
    if check:
        try:
            with io.open(reg_path, encoding="utf-8") as f:
                current = json.load(f)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": "REGISTRY_MISSING", "detail": str(exc)},
                             ensure_ascii=False))
            return 1
        if current.get("scripts") != reg["scripts"]:
            print(json.dumps({"ok": False, "error": "REGISTRY_STALE",
                              "hint": "跑 python scripts/gen_script_index.py 重建"}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "cmd": "gen_script_index --check",
                          "count": len(reg["scripts"])}, ensure_ascii=False))
        return 0
    rp, dp = write_outputs(reg)
    orphan = [e["name"] for e in reg["scripts"] if not e["internal"] and not e["used_by"]]
    print(json.dumps({"ok": True, "cmd": "gen_script_index", "registry": rp, "docs": dp,
                      "count": len(reg["scripts"]), "internal": sum(1 for e in reg["scripts"] if e["internal"]),
                      "orphan_noninternal": orphan or None,
                      "hint": "有孤儿 → 给该脚本挂到某册「本册用到的脚本」" if orphan else None},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
