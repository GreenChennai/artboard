r"""artboard 模型分发:VQA / OCR 模块打包与下载部署。

用法:
  python fetch_model.py vqa        # 从 GitHub 发行页下载 VQA 模块并部署
  python fetch_model.py ocr        # 同上,OCR 模块
  python fetch_model.py            # 查看本地部署状态

模块来源:artboard 仓库的 GitHub Releases(见 RELEASE_BASE)。
部署位置:config.json 的 vqa_path / ocr_path(缺省会写到 artboard-tools 下)。
"""

import json
import os
import sys
import zipfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from _config import cfg, write_config  # noqa: E402
from _download import download  # noqa: E402

RELEASE_BASE = ("https://github.com/GreenChennai/artboard/releases/download/"
                "vqa-ocr-modules-v1")
MODULES = {
    "vqa": {
        "zip": f"{RELEASE_BASE}/vqa-module.zip",
        "path_key": "vqa_path",
        "default_dir": os.path.join(os.path.expanduser("~"), "artboard-tools", "VQA"),
        "probe": os.path.join("qora_assets", "qor08b.exe"),
        "size": "约 600MB(含 QORA-0.8B 模型,首次下载耐心等待)",
    },
    "ocr": {
        "zip": f"{RELEASE_BASE}/ocr-module.zip",
        "path_key": "ocr_path",
        "default_dir": os.path.join(os.path.expanduser("~"), "artboard-tools", "OCR"),
        "probe": "OCR.exe",
        "size": "约 110MB(单文件 OCR.exe,模型内嵌)",
    },
}


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def deployed(d: str, probe: str) -> bool:
    return os.path.isfile(os.path.join(d, probe))


def set_config(key: str, path: str) -> str:
    return write_config({key: path})


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    if not args:
        for name, m in MODULES.items():
            d = cfg(m["path_key"], m["default_dir"])
            state = "已部署" if deployed(d, m["probe"]) else "未部署"
            print(f"{name:<6} {state}  ({d})")
        print("用法: python fetch_model.py vqa|ocr")
        return 0

    failures = 0
    for name in args:
        m = MODULES.get(name)
        if not m:
            emit({"ok": False, "error": f"未知模块: {name}"})
            failures += 1
            continue
        d = cfg(m["path_key"], m["default_dir"])
        if deployed(d, m["probe"]):
            print(f"[{name}] 已部署于 {d}")
            continue
        try:
            print(f"[{name}] 下载模块({m['size']})…")
            os.makedirs(d, exist_ok=True)
            tmp = os.path.join(d, "_module.zip")
            try:
                download(m["zip"], tmp, label=f"{name} 模块")
                print(f"[{name}] 解压…")
                try:
                    with zipfile.ZipFile(tmp) as z:
                        z.extractall(d)
                finally:
                    if os.path.isfile(tmp):
                        os.remove(tmp)
            except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                if os.path.isfile(tmp):
                    os.remove(tmp)
                raise RuntimeError(f"{exc}") from exc
            if not deployed(d, m["probe"]):
                # zip 可能带一层目录,下探一层
                for sub in os.listdir(d):
                    subp = os.path.join(d, sub)
                    if os.path.isdir(subp) and deployed(subp, m["probe"]):
                        for item in os.listdir(subp):
                            os.rename(os.path.join(subp, item),
                                      os.path.join(d, item))
                        os.rmdir(subp)
                        break
            if not deployed(d, m["probe"]):
                raise RuntimeError(f"解压后未找到 {m['probe']}")
            path = set_config(m["path_key"], d)
            print(f"[{name}] 部署完成: {d}(已写入 {path})")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            emit({"ok": False, "module": name,
                  "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
