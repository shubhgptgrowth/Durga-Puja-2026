"""Street basemap for the route reels: real roads, water, parks and rail from OpenStreetMap, drawn in the reels'
light paper style. The data is the Protomaps basemap build (OpenStreetMap, ODbL), read tile by tile with HTTP range
requests (no CLI, no API key), cached on disk, decoded and drawn with Pillow. Credit on every frame that shows it:
"Map data © OpenStreetMap contributors, Protomaps".

    im = draw(size, to_px, from_px)   # to_px(lat, lng) -> (x, y) pixels; from_px(x, y) -> (lat, lng)

Needs `pmtiles` and `mapbox-vector-tile` (pip). PMTILES_URL overrides the build; BASEMAP_CACHE the tile cache.
"""
import gzip
import json
import math
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

BUILDS = "https://build-metadata.protomaps.dev/builds.json"
CACHE = Path(os.environ.get("BASEMAP_CACHE") or Path.home() / ".cache" / "pujo-basemap")
UA = "pujoparikrama-route-reel/1.0 (+https://pujoparikramaguide.in)"
ATTRIBUTION = "Map data © OpenStreetMap contributors, Protomaps"

PAPER = (251, 243, 228)
STYLE = {  # fill colours on the paper; roads are (casing, fill, width at z15)
    "water": (186, 212, 226), "park": (225, 232, 200), "grass": (230, 235, 206), "cemetery": (226, 228, 210),
    "highway": ((214, 172, 120), (250, 222, 170), 15), "major_road": ((214, 196, 168), (255, 252, 244), 12),
    "medium_road": ((222, 206, 180), (255, 250, 240), 9), "minor_road": (None, (238, 225, 204), 5),
    "path": (None, (240, 230, 214), 2), "rail": (None, (168, 150, 132), 3),
}
NIGHT_PAPER = (9, 11, 20)
NIGHT = {  # the night-map look (marketing/night_route.py): dark land, ink-blue river, faint roads
    "water": (14, 30, 54), "park": (13, 24, 22), "grass": (13, 24, 22), "cemetery": (16, 20, 24),
    "highway": ((20, 22, 34), (70, 58, 74), 15), "major_road": ((18, 20, 32), (52, 54, 72), 12),
    "medium_road": ((16, 18, 30), (40, 42, 60), 9), "minor_road": (None, (29, 31, 46), 5),
    "path": (None, (23, 25, 38), 2), "rail": (None, (64, 54, 78), 3),
}
PARKS = {"park", "grass", "garden", "cemetery", "village_green", "golf_course", "meadow", "pitch", "forest", "wood"}


def _url():
    if os.environ.get("PMTILES_URL"):
        return os.environ["PMTILES_URL"]
    pin = CACHE / "build.txt"  # one build per cache, so every reel in a batch uses the same map
    if pin.exists():
        return pin.read_text().strip()
    req = urllib.request.Request(BUILDS, headers={"User-Agent": UA})
    keys = sorted(b["key"] for b in json.load(urllib.request.urlopen(req, timeout=60)) if b["key"].endswith(".pmtiles"))
    url = f"https://build.protomaps.com/{keys[-1]}"
    CACHE.mkdir(parents=True, exist_ok=True)
    pin.write_text(url)
    return url


class Tiles:
    def __init__(self):
        from pmtiles.reader import Reader
        self.url = _url()
        self.dir = CACHE / Path(self.url).stem
        self.reader = Reader(self._get)

    def _get(self, off, n):
        f = self.dir / "ranges" / f"{off}-{n}"
        if f.exists():
            return f.read_bytes()
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={off}-{off + n - 1}", "User-Agent": UA})
        for attempt in range(4):
            try:
                data = urllib.request.urlopen(req, timeout=90).read()
                break
            except OSError:
                if attempt == 3:
                    raise
        if n < 2_000_000:  # directories and tiles; never cache anything huge
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        return data

    def get(self, z, x, y):
        import mapbox_vector_tile as mvt
        data = self.reader.get(z, x, y)
        if not data:
            return {}
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return mvt.decode(data, default_options={"y_coord_down": True})


