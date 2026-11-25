"""Independent fixed-scene comparison of exact opposite parked-side cases."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize import analyze


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(attempt_a, attempt_b, processing_a, processing_b, diagnostic=False):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    pa, pb = (json.loads(Path(path).read_text()) for path in (processing_a, processing_b))
    prefix = "training__C135709__NRS-484B-493__motor_vehicle_driver__"
    if pa.get("case_id") != prefix + "controlled_1" or pb.get("case_id") != prefix + "controlled_2":
        raise ValueError("Exact comparison cases differ")
    if not all(p.get("passed") is True and p.get("recorded_only") is True for p in (pa, pb)):
        raise ValueError("Recorded-only processing proof missing")
    for source in ("road.xodr", "road-context.json"):
        if sha(a / source) != sha(b / source):
            raise ValueError("Fixed street context differs: " + source)
    for role in ("one-way-designation", "street-boundary", "device-authority",
                 "device-content", "device-erection"):
        for suffix in (".json", ".source.txt"):
            name = "authority-review/" + role + suffix
            if sha(a / name) != sha(b / name):
                raise ValueError("Fixed reviewed source differs: " + name)
    configs = [json.loads((path / "config.json").read_text()) for path in (a, b)]
    for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s",
                  "cameras", "source_actor_ids", "required_atoms"):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError("Fixed comparison configuration differs: " + field)
    if [c["parking_side"] for c in configs] != ["right", "left"]:
        raise ValueError("Declared parked-side contrast differs")
    measured = [analyze(path) for path in (a, b)]
    right = len(measured[0]["measurement"]["fully_right_governed_frames"])
    left = len(measured[1]["measurement"]["fully_left_governed_frames"])
    if right < 1 or left < 1:
        raise ValueError("Measured opposite stationary sides absent")
    if diagnostic and any(json.loads((path / "acquisition-provenance.json").read_text()).get(
            "provenance_kind") != "synthetic_fixture" for path in (a, b)):
        raise ValueError("Diagnostic comparison requires CPU fixtures")
    return {"format": "c135709-comparison-audit-v1",
            "case_ids": [m["case_id"] for m in measured],
            "diagnostic_fixture": diagnostic,
            "fixed_map_sha256": sha(a / "road.xodr"),
            "deliberate_difference": "requested_and_measured_parked_side",
            "measured_right_frames": right, "measured_left_frames": left,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("attempt-a", "attempt-b", "processing-a", "processing-b", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    value = compare(args.attempt_a, args.attempt_b, args.processing_a,
                    args.processing_b, args.diagnostic)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))
