# artboard 模式 H · H5 交互页(移动端落地页 / 互动页 / 邀请函 H5)

> **本册是"H5 交互页"的唯一真相源**。模式 H 与静态海报**井水不犯河水**:
> H5 是"页面"——可滚动、可触摸、可分页、可动;海报是"一屏即全部"(铁律 1)。
> **铁律 1 不适用于模式 H**;模式 H 遵守本册 §二 的 H5 铁律集(7 条)。

---

## 〇、边界:接什么,不接什么

| 维度 | 静态海报(默认) | 模式 W(公众号图文) | **模式 H(H5,本册)** |
|---|---|---|---|
| 产物 | PNG/JPG/… | 可粘贴的内联样式 HTML | **可运行的 HTML 页面** |
| 画布 | 固定尺寸 + overflow:hidden | 内容流 | **视口自适应** |
| 滚动 | 禁 | 允许 | **允许(核心)** |
| position:fixed | 禁 | 谨慎 | **允许** |
| 动效 | 海报循环/场景卡 | 内联 SVG+SMIL | **CSS 动画 / GSAP(vendored)/ 触摸驱动** |
| 导出 | Kiln 九格式 | 不走 Kiln | 不走 Kiln(可选出首屏截图/分享卡片) |
| 机检 | check_overflow | check_wechat_svg + check_mobile_width | **check_h5.py** |

**接**:轻量 H5 落地页 / 邀请函 / 报名页 / 长滚动叙事 / 一屏一页翻页 / 轻互动(抽奖转盘等)。
**不接**(维持"不适配"原判):**应用型**交互原型、SPA 路由、后端交互/数据请求、小程序、
需要真机 SDK 的能力(支付/分享签名——这类只留占位并标注"需后端配合")。

---

## 一、权威结论台账(标来源;置信度=高/中/待核验)

### 1.1 viewport(MDN `<meta name="viewport">`,2026-09 修订版)——置信度高

| 项 | 结论 |
|---|---|
| 基线写法 | `<meta name="viewport" content="width=device-width">` |
| `initial-scale=1` | **通常不必要**(MDN 明示);仅当溢出导致不想要缩放时才加 |
| 全屏沉浸 | `viewport-fit=cover` **必须**配 `env(safe-area-inset-*)`,否则内容落进刘海/圆角 |
| 虚拟键盘 | `interactive-widget=resizes-content` 让布局随键盘重排(**vw/vh 计算值随之变化** = 布局跳动根因) |
| **`user-scalable=no`** | **不采纳**(见 1.2) |
| maximum/minimum-scale | 同样可能被忽略,不作为设计手段 |

### 1.2 反模式声明:**不用 `user-scalable=no`**

1. MDN 明确**警告**:阻止低视力用户放大阅读;
2. WCAG(1.4.4 Resize Text)要求文本至少可放大 2×,最佳实践 5×;
3. iOS 10+ 与浏览器设置**本就可忽略**该属性 → 想锁缩放也锁不住,双重不合规。
   中文流行教程仍推荐此写法——**本项目不采纳**,机检直接 FAIL。

### 1.3 安全区(MDN + CSS Viewport 模块)——置信度高

```css
body{ padding-top: env(safe-area-inset-top); padding-right: env(safe-area-inset-right);
      padding-bottom: env(safe-area-inset-bottom); padding-left: env(safe-area-inset-left); }
.footer{ padding-bottom: env(safe-area-inset-bottom, 0px); }  /* 带回退值 */
```

- 仅 `viewport-fit=cover` 时 `env(...)` 才非零;
- **交互控件**(底部按钮/悬浮 CTA)必须避让 `safe-area-inset-bottom`,否则落进系统手势区。

### 1.4 触摸目标(WCAG 2.5.5 / 2.5.8 + 平台规范)——置信度高

| 来源 | 最小尺寸 | 等级 |
|---|---|---|
| WCAG 2.5.8 Target Size (Minimum) | **24×24** CSS px | AA |
| WCAG 2.5.5 Target Size (Enhanced) | **44×44** CSS px | AAA |
| Apple HIG | 44×44 pt | 平台推荐 |
| Material Design | 48×48 dp | 平台推荐 |

**项目口径**:主交互控件 **≥44×44**(取 AAA 线);次要/图标按钮 ≥24×24 且用间距补偿。

### 1.5 性能(Core Web Vitals 官方阈值)——置信度高;评估口径为 p75

| 指标 | Good | 需改进 | 差 |
|---|---|---|---|
| **LCP** 最大内容绘制 | ≤ 2.5s | 2.5–4.0s | > 4.0s |
| **INP** 交互到下一次绘制 | ≤ 200ms | 200–500ms | > 500ms |
| **CLS** 累计布局偏移 | ≤ 0.1 | 0.1–0.25 | > 0.25 |

本地验收 → 工程等效项见 §四(显式尺寸/内联关键 CSS/transform·opacity 动画)。

### 1.6 适配方案——置信度:中(实战口径;标"待核验"的不进铁律)

| 项 | 结论 | 置信度 |
|---|---|---|
| 设计稿基准 375px;1rem = 37.5px(或 scale×100 一套) | **同一项目只用一套 rem 基准**——混用 37.5 与 scale×100 两套 = 整体偏差 ≈2.67×(实战文自相矛盾点,引以为戒) | 中 |
| 1px 边框固定 px,不参与缩放 | 通用实践 | 中 |
| 点击延迟 | `width=device-width` 后现代浏览器已消除 300ms;需要时 `touch-action: manipulation` | **待核验** |
| iOS 滚动 `-webkit-overflow-scrolling: touch` | 实战口径 | 中 |
| 音频 | iOS 需用户手势触发一次;微信内需 JS-SDK | 中 |
| 图片 2x/3x;页面必须 HTTPS | 实战口径 | 中 |

