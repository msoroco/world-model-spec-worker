"""Exercise the independent audit with a full-length synthetic capture.

The diagnostic result can prove software checks only; it cannot enter a set.
"""

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.media import compose_four_views
from worker_exchange.native_output import physical_result
from delivery_audit import CAMERAS, audit_attempt, sha


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def source(case_id):
    manifest = json.loads((FOLDER / "review-draft-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == case_id)
    recipe = json.loads((REPO / entry["fixture_recipe"]).read_text())
    data = json.loads((REPO / recipe["generator"]["source"]).read_text())
    construction = FOLDER / entry["construction"]
    if sha(construction) != entry["construction_sha256"]:
        raise ValueError("Exact construction changed")
    package = json.loads(construction.read_text())
    config = json.loads(next(item["content"] for item in package["files"]
                             if item["path"] == "config.json"))
    return config, data


def build(case_id, root):
    if root.exists():
        raise ValueError("Use a fresh diagnostic proof root")
    config, data = source(case_id)
    if config["selected_case_id"] != case_id:
        raise ValueError("Construction case differs")
    attempt = root / "attempt"
    attempt.mkdir(parents=True)
    write(attempt / "config.json", config)
    (attempt / "junction_context.json").write_text(data["files"]["junction_context.json"])
    write(attempt / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "scope": "CPU full-decode software check; no physical recording"})
    original = [json.loads(line) for line in data["files"]["vehicle_signal_history.jsonl"].splitlines()]
    count = config["rate_hz"] * config["duration_s"]
    start = original[0]["frame"]
    history, mapping, trace = [], [], []
    for index in range(count):
        row = copy.deepcopy(original[min(index, len(original) - 1)])
        frame, time_s = start + index, round((index + 1) / config["rate_hz"], 6)
        row["frame"], row["time_s"] = frame, time_s
        if index >= len(original):
            # Diagnostic projection crosses and clears the authored polygon.
            # The jump is not offered as a physical CARLA motion claim.
            for vertex in row["ego"]["body_vertices_xy_m"]:
                vertex[0] += 20
            row["ego"]["speed_mps"] = 0.0
        history.append(row)
        mapping.append({"video_frame": index, "carla_frame": frame, "time_s": time_s})
        trace.append({"frame": frame, "time_s": time_s, "case_id": case_id})
    for name, lines in (("vehicle_signal_history.jsonl", history),
                        ("video_frames.jsonl", mapping), ("trace.jsonl", trace)):
        (attempt / name).write_text("".join(json.dumps(line, separators=(",", ":")) + "\n"
                                               for line in lines))
    write(attempt / "converted/trace.json", {
        "scenes": [{"t": round(row["time_s"] * 1000)} for row in mapping]})
    result = physical_result(attempt, {"case_id": case_id, "target_checks": [],
        "realized_observables": {}, "setup_confirmed": False,
        "behavior_attempted": False, "maneuver_completed": False})
    if (result["physical_checks"]["setup"]["status"] != "met"
            or result["physical_checks"]["maneuver"]["status"] != "met"
            or not result["realized_observables"]
            or result["physical_acceptance_claimed"] is not False):
        raise ValueError("Synthetic physical-completion checker did not pass")
    write(attempt / "result.json", result)
    dimensions = {"overview": (1920, 1080), "approach": (1280, 720),
                  "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
    for name, (width, height) in dimensions.items():
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-vf", "drawbox=x=20:y=20:w=64:h=64:color=red:t=fill",
                        "-frames:v", str(count), "-c:v", "ffv1", "-pix_fmt", "yuv444p",
                        str(attempt / (name + ".mkv"))], check=True)
    compose_four_views({name: attempt / (name + ".mkv") for name in CAMERAS},
                       attempt / "video_frames.jsonl", attempt / "raw.mkv")
    sealed = {name: sha(attempt / name) for name in
              ("config.json", "trace.jsonl", "vehicle_signal_history.jsonl",
               "video_frames.jsonl", "junction_context.json",
               *(name + ".mkv" for name in CAMERAS))}
    write(attempt / "capture-seal.json", {
        "format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "frames": count, "sources": sealed,
        "events": ["capture_finished", "encoders_closed", "restoration_verified"],
        "physical_acceptance_claimed": False})
    write(attempt / "native-exit.json", {
        "event": "native_exit", "capture_seal_sha256": sha(attempt / "capture-seal.json")})
    write(attempt / "owner-release.json", {
        "event": "owner_released", "operator_attested": True,
        "native_exit_sha256": sha(attempt / "native-exit.json"),
        "diagnostic_fixture": True})
    write(root / "pixel-review.json", {
        "case_id": case_id, "reviewer": "synthetic CPU fixture generator",
        "method": "test pattern pixel ROI only; no real vehicle identification",
        "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
        "source_sha256": {name: sha(attempt / (name + ".mkv")) for name in CAMERAS},
        "observations": [{"camera": name, "video_frame": 0, "actor": actor,
                          "bbox_xyxy": [0, 0, dimensions[name][0], dimensions[name][1]]}
                         for name in CAMERAS for actor in ("ego", "other")]})
    return attempt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--negative-source-root", type=Path)
    parser.add_argument("--negative-missing-source", action="store_true")
    args = parser.parse_args()
    root = args.output_root.resolve()
    if args.negative_source_root:
        if not args.negative_missing_source or root.exists():
            raise ValueError("Fresh negative root and missing-source mode required")
        source_root = args.negative_source_root.resolve()
        if not (source_root / "attempt/diagnostic-audit.json").is_file():
            raise ValueError("Completed positive source required")
        attempt = root / "attempt"
        attempt.mkdir(parents=True)
        for file in (source_root / "attempt").rglob("*"):
            if file.is_file() and file.name != "vehicle_signal_history.jsonl":
                target = attempt / file.relative_to(source_root / "attempt")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(file, target)
        shutil.copyfile(source_root / "pixel-review.json", root / "pixel-review.json")
    else:
        attempt = build(args.case, root)
    result = audit_attempt(attempt, args.case, "diagnostic-job", 1,
                           "diagnostic-recording", root / "pixel-review.json",
                           attempt / "diagnostic-audit.json", root / "source-decode.json",
                           diagnostic_selftest=True)
    if result["passed"] or not result["software_checks_passed"]:
        raise ValueError("Diagnostic fixture claimed physical delivery")
    print(json.dumps({"case_id": args.case, "software_checks_passed": True,
                      "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                      "audit_sha256": sha(attempt / "diagnostic-audit.json")}))


if __name__ == "__main__":
    main()
