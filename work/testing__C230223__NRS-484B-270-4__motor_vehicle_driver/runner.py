"""Exact source-gated Native entrypoint for the four cycle-lane cases."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_native import VIEWS, prepare


def check_config(config: dict) -> bool:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    cases = {case["case_id"]: case for case in plan["cases"]}
    case_id = config.get("selected_case_id")
    if (case_id not in cases or
            set(config.get("supported_case_ids", [])) != set(cases) or
            config.get("law_id") != "NRS-484B-270-4" or
            config.get("cell_id") != "C230223" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45 or
            tuple(config.get("cameras", [])) != VIEWS or
            config.get("diagnostic_only") is not True):
        raise ValueError("exact cycle-lane Native case/config mismatch")
    selected = cases[case_id]
    if (config.get("requested_overlap") is not selected["requested_cycle_lane_intersection_overlap"] or
            config.get("requested_subsection_3_status") != selected["requested_subsection_3_exception_status"] or
            not config.get("route_candidate_id")):
        raise ValueError("exact case route and exception request mismatch")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    check_config(config)
    if args.check:
        print("exact four-case source-gated cycle-lane config passed")
        return
    if args.output_dir is None:
        raise ValueError("Native output directory required")
    source = os.environ.get("C230223_REVIEWED_PACKET")
    if not source:
        raise ValueError("original reviewed cycle-lane packet required")
    packet = json.loads(Path(source).read_text())
    paths = packet.get("sources", {})
    hashes = packet.get("reviewed_sha256", {})
    if set(paths) != {"site", "subsection_3", "vehicle"} or set(hashes) != set(paths):
        raise ValueError("independent site, subsection 3 and vehicle review bindings required")
    source_root = Path(source).resolve().parent
    source_paths = {name: source_root / paths[name] for name in paths}
    if any(not path.resolve().is_relative_to(source_root) for path in source_paths.values()):
        raise ValueError("reviewed source path escaped packet")
    native_plan = prepare(config["selected_case_id"], source_paths["site"], hashes["site"],
                          source_paths["subsection_3"], hashes["subsection_3"],
                          source_paths["vehicle"], hashes["vehicle"],
                          config["route_candidate_id"])
    from native_adapter import NativeAdapter
    adapter = NativeAdapter(args.host, args.port, args.output_dir, source_paths,
                            hashes, native_plan)
    try:
        adapter.execute(config)
    finally:
        adapter.close()
    if not adapter.restoration_verified:
        raise ValueError("original Native world restoration unverified")
    (args.output_dir / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False}) + "\n")
    from analysis import analyze, saved_result
    from worker_exchange.native_output import seal_capture, write_result
    report = analyze(args.output_dir, config["selected_case_id"])
    write_result(args.output_dir, saved_result(args.output_dir, report))
    seal_capture(args.output_dir, frames=900,
                 restoration={"restored": True,
                              "settings_readback": "synchronous mode and delta verified"},
                 errors=[], encoder_exit_codes={name: 0 for name in VIEWS},
                 context={"site_sha256": hashes["site"],
                          "subsection_3_sha256": hashes["subsection_3"],
                          "vehicle_sha256": hashes["vehicle"]})


if __name__ == "__main__":
    main()
