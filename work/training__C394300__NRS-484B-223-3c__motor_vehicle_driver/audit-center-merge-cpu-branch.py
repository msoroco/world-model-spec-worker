"""Independent exact-source CPU audit of the 50-foot post-turn merge branch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-223-3c"
PROOFS = (
    "draft-execution-manifest.json",
    "draft-offline-summary.json",
    "draft-offline-audit-current.log",
    "draft-comparison-audit-current.log",
    "draft-measurement-audit.log",
    "measurement-contract-proof-current.log",
    "saved-fixture-proof-current.log",
    "saved-comparison-audit-current.log",
    "saved-trigger-baseline-audit.log",
    "draft-package-probe-summary.json",
    "package-probe-audit-current.log",
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    topics = read(ROOT / "inputs/coverage/branch-sources.json")["laws"][LAW]["topics"]
    if ("single center lane" not in topics["text-0"]["text"]
            or "not travel more than 50 feet" not in topics["text-1"]["text"]):
        raise ValueError("Frozen center-lane source differs")
    plan = read(HERE / "case-plan.json")
    matrix_path = ROOT / "work/_shared/branch-coverage.json"
    matrix = read(matrix_path)
    branches = matrix["laws"][LAW]["branches"]
    branch = branches[0]
    cases = {item["case_id"] for item in plan["cases"]}
    comparison = plan["comparisons"][0]
    if (len(branches) != 1 or set(branch["topic_ids"]) != set(topics)
            or branch["status"] != "runnable" or branch["assignment_id"] != HERE.name
            or set(branch["case_ids"]) != cases
            or branch["comparison_ids"] != [comparison["comparison_id"]]
            or set(comparison["case_ids"]) != cases):
        raise ValueError("Exact source, case or comparison binding differs")
    expected = {name: sha(HERE / name) for name in PROOFS}
    if branch.get("cpu_proofs") != expected:
        raise ValueError("CPU proof hashes differ from current receipts")
    review = read(ROOT / "work/_shared/branch-review.json")
    if review["coverage_sha256"] != sha(matrix_path) or LAW in review["missing_branches"]:
        raise ValueError("Full-law branch review differs")
    offline = read(HERE / "draft-offline-summary.json")
    offline_audit = read(HERE / "draft-offline-audit-current.log")
    measurements = read(HERE / "measurement-contract-proof-current.log")
    saved = read(HERE / "saved-fixture-proof-current.log")
    pair = read(HERE / "saved-comparison-audit-current.log")
    triggers = read(HERE / "saved-trigger-baseline-audit.log")
    package = read(HERE / "draft-package-probe-summary.json")
    result = read(HERE / "result.json")
    threshold_m = 50 * 0.3048
    intervals = pair["sampled_intervals_m"]
    if (read(HERE / "draft-execution-manifest.json")["status"] != "draft_not_selected"
            or len(cases) != 3 or len(offline["results"]) != 12
            or any(row["exit_code"] != 0 for row in offline["results"])
            or not offline_audit["passed"] or offline_audit["offline_unit_tests_per_bundle"] != 21
            or measurements["selected_delivery_cases"] != 0
            or len(measurements["records"]) != 3
            or len(saved) != 3
            or any(row["frames"] != 480 or row["positive_exit_code"] != 0
                   or row["negative_exit_codes"] != [1, 1]
                   or not row["source_unchanged"] or row["setup_confirmed"]
                   for row in saved)
            or not pair["passed"] or pair["frames_per_case"] != 480
            or pair["physical_native_verified"] or pair["accepted_recordings"] != 0
            or not intervals["below_50_ft"][1] < threshold_m
            or not intervals["at_50_ft"][0] < threshold_m < intervals["at_50_ft"][1]
            or not threshold_m < intervals["above_50_ft"][0]
            or not triggers["passed"] or triggers["original_native_or_pixels_observed"]
            or len(triggers["cases"]) != 3
            or any(row["frames"] != 480 or row["baseline_fallback1"]
                   or row["baseline_fallback2"] or row["baseline_fallback3"]
                   or len(row["isolated_crossings"]) != 3 for row in triggers["cases"])
            or package["count"] != 12 or package["ready"]
            or package["strict_v2_compatibility"]
            or result["status"] != "blocked" or result["cases_selected"] != 0
            or result["carla_executed"] or result["recordings_accepted"] != 0
            or result["native_bidirectional_lane_type_observed"]):
        raise ValueError("Exact CPU evidence incomplete or physical status overstated")
    return {"passed": True, "law_id": LAW, "branch_id": branch["branch_id"],
            "source_topics": sorted(topics), "controlled_cases": sorted(cases),
            "exact_offline_bundles": 12, "synthetic_package_positive_negative_pairs": 12,
            "saved_frames_per_case": 480, "distance_threshold_m": threshold_m,
            "saved_distance_intervals_m": intervals,
            "isolated_measured_triggers_per_case": 3, "selected": False,
            "original_native_or_strict_v2_verified": False, "cpu_proofs": expected}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
