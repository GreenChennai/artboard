# ADR 0005:文字特效必须通过导出安全审查才能入册

日期:2026-09-06 · 状态:已采纳

## 背景

CSS 字效在浏览器里好看 ≠ 无头截图导出后还原。实测坑:backdrop-filter 无头不渲染、
透明填充字的 text-shadow 会透底毁掉渐变、glitch 动画默认态截出来是普通字。

## 决策

effects/title-fx 收录的每条配方必须标注导出安全性;三条硬禁令:
①禁 backdrop-filter(改预模糊图+色块);②透明填充字禁 text-shadow
(用 drop-shadow 或伪元素分层);③glitch/flicker 的"瞬态"写死为默认态。

## 后果

特效库全部"截图即所得";新特效入册前须无头渲染验证一次。
