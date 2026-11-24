"""Exercise selected independent delivery audit on an exact CPU fixture.

This proves source checks and a negative rejection, not Native or legal acceptance.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / ".runtime-work"
requested = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not requested.is_relative_to(OUTPUT_ROOT.resolve()):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE))
from check_source_fixture import build
from delivery_audit import CAMERAS, PREFIX, audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_sources(source, target):
    target.mkdir()
    for name in ("config.json", "result.json", "analysis-report.json",
                 "entry_history.jsonl", "video_frames.jsonl",
                 "intersection_context.json", "site_review.json"):
        shutil.copy2(source / name, target / name)
    if (source / "officer_review.json").is_file():
        shutil.copy2(source / "officer_review.json", target / "officer_review.json")
    for name in CAMERAS:
        (target / (name + ".mkv")).symlink_to((source / (name + ".mkv")).resolve())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=("positive", "negative"), required=True)
    args = parser.parse_args()
    manifest_path = PACKAGE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    matches = [e for e in manifest["cases"] if e["case_id"] == args.case]
    if len(matches) != 1 or not args.case.startswith(PREFIX):
        raise ValueError("Selected exact delivery case missing")
    entry = matches[0]
    if sha(PACKAGE / entry["construction"]) != entry["construction_sha256"]:
        raise ValueError("Exact selected construction changed")
    kind = args.case.removeprefix(PREFIX)
    OUTPUT_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_ROOT, prefix="c158208-delivery-proof-") as directory:
        temp = Path(directory)
        source = build(kind, temp / "source", manifest=manifest_path)
        selection = json.loads((source / "candidate-selection.json").read_text())
        if (selection.get("case_id") != args.case
                or selection.get("candidate_id") != "primary"
                or selection.get("construction_sha256") != entry["construction_sha256"]):
            raise ValueError("Diagnostic acquisition selected another construction")
        target = temp / "audit"
        copy_sources(source, target)
        if args.mode == "negative":
            with (target / "video_frames.jsonl").open("a") as stream:
                stream.write("{}\n")
            try:
                audit(target, args.case, diagnostic_fixture=True)
            except ValueError as error:
                if "Original analysis source changed: video_frames.jsonl" not in str(error):
                    raise
                raise ValueError("Original analysis source changed: video_frames.jsonl") from error
            raise ValueError("Changed original frame source was accepted")
        result = audit(target, args.case, diagnostic_fixture=True)
        if (result["original_frames"] != 3
                or result["physical_acceptance_claimed"] is not False):
            raise ValueError("CPU diagnostic claimed physical acceptance")
        sample = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(target / "approach.mkv"),
             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if sample.returncode or len(sample.stdout) != 1280 * 720 * 3:
            raise ValueError("Diagnostic source pixels could not be decoded")
        try:
            audit(target, args.case, diagnostic_fixture=False)
        except ValueError as error:
            if "600-frame" not in str(error):
                raise
        else:
            raise ValueError("Short synthetic source passed Native delivery check")
        print(json.dumps({"case_id": args.case, "diagnostic_frames": 3,
                          "source_audit_passed": True, "pixel_decode_passed": True,
                          "native_short_capture_rejected": True,
                          "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
