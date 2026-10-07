"""artboard 仓库自检:拦住"文档说有、代码没有"与"同一事实多处不一致"这一类缺陷。

用法:
  python selfcheck.py                 # 全部检查,人类可读
  python selfcheck.py --json          # 单行 JSON(给 CI)
  python selfcheck.py --only build    # 只跑指定项,逗号分隔
  python selfcheck.py --list          # 列出检查项
退出码:0 = 全过;1 = 有 FAIL;2 = 用法错误

检查项(每一项都对应一次真实发生过的缺陷):
  refs   悬空引用        —— Markdown 里写的 scripts/…py、references/…md 是否真存在
  nums   数字一致性      —— 同一事实的多处表述是否一致(字体数/特效数/尺寸/字号下限…)
  cfg    配置契约        —— cfg("k") 读的键 vs 声明处;双向 diff(未声明 / 死配置)
  route  路由完备性      —— references/ 下有无"从未被 SKILL.md 路由表引用"的孤儿分册
  build  构建产物同步    —— 被跟踪的 exe 是否比源码旧(源与产物同仓的维护陷阱)
  smoke  脚本冒烟        —— 每个脚本能 import、CLI 能装配(--help)
  jsonfail 失败路径 JSON —— 关键脚本喂必失败输入,最后一行 stdout 必须能被 json.loads

只读:不改任何文件。CI 里建议 refs/nums/cfg/route/build/jsonfail 全跑,smoke 可按需。
"""

from __future__ import annotations

import argparse
import ast
import builtins
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
REF_DIR = os.path.join(ROOT, "references")

MARKDOWN_GLOBS = ("*.md", "references/**/*.md", "docs/*.md", "docs/map/*.md",
                  "fonts/*.md", "tools/**/*.md", "assets/**/*.md")

# 过程性文档:本地留档、不进仓库(见 .gitignore)。里面记的是"某个提案""某个已删文件",
# 不是现存引用 —— 纳入引用核验只会产生假阳性。
# docs/map/ITERATION.md 与 docs/map/adr/ 同属地图模块的历史留档(命令/路径按并入前
# 布局书写,文件头已有"勿照抄"声明),按同一口径豁免;docs/map/ 下的调研/术语文档
# (**/*.md 一层,不含子目录)参与引用核验。
PROCESS_DOCS = ("docs/ITERATION.md", "docs/review/", "docs/adr/",
                "docs/map/ITERATION.md", "docs/map/adr/", "docs/map/legacy-patches/")

# 设计上豁免 import/CLI 冒烟的脚本(见各自文件头)
SKIP_SMOKE = {
    "export_local.py",   # 禁止在 scripts/ 下运行:import 即 sys.exit(2)
}

# 构建产物 ↔ 源码:改了源码必须重新打包,否则用户拿到的 exe 还是旧的
BUILD_PAIRS = (
    ("scripts/config_gui.py",
     "tools/config-editor/artboard-config-editor.exe",
     "python -m PyInstaller --onefile --windowed --name artboard-config-editor "
     "--distpath tools/config-editor --workpath .build --specpath .build "
     "--noconfirm scripts/config_gui.py"),
)

# 冒烟参数:多数脚本 --help 即可;有副作用(开 GUI / 无 argparse / 会写盘)的另行指定
SMOKE_ARGS = {
    "config_gui.py": ["--locate"],   # --help 会开窗口
    "fetch_font.py": [],             # 无 argparse;空参 = 列状态
    # --help 不被识别 → 会真的重写 registry.json + docs/scripts.md,把工作区弄脏
    "gen_script_index.py": ["--check"],
}
DEFAULT_SMOKE_ARGS = ["--help"]

