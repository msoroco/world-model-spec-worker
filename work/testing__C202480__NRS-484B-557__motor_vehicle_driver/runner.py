"""Source-gated Native entrypoint for the exact NRS 484B.557 case matrix."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from native_construction import create, verify_production_site
from native_camera import CameraRig
from native_capture import capture

HERE = Path(__file__).resolve().parent


def check_construction(config_path: Path, plan_path: Path, packet_path: Path | None = None) -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    cases = [item for item in plan["cases"] if item["case_id"] == case_id]
    if (len(cases) != 1 or config.get("assignment_id") != plan.get("assignment_id") or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            (plan.get("law_id"), plan.get("cell_id"), plan.get("actor")) or
            set(config.get("supported_case_ids", [])) != {item["case_id"] for item in plan["cases"]} or
            config.get("case") != cases[0]):
        raise ValueError("exact case construction identity differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("exact capture cadence or duration differs")
    expected = (("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
    if tuple((c.get("name"), c.get("width"), c.get("height")) for c in config.get("cameras", [])) != expected:
        raise ValueError("four-view capture plan differs")
    if packet_path is not None:
        verify_production_site(packet_path, cases[0])
    return {"case_id": case_id, "construction_checked": True,
            "reviewed_site_checked": packet_path is not None,
            "physical_acceptance_claimed": False}


def _private_attempt(path: Path) -> Path:
    path = Path(path).resolve()
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if (not output or ".runtime-work" not in path.parts or
            not path.is_relative_to(Path(output).resolve())):
        raise ValueError("Native output requires exported .runtime-work output root")
    if path.exists():
        raise ValueError("retain previous Native attempt; choose a fresh output")
    return path


def capture_original(attempt: Path, packet_path: Path, config_path: Path,
                     plan_path: Path, *, host: str, port: int) -> dict:
    attempt = _private_attempt(attempt)
    checked = check_construction(config_path, plan_path, packet_path)
    config = json.loads(config_path.read_text())
    case = config["case"]
    import carla
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import seal_capture

    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    saved = snapshot(client)
    settings = copy.copy(saved["settings"])
    settings.synchronous_mode = True
    settings.no_rendering_mode = False
    settings.fixed_delta_seconds = .05
    scene = camera = acquired = restoration = None
    errors = []
    try:
        world.apply_settings(settings)
        def ego_transform(x, y, normal, z=None):
            return carla.Transform(carla.Location(x=x, y=y,
                z=float(json.loads(packet_path.read_text())["ego_spawn_z_m"] if z is None else z)),
                carla.Rotation(yaw=math.degrees(math.atan2(normal[1], normal[0]))))
        scene = create(world, packet_path, case, ego_transform)
        def camera_transform(location, rotation):
            return carla.Transform(carla.Location(x=location[0], y=location[1], z=location[2]),
                carla.Rotation(roll=rotation[0], pitch=rotation[1], yaw=rotation[2]))
        camera = CameraRig(world, scene["ego"], packet_path, attempt / "raw", camera_transform)
        acquired = capture(world, scene, camera, attempt, case, carla.VehicleControl)
    except Exception as error:
        errors.append("capture: " + str(error))
    finally:
        if camera is not None:
            try:
                camera.close()
            except Exception as error:
                errors.append("camera cleanup: " + str(error))
        if scene is not None:
            try:
                if scene.get("conflict_actor") is not None:
                    scene["conflict_actor"].destroy()
                scene["ego"].destroy()
            except Exception as error:
                errors.append("actor cleanup: " + str(error))
        try:
            restoration = restore(client, saved)
        except Exception as error:
            errors.append("world restoration: " + str(error))
    attempt.mkdir(parents=True, exist_ok=True)
    status = {"case_id": checked["case_id"], "capture": acquired,
              "restoration": restoration, "errors": errors,
              "site_packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
              "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
    (attempt / "native-run-status.json").write_text(json.dumps(status, indent=2) + "\n")
    if errors:
        raise ValueError("; ".join(errors))
    retained = attempt / "site"
    retained.mkdir()
    shutil.copyfile(packet_path, retained / "packet.json")
    for binding in scene["packet"]["sources"].values():
        relative = Path(binding["path"])
        target = retained / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(packet_path.parent / relative, target)
    verify_production_site(retained / "packet.json", case)
    (attempt / "runner.py").write_bytes(Path(__file__).read_bytes())
    (attempt / "config.json").write_bytes(config_path.read_bytes())
    (attempt / "construction.json").write_bytes(config_path.with_name("construction.json").read_bytes())
    (attempt / "acquisition-provenance.json").write_text(
        json.dumps({"provenance_kind": "native", "diagnostic_fixture": False}) + "\n")
    seal_capture(attempt, frames=acquired["frames"], restoration=restoration, errors=[],
                 encoder_exit_codes=acquired["encoder_exit_codes"],
                 context={"case_id": case["case_id"], "site_packet_sha256": status["site_packet_sha256"]})
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site-packet", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config_path = HERE / "config.json"
    plan_path = HERE / "case-plan.json"
    if args.check:
        print(json.dumps(check_construction(config_path, plan_path, args.site_packet)))
        return
    if args.site_packet is None or args.output_dir is None:
        parser.error("reviewed --site-packet and fresh --output-dir required")
    print(json.dumps(capture_original(args.output_dir, args.site_packet,
        config_path, plan_path, host=args.host, port=args.port)))


if __name__ == "__main__":
    main()
