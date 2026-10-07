# 地图绘制能力调研与实测报告(artboard 扩展)

> 日期:2026-09-23 · 环境:Windows 10.0.19045(x64)、Python 3.14.7、Chrome
> (`VB_BROWSER_PATH`)、Playwright(pip)、Pillow 12.3.0
> 结论:已在本机完整跑通「任意城市/任意范围 · 多网点标注 · 平面 + 2.5D + 3D」
> 的可复现地图资产生成管线,全部产物见 `assets/`。

---

## 一、需求拆解

| 需求 | 本机解法 | 状态 |
|---|---|---|
| 标注某一个/多个地点(公司网点) | `assets/map/points.*.json` 统一坐标入口,PIL 图钉 / HTML 图钉两种 | ✅ 实测 |
| 显示周边道路/地点 | 瓦片底图自带路网+中文 POI;z17 街道级 1.1 m/px | ✅ 实测 |
| 不止广州,任意区域可大可小 | z4(国家级)~z17(门牌级)连续缩放;城市/省份/全国同一命令 | ✅ 广州/深圳实测 |
| 平面视角 | `scripts/map_tiles.py` 瓦片拼接器(纯 Python,无浏览器) | ✅ 实测 |
| 2.5D 视角 | 海报 HTML 内 CSS 透视倾斜(`rotateX+rotateZ`),见 mapnet-kv | ✅ 实测 |
| 3D 视角(真透视+楼体) | MapLibre GL v5.9.0(本地 vendor)+ pitch/bearing 相机 + OSM 建筑按真实高度挤出(fill-extrusion)+ Playwright Chrome 截图 | ✅ 实测 |

## 二、网络可达性实测(2026-09-23,本机直连)

| 数据源 | 结果 | 对选型的影响 |
|---|---|---|
| `webrd01-04.is.autonavi.com`(高德街道瓦片,style=8,scale=2) | ✅ 200,真实中文街道图(路网+POI+注记) | **平面+3D 底图主线** |
| `overpass-api.de/api/interpreter` | ✅ 可用;偶发 "server too busy"(返回 HTML),脚本需重试 | **建筑/道路矢量主线** |
| `basemaps.cartocdn.com`(CARTO) | ⚠️ 200 但无 key 时瓦片上印大字水印 `API KEY REQUIRED`(两种样式均实测) | 弃主线;注册免费 key 后可用(免费额度 500 万瓦片/月,官方要求强署名) |
| `tile.openstreetmap.org` | ❌ 连接超时 | 弃 |
| `a.basemaps.cartocdn.com`(带子域) | ❌ 超时(裸域名反而可达) | — |
| `services.arcgisonline.com`(Esri) | ❌ 超时 | 弃 |
| `download.geofabrik.de`(离线 pbf) | ❌ 超时 | 离线矢量全栈路线本机不可复现(见 §四-5) |
| `nominatim.openstreetmap.org`(地理编码) | ❌ 超时 | 地名→坐标改由 Overpass 节点查询实现 |
| `overpass.kumi.systems`(镜像) | ❌ 读超时 | — |
| `cdn.jsdelivr.net` / `registry.npmmirror.com` | ✅ | maplibre vendor 下载渠道 |

## 三、坐标系(GCJ-02 偏移)——本调研最关键的"非表层"事实

- 国内互联网地图底图(高德/腾讯/百度)分别使用 **GCJ-02 / BD-09**,而
  **OSM/Overpass 数据是 WGS-84**。两系混标,广州实测偏差(经
  `eviltransform.wgs2gcj` 计算):**dLon +0.005330(≈546 m 东)、dLat −0.002677(≈298 m 北)**。
- 因此本管线**统一坐标入口为 WGS-84**(点位来自 Overpass 实查或 GPS/OSM),
  在渲染高德底图/对齐建筑矢量时由脚本内部自动换算 GCJ-02;
  若用户从高德拾取器拿坐标,给 `--coord gcj` 参数即可反向兼容。
