"""Independent fixed-condition audit for five selected synthetic sweep cases.

The diagnostic setpoints are engineering variations; this auditor makes no
physical or legal safety judgment and must be rerun on original Native sources.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from prove_delivery_acceptance import source_for


HERE = Path(__file__).resolve().parent
FILES = ("lane_context.json", "video_frames.jsonl", "lane_history.jsonl",
         "trace.jsonl", "capture/evidence.jsonl")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    text = path.read_text()
    return json.loads(text) if path.suffix == ".json" else [json.loads(line) for line in text.splitlines() if line]


def normalize_signal(name, data):
    data = copy.deepcopy(data)
    if name == "lane_history.jsonl":
        for row in data:
            row.pop("indicator", None)
    elif name == "trace.jsonl":
        for row in data:
            row.pop("ego_lamp_bits", None)
    elif name == "capture/evidence.jsonl":
        for row in data:
            for person in row["original_observations"]["participants"]:
                person.get("light_attributes", {}).pop("light_LeftBlinker", None)
                person.get("light_attributes", {}).pop("light_RightBlinker", None)
    return data


def normalize_gap(name, data):
    data = copy.deepcopy(data)
    if name == "lane_history.jsonl":
        for row in data:
            for target in row["target_lane_bodies"]:
                target.pop("body_vertices_xy_m", None)
    elif name == "capture/evidence.jsonl":
        for row in data:
            target = row["original_observations"]["participants"][1]
            target.pop("position_m", None)
            target.pop("body_vertices_m", None)
    return data


def audit(kind, negative=False):
    if kind == "signal_lead_finite_sweep":
        suffixes = ["signal-appropriateness-pending-" + str(i).zfill(4) for i in range(3)]
        normalize = normalize_signal
        variable = "appropriate_signal_lead_frames"
        expected = [-1, 1, 0]
    else:
        suffixes = ["safety-ascertainment-pending-" + str(i).zfill(4) for i in range(2)]
        normalize = normalize_gap
        variable = "nearest_target_body_gap_at_departure_m"
        expected = [3, 8]
    cases = json.loads((HERE / "proposals/cases.json").read_text())["cases"]
    cases = {case["case_id"].split("__")[-1]: case for case in cases}
    paths = [source_for(suffix) for suffix in suffixes]
    for suffix, value in zip(suffixes, expected):
        actual = cases[suffix]["variable_assignments"][variable]["value"]
        if actual != value:
            raise ValueError("Selected sweep setpoint differs")
    hashes = {}
    for filename in FILES:
        observations = [load(path / filename) for path in paths]
        if negative and filename == "lane_history.jsonl":
            observations[-1][0]["ego_lane_id"] = 999
        if filename != "lane_context.json" and any(len(value) != 900 for value in observations):
            raise ValueError("Selected sweep original frame count differs")
        baseline = normalize(filename, observations[0])
        if any(normalize(filename, item) != baseline for item in observations[1:]):
            raise ValueError("Selected sweep changed fixed original fields: " + filename)
        hashes[filename] = {suffix: digest(path / filename) for suffix, path in zip(suffixes, paths)}
    return {"format": "worker-c144550-finite-sweep-audit", "comparison_id": kind,
            "case_ids": [cases[suffix]["case_id"] for suffix in suffixes],
            "setpoints": dict(zip(suffixes, expected)), "variable": variable,
            "source_sha256": hashes, "original_frames": 900,
            "synthetic_fixture": True, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=("signal_lead_finite_sweep", "target_gap_finite_sweep"), required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.negative), sort_keys=True))
