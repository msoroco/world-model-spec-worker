"""Original-frame stop-before-entry and occupied-intersection observations.

The source context must establish a non-through-highway signed entrance and
every competing entrance's device. No legal hazard or caution verdict is made.
"""

import hashlib
import json
import math
from pathlib import Path


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path):
    root = Path(root)
    names = ("intersection_context.json", "entry_history.jsonl", "video_frames.jsonl")
    hashes = {}
    for name in names:
        path = root/name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root/"intersection_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "ego_approach_road_id",
                "native_stop_sign_id", "sign_governance_source", "entrance_inventory_source",
                "stop_reference_source", "highway_status_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced intersection context: " + key)
    if context.get("non_through_highway") is not True:
        raise ValueError("Non-through-highway status not sourced")
    if context.get("police_control") is not False or context.get("traffic_signal_control") is not False:
        raise ValueError("Officer/signal exception unresolved")
    if context.get("ego_entrance_device") != "stop":
        raise ValueError("Ego stop-sign governance missing")
    entrances = context.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2 or any("road_id" not in e or "device" not in e for e in entrances):
        raise ValueError("Incomplete entrance device inventory")
    rows, frames = _rows(root/"entry_history.jsonl"), _rows(root/"video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete entry history")
    samples, previous = [], (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = fid, time
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        if row.get("ego_road_id") != context["ego_approach_road_id"]:
            raise ValueError("Ego approach identity mismatch")
        if row.get("ego_speed_source") != "actor.get_velocity":
            raise ValueError("Ego Native velocity source missing")
        speed = _finite(row.get("ego_speed_mps"), "ego speed")
        if speed < 0:
            raise ValueError("Negative ego speed")
        entry, before_ref = row.get("ego_body_in_intersection"), row.get("ego_body_before_stop_reference")
        other_in = row.get("other_body_in_intersection")
        if any(type(v) is not bool for v in (entry, before_ref, other_in)):
            raise ValueError("Missing original body occupancy")
        samples.append({"frame":fid,"time_s":time,"ego_speed_mps":speed,
                        "ego_body_in_intersection":entry,"ego_body_before_stop_reference":before_ref,
                        "other_body_in_intersection":other_in})
    first_entry = next((i for i,s in enumerate(samples) if s["ego_body_in_intersection"]), None)
    if first_entry is None or first_entry == 0:
        raise ValueError("No observed approach before entry")
    stopped = [s for s in samples[:first_entry] if s["ego_body_before_stop_reference"] and s["ego_speed_mps"] == 0]
    other_occupied = [s for s in samples if s["other_body_in_intersection"]]
    return {"format":"worker-stop-sign-intersection-observations","sources":hashes,
            "first_ego_entry_frame":samples[first_entry]["frame"],
            "observed_full_stop_before_reference":bool(stopped),
            "observed_other_occupancy":bool(other_occupied),"samples":samples,
            "immediate_hazard_judgment":"unresolved; no legal time-to-conflict cutoff",
            "caution_and_yield_judgment":"unresolved","legal_conclusion":"unresolved"}
