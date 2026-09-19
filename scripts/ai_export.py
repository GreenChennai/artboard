"""一键矢量导出(v1.9:Kiln 原生九格式薄壳)。

用法:
  python ai_export.py <项目目录>                # 出 SVG + PDF
  python ai_export.py <项目目录> --eps --ai     # 追加 EPS / Ai
  python ai_export.py --source 正面.html --source 反面.html --ai

画布尺寸由 Kiln 从画板几何自适应;矢量格式全部真文本可编辑
(SVG/PPTX 真文本、PDF CID 中文真文本、EPS 轮廓)。
"""

import argparse
import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
from _config import cfg, near_workspace  # noqa: E402


def _supports(path: str, flag: str) -> bool:
    """能力探测:二进制参数面是否含 flag(dist 曾长期滞后于源码)。"""
    try:
        r = subprocess.run([path, "export", "--help"], capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        return False
    return flag.encode() in r.stdout


def find_kiln() -> str:
    """返回满足参数面的 kiln-cli 路径;找不到返回空串。

    优先 dev 构建(target/release,随源码更新),dist 兜底;need 过滤掉
    参数面滞后的旧二进制(--engine/--height/--vector 是双车道契约最低集)。
    """
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    dev = near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))
    dst = near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe"))
    need = ("--engine", "--height", "--vector")
    for cand in (dev, dst):
        if cand and os.path.isfile(cand) and all(_supports(cand, f) for f in need):
            return cand
    # 全都不满足时退回原顺序并放行(让上层拿到可诊断的调用错误,而非静默)
    for cand in (dst, dev):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="artboard → Kiln 一键矢量导出")
    p.add_argument("source", nargs="?", help="项目目录 / HTML 文件（兼容旧用法）")
    p.add_argument("--source", dest="source_flags", action="append", default=[],
                   help="项目目录 / HTML 文件，可重复；多个源合并为一个多画板 AI")
    p.add_argument("--outdir", default="", help="输出目录(缺省 <项目>/export)")
    p.add_argument("--svg", action="store_true")
    p.add_argument("--pdf", action="store_true")
    p.add_argument("--eps", action="store_true")
    p.add_argument("--ai", action="store_true")
    p.add_argument("--pptx", action="store_true")
    p.add_argument("--width", type=int, default=0, help="矢量采集视口宽度")
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--reference", default="", help="PNG 参考图；提供时执行 97%% 相似度门禁")
    p.add_argument("--similarity", type=float, default=97.0,
                   help="参考图门禁（默认 97）")
    args = p.parse_args()

    sources = list(args.source_flags)
    if args.source:
        sources.insert(0, args.source)
    if not sources:
        p.error("必须提供项目目录/HTML，或至少一个 --source")

    kiln = find_kiln()
    if not kiln:
        print("[X] 未找到 Kiln 引擎:跑 scripts/setup_kiln.py 或设 ARTBOARD_KILN_CLI")
        return 2

    src = sources[0].rstrip("/\\")
    proj = src if os.path.isdir(src) else os.path.dirname(os.path.abspath(src))
    outdir = args.outdir or os.path.join(proj, "export")
    os.makedirs(outdir, exist_ok=True)

    fmts = []
    if args.svg: fmts.append("SVG")
    if args.pdf: fmts.append("PDF")
    if args.eps: fmts.append("EPS")
    if args.ai: fmts.append("AI")
    if args.pptx: fmts.append("PPTX")
    if not fmts:
        fmts = ["SVG", "PDF"]

    base = os.path.splitext(os.path.basename(src if os.path.isfile(src) else "poster"))[0]
    made = []
    failed = []
    for fmt in fmts:
        # 多源仅对 AI/矢量 DOM 路线有明确多画板语义；仍透传给 CLI，
        # 由 Kiln 对不支持的格式给出可诊断错误。
        out_base = f"{base}.{fmt.lower()}"
        out = os.path.join(outdir, out_base)
        cmd = [kiln, "export"]
        for source in sources:
            cmd += ["--source", source]
        cmd += ["--output", out, "--format", fmt]
        if args.width > 0:
            cmd += ["--width", str(args.width)]
        if args.transparent:
            cmd += ["--transparent"]
        r = subprocess.run(cmd,
                           capture_output=True, timeout=600)
        if r.returncode == 0 and os.path.isfile(out):
            made.append(out)
            print(f"[OK] {fmt}: {out}", file=sys.stderr)
        else:
            failed.append(fmt)
            print(f"[FAIL] {fmt}", file=sys.stderr)
    result = {"ok": bool(made), "made": made, "failed": failed or [],
              "sources": sources, "artboards": len(sources)}
    if args.reference and made:
        # 不依赖第三方库：交给随 Skill 提供的 ai_fidelity.py 做 PDF/AI 栅格对拍。
        verifier = os.path.join(_SCRIPTS, "ai_fidelity.py")
        try:
            vr = subprocess.run([sys.executable, verifier, "--reference", args.reference,
                                 "--ai", made[-1], "--min-score", str(args.similarity)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=300)  # pypdfium2 卡死时不再无限挂起
        except subprocess.TimeoutExpired:
            result["ok"] = False
            result["similarity"] = {"min": args.similarity, "returncode": -1,
                                    "output": "ai_fidelity 超时 300s"}
            print(json.dumps(result, ensure_ascii=False))
            return 1
        result["similarity"] = {"min": args.similarity, "returncode": vr.returncode,
                                "output": vr.stdout.strip()[-2000:]}
        if vr.returncode != 0:
            result["ok"] = False
    print(json.dumps(result, ensure_ascii=False))
    # 产出成功 ≠ 门禁通过:--reference 相似度不达标必须让进程失败,
    # 否则脚本链无法拦截(E 修:此前只看是否产出文件)
    ok = bool(made) and bool(result.get("ok", True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
