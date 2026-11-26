"""CPU fixture for positive and mutated-source independent audit paths."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))

from delivery_audit import audit, sha
from pixel_checks import check as pixel_check


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    suffix = args.case.rsplit("__", 1)[-1]
    if args.case != ROOT.name + "__" + suffix:
        raise ValueError("audit probe exact assignment mismatch")
    if not Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    source = REPO / ".runtime-work/c150088-nov26/saved-proofs-v2" / (suffix + "-attempt")
    saved = REPO / ".runtime-work/c150088-nov26/saved-proofs-v2" / (suffix + "-output/v0001/processing.json")
    output = Path(args.output).resolve()
    if not output.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("audit fixture belongs under .runtime-work")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    result["physical_checks"]["maneuver"]["status"] = "met"
    result["maneuver_completed"] = True
    write(output / "result.json", result)
    write(output / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                                   "diagnostic_fixture": True})
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    required = ("original-projection-history.jsonl", "camera-frame-map.jsonl", "trace.jsonl",
                "video_frames.jsonl", "road.xodr", "overview.mkv", "approach.mkv",
                "reference_corner.mkv", "driver_reference.mkv")
    seal = {"format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "frames": 9,
            "restoration": {"restored": True}, "encoder_exit_codes": {"fixture": 0},
            "sources": {name: sha(output / name) for name in required},
            "native_revision": {"construction_sha256": sha(output / "construction.json"),
                                "runner_sha256": sha(output / "runner.py")},
            "events": ["capture_finished", "encoders_closed", "restoration_verified"]}
    write(output / "capture-seal.json", seal)
    record_native_exit(output)
    acknowledge_owner_release(output, output / "owner-release.json", True)
    saved_receipt = json.loads(saved.read_text(encoding="utf-8"))
    video_dir = output / "cpu-analysis"
    video_dir.mkdir()
    video = video_dir / "raw.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=20",
                    "-frames:v", "9", "-c:v", "ffv1", "-pix_fmt", "yuv444p",
                    str(video)], check=True, timeout=60)
    saved_receipt["analysis_directory"] = str(video_dir)
    saved_receipt["result"] = str(output / "result.json")
    saved_receipt["result_sha256"] = sha(output / "result.json")
    processing = output / "cpu-processing-fixture.json"
    write(processing, saved_receipt)
    from worker_exchange.media import audit as decode
    decode_path = output / "cpu-decode.json"
    decode(video, 9, checkers={"pixel_presence": (sha(ROOT / "pixel_checks.py"), pixel_check)},
           mapping_sha256=sha(output / "video_frames.jsonl"), receipt=decode_path)
    required_objects = ["curb_line", "vehicle_outer_edge", "controlling_part_outer_edge"]
    if suffix == "load_above":
        required_objects.append("load_attachment")
    if suffix == "trailer_above":
        required_objects.append("trailer_hitch")
    write(output / "visibility-review.json", {"reviewer": "synthetic CPU fixture",
         "synthetic_fixture": True, "video_sha256": sha(video),
         "frame_map_sha256": sha(output / "video_frames.jsonl"),
         "visible_objects": required_objects})
    if args.negative:
        with (output / "original-projection-history.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("{}\n")
    print(json.dumps(audit(output, processing, decode_path, args.case,
                           synthetic_fixture=True), indent=2))


if __name__ == "__main__":
    main()
