import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speed_source_review import ASSIGNMENT, measure


class OriginalSpeedReviewTests(unittest.TestCase):
    def _attempt(self, root, suffix="above", speed=15.0, unit="mph", rate=30):
        case = ASSIGNMENT + "__" + suffix
        frames = [{"frame": i, "time_s": round(i / 20, 2)} for i in range(900)]
        motion = {"case_id": case, "source_kind": "original_native",
                  "samples": [{"frame": r["frame"], "time_s": r["time_s"],
                               "vehicle_id": "ego", "speed_mps": speed} for r in frames]}
        route = {"case_id": case, "source_kind": "original_native",
                 "samples": [{"frame": r["frame"], "time_s": r["time_s"],
                              "road_id": "narrow-1", "segment_id": "posted-east-1",
                              "direction": "east",
                              "on_highway": True, "operating": True} for r in frames]}
        control = {"case_id": case, "source_kind": "original_native_context",
                   "rate": rate, "unit": unit, "vehicle_id": "ego",
                   "highway_dedication_source": "municipal dedication record",
                   "public_access_source": "field access review",
                   "narrow_road_geometry_source": "original lane geometry",
                   "vehicle_clearance_source": "original body and lane geometry",
                   "governed_segment_source": "authority order and route chainage",
                   "governed_direction_source": "authority order and sign facing",
                   "sign_position_source": "original sign transform",
                   "posting_authority_source": "municipal order",
                   "public_authority_posted": True, "sign_in_camera_view": True,
                   "governed_road_id": "narrow-1", "governed_segment_id": "posted-east-1",
                   "governed_direction": "east"}
        packets = {"frame_map": {"frames": frames}, "vehicle_motion": motion,
                   "route_occupancy": route, "posted_control": control}
        sources = {}
        for name, value in packets.items():
            raw = (json.dumps(value) + "\n").encode()
            (root / (name + ".json")).write_bytes(raw)
            sources[name] = {"path": name + ".json", "sha256": hashlib.sha256(raw).hexdigest()}
        return case, {"case_id": case, "source_kind": "original_native", "sources": sources}

    def _change(self, root, inventory, name, key, value):
        path = root / (name + ".json")
        packet = json.loads(path.read_text())
        packet[key] = value
        raw = (json.dumps(packet) + "\n").encode()
        path.write_bytes(raw)
        inventory["sources"][name]["sha256"] = hashlib.sha256(raw).hexdigest()

    def test_exact_rate_and_metric_unit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root, speed=13.4112)
            result = measure(root, inventory, case)
            self.assertEqual(result["posted_rate_mps"], 13.4112)
            self.assertEqual(result["samples"][0]["rate_difference_mps"], 0)
            self.assertEqual(result["governed_frames"], 900)
            self.assertEqual(result["legal_applicability_and_priority"], "unresolved")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root, suffix="metric_equivalent", speed=13.4112,
                                             unit="km/h", rate=48.28032)
            self.assertAlmostEqual(measure(root, inventory, case)["posted_rate_mps"], 13.4112)

    def test_governed_portion_and_direction_are_measured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root, suffix="outside_zone")
            packet = json.loads((root / "route_occupancy.json").read_text())
            packet["samples"][450]["road_id"] = "outside"
            self._change(root, inventory, "route_occupancy", "samples", packet["samples"])
            result = measure(root, inventory, case)
            self.assertEqual(result["governed_frames"], 899)
            self.assertIsNone(result["samples"][450]["rate_difference_mps"])

    def test_direction_and_authority_alternatives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root, suffix="opposite_direction")
            self._change(root, inventory, "posted_control", "governed_direction", "west")
            self.assertEqual(measure(root, inventory, case)["governed_frames"], 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root, suffix="non_authority_sign")
            self._change(root, inventory, "posted_control", "public_authority_posted", False)
            self.assertEqual(measure(root, inventory, case)["governed_frames"], 0)

    def test_off_camera_sign_requires_reading_assumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root, suffix="sign_not_in_view")
            self._change(root, inventory, "posted_control", "sign_in_camera_view", False)
            with self.assertRaisesRegex(ValueError, "off-camera governing limit remains unknown"):
                measure(root, inventory, case)
            self._change(root, inventory, "posted_control", "off_camera_reading_assumption_source", "original authority order")
            self.assertFalse(measure(root, inventory, case)["sign_in_camera_view"])

    def test_rejects_stale_source_and_wrong_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root)
            (root / "posted_control.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                measure(root, inventory, case)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root)
            packet = json.loads((root / "frame_map.json").read_text())
            packet["frames"][3]["time_s"] = 1.0
            self._change(root, inventory, "frame_map", "frames", packet["frames"])
            with self.assertRaisesRegex(ValueError, "20 Hz"):
                measure(root, inventory, case)


if __name__ == "__main__":
    unittest.main()
