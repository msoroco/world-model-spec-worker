"""Source-only diagnostic for the NRS 484B.250(4) crosswalk branch.

This consumes retained rows, not labels or fixture-provided derived channels.
It measures a complete halt, boundary order, and conflicting-vehicle yield;
physical signal failure and legal compliance require independent Native review.
"""
import argparse
import hashlib
import json
from pathlib import Path

RATE = 20
FRAMES = 600


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(source):
    source = Path(source)
    index = json.loads((source / "source-index.json").read_text())
    for name, expected in index["files"].items():
        path = source / name
        require(path.is_file() and digest(path) == expected, "source hash mismatch: " + name)
    geometry = json.loads((source / "geometry.json").read_text())
    signal = json.loads((source / "signal.json").read_text())
    rows = [json.loads(line) for line in (source / "native-rows.jsonl").read_text().splitlines()]
    return index, geometry, signal, rows


def measure(source):
    index, geometry, signal, rows = load(source)
    require(len(rows) == FRAMES and index["rate_hz"] == RATE, "600-frame 20 Hz source required")
    require(geometry["stop_line_present"] is False, "selected branch requires no stop line")
    require(geometry["near_crosswalk_present"] is True, "near-side crosswalk missing")
    boundary = geometry["crosswalk_near_edge_x_m"]
    require(signal["installed"] is True and signal["uncovered"] is True,
            "installed uncovered signal source missing")
    require(signal["controlled_incoming_lane"] == geometry["ego_incoming_lane"],
            "signal does not govern ego lane")
    require(signal["inoperative_observed"] is True, "inoperative signal observation missing")
    for i, row in enumerate(rows):
        require(row["frame"] == i and abs(row["time_s"] - i / RATE) < 1e-8,
                "frame/time join failed")
        require(row["ego_speed_mps"] >= 0 and row["other_speed_mps"] >= 0,
                "invalid speed source")
    entry = next((r["frame"] for r in rows if r["ego_front_x_m"] >= boundary), None)
    require(entry is not None, "ego never reached crosswalk")
    halted = [r["frame"] for r in rows[:entry]
              if r["ego_speed_mps"] <= 0.05 and r["ego_front_x_m"] < boundary]
    other_stops = [r["frame"] for r in rows[:entry]
                   if r["other_speed_mps"] <= 0.05 and not r["other_in_intersection"]]
    require(other_stops, "other vehicle stop history missing")
    other_first_stop = other_stops[0]
    other_last_inside = max((r["frame"] for r in rows if r["other_in_intersection"]), default=-1)
    require(other_last_inside >= other_first_stop, "other vehicle intersection history missing")
    result = {
        "format": "nrs-484b-250-4-source-measurement-v1",
        "assignment_id": index["assignment_id"],
        "condition": index["condition"],
        "source_index_sha256": digest(Path(source) / "source-index.json"),
        "source_hashes": index["files"],
        "frames": len(rows), "rate_hz": RATE,
        "stop_line_present": False, "near_crosswalk_present": True,
        "installed_uncovered_inoperative_source": True,
        "crosswalk_entry_frame": entry,
        "halt_before_crosswalk": bool(halted),
        "first_halt_frame": halted[0] if halted else None,
        "other_first_stop_frame": other_first_stop,
        "other_last_inside_frame": other_last_inside,
        "yielded_until_other_clear": entry > other_last_inside,
        "physical_signal_failure_confirmed": False,
        "legal_outcome_asserted": False,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    result = measure(args.source)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"condition": result["condition"], "frames": result["frames"],
                      "halt": result["halt_before_crosswalk"],
                      "yield": result["yielded_until_other_clear"]}))


if __name__ == "__main__":
    main()
