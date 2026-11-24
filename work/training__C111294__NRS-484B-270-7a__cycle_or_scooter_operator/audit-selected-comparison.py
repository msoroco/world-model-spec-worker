"""Check fixed conditions and the declared rider-path difference from durable sources."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(negative=False):
    plan = read(HERE / "case-plan.json")
    manifest = read(HERE / "execution-manifest.json")
    comparison = plan["comparisons"][0]
    assert comparison["deliberate_differences"] == ["bicycle_path_intervention"]
    assert [x["case_id"] for x in manifest["cases"]] == comparison["case_ids"]
    roots = [HERE / "v2-primary" / case for case in ("witness_1", "witness_2")]
    fixed = ("sources/road.xodr", "sources/camera_context.json",
             "sources/video_frames.jsonl")
    for rel in fixed:
        if sha(roots[0] / rel) != sha(roots[1] / rel):
            raise ValueError("Fixed source changed: " + rel)
    descriptions = [read(root / "construction.json")["recording_description"] for root in roots]
    if descriptions[0] != descriptions[1]:
        raise ValueError("Fixed capture contract changed")
    configs = [json.loads(next(row["content"] for row in read(root / "construction.json")["files"]
                               if row["path"] == "config.json")) for root in roots]
    for key in ("rate_hz", "duration_s", "required_atoms", "source_packets", "knobs"):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError("Fixed configuration changed: " + key)
    interactions = [read(root / "sources/interaction.json") for root in roots]
    if negative:
        interactions[1]["frames"][0]["motor_vehicle"]["actor_id"] += 1
    frames = [x["frames"] for x in interactions]
    if any(len(rows) != 600 for rows in frames):
        raise ValueError("600-frame source missing")
    if any(frames[0][i]["bicycle"] != frames[1][i]["bicycle"] or
           frames[0][i]["motor_vehicle"] != frames[1][i]["motor_vehicle"] for i in range(75)):
        raise ValueError("Fixed pre-intervention participants changed")
    commands = [x["rider_command_declared"] for x in interactions]
    if commands != ["hold_before_motorist_crosses", "enter_before_motorist_crosses"]:
        raise ValueError("Declared rider intervention missing")
    brakes = [sum(bool(row["motor_vehicle"]["brake_applied"]) for row in rows)
              for rows in frames]
    if brakes[0] != 0 or brakes[1] <= 0:
        raise ValueError("Measured motorist response contrast missing")
    return {"format": "c111294-controlled-comparison-v1",
            "comparison_id": comparison["comparison_id"],
            "case_ids": comparison["case_ids"],
            "manifest_sha256": sha(HERE / "execution-manifest.json"),
            "fixed_source_sha256": {rel: sha(roots[0] / rel) for rel in fixed},
            "interaction_sha256": [sha(root / "sources/interaction.json") for root in roots],
            "fixed_pre_intervention_frames": 75,
            "measured_motor_brake_frames": brakes,
            "diagnostic_only": True, "intent_or_legal_verdict": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    result = audit(args.negative)
    path = HERE / "selected-v2/comparison.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "brake_frames": result["measured_motor_brake_frames"]}))


if __name__ == "__main__":
    main()
