"""VectorEdit2WebHtml —— 逆向核心:可编辑矢量产物 → HTML(不依赖 WPI)。

输入:PDF(含 .ai 的 PDF 兼容层)/ EPS / SVG。
  PDF/ai → pdftohtml -xml(文字坐标/字号/颜色 + 图片位置)+ pdftocairo -svg(矢量底景)
  EPS    → gs 转回 PDF 再走上面管线
  SVG    → 直接内嵌(文字已转曲,无法还原字串,见输出告警)

两种模式:
  visual(默认)   矢量底景(SVG data-uri,视觉 100%)+ 透明可选文字层 + 原图 <img>;
  editable        去掉矢量底景,只留真实文字/图片(方便改文案后重走正向导出),
                  装饰性矢量不还原(文档明示)。

所有子进程在 ASCII 临时目录执行(poppler/gs 不吃非 ASCII 路径),产物搬运回最终路径。
"""

from __future__ import annotations

import base64
import html
import os
import re
import sys
import xml.etree.ElementTree as ET

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
from webhtml2vectoredit import (gs_exe, poppler_exe, run, run_gs,  # noqa: E402
                                work_dir)

PT2PX = 4.0 / 3.0     # pt → CSS px(96dpi)
MAX_EMBED = 12 * 1024 * 1024   # 单图内嵌上限(质量优先,超过仍内嵌但告警)


def _b64(path: str, mime: str) -> str:
    raw = open(path, "rb").read()
    if len(raw) > MAX_EMBED:
        print(f"[warn] {os.path.basename(path)} "
              f"{len(raw) // 1024}KB 内嵌为 data-uri", file=sys.stderr)
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _to_pdf(source: str, wd: str) -> tuple[str, str]:
    """归一到 PDF;返回 (ASCII 临时目录里的 pdf 路径, 实际输入类型)。"""
    ext = os.path.splitext(source)[1].lower().lstrip(".")
    if ext in ("pdf", "ai"):
        dst = os.path.join(wd, "in.pdf")
        import shutil
        shutil.copy(source, dst)                    # .ai 即 PDF 兼容流
        return dst, "pdf"
    if ext == "svg":
        return source, "svg"
    if ext == "eps":
        # -dEPSCrop:gs 默认把 EPS 搁在 A4 页面上,必须裁到 BoundingBox
        rc, out = run_gs(["-dBATCH", "-dNOPAUSE", "-dSAFER", "-dEPSCrop",
                          "-sDEVICE=pdfwrite",
                          f"-sOutputFile={os.path.join(wd, 'in.pdf')}", source])
        if rc:
            raise RuntimeError(f"EPS→PDF 失败: {out[-300:]}")
        return os.path.join(wd, "in.pdf"), "eps"
    raise ValueError(f"不支持的输入类型: .{ext}")


def _svg_to_data_uri(svg_path: str) -> str:
    raw = open(svg_path, "rb").read()
    b = base64.b64encode(raw).decode("ascii")
    return f"data:image/svg+xml;base64,{b}"


