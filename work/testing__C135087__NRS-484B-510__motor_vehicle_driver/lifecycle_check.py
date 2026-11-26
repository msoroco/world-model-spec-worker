"""Check that saved processing begins after Native ownership release."""

import argparse
import json
from pathlib import Path


EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def check(events):
    if events != EVENTS:
        raise ValueError("saved processing precedes Native ownership closure")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    check(json.loads(args.events.read_text()))
    print("Native exit and owner release precede saved processing")


if __name__ == "__main__":
    main()
