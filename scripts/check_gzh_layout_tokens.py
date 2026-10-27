#!/usr/bin/env python3
"""Regression checks for cover layout tokens and fail-closed title export."""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import zlib
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import _gzh_layouts as layouts
import gzh_cover


def relative_webgpu_paths_resolve_from_caller() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-relative-export-path-") as temp:
        caller = Path(temp)
        previous = os.getcwd()
        calls = []

        def fake_runner(command, *, cwd, env, timeout):
            calls.append((command, cwd, env, timeout))
            return SimpleNamespace(stdout='{"ok":true}', stderr="", returncode=0)

        try:
            os.chdir(caller)
            with patch.object(gzh_cover._shader_fx, "_run_export_with_timeout",
                              side_effect=fake_runner):
                result = gzh_cover.run_export(
                    "src/cover.html", "out/cover.png", 900, 383, 1, webgpu=True)
        finally:
            os.chdir(previous)
        if not result.get("ok") or not calls:
            return False
        command, cwd, _env, timeout = calls[0]
        source = Path(command[command.index("--source") + 1])
        output = Path(command[command.index("--output") + 1])
        return (source == caller / "src" / "cover.html" and output == caller / "out" / "cover.png"
                and source.is_absolute() and output.is_absolute()
                and cwd == gzh_cover.SKILL_DIR and timeout == 600)


def main_title_minimum_and_width_are_enforced() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    tiny_html = layouts.render("giant-caps", theme,
                               layouts.make_data(title="城" * 40), font_vars="",
                               sub=False, pattern="none", fx="")
    wide_html = layouts.render("center-band", theme,
                               layouts.make_data(title="城市更新的三条路"), font_vars="",
                               sub=False, pattern="none", fx="")
    title_match = re.search(r'(<h1 class="t"[^>]*>)(.*?)(</h1>)', wide_html, re.S)
    if not title_match:
        return False
    wide_html = wide_html[:title_match.start(2)] + title_match.group(2).replace("<br>", "") + wide_html[title_match.end(2):]
    wide_html = re.sub(r"(--t-size:\s*)\d+px", r"\g<1>120px", wide_html, count=1)
    with tempfile.TemporaryDirectory(prefix="artboard-main-title-fit-") as temp:
        tiny_path = Path(temp) / "tiny.html"
        wide_path = Path(temp) / "wide.html"
        tiny_path.write_text(tiny_html, encoding="utf-8")
        wide_path.write_text(wide_html, encoding="utf-8")
        tiny_checks = {row["id"]: row["ok"]
                       for row in gzh_cover.check_one(str(tiny_path), gzh_cover.MAIN_W, "giant-caps")}
        wide_checks = {row["id"]: row["ok"]
                       for row in gzh_cover.check_one(str(wide_path), gzh_cover.MAIN_W, "center-band")}
    return (tiny_checks.get("title-min-px") is False
            and wide_checks.get("title-width-fit") is False)


def invalid_title_fails_before_kiln() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    # 12 字上限之后,手写 HTML 里超长标题是最典型的「导出前必须拦下」场景:
    # 引擎已改成 8–10 字直排,靠断行触发助词边界的路径不再稳定,这条改用字数预算。
    main_html = layouts.render(
        "band-editorial", theme,
        layouts.make_data(title="城市更新的三条路径太长了吧", sub="欢迎关注"),
        font_vars="", sub=False, pattern="none", fx="none")
    sub_html = layouts.render(
        "band-editorial", theme, layouts.make_data(title="封面要点"),
        font_vars="", sub=True, pattern="none", fx="none")
    with tempfile.TemporaryDirectory(prefix="artboard-cover-export-gate-") as temp:
        root = Path(temp) / "project"
        src = root / "src"
        src.mkdir(parents=True)
        (root / "project.json").write_text(
            json.dumps({"layout": "band-editorial", "fx": ""}), encoding="utf-8")
        (src / "index.html").write_text(main_html, encoding="utf-8")
        (src / "sub.html").write_text(sub_html, encoding="utf-8")
        output = Path(temp) / "export"
        emitted = []
        args = type("Args", (), {"project": str(root), "only": "",
                                  "outdir": str(output)})()
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            with patch.object(gzh_cover, "check_kiln",
                              side_effect=AssertionError("Kiln must not run")):
                rc = gzh_cover.cmd_export(args)
        result = emitted[-1] if emitted else {}
        failed_ids = {row.get("id") for row in result.get("failed", [])}
        return (rc == 1 and result.get("error") == "COVER_CHECK_FAILED"
                and "title-char-cap" in failed_ids and not output.exists())


def _write_checked_page(root: Path, filename: str, html: str) -> Path:
    path = root / filename
    path.write_text(html, encoding="utf-8")
    return path


