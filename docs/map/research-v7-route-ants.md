# v7 调研报告:彗星寻路与蚂蚁线升级(GitHub / 开源轮子 + 落地方案)

> 日期:2026-09-29 · 前置:`docs/map/research-traffic-algorithms.md`(v7 选型调研)+ `ADR-0008`(走廊图+IDM,已采纳未落地)。
> 本文 = ①现状代码级 review(找出"不及预期"的根因)→ ②开源轮子调研(4 路并行,license/体积/源码已实测核验)→ ③v7 设计方案 → ④验收标准。

---

## 一、现状 Review(代码级根因分析)

基线:`assets/map/demo/map-player.template.html` v6.1(1188 行),构建 `scripts/build_player.py`(模板内联 SVG/routes.json)。
数据规模:798 条路段(secondary 251 / service 181 / tertiary 125 / trunk 73 / primary 65 / 其余 ~103),
548 条带 oneway 标记,234 个不同路名;车流池(≥220px)约 240 段。

### 1.1 蚂蚁线(fx.pulse)——一根真 bug + 三个观感/性能问题

| # | 问题 | 根因(代码位置) | 影响 |
|---|---|---|---|
| A1 | **过弯甩出/切角** | "三点折叠"实为**沿切向直线回退**:`m2/t2 = sm[0] - sm[2]*stp*0.45`(第 804-806 行),中尾两点不在路上——README 7.1 宣称"三点沿路采样"与实现不符 | 弯道处蚂蚁中后段飘到路外,缩放越大越明显 |
| A2 | 观感是"小彗星群"不是"流光带" | 每蚁 = 2 段描边 + 发光精灵 + 白芯点,彼此独立;业界蚂蚁线(Mapbox ant-path / Leaflet.AntPath)是**虚线相位流动** | 密集时像噪点,不"淡雅" |
| A3 | 蚂蚁在路段端点原地循环 | `(k*spacing + phase) % len2` 单路内回绕 | 长街被路口切碎,光带断续(与车流连续行驶形成反差) |
| A4 | 性能脆弱 | 预算 1500 蚁 × (save/restore + 2 stroke + drawImage + arc) ≈ 6000+ canvas 调用/帧 | 软渲染/低端机掉帧;全开叠加时波动 |

### 1.2 彗星车流(彗星寻路主体)——无图结构的结构性缺陷

| # | 问题 | 根因 | 影响 |
|---|---|---|---|
| C1 | **路口漂移/匹配错误的残余案例** | `buildRoute` 逐跳对全池(~240 段×2 向)线性扫描几何打分,无预建图;`corridorClear` 逐 AABB×11 采样现场算 | 每次出生重复 O(60×480×11) 计算;启发式在分离车道+丁字+平行路叠加场景仍会选错 |
| C2 | 桥占比过高(552 桥/907 链 ≈ 38%) | 走廊没有在**加载期**缝合,几乎每个路口都靠贝塞尔曲桥跨缺口 | 车辆大量时间行驶在"合成曲线"上;桥长闸门内的错误匹配照飞 |
| C3 | 无交通动力学:恒速、无跟驰、无转弯减速 | `pos += s*dt`,`SPD` 按等级定速 | 车与车互不相干,"萤火虫"感;排队/疏密涌现全无 |
| C4 | 路线寿命不可控 | 随机游走 60 跳封顶;死头/无续接 → fade 重生 | 中途消失-闪现感 |
| C5 | 出口识别只看 12px 贴边 | `__EXIT_POOL` 端点贴边判定 | 不贴边的边界路没有出口流 |

### 1.3 寻路动画 A→B(fx.route)——观感差距

