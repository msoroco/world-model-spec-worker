"""Independent CPU source and pixel audit for one exact flagger case."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from measure_original import measure_core_join


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries", "stream=nb_read_frames",
                            "-of", "default=nw=1:nk=1", str(path)],
                           capture_output=True, text=True, check=True, timeout=120)
    if int(probe.stdout.strip()) != 600:
        raise ValueError("Incomplete delivery video: " + path.name)
    pixels = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                             "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    if pixels.returncode or pixels.stderr:
        raise ValueError("Video pixel decoding failed: " + path.name + pixels.stderr)


def audit(root, case, diagnostic):
    root = Path(root)
    if not case.startswith("training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator__probe_"):
        raise ValueError("Another assignment selected")
    if not diagnostic:
        for name in ("capture-seal.json", "native-capture-report.json"):
            if not (root / name).is_file():
                raise ValueError("Missing delivery source: " + name)
    measured = measure_core_join(root, case)
    compliant = case.endswith(("__probe_a", "__probe_c"))
    observed = measured["body_crossed_during_requested_stop"]
    if observed == compliant:
        raise ValueError("Requested exact flagger response not realized")
    for name in CAMERAS:
        decode(root / (name + ".mkv"))
    sources = {name: sha(root / name) for name in
               ("captured-source-hashes.json", "native-rows.jsonl", "trace.jsonl",
                "video_frames.jsonl", "capture/evidence.jsonl",
                "capture/native/frames.jsonl", "original-flagger-review.json")}
    sources.update({name + ".mkv": sha(root / (name + ".mkv")) for name in CAMERAS})
    return {"format": "c183370-independent-delivery-audit-v1", "case_id": case,
            "checks": list(CHECKS), "source_hashes": sources, "frames": measured["frame_count"],
            "location_basis": measured["statutory_location_basis"],
            "body_crossed_during_requested_stop": observed,
            "requested_indication_at_crossing": measured["requested_indication_at_crossing"],
            "diagnostic_fixture": diagnostic, "original_native_observed": not diagnostic,
            "display_pixels_reviewed": False, "physical_acceptance": False,
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    for name in ("attempt", "case", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "frames": result["frames"],
                      "physical_acceptance": False, "legal_verdict": None}))


if __name__ == "__main__":
    main()
