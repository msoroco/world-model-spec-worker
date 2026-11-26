"""Independently check retained CPU receipts and fixed-context comparison."""
import hashlib
import json
from pathlib import Path

from compare_speed import compare

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
SOURCE = REPO / ".runtime-work"
REQUIRED = {"actual_analysis", "native_validation", "mandatory_observations",
            "lean_decoder", "render", "final_decode", "acquisition_unchanged",
            "derived_outputs_rebuilt", "four_camera_sources", "selected_measurements",
            "negative_case_source"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit():
    entries = []
    paths = []
    for suffix, target in (("a", 7.0), ("b", 14.0)):
        origin = SOURCE / ("c405647-selected-" + suffix + "-compat-v2")
        saved = SOURCE / ("c405647-selected-" + suffix + "-saved-v2/v0001")
        receipt = json.loads((origin / "compatibility.json").read_text())
        processed = json.loads((saved / "processing.json").read_text())
        assert receipt["passed"] is True and REQUIRED <= set(receipt["checks"])
        assert receipt["scope"] == "diagnostic software compatibility only"
        assert processed["passed"] is True and processed["recorded_only"] is True
        assert processed["originals_preserved"] is True
        assert processed["missing_evidence"] is False
        assert processed["physical_acceptance_claimed"] is False
        assert processed["legal_acceptance_claimed"] is False
        assert processed["timestamp_joins"]["frames"] == 600
        assert processed["timestamp_joins"]["passed"] is True
        for name, checksum in processed["original_source_hashes"].items():
            assert sha(origin / name) == checksum, "Saved processing changed " + name
        for name, checksum in receipt["fixture_manifest"].items():
            if name.endswith(".mkv"):
                continue
            assert sha(origin / name) == checksum, "Fixture source changed " + name
        value = receipt["measurement_examples"]["speed_response"]["value"]
        assert value["speed_before_mps"] == 14.0
        assert value["speed_after_mps"] == target
        assert value["reasonable_and_proper_legally_determined"] is False
        assert "Missing required source: emergency_observations.jsonl" in (
            origin / "negative-analysis.log").read_text()
        assert sha(saved / "analysis/result.json") == processed["result_sha256"]
        assert sha(saved / "analysis.log") == processed["analysis_log_sha256"]
        assert sha(origin / "analysis-report.json") == receipt["analysis_report_sha256"]
        entries.append({"case_id": receipt["case_id"],
                        "compatibility_receipt_sha256": sha(origin / "compatibility.json"),
                        "saved_receipt_sha256": sha(saved / "processing.json"),
                        "measured_speed_after_mps": target,
                        "original_source_count_verified": len(processed["original_source_hashes"])})
        paths.append(origin / "emergency_observations.jsonl")
    comparison = compare(*paths, synthetic=True)
    assert comparison["reduction_difference_mps"] == 7.0
    assert comparison["fixed_context_checked_frames"] == 600
    return {"format": "c405647-independent-cpu-diagnostic-audit-v1",
            "passed": True, "scope": "synthetic CPU compatibility and saved processing only",
            "physical_completion_claimed": False, "legal_outcome_claimed": False,
            "cases": entries, "comparison": comparison}


if __name__ == "__main__":
    result = audit()
    path = FOLDER / "selected-diagnostic-audit.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": result["passed"], "cases": len(result["cases"]),
                      "comparison_mps": result["comparison"]["reduction_difference_mps"]}))
