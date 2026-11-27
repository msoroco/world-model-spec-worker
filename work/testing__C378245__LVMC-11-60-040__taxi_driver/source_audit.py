"""Independent saved taxi stand source audit for local delivery review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis import source
from taxi_stand_measurement import measure


def audit(attempt: Path, case_id: str, output: Path) -> dict:
    attempt = attempt.resolve()
    packet = json.loads(source(attempt, "taxi-source-packet.json").read_text())
    if packet.get("case_id") != case_id or packet.get("diagnostic_fixture") is True:
        raise ValueError("exact original taxi source packet required")
    observation = measure(packet, attempt)
    if observation.get("case_id") != case_id or observation.get("diagnostic_fixture") is True:
        raise ValueError("original taxi observation differs")
    result = {
        "format": "worker-taxi-local-source-audit",
        "case_id": case_id,
        "recording_id": observation["recording_id"],
        "source_sha256": observation["source_sha256"],
        "camera_sha256": observation["camera_sha256"],
        "halt_interval_frames": observation["halt_interval_frames"],
        "reviewed_activity": observation["reviewed_activity"],
        "physical_acceptance_claimed": False,
        "legal_verdict": None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.attempt, args.case_id, args.output)
