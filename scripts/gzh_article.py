"""公众号文章排版器:Markdown → 微信公众号编辑器可直接粘贴的全内联样式 HTML。

用法:
  python gzh_article.py convert <input.md> --out article.html [--title 标题]
                  [--author 署名] [--theme ink|night|warm|grass|red|mono] [--preview]
                  [--cover-layout band-editorial] [--cover-kicker 眉题] [--cover-sub 副题]
                  [--cover-image PATH (plate-page)]
  python gzh_article.py demo --outdir <目录>   # 生成示例 .md 并转换
  python gzh_article.py check <article.html>   # 通用内联样式自检
  python gzh_preview_copy.py <article.html>    # 单篇/多篇预览与剪贴板中转

产出:
  <out>            公众号正文片段(全内联样式,<section> 包裹,无 class/id/script/style 标签)
  <out_stem>.preview-copy.html  单文件预览复制页(选择/预览/复制;打开官方 135)
  check 输出单行 JSON(violations 为空 = 兼容通过)

Artboard 不克隆 135 编辑器，也不模拟其私有 DOM。
                 需要 135 中转时,运行 `convert --preview` 生成页面;预览复制页只负责选择/预览/复制,实际编辑始终使用官方 135。

排版规范依据(来源与决策记录见 references/gzh-typography.md 与 docs/gzh-spec-summary.md):
  - doocs/md(20k+ star 微信 Markdown 编辑器)主题 CSS 的内联化结论:
    <section> 包裹 + 每个元素 style 内联 + 桌面级字号(正文 15px)+ 主色强调;
  - 本工具将样式内联作为兼容策略,不假定官方编辑器会固定清洗某些标签或属性;
    粘贴后应在官方编辑器预览中核对实际保留效果;
  - 斜体/删除线在移动端中文可读性差 → 弱化处理(遵循主流公众号排版惯例)。
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import _proc
from gzh_preview_copy import write_preview_copy_page
import _gzh_layouts as _GHL

COVER_LAYOUT_DEFAULT = "auto"
COVER_LAYOUT_NO_SUB_DEFAULT = "center-band"
COVER_LAYOUT_CHOICES = ("auto", *_GHL.LAYOUT_SLUGS, "legacy")
COVER_FX_CHOICES = ("auto", "none", *_GHL.SHADER_FX)


# ---------------------------------------------------------------- 主题

FONT_STACK = ("-apple-system-font,BlinkMacSystemFont,'Helvetica Neue',"
              "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif")
CODE_FONT = "'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

# 主题:唯一真相源 = _gzh_theme.py(与 gzh_cover 共用;一处改色两产物同变)
import _gzh_theme as _GZT
THEMES, _THEME_ALIAS = _GZT.article_themes()


def _resolve_theme(name: str) -> str:
    """旧名别名(default/orange/green)→ 新名 + 一次性弃用提示(stderr)。"""
    if name in _THEME_ALIAS:
        canonical = _THEME_ALIAS[name]
        note = ("色值已统一到全局主题源,与旧 green 不同" if name == "green" else f"请改用 {canonical}")
        print(f"△ 主题名「{name}」已弃用 → 改用「{canonical}」({note})。", file=sys.stderr)
        return canonical
    return name


def _extract_h1(md_text: str) -> str:
    """文章第一个 H1(取 `# 标题` 行;图文与封面标题同源)。"""
    for line in md_text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------- 行内解析

def esc(s: str) -> str:
    return html_mod.escape(s, quote=True)


def esc_attr(s: str) -> str:
    """Normalize one existing entity layer, then escape for a quoted HTML attribute."""
    return html_mod.escape(html_mod.unescape(s), quote=True)


def _markdown_url_allowed(raw: str, *, image: bool = False) -> bool:
    """Allow portable article URLs only; the rendered value is already HTML-escaped."""
    value = html_mod.unescape(raw or "").strip()
    if not value or "\\" in value or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        return False
    try:
        scheme = urlsplit(value).scheme.lower()
    except ValueError:
        return False
    if not scheme:
        return True  # relative path, query, fragment, or protocol-relative URL
    if image and scheme == "data":
        return bool(re.match(r"^data:image/(?:png|jpe?g|gif|webp|avif|bmp);base64,", value, re.I))
    return scheme in ({"http", "https"} if image else {"http", "https", "mailto", "tel"})


class Inline:
    """行内 Markdown → 内联样式 HTML。顺序:转义 → 代码 → 图片 → 链接 → 强调。"""

    def __init__(self, t: dict):
        self.t = t

    def render(self, s: str) -> str:
        tokens: list[str] = []
        s = esc(s)

        def stash(h: str) -> str:
            tokens.append(h)
            return f"\x00{len(tokens) - 1}\x00"

        # 1) 行内代码(优先级最高,内部不再处理)
        s = re.sub(r"`([^`\n]+)`",
                   lambda m: stash(
                       f'<code style="font-family:{CODE_FONT};font-size:87%;">'
                       f'{m.group(1)}</code>'), s)

        # 2) 图片 ![alt](src)
        img_style = ("display:block;border-radius:4px;max-width:100%;"
                     "margin:16px auto;")
        def _image(m):
            alt, src = m.group(1), m.group(2)
            if not _markdown_url_allowed(src, image=True):
                return stash(alt)
            return stash(f'<img src="{esc_attr(src)}" alt="{esc_attr(alt)}" style="{img_style}"/>')
        s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", _image, s)

        # 3) 链接 [text](url) — 链接文字再过一遍强调处理
        def _link(m):
            inner = self._emphasis(m.group(1))
            href = m.group(2)
            if not _markdown_url_allowed(href):
                return stash(inner)
            return stash(f'<a href="{esc_attr(href)}" style="color:{self.t["primary"]};'
                         f'text-decoration:none;">{inner}</a>')
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, s)

        # 4) 强调
        s = self._emphasis(s)
        # 5) 还原
        s = re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m.group(1))], s)
        return s

    def _emphasis(self, s: str) -> str:
        t = self.t
        s = re.sub(r"\*\*([^*\n]+)\*\*",
                   rf'<strong style="color:{t["primary"]};font-weight:700;">\1</strong>', s)
        s = re.sub(r"(?<![A-Za-z0-9])__([^_\n]+)__(?![A-Za-z0-9])",
                   rf'<strong style="color:{t["primary"]};font-weight:700;">\1</strong>', s)
        s = re.sub(r"~~([^~\n]+)~~",
                   f'<span style="text-decoration:line-through;'
                   f'color:{t["muted"]};">\\1</span>', s)
        # 斜体:中文场景降级为主色着色(斜体在移动端中文可读性差,主流惯例)
        s = re.sub(r"(?<![A-Za-z0-9])\*([^*\n]+)\*(?![A-Za-z0-9])",
                   rf'<span style="color:{t["primary"]};">\1</span>', s)
        return s


# ---------------------------------------------------------------- 块解析

def parse_blocks(lines: list[str]) -> list[dict]:
    """把 Markdown 行解析为块列表。支持:标题/段落/引用/无序有序列表(1 层嵌套)/
    围栏代码/表格/分割线/独立图片行。"""
    blocks: list[dict] = []
    i, n = 0, len(lines)
    para: list[str] = []

    def flush_para():
        if para:
            blocks.append({"type": "p", "text": " ".join(para).strip()})
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        # 围栏代码
        if stripped.startswith("```"):
            flush_para()
            lang = stripped[3:].strip()
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i].rstrip("\n"))
                i += 1
            i += 1  # 跳过闭合 ```
            blocks.append({"type": "code", "lang": lang,
                           "text": "\n".join(code_lines)})
            continue

        # 分割线
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            flush_para()
            blocks.append({"type": "hr"})
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            flush_para()
            blocks.append({"type": f"h{len(m.group(1))}", "text": m.group(2).strip()})
            i += 1
            continue

        # 引用(收集连续 > 行,支持内部空行)
        if stripped.startswith(">"):
            flush_para()
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].lstrip())
                i += 1
            blocks.append({"type": "quote", "lines": quote_lines})
            continue

        # 表格:| a | b |  +  |---|---|
        if stripped.startswith("|") and i + 1 < n and \
                re.fullmatch(r"\|?[\s:|-]+\|?", lines[i + 1].strip()) and \
                "-" in lines[i + 1]:
            flush_para()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append({"type": "table", "header": header, "rows": rows})
            continue

        # 列表(支持 1 层嵌套:2-4 空格缩进的子项)
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line.rstrip())
        if m:
            flush_para()
            items = []
            while i < n:
                mm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[i].rstrip())
                if not mm:
                    # 列表项续行(缩进且非空)
                    if lines[i].strip() and items and \
                            re.match(r"^\s{2,}", lines[i]):
                        items[-1]["text"] += " " + lines[i].strip()
                        i += 1
                        continue
                    break
                indent = len(mm.group(1).expandtabs(4))
                ordered = mm.group(2)[0].isdigit()
                items.append({"level": 1 if indent >= 2 else 0,
                              "ordered": ordered, "text": mm.group(3).strip()})
                i += 1
            blocks.append({"type": "list", "items": items})
            continue

        # 独立图片行
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", stripped)
        if m:
            flush_para()
            blocks.append({"type": "img", "alt": m.group(1), "src": m.group(2)})
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return blocks


# ---------------------------------------------------------------- 渲染

class Renderer:
    def __init__(self, t: dict):
        self.t = t
        self.inline = Inline(t)

    def _sec(self, style: str, inner: str) -> str:
        return f'<section style="{style}">{inner}</section>'

    def p(self, text: str) -> str:
        return self._sec(
            f"margin:24px 8px;font-size:15px;line-height:1.75;letter-spacing:0.5px;"
            f"color:{self.t['text']};text-align:justify;",
            self.inline.render(text))

    def h(self, level: int, text: str) -> str:
        t = self.t
        rendered = self.inline.render(text)
        if level == 1:
            return self._sec(
                f"margin:40px 8px 24px;text-align:center;font-size:20px;"
                f"font-weight:700;color:{t['text']};", rendered)
        if level == 2:
            return self._sec(
                f"margin:36px 8px 20px;", self._sec(
                    f"display:table;padding:6px 14px;margin:0 auto;font-size:17px;"
                    f"font-weight:700;color:#ffffff;background:{t['primary']};"
                    f"border-radius:6px;", rendered))
        if level == 3:
            return self._sec(
                f"margin:30px 8px 16px;font-size:16px;font-weight:700;"
                f"color:{t['text']};", self._sec(
                    f"border-left:3px solid {t['primary']};padding-left:10px;",
                    rendered))
        return self._sec(
            f"margin:24px 8px 12px;font-size:15px;font-weight:700;"
            f"color:{t['primary']};", rendered)

    def quote(self, blocks: list[dict]) -> str:
        inner = "".join(self.block(b, in_quote=True) for b in blocks)
        return self._sec(
            f"margin:24px 8px;padding:12px 14px;border-left:3px solid "
            f"{self.t['primary']};background:{self.t['soft']};border-radius:0 6px 6px 0;",
            inner)

    def quote_p(self, text: str) -> str:
        return self._sec(
            f"margin:8px 0;font-size:14px;line-height:1.7;letter-spacing:0.5px;"
            f"color:{self.t['quote_text']};",
            self.inline.render(text))

    def list(self, items: list[dict]) -> str:
        t = self.t
        out = []
        for idx, it in enumerate(items):
            pad = "padding-left:1.5em;" if it["level"] else ""
            if it["ordered"]:
                no = sum(1 for x in items[:idx + 1]
                         if x["ordered"] and x["level"] == it["level"])
                marker = f'<span style="color:{t["primary"]};font-weight:700;">{no}.</span>'
            else:
                marker = f'<span style="color:{t["primary"]};font-weight:700;">•</span>'
            body = self.inline.render(it["text"])
            out.append(self._sec(
                f"margin:10px 8px;font-size:15px;line-height:1.75;"
                f"letter-spacing:0.5px;color:{t['text']};{pad}",
                f'{marker}<span style="margin-left:8px;">{body}</span>'))
        return "".join(out)

    def code_block(self, text: str, lang: str) -> str:
        t = self.t
        label = (f'<section style="margin:0;padding:8px 14px;font-size:12px;'
                 f'color:{t["muted"]};background:{t["soft"]};'
                 f'border-radius:6px 6px 0 0;font-family:{CODE_FONT};">{esc(lang)}</section>'
                 if lang else "")
        body = self._sec(
            f"padding:14px;font-size:13px;line-height:1.6;background:{t['soft']};"
            f"{'' if lang else 'border-radius:6px;'}white-space:pre-wrap;"
            f"word-break:break-all;font-family:{CODE_FONT};color:{t['text']};",
            esc(text))
        return self._sec(
            f"margin:24px 8px;border:1px solid {t['border']};border-radius:6px;"
            f"overflow:hidden;", label + body)

    def table(self, header: list[str], rows: list[list[str]]) -> str:
        t = self.t
        th_style = (f"border:1px solid {t['border']};padding:8px 12px;"
                    f"background:{t['soft']};font-weight:700;color:{t['text']};")
        td_style = f"border:1px solid {t['border']};padding:8px 12px;color:{t['text']};"
        ths = "".join(f'<th style="{th_style}">{self.inline.render(h)}</th>'
                      for h in header)
        trs = []
        for r in rows:
            tds = "".join(f'<td style="{td_style}">{self.inline.render(c)}</td>'
                          for c in r)
            trs.append(f"<tr>{tds}</tr>")
        return self._sec(
            f"margin:24px 8px;font-size:14px;line-height:1.6;",
            f'<table style="border-collapse:collapse;margin:0 auto;min-width:80%;">'
            f"<thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>")

    def img(self, alt: str, src: str) -> str:
        if not _markdown_url_allowed(src, image=True):
            return self._sec(
                "margin:24px 8px;text-align:center;",
                esc(alt))
        return self._sec(
            "margin:24px 8px;text-align:center;",
            f'<img src="{esc_attr(src)}" alt="{esc_attr(alt)}" '
            f'style="display:block;border-radius:4px;max-width:100%;margin:0 auto;"/>'
            + (self._sec(f"margin-top:8px;font-size:12px;color:{self.t['muted']};",
                         esc(alt)) if alt else ""))

    def hr(self) -> str:
        return self._sec(
            f"margin:36px 8px;border-top:1px solid {self.t['border']};height:0;", "")

    def block(self, b: dict, in_quote: bool = False) -> str:
        if in_quote:
            if b["type"] == "p":
                return self.quote_p(b["text"])
            if b["type"] == "list":
                return self.list(b["items"])
        fn = {"p": lambda: self.p(b["text"]),
              "h1": lambda: self.h(1, b["text"]),
              "h2": lambda: self.h(2, b["text"]),
              "h3": lambda: self.h(3, b["text"]),
              "h4": lambda: self.h(4, b["text"]),
              "quote": lambda: self.quote(parse_blocks(b["lines"])),
              "list": lambda: self.list(b["items"]),
              "code": lambda: self.code_block(b["text"], b["lang"]),
              "table": lambda: self.table(b["header"], b["rows"]),
              "img": lambda: self.img(b["alt"], b["src"]),
              "hr": self.hr}
        return fn[b["type"]]()


TITLE_BANNER = (
    '<section style="margin:16px 8px 32px;text-align:center;">'
    '<section style="font-size:22px;font-weight:700;color:{text};'
    'letter-spacing:1px;">{title}</section>{author}</section>')
AUTHOR_LINE = (
    '<section style="margin-top:12px;font-size:13px;color:{muted};">{author}</section>')


def render_article(md_text: str, theme: str, title: str = "", author: str = "") -> str:
    t = THEMES[theme]
    blocks = parse_blocks(md_text.splitlines())
    if not blocks:
        raise ValueError("EMPTY_INPUT")
    r = Renderer(t)
    body = "".join(r.block(b) for b in blocks)
    head = ""
    if title:
        author_html = (AUTHOR_LINE.format(muted=t["muted"], author=esc(author))
                       if author else "")
        head = TITLE_BANNER.format(text=t["text"], title=esc(title),
                                   author=author_html)
    return head + body


# ---------------------------------------------------------------- 兼容自检

ALLOWED_TAGS = {"section", "p", "h1", "h2", "h3", "h4", "h5", "h6", "span",
                "strong", "em", "del", "hr", "br", "img", "table", "thead",
                "tbody", "tr", "th", "td", "ul", "ol", "li", "a", "blockquote",
                "code", "figure", "figcaption"}
BANNED_PATTERNS = ("class=", "<script", "<style", "<link", "id=", "javascript:")


class _CompatAttributeAudit(HTMLParser):
    """Find active attributes and non-portable URLs in generated article HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.event_attrs: list[str] = []
        self.unsafe_urls: list[str] = []

    def _inspect(self, tag: str, attrs):
        for name, value in attrs:
            attr = (name or "").lower()
            if attr.startswith("on") or attr == "srcdoc":
                self.event_attrs.append(f"{tag}[{attr}]")
            if value is None:
                continue
            if attr in {"href", "src", "xlink:href"} and not _markdown_url_allowed(
                    value, image=(attr != "href")):
                self.unsafe_urls.append(f"{tag}[{attr}]={value[:100]}")
            elif attr in {"action", "formaction", "ping"}:
                self.unsafe_urls.append(f"{tag}[{attr}]")

    def handle_starttag(self, tag, attrs):
        self._inspect(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._inspect(tag, attrs)


def check_compat(path: str) -> dict:
    """检查通用微信文章片段；预览复制页本身不应作为文章片段检查。"""
    with open(path, encoding="utf-8") as f:
        doc = f.read()
    violations: list[str] = []
    audit = _CompatAttributeAudit()
    audit.feed(doc)
    audit.close()
    if audit.event_attrs:
        violations.append(f"存在事件处理器或 srcdoc 属性: {', '.join(sorted(set(audit.event_attrs))[:8])}")
    if audit.unsafe_urls:
        violations.append(f"存在不安全或不可移植 URL: {', '.join(sorted(set(audit.unsafe_urls))[:8])}")
    for pat in BANNED_PATTERNS:
        if pat.lower() in doc.lower():
            violations.append(f"出现禁用模式: {pat}")
    tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)", doc)
    unknown = sorted({t.lower() for t in tags} - ALLOWED_TAGS)
    if unknown:
        violations.append(f"白名单外标签: {', '.join(unknown)}")
    open_tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)(\s[^>]*)?>", doc)
    unstyled = [t for t, attrs in open_tags
                if t.lower() not in ("br", "img", "table", "thead", "tbody", "tr")
                and "style=" not in (attrs or "")]
    if unstyled:
        violations.append(f"缺内联样式的标签: {', '.join(sorted(set(unstyled))[:8])}"
                          f"(共 {len(unstyled)} 处)")
    ext_css = re.findall(r'<link[^>]+href=', doc, re.I)
    if ext_css:
        violations.append("存在外链 CSS")
    return {"ok": not violations, "violations": violations,
            "counts": {"tags": len(tags), "elements": len(open_tags)},
            "checked_file": os.path.abspath(path)}