# 失败路径 JSON 契约:给必失败的输入,断言最后一行 stdout 是合法 JSON
JSONFAIL_CASES = (
    ("gzh_cover.py", ["export", "__nope__"]),
    ("gzh_article.py", ["convert", "__nope__.md", "--out", "__nope__.html"]),
    ("gzh_article.py", ["check", "__nope__.html"]),
    ("vectoredit2webhtml.py", ["__nope__.pdf", "__nope__.html"]),
    ("export_fallback.py", ["--source", "__nope__", "--output", "__nope__.png"]),
    ("ai_export.py", ["__nope__"]),
    ("make_bats.py", ["__nope__"]),
    ("pack.py", ["__nope__"]),
    ("imageops.py", ["convert", "--in", "___nonexistent___.png", "--to", "webp"]),
    ("imageops.py", ["pipeline", "probe"]),          # P* 禁入 pipeline → exit 2
    ("imageops.py", ["convert", "--in", "x.png"]),   # 缺 --to → exit 2
    ("check_brief.py", ["__nope__.txt"]),            # 检查单文件缺失 → 全部必需字段缺失
    ("check_credits.py", ["__nope__img"]),           # img 目录缺失 → JSON 信封
    ("beat_sheet.py", []),                           # 缺 --bpm 与 --list → USAGE JSON
    ("check_svg.py", []),                            # 缺路径 → USAGE JSON
    ("fetch_svg.py", ["iconify"]),                   # 缺 --set/--query → USAGE JSON
    ("pixel.py", []),                                # 空参 → USAGE JSON
    ("pixel.py", ["blend"]),                         # 缺 --in/--top/-o → USAGE JSON(非 traceback)
    ("pixel.py", ["blur-gaussian", "--in", "___nonexistent___.png",
                  "-o", "___nonexistent_out___.png", "--params", "oops"]),
    ("pixel.py", ["recipe", "validate", "___nonexistent___.json"]),
    ("imageops.py", ["stitch", "___nonexistent___.png", "___nonexistent2___.png",
                     "-o", "___nonexistent_out___.png"]),
    ("check_h5.py", ["__nope__.html"]),              # 无 HTML → USAGE JSON
    ("check_slop.py", ["___nonexistent___.html"]),   # 无 HTML → NO_HTML JSON
    ("check_slop.py", ["--only", "PX"]),             # 非法级别 → 用法 JSON
    ("check_review_ui.py", ["--tool", "___nonexistent___"]),   # 工具目录缺 → JSON
    ("check_review_cache.py", []),                              # 缺 --url → USAGE JSON
    ("check_review_cache.py", ["--url", "file:///x.html"]),     # file:// → NEED_HTTP JSON
    ("check_px_baseline.py", ["--new", "___nonexistent___",
                              "--baseline", "___nonexistent___"]),  # 无出图目录 → JSON
    ("doctor.py", ["___nonexistent_dir___", "--json"]),  # 目录不存在 → JSON;且 --json 不得混人类行
    ("gzh_cover.py", ["merge", "___nonexistent___"]),    # 项目不存在 → JSON
)


# ---------------------------------------------------------------- scriptdocs

def check_scriptdocs(rep: Report) -> None:
    """脚本文档覆盖(08 迭代 D-08-5):非 internal 脚本必须在 ≥1 处文档被提及。
    白名单:_*.py 内部模块 + junction/config_gui/gen_script_index/selfcheck(维护工具)。"""
    reg_path = os.path.join(SCRIPTS, "registry.json")
    if not os.path.isfile(reg_path):
        rep.add("scriptdocs", "FAIL", "scripts/registry.json 不存在",
                "跑 python scripts/gen_script_index.py 重建")
        return
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gen_script_index.py"), "--check"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        rep.add("scriptdocs", "FAIL", "registry.json 与实际状态不一致(生成物过期)",
                "跑 python scripts/gen_script_index.py 重建")
        return
    reg = json.loads(read(reg_path))
    orphan = [e["name"] for e in reg.get("scripts", [])
              if not e.get("internal") and not e.get("used_by")]
    stale = [e["name"] for e in reg.get("scripts", [])
             if not e.get("internal")
             and any(not os.path.isfile(os.path.join(ROOT, d)) for d in e.get("used_by", []))]
    if orphan:
        rep.add("scriptdocs", "FAIL", f"孤儿脚本(无任何文档提及):{', '.join(orphan)}",
                "挂到某分册末尾「本册用到的脚本」,或列入 internal 白名单(需在 07 登记理由)")
    if stale:
        rep.add("scriptdocs", "FAIL", f"used_by 指向不存在的文档:{', '.join(stale)}")
    rep.add("scriptdocs", "PASS",
            f"{len(reg.get('scripts', []))} 个脚本全部可达(生成物一致;白名单豁免 internal)")


# ---------------------------------------------------------------- materials / golden

