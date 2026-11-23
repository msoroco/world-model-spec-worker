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

from native_camera import CameraRig
from native_capture import capture
from native_media import finalize as finalize_media
from native_scene import create, validate


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
    root = Path(__file__).resolve().parents[2] / ".runtime-work"
    attempt = Path(attempt).resolve()
    if root not in attempt.parents:
        raise ValueError("original Native output must be under .runtime-work")
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
    acquired = None
    errors = []
    restoration = None
    try:
        world.apply_settings(settings)
        scene = create(world, packet_path, plan_path, case_id, carla.Vector3D)
        transform = lambda xyz, rpy: carla.Transform(carla.Location(*xyz), carla.Rotation(*rpy))
        rig = CameraRig(world, scene.ego, packet_path, attempt / "raw", transform)
        acquired = capture(world, scene, rig, attempt, case_id, carla.VehicleControl)
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
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--site-packet", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    print(json.dumps(capture_original(args.attempt, args.site_packet,
                                      args.plan, args.case_id,
                                      host=args.host, port=args.port), indent=2))
