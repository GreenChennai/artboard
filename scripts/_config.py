"""artboard 共享配置读取与写入:环境变量 > config.json > 默认值。

用法(其他脚本):
    from _config import cfg, write_config, near_workspace
    kiln = cfg("kiln_cli_exe", near_workspace(os.path.join("VellumBench", "dist")))
    key = cfg("pexels_key")
    write_config({"kiln_cli_exe": r"D:\\WPI"})     # 原子写,自动合并
"""

import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

# 工作区根:技能装在 <ws>/.agents/skills/artboard 时即 <ws>。
# 用于替代此前硬编码的作者机器绝对路径(E:\\平日资料\\GitHub\\…)。
# 只有未配置时才用到,正式环境请显式写 config.json。
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))


def near_workspace(name: str) -> str:
    """工作区根下的兄弟目录,作为未配置时的默认落点。"""
    return os.path.join(WORKSPACE, name)


# 配置键 → 环境变量(环境变量优先,便于临时覆盖)
ENV_MAP = {
    "kiln_cli_exe": "ARTBOARD_KILN_CLI",
    "studio_dir": "ARTBOARD_STUDIO",
    "ffmpeg": "ARTBOARD_FFMPEG",
    "pexels_key": "ARTBOARD_PEXELS_KEY",
    "pixabay_key": "ARTBOARD_PIXABAY_KEY",
    "huaban_cookie": "HUABAN_COOKIE",
    "iconfont_cookie": "ARTBOARD_ICONFONT_COOKIE",
    "pinterest_cookie": "ARTBOARD_PINTEREST_COOKIE",
    "proxy": "ARTBOARD_PROXY",
    "vision_mode": "ARTBOARD_VISION_MODE",
    "vqa_path": "ARTBOARD_VQA",
    "ocr_path": "ARTBOARD_OCR",
}

_cache: dict | None = None
_bad_config: str | None = None


def _load() -> dict:
    global _cache, _bad_config
    if _cache is None:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except FileNotFoundError:
            _cache = {}                     # 还没建 config.json:正常,走默认值
        except json.JSONDecodeError as exc:
            _cache = {}
            _bad_config = f"第 {exc.lineno} 行第 {exc.colno} 列: {exc.msg}"
            print(f"[FATAL] config.json 解析失败({_bad_config})\n"
                  f"        路径: {CONFIG_PATH}\n"
                  f"        已按全部默认值运行,请修正后重试。", file=sys.stderr)
        except OSError as exc:
            _cache = {}
            print(f"[WARN] config.json 读取失败: {exc}(按默认值运行)",
                  file=sys.stderr)
    return _cache


def config_error() -> str:
    """config.json 的解析错误(供 preflight 上报);无错误返回空串。"""
    _load()
    return _bad_config or ""


def cfg(key: str, default: str = "") -> str:
    env = os.environ.get(ENV_MAP.get(key, ""))
    if env:
        return env
    v = _load().get(key)
    return v if isinstance(v, str) and v else default


def cfg_raw(key: str, default=None):
    """取原始值(不强制转 str),给 bool/int 类配置用。"""
    env = os.environ.get(ENV_MAP.get(key, ""))
    if env:
        return env
    v = _load().get(key)
    return default if v is None else v


def write_config(data: dict, path: str = "") -> str:
    """原子写配置:先写 .tmp 再 os.replace,避免写一半崩溃留下截断的 config.json。
    传入的键与已有配置**合并**(不整体覆盖),返回实际写入路径。
    写完后失效读缓存,同进程内后续 cfg() 立即可见。"""
    global _cache
    target = os.path.abspath(path or CONFIG_PATH)
    merged: dict = {}
    if os.path.isfile(target):
        try:
            with open(target, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                merged = loaded
        except (OSError, ValueError):
            merged = {}
    merged.update(data)
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    _cache = None
    return target
