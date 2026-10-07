# 地图模块(子技能)· 城市地图 / 路网 / 区位图 / 3D 城市 / 地图动画

> **用户需要"地图"类物料时,读本文。** 工具已并入本技能 `scripts/`
> (`map_tiles.py` / `fetch_osm_data.py` / `svg_map.py` / `svg_iso.py` / `svg_preview.py` /
> `render_3d.py` / `render_3d_vec.py` / `compute_route.py` / `build_player.py` /
> `probe_tiles.py` / `test_v7.py`;内部层 `_map_common.py` / `_map_mercator.py`)。
> 运行期产物落 `<技能根>/work/`(已进 .gitignore);随技能附带的成品样张在
> `assets/map/samples/`,主题 JSON 在 `assets/map/themes/`,底图 vendor 在 `assets/vendor/maplibre/`。
> **所有命令都在技能根执行**(写成 `scripts/<工具名>.py`,不是 `cd scripts`)。

## 一、什么时候读本文(触发词)

- **实体词**:地图、城市地图、路网、区位图、平面图(地图语境)、街道级地图/底图、
  3D 城市、三维地图、2.5D/等轴测地图、地图 KV、导航动画、车流/车辆动画、
  通勤动画、地图演示页/播放器、多网点分布图、网点标注图
- **场景词**:发布会 KV 里的城市配图、汇报/PPT 里的区位页、公众号城市示意、
  "画一下 XX 城市的地图"、"XX 城市路网"、"给我一个地图动画"

## 二、不触发(还给主线)

- 海报里放风景照/卫星截图(没有"绘制地图"语义)→ `references/materials.md` 素材流程
- 纯图表 / 数据可视化 → `references/dataviz.md`
- 需要**审图号**的公开出版地图 → 超出本模块范围(见 §七)

## 三、先选产物形态(能力矩阵)

| 形态 | 工具 | 产物特征 | 典型用法 |
|---|---|---|---|
| 平面 PNG | `map_tiles.py` | 高德 XYZ 瓦片拼接 + 网点图钉 + 版权条 | 最快、最像"真地图";海报图卡/汇报底图 |
| 2D 主题化 SVG | `svg_map.py` | 每个元素独立 `<path>` 带语义 class,四主题内嵌(`data-theme` 即换肤) | 要换肤/隐藏图层/后续可编辑 |
| 2.5D 等轴测 SVG | `svg_iso.py` | 建筑按 OSM 真实高度挤出,画家算法排序 | 区位图要立体又保持矢量 |
| 真 3D PNG(栅格) | `render_3d.py` | MapLibre + 瓦片底图 + 建筑挤出 + 项目位图钉 | 发布会主视觉 |
| 真 3D PNG(全矢量) | `render_3d_vec.py` | 零瓦片、零栅格,换主题 = 换一个 JSON | 成套主题、无底图依赖 |
| 动画播放器 | `build_player.py` + `test_v7.py` | 自包含单文件 HTML:车流通勤 A*、蚂蚁线、寻路 A→B、巡检/涟漪/入场生长 | H5 大屏/演示;录屏可进 CutFlow |
| 寻路数据 | `compute_route.py` | `routes.json`(A* 真实路网最短路径,px 坐标) | 播放器/海报的路径素材 |
| 源探测 | `probe_tiles.py` | 瓦片端点可用性/水印、POI 真实坐标、GCJ 偏移量 | 换底图源、换机器时先验伪 |

## 四、快速开始(以下命令均在本机实测通过)

