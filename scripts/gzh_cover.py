"""微信公众号双封面工作站:一次设计,三张产物(主封面/次条/合并预览图)。

用法:
  python gzh_cover.py new <slug> --title 文案 [--sub-title 次条标题] [--kicker 眉题]
                  [--sub 副题] [--footer 页脚] [--num 期号] [--theme ink|night|warm|grass|red|mono]
                  [--fonts smiley-sans,source-han-sans]
                  [--layout center-band|band-editorial|stack-cards|giant-caps|kraft-note|plate-page]
                  [--bg-pattern auto|none|dots|stripe|grid|lattice|grain|glow]
                  [--accent-tone auto|none|font|capsule|pill]
                  [--sub-mode same|minimal|flat]
                  [--fx auto|none|halftone|dot-grid|aurora|...]  # 着色器底材(见 --list-fx)
                  [--title-en 水印] [--badge 贴纸] [--side-label 竖排] [--meta 时间,地点,主办]
                  [--image 本地 PNG/JPEG/WebP 照片(plate-page 必填)]
                   [--force]
  python gzh_cover.py new --list-layouts              # 列 6 套版式族与适用文案形态
  python gzh_cover.py export <项目目录|slug> [--only main|sub|merged] [--scale 2] [--outdir 目录]
  python gzh_cover.py merge <项目目录|slug> [--gap 57] [--bg "#f6f7f9"]   # 仅重拼合并图(不重导)
  python gzh_cover.py check <项目目录|slug>           # 静态几何断言(安全区/层级/底纹),无需浏览器

版式族(详见 references/gzh-cover-layouts.md):
  center-band 居中色带 / band-editorial 左文带 / stack-cards 分层堆叠 /
  giant-caps 巨字压边 / kraft-note 牛皮便签 / plate-page 画页分栏。
  **不加 --layout 时输出与旧版逐字节一致**(center-band 即旧版居中版式)。

产物约定(项目目录 = <studio_dir>/<slug>/;以下像素为 Artboard 默认工作画布,不是官方规格承诺):
  src/index.html            主封面画布 900×383(约 2.35:1)
  src/sub.html              次条封面画布 383×383(1:1)
  export/cover-main-<slug>.png    主封面(默认 2x = 1800×766)
  export/cover-sub-<slug>.png     次条封面(默认 2x = 766×766)
  export/cover-merged-<slug>.png  双封面合并图(kiln img stitch 等高拼接,单张原始比例不变)

设计约定(证据与来源见 references/formats/gzh-cover.md 与 docs/gzh-spec-summary.md):
  - 900×383 与 383×383 是依据第三方 135 编辑教程示例选定的 Artboard 内部默认值,并非已核实的微信官方尺寸要求;
  - 中央约 383×383 是保守的内部排版安全区,不代表转发/分享卡片的保证裁切范围;实际显示请以当前公众号后台预览为准;
  - 合并图 = 两张导出 PNG 按原始像素等高拼接(间隔默认 57px×scale),Pillow 纯拼接,
    不重新渲染 HTML → 单张内容零形变、零重采样。

输出:单行 JSON(ok/…);失败也输出 JSON(ok:false + error/hint),便于脚本链消费。
"""

import argparse
import base64
import filecmp
import html as html_lib
import io
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
import zlib


def _decode_css_escapes(text: str) -> str:
    """Decode CSS escapes before applying static policy checks to tokens/URLs."""
    out = []
    i = 0
    hexchars = "0123456789abcdefABCDEF"
    whitespace = (9, 10, 12, 13, 32)
    while i < len(text):
        if ord(text[i]) != 92:
            out.append(text[i])
            i += 1
            continue
        i += 1
        if i >= len(text):
            break
        code = ord(text[i])
        if code in (10, 12, 13):
            if code == 13 and i + 1 < len(text) and ord(text[i + 1]) == 10:
                i += 2
            else:
                i += 1
            continue
        start = i
        while i < len(text) and i - start < 6 and text[i] in hexchars:
            i += 1
        if i > start:
            codepoint = int(text[start:i], 16)
            if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                out.append(chr(0xFFFD))
            else:
                out.append(chr(codepoint))
            if i < len(text) and ord(text[i]) in whitespace:
                if ord(text[i]) == 13 and i + 1 < len(text) and ord(text[i + 1]) == 10:
                    i += 2
                else:
                    i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _split_css_declarations(block: str) -> list[str]:
    """Split at declaration semicolons, not inside strings, escapes, or functions."""
    declarations = []
    start = 0
    quote = ""
    escaped = False
    depth = 0
    for index, char in enumerate(block):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        elif char == ";" and depth == 0:
            declarations.append(block[start:index].strip())
            start = index + 1
    if block[start:].strip():
        declarations.append(block[start:].strip())
    return declarations


class _CoverHTMLAudit(HTMLParser):
    """Collect CSS and resource URLs using HTML's case-insensitive attribute syntax."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.style_parts = []
        self.external_urls = []
        self.unreviewed_stylesheets = []
        self.shader_canvas = False
        self.webgpu_marker = False
        self.poster_inline_styles = []
        self.page_root_inline_styles = []
        self.title_inline_styles = []
        self.title_ancestor_inline_styles = []
        self.title_tags = set()
        self.title_ancestor_classes = set()
        self.title_ancestor_tags = set()
        self.image_sources = []
        self.media_elements = []
        self.unreviewed_code = []
        self.script_sources = []
        self.resource_urls = []
        self.base_elements = []
        self._style_depth = 0
        self._script_depth = 0
        self.element_stack = []
        self.poster_parent_chains = []
        self.body_child_elements = []
        self.body_child_text = []
        self.shader_canvas_fx = []

    @staticmethod
    def _is_external(url: str) -> bool:
        raw_value = html_lib.unescape(url or "")
        # WHATWG URL parsing strips ASCII tabs/newlines even inside a scheme;
        # reject controls before trimming so obfuscated HTTPS cannot look local.
        if re.search(r"[\x00-\x1f\x7f]", raw_value):
            return True
        # WHATWG treats backslashes as slashes for special schemes; network-path
        # forms like \\evil.example can therefore escape the local file origin.
        if "\\" in raw_value:
            return True
        value = raw_value.strip()
        if re.match(r"^(?:https?:)?//", value, re.I):
            return True
        scheme = re.match(r"^([a-z][a-z0-9+.-]*):", value, re.I)
        if not scheme:
            return False
        protocol = scheme.group(1).lower()
        if protocol == "data":
            # Inline raster data is inert and used by some existing projects.
            # Data CSS/SVG/HTML can itself fetch or execute content, so fail closed.
            return not re.match(
                r"^data:image/(?:png|jpe?g|gif|webp|avif|bmp);base64,", value, re.I)
        return protocol not in {"mailto", "tel"}

    def handle_starttag(self, tag, attrs):
        tag_name = tag.lower()
        values = {}
        for name, value in attrs:
            key = name.lower()
            if key not in values:
                values[key] = value or ""
        classes = values.get("class", "").split()
        parent_tags = [item["tag"] for item in self.element_stack]
        if parent_tags[-2:] == ["html", "body"]:
            self.body_child_elements.append({
                "tag": tag_name, "classes": tuple(classes), "attrs": dict(values)})
        if "poster" in classes:
            self.poster_parent_chains.append(tuple(item["tag"] for item in self.element_stack))
        if tag_name == "h1" or "t" in classes:
            self.title_tags.add(tag_name)
            self.title_ancestor_classes.update(
                name for item in self.element_stack for name in item.get("classes", ()))
            self.title_ancestor_tags.update(item["tag"] for item in self.element_stack)
            self.title_ancestor_inline_styles.extend(
                item.get("attrs", {}).get("style", "")
                for item in self.element_stack if item.get("attrs", {}).get("style"))
            if "style" in values:
                self.title_inline_styles.append(values["style"])
        if tag_name in {"img", "image", "source"}:
            if tag_name in {"img", "image"}:
                image_src = values.get("src") or values.get("href", "")
                if image_src:
                    self.image_sources.append(image_src)
            for candidate in values.get("srcset", "").split(","):
                candidate_url = candidate.strip().split(None, 1)[0] if candidate.strip() else ""
                if candidate_url:
                    self.image_sources.append(candidate_url)
        if tag_name in {"video", "audio", "marquee"}:
            self.media_elements.append(tag_name)
        if tag_name == "meta" and values.get("http-equiv", "").strip().lower() == "refresh":
            self.external_urls.append("meta refresh is disallowed")
        if tag_name == "base":
            # Even a relative base changes the resolution origin of approved script names.
            self.base_elements.append(values.get("href", ""))
            self.unreviewed_code.append("<base> is disallowed in cover HTML")
        if tag_name == "script":
            src = values.get("src", "").strip()
            self.script_sources.append(src)
            if src not in {"vendor/shaders/upstream.js", "vendor/shaders/runtime.js"}:
                self.unreviewed_code.append(src or "inline script")
            self._script_depth += 1
        for name, value in attrs:
            attr = name.lower()
            if attr.startswith("on") or attr == "srcdoc":
                self.unreviewed_code.append(f"active attribute {attr}")
        if tag_name == "link" and "stylesheet" in values.get("rel", "").lower().split():
            self.unreviewed_stylesheets.append(values.get("href", "linked stylesheet"))
        if "poster" in classes and "style" in values:
            self.poster_inline_styles.append(values["style"])
        if tag_name in {"html", "body"} and "style" in values:
            self.page_root_inline_styles.append(values["style"])
        if tag_name == "canvas":
            # Match runtime.js exactly: it only mounts canvas.ab-shader[data-fx].
            is_shader_canvas = "ab-shader" in classes and "data-fx" in values
            if is_shader_canvas:
                self.shader_canvas = True
                self.shader_canvas_fx.append(values.get("data-fx", "").strip())
                if values.get("data-webgpu-required", "").strip().lower() == "true":
                    self.webgpu_marker = True
                if values.get("data-fx", "").strip().lower() == "water":
                    try:
                        params = json.loads(values.get("data-params", ""))
                    except (json.JSONDecodeError, TypeError):
                        params = None
                    if not isinstance(params, dict):
                        self.external_urls.append("invalid shader parameter JSON")
                    else:
                        sdf_url = params.get("shapeSdfUrl")
                        if sdf_url:
                            if not isinstance(sdf_url, str):
                                self.external_urls.append("Water shapeSdfUrl is not a string")
                            else:
                                self.resource_urls.append(sdf_url)
                                if self._is_external(sdf_url):
                                    self.external_urls.append("Water shapeSdfUrl is not offline")
        if tag_name in {"svg", "animate", "animatecolor", "animatemotion",
                         "animatetransform", "set", "discard", "mpath"}:
            # Inline SVG/SMIL can change a link after click, bypassing static href checks.
            self.unreviewed_code.append(f"inline SVG/SMIL element <{tag_name}> is not allowed")
        if tag_name in {"object", "embed", "iframe", "frame", "frameset", "applet"}:
            # These can load active documents even when their URL is relative or data:.
            self.external_urls.append(f"active embedded element <{tag_name}>")
        for name, value in attrs:
            if value is None:
                continue
            attr = name.lower()
            url_attrs = {"src", "href", "poster", "data", "background", "codebase", "archive",
                         "action", "formaction", "cite", "longdesc", "manifest", "profile"}
            if attr in url_attrs or attr.endswith(":href"):
                self.resource_urls.append(value)
                if self._is_external(value):
                    self.external_urls.append(value.strip())
            elif attr in {"srcset", "ping"}:
                for candidate in value.split(",") if attr == "srcset" else value.split():
                    url = candidate.strip().split(None, 1)[0] if candidate.strip() else ""
                    if url:
                        self.resource_urls.append(url)
                    if self._is_external(url):
                        self.external_urls.append(url)
            if attr == "style":
                self.style_parts.append(value)
        if tag_name == "style":
            self._style_depth += 1
        void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                     "link", "meta", "param", "source", "track", "wbr", "image"}
        if tag_name not in void_tags:
            self.element_stack.append({"tag": tag_name, "classes": tuple(classes),
                                       "attrs": dict(values)})

    def handle_startendtag(self, tag, attrs):
        # HTML ignores the self-closing slash on non-void elements such as style.
        # Match the browser's raw-text parsing instead of HTMLParser's eager close.
        self.handle_starttag(tag, attrs)
        if tag.lower() not in {"style", "script"}:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if data.strip() and [item["tag"] for item in self.element_stack][-2:] == ["html", "body"]:
            self.body_child_text.append(data.strip())
        if self._style_depth:
            self.style_parts.append(data)
        if self._script_depth:
            self.unreviewed_code.append("inline script content")

    def handle_endtag(self, tag):
        tag_name = tag.lower()
        if tag_name == "style" and self._style_depth:
            self._style_depth -= 1
        elif tag_name == "script" and self._script_depth:
            self._script_depth -= 1
        for index in range(len(self.element_stack) - 1, -1, -1):
            if self.element_stack[index]["tag"] == tag_name:
                del self.element_stack[index:]
                break

    def css_resource_urls(self):
        css = self.css_text()
        url_pattern = r"""url\(\s*(?:(['\"])(.*?)\1|([^)]*?))\s*\)"""
        return [(match.group(2) if match.group(1) else match.group(3) or "").strip()
                for match in re.finditer(url_pattern, css, flags=re.I | re.S)]

    def css_image_resource_urls(self):
        css = self.css_text()
        image_properties = {
            "background", "background-image", "border-image", "border-image-source",
            "list-style", "list-style-image", "mask", "mask-image", "mask-border",
            "mask-border-source", "-webkit-mask", "-webkit-mask-image", "content",
            "shape-outside", "cursor",
        }
        url_pattern = r"""url\(\s*(?:(['\"])(.*?)\1|([^)]*?))\s*\)"""
        urls = []
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
            for declaration in _split_css_declarations(match.group(2)):
                name, separator, value = declaration.partition(":")
                if (not separator or name.strip().lower() not in image_properties):
                    continue
                for url_match in re.finditer(url_pattern, value, flags=re.I | re.S):
                    urls.append((url_match.group(2) if url_match.group(1)
                                 else url_match.group(3) or "").strip())
        return urls

    def css_font_resource_urls(self):
        css = self.css_text()
        url_pattern = r"""url\(\s*(?:(['\"])(.*?)\1|([^)]*?))\s*\)"""
        urls = []
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
            if match.group(1).strip().lower() != "@font-face":
                continue
            for declaration in _split_css_declarations(match.group(2)):
                name, separator, value = declaration.partition(":")
                if not separator or name.strip().lower() != "src":
                    continue
                for url_match in re.finditer(url_pattern, value, flags=re.I | re.S):
                    urls.append((url_match.group(2) if url_match.group(1)
                                 else url_match.group(3) or "").strip())
        return urls

    def css_external_urls(self):
        css = self.css_text()
        urls = [value for value in self.css_resource_urls() if self._is_external(value)]
        import_pattern = r"""@import\s+(?:url\(\s*)?(?:(['\"])(.*?)\1|([^\s);]+))"""
        for match in re.finditer(import_pattern, css, flags=re.I):
            value = (match.group(2) if match.group(1) else match.group(3) or "").strip()
            if self._is_external(value):
                urls.append(value)
        # CSS image-set() permits URL strings without url(); the current
        # lightweight parser cannot prove every source is portable, so fail closed.
        if re.search(r"(?<![\w-])(?:-webkit-)?image-set\s*\(", css, flags=re.I):
            urls.append("CSS image-set() is unsupported by offline-only audit")
        return urls

    def has_unreviewed_stylesheets(self) -> bool:
        # Cover projects intentionally inline CSS; resolving imports would require
        # following paths and auditing a transitive resource graph.
        return bool(self.unreviewed_stylesheets or re.search(
            r"(?<![\w-])@\s*import\b", self.css_text(), flags=re.I))

    def css_text(self) -> str:
        css = re.sub(r"/\*.*?\*/", "", "\n".join(self.style_parts), flags=re.S)
        return _decode_css_escapes(css)


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from _config import cfg, near_workspace  # noqa: E402
import shader_fx as _shader_fx  # noqa: E402

MAIN_W, MAIN_H = 900, 383      # Artboard 主封面内部默认画布(约 2.35:1)
SUB_W, SUB_H = 383, 383        # Artboard 次条内部默认 1:1 画布
MERGE_GAP = 57                 # 合并图间隔(CSS px,随 scale 放大)

# 主题色板:唯一真相源 = _gzh_theme.py(图文与封面共用;一处改色两产物同变)
import _gzh_theme as _GZT
THEMES, _THEME_ALIAS = _GZT.cover_themes()

# 版式族库:6 套内容结构(见 references/gzh-cover-layouts.md)
import _gzh_layouts as _GL

# 各族标题行数上限(超过就是标题太长该换族,不是"再断一行就好")。
# 数的是 `<br>` 断出来的显式行——CSS 自动折出来的行算不出来,所以新族必须走 break_lines。
TITLE_ROW_CAP = {
    "center-band": 2,
    "band-editorial": 2,
    "stack-cards": 4,   # 次条卡片的 4 行是有意的均匀断法(主封走 fit_title 的 2 行)
    "giant-caps": 4,   # 巨字族靠"字即画布",4 行是设计
    "kraft-note": 2,
    "plate-page": 2,
}
TITLE_MIN_PX = 22
# 主标可见字符上限:与 _gzh_layouts.TITLE_HARD_CAP 同源,一处改两处同变
TITLE_HARD_CAP = _GL.TITLE_HARD_CAP


def _resolve_theme(name: str) -> tuple[str, dict | None]:
    """旧名别名(blue/dark/green)→ 新名 + 一次性弃用提示。"""
    canonical = name
    if name in _THEME_ALIAS:
        canonical = _THEME_ALIAS[name]
        note = ("色值已统一到全局主题源,与旧 green 不同" if name == "green" else f"请改用 {canonical}")
        print(f"△ 主题名「{name}」已弃用 → 改用「{canonical}」({note})。", file=sys.stderr)
    return canonical, THEMES.get(canonical)


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def fail(error: str, hint: str = "", **extra) -> int:
    emit({"ok": False, "error": error, "hint": hint, **extra})
    return 1


def _project_fx_value_valid(value) -> bool:
    return (value is None or (isinstance(value, str)
            and (value in {"", "none"} or value in _GL.SHADER_FX)))


def _project_fx_enabled(value) -> bool:
    return isinstance(value, str) and value not in {"", "none"}


def _project_canvas_fx_matches(value, canvas_fx: list[str]) -> bool:
    if not _project_fx_value_valid(value):
        return False
    if _project_fx_enabled(value):
        return len(canvas_fx) == 1 and canvas_fx[0] == value
    return not canvas_fx


def load_project_manifest(proj: str) -> tuple[dict | None, str | None]:
    """Load an optional object manifest or return a stable structured error."""
    meta_path = os.path.join(proj, "project.json")
    if not os.path.exists(meta_path):
        return {}, None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None, "无法读取 project.json: 必须是有效 JSON"
    if not isinstance(meta, dict):
        return None, "project.json 根值必须为 JSON 对象"
    layout = meta.get("layout")
    if layout not in (None, "") and (
            not isinstance(layout, str)
            or (layout != "legacy" and layout not in _GL.LAYOUT_SLUGS)):
        return None, "project.json layout 必须是 legacy 或受支持的版式族"
    for key in ("fx", "main_fx", "sub_fx"):
        if key in meta and not _project_fx_value_valid(meta[key]):
            return None, f"project.json {key} 必须为空、none 或受支持的 shader slug"
    recipe = meta.get("bg_recipe")
    if recipe not in (None, "") and (not isinstance(recipe, str)
                                     or recipe not in _GL.BG_RECIPE_SLUGS):
        return None, "project.json bg_recipe 必须为空或受支持的背景配方"
    return meta, None


def resolve_project(slug_or_dir: str) -> str:
    """参数既可以是 slug(在 studio_dir 下找),也可以是项目目录本身。"""
    if os.path.isdir(slug_or_dir):
        return os.path.abspath(slug_or_dir)
    studio = cfg("studio_dir", near_workspace("artboard-studio"))
    cand = os.path.join(studio, slug_or_dir)
    if os.path.isdir(cand):
        return os.path.abspath(cand)
    return ""


def check_kiln() -> tuple[str, str]:
    """与 export.py 相同的引擎发现逻辑(配置 → 兜底探测)。"""
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return "cli", cli
    for cand in (near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe")),
                 near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))):
        if cand and os.path.isfile(cand):
            return "cli", cand
    return "", ""


def run_export(source_html: str, output: str, width: int, height: int,
               scale: int, webgpu: bool = False) -> dict:
    """委托 scripts/export.py; shader 页显式要求 WebGPU 并拒绝静默降级。"""
    # The WebGPU runner changes cwd to the installed Skill directory; resolve
    # caller-relative paths before that transition so output/source stay anchored
    # to the CLI caller's working directory.
    source_html = os.path.abspath(source_html)
    output = os.path.abspath(output)
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "export.py"),
           "--source", source_html, "--output", output,
           "--width", str(width), "--height", str(height),
           "--scale", str(scale), "--format", "PNG"]
    if webgpu:
        cmd.append("--webgpu")
    try:
        if webgpu:
            r = _shader_fx._run_export_with_timeout(
                cmd, cwd=SKILL_DIR, env=os.environ.copy(), timeout=600)
        else:
            r = subprocess.run(cmd, capture_output=True, timeout=600,
                               encoding="utf-8", errors="replace")
    except RuntimeError as exc:
        detail = str(exc)
        return {"ok": False,
                "error": "EXPORT_TIMEOUT" if "timed out after" in detail else "EXPORT_SPAWN_FAILED",
                "detail": detail, "hint": "手动执行: " + " ".join(cmd)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "EXPORT_SPAWN_FAILED", "detail": str(exc),
                "hint": "手动执行: " + " ".join(cmd)}
    out = r.stdout or ""
    if isinstance(out, bytes):
        out = out.decode("utf-8", errors="replace")
    lines = [l for l in out.splitlines() if l.strip()]
    if lines:
        try:
            return json.loads(lines[-1])
        except ValueError:
            pass
    err = r.stderr or ""
    if isinstance(err, bytes):
        err = err.decode("utf-8", errors="replace")
    return {"ok": False, "error": "EXPORT_BAD_OUTPUT",
            "detail": err[-300:],
            "hint": "export.py 未输出合法 JSON"}


