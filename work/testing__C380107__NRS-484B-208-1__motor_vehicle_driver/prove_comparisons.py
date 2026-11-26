"""Prove each selected comparison protocol against exact current case seals."""

import hashlib
import json
from pathlib import Path

from comparison_audit import audit

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    cases = {entry["case_id"]: entry for entry in manifest["cases"]}
    if len(cases) != 18 or len(plan["comparisons"]) != 11:
        raise ValueError("exact selected case/comparison coverage required")
    proofs = []
    for index, pair in enumerate(plan["comparisons"]):
        receipts, seals = [], []
        for side, case_id in enumerate(pair["case_ids"]):
            entry = cases[case_id]
            construction = HERE / entry["construction"]
            compatibility = HERE / entry["compatibility"]["receipt"]
            if (sha(construction) != entry["construction_sha256"] or
                    sha(compatibility) != entry["compatibility"]["sha256"] or
                    not json.loads(compatibility.read_text()).get("passed")):
                raise ValueError("stale exact case proof: " + case_id)
            seals.append({"case_id": case_id, "construction_sha256": sha(construction),
                          "compatibility_sha256": sha(compatibility)})
            receipts.append({"format": "c380107-original-delivery-audit-v1", "case_id": case_id,
                             "source_kind": "original_native_attempt", "frames_checked": 900,
                             "physical_completion": "requires independent local review",
                             "attempt_id": "synthetic-%d-%d" % (index, side),
                             "trace_sha256": "synthetic-trace-%d-%d" % (index, side),
                             "site_sha256": "synthetic-site-same",
                             "measurement": {"rear_gap_crossing_frame": 400 + side,
                                             "posted_limit_mps": 9.0,
                                             "extreme_left_lane_id": "L0",
                                             "hov_designation_state": "unresolved",
                                             "hov_compliance_state": "unresolved"}})
        result = audit(pair["comparison_id"], *receipts)
        if result["comparison_id"] != pair["comparison_id"] or result["physical_acceptance"]:
            raise ValueError("comparison protocol did not pass: " + pair["comparison_id"])
        proofs.append({"comparison_id": pair["comparison_id"], "case_seals": seals,
                       "cpu_protocol_passed": True, "diagnostic_fixture": True,
                       "original_delivery_claimed": False})
    (HERE / "cpu-comparison-proofs.json").write_text(
        json.dumps({"format": "c380107-comparison-cpu-proofs-v1",
                    "comparisons": proofs}, indent=2, sort_keys=True) + "\n")
    print("Proved", len(proofs), "selected comparison protocols with current case seals")


if __name__ == "__main__":
    main()
