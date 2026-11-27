"""Lazy source-hashed Native entry point for exact business-alley captures."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from alley_construction import ASSIGNMENT, VARIANTS
from native_acquisition import capture
from finalize_native import finalize


def check(root: Path):
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact business-alley plan changed")
    plan = json.loads(plan_bytes)
    case_id = config.get("selected_case_id")
    if (case_id not in {row["case_id"] for row in plan["cases"]} or
            config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-477-1a" or
            config.get("cell_id") != "C378707" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("variant") != case_id.removeprefix(ASSIGNMENT + "__")):
        raise ValueError("exact business-alley identity differs")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("original capture cadence differs")
    if config.get("approach_direction") not in (-1, 1):
        raise ValueError("surveyed approach direction invalid")
    if {c["name"] for c in config.get("cameras", [])} != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four original camera views differ")
    return config


def _checked_file(path: Path, digest: str, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError(label + " source missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(label + " source hash differs")
    return raw


def _operator(path: Path, digest: str):
    _checked_file(path, digest, "reviewed Native operator")
    spec = importlib.util.spec_from_file_location("reviewed_business_alley_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def _verify_site_sources(site: dict, packet_path: Path):
    sources = site.get("reviewed_sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed site sources absent")
    for label, source in sources.items():
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise ValueError("reviewed " + label + " source absent")
        path = Path(source["path"])
        if not path.is_absolute():
            path = packet_path.parent / path
        _checked_file(path, source.get("sha256", ""), "reviewed " + label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case-id")
    parser.add_argument("--direction", type=int, choices=(-1, 1))
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
        print("exact business-alley bundle passed: " + config["selected_case_id"])
        return {"case_id": config["selected_case_id"], "offline_check": "passed"}
    case_id = args.case_id or config["selected_case_id"]
    direction = args.direction if args.direction is not None else config["approach_direction"]
    if direction != config["approach_direction"]:
        raise ValueError("selected approach direction differs from bound construction")
    if case_id != config["selected_case_id"] or not case_id.startswith(ASSIGNMENT + "__") or case_id.removeprefix(ASSIGNMENT + "__") not in VARIANTS:
        raise ValueError("unknown exact business-alley case")
    site_packet = args.site_packet or (Path(os.environ["SCENARIO_BUSINESS_ALLEY_SITE_PACKET"]) if os.environ.get("SCENARIO_BUSINESS_ALLEY_SITE_PACKET") else None)
    site_sha = args.site_sha256 or os.environ.get("SCENARIO_BUSINESS_ALLEY_SITE_SHA256")
    operator_module = args.operator_module or (Path(os.environ["SCENARIO_BUSINESS_ALLEY_OPERATOR_MODULE"]) if os.environ.get("SCENARIO_BUSINESS_ALLEY_OPERATOR_MODULE") else None)
    operator_sha = args.operator_sha256 or os.environ.get("SCENARIO_BUSINESS_ALLEY_OPERATOR_SHA256")
    if not all((args.host, args.port, args.output_dir, site_packet,
                site_sha, operator_module, operator_sha)):
        raise ValueError("Native host, output, reviewed site and operator source required")
    if ".runtime-work" not in args.output_dir.resolve().parts:
        raise ValueError("original output must be under .runtime-work")
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be set under .runtime-work")
    site = json.loads(_checked_file(site_packet, site_sha,
                                    "reviewed business-alley site"))
    _verify_site_sources(site, site_packet)
    module = _operator(operator_module, operator_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    operator = module.make_operator(client.get_world(), site, case_id, direction)
    if operator.get_map_packet(case_id) != site:
        raise ValueError("Native operator site packet differs from reviewed source")
    from pipeline_capture import PipelineCapture
    args.output_dir.mkdir(parents=True, exist_ok=True)
    original = args.output_dir / "original-attempt"
    def capture_graph(native_frame, native_time):
        if getattr(operator, "pipeline_capture", None) is None:
            if getattr(operator, "ego", None) is None:
                raise ValueError("original ego actor was not spawned")
            operator.pipeline_capture = PipelineCapture(client, operator.ego,
                                                        args.output_dir, case_id)
        operator.pipeline_capture.capture(native_frame, native_time)
    try:
        capture(operator, case_id, original, direction=direction,
                after_tick=capture_graph)
        return finalize(args.output_dir, case_id, operator)
    except BaseException as error:
        (args.output_dir / "native-run-status.json").write_text(json.dumps({
            "case_id": case_id, "errors": [type(error).__name__ + ": " + str(error)],
            "capture_complete": False, "physical_acceptance_claimed": False},
            indent=2, sort_keys=True) + "\n")
        raise
    finally:
        if not getattr(operator, "capture_cleanup_complete", False):
            operator.cleanup()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