| # | 问题 | 根因 |
|---|---|---|
| R1 | 折线硬角、像 PPT 路径动画 | routes.json 已 DP 1.2px 简化(37/59 点),播放时直线连折点,转角无圆滑 |
| R2 | 节奏单一 | 全程 easeInOutQuad 一把梭(RDUR 4200ms),启动-巡航-到达无速度层次 |
| R3 | 完成即静止 | 画完只剩静态线,无"能量流"延续;RHOLD 后硬切重来 |
| R4 | 头部箭头生硬 | 三角箭头 + 6 个圆形 glow,无彗尾 ribbon |

### 1.4 结论

v6.2→6.12 十轮补丁证明:**逐路口现场几何推断已到天花板**。ADR-0008 判断正确——必须加载期建图
(走廊合并),行为模型上 IDM。蚂蚁线需要"沿真实路径几何"的重写 + 配方升级,寻路 A→B 需要
平滑+节奏+尾迹的观感重做。以下调研为这三件事找轮子。

---

## 二、开源轮子调研(4 路并行,均已核验 license/体积/源码)

### 2.1 路网拓扑

| 轮子 | 出处 / License | 核心思想 | 采纳 |
|---|---|---|---|
| **OSMnx `simplify_graph` + `consolidate_intersections`** | [gboeing/osmnx](https://github.com/gboeing/osmnx) · MIT · 算法论文 Boeing 2025 (DOI 10.1111/tgis.70037) | ① endpoint 五规则消假节点;② 路口聚类七步:buffer 聚类(容差=缓冲半径,20-90px 节点簇 → tolerance 30-45px)→ 簇内弱连通分量拆分 → 质心为新节点 → 边几何向质心缝合 → 有向边保留 oneway。**无成熟 JS 移植;800 段规模用网格桶+并查集 ~150 行直译** | ✅ 移植直译 |
| **osm2streets(A/B Street 生态)** | [a-b-street/osm2streets](https://github.com/a-b-street/osm2streets) · Apache-2.0 · [npm osm2streets-js](https://www.npmjs.com/package/osm2streets-js) ~1.93MB WASM | 变换管线思想:CollapseDegenerateIntersections(度2缝合)/ **MergeDualCarriageways**(分离车道合并走廊)/ CollapseShortRoads;路口内部 = 修剪(trim)→路口多边形→movement 表(入口→出口显式转向) | ✅ 思想(movement 表 = 图邻接;WASM 不引) |
| **地图匹配 Valhalla Meili / OSRM / Newson-Krumm HMM** | [valhalla](https://github.com/valhalla/valhalla) MIT · [OSRM](https://github.com/Project-OSRM/osrm-backend) BSD-2 | 表示层三戒律:**状态=(边, 弧长, 方向)**,不存在自由点;后继只走图上合法转移;过近点内插不参与定位 → 漂移/瞬移在表示层被消灭 | ✅ 表示层采纳 |
| JS 图库(ngraph.path / graphology) | MIT,0 依赖 UMD | 专为十万+边;800 段手写 60 行 Dijkstra/A* 就够 | ❌ 不引(抽象错位) |
| simplify-js / Chaikin / 弧长参数化 | [mourner/simplify-js](https://github.com/mourner/simplify-js) BSD-2 7KB · Chaikin 1974 | DP 简化 / 拐角切割平滑(`Q'=3/4Pᵢ+1/4Pᵢ₊₁` 等,10 行)/ cumLen 表+二分 pointAt | ✅ 思想内联(几何在 Python 侧已简化,弧长表手写) |
| **OSRM 转向代价 sigmoid** | car.lua 源码 BSD-2 | `penalty = 7.5/(1+e^(-13·angle/180+6.5))`,直行偏好/转弯降速一行公式 | ✅ 公式移植 |
| 转向约束建模(GraphHopper 边基搜索) | Apache-2.0 | **边基图**:状态=有向边,后继=终点处其余出边(自动表达 oneway,默认禁 U-turn) | ✅ 建模决策 |

### 2.2 车辆行为与交通仿真

| 轮子 | 出处 / License | 核心思想 | 采纳 |
|---|---|---|---|
| **IDM 智能驾驶员模型** | [movsim/traffic-simulation-de](https://github.com/movsim/traffic-simulation-de)(Treiber 官方站,GPL-3.0 **只借思想**)+ 原论文 Phys. Rev. E 2000 | `a_free = a(1-(v/v0)⁴)`;`s* = s0+max(0, vT+vΔv/(2√(ab)))`;`acc = a_free − a(s*/gap)²`,钳 `[−bmax, a]`;**弹道积分** `v+=acc·dt; u+=v·dt+½acc·dt²`(Δt<0.5s 收敛);逐车抖动 v0×0.85-1.15、T×0.9-1.3 | ✅ 30 行重写 |
| **红灯/让行 = 静止虚拟车** | 同上 `calcAccGiveWay` 思想 | 停止线/冲突点当一辆停在 s0 的虚拟前车喂给 IDM,刹车起步自然涌现 | ✅(转弯减速用虚拟车/速度上限两式并用) |
| **转向冲突表 + FCFS** | [A/B Street from_scratch 教程](https://github.com/a-b-street/docs/blob/main/book/src/tech/trafficsim/from_scratch.md) Apache-2.0 · Dresner & Stone AIM (JAIR 2008) | 路口内 (入×转) 对预标冲突;先到先得过;不冲突并发 | ◐ 简化:路口占用锁(装饰级,防穿模即可) |
| **带权随机游走到边缘** | 类偏置随机游走(无标准库,Cities Skylines 复盘印证"物理对象+前瞻目标"思想:[Game Developer 深度复盘](https://www.gamedeveloper.com/design/game-design-deep-dive-traffic-systems-in-i-cities-skylines-i-)) | 权重 = 等级偏好 × 同级续接 × 直行偏好 × 驶向边缘;禁 U-turn;2-3 步前瞻防死路;兜底最短路 | ✅ ~40 行 |
| **密度分布 FHWA 等级权重** | FHWA Highway Functional Classification (2013):干道 10-15% 里程承载 65-75% VKT | 干道:支路 ≈ 8:3:1 驱动出生抽样 + 续接偏好;拥挤降权 10 行 ≈ 随机用户均衡一步近似 | ✅(现有缺口配给保留,权重改 8:3:1) |
| 轨迹系统 `traj(u)` | traffic-simulation.de `road.js` 结构 | 车道级路径 = 入段折线+路口曲线+出段折线,统一弧长接口;**朝向恒取轨迹切线** | ✅(v7 核心:全路线一条轨迹) |

### 2.3 蚂蚁线与路线动画美化

| 轮子 | 出处 / License | 核心思想 | 采纳 |
|---|---|---|---|
| **Mapbox 官方 ant-path** | [animate-ant-path 示例](https://docs.mapbox.com/mapbox-gl-js/example/animate-ant-path/) | 蚂蚁线行业标准 = **dash 相位动画**(14 帧离散步进,≈50px/s);Canvas 2D 有原生 `lineDashOffset` 可连续偏移,比官方更平滑 | ✅ 配方 A 基底 |
| Leaflet.Polyline.AntPath | [rubenspgcavalcante/leaflet-ant-path](https://github.com/rubenspgcavalcante/leaflet-ant-path) MIT | 底衬 pulseColor + 顶层虚线双层 = "淡雅"关键 | ✅ 双层结构 |
| **deck.gl TripsLayer / ECharts lines.effect** | [deck.gl](https://deck.gl/docs/api-reference/geo-layers/trips-layer) MIT · [ECharts](https://echarts.apache.org/en/option.html#series-lines.effect) Apache-2.0 | 专业路线动画共同参数:**fadeTrail 尾部按比例淡出**、`trailLength 0.2`、`constantSpeed` 匀速 px/s、round cap/join | ✅ 参数直接搬 |
| 辉光配方(2~3 层描边 + lighter) | Uber/kepler 生态共识 | halo(3×宽 α.15-.25)→ mid(1.6× α.4)→ core(1× α.9+),加色混合;**shadowBlur 运行时禁用** | ✅ |
| **UnrealBloom Canvas 2D 降级** | [three.js UnrealBloomPass](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/postprocessing/UnrealBloomPass.js) MIT · [pixi-filters](https://github.com/pixijs/filters) MIT(outerStrength≈合成 α,distance≈下采样级数) | 发光画在 0.5× glowCanvas → 0.25× 再下采样 → `lighter` 放大合成 = 免费 bloom;1/4 buffer 少 16 倍像素 | ✅(蚂蚁线/寻路共享) |
| 变宽 ribbon 数学 | mattdesl《Drawing Lines is Hard》 | 中心差分切向 `T=norm(P[i+1]-P[i-1])` → 法线偏移 → 平分线 miter(超 3× 退化 bevel);`w(u)=wMax(1-u)^0.7+wMin`,`a(u)=aMax(1-u)^1.6`;**先 4-6px 等距重采样再建 ribbon** | ✅(现 cometRibbon 升级) |
| 弧长表 + getPointAt/getTangentAt | [kjerandp/curve-interpolator](https://github.com/kjerandp/curve-interpolator) MIT | cumLen 数组 + 二分查找;平滑用 Catmull-Rom/Chaikin | ✅ 思想内联 |
| 节奏参考值 | Mapbox/ECharts 官方 | 蚂蚁 40-90px/s 匀速 linear、相位错峰 `hash(id)%period`;彗星画线 easeInOutCubic、巡航 300-600px/s、尾长 clamp(0.28L, 120, 400)、到达 pulse 250ms+扩散环 400ms | ✅ |

### 2.4 渲染性能

| 轮子 | 出处 | 数据 | 采纳 |
|---|---|---|---|
| Canvas2D 极限优化清单 | [MDN Optimizing canvas](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas) · HTML5Rocks(Sam Saccone) | 离屏精灵 3.40→0.40ms;整数坐标 10.9→9.1ms;**setLineDash 每帧=Skia 逐段 CPU 重算,最差用法**;ctx.filter 单次绘制级后处理极贵(Safari 18 才支持);willReadFrequently=强制软渲染(反项警告) | ✅ 指导配方 |
| WebGL 库(PixiJS v8 828KB / deck.gl 1.44MB / regl) | npm 实测 | 2 千精灵规模收益不抵迁移;无构建约束下整包内嵌 +828KB | ❌ 不引 |
| OffscreenCanvas Worker | caniuse 实测(Safari 17+ 完整) | 瓶颈在栅格化不在主线程排队;worker 不减少任何 draw call | ❌ 不做 |
| ticker 标准模式 | MDN rAF · [GSAP ticker](https://gsap.com/docs/v3/GSAP/gsap.ticker)(72KB,只抄设计) | dt 驱动防高刷加速;**lagSmoothing**(>500ms 只前推 33ms)防卡后瞬移;帧时 EMA 自适应降档;visibilitychange 守卫 | ✅ ~40 行 |
| 视口裁剪 | [mourner/rbush](https://github.com/mourner/rbush) 6KB(基准 ~30µs/查询) | 静态路网用自写均匀网格更廉(O(可见格));精灵按"所属路段"间接裁剪 | ✅ 网格分桶 |
| 合成器行为 | [Chromium GPU 合成文档](https://www.chromium.org/developers/design-documents/gpu-accelerated-compositing-in-chrome/) | 加速 2D canvas 各自成独立合成层,层失效互不波及;现有双层 canvas 即最优结构 | ✅ 维持 |

### 2.5 调研结论一句话

> **蚂蚁线** = 业界标准做法是"虚线相位动画"(dash 沿真实路径几何计算,**天生贴弯、零切角**),
> 我们却用了 1500 个独立精灵(切角 + 贵)——推倒重来。
> **彗星寻路** = 业界共同形态是"加载期建图(简化+合并)+ 边基图状态(边,弧长,方向)+ IDM 跟驰",
> 我们是"逐路口现场几何打分"——按 ADR-0008 落地图结构。
> **性能** = 砍掉每帧 dash 重算与千级 blit,换"合并 Path2D 分桶 + 预烘焙精灵 + 半分辨率 bloom 合成"。

---

## 三、v7 设计方案

### 3.1 路口图(加载期,替代逐跳扫描)

```
① 端点聚类(OSMnx consolidate 直译):
   798 段端点 → 网格桶(格 64px)→ 并查集合并 ≤26px 端点 → 节点(质心)
   [分离车道同路口的 4-8 个端点收敛为 1-3 个节点]
② 邻接:node → [(edge, dir)],oneway 门控方向;U-turn 默认禁止(死头豁免)
③ 度 2 走廊缝合(OSMnx simplify 思想):
   节点处入边唯一续接(对齐 ≥0.92)→ 链式合并为走廊(corridor)
   [决策点只剩真路口;走廊内部零缺口]
④ 转向曲线(路口内):入点+入切向 → 出点+出切向 的三次贝塞尔(控制点沿切向前方验证,
   近平行退化直跨),12 点等弧长采样 —— 运行期不再现场造桥
```

### 3.2 全路线轨迹(表示层根治漂移)

出生即规划:**route = 走廊图上带权随机游走(等级权 8:3:1 × 同级续接 × 直行偏好 × 驶向边缘,禁 U-turn,
已访路禁止,2 步前瞻防死路)到边界走廊**;把整条路线(走廊 LUT + 转向曲线)**拼成一条轨迹**
(cumLen 弧长表 + 均匀 3px 采样)。车辆状态 = `{traj, s, v}` —— 位置/切向 = 轨迹查表,
**运行期零路口决策、零桥、零 hist 回溯**;驶出边界(路线终点在 viewBox 外延)才销毁。

### 3.3 IDM-lite 跟驰(30 行,弹道积分)

```
leader = 同走廊同向最近前车(每帧按 (edgeKey) 分桶,桶内线性找前车)
s*  = s0 + max(0, v·T + v·Δv / (2√(a·b)))
acc = a·(1 − (v/v0)⁴ − (s*/max(gap,s0))²)      钳 [−Bmax, a]
转弯减速:前方轨迹存转向点(弧长位置,转角);v_cap = √(vTurn² + 2b·distToTurn)
积分:v += acc·dt; s += v·dt + ½acc·dt²;  逐车 v0×(0.85-1.15)、T×(0.9-1.3)
参数(像素世界,风格化标定):SPD 等级表沿用;s0=10px, T=1.1s, a=120, b=140 px/s²
```

### 3.4 蚂蚁线新配方(虚线相位 + 三层同心 + 半分辨率 bloom)

```
预处理:主等级路(5 类)各并成 1 个 Path2D ×3 个相位桶(hash 错峰);round cap/join
每帧(glowCanvas 0.35× 分辨率,世界变换):
  lineDashOffset = -(t·50 世界px/s) + 桶相位偏移;dash = [2.6W, 3.4W](W=该级路宽)
  层1 halo: lw 3×W, α.14;层2 mid: lw 1.6×W, α.34   ← 画在 glow canvas
  层3 core: lw 1×W, mix(fx,#fff,.35) α.9            ← 直接画 fx(锐利芯线)
合成:glowCanvas drawImage 回 fx,'lighter',α.85(= 免费 bloom,虚线端头融成柔光)
成本:~10 次 stroke + 1 blit(替代 1500 blit);**dash 沿真实路径几何计算,过弯贴路由构造保证**
深缩放(k>2.2)切换:按路网网格分桶逐路 stroke(bbHit 剔除),dash 同参
```

### 3.5 寻路 A→B 观感升级

```
① 平滑:折点 4px 等距重采样 → Chaikin 拐角切割 ×2(圆角贴路,偏差 ≤2px)
② 三段节奏:画线 easeInOutCubic,时长 clamp(L/450px/s, 2.6s, 5.2s);
   巡航头部 = 预烘焙头精灵 + 32 点变宽 ribbon 尾(w(u)=9(1-u)^0.7+0.8, a(u)=.85(1-u)^1.6)
③ 完成后能量流:bright dash [70, L] 沿线 lineDashOffset 流动(2 stroke),直至切换路线
④ 到达反馈:头部 scale 1→1.7(sin 250ms)+ 终点扩散环 400ms;A/B 端点卡保留
```

### 3.6 性能预算(ticker + 自适应 + 裁剪)

- dt 驱动(已有)+ lagSmoothing(>0.25s 重置)+ 帧时 EMA 自适应降档:ema>20ms 持续 1.5s →
  关 bloom / 预算降档(蚂蚁桶减半、ribbon 采样 32→16);<14ms 持续 3s 升回;
- 路网均匀网格(格 200px)分桶:深缩放时蚂蚁/寻路按桶剔除;
- 发光精灵全部预烘焙(已有),新建头部精灵/蚂蚁 bloom canvas 共享;
- 明确不做:WebGL 库、OffscreenCanvas worker、GSAP、SVG 动画层(调研 2.4)。

### 3.7 不变项

静态层栅格化、入场生长、重点标注、巡检、涟漪、POI 标注、视口交互、主题跟随、面板 UI 全部保留;
routes.json(A→B 数据源)不变;构建管线不变。

---

## 四、验收标准(自动化,Playwright 无头)

| # | 断言 | 通过线 | 实测(2026-09-29) |
|---|---|---|---|
| V1 | 全特效 25s 长跑 pageerror | 0 错误 | ✅ 0 错误 |
| V2 | 车流连续性:逐帧记录每车位移(gid 跟踪) | 帧间跳变 ≤ v·dt·1.05+2px | ✅ 0 违规(max 5.06px 均在包络内) |
| V3 | 贴路:走廊区间采样到最近走廊 LUT 距离(跳过 b0 桥区) | ≤4px | ✅ 最差 1.50px / 9348 采样 |
| V4 | 跟驰:同走廊同向两车间隙 | ≥8px | ✅ 最小 96.9px |
| V5 | 转弯减速符合制动曲线 | ≥90% | ✅ 100% |
| V6 | 每帧 stroke 调用(全开) | ≤60/帧 | ✅ 36/帧 |
| V7 | 帧率(无头软渲染) | ≥25 | ✅ 59-61fps(真机预期 60) |
| V8 | 蚂蚁/寻路三阶段截图人审 | PASS | ✅ `assets/map/samples/v7-*.png` |
| V9 | 掉头合法性:300 条离线规划相邻走廊不共享道路 | 0 违规 | ✅ 0(v7.0b) |
| V10 | 环岛行为:入环不绕圈(≤8 弧)、不从原路返回 | 0 违规 | ✅ 62 条环走廊 / 20 次入环全过(v7.0b) |

> 实施记录见 README 迭代 8;落地偏差:路口冲突表/占用锁未做(调研 §五:装饰动画收益趋零),
> 转弯减速用制动曲线实现;蚂蚁线 halo 层由 bloom 合成替代(省 18 stroke/帧)。
> v7.0b 三修:蚂蚁线瘦身降亮(给车流让层级)、环岛检测+入环定出口+真死头才掉头、
> 入场生长按真实宽度/casing 淡入/柔影尾段淡入(消除完成瞬间爆现)。

### v7.2 修订(2026-09-29,用户反馈"寻路还是随机"后)

**§3.2 的带权随机游走已被 A* 确定性导航取代**(调研 §6 转向约束建模的完全体落地):

- 车辆出生从"可达出口表"(加载期正向 BFS 预计算,与 A* 同规则)随机选**目的地**——
  司机去哪有自由;选定后 **A\*** 一次算定全程:代价 = 路长×等级因子(干道 0.92)
  \+ 转向罚(直行免费、转弯 `12+40(1-align)`、**同名大道零罚**),U-turn 不展开;
- 环岛:检测预算 900px;与环同路但反向弯曲的走廊**一律禁行**(补数据缺 oneway 的洞);
- 可达性:边界反向 BFS 过滤车流池;路口**让行**(入口占用声明制+停止线等待)+ 防穿模回推兜底;
- 验收 V1-V11(新增 V11 确定性:同(车,目的地)路线逐 id 一致 23/23;多样性 23/23)。

> "绕行比"验收在目的地随机化后语义失效(合法绕行天然存在),由确定性断言替代——
> **这正是"按交通规则严格规定路线"的可验证形式:同输入必同输出。**

### v7.3 修订(2026-09-30,用户反馈"出生点扎堆像刷怪"后)

**出生模型改为通勤式**:车辆全部从**地图边缘入口**驶入(ENTRY_POOL:起点 XY 贴边 ≤14px、
向城内、可达、可达出口 ≥4——边缘短街开进去就出去的不算入口),A\* 穿城,目的地从可达出口
按距离**降序取前 3**;35% 车辆带城中途经点(两段 A\*,兜一圈再走)。城内不再有任何出生点,
车流形态 = 真实过境交通:边缘进、主干道穿城、对侧出。

配套修正:贴边判定从"节点簇质心"(可深入内部 26px,曾致入口池为空/可达池错杀到 30 条)
改为**走廊自身端点 XY**;可达性反向 BFS 原来误用 OUT_AT(向前走)→ 补 IN_AT 入边表;
入口全拥挤时延迟出生并释放槽位(并入 Yield/回推体系)。
验收 V1-V12:新增 V12(入口全贴边;穿城占比 75%,中位出口距 1517px/对角线 2497);
确定性 60/60、多样性 60/60、faded=0、120 辆 61fps。

### v7.3b 修订(2026-09-30,用户反馈"虚空路 180° 调头 / 异常堵车")

诊断:320 条规划 90 条(28%)含 align < -0.5 的折返转向(最差 -1.0)——A\* 只罚不禁对向走廊
转移,贝塞尔桥连反向切线即勾回的虚空弧;冻结车 0 辆,堵车主要是折返横穿对向流的视觉混乱+汇流排队。

- **急折返禁行**:A\* 展开跳过 align < -0.55 的后继(>123°);150 条复测 0 例、最大桥 37px;
- **可达表与 A\* 同规则**:reach / EXITS_OF 的 BFS 同步禁急折返(EXITS_OF goal 亦切 isEdgeXY),
  否则"表说可达、A\* 走不通"曾致 46/300 规划失败回退;
- **饱和泄压**:入口 ≥3 出口(城门 10 个)、默认车流 100、死锁破解等 5s 低速放行 25px/s;
- V1-V12 全绿:修正 41→6、到达 300/300、确定性/多样性 60/60、穿城 75%(中位 1614px)。

### 实施期修复(过程坑)
1. 走廊缝合的桥检测只在**段缝**处做(段内采样间距 3px 会被误判,曾一次产生 3.6 万桥);
2. 蚂蚁合并 Path2D 的相位错峰靠**分桶**(lineDashOffset 对所有子路径统一生效,无法按路偏移);
3. 半分辨率 glow 层的 halo/mid 在 bloom 关闭时回退直画 fx(保证降档不消失);
4. 默认视口左上裁切(v5 起遗留)→ fit() 自动居中 + 用户交互接管;
5. 测试采样器必须在 rAF 回调**之后**记录,否则与页面步进错位一帧,误报瞬移。
