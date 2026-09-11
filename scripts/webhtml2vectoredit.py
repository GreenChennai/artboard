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
from text_run_merger import merge_text_runs  # noqa: E402

PX_PER_PT = 0.75          # CSS px → PDF pt
LAYER_ORDER = ("bg", "content")  # 合成自底向上:仅 背景层/内容层(item 5)
LAYER_NAMES_ZH = {"bg": "背景", "content": "内容"}

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
    """屏媒体 + 精确 @page 尺寸单页打印(所见即所得,无分页)。
    打印后立即合并逐字 Td/Tj 为整句 TJ(修 AI 文字断层,item 4)。"""
    page.emulate_media(media="screen")
    page.add_style_tag(
        content=f"@page {{ size: {width}px {height}px; margin: 0; }}")
    page.pdf(path=path, width=f"{width}px", height=f"{height}px",
             print_background=True, prefer_css_page_size=True, page_ranges="1")
    try:
        merge_text_runs(path)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 文字合并跳过: {exc}", file=sys.stderr)


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
                    # 双层制(item 5):背景层=图形/装饰底;内容层=文字/图片/蒙层
                    passes = [
                        ("bg",
                         '[data-w2v-layer="text"],[data-w2v-layer="image"],'
                         '[data-w2v-layer="overlay"]{visibility:hidden}'),
                        ("content",
                         '[data-w2v-layer="graphic"]{visibility:hidden}'),
                    ]
                    layer_files = []
                    self.layer_names = [LAYER_NAMES_ZH[k] for k, _ in passes]
                    for k, css in passes:
                        style = page.add_style_tag(content=css)
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



# ---- 原生 AI 构建:DOM 组件树 → ExtendScript 建嵌套真组(item 1/2/5) ----
_DOM_EXTRACT_JS = r"""
() => {
  function parseColor(s) {
    if (!s || s === 'transparent' || s === 'none') return null;
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[, ]+/).map(Number);
      const a = p.length > 3 ? p[3] : 1;
      if (a === 0) return null;               // 全透明黑不算填充
      return {r: p[0], g: p[1], b: p[2], a: a};
    }
    return null;
  }
  const firstNum = s => { const m = String(s || '0').match(/[\d.]+/); return m ? parseFloat(m[0]) : 0; };
  const cands = [...document.body.children].map(el => {
    const r = el.getBoundingClientRect();
    return {el, area: r.width * r.height};
  });
  cands.sort((a, b) => b.area - a.area);
  const root = cands.length ? cands[0].el : document.body;
  const rr0 = root.getBoundingClientRect();
  const OX = rr0.left, OY = rr0.top;
  const out = {w: rr0.width, h: rr0.height,
               bodyBg: parseColor(getComputedStyle(document.body).backgroundColor),
               root: null, images: []};

  function nodeFor(el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    const cls = (typeof el.className === 'string')
      ? el.className.split(/\s+/).filter(Boolean).slice(0, 2).join('.') : '';
    const n = {
      name: el.tagName.toLowerCase() + (cls ? '.' + cls : ''),
      rect: [r.left - OX, r.top - OY, r.width, r.height],
      bg: parseColor(s.backgroundColor),
      radius: firstNum(s.borderRadius),
      border: null, image: null, texts: [], children: []
    };
    const bw = [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth,
                s.borderLeftWidth].map(parseFloat);
    const bc = parseColor(s.borderTopColor);
    if (bc && bw.some(v => v > 0)) n.border = {w: Math.max.apply(null, bw), color: bc};
    if (el.tagName === 'IMG') {
      n.image = {url: el.src, file: null};
      out.images.push(n.image);   // 同一引用:materialize 时 file 回填到节点
    }
    el.childNodes.forEach(nd => {
      if (nd.nodeType === 3 && nd.textContent.trim()) {
        const rng = document.createRange();
        rng.selectNodeContents(nd);
        const rr = rng.getBoundingClientRect();
        if (rr.width < 0.5 || rr.height < 0.5) return;
        n.texts.push({
          text: nd.textContent.trim().slice(0, 800),
          x: rr.left - OX, y: rr.top - OY, w: rr.width, h: rr.height,
          size: parseFloat(s.fontSize),
          weight: parseInt(s.fontWeight) >= 600 ? 700 : 400,
          color: parseColor(s.color),
          family: s.fontFamily.split(',')[0].replace(/["']/g, ''),
          tracking: (s.letterSpacing !== 'normal')
                    ? parseFloat(s.letterSpacing) / parseFloat(s.fontSize) * 1000 : 0
        });
      }
    });
    return n;
  }

  function walk(el) {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return null;
    const n = nodeFor(el);
    for (const child of el.children) {
      if (child.tagName === 'SCRIPT' || child.tagName === 'STYLE' || child.tagName === 'LINK') continue;
      const c = walk(child);
      if (c) n.children.push(c);
    }
    return n;
  }
  out.root = walk(root);
  return out;
}
"""

