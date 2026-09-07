"""artboard 工程打包:把瘦身影子项目引用的所有外部文件收集进 zip,可迁移交付。

用法:
  python pack.py <项目路径> [--out <zip路径>] [--include-fonts] [--include-vendor]

背景:scaffold 默认「瘦身影子」——src/fonts 与 src/vendor 是指向 Skill 资产库的
NTFS 目录联接,HTML 用相对引用。打包时把联接穿透到的真实文件收进包内
(assets/fonts/<款>/<文件>),并把 HTML 内引用改写为对应相对路径,包即自包含。

- 相对引用 fonts/… 与 vendor/…:穿透联接解析真实文件 → assets/… 并改写 HTML
- file:/// 引用(旧项目):同样收集改写
- --include-fonts / --include-vendor:额外收全库
- PACKING.txt 记录收集清单,方便核对
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import zipfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RX_ATTR = re.compile(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', re.I)
RX_CSS_URL = re.compile(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', re.I)


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def is_junction(path: str) -> bool:
    try:
        return os.path.realpath(path) != os.path.abspath(path)
    except OSError:
        return False


def collect_refs(src_dir: str):
    """返回 (项目自身文件列表, 引用清单 {原始引用串: 解析后的绝对路径 或 None})。"""
    own, refs = [], {}
    for root, dirs, files in os.walk(src_dir):
        # 联接目录不作为项目文件遍历(其内容按引用收集)
        dirs[:] = [d for d in dirs if not is_junction(os.path.join(root, d))]
        for fn in files:
            fp = os.path.join(root, fn)
            if fn.endswith((".zip", ".bin")):
                continue
            own.append(fp)
            if fn.lower().endswith((".html", ".htm", ".css")):
                text = open(fp, encoding="utf-8", errors="ignore").read()
                for rx in (RX_ATTR, RX_CSS_URL):
                    for m in rx.finditer(text):
                        refs.setdefault(m.group(1).strip(), None)

    # 解析每个引用
    resolved = {}
    for ref in refs:
        r = ref.strip("'\"")
        real = None
        if r.startswith("file:///"):
            cand = urllib.parse.unquote(r[len("file:///"):]).replace("/", os.sep)
            cand = os.path.normpath(cand)
            if os.path.isfile(cand):
                real = os.path.realpath(cand)
        else:
            cand = os.path.normpath(os.path.join(src_dir, r.replace("/", os.sep)))
            if os.path.isfile(cand):
                real = os.path.realpath(cand)  # 穿透联接
        resolved[ref] = real
    return own, resolved


def classify(real_path: str) -> str | None:
    """真实路径 → 包内 assets/ 相对路径(仅收 Skill 资产库内的)。"""
    norm = real_path.replace(os.sep, "/").lower()
    skill = SKILL_DIR.replace(os.sep, "/").lower() + "/"
    if not norm.startswith(skill):
        return None
    rel = real_path.replace(os.sep, "/")[len(skill):]
    for prefix, dest in (("fonts/", "assets/fonts/"),
                         ("assets/vendor/", "assets/vendor/"),
                         ("assets/icons/", "assets/icons/")):
        if rel.startswith(prefix):
            return dest + rel[len(prefix):]
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--out", default="")
    p.add_argument("--include-fonts", action="store_true")
    p.add_argument("--include-vendor", action="store_true")
    args = p.parse_args()

    proj = os.path.abspath(args.project)
    src_dir = os.path.join(proj, "src")
    if not os.path.isdir(src_dir):
        emit({"ok": False, "error": "NO_SRC", "hint": f"{src_dir} 不存在"})
        return 1
    slug = os.path.basename(proj.rstrip("\\/"))
    out = args.out or os.path.join(proj, "export", f"{slug}-pack.zip")

    own, resolved = collect_refs(src_dir)

    collected = {}   # 真实绝对路径 -> 包内 assets/ 相对路径
    rewrite = {}     # 原始引用串 -> 改写后的相对引用
    for ref, real in resolved.items():
        if not real:
            continue
        dest = classify(real)
        if not dest:
            continue
        collected[real] = dest
        rewrite[ref] = dest

    if args.include_fonts:
        fonts_root = os.path.join(SKILL_DIR, "fonts")
        for root, dirs, files in os.walk(fonts_root):
            dirs[:] = [d for d in dirs if not d.startswith(("_", "."))]
            for fn in files:
                if fn.lower().endswith((".ttf", ".otf", ".woff", ".woff2")):
                    rel = os.path.relpath(os.path.join(root, fn),
                                          fonts_root).replace(os.sep, "/")
                    collected[os.path.join(root, fn)] = f"assets/fonts/{rel}"
    if args.include_vendor:
        vendor = os.path.join(SKILL_DIR, "assets", "vendor")
        for fn in os.listdir(vendor):
            fp = os.path.join(vendor, fn)
            if os.path.isfile(fp):
                collected[fp] = f"assets/vendor/{fn}"

    def html_for_pack(text: str) -> str:
        for old_ref, new_ref in sorted(rewrite.items(), key=lambda kv: -len(kv[0])):
            text = text.replace(old_ref, new_ref)
        return text

    os.makedirs(os.path.dirname(out), exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fp in own:
            rel = os.path.relpath(fp, src_dir).replace(os.sep, "/")
            if fp.lower().endswith((".html", ".htm", ".css")):
                z.writestr(f"{slug}/src/{rel}",
                           html_for_pack(open(fp, encoding="utf-8",
                                              errors="ignore").read()))
            else:
                z.write(fp, f"{slug}/src/{rel}")
            count += 1
        for real, dest in collected.items():
            if os.path.isfile(real):
                z.write(real, f"{slug}/{dest}")
                count += 1
        note = (f"artboard 打包工程 · {slug}\n{'=' * 40}\n"
                "自包含交付包:解压后 src/ 内 HTML 可直接用浏览器打开,\n"
                "外部依赖已收至 assets/ 并改写为相对引用。\n"
                f"\n收集的外部依赖 {len(collected)} 项:\n")
        for real, dest in sorted(collected.items(), key=lambda kv: kv[1]):
            note += f"  {dest}  <-  {os.path.relpath(real, SKILL_DIR)}\n"
        z.writestr(f"{slug}/PACKING.txt", note)
        count += 1

    emit({"ok": True, "zip": os.path.abspath(out), "files": count,
          "external": len(collected),
          "hint": "联接已被穿透收集:包内 assets/ 为实体文件,HTML 引用已改写"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
