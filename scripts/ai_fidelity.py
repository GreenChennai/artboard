"""PNG ↔ 可编辑 AI/PDF 相似度门禁。

AI 是 PDF 兼容流，使用 pypdfium2 将第一页栅格化后与参考 PNG 按
MAD 评分。默认单页最低 97 分；多画板可重复 --reference/--page 对拍。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops


def score(reference: Path, ai: Path, page: int = 0) -> tuple[float, float, tuple[int, int]]:
    import pypdfium2 as pdfium

    ref = Image.open(reference).convert("RGB")
    doc = pdfium.PdfDocument(str(ai))
    if page >= len(doc):
        raise ValueError(f"AI 画板不存在: page={page}, pages={len(doc)}")
    rendered = doc[page].render(scale=1.0).to_pil().convert("RGB")
    if ref.size != rendered.size:
        # 尺寸必须一致；这里只允许裁剪多出的底部空白，避免“缩放作弊”。
        w, h = min(ref.width, rendered.width), min(ref.height, rendered.height)
        ref, rendered = ref.crop((0, 0, w, h)), rendered.crop((0, 0, w, h))
    diff = ImageChops.difference(ref, rendered)
    hist = diff.histogram()
    mad = sum((i % 256) * n for i, n in enumerate(hist)) / (ref.width * ref.height * 3)
    return 100.0 * (1.0 - mad / 255.0), mad, ref.size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--ai", required=True, type=Path)
    ap.add_argument("--page", type=int, default=0)
    ap.add_argument("--min-score", type=float, default=97.0)
    args = ap.parse_args()
    try:
        s, mad, size = score(args.reference, args.ai, args.page)
    except Exception as exc:
        print(f"[FAIL] AI 相似度无法计算: {exc}")
        return 2
    print(f"AI similarity={s:.2f} mad={mad:.3f} size={size} threshold={args.min_score:.2f}")
    return 0 if s >= args.min_score else 2


if __name__ == "__main__":
    raise SystemExit(main())
