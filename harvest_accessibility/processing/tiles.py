"""Elevation tiles: source list, decoding, and assembly into a DEM.

Shared by the main algorithm (which can fetch a DEM itself) and by the
standalone fetch algorithm (which writes one to a file for reuse).
"""

import hashlib
import math
import os
import tempfile
import urllib.error
import urllib.request

TILE_SIZE = 256
MERCATOR_ORIGIN = 20037508.342789244
MAX_TILES = 400

# (label, url template, max zoom, attribution).  Tile path order differs between
# services -- the GSJ set puts y before x -- so the template carries it.
# Only combinations that actually return tiles are listed: the published table
# is wider than the service (land and mixed answer 404).
SOURCES = [
    (
        "VIRTUAL SHIZUOKA (~0.5 m, Shizuoka only)",
        "https://tiles.gsj.jp/tiles/elev/shizuoka/{z}/{y}/{x}.png",
        18,
        "静岡県 VIRTUAL SHIZUOKA / 産業技術総合研究所 シームレス標高タイル (CC BY 4.0)",
    ),
    (
        "GSI DEM5A (~4 m, where surveyed)",
        "https://tiles.gsj.jp/tiles/elev/gsidem5a/{z}/{y}/{x}.png",
        15,
        "国土地理院 基盤地図情報数値標高モデル DEM5A / 産業技術総合研究所 シームレス標高タイル",
    ),
    (
        "GSI DEM10B (~8 m, nationwide)",
        "https://tiles.gsj.jp/tiles/elev/gsidem/{z}/{y}/{x}.png",
        14,
        "国土地理院 基盤地図情報数値標高モデル DEM10B / 産業技術総合研究所 シームレス標高タイル",
    ),
]

NODATA = -9999.0


class TileError(Exception):
    """Anything that stops a DEM being built from tiles."""


def tile_of(lon, lat, zoom):
    n = 2 ** zoom
    x = int(math.floor((lon + 180.0) / 360.0 * n))
    lat_r = math.radians(max(min(lat, 85.05112878), -85.05112878))
    y = int(math.floor((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n))
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def native_resolution(zoom, lat_deg):
    """Ground resolution of a tile pixel, in metres."""
    pixel = 2 * MERCATOR_ORIGIN / (2 ** zoom) / TILE_SIZE
    return pixel * math.cos(math.radians(lat_deg))


def decode(arr):
    """Decode the GSJ elevation PNG encoding into metres.

    r' = r < 128 ? r : r - 256;  h = (65536 r' + 256 g + b) * 0.01
    Fully transparent pixels carry no elevation.
    """
    import numpy as np
    a = arr.astype("int32")
    r, g, b = a[0], a[1], a[2]
    rp = np.where(r < 128, r, r - 256)
    h = (65536.0 * rp + 256.0 * g + b) * 0.01
    if a.shape[0] > 3:
        h = np.where(a[3] == 0, float("nan"), h)
    return h


def cache_path(source_idx, zoom, x0, y0, x1, y1, crs_authid, res):
    """A stable name for one fetched-and-warped DEM.

    Tuning the model means running it repeatedly over the same block; without
    this every run would re-download the same tiles.
    """
    key = "|".join(str(v) for v in
                   (source_idx, zoom, x0, y0, x1, y1, crs_authid, round(res, 4)))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    folder = os.path.join(tempfile.gettempdir(), "harvest_accessibility_dem")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "dem_%s.tif" % digest)


