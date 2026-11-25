"""Bind bounded receipts from pinned diagnostic compatibility and saved processing.

The raw runtime receipts remain in scratch because they list all 900 graph hashes.
These returned receipts preserve the checks and their raw receipt digests. They
cannot establish original-source or legal acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reviewed_scene import ASSIGNMENT, VARIANTS

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bind(compat: Path, saved: Path, suffix: str) -> None:
    case = ASSIGNMENT + "__" + suffix
    a, b = json.loads(compat.read_text()), json.loads(saved.read_text())
    if not (a["passed"] and b["passed"] and b["recorded_only"]):
        raise ValueError("Pinned diagnostic proof failed")
    if a["case_id"] != case or b["case_id"] != case:
        raise ValueError("Wrong diagnostic case identity")
    if a["construction_sha256"] != b["native_revision"]["construction_sha256"]:
        raise ValueError("Compatibility and saved construction differ")
    if not b["originals_preserved"]:
        raise ValueError("Saved processing changed original sources")
    if b["physical_acceptance_claimed"] or b["legal_acceptance_claimed"]:
        raise ValueError("Synthetic attempt claimed acceptance")
    if a["scope"] != "diagnostic software compatibility only":
        raise ValueError("Unexpected compatibility scope")
    save(ROOT / f"cpu-pinned-compatibility-{suffix}.json", {
        "format": "c147344-bounded-pinned-compatibility-receipt",
        "case_id": case, "source_kind": "synthetic_software_fixture",
        "passed": True, "checks": a["checks"], "scope": a["scope"],
        "construction_sha256": a["construction_sha256"],
        "runtime_manifest_sha256": a["runtime_manifest_sha256"],
        "fixture_sha256": a["fixture_sha256"],
        "measurement_contract_sha256": a["measurement_contract_sha256"],
        "measurement_keys": a["measurement_keys"],
        "measurement_examples": a["measurement_examples"],
        "negative_removed": a["negative_removed"],
        "negative_error_contains": a["negative_error_contains"],
        "negative_log_sha256": a["negative_log_sha256"],
        "raw_receipt_sha256": sha(compat),
    })
    save(ROOT / f"cpu-pinned-saved-{suffix}.json", {
        "format": "c147344-bounded-pinned-saved-receipt",
        "case_id": case, "source_kind": "synthetic_software_fixture",
        "passed": True, "recorded_only": True,
        "construction_sha256": b["native_revision"]["construction_sha256"],
        "originals_preserved": b["originals_preserved"],
        "timestamp_joins": b["timestamp_joins"],
        "analysis_log_sha256": b["analysis_log_sha256"],
        "result_sha256": b["result_sha256"],
        "missing_evidence": b["missing_evidence"],
        "physical_acceptance_claimed": b["physical_acceptance_claimed"],
        "legal_acceptance_claimed": b["legal_acceptance_claimed"],
        "remaining": b["remaining"],
        "raw_receipt_sha256": sha(saved),
    })


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--proof-root", type=Path, required=True)
    ns = p.parse_args()
    for suffix in VARIANTS:
        short = "middle" if suffix == "slow_middle_follower" else suffix
        bind(ns.proof_root / f"pinned-compat-v7-{short}.log",
             ns.proof_root / f"pinned-saved-v2-{short}.log", suffix)
    print("Bound four pinned diagnostic compatibility and saved receipts")


if __name__ == "__main__":
    main()
