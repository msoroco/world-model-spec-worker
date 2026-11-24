"""CPU geometry checks for the proposed alley and adjacent striped access aisle.

The scene coordinates are construction targets, not proof of Native realization.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _box(raw, name):
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError(name + " requires [xmin,ymin,xmax,ymax]")
    if any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in raw):
        raise ValueError(name + " has nonfinite coordinates")
    x0, y0, x1, y1 = raw
    if x0 >= x1 or y0 >= y1:
        raise ValueError(name + " has nonpositive area")
    return x0, y0, x1, y1


def validate(scene):
    alley = _box(scene["alley_xy_m"], "alley")
    aisle = _box(scene["access_aisle_xy_m"], "access aisle")
    parking = _box(scene["designated_parking_xy_m"], "designated parking")
    route = scene["ego_route_xy_m"]
    if len(route) < 2 or any(len(point) != 2 for point in route):
        raise ValueError("ego route needs at least two XY points")
    width = scene["ego_width_m"]
    if not isinstance(width, (float, int)) or width <= 0:
        raise ValueError("invalid ego width")
    if aisle[1] != alley[3] or parking[1] != aisle[3]:
        raise ValueError("access aisle must be beside alley and designated parking")
    if not (alley[0] <= aisle[0] < aisle[2] <= alley[2] and aisle[0] <= parking[0] < parking[2] <= aisle[2]):
        raise ValueError("access aisle and parking must share the alley segment")
    stripes = scene["contrasting_stripes_xy_m"]
    if len(stripes) < 3:
        raise ValueError("access aisle requires multiple contrasting stripes")
    for stripe in stripes:
        sx0, sy0, sx1, sy1 = _box(stripe, "stripe")
        if not (aisle[0] <= sx0 < sx1 <= aisle[2] and aisle[1] <= sy0 < sy1 <= aisle[3]):
            raise ValueError("contrasting stripe lies outside access aisle")
    margin = width / 2
    for point in route:
        x, y = point
        if not (alley[0] + margin <= x <= alley[2] - margin and
                alley[1] + margin <= y <= alley[3] - margin):
            raise ValueError("ego body does not clear alley route")
    route_length = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                       for a, b in zip(route, route[1:]))
    if route_length < 90:
        raise ValueError("proposed route is shorter than 45 seconds at nominal 2 m/s")
    if scene["surface_role"] != "access_aisle_adjacent_to_designated_handicapped_parking":
        raise ValueError("ordinary travel lane is not the access aisle")
    return {"route_clearance_verified_offline": True, "route_length_m": route_length,
            "stripe_count": len(stripes),
            "access_aisle_adjacent_to_parking": True, "native_realization_confirmed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(json.loads(args.scene.read_text())), sort_keys=True))


if __name__ == "__main__":
    main()
