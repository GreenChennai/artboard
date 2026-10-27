"""微信公众号双封面 · 版式族库(gzh_cover.py 的渲染后端)。

设计目标:
- 一个只会读 references/formats/gzh-cover.md + references/gzh-cover-layouts.md 的
  执行者,调 `gzh_cover.py new --layout <族>` 就能拿到该族的完整结构(不是调色板)。
- **不改 _gzh_theme.py**:配色一切从 `cover_roles()` 给出的 6 个角色派生,
  「深底 / 浅底」由 ink 亮度自动判定,不新增主题名。
- 不新增外部依赖:底纹全部 CSS(inline SVG data-uri / repeating-linear-gradient /
  radial-gradient);plate-page 仅引用用户提供并复制到项目 src/images 的本地照片。

内部坐标约定(900×383 Artboard 主封面,不是平台裁切规格):
  x 0–257   左侧装饰区             保守排版安全区 258–642(383px)
  x 642–900 右侧装饰区
所有族的主标/眉题/副题按内部设计规则放在 .safe 内;边缘区用于装饰,实际显示须在当前公众号后台预览核验。

HTML 携带可机检标记(供 `gzh_cover.py check` 做几何断言):
  .poster[data-layout][data-kind][data-pattern]
  .safe[data-band="safe"]        安全区容器(约束见各族的 left/width)
  [data-role="info"]             信息件(必须在安全区内)
  [data-role="decor"]            装饰件(允许进入边缘装饰区)
"""

import html
import json
import re
import unicodedata

LAYOUTS = [
    {
        "slug": "center-band",
        "name": "居中色带",
        "tone": "Quiet",
        "layers": "2–3",
        "fits": "通知/通稿/喜报/每日资讯;信息只有标题(+副题)时最稳",
        "avoid": "标题 ≤5 字(会显得空);需要贴纸/分层的热闹气",
    },
    {
        "slug": "band-editorial",
        "name": "左文带",
        "tone": "Editorial / Power",
        "layers": "3–4",
        "fits": "标题 7–14 字、需要两行断行、有副题;栏目化运营号",
        "avoid": "没有副题(右半会空);没有任何图案时右半仍空落",
    },
    {
        "slug": "stack-cards",
        "name": "分层堆叠",
        "tone": "Playful",
        "layers": "3",
        "fits": "活动/招募;要「卡片 + 贴纸」的点击感;标题 5–10 字",
        "avoid": "三层形状语言不统一;已经要纸感(别和 kraft-note 叠)",
    },
    {
        "slug": "giant-caps",
        "name": "巨字压边",
        "tone": "Power",
        "layers": "1–2",
        "fits": "标题 ≤6 字,字即画布(倡议书/重要通知/周年)",
        "avoid": "标题 >8 字;要塞地点日期",
    },
    {
        "slug": "kraft-note",
        "name": "牛皮便签",
        "tone": "Playful / Quiet",
        "layers": "3",
        "fits": "手作感:市集/茶歇/迎新/开业,配手写体",
        "avoid": "深底主题;标题 ≥10 字;只有一张贴纸撑场",
    },
    {
        "slug": "plate-page",
        "name": "画页分栏",
        "tone": "Editorial",
        "layers": "5–6",
        "fits": "必须有本地照片/插画;时间/地点/主办等元数据可选",
        "avoid": "零图片素材",
    },
]
LAYOUT_SLUGS = [x["slug"] for x in LAYOUTS]
DEFAULT_LAYOUT = "center-band"

SUB_MODES = ["same", "minimal", "flat"]
BG_PATTERNS = ["auto", "none", "dots", "stripe", "grid", "lattice", "grain", "glow"]
ACCENT_TONES = ["auto", "none", "font", "capsule", "pill"]


def layout_spec(slug: str) -> dict:
    for x in LAYOUTS:
        if x["slug"] == slug:
            return dict(x)
    return {}


def layout_hint(slug: str) -> str:
    """给 --help / 报错用的一行提示。"""
    x = layout_spec(slug)
    return f"{x['name']}({x['tone']}):适合 {x['fits']}" if x else ""


# ---------------------------------------------------------------- 颜色工具

def _hex_rgb(c: str):
    m = re.fullmatch(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", (c or "").strip())
    if not m:
        return None
    s = m.group(1)
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_alpha(c: str, a: float) -> str:
    """'#rrggbb' → 'rgba(r,g,b,a)';已是 rgba() 的原样返回。"""
    if c.strip().lower().startswith("rgba"):
        return c
    rgb = _hex_rgb(c)
    if not rgb:
        return c
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{a:g})"


