"""Source-gated original Native C179789 alternate-route attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from reviewed_route_scene import plan as reviewed_plan
from source_gated_sweeps import prepare as prepare_sweeps

ROOT = Path(__file__).resolve().parent
AID = "testing__C179789__NRS-484B-627-1c__motor_vehicle_driver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(case_id: str) -> dict:
    rows = json.loads((ROOT / "case-plan.json").read_text())["cases"]
    selected = [row for row in rows if row["case_id"] == case_id]
    if len(selected) != 1:
        raise ValueError("unselected exact alternate-route case")
    return selected[0]


def plan(case_id: str, site_path: Path, site_sha256: str) -> dict:
    selected = select(case_id)
    if sha(site_path) != site_sha256:
        raise ValueError("reviewed original route site hash changed")
    root = site_path.resolve().parent
    ref = {"path": site_path.name, "sha256": site_sha256}
    if "__impediment-" in case_id or "__route_possibility-" in case_id:
        matches = [item for item in prepare_sweeps(root, ref) if item["case_id"] == case_id]
        if len(matches) != 1:
            raise ValueError("selected engineering station missing")
        route_plan = matches[0]
    else:
        route_plan = reviewed_plan(root, ref, case_id)
    target = selected["target"]
    if route_plan["scene"]["controlled_access"] is not target["controlled_access"] or \
            route_plan["scene"]["alternate_declared"] is not target["alternate_declared"] or \
            route_plan["requested_route"] != target["route_choice"]:
        raise ValueError("original reviewed source differs from selected route target")
    if route_plan.get("requested_ego_speed_mps") != target.get("ego_speed_mps") or \
            route_plan.get("requested_alternate_entry_lead_m") != target.get("alternate_entry_lead_m"):
        raise ValueError("engineering station differs from canonical selected case")
    return route_plan


def execute(case_id: str, site_path: Path, site_sha256: str,
            output: Path, host: str, port: int) -> dict:
    route_plan = plan(case_id, site_path, site_sha256)
    config = json.loads((ROOT / "config.json").read_text())
    if config["selected_case_id"] != case_id or config["rate_hz"] != 20 or \
            config["duration_s"] != 45:
        raise ValueError("materialized exact route configuration differs")
    from native_route_capture import capture
    receipt = capture(route_plan, output, host, port)
    with (output / "original-site.json").open("xb") as target, site_path.open("rb") as source:
        shutil.copyfileobj(source, target)
    (output / "original-route-acquisition.json").write_text(json.dumps({
        "format": "original-route-acquisition", "case_id": case_id,
        "site_sha256": site_sha256, **receipt}, sort_keys=True) + "\n")
    originals = ("original-site.json", "original-route-motion.json",
                 "original-route-acquisition.json", "trace.jsonl",
                 "video_frames.jsonl", "body_history.jsonl", "road.xodr",
                 "carla_recorder.log", "overview.mkv", "approach.mkv",
                 "reference_corner.mkv", "driver_reference.mkv")
    (output / "acquisition.json").write_text(json.dumps({name: {
        "kind": "original_native", "sha256": sha(output / name)} for name in originals},
        sort_keys=True) + "\n")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False}, sort_keys=True) + "\n")
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=receipt["frame_count"],
                 restoration={"restored": True,
                              "settings_readback": "original CARLA synchronous settings restored"},
                 errors=[], encoder_exit_codes={name: 0 for name in receipt["camera_archives"]})
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case-id")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--site-sha256")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    case_id = args.case_id or config["selected_case_id"]
    select(case_id)
    if config["selected_case_id"] != case_id or config["rate_hz"] != 20 or config["duration_s"] != 45:
        raise ValueError("materialized route configuration differs")
    if args.check:
        print(json.dumps({"case_id": case_id, "source_gate": "reviewed-original-route-site-sha256",
                          "simulation_started": False}))
        return
    site = args.site or (Path(os.environ["ROUTE_SITE_PATH"]) if "ROUTE_SITE_PATH" in os.environ else None)
    checksum = args.site_sha256 or os.environ.get("ROUTE_SITE_SHA256")
    if site is None or not checksum or args.output_dir is None:
        parser.error("original route capture requires reviewed site path, SHA-256 and output")
    print(json.dumps(execute(case_id, site, checksum, args.output_dir, args.host, args.port)))


if __name__ == "__main__":
    main()
