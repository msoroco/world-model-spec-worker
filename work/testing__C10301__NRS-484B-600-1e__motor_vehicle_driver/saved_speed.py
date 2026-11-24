"""Saved-only speed source join; no CARLA import or physical acceptance claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from speed_boundary import measure
from delivery_audit import audit_decoded_media


def process(attempt: Path, case_id: str, output: Path, *,
            allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt)
    receipt_path = attempt / "native-motion-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("format") != "c10301-native-motion-v1" or
            receipt.get("case_id") != case_id or
            receipt.get("sample_count") != 900 or
            type(receipt.get("travel_m")) not in (int, float) or
            not math.isfinite(receipt["travel_m"]) or
            receipt["travel_m"] < 100 or
            receipt.get("physical_acceptance_claimed") is not False or
            type(receipt.get("diagnostic_fixture")) is not bool):
        raise ValueError("Native motion source receipt incomplete")
    if receipt["diagnostic_fixture"] and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot enter delivery processing")
    observation = measure(attempt, case_id)
    if (observation["source_sha256"] != receipt.get("speed_source_sha256") or
            observation["native_run_id"] != receipt.get("native_run_id") or
            observation["diagnostic_fixture"] != receipt["diagnostic_fixture"]):
        raise ValueError("saved speed source and motion receipt differ")
    result = {"format": "c10301-saved-speed-v1", "case_id": case_id,
              "native_run_id": receipt["native_run_id"],
              "native_motion_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
              "measurement": observation, "physical_acceptance_claimed": False,
              "legal_judgment": "unresolved"}
    output = Path(output)
    if output.exists():
        raise ValueError("saved speed output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return result


def process_delivery(attempt: Path, case_id: str, output: Path, *,
                     allow_diagnostic: bool = False) -> dict:
    """Saved-only speed and fully decoded media, written after all checks pass."""
    output = Path(output)
    if output.exists():
        raise ValueError("saved delivery output already exists")
    media = audit_decoded_media(attempt, case_id,
                                allow_diagnostic=allow_diagnostic)
    speed = measure(attempt, case_id)
    if (media["native_run_id"] != speed["native_run_id"] or
            media["case_id"] != speed["case_id"]):
        raise ValueError("saved speed and media run identity differ")
    result = {"format": "c10301-saved-delivery-v1",
              "case_id": case_id, "native_run_id": speed["native_run_id"],
              "measurement": speed, "media_audit": media,
              "physical_acceptance_claimed": False,
              "legal_judgment": "unresolved"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(process_delivery(args.attempt, args.case_id, args.output,
                                      allow_diagnostic=args.allow_diagnostic), indent=2))
