"""Create explicitly synthetic 30-second Native-shaped diagnostic sources."""
import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = "training__C158142__NRS-484B-250-4__motor_vehicle_driver"


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def x_at(condition, i):
    if condition == "halt":
        if i <= 150:
            return -35.0 + 33.0 * i / 150
        if i <= 250:
            return -2.0
        if i <= 300:
            return -2.0 + 2.0 * (i - 250) / 50
    else:
        if i <= 300:
            return -35.0 + 35.0 * i / 300
    return 0.1 * (i - 300)


def make(root, condition):
    root.mkdir(parents=True, exist_ok=True)
    write(root / "geometry.json", {
        "source_kind": "synthetic_native_sample", "ego_incoming_lane": "westbound_1",
        "stop_line_present": False, "near_crosswalk_present": True,
        "crosswalk_near_edge_x_m": 0.0, "intersection_entry_x_m": 3.0,
        "source_note": "Fixture geometry only; survey Native geometry and visibility later.",
    })
    write(root / "signal.json", {
        "source_kind": "synthetic_native_sample", "installed": True,
        "uncovered": True, "inoperative_observed": True,
        "controlled_incoming_lane": "westbound_1",
        "source_note": "Fixture state only; Native signal and original pixels unconfirmed.",
    })
    rows = []
    for i in range(600):
        x = x_at(condition, i)
        speed = max(0.0, ((x_at(condition, i + 1) - x) if i == 0
                          else (x - x_at(condition, i - 1))) * 20)
        rows.append({"frame": i, "time_s": i / 20,
                     "ego_front_x_m": round(x, 6), "ego_speed_mps": round(speed, 6),
                     "other_speed_mps": 0.0 if 80 <= i <= 100 else 4.0,
                     "other_in_intersection": 120 <= i <= 240,
                     "source_kind": "synthetic_native_sample"})
    (root / "native-rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    names = ("geometry.json", "signal.json", "native-rows.jsonl")
    write(root / "source-index.json", {
        "format": "nrs-484b-250-4-diagnostic-source-index-v1",
        "assignment_id": ASSIGNMENT, "condition": condition,
        "rate_hz": 20, "frames": 600,
        "files": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                  for name in names},
        "claim": "synthetic diagnostic; no physical or legal outcome",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(args.output)
    for condition in ("halt", "roll"):
        make(root / condition, condition)
    print(json.dumps({"conditions": ["halt", "roll"], "frames_each": 600}))
