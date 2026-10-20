"""artboard 工程打包:把瘦身影子项目引用的所有外部文件收集进 zip,可迁移交付。

用法:
  python pack.py <项目路径> [--out <zip路径>] [--include-fonts] [--include-vendor]

背景:scaffold 默认「瘦身影子」——src/fonts 与 src/vendor 可链接到 Skill 许可资产库,
HTML 用相对引用。打包时将可信文件联接解析出的真实文件收进包内(assets/fonts/<款>/<文件>),
并将 HTML 引用改写为相对路径,使包自包含。普通目录联接因不会递归扫描其 HTML/CSS 而拒绝,仅认可字体/vendor 的明确资产根。

- 相对引用 fonts/… 与 vendor/…:解析可信 Skill 资产/项目内真实文件并改写 HTML
- file:/// 引用(旧项目):同样收集改写
- --include-fonts / --include-vendor:额外收全库
- 逃逸项目与许可资产目录的联接拒绝打包(FONT_LINK_FAILED / SHADER_VENDOR_LINK_FAILED / PROJECT_LINK_FAILED)
- PACKING.txt 记录收集清单,方便核对
"""

import argparse
import json
import os
import posixpath
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
        return os.path.normcase(os.path.realpath(path)) != os.path.normcase(os.path.abspath(path))
    except OSError:
        return False


def collect_refs(src_dir: str):
    """返回 (项目自身文件列表, 引用清单 {(引用所在文件, 引用串): 解析后绝对路径 或 None})。

    引用按**所在文件自己的目录**解析:src/sub/deep.html 里的 `../fonts/x` 只有相对
    src/sub/ 才算得对(此前统一按 src/ 根解析,嵌套层级的引用永远收不到,自然也不会被改写)。
    """
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
                        refs.setdefault((fp, m.group(1).strip()), None)

    # 解析每个引用(基准 = 该引用所在文件的目录)
    resolved = {}
    for fp, ref in refs:
        r = ref.strip("'\"")
        real = None
        if r.startswith("file:///"):
            cand = urllib.parse.unquote(r[len("file:///"):]).replace("/", os.sep)
            cand = os.path.normpath(cand)
            if os.path.isfile(cand):
                real = os.path.realpath(cand)
        else:
            cand = os.path.normpath(
                os.path.join(os.path.dirname(fp), r.replace("/", os.sep)))
            if os.path.isfile(cand):
                real = os.path.realpath(cand)  # 穿透联接
        resolved[(fp, ref)] = real
    return own, resolved


def _within(path: str, root: str) -> bool:
    try:
        target = os.path.normcase(os.path.realpath(path))
        base = os.path.normcase(os.path.realpath(root))
        return os.path.commonpath((target, base)) == base
    except ValueError:
        return False


def project_shader_root(src_dir: str) -> str | None:
    """Return the exact trusted Skill tree or a physical project-local shader tree."""
    candidate = os.path.join(src_dir, "vendor", "shaders")
    if not os.path.isdir(candidate):
        return None
    resolved = os.path.realpath(candidate)
    trusted = os.path.realpath(os.path.join(SKILL_DIR, "vendor", "shaders"))
    # Only the complete licensed tree is a valid Skill alias; a subtree such as
    # LICENSES is not a runtime and must not be treated as a complete vendor.
    if os.path.normcase(resolved) == os.path.normcase(trusted):
        return trusted
    # A project may carry a real local copy, but never recurse through links.
    vendor_parent = os.path.dirname(candidate)
    if (is_junction(candidate) or os.path.islink(candidate) or
            is_junction(vendor_parent) or os.path.islink(vendor_parent) or
            not _within(resolved, src_dir)):
        return None
    return resolved


def has_invalid_project_shader_root(src_dir: str) -> bool:
    """Reject an existing shader root that is neither exact Skill nor physical local."""
    candidate = os.path.join(src_dir, "vendor", "shaders")
    if not os.path.isdir(candidate):
        return False
    return project_shader_root(src_dir) is None


