import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit_pair


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_attempt(folder, kind):
    folder.mkdir()
    shutil.copy2(ROOT / "candidate-red-x-road.xodr", folder / "road.xodr")
    scene = json.loads((ROOT / "cases" / kind / "scene.json").read_text())
    (folder / "scene.json").write_text(json.dumps(scene))
    for name, data in (("highway.txt", "fixture highway"), ("device.txt", "fixture device"),
                       ("original-capture.bin", "fixture original acquisition")):
        (folder / name).write_text(data)
    descriptor = lambda name: {"source_path": name, "source_sha256": sha(folder / name),
                               "reviewer": "fixture", "source_citation": "fixture only"}
    packet = {"review_status": "reviewed",
              "highway": {**descriptor("highway.txt"), "status": "public_highway_reviewed"},
              "official_device": {**descriptor("device.txt"),
                  "device_kind": "official_overhead_lane_signal", "symbol": "red_x",
                  "faces_bus": True, "governed_lane_id": "red_lane",
                  "native_asset_blueprint_id": "fixture.red_x_asset"}}
    (folder / "source-review.json").write_text(json.dumps(packet))
    positions = {
        "adjacent_travel": [(-5.4, 0), (-5.4, 3)],
        "lateral_entry": [(-5.4, 0), (-3.9, 3)],
        "red_lane_stand": [(-1.8, 0), (-1.8, 0)],
        "red_lane_drive": [(-1.8, 0), (-1.8, 3)],
    }[kind]
    channels = {"bus-body-history.jsonl": [], "lane-signal-history.jsonl": [],
                "camera-frame-map.jsonl": []}
    for frame, (y, x) in enumerate(positions, 1):
        common = {"frame": frame, "elapsed_seconds": frame / 20,
                  "source_path": "original-capture.bin"}
        channels["bus-body-history.jsonl"].append({**common,
            "bus_footprint": [[x - 5, y - 1], [x + 5, y - 1],
                              [x + 5, y + 1], [x - 5, y + 1]]})
        channels["lane-signal-history.jsonl"].append({**common,
            "governed_lane_id": "red_lane", "lane_lateral_bounds_m": [-3.6, 0],
            "symbol": "red_x", "faces_bus": True,
            "official_device_source_sha256": sha(folder / "device.txt")})
        channels["camera-frame-map.jsonl"].append(dict(common))
    acquisition = {name: sha(folder / name) for name in
                   ("highway.txt", "device.txt", "original-capture.bin", "source-review.json",
                    "road.xodr")}
    for name, rows in channels.items():
        (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        acquisition[name] = sha(folder / name)
    (folder / "acquisition.json").write_text(json.dumps(acquisition))


class RedXComparisonAudit(unittest.TestCase):
    def test_realized_entry_and_driving_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive"):
                make_attempt(root / kind, kind)
            entry = audit_pair("red_x_lateral_entry", root / "adjacent_travel", root / "lateral_entry")
            self.assertEqual(entry["realized_changed_frames"], [2])
            drive = audit_pair("red_x_in_lane_driving", root / "red_lane_stand", root / "red_lane_drive")
            self.assertEqual(drive["realized_changed_frames"], [2])
            scene_path = root / "lateral_entry" / "scene.json"
            scene = json.loads(scene_path.read_text())
            scene["signal"]["lateral_m"] = -5.4
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "fixed condition"):
                audit_pair("red_x_lateral_entry", root / "adjacent_travel", root / "lateral_entry")

    def test_original_map_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root / "adjacent_travel", "adjacent_travel")
            make_attempt(root / "lateral_entry", "lateral_entry")
            (root / "lateral_entry" / "road.xodr").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "original map source"):
                audit_pair("red_x_lateral_entry", root / "adjacent_travel", root / "lateral_entry")


if __name__ == "__main__":
    unittest.main()
