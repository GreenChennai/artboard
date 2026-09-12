"""artboard 复刻比对:参考图 vs 复刻导出图并排拼接,供视觉逐项核对。

用法:
  python compare.py <参考图> <复刻图> [-o compare.png]
  python compare.py <参考图> <复刻图> --region 0,0,1,0.25 -o compare-top.png   # 局部放大(比例坐标)
"""
import argparse
import sys

from PIL import Image, ImageDraw, ImageChops, ImageStat


def _prep(path: str, region, H: int):
    im = Image.open(path).convert("RGB")
    if region:
        x0, y0, x1, y1 = region
        im = im.crop((round(im.width * x0), round(im.height * y0),
                      round(im.width * x1), round(im.height * y1)))
    return im.resize((max(1, int(im.width * H / im.height)), H))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("reference")
    p.add_argument("render")
    p.add_argument("-o", "--out", default="compare.png")
    p.add_argument("--region", default=None,
                   help="局部放大: x0,y0,x1,y1 各图自身的比例坐标 0–1,如 0,0,1,0.25")
    args = p.parse_args()

    region = tuple(float(v) for v in args.region.split(",")) if args.region else None
    a = _prep(args.reference, region, 1400)
    b = _prep(args.render, region, 1400)

    # ΔRGB 均值(数字锚点:哪轮比对降了,一眼看出修没修对)
    w = min(a.width, b.width)
    h = min(a.height, b.height)
    diff = ImageChops.difference(a.crop((0, 0, w, h)), b.crop((0, 0, w, h)))
    dr, dg, db = ImageStat.Stat(diff).mean
    print(f"ΔRGB 均值: R{dr:.1f} G{dg:.1f} B{db:.1f}  综合 {(dr + dg + db) / 3:.1f} (0=逐像素一致)")

    gap, label_h = 24, 56
    W = a.width + gap + b.width
    canvas = Image.new("RGB", (W, h + label_h + gap), "#181109")
    canvas.paste(a, (0, label_h + gap))
    canvas.paste(b, (a.width + gap, label_h + gap))
    d = ImageDraw.Draw(canvas)
    tag = f"  region={args.region}" if args.region else ""
    d.text((8, 12), f"REFERENCE  {args.reference}{tag}", fill="#e0a458")
    d.text((a.width + gap + 8, 12), f"RENDER  {args.render}", fill="#2ee6a8")
    canvas.save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