def check_materials(rep: Report) -> None:
    """素材声明 vs 磁盘(06-P):materials.md §4 声明"已落地"的包必须真实存在且非空;
    图标库须 ≥150 枚(05 扩容口径)。防止再出现"声明三套、实际一套"。"""
    # a) 插画包:open-doodles 是唯一声明"已落地"的包
    doodles = os.path.join(ROOT, "assets", "illustrations", "open-doodles")
    n_doodles = len(glob.glob(os.path.join(doodles, "*.svg"))) if os.path.isdir(doodles) else 0
    materials = read(os.path.join(ROOT, "references", "materials.md"))
    if "✅ **已落地**" not in materials and "已落地" not in materials:
        rep.add("materials", "WARN", "materials.md §4 无'已落地'声明行(表述格式变了?核对检查器)")
    if n_doodles == 0:
        rep.add("materials", "FAIL", "声明'已落地'的插画包 open-doodles 磁盘为空/不存在",
                "声明与磁盘必须一致(判据 C);包没了就改 materials.md §4 状态")
    # b) 声明'需人工获取'的包若目录出现了,提示更新状态(诚实正向)
    for name in ("open-peeps", "undraw"):
        d = os.path.join(ROOT, "assets", "illustrations", name)
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.svg")):
            rep.add("materials", "WARN",
                    f"{name} 已有 SVG 落盘,但 materials.md §4 仍标'需人工获取'",
                    "更新 materials.md §4 与 assets/illustrations/README.md 状态")
    # c) 图标库下限
    n_icons = len(glob.glob(os.path.join(ROOT, "assets", "icons", "*.svg")))
    if n_icons < 150:
        rep.add("materials", "FAIL", f"图标库 {n_icons} 枚 < 150(05 扩容口径)")
    rep.add("materials", "PASS",
            f"插画声明一致(open-doodles {n_doodles} SVG)/ 图标 {n_icons} 枚")


def check_golden(rep: Report) -> None:
    """回归基线(06-M):视频动效 5 例 MP4 在位;SVG 固样例 3 好 3 坏判据不漂移。"""
    base_path = os.path.join(ROOT, "docs", "samples", "golden-baselines.json")
    if not os.path.isfile(base_path):
        rep.add("golden", "WARN", "docs/samples/golden-baselines.json 不存在(基线未建)")
        return
    base = json.loads(read(base_path))
    missing = [c for c, v in base.get("video_cases", {}).items()
               if not os.path.isfile(os.path.join(ROOT, v["mp4"]))]
    if missing:
        rep.add("golden", "FAIL", f"基线 MP4 缺失:{', '.join(missing)}",
                "重导 assets/cases/preview 或更新基线")
    # SVG 固样例:check_svg 好样例必须过,坏样例必须报
    good = sorted(glob.glob(os.path.join(ROOT, "docs", "samples", "svg-good", "*.svg")))
    bad = sorted(glob.glob(os.path.join(ROOT, "docs", "samples", "svg-bad", "*.svg")))
    if good:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_svg.py"), *good],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            rep.add("golden", "FAIL", "svg-good 固样例被 check_svg 报错(检查器或样例漂移)")
    if bad:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_svg.py"), *bad],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            rep.add("golden", "FAIL", "svg-bad 固样例未被 check_svg 拦下(检查器钝化)")
    # slop 固样例:好样例必须零 P0/P1(否则规则过严),坏样例必须报出 P0(否则检查器钝化)
    slop_good = os.path.join(ROOT, "docs", "samples", "slop-good")
    slop_bad = os.path.join(ROOT, "docs", "samples", "slop-bad")
    slop_n = 0
    if os.path.isdir(slop_good):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_slop.py"),
                            slop_good, "--strict"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            rep.add("golden", "FAIL", "slop-good 固样例被 check_slop 报出问题(规则过严/假阳性)",
                    "先改规则再改样例;判据见 check_slop.py 文件头")
        slop_n += 1
    if os.path.isdir(slop_bad):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_slop.py"), slop_bad],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            rep.add("golden", "FAIL", "slop-bad 固样例未被 check_slop 报出 P0(检查器钝化)")
        slop_n += 1
    rep.add("golden", "PASS",
            f"基线 {len(base.get('video_cases', {}))} 例在位;SVG 固样例 {len(good)}好/{len(bad)}坏;"
            f"slop 固样例 {slop_n} 组判据稳定")


# ---------------------------------------------------------------- helpers

def is_process_doc(p: str) -> bool:
    r = rel(p)
    return any(r == d or r.startswith(d) for d in PROCESS_DOCS)


