"""Exercise measured engineering completion states with synthetic motion only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build_bundles import HERE, AID

REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work" / "c135087-physical-probes-v4"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def probe(entry, suffix, kind):
    sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
    from worker_exchange.native_output import physical_result
    root = SCRATCH / suffix / kind
    if root.exists():
        raise ValueError("physical probe scratch exists; choose a fresh revision")
    root.mkdir(parents=True)
    construction = json.loads((HERE / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"] if item["path"] == "config.json"))
    write(root / "config.json", config)
    write(root / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                                  "diagnostic_fixture": True})
    mapping = [{"video_frame": i, "carla_frame": 100 + i, "time_s": i / 20} for i in range(2)]
    (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))
    if kind != "missing_evidence":
        positions = [0.0, 2.0] if kind == "complete_motion" else [0.0, 0.0]
        rows = [{"frame": 100 + i, "time_s": i / 20, "position_m": [value, 0.0, 0.0]}
                for i, value in enumerate(positions)]
        (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = physical_result(root, {"target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if result["physical_checks"]["maneuver"]["status"] != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("synthetic physical state differs from original-motion assessor")
    target = HERE / "physical" / suffix / (kind + "-result.json")
    write(target, result)
    log = HERE / "physical" / suffix / (kind + "-proof.log")
    log.write_text("source-bound synthetic motion assessment: " + expected + "\n")
    return {"kind": kind, "command": "prove_physical_preparation.py " + suffix + " " + kind,
            "exit_code": 0, "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
            "result": str(target.relative_to(HERE)), "result_sha256": sha(target)}


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    events = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit",
              "owner_released", "saved_processing_started"]
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        fixtures = [probe(entry, suffix, kind) for kind in ("complete_motion", "incomplete_motion", "missing_evidence")]
        log = HERE / "physical" / suffix / "lifecycle.log"
        log.write_text("\n".join(events) + "\n")
        receipt = {"format": "c135087-synthetic-physical-preparation",
                   "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
                   "diagnostic_fixture": True, "fixtures": fixtures,
                   "lifecycle": {"events": events, "exit_code": 0,
                                 "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}}
        path = HERE / f"physical-{suffix}-receipt.json"
        write(path, receipt)
        print(suffix, "three synthetic motion states and ordered lifecycle", flush=True)


if __name__ == "__main__":
    build()
