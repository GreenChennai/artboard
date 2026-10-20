#!/usr/bin/env python3
"""Artboard's offline helper for the official upstream WebGPU shader bundle.

Examples:
  python scripts/shader_fx.py --list
  python scripts/shader_fx.py --embed aurora --params '{"colorA":"#16233d","colorB":"#42b7c8"}'
  python scripts/shader_fx.py --embed aurora --dynamic --speed 0.6
  python scripts/shader_fx.py --bake halftone --out preview.png --width 900 --height 383 --kiln PATH

Rendering is performed by vendor/shaders/upstream.js, built from the official
shader-effects-inc/shaders package; runtime.js only maps Artboard slugs and forwards
props. Static bake requires a Kiln version with --webgpu. No CDN/Python package needed.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import _proc

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "vendor" / "shaders" / "runtime.js"
UPSTREAM_RUNTIME = ROOT / "vendor" / "shaders" / "upstream.js"
EXPORT = ROOT / "scripts" / "export.py"
PINNED_VENDOR_SHA256 = {
    "runtime.js": "4510B13162748597896C5CA45E3FD509499BE9F670AEDDB7E7BF51A128B1A7E6",
    "upstream.js": "CAD63C8EE9F907F9773772AC8CA03EBBE21F85CD9EF75C1D6B2C430EA8795290",
    "LICENSES/shaders-LICENSE": "EEAAA26F5C65CB6DFEBF1C098AC2375FDCDB497CEBF105B0542F229482B106F4",
}


def pinned_vendor_hash_mismatches(root: Path | str) -> list[str]:
    """Return missing or modified pinned shader runtime, upstream bundle, or MIT notice."""
    root_path = Path(root)
    mismatches = []
    for relative, expected in PINNED_VENDOR_SHA256.items():
        candidate = root_path.joinpath(*relative.split("/"))
        digest = hashlib.sha256()
        try:
            with candidate.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            mismatches.append(relative)
            continue
        if digest.hexdigest().upper() != expected:
            mismatches.append(relative)
    return mismatches


def _effects() -> dict[str, dict]:
    if not RUNTIME.is_file():
        raise RuntimeError(f"Artboard shader host not found: {RUNTIME}")
    source = RUNTIME.read_text(encoding="utf-8")
    marker = "var EFFECT_META = "
    start = source.find(marker)
    end = source.find("\n  };", start)
    if start < 0 or end < 0:
        raise RuntimeError("unable to read EFFECT_META from vendor/shaders/runtime.js")
    raw = source[start + len(marker):end + 4].strip()
    try:
        effects = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid EFFECT_META JSON in runtime.js: {exc}") from exc
    if not isinstance(effects, dict) or not effects:
        raise RuntimeError("EFFECT_META is empty")
    return effects


def _reject_json_constant(constant: str):
    raise ValueError(f"non-finite JSON number is not allowed: {constant}")


def _validate_finite_json(value, path: str = "params") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite JSON numbers")
    elif isinstance(value, int) and not isinstance(value, bool):
        try:
            if not math.isfinite(float(value)):
                raise ValueError(f"{path} must contain only finite JSON numbers")
        except OverflowError as exc:
            raise ValueError(f"{path} integer is outside the finite JSON range") from exc
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_finite_json(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_finite_json(item, f"{path}.{key}")


def _params(raw: str | None, speed: float | None, meta: dict) -> dict:
    if raw:
        try:
            value = json.loads(raw, parse_constant=_reject_json_constant)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--params must be a JSON object: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("--params must be a JSON object")
    else:
        value = {}
    allowed = set(meta.get("params", []))
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValueError("unsupported parameter(s) for this effect: " + ", ".join(extra))
    if speed is not None:
        if "speed" not in allowed:
            raise ValueError("--speed is not supported by this upstream effect")
        value["speed"] = speed
    _validate_finite_json(value)
    return value


def _canvas(fx: str, params: dict, freeze: bool) -> str:
    encoded = html.escape(json.dumps(
        params, ensure_ascii=False, separators=(",", ":"), allow_nan=False), quote=True)
    frozen = ' data-freeze="true"' if freeze else ' data-freeze="false"'
    return (f'<canvas class="ab-shader" data-fx="{html.escape(fx, quote=True)}"'
            f' data-webgpu-required="true" data-params="{encoded}"{frozen}'
            ' style="position:absolute;inset:0;width:100%;height:100%;z-index:0;'
            'pointer-events:none"></canvas>')


def _snippet(fx: str, params: dict, dynamic: bool) -> str:
    canvas = _canvas(fx, params, not dynamic)
    return ("<!-- Local vendor files are required; place below content inside a positioned wrapper. -->\n"
            + canvas + '\n<script src="vendor/shaders/upstream.js"></script>'
            + '\n<script src="vendor/shaders/runtime.js"></script>\n')


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def inspect_png(path: Path) -> dict:
    """Decode 8-bit RGB/RGBA PNG scanlines and measure sampled color variation."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Kiln output is not a PNG")
    offset = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        if len(chunk) != length:
            raise RuntimeError("truncated PNG chunk")
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            if interlace:
                raise RuntimeError("interlaced PNG is not supported by the local pixel check")
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
        offset += length + 12
    if not width or not height:
        raise RuntimeError("PNG has no valid IHDR")
    channels = {2: 3, 6: 4}.get(color_type)
    if bit_depth != 8 or channels is None:
        raise RuntimeError(f"unsupported PNG pixel format: bit_depth={bit_depth}, color_type={color_type}")
    bpp, stride = channels, width * channels
    raw = zlib.decompress(compressed)
    if len(raw) != height * (stride + 1):
        raise RuntimeError("PNG scanline data length does not match its dimensions")
    prev = bytearray(stride)
    colors: set[tuple[int, int, int]] = set()
    visible_samples = 0
    luma_min, luma_max = 255, 0
    sample_step = max(1, (width * height) // 50000)
    pixel_index = 0
    pos = 0
    for _y in range(height):
        filt = raw[pos]
        source = raw[pos + 1:pos + 1 + stride]
        pos += stride + 1
        row = bytearray(stride)
        if filt > 4:
            raise RuntimeError(f"unknown PNG filter type {filt}")
        for i, value in enumerate(source):
            left = row[i - bpp] if i >= bpp else 0
            above = prev[i]
            upper_left = prev[i - bpp] if i >= bpp else 0
            if filt == 1:
                predictor = left
            elif filt == 2:
                predictor = above
            elif filt == 3:
                predictor = (left + above) // 2
            elif filt == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                predictor = 0
            row[i] = (value + predictor) & 255
        for x in range(width):
            if pixel_index % sample_step == 0:
                base = x * bpp
                alpha = row[base + 3] if channels == 4 else 255
                if alpha > 0:
                    visible_samples += 1
                    r, g, b = row[base], row[base + 1], row[base + 2]
                    colors.add((r, g, b))
                    luma = (2126 * r + 7152 * g + 722 * b) // 10000
                    luma_min, luma_max = min(luma_min, luma), max(luma_max, luma)
            pixel_index += 1
        prev = row
    if channels == 4 and visible_samples == 0:
        raise RuntimeError("shader render appears fully transparent (sampled visible pixels=0)")
    if len(colors) < 8 or luma_max - luma_min < 8:
        raise RuntimeError(
            f"shader render appears blank/flat (sampled colors={len(colors)}, luma_range={luma_max-luma_min}); "
            "check the upstream WebGPU render, adapter readiness, effect props, and canvas size"
        )
    return {"width": width, "height": height, "sampled_unique_colors": len(colors),
            "visible_samples": visible_samples, "luma_range": [luma_min, luma_max], "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def _windows_process_descendants(root_pid: int) -> list[int] | None:
    """Snapshot descendant PIDs even when the original parent has already exited."""
    import ctypes
    from ctypes import wintypes

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        snapshot_fn = kernel32.CreateToolhelp32Snapshot
        snapshot_fn.argtypes = [wintypes.DWORD, wintypes.DWORD]
        snapshot_fn.restype = wintypes.HANDLE
        first_fn = kernel32.Process32FirstW
        first_fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
        first_fn.restype = wintypes.BOOL
        next_fn = kernel32.Process32NextW
        next_fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
        next_fn.restype = wintypes.BOOL
        close_fn = kernel32.CloseHandle
        close_fn.argtypes = [wintypes.HANDLE]
        close_fn.restype = wintypes.BOOL
        snapshot = snapshot_fn(0x00000002, 0)  # TH32CS_SNAPPROCESS
        if not snapshot or snapshot == ctypes.c_void_p(-1).value:
            return None
        children: dict[int, list[int]] = {}
        try:
            entry = ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(entry)
            if first_fn(snapshot, ctypes.byref(entry)):
                while True:
                    pid = int(entry.th32ProcessID)
                    parent = int(entry.th32ParentProcessID)
                    if pid:
                        children.setdefault(parent, []).append(pid)
                    if not next_fn(snapshot, ctypes.byref(entry)):
                        break
        finally:
            close_fn(snapshot)
    except (AttributeError, OSError, TypeError, ValueError):
        return None

    descendants = []
    pending = [int(root_pid)]
    seen = {int(root_pid)}
    while pending:
        parent = pending.pop()
        for pid in children.get(parent, []):
            if pid not in seen:
                seen.add(pid)
                descendants.append(pid)
                pending.append(pid)
    return descendants


def _terminate_process_tree(proc, *, windows: bool | None = None,
                            descendants=()) -> bool:
    """Terminate and reap the export process plus its browser/Kiln descendants."""
    is_windows = os.name == "nt" if windows is None else windows
    tree_terminated = False
    root_running = proc.poll() is None
    if is_windows:
        known_descendants = {int(pid) for pid in descendants if int(pid) != int(proc.pid)}
        if root_running:
            try:
                result = subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False, timeout=15)
                if result.returncode == 0:
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        pass
                    tree_terminated = proc.poll() is not None
            except (OSError, subprocess.SubprocessError):
                tree_terminated = False
        if not tree_terminated or known_descendants:
            discovered = set(_windows_process_descendants(proc.pid) or [])
            known_descendants.update(discovered)
            for pid in reversed(sorted(known_descendants)):
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=False, timeout=15)
                except (OSError, subprocess.SubprocessError):
                    pass
        process_table = _proc._windows_process_table()
        if process_table is not None:
            live_tracked = known_descendants.intersection(process_table)
            tree_terminated = proc.poll() is not None and not live_tracked
        elif not known_descendants:
            remaining = _windows_process_descendants(proc.pid)
            tree_terminated = remaining == [] and proc.poll() is not None
    else:
        try:
            # A process group can outlive its original leader; still signal it
            # after proc.poll() reports the leader has exited.
            os.killpg(proc.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            tree_terminated = True
        except ProcessLookupError:
            tree_terminated = proc.poll() is not None
        except (PermissionError, OSError):
            tree_terminated = False
    if not tree_terminated and proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    if proc.poll() is None:
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False
    return tree_terminated and proc.poll() is not None


def _has_nested_kiln_timeout(*streams: str) -> bool:
    for text in streams:
        for line in reversed((text or "").splitlines()):
            try:
                payload = json.loads(line)
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict) and payload.get("error") == "KILN_CLI_TIMEOUT":
                return True
    return False


