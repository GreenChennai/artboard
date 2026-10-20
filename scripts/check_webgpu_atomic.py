#!/usr/bin/env python3
"""WebGPU 引擎/像素验收失败不得覆盖旧输出的本地回归检查。"""
from __future__ import annotations

import contextlib
import io
import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import _gzh_layouts as layouts
import _proc
import export as exporter
import gzh_cover
import shader_fx


def run_case(fmt: str, engine: str, webgpu: bool, should_pass: bool,
             engine_fallback: bool | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="artboard-webgpu-atomic-") as directory:
        final_path = Path(directory) / "cover.png"
        final_path.write_bytes(b"existing-output")
        previous_argv = sys.argv
        previous_find = exporter.find_kiln
        previous_supports = exporter._supports
        previous_export = exporter.export_via_kiln
        previous_fallback = exporter.run_playwright_fallback
        exporter.find_kiln = lambda: "mock-kiln"
        exporter._supports = lambda *_args, **_kwargs: True

        staged_paths = []
        fallback_calls = []

        def fake_export(_cli: str, args) -> tuple[int, dict, dict]:
            staged = Path(args.output).parent
            staged_paths.append(staged.parent == final_path.parent
                                and staged.name.startswith(".artboard-stage-")
                                and not staged.is_symlink())
            Path(args.output).write_bytes(b"rendered-output")
            metadata = {"format": fmt, "engine": engine, "webgpu": webgpu}
            if engine_fallback is not None:
                metadata["engine_fallback"] = engine_fallback
            return 0, {}, metadata

        def fake_fallback(args):
            fallback_calls.append(True)
            Path(args.output).write_bytes(b"fallback-output")
            return 0, {"path": str(Path(args.output).resolve()), "engine": "playwright"}

        exporter.export_via_kiln = fake_export
        exporter.run_playwright_fallback = fake_fallback
        sys.argv = ["export.py", "--source", "unused.html", "--output", str(final_path),
                    "--format", fmt, "--webgpu"]
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = exporter.main()
        finally:
            sys.argv = previous_argv
            exporter.find_kiln = previous_find
            exporter._supports = previous_supports
            exporter.export_via_kiln = previous_export
            exporter.run_playwright_fallback = previous_fallback

        payload = json.loads(output.getvalue().splitlines()[-1])
        actual = final_path.read_bytes()
        staging_dirs = list(Path(directory).glob(".artboard-stage-*"))
        stage_was_private = bool(staged_paths) and all(staged_paths)
        preserved_on_failure = (code != 0 and actual == b"existing-output"
                                and not staging_dirs and stage_was_private)
        committed_on_success = (code == 0 and actual == b"rendered-output"
                                 and not staging_dirs and stage_was_private
                                 and payload.get("path") == str(final_path.resolve()))
        if engine_fallback:
            passed = (preserved_on_failure and payload.get("error") == "KILN_WEBGPU_UNVERIFIED"
                      and not fallback_calls)
        else:
            passed = committed_on_success if should_pass else preserved_on_failure
        return {"case": f"{fmt}/{engine}/webgpu={webgpu}/fallback={engine_fallback}", "ok": passed,
                "returncode": code, "error": payload.get("error"),
                "reported_path": payload.get("path"),
                "old_output_preserved": actual == b"existing-output",
                "playwright_fallback_calls": len(fallback_calls),
                "private_stage_used": stage_was_private,
                "remaining_stage_dirs": len(staging_dirs)}


