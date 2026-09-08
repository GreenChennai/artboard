"""artboard 复刻比对:参考图 vs 复刻导出图并排拼接,供视觉逐项核对。

用法:
  python compare.py <参考图> <复刻图> [-o compare.png]
"""

import argparse
import sys

from PIL import Image, ImageDraw


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("reference")
    p.add_argument("render")
    p.add_argument("-o", "--out", default="compare.png")
    args = p.parse_args()

    a = Image.open(args.reference).convert("RGB")
    b = Image.open(args.render).convert("RGB")
    H = 1400
    a = a.resize((int(a.width * H / a.height), H))
    b = b.resize((int(b.width * H / b.height), H))
    gap, label_h = 24, 56
    W = a.width + gap + b.width
    canvas = Image.new("RGB", (W, H + label_h + gap), "#181109")
    canvas.paste(a, (0, label_h + gap))
    canvas.paste(b, (a.width + gap, label_h + gap))
    d = ImageDraw.Draw(canvas)
    d.text((8, 12), f"REFERENCE  {args.reference}", fill="#e0a458")
    d.text((a.width + gap + 8, 12), f"RENDER  {args.render}", fill="#2ee6a8")
    canvas.save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
