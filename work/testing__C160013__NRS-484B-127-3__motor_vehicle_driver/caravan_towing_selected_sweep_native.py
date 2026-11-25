"""CARLA-lazy C160013 towing-combination capture candidate.

A locally reviewed Native packet is required. Capture creates original sources;
local saved processing must determine whether the planned motion actually occurred.
"""
import argparse
import hashlib
import json
import math
import os
from contextlib import ExitStack
from pathlib import Path

from caravan_cameras import PROFILE, source_cameras
from caravan_capture import CAMERAS, capture_frames, validate_site
from caravan_construction import spawn_caravan
from caravan_video import FFV1Writer
from caravan_combination_native import spawn_drawn_unit
from caravan_combination_capture import CombinationHistory

ASSIGNMENT = "testing__C160013__NRS-484B-127-3__motor_vehicle_driver"
CASES = {'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0000': 'stop_before',
         'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0001': 'occupy',
         'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0002': 'occupy'}


def _transform(carla, row):
    if not isinstance(row, dict):
        raise ValueError("Reviewed Native transform required")
    values = {}
    for key in ("x", "y", "z", "yaw_deg"):
        value = row.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Finite reviewed Native transform required: " + key)
        values[key] = float(value)
    return carla.Transform(carla.Location(x=values["x"], y=values["y"], z=values["z"]),
                           carla.Rotation(yaw=values["yaw_deg"]))


def _install_review(output, bundle):
    if not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction")
    bundle = Path(bundle).resolve(strict=True)
    packet_path = bundle / "site_packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    sources = ["site_packet.json"]
    for key in ("business_district_source", "caravan_membership_source",
                "route_source", "lane_source"):
        ref = packet.get(key)
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            raise ValueError("Reviewed source reference missing: " + key)
        sources.append(ref["path"])
    drawn = packet.get("drawn_unit")
    design_ref = packet.get("towing_design_source")
    if not isinstance(drawn, dict) or not isinstance(design_ref, dict):
        raise ValueError("Reviewed drawn-unit design and source required")
    if not isinstance(design_ref.get("path"), str) or not isinstance(design_ref.get("sha256"), str):
        raise ValueError("Original towing design source reference required")
    sources.append(design_ref["path"])
    # Validate the complete bundle before writing into the Native attempt.
    validate_site(packet, bundle, packet.get("native_map_id"))
    copies = []
    for name in sources:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Unsafe reviewed source path")
        if name != "site_packet.json" and relative.parts[0] in (
                "construction.json", "video_frames.jsonl", "caravan_history.jsonl",
                "road_context.json", "native-exit.json"):
            raise ValueError("Reviewed source collides with Native output")
        source = (bundle / relative).resolve()
        target = (output / relative).resolve()
        if not source.is_relative_to(bundle) or not target.is_relative_to(output):
            raise ValueError("Reviewed source escapes attempt")
        data = source.read_bytes()
        if not data or len(data) > 2 * 1024 * 1024:
            raise ValueError("Invalid reviewed source size")
        data.decode("utf-8")
        if name == design_ref["path"] and hashlib.sha256(data).hexdigest() != design_ref["sha256"]:
            raise ValueError("Changed original towing design source")
        copies.append((target, data))
    for target, data in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return packet


