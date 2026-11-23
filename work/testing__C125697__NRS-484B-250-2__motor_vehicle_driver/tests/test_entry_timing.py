import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "entry_timing.py"
spec = importlib.util.spec_from_file_location("entry_timing", MODULE)
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


def packet(ego_entry=3, other_entry=2, ego_side="left"):
    return {
        "format": "nrs-484b-250-2-original-frames-v1",
        "law_id": "NRS-484B-250-2",
        "cell_id": "C125697",
        "case_id": "case-a",
        "participants": {
            "ego": {"kind": "motor_vehicle", "road_id": "highway-a", "approach_side": ego_side, "movement": "straight"},
            "other": {"kind": "motor_vehicle", "road_id": "highway-b", "approach_side": "right" if ego_side == "left" else "left", "movement": "straight"},
        },
        "opposite_approaches": False,
        "official_device_controls_intersection": False,
        "signal": {"present": True, "mode": "inoperative", "controls_traffic": False},
        "frames": [{"frame": i, "timestamp_s": i / 20, "actors": {
            "ego": {"footprint_intersects_intersection": i >= ego_entry},
            "other": {"footprint_intersects_intersection": i >= other_entry},
        }} for i in range(6)],
    }


class EntryTimingTests(unittest.TestCase):
    def test_original_transition_brackets_and_difference(self):
        result = entry.measure(packet())
        self.assertEqual(result["ego_entry"]["lower_frame"], 2)
        self.assertEqual(result["ego_entry"]["upper_frame"], 3)
        self.assertAlmostEqual(result["intersection_entry_time_difference_s"], .05)
        self.assertIsNone(result["legal_judgment"])

    def test_rejects_source_and_context_gaps(self):
        for mutate in (
            lambda p: p["frames"].pop(2),
            lambda p: p["participants"]["other"].update(road_id="highway-a"),
            lambda p: p.update(official_device_controls_intersection=True),
            lambda p: p["signal"].update(mode="working"),
            lambda p: p["frames"][2]["actors"]["other"].pop("footprint_intersects_intersection"),
        ):
            with self.subTest(mutate=mutate):
                data = packet()
                mutate(data)
                with self.assertRaises((ValueError, KeyError)):
                    entry.measure(data)

    def test_rejects_initially_inside_or_missing_entry(self):
        with self.assertRaisesRegex(ValueError, "first original sample"):
            entry.measure(packet(ego_entry=0))
        with self.assertRaisesRegex(ValueError, "no original footprint entry"):
            entry.measure(packet(ego_entry=9))

    def test_hashed_source_and_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            source.write_text(json.dumps(packet()), encoding="utf-8")
            digest = entry._sha256(source)
            a = entry.measure_file(source, digest)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                entry.measure_file(source, "0" * 64)
            other = packet(ego_entry=2, other_entry=3)
            other["case_id"] = "case-b"
            source.write_text(json.dumps(other), encoding="utf-8")
            b = entry.measure_file(source, entry._sha256(source))
            audit = entry.compare([a, b], ["case-a", "case-b"], "entry_timing")
            self.assertEqual(audit["case_ids"], ["case-a", "case-b"])
            with self.assertRaisesRegex(ValueError, "case identity"):
                entry.compare([a, b], ["case-a", "case-c"], "entry_timing")
            c = copy.deepcopy(b)
            c["ego_approach_side"] = "right"
            with self.assertRaisesRegex(ValueError, "approach side changed"):
                entry.compare([a, c], ["case-a", "case-b"], "entry_timing")
            c = copy.deepcopy(b)
            c["road_ids"]["other"] = "another-highway"
            with self.assertRaisesRegex(ValueError, "fixed condition changed: road_ids"):
                entry.compare([a, c], ["case-a", "case-b"], "entry_timing")


if __name__ == "__main__":
    unittest.main()