```bash
# 环境(一次性):pip install requests pillow playwright
#   浏览器不必是 Chrome:VB_BROWSER_PATH > _paths 的 Chrome/Edge > Playwright 自带 chromium
#   首次联网:瓦片进 work/tiles/cache、矢量底料进 work/geo/**,之后离线可复跑

# ① 平面图:广州全城 5 网点(z12,首跑下瓦片约 30 张)
python scripts/map_tiles.py --lat 23.1291 --lon 113.2644 --zoom 12 --width 1600 --height 1200 \
    --style amap --points assets/map/points.guangzhou.json \
    --out work/tmp/flat-gz-z12.png --meta work/tmp/flat-gz-z12.json

# ② 街道级(z17,道路/POI 全可见,~1.1 m/px)
python scripts/map_tiles.py --lat 23.129727 --lon 113.241342 --zoom 17 --width 1600 --height 1200 \
    --style amap --out work/tmp/flat-gz-chenjiaci-z17.png

# ③ 矢量:一次抓五层(建筑/道路/水系/绿地/轨道)→ 2D 四主题 SVG → 2.5D 等轴测
python scripts/fetch_osm_data.py --bbox 23.1055,113.3120,23.1300,113.3350 --out work/geo/cbd-gz
python scripts/svg_map.py --base work/geo/cbd-gz --bbox 23.1055,113.3120,23.1300,113.3350 \
    --width 1600 --theme all --points assets/map/points.cbd.json --out work/tmp/svg-cbd.svg
    #   --theme all → 一出四份:…-dark-tech.svg / -blueprint / -paper / -mono
python scripts/svg_iso.py --base work/geo/cbd-gz --bbox 23.1055,113.3120,23.1300,113.3350 \
    --width 1600 --bearing -24 --pitch 55 --theme dark-tech --out work/tmp/iso-cbd.svg
python scripts/svg_preview.py work/tmp/svg-cbd-dark-tech.svg --out work/tmp/svg-cbd.png --width 1200

# ④ 3D:栅格底图版 / 全矢量主题版
python scripts/render_3d.py --center 23.1145,113.3255 --zoom 15 --camera-zoom 14.6 \
    --pitch 63 --bearing -28 --buildings work/geo/cbd-gz_buildings_gcj02.geojson \
    --points assets/map/points.cbd.json --out work/tmp/v3d-raster.png
python scripts/render_3d_vec.py --center 23.1145,113.3255 --camera-zoom 14.6 --pitch 63 --bearing -28 \
    --theme assets/map/themes/dark-tech.json --base work/geo/cbd-gz \
    --points assets/map/points.cbd.json --out work/tmp/v3d-vec.png

# ⑤ 动画播放器(自包含单文件,双击即开)+ 自动化验收
python scripts/build_player.py        # → assets/map/demo/map-player.html(约 414 KB)
python scripts/test_v7.py             # V1-V12 全绿才算过;--no-shots 只跑断言

# ⑥ 换底图源/换机器前先验伪(瓦片端点、水印、POI 坐标、GCJ 偏移)
python scripts/probe_tiles.py --no-overpass
```

- **换城市**:只改 `--lat/--lon`(或 `--bbox 南,西,北,东`)与 `--zoom`,无其它改动。
- **换网点**:改 `assets/map/points.*.json`(`[{"name","lat","lon"}]`,WGS-84;
  高德地图上拾取的坐标传 `--coord gcj`)。
- **换主题**:`assets/map/themes/*.json`(dark-tech / kv-tech / paper),`render_3d_vec` 换路径即换肤。
- 随技能附带的成品样张(30 件)在 `assets/map/samples/`,可直接当图卡/参照,不必重跑。

## 五、产物去向

| 形态 | 产物 | 去向 |
|---|---|---|
| 静态图 | 平面 PNG / 四主题 SVG / 2.5D 等轴测 SVG / 真 3D PNG | 直接当 artboard 海报的图卡(集成范式:海报 HTML 注入共享 CSS,与文案同版) |
| 动画页 | `assets/map/demo/map-player.html`(自包含单文件) | H5 演示/大屏素材;录屏可进视频管线(CutFlow) |
| 2.5D 轻量 | 海报 HTML 对平面 PNG 做 CSS 透视(零渲染) | artboard 海报主线(见 §六 第 5 条) |

## 六、要点速记(踩坑结晶,细节见 §八 文档)

