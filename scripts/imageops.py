"""位图工序唯一入口(指导书 §1.3/附录 D.2):只做参数分发与结果汇总,不含算法。
`--help` 列全子命令;`<cmd> --help` 按需展开(渐进披露,ADR-0002)。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _img_core as core  # noqa: E402
import _img_geom as geom  # noqa: E402
import _img_compose as compose  # noqa: E402
import _img_encode as encode  # noqa: E402
import _img_probe as probe  # noqa: E402

PIPELINE_ALLOWED = {"resize", "fit", "pad", "crop", "expand", "rotate", "trim",
                    "smartcrop", "convert", "compress", "optimize", "strip-meta",
                    "card", "watermark", "stitch", "blur-bg", "tone"}

HELP_MAP = {
    "素材能不能用": "probe",
    "平台要 3:4(允许裁)": "fit --presets xhs",
    "不许裁边": "pad --aspect W:H --bg edge",
    "上传超体积": "compress --target 500KB",
    "发九宫格": "slice --grid 3x3",
    "发多平台多规格": "derive --presets ... --matrix",
    "透明图转 JPG": "convert --to jpg --alpha flatten --bg '#ffffff'",
    "文字发糊": "convert --subsampling 4:4:4(或转 webp)",
    "压字看不清": "contrast-check --box ... --fg ...",
    "要印刷": "dpi-check → icc → export.py --cmyk",
    "手机图方向乱(单张/整目录)": "rotate --exif-fix 或 exif-fix <目录>",
    "几十张素材批量旋正缩放": "exif-fix <目录> 或 resize <目录> --max-edge 2200",
    "裁透明边": "trim",
    "圆角卡片化": "card --radius ... --shadow ...",
    "加水印": "watermark --text ... --position br",
    "纵向拼接": "stitch --direction v",
    "多稿对比选一版": "montage --grid 2x2 --gap 24 --bg '#e8e8e6' --label",
    "统一多图色调": "tone --duotone/--saturation/--temp",
    "模糊铺底转竖版": "blur-bg --aspect 3:4",
    "缩小长图": "resize --max-edge N",
    "一图多倍率": "derive --scales 1,2",
    "占位图 LQIP": "thumb --lqip 24",
}


def _add_global(p: argparse.ArgumentParser) -> None:
    p.add_argument("inputs", nargs="*",
                   help="输入文件**或目录**(目录递归展开其中的图片;可多个)")
    p.add_argument("--in", dest="in_glob", action="append", help="glob,可重复")
    p.add_argument("--in-dir", dest="in_dir", help="目录(单层;必须配 --ext)")
    p.add_argument("--ext", help="--in-dir 扩展名白名单,如 jpg,png")
    p.add_argument("--from-list", dest="from_list", help="清单文件,每行一路径")
    p.add_argument("--out", "-o", help="单文件输出")
    p.add_argument("--out-dir", dest="out_dir", help="批处理输出目录(缺省同输入目录)")
    p.add_argument("--name-template", dest="name_template", help='命名模板,须含 {name}')
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="只回填预测路径不写盘")
    p.add_argument("--skip-existing", dest="skip_existing", action="store_true")
    p.add_argument("--jobs", type=int, default=1, help="并发;0=auto")
    p.add_argument("--max-files", dest="max_files", type=int, default=500)
    p.add_argument("--manifest", help="写完整账本 JSON")
    p.add_argument("--verbose", action="store_true")


def _add_geom(sub) -> None:
    g = sub.add_parser("resize", help="G1 缩放(等比/精确/长边/倍率)")
    g.add_argument("--to"); g.add_argument("--width", type=int); g.add_argument("--height", type=int)
    g.add_argument("--scale", type=float); g.add_argument("--max-edge", dest="max_edge", type=int)
    g.add_argument("--resample", choices=list(core.RESAMPLE))
    g.add_argument("--no-upscale", dest="no_upscale", action="store_true")
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("fit", help="G2 裁切到目标比例(cover)")
    _add_target(g); g.add_argument("--gravity", default="center")
    g.add_argument("--bleed", type=float, default=0.0)
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("pad", help="G3 补边到目标比例(contain)")
    _add_target(g); g.add_argument("--bg", default="#ffffff")
    g.add_argument("--gravity", default="center"); g.add_argument("--blur-bg", dest="blur_bg", action="store_true")
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("crop", help="G4 坐标/百分比/锚点裁切")
    g.add_argument("--box"); g.add_argument("--pct"); g.add_argument("--anchor"); g.add_argument("--size")
    g.add_argument("--no-clamp", dest="clamp", action="store_false")
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("expand", help="G5 四周加固定边距")
    g.add_argument("--margin", default="0"); g.add_argument("--bg", default="#ffffff")
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("rotate", help="G6 旋转/翻转/EXIF 旋正")
    g.add_argument("--angle", type=float); g.add_argument("--expand", action="store_true")
    g.add_argument("--fill", default="#ffffff"); g.add_argument("--flip", choices=["h", "v"])
    g.add_argument("--exif-fix", dest="exif_fix", action="store_true")
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("trim", help="G7 裁透明边/纯色边")
    g.add_argument("--by", choices=["alpha", "color"], default="alpha")
    g.add_argument("--bg", default="edge"); g.add_argument("--tol", type=int, default=12)
    g.add_argument("--pad", type=int, default=0)
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("smartcrop", help="G8 主体感知裁切(降级链 smartcrop→cv2→center)")
    _add_target(g); g.add_argument("--engine", default="auto")
    _add_out_fmt(g); _add_global(g)


def _add_target(g):
    g.add_argument("--aspect", help="W:H,如 3:4")
    g.add_argument("--size", help="WxH")
    g.add_argument("--presets", help="SIZES 键名(唯一真源 scaffold.SIZES)")


def _add_out_fmt(g):
    g.add_argument("--format", dest="format_out", help="输出格式(png/jpg/webp/avif)")
    g.add_argument("--quality", type=int, default=None, help="0-100,缺省读 --profile")


def _add_encode(sub) -> None:
    g = sub.add_parser("convert", help="E1 格式转换")
    g.add_argument("--to", required=True, help="png/jpg/webp/avif/tif/bmp")
    g.add_argument("--quality", type=int, default=None)
    g.add_argument("--profile", choices=list(core.PROFILES), default="web")
    g.add_argument("--lossless", action="store_true")
    g.add_argument("--alpha", choices=["keep", "flatten", "drop"], default="keep")
    g.add_argument("--bg", default="#ffffff")
    g.add_argument("--icc", choices=["keep", "strip", "srgb"], default="keep")
    g.add_argument("--exif", choices=["keep", "strip"], default="strip")
    g.add_argument("--dpi"); g.add_argument("--progressive", action="store_true")
    g.add_argument("--optimize", action="store_true"); g.add_argument("--colors", type=int)
    _add_global(g)

    g = sub.add_parser("compress", help="E2 目标体积压缩(二分逼近)")
    g.add_argument("--target", required=True, help="300KB / 800KB / 字节数")
    g.add_argument("--format"); g.add_argument("--quality", type=int, default=None)
    g.add_argument("--profile", choices=list(core.PROFILES), default="platform")
    g.add_argument("--min-quality", dest="min_quality", type=int, default=40)
    g.add_argument("--max-quality", dest="max_quality", type=int, default=92)
    g.add_argument("--steps", type=int, default=8)
    g.add_argument("--tolerance", type=float, default=0.03)
    g.add_argument("--allow-downscale", dest="allow_downscale", action="store_true")
    g.add_argument("--allow-format-switch", dest="allow_format_switch", action="store_true")
    g.add_argument("--bg", default="#ffffff")
    _add_global(g)

    g = sub.add_parser("optimize", help="E3 无损优化")
    _add_out_fmt(g); g.add_argument("--optimize", action="store_true", default=True)
    _add_global(g)

    g = sub.add_parser("strip-meta", help="E6 元数据剥离(--keep-icc 默认开)")
    g.add_argument("--keep-icc", dest="keep_icc", action="store_true", default=True)
    _add_out_fmt(g); _add_global(g)


def _add_compose(sub) -> None:
    g = sub.add_parser("card", help="C1 圆角+描边+阴影")
    g.add_argument("--radius", type=int, default=0)
    g.add_argument("--border", help="W:颜色,如 2:#ffffff")
    g.add_argument("--shadow", help="dx,dy,blur,#rrggbbaa")
    g.add_argument("--bg", default="transparent")
    _add_global(g)

    g = sub.add_parser("watermark", help="C3 水印(文字/图片/平铺)")
    g.add_argument("--text"); g.add_argument("--image")
    g.add_argument("--font"); g.add_argument("--size", type=int, default=24)
    g.add_argument("--color", default="#ffffff"); g.add_argument("--opacity", type=float, default=0.35)
    g.add_argument("--position", default="br"); g.add_argument("--margin", type=int, default=24)
    g.add_argument("--tile-gap", dest="tile_gap", default="240x180")
    g.add_argument("--scale", type=float, default=1)
    _add_global(g)

    g = sub.add_parser("stitch", help="C4 拼接(横/纵;公众号双封面仍走 gzh_cover.py)")
    g.add_argument("--direction", default="h"); g.add_argument("--gap", type=int, default=0)
    g.add_argument("--bg", default="#ffffff")
    _add_global(g)

    g = sub.add_parser("montage", help="C5 网格拼图(多稿联络表;格多图少留空格,图多报错并给建议网格)")
    g.add_argument("--grid", help="行x列,如 2x2(4 稿);3 稿可 1x3")
    g.add_argument("--gap", type=int, default=0, help="格间距(联络表规范 24)")
    g.add_argument("--margin", type=int, default=0, help="四边外边距(联络表规范 32)")
    g.add_argument("--bg", default="#ffffff", help="底色(联络表规范 #e8e8e6 中性灰)")
    g.add_argument("--label", action="store_true", help="每格左上角叠 A/B/C/D… 索引字母")
    g.add_argument("--label-size", dest="label_size", type=int, default=0,
                   help="标签字号,缺省随格子高自适应")
    _add_global(g)

    g = sub.add_parser("blur-bg", help="C6 模糊铺底")
    _add_target(g); g.add_argument("--blur", type=float, default=24)
    g.add_argument("--dim", type=float, default=0.25); g.add_argument("--scale", type=float, default=1.0)
    _add_out_fmt(g); _add_global(g)

    g = sub.add_parser("tone", help="C8 统一色调/双色调/白平衡")
    g.add_argument("--duotone", help="#色1,#色2")
    g.add_argument("--saturation", type=float, default=1)
    g.add_argument("--temp", type=int, default=0)
    g.add_argument("--autocontrast", type=int); g.add_argument("--equalize", action="store_true")
    g.add_argument("--gamma", type=float, default=1)
    _add_global(g)


def _add_probe(sub) -> None:
    g = sub.add_parser("probe", help="P1 单图体检(尺寸/DPI/alpha/主色/疑点)")
    _add_global(g)
    g = sub.add_parser("palette", help="P2 主色/调色板提取")
    g.add_argument("--colors", type=int, default=6)
    _add_global(g)
    g = sub.add_parser("contrast-check", help="P6 压字对比度采样(WCAG)")
    g.add_argument("--box", required=True); g.add_argument("--fg", required=True)
    g.add_argument("--method", choices=["mean", "dominant", "p95-1"], default="dominant")
    _add_global(g)
    g = sub.add_parser("dpi-check", help="P8 印刷分辨率校验(DPI=LPI×2)")
    g.add_argument("--lpi", type=int); g.add_argument("--target-dpi", dest="target_dpi", type=int)
    g.add_argument("--print-size", dest="print_size", help="WxHmm,如 210x297")
    _add_global(g)


def _add_engineering(sub) -> None:
    g = sub.add_parser("rename", help="M1 批量改名(dry-run 默认开)")
    g.add_argument("--prefix"); g.add_argument("--suffix-text", dest="suffix_text")
    g.add_argument("--pattern"); g.add_argument("--replace")
    g.add_argument("--seq", action="store_true"); g.add_argument("--start", type=int, default=1)
    g.add_argument("--pad", type=int, default=3)
    g.add_argument("--apply", action="store_true", help="真正执行(缺省 dry-run)")
    _add_global(g)

    g = sub.add_parser("exif-fix", help="M2 批量 EXIF 旋正")
    _add_out_fmt(g); _add_global(g)

    sub.add_parser("deps", help="M3 位图族依赖状态(编码器级探测)")
    sub.add_parser("help-map", help="M4 场景→子命令映射")
    g = sub.add_parser("pipeline", help="链式工序,单次读单次写(§4.9)")
    g.add_argument("steps", help='分号分隔步骤,如 "exif-fix; fit aspect=1:1"')
    _add_global(g)


def _add_derived(sub) -> None:
    g = sub.add_parser("derive", help="D1 一图派生多规格矩阵(尺寸×格式×倍率)")
    _add_target(g)
    g.add_argument("--sizes", help="显式尺寸,如 1080x1080,1920x1080")
    g.add_argument("--mode", choices=["fit", "pad", "stretch"], default="fit")
    g.add_argument("--formats", help="png,webp,jpg 逗号分隔")
    g.add_argument("--scales", default="1", help="多倍率,如 1,2")
    g.add_argument("--profile", choices=list(core.PROFILES), default="platform")
    g.add_argument("--matrix", action="store_true")
    g.add_argument("--gravity", default="center")
    _add_global(g)

    g = sub.add_parser("slice", help="D2 宫格切片/长图切分")
    g.add_argument("--grid", help="RxC,如 3x3")
    g.add_argument("--rows", type=int); g.add_argument("--cols", type=int)
    g.add_argument("--max-height", dest="max_height", type=int)
    g.add_argument("--max-width", dest="max_width", type=int)
    g.add_argument("--overlap", type=int, default=0)
    _add_global(g)

    g = sub.add_parser("thumb", help="D3 缩略图/LQIP")
    g.add_argument("--max-edge", dest="max_edge", type=int, default=256)
    g.add_argument("--lqip", type=int); g.add_argument("--blur", type=float, default=0)
    g.add_argument("--format", dest="format_out", default="webp")
    _add_global(g)


def _register_all(sub) -> None:
    _add_geom(sub); _add_encode(sub); _add_compose(sub); _add_probe(sub)
    _add_derived(sub); _add_engineering(sub)


def _cmd_deps(_args) -> int:
    caps = core.ffmpeg_caps()
    pill = core.load_pillow()
    info = {"ok": True, "cmd": "deps", "degraded": False, "warnings": [], "error": None,
            "tiers": {
                "pillow": {"available": pill},
                "ffmpeg": caps,
                "optional_py": {m: _have(m) for m in ("numpy", "cv2", "smartcrop")},
                "externals": {"oxipng": core.ffmpeg_path() and None,
                              "imagemagick": None,
                              "note": "外部 CLI 仅『存在则用』;convert 会被 Windows 冒名(NTFS convert)"},
            }}
    core.emit(info)
    return 0


def _have(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _cmd_help_map(_args) -> int:
    core.emit({"ok": True, "cmd": "help-map", "map": HELP_MAP,
               "degraded": False, "warnings": [], "error": None})
    return 0


def _cmd_rename(args) -> int:
    """M1 批量改名:缺省 dry-run,--apply 才落盘;版权前缀守卫。"""
    if not (args.prefix or args.suffix_text or args.pattern or args.seq):
        return core.fail("rename", "USAGE", "需要 --prefix/--suffix-text/--pattern/--seq 之一")
    results = []
    seq = args.start
    for src in core.input_expand(args):
        try:
            name = src.stem
            if base_check := name.startswith("版权风险-"):
                new = "版权风险-"
                name = name[len("版权风险-"):]
            else:
                new = ""
            if args.pattern:
                name = __import__("re").sub(args.pattern, args.replace or "", name)
            if args.prefix:
                new += args.prefix
            new += name
            if args.suffix_text:
                new += args.suffix_text
            if args.seq:
                new += f"-{seq:0{args.pad or 3}d}"
                seq += 1
            if base_check and not new.startswith("版权风险-"):
                new = "版权风险-" + new  # 前缀永不丢(§4.10)
            dst = src.with_name(new + src.suffix)
            results.append({"input": str(src), "output": str(dst), "applied": bool(args.apply),
                            "degraded": False, "warnings": [], "error": None})
            if args.apply and dst != src:
                if dst.exists():
                    results[-1]["error"] = f"EXISTS: {dst}"
                    results[-1]["applied"] = False
                else:
                    src.rename(dst)
        except OSError as exc:
            results.append({"input": str(src), "error": f"OSError: {exc}",
                            "degraded": False, "warnings": [], "output": None})
    env_code = core.ok_envelope("rename", results)
    if not args.apply:
        # 单信封原则:补一条说明字段,不再第二次 emit(末行 JSON 契约)
        core.emit({"ok": True, "cmd": "rename", "note": "dry-run 预览;加 --apply 才执行",
                   "count": len(results), "results": results,
                   "degraded": False, "warnings": [], "error": None})
    return env_code


def _cmd_exif_fix(args) -> int:
    """M2:批量 EXIF 旋正(rotate --exif-fix 的批处理别名)。"""
    args.cmd = "exif-fix"
    args.size_tag = "exif"
    results = []
    for src in core.input_expand(args):
        try:
            img = geom._open(src)
            from PIL import ImageOps
            fixed = ImageOps.exif_transpose(img)
            fmt = (src.suffix.lstrip('.') or "png").lower()
            fmt = {"jpg": "jpeg"}.get(fmt, fmt)
            before = src.stat().st_size
            out = args.out or core.out_path_for(src, args, "exif", "jpg" if fmt == "jpeg" else fmt)
            fixed.save(out)
            # result_item 第 4 位是**编码后的字节**(内部要 len),此前直接塞
            # out.stat().st_size(int)→ TypeError,整条 exif-fix 全失败
            results.append(core.result_item(src, out, before, out.read_bytes()))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(core.result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return core.ok_envelope("exif-fix", results)


def _cmd_pipeline(args) -> int:
    """§4.9:一次调用走完整条链;中间结果只在内存。"""
    spec = args.steps
    steps = []
    for raw in [s.strip() for s in spec.split(";") if s.strip()]:
        parts = raw.split()
        name = parts[0]
        params = dict(kv.split("=", 1) for kv in parts[1:] if "=" in kv)
        # 位置参数形态:max-edge 1080 → max_edge=1080
        for i in range(1, len(parts)):
            if "=" not in parts[i] and i + 1 < len(parts) and "=" not in parts[i + 1]:
                params[parts[i].replace("-", "_")] = parts[i + 1]
        if name == "exif-fix":
            name, params = "rotate", {"exif_fix": True}
        if name not in geom.PIPELINE_OPS and name not in ("convert", "compress"):
            return core.fail("pipeline", "STEP_NOT_ALLOWED", f"{name} 不允许进 pipeline",
                             hint=f"允许:{','.join(sorted(PIPELINE_ALLOWED))}")
        steps.append((name, params))
    results = []
    for src in core.input_expand(args):
        try:
            img = geom._open(src)
            before = src.stat().st_size
            step_log = []
            fmt = "png"
            quality = 92
            error = None
            for name, params in steps:
                t0_ms = __import__("time").perf_counter_ns() // 1_000_000
                try:
                    if name == "convert":
                        to = params.get("to", params.get("format", "png"))
                        img, flat = encode._flatten(img, params.get("bg", "#ffffff")) \
                            if to in ("jpeg", "bmp") else (img, False)
                        data, meta = core.encode_image(img, to, int(params.get("quality", 82)))
                        import io
                        img = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(data))
                        fmt = to
                    elif name == "compress":
                        tgt = core.encode_image  # noqa: F841
                        q = int(params.get("quality", 82))
                        data, _m = core.encode_image(img, params.get("format", "webp"), q)
                        quality = q
                        fmt = params.get("format", "webp")
                    else:
                        fn = geom.PIPELINE_OPS[name]
                        if name in ("fit", "pad", "smartcrop", "blur-bg"):
                            params["target"] = geom._target_spec(
                                type("A", (), {"aspect": params.get("aspect"),
                                               "size": params.get("size"),
                                               "presets": None})(), img)
                        out_img = fn(img, params)
                        img = out_img[0] if isinstance(out_img, tuple) else out_img
                except SystemExit as exc:
                    error = f"STEP {name}: {exc}"
                    break
                except Exception as exc:  # noqa: BLE001
                    error = f"STEP {name}: {type(exc).__name__}: {exc}"
                    break
                step_log.append({"cmd": name, "ms": __import__("time").perf_counter_ns() // 1_000_000 - t0_ms,
                                 "size": list(img.size)})
            if error:
                results.append(core.result_item(src, None, before, None, error=error))
                continue
            ext = "jpg" if fmt == "jpeg" else fmt
            out = pathlib.Path(args.out) if args.out else core.out_path_for(src, args, "chain", ext)
            data, meta = core.encode_image(img, fmt, quality)
            out.write_bytes(data)
            item = core.result_item(src, out, before, data, engine=meta["engine"], quality=quality)
            item["steps"] = step_log
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(core.result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return core.ok_envelope("pipeline", results)


class JsonArgumentParser(argparse.ArgumentParser):
    """argparse error 也必须吐合法 JSON 末行(selfcheck.jsonfail 契约)。"""

    def error(self, message):
        core.emit({"ok": False, "cmd": self.prog, "error": "USAGE", "detail": message,
                   "hint": f"{self.prog} <cmd> --help"})
        raise SystemExit(core.EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    p = JsonArgumentParser(prog="imageops",
                                description="artboard 位图工序唯一入口(从图到图;"
                                            "从 HTML 到图走 export.py;抠图走 cutout.py)")
    sub = p.add_subparsers(dest="cmd", required=True)
    _register_all(sub)
    for name, fn in (("deps", _cmd_deps), ("help-map", _cmd_help_map),
                     ("rename", _cmd_rename), ("exif-fix", _cmd_exif_fix),
                     ("pipeline", _cmd_pipeline),
                     ("resize", geom.cmd_geom), ("fit", geom.cmd_geom),
                     ("pad", geom.cmd_geom), ("crop", geom.cmd_geom),
                     ("expand", geom.cmd_geom), ("rotate", geom.cmd_geom),
                     ("trim", geom.cmd_geom), ("smartcrop", geom.cmd_geom),
                     ("blur-bg", geom.cmd_geom), ("derive", geom.cmd_derive),
                     ("slice", geom.cmd_slice), ("thumb", geom.cmd_thumb),
                     ("convert", encode.cmd_convert), ("compress", encode.cmd_compress),
                     ("optimize", encode.cmd_optimize), ("strip-meta", encode.cmd_strip_meta),
                     ("card", compose.cmd_card), ("watermark", compose.cmd_watermark),
                     ("stitch", compose.cmd_stitch), ("montage", compose.cmd_montage),
                     ("tone", compose.cmd_tone),
                     ("probe", probe.cmd_probe), ("palette", probe.cmd_palette),
                     ("contrast-check", probe.cmd_contrast_check),
                     ("dpi-check", probe.cmd_dpi_check)):
        sub.choices[name].set_defaults(func=fn)
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    if not core.load_pillow():
        return core.fail(args.cmd, "NO_PILLOW", "Pillow 未安装",
                         hint="pip install -r requirements.txt")
    args.cmd = args.cmd
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