def missing_shader_vendor_files(root: str) -> list[str]:
    """Return required shader runtime/source/license files missing or linked outside root."""
    required = ("runtime.js", "upstream.js", "LICENSES/shaders-LICENSE")
    missing = []
    for rel in required:
        path = os.path.join(root, *rel.split("/"))
        if (not os.path.isfile(path) or is_junction(path) or os.path.islink(path)
                or not _within(path, root) or os.path.getsize(path) == 0):
            missing.append(rel)
    return missing


def linked_shader_vendor_paths(root: str) -> list[str]:
    """Return symlink/junctions anywhere in a shader tree; they cannot be safely packaged."""
    linked = []
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = os.path.join(current, name)
            if is_junction(path) or os.path.islink(path):
                linked.append(os.path.relpath(path, root).replace(os.sep, "/"))
    return sorted(linked)


def untrusted_project_font_links(src_dir: str) -> list[str]:
    """Reject font links escaping real src files and the licensed Skill font tree."""
    root = os.path.join(src_dir, "fonts")
    if not os.path.isdir(root):
        return []
    skill_fonts = os.path.realpath(os.path.join(SKILL_DIR, "fonts"))
    allowed_roots = (os.path.realpath(src_dir), skill_fonts)
    linked = []

    def inspect_link(path: str) -> None:
        if not (is_junction(path) or os.path.islink(path)):
            return
        target = os.path.realpath(path)
        if not any(_within(target, allowed) for allowed in allowed_roots):
            linked.append(os.path.relpath(path, root).replace(os.sep, "/") or ".")

    inspect_link(root)
    if is_junction(root) or os.path.islink(root):
        return sorted(linked)
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            inspect_link(os.path.join(current, name))
        dirs[:] = [name for name in dirs
                   if not is_junction(os.path.join(current, name))
                   and not os.path.islink(os.path.join(current, name))]
    return sorted(linked)


def untrusted_project_source_links(src_dir: str) -> list[str]:
    """Reject unsafe source links and directory aliases the packer cannot traverse."""
    skill_roots = (
        os.path.join(SKILL_DIR, "fonts"),
        os.path.join(SKILL_DIR, "assets", "vendor"),
        os.path.join(SKILL_DIR, "assets", "icons"),
        os.path.join(SKILL_DIR, "vendor", "shaders"),
    )
    src_root = os.path.realpath(src_dir)
    skill_fonts = os.path.realpath(os.path.join(SKILL_DIR, "fonts"))
    skill_assets_vendor = os.path.realpath(os.path.join(SKILL_DIR, "assets", "vendor"))
    skill_shaders = os.path.realpath(os.path.join(SKILL_DIR, "vendor", "shaders"))
    allowed_roots = (src_root, *(os.path.realpath(p) for p in skill_roots))
    linked = []

    # A linked src root can expose arbitrary project files outside src. Reject
    # every root link before traversal; only nested links to src or explicit
    # licensed Skill roots are eligible for review below.
    if is_junction(src_dir) or os.path.islink(src_dir):
        return ["."]

    for current, dirs, files in os.walk(src_dir, followlinks=False):
        for name in dirs + files:
            path = os.path.join(current, name)
            if not (is_junction(path) or os.path.islink(path)):
                continue
            target = os.path.realpath(path)
            rel = os.path.relpath(path, src_dir).replace(os.sep, "/")
            if os.path.isdir(path):
                font_alias = (rel == "fonts" or rel.startswith("fonts/")) and _within(
                    target, skill_fonts)
                vendor_alias = rel == "vendor" and _within(target, skill_assets_vendor)
                shader_alias = rel == "vendor/shaders" and _within(target, skill_shaders)
                if not (font_alias or vendor_alias or shader_alias):
                    linked.append(rel)
                continue
            if not os.path.isfile(path) or not any(
                    _within(target, allowed) for allowed in allowed_roots):
                linked.append(rel)
        dirs[:] = [name for name in dirs
                   if not is_junction(os.path.join(current, name))
                   and not os.path.islink(os.path.join(current, name))]
    return sorted(linked)