# ---------------------------------------------------------------- 子命令

def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


def _truncate_utf16(value: str, max_units: int) -> str:
    parts = []
    used = 0
    for char in value:
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > max_units:
            break
        parts.append(char)
        used += width
    return "".join(parts)


def _preview_copy_path(article: Path) -> Path:
    suffix = ".preview-copy.html"
    stem = article.stem
    filename = stem + suffix
    if _utf16_units(filename) <= 255:
        return article.with_name(filename)
    digest = hashlib.sha256(os.fsencode(article.name)).hexdigest()[:12]
    marker = f".{digest}"
    budget = max(1, 255 - _utf16_units(marker) - _utf16_units(suffix))
    return article.with_name(_truncate_utf16(stem, budget) + marker + suffix)


def _write_preview_copy(fragment: str, title: str, input_path: str,
                        article_path: str) -> str:
    """Create a single-file preview/copy wrapper; the official 135 site remains the editor."""
    article = Path(article_path).expanduser().resolve()
    preview = _preview_copy_path(article)
    source_base = Path(input_path).expanduser().resolve().parent.as_uri() + "/"
    label = (title or Path(input_path).stem).strip()
    write_preview_copy_page(
        [{"title": label, "html": fragment, "base": source_base}],
        preview,
        page_title=f"公众号预览与复制 · {label}")
    return str(preview)


