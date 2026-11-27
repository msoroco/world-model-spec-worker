"""Lazy exact-case Native right-curb acquisition entry point."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from curb_construction import TARGETS
from curb_geometry import ASSIGNMENT, load_site
from native_acquisition import capture
from finalize_native import finalize


def check(root):
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact right-curb plan changed")
    plan = json.loads(plan_bytes)
    case_id = config.get("selected_case_id")
    if (case_id not in {row["case_id"] for row in plan["cases"]} or
            config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-457-1" or
            config.get("cell_id") != "C214875" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("variant") != case_id.removeprefix(ASSIGNMENT + "__") or
            config["variant"] not in TARGETS):
        raise ValueError("exact right-curb case identity differs")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("original right-curb capture cadence differs")
    if type(config.get("fallback")) is not bool:
        raise ValueError("selected curb candidate missing")
    if {row["name"] for row in config.get("cameras", [])} != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four original right-curb views differ")
    return config


def _checked(path, digest, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(label + " missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(label + " source hash differs")
    return raw


def _operator(path, digest):
    _checked(path, digest, "reviewed Native operator")
    spec = importlib.util.spec_from_file_location("reviewed_curb_native_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--site-packet", type=Path)
    parser.add_argument("--site-sha256")
    parser.add_argument("--operator-module", type=Path)
    parser.add_argument("--operator-sha256")
    args = parser.parse_args()
    config = check(Path(__file__).resolve().parent)
    if args.check:
        print("exact right-curb bundle passed: " + config["selected_case_id"])
        return {"case_id": config["selected_case_id"], "offline_check": "passed"}
    site_packet = args.site_packet or (Path(os.environ["SCENARIO_CURB_SITE_PACKET"])
                                       if os.environ.get("SCENARIO_CURB_SITE_PACKET") else None)
    site_sha = args.site_sha256 or os.environ.get("SCENARIO_CURB_SITE_SHA256")
    operator_module = args.operator_module or (Path(os.environ["SCENARIO_CURB_OPERATOR_MODULE"])
                                               if os.environ.get("SCENARIO_CURB_OPERATOR_MODULE") else None)
    operator_sha = args.operator_sha256 or os.environ.get("SCENARIO_CURB_OPERATOR_SHA256")
    if not all((args.host, args.port, args.output_dir, site_packet, site_sha,
                operator_module, operator_sha)):
        raise ValueError("Native endpoint, output, reviewed site and operator source required")
    if ".runtime-work" not in args.output_dir.resolve().parts:
        raise ValueError("original output must be under .runtime-work")
    if ".runtime-work" not in Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve().parts:
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    _checked(site_packet, site_sha, "reviewed right-curb site")
    site = load_site(site_packet, config["selected_case_id"])
    module = _operator(operator_module, operator_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    operator = module.make_operator(client.get_world(), site, config["selected_case_id"], config["fallback"])
    if operator.get_map_packet(config["selected_case_id"]) != site:
        raise ValueError("Native operator site packet differs from reviewed source")
    from pipeline_capture import PipelineCapture
    def same_tick(native_frame, native_time):
        if getattr(operator, "pipeline_capture", None) is None:
            if getattr(operator, "ego", None) is None:
                raise ValueError("original ego actor not spawned")
            operator.pipeline_capture = PipelineCapture(client, operator.ego,
                                                        args.output_dir, config["selected_case_id"])
        operator.pipeline_capture.capture(native_frame, native_time)
    try:
        capture(operator, site_packet, config["selected_case_id"], args.output_dir,
                fallback=config["fallback"], after_tick=same_tick)
        return finalize(args.output_dir, config["selected_case_id"], operator)
    except BaseException as error:
        (args.output_dir / "native-run-status.json").write_text(json.dumps({
            "case_id": config["selected_case_id"],
            "errors": [type(error).__name__ + ": " + str(error)],
            "capture_complete": False, "physical_acceptance_claimed": False},
            indent=2, sort_keys=True) + "\n")
        raise
    finally:
        if not getattr(operator, "capture_cleanup_complete", False):
            operator.cleanup()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