def has_untrusted_project_shader_ref(src_dir: str, resolved_refs: dict) -> bool:
    candidate = os.path.join(src_dir, "vendor", "shaders")
    if not os.path.isdir(candidate) or project_shader_root(src_dir) is not None:
        return False
    untrusted_root = os.path.realpath(candidate)
    return any(real and _within(real, untrusted_root) for real in resolved_refs.values())


def missing_shader_vendor_references(src_dir: str, resolved_refs: dict) -> list[str]:
    """Find unresolved relative references under src/vendor/shaders."""
    vendor_root = os.path.normcase(os.path.normpath(
        os.path.abspath(os.path.join(src_dir, "vendor", "shaders"))))
    missing = []
    for (referer, ref), real in resolved_refs.items():
        if real:
            continue
        try:
            parsed = urllib.parse.urlsplit(ref.strip("'\""))
        except ValueError:
            continue
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = urllib.parse.unquote(parsed.path).replace("/", os.sep)
        candidate = os.path.normcase(os.path.normpath(
            os.path.abspath(os.path.join(os.path.dirname(referer), path))))
        try:
            if os.path.commonpath((candidate, vendor_root)) == vendor_root:
                missing.append(ref)
        except ValueError:
            continue
    return sorted(set(missing))


def referenced_shader_root_kinds(resolved_refs: dict, skill_root: str,
                                 project_root: str | None) -> set[str]:
    """Identify shader bundle roots referenced by the project before ZIP paths are assigned."""
    trusted = os.path.realpath(skill_root)
    project = os.path.realpath(project_root) if project_root else None
    kinds = set()
    for real in resolved_refs.values():
        if not real:
            continue
        if _within(real, trusted):
            kinds.add("skill")
        elif project and _within(real, project):
            kinds.add("project")
    return kinds