def cmd_convert(args) -> int:
    try:
        with open(args.input, encoding="utf-8") as f:
            md_text = f.read()
    except OSError as exc:
        print(json.dumps({"ok": False, "error": "INPUT_READ_FAILED",
                          "detail": str(exc)}, ensure_ascii=False))
        return 1
    if not md_text.strip():
        print(json.dumps({"ok": False, "error": "EMPTY_INPUT",
                          "hint": "输入 Markdown 为空"}, ensure_ascii=False))
        return 1
    theme_name = _resolve_theme(args.theme)
    if theme_name not in THEMES:
        print(json.dumps({"ok": False, "error": "BAD_THEME",
                          "hint": f"可选主题: {', '.join(sorted(THEMES))}"
                                  "(旧名 default/orange/green 仍可用,见弃用提示)"},
                         ensure_ascii=False))
        return 1
    try:
        fragment = render_article(md_text, theme_name, args.title, args.author)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    write_text(args.out, fragment)
    payload = {"ok": True, "output": os.path.abspath(args.out),
               "theme": theme_name, "chars": len(fragment)}
    if args.preview:
        try:
            preview_path = _write_preview_copy(fragment, args.title, args.input, args.out)
        except (OSError, ValueError) as exc:
            payload.update({"ok": False, "preview_error": str(exc)})
            print(json.dumps(payload, ensure_ascii=False))
            return 1
        payload["preview"] = os.path.abspath(preview_path)
        payload["preview_copy"] = os.path.abspath(preview_path)

    # ---- 图文 ⇒ 封面 单向绑定(D-11-1:默认 on;--no-cover 逃生口) ----
    if not getattr(args, "no_cover", False):
        cover_result = _make_covers(args, md_text, theme_name)
        if cover_result.get("ok"):
            payload["cover"] = cover_result
        else:
            payload["ok"] = False
            payload["cover_error"] = cover_result.get("error")
            payload["cover_hint"] = cover_result.get("hint")
            payload["note"] = "图文产物已生成(见 output),但封面失败——交付时必须向用户说明"
            print(json.dumps(payload, ensure_ascii=False))
            return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _make_covers(args, md_text: str, theme_name: str) -> dict:
    """调同目录 gzh_cover.py 生成同主题双封面(new + export 三图)。
    标题优先级:--cover-title > --title > 文章 H1;slug 默认 = 文件名去扩展名。"""
    import re as _re
    import subprocess
    cover_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gzh_cover.py")
    slug = getattr(args, "slug", "") or _re.sub(r"\.[^.]+$", "", os.path.basename(args.input))
    requested_layout = getattr(args, "cover_layout", COVER_LAYOUT_DEFAULT) or "auto"
    cover_sub = (getattr(args, "cover_sub", "") or "").strip()
    if requested_layout == "auto":
        layout = "band-editorial" if cover_sub else COVER_LAYOUT_NO_SUB_DEFAULT
    else:
        layout = requested_layout
    cover_image_arg = (getattr(args, "cover_image", "") or "").strip()
    cover_image = (os.path.abspath(os.path.expanduser(cover_image_arg))
                   if cover_image_arg else "")
    if layout == "plate-page":
        if not cover_image:
            return {"ok": False, "error": "COVER_IMAGE_REQUIRED",
                    "hint": "文章转换使用 plate-page 时,请提供 --cover-image 本地 PNG/JPEG/WebP 图片"}
        if not os.path.isfile(cover_image):
            return {"ok": False, "error": "COVER_IMAGE_NOT_FOUND",
                    "hint": f"--cover-image 不是现存本地文件: {cover_image}"[:200]}
    elif cover_image:
        return {"ok": False, "error": "COVER_IMAGE_LAYOUT_CONFLICT",
                "hint": "--cover-image 仅与显式 --cover-layout plate-page 搭配使用"}
    requested_fx = getattr(args, "cover_fx", "auto") or "auto"
    if layout == "legacy":
        if requested_fx not in ("auto", "none"):
            return {"ok": False, "error": "COVER_FX_UNSUPPORTED_LAYOUT",
                    "hint": "legacy 模板不接入 WebGPU shader;改用六个新版式或 --cover-fx none"}
        fx = ""
    else:
        fx = _GHL.resolve_fx(layout, requested_fx)
    title = (getattr(args, "cover_title", "") or args.title
             or _extract_h1(md_text) or os.path.basename(args.input)).strip()
    if not title:
        return {"ok": False, "error": "NO_TITLE",
                "hint": "无标题可用:给 --cover-title 或文内 H1"}
    base_cmd = [sys.executable, cover_py, "new", slug, "--title", title,
                "--theme", theme_name]
    if cover_image:
        base_cmd += ["--image", cover_image]
    if getattr(args, "cover_kicker", ""):
        base_cmd += ["--kicker", args.cover_kicker]
    if cover_sub:
        base_cmd += ["--sub", cover_sub]
    if getattr(args, "cover_sub_title", ""):
        base_cmd += ["--sub-title", args.cover_sub_title]
    if getattr(args, "cover_sub_sub", ""):
        base_cmd += ["--sub-sub", args.cover_sub_sub]
    if getattr(args, "cover_num", ""):
        base_cmd += ["--num", args.cover_num]

    def create_and_check(candidate_layout: str, *, overwrite_created: bool = False):
        cmd_new = list(base_cmd)
        if overwrite_created:
            # Only replace the project that this invocation just created and checked;
            # never force the initial creation over a pre-existing user project.
            cmd_new.append("--force")
        if candidate_layout != "legacy":
            candidate_fx = _GHL.resolve_fx(candidate_layout, requested_fx)
            cmd_new += ["--layout", candidate_layout, "--fx", candidate_fx or "none"]
        r_new = subprocess.run(cmd_new, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
        lines = [line for line in (r_new.stdout or "").splitlines() if line.strip()]
        new_data = json.loads(lines[-1]) if lines else {}
        if r_new.returncode != 0 or not new_data.get("ok"):
            return new_data, {}, {"ok": False, "error": "COVER_NEW_FAILED",
                                  "hint": (new_data.get("hint") or r_new.stderr or "")[:200]}
        cmd_check = [sys.executable, cover_py, "check", new_data["project"]]
        r_check = subprocess.run(cmd_check, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=120)
        check_lines = [line for line in (r_check.stdout or "").splitlines() if line.strip()]
        check_data = json.loads(check_lines[-1]) if check_lines else {}
        if r_check.returncode != 0 or not check_data.get("ok"):
            failed = check_data.get("failed") or []
            details = [f"{row.get('kind', '?')}/{row.get('id', '?')}: {row.get('detail', '')}"
                       for row in failed]
            error = {"ok": False, "error": "COVER_CHECK_FAILED",
                     "hint": ("；".join(details) or check_data.get("hint")
                              or r_check.stderr or "双封面静态检查失败")[:300],
                     "failed": failed}
            return new_data, check_data, error
        return new_data, check_data, None

    layout_fallback = None
    try:
        new_payload, check_payload, cover_error = create_and_check(layout)
        created_by_this_invocation = bool(new_payload.get("ok"))
        title_fit_checks = {"title-word-break", "title-particle-edge", "title-row-cap",
                            "title-min-px", "title-width-fit"}
        failed_ids = {row.get("id") for row in (cover_error or {}).get("failed", [])}
        if (cover_error and requested_layout == "auto" and layout == "band-editorial"
                and failed_ids.intersection(title_fit_checks)):
            first_hint = cover_error.get("hint", "标题断行不适配")
            fallback_layout = COVER_LAYOUT_NO_SUB_DEFAULT
            fallback_data, fallback_check, fallback_error = create_and_check(
                fallback_layout, overwrite_created=created_by_this_invocation)
            if fallback_error:
                return {"ok": False, "error": fallback_error.get("error", "COVER_CHECK_FAILED"),
                        "hint": (f"band-editorial标题不适配({first_hint});center-band回退失败: "
                                 f"{fallback_error.get('hint', '')}")[:300],
                        "failed": fallback_error.get("failed", [])}
            new_payload, check_payload = fallback_data, fallback_check
            layout = fallback_layout
            fx = _GHL.resolve_fx(layout, requested_fx)
            layout_fallback = {"from": "band-editorial", "to": fallback_layout,
                               "reason": first_hint}
        elif cover_error:
            return cover_error
        # 封面跟图文落在同一个 outdir(传 --outdir 时),否则用户去 studio_dir 里翻图
        outdir = getattr(args, "outdir", "") or ""
        # v1.26 默认单图交付:export 默认只出 cover-<slug>.png;要主/次单张才显式 --split
        cmd_exp = [sys.executable, cover_py, "export", new_payload["project"]]
        if getattr(args, "cover_split", False):
            cmd_exp.append("--split")
        if outdir:
            cmd_exp += ["--outdir", outdir]
        r_exp = _proc.run(cmd_exp, timeout=300)
        if r_exp.timed_out:
            return {"ok": False, "error": "COVER_EXPORT_TIMEOUT",
                    "hint": "封面导出超时;Kiln/浏览器进程树已终止"}
        exp_lines = [l for l in (r_exp.stdout or "").splitlines() if l.strip()]
        exp_payload = json.loads(exp_lines[-1]) if exp_lines else {}
        if r_exp.returncode != 0 or not exp_payload.get("ok"):
            # 把首条 failed[].error 带出来:否则只剩一句通用的"单张失败",
            # 用户和 Agent 都得去翻 gzh_cover.py 才知道是缺 Kiln / 缺浏览器 / 尺寸问题。
            first = (exp_payload.get("failed") or [{}])[0]
            detail = first.get("error") or ""
            hint = first.get("hint") or exp_payload.get("hint") or r_exp.stderr or ""
            if detail and detail not in hint:
                hint = f"{detail}: {hint}"
            return {"ok": False, "error": "COVER_EXPORT_FAILED",
                    "hint": hint[:300]}
        return {"ok": True, "project": new_payload["project"],
                "title": title, "theme": theme_name, "layout": layout,
                "fx": fx or "none", "layout_fallback": layout_fallback,
                "check": {"ok": True, "coverage": check_payload.get("coverage"),
                          "passed": [r.get("kind") for r in check_payload.get("reports", [])
                                     if r.get("pass")]},
                "images": [e.get("output") for e in exp_payload.get("exports", [])],
                "note": "图文必带双封面(单向绑定);反向 gzh_cover 不产图文"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "COVER_EXCEPTION", "hint": f"{type(exc).__name__}: {exc}"[:200]}


def _studio_dir() -> str:
    """studio_dir(路径口径与 gzh_cover 一致;未用则不引 _config)。"""
    try:
        from _config import cfg, near_workspace
        return cfg("studio_dir", near_workspace("artboard-studio"))
    except Exception:  # noqa: BLE001
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "..", "artboard-studio")