def canvas_and_vertical_safety_are_enforced() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="春日漫游"),
                            font_vars="", sub=False, pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-geometry-") as temp:
        path = Path(temp) / "main.html"
        path.write_text(markup, encoding="utf-8")
        good = {row["id"]: row["ok"] for row in
                gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        wrong_height = markup.replace("height: 383px;", "height: 382px;", 1)
        bad_y = markup.replace("top: 30px; bottom: 30px;", "top: -1px; bottom: 30px;", 1)
        duplicate_poster = markup.replace(
            "</style>", "\n.poster { overflow: visible; }\n</style>", 1)
        constrained_poster = markup.replace(
            "</style>", "\n.poster { max-width: 800px; }\n</style>", 1)
        logical_poster = markup.replace(
            "</style>", "\n.poster { inline-size: 1px; block-size: 1px; }\n</style>", 1)
        bad_box_model = markup.replace(
            "</style>", "\n.poster { box-sizing: content-box; padding: 100px; }\n</style>", 1)
        inline_poster, replaced = re.subn(
            r'(<div class="[^"]*\bposter\b[^"]*")',
            r'\1 style="overflow: visible"', markup, count=1)
        path.write_text(wrong_height, encoding="utf-8")
        height = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        path.write_text(bad_y, encoding="utf-8")
        vertical = {row["id"]: row["ok"] for row in
                    gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        path.write_text(duplicate_poster, encoding="utf-8")
        cascade = {row["id"]: row["ok"] for row in
                   gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        path.write_text(inline_poster, encoding="utf-8")
        inline = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        path.write_text(constrained_poster, encoding="utf-8")
        constrained = {row["id"]: row["ok"] for row in
                       gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        path.write_text(logical_poster, encoding="utf-8")
        logical = {row["id"]: row["ok"] for row in
                   gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
        path.write_text(bad_box_model, encoding="utf-8")
        box_model = {row["id"]: row["ok"] for row in
                     gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
    return (good.get("canvas-fixed") is True
            and good.get("poster-cascade-controlled") is True
            and good.get("safe-zone-vertical-inside") is True
            and height.get("canvas-fixed") is False
            and vertical.get("safe-zone-vertical-inside") is False
            and cascade.get("poster-cascade-controlled") is False
            and cascade.get("canvas-fixed") is False
            and replaced == 1
            and inline.get("poster-cascade-controlled") is False
            and inline.get("canvas-fixed") is False
            and constrained.get("poster-cascade-controlled") is False
            and constrained.get("canvas-fixed") is False
            and logical.get("poster-cascade-controlled") is False
            and logical.get("canvas-fixed") is False
            and box_model.get("poster-cascade-controlled") is False
            and box_model.get("canvas-fixed") is False)


def poster_cascade_cannot_reset_hide_or_leave_viewport() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="画布可见性"),
                            font_vars="", sub=False, pattern="none", fx="")
    payloads = (
        ("all-reset", ".poster { all: initial; }"),
        ("display-none", ".poster { display: none; }"),
        ("absolute-offscreen", ".poster { position: absolute; left: -10000px; }"),
        ("logical-inset-block-offscreen", ".poster { inset-block-start: -10000px; }"),
        ("logical-inset-inline-offscreen", ".poster { inset-inline-start: -10000px; }"),
        ("relative-offscreen", ".poster { position: relative; left: -10000px; }"),
        ("visibility-hidden", ".poster { visibility: hidden; }"),
        ("opacity-zero", ".poster { opacity: 0; }"),
        ("translate-offscreen", ".poster { translate: -10000px 0; }"),
        ("transparent-mask", ".poster { mask-image: linear-gradient(transparent, transparent); }"),
        ("hidden-keyframe-animation", "@keyframes vanish { to { opacity:0; } } "
         ".poster { animation: vanish 0.01s forwards; }"),
    )
    with tempfile.TemporaryDirectory(prefix="artboard-poster-visible-") as temp:
        for name, payload in payloads:
            path = Path(temp) / f"{name}.html"
            path.write_text(markup.replace("</style>", payload + "</style>", 1),
                            encoding="utf-8")
            checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
            if name == "hidden-keyframe-animation":
                if (checks.get("poster-static-no-animation") is not False
                        or checks.get("poster-cascade-controlled") is not False
                        or checks.get("canvas-fixed") is not False):
                    return False
                continue
            if (checks.get("poster-visible-in-canvas") is not False
                    or checks.get("poster-cascade-controlled") is not False
                    or checks.get("canvas-fixed") is not False):
                return False
            if name == "all-reset" and checks.get("no-css-all-reset") is not False:
                return False
    return True


def ancestor_visibility_and_layout_cascade_are_checked() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="CSS级联验证"),
                            font_vars="", sub=False, pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-root-band-cascade-") as temp:
        root = Path(temp)
        attacks = (
            ("body-rule", "<style>body { display:none; }</style>", "page-root-visible"),
            ("body-padding", "<style>body { padding-top:10000px; }</style>", "page-root-visible"),
            ("body-logical-padding", "<style>body { padding-block-start:10000px; }</style>",
             "page-root-visible"),
            ("body-inline", '<body style="display:none">', "page-root-visible"),
            ("body-pseudo-overlay", '<style>body::after{content:"";position:fixed;inset:0;background:#fff}</style>',
             "page-root-visible"),
            ("band-translate", "<style>.band { transform:translateX(10000px); }</style>",
             "layout-selector-cascade-controlled"),
        )
        for name, payload, expected_row in attacks:
            modified = (markup.replace("<body>", payload, 1) if name == "body-inline"
                        else markup.replace("</body>", payload + "</body>", 1))
            path = root / f"{name}.html"
            path.write_text(modified, encoding="utf-8")
            checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
            if checks.get(expected_row) is not False:
                return False
            if name.startswith("body-") and checks.get("poster-visible-in-canvas") is not False:
                return False
            if name == "band-translate" and checks.get("center-band-geometry") is not False:
                return False
        sibling_overlay = markup.replace(
            "</body>", '<div style="position:absolute;inset:0;z-index:999;background:#fff"></div></body>', 1)
        sibling_path = root / "sibling-overlay.html"
        sibling_path.write_text(sibling_overlay, encoding="utf-8")
        sibling_checks = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(sibling_path), gzh_cover.MAIN_W, "center-band", "")}
        if (sibling_checks.get("body-content-controlled") is not False
                or sibling_checks.get("poster-visible-in-canvas") is not False):
            return False
        wrapped = markup.replace("</style>", ".hide{display:none}</style>", 1)
        wrapped = wrapped.replace('<div class="poster', '<div class="hide"><div class="poster', 1)
        wrapped = wrapped.replace("</body>", "</div></body>", 1)
        wrapper_path = root / "hidden-wrapper.html"
        wrapper_path.write_text(wrapped, encoding="utf-8")
        wrapper_checks = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(wrapper_path), gzh_cover.MAIN_W, "center-band", "")}
        if (wrapper_checks.get("poster-parent-chain") is not False
                or wrapper_checks.get("poster-visible-in-canvas") is not False):
            return False
    return True


def thirteen_char_title_is_rejected() -> bool:
    title = "春" * 13
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title=title),
                            font_vars="", sub=False, pattern="none", fx="")
    emitted = []
    with tempfile.TemporaryDirectory(prefix="artboard-title-cap-") as temp:
        page = Path(temp) / "main.html"
        page.write_text(markup, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(page), gzh_cover.MAIN_W, "center-band", "")}
        legacy_html = gzh_cover.main_html(gzh_cover.MAIN_W, gzh_cover.MAIN_H, theme,
                                          title, "", "", "", "", "", "")
        legacy_path = Path(temp) / "legacy.html"
        legacy_path.write_text(legacy_html, encoding="utf-8")
        legacy_checks = {row["id"]: row["ok"] for row in
                         gzh_cover.check_one(str(legacy_path), gzh_cover.MAIN_W, "legacy", "")}
        project = Path(temp) / "new-project"
        args = type("Args", (), {"slug": str(project), "title": title, "force": False,
                                  "theme": "ink", "layout": "center-band", "image": "",
                                  "sub_title": ""})()
        legacy_project = Path(temp) / "new-legacy-project"
        legacy_args = type("Args", (), {"slug": str(legacy_project), "title": title,
                                         "force": False, "theme": "ink", "layout": "",
                                         "image": "", "sub_title": ""})()
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            rc = gzh_cover.cmd_new(args)
            legacy_rc = gzh_cover.cmd_new(legacy_args)
        return (checks.get("title-char-cap") is False
                and legacy_checks.get("title-char-cap") is False
                and rc == 1 and legacy_rc == 1 and len(emitted) == 2
                and all(item.get("error") == "TITLE_TOO_LONG" for item in emitted)
                and not project.exists() and not legacy_project.exists())


