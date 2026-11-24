"""Exact C215286 reverse-crosswalk Native entrypoint and offline identity check."""

import argparse
import json
import math
import os
import shutil
from pathlib import Path

TARGETS = {"reverse_clear": "disjoint", "reverse_tangent": "contact", "reverse_overlap": "overlap"}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def check(scene):
    if scene.get("law_id") != "NRS-484B-113-2" or scene.get("cell_id") != "C215286":
        raise ValueError("wrong frozen law or cell")
    if scene.get("actor") != "motor_vehicle_driver":
        raise ValueError("wrong frozen actor")
    key = scene.get("case_id", "").split("__")[-1]
    if TARGETS.get(key) != scene.get("target_physical_relation"):
        raise ValueError("wrong exact case target")
    if scene.get("fps") != 20 or scene.get("camera_names") != list(VIEWS):
        raise ValueError("missing common four-camera capture plan")
    return {"case_id": scene["case_id"], "target": TARGETS[key],
            "native_source_packet_required": True, "physical_realization": "pending"}


def _copy(source, destination):
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream, Path(source).open("rb") as original:
        shutil.copyfileobj(original, stream)


def _project(attempt, scene, packet):
    """Copy sealed acquisition to attempt root and derive original trace rows."""
    from crosswalk_delivery import measure

    root = Path(attempt)
    source = root / "capture"
    names = ("video_frames.jsonl", "reviewed-crosswalk-source.json",
             "original-site-packet.json", "original-site-source.json",
             "channels/reverse-body-crosswalk.jsonl")
    for name in names:
        _copy(source / name, root / name)
    rows = [json.loads(line) for line in (root / "channels/reverse-body-crosswalk.jsonl").read_text().splitlines()]
    context = json.loads((root / "reviewed-crosswalk-source.json").read_text())
    measured = measure(rows, source_id=context["source_id"],
                       map_sha256=packet["map_sha256"],
                       crosswalk_source=packet["crosswalk_source"],
                       vehicle_actor_id=context["vehicle_actor_id"])
    target = scene["target_physical_relation"]
    target_rows = [row for row in measured["frames"] if row["relation"] == target
                   and row["reverse_gear"] and row["reverse_speed_mps"] > .05]
    destination = packet["reverse_route_xy"][-1]
    distance = math.dist(rows[-1]["position_xy"], destination)
    trace = [{"frame": row["native_frame"], "time_s": row["time_s"],
              "position": {"x": row["position_xy"][0],
                           "y": row["position_xy"][1], "z": 0.0},
              "position_m": [*row["position_xy"], 0],
              "velocity_mps": row["velocity_mps"],
              "speed_mps": math.hypot(*row["velocity_mps"][:2]),
              "heading_deg": row["heading_deg"]} for row in rows]
    reverse = [{"frame": row["native_frame"], "time_s": row["time_s"],
                "body_vertices_m": row["body_vertices_m"],
                "heading_deg": row["heading_deg"],
                "velocity_mps": row["velocity_mps"]} for row in rows]
    for name, values in (("trace.jsonl", trace), ("reverse_history.jsonl", reverse)):
        with (root / name).open("x") as stream:
            for value in values:
                stream.write(json.dumps(value, sort_keys=True) + "\n")
    (root / "crosswalk_context.json").write_text(json.dumps({
        "map_sha256": packet["map_sha256"],
        "crosswalk_source": packet["crosswalk_source"],
        "crosswalk_polygon_xy": packet["crosswalk_polygon_xy"],
        "district_source": packet["district_source"],
        "highway_boundary_source": packet["highway_boundary_source"],
        "crosswalk_marking_source": packet["crosswalk_marking_source"]
    }, sort_keys=True) + "\n")
    (root / "marked-crosswalk-source.json").write_text(json.dumps({
        "marked_crosswalk_source": packet["crosswalk_source"],
        "map_sha256": packet["map_sha256"],
        "crosswalk_polygon_xy": packet["crosswalk_polygon_xy"]
    }, sort_keys=True) + "\n")
    with (root / "reverse-body-crosswalk.jsonl").open("x") as stream:
        for row, relation in zip(rows, measured["frames"]):
            stream.write(json.dumps({"time_s": row["time_s"],
                                     "value": {"relation": relation["relation"],
                                               "body_polygon_xy": row["body_polygon_xy"],
                                               "crosswalk_polygon_xy": row["crosswalk_polygon_xy"],
                                               "reverse_gear": row["reverse_gear"],
                                               "reverse_speed_mps": relation["reverse_speed_mps"]}},
                                    sort_keys=True) + "\n")
    return measured, target_rows, distance


