"""Exact source-gated Native capture entrypoint for emergency-device cases.

The local operator supplies reviewed source files and a separately reviewed
physical device/drive controller. Nothing here claims audibility or legality.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from camera_recorder import CAMERAS
from native_camera_rig import NativeCameraRig
from native_handoff import validate_handoff
from original_adapters import capture_with_original_adapters


def check_bundle() -> dict:
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan = json.loads((root / "case-plan.json").read_text())
    case_id = config.get("selected_case_id")
    if (config.get("assignment_id") != plan.get("assignment_id") or
            config.get("law_id") != plan.get("law_id") or
            config.get("cell_id") != plan.get("cell_id") or
            config.get("actor") != plan.get("actor") or
            case_id not in {row["case_id"] for row in plan["cases"]} or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45):
        raise ValueError("Exact bundle identity or Native timebase differs")
    return {"case_id": case_id, "physical_acceptance_claimed": False}


def _controller(site: dict, path: Path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not path.is_absolute():
        raise ValueError("Reviewed physical control adapter missing")
    if (not site.get("device_controller_reviewer") or
            not site.get("device_controller_source_citation") or
            hashlib.sha256(path.read_bytes()).hexdigest() !=
            site.get("device_controller_sha256")):
        raise ValueError("Reviewed physical control adapter bytes differ")
    spec = importlib.util.spec_from_file_location("c109035_local_control", path)
    if spec is None or spec.loader is None:
        raise ValueError("Reviewed physical control adapter cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "set_state", None)) or not callable(
            getattr(module, "drive_step", None)):
        raise ValueError("Physical control adapter needs set_state and drive_step")
    return module


def capture_original(output: Path, handoff_path: Path, controller_path: Path,
                     *, host: str, port: int) -> dict:
    config = check_bundle()
    case_id = config["case_id"]
    reviewed = validate_handoff(handoff_path, case_id=case_id)
    controller = _controller(reviewed["site"], controller_path)
    output = Path(output).resolve()
    private = next((parent for parent in output.parents
                    if parent.name == ".runtime-work"), None)
    configured = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if (private is None or configured is None or
            not Path(configured).resolve().is_relative_to(private) or
            not output.is_relative_to(Path(configured).resolve())):
        raise ValueError("Original Native output must stay under configured .runtime-work")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Original Native attempt must be empty")

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
    rig = None
    original = None
    failures = []
    restoration = None

    def bind_camera(native_world, ego):
        nonlocal rig
        rig = NativeCameraRig(native_world, ego, carla, reviewed["site"])

    def read_camera(native_frame):
        if rig is None:
            raise ValueError("Original RGB rig was not bound to Native ego")
        return rig.read(native_frame)

    try:
        world.apply_settings(settings)
        spec = reviewed["source_specs"]["instrument_log"]
        original = capture_with_original_adapters(
            world, carla, case_id=case_id,
            site_packet=reviewed["paths"]["site_packet"],
            dispatch_document=reviewed["paths"]["dispatch_context"],
            equipment_document=reviewed["paths"]["equipment_record"],
            instrument_log=reviewed["paths"]["instrument_log"],
            instrument_sha256=spec["sha256"],
            instrument_source_type=spec["source_type"],
            instrument_source_citation=spec["source_citation"], output=output,
            device_command=controller.set_state, drive_step=controller.drive_step,
            camera_frame_reader=read_camera,
            camera_source_ids={name: "original-carla-rgb-" + name for name in CAMERAS},
            camera_binding=bind_camera)
        for name, spec in reviewed["source_specs"].items():
            if hashlib.sha256(reviewed["paths"][name].read_bytes()).hexdigest() != spec["sha256"]:
                raise ValueError("Reviewed source changed during Native capture: " + name)
        if hashlib.sha256(Path(controller_path).read_bytes()).hexdigest() != reviewed[
                "site"]["device_controller_sha256"]:
            raise ValueError("Reviewed physical control adapter changed during Native capture")
    except Exception as error:
        failures.append("capture: " + str(error))
    finally:
        if rig is not None:
            try:
                rig.close()
            except Exception as error:
                failures.append("camera cleanup: " + str(error))
        try:
            restoration = restore(client, saved)
        except Exception as error:
            failures.append("world restoration: " + str(error))
    output.mkdir(parents=True, exist_ok=True)
    status = {"case_id": case_id, "capture": original,
              "reviewed_handoff_sha256": reviewed["packet_sha256"],
              "restoration": restoration, "errors": failures,
              "physical_acceptance_claimed": False}
    (output / "native-run-status.json").write_text(json.dumps(status, indent=2) + "\n")
    if failures:
        raise ValueError("; ".join(failures))
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_bundle(), indent=2))
    else:
        if args.output_dir is None:
            parser.error("Original Native output directory required")
        handoff = os.environ.get("SCENARIO_NATIVE_HANDOFF")
        control = os.environ.get("SCENARIO_NATIVE_DEVICE_CONTROL_PY")
        if not handoff or not control:
            parser.error("Reviewed Native handoff and physical control adapter required")
        print(json.dumps(capture_original(
            args.output_dir, Path(handoff), Path(control),
            host=args.host, port=args.port), indent=2))


if __name__ == "__main__":
    main()