DEMO_MD = """# 双封面时代的公众号排版指南

> 本文演示 artboard 公众号排版器的全部组件:标题、引用、列表、表格、代码块与分割线。

Artboard 将头条封面与次条封面作为一组来设计,共享主题与字体语言,方便同稿联动。下列画布尺寸是本工具的内部默认值,参考第三方 135 编辑教程,并非已核实的微信官方规格；实际展示请以当前公众号后台预览为准。

## 一、封面画布速记

- 头条封面:Artboard 默认 900 × 383 px(约 2.35:1),关键信息优先放入内部保守安全区
- 次条封面:Artboard 默认 383 × 383 px(1:1),减少元素以适配小尺寸阅读
- 合并预览:两图等高拼接,间隔 57px,用于联审；不是平台要求的上传画布

## 二、为什么优先用内联样式

为提高复制到官方编辑器后的样式兼容性,本工具默认将正文格式写入元素的 `style` 属性；class、id 与 `<style>` 的保留情况可能随编辑器流程变化,应通过官方编辑器预览确认。这个实现选择是兼容策略,不是对平台 DOM 清洗行为的官方承诺。

| 组件 | 存活方式 | 备注 |
|---|---|---|
| 段落 | section + 内联样式 | 字号 15px 最稳 |
| 引用 | section 左边框 | 背景色浅灰 |
| 代码块 | section + pre-wrap | 长行自动换行 |

## 三、一段代码示例

```python
from artboard import gzh_cover
gzh_cover.export("my-post")   # 主封面 + 次条 + 合并图,一次导出
```

---

1. 用 `gzh_cover.py new` 生成双封面项目
2. 改文案后 `gzh_cover.py export` 三图齐出
3. 用 `gzh_article.py convert` 排版正文

*斜体在中文场景被转为主色着色*,~~删除线保留但降灰~~,[链接样式](https://github.com/doocs/md)参考 doocs/md。
"""


