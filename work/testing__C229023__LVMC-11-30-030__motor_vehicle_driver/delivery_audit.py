"""Independent exact-case source, media and sampled-motion delivery audit.

Diagnostic mode exercises the software path without asserting physical or legal
acceptance. Original Native attempts use the same source and media checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID, measure
from saved_capture_audit import audit as audit_capture
from saved_video_audit import audit as audit_video


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(*, attempt: str | Path, case_id: str, diagnostic_test: bool = False) -> dict:
    root = Path(attempt)
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact selected case required")
    if not (root / "context.json").is_file():
        raise ValueError("missing original context source")
    capture = audit_capture(directory=root, case_id=case_id, fixture_mode=diagnostic_test)
    media = audit_video(directory=root, case_id=case_id, fixture_mode=diagnostic_test)
    report_path = root / "crosswalk-measurement.json"
    if report_path.is_symlink() or not report_path.is_file():
        raise ValueError("saved original measurement missing")
    report = json.loads(report_path.read_text())
    if (report.get("case_id") != case_id or report.get("diagnostic_fixture") is not diagnostic_test or
            report.get("physical_acceptance") != "unverified" or report.get("legal_verdict_claimed") is not False):
        raise ValueError("saved measurement scope or physical claim differs")
    measured = measure(case_id=case_id, context_path=root / "context.json",
                       trace_path=root / "trace.jsonl", receipt_path=root / "receipt.json",
                       fixture_mode=diagnostic_test)
    if report.get("measured_values") != measured or report.get("media") != media:
        raise ValueError("saved measurement differs from original source recomputation")
    checks = report.get("target_checks", [])
    if len(checks) != 4 or not all(item.get("matched") is True for item in checks):
        raise ValueError("selected motion observation differs")
    original = {name: sha(root / name) for name in
                ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json")}
    if report.get("source_sha256") != original:
        raise ValueError("saved source hash differs")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "status": "cpu_source_audit_passed", "diagnostic_audit_test_passed": diagnostic_test,
            "measurement_sha256": sha(report_path), "original_source_sha256": original,
            "frame_count": capture["frame_count"],
            "videos_fully_decoded": {name: value["frames"] for name, value in media["videos"].items()},
            "sampled_target_checks": checks,
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--diagnostic-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if args.negative:
        with tempfile.TemporaryDirectory(prefix="delivery-negative-", dir=Path(args.attempt).parent) as temp:
            source = Path(args.attempt) / "receipt.json"
            (Path(temp) / "receipt.json").write_bytes(source.read_bytes())
            print(json.dumps(audit(attempt=temp, case_id=args.case,
                                   diagnostic_test=args.diagnostic_test), indent=2))
    else:
        print(json.dumps(audit(attempt=args.attempt, case_id=args.case,
                               diagnostic_test=args.diagnostic_test), indent=2))


if __name__ == "__main__":
    main()
