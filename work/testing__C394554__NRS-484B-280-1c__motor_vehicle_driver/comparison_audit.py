"""Independent controlled comparison of original waiting versus boarding."""
import argparse
import json
import math
from pathlib import Path


FIXED = ("law_id", "cell_id", "actor_id", "map_sha256", "fixed_scene_sha256",
         "participant_classes", "camera_contract_sha256", "duration_s")


def audit(waiting, boarding):
    if (not waiting.get("case_id", "").endswith("__waiting_at_stop") or
            not boarding.get("case_id", "").endswith("__boarding_bus")):
        raise ValueError("wrong exact transit comparison cases")
    for key in FIXED:
        if not waiting.get(key) or not boarding.get(key):
            raise ValueError("missing fixed condition: " + key)
        if waiting[key] != boarding[key]:
            raise ValueError("fixed condition differs: " + key)
    first = waiting.get("fixed_transit_geometry", {})
    second = boarding.get("fixed_transit_geometry", {})
    for key in ("stop_blueprint_id", "bus_blueprint_id", "road_id"):
        if first.get(key) is None or first.get(key) != second.get(key):
            raise ValueError("fixed transit identity differs: " + key)
    for key in ("stop_position_m", "bus_position_m"):
        a, b = first.get(key), second.get(key)
        if (not isinstance(a, list) or not isinstance(b, list) or len(a) != 3 or len(b) != 3 or
                math.dist(a, b) > 0.1):
            raise ValueError("fixed transit placement differs: " + key)
    for key in ("x_min", "x_max", "y_min", "y_max"):
        a = first.get("door_region_m", {}).get(key)
        b = second.get("door_region_m", {}).get(key)
        if type(a) not in (int, float) or type(b) not in (int, float) or abs(a-b) > 0.1:
            raise ValueError("fixed bus-side region differs")
    for record, phase in ((waiting, "waiting_at_stop"), (boarding, "boarding_bus")):
        if record.get("format") != "worker-delivery-audit" or record.get("passed") is not True:
            raise ValueError("source-audited delivery receipt missing")
        if record.get("passenger_phase") != phase:
            raise ValueError("declared phase differs from exact case")
        if not all(record.get(key) for key in
                   ("native_result_sha256", "frame_map_sha256", "video_sha256",
                    "source_decode_receipt_sha256", "pixel_review_sha256")):
            raise ValueError("missing original saved-media or pixel-review binding")
        measured = record.get("measurement", {})
        if measured.get("format") != "worker-transit-pedestrian-measurements" or not all(
                measured.get("sources", {}).get(name) for name in
                ("transit-site.json", "map.xodr", "encounter-history.jsonl", "video_frames.jsonl")):
            raise ValueError("missing source-bound transit measurement")
        if measured.get("frame_count") != record.get("frame_count") or measured.get("first_observation") is None:
            raise ValueError("incomplete original encounter history")
        if measured.get("legal_proper_caution_verdict") != "unresolved" or record.get("legal_verdict") is not None:
            raise ValueError("comparison asserted legal proper caution")
        if record.get("human_observation_claimed") is not False:
            raise ValueError("scripted input misrepresented as human cognition")
    before = waiting["measurement"]["door_approach_m"]
    after = boarding["measurement"]["door_approach_m"]
    if type(before) not in (int, float) or type(after) not in (int, float) or not after > before:
        raise ValueError("declared passenger movement difference not observed")
    return {"comparison_id": "transit_passenger_state", "passed": True,
            "fixed_conditions": list(FIXED) + ["original stop/bus placement and bus-side region within 0.1 m measurement tolerance"],
            "difference": "measured pedestrian movement toward bus-side ingress region",
            "waiting_door_approach_m": before, "boarding_door_approach_m": after,
            "actual_boarding_reviewed": not (waiting.get("fixture_only") or
                                              boarding.get("fixture_only")),
            "human_observation_claimed": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("waiting")
    parser.add_argument("boarding")
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.waiting).read_text()),
                           json.loads(Path(args.boarding).read_text())), indent=2))


if __name__ == "__main__":
    main()