- 已用视觉对齐验证:广州塔 WGS-84 坐标 23.109049,113.317930 换算后,
  3D 渲染与平面拼接图中图钉均精确落在真实塔位/江湾处。
- `pip install eviltransform`(纯 Python,无依赖,本次实测安装即用)。

## 四、候选方案核验结论

1. **高德/百度 Static Map API(官方静态图)**:官方文档核实**必须注册 key**
   (高德 `restapi.amap.com/v3/staticmap`,size 上限 1024×1024、scale=2 翻倍、
   markers ≤10)。免注册不可复现 → 记录为备选(用户愿意注册 key 时,一行 URL
   即出图,坐标系同为 GCJ-02)。
2. **CARTO 底图**:无 key 瓦片带水印(实测截图存 `work/tiles/probe/`);注册免费
   key 后合法可用 → 备选。
3. **OSM 官方瓦片 / Esri**:本机直连超时 → 弃。
4. **Leaflet + 在线瓦片截图**:能做平面,但需浏览器、2.5D/3D 能力为零,且
   Leaflet 本身只管平面;被 maplibre 方案完全覆盖 → 不单列。
5. **离线矢量全栈(Geofabrik pbf → tilemaker/pmtiles → maplibre 矢量样式)**:
   效果上限最高(完全离线、样式全自定义、含地形),但 Geofabrik 数据源在本机
   不可达 → **本机不可复现**,不作为主线;网络环境允许时是增强方向(protomaps
   的 pmtiles 单文件 + `pmtiles-serve` 亦可)。
6. **✅ 主线 = 高德 Web 瓦片(无需 key,直连可达)+ 本地 GCJ-02 换算
   (`scripts/_map_mercator.py`,不再依赖 pip eviltransform)+
   Overpass 矢量**:两个数据源本机实测可达,全程命令化,产物可离线复跑
   (瓦片有本地缓存 `work/tiles/cache/`)。
   *合规注记:直连高德 Web 瓦片未走官方授权,适合内部演示/设计样张;对外商用
   产品应申请高德官方 key(静态图 API 或 WMS)或采购授权。OSM 矢量数据按 ODbL
   署名(产物已内置署名)。境内公开出版/发布地图另有审图号要求,本管线不覆盖。*
7. **3D 渲染器选型**:
   - **maplibre-gl v5.9.0 UMD 单文件**(`assets/vendor/maplibre/maplibre-gl.js`,
     BSD-3-Clause,npmmirror 实测下载):支持 pitch/bearing 相机、fill-extrusion、
     raster 源。**不选 v6.x**:6 起改 ESM 多分包(worker/shared),file:// 与
     单文件 vendor 场景不便。
   - **HTML 覆盖层做标注**而非 maplibre symbol 层:symbol 需要离线字形 PBF
     (额外一整套字体切片);HTML 图钉自由度更高、中文字体直接用系统/
     artboard 字体,静态相机下 `map.project()` 一次定位即可。
   - **本地 HTTP 服务**(127.0.0.1 随机端口,脚本内起停)供 maplibre 取瓦片与
     GeoJSON:避免 file:// fetch 限制;截图完自动关停,不改变"产物离线"性质。
   - **软件 WebGL**:headless Chrome 加 `--enable-unsafe-swiftshader
     --use-angle=swiftshader`,实测渲染正常(3840×2160)。
   - deck.gl/three.js 自绘:可行但工程量大,maplibre 一层 fill-extrusion 已
     覆盖需求 → 不选。
8. **平面拼接器自写**(Python+PIL,~200 行)而非用 `staticmap` 库:该库久未
   维护且不支持高德 scale=2/数据源/坐标系定制;slippy tile 数学是标准公式
   (OSM Wiki "Slippy map tilenames"),自写反而完全可控。经真实瓦片落点验证。

## 五、关键实现参数(踩坑实录)

