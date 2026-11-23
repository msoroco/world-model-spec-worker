import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lamp_probe import command_lights, measure
from parking_geometry import classify_footprint
from comparison_audit import audit


class Bits:
    NONE = 0
    Position = 1
    LowBeam = 2
    HighBeam = 4


class Vehicle:
    def set_light_state(self, bits):
        self.bits = bits

    def get_light_state(self):
        return self.bits


class LampProbeTests(unittest.TestCase):
    def test_command_and_readback(self):
        vehicle = Vehicle()
        self.assertEqual(command_lights(vehicle, Bits, "unlit")["readback_bits"], 0)
        self.assertEqual(command_lights(vehicle, Bits, "low_beam")["readback_bits"], 3)
        self.assertEqual(command_lights(vehicle, Bits, "high_beam")["readback_bits"], 5)
        with self.assertRaisesRegex(ValueError, "unknown"):
            command_lights(vehicle, Bits, "depressed")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        states = []
        maps = []
        for i in range(4):
            states.append(dict(frame=100 + i, time_s=i * .05, speed_mps=0,
                               parking_brake=True,
                               footprint_inside_reviewed_parking_polygon=True,
                               light_state_bits=3, actor_id=17))
            maps.append(dict(frame=100 + i, **{name + "_source_frame": 100 + i
                         for name in ("overview", "approach", "reference_corner", "driver_reference")}))
        self.write("actor-state.jsonl", states)
        self.write("camera-frame-map.jsonl", maps)

    def write(self, name, rows):
        (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))

    def hashes(self):
        return {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                for name in ("actor-state.jsonl", "camera-frame-map.jsonl")}

    def test_measures_source_bound_originals(self):
        result = measure(self.root, self.hashes(), mode="low_beam", low_beam_bit=2, high_beam_bit=4)
        self.assertEqual((result["parked_sample_count"], result["low_beam_readback_count"],
                          result["high_beam_readback_count"]), (4, 4, 0))
        self.assertEqual(result["first_original_frame"], 100)

    def test_rejects_mutated_source_and_missing_view(self):
        hashes = self.hashes()
        path = self.root / "actor-state.jsonl"
        path.write_text(path.read_text().replace('"speed_mps": 0', '"speed_mps": 1', 1))
        with self.assertRaisesRegex(ValueError, "hash changed"):
            measure(self.root, hashes, mode="low_beam", low_beam_bit=2, high_beam_bit=4)
        rows = [json.loads(line) for line in (self.root / "camera-frame-map.jsonl").read_text().splitlines()]
        del rows[0]["driver_reference_source_frame"]
        self.write("camera-frame-map.jsonl", rows)
        with self.assertRaisesRegex(ValueError, "four-view"):
            measure(self.root, self.hashes(), mode="low_beam", low_beam_bit=2, high_beam_bit=4)

    def test_rejects_unverified_parked_context(self):
        rows = [json.loads(line) for line in (self.root / "actor-state.jsonl").read_text().splitlines()]
        del rows[0]["footprint_inside_reviewed_parking_polygon"]
        self.write("actor-state.jsonl", rows)
        with self.assertRaisesRegex(ValueError, "parking evidence"):
            measure(self.root, self.hashes(), mode="low_beam", low_beam_bit=2, high_beam_bit=4)

    def test_original_footprint_geometry(self):
        parking = [(0, 0), (10, 0), (10, 4), (0, 4)]
        intersection = [(10, 0), (14, 0), (14, 4), (10, 4)]
        body = [(2, 1), (4, 1), (4, 3), (2, 3)]
        measured = classify_footprint(body, parking, intersection)
        self.assertTrue(measured["footprint_inside_reviewed_parking_polygon"])
        self.assertEqual(measured["body_corner_inside_intersection_count"], 0)
        crossing = [(9, 1), (11, 1), (11, 3), (9, 3)]
        measured = classify_footprint(crossing, parking, intersection)
        self.assertFalse(measured["footprint_inside_reviewed_parking_polygon"])
        self.assertEqual(measured["body_corner_inside_intersection_count"], 2)

    def test_comparison_audit_rejects_unheld_setup_and_bad_readback(self):
        modes = ("unlit", "low_beam", "high_beam")
        fixed = {mode: {key: "hash" for key in
                 ("reviewed_map_sha256", "parking_polygon_sha256", "vehicle_blueprint_sha256",
                  "weather_sha256", "camera_policy_sha256", "parking_controller_sha256")}
                 for mode in modes}
        measured = {mode: dict(requested_mode=mode, frame_count=4, parked_sample_count=4,
                               low_beam_readback_count=4 if mode == "low_beam" else 0,
                               high_beam_readback_count=4 if mode == "high_beam" else 0,
                               source_hashes={"actor-state.jsonl": "a", "camera-frame-map.jsonl": "b"})
                    for mode in modes}
        self.assertTrue(audit(fixed, measured)["readback_differences_confirmed"])
        fixed["high_beam"]["weather_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "fixed condition changed"):
            audit(fixed, measured)
        fixed["high_beam"]["weather_sha256"] = "hash"
        measured["unlit"]["high_beam_readback_count"] = 1
        with self.assertRaisesRegex(ValueError, "unlit case"):
            audit(fixed, measured)


if __name__ == "__main__":
    unittest.main()
