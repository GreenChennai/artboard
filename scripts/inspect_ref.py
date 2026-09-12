"""artboard 复刻测量:参考图像素普查工具(证据链协议,见 references/replicate.md)。

复刻纪律:每个颜色和度量都必须追溯到测量。裸眼估的 hex 不写进 CSS。

用法:
  python inspect_ref.py grid  <参考图> [-o grid.png] [--pitch 100 --minor 20]  # 带标注网格(先看后量)
  python inspect_ref.py census <参考图> --box x0,y0,x1,y1                      # 分区普查(flat/all/ink)
  python inspect_ref.py bbox  <参考图> --box x0,y0,x1,y1 [--bg auto] [--tol 12] # 区内内容外接框(测边距)
  python inspect_ref.py crop  <参考图> --box x0,y0,x1,y1 -o img/photo-01.png   # 按测得框裁出素材
"""

import argparse
import os
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont


def _save(im: Image.Image, path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)  # 协议默认往 img/ 裁图,新项目目录尚不存在
    im.save(path)


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def _lum(rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _load(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def _box(s: str, size) -> tuple:
    x0, y0, x1, y1 = (int(v) for v in s.split(","))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(size[0], x1), min(size[1], y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        sys.exit(f"box 无效或太小: {s} (图 {size[0]}x{size[1]})")
    return x0, y0, x1, y1


def cmd_grid(args) -> None:
    im = _load(args.image)
    pitch, minor = args.pitch, args.minor
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for x in range(0, im.width, minor):
        major = x % pitch == 0
        d.line([(x, 0), (x, im.height)], fill=(255, 0, 128, 60 if major else 25), width=2 if major else 1)
    for y in range(0, im.height, minor):
        major = y % pitch == 0
        d.line([(0, y), (im.width, y)], fill=(255, 0, 128, 60 if major else 25), width=2 if major else 1)
    try:
        font = ImageFont.load_default(size=max(14, pitch // 4))
    except TypeError:
        font = ImageFont.load_default()
    for x in range(0, im.width, pitch):
        d.text((x + 4, 2), str(x), fill=(255, 0, 128, 255), font=font, stroke_width=2, stroke_fill=(255, 255, 255, 255))
        d.text((x + 4, im.height - pitch // 4 - 6), str(x), fill=(255, 0, 128, 255), font=font, stroke_width=2, stroke_fill=(255, 255, 255, 255))
    for y in range(pitch, im.height, pitch):
        d.text((2, y + 2), str(y), fill=(255, 0, 128, 255), font=font, stroke_width=2, stroke_fill=(255, 255, 255, 255))
    out = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    _save(out, args.out)
    print(f"{args.out}  (图 {im.width}x{im.height}, pitch={pitch}, minor={minor})")


def cmd_census(args) -> None:
    im = _load(args.image)
    box = _box(args.box, im.size)
    reg = im.crop(box)
    w, h = reg.size
    if w * h > 4_000_000:
        print(f"warn: 分区 {w}x{h} 过大,普查较慢;建议 <2000x2000", file=sys.stderr)
    px = reg.load()
    print(f"box={box}  size={w}x{h}  ({args.image})")

    # 真填充:与上下左右四邻全等的像素(抗锯齿边不算)
    flat = Counter()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            p = px[x, y]
            if p == px[x - 1, y] and p == px[x + 1, y] and p == px[x, y - 1] and p == px[x, y + 1]:
                flat[p] += 1
    total = max(1, (w - 2) * (h - 2))
    print("[flat fills] 真填充 top3(底色/卡片大面积色块看这里)")
    for c, n in flat.most_common(3):
        print(f"  {_hex(c)}  {n} px  {100 * n / total:.1f}%")
    if not flat:
        print("  (无——分区太小或全是渐变/照片,改用 all pixels)")

    # 全像素 top(徽章/圆点/小色块;必要时缩小 box 只留核心)
    allpix = Counter()
    for y in range(h):
        for x in range(w):
            allpix[px[x, y]] += 1
    print("[all pixels] 全像素 top3(徽章/圆点小块看这里)")
    for c, n in allpix.most_common(3):
        print(f"  {_hex(c)}  {n} px  {100 * n / (w * h):.1f}%")

    # 文字墨色:最暗 5% 的均值(文字区的众数色是背景,不是文字色)
    ranked = sorted(allpix.elements(), key=_lum)
    core = ranked[: max(16, len(ranked) // 20)]
    r = sum(p[0] for p in core) // len(core)
    g = sum(p[1] for p in core) // len(core)
    b = sum(p[2] for p in core) // len(core)
    print(f"[ink core] 最暗5%均值(文字墨色)  {_hex((r, g, b))}  (n={len(core)})")


def cmd_bbox(args) -> None:
    im = _load(args.image)
    box = _box(args.box, im.size)
    reg = im.crop(box)
    w, h = reg.size
    px = reg.load()
    if args.bg == "auto":  # 分区边框环的众数色当背景
        ring = Counter()
        for x in range(w):
            ring[px[x, 0]] += 1
            ring[px[x, h - 1]] += 1
        for y in range(h):
            ring[px[0, y]] += 1
            ring[px[w - 1, y]] += 1
        bg = ring.most_common(1)[0][0]
    else:
        bg = tuple(int(args.bg[i:i + 2], 16) for i in (1, 3, 5))

    def diff(p):
        return max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2]))

    x0 = y0 = w  # 内容外接框
    x1 = y1 = -1
    for y in range(h):
        for x in range(w):
            if diff(px[x, y]) > args.tol:
                x0, y0 = min(x0, x), min(y0, y)
                x1, y1 = max(x1, x), max(y1, y)
    print(f"bg={_hex(bg)}{'(auto)' if args.bg == 'auto' else ''}  tol={args.tol}  box={box}")
    if x1 < 0:
        print("未检出与背景差异 >tol 的内容(空区/纯底色)")
        return
    print(f"内容外接框: 绝对 ({box[0] + x0},{box[1] + y0})-({box[0] + x1 + 1},{box[1] + y1 + 1})  size {x1 - x0 + 1}x{y1 - y0 + 1}")
    print(f"insets 相对box: left={x0} top={y0} right={w - 1 - x1} bottom={h - 1 - y1}")
    print("圆角估算: 外接框角部第一个非背景像素的偏移(px),可用 grid 图目测复核")


def cmd_crop(args) -> None:
    im = _load(args.image)
    box = _box(args.box, im.size)
    out = im.crop(box)
    if args.scale != 1:
        out = out.resize((round(out.width * args.scale), round(out.height * args.scale)), Image.LANCZOS)
    _save(out, args.out)
    print(f"{args.out}  crop={box}  原始 {box[2] - box[0]}x{box[3] - box[1]}px → 输出 {out.width}x{out.height}px")
    print('登记: img/crops.json 写 {"%s": [%d,%d,%d,%d]}' % (
        args.out.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0], *box))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("grid", "census", "bbox", "crop"):
        sp = sub.add_parser(name)
        sp.add_argument("image")
        if name == "grid":
            sp.add_argument("-o", "--out", default="grid.png")
            sp.add_argument("--pitch", type=int, default=100)
            sp.add_argument("--minor", type=int, default=20)
        else:
            sp.add_argument("--box", required=True, help="x0,y0,x1,y1 参考图绝对像素")
        if name == "bbox":
            sp.add_argument("--bg", default="auto", help="auto=边框环众数 或 #RRGGBB")
            sp.add_argument("--tol", type=int, default=12)
        if name in ("bbox", "crop"):
            pass
        if name == "crop":
            sp.add_argument("-o", "--out", required=True)
            sp.add_argument("--scale", type=float, default=1.0)
        sp.set_defaults(func={"grid": cmd_grid, "census": cmd_census, "bbox": cmd_bbox, "crop": cmd_crop}[name])
    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