def literal_angle_bracket_title_counts_consistently() -> bool:
    title = "春" * 18 + "<x>"
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title=title),
                            font_vars="", sub=False, pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-title-literal-angle-") as temp:
        page = Path(temp) / "main.html"
        page.write_text(markup, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(page), gzh_cover.MAIN_W, "center-band", "")}
        project = Path(temp) / "new-project"
        args = type("Args", (), {"slug": str(project), "title": title, "force": False,
                                  "theme": "ink", "layout": "center-band", "image": "",
                                  "sub_title": ""})()
        emitted = []
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            rc = gzh_cover.cmd_new(args)
    return (len(layouts.plain(title)) == 21
            and len(layouts.plain("春" * 17 + "<x>")) == 20
            and checks.get("title-char-cap") is False
            and rc == 1 and emitted and emitted[-1].get("error") == "TITLE_TOO_LONG"
            and emitted[-1].get("length") == 21 and not project.exists())


def _test_png_pixel(gray: int) -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(name + payload) & 0xFFFFFFFF
        return (len(payload).to_bytes(4, "big") + name + payload
                + crc.to_bytes(4, "big"))

    return (bytes.fromhex("89504e470d0a1a0a")
            + chunk(b"IHDR", bytes.fromhex("00000001000000010804000000"))
            + chunk(b"IDAT", zlib.compress(bytes((0, gray, 255))))
            + chunk(b"IEND", b""))


def local_photo_is_required_and_preserved() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    with tempfile.TemporaryDirectory(prefix="artboard-plate-photo-") as temp:
        root = Path(temp)
        source = root / "source.png"
        source.write_bytes(_test_png_pixel(255))
        spec, error = gzh_cover._local_raster_spec(str(source))
        corrupt_png = root / "bad-crc.png"
        corrupt_png.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/iXcAAAAASUVORK5CYII="))
        _corrupt_spec, corrupt_png_error = gzh_cover._local_raster_spec(str(corrupt_png))
        fake_jpeg = root / "fake.jpg"
        fake_jpeg.write_bytes(b"\xff\xd8\xff\xd9")
        _jpeg_spec, fake_jpeg_error = gzh_cover._local_raster_spec(str(fake_jpeg))
        fake_webp = root / "fake.webp"
        fake_webp.write_bytes(b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00")
        _webp_spec, fake_webp_error = gzh_cover._local_raster_spec(str(fake_webp))
        unsupported = root / "not-an-image.txt"
        unsupported.write_text("not an image", encoding="utf-8")
        bad_spec, bad_image_error = gzh_cover._local_raster_spec(str(unsupported))
        src_dir = root / "project" / "src"
        src_dir.mkdir(parents=True)
        photo_ref, copy_error = gzh_cover._install_local_raster(str(src_dir), spec)
        data = layouts.make_data(title="春日漫游", sub="本地照片测试", image=photo_ref,
                                 sub_mode="flat")
        main = layouts.render("plate-page", theme, data, font_vars="", sub=False,
                              pattern="none", fx="halftone")
        sub = layouts.render("plate-page", theme,
                             dict(data, title="封面要点"), font_vars="", sub=True,
                             pattern="none", fx="halftone")
        main_path = _write_checked_page(src_dir, "index.html", main)
        sub_path = _write_checked_page(src_dir, "sub.html", sub)
        main_checks = {row["id"]: row["ok"] for row in
                       gzh_cover.check_one(str(main_path), gzh_cover.MAIN_W, "plate-page", "halftone")}
        sub_checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(sub_path), gzh_cover.SUB_W, "plate-page", "")}
        copied = src_dir / photo_ref
        before = copied.read_bytes()
        replacement = root / "replacement.png"
        replacement.write_bytes(_test_png_pixel(254))
        replacement_spec, replacement_error = gzh_cover._local_raster_spec(str(replacement))
        _ref, conflict = gzh_cover._install_local_raster(str(src_dir), replacement_spec)
        flat_has_photo = ("data-sub-mode=\"flat\"" in sub
                          and '<img class="plate-image"' in sub
                          and "[data-sub-mode=\"flat\"] .plate" in sub
                          and "display: block !important" in sub)
        preserved = conflict == "IMAGE_DEST_CONFLICT" and copied.read_bytes() == before
    try:
        layouts.render("plate-page", theme, layouts.make_data(title="无图"),
                       font_vars="", sub=False, pattern="none", fx="")
    except ValueError:
        missing_rejected = True
    else:
        missing_rejected = False
    emitted = []
    with tempfile.TemporaryDirectory(prefix="artboard-missing-photo-") as temp:
        project = Path(temp) / "new-project"
        args = type("Args", (), {"slug": str(project), "title": "本地照片",
                                  "force": False, "theme": "ink", "layout": "plate-page",
                                  "image": "", "sub_title": ""})()
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            rc = gzh_cover.cmd_new(args)
        cli_rejected = (rc == 1 and emitted and emitted[-1].get("error") == "IMAGE_REQUIRED"
                        and not project.exists())
    return (not error and not copy_error and bad_spec is None
            and _corrupt_spec is None and corrupt_png_error == "IMAGE_DECODE_FAILED"
            and _jpeg_spec is None and fake_jpeg_error == "IMAGE_DECODE_FAILED"
            and _webp_spec is None and fake_webp_error == "IMAGE_DECODE_FAILED"
            and bad_image_error == "IMAGE_FORMAT_UNSUPPORTED" and not replacement_error
            and main_checks.get("plate-page-photo") is True
            and sub_checks.get("plate-page-photo") is True and preserved
            and flat_has_photo and missing_rejected and cli_rejected)


