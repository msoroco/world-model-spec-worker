"""Expand the parking alternatives only after a sealed site binding exists.

The result is a construction plan. It does not decide whether a measured angle
is legally parallel or whether an original Native vehicle reached the pose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bind_reviewed_site import bind
from parking_pose import REQUESTS


ASSIGNMENT = "testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver"
LAW = "LVMC-11-52-040-A"
PHRASE = "parallel with the edge of the roadway"


def expand(proposal: dict, park_packet: Path, stand_packet: Path) -> dict:
    """Return an exact six-case, source-sealed categorical sweep proposal."""
    binding = bind(park_packet, stand_packet)
    proposed = {case["case_id"]: case for case in proposal.get("cases", [])
                if case.get("target_type") != "baseline"}
    expected = {ASSIGNMENT + "__" + suffix for suffix in REQUESTS}
    if set(proposed) != expected:
        raise ValueError("source-bound sweep needs exactly six selected cases")
    samples = {row["angle_deg"]: row
               for row in binding["placement_grid"]["offsets"][0]["samples"]}
    rows = []
    for suffix, (activity, orientation, heading) in REQUESTS.items():
        case_id = ASSIGNMENT + "__" + suffix
        case = proposed[case_id]
        assigned = case.get("variable_assignments", {})
        for key, value in (("activity_context", activity),
                           ("orientation_request", orientation),
                           ("heading_request", heading)):
            if assigned.get(key, {}).get("value") != value:
                raise ValueError("selected case differs from source-bound sweep: " + case_id)
        angle = 30 if orientation == "angled" else 0
        if not samples[angle]["full_footprint_inside_reviewed_roadway"]:
            raise ValueError("selected orientation footprint outside reviewed roadway")
        scene = binding["scenes"][suffix]
        rows.append({"case_id": case_id, "activity": activity,
                     "orientation_request": orientation, "heading_request": heading,
                     "engineering_angle_request_deg": angle,
                     "source_packet_sha256": binding["packet_sha256"][activity],
                     "target_center_xy_m": scene["target_pose"]["target_center_xy_m"],
                     "target_forward_xy": scene["target_pose"]["target_forward_xy"],
                     "full_footprint_inside_reviewed_roadway": True,
                     "actual_motion_reviewed": False, "legal_judgment": "unresolved"})
    result = dict(proposal)
    result["sweep_specs"] = [{
        "sweep_id": "reviewed_parallel_orientation_and_heading",
        "target_law_id": LAW,
        "status": "expanded_source_bound_construction",
        "mode": "categorical_alternatives",
        "judgment_refs": [{"phrase": PHRASE,
                           "note": "No numeric legal angular cutoff or training range is supplied."}],
        "source_packets_sha256": binding["packet_sha256"],
        "reviewed_source_hashes": binding["reviewed_source_hashes"],
        "native_map": binding["native_map"],
        "engineering_feasibility": binding["placement_grid"],
        "case_measurements": rows,
        "limitations": ["Original Native pose and pixels remain unverified.",
                        "Chapter applicability and legal judgment require independent review.",
                        "The 0 and 30 degree requests are construction values, not legal thresholds."],
    }]
    result["sweeps_expanded"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--park-packet", required=True)
    parser.add_argument("--stand-packet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / ".runtime-work").resolve()
    output = Path(args.output).resolve()
    if not output.is_relative_to(scratch) or output.exists():
        raise ValueError("fresh .runtime-work output required")
    proposal = json.loads(Path(args.proposal).read_text())
    expanded = expand(proposal, Path(args.park_packet), Path(args.stand_packet))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(expanded, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "cases": len(expanded["sweep_specs"][0]["case_measurements"])}))


if __name__ == "__main__":
    main()
