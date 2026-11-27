"""Independent saved-source checks for four exact protected-lane contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, require, rows, sha

ROOT = Path(__file__).resolve().parent
CHANGES = {"lane_edge_intrusion": {"ego_path"},
           "lane_intrusion_depth": {"ego_path"},
           "protected_vehicle_class": {"protected_kind"},
           "driven_activation": {"protected_driven"}}


def compare(comparison_id, left, right):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = [item for item in plan["comparisons"] if item["comparison_id"] == comparison_id]
    require(len(selected) == 1 and comparison_id in CHANGES, "Unknown exact comparison")
    pair = selected[0]["case_ids"]
    roots = (Path(left).resolve(), Path(right).resolve())
    evidence = [audit(root, cid) for root, cid in zip(roots, pair)]
    require(evidence[0]["native_source"] == evidence[1]["native_source"],
            "Comparison mixes original and diagnostic sources")
    configs = [json.loads((root / "config.json").read_text()) for root in roots]
    scenes = [json.loads((root / "protected-lane-scene.json").read_text()) for root in roots]
    histories = [rows(root / "protected-lane-history.jsonl") for root in roots]
    require(configs[0]["cameras"] == configs[1]["cameras"] and
            configs[0]["engineering"] == configs[1]["engineering"] and
            configs[0]["duration_s"] == configs[1]["duration_s"] == 45 and
            configs[0]["rate_hz"] == configs[1]["rate_hz"] == 20,
            "Fixed capture or engineering conditions differ")
    keys = ("map_source_sha256", "lane_source_sha256", "highway_source_sha256",
            "protected_lane_center_xy", "protected_lane_width_m", "ego_width_m",
            "protected_width_m", "lane_ids")
    require(all(scenes[0]["site"].get(key) == scenes[1]["site"].get(key) for key in keys),
            "Fixed reviewed site or lane geometry differs")
    changed = CHANGES[comparison_id]
    for key in ("protected_kind", "ego_path", "protected_driven"):
        require((configs[0]["case"][key] != configs[1]["case"][key]) == (key in changed),
                "Declared difference or fixed case parameter differs: " + key)
    lateral = [sum(row["ego_xy"][1] for row in history) / 900 for history in histories]
    protected_motion = [sum(row["protected_speed_mps"] for row in history) / 900
                        for history in histories]
    if "ego_path" in changed:
        require(abs(lateral[0] - lateral[1]) > .5, "Ego path contrast not observed")
    if "protected_driven" in changed:
        require(abs(protected_motion[0] - protected_motion[1]) > .5,
                "Protected vehicle driven contrast not observed")
    if "protected_kind" in changed:
        require(histories[0][0]["protected_kind"] != histories[1][0]["protected_kind"],
                "Protected vehicle classification contrast not observed")
        if all(item["native_source"] for item in evidence):
            require(scenes[0]["site"]["motorcycle_class_source_sha256"] !=
                    scenes[1]["site"]["moped_class_source_sha256"],
                    "Independent class source contrast absent")
    return {"format": "c147339-comparison-audit", "comparison_id": comparison_id,
            "case_ids": pair, "source_sha256": [item["source_sha256"] for item in evidence],
            "construction_sha256": [sha(root / "construction.json") for root in roots],
            "declared_differences": sorted(changed), "fixed_conditions_checked": True,
            "observed_lateral_m": lateral, "observed_protected_speed_mps": protected_motion,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, args.left, args.right), sort_keys=True))
