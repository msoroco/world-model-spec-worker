"""Read-only check of a C10014 physical outcome before proof binding.

The selected synthetic compatibility result must never satisfy this check.
Measured outcomes require an original Native closure chain and frame joins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import check_original_rows
from lifecycle_audit import audit as audit_lifecycle


EXPECTED = {"complete_motion": "met", "incomplete_motion": "not_met",
            "missing_evidence": "unverified"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_result(result: dict, kind: str, case_id: str, *,
                 test_shape: bool = False) -> dict:
    require(kind in EXPECTED, "Unknown physical outcome kind")
    check = result.get("physical_checks", {}).get("maneuver", {})
    expected = EXPECTED[kind]
    require(result.get("case_id") == case_id and
            result.get("provenance_kind") == "native" and
            result.get("diagnostic_fixture") in (None, False) and
            (result.get("source_shaped_unit_test") is True) == test_shape and
            result.get("accepted") is not True and
            result.get("legal_verdict_claimed") is not True,
            "Synthetic or accepted result cannot prove Native physical outcome")
    require(check.get("status") == expected and check.get("method") and
            isinstance(check.get("sources"), dict) and check["sources"] and
            result.get("maneuver_completed") is (expected == "met"),
            "Physical outcome status lacks measured source contract")
    if expected == "met":
        require(result.get("realized_observables"),
                "Completed motion lacks realized Native observations")
    return {"kind": kind, "status": expected, "sources": check["sources"]}


def audit(attempt: Path, owner_receipt: Path, processing_path: Path,
          kind: str, case_id: str, construction_sha256: str, *,
          test_shape: bool = False) -> dict:
    attempt = attempt.resolve()
    processing_path = processing_path.resolve()
    processing = read(processing_path)
    result_path = Path(processing.get("result", "")).resolve()
    require(processing_path.parent in result_path.parents and result_path.is_file() and
            processing.get("result_sha256") == sha(result_path),
            "Saved physical result missing or changed")
    result = read(result_path)
    outcome = check_result(result, kind, case_id, test_shape=test_shape)
    require(processing.get("case_id") == case_id and
            processing.get("passed") is True and
            processing.get("native_revision", {}).get("construction_sha256") ==
                construction_sha256 and
            processing.get("recorded_only") is True and
            processing.get("originals_preserved") is True,
            "Physical outcome does not bind selected saved processing")
    if kind != "missing_evidence":
        require(processing.get("missing_evidence") is False,
                "Measured motion cannot have missing analysis evidence")
    else:
        require(processing.get("missing_evidence") is True,
                "Missing-evidence outcome must come from saved analysis")
    for name, digest in outcome["sources"].items():
        source = (attempt / name).resolve()
        require(attempt in source.parents and source.is_file() and
                sha(source) == digest and
                processing.get("original_source_hashes", {}).get(name) == digest,
                "Physical source missing or changed: " + name)
    if kind != "missing_evidence":
        closure = audit_lifecycle(attempt, owner_receipt, processing_path,
                                  case_id, construction_sha256,
                                  test_shape=test_shape)
        original = check_original_rows(attempt, 480, test_shape=test_shape)
    else:
        if (attempt / "capture-seal.json").is_file():
            closure = audit_lifecycle(attempt, owner_receipt, processing_path,
                                      case_id, construction_sha256,
                                      test_shape=test_shape)
        else:
            # A failed acquisition can lack a seal. Require its Native failure
            # record instead of accepting an unmarked synthetic missing source.
            status_path = attempt / "native-run-status.json"
            exit_path = attempt / "native-exit.json"
            require(status_path.is_file() and exit_path.is_file() and
                    read(status_path).get("errors") and
                    read(exit_path).get("event") == "native_exit" and
                    read(exit_path).get("capture_failed") is True and
                    read(exit_path).get("native_revision", {}).get(
                        "construction_sha256") == construction_sha256,
                    "Missing evidence lacks an original failed Native acquisition")
            closure = None
        original = None
    return {"kind": kind, "case_id": case_id,
            "source_shaped_unit_test": test_shape,
            "construction_sha256": construction_sha256,
            "result_sha256": sha(result_path),
            "processing_sha256": sha(processing_path),
            "status": outcome["status"],
            "source_hashes": outcome["sources"],
            "native_lifecycle": closure, "original_frame_join": original,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--owner-receipt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--kind", choices=sorted(EXPECTED), required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.owner_receipt, args.processing,
                           args.kind, args.case, args.construction_sha256), indent=2))


if __name__ == "__main__":
    main()
