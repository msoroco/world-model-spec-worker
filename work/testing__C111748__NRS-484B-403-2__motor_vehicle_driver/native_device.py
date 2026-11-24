"""Original-frame measurement of official U-turn device and observed action."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise SourceError(reason)


def analyze(path: Path, *, case_id: str, sha256: str) -> dict:
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == sha256, "Native source hash mismatch")
    packet = json.loads(raw)
    require(packet.get("case_id") == case_id, "case mismatch")
    require(packet.get("actor") == "motor_vehicle_driver", "actor mismatch")
    require(packet.get("map_sha256") and packet.get("route_sha256"), "map/route source missing")
    require(packet.get("highway_status", {}).get("source_sha256"), "highway source missing")
    device = packet.get("device", {})
    for key in ("authority_source_sha256", "legal_consistency_source_sha256", "display_source_sha256", "governed_approach", "device_id"):
        require(device.get(key), f"device {key} missing")
    require(isinstance(device.get("prohibits_u_turn"), bool), "device meaning missing")
    frames = packet.get("frames", [])
    require(len(frames) >= 3, "original frame history missing")
    prev_t = -math.inf
    first = frames[0].get("frame")
    require(isinstance(first, int), "first frame missing")
    visible_frames = []
    governed_frames = []
    governed_visible_frames = []
    turn_frames = []
    for i, frame in enumerate(frames):
        require(frame.get("frame") == first + i, "noncontiguous original frames")
        t = frame.get("time_s")
        require(isinstance(t, (float, int)) and math.isfinite(t) and t > prev_t, "invalid original time")
        prev_t = t
        ego = frame.get("ego", {})
        require(ego.get("id") == packet.get("ego_id"), "ego identity mismatch")
        require(ego.get("road_id") is not None and ego.get("lane_id") is not None, "ego lane missing")
        require(all(isinstance(ego.get(k), (int, float)) and math.isfinite(ego[k]) for k in ("x", "y", "yaw_deg")), "ego pose missing")
        observed = frame.get("device_readback", {})
        require(observed.get("device_id") == device["device_id"], "device identity mismatch")
        require(isinstance(observed.get("prohibits_u_turn"), bool), "live display readback missing")
        require(observed["prohibits_u_turn"] == device["prohibits_u_turn"], "live display differs from reviewed setup")
        if observed.get("visible_to_ego") is True:
            visible_frames.append(frame["frame"])
        if ego.get("approach_id") == device["governed_approach"]:
            governed_frames.append(frame["frame"])
            if observed.get("visible_to_ego") is True:
                governed_visible_frames.append(frame["frame"])
        if ego.get("u_turn_in_progress") is True:
            turn_frames.append(frame["frame"])
    require(governed_frames, "no governed approach frames")
    require(visible_frames, "no observed device visibility")
    require(governed_visible_frames, "no device visibility on governed approach")
    if turn_frames:
        require(min(governed_visible_frames) < min(turn_frames), "governed device observation not before turn")
        start, end = frames[0]["ego"], frames[-1]["ego"]
        require(start["road_id"] == end["road_id"], "U-turn road continuity missing")
        require(start["lane_id"] != end["lane_id"], "opposite destination lane missing")
        heading_change = abs((end["yaw_deg"] - start["yaw_deg"] + 180.0) % 360.0 - 180.0)
        require(heading_change >= 135.0, "full observed reversal missing")
    return {"case_id": case_id, "source_sha256": sha256, "frame_count": len(frames),
            "device_id": device["device_id"], "display_source_sha256": device["display_source_sha256"],
            "prohibits_u_turn": device["prohibits_u_turn"], "first_visible_frame": min(governed_visible_frames),
            "first_governed_frame": min(governed_frames), "first_turn_frame": min(turn_frames) if turn_frames else None,
            "turn_observed": bool(turn_frames), "device_apparent_before_turn": bool(turn_frames and min(governed_visible_frames) < min(turn_frames)),
            "legal_device_status": "requires_independent_source_review"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = analyze(args.native, case_id=args.case, sha256=args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
