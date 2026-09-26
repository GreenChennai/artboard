"""公众号统一主题真相源(图文 gzh_article + 双封面 gzh_cover 共用;11 迭代 D-11-2)。

为什么存在:此前封面与图文各有 THEME 表,**名字不同、色板结构不同**,
`green` 甚至"同名不同色"——"图文带同风格封面"在旧状态下做不到。
本模块是唯一色源:一处改色,两个产物同时变;**任何一方不得自带私有色值**。

角色总表(两边各自取用):
  bg/bg2     封面底 / 渐变第二色      图文:强调底(引用块)
  surface    封面卡片面               图文:代码块底
  ink/text   封面主文字               图文:正文色
  muted      封面次要文字             图文:次要/图注
  primary    封面主强调(线条/编号)   图文:主色(标题/链接/引用竖线)
  accent     封面强调(≤1 处)        图文:强调(≤1 处)
  border     封面分隔线               图文:表格/分割线
  soft       封面浅底块               图文:引用块底
  quote      —                        图文:引文文字
  muted_css/line_css  封面专用 rgba 形态(保留旧观感)

旧名别名(D-11-8):blue→ink / dark→night / default→ink / orange→warm / green→grass;
使用旧名**打印一次性弃用提示**(green 必须明示"色值已统一")。
"""

from __future__ import annotations

import sys

# 6 套统一主题 × 全量角色(值全部 hex;封面专用 rgba 由 cover_themes 派生)
THEMES: dict[str, dict[str, str]] = {
    "ink":   {"bg": "#0f1b3d", "bg2": "#1b2f66", "surface": "#141f47",
              "ink": "#f5f7ff", "text": "#e8ecf8", "muted": "#a9b3cf",
              "primary": "#3b82f6", "accent": "#3b82f6",
              "border": "#2a3a6b", "soft": "#16224d", "quote": "#9fb0d8"},
    "night": {"bg": "#16130f", "bg2": "#2c2620", "surface": "#201b15",
              "ink": "#faf7f2", "text": "#f2ede4", "muted": "#b3a892",
              "primary": "#e8b04b", "accent": "#e8b04b",
              "border": "#3a332a", "soft": "#241f18", "quote": "#cbb98a"},
    "warm":  {"bg": "#fdf3e7", "bg2": "#f6e3cd", "surface": "#fff9f0",
              "ink": "#3a2c1e", "text": "#4a3b2c", "muted": "#96897f",
              "primary": "#d47435", "accent": "#c96f2e",
              "border": "#ecdcd0", "soft": "#faf5ef", "quote": "#75655a"},
    "grass": {"bg": "#12291c", "bg2": "#1d4029", "surface": "#163322",
              "ink": "#f0f7f1", "text": "#dfeee2", "muted": "#8a938c",
              "primary": "#1a7a4f", "accent": "#4ade80",
              "border": "#dfe8e2", "soft": "#f3f8f5", "quote": "#5a6b60"},
    "red":   {"bg": "#2b1210", "bg2": "#451b16", "surface": "#331713",
              "ink": "#fbf1ef", "text": "#f0e2df", "muted": "#928a88",
              "primary": "#c0392b", "accent": "#e05a4a",
              "border": "#ecd6d3", "soft": "#faf3f2", "quote": "#6e605d"},
    "mono":  {"bg": "#111111", "bg2": "#232323", "surface": "#1a1a1a",
              "ink": "#f7f7f5", "text": "#eeeeec", "muted": "#999995",
              "primary": "#444444", "accent": "#777774",
              "border": "#e5e5e5", "soft": "#f7f7f7", "quote": "#666666"},
}

# 旧名 → 新名(使用即弃用提示;green 高危:同名不同色已统一)
ALIASES: dict[str, str] = {
    "blue": "ink",      # 封面旧名
    "dark": "night",    # 封面旧名
    "default": "ink",   # 图文旧名
    "orange": "warm",   # 图文旧名
    "green": "grass",   # 双方旧名,同名不同色 → 已统一
}

# 深底主题(封面 muted/line 用浅色 rgba;暖米等浅底用深色 rgba)
_LIGHT_BG = {"warm"}


def resolve(name: str, where: str = "") -> tuple[str, dict[str, str], bool]:
    """主题名解析(含别名)→ (规范名, 全量角色, 是否弃用名)。未知名抛 KeyError。"""
    canonical = name
    aliased = False
    if name in ALIASES:
        canonical = ALIASES[name]
        aliased = True
        note = ("色值已统一到全局主题源,与旧 green 不同" if name == "green"
                else f"请改用 {canonical}")
        print(f"△ 主题名「{name}」已弃用 → 改用「{canonical}」({note})。"
              f"本提示只提醒,不影响出图。", file=sys.stderr)
    t = THEMES[canonical]
    return canonical, t, aliased


def cover_roles(name: str) -> dict[str, str]:
    """封面用角色子集(bg/bg2/ink/accent/muted/line;键名与旧封面 THEMES 完全一致,
    观感兼容;line 另保留 line_css 别名无需——模板只认 muted/line)。"""
    canonical, t, _ = resolve(name)
    if canonical in _LIGHT_BG:
        return {"bg": t["bg"], "bg2": t["bg2"], "ink": t["ink"],
                "accent": t["accent"],
                "muted": "rgba(58,44,30,.62)", "line": "rgba(58,44,30,.16)"}
    return {"bg": t["bg"], "bg2": t["bg2"], "ink": t["ink"], "accent": t["accent"],
            "muted": "rgba(245,247,255,.72)", "line": "rgba(255,255,255,.18)"}


def article_roles(name: str) -> dict[str, str]:
    """图文用角色子集(primary/text/muted/soft/border/quote)。"""
    _, t, _ = resolve(name)
    return {"primary": t["primary"], "text": t["text"], "muted": t["muted"],
            "soft": t["soft"], "border": t["border"], "quote_text": t["quote"]}


def cover_themes() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """全部封面主题(供 gzh_cover 的 THEMES 惯用法)+ 别名表。"""
    themes = {name: cover_roles(name) for name in THEMES}
    return themes, dict(ALIASES)


def article_themes() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """全部图文主题(供 gzh_article 的 THEMES 惯用法)+ 别名表。"""
    themes = {name: article_roles(name) for name in THEMES}
    return themes, dict(ALIASES)