def classify(real_path: str, src_dir: str = "") -> str | None:
    """真实资产路径 → 包内 assets/ 路径;支持 Skill 链接和项目内拷贝。"""
    roots = [
        (os.path.join(SKILL_DIR, "fonts"), "assets/fonts/"),
        (os.path.join(SKILL_DIR, "assets", "vendor"), "assets/vendor/"),
        (os.path.join(SKILL_DIR, "assets", "icons"), "assets/icons/"),
        (os.path.join(SKILL_DIR, "vendor", "shaders"), "assets/vendor/shaders/"),
    ]
    if src_dir:
        project_fonts = os.path.join(src_dir, "fonts")
        roots.append((project_fonts, "assets/fonts/"))
        # gzh_cover 接字体时按 family 建 junction;从另一卷打包时要把每个 junction
        # 的真实根纳入分类,否则 commonpath(src/fonts, real_font) 会跨 root 失配。
        if os.path.isdir(project_fonts):
            skill_fonts = os.path.join(SKILL_DIR, "fonts")
            for family in os.listdir(project_fonts):
                family_root = os.path.join(project_fonts, family)
                if (os.path.isdir(family_root)
                        and (_within(family_root, project_fonts)
                             or _within(family_root, skill_fonts))):
                    roots.append((family_root, f"assets/fonts/{family}/"))
        safe_shader_root = project_shader_root(src_dir)
        if safe_shader_root:
            roots.append((safe_shader_root, "assets/vendor/shaders/"))
    for root, dest in roots:
        if not os.path.isdir(root) or not _within(real_path, root):
            continue
        rel = os.path.relpath(os.path.realpath(real_path), os.path.realpath(root))
        if rel != "." and not rel.startswith(".." + os.sep):
            return dest + rel.replace(os.sep, "/")
    return None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
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
    if is_junction(src_dir) or os.path.islink(src_dir):
        emit({"ok": False, "error": "PROJECT_LINK_FAILED", "linked": ["."],
              "hint": "src 根目录不能是联接;引用目标必须位于真实 src/ 或已许可的 Skill 资源内"})
        return 1
    slug = os.path.basename(proj.rstrip("\\/"))
    out = args.out or os.path.join(proj, "export", f"{slug}-pack.zip")

    # Validate link boundaries before collect_refs opens any HTML/CSS under src/.
    font_links = untrusted_project_font_links(src_dir)
    if font_links:
        emit({"ok": False, "error": "FONT_LINK_FAILED", "linked": font_links,
              "hint": "src/fonts 只能链接项目内文件或 Skill 许可字体目录"})
        return 1
    project_vendor_root = project_shader_root(src_dir)
    if project_vendor_root:
        linked = linked_shader_vendor_paths(project_vendor_root)
        if linked:
            emit({"ok": False, "error": "SHADER_VENDOR_LINK_FAILED", "linked": linked,
                  "hint": "shader vendor 树内不能含 symlink/junction,请使用实体文件"})
            return 1
    source_links = untrusted_project_source_links(src_dir)
    if source_links:
        shader_links = [item for item in source_links
                        if item == "vendor/shaders" or item.startswith("vendor/shaders/")]
        if shader_links:
            error = "SHADER_VENDOR_LINK_FAILED"
            hint = "shader vendor 树内不能含 symlink/junction,请使用实体文件"
            rejected_links = shader_links
        else:
            error = "PROJECT_LINK_FAILED"
            hint = "src/ 不支持普通目录联接;文件联接仅可指向真实 src 文件或许可 Skill 资源"
            rejected_links = source_links
        emit({"ok": False, "error": error, "linked": rejected_links, "hint": hint})
        return 1
    if has_invalid_project_shader_root(src_dir):
        emit({"ok": False, "error": "SHADER_VENDOR_LINK_FAILED",
              "linked": ["vendor/shaders"],
              "hint": "shader vendor 根必须是完整的许可 Skill 树或项目内实体目录"})
        return 1

    own, resolved = collect_refs(src_dir)
    missing_shader_refs = missing_shader_vendor_references(src_dir, resolved)
    if missing_shader_refs:
        emit({"ok": False, "error": "SHADER_VENDOR_INCOMPLETE",
              "missing": missing_shader_refs,
              "hint": "HTML/CSS 引用了缺失的 src/vendor/shaders 资源"})
        return 1
    if has_untrusted_project_shader_ref(src_dir, resolved):
        emit({"ok": False, "error": "SHADER_VENDOR_LINK_FAILED",
              "hint": "src/vendor/shaders 必须是 Skill 许可目录联接，或项目内真实目录"})
        return 1

    collected = {}          # 真实绝对路径 -> 包内 assets/ 相对路径
    destination_sources = {}  # 跨平台 ZIP 目标名(casefold) -> (源文件,目标名)
    destination_conflicts = {}
    rewrite_by_file = {}    # 引用所在文件 -> {原始引用串: 包内 assets/ 相对路径}

    def add_asset(source: str, dest: str) -> None:
        source_real = os.path.realpath(source)
        normalized_dest = posixpath.normpath(dest.replace("\\", "/"))
        dest_key = normalized_dest.casefold()
        previous = destination_sources.get(dest_key)
        if previous:
            previous_source, previous_dest = previous
            if (os.path.normcase(previous_source) != os.path.normcase(source_real)
                    or previous_dest != normalized_dest):
                conflict = destination_conflicts.setdefault(
                    dest_key, {"path": normalized_dest, "sources": []})
                for candidate in (previous_source, source_real):
                    if all(candidate != item for item in conflict["sources"]):
                        conflict["sources"].append(candidate)
                return
            return  # The same physical file was referenced more than once.
        destination_sources[dest_key] = (source_real, normalized_dest)
        collected[source_real] = normalized_dest

    for (fp, ref), real in resolved.items():
        if not real:
            continue
        dest = classify(real, src_dir)
        if not dest:
            continue
        add_asset(real, dest)
        rewrite_by_file.setdefault(fp, {})[ref] = dest

    # Shader runtime 从 upstream.js 动态加载 bundle,并在发布包中附带 MIT LICENSE。
    # 只从明确授权的 Skill 树或项目内实体目录收集，禁止按路径 basename 向外递归。
    skill_shader_root = os.path.realpath(os.path.join(SKILL_DIR, "vendor", "shaders"))
    local_shader_root = project_vendor_root
    shader_source_kinds = referenced_shader_root_kinds(
        resolved, skill_shader_root, local_shader_root)
    if len(shader_source_kinds) > 1:
        emit({"ok": False, "error": "SHADER_VENDOR_ROOT_CONFLICT",
              "roots": sorted(shader_source_kinds),
              "hint": "一个项目包只能引用单一 shader vendor 来源,请统一使用 Skill 树或项目本地副本"})
        return 1
    if "skill" in shader_source_kinds:
        shader_root = skill_shader_root
    elif "project" in shader_source_kinds:
        shader_root = local_shader_root
    else:
        shader_root = None
    if args.include_vendor and shader_root is None:
        shader_root = skill_shader_root if os.path.isdir(skill_shader_root) else None
    if shader_root and os.path.isdir(shader_root):
        linked = linked_shader_vendor_paths(shader_root)
        if linked:
            emit({"ok": False, "error": "SHADER_VENDOR_LINK_FAILED",
                  "linked": linked,
                  "hint": "shader vendor 树内不能含 symlink/junction,请使用实体文件"})
            return 1
        missing = missing_shader_vendor_files(shader_root)
        if missing:
            emit({"ok": False, "error": "SHADER_VENDOR_INCOMPLETE",
                  "missing": missing,
                  "hint": "打包 shader runtime 必须包含 runtime.js、upstream.js 与 MIT LICENSE"})
            return 1
        for root, dirs, files in os.walk(shader_root, followlinks=False):
            dirs[:] = [d for d in dirs
                       if not is_junction(os.path.join(root, d))
                       and not os.path.islink(os.path.join(root, d))]
            for name in files:
                source = os.path.join(root, name)
                if os.path.isfile(source) and not is_junction(source) and not os.path.islink(source):
                    rel = os.path.relpath(source, shader_root).replace(os.sep, "/")
                    add_asset(source, "assets/vendor/shaders/" + rel)

    if args.include_fonts:
        fonts_root = os.path.join(SKILL_DIR, "fonts")
        for root, dirs, files in os.walk(fonts_root):
            dirs[:] = [d for d in dirs if not d.startswith(("_", "."))]
            for fn in files:
                if fn.lower().endswith((".ttf", ".otf", ".woff", ".woff2")):
                    rel = os.path.relpath(os.path.join(root, fn),
                                          fonts_root).replace(os.sep, "/")
                    add_asset(os.path.join(root, fn), f"assets/fonts/{rel}")
    if args.include_vendor:
        vendor = os.path.join(SKILL_DIR, "assets", "vendor")
        if os.path.isdir(vendor):
            for fn in os.listdir(vendor):
                fp = os.path.join(vendor, fn)
                if os.path.isfile(fp):
                    add_asset(fp, f"assets/vendor/{fn}")

    def source_label(real: str) -> str:
        project_fonts = os.path.join(src_dir, "fonts")
        roots = [
            ("$SKILL/fonts", os.path.join(SKILL_DIR, "fonts")),
            ("$SKILL/vendor/shaders", os.path.join(SKILL_DIR, "vendor", "shaders")),
            ("$SKILL/assets/vendor", os.path.join(SKILL_DIR, "assets", "vendor")),
            ("$SKILL/assets/icons", os.path.join(SKILL_DIR, "assets", "icons")),
            ("$PROJECT/src/fonts", project_fonts),
            ("$PROJECT/src/vendor/shaders", os.path.join(src_dir, "vendor", "shaders")),
        ]
        if os.path.isdir(project_fonts):
            for family in os.listdir(project_fonts):
                family_root = os.path.join(project_fonts, family)
                if os.path.isdir(family_root):
                    roots.append((f"$PROJECT/src/fonts/{family}", family_root))
        for label, root in roots:
            if os.path.isdir(root) and _within(real, root):
                rel = os.path.relpath(os.path.realpath(real), os.path.realpath(root))
                return f"{label}/{rel.replace(os.sep, '/')}"
        if _within(real, src_dir):
            rel = os.path.relpath(os.path.realpath(real), os.path.realpath(src_dir))
            return "$PROJECT/src/" + rel.replace(os.sep, "/")
        return "$resolved-asset/" + os.path.basename(real)

    def pack_prefix(rel_dir: str) -> str:
        """HTML/CSS 相对 src/ 的目录深度 → 回到包根 <slug>/ 所需的 ../ 层数。

        包内固定布局是 <slug>/src/… 与 <slug>/assets/…:src 根的 HTML 要一层 `../`,
        再深一层就得多一层。少这一层引用会落到 <slug>/src/assets/…(包内不存在)。
        """
        depth = len([p for p in rel_dir.replace("\\", "/").split("/")
                     if p and p != "."])
        return "../" * (depth + 1)

    def html_for_pack(text: str, rel_dir: str, refs: dict) -> str:
        prefix = pack_prefix(rel_dir)
        for old_ref, new_ref in sorted(refs.items(), key=lambda kv: -len(kv[0])):
            text = text.replace(old_ref, prefix + new_ref)
        return text

    # 自有 src 文件也会按 ZIP 目标路径写入；在 Windows 解压前统一按
    # casefold 预留这些目标名，避免 A.html 与 a.html 覆盖彼此。
    for fp in own:
        rel = os.path.relpath(fp, src_dir).replace(os.sep, "/")
        normalized_dest = posixpath.normpath(f"{slug}/src/{rel}")
        dest_key = normalized_dest.casefold()
        source_real = os.path.realpath(fp)
        previous = destination_sources.get(dest_key)
        if previous:
            previous_source, previous_dest = previous
            if (os.path.normcase(previous_source) != os.path.normcase(source_real)
                    or previous_dest != normalized_dest):
                conflict = destination_conflicts.setdefault(
                    dest_key, {"path": normalized_dest, "sources": []})
                for candidate in (previous_source, source_real):
                    if all(candidate != item for item in conflict["sources"]):
                        conflict["sources"].append(candidate)
        else:
            destination_sources[dest_key] = (source_real, normalized_dest)

    if destination_conflicts:
        conflicts = [
            {"path": item["path"],
             "sources": [source_label(source) for source in item["sources"]]}
            for item in list(destination_conflicts.values())[:20]
        ]
        emit({"ok": False, "error": "PACK_DESTINATION_CONFLICT",
              "conflict_count": len(destination_conflicts), "conflicts": conflicts,
              "hint": "不同源文件映射到同一 ZIP 路径;请移除冲突资产或调整引用名"})
        return 1

    # --out 只给文件名时 dirname 为 "",必须 abspath 兜底
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fp in own:
            rel = os.path.relpath(fp, src_dir).replace(os.sep, "/")
            if fp.lower().endswith((".html", ".htm", ".css")):
                rel_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
                z.writestr(f"{slug}/src/{rel}",
                           html_for_pack(open(fp, encoding="utf-8",
                                              errors="ignore").read(),
                                         rel_dir, rewrite_by_file.get(fp, {})))
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
            note += f"  {dest}  <-  {source_label(real)}\n"
        z.writestr(f"{slug}/PACKING.txt", note)
        count += 1

    emit({"ok": True, "zip": os.path.abspath(out), "files": count,
          "external": len(collected),
          "hint": "联接已被穿透收集:包内 assets/ 为实体文件,HTML 引用已改写"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
