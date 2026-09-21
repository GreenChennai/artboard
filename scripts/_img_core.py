"""imageops 公共契约(《artboard-位图脚本库扩充-迭代指导书》§4):
JSON 信封 / 退出码 / 唯一尺寸真源 / 依赖探测 / 懒安装 / 批处理骨架 / 唯一默认值。
子命令禁止绕过本模块定义信封、退出码、PROFILES 与命名约定。"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

EXIT_OK, EXIT_PARTIAL, EXIT_USAGE, EXIT_DEP = 0, 1, 2, 3

# ---- 唯一默认值真源(§4.6):子命令禁止各自定义 quality/档位 -------------
PROFILES = {
    "web":      {"jpeg": 82, "webp": 82, "avif": 58, "png_mode": "lossless"},
    "web-hq":   {"jpeg": 90, "webp": 88, "avif": 68, "png_mode": "lossless"},
    "thumb":    {"jpeg": 72, "webp": 70, "avif": 45, "png_mode": "palette"},
    "print":    {"jpeg": 95, "webp": 95, "avif": 80, "png_mode": "lossless"},
    "platform": {"jpeg": 88, "webp": 85, "avif": 60, "png_mode": "lossless"},
}

# 统一命名 → (ffmpeg blend 模式, Pillow ImageChops 名或 None)(§5.4 C2 矩阵)
BLENDS = {
    "normal":      ("normal",     None),  # normal 走 paste
    "multiply":    ("multiply",   "multiply"),
    "screen":      ("screen",     "screen"),
    "overlay":     ("overlay",    "overlay"),
    "darken":      ("darken",     "darker"),
    "lighten":     ("lighten",    "lighter"),
    "hard-light":  ("hardlight",  "hard_light"),
    "soft-light":  ("softlight",  "soft_light"),
    "difference":  ("difference", "difference"),
    "exclusion":   ("exclusion",  None),
    "color-dodge": ("dodge",      None),
    "color-burn":  ("burn",       None),
}

INSTALL_WHITELIST = {"smartcrop", "opencv-python-headless", "numpy", "piexif"}

# 平台体积红线(唯一出处 references/material-catalog.md;此处只引用数值键)
SIZE_LIMITS = {"taobao_main": 3 * 1024 * 1024, "detail": 500 * 1024, "moments_ad": 300 * 1024}


def emit(obj: dict) -> None:
    """单行 JSON,ensure_ascii=False(对齐 cutout.py emit 口径)。"""
    print(json.dumps(obj, ensure_ascii=False))


def fail(cmd: str, code: str, detail: str = "", hint: str = "", fallback: str = "") -> int:
    """失败信封:末行必为合法 JSON(selfcheck.jsonfail 契约)。"""
    emit({"ok": False, "cmd": cmd, "error": code, "detail": detail,
          "hint": hint, "fallback": fallback})
    return EXIT_DEP if code.startswith("NO_") else EXIT_USAGE


def ok_envelope(cmd: str, results: list, warnings: list | None = None,
                engine: str | None = None, hint: str = "") -> int:
    degraded = any(r.get("degraded") for r in results)
    failed = sum(1 for r in results if r.get("error"))
    ok = bool(results) and failed == 0
    emit({"ok": ok, "cmd": cmd, "count": len(results),
          "engine": engine or (results[0].get("engine") if results else None),
          "results": results, "warnings": warnings or [],
          "degraded": degraded, "hint": hint})
    if not ok:
        return EXIT_USAGE
    return EXIT_PARTIAL if degraded else EXIT_OK


def load_pillow():
    try:
        from PIL import Image, ImageOps, ImageChops  # noqa: F401
        return True
    except ImportError:
        return False


def size_of(name: str) -> tuple[int, int]:
    """唯一尺寸真源:读 scaffold.SIZES(§4.7)。h==0 = 高度随内容。"""
    p = pathlib.Path(__file__).with_name("scaffold.py")
    spec = importlib.util.spec_from_file_location("_ab_scaffold", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if name not in mod.SIZES:
        raise KeyError(f"未知预设 {name};可用:{','.join(sorted(mod.SIZES))}")
    s = mod.SIZES[name]
    return int(s["w"]), int(s["h"])


def quality_for(args, fmt: str) -> int:
    """quality 唯一取值:显式 --quality > PROFILES[profile] > 82。"""
    if getattr(args, "quality", None):
        return int(args.quality)
    prof = PROFILES[getattr(args, "profile", None) or "web"]
    if fmt == "png":
        return 100
    return int(prof.get({"jpeg": "jpeg", "webp": "webp", "avif": "avif"}.get(fmt), 82))


def avif_crf(quality: int) -> int:
    """quality 0-100 → AV1 crf 0-63(唯一换算,§4.6)。"""
    return max(0, min(63, round((100 - quality) * 63 / 100)))


def need(mod: str, hint: str):
    """依赖探测:缺失 → NO_<MOD> 信封 + 退出 3,不静默。"""
    try:
        return __import__(mod)
    except ImportError as exc:
        raise SystemExit(fail("deps", f"NO_{mod.upper()}", str(exc), hint))


def install_missing(pkg: str) -> tuple[bool, str]:
    """§4.5 懒安装:仅白名单;显式授权才装;分报不宽 except。"""
    if pkg not in INSTALL_WHITELIST:
        return False, f"{pkg} 不在懒安装白名单:{','.join(sorted(INSTALL_WHITELIST))}"
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, "pip install 超时(600s)"
    except OSError as exc:
        return False, f"pip 启动失败: {exc}"
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "")[-400:]
    return True, ""


def ffmpeg_path() -> str | None:
    from _config import cfg  # noqa: PLC0415
    p = cfg("ffmpeg") or os.environ.get("ARTBOARD_FFMPEG") or shutil.which("ffmpeg")
    return p or None


def ffmpeg_caps() -> dict:
    """编码器级探测(§附录 C.2:只探『有没有 ffmpeg』不够)。"""
    exe = ffmpeg_path()
    if not exe:
        return {"available": False}
    try:
        v = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True,
                           text=True, errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    enc = v.stdout + v.stderr
    has = lambda name: name in enc  # noqa: E731
    return {"available": v.returncode == 0, "path": exe,
            "encoders": {"libwebp": has("libwebp"), "libsvtav1": has("libsvtav1"),
                         "libaom-av1": has("libaom-av1"), "libjxl": has("libjxl"),
                         "png": has(" png")}}

# 位置参数直接给目录时展开的默认扩展名(可用 --ext 覆盖)
DEFAULT_INPUT_EXTS = ("jpg", "jpeg", "png", "webp", "avif", "bmp", "tif", "tiff", "gif")


def _glob(pattern: str) -> list[pathlib.Path]:
    """glob,且支持**绝对模式**。

    `Path.glob()` 对绝对模式直接 `NotImplementedError`,而 `--in "E:/x/*.png"`
    是最自然的写法。绝对模式拆成「盘根 + 相对模式」两段再拼。
    """
    pat = pathlib.Path(pattern)
    if pat.is_absolute():
        anchor = pathlib.Path(pat.anchor)
        return list(anchor.glob(str(pat.relative_to(anchor))))
    return list(pathlib.Path().glob(pattern))


def input_expand(args) -> list[pathlib.Path]:
    """§4.8 输入展开:位置参数 / --in(glob)/ --in-dir / --from-list。

    位置参数**可以是目录**:给定目录时递归展开其中的图片文件(此前直接把
    目录当文件交给 PIL,`PermissionError: '.'`)。扩展名默认取常见
    图片集,可用 `--ext jpg,png` 收窄。
    """
    paths: list[pathlib.Path] = []
    exts = [e.strip().lstrip('.').lower()
            for e in (getattr(args, "ext", None) or "").split(',') if e.strip()]
    allow = set(exts) if exts else set(DEFAULT_INPUT_EXTS)
    for raw in list(getattr(args, "inputs", []) or []):
        p = pathlib.Path(raw)
        if p.is_dir():
            hits = sorted(q for q in p.rglob("*")
                          if q.is_file() and q.suffix.lower().lstrip('.') in allow)
            if not hits:
                raise SystemExit(fail(args.cmd, "INPUT_NOT_FOUND",
                                      f"目录下没有图片: {raw}",
                                      hint="白名单:" + ",".join(sorted(allow))
                                           + "(用 --ext 覆盖)"))
            paths.extend(hits)
        else:
            paths.append(p)
    for raw in list(getattr(args, "in_glob", []) or []):
        hits = sorted(_glob(raw))
        if not hits:
            raise SystemExit(fail(args.cmd, "INPUT_NOT_FOUND", f"glob 无命中: {raw}"))
        paths.extend(hits)
    if getattr(args, "in_dir", None):
        exts = [e.strip().lstrip('.').lower() for e in (args.ext or "").split(',') if e.strip()]
        if not exts:
            raise SystemExit(fail(args.cmd, "USAGE", "--in-dir 必须配 --ext(避免误吞)"))
        paths.extend(sorted(p for p in pathlib.Path(args.in_dir).iterdir()
                            if p.is_file() and p.suffix.lower().lstrip('.') in exts))
    if getattr(args, "from_list", None):
        for line in pathlib.Path(args.from_list).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                paths.append(pathlib.Path(line))
    # 去重保序
    seen, uniq = set(), []
    for p in paths:
        rp = str(p.resolve()) if p.exists() else str(p)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    if getattr(args, "max_files", None) and len(uniq) > args.max_files:
        raise SystemExit(fail(args.cmd, "TOO_MANY_FILES",
                              f"{len(uniq)} 个输入超过安全阀 --max-files {args.max_files}"))
    return uniq


def out_path_for(src: pathlib.Path, args, tag: str, ext: str) -> pathlib.Path:
    """§4.10 命名约定 + 版权前缀守卫(铁律 7)。"""
    base = src.stem
    tmpl = getattr(args, "name_template", None)
    if tmpl:
        if base.startswith("版权风险-") and "{name}" not in tmpl:
            raise SystemExit(fail(getattr(args, "cmd", ""), "COPYRIGHT_PREFIX_LOST",
                                  "模板会剥掉『版权风险-』前缀(=洗掉素材风险标记,违反铁律 7)",
                                  hint="模板必须含 {name},或去掉 --name-template"))
        name = tmpl.format(name=base, cmd=tag, ext=ext,
                           size=getattr(args, "size_tag", "") or "")
    else:
        name = f"{base}-{tag}.{ext}" if tag else f"{base}.{ext}"
    d = pathlib.Path(getattr(args, "out_dir", None) or src.parent)
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def parse_color(s: str, default=(255, 255, 255, 255)) -> tuple:
    """#rrggbb / #rrggbbaa / named → RGBA 元组;transparent → 全透明。"""
    if not s or s == "transparent":
        return (0, 0, 0, 0)
    s = s.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?", s)
    if m:
        v = m.group(1)
        a = int(m.group(2), 16) if m.group(2) else 255
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), a)
    from PIL import ImageColor  # noqa: PLC0415
    c = ImageColor.getrgb(s)
    return (c[0], c[1], c[2], 255) if len(c) == 3 else tuple(c)