def _html_audit(markup: str) -> _CoverHTMLAudit:
    parser = _CoverHTMLAudit()
    parser.feed(markup or "")
    parser.close()
    return parser


def _local_resource_violations(html_path: str, urls: list[str]) -> list[str]:
    """Require file-backed page resources to stay in src or explicit Skill asset roots."""
    page_dir = os.path.realpath(os.path.dirname(html_path))
    src_root = page_dir
    skill_assets = (
        os.path.join(SKILL_DIR, "fonts"),
        os.path.join(SKILL_DIR, "assets", "vendor"),
        os.path.join(SKILL_DIR, "assets", "icons"),
        os.path.join(SKILL_DIR, "vendor", "shaders"),
    )
    allowed_roots = (src_root, *(os.path.realpath(root) for root in skill_assets))
    rejected = []
    for raw in urls:
        value = html_lib.unescape(raw or "").strip()
        if not value or value.startswith("#"):
            continue
        try:
            parsed = urllib.parse.urlsplit(value)
        except (ValueError, UnicodeError):
            rejected.append(value)
            continue
        scheme = parsed.scheme.lower()
        if scheme in {"data", "mailto", "tel"}:
            continue
        if parsed.netloc:
            rejected.append(value)
            continue
        if scheme:
            if scheme != "file":
                rejected.append(value)
                continue
            path = urllib.parse.unquote(parsed.path)
            if os.name == "nt" and re.match(r"^/[a-z]:/", path, flags=re.I):
                path = path[1:]
            if not os.path.isabs(path):
                rejected.append(value)
                continue
            candidate = path
        else:
            path = urllib.parse.unquote(parsed.path)
            if not path:
                continue
            candidate = os.path.join(page_dir, path.replace("/", os.sep))
        resolved = os.path.realpath(candidate)
        if not any(_path_within(root, resolved) for root in allowed_roots):
            rejected.append(value)
    return rejected


def _font_resource_violations(html_path: str, urls: list[str]) -> list[str]:
    """Require every @font-face URL to resolve to a readable, non-empty local file."""
    rejected = []
    page_dir = os.path.realpath(os.path.dirname(html_path))
    for raw in urls:
        value = html_lib.unescape(raw or "").strip()
        if not value or _local_resource_violations(html_path, [value]):
            rejected.append(value or "empty font URL")
            continue
        try:
            parsed = urllib.parse.urlsplit(value)
        except (ValueError, UnicodeError):
            rejected.append(value)
            continue
        scheme = parsed.scheme.lower()
        if scheme == "file":
            if parsed.netloc:
                rejected.append(value)
                continue
            path = urllib.parse.unquote(parsed.path)
            if os.name == "nt" and re.match(r"^/[a-z]:/", path, flags=re.I):
                path = path[1:]
            if not os.path.isabs(path):
                rejected.append(value)
                continue
        elif not scheme and not parsed.netloc:
            path = os.path.join(page_dir,
                                urllib.parse.unquote(parsed.path).replace("/", os.sep))
        else:
            rejected.append(value)
            continue
        try:
            if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                rejected.append(value)
                continue
            with open(path, "rb") as stream:
                if not stream.read(1):
                    rejected.append(value)
        except OSError:
            rejected.append(value)
    return rejected


def _image_reference_bytes(html_path: str, raw: str, *, image_element: bool = False):
    """Resolve a reviewed local raster URL to bounded bytes; report broken img refs."""
    value = html_lib.unescape(raw or "").strip()
    if not value or value.startswith("#"):
        return None, "image element has no local raster URL" if image_element else ""
    if _local_resource_violations(html_path, [value]):
        return None, "image element URL is outside approved local roots" if image_element else ""
    try:
        parsed = urllib.parse.urlsplit(value)
    except (ValueError, UnicodeError):
        return None, "invalid image URL" if image_element else ""
    scheme = parsed.scheme.lower()
    if scheme == "data":
        header, separator, payload = value.partition(",")
        if not separator or not header.lower().startswith("data:image/"):
            return (None, "image URL is not a raster data URI" if image_element else "")
        try:
            data = (base64.b64decode(payload, validate=False)
                    if ";base64" in header.lower()
                    else urllib.parse.unquote_to_bytes(payload))
        except (ValueError, base64.binascii.Error):
            return None, "image data URI is invalid"
        if len(data) > 50 * 1024 * 1024:
            return None, "image data URI exceeds 50 MiB"
        return data, ""
    if scheme == "file":
        path = urllib.parse.unquote(parsed.path)
        if os.name == "nt" and re.match(r"^/[a-z]:/", path, flags=re.I):
            path = path[1:]
    elif not scheme and not parsed.netloc:
        path = os.path.join(os.path.dirname(html_path),
                            urllib.parse.unquote(parsed.path).replace("/", os.sep))
    else:
        return (None, "unsupported image URL scheme" if image_element else "")
    if Path(path).suffix.lower() in {".svg", ".svgz"}:
        return None, "vector images are not accepted in static covers"
    try:
        if not os.path.isfile(path):
            return (None, "image resource is missing" if image_element else "")
        size = os.path.getsize(path)
        if size > 50 * 1024 * 1024:
            return None, "image resource exceeds 50 MiB"
        with open(path, "rb") as stream:
            data = stream.read(50 * 1024 * 1024 + 1)
    except OSError:
        return (None, "image resource is unreadable" if image_element else "")
    if len(data) > 50 * 1024 * 1024:
        return None, "image resource exceeds 50 MiB"
    return data, ""


def _static_image_violations(html_path: str, audit: _CoverHTMLAudit) -> list[str]:
    """Reject animated image frames so a static export is deterministic."""
    image_refs = list(dict.fromkeys(audit.image_sources))
    css_image_refs = list(dict.fromkeys(audit.css_image_resource_urls()))
    refs = list(dict.fromkeys(image_refs + css_image_refs))
    try:
        from PIL import Image
    except ImportError:
        image_suffixes = {".png", ".apng", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif", ".svg", ".svgz"}
        candidates = []
        for raw in refs:
            try:
                suffix = Path(urllib.parse.urlsplit(raw).path).suffix.lower()
            except (ValueError, UnicodeError):
                suffix = ""
            if raw in audit.image_sources or suffix in image_suffixes:
                candidates.append(raw)
        return [f"{raw}: Pillow is required to verify static image resources" for raw in candidates]
    violations = []
    required_refs = set(image_refs) | set(css_image_refs)
    for raw in dict.fromkeys(refs):
        data, error = _image_reference_bytes(
            html_path, raw, image_element=raw in required_refs)
        if error:
            violations.append(f"{raw}: {error}")
            continue
        if data is None:
            continue
        try:
            with Image.open(io.BytesIO(data)) as image:
                image_format = image.format
                if image_format not in {"PNG", "JPEG", "WEBP", "GIF", "BMP", "AVIF"}:
                    violations.append(f"{raw}: unsupported image format {image_format}")
                    continue
                if int(getattr(image, "n_frames", 1)) > 1:
                    violations.append(f"{raw}: animated {image_format} is not allowed")
                image.verify()
            # verify() checks container structure; load() forces a full decode so
            # truncated IDAT/pixel streams cannot pass a header-only inspection.
            with Image.open(io.BytesIO(data)) as decoded:
                decoded.load()
        except Exception as exc:  # noqa: BLE001 — required raster refs fail closed
            if raw in required_refs:
                violations.append(f"{raw}: image cannot be fully decoded ({type(exc).__name__})")
    return violations


def _untrusted_script_sources(html_path: str, audit: _CoverHTMLAudit) -> list[str]:
    """Resolve the literal shader allowlist against the page and its real vendor tree."""
    if audit.base_elements:
        return list(audit.script_sources) or ["<base>"]
    page_dir = os.path.realpath(os.path.dirname(html_path))
    vendor_root = os.path.realpath(os.path.join(page_dir, "vendor", "shaders"))
    rejected = []
    for src in audit.script_sources:
        if src not in {"vendor/shaders/runtime.js", "vendor/shaders/upstream.js"}:
            rejected.append(src or "inline script")
            continue
        candidate = os.path.realpath(os.path.join(page_dir, src.replace("/", os.sep)))
        expected = os.path.realpath(os.path.join(vendor_root, os.path.basename(src)))
        if (os.path.normcase(candidate) != os.path.normcase(expected)
                or not _path_within(vendor_root, candidate)):
            rejected.append(src)
    return rejected


def _html_has_shader_canvas(markup: str) -> bool:
    """Parse canvas attributes as HTML; do not trust a manually editable marker."""
    return _html_audit(markup).shader_canvas


def _html_has_webgpu_marker(markup: str) -> bool:
    """The required marker only counts when it is an actual canvas attribute."""
    return _html_audit(markup).webgpu_marker


def html_requires_webgpu(path: str) -> bool:
    """只要页面实际含 shader canvas 就要求 Kiln WebGPU lane。"""
    try:
        with open(path, encoding="utf-8") as source:
            return _html_audit(source.read()).shader_canvas
    except OSError:
        return False


def html_requires_vendor_validation(path: str) -> bool:
    """Hash-check the vendor tree whenever a shader canvas or approved vendor script is referenced."""
    try:
        with open(path, encoding="utf-8") as source:
            audit = _html_audit(source.read())
    except OSError:
        return False
    approved = {"vendor/shaders/runtime.js", "vendor/shaders/upstream.js"}
    return audit.shader_canvas or any(src in approved for src in audit.script_sources)


# ---------------------------------------------------------------- 字体

DEFAULT_FONTS = ("smiley-sans", "source-han-sans")

FMT_BY_EXT = {"ttf": "truetype", "ttc": "truetype", "otf": "opentype",
              "woff2": "woff2", "woff": "woff"}


def _shader_vendor_missing(path: str) -> list[str]:
    required = ("runtime.js", "upstream.js", os.path.join("LICENSES", "shaders-LICENSE"))
    missing = []
    for rel in required:
        candidate = os.path.join(path, rel)
        try:
            if not os.path.isfile(candidate) or os.path.getsize(candidate) <= 0:
                missing.append(rel.replace(os.sep, "/"))
        except OSError:
            missing.append(rel.replace(os.sep, "/"))
    return missing


SHADER_VENDOR_SHA256 = _shader_fx.PINNED_VENDOR_SHA256


def _shader_vendor_hash_mismatches(path: str) -> list[str]:
    return _shader_fx.pinned_vendor_hash_mismatches(path)


def _path_within(root: str, target: str) -> bool:
    try:
        root_key = os.path.normcase(os.path.realpath(root))
        target_key = os.path.normcase(os.path.realpath(target))
        return os.path.normcase(os.path.commonpath([root_key, target_key])) == root_key
    except (OSError, ValueError):
        return False


def _is_link_or_junction(path: str) -> bool:
    if os.path.islink(path):
        return True
    try:
        return os.path.normcase(os.path.realpath(path)) != os.path.normcase(os.path.abspath(path))
    except OSError:
        return False


def _shader_vendor_link_paths(path: str) -> list[str]:
    links = []
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            child = os.path.join(current, name)
            if _is_link_or_junction(child):
                links.append(os.path.relpath(child, path).replace(os.sep, "/"))
        dirs[:] = [name for name in dirs
                   if not _is_link_or_junction(os.path.join(current, name))]
    return sorted(links)


def _shader_vendor_status(src_dir: str) -> dict | None:
    """Require the exact trusted Skill link or a hash-pinned local vendor copy."""
    vendor = os.path.join(src_dir, "vendor", "shaders")
    if not os.path.lexists(vendor) or not os.path.isdir(vendor):
        return {"error": "SHADER_VENDOR_INCOMPLETE",
                "missing": _shader_vendor_missing(vendor)}
    skill_root = os.path.realpath(os.path.join(SKILL_DIR, "vendor", "shaders"))
    project_root = os.path.realpath(os.path.dirname(src_dir))
    vendor_real = os.path.realpath(vendor)
    trusted_skill_link = _is_link_or_junction(vendor)
    if trusted_skill_link:
        if os.path.normcase(vendor_real) != os.path.normcase(skill_root):
            return {"error": "SHADER_VENDOR_LINK_FAILED", "linked": ["."]}
    elif not _path_within(project_root, vendor_real):
        return {"error": "SHADER_VENDOR_LINK_FAILED", "linked": ["."]}
    # Scanning children through a Windows junction makes every child appear to
    # escape its lexical root. Scan the trusted real Skill tree, not the alias.
    links = _shader_vendor_link_paths(skill_root if trusted_skill_link else vendor)
    if links:
        return {"error": "SHADER_VENDOR_LINK_FAILED", "linked": links}
    missing = _shader_vendor_missing(vendor)
    if missing:
        return {"error": "SHADER_VENDOR_INCOMPLETE", "missing": missing}
    mismatched = _shader_vendor_hash_mismatches(vendor)
    if mismatched:
        return {"error": "SHADER_VENDOR_HASH_MISMATCH", "mismatched": mismatched}
    return None


def _skill_shader_vendor_status() -> dict | None:
    """Validate the pinned Skill source before reserving a new project slug."""
    root = os.path.join(SKILL_DIR, "vendor", "shaders")
    if not os.path.isdir(root):
        return {"error": "SHADER_VENDOR_INCOMPLETE", "missing": _shader_vendor_missing(root)}
    real_root = os.path.realpath(root)
    links = _shader_vendor_link_paths(real_root)
    if links:
        return {"error": "SHADER_VENDOR_LINK_FAILED", "linked": links}
    missing = _shader_vendor_missing(real_root)
    if missing:
        return {"error": "SHADER_VENDOR_INCOMPLETE", "missing": missing}
    mismatched = _shader_vendor_hash_mismatches(real_root)
    if mismatched:
        return {"error": "SHADER_VENDOR_HASH_MISMATCH", "mismatched": mismatched}
    return None


def _link_shader_vendor(src_dir):
    """把完整官方 shader runtime、bundle 与 LICENSE 接入项目 src/vendor/shaders。"""
    src_sub = os.path.join(SKILL_DIR, "vendor", "shaders")
    dst_sub = os.path.join(src_dir, "vendor", "shaders")
    if (_shader_vendor_missing(src_sub) or _shader_vendor_link_paths(src_sub)
            or _shader_vendor_hash_mismatches(src_sub)):
        return False
    if os.path.lexists(dst_sub):
        return _shader_vendor_status(src_dir) is None
    os.makedirs(os.path.dirname(dst_sub), exist_ok=True)
    try:
        if os.name == "nt":
            out = subprocess.run(["cmd", "/c", "mklink", "/J", dst_sub, src_sub],
                                 capture_output=True, text=True, encoding="mbcs", errors="replace")
            if out.returncode == 0 and _shader_vendor_status(src_dir) is None:
                return True
        else:
            os.symlink(src_sub, dst_sub, target_is_directory=True)
            if _shader_vendor_status(src_dir) is None:
                return True
    except Exception:
        pass
    # 退化:真拷贝(Windows 非管理员/受限卷常见)
    try:
        shutil.copytree(src_sub, dst_sub)
        return _shader_vendor_status(src_dir) is None
    except Exception:
        return False


def build_font_assets(fam_dirs: list[str]) -> tuple[str, str]:
    """生成 @font-face 块与 --font-* 变量。第一款 = 展示体(--font-display),
    第二款 = 正文体(--font-sans);只有一款时两者同族。"""
    faces, fam_names = [], []
    for fam in fam_dirs:
        src_dir = os.path.join(SKILL_DIR, "fonts", fam)
        if not os.path.isdir(src_dir):
            print(f"△ 字体目录不存在,跳过: {fam}", file=sys.stderr)
            continue
        files = sorted(f for f in os.listdir(src_dir)
                       if f.lower().endswith(tuple(FMT_BY_EXT)))
        family = fam.replace("-", " ").title().replace(" ", "")
        fam_names.append(family)
        for fn in files:
            ext = fn.rsplit(".", 1)[-1].lower()
            faces.append(
                f"@font-face {{ font-family: '{family}'; "
                f"src: url('fonts/{fam}/{fn}') format('{FMT_BY_EXT.get(ext, 'truetype')}'); "
                f"font-weight: 100 900; font-display: block; }}")
    if not fam_names:
        return "", ""
    display = fam_names[0]
    sans = fam_names[1] if len(fam_names) > 1 else fam_names[0]
    vars_block = (f"  --font-display: '{display}';\n"
                  f"  --font-sans: '{sans}';")
    return "\n".join(faces), vars_block


def _link_project_fonts(src_dir: str, families: list[str]) -> list[str]:
    """把所选字体族接入 src/fonts,供新/legacy HTML 的相对 font-face URL 使用。"""
    source_root = os.path.join(SKILL_DIR, "fonts")
    dest_root = os.path.join(src_dir, "fonts")
    os.makedirs(dest_root, exist_ok=True)
    failures = []
    for family in families:
        if not family or os.path.basename(family) != family or family in (".", ".."):
            failures.append(f"非法字体族路径: {family}")
            continue
        source = os.path.join(source_root, family)
        dest = os.path.join(dest_root, family)
        if not os.path.isdir(source):
            continue  # build_font_assets 已负责报告缺失目录
        if os.path.exists(dest):
            continue  # 保留用户自己的字体副本/链接
        try:
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", dest, source],
                                        capture_output=True, text=True, encoding="mbcs",
                                        errors="replace")
                if result.returncode == 0:
                    continue
            else:
                os.symlink(source, dest, target_is_directory=True)
                continue
        except OSError:
            pass
        try:
            shutil.copytree(source, dest)
        except OSError as exc:
            failures.append(f"{family}: {exc}")
    return failures


