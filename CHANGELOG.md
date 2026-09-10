# Changelog

## v1.1.0 — 一致性收口

### Fixed
- export_local.py 补 import shutil(修复双击导出 NameError)
- make_bats 引用清理(已被 export_local.py 替代)
- 动效口径统一(guardrails/pipeline/SKILL 三处改"已启用")
- harmonyos-sans download.json 文件名修正(单文件可变字体)
- rollup 导出尺寸 11811→11812(同文件内部不一致)
- preflight WPI 缺失 FATAL→WARN(有 export_fallback 兜底)
- export.py from PIL 加 try/except(缺 Pillow 时 --cmyk 不裸 traceback)

### Changed
- guardrails.md 动画条目改为"已启用"
- pipeline.md 动效节标题去掉"禁用动画"
- scaffold --embed-fonts help 描述修正(联接非绝对路径)
- config.example.json 补 ocr_path(空串)

### Security
- preflight WPI 缺失不再 FATAL(可降级 export_fallback)
