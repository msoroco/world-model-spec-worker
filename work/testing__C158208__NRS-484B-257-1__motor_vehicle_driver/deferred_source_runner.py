"""Run a C158208 case only after a local operator supplies reviewed sources.

Offline checking validates the portable bundle. Native capture additionally
requires a reviewed site packet and all eight adjacent survey sources. A CPU
fixture cannot satisfy the original capture gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from branch_site_preflight import validate_site_branch
from carla_scene_adapter import validate_native_scene_spec
from native_attempt import verify_review_sources
from source_tick_capture import validate_geometry
from through_traffic_control import validate_plan as validate_through_plan


HERE = Path(__file__).resolve().parent


def check() -> dict:
    scene = json.loads((HERE / "scene.json").read_text())
    config = json.loads((HERE / "config.json").read_text())
    case_id = scene.get("case_id")
    if (scene.get("source_kind") != "local_review_required" or
            not isinstance(case_id, str) or
            not case_id.startswith("testing__C158208__NRS-484B-257-1__motor_vehicle_driver__") or
            config.get("selected_case_id") != case_id or
            config.get("case", {}).get("kind") != scene.get("kind") or
            config.get("rate_hz") * config.get("duration_s") != 900):
        raise ValueError("exact deferred-source construction identity differs")
    if config.get("cameras") != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four original camera channels required")
    speed = config.get("candidate_target_speed_mps", 4.0)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0 < speed <= 4.0:
        raise ValueError("invalid source-gated engineering target speed")
    plan = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan).hexdigest() != scene.get("case_plan_sha256"):
        raise ValueError("case plan changed after construction")
    return {"case_id": case_id, "kind": scene["kind"],
            "target_speed_mps": float(speed)}


def reviewed_site(case_id: str) -> Path:
    named = os.environ.get("C158208_REVIEWED_SITE", "")
    digest = os.environ.get("C158208_REVIEWED_SITE_SHA256", "")
    if not named or len(digest) != 64:
        raise ValueError("source-hashed reviewed C158208 site required")
    path = Path(named).resolve()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("reviewed C158208 site source bytes changed")
    site = json.loads(path.read_text())
    if (site.get("review_status") != "reviewed" or
            site.get("cell_id") != "C158208" or
            site.get("diagnostic_fixture") is True):
        raise ValueError("original reviewed C158208 site required")
    verify_review_sources(site, path, diagnostic_fixture=False)
    validate_site_branch(site, case_id)
    validate_geometry(site["capture_geometry"])
    validate_native_scene_spec(site.get("native_scene"), site["capture_geometry"])
    validate_through_plan(site["native_scene"]["through_vehicle"].get("motion_plan"))
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    selected = check()
    if args.check:
        print("deferred-source offline check passed: " + selected["case_id"])
        return
    if args.output_dir is None:
        raise ValueError("original Native output directory required")
    site_path = reviewed_site(selected["case_id"])
    from native_capture_finalize import close_capture
    from native_attempt import run_native_attempt
    from carla_scene_adapter import CarlaSceneAdapter
    from scenario_pipeline.worker_exchange import world_restore
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    release = run_native_attempt(client, CarlaSceneAdapter(carla), world_restore,
                                 case_id=selected["case_id"],
                                 construction=HERE / "construction.json",
                                 reviewed_site_packet=site_path,
                                 attempt=args.output_dir,
                                 target_speed_mps=selected["target_speed_mps"])
    close_capture(args.output_dir, release)


if __name__ == "__main__":
    main()