class VectorEdit2WebHtml:
    """PDF/EPS/SVG → 单文件自包含 HTML。"""

    def __init__(self, source: str, output: str, mode: str = "visual",
                 max_wait: float = 60.0):
        if mode not in ("visual", "editable"):
            raise ValueError("mode 须为 visual|editable")
        self.source = os.path.abspath(source)
        self.output = os.path.abspath(output)
        self.mode = mode
        self.max_wait = max_wait
        self.warnings: list[str] = []

    def log(self, msg: str) -> None:
        print(msg, file=sys.stderr)

    # ---- PDF/ai/eps:pdftohtml xml → 结构化内容 ----
    def _pdf_parts(self, pdf_path: str, wd: str) -> dict:
        pdftohtml = poppler_exe("pdftohtml.exe")
        if not pdftohtml:
            raise RuntimeError("缺 pdftohtml:跑 scripts/setup_vector.py")
        base = os.path.join(wd, "ve")
        rc, out = run([pdftohtml, "-xml", "-q", pdf_path, base])
        xml_path = base + ".xml"
        if rc or not os.path.isfile(xml_path):
            raise RuntimeError(f"pdftohtml 失败: {out[-300:]}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        page = root.find("page")

        # 坐标尺度归一:xml 单位 → CSS px(以页面宽对 MediaBox 换算,不依赖 zoom)
        import pikepdf
        with pikepdf.open(pdf_path) as pk:
            mb = [float(v) for v in pk.pages[0].MediaBox]
        unit_scale = float(page.get("width")) / max(mb[2] - mb[0], 1e-6)
        px = lambda u: float(u) * PT2PX / unit_scale

        fonts = {f.get("id"): {"size": float(f.get("size", "12")),
                               "family": re.sub(r"^[A-Z]{6}\+", "", f.get("family", "sans")),
                               "color": f.get("color", "#000000")}
                 for f in page.findall("fontspec")}
        texts, images = [], []
        for el in page:
            if el.tag == "text":
                spec = fonts.get(el.get("font", ""), {})
                txt = "".join(el.itertext()).replace("\n", " ").strip()
                if not txt:
                    continue
                texts.append({
                    "x": px(el.get("left")), "y": px(el.get("top")),
                    "size": px(spec.get("size", 12)),
                    "family": spec.get("family", "sans-serif"),
                    "color": spec.get("color", "#000000"),
                    "bold": el.find("b") is not None,
                    "text": html.escape(txt),
                })
            elif el.tag == "image":
                src = el.get("src") or ""
                h_u = float(el.get("height", "0"))
                # 只在 editable 模式放真实照片(.jpg);阴影等整页栅格件跳过
                if (self.mode == "editable" and src
                        and src.lower().endswith((".jpg", ".jpeg"))
                        and 2 < h_u < float(page.get("height"))
                        and float(el.get("left", "0")) >= 0):
                    fp = os.path.join(wd, src)
                    if os.path.isfile(fp):
                        images.append({
                            "x": px(el.get("left")), "y": px(el.get("top")),
                            "w": px(el.get("width")), "h": px(h_u),
                            "data": _b64(fp, "image/jpeg"),
                        })
        return {"w": px(page.get("width")), "h": px(page.get("height")),
                "texts": texts, "images": images}

    # ---- 组装 HTML ----
    def _compose(self, parts: dict, bg_data_uri: str | None) -> str:
        w, h = parts["w"], parts["h"]
        layers_css = [
            "body{margin:0;background:#888;font-family:sans-serif}",
            ".ve-canvas{position:relative;margin:0 auto;width:%gpx;height:%gpx;"
            "overflow:hidden;background:#fff}" % (w, h),
            ".ve-canvas>*{position:absolute;box-sizing:border-box}",
            ".ve-bg{left:0;top:0;width:100%%;height:100%%;"
            "background:url('%s') 0 0 / 100%% 100%% no-repeat}" % bg_data_uri
            if bg_data_uri else ".ve-bg{display:none}",
            ".ve-img{object-fit:fill}",
            ".ve-text{line-height:1;white-space:pre;pointer-events:auto}",
        ]
        parts_html = []
        if bg_data_uri:
            parts_html.append('<div class="ve-bg"></div>')
        for im in parts.get("images", []):
            parts_html.append(
                f'<img class="ve-img" src="{im["data"]}" '
                f'style="left:{im["x"]:.1f}px;top:{im["y"]:.1f}px;'
                f'width:{im["w"]:.1f}px;height:{im["h"]:.1f}px" alt="">')
        for tx in parts.get("texts", []):
            weight = "700" if tx["bold"] else "400"
            # visual 模式:文字透明(底景已画字形,透明层仅供选中复制,无叠影)
            color = "transparent" if self.mode == "visual" else tx["color"]
            parts_html.append(
                f'<span class="ve-text" style="left:{tx["x"]:.1f}px;top:{tx["y"]:.1f}px;'
                f'font:{weight} {tx["size"]:.0f}px/1 \'{tx["family"]}\',sans-serif;'
                f'color:{color}">{tx["text"]}</span>')
        return (f'<!DOCTYPE html>\n<!-- 由 VectorEdit2WebHtml 生成 '
                f'(mode={self.mode}) -->\n<html lang="zh">\n<head>\n'
                f'<meta charset="utf-8">\n<title>vector-edit-rebuild</title>\n'
                f'<style>\n{"".join(layers_css)}\n</style>\n</head>\n<body>\n'
                f'<div class="ve-canvas" style="width:{w:.0f}px;height:{h:.0f}px">\n'
                + "\n".join(parts_html) + "\n</div>\n</body>\n</html>\n")

    def run(self) -> dict:
        import shutil
        wd = work_dir()
        try:
            pdf_path, kind = _to_pdf(self.source, wd)
            bg_data_uri = None
            if kind == "svg":
                self.warnings.append(
                    "SVG 的文字已转曲(轮廓路径),无法还原字串;要可编辑文字请用 PDF/.ai 输入")
                with open(pdf_path, "rb") as f:
                    svg_raw = f.read()
                parts = {"w": 1080, "h": 1440, "texts": [], "images": []}
                m = re.search(rb'width="([\d.]+)pt" height="([\d.]+)pt"', svg_raw[:400])
                if m:
                    parts["w"], parts["h"] = float(m.group(1)) * PT2PX, float(m.group(2)) * PT2PX
                if self.mode == "visual":
                    bg_data_uri = _svg_to_data_uri(pdf_path)
            else:
                parts = self._pdf_parts(pdf_path, wd)
                if kind == "eps":
                    self.warnings.append("EPS 无透明:原透明区域已压平,视觉与源文件一致")
                if self.mode == "visual":
                    pdftocairo = poppler_exe("pdftocairo.exe")
                    svg_path = os.path.join(wd, "bg.svg")
                    rc, out = run([pdftocairo, "-svg", "-r", "96",
                                   pdf_path, svg_path])
                    if rc:
                        self.warnings.append("矢量底景生成失败,已退化为 editable 模式")
                    else:
                        bg_data_uri = _svg_to_data_uri(svg_path)
                if self.mode == "editable":
                    self.warnings.append(
                        "editable 模式不含装饰性矢量(渐变/图形),改完文案请重走 WebHtml2VectorEdit")
            html_doc = self._compose(parts, bg_data_uri)
            with open(self.output, "w", encoding="utf-8") as f:
                f.write(html_doc)
        finally:
            shutil.rmtree(wd, ignore_errors=True)

        return {"ok": True, "output": self.output,
                "mode": self.mode, "input": os.path.splitext(self.source)[1],
                "canvas": [round(parts["w"]), round(parts["h"])],
                "text_runs": len(parts.get("texts", [])),
                "images": len(parts.get("images", [])),
                "warnings": self.warnings}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import argparse
    p = argparse.ArgumentParser(
        description="VectorEdit2WebHtml:PDF/EPS/SVG/.ai → 可维护 HTML")
    p.add_argument("source", help=".pdf / .eps / .svg / .ai")
    p.add_argument("output", help="输出 HTML 路径")
    p.add_argument("--mode", default="visual", choices=["visual", "editable"],
                   help="visual=视觉完整(矢量底景+可选文字);"
                        "editable=纯文字图片,方便改稿重导出")
    a = p.parse_args()
    try:
        job = VectorEdit2WebHtml(a.source, a.output, mode=a.mode)
        report = job.run()
    except Exception as exc:  # noqa: BLE001
        print('{"ok": false, "error": %r}' % str(exc))
        return 1
    import json
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