def build_dem(extent_wgs, source_idx, zoom, target_crs_wkt, target_crs_authid,
              resolution=0.0, out_path=None, use_cache=True, log=None,
              progress=None, cancelled=None):
    """Fetch tiles covering extent_wgs and write a DEM in the target CRS.

    extent_wgs is (xmin, ymin, xmax, ymax) in degrees.  Returns the file path.
    Leaving web mercator is not cosmetic: horizontal distances there are
    stretched by 1/cos(latitude), so slope taken straight from mercator pixels
    comes out about 20% too gentle at Japanese latitudes -- and the felling
    model branches on a slope threshold.
    """
    import numpy as np
    from osgeo import gdal

    def say(msg):
        if log is not None:
            log(msg)

    label, url_tpl, max_zoom, attribution = SOURCES[source_idx]
    zoom = zoom or max_zoom
    xmin, ymin, xmax, ymax = extent_wgs
    x0, y0 = tile_of(xmin, ymax, zoom)
    x1, y1 = tile_of(xmax, ymin, zoom)
    n_tiles = (x1 - x0 + 1) * (y1 - y0 + 1)
    if n_tiles > MAX_TILES:
        raise TileError(
            "That area needs %d tiles. Reduce the zoom level or split the area."
            % n_tiles)

    lat_mid = (ymin + ymax) / 2.0
    if resolution <= 0:
        # Resampling an 8 m source onto a 0.5 m grid invents detail that is not
        # there, so default to what the tiles actually carry.
        resolution = native_resolution(zoom, lat_mid)

    cached = cache_path(source_idx, zoom, x0, y0, x1, y1, target_crs_authid, resolution)
    if use_cache and out_path is None and os.path.exists(cached):
        say("Reusing the DEM already fetched for this area (%s)." % cached)
        return cached
    destination = out_path or cached

    say("%s at zoom %d: %d tiles" % (label, zoom, n_tiles))
    width = (x1 - x0 + 1) * TILE_SIZE
    height = (y1 - y0 + 1) * TILE_SIZE
    mosaic = np.full((height, width), np.nan, dtype="float32")

    fetched = 0
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            if cancelled is not None and cancelled():
                raise TileError("Cancelled.")
            url = url_tpl.format(z=zoom, x=tx, y=ty)
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "QGIS harvest_accessibility"})
                data = urllib.request.urlopen(req, timeout=30).read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue  # no tile here: sea, or outside this source's coverage
                raise TileError("Tile request failed (%s): %s" % (exc.code, url))
            except Exception as exc:
                raise TileError(
                    "Could not reach the tile service (%s). Supply a DEM file "
                    "instead if this machine has no network access." % exc)
            vsi = "/vsimem/harvest_dem_tile_%d_%d.png" % (tx, ty)
            gdal.FileFromMemBuffer(vsi, data)
            tile = gdal.Open(vsi)
            arr = tile.ReadAsArray() if tile is not None else None
            tile = None
            gdal.Unlink(vsi)
            if arr is None or arr.ndim != 3:
                continue
            oy = (ty - y0) * TILE_SIZE
            ox = (tx - x0) * TILE_SIZE
            mosaic[oy:oy + TILE_SIZE, ox:ox + TILE_SIZE] = decode(arr)
            fetched += 1
            if progress is not None:
                progress(100.0 * fetched / n_tiles)

    if fetched == 0:
        raise TileError(
            "No tiles were returned for this area. %s may not cover it -- try a "
            "nationwide source." % label)
    say("Fetched %d of %d tiles." % (fetched, n_tiles))

    mosaic = np.where(np.isnan(mosaic), NODATA, mosaic)
    mem = gdal.GetDriverByName("MEM").Create("", width, height, 1, gdal.GDT_Float32)
    band = mem.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(mosaic)
    pixel = 2 * MERCATOR_ORIGIN / (2 ** zoom) / TILE_SIZE
    mem.SetGeoTransform((
        -MERCATOR_ORIGIN + x0 * TILE_SIZE * pixel, pixel, 0,
        MERCATOR_ORIGIN - y0 * TILE_SIZE * pixel, 0, -pixel
    ))
    from osgeo import osr
    merc = osr.SpatialReference(); merc.ImportFromEPSG(3857)
    mem.SetProjection(merc.ExportToWkt())

    say("Reprojecting to %s at %.2f m..." % (target_crs_authid, resolution))
    gdal.Warp(destination, mem, dstSRS=target_crs_wkt,
              xRes=resolution, yRes=resolution,
              resampleAlg="bilinear", dstNodata=NODATA)
    mem = None
    say("Source: %s" % attribution)
    return destination
