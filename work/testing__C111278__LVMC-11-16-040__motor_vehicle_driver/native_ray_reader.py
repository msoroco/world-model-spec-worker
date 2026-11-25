"""Original Native sight rays for every reviewed entering street arm.

The operator supplies a live per-arm traffic census with its own source hash.
This reader does not infer that a clear ray settles a driver's legal view.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class RayReadError(ValueError):
    pass


def _inside(xy, polygon):
    x, y = xy
    inside = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


class NativeTrafficCensus:
    """Enumerate live Native actors in reviewer supplied entering-arm polygons."""

    def __init__(self, world, geometry: dict, ego_id):
        polygons = {}
        for arm, row in geometry.items():
            vertices = row.get("traffic_arm_polygon_xy")
            if (not isinstance(vertices, list) or len(vertices) < 3 or
                    any(not isinstance(v, list) or len(v) != 2 or
                        any(type(n) not in (int, float) or not math.isfinite(n) for n in v)
                        for v in vertices)):
                raise RayReadError("reviewed entering-arm traffic polygon missing")
            polygons[arm] = [tuple(map(float, vertex)) for vertex in vertices]
        if ego_id is None or not hasattr(world, "get_actors"):
            raise RayReadError("original Native actor census source missing")
        self.world = world
        self.polygons = polygons
        self.ego_id = str(ego_id)

    def __call__(self, frame, snapshot, arm):
        if snapshot.frame != frame or arm not in self.polygons:
            raise RayReadError("traffic census frame or arm differs")
        actors = []
        for actor in self.world.get_actors():
            kind = str(getattr(actor, "type_id", ""))
            if (str(getattr(actor, "id", "")) == self.ego_id or
                    not (kind.startswith("vehicle.") or kind.startswith("walker.")) or
                    not getattr(actor, "is_alive", False)):
                continue
            location = actor.get_transform().location
            xyz = _xyz((location.x, location.y, location.z))
            bounds = getattr(actor, "bounding_box", None)
            if bounds is None or not hasattr(bounds, "get_world_vertices"):
                raise RayReadError("original traffic body bounds missing")
            vertices = bounds.get_world_vertices(actor.get_transform())
            if len(vertices) != 8:
                raise RayReadError("original traffic body needs eight vertices")
            bbox = [_xyz((v.x, v.y, v.z)) for v in vertices]
            matched = [name for name, polygon in self.polygons.items()
                       if _inside(xyz[:2], polygon)]
            if len(matched) > 1:
                raise RayReadError("original traffic actor belongs to multiple entering arms")
            if matched == [arm]:
                actors.append({"id": str(actor.id), "type_id": kind,
                               "xyz": xyz, "bbox_xyz": bbox})
        actors.sort(key=lambda item: item["id"])
        source = {"frame": frame, "arm": arm, "actors": actors,
                  "source_kind": "original_native_actor_census"}
        digest = hashlib.sha256(json.dumps(source, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        return {**source, "source_sha256": digest}


def _xyz(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise RayReadError("reviewed or original ray coordinate invalid")
    return tuple(float(v) for v in value)


def _hit_xyz(hit):
    location = hit.location
    return _xyz((location.x, location.y, location.z))


class ReviewedRayReader:
    def __init__(self, site: dict, source_path: Path, world, traffic_reader,
                 location_factory, ego_id=None):
        raw = Path(source_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != site.get("arm_sight_geometry_source_sha256"):
            raise RayReadError("reviewed arm geometry source hash differs from site")
        source = json.loads(raw)
        if (source.get("source_kind") != "arm_sight_geometry" or
                not source.get("reviewer") or not source.get("source_citation") or
                source.get("entering_arms") != site.get("entering_arms")):
            raise RayReadError("reviewed arm geometry claim differs from site")
        geometry = source.get("arm_geometry")
        arms = site.get("entering_arms")
        if not isinstance(geometry, dict) or set(geometry) != set(arms):
            raise RayReadError("every entering arm needs reviewed sight geometry")
        for arm in arms:
            row = geometry[arm]
            if not isinstance(row, dict) or type(row.get("sampled_extent_m")) not in (int, float):
                raise RayReadError("reviewed arm extent missing")
            if not math.isfinite(row["sampled_extent_m"]) or row["sampled_extent_m"] < 30.48:
                raise RayReadError("reviewed arm extent shorter than 100 feet")
            _xyz(row.get("intersection_xyz"))
            samples = row.get("traffic_corridor_xyz")
            if not isinstance(samples, list) or len(samples) < 2:
                raise RayReadError("reviewed traffic corridor samples missing")
            stations = []
            for sample in samples:
                if not isinstance(sample, dict) or type(sample.get("station_m")) not in (int, float):
                    raise RayReadError("reviewed traffic corridor station missing")
                station = sample["station_m"]
                if not math.isfinite(station):
                    raise RayReadError("reviewed traffic corridor station invalid")
                stations.append(float(station))
                _xyz(sample.get("xyz"))
            if (stations[0] > 0.5 or stations[-1] < 30.48 or
                    any(b <= a or b - a > 5.0 for a, b in zip(stations, stations[1:]))):
                raise RayReadError("reviewed 100-foot traffic corridor has a sampling gap")
        if traffic_reader is None:
            traffic_reader = NativeTrafficCensus(world, geometry, ego_id)
        if not callable(traffic_reader) or not callable(location_factory):
            raise RayReadError("live Native traffic reader and location factory required")
        self.geometry = geometry
        self.world = world
        self.traffic_reader = traffic_reader
        self.location_factory = location_factory
        self.last_frame = None

    def _cast(self, start, target, ignored_actors=()):
        target_xyz = _xyz(target)
        end = self.location_factory(*target_xyz)
        origin = _xyz((start.x, start.y, start.z))
        target_distance = math.dist(origin, target_xyz)
        if target_distance < 0.1:
            raise RayReadError("ray target coincides with original eye")
        hits = self.world.cast_ray(start, end)
        if not isinstance(hits, (list, tuple)):
            raise RayReadError("original Native ray hits missing")
        observed = []
        blocked = False
        for hit in hits:
            position = _hit_xyz(hit)
            distance = math.dist(origin, position)
            label = str(getattr(hit, "label", ""))
            actor_id = getattr(hit, "actor_id", None)
            observed.append({"label": label, "actor_id": actor_id,
                             "xyz": position, "distance_m": distance})
            belongs_to_visible_actor = False
            for actor in ignored_actors:
                vertices = actor.get("bbox_xyz")
                if not isinstance(vertices, list) or len(vertices) != 8:
                    raise RayReadError("original traffic body bounds missing")
                bounds = [_xyz(v) for v in vertices]
                if (str(actor_id) == str(actor["id"]) or
                        all(min(v[axis] for v in bounds) - 0.2 <= position[axis] <=
                            max(v[axis] for v in bounds) + 0.2 for axis in range(3))):
                    belongs_to_visible_actor = True
            if distance < target_distance - 0.05 and not belongs_to_visible_actor:
                blocked = True
        return blocked, {"target_xyz": target_xyz, "hits": observed}

    def __call__(self, frame: int, snapshot, ego, arms: list[str]) -> dict:
        if type(frame) is not int or snapshot.frame != frame:
            raise RayReadError("ray frame differs from original snapshot")
        if self.last_frame is not None and frame != self.last_frame + 1:
            raise RayReadError("original ray frame gap")
        if set(arms) != set(self.geometry) or len(arms) != len(self.geometry):
            raise RayReadError("entering arm inventory differs from reviewed geometry")
        transform = ego.get_transform()
        eye = transform.location
        start = self.location_factory(eye.x, eye.y, eye.z + 1.4)
        out = {}
        for arm in arms:
            row = self.geometry[arm]
            census = self.traffic_reader(frame, snapshot, arm)
            if (not isinstance(census, dict) or census.get("frame") != frame or
                    census.get("arm") != arm or not census.get("source_sha256") or
                    not isinstance(census.get("actors"), list) or
                    census.get("source_kind") != "original_native_actor_census"):
                raise RayReadError("original per-arm traffic census missing")
            census_source = dict(census)
            sealed = census_source.pop("source_sha256")
            if hashlib.sha256(json.dumps(census_source, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode()).hexdigest() != sealed:
                raise RayReadError("original traffic census seal mismatch")
            observed_ids = []
            targets = [(sample["xyz"], None) for sample in row["traffic_corridor_xyz"]]
            for actor in census["actors"]:
                if not isinstance(actor, dict) or not actor.get("id"):
                    raise RayReadError("original traffic actor identity missing")
                observed_ids.append(str(actor["id"]))
                targets.append((_xyz(actor.get("xyz")), actor))
            if len(set(observed_ids)) != len(observed_ids):
                raise RayReadError("duplicate original traffic actor")
            intersection_blocked, intersection_trace = self._cast(start, row["intersection_xyz"])
            traffic_traces = [self._cast(
                start, target,
                [target_actor] if target_actor is not None else census["actors"])
                for target, target_actor in targets]
            traffic_blocked = any(blocked for blocked, _ in traffic_traces)
            source = {"frame": frame, "arm": arm, "census": census,
                      "intersection": intersection_trace,
                      "traffic": [trace for _, trace in traffic_traces]}
            digest = hashlib.sha256(json.dumps(source, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
            out[arm] = {"observer_convention": "ego_reference_1.4m_arm_rays",
                        "sampled_extent_m": row["sampled_extent_m"],
                        "intersection_view": "blocked" if intersection_blocked else "clear",
                        "traffic_view": "blocked" if traffic_blocked else "clear",
                        "ray_frame_source_sha256": digest,
                        "traffic_census_source_sha256": census["source_sha256"],
                        "traffic_actor_ids": observed_ids,
                        "ray_hit_trace": source}
        self.last_frame = frame
        return out
