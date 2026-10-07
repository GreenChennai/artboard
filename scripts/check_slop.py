"""artboard AI 味与铁律机检(静态,零渲染)。

为什么需要它:`check_overflow.py` 只看得见"几何"(越框/安全区),看不见"气质"——
默认 indigo、紫蓝渐变、emoji 当图标、编造指标这些**一眼 AI** 的特征,以及
铁律 1/2(固定画布/离线渲染)的静态违反,全靠人工目检。本脚本把 open-design
`apps/daemon/src/lint-artifact.ts`(Apache-2.0)的成品 HTML linter 规则集移植过来,
并按 artboard 自己的口径重定级(差异逐条注在规则旁)。

用法:
  python check_slop.py <项目目录|src目录|HTML文件>
  python check_slop.py src --strict            # P1 也算阻断(默认只 P0 阻断)
  python check_slop.py src --only P0           # 只看某级别
  python check_slop.py src --list-rules        # 列出全部规则与级别
传**目录**时逐页查该目录下所有 HTML(多页 PPT/三折页不再只查第一页)。

输出:stdout 单行 JSON;人类可读清单走 stderr。
退出码:0 = 无 P0(P2/P1 只是提示) / 1 = 有 P0(或 --strict 下有 P1) / 2 = 用法错。

规则(级别 —— 谁能拦住):
  P0 external-ref          离线铁律 2:HTML 引用 http(s) 资源(字体/图/脚本/iframe)
  P0 canvas-discipline     铁律 1:position:fixed / 100vh / 100vw(H5 页自动降 P1)
  P0 ai-default-indigo     默认 LLM 强调色(Tailwind indigo/violet 那 7 个 hex)
  P0 purple-gradient       紫/蓝紫渐变("大众脸"第一名;含 purple/violet 关键词)
  P0 trust-gradient        蓝→青两段式"信任渐变"(SaaS hero 陈词)
  P0 emoji-icon            emoji 当图标(结构语境:标题/按钮/列表项/icon 元素)
  P0 invented-metric       编造指标("10× faster""99.9% uptime""效率提升 N 倍"…)
  P0 filler-copy           填充文案(lorem ipsum / feature one / 待补充…)
  P0 sans-display          标题硬编码 Inter/Roboto/system-ui 当展示体
  P0 cjk-leading           **中文**标题行高 < 1.3(强制换行时 P0;单行降 P1)
  P1 left-accent-card      圆角卡 + 左彩边(AI 仪表盘卡经典形)
  P1 all-caps-no-tracking  uppercase 无 ≥0.06em 字距(token 感知)
  P1 raw-hex               :root 外裸 hex > 12 个(token 没被遵守)
  P1 accent-overuse        正文里强调色引用 > 6 次(每屏可见 ≤2 处)
  P1 cjk-negative-tracking 中文标题负字距(促销风例外)

级别台账在 `RULE_META`,是**唯一真相源** —— 本表与 `--list-rules` 都从它渲染,
改级别只改一处。合计 10 条 P0 + 5 条 P1(无 P2)。

豁免(与 check_overflow 的 data-allow-* 同源):
  - 文件级:`<!-- slop-ignore: filler-copy,invented-metric -->` 或 `<!-- slop-ignore: all -->`
    —— 任一位置的注释即可;用于"确实要保留"的例外,交付时要在报告里说明理由。
  - token 定义块(`:root` / `html` / `[data-theme]` 内的声明)里的颜色不算违规:
    品牌色/设计系统**有意**把 indigo 写成 `--accent` 是设计决策,不是模型默认。

实测口径:纯 stdlib、无浏览器、单页 <0.3s(比 check_overflow 快两个数量级,
所以两者的分工是"每次重导前都跑 slop,overflow 按需")。

与上游 lint-artifact.ts 的差异(抄写合规:Apache-2.0,改编处逐条标注):
  1. **多两条 artboard 铁律**:`external-ref`(铁律 2 离线渲染)、`canvas-discipline`
     (铁律 1 固定画布)—— 上游没有这两条,但它们是本技能最硬的约束;
  2. **`left-accent-card` 由 P0 降 P1**:上游把"圆角+左彩边卡"一票否决,artboard 的
     引用卡/要点卡**合法**使用左彩边,阻断会误伤 → 降为建议;
  3. **新增 `cjk-leading` / `cjk-negative-tracking`**:上游是拉丁语境的 linter,
     中文行高下限(1.3)与"负字距是拉丁专属"必须由本技能自己守;
  4. **token 名适配**:上游只认 `--accent`,本技能同时认 `--c-accent` 等 `*accent*` 变量。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# ── 规则台账(id → (级别, 一句话)):级别是**唯一真相源**,文件头表格与
#    `--list-rules` 都从这里读。改级别只改这里。 ──
RULE_META = {
    "external-ref": ("P0", "离线铁律 2:HTML 引用 http(s) 资源"),
    "canvas-discipline": ("P0", "铁律 1:position:fixed / 100vh / 100vw(H5 页降 P1)"),
    "ai-default-indigo": ("P0", "默认 LLM 强调色(Tailwind indigo/violet 7 个 hex)"),
    "purple-gradient": ("P0", "紫/蓝紫渐变(大众脸第一名)"),
    "trust-gradient": ("P0", "蓝→青两段式「信任渐变」"),
    "emoji-icon": ("P0", "emoji 当图标(结构语境)"),
    "invented-metric": ("P0", "编造指标(10× faster / 效率提升 N 倍…)"),
    "filler-copy": ("P0", "填充文案(lorem ipsum / 待补充…)"),
    "sans-display": ("P0", "标题硬编码 Inter/Roboto/system-ui 当展示体"),
    "cjk-leading": ("P0", "中文标题行高 < 1.3(强制换行 P0 / 单行 P1)"),
    "left-accent-card": ("P1", "圆角卡 + 左彩边(AI 仪表盘卡)"),
    "all-caps-no-tracking": ("P1", "uppercase 无 ≥0.06em 字距(token 感知)"),
    "raw-hex": ("P1", ":root 外裸 hex > 12 个"),
    "accent-overuse": ("P1", "正文里强调色引用 > 6 次"),
    "cjk-negative-tracking": ("P1", "中文标题负字距(促销风例外)"),
}

# ── 颜色/字符表(与 open-design lint-artifact.ts 同步;改这里要同步 guardrails §5) ──
PURPLE_HEXES = [
    # Tailwind violet / purple
    "#a855f7", "#9333ea", "#7c3aed", "#6d28d9", "#581c87",
    "#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe", "#ede9fe",
    # Tailwind indigo
    "#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#312e81",
    "#818cf8", "#a5b4fc", "#c7d2fe", "#e0e7ff", "#eef2ff",
]
# 单个 hex 就构成"模型默认"的那 7 个(即使不在渐变里)
AI_DEFAULT_INDIGO = ["#6366f1", "#4f46e5", "#4338ca", "#3730a3",
                     "#8b5cf6", "#7c3aed", "#a855f7"]
TRUST_BLUE_HEXES = ["#3b82f6", "#2563eb", "#1d4ed8", "#1e40af", "#1e3a8a",
                    "#60a5fa", "#93c5fd", "#bfdbfe",
                    "#0ea5e9", "#0284c7", "#0369a1", "#38bdf8", "#7dd3fc"]
TRUST_CYAN_HEXES = ["#06b6d4", "#0891b2", "#0e7490", "#155e75", "#164e63",
                    "#22d3ee", "#67e8f9", "#a5f3fc"]
SLOP_EMOJI = ["✨", "🚀", "🎯", "⚡", "🔥", "💡", "📈", "🎨", "🛡️", "🌟",
              "💪", "🎉", "👋", "🙌", "✅", "⭐", "🏆"]

INVENTED_METRIC_PATTERNS = [
    r"\b10×\s+(?:faster|better|easier)\b",
    r"\b100×\s+(?:faster|better)\b",
    r"\b99\.\d+%\s+uptime\b",
    r"\bzero[- ]downtime\b",
    r"\b3×\s+more\s+(?:productive|efficient)\b",
    # 中文口径:与 "不编造数据"(铁律 4)同源。只收**典型的营销空话句式**,
    # 单看数字(如"立省 50%")不判 —— 那可能是用户真实给的促销条款。
    r"效率提升\s*\d+\s*[倍%]",
    r"提升\s*\d+\s*倍(?:效率|性能|速度)",
    r"提升\s*\d+\s*倍",
    r"\d{2,4}%\s*(?:的)?用户(?:都)?(?:选择|满意|推荐)",
    r"零(?:故障|事故|投诉)",
]
FILLER_PATTERNS = [
    r"\bfeature\s+(?:one|two|three|1|2|3)\b",
    r"\blorem\s+ipsum\b",
    r"\bdolor\s+sit\s+amet\b",
    r"\bplaceholder\s+text\b",
    r"\bsample\s+content\b",
    r"待补充|占位文本|示例文本|此处填写|内容待定",
]
# 展示体硬编码无衬线:artboard 的对应规则是"主标必须用字体库的性格款"(guardrails §5.2)
SYSTEM_SANS = r"(?:Inter|Roboto|Arial|-apple-system|system-ui|SF\s*Pro|Helvetica)"
DISPLAY_SEL = r"(?:h1|h2|h3|\.h-?(?:hero|xl|lg|md))"
DISPLAY_SANS_RE = re.compile(
    rf"(?:{DISPLAY_SEL})[^{{}}]*\{{[^}}]*font-family\s*:\s*[\"']?{SYSTEM_SANS}[^}}]*\}}",
    re.I)
HEADING_SEL_RE = re.compile(
    r"(?:^|[\s,>+~])(?:h[1-3]|\.h-?(?:hero|xl|lg|md)|\.(?:title|headline|hero-title|"
    r"poster-title|main-title|display|t)\b)", re.I)

LEFT_ACCENT_RE = re.compile(
    r"\.[a-z-]+\s*\{[^}]*border-left\s*:\s*\d+px\s+solid\s+[^;]+;[^}]*border-radius\s*:\s*[1-9]",
    re.I)
EXTERNAL_ASSET_RE = re.compile(
    r"(?:<(?:img|script|iframe|source|video|audio|link)\b[^>]*\b(?:src|href)\s*=\s*[\"']https?://"
    r"|@import\s+url\(\s*[\"']?https?://"
    r"|url\(\s*[\"']?https?://)",
    re.I)
# SVG 命名空间不是网络请求,必须排除
NS_OK = ("http://www.w3.org/", "https://www.w3.org/")
FIXED_RE = re.compile(r"position\s*:\s*fixed", re.I)
VIEWPORT_RE = re.compile(r"<meta[^>]+name\s*=\s*[\"']viewport", re.I)
VH_VW_RE = re.compile(r"\b100(?:vh|vw|dvh|dvw|svh|svw)\b", re.I)
UPPER_RULE_RE = re.compile(r"([^{}]*)\{([^{}]*text-transform\s*:\s*uppercase[^{}]*)\}", re.I)
INLINE_STYLE_RE = re.compile(r"(?:^|\s)style\s*=\s*([\"'])([\s\S]*?)\1", re.I)
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
ACCENT_VAR_RE = re.compile(r"var\(\s*--[A-Za-z0-9_-]*accent[A-Za-z0-9_-]*\s*[,)]")
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
CJK_FONT_RE = re.compile(
    r"思源|Noto\s+(?:Sans|Serif)\s+SC|PingFang|Hiragino|Microsoft\s+YaHei|微软雅黑|"
    r"SimSun|宋体|SimHei|黑体|霞鹜|LXGW|Source\s+Han|阿里|Alibaba|方正|汉仪|站酷",
    re.I)
TOKEN_SCOPE_RE = re.compile(r"(?::root|html|\[data-theme[^\]]*\])\s*\{[^}]*\}", re.I)
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([\d.]+)\s*(px|em|rem)?", re.I)
LINE_HEIGHT_RE = re.compile(r"line-height\s*:\s*([\d.]+)\s*(px|em|rem|%)?", re.I)
LETTER_SPACING_RE = re.compile(r"letter-spacing\s*:\s*(-?[\d.]+)\s*(em|px|rem|%)?", re.I)
VAR_DEF_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}]+)")

SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2}


# ------------------------------------------------------------------ 小工具

def clip(s: str, n: int = 200) -> str:
    """压平空白并截断(与上游 lint-artifact 的 clip 同口径)。"""
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[: n - 3] + "…" if len(s) > n else s


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_ignores(raw: str) -> tuple[set, str]:
    """取 `<!-- slop-ignore: id[,id] -->`,返回 (豁免 id 集, 去掉注释的正文)。

    `all` 表示整文件豁免。注释必须在校验**之前**剥掉:注释里的教学示例
    (如"别写 linear-gradient(...purple...)")会触发假阳性 —— 上游同款技巧。
    """
    ids: set = set()
    for m in re.finditer(r"<!--\s*slop-ignore\s*:\s*([^>]*?)-->", raw, re.I):
        for tok in re.split(r"[,\s]+", m.group(1).strip()):
            if tok:
                ids.add(tok.lower())
    if "all" in ids:
        ids.add("*")
    body = re.sub(r"<!--[\s\S]*?-->", "", raw)
    return ids, body


def strip_css_comments(css: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def strip_token_blocks(html: str) -> str:
    """剥掉全局主题作用域的 token 定义块。

    品牌色**有意**是 indigo 时,设计系统会写 `--accent: #6366f1` 再全程 var() ——
    那是设计决策;只有裸写在组件里的 indigo 才叫"模型默认"。组件局部变量
    (`.cta { --cta-bg: #6366f1; }`)不在此列,仍会被抓。
    """
    return TOKEN_SCOPE_RE.sub("", html)


def style_blocks(html: str) -> list[str]:
    return [strip_css_comments(m) for m in
            re.findall(r"<style[^>]*>([\s\S]*?)</style>", html, re.I)]


def resolve_source(source: str) -> tuple[str, str, list[str]]:
    """返回 (kind, path, html 文件名列表);kind ∈ dir/file/missing。"""
    p = os.path.abspath(source)
    if os.path.isdir(p):
        src = os.path.join(p, "src")
        base = src if os.path.isdir(src) else p
        names = sorted(n for n in os.listdir(base) if n.lower().endswith((".html", ".htm")))
        return ("dir", base, names) if names else ("missing", p, [])
    if os.path.isfile(p) and p.lower().endswith((".html", ".htm")):
        return "file", p, [p]
    return "missing", p, []


# ------------------------------------------------------------------ 规则实现

def rule_external_ref(html: str) -> list[dict]:
    out = []
    for m in EXTERNAL_ASSET_RE.finditer(html):
        if any(ns in m.group(0) for ns in NS_OK):
            continue
        out.append(sev("P0", "external-ref",
                       "HTML 引用了 http(s) 资源 —— 违反铁律 2(离线渲染)。",
                       "把该资源复制进项目 `src/vendor/`(字体 → `src/fonts/`),"
                       "或换成 assets/ 里的本地文件。渲染导出在离线环境下会直接缺资源。",
                       m.group(0)))
        break
    return out


def rule_canvas(html: str) -> list[dict]:
    """铁律 1:固定画布。H5 页(有 viewport meta)自动降 P1 —— 模式 H 允许滚动。

    扫**整个 html** 而不只是 <style>:行内 `style="position:fixed"` 同样是
    违反铁律 1。正则要求 `position:` / 数值单位前缀,正文散文撞不上。
    """
    m = FIXED_RE.search(html) or VH_VW_RE.search(html)
    if not m:
        return []
    h5 = bool(VIEWPORT_RE.search(html))
    lvl = "P1" if h5 else "P0"
    extra = ("(检测到 viewport meta,按模式 H 降级:P1)" if h5 else "")
    return [sev(lvl, "canvas-discipline",
                f"出现 `{m.group(0)}` —— 静态海报/视频卡违反铁律 1(固定画布){extra}。",
                "画布用 `.poster` 的固定像素尺寸代替;确需 100vh 的 H5 页面走模式 H"
                "(`check_h5.py`),并给本文件加 `<!-- slop-ignore: canvas-discipline -->`。",
                m.group(0), force=True)]


def rule_indigo(html: str) -> list[dict]:
    body = strip_token_blocks(html)
    for hexv in AI_DEFAULT_INDIGO:
        m = re.search(re.escape(hexv), body, re.I)
        if m:
            return [sev("P0", "ai-default-indigo",
                        f"用了默认 LLM 强调色 {hexv} —— 最常被点名的 AI 设计特征。",
                        "换成本项目的强调色 token(artboard 口径 `var(--c-accent)` /"
                        " `var(--accent)`);确要 indigo 就把它写进 `:root` 的 token,"
                        "让它是「设计决策」而不是「模型默认」。",
                        m.group(0))]
    return []


def rule_purple_gradient(html: str) -> list[dict]:
    for hexv in PURPLE_HEXES:
        m = re.search(r"linear-gradient\([^)]*" + re.escape(hexv) + r"[^)]*\)", html, re.I)
        if m:
            return [sev("P0", "purple-gradient",
                        f"紫/蓝紫渐变用了 {hexv} —— 大众脸第一名。",
                        "改成平面底色(`var(--c-bg)` / `var(--c-surface)`)或单一强调色一块;"
                        "需要层次就用留白与字号对比,不要渐变。", m.group(0))]
    m = re.search(r"linear-gradient\([^)]*\b(?:purple|violet|indigo)\b[^)]*\)", html, re.I)
    if m:
        return [sev("P0", "purple-gradient", "渐变里出现 purple/violet/indigo 关键词。",
                    "同紫蓝渐变:换平面底色或单一 token 色。", m.group(0))]
    return []


def rule_trust_gradient(html: str) -> list[dict]:
    for gm in re.finditer(r"linear-gradient\([^)]*\)", html, re.I):
        g = gm.group(0)
        blue = any(h in g.lower() for h in TRUST_BLUE_HEXES) or re.search(r"\bblue\b", g, re.I)
        cyan = any(h in g.lower() for h in TRUST_CYAN_HEXES) or re.search(r"\bcyan\b", g, re.I)
        if blue and cyan:
            return [sev("P0", "trust-gradient",
                        "蓝→青两段式「信任渐变」—— SaaS hero 陈词。",
                        "换平面底(或单一强调色);两段渐变本身不是错,"
                        "错在它是模板默认。", g)]
    return []


def rule_emoji(html: str) -> list[dict]:
    for e in SLOP_EMOJI:
        if e not in html:
            continue
        m = re.search(r"<(?:h[1-6]|button|li|span\s+class\s*=\s*[\"'][^\"']*icon[^\"']*)[^>]*>[^<]*"
                      + re.escape(e), html, re.I)
        if m:
            return [sev("P0", "emoji-icon",
                        f"emoji {e} 当图标用 —— 结构语境(标题/按钮/列表/icon 元素)里出现。",
                        "换成 `assets/icons/` 的内联 Tabler SVG(1.5–1.75px 描边、"
                        "`currentColor`),或干脆去掉图标。正文散文里的 emoji 不算违规。",
                        m.group(0))]
    return []


def rule_invented_metric(html: str) -> list[dict]:
    for pat in INVENTED_METRIC_PATTERNS:
        m = re.search(pat, html, re.I)
        if m:
            return [sev("P0", "invented-metric",
                        f"疑似编造指标:「{m.group(0)}」—— 铁律 4:文案逐字来自用户。",
                        "删掉该说法,或换成占位(`——`)等用户给真实数字;"
                        "用户已给的真实数据不受此限(必要时用 slop-ignore 说明)。",
                        m.group(0))]
    return []


def rule_filler(html: str) -> list[dict]:
    for pat in FILLER_PATTERNS:
        m = re.search(pat, html, re.I)
        if m:
            return [sev("P0", "filler-copy",
                        f"填充文案:「{m.group(0)}」—— 空版面是设计问题,不是文案问题。",
                        "换成来自用户简报的真实文案;没文案就把这一块去掉,"
                        "用构图(留白/放大主标)填满版面。", m.group(0))]
    return []


def rule_sans_display(html: str) -> list[dict]:
    m = DISPLAY_SANS_RE.search(html)
    if not m:
        return []
    return [sev("P0", "sans-display",
                "标题规则把展示体硬编码成 Inter/Roboto/system-ui —— 一眼模板。",
                "标题走字体库的性格款:`font-family: var(--font-display)`"
                "(或项目 `:root` 里声明的标题字体栈);只有「科技实用/现代极简」方向"
                "才允许系统无衬线,且要写进风格分册。", m.group(0))]


def rule_left_accent(html: str) -> list[dict]:
    m = LEFT_ACCENT_RE.search(html)
    if not m:
        return []
    # 与上游不同:artboard 的引用卡/要点卡**允许**左彩边(许多风格分册就这么写),
    # 所以这里定 P1(建议)而非 P0(阻断)——升级口径见本文件头「与上游的差异」。
    return [sev("P1", "left-accent-card",
                "圆角 + 左彩边卡片 —— AI 仪表盘卡经典形。",
                "二选一:去掉圆角(`border-radius: 0`),或去掉左彩边改成四周细描边。"
                "若这是风格的既定语言(引用卡),确认后加 slop-ignore。", m.group(0))]


def _resolve_var(decl_value: str, tokens: dict) -> str:
    """把 `var(--x)` 解成字面值(最多 4 层,与上游 VAR_RESOLVE_MAX_DEPTH 一致)。"""
    val = decl_value
    for _ in range(4):
        m = re.search(r"var\(\s*(--[A-Za-z0-9_-]+)", val)
        if not m or m.group(1) not in tokens:
            break
        val = val.replace(m.group(0), tokens[m.group(1)])
    return val


def collect_tokens(css_all: str) -> dict:
    tokens = {}
    for blk in TOKEN_SCOPE_RE.findall(css_all):
        for name, val in VAR_DEF_RE.findall(blk):
            tokens[name] = val.strip()
    return tokens


def _tracking_ok(body: str, tokens: dict) -> bool:
    """uppercase 规则的字距是否 ≥0.06em(支持 token 与 px 换算)。"""
    m = LETTER_SPACING_RE.search(body)
    if not m:
        return False
    raw = m.group(0)
    if "var(" in raw:
        raw = _resolve_var(raw, tokens)
        m2 = LETTER_SPACING_RE.search(raw)
        if not m2:
            return False
        num, unit = float(m2.group(1)), (m2.group(2) or "em").lower()
    else:
        num, unit = float(m.group(1)), (m.group(2) or "em").lower()
    if unit == "px":
        fs = FONT_SIZE_RE.search(body)
        px = float(fs.group(1)) if fs else 16.0        # 无字号时按 16px 基准
        num = num / px
    elif unit == "%":
        num = num / 100.0
    return num >= 0.06


def rule_all_caps(html: str, css_all: str, tokens: dict) -> list[dict]:
    for css in style_blocks(html):
        for m in UPPER_RULE_RE.finditer(css):
            selector, body = (m.group(1) or "").strip(), (m.group(2) or "")
            if not _tracking_ok(body, tokens):
                return [sev("P1", "all-caps-no-tracking",
                            f"`{clip(selector, 60)}` 用了 uppercase 但字距 <0.06em。",
                            "同一条规则里加 `letter-spacing: 0.08em`(典型值);"
                            "大写字母不加字距会挤成一团 —— 这是业余感头号来源。",
                            f"{selector} {{ {body.strip()} }}")]
    for im in INLINE_STYLE_RE.finditer(html):
        decl = im.group(2) or ""
        if re.search(r"text-transform\s*:\s*uppercase", decl, re.I) and not _tracking_ok(decl, tokens):
            return [sev("P1", "all-caps-no-tracking",
                        "行内样式用了 uppercase 但字距 <0.06em。",
                        "行内加 `letter-spacing:0.08em`,或提成 class 统一管。", decl.strip())]
    return []


def rule_raw_hex(html: str) -> list[dict]:
    # 所有 <style> 块一起数 —— 只看第一块的话,拆成多段样式的页会漏掉后半截
    css = TOKEN_SCOPE_RE.sub("", "\n".join(style_blocks(html)))
    hexes = HEX_RE.findall(css)
    if len(hexes) > 12:
        return [sev("P1", "raw-hex",
                    f":root 之外有 {len(hexes)} 个裸 hex —— token 大概没被遵守。",
                    "把颜色收进 `:root`(`--c-ink/--c-bg/--c-primary/--c-accent/"
                    "--c-muted`),用 `var()` 引用;派生色用 `color-mix()`。",
                    " ".join(hexes[:6]))]
    return []


def rule_accent_overuse(html: str) -> list[dict]:
    body = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.I)
    n = len(ACCENT_VAR_RE.findall(body))
    if n > 6:
        return [sev("P1", "accent-overuse",
                    f"正文里强调色被引用了 {n} 次 —— 每屏可见 ≤2 处。",
                    "只给最先该看的 1–2 个元素上强调色,其余降到 `var(--c-ink)` /"
                    " `var(--c-muted)`。到处强调 = 没有强调。", f"{n} 处")]
    return []


def _px_font_size(body: str) -> float | None:
    m = FONT_SIZE_RE.search(body)
    if not m:
        return None
    num, unit = float(m.group(1)), (m.group(2) or "px").lower()
    if unit == "em":
        return num * 16.0
    if unit == "rem":
        return num * 16.0
    return num


def _cjk_context(html: str, selector: str) -> tuple[bool, bool]:
    """该规则的**实际承载文本**返回 (是否含中文, 是否强制换行 `<br>`)。

    宁可漏报:判不出的按"非中文"处理,不拿整个页面有没有中文来一刀切。
    伪元素规则(`::first-letter` 这类)不参与 —— 首字下沉的紧行高是合法排版手法。
    """
    if "::" in selector:
        return False, False
    if CJK_FONT_RE.search(selector):
        return True, False
    found_cjk = br = False

    def scan(chunk: str) -> None:
        nonlocal found_cjk, br
        text = re.split(r"</", chunk)[0]           # 元素内文本(嵌套闭合前)
        if CJK_RE.search(re.sub(r"<[^>]+>", "", text)):
            found_cjk = True
        if re.search(r"<br\s*/?>", text, re.I):
            br = True

    for tok in re.findall(r"\.([A-Za-z0-9_-]+)", selector)[:6]:
        pat = r'class\s*=\s*"[^"]*\b' + re.escape(tok) + r'\b[^"]*"[^>]*>([\s\S]{1,300})'
        for m in re.finditer(pat, html, re.I):
            scan(m.group(1) or "")
    for tag in re.findall(r"(?<![\w.#-])(h[1-6])", selector, re.I)[:3]:
        for m in re.finditer(rf"<{tag}\b[^>]*>([\s\S]{{1,300}})", html, re.I):
            scan(m.group(1) or "")
    return found_cjk, br


def rule_cjk_leading(html: str) -> list[dict]:
    """中文标题行高下限 1.3(来源:open-design craft/typography.md)。

    CJK 字形撑满 em 框,拉丁能用的 1.0–1.2 会让两行中文肉眼相撞。分级:
      - 元素**强制换行**(内含 `<br>`,作者已经决定排两行)→ P0(一定会撞);
      - 单行中文标题 → P1(文案一改就可能变两行,建议留 1.3 余量)。
    只报"字号 ≥32px + 显式行高 <1.3 + 确实承载中文"的规则;拉丁元素不受限。"""
    for css in style_blocks(html):
        for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
            selector, body = (m.group(1) or "").strip(), (m.group(2) or "")
            if selector.startswith("@") or not selector:
                continue
            fs = _px_font_size(body)
            lh = LINE_HEIGHT_RE.search(body)
            if fs is None or lh is None or fs < 32:
                continue
            num, unit = float(lh.group(1)), (lh.group(2) or "").lower()
            # % 要除 100;px 直接用;无单位 / em / rem 都按倍数算
            # (rem 严格说挂在根字号上,海报里几乎不这么写行高,按倍数是安全近似)
            px = {"px": num, "%": num / 100.0 * fs}.get(unit, num * fs)
            ratio = px / fs
            if ratio >= 1.3:
                continue
            has_cjk, forced_br = _cjk_context(html, selector)
            if not has_cjk:
                continue
            level = "P0" if forced_br else "P1"
            msg = (f"`{clip(selector, 50)}` 字号 {fs:.0f}px 却给了行高 {ratio:.2f}"
                   + (";而且已用 `<br>` 强制排成两行 —— 两行中文会叠在一起。"
                      if forced_br else "(单行暂时安全,但文案一改就可能撞行)。"))
            return [sev(level, "cjk-leading", msg,
                        "把该规则 `line-height` 提到 1.3–1.4;纯拉丁元素才可以用 1.0–1.2。"
                        "中英混排时把紧行高只给拉丁那层,别让中文继承父级紧行高。",
                        f"{selector} {{ {body.strip()} }}", force=True)]
    return []


def rule_cjk_negative_tracking(html: str) -> list[dict]:
    for css in style_blocks(html):
        for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
            selector, body = (m.group(1) or "").strip(), (m.group(2) or "")
            ls = LETTER_SPACING_RE.search(body)
            if not ls or selector.startswith("@") or not selector:
                continue
            num = float(ls.group(1))
            if num >= 0:
                continue
            fs = _px_font_size(body)
            if fs is None or fs < 32:
                continue
            if not _cjk_context(html, selector)[0]:
                continue
            return [sev("P1", "cjk-negative-tracking",
                        f"`{clip(selector, 50)}` 给中文标题加了负字距 {num}em。",
                        "中文在固定 em 网格上,负字距是挤压字形而非收紧字距 —— 改 0;"
                        "锐利促销风确要负字距时,加 slop-ignore 并说明风格依据。",
                        f"{selector} {{ {body.strip()} }}")]
    return []


RULES = {
    "external-ref": rule_external_ref,
    "canvas-discipline": rule_canvas,
    "ai-default-indigo": rule_indigo,
    "purple-gradient": rule_purple_gradient,
    "trust-gradient": rule_trust_gradient,
    "emoji-icon": rule_emoji,
    "invented-metric": rule_invented_metric,
    "filler-copy": rule_filler,
    "sans-display": rule_sans_display,
    "left-accent-card": rule_left_accent,
    "all-caps-no-tracking": rule_all_caps,
    "raw-hex": rule_raw_hex,
    "accent-overuse": rule_accent_overuse,
    "cjk-leading": rule_cjk_leading,
    "cjk-negative-tracking": rule_cjk_negative_tracking,
}

# 绝大多数规则只吃 html;唯一需要跨 <style> 汇总上下文的是 all-caps
# (要 :root 的 token 表来换算 letter-spacing)。
def _call(fn, html: str, css_all: str, tokens: dict) -> list:
    if fn is rule_all_caps:
        return fn(html, css_all, tokens)
    return fn(html)


def sev(level: str, rid: str, message: str, fix: str, snippet: str = "",
        force: bool = False) -> dict:
    """级别一律取 RULE_META(台账是唯一真相源),`force=True` 只给动态降级的规则用。"""
    lv = level if force else RULE_META[rid][0]
    return {"severity": lv, "id": rid, "message": message,
            "fix": fix, "snippet": clip(snippet)}


def lint_page(html_raw: str, file: str, only: set) -> list[dict]:
    ignores, html = parse_ignores(html_raw)
    if "*" in ignores:
        return []
    css_all = "\n".join(style_blocks(html))
    tokens = collect_tokens(css_all)
    out: list[dict] = []
    crashed: list[str] = []
    for rid, fn in RULES.items():
        if rid in ignores:
            continue      # 注意:only 是**级别**(P0/P1/P2),不是规则 id,故此层不过滤
        try:
            found = _call(fn, html, css_all, tokens)
        except Exception as exc:  # noqa: BLE001 — 单条规则出错不该让整页检查失败,
            # 但**必须留痕**:静默 continue 会让规则悄悄失效(签名一改就中招),
            # 门禁看上去"通过"实则没跑,那比误报危险得多。
            crashed.append(f"{rid}({type(exc).__name__}: {exc})")
            continue
        for f in found:
            if only and "P" in f["severity"] and f["severity"] not in only:
                continue
            f["file"] = file
            out.append(f)
    for c in crashed:                      # 规则崩了要在报告里看得见
        out.append({"severity": "P2", "id": "rule-crashed", "message": c,
                    "fix": "这是本脚本自身的 bug(规则实现与签名不符等),"
                           "请修脚本而不是加豁免;该规则本轮**没有运行**。",
                    "snippet": "", "file": file})
    return out


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def list_rules() -> None:
    emit({"ok": True, "cmd": "check_slop --list-rules",
          "rules": [{"id": rid, "severity": lv, "what": desc}
                    for rid, (lv, desc) in RULE_META.items()],
          "counts": {lv: sum(1 for v in RULE_META.values() if v[0] == lv)
                     for lv in ("P0", "P1", "P2")}})


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    p = argparse.ArgumentParser(
        description="artboard AI 味与铁律机检(静态,零渲染)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="规则明细见 references/guardrails.md §5 与 references/cjk-typography-css.md")
    p.add_argument("source", nargs="?", default="", help="项目目录 / src 目录 / HTML 文件")
    p.add_argument("--strict", action="store_true", help="P1 也算阻断(默认只有 P0 阻断)")
    p.add_argument("--only", default="", help="只看某级别,逗号分隔:P0,P1,P2")
    p.add_argument("--list-rules", action="store_true", help="列出全部规则与级别后退出")
    args = p.parse_args()

    if args.list_rules:
        list_rules()
        return 0
    if not args.source:
        emit({"ok": False, "error": "USAGE",
              "hint": "用法:python check_slop.py <项目目录|src目录|HTML文件>"
                      "(参数明细见 --help)"})
        return 2

    only = {s.strip().upper() for s in args.only.split(",") if s.strip()}
    bad_sev = [s for s in only if s not in SEV_ORDER]
    if bad_sev:
        emit({"ok": False, "error": "BAD_SEVERITY", "detail": sorted(bad_sev),
              "hint": "--only 只接受 P0,P1,P2"})
        return 2

    kind, path, names = resolve_source(args.source)
    if kind == "missing":
        emit({"ok": False, "error": "NO_HTML", "detail": path,
              "hint": "传项目目录(内含 src/*.html)、src 目录或单个 HTML 文件"})
        return 2

    findings: list[dict] = []
    files: list[dict] = []
    # --strict 下 P1 也阻断,单页 ok 必须跟着变,否则 files[] 与 blocking 自相矛盾
    gate = {"P0", "P1"} if args.strict else {"P0"}
    for name in names:
        full = name if kind == "file" else os.path.join(path, name)
        rel = os.path.basename(full) if kind == "dir" else full
        got = lint_page(read_text(full), rel, only)
        findings.extend(got)
        files.append({"file": rel,
                      "ok": not any(f["severity"] in gate for f in got),
                      "count": len(got)})

    findings.sort(key=lambda f: (SEV_ORDER.get(f["severity"], 9), f["file"], f["id"]))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEV_ORDER}
    blocking = sum(counts[s] for s in gate)
    emit({"ok": blocking == 0, "source": path, "strict": args.strict,
          "files": files, "count": len(findings), "counts": counts,
          "blocking": blocking, "findings": findings})

    if findings:
        print(f"\nAI 味/铁律机检:{len(findings)} 条"
              f"(P0 {counts['P0']} · P1 {counts['P1']} · P2 {counts['P2']})", file=sys.stderr)
        multi = len(files) > 1
        for f in findings[:25]:
            where = f"[{f['file']}] " if multi else ""
            print(f"  {'✗' if f['severity'] == 'P0' else '△'} [{f['severity']} {f['id']}]"
                  f" {where}{f['message']}", file=sys.stderr)
            print(f"      修:{f['fix']}", file=sys.stderr)
        if len(findings) > 25:
            print(f"  … 其余 {len(findings) - 25} 条见 JSON", file=sys.stderr)
        print("\n  规则与判据见 references/guardrails.md §5(去 AI 味)与"
              "\n    references/cjk-typography-css.md(中文行高/字距);"
              "\n    确实要保留的例外:<!-- slop-ignore: 规则id --> 并在交付报告里说明理由",
              file=sys.stderr)
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