def md_files() -> list[str]:
    out: list[str] = []
    for g in MARKDOWN_GLOBS:
        out += glob.glob(os.path.join(ROOT, g), recursive=True)
    keep = {os.path.normpath(p) for p in out if not is_process_doc(p)}
    return sorted(keep)


def read(p: str) -> str:
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def rel(p: str) -> str:
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, check: str, level: str, detail: str, hint: str = "") -> None:
        self.items.append({"check": check, "level": level,
                           "detail": detail, "hint": hint})

    def count(self, level: str) -> int:
        return sum(1 for i in self.items if i["level"] == level)


# ---------------------------------------------------------------- refs

REF_RE = re.compile(
    r"(?<![\w/])((?:\.\./)*)"
    r"((?:references|scripts|docs|assets|fonts|tools)"
    r"/[\w\-./]+\.[A-Za-z0-9]+)")

# 项目级投放脚本:由 scaffold.py 写进 <项目>/src/,**不在 scripts/**。
# 文档里 `python 导出.py` 这种调用是正确写法,不该按 scripts/导出.py 判悬挂。
PROJECT_LEVEL_SCRIPTS = {"导出.py"}

# 已知顶层目录:文档里的 `python tools/…/x.py` 按技能根解析(见 check_refs)
TOP_DIRS = ("scripts", "tools", "docs", "assets", "references", "fonts", "mcp")


def check_refs(rep: Report) -> None:
    checked = 0
    for md in md_files():
        if rel(md) == "CHANGELOG.md":
            continue  # 历史版本记录:引用旧脚本名属正常,不参与悬挂检查
        for lineno, line in enumerate(read(md).splitlines(), 1):
            for m in REF_RE.finditer(line):
                up, ref = m.group(1), m.group(2)
                if any(c in ref for c in "<>*…"):
                    continue                      # 占位符/通配,跳过
                if ref.endswith((".py", ".md")) and ref.startswith("docs/review/"):
                    continue                      # 过程文档,本地生成
                checked += 1
                # 显式 `../` 前缀 → 相对当前文件解析(references/styles/*.md 里
                # `../../fonts/…` 才是对的,历史上这里全漏检);
                # 裸路径仍按技能根解析(既有口径)。
                target = (os.path.normpath(os.path.join(os.path.dirname(md), up + ref))
                          if up else os.path.join(ROOT, ref))
                if up and not os.path.abspath(target).startswith(
                        os.path.abspath(ROOT) + os.sep):
                    continue                      # 指向技能之外,不属本仓库
                if not os.path.isfile(target):
                    rep.add("refs", "FAIL", f"{rel(md)}:{lineno} → {up}{ref} 不存在",
                            "改引用或补文件;重命名脚本时务必全局搜一遍")
    # 代码块里 `python $S/xxx.py` / `python tools/…/x.py` 这类调用。
    # 判据:取最后一个路径段当文件名;若路径里出现过**已知顶层目录**(scripts/tools/…),
    # 就从该目录起按技能根解析 —— 此前只在 scripts/ 下找,tools/ 下的工具脚本
    # (review-station)完全不在门禁覆盖内;`$S/preflight.py` 这类变量前缀也不会误判。
    call_re = re.compile(r"(?:python|python3)[^\n]*?([\w\-./$<>'\"]+\.py)")
    for md in md_files():
        if rel(md) == "CHANGELOG.md":
            continue
        for lineno, line in enumerate(read(md).splitlines(), 1):
            for m in call_re.finditer(line):
                tok = m.group(1)
                parts = [p for p in tok.replace("\\", "/").split("/") if p and p != "."]
                if not parts:
                    continue
                name = parts[-1]
                if name in ("setup.py",) or name in PROJECT_LEVEL_SCRIPTS:
                    continue
                checked += 1
                idx = next((i for i, p in enumerate(parts[:-1]) if p in TOP_DIRS), -1)
                target = (os.path.join(ROOT, *parts[idx:]) if idx >= 0
                          else os.path.join(SCRIPTS, name))
                if not os.path.isfile(target):
                    rep.add("refs", "FAIL",
                            f"{rel(md)}:{lineno} → 调用的 {tok} 不存在",
                            "文档漂移的典型症状:脚本删了/改名了,引用没跟上")
    rep.add("refs", "PASS", f"核验 {checked} 处引用")