def _run_export_with_timeout(command: list[str], *, cwd: str, env: dict,
                             timeout: int = 240) -> subprocess.CompletedProcess:
    # On POSIX, export.py's nested Kiln process joins this wrapper-owned group.
    # If its own timeout fires first, the JSON marker below makes this wrapper kill
    # the group after export.py returns, including orphaned browser pipe holders.
    env = dict(env)
    env["ARTBOARD_INHERIT_PROCESS_GROUP"] = "1"
    options = {
        "cwd": cwd, "env": env, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
        "text": True, "encoding": "utf-8", "errors": "replace",
    }
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        options["start_new_session"] = True
    proc, job = _proc.popen_with_tree(command, **options)
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if job is not None:
                terminated = job.terminate()
            else:
                terminated = _terminate_process_tree(proc)
            stdout = stderr = ""
            state = "process tree termination unverified"
            if terminated:
                try:
                    stdout, stderr = proc.communicate(timeout=10)
                    state = "process tree terminated"
                except subprocess.TimeoutExpired as cleanup_exc:
                    stdout = cleanup_exc.output or exc.output or ""
                    stderr = cleanup_exc.stderr or exc.stderr or ""
                    state = "process tree termination succeeded but pipe closure timed out"
            else:
                stdout = exc.output or ""
                stderr = exc.stderr or ""
                for stream in (proc.stdout, proc.stderr):
                    if stream:
                        try:
                            stream.close()
                        except OSError:
                            pass
            detail = (stderr or stdout or "")
            if isinstance(detail, bytes):
                detail = detail.decode("utf-8", "replace")
            detail = detail.strip()[-4000:]
            raise RuntimeError(
                f"Kiln WebGPU export timed out after {timeout} seconds; {state}.\n{detail}") from exc
        if job is not None and not job.wait_empty(timeout=0.5):
            active = job.active_processes()
            terminated = job.terminate()
            state = "descendant tree terminated" if terminated else "descendant cleanup unverified"
            raise RuntimeError(
                f"Kiln WebGPU export exited with live Job Object members; {state}: {active}")
        if os.name != "nt" and _has_nested_kiln_timeout(stdout, stderr):
            if not _terminate_process_tree(proc):
                raise RuntimeError(
                    "Nested Kiln timeout reported but wrapper process-group cleanup was not verified")
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    finally:
        if job is not None:
            job.close()


