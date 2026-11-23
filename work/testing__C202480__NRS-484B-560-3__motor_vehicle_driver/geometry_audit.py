"""Independent saved geometry audit of the original crossing actor trace.

This checks measurement consistency. It does not decode video, judge the law,
or claim physical completion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_scene import inspect
from owner_release import verify_release


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("original actor geometry invalid")
    return float(value)


def _actor(row: dict, name: str):
    item = row.get(name)
    if not isinstance(item, dict):
        raise ValueError("original actor missing: " + name)
    pos, vel, ext = (item.get("position_m"), item.get("velocity_mps"),
                     item.get("bbox_half_extent_m"))
    if any(not isinstance(v, list) or len(v) != 3 for v in (pos, vel, ext)):
        raise ValueError("original actor geometry invalid")
    x, y = _number(pos[0]), _number(pos[1])
    speed = math.sqrt(sum(_number(v) ** 2 for v in vel))
    length, width = _number(ext[0]), _number(ext[1])
    if min(length, width) <= 0:
        raise ValueError("original actor footprint invalid")
    return x, y, speed, length, width


def audit(attempt: Path) -> dict:
    attempt = Path(attempt).resolve()
    verify_release(attempt)
    root = Path(__file__).resolve().parents[2] / ".runtime-work"
    if root not in attempt.parents:
        raise ValueError("geometry audit requires original private attempt")
    status = json.loads((attempt / "native-run-status.json").read_text())
    case_id = status["case_id"]
    packet_path = attempt / "site/packet.json"
    packet, case, _ = inspect(packet_path, Path(__file__).with_name("case-plan.json"),
                              case_id)
    trace_path = attempt / "trace.jsonl"
    receipt = json.loads((attempt / "media-receipt.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    if (status.get("errors") != [] or status.get("capture", {}).get("frames") != 900 or
            status.get("restoration", {}).get("restored") is not True or
            status.get("site_packet_sha256") != sha(packet_path) or
            receipt.get("source_packet_sha256") != sha(packet_path) or
            receipt.get("trace_sha256") != sha(trace_path) or
            result.get("case_id") != case_id or
            result.get("physical_acceptance_claimed") is not False or
            result.get("legal_judgment") != "unresolved"):
        raise ValueError("saved geometry/source identity differs")
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    if len(rows) != 900:
        raise ValueError("original geometry frame count differs")
    direction = packet["approach_direction"]
    right_y = packet["slots"][packet["rightmost_feasible_slot"]]["y_m"]
    stopped_offsets = []
    aligned = 0
    first = None
    for row in rows:
        if row.get("case_id") != case_id or row.get("source_packet_sha256") != sha(packet_path):
            raise ValueError("original geometry row identity differs")
        x, y, speed, length, width = _actor(row, "ego")
        before_rail = direction * (packet["rail_line_x_m"] - x) > 0
        if speed <= .1 and before_rail:
            stopped_offsets.append(direction * (y - right_y))
        if case["traffic_arrangement"] == "two_queues":
            cx, cy, cspeed, clength, cwidth = _actor(row, "companion")
            if (speed <= .1 and cspeed <= .1 and before_rail and
                    direction * (packet["rail_line_x_m"] - cx) > 0 and
                    abs(y - cy) > width + cwidth + .1 and
                    abs(x - cx) <= length + clength):
                aligned += 1
                if first is None:
                    first = {"frame": row["frame"],
                             "lateral_center_separation_m": abs(y - cy),
                             "longitudinal_center_separation_m": abs(x - cx)}
        elif row.get("companion") is not None:
            raise ValueError("unexpected companion in one-queue geometry")
    expected = result.get("realized_observables", {})
    actual_offset = min(stopped_offsets) if stopped_offsets else None
    if (expected.get("two_queue_aligned_frame_count") != aligned or
            expected.get("first_two_queue_alignment") != first or
            expected.get("minimum_stopped_lateral_offset_from_reviewed_rightmost_m") != actual_offset):
        raise ValueError("saved geometry measurement differs from original trace")
    return {"format": "c202480-independent-geometry-audit-v1",
            "case_id": case_id, "source_packet_sha256": sha(packet_path),
            "trace_sha256": sha(trace_path),
            "two_queue_aligned_frame_count": aligned,
            "minimum_stopped_lateral_offset_from_reviewed_rightmost_m": actual_offset,
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), indent=2))
