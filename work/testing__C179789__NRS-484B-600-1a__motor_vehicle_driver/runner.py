"""Exact Native acquisition entrypoint for the seven speed/condition cases.

Run through the exported runtime so worker_exchange and its output root are set.
The CPU worker only exercises this with fakes; it never starts CARLA here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil

from native_camera import CameraRig
from native_capture import capture
from native_media import finalize as finalize_media
from native_scene import create, validate
from native_count_capture import CountCapture
from native_count_probes import construct as construct_count, validate_packet as validate_count_packet


def check_bundle() -> dict:
    """Check the materialized exact-case bundle without starting Native CARLA."""
    here = Path(__file__).resolve().parent
    config = json.loads((here / "config.json").read_text(encoding="utf-8"))
    plan = json.loads((here / "case-plan.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    if (config.get("assignment_id") != plan.get("assignment_id") or
            config.get("cell_id") != plan.get("cell_id") or
            config.get("law_id") != plan.get("law_id") or
            config.get("actor") != plan.get("actor") or
            case_id not in {item["case_id"] for item in plan["cases"]} or
            config.get("case", {}).get("case_id") != case_id):
        raise ValueError("exact case bundle identity differs from frozen plan")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("exact case bundle must request 900 frames at 20 Hz")
    if config.get("capture_provenance") != "original Native samples required":
        raise ValueError("exact case bundle requires original Native acquisition")
    expected = [("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
    cameras = config.get("cameras", [])
    if [(item.get("name"), item.get("width"), item.get("height"))
            for item in cameras] != expected:
        raise ValueError("exact case bundle camera profile differs")
    return {"case_id": case_id, "bundle_checked": True,
            "physical_acceptance_claimed": False}


def seal_authored_setup(attempt: Path, packet_path: Path, plan_path: Path, case_id: str):
    """Retain the exact authored setup separately from measured Native outcomes."""
    packet, item, _ = validate(packet_path, plan_path, case_id)
    attempt = Path(attempt)
    path = attempt / "authored-setup.json"
    seal_path = attempt / "authored-setup-seal.json"
    if path.exists() or seal_path.exists():
        raise ValueError("retain previous authored setup")
    document = {"case_id": case_id, "variables": item["variables"],
                "vehicle_blueprint": packet["ego_blueprint_id"],
                "travel_direction": packet["travel_direction"],
                "paved_road": packet["paved_road"],
                "camera_profile": packet["camera_profile"],
                "duration_frames": packet["duration_frames"],
                "opendrive_sha256": packet["map_sha256"],
                "source_packet_sha256": hashlib.sha256(Path(packet_path).read_bytes()).hexdigest()}
    if document["paved_road"] is not True or not document["travel_direction"]:
        raise ValueError("reviewed paved road or travel direction missing")
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    seal = {"format": "c179789-authored-setup-v1", "case_id": case_id,
            "sha256": hashlib.sha256(data).hexdigest()}
    seal_path.write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
    return seal


def capture_original(attempt: Path, packet_path: Path, plan_path: Path, case_id: str,
                     *, host: str = "127.0.0.1", port: int = 2000):
    """Connect only in the local Native runtime; retain failures and restore world."""
    attempt = Path(attempt).resolve()
    roots = [parent for parent in attempt.parents if parent.name == ".runtime-work"]
    if len(roots) != 1:
        raise ValueError("original Native output must be under .runtime-work")
    root = roots[0]
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not output_root:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    output_root = Path(output_root).resolve()
    if not (output_root == root or root in output_root.parents) or not (
            output_root == attempt or output_root in attempt.parents):
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    import carla
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    saved = snapshot(client)
    settings = copy.copy(saved["settings"])
    settings.synchronous_mode = True
    settings.no_rendering_mode = False
    settings.fixed_delta_seconds = .05
    scene = None
    rig = None
    count_construction = None
    acquired = None
    errors = []
    restoration = None
    try:
        world.apply_settings(settings)
        scene = create(world, packet_path, plan_path, case_id, carla.Vector3D)
        count_path = os.environ.get("SCENARIO_NATIVE_COUNT_PACKET")
        if count_path:
            count_source = json.loads(Path(count_path).read_text(encoding="utf-8"))
            validate_count_packet(Path(count_path), case_id=case_id,
                                  kind=count_source.get("kind"),
                                  expected_count=count_source.get("expected_count"))
            count_construction = construct_count(
                world, Path(count_path), case_id=case_id,
                kind=count_source["kind"], expected_count=count_source["expected_count"],
                transform_factory=lambda **v: carla.Transform(
                    carla.Location(x=v["x"], y=v["y"], z=v["z"]),
                    carla.Rotation(yaw=v["yaw"])))
        transform = lambda xyz, rpy: carla.Transform(carla.Location(*xyz), carla.Rotation(*rpy))
        rig = CameraRig(world, scene.ego, packet_path, attempt / "raw", transform)
        acquired = capture(
            world, scene, rig, attempt, case_id, carla.VehicleControl,
            count_capture=CountCapture(count_construction) if count_construction else None,
            count_reader=(lambda actor: {"actor_id": actor.id, "type_id": actor.type_id,
                                         "alive": actor.is_alive}) if count_construction else None)
        if count_construction:
            target = attempt / "count-probe-packet.json"
            if target.exists():
                raise ValueError("retain previous reviewed count packet")
            shutil.copy2(count_path, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != count_construction["packet_sha256"]:
                raise ValueError("reviewed count packet changed during Native capture")
    except Exception as error:
        errors.append("capture: " + str(error))
    finally:
        if rig is not None:
            try:
                rig.close()
            except Exception as error:
                errors.append("camera cleanup: " + str(error))
        if scene is not None:
            try:
                scene.close()
            except Exception as error:
                errors.append("actor cleanup: " + str(error))
        if count_construction is not None:
            for actor in reversed(count_construction["actors"]):
                try:
                    actor.destroy()
                except Exception as error:
                    errors.append("count actor cleanup: " + str(error))
        try:
            restoration = restore(client, saved)
        except Exception as error:
            errors.append("world restoration: " + str(error))
    attempt.mkdir(parents=True, exist_ok=True)
    media = None
    if not errors:
        try:
            media = finalize_media(attempt)
            seal_authored_setup(attempt, packet_path, plan_path, case_id)
        except Exception as error:
            errors.append("saved media/setup: " + str(error))
    status = {"case_id": case_id, "capture": acquired, "media": media,
              "restoration": restoration,
              "errors": errors, "physical_acceptance_claimed": False}
    (attempt / "native-run-status.json").write_text(json.dumps(status, indent=2) + "\n")
    if errors:
        raise ValueError("; ".join(errors))
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--site-packet", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_bundle(), indent=2))
    else:
        here = Path(__file__).resolve().parent
        attempt = args.output_dir or args.attempt
        site_packet = args.site_packet or Path(os.environ.get(
            "SCENARIO_NATIVE_SITE_PACKET", str(here / "native-site-packet.json")))
        plan = args.plan or here / "case-plan.json"
        config = json.loads((here / "config.json").read_text(encoding="utf-8"))
        case_id = args.case_id or config.get("selected_case_id")
        if not attempt or not case_id:
            parser.error("Native capture requires an output directory and selected exact case")
        if not site_packet.is_file():
            parser.error("reviewed native-site-packet.json is required for original capture")
        if not plan.is_file():
            parser.error("selected case-plan.json is required for original capture")
        os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(Path(attempt).resolve()))
        print(json.dumps(capture_original(attempt, site_packet,
                                          plan, case_id,
                                          host=args.host, port=args.port), indent=2))
