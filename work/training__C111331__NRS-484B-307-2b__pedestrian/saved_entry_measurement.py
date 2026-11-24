"""Measure the 307(2)(b) entry condition from retained raw signal/pose packets.

This is a CPU diagnostic finalizer. It does not assert Native provenance or
physical visibility. It deliberately takes raw per-frame observations instead
of an authored legal outcome or derived-channel verdict.
"""

import argparse
import json
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def measure(source):
    if source.get("format") != "pedestrian-entry-raw-v1":
        raise ValueError("raw source format missing")
    if source.get("hz") != 20 or source.get("frame_count") != 600:
        raise ValueError("30-second 20 Hz frame contract missing")
    if set(source.get("camera_ids", [])) != set(CAMERAS):
        raise ValueError("four source camera identities missing")
    frames = source.get("frames")
    if not isinstance(frames, list) or len(frames) != 600:
        raise ValueError("complete raw frame sequence missing")
    crosswalk = source.get("crosswalk")
    if not isinstance(crosswalk, dict) or crosswalk.get("id") is None:
        raise ValueError("crosswalk geometry missing")
    bounds = crosswalk.get("bounds_xy")
    if not isinstance(bounds, list) or len(bounds) != 4 or not all(isinstance(v, (int, float)) for v in bounds):
        raise ValueError("crosswalk bounds missing")
    xmin, ymin, xmax, ymax = bounds
    if not xmin < xmax or not ymin < ymax:
        raise ValueError("crosswalk bounds invalid")
    governing = source.get("governing_devices")
    if not isinstance(governing, dict) or not governing.get("traffic_head") or not governing.get("pedestrian_head"):
        raise ValueError("governing device IDs missing")
    inside = []
    for i, frame in enumerate(frames):
        if frame.get("frame") != i or abs(frame.get("time_s", -1) - i / 20) > 1e-6:
            raise ValueError("raw frame identity or time join invalid")
        if frame.get("pedestrian_id") != source.get("pedestrian_id"):
            raise ValueError("pedestrian identity changed")
        pose = frame.get("pedestrian_xy")
        if not isinstance(pose, list) or len(pose) != 2 or not all(isinstance(v, (int, float)) for v in pose):
            raise ValueError("pedestrian raw pose missing")
        traffic = frame.get("traffic_signal")
        pedal = frame.get("pedestrian_signal")
        if not isinstance(traffic, dict) or traffic.get("id") != governing["traffic_head"] or traffic.get("state") not in ("circular_green", "circular_yellow", "circular_red"):
            raise ValueError("governing traffic signal sample missing")
        if not isinstance(pedal, dict) or pedal.get("id") != governing["pedestrian_head"] or pedal.get("state") not in ("walk", "dont_walk", "dark"):
            raise ValueError("governing pedestrian signal sample missing")
        inside.append(xmin <= pose[0] <= xmax and ymin <= pose[1] <= ymax)
    entries = [i for i in range(1, 600) if inside[i] and not inside[i - 1]]
    if len(entries) != 1:
        raise ValueError("one observed crosswalk entry required")
    entry = entries[0]
    end = next((i for i in range(entry + 1, 600) if not inside[i]), None)
    if end is None or end - entry < 2:
        raise ValueError("observed crossing interval missing")
    at_entry = frames[entry]
    green = at_entry["traffic_signal"]["state"] == "circular_green"
    contrary = at_entry["pedestrian_signal"]["state"] == "dont_walk"
    return {
        "format": "pedestrian-entry-measurement-v1",
        "pedestrian_id": source["pedestrian_id"],
        "crosswalk_id": crosswalk["id"],
        "entry_frame": entry,
        "entry_time_s": entry / 20,
        "exit_frame": end,
        "circular_green_at_entry": green,
        "pedestrian_signal_at_entry": at_entry["pedestrian_signal"]["state"],
        "contrary_pedestrian_signal_at_entry": contrary,
        "permission_branch_307_2b_observed": green and not contrary,
        "deferred_to_484b_283_observed": green and contrary,
        "legal_verdict": None,
        "native_provenance": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    result = measure(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
