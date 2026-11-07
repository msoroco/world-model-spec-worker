"""Independent exact-source CPU audit of both 200-foot pre-turn branches."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-223-3b"
PROOFS = (
    "draft-execution-manifest.json", "draft-offline-summary.json",
    "draft-offline-audit.log", "draft-comparison-audit.log",
    "measurement-contract-proof.log", "saved-fixture-proof.log",
    "saved-comparison-audit.log", "saved-trigger-baseline-audit.log",
    "synthetic-trigger-crossings-audit.log", "fallback-trigger-audit.json",
    "draft-package-probe-summary.json", "package-probe-audit.log",
    "native-closure-synthetic.log", "statutory-mapping-audit.log",
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    topics = read(ROOT / "inputs/coverage/branch-sources.json")["laws"][LAW]["topics"]
    if ("single center lane" not in topics["text-0"]["text"]
            or "not travel more than 200 feet" not in topics["text-1"]["text"]):
        raise ValueError("Frozen 200-foot clause differs")
    plan = read(HERE / "case-plan.json")
    matrix_path = ROOT / "work/_shared/branch-coverage.json"
    branches = read(matrix_path)["laws"][LAW]["branches"]
    comparisons = {row["comparison_id"]: set(row["case_ids"])
                   for row in plan["comparisons"]}
    expected_ids = {row["case_id"] for row in plan["cases"]}
    if len(branches) != 2 or len(comparisons) != 2:
        raise ValueError("Two exact controlled branches expected")
    proofs = {name: sha(HERE / name) for name in PROOFS}
    covered = set()
    for branch in branches:
        if (set(branch["topic_ids"]) != set(topics)
                or branch["status"] != "runnable"
                or branch["assignment_id"] != HERE.name
                or branch.get("cpu_proofs") != proofs
                or len(branch["comparison_ids"]) != 1):
            raise ValueError("Branch source or current proof binding differs")
        cid = branch["comparison_ids"][0]
        if set(branch["case_ids"]) != comparisons[cid]:
            raise ValueError("Branch comparison cases differ")
        covered.update(branch["case_ids"])
    if covered != expected_ids:
        raise ValueError("One or more exact cases unmapped")
    review = read(ROOT / "work/_shared/branch-review.json")
    if review["coverage_sha256"] != sha(matrix_path) or LAW in review["missing_branches"]:
        raise ValueError("Full-law review differs")
    offline = read(HERE / "draft-offline-summary.json")
    offline_audit = read(HERE / "draft-offline-audit.log")
    saved = read(HERE / "saved-fixture-proof.log")
    pair = read(HERE / "saved-comparison-audit.log")
    baseline = read(HERE / "saved-trigger-baseline-audit.log")
    crossing = read(HERE / "synthetic-trigger-crossings-audit.log")
    package = read(HERE / "draft-package-probe-summary.json")
    result = read(HERE / "result.json")
    intervals = pair["sampled_intervals_m"]
    threshold = 200 * .3048
    if (read(HERE / "draft-execution-manifest.json")["status"] != "draft_not_selected"
            or len(offline["results"]) != 20
            or any(row["exit_code"] != 0 for row in offline["results"])
            or not offline_audit["passed"] or offline_audit["offline_unit_tests_per_bundle"] != 22
            or len(saved) != 5
            or any(row["frames"] != 480 or row["positive_exit_code"] != 0
                   or row["negative_exit_codes"] != [1, 1]
                   or not row["source_unchanged"] or row["setup_confirmed"]
                   for row in saved)
            or not pair["passed"] or pair["frames_per_case"] != 480
            or pair["physical_native_verified"] or pair["accepted_recordings"] != 0
            or not intervals["witness_1"][1] < threshold
            or not threshold < intervals["witness_2"][0]
            or not intervals["numeric_1_0"][1] < threshold
            or not intervals["numeric_1_1"][0] < threshold < intervals["numeric_1_1"][1]
            or not threshold < intervals["numeric_1_2"][0]
            or not baseline["passed"] or baseline["original_native_or_pixels_observed"]
            or baseline["full_duration_cases"] != 5
            or any(row["source_kind"] != "synthetic_diagnostic"
                   or row["fallback1"] or row["fallback2"] for row in baseline["rows"])
            or not crossing["passed"] or crossing["native_executed"]
            or crossing["original_pixels_reviewed"] or len(crossing["records"]) != 5
            or any(row["saved_rows"] != 480 or row["isolated_fallbacks"] != [1, 2, 3]
                   or not row["changed_video_and_mixed_provenance_rejected"]
                   for row in crossing["records"])
            or package["count"] != 20 or package["ready"] or package["strict_v2_compatibility"]
            or result["status"] != "blocked" or result["accepted_membership_count"] != 0):
        raise ValueError("Exact CPU evidence incomplete or physical status overstated")
    return {"passed": True, "law_id": LAW,
            "branch_ids": [branch["branch_id"] for branch in branches],
            "controlled_cases": sorted(expected_ids), "exact_offline_bundles": 20,
            "synthetic_package_positive_negative_pairs": 20,
            "saved_frames_per_case": 480, "distance_threshold_m": threshold,
            "sampled_intervals_m": intervals, "isolated_measured_triggers_per_case": 3,
            "selected": False, "original_native_or_strict_v2_verified": False,
            "cpu_proofs": proofs}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
