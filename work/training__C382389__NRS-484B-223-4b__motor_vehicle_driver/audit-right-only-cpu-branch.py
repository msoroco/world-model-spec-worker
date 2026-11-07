"""Independent exact-source and current-receipt audit for the CPU 4(b) branch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-223-4b"
PROOFS = (
    "draft-execution-manifest.json",
    "draft-offline-summary.json",
    "draft-offline-independent-audit.log",
    "comparison-audit-latest.log",
    "saved-fixture-proof-480.log",
    "saved-comparison-latest.log",
    "trigger-source-contract-audit.log",
    "draft-package-probe-summary.json",
    "package-probe-audit-current.log",
    "native-closure-synthetic.log",
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = read(ROOT / "inputs/coverage/branch-sources.json")["laws"][LAW]
    topics = source["topics"]
    if ("single right lane" not in topics["text-0"]["text"]
            or "not travel through an intersection" not in topics["text-1"]["text"]):
        raise ValueError("Frozen statutory text differs")
    plan = read(HERE / "case-plan.json")
    matrix_path = ROOT / "work/_shared/branch-coverage.json"
    matrix = read(matrix_path)
    branch = matrix["laws"][LAW]["branches"][0]
    cases = {item["case_id"] for item in plan["cases"]}
    comparison = plan["comparisons"][0]
    if (len(matrix["laws"][LAW]["branches"]) != 1
            or set(branch["topic_ids"]) != set(topics)
            or branch["status"] != "runnable"
            or branch["assignment_id"] != HERE.name
            or set(branch["case_ids"]) != cases
            or branch["comparison_ids"] != [comparison["comparison_id"]]
            or set(comparison["case_ids"]) != cases):
        raise ValueError("Source, case or controlled comparison mapping differs")
    expected = {name: sha(HERE / name) for name in PROOFS}
    if branch.get("cpu_proofs") != expected:
        raise ValueError("CPU branch proof differs from current source")
    review = read(ROOT / "work/_shared/branch-review.json")
    if review["coverage_sha256"] != sha(matrix_path) or LAW in review["missing_branches"]:
        raise ValueError("Independent full-law review not current")
    manifest = read(HERE / "draft-execution-manifest.json")
    offline = read(HERE / "draft-offline-summary.json")
    saved = read(HERE / "saved-fixture-proof-480.log")
    pair = read(HERE / "saved-comparison-latest.log")
    trigger = read(HERE / "trigger-source-contract-audit.log")
    package = read(HERE / "draft-package-probe-summary.json")
    closure = read(HERE / "native-closure-synthetic.log")
    result = read(HERE / "result.json")
    if (manifest["status"] != "draft_not_selected" or len(manifest["cases"]) != 2
            or len(offline["results"]) != 8
            or any(row["exit_code"] != 0 for row in offline["results"])
            or len(saved["results"]) != 2
            or any(row["frames"] != 480 or row["positive_exit_code"] != 0
                   or row["negative_exit_code"] == 0 or not row["source_unchanged"]
                   for row in saved["results"])
            or pair["intersection_right_only_fractions"] != [0, 1]
            or pair["native_right_only_design_verified"]
            or not trigger["passed"] or len(trigger["records"]) != 2
            or trigger["native_executed"]
            or any(row["saved_rows"] != 480 or row["isolated_fallbacks"] != [1, 2, 3]
                   or not row["changed_samples_and_video_rejected"]
                   for row in trigger["records"])
            or package["count"] != 8 or package["ready"] or package["strict_v2_compatibility"]
            or not closure["passed"] or closure["native_executed"]
            or result["status"] != "blocked" or result["cases_selected"] != 0
            or result["carla_executed"] or result["recordings_accepted"] != 0):
        raise ValueError("Exact CPU evidence incomplete or physical status overstated")
    return {
        "passed": True, "law_id": LAW, "branch_id": branch["branch_id"],
        "source_topics": sorted(topics), "controlled_cases": sorted(cases),
        "exact_offline_bundles": 8, "synthetic_package_positive_negative_pairs": 8,
        "saved_frames_per_case": 480, "measured_trigger_crossings_per_case": 3,
        "selected": False, "original_native_or_strict_v2_verified": False,
        "cpu_proofs": expected,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
