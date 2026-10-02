"""Geometry helpers: distances and walking-route ordering."""
from math import asin, cos, radians, sin, sqrt

from . import config

EARTH_R_M = 6_371_000


def haversine_m(a, b):
    """Great-circle distance in metres between two (lat, lng) pairs."""
    lat1, lng1 = map(radians, a)
    lat2, lng2 = map(radians, b)
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_R_M * asin(sqrt(h))


def walk_m(a, b):
    """Estimated on-foot distance (straight line × lane detour factor)."""
    return haversine_m(a, b) * config.DETOUR_FACTOR


def path_length(points):
    return sum(walk_m(points[i], points[i + 1]) for i in range(len(points) - 1))


def order_route(start, stops):
    """Order `stops` into a short open walking path from `start`.

    Nearest-neighbour seed, then 2-opt improvement. `start` stays fixed and is
    not returned; the result is a permutation of indices into `stops`.
    """
    n = len(stops)
    if n <= 1:
        return list(range(n))

    remaining = set(range(n))
    order, cur = [], start
    while remaining:
        nxt = min(remaining, key=lambda i: haversine_m(cur, stops[i]))
        order.append(nxt)
        remaining.remove(nxt)
        cur = stops[nxt]

    def length(o):
        return path_length([start] + [stops[i] for i in o])

    best = length(order)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                cand_len = length(cand)
                if cand_len < best - 1e-6:
                    order, best, improved = cand, cand_len, True
    return order


def centroid(points):
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))
