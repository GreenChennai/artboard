# 品类规范 · 名片(card)

> 介质品类:视觉风格仍从风格清单选(科技 KV 极简风/暖纸编辑风最常用)。品类规范只管尺寸、字号下限与印刷纪律。

## 画布与导出
- 成品 **90×54mm**,画布 1063×638(300dpi),**导出 `--scale 1`**(即为印刷分辨率)。
- 双面名片:建两个 HTML(`index.html`/`back.html`)分别导出,交付两图;需要合 PDF 用 Pillow:
  `python -c "from PIL import Image; a=Image.open('front.png'); b=Image.open('back.png'); a.save('card.pdf', save_all=True, append_images=[b], resolution=300)"`
- 出血:数码/普通印刷店按成品尺寸收文件;要求 3mm 出血的店,把背景色块外扩后告知店家"裁切按 90×54"。
- 安全边距 **4mm ≈ 47px**,所有文字/二维码不得越线。

## 字号阶(1063 宽画布,下限即印刷可读底线)
| 元素 | 字号 | 说明 |
|---|---|---|
| 姓名 | 64–76px | 12–14pt |
| 职位/头衔 | 32–36px | |
| 电话/邮箱/地址 | 28–32px | **≥7pt(33px)为印刷可读底线,禁止再小** |
| logo 高 | 90–140px | |
| 二维码 | ≥ 177×177px(15mm) | 留白 ≥ 24px |

## 版式原型
- **左分区**:左 40% 色块/logo 区 + 右 60% 信息区(最稳)。
- **底对齐**:全部信息沉底,上 2/3 留白放 logo(高级感)。
- **居中仪式感**:居中排版,适合极简风。

### 二维码
设计稿放「二维码占位」框即可;终稿前 `python scripts/qr.py generate --data "…" --out src/img/qr.png`(支持品牌色/内嵌 logo,H 级纠错)替换,重导。码宽 ≥ 版面宽 8%,四周留白 ≥1 模块;解析用 `qr.py decode <图>`(本地 zxing,离线),公网图片可走草料 API `read-qr-code`。

## 参考案例
[assets/cases/card-case.html](../../assets/cases/card-case.html) · 双面:[card-case-back.html](../../assets/cases/card-case-back.html)

## 调性禁则
1. 字体 ≤2 款;整卡元素 ≤5 组(姓名/职位/联系方式/logo/二维码)。
2. 禁 7pt 以下任何文字;禁满铺重底纹压字。
3. 信息一层排完,禁止折行超过 1 次。
4. 深底卡注意文字对比度 ≥4.5:1(烫金/UV 工艺另议,设计稿按对比度做)。
