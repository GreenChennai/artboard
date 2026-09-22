#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_wechat_svg.py — 微信公众号图文/内联 SVG 动效机检(零 token)

用途: 交付公众号 HTML 之前跑一次。白名单/禁用标签/id/被剥离 CSS/标签配平/静态降级陷阱。
      属于 artboard 的「机检门禁」家族, 与 check_overflow.py 并列:
      check_overflow.py 管「文字越框」, 本脚本管「微信会不会把动画/样式灭掉」。

用法:
    python check_wechat_svg.py <文件或目录> [...] [--json] [--quiet]
    python check_wechat_svg.py 粘贴版-*.html
    python check_wechat_svg.py "D:/.../2026-09-22"          # 目录则递归找 *.html

退出码: 0 = 通过(可交付) ; 1 = 存在 FATAL(禁止交付)

依据: 微信 SVG AttributeName 白名单(2016 微信团队 & JZ Creative; T/CASME 1609—2024)
"""
import argparse
import glob
import json
import os
import re
import sys

# ---- 微信白名单 ----
ALLOW_ANIM_ATTR = {"x", "y", "width", "height", "cx", "cy", "opacity", "d", "points",
                   "stroke-width", "stroke-linecap", "stroke-dashoffset", "fill"}
ALLOW_SET_ATTR = {"visibility"}
ALLOW_TF_TYPE = {"translate", "scale", "rotate", "skewX", "skewY"}
ALLOW_MOTION = {"path", "rotate", "keypoints"}
BAN_TAGS = ["filter", "clipPath", "mask", "linearGradient", "radialGradient", "pattern",
            "use", "symbol", "marker", "foreignObject", "script"]
STRIP_TAGS = ["style"]
# 会被微信剥离的 CSS 语法
BAN_CSS = [r"@keyframes", r"@media", r"@import", r"@font-face", r"animation\s*:",
           r"transition\s*:"]
BALANCE_TAGS = ["svg", "g", "section", "p", "table", "tr", "td", "text", "strong", "span",
                "div", "a", "ul", "ol", "li"]


def collect(paths, exclude=()):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, "**", "*.html"), recursive=True))
        else:
            out += sorted(glob.glob(p))
    out = [f for f in dict.fromkeys(out) if os.path.isfile(f)]
    for pat in exclude:
        out = [f for f in out if pat not in os.path.basename(f)
               and pat not in f.replace("\\", "/")]
    return out


def slice_article_root(raw):
    """从整页文档里切出「会被粘贴进公众号」的那一段。

    公众号图文常被包在一层本地预览壳里(<!DOCTYPE html> + 页级 <style>/<script> 切换品牌)。
    壳里的 <style>/<script>/id 并不会跟着粘进编辑器, 所以默认只检正文根节点。
    正文根 = 含 max-width:677px 的最外层 <section> (公众号正文标准宽度)。
    返回 (待检文本, 壳是否被剔除)
    """
    hits = list(re.finditer(r"max-width\s*:\s*677px", raw))
    if not hits:
        return raw, False
    # 一稿多版时正文根有多处(预览器里安信德/创客龙各一份) → 取最后一处
    start = raw.rfind("<section", 0, hits[-1].start())
    if start < 0:
        return raw, False
    # 从 start 起按 <section> 嵌套深度找匹配的收尾
    # (不能用 rfind("</section>") —— 外面还套着本地预览壳的包裹 <section>)
    depth = 0
    for m in re.finditer(r"<section\b|</section\s*>", raw[start:]):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return raw[start:start + m.end()], True
        else:
            depth += 1
    return raw[start:], True


def check_file(fp, strict=False):
    fatal, warn, info = [], [], {}
    name = os.path.basename(fp)
    raw = open(fp, encoding="utf-8", errors="replace").read()
    body, has_shell = (raw, False) if strict else slice_article_root(raw)
    info["预览壳已剔除"] = has_shell
    # 抹掉 base64 再检(否则正则会在几 MB 的串上白跑)
    stripped = re.sub(r'data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+', "B64", body)
    page_style = len(re.findall(r"<style\b", stripped, re.I))
    s = re.sub(r"<style\b.*?</style>", "", stripped, flags=re.S | re.I)
    if page_style:
        warn.append(f"{name}: 正文根节点内仍有 <style> ×{page_style}（会被微信剥离）")

    def add(lst, msg):
        lst.append(f"{name}: {msg}")

    # 1) 动画目标属性白名单
    for m in sorted(set(re.findall(r'<animate\b[^>]*?\battributeName="([^"]+)"', s))):
        if m not in ALLOW_ANIM_ATTR:
            add(fatal, f'<animate attributeName="{m}"> 不在白名单')
    for m in sorted(set(re.findall(r'<set\b[^>]*?\battributeName="([^"]+)"', s))):
        if m not in ALLOW_SET_ATTR:
            add(fatal, f'<set attributeName="{m}"> 只允许 visibility')
    for m in sorted(set(re.findall(r'<animateTransform\b[^>]*?\btype="([^"]+)"', s))):
        if m not in ALLOW_TF_TYPE:
            add(fatal, f'<animateTransform type="{m}"> 不在白名单')
    for m in sorted(set(re.findall(r'<animateMotion\b[^>]*?\battributeName="([^"]+)"', s))):
        if m not in ALLOW_MOTION:
            add(fatal, f'<animateMotion attributeName="{m}"> 不在白名单')

    # 2) 禁用标签 / 会被剥离的标签
    for t in BAN_TAGS:
        n = len(re.findall(rf"<{t}[\s>/]", s, re.I))
        if n:
            add(fatal, f"含禁用标签 <{t}> ×{n}（微信会消除/依赖 id）")
    for t in STRIP_TAGS:
        n = len(re.findall(rf"<{t}[\s>/]", s, re.I))
        if n:
            add(fatal, f"含会被剥离的 <{t}> ×{n}（页面级 <style> 仅预览壳可用）")

    # 3) id / url(#..)
    ids = len(re.findall(r"\sid\s*=", s))
    if ids:
        add(fatal, f"含 id 属性 ×{ids}（微信会过滤所有 id）")
    if re.search(r"url\(#", s):
        add(fatal, "含 url(#…) 引用（id 被过滤后必失效）")

    # 4) animateTransform 直接压在有静态 transform 的元素上 → 覆盖定位, 元素跳到原点
    bad = re.findall(r'<(\w+)([^>]*?\btransform="[^"]*"[^>]*?)>\s*<animateTransform', s)
    if bad:
        add(fatal, f"{len(bad)} 处 <animateTransform> 直接写在带静态 transform 的元素上"
                   "（会覆盖定位 → 元素被移到原点；应嵌一层只做静态定位的外层 <g>）")

    # 5) 会被剥离的 CSS
    for pat in BAN_CSS:
        n = len(re.findall(pat, s, re.I))
        if n:
            add(fatal, f"含会被剥离的 CSS `{pat}` ×{n}")

    # 6) 标签配平
    for tag in BALANCE_TAGS:
        o = len(re.findall(rf"<{tag}[\s>]", s))
        c = len(re.findall(rf"</{tag}>", s))
        if o != c:
            add(fatal, f"<{tag}> 不配平 open={o} close={c}")

    # 7) span leaf 兼容层配平
    lo = len(re.findall(r'<span leaf="">', s))
    lc = len(re.findall(r"</span>", s))
    if lo > lc:
        add(fatal, f"span leaf 数({lo}) > </span> 数({lc})（秀米系编辑器会样式漂移）")

    # 8) keyTimes 合法性
    for m in re.findall(r'keyTimes="([^"]+)"', s):
        try:
            vals = [float(x) for x in m.split(";")]
            if vals != sorted(vals) or vals[0] < 0 or vals[-1] > 1:
                add(fatal, f"keyTimes 非法: {m}")
        except ValueError:
            add(fatal, f"keyTimes 无法解析: {m}")

    # 9) WARN: svg 缺 viewBox(不同宽度下会错位)
    for m in re.findall(r"<svg\b([^>]*)>", s):
        if "viewBox" not in m:
            add(warn, "有 <svg> 缺 viewBox（容器宽度变化时会错位）")
            break

    # 10) WARN: 中文裸放在 <p> 里(漏 span leaf)
    for m in re.findall(r"<p\b[^>]*>([^<]{1,40}[\u4e00-\u9fff][^<]*)</p>", s):
        if m.strip():
            add(warn, f"<p> 内有裸中文未包 span leaf: {m.strip()[:24]}…")
            break

    # 11) WARN: 正文段落(<p> 且文字够长)用了衬线字体
    #     规则: 正文强制无衬线; 标题/诗词/卡片标题等「特殊文字」不受限,
    #     所以只对长段落报警(阈值 40 个汉字), 短句(诗词/标签)放行。
    SERIF_TOKENS = ("Songti", "STSong", "SimSun", "Noto Serif", "Source Han Serif",
                    "serif")
    serif_body = []
    for m in re.finditer(r"<p\b([^>]*)>(.*?)</p>", s, re.S):
        attrs, inner = m.group(1), m.group(2)
        style = re.search(r'style="([^"]*)"', attrs)
        fam = re.search(r"font-family:([^;]+)", style.group(1)) if style else None
        if not fam:
            continue
        f = fam.group(1)
        if "sans-serif" in f and not re.search(r"Serif|Songti|STSong|SimSun", f):
            continue
        if not any(t in f for t in SERIF_TOKENS):
            continue
        if re.search(r"(?<!sans-)serif", f) is None:
            continue
        n_cjk = len(re.findall(r"[\u4e00-\u9fff]", re.sub(r"<[^>]+>", "", inner)))
        if n_cjk >= 40:
            serif_body.append(n_cjk)
    if serif_body:
        add(warn, f"有 {len(serif_body)} 个长正文段落(<p>)使用了衬线字体"
                  f"(最长 {max(serif_body)} 字) —— 正文应强制无衬线, "
                  f"仅标题/诗词/特殊文字可用衬线")

    # 12) WARN: 用了较大的固定 px 宽且**没有百分比 max-width 兜底**(窄屏易顶出屏幕)
    #     例: style="width:86px" 放在 25% 的单元格里, 320px 手机上单元格只剩 ~67px。
    #     安全写法: 同一 style 里带 max-width:100%(或任意百分比) → 能收缩, 不算风险。
    fixed = []
    for st in re.findall(r'style="([^"]*)"', s):
        if re.search(r"max-width\s*:\s*\d+%", st):
            continue                      # 有百分比 max-width 兜底 → 能收缩, 跳过
        for v in re.findall(r"(?<!-)width:(\d{2,3})px", st):
            if int(v) > 80:
                fixed.append(int(v))
    if fixed:
        add(warn, f"有 {len(fixed)} 处固定 px 宽 >80px 且无百分比 max-width 兜底"
                  f"(如 {sorted(set(fixed))[:4]}) —— 窄屏(320px)可能横向溢出, "
                  f"建议改 `width:100%;max-width:Npx`; 用 scripts/check_mobile_width.py 复验")

    # 11) INFO: 外链图片(公众号正文允许, 但要知道有几张、是否同域)
    ext = re.findall(r'<img\b[^>]*?\bsrc="(https?://[^"]+)"', s)
    hosts = sorted({re.match(r"https?://([^/]+)", u).group(1) for u in ext})
    info["外链图"] = f"{len(ext)} 张  hosts={hosts}" if ext else "0 张"
    info["页面级<style>"] = page_style

    # 统计
    def cnt(p):
        return len(re.findall(p, s))
    info["svg"] = cnt(r"<svg[\s>]")
    info["animate"] = cnt(r"<animate[\s>]")
    info["animateTransform"] = cnt(r"<animateTransform[\s>]")
    info["img"] = cnt(r"<img[\s>]")
    info["内嵌base64"] = cnt(r'src="data:image')
    info["大小MB"] = round(len(raw) / 1024 / 1024, 3)
    return name, fatal, warn, info


def main():
    ap = argparse.ArgumentParser(description="微信公众号 HTML / 内联 SVG 动效机检")
    ap.add_argument("paths", nargs="+", help="HTML 文件或目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--quiet", action="store_true", help="只打结论")
    ap.add_argument("--strict", action="store_true",
                    help="连预览壳一起检(默认只检会被粘进公众号的正文根节点)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="跳过路径中含该子串的文件, 可重复(如 --exclude _旧版)")
    a = ap.parse_args()

    files = collect(a.paths, a.exclude)
    if not files:
        print("没有找到 HTML 文件:", a.paths)
        return 1

    report, allf, allw = [], [], []
    for fp in files:
        name, f, w, info = check_file(fp, strict=a.strict)
        report.append({"file": name, "fatal": f, "warn": w, "info": info})
        allf += f
        allw += w

    if a.json:
        print(json.dumps({"files": report, "fatal": allf, "warn": allw},
                         ensure_ascii=False, indent=2))
    elif not a.quiet:
        for r in report:
            i = r["info"]
            print(f"\n{r['file']}")
            print(f"   svg ×{i['svg']}  <animate> ×{i['animate']}  "
                  f"<animateTransform> ×{i['animateTransform']}  <img> ×{i['img']} "
                  f"(内嵌 {i['内嵌base64']})  {i['大小MB']} MB")
            print(f"   外链图 {i['外链图']}"
                  + ("   [已剔除预览壳]" if i["预览壳已剔除"] else ""))
        print("\n===== FATAL =====")
        print("\n".join(allf) if allf else "(无)")
        print("\n===== WARN =====")
        print("\n".join(allw) if allw else "(无)")
        print("\n结论:", "通过 ✅" if not allf else f"未通过 ❌ ({len(allf)} 项 FATAL)")

    return 1 if allf else 0


if __name__ == "__main__":
    sys.exit(main())
