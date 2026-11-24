"""Exact-case synthetic positive and original-source tamper audit protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from delivery_audit import CAMERAS, ORIGINALS, audit_attempt


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
KINDS = {"adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--source", default=".runtime-work/c147332-compat-v5")
    args = parser.parse_args()
    kind = args.case.removeprefix(ASSIGNMENT + "__")
    if args.case != ASSIGNMENT + "__" + kind or kind not in KINDS:
        raise ValueError("wrong exact red-X case")
    pipeline_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    attempt = Path(args.output).resolve()
    for path in (pipeline_root, attempt):
        if not path.is_relative_to((REPO / ".runtime-work").resolve()):
            raise ValueError("diagnostic output must stay under .runtime-work")
    if args.negative:
        if not attempt.is_dir():
            raise ValueError("run exact positive fixture first")
        source = attempt / "lane-signal-history.jsonl"
        source.write_bytes(source.read_bytes() + b"\nchanged original source\n")
        audit_attempt(attempt, diagnostic=True)
        raise AssertionError("changed original signal passed independent delivery audit")
    if attempt.exists():
        raise ValueError("choose a fresh exact diagnostic attempt")
    source = Path(args.source).resolve() / kind
    if (source / "primary").is_dir():
        source /= "primary"
    if not source.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("diagnostic source must stay under .runtime-work")
    shutil.copytree(source, attempt)
    (attempt / "carla_recorder.log").write_text("diagnostic recorder log\n")
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    for name in ORIGINALS:
        if not (attempt / name).is_file():
            raise ValueError("diagnostic original-shaped source missing: " + name)
        acquisition[name] = sha(attempt / name)
    write(attempt / "acquisition.json", acquisition)
    seal = {"format": "worker-sealed-capture", "provenance_kind": "diagnostic",
            "diagnostic_fixture": True, "frames": 5,
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "restoration": {"restored": True},
            "encoder_exit_codes": {name: 0 for name in CAMERAS},
            "sources": {name: item.get("sha256") if isinstance(item, dict) else item
                        for name, item in acquisition.items()}}
    write(attempt / "capture-seal.json", seal)
    report = audit_attempt(attempt, diagnostic=True)
    if report["physical_acceptance_claimed"] or set(report["decoded_frames"]) != set(CAMERAS):
        raise AssertionError("diagnostic audit claims physical success or misses a camera")
    try:
        audit_attempt(attempt)
    except ValueError as error:
        if "original Native" not in str(error):
            raise
    else:
        raise AssertionError("synthetic attempt passed Native delivery audit")
    print(args.case, "diagnostic full-source/four-camera audit passed")
    print("native provenance rejected; physical acceptance false")


if __name__ == "__main__":
    main()