def _pending_png_path(out: Path) -> Path:
    """Reserve a same-directory temporary PNG with a bounded Windows component name."""
    fd, pending_name = tempfile.mkstemp(prefix=".artboard-shader-pending-",
                                        suffix=".png", dir=str(out.parent))
    os.close(fd)
    os.unlink(pending_name)  # Kiln 应自行创建,不能把空占位当成有效导出
    return Path(pending_name)


def bake(fx: str, params: dict, out: Path, width: int, height: int,
         overwrite: bool, kiln_path: str | None = None) -> dict:
    if not EXPORT.is_file():
        raise RuntimeError(f"Artboard exporter not found: {EXPORT}")
    if not RUNTIME.is_file() or not UPSTREAM_RUNTIME.is_file():
        raise RuntimeError("official shader runtime files are missing under vendor/shaders")
    mismatched = pinned_vendor_hash_mismatches(RUNTIME.parent)
    if mismatched:
        raise RuntimeError("SHADER_VENDOR_HASH_MISMATCH: " + ", ".join(mismatched))
    metadata = _effects().get(fx)
    if metadata is None:
        raise ValueError(f"unknown effect {fx!r}")
    if "speed" in metadata.get("params", []):
        params.setdefault("speed", 0)
    out = out.expanduser().resolve()
    if out.suffix.lower() != ".png":
        raise ValueError("--out must use a .png extension")
    if out.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {out}; pass --overwrite")
    out.parent.mkdir(parents=True, exist_ok=True)
    pending = _pending_png_path(out)
    try:
        with tempfile.TemporaryDirectory(prefix="artboard-shader-") as temp:
            work = Path(temp)
            vendor = work / "vendor" / "shaders"
            vendor.mkdir(parents=True)
            shutil.copy2(RUNTIME, vendor / "runtime.js")
            shutil.copy2(UPSTREAM_RUNTIME, vendor / "upstream.js")
            canvas = _canvas(fx, params, True)
            page = work / "shader.html"
            page.write_text(
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                f"<style>*{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px;"
                f"overflow:hidden;background:#101018}}.stage{{position:relative;width:{width}px;height:{height}px;overflow:hidden}}"
                "</style></head><body><main class=\"stage\">" + canvas +
                "</main><script src=\"vendor/shaders/upstream.js\"></script>"
                "<script src=\"vendor/shaders/runtime.js\"></script></body></html>",
                encoding="utf-8")
            command = [sys.executable, str(EXPORT), "--source", str(page), "--output", str(pending),
                       "--format", "PNG", "--width", str(width), "--height", str(height),
                       "--scale", "1", "--webgpu"]
            child_env = os.environ.copy()
            if kiln_path:
                child_env["ARTBOARD_KILN_CLI"] = str(Path(kiln_path).expanduser().resolve())
            result = _run_export_with_timeout(command, cwd=str(ROOT), env=child_env, timeout=240)
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()[-4000:]
                raise RuntimeError(f"Kiln WebGPU export failed ({result.returncode}):\n{detail}")
        measured = inspect_png(pending)
        if measured["width"] != width or measured["height"] != height:
            raise ValueError(f"Kiln PNG 尺寸不匹配:请求 {width}×{height},实际 "
                             f"{measured['width']}×{measured['height']};原输出保留")
        if out.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite {out}; pass --overwrite")
        os.replace(pending, out)
        return {"ok": True, "fx": fx, "output": str(out), **measured,
                "upstream_version": "4.0.4", "exporter": "scripts/export.py --webgpu → Kiln", "static": True}
    finally:
        try:
            pending.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="使用官方 shader-effects-inc/shaders WebGPU runtime")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="列出打包的官方 upstream 效果映射")
    action.add_argument("--embed", metavar="FX", help="输出使用本地官方 bundle 的 canvas 与 script 标签")
    action.add_argument("--bake", metavar="FX", help="通过 Kiln --webgpu 导出静态 PNG 并检查像素变化")
    parser.add_argument("--out", type=Path, help="--bake 的 PNG 输出路径")
    parser.add_argument("--params", help="官方组件参数 JSON 对象；参数按所选效果校验")
    parser.add_argument("--speed", type=float, help="覆盖官方组件的 speed 参数(用于 dynamic embed)")
    parser.add_argument("--dynamic", action="store_true", help="--embed 动效模式(默认等首帧后冻结)")
    parser.add_argument("--width", type=int, default=900, help="烘焙宽度 CSS px (默认 900)")
    parser.add_argument("--height", type=int, default=383, help="烘焙高度 CSS px (默认 383)")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已有 PNG")
    parser.add_argument("--kiln", help="显式 Kiln CLI 路径(或设置 ARTBOARD_KILN_CLI)")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        effects = _effects()
        if args.list:
            print(json.dumps([{"name": name, **metadata}
                              for name, metadata in effects.items()], ensure_ascii=False, indent=2))
            return 0
        fx = args.embed or args.bake
        if fx not in effects:
            raise ValueError(f"unknown effect {fx!r}; run `python scripts/shader_fx.py --list`")
        metadata = effects[fx]
        params = _params(args.params, args.speed, metadata)
        if args.embed:
            print(_snippet(fx, params, args.dynamic), end="")
            return 0
        if args.dynamic:
            raise ValueError("--bake is static; use --embed FX --dynamic for video cards")
        if "speed" in metadata.get("params", []) and params.get("speed", 0) != 0:
            raise ValueError("static --bake requires speed=0; use --embed FX --dynamic for motion")
        if not args.out:
            raise ValueError("--bake requires --out <file.png>")
        if not 16 <= args.width <= 4096 or not 16 <= args.height <= 4096:
            raise ValueError("--width/--height must be in 16..4096")
        print(json.dumps(bake(fx, params, args.out, args.width, args.height,
                              args.overwrite, args.kiln), ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