def cmd_demo(args) -> int:
    outdir = args.outdir or os.path.join(os.getcwd(), "gzh-demo")
    md_path = os.path.join(outdir, "demo.md")
    out_path = os.path.join(outdir, "demo-article.html")
    write_text(md_path, DEMO_MD)
    rc = cmd_convert(argparse.Namespace(
        input=md_path, out=out_path, title="双封面时代的公众号排版指南",
        cover_title="双封面指南", author="artboard · 排版器演示",
        theme=args.theme, preview=True))
    if rc == 0:
        chk = check_compat(out_path)
        chk["demo_md"] = os.path.abspath(md_path)
        print(json.dumps(chk, ensure_ascii=False))
        return 0 if chk["ok"] else 1
    return rc


def cmd_check(args) -> int:
    if not os.path.isfile(args.file):
        print(json.dumps({"ok": False, "error": "FILE_NOT_FOUND",
                          "detail": args.file}, ensure_ascii=False))
        return 1
    # 主题一致性机检(D-11-7):图文与封面的 tokens 必须同源同值(容差 0)
    if getattr(args, "theme_consistency", False):
        cover_html = getattr(args, "cover_html", "")
        if not cover_html or not os.path.isfile(cover_html):
            print(json.dumps({"ok": False, "error": "USAGE",
                              "hint": "需要 --cover-html <封面项目>/src/index.html"},
                             ensure_ascii=False))
            return 2
        theme = _resolve_theme(getattr(args, "theme", "") or "ink")
        a_roles = _GZT.article_roles(theme)
        c_roles = _GZT.cover_roles(theme)
        with open(args.file, encoding="utf-8", errors="replace") as f:
            a_text = f.read().lower()
        with open(cover_html, encoding="utf-8", errors="replace") as f:
            c_text = f.read().lower()
        mismatches = []
        # ① 核心角色必命中(容差 0:颜色必须精确)
        for role in ("primary", "text"):
            if a_roles[role].lower() not in a_text:
                mismatches.append({"role": role, "expected": a_roles[role], "where": "article"})
        for role in ("bg", "bg2", "ink", "accent"):
            if c_roles[role].lower() not in c_text:
                mismatches.append({"role": role, "expected": c_roles[role], "where": "cover"})
        # ② 禁他主题强调色混入(同风格的核心威胁是"两套色")
        for other, roles in _GZT.THEMES.items():
            if other == theme:
                continue
            for hexv in (roles["primary"], roles["accent"]):
                if hexv.lower() in a_text or hexv.lower() in c_text:
                    mismatches.append({"role": f"foreign:{other}", "expected": "absent",
                                       "found": hexv})
        print(json.dumps({"ok": not mismatches, "check": "theme-consistency",
                          "theme": theme, "mismatches": mismatches,
                          "hint": None if not mismatches
                          else "两产物色值与 _gzh_theme 不一致:重新用同一 --theme 生成"},
                         ensure_ascii=False))
        return 0 if not mismatches else 1
    result = check_compat(args.file)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="公众号文章排版器(Markdown → 全内联样式 HTML)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("convert", help="转换 Markdown 为公众号 HTML")
    pc.add_argument("input", help="输入 .md 文件")
    pc.add_argument("--out", required=True, help="输出 HTML 路径")
    pc.add_argument("--outdir", default="", help="可选：双封面 PNG 输出目录(正文/预览仍按 --out 落盘)")
    pc.add_argument("--title", default="", help="文章大标题(空=用文内 H1)")
    pc.add_argument("--author", default="", help="作者署名行")
    pc.add_argument("--theme", default="ink",
                    help="主题(统一源 _gzh_theme):ink/night/warm/grass/red/mono;"
                         "旧名 default/orange/green 仍可用(弃用提示)")
    pc.add_argument("--preview", action="store_true", help="同时生成独立预览复制页")
    pc.add_argument("--with-cover", dest="with_cover", action="store_true", default=True,
                    help="(默认)图文同时出同主题双封面")
    pc.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="只出图文不出封面(逃生口;交付汇报需说明)")
    pc.add_argument("--slug", default="", help="封面项目 slug(默认=文件名去扩展名)")
    pc.add_argument("--cover-title", dest="cover_title", default="",
                    help="封面主标题(默认取 --title 或文章 H1)")
    pc.add_argument("--cover-kicker", dest="cover_kicker", default="", help="封面眉题/栏目")
    pc.add_argument("--cover-sub", dest="cover_sub", default="", help="主封面副题")
    pc.add_argument("--cover-sub-title", dest="cover_sub_title", default="",
                    help="次条封面主标题(默认同封面主标题)")
    pc.add_argument("--cover-sub-sub", dest="cover_sub_sub", default="",
                    help="次条封面副题(默认同主封面副题)")
    pc.add_argument("--cover-num", dest="cover_num", default="", help="封面期号")
    pc.add_argument("--cover-image", dest="cover_image", default="",
                    help="plate-page 本地 PNG/JPEG/WebP 主封照片;须同时显式选择 --cover-layout plate-page")
    pc.add_argument("--cover-layout", default=COVER_LAYOUT_DEFAULT,
                    choices=COVER_LAYOUT_CHOICES,
                    help="auto:有主封副题先用 band-editorial,否则 center-band;标题不适配时回退 center-band;可选六族/legacy")
    pc.add_argument("--cover-fx", default="auto", choices=COVER_FX_CHOICES,
                    help="背景 shader 效果(auto=版式默认;none=关闭;11种MIT上游效果)")
    pc.add_argument("--cover-split", dest="cover_split", action="store_true",
                    help="封面分三张出图(主/次/合并);默认只出一张合一图 cover-<slug>.png")
    pc.set_defaults(func=cmd_convert)

    pd = sub.add_parser("demo", help="生成示例文章并转换(自检兼容性)")
    pd.add_argument("--outdir", default="")
    pd.add_argument("--theme", default="ink")
    pd.set_defaults(func=cmd_demo)

    pk = sub.add_parser("check", help="公众号兼容性自检(可加 --theme-consistency)")
    pk.add_argument("file", help="待检查的 HTML 文件")
    pk.add_argument("--theme-consistency", dest="theme_consistency", action="store_true",
                    help="校验图文与封面 tokens 同源同值(11 迭代)")
    pk.add_argument("--cover-html", default="", dest="cover_html",
                    help="<封面项目>/src/index.html")
    pk.add_argument("--theme", default="", help="主题名(默认 ink)")
    pk.set_defaults(func=cmd_check)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
