# artboard 动效分册(M2:CSS 动画 → GIF/MP4)

> 理论核:迪士尼十二法则(Frank Thomas & Ollie Johnston《The Illusion of Life》)+
> Material Design 3 缓动/时长 token(m3.material.io,styles/motion),按「海报动图 / 视频场景卡」语境重写。
> 动画的本质是**时间与间距**,不是画得多。重量感是"演"出来的。

---

## 〇、先选模式:动图去往何处?

| | **模式 P · 海报循环**(默认) | **模式 S · 视频场景卡** | **模式 V · 视频动效件** |
|---|---|---|---|
| 产物去向 | 独立物料:动态海报/GIF/宣传图,循环播放 | 视频时间轨:与口播/实拍交替出现(信息卡/图解卡,如 cutflow 桥) | **整件交付:片头/片尾/概括/章节/转场**(多镜头,交 CutFlow 挂轨) |
| 时间轴 | 无缝循环 2–6s,**首帧=末帧** | **五段式一次性**:前置静置→入场→持住→出场→收尾静置 | **分镜表**:shot 间转场衔接,**每 shot 内仍守五段式** |
| 动画性质 | 可 `infinite`(但**静态版须另出有限版**,见 §一) | **全 finite**(禁 `infinite`;静态导出只取终态) | **全 finite**(同左) |
| 终态 | **静态版由"有限动画的合格终态"决定**;`infinite` 的静态相位不确定(§一) | 允许是"空卡"(内容已退场) | 末 shot 收尾静置收束 |
| 章节 | §一 – §七 | §八 – §十二 | **`video-motion.md`(独立分册)** |

判定:问一句"这个 MP4/GIF 是**独立循环看**(P)、**接在口播后面播**(S)、还是**一整件片头/片尾/概括/章节/转场**(V → `video-motion.md`)?"

> **X4 边界提示(此能力不做)**:视频剪辑/合成(多素材剪辑、转场、成片时间轨组装)不在 artboard 范围——那是 CutFlow 的领域;本册与 video-motion.md 只产出**插入视频轨的画面件**,不做剪辑。

---

## 一、时间轴规范与静态确定性(模式 P;Kiln 逐帧求值口径)

> 标【硬】= 违反即废;标【软】= 建议值。旧版整节写成"违反即废"(WPI 时代口径,v1.9 起消亡),
> 其中帧率早已不是强制项 —— v1.9 换 Kiln 后,约束面由 `scripts/export.py` 的参数面决定;
> 本节同时承载**静态导出**(PNG/JPG)的确定性规则(静态 ≠ 动画的求值口径,见下)。
> 章节号未变(§一–§七 仍是模式 P),外部引用按章号,不受本次改名影响。

- 【硬】**无缝循环**:首帧与末帧状态完全一致(`0%` 与 `100%` 关键帧相同),单循环 **2–6 秒**;
- 【软】总时长与帧率:`--max-wait` **默认 15 秒**(要更长须显式传;循环 2–6s 通常远够);
  帧率 `--fps` 是**普通整数、默认 25** —— `{10, 20, 25, 50}` 只是引擎/播放器**建议值**,
  **不再是硬约束**(`scripts/export.py:197`:`--fps` 为 `type=int, default=25`,**无 `choices`**;
  旧 WPI 的枚举限制随 v1.9 退役);
- 【硬】循环时长必须能被帧间隔整除:25fps 帧间隔 40ms → 循环取 **2.0s / 2.4s / 3.2s**(别用 2.1s 这种);
- 【硬】**静态版的确定性只来自"有限动画 + 合格终态",不来自 `infinite`**:静态导出(PNG/JPG)把
  **有限动画快进到终态**再截,而 `infinite` 动画不收敛、静态相位不确定(实测 2026-10-07:同一页
  连导三次相位 0.45s / 0.43s / 0.55s;依据见 `export.md` §已知行为)。二选一:
  ① 静态交付要确定性 → 交**有限版本**(收在终态),且**终态构图必须仍是一张合格海报**(静态版就是它);
  ② 网页/GIF/MP4 确实要无限循环 → 必须**另出一版有限静态图**当静态交付,或保证**任意相位**都合格
  (自检时抽 2–3 个相位各自看一遍);
