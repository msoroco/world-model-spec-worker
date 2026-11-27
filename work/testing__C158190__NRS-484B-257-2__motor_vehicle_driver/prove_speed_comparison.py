"""Diagnostic logic proof for the independent original speed comparator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from speed_sweep_comparison import compare, audit_attempts

HERE = Path(__file__).resolve().parent
EXTENSION = HERE / "speed-sweep-extension.json"


def main() -> None:
    extension = json.loads(EXTENSION.read_text())
    records = []
    for row, mean in zip(extension["cases"], (1.0, 3.0, 5.0)):
        records.append(({"selected_case_id": row["case_id"],
                         "case": {"draft_variables": dict(row["draft_variables"])}},
                        {"case_id": row["case_id"], "realized_observables": {
                            "counterpart_center_station_first_m": 8.0,
                            "ego_speed_min_peak_to_stop_reference_mps": 0.004,
                            "ego_speed_mean_full_body_overlap_to_clear_mps": mean}}))
    positive = compare(records)
    if positive["range_indices"] != [2, 5, 8] or not positive["realized_bins_checked"]:
        raise ValueError("independent speed bins not checked")
    records[2][1]["realized_observables"]["ego_speed_mean_full_body_overlap_to_clear_mps"] = 3.0
    try:
        compare(records)
    except ValueError as exc:
        if "missed planned above bin" not in str(exc):
            raise
    else:
        raise ValueError("mis-binned speed accepted")
    records[2][1]["realized_observables"]["ego_speed_mean_full_body_overlap_to_clear_mps"] = 5.0
    records[2][0]["case"]["draft_variables"]["requested_other_station_m"] = 9
    try:
        compare(records)
    except ValueError as exc:
        if "construction identity differs" not in str(exc):
            raise
    else:
        raise ValueError("changed fixed condition accepted")
    attempts = [HERE.parents[1] / ".runtime-work/c158190-2572-final" /
                ("speed-saved-proof-" + row["case_id"].removeprefix(HERE.name + "__") + "-v1/v0001/analysis")
                for row in extension["cases"]]
    try:
        audit_attempts(attempts)
    except ValueError as exc:
        if "synthetic saved source cannot satisfy original delivery" not in str(exc):
            raise
    else:
        raise ValueError("diagnostic source accepted as original comparison")
    receipt = {"format": "c158190-speed-comparison-diagnostic-proof-v1",
               "comparison_id": "approaching_near_crossing_speed_sweep",
               "case_ids": [row["case_id"] for row in extension["cases"]],
               "comparator_sha256": hashlib.sha256((HERE / "speed_sweep_comparison.py").read_bytes()).hexdigest(),
               "extension_sha256": hashlib.sha256(EXTENSION.read_bytes()).hexdigest(),
               "positive_logic": positive, "negative_missed_bin_rejected": True,
               "negative_fixed_condition_rejected": True,
               "diagnostic_as_original_rejected": True,
               "diagnostic_fixture": True, "realized_original_difference_claimed": False,
               "legal_conclusion": None}
    (HERE / "cpu-speed-comparison-diagnostics.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("speed comparison diagnostic logic and original-source rejection passed")


if __name__ == "__main__":
    main()
