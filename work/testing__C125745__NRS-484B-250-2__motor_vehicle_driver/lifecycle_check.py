"""Require owner release before postprocessing of any recorded attempt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def check(events: list[str]) -> None:
    if events != EVENTS:
        raise ValueError("saved processing must follow Native exit and owner release")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    events = json.loads(args.events.read_text())
    check(events)
    for boundary in range(len(EVENTS) - 1):
        altered = events.copy()
        altered[boundary], altered[boundary + 1] = altered[boundary + 1], altered[boundary]
        try:
            check(altered)
        except ValueError:
            pass
        else:
            raise ValueError("lifecycle ordering negative control accepted")
    print("lifecycle positive and five adjacent-swap negatives passed")


if __name__ == "__main__":
    main()
