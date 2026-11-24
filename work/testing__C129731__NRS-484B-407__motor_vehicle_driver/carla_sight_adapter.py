"""CARLA-facing adapter for the original two-direction sight capture.

The caller supplies a reviewed site packet and live actors. This module reads
the loaded OpenDRIVE map, snapshots, actor transforms and CARLA ray hits. The
reviewed station locations are route measurements, never inferred from a fake
straight-line 500-foot radius. Ray clearance is an engineering observation,
not a conclusion about what a driver could see.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from sight_measurement import DIRECTIONS, STATIONS_M
from reversal_phase import HeadingReversalPhase
from reversal_route_controller import RouteFollower


def _xyz(location):
    return {axis: float(getattr(location, axis)) for axis in ("x", "y", "z")}


def load_reviewed_site(path: Path, source_sha256: str) -> dict:
    """Open the immutable site packet by its independently reviewed digest."""
    if (not isinstance(source_sha256, str) or len(source_sha256) != 64 or
            any(ch not in "0123456789abcdef" for ch in source_sha256)):
        raise ValueError("reviewed site SHA-256 required")
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256:
        raise ValueError("reviewed site source hash mismatch")
    site = json.loads(raw)
    if not isinstance(site, dict):
        raise ValueError("reviewed site packet must be an object")
    return site


class CarlaSightAdapter:
    @classmethod
    def from_reviewed_source(cls, world, ego, approach, site_path: Path,
                             site_sha256: str, location_factory, turn_active,
                             before_tick=None):
        return cls(world, ego, approach,
                   load_reviewed_site(site_path, site_sha256),
                   location_factory, turn_active, before_tick)

    def __init__(self, world, ego, approach, reviewed_site: dict,
                 location_factory, turn_active, before_tick=None):
        self.world, self.ego_actor, self.approach_actor = world, ego, approach
        self.site = reviewed_site
        self.location_factory = location_factory
        self.turn_active = turn_active
        self.before_tick = before_tick
        settings = world.get_settings()
        if (settings.synchronous_mode is not True or
                abs(settings.fixed_delta_seconds - 0.05) > 1e-8):
            raise ValueError("original Native world requires synchronous 20 Hz")
        world_map = world.get_map()
        source = world_map.to_opendrive().encode("utf-8")
        self.loaded_digest = hashlib.sha256(source).hexdigest()
        expected = reviewed_site.get("map_source_sha256")
        if expected != self.loaded_digest:
            raise ValueError("loaded OpenDRIVE map differs from reviewed source")
        for role, actor in (("ego", ego), ("approach", approach)):
            expected_id = reviewed_site.get(role + "_vehicle_id")
            expected_blueprint = reviewed_site.get(role + "_blueprint_id")
            if expected_id is not None:
                if str(actor.id) != str(expected_id):
                    raise ValueError("live actor identity differs from reviewed site")
            elif (not isinstance(expected_blueprint, str) or
                  getattr(actor, "type_id", None) != expected_blueprint):
                raise ValueError("live actor blueprint differs from reviewed site")
        if reviewed_site.get("location_kind") not in ("curve", "approach_to_crest", "near_crest"):
            raise ValueError("reviewed curve or crest classification required")
        stations = reviewed_site.get("observer_stations")
        if not isinstance(stations, list):
            raise ValueError("reviewed observer stations required")
        self.stations = {}
        for row in stations:
            key = (row.get("direction"), row.get("station_distance_m"))
            xyz = row.get("location")
            if (key in self.stations or not isinstance(xyz, dict) or
                    not row.get("road_waypoint_source") or
                    type(row.get("road_id")) is not int or
                    type(row.get("lane_id")) is not int or
                    any(type(xyz.get(axis)) not in (int, float) or
                        not math.isfinite(xyz[axis]) for axis in ("x", "y", "z"))):
                raise ValueError("reviewed observer station is incomplete or repeated")
            location = location_factory(xyz["x"], xyz["y"], xyz["z"])
            waypoint = world_map.get_waypoint(location, project_to_road=False)
            if (waypoint is None or waypoint.road_id != row["road_id"] or
                    waypoint.lane_id != row["lane_id"] or
                    math.dist(tuple(_xyz(waypoint.transform.location).values()),
                              tuple(xyz[axis] for axis in ("x", "y", "z"))) > 0.5):
                raise ValueError("reviewed observer station differs from loaded road lane")
            self.stations[key] = row
        if set(self.stations) != {(direction, distance)
                                 for direction in DIRECTIONS for distance in STATIONS_M}:
            raise ValueError("both directions need every reviewed station")
        if not reviewed_site.get("highway_source"):
            raise ValueError("reviewed highway source required")
        terrain_labels = reviewed_site.get("terrain_hit_labels")
        if (not isinstance(terrain_labels, list) or not terrain_labels or
                any(not isinstance(label, str) or not label for label in terrain_labels)):
            raise ValueError("reviewed terrain hit labels required")
        self.terrain_labels = set(terrain_labels)
        target_labels = reviewed_site.get("subject_body_hit_labels")
        if (not isinstance(target_labels, list) or not target_labels or
                any(not isinstance(label, str) or not label for label in target_labels)):
            raise ValueError("reviewed subject body hit labels required")
        self.target_labels = set(target_labels)

    def geometry(self):
        return {"source_kind": "original_native_geometry",
                "map_source_sha256": self.site["map_source_sha256"],
                "loaded_map_sha256": self.loaded_digest,
                "highway_source": self.site["highway_source"],
                "location_kind": self.site["location_kind"],
                "ego_vehicle_id": str(self.ego_actor.id),
                "approach_vehicle_id": str(self.approach_actor.id)}

    def tick(self):
        if self.before_tick is not None:
            self.before_tick()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("CARLA tick and snapshot frame mismatch")
        return {"source_kind": "original_native", "frame": frame,
                "time_s": float(snapshot.timestamp.elapsed_seconds)}

    def ego(self, frame):
        transform = self.ego_actor.get_transform()
        active = self.turn_active(frame["frame"], self.ego_actor)
        if type(active) is not bool:
            raise ValueError("original controller turn phase must be boolean")
        return {"source_kind": "original_native", "vehicle_id": str(self.ego_actor.id),
                "yaw_deg": float(transform.rotation.yaw), "turn_active": active}

    def approach(self, frame):
        return {"source_kind": "original_native", "frame": frame["frame"],
                "time_s": frame["time_s"], "vehicle_id": str(self.approach_actor.id),
                "ego_position": _xyz(self.ego_actor.get_transform().location),
                "approach_position": _xyz(self.approach_actor.get_transform().location)}

    def ray(self, frame, direction, station_m):
        row = self.stations.get((direction, station_m))
        if row is None:
            raise ValueError("unreviewed observer station")
        xyz = row["location"]
        start = self.location_factory(xyz["x"], xyz["y"], xyz["z"] + 1.4)
        vertices = self.ego_actor.bounding_box.get_world_vertices(self.ego_actor.get_transform())
        if len(vertices) != 8:
            raise ValueError("original subject body needs eight Native vertices")
        center = self.ego_actor.get_transform().location
        bounds = {axis: (min(getattr(v, axis) for v in vertices) - 0.2,
                         max(getattr(v, axis) for v in vertices) + 0.2)
                  for axis in ("x", "y", "z")}
        blocked, clear = [], []
        for point in [*vertices, center]:
            hits = self.world.cast_ray(start, point)
            if not isinstance(hits, (list, tuple)):
                raise ValueError("original Native ray hits required")
            distance = math.dist(tuple(_xyz(start).values()), tuple(_xyz(point).values()))
            nearby = []
            for hit in hits:
                hit_location = hit.location
                hit_distance = math.dist(tuple(_xyz(start).values()),
                                         tuple(_xyz(hit_location).values()))
                if hit_distance < distance - 0.05:
                    nearby.append((hit_distance, hit))
            if nearby:
                _, first = min(nearby, key=lambda item: item[0])
                hit_xyz = _xyz(first.location)
                if (str(first.label) in self.target_labels and
                        all(bounds[axis][0] <= hit_xyz[axis] <= bounds[axis][1]
                            for axis in ("x", "y", "z"))):
                    clear.append(True)
                    continue
                if str(first.label) not in self.terrain_labels:
                    raise ValueError("ray occluder is outside reviewed terrain labels")
                blocked.append(f"{first.label}:{hit_xyz['x']:.3f},{hit_xyz['y']:.3f},{hit_xyz['z']:.3f}")
                clear.append(False)
            else:
                clear.append(True)
        return {"source_kind": "original_native", "frame": frame["frame"],
                "time_s": frame["time_s"], "direction": direction,
                "station_distance_m": station_m, "observer_height_m": 1.4,
                "observer_lane_source": row["road_waypoint_source"],
                "target_vehicle_id": str(self.ego_actor.id), "body_point_clear": clear,
                "terrain_hit_id": blocked[0] if not any(clear) else None}


def capture_original_carla(world, ego, approach, site_path: Path,
                           site_sha256: str, location_factory, case_id: str,
                           destination: Path, recording_id: str | None = None,
                           control_factory=None):
    """Acquire one attempt from live actors after the caller starts control.

    The caller owns the CARLA world lease, actor spawning, camera sensors and
    cleanup. Supplying control_factory follows the reviewed case routes before
    each tick. A recorded turn phase comes from live heading;
    the saved capture independently rejects a missing 150-degree reversal.
    """
    from native_sight_capture import capture

    site = load_reviewed_site(site_path, site_sha256)
    before_tick = None
    if control_factory is not None:
        setup = site.get("case_setups", {}).get(case_id)
        if not isinstance(setup, dict):
            raise ValueError("reviewed exact case routes required")
        route_ego = RouteFollower(world.get_map(), setup.get("ego_route", {}),
                                  location_factory, control_factory)
        route_approach = RouteFollower(world.get_map(), setup.get("approach_route", {}),
                                       location_factory, control_factory)

        def before_tick():
            route_ego.apply(ego)
            route_approach.apply(approach)

    adapter = CarlaSightAdapter(world, ego, approach, site, location_factory,
                                HeadingReversalPhase(), before_tick)
    return capture(adapter, case_id, destination, recording_id=recording_id)
