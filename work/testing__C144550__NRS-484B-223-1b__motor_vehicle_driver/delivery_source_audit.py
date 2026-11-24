"""Independent source and frame audit for an exact lane-change attempt.

Diagnostic attempts prove the software path only. Native acceptance requires a
separately sealed acquisition, original pixel review and owner release.
"""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from lane_change_measurements import measure_exact_case
from late_lane_change_measurements import measure_exact_case as measure_late_case


HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, case_id):
    attempt = Path(attempt).resolve()
    manifest = read(HERE / "execution-manifest.json")
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact lane-change case")
    config = read(attempt / "config.json")
    result = read(attempt / "result.json")
    report = read(attempt / "analysis-report.json")
    receipt = read(attempt / "compatibility.json")
    provenance = read(attempt / "acquisition-provenance.json")
    if any(value.get("case_id") != case_id for value in (result, report, receipt)) or config.get("selected_case_id") != case_id:
        raise ValueError("Exact case identity differs")
    if receipt.get("passed") is not True or receipt.get("candidate_id") != "primary" or receipt.get("construction_sha256") != entry["construction_sha256"]:
        raise ValueError("Current exact primary compatibility differs")
    if (provenance != {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}
            or result.get("provenance_kind") != "synthetic_fixture"
            or result.get("diagnostic_fixture") is not True
            or result.get("physical_acceptance_claimed") is not False):
        raise ValueError("Diagnostic provenance or acceptance claim differs")
    inventory = receipt.get("fixture_manifest", {})
    required = {"lane_context.json", "lane_history.jsonl", "video_frames.jsonl", "trace.jsonl",
                "capture/evidence.jsonl"}
    if not required <= set(inventory):
        raise ValueError("Original source inventory incomplete")
    for name in required:
        source = attempt / name
        if not source.is_file() or sha(source) != inventory[name]:
            raise ValueError("Original source changed: " + name)
    if sha(attempt / "config.json") != result.get("physical_checks", {}).get("setup", {}).get("sources", {}).get("config.json"):
        raise ValueError("Original config changed")
    four_view = read(attempt / "four-view-receipt.json")
    if (four_view.get("format") != "synchronized-four-view"
            or four_view.get("frame_map_sha256") != inventory["video_frames.jsonl"]
            or set(four_view.get("sources", {})) != set(CAMERAS)):
        raise ValueError("Original four-view binding differs")
    for name in CAMERAS:
        if sha(attempt / (name + ".mkv")) != four_view["sources"][name]:
            raise ValueError("Original camera source changed: " + name)
    evidence = result.get("source_evidence_hashes", {})
    if evidence != report.get("source_hashes") or any(inventory.get(name) != digest for name, digest in evidence.items()):
        raise ValueError("Original measurement source binding differs")
    mapping, trace, lane, capture = [rows(attempt / name) for name in
                                     ("video_frames.jsonl", "trace.jsonl", "lane_history.jsonl", "capture/evidence.jsonl")]
    count = config.get("rate_hz", 0) * config.get("duration_s", 0)
    if count != 900 or any(len(stream) != count for stream in (mapping, trace, lane, capture)):
        raise ValueError("Original source frame count differs")
    participants = set()
    for index, (frame, motion, body, observation) in enumerate(zip(mapping, trace, lane, capture)):
        native, time_s = frame.get("carla_frame"), frame.get("time_s")
        if (frame.get("video_frame") != index or native != motion.get("frame") or native != body.get("frame")
                or native != observation.get("original_frame") or not isinstance(time_s, (int, float))
                or not math.isfinite(time_s) or abs(time_s - motion.get("time_s", float("inf"))) > .001
                or abs(time_s - body.get("time_s", float("inf"))) > .001
                or abs(time_s - observation.get("recording_time_s", float("inf"))) > .001):
            raise ValueError("Original frame/time join differs")
        if index and (native <= mapping[index - 1]["carla_frame"]
                      or abs(time_s - mapping[index - 1]["time_s"] - 1 / config["rate_hz"]) > .001):
            raise ValueError("Original frame/time sequence differs")
        people = observation.get("original_observations", {}).get("participants")
        if not isinstance(people, list) or len(people) < 2:
            raise ValueError("Original participant inventory incomplete")
        ids = [person.get("actor_id") for person in people if isinstance(person, dict)]
        if len(ids) != len(people) or len(set(ids)) != len(ids) or observation.get("actor_id") not in ids:
            raise ValueError("Original participant identity differs")
        if any(not isinstance(person.get("body_vertices_m"), list) or len(person["body_vertices_m"]) < 8
               for person in people):
            raise ValueError("Original participant body missing")
        participants.update(ids)
    measure = measure_late_case if case_id.endswith("__left_signal_late_clear_gap") else measure_exact_case
    measured = measure(attempt, case_id, count)
    if not measured["observed_signal_pattern_matches_plan"]:
        raise ValueError("Original signal pattern differs from selected construction")
    if measured["sources"] != evidence or report.get("legal_verdict_asserted") is not False:
        raise ValueError("Fresh exact measurement or legal scope differs")
    cameras = {item["name"]: item for item in config.get("cameras", [])}
    if set(cameras) != set(CAMERAS) or set(result.get("video_references", [])) != {name + ".mkv" for name in CAMERAS}:
        raise ValueError("Four original cameras required")
    decodes = {}
    for name in CAMERAS:
        source = attempt / (name + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(source)],
                               capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or (streams[0].get("width"), streams[0].get("height")) != (cameras[name]["width"], cameras[name]["height"]) or int(streams[0].get("nb_read_frames", -1)) != count:
            raise ValueError("Original camera frame count or dimensions differ: " + name)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0",
                                  "-f", "framemd5", "-"], capture_output=True, check=True)
        frame_lines = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b"#")]
        if len(frame_lines) != count:
            raise ValueError("Original camera full decode differs: " + name)
        decodes[name] = {"frames": count, "source_sha256": sha(source),
                         "decoded_frames_sha256": hashlib.sha256(b"\n".join(frame_lines)).hexdigest()}
    return {"format": "worker-lane-change-source-diagnostic-audit", "case_id": case_id,
            "frames": count, "participant_ids": sorted(participants), "source_hashes": evidence,
            "camera_decodes": decodes, "software_checks_passed": True, "diagnostic_only": True,
            "native_source_accepted": False, "actual_pixels_reviewed": False,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case), sort_keys=True))