### 1.7 待核验清单(实测前不进铁律;回填格式:`项 → 实测结论 + 日期`)

1. `touch-action: manipulation` 与 300ms 延迟的现代行为 —— **未实测**(本机为桌面环境;
   建议真机 iOS Safari + 微信 WebView 各验一次);
2. `interactive-widget` 在主流微信 WebView 的实际支持 —— **未实测**;
3. `safe-area-inset-*` 在微信 iOS WebView 的实测值 —— **未实测**(写法按 MDN,数值待真机);
4. rem 与 vw 混用的边界(1px / border-radius / 字号)—— **未实测**;
5. 微信内 H5 音频/视频自动播放策略当前状态 —— **未实测**。

---

## 二、H5 铁律集(7 条;仅模式 H 生效,替代铁律 1 的位置)

1. **viewport 基线**:必须有 `<meta name="viewport" content="width=device-width">`;**禁 `user-scalable=no`**;
2. **安全区**:用 `viewport-fit=cover` 时**必须**配 `env(safe-area-inset-*)` 保护内容与控件;
3. **触摸目标**:主交互 ≥44×44 CSS px;次要 ≥24×24 且间距补偿;
4. **性能**:达成 CWV 工程目标(LCP ≤2.5s / INP ≤200ms / CLS ≤0.1 的本地等效项,§四);
5. **离线优先**:零 CDN;第三方库 vendored(动画可用 `assets/vendor/gsap.min.js`);
6. **无障碍**:尊重 `prefers-reduced-motion`(有动画必配分支);图片有 `alt`;不禁缩放;
7. **降级**:能力缺失(音频/分享/震动)必须有可用回退,不白屏。

---

## 三、页面骨架与场景配方

骨架(可直接抄;含 viewport/安全区/触摸目标/防 CLS/reduced-motion 五要素)见
`assets/cases/h5-scroll-story.html` 与 `assets/cases/h5-form.html` 头部——两案例过 `check_h5.py`。

**rem 设置**:同一项目只用一套基准。方式 A(`1rem = scale×100`):

```js
const setRem = () => { document.documentElement.style.fontSize =
  (document.documentElement.clientWidth / 375 * 100) + 'px'; };
addEventListener('resize', setRem); setRem();
```

| 场景 | 骨架 | 动效 | 注意 |
|---|---|---|---|
| 单页长滚动叙事 | 区块堆叠 + `IntersectionObserver` 进场 | 淡入上移/视差 | 首屏图小;后续懒加载 |
| 整屏翻页 | `scroll-snap-type: y mandatory` | 页间过渡 | 给页码指示,禁"滚不动"错觉 |
| 交互卡片/表单 | 卡片 + 输入 | 焦点态/校验反馈 | 键盘遮挡 → `interactive-widget` + 聚焦滚动 |
| 轻游戏/抽奖 | Canvas 或 DOM | GSAP 时间线 | 触摸目标、INP 反馈 |

## 四、性能工程(CWV → 本地等效项)

| 目标 | 做法 |
|---|---|
| LCP ≤2.5s | 首屏关键 CSS 内联;首屏图 ≤100KB 且预加载;`font-display:swap` 或系统字体优先 |
| INP ≤200ms | 事件处理轻量;避免 >50ms 长任务;动画只动 transform/opacity |
| CLS ≤0.1 | **图片/视频显式宽高**;字体尺寸稳定;禁"内容插入式"跳动 |
| 体积 | 单文件首屏关键资源 ≤300KB(**工程取值**,按场景调整) |
| 图片 | WebP(`imageops convert --to webp`);`loading="lazy"`(首屏除外) |

## 五、微信内 H5 特殊项

| 项 | 结论 |
|---|---|
| 分享 | 需 JS-SDK + 后端签名 → **只留占位与说明**,不实现签名 |
| 音频 | iOS 需用户手势触发一次 → 给"点击开启音效"入口 |
| 调试 | vConsole 临时可引,但 CDN 有供应链风险 → 生产禁用或 vendored |
| 缓存 | 微信 WebView 缓存顽固 → 资源加版本号(`?v=`) |
| 主题 | 公众号内嵌 H5 可复用 `scripts/_gzh_theme.py` 主题源(与 11 迭代共用) |

## 六、机检与交付

```bash
python scripts/check_h5.py <页面.html|目录> [--min-touch 44] [--budget-kb 300]
```

8 项:viewport 合法性(含 user-scalable=no FAIL)/ cover 配 env / 零 CDN(FAIL)/
触摸目标(<24 FAIL、<44 WARN)/ 图片 alt 与显式尺寸(WARN)/ 100vh 误用(WARN)/
reduced-motion 分支(有动画时 FAIL)/ 体积预算(WARN)。**退出码 1 = 有 FAIL,挡过。**

交付自检 9 条:viewport 合法?cover 配 env?主交互 ≥44?CWV 等效项达标?零 CDN?
图有 alt 与尺寸?reduced-motion 分支?微信内音频手势入口与分享占位?`check_h5.py` 过?

## 七、参考案例

`assets/cases/h5-scroll-story.html`(长滚动叙事:IO 进场 + 锚点目录 + data-URI 图)、
`assets/cases/h5-form.html`(交互表单:44px+ 输入/按钮、原生校验)——
均过 `check_h5.py`(2026-09-26 机检记录:好 2 例 0 issues;坏样例 3 例见 `docs/samples/h5-bad/`)。

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `check_h5.py` | H5 机检(8 项) | `python scripts/check_h5.py page.html` |
| `pack.py` | H5 交付打包 | `python scripts/pack.py <slug>` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
