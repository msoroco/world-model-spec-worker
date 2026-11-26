"""Independent CPU comparisons for the explicit stop and stand source branches."""
import argparse
import json
from pathlib import Path
import tempfile

from saved_angle_activity import measure

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name


def materialize(action, letter, folder):
    prefix = f"selected-{action}-{letter}"
    spec = json.loads((HERE / f"{prefix}-fixture.json").read_text())
    for name, content in spec["files"].items():
        if name in ("native_samples.jsonl", "body_history.jsonl", "video_frames.jsonl",
                    "official_device.json", "road_geometry.json", "parking_context.json"):
            (folder / name).write_text(content)
    construction = json.loads((HERE / f"{prefix}-construction.json").read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    (folder / "config.json").write_text(json.dumps(config) + "\n")
    return config


def run(action):
    if action not in ("stop", "stand"):
        raise ValueError("Unknown statutory action")
    activity = {"stop": "stopped", "stand": "standing"}[action]
    with tempfile.TemporaryDirectory(dir=HERE.parents[2] / ".runtime-work",
                                     prefix=f"c385967-{action}-compare-") as name:
        left, right = Path(name) / "a", Path(name) / "b"
        left.mkdir(); right.mkdir()
        config_a = materialize(action, "a", left)
        config_b = materialize(action, "b", right)
        for config, letter, heading in ((config_a, "a", 45), (config_b, "b", 70)):
            if (config.get("source_action_declaration"), config.get("observed_activity_request"),
                config.get("parked_heading_request_deg")) != (action, activity, heading):
                raise ValueError("Action or requested angle differs")
            if config.get("case_id") != ASSIGNMENT + f"__selected_03f318de__{action}_condition_{letter}":
                raise ValueError("Case identity differs")
        fixed = [dict(config) for config in (config_a, config_b)]
        for config in fixed:
            for key in ("case_id", "selected_case_id", "parked_heading_request_deg", "case"):
                config.pop(key, None)
        if fixed[0] != fixed[1]:
            raise ValueError("Comparison fixed setup differs")
        measured = [measure(folder, config["case_id"], allow_fixture=True)
                    for folder, config in ((left, config_a), (right, config_b))]
        for source in ("official_device.json", "road_geometry.json"):
            if measured[0]["source_hashes"][source] != measured[1]["source_hashes"][source]:
                raise ValueError("Governing device or curb source changed")
        angles = [item["mean_measured_angle_to_curb_deg"] for item in measured]
        if angles != [45, 70]:
            raise ValueError("At-rest angle contrast missing")
        altered = json.loads((right / "parking_context.json").read_text())
        altered["source_action_declaration"] = "park"
        (right / "parking_context.json").write_text(json.dumps(altered) + "\n")
        try:
            measure(right, config_b["case_id"], allow_fixture=True)
        except ValueError as exc:
            if "Source action context differs" not in str(exc):
                raise
            negative = str(exc)
        else:
            raise ValueError("Wrong action declaration accepted")
    receipt = {"format": "c385967-activity-comparison-v1", "action": action,
        "case_ids": [config_a["case_id"], config_b["case_id"]],
        "fixed_device_curb_camera_and_action": True,
        "measured_angles_to_curb_deg": angles,
        "source_hashes": [item["source_hashes"] for item in measured],
        "wrong_action_rejected": negative, "diagnostic_fixture": True,
        "original_physical_activity_verified": False, "legal_verdict": None}
    (HERE / f"{action}-comparison-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("stop", "stand"), required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.action), sort_keys=True))