def run_bake_case(pixel_valid: bool, dimension_valid: bool = True) -> dict:
    with tempfile.TemporaryDirectory(prefix="artboard-shader-bake-atomic-") as directory:
        final_path = Path(directory) / "cover.png"
        final_path.write_bytes(b"existing-output")
        previous_run = shader_fx._run_export_with_timeout
        previous_inspect = shader_fx.inspect_png

        def fake_run(command, **_kwargs):
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_bytes(b"rendered-pending-png")
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        def fake_inspect(_path):
            if not pixel_valid:
                raise ValueError("test fixture failed pixel validation")
            return {"width": 900 if dimension_valid else 899,
                    "height": 383, "bytes": 19, "unique_colors": 23,
                    "luma_range": [10, 220]}

        shader_fx._run_export_with_timeout = fake_run
        shader_fx.inspect_png = fake_inspect
        raised = False
        try:
            shader_fx.bake("halftone", {}, final_path, 900, 383, True)
        except ValueError:
            raised = True
        finally:
            shader_fx._run_export_with_timeout = previous_run
            shader_fx.inspect_png = previous_inspect

        actual = final_path.read_bytes()
        pending = list(Path(directory).glob(".cover.artboard-pending-*"))
        preserved_on_failure = (raised and actual == b"existing-output" and not pending)
        committed_on_success = (not raised and actual == b"rendered-pending-png" and not pending)
        acceptance = pixel_valid and dimension_valid
        passed = committed_on_success if acceptance else preserved_on_failure
        return {"case": f"shader-bake/pixel_valid={pixel_valid}/dimension_valid={dimension_valid}", "ok": passed,
                "old_output_preserved": actual == b"existing-output",
                "pending_files": len(pending)}


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    crc = zlib.crc32(kind + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)


def _transparent_varied_png() -> bytes:
    width = height = 64
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(((x * 4) & 255, (y * 4) & 255, ((x + y) * 2) & 255, 0))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(rows)) + _png_chunk(b"IEND", b""))


def fully_transparent_shader_png_is_rejected_atomically() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-transparent-shader-") as directory:
        out = Path(directory) / "cover.png"
        out.write_bytes(b"existing-output")
        previous_run = shader_fx._run_export_with_timeout
        transparent = _transparent_varied_png()

        def fake_run(command, **_kwargs):
            Path(command[command.index("--output") + 1]).write_bytes(transparent)
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        shader_fx._run_export_with_timeout = fake_run
        try:
            try:
                shader_fx.bake("halftone", {}, out, 900, 383, True)
            except RuntimeError as exc:
                rejected = "fully transparent" in str(exc)
            else:
                rejected = False
        finally:
            shader_fx._run_export_with_timeout = previous_run
        pending = list(Path(directory).glob(".cover.artboard-pending-*"))
        return rejected and out.read_bytes() == b"existing-output" and not pending


def run_shader_marker_guard_case() -> dict:
    with tempfile.TemporaryDirectory(prefix="artboard-webgpu-marker-") as directory:
        project = Path(directory) / "project"
        src = project / "src"
        src.mkdir(parents=True)
        _theme_name, theme = gzh_cover._resolve_theme("ink")
        data = layouts.make_data(title="封面要点", sub="分层说明")
        markup = layouts.render("center-band", theme, data, font_vars="",
                                sub=False, pattern="none", fx="halftone")
        markup = markup.replace(' data-webgpu-required="true"', "")
        markup = markup.replace("<canvas", '<canvas data-probe="quoted > delimiter"', 1)
        main_html = src / "index.html"
        main_html.write_text(markup, encoding="utf-8")
        (project / "project.json").write_text(
            json.dumps({"layout": "center-band", "fx": "halftone"}), encoding="utf-8")
        outdir = Path(directory) / "exports"
        previous_check = gzh_cover.check_kiln
        def unexpected_export(*_args, **_kwargs):
            raise AssertionError("export must not run when WebGPU metadata is inconsistent")

        previous_export = gzh_cover.run_export
        gzh_cover.check_kiln = lambda: False
        gzh_cover.run_export = unexpected_export
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = gzh_cover.cmd_export(SimpleNamespace(
                    project=str(project), only="main", outdir=str(outdir), scale=1,
                    bg="#f6f7f9"))
        finally:
            gzh_cover.check_kiln = previous_check
            gzh_cover.run_export = previous_export
        payload = json.loads(output.getvalue().splitlines()[-1])
        check_rows = gzh_cover.check_one(str(main_html), gzh_cover.MAIN_W,
                                        "center-band", project_fx="halftone")
        marker_row = next(row for row in check_rows if row["id"] == "webgpu-required-marker")
        no_outputs = not outdir.exists() or not list(outdir.glob("*.png"))
        passed = (code != 0 and payload.get("error") == "WEBGPU_REQUIREMENT_MISMATCH"
                  and gzh_cover.html_requires_webgpu(str(main_html))
                  and not marker_row["ok"] and no_outputs)
        return {"case": "quoted-greater-than-shader-canvas-with-missing-marker", "ok": passed,
                "error": payload.get("error"), "marker_row": marker_row["ok"],
                "webgpu_lane_detected": gzh_cover.html_requires_webgpu(str(main_html)),
                "export_called": False, "output_dir_created": outdir.exists()}


