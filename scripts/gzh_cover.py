"""微信公众号双封面工作站:一次设计,三张产物(主封面/次条/合并预览图)。

用法:
  python gzh_cover.py new <slug> --title 文案 [--sub-title 次条标题] [--kicker 眉题]
                  [--sub 副题] [--footer 页脚] [--num 期号] [--theme blue|dark|warm|green]
                  [--fonts smiley-sans,source-han-sans] [--force]
  python gzh_cover.py export <项目目录|slug> [--only main|sub|merged] [--scale 2] [--outdir 目录]
  python gzh_cover.py merge <项目目录|slug> [--gap 57] [--bg "#f6f7f9"]   # 仅重拼合并图(不重导)

产物约定(项目目录 = <studio_dir>/<slug>/):
  src/index.html            主封面画布 900×383(2.35:1,头条)
  src/sub.html              次条封面画布 383×383(1:1,官方下限 200×200)
  export/cover-main-<slug>.png    头条主封面(默认 2x = 1800×766)
  export/cover-sub-<slug>.png     次条副封面(默认 2x = 766×766)
  export/cover-merged-<slug>.png  双封面合并图(Pillow 等高拼接,单张原始比例不变)

设计规范(证据与来源见 references/formats/gzh-cover.md 与 docs/gzh-spec-summary.md):
  - 头条封面 900×383(2.35:1)官方口径;转发/分享卡片只露中央 ~383×383,关键信息居中;
  - 次条封面 1:1,官方下限 200×200,主流 383×383(与头条等高,便于同稿联动与等高拼接);
  - 合并图 = 两张导出 PNG 按原始像素等高拼接(间隔默认 57px×scale),Pillow 纯拼接,
    不重新渲染 HTML → 单张内容零形变、零重采样。

输出:单行 JSON(ok/…);失败也输出 JSON(ok:false + error/hint),便于脚本链消费。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from _config import cfg, near_workspace  # noqa: E402

MAIN_W, MAIN_H = 900, 383      # 头条 2.35:1(官方口径)
SUB_W, SUB_H = 383, 383        # 次条 1:1(官方下限 200×200,主流与头条等高)
MERGE_GAP = 57                 # 合并图间隔(CSS px,随 scale 放大)

# 主题色板:黑白 + 一抹品牌色的瑞士网格基调,主/次条共用同一套 tokens
THEMES = {
    "blue":  {"bg": "#0f1b3d", "bg2": "#1b2f66", "ink": "#f5f7ff",
              "accent": "#3b82f6", "muted": "rgba(245,247,255,.72)",
              "line": "rgba(255,255,255,.18)"},
    "dark":  {"bg": "#16130f", "bg2": "#2c2620", "ink": "#faf7f2",
              "accent": "#e8b04b", "muted": "rgba(250,247,242,.70)",
              "line": "rgba(255,255,255,.18)"},
    "warm":  {"bg": "#fdf3e7", "bg2": "#f6e3cd", "ink": "#3a2c1e",
              "accent": "#c96f2e", "muted": "rgba(58,44,30,.62)",
              "line": "rgba(58,44,30,.16)"},
    "green": {"bg": "#12291c", "bg2": "#1d4029", "ink": "#f0f7f1",
              "accent": "#4ade80", "muted": "rgba(240,247,241,.70)",
              "line": "rgba(255,255,255,.18)"},
}


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def fail(error: str, hint: str = "", **extra) -> int:
    emit({"ok": False, "error": error, "hint": hint, **extra})
    return 1


def resolve_project(slug_or_dir: str) -> str:
    """参数既可以是 slug(在 studio_dir 下找),也可以是项目目录本身。"""
    if os.path.isdir(slug_or_dir):
        return os.path.abspath(slug_or_dir)
    studio = cfg("studio_dir", near_workspace("artboard-studio"))
    cand = os.path.join(studio, slug_or_dir)
    if os.path.isdir(cand):
        return os.path.abspath(cand)
    return ""


def check_kiln() -> tuple[str, str]:
    """与 export.py 相同的引擎发现逻辑(配置 → 兜底探测)。"""
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return "cli", cli
    for cand in (near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe")),
                 near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))):
        if cand and os.path.isfile(cand):
            return "cli", cand
    return "", ""


def run_export(source_html: str, output: str, width: int, height: int, scale: int) -> dict:
    """委托 scripts/export.py(保持单一导出链);返回其单行 JSON。"""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "export.py"),
           "--source", source_html, "--output", output,
           "--width", str(width), "--height", str(height),
           "--scale", str(scale), "--format", "PNG"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600,
                           encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "EXPORT_SPAWN_FAILED", "detail": str(exc),
                "hint": "手动执行: " + " ".join(cmd)}
    out = r.stdout or ""
    if isinstance(out, bytes):
        out = out.decode("utf-8", errors="replace")
    lines = [l for l in out.splitlines() if l.strip()]
    if lines:
        try:
            return json.loads(lines[-1])
        except ValueError:
            pass
    err = r.stderr or ""
    if isinstance(err, bytes):
        err = err.decode("utf-8", errors="replace")
    return {"ok": False, "error": "EXPORT_BAD_OUTPUT",
            "detail": err[-300:],
            "hint": "export.py 未输出合法 JSON"}


# ---------------------------------------------------------------- 字体

DEFAULT_FONTS = ("smiley-sans", "source-han-sans")

FMT_BY_EXT = {"ttf": "truetype", "ttc": "truetype", "otf": "opentype",
              "woff2": "woff2", "woff": "woff"}


def build_font_assets(fam_dirs: list[str]) -> tuple[str, str]:
    """生成 @font-face 块与 --font-* 变量。第一款 = 展示体(--font-display),
    第二款 = 正文体(--font-sans);只有一款时两者同族。"""
    faces, fam_names = [], []
    for fam in fam_dirs:
        src_dir = os.path.join(SKILL_DIR, "fonts", fam)
        if not os.path.isdir(src_dir):
            print(f"△ 字体目录不存在,跳过: {fam}", file=sys.stderr)
            continue
        files = sorted(f for f in os.listdir(src_dir)
                       if f.lower().endswith(tuple(FMT_BY_EXT)))
        family = fam.replace("-", " ").title().replace(" ", "")
        fam_names.append(family)
        for fn in files:
            ext = fn.rsplit(".", 1)[-1].lower()
            faces.append(
                f"@font-face {{ font-family: '{family}'; "
                f"src: url('fonts/{fam}/{fn}') format('{FMT_BY_EXT.get(ext, 'truetype')}'); "
                f"font-weight: 100 900; font-display: block; }}")
    if not fam_names:
        return "", ""
    display = fam_names[0]
    sans = fam_names[1] if len(fam_names) > 1 else fam_names[0]
    vars_block = (f"  --font-display: '{display}';\n"
                  f"  --font-sans: '{sans}';")
    return "\n".join(faces), vars_block


# ---------------------------------------------------------------- HTML 模板

def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") \
        .replace("\n", "<br>")


def main_html(w: int, h: int, t: dict, title: str, kicker: str, sub: str,
              footer: str, num: str, faces: str, font_vars: str) -> str:
    """主封面 900×383:居中版式——转发/分享卡片只露中央 383×383,
    关键信息(眉题/主标/副题)居中排布,期号与页脚作边缘装饰。"""
    kicker_html = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    footer_html = f'<div class="footer">{esc(footer)}</div>' if footer else ""
    num_html = f'<div class="num">{esc(num)}</div>' if num else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>gzh-main · {esc(title)}</title>
<style>
/* ===== 字体(gzh_cover 生成;fonts/ 经目录联接指向 Skill 字体库) ===== */
{faces}

/* ===== 画布:900×383 头条封面,转发卡片只露中央 383×383 ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; background: #ffffff; }}
.poster {{
  position: relative;
  width: {w}px;
  height: {h}px;
  overflow: hidden;
  background: linear-gradient(135deg, {t['bg']} 0%, {t['bg2']} 100%);
}}
:root {{
  --c-ink: {t['ink']};
  --c-accent: {t['accent']};
  --c-muted: {t['muted']};
{font_vars}
}}

/* ===== 居中安全区:关键信息全部落在中央 383×383 内 ===== */
.safe {{
  position: absolute; left: 50%; top: 0; bottom: 0; width: 383px;
  transform: translateX(-50%);
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center; gap: 16px;
}}
.mark {{ width: 44px; height: 8px; background: var(--c-accent); }}
.kicker {{ font: 600 16px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .42em; text-indent: .42em; }}
.t {{ font: 700 54px/1.25 var(--font-display);
  color: var(--c-ink); letter-spacing: .02em; max-width: 360px; }}
.sub {{ font: 400 18px/1.4 var(--font-sans); color: var(--c-muted);
  letter-spacing: .16em; text-indent: .16em; max-width: 340px; }}

/* ===== 边缘装饰(允许在安全区外) ===== */
.bar {{ position: absolute; left: 0; top: 0; bottom: 0; width: 10px; background: var(--c-accent); }}
.footer {{ position: absolute; left: 0; right: 0; bottom: 36px;
  text-align: center;
  font: 500 14px/1 var(--font-sans); color: var(--c-muted); letter-spacing: .3em; }}
.num {{ position: absolute; right: 48px; top: 32px;
  font: 800 84px/1 var(--font-display);
  color: var(--c-accent); opacity: .30; }}
</style>
</head>
<body>
  <div class="poster">
    <div class="bar"></div>
    {num_html}
    <div class="safe">
      <div class="mark"></div>
      {kicker_html}
      <h1 class="t">{esc(title)}</h1>
      {sub_html}
    </div>
    {footer_html}
  </div>
</body>
</html>"""


