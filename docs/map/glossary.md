# 词汇表 · 地图渲染

> 术语消歧,取值口径以本机实测为准(2026-09-23)。

| 术语 | 含义 / 本项目口径 |
|---|---|
| **瓦片(TILE / XYZ tile)** | 256×256 的地图切片,按 `z/x/y`(缩放级/列/行)索引;z 每加 1 分辨率翻倍。本项目:高德街道瓦片,本地缓存在 `work/tiles/cache/amap/<z>/<x>/<y>.png`(`work/` 已 gitignore)。 |
| **Slippy tile 数学** | 经纬度 ↔ 瓦片编号的标准 Web 墨卡托公式(`deg2num/num2deg`),OSM Wiki "Slippy map tilenames";本项目 `scripts/_map_mercator.py`,已用真实瓦片落点验证。 |
| **GCJ-02(火星坐标)** | 国内互联网底图(高德/腾讯等)的加密坐标系。广州实测相对 WGS-84 偏移 ≈ 东 546 m / 北 298 m。高德瓦片网格按 GCJ-02 索引。 |
| **WGS-84** | GPS/OSM 原始坐标系。本项目所有点位文件的统一入口(ADR-0004)。 |
| **BD-09** | 百度系坐标,本项目未使用(需时再在 `_map_mercator.py` 加转换)。 |
| **eviltransform** | 开源 GCJ-02↔WGS-84 换算库(pip 安装)。**已不再依赖**:并入 artboard 时换成 `scripts/_map_mercator.py` 本地实现(与该库对拍 8 点最大偏差 1.1e-7 度,往返误差 0)。 |
| **Overpass API** | OSM 结构化数据查询服务(`overpass-api.de/api/interpreter`,POST `data=`)。本项目建筑/道路矢量与地名→坐标的唯一来源;忙时返回 HTML,需重试。 |
| **ODbL** | OSM 数据许可(署名-相同方式共享)。产物署名:"建筑矢量 © OpenStreetMap 贡献者(ODbL)"。 |
| **MapLibre GL JS** | 开源 WebGL 地图引擎(Mapbox GL 分叉,BSD-3)。本项目钉 **v5.9.0 单文件 UMD**(v6 改 ESM 多分包,不利于单文件离线)。 |
| **fill-extrusion** | MapLibre 图层类型:按属性(如 `height`)把多边形挤出成 3D 体块。本项目建筑高度的取值顺序:`height` → `building:levels×3.2m` → 10m 缺省。 |
| **pitch / bearing** | 相机俯仰角(0=俯视,60~65=街景透视)/ 旋转角。本项目 3D:60–63 / −28~−30。 |
| **2.5D(伪 3D)** | 平面图经 CSS `perspective + rotateX/rotateZ` 得到的透视倾斜观感,无真实楼体;与真 3D(fill-extrusion)区分。 |
| **scale=2(高德)** | 瓦片像素仍 256 但注记/线划密度翻倍(视网膜瓦片),同 zoom 更清晰。 |
| **m/px(米每像素)** | `156543.034·cos(纬度)/2^z`;z12≈35.2 m/px(全市),z17≈1.1 m/px(街道)。 |
| **符号层 / 字形 PBF** | MapLibre 的 maplibre symbol 文字标注需离线字形切片;本项目**不用**符号层,标注走 HTML 覆盖层(`map.project()` 屏幕定位),省一整套字体资产。 |
| **软件 WebGL(SwiftShader)** | headless Chrome 无 GPU 时的软件渲染路径;启动参数 `--enable-unsafe-swiftshader --use-angle=swiftshader`,实测可出 4K。 |
| **`degraded_artboard`** | artboard 导出回执中的画布回填标注;显式传了 `--width/--height` 且尺寸核对无误即为正常,不代表废图。 |
| **Casing(路缘描边)** | 主干路填充下方更宽一圈的暗/亮晕边,制造道路与地物的层次;本项目只给 primary/trunk/motorway 上 casing,宽度 = 路宽 + 2,主题变量 `--rc`。 |
| **双向墙面着色** | 等轴测图按墙面外法线朝向分两个色调(受光/背光),模拟固定光源;类 `wall-wa/wb`,变量 `--bld-wall(--2)`。 |
| **Path2D** | 浏览器 Canvas 的预编译路径对象;加载期把 SVG path 的 `d` 属性转成 Path2D,每帧只 stroke/fill,免运行期解析。 |
| **采样查找表(LUT)** | 对每条道路按 9px 步长预采样坐标存 Float32Array;运行期粒子位置=查表线性插值 O(1),并顺带获得切向。 |
| **彗尾(Comet Trail)** | 移动光点后 4 段渐隐尾迹(透明度/宽度递减)+ 亮头点;车流与寻路的标准视觉。 |
| **fill-extrusion-vertical-gradient** | MapLibre 挤出体沿高度的明暗渐变 paint 属性,给 3D 楼体加"受光"立体感。 |
| **发光精灵(Glow Sprite)** | 预渲染一次的径向渐变小画布,运行期 drawImage 复用;替代逐帧 createRadialGradient(贵一个数量级)。 |
| **加色混合(lighter)** | Canvas `globalCompositeOperation='lighter'`,重叠光叠加变亮;整批设置一次,勿逐粒子切换。 |
| **视口变换(Viewport)** | 地图世界坐标→屏幕的三元组 {pan.x, pan.y, k};拖拽改 pan,Alt+滚轮以鼠标为锚点改 k(锚点世界点前后不动)。 |
| **引线标注卡(Callout)** | 屏幕空间绘制的网点标注:定位点+引线+圆角卡(名称/区/迷你示意图),字号屏幕恒定、缩放分级展开、矩形碰撞避让。 |
| **微投影(Micro-shadow)** | 2D 建筑轮廓整组平移一份半透明深色副本置于建筑层下,制造浮起感;SVG 内单 group transform,零逐要素成本。 |
| **双层 Canvas** | 静态层(地图,仅视图变化重绘)+ 动态层(特效,每帧);SVG 隐藏作数据源。解决 CSS transform 缩放 = 纹理拉伸发糊的问题(Canvas 按当前变换重新栅格化)。 |
| **will-change 陷阱** | `will-change:transform` 促使浏览器把元素光栅化为纹理再由 GPU 拉伸——矢量内容在放大倍率下必然发糊;交互式缩放的矢量地图禁用。 |
| **彗尾锥形(comet taper)** | 尾迹按段递减线宽与透明度(头 3.4→尾 0.25),加头部发光精灵,呈"头重脚轻"彗星状;参数化 `comet(ctx,v,pos,{segs,gap,w0,w1,a0,a1})`。 |
| **审图号** | 境内公开出版/发布地图的行政审查编号。本管线产出为设计样张/内部演示,不含审图号;对外公开出版需另行送审(超出本管线范围)。 |