# ---------------------------------------------------------------- HTML 模板

def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") \
        .replace("\n", "<br>")


def main_html(w: int, h: int, t: dict, title: str, kicker: str, sub: str,
              footer: str, num: str, faces: str, font_vars: str) -> str:
    """主封面 900×383 旧版居中模板(center-band 的 legacy 输出,逐字节保留)。

    新族一律走 _gzh_layouts.render();本函数只为保证「不加 --layout 行为不变」。"""
    return _legacy_main(w, h, t, title, kicker, sub, footer, num, faces, font_vars)


def _legacy_main(w: int, h: int, t: dict, title: str, kicker: str, sub: str,
                 footer: str, num: str, faces: str, font_vars: str) -> str:
    """主封面 900×383:旧版居中排版,按内部约 383px 安全栏布置信息;
    该安全栏是保守构图约定,不保证平台转发/分享裁切范围。"""
    kicker_html = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    footer_html = f'<div class="footer">{esc(footer)}</div>' if footer else ""
    num_html = f'<div class="num">{esc(num)}</div>' if num else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>gzh-main · {esc(title)}</title>
<style>
/* ===== 字体(gzh_cover 生成;fonts/ 经目录联接指向 Skill 字体库) ===== */
{faces}

/* ===== 画布:900×383 Artboard 工作画布;平台显示/裁切须以后台预览核验 ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; background: #ffffff; }}
.poster {{
  position: relative;
  width: {w}px;
  height: {h}px;
  overflow: hidden;
  background: linear-gradient(135deg, {t['bg']} 0%, {t['bg2']} 100%);
}}
:root {{
  --c-ink: {t['ink']};
  --c-accent: {t['accent']};
  --c-muted: {t['muted']};
{font_vars}
}}

/* ===== 内部保守排版安全区:关键信息置于中央 383px 栏,非平台裁切保证 ===== */
.safe {{
  position: absolute; left: 50%; top: 0; bottom: 0; width: 383px;
  transform: translateX(-50%);
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center; gap: 16px;
}}
.mark {{ width: 44px; height: 8px; background: var(--c-accent); }}
.kicker {{ font: 600 16px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .42em; text-indent: .42em; }}
.t {{ font: 700 54px/1.25 var(--font-display);
  color: var(--c-ink); letter-spacing: .02em; max-width: 360px; }}
.sub {{ font: 400 18px/1.4 var(--font-sans); color: var(--c-muted);
  letter-spacing: .16em; text-indent: .16em; max-width: 340px; }}

/* ===== 边缘装饰(允许在安全区外) ===== */
.bar {{ position: absolute; left: 0; top: 0; bottom: 0; width: 10px; background: var(--c-accent); }}
.footer {{ position: absolute; left: 0; right: 0; bottom: 36px;
  text-align: center;
  font: 500 14px/1 var(--font-sans); color: var(--c-muted); letter-spacing: .3em; }}
.num {{ position: absolute; right: 48px; top: 32px;
  font: 800 84px/1 var(--font-display);
  color: var(--c-accent); opacity: .30; }}
</style>
</head>
<body>
  <div class="poster">
    <div class="bar"></div>
    {num_html}
    <div class="safe">
      <div class="mark"></div>
      {kicker_html}
      <h1 class="t">{esc(title)}</h1>
      {sub_html}
    </div>
    {footer_html}
  </div>
</body>
</html>"""


def sub_html(w: int, h: int, t: dict, title: str, kicker: str, sub: str,
             faces: str, font_vars: str) -> str:
    """次条封面 383×383 旧版模板(center-band 的 legacy 输出,逐字节保留)。"""
    return _legacy_sub(w, h, t, title, kicker, sub, faces, font_vars)


def _legacy_sub(w: int, h: int, t: dict, title: str, kicker: str, sub: str,
                faces: str, font_vars: str) -> str:
    """旧版次条兼容模板:居中排版,最多三项(眉题/标题/副题);不约束新六族或平台规则。"""
    kicker_html = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>gzh-sub · {esc(title)}</title>
<style>
/* ===== 字体(与主封面同一套,保证双封面同气质) ===== */
{faces}

/* ===== 383×383 Artboard 内部次条画布;旧版模板最多三项,平台显示以后台预览为准 ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; background: #ffffff; }}
.poster {{
  position: relative;
  width: {w}px;
  height: {h}px;
  overflow: hidden;
  background: linear-gradient(135deg, {t['bg']} 0%, {t['bg2']} 100%);
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center; gap: 16px;
}}
:root {{
  --c-ink: {t['ink']};
  --c-accent: {t['accent']};
  --c-muted: {t['muted']};
{font_vars}
}}

/* ===== 版式:居中堆叠;顶部小色块是唯一装饰 ===== */
.mark {{ width: 44px; height: 8px; background: var(--c-accent); }}
.kicker {{ font: 600 13px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .38em; text-indent: .38em; }}
.t {{ font: 700 44px/1.3 var(--font-display); color: var(--c-ink);
  letter-spacing: .02em; max-width: 315px; }}
.sub {{ font: 400 15px/1.5 var(--font-sans); color: var(--c-muted);
  letter-spacing: .12em; max-width: 300px; }}
</style>
</head>
<body>
  <div class="poster">
    <div class="mark"></div>
    {kicker_html}
    <h1 class="t">{esc(title)}</h1>
    {sub_html}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------- 子命令

def _png_stream_decodable(source: str, max_bytes: int = 50 * 1024 * 1024) -> bool:
    """Validate PNG chunks, CRCs, zlib image stream, scanline sizes and filter bytes."""
    signature = b"\x89PNG\r\n\x1a\n"
    try:
        with open(source, "rb") as stream:
            data = stream.read(max_bytes + 1)
    except OSError:
        return False
    if len(data) > max_bytes or not data.startswith(signature):
        return False
    offset = len(signature)
    seen_ihdr = seen_idat = seen_iend = seen_plte = idat_closed = False
    width = height = bit_depth = color_type = interlace = 0
    inflater = None
    row_sizes: list[int] = []
    row_index = 0
    row_remaining = None
    filter_pending = False

    def consume(decoded: bytes) -> bool:
        nonlocal row_index, row_remaining, filter_pending
        cursor = 0
        while cursor < len(decoded):
            if row_remaining is None:
                return False
            if filter_pending:
                if decoded[cursor] > 4:
                    return False
                filter_pending = False
            count = min(row_remaining, len(decoded) - cursor)
            cursor += count
            row_remaining -= count
            if row_remaining == 0:
                row_index += 1
                row_remaining = row_sizes[row_index] if row_index < len(row_sizes) else None
                filter_pending = row_remaining is not None
        return True

    try:
        while offset < len(data):
            if offset + 12 > len(data):
                return False
            length = int.from_bytes(data[offset:offset + 4], "big")
            kind = data[offset + 4:offset + 8]
            start = offset + 8
            end = start + length
            crc_end = end + 4
            if crc_end > len(data) or not all(
                    (65 <= byte <= 90) or (97 <= byte <= 122) for byte in kind):
                return False
            payload = data[start:end]
            expected_crc = int.from_bytes(data[end:crc_end], "big")
            if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
                return False
            if not seen_ihdr and kind != b"IHDR":
                return False
            if seen_idat and kind != b"IDAT":
                idat_closed = True
            if kind == b"IHDR":
                if seen_ihdr or length != 13:
                    return False
                width = int.from_bytes(payload[0:4], "big")
                height = int.from_bytes(payload[4:8], "big")
                bit_depth, color_type = payload[8], payload[9]
                interlace = payload[12]
                channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
                depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16},
                          3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
                if (not width or not height or width > 100_000 or height > 100_000
                        or width * height > 100_000_000 or channels is None
                        or bit_depth not in depths[color_type]
                        or payload[10] != 0 or payload[11] != 0 or interlace not in {0, 1}):
                    return False
                bits_per_pixel = channels * bit_depth
                passes = ([(0, 0, 1, 1)] if interlace == 0 else
                          [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
                           (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)])
                for x0, y0, dx, dy in passes:
                    pass_width = (width - x0 + dx - 1) // dx if width > x0 else 0
                    pass_height = (height - y0 + dy - 1) // dy if height > y0 else 0
                    if pass_width and pass_height:
                        row_size = (pass_width * bits_per_pixel + 7) // 8 + 1
                        row_sizes.extend([row_size] * pass_height)
                if sum(row_sizes) > 256 * 1024 * 1024:
                    return False
                row_remaining = row_sizes[0] if row_sizes else None
                filter_pending = row_remaining is not None
                seen_ihdr = True
            elif kind == b"PLTE":
                if (seen_plte or seen_idat or not (3 <= length <= 768 and length % 3 == 0)
                        or color_type in {0, 4}):
                    return False
                seen_plte = True
            elif kind in {b"acTL", b"fcTL", b"fdAT"}:
                return False
            elif kind == b"IDAT":
                if idat_closed or not seen_ihdr or (color_type == 3 and not seen_plte):
                    return False
                if inflater is None:
                    inflater = zlib.decompressobj()
                pending = payload
                while pending:
                    decoded = inflater.decompress(pending, 1024 * 1024)
                    pending = inflater.unconsumed_tail
                    if inflater.unused_data or not consume(decoded):
                        return False
                    if not pending:
                        break
                seen_idat = True
            elif kind == b"IEND":
                if length != 0 or not seen_idat or inflater is None or not inflater.eof:
                    return False
                if row_remaining is not None or row_index != len(row_sizes):
                    return False
                seen_iend = True
                offset = crc_end
                break
            elif (kind[0] & 0x20) == 0 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
                return False
            offset = crc_end
        return seen_ihdr and seen_idat and seen_iend and offset == len(data)
    except (ValueError, OverflowError, zlib.error):
        return False


def _other_raster_decodable(source: str, expected_format: str) -> bool:
    """Use Pillow's full decoder for JPEG/WebP; never accept a header-only probe."""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(source) as image:
            if (image.format != expected_format or image.width <= 0 or image.height <= 0
                    or image.width * image.height > 100_000_000
                    or getattr(image, "n_frames", 1) != 1
                    or bool(getattr(image, "is_animated", False))):
                return False
            image.verify()
        with Image.open(source) as image:
            image.load()
        return True
    except Exception:  # noqa: BLE001 — decoder errors are an invalid local asset
        return False


def _local_raster_spec(path: str):
    """只接受完整可解码且压缩文件 ≤50 MiB 的本地 PNG/JPEG/WebP,不信任后缀或 URL。"""
    if not path:
        return None, ""
    source = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(source):
        return None, "IMAGE_NOT_FOUND"
    try:
        size = os.path.getsize(source)
        with open(source, "rb") as image:
            header = image.read(24)
            image.seek(-2, os.SEEK_END) if size >= 2 else None
            tail = image.read(2) if size >= 2 else b""
    except OSError:
        return None, "IMAGE_READ_FAILED"
    if size > 50 * 1024 * 1024:
        return None, "IMAGE_TOO_LARGE"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        if not _png_stream_decodable(source):
            return None, "IMAGE_DECODE_FAILED"
        ext = ".png"
    elif header.startswith(b"\xff\xd8\xff") and size >= 4 and tail == b"\xff\xd9":
        if not _other_raster_decodable(source, "JPEG"):
            return None, "IMAGE_DECODE_FAILED"
        ext = ".jpg"
    elif (header[:4] == b"RIFF" and header[8:12] == b"WEBP" and size >= 20
          and int.from_bytes(header[4:8], "little") + 8 == size):
        if not _other_raster_decodable(source, "WEBP"):
            return None, "IMAGE_DECODE_FAILED"
        ext = ".webp"
    else:
        return None, "IMAGE_FORMAT_UNSUPPORTED"
    return {"source": source, "filename": "plate-page-image" + ext}, ""


