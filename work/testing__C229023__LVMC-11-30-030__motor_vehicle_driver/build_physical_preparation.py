"""Build source-bound synthetic completion and Native lifecycle CPU proofs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES


ROOT = Path(__file__).resolve().parent
SCRATCH = Path(__file__).resolve().parents[2] / ".runtime-work" / "lead-nov24-converter"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def check_lifecycle(events: list[str]) -> None:
    if events != EVENTS:
        raise ValueError("saved processing precedes Native exit or owner release")


def outcome(*, case_id: str, source: Path, kind: str) -> dict:
    receipt = json.loads((source / "receipt.json").read_text())
    report = json.loads((source / "crosswalk-measurement.json").read_text())
    if (receipt.get("case_id") != case_id or receipt.get("diagnostic_fixture") is not True or
            report.get("case_id") != case_id or report.get("diagnostic_fixture") is not True):
        raise ValueError("exact diagnostic source required")
    rows = (source / "trace.jsonl").read_text().splitlines()
    if len(rows) != 900 or sha(source / "trace.jsonl") != receipt.get("trace_sha256"):
        raise ValueError("sealed complete diagnostic trace required")
    if kind == "complete_motion":
        if not all(item.get("matched") is True for item in report["target_checks"]):
            raise ValueError("selected diagnostic targets not sampled")
        status, count = "met", 900
    elif kind == "incomplete_motion":
        status, count = "not_met", 200
    elif kind == "missing_evidence":
        status, count = "unverified", 0
    else:
        raise ValueError("unknown fixture kind")
    sources = {"receipt_sha256": sha(source / "receipt.json"),
               "trace_sha256": receipt["trace_sha256"],
               "measurement_sha256": sha(source / "crosswalk-measurement.json"),
               "sampled_frames": count,
               "fixture_recipe": "fixture-recipe-" + case_id.removeprefix(ROOT.name + "__") + ".json"}
    return {"format": "diagnostic-physical-outcome", "case_id": case_id,
            "fixture_kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status,
                            "method": "sealed diagnostic actor trace and selected measurement target checks",
                            "sources": sources}},
            "realized_observables": report["observed"] if status == "met" else {},
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def build() -> None:
    for suffix in CASES:
        case_id = ROOT.name + "__" + suffix
        source = SCRATCH / ("unmarked-pass-v4" if suffix == "unmarked_pass" else "compat-" + suffix)
        dest = ROOT / "cases" / suffix
        dest.mkdir(parents=True, exist_ok=True)
        construction = ROOT / ("construction-" + suffix + ".json")
        if not construction.is_file():
            raise ValueError("selected construction missing: " + suffix)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = outcome(case_id=case_id, source=source, kind=kind)
            result_path = dest / ("physical-" + kind + ".json")
            log_path = dest / ("physical-" + kind + ".log")
            write(result_path, result)
            write(log_path, {"case_id": case_id, "fixture_kind": kind,
                             "observed_status": result["physical_checks"]["maneuver"]["status"],
                             "source_receipt_sha256": result["physical_checks"]["maneuver"]["sources"]["receipt_sha256"],
                             "passed": True})
            fixtures.append({"kind": kind,
                             "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ROOT.name + "/build_physical_preparation.py",
                             "exit_code": 0,
                             "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path),
                             "result": str(result_path.relative_to(ROOT)), "result_sha256": sha(result_path)})
        check_lifecycle(EVENTS)
        try:
            check_lifecycle(EVENTS[:-2] + ["saved_processing_started", "owner_released"])
        except ValueError as error:
            negative_error = str(error)
        else:
            raise AssertionError("invalid lifecycle accepted")
        life_path = dest / "physical-lifecycle.log"
        write(life_path, {"case_id": case_id, "events": EVENTS,
                          "early-processing-negative": negative_error, "passed": True})
        receipt_path = dest / "physical-preparation.json"
        write(receipt_path, {"format": "worker-physical-preparation",
                             "case_id": case_id, "construction_sha256": sha(construction),
                             "fixtures": fixtures,
                             "lifecycle": {"events": EVENTS, "exit_code": 0,
                                           "log": str(life_path.relative_to(ROOT)),
                                           "log_sha256": sha(life_path)}})
    print("built", len(CASES), "source-bound diagnostic physical preparation receipts")


if __name__ == "__main__":
    build()
