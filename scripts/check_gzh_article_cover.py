#!/usr/bin/env python3
"""Regression checks for article-to-cover layout and image forwarding."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import gzh_article


def _convert(tmp: Path, image: Path | None, layout: str = "plate-page"):
    source = tmp / "story.md"
    output = tmp / "story.html"
    source.write_text("# Article cover integration\n\nBody text.\n", encoding="utf-8")
    argv = ["gzh_article.py", "convert", str(source), "--out", str(output),
            "--cover-layout", layout, "--cover-fx", "none"]
    if image is not None:
        argv += ["--cover-image", str(image)]
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        cmd = list(command)
        commands.append(cmd)
        if len(cmd) < 3:
            raise AssertionError(f"unexpected cover command: {cmd}")
        if cmd[2] == "new":
            payload = {"ok": True, "project": cmd[3]}
        elif cmd[2] == "check":
            payload = {"ok": True, "coverage": {"main": 1, "sub": 1}, "reports": []}
        elif cmd[2] == "export":
            payload = {"ok": True, "exports": [{"output": str(tmp / "cover.png")}]}  # mocked export output
        else:
            raise AssertionError(f"unexpected cover subcommand: {cmd[2]}")
        return subprocess.CompletedProcess(
            cmd, 0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")

    def fake_tree(command, timeout=300, **_kwargs):
        cmd = list(command)
        commands.append(cmd)
        payload = {"ok": True, "exports": [{"output": str(tmp / "cover.png")}]}
        return gzh_article._proc.Result(0, json.dumps(payload), "", False, cmd, 0.01)

    stdout = io.StringIO()
    with patch.object(sys, "argv", argv), patch("subprocess.run", side_effect=fake_run), \
            patch.object(gzh_article._proc, "run", side_effect=fake_tree):
        with contextlib.redirect_stdout(stdout):
            rc = gzh_article.main()
    return rc, json.loads(stdout.getvalue()), commands


def plate_page_image_reaches_cover_cli() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-article-cover-image-") as temp:
        root = Path(temp)
        image = root / "cover.png"
        image.write_bytes(b"fixture; the cover subprocess is mocked")
        rc, payload, commands = _convert(root, image)
        new_commands = [cmd for cmd in commands if len(cmd) > 2 and cmd[2] == "new"]
        if len(new_commands) != 1:
            return False
        command = new_commands[0]
        image_index = command.index("--image") if "--image" in command else -1
        return (rc == 0 and payload.get("ok") is True
                and payload.get("cover", {}).get("layout") == "plate-page"
                and image_index >= 0 and command[image_index + 1] == str(image.resolve()))


def plate_page_without_image_fails_before_cover_cli() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-article-cover-required-") as temp:
        root = Path(temp)
        rc, payload, commands = _convert(root, None)
        return (rc == 1 and payload.get("cover_error") == "COVER_IMAGE_REQUIRED"
                and not commands and (root / "story.html").is_file())


def missing_or_wrong_layout_image_fails_closed() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-article-cover-invalid-") as temp:
        root = Path(temp)
        missing = root / "missing.png"
        rc_missing, payload_missing, commands_missing = _convert(root, missing)
        existing = root / "cover.png"
        existing.write_bytes(b"fixture")
        rc_conflict, payload_conflict, commands_conflict = _convert(
            root, existing, layout="center-band")
        return (rc_missing == 1
                and payload_missing.get("cover_error") == "COVER_IMAGE_NOT_FOUND"
                and not commands_missing
                and rc_conflict == 1
                and payload_conflict.get("cover_error") == "COVER_IMAGE_LAYOUT_CONFLICT"
                and not commands_conflict)


def demo_uses_a_short_cover_headline() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-demo-cover-title-") as temp:
        root = Path(temp)
        commands: list[list[str]] = []

        def fake_run(command, **_kwargs):
            cmd = list(command)
            commands.append(cmd)
            if len(cmd) < 3:
                raise AssertionError(f"unexpected cover command: {cmd}")
            if cmd[2] == "new":
                payload = {"ok": True, "project": str(root / "cover-project")}
            elif cmd[2] == "check":
                payload = {"ok": True, "coverage": {"main": 1, "sub": 1}, "reports": []}
            elif cmd[2] == "export":
                payload = {"ok": True, "exports": [
                    {"output": str(root / "cover.png")}]}
            else:
                raise AssertionError(f"unexpected cover subcommand: {cmd[2]}")
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")

        def fake_tree(command, timeout=300, **_kwargs):
            cmd = list(command)
            commands.append(cmd)
            payload = {"ok": True, "exports": [{"output": str(root / "cover.png")}]}
            return gzh_article._proc.Result(0, json.dumps(payload), "", False, cmd, 0.01)

        stdout = io.StringIO()
        args = argparse.Namespace(outdir=str(root), theme="ink")
        with patch("subprocess.run", side_effect=fake_run), \
                patch.object(gzh_article._proc, "run", side_effect=fake_tree):
            with contextlib.redirect_stdout(stdout):
                rc = gzh_article.cmd_demo(args)
        new_commands = [cmd for cmd in commands if len(cmd) > 2 and cmd[2] == "new"]
        if len(new_commands) != 1:
            return False
        command = new_commands[0]
        title_index = command.index("--title") if "--title" in command else -1
        return (rc == 0 and title_index >= 0
                and command[title_index + 1] == "双封面指南")


def article_cover_timeout_uses_process_tree_runner() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-article-cover-timeout-") as temp:
        root = Path(temp)
        args = argparse.Namespace(
            input=str(root / "story.md"), title="", cover_title="", slug="story",
            theme="ink", cover_layout="center-band", cover_sub="", cover_fx="none",
            cover_image="", cover_kicker="", cover_sub_title="", cover_sub_sub="",
            cover_num="", outdir="")
        direct_calls: list[list[str]] = []
        tree_calls: list[tuple[list[str], float]] = []

        def fake_direct(command, **_kwargs):
            cmd = list(command)
            direct_calls.append(cmd)
            payload = ({"ok": True, "project": str(root / "project")} if cmd[2] == "new"
                       else {"ok": True, "coverage": "complete", "reports": []})
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps(payload), stderr="")

        def fake_tree(command, timeout=0, **_kwargs):
            cmd = list(command)
            tree_calls.append((cmd, timeout))
            return gzh_article._proc.Result(-9, "", "", True, cmd, float(timeout))

        with patch("subprocess.run", side_effect=fake_direct), \
                patch.object(gzh_article._proc, "run", side_effect=fake_tree):
            result = gzh_article._make_covers(args, "# Story\n", "ink")
        return (result.get("error") == "COVER_EXPORT_TIMEOUT"
                and len(tree_calls) == 1 and tree_calls[0][1] == 300
                and tree_calls[0][0][2] == "export"
                and [cmd[2] for cmd in direct_calls] == ["new", "check"])


def existing_cover_project_is_not_overwritten() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-existing-cover-protection-") as temp:
        root = Path(temp)
        project = root / "same-slug"
        src = project / "src"
        src.mkdir(parents=True)
        original_html = '<html><body><h1>USER_KEEP_ME</h1></body></html>'
        original_manifest = '{"layout":"legacy","user":"keep"}'
        (src / "index.html").write_text(original_html, encoding="utf-8")
        (project / "project.json").write_text(original_manifest, encoding="utf-8")
        args = argparse.Namespace(
            input=str(root / "same-slug.md"), slug=str(project), title="New article",
            cover_layout="center-band", cover_sub="", cover_image="", cover_fx="none",
            cover_title="New article", cover_kicker="", cover_sub_title="",
            cover_sub_sub="", cover_num="")
        result = gzh_article._make_covers(args, "# New article\n", "ink")
        return (result.get("ok") is False and result.get("error") == "COVER_NEW_FAILED"
                and (src / "index.html").read_text(encoding="utf-8") == original_html
                and (project / "project.json").read_text(encoding="utf-8") == original_manifest)


def auto_layout_fallback_reuses_only_its_own_created_project() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-article-auto-layout-fallback-") as temp:
        root = Path(temp)
        args = argparse.Namespace(
            input=str(root / "story.md"), title="故事标题", cover_title="", slug="story",
            theme="ink", cover_layout="auto", cover_sub="副题", cover_fx="none",
            cover_image="", cover_kicker="", cover_sub_title="", cover_sub_sub="",
            cover_num="", outdir="")
        new_commands: list[list[str]] = []
        check_count = 0

        def fake_direct(command, **_kwargs):
            nonlocal check_count
            cmd = list(command)
            if cmd[2] == "new":
                new_commands.append(cmd)
                payload = {"ok": True, "project": str(root / "story")}
            elif cmd[2] == "check":
                check_count += 1
                payload = ({"ok": False, "failed": [{"id": "title-row-cap",
                                                       "detail": "test fit failure"}]}
                           if check_count == 1 else
                           {"ok": True, "coverage": "complete", "reports": []})
            else:
                raise AssertionError(f"unexpected cover subcommand {cmd[2]}")
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")

        def fake_export(command, timeout=0, **_kwargs):
            cmd = list(command)
            payload = {"ok": True, "exports": [{"output": str(root / "cover.png")}]}
            return gzh_article._proc.Result(0, json.dumps(payload), "", False, cmd, 0.01)

        with patch("subprocess.run", side_effect=fake_direct), \
                patch.object(gzh_article._proc, "run", side_effect=fake_export):
            result = gzh_article._make_covers(args, "# Story\n", "ink")
        return (result.get("ok") is True and result.get("layout") == "center-band"
                and len(new_commands) == 2
                and "--force" not in new_commands[0]
                and "--force" in new_commands[1]
                and new_commands[0][new_commands[0].index("--layout") + 1] == "band-editorial"
                and new_commands[1][new_commands[1].index("--layout") + 1] == "center-band")


def long_article_name_preview_is_bounded() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-long-article-preview-") as temp:
        root = Path(temp)
        source = root / "story.md"
        output = root / ("a" * 240 + ".html")
        source.write_text("# Long article output\n\nBody.\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(Path(gzh_article.__file__)), "convert", str(source),
             "--out", str(output), "--preview", "--no-cover"],
            cwd=Path(gzh_article.__file__).resolve().parent.parent,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        payload = json.loads(lines[-1]) if lines else {}
        preview = Path(payload.get("preview_copy", "")) if payload.get("preview_copy") else None
        return (result.returncode == 0 and output.is_file() and preview is not None
                and preview.is_file() and gzh_article._utf16_units(preview.name) <= 255
                and preview.parent == output.parent)


def markdown_attributes_are_escaped_and_checked() -> bool:
    renderer = gzh_article.Inline(gzh_article.THEMES["ink"])
    source = ("# Security test\n\n"
              "![x](missing.png\"onerror=\"location='https://bad.example/pixel')\n\n"
              "[go](x\"onmouseover=\"location='https://bad.example/pixel')\n")
    markup = gzh_article.render_article(source, "ink")
    audit = gzh_article._CompatAttributeAudit()
    audit.feed(markup)
    audit.close()
    with tempfile.TemporaryDirectory(prefix="artboard-article-attr-audit-") as temp:
        output = Path(temp) / "attack.html"
        output.write_text(markup, encoding="utf-8")
        generated_check = gzh_article.check_compat(str(output))
        output.write_text(
            '<section><p style="color:#303030" onerror="alert(1)">bad</p></section>',
            encoding="utf-8")
        malicious_check = gzh_article.check_compat(str(output))
    blocked = renderer.render("[bad](javascript:alert(1)) ![bad](data:text/html;base64,PHNjcmlwdD4=)")
    return (not audit.event_attrs and not audit.unsafe_urls
            and generated_check.get("ok") is True
            and '&quot;onerror=&quot;' in markup
            and '&quot;onmouseover=&quot;' in markup
            and malicious_check.get("ok") is False
            and any("事件处理器" in item for item in malicious_check.get("violations", []))
            and "<a " not in blocked and "<img " not in blocked)


def main() -> int:
    checks = {
        "plate_page_image_forwarded": plate_page_image_reaches_cover_cli(),
        "plate_page_requires_image": plate_page_without_image_fails_before_cover_cli(),
        "missing_and_wrong_layout_images_rejected": missing_or_wrong_layout_image_fails_closed(),
        "demo_uses_a_short_cover_headline": demo_uses_a_short_cover_headline(),
        "markdown_attribute_injection_blocked": markdown_attributes_are_escaped_and_checked(),
        "article_cover_timeout_uses_process_tree_runner": article_cover_timeout_uses_process_tree_runner(),
        "existing_cover_project_is_not_overwritten": existing_cover_project_is_not_overwritten(),
        "auto_layout_fallback_reuses_only_its_own_created_project":
            auto_layout_fallback_reuses_only_its_own_created_project(),
        "long_article_name_preview_path_is_bounded": long_article_name_preview_is_bounded(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    print(json.dumps({"ok": not failed, "checks": checks, "failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
