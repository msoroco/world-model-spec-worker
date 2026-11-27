"""Audit original alley attempts before any local delivery decision.

The receipt records source integrity and exterior and interior measurements.
It never labels physical completion or statutory compliance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import STEADY, VARIATION
from saved_delivery import audit, audit_comparison

HERE = Path(__file__).resolve().parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selected(case_id: str) -> dict:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    if manifest.get("assignment_id") != HERE.name:
        raise ValueError("selected manifest identity mismatch")
    entry = next((row for row in manifest.get("cases", []) if row.get("case_id") == case_id), None)
    if entry is None:
        raise ValueError("case absent from selected manifest")
    construction = HERE / entry["construction"]
    if not construction.is_file() or _sha(construction) != entry["construction_sha256"]:
        raise ValueError("selected construction changed")
    binding = entry.get("delivery_acceptance", {}).get("production_source_audit", {})
    if binding.get("script") != "production_audit.py" or binding.get("script_sha256") != _sha(Path(__file__)):
        raise ValueError("selected production auditor changed")
    return entry


def _original(attempt: Path) -> tuple[Path, str]:
    attempt = attempt.resolve()
    capture = attempt / "capture.json"
    if not capture.is_file() or capture.is_symlink():
        raise ValueError("original capture metadata missing or symlinked")
    return attempt, _sha(capture)


def audit_case(case_id: str, attempt: Path) -> dict:
    entry = _selected(case_id)
    attempt, capture_sha = _original(attempt)
    source = audit(attempt, case_id, require_delivery=True)
    if source.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic source cannot enter production receipt")
    return {"format": "worker-alley-production-source-audit", "assignment_id": HERE.name,
            "case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "capture_sha256": capture_sha, "source_audit": source,
            "physical_completion": "pending_independent_review",
            "attention_state": source["attention_state"],
            "original_eyes_off_road_duration_s":
                source["interior_source_audit"]["measured_duration_s"],
            "legal_judgment": "unresolved"}


def audit_pair(steady: Path, variation: Path) -> dict:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    binding = manifest.get("comparison_audit", {})
    if binding.get("script") != "production_audit.py" or binding.get("script_sha256") != _sha(Path(__file__)):
        raise ValueError("selected comparison auditor changed")
    for case in (STEADY, VARIATION):
        _selected(case)
    steady, steady_sha = _original(steady)
    variation, variation_sha = _original(variation)
    result = audit_comparison({STEADY: steady, VARIATION: variation}, require_delivery=True)
    if result.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic pair cannot enter production receipt")
    return {"format": "worker-alley-production-comparison-audit",
            "assignment_id": HERE.name,
            "capture_sha256": {STEADY: steady_sha, VARIATION: variation_sha},
            "comparison": result, "physical_completion": "pending_independent_review",
            "attention_state": "unresolved", "legal_judgment": "unresolved"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=(STEADY, VARIATION))
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--steady", type=Path)
    parser.add_argument("--variation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    single = args.case is not None and args.attempt is not None and args.steady is None and args.variation is None
    pair = args.case is None and args.attempt is None and args.steady is not None and args.variation is not None
    if not (single or pair):
        raise ValueError("supply one exact case attempt or both comparison attempts")
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("audit output already exists")
    receipt = audit_case(args.case, args.attempt) if single else audit_pair(args.steady, args.variation)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
