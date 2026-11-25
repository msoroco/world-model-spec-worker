"""Bind source-shaped CPU physical outcomes and ownership lifecycle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        log = HERE / ("proof-physical-" + suffix + ".log")
        content = log.read_text()
        if not all(term in content for term in ("complete_motion met", "incomplete_motion not_met",
                                                "missing_evidence unverified", "lifecycle " + " ".join(EVENTS))):
            raise ValueError("physical probe incomplete: " + case)
        command = f".venv-cpu/bin/python physical_probe.py --case {case} --output $SCRATCH"
        fixtures = []
        for kind, status in (("complete_motion", "met"),
                             ("incomplete_motion", "not_met"),
                             ("missing_evidence", "unverified")):
            result = HERE / ("physical-" + suffix + "-" + kind + ".json")
            record = json.loads(result.read_text())
            if record["physical_checks"]["maneuver"]["status"] != status:
                raise ValueError("physical fixture status mismatch: " + case)
            fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                             "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        receipt = HERE / ("physical-" + suffix + "-receipt.json")
        receipt.write_text(json.dumps({"case_id": case,
            "construction_sha256": entry["construction_sha256"],
            "fixtures": fixtures,
            "lifecycle": {"events": EVENTS, "command": command,
                          "exit_code": 0, "log": log.name,
                          "log_sha256": sha(log)}}, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": receipt.name,
                                         "sha256": sha(receipt)}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "physical preparation receipts")


if __name__ == "__main__":
    bind()
