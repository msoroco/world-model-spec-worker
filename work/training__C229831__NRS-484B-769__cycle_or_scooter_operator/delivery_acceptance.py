"""Independent exact-case saved-source audit; diagnostic evidence stays diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER / "native"))
from audit_arm_cases import audit_case

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def need(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing delivery source: " + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(root, case, diagnostic):
    root = Path(root)
    config = json.loads(need(root, "config.json").read_text())
    selected = config.get("selected_case_id") or config.get("case", {}).get("case_id")
    if selected != case:
        raise ValueError("Wrong exact delivery case")
    source_names = ("rider_arm.jsonl", "camera_frames.jsonl", "road_context.json",
                    "trace.jsonl", "video_frames.jsonl", "capture-seal.json",
                    "analysis-report.json")
    evidence = {name: sha(need(root, name)) for name in source_names}
    arm, camera, trace, video = (rows(root / name) for name in
                                 ("rider_arm.jsonl", "camera_frames.jsonl",
                                  "trace.jsonl", "video_frames.jsonl"))
    if any(len(stream) != 600 for stream in (arm, camera, trace, video)):
        raise ValueError("Incomplete 600-frame delivery source")
    for index, (rider, frame, state, mapped) in enumerate(zip(arm, camera, trace, video)):
        native = rider["native_frame"]
        if (rider["frame"] != index or frame["frame"] != index or
                frame["native_frame"] != native or state["frame"] != native or
                mapped["native_frame"] != native or mapped["video_frame"] != index or
                any(mapped["camera_native_frames"][name] != native for name in CAMERAS)):
            raise ValueError("Delivery source time join failed")
    source_audit = audit_case(root, case, diagnostic_fixture=diagnostic)
    for name in CAMERAS:
        path = need(root, name + ".mkv")
        run = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-count_frames", "-show_entries", "stream=nb_read_frames",
                              "-of", "default=nw=1:nk=1", str(path)],
                             capture_output=True, text=True, check=True)
        if int(run.stdout.strip()) != 600:
            raise ValueError("Incomplete delivery video: " + name)
        evidence[name + ".mkv"] = sha(path)
    return {"format": "c229831-independent-delivery-audit-v1", "case_id": case,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "source_hashes": evidence, "arm_source_audit": source_audit,
            "frames": 600, "diagnostic_fixture": diagnostic,
            "original_native_observed": not diagnostic,
            "pixel_visibility_reviewed": False,
            "physical_acceptance": False, "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("attempt", "case", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "frames": 600,
                      "diagnostic_fixture": args.diagnostic,
                      "physical_acceptance": False}))