1. **maplibre zoom 与 256px 瓦片源的换算**:相机 zoom `cz` 下,maplibre 以
   `512·2^cz` px 世界宽度渲染;256px 源请求的瓦片级别约为 `cz−1`。实践:
   相机 zoom 14.0~14.6 配 15 级瓦片,dpi=2 时清晰;预缓存级别覆盖
   `z−2 ~ z`,窗口比视口多 4 瓦片,避免边缘 404。
2. **GCJ-02 瓦片网格**:高德瓦片网格按 GCJ-02 经纬度索引——不只是"点要换算",
   **拼接窗口/中心点/图钉投影全部要在 GCJ-02 空间计算**,否则整体错位约 600 m。
3. **建筑高度规则**(无编造):`height` 标签 → `building:levels × 3.2 m` →
   缺省 10 m;珠江新城 bbox 实测抓到 480 栋(217 栋有 >10 m 标注,最高 440.2 m)。
4. **Overpass 忙碌是常态**:首次请求常返回 HTML 错误页,脚本内置 4 次重试、
   间隔 20 s;查询按 bbox 收窄 + `out geom qt` 控制负载(480 栋 ~240 KB)。
5. **Windows Python 不认 Git Bash 的 `/d/...` 路径**:脚本内一律
   `os.path.abspath`/`__file__` 推导或 Windows 风格路径。
6. **模板大括号**:渲染页 HTML 含大量 JS/CSS 大括号,禁用 Python `str.format`
   (转义地狱),用 `__TOKEN__` 替换。
7. **导出参数**:artboard `export.py` 当前版本**无 `--engine` 参数**(记忆中的
   旧参数),默认即自动走浏览器道(`VB_BROWSER_PATH` 指向 Chrome),
   `degraded_artboard:true` 仅为画布回填标注,核对导出尺寸无误即可。

## 六、产物清单(全部可由 §README 命令重跑)

| 文件(并入后路径) | 内容 | 参数 |
|---|---|---|
| `assets/map/samples/flat-gz-citywide-z12.png` | 广州全市 5 网点平面图(1600×1200,z12,35.2 m/px) | amap style8 scale2 |
| `assets/map/samples/flat-gz-chenjiaci-z17.png` | 陈家祠街道级(1600×1200,z17,1.1 m/px,周边 POI 全可见) | 同上 |
| `assets/map/samples/flat-sz-citywide-z12.png` | 深圳全域(跨城验证) | 同上 |
| `assets/map/samples/v3d-*.png` | 珠江新城真 3D 三主题(pitch63/bearing−28,3840×2160,见 §八) | z15 数据 |
| `work/geo/gz-cbd/*.geojson` | 建筑/五层矢量底料(运行期产物,`work/` 已 gitignore;重跑即出) | Overpass |

> 并入 artboard 时的取舍:栅格 3D 俯瞰样张(`s3d-gz-cbd.png` / `s3d-gz-cbd-hero.png`)
> 与 KV 海报工程未随迁移保留 —— 两者都可由 `scripts/render_3d.py` 与 artboard 海报
> 管线按本文命令重跑;成品样张以 `assets/map/samples/` 现存 31 件为准。

## 七、遗留与增强方向

- 地形 3D(raster-dem):高德无高程瓦片,MapLibre 支持 terrarium 格式
  (AWS 免费源,本机未测可达性);平坦城市需求低。
- `--coord gcj` 已在拼接器实现;3D 渲染器暂只收 WGS-84 入口(可按同一
  `to_datum` 模式补一行)。
- 卫星底图(`webst0x ... style=6`)代码已内置但本次未实测;跑前先看
  `work/tiles/cache/amap-sat/` 是否出图。
- 小 Town/乡镇级验证只做了深圳跨城;乡镇名地理编码因 Nominatim 不可达,
  需用户提供坐标或用 Overpass 按乡镇名查 relation。


---

## 八、迭代 2 · 矢量可编程地图(2026-09-23 追加)

需求升级:栅格贴图风格单一,要 1:1 矢量化且**逐元素可控**(显隐/改色),2.5D/3D 同步迭代。

