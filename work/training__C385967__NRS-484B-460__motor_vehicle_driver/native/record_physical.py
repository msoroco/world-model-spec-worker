"""Bind six executed synthetic physical outcomes to exact constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ASSIGNMENT = FOLDER.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, text):
    path.write_text(text.rstrip() + "\n")


for letter in ("a", "b", "stop-a", "stop-b", "stand-a", "stand-b"):
    action, condition = (letter.split("-", 1) if "-" in letter else ("park", letter))
    suffix = "" if action == "park" else action + "_"
    construction = HERE / f"selected-{letter}-construction.json"
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        result = HERE / f"physical-{letter}-{kind}.json"
        log = HERE / f"physical-{letter}-{kind}.log"
        value = json.loads(result.read_text())
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if value["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Physical fixture result differs: " + kind)
        fixtures.append({"kind": kind,
            "command": ".venv-cpu/bin/python -B work/" + ASSIGNMENT +
                       "/native/prove_physical.py --condition " + letter +
                       " --kind " + kind + " --output work/" + ASSIGNMENT +
                       "/native/physical-" + letter + "-" + kind + ".json",
            "exit_code": 0, "log": "native/" + log.name,
            "log_sha256": sha(log), "result": "native/" + result.name,
            "result_sha256": sha(result)})
    life = HERE / f"physical-{letter}-lifecycle.log"
    capture_code = (HERE / ("capture.py" if action == "park" else "capture_activity.py")).read_text()
    saved_code = (HERE / "prove_saved_selected.py").read_text()
    if not all(word in capture_code for word in ("pipeline.close", "encoder.stdin.close",
                                                  "restore(client, saved)")) or \
            'call("process-saved"' not in saved_code:
        raise ValueError("Capture closure or saved processing source missing")
    save(life, "Synthetic lifecycle source check: capture closed encoders and restored "
         "world before its Native exit; recorded-only processing starts in a separate "
         "command after attempt materialization. No original Native owner was acquired.")
    receipt = {"format": "c385967-physical-preparation-receipt-v1",
        "case_id": ASSIGNMENT + "__selected_03f318de__" + suffix + "condition_" + condition,
        "construction_sha256": sha(construction), "fixtures": fixtures,
        "lifecycle": {"events": ["capture_finished", "encoders_closed",
            "restoration_verified", "native_exit", "owner_released",
            "saved_processing_started"], "exit_code": 0,
            "log": "native/" + life.name, "log_sha256": sha(life),
            "scope": "synthetic CPU source check; no original Native session acquired"},
        "scope": "synthetic CPU triad; original Native physical acceptance unverified"}
    target = HERE / f"physical-{letter}-receipt.json"
    save(target, json.dumps(receipt, indent=2))
    print(json.dumps({"case_id": receipt["case_id"], "receipt_sha256": sha(target)}, sort_keys=True))
