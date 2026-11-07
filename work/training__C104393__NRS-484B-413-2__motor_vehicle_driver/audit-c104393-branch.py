"""Independent statutory CPU branch binding for C104393 any-other-area signaling."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AID = HERE.name
LAW = "NRS-484B-413-2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    frozen = read(ROOT / "inputs" / AID / "assignment.json")
    assert frozen["law_id"] == LAW and frozen["cell_id"] == "C104393"
    plan = read(HERE / "case-plan.json")
    assert plan["source_law_text"].find("last 300 feet") >= 0
    assert "regardless of the weather" in plan["source_law_text"]
    expected = [AID + "__" + str(feet) for feet in (90, 100, 110, 290, 300, 310)]
    assert [case["case_id"] for case in plan["cases"]] == expected
    assert len(plan["comparisons"]) == 1
    comparison = plan["comparisons"][0]
    assert comparison["case_ids"] == expected
    assert comparison["deliberate_differences"] == ["continuous_signal_distance_before_course_change"]
    matrix_path = ROOT / "work/_shared/branch-coverage.json"
    matrix = read(matrix_path)
    review = read(ROOT / "work/_shared/branch-review.json")
    assert review["coverage_sha256"] == sha(matrix_path)
    assert LAW not in review["missing_branches"]
    branch = next(b for b in matrix["laws"][LAW]["branches"] if b.get("assignment_id") == AID)
    assert branch["status"] == "runnable"
    assert branch["branch_id"] == "continuous_signal_300_ft__C104393__NRS-484B-413-2"
    assert branch["case_ids"] == expected
    assert branch["comparison_ids"] == [comparison["comparison_id"]]
    source_topics = read(ROOT / "inputs/coverage/branch-sources.json")["laws"][LAW]["topics"]
    assert set(branch["topic_ids"]) == set(source_topics)
    for name, digest in branch["cpu_proofs"].items():
        assert sha(HERE / name) == digest, name
    manifest = read(HERE / "draft-execution-manifest.json")
    offline = read(HERE / "draft-offline-summary.json")
    package = read(HERE / "package-probes-summary.json")
    weather = read(HERE / "synthetic-weather-control.json")
    independent = read(HERE / "independent-package-audit.json")
    assert manifest["status"] == "draft_not_selected" and len(manifest["cases"]) == 6
    assert len(offline["results"]) == 24 and all(x["exit_code"] == 0 for x in offline["results"])
    assert package["positive"] == package["negative"] == 24 and package["selected"] is False
    assert weather["cases"] == 6 and weather["native_executed"] is False
    assert independent["positive"] == independent["negative"] == 24
    assert read(HERE / "independent-cpu-audit.json")["passed"] is True
    assert read(HERE / "independent-weather-audit.json")["passed"] is True
    result = read(HERE / "result.json")
    assert result["status"] == "blocked" and result["cases_selected"] == 0
    assert result["recordings_accepted"] == 0 and result["carla_executed"] is False
    receipt = {"format": "c104393-independent-statutory-branch-audit-v1",
               "passed": True, "source_topics": len(source_topics),
               "controlled_cases": 6, "pinned_offline": 24,
               "package_positive_negative_pairs": 24,
               "synthetic_weather_pairs": 6,
               "branch_status": "runnable", "assignment_status": "blocked",
               "native_executed": False,
               "coverage_sha256": sha(matrix_path)}
    (HERE / "independent-statutory-branch-audit.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