- 【硬】只动 `transform` 和 `opacity`(可采样、不触发重排);**禁用** width/height/top/left 动画;
- 【硬】禁依赖交互/滚动/音频;`prefers-reduced-motion` 对导出无效,不用写。
- 【软】**捕获起点偏移 ≈1.0s**(GIF/MP4;实测 2026-10-07:**200–400px 页面 0.9–1.0s / 1080×1920 交叉验证 1.0–1.25s**):
  第一帧不是动画 0% 态,从 0s 起播的入场会被截掉前约 1s —— 循环型(P)通常无妨(主体靠循环表达),
  一次性入场型(S)必须给前置静置,见 §八(≈1.25s 时 ≥2.0s 静置仍留 ≥0.75s 余量)。

## 二、动画十二法则 × 海报动效(相关子集)

| 法则 | 海报动效映射 | 用法 |
|---|---|---|
| **9 时间与节奏** | 帧数=重量:重的东西慢、轻的东西快 | 价格牌入场 500ms,星星闪烁 1500ms |
| **6 缓入缓出** | 一切位移默认带缓动(见下表),匀速=死 | 除循环漂浮外,禁止 `linear` 做位移 |
| **2 预备动作** | 主动作前先反向一小步 | 价格数字落下前先向上抬 8px |
| **1 挤压拉伸** | 弹性落地,保持体积 | 促销词 scale 1→1.08→0.96→1 |
| **5 跟随与重叠** | 主体停了,装饰还在动;各部位不同步 | 主标停,角标迟 200ms 弹入 |
| **7 弧线运动** | 位移走弧线不走直线 | 元素飞入用 `translate` X/Y 组合而非单轴 |
| **3 舞台呈现** | 一屏一事 | 动的不超过 2 组元素,其余保持静止当背景 |

## 三、缓动 token(M3,直接抄进 CSS)

| token | cubic-bezier | 用途 |
|---|---|---|
| standard | `cubic-bezier(0.2, 0.0, 0.0, 1.0)` | 通用过渡 |
| decelerate(进场) | `cubic-bezier(0.0, 0.0, 0.0, 1.0)` | 元素入画 |
| accelerate(出场) | `cubic-bezier(0.3, 0.0, 1.0, 1.0)` | 元素离画 |
| emphasized | `cubic-bezier(0.4, 0.0, 0.2, 1)` | 大动作强调(M1/M2 经典) |
| linear | `linear` | 仅循环漂浮/淡入淡出/加载 |

**时长 token**:短 200ms(小元素反馈)/ 中 300ms(卡片入场)/ 长 500ms(主标/大位移)/
超长 700–1000ms(环境性漂移)。两条铁律:**面积越大时长越长;进场长、退场短**。

## 四、海报动效模式库(模式 P;循环前 0–1.5s 做完入场,之后进入循环)

| 模式 | 写法要点 |
|---|---|
| **入场序列** | 主标(0s,decelerate 500ms)→ 副标(150ms)→ 要点逐个(stagger 每项 delay +80–150ms,总量 ≤800ms)→ CTA 最后 |
| **价格弹跳** | 预备上移 → 落地 squash(stretch 不对称:`scale(1.06,0.9)`→`scale(0.96,1.04)`→1),体积守恒 |
| **循环漂浮** | 装饰元素 `translateY ±10px` 3s `ease-in-out` infinite alternate;每件周期错开(3s/4s/5s)避免同步抖动 |
| **呼吸强调** | CTA `scale 1↔1.04` 2s infinite——只给一个元素 |
| **光效流动** | 背景 mesh/光晕 `opacity 0.7↔1` 或 `background-position` 缓移,8s 慢循环 |
| **数字滚动** | 尽量不用——GIF 采样下易糊;用「数字翻牌落下」替代 |

## 五、CSS 实现规范

```css
/* 统一写法:变量控时长,fill-mode both 保证入场前隐藏 */
:root { --dur-in: .5s; --ease-in: cubic-bezier(0.0,0.0,0.0,1.0); }
@keyframes drop-in {
  0%   { transform: translateY(-40px); opacity: 0; }   /* 入场 */
  100% { transform: translateY(0);     opacity: 1; }
}
.hero-title { animation: drop-in var(--dur-in) var(--ease-in) both; }

/* 无缝循环示范:0% 与 100% 状态一致 */
@keyframes float-y {
  0%, 100% { transform: translateY(-10px); }
  50%      { transform: translateY(10px); }
}
.deco { animation: float-y 3.2s ease-in-out infinite; }  /* 3.2s = 25fps 的 80 帧 ✓ */
```