def tile_of(lat, lng, z):
    n = 2 ** z
    return ((lng + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def lnglat(z, tx, ty, px, py, extent=4096):
    n = 2 ** z
    x, y = tx + px / extent, ty + py / extent
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))), x / n * 360 - 180


def _rings(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        return [c]
    if t == "MultiPolygon":
        return c
    return []


def _lines(geom):
    t, c = geom["type"], geom["coordinates"]
    return [c] if t == "LineString" else c if t == "MultiLineString" else []


def pick_zoom(bounds):
    """The highest zoom (max 15) that covers the frame in at most ~48 tiles."""
    (la0, lo0), (la1, lo1) = bounds
    for z in range(15, 10, -1):
        x0, y0 = tile_of(la1, lo0, z)
        x1, y1 = tile_of(la0, lo1, z)
        if (int(x1) - int(x0) + 1) * (int(y1) - int(y0) + 1) <= 48:
            return z
    return 11


def draw(size, to_px, from_px, tiles=None, style=None, paper=None):
    """The basemap for a frame of size (w, h). to_px/from_px convert between (lat, lng) and frame pixels.
    style/paper swap the colours (NIGHT, NIGHT_PAPER for the night map)."""
    STYLE_, PAPER_ = style or STYLE, paper or PAPER
    w, h = size
    corners = [from_px(0, 0), from_px(w, 0), from_px(0, h), from_px(w, h)]
    la0, la1 = min(c[0] for c in corners), max(c[0] for c in corners)
    lo0, lo1 = min(c[1] for c in corners), max(c[1] for c in corners)
    z = pick_zoom(((la0, lo0), (la1, lo1)))
    x0, y0 = map(int, tile_of(la1, lo0, z))
    x1, y1 = map(int, tile_of(la0, lo1, z))
    tiles = tiles or Tiles()
    im = Image.new("RGB", (w, h), PAPER_)
    d = ImageDraw.Draw(im)
    zs = 0.55 + 0.45 * (z - 11) / 4  # thinner roads when zoomed out
    polys, roads, places = [], [], []
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            layers = tiles.get(z, tx, ty)
            conv = lambda pts: [to_px(*lnglat(z, tx, ty, px, py)) for px, py in pts]
            for f in layers.get("landuse", {}).get("features", []):
                if f["properties"].get("kind") in PARKS:
                    polys += [("park", conv(r[0])) for r in _rings(f["geometry"]) if r and len(r[0]) > 2]
            for f in layers.get("water", {}).get("features", []):
                polys += [("water", conv(r[0])) for r in _rings(f["geometry"]) if r and len(r[0]) > 2]
                for ln in _lines(f["geometry"]):
                    roads.append(("river", conv(ln)))
            for f in layers.get("roads", {}).get("features", []):
                k = f["properties"].get("kind")
                if k in STYLE_:
                    roads += [(k, conv(ln)) for ln in _lines(f["geometry"]) if len(ln) > 1]
            for f in layers.get("places", {}).get("features", []):
                p = f["properties"]
                if p.get("kind") in ("neighbourhood", "locality", "macrohood") and f["geometry"]["type"] == "Point" and p.get("name"):
                    places.append((p.get("name:en") or p["name"], to_px(*lnglat(z, tx, ty, *f["geometry"]["coordinates"]))))
    for kind, pts in polys:
        d.polygon(pts, fill=STYLE_["water"] if kind == "water" else STYLE_["park"])
    for _, pts in (r for r in roads if r[0] == "river"):
        d.line(pts, fill=STYLE_["water"], width=max(2, int(6 * zs)))
    order = ["path", "minor_road", "rail", "medium_road", "major_road", "highway"]
    for k in order:  # casings first, then fills, so junctions read as one road
        casing, fill, wd = STYLE_[k]
        if casing:
            for kk, pts in roads:
                if kk == k:
                    d.line(pts, fill=casing, width=max(2, int((wd + 4) * zs)), joint="curve")
    for k in order:
        casing, fill, wd = STYLE_[k]
        for kk, pts in roads:
            if kk == k:
                d.line(pts, fill=fill, width=max(1, int(wd * zs)), joint="curve")
    im.info["places"] = places
    im.info["zoom"] = z
    return im