def sub_html(w: int, h: int, t: dict, title: str, kicker: str, sub: str,
             faces: str, font_vars: str) -> str:
    """次条封面 383×383:居中版式,元素 ≤3(眉题/标题/副题),小图可读优先。"""
    kicker_html = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>gzh-sub · {esc(title)}</title>
<style>
/* ===== 字体(与主封面同一套,保证双封面同气质) ===== */
{faces}

/* ===== 画布:383×383 次条封面(列表页缩略图,元素 ≤3) ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; background: #ffffff; }}
.poster {{
  position: relative;
  width: {w}px;
  height: {h}px;
  overflow: hidden;
  background: linear-gradient(135deg, {t['bg']} 0%, {t['bg2']} 100%);
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center; gap: 16px;
}}
:root {{
  --c-ink: {t['ink']};
  --c-accent: {t['accent']};
  --c-muted: {t['muted']};
{font_vars}
}}

/* ===== 版式:居中堆叠;顶部小色块是唯一装饰 ===== */
.mark {{ width: 44px; height: 8px; background: var(--c-accent); }}
.kicker {{ font: 600 13px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .38em; text-indent: .38em; }}
.t {{ font: 700 44px/1.3 var(--font-display); color: var(--c-ink);
  letter-spacing: .02em; max-width: 315px; }}