- 入场用 `both`(开始前保持 0% 态);循环用 `infinite`;
- stagger 用 `animation-delay: calc(var(--i) * 120ms)`;
- **终态 = 最佳静态画面**:静态导出把**有限动画快进到终态**再截,所以动画 case 的
  **终态构图必须完整**——入场动画结束后的静止画面就是静态版(实测 2026-10-07:
  `.box{animation:toBlue 2s linear forwards}` 导出为终态纯蓝、带 1s 延迟的同款动画同样出终态;
  依据见 `export.md` §已知行为)。
  **`infinite` 例外**:它不收敛,静态导出的相位不确定(同一次实测连导三次相位 0.45/0.43/0.55s)
  —— 静态交付请另出有限版(§一【硬】)。

## 六、导出命令

```bash
# GIF(无 ffmpeg 也可,Pillow 回退;有 ffmpeg 质量更佳)
python scripts/export.py --source <proj>/src --output <proj>/export/anim.gif \
  --width 1080 --scale 2 --height 1440 --format GIF --fps 25 --max-wait 6
# MP4(必须 ffmpeg)
python scripts/export.py --source <proj>/src --output <proj>/export/anim.mp4 \
  --width 1080 --scale 2 --height 1440 --format MP4 --fps 30 --max-wait 6
```

- `--max-wait` = **导出总长**(帧数 = `--fps` × `--max-wait`);循环 2–6s 的动画录 6s(含入场);
- **捕获起点在 CSS 时间轴 ≈1.0s 处**(实测 2026-10-07:200–400px 页面 0.9–1.0s /
  1080×1920 交叉验证 1.0–1.25s;GIF/MP4 同):从 0s 起播的入场,前约 1s 会被截掉。
  所以**动图主体靠循环表达**;入场要么给 ≥1s 的前置静置,要么只当锦上添花。
  > (WPI 时代机制,v1.9 起消亡)旧版此处写「录制从页面加载完成后才开始」并引"入场 1.2s 的案例,
  > 148 帧里全是循环态"——那是 WPI 实时采样时代(偏移 1.7–1.9s)的实测,数值与机制均已退役;
  > **偏移本身仍存在(≈1.0s)**,只是不再靠"录制"、而是逐帧求值时的固定起点;
- 无缝循环自检法:对相隔「一个循环帧数」的两帧做像素差,均值 ≈ 0 即无缝
  (实测 80 帧循环差 0.13,半周期差 2.35);
- GIF 是 256 色:深底细线/渐变可能带状化——深底动画优先 MP4,GIF 慎用高精度渐变。
- **卡点/节拍优先用 `linear`/`ease` 的连续动画**:`steps(1, end)` 这类硬跳变在 GIF 车道表现异常
  (2026-10-07 探针疑似不按关键帧走,待上游复核),需要硬切时先做 5 分钟小样探针或改走 MP4。

## 七、交付前自检(动图版;模式 P)

- [ ] 首尾帧一致(循环无缝,肉眼在 2 处循环点看不跳变)
- [ ] 每个位移都带缓动(除循环漂浮),入场用 decelerate
- [ ] 同屏动的不超过 2 组;stagger 总时长 ≤800ms
- [ ] 挤压拉伸保持体积;大动作前有预备动作
- [ ] 循环时长能被帧间隔整除;总长 ≤15s(**设计预算**:`--max-wait` 默认 15 秒、可超,不是引擎上限)
- [ ] 终态(静止画面)本身是一张合格海报——用**有限版本**验证(静态导出 = 快进到终态);
      若产物含 `infinite`,已另出有限静态版或已确认**任意相位**都合格
- [ ] **运动敏感(光敏安全)**:全片任一秒内"整幅画面明暗/颜色反转"≤3 次,禁高频频闪与满屏快速闪烁——高频闪烁有诱发光敏性癫痫反应的风险(WCAG 2.3.1「闪动 ≤3 次/秒」同口径),且信息流缩略预览里"闪"读作坏图;缓慢的元素级闪烁(星/灯)不受此限,受铁律 3 强调 ≤2 约束
- [ ] GIF 检查深底渐变有无带状;必要时换 MP4 或简化渐变