# ---------------------------------------------------------------- nums

def _count_effects(text: str) -> int:
    return len(re.findall(r"^#{3,4}\s+(?:fx|tx)-", text, re.M))


def _count_style_directions(text: str) -> int:
    """styles-catalog.md:各节标题声明的 N 之和(与实测条目数应一致)。"""
    return sum(int(n) for n in re.findall(r"^##\s+[^\n(]+\((\d+)", text, re.M))


def _count_vector_bans(text: str) -> int:
    m = re.search(r"五条禁令:(.*?)(?:\n\n|\Z)", text, re.S)
    if m:
        return len(re.findall(r"[①②③④⑤⑥]", m.group(1)))
    m = re.search(r"\*\*五条禁令\*\*", text)
    return 5 if m else 0


def _count_fonts(text: str) -> int:
    try:
        j = json.loads(text)
    except ValueError:
        return -1
    return len([k for k in j if not k.startswith("_")])


def _rollup_height(scaffold_src: str) -> int:
    m = re.search(r'"rollup":\s*\{[^}]*"h":\s*(\d+)', scaffold_src)
    return int(m.group(1)) * 2 if m else -1


NUM_CHECKS = (
    ("字体族数", ("fonts/download.json", _count_fonts),
     (("README.md", r"(\d+) 款开源中英文字体族"),)),
    ("特效式数", ("references/effects.md", _count_effects),
     (("SKILL.md", r"视觉特效 (\d+) 式"),
      ("README.md", r"视觉特效 (\d+) 式"),
      ("references/effects.md", r"视觉特效分册\((\d+) 式"))),
    ("风格方向数", ("references/styles-catalog.md", _count_style_directions),
     (("references/styles-catalog.md", r"^#\s*风格气质总表\((\d+) 方向"),
      ("README.md", r"(\d+) 风格方向速查"))),
    ("矢量禁令条数", ("references/vector-export.md", _count_vector_bans),
     (("README.md", r"五条禁令"), ("docs/glossary.md", r"\*\*五条禁令\*\*"))),
    ("易拉宝导出高", ("scripts/scaffold.py", _rollup_height),
     (("references/export.md", r"4724×(\d+)"),
      ("references/formats/rollup.md", r"4724×(\d+)"))),
)


def check_nums(rep: Report) -> None:
    for name, (src_path, src_fn), mirrors in NUM_CHECKS:
        full = os.path.join(ROOT, src_path)
        if not os.path.isfile(full):
            rep.add("nums", "FAIL", f"{name}:真相源 {src_path} 不存在")
            continue
        expect = src_fn(read(full))
        if expect < 0:
            rep.add("nums", "FAIL", f"{name}:无法从 {src_path} 取到真相值")
            continue
        bad = []
        for mfile, pat in mirrors:
            mfull = os.path.join(ROOT, mfile)
            if not os.path.isfile(mfull):
                bad.append(f"{mfile}(缺)")
                continue
            text = read(mfull)
            if r"(\d" not in pat:
                # 无捕获组 → 存在性断言(如「五条禁令」这类纯文案)
                if not re.search(pat, text, re.M):
                    bad.append(f"{mfile} 未出现 {pat}")
                continue
            found = [int(x) for x in re.findall(pat, text, re.M)]
            if not found:
                bad.append(f"{mfile} 未匹配 {pat}")
            elif any(f != expect for f in found):
                bad.append(f"{mfile}={found}")
        if bad:
            rep.add("nums", "FAIL", f"{name}:真相值 {expect},镜像 {'; '.join(bad)}",
                    f"以 {src_path} 为准改镜像处")
    rep.add("nums", "PASS", f"核验 {len(NUM_CHECKS)} 组数字一致性")


# ---------------------------------------------------------------- cfg

def cfg_keys_read() -> dict[str, set[str]]:
    """只认**真实的 cfg(...) 调用**(走 AST),不扫注释/文档字符串 —— 否则本文件
    docstring 里的示例 `cfg("k")` 会被当成真读键。"""
    out: dict[str, set[str]] = {}
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py"):
            continue
        try:
            tree = ast.parse(read(os.path.join(SCRIPTS, fn)))
        except SyntaxError:
            continue
        keys: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            fname = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if fname not in ("cfg", "cfg_raw"):
                continue
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                keys.add(a0.value)
        if keys:
            out[fn] = keys
    return out


