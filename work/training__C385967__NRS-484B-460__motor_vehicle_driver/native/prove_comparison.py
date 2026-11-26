"""Test fixed conditions and missing-source rejection for angle comparison."""
import json
from pathlib import Path
import shutil
import tempfile

from comparison_audit import audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def copy_small(source, destination):
    destination.mkdir()
    for name in ("config.json", "native_samples.jsonl", "body_history.jsonl",
                 "video_frames.jsonl", "official_device.json", "road_geometry.json",
                 "parking_context.json"):
        shutil.copyfile(source / name, destination / name)


def prove():
    left = ROOT / ".runtime-work/c385967-compat-a2"
    right = ROOT / ".runtime-work/c385967-compat-b"
    positive = audit(left, right, allow_fixture=True)
    (HERE / "comparison-positive.json").write_text(json.dumps(positive,
        indent=2, allow_nan=False) + "\n")
    negative = {}
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work",
                                     prefix="c385967-comparison-") as name:
        changed = Path(name) / "changed"
        copy_small(right, changed)
        config_path = changed / "config.json"
        config = json.loads(config_path.read_text())
        config["cameras"][0]["fov_deg"] += 1
        config_path.write_text(json.dumps(config) + "\n")
        try:
            audit(left, changed, allow_fixture=True)
        except ValueError as error:
            if "fixed camera or scene" not in str(error):
                raise
            negative["camera_changed"] = str(error)
        else:
            raise AssertionError("Changed comparison camera accepted")
        shutil.copyfile(right / "config.json", config_path)
        device = changed / "official_device.json"
        doc = json.loads(device.read_text())
        doc["indicated_angle_to_curb_deg"] = 50
        device.write_text(json.dumps(doc) + "\n")
        try:
            audit(left, changed, allow_fixture=True)
        except ValueError as error:
            if "fixed device or curb" not in str(error):
                raise
            negative["device_changed"] = str(error)
        else:
            raise AssertionError("Changed comparison device accepted")
        device.unlink()
        try:
            audit(left, changed, allow_fixture=True)
        except ValueError as error:
            if "Missing required source: official_device" not in str(error):
                raise
            negative["device_missing"] = str(error)
        else:
            raise AssertionError("Missing comparison device accepted")
    (HERE / "comparison-negative.json").write_text(json.dumps(negative,
        indent=2, allow_nan=False) + "\n")
    return {"positive": True, "negative_rejections": negative,
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