---

# 模式 S · 视频场景卡(口播桥:信息卡/图解卡/片头尾)

> 场景:产物插入视频时间轨,前接口播、后接口播。要解决的三件事:
> **入场被截**、**没有出场导致切换僵硬**、**画面不生动**。
> 现行导出机制(实测 2026-10-07,依据见 `export.md` §已知行为):
> - **GIF/MP4** = 逐帧求值 + 固定时长(帧数 = `--fps` × `--max-wait`);**捕获从 CSS 时间轴
>   ≈1.0s 处开始**(200–400px 0.9–1.0s / 1080×1920 1.0–1.25s),动画结束后的余帧冻结在终态;
> - **静态 PNG/JPG** = 把**有限动画快进到终态**再截,与时间轴起点无关。
> **所以时间轴两端仍要留静置段**——前置静置吸收起点偏移、收尾静置保证终态落定(ADR-0012)。

## 八、五段式时间轴契约(模式 S 硬规范,违反即废)

```
|-- 前置静置 P0 --|-- 入场 IN --|-- 持住 HOLD --|-- 出场 OUT --|-- 收尾静置 P1 --|
      ≥2.0s          0.5–0.8s     与口播句对齐      0.4–0.6s         ≥0.3s
     (空卡)        decelerate    (可含演进)      accelerate       (空卡)
```

- 【硬】**前置静置 ≥2.0s**:所有入场动画的 `animation-delay` 从 **2.0s 起算**(`--t0`)。
  理由(实测 2026-10-07):GIF/MP4 的**捕获从 CSS 时间轴 ≈1.0s 处开始**
  (**200–400px 页面 0.9–1.0s / 1080×1920 交叉验证 1.0–1.25s**;推导见 `export.md` §已知行为),
  入场若从 0s 起播,前约 1s 必被截;≥2.0s 的静置给足 ≥0.75s 余量(最坏值 1.25s 也够),
  被吃掉的是这段静置——片头呈现为"空卡一拍",正是镜头切换给观众的呼吸,不可感。
  > (WPI 时代机制,v1.9 起消亡)旧版把这段写成"WPI 从稳定点实时采样、比 0s 晚 1.7–1.9s
  > (1080×1920 四次 ffprobe 反推 + 时钟探针互证)、靠连续稳定帧 early_stop 提前停",
  > 并据此建议"页面侧无法重新对表"(监听 resize/scroll 把 `currentTime` 归零实测无效)、
  > "要根治需上游提供录制起点钩子(ADR-0012)"。**那些机制与 1.7–1.9s 的数值已随 Kiln 逐帧求值退役**;
  > 起点偏移本身仍在(≈1.0s),但页面侧只需**留静置**,不需要钩子。
- 【硬】**全 finite,禁 `infinite`**:Kiln 是**逐帧求值 + 固定时长**(`--max-wait` 即导出总长,
  不再有"提前停止录制"这一步),无限动画不会报错,但卡片到片尾也落不定 ——
  收尾静置与"终态 = 持住构图"都不成立。持住期的环境微动用**有限次数**
  (`animation-iteration-count: 2~3`),次数提前算好。
- 【硬】**微动的结束 ≤ 出场的结束**:算好 iteration 次数,别让环境元素
  在内容退场后独自留在空卡上漂(实测翻车点)。
- 【硬】**出场必须有**:口播→动画→口播不僵硬的关键在"出比进快"。
  无出场的卡片切回口播时像"画面突然消失",有出场则是"内容离开"。
- 【硬】**收尾静置 ≥0.3s**:有限动画落定后要留够收束帧,否则会截在动画半途
  (尾部余帧只是冻结在终态,不会替你补时间);同时给切回口播留半拍。
- 【默认】总时长对齐口播句:dwell ≥1.5s/13 字符(cutflow 字数纪律同源);
  导出 `--max-wait` = 五段总和 + 1.5s(帧数 = `--fps` × `--max-wait`)。