def capture(args):
    if args.case_id not in CASES:
        raise ValueError("Exact selected caravan case required")
    output = Path(args.output_dir).resolve()
    packet = _install_review(output, args.review_bundle)
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    if config.get("selected_case_id") != args.case_id:
        raise ValueError("Materialized construction selected another caravan case")
    if not isinstance(config.get("required_atoms"), list):
        raise ValueError("Materialized required atom inventory missing")
    cap = config.get("target_speed_cap_mps")
    if type(cap) not in (int, float) or not math.isfinite(cap) or not 0 < cap <= 8:
        raise ValueError("Finite bounded Native target speed cap required")
    packet["target_speed_mps"] = min(packet["target_speed_mps"], float(cap))
    packet["required_atoms"] = config["required_atoms"]
    if CASES[args.case_id] == "occupy":
        if packet.get("target_lane_id") != config.get("physical_completion", {}).get("destination_lane"):
            raise ValueError("Reviewed entrant destination lane differs from exact physical plan")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot_world(client)
    world = client.get_world()
    frames = 0
    encoders = {}
    error = None
    try:
        validate_site(packet, output, world.get_map().name)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        vehicle_rows = packet.get("caravan_vehicles")
        entrant_row = packet.get("entering_vehicle")
        if not isinstance(vehicle_rows, list) or len(vehicle_rows) < 3 or not isinstance(entrant_row, dict):
            raise ValueError("Reviewed three-caravan-plus-entrant spawn plan required")
        library = world.get_blueprint_library()
        vehicles = [(library.find(row["blueprint_id"]), _transform(carla, row["transform"]))
                    for row in vehicle_rows]
        with spawn_caravan(world, vehicles) as caravan:
            entrant = world.try_spawn_actor(library.find(entrant_row["blueprint_id"]),
                                            _transform(carla, entrant_row["transform"]))
            if entrant is None:
                raise ValueError("Native entering vehicle spawn failed")
            tow_stack = ExitStack()
            try:
                unit = tow_stack.enter_context(spawn_drawn_unit(world, carla, caravan[0], packet["drawn_unit"]))
                for actor in caravan + [entrant, unit]:
                    waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
                    if waypoint is None or waypoint.road_id != packet["road_id"]:
                        raise ValueError("Native participant is not on reviewed road")
                camera_rows = packet.get("camera_transforms")
                if not isinstance(camera_rows, dict) or set(camera_rows) != set(CAMERAS):
                    raise ValueError("Four reviewed Native camera transforms required")
                poses = {name: _transform(carla, row) for name, row in camera_rows.items()}
                context = {key: packet[key] for key in
                           ("native_map_id", "highway_id", "road_id", "outside_business_district",
                            "caravan_or_motorcade", "roadway_polygon_xy_m", "road_forward_xy",
                            "business_district_source", "caravan_membership_source",
                            "route_source", "lane_source")}
                relationship = {"drawing_actor_id": caravan[0].id,
                                "drawn_actor_id": unit.id,
                                "drawn_unit_has_motive_power": False,
                                "towing_design_source_sha256": packet["towing_design_source"]["sha256"]}
                relationship_data = (json.dumps(relationship, sort_keys=True) + "\n").encode()
                (output / "towing-relationship.json").write_bytes(relationship_data)
                context["towing_relationship_source"] = {
                    "path": "towing-relationship.json",
                    "sha256": hashlib.sha256(relationship_data).hexdigest(),
                    "review_status": "reviewed_native_relationship"}
                context["towing_design_source"] = packet["towing_design_source"]
                context["control_target_speed_mps"] = packet["target_speed_mps"]
                (output / "road_context.json").write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
                (output / "caravan_context.json").write_text(json.dumps({
                    "native_map_id": packet["native_map_id"], "road_id": packet["road_id"],
                    "highway_id": packet["highway_id"],
                    "selected_gap_index": packet["selected_gap_index"],
                    "lane_source": packet["lane_source"],
                    "physical_completion_note": "Engineering maneuver event, not a legal danger threshold"
                }, indent=2) + "\n", encoding="utf-8")
                with source_cameras(world, entrant, poses) as sensors, ExitStack() as stack:
                    for name, (width, height) in PROFILE.items():
                        encoders[name] = stack.enter_context(FFV1Writer(output / (name + ".mkv"), width, height))
                    mapping = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                    history_file = stack.enter_context((output / "caravan_history.jsonl").open("x", encoding="utf-8", buffering=1))
                    history = CombinationHistory(history_file, caravan[0], unit)
                    helper = PipelineCapture(client, entrant, output, args.case_id,
                                             required_observations=packet.get("required_atoms", []))
                    try:
                        result = capture_frames(world, carla, caravan, entrant, sensors, encoders,
                                                mapping, history, helper, packet,
                                                outcome=CASES[args.case_id], frames=900)
                        frames = result["frames"]
                    finally:
                        helper.close()
            finally:
                tow_stack.close()
                entrant.destroy()
    except BaseException as caught:
        error = caught
        raise
    finally:
        restoration = restore(client, saved)
        if error is None:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: writer.exit_code for name, writer in encoders.items()},
                         context={"caravan_site_review": packet["site_review_status"],
                                  "physical_acceptance_claimed": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case-id")
    parser.add_argument("--output-dir")
    parser.add_argument("--review-bundle")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"assignment_id": ASSIGNMENT, "case_ids": list(CASES),
                          "cpu_check_passed": True, "carla_started": False}))
        return
    if not args.output_dir:
        raise ValueError("Materialized output required")
    if not args.case_id:
        config = json.loads((Path(args.output_dir) / "config.json").read_text(encoding="utf-8"))
        args.case_id = config.get("selected_case_id")
    if not args.review_bundle:
        args.review_bundle = os.environ.get("C160013_REVIEW_BUNDLE")
    if not args.review_bundle:
        raise ValueError("C160013_REVIEW_BUNDLE with original reviewed Native site required")
    capture(args)


if __name__ == "__main__":
    main()
