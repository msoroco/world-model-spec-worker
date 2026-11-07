"""Independent exact construction/source/receipt audit of eight v1 probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {"probe_a": "measured_early_decrease_held",
            "probe_b": "measured_no_material_decrease"}
CHECKS = {"actual_analysis", "native_validation", "mandatory_observations",
          "lean_decoder", "render", "final_decode", "acquisition_unchanged"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "draft-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads((HERE / "exact-package-summary.json").read_text())
    assert summary["format"] == "c111294-603-unselected-exact-package-v1"
    assert summary["manifest_sha256"] == sha(manifest_path)
    assert summary["all_passed"] and not summary["ready"]
    assert not summary["carla_executed"] and not summary["accepted"]
    assert len(summary["results"]) == 8
    seen = set()
    for row in summary["results"]:
        case, candidate = row["case_id"], row["candidate_id"]
        suffix = case.split("__")[-1]
        assert suffix in EXPECTED and candidate in ("primary", "fallback1", "fallback2", "fallback3")
        assert (case, candidate) not in seen
        seen.add((case, candidate))
        entry = next(item for item in manifest["cases"] if item["case_id"] == case)
        selected = entry if candidate == "primary" else next(
            item for item in entry["candidates"] if item["id"] == candidate)
        construction = HERE / selected["construction"]
        assert sha(construction) == selected["construction_sha256"] == row["construction_sha256"]
        folder = HERE / "exact-drafts" / suffix / candidate
        receipt_path = folder / "package-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert row["receipt_sha256"] == sha(receipt_path)
        assert receipt["format"] == "worker-package-compatibility-v1"
        assert receipt["passed"] and CHECKS <= set(receipt["checks"])
        assert receipt["case_id"] == case and receipt["candidate_id"] == candidate
        assert receipt["construction_sha256"] == selected["construction_sha256"]
        assert receipt["fixture_sha256"] == row["fixture_sha256"]
        assert receipt["log_sha256"] == row["positive_log_sha256"] == sha(folder / "package-positive.log")
        negative = (folder / "package-negative.log").read_text()
        assert row["negative_log_sha256"] == sha(folder / "package-negative.log")
        assert row["negative_exit_code"] != 0
        assert "Missing required source: native_samples.jsonl" in negative
        output = Path(row["positive_output"])
        assert output.is_dir()
        assert sha(output / "construction.json") == selected["construction_sha256"]
        assert sha(output / "compatibility.json")
        report = json.loads((output / "analysis-report.json").read_text())
        result = json.loads((output / "result.json").read_text())
        contract = json.loads((output / "measurement-contract.json").read_text())
        assert contract["case_id"] == case
        assert set(report["measurements"]) == {
            requirement["output_key"] for requirement in contract["requirements"]}
        for requirement in contract["requirements"]:
            measured = report["measurements"][requirement["output_key"]]
            assert measured["method"] == requirement["method"]
            assert measured["sources"] == {
                name: sha(output / name) for name in requirement["inputs"]}
        assert report["measurements"]["intersection_approach"]["value"]["measured_relation"] == EXPECTED[suffix]
        assert report["original_joins"]["frames"] == 480
        assert set(report["video_frames"].values()) == {480}
        assert not result["accepted"] and result["diagnostic_fixture"]
        assert not result["setup_confirmed"] and not result["behavior_attempted"]
        for index in range(4):
            audit = json.loads((output / f"source-{index}.json").read_text())
            assert audit["passed"] and audit["frames"] == 480
        final = json.loads((output / "final-decode.json").read_text())
        assert final["passed"] and final["frames"] == 480
        assert final["video_sha256"] == sha(output / "event_review.webm")
    assert len(seen) == 8
    print(json.dumps({"passed": True, "audited_exact_v1_packages": len(seen),
                      "positive_and_negative": True, "selected_v2": False,
                      "native_physical": False, "ready": False}, sort_keys=True))


if __name__ == "__main__": main()
