"""artboard-mcp:取图通道薄壳(判定表 + 搜索/下载复用 fetch_asset.py + Bridge + 查重)。

单一真相源约定(ADR-AB-E03):本包只做入口包装,不复制取图实现;
sources.py 经 import 复用 scripts/fetch_asset.py,dedupe.py 经 import 复用
scripts/_img_probe.py 的 pHash。fetch_asset.py 改行为,MCP 自动跟随。
"""

__version__ = "0.1.0"
