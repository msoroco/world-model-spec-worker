"""Exercise selected comparison isolation and rejection branches on CPU."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from comparison_audit import audit, compare, load_case, read, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")


def rejects(call, expected: str) -> None:
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"Wrong rejection: {error}") from error
    else:
        raise AssertionError("Expected comparison rejection: " + expected)


def run() -> dict:
    manifest_path = HERE/"execution-manifest.json"
    manifest = read(manifest_path)
    plan = read(HERE/"case-plan.json")["comparisons"][0]
    attempts = [ROOT/".runtime-work"/(
        "c104538-final-below-primary-compat" if suffix == "below_500_ft" else
        f"c104538-final-{suffix}-primary-compat") for suffix in SUFFIXES]
    saved = [ROOT/".runtime-work"/(
        "c104538-final-below-primary-saved" if suffix == "below_500_ft" else
        f"c104538-final-{suffix}-primary-saved") for suffix in SUFFIXES]
    records = [load_case(a, s, entry["case_id"], entry["construction_sha256"],
                         sha(manifest_path))
               for a, s, entry in zip(attempts, saved, manifest["cases"])]
    comparison = audit(attempts, saved, diagnostic=True)
    assert comparison["comparison_complete"] is False
    assert comparison["original_visibility_proven"] is False
    assert comparison["authored_center_reference_limits_ft"] == [450, 500, 550]
    changed = copy.deepcopy(records)
    changed[1]["config"]["cameras"][1]["width"] += 1
    rejects(lambda: compare(changed, plan, diagnostic=True),
            "Undeclared camera, capture, law or controller difference")
    changed = copy.deepcopy(records)
    changed[1]["source_sha256"]["road.xodr"] = "0"*64
    rejects(lambda: compare(changed, plan, diagnostic=True), "Fixed authored road differs")
    changed = copy.deepcopy(records)
    changed[2]["obstruction"]["inner_radius_m"] = changed[1]["obstruction"]["inner_radius_m"]
    rejects(lambda: compare(changed, plan, diagnostic=True),
            "Authored sightline limit differs from geometry")
    changed = copy.deepcopy(records)
    changed[1]["source_sha256"]["trace.jsonl"] = "0"*64
    rejects(lambda: compare(changed, plan, diagnostic=True),
            "Diagnostic fixed motion or capture source differs")
    with tempfile.TemporaryDirectory(dir=ROOT/".runtime-work") as temporary:
        damaged_saved = Path(temporary)
        target = damaged_saved/"v0001/processing.json"
        target.parent.mkdir()
        processing = copy.deepcopy(records[0]["processing"])
        processing["original_source_hashes"]["road.xodr"] = "0"*64
        target.write_text(json.dumps(processing))
        rejects(lambda: load_case(attempts[0], damaged_saved,
                                  records[0]["case_id"],
                                  manifest["cases"][0]["construction_sha256"],
                                  sha(manifest_path)),
                "Comparison saved processing incomplete")
    rejects(lambda: compare(records, plan, diagnostic=False),
            "Comparison needs three original delivery audits")
    fake = [{"format": "worker-delivery-audit", "passed": True,
             "case_id": record["case_id"], "attempt_path": record["attempt"],
             "checks": {key: True for key in (
                 "native_source", "all_participants", "time_join",
                 "full_video_decode", "actual_pixels", "physical_completion")}}
            for record in records]
    rejects(lambda: compare(records, plan, diagnostic=False,
                            delivery_receipts=fake),
            "Comparison lacks independent original delivery acceptance")
    report = {"format": "c104538-comparison-cpu-proof-v1",
              "comparison_id": comparison["comparison_id"],
              "case_ids": comparison["case_ids"],
              "authored_center_reference_limits_ft":
                  comparison["authored_center_reference_limits_ft"],
              "fixed_conditions_checked": comparison["fixed_conditions_checked"],
              "negative_rejections": ["changed_camera", "changed_road",
                                      "changed_geometry_limit", "changed_trace",
                                      "changed_saved_source_hash",
                                      "missing_delivery_audits", "false_acceptance"],
              "comparison_complete": False,
              "original_visibility_proven": False,
              "source_sha256": comparison["source_sha256"]}
    path = HERE/"update019-comparison-cpu-proof.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return {"case_count": len(records), "negative_rejections": 7,
            "proof_sha256": sha(path), "comparison_complete": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
