"""artboard 项目脚手架:在 artboard-studio/ 下生成海报项目(src/ + export/)。

用法:
  python scaffold.py <slug> [--size xhs|long|banner|kv|square|vertical]
                     [--fonts smiley-sans,source-han-sans] [--force]

- 复制所选字体的字体文件到 src/fonts/;复制 vendor JS 到 src/vendor/
- 生成 src/index.html 骨架:固定画布 + 已选字体的 @font-face + design tokens 占位
- 尺寸预设: xhs=1080x1440 long=2400xauto banner=1920x600 kv=1920x1080
             square=1080x1080 vertical=1080x1920 card=1063x638(90x54mm)
             a4p=1240x1754(A4) trifold=1754x1240(A4横,单面) rollup=2362x5906(80x200cm)
"""

import argparse
import json
import os
import shutil
import sys

from _config import cfg

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(SKILL_DIR, "fonts")
VENDOR_DIR = os.path.join(SKILL_DIR, "assets", "vendor")
STUDIO = cfg("studio_dir", r"E:\平日资料\GitHub\artboard-studio")
FONT_EXTS = (".ttf", ".otf", ".woff2", ".woff", ".ttc", ".otc")

SIZES = {
    "xhs":     {"w": 1080, "h": 1440},
    "long":    {"w": 2400, "h": 0},
    "banner":  {"w": 1920, "h": 600},
    "kv":      {"w": 1920, "h": 1080},
    "square":  {"w": 1080, "h": 1080},
    "vertical": {"w": 1080, "h": 1920},
    # ---- 印刷品类(scale 2 = 300dpi;rollup 为 150dpi 大幅面)----
    "card":    {"w": 1063, "h": 638},    # 名片 90×54mm 成品,导出 scale 1 即 300dpi
    "a4p":     {"w": 1240, "h": 1754},   # A4 竖版海报 210×297mm,scale 2 → 2480×3508
    "trifold": {"w": 1754, "h": 1240},   # 三折页单面 297×210mm,scale 2 → 3508×2480;正/背两个画布
    "rollup":  {"w": 2362, "h": 5906},   # 易拉宝 80×200cm,scale 2 → 4724×11811(150dpi)
}

# 字重轴:可变字体声明 100-900;单字重字体用具体值
VF_HINT = {"NotoSansSC-VF": True, "NotoSerifSC-VF": True}


def font_face_block(family: str, files: list[str]) -> str:
    f = files[0]
    url = f"fonts/{f}"
    fmt = "truetype" if f.lower().endswith((".ttf", ".ttc")) else \
        "opentype" if f.lower().endswith(".otf") else "woff2"
    weight = "100 900" if any(k in f for k in VF_HINT) else "normal"
    return (f"@font-face {{\n  font-family: '{family}';\n  src: url('{url}') format('{fmt}');\n"
            f"  font-weight: {weight};\n  font-display: block;\n}}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("--size", default="xhs", choices=list(SIZES))
    p.add_argument("--fonts", default="source-han-sans", help="逗号分隔的 fonts/ 目录名")
    p.add_argument("--force", action="store_true", help="允许写入已存在项目")
    args = p.parse_args()

    proj = os.path.join(STUDIO, args.slug)
    if os.path.exists(proj) and not args.force:
        print(json.dumps({"ok": False, "error": "EXISTS", "path": proj,
                          "hint": "换 slug 或 --force"}, ensure_ascii=False))
        return 1
    os.makedirs(os.path.join(proj, "src"), exist_ok=True)
    os.makedirs(os.path.join(proj, "export"), exist_ok=True)
    os.makedirs(os.path.join(proj, "src", "fonts"), exist_ok=True)
    os.makedirs(os.path.join(proj, "src", "vendor"), exist_ok=True)

    faces, font_vars = [], []
    for fam_dir in [s.strip() for s in args.fonts.split(",") if s.strip()]:
        src_dir = os.path.join(FONTS_DIR, fam_dir)
        if not os.path.isdir(src_dir):
            print(f"△ 字体目录不存在,跳过: {fam_dir}", file=sys.stderr)
            continue
        files = [f for f in os.listdir(src_dir) if f.lower().endswith(FONT_EXTS)]
        for f in files:
            shutil.copy2(os.path.join(src_dir, f),
                         os.path.join(proj, "src", "fonts", f))
        family = fam_dir.replace("-", " ").title().replace(" ", "")
        faces.append(font_face_block(family, files))
        font_vars.append(f"  --font-{fam_dir.replace('-', '-')}: '{family}';")

    for js in ("echarts.min.js", "gsap.min.js"):
        src = os.path.join(VENDOR_DIR, js)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(proj, "src", "vendor", js))

    size = SIZES[args.size]
    css_size = (f"width: {size['w']}px;" if size["h"] else
                f"width: {size['w']}px; /* 长图:高度随内容 */")
    html = INDEX_TEMPLATE.format(
        faces="\n".join(faces),
        font_vars="\n".join(font_vars) or "  /* --font-…: 未选字体,回退系统 */",
        canvas=css_size,
        w=size["w"],
    )
    with open(os.path.join(proj, "src", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    meta = {"slug": args.slug, "size": args.size, "width": size["w"],
            "height": size["h"], "fonts": args.fonts,
            "created_by": "artboard.scaffold"}
    with open(os.path.join(proj, "project.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(json.dumps({"ok": True, "project": proj, "size": args.size,
                      "fonts": args.fonts}, ensure_ascii=False))
    return 0


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>artboard · {{slug 占位}}</title>
<style>
/* ===== 字体(scaffold 自动生成) ===== */
{faces}

/* ===== 画布与全局 ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; background: #ffffff; }}
.poster {{
  position: relative;
  {canvas}
  overflow: hidden;
}}

/* ===== Design tokens(按风格分册填写) ===== */
:root {{
  --c-ink: #16130f;      /* 近黑文字 */
  --c-bg: #faf7f2;       /* 底色 */
  --c-primary: #2b4acb;  /* 主色 */
  --c-accent: #e84a5f;   /* 强调色(最多 1-2 个元素用) */
  --c-muted: #8a8578;    /* 辅助文字 */
{font_vars}
}}

/* ===== 内容从这里开始 ===== */
</style>
</head>
<body>
  <div class="poster">
    <!-- 画布 {w}px 宽;所有内容放这里面,溢出即隐藏 -->
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
