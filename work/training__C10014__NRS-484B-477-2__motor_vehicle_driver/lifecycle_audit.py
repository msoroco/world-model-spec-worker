"""Verify the original Native closure chain before physical preparation.

This verifier is read-only. A source-shaped unit test is not a Native receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt: Path, owner_receipt: Path, processing_path: Path,
          case_id: str, construction_sha256: str, *, test_shape: bool = False) -> dict:
    attempt = attempt.resolve()
    processing_path = processing_path.resolve()
    seal_path = attempt / "capture-seal.json"
    exit_path = attempt / "native-exit.json"
    require(seal_path.is_file() and exit_path.is_file(),
            "Original Native capture seal or exit missing")
    seal, exit_record, owner, processing = (read(path) for path in
        (seal_path, exit_path, owner_receipt, processing_path))
    require((seal.get("source_shaped_unit_test") is True) == test_shape and
            (processing.get("source_shaped_unit_test") is True) == test_shape,
            "Source-shaped unit test cannot establish original Native lifecycle")
    revision = seal.get("native_revision", {})
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and
            seal.get("frames") == 480 and
            seal.get("events") == EVENTS[:3] and
            seal.get("restoration", {}).get("restored") is True and
            set(seal.get("encoder_exit_codes", {})) == set(CAMERAS) and
            all(code == 0 for code in seal["encoder_exit_codes"].values()) and
            revision.get("construction_sha256") == construction_sha256 and
            revision.get("runner_sha256") == sha(attempt / "runner.py"),
            "Native closure or selected construction differs")
    sources = seal.get("sources", {})
    require(all(name in sources for name in
                ("runner.py", "construction.json", "native_samples.jsonl",
                 "video_frames.jsonl", *(camera + ".mkv" for camera in CAMERAS))),
            "Original Native source inventory incomplete")
    for name, digest in sources.items():
        source = (attempt / name).resolve()
        require(attempt in source.parents and source.is_file() and sha(source) == digest,
                "Sealed original source changed: " + name)
    require(exit_record.get("event") == "native_exit" and
            exit_record.get("capture_failed") is not True and
            exit_record.get("native_process_exit_code") == 0 and
            exit_record.get("capture_seal_sha256") == sha(seal_path) and
            exit_record.get("native_revision") == revision,
            "Native exit does not follow sealed capture")
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("no_resource_operation_performed") is True and
            owner.get("native_exit_sha256") == sha(exit_path) and
            owner.get("native_construction_sha256") == construction_sha256,
            "Owner release absent or before Native exit")
    require(processing.get("format") == "worker-saved-processing" and
            processing.get("case_id") == case_id and
            processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("originals_preserved") is True and
            processing.get("native_revision", {}).get("construction_sha256") ==
                construction_sha256 and
            processing.get("events") == ["saved_processing_started",
                                         "selected_analysis_executed", "originals_verified"],
            "Saved processing is not bound to released Native capture")
    for name, digest in sources.items():
        require(processing.get("original_source_hashes", {}).get(name) == digest,
                "Saved processing source hash differs: " + name)
    result_path = Path(processing.get("result", "")).resolve()
    require(processing_path.parent in result_path.parents and result_path.is_file() and
            processing.get("result_sha256") == sha(result_path),
            "Saved result is missing or changed")
    result = read(result_path)
    require(result.get("case_id") == case_id and
            result.get("provenance_kind") == "native" and
            result.get("diagnostic_fixture") in (None, False) and
            (result.get("source_shaped_unit_test") is True) == test_shape,
            "Saved result is synthetic or for another case")
    return {"case_id": case_id, "construction_sha256": construction_sha256,
            "events": EVENTS, "exit_code": 0,
            "source_shaped_unit_test": test_shape,
            "capture_seal_sha256": sha(seal_path),
            "native_exit_sha256": sha(exit_path),
            "owner_release_sha256": sha(owner_receipt),
            "saved_processing_sha256": sha(processing_path),
            "result_sha256": sha(result_path),
            "scope": ("source-shaped CPU unit test only; no original Native, physical or legal acceptance"
                      if test_shape else
                      "original Native closure and source preservation; no physical or legal acceptance")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--owner-receipt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.owner_receipt, args.processing,
                           args.case, args.construction_sha256), indent=2))


if __name__ == "__main__":
    main()
