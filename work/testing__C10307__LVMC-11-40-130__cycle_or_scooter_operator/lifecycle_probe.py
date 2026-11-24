"""CPU state-machine proof that saved processing waits for Native closure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ORDER = ["capture_finished", "encoders_closed", "restoration_verified",
         "native_exit", "owner_released", "saved_processing_started"]


def verify(events: list[str]) -> dict:
    if events != ORDER:
        raise ValueError("saved processing precedes Native ownership closure")
    return {"events": events, "native_ownership_closed_before_saved": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.events.read_text())
    print(json.dumps(verify(data["events"]), sort_keys=True))


if __name__ == "__main__":
    main()
