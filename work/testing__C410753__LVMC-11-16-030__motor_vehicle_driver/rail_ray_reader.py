"""Original Native crossing and bidirectional 400-foot railway sight rays."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

EXTENT_M = 400 * .3048


def _xyz(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("reviewed or original rail ray coordinate invalid")
    return tuple(float(v) for v in value)


def _samples(rows):
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("reviewed railway 400-foot ray sample inventory missing")
    stations = []
    targets = []
    for row in rows:
        station = row.get("station_m")
        if type(station) not in (int, float) or not math.isfinite(station):
            raise ValueError("reviewed railway ray station invalid")
        stations.append(float(station))
        targets.append(_xyz(row.get("xyz")))
    if (stations[0] > .5 or stations[-1] < EXTENT_M - .5 or
            any(b <= a or b - a > 5 for a, b in zip(stations, stations[1:]))):
        raise ValueError("reviewed railway 400-foot ray samples have a gap")
    return targets


class ReviewedRailRayReader:
    def __init__(self, site, source_path, world, location_factory):
        raw = Path(source_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != site.get("rail_ray_geometry_source_sha256"):
            raise ValueError("reviewed railway ray geometry source hash differs")
        source = json.loads(raw)
        if (source.get("source_kind") != "railway_sight_geometry" or
                not source.get("reviewer") or not source.get("source_citation") or
                source.get("road_sha256") != site.get("road_sha256")):
            raise ValueError("reviewed railway ray geometry identity missing")
        self.crossing = _xyz(source.get("crossing_xyz"))
        self.minus = _samples(source.get("rail_minus_400ft"))
        self.plus = _samples(source.get("rail_plus_400ft"))
        if not callable(location_factory) or not hasattr(world, "cast_ray"):
            raise ValueError("original Native railway ray capability missing")
        self.world = world
        self.location_factory = location_factory
        self.last_frame = None

    def _cast(self, start, target):
        end = self.location_factory(*target)
        origin = _xyz((start.x, start.y, start.z))
        distance = math.dist(origin, target)
        if distance < .1:
            raise ValueError("railway ray target coincides with observer")
        hits = self.world.cast_ray(start, end)
        if not isinstance(hits, (list, tuple)):
            raise ValueError("original Native railway ray hits missing")
        trace = []
        blocked = False
        for hit in hits:
            location = hit.location
            xyz = _xyz((location.x, location.y, location.z))
            hit_distance = math.dist(origin, xyz)
            if hit_distance < distance - .05:
                blocked = True
            trace.append({"xyz": xyz, "distance_m": hit_distance,
                          "label": str(getattr(hit, "label", "")),
                          "actor_id": getattr(hit, "actor_id", None)})
        return not blocked, {"target_xyz": target, "hits": trace}

    def __call__(self, frame, snapshot, ego):
        if (type(frame) is not int or snapshot.frame != frame or
                (self.last_frame is not None and frame != self.last_frame + 1)):
            raise ValueError("original railway sight frame join differs")
        location = ego.get_transform().location
        eye = self.location_factory(location.x, location.y, location.z + 1.4)
        crossing, crossing_trace = self._cast(eye, self.crossing)
        minus = [self._cast(eye, target) for target in self.minus]
        plus = [self._cast(eye, target) for target in self.plus]
        self.last_frame = frame
        return {"crossing": crossing,
                "rail_minus_400ft": all(clear for clear, _ in minus),
                "rail_plus_400ft": all(clear for clear, _ in plus),
                "source_trace": {"original_frame": frame,
                                 "observer_convention": "ego_location_plus_1.4m",
                                 "crossing": crossing_trace,
                                 "rail_minus_400ft": [trace for _, trace in minus],
                                 "rail_plus_400ft": [trace for _, trace in plus]}}