def wall_flag_reaches_kiln() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-export-wall-flag-") as temp:
        output_path = Path(temp) / "video.mp4"
        previous_run = exporter.run_tree
        commands = []

        def fake_run(command, **_kwargs):
            cmd = list(command)
            commands.append(cmd)
            Path(cmd[cmd.index("--output") + 1]).write_bytes(b"video")
            payload = {"ok": True, "format": "MP4", "engine": "browser-anim",
                       "webgpu": True, "frames": 20}
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="",
                                   timed_out=False, seconds=0.1)

        exporter.run_tree = fake_run
        args = SimpleNamespace(
            source="video.html", output=str(output_path), format="MP4", scale=1,
            width=900, height=384, wall=True, fps=10, max_wait=2, transparent=False,
            webgpu=True, gop=10, bf=0, pix_fmt="", no_color_tags=False,
            max_wait_budget=0, timeout=30)
        try:
            rc, error, engine = exporter.export_via_kiln("mock-kiln", args)
        finally:
            exporter.run_tree = previous_run
        return (rc == 0 and not error and engine.get("webgpu") is True
                and any("--wall" in command and "--webgpu" in command
                        for command in commands))


def timeout_export_process_tree_is_terminated() -> bool:
    class FakeProcess:
        pid = 24680

        def __init__(self):
            self.returncode = None
            self.communicate_calls = 0
            self.killed = False

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(["fake-kiln-export"], timeout)
            return "partial stdout", "partial stderr"

        def wait(self, timeout=None):
            self.returncode = -9
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

    proc = FakeProcess()
    operations = []

    class FakeJob:
        def terminate(self):
            operations.append("terminate")
            proc.returncode = -9
            return True

        def wait_empty(self, timeout=0.5):
            return True

        def active_processes(self):
            return 0

        def close(self):
            operations.append("close")

    job = FakeJob()
    with patch.object(shader_fx._proc, "popen_with_tree", return_value=(proc, job)) as popen:
        try:
            shader_fx._run_export_with_timeout(["fake-kiln-export"], cwd=".", env={}, timeout=1)
        except RuntimeError as exc:
            error = str(exc)
        else:
            return False
    launch_options = popen.call_args.kwargs
    isolated = (launch_options.get("creationflags", 0) != 0 if os.name == "nt"
                else launch_options.get("start_new_session") is True)
    return (operations == ["terminate", "close"] and isolated
            and proc.communicate_calls == 2 and "process tree terminated" in error
            and "partial stderr" in error)