def _install_local_raster(src_dir: str, spec: dict):
    """Install without replacing any pre-existing project asset or following escapes."""
    image_dir = os.path.join(src_dir, "images")
    try:
        os.makedirs(image_dir, exist_ok=True)
        src_real = os.path.realpath(src_dir)
        image_real = os.path.realpath(image_dir)
        if os.path.normcase(os.path.commonpath([src_real, image_real])) != os.path.normcase(src_real):
            return "", "IMAGE_PATH_ESCAPE"
        dest = os.path.join(image_dir, spec["filename"])
        if os.path.lexists(dest):
            if os.path.islink(dest) or not os.path.isfile(dest):
                return "", "IMAGE_DEST_CONFLICT"
            if not filecmp.cmp(spec["source"], dest, shallow=False):
                return "", "IMAGE_DEST_CONFLICT"
        else:
            shutil.copyfile(spec["source"], dest)
    except (OSError, ValueError):
        return "", "IMAGE_COPY_FAILED"
    return "images/" + spec["filename"], ""


def build_layout_data(args) -> dict:
    """把 CLI 参数整理成版式层要的 data 结构。"""
    meta = [s.strip() for s in (args.meta or "").split(",") if s.strip()]
    return _GL.make_data(
        title=args.title, kicker=args.kicker, sub=args.sub,
        footer=args.footer, num=args.num, title_en=args.title_en,
        badge=args.badge, side_label=args.side_label, meta=meta,
        accent_tone=args.accent_tone, sub_mode=args.sub_mode,
        image=getattr(args, "image_ref", None))


_SUB_TITLE_SEP = re.compile(r"[·・|｜/／、,，:：;；—–\-\s]+")


def distill_subtitle(title: str) -> tuple[str, bool]:
    """从主标提炼次条标题;返回 (次条标题, 是否回落成主标)。

    次条默认复制主标,是「两页看起来一样」的根源:次条走 383×383 方图,
    标题必须更短、更提炼,不能照搬主标的排布。规则按序:
    1) 主标 ≤4 字 → 原样(再缩就没信息了);
    2) 有分隔符(·/|/空格/破折号)→ 取第一段,长度落在 [2, min(4, n-2)];
    3) 否则取前 min(4, n-2) 个可见字符(中文标题语序最稳的短版)。
    回落(没能提炼)时返回 True,由 check 的 sub-title-distilled 要求人工确认。
    """
    text = (title or "").strip()
    visible = "".join(_GL.plain(text).split())
    n = _GL.visible_len(visible)
    if n <= 4:
        return text, True
    target = max(2, min(4, n - 2))
    parts = [p.strip() for p in _SUB_TITLE_SEP.split(text) if p.strip()]
    if len(parts) >= 2:
        head = parts[0]
        if 2 <= _GL.visible_len("".join(head.split())) <= target:
            return head, False
    chars = [c for c in _GL.grapheme_clusters(_GL.plain(text)) if not c.isspace()]
    head = "".join(chars[:target])
    return head, head == visible


