import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_acquisition import seal_original_acquisition
from speed_measurement import measure


CASE = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__reference"


def source_rows():
    motion = [{"frame_id": 101 + i, "time_s": i / 20,
               "velocity_mps": [3.0, 0.0, 0.0], "x_m": -30 + 3 * i / 20,
               "y_m": -.75} for i in range(25)]
    context = {"case_id": CASE, "source_kind": "original_local_native_capture",
               "jurisdiction": {"city_of_las_vegas": True, "source": "source-bound local map"},
               "bicycle_classification": {"human_powered": True, "moped": False,
                                          "source": "source-bound local asset inventory"},
               "alley_route": {"source": "original road geometry"},
               "rack_geometry": {"source": "original actor vertices"},
               "samples": [{"frame": row["frame_id"], "time_s": row["time_s"],
                            "weather": "clear", "surface": "dry", "visibility": "clear",
                            "pedestrians": "none near rack", "curvature": "straight"}
                           for row in motion]}
    return motion, context


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.motion, self.context = source_rows()
        self.source = self.base / "original-context-packet.json"
        self.source.write_text(json.dumps(self.context))
        self.ref = {"path": str(self.source),
                    "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}
        self.output = self.base / "acquisition"

    def test_sealed_sources_read_back_with_original_frame_time(self):
        inventory = seal_original_acquisition(self.output, CASE, self.motion,
                                              self.context, context_source=self.ref)
        actual = measure(self.output, inventory, CASE)
        self.assertEqual(actual["summary"]["sample_count"], 25)
        self.assertEqual(actual["samples"][0]["frame"], 101)
        self.assertEqual(actual["legal_prudence"], "unresolved")
        self.assertTrue((self.output / "inventory.json").is_file())
        with self.assertRaisesRegex(ValueError, "overwrite"):
            seal_original_acquisition(self.output, CASE, self.motion,
                                      self.context, context_source=self.ref)

    def test_hash_and_source_identity_rejected(self):
        bad = dict(self.ref, sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            seal_original_acquisition(self.output, CASE, self.motion,
                                      self.context, context_source=bad)
        self.context["source_kind"] = "authored_fixture"
        with self.assertRaisesRegex(ValueError, "original Native"):
            seal_original_acquisition(self.output, CASE, self.motion,
                                      self.context, context_source=self.ref)

    def test_source_packet_disagreement_rejected(self):
        self.context["samples"][0]["weather"] = "rain"
        with self.assertRaisesRegex(ValueError, "differs from original"):
            seal_original_acquisition(self.output, CASE, self.motion,
                                      self.context, context_source=self.ref)

    def test_frame_gap_and_condition_gap_rejected(self):
        self.motion[7]["frame_id"] += 1
        with self.assertRaisesRegex(ValueError, "continuity"):
            seal_original_acquisition(self.output, CASE, self.motion,
                                      self.context, context_source=self.ref)
        self.motion, self.context = source_rows()
        self.context["samples"][8]["time_s"] += .05
        self.source.write_text(json.dumps(self.context))
        self.ref["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "condition frame/time"):
            seal_original_acquisition(self.output, CASE, self.motion,
                                      self.context, context_source=self.ref)


if __name__ == "__main__":
    unittest.main()