def plate_page_meta_items_wrap_as_units() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    data = layouts.make_data(title="街区漫步", meta=["2026", "杭州", "Artboard", "周末特刊"],
                             image="images/plate-page-image.png", sub_mode="flat")
    html = layouts.render("plate-page", theme, data, font_vars="", sub=True,
                          pattern="none", fx="")
    return ("class=\"meta meta-inline\"" in html
            and html.count('class="meta-item"') == 4
            and ".meta-item { display: inline-block; white-space: nowrap; }" in html
            and ".meta-item + .meta-item::before" in html)


def css_policy_and_html_attributes_are_semantic() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="春日漫游"),
                            font_vars="", sub=False, pattern="none", fx="")
    escaped_css = r".x { position:f\69xed; height:100dvh; width:100vmin; " \
                  r"background-image:u\72l(file:///C:/private.png); }"
    hostile_css = markup.replace("</style>", escaped_css + "\n</style>", 1)
    resource_forms = (
        "<script src='https://example.invalid/a.js'></script>",
        "<script src=https://example.invalid/a.js></script>",
        "<script SRC='https://example.invalid/a.js'></script>",
        "<div style=\"background-image:url('https://example.invalid/a.png')\"></div>",
        "<style>@import url('https://example.invalid/a.css');</style>",
        '<style/>@import url("https://example.invalid/self-closing.css");</style>',
        '<link rel="stylesheet" href="data:text/css,%40import%20url%28https%3A%2F%2Fevil.example%2Fremote.css%29">',
        '<img src="data:image/svg+xml,%3Csvg%20onload%3Dalert(1)%3E">',
        "<img src='file:///C:/private.png'>",
        "<img src='ftp://example.invalid/private.png'>",
        '<img src="http&#10;s://example.invalid/obfuscated.png">',
        r'<img src="\\evil.example/tracking.png">',
        '<table background="https://example.invalid/bg.png"></table>',
        '<script>new Image().src="https://example.invalid/pixel.png";</script>',
        '<img src="x.png" onload="new Image().src=\'https://example.invalid/pixel.png\'">',
        '<style>.x{background-image:image-set("https://example.invalid/pixel.png" 1x);}</style>',
        '<object data="https://example.invalid/payload.html" type="text/html"></object>',
        '<meta HTTP-EQUIV="Refresh" content="0;url=https://example.invalid/">',
        '<svg><a href="#x"><animate attributeName="href" values="javascript:alert(1)" dur="1s" begin="click"/></a></svg>',
        '<base href="../"><script src="vendor/shaders/runtime.js"></script>',
        '<img src="../private.png">',
        '<div style="background:url(../private.png)"></div>',
        '<img src="//[bad">',
        '<div style="background:url(//[bad)"></div>',
    )
    viewport_units = (
        "vw", "vh", "vmin", "vmax", "vi", "vb",
        "svw", "svh", "svmin", "svmax", "svi", "svb",
        "lvw", "lvh", "lvmin", "lvmax", "lvi", "lvb",
        "dvw", "dvh", "dvmin", "dvmax", "dvi", "dvb",
    )
    with tempfile.TemporaryDirectory(prefix="artboard-css-policy-") as temp:
        root = Path(temp)
        css_path = root / "hostile-css.html"
        css_path.write_text(hostile_css, encoding="utf-8")
        css_checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(css_path), gzh_cover.MAIN_W, "center-band", "")}
        offline_checks = []
        executable_checks = []
        for index, resource in enumerate(resource_forms):
            path = root / f"external-{index}.html"
            path.write_text(markup.replace("</body>", resource + "</body>"), encoding="utf-8")
            checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
            offline_checks.append(checks.get("offline-only") is False)
            if "<script" in resource or "onload=" in resource or "<svg" in resource:
                executable_checks.append(checks.get("no-unreviewed-executable-code") is False)
        water_canvas = gzh_cover._shader_fx._canvas(
            "water", {"shapeSdfUrl": "https://example.invalid/shape.png"}, False)
        water_markup = markup.replace("</body>", water_canvas + "</body>", 1)
        water_path = root / "water-sdf.html"
        water_path.write_text(water_markup, encoding="utf-8")
        water_checks = {row["id"]: row["ok"] for row in
                        gzh_cover.check_one(str(water_path), gzh_cover.MAIN_W, "center-band", "water")}
        water_escape = gzh_cover._shader_fx._canvas(
            "water", {"shapeSdfUrl": "../private.png"}, False)
        water_escape_path = root / "water-relative-escape.html"
        water_escape_path.write_text(markup.replace("</body>", water_escape + "</body>", 1),
                                     encoding="utf-8")
        water_escape_checks = {row["id"]: row["ok"] for row in
                               gzh_cover.check_one(str(water_escape_path), gzh_cover.MAIN_W,
                                                   "center-band", "water")}
        unit_checks = []
        viewport_values = [f"100{unit}" for unit in viewport_units] + [".5vw", "1e2vw"]
        for index, value in enumerate(viewport_values):
            path = root / f"viewport-{index}.html"
            payload = markup.replace("</style>", f".x {{ width:{value}; }}\n</style>", 1)
            path.write_text(payload, encoding="utf-8")
            checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
            unit_checks.append(checks.get("no-viewport-units") is False)
        root_hidden_path = root / "hidden-root.html"
        root_hidden_path.write_text(
            markup.replace("</style>", "html,body{width:0;height:0;overflow:hidden}</style>", 1),
            encoding="utf-8")
        root_checks = {row["id"]: row["ok"] for row in
                       gzh_cover.check_one(str(root_hidden_path), gzh_cover.MAIN_W,
                                           "center-band", "")}
        nested_root_path = root / "nested-root.html"
        nested_root_path.write_text(
            markup.replace("</style>", "body { & { padding-top:250px !important; } }\n</style>", 1),
            encoding="utf-8")
        nested_root_checks = {row["id"]: row["ok"] for row in
                              gzh_cover.check_one(str(nested_root_path), gzh_cover.MAIN_W,
                                                  "center-band", "")}
        unsafe_safe = re.sub(r"(\.safe\s*\{[^}]*?)left\s*:\s*50%",
                             r"\1LEFT:0px", markup, count=1, flags=re.I)
        unsafe_safe_path = root / "unsafe-safe-anchor.html"
        unsafe_safe_path.write_text(unsafe_safe, encoding="utf-8")
        safe_checks = {row["id"]: row["ok"] for row in
                       gzh_cover.check_one(str(unsafe_safe_path), gzh_cover.MAIN_W,
                                           "center-band", "")}
    return (css_checks.get("no-fixed-position") is False
            and css_checks.get("no-viewport-units") is False
            and css_checks.get("offline-only") is False
            and all(offline_checks) and all(executable_checks) and all(unit_checks)
             and water_checks.get("offline-only") is False
             and water_escape_checks.get("resources-confined-to-src-or-skill-assets") is False
             and water_escape_checks.get("offline-only") is False
             and root_checks.get("page-root-visible") is False
              and nested_root_checks.get("no-css-nesting") is False
             and safe_checks.get("safe-zone-inside") is False)