def cmd_new(args) -> int:
    if not args.slug or not args.title:
        return fail("MISSING_ARGS",
                    "new 需要 <slug> 与 --title;想看版式族用: new --list-layouts")
    proj_dir = args.slug if os.path.isabs(args.slug) else \
        os.path.join(cfg("studio_dir", near_workspace("artboard-studio")), args.slug)
    project_preexisting = os.path.lexists(proj_dir)
    if project_preexisting and not args.force:
        return fail("EXISTS", "换 slug 或 --force", path=os.path.abspath(proj_dir))
    theme_name, t = _resolve_theme(args.theme)
    if t is None:
        return fail("BAD_THEME", f"可选主题: {', '.join(sorted(THEMES))}"
                                  "(旧名 blue/dark/green 仍可用,见弃用提示)")
    # 版式族校验(--layout 缺省 = None = 旧版模板,输出逐字节不变)
    layout = args.layout or None
    if layout and layout not in _GL.LAYOUT_SLUGS:
        return fail("BAD_LAYOUT",
                    f"可选: {', '.join(_GL.LAYOUT_SLUGS)};用 new --list-layouts 看每族适用文案",
                    layout=layout)
    image_input = getattr(args, "image", "")
    if image_input and layout != "plate-page":
        return fail("IMAGE_LAYOUT_CONFLICT", "--image 仅供 --layout plate-page 使用")
    image_spec = None
    titles = [("主封", args.title), ("次条", args.sub_title or args.title)]
    for kind, value in titles:
        visible = "".join(_GL.plain(value).split())
        visible_count = _GL.visible_len(visible)
        if visible_count > TITLE_HARD_CAP:
            return fail("TITLE_TOO_LONG",
                        f"{kind}标题最多 {TITLE_HARD_CAP} 个可见字符(中文建议 ≤9 字),"
                        f"当前 {visible_count} 个;标题太长会挤掉字号,换族或压短文案",
                        kind=kind, length=visible_count, max=TITLE_HARD_CAP)
    if layout == "plate-page":
        if not image_input:
            return fail("IMAGE_REQUIRED", "plate-page 必须用 --image 提供本地 PNG/JPEG/WebP 照片")
        image_spec, image_error = _local_raster_spec(image_input)
        if image_error:
            return fail(image_error, "--image 需要可读的本地 PNG/JPEG/WebP 文件", image=image_input)
    if layout:
        try:
            visual_pattern, shader_fx = _GL.resolve_visual_layers(
                layout, args.bg_pattern, getattr(args, "fx", "auto"))
        except ValueError as exc:
            return fail("BACKGROUND_LAYER_CONFLICT", str(exc))
        try:
            bg_recipe = _GL.resolve_bg_recipe(getattr(args, "bg_recipe", ""))
        except ValueError as exc:
            return fail("BAD_BG_RECIPE", str(exc))
        # 两种底材不叠加:配方是 CSS 底纹,fx 是 canvas 底材,同屏会把配方盖成
        # 一层粗网点(实测 warm 主题默认 halftone + dots-grid)。fx 是 auto 时静默
        # 让位给配方;用户显式点了 fx 则报冲突,不替他做决定。
        if bg_recipe and shader_fx and shader_fx != "none":
            if getattr(args, "fx", "auto") == "auto":
                print(f"· 已选背景配方 {bg_recipe},主题默认底材 {shader_fx} 让位"
                      f"(要保留请显式 --fx {shader_fx})", file=sys.stderr)
                # 必须落成显式 "none":空串在 render() 里会被当成 auto 再解析回族默认。
                shader_fx = "none"
            else:
                return fail("BACKGROUND_LAYER_CONFLICT",
                            f"--bg-recipe {bg_recipe} 与 --fx {shader_fx} 是两种底材,只能选一种")
    else:
        visual_pattern, shader_fx = "none", ""
        bg_recipe = ""
    fams = DEFAULT_FONTS if args.fonts == "auto" else \
        [s.strip() for s in args.fonts.split(",") if s.strip()]
    faces, font_vars = build_font_assets(fams)
    if not faces:
        return fail("NO_FONTS", "fonts/ 下找不到所选字体目录", fonts=args.fonts)

    if shader_fx:
        vendor_issue = _skill_shader_vendor_status()
        if vendor_issue:
            return fail(vendor_issue["error"], "本地 shader runtime、upstream bundle 或 LICENSE 未安全接入",
                        missing_source=_shader_vendor_missing(
                            os.path.join(SKILL_DIR, "vendor", "shaders")),
                        **{key: value for key, value in vendor_issue.items() if key != "error"})

    created_project_root = False
    if not project_preexisting:
        try:
            os.makedirs(proj_dir, exist_ok=False)
            created_project_root = True
        except FileExistsError:
            return fail("EXISTS", "换 slug 或 --force", path=os.path.abspath(proj_dir))
    else:
        os.makedirs(proj_dir, exist_ok=True)

    def rollback_new_project():
        if not created_project_root:
            return
        try:
            if os.path.isdir(proj_dir) and not _is_link_or_junction(proj_dir):
                shutil.rmtree(proj_dir)
        except OSError:
            pass

    src = os.path.join(proj_dir, "src")
    os.makedirs(src, exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "export"), exist_ok=True)
    font_link_failures = _link_project_fonts(src, fams)
    if font_link_failures:
        rollback_new_project()
        return fail("FONT_LINK_FAILED", "所选字体未能接入项目", detail=font_link_failures)
    image_ref = None
    if image_spec:
        image_ref, image_error = _install_local_raster(src, image_spec)
        if image_error:
            rollback_new_project()
            return fail(image_error, "本地照片无法安全接入 src/images,未覆盖现有项目资产",
                        image=image_input)
    args.image_ref = image_ref

    sub_title = args.sub_title or distill_subtitle(args.title)[0]
    if not args.sub_title:
        # 次条标题默认由主标提炼,而不是复制主标(缩排根源)
        print("· 次条标题缺省,已从主标提炼为:" + sub_title, file=sys.stderr)
    sub_sub = args.sub_sub or args.sub
    if layout:
        data_main = build_layout_data(args)
        data_sub = dict(data_main, title=sub_title, sub=sub_sub)
        files = {
            "index.html": _GL.render(layout, t, data_main, font_vars, sub=False,
                                     pattern=visual_pattern, tone=args.accent_tone,
                                     fx=shader_fx, font_faces=faces,
                                     bg_recipe=bg_recipe),
            "sub.html": _GL.render(layout, t, data_sub, font_vars, sub=True,
                                   pattern=visual_pattern, tone=args.accent_tone,
                                   fx=shader_fx, font_faces=faces,
                                   bg_recipe=bg_recipe),
        }
    else:
        files = {
            "index.html": main_html(MAIN_W, MAIN_H, t, args.title, args.kicker,
                                    args.sub, args.footer, args.num, faces, font_vars),
            "sub.html": sub_html(SUB_W, SUB_H, t, sub_title, args.kicker,
                                 sub_sub, faces, font_vars),
        }
    # 先确认本地 shader 运行时/官方 bundle/LICENSE 都已接入,再写引用这些文件的 HTML。
    if shader_fx and not _link_shader_vendor(src):
        issue = _shader_vendor_status(src) or _skill_shader_vendor_status() or {
            "error": "SHADER_VENDOR_INCOMPLETE",
            "missing": _shader_vendor_missing(os.path.join(src, "vendor", "shaders")),
        }
        rollback_new_project()
        return fail(issue["error"], "本地 shader runtime、upstream bundle 或 LICENSE 未安全接入",
                    missing_source=_shader_vendor_missing(os.path.join(SKILL_DIR, "vendor", "shaders")),
                    **{key: value for key, value in issue.items() if key != "error"})

    for name, html in files.items():
        with open(os.path.join(src, name), "w", encoding="utf-8") as f:
            f.write(html)

    project = {"slug": os.path.basename(os.path.abspath(proj_dir)),
               "kind": "gzh-cover",
               "main": [MAIN_W, MAIN_H], "sub": [SUB_W, SUB_H],
               "theme": theme_name, "fonts": args.fonts,
               # 交付口径:merged = 只出合并图(默认);split = 三张单图都要
               "deliver": getattr(args, "deliver", "merged") or "merged",
               "skill_dir": SKILL_DIR, "created_by": "artboard.gzh_cover"}
    if layout:
        project["layout"] = layout
        project["bg_pattern"] = visual_pattern
        project["bg_recipe"] = bg_recipe
        project["accent_tone"] = _GL.resolve_tone(layout, args.accent_tone)
        project["sub_mode"] = args.sub_mode
        # 旧版 fx 保留兼容;new 版同时记录每页真实底材,flat 次条不会误报 shader。
        project["fx"] = shader_fx
        project["main_fx"] = shader_fx
        project["sub_fx"] = "" if args.sub_mode == "flat" else shader_fx
        if image_ref:
            project["image"] = image_ref
    with open(os.path.join(proj_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)

    out = {"ok": True, "project": os.path.abspath(proj_dir),
           "files": [f"src/{k}" for k in files],
           "main": f"{MAIN_W}x{MAIN_H}", "sub": f"{SUB_W}x{SUB_H}",
           "next": f"python scripts/gzh_cover.py export \"{os.path.abspath(proj_dir)}\""}
    if layout:
        spec = _GL.layout_spec(layout)
        out["layout"] = {"slug": layout, "name": spec.get("name", ""),
                         "tone": spec.get("tone", ""), "layers": spec.get("layers", "")}
        out["bg_pattern"] = project["bg_pattern"]
        if project.get("bg_recipe"):
            out["bg_recipe"] = project["bg_recipe"]
        out["accent_tone"] = project["accent_tone"]
    emit(out)
    return 0


def find_kiln_for_img() -> str:
    """与 export.py 相同的 Kiln 引擎发现(位图拼接走 kiln img 工具箱)。"""
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    for cand in (near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe")),
                 near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def stitch_merged(main_png: str, sub_png: str, out_path: str, gap: int,
                  bg: str) -> dict:
    """等高拼接:主封面在左,次条在右,间隔 gap px,浅底色。
    v1.9:委托 kiln-cli img stitch(纯像素搬运,不缩放不重采样)。"""
    kiln = find_kiln_for_img()
    if not kiln:
        return {"ok": False, "error": "KILN_NOT_FOUND",
                "hint": "跑 scripts/setup_kiln.py 部署(kiln img 工具箱用于拼接)"}
    try:
        r = subprocess.run(
            [kiln, "img", "stitch",
             "--inputs", f"{main_png},{sub_png}",
             "--output", out_path,
             "--direction", "horizontal", "--gap", str(gap),
             "--bg", bg, "--align", "center"],
            capture_output=True, timeout=120)
        if r.returncode != 0:
            err = r.stderr.decode("utf-8", errors="replace")[:200]
            return {"ok": False, "error": "STITCH_FAILED", "detail": err,
                    "hint": "检查两张 PNG 是否存在且未损坏"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "STITCH_FAILED", "detail": str(exc)}
    # 读取输出尺寸:优先用 kiln 的 JSON 回报;解析不到就回读产物(PIL),
    # 保证 ok:true 时 width/height 一定存在(下游 size 字段不再出现 NonexNone)。
    size = None
    try:
        lines = r.stdout.decode("utf-8", errors="replace").strip().splitlines()
        j = json.loads(lines[-1])
        if j.get("width") and j.get("height"):
            size = (j["width"], j["height"])
    except Exception:  # noqa: BLE001
        size = None
    if size is None:
        try:
            from PIL import Image
            with Image.open(out_path) as im:
                size = im.size
        except Exception:  # noqa: BLE001 — 拼接已成功,尺寸读不到不算失败
            size = (None, None)
    out = {"ok": True, "path": os.path.abspath(out_path),
           "width": size[0], "height": size[1]}
    if size[0] is None:
        out["warning"] = "拼接成功但尺寸未能读出(产物请在文件管理器核对)"
    return out


def cmd_export(args) -> int:
    proj = resolve_project(args.project)
    if not proj:
        return fail("PROJECT_NOT_FOUND", "传项目目录或 slug", project=args.project)
    src = os.path.join(proj, "src")
    main_html_p = os.path.join(src, "index.html")
    sub_html_p = os.path.join(src, "sub.html")
    if not os.path.isfile(main_html_p):
        return fail("NO_MAIN_HTML", "src/index.html 不存在;先跑 gzh_cover.py new", project=proj)
    if args.only in ("", "sub") and not os.path.isfile(sub_html_p):
        return fail("NO_SUB_HTML", "src/sub.html 不存在;先跑 gzh_cover.py new", project=proj)
    meta, manifest_error = load_project_manifest(proj)
    if manifest_error:
        return fail("PROJECT_MANIFEST_INVALID", manifest_error, project=proj)
    if args.only != "merged":
        project_fx = meta.get("fx") if "fx" in meta else None
        layout = meta.get("layout") or "legacy"
        targets = ([('main', main_html_p, MAIN_W)] if args.only == "main" else
                   [('sub', sub_html_p, SUB_W)] if args.only == "sub" else
                   [('main', main_html_p, MAIN_W), ('sub', sub_html_p, SUB_W)])
        for kind, page, width in targets:
            page_fx = meta.get(f"{kind}_fx", project_fx)
            has_shader = html_requires_webgpu(page)
            try:
                with open(page, "r", encoding="utf-8") as f:
                    markup = f.read()
            except OSError as exc:
                return fail("HTML_READ_FAILED", str(exc), page=page)
            page_audit = _html_audit(markup)
            has_marker = page_audit.webgpu_marker
            project_matches = _project_canvas_fx_matches(
                page_fx, page_audit.shader_canvas_fx)
            if has_shader != has_marker or not project_matches:
                return fail("WEBGPU_REQUIREMENT_MISMATCH",
                            "实际 shader canvas、required标记和对应页面 project.json fx 不一致",
                            page=page, shader_canvas=has_shader,
                            marker=has_marker, project_fx=page_fx)
            approved_vendor_scripts = {"vendor/shaders/runtime.js", "vendor/shaders/upstream.js"}
            vendor_validation_required = (has_shader or any(
                script in approved_vendor_scripts for script in page_audit.script_sources))
            if vendor_validation_required:
                vendor_issue = _shader_vendor_status(src)
                if vendor_issue:
                    return fail(vendor_issue["error"],
                                "shader 页面必须使用哈希固定的可信 Skill/vendor 文件",
                                page=page,
                                **{key: value for key, value in vendor_issue.items()
                                   if key != "error"})
            bad = [row for row in check_one(page, width, layout, page_fx) if not row["ok"]]
            if bad:
                return fail("COVER_CHECK_FAILED", "导出前静态质量检查未通过",
                            kind=kind, coverage="partial" if layout == "legacy" else "complete",
                            failed=bad,
                            next_action="运行 gzh_cover.py check 并根据 failed/detail 修正文案或版式")
    if args.only != "merged" and not check_kiln():
        return fail("KILN_NOT_FOUND",
                    "跑 scripts/setup_kiln.py 部署,或设 ARTBOARD_KILN_CLI 指向 Kiln-noGUI-CLI.exe")

    outdir = args.outdir or os.path.join(proj, "export")
    os.makedirs(outdir, exist_ok=True)
    slug = os.path.basename(proj.rstrip("\\/"))
    split = bool(getattr(args, "split", False))
    # 交付口径:默认只出一张合并图(公众号后台一次上传一张),--split 才出三张单图。
    # 单图模式下单张只是中间产物,渲染到 .parts/ 临时目录,拼完即删,不让用户看到半成品。
    single = args.only == "" and not split
    merged_name = f"cover-{slug}.png"
    parts_dir = ""
    if single:
        parts_dir = os.path.join(outdir, ".parts")
        shutil.rmtree(parts_dir, ignore_errors=True)
        os.makedirs(parts_dir, exist_ok=True)
        main_png = os.path.join(parts_dir, f"cover-main-{slug}.png")
        sub_png = os.path.join(parts_dir, f"cover-sub-{slug}.png")
    else:
        main_png = os.path.join(outdir, f"cover-main-{slug}.png")
        sub_png = os.path.join(outdir, f"cover-sub-{slug}.png")

    def bake(kind, page, png, width) -> tuple[dict, bool]:
        r = run_export(page, png, width, MAIN_H if width == MAIN_W else SUB_H,
                       args.scale, webgpu=html_requires_webgpu(page))
        ok = bool(r.get("ok"))
        row = {"kind": kind, "output": png,
               **({"size": f"{r.get('width')}x{r.get('height')}"} if ok
                  else {"error": r.get("error")})}
        if not ok:
            failed.append({"kind": kind, **r})
        return row, ok

    exports, failed = [], []
    merged = {}
    if args.only == "merged":
        existing = [p for p in (os.path.join(outdir, merged_name),
                                os.path.join(outdir, f"cover-merged-{slug}.png"))
                    if os.path.isfile(p)]
        if not existing:
            return fail("MISSING_EXPORTS",
                        "export 默认已直接产出单张封面(cover-<slug>.png),无需 --only merged;"
                        "若是旧产物请先跑 export",
                        missing=[os.path.join(outdir, merged_name)])
        merged = {"ok": True, "path": existing[0]}
        exports.append({"kind": "merged", "output": existing[0]})
    else:
        if args.only in ("", "main"):
            row, ok = bake("main", main_html_p, main_png, MAIN_W)
            if not single:
                exports.append(row)
        if args.only in ("", "sub"):
            row, ok = bake("sub", sub_html_p, sub_png, SUB_W)
            if not single:
                exports.append(row)
        if args.only == "" and not failed:
            target = os.path.join(outdir, merged_name if single
                                  else f"cover-merged-{slug}.png")
            merged = stitch_merged(main_png, sub_png, target,
                                   gap=MERGE_GAP * args.scale, bg=args.bg)
            exports.append({"kind": "cover" if single else "merged",
                            "output": merged.get("path", target), **(
                                {"size": f"{merged.get('width')}x{merged.get('height')}"}
                                if merged.get("ok") else {"error": merged.get("error")})})
            if not merged.get("ok"):
                failed.append({"kind": "merged", **merged})

    if single:
        shutil.rmtree(parts_dir, ignore_errors=True)

    payload = {"ok": not failed, "project": proj, "exports": exports,
               "deliver": "single" if single else "split"}
    if merged.get("ok"):
        payload["merged"] = merged["path"]
    if failed:
        payload["failed"] = failed
        payload["hint"] = "单张失败不影响其他产物;按 error 处理后重跑(幂等覆盖)"
    elif single:
        payload["hint"] = "默认只交付一张合并图(长封面在左+方形在右);要单张分别用加 --split"
    emit(payload)
    return 0 if not failed else 1


def cmd_merge(args) -> int:
    """仅重拼合并图:单张 PNG 已在时使用,不重导(不需要引擎)。"""
    proj = resolve_project(args.project)
    if not proj:
        return fail("PROJECT_NOT_FOUND", "传项目目录或 slug", project=args.project)
    outdir = os.path.join(proj, "export")
    slug = os.path.basename(proj.rstrip("\\/"))
    main_png = os.path.join(outdir, f"cover-main-{slug}.png")
    sub_png = os.path.join(outdir, f"cover-sub-{slug}.png")
    missing = [p for p in (main_png, sub_png) if not os.path.isfile(p)]
    if missing:
        return fail("MISSING_EXPORTS", "先跑 gzh_cover.py export 生成单张封面",
                    missing=missing)
    # 间隔按导出倍率放大:从主封面 PNG 实宽反推 scale(900 为 CSS 画布宽)
    try:
        from PIL import Image
        with Image.open(main_png) as im:
            px_scale = max(1, round(im.width / MAIN_W))
    except Exception:  # noqa: BLE001
        px_scale = 1
    r = stitch_merged(main_png, sub_png,
                      os.path.join(outdir, f"cover-merged-{slug}.png"),
                      gap=args.gap * px_scale, bg=args.bg)
    emit(r)
    return 0 if r.get("ok") else 1


def _has_nested_css_blocks(css: str) -> bool:
    """Reject CSS nesting/ambiguous blocks until the static audit can resolve them."""
    depth = 0
    quote = ""
    index = 0
    while index < len(css):
        char = css[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if css.startswith("/*", index):
            end = css.find("*/", index + 2)
            if end < 0:
                return True
            index = end + 2
            continue
        if char in "\"'":
            quote = char
            index += 1
            continue
        if char == "\\":
            # Skip one CSS escape (up to six hex digits and optional whitespace).
            index += 1
            if index < len(css) and css[index] in "0123456789abcdefABCDEF":
                count = 0
                while index < len(css) and count < 6 and css[index] in "0123456789abcdefABCDEF":
                    index += 1
                    count += 1
                if index < len(css) and css[index].isspace():
                    index += 1
            elif index < len(css):
                index += 1
            continue
        if char == "{":
            if depth:
                return True
            depth = 1
        elif char == "}":
            if not depth:
                return True
            depth = 0
        index += 1
    return bool(depth or quote)


def _css_prop(css: str, name: str) -> str:
    """取一条 CSS 块里某属性的原值(取最后一次声明)。"""
    vals = re.findall(rf"(?<![-\w]){name}\s*:\s*([^;}}]+)", css, flags=re.I)
    return vals[-1].strip() if vals else ""


def _css_values(css: str, name: str) -> list[str]:
    return [value.strip() for value in re.findall(
        rf"(?<![-\w]){re.escape(name)}\s*:\s*([^;{{}}]+)", css, flags=re.I)]


def _selector_targets_class(selector: str, class_name: str) -> bool:
    escaped = re.escape(class_name)
    for member in selector.split(","):
        member = member.strip()
        # Pseudo-element rules decorate the element but do not override its box.
        if re.search(r"::[\w-]+(?:\([^)]*\))?\s*$", member):
            continue
        subject = re.split(r"\s*[>+~]\s*|\s+", member)[-1]
        if re.search(rf"(?<![-\w])\.{escaped}(?![-\w])", subject, flags=re.I):
            return True
        if re.search(rf"\[\s*class[^]]*\b{escaped}\b[^]]*\]", subject, flags=re.I):
            return True
    return False


def _selector_targets_poster(selector: str) -> bool:
    return _selector_targets_class(selector, "poster")


def _css_rules_for_class(css: str, class_name: str) -> list[tuple[str, str]]:
    rules = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
        selector = match.group(1).strip()
        if _selector_targets_class(selector, class_name):
            rules.append((selector, match.group(2)))
    return rules


def _poster_rules(css: str) -> list[tuple[str, str]]:
    return _css_rules_for_class(css, "poster")


def _poster_pseudo_overlay_policy(css: str) -> tuple[bool, str]:
    """Allow only the generated, non-obscuring poster texture pseudo-element."""
    base_rules = []
    flat_rules = []
    rejected = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
        selector, body = match.group(1).strip(), match.group(2)
        if re.search(r"(?<![-\w])\.ab-bg-layer(?![-\w])", selector, flags=re.I):
            # 背景层伪元素由 bg-* 专项机检把关;这里只禁止把文字塞进背景层
            for raw in _split_css_declarations(body):
                name, sep, value = raw.partition(":")
                if sep and name.strip().lower() == "content":
                    val = _css_value_base(value)
                    if val not in ('""', "none", "normal"):
                        return False, f"背景层伪元素含可见文字: {selector}"
            continue
        if not re.search(r"(?<![-\w])\.poster(?![-\w])", selector, flags=re.I):
            continue
        pseudo = re.search(r":{1,2}(before|after)\b", selector, flags=re.I)
        if not pseudo:
            continue
        normalized = re.sub(r"\s+", "", selector).lower().replace("'", '"')
        if pseudo.group(1).lower() == "before":
            rejected.append(selector)
        elif normalized == ".poster::after":
            base_rules.append(body)
        elif normalized == '.poster[data-kind="sub"][data-sub-mode="flat"]::after':
            flat_rules.append(body)
        else:
            rejected.append(selector)
    if rejected or len(base_rules) != 1 or len(flat_rules) > 1:
        return False, f"unreviewed poster pseudo rules={rejected}, base={len(base_rules)}, flat={len(flat_rules)}"

    allowed_props = {"content", "position", "inset", "pointer-events", "z-index",
                     "background-image", "background-size"}
    declarations = {}
    for raw in base_rules[0].split(";"):
        if ":" not in raw:
            continue
        name, value = raw.split(":", 1)
        declarations.setdefault(name.strip().lower(), []).append(_css_value_base(value))
    if set(declarations) - allowed_props:
        return False, f"poster::after has unreviewed properties={sorted(set(declarations) - allowed_props)}"
    required = {"content": ['""'], "position": ["absolute"], "inset": ["0"],
                "pointer-events": ["none"], "z-index": ["0"]}
    if any(declarations.get(name) != values for name, values in required.items()):
        return False, f"poster::after required declarations differ: {declarations}"
    if flat_rules:
        flat_declarations = {}
        for raw in flat_rules[0].split(";"):
            if ":" in raw:
                name, value = raw.split(":", 1)
                flat_declarations[name.strip().lower()] = _css_value_base(value)
        if flat_declarations != {"background-image": "none"}:
            return False, f"flat poster::after override differs: {flat_declarations}"
    return True, "只有固定 z-index:0 的内部纹理 ::after"


def _panel_accent_pseudo_is_safe(body: str) -> bool:
    declarations = {}
    for raw in _split_css_declarations(body):
        name, separator, value = raw.partition(":")
        if not separator:
            continue
        key = name.strip().lower()
        declarations.setdefault(key, []).append(_css_value_base(value))
    if any(len(values) != 1 for values in declarations.values()):
        return False
    values = {name: rows[0] for name, rows in declarations.items()}
    expected = {
        "content": '""', "position": "absolute", "left": "0", "top": "0",
        "bottom": "0", "width": "6px", "background": "var(--c-accent)",
    }
    alternate = dict(expected, width="5px")
    return values in (expected, alternate)


def _title_pseudo_policy(css: str, title_tags: set[str],
                         ancestor_classes: set[str],
                         ancestor_tags: set[str]) -> tuple[bool, str]:
    """Reject unreviewed pseudo overlays on a title or any containing element."""
    panel_before = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
        selector, body = match.group(1).strip(), match.group(2)
        for member in selector.split(","):
            pseudo = re.search(r":{1,2}(before|after)\b", member, flags=re.I)
            if not pseudo:
                continue
            base_selector = re.sub(r":{1,2}(?:before|after)\b", "", member, flags=re.I)
            subject = re.split(r"\s*[>+~]\s*|\s+", base_selector.strip())[-1]
            direct_title = (_selector_targets_class(subject, "t") or any(
                re.search(rf"(?<![-\w]){re.escape(tag)}(?![-\w])",
                          subject, flags=re.I) for tag in title_tags))
            if direct_title:
                return False, f"title pseudo-element is not allowed: {member.strip()}"
            selector_classes = {
                name for name in ancestor_classes
                if _selector_targets_class(subject, name)}
            selector_tags = {
                name for name in ancestor_tags
                if re.search(rf"(?<![-\w]){re.escape(name)}(?![-\w])",
                             subject, flags=re.I)}
            if selector_tags or "*" in subject:
                return False, f"generic ancestor pseudo-element is not allowed: {member.strip()}"
            normalized = re.sub(r"\s+", "", member).lower()
            if not selector_classes:
                continue
            if normalized in {".poster::after",
                              '.poster[data-kind="sub"][data-sub-mode="flat"]::after'}:
                continue  # Independently constrained by _poster_pseudo_overlay_policy.
            if normalized == ".panel::before" and selector_classes == {"panel"}:
                panel_before.append(body)
                continue
            return False, f"ancestor pseudo-element is not allowed: {member.strip()}"
    if panel_before and (len(panel_before) != 1 or
                         not _panel_accent_pseudo_is_safe(panel_before[0])):
        return False, "panel accent pseudo-element differs from the reviewed edge stripe"
    return True, "标题及祖先无未审查的伪元素遮挡"


def _title_transform_is_safe(value: str) -> bool:
    """Permit only the small intentional kraft-note title rotation."""
    normalized = _css_value_base(value)
    if not normalized:
        return True
    matches = list(re.finditer(
        r"rotate(?:z)?\(\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(deg|rad|turn)\s*\)",
        normalized, flags=re.I))
    if not matches:
        return False
    cursor = 0
    for match in matches:
        if normalized[cursor:match.start()].strip():
            return False
        cursor = match.end()
    if normalized[cursor:].strip():
        return False
    for match in matches:
        angle = float(match.group(1))
        unit = match.group(2).lower()
        degrees = angle if unit == "deg" else angle * (180 / 3.141592653589793) if unit == "rad" else angle * 360
        if not math.isfinite(degrees) or abs(degrees) > 3:
            return False
    return True


def _css_number(value: str) -> tuple[float, str] | None:
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)(%|[a-z]+)?",
        _css_value_base(value), flags=re.I)
    if not match:
        return None
    try:
        number = float(match.group(1))
    except ValueError:
        return None
    return (number, (match.group(2) or "").lower()) if math.isfinite(number) else None


def _opacity_fraction(value: str) -> float | None:
    parsed = _css_number(value)
    if parsed is None:
        return None
    number, unit = parsed
    return number / 100 if unit == "%" else number if not unit else None


def _color_alpha(value: str) -> float | None:
    normalized = _css_value_base(value)
    if normalized == "transparent":
        return 0.0
    if normalized.startswith("#"):
        digits = normalized[1:]
        if len(digits) == 4:
            try:
                return int(digits[-1] * 2, 16) / 255
            except ValueError:
                return None
        if len(digits) == 8:
            try:
                return int(digits[-2:], 16) / 255
            except ValueError:
                return None
    if "(" not in normalized or ")" not in normalized:
        return None
    content = normalized[normalized.find("(") + 1:normalized.rfind(")")]
    if "/" in content:
        alpha = content.rsplit("/", 1)[1].strip()
    else:
        pieces = [part.strip() for part in content.split(",")]
        if len(pieces) < 4:
            return None
        alpha = pieces[-1]
    parsed = _css_number(alpha)
    if parsed is None:
        return None
    number, unit = parsed
    return number / 100 if unit == "%" else number if not unit else None


def _font_size_below_one_px(value: str) -> bool:
    parsed = _css_number(value)
    if parsed is None:
        return False
    number, unit = parsed
    factors = {"": 1.0, "px": 1.0, "pt": 4 / 3, "pc": 16.0,
               "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4,
               "q": 96 / 101.6, "em": 16.0, "rem": 16.0, "%": 0.16}
    factor = factors.get(unit)
    return factor is not None and abs(number * factor) < 1.0


def _filter_hides_title(value: str) -> bool:
    for match in re.finditer(r"opacity\(\s*([^)]*)\)", value, flags=re.I):
        alpha = _opacity_fraction(match.group(1))
        if alpha is not None and alpha <= 0.01:
            return True
    return False


def _css_custom_property_values(css: str, blocks: list[str]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    bodies = [match.group(2) for match in re.finditer(
        r"([^{}]+)\{([^{}]*)\}", css, flags=re.S)] + blocks
    for body in bodies:
        for declaration in _split_css_declarations(body):
            name, separator, value = declaration.partition(":")
            key = name.strip().lower()
            if separator and re.fullmatch(r"--[\w-]+", key):
                values.setdefault(key, []).append(value.strip())
    return {key: list(dict.fromkeys(items)) for key, items in values.items()}


def _resolve_title_css_variables(value: str, variables: dict[str, list[str]]) -> str | None:
    resolved = value.strip()
    for _ in range(16):
        match = re.search(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)", resolved, flags=re.I)
        if not match:
            return None if re.search(r"var\s*\(", resolved, flags=re.I) else resolved
        candidates = variables.get(match.group(1).lower(), [])
        if len(candidates) == 1:
            replacement = candidates[0]
        elif not candidates and match.group(2) is not None:
            replacement = match.group(2).strip()
        else:
            return None
        resolved = resolved[:match.start()] + replacement + resolved[match.end():]
    return None


def _title_visibility_policy(css: str, inline_styles: list[str], ancestor_inline_styles: list[str],
                             title_tags: set[str], ancestor_classes: set[str],
                             ancestor_tags: set[str]) -> tuple[bool, str]:
    """Reject CSS rules that hide, shrink, or move the title or its ancestors."""
    if not title_tags:
        return False, "未识别封面标题节点"
    style_blocks: list[tuple[str, bool]] = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
        selector, body = match.group(1).strip(), match.group(2)
        direct = False
        ancestor = False
        for member in selector.split(","):
            if re.search(r"::[\w-]+", member):
                continue
            subject = re.split(r"\s*[>+~]\s*|\s+", member.strip())[-1]
            if (_selector_targets_class(subject, "t")
                    or any(re.search(rf"(?<![-\w]){re.escape(tag)}(?![-\w])",
                                     subject, flags=re.I) for tag in title_tags)):
                direct = True
                break
            if (any(_selector_targets_class(subject, name) for name in ancestor_classes)
                    or any(re.search(rf"(?<![-\w]){re.escape(tag)}(?![-\w])",
                                     subject, flags=re.I) for tag in ancestor_tags)
                    or "*" in subject):
                ancestor = True
        if direct:
            style_blocks.append((body, False))
        elif ancestor:
            style_blocks.append((body, True))
    style_blocks.extend((block, False) for block in inline_styles)
    style_blocks.extend((block, True) for block in ancestor_inline_styles)
    variable_blocks = [block for block, _is_ancestor in style_blocks]
    variables = _css_custom_property_values(css, variable_blocks)
    hidden = []
    ancestor_safe_props = {"display", "visibility", "opacity", "content-visibility", "font-size",
                           "color", "-webkit-text-fill-color", "text-indent", "clip", "clip-path",
                           "mask", "mask-image", "filter", "width", "height", "position"}
    direct_safe_props = ("display", "visibility", "opacity", "content-visibility", "font-size",
                         "color", "-webkit-text-fill-color", "text-indent", "clip", "clip-path",
                         "mask", "mask-image", "filter", "position", "left", "right", "top",
                         "bottom", "inset", "translate", "scale", "zoom", "width", "height")
    for block, is_ancestor in style_blocks:
        properties = ancestor_safe_props if is_ancestor else direct_safe_props
        for prop in properties:
            for value in _css_values(block, prop):
                resolved = _resolve_title_css_variables(value, variables)
                if resolved is None:
                    hidden.append(f"{prop}:unresolved {value.strip()}")
                    continue
                normalized = _css_value_base(resolved)
                alpha = _opacity_fraction(normalized)
                color_alpha = _color_alpha(normalized) if prop in {
                    "color", "-webkit-text-fill-color"} else None
                bad = ((prop == "display" and normalized == "none")
                       or (prop == "visibility" and normalized in {"hidden", "collapse"})
                       or (prop == "opacity" and alpha is not None and alpha <= 0.01)
                       or (prop == "content-visibility" and normalized == "hidden")
                       or (prop == "font-size" and _font_size_below_one_px(normalized))
                       or (prop in {"width", "height"} and normalized in {"0", "0px"})
                       or (prop in {"color", "-webkit-text-fill-color"}
                           and color_alpha is not None and color_alpha <= 0.01)
                       or (prop == "text-indent" and _px(normalized) is not None
                           and abs(_px(normalized)) > 1000)
                       or (prop == "clip" and normalized not in {"auto", "unset"})
                       or (prop == "clip-path" and normalized not in {"none", "unset"})
                       or (prop in {"mask", "mask-image"} and normalized != "none")
                       or (prop == "filter" and normalized != "none")
                       or (prop == "filter" and _filter_hides_title(normalized))
                       or (prop == "position" and normalized in {"fixed", "sticky"})
                       or (prop in {"left", "right", "top", "bottom", "inset", "translate", "scale", "zoom"}
                           and normalized not in {"0", "0px", "none", "unset"}))
                if bad:
                    hidden.append(f"{prop}:{value.strip()}")
        if not is_ancestor:
            for value in _css_values(block, "transform"):
                resolved = _resolve_title_css_variables(value, variables)
                if resolved is None or not _title_transform_is_safe(resolved):
                    hidden.append(f"transform:{value.strip()}")
    return not hidden, ("标题及祖先规则未声明隐藏/移出属性" if not hidden
                        else f"标题及祖先含隐藏/移出声明={hidden[:6]}")


def _css_value_base(value: str) -> str:
    return re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.I).lower()


def _poster_visibility_policy(css: str) -> tuple[bool, str]:
    """Reject root styles that reset, hide, or move the exported canvas."""
    values = {name: [_css_value_base(value) for value in _css_values(css, name)]
              for name in (
                  "all", "display", "position", "visibility", "opacity",
                  "left", "right", "top", "bottom", "inset", "inset-inline",
                  "inset-block", "inset-block-start", "inset-block-end",
                   "inset-inline-start", "inset-inline-end", "margin", "margin-left", "margin-right",
                  "margin-top", "margin-bottom", "transform", "translate", "rotate", "scale", "zoom",
                  "clip", "clip-path", "filter", "mask", "mask-image", "mask-border",
                   "backdrop-filter", "content-visibility",
              )}
    if values["all"]:
        return False, "all reset"
    if any(value not in {"block", "flex", "grid", "inline-block", "inline-flex",
                         "inline-grid", "flow-root"} for value in values["display"]):
        return False, f"display={values['display']}"
    if not values["position"] or any(value != "relative" for value in values["position"]):
        return False, f"position={values['position']}"
    if any(value != "visible" for value in values["visibility"]):
        return False, f"visibility={values['visibility']}"
    if any(value not in {"1", "1.0", "1.00", "100%"} for value in values["opacity"]):
        return False, f"opacity={values['opacity']}"
    zero_or_auto = {"0", "0px", "0%", "auto"}
    for name in ("left", "right", "top", "bottom", "inset", "inset-inline", "inset-block",
                 "inset-block-start", "inset-block-end", "inset-inline-start", "inset-inline-end",
                 "margin", "margin-left", "margin-right", "margin-top", "margin-bottom"):
        if any(value not in zero_or_auto for value in values[name]):
            return False, f"{name}={values[name]}"
    for name in ("transform", "scale", "zoom"):
        if any(value not in {"none", "1", "1.0", "1 1", "1.0 1.0"}
               for value in values[name]):
            return False, f"{name}={values[name]}"
    if any(value not in {"none", "0", "0px", "0 0", "0px 0px", "0deg"}
           for value in values["translate"] + values["rotate"]):
        return False, f"translate/rotate={values['translate'] + values['rotate']}"
    if any(value not in {"auto", "none"}
           for name in ("clip", "clip-path", "filter", "mask", "mask-image",
                        "mask-border", "backdrop-filter") for value in values[name]):
        return False, "clip/filter/mask override"
    if any(value != "visible" for value in values["content-visibility"]):
        return False, f"content-visibility={values['content-visibility']}"
    return True, "visible, positioned, and box-preserving"


def _selector_targets_page_root(selector: str) -> bool:
    for member in selector.split(","):
        member = member.strip()
        if member == "*" or re.search(
                r"(?:^|[\s>+~,(])(?:html|body|:root)(?=$|[\s.#:\[>+~)])",
                member, flags=re.I):
            return True
    return False


def _page_root_visibility_policy(css: str, inline_styles: list[str]) -> tuple[bool, str]:
    """Fail closed when html/body/root selectors can hide, move, or overlay the poster."""
    for selector, _body in re.findall(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
        if (_selector_targets_page_root(selector)
                and re.search(r":{1,2}(?:before|after)\b", selector, flags=re.I)):
            return False, f"page-root pseudo overlay is not allowed: {selector.strip()}"
    blocks = [body for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S)
              if _selector_targets_page_root(selector)]
    blocks.extend(inline_styles)
    root_css = "\n".join(blocks)
    root_props = (
        "all", "display", "position", "visibility", "opacity", "left", "right",
        "top", "bottom", "inset", "inset-inline", "inset-block", "inset-inline-start",
        "inset-inline-end", "inset-block-start", "inset-block-end", "margin", "margin-top",
        "margin-right", "margin-bottom", "margin-left", "margin-block", "margin-block-start",
        "margin-block-end", "margin-inline", "margin-inline-start", "margin-inline-end",
        "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
        "padding-block", "padding-block-start", "padding-block-end", "padding-inline",
        "padding-inline-start", "padding-inline-end", "border", "border-width", "border-top",
        "border-right", "border-bottom", "border-left", "transform", "translate", "rotate",
        "scale", "zoom", "clip", "clip-path", "filter", "mask", "mask-image", "mask-border",
        "backdrop-filter", "content-visibility",
        "width", "min-width", "max-width", "height", "min-height", "max-height",
        "overflow", "overflow-x", "overflow-y",
    )
    values = {name: [_css_value_base(value) for value in _css_values(root_css, name)]
              for name in root_props}
    if values["all"]:
        return False, "page root all reset"
    if any(value not in {"block", "flow-root", "flex", "grid", "inline-block",
                         "inline-flex", "inline-grid"} for value in values["display"]):
        return False, f"page root display={values['display']}"
    if any(value not in {"static", "relative"} for value in values["position"]):
        return False, f"page root position={values['position']}"
    if any(value != "visible" for value in values["visibility"]):
        return False, f"page root visibility={values['visibility']}"
    if any(value not in {"1", "1.0", "1.00", "100%"} for value in values["opacity"]):
        return False, f"page root opacity={values['opacity']}"
    root_size_props = ("width", "min-width", "max-width", "height", "min-height", "max-height")
    if any(value not in {"auto", "none"}
           for name in root_size_props for value in values[name]):
        return False, "page root dimensions can shrink or clip the poster"
    if any(value != "visible" for name in ("overflow", "overflow-x", "overflow-y")
           for value in values[name]):
        return False, "page root overflow can clip the poster"
    root_distance_props = (
        "left", "right", "top", "bottom", "inset", "inset-inline", "inset-block",
        "inset-inline-start", "inset-inline-end", "inset-block-start", "inset-block-end",
        "margin", "margin-top", "margin-right",
        "margin-bottom", "margin-left", "margin-block", "margin-block-start", "margin-block-end",
        "margin-inline", "margin-inline-start", "margin-inline-end", "padding", "padding-top",
        "padding-right", "padding-bottom", "padding-left", "padding-block", "padding-block-start",
        "padding-block-end", "padding-inline", "padding-inline-start", "padding-inline-end",
        "border", "border-width", "border-top", "border-right", "border-bottom", "border-left",
    )
    if any(value not in {"0", "0px", "0%", "auto", "none"}
           for name in root_distance_props for value in values[name]):
        return False, "page root positioned outside layout"
    if any(value not in {"none", "1", "1.0", "0", "0px", "0deg"}
           for name in ("transform", "translate", "rotate", "scale", "zoom")
           for value in values[name]):
        return False, "page root transform override"
    if any(value not in {"auto", "none"}
           for name in ("clip", "clip-path", "filter", "mask", "mask-image",
                        "mask-border", "backdrop-filter") for value in values[name]):
        return False, "page root clip/filter/mask override"
    if any(value != "visible" for value in values["content-visibility"]):
        return False, f"page root content-visibility={values['content-visibility']}"
    return True, "page root remains visible and untransformed"


def _body_content_policy(children: list[dict], text_nodes: list[str]) -> tuple[bool, str]:
    """Body may contain only the poster and its already-audited runtime scripts."""
    posters = [child for child in children if "poster" in child.get("classes", ())]
    extras = [child for child in children if "poster" not in child.get("classes", ())]
    if len(posters) != 1:
        return False, f"expected one direct body poster, found {len(posters)}"
    if text_nodes:
        return False, "unreviewed direct text exists in body"
    if any(child.get("tag") != "script" for child in extras):
        return False, f"unreviewed body siblings can cover or alter poster: {extras[:3]}"
    return True, "body has only the poster and audited script siblings"


def _poster_parent_policy(parent_chains: list[tuple[str, ...]]) -> tuple[bool, str]:
    """Generated canvases must be direct children of body, with no hideable wrappers."""
    allowed = {("html", "body"), ("body",)}
    if len(parent_chains) != 1:
        return False, f"expected one poster element, found {len(parent_chains)}"
    chain = parent_chains[0]
    if chain not in allowed:
        return False, f"unreviewed poster ancestor chain: {'/'.join(chain)}"
    return True, "poster is a direct child of body"


def _px(v: str):
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)px\s*", v or "")
    return float(m.group(1)) if m else None


