"""Exercise independent audit with clearly synthetic, source-bound CPU evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

from delivery_audit import audit
from analysis import SOURCES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    command = shlex.split(entry["compatibility"]["command"])
    source = Path(command[command.index("--output") + 1]).resolve()
    output = Path(args.output).resolve()
    if not output.is_relative_to(REPO / ".runtime-work") or output.exists():
        raise ValueError("Use a fresh diagnostic output under .runtime-work")
    output.mkdir(parents=True)
    names = [*SOURCES, "config.json", "construction.json", "acquisition.json",
             "acquisition-provenance.json", "result.json",
             "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"]
    for name in names:
        shutil.copyfile(source / name, output / name)
    count = len((output / "trace.jsonl").read_text().splitlines())
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        video = output / (name + ".mkv")
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-count_frames",
            "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "json", str(video)], text=True))
        if int(probe["streams"][0]["nb_read_frames"]) != count:
            raise ValueError("diagnostic camera frame count differs")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
                        "-f", "null", "-"], check=True, stdout=subprocess.DEVNULL, timeout=120)
    seal = {"format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "restoration": {"restored": True},
            "sources": {name: sha(output / name) for name in names}}
    write(output / "capture-seal.json", seal)
    if args.negative:
        path = output / "ego-body-history.jsonl"
        path.write_text(path.read_text() + "\n")
        acquisition = json.loads((output / "acquisition.json").read_text())
        acquisition["ego-body-history.jsonl"]["sha256"] = sha(path)
        write(output / "acquisition.json", acquisition)
    result = audit(output, diagnostic_test=True)
    if not result["diagnostic_audit_test_passed"] or result["delivery_physical_audit_passed"]:
        raise AssertionError("Diagnostic audit incorrectly claims delivery acceptance")
    print(json.dumps({"case_id": args.case, "diagnostic_audit_test_passed": True,
                      "full_camera_decode_count": 4, "actual_carla_capture_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
