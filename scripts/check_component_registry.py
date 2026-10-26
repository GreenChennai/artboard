#!/usr/bin/env python3
"""组件注册体系机检:三层索引一致性 + token 契约 + 来源红线。

为什么存在(24 迭代):组件注册表的价值在"缺索引 = 不存在",但人工维护的
三处落点(类目 INDEX / MASTER / 组件 frontmatter)必然漂移。本脚本把漂移变成
退出码,供 PIPELINE Step 4 与 CI 直接调用。

校验项:
  1. registry 根文件齐全(TOKENS/MASTER/PIPELINE),components/README.md 存在。
  2. 每个类目目录有 INDEX.md;INDEX 行 ID 与组件文件双向一致(缺一即 FAIL)。
  3. 组件 frontmatter:id == 文件名、category == 所在目录、tokens 已在 TOKENS 登记。
  4. MASTER.md 的 ID 集合与组件文件集合完全一致,无重复。
  5. 组件禁止引用已移除的 shader-effects-inc/shaders 视觉源。
  6. SKILL.md 有"组件库(按需加载)"段,行数 ≤ 26,索引路径真实存在。
  7. 组件文件 > 100 行必须带 "## 目录"(否则建议拆分)。

用法:
  python scripts/check_component_registry.py          # 人读报告
  python scripts/check_component_registry.py --quiet  # 只输出 FAIL/WARN
退出码:0 = 全部通过;1 = 存在 FAIL。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "components" / "registry"
SKILL = ROOT / "SKILL.md"
TOKENS = REG / "TOKENS.md"
MASTER = REG / "MASTER.md"
PIPELINE = REG / "PIPELINE.md"
COMP_README = ROOT / "components" / "README.md"

CATEGORIES = {
    "layout": "版式",
    "typography": "文字",
    "ornament": "装饰",
    "data-display": "数据",
    "feedback": "状态与反馈",
    "style-presets": "风格预设",
}
STYLES = {"新中式", "赛博", "玻璃拟态", "极简"}
BANNED_SOURCES = ("shader-effects-inc/shaders",)
SKILL_SECTION_MAX_LINES = 26

FAILS: list[str] = []
WARNS: list[str] = []
PASSES: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


def ok(msg: str) -> None:
    PASSES.append(msg)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    raw = text[3:end].strip("\n")
    body = text[end + 4:]
    meta = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip('"').strip("'")
                         for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip('"').strip("'")
    return meta, body


def registered_tokens() -> set[str]:
    if not TOKENS.is_file():
        fail("components/registry/TOKENS.md 不存在")
        return set()
    return set(re.findall(r"(--ab-[a-z0-9-]+)\s*:", read(TOKENS)))


def index_ids(path: Path) -> list[str]:
    ids: list[str] = []
    for line in read(path).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        for token in re.findall(r"`([a-z0-9-]+\.[a-z0-9-]+)`", line):
            if token not in ids:
                ids.append(token)
    return ids


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    for p in (TOKENS, MASTER, PIPELINE, COMP_README):
        if not p.is_file():
            fail("缺少根文件:" + str(p.relative_to(ROOT)))
    if FAILS:
        report(quiet)
        return 1

    tokens = registered_tokens()
    components = {}

    for cat in CATEGORIES:
        cdir = REG / cat
        if not cdir.is_dir():
            fail("缺少类目目录:" + str(cdir.relative_to(ROOT)))
            continue
        index = cdir / "INDEX.md"
        if not index.is_file():
            fail(cat + ":缺少 INDEX.md(目录不存在于注册体系)")
            continue
        listed = index_ids(index)
        files = sorted(p for p in cdir.glob("*.md") if p.name != "INDEX.md")
        stems = [p.stem for p in files]
        if not files:
            fail(cat + ":INDEX 存在但类目下没有组件文件")
        for cid in listed:
            if cid not in stems:
                fail(cat + ":INDEX 列了 " + cid + " 但 " + cid + ".md 不存在(坏链接)")
        for stem in stems:
            if stem not in listed:
                fail(cat + ":组件 " + stem + ".md 未登记在 INDEX.md(缺索引 = 不存在)")
            prefixes = {cat, cat[:-1] if cat.endswith("s") else cat}
            if not any(stem.startswith(p + ".") for p in prefixes):
                fail(cat + ":文件 " + stem + ".md 的 ID 前缀应为 " + "/".join(sorted(prefixes)) + ".")
            text = read(cdir / (stem + ".md"))
            parsed = parse_frontmatter(text)
            if parsed is None:
                fail(cat + "/" + stem + ".md:缺少 frontmatter")
                continue
            meta, body = parsed
            if meta.get("id") != stem:
                fail(cat + "/" + stem + ".md:frontmatter id=" + repr(meta.get("id")) + " != 文件名 " + stem)
            if meta.get("category") != cat:
                fail(cat + "/" + stem + ".md:frontmatter category=" + repr(meta.get("category")) + " != " + cat)
            declared = meta.get("tokens") or []
            if not isinstance(declared, list):
                declared = [declared]
            for t in declared:
                if t not in tokens:
                    fail(cat + "/" + stem + ".md:token " + t + " 未在 TOKENS.md 登记")
            used = set(re.findall(r"var\((--ab-[a-z0-9-]+)", body))
            used |= set(re.findall(r"^\s*(--ab-[a-z0-9-]+)\s*:", body, re.M))
            for t in sorted(used - set(declared)):
                fail(cat + "/" + stem + ".md:CSS 使用 " + t + " 但未列入 frontmatter tokens")
            for t in sorted(set(declared) - used):
                warn(cat + "/" + stem + ".md:声明了 " + t + " 但正文未使用")
            styles = meta.get("styles") or []
            if not isinstance(styles, list):
                styles = [styles]
            for s in styles:
                if s not in STYLES:
                    warn(cat + "/" + stem + ".md:未知风格标签 " + repr(s))
            for banned in BANNED_SOURCES:
                if banned in text:
                    fail(cat + "/" + stem + ".md:引用了已移除的视觉源 " + banned)
            nlines = len(text.splitlines())
            if nlines > 100 and "## 目录" not in text:
                fail(cat + "/" + stem + ".md:超过 100 行但缺 ## 目录(拆分或加目录)")
            components[stem] = {"category": cat, "lines": nlines}
        ok(cat + ":" + str(len(stems)) + " 组件,INDEX 与文件一致")

    master_ids = index_ids(MASTER)
    dup = {i for i in master_ids if master_ids.count(i) > 1}
    for d in sorted(dup):
        fail("MASTER.md:ID " + d + " 重复")
    missing = sorted(set(components) - set(master_ids))
    extra = sorted(set(master_ids) - set(components))
    for m in missing:
        fail("MASTER.md:缺少组件 " + m)
    for e in extra:
        fail("MASTER.md:列了不存在的组件 " + e)
    if not missing and not extra:
        ok("MASTER.md:" + str(len(master_ids)) + " 条与组件文件一致")

    if not SKILL.is_file():
        fail("SKILL.md 不存在")
    else:
        skill_text = read(SKILL)
        heading = "## 组件库(按需加载)"
        if heading not in skill_text:
            fail("SKILL.md:缺少 " + heading + " 路由段")
        else:
            start = skill_text.index(heading)
            nxt = skill_text.find("\n## ", start + 3)
            section = skill_text[start:nxt if nxt > 0 else len(skill_text)]
            lines = [l for l in section.splitlines() if l.strip()]
            if len(lines) > SKILL_SECTION_MAX_LINES:
                fail("SKILL.md:组件段 " + str(len(lines)) + " 行,超过上限 " + str(SKILL_SECTION_MAX_LINES) + " 行(主入口只做路由)")
            for cat in CATEGORIES:
                rel = "components/registry/" + cat + "/INDEX.md"
                if rel not in section:
                    fail("SKILL.md:组件段未指向 " + rel)
                elif not (ROOT / rel).is_file():
                    fail("SKILL.md:组件段指向的 " + rel + " 不存在")
            if len(lines) <= SKILL_SECTION_MAX_LINES:
                ok("SKILL.md:组件路由段 " + str(len(lines)) + " 行(上限 " + str(SKILL_SECTION_MAX_LINES) + ")")

    report(quiet)
    return 1 if FAILS else 0


def report(quiet: bool) -> None:
    if not quiet:
        for p in PASSES:
            print("PASS  " + p)
    for w in WARNS:
        print("WARN  " + w)
    for f in FAILS:
        print("FAIL  " + f)
    total = len(PASSES) + len(WARNS) + len(FAILS)
    print("\n组件注册体系:" + str(total - len(FAILS)) + " / " + str(total) + " 项通过"
          + "(" + str(len(FAILS)) + " FAIL," + str(len(WARNS)) + " WARN)")
    if FAILS:
        print("修复路径见 components/registry/PIPELINE.md Step 3(注册与挂载)/ Step 4(回归验证)。")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))