def cfg_keys_declared() -> set[str]:
    declared: set[str] = set()
    ex = os.path.join(ROOT, "config.example.json")
    if os.path.isfile(ex):
        try:
            declared |= {k for k in json.loads(read(ex)) if not k.startswith("_")}
        except ValueError:
            pass
    envs = read(os.path.join(SCRIPTS, "_config.py"))
    m = re.search(r"ENV_MAP\s*=\s*\{(.*?)\n\}", envs, re.S)
    if m:
        declared |= set(re.findall(r'"(\w+)":', m.group(1)))
    gui = os.path.join(SCRIPTS, "config_gui.py")
    if os.path.isfile(gui):
        try:
            tree = ast.parse(read(gui))
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                        getattr(t, "id", "") == "FIELDS" for t in node.targets):
                    for elt in getattr(node.value, "elts", []):
                        if elt.elts and isinstance(elt.elts[0], ast.Constant):
                            declared.add(elt.elts[0].value)
        except SyntaxError:
            pass
    return declared


# 在 scripts/ 之外被消费的配置键:自检的 AST 只扫 scripts/*.py,这些键会被
# 误报成"死配置"。逐条写明消费方,便于日后核对(新增豁免必须带理由)。
EXTERNAL_KEYS = {
    "huaban_cookie": "tools/asset-bridge/popup.js(浏览器扩展读登录态并写回)",
    "bridge_token_ttl": "mcp/artboard-mcp 的 Bridge 会话 TTL(references/mcp-assets.md §2)",
    "ocr_path": "fetch_model.py 的 MODULES 目标路径键(写配置,非 cfg 调用)",
}


def check_cfg(rep: Report) -> None:
    read_map = cfg_keys_read()
    declared = cfg_keys_declared()
    read_all = set().union(*read_map.values()) if read_map else set()

    missing = sorted(read_all - declared)
    if missing:
        rep.add("cfg", "FAIL", f"脚本在读但无处声明:{', '.join(missing)}",
                "用户拿不到这些键名:GUI 与 config.example.json 都要补")
    orphan = sorted(declared - read_all - set(EXTERNAL_KEYS))
    if orphan:
        rep.add("cfg", "WARN", f"已声明但无脚本读取(可能是死配置):{', '.join(orphan)}",
                "确认是否废弃;留着会让人以为有用")
    rep.add("cfg", "PASS",
            f"读键 {len(read_all)} 个 / 声明 {len(declared)} 个"
            f"(另 {len(EXTERNAL_KEYS)} 个在 scripts/ 之外消费,已豁免)")


# ---------------------------------------------------------------- route

def check_route(rep: Report) -> None:
    skill = os.path.join(ROOT, "SKILL.md")
    if not os.path.isfile(skill):
        rep.add("route", "FAIL", "SKILL.md 不存在")
        return
    text = read(skill)
    covered = set(re.findall(r"references/[\w\-./]+\.md", text))
    covered |= set(re.findall(r"docs/[\w\-./]+\.md", text))
    covered_dirs = {c.rsplit("/", 1)[0] + "/" for c in covered}
    actual = {rel(p) for p in glob.glob(os.path.join(REF_DIR, "**", "*.md"),
                                        recursive=True)}
    # docs/ 顶层 md 同样要"有路由才存在"(过程文档见 PROCESS_DOCS,已排除);
    # docs/map/** 属于地图子技能自己的索引(references/map-studio.md §八),不在此列。
    actual |= {rel(p) for p in glob.glob(os.path.join(ROOT, "docs", "*.md"))}
    orphan = []
    for f in sorted(actual):
        if f in covered:
            continue
        d = f.rsplit("/", 1)[0] + "/"
        if d in covered_dirs or any(f.startswith(c) for c in covered_dirs):
            continue
        orphan.append(f)
    if orphan:
        rep.add("route", "FAIL",
                f"孤儿分册(未被 SKILL.md 路由表引用):{', '.join(orphan)}",
                "渐进披露下=不存在;补一行路由或删除文件")
    rep.add("route", "PASS", f"路由覆盖 {len(actual) - len(orphan)}/{len(actual)} 个分册")


# ---------------------------------------------------------------- build

