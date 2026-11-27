import copy
import json
import unittest
from pathlib import Path

from runner import check, survey_source


class SelectedHydrantOffline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_window_and_source_plan(self):
        result = check(self.config)
        self.assertEqual(result["case_id"], self.config["case_id"])
        self.assertEqual((result["frames"], result["rate_hz"]), (600, 20))
        self.assertFalse(result["physical_completion"])

    def test_missing_or_changed_case_inputs_rejected(self):
        for key, value in (("case_id", "wrong"), ("frames", 599),
                           ("parking_permission", "painted_red"),
                           ("exception_context", "assumed"),
                           ("physical_completion", {"complete": True})):
            changed = copy.deepcopy(self.config)
            changed[key] = value
            with self.assertRaises(ValueError):
                check(changed)

    def test_camera_loss_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four named"):
            check(changed)

    def test_survey_requires_permission_and_hydrant_provenance(self):
        from tempfile import TemporaryDirectory
        survey = {"source_kind": "original_native_hydrant_survey",
                  "map_name": "surveyed-map", "premises_access_source": "original-map",
                  "parking_permission_source": "original-regulatory-survey",
                  "parking_permission": self.config["parking_permission"],
                  "hydrant_identity_source": "original-hydrant-inventory",
                  "hydrant_xyz_m": [0, 0, 0], "vehicle_spawn_index": 0,
                  "distance_uncertainty_ft": 0.1}
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "survey.json"
            path.write_text(json.dumps(survey))
            self.assertEqual(survey_source(path, self.config)["map_name"], "surveyed-map")
            for key in ("parking_permission_source", "hydrant_identity_source",
                        "premises_access_source"):
                changed = copy.deepcopy(survey)
                changed.pop(key)
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    survey_source(path, self.config)


if __name__ == "__main__":
    unittest.main()
