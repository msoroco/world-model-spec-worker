"""Exercise the complete C10316 delivery boundary on an explicit CPU test shape.

The temporary attempt hard-links retained diagnostic sources, creates only
source-shaped lifecycle/review data, and is deleted after the proof. It cannot
be used as an original Native receipt or a delivery acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from delivery_audit import CAMERAS, VIEW_SUBJECTS, audit, sha
from comparison_audit import audit_pair
from physical_outcome_audit import SOURCES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()  # Break a hard link before changing a temporary test shape.
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def shape(root: Path, suffix: str):
    source = ROOT / ".runtime-work" / f"c10316-current-{suffix}-primary-compat"
    original_saved = (ROOT / ".runtime-work" /
                      f"c10316-current-{suffix}-primary-saved/v0001")
    case = HERE.name + "__" + suffix
    attempt = root / "attempt"
    shutil.copytree(source, attempt, copy_function=os.link,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    saved = root / "saved/v0001"
    (saved / "analysis").mkdir(parents=True)
    construction = sha(attempt / "construction.json")
    context = json.loads((attempt / "crosswalk-context.json").read_text())
    context["native_map_sha256"] = "source-shaped-map-digest"
    write(attempt / "crosswalk-context.json", context)
    write(attempt / "native-construction-context.json", {
        "case_id": case, "native_map_sha256": context["native_map_sha256"],
        "source_shaped_unit_test": True,
        "requested_plan": {
            "engineering": {"target_lateral_m":
                            -0.65 if suffix == "reference" else 0.65}}})
    sources = {str(path.relative_to(attempt)): sha(path)
               for path in attempt.rglob("*") if path.is_file()}
    assert set(SOURCES) <= set(sources)
    assert {name + ".mkv" for name in CAMERAS} <= set(sources)
    seal = {"format": "worker-sealed-capture",
            "provenance_kind": "source_shaped_unit_test",
            "diagnostic_fixture": True, "source_shaped_unit_test": True,
            "frames": 240,
            "events": ["capture_finished", "encoders_closed",
                       "restoration_verified"],
            "restoration": {"restored": True},
            "encoder_exit_codes": {name: 0 for name in CAMERAS},
            "native_revision": {"construction_sha256": construction,
                                "runner_sha256": sha(attempt / "runner.py")},
            "sources": sources}
    write(attempt / "capture-seal.json", seal)
    write(attempt / "native-exit.json", {
        "event": "native_exit", "native_process_exit_code": 0,
        "capture_seal_sha256": sha(attempt / "capture-seal.json"),
        "native_revision": seal["native_revision"]})
    owner = root / "owner-release.json"
    write(owner, {"event": "owner_released", "operator_attested": True,
                  "no_resource_operation_performed": True,
                  "native_exit_sha256": sha(attempt / "native-exit.json"),
                  "native_construction_sha256": construction,
                  "source_shaped_unit_test": True})
    result = json.loads((original_saved / "analysis/result.json").read_text())
    result.update(provenance_kind="synthetic_local_diagnostic",
                  diagnostic_fixture=True, source_shaped_unit_test=True,
                  maneuver_completed=False, accepted=False,
                  legal_verdict_claimed=False)
    result_path = saved / "analysis/result.json"
    write(result_path, result)
    processing = {"format": "worker-saved-processing", "case_id": case,
                  "source_shaped_unit_test": True, "passed": True,
                  "recorded_only": True, "originals_preserved": True,
                  "native_revision": {"construction_sha256": construction},
                  "events": ["saved_processing_started",
                             "selected_analysis_executed", "originals_verified"],
                  "original_source_hashes": sources, "result": str(result_path),
                  "result_sha256": sha(result_path), "missing_evidence": False,
                  "timestamp_joins": {"frames": 240, "passed": True}}
    write(saved / "processing.json", processing)
    pixel = root / "pixel-review.json"
    write(pixel, {"format": "c10316-source-pixel-review-v1",
                  "case_id": case, "frames": 240, "reviewer": "CPU unit shape",
                  "method": "source-shaped protocol test only",
                  "source_kind": "source_shaped_unit_test",
                  "legal_verdict_claimed": False,
                  "views": {name: {
                      "video_sha256": sha(attempt / (name + ".mkv")),
                      "subjects_visible": sorted(VIEW_SUBJECTS[name]),
                      "reviewed_crosswalk_frames": 112,
                      "limitations": ["No original Native pixels reviewed"]}
                      for name in CAMERAS}})
    crossing = root / "crossing-review.json"
    facts = {name: {"observation": "source-shaped placeholder",
                    "source_path": "crosswalk-context.json",
                    "source_sha256": sha(attempt / "crosswalk-context.json")}
             for name in ("signals", "passage_space", "obstacles",
                          "other_pedestrians")}
    write(crossing, {"format": "c10316-crossing-context-review-v1",
                     "case_id": case, "reviewer": "CPU unit shape",
                     "method": "source-shaped protocol test only",
                     "source_kind": "source_shaped_unit_test",
                     "crosswalk_context_sha256":
                         sha(attempt / "crosswalk-context.json"),
                     "native_construction_sha256":
                         sha(attempt / "native-construction-context.json"),
                     "native_map_sha256": context["native_map_sha256"],
                     "marked_highway_crosswalk_confirmed": True,
                     "alley_route_connection_confirmed": True,
                     "practicability_judgment": "unverified",
                     "legal_verdict_claimed": False, "facts": facts})
    return attempt, saved, owner, construction, pixel, crossing, case


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="c10316-delivery-shape-",
                                     dir=ROOT / ".runtime-work") as directory:
        audit_paths = []
        source_hashes = {}
        for suffix in ("reference", "contrast"):
            folder = Path(directory) / suffix
            folder.mkdir()
            (attempt, saved, owner, construction, pixel,
             crossing, case) = shape(folder, suffix)
            report = audit(attempt, saved, owner, case, construction, pixel,
                           crossing, attempt / "raw.mkv",
                           attempt / "converted/trace.json",
                           folder / "decode", test_shape=True)
            if (report["passed"] or report["motion_status"] != "unverified" or
                    report["practicability_judgment"] != "unverified" or
                    report["legal_verdict_claimed"]):
                raise AssertionError("Source-shaped protocol data was promoted")
            audit_path = folder / "delivery-audit-source-shape.json"
            write(audit_path, report)
            audit_paths.append(audit_path)
            source_hashes[case] = {name: sha(attempt / name) for name in SOURCES}
        comparison = audit_pair(*audit_paths, test_shape=True)
        if comparison["passed"] or comparison["legal_verdict_claimed"]:
            raise AssertionError("Source-shaped comparison was promoted")
        summary = {"format": "c10316-full-delivery-source-shape-proof-v1",
                   "auditor_sha256": sha(HERE / "delivery_audit.py"),
                   "lifecycle_auditor_sha256": sha(HERE / "lifecycle_audit.py"),
                   "motion_auditor_sha256": sha(HERE / "physical_outcome_audit.py"),
                   "selected_manifest_sha256": sha(HERE / "execution-manifest.json"),
                   "selected_case_ids": [HERE.name + "__reference",
                                         HERE.name + "__contrast"],
                   "source_shaped_source_sha256": source_hashes,
                   "full_decode_receipts": 10,
                   "delivery_checks_exercised": sorted(report["checks"]),
                   "source_shaped_report_passed": report["passed"],
                   "source_shaped_comparison_passed": comparison["passed"],
                   "observed_mean_lateral_separation_m":
                       comparison["observed_mean_lateral_separation_m"],
                   "native_motion_status": report["motion_status"],
                   "original_native_or_legal_acceptance": False}
    path = HERE / "update022-delivery-source-shape-proof.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"full_decode_receipts": 10,
                      "source_shaped_report_passed": False,
                      "source_shaped_comparison_passed": False,
                      "original_native_or_legal_acceptance": False,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