- 【默认】**导出长度不再被吃掉**:片长 = `--max-wait`;被"吃"的是**内容对齐**——开头 ≈1.0s 的
  动画进度被跳过、结尾多出的时间冻结在终态。所以旧口径"导出片长 ≈ 时间轴总长 − 1.8s(前置静置被吃)"
  已作废(cutflow 直接按 `--max-wait` 挂轨);旧口径"1080×1920 实际采样 ≈20fps(WPI 时代自适应采样)"
  同样作废:帧率就是 `--fps`(默认 25,`{10,20,25,50}` 只是建议值,见 §一)。

**时钟探针校准法**(备用:换画幅/换机器想自己复测起点偏移时用):页面加 rAF 时钟显示
"加载后秒数",导出后看首帧读数即真实起点,据此定 `--t0`。(WPI 时代用它反推 1.7–1.9s 的录制偏移,
实测样例"首帧读 1.70s,视频 1.5s 处读 3.35s";现行起点偏移 ≈1.0s(1080×1920 1.0–1.25s),
§八的 ≥2.0s 前置静置已留足余量,通常不必再测。)

```html
<div id="clk" style="position:fixed;left:20px;top:20px;z-index:99;
     font:700 44px monospace;color:#0f0;background:rgba(0,0,0,.6)">0.00</div>
<script>const t=performance.now(),e=document.getElementById('clk');
(function f(){e.textContent=((performance.now()-t)/1000).toFixed(2);requestAnimationFrame(f)})();</script>
```

## 九、入场 / 持住 / 出场 模式库(模式 S)

### 入场(IN;decelerate,叙事顺序 = 观看顺序)

| 模式 | 写法要点 |
|---|---|
| **骨架先行** | 容器/色块/底图 0ms 先落,给后续元素"垫背";纯元素飞入无骨架显得飘 |
| **标题逐行** | 标题每行一个 `<span class="tl">`,**断行=换色=stagger 三合一**(+80ms/行);断行规则见 typography-rules.md §一「标题语义断行」 |
| **图元 stagger** | 卡片/图标/图形逐个入(+80–120ms/个,总量 ≤800ms),弧线位移(X+Y 组合或 offset-path) |
| **强调压轴** | 关键词/数字/结论最后入,可带预备动作(反向 8px)或 spring overshoot ≤1.1 |
| **逐字弹入**(慎用) | 只用于 ≤6 字的口号召语;按字 span stagger 40ms,不得跨断行点 |

### 持住(HOLD;内容工作区,生动性主战场)

- 【硬】同屏动的不超过 2 组(同模式 P);环境微动 ≤1 组、有限次数。
- **信息演进**(教程核心):同一张卡逐态揭示(图解渐进构建,见 §十),
  不切卡——切卡交给口播,卡内演进交给动画。

### 出场(OUT;accelerate,三原则)

1. **比入场短**:0.4–0.6s,"进慢出快"是节奏感来源(M3 emphasized-accelerate)。
2. **方向延续**:从左入→向右出,从下入→向上出;阅读动线不折返,
   scale 入→scale 出则加深"推进-离开"的空间感。
3. **stagger 反序**:后进先出(强调元素最先退,骨架最后退)。

| 模式 | 写法要点 |
|---|---|
| **淡出+微缩**(默认) | `opacity→0` + `scale .97`;安全、百搭,配 accelerate |
| **反向滑出** | 入场位移的反向 + accelerate;与口播切点呼应"此话题讲完了" |
| **擦除收回** | `clip-path` 反向收回(幕布合上);图解卡连线的"倒画"归零 |
| **焦点收缩** | 配角元素先退,主角最后退并放大定格 0.2s 再退——结论型卡片用 |

## 十、生动性词汇表(科普/教程;每卡选 2–3 种,贪多必乱)

