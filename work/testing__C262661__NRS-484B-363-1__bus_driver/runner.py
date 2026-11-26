"""Source-gated original Native bus school-zone capture entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from native_capture import capture
from school_scene_construction import ASSIGNMENT, construct, load_case, validate_site

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(case_id):
    case = load_case(case_id)
    if case["actor"] != "bus_driver" or case["target_law_id"] != "NRS-484B-363-1":
        raise ValueError("exact bus school-zone scope mismatch")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id, "source_pending": True}


def load_operator(path, digest):
    if not path.is_file() or sha(path) != digest:
        raise ValueError("reviewed original Native operator hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_school_bus_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed original Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_adapter", None)):
        raise ValueError("reviewed original Native operator factory missing")
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config_path = ROOT / "config.json"
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    case_id = args.case or config.get("selected_case_id")
    selected = check(case_id)
    if config and (config.get("assignment_id") != ASSIGNMENT or
                   config.get("selected_case_id") != case_id or
                   config.get("cell_id") != "C262661" or
                   config.get("law_id") != "NRS-484B-363-1" or
                   config.get("plan_sha256") != sha(ROOT / "case-plan.json")):
        raise ValueError("exact source-bound bus construction config differs")
    if args.check:
        print(json.dumps(selected, sort_keys=True))
        return
    site_name = os.environ.get("SCENARIO_SCHOOL_SITE_PACKET")
    site_hash = os.environ.get("SCENARIO_SCHOOL_SITE_SHA256")
    operator_name = os.environ.get("SCENARIO_SCHOOL_OPERATOR_MODULE")
    operator_hash = os.environ.get("SCENARIO_SCHOOL_OPERATOR_SHA256")
    if not all((site_name, site_hash, operator_name, operator_hash, args.output_dir)):
        raise ValueError("source-hashed original site, operator and output directory required")
    site_path = Path(site_name).resolve()
    if not site_path.is_file() or sha(site_path) != site_hash:
        raise ValueError("reviewed original school-zone site seal differs")
    site = validate_site(site_path, case_id)
    operator = load_operator(Path(operator_name).resolve(), operator_hash)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    adapter = operator.make_adapter(world, site, case_id)
    try:
        built = construct(adapter, site_path, case_id)
        site["vehicle_id"] = built["vehicle_id"]
        capture(world, adapter, site, case_id, args.output_dir, site_hash)
    finally:
        for actor in reversed(adapter.owned_actors()):
            adapter.destroy(actor)


if __name__ == "__main__":
    main()
