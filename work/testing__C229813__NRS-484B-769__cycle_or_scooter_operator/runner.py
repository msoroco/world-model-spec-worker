"""Source-gated Native acquisition of original cycle and rider-arm motion."""

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path

from signal_scene import ASSIGNMENT, case_parts, construct, load_reviewed_scene, require

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRAMES = 900


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _context(scene, case_id):
    route = scene["right_turn_route"]
    def heading(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        require(length > 0, "reviewed turn heading degenerate")
        return [dx / length, dy / length]
    return {
        "case_id": case_id, "map_sha256": scene["map_opendrive_source_sha256"],
        "operator_vehicle_kind": scene["operator_vehicle_kind"],
        "operator_identity_source": scene["operator_identity_source_sha256"],
        "roadway_status": "roadway",
        "highway_status_source": scene["highway_status_source_sha256"],
        "roadway_polygon": scene["roadway_polygon"],
        "shoulder_polygon": scene["shoulder_polygon"],
        "roadway_geometry_source": scene["roadway_geometry_source_sha256"],
        "shoulder_geometry_source": scene["shoulder_geometry_source_sha256"],
        "right_turn_route": {
            "waypoint_source": scene["turn_route_source_sha256"],
            "first_heading": heading(route[0], route[1]),
            "last_heading": heading(route[-2], route[-1])},
        "requested_signal_posture": scene["requested_signal_posture"],
        "reviewed_source_hashes": {key: scene[key] for key in scene if key.endswith("_source_sha256")},
    }


def run(adapter, scene, config, output, packet_sha256):
    """Record one original episode; no target label is treated as a readback."""
    case_id = config["selected_case_id"]
    _, posture = case_parts(case_id)
    require(config.get("rate_hz") == 20 and config.get("duration_s") == 45 and
            config.get("frame_count") == FRAMES and
            tuple(camera["name"] for camera in config["cameras"]) == VIEWS,
            "20 Hz four-camera capture contract differs")
    scene = dict(scene, requested_signal_posture=posture)
    built = construct(adapter, scene, case_id)
    output = Path(output)
    try:
        adapter.begin_four_camera_capture(VIEWS, config["cameras"],
                                          scene["camera_sites"], scene["rider_arm_rig"],
                                          built["owned"], output)
        frame_rows = []
        signal_rows = []
        for index in range(FRAMES):
            frame = adapter.tick()
            require(type(frame) is int and
                    (not frame_rows or frame == frame_rows[-1]["frame"] + 1),
                    "original Native frame sequence incomplete")
            # This method must read live operator contact, heading and actual
            # shoulder/elbow/wrist joints after each tick. A requested pose is
            # not admissible as a value returned here.
            observed = adapter.read_original_signal_frame(frame, built)
            require(isinstance(observed, dict) and
                    all(key in observed for key in
                        ("operator_vehicle_contact_point", "operator_heading", "right_arm")),
                    "original rider arm and roadway readback missing")
            row = {"frame": frame, "time_s": round(index / 20, 3), **observed}
            signal_rows.append(row)
            adapter.record_original_trace_frame(frame, index / 20, built, output)
            camera_ids = adapter.capture_frame_identities(frame)
            require(isinstance(camera_ids, dict) and set(camera_ids) == set(VIEWS) and
                    all(camera_ids[name] == frame for name in VIEWS),
                    "four original camera frame identities differ")
            frame_rows.append({"frame": frame, "video_frame": index,
                               "carla_frame": frame, "native_frame": frame,
                               "time_s": round(index / 20, 3),
                               "camera_frames": camera_ids})
        adapter.finish_four_camera_capture(output)
        require(adapter.camera_frame_counts() == {name: FRAMES for name in VIEWS},
                "four-camera original frame count incomplete")
        require(adapter.native_source_kind() == "original_native_capture",
                "original Native source provenance missing")
        (output / "signal-readback.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in signal_rows),
            encoding="utf-8")
        (output / "video_frames.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_rows),
            encoding="utf-8")
        _write_json(output / "signal-context.json", _context(scene, case_id))
        _write_json(output / "source-receipt.json", {
            "assignment_id": ASSIGNMENT, "case_id": case_id,
            "context_sha256": _sha(output / "signal-context.json"),
            "trace_sha256": _sha(output / "signal-readback.jsonl"),
            "frame_count": FRAMES, "fps": 20, "diagnostic_fixture": False,
            "reviewed_scene_packet_sha256": packet_sha256})
        names = ("config.json", "signal-context.json", "source-receipt.json",
                 "signal-readback.jsonl", "trace.jsonl", "video_frames.jsonl") + tuple(
                     name + ".mkv" for name in VIEWS)
        files = {}
        for name in names:
            target = output / name
            require(target.is_file() and not target.is_symlink(),
                    "original capture source missing: " + name)
            files[name] = {"sha256": _sha(target)}
        _write_json(output / "original-sources.json", {
            "source_kind": "original_native_capture",
            "accepted_original_source": True,
            "case_id": case_id, "frame_count": FRAMES,
            "camera_frame_counts": adapter.camera_frame_counts(),
            "reviewed_scene_packet_sha256": packet_sha256,
            "files": files})
        return {"case_id": case_id, "frame_count": FRAMES,
                "first_frame": frame_rows[0]["frame"],
                "last_frame": frame_rows[-1]["frame"],
                "original_sources_sha256": _sha(output / "original-sources.json"),
                "physical_acceptance_claimed": False, "legal_verdict": None}
    finally:
        if hasattr(adapter, "cleanup"):
            adapter.cleanup()
        for actor in reversed(built["owned"]):
            adapter.destroy(actor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--scene-packet", type=Path,
                        default=os.getenv("C229813_SCENE_PACKET"))
    parser.add_argument("--source-root", type=Path,
                        default=os.getenv("C229813_SOURCE_ROOT"))
    parser.add_argument("--adapter-module", default="native_adapter")
    parser.add_argument("--host", default=os.getenv("CARLA_HOST"))
    parser.add_argument("--port", default=os.getenv("CARLA_PORT"))
    args = parser.parse_args()
    config = json.loads((Path(__file__).parent / "config.json").read_text())
    case_parts(config["selected_case_id"])
    if args.check:
        print(config["selected_case_id"])
        return
    require(args.output_dir and args.scene_packet and args.source_root and
            args.host and args.port, "reviewed scene and CARLA endpoint required")
    scene, packet_sha256 = load_reviewed_scene(
        args.scene_packet, args.source_root, config["selected_case_id"])
    adapter = importlib.import_module(args.adapter_module).create_adapter(
        config, args.host, int(args.port))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import restore, snapshot
    saved_world = snapshot(adapter.client)
    error = None
    restoration = None
    result = None
    try:
        result = run(adapter, scene, config, args.output_dir, packet_sha256)
    except Exception as failure:
        error = failure
    finally:
        try:
            restoration = restore(adapter.client, saved_world)
        except Exception as failure:
            error = error or failure
    if error is not None:
        _write_json(args.output_dir / "native-run-status.json", {
            "errors": [str(error)], "restoration": restoration,
            "physical_acceptance_claimed": False})
        raise error
    codes = adapter.encoder_exit_codes()
    require(set(codes) == set(VIEWS) and all(code == 0 for code in codes.values()),
            "four camera encoders did not close cleanly")
    seal_capture(args.output_dir, frames=FRAMES, restoration=restoration,
                 errors=[], encoder_exit_codes=codes,
                 context={"case_id": config["selected_case_id"],
                          "reviewed_scene_packet_sha256": packet_sha256})
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