def shader_canvas_requires_vendor_bootstrap() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="需要启动器"),
                            font_vars="", sub=False, pattern="none", fx="halftone")
    markup = markup.replace('<script src="vendor/shaders/runtime.js"></script>', "", 1)
    with tempfile.TemporaryDirectory(prefix="artboard-shader-runtime-required-") as temp:
        path = Path(temp) / "missing-runtime.html"
        path.write_text(markup, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(path), gzh_cover.MAIN_W,
                                      "center-band", "halftone")}
    return checks.get("shader-runtime-scripts-present") is False


def offline_audit_rejects_unreviewed_local_stylesheets() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="本地样式审查"),
                            font_vars="", sub=False, pattern="none", fx="")
    payloads = (
        '<link rel="stylesheet" href="theme.css">',
        '<style>@import "theme.css";</style>',
        r'<style>@\69mport "theme.css";</style>',
    )
    with tempfile.TemporaryDirectory(prefix="artboard-unreviewed-stylesheet-") as temp:
        outcomes = []
        for index, payload in enumerate(payloads):
            path = Path(temp) / f"linked-style-{index}.html"
            path.write_text(markup.replace("</body>", payload + "</body>"), encoding="utf-8")
            checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
            outcomes.append(checks.get("inline-css-only") is False)
    return all(outcomes)


def quoted_gt_shader_canvas_is_detected_semantically() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="安全审查"),
                            font_vars="", sub=False, pattern="none", fx="halftone")
    original = layouts.fx_canvas("halftone", theme)
    hostile = ('<canvas data-fx="halftone > inert" class="ab-shader"></canvas>'
               '<canvas data-webgpu-required="true"></canvas>')
    if original not in markup:
        return False
    markup = markup.replace(original, hostile, 1)
    with tempfile.TemporaryDirectory(prefix="artboard-semantic-shader-canvas-") as temp:
        path = Path(temp) / "shader.html"
        path.write_text(markup, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "halftone")}
    return (gzh_cover._html_has_shader_canvas(markup)
            and not gzh_cover._html_has_webgpu_marker(markup)
            and checks.get("webgpu-required-marker") is False)


def shader_audit_matches_runtime_selector() -> bool:
    alias = ('<canvas class="shader-canvas" data-fx="halftone" '
             'data-webgpu-required="true"></canvas>')
    missing_fx = '<canvas class="ab-shader" data-webgpu-required="true"></canvas>'
    actual = '<canvas class="ab-shader" data-fx="halftone"></canvas>'
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    generated = layouts.render("center-band", theme, layouts.make_data(title="本地 shader 允许名单"),
                               font_vars="", sub=False, pattern="none", fx="halftone")
    audit = gzh_cover._html_audit(generated)
    with tempfile.TemporaryDirectory(prefix="artboard-local-shader-scripts-") as temp:
        page = Path(temp) / "shader.html"
        page.write_text(generated, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(page), gzh_cover.MAIN_W, "center-band", "halftone")}
    return (not gzh_cover._html_has_shader_canvas(alias)
            and not gzh_cover._html_has_webgpu_marker(alias)
            and not gzh_cover._html_has_shader_canvas(missing_fx)
            and gzh_cover._html_has_shader_canvas(actual)
            and audit.unreviewed_code == [] and audit.external_urls == []
            and checks.get("offline-only") is True
            and checks.get("no-unreviewed-executable-code") is True)


