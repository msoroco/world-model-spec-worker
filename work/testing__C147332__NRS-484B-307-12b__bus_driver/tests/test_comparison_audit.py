import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit_pair
from delivery_audit import audit_attempt


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
    (folder / "reviewed-context.json").write_text(json.dumps(packet))
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
        channels["camera-frame-map.jsonl"].append({**common,
            "camera_names": ["overview", "approach", "reference_corner", "driver_reference"]})
    acquisition = {name: sha(folder / name) for name in
                   ("highway.txt", "device.txt", "original-capture.bin", "reviewed-context.json",
                    "road.xodr")}
    for name, rows in channels.items():
        (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        acquisition[name] = sha(folder / name)
    (folder / "acquisition.json").write_text(json.dumps(acquisition))


class RedXComparisonAudit(unittest.TestCase):
    def test_diagnostic_delivery_decodes_all_four_original_videos_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / "lateral_entry"
            make_attempt(attempt, "lateral_entry")
            (attempt / "trace.jsonl").write_text("{}\n{}\n")
            (attempt / "video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame": n - 1, "carla_frame": n, "native_frame": n,
                "time_s": n / 20}) + "\n" for n in (1, 2)))
            (attempt / "carla_recorder.log").write_text("diagnostic recorder fixture\n")
            for name in ("sign-state-original.jsonl", "controller-history.jsonl"):
                (attempt / name).write_text("{}\n{}\n")
            movie = attempt / "overview.mkv"
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "color=c=red:s=64x36:r=20", "-frames:v", "2",
                            "-c:v", "ffv1", str(movie)], check=True, capture_output=True)
            for name in ("approach", "reference_corner", "driver_reference"):
                shutil.copy2(movie, attempt / (name + ".mkv"))
            acquisition = json.loads((attempt / "acquisition.json").read_text())
            for name in ("trace.jsonl", "video_frames.jsonl", "carla_recorder.log",
                         "sign-state-original.jsonl", "controller-history.jsonl",
                         "overview.mkv", "approach.mkv", "reference_corner.mkv",
                         "driver_reference.mkv"):
                acquisition[name] = sha(attempt / name)
            (attempt / "acquisition.json").write_text(json.dumps(acquisition))
            seal = {"format": "worker-sealed-capture", "provenance_kind": "diagnostic",
                    "diagnostic_fixture": True, "frames": 2,
                    "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                    "restoration": {"restored": True},
                    "encoder_exit_codes": {name: 0 for name in
                        ("overview", "approach", "reference_corner", "driver_reference")},
                    "sources": dict(acquisition)}
            (attempt / "capture-seal.json").write_text(json.dumps(seal))
            report = audit_attempt(attempt, diagnostic=True)
            self.assertEqual(report["decoded_frames"]["reference_corner"], 2)
            self.assertFalse(report["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "original Native"):
                audit_attempt(attempt)
            (attempt / "reference_corner.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                audit_attempt(attempt, diagnostic=True)

    def test_realized_entry_and_driving_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive"):
                make_attempt(root / kind, kind)
            entry = audit_pair("red_x_lateral_entry", root / "adjacent_travel", root / "lateral_entry", diagnostic=True)
            self.assertEqual(entry["realized_changed_frames"], [2])
            drive = audit_pair("red_x_in_lane_driving", root / "red_lane_stand", root / "red_lane_drive", diagnostic=True)
            self.assertEqual(drive["realized_changed_frames"], [2])
            scene_path = root / "lateral_entry" / "scene.json"
            scene = json.loads(scene_path.read_text())
            scene["signal"]["lateral_m"] = -5.4
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "fixed condition"):
                audit_pair("red_x_lateral_entry", root / "adjacent_travel", root / "lateral_entry", diagnostic=True)

    def test_original_map_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root / "adjacent_travel", "adjacent_travel")
            make_attempt(root / "lateral_entry", "lateral_entry")
            (root / "lateral_entry" / "road.xodr").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "original map source"):
                audit_pair("red_x_lateral_entry", root / "adjacent_travel", root / "lateral_entry", diagnostic=True)


if __name__ == "__main__":
    unittest.main()
