import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
SPEC = importlib.util.spec_from_file_location("measure_gap", BASE / "measure_gap.py")
measure_gap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure_gap)


class OriginalMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.map_path = root / "map.json"
        self.pose_path = root / "original.jsonl"
        self.packet_path = root / "packet.json"
        self.map_path.write_text(json.dumps({"map_id": "synthetic-test-map",
            "geometry_provenance": "synthetic CPU fixture only",
            "intersection_boundary_local_m": {"west": -8, "south": -8, "east": 8, "north": 8}}))
        center_x = 8 + 4.2672 + 2.25
        with self.pose_path.open("w") as out:
            for frame in range(900):
                out.write(json.dumps({"frame": frame, "time_s": frame / 20,
                    "actor_id": "ego", "x_m": center_x, "y_m": 0,
                    "heading_deg": 180, "speed_mps": 0 if frame >= 800 else 5,
                    "halt_state": frame >= 800}) + "\n")
        self.packet = {"actor_id": "ego", "vehicle_length_m": 4.5,
                       "vehicle_width_m": 1.8,
                       "map_source": {"path": "map.json", "sha256": self._sha(self.map_path)},
                       "pose_source": {"path": "original.jsonl", "sha256": self._sha(self.pose_path)}}
        self._save_packet()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _save_packet(self):
        self.packet_path.write_text(json.dumps(self.packet))

    def test_original_halt_gap_and_source_hashes(self):
        result = measure_gap.measure(self.packet_path)
        self.assertEqual(result["halt_frame_count"], 100)
        self.assertAlmostEqual(result["minimum_halt_body_gap_m"], 4.2672)
        self.assertEqual(result["pose_sha256"], self._sha(self.pose_path))

    def test_changed_original_trace_rejected(self):
        self.pose_path.write_text(self.pose_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            measure_gap.measure(self.packet_path)

    def test_short_or_nonhalt_trace_rejected(self):
        self.pose_path.write_text("".join(self.pose_path.read_text().splitlines(keepends=True)[:-1]))
        self.packet["pose_source"]["sha256"] = self._sha(self.pose_path)
        self._save_packet()
        with self.assertRaisesRegex(ValueError, "900-frame"):
            measure_gap.measure(self.packet_path)

    def test_missing_geometry_provenance_rejected(self):
        data = json.loads(self.map_path.read_text())
        del data["geometry_provenance"]
        self.map_path.write_text(json.dumps(data))
        self.packet["map_source"]["sha256"] = self._sha(self.map_path)
        self._save_packet()
        with self.assertRaisesRegex(ValueError, "provenance"):
            measure_gap.measure(self.packet_path)

    def test_scattered_halt_frames_rejected(self):
        rows = [json.loads(line) for line in self.pose_path.read_text().splitlines()]
        for row in rows:
            row["halt_state"] = row["frame"] % 2 == 0
            row["speed_mps"] = 0 if row["halt_state"] else 5
        self.pose_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.packet["pose_source"]["sha256"] = self._sha(self.pose_path)
        self._save_packet()
        with self.assertRaisesRegex(ValueError, "contiguous two-second"):
            measure_gap.measure(self.packet_path)

    def test_matching_hash_cannot_escape_saved_acquisition(self):
        outside = self.packet_path.parent.parent / "outside-pose.jsonl"
        outside.write_bytes(self.pose_path.read_bytes())
        self.addCleanup(outside.unlink)
        self.packet["pose_source"] = {"path": str(outside), "sha256": self._sha(outside)}
        self._save_packet()
        with self.assertRaisesRegex(ValueError, "escapes saved acquisition"):
            measure_gap.measure(self.packet_path)
        self.packet["pose_source"]["path"] = "../outside-pose.jsonl"
        self._save_packet()
        with self.assertRaisesRegex(ValueError, "escapes saved acquisition"):
            measure_gap.measure(self.packet_path)
        link = self.packet_path.parent / "linked-pose.jsonl"
        link.symlink_to(outside)
        self.packet["pose_source"]["path"] = link.name
        self._save_packet()
        with self.assertRaisesRegex(ValueError, "outside saved acquisition"):
            measure_gap.measure(self.packet_path)


if __name__ == "__main__":
    unittest.main()
