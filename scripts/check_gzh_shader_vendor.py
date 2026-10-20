#!/usr/bin/env python3
"""Verify shader-enabled projects fail closed when local vendor assets cannot link."""
from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gzh_cover
import pack

REPO_ROOT = Path(__file__).resolve().parent.parent
PACK_CLI = Path(__file__).resolve().with_name("pack.py")
SHADER_VENDOR = REPO_ROOT / "vendor" / "shaders"


def own_src_case_collision_is_rejected(work: Path) -> bool:
    project = work / "own-case-collision-project"
    src = project / "src"
    src.mkdir(parents=True)
    paths = [str(src / "A.html"), str(src / "a.html")]
    output_zip = work / "own-case-collision.zip"
    emitted = []
    with patch.object(pack.sys, "argv", [str(PACK_CLI), str(project), "--out", str(output_zip)]), \
            patch.object(pack, "collect_refs", return_value=(paths, {})), \
            patch.object(pack, "emit", side_effect=emitted.append):
        code = pack.main()
    payload = emitted[-1] if emitted else {}
    conflicts = payload.get("conflicts", [])
    return (code == 1 and payload.get("error") == "PACK_DESTINATION_CONFLICT"
            and any(len(item.get("sources", [])) == 2
                    and "$PROJECT/src/" in " ".join(item["sources"])
                    for item in conflicts)
            and not output_zip.exists())


def case_variant_project_path_still_packs(work: Path) -> bool:
    if os.name != "nt":
        return True
    project = work / "MixedCaseProject"
    src = project / "src"
    src.mkdir(parents=True)
    (src / "index.html").write_text("<p>case-insensitive path</p>", encoding="utf-8")
    variant = str(project).swapcase()
    if not os.path.isdir(variant):
        return False
    output_zip = work / "case-variant.zip"
    emitted = []
    with patch.object(pack.sys, "argv", [str(PACK_CLI), variant, "--out", str(output_zip)]), \
            patch.object(pack, "emit", side_effect=emitted.append):
        code = pack.main()
    payload = emitted[-1] if emitted else {}
    return code == 0 and payload.get("ok") is True and output_zip.is_file()


