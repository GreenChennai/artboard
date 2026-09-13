"""artboard 环境部署:一键部署矢量转换工具链 poppler + Ghostscript(Windows)。

用法:
  python setup_vector.py                 # 检查并部署缺失项;路径写回 config.json
  python setup_vector.py --dir D:\tools  # 指定部署根目录(默认 ~/artboard-tools)

策略(二进制不进 git;许可 GPL/AGPL,技能仅子进程调用,不链接不分发):
  poppler     — oschwartz10612/poppler-windows release zip,解压即用;
  ghostscript — Artifex 官方 NSIS 安装器**用 7-Zip 解包**成便携版(免管理员、
                静默、不碰注册表);需要系统已装 7z(未装时提示手动安装 gs)。
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import zipfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from _config import cfg, write_config  # noqa: E402
from _download import download  # noqa: E402

POPPLER_URL = ("https://github.com/oschwartz10612/poppler-windows/releases/"
               "download/v26.07.0-0/Release-26.07.0-0.zip")
GS_URL = ("https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/"
          "download/gs10080/gs10080w64.exe")
def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def poppler_exe(d: str, name: str = "pdftocairo.exe") -> str | None:
    if not d:
        return None
    exe = os.path.join(d, name)
    if not os.path.isfile(exe):
        exe = os.path.join(d, "Library", "bin", name)
    return exe if os.path.isfile(exe) else None


def gs_ok(p: str) -> str | None:
    return p if p and os.path.isfile(p) else None


def find_7z() -> str:
    from _paths import find_7z as _find
    return _find()


def deploy_poppler(root: str) -> str:
    print(f"[poppler] 下载 {POPPLER_URL.rsplit('/', 1)[-1]}(约 42MB)…", file=sys.stderr)
    target = os.path.join(root, "poppler")
    os.makedirs(root, exist_ok=True)
    tmp = os.path.join(root, "_poppler.zip")
    tmpd = os.path.join(root, "_poppler_tmp")
    try:
        try:
            download(POPPLER_URL, tmp, label="poppler")
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc
        print("[poppler] 解压…", file=sys.stderr)
        try:
            with zipfile.ZipFile(tmp) as z:
                z.extractall(tmpd)
        finally:
            if os.path.isfile(tmp):
                os.remove(tmp)
        inner = glob.glob(os.path.join(tmpd, "poppler-*"))
        if not inner:
            raise RuntimeError(
                f"解压后未找到 poppler-* 目录(发行包结构可能变化): {tmpd}")
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.move(inner[0], target)
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
        if os.path.isfile(tmp):
            os.remove(tmp)
    bindir = os.path.join(target, "Library", "bin")
    print(f"[poppler] 就绪: {bindir}", file=sys.stderr)
    return bindir


def deploy_gs(root: str) -> str:
    z = find_7z()
    if not z:
        raise RuntimeError(
            "未找到 7-Zip:请先安装 https://www.7-zip.org,或手动安装 Ghostscript "
            "(https://ghostscript.com)后把 gswin64c.exe 路径填入 config.json 的 gs_path")
    target = os.path.join(root, "gs-portable")
    dl = os.path.join(root, "_dl")
    os.makedirs(dl, exist_ok=True)
    installer = os.path.join(dl, "gs-setup.exe")
    print("[ghostscript] 下载官方安装器(约 65MB,Artifex 官方发行)…", file=sys.stderr)
    try:
        download(GS_URL, installer, label="ghostscript")
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc
    print("[ghostscript] 7-Zip 解包为便携版(免管理员,不运行安装器)…", file=sys.stderr)
    try:
        subprocess.run([z, "x", "-y", f"-o{target}", installer],
                       check=True, capture_output=True, timeout=600)
    finally:
        if os.path.isfile(installer):
            os.remove(installer)
    exe = os.path.join(target, "bin", "gswin64c.exe")
    if not os.path.isfile(exe):
        raise RuntimeError(f"解包后未找到 gswin64c.exe: {target}")
    print(f"[ghostscript] 就绪(便携): {exe}", file=sys.stderr)
    return exe


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="", help="部署根目录(默认 ~/artboard-tools)")
    args = p.parse_args()

    root = args.dir or os.path.join(os.path.expanduser("~"), "artboard-tools")
    changed = {}

    pd = poppler_exe(cfg("poppler_dir"))
    if pd:
        print(f"[OK] poppler 已就绪: {pd}")
    else:
        try:
            changed["poppler_dir"] = deploy_poppler(root)
        except RuntimeError as exc:
            print(f"[FAIL] poppler 部署失败: {exc}", file=sys.stderr)
            print("  (pdftocairo/pdftops 缺失 → SVG / EPS / print-pdf 自检不可用;"
                  "可手动下载 Release 后把目录填入 config.json 的 poppler_dir)",
                  file=sys.stderr)

    gs = gs_ok(cfg("gs_path"))
    if gs:
        print(f"[OK] ghostscript 已就绪: {gs}")
    else:
        try:
            changed["gs_path"] = deploy_gs(root)
        except RuntimeError as exc:
            print(f"[WARN] ghostscript 部署失败: {exc}", file=sys.stderr)
            print("  (SVG / print-pdf / outline-pdf / poppler-EPS 不受影响;"
                  "仅 gs-EPS 引擎与 EPS 相似度校验不可用)", file=sys.stderr)

    if changed:
        path = write_config(changed)
        print(f"[done] 已写入 {path}: {', '.join(changed)}", file=sys.stderr)
    print("矢量交付就绪:python scripts/to_vector.py --source <proj>/src "
          "--output <proj>/export/poster --width 1080 --height 1440")
    return 0


if __name__ == "__main__":
    sys.exit(main())
