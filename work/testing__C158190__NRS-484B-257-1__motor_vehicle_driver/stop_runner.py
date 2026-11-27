"""Fixed stop-sign Native entrypoint for two C158190 response cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from carla_stop_operator import make_adapter
from carla_yield_operator import validate_scene
from stop_sign_branch import ASSIGNMENT, CASES, construct, validate_site
from stop_native_capture import capture
from stop_native_output_bridge import publish


ROOT = Path(__file__).resolve().parent


def check(site_path=None, site_sha256=None):
    config = json.loads((ROOT / "config.json").read_text())
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("cell_id") != "C158190" or
            config.get("law_id") != "NRS-484B-257-1" or
            hashlib.sha256((ROOT / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256")):
        raise ValueError("fixed stop branch or plan hash differs")
    case_id = config.get("selected_case_id")
    if case_id not in CASES or case_id not in config.get("supported_case_ids", []):
        raise ValueError("unknown selected stop case")
    if site_path is not None or site_sha256 is not None:
        if (site_path is None or site_sha256 is None or
                hashlib.sha256(Path(site_path).read_bytes()).hexdigest() != site_sha256):
            raise ValueError("reviewed original stop-site hash required")
        site = validate_site(site_path, case_id)
        validate_scene(site)
    return {"case_id": case_id, "site_sha256": site_sha256}


def run_attempt(world, adapter, site, site_path, case_id, output_dir, site_hash):
    """Release every owned actor and seal only restored Native output."""
    built = construct(adapter, site_path, case_id)
    try:
        capture(world, adapter, site, case_id, output_dir, site_hash)
    finally:
        adapter.destroy(built["through_vehicle_actor_id"])
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
    site_name = os.environ.get("SCENARIO_STOP_SITE_PACKET")
    site_hash = os.environ.get("SCENARIO_STOP_SITE_SHA256")
    if not all((site_name, site_hash, args.output_dir)):
        raise ValueError("reviewed stop site and Native output required")
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