def check_shader_packaging(work: Path) -> dict:
    own_case_collision_rejected = own_src_case_collision_is_rejected(work)
    case_variant_ok = case_variant_project_path_still_packs(work)
    trusted_project = work / "trusted-project"
    trusted_src = trusted_project / "src"
    (trusted_src / "vendor").mkdir(parents=True)
    (trusted_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>', encoding="utf-8")
    trusted_link = trusted_src / "vendor" / "shaders"
    try:
        trusted_link.symlink_to(SHADER_VENDOR, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": True, "skipped": f"directory_symlink_unavailable:{type(exc).__name__}"}

    trusted_zip = work / "trusted.zip"
    trusted = subprocess.run(
        [sys.executable, str(PACK_CLI), str(trusted_project), "--out", str(trusted_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if trusted.returncode:
        return {"ok": False, "trusted_stderr": trusted.stderr[-1000:],
                "trusted_stdout": trusted.stdout[-1000:]}
    extracted = work / "extracted"
    with zipfile.ZipFile(trusted_zip) as archive:
        names = set(archive.namelist())
        archive.extractall(extracted)
    required = {
        f"{trusted_project.name}/assets/vendor/shaders/runtime.js",
        f"{trusted_project.name}/assets/vendor/shaders/upstream.js",
        f"{trusted_project.name}/assets/vendor/shaders/LICENSES/shaders-LICENSE",
    }
    trusted_ok = required.issubset(names) and all((extracted / name).is_file() for name in required)

    skill_assets = work / "fake-skill-assets"
    skill_vendor = skill_assets / "assets" / "vendor"
    skill_vendor.mkdir(parents=True)
    (skill_vendor / "library.js").write_text("trusted library", encoding="utf-8")
    slim_vendor_project = work / "slim-vendor-project"
    slim_vendor_src = slim_vendor_project / "src"
    slim_vendor_src.mkdir(parents=True)
    (slim_vendor_src / "index.html").write_text(
        '<script src="vendor/library.js"></script>', encoding="utf-8")
    try:
        (slim_vendor_src / "vendor").symlink_to(skill_vendor, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "slim_vendor_link_setup_failed": type(exc).__name__}
    slim_vendor_zip = work / "slim-vendor.zip"
    slim_vendor_output = []
    old_skill_dir = pack.SKILL_DIR
    try:
        pack.SKILL_DIR = str(skill_assets)
        with patch.object(pack.sys, "argv", [str(PACK_CLI), str(slim_vendor_project),
                                             "--out", str(slim_vendor_zip)]), \
             patch.object(pack, "emit", side_effect=slim_vendor_output.append):
            slim_vendor_returncode = pack.main()
    finally:
        pack.SKILL_DIR = old_skill_dir
    slim_vendor_result = slim_vendor_output[-1] if slim_vendor_output else {}
    slim_vendor_ok = False
    if slim_vendor_returncode == 0 and slim_vendor_zip.is_file():
        with zipfile.ZipFile(slim_vendor_zip) as archive:
            slim_vendor_ok = (any(name.endswith("/assets/vendor/library.js")
                                  for name in archive.namelist())
                              and archive.read(next(name for name in archive.namelist()
                                                    if name.endswith("/assets/vendor/library.js")))
                              == b"trusted library")

    external = work / "outside" / "shaders"
    external.mkdir(parents=True)
    (external / "upstream.js").write_text("public asset", encoding="utf-8")
    (external / "private.txt").write_text("must not leak", encoding="utf-8")
    malicious_project = work / "linked-project"
    malicious_src = malicious_project / "src"
    (malicious_src / "vendor").mkdir(parents=True)
    (malicious_src / "index.html").write_text(
        '<script src="vendor/shaders/upstream.js"></script>', encoding="utf-8")
    try:
        (malicious_src / "vendor" / "shaders").symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "skipped_attack": f"directory_symlink_unavailable:{type(exc).__name__}"}
    malicious_zip = work / "malicious.zip"
    attack = subprocess.run(
        [sys.executable, str(PACK_CLI), str(malicious_project), "--out", str(malicious_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        error = json.loads(attack.stdout).get("error")
    except (json.JSONDecodeError, AttributeError):
        error = None
    rejected = attack.returncode != 0 and error == "SHADER_VENDOR_LINK_FAILED" and not malicious_zip.exists()
    leaked_secret = False
    if malicious_zip.exists():
        with zipfile.ZipFile(malicious_zip) as archive:
            leaked_secret = any(name.endswith("/private.txt") for name in archive.namelist())
    local_project = work / "local-vendor-project"
    local_src = local_project / "src"
    local_vendor = local_src / "vendor" / "shaders"
    local_vendor.mkdir(parents=True)
    (local_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>', encoding="utf-8")
    (local_vendor / "runtime.js").write_text("load upstream.js", encoding="utf-8")
    (local_vendor / "upstream.js").write_text("shader bundle", encoding="utf-8")
    (local_vendor / "LICENSES").mkdir()
    (local_vendor / "LICENSES" / "shaders-LICENSE").write_text(
        "MIT License\\nCopyright (c) Shader Effects Inc.\\n", encoding="utf-8")
    local_zip = work / "local-vendor.zip"
    local_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(local_project), "--out", str(local_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    local_ok = False
    local_names = set()
    if local_result.returncode == 0 and local_zip.is_file():
        with zipfile.ZipFile(local_zip) as archive:
            local_names = set(archive.namelist())
        prefix = f"{local_project.name}/assets/vendor/shaders/"
        local_ok = all(prefix + rel in local_names for rel in (
            "runtime.js", "upstream.js", "LICENSES/shaders-LICENSE"))

    incomplete_project = work / "incomplete-vendor-project"
    incomplete_src = incomplete_project / "src"
    incomplete_vendor = incomplete_src / "vendor" / "shaders"
    incomplete_vendor.mkdir(parents=True)
    (incomplete_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>', encoding="utf-8")
    (incomplete_vendor / "runtime.js").write_text("load upstream.js", encoding="utf-8")
    (incomplete_vendor / "upstream.js").write_text("shader bundle", encoding="utf-8")
    incomplete_zip = work / "incomplete-vendor.zip"
    incomplete = subprocess.run(
        [sys.executable, str(PACK_CLI), str(incomplete_project), "--out", str(incomplete_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        incomplete_payload = json.loads(incomplete.stdout)
    except json.JSONDecodeError:
        incomplete_payload = {}
    incomplete_rejected = (
        incomplete.returncode != 0
        and incomplete_payload.get("error") == "SHADER_VENDOR_INCOMPLETE"
        and "LICENSES/shaders-LICENSE" in incomplete_payload.get("missing", [])
        and not incomplete_zip.exists())

    nested_project = work / "nested-link-project"
    nested_src = nested_project / "src"
    nested_vendor = nested_src / "vendor" / "shaders"
    nested_vendor.mkdir(parents=True)
    (nested_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>'
        '<script src="vendor/shaders/external/payload.js"></script>', encoding="utf-8")
    (nested_vendor / "runtime.js").write_text("load upstream.js", encoding="utf-8")
    (nested_vendor / "upstream.js").write_text("shader bundle", encoding="utf-8")
    (nested_vendor / "LICENSES").mkdir()
    (nested_vendor / "LICENSES" / "shaders-LICENSE").write_text(
        "MIT License\\n", encoding="utf-8")
    nested_external = work / "nested-external"
    nested_external.mkdir()
    (nested_external / "payload.js").write_text("external payload", encoding="utf-8")
    try:
        (nested_vendor / "external").symlink_to(nested_external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "symlink_setup_failed": type(exc).__name__}
    nested_zip = work / "nested-link.zip"
    nested = subprocess.run(
        [sys.executable, str(PACK_CLI), str(nested_project), "--out", str(nested_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        nested_payload = json.loads(nested.stdout)
    except json.JSONDecodeError:
        nested_payload = {}
    nested_link_rejected = (
        nested.returncode != 0
        and nested_payload.get("error") == "SHADER_VENDOR_LINK_FAILED"
        and "external" in nested_payload.get("linked", [])
        and not nested_zip.exists())

    file_link_project = work / "file-link-project"
    file_link_src = file_link_project / "src"
    file_link_vendor = file_link_src / "vendor" / "shaders"
    file_link_vendor.mkdir(parents=True)
    (file_link_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>', encoding="utf-8")
    (file_link_vendor / "runtime.js").write_text("load upstream.js", encoding="utf-8")
    (file_link_vendor / "upstream.js").write_text("shader bundle", encoding="utf-8")
    (file_link_vendor / "LICENSES").mkdir()
    (file_link_vendor / "LICENSES" / "shaders-LICENSE").write_text(
        "MIT License\\n", encoding="utf-8")
    file_secret = work / "file-link-secret.js"
    file_secret.write_text("must not leak", encoding="utf-8")
    try:
        (file_link_vendor / "private.js").symlink_to(file_secret)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "file_link_setup_failed": type(exc).__name__}
    file_link_zip = work / "file-link.zip"
    file_link_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(file_link_project), "--out", str(file_link_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        file_link_payload = json.loads(file_link_result.stdout)
    except json.JSONDecodeError:
        file_link_payload = {}
    file_link_rejected = (
        file_link_result.returncode != 0
        and file_link_payload.get("error") == "SHADER_VENDOR_LINK_FAILED"
        and "private.js" in file_link_payload.get("linked", [])
        and not file_link_zip.exists())

    font_external = work / "font-external"
    font_external.mkdir()
    (font_external / "private.ttf").write_text("must not leak", encoding="utf-8")
    font_dir_project = work / "font-dir-link-project"
    font_dir_src = font_dir_project / "src"
    (font_dir_src / "fonts").mkdir(parents=True)
    (font_dir_src / "index.html").write_text(
        '<style>@font-face{src:url("fonts/family/private.ttf")}</style>', encoding="utf-8")
    try:
        (font_dir_src / "fonts" / "family").symlink_to(font_external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "font_dir_link_setup_failed": type(exc).__name__}
    font_dir_zip = work / "font-dir-link.zip"
    font_dir_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(font_dir_project), "--out", str(font_dir_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        font_dir_payload = json.loads(font_dir_result.stdout)
    except json.JSONDecodeError:
        font_dir_payload = {}
    font_dir_rejected = (
        font_dir_result.returncode != 0
        and font_dir_payload.get("error") == "FONT_LINK_FAILED"
        and "family" in font_dir_payload.get("linked", [])
        and not font_dir_zip.exists())

    font_file_project = work / "font-file-link-project"
    font_file_src = font_file_project / "src"
    font_family = font_file_src / "fonts" / "family"
    font_family.mkdir(parents=True)
    (font_file_src / "index.html").write_text(
        '<style>@font-face{src:url("fonts/family/private.ttf")}</style>', encoding="utf-8")
    try:
        (font_family / "private.ttf").symlink_to(font_external / "private.ttf")
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "font_file_link_setup_failed": type(exc).__name__}
    font_file_zip = work / "font-file-link.zip"
    font_file_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(font_file_project), "--out", str(font_file_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        font_file_payload = json.loads(font_file_result.stdout)
    except json.JSONDecodeError:
        font_file_payload = {}
    font_file_rejected = (
        font_file_result.returncode != 0
        and font_file_payload.get("error") == "FONT_LINK_FAILED"
        and "family/private.ttf" in font_file_payload.get("linked", [])
        and not font_file_zip.exists())

    font_collision_project = work / "font-destination-collision-project"
    font_collision_src = font_collision_project / "src"
    local_collision_font = font_collision_src / "fonts" / "english-chewy" / "Chewy-Regular.ttf"
    local_collision_font.parent.mkdir(parents=True)
    local_collision_font.write_bytes(b"project-local font with a different payload")
    (font_collision_src / "index.html").write_text(
        '<style>@font-face{font-family:Chewy;src:url("fonts/english-chewy/Chewy-Regular.ttf")}</style>',
        encoding="utf-8")
    font_collision_zip = work / "font-destination-collision.zip"
    font_collision_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(font_collision_project),
         "--include-fonts", "--out", str(font_collision_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    try:
        font_collision_payload = json.loads(font_collision_result.stdout)
    except json.JSONDecodeError:
        font_collision_payload = {}
    font_collision_entries = font_collision_payload.get("conflicts", [])
    font_collision_rejected = (
        font_collision_result.returncode != 0
        and font_collision_payload.get("error") == "PACK_DESTINATION_CONFLICT"
        and any(entry.get("path") == "assets/fonts/english-chewy/Chewy-Regular.ttf"
                for entry in font_collision_entries)
        and not font_collision_zip.exists())

    source_link_project = work / "source-link-project"
    source_link_src = source_link_project / "src"
    source_link_src.mkdir(parents=True)
    (source_link_src / "index.html").write_text("<p>source link fixture</p>", encoding="utf-8")
    try:
        (source_link_src / "private.js").symlink_to(file_secret)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "source_link_setup_failed": type(exc).__name__}
    source_link_zip = work / "source-link.zip"
    source_link_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(source_link_project), "--out", str(source_link_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        source_link_payload = json.loads(source_link_result.stdout)
    except json.JSONDecodeError:
        source_link_payload = {}
    source_link_rejected = (
        source_link_result.returncode != 0
        and source_link_payload.get("error") == "PROJECT_LINK_FAILED"
        and "private.js" in source_link_payload.get("linked", [])
        and not source_link_zip.exists())

    internal_project_link = work / "internal-project-link"
    internal_src = internal_project_link / "src"
    internal_src.mkdir(parents=True)
    (internal_src / "index.html").write_text(
        '<script src="project-secret.js"></script>', encoding="utf-8")
    private_dir = internal_project_link / ".private"
    private_dir.mkdir()
    private_target = private_dir / "secret.js"
    private_target.write_text("PROJECT_ROOT_SECRET", encoding="utf-8")
    try:
        (internal_src / "project-secret.js").symlink_to(private_target)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "internal_project_link_setup_failed": type(exc).__name__}
    internal_project_zip = work / "internal-project-link.zip"
    internal_project_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(internal_project_link),
         "--out", str(internal_project_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        internal_project_payload = json.loads(internal_project_result.stdout)
    except json.JSONDecodeError:
        internal_project_payload = {}
    internal_project_link_rejected = (
        internal_project_result.returncode != 0
        and internal_project_payload.get("error") == "PROJECT_LINK_FAILED"
        and "project-secret.js" in internal_project_payload.get("linked", [])
        and not internal_project_zip.exists())

    internal_directory_link_project = work / "internal-directory-link-project"
    internal_directory_src = internal_directory_link_project / "src"
    real_page_dir = internal_directory_src / "real-page"
    real_page_dir.mkdir(parents=True)
    (internal_directory_src / "index.html").write_text(
        '<iframe src="alias/page.html"></iframe>', encoding="utf-8")
    (real_page_dir / "page.html").write_text(
        '<img src="photo.png">', encoding="utf-8")
    (real_page_dir / "photo.png").write_bytes(b"local image")
    try:
        (internal_directory_src / "alias").symlink_to(real_page_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "internal_directory_link_setup_failed": type(exc).__name__}
    internal_directory_zip = work / "internal-directory-link.zip"
    internal_directory_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(internal_directory_link_project),
         "--out", str(internal_directory_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        internal_directory_payload = json.loads(internal_directory_result.stdout)
    except json.JSONDecodeError:
        internal_directory_payload = {}
    internal_directory_link_rejected = (
        internal_directory_result.returncode != 0
        and internal_directory_payload.get("error") == "PROJECT_LINK_FAILED"
        and "alias" in internal_directory_payload.get("linked", [])
        and not internal_directory_zip.exists())

    linked_html_project = work / "linked-html-project"
    linked_html_src = linked_html_project / "src"
    linked_html_src.mkdir(parents=True)
    (linked_html_src / "index.html").write_text("<p>local</p>", encoding="utf-8")
    linked_html_target = work / "outside-linked.html"
    linked_html_target.write_text("<p>outside payload</p>", encoding="utf-8")
    try:
        (linked_html_src / "linked.html").symlink_to(linked_html_target)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "linked_html_setup_failed": type(exc).__name__}
    linked_html_zip = work / "linked-html.zip"
    linked_html_payloads = []
    linked_html_reads = []
    real_open = builtins.open

    def watch_external_html(path, *args, **kwargs):
        try:
            if os.path.realpath(os.fspath(path)) == os.path.realpath(linked_html_target):
                linked_html_reads.append(os.fspath(path))
        except (TypeError, ValueError):
            pass
        return real_open(path, *args, **kwargs)

    with patch.object(pack.sys, "argv", [str(PACK_CLI), str(linked_html_project),
                                         "--out", str(linked_html_zip)]), \
         patch.object(pack, "emit", side_effect=linked_html_payloads.append), \
         patch("builtins.open", side_effect=watch_external_html):
        linked_html_returncode = pack.main()
    linked_html_result = linked_html_payloads[-1] if linked_html_payloads else {}
    linked_html_rejected_before_read = (
        linked_html_returncode != 0
        and linked_html_result.get("error") == "PROJECT_LINK_FAILED"
        and "linked.html" in linked_html_result.get("linked", [])
        and not linked_html_reads and not linked_html_zip.exists())

    source_root_project = work / "source-root-link-project"
    source_root_project.mkdir()
    external_src = work / "external-src-root"
    external_src.mkdir()
    (external_src / "index.html").write_text(
        '<script src="private.js"></script>', encoding="utf-8")
    (external_src / "private.js").write_text("ROOT_SRC_SECRET", encoding="utf-8")
    try:
        (source_root_project / "src").symlink_to(external_src, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "source_root_link_setup_failed": type(exc).__name__}
    source_root_zip = work / "source-root-link.zip"
    source_root_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(source_root_project), "--out", str(source_root_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        source_root_payload = json.loads(source_root_result.stdout)
    except json.JSONDecodeError:
        source_root_payload = {}
    source_root_rejected = (
        source_root_result.returncode != 0
        and source_root_payload.get("error") == "PROJECT_LINK_FAILED"
        and "." in source_root_payload.get("linked", [])
        and not source_root_zip.exists())

    mixed_shader_project = work / "mixed-shader-roots-project"
    mixed_shader_src = mixed_shader_project / "src"
    local_vendor = mixed_shader_src / "vendor" / "shaders"
    (local_vendor / "LICENSES").mkdir(parents=True)
    for rel in ("runtime.js", "upstream.js", "LICENSES/shaders-LICENSE"):
        (local_vendor / rel).write_bytes((SHADER_VENDOR / rel).read_bytes())
    skill_upstream = Path(pack.SKILL_DIR) / "vendor" / "shaders" / "upstream.js"
    (mixed_shader_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>'
        f'<script src="{skill_upstream.as_uri()}"></script>', encoding="utf-8")
    mixed_shader_zip = work / "mixed-shader-roots.zip"
    mixed_shader_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(mixed_shader_project),
         "--out", str(mixed_shader_zip)], cwd=REPO_ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        mixed_shader_payload = json.loads(mixed_shader_result.stdout)
    except json.JSONDecodeError:
        mixed_shader_payload = {}
    mixed_shader_roots_rejected = (
        mixed_shader_result.returncode != 0
        and mixed_shader_payload.get("error") == "SHADER_VENDOR_ROOT_CONFLICT"
        and set(mixed_shader_payload.get("roots", [])) == {"project", "skill"}
        and not mixed_shader_zip.exists())

    tampered_vendor_project = work / "tampered-local-vendor-project"
    tampered_src = tampered_vendor_project / "src"
    tampered_vendor = tampered_src / "vendor" / "shaders"
    (tampered_vendor / "LICENSES").mkdir(parents=True)
    for rel in ("runtime.js", "upstream.js", "LICENSES/shaders-LICENSE"):
        (tampered_vendor / rel).write_bytes((SHADER_VENDOR / rel).read_bytes())
    runtime_path = tampered_vendor / "runtime.js"
    runtime_path.write_bytes(runtime_path.read_bytes() + b"\\n// unreviewed payload")
    tampered_status = gzh_cover._shader_vendor_status(str(tampered_src))
    tampered_vendor_rejected = (
        tampered_status is not None
        and tampered_status.get("error") == "SHADER_VENDOR_HASH_MISMATCH"
        and tampered_status.get("mismatched") == ["runtime.js"])
    _theme_name, tampered_theme = gzh_cover._resolve_theme("ink")
    tampered_markup = gzh_cover._GL.render(
        "center-band", tampered_theme,
        gzh_cover._GL.make_data(title="Bundle integrity test"),
        font_vars="", sub=False, pattern="none", fx="halftone")
    (tampered_src / "index.html").write_text(tampered_markup, encoding="utf-8")
    (tampered_vendor_project / "project.json").write_text(json.dumps({
        "layout": "center-band", "fx": "halftone", "main_fx": "halftone", "sub_fx": ""
    }), encoding="utf-8")
    tampered_export_emit = []
    tampered_export_calls = []
    tampered_export_dir = tampered_vendor_project / "export"
    with patch.object(gzh_cover, "emit", side_effect=tampered_export_emit.append), \
            patch.object(gzh_cover, "run_export",
                         side_effect=lambda *a, **k: tampered_export_calls.append(a)), \
            patch.object(gzh_cover, "check_kiln", return_value=True):
        tampered_export_rc = gzh_cover.cmd_export(SimpleNamespace(
            project=str(tampered_vendor_project), only="main",
            outdir=str(tampered_export_dir), scale=1, bg="#ffffff"))
    tampered_export_result = tampered_export_emit[-1] if tampered_export_emit else {}
    tampered_cover_export_rejected = (
        tampered_export_rc != 0
        and tampered_export_result.get("error") == "SHADER_VENDOR_HASH_MISMATCH"
        and tampered_export_result.get("mismatched") == ["runtime.js"]
        and not tampered_export_calls and not tampered_export_dir.exists())

    nonshader_markup = gzh_cover._GL.render(
        "center-band", tampered_theme, gzh_cover._GL.make_data(title="No shader canvas"),
        font_vars="", sub=False, pattern="none", fx="none")
    nonshader_markup = nonshader_markup.replace(
        "</body>", '<script src="vendor/shaders/runtime.js"></script></body>', 1)
    (tampered_src / "index.html").write_text(nonshader_markup, encoding="utf-8")
    (tampered_src / "sub.html").write_text(
        gzh_cover._GL.render("center-band", tampered_theme,
                             gzh_cover._GL.make_data(title="Sub"), font_vars="",
                             sub=True, pattern="none", fx="none"), encoding="utf-8")
    (tampered_vendor_project / "project.json").write_text(json.dumps({
        "layout": "center-band", "fx": "", "main_fx": "", "sub_fx": ""
    }), encoding="utf-8")
    no_canvas_check_emit = []
    with patch.object(gzh_cover, "emit", side_effect=no_canvas_check_emit.append):
        no_canvas_check_rc = gzh_cover.cmd_check(SimpleNamespace(project=str(tampered_vendor_project)))
    no_canvas_check_payload = no_canvas_check_emit[-1] if no_canvas_check_emit else {}
    no_canvas_vendor_check_rejected = (
        no_canvas_check_rc != 0 and any(
            row.get("id") == "shader-vendor" and row.get("error") == "SHADER_VENDOR_HASH_MISMATCH"
            for row in no_canvas_check_payload.get("failed", [])))
    no_canvas_export_emit = []
    no_canvas_export_calls = []
    no_canvas_export_dir = tampered_vendor_project / "no-canvas-export"
    with patch.object(gzh_cover, "emit", side_effect=no_canvas_export_emit.append), \
            patch.object(gzh_cover, "run_export",
                         side_effect=lambda *a, **k: no_canvas_export_calls.append(a)), \
            patch.object(gzh_cover, "check_kiln", return_value=True):
        no_canvas_export_rc = gzh_cover.cmd_export(SimpleNamespace(
            project=str(tampered_vendor_project), only="main",
            outdir=str(no_canvas_export_dir), scale=1, bg="#fff"))
    no_canvas_export_payload = no_canvas_export_emit[-1] if no_canvas_export_emit else {}
    tampered_vendor_script_without_canvas_rejected = (
        no_canvas_vendor_check_rejected and no_canvas_export_rc != 0
        and no_canvas_export_payload.get("error") == "SHADER_VENDOR_HASH_MISMATCH"
        and not no_canvas_export_calls and not no_canvas_export_dir.exists())

    cover_vendor_project = work / "cover-external-vendor-project"
    cover_src = cover_vendor_project / "src"
    vendor_parent = cover_src / "vendor"
    vendor_parent.mkdir(parents=True)
    external_cover_vendor = work / "external-cover-vendor"
    (external_cover_vendor / "LICENSES").mkdir(parents=True)
    (external_cover_vendor / "runtime.js").write_text("runtime", encoding="utf-8")
    (external_cover_vendor / "upstream.js").write_text("upstream", encoding="utf-8")
    (external_cover_vendor / "LICENSES" / "shaders-LICENSE").write_text(
        "MIT license", encoding="utf-8")
    try:
        (vendor_parent / "shaders").symlink_to(external_cover_vendor, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "cover_vendor_link_setup_failed": type(exc).__name__}
    _theme_name, cover_theme = gzh_cover._resolve_theme("ink")
    cover_data = gzh_cover._GL.make_data(title="封面 WebGPU 路径")
    cover_html = gzh_cover._GL.render("center-band", cover_theme, cover_data,
                                      font_vars="", sub=False, pattern="none", fx="halftone")
    (cover_src / "index.html").write_text(cover_html, encoding="utf-8")
    cover_sub = gzh_cover._GL.render("center-band", cover_theme,
                                     gzh_cover._GL.make_data(title="次封面"),
                                     font_vars="", sub=True, pattern="none", fx="")
    (cover_src / "sub.html").write_text(cover_sub, encoding="utf-8")
    (cover_vendor_project / "project.json").write_text(
        json.dumps({"layout": "center-band", "fx": "halftone",
                    "main_fx": "halftone", "sub_fx": ""}), encoding="utf-8")
    cover_emit = []
    cover_export_calls = []
    with patch.object(gzh_cover, "emit", side_effect=cover_emit.append), \
         patch.object(gzh_cover, "run_export", side_effect=lambda *a, **k: cover_export_calls.append(a)), \
         patch.object(gzh_cover, "check_kiln", return_value=True):
        cover_rc = gzh_cover.cmd_export(SimpleNamespace(
            project=str(cover_vendor_project), only="main",
            outdir=str(cover_vendor_project / "export"), scale=1, bg="#ffffff"))
    cover_result = cover_emit[-1] if cover_emit else {}
    cover_vendor_rejected = (cover_rc != 0
                             and cover_result.get("error") == "SHADER_VENDOR_LINK_FAILED"
                             and cover_result.get("linked") == ["."]
                             and not cover_export_calls
                             and not (cover_vendor_project / "export").exists())
    cover_check_emit = []
    with patch.object(gzh_cover, "emit", side_effect=cover_check_emit.append):
        cover_check_rc = gzh_cover.cmd_check(SimpleNamespace(project=str(cover_vendor_project)))
    cover_check_result = cover_check_emit[-1] if cover_check_emit else {}
    cover_check_rejected = (cover_check_rc != 0
                            and any(item.get("id") == "shader-vendor"
                                    and item.get("error") == "SHADER_VENDOR_LINK_FAILED"
                                    for item in cover_check_result.get("failed", [])))

    trusted_link_project = work / "trusted-skill-link-project"
    trusted_link_src = trusted_link_project / "src"
    trusted_link_src.mkdir(parents=True, exist_ok=True)
    trusted_link_setup = gzh_cover._link_shader_vendor(str(trusted_link_src))
    trusted_link_path = trusted_link_src / "vendor" / "shaders"
    trusted_link_status = gzh_cover._shader_vendor_status(str(trusted_link_src))
    trusted_skill_link_accepted = (trusted_link_setup and trusted_link_status is None
                                   and (not gzh_cover._is_link_or_junction(str(trusted_link_path))
                                        or os.path.normcase(os.path.realpath(trusted_link_path))
                                        == os.path.normcase(os.path.realpath(
                                            Path(gzh_cover.SKILL_DIR) / "vendor" / "shaders"))))

    shader_subdir_project = work / "shader-subdir-alias-project"
    shader_subdir_src = shader_subdir_project / "src"
    shader_subdir_vendor_parent = shader_subdir_src / "vendor"
    shader_subdir_vendor_parent.mkdir(parents=True)
    (shader_subdir_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>', encoding="utf-8")
    skill_shader_licenses = Path(pack.SKILL_DIR) / "vendor" / "shaders" / "LICENSES"
    try:
        (shader_subdir_vendor_parent / "shaders").symlink_to(
            skill_shader_licenses, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        return {"ok": False, "trusted_vendor": trusted_ok,
                "shader_subdir_alias_setup_failed": type(exc).__name__}
    shader_subdir_zip = work / "shader-subdir-alias.zip"
    shader_subdir_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(shader_subdir_project), "--out", str(shader_subdir_zip)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        shader_subdir_payload = json.loads(shader_subdir_result.stdout)
    except json.JSONDecodeError:
        shader_subdir_payload = {}
    shader_subdir_alias_rejected = (
        shader_subdir_result.returncode != 0
        and shader_subdir_payload.get("error") == "SHADER_VENDOR_LINK_FAILED"
        and "vendor/shaders" in shader_subdir_payload.get("linked", [])
        and not shader_subdir_zip.exists())

    missing_shader_project = work / "missing-shader-root-project"
    missing_shader_src = missing_shader_project / "src"
    missing_shader_src.mkdir(parents=True)
    (missing_shader_src / "index.html").write_text(
        '<script src="vendor/shaders/runtime.js"></script>', encoding="utf-8")
    missing_shader_zip = work / "missing-shader-root.zip"
    missing_shader_result = subprocess.run(
        [sys.executable, str(PACK_CLI), str(missing_shader_project),
         "--out", str(missing_shader_zip)], cwd=REPO_ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        missing_shader_payload = json.loads(missing_shader_result.stdout)
    except json.JSONDecodeError:
        missing_shader_payload = {}
    missing_shader_root_rejected = (
        missing_shader_result.returncode != 0
        and missing_shader_payload.get("error") == "SHADER_VENDOR_INCOMPLETE"
        and "vendor/shaders/runtime.js" in missing_shader_payload.get("missing", [])
        and not missing_shader_zip.exists())

    return {"ok": trusted_ok and slim_vendor_ok and rejected and not leaked_secret and local_ok
            and incomplete_rejected and nested_link_rejected and file_link_rejected
            and font_dir_rejected and font_file_rejected and font_collision_rejected
            and source_link_rejected
            and internal_project_link_rejected and internal_directory_link_rejected
            and source_root_rejected and linked_html_rejected_before_read
            and mixed_shader_roots_rejected and tampered_vendor_rejected
            and tampered_cover_export_rejected
            and tampered_vendor_script_without_canvas_rejected and cover_vendor_rejected
            and cover_check_rejected and trusted_skill_link_accepted and case_variant_ok
            and shader_subdir_alias_rejected and own_case_collision_rejected
            and missing_shader_root_rejected,
            "own_src_case_collision_rejected": own_case_collision_rejected,
            "trusted_vendor": trusted_ok, "trusted_returncode": trusted.returncode,
            "trusted_stdout": trusted.stdout[-1000:], "missing_vendor_files": sorted(required - names),
            "packed_vendor_files": sorted(name for name in names
                                           if name.startswith(f"{trusted_project.name}/assets/vendor/shaders/")),
            "slim_project_vendor_root_link_packaged": slim_vendor_ok,
            "slim_project_vendor_error": slim_vendor_result.get("error"),
            "external_recursive_link_rejected": rejected, "error": error,
            "external_secret_packed": leaked_secret, "local_vendor_with_license_packaged": local_ok,
            "local_vendor_missing_license_rejected": incomplete_rejected,
            "incomplete_error": incomplete_payload.get("error"),
            "incomplete_zip_created": incomplete_zip.exists(),
            "nested_vendor_symlink_rejected": nested_link_rejected,
            "nested_error": nested_payload.get("error"),
            "nested_linked_paths": nested_payload.get("linked", []),
            "nested_zip_created": nested_zip.exists(),
            "shader_file_link_rejected": file_link_rejected,
            "shader_file_link_paths": file_link_payload.get("linked", []),
            "shader_file_link_zip_created": file_link_zip.exists(),
            "font_directory_link_rejected": font_dir_rejected,
            "font_directory_link_paths": font_dir_payload.get("linked", []),
            "font_directory_link_zip_created": font_dir_zip.exists(),
            "font_file_link_rejected": font_file_rejected,
            "font_file_link_paths": font_file_payload.get("linked", []),
            "font_file_link_zip_created": font_file_zip.exists(),
            "font_destination_conflict_rejected": font_collision_rejected,
            "font_destination_conflict_error": font_collision_payload.get("error"),
            "font_destination_conflicts": font_collision_entries,
            "font_destination_conflict_zip_created": font_collision_zip.exists(),
            "other_source_link_rejected": source_link_rejected,
            "other_source_link_paths": source_link_payload.get("linked", []),
            "other_source_link_zip_created": source_link_zip.exists(),
            "internal_project_outside_src_link_rejected": internal_project_link_rejected,
            "internal_project_link_paths": internal_project_payload.get("linked", []),
            "internal_project_link_zip_created": internal_project_zip.exists(),
            "internal_src_directory_alias_rejected": internal_directory_link_rejected,
            "internal_src_directory_link_paths": internal_directory_payload.get("linked", []),
            "internal_src_directory_link_zip_created": internal_directory_zip.exists(),
            "linked_html_rejected_before_read": linked_html_rejected_before_read,
            "linked_html_reads": linked_html_reads,
            "linked_html_zip_created": linked_html_zip.exists(),
             "source_root_link_rejected": source_root_rejected,
             "source_root_link_paths": source_root_payload.get("linked", []),
             "source_root_link_zip_created": source_root_zip.exists(),
             "mixed_shader_roots_rejected": mixed_shader_roots_rejected,
             "mixed_shader_roots": mixed_shader_payload.get("roots", []),
             "mixed_shader_error": mixed_shader_payload.get("error"),
             "mixed_shader_zip_created": mixed_shader_zip.exists(),
             "tampered_local_vendor_rejected": tampered_vendor_rejected,
             "tampered_local_vendor_error": tampered_status.get("error") if tampered_status else None,
             "tampered_local_vendor_files": tampered_status.get("mismatched", []) if tampered_status else [],
             "tampered_cover_export_rejected": tampered_cover_export_rejected,
             "tampered_cover_export_error": tampered_export_result.get("error"),
             "tampered_cover_export_called": bool(tampered_export_calls),
             "tampered_cover_export_dir_created": tampered_export_dir.exists(),
             "tampered_vendor_script_without_canvas_rejected": tampered_vendor_script_without_canvas_rejected,
             "tampered_no_canvas_check_error": next((row.get("error") for row in
                 no_canvas_check_payload.get("failed", []) if row.get("id") == "shader-vendor"), None),
             "tampered_no_canvas_export_error": no_canvas_export_payload.get("error"),
             "tampered_no_canvas_export_called": bool(no_canvas_export_calls),
             "tampered_no_canvas_export_dir_created": no_canvas_export_dir.exists(),
              "cover_export_external_vendor_root_rejected": cover_vendor_rejected,
              "cover_export_error": cover_result.get("error"),
              "cover_export_linked_paths": cover_result.get("linked", []),
              "cover_export_called": bool(cover_export_calls),
              "cover_export_dir_created": (cover_vendor_project / "export").exists(),
              "cover_check_external_vendor_root_rejected": cover_check_rejected,
              "trusted_skill_vendor_root_link_accepted": trusted_skill_link_accepted,
             "case_variant_project_path_packaged": case_variant_ok,
              "shader_subdirectory_alias_rejected": shader_subdir_alias_rejected,
              "shader_subdirectory_alias_error": shader_subdir_payload.get("error"),
              "shader_subdirectory_alias_zip_created": shader_subdir_zip.exists(),
              "trusted_skill_vendor_link_status": trusted_link_status,
              "missing_shader_root_reference_rejected": missing_shader_root_rejected,
              "missing_shader_root_error": missing_shader_payload.get("error"),
              "missing_shader_root_paths": missing_shader_payload.get("missing", []),
              "missing_shader_root_zip_created": missing_shader_zip.exists(),
              "cover_check_error": next((item.get("error") for item in cover_check_result.get("failed", [])
                                          if item.get("id") == "shader-vendor"), None)}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="artboard-shader-link-") as temp:
        studio = Path(temp) / "studio"
        args = SimpleNamespace(
            list_layouts=False, slug="must-not-build", title="设计指南", force=False,
            theme="ink", layout="center-band", fonts="auto", sub_title="",
            sub_sub="", kicker="", sub="", footer="", num="", title_en="",
            badge="", side_label="", meta="", accent_tone="", sub_mode="",
            bg_pattern="", fx="auto")
        output = io.StringIO()
        with patch.object(gzh_cover, "cfg", side_effect=lambda _key, _default="": str(studio)), \
             patch.object(gzh_cover, "build_font_assets", return_value=("@font-face { font-family: Mock; }", "  --font-display: Mock;")), \
             patch.object(gzh_cover, "_link_project_fonts", return_value=[]), \
             patch.object(gzh_cover, "_link_shader_vendor", return_value=False), \
             contextlib.redirect_stdout(output):
            returncode = gzh_cover.cmd_new(args)
        payload = json.loads(output.getvalue().splitlines()[-1])
        project = studio / "must-not-build"
        passed = (returncode != 0 and payload.get("error") == "SHADER_VENDOR_INCOMPLETE"
                  and not project.exists()
                  and not (project / "src" / "index.html").exists()
                  and not (project / "project.json").exists())
        packaging = check_shader_packaging(Path(temp))
        passed = passed and packaging.get("ok", False)
        print(json.dumps({"ok": passed, "returncode": returncode,
                          "error": payload.get("error"),
                          "project_dir_exists": project.exists(),
                          "html_written": (project / "src" / "index.html").exists(),
                          "project_manifest_written": (project / "project.json").exists(),
                          "packaging": packaging}, ensure_ascii=False))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
