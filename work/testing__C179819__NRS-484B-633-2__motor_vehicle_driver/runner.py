"""Exact source-gated elevated-highway Native entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from bridge_observations import verify_site_bundle


HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C179819__NRS-484B-633-2__motor_vehicle_driver"


def selected_case(config):
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            ASSIGNMENT, "NRS-484B-633-2", "C179819", "motor_vehicle_driver"):
        raise ValueError("exact elevated-highway identity differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("original capture cadence/duration differs")
    if hashlib.sha256((HERE / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact bridge case plan changed")
    cases = {case["case_id"]: case for case in plan["cases"]}
    if config.get("supported_case_ids") != list(cases):
        raise ValueError("supported exact bridge case IDs differ")
    case_id = config.get("selected_case_id")
    if case_id not in cases:
        raise ValueError("unselected exact bridge case")
    return cases[case_id]


def _source(path_text, digest_text, label):
    if not path_text or not digest_text:
        raise ValueError(f"source-hashed reviewed {label} required")
    path = Path(path_text)
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest_text:
        raise ValueError(f"reviewed {label} bytes changed or unavailable")
    return path.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    case = selected_case(config)
    if args.check:
        print(json.dumps({"exact_case": case["case_id"], "source_gated": True}))
        return
    if not args.host or not args.port or args.output_dir is None:
        raise ValueError("Native host, port and materialized attempt required")
    site_path = _source(os.environ.get("SCENARIO_BRIDGE_SITE"),
                        os.environ.get("SCENARIO_BRIDGE_SITE_SHA256"), "bridge site dossier")
    site = verify_site_bundle(site_path, os.environ["SCENARIO_BRIDGE_SITE_SHA256"], case["case_id"])
    operator_path = _source(os.environ.get("SCENARIO_BRIDGE_OPERATOR"),
                            os.environ.get("SCENARIO_BRIDGE_OPERATOR_SHA256"), "bridge Native operator")
    spec = importlib.util.spec_from_file_location("reviewed_bridge_operator", operator_path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed bridge operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_adapter", None)):
        raise ValueError("reviewed bridge Native adapter factory missing")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    adapter = module.make_adapter(client.get_world(), site, case)
    from native_acquisition import acquire
    receipt = acquire(adapter, site_path, os.environ["SCENARIO_BRIDGE_SITE_SHA256"],
                      case, args.output_dir)
    print(json.dumps({"case_id": receipt["case_id"],
                      "original_frames": receipt["original_frame_count"]}))


if __name__ == "__main__":
    main()
