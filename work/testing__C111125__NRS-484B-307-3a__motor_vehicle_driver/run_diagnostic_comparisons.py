"""Independently compare saved diagnostic contrasts without legal labels."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import PAIRS, audit_pair
from dual_green import measure_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(attempt):
    root = Path(attempt).resolve()
    site = json.loads((root / "site.json").read_text())
    config = json.loads((root / "config.json").read_text())
    event = root / "original-events.json"
    measured = measure_original(site, root, {"path": event.name,
                                            "sha256": sha(event)})
    sources = {item["path"]: item["sha256"] for item in site["original_sources"]}
    identity = {"map_sha256": sources[site["map_source_path"]],
                "route_sha256": sources[site["route_source_path"]],
                "signal_survey_sha256": sources[site["signal_survey_path"]],
                "crosswalk_sha256": sources[site["crosswalk_source_path"]],
                "movement_permission_sha256": sources[site["movement_permission_source_path"]],
                "camera_profile_sha256": hashlib.sha256(json.dumps({
                    "fps": config["fps"], "cameras": config["cameras"]},
                    sort_keys=True).encode()).hexdigest(),
                "duration_frames": len(measured["records"]),
                "official_head_id": site["official_head_id"],
                "ego_approach_id": site["ego_approach_id"],
                "arrow_direction": site["arrow_direction"]}
    return {**identity, **measured,
            "case_suffix": config["selected_case_id"].split("__")[-1],
            "source_sha256": {"site.json": sha(root / "site.json"),
                              "original-events.json": sha(event)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    attempts = {Path(path).name.split("__")[-1]: load(path) for path in args.attempt}
    by_suffix = {record["case_suffix"]: record for record in attempts.values()}
    if len(by_suffix) != 4:
        raise ValueError("four exact diagnostic cases required")
    results = []
    for comparison, (left, right, _, _) in PAIRS.items():
        checked = audit_pair(comparison, by_suffix[left], by_suffix[right])
        checked["source_sha256"] = {left: by_suffix[left]["source_sha256"],
                                    right: by_suffix[right]["source_sha256"]}
        checked["diagnostic_only"] = True
        results.append(checked)
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain prior comparison receipt")
    output.write_text(json.dumps({"format": "dual-green-diagnostic-comparisons",
                                  "comparisons": results,
                                  "physical_acceptance_claimed": False}, indent=2) + "\n")


if __name__ == "__main__":
    main()