_AI_BUILD_JSX = r"""
#target illustrator
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var TREE = __TREE__;
var doc = app.documents.add(DocumentColorSpace.RGB, TREE.w * 0.75, TREE.h * 0.75);
doc.layers[0].name = "背景层";                 // 复用默认层,避免多余空层
var layBg = doc.layers[0];
var layContent = doc.layers.add(); layContent.name = "内容层";
var fontCache = {};
function findFont(fam) {
    if (fontCache[fam] !== undefined) return fontCache[fam];
    var found = null;
    for (var i = 0; i < app.textFonts.length; i++) {
        if (app.textFonts[i].family === fam) { found = app.textFonts[i]; break; }
    }
    fontCache[fam] = found;
    return found;
}
function rgbCol(c) { var k = new RGBColor(); k.red = c.r; k.green = c.g; k.blue = c.b; return k; }
function px(v) { return v * 0.75; }
// 标定实测:rectangle/position 的纵参数 = 画布高 - DOM 顶边距(底部原点向上)
function topY(y, h) { return (TREE.h - y) * 0.75; }
function makeRect(container, n) {
    var x = px(n.rect[0]), y = topY(n.rect[1], n.rect[3]), w = px(n.rect[2]), h = px(n.rect[3]);
    var p = (n.radius > 0.5)
        ? container.pathItems.roundedRectangle(y, x, w, h, px(Math.min(n.radius, h / 2)))
        : container.pathItems.rectangle(y, x, w, h);
    p.filled = true;
    p.fillColor = rgbCol(n.bg);
    if (n.bg.a < 1) p.opacity = n.bg.a * 100;
    p.stroked = false;
    return p;
}
function addImage(container, n) {
    var f = new File(n.image.file);
    if (!f.exists) return;
    var pi = doc.layers[0].placedItems.add();   // placedItem 只能建在层上
    pi.file = f;
    pi.width = px(n.rect[2]);
    pi.height = px(n.rect[3]);
    pi.position = [px(n.rect[0]), topY(n.rect[1], n.rect[3])];
    pi.embed();
    pi.move(container, ElementPlacement.PLACEATEND);   // 移入目标组,垫底
}
function addTexts(container, node) {
    for (var i = 0; i < node.texts.length; i++) {
        var t = node.texts[i];
        var tf = container.textFrames.add();
        tf.contents = t.text;
        tf.textRange.characterAttributes.size = px(t.size);
        tf.textRange.characterAttributes.fillColor = rgbCol(t.color);
        if (t.tracking) tf.textRange.characterAttributes.tracking = Math.round(t.tracking);
        var f = findFont(t.family);
        if (f) tf.textRange.characterAttributes.textFont = f;
        tf.left = px(t.x);
        tf.top = topY(t.y, t.h) - px(t.size) * 0.24;
    }
}
function build(node, container) {
    var grp = container.groupItems.add();
    try { grp.name = node.name; } catch (eG) {}
    if (node.bg) makeRect(grp, node);
    if (node.border) {
        var bp = grp.pathItems.rectangle(
            topY(node.rect[1], node.rect[3]),
            px(node.rect[0]), px(node.rect[2]), px(node.rect[3]));
        bp.filled = false;
        bp.stroked = true;
        bp.strokeWidth = px(node.border.w);
        bp.strokeColor = rgbCol(node.border.color);
    }
    if (node.image) addImage(grp, node);
    addTexts(grp, node);
    for (var i = 0; i < node.children.length; i++) build(node.children[i], grp);
    return grp;
}
if (TREE.bodyBg) {
    // 顶部边距底 = 画布高(底部原点坐标系)
    var b = layBg.pathItems.rectangle(px(TREE.h), 0, px(TREE.w), px(TREE.h));
    b.filled = true;
    b.fillColor = rgbCol(TREE.bodyBg);
    b.stroked = false;
}
if (TREE.root && TREE.root.bg) makeRect(layBg, TREE.root);
if (TREE.root) {
    var rootGrp = layContent.groupItems.add();
    try { rootGrp.name = "内容"; } catch (eR) {}
    for (var i = 0; i < TREE.root.children.length; i++) build(TREE.root.children[i], rootGrp);
}
doc.saveAs(new File("__OUT__"), new IllustratorSaveOptions());
doc.close(SaveOptions.DONOTSAVECHANGES);
"native-done";
"""


