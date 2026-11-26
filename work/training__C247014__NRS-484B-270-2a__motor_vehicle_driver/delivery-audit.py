"""Independently inspect an exact cycle-pass source and four decoded videos."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("config.json", "road.xodr", "participant-poses.jsonl", "trace.jsonl",
           "video_frames.jsonl", "capture/evidence.jsonl", "pass-context.json")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(root, name, omitted):
    path = root / name
    if name == omitted or not path.is_file():
        raise ValueError("Missing delivery source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def decode(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries", "stream=nb_read_frames",
                            "-of", "default=nw=1:nk=1", str(path)],
                           capture_output=True, text=True, check=True, timeout=120)
    if int(probe.stdout.strip()) != 600:
        raise ValueError("Incomplete delivery video: " + path.name)
    run = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                          "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    if run.returncode or run.stderr:
        raise ValueError("Video pixel decoding failed: " + path.name + " " + run.stderr)


def audit(root, case, diagnostic, omitted):
    root = Path(root)
    config = json.loads(need(root, "config.json", omitted).read_text())
    if config.get("case_id") != case or config.get("case", {}).get("case_id") != case:
        raise ValueError("Wrong exact delivery case")
    if not diagnostic:
        need(root, "capture-seal.json", omitted)
        need(root, "native-capture-report.json", omitted)
    sources = {name: sha(need(root, name, omitted)) for name in SOURCES}
    context = json.loads((root / "pass-context.json").read_text())
    if context.get("case_id") != case or context.get("statutory_subject") not in (
            "bicycle", "electric_bicycle", "electric_scooter"):
        raise ValueError("Cycle-pass source context differs")
    if context.get("reasonable_safety_judged") or context.get("legal_verdict") is not None:
        raise ValueError("Legal judgment must remain unresolved")
    actors, trace, frames, capture = (rows(root / name) for name in
        ("participant-poses.jsonl", "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl"))
    if any(len(stream) != 600 for stream in (actors, trace, frames, capture)):
        raise ValueError("Incomplete 600-frame delivery source")
    separations = []
    for i, (actor, state, frame, event) in enumerate(zip(actors, trace, frames, capture)):
        native = actor.get("frame")
        ego, cycle = actor.get("ego", {}), actor.get("cyclist", {})
        if (actor.get("video_frame") != i or frame.get("video_frame") != i or
                state.get("frame") != native or frame.get("native_frame") != native or
                event.get("original_frame") != native or
                abs(actor.get("time_s", -1) - frame.get("time_s", -2)) > 1e-4 or
                any(frame.get("camera_native_frames", {}).get(name) != native for name in CAMERAS)):
            raise ValueError("Delivery source actor/camera time join failed")
        if (ego.get("actor_id") == cycle.get("actor_id") or
                not ego.get("body_xy_m") or not cycle.get("body_xy_m") or
                "bicycle" not in cycle.get("blueprint_id", "") and "crossbike" not in cycle.get("blueprint_id", "")):
            raise ValueError("Delivery participant identity or body history differs")
        if event.get("world", {}).get("road_projection", {}).get("lane_id") not in (-1, -2):
            raise ValueError("Delivery lane readback differs")
        separations.append(ego["center_xy_m"][0] - cycle["center_xy_m"][0])
    overlap = [i for i, distance in enumerate(separations) if abs(distance) <= 4]
    completed = bool(overlap and separations[0] < -4 and separations[-1] > 4)
    if not completed:
        raise ValueError("Original passing motion incomplete")
    for name in CAMERAS:
        path = need(root, name + ".mkv", omitted)
        decode(path)
        sources[name + ".mkv"] = sha(path)
    return {"format": "c247014-independent-delivery-audit-v1", "case_id": case,
            "checks": list(CHECKS), "source_hashes": sources, "frames": 600,
            "pass_first_frame": overlap[0], "pass_last_frame": overlap[-1],
            "diagnostic_fixture": diagnostic, "original_native_observed": not diagnostic,
            "display_pixels_reviewed": False, "physical_acceptance": False,
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    for name in ("attempt", "case", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit", default="")
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic, args.omit)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "frames": result["frames"],
                      "physical_acceptance": False, "legal_verdict": None}))


if __name__ == "__main__":
    main()
