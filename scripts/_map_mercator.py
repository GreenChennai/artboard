"""Web-mercator tile math + China datum (GCJ-02) conversion.

地图模块内部共享模块(artboard `_` 前缀 = 不进 Agent 上下文)。
被 map_tiles.py(平面拼接)、svg_map.py / svg_iso.py(矢量)、render_3d.py /
render_3d_vec.py(2.5D/3D)、fetch_osm_data.py、compute_route.py 引用。
所有对外 lat/lon 参数一律十进制角度。

Datum rule (verified 2026-09-23, Guangzhou, offset ~546m E / 298m N):
  - OSM/Overpass/CARTO/OpenFreeMap ... WGS-84
  - AMap (Gaode) tiles & static API  ... GCJ-02  -> must convert WGS-84 input

GCJ-02 变换为**本地实现**(算法与 eviltransform 同源),不再依赖 pip 包:
技能要能离线/换机复跑,装不上的第三方包不该成为地图链路的隐性前置。
等价性已对拍(见 docs/map/ITERATION.md 或 CHANGELOG):与 eviltransform 相比
wgs2gcj 最大偏差 < 1e-9 度(≈0.1mm),gcj2wgs 为迭代精确反解。
"""
import math

TILE = 256  # logical tile size in px (AMap scale=2 returns denser pixels, same coverage)


def deg2num(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def num2deg(x, y, z):
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def world_px(lat, lon, z):
    """Global pixel coordinates at zoom z (256px tile grid)."""
    x, y = deg2num(lat, lon, z)
    return x * TILE, y * TILE


def px_to_latlon(px_x, px_y, z):
    return num2deg(px_x / TILE, px_y / TILE, z)


def meters_per_pixel(lat, z):
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


# --- datum conversion (local GCJ-02 implementation, eviltransform-equivalent) ---

_A = 6378245.0                  # Krasovsky 1940 长半轴
_EE = 0.00669342162296594323    # 第一偏心率平方


def _out_of_china(lat, lon):
    """国境粗判:境外不做偏移。边界与 eviltransform 完全一致
    (lon 72.004~137.8347 / lat 0.8293~55.8271),否则同一坐标在本模块
    与历史产物之间会差 0.001 度量级。"""
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _delta(lat, lon):
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return dlat, dlon


def wgs2gcj(lat, lon):
    """WGS-84 -> GCJ-02(火星坐标)。境外原样返回。"""
    if _out_of_china(lat, lon):
        return lat, lon
    dlat, dlon = _delta(lat, lon)
    return lat + dlat, lon + dlon


def gcj2wgs(lat, lon):
    """GCJ-02 -> WGS-84:迭代精确反解(与 eviltransform.gcj2wgs_exact 同量级)。"""
    if _out_of_china(lat, lon):
        return lat, lon
    wlat, wlon = lat, lon
    for _ in range(10):
        glat, glon = wgs2gcj(wlat, wlon)
        dlat, dlon = glat - lat, glon - lon
        wlat -= dlat
        wlon -= dlon
        if abs(dlat) < 1e-11 and abs(dlon) < 1e-11:
            break
    return wlat, wlon


def to_datum(lat, lon, datum):
    """Convert WGS-84 input to the datum a tile source natively uses."""
    if datum == "gcj":
        return wgs2gcj(lat, lon)
    return lat, lon


def from_datum(lat, lon, datum):
    """Convert tile-source-native coords back to WGS-84."""
    if datum == "gcj":
        return gcj2wgs(lat, lon)
    return lat, lon
