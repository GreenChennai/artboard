"""artboard 字体登记:把 fonts/<目录> 注册进字体总目录 fonts/README.md。

用法:
  python add_font.py <字体目录名> [--name 显示名] [--category 分类]
                     [--tags 气质关键词,逗号分隔] [--weights 字重说明] [--note 备注]

约定:每个字体目录 = 字体文件(ttf/otf/woff2…) + INTRO.md(简介)。
本脚本负责:校验字体文件存在 → 缺 INTRO.md 则生成模板 → 在 README.md 总表追加一行。
已存在的同名行不会重复追加(提示手动更新)。
"""

import argparse
import datetime
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(SKILL_DIR, "fonts")
FONT_EXTS = (".ttf", ".otf", ".woff", ".woff2", ".ttc", ".otc")

INTRO_TEMPLATE = """# {name}

| 属性 | 值 |
|---|---|
| 字体文件 | {files} |
| 字重/变体 | {weights} |
| 分类 | {category} |
| 气质关键词 | {tags} |
| 协议/来源 | (待补:OFL / 免费商用 / 来源地址) |

## 气质描述
(待补:这款字体什么调性?锋利/圆润/文艺/机械?写 2-3 句。)

## 适用
(待补:什么风格、什么位置用它在行?标题/正文/数字?)

## 慎用
(待补:什么场景会翻车?正文小字?全大写?)

## 示例句
「{sample}」
"""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("folder", help="fonts/ 下的字体目录名")
    p.add_argument("--name", default=None)
    p.add_argument("--category", default="未分类")
    p.add_argument("--tags", default="", help="逗号分隔气质关键词")
    p.add_argument("--weights", default="见字体文件")
    p.add_argument("--note", default="")
    args = p.parse_args()

    folder = os.path.join(FONTS_DIR, args.folder)
    if not os.path.isdir(folder):
        print(f"✗ 目录不存在: {folder}")
        return 1
    fonts = [f for f in os.listdir(folder) if f.lower().endswith(FONT_EXTS)]
    if not fonts:
        print(f"✗ {args.folder}/ 中没有字体文件 ({', '.join(FONT_EXTS)})")
        return 1

    name = args.name or args.folder
    files = ", ".join(fonts)
    intro = os.path.join(folder, "INTRO.md")
    if not os.path.isfile(intro):
        with open(intro, "w", encoding="utf-8") as f:
            f.write(INTRO_TEMPLATE.format(
                name=name, files=files, weights=args.weights,
                category=args.category, tags=args.tags or "(待补)",
                sample="海内存知己,天涯若比邻 0123456789"))
        print(f"✓ 生成简介模板: {os.path.relpath(intro, SKILL_DIR)}(请补全待补项)")

    readme = os.path.join(FONTS_DIR, "README.md")
    line = (f"| [{args.folder}](INTRO_PLACEHOLDER) | {name} | {args.category} "
            f"| {args.tags} | {args.weights or files} |")
    # 目录链接统一指向目录内 INTRO.md
    line = line.replace("(INTRO_PLACEHOLDER)", f"{args.folder}/INTRO.md")
    if os.path.isfile(readme):
        with open(readme, encoding="utf-8") as f:
            content = f.read()
        if f"]({args.folder}/INTRO.md)" in content or f"| {args.folder} |" in content:
            print(f"△ README.md 已有 {args.folder} 的条目,未重复追加")
            return 0
        content = content.rstrip("\n") + "\n" + line + "\n"
        with open(readme, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(readme, "w", encoding="utf-8") as f:
            f.write(README_HEADER + line + "\n")
    print(f"✓ 已登记进 fonts/README.md: {name}")
    if args.note:
        print(f"  备注: {args.note}")
    print(f"  ({datetime.date.today().isoformat()})")
    return 0


README_HEADER = """# artboard 字体库总目录

> 两级筛查法:先按「分类」选定大类 → 点进对应 `<目录>/INTRO.md` 细读气质与适用场景 → 定稿 ≤3 款(标题/正文/数字各司其职)。
> 新增字体:建目录放字体文件 + INTRO.md,然后跑 `scripts/add_font.py <目录名> --name 显示名 --category 分类 --tags 关键词`。

| 目录 | 字体 | 分类 | 气质关键词 | 字重/变体 |
|---|---|---|---|---|
"""


if __name__ == "__main__":
    sys.exit(main())
