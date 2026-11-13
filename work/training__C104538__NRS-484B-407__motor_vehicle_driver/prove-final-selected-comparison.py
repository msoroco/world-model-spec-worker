"""Reprove the selected 450/500/550-foot comparison on final-manifest sources."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shlex

from comparison_audit import compare, load_case, read, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")


def option(command: str, name: str) -> Path:
    tokens = shlex.split(command)
    return Path(tokens[tokens.index(name) + 1])


def rejects(call, expected: str) -> None:
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"Wrong rejection: {error}") from error
    else:
        raise AssertionError("Expected rejection: " + expected)


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    matrix_path = HERE / "update027-final-manifest-matrix.json"
    matrix = read(matrix_path)
    plan = read(HERE / "case-plan.json")["comparisons"][0]
    assert matrix["manifest_sha256"] == sha(manifest_path)
    assert [entry["case_id"].rsplit("__", 1)[-1] for entry in manifest["cases"]] == list(SUFFIXES)
    primary = {row["case_id"]: row for row in matrix["results"]
               if row["candidate_id"] == "primary"}
    assert set(primary) == {entry["case_id"] for entry in manifest["cases"]}
    records = []
    for entry in manifest["cases"]:
        row = primary[entry["case_id"]]
        attempt = option(row["compatibility_command"], "--output")
        saved = option(row["saved_command"], "--output")
        assert attempt.is_relative_to(ROOT / ".runtime-work")
        assert saved.is_relative_to(ROOT / ".runtime-work")
        assert sha(attempt / "candidate-selection.json") == row["proofs"]["candidate-selection.json"]
        assert sha(saved / "v0001/processing.json") == row["proofs"]["processing.json"]
        records.append(load_case(attempt, saved, entry["case_id"],
                                 entry["construction_sha256"], sha(manifest_path)))

    report = compare(records, plan, diagnostic=True)
    assert report["authored_center_reference_limits_ft"] == [450, 500, 550]
    assert not report["comparison_complete"] and not report["original_visibility_proven"]
    negatives = {}
    changes = (
        ("changed_camera", lambda x: x[1]["config"]["cameras"][1].update(width=999),
         "Undeclared camera, capture, law or controller difference"),
        ("changed_road", lambda x: x[1]["source_sha256"].update({"road.xodr": "0" * 64}),
         "Fixed authored road differs"),
        ("changed_geometry", lambda x: x[2]["obstruction"].update(
            inner_radius_m=x[1]["obstruction"]["inner_radius_m"]),
         "Authored sightline limit differs from geometry"),
        ("changed_capture", lambda x: x[1]["source_sha256"].update(
            {"capture/evidence.jsonl": "0" * 64}),
         "Diagnostic fixed motion or capture source differs"),
    )
    for name, change, expected in changes:
        damaged = copy.deepcopy(records)
        change(damaged)
        rejects(lambda: compare(damaged, plan, diagnostic=True), expected)
        negatives[name] = expected
    rejects(lambda: compare(records, plan, diagnostic=False),
            "Comparison needs three original delivery audits")
    negatives["missing_original_delivery"] = "Comparison needs three original delivery audits"
    fake = [{"format": "worker-delivery-audit", "passed": True,
             "case_id": record["case_id"], "attempt_path": record["attempt"],
             "checks": {key: True for key in (
                 "native_source", "all_participants", "time_join",
                 "full_video_decode", "actual_pixels", "physical_completion")}}
            for record in records]
    rejects(lambda: compare(records, plan, diagnostic=False, delivery_receipts=fake),
            "Comparison lacks independent original delivery acceptance")
    negatives["fake_original_delivery"] = "Comparison lacks independent original delivery acceptance"
    proof = {"format": "c104538-final-selected-comparison-cpu-proof-v1",
             "selected_manifest_sha256": sha(manifest_path),
             "selected_matrix_sha256": sha(matrix_path),
             "comparison_auditor_sha256": sha(HERE / "comparison_audit.py"),
             "case_ids": report["case_ids"],
             "authored_center_reference_limits_ft": report["authored_center_reference_limits_ft"],
             "fixed_conditions_checked": report["fixed_conditions_checked"],
             "source_sha256": report["source_sha256"],
             "negative_rejections": negatives,
             "diagnostic_comparison_passed": True,
             "original_comparison_accepted": False,
             "original_native_or_pixel_visibility_proven": False,
             "legal_verdict_claimed": False}
    path = HERE / "update027-final-selected-comparison.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(records), "negative_rejections": len(negatives),
                      "original_comparison_accepted": False, "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
