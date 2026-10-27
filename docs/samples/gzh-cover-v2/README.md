# 双封面 v1.26 样张:同一句文案,改前 vs 改后

两页都由 `scripts/gzh_cover.py new` 真实渲染,画布同为 900×383,主标同为「秋日新品发布」(6 字),字体、主题(ink)、版式(center-band)一致。唯一变量是 v1.26 的字号引擎与外层背景层。

| 文件 | 版本 | 主标字号 | 色带宽度 | 背景层 |
|---|---|---|---|---|
| `before.html` | v1.25(HEAD) | 54px | 383px | 无 |
| `after.html` | v1.26 | **96px** | 383px(标题越界到 720 授权区) | dots-grid |

主标字高占画布从 14% 提到 25%,与 18 张参考的中位 20% 同档;标题不再被 383 安全区锁死。

复现方式(输出到临时目录,不写回仓库):

```bash
python scripts/gzh_cover.py new /tmp/sample-new --title '秋日新品发布' \
    --layout center-band --bg-recipe dots-grid --force
```

两页 `check_slop.py` 均为 0 发现(0 P0 / 0 P1 / 0 P2);该工具查排版通病,不替代字号核验,字号以上表为准。
