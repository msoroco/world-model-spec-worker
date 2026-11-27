"""Measure a retained restricted-zone capture from original Native sources.

The independent review is an input, not a fact inferred from a control request.
The output records observable body, timing and nearby-actor facts only.
"""

import argparse
import json
from pathlib import Path

from original_source_contract import CAMERAS, FRAME_COUNT, sha, validate

CHANNELS = ("st.curb_zone", "dev.regulatory_sign", "drv.condition_in_effect",
            "drv.standing_or_parked", "kin.time", "ru.occupant_count",
            "sig.door_open", "ru.pedestrian", "ru.motor_vehicle", "drv.approaching")


def require(value, message):
    if not value:
        raise ValueError(message)


def run(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / "result.json").exists(),
            "choose a fresh saved analysis")
    review_path = attempt / "source-review.json"
    finding = validate(attempt, review_path)
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    require(config.get("case_id") == finding["case_id"], "original case differs from config")
    require(tuple(item["name"] for item in config["recording_description"]["channels"]) == CHANNELS,
            "selected recording channel list changed")
    zone = json.loads((attempt / "zone-survey.json").read_text(encoding="utf-8"))
    actors = [json.loads(line) for line in (attempt / "actor-frames.jsonl").read_text(encoding="utf-8").splitlines()]
    joins = [json.loads(line) for line in (attempt / "camera-frames.jsonl").read_text(encoding="utf-8").splitlines()]
    require(len(actors) == len(joins) == FRAME_COUNT, "original packet length changed")
    source_names = ("capture-manifest.json", "road.xodr", "zone-survey.json",
                    "actor-frames.jsonl", "camera-frames.jsonl", "trace.jsonl",
                    "video_frames.jsonl", "source-review.json")
    if (attempt / "capture-seal.json").is_file():
        source_names += ("capture-seal.json",)
    source_hashes = {name: sha(attempt / name) for name in source_names}
    source_hashes.update({f"{name}.mkv": sha(attempt / f"{name}.mkv") for name in CAMERAS})
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    trace_path = attempt / "trace.jsonl"
    frame_map_path = attempt / "video_frames.jsonl"
    require(trace_path.is_file() and frame_map_path.is_file(),
            "Missing required source: original trace.jsonl or video_frames.jsonl")
    evidence = []
    writers = {}
    try:
        for name in CHANNELS:
            writers[name] = (channels / (name + ".jsonl")).open("x", encoding="utf-8")
            evidence.append({"name": name, "unit": "structured",
                             "reference": "channels/" + name + ".jsonl"})
        previous_nearby = None
        for i, (actor, join) in enumerate(zip(actors, joins)):
                body = actor["ego_body_m"]
                time_s = actor["elapsed_s"]
                nearby = actor["passenger_actor_ids_near_vehicle"]
                values = {
                    "st.curb_zone": {"bounds_m": zone["bounds_m"], "survey_sha256": source_hashes["zone-survey.json"]},
                    "dev.regulatory_sign": {"sign_id": zone["sign_id"],
                                             "original_text_readback": zone["sign_text_readback"],
                                             "authority_review": finding["sign_authority_review"],
                                             "pixel_review": finding["sign_pixel_status"]},
                    "drv.condition_in_effect": {"source_review_required": True,
                                                 "effective_conditions": "unverified"},
                    "drv.standing_or_parked": {"ego_body_m": body,
                                                "ego_speed_mps": actor["ego_speed_mps"]},
                    "kin.time": {"elapsed_s": time_s},
                    "ru.occupant_count": {"observed": False, "value": None},
                    "sig.door_open": {"control_requested": actor["door_open_request"],
                                      "actual_state_observed": False},
                    "ru.pedestrian": {"nearby_actor_ids": nearby,
                                      "nearby_identity_changed": previous_nearby is not None and nearby != previous_nearby,
                                      "actual_loading_observed": False},
                    "ru.motor_vehicle": {"other_vehicles": actor["other_vehicles"]},
                    "drv.approaching": {"other_vehicle_entry_requests":
                                        [v["actor_id"] for v in actor["other_vehicles"] if v["requesting_zone_entry"]],
                                        "waiting_purpose_observed": False},
                }
                for name, value in values.items():
                    writers[name].write(json.dumps({"time_s": time_s, "value": value}) + "\n")
                previous_nearby = nearby
    finally:
        for writer in writers.values():
            writer.close()
    from worker_exchange.native_output import physical_result, write_result
    result = {
        "case_id": config["case_id"], "measured_values": finding,
        "target_checks": [{"target": "restricted-zone use and exception source facts",
                           "requested": config.get("requested_purpose"),
                           "measured": {"stopped_in_zone_frames": finding["stopped_in_zone_frames"],
                                        "door_request_with_nearby_identity_change_frames": finding["nearby_passenger_identity_change_frames_with_door_request"],
                                        "requested_waiting_overlap_frames": finding["requested_waiting_or_entering_overlap_frames"]},
                           "method": "original Native actor/camera join and independent source review",
                           "tolerance": "original purpose, actual loading and interference require local review",
                           "matched": False, "physical_cause_confirmed": False,
                           "cause_evidence": list(source_hashes)}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "accepted": False,
        "termination_reason": "Original source measured; physical, purpose and legal review pending",
        "physical_failure_flags": ["original_purpose_and_physical_review_pending"],
        "trace_reference": "trace.jsonl",
        "video_references": [f"{name}.mkv" for name in CAMERAS] + ["raw.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence, "realized_observables": {},
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
    }
    write_result(attempt, physical_result(attempt, result))
    report = {"format": "worker-analysis-report", "case_id": config["case_id"],
              "measurements": {"restricted_zone_original_facts": {
                  "method": "original_native_source_contract", "value": finding,
                  "sources": source_hashes}},
              "source_complete": True, "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), sort_keys=True))