def emoji_title_width_is_conservative() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    data = layouts.make_data(title="😀" * 10)
    markup = layouts.render("center-band", theme, data, font_vars="", sub=False,
                            pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-emoji-title-width-") as temp:
        path = Path(temp) / "emoji-title.html"
        path.write_text(markup, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
    return (layouts._em("😀" * 10, 0.02) >= 14.7
            and checks.get("title-char-cap") is True
            and checks.get("title-width-fit") is True)


def joined_emoji_uses_one_visible_title_unit() -> bool:
    family = "👨‍👩‍👧‍👦"
    source = family + "山川日月星辰"
    clusters = layouts.grapheme_clusters(source)
    rows = layouts.break_lines(source, 2, 4).split("<br>")
    boundaries = set()
    cursor = 0
    for cluster in clusters:
        cursor += len(cluster)
        boundaries.add(cursor)
    cuts = []
    cursor = 0
    for row in rows[:-1]:
        cursor += len(row)
        cuts.append(cursor)

    _theme_name, theme = gzh_cover._resolve_theme("ink")
    rendered = layouts.render("center-band", theme,
                              layouts.make_data(title=family * 3),
                              font_vars="", sub=False, pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-family-emoji-title-") as temp:
        page = Path(temp) / "family.html"
        page.write_text(rendered, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(page), gzh_cover.MAIN_W, "center-band", "")}
        too_long_project = Path(temp) / "too-many-families"
        emitted = []
        args = type("Args", (), {
            "slug": str(too_long_project), "title": family * 21,
            "sub_title": "", "force": False, "theme": "ink",
            "layout": "center-band", "image": "",
        })()
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            too_long_rc = gzh_cover.cmd_new(args)
    return (len(clusters) == 7 and len(rows) == 2
            and all(cut in boundaries for cut in cuts)
            and layouts.visible_len(family * 3) == 3
            and layouts._em(family * 3) == 4.35
            and checks.get("title-char-cap") is True
            and checks.get("title-width-fit") is True
            and too_long_rc == 1 and emitted
            and emitted[-1].get("error") == "TITLE_TOO_LONG"
            and emitted[-1].get("length") == 21
            and not too_long_project.exists())


def stray_zwj_does_not_merge_plain_title_text() -> bool:
    title = "A\u200dB" * 10 + "A"
    clusters = layouts.grapheme_clusters(title)
    emitted = []
    with tempfile.TemporaryDirectory(prefix="artboard-stray-zwj-title-") as temp:
        project = Path(temp) / "too-many-visible-letters"
        args = type("Args", (), {
            "slug": str(project), "title": title, "sub_title": "", "force": False,
            "theme": "ink", "layout": "center-band", "image": "",
        })()
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            rc = gzh_cover.cmd_new(args)
    return (len(clusters) == 21 and layouts.visible_len(title) == 21
            and rc == 1 and emitted
            and emitted[-1].get("error") == "TITLE_TOO_LONG"
            and emitted[-1].get("length") == 21 and not project.exists())


def hangul_jamo_syllables_count_and_break_as_one_grapheme() -> bool:
    decomposed = "\u1100\u1161"
    decomposed_with_final = decomposed + "\u11a8"
    title = decomposed * 11
    clusters = layouts.grapheme_clusters(title)
    lvt_clusters = layouts.grapheme_clusters(decomposed_with_final)
    wrapped = layouts.break_lines(title, max_lines=2, max_chars=8)
    if not wrapped or "\u1100<br>\u1161" in wrapped:
        return False
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title=title),
                            font_vars="", sub=False, pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-hangul-jamo-title-") as temp:
        page = Path(temp) / "hangul.html"
        page.write_text(markup, encoding="utf-8")
        checks = {row["id"]: row["ok"] for row in
                  gzh_cover.check_one(str(page), gzh_cover.MAIN_W, "center-band", "")}
    return (len(clusters) == 11 and len(lvt_clusters) == 1
            and layouts.visible_len(title) == 11
            and layouts.visible_len("가" * 11) == 11
            and layouts._em(title) == layouts._em("가" * 11) == 11.0
            and checks.get("title-char-cap") is True
            and checks.get("title-width-fit") is True)


def malformed_manifest_roots_fail_closed() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-manifest-root-") as temp:
        payloads = ("[]", "null", "{", '{"layout":"unsupported-layout"}',
                    '{"layout":["center-band"]}', '{"main_fx":{}}',
                    '{"main_fx":[]}', '{"fx":[]}', '{"fx":"unknown-effect"}',
                    '{"sub_fx":"unknown-effect"}')
        for index, raw in enumerate(payloads):
            project = Path(temp) / f"project-{index}"
            src = project / "src"
            src.mkdir(parents=True)
            (src / "index.html").write_text("<html></html>", encoding="utf-8")
            (project / "project.json").write_text(raw, encoding="utf-8")

            check_emitted = []
            with patch.object(gzh_cover, "emit", side_effect=check_emitted.append):
                check_rc = gzh_cover.cmd_check(type("Args", (), {"project": str(project)})())
            if (check_rc != 1 or not check_emitted
                    or check_emitted[-1].get("error") != "PROJECT_MANIFEST_INVALID"):
                return False

            for only in ("main", "merged"):
                export_emitted = []
                args = type("Args", (), {
                    "project": str(project), "only": only,
                    "outdir": str(project / "export"), "scale": 1,
                    "bg": "#f6f7f9",
                })()
                with patch.object(gzh_cover, "emit", side_effect=export_emitted.append):
                    export_rc = gzh_cover.cmd_export(args)
                if (export_rc != 1 or not export_emitted
                        or export_emitted[-1].get("error") != "PROJECT_MANIFEST_INVALID"
                        or (project / "export").exists()):
                    return False
    return True


def canvas_fx_slug_must_match_manifest() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="FX slug gate"),
                            font_vars="", sub=False, pattern="none", fx="aurora")
    with tempfile.TemporaryDirectory(prefix="artboard-fx-slug-match-") as temp:
        path = Path(temp) / "main.html"
        path.write_text(markup, encoding="utf-8")
        expected = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(path), gzh_cover.MAIN_W, "center-band", "aurora")}
        mismatched = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(path), gzh_cover.MAIN_W, "center-band", "halftone")}
        disabled = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(path), gzh_cover.MAIN_W, "center-band", "")}
    return (expected.get("webgpu-required-marker") is True
            and mismatched.get("webgpu-required-marker") is False
            and disabled.get("webgpu-required-marker") is False)


def flat_sub_mode_and_scale_are_real() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    same_data = layouts.make_data(title="春日漫游", sub="内容观察", sub_mode="same")
    flat_data = dict(same_data, sub_mode="flat")
    same = layouts.render("center-band", theme, same_data, font_vars="", sub=True,
                          pattern="dots", fx="")
    flat = layouts.render("center-band", theme, flat_data, font_vars="", sub=True,
                          pattern="dots", fx="")
    shader_same = layouts.render("center-band", theme, same_data, font_vars="", sub=True,
                                 pattern="auto", fx="halftone")
    shader_flat = layouts.render("center-band", theme, flat_data, font_vars="", sub=True,
                                 pattern="auto", fx="halftone")
    main_size = layouts._RENDERERS["center-band"](theme, same_data, False)[1]
    same_size = int(re.search(r"--t-size: (\d+)px", same).group(1))
    flat_size = int(re.search(r"--t-size: (\d+)px", flat).group(1))
    # 方图大字:4 字按 2+2 排,块高必须吃掉画布 70% 以上,否则手机上认不出
    sub_rows = same.count("<br>", 0, same.find("</h1>")) + 1
    block_h_ratio = same_size * sub_rows * 1.12 / layouts.SUB_CANVAS
    with tempfile.TemporaryDirectory(prefix="artboard-flat-manifest-") as temp:
        project = Path(temp)
        src_dir = project / "src"
        src_dir.mkdir()
        main_html = layouts.render("center-band", theme, same_data, font_vars="",
                                   sub=False, pattern="none", fx="halftone")
        flat_html = layouts.render("center-band", theme, flat_data, font_vars="",
                                   sub=True, pattern="none", fx="halftone")
        (src_dir / "index.html").write_text(main_html, encoding="utf-8")
        (src_dir / "sub.html").write_text(flat_html, encoding="utf-8")
        local_vendor = src_dir / "vendor" / "shaders"
        (local_vendor / "LICENSES").mkdir(parents=True)
        trusted_vendor = Path(gzh_cover.SKILL_DIR) / "vendor" / "shaders"
        for rel in ("runtime.js", "upstream.js", "LICENSES/shaders-LICENSE"):
            (local_vendor / rel).write_bytes((trusted_vendor / rel).read_bytes())
        (project / "project.json").write_text(json.dumps({
            "layout": "center-band", "fx": "halftone",
            "main_fx": "halftone", "sub_fx": "",
        }), encoding="utf-8")
        emitted = []
        with patch.object(gzh_cover, "emit", side_effect=emitted.append):
            manifest_rc = gzh_cover.cmd_check(type("Args", (), {"project": str(project)})())
        manifest_ok = manifest_rc == 0 and emitted and emitted[-1].get("ok") is True
        export_emitted = []
        with patch.object(gzh_cover, "emit", side_effect=export_emitted.append), \
                patch.object(gzh_cover, "check_kiln", return_value=False):
            export_rc = gzh_cover.cmd_export(type("Args", (), {
                "project": str(project), "only": "", "outdir": str(project / "export"),
                "scale": 1, "bg": "#f6f7f9",
            })())
        export_ok = (export_rc == 1 and export_emitted
                     and export_emitted[-1].get("error") == "KILN_NOT_FOUND"
                     and not (project / "export").exists())
    return (manifest_ok and export_ok and "data-pattern=\"dots\"" in same
            and 'data-fx=""' in same
            and "data-pattern=\"none\"" in flat and 'data-fx=""' in flat
            and 'data-fx="halftone"' in shader_same and '<canvas' in shader_same
            and 'data-fx=""' in shader_flat and '<canvas' not in shader_flat
            and "background-image: none !important" in flat
            and flat_size == same_size and sub_rows >= 2 and block_h_ratio >= 0.70
            and "[data-role=\"decor\"] { display: none !important; }" in flat)


