"""artboard 共享配置读取:环境变量 > config.json > 默认值。

用法(其他脚本):
    from _config import cfg
    wpi = cfg("wpi_path")           # 默认值已在各脚本内给定
    key = cfg("pexels_key")
"""

import json
import os

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

# 配置键 → 环境变量(环境变量优先,便于临时覆盖)
ENV_MAP = {
    "wpi_path": "ARTBOARD_WPI",
    "studio_dir": "ARTBOARD_STUDIO",
    "ffmpeg": "ARTBOARD_FFMPEG",
    "pexels_key": "ARTBOARD_PEXELS_KEY",
    "pixabay_key": "ARTBOARD_PIXABAY_KEY",
    "huaban_cookie": "HUABAN_COOKIE",
    "iconfont_cookie": "ARTBOARD_ICONFONT_COOKIE",
    "pinterest_cookie": "ARTBOARD_PINTEREST_COOKIE",
    "proxy": "ARTBOARD_PROXY",
    "vqa_path": "ARTBOARD_VQA",
}

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def cfg(key: str, default: str = "") -> str:
    env = os.environ.get(ENV_MAP.get(key, ""))
    if env:
        return env
    v = _load().get(key)
    return v if isinstance(v, str) and v else default