.sub {{ font: 400 15px/1.5 var(--font-sans); color: var(--c-muted);
  letter-spacing: .12em; max-width: 300px; }}
</style>
</head>
<body>
  <div class="poster">
    <div class="mark"></div>
    {kicker_html}
    <h1 class="t">{esc(title)}</h1>
    {sub_html}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------- 子命令

def cmd_new(args) -> int:
    proj_dir = args.slug if os.path.isabs(args.slug) else \
        os.path.join(cfg("studio_dir", near_workspace("artboard-studio")), args.slug)
    if os.path.exists(proj_dir) and not args.force:
        return fail("EXISTS", "换 slug 或 --force", path=os.path.abspath(proj_dir))
    t = THEMES.get(args.theme)
    if t is None:
        return fail("BAD_THEME", f"可选主题: {', '.join(sorted(THEMES))}")
    fams = DEFAULT_FONTS if args.fonts == "auto" else \
        [s.strip() for s in args.fonts.split(",") if s.strip()]
    faces, font_vars = build_font_assets(fams)
    if not faces:
        return fail("NO_FONTS", "fonts/ 下找不到所选字体目录", fonts=args.fonts)

    src = os.path.join(proj_dir, "src")
    os.makedirs(src, exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "export"), exist_ok=True)

    files = {
        "index.html": main_html(MAIN_W, MAIN_H, t, args.title, args.kicker,
                                args.sub, args.footer, args.num, faces, font_vars),
        "sub.html": sub_html(SUB_W, SUB_H, t,
                             args.sub_title or args.title, args.kicker,
                             args.sub_sub or args.sub, faces, font_vars),
    }
    for name, html in files.items():
        with open(os.path.join(src, name), "w", encoding="utf-8") as f:
            f.write(html)

    with open(os.path.join(proj_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump({"slug": os.path.basename(os.path.abspath(proj_dir)),
                   "kind": "gzh-cover",
                   "main": [MAIN_W, MAIN_H], "sub": [SUB_W, SUB_H],
                   "theme": args.theme, "fonts": args.fonts,
                   "skill_dir": SKILL_DIR, "created_by": "artboard.gzh_cover"},
                  f, ensure_ascii=False, indent=2)

    emit({"ok": True, "project": os.path.abspath(proj_dir),
          "files": [f"src/{k}" for k in files],
          "main": f"{MAIN_W}x{MAIN_H}", "sub": f"{SUB_W}x{SUB_H}",
          "next": f"python scripts/gzh_cover.py export \"{os.path.abspath(proj_dir)}\""})
    return 0


def find_kiln_for_img() -> str:
    """与 export.py 相同的 Kiln 引擎发现(位图拼接走 kiln img 工具箱)。"""
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    for cand in (near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe")),
                 near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def stitch_merged(main_png: str, sub_png: str, out_path: str, gap: int,
                  bg: str) -> dict:
    """等高拼接:主封面在左,次条在右,间隔 gap px,浅底色。
    v1.9:委托 kiln-cli img stitch(纯像素搬运,不缩放不重采样)。"""
    kiln = find_kiln_for_img()
    if not kiln:
        return {"ok": False, "error": "KILN_NOT_FOUND",
                "hint": "跑 scripts/setup_kiln.py 部署(kiln img 工具箱用于拼接)"}
    try:
        r = subprocess.run(
            [kiln, "img", "stitch",
             "--inputs", f"{main_png},{sub_png}",
             "--output", out_path,
             "--direction", "horizontal", "--gap", str(gap),
             "--bg", bg, "--align", "center"],
            capture_output=True, timeout=120)
        if r.returncode != 0:
            err = r.stderr.decode("utf-8", errors="replace")[:200]
            return {"ok": False, "error": "STITCH_FAILED", "detail": err,
                    "hint": "检查两张 PNG 是否存在且未损坏"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "STITCH_FAILED", "detail": str(exc)}
    # 读取输出尺寸
    try:
        lines = r.stdout.decode("utf-8", errors="replace").strip().splitlines()
        j = json.loads(lines[-1])
        return {"ok": True, "path": os.path.abspath(out_path),
                "width": j.get("width"), "height": j.get("height")}
    except Exception:
        return {"ok": True, "path": os.path.abspath(out_path)}


def cmd_export(args) -> int:
    proj = resolve_project(args.project)
    if not proj:
        return fail("PROJECT_NOT_FOUND", "传项目目录或 slug", project=args.project)
    src = os.path.join(proj, "src")
    main_html_p = os.path.join(src, "index.html")
    sub_html_p = os.path.join(src, "sub.html")
    if not os.path.isfile(main_html_p):
        return fail("NO_MAIN_HTML", "src/index.html 不存在;先跑 gzh_cover.py new", project=proj)
    if args.only in ("", "sub") and not os.path.isfile(sub_html_p):
        return fail("NO_SUB_HTML", "src/sub.html 不存在;先跑 gzh_cover.py new", project=proj)
    if args.only != "merged" and not check_kiln():
        return fail("KILN_NOT_FOUND",
                    "跑 scripts/setup_kiln.py 部署,或设 ARTBOARD_KILN_CLI 指向 Kiln-noGUI-CLI.exe")

    outdir = args.outdir or os.path.join(proj, "export")
    os.makedirs(outdir, exist_ok=True)
    slug = os.path.basename(proj.rstrip("\\/"))
    main_png = os.path.join(outdir, f"cover-main-{slug}.png")
    sub_png = os.path.join(outdir, f"cover-sub-{slug}.png")

    exports, failed = [], []
    if args.only in ("", "main"):
        r = run_export(main_html_p, main_png, MAIN_W, MAIN_H, args.scale)
        exports.append({"kind": "main", "output": main_png, **(
            {"size": f"{r.get('width')}x{r.get('height')}"} if r.get("ok")
            else {"error": r.get("error")})})
        if not r.get("ok"):
            failed.append({"kind": "main", **r})
    if args.only in ("", "sub"):
        r = run_export(sub_html_p, sub_png, SUB_W, SUB_H, args.scale)
        exports.append({"kind": "sub", "output": sub_png, **(
            {"size": f"{r.get('width')}x{r.get('height')}"} if r.get("ok")
            else {"error": r.get("error")})})
        if not r.get("ok"):
            failed.append({"kind": "sub", **r})

    merged = {}
    if args.only in ("", "merged"):
        if args.only == "merged":
            missing = [p for p in (main_png, sub_png) if not os.path.isfile(p)]
            if missing:
                return fail("MISSING_EXPORTS", "--only merged 需要单张封面已导出;先跑 export --only main|sub", missing=missing)
        if not failed:
            merged_png = os.path.join(outdir, f"cover-merged-{slug}.png")
            merged = stitch_merged(main_png, sub_png, merged_png,
                                   gap=MERGE_GAP * args.scale, bg=args.bg)
            exports.append({"kind": "merged", "output": merged.get("path", merged_png), **(
                {"size": f"{merged.get('width')}x{merged.get('height')}"} if merged.get("ok")
                else {"error": merged.get("error")})})
            if not merged.get("ok"):
                failed.append({"kind": "merged", **merged})

    payload = {"ok": not failed, "project": proj, "exports": exports}
    if merged.get("ok"):
        payload["merged"] = merged["path"]
    if failed:
        payload["failed"] = failed
        payload["hint"] = "单张失败不影响其他产物;按 error 处理后重跑(幂等覆盖)"
    emit(payload)
    return 0 if not failed else 1


def cmd_merge(args) -> int:
    """仅重拼合并图:单张 PNG 已在时使用,不重导(不需要引擎)。"""
    proj = resolve_project(args.project)
    if not proj:
        return fail("PROJECT_NOT_FOUND", "传项目目录或 slug", project=args.project)
    outdir = os.path.join(proj, "export")
    slug = os.path.basename(proj.rstrip("\\/"))
    main_png = os.path.join(outdir, f"cover-main-{slug}.png")
    sub_png = os.path.join(outdir, f"cover-sub-{slug}.png")
    missing = [p for p in (main_png, sub_png) if not os.path.isfile(p)]
    if missing:
        return fail("MISSING_EXPORTS", "先跑 gzh_cover.py export 生成单张封面",
                    missing=missing)
    # 间隔按导出倍率放大:从主封面 PNG 实宽反推 scale(900 为 CSS 画布宽)
    try:
        from PIL import Image
        with Image.open(main_png) as im:
            px_scale = max(1, round(im.width / MAIN_W))
    except Exception:  # noqa: BLE001
        px_scale = 1
    r = stitch_merged(main_png, sub_png,
                      os.path.join(outdir, f"cover-merged-{slug}.png"),
                      gap=args.gap * px_scale, bg=args.bg)
    emit(r)
    return 0 if r.get("ok") else 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="微信公众号双封面工作站(主 900×383 + 次 383×383 + 合并图)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("new", help="生成双封面项目")
    pn.add_argument("slug")
    pn.add_argument("--title", required=True, help="头条主标题(≤12 字一行;\\n 强制断行)")
    pn.add_argument("--sub-title", default="", help="次条标题(默认同主标题)")
    pn.add_argument("--kicker", default="", help="眉题/栏目名(可空)")
    pn.add_argument("--sub", default="", help="主封面副题(可空)")
    pn.add_argument("--sub-sub", default="", help="次条副题(默认同副题)")
    pn.add_argument("--footer", default="", help="页脚(仅主封面)")
    pn.add_argument("--num", default="", help="期号/序号(仅主封面,如 02)")
    pn.add_argument("--theme", default="blue", choices=sorted(THEMES))
    pn.add_argument("--fonts", default="auto",
                    help="auto=默认双字体;或 fonts/ 目录名逗号分隔(第一款=展示体)")
    pn.add_argument("--force", action="store_true")
    pn.set_defaults(func=cmd_new)

    pe = sub.add_parser("export", help="导出:默认三图齐出;--only 只出指定产物")
    pe.add_argument("project", help="项目目录或 slug")
    pe.add_argument("--only", default="", choices=["", "main", "sub", "merged"],
                    help="merged=只重拼合并图(单张须已导出)")
    pe.add_argument("--scale", type=int, default=2, choices=[1, 2])
    pe.add_argument("--outdir", default="")
    pe.add_argument("--bg", default="#f6f7f9", help="合并图底色")
    pe.set_defaults(func=cmd_export)

    pm = sub.add_parser("merge", help="仅重拼合并图(不重导单张,不需要引擎)")
    pm.add_argument("project")
    pm.add_argument("--gap", type=int, default=MERGE_GAP, help="间隔 CSS px(按导出 scale 自动放大)")
    pm.add_argument("--bg", default="#f6f7f9")
    pm.set_defaults(func=cmd_merge)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