def every_layout_passes_static_geometry() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    with tempfile.TemporaryDirectory(prefix="artboard-layout-matrix-") as temp:
        src_dir = Path(temp) / "src"
        src_dir.mkdir()
        photo = src_dir / "images" / "plate-page-image.png"
        photo.parent.mkdir()
        photo.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="))
        for layout in layouts.LAYOUT_SLUGS:
            data = layouts.make_data(title="海风漫游", sub="内容观察", kicker="栏目观察",
                                     footer="Artboard", meta=["上海", "2025"],
                                     image="images/plate-page-image.png" if layout == "plate-page" else None)
            main_html = layouts.render(layout, theme, data, font_vars="", sub=False,
                                       pattern="none", fx="none")
            sub_html = layouts.render(layout, theme, dict(data, title="封面要点"), font_vars="",
                                      sub=True, pattern="none", fx="none")
            main_path = _write_checked_page(src_dir, f"{layout}-main.html", main_html)
            sub_path = _write_checked_page(src_dir, f"{layout}-sub.html", sub_html)
            main_rows = gzh_cover.check_one(str(main_path), gzh_cover.MAIN_W, layout, "")
            sub_rows = gzh_cover.check_one(str(sub_path), gzh_cover.SUB_W, layout, "")
            if any(not row["ok"] for row in main_rows + sub_rows):
                return False
    return True


def poster_pseudo_title_and_animated_resources_are_rejected() -> bool:
    _theme_name, theme = gzh_cover._resolve_theme("ink")
    markup = layouts.render("center-band", theme, layouts.make_data(title="标题必须可见"),
                            font_vars="", sub=False, pattern="none", fx="")
    with tempfile.TemporaryDirectory(prefix="artboard-static-cover-policy-") as temp:
        root = Path(temp)
        gif = root / "two-frame.gif"
        try:
            from PIL import Image
            Image.new("RGB", (2, 2), "red").save(
                gif, save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")],
                duration=50, loop=0)
        except ImportError:
            return False
        valid_png = root / "valid.png"
        truncated_png = root / "truncated.png"
        Image.new("RGB", (16, 16), "green").save(valid_png, format="PNG")
        truncated_png.write_bytes(valid_png.read_bytes()[:-20])
        (root / "fake.woff").write_bytes(b"not a raster image")
        attacks = (
            ("poster-before-overlay", ".poster::before{content:\"\";position:absolute;inset:0;background:#fff;z-index:999;}",
             "poster-pseudo-overlay-controlled"),
            ("poster-after-overlay", ".poster::after{z-index:999;}",
             "poster-pseudo-overlay-controlled"),
            ("title-display-none", ".t{display:none!important;}", "title-visible"),
            ("title-tag-zero-size", "h1{font-size:0;}", "title-visible"),
            ("safe-ancestor-pseudo-overlay", ".safe::before{content:\"\";position:absolute;inset:0;background:#fff;z-index:999;}",
             "title-pseudo-controlled"),
            ("title-pseudo-overlay", ".t::before{content:open-quote;position:absolute;inset:0;background:#fff;z-index:999;}",
             "title-pseudo-controlled"),
            ("safe-ancestor-opacity", ".safe{opacity:0}", "title-visible"),
            ("title-opacity-from-css-variable", ":root{--hide:0}.t{opacity:var(--hide)}", "title-visible"),
            ("title-unresolved-css-variable-fails-closed", ".t{opacity:var(--missing)}", "title-visible"),
            ("generic-div-pseudo-overlay", "div::before{content:\"\";position:absolute;inset:0;background:#fff;z-index:9;}", "title-pseudo-controlled"),
            ("title-low-opacity", ".t{opacity:0.0001!important;}", "title-visible"),
            ("title-tiny-font-size", ".t{font-size:0.0001px!important;}", "title-visible"),
            ("title-near-transparent-rgba", ".t{color:rgba(10,20,30,0.0001)!important;}", "title-visible"),
            ("title-near-zero-scale", ".t{transform:scale(0.0001)!important;}", "title-visible"),
            ("video-media", "<video src=clip.mp4></video>", "static-media-only"),
            ("marquee-media", "<marquee>moving text</marquee>", "static-media-only"),
            ("animated-image", '<img src="two-frame.gif">', "static-image-resources"),
            ("animated-image-alias", '<image src="two-frame.gif">', "static-image-resources"),
            ("missing-image", '<img src="missing.png">', "static-image-resources"),
            ("truncated-image", '<img src="truncated.png">', "static-image-resources"),
            ("mailto-image", '<img src="mailto:person@example.com">', "static-image-resources"),
            ("tel-image", '<img src="tel:1234567">', "static-image-resources"),
            ("missing-css-background", "<style>.poster{background-image:url(missing.png)}</style>",
             "static-image-resources"),
            ("css-font-as-image", "<style>.poster{background-image:url(fake.woff)}</style>",
             "static-image-resources"),
            ("missing-font-face-resource", "@font-face{font-family:Missing;src:url(fonts/not-there.woff2)}",
             "font-face-resources-exist"),
        )
        for index, (name, payload, expected) in enumerate(attacks):
            if name in {"video-media", "marquee-media", "animated-image",
                        "animated-image-alias", "missing-image", "truncated-image",
                        "mailto-image", "tel-image"}:
                modified = markup.replace("</body>", payload + "</body>", 1)
            else:
                modified = markup.replace("</style>", payload + "</style>", 1)
            path = root / f"{index}-{name}.html"
            path.write_text(modified, encoding="utf-8")
            checks = {row["id"]: row["ok"] for row in
                      gzh_cover.check_one(str(path), gzh_cover.MAIN_W, "center-band", "")}
            if checks.get(expected) is not False:
                return False
        safe_ancestor_hidden = markup.replace(
            'class="safe"', 'class="safe" style="opacity:0"', 1)
        ancestor_path = root / "safe-ancestor-inline-hidden.html"
        ancestor_path.write_text(safe_ancestor_hidden, encoding="utf-8")
        ancestor_checks = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(ancestor_path), gzh_cover.MAIN_W, "center-band", "")}
        if ancestor_checks.get("title-visible") is not False:
            return False
        encoded = base64.b64encode(gif.read_bytes()).decode("ascii")
        data_css = markup.replace(
            "</style>",
            f".poster{{background-image:url(data:image/gif;base64,{encoded})}}</style>", 1)
        data_path = root / "animated-data-css.html"
        data_path.write_text(data_css, encoding="utf-8")
        data_checks = {row["id"]: row["ok"] for row in gzh_cover.check_one(
            str(data_path), gzh_cover.MAIN_W, "center-band", "")}
        return data_checks.get("static-image-resources") is False