### 轮子调研结论(详 ADR-0006)
prettymaps / map-machine / OSM2World / city-roads / geojson2svg / d3-geo 均不满足
"逐元素 class 化 + CSS 换肤",或有重型依赖(geopandas/PyCairo/Java/Node)→ **自建**。

### 实测落地
- **数据层 v2**:Overpass 合并查询一次抓五层,自动重试(本次实测前两次 busy,第三次成功);
  珠江新城 bbox:建筑 480 / 道路 798 / 轨道 100 / 水系 17 / 绿地 98。
- **2D SVG**(`svg_map.py`):每要素一个 `<path>` + 语义 class;四主题 CSS 变量组内嵌,
  `data-theme` 属性换肤,`no-*` class 关图层;235 KB/幅。
  坑:CSS 注释里裸写 `<layer>` 会炸 XML 解析 → CSS 内容必须 CDATA 包裹。
  自动 bbox 会被河流/地铁的长几何撑大 → 用显式 `--bbox`。
- **2.5D 等轴测 SVG**(`svg_iso.py`):正交投影(bearing 旋转 + cos(pitch) 压扁),
  建筑按真实高度挤出,画家算法 + 外法线墙面剔除;392 KB/幅,深/纸双主题验证通过。
- **真 3D 全矢量**(`render_3d_vec.py`):maplibre 五源(建筑/道路/轨道/水/绿地)全数据驱动,
  主题 = 一个 JSON;**零栅格瓦片**,彻底摆脱底图服务依赖。
  坑:`line-cap` 属 MapLibre `layout` 段,写进 `paint` 会导致 style 校验失败、idle 不触发。
- **交互验证**:`assets/map/demo/svg-demo.html` 经 Playwright 真实点击验证——切蓝图主题 +
  关建筑/绿地图层,同文件即时换肤。


---

## 九、迭代 3 · 基础动画预设(2026-09-24 追加)

- **寻路是真寻路**:`compute_route.py` 把 798 条路建成图(4062 节点/4345 边,节点按坐标 7 位小数吸附,
  权重=分段米长),Dijkstra 求 OD 最短路,再经同一 Proj 投到 SVG 像素空间——动画走的是真实路网。
- **坑**:fx 层开关的清理顺序——`off()` 必须**先删注册表再调 teardown**,否则 boot 的清理里再调
  off 自己 → 无限递归 Maximum call stack;route/traffic 的 rAF 句柄要在闭包内自持,不能读全局注册表。
- **坑**:自绘开关的 `<input>` 被 `display:none` 隐藏,Playwright `check()` 会超时——测试一律走
  `evaluate` 置 checked + dispatchEvent('change')。
- 验证:七项预设逐项开关截图确认(律动流光/寻路光轨沿真实道路/车流粒子/最高楼铭牌/巡检/涟漪/入场生长中段与完成态),pageerror=0。


---

## 十、迭代 3.5 · 播放器性能重构与实测结论(2026-09-24)

**方法论:SVG 动画开销 = 动画元素数 × 每元素重绘成本。** 三板斧:
1. 合并同类:`d` 属性多子路径拼接(同等级道路合 1 条),动画元素 800→18;
2. 查表化:`getPointAtLength`(每次 O(路径复杂度))→ 初始化时按 9px 采样建 Float32Array,
   运行期线性插值 O(1),并顺带拿到切向(粒子拖尾方向);
3. 去 filter:SVG CSS filter 动画逐帧触发全层重绘,改 paint 属性(stroke-width/fill-opacity)脉冲。

**FPS 佐证**:无头软渲染环境空闲基线 ≈32fps(帧率上限在环境),单项/全开(200 粒子)同为 ~31-32
→ 动画逻辑已不是瓶颈,真实浏览器满帧。**测性能务必先测空闲基线**,否则会把环境上限误读成自己代码的开销。

**算法升级**:OD 吸附改空间哈希网格(500m 格 + 环形扩搜),Dijkstra→A*(haversine 启发式可采纳),
输出折线 Douglas-Peucker 简化(1.2px 容差);两条 demo 路线米数与 v1 Dijkstra 完全一致(互验),点数 -65%。
