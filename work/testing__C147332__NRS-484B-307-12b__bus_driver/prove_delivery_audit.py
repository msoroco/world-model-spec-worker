"""Run independent delivery-audit positive and tamper negatives on CPU fixtures."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from bus_route import ROUTES
from delivery_audit import CAMERAS, ORIGINALS, audit_attempt


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    runtime_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not runtime_root.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("pipeline outputs must stay under .runtime-work")
    output = REPO / ".runtime-work" / "c147332-delivery-audit-v1"
    if output.exists():
        raise ValueError("retain previous audit fixture; choose a fresh version")
    output.mkdir(parents=True)
    for kind in ROUTES:
        source = REPO / ".runtime-work" / "c147332-compat-v5" / kind / "primary"
        attempt = output / kind
        shutil.copytree(source, attempt)
        (attempt / "carla_recorder.log").write_text("diagnostic recorder log\n")
        acquisition = json.loads((attempt / "acquisition.json").read_text())
        for name in ORIGINALS:
            if not (attempt / name).is_file():
                raise ValueError("diagnostic original-shaped source missing: " + name)
            acquisition[name] = sha(attempt / name)
        write(attempt / "acquisition.json", acquisition)
        seal = {"format": "worker-sealed-capture", "provenance_kind": "diagnostic",
                "diagnostic_fixture": True, "frames": 5,
                "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                "restoration": {"restored": True},
                "encoder_exit_codes": {name: 0 for name in CAMERAS},
                "sources": {name: item.get("sha256") if isinstance(item, dict) else item
                            for name, item in acquisition.items()}}
        write(attempt / "capture-seal.json", seal)
        positive = audit_attempt(attempt, diagnostic=True)
        if positive["physical_acceptance_claimed"] or set(positive["decoded_frames"]) != set(CAMERAS):
            raise AssertionError("diagnostic delivery audit claimed physical acceptance")
        try:
            audit_attempt(attempt)
        except ValueError as error:
            if "original Native" not in str(error):
                raise
        else:
            raise AssertionError("diagnostic capture passed Native delivery audit")
        print(kind, "diagnostic four-camera audit passed; Native claim rejected")
        if kind == "red_lane_stand":
            trace = attempt / "trace.jsonl"
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            rows[-1]["speed_mps"] = 2.0
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            acquisition["trace.jsonl"] = sha(trace)
            seal["sources"]["trace.jsonl"] = sha(trace)
            write(attempt / "acquisition.json", acquisition)
            write(attempt / "capture-seal.json", seal)
            try:
                audit_attempt(attempt, diagnostic=True)
            except ValueError as error:
                if "stationary measured speed" not in str(error):
                    raise
            else:
                raise AssertionError("moving red-lane stand passed the independent audit")
            print("red_lane_stand moving-source negative rejected")


if __name__ == "__main__":
    main()
