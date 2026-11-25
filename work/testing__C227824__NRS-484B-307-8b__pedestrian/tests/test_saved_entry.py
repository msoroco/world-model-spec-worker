import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("c227824_saved_entry", ROOT / "saved_entry.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = "testing__C227824__NRS-484B-307-8b__pedestrian__red_no_device_entry"


def _write(root, name, value):
    path = root / name
    if isinstance(value, bytes):
        path.write_bytes(value)
    elif name.endswith(".jsonl"):
        path.write_text("".join(json.dumps(row) + "\n" for row in value))
    else:
        path.write_text(json.dumps(value) + "\n")


def make_attempt(root):
    outside = [[-2, 3], [-1, 3], [-1, 4], [-2, 4]]
    inside = [[1, 3], [2, 3], [2, 4], [1, 4]]
    _write(root, "scene.json", {"law_id": "NRS-484B-307-8b", "cell_id": "C227824",
                                "actor": "pedestrian", "case_id": CASE,
                                "map_source_sha256": "a" * 64,
                                "facing_head_id": 5,
                                "walker_blueprint_id": "walker.pedestrian.test",
                                "route_id": "crossing-1", "camera_placements": {"views": 4},
                                "entry_request": "entry",
                                "requested_pedestrian_indication": "none",
                                "highway_polygon_xy_m": [[0, 0], [8, 0], [8, 8], [0, 8]]})
    _write(root, "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                                  "diagnostic_fixture": True})
    bodies = []
    signals = []
    devices = []
    mapping = []
    joins = []
    for i in range(3):
        frame, time_s = i + 1, (i + 1) * .05
        common = {"frame": frame, "time_s": time_s, "case_id": CASE}
        bodies.append({**common, "body_polygon_xy_m": outside if i == 0 else inside})
        signals.append({**common, "facing_traffic_signal": {"official": True,
                                                              "indication": "steady_red_alone"}})
        devices.append({**common, "other_devices": []})
        mapping.append({"video_frame": i, "carla_frame": frame, "time_s": time_s})
        joins.append({**common, "cameras": {name: {"frame": frame} for name in MODULE.CAMERAS}})
    for name, rows in zip(MODULE.PACKETS, (bodies, signals, devices, mapping, joins)):
        _write(root, name, rows)
    for name in MODULE.CAMERAS:
        _write(root, name + ".mkv", b"synthetic bytes; not a decoded video")
    names = ("scene.json", *MODULE.PACKETS, *(name + ".mkv" for name in MODULE.CAMERAS))
    _write(root, "acquisition.json", {name: {"sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
                                      for name in names})


class SavedEntryTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.root = Path(self.temp.name)
        make_attempt(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_joins_and_measures_synthetic_sources_without_acceptance_claim(self):
        report = MODULE.build_report(self.root)
        self.assertEqual(report["measurement"]["first_entry"]["frame"], 2)
        self.assertTrue(report["diagnostic_fixture"])
        self.assertFalse(report["actual_pixels_verified"])
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertEqual(report["map_sha256"], "a" * 64)
        self.assertEqual(report["entry_request"], "entry")
        self.assertEqual(report["planned_device_indication"], "none")

    def test_rejects_changed_source_hash(self):
        with (self.root / "signal-history.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "saved source hash mismatch"):
            MODULE.build_report(self.root)

    def test_rejects_missing_device_packet(self):
        (self.root / "device-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "missing saved source"):
            MODULE.build_report(self.root)

    def test_rejects_misaligned_camera_and_signal_frames(self):
        path = self.root / "camera-frame-joins.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["cameras"]["approach"]["frame"] = 3
        _write(self.root, path.name, rows)
        manifest = json.loads((self.root / "acquisition.json").read_text())
        manifest[path.name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        _write(self.root, "acquisition.json", manifest)
        with self.assertRaisesRegex(ValueError, "four original camera joins"):
            MODULE.build_report(self.root)


if __name__ == "__main__":
    unittest.main()
