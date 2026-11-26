"""Lazy source-gated Native entrypoint for the exact marked-crosswalk probes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import crosswalk_site as crossing

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    case_id = config.get("selected_case_id")
    expected = {row["case_id"] for row in plan["cases"]}
    if (case_id not in expected or set(config.get("supported_case_ids", [])) != expected or
            config.get("assignment_id") != crossing.ASSIGNMENT_ID or
            config.get("law_id") != "LVMC-11-52-130-A12" or
            config.get("cell_id") != "C394507" or config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45):
        raise ValueError("materialized exact crossing case differs from plan")
    if hashlib.sha256((HERE / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256"):
        raise ValueError("source-hashed exact crossing plan changed")
    return case_id, config


def reviewed_operator(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("reviewed Native operator module changed")
    spec = importlib.util.spec_from_file_location("reviewed_crosswalk_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    case_id, config = check()
    if args.check:
        print(json.dumps({"case_id": case_id, "source_gate": "reviewed-site-before-CARLA",
                          "simulation_started": False}))
        return
    if not all((args.host, args.port, args.output_dir)):
        parser.error("Native host, port and output directory required")
    site_path = os.environ.get("SCENARIO_CROSSWALK_SITE_PACKET")
    site_sha = os.environ.get("SCENARIO_CROSSWALK_SITE_SHA256")
    module_path = os.environ.get("SCENARIO_CROSSWALK_OPERATOR_MODULE")
    module_sha = os.environ.get("SCENARIO_CROSSWALK_OPERATOR_SHA256")
    if not all((site_path, site_sha, module_path, module_sha)):
        raise ValueError("source-hashed reviewed crosswalk site and operator required")
    site = crossing.load_site(site_path, site_sha, case_id)
    module = reviewed_operator(Path(module_path).resolve(), module_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = module.make_operator(world, site, case_id)
    from native_capture import capture
    capture(world, operator, site, case_id, args.output_dir,
            requested_clearance_m=config["requested_body_clearance_m"],
            source_site_path=Path(site_path))


if __name__ == "__main__":
    main()
