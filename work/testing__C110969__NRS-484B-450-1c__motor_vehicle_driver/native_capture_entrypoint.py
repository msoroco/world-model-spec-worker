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


def check_materialized_attempt(output, case_id):
    """Accept only the pinned launcher's fresh package inventory."""
    output = Path(output)
    _require(output.is_dir(), "materialized Native attempt directory required")
    construction_path = output / "construction.json"
    selection_path = output / "candidate-selection.json"
    _require(construction_path.is_file() and selection_path.is_file(),
             "materialized Native construction and selection required")
    construction = json.loads(construction_path.read_text())
    selection = json.loads(selection_path.read_text())
    _require(construction.get("case_id") == case_id and
             selection.get("case_id") == case_id and
             selection.get("construction_sha256") == hashlib.sha256(
                 construction_path.read_bytes()).hexdigest(),
             "materialized Native case or selection differs")
    expected = {item["path"] for item in construction["files"]}
    expected.update({"construction.json", "candidate-selection.json"})
    actual = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    _require(actual == expected, "Native attempt contains missing or prior acquisition files")
    for item in construction["files"]:
        path = (output / item["path"]).resolve()
        _require(path.is_relative_to(output.resolve()) and
                 path.read_text() == item["content"],
                 "materialized Native implementation changed")
    return selection


def finalize_native_capture(output, case_id, world, original_settings):
    from native_export import export
    from worker_exchange.native_output import seal_capture

    exported = export(output, case_id)
    restored = world.get_settings()
    verified = (restored.synchronous_mode == original_settings.synchronous_mode and
                restored.fixed_delta_seconds == original_settings.fixed_delta_seconds)
    _require(verified, "Native world settings restoration differs")
    seal_capture(output, frames=exported['frame_count'],
                 restoration={'restored': True, 'method': 'post-cleanup Native world settings readback'},
                 errors=[], encoder_exit_codes={name: 0 for name in exported['videos']},
                 context={'case_id': case_id, 'native_export_sha256': hashlib.sha256(
                     (Path(output)/'native-export-receipt.json').read_bytes()).hexdigest()})
    return exported


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
    check_materialized_attempt(output, case_id)
    if api is None:
        import carla as api
    if client is None:
        client = api.Client(host, int(port))
        client.set_timeout(30.0)
    world = client.get_world()
    _require(world.get_map().name == boundary["map_id"], "live Native map differs")
    original_settings = world.get_settings()
    for kind, path in zip(("route", "boundary", "camera"), paths):
        (output / ("reviewed-" + kind + ".json")).write_bytes(Path(path).read_bytes())
    (output/'reviewed-source-index.json').write_bytes(Path(index_path).read_bytes())
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source_index_sha256': hashlib.sha256(Path(index_path).read_bytes()).hexdigest(),
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False
    }, sort_keys=True)+'\n')
    try:
        captured = run_native(world, api, route, boundary, cameras, OriginalMotionObserver(),
                              case_id, output.name, output)
        exported = finalize_native_capture(output, case_id, world, original_settings)
        return {'case_id': case_id, 'native_capture': captured,
                'export': exported, 'physical_acceptance_claimed': False}
    except BaseException as error:
        (output/'native-run-status.json').write_text(json.dumps({
            'errors': [{'type': type(error).__name__, 'message': str(error)}],
            'physical_acceptance_claimed': False
        }, sort_keys=True)+'\n')
        raise