def check_build(rep: Report) -> None:
    for src_rel, out_rel, cmd in BUILD_PAIRS:
        src = os.path.join(ROOT, src_rel)
        out = os.path.join(ROOT, out_rel)
        if not os.path.isfile(src):
            continue
        if not os.path.isfile(out):
            rep.add("build", "FAIL", f"{out_rel} 缺失(源码 {src_rel} 存在)",
                    f"重新打包:{cmd}")
            continue
        if os.path.getmtime(out) < os.path.getmtime(src):
            import time
            rep.add("build", "FAIL",
                    f"{out_rel} 比 {src_rel} 旧"
                    f"({time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(out)))}"
                    f" < {time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(src)))})",
                    f"用户拿到的仍是旧版,重新打包:{cmd}")
    rep.add("build", "PASS", f"核验 {len(BUILD_PAIRS)} 对构建产物")


# ---------------------------------------------------------------- smoke

def check_smoke(rep: Report) -> None:
    n = 0
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py") or fn.startswith("_") or fn in SKIP_SMOKE:
            continue
        mod = fn[:-3]
        n += 1
        r = subprocess.run(
            [sys.executable, "-c",
             f"import sys;sys.path.insert(0,r'{SCRIPTS}');import {mod}"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=90, cwd=ROOT)
        if r.returncode != 0:
            rep.add("smoke", "FAIL", f"{fn} import 失败",
                    (r.stderr or r.stdout).strip().splitlines()[-1][:200])
            continue
        args = SMOKE_ARGS.get(fn, DEFAULT_SMOKE_ARGS)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, fn), *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, cwd=ROOT)
        if r.returncode not in (0, 1):
            rep.add("smoke", "FAIL", f"{fn} {' '.join(args) or '(空参)'} 退出 {r.returncode}",
                    (r.stderr or r.stdout).strip().splitlines()[-1][:200])
    rep.add("smoke", "PASS", f"冒烟 {n} 个脚本")


# ---------------------------------------------------------------- stale

STALE_KEYS = ("wpi_path", "wpi_cli_exe", "setup_wpi", "ARTBOARD_WPI",
              "wpi_not_found", "wpi_import_failed", "wpi")

# 历史注记允许词:正文里写"WPI 时代概念,v1.9 起消亡/已退役"是**要求**的写法
# (glossary / animation 的历史段),不该判违规;缺这些词的裸 WPI 才是漂移。
STALE_OK_WORDS = ("退役", "已删除", "已移除", "均已删除", "消亡", "时代", "v1.9 起",
                  "v1.8 及以前")


def check_stale(rep: Report) -> None:
    """过期引用扫描:SKILL.md / references/** / docs/*.md 不得出现 v1.8 已退役的
    WPI 配置键/错误码/裸引擎名;带"已退役/已消亡"注记的历史说明行豁免。
    (历史上这里只扫 references/ 一层、且键里没有裸 `wpi` —— forms/ 与 animation
    的残留因此长期免检。)"""
    root = os.path.dirname(SCRIPTS)
    targets = [os.path.join(root, "SKILL.md")]
    refs = os.path.join(root, "references")
    if os.path.isdir(refs):
        targets.extend(sorted(glob.glob(os.path.join(refs, "**", "*.md"),
                                        recursive=True)))
    docs = os.path.join(root, "docs")
    if os.path.isdir(docs):
        targets.extend(sorted(glob.glob(os.path.join(docs, "*.md"))))
    n = hits = 0
    for f in targets:
        if not os.path.isfile(f):
            continue
        if rel(f) in PROCESS_DOCS or rel(f).startswith("docs/review/"):
            continue
        for ln, line in enumerate(open(f, encoding="utf-8").read().splitlines(), 1):
            low = line.lower()
            if any(k in low for k in STALE_KEYS):
                n += 1
                if any(w in line for w in STALE_OK_WORDS):
                    continue
                hits += 1
                rep.add("stale", "FAIL",
                        f"{rel(f)}:{ln} 出现已退役 WPI 键: {line.strip()[:90]}",
                        "v1.9 已 WPI 退役;若为历史记录请加「WPI 时代概念,v1.9 起消亡」注记")
    rep.add("stale", "PASS" if hits == 0 else "FAIL",
            f"过期引用扫描 {n} 处提及 / {hits} 处违规")


# ---------------------------------------------------------------- deploy

