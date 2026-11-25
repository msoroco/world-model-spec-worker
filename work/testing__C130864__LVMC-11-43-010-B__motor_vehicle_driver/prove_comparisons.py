"""Run five selected saved-source comparison audits on CPU diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from roundabout_comparison_audit import compare
from roundabout_measurements import measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def _selected(case_id):
    short = case_id.split("__")[-1]
    attempt = REPO / ".runtime-work/c130864-compat-selected" / short / "primary"
    packet = json.loads((attempt / "original-map.json").read_text())
    motion = measure(case_id=case_id, map_path=attempt / "original-map.json",
        trace_path=attempt / "original-trace.jsonl",
        receipt_path=attempt / "original-receipt.json", allow_diagnostic=True)
    receipt = json.loads((attempt / "original-receipt.json").read_text())
    if not receipt.get("diagnostic_fixture") or receipt.get("frame_count") != 9:
        raise ValueError("expected only nine-frame CPU diagnostic source")
    return packet, {"case_id": case_id, "decoded_images": 36,
                    "motion": motion}


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    results = []
    for row in plan["comparisons"]:
        left_id, right_id = row["case_ids"]
        left_packet, left = _selected(left_id)
        right_packet, right = _selected(right_id)
        proof = compare(row["comparison_id"], left, right,
                        left_packet, right_packet, expected_decoded_images=36)
        proof.update({"diagnostic_only": True,
                      "source_attempts": [left_id, right_id]})
        results.append(proof)
        print(row["comparison_id"], "passed")
    (ROOT / "cpu-comparison-proofs.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
