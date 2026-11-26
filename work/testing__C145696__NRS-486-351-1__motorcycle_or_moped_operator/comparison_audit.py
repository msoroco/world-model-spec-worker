"""Independent source-bound audit of the six exact adjacent-lane contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, require, rows, sha

ROOT = Path(__file__).resolve().parent


def compare(comparison_id, left_path, right_path):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = [item for item in plan["comparisons"] if item["comparison_id"] == comparison_id]
    require(len(selected) == 1, "Unknown exact comparison")
    pair = selected[0]["case_ids"]
    roots = (Path(left_path).resolve(), Path(right_path).resolve())
    audited = [audit(root, cid) for root, cid in zip(roots, pair)]
    require(audited[0]["native_source"] == audited[1]["native_source"],
            "Comparison mixes original and diagnostic sources")
    require(all(item["all_participants"] and item["time_join"] and
                item["full_video_decode"] for item in audited),
            "Comparison source audit incomplete")
    configs = [json.loads((root / "config.json").read_text()) for root in roots]
    scenes = [json.loads((root / "lane-split-scene.json").read_text()) for root in roots]
    histories = [rows(root / "lane-split-history.jsonl") for root in roots]
    require(configs[0]["cameras"] == configs[1]["cameras"] and
            configs[0]["rate_hz"] == configs[1]["rate_hz"] == 20 and
            configs[0]["duration_s"] == configs[1]["duration_s"] == 45 and
            configs[0]["engineering"] == configs[1]["engineering"],
            "Camera, duration or engineering setup differs")
    require(scenes[0]["map_id"] == scenes[1]["map_id"] and
            scenes[0]["lanes"] == scenes[1]["lanes"] and
            scenes[0].get("opendrive_sha256") == scenes[1].get("opendrive_sha256"),
            "Map or adjacent lane pair differs")
    parameters = [config["case"] for config in configs]
    changed = {
        "left_vehicle_motion": {"left_motion"},
        "right_vehicle_motion": {"right_motion"},
        "joint_vehicle_motion": {"left_motion", "right_motion"},
        "passage_path": {"maneuver"},
        "police_duty_exception": {"performance_of_duty"},
        "vehicle_subtype": {"vehicle_class"},
    }[comparison_id]
    for key in ("left_motion", "right_motion", "maneuver", "vehicle_class",
                "operator_status", "performance_of_duty", "target_speed_mps"):
        if key in changed:
            require(parameters[0][key] != parameters[1][key],
                    "Declared difference not constructed: " + key)
        else:
            require(parameters[0][key] == parameters[1][key],
                    "Fixed scenario parameter differs: " + key)
    means = []
    for history in histories:
        means.append({role: sum(row["actors"][role]["speed_mps"] for row in history) / 900
                      for role in ("ego", "left_occupant", "right_occupant")})
    if "left_motion" in changed:
        require(abs(means[0]["left_occupant"] - means[1]["left_occupant"]) > .5,
                "Left occupant motion contrast not observed")
    if "right_motion" in changed:
        require(abs(means[0]["right_occupant"] - means[1]["right_occupant"]) > .5,
                "Right occupant motion contrast not observed")
    if comparison_id == "passage_path":
        lateral = [sum(row["actors"]["ego"]["lateral_m"] for row in history) / 900
                   for history in histories]
        require(abs(lateral[0] - lateral[1]) > .5,
                "Ego passage path contrast not observed")
    if comparison_id == "police_duty_exception":
        require(scenes[0]["operator_status"] == scenes[1]["operator_status"] == "police" and
                (not all(item["native_source"] for item in audited) or
                 scenes[0]["performance_of_duty_source_sha256"] !=
                 scenes[1]["performance_of_duty_source_sha256"]),
                "Independent duty source contrast not observed")
    if comparison_id == "vehicle_subtype":
        require(not all(item["native_source"] for item in audited) or
                scenes[0]["classification_source_sha256"] !=
                scenes[1]["classification_source_sha256"],
                "Independent chapter class source contrast not observed")
    return {"format": "c145696-comparison-audit", "comparison_id": comparison_id,
            "case_ids": pair, "source_sha256": [item["source_sha256"] for item in audited],
            "construction_sha256": [sha(root / "construction.json") for root in roots],
            "declared_differences": sorted(changed), "fixed_conditions_checked": True,
            "observed_speed_mps": means, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, args.left, args.right), sort_keys=True))


if __name__ == "__main__":
    main()
