"""Build the map player HTML (assets/map/demo/map-player.html) from template + SVG + routes.

  python scripts/build_player.py [--svg assets/map/samples/svg-cbd-dark-tech.svg]

模板里的 `__SVG__` / `__ROUTES__` / `__ZONES__` / `__BUILD__` 占位符由本脚本注入;
产物是**自包含单文件**(双击即开),可直接当 H5 大屏素材,或交给 CutFlow 录屏。
验收:改完模板/播放器后跑 scripts/test_v7.py(V1-V12)。
"""
import argparse, datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join("assets", "map", "demo")


def fit_svg(text: str) -> str:
    """把 SVG 根节点的固定 width/height 换成 100%,让播放器缩放铺满自身容器。

    原实现是 `replace('width="1600" height="1917"', ...)`:换了 bbox / 尺寸后
    字符串对不上,**静默不改**(隐藏 div 里会按原始像素参与布局)。这里按属性改,
    与具体尺寸解耦。
    """
    text = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"', r'\1 width="100%"', text, count=1)
    return re.sub(r'(<svg[^>]*?)\sheight="[^"]*"', r'\1 height="100%"', text, count=1)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg", default="assets/map/samples/svg-cbd-dark-tech.svg")
    ap.add_argument("--routes", default="assets/map/routes.json")
    ap.add_argument("--points", default="assets/map/points.cbd.json")
    ap.add_argument("--template", default=os.path.join(DEMO, "map-player.template.html"))
    ap.add_argument("--out", default=os.path.join(DEMO, "map-player.html"))
    args = ap.parse_args()

    with open(os.path.join(ROOT, args.template), encoding="utf-8") as f:
        tpl = f.read()
    with open(os.path.join(ROOT, args.svg), encoding="utf-8") as f:
        svg = fit_svg(f.read())
    with open(os.path.join(ROOT, args.routes), encoding="utf-8") as f:
        routes = f.read()
    with open(os.path.join(ROOT, args.points), encoding="utf-8") as f:
        pts = json.load(f)

    zones = {p["name"].replace(" ", ""): p.get("zone", "") for p in pts}
    stamp = datetime.datetime.now().strftime("%m-%d %H:%M")
    out = (tpl.replace("__SVG__", svg).replace("__ROUTES__", routes)
              .replace("__ZONES__", json.dumps(zones, ensure_ascii=False))
              .replace("__BUILD__", stamp))

    p = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"built {p} ({len(out)//1024} KB)")


if __name__ == "__main__":
    main()
