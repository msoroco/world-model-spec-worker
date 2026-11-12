"""CPU tests for closure ordering; no source-shaped receipt is returned as Native."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from lifecycle_audit import CAMERAS, SOURCES, audit, check_chain

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__below_500_ft"
CONSTRUCTION = "c" * 64
RUNNER = "r" * 64
SEAL = "s" * 64
EXIT = "e" * 64


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(call, expected: str) -> None:
    try:
        call()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("Expected rejection: " + expected)


def run() -> dict:
    revision = {"construction_sha256": CONSTRUCTION, "runner_sha256": RUNNER}
    sources = {name: "0" * 64 for name in SOURCES}
    seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": False, "frames": 480,
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "restoration": {"restored": True},
            "encoder_exit_codes": {name: 0 for name in CAMERAS},
            "native_revision": revision, "sources": sources}
    exit_record = {"event": "native_exit", "capture_seal_sha256": SEAL,
                   "native_revision": revision}
    owner = {"event": "owner_released", "operator_attested": True,
             "no_resource_operation_performed": True,
             "native_exit_sha256": EXIT,
             "native_construction_sha256": CONSTRUCTION}
    processing = {"format": "worker-saved-processing", "case_id": CASE,
                  "candidate_id": "primary", "passed": True,
                  "recorded_only": True, "originals_preserved": True,
                  "missing_evidence": False,
                  "events": ["saved_processing_started", "selected_analysis_executed",
                             "originals_verified"],
                  "native_revision": {"construction_sha256": CONSTRUCTION},
                  "original_source_hashes": sources}
    def check(**changes):
        values = {"seal": seal, "exit_record": exit_record,
                  "owner": owner, "processing": processing}
        values.update(changes)
        return check_chain(**values, case_id=CASE, candidate_id="primary",
                           construction_sha256=CONSTRUCTION,
                           runner_sha256=RUNNER, seal_sha256=SEAL,
                           exit_sha256=EXIT)
    assert check()["saved_processing_after_owner_release"] is True
    negatives = [
        ("synthetic seal", "seal", "provenance_kind", "synthetic_fixture",
         "Native capture seal"),
        ("wrong frame count", "seal", "frames", 479, "Native capture seal"),
        ("missing encoder", "seal", "encoder_exit_codes", {"overview": 0},
         "Four source encoders"),
        ("failed restoration", "seal", "restoration", {"restored": False},
         "Native capture seal"),
        ("wrong Native exit", "exit_record", "capture_seal_sha256", "x" * 64,
         "Native exit does not follow"),
        ("unreleased owner", "owner", "operator_attested", False,
         "Owner release missing"),
        ("early saved processing", "processing", "events",
         ["selected_analysis_executed", "saved_processing_started", "originals_verified"],
         "Saved processing is not bound"),
        ("altered source", "processing", "original_source_hashes", {},
         "Saved processing source inventory"),
    ]
    for _, target, key, value, message in negatives:
        damaged = copy.deepcopy({"seal": seal, "exit_record": exit_record,
                                 "owner": owner, "processing": processing})
        damaged[target][key] = value
        rejects(lambda damaged=damaged: check(**damaged), message)
    attempt = ROOT/".runtime-work/c104538-final-below-primary-compat"
    saved = ROOT/".runtime-work/c104538-final-below-primary-saved/v0001/processing.json"
    rejects(lambda: audit(attempt, attempt/"owner-release.json", saved,
                          CASE, "primary", sha(attempt/"construction.json")),
            "Original Native seal, exit, owner release")
    report = {"format": "c104538-lifecycle-cpu-proof-v1",
              "source_shaped_chain_passed": True,
              "source_shaped_unit_test": True,
              "negative_checks": [name for name, *_ in negatives] +
                  ["synthetic attempt lacks Native closure"],
              "original_native_lifecycle_verified": False,
              "legal_verdict_claimed": False}
    path = HERE/"update020-lifecycle-cpu-proof.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return {"negative_checks": len(report["negative_checks"]),
            "proof_sha256": sha(path), "original_native_lifecycle_verified": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
