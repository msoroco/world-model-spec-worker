"""CPU protocol proofs for four source-joined controlled comparisons."""

import hashlib
import json
from pathlib import Path

from comparison_audit import BASE_FIXED, DESIGN_FIXED, ComparisonError, audit
from package_spec import AID


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan["assignment_id"] != AID or len(plan["comparisons"]) != 4:
        raise ValueError("four exact NRS 484B.400(1) comparisons required")
    cases = {case["case_id"]: case for case in plan["cases"]}
    reports = []
    for comparison in plan["comparisons"]:
        records = []
        for case_id in comparison["case_ids"]:
            case = cases[case_id]
            approach = -1 if case["approach_lane_request"] == "turn" else -2
            turn = -1 if case["turn_lane_request"] == "turn" else -2
            qualified = case["qualifying_right_turn_lane"]
            record = {"format": "turn-position-delivery-measurement", "case_id": case_id,
                      "native_result_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                      "frame_count": 900, "full_video_decode": True, "actual_pixels": True,
                      "physical_completion": True,
                      "approach_source_sha256": hashlib.sha256((case_id + "approach").encode()).hexdigest(),
                      "turn_source_sha256": hashlib.sha256((case_id + "turn").encode()).hexdigest(),
                      "observables": {"approach_lane_ids": [approach], "turn_lane_ids": [turn],
                                      "qualifying_right_turn_lane": qualified,
                                      "conditional_lane_id": -1 if qualified else -2},
                      "diagnostic_fixture": True, "legal_verdict": None}
            record.update({field: "synthetic-fixed-" + field for field in BASE_FIXED})
            record.update({field: ("qualified-" if qualified else "unqualified-") + field
                           for field in DESIGN_FIXED})
            record["duration_frames"] = 900
            records.append(record)
        positive = audit(records, deliberate_differences=comparison["deliberate_differences"],
                         comparison_id=comparison["comparison_id"])
        negative = json.loads(json.dumps(records))
        negative[1]["map_sha256"] = "changed-map"
        try:
            audit(negative, deliberate_differences=comparison["deliberate_differences"],
                  comparison_id=comparison["comparison_id"])
        except ComparisonError as error:
            if "fixed condition changed: map_sha256" not in str(error):
                raise
            negative_error = str(error)
        else:
            raise ValueError("changed fixed map accepted")
        same_value = json.loads(json.dumps(records))
        for field in comparison["deliberate_differences"]:
            same_value[1]["observables"][field] = same_value[0]["observables"][field]
        try:
            audit(same_value, deliberate_differences=comparison["deliberate_differences"],
                  comparison_id=comparison["comparison_id"])
        except ComparisonError as error:
            if "deliberate difference absent" not in str(error):
                raise
            missing_difference_error = str(error)
        else:
            raise ValueError("missing deliberate difference accepted")
        log = HERE / ("proof-comparison-" + comparison["comparison_id"] + ".log")
        log.write_text("positive: " + positive["status"] + "\nnegative fixed: " + negative_error +
                       "\nnegative difference: " + missing_difference_error +
                       "\nsynthetic CPU protocol; Native acceptance false\n")
        reports.append({"comparison_id": comparison["comparison_id"],
                        "case_ids": comparison["case_ids"],
                        "script": "comparison_audit.py", "script_sha256": sha(HERE / "comparison_audit.py"),
                        "diagnostic_fixture": True, "source_verified": False,
                        "positive_exit_code": 0, "negative_rejected": True,
                        "log": log.name, "log_sha256": sha(log), "legal_verdict": None})
    (HERE / "comparison-proposal.json").write_text(json.dumps({
        "format": "turn-position-exact-comparison-proposal", "assignment_id": AID,
        "comparisons": reports, "legal_verdict": None}, indent=2) + "\n")
    return len(reports)


if __name__ == "__main__":
    print("turn-position comparison CPU proofs:", run())
