"""WebHtml2VectorEdit —— 自写 HTML→可编辑矢量转换核心(不依赖 WPI)。

管线:Playwright 加载(settle)→ 基准截图 → 平面枢纽 PDF → DOM 分层手术
(背景/图形/图片/文字四层,面板底色克隆剥离)→ 每层单独打印 →
pikepdf 按 OCG(可选内容组)合成为分层 PDF —— Illustrator 打开即得
图层结构;SVG/EPS 从平面枢纽衍生。相似度自检(SSIM)贯穿。

设计决策:胶水层用 Python(性能瓶颈在 Playwright/poppler/gs 子进程,
Rust 化无收益);分层用 PDF OCG(AI 打开 PDF 时 OCG 映射为图层,ADR 0009)。

被 to_vector.py / ai_export.py 调用;也可独立 import。
"""

from __future__ import annotations

import http.server
import os
import re
import socket
import subprocess
import sys
import threading

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

PX_PER_PT = 0.75          # CSS px → PDF pt
LAYER_ORDER = ("bg", "graphic", "image", "overlay", "text")  # 合成自底向上
LAYER_NAMES_ZH = {"bg": "背景", "graphic": "图形", "image": "图片",
                  "overlay": "蒙层", "text": "文字"}

EXE_CANDIDATES = {
    "msedge": (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    "chrome": (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
}

# ---- DOM 分层手术(JS,在页面里执行) --------------------------------
# 规则:
#   data-ai-layer 属性(背景/bg、图形/graphic、图片/image、文字/text)强制指定;
#   IMG/SVG/CANVAS/PICTURE/VIDEO → image;有直接文字且有底色 → text(底色随行);
#   有底色无内容 → graphic;"面板"(有底色且含子元素)→ 克隆底色为 graphic、
#   本体转结构;纯结构容器不打标(每层都显示,保证布局一致)。
INJECT_JS = r"""
() => {
  const KEY = {背景:'bg', bg:'bg', 图形:'graphic', graphic:'graphic',
               图片:'image', image:'image', 文字:'text', text:'text'};
  const alphaOf = c => { const m = c.match(/rgba?\([^)]*[, ]([\d.]+)\)/i);
                         return m ? parseFloat(m[1]) : (c && c !== 'transparent' ? 1 : 0); };
  const paints = el => {
    const s = getComputedStyle(el);
    if (s.backgroundColor && alphaOf(s.backgroundColor) > 0) return true;
    if (s.backgroundImage && s.backgroundImage !== 'none') return true;
    if (s.boxShadow && s.boxShadow !== 'none') return true;
    if (s.filter && s.filter !== 'none') return true;
    const bw = [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth];
    if (bw.some(w => parseFloat(w) > 0) && alphaOf(s.borderTopColor) > 0) return true;
    const pre = getComputedStyle(el, '::before'), aft = getComputedStyle(el, '::after');
    return (pre.content !== 'none' && pre.content !== '' && alphaOf(pre.backgroundColor) > 0)
        || (aft.content !== 'none' && aft.content !== '' && alphaOf(aft.backgroundColor) > 0);
  };
  const directText = el => [...el.childNodes].some(n =>
      n.nodeType === 3 && n.textContent.trim().length > 0);
  const tagOf = el => el.tagName;
  const mark = (el, k) => { if (k) el.setAttribute('data-w2v-layer', k); };

  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('[data-w2v-skip]')) continue;
    const ov = el.getAttribute('data-ai-layer');
    if (ov && KEY[ov.toLowerCase()]) { mark(el, KEY[ov.toLowerCase()]); continue; }
    const t = tagOf(el);
    if (t === 'IMG' || t === 'SVG' || t === 'CANVAS' || t === 'PICTURE' || t === 'VIDEO') {
      mark(el, 'image'); continue;
    }
    if (t === 'SCRIPT' || t === 'STYLE' || t === 'LINK' || t === 'META') continue;
    if (paints(el)) {
      if (directText(el)) { mark(el, 'text'); continue; }
      if (el.children.length > 0) {                    // 面板:底色剥离为克隆
        const s = getComputedStyle(el);
        const c = document.createElement('div');   // 用 div:避免被海报的 i/b 等元素选择器误中
        c.setAttribute('data-w2v-layer', 'graphic');
        c.style.cssText =
          'position:absolute;inset:0;z-index:-1;pointer-events:none;' +
          'border-style:solid;' +
          'border-color:' + s.borderTopColor + ';' +
          'border-width:' + s.borderTopWidth + ' ' + s.borderRightWidth + ' ' +
          s.borderBottomWidth + ' ' + s.borderLeftWidth + ';' +
          'border-radius:' + s.borderRadius + ';' +
          'background-color:' + s.backgroundColor + ';' +
          'background-image:' + s.backgroundImage + ';' +
          'background-size:' + s.backgroundSize + ';' +
          'background-position:' + s.backgroundPosition + ';' +
          'box-shadow:' + s.boxShadow + ';';
        el.style.backgroundColor = 'transparent';
        el.style.backgroundImage = 'none';
        el.style.boxShadow = 'none';
        el.style.borderColor = 'transparent';
        if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
        el.style.zIndex = '0';
        el.prepend(c);
        continue;                                      // 本体转结构,不打标
      }
      mark(el, 'graphic'); continue;
    }
    if (directText(el)) { mark(el, 'text'); continue; }
  }
  // 蒙层识别:graphic 且其前方兄弟里有图片/含图片 → 实为照片上的遮罩,归 overlay
  document.querySelectorAll('[data-w2v-layer="graphic"]').forEach(el => {
    let sib = el.previousElementSibling;
    while (sib) {
      if (sib.getAttribute('data-w2v-layer') === 'image'
          || sib.querySelector('[data-w2v-layer="image"]')) {
        el.setAttribute('data-w2v-layer', 'overlay');
        return;
      }
      sib = sib.previousElementSibling;
    }
  });

  // 返回每层元素的平均文档序(用于决定合成时上下层顺序)
  const all = [...document.querySelectorAll('body *')];
  const sums = {}, cnt = {};
  all.forEach((el, idx) => {
    const k = el.getAttribute && el.getAttribute('data-w2v-layer');
    if (k) { sums[k] = (sums[k] || 0) + idx; cnt[k] = (cnt[k] || 0) + 1; }
  });
  const means = {};
  for (const k in sums) means[k] = sums[k] / cnt[k];
  return means;
}
"""


def pick_channel() -> str | None:
    for channel, paths in EXE_CANDIDATES.items():
        if any(os.path.isfile(p) for p in paths):
            return channel
    return None


def poppler_exe(name: str) -> str | None:
    from _config import cfg
    d = cfg("poppler_dir")
    if not d:
        return None
    for cand in (os.path.join(d, name), os.path.join(d, "Library", "bin", name)):
        if os.path.isfile(cand):
            return cand
    return None


def gs_exe() -> str | None:
    from _config import cfg
    p = cfg("gs_path")
    return p if p and os.path.isfile(p) else None


def gs_env() -> dict:
    env = dict(os.environ)
    gs = gs_exe()
    if gs:
        root = os.path.dirname(os.path.dirname(gs))
        init = os.path.join(root, "Resource", "Init")
        if os.path.isdir(init):
            env["GS_LIB"] = ";".join((init, os.path.join(root, "lib"),
                                      os.path.join(root, "iccprofiles")))
    return env


def run(cmd: list[str], timeout: float = 300.0) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, env=gs_env(),
                       encoding="utf-8", errors="replace", timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_gs(cmd: list[str]) -> tuple[int, str]:
    gs = gs_exe()
    full = [gs] + cmd
    if gs:
        root = os.path.dirname(os.path.dirname(gs))
        if os.path.isdir(os.path.join(root, "Resource")):
            full.append("-sGenericResourceDir=" + os.path.join(root, "Resource") + os.sep)
    return run(full)


def work_dir() -> str:
    """poppler/gs 打不开非 ASCII 路径:全部子进程转换在 ASCII 临时目录进行。"""
    import tempfile
    return tempfile.mkdtemp(prefix="w2v_")


def serve(directory: str) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a) -> None:
            pass

    handler = lambda *a, **k: Quiet(*a, directory=directory, **k)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{port}"


def settle(page, max_wait: float) -> None:
    page.wait_for_load_state("networkidle", timeout=max_wait * 1000)
    page.evaluate("document.fonts.ready.then(() => 1)")
    page.evaluate("""async () => {
        const imgs = [...document.images];
        await Promise.all(imgs.map(im => im.complete ? 1 :
            new Promise(res => { im.onload = im.onerror = res; })));
    }""")
    page.wait_for_timeout(800)


def print_pdf(page, path: str, width: int, height: int) -> None:
    """屏媒体 + 精确 @page 尺寸单页打印(所见即所得,无分页)。"""
    page.emulate_media(media="screen")
    page.add_style_tag(
        content=f"@page {{ size: {width}px {height}px; margin: 0; }}")
    page.pdf(path=path, width=f"{width}px", height=f"{height}px",
             print_background=True, prefer_css_page_size=True, page_ranges="1")


# ---- 分层合成(pikepdf OCG) ------------------------------------------
_WHITE_FILL = re.compile(
    rb"q\s*[\d.]+ 0 0 [\d.]+ 0 0 cm\s*"
    rb"1 1 1 RG 1 1 1 rg\s*/G\d+ gs\s*"
    rb"0 0 \d+(?:\.\d+)? \d+(?:\.\d+)? re\s*f\s*Q\s*")


def strip_white_background(pdf_path: str) -> None:
    """剥掉 Chromium 打印 PDF 的整页不透明白底(原地)。
    不剥的话每层 XObject 都带白底,合成时上层把下层盖死。"""
    import pikepdf
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        data = page.Contents.read_bytes()
        cleaned, n = _WHITE_FILL.subn(b"", data)
        if n:
            page.Contents.write(cleaned)
        pdf.save(pdf_path)


def _inline_xobjects(out: "pikepdf.Pdf", src_pdf, page) -> tuple[bytes, pikepdf.Dictionary]:
    """递归内联页面内容里的 Form XObject(Chromium 套 2 层壳),资源改名防撞。
    返回 (摊平后的内容流字节, 合并后的资源字典)。"""
    import pikepdf
    from pikepdf import Dictionary, Name

    merged: dict[str, dict] = {}
    counter = {"n": 0}

    def visit(content: bytes, res: pikepdf.Dictionary, depth: int) -> bytes:
        if depth > 8:
            return content
        renames: dict[bytes, bytes] = {}
        hoisted: dict[str, Dictionary] = {}
        for cat in ("XObject", "ExtGState", "Font", "Pattern", "Shading",
                    "ColorSpace", "Properties"):
            if cat not in res:
                continue
            hoisted[cat] = Dictionary()
            for k, v in res[cat].items():
                new_name = f"{cat[0]}{counter['n']}{k.rawname[1:]}"
                counter["n"] += 1
                renames[k.rawname] = new_name.encode()
                hoisted[cat][Name("/" + new_name)] = out.copy_foreign(v)
        for cat, d in hoisted.items():
            merged.setdefault(cat, {})
            merged[cat].update(d)
        for old, new in renames.items():
            content = re.sub(rb"(" + re.escape(old) + rb")(?![A-Za-z0-9])",
                             b"/" + new, content)
        if "XObject" in res:
            for k, v in res.XObject.items():
                if "/Subtype" in v and v.Subtype == Name.Form:
                    inner = visit(v.read_bytes(), v.Resources or Dictionary(),
                                  depth + 1)
                    content = content.replace(
                        k.rawname + b" Do", b"q\n" + inner + b"\nQ")
        return content

    streams = [page.Contents] if not isinstance(page.Contents, pikepdf.Array) \
        else page.Contents
    data = b"".join(s.read_bytes() for s in streams)
    flat = visit(data, page.Resources or Dictionary(), 0)
    return flat, Dictionary({c: Dictionary(d) for c, d in merged.items()})


def merge_layers(layer_pdfs: list[str], names: list[str],
                 out_path: str, width_px: int, height_px: int) -> int:
    """把各层单页 PDF 合成单页分层 PDF(OCG,Acrobat/浏览器可见图层开关)。
    层内容以 Form XObject + BDC 标记承载(渲染实测 0.978);
    Illustrator 内部的真图层由 ai_save 的 COM 分发建立(见 ai_build_layers)。"""
    import pikepdf
    from pikepdf import Array, Dictionary, Name, String

    for src in layer_pdfs:
        strip_white_background(src)

    out = pikepdf.new()
    page = out.add_blank_page(page_size=(width_px * PX_PER_PT, height_px * PX_PER_PT))
    if Name.Resources not in page:
        page.Resources = Dictionary()
    if Name.XObject not in page.Resources:
        page.Resources.XObject = Dictionary()
    if Name.Properties not in page.Resources:
        page.Resources.Properties = Dictionary()

    content, ocg_refs = [], []
    for i, (src, name) in enumerate(zip(layer_pdfs, names)):
        with pikepdf.open(src) as src_pdf:
            xo = pikepdf.Page(src_pdf.pages[0]).as_form_xobject()
            page.Resources.XObject[Name(f"/W2V{i}")] = out.copy_foreign(xo)
        ocg = out.make_indirect(Dictionary(
            Type=Name.OCG, Name=String(name),
            Intent=Array([Name.View, Name.Design]),
            Usage=Dictionary(CreatorInfo=Dictionary(
                Creator=String("WebHtml2VectorEdit"), Subtype=Name.Artwork))))
        page.Resources.Properties[Name(f"/OC{i}")] = ocg
        ocg_refs.append(ocg)
        content.append(f"/OC /OC{i} BDC /W2V{i} Do EMC")

    page.Contents = out.make_stream(("\n".join(content) + "\n").encode("ascii"))
    out.Root.OCProperties = Dictionary(
        OCGs=Array(ocg_refs),
        D=Dictionary(RBGroups=Array([]), ON=Array(ocg_refs), Order=Array(ocg_refs)))
    out.save(out_path)
    return len(layer_pdfs)


def pdf_layers(path: str) -> list[str]:
    """读取 PDF 的 OCG 层名(校验用)。"""
    import pikepdf
    with pikepdf.open(path) as pdf:
        try:
            return [str(ocg.Name) for ocg in pdf.Root.OCProperties.OCGs]
        except (AttributeError, KeyError):
            return []


# ---- 下游衍生格式 ----------------------------------------------------
def to_svg(hub_pdf: str, out_path: str) -> None:
    pdftocairo = poppler_exe("pdftocairo.exe")
    rc, out = run([pdftocairo, "-svg", "-r", "300", hub_pdf, out_path])
    if rc:
        raise RuntimeError(f"pdftocairo -svg 失败: {out[-300:]}")


def to_eps(hub_pdf: str, out_path: str, engine: str = "poppler") -> None:
    if engine == "poppler":
        pdftops = poppler_exe("pdftops.exe")
        rc, out = run([pdftops, "-eps", "-level3", hub_pdf, out_path])
    else:
        rc, out = run_gs(["-dBATCH", "-dNOPAUSE", "-dSAFER",
                          "-sDEVICE=eps2write", "-dNoOutputFonts",
                          f"-sOutputFile={out_path}", hub_pdf])
    if rc:
        raise RuntimeError(f"EPS({engine}) 失败: {out[-300:]}")


def to_outline_pdf(hub_pdf: str, out_path: str) -> None:
    pdftocairo = poppler_exe("pdftocairo.exe")
    rc, out = run([pdftocairo, "-pdf", hub_pdf, out_path])
    if rc:
        raise RuntimeError(f"pdftocairo -pdf 转曲失败: {out[-300:]}")


# ---- 相似度自检 ------------------------------------------------------
def pdf_raster(pdftocairo: str, pdf: str, out_base: str) -> str:
    png = out_base + ".png"
    rc, out = run([pdftocairo, "-png", "-r", "96", "-singlefile", pdf, out_base])
    if rc or not os.path.isfile(png):
        raise RuntimeError(f"pdftocairo 栅格化失败: {out[-300:]}")
    return png


def svg_raster(page, svg_path: str, shot_path: str) -> None:
    head = open(svg_path, encoding="utf-8", errors="ignore").read(500)
    m = re.search(r'width="([\d.]+)pt"\s+height="([\d.]+)pt"', head)
    if not m:
        raise RuntimeError("SVG 缺少 pt 尺寸,无法定栅格视口")
    w, h = round(float(m.group(1)) * 4 / 3), round(float(m.group(2)) * 4 / 3)
    page.set_viewport_size({"width": w, "height": h})
    page.goto("file:///" + svg_path.replace("\\", "/"))
    page.wait_for_timeout(600)
    page.screenshot(path=shot_path)


def eps_raster(eps: str, png: str) -> None:
    rc, out = run_gs(["-dBATCH", "-dNOPAUSE", "-dSAFER", "-dEPSCrop",
                      "-sDEVICE=png16m", "-r96", f"-sOutputFile={png}", eps])
    if rc or not os.path.isfile(png):
        raise RuntimeError(f"gs EPS 栅格化失败: {out[-300:]}")


def ssim_report(ref_png: str, cand_png: str, diff_png: str) -> dict:
    from skimage.metrics import structural_similarity as ssim
    from PIL import Image
    import numpy as np

    ref_im = Image.open(ref_png).convert("RGB")
    cand_im = Image.open(cand_png).convert("RGB")
    if cand_im.size != ref_im.size:
        canvas = Image.new("RGB", ref_im.size, "white")
        canvas.paste(cand_im, (0, 0))
        cand_im = canvas
    ref, cand = (np.asarray(ref_im).astype(int), np.asarray(cand_im).astype(int))
    s = float(ssim(ref, cand, channel_axis=2, gaussian_weights=True,
                   sigma=1.5, use_sample_covariance=False, data_range=255))
    d = np.abs(ref - cand).sum(2)
    heat = np.zeros((ref.shape[0], ref.shape[1], 3), np.uint8)
    heat[..., 0] = np.clip(d, 0, 255)
    Image.fromarray(heat).save(diff_png)
    return {"ssim": round(s, 4),
            "mean_abs_diff": round(float(np.abs(ref - cand).mean()), 2),
            "diff_px_pct": round(float((d > 60).mean() * 100), 2),
            "diff_heatmap": diff_png}


# ---- 主流程 ----------------------------------------------------------
class WebHtml2VectorEdit:
    """HTML → 分层 AI 可编辑 PDF(默认)/ SVG / EPS / 免字体依赖 PDF + SSIM 自检。"""

    def __init__(self, source: str, output: str, width: int | None,
                 height: int | None,
                 layers: bool = True, formats: tuple[str, ...] = ("ai-pdf",),
                 eps_engine: str = "poppler", threshold: float = 0.95,
                 no_check: bool = False, max_wait: float = 15.0):
        self.source = source
        self.output = os.path.abspath(output)          # 前缀,无扩展名
        self.width, self.height = width, height        # 缺省时页面自探测
        self.layers = layers
        self.formats = formats                          # ai-pdf/print-pdf/svg/eps/outline-pdf
        self.eps_engine = eps_engine
        self.threshold = threshold
        self.no_check = no_check
        self.max_wait = max_wait
        self.warnings: list[str] = []
        self.outputs: dict[str, str] = {}
        self.similarity: dict[str, dict] = {}
        self.layer_names: list[str] = []

    def log(self, msg: str) -> None:
        print(msg, file=sys.stderr)

    def run(self) -> dict:
        from playwright.sync_api import sync_playwright

        os.makedirs(os.path.dirname(self.output) or ".", exist_ok=True)
        wd = work_dir()
        hub = os.path.join(wd, "hub.pdf")               # 平面枢纽(ASCII 目录)
        ref_png = self.output + "-reference.png"

        is_dir = os.path.isdir(self.source)
        if is_dir:
            if not os.path.isfile(os.path.join(self.source, "index.html")):
                raise FileNotFoundError("目录缺 index.html")
            srv, base = serve(self.source)
            url = base + "/index.html"
        else:
            srv = None
            url = "file:///" + os.path.abspath(self.source).replace("\\", "/")

        channel = pick_channel()
        if not channel:
            raise RuntimeError("未找到 Edge/Chrome,无法渲染")

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel=channel, headless=True)
                probe_w = self.width or 1080
                probe_h = self.height or 1440
                page = browser.new_page(
                    viewport={"width": probe_w, "height": probe_h},
                    device_scale_factor=1)
                page.goto(url, timeout=self.max_wait * 1000)
                settle(page, self.max_wait)
                if not self.width or not self.height:   # 画布自探测(固定画布海报)
                    # 先用矮视口量内容高:否则视口高度会灌进 scrollHeight(kv 踩过)
                    self.width = page.evaluate("document.documentElement.scrollWidth")
                    page.set_viewport_size({"width": self.width, "height": 800})
                    page.wait_for_timeout(400)
                    self.height = page.evaluate("document.documentElement.scrollHeight")
                    page.set_viewport_size({"width": self.width,
                                            "height": self.height})
                    settle(page, self.max_wait)
                    self.log(f"[probe] 画布 {self.width}x{self.height}")

                page.screenshot(path=ref_png, full_page=True)
                shot_h = page.evaluate("document.documentElement.scrollHeight")
                if shot_h > self.height + 2:
                    self.warnings.append(
                        f"内容高 {shot_h}px > 画布 {self.height}px:检查固定画布/overflow:hidden")

                # 1) 平面枢纽 PDF(未动 DOM,保真源头)
                print_pdf(page, hub, self.width, self.height)
                self.log(f"[hub] 平面枢纽 PDF 完成")

                # 2) 分层:DOM 手术 → 逐层打印(ASCII 临时目录)
                merged = os.path.join(wd, "ai.pdf")
                if self.layers and "ai-pdf" in self.formats:
                    means = page.evaluate(INJECT_JS)            # 每层平均文档序
                    self.log(f"[inject] {means}")
                    # 固定语义层序:背景→图形→图片→蒙层(照片上的遮罩)→文字
                    order = [k for k in LAYER_ORDER if k in means]
                    self.layer_names = [LAYER_NAMES_ZH[k] for k in order]
                    layer_files = []
                    for k in order:
                        style = page.add_style_tag(
                            content=(f'[data-w2v-layer]{{visibility:hidden}}'
                                     f'[data-w2v-layer="{k}"]{{visibility:visible}}'))
                        lp = os.path.join(wd, f"layer_{k}.pdf")
                        print_pdf(page, lp, self.width, self.height)
                        style.evaluate("el => el.remove()")
                        layer_files.append(lp)
                        self.log(f"[layer] {LAYER_NAMES_ZH[k]} 打印完成")
                    n = merge_layers(layer_files, self.layer_names,
                                     merged, self.width, self.height)
                    self.log(f"[ai-pdf] 分层合成完成({n} 层)")
                elif "ai-pdf" in self.formats:
                    merged = hub

                # 3) 下游衍生(从平面枢纽)
                for fmt, ext, fn in (("svg", "hub.svg", to_svg),
                                     ("outline-pdf", "outline.pdf", to_outline_pdf)):
                    if fmt in self.formats:
                        dst = os.path.join(wd, ext)
                        fn(hub, dst)
                        self.log(f"[{fmt}] 转换完成")
                if "eps" in self.formats:
                    to_eps(hub, os.path.join(wd, "hub.eps"), self.eps_engine)
                    self.log("[eps] 转换完成")

                # 4) 相似度自检(分层 PDF 整幅栅格,OCG 默认全开)
                if not self.no_check:
                    pdftocairo = poppler_exe("pdftocairo.exe")
                    checks = {"ai-pdf": merged, "print-pdf": hub}
                    if "outline-pdf" in self.formats:
                        checks["outline-pdf"] = os.path.join(wd, "outline.pdf")
                    if "svg" in self.formats:
                        checks["svg"] = None                    # chromium 栅格
                    if "eps" in self.formats:
                        if gs_exe():
                            checks["eps"] = os.path.join(wd, "hub.eps")
                        else:
                            self.warnings.append(
                                "EPS 相似度校验需要 gs(未部署),已跳过")
                    for fmt, src in checks.items():
                        cand = os.path.join(wd, f"chk-{fmt}.png")
                        if fmt == "svg":
                            svg_raster(page, os.path.join(wd, "hub.svg"), cand)
                        elif fmt == "eps":
                            eps_raster(src, cand)
                        else:
                            pdf_raster(pdftocairo, src, os.path.join(wd, f"chk-{fmt}"))
                        self.similarity[fmt] = ssim_report(
                            ref_png, cand, self.output + f"-diff-{fmt}.png")
                        os.remove(cand)
                        self.log(f"[check] {fmt}: SSIM {self.similarity[fmt]['ssim']}")
                browser.close()
        finally:
            if srv:
                srv.shutdown()

        # 5) 产物搬运(ASCII → 最终路径)
        import shutil as _sh
        plan = {"ai-pdf": (merged if "ai-pdf" in self.formats else None,
                           self.output + "-ai.pdf"),
                "print-pdf": (hub, self.output + "-print.pdf"),
                "outline-pdf": (os.path.join(wd, "outline.pdf"),
                                self.output + "-outline.pdf"),
                "svg": (os.path.join(wd, "hub.svg"), self.output + ".svg"),
                "eps": (os.path.join(wd, "hub.eps"), self.output + ".eps")}
        for fmt, (src, dst) in plan.items():
            if fmt in self.formats and src and os.path.isfile(src):
                if src == hub and fmt != "print-pdf":
                    _sh.copy(src, dst)      # 关图层时 ai-pdf 与枢纽同源,枢纽留给 print-pdf
                else:
                    _sh.move(src, dst)
                self.outputs[fmt] = dst
        if os.environ.get("W2V_KEEP"):          # 调试:保留 ASCII 临时目录
            self.log(f"[keep] 临时目录未清理: {wd}")
        else:
            _sh.rmtree(wd, ignore_errors=True)
        self.outputs["reference"] = ref_png

        failed = {k: v["ssim"] for k, v in self.similarity.items()
                  if v["ssim"] < self.threshold}
        report = {"ok": not failed, "outputs": self.outputs,
                  "reference": ref_png, "similarity": self.similarity,
                  "threshold": self.threshold,
                  "layers": self.layer_names, "warnings": self.warnings}
        if failed:
            report["error"] = "SSIM_BELOW_THRESHOLD"
            report["detail"] = failed
        return report


