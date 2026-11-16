"""Independent source and media audit for saved pedestrian officer-response attempts."""
from __future__ import annotations
import json
import hashlib
import math
import subprocess
from pathlib import Path

def audit_saved_sources(attempt, *, missing_source=None):
    """Recompute the saved observation from originals, without the finalizer."""
    root = Path(attempt)
    def required(name):
        if name == missing_source:
            raise ValueError("Missing required original: " + name)
        path = root / name
        if not path.is_file() or not path.read_bytes():
            raise ValueError("Missing required original: " + name)
        return path

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def rows(name):
        return [json.loads(line) for line in required(name).read_text().splitlines() if line.strip()]

    config = json.loads(required("config.json").read_text())
    report = json.loads(required("analysis-report.json").read_text())
    result = json.loads(required("result.json").read_text())
    case_id = config["selected_case_id"]
    if report.get("case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Saved case identity differs")
    if any(x.get("legal_acceptance_claimed") or x.get("physical_acceptance_claimed")
           for x in (report, result)):
        raise ValueError("Saved result asserts physical or legal acceptance")
    sources = report["measurements"]["officer_response"]["sources"]
    names = ("officer_context.json", "officer_direction.json", "subject_motion.json",
             "subject_motion_history.jsonl", "video_frames.jsonl", "trace.jsonl")
    if set(sources) != set(names):
        raise ValueError("Saved officer-response source inventory differs")
    for name in names:
        if digest(required(name)) != sources[name]:
            raise ValueError("Saved officer-response source hash differs: " + name)
    context = json.loads(required(names[0]).read_text())
    direction = json.loads(required(names[1]).read_text())
    motion = json.loads(required(names[2]).read_text())
    history, frames, trace = rows(names[3]), rows(names[4]), rows(names[5])
    if not history or not (len(history) == len(frames) == len(trace)) or motion.get("frames") != history:
        raise ValueError("Original pedestrian motion and frame lengths differ")
    if context.get("actor_role") != "pedestrian" or context.get("officer_role") != "police_officer":
        raise ValueError("Original pedestrian or officer role differs")
    if not context.get("duty_source") or not context.get("lawfulness_source"):
        raise ValueError("Original officer legal-context sources missing")
    subject, officer = context.get("subject_id"), context.get("officer_id")
    if not subject or not officer or direction.get("subject_id") != subject or direction.get("officer_id") != officer or direction.get("recipient_id") != subject:
        raise ValueError("Original officer direction is not addressed to this subject")
    if not all(direction.get(k) for k in ("exact_direction_text", "wait_location_source",
                                         "communication_source", "opportunity_source", "indication_source")):
        raise ValueError("Original direction or communication source missing")
    if direction.get("actual_perception") is not None:
        raise ValueError("Original source asserts actual perception")
    command = direction.get("command")
    if command not in ("stop", "proceed") or command not in case_id:
        raise ValueError("Original command differs from selected case")
    indication = direction.get("frame")
    if type(indication) is not int or indication not in {row.get("frame") for row in history}:
        raise ValueError("Original indication frame missing")
    for index, (row, mapping, tick) in enumerate(zip(history, frames, trace)):
        if (mapping.get("video_frame") != index or mapping.get("carla_frame") != row.get("frame")
                or tick.get("frame") != row.get("frame") or mapping.get("time_s") != row.get("time_s")
                or tick.get("time_s") != row.get("time_s") or row.get("subject_id") != subject):
            raise ValueError("Original pedestrian frame join differs")
        if index and (row["frame"] != history[index - 1]["frame"] + 1
                      or row["time_s"] <= history[index - 1]["time_s"]):
            raise ValueError("Original pedestrian frame continuity differs")
    following = [row["speed_mps"] for row in history if row["frame"] > indication]
    if len(following) < 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in following):
        raise ValueError("Original post-indication motion invalid")
    response = ("stopped_after_indication" if any(v <= .1 for v in following) else "no_observed_stop") if command == "stop" else ("moved_after_indication" if any(v > .5 for v in following) else "no_observed_movement")
    observed = report["measurements"]["officer_response"]["value"]
    if (observed.get("observed_response") != response or result["measured_values"]["officer_response"] != observed
            or observed.get("post_indication_samples") != len(following)
            or observed.get("min_post_speed_mps") != min(following)
            or observed.get("max_post_speed_mps") != max(following)):
        raise ValueError("Saved response differs from original motion")
    channels = {"subject_speed_mps": [row["speed_mps"] for row in history],
                "officer_direction": [int(row["frame"] >= indication) for row in history]}
    for name, expected in channels.items():
        actual = rows(name + ".jsonl")
        if [(r.get("frame"), r.get("time_s"), r.get("value")) for r in actual] != [
                (r["frame"], r["time_s"], value) for r, value in zip(history, expected)]:
            raise ValueError("Derived officer-response channel differs: " + name)
    video_hashes = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        path = required(name + ".mkv")
        decode = subprocess.run(("ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"),
                                capture_output=True, text=True, check=False)
        if decode.returncode or decode.stderr:
            raise ValueError("Original camera full decode failed: " + name)
        count = subprocess.run(("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1",
                                str(path)), capture_output=True, text=True, check=False)
        if count.returncode or count.stdout.strip() != str(len(history)):
            raise ValueError("Original camera frame count differs: " + name)
        video_hashes[name] = digest(path)
    return {"case_id": case_id, "original_frames": len(history),
            "observed_response": response, "source_sha256": sources,
            "video_sha256": video_hashes, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


def compare_saved_pair(responding_attempt, nonresponding_attempt, *, command):
    """Require the same direction and capture conditions across a response pair."""
    if command not in ("stop", "proceed"):
        raise ValueError("Unsupported officer command")
    left = audit_saved_sources(responding_attempt)
    right = audit_saved_sources(nonresponding_attempt)
    prefix = left["case_id"].rsplit("__", 1)[0]
    if (left["case_id"] != prefix + "__" + command + "_responds" or
            right["case_id"] != prefix + "__" + command + "_does_not_respond"):
        raise ValueError("Fixed-command exact response pair differs")
    fixed = ("officer_context.json", "officer_direction.json", "video_frames.jsonl")
    for name in fixed:
        if left["source_sha256"][name] != right["source_sha256"][name]:
            raise ValueError("Fixed officer or capture source differs: " + name)
    if left["video_sha256"] != right["video_sha256"]:
        raise ValueError("Fixed four-camera sources differ")
    expected = {"stop": ("stopped_after_indication", "no_observed_stop"),
                "proceed": ("moved_after_indication", "no_observed_movement")}[command]
    if (left["observed_response"], right["observed_response"]) != expected:
        raise ValueError("Original response distinction absent")
    return {"case_ids": [left["case_id"], right["case_id"]],
            "fixed_originals": {name: left["source_sha256"][name] for name in fixed},
            "fixed_cameras": left["video_sha256"],
            "deliberate_difference": "original post-indication pedestrian motion",
            "responses": list(expected), "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


def run_suite(attempts):
    if len(attempts) != 4:
        raise ValueError("Four exact saved pedestrian attempts required")
    audited = [audit_saved_sources(path) for path in attempts]
    suffixes = ("__stop_responds", "__stop_does_not_respond",
                "__proceed_responds", "__proceed_does_not_respond")
    if any(not row["case_id"].endswith(suffix) for row, suffix in zip(audited, suffixes)):
        raise ValueError("Saved pedestrian exact case order differs")
    comparisons = [compare_saved_pair(attempts[0], attempts[1], command="stop"),
                   compare_saved_pair(attempts[2], attempts[3], command="proceed")]
    negatives = []
    for missing in ("officer_direction.json", "overview.mkv"):
        try:
            audit_saved_sources(attempts[0], missing_source=missing)
        except ValueError as error:
            if str(error) != "Missing required original: " + missing:
                raise
            negatives.append({"removed": missing, "rejected": True, "error": str(error)})
        else:
            raise ValueError("Missing original was accepted: " + missing)
    for pair in ((attempts[0], attempts[0], "stop"),
                 (attempts[0], attempts[3], "stop")):
        try:
            compare_saved_pair(pair[0], pair[1], command=pair[2])
        except ValueError as error:
            if str(error) != "Fixed-command exact response pair differs":
                raise
            negatives.append({"pair": [str(pair[0]), str(pair[1])],
                              "rejected": True, "error": str(error)})
        else:
            raise ValueError("Invalid response comparison was accepted")
    return {"format": "worker-pedestrian-officer-delivery-audit-fixture",
            "audit_sha256": digest_file(Path(__file__)), "case_audits": audited,
            "comparison_audits": comparisons, "negative_probes": negatives,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_suite(args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
