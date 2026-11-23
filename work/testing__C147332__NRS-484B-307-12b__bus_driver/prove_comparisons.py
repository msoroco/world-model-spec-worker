"""Run both exact red-X comparison audits on retained synthetic CPU attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from comparison_audit import audit_pair


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive")
PAIRS = (("red_x_lateral_entry", "adjacent_travel", "lateral_entry"),
         ("red_x_in_lane_driving", "red_lane_stand", "red_lane_drive"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    pipeline_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    for path in (pipeline_root, source, output):
        if not path.is_relative_to((REPO / ".runtime-work").resolve()):
            raise ValueError("diagnostic sources and output must stay under .runtime-work")
    if output.exists():
        raise ValueError("choose fresh proof output")
    output.mkdir(parents=True)
    bindings = {}
    for kind in KINDS:
        origin, attempt = source / kind / "primary", output / kind
        shutil.copytree(origin, attempt)
        acquisition = json.loads((attempt / "acquisition.json").read_text())
        acquisition["road.xodr"] = sha(attempt / "road.xodr")
        write(attempt / "acquisition.json", acquisition)
        bindings[kind] = {"scene_sha256": sha(attempt / "scene.json"),
                          "original_map_sha256": sha(attempt / "road.xodr"),
                          "acquisition_sha256": sha(attempt / "acquisition.json")}
    results = []
    for pair, left, right in PAIRS:
        result = audit_pair(pair, output / left, output / right, diagnostic=True)
        if not result["realized_changed_frames"] or result["realized_baseline_frames"]:
            raise AssertionError("missing measured red-X contrast")
        results.append(result)
        print(pair, "diagnostic contrast", result["realized_changed_frames"])
    scene_path = output / "lateral_entry" / "scene.json"
    original = scene_path.read_bytes()
    scene = json.loads(original)
    scene["signal"]["lateral_m"] += 1
    write(scene_path, scene)
    try:
        audit_pair(*PAIRS[0][:1], output / "adjacent_travel", output / "lateral_entry",
                   diagnostic=True)
    except ValueError as error:
        if "fixed condition changed" not in str(error):
            raise
        print("fixed-condition tamper rejected")
    else:
        raise AssertionError("changed signal passed comparison audit")
    scene_path.write_bytes(original)
    signal_path = output / "lateral_entry" / "lane-signal-history.jsonl"
    original_signal = signal_path.read_bytes()
    rows = [json.loads(line) for line in original_signal.splitlines()]
    rows[0]["faces_bus"] = False
    signal_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    acquisition_path = output / "lateral_entry" / "acquisition.json"
    original_acquisition = acquisition_path.read_bytes()
    acquisition = json.loads(original_acquisition)
    acquisition[signal_path.name] = sha(signal_path)
    write(acquisition_path, acquisition)
    try:
        audit_pair(PAIRS[0][0], output / "adjacent_travel", output / "lateral_entry",
                   diagnostic=True)
    except ValueError as error:
        if "observed red-X signal condition changed" not in str(error):
            raise
        print("rehashed observed-signal tamper rejected")
    else:
        raise AssertionError("changed observed signal passed comparison audit")
    signal_path.write_bytes(original_signal)
    acquisition_path.write_bytes(original_acquisition)
    map_path = output / "red_lane_drive" / "road.xodr"
    original_map = map_path.read_bytes()
    map_path.write_bytes(original_map + b"\nchanged\n")
    try:
        audit_pair(PAIRS[1][0], output / "red_lane_stand", output / "red_lane_drive",
                   diagnostic=True)
    except ValueError as error:
        if "original map source changed" not in str(error):
            raise
        print("original-map tamper rejected")
    else:
        raise AssertionError("changed original map passed comparison audit")
    map_path.write_bytes(original_map)
    write(ROOT / "comparison-diagnostic-proof.json", {
        "format": "worker-red-x-comparison-diagnostic-proof",
        "source_root": str(source.relative_to(REPO)), "bindings": bindings,
        "results": results, "negative_checks": ["fixed-condition tamper rejected",
                                                 "rehashed observed-signal tamper rejected",
                                                 "original-map tamper rejected"],
        "provenance_kind": "synthetic_fixture", "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False})


if __name__ == "__main__":
    main()
