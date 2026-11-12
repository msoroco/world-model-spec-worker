"""Original-footprint measurements for the C229126 pass and return sequence.

Geometry is reported for later review; no engineering value defines statutory
"safe distance" or "safely clear".
"""

import hashlib
import json
from math import hypot, isfinite
from pathlib import Path


def _pair(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Missing original " + name)
    pair = tuple(float(v) for v in value)
    if not all(isfinite(v) for v in pair):
        raise ValueError("Nonfinite original " + name)
    return pair


def _footprint(row, key):
    value = row.get(key)
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("Missing four-corner original " + key)
    return [_pair(corner, key) for corner in value]


def _extent(corners, axis):
    values = [x * axis[0] + y * axis[1] for x, y in corners]
    return min(values), max(values)


def measure(source):
    raw = Path(source).read_bytes()
    if not raw:
        raise ValueError("Empty original participant footprints")
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) < 4:
        raise ValueError("Approach, pass, clear and return frames required")
    ids = (rows[0].get("ego_id"), rows[0].get("other_id"))
    if not all(ids) or ids[0] == ids[1]:
        raise ValueError("Two stable participant identities required")
    samples = []
    right_lane = rows[0].get("other_lane_id")
    if type(right_lane) is not int or rows[0].get("ego_lane_id") != right_lane:
        raise ValueError("Original same-lane approach required")
    for index, row in enumerate(rows):
        if (row.get("ego_id"), row.get("other_id")) != ids:
            raise ValueError("Original participant identity changed")
        frame, time_s = row.get("frame"), row.get("time_s")
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError("Original frame and time required")
        if index and (frame != rows[index - 1]["frame"] + 1 or
                      abs(time_s - rows[index - 1]["time_s"] - .05) > 1e-4):
            raise ValueError("Original 20 Hz frame join failed")
        tx, ty = _pair(row.get("road_tangent_xy"), "road tangent")
        length = hypot(tx, ty)
        if length < 1e-6:
            raise ValueError("Degenerate road tangent")
        axis = (tx / length, ty / length)
        left = (-axis[1], axis[0])
        for actor in ("ego", "other"):
            hx, hy = _pair(row.get(actor + "_heading_xy"), actor + " heading")
            hlen = hypot(hx, hy)
            if hlen < 1e-6 or (hx * axis[0] + hy * axis[1]) / hlen < .95:
                raise ValueError("Participants not proceeding in same direction")
        ego = _footprint(row, "ego_corners")
        other = _footprint(row, "other_corners")
        if type(row.get("ego_lane_id")) is not int or row.get("other_lane_id") != right_lane:
            raise ValueError("Original right-lane membership required")
        el, ol = _extent(ego, axis), _extent(other, axis)
        ey, oy = _extent(ego, left), _extent(other, left)
        overlap = el[0] <= ol[1] and ol[0] <= el[1]
        samples.append({"frame": frame, "time_s": time_s,
                        "ego_lane_id": row["ego_lane_id"], "other_lane_id": right_lane,
                        "abreast": overlap, "left_gap_m": ey[0] - oy[1],
                        "ego_left_of_other": sum(ey) > sum(oy),
                        "longitudinal_clearance_m": el[0] - ol[1],
                        "ego_lateral_center_m": sum(ey) / 2,
                        "other_lateral_center_m": sum(oy) / 2,
                        "other_speed_mps": float(row.get("other_speed_mps", 0))})
        if not isfinite(samples[-1]["other_speed_mps"]) or samples[-1]["other_speed_mps"] <= 0:
            raise ValueError("Original overtaken-vehicle speed required")
    if samples[0]["longitudinal_clearance_m"] >= 0:
        raise ValueError("Approach must begin behind overtaken vehicle")
    abreast = [sample for sample in samples if sample["abreast"]]
    if not abreast:
        raise ValueError("Missing abreast phase")
    first_abreast = next(i for i, sample in enumerate(samples) if sample["abreast"])
    returns = [samples[i] for i in range(first_abreast + 1, len(samples))
               if samples[i]["ego_lateral_center_m"] < samples[i - 1]["ego_lateral_center_m"] - .1]
    if not returns:
        raise ValueError("Missing observed rightward return")
    first_return = returns[0]
    if not any(sample["ego_lane_id"] == right_lane for sample in samples
               if sample["frame"] > first_return["frame"]):
        raise ValueError("Trace ends before observed return to right lane")
    if not any(sample["longitudinal_clearance_m"] > 0 for sample in samples):
        raise ValueError("Trace lacks complete-body clearance")
    return {"format": "worker-overtake-sequence-observation",
            "source_sha256": hashlib.sha256(raw).hexdigest(), "actor_ids": list(ids),
            "frame_count": len(samples), "abreast_frames": [s["frame"] for s in abreast],
            "all_abreast_left": all(s["ego_left_of_other"] for s in abreast),
            "minimum_abreast_left_gap_m": min(s["left_gap_m"] for s in abreast),
            "first_return_frame": first_return["frame"],
            "body_clearance_at_first_return_m": first_return["longitudinal_clearance_m"],
            "time_gap_at_first_return_s": first_return["longitudinal_clearance_m"] / first_return["other_speed_mps"],
            "samples": samples, "legal_acceptance_claimed": False}
