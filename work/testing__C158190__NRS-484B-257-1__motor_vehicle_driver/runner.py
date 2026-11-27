"""Exact source-gated C158190 yield-sign Native capture entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from carla_yield_operator import make_adapter, validate_scene
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
        validate_scene(site)
    return {"case_id": case_id, "site_sha256": site_sha256}


def run_attempt(world, adapter, site, site_path, case_id, output_dir, site_hash):
    """Seal output only after Native settings and owned actors are released."""
    built = construct(adapter, site_path, case_id)
    try:
        capture(world, adapter, site, case_id, output_dir, site_hash)
    finally:
        try:
            adapter.destroy(built["through_vehicle_actor_id"])
        finally:
            adapter.destroy(built["yield_sign_actor_id"])
    return publish(output_dir, map_bytes=adapter.map_bytes(world), restored=True)


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
    if not all((site_name, site_hash, args.output_dir)):
        raise ValueError("reviewed yield site and Native output required")
    site_path = Path(site_name).resolve()
    selected = check(site_path, site_hash)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    site = validate_site(site_path, selected["case_id"])
    adapter = make_adapter(world, site, selected["case_id"])
    run_attempt(world, adapter, site, site_path, selected["case_id"], args.output_dir, site_hash)


if __name__ == "__main__":
    main()