| 词汇 | 技术 | 要点 |
|---|---|---|
| **图解渐进构建** | stagger + `stroke-dashoffset` | 节点先落,连线"画出来"(SVG stroke 从满→0),结论最后落;一次只讲一步——科普动画的第一手法 |
| **逐词强调** | 关键词 span 高亮/描边 | 变强调色、画下划线(stroke)、微 pop(scale 1.06);一屏 ≤2 处 |
| **数字计数** | `@property` `<integer>` + counter | 纯 CSS count-up(Chromium 85+),`tabular-nums` 防抖动;时长 ≤1s,终值=文案数值 |
| **前后对比切换** | 卡内两态 | 态 A 快速退场(0.3s)→ 态 B 入场;"错→对 / 旧→新"省一次切卡,对比感强 |
| **聚光灯** | radial-gradient 遮罩移动 | 把"现在讲哪"照出来;遮罩容器整体 transform 位移,不动 mask 本身 |
| **推近 Ken Burns** | 静图 `scale 1→1.08` + 缓移 | 静图瞬间"活";8–12s 播一次(finite),配合讲解节奏 |
| **次要动作** | 环境回应主角(迪士尼第 8 法则) | 主角入场时,背景光斑/粒子轻微回应:幅度 ≤ 主角 1/3、迟 100–200ms |
| **夸张有度** | overshoot ≤1.1(第 10 法则的"度") | 科普/教程不是娱乐片:预备动作和回弹可以有,弹簧系数收着用 |

## 十一、可动属性白名单(扩容;分级护栏)

| 级 | 属性 | 成本 | 护栏 |
|---|---|---|---|
| L1 | `transform`、`opacity` | composite,零顾虑 | 随便用 |
| L2 | `clip-path`、SVG `stroke-dashoffset`、`@property` 注册的自定义属性(驱动渐变角/进度环/整数计数) | paint-only,不触发重排 | 每卡 ≤3 处 |
| L3 | `filter: blur/brightness/saturate` | 重渲染 | 同屏 ≤1 个;半径 ≤20px;元素 ≤40% 画布 |

- 【硬】仍然禁止:`width/height/top/left/margin`、字号、`box-shadow` 扩散——重排属性导致采样抖帧。
- 【硬】L2/L3 是为**生动性**开的口子,不是为炫技:能用 L1 表达就不升级。
- 浏览器(Edge/Chrome 常青版)均支持上述属性;`linear()` 缓动(Chromium 113+)可写真弹簧:
  `linear(0, 0.008, 3.1% 0.38, 8% 1.06, ... 1)`——从 ease-out 弹簧生成器取值,勿手搓。

## 十二、模式 S 实现骨架(整段可抄)

```css
/* 场景卡五段式:全 finite;--t0 吸收捕获起点偏移(ADR-0012;实测 2026-10-07 ≈1.0s,见 §八) */
:root {
  --t0: 2.0s;                          /* 前置静置 ≥2.0s */
  --in: .6s; --out: .5s;
  --hold: 4.8s;                        /* 持住=口播句长 - 入场 - 出场 */
  --ease-in:  cubic-bezier(0, 0, 0, 1);          /* M3 standard-decelerate */
  --ease-out: cubic-bezier(.3, 0, .8, .15);      /* M3 emphasized-accelerate */
}
@keyframes rise-in  { from { transform: translateY(28px); opacity: 0; }
                      to   { transform: none;         opacity: 1; } }
@keyframes rise-out { from { transform: none;            opacity: 1; }
                      to   { transform: translateY(-20px) scale(.97); opacity: 0; } }

.tl { display: block; }                /* 标题逐行 span:断行=换色=stagger 三合一 */

/* 【硬】入场与出场必须分属两层嵌套元素(外层 .si 入、内层 .so 出)。
   同一元素挂两条 animation(简写相叠或逗号列表)都错:同属性上后一场
   动画的 backwards fill 会覆盖前一场——出场 from(opacity:1)压住入场
   from(opacity:0),元素从 0s 起全程可见,即"没有入场、画面常驻"。 */
.si { display: block;
  animation: rise-in  var(--in)  var(--ease-in)  calc(var(--t0) + var(--i, 0) * 120ms) both; }
.so { display: block;
  animation: rise-out var(--out) var(--ease-out) calc(var(--t0) + var(--in) + var(--hold) + var(--i, 0) * 80ms) both; }

/* 持住期环境微动:有限次数,禁 infinite;结束须 ≤ 出场结束 */
.drift { animation: drift 1.8s ease-in-out 2 both; animation-delay: calc(var(--t0) + var(--in)); }
@keyframes drift { 0%,100% { transform: translateY(-6px); } 50% { transform: translateY(6px); } }

/* 【硬】安全区包裹层:所有内容必须放在 .safe 里,否则会被成片字幕/平台按钮盖住。
   数值与另两个画幅见 video-safe-area.md;装饰越界放 .bg 并加 data-allow-overflow。 */
.safe {
  position: absolute; left: 184px; right: 184px; top: 230px; bottom: 576px;
  display: flex; flex-direction: column; justify-content: center;
  /* 用 flex 居中,不要在里面再用 top:/bottom: 绝对定位贴边——那会跑回安全区外 */
}
```

