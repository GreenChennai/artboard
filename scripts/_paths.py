"""artboard 共享路径探测:浏览器内核 / 7-Zip 的候选路径单点定义。

背景:此前 EDGE/CHROME 候选路径在 export_fallback.py、preflight.py、
webhtml2vectoredit.py 各写一份,且 webhtml2vectoredit.py 那份**漏了**
`%LOCALAPPDATA%\\Google\\Chrome\\...`(用户级安装的 Chrome),导致矢量导出
探测不到浏览器。这里统一定义,三处引用。
"""

import os
import shutil

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

SEVENZIP_PATHS = [
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
]

# Playwright 的 channel 名 → 候选路径(给 export_fallback / webhtml2vectoredit 用)
EXE_CANDIDATES = {
    "msedge": EDGE_PATHS,
    "chrome": CHROME_PATHS,
}


def find_edge() -> str:
    return next((p for p in EDGE_PATHS if os.path.isfile(p)), "")


def find_chrome() -> str:
    return next((p for p in CHROME_PATHS if os.path.isfile(p)), "")


def pick_channel() -> str:
    """返回 Playwright 可用的 channel:msedge / chrome;都没有返回空串。"""
    for channel, paths in EXE_CANDIDATES.items():
        if any(os.path.isfile(p) for p in paths):
            return channel
    return ""


def find_7z() -> str:
    for p in SEVENZIP_PATHS:
        if os.path.isfile(p):
            return p
    return shutil.which("7z") or ""
