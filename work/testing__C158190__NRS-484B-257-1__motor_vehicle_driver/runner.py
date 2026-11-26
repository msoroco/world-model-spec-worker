"""Exact source-gated C158190 yield-sign Native capture entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from yield_view_measurement import ASSIGNMENT
from yield_scene_construction import VARIANTS, construct, validate_site, verify_original_sources
from native_capture import capture
from native_output_bridge import publish


ROOT = Path(__file__).resolve().parent


def check(site_path=None, site_sha256=None):
    config = json.loads((ROOT / "config.json").read_text())
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("cell_id") != "C158190" or
            config.get("law_id") != "NRS-484B-257-1" or
            hashlib.sha256((ROOT / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256")):
        raise ValueError("exact yield branch or plan hash differs")
    case_id = config.get("selected_case_id")
    if (case_id not in config.get("supported_case_ids", []) or
            case_id.removeprefix(ASSIGNMENT + "__") not in VARIANTS):
        raise ValueError("unknown selected yield case")
    if site_path is not None or site_sha256 is not None:
        if (site_path is None or site_sha256 is None or
                hashlib.sha256(Path(site_path).read_bytes()).hexdigest() != site_sha256):
            raise ValueError("reviewed original yield-site hash required")
        site = validate_site(site_path, case_id)
        verify_original_sources(site, site_path)
    return {"case_id": case_id, "site_sha256": site_sha256}


def load_operator(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("reviewed Native operator source hash differs")
    spec = importlib.util.spec_from_file_location("reviewed_yield_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_adapter", None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.check:
        print(check()["case_id"])
        return
    site_name = os.environ.get("SCENARIO_YIELD_SITE_PACKET")
    site_hash = os.environ.get("SCENARIO_YIELD_SITE_SHA256")
    operator_name = os.environ.get("SCENARIO_YIELD_OPERATOR_MODULE")
    operator_hash = os.environ.get("SCENARIO_YIELD_OPERATOR_SHA256")
    if not all((site_name, site_hash, operator_name, operator_hash, args.output_dir)):
        raise ValueError("reviewed yield site, operator and Native output required")
    site_path = Path(site_name).resolve()
    selected = check(site_path, site_hash)
    operator = load_operator(Path(operator_name).resolve(), operator_hash)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    site = validate_site(site_path, selected["case_id"])
    adapter = operator.make_adapter(world, site, selected["case_id"])
    built = construct(adapter, site_path, selected["case_id"])
    try:
        capture(world, adapter, site, selected["case_id"], args.output_dir, site_hash)
        publish(args.output_dir, map_bytes=adapter.map_bytes(world), restored=True)
    finally:
        for actor in reversed((built["through_vehicle_actor_id"], built["yield_sign_actor_id"])):
            adapter.destroy(actor)


if __name__ == "__main__":
    main()