RESAMPLE = {
    "lanczos": "LANCZOS", "bicubic": "BICUBIC", "bilinear": "BILINEAR",
    "hamming": "HAMMING", "box": "BOX", "nearest": "NEAREST",
}


def resample_of(name: str | None, upscaling: bool):
    """§4.6 重采样唯一默认:缩小 LANCZOS / 放大 BICUBIC / 显式覆盖。"""
    from PIL import Image  # noqa: PLC0415
    if name:
        return getattr(Image.Resampling, RESAMPLE[name])
    return getattr(Image.Resampling, "BICUBIC" if upscaling else "LANCZOS")


def encode_image(img, fmt: str, quality: int, args=None) -> tuple[bytes, dict]:
    """统一编码出口:返回 (bytes, meta{engine,format,degraded,warnings})。
    quality 语义唯一:0-100 感知质量(§4.6);AVIF 经 ffmpeg 时换算 crf。"""
    import io  # noqa: PLC0415
    fmt = fmt.lower().lstrip('.')
    warnings: list[str] = []
    degraded = False
    engine = "pillow"
    buf = io.BytesIO()
    if fmt in ("jpg", "jpeg"):
        img.convert("RGB").save(buf, "JPEG", quality=max(1, min(95, quality)),
                                optimize=bool(getattr(args, "optimize", False)),
                                progressive=bool(getattr(args, "progressive", False)))
        fmt = "jpeg"
    elif fmt == "png":
        img.save(buf, "PNG", optimize=bool(getattr(args, "optimize", False)))
    elif fmt == "webp":
        img.save(buf, "WEBP", quality=quality, lossless=bool(getattr(args, "lossless", False)))
    elif fmt == "avif":
        caps = ffmpeg_caps()
        if caps.get("available") and caps["encoders"]["libsvtav1"]:
            b, d = encode_avif_ffmpeg(img, quality)
            engine, degraded = "ffmpeg", d
            return b, {"engine": engine, "format": "avif", "degraded": degraded, "warnings": warnings}
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(buf, "AVIF", quality=quality)
        warnings.append("AVIF_ENGINE_FALLBACK")
        degraded = True
    elif fmt in ("tif", "tiff"):
        img.save(buf, "TIFF")
        fmt = "tiff"
    elif fmt == "bmp":
        img.convert("RGB").save(buf, "BMP")
    else:
        raise SystemExit(fail("encode", "UNSUPPORTED_FORMAT", fmt))
    return buf.getvalue(), {"engine": engine, "format": fmt, "degraded": degraded,
                            "warnings": warnings}


