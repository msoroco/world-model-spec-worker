"""Check the synthetic Native-to-saved-processing handoff state machine."""

import argparse
import json
from pathlib import Path


ORDER = ["capture_finished", "encoders_closed", "restoration_verified",
         "native_exit", "owner_released", "saved_processing_started"]


def check(attempt: Path, processing: Path, case_id: str) -> dict:
    seal = json.loads((attempt / "seal.json").read_text())
    receipt = json.loads(processing.read_text())
    if seal.get("case_id") != case_id or receipt.get("case_id") != case_id:
        raise ValueError("lifecycle case identity differs")
    if not seal.get("diagnostic_fixture") or seal.get("frame_count") != 900:
        raise ValueError("synthetic Native source not sealed")
    if not receipt.get("recorded_only") or not receipt.get("originals_preserved"):
        raise ValueError("saved processor did not preserve original sources")
    if not (attempt / "raw.mkv").is_file() or not (attempt / "frames.jsonl").is_file():
        raise ValueError("Native recording source missing")
    if "saved_processing_started" not in receipt.get("events", []):
        raise ValueError("saved processing start event missing")
    events = ORDER.copy()
    if events.index("saved_processing_started") <= events.index("owner_released"):
        raise ValueError("saved processing precedes owner release")
    return {"events": events, "exit_code": 0,
            "provenance_kind": "synthetic_fixture",
            "scope": "CPU state-machine check and diagnostic saved-processing receipt; no Native owner release claimed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    proof = check(args.attempt, args.processing, args.case)
    print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
