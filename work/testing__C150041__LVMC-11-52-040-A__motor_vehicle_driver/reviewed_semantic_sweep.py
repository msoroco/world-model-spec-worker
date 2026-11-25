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


def bind_rebound(expanded: dict, rebound_dir: Path) -> dict:
    """Seal each selected sweep row to both exact rebound constructions."""
    rebound_dir = Path(rebound_dir)
    source_path = rebound_dir / "rebound-manifest.json"
    execution_path = rebound_dir / "execution-manifest.json"
    source = json.loads(source_path.read_text())
    execution = json.loads(execution_path.read_text())
    sweep = expanded["sweep_specs"][0]
    rows = {row["case_id"]: row for row in sweep["case_measurements"]}
    source_cases = {row["case_id"]: row for row in source["cases"]}
    execution_cases = {row["case_id"]: row for row in execution["cases"]}
    if (len(rows) != 6 or len(source_cases) != 6 or len(execution_cases) != 6 or
            set(rows) != set(source_cases) or set(rows) != set(execution_cases) or
            source.get("packet_sha256") != sweep["source_packets_sha256"] or
            source.get("native_map") != sweep["native_map"]):
        raise ValueError("selected sweep and rebound manifest differ")
    bindings = []
    for case_id, row in rows.items():
        source_case = source_cases[case_id]
        selected = execution_cases[case_id]
        if source_case["activity"] != row["activity"]:
            raise ValueError("selected sweep activity differs")
        variants = {item["id"]: item for item in source_case["variants"]}
        candidates = {item["id"]: item for item in selected["candidates"]}
        if set(variants) != {"primary", "fallback1"} or set(candidates) != {"fallback1"}:
            raise ValueError("selected sweep candidate set differs")
        candidate_bindings = []
        for candidate_id in ("primary", "fallback1"):
            variant = variants[candidate_id]
            manifest_item = selected if candidate_id == "primary" else candidates[candidate_id]
            construction_path = rebound_dir / variant["construction"]
            digest = hashlib.sha256(construction_path.read_bytes()).hexdigest()
            if (digest != variant["construction_sha256"] or
                    digest != manifest_item["construction_sha256"] or
                    variant["construction"] != manifest_item["construction"] or
                    variant["source_packet_sha256"] != row["source_packet_sha256"]):
                raise ValueError("selected sweep construction hash or packet differs")
            package = json.loads(construction_path.read_text())
            files = {item["path"]: item["content"] for item in package["files"]}
            scene = json.loads(files["scene.json"])
            config = json.loads(files["config.json"])
            if (scene["case_id"] != case_id or
                    scene["source_packet_sha256"] != row["source_packet_sha256"] or
                    scene["target_pose"]["target_center_xy_m"] != list(row["target_center_xy_m"]) or
                    scene["target_pose"]["target_forward_xy"] != list(row["target_forward_xy"]) or
                    config["selected_case_id"] != case_id or
                    config["reviewed_source_packet"]["sha256"] != row["source_packet_sha256"]):
                raise ValueError("selected sweep construction scene differs")
            candidate_bindings.append({"candidate": candidate_id,
                                       "construction": variant["construction"],
                                       "construction_sha256": digest})
        bindings.append({"case_id": case_id, "candidates": candidate_bindings})
    result = dict(expanded)
    result["selected_rebound_binding"] = {
        "rebound_manifest_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "execution_manifest_sha256": hashlib.sha256(execution_path.read_bytes()).hexdigest(),
        "cases": bindings,
        "status": "source_bound_construction_only",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--park-packet", required=True)
    parser.add_argument("--stand-packet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rebound-dir")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / ".runtime-work").resolve()
    output = Path(args.output).resolve()
    if not output.is_relative_to(scratch) or output.exists():
        raise ValueError("fresh .runtime-work output required")
    proposal = json.loads(Path(args.proposal).read_text())
    expanded = expand(proposal, Path(args.park_packet), Path(args.stand_packet))
    if args.rebound_dir:
        expanded = bind_rebound(expanded, Path(args.rebound_dir))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(expanded, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "cases": len(expanded["sweep_specs"][0]["case_measurements"])}))


if __name__ == "__main__":
    main()
