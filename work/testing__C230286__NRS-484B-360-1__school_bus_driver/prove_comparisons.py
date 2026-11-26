"""Exercise exact three-speed and trip-phase comparisons with negative controls."""

import hashlib
import json
from pathlib import Path

from comparison_audit import FIXED_FIELDS, ComparisonError, audit
from package_spec import AID

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan["assignment_id"] != AID or len(plan["comparisons"]) != 2:
        raise ValueError("two exact school-bus comparisons required")
    reports = []
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        changed = (["target_speed_mph"] if cid == "below_at_above_55_mph" else
                   ["transporting_pupils_to_or_from_school"])
        records = []
        for index, case_id in enumerate(comparison["case_ids"]):
            speed = 54 + index if cid == "below_at_above_55_mph" else 56
            active = (index == 0) if cid == "transport_phase" else True
            record = {"format": "school-bus-delivery-measurement", "case_id": case_id,
                      "native_result_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                      "frame_count": 900, "full_video_decode": True,
                      "actual_pixels": True, "physical_completion": True,
                      "observables": {"target_speed_mph": speed,
                                      "transporting_pupils_to_or_from_school": active},
                      "diagnostic_fixture": True, "legal_verdict": None}
            record.update({key: "synthetic-fixed-" + key for key in FIXED_FIELDS})
            record["duration_frames"] = 900
            records.append(record)
        positive = audit(records, deliberate_differences=changed)
        if positive["status"] != "measurement_comparable_legal_judgment_unresolved":
            raise ValueError("comparison positive diagnostic failed")
        negative = json.loads(json.dumps(records))
        negative[1]["map_sha256"] = "changed-map"
        try:
            audit(negative, deliberate_differences=changed)
        except ComparisonError as error:
            if "fixed condition changed: map_sha256" not in str(error):
                raise
            negative_error = str(error)
        else:
            raise ValueError("comparison accepted changed fixed map")
        log = HERE / ("proof-comparison-" + cid + ".log")
        log.write_text("positive: " + positive["status"] + "\nnegative: " +
                       negative_error + "\nsynthetic CPU protocol; Native acceptance false\n")
        reports.append({"comparison_id": cid, "case_ids": comparison["case_ids"],
                        "script": "comparison_audit.py",
                        "script_sha256": sha(HERE / "comparison_audit.py"),
                        "diagnostic_fixture": True, "source_verified": False,
                        "positive_exit_code": 0, "negative_rejected": True,
                        "log": log.name, "log_sha256": sha(log), "legal_verdict": None})
    (HERE / "comparison-proposal.json").write_text(json.dumps({
        "format": "school-bus-exact-comparison-proposal", "assignment_id": AID,
        "comparisons": reports, "legal_verdict": None}, indent=2) + "\n")
    return len(reports)


if __name__ == "__main__":
    print("school-bus comparison CPU proofs:", run())