def native(scene, output_dir, host, port):
    from carla_cameras import OriginalCameras
    from encode_original import encode
    from native_capture import capture
    from site_packet import check_world, read
    from worker_exchange.native_output import seal_capture, write_result
    from worker_exchange.world_restore import restore, snapshot
    import carla

    checked = check(scene)
    site_path = os.environ.get("CROSSWALK_SITE_PACKET")
    if not site_path:
        raise ValueError("CROSSWALK_SITE_PACKET original reviewed site path required")
    packet, _, _ = read(site_path, checked["case_id"])
    root = Path(output_dir)
    if not root.is_dir():
        raise ValueError("materialized attempt directory required")
    client = carla.Client(host, int(port))
    client.set_timeout(20)
    saved = snapshot(client)
    world = client.get_world()
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-6:
        raise ValueError("dedicated Native world must run synchronously at 20 Hz")
    check_world(world, packet)
    cameras = None
    failure = None
    restoration = None
    try:
        cameras = OriginalCameras(world, carla, packet)
        capture_dir = root / "capture"
        capture_dir.mkdir()
        captured = capture(world, carla, site_path, checked["case_id"],
                           capture_dir, cameras.read)
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            if cameras is not None:
                cameras.close()
        finally:
            restoration = restore(client, saved)
            if failure is not None:
                (root / "native-run-status.json").write_text(json.dumps({
                    "errors": [type(failure).__name__ + ": " + str(failure)],
                    "restoration": restoration, "physical_acceptance_claimed": False
                }, indent=2) + "\n")
    encoded = encode(root, checked["case_id"])
    measured, target_rows, distance = _project(root, scene, packet)
    completion = distance <= .25
    target_check = {"target": "reverse_body_crosswalk_relation",
                    "requested": checked["target"],
                    "measured": {"target_original_frames": [row["frame"] for row in target_rows],
                                 "observed_relations": sorted({row["relation"] for row in measured["frames"]})},
                    "method": "source-hashed original 20 Hz reverse body and crossing polygon",
                    "tolerance": {"polygon_contact_m": 1e-8, "reverse_speed_mps": .05},
                    "matched": bool(target_rows), "physical_cause_confirmed": False,
                    "cause_evidence": []}
    check_source = {"reverse_frames": captured["source_hashes"]["reverse_frames"]}
    checks = {"setup": {"status": "met", "method": "900 original frames and four source cameras",
                        "sources": {"site_packet": packet["map_sha256"]}, "intervals": []},
              "target": {"status": "met" if target_rows else "not_met",
                         "method": "original body/crossing polygon while backing",
                         "sources": check_source, "intervals": []},
              "maneuver": {"status": "met" if completion else "not_met",
                           "method": "original route endpoint distance",
                           "sources": check_source, "intervals": [],
                           "engineering_endpoint_radius_m": .25,
                           "endpoint_distance_m": distance}}
    result = {"case_id": checked["case_id"],
              "measured_values": {"original_frame_count": captured["frame_count"],
                                  "backing_target_frame_count": len(target_rows),
                                  "endpoint_distance_m": distance},
              "target_checks": [target_check], "physical_checks": checks,
              "setup_confirmed": True, "behavior_attempted": True,
              "maneuver_completed": completion,
              "termination_reason": "planned_900_frame_reverse_interval_completed",
              "physical_failure_flags": [name for name, failed in (
                  ("target_not_observed", not target_rows),
                  ("reverse_goal_not_reached", not completion)) if failed],
              "trace_reference": "trace.jsonl",
              "video_references": ["raw.mkv", *[name + ".mkv" for name in VIEWS]],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": json.loads((root / "construction.json").read_text())["recording_description"],
              "recording_evidence": [{"name": "reverse_body_crosswalk", "unit": "structured",
                                      "reference": "reverse-body-crosswalk.jsonl"},
                                     {"name": "marked_crosswalk_source", "unit": "metadata",
                                      "reference": "marked-crosswalk-source.json"}],
              "realized_observables": {"reverse_body_crosswalk": {
                  "relations": [row["relation"] for row in measured["frames"]],
                  "original_source": "channels/reverse-body-crosswalk.jsonl"}},
              "physical_acceptance_claimed": False}
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": checked["case_id"],
        "site_source_sha256": captured["source_hashes"]["site_source"]
    }, sort_keys=True) + "\n")
    write_result(root, result)
    seal_capture(root, frames=900, restoration=restoration, errors=[],
                 encoder_exit_codes={name: 0 for name in encoded["views"]},
                 context={"map_sha256": packet["map_sha256"],
                          "original_camera_identity": "video_frames.jsonl"})
    print(json.dumps({"case_id": checked["case_id"], "original_frames": 900,
                      "physical_target_met": bool(target_rows),
                      "physical_acceptance_claimed": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene = json.loads(Path("scene.json").read_text())
    if args.check:
        print(json.dumps(check(scene)))
    else:
        if not args.output_dir:
            parser.error("--output-dir required")
        native(scene, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