```html
<div class="poster">
  <div class="bg" data-allow-overflow><!-- 装饰层:可越界,透明度 ≤.5 --></div>
  <div class="safe"><!-- 内容层:一切内容都在这层里 -->
    <h2>
      <span class="tl si" style="--i:0"><span class="tl so" style="--i:0; color:var(--c-ink)">店群运营</span></span>
      <span class="tl si" style="--i:1"><span class="tl tl-accent so" style="--i:1; color:var(--c-accent)">被认定为拆分收入</span></span>
    </h2>
  </div>
</div>
```

导出(S 卡一律 MP4;深底渐变 GIF 会带状化):

```bash
python scripts/export.py --source <proj>/src --output <proj>/export/scene.mp4 \
  --width 1080 --height 1920 --format MP4 --fps 25 --max-wait 9
# --max-wait = 五段总和 + 1.5s;片长 = fps × max-wait(开头 ≈1.0s 是捕获起点偏移,见 §八)
```

- **需要静态版**(封面/缩略图)时:复制 index.html 为 `index_static.html`,
  删掉 `.so` 的引用(终态=持住构图)再导 PNG——S 卡直接导 PNG 会得到**空卡**,
  因为静态导出 = 快进到有限动画的终态,而 S 卡的终态正是"出场之后"的空态
  (实测机制见 `export.md` §已知行为)。

## 十三、交付前自检(场景卡版;模式 S)

- [ ] 抽帧验证 3 点:入场完整在片、出场完整在片、首尾静置干净
      (`ffmpeg -i scene.mp4 -vf "select='eq(n,0)+eq(n,mid)+eq(n,last)'"` 抽看)
- [ ] 全 finite:无任何 `infinite`;微动均为有限次数且算入总时长
- [ ] 五段齐备:前置静置 ≥2.0s / 入场 0.5–0.8s / 出场 0.4–0.6s / 收尾 ≥0.3s
- [ ] 入场+出场分属**两层嵌套元素**(外入内出;同元素双动画会让元素从 0s 起常驻,§十二)
- [ ] 文字:标题逐行 span 制,断点无词被劈(见 typography-rules.md §一「标题语义断行」);
      卡片文字 ≤3 组元素、单行 ≤14 字、dwell ≥1.5s/13 字符
- [ ] **内容全部落在视频安全区内**(细则见 `video-safe-area.md`):9:16 左/右 **184px** /
      顶部 **230px** / 底部 **576px**;16:9 与 3:4 换用各画幅数值。
      最容易漏的是**左右 184px**(平台按钮列)——"logo 放右下""落款贴边"必中
- [ ] 卡片本身不越框(`card-layout.md`):`.card` 用 `min-height`、无定高、文案超长已 `line-clamp`
- [ ] **跑过机检门禁**:`scripts/check_overflow.py <proj>/src --safe-area auto` → `ok:true`
      (A/B 类查容器越框,C 类查越出安全区;每次重导前必跑,见 `pipeline.md` Step 6.0)
- [ ] L2 ≤3 处、L3 同屏 ≤1 个;同屏动 ≤2 组
- [ ] **运动敏感(光敏安全)**:任一秒内整幅明暗反转 ≤3 次,禁高频频闪(模式 P 同口径,理由见 §七——
      场景卡会在视频里被成片播放,光敏风险随播放时长放大)
- [ ] 需要静态版的卡,已另出 index_static.html → PNG(不是直接导动画卡的 PNG)
- [ ] **减弱动效(06-A)**:同一 HTML 若还会以网页形式出现,必须带 `prefers-reduced-motion: reduce` 分支(降级为淡入淡出;纯导出产物不受此设置影响,依据 Apple HIG《Motion》)

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `export.py` | GIF/MP4 导出 | `python scripts/export.py … --format MP4 --fps 25` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