def main() -> int:
    cases = [
        ("explicit-pattern-beats-auto-fx", layouts.resolve_visual_layers(
            "center-band", "dots", "auto") == ("dots", "")),
        ("explicit-shader-beats-auto-pattern", layouts.resolve_visual_layers(
            "center-band", "auto", "halftone") == ("none", "halftone")),
        ("auto-prefers-layout-shader", layouts.resolve_visual_layers(
            "center-band", "auto", "auto") == ("none", "halftone")),
        ("paper-layout-keeps-css-grain", layouts.resolve_visual_layers(
            "kraft-note", "auto", "auto") == ("grain", "")),
        ("accent-auto-is-valid", "auto" in layouts.ACCENT_TONES),
        ("latin-word-spaces-preserved", layouts.break_lines("AI for Good", 1) == "AI for Good"),
        ("explicit-br-variants-preserved",
         layouts.break_lines("AI<br />for Good", 2, 12) == "AI<br>for Good"),
        ("main-title-minimum-and-width-are-enforced",
         main_title_minimum_and_width_are_enforced()),
        ("bad-title-fails-before-kiln-or-output-directory",
         invalid_title_fails_before_kiln()),
        ("exact-canvas-and-vertical-safe-zone-enforced",
         canvas_and_vertical_safety_are_enforced()),
        ("relative-webgpu-export-paths-resolve-from-caller",
         relative_webgpu_paths_resolve_from_caller()),
        ("poster-cascade-cannot-reset-hide-or-leave-viewport",
         poster_cascade_cannot_reset_hide_or_leave_viewport()),
        ("poster-pseudo-title-visibility-and-animation-resources-are-checked",
         poster_pseudo_title_and_animated_resources_are_rejected()),
        ("ancestor-visibility-and-layout-css-cascade-are-checked",
         ancestor_visibility_and_layout_cascade_are_checked()),
        ("thirteen-character-title-rejected",
         thirteen_char_title_is_rejected()),
        ("literal-angle-brackets-count-as-visible-title-text",
         literal_angle_bracket_title_counts_consistently()),
        ("plate-page-local-photo-required-and-preserved",
         local_photo_is_required_and_preserved()),
        ("plate-page-sub-metadata-wraps-whole-items",
         plate_page_meta_items_wrap_as_units()),
        ("plate-page-layout-help-marks-metadata-optional",
         "元数据可选" in layouts.layout_spec("plate-page")["fits"]),
        ("css-policy-and-offline-resource-checks-parse-html-syntax",
         css_policy_and_html_attributes_are_semantic()),
        ("offline-audit-rejects-unreviewed-local-stylesheets",
         offline_audit_rejects_unreviewed_local_stylesheets()),
        ("quoted-angle-bracket-canvas-attributes-use-html-parser",
         quoted_gt_shader_canvas_is_detected_semantically()),
        ("shader-canvas-requires-runtime-bootstrap-script",
         shader_canvas_requires_vendor_bootstrap()),
        ("shader-canvas-audit-matches-runtime-selector",
         shader_audit_matches_runtime_selector()),
        ("invalid-manifest-and-fx-values-fail-closed-in-check-and-export",
         malformed_manifest_roots_fail_closed()),
        ("shader-canvas-fx-slug-matches-manifest", canvas_fx_slug_must_match_manifest()),
        ("emoji-title-width-estimate-prevents-overflow",
         emoji_title_width_is_conservative()),
        ("joined-emoji-count-and-wrap-use-grapheme-clusters",
         joined_emoji_uses_one_visible_title_unit()),
        ("stray-zwj-does-not-merge-plain-title-text",
         stray_zwj_does_not_merge_plain_title_text()),
        ("hangul-lvt-jamo-count-and-break-as-one-grapheme",
         hangul_jamo_syllables_count_and_break_as_one_grapheme()),
        ("flat-sub-mode-and-independent-sub-scale-are-real",
         flat_sub_mode_and_scale_are_real()),
        ("all-layouts-pass-static-geometry",
         every_layout_passes_static_geometry()),
    ]
    try:
        layouts.resolve_visual_layers("center-band", "dots", "halftone")
    except ValueError:
        cases.append(("reject-two-explicit-backgrounds", True))
    else:
        cases.append(("reject-two-explicit-backgrounds", False))
    report = {"ok": all(ok for _, ok in cases), "count": len(cases),
              "passed": sum(ok for _, ok in cases),
              "checks": [{"id": name, "ok": ok} for name, ok in cases]}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
