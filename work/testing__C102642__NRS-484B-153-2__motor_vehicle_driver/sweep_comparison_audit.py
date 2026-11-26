"""Independently compare three source-bound door clearance observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_measure import measure

ROOT = Path(__file__).resolve().parent
SWEEP = ROOT.name + "__door_interference_physical_range"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(paths: list[Path], *, allow_diagnostic: bool = False) -> dict:
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    spec = next(item for item in proposal["sweep_specs"] if item["sweep_id"] == SWEEP)
    if len(paths) != 3 or spec["status"] != "complete":
        raise ValueError("three selected clearance source attempts are required")
    fixed = None
    rows = []
    for case_id, requested, path in zip(spec["selection_order"],
                                         [case["sweep_point"]["engineering_clearance_m"]
                                          for cid in spec["selection_order"]
                                          for case in proposal["cases"] if case["case_id"] == cid], paths):
        source = path / "native-trace.json"
        intent_path = path / "door-source.json"
        trace = json.loads(source.read_text())
        intent = json.loads(intent_path.read_text())
        if trace.get("case_id") != case_id or intent.get("case_id") != case_id or (
                intent.get("source_trace_sha256") != sha(source)):
            raise ValueError("clearance source identity or hash differs")
        diagnostic = bool(trace.get("diagnostic_fixture") or intent.get("diagnostic_fixture"))
        if diagnostic and not allow_diagnostic:
            raise ValueError("original Native clearance frames are required")
        if not diagnostic and len(trace.get("frames", [])) != 900:
            raise ValueError("original clearance capture requires 900 frames")
        context = trace["fixed_context"]
        key = (context["map_sha256"], context["survey_sha256"],
               context["loading_site_id"], context["traffic_route_id"],
               tuple(trace["parked_center_xy"]), tuple(trace["parked_heading_xy"]))
        if fixed is None:
            fixed = key
        elif key != fixed:
            raise ValueError("controlled clearance sweep changed fixed site or route")
        measured = measure(trace, expected_case_id=case_id,
                           expected_act="open", expected_side=intent["selected_side"])
        if not measured["act_on_closest_side"]:
            raise ValueError("clearance act is not on passing side")
        rows.append({"case_id": case_id, "requested_engineering_m": requested,
                     "original_measured_minimum_m": measured["minimum_body_gap_m"],
                     "original_interaction_frames": measured["body_gap_by_frame_m"],
                     "source_sha256": {"native-trace.json": sha(source),
                                       "door-source.json": sha(intent_path)}})
    return {"format": "worker-door-clearance-sweep-audit", "sweep_id": SWEEP,
            "cases": rows, "fixed_site_and_route_checked": True,
            "diagnostic_fixture": allow_diagnostic,
            "physical_acceptance_claimed": False, "legal_interference": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt, allow_diagnostic=args.allow_diagnostic)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("controlled source-bound clearance sweep passed:", len(result["cases"]))


if __name__ == "__main__":
    main()
