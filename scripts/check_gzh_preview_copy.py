#!/usr/bin/env python3
"""Offline regression test for the standalone public-account preview/copy page."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from gzh_preview_copy import write_preview_copy_page

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "gzh_preview_copy.py"
ARTICLE_CLI = ROOT / "scripts" / "gzh_article.py"


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="artboard-preview-copy-check-") as tmp:
            work = Path(tmp)
            a = work / "brand-a.html"
            b = work / "brand-b.html"
            out = work / "preview-copy.html"
            a.write_text('<section style="color:#166ec8"><p>品牌A文章</p></section>', encoding="utf-8")
            # A literal closing-script sequence must remain data, not terminate the wrapper script.
            b.write_text('<section><p>品牌B &amp; 版本</p><p></script><script>alert(1)</script></p>'
                         '<img src=x onerror="alert(1)">'
                         '<a href="java&#10;script:alert(2)">恶意换行链接</a>'
                         '<a href="data:text/html;base64,PHNjcmlwdD4=">恶意data文档</a>'
                         '<div class="nested"><div><style>@import url(https://bad.example/nested.css);'
                         '.x{background-image:url(https://bad.example/nested.png)}</style>'
                         '<div><link rel="stylesheet" href="https://bad.example/linked.css"></div>'
                         '<base href="https://bad.example/"><meta http-equiv="refresh" '
                         'content="0;url=https://bad.example/redirect"></div></div>'
                         '<p style="color:#c00;background-image:url(https://bad.example/css.png)">CSS URL</p>'
                         '<p style="color:#090; @import url(https://bad.example/import.css)">CSS import</p>'
                         '<p style="font-weight:bold;width:expression(alert(1))">CSS expression</p>'
                         '<p style="behavior:url(https://bad.example/behavior.htc)">CSS behavior</p>'
                          '<p style="background-image:image-set(&quot;https://bad.example/image-set.png&quot; 1x)">CSS image-set</p>'
                          '<video autoplay muted preload="auto" src="https://bad.example/video.mp4">'
                          '<source src="https://bad.example/video-source.mp4" type="video/mp4">'
                          '<track src="https://bad.example/captions.vtt"></video>'
                          '<audio autoplay preload="auto" src="https://bad.example/audio.mp3">'
                          '<source src="https://bad.example/audio-source.mp3" type="audio/mpeg"></audio>'
                         '<p style="font-size:16px;color:#303030;line-height:1.7;background-color:#fff">'
                         '正常文章格式</p><a href="https://example.com/article">保留链接</a>'
                         '<img src="https://example.com/image.png" alt="保留图片">'
                         '<img src="data:image/png;base64,iVBORw0KGgo=" alt="安全栅格data图">'
                          '<svg><animate xlink:href="#target" attributeName="href" values="javascript:alert(3)"/><a id="target" href="#target">SVG链接</a></svg>'
                          '<math><mi>MathML内容</mi></math>'
                          '<template shadowrootmode="open"><script>window.__template_pwned=1</script>'
                          '<img src=x onerror="alert(4)"><svg onload="alert(5)"></svg></template></section>', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CLI), "--doc", f"品牌A={a}", "--doc", f"品牌B={b}",
                 "--out", str(out)], cwd=ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30)
            if result.returncode:
                raise RuntimeError(f"preview-copy CLI failed: {result.stderr[-2000:]}")
            payload = json.loads(result.stdout)
            page = out.read_text(encoding="utf-8")
            sentinel = work / "sentinel.txt"
            sentinel.write_text("must remain unchanged", encoding="utf-8")
            safe_out = work / "safe-preview.html"
            preexisting_tmp = safe_out.with_suffix(safe_out.suffix + ".tmp")
            symlink_check = None
            try:
                os.symlink(sentinel, preexisting_tmp)
            except (OSError, NotImplementedError):
                pass  # platform/policy may disable symlink creation; report the coverage gap
            else:
                write_preview_copy_page(
                    [{"title": "test", "html": "<p>safe</p>"}], safe_out)
                symlink_check = (sentinel.read_text(encoding="utf-8") == "must remain unchanged"
                                 and safe_out.is_file() and not safe_out.is_symlink()
                                 and preexisting_tmp.is_symlink())
            long_name_output = work / ("p" * 240 + ".html")
            long_name_result = write_preview_copy_page(
                [{"title": "long name", "html": "<p>safe</p>"}], long_name_output)
            checks = {
                "long_output_name_uses_short_temp_component": (
                    long_name_output.name == "p" * 240 + ".html"
                    and long_name_output.is_file()
                    and long_name_result.get("output") == str(long_name_output)),
                "preexisting_temp_symlink_safe": symlink_check,
                "two_versions": payload.get("documents") == 2 and "品牌A" in page and "品牌B" in page,
                "iframe_preview": 'id="preview"' in page and "frame.srcdoc" in page,
                "rich_and_plain_clipboard": "text/html" in page and "text/plain" in page
                    and "navigator.clipboard.write" in page,
                "legacy_copy_fallback": "document.execCommand('copy')" in page,
                "open_135": "https://www.135editor.com/" in page,
                "script_safe_data": "\\u003c/script\\u003e" in page
                    and "</script><script>alert(1)" not in page,
                "active_markup_sanitizer": "function sanitizeMarkup" in page
                    and "function safeUrlAttribute" in page
                    and "name.startsWith('on')" in page and "fallbackCopy(safeHtml)" in page,
                "active_and_media_elements_removed":
                    "querySelectorAll('script,iframe,object,embed,applet,form,style,link,base,meta,template,video,audio,source,track')" in page
                    and all(f"https://bad.example/{name}" in page for name in (
                        "video.mp4", "video-source.mp4", "captions.vtt",
                        "audio.mp3", "audio-source.mp3")),
                "declarative_shadow_root_template_fixture":
                    "template shadowrootmode=\\\"open\\\"" in page
                    and "__template_pwned" in page and "onerror=\\\"alert(4)\\\"" in page,
                "foreign_namespace_elements_removed":
                    "node.namespaceURI !== 'http://www.w3.org/1999/xhtml'" in page
                    and "node.remove();" in page,
                "svg_smil_and_mathml_attack_fixture":
                    r"\u003canimate" in page and r"attributeName=\"href\"" in page
                    and "javascript:alert(3)" in page and r"\u003cmath" in page,
                "inline_css_active_payload_guard": "function safeStyleAttribute(rawValue)" in page
                    and r"/url\s*\(|expression\s*\(|\bprogid\s*:/i" in page
                    and "behavior|-moz-binding" in page
                    and r"/(?:^|;)\s*position\s*:\s*fixed\b/i" in page
                    and "name === 'style' && !safeStyleAttribute(attr.value)" in page,
                "css_image_set_resource_guard":
                    "image-set|image|cross-fade|element|paint" in page
                    and "image-set.png" in page and "CSS image-set" in page,
                "nested_stylesheet_and_css_attack_fixtures":
                    "https://bad.example/nested.css" in page
                    and "https://bad.example/linked.css" in page
                    and "https://bad.example/import.css" in page
                    and "https://bad.example/behavior.htc" in page
                    and "expression(alert(1))" in page,
                "safe_article_formatting_and_assets_retained":
                    "font-size:16px;color:#303030;line-height:1.7;background-color:#fff" in page
                    and "https://example.com/article" in page
                    and "https://example.com/image.png" in page
                    and "(name === 'style' && !safeStyleAttribute(attr.value))" in page,
                "control_character_url_guard": r"/[\u0000-\u001f\u007f]/.test(rawValue)" in page,
                "html_entity_control_payload": r"java\u0026#10;script:alert(2)" in page,
                "url_protocol_allowlist": "['http', 'https', 'mailto', 'tel']" in page
                    and "name === 'srcset'" in page and "data:text/html/SVG" in page,
                "raster_data_image_only": "protocol === 'data'" in page
                    and "data:image\\/" in page and "name === 'src'" in page,
                "dangerous_data_document_payload": "data:text/html;base64" in page,
                "no_external_runtime": '<script src=' not in page,
            }

            source_md = work / "article.md"
            article_dir = work / "article-output"
            article_dir.mkdir()
            article_html = article_dir / "article.html"
            source_md.write_text("# 标题\\n\\n一段正文。\\n", encoding="utf-8")
            converted = subprocess.run(
                [sys.executable, str(ARTICLE_CLI), "convert", str(source_md),
                 "--out", str(article_html), "--outdir", str(article_dir),
                 "--theme", "ink", "--no-cover", "--preview"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30)
            if converted.returncode:
                raise RuntimeError(f"gzh_article convert failed: {converted.stderr[-2000:]}")
            article_payload = json.loads(converted.stdout)
            article_copy = Path(article_payload["preview_copy"])
            checked = subprocess.run(
                [sys.executable, str(ARTICLE_CLI), "check", str(article_html)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30)
            if checked.returncode:
                raise RuntimeError(f"gzh_article check failed: {checked.stdout[-2000:]} {checked.stderr[-2000:]}")
            compat_payload = json.loads(checked.stdout)
            checks["convert_preview_copy"] = article_copy.is_file()
            checks["generic_compatibility"] = compat_payload.get("ok") is True
            failed = [name for name, passed in checks.items() if passed is False]
            skipped = [name for name, passed in checks.items() if passed is None]
            if failed:
                raise RuntimeError("preview-copy assertions failed: " + json.dumps(checks, ensure_ascii=False))
            print(json.dumps({"ok": True, "output": str(out), "checks": checks,
                              "skipped": skipped}, ensure_ascii=False))
            return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
