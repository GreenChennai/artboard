"""artboard 抠图:本地 rembg + 四件套后处理(去残边/羽化/贴纸白边/软投影)。

模型策略(许可证红线,详见 references/materials.md):
  默认            isnet-general-use      产品图/食品照,软 alpha,CPU 1-2s
  卡通/吉祥物      isnet-anime            --model isnet-anime
  高质量          birefnet-general-lite  --quality high(慢,可配 --dml)
  ★ 禁用 bria-rmbg(RMBG-2.0):商用需向 BRIA 付费,脚本层硬拒绝。

用法:
  python cutout.py <图片...> [--out <目录>] [--model auto|isnet-anime|birefnet-general-lite|...]
      [--quality normal|high] [--feather 1.0] [--sticker] [--shadow] [--shadow-blur 8] [--trim] [--dml]
  python cutout.py --prefetch isnet-general-use isnet-anime   # 提前下载模型(离线可用)
"""

import argparse
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALLOWED_MODELS = {
    "isnet-general-use", "isnet-anime", "u2net", "u2netp",
    "birefnet-general-lite", "birefnet-general", "birefnet-dis",
}
FORBIDDEN_MODELS = {"bria-rmbg"}  # RMBG-2.0:商用需 BRIA 付费协议,绝不使用
DEFAULT_MODEL = "isnet-general-use"


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def get_session(model: str, dml: bool):
    from rembg import new_session
    if dml:
        try:
            session = new_session(model, providers=["DmlExecutionProvider"])
            return session, "dml"
        except Exception:  # noqa: BLE001 — 无 directml 时回退 CPU
            pass
    return new_session(model), "cpu"


def postprocess(img, feather: float, sticker: bool, shadow: bool,
                shadow_blur: int, trim: bool):
    """四件套后处理。img: RGBA PIL.Image;返回处理后的 RGBA 图。"""
    from PIL import Image, ImageFilter

    alpha = img.getchannel("A")
    # 1) 去残边:1px 腐蚀收紧 alpha,再按 feather 羽化
    alpha = alpha.filter(ImageFilter.MinFilter(3))
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    img = img.copy()
    img.putalpha(alpha)

    layers = []
    if shadow:
        sil = Image.new("RGBA", img.size, (0, 0, 0, 0))
        black = Image.new("RGBA", img.size, (0, 0, 0, 180))
        sil.paste(black, mask=alpha)
        sil = sil.filter(ImageFilter.GaussianBlur(shadow_blur))
        layers.append((0, max(8, shadow_blur // 2), sil))  # 下移投影

    if sticker:
        # 贴纸白描边:alpha 膨胀后垫白
        thick = alpha.filter(ImageFilter.MaxFilter(9))
        pad = 12
        canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
        white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
        canvas.paste(white, (pad, pad), thick)
        canvas.paste(img, (pad, pad), img)
        img = canvas

    if layers:
        pad = shadow_blur * 3
        canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
        for dx, dy, lay in layers:
            canvas.paste(lay, (pad + dx, pad + dy), lay)
        canvas.paste(img, (pad, pad), img)
        img = canvas

    if trim:
        bbox = img.getchannel("A").getbbox()
        if bbox:
            img = img.crop(bbox)
    return img


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="*", help="待抠图路径(可多张)")
    p.add_argument("--prefetch", nargs="*", choices=sorted(ALLOWED_MODELS), default=None,
                   help="只下载模型到本地缓存,不处理图片")
    p.add_argument("--out", default="", help="输出目录(默认与输入同目录)")
    p.add_argument("--model", default="auto",
                   help="auto=isnet-general-use;卡通/吉祥物显式传 isnet-anime")
    p.add_argument("--quality", default="normal", choices=["normal", "high"],
                   help="high → birefnet-general-lite(慢,建议配 --dml)")
    p.add_argument("--feather", type=float, default=1.0)
    p.add_argument("--sticker", action="store_true", help="贴纸白描边")
    p.add_argument("--shadow", action="store_true", help="软投影")
    p.add_argument("--shadow-blur", type=int, default=8, dest="shadow_blur")
    p.add_argument("--trim", action="store_true", help="裁掉透明边")
    p.add_argument("--dml", action="store_true",
                   help="尝试 DirectML 加速(需 pip install onnxruntime-directml;仅 birefnet 值得)")
    args = p.parse_args()

    # 许可证红线(脚本层硬拒绝,文档层另有说明)
    if args.model in FORBIDDEN_MODELS:
        emit({"ok": False, "error": "MODEL_FORBIDDEN",
              "hint": f"{args.model} = RMBG-2.0,商用需向 BRIA 付费。"
                      f"改用 {DEFAULT_MODEL}(默认)/ isnet-anime(卡通)/ birefnet-general-lite(high)"})
        return 2

    if args.prefetch is not None:
        for m in args.prefetch:
            get_session(m, False)
            emit({"ok": True, "prefetched": m})
        return 0

    if not args.inputs:
        emit({"ok": False, "error": "NO_INPUT", "hint": "传图片路径,或用 --prefetch 预取模型"})
        return 1

    model = DEFAULT_MODEL if args.model == "auto" else args.model
    if args.quality == "high" and args.model == "auto":
        model = "birefnet-general-lite"
    if model not in ALLOWED_MODELS:
        emit({"ok": False, "error": "UNKNOWN_MODEL",
              "hint": f"允许的模型:{', '.join(sorted(ALLOWED_MODELS))}"})
        return 2

    from PIL import Image
    from rembg import remove

    session, engine = get_session(model, args.dml)
    results = []
    out_dir = args.out
    for src in args.inputs:
        try:
            data = open(src, "rb").read()
            raw = remove(data, session=session)
            img = Image.open(__import__("io").BytesIO(raw)).convert("RGBA")
            img = postprocess(img, args.feather, args.sticker, args.shadow,
                              args.shadow_blur, args.trim)
            base = os.path.splitext(os.path.basename(src))[0]
            dst_dir = out_dir or os.path.dirname(os.path.abspath(src))
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f"{base}-cutout.png")
            img.save(dst)
            results.append({"input": src, "output": dst, "size": list(img.size)})
        except Exception as exc:  # noqa: BLE001
            results.append({"input": src, "error": f"{type(exc).__name__}: {exc}"})

    ok = all("output" in r for r in results)
    emit({"ok": ok, "model": model, "engine": engine, "results": results})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
