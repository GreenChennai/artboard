# 品类规范 · 三折页(trifold)

> 介质品类:A4 横 297×210mm,包心折(信封折)三等分。**单面 = 一个画布,共两个画布(正面/背面)。**

## 画布与导出
- 每面画布 **1754×1240**(150dpi 设计稿),`--scale 2` → 3508×2480 = 300dpi。
- **折线位置:x = 585px 与 x = 1169px**(三等分)。每栏内容安全边距 40px,**文字禁止跨折线**。
- 跨栏大图慎用:图横跨折线会被折痕切断,必须跨时把主体放在单栏内。

## 栏位映射(包心折,交付前建议按打印店模板核对)
```
正面画布(左→右):  [内页一 | 内页二(主内页) | 内页三(折口页)]
背面画布(左→右):  [内页三背面 | 封底(联系方式) | 封面]
```
- 阅读顺序:封面(背面右栏)→ 翻开见正面左栏(内页一)→ 内页二 → 内页三(折口)。
- 不同厂家/折法(Z 折)栏位顺序不同——正式印刷前拿店家模板核对一次。

## 工作流
1. `scaffold.py <slug> --size trifold` 建项目(默认 index.html = 正面画布)。
2. `cp index.html back.html` 做背面画布(注意背面从"内页三背面"开始排)。
3. 分别导出:`--source <proj>/src --output export/front.png`(index.html 为入口);
   背面用 `--source <proj>/src/back.html` 指定文件导出 back.png。
4. 合双面 PDF(**`Image.init()` 不能省**,否则 Pillow 找不到 JPEG 编码器):
   `python -c "from PIL import Image; Image.init(); a=Image.open('export/front.png'); b=Image.open('export/back.png'); a.save('export/<slug>.pdf', save_all=True, append_images=[b], resolution=300)"`

## 字号阶(1754 宽画布)
封面主标 110–150px / 栏内标题 44–56px / 正文 26–30px / 封底联系方式 26–32px / 页脚 20px。

## 参考案例
[assets/cases/trifold-case.html](../../assets/cases/trifold-case.html) · 双面:[trifold-case-back.html](../../assets/cases/trifold-case-back.html)

### 二维码
设计稿放「二维码占位」框即可;终稿前 `python scripts/qr.py generate --data "…" --out src/img/qr.png`(支持品牌色/内嵌 logo,H 级纠错)替换,重导。码宽 ≥ 版面宽 8%,四周留白 ≥1 模块;解析用 `qr.py decode <图>`(本地 zxing,离线),公网图片可走草料 API `read-qr-code`。

## 调性禁则
1. 封面只放:logo + 主标 + 一句副标,禁止把内页内容挤上封面。
2. 文字/关键图形禁跨折线;每栏独立成篇。
3. 三个内页用一个视觉母题串联(同一套 tokens/同一装饰语言),禁止一栏一个风格。
4. 封底信息层:联系方式 + 二维码(≥160px)+ 地址,一层排完。
