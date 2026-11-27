"""Check Native ownership closes before saved-only processing starts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ORDER = ("capture_finished", "encoders_closed", "restoration_verified",
         "native_exit", "owner_released", "saved_processing_started")


def validate(events):
    if not isinstance(events, list) or events != list(ORDER):
        raise ValueError("Native capture/encoder/restoration/exit/owner-release lifecycle order differs")
    return {"events": events, "recorded_only_after_owner_release": True,
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.events.read_text())
    print(json.dumps(validate(value["events"]), sort_keys=True))


if __name__ == "__main__":
    main()
