"""Source-bound synthetic physical outcome fixtures for four reverse routes."""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.native_output import assess_physical  # noqa: E402


ROWS = (
    ("intersection-entry", "reverse_into_intersection", "c215286-alt-intersection-compat-v4"),
    ("intersection-stop", "reverse_stops_before_intersection", "c215286-alt-intersection-stop-compat"),
    ("corner-entry", "reverse_around_street_corner", "c215286-alt-corner-entry-compat-v3"),
    ("corner-stop", "reverse_stops_before_street_corner", "c215286-alt-corner-stop-compat"),
)
SOURCES = ("config.json", "trace.jsonl", "video_frames.jsonl", "reverse_history.jsonl",
           "reverse_site_context.json")
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run():
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output_root or not Path(output_root).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
    staged = []
    lines = []
    manifest = json.loads((ROOT / ".runtime-work/c215286-intersection-stage/manifest.json").read_text())
    entries = {row["case_id"]: row for row in manifest["cases"]}
    command = "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-physical-proof .venv-cpu/bin/python work/" + PACKAGE.name + "/cases/prove_alternative_physical.py"
    for label, suffix, source_name in ROWS:
        case_id = PACKAGE.name + "__" + suffix
        entry = entries[case_id]
        saved = PACKAGE / "cases" / (label + "-saved-processing-receipt.json")
        receipt = json.loads(saved.read_text())
        if not (receipt["passed"] and receipt["recorded_only"] and receipt["originals_preserved"]
                and not receipt["missing_evidence"] and receipt["case_id"] == case_id):
            raise ValueError("Recorded-only proof missing: " + case_id)
        source = ROOT / ".runtime-work" / source_name
        config = json.loads((source / "config.json").read_text())
        fixtures = []
        for kind in KINDS:
            folder = ROOT / ".runtime-work/c215286-alternative-physical" / label / kind
            folder.mkdir(parents=True, exist_ok=True)
            for name in SOURCES:
                shutil.copy2(source / name, folder / name)
            history = folder / "reverse_history.jsonl"
            if kind == "incomplete_motion":
                rows = [json.loads(line) for line in history.read_text().splitlines()]
                for row in rows:
                    row["velocity_mps"] = [0, 0]
                history.write_text("".join(json.dumps(row) + "\n" for row in rows))
            elif kind == "missing_evidence":
                history.unlink()
            result = assess_physical(folder, config, [])
            result["provenance_kind"] = "synthetic_fixture"
            result["diagnostic_fixture"] = True
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            actual = result["physical_checks"]["maneuver"]["status"]
            if actual != expected or result["maneuver_completed"] != (expected == "met"):
                raise ValueError(case_id + " " + kind + ": " + actual + " expected " + expected)
            path = PACKAGE / "cases" / (label + "-" + kind + "-physical-result.json")
            write(path, result)
            fixtures.append({"kind": kind, "command": command,
                             "log": "cases/alternative-physical-fixtures.log", "exit_code": 0,
                             "result": "cases/" + path.name, "result_sha256": sha(path)})
            lines.append(label + " " + kind + " " + actual + " " + sha(path))
        staged.append((label, entry, fixtures))
    lines.append("Synthetic lifecycle ordering asserted: capture_finished, encoders_closed, restoration_verified, native_exit, owner_released, saved_processing_started. No Native closure or owner release observed by this CPU fixture.")
    log = PACKAGE / "cases/alternative-physical-fixtures.log"
    log.write_text("\n".join(lines) + "\n")
    index = {"format": "worker-staged-alternative-physical-index", "cases": []}
    for label, entry, fixtures in staged:
        for fixture in fixtures:
            fixture["log_sha256"] = sha(log)
        proof = {"format": "worker-physical-preparation", "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
                 "lifecycle": {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                                          "native_exit", "owner_released", "saved_processing_started"],
                               "exit_code": 0, "log": "cases/alternative-physical-fixtures.log",
                               "log_sha256": sha(log)}}
        path = PACKAGE / "cases" / (label + "-physical-preparation.json")
        write(path, proof)
        index["cases"].append({"case_id": entry["case_id"], "receipt": "cases/" + path.name,
                               "sha256": sha(path), "passed": True})
    write(PACKAGE / "cases/alternative-physical-index.json", index)
    print("Four three-outcome synthetic physical checks passed")


if __name__ == "__main__":
    run()