def ai_build_native(source: str, out_ai: str, width: int | None = None,
                    height: int | None = None, max_wait: float = 15.0,
                    timeout: float = 600.0) -> dict:
    """从 HTML 的 DOM 组件树原生构建 .ai:嵌套真组(Ctrl+G 语义)+真文字,
    背景/内容双层。不经 PDF——组件层级即 DOM 层级(item 1/2/5)。"""
    import json as _json
    import shutil as _sh
    import tempfile
    import urllib.parse

    is_dir = os.path.isdir(source)
    if is_dir:
        if not os.path.isfile(os.path.join(source, "index.html")):
            raise FileNotFoundError("目录缺 index.html")
        srv, base = serve(source)
        root_dir = os.path.abspath(source)
        url = base + "/index.html"
    else:
        srv = None
        root_dir = os.path.dirname(os.path.abspath(source))
        url = "file:///" + os.path.abspath(source).replace("\\", "/")

    channel = pick_channel()
    if not channel:
        raise RuntimeError("未找到 Edge/Chrome")
    wd = work_dir()

    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel=channel, headless=True)
            page = browser.new_page(
                viewport={"width": width or 1080, "height": height or 1440},
                device_scale_factor=1)
            page.goto(url, timeout=max_wait * 1000)
            settle(page, max_wait)
            if not width or not height:
                page.set_viewport_size({"width": page.evaluate(
                    "document.documentElement.scrollWidth"), "height": 800})
                page.wait_for_timeout(400)
                page.set_viewport_size({
                    "width": page.evaluate("document.documentElement.scrollWidth"),
                    "height": page.evaluate("document.documentElement.scrollHeight")})
                settle(page, max_wait)
            tree = page.evaluate(_DOM_EXTRACT_JS)
            browser.close()
    finally:
        if srv:
            srv.shutdown()

    # 图片落位:http URL → 源目录真实文件;拷进 ASCII 临时目录(AI File 不吃中文路径)
    img_n = 0
    for img in tree.get("images", []):
        u = img["url"]
        path = urllib.parse.unquote(urllib.parse.urlparse(u).path).lstrip("/")
        real = None
        for cand in (os.path.join(root_dir, path),):
            if os.path.isfile(cand):
                real = cand
                break
        if real:
            img_n += 1
            fp = os.path.join(wd, f"img{img_n}."
                              + (os.path.splitext(real)[1].lstrip(".") or "jpg"))
            _sh.copy(real, fp)
            img["file"] = fp.replace("\\", "/")
        else:
            img["file"] = None

    def clean(n):
        if isinstance(n.get("image"), dict) and not n["image"].get("file"):
            n["image"] = None
        for c in n.get("children", []):
            clean(c)

    clean(tree["root"])

    tree_json = _json.dumps(tree, ensure_ascii=False)
    jsx = (_AI_BUILD_JSX
           .replace("__TREE__", tree_json)
           .replace("__OUT__", os.path.abspath(out_ai).replace("\\", "/")))

    tl = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Illustrator.exe"],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    ai_was_running = "illustrator.exe" in (tl.stdout or "").lower()
    fd, jsx_path = tempfile.mkstemp(prefix="w2v_build_", suffix=".jsx")
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
        if not os.path.isfile(out_ai):
            raise RuntimeError("Illustrator 原生构建失败: "
                               + ((rc.stdout or "") + (rc.stderr or ""))[-400:])
    finally:
        os.remove(jsx_path)
    return {"ok": True, "output": os.path.abspath(out_ai),
            "layers": ["背景", "内容"], "mode": "native-dom",
            "images": len(tree.get("images", []))}