def _safe_inner(html: str) -> str:
    """Return the complete .safe div body, respecting nested divs."""
    root = re.search(r'<div class="safe"[^>]*>', html, re.I)
    if not root:
        return ""
    depth = 1
    for tag in re.finditer(r"</?div\b[^>]*>", html[root.end():], re.I):
        closing = tag.group(0).startswith("</")
        depth += -1 if closing else 1
        if depth == 0:
            return html[root.end():root.end() + tag.start()]
    return ""


def _parse_safe_box(html: str, canvas_w: int) -> tuple[float, float, str]:
    """从 .safe 的 CSS 规则推出安全区的 x 区间(左闭右开)。

    解释本工具产出的几种写法:left/right/width + translateX(-50%)(水平居中)/
    left:0 + right:0(撑满)。解析不出返回 (0, canvas_w, 'unparsed'),由断言判失。
    """
    css = "\n".join(body for _selector, body in
                     _css_rules_for_class(_html_audit(html).css_text(), "safe"))
    if not css:
        return 0, canvas_w, "no .safe rule"
    left_raw = _css_prop(css, "left").strip()
    left, right = _px(left_raw), _px(_css_prop(css, "right"))
    width = _px(_css_prop(css, "width"))
    tr = re.sub(r"\s+", "", _css_prop(css, "transform"))
    center_transform = tr.lower() == "translatex(-50%)"
    centered_anchor = bool(re.fullmatch(r"50(?:\.0+)?%", left_raw))
    if tr and tr.lower() != "none" and not (center_transform and centered_anchor):
        return 0, canvas_w, "unparsed unsafe transform/anchor"
    centered = center_transform and centered_anchor
    try:
        cx = canvas_w / 2 + (left or 0.0)
        if centered and width is not None:
            return cx - width / 2, cx + width / 2, "left:50% + translateX(-50%) + width"
        if left is not None and width is not None:
            if left == 0 and right == 0:
                return 0, canvas_w, "left:0 + right:0(撑满)"
            return left, left + width, "left + width"
        if width is not None:               # 只用 right 定位(width + right)
            if right is not None:
                return canvas_w - right - width, canvas_w - right, "right + width"
            return cx - width / 2, cx + width / 2, "仅 width(默认贴左,居中排)"
        if left is not None and right is not None:
            return left, canvas_w - right, "left + right"
        if left is None and right is None and width is None:
            return 0, canvas_w, "full-bleed(default)"
    except (TypeError, ValueError):
        pass
    return 0, canvas_w, "unparsed"


def _parse_safe_y_box(html: str, canvas_h: int) -> tuple[float, float, str]:
    """推导 .safe 的 top/bottom 区间;无法从明确像素锚点解析时返回无效标记。"""
    css = "\n".join(body for _selector, body in
                     _css_rules_for_class(_html_audit(html).css_text(), "safe"))
    if not css:
        return 0, canvas_h, "no .safe rule"
    top, bottom = _px(_css_prop(css, "top")), _px(_css_prop(css, "bottom"))
    height = _px(_css_prop(css, "height"))
    if top is not None and bottom is not None:
        return top, canvas_h - bottom, "top + bottom"
    if top is not None and height is not None:
        return top, top + height, "top + height"
    if bottom is not None and height is not None:
        return canvas_h - bottom - height, canvas_h - bottom, "bottom + height"
    return 0, canvas_h, "unparsed vertical anchors"