def encode_avif_ffmpeg(img, quality: int) -> tuple[bytes, bool]:
    """AVIF 经 ffmpeg libsvtav1(§2.2 陷阱 2:Pillow AVIF 面窄)。"""
    import io, tempfile  # noqa: PLC0415
    exe = ffmpeg_path()
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "in.png"
        img.save(src, "PNG")
        dst = pathlib.Path(td) / "out.avif"
        r = subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(src),
                            "-c:v", "libsvtav1", "-crf", str(avif_crf(quality)),
                            str(dst)], capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not dst.exists():
            raise RuntimeError(f"ffmpeg avif 失败: {(r.stderr or '')[-200:]}")
        return dst.read_bytes(), False


FORMAT_ALIASES = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp",
                  "avif": "avif", "tif": "tiff", "tiff": "tiff", "bmp": "bmp"}

ALPHA_CAPABLE = {"png", "webp", "avif", "tiff"}


def result_item(src: pathlib.Path, out: pathlib.Path | None, before: int, data: bytes | None,
                engine=None, quality=None, warnings=None, degraded=False, error=None) -> dict:
    item = {"input": str(src.resolve() if src.exists() else src),
            "output": str(out) if out else None,
            "size": None, "mode": None, "format": None,
            "bytes": len(data) if data is not None else None,
            "bytes_before": before or None,
            "ratio": round(len(data) / before, 4) if (data is not None and before) else None,
            "engine": engine, "quality": quality,
            "degraded": degraded, "warnings": warnings or [], "error": error}
    if out and pathlib.Path(out).exists():
        from PIL import Image  # noqa: PLC0415
        with Image.open(out) as im:
            item["size"] = list(im.size)
            item["mode"] = im.mode
            item["format"] = (im.format or "").lower()
    return item