1. **坐标**:点位一律 **WGS-84 入口**;高德瓦片网格按 **GCJ-02** 索引,脚本内
   `_map_mercator` 本地转换(广州实测偏移 ~546m 东 / ~298m 北)。境外不偏移,
   边界与 eviltransform 完全一致;本机不再需要 `pip install eviltransform`。
2. **首次联网,之后离线**:瓦片缓存 `work/tiles/cache/`、矢量底料 `work/geo/*.geojson`。
   Overpass 忙时返回 HTML,`fetch_osm_data.py` 内置重试(5 次 ×20s);换端点看 `probe_tiles.py`。
   **3D 渲染的瓦片按需补抓**:俯仰相机视野会超出预缓存窗口,渲染页的本地服务对
   缺失瓦片即时现抓(落同一缓存 → 同视角可离线复跑);纯离线复跑时设
   `ARTBOARD_TILE_ONDEMAND=0` 关闭该行为。
   **换 bbox 必重跑 `fetch_osm_data`**:`work/geo/` 是缓存,楼体文件与 `--center`
   必须来自同一 bbox,否则画面里只有远处一小簇楼(表现为"3D 建筑不在中心")。
3. **浏览器**:`VB_BROWSER_PATH` > artboard `_paths`(Chrome/Edge)> Playwright 自带 chromium。
   原模块硬编码 `C:\Program Files\Google\Chrome\...`,本机只有 Edge → 必然启动失败,已修。
4. **播放器架构**:静态 Canvas 栅格化 + 动态 Canvas 特效;**在大 SVG 上逐帧改属性 = 全图重绘,禁**。
5. **2.5D 零渲染**:海报对平面 PNG 做 CSS 透视(`rotateX/skewY` 组合)即可,不必跑 3D 渲染。
6. **交付未知内核**:禁 `?.` / `.at()`(ES5 纪律);页面内置错误红条 + 版本徽标防缓存。
7. **验收方法论**:真实鼠标点击、零注入裸用户长跑、像素采样、**先测空闲帧率基线**;
   `test_v7.py` 的 V9-V12 边界断言按随技能附带的样例画布 1600×1917 写死,换 bbox 后要同步。
8. **零 CDN**(artboard 铁律 2):MapLibre GL v5.9.0 已 vendor 在 `assets/vendor/maplibre/`
   (BSD-3),渲染页由本地 HTTP 服务提供,不联网取库。
9. **代理口径**:所有下载/查询经 `_config.proxy_active()`(默认关 = 直连),`proxy_enabled`
   打开才走 `proxy`;地图脚本已统一,不再各自读 `proxy`。

## 七、合规

高德瓦片直连仅限**内部演示 / 设计样张**;商用请注册高德官方 key(静态图 API)或
CARTO 免费 key。OSM 矢量按 **ODbL** 署名(产物右下角已内置版权条/海报页脚已带)。
**公开出版地图需审图号**,不在本模块范围。

## 八、文档索引(细节与迭代史)

| 文档 | 内容 |
|---|---|
| `docs/map/ITERATION.md` | 全部迭代记录(v1 瓦片 → v7.3 通勤模型),每轮含根因与教训;开头有**旧路径 → 现路径**映射表(**本地留档,不进仓库**) |
| `docs/map/map-rendering-research.md` | 地图渲染技术选型调研(底图源/引擎对比) |
| `docs/map/research-traffic-algorithms.md` | 车流/跟驰/路口行为算法调研 |
| `docs/map/research-v7-route-ants.md` | v7 寻路 + 蚂蚁线 + 走廊图全程依据(V1-V12 验收口径) |
| `docs/map/adr/` | 八项架构决策(底图源/管线/坐标/集成/SVG/Canvas 引擎/走廊图),**本地留档** |
| `docs/map/glossary.md` | 地图模块术语表 |
| `scripts/test_v7.py` | 自动化验收 V1-V12(Playwright,真浏览器长跑) |