_AI_JS = '''app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var doc = app.open(new File("__IN__"));
var base = doc.layers[doc.layers.length - 1];   // 原内容层(在最后)
var items = [];
for (var i = 0; i < base.pageItems.length; i++) items.push(base.pageItems[i]);
function classify(it) {
    var t = it.typename;
    if (t === "RasterItem" || t === "PlacedItem") return "image";
    if (t === "TextFrame") return "text";
    if (t === "GroupItem" || t === "CompoundPathItem") {
        var children = (t === "CompoundPathItem") ? it.pathItems : it.pageItems;
        var hasText = false, hasImage = false;
        for (var j = 0; j < children.length; j++) {
            var c = classify(children[j]);
            if (c === "text") hasText = true;
            if (c === "image") hasImage = true;
        }
        if (hasText) return "text";
        if (hasImage) return "image";
    }
    return "graphic";
}
// PDF 导入常把整页包成少数大组:拆一层组才是有意义的分发粒度
if (items.length > 0 && items.length <= 3) {
    var flat = [];
    for (var i = 0; i < items.length; i++) {
        if (items[i].typename === "GroupItem") {
            for (var j = 0; j < items[i].pageItems.length; j++)
                flat.push(items[i].pageItems[j]);
        } else flat.push(items[i]);
    }
    items = flat;
}
var layGraphic = doc.layers.add(); layGraphic.name = "图形";
var layImage   = doc.layers.add(); layImage.name = "图片";
var layText    = doc.layers.add(); layText.name = "文字";
var n = {graphic: 0, image: 0, text: 0};
for (var i = 0; i < items.length; i++) {
    var k = classify(items[i]);
    items[i].move(k === "text" ? layText : (k === "image" ? layImage : layGraphic),
                  ElementPlacement.PLACEATBEGINNING);
    n[k]++;
}
base.remove();
var opts = new IllustratorSaveOptions();
opts.pdfCompatible = true;
doc.saveAs(new File("__OUT__"), opts);
doc.close(SaveOptions.DONOTSAVECHANGES);
"graphic=" + n.graphic + " image=" + n.image + " text=" + n.text;
'''


