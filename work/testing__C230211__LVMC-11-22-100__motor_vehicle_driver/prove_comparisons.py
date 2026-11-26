"""Exercise each exact comparison with independent positive and negative CPU records."""

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
    if plan["assignment_id"] != AID or len(plan["comparisons"]) != 6:
        raise ValueError("six exact protected-pavement comparisons required")
    reports = []
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        changed = comparison["deliberate_differences"]
        records = []
        for index, case_id in enumerate(comparison["case_ids"]):
            record = {"format": "pavement-delivery-measurement", "case_id": case_id,
                      "native_result_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                      "frame_count": 900, "full_video_decode": True,
                      "actual_pixels": True, "physical_completion": True,
                      "observables": {key: index for key in changed},
                      "diagnostic_fixture": True, "legal_verdict": None}
            record.update({key: "synthetic-fixed-" + key for key in FIXED_FIELDS})
            record["duration_frames"] = 900
            records.append(record)
        positive = audit(*records, deliberate_differences=changed)
        if positive["status"] != "measurement_comparable_legal_judgment_unresolved":
            raise ValueError("comparison positive diagnostic failed")
        negative = json.loads(json.dumps(records))
        negative[1]["map_sha256"] = "changed-map"
        try:
            audit(*negative, deliberate_differences=changed)
        except ComparisonError as error:
            if "fixed condition changed: map_sha256" not in str(error):
                raise
            negative_error = str(error)
        else:
            raise ValueError("comparison accepted a changed fixed map")
        log = HERE / ("proof-comparison-" + cid + ".log")
        log.write_text("positive: " + positive["status"] + "\nnegative: " +
                       negative_error + "\nsynthetic CPU protocol; Native acceptance false\n")
        reports.append({"comparison_id": cid, "case_ids": comparison["case_ids"],
                        "script": "comparison_audit.py",
                        "script_sha256": sha(HERE / "comparison_audit.py"),
                        "diagnostic_fixture": True, "source_verified": False,
                        "positive_exit_code": 0, "negative_rejected": True,
                        "log": log.name, "log_sha256": sha(log),
                        "legal_verdict": None})
    (HERE / "comparison-proposal.json").write_text(json.dumps({
        "format": "pavement-exact-comparison-proposal", "assignment_id": AID,
        "comparisons": reports, "legal_verdict": None}, indent=2) + "\n")
    return len(reports)


if __name__ == "__main__":
    print("pavement comparison CPU proofs:", run())
