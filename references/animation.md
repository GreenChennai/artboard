# artboard 动效分册(M2:CSS 动画 → GIF/MP4)

> 理论核:迪士尼十二法则(Frank Thomas & Ollie Johnston《The Illusion of Life》)+
> Material Design 3 缓动/时长 token,按「海报动图」语境重写。
> 动画的本质是**时间与间距**,不是画得多。重量感是"演"出来的。

---

## 一、硬性时间轴规范(WPI 采样约束,违反即废)

- **无缝循环**:首帧与末帧状态完全一致(`0%` 与 `100%` 关键帧相同),单循环 **2–6 秒**;
- 总录制时长 **≤15 秒**(WPI 上限);帧率 `--fps` ∈ {10, 20, 25, 50},**默认 25**;
- 循环时长必须能被帧间隔整除:25fps 帧间隔 40ms → 循环取 **2.0s / 2.4s / 3.2s**(别用 2.1s 这种);
- 只动 `transform` 和 `opacity`(可采样、不触发重排);**禁用** width/height/top/left 动画;
- 禁依赖交互/滚动/音频;`prefers-reduced-motion` 对导出无效,不用写。

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

## 四、海报动效模式库(循环前 0–1.5s 做完入场,之后进入循环)

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
- **终态 = 最佳静态画面**:WPI 导 PNG 会把动画收敛到终态,动画 case 必须保证
  终态构图完整(入场动画结束后的静止画面就是静态版)。

## 六、导出命令

```bash
# GIF(无 ffmpeg 也可,Pillow 回退;有 ffmpeg 质量更佳)
python scripts/export.py --source <proj>/src --output <proj>/export/anim.gif \
  --width 1080 --scale 2 --height 1440 --format GIF --fps 25 --max-wait 6
# MP4(必须 ffmpeg)
python scripts/export.py --source <proj>/src --output <proj>/export/anim.mp4 \
  --width 1080 --scale 2 --height 1440 --format MP4 --fps 30 --max-wait 6
```

- `--max-wait` = 录制秒数;循环 2–6s 的动画录 6s(含入场);
- **录制从页面加载完成后才开始**——入场动画很可能被错过。实测:入场 1.2s 的案例,
  148 帧里全是循环态。所以**动图主体靠循环表达,入场只锦上添花**;
- 无缝循环自检法:对相隔「一个循环帧数」的两帧做像素差,均值 ≈ 0 即无缝
  (实测 80 帧循环差 0.13,半周期差 2.35);
- GIF 是 256 色:深底细线/渐变可能带状化——深底动画优先 MP4,GIF 慎用高精度渐变。

## 七、交付前自检(动图版)

- [ ] 首尾帧一致(循环无缝,肉眼在 2 处循环点看不跳变)
- [ ] 每个位移都带缓动(除循环漂浮),入场用 decelerate
- [ ] 同屏动的不超过 2 组;stagger 总时长 ≤800ms
- [ ] 挤压拉伸保持体积;大动作前有预备动作
- [ ] 循环时长能被帧间隔整除;总长 ≤15s
- [ ] 终态(静止画面)本身是一张合格海报
- [ ] GIF 检查深底渐变有无带状;必要时换 MP4 或简化渐变
