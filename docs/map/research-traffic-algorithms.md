# 车流模拟算法调研报告(GitHub / 学术 / 游戏工业)

> 日期:2026-09-24 · 目的:为 map-studio 车流模拟(v7)选型成熟算法,替代闭门造车的随机游走。
> 结论先行:**车道拓扑用 OSMnx 式"简化+路口合并"管线,车辆行为用 IDM 智能驾驶员模型**。

---

## 一、车道拓扑(Lane/Road Topology)

### 1.1 OSMnx 标准管线(Python,最权威的 OSM 路网图处理库)

来源:[spatialworkflow 指南](https://www.spatialworkflow.io)、[OSMnx 文档](https://osmnx.readthedocs.io)、
[SO:consolidate_intersections 实践](https://stackoverflow.com/questions/tagged/osmnx+consolidate-intersections)

标准三步:
1. **`simplify_graph()`** —— 合并度 2 节点(非路口的中间点),把被路口切碎的路段
   缝合成完整街道;尊重 oneway 方向性;
2. **`consolidate_intersections()`** —— 吸附路口节点(容差距离,`rebuild_graph=True`),
   解决**分离车道把一个十字路口拆成 4 个节点**的经典问题;
3. 产出:有向图(节点=路口,边=路段),死胡同用 `dead_ends` 参数保留。

**我们项目的对应缺陷**:v6.x 逐路口"就近+对齐"打分 = 手写版 simplify,但每次 respawn
现场算、无图结构,导致链路漂移/断头。v7 应在**加载期一次性构建图**。

### 1.2 osm2streets(A/B Street 生态,Rust+WASM+JS)

来源:[osm2streets](https://dabreegster.github.io)、[A/B Street](https://www.zendot.org)

OSM → **车道级路网**(含路口几何、转弯规则、公交道),A/B Street 用它做城市级微观仿真。
概念借鉴:把双向分离车道合并为一条"街道走廊(corridor)",车道是走廊的属性——
正是我们"直行同线走廊"的正确形态。

### 1.3 学术简化算法

[Adaptive continuity-preserving simplification(2025)](https://www.researchgate.net):
连续性保持的街道简化,专门处理双行道/环岛的合并——验证了"简化必须保连续性"。

---

## 二、车辆行为模型(Vehicle Behavior)

### 2.1 IDM 智能驾驶员模型(工业标准)

来源:[traffic-simulation.de 官方 JS 实现](https://traffic-simulation.de/info/info_IDM.html)、
[原始论文 Treiber/Hennecke/Helbing 2000, Phys. Rev. E](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.62.1805)

加速度方程(每车每帧):
```
s*(v,Δv) = s₀ + max(0, v·T + v·Δv / (2·√(a·b)))     # 期望间距
acc     = a · [1 − (v/v₀)^δ − (s*(v,Δv)/gap)²]       # 纵向加速度
```
参数(城市):期望速度 v₀、期望时距 T≈1.2s、最大加速 a≈2.5、舒适减速 b≈2.2、
最小间距 s₀≈2.5。行为涌现:**跟车不追尾、排队、起步加速、接近前车减速**——全部免费获得。

### 2.2 交叉口逻辑

[A/B Street](https://www.zendot.org):路口=节点,转向=有向边对,**转向先到先得**,
冲突时让行;[Citybound](https://context7.com):微观仿真按"承诺-让行"协商。

我们的简化版:到达路口前按 IDM 减速到转弯速度,路口内已有车(占用)则等待。

### 2.3 生成模型

SUMO 式 `flows`:按 (路线, 间隔/数量) 定义车流;入口检查间距——
对应我们的"缺口配给 + 入口间距检查"。

---

## 三、游戏/web 实现参考

| 项目 | 形态 | 可借鉴 |
|---|---|---|
| [traffic-simulation.de](https://traffic-simulation.de/info/info_IDM.html) | 纯 JS/Canvas,IDM 作者官方 | IDM 参数与实现 |
| [A/B Street](https://www.zendot.org) | Rust 城市仿真 | 路口拓扑、转向模型 |
| osm2streets | Rust/WASM/JS | OSM→车道级路网转换 |
| Citybound | Rust 城市游戏 | 微观交通协商 |

---

## 四、v7 采用方案(决策)

1. **拓扑**:加载期构建**路口图**——路段端点 26px 吸附成路口节点;沿"对齐 ≥0.9 的
   唯一续接"把度 2 链**合并成长走廊(corridor)**= OSMnx simplify 的 JS 版;
   路线/车辆都在走廊图上运行(路口数从 4062 → 数百,决策点大幅减少)。
2. **路线**:出生时在走廊图上随机游走(缺口配给选起点)至地图边缘节点;
   整条路线一次算定,天然连续(共点),无跨街跳跃。
3. **车辆**:IDM-lite——同走廊按 pos 排序跟驰(排队自然涌现),路口减速;
   曲桥仅在缺口 >2px 时使用(规划期已验证走廊连续,缺口罕见)。
4. **蚂蚁线**与车流解耦(装饰层,维持现状)。

> ADR:v7 拓扑与行为模型选型见 `docs/map/adr/ADR-0008-corridor-graph-idm.md`。