def check_deploy(rep: Report) -> None:
    """投放脚本(export_local.py → <项目>/src/导出.py)名称解析门禁:
    AST 层校验「被调用即有定义/导入」,拦截 v1.9 的 find_kiln NameError
    (import 级冒烟查不出只调用无定义)。"""
    src = os.path.join(SCRIPTS, "export_local.py")
    if not os.path.isfile(src):
        rep.add("deploy", "WARN", "export_local.py 不存在,跳过")
        return
    with open(src, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    defined: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(n.name)
        elif isinstance(n, ast.Import):
            defined.update(a.asname or a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            defined.update(a.asname or a.name for a in n.names)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)
        elif isinstance(n, ast.Try):
            pass
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    missing = calls - defined - set(dir(builtins))
    if missing:
        rep.add("deploy", "FAIL",
                f"export_local.py 调用了未定义的名称: {', '.join(sorted(missing))}",
                "投放后运行即 NameError;补定义或删调用")
        return
    # 死函数扫描:find_wpi 等 WPI 时代残留不得回流
    dead = [d for d in defined if "wpi" in d.lower()]
    if dead:
        rep.add("deploy", "FAIL", f"export_local.py 残留 WPI 时代函数: {', '.join(dead)}",
                "v1.9 已 WPI 退役,应替换为 find_kiln")
        return
    rep.add("deploy", "PASS", "投放脚本名称解析 + WPI 残留扫描")


# ---------------------------------------------------------------- jsonfail

def check_jsonfail(rep: Report) -> None:
    n = 0
    for fn, args in JSONFAIL_CASES:
        path = os.path.join(SCRIPTS, fn)
        if not os.path.isfile(path):
            continue
        n += 1
        r = subprocess.run([sys.executable, path, *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180, cwd=ROOT)
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
        ok = False
        if lines:
            try:
                json.loads(lines[-1])
                ok = True
            except ValueError:
                ok = False
        if not ok:
            tail = (r.stderr or "").strip().splitlines()
            rep.add("jsonfail", "FAIL",
                    f"{fn} 失败路径未输出合法 JSON",
                    (tail[-1][:200] if tail else
                     f"最后一行: {(lines[-1][:120] if lines else '(无 stdout)')}"))
    rep.add("jsonfail", "PASS", f"核验 {n} 个脚本的失败路径")


# ---------------------------------------------------------------- main

CHECKS = {
    "refs": check_refs,
    "nums": check_nums,
    "cfg": check_cfg,
    "route": check_route,
    "build": check_build,
    "smoke": check_smoke,
    "deploy": check_deploy,
    "stale": check_stale,
    "jsonfail": check_jsonfail,
    "materials": check_materials,
    "golden": check_golden,
    "scriptdocs": check_scriptdocs,
}
LEVEL_MARK = {"FAIL": "✗", "WARN": "△", "PASS": "✓"}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="artboard 仓库自检")
    p.add_argument("--only", default="", help="只跑指定项,逗号分隔")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.add_argument("--list", action="store_true", help="列出检查项")
    args = p.parse_args()

    if args.list:
        for k in CHECKS:
            print(k)
        return 0

    todo = [k.strip() for k in args.only.split(",") if k.strip()] or list(CHECKS)
    bad = [k for k in todo if k not in CHECKS]
    if bad:
        print(f"未知检查项: {', '.join(bad)};可选 {', '.join(CHECKS)}",
              file=sys.stderr)
        return 2

    rep = Report()
    for name in todo:
        CHECKS[name](rep)

    if args.as_json:
        fails = rep.count("FAIL")
        print(json.dumps({"ok": fails == 0, "fail": fails,
                          "warn": rep.count("WARN"), "items": rep.items},
                         ensure_ascii=False))
        return 1 if fails else 0

    for i in rep.items:
        mark = LEVEL_MARK[i["level"]]
        if i["level"] == "PASS":
            print(f"  {mark} [{i['check']}] {i['detail']}")
        else:
            print(f"  {mark} [{i['check']}] {i['detail']}")
            if i["hint"]:
                print(f"       ↳ {i['hint']}")
    print()
    print(f"  FAIL {rep.count('FAIL')}  ·  WARN {rep.count('WARN')}  ·  "
          f"PASS {rep.count('PASS')}")
    if rep.count("FAIL"):
        print("  结论:存在 FAIL —— 多为「文档说有、代码没有」或「同一事实多处不一致」,修完再提交。")
        return 1
    print("  结论:仓库自检通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