def ai_save(pdf_path: str, ai_path: str, timeout: float = 300.0) -> str:
    """真 .ai(带图层):驱动本机 Illustrator(COM)打开 PDF,建 图形/图片/文字
    三层并按对象类型分发,再另存(ADR 0008)。AI 未运行则结束后代为退出。
    返回分发明细字符串(graphic=N image=N text=N)。"""
    import tempfile

    tl = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Illustrator.exe"],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    ai_was_running = "illustrator.exe" in (tl.stdout or "").lower()

    jsx = (_AI_JS
           .replace("__IN__", pdf_path.replace("\\", "/"))
           .replace("__OUT__", ai_path.replace("\\", "/")))
    fd, jsx_path = tempfile.mkstemp(prefix="w2v_ai_", suffix=".jsx")
    with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
        f.write(jsx)

    ps = ("$ErrorActionPreference='Stop';"
          "$app = New-Object -ComObject Illustrator.Application; "
          f"$out = $app.DoJavaScriptFile('{jsx_path.replace(chr(92), '/')}'); "
          "Write-Output $out; "
          + ("$app.Quit();" if not ai_was_running else ""))
    try:
        rc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", ps], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
        if not os.path.isfile(ai_path):
            detail = ((rc.stdout or "") + (rc.stderr or ""))[-300:]
            raise RuntimeError(
                "Illustrator 另存 .ai 失败(检查是否已安装/COM 可用): " + detail)
        return (rc.stdout or "").strip()
    finally:
        os.remove(jsx_path)
