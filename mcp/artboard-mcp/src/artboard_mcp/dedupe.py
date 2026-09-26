"""查重薄壳:pHash 复用 scripts/_img_probe.py(单一真相源,不写第二套 DCT)。"""

from __future__ import annotations

import os
import sys

_SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))  # …/mcp/artboard-mcp/src/artboard_mcp/ → skill 根
_SCRIPTS = os.path.join(_SKILL, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _img_probe import _phash  # noqa: E402


def dedupe(dir_or_files: str | list[str], threshold: int = 6) -> dict:
    """对目录(递归)或文件清单做 pHash 查重;只报告不删图,keeper = 字母序靠前者。"""
    import pathlib
    if isinstance(dir_or_files, str):
        p = pathlib.Path(dir_or_files)
        if p.is_dir():
            files = sorted(q for q in p.rglob("*")
                           if q.is_file() and q.suffix.lower() in
                           {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"})
        elif p.is_file():
            files = [p]
        else:
            return {"ok": False, "error": "NOT_FOUND", "hint": f"路径不存在: {dir_or_files}"}
    else:
        files = [pathlib.Path(s) for s in dir_or_files]
    if len(files) < 2:
        return {"ok": False, "error": "TOO_FEW", "hint": "查重需要 ≥2 张图"}
    hashes, warnings = {}, []
    for f in files:
        try:
            from PIL import Image
            with Image.open(f) as img:
                hashes[str(f)] = _phash(img)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{f.name}: 无法解码({type(exc).__name__})")
    names = sorted(hashes)
    dups: list[list] = []
    dropped: set[str] = set()
    for i, a in enumerate(names):
        if a in dropped:
            continue
        for b in names[i + 1:]:
            if b in dropped:
                continue
            dist = (hashes[a] ^ hashes[b]).bit_count()
            if dist <= threshold:
                dups.append([a, b, dist])
                dropped.add(b)
    return {"ok": True, "count": len(names), "dups": dups,
            "kept": [n for n in names if n not in dropped],
            "threshold": threshold, "warnings": warnings}
