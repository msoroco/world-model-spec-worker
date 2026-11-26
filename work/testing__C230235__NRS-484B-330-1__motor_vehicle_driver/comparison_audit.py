"""Check that each planned flagger contrast changes only its declared axis."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery
from source_packet import ASSIGNMENT


AXES = {"flagger_response": "response", "zone_designation": "designated",
        "flagger_authorization": "authorized", "signal_content": "signal",
        "marked_construction_response": "response"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(plan_path: Path, stages: dict[str, dict], *, diagnostic_fixture: bool = False) -> dict:
    plan = json.loads(Path(plan_path).read_text())
    if plan.get("assignment_id") != ASSIGNMENT or len(plan.get("comparisons", [])) != 5:
        raise ValueError("exact comparison plan differs")
    observed = []
    for comparison in plan["comparisons"]:
        comparison_id = comparison.get("comparison_id")
        if comparison_id not in AXES or len(comparison.get("case_ids", [])) != 2:
            raise ValueError("unrecognized controlled comparison")
        cases = comparison["case_ids"]
        if any(case_id not in stages for case_id in cases):
            raise ValueError("comparison source stage missing")
        scenes = []
        rows = []
        receipts = []
        for case_id in cases:
            stage = Path(stages[case_id]["stage"])
            saved = Path(stages[case_id]["saved"])
            receipts.append(audit_delivery(stage, saved, case_id=case_id,
                                           diagnostic_fixture=diagnostic_fixture))
            packet = json.loads((stage / "source-packet.json").read_text())
            scenes.append(packet["scene"])
            rows.append([json.loads(line) for line in (stage / "original-ticks.jsonl").read_text().splitlines()])
        left, right = scenes
        axis = AXES[comparison_id]
        if left[axis] == right[axis]:
            raise ValueError("declared comparison axis did not change: " + comparison_id)
        fixed = set(left) - {"designated", "marked_construction", "authorized", "signal", "response"}
        if set(left) != set(right) or any(left[name] != right[name] for name in fixed):
            raise ValueError("comparison changed fixed scene source or geometry: " + comparison_id)
        if any(left[name] != right[name] for name in set(AXES.values()) - {axis}):
            raise ValueError("comparison changed more than one declared case axis")
        if (len(rows[0]) != len(rows[1]) or
                any(a["original_frame"] != b["original_frame"] or a["time_s"] != b["time_s"]
                    for a, b in zip(*rows))):
            raise ValueError("comparison changed original frame/time alignment")
        if comparison_id in ("flagger_response", "marked_construction_response"):
            if not any(a["vehicle_speed_mps"] != b["vehicle_speed_mps"]
                       for a, b in zip(*rows)):
                raise ValueError("driver response contrast was not realized")
        observed.append({"comparison_id": comparison_id, "case_ids": cases,
                         "changed_axis": axis, "fixed_scene_and_source_hashes": True,
                         "frame_time_aligned": True,
                         "source_receipt_sha256": [hashlib.sha256(
                             json.dumps(receipt, sort_keys=True).encode()).hexdigest()
                             for receipt in receipts],
                         "status": "synthetic_software_only" if diagnostic_fixture
                                   else "original_measurements_pending_judgment"})
    if {row["comparison_id"] for row in observed} != set(AXES):
        raise ValueError("five comparisons not covered")
    return {"format": "c230235-comparison-audit-v1", "assignment_id": ASSIGNMENT,
            "plan_sha256": sha(Path(plan_path)), "diagnostic_fixture": diagnostic_fixture,
            "comparisons": observed, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--stages", required=True, type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("comparison output already exists")
    stages = json.loads(args.stages.read_text())
    receipt = audit(args.plan, stages, diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(len(receipt["comparisons"]))
