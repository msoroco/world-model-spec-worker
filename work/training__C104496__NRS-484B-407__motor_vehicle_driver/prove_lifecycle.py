"""Synthetic CPU protocol check; it does not attest a Native capture or owner release."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVENTS = [
    "capture_finished",
    "encoders_closed",
    "restoration_verified",
    "native_exit",
    "owner_released",
    "saved_processing_started",
]


def advance(state, event):
    if state >= len(EVENTS) or event != EVENTS[state]:
        raise ValueError("out-of-order synthetic lifecycle event")
    return state + 1


def main():
    for number in range(1, 4):
        probe = f"probe_{number:02d}"
        receipt = ROOT / "saved-processing" / probe / "processing.json"
        value = json.loads(receipt.read_text())
        if value.get("passed") is not True or value.get("recorded_only") is not True:
            raise ValueError("saved processing receipt did not pass")
        if value.get("events", [None])[0] != EVENTS[-1]:
            raise ValueError("saved processing did not begin")
        state = 0
        for event in EVENTS:
            state = advance(state, event)
        if state != len(EVENTS):
            raise ValueError("synthetic sequence incomplete")
        try:
            advance(2, "owner_released")
        except ValueError:
            pass
        else:
            raise ValueError("out-of-order negative check did not reject")
        target = ROOT / "physical" / probe / "lifecycle.log"
        target.write_text(json.dumps({
            "scope": "synthetic CPU lifecycle ordering only",
            "native_capture_or_owner_release_attested": False,
            "events": EVENTS,
            "out_of_order_rejected": True,
            "recorded_only_processing_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
        }, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
