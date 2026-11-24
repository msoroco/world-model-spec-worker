"""Replay independent original-source comparisons for five selected cases."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from comparison_proof import (lane_change_direction, read, rows, signal_order,
                              target_lane_gap)
from lane_change_measurements import measure_exact_case
from late_lane_change_measurements import measure_exact_case as measure_late_case
from prove_delivery_acceptance import source_for


HERE = Path(__file__).resolve().parent
NAMES = ("left_signal_before_clear_gap", "left_signal_late_clear_gap",
         "left_wrong_signal_clear_gap", "left_signal_before_close_gap",
         "right_signal_before_clear_gap")
FILES = ("lane_context.json", "lane_history.jsonl", "video_frames.jsonl",
         "trace.jsonl", "capture/evidence.jsonl")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases():
    manifest = read(HERE / "execution-manifest.json")
    selected = {item["case_id"]: item for item in manifest["cases"]}
    cases = {}
    for name in NAMES:
        case_id = HERE.name + "__" + name
        entry = selected[case_id]
        attempt = source_for(name)
        receipt = read(attempt / "compatibility.json")
        if (receipt.get("passed") is not True or receipt.get("case_id") != case_id
                or receipt.get("candidate_id") != "primary"
                or receipt.get("construction_sha256") != entry["construction_sha256"]
                or receipt.get("runtime_manifest_sha256") != manifest["runtime_manifest_sha256"]):
            raise ValueError("Current primary source identity or runtime differs: " + name)
        source_hashes = {filename: sha(attempt / filename) for filename in FILES}
        if any(receipt["fixture_manifest"].get(filename) != digest
               for filename, digest in source_hashes.items()):
            raise ValueError("Original comparison source changed: " + name)
        measure = measure_late_case if name == "left_signal_late_clear_gap" else measure_exact_case
        cases[name] = {"case_id": case_id,
                       "context": read(attempt / "lane_context.json"),
                       "history": rows(attempt / "lane_history.jsonl"),
                       "frames": rows(attempt / "video_frames.jsonl"),
                       "trace": rows(attempt / "trace.jsonl"),
                       "capture": rows(attempt / "capture/evidence.jsonl"),
                       "measured": measure(attempt, case_id),
                       "source_sha256": source_hashes}
        if any(len(cases[name][field]) != 900 for field in ("history", "frames", "trace", "capture")):
            raise ValueError("Original comparison frame count differs")
    return cases


def audit(kind, negative=False):
    cases = load_cases()
    clear, late, wrong, close, right = (cases[name] for name in NAMES)
    if kind == "signal_order":
        members = [clear, late, wrong]
        function = signal_order
        mutation = lambda candidate: candidate["capture"][0]["ego"]["position_m"].__setitem__(0, -99)
    elif kind == "target_lane_gap":
        members = [clear, close]
        function = target_lane_gap
        mutation = lambda candidate: candidate["history"][0]["target_lane_bodies"][0]["body_vertices_xy_m"][0].__setitem__(0, -99)
    else:
        members = [clear, right]
        function = lane_change_direction
        mutation = lambda candidate: candidate["history"][0]["ego_body_vertices_xy_m"][0].__setitem__(1, -99)
    if negative:
        members = copy.deepcopy(members)
        mutation(members[1])
    measured = function(*members)
    return {"format": "worker-c144550-original-comparison-audit",
            "comparison_id": kind, "case_ids": [item["case_id"] for item in members],
            "source_sha256": {item["case_id"]: item["source_sha256"] for item in members},
            "measured_diagnostic_contrast": measured,
            "synthetic_fixture": True, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=("signal_order", "target_lane_gap", "lane_change_direction"), required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.negative), sort_keys=True))
