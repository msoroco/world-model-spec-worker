import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("observed_speed", ROOT / "observed_speed.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SCRATCH = ROOT.parents[2] / ".runtime-work" / "c405647-observed-speed-tests"


def fixture(suffix):
    case = module.BASE + suffix
    rows = []
    for index in range(module.FRAMES):
        t = index / module.RATE
        speed = 14.0 if suffix == "b" or t < 8 else max(7.0, 14.0 - 3.5 * (t - 8))
        x = -100 + 14 * t if suffix == "b" or t < 8 else -100 + 112 + 14 * min(t - 8, 2) - 1.75 * min(t - 8, 2) ** 2 + 7 * max(0, t - 10)
        native = 3000 + index
        rows.append({"case_id": case, "source_kind": "synthetic_cpu_fixture",
                     "video_frame": index, "native_frame": native, "time_s": t,
                     "ego": {"road_x_m": x, "speed_mps": speed},
                     "qualifying_vehicle": {"road_x_m": 100 + 2 * t, "speed_mps": 2.0,
                                            "kind": "authorized_emergency_vehicle",
                                            "authorized_source_id": "fixture-actor",
                                            "flashing_state": (index // 10) % 2 == 0,
                                            "lamp_equipment_source_id": "fixture-equipment",
                                            "lamp_qualification_source_id": "fixture-qualification"},
                     "officer_direction": None, "officer_direction_source_id": "fixture-scene",
                     "road_context_source_id": "fixture-road", "weather_context_source_id": "fixture-weather",
                     "posted_limit_mps": 15.0, "wet_road": False, "visibility_m": 200.0,
                     "camera_frames": {name: native for name in ("overview", "approach", "reference_corner", "driver_reference")}})
    return rows


class ObservedSpeedTest(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "observations.jsonl"

    def run_rows(self, rows, *, synthetic=True):
        self.path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        return module.measure(self.path, synthetic=synthetic)

    def test_both_exact_interventions(self):
        a = self.run_rows(fixture("a"))
        b = self.run_rows(fixture("b"))
        self.assertGreater(a["reduction_mps"], 3)
        self.assertEqual(b["reduction_mps"], 0)
        self.assertTrue(a["fixture_only"])
        self.assertFalse(a["actual_pixels_reviewed"])

    def test_rejects_short_window(self):
        with self.assertRaisesRegex(ValueError, "600 frames"):
            self.run_rows(fixture("a")[:-1])

    def test_rejects_missing_camera(self):
        rows = fixture("a")
        rows[80]["camera_frames"].pop("approach")
        with self.assertRaisesRegex(ValueError, "Four synchronized"):
            self.run_rows(rows)

    def test_rejects_lamp_qualification(self):
        rows = fixture("a")
        rows[100]["qualifying_vehicle"]["lamp_qualification_source_id"] = ""
        with self.assertRaisesRegex(ValueError, "flashing-light source"):
            self.run_rows(rows)

    def test_rejects_stopped_other_vehicle(self):
        rows = fixture("a")
        rows[100]["qualifying_vehicle"]["speed_mps"] = 0
        with self.assertRaisesRegex(ValueError, "Moving authorized"):
            self.run_rows(rows)

    def test_rejects_missing_officer_source(self):
        rows = fixture("a")
        rows[100]["officer_direction_source_id"] = ""
        with self.assertRaisesRegex(ValueError, "Officer exception"):
            self.run_rows(rows)

    def test_rejects_wrong_intervention(self):
        rows = fixture("b")
        for row in rows:
            row["case_id"] = module.BASE + "a"
        with self.assertRaisesRegex(ValueError, "speed intervention"):
            self.run_rows(rows)

    def test_rejects_fixture_as_original(self):
        with self.assertRaisesRegex(ValueError, "Source provenance"):
            self.run_rows(fixture("a"), synthetic=False)


if __name__ == "__main__":
    unittest.main()
