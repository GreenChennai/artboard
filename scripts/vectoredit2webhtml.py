"""VectorEdit2WebHtml —— 逆向核心:可编辑矢量产物 → HTML(不依赖 WPI)。

输入:PDF(含 .ai 的 PDF 兼容层)/ EPS / SVG;PDF 支持多页(逐页输出 HTML)。
  PDF/ai → pdftohtml -xml(文字坐标/字号/颜色 + 图片位置)+ pdftocairo -svg(矢量底景)
  EPS    → gs -dEPSCrop 转回 PDF 再走上面管线
  SVG    → 直接内嵌(文字已转曲,无法还原字串,见输出告警)

两种模式:
  visual(默认)   矢量底景(SVG data-uri,视觉 100%)+ 透明可选文字层;
  editable        去掉矢量底景,只留真实文字/图片(改文案后重走正向导出),
                  装饰性矢量不还原(文档明示)。

多页:输出 <前缀>-p01.html … <前缀>-pNN.html(每页自包含)。
所有子进程在 ASCII 临时目录执行(poppler/gs 不吃非 ASCII 路径)。
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
MAX_EMBED = 12 * 1024 * 1024


def _b64(path: str, mime: str) -> str:
    raw = open(path, "rb").read()
    if len(raw) > MAX_EMBED:
        print(f"[warn] {os.path.basename(path)} "
              f"{len(raw) // 1024}KB 内嵌为 data-uri", file=sys.stderr)
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _normalize_pdf(source: str, wd: str) -> tuple[str, str]:
    """归一到 PDF;返回 (临时目录内 pdf 路径, 实际输入类型)。"""
    import shutil
    ext = os.path.splitext(source)[1].lower().lstrip(".")
    if ext in ("pdf", "ai"):
        dst = os.path.join(wd, "in.pdf")
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


def _page_parts(page_el, pdf_path: str, wd: str, mode: str,
                page_no: int) -> dict:
    """解析 pdftohtml -xml 的单个 <page> → 结构化内容。"""
    mb_w = 595.0
    try:
        import pikepdf
        with pikepdf.open(pdf_path) as pk:
            mb = [float(v) for v in pk.pages[page_no - 1].MediaBox]
            mb_w = mb[2] - mb[0]
    except Exception:
        pass
    unit_scale = float(page_el.get("width")) / max(mb_w, 1e-6)

    def px(u):
        return float(u) * PT2PX / unit_scale

    fonts = {f.get("id"): {"size": float(f.get("size", "12")),
                           "family": re.sub(r"^[A-Z]{6}\+", "", f.get("family", "sans")),
                           "color": f.get("color", "#000000")}
             for f in page_el.findall("fontspec")}
    texts, images = [], []
    for el in page_el:
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
            if (mode == "editable" and src
                    and src.lower().endswith((".jpg", ".jpeg"))
                    and 2 < h_u < float(page_el.get("height"))
                    and float(el.get("left", "0")) >= 0):
                fp = os.path.join(wd, src)
                if os.path.isfile(fp):
                    images.append({
                        "x": px(el.get("left")), "y": px(el.get("top")),
                        "w": px(el.get("width")), "h": px(h_u),
                        "data": _b64(fp, "image/jpeg"),
                    })
    return {"w": px(page_el.get("width")), "h": px(page_el.get("height")),
            "texts": texts, "images": images}


def _compose(parts: dict, bg_data_uri: str | None, mode: str,
             page_label: str = "") -> str:
    w, h = parts["w"], parts["h"]
    css = [
        "body{margin:0;background:#888;font-family:sans-serif}",
        f".ve-canvas{{position:relative;margin:0 auto;width:{w:.0f}px;"
        f"height:{h:.0f}px;overflow:hidden;background:#fff}}",
        ".ve-canvas>*{position:absolute;box-sizing:border-box}",
    ]
    if bg_data_uri:
        css.append(".ve-bg{left:0;top:0;width:100%;height:100%;"
                   f"background:url('{bg_data_uri}') 0 0 / 100% 100% no-repeat}}")
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
        color = "transparent" if mode == "visual" else tx["color"]
        parts_html.append(
            f'<span class="ve-text" style="left:{tx["x"]:.1f}px;top:{tx["y"]:.1f}px;'
            f'font:{weight} {tx["size"]:.0f}px/1 \'{tx["family"]}\',sans-serif;'
            f'color:{color}">{tx["text"]}</span>')
    return (f'<!DOCTYPE html>\n<!-- 由 VectorEdit2WebHtml 生成 (mode={mode}'
            f' page={page_label}) -->\n<html lang="zh">\n<head>\n'
            f'<meta charset="utf-8">\n<title>vector-edit-rebuild {page_label}</title>\n'
            f'<style>\n{"".join(css)}\n</style>\n</head>\n<body>\n'
            f'<div class="ve-canvas">\n' + "\n".join(parts_html)
            + "\n</div>\n</body>\n</html>\n")


class VectorEdit2WebHtml:
    """PDF/EPS/SVG → 自包含 HTML(多页逐页输出)。"""

    def __init__(self, source: str, output: str, mode: str = "visual",
                 pages: str = "", max_wait: float = 60.0):
        if mode not in ("visual", "editable"):
            raise ValueError("mode 须为 visual|editable")
        self.source = os.path.abspath(source)
        self.output = os.path.abspath(output)          # 单页:直接用;多页:作为前缀
        self.mode = mode
        self.pages = pages                              # 如 "1-5,10";空=全部
        self.warnings: list[str] = []

    def log(self, msg: str) -> None:
        print(msg, file=sys.stderr)

    def run(self) -> dict:
        wd = work_dir()
        try:
            pdf_path, kind = _normalize_pdf(self.source, wd)
            if kind == "svg":
                return self._svg_single(pdf_path, wd)
            return self._pdf_multi(pdf_path, wd, kind)
        finally:
            import shutil as _sh
            _sh.rmtree(wd, ignore_errors=True)

    # ---- SVG 单文件 ----
    def _svg_single(self, svg_path: str, wd: str) -> dict:
        self.warnings.append(
            "SVG 的文字已转曲(轮廓路径),无法还原字串;要可编辑文字请用 PDF/.ai 输入")
        with open(svg_path, "rb") as f:
            raw = f.read()
        m = re.search(rb'width="([\d.]+)pt" height="([\d.]+)pt"', raw[:400])
        w = float(m.group(1)) * PT2PX if m else 1080.0
        h = float(m.group(2)) * PT2PX if m else 1440.0
        parts = {"w": w, "h": h, "texts": [], "images": []}
        doc = _compose(parts, _svg_to_data_uri(svg_path), self.mode)
        with open(self.output, "w", encoding="utf-8") as f:
            f.write(doc)
        return {"ok": True, "output": self.output, "pages": 1, "mode": self.mode,
                "warnings": self.warnings}

    # ---- PDF 多页 ----
    def _pdf_multi(self, pdf_path: str, wd: str, kind: str) -> dict:
        pdftohtml = poppler_exe("pdftohtml.exe")
        pdftocairo = poppler_exe("pdftocairo.exe")
        if not pdftohtml or not pdftocairo:
            raise RuntimeError("缺 poppler:跑 scripts/setup_vector.py")
        if kind == "eps":
            self.warnings.append("EPS 无透明:原透明区域已压平,视觉与源文件一致")
        if self.mode == "editable":
            self.warnings.append(
                "editable 模式不含装饰性矢量(渐变/图形),改完文案请重走 WebHtml2VectorEdit")

        base = os.path.join(wd, "ve")
        rc, out = run([pdftohtml, "-xml", "-q", pdf_path, base])
        xml_path = base + ".xml"
        if rc or not os.path.isfile(xml_path):
            raise RuntimeError(f"pdftohtml 失败: {out[-300:]}")
        root = ET.parse(xml_path).getroot()
        page_els = root.findall("page")
        total = len(page_els)

        # 页码选择
        if self.pages:
            wanted: set[int] = set()
            for part in self.pages.split(","):
                if "-" in part:
                    a, b = part.split("-")
                    wanted.update(range(int(a), int(b) + 1))
                elif part.strip():
                    wanted.add(int(part))
            wanted = {p for p in wanted if 1 <= p <= total}
        else:
            wanted = set(range(1, total + 1))

        outputs = []
        for pno in sorted(wanted):
            page_el = page_els[pno - 1]
            parts = _page_parts(page_el, pdf_path, wd, self.mode, pno)
            bg_uri = None
            if self.mode == "visual":
                svg_path = os.path.join(wd, f"bg-{pno}.svg")
                rc, out = run([pdftocairo, "-svg", "-r", "96",
                               "-f", str(pno), "-l", str(pno), pdf_path, svg_path])
                if rc == 0 and os.path.isfile(svg_path):
                    bg_uri = _svg_to_data_uri(svg_path)
                else:
                    self.warnings.append(f"第 {pno} 页矢量底景生成失败,退化为 editable")
            doc_html = _compose(parts, bg_uri, self.mode, str(pno))
            if total > 1:
                out_path = re.sub(r"\.html$", "",
                                  self.output) + f"-p{pno:02d}.html"
            else:
                out_path = self.output
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(doc_html)
            outputs.append(out_path)
            self.log(f"[page {pno}/{total}] {os.path.basename(out_path)} "
                     f"({len(parts['texts'])} 文字块)")

        return {"ok": True, "output": outputs[0] if len(outputs) == 1
                else os.path.dirname(outputs[0]),
                "pages": len(outputs), "total_pages": total,
                "files": outputs, "mode": self.mode,
                "warnings": self.warnings}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import argparse
    p = argparse.ArgumentParser(
        description="VectorEdit2WebHtml:PDF/EPS/SVG/.ai → 可维护 HTML(支持多页)")
    p.add_argument("source", help=".pdf / .eps / .svg / .ai")
    p.add_argument("output", help="输出 HTML 路径(多页时作为前缀)")
    p.add_argument("--mode", default="visual", choices=["visual", "editable"],
                   help="visual=视觉完整(矢量底景+透明可选文字);"
                        "editable=纯文字图片,方便改稿重导出")
    p.add_argument("--pages", default="",
                   help='多页 PDF 页码选择,如 "1-5,10";默认全部')
    a = p.parse_args()
    try:
        job = VectorEdit2WebHtml(a.source, a.output, mode=a.mode, pages=a.pages)
        report = job.run()
    except Exception as exc:  # noqa: BLE001
        print('{"ok": false, "error": %r}' % str(exc))
        return 1
    import json
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
