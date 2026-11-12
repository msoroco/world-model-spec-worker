"""Read-only verification of C104538 original Native ownership and saved sources.

The in-memory chain checker supports CPU tests; only audit() reads and verifies
an actual sealed Native attempt. Neither path judges legal or pixel visibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]
SOURCES = ("config.json", "construction.json", "runner.py", "road.xodr",
           "obstruction.json", "native-construction-context.json",
           "native_body_history.jsonl", "trace.jsonl", "capture/evidence.jsonl",
           "video_frames.jsonl", "driver_eye_rays.jsonl",
           "candidate-selection.json", "acquisition-provenance.json",
           *(camera + ".mkv" for camera in CAMERAS))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def check_chain(seal: dict, exit_record: dict, owner: dict,
                processing: dict, *, case_id: str, candidate_id: str,
                construction_sha256: str, runner_sha256: str,
                seal_sha256: str, exit_sha256: str) -> dict:
    """Check receipt fields; the caller must separately verify source bytes."""
    revision = {"construction_sha256": construction_sha256,
                "runner_sha256": runner_sha256}
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and
            seal.get("frames") == 480 and
            seal.get("events") == EVENTS[:3] and
            seal.get("restoration", {}).get("restored") is True and
            seal.get("native_revision") == revision,
            "Native capture seal or selected revision differs")
    codes = seal.get("encoder_exit_codes", {})
    require(set(codes) == set(CAMERAS) and all(code == 0 for code in codes.values()),
            "Four source encoders did not close successfully")
    require(set(SOURCES) <= set(seal.get("sources", {})),
            "Native source inventory incomplete")
    require(exit_record.get("event") == "native_exit" and
            exit_record.get("capture_failed") is not True and
            exit_record.get("native_process_exit_code") in (None, 0) and
            exit_record.get("capture_seal_sha256") == seal_sha256 and
            exit_record.get("native_revision") == revision,
            "Native exit does not follow sealed capture")
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("no_resource_operation_performed") is True and
            owner.get("native_exit_sha256") == exit_sha256 and
            owner.get("native_construction_sha256") == construction_sha256,
            "Owner release missing or bound to another Native exit")
    require(processing.get("format") == "worker-saved-processing" and
            processing.get("case_id") == case_id and
            processing.get("candidate_id") == candidate_id and
            processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("originals_preserved") is True and
            processing.get("missing_evidence") is False and
            processing.get("events") == EVENTS[-1:] +
                ["selected_analysis_executed", "originals_verified"] and
            processing.get("native_revision", {}).get("construction_sha256") ==
                construction_sha256,
            "Saved processing is not bound to released Native capture")
    require(all(processing.get("original_source_hashes", {}).get(name) == digest
                for name, digest in seal["sources"].items()),
            "Saved processing source inventory differs from sealed originals")
    return {"events": EVENTS, "source_count": len(seal["sources"]),
            "saved_processing_after_owner_release": True}


def audit(attempt: Path, owner_receipt: Path, processing_path: Path,
          case_id: str, candidate_id: str, construction_sha256: str) -> dict:
    attempt, processing_path = attempt.resolve(), processing_path.resolve()
    require(case_id.startswith("training__C104538__") and
            case_id.endswith(("__below_500_ft", "__at_500_ft", "__above_500_ft")),
            "Unknown exact C104538 case")
    seal_path, exit_path = attempt/"capture-seal.json", attempt/"native-exit.json"
    require(all(path.is_file() for path in
                (seal_path, exit_path, owner_receipt, processing_path)),
            "Original Native seal, exit, owner release or saved processing missing")
    provenance = read(attempt/"acquisition-provenance.json")
    require(provenance.get("provenance_kind") == "native" and
            provenance.get("diagnostic_fixture") is False,
            "Synthetic source cannot establish original Native lifecycle")
    config, selection = read(attempt/"config.json"), read(attempt/"candidate-selection.json")
    require(config.get("case_id") == case_id and
            config.get("selected_case_id") == case_id and
            config.get("candidate_id") == candidate_id and
            config.get("duration_s") == 24 and config.get("rate_hz") == 20 and
            selection.get("case_id") == case_id and
            selection.get("candidate_id") == candidate_id and
            selection.get("construction_sha256") == construction_sha256 and
            sha(attempt/"construction.json") == construction_sha256,
            "Attempt selects another case, candidate or construction")
    seal, exit_record, owner, processing = (read(path) for path in
        (seal_path, exit_path, owner_receipt, processing_path))
    chain = check_chain(seal, exit_record, owner, processing,
                        case_id=case_id, candidate_id=candidate_id,
                        construction_sha256=construction_sha256,
                        runner_sha256=sha(attempt/"runner.py"),
                        seal_sha256=sha(seal_path), exit_sha256=sha(exit_path))
    for name, digest in seal["sources"].items():
        path = (attempt/name).resolve()
        require(attempt in path.parents and path.is_file() and sha(path) == digest,
                "Sealed original source changed: " + name)
    result_path = Path(processing.get("result", "")).resolve()
    require(processing_path.parent in result_path.parents and
            result_path.is_file() and processing.get("result_sha256") == sha(result_path),
            "Saved result missing or changed")
    result = read(result_path)
    require(result.get("case_id") == case_id and
            result.get("provenance_kind") != "synthetic_local_diagnostic" and
            result.get("diagnostic_fixture") is not True,
            "Saved result is synthetic or for another case")
    return {"format": "c104538-original-native-lifecycle-v1",
            "case_id": case_id, "candidate_id": candidate_id,
            "attempt_path": str(attempt), "passed": True,
            "source_shaped_unit_test": False, **chain,
            "capture_seal_sha256": sha(seal_path),
            "native_exit_sha256": sha(exit_path),
            "owner_release_sha256": sha(owner_receipt),
            "saved_processing_sha256": sha(processing_path),
            "source_result_sha256": sha(result_path),
            "legal_verdict_claimed": False,
            "physical_or_pixel_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--owner-receipt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--construction-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.owner_receipt, args.processing,
                           args.case, args.candidate, args.construction_sha256), indent=2))
