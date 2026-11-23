"""Native entrypoint for exact railroad-crossing stop constructions.

The worker CPU proof uses fakes. CARLA connects only inside capture_original.
Saved media conversion and legal review start after Native exit and owner release.
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
from native_scene import create, inspect


def native_process_identity() -> dict:
    """Retain the Linux PID generation so later release rejects a live owner."""
    pid = os.getpid()
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    ticks = int(stat.rsplit(")", 1)[1].split()[19])
    return {"pid": pid, "proc_start_ticks": ticks}


def retain_site_sources(attempt: Path, packet_path: Path, plan_path: Path,
                        case_id: str) -> Path:
    """Copy reviewed source bytes into the immutable original attempt."""
    packet, _, _ = inspect(packet_path, plan_path, case_id)
    destination = attempt / "site"
    if destination.exists():
        raise ValueError("retain previous original site packet")
    destination.mkdir()
    target = destination / "packet.json"
    shutil.copyfile(packet_path, target)
    for spec in packet["sources"].values():
        relative = Path(spec["path"])
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(packet_path).parent / relative, output)
    inspect(target, plan_path, case_id)
    return target


def capture_original(attempt: Path, packet_path: Path, plan_path: Path,
                     case_id: str, *, host="127.0.0.1", port=2000):
    """Retain one original attempt, closing cameras, actors and world on error."""
    attempt = Path(attempt).resolve()
    private_roots = [parent for parent in attempt.parents if parent.name == ".runtime-work"]
    if len(private_roots) != 1:
        raise ValueError("original Native attempt must stay under .runtime-work")
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not output_root or not Path(output_root).resolve().is_relative_to(private_roots[0]):
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    if not attempt.is_relative_to(Path(output_root).resolve()):
        raise ValueError("Native attempt differs from exported output root")
    inspect(packet_path, plan_path, case_id)
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
    scene = rig = acquired = restoration = None
    errors = []
    try:
        world.apply_settings(settings)
        transform = lambda x, y, z, yaw: carla.Transform(
            carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))
        scene = create(world, packet_path, plan_path, case_id, transform)
        camera_transform = lambda location, rotation: carla.Transform(
            carla.Location(*location),
            carla.Rotation(roll=rotation[0], pitch=rotation[1], yaw=rotation[2]))
        rig = CameraRig(world, scene.ego, packet_path, attempt / "raw",
                        camera_transform)
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
    retained_packet = None
    if not errors:
        try:
            retained_packet = retain_site_sources(attempt, packet_path, plan_path, case_id)
        except Exception as error:
            errors.append("site retention: " + str(error))
    status = {"case_id": case_id, "capture": acquired,
              "restoration": restoration, "errors": errors,
              "native_process": native_process_identity(),
              "site_packet_sha256": hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(),
              "retained_site_packet": "site/packet.json" if retained_packet else None,
              "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
    (attempt / "native-run-status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise ValueError("; ".join(errors))
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--site-packet", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    plan = args.plan or here / "case-plan.json"
    packet = args.site_packet or Path(os.environ.get(
        "SCENARIO_NATIVE_SITE_PACKET", str(here / "native-site-packet.json")))
    if not packet.is_file():
        parser.error("reviewed crossing native-site-packet.json is required")
    if not args.case_id:
        parser.error("exact case ID is required")
    os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(args.output_dir.resolve()))
    status = capture_original(args.output_dir, packet, plan, args.case_id,
                              host=args.host, port=args.port)
    status_path = args.output_dir / "native-run-status.json"
    exit_path = args.output_dir / "native-exit.json"
    if exit_path.exists():
        raise ValueError("retain previous Native exit receipt")
    exit_path.write_text(json.dumps({
        "event": "native_exit_pending_process_termination",
        "case_id": args.case_id,
        "native_process": status["native_process"],
        "native_run_status_sha256": hashlib.sha256(status_path.read_bytes()).hexdigest(),
        "physical_acceptance_claimed": False}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
