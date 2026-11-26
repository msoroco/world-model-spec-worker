"""Independent original emergency-unit delivery audit; diagnostics rejected."""

from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path
import subprocess

from analysis import check_joins, check_source, measure_case, required, rows, HISTORY
from emergency_construction import CASES
from native_packet import AID, VIEWS


def require(ok, message):
    if not ok:
        raise ValueError(message)


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


def audit_cues(cues, history, case):
    require(len(cues) == len(history) == 900, "driver-view cue frame inventory incomplete")
    visible_movement, visible_hand = [], []
    for index, (cue, motion) in enumerate(zip(cues, history)):
        require(cue.get("frame") == motion["frame"] == index and
                cue.get("native_frame") == motion["native_frame"],
                "driver-view cue frame join changed")
        require(cue.get("camera") == "driver_reference" and cue.get("pixel_review_source") and
                cue.get("reviewer") and cue.get("roi_pixels") and cue.get("frame_md5"),
                "actual reviewed driver-view pixels missing")
        require(cue.get("movement_visible") == motion["movement_visible"],
                "driver-view movement visibility disagrees with motion packet")
        if cue["movement_visible"]:
            visible_movement.append(index)
        if cue.get("hand_signal_visible") is True:
            visible_hand.append(index)
    if case.cue == "movement":
        require(bool(visible_movement) == case.visible,
                "physical movement visibility differs from selected case")
    else:
        require(visible_hand, "reviewed driver hand signal missing")
    return {"movement_visible_frames": len(visible_movement),
            "hand_signal_visible_frames": len(visible_hand)}


def audit_attempt(attempt, processed, case_id, decoder=decode):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), "original attempt missing")
    cases = {AID + "__" + case.suffix: case for case in CASES}
    require(case_id in cases, "unknown exact emergency case")
    diagnostic, source = check_source(attempt, case_id)
    require(not diagnostic, "source-bound original emergency seal required")
    seal = json.loads(required(attempt, "capture-seal.json").read_text(encoding="utf-8"))
    require(seal.get("case_id") == case_id, "original seal exact case mismatch")
    source["capture-seal.json"] = hashlib.sha256(required(attempt, "capture-seal.json").read_bytes()).hexdigest()
    for name in ("emergency-site.json", "driver-view-cues.jsonl", "authority-readback.json",
                 "scene-context.json"):
        path = required(attempt, name)
        require(seal.get("sources", {}).get(name) == hashlib.sha256(path.read_bytes()).hexdigest(),
                "original emergency source is not byte sealed: " + name)
    authority = json.loads(required(attempt, "authority-readback.json").read_text(encoding="utf-8"))
    context = json.loads(required(attempt, "scene-context.json").read_text(encoding="utf-8"))
    for key in ("road_source_sha256", "weather_sha256", "ego_route_sha256",
                "camera_plan_sha256", "unit_route_sha256"):
        require(context.get(key), "reviewed original scene context missing: " + key)
    require(authority.get("class") == cases[case_id].unit_class and
            authority.get("qualifying_flashing_equipment_verified") is True and
            authority.get("authorization_source") and authority.get("equipment_source") and
            authority.get("light_rule_source") == "DEF-NRS-484A-480-3",
            "reviewed original emergency authority/equipment missing")
    history = rows(required(attempt, HISTORY))
    check_joins(attempt, history)
    require(all(row.get("motion_source") and row.get("light_source") and
                row.get("visibility_source") and row.get("control_source")
                for row in history), "original emergency source bindings incomplete")
    require(any(row.get("flashing_light_on") is True for row in history),
            "qualifying flashing-light use absent from original frames")
    first_distance = hypot(history[0]["ego_xy"][0] - history[0]["emergency_xy"][0],
                           history[0]["ego_xy"][1] - history[0]["emergency_xy"][1])
    require(any(hypot(row["ego_xy"][0] - row["emergency_xy"][0],
                      row["ego_xy"][1] - row["emergency_xy"][1]) < first_distance
                for row in history), "ego approach to emergency unit absent")
    site = json.loads(required(attempt, "emergency-site.json").read_text(encoding="utf-8"))
    measurement = measure_case(cases[case_id], site, history)
    cues = audit_cues(rows(required(attempt, "driver-view-cues.jsonl")), history, cases[case_id])
    decoded = {}
    for name in VIEWS:
        size = (1920, 1080) if name == "overview" else (1280, 720)
        decoded[name] = decoder(required(attempt, name + ".mkv"), size)
        require(decoded[name].get("decoded_frames") == 900,
                "original full camera decode missing")
    require([cue["frame_md5"] for cue in cues] == decoded["driver_reference"].get("frame_md5"),
            "reviewed driver-view pixels differ from original decoded frames")
    require(processed.is_file() and not processed.is_symlink(),
            "saved original physical result missing")
    result = json.loads(processed.read_text(encoding="utf-8"))
    require(result.get("case_id") == case_id and
            result.get("diagnostic_fixture") is False and
            result.get("physical_acceptance_claimed") is False and
            result.get("legal_verdict_claimed") is False,
            "source-bound original nonclaim physical result required")
    return {"format": "c405341-2c-original-delivery-audit-v1", "case_id": case_id,
        "original_frame_count": 900, "measurement": measurement, "cue_pixel_audit": cues,
        "authority": authority, "scene_context": context,
        "camera_decodes": decoded, "source_sha256": source,
        "processed_result_sha256": hashlib.sha256(processed.read_bytes()).hexdigest(),
        "physical_visibility": "requires_independent_review",
        "prepared_to_stop": "unresolved", "legal_status": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processed", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency delivery audit")
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
