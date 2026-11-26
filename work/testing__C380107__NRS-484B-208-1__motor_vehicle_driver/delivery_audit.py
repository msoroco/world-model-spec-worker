"""Independently bind released original highway/HOV footage and measurements."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from package_contract import ASSIGNMENT, CAMERAS
from reviewed_site import plan
from hov_encounter_observations import observe


VIEWS = tuple(item["name"] for item in CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def linked(root, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
        raise ValueError("original source reference missing")
    candidate = root / ref["path"]
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original source path missing or escaping root")
    if sha(path) != ref["sha256"]:
        raise ValueError("original source hash changed")
    return path


def probe_video(path):
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_entries", "stream=nb_read_frames,r_frame_rate,width,height",
               "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required")
    return streams[0]


def decode_video(path):
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                   capture_output=True, text=True, check=True, timeout=300)
    return True


def pixel_check(paths):
    from PIL import Image, ImageStat
    signatures = []
    for path in paths:
        with Image.open(path) as picture:
            picture.load()
            rgb = picture.convert("RGB")
            if min(rgb.size) < 360 or max(ImageStat.Stat(rgb).stddev) < 1.0:
                raise ValueError("original camera pixels blank or too small")
            signatures.append(sha(path))
    if len(set(signatures)) < 2:
        raise ValueError("original camera frames are identical across sampled times")
    return True


def audit(root, receipt, probe=probe_video, decode=decode_video, pixels=pixel_check):
    root = Path(root).resolve()
    case_id = receipt.get("case_id", "")
    if (not case_id.startswith(ASSIGNMENT + "__") or
            receipt.get("source_kind") != "original_native_attempt" or
            receipt.get("diagnostic_fixture") is True or
            receipt.get("owner_released") is not True or
            receipt.get("native_process_exit_code") != 0 or
            not receipt.get("attempt_id") or not receipt.get("recording_id")):
        raise ValueError("released original highway/HOV Native attempt required")
    site_path = linked(root, receipt.get("site_ref"))
    scene = plan(root, receipt["site_ref"], case_id)
    frame_path = linked(root, receipt.get("frame_map_ref"))
    trace_path = linked(root, receipt.get("trace_ref"))
    context_path = linked(root, receipt.get("context_ref"))
    original_receipt_path = linked(root, receipt.get("original_receipt_ref"))
    videos = receipt.get("video_refs")
    if not isinstance(videos, dict) or set(videos) != set(VIEWS):
        raise ValueError("four original camera videos required")
    video_paths = {name: linked(root, videos[name]) for name in VIEWS}
    seal_path = linked(root, receipt.get("capture_seal_ref"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (seal.get("source_kind") != "original_native_capture_seal" or
            seal.get("case_id") != case_id or
            seal.get("attempt_id") != receipt["attempt_id"] or
            seal.get("recording_id") != receipt["recording_id"]):
        raise ValueError("original capture seal identity differs")
    all_refs = [receipt[name] for name in ("site_ref", "frame_map_ref", "trace_ref",
                                            "context_ref", "original_receipt_ref")]
    all_refs.extend(videos.values())
    if any(seal.get("sources", {}).get(ref["path"]) != ref["sha256"] for ref in all_refs):
        raise ValueError("original capture seal inventory differs")
    frame_map = json.loads(frame_path.read_text())
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
    frames = frame_map.get("frames")
    if (frame_map.get("source_kind") != "original_native_frame_map" or
            frame_map.get("case_id") != case_id or
            not isinstance(frames, list) or len(frames) != 900 or
            not isinstance(rows, list) or len(rows) != 900):
        raise ValueError("complete original 900-frame map and motion required")
    first_last_paths = []
    for index, (frame, row) in enumerate(zip(frames, rows)):
        if (frame.get("frame") != index or row.get("frame") != index or
                frame.get("time_s") != row.get("time_s") or
                frame.get("native_frame") != row.get("native_frame") or
                set(frame.get("camera_frames", {})) != set(VIEWS)):
            raise ValueError("original four-camera time join differs")
        for name in VIEWS:
            image = frame["camera_frames"][name]
            if image.get("native_frame") != frame["native_frame"]:
                raise ValueError("original camera native frame differs")
            path = linked(root, image)
            if index in (0, 450, 899):
                first_last_paths.append(path)
    for name, path in video_paths.items():
        stream = probe(path)
        expected = next(item for item in CAMERAS if item["name"] == name)
        if (stream.get("nb_read_frames") != "900" or
                stream.get("r_frame_rate") != "20/1" or
                int(stream.get("width", 0)) != expected["width"] or
                int(stream.get("height", 0)) != expected["height"]):
            raise ValueError("original camera decode or profile incomplete: " + name)
        decode(path)
    pixels(first_last_paths)
    measured = observe(case_id, context_path, trace_path, original_receipt_path)
    return {"format": "c380107-original-delivery-audit-v1", "case_id": case_id,
            "attempt_id": receipt["attempt_id"], "recording_id": receipt["recording_id"],
            "source_kind": "original_native_attempt", "site_sha256": sha(site_path),
            "trace_sha256": sha(trace_path), "frame_map_sha256": sha(frame_path),
            "capture_seal_sha256": sha(seal_path),
            "video_sha256": {name: sha(path) for name, path in video_paths.items()},
            "frames_checked": 900,
            "measurement": {"rear_gap_crossing_frame": measured["first_rear_gap_crossing_frame"],
                            "posted_limit_mps": measured["posted_limit_mps"],
                            "extreme_left_lane_id": measured["extreme_left_lane_id"],
                            "hov_designation_state": measured["hov_designation_state_source_label"],
                            "hov_compliance_state": measured["hov_compliance_state_source_label"]},
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "physical_completion": "requires independent local review",
            "legal_verdict": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh independent audit output required")
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if receipt.get("case_id") != args.case:
        raise ValueError("independent audit selects another exact case")
    result = audit(args.authority_root, receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"case_id": result["case_id"], "source_kind": result["source_kind"],
                      "frames_checked": result["frames_checked"],
                      "legal_verdict": "unresolved"}, sort_keys=True))


if __name__ == "__main__":
    main()
