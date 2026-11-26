"""Independent saved-source checks for C150979; no legal or physical verdict."""

import hashlib
import argparse
import json
from pathlib import Path
import subprocess

from analysis import measure
from native_capture import VIEWS
from speed_delivery import ASSIGNMENT


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_saved(source, measured):
    """Require current, complete original acquisition joins and real media bytes.

    Caller supplies sealed Native paths/claims after acquisition; the auditor
    opens each file itself. Decode counts are claimed by the caller and require
    separate full video decoder receipts; this check cannot establish pixels.
    """
    _require(source.get("case_id") == measured.get("case_id"), "case binding missing")
    _require(source.get("native_result_path") and source.get("native_result_sha256"), "sealed Native result missing")
    _require(file_sha256(source["native_result_path"]) == source["native_result_sha256"], "Native result seal mismatch")
    _require(source.get("map_sha256") == measured.get("map_sha256"), "map join mismatch")
    count = measured.get("original_frame_count")
    _require(isinstance(count, int) and count >= 400, "original frame count missing")
    frame_map = source.get("frame_map")
    _require(isinstance(frame_map, list) and len(frame_map) == count, "frame map incomplete")
    for i, row in enumerate(frame_map):
        _require(row.get("frame_index") == i and row.get("native_frame") is not None and row.get("time_s") is not None, "frame map identity gap")
        if i:
            _require(row["native_frame"] > frame_map[i - 1]["native_frame"] and row["time_s"] > frame_map[i - 1]["time_s"], "frame map nonmonotone")
    for sample in measured.get("governed_original_samples", []):
        i = sample.get("frame_index")
        _require(isinstance(i, int) and 0 <= i < count and abs(frame_map[i]["time_s"] - sample.get("time_s", -1)) <= 0.002, "measurement time join missing")
    cameras = source.get("cameras", {})
    _require(set(cameras) == set(CAMERAS), "four camera sources missing")
    for name in CAMERAS:
        row = cameras[name]
        _require(row.get("path") and row.get("sha256") and row.get("decoded_frames") == count, f"{name} camera decode missing")
        _require(file_sha256(row["path"]) == row["sha256"], f"{name} camera source changed")
        _require(row.get("original_frame_first") == 0 and row.get("original_frame_last") == count - 1, f"{name} camera frame join missing")
    for name in ("sign_inventory_source", "title_review_source"):
        item = source.get(name, {})
        _require(item.get("path") and item.get("sha256"), "posting source seals missing")
        _require(file_sha256(item["path"]) == item["sha256"], "posting source seal mismatch")
    _require(source.get("physical_completion") is True, "physical completion unconfirmed")
    return {"case_id": measured["case_id"], "original_frame_count": count,
            "native_result_sha256": source["native_result_sha256"],
            "camera_sha256": {name: cameras[name]["sha256"] for name in CAMERAS},
            "status": "source_join_checked_pending_independent_pixel_and_legal_review"}


def _rows(path):
    if not Path(path).is_file() or Path(path).is_symlink():
        raise ValueError("original source missing: " + Path(path).name)
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def _decode(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original camera video missing")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("original camera stream missing")
    stream = streams[0]
    if int(stream.get("nb_read_frames", -1)) < 1 or stream.get("codec_name") != "ffv1":
        raise ValueError("camera full decode profile differs")
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                              "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("camera full decode failed: " + decoded.stderr[-300:])
    return {"sha256": file_sha256(path), "decoded_frames": int(stream["nb_read_frames"]),
            "dimensions": [stream["width"], stream["height"]],
            "fps": stream["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    if case_id not in {row["case_id"] for row in json.loads(Path(plan).read_text())["cases"]}:
        raise ValueError("exact delivery case differs")
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact assignment differs")
    inventory_path = attempt / "inventory.json"
    if not inventory_path.is_file():
        raise ValueError("original inventory missing")
    measured = measure(attempt)
    if measured["case_id"] != case_id:
        raise ValueError("attempt case identity differs")
    mapping = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    evidence = _rows(attempt / "capture/evidence.jsonl")
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("original video and actor frame counts differ")
    numbers = [row.get("carla_frame") for row in mapping]
    if any(row.get("frame") != number or ev.get("original_frame") != number
           for row, ev, number in zip(trace, evidence, numbers)):
        raise ValueError("original video and actor frame join differs")
    videos = {name: _decode(attempt / (name + ".mkv")) for name in VIEWS}
    if any(item["decoded_frames"] != len(mapping) for item in videos.values()):
        raise ValueError("camera full-decode frame count differs")
    history = json.loads((attempt / "history.json").read_text())
    joined = len(history) == len(mapping) and all(
        abs(packet["time_s"] - mapped["time_s"]) < .005 and
        packet.get("source_frame_id", mapped["carla_frame"]) == mapped["carla_frame"]
        for packet, mapped in zip(history, mapping))
    fixture = (attempt / "fixture-provenance.json").is_file()
    if not fixture and (not joined or len(mapping) != 900):
        raise ValueError("original Native source/video frame join incomplete")
    return {"format": "c150979-independent-speed-delivery-audit-v1",
            "case_id": case_id, "inventory_sha256": file_sha256(inventory_path),
            "source_measurement": {"observed_speed_mph_min": measured["observed_speed_mph_min"],
                                   "observed_speed_mph_max": measured["observed_speed_mph_max"],
                                   "posting_context": measured["posting_context"]},
            "capture_frames": len(mapping), "packet_frames": len(history),
            "source_video_join": joined, "four_view_full_decode": videos,
            "diagnostic_fixture": fixture, "actual_pixels_verified": False,
            "physical_acceptance": False, "legal_posting_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent audit")
    result = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
