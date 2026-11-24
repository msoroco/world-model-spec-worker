"""Source-gated local Native launch for the nine intersection cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from intersection_observables import _require
from native_scene import validate_route
from native_scene_factory import run_native, validate_camera_packet


class OriginalMotionObserver:
    """Record original controls and motion; leave legal exceptions unresolved."""

    def observe(self, snapshot, actor):
        control = actor.get_control()
        velocity = actor.get_velocity()
        return {
            "source_ref": f"original_native_frame:{snapshot.frame}",
            "activity_observation": {
                "native_frame": snapshot.frame,
                "throttle": float(control.throttle),
                "brake": float(control.brake),
                "hand_brake": bool(control.hand_brake),
                "velocity_xyz_mps": [float(velocity.x), float(velocity.y), float(velocity.z)],
                "stop_stand_park_legal_class": "unresolved",
            },
            "traffic_conflict_observation": None,
            "law_direction_observation": None,
            "officer_direction_observation": None,
            "device_direction_observation": None,
        }


def run_from_environment(case_id, output_dir, host, port, *, api=None, client=None):
    names = ("C110969_ROUTE_PACKET", "C110969_BOUNDARY_PACKET",
             "C110969_CAMERA_PACKET")
    paths = [os.environ.get(name) for name in names]
    _require(all(paths), "reviewed Native route, boundary and camera packet paths required")
    index_path = os.environ.get("C110969_SOURCE_INDEX")
    _require(index_path, "independent reviewed Native source index required")
    index = json.loads(Path(index_path).read_text())
    refs = index.get("packet_refs", {})
    _require(index.get("case_id") == case_id and index.get("reviewer") and
             index.get("review_note") and set(refs) == {"route", "boundary", "camera"},
             "independent source index identity or review missing")
    packets = []
    for kind, path in zip(("route", "boundary", "camera"), paths):
        raw = Path(path).read_bytes()
        ref = refs[kind]
        _require(ref.get("path") == str(Path(path).resolve()) and
                 ref.get("sha256") == hashlib.sha256(raw).hexdigest(),
                 "reviewed Native source packet hash/path differs: " + kind)
        packets.append(json.loads(raw))
    route, boundary, cameras = packets
    _require(route.get("case_id") == case_id, "exact route case differs")
    validate_route(route, boundary, case_id)
    validate_camera_packet(cameras, route, boundary)
    output = Path(output_dir)
    _require(not output.exists() or not any(output.iterdir()),
             "Native attempt output must be empty")
    if api is None:
        import carla as api
    if client is None:
        client = api.Client(host, int(port))
        client.set_timeout(30.0)
    world = client.get_world()
    _require(world.get_map().name == boundary["map_id"], "live Native map differs")
    return run_native(world, api, route, boundary, cameras, OriginalMotionObserver(),
                      case_id, output.name, output)