def exited_parent_descendant_is_terminated() -> bool:
    if os.name != "nt":
        return True
    with tempfile.TemporaryDirectory(prefix="artboard-exited-parent-tree-") as temp:
        pid_file = Path(temp) / "child.pid"
        child_code = "import time; time.sleep(30)"
        parent_code = (
            "import subprocess,sys; "
            f"child=subprocess.Popen([{sys.executable!r},'-c',{child_code!r}], "
            "stdout=sys.stdout,stderr=sys.stderr); "
            f"open({str(pid_file)!r},'w').write(str(child.pid)); "
            "print('parent-exited');sys.stdout.flush()"
        )
        error = ""
        try:
            shader_fx._run_export_with_timeout(
                [sys.executable, "-c", parent_code], cwd=temp,
                env=os.environ.copy(), timeout=1)
        except RuntimeError as exc:
            error = str(exc)
        if not pid_file.is_file():
            return False
        try:
            child_pid = int(pid_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        tasklist = subprocess.run(
            ["tasklist", "/FI", f"PID eq {child_pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        child_still_running = f'"{child_pid}"' in tasklist.stdout
        if child_still_running:
            subprocess.run(["taskkill", "/PID", str(child_pid), "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=10)
        return ("process tree terminated" in error and tasklist.returncode == 0
                and not child_still_running)


def process_tree_killer_targets_descendants() -> bool:
    class FakeProcess:
        pid = 13579

        def __init__(self):
            self.returncode = None
            self.killed = False

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def kill(self):
            self.killed = True
            self.returncode = -9

    windows_proc = FakeProcess()
    with patch.object(shader_fx.subprocess, "run",
                      return_value=SimpleNamespace(returncode=0)) as taskkill:
        windows_ok = shader_fx._terminate_process_tree(windows_proc, windows=True)
    windows_call = taskkill.call_args.args[0] if taskkill.call_args else []

    posix_proc = FakeProcess()
    with patch.object(shader_fx.os, "killpg", create=True) as killpg:
        posix_ok = shader_fx._terminate_process_tree(posix_proc, windows=False)
    posix_call = killpg.call_args.args if killpg.call_args else ()
    return (windows_ok and windows_call == ["taskkill", "/PID", "13579", "/T", "/F"]
            and not windows_proc.killed and posix_ok
            and posix_call == (13579, getattr(signal, "SIGKILL", signal.SIGTERM))
            and not posix_proc.killed)


def saved_posix_group_id_is_used_after_parent_exit() -> bool:
    expected_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
    with patch.object(_proc.os, "killpg", create=True) as killpg, \
            patch.object(_proc.os, "getpgid", create=True,
                         side_effect=AssertionError("must not re-query reaped root")):
        ok = _proc._kill_process_group(424242)
    return (ok and killpg.call_args is not None
            and killpg.call_args.args == (424242, expected_signal))


def nested_export_timeout_triggers_wrapper_group_cleanup() -> bool:
    class FakeProcess:
        pid = 24680
        returncode = 1

        def communicate(self, timeout=None):
            return json.dumps({"ok": False, "error": "KILN_CLI_TIMEOUT"}), ""

    process = FakeProcess()
    captured = []

    def fake_popen(_command, **options):
        captured.append(options)
        return process, None

    with patch.object(shader_fx.os, "name", "posix"), \
            patch.object(shader_fx._proc, "popen_with_tree", side_effect=fake_popen), \
            patch.object(shader_fx, "_terminate_process_tree", return_value=True) as terminate:
        completed = shader_fx._run_export_with_timeout(
            ["python", "export.py"], cwd=".", env={}, timeout=10)
    options = captured[-1] if captured else {}
    return (completed.returncode == 1
            and options.get("env", {}).get("ARTBOARD_INHERIT_PROCESS_GROUP") == "1"
            and terminate.call_args is not None
            and terminate.call_args.args == (process,))


def proc_run_inherits_wrapper_process_group_when_requested() -> bool:
    class FakeProcess:
        pid = 13579
        returncode = 0

        def __init__(self):
            self.stdout = io.BytesIO(b"")
            self.stderr = io.BytesIO(b"")
            self.killed = False

        def wait(self, timeout=None):
            return self.returncode

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True

    process = FakeProcess()
    captured = []

    def fake_popen(_command, **options):
        captured.append(options)
        return process, None

    with patch.object(_proc.os, "name", "posix"), \
            patch.dict(os.environ, {"ARTBOARD_INHERIT_PROCESS_GROUP": "1"}), \
            patch.object(_proc, "popen_with_tree", side_effect=fake_popen):
        result = _proc.run(["nested-kiln"], timeout=1)
    options = captured[-1] if captured else {}
    return (result.returncode == 0 and not result.timed_out and not process.killed
            and "start_new_session" not in options)


def root_exit_with_pipe_descendant_is_cleaned() -> bool:
    child_pid = None
    code = ("import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)']); "
            "print(child.pid,flush=True); time.sleep(0.25)")
    result = _proc.run([sys.executable, "-c", code], timeout=2.0)
    try:
        child_pid = int(result.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return False

    def alive(pid: int) -> bool:
        if os.name == "nt":
            check = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                   capture_output=True, text=True, timeout=5)
            return f'"{pid}"' in check.stdout
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    process_alive = alive(child_pid)
    if process_alive:
        # A failing regression must not leave a 90-second test process behind.
        _proc.kill_tree(child_pid, [child_pid])
        deadline = time.monotonic() + 2
        while alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
    return (result.timed_out and result.seconds < 3.0 and not process_alive
            and result.returncode == 0)


def short_lived_intermediate_tree_is_job_contained() -> bool:
    if os.name != "nt":
        return True
    with tempfile.TemporaryDirectory(prefix="artboard-job-intermediate-") as temp:
        pid_file = Path(temp) / "worker.pid"
        worker = Path(temp) / "worker.py"
        worker.write_text(
            f"import os,time; open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(90)",
            encoding="utf-8")
        cmdline = f'start "" /B "{sys.executable}" "{worker}"'
        parent_code = (
            "import os,subprocess,sys,time\n"
            f"raw=chr(34)+os.environ.get('ComSpec','cmd.exe')+chr(34)+' /d /c '+{cmdline!r}\n"
            "subprocess.Popen(raw, stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr)\n"
            f"deadline=time.time()+3\nwhile not os.path.isfile({str(pid_file)!r}) and time.time()<deadline:\n"
            "    time.sleep(0.01)\n"
            "print('root exits after intermediate launcher',flush=True)\n"
        )
        result = _proc.run([sys.executable, "-c", parent_code], timeout=5)
        if not pid_file.is_file():
            return False
        try:
            worker_pid = int(pid_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        tasklist = subprocess.run(
            ["tasklist", "/FI", f"PID eq {worker_pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        worker_alive = tasklist.returncode != 0 or f'"{worker_pid}"' in tasklist.stdout
        if worker_alive:
            subprocess.run(["taskkill", "/PID", str(worker_pid), "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=10)
        return (result.timed_out and result.returncode == 0 and result.seconds < 5
                and tasklist.returncode == 0 and not worker_alive)


def non_finite_shader_params_are_rejected() -> bool:
    metadata = {"params": ["speed", "balance"]}
    malformed = ('{"speed":NaN}', '{"speed":Infinity}', '{"speed":1e999}',
                 '{"balance":[1,{"nested":-1e999}]}')
    for raw in malformed:
        try:
            shader_fx._params(raw, None, metadata)
        except ValueError:
            continue
        return False
    for speed in (float("nan"), float("inf"), float("-inf")):
        try:
            shader_fx._params(None, speed, metadata)
        except ValueError:
            continue
        return False
    try:
        shader_fx._canvas("aurora", {"speed": float("nan")}, False)
    except ValueError:
        pass
    else:
        return False
    result = subprocess.run(
        [sys.executable, str(Path(shader_fx.__file__).resolve()),
         "--embed", "aurora", "--speed", "nan"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    return result.returncode == 2 and "finite" in result.stderr.lower() \
        and "data-params" not in result.stdout


def cover_webgpu_export_uses_tree_timeout() -> bool:
    calls = []

    def fake_runner(command, *, cwd, env, timeout):
        calls.append((command, cwd, env, timeout))
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"ok": True, "webgpu": True}), "")

    def fake_timeout(*_args, **_kwargs):
        raise RuntimeError("Kiln WebGPU export timed out after 600 seconds; process tree terminated.")

    original = shader_fx._run_export_with_timeout
    try:
        shader_fx._run_export_with_timeout = fake_runner
        result = gzh_cover.run_export("source.html", "output.png", 900, 383, 1, webgpu=True)
        shader_fx._run_export_with_timeout = fake_timeout
        timeout_result = gzh_cover.run_export(
            "source.html", "output.png", 900, 383, 1, webgpu=True)
    finally:
        shader_fx._run_export_with_timeout = original
    command, cwd, env, timeout = calls[0] if calls else ([], "", {}, 0)
    return (result.get("ok") is True and result.get("webgpu") is True
            and timeout_result.get("error") == "EXPORT_TIMEOUT"
            and "--webgpu" in command and cwd == gzh_cover.SKILL_DIR
            and isinstance(env, dict) and timeout == 600)


def long_output_names_use_bounded_stage_components() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-long-output-name-") as temp:
        final = Path(temp) / ("x" * 240 + ".png")
        if len(final.name) != 244:
            return False
        stage = None
        try:
            stage, staged_output = exporter._temporary_output_path(str(final))
            pending_png = shader_fx._pending_png_path(final)
            return (len(Path(stage.name).name) < 80
                    and Path(staged_output).parent == Path(stage.name)
                    and Path(staged_output).name == final.name
                    and pending_png.parent == final.parent
                    and pending_png.name.startswith(".artboard-shader-pending-")
                    and len(pending_png.name) < 80 and not pending_png.exists())
        finally:
            if stage is not None:
                stage.cleanup()


def shader_bake_rejects_tampered_vendor_before_export() -> bool:
    with tempfile.TemporaryDirectory(prefix="artboard-shader-hash-gate-") as temp:
        root = Path(temp) / "vendor" / "shaders"
        (root / "LICENSES").mkdir(parents=True)
        (root / "runtime.js").write_text("tampered runtime", encoding="utf-8")
        (root / "upstream.js").write_text("tampered bundle", encoding="utf-8")
        (root / "LICENSES" / "shaders-LICENSE").write_text("MIT", encoding="utf-8")
        out = Path(temp) / "not-created" / "result.png"
        previous_runtime, previous_upstream = shader_fx.RUNTIME, shader_fx.UPSTREAM_RUNTIME
        shader_fx.RUNTIME = root / "runtime.js"
        shader_fx.UPSTREAM_RUNTIME = root / "upstream.js"
        export_calls = []
        try:
            with patch.object(shader_fx, "_run_export_with_timeout",
                              side_effect=lambda *args, **kwargs: export_calls.append(args)):
                try:
                    shader_fx.bake("halftone", {}, out, 32, 32, overwrite=True)
                except RuntimeError as exc:
                    return ("SHADER_VENDOR_HASH_MISMATCH" in str(exc)
                            and export_calls == [] and not out.parent.exists())
                return False
        finally:
            shader_fx.RUNTIME = previous_runtime
            shader_fx.UPSTREAM_RUNTIME = previous_upstream


def main() -> int:
    results = [
        run_case("PNG", "browser", True, True),
        run_case("PNG", "browser", False, False),
        run_case("PNG", "browser-anim", True, False),
        run_case("PNG", "browser", True, False, engine_fallback=True),
        run_bake_case(False),
        run_bake_case(True, dimension_valid=False),
        run_bake_case(True, dimension_valid=True),
        run_shader_marker_guard_case(),
        {"case": "animated-webgpu-wall-flag-forwarded", "ok": wall_flag_reaches_kiln()},
        {"case": "shader-bake-timeout-terminates-process-tree",
         "ok": timeout_export_process_tree_is_terminated()},
        {"case": "non-finite-shader-parameters-rejected",
         "ok": non_finite_shader_params_are_rejected()},
        {"case": "process-tree-killer-targets-all-descendants",
         "ok": process_tree_killer_targets_descendants()},
        {"case": "saved-posix-process-group-survives-root-reap",
         "ok": saved_posix_group_id_is_used_after_parent_exit()},
        {"case": "nested-posix-kiln-timeout-triggers-wrapper-group-cleanup",
         "ok": nested_export_timeout_triggers_wrapper_group_cleanup()},
        {"case": "nested-proc-run-inherits-wrapper-posix-group",
         "ok": proc_run_inherits_wrapper_process_group_when_requested()},
        {"case": "exited-parent-still-terminates-inherited-pipe-descendant",
         "ok": exited_parent_descendant_is_terminated()},
        {"case": "cover-webgpu-export-uses-process-tree-timeout",
         "ok": cover_webgpu_export_uses_tree_timeout()},
        {"case": "root-exit-with-inherited-pipe-descendant-is-cleaned",
         "ok": root_exit_with_pipe_descendant_is_cleaned()},
        {"case": "short-lived-intermediate-is-job-contained",
         "ok": short_lived_intermediate_tree_is_job_contained()},
        {"case": "long-output-name-uses-bounded-temp-components",
         "ok": long_output_names_use_bounded_stage_components()},
        {"case": "shader-bake-rejects-tampered-vendor-before-export",
         "ok": shader_bake_rejects_tampered_vendor_before_export()},
        {"case": "fully-transparent-shader-png-rejected-atomically",
         "ok": fully_transparent_shader_png_is_rejected_atomically()},
    ]
    report = {"ok": all(row["ok"] for row in results), "count": len(results),
              "passed": sum(row["ok"] for row in results), "results": results}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
