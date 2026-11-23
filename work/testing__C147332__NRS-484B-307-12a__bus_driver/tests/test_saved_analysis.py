"""Synthetic source custody tests; fixture sources are never official evidence."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import build_report
from comparison_audit import audit
from scene_construction import scene


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.write_text(value)
    return sha(path)


def fixture(root, *, bus_lane="east", green=("east",), moving=True, case_id=None):
    highway_hash = put(root / "synthetic-highway.txt", "synthetic public highway record\n")
    device_hash = put(root / "synthetic-device.txt", "synthetic green arrow over east lane\n")
    packet = {"review_status": "reviewed",
              "highway": {"source_path": "synthetic-highway.txt", "source_sha256": highway_hash,
                          "source_citation": "synthetic test fixture", "reviewer": "unit test only",
                          "status": "public_highway_reviewed", "highway_id": "fixture-highway"},
              "official_device": {"source_path": "synthetic-device.txt", "source_sha256": device_hash,
                                  "source_citation": "synthetic test fixture", "reviewer": "unit test only",
                                  "device_kind": "official_overhead_lane_signal",
                                  "symbol": "down_green_arrow", "faces_bus": True,
                                  "placement": "over_individual_lanes",
                                  "native_asset_blueprint_id": "fixture.signal",
                                  "dark_asset_blueprint_id": "fixture.dark",
                                  "governed_lane_ids": list(green)}}
    packet_hash = put(root / "reviewed-context.json", json.dumps(packet))
    acquisition = {"reviewed-context.json": packet_hash}
    channels = {name: [] for name in ("bus-body-history.jsonl", "lane-signal-history.jsonl",
                                      "camera-frame-map.jsonl")}
    for frame in range(3):
        t = frame / 20
        x = float(frame if moving else 0)
        y = 0 if bus_lane == "east" else 4
        payload = {"frame": frame, "elapsed_seconds": t}
        body = {**payload, "bus_footprint": [[x-1, y-1], [x+1, y-1],
                                               [x+1, y+1], [x-1, y+1]]}
        signal = {**payload, "highway_id": "fixture-highway",
                  "official_device_source_sha256": device_hash,
                  "faces_bus": True, "placement": "over_individual_lanes",
                  "lanes": [{"lane_id": "east", "direction": "bus_direction",
                             "lateral_bounds_m": [-2, 2],
                             "symbol": "down_green_arrow" if "east" in green else "dark"},
                            {"lane_id": "west", "direction": "bus_direction",
                             "lateral_bounds_m": [2, 6],
                             "symbol": "down_green_arrow" if "west" in green else "dark"}]}
        camera = {**payload, "camera_names": ["overview"]}
        for name, data, prefix in (("bus-body-history.jsonl", body, "body"),
                                   ("lane-signal-history.jsonl", signal, "signal"),
                                   ("camera-frame-map.jsonl", camera, "camera")):
            original = prefix + "-" + str(frame) + ".json"
            digest = put(root / original, json.dumps(data))
            acquisition[original] = digest
            channels[name].append({**data, "source_path": original, "source_sha256": digest})
    for name, rows in channels.items():
        acquisition[name] = put(root / name, "".join(json.dumps(row) + "\n" for row in rows))
    put(root / "acquisition.json", json.dumps(acquisition))
    if case_id:
        put(root / "scene.json", json.dumps(scene(case_id, "a" * 64)))
    return acquisition


class SavedAnalysisTests(unittest.TestCase):
    def test_source_bound_green_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            report = build_report(root)
            observed = report["measurements"]["green_arrow_bus_lane"]
            self.assertEqual(observed["permission_observed_frames"], [0, 1, 2])
            self.assertEqual(observed["bus_moving_frames"], [1, 2])
            self.assertFalse(report["physical_acceptance_claimed"])
            self.assertFalse(report["legal_verdict_claimed"])

    def test_changed_original_and_unreviewed_packet_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "body-1.json").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "row source missing or changed"):
                build_report(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            packet = json.loads((root / "reviewed-context.json").read_text())
            packet["review_status"] = "diagnostic"
            (root / "reviewed-context.json").write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "review not completed"):
                build_report(root)

    def test_green_lane_and_acquisition_binding_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            acquisition = fixture(root)
            rows = [json.loads(s) for s in (root / "lane-signal-history.jsonl").read_text().splitlines()]
            rows[1]["lanes"][0]["symbol"] = "dark"
            acquisition["lane-signal-history.jsonl"] = put(
                root / "lane-signal-history.jsonl", "".join(json.dumps(row) + "\n" for row in rows))
            put(root / "acquisition.json", json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "observed green lanes differ"):
                build_report(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            acquisition = fixture(root)
            acquisition["reviewed-context.json"] = "0" * 64
            put(root / "acquisition.json", json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "not bound"):
                build_report(root)

    def test_source_bound_comparison_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b, c, d = (root / name for name in ("dark", "second", "drive", "stand"))
            for path in (a, b, c, d):
                path.mkdir()
            fixture(a, bus_lane="west", case_id="adjacent_dark_drive")
            fixture(b, bus_lane="west", green=("east", "west"), case_id="second_green_drive")
            fixture(c, case_id="green_selected_drive")
            fixture(d, moving=False, case_id="green_selected_stand")
            # The synthetic text is shared to exercise source binding only.
            self.assertTrue(audit(a, b, "second_green_arrow")["source_bound"])
            self.assertTrue(audit(c, d, "permission_without_motion")["source_bound"])
            with self.assertRaisesRegex(ValueError, "wrong exact comparison"):
                audit(b, a, "second_green_arrow")

    def test_comparison_rejects_changed_original_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "dark", root / "second"
            a.mkdir()
            b.mkdir()
            fixture(a, bus_lane="west", case_id="adjacent_dark_drive")
            fixture(b, bus_lane="west", green=("east", "west"), case_id="second_green_drive")
            source = b / "body-1.json"
            source.write_text("changed body")
            with self.assertRaisesRegex(ValueError, "row source missing or changed"):
                audit(a, b, "second_green_arrow")


if __name__ == "__main__":
    unittest.main()