def _luminance(c: str) -> float:
    rgb = _hex_rgb(c)
    if not rgb:
        return 0.5
    r, g, b = (x / 255 for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_dark(t: dict) -> bool:
    """深底/浅底由主题 bg 决定(阈值 0.45):主题名不增长,换底自动适配。"""
    return _luminance(t.get("bg", "#ffffff")) < 0.45


# ---------------------------------------------------------------- CSS 底纹
# 全部 inline,零外部请求;数值只用主题角色色,换主题整族联动。

def pattern_css(name: str, t: dict) -> str:
    dark = is_dark(t)
    ink = t["ink"]
    accent = t["accent"]
    strong = _rgb_alpha(ink, .16 if dark else .10)
    soft = _rgb_alpha(ink, .08 if dark else .05)
    if name == "dots":
        return ("background-image: radial-gradient("
                f"{strong} 1.1px, transparent 1.2px);\n  background-size: 14px 14px;")
    if name == "stripe":
        return ("background-image: repeating-linear-gradient(45deg,\n    "
                f"{soft} 0 2px, transparent 2px 12px);")
    if name == "grid":
        return ("background-image:\n    "
                f"repeating-linear-gradient(90deg, {soft} 0 1px, transparent 1px 40px),\n    "
                f"repeating-linear-gradient(0deg, {soft} 0 1px, transparent 1px 40px);")
    if name == "lattice":
        return ("background-image:\n    "
                f"repeating-linear-gradient(0deg, {soft} 0 1px, transparent 1px 22px),\n    "
                f"repeating-linear-gradient(90deg, {soft} 0 1px, transparent 1px 22px),\n    "
                f"repeating-linear-gradient(90deg, {soft} 0 1px, transparent 1px 110px),\n    "
                f"repeating-linear-gradient(0deg, {soft} 0 1px, transparent 1px 110px);")
    if name == "grain":
        # 干燥纸颗粒:细密交叉斜纹,近看是纹理、远看是底色
        return ("background-image:\n    "
                f"repeating-linear-gradient(122deg, {strong} 0 1px, transparent 1px 5px),\n    "
                f"repeating-linear-gradient(58deg, {soft} 0 1px, transparent 1px 7px);")
    if name == "glow":
        # 单光源弧光(参考图 5/8/9/17:左上主光 + 右下反光)
        return ("background-image:\n    "
                f"radial-gradient(58% 118% at 16% 6%, {_rgb_alpha(accent, .52)} 0%, transparent 62%),\n    "
                f"radial-gradient(52% 128% at 94% 102%, {_rgb_alpha(accent, .30)} 0%, transparent 60%),\n    "
                f"radial-gradient(78% 92% at 50% 50%, {_rgb_alpha(ink, .10 if dark else .06)} 0%, transparent 70%);")
    return ""


DEFAULT_PATTERN = {
    "center-band": "glow",
    "band-editorial": "stripe",
    "stack-cards": "dots",
    "giant-caps": "glow",
    "kraft-note": "grain",
    "plate-page": "none",
}


def resolve_pattern(layout: str, want: str) -> str:
    if want in (None, "", "auto"):
        return DEFAULT_PATTERN.get(layout, "none")
    if want in BG_PATTERNS:
        return want
    return DEFAULT_PATTERN.get(layout, "none")


# ---------------------------------------------------------------- 着色器底材(shader effects)
# 来源:shader-effects-inc/shaders(MIT)。机制与参数见 references/shader-fx.md。
# 这里只做「主题 → 上游组件 props」的确定性映射:静态参数固定 seed/speed 后首帧 pause。
# 静态导出在官方 onReady 首帧回调后 pause,避免主封/次条采样相位不同。

SHADER_FX = ["mesh-gradient", "aurora", "flowing-gradient", "godrays", "curl-noise",
             "bokeh", "dot-grid", "halftone", "truchet", "vignette-grain", "water"]

# 各族默认搭配:克制优先,底材只做质感不做主角
DEFAULT_FX = {
    "center-band": "halftone",
    "band-editorial": "halftone",
    "stack-cards": "dot-grid",
    "giant-caps": "aurora",
    "kraft-note": "",          # 纸张族走 CSS 纹理,着色器会破坏纸感
    "plate-page": "",
}


def resolve_fx(layout: str, want: str) -> str:
    if want in (None, "", "auto"):
        return DEFAULT_FX.get(layout, "")
    if want == "none":
        return ""
    return want if want in SHADER_FX else ""


def resolve_visual_layers(layout: str, pattern: str, fx: str) -> tuple[str, str]:
    """CSS 底纹和 WebGPU shader 互斥:保留显式选择,拒绝显式双选。"""
    pattern_auto = pattern in (None, "", "auto")
    fx_auto = fx in (None, "", "auto")
    resolved_pattern = resolve_pattern(layout, pattern)
    resolved_fx = resolve_fx(layout, fx)
    if resolved_pattern not in ("", "none") and resolved_fx:
        if not pattern_auto and not fx_auto:
            raise ValueError("CSS 底纹与 shader 不能同时显式指定;请选择 --bg-pattern 或 --fx 其一")
        if not pattern_auto:
            resolved_fx = ""  # 显式底纹优先于版式自动 shader
        else:
            resolved_pattern = "none"  # 显式/自动 shader 取代版式默认 CSS 底纹
    return resolved_pattern, resolved_fx


# ---------------------------------------------------------------- 背景配方(外层背景层)
# 与 pattern_css 的区别:pattern 画在 .poster::after(版式底纹,受 pattern 互斥规则约束);
# 背景配方是独立的「外层背景层」.ab-bg-layer,贴在画布边缘、永远在内容(z-index 1)之下,
# 用于撕纸/票券/浏览器窗这类结构背景。全部 CSS-only、无外部资源、无文字。
# 规则与取舍见 references/gzh-cover-backgrounds.md;机检见 gzh_cover.py check 的 bg-* 项。

BG_RECIPE_SLUGS = [
    "kraft-paper", "gingham", "dots-grid", "tear", "ticket", "window", "rays", "curtain",
]

BG_LAYER_BASE_CSS = """
/* 外层背景层:内容之下、不接收指针事件、不放任何文字 */
.poster > .ab-bg-layer {
  position: absolute; inset: 0; z-index: 0; pointer-events: none;
  opacity: var(--bg-alpha, .5);
}
.poster > .ab-bg-layer::before,
.poster > .ab-bg-layer::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
}
"""


def bg_recipe_css(name: str, t: dict) -> str:
    """返回一个背景配方的 CSS 片段;未知配方返回空串(调用方负责报错)。"""
    if name not in BG_RECIPE_SLUGS:
        return ""
    dark = is_dark(t)
    ink = t["ink"]
    soft = _rgb_alpha(ink, .12 if dark else .08)
    faint = _rgb_alpha(ink, .07 if dark else .045)
    paper = "rgba(255,255,255,.80)" if not dark else "rgba(12,12,12,.34)"
    if name == "kraft-paper":
        # 牛皮纸:斜向纤维 + 细点孔,靠颜色不靠贴图
        return (".poster > .ab-bg-layer { --bg-alpha: .92;"
                f" background-color: {'#d9c7a1' if not dark else '#26221c'};"
                " background-image:"
                f" repeating-linear-gradient(112deg, {faint} 0 1px, transparent 1px 5px),"
                f" repeating-linear-gradient(64deg, {faint} 0 1px, transparent 1px 7px),"
                f" radial-gradient(circle at 50% 50%, {soft} .7px, transparent 1px);"
                " background-size: auto, auto, 7px 7px; }")
    if name == "gingham":
        # 两轴条纹 multiply:交叠处自然加深,不需要两套颜色
        return (".poster > .ab-bg-layer { --bg-alpha: .85; background-blend-mode: multiply;"
                " background-image:"
                f" repeating-linear-gradient(0deg, {soft} 0 6px, transparent 6px 26px),"
                f" repeating-linear-gradient(90deg, {soft} 0 6px, transparent 6px 26px); }}")
    if name == "dots-grid":
        # 点阵是「纸的肌理」不是「网」:alpha 压到 .3、点径 1px,12px 一格,
        # 在 2x 出图上刚好是一层浅网点;原来的 .55/1.2px 会变成粗布颗粒,
        # 背景抢过标题(实测 c1 warm 样本)。
        dot = _rgb_alpha(ink, .20)   # 点要看得见:叠在 --bg-alpha 上还要剩一层浅网点
        return (".poster > .ab-bg-layer { --bg-alpha: .60;"
                " background-image:"
                f" radial-gradient(circle at 50% 50%, {dot} 1px, transparent 1.6px);"
                " background-size: 12px 12px; }")
    if name == "tear":
        # 撕纸:纸卡 + 底边锯齿,drop-shadow 让白描边露出来
        return (".poster > .ab-bg-layer { --bg-alpha: .95; }"
                ".poster > .ab-bg-layer::before { inset: 12px 14px 0 14px;"
                f" background: {paper};"
                " clip-path: polygon(0 0, 100% 0, 100% 92%, 96% 96%, 92% 91%, 88% 97%,"
                " 82% 92%, 76% 98%, 70% 92%, 64% 97%, 58% 91%, 52% 97%, 46% 92%, 40% 98%,"
                " 34% 92%, 28% 97%, 22% 91%, 16% 97%, 10% 92%, 4% 96%, 0 91%);"
                " filter: drop-shadow(0 2px 0 rgba(255,255,255,.55)); }")
    if name == "ticket":
        # 票券:两侧半圆缺口用 mask 抠掉,不叠白色圆点
        return (".poster > .ab-bg-layer { --bg-alpha: .9; }"
                ".poster > .ab-bg-layer::before { inset: 16px 30px;"
                f" background: {paper}; border-radius: 4px;"
                " -webkit-mask-image:"
                " radial-gradient(circle 11px at 0 50%, transparent 98%, #000 100%),"
                " radial-gradient(circle 11px at 100% 50%, transparent 98%, #000 100%),"
                " linear-gradient(#000, #000);"
                " -webkit-mask-composite: source-in;"
                " mask-image:"
                " radial-gradient(circle 11px at 0 50%, transparent 98%, #000 100%),"
                " radial-gradient(circle 11px at 100% 50%, transparent 98%, #000 100%),"
                " linear-gradient(#000, #000);"
                " mask-composite: intersect; }")
    if name == "window":
        # 浏览器窗:一张卡 + 顶栏 + 三个圆点(纯 radial-gradient,无 emoji)
        return (".poster > .ab-bg-layer { --bg-alpha: .88; }"
                ".poster > .ab-bg-layer::before { inset: 30px 62px 42px 62px;"
                f" background: {paper}; border-radius: 10px 10px 0 0;"
                " box-shadow: inset 0 0 0 1px rgba(0,0,0,.10); }"
                ".poster > .ab-bg-layer::after { top: 30px; left: 62px; right: 62px; height: 26px;"
                " border-radius: 10px 10px 0 0;"
                f" background-image: {faint},"
                " radial-gradient(circle at 18px 50%, #d9705f 4px, transparent 4.6px),"
                " radial-gradient(circle at 36px 50%, #d9b25f 4px, transparent 4.6px),"
                " radial-gradient(circle at 54px 50%, #7fa87a 4px, transparent 4.6px);"
                " border-bottom: 1px solid rgba(0,0,0,.08); }")
    if name == "rays":
        # 主标区放射光:只在上半区,渐隐到 62% 高度,不压标题
        return (".poster > .ab-bg-layer { --bg-alpha: .45;"
                " background-image:"
                " repeating-conic-gradient(from -34deg at 50% -8%,"
                f" transparent 0 9deg, {soft} 9deg 10.5deg);"
                " -webkit-mask-image: linear-gradient(180deg, #000 0%, transparent 62%);"
                " mask-image: linear-gradient(180deg, #000 0%, transparent 62%); }")
    if name == "curtain":
        # 幕布:单一色相的多明度竖条,靠叠层做褶皱
        return (".poster > .ab-bg-layer { --bg-alpha: .5;"
                " background-image:"
                f" repeating-linear-gradient(90deg, {soft} 0 22px, transparent 22px 46px),"
                f" repeating-linear-gradient(90deg, {faint} 0 53px, transparent 53px 71px); }}")
    return ""


BG_PHOTO_CSS = """
/* 生图/用户图背景:铺满 + 左重右轻 scrim(标题在左,右侧透出画面) */
.poster > .ab-bg-layer { --bg-alpha: 1; background-image: var(--bg-photo);
  background-position: center; background-size: cover; background-repeat: no-repeat; }
.poster > .ab-bg-layer::after { inset: 0; background-image: var(--bg-photo-scrim); }
"""

BG_PHOTO_MAX_BYTES = 2_600_000   # 内联 data URI 上限(超过让调用方压图,避免产物失控)
BG_PHOTO_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def bg_photo_layer(t: dict, data_uri: str) -> tuple[str, str]:
    """把一张图片做成外层背景层:返回 (root 变量 CSS, 层 CSS)。

    图片以 data URI 内联,导出链路(Kiln/离线浏览器)不依赖外部文件,也不会
    因为相对路径失效而在成品里留白。
    """
    if not data_uri.startswith("data:image/"):
        raise ValueError("背景图必须是 data:image/* 内联 URI")
    dark = is_dark(t)
    bg = t["bg"]
    near = _rgb_alpha(bg, .58 if not dark else .46)
    far = _rgb_alpha(bg, .26 if not dark else .14)
    clear = _rgb_alpha(bg, 0.0)
    scrim = f"linear-gradient(90deg, {near} 0%, {far} 62%, {clear} 88%)"
    root = (".poster { --bg-photo: url(\"" + data_uri + "\");"
            f" --bg-photo-scrim: {scrim}; }}")
    return root, BG_PHOTO_CSS


def resolve_bg_recipe(want: str) -> str:
    """校验/归一背景配方:'', 'none', 'auto' → 空;非法值抛 ValueError 交给调用方报错。"""
    if want in (None, "", "auto", "none"):
        return ""
    if want in BG_RECIPE_SLUGS:
        return want
    raise ValueError(f"未知背景配方: {want};可选: {', '.join(BG_RECIPE_SLUGS)}")


def fx_params(fx: str, t: dict) -> str:
    """按官方组件 schema 将主题色映射到 upstream 参数;静态底材固定 speed/seed。"""
    if not fx:
        return ""
    bg, bg2, accent, ink = t["bg"], t["bg2"], t["accent"], t["ink"]
    muted = t.get("muted", ink)
    if fx == "aurora":
        p = {"colorA": bg2, "colorB": accent, "colorC": muted, "colorSpace": "oklab",
             "balance": 55, "intensity": 64, "curtainCount": 3, "speed": 0,
             "waviness": 42, "rayDensity": 24, "height": 110, "center": {"x": 0.5, "y": 0}, "seed": 7}
    elif fx == "mesh-gradient":
        p = {"colorA": bg, "colorB": accent,
             "stops": [{"color": bg, "position": 0}, {"color": bg2, "position": 0.28},
                       {"color": accent, "position": 0.58}, {"color": muted, "position": 0.8},
                       {"color": bg, "position": 1}],
             "colorSpace": "oklab", "count": 5, "smoothness": 1.35, "variation": 0.25,
             "swirl": 0.15, "drift": 0, "wrapping": 0, "speed": 0, "seed": 7}
    elif fx == "flowing-gradient":
        p = {"colorA": bg, "colorB": accent, "colorC": bg2, "colorD": muted,
             "colorSpace": "oklab", "speed": 0, "distortion": 0.25, "seed": 7}
    elif fx == "godrays":
        p = {"center": {"x": 0.5, "y": 0}, "density": 0.3, "intensity": 0.55,
             "spotty": 0.65, "speed": 0, "rayColor": accent, "backgroundColor": "transparent"}
    elif fx == "curl-noise":
        p = {"colorA": bg, "colorB": accent, "colorSpace": "oklab", "scale": 1.4,
             "contrast": 0.2, "balance": 0, "seed": 7, "speed": 0}
    elif fx == "bokeh":
        p = {"radius": 48, "highlightGain": 3, "highlightThreshold": 0.55,
             "bladeShape": "blades", "bladeCount": 6, "bladeRotation": 0,
             "chromaticFringe": 0.05, "catEye": 0.2, "backdropColorA": bg, "backdropColorB": bg2}
    elif fx == "dot-grid":
        p = {"color": accent, "density": 28, "dotSize": 0.24, "offset": 0,
             "speed": 0, "speedVariance": 0, "twinkle": 0}
    elif fx == "halftone":
        p = {"style": "cmyk", "frequency": 70, "angle": 45, "misprint": 0.001,
             "paperColor": bg, "cyanColor": bg2, "magentaColor": accent,
             "yellowColor": muted, "blackColor": ink,
             "backdropColorA": bg, "backdropColorB": bg2}
    elif fx == "truchet":
        p = {"colorA": bg2, "colorB": accent, "cells": 10, "thickness": 2,
             "rotation": 0, "softness": 0.15, "seed": 7, "colorSpace": "oklab"}
    elif fx == "vignette-grain":
        p = {"color": bg, "center": {"x": 0.5, "y": 0.5}, "radius": 0.75,
             "falloff": 0.65, "intensity": 0.35, "grainStrength": 0.16, "grainBias": 2,
             "backdropColorA": bg, "backdropColorB": bg2}
    elif fx == "water":
        p = {"center": {"x": 0.5, "y": 0.5}, "waterColor": accent, "scale": 1,
             "rotation": 0, "clarity": 0.6, "depth": 5, "shallows": 0.5,
             "caustics": 0.12, "causticScale": 6, "choppiness": 0.6, "waveScale": 3.2,
             "swirl": 0.4, "speed": 0, "reflection": 1, "envRotation": 0,
             "sharpness": 0.1, "lightAngle": 30, "foam": 0.2, "edgeSoftness": 0.05}
    else:
        return ""
    return json.dumps(p, ensure_ascii=False, separators=(",", ":"))


def fx_canvas(fx: str, t: dict) -> str:
    """着色器底层 DOM。z-index 0,内容层 z-index 1(canvas 已由 .poster > * 统一置 1,故单独覆盖)。"""
    if not fx:
        return ""
    params = fx_params(fx, t).replace("'", "&#39;")
    return (f'<canvas class="ab-shader" data-fx="{fx}" data-freeze="true" '
            f'data-webgpu-required="true" data-params=\'{params}\' '
            f'style="position:absolute;inset:0;width:100%;height:100%;z-index:0"></canvas>')


def fx_runtime_tag() -> str:
    """加载本地官方 upstream bundle 与 Artboard 的薄加载器。"""
    return ('<script src="vendor/shaders/upstream.js"></script>'
            '<script src="vendor/shaders/runtime.js"></script>')


def resolve_tone(layout: str, want: str) -> str:
    if want in (None, "", "auto"):
        return {"kraft-note": "pill", "giant-caps": "capsule"}.get(layout, "none")
    return want


# ---------------------------------------------------------------- 公共工具

def esc(s: str) -> str:
    """HTML 转义文本,保留任何合法 `<br>` 变体作为显式断行。"""
    text = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return escaped.replace("\n", "<br>")


def plain(s: str) -> str:
    """规范化原始文本;仅把 `<br>` 视为断行,保留用户输入的尖括号字面文本。"""
    text = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def markup_plain(s: str) -> str:
    """抽取已转义 HTML 片段中的可见文本,用于检查渲染后的标题标记。"""
    text = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    text = re.sub(r"<[^>]*>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fit_size(text: str, big: int, mid: int, small: int, n_big=6, n_mid=10) -> int:
    """按可见字数选字号(映射表见 formats/gzh-cover.md §4.2)。"""
    n = visible_len(plain(text))
    if n <= n_big:
        return big
    if n <= n_mid:
        return mid
    return small


def root_vars(t: dict, font_vars: str, font_faces: str = "") -> str:
    dark = is_dark(t)
    ink = t["ink"]
    line = t.get("line") or _rgb_alpha(ink, .18)
    faces = f"{font_faces}\n" if font_faces else ""
    return f"""{faces}:root {{
  --c-ink: {ink};
  --c-accent: {t['accent']};
  --c-muted: {t['muted']};
  --c-line: {line};
  --c-bg: {t['bg']};
  --c-bg2: {t['bg2']};
  /* 由 bg 亮暗派生:浅底主题用深墨色作「反色卡」底色,深底主题用白 */
  --c-contrast: {'#ffffff' if dark else ink};
  --c-plate: {'rgba(255,255,255,.07)' if dark else 'rgba(255,255,255,.72)'};
  --c-vellum: {'rgba(255,255,255,.07)' if dark else 'rgba(255,255,255,.66)'};
  --c-shadow: {'0 18px 48px rgba(0,0,0,.38)' if dark else '0 14px 34px rgba(58,44,30,.16)'};
{font_vars}
}}"""


def canvas(w: int, h: int, t: dict, layout: str, pattern: str, tone: str,
           size: int, body: str, css: str, title: str, kind: str, fx: str = "",
           sub_mode: str = "same", bg_recipe: str = "", bg_photo: str = "") -> str:
    bg_css = ""
    if bg_recipe:
        bg_css = BG_LAYER_BASE_CSS + bg_recipe_css(bg_recipe, t)
    elif bg_photo:
        photo_root, photo_css = bg_photo_layer(t, bg_photo)
        bg_css = BG_LAYER_BASE_CSS + photo_root + photo_css
    bg_attr = (f' data-bg-recipe="{bg_recipe}"' if bg_recipe
               else (' data-bg-photo="1"' if bg_photo else ""))
    bg_tag = (f'<div class="ab-bg-layer"{bg_attr} aria-hidden="true"></div>'
              if (bg_recipe or bg_photo) else "")
    pat = pattern_css(pattern, t) if pattern not in ("", "none") else ""
    pat_block = f"\n  {pat}" if pat else ""
    tone_cls = f" tone-{tone}" if tone != "none" else ""
    # 双底材是歧义参数:公共解析器已选择其中之一,底层不再静默丢弃显式请求。
    if fx and pat not in ("", "none"):
        raise ValueError("CSS 底纹与 shader 不能同时渲染")
    fx_tag = '\n' + fx_runtime_tag() if fx else ""
    flat_css = ""
    if kind == "sub" and sub_mode == "flat":
        flat_css = f"""
/* flat 次条:纯主题底色 + 清晰文字,不沿用主封装饰与纹理 */
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] {{
  background: {t['bg']} !important; background-image: none !important;
}}
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"]::after {{ background-image: none !important; }}
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] [data-role=\"decor\"] {{ display: none !important; }}
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] > .ab-bg-layer {{ display: none !important; }}
/* plate-page 的用户照片是内容素材,flat 只去除装饰,不移除照片 */
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] .plate,
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] .plate-image {{ display: block !important; }}
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] .t {{
  color: var(--c-ink) !important; background: transparent !important; padding: 0 !important;
}}
.poster[data-kind=\"sub\"][data-sub-mode=\"flat\"] .sub {{
  color: var(--c-muted) !important; background: transparent !important; opacity: 1 !important;
}}
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="generator" content="artboard.gzh_cover">
<title>gzh-{kind} · {esc(title)}</title>
<style>
/* ===== 画布 {w}×{h} · 版式族 {layout} · 底纹 {pattern} · 强调 {tone} · 着色器 {fx or '无'} ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; background: transparent; }}
.poster {{
  position: relative;
  box-sizing: border-box;
  width: {w}px;
  height: {h}px;
  margin: 0;
  padding: 0;
  border: 0;
  overflow: hidden;
  isolation: isolate;
  background-image: linear-gradient(135deg, {t['bg']} 0%, {t['bg2']} 100%);
  --t-size: {size}px;
}}
/* 底纹层:纯 CSS,零外部资源 */
.poster::after {{
  content: "";
  position: absolute; inset: 0;
  pointer-events: none;{pat_block}
  z-index: 0;
}}
.poster > * {{ position: absolute; z-index: 1; }}
/* 着色器底材(来源 shader-effects-inc/shaders,MIT):canvas 参与布局,尺寸稳定不引起滚动 */
.poster > canvas.ab-shader {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 0; }}
{css}
{flat_css}
{bg_css}
</style>
</head>
<body>
<div class="poster{tone_cls}" data-layout="{layout}" data-kind="{kind}" data-pattern="{pattern}" data-fx="{fx}" data-sub-mode="{sub_mode if kind == 'sub' else 'same'}">
{bg_tag}{body}
</div>{fx_tag}
</body>
</html>"""


def _tone_css(tone: str) -> str:
    """强调处理:主标变名片色 / 色块 / 副题胶囊(全族通用,族内只需给出选择器)。"""
    if tone == "font":
        return ".t { color: var(--c-accent) !important; }"
    if tone == "capsule":
        # width 取族内算出的最长行宽(--block-w),避免断行后色块被拉满容器
        return (".t { background: var(--c-accent) !important; color: var(--c-bg) !important;"
                " padding: 0 16px; box-decoration-break: clone;"
                " display: inline-block; width: var(--block-w, auto); max-width: 100%; }")
    if tone == "pill":
        return (".sub { background: var(--c-accent) !important; color: var(--c-bg) !important;"
                " border-radius: 999px; padding: 5px 16px; opacity: 1 !important; }")
    return ""


# ================================================================ 族一:center-band

CB_CSS = """
/* 中央色带:主封基准 383×232, y=96;标题越界时色带随字宽生长(--band-w ≤ 720) */
.band { left: 50%; top: 96px; transform: translateX(-50%);
  width: var(--band-w, 383px); height: 232px; background: var(--c-plate);
  border: 1px solid var(--c-line); border-radius: 8px; }
.safe { left: 50%; top: 30px; bottom: 30px; width: var(--band-w, 383px); transform: translateX(-50%);
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; gap: 15px; }
.mark { width: 44px; height: 8px; background: var(--c-accent); }
.kicker { font: 600 16px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .42em; text-indent: .42em; }
.t { font: 700 var(--t-size)/1.25 var(--font-display);
  color: var(--c-ink); letter-spacing: .02em; max-width: var(--band-w, 383px); }
.sub { font: 400 18px/1.4 var(--font-sans); color: var(--c-muted);
  letter-spacing: .16em; text-indent: .16em; max-width: 340px; }
.rule { width: 58px; height: 1px; background: var(--c-line); }
.bar { left: 0; top: 0; bottom: 0; width: 10px; background: var(--c-accent); }
.footer { left: 0; right: 0; bottom: 30px; text-align: center;
  font: 500 14px/1 var(--font-sans); color: var(--c-muted); letter-spacing: .3em;
  text-indent: .3em; }
.num { right: 48px; top: 30px; font: 800 84px/1 var(--font-display);
  color: var(--c-accent); opacity: .30; }
.wm { left: 24px; top: 50%; transform: translate(-50%, -50%) rotate(90deg);
  transform-origin: center; white-space: nowrap;
  font: 700 12px/1 var(--font-sans); letter-spacing: .25em;
  color: var(--c-ink); opacity: .08; }
"""

CB_CSS_SUB = """
/* 次条保留同一色带语言,改为近铺满的 349×349 方卡 */
.band { left: 50%; top: 50%; transform: translate(-50%, -50%);
  width: 349px; height: 349px; background: var(--c-plate);
  border: 1px solid var(--c-line); border-radius: 8px; }
.safe { left: 50%; top: 24px; bottom: 24px; width: 315px; transform: translateX(-50%);
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; gap: 14px; }
.mark { width: 44px; height: 8px; background: var(--c-accent); }
.kicker { font: 600 13px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .38em; text-indent: .38em; }
.t { font: 700 var(--t-size)/1.3 var(--font-display); color: var(--c-ink);
  letter-spacing: .02em; max-width: 315px; white-space: normal; }
.sub { font: 400 15px/1.5 var(--font-sans); color: var(--c-muted);
  letter-spacing: .12em; max-width: 300px; }
.wm { left: 24px; top: 50%; transform: translate(-50%, -50%) rotate(90deg);
  transform-origin: center; white-space: nowrap;
  font: 600 10px/1 var(--font-sans); letter-spacing: .18em;
  color: var(--c-ink); opacity: .08; }
"""


# ---------------------------------------------------------------- 字号体系(v2)
# 参考 18 张双封面的量化结论:主标字高占画布高 15–33%(中位 20%),中文 3–9 字,
# 单侧 ≤2 行。字号不能按"平面物料"线性给,而要按「字数档 × 画布占比」给上限,
# 再由实际字宽反推 —— 否则短标题会被 base 锁死,长标题会被安全区压成小字。
CANVAS_H = 383                 # 主封面画布高(900×383)
TITLE_SHARE_CAP = 0.36         # 主标字高占画布高的硬上限(满版:4 字可到 132px)
TITLE_HARD_CAP = 12            # 文案预算:主标可见字符上限(与 check 的 title-char-cap 同源)
TITLE_COL_MAX = 820            # 主标授权行宽上限:x≈40–860(语义守 383,字形可越)
CENTER_BAND = (258, 642)       # 中央语义安全区:x 区间
TITLE_CEILING = {1: 137, 2: 137, 3: 137, 4: 132, 5: 130, 6: 120,
                 7: 104, 8: 96, 9: 84, 10: 76, 11: 70, 12: 64}
SUB_TITLE_STEPS = {1: 170, 2: 160, 3: 137, 4: 112, 5: 96, 6: 96}
SUB_TITLE_MIN_PX = 22          # 次条可读下限(与 check 的 title-min-px 同源)
SINGLE_LINE_MIN_PX = 64        # 主标一行可读下限:字号到这就不拆行(8–12 字直排的依据)
SUB_CANVAS = 383               # 次条方图边长
SUB_TOP_ZONE = 53              # 方图标题块上沿:眉题(6px 起)之下再留 10px 呼吸
SUB_BOTTOM_ZONE = 53           # 方图标题块下沿:与上沿对称,保证块中心=画布中心
SUB_BLOCK_H_RATIO = (SUB_CANVAS - SUB_TOP_ZONE - SUB_BOTTOM_ZONE) / SUB_CANVAS  # ≈0.72:标题块居中且不碰眉题/副题
SUB_BLOCK_W_RATIO = 0.84       # 方图标题块宽占画布比(两侧各留 8% 呼吸)
SUB_LINE_HEIGHT = 1.12         # 方图标题行高:与 CSS 的 .t line-height 同源,块高按它反推

# 次条铁律:标题永远压在方图正中,眉题/副题贴边固定,任何内容都不得把标题挤偏。
# 各族的 .safe 仍是 flex 居中容器,但只让 .t 参与垂直居中;其余信息件绝对定位到上下带。
SUB_CENTER_CSS = """
/* 次条:标题垂直居中(不看眉题/副题多少),眉题贴顶、副题贴底 */
.safe > .t { line-height: 1.12; text-align: center; align-self: center; }
.safe > .kicker { position: absolute; top: 6px; left: 0; right: 0;
  font-size: 13px; text-align: center; text-indent: 0; color: @KICKER@; }
.safe > .kicker::before { display: none; }
.safe > .sub { position: absolute; bottom: 10px; left: 0; right: 0;
  text-align: center; margin: 0; }
.safe > .mark, .safe > .rule { display: none; }
"""


def sub_center_css(t: dict) -> str:
    """次条居中样式的主题特化:深底用 muted(accent 在深底上常低于 4.5:1),浅底用 accent。"""
    color = "var(--c-muted)" if is_dark(t) else "var(--c-accent)"
    return SUB_CENTER_CSS.replace("@KICKER@", color)


def title_ceiling(n: int) -> int:
    """按"最长行字数"取主标字号上限(px,900×383 画布)。"""
    n = max(1, min(int(n), TITLE_HARD_CAP))
    return TITLE_CEILING[n]


def sub_title_step(n: int) -> int:
    """次条独立字阶:按次条标题字数取上限,不再用主标 ×0.62 缩排。"""
    n = max(1, min(int(n), 6))
    return SUB_TITLE_STEPS[n]


def longest_line_chars(text: str) -> int:
    lines = text.split("<br>") if "<br>" in text else [text]
    return max(1, max(visible_len(plain(x)) for x in lines))


# ---------------------------------------------------------------- 断行(孤字治理)
# 为什么不用浏览器自动换行:max-width 断行时最后一行可能只剩 1 个字(实测"…排版指/南")。
# 这是用户"每次都要手动调很多次"的头号来源,必须在排版阶段就定死,不能交给渲染器。

NO_TAIL = set("的了和与及给在把被对向从为以就都也还而又并或但且如")
NO_LEAD = set("的了和与及给在把被对向从为以就都也还而又并或但且如·、,，。.：:；;！!？?)）】」』》")

# 高置信标题词组锁:不做通用分词(无第三方词库),只避免双封面/公众号常见
# 复合词被断在内部。命中词组长度很短,不影响其它标题分行。
TITLE_BREAK_LOCKS = (
    "微信公众号", "公众号", "双封面", "城市更新", "社区更新", "乡村振兴",
    "人工智能", "数字化转型", "移动互联网", "内容设计", "封面设计", "视觉设计",
    "版式设计", "品牌传播", "品牌故事", "用户体验", "阅读体验", "内容运营",
    "数据分析", "数据驱动", "产品设计", "解决方案", "应用场景", "交通出行",
    "社交媒体", "行业观察", "深度解析", "实用指南", "排版指南", "设计指南",
    "发展趋势", "市场趋势", "产业升级", "技术路线", "公共空间", "文化体验",
    "项目管理", "传播效果", "运营策略", "内容创作", "案例分析", "工作流程",
    "高质量", "可持续", "入门指南", "效率提升",
)


def _hangul_type(ch: str) -> str:
    """Return the UAX #29 Hangul grapheme class for a code point, if any."""
    code = ord(ch)
    if (0x1100 <= code <= 0x115F or 0xA960 <= code <= 0xA97C):
        return "L"
    if 0x1160 <= code <= 0x11A7 or 0xD7B0 <= code <= 0xD7C6:
        return "V"
    if 0x11A8 <= code <= 0x11FF or 0xD7CB <= code <= 0xD7FB:
        return "T"
    if 0xAC00 <= code <= 0xD7A3:
        return "LV" if (code - 0xAC00) % 28 == 0 else "LVT"
    return ""


def _hangul_grapheme_join(previous: str, current: str) -> bool:
    prev_type, curr_type = _hangul_type(previous), _hangul_type(current)
    return ((prev_type == "L" and curr_type in {"L", "V", "LV", "LVT"})
            or (prev_type in {"LV", "V"} and curr_type in {"V", "T"})
            or (prev_type in {"LVT", "T"} and curr_type == "T"))


def _is_cjk(ch: str) -> bool:
    return any(0x3400 <= ord(char) <= 0x9FFF or 0xF900 <= ord(char) <= 0xFAFF
               or 0x1100 <= ord(char) <= 0x11FF or 0x3130 <= ord(char) <= 0x318F
               or 0xA960 <= ord(char) <= 0xA97F or 0xAC00 <= ord(char) <= 0xD7FF
               for char in ch)


_EXTENDED_PICTOGRAPHIC_RANGES = (
    (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x203C, 0x203C), (0x2049, 0x2049),
    (0x2122, 0x2122), (0x2139, 0x2139), (0x2194, 0x2199), (0x21A9, 0x21AA),
    (0x231A, 0x231B), (0x2328, 0x2328), (0x2388, 0x2388), (0x23CF, 0x23CF),
    (0x23E9, 0x23F3), (0x23F8, 0x23FA), (0x24C2, 0x24C2), (0x25AA, 0x25AB),
    (0x25B6, 0x25B6), (0x25C0, 0x25C0), (0x25FB, 0x25FE), (0x2600, 0x2605),
    (0x2607, 0x2612), (0x2614, 0x2685), (0x2690, 0x2705), (0x2708, 0x2712),
    (0x2714, 0x2714), (0x2716, 0x2716), (0x271D, 0x271D), (0x2721, 0x2721),
    (0x2728, 0x2728), (0x2733, 0x2734), (0x2744, 0x2744), (0x2747, 0x2747),
    (0x274C, 0x274C), (0x274E, 0x274E), (0x2753, 0x2755), (0x2757, 0x2757),
    (0x2763, 0x2767), (0x2795, 0x2797), (0x27A1, 0x27A1), (0x27B0, 0x27B0),
    (0x27BF, 0x27BF), (0x2934, 0x2935), (0x2B05, 0x2B07), (0x2B1B, 0x2B1C),
    (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0x3030, 0x3030), (0x303D, 0x303D),
    (0x3297, 0x3297), (0x3299, 0x3299), (0x1F000, 0x1F0FF), (0x1F10D, 0x1F10F),
    (0x1F12F, 0x1F12F), (0x1F16C, 0x1F171), (0x1F17E, 0x1F17F), (0x1F18E, 0x1F18E),
    (0x1F191, 0x1F19A), (0x1F1AD, 0x1F1E5), (0x1F201, 0x1F202), (0x1F21A, 0x1F21A),
    (0x1F22F, 0x1F22F), (0x1F232, 0x1F23A), (0x1F23C, 0x1F23F), (0x1F249, 0x1F3FA),
    (0x1F400, 0x1F53D), (0x1F546, 0x1F64F), (0x1F680, 0x1F6FF), (0x1F774, 0x1F77F),
    (0x1F7D5, 0x1F7FF), (0x1F80C, 0x1F80F), (0x1F848, 0x1F84F), (0x1F85A, 0x1F85F),
    (0x1F888, 0x1F88F), (0x1F8AE, 0x1F8AF), (0x1F8B2, 0x1F8FF), (0x1F90C, 0x1F93A),
    (0x1F93C, 0x1F945), (0x1F947, 0x1FAFF),
)


def _is_extended_pictographic(ch: str) -> bool:
    """Match the explicit Extended_Pictographic range table used for ZWJ joins."""
    code = ord(ch)
    return any(first <= code <= last for first, last in _EXTENDED_PICTOGRAPHIC_RANGES)


def grapheme_clusters(text: str) -> list[str]:
    """Group Hangul, combining sequences, valid emoji ZWJ sequences and RI flags."""
    clusters: list[str] = []
    join_next = False
    regional_count = 0
    source = text or ""
    for index, ch in enumerate(source):
        code = ord(ch)
        category = unicodedata.category(ch)
        regional = 0x1F1E6 <= code <= 0x1F1FF
        extend = (category in {"Mn", "Mc", "Me", "Cf"}
                  or 0x1F3FB <= code <= 0x1F3FF
                  or 0xE0020 <= code <= 0xE007F)
        if ch == "\u200d":
            previous = clusters[-1] if clusters else ""
            next_char = source[index + 1] if index + 1 < len(source) else ""
            if (previous and not previous.endswith("\u200d")
                    and any(_is_extended_pictographic(part) for part in previous)
                    and next_char and _is_extended_pictographic(next_char)):
                clusters[-1] += ch
                join_next = True
                regional_count = 0
            else:
                # A stray ZWJ is a zero-width format control, not permission to
                # merge unrelated title characters into one visible unit.
                join_next = False
            continue
        if not clusters:
            clusters.append(ch)
            regional_count = 1 if regional else 0
        elif join_next:
            clusters[-1] += ch
            join_next = False
            regional_count = 0
        elif extend:
            clusters[-1] += ch
        elif _hangul_grapheme_join(clusters[-1][-1], ch):
            clusters[-1] += ch
            regional_count = 0
        elif regional:
            if regional_count % 2:
                clusters[-1] += ch
                regional_count += 1
            else:
                clusters.append(ch)
                regional_count = 1
        else:
            clusters.append(ch)
            regional_count = 0
    return clusters


def visible_len(text: str) -> int:
    """Count visible grapheme clusters, ignoring whitespace and standalone controls."""
    invisible = {"Mn", "Me", "Cf", "Cc", "Cs", "Zl", "Zp"}
    return sum(1 for cluster in grapheme_clusters(text)
               if not cluster.isspace()
               and any(unicodedata.category(ch) not in invisible for ch in cluster))


def _units(text: str):
    """切成不可再分的换行单元:中文逐字,英文/数字按词,标点黏住前一个单元。"""
    units, buf = [], ""
    for ch in grapheme_clusters(text):
        if ch.isspace():
            if buf:
                units.append(buf)
                buf = ""
            if units and not units[-1].endswith(" "):
                units[-1] += " "
            continue
        if ch.isascii() and (ch.isalnum() or ch in "-_%+&/'."):
            buf += ch
            continue
        if buf:
            units.append(buf)
            buf = ""
        if units and not _is_cjk(ch) and ch in "，。、：；！？）」』》%,.;:!?)]":
            units[-1] += ch          # 标点不占行首
        else:
            units.append(ch)
    if buf:
        units.append(buf)
    return units


def _title_term_boundaries(text: str) -> set[int]:
    """返回高置信复合词内部的字符边界,供断行评分保护。"""
    protected = set()
    for term in TITLE_BREAK_LOCKS:
        start = 0
        while True:
            start = text.find(term, start)
            if start < 0:
                break
            protected.update(range(start + 1, start + len(term)))
            start += 1
    return protected


def locked_title_splits(markup: str) -> list[str]:
    """列出显式 <br> 拆开的高置信词组;供 gzh_cover check 做静态验收。"""
    lines = re.split(r"<br\s*/?>", markup or "", flags=re.I)
    lines = [re.sub(r"\s+", "", markup_plain(line)) for line in lines]
    full = "".join(lines)
    cuts = set()
    cursor = 0
    for line in lines[:-1]:
        cursor += len(line)
        cuts.add(cursor)
    broken = []
    for term in TITLE_BREAK_LOCKS:
        start = 0
        while True:
            start = full.find(term, start)
            if start < 0:
                break
            end = start + len(term)
            if any(start < cut < end for cut in cuts):
                broken.append((start, end, term))
                break
            start += 1
    # 只报告最长命中词组,避免一次断点重复报「城市更新」和子串「更新」。
    maximal = [term for start, end, term in broken
               if not any(a <= start and end <= b and len(other) > len(term)
                          for a, b, other in broken)]
    return sorted(set(maximal))


def title_particle_edges(markup: str) -> list[str]:
    """列出显式断行后落在行首/行尾的助词,供静态封面检查拦截。"""
    lines = re.split(r"<br\s*/?>", markup or "", flags=re.I)
    lines = [re.sub(r"\s+", "", markup_plain(line)) for line in lines]
    edges = []
    for i, line in enumerate(lines):
        if i > 0 and line and line[0] in NO_LEAD:
            edges.append(f"第{i + 1}行以「{line[0]}」起行")
        if i < len(lines) - 1 and line and line[-1] in NO_TAIL:
            edges.append(f"第{i + 1}行以「{line[-1]}」收尾")
    return edges


def plan_lines(text: str, max_lines: int = 2, max_chars: int | None = None,
               even: int = 3, allow_pair_lines: bool = False):
    """把标题切成「行数尽量少、行宽尽量均、且不产生孤字」的行列表。

    max_chars: 单行可容纳的最大字数(次条 383 宽要按这个约束,否则断出来的行放不下)。
    even: 行宽差的权重。默认 3 是"宁可多断一行也别孤字"的普通版式;
          巨字族这类**多行会被共同底色块框住**的版式要传很大的值(如 100),
          逼出等宽断法,否则色块里会出现参差的锯齿留白。
    高置信词组内部的断点有强惩罚,避免"城市更 / 新的三条路"这类字数均匀但语义断裂。
    返回行列表;无法满足时返回 None(调用方保留自动换行)。
    """
    raw = text or ""
    if not raw.strip():
        return []
    hard_lines = re.split(r"<br\s*/?>|\r\n?|\n", raw, flags=re.I)
    if len(hard_lines) > 1:
        # 用户显式换行是硬边界:保留而不重新拼接,超出族容量时交给check拒绝。
        fixed = [line.strip() for line in hard_lines]
        if len(fixed) > max_lines or any(not line for line in fixed):
            return None
        if max_chars and any(visible_len(plain(line)) > max_chars for line in fixed):
            return None
        return fixed
    t = raw.strip()
    units = _units(t)
    n = len(units)
    # 组合枚举是 C(n, k-1):n 一大就指数爆炸(200 字的测试标题曾把检查卡死 5 分钟)。
    # 标题超过 24 个单元已不是标题,直接放弃断行交给 CSS 自动换行。
    if n > 24:
        return None
    unit_offsets = [0]
    for unit in units:
        unit_offsets.append(unit_offsets[-1] + len(unit))
    locked_breaks = _title_term_boundaries(t)
    visible_chars = visible_len(plain(t))
    if max_chars:
        max_chars = max(max_chars, -(-visible_chars // max(1, max_lines)))
    if n <= 1:
        line = "".join(units).strip()
        if max_chars and visible_len(plain(line)) > max_chars:
            return None
        return [line] if line else []
    import itertools
    first_best, first_cost = None, None
    even_best, even_notch = None, None
    for k in range(1, min(max_lines, n) + 1):
        best, best_cost = None, None
        eb, eb_notch = None, None
        # 枚举 k-1 个断点:单元数不多(标题 ≤20 单元),组合可穷举
        for cuts in itertools.combinations(range(1, n), k - 1):
            idx = (0,) + cuts + (n,)
            segs = [units[idx[i]:idx[i + 1]] for i in range(k)]
            firsts = ["".join(s).strip() for s in segs]
            lens = [visible_len(plain(line)) for line in firsts]
            semantic_breaks = sum(unit_offsets[cut] in locked_breaks for cut in cuts)
            if max_chars and any(l > max_chars for l in lens):
                continue
            # 孤字:单行只有 1 个字,或多行里有一行只有 2 个字(视觉上等同孤字)
            if any(l <= 1 or (l == 2 and k > 1 and not allow_pair_lines) for l in lens):
                continue
            bad_lead = any(line.lstrip()[:1] in NO_LEAD for line in firsts[1:])
            bad_tail = any(line.rstrip()[-1:] in NO_TAIL for line in firsts[:-1])
            wid = max(lens) - min(lens)
            # 标点/助词断行是坏味道,但比孤字轻:没别的选时才用
            cost = (10000 * semantic_breaks + even * wid + 3 * (k - 1)
                    + (8 if bad_lead else 0) + (8 if bad_tail else 0))
            if best_cost is None or cost < best_cost:
                best, best_cost = firsts, cost
            # 等宽通道:先比"是否完全等宽",再比断行质量 —— 只有该族需要(even 很大)时才起作用
            key = (semantic_breaks, wid,
                   3 * (k - 1) + (8 if bad_lead else 0) + (8 if bad_tail else 0))
            if eb_notch is None or key < eb_notch:
                eb, eb_notch = firsts, key
        if best and first_cost is None:
            first_best, first_cost = best, best_cost
        # 等宽通道要跨 k 比较:3 行只能 5/5/3 时,必须继续试 4 行的 4/4/3/2。
        # 比较键里 wid 是第一位,行数只是次要点 —— even>=50 的族才有此诉求。
        if eb and (even_notch is None or eb_notch < even_notch):
            even_best, even_notch = eb, eb_notch
        # 等宽族要扫完全部 k 才能知道"多加一行能不能更齐";普通族保持首个有解即返回
        if first_best and even < 50:
            break
    # 等宽解只在 even 很大(被底色块框住的族)时才优先,普通族保持原行为
    if even >= 50 and even_best:
        return even_best
    if first_best:
        return first_best
    # 没有任何断法能避开孤字:_ 时宁可交给自动换行,也不制造"…指/南"
    return None


def break_lines(text: str, max_lines: int = 2, max_chars: int | None = None,
                even: int = 3, allow_pair_lines: bool = False) -> str:
    """plan_lines 的 <br> 化版本;算不出来就原样返回(交给 CSS 兜底)。"""
    lines = plan_lines(text, max_lines, max_chars, even, allow_pair_lines)
    return "<br>".join(lines) if lines else (text or "")


def _em(text: str, tracking: float = 0.0) -> float:
    """Estimate max line width in em, counting each visible grapheme cluster once."""
    widths = []
    invisible = {"Mn", "Me", "Cf", "Cc", "Cs", "Zl", "Zp"}
    for line in re.split(r"<br\s*/?>", text or "", flags=re.I):
        visible = plain(line)
        w = 0.0
        for cluster in grapheme_clusters(visible):
            if cluster.isspace():
                w += 0.32
                continue
            bases = [ch for ch in cluster if unicodedata.category(ch) not in invisible]
            if not bases:
                continue
            if any(_hangul_type(ch) for ch in cluster):
                # A decomposed L/V/T Hangul syllable is one full-width glyph.
                w += 1.0
            elif ("\u200d" in cluster or "\ufe0f" in cluster
                  or any(unicodedata.category(ch) == "So" for ch in bases)):
                # Treat a joined emoji sequence as one glyph, not N code points.
                w += 1.45
            elif any(_is_cjk(ch) or unicodedata.east_asian_width(ch) in {"W", "F"}
                     for ch in bases):
                w += 1.0
            else:
                w += 0.55
        widths.append(w)
    return max(widths or [0.0]) * (1 + tracking)


def title_px(text: str, base: int, floor: int, relax: int = 1, col: int = 383,
             cap: int | None = None) -> int:
    """主标字号:先取「字数档上限」,再按实际字宽反推,最后守可读下限。

    只按字数分档会在 8 字时给出 54px → 8×54=432 > 安全区 383,必然回退断行;
    只看字宽不看字数又会把 12 字压到 56px 以下不可读。两层一起算:
    1) cap = 字数档上限(title_ceiling),且不超过画布高的 33%;
    2) fit = 栏宽能装下的字号(col 已授权放宽到 720,越界由 check 记录)。

    col: 该族实际文字栏宽。骨架族常压到 283–352;全宽族可用到 720。
    """
    if cap is None:
        cap = title_ceiling(longest_line_chars(text))
    base = min(base, cap, int(CANVAS_H * TITLE_SHARE_CAP))
    w = _em(text, 0.02) or 1.0
    fit = int(min(col * 0.96, TITLE_COL_MAX * 0.96) / w)
    # 不再按「中央 383 区容纳 60% 字」压字号:参考样本里 8–10 字主标本来就从左到右
    # 直排,压字号只会把小图里的标题压没。越界由 check 的 title-bleed 守边界(90–810),
    # 多行方案才额外要求核心字可读。
    size = min(base, fit)
    return size if size >= floor else floor


def sub_px(text: str, base: int, floor: int, col: int = 315,
           cap: int | None = None) -> int:
    """次条单行标题字号。col 同上:次条各族栏宽 213–307,默认 315 是 center-band 口径。"""
    if cap is None:
        cap = sub_title_step(longest_line_chars(text))
    base = min(base, cap)
    w = _em(text, 0.02) or 1.0
    return max(floor, min(base, int(col * 0.97 / w)))


def fit_title(text: str, col: int, floor: int, max_lines: int = 2,
              cap: int | None = None) -> tuple[str, int]:
    """主标断行:一行放得下就用一行,只有一行会被压到不可读才拆。

    参考样本里换行的都是「插画/物件已经占了 40%–55% 版面」的版式,或标题超长;
    纯文字版式把 8–10 字拆成 4+4,缩略图上一眼看到的是两截短句,信息反而断开。
    所以规则是:单行字号 >= SINGLE_LINE_MIN_PX 就锁定单行(8–10 字直排的依据),
    否则才在 max_lines 内找能把字号抬起来的断法。
    """
    n = visible_len(plain(text))
    cap = cap if cap is not None else title_ceiling(n)
    single = break_lines(text, 1, n)
    size = title_px(single, cap, floor, col=col, cap=cap)
    if size >= max(floor, SINGLE_LINE_MIN_PX) or max_lines < 2:
        return (single, size)
    best: tuple[str, int] = (single, size)
    for lines in range(2, max(1, max_lines) + 1):
        chars = -(-n // lines)              # 向上取整,保证不超行
        ttl = break_lines(text, lines, chars)
        s = title_px(ttl, cap, floor, col=col, cap=cap)
        if s > best[1] * 1.04:              # 多行得明显更大才值得牺牲直排
            best = (ttl, s)
    return best


def fit_sub_title(text: str, col: int, floor: int, max_lines: int = 2,
                  cap: int | None = None) -> tuple[str, int]:
    """次条(方图)标题:手机缩到指甲盖大,所以要「字大、占满、以换行为主」。

    方图 383×383 里 4 字不再直排,而是 2+2、块高占画布 80%;字数 1–2 才单行。
    含显式 <br> 时按用户硬边界走,只估字号。
    """
    raw = text or ""
    n = visible_len(plain(raw))
    if re.search(r"<br\s*/?>|\r?\n", raw, flags=re.I):
        ttl = raw
    else:
        lines = 1 if n <= 2 else min(2, max(1, max_lines))
        chars = -(-n // lines) if n else 1
        # 次条允许 2 字一行(方图大字的设计),主标题的"孤字"禁忌在这里不适用
        ttl = break_lines(raw, lines, chars, even=100, allow_pair_lines=True)
    per_line = max(1, -(-visible_len(plain(ttl)) // max(1, ttl.count("<br>") + 1)))
    line_count = max(1, ttl.count("<br>") + 1)
    # 块高必须用 CSS 的真实行高算:此前按 1.12 估、CSS 写 1.3,4 字方图 136px
    # 实际 354px > 画布,眉题被挤出画布顶边、标题也不居中。
    by_h = int(SUB_CANVAS * SUB_BLOCK_H_RATIO / (line_count * SUB_LINE_HEIGHT))
    # 栏宽也是硬约束:plate-page 次条只有 206px 文字列,方图大字要让位给它
    col_w = min(SUB_CANVAS * SUB_BLOCK_W_RATIO, col * 0.97)
    by_w = int(col_w / (per_line * 1.02))
    size = max(floor, min(by_h, by_w, cap if cap is not None else SUB_TITLE_STEPS[1]))
    return (ttl, size)


def _center_band(t, d, sub=False):
    # 主封面:字数档定上限,栏宽授权到 720(允许越过 383 语义区);次条窄,必须断
    floor, col = 28, (315 if sub else TITLE_COL_MAX)
    ttl, size = (fit_sub_title(d["title"], col, floor, 2) if sub
                 else fit_title(d["title"], col, floor, 2))
    main_px = size
    # 色带跟随字宽生长:标题越过 383 时带子一起放宽,不让字形溢出带外压边(上限 720)
    band_w = 383
    if not sub:
        band_w = max(383, min(TITLE_COL_MAX, int(_em(ttl, 0.02) * size + 56)))
    parts = ['<div class="mark" data-role="decor"></div>']
    if d["kicker"]:
        parts.append(f'<div class="kicker" data-role="info">{esc(d["kicker"])}</div>')
    parts.append(f'<h1 class="t" data-role="info">{esc(ttl)}</h1>')
    if d["sub"]:
        parts.append(f'<div class="sub" data-role="info">{esc(d["sub"])}</div>')
    if not sub:
        parts.append('<div class="rule" data-role="decor"></div>')
    body = "".join(parts)
    safe = f'<div class="safe" data-band="safe">{body}</div>'
    # 中央色带是主结构层,不是只靠背景纹理的文字模板。
    decor = ['<div class="band" data-role="decor"></div>']
    if not sub:
        decor.append('<div class="bar" data-role="decor"></div>')
        if d["num"]:
            decor.append(f'<div class="num" data-role="decor">{esc(d["num"])}</div>')
        if d["title_en"]:
            decor.append(f'<div class="wm" data-role="decor">{esc(d["title_en"])}</div>')
    elif d["title_en"] and d["sub_mode"] != "minimal":
        decor.append(f'<div class="wm" data-role="decor">{esc(d["title_en"])}</div>')
    if not sub and d["footer"]:
        decor.append(f'<div class="footer" data-role="decor">{esc(d["footer"])}</div>')
    # 色带宽度写死进 CSS(而不是只留在 var()):静态检查要能解析出真实像素,
    # 否则安全区会被当作 full-bleed 而无法验证"标题是否还在画布内"。
    css = CB_CSS_SUB if sub else CB_CSS.replace("var(--band-w, 383px)", f"{band_w}px")
    return ("".join(decor) + safe, main_px, css, {"band_w": f"{band_w}px"})


# ================================================================ 族二:band-editorial

BE_CSS = """
/* 左文带横穿左侧 80% 版面,覆盖 0–720 全高;文字列 84–720(满版,右侧留 180px 呼吸) */
.panel { left: 0px; top: 0px; bottom: 0px; width: 720px;
  background: var(--c-plate); border: 1px solid var(--c-line); }
.panel::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 6px;
  background: var(--c-accent); }
.safe { left: 84px; top: 30px; bottom: 30px; width: 636px;
  display: flex; flex-direction: column; justify-content: center;
  align-items: flex-start; text-align: left; gap: 13px; }
.kicker { font: 600 14px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .30em; display: flex; gap: 10px; align-items: center; }
.kicker::before { content: ""; width: 22px; height: 2px; background: var(--c-accent); }
.t { font: 700 var(--t-size)/1.2 var(--font-display); color: var(--c-ink);
  letter-spacing: .01em; max-width: 636px; }
.sub { font: 400 17px/1.5 var(--font-sans); color: var(--c-muted);
  letter-spacing: .08em; max-width: 470px; }
.wm { right: -40px; top: 50%; transform: translateY(-50%); white-space: nowrap;
  font: 800 150px/1 var(--font-display); letter-spacing: -.02em;
  color: var(--c-ink); opacity: .07; }
.num { right: 46px; bottom: 24px; font: 800 96px/1 var(--font-display);
  color: var(--c-accent); opacity: .26; }
.side { right: 18px; top: 42px; bottom: 42px; writing-mode: vertical-rl;
  font: 600 14px/1 var(--font-sans); color: var(--c-muted); letter-spacing: .48em; }
/* 页脚进流(margin-top:auto):绝对定位会和 justify-content:center 的内容抢位置 */
.footer { position: relative; margin-top: auto; margin-bottom: 14px; width: 100%;
  font: 500 13px/1 var(--font-sans);
  color: var(--c-muted); letter-spacing: .28em; }
"""

BE_CSS_SUB = """
/* 次条面板与主封同构:留边距 + 左侧竖条。贴边通栏会让次条像被裁掉一块
   (主封有 30px 边距,次条若 0 边距,两图并排就是两套视觉语言) */
.panel { left: 22px; top: 22px; bottom: 22px; right: 22px;
  background: var(--c-plate); border: 1px solid var(--c-line); }
.panel::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
  background: var(--c-accent); }
/* 文字栏 295:left 56 + 295 = 351,落在 8% 安全边距(352.36)内。
   原来写 315 会顶到 371 —— 面板右边界 361,文字直接压着描边出去。 */
.safe { left: 50%; top: 22px; bottom: 22px; width: 295px; transform: translateX(-50%);
  display: flex; flex-direction: column; justify-content: center;
  align-items: flex-start; text-align: left; gap: 11px; }
.kicker { font: 600 12px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .28em; }
.t { font: 700 var(--t-size)/1.24 var(--font-display); color: var(--c-ink);
  letter-spacing: .01em; max-width: 295px; }
.sub { font: 400 14px/1.5 var(--font-sans); color: var(--c-muted); max-width: 290px; }
.wm { right: -30px; top: 50%; transform: translateY(-50%); white-space: nowrap;
  font: 800 96px/1 var(--font-display); color: var(--c-ink); opacity: .07; }
"""


def _band_editorial(t, d, sub=False):
    # 主封文字栏 560(8–10 字直排)/ 次条 295(方图大字 2 字一行)
    ttl, main_px = (fit_sub_title(d["title"], 295, 28, 2) if sub
                    else fit_title(d["title"], 636, 28, 2))
    parts = []
    if d["kicker"]:
        parts.append(f'<div class="kicker" data-role="info">{esc(d["kicker"])}</div>')
    parts.append(f'<h1 class="t" data-role="info">{esc(ttl)}</h1>')
    if d["sub"]:
        parts.append(f'<div class="sub" data-role="info">{esc(d["sub"])}</div>')
    # 页脚进流尾:绝对定位的页脚会和 justify-content:center 的正文抢位置,压到副题上
    if not sub and d["footer"]:
        parts.append(f'<div class="footer" data-role="decor">{esc(d["footer"])}</div>')
    safe = ('<div class="safe" data-band="safe">' + "".join(parts) + '</div>')
    decor = ['<div class="panel" data-role="decor"></div>']
    wm = d["title_en"] if (not sub or d["sub_mode"] != "minimal") else ""
    if wm:
        decor.append(f'<div class="wm" data-role="decor">{esc(wm)}</div>')
    if not sub:
        if d["num"]:
            decor.append(f'<div class="num" data-role="decor">{esc(d["num"])}</div>')
        if d["side_label"]:
            decor.append(f'<div class="side" data-role="decor">{esc(d["side_label"])}</div>')
    return "".join(decor) + safe, main_px, BE_CSS_SUB if sub else BE_CSS


# ================================================================ 族三:stack-cards

SC_CSS = """
.card { left: 258px; top: 48px; width: 384px; height: 287px;
  background: var(--c-contrast); border-radius: 16px; box-shadow: var(--c-shadow); }
/* 卡内色条:相对卡片四周退让 24px,不再充当贴边页脚线 */
.band { left: 50%; top: 80px; transform: translateX(-50%); width: 336px; height: 64px;
  background: var(--c-plate); border: 1px solid var(--c-accent);
  border-left-width: 6px; border-radius: 8px; }
.safe { left: 50%; top: 80px; transform: translateX(-50%);
  width: 336px; height: 223px;
  display: flex; flex-direction: column; justify-content: flex-start; align-items: center;
  text-align: center; gap: 0; }
.kicker { width: 100%; height: 64px; flex: 0 0 64px;
  display: flex; justify-content: center; align-items: center;
  font: 600 13px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .32em; text-indent: .32em; }
.t { margin-top: 14px; font: 700 var(--t-size)/1.18 var(--font-display); color: var(--c-bg);
  letter-spacing: .02em; max-width: 331px; }
.sub { margin-top: auto; font: 400 15px/1.45 var(--font-sans); color: var(--c-bg); opacity: .62;
  letter-spacing: .06em; max-width: 300px; }
.rule { margin-top: 10px; width: 44px; height: 3px; background: var(--c-accent); }
.sticker { width: 92px; height: 92px; border-radius: 50%;
  background: var(--c-accent); color: var(--c-bg);
  display: flex; align-items: flex-end; justify-content: center;
  font: 700 17px/1.1 var(--font-display); text-align: center; padding-bottom: 14px;
  transform: rotate(-6deg); box-shadow: var(--c-shadow); }
.sticker-r { top: 24px; right: 32px; }
.num { left: 36px; bottom: 24px; font: 800 76px/1 var(--font-display);
  color: var(--c-accent); opacity: .34; }
.wm { left: 16px; top: 22px; writing-mode: vertical-rl;
  font: 700 15px/1 var(--font-sans); color: var(--c-ink); opacity: .20;
  letter-spacing: .42em; }
"""

SC_CSS_SUB = """
.card { left: 28px; top: 28px; width: 327px; height: 327px;
  background: var(--c-contrast); border-radius: 16px; box-shadow: var(--c-shadow); }
.band { left: 50%; top: 45px; transform: translateX(-50%); width: 283px; height: 56px;
  background: var(--c-plate); border: 1px solid var(--c-accent);
  border-left-width: 5px; border-radius: 7px; }
.safe { left: 50%; top: 45px; transform: translateX(-50%);
  width: 283px; bottom: 45px;
  display: flex; flex-direction: column; justify-content: flex-start; align-items: center;
  text-align: center; gap: 0; }
.kicker { width: 100%; height: 56px; flex: 0 0 56px;
  display: flex; justify-content: center; align-items: center;
  font: 600 11px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .28em; text-indent: .28em; }
.t { margin-top: 12px; font: 700 var(--t-size)/1.2 var(--font-display); color: var(--c-bg);
  max-width: 283px; }
.sub { margin-top: auto; font: 400 13px/1.45 var(--font-sans); color: var(--c-bg); opacity: .62;
  max-width: 260px; }
.rule { margin-top: 8px; width: 36px; height: 3px; background: var(--c-accent); }
.sticker { width: 66px; height: 66px; border-radius: 50%;
  background: var(--c-accent); color: var(--c-bg);
  display: flex; align-items: flex-end; justify-content: center;
  font: 700 13px/1.1 var(--font-display); text-align: center; padding-bottom: 9px;
  transform: rotate(-5deg); right: 2px; top: 2px; }
"""


def _stack_cards(t, d, sub=False):
    # 次条卡片内栏 283px → 长标题可到 4 行;主封 331px 守 2 行
    ttl, main_px = (fit_sub_title(d["title"], 283, 28, 4) if sub
                    else fit_title(d["title"], 331, 28, 2))
    parts = []
    if d["kicker"]:
        parts.append(f'<div class="kicker" data-role="info">{esc(d["kicker"])}</div>')
    else:
        # 保留内色带的眉题高度,无眉题时不把标题推到色带顶端。
        parts.append('<div class="kicker" data-role="decor"></div>')
    parts.append(f'<h1 class="t" data-role="info">{esc(ttl)}</h1>')
    parts.append('<div class="rule" data-role="decor"></div>')
    if d["sub"]:
        parts.append(f'<div class="sub" data-role="info">{esc(d["sub"])}</div>')
    safe = ('<div class="safe" data-band="safe">' + "".join(parts) + '</div>')
    decor = ['<div class="card" data-role="decor"></div>',
             '<div class="band" data-role="decor"></div>']
    if d["badge"]:
        decor.append(f'<div class="sticker sticker-r" data-role="decor">'
                     f'{esc(d["badge"])}</div>')
    if d["sub_mode"] != "minimal":
        if not sub and d["num"]:
            decor.append(f'<div class="num" data-role="decor">{esc(d["num"])}</div>')
        if d["title_en"]:
            decor.append(f'<div class="wm" data-role="decor">{esc(d["title_en"])}</div>')
    return "".join(decor) + safe, main_px, SC_CSS_SUB if sub else SC_CSS


# ================================================================ 族四:giant-caps

GC_CSS = """
.water { left: 50%; top: 50%; transform: translate(-50%, -50%);
  font: 800 300px/0.84 var(--font-display); letter-spacing: -.03em;
  color: transparent; -webkit-text-stroke: 1.5px var(--c-ink); opacity: .16;
  white-space: nowrap; }
.safe { left: 50%; top: 30px; bottom: 30px; transform: translateX(-50%);
  width: var(--block-w, 383px); max-width: 720px;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; gap: 10px; }
.t { font: 800 var(--t-size)/0.92 var(--font-display); color: var(--c-ink);
  letter-spacing: -.02em; white-space: nowrap; }
.kicker { font: 600 15px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .44em; text-indent: .44em; }
.sub { font: 500 17px/1.4 var(--font-sans); color: var(--c-muted);
  letter-spacing: .10em; max-width: 340px; }
.rule { width: 100px; height: 2px; background: var(--c-accent); }
.num { left: 34px; bottom: 24px; font: 800 60px/1 var(--font-display);
  color: var(--c-accent); opacity: .30; }
.footer { right: 30px; bottom: 26px; font: 500 14px/1 var(--font-sans);
  color: var(--c-muted); letter-spacing: .3em; }
.side { right: 16px; top: 36px; bottom: 36px; writing-mode: vertical-rl;
  font: 600 13px/1 var(--font-sans); color: var(--c-muted); letter-spacing: .46em; }
"""

GC_CSS_SUB = """
.water { left: 50%; top: 50%; transform: translate(-50%, -50%);
  font: 800 172px/0.84 var(--font-display); color: transparent;
  -webkit-text-stroke: 1.2px var(--c-ink); opacity: .14; white-space: nowrap; }
.safe { left: 50%; top: 24px; bottom: 24px; transform: translateX(-50%);
  width: 307px; display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; gap: 10px; }
.t { font: 800 var(--t-size)/0.98 var(--font-display); color: var(--c-ink);
  letter-spacing: -.01em; white-space: nowrap; }
.kicker { font: 600 12px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .38em; text-indent: .38em; }
.sub { font: 500 14px/1.4 var(--font-sans); color: var(--c-muted); max-width: 300px; }
.rule { width: 68px; height: 2px; background: var(--c-accent); }
"""


def _giant_caps(t, d, sub=False):
    # 巨字族靠"字即画布":主封面超 4 字就该换族;这里守到 5 字并以 300 宽反推字号。
    # 次条画布 307 宽,4 字以上必须断行,否则一定压边。
    n = visible_len(plain(d["title"]))
    # 巨字族的标题被同一个底色块框住:必须断成等宽行,否则块里是锯齿。
    # 行数上限 4:13 字以内,主封按 4 行才有 4/4/3/2 这类齐整断法。
    if sub:
        # 次条方图:字要大、块要占满。复用统一的大字方图算法(4 字 → 2+2、块高 80%)
        ttl, main_px = fit_sub_title(d["title"], 307, 28, 2)
        longest = max(1, max(len(x) for x in ttl.split("<br>")))
    else:
        ttl = break_lines(d["title"], 4, 5, even=100) if n > 5 else break_lines(d["title"], 1)
        # 四档上限取「字数档 × 画布占比」:1–3 字 137 / 4 字 132 / 5 字 118(与 title-share 36% 同源)
        main_px = 137 if n <= 3 else 132 if n <= 4 else 118
        # 字号必须同时满足「最长行装得下」和「总高度不超框」;行宽上限放宽到 720
        longest = max(1, max(len(x) for x in ttl.split("<br>")))
        rows = ttl.count("<br>") + 1
        main_px = min(main_px, int(CANVAS_H * TITLE_SHARE_CAP),
                      int(TITLE_COL_MAX * 0.96 / longest), int(340 / rows))
    # 色块宽度按"最长行"定,不按容器宽定 —— 否则断行后各行宽窄不一,色块撑歪成台阶
    # 色块要含左右各 16px 内边距(tone 的 padding),否则字形会顶出色块边缘
    block_w = min(TITLE_COL_MAX if not sub else 307,
                  int(longest * main_px * 1.06) + 32)
    parts = []
    if d["kicker"]:
        parts.append(f'<div class="kicker" data-role="info">{esc(d["kicker"])}</div>')
    parts.append(f'<h1 class="t" data-role="info">{esc(ttl)}</h1>')
    parts.append('<div class="rule" data-role="decor"></div>')
    if d["sub"]:
        parts.append(f'<div class="sub" data-role="info">{esc(d["sub"])}</div>')
    safe = ('<div class="safe" data-band="safe">' + "".join(parts) + '</div>')
    decor = []
    # 水印层:优先用显式英文;无英文时仅短标题(≤4 字)可作描边水印,长中文标题会裁成噪点
    water = d["title_en"] or (plain(d["title"]) if visible_len(plain(d["title"])) <= 4 else "")
    if water and (d["sub_mode"] != "minimal" or d["title_en"]):
        decor.append(f'<div class="water" data-role="decor">{esc(water)}</div>')
    decor.append(safe)
    if not sub:
        if d["num"]:
            decor.append(f'<div class="num" data-role="decor">{esc(d["num"])}</div>')
        if d["footer"]:
            decor.append(f'<div class="footer" data-role="decor">{esc(d["footer"])}</div>')
        if d["side_label"]:
            decor.append(f'<div class="side" data-role="decor">{esc(d["side_label"])}</div>')
    css = GC_CSS_SUB if sub else GC_CSS.replace("var(--block-w, 383px)", f"{block_w}px")
    return "".join(decor), main_px, css, {"block_w": block_w}


# ================================================================ 族五:kraft-note

KN_CSS = """
.strip { left: 30px; top: 0; bottom: 0; width: 4px; background: var(--c-accent); opacity: .55; }
.safe { left: 262px; top: 26px; bottom: 26px; width: 348px;
  display: flex; flex-direction: column; justify-content: center;
  align-items: flex-start; text-align: left; gap: 12px; }
.t { font: 700 var(--t-size)/1.16 var(--font-display); color: var(--c-ink);
  letter-spacing: .01em; max-width: 348px; transform: rotate(-1.2deg);
  /* 标题带 -1.2° 手写倾斜:旋转后的外接盒比原宽大,留 1.06 系数防末字被裁 */
  white-space: normal; }
.kicker { font: 600 14px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .26em; }
.sub { font: 500 16px/1.5 var(--font-sans); color: var(--c-ink); opacity: .72;
  letter-spacing: .06em; max-width: 320px; }
.note { width: 108px; height: 76px; background: rgba(255,255,255,.82);
  box-shadow: 0 6px 16px rgba(0,0,0,.22); transform: rotate(2deg);
  display: flex; align-items: center; justify-content: center;
  font: 700 15px/1.15 var(--font-display); color: var(--c-bg); text-align: center; }
.note-r { right: 34px; top: 38px; }
.tagnote { right: 34px; bottom: 36px; width: 132px; padding: 10px 12px;
  background: var(--c-ink); color: var(--c-bg); transform: rotate(-2deg);
  font: 600 13px/1.4 var(--font-sans); letter-spacing: .06em; }
.tape { width: 74px; height: 22px; background: rgba(255,255,255,.34);
  transform: rotate(-6deg); }
.tape-l { left: 44px; top: 26px; }
.tape-r { right: 42px; top: 26px; transform: rotate(5deg); }
.stereotype { right: 20px; top: 50%; transform: translateY(-50%) rotate(90deg);
  font: 700 12px/1 var(--font-sans); color: var(--c-ink); opacity: .34;
  letter-spacing: .5em; white-space: nowrap; }
.footer { position: relative; margin-top: auto; margin-bottom: 10px;
  font: 500 13px/1 var(--font-sans);
  color: var(--c-ink); opacity: .5; letter-spacing: .26em; }
"""

KN_CSS_SUB = """
.safe { left: 38px; top: 26px; bottom: 26px; width: 307px;
  display: flex; flex-direction: column; justify-content: center;
  align-items: flex-start; text-align: left; gap: 11px; }
.t { font: 700 var(--t-size)/1.2 var(--font-display); color: var(--c-ink);
  max-width: 307px; transform: rotate(-1.2deg); }
.kicker { font: 600 12px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .24em; }
.sub { font: 500 14px/1.5 var(--font-sans); color: var(--c-ink); opacity: .72;
  max-width: 290px; }
.tape { width: 60px; height: 18px; background: rgba(255,255,255,.34);
  left: 26px; top: 22px; transform: rotate(-6deg); }
.tagnote { right: 20px; bottom: 22px; width: 104px; padding: 8px 10px;
  background: var(--c-ink); color: var(--c-bg); transform: rotate(-2deg);
  font: 600 11px/1.35 var(--font-sans); }
"""


def _kraft_note(t, d, sub=False):
    # 主封面文字栏 348 → 6 字/行;次条 307 → 5 字/行。
    # 标题带 -1.2° 手写倾斜,外接盒更宽:字号要按 0.92 栏宽再留 1.06 系数算,否则末字会被裁。
    # 栏宽 ×0.92 抵扣 -1.2° 旋转后的外接盒增量(倾斜标题的末字比直排更容易被裁)
    col = int((315 if sub else 348) * 0.92)
    ttl, main_px = (fit_sub_title(d["title"], col, 28, 2) if sub
                    else fit_title(d["title"], col, 28, 2))
    parts = []
    if d["kicker"]:
        parts.append(f'<div class="kicker" data-role="info">{esc(d["kicker"])}</div>')
    parts.append(f'<h1 class="t" data-role="info">{esc(ttl)}</h1>')
    if d["sub"]:
        parts.append(f'<div class="sub" data-role="info">{esc(d["sub"])}</div>')
    # 页脚进流:绝对定位会压到副题,或随内容撑出画布被裁
    if not sub and d["footer"]:
        parts.append(f'<div class="footer" data-role="decor">{esc(d["footer"])}</div>')
    safe = ('<div class="safe" data-band="safe">' + "".join(parts) + '</div>')
    decor = ['<div class="tape" data-role="decor"></div>' if sub
             else '<div class="tape tape-l" data-role="decor"></div>']
    if d["badge"]:
        decor.append(f'<div class="tagnote" data-role="decor">{esc(d["badge"])}</div>')
    if not sub:
        decor.append('<div class="strip" data-role="decor"></div>')
        if d["title_en"] and d["sub_mode"] != "minimal":
            decor.append(f'<div class="stereotype" data-role="decor">'
                         f'{esc(d["title_en"])}</div>')
        if d["num"]:
            decor.append('<div class="tape tape-r" data-role="decor"></div>')
            decor.append(f'<div class="note note-r" data-role="decor">{esc(d["num"])}</div>')
    return "".join(decor) + safe, main_px, KN_CSS_SUB if sub else KN_CSS


# ================================================================ 族六:plate-page

PP_CSS = """
/* 右侧装饰图窗 x=672–900;文字栏 x=272 起,完整落在内部 383px 安全区 */
.plate { left: 672px; top: 0; bottom: 0; width: 228px; overflow: hidden;
  background: linear-gradient(160deg, var(--c-accent) 0%, var(--c-bg2) 100%); }
.plate-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
  object-position: center; }
.plate::after { content: ""; position: absolute; inset: 18px;
  border: 1px solid rgba(255,255,255,.45); pointer-events: none; }
.plate-glyph { left: 672px; top: 0; width: 228px; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  font: 800 92px/1 var(--font-display); color: #fff; opacity: .34; }
.safe { left: 272px; top: 26px; bottom: 26px; width: 352px;
  display: flex; flex-direction: column; justify-content: center;
  align-items: flex-start; text-align: left; gap: 13px; }
.kicker { font: 600 14px/1 var(--font-sans); color: var(--c-accent);
  letter-spacing: .34em; }
.t { font: 700 var(--t-size)/1.2 var(--font-display); color: var(--c-ink);
  letter-spacing: .02em; max-width: 352px; }
.rule { width: 52px; height: 1px; background: var(--c-line); }
.meta { font: 500 14px/1.6 var(--font-sans); color: var(--c-muted); letter-spacing: .14em; }
.meta b { color: var(--c-ink); font-weight: 600; }
.sub { font: 400 16px/1.45 var(--font-sans); color: var(--c-muted); max-width: 330px; }
.side { left: 44px; top: 32px; writing-mode: vertical-rl;
  font: 600 13px/1 var(--font-sans); color: var(--c-muted); letter-spacing: .5em; }
.num { right: 30px; top: 24px; font: 800 72px/1 var(--font-display);
  color: var(--c-accent); opacity: .30; }
.wm { right: 26px; bottom: 22px; font: 700 13px/1 var(--font-sans);
  color: var(--c-muted); letter-spacing: .3em; }
"""

PP_CSS_SUB = """
/* 次条同构为右侧 123px 竖向照片窗;文案固定在中央安全区 x=34–240。 */
.plate { left: 260px; top: 0; bottom: 0; width: 123px; overflow: hidden;
  background: linear-gradient(160deg, var(--c-accent) 0%, var(--c-bg2) 100%); }
.plate-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
  object-position: center; }
.plate::after { content: ""; position: absolute; inset: 12px;
  border: 1px solid rgba(255,255,255,.45); pointer-events: none; }
.plate-glyph { left: 260px; top: 0; width: 123px; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  font: 800 46px/1 var(--font-display); color: #fff; opacity: .34; }
.safe { left: 34px; top: 26px; bottom: 26px; width: 206px;
  display: flex; flex-direction: column; justify-content: center;
  align-items: flex-start; text-align: left; gap: 9px; }
.kicker { font: 600 11px/1 var(--font-sans); color: var(--c-accent); letter-spacing: .3em; }
.t { font: 700 var(--t-size)/1.22 var(--font-display); color: var(--c-ink); max-width: 206px; }
.rule { width: 36px; height: 1px; background: var(--c-line); }
.meta { font: 500 12px/1.5 var(--font-sans); color: var(--c-muted); letter-spacing: .1em; }
.meta.meta-inline { display: flex; flex-wrap: wrap; width: 100%; max-width: 206px;
  column-gap: 7px; row-gap: 0; }
.meta-item { display: inline-block; white-space: nowrap; }
.meta-item + .meta-item::before { content: "·"; margin-right: 5px; }
.sub { font: 400 12px/1.4 var(--font-sans); color: var(--c-muted); max-width: 200px; }
"""


def _plate_page(t, d, sub=False):
    if not d.get("image"):
        raise ValueError("plate-page requires a local raster image")
    # 主封安全栏 352px;次条 206px,照片只在右侧出血窗,不侵入文字栏。
    ttl, main_px = (fit_sub_title(d["title"], 206, 28, 2) if sub
                    else fit_title(d["title"], 352, 28, 2))
    parts = []
    if d["kicker"]:
        parts.append(f'<div class="kicker" data-role="info">{esc(d["kicker"])}</div>')
    parts.append(f'<h1 class="t" data-role="info">{esc(ttl)}</h1>')
    parts.append('<div class="rule" data-role="decor"></div>')
    meta_bits = [esc(x) for x in d["meta"] if x]
    if meta_bits:
        if sub:
            items = "".join(f'<span class="meta-item">{x}</span>' for x in meta_bits)
            parts.append(f'<div class="meta meta-inline" data-role="info">{items}</div>')
        else:
            parts.append('<div class="meta" data-role="info">'
                         + "<br>".join(f"<b>{x}</b>" for x in meta_bits) + '</div>')
    if d["sub"] and (not sub or d["sub_mode"] != "minimal"):
        parts.append(f'<div class="sub" data-role="info">{esc(d["sub"])}</div>')
    safe = ('<div class="safe" data-band="safe">' + "".join(parts) + '</div>')
    glyph = (d["title_en"] or plain(d["title"])[:1])[:2]
    image_src = html.escape(str(d["image"]), quote=True)
    photo = (f'<div class="plate" data-role="decor">'
             f'<img class="plate-image" src="{image_src}" alt=""></div>')
    decor = [photo, f'<div class="plate-glyph" data-role="decor">{esc(glyph)}</div>']
    if not sub:
        if d["num"]:
            decor.append(f'<div class="num" data-role="decor">{esc(d["num"])}</div>')
        if d["footer"]:
            decor.append(f'<div class="wm" data-role="decor">{esc(d["footer"])}</div>')
        if d["side_label"]:
            decor.append(f'<div class="side" data-role="decor">{esc(d["side_label"])}</div>')
    return "".join(decor) + safe, main_px, PP_CSS_SUB if sub else PP_CSS


# ================================================================ 渲染入口

_RENDERERS = {
    "center-band": _center_band,
    "band-editorial": _band_editorial,
    "stack-cards": _stack_cards,
    "giant-caps": _giant_caps,
    "kraft-note": _kraft_note,
    "plate-page": _plate_page,
}


def make_data(title, kicker="", sub="", footer="", num="", title_en="",
              badge="", side_label="", meta=None, accent_tone="auto",
              sub_mode="same", image=None) -> dict:
    return {
        "title": title, "kicker": kicker, "sub": sub, "footer": footer,
        "num": num, "title_en": title_en, "badge": badge,
        "side_label": side_label, "meta": list(meta or []),
        "accent_tone": accent_tone, "sub_mode": sub_mode, "image": image,
    }


def render(layout: str, t: dict, d: dict, font_vars: str,
           sub: bool = False, pattern: str = "auto", tone: str = "auto",
           fx: str = "", font_faces: str = "", bg_recipe: str = "",
           bg_photo: str = "") -> str:
    """渲染一张封面 HTML。调用方保证 layout 已校验。

    fx: 着色器底材名(见 SHADER_FX);空/auto 时取族默认;'none' 关掉。
    """
    fn = _RENDERERS.get(layout) or _RENDERERS[DEFAULT_LAYOUT]
    res = fn(t, d, sub)
    body, size, css = res[0], res[1], res[2]
    extra = res[3] if len(res) > 3 else {}
    # 次条字号由 fit_sub_title 按「块高 80% + 栏宽」反推,不再二次用字数档压回来:
    # 方图缩到手机指甲盖大时,4 字压到 112px 就只剩半屏,传达不起来。
    pat, fx = resolve_visual_layers(layout, pattern, fx)
    if sub:
        css = css + "\n" + sub_center_css(t)
    flat_sub = sub and d.get("sub_mode") == "flat"
    if flat_sub:
        # flat 只作用于次条:禁用其底纹/shader,用纯主题底色而保留 plate-page 的照片。
        pat, fx = "none", ""
    ton = resolve_tone(layout, tone)
    tone_css = _tone_css(ton)
    # pill/capsule 已在族内 `.sub`/`.t` 上定义,这里只补全局覆盖
    full_css = css + ("\n/* 强调处理 */\n" + tone_css if tone_css else "")
    # 族内算出的量(如色块宽度)——必须进变量,否则 CSS 里 var(--x) 取不到值
    if extra:
        # 长度类计量必须带单位:--block-w: 288 是无效 CSS 长度,var() 会退化成 auto
        def _decl(k, v):
            name = k.replace("_", "-")
            unit = "px" if isinstance(v, int) and name.endswith(("-w", "-size")) else ""
            return f"--{name}: {v}{unit};"
        full_css += "\n/* 版式计量 */\n.poster { " + " ".join(
            _decl(k, v) for k, v in extra.items()) + " }\n"
    w, h = (383, 383) if sub else (900, 383)
    title = re.sub(r"<br\s*/?>", " ", plain(d["title"]) or "", flags=re.I)
    if fx:
        body = fx_canvas(fx, t) + body
    if flat_sub:
        bg_recipe, bg_photo = "", ""  # flat 次条是纯色底,不叠外层背景
    return canvas(w, h, t, layout, pat, ton, size, body,
                  root_vars(t, font_vars, font_faces) + full_css,
                  title, "sub" if sub else "main", fx=fx,
                  sub_mode=d.get("sub_mode", "same"), bg_recipe=bg_recipe,
                  bg_photo=bg_photo)


def layout_list_text() -> str:
    rows = ["可用版式族(--layout):"]
    for x in LAYOUTS:
        rows.append(f"  {x['slug']:<15} {x['name']}({x['tone']}, {x['layers']} 层)")
        rows.append(f"      适合:{x['fits']}")
        rows.append(f"      别用:{x['avoid']}")
    rows.append(f"  默认:{DEFAULT_LAYOUT}(与旧版居中版式一致,不加 --layout 行为不变)")
    return "\n".join(rows)