def check_one(html_path: str, canvas_w: int, layout: str,
              project_fx: str | None = None) -> list[dict]:
    """对单张封面做静态断言。返回 [{id, ok, detail}]。"""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    canvas_h = MAIN_H if canvas_w == MAIN_W else SUB_H
    res = []

    def add(cid, ok, detail):
        res.append({"id": cid, "ok": bool(ok), "detail": detail})

    def skip(cid, detail):
        res.append({"id": cid, "ok": True, "skipped": True, "detail": detail})

    html_audit = _html_audit(html)
    has_shader = html_audit.shader_canvas
    has_webgpu_marker = html_audit.webgpu_marker
    marker_matches = has_shader == has_webgpu_marker
    project_matches = _project_canvas_fx_matches(
        project_fx, html_audit.shader_canvas_fx)
    add("webgpu-required-marker", marker_matches and project_matches,
        f"HTML shader canvas={has_shader},WebGPU标记={has_webgpu_marker},"
        f"canvas fx={html_audit.shader_canvas_fx},项目fx={project_fx!r}")
    shader_scripts = set(html_audit.script_sources)
    runtime_scripts_present = (not has_shader or {
        "vendor/shaders/upstream.js", "vendor/shaders/runtime.js"}.issubset(shader_scripts))
    add("shader-runtime-scripts-present", runtime_scripts_present,
        "shader canvas 有 upstream/runtime 启动脚本" if runtime_scripts_present
        else "shader canvas 必须引用 vendor/shaders/upstream.js 与 runtime.js")

    # 1 固定画布的有效规则必须唯一,避免后续 CSS/inline cascade 覆盖固定几何与裁切。
    css_text = html_audit.css_text()
    poster_rules = _poster_rules(css_text)
    poster_css = "\\n".join(body for _selector, body in poster_rules)
    width_values = _css_values(poster_css, "width")
    height_values = _css_values(poster_css, "height")
    overflow_values = _css_values(poster_css, "overflow")
    overflow_x = _css_values(poster_css, "overflow-x")
    overflow_y = _css_values(poster_css, "overflow-y")
    size_constraints = {
        prop: _css_values(poster_css, prop)
        for prop in ("min-width", "max-width", "min-height", "max-height",
                     "inline-size", "block-size", "min-inline-size", "max-inline-size",
                     "min-block-size", "max-block-size")
    }
    box_sizing = _css_values(poster_css, "box-sizing")
    box_model_props = (
        "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
        "padding-inline", "padding-inline-start", "padding-inline-end",
        "padding-block", "padding-block-start", "padding-block-end",
        "border", "border-width", "border-top-width", "border-right-width",
        "border-bottom-width", "border-left-width", "border-inline-width",
        "border-block-width",
    )
    box_model_values = {prop: _css_values(poster_css, prop) for prop in box_model_props}
    zero_box_values = {"0", "0px", "none"}
    safe_box_model = (box_sizing == ["border-box"] and all(
        value.lower() in zero_box_values
        for values in box_model_values.values() for value in values))
    visual_transforms = {
        prop: _css_values(poster_css, prop)
        for prop in ("transform", "scale", "zoom")
    }
    has_size_constraints = any(size_constraints.values())
    has_visual_transforms = any(visual_transforms.values())
    poster_visibility_ok, poster_visibility_detail = _poster_visibility_policy(poster_css)
    poster_pseudo_ok, poster_pseudo_detail = _poster_pseudo_overlay_policy(css_text)
    title_visible, title_detail = _title_visibility_policy(
        css_text, html_audit.title_inline_styles, html_audit.title_ancestor_inline_styles,
        html_audit.title_tags, html_audit.title_ancestor_classes,
        html_audit.title_ancestor_tags)
    title_pseudo_ok, title_pseudo_detail = _title_pseudo_policy(
        css_text, html_audit.title_tags, html_audit.title_ancestor_classes,
        html_audit.title_ancestor_tags)
    title_visible = title_visible and title_pseudo_ok
    if not title_pseudo_ok:
        title_detail = f"{title_detail}; {title_pseudo_detail}"
    page_root_visible, page_root_detail = _page_root_visibility_policy(
        css_text, html_audit.page_root_inline_styles)
    poster_parent_ok, poster_parent_detail = _poster_parent_policy(
        html_audit.poster_parent_chains)
    body_content_ok, body_content_detail = _body_content_policy(
        html_audit.body_child_elements, html_audit.body_child_text)
    media_violations = _static_image_violations(html_path, html_audit)
    nested_css_rules = _has_nested_css_blocks(css_text)
    add("no-css-nesting", not nested_css_rules,
        "未出现 CSS nesting/歧义块" if not nested_css_rules
        else "静态封面检查不接受嵌套 CSS 规则")
    css_animation = bool(re.search(
        r"@(?:-webkit-)?keyframes\b|(?:^|[;{])\s*(?:-webkit-)?animation(?:-[\w-]+)?\s*:",
        css_text, flags=re.I))
    add("poster-static-no-animation", not css_animation,
        "未声明 CSS animation/keyframes" if not css_animation
        else "静态封面不允许 CSS animation 或 keyframes")
    unique_geometry = (not nested_css_rules and not css_animation
                       and len(width_values) == 1 and len(height_values) == 1
                       and len(overflow_values) == 1
                       and safe_box_model and not has_size_constraints
                       and not has_visual_transforms and poster_visibility_ok)
    poster_rule_controlled = (bool(poster_rules) and not html_audit.poster_inline_styles
                              and unique_geometry and poster_pseudo_ok and poster_parent_ok
                              and body_content_ok)
    poster_w = _px(width_values[0]) if len(width_values) == 1 else None
    poster_h = _px(height_values[0]) if len(height_values) == 1 else None
    dimensions_ok = poster_w == canvas_w and poster_h == canvas_h
    overflow_ok = (overflow_values == ["hidden"]
                   and all(value == "hidden" for value in overflow_x + overflow_y))
    add("poster-cascade-controlled", poster_rule_controlled,
        f".poster 匹配规则数={len(poster_rules)},geometry declarations={len(width_values)}/{len(height_values)}/{len(overflow_values)},size constraints={sum(map(len, size_constraints.values()))},box-sizing={box_sizing},box-model-values={sum(map(len, box_model_values.values()))},transforms={sum(map(len, visual_transforms.values()))},inline-style={len(html_audit.poster_inline_styles)},visibility={poster_visibility_detail}")
    add("poster-parent-chain", poster_parent_ok, poster_parent_detail)
    add("body-content-controlled", body_content_ok, body_content_detail)
    add("poster-visible-in-canvas", poster_visibility_ok and page_root_visible
        and poster_parent_ok and body_content_ok,
        f"poster: {poster_visibility_detail}; ancestors: {page_root_detail}; wrapper: {poster_parent_detail}; body: {body_content_detail}")
    add("poster-pseudo-overlay-controlled", poster_pseudo_ok, poster_pseudo_detail)
    add("title-pseudo-controlled", title_pseudo_ok, title_pseudo_detail)
    add("title-visible", title_visible, title_detail)
    add("page-root-visible", page_root_visible, page_root_detail)
    add("static-media-only", not html_audit.media_elements,
        f"媒体/原生动画元素={html_audit.media_elements}" if html_audit.media_elements
        else "无 video/audio/marquee")
    add("static-image-resources", not media_violations,
        f"图像资源可静态解码且非动画" if not media_violations else f"动态/不安全图像={media_violations[:4]}")
    font_violations = _font_resource_violations(
        html_path, html_audit.css_font_resource_urls())
    add("font-face-resources-exist", not font_violations,
        "@font-face 本地 URL 均存在且可读" if not font_violations
        else f"@font-face 资源缺失/不可读={font_violations[:4]}")
    all_resets = _css_values(css_text, "all")
    add("no-css-all-reset", not all_resets,
        "未出现 CSS all reset" if not all_resets else f"出现 CSS all reset: {all_resets[:3]}")
    add("canvas-fixed", poster_rule_controlled and dimensions_ok and overflow_ok,
        f".poster 声明 {poster_w or '?'}×{poster_h or '?'}px,要求精确 {canvas_w}×{canvas_h}px 且有效 overflow:hidden")

    # 2 无 viewport 单位 / 无 fixed 定位(铁律 2);以 HTML/CSS 语法而非空格和大小写格式判断。
    bad_units = re.findall(
        r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?\s*"
        r"(?:v(?:w|h|min|max|i|b)|(?:sv|lv|dv)(?:w|h|min|max|i|b))\b",
        css_text, flags=re.I)
    add("no-viewport-units", not bad_units,
        "未出现 viewport-relative units" if not bad_units else f"出现 viewport 单位: {set(bad_units)}")
    has_fixed = re.search(r"\bposition\s*:\s*fixed\b", css_text, flags=re.I)
    add("no-fixed-position", not has_fixed, "未出现 position:fixed")

    # 3 版式族有标记(新族必须带;旧版无标记 → 记为 legacy 跳过)
    m = re.search(r'data-layout="([^"]+)"', html)
    if m:
        add("layout-tag", m.group(1) == layout, f"data-layout={m.group(1)}")
    else:
        add("layout-tag", layout == "legacy",
            "legacy 模板(无 data-layout)" if layout == "legacy" else "新版式缺少 data-layout")

    def css_rule(selector):
        # Join every selector block in source order so _css_prop sees the
        # effective last declaration rather than an obsolete first rule.
        return "\n".join(body for _name, body in _css_rules_for_class(css_text, selector))

    def numeric_rule(selector, prop):
        return _px(_css_prop(css_rule(selector), prop))

    structural_selectors = {
        "center-band": ("band", "safe"),
        "band-editorial": ("panel", "safe"),
        "stack-cards": ("card", "band", "safe"),
        "giant-caps": ("safe",),
        "kraft-note": ("safe",),
        "plate-page": ("plate", "safe"),
    }.get(layout, ())
    cascade_controls = {
        name: (len(rules := _css_rules_for_class(css_text, name)) == 1
               and rules[0][0].strip().lower() == f".{name}")
        for name in structural_selectors
    }
    cascade_ok = all(cascade_controls.values()) if cascade_controls else True
    add("layout-selector-cascade-controlled", cascade_ok,
        f"结构选择器规则={cascade_controls}")

    if layout == "center-band":
        band = css_rule("band")
        band_size = (numeric_rule("band", "width"), numeric_rule("band", "height"))
        if canvas_w == MAIN_W:
            # 色带随主标字宽生长:v1.26 允许 383→720(标题越界授权),高度与位置不变
            band_w_val = band_size[0] or 0
            geometry_ok = (383 <= band_w_val <= 720 and band_size[1] == 232
                           and numeric_rule("band", "top") == 96
                           and _css_prop(band, "left") == "50%"
                           and "translateX(-50%)" in re.sub(r"\s+", "", _css_prop(band, "transform")))
            expected_band = "居中 383–720×232px,y=96(色带随字宽生长)"
        else:
            geometry_ok = (band_size == (349, 349) and _css_prop(band, "top") == "50%"
                           and "translate(-50%,-50%)" in re.sub(r"\s+", "", _css_prop(band, "transform")))
            expected_band = "居中 349×349px"
        add("center-band-geometry", geometry_ok,
            f"主/次条中央色带 {band_size},要求{expected_band}")
    elif layout == "band-editorial" and canvas_w == MAIN_W:
        panel = css_rule("panel")
        panel_ok = (numeric_rule("panel", "left") == 0 and numeric_rule("panel", "width") == 642
                    and numeric_rule("panel", "top") == 0 and numeric_rule("panel", "bottom") == 0)
        add("band-editorial-geometry", panel_ok,
            f"主封左文带 left={_css_prop(panel, 'left')},width={_css_prop(panel, 'width')};要求 x=0..642 全高")
    elif layout == "stack-cards":
        card, band = css_rule("card"), css_rule("band")
        expected = ((258, 48, 384, 287, 336, 80) if canvas_w == MAIN_W
                    else (28, 28, 327, 327, 283, 45))
        card_ok = (numeric_rule("card", "left"), numeric_rule("card", "top"),
                   numeric_rule("card", "width"), numeric_rule("card", "height")) == expected[:4]
        band_ok = (numeric_rule("band", "width") == expected[4]
                   and numeric_rule("band", "top") == expected[5]
                   and _css_prop(band, "bottom") == "")
        add("stack-cards-geometry", card_ok and band_ok,
            f"卡片/内色条尺寸符合主/次条规格,非画布页脚条(card={card_ok},band={band_ok})")
    elif layout == "plate-page":
        plate = css_rule("plate")
        plate_ok = ((numeric_rule("plate", "left"), numeric_rule("plate", "width")) ==
                    ((672, 228) if canvas_w == MAIN_W else (260, 123)))
        image_match = re.search(r'<img\b[^>]*class="plate-image"[^>]*src="([^"]+)"', html, re.I)
        image_ok = False
        if image_match:
            image_ref = html_lib.unescape(image_match.group(1))
            if (re.fullmatch(r"images/plate-page-image\.(?:png|jpg|webp)", image_ref)
                    and ".." not in image_ref.split("/")):
                image_path = os.path.join(os.path.dirname(html_path), *image_ref.split("/"))
                image_spec, image_error = _local_raster_spec(image_path)
                image_ok = not image_error and image_spec["filename"] == os.path.basename(image_ref)
        add("plate-page-photo", plate_ok and image_ok,
            f"出血照片窗几何有效={plate_ok},本地 PNG/JPEG/WebP={image_ok}")
    else:
        skip("layout-structure", "无此族专属静态几何断言")

    # 4–5 新族使用 .safe/data-role 做精确几何断言。旧版模板没有这些锚点，
    #    不把“无法解析”误报成溢出；其覆盖范围在 check 结果中标为 partial。
    x0, x1, how = _parse_safe_box(html, canvas_w)
    if layout == "legacy":
        skip("safe-zone-inside" if canvas_w == MAIN_W else "safe-margin-small",
             "legacy 模板未声明新族几何锚点,本项未测量")
        skip("safe-zone-vertical-inside", "legacy 模板未声明 .safe 垂直锚点,本项未测量")
        skip("info-inside-safe", "legacy 模板没有 data-role=info,本项未测量")
    else:
        if canvas_w == MAIN_W:
            # v1.26 起主标授权越过中央语义区(258–642):参考样本 18/18 的大字主标
            # 都横跨色带。授权上限 90–810(两侧各留 90px 呼吸),但越过语义区必须由
            # title-overreach 证明「核心字仍在语义区内可读」,不是无条件放开。
            in_band = 258 <= x0 and x1 <= 642
            authorized = x0 >= 90 and x1 <= 810
            add("safe-zone-inside", authorized,
                f"语义区 x∈[{x0:g},{x1:g}] 依据 {how}"
                + ("(在 258–642 内)" if in_band
                   else "(越过语义区,授权区间 90–810,由 title-overreach 校验可读性)"))
        else:
            margin = canvas_w * 0.08
            add("safe-margin-small", margin <= x0 and x1 <= canvas_w - margin,
                f"安全区 x∈[{x0:g},{x1:g}],要求 ≥{margin:g} 且 ≤{canvas_w - margin:g}")
        y0, y1, yhow = _parse_safe_y_box(html, canvas_h)
        v_margin = 20
        add("safe-zone-vertical-inside",
            y0 >= v_margin and y1 <= canvas_h - v_margin and y0 < y1,
            f"安全区 y∈[{y0:g},{y1:g}] 依据 {yhow},要求 ≥{v_margin} 且 ≤{canvas_h - v_margin}")

        # 信息件都在 .safe 内(data-role=info 只出现在 safe 块中)
        safe_inner = _safe_inner(html)
        info_total = len(re.findall(r'data-role="info"', html))
        info_in_safe = len(re.findall(r'data-role="info"', safe_inner)) if safe_inner else -1
        add("info-inside-safe", info_in_safe == info_total,
            f"信息件 {info_total} 个,安全区内 {max(info_in_safe, 0)} 个" if safe_inner
            else f"信息件 {info_total} 个,安全区块未识别")

    # 6 层级 ≤3(防固):元素类名不算层级,这里只查有没有出现 4 层以上 z-index
    zs = sorted({int(x) for x in re.findall(r"z-index:\s*(\d+)", html)})
    add("layer-count", len(zs) <= 3, f"z-index 取值 {zs}(≤3 种)")

    # 7 Offline resources and executable code must resolve to a reviewed local root.
    ext = html_audit.external_urls + html_audit.css_external_urls()
    resource_urls = html_audit.resource_urls + html_audit.css_resource_urls()
    bad_local_resources = _local_resource_violations(html_path, resource_urls)
    bad_script_sources = _untrusted_script_sources(html_path, html_audit)
    code_violations = html_audit.unreviewed_code + bad_script_sources
    add("shader-scripts-resolve-to-vendor-root", not bad_script_sources,
        "脚本解析到当前页面的 vendor/shaders 树" if not bad_script_sources else
        f"未审计脚本路径 {bad_script_sources[:3]}")
    add("resources-confined-to-src-or-skill-assets", not bad_local_resources,
        "文件资源位于 src/ 或明确许可的 Skill 资产根" if not bad_local_resources else
        f"文件资源越过允许根 {bad_local_resources[:3]}")
    add("no-unreviewed-executable-code", not code_violations,
        "未发现未审计脚本/事件属性/base" if not code_violations else
        f"未审计可执行内容 {code_violations[:3]}")
    offline_ok = not ext and not code_violations and not bad_local_resources
    add("offline-only", offline_ok,
        "无外部链接、越界文件引用或未审计代码" if offline_ok
        else f"发现外部引用/代码 { (ext + code_violations + bad_local_resources)[:3]}")
    unreviewed_css = html_audit.has_unreviewed_stylesheets()
    add("inline-css-only", not unreviewed_css,
        "CSS 全部内联且无 @import" if not unreviewed_css else
        "拒绝未审计的 <link rel=stylesheet> 或 CSS @import")

    # 8 字体 ≤2 款(v1.26:超过 2 款在 383 高的画布上就是噪音)
    fams = set(re.findall(r"--font-(?:display|sans):\s*'([^']+)'", html))
    add("font-count", len(fams) <= 2, f"字体族 {sorted(fams)}(≤2 款)")

    # 8b 文案预算:全图中文可见字符 ≤28(手机一屏能读进来的上限);
    #    附属信息层(眉题/副题/落款等 data-role=info)≤3 层,取代旧的"元素 5–8 件"。
    body_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    body_text = re.sub(r"<[^>]+>", " ", body_text)
    body_text = html_lib.unescape(body_text)
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", body_text))
    add("title-budget", cjk <= 28, f"全图中文 {cjk} 字(≤28)")
    layers = max(0, len(re.findall(r'data-role="info"', html)) - 1)
    add("info-layers", layers <= 3, f"附属信息层 {layers} 层(≤3)")

    # 8d 外层背景层(v1.26 W6):一个可选 div,必须离线、无字、不抢信息层。
    bg_tags = re.findall(r'<div[^>]*class="ab-bg-layer"[^>]*>', html)
    bg_recipe = ""
    if bg_tags:
        bg_recipe_match = re.search(r'data-bg-recipe="([^"]*)"', bg_tags[0])
        bg_recipe = bg_recipe_match.group(1) if bg_recipe_match else ""
    add("bg-recipe-known", not bg_tags or bg_recipe in _GL.BG_RECIPE_SLUGS,
        f"背景配方={bg_recipe!r}(白名单 {len(_GL.BG_RECIPE_SLUGS)} 个)" if bg_tags
        else "未使用外层背景层")
    bg_bodies = []
    for bg_match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_text, flags=re.S):
        if re.search(r"(?<![-\w])\.ab-bg-layer(?![-\w])", bg_match.group(1), flags=re.I):
            bg_bodies.append(bg_match.group(2))
    bg_segment = "\n".join(bg_bodies)
    bg_image_decls = len(re.findall(r"(?:^|;)\s*background-image\s*:", bg_segment))
    add("bg-layer-budget", len(bg_tags) <= 1 and bg_image_decls <= 2,
        f"背景层 {len(bg_tags)} 个(≤1),background-image 声明 {bg_image_decls} 条(≤2)")
    bg_inner = ""
    if bg_tags:
        inner_match = re.search(r'<div[^>]*class="ab-bg-layer"[^>]*>(.*?)</div>', html, re.S)
        bg_inner = inner_match.group(1) if inner_match else ""
    bg_plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", bg_inner)).strip()
    info_pos = html.find('data-role="info"')
    bg_pos = html.find('class="ab-bg-layer"')
    add("bg-text-safe", not bg_plain and (not bg_tags or info_pos < 0 or bg_pos < info_pos),
        "背景层无文字且在信息层之前" if bg_tags
        else "未使用外层背景层")
    bg_offline = not re.search(r"url\(|https?://|@import", bg_segment, flags=re.I)
    add("bg-offline", bg_offline,
        "背景规则全部离线(CSS 渐变/遮罩)" if bg_offline
        else "背景规则含外链或 @import")


    # 左文带必须有主封副题,否则左边只有标题而右侧信息栏落空。
    if layout == "legacy":
        skip("layout-content-fit", "legacy 模板没有新版式信息密度规则,本项未测量")
    elif layout == "band-editorial" and canvas_w == MAIN_W:
        sub_match = re.search(r'<div\s+class="sub"[^>]*>(.*?)</div>', html, re.S)
        sub_text = re.sub(r"<[^>]+>", "", sub_match.group(1)).strip() if sub_match else ""
        add("layout-content-fit", bool(sub_text),
            "主封面副题存在,符合左文带信息密度" if sub_text
            else "band-editorial 需要主封面副题;补 --cover-sub 或改用 center-band")

    # 9 标题行数在族容量内 + 次条字号不低于下限
    #    巨字族 4 行是设计(4/4/3/2 齐整断法),但 13 字塞进 383 宽会把字号压到 24px 下限,
    #    手机上就糊了。这条把「标题太长该换族」从审美问题变成可机检的几何问题。
    h1 = re.search(r'<h1 class="t"[^>]*>(.*?)</h1>', html, re.S)
    if h1:
        visible_title = "".join(_GL.markup_plain(h1.group(1)).split())
        visible_count = _GL.visible_len(visible_title)
        add("title-char-cap", visible_count <= TITLE_HARD_CAP,
            f"标题 {visible_count} 个可见字符(上限 {TITLE_HARD_CAP},中文建议 ≤9)")
    if layout == "legacy":
        skip("title-row-cap", "legacy 模板未使用 .t 标题锚点,本项未测量")
        if not h1:
            skip("title-char-cap", "legacy 模板未使用 .t 标题锚点,本项未测量")
        skip("title-word-break", "legacy 模板未使用 .t 标题锚点,本项未测量")
        skip("title-particle-edge", "legacy 模板未使用 .t 标题锚点,本项未测量")
        skip("title-width-fit", "legacy 模板没有可解析的安全栏宽,本项未测量")
        skip("title-min-px", "legacy 模板没有可解析的字号 token,本项未测量")
    elif h1:
        broken_terms = _GL.locked_title_splits(h1.group(1))
        add("title-word-break", not broken_terms,
            "未拆开高置信标题词组" if not broken_terms
            else f"显式断行拆开标题词组: {broken_terms}")
        particle_edges = _GL.title_particle_edges(h1.group(1))
        add("title-particle-edge", not particle_edges,
            "断行未将助词推到行首/行尾" if not particle_edges
            else f"显式断行产生不自然助词边界: {particle_edges}")
        rows = len(re.findall(r"<br\s*/?>", h1.group(1), flags=re.I)) + 1
        cap = TITLE_ROW_CAP.get(layout)
        if cap:
            add("title-row-cap", rows <= cap,
                f"标题 {rows} 行({layout} 上限 {cap} 行);超了说明标题过长,换族或压短标题")
        px_m = (re.search(r"--t-size:\s*(\d+)px", html)
                or re.search(r'<h1 class="t"[^>]*font-size:\s*(\d+)px', html))
        px = int(px_m.group(1)) if px_m else 0
        safe_left, safe_right, safe_source = _parse_safe_box(html, canvas_w)
        column = max(0.0, safe_right - safe_left)
        title_rules = "\n".join(m.group(1) for m in
                               re.finditer(r"\.t\s*\{([^}]*)\}", html, re.S))
        title_max_width = _px(_css_prop(title_rules, "max-width"))
        if title_max_width is not None:
            column = min(column, title_max_width)
        letter_rule = _css_prop(title_rules, "letter-spacing")
        tracking_m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)em\s*", letter_rule or "")
        tracking = float(tracking_m.group(1)) if tracking_m else 0.0
        width_em = _GL._em(h1.group(1), tracking)
        width_px = width_em * px
        add("title-width-fit", px > 0 and column > 0 and width_px <= column + 0.5,
            f"标题估算宽 {width_px:.1f}px/可用栏 {column:.1f}px({safe_source};"
            "超宽不能依赖浏览器自动折行)")
        add("title-min-px", px >= TITLE_MIN_PX,
            f"{'次条' if canvas_w == SUB_W else '主封'}标题 {px or '?'}px(下限 {TITLE_MIN_PX}px)")

        # 越界授权不是免检:标题盒越过 258–642 时,要求「承载核心信息的那几个字」
        # 仍能整行落在语义区内。按 px 反推一行最多能放几个字,需 ≥ 最长行的 60%。
        band_overreach = max(0.0, 258 - x0, x1 - 642)
        longest_chars = max([_GL.visible_len(line) for line in
                             re.split(r"<br\s*/?>", h1.group(1), flags=re.I)] or [0])
        capacity = int(383 // px) if px > 0 else 0
        need_chars = max(2, -(-longest_chars * 3 // 5))
        add("title-overreach",
            canvas_w == SUB_W or band_overreach <= 0 or capacity >= need_chars,
            f"越出语义区 {band_overreach:g}px;一行可容 {capacity} 字,需 ≥{need_chars} 字"
            + ("" if band_overreach <= 0 else "(越界后核心字仍须整行落在 258–642)"))

        # 字高占比:主封要在信息流里一眼可读,占满画布才立得住;太小说明标题长度撑不起
        # 这个族。次条是方形小图(383×383),排版介质不同,字高下限交给 title-min-px 守。
        share = (px / canvas_h) if px > 0 else 0.0
        if canvas_w == MAIN_W:
            add("title-share", 0.15 <= share <= 0.35,
                f"字高占画布 {share:.0%}(须 15%–35%);低于 15% 请压短标题或换族")
        else:
            add("title-share", True, f"次条字高占画布 {share:.0%}(次条由 title-min-px 守下限)")
    else:
        add("title-present", False, "未找到 h1.t 标题锚点")

    return res


def cmd_check(args) -> int:
    """静态几何断言:不需要浏览器/Kiln,给「HTML 是否守纪律」一个可机检答案。"""
    proj = resolve_project(args.project)
    if not proj:
        return fail("PROJECT_NOT_FOUND", "传项目目录或 slug", project=args.project)
    meta, manifest_error = load_project_manifest(proj)
    if manifest_error:
        return fail("PROJECT_MANIFEST_INVALID", manifest_error, project=proj)
    layout = meta.get("layout") or "legacy"
    targets = [("main", os.path.join(proj, "src", "index.html"), MAIN_W),
               ("sub", os.path.join(proj, "src", "sub.html"), SUB_W)]
    reports, failed, missing = [], [], []
    for kind, path, w in targets:
        if not os.path.isfile(path):
            missing.append(kind)
            failed.append({"kind": kind, "id": "missing-file", "ok": False,
                           "detail": f"缺少预期封面文件: {path}"})
            continue
        page_fx = meta.get(f"{kind}_fx", meta.get("fx") if "fx" in meta else None)
        rows = check_one(path, w, layout, page_fx)
        bad = [r for r in rows if not r["ok"]]
        if html_requires_vendor_validation(path):
            vendor_issue = _shader_vendor_status(os.path.join(proj, "src"))
            if vendor_issue:
                rows.append({"id": "shader-vendor", "ok": False,
                             "error": vendor_issue["error"], **{
                                 key: value for key, value in vendor_issue.items()
                                 if key != "error"}})
                bad = [r for r in rows if not r["ok"]]
        reports.append({"kind": kind, "file": path, "pass": not bad,
                        "checks": rows})
        if bad:
            failed.extend([{"kind": kind, **r} for r in bad])
    # 跨页规则:次条必须是提炼版而不是主标的复制(缩排式"两页一样"是旧缺陷)
    def _h1_text(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                markup = f.read()
        except OSError:
            return ""
        m = re.search(r'<h1 class="t"[^>]*>(.*?)</h1>', markup, re.S)
        return "".join(_GL.markup_plain(m.group(1)).split()) if m else ""

    main_t = _h1_text(targets[0][1]) if os.path.isfile(targets[0][1]) else ""
    sub_t = _h1_text(targets[1][1]) if os.path.isfile(targets[1][1]) else ""
    cross = []
    if layout == "legacy":
        cross.append({"id": "sub-title-distilled", "ok": True,
                      "detail": "legacy 模板未使用 .t 标题锚点,本项未测量"})
    elif main_t and sub_t:
        n_main = _GL.visible_len(main_t)
        n_sub = _GL.visible_len(sub_t)
        distilled = n_main <= 4 or (sub_t != main_t and abs(n_sub - n_main) >= 2)
        cross.append({"id": "sub-title-distilled", "ok": distilled,
                      "detail": f"主标「{main_t}」{n_main} 字 / 次条「{sub_t}」{n_sub} 字"
                                + ("(主标 ≤4 字,允许原样)" if n_main <= 4 else
                                   ";次条须独立提炼:与主标不同且字数差 ≥2")})
    deliver_val = meta.get("deliver")
    cross.append({"id": "single-deliverable",
                  "ok": deliver_val is None or deliver_val in ("merged", "split"),
                  "detail": ("project.json 未声明 deliver(旧项目,按默认单图交付)"
                             if deliver_val is None else
                             f"deliver={deliver_val}(merged=只交付合并图 / split=三张单图)")})
    if cross:
        reports.append({"kind": "project", "file": proj,
                        "pass": all(r["ok"] for r in cross), "checks": cross})
        failed.extend([{"kind": "project", **r} for r in cross if not r["ok"]])

    coverage = "partial" if layout == "legacy" or missing else "complete"
    payload = {"ok": not failed, "project": proj, "layout": layout,
               "coverage": coverage, "reports": reports}
    limitations = []
    if layout == "legacy":
        limitations.append(
            "legacy 模板不含新族的 data-role/safe 标记;版式专属几何项为 skipped,只报告基础画布/离线检查"
        )
    if missing:
        limitations.append("缺少必要封面文件: " + ", ".join(missing))
    if limitations:
        payload["limitations"] = limitations
    if failed:
        payload["failed"] = failed
        payload["hint"] = "按 failed 的 detail 改 src/*.html 后重跑 check;check 只查几何与离线纪律,不含视觉判断"
    emit(payload)
    return 0 if not failed else 1


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="微信公众号双封面工作站(Artboard 内部画布:主 900×383 + 次 383×383 + 合并图)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("new", help="生成双封面项目")
    pn.add_argument("slug", nargs="?", default="", help="项目名(--list-layouts 时可省略)")
    pn.add_argument("--title", default="",
                    help=f"头条主标题(≤{TITLE_HARD_CAP} 个可见字符,中文建议 ≤9 字;\\n 强制断行;"
                         "标题越长字号越小,超 12 字直接拒绝)")
    pn.add_argument("--sub-title", default="",
                    help="次条标题(缺省自动从主标提炼 2–4 字,不再复制主标题)")
    pn.add_argument("--kicker", default="", help="眉题/栏目名(可空)")
    pn.add_argument("--sub", default="", help="主封面副题(可空)")
    pn.add_argument("--sub-sub", default="", help="次条副题(默认同副题)")
    pn.add_argument("--footer", default="", help="页脚(仅主封面)")
    pn.add_argument("--num", default="", help="期号/序号(仅主封面,如 02)")
    pn.add_argument("--theme", default="ink",
                    help="主题(统一源 _gzh_theme):ink/night/warm/grass/red/mono;"
                         "旧名 blue/dark/green 仍可用(弃用提示)")
    pn.add_argument("--fonts", default="auto",
                    help="auto=默认双字体;或 fonts/ 目录名逗号分隔(第一款=展示体)")
    pn.add_argument("--layout", default="",
                    help="版式族(默认空=旧版居中模板,输出逐字节不变):"
                         + " / ".join(_GL.LAYOUT_SLUGS) + ";用 --list-layouts 看每族适用文案")
    pn.add_argument("--bg-pattern", default="auto", choices=_GL.BG_PATTERNS,
                    help="底纹:CSS 实现、零外部资源。auto=按族取默认(dots/stripe/grain/glow/none)")
    pn.add_argument("--accent-tone", default="auto", choices=_GL.ACCENT_TONES,
                    help="强调处理:font=主标名片色 / capsule=主标色块 / pill=副题胶囊 / none=不做")
    pn.add_argument("--sub-mode", default="same", choices=_GL.SUB_MODES,
                    help="次条策略:same=同版缩排(默认)/ minimal=只留标题 / flat=纯主题纯底、去装饰与底纹(保留照片素材)")
    pn.add_argument("--fx", default="auto", choices=_GL.SHADER_FX + ["auto", "none"],
                    help="着色器底材(shader-effects-inc/shaders,MIT):auto=按族取默认 / none=纯 CSS 底纹;"
                         "fx 在场时 CSS 底纹让位,避免两种底材叠加")
    pn.add_argument("--title-en", default="",
                    help="英文/拼音水印(边缘装饰层,不承担关键信息;英文 ≤24 字符)")
    pn.add_argument("--badge", default="", help="贴纸文字(≤6 字,用于 stack-cards / kraft-note)")
    pn.add_argument("--side-label", default="", help="边缘竖排小字(≤6 字,装饰用途)")
    pn.add_argument("--meta", default="",
                    help="时间/地点/主办,逗号分隔(plate-page 用;≤4 项,每项 ≤14 字)")
    pn.add_argument("--image", default="",
                    help="plate-page 必填的本地 PNG/JPEG/WebP 照片;不会联网或覆盖已有素材")
    pn.add_argument("--list-layouts", action="store_true",
                    help="列出 6 套版式族及适用文案形态(可省略 slug/--title)")
    pn.add_argument("--bg-recipe", dest="bg_recipe", default="", metavar="配方",
                    help="外层背景配方(" + "/".join(_GL.BG_RECIPE_SLUGS) + ");默认不加")
    pn.add_argument("--deliver", default="merged", choices=["merged", "split"],
                    help="交付口径:merged=只交付一张合并图(默认)/ split=三张单图都要")
    pn.add_argument("--force", action="store_true")
    pn.set_defaults(func=cmd_new)

    pe = sub.add_parser("export", help="导出:默认只出一张合并图(长封面在左+方形在右);--split 出三张单图")
    pe.add_argument("project", help="项目目录或 slug")
    pe.add_argument("--only", default="", choices=["", "main", "sub", "merged"],
                    help="main/sub=只出该单张;merged=只重拼/复用已产出的单图封面")
    pe.add_argument("--split", action="store_true",
                    help="同时产出 cover-main-/cover-sub-/cover-merged- 三张单图(旧行为)")
    pe.add_argument("--scale", type=int, default=2, choices=[1, 2])
    pe.add_argument("--outdir", default="")
    pe.add_argument("--bg", default="#f6f7f9", help="合并图底色")
    pe.set_defaults(func=cmd_export)

    pm = sub.add_parser("merge", help="仅重拼合并图(不重导出单张;拼接仍走 kiln img stitch,需 Kiln)")
    pm.add_argument("project")
    pm.add_argument("--gap", type=int, default=MERGE_GAP, help="间隔 CSS px(按导出 scale 自动放大)")
    pm.add_argument("--bg", default="#f6f7f9")
    pm.set_defaults(func=cmd_merge)

    pc = sub.add_parser("check", help="静态几何断言(安全区/固定画布/离线/层级),无需浏览器")
    pc.add_argument("project")
    pc.set_defaults(func=cmd_check)

    pl = sub.add_parser("layouts", help="列 6 套版式族与适用文案形态(同 new --list-layouts)")
    pl.set_defaults(func=lambda a: (print(_GL.layout_list_text()), 0)[1])

    args = p.parse_args()
    if getattr(args, "list_layouts", False):
        print(_GL.layout_list_text())
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
