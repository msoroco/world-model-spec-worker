"""Independent original lane-selection delivery audit; diagnostics rejected."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from analysis import check_joins, check_source, measure_case, required, rows, HISTORY
from emergency_construction import CASES
from native_packet import AID, VIEWS


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, expected):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=nb_read_frames,width,height,r_frame_rate",
        "-of", "json", str(path)], capture_output=True, text=True, check=True, timeout=120)
    stream = json.loads(probe.stdout)["streams"][0]
    require(stream.get("nb_read_frames") == "900"
            and stream.get("r_frame_rate") in ("20/1", "20")
            and (stream.get("width"), stream.get("height")) == expected,
            "original full camera decode/profile missing")
    digest = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
        "-map", "0:v:0", "-f", "framemd5", "-"], capture_output=True, text=True,
        check=True, timeout=240)
    frame_md5 = [line.rsplit(",", 1)[-1].strip() for line in digest.stdout.splitlines()
                 if line and not line.startswith("#")]
    require(len(frame_md5) == 900 and all(len(value) == 32 for value in frame_md5),
            "actual decoded frame hashes missing")
    return {"decoded_frames": 900, "width": expected[0], "height": expected[1],
            "frame_md5": frame_md5}


def audit_pixels(cues, history, case, expected_md5):
    require(len(cues) == len(history) == len(expected_md5) == 900,
            "driver-view lane/cue frame inventory incomplete")
    movement, hand, lane = [], [], []
    for index, (cue, motion, digest) in enumerate(zip(cues, history, expected_md5)):
        require(cue.get("frame") == motion["frame"] == index and
                cue.get("native_frame") == motion["native_frame"],
                "driver-view lane/cue frame join changed")
        require(cue.get("camera") == "driver_reference" and cue.get("pixel_review_source") and
                cue.get("reviewer") and cue.get("roi_pixels") and cue.get("frame_md5") == digest,
                "actual reviewed driver-view pixels missing or stale")
        require(cue.get("movement_visible") == motion["movement_visible"] and
                cue.get("hand_signal_visible") == motion["driver_hand_signal_visible"],
                "driver-view cue disagrees with original motion packet")
        require(cue.get("ego_lane_id") == motion["ego_lane_id"],
                "reviewed ego body lane disagrees with original lane packet")
        if cue["movement_visible"]:
            movement.append(index)
        if cue["hand_signal_visible"]:
            hand.append(index)
        lane.append(cue["ego_lane_id"])
    if case.motion_state == "preparing_movement":
        require(movement, "reviewed movement preparation cue missing")
    if case.motion_state == "preparing_hand_signal":
        require(hand, "reviewed driver hand signal missing")
    return {"movement_visible_frames": len(movement),
            "hand_signal_visible_frames": len(hand),
            "ego_lane_original_frames": lane}


def audit_attempt(attempt, processed, case_id, decoder=decode):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), "original attempt missing")
    cases = {AID + "__" + case.suffix: case for case in CASES}
    require(case_id in cases, "unknown exact emergency lane case")
    case = cases[case_id]
    diagnostic, source = check_source(attempt, case_id)
    require(not diagnostic, "source-bound original emergency lane seal required")
    seal = json.loads(required(attempt, "capture-seal.json").read_text(encoding="utf-8"))
    require(seal.get("case_id") == case_id, "original seal exact case mismatch")
    source["capture-seal.json"] = sha(attempt / "capture-seal.json")
    for name in ("emergency-site.json", "driver-view-cues.jsonl", "authority-readback.json",
                 "scene-context.json"):
        path = required(attempt, name)
        require(seal.get("sources", {}).get(name) == sha(path),
                "original emergency lane source is not byte sealed: " + name)
    authority = json.loads(required(attempt, "authority-readback.json").read_text(encoding="utf-8"))
    context = json.loads(required(attempt, "scene-context.json").read_text(encoding="utf-8"))
    site = json.loads(required(attempt, "emergency-site.json").read_text(encoding="utf-8"))
    for key in ("road_source_sha256", "weather_sha256", "traffic_sha256",
                "ego_route_sha256", "camera_plan_sha256", "unit_route_sha256",
                "lane_graph_sha256"):
        require(context.get(key), "reviewed original scene context missing: " + key)
    require(site.get("source_kind") == "reviewed_native_lane_site",
            "reviewed Native lane graph required")
    require(authority.get("class") == case.unit_class and
            authority.get("qualifying_flashing_equipment_verified") is True and
            authority.get("authorization_source") and authority.get("equipment_source") and
            authority.get("light_rule_source") == "DEF-NRS-484A-480-3",
            "reviewed original emergency authority/equipment missing")
    history = rows(required(attempt, HISTORY))
    check_joins(attempt, history)
    measurement = measure_case(case, site, history)
    decoded = {}
    for name in VIEWS:
        size = (1920, 1080) if name == "overview" else (1280, 720)
        decoded[name] = decoder(required(attempt, name + ".mkv"), size)
        require(decoded[name].get("decoded_frames") == 900,
                "original full camera decode missing")
    pixel = audit_pixels(rows(required(attempt, "driver-view-cues.jsonl")), history,
                         case, decoded["driver_reference"].get("frame_md5", []))
    require(processed.is_file() and not processed.is_symlink(),
            "saved original physical result missing")
    result = json.loads(processed.read_text(encoding="utf-8"))
    require(result.get("case_id") == case_id and
            result.get("diagnostic_fixture") is False and
            result.get("physical_acceptance_claimed") is False and
            result.get("legal_verdict_claimed") is False,
            "source-bound original nonclaim physical result required")
    return {"format": "c405341-2e-original-delivery-audit-v1", "case_id": case_id,
        "original_frame_count": 900, "measurement": measurement, "lane_pixel_audit": pixel,
        "authority": authority, "scene_context": context, "lane_site": site,
        "original_condition_counts": {"flashing_frames": sum(bool(row["flashing_light_on"]) for row in history),
            "approaching_frames": sum(bool(row["approaching_unit"]) for row in history),
            "traffic_occupied_frames": sum(bool(row["traffic_path_occupied"]) for row in history),
            "other_hazard_frames": sum(bool(row["other_hazard_path_occupied"]) for row in history),
            "weather_adverse_frames": sum(bool(row["weather_adverse"]) for row in history),
            "officer_direction_frames": sum(bool(row["officer_direction"]) for row in history)},
        "camera_decodes": decoded, "source_sha256": source,
        "processed_result_sha256": sha(processed),
        "physical_visibility": "requires_independent_review",
        "legal_possible_and_safe": "unresolved", "legal_status": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processed", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency lane delivery audit")
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
