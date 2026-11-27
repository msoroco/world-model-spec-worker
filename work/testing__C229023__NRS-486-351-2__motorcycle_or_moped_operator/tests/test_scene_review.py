"""Construction and source gate tests; no CARLA is imported."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("c229023_scene_review", ROOT / "scene_review.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
AID = ROOT.name


class SceneReviewTest(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c229023-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.survey = {
            "route_origin_xy": [0, 0], "route_unit_xy": [1, 0],
            "route_stations_m": [0, 10, 20, 30, 40, 50],
            "lane_width_m": 4.7, "ego_lane_id": 1, "other_lane_id": 1,
            "adjacent_lane_id": 2, "adjacent_lane_center_offset_m": 4.7,
            "abreast_lateral_offsets_m": [-1.35, 0, 1.35],
            "participant_half_widths_m": [0.36, 0.38, 0.35],
            "other_vehicle_class": "motorcycle", "spawn_z_m": 0.5,
        }
        self.plan = json.loads((ROOT / "case-plan.json").read_text())

    def packet(self, case, *, consent=None):
        sources = {}
        for key in module.SOURCE_KEYS:
            p = self.folder / (key + ".txt")
            p.write_text("reviewed source for " + key + "\n")
            sources[key] = {"path": p.name,
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        if consent is None:
            consent = "consented" if case["requested_driver_consent"] else "not_consented"
        scene = {
            "format": "c229023-reviewed-original-v1",
            "source_kind": "original_reviewed", "diagnostic_fixture": False,
            "case_id": case["case_id"], "reviewer": "fixture reviewer",
            "map_id": "TownFixture", "opendrive_sha256": "a" * 64,
            "sources": sources, "ego_blueprint_id": "vehicle.fixture.motorcycle",
            "other_blueprint_id": "vehicle.fixture.motorcycle",
            "ego_vehicle_class": "motorcycle", "other_vehicle_class": "motorcycle",
            "ego_classification_source_sha256": sources["ego_classification"]["sha256"],
            "other_classification_source_sha256": sources["other_classification"]["sha256"],
            "driver_identity_source_sha256": sources["driver_identity"]["sha256"],
            "consent_status": consent,
            "consent_source_sha256": sources["driver_consent"]["sha256"],
            "subsection_3_status": "unresolved",
            "subsection_3_source_sha256": sources["subsection_3_review"]["sha256"],
            "survey": self.survey,
        }
        path = self.folder / "scene.json"
        path.write_text(json.dumps(scene) + "\n")
        return path

    def test_all_five_source_gated_constructions(self):
        for case in self.plan["cases"]:
            with self.subTest(case=case["case_id"]):
                request = module.reviewed_scene(self.packet(case), case["case_id"], case)
                self.assertEqual(len(request["participants"]),
                                 3 if case["requested_two_wheeler_count"] == 3 else 2)
                ego, other = request["participants"][:2]
                self.assertEqual(ego["lane_id"] == other["lane_id"],
                                 case["requested_same_lane"])
                self.assertLess(ego["station_m"], other["station_m"]) if case["requested_pass"] else self.assertEqual(ego["station_m"], other["station_m"])

    def test_missing_and_changed_source_rejected(self):
        case = self.plan["cases"][0]
        path = self.packet(case)
        (self.folder / "lane_geometry.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash or path invalid"):
            module.reviewed_scene(path, case["case_id"], case)

    def test_consent_is_independent(self):
        case = self.plan["cases"][2]
        path = self.packet(case, consent="unresolved")
        with self.assertRaisesRegex(ValueError, "independent consent"):
            module.reviewed_scene(path, case["case_id"], case)

    def test_no_lateral_body_overlap(self):
        case = self.plan["cases"][4]
        self.survey["abreast_lateral_offsets_m"] = [0, 0.2, 0.4]
        with self.assertRaisesRegex(ValueError, "footprints overlap"):
            module.construction(self.survey, case)

    def test_no_lane_width_fiction(self):
        case = self.plan["cases"][4]
        self.survey["lane_width_m"] = 3.5
        self.survey["abreast_lateral_offsets_m"] = [-1.55, 0, 1.55]
        with self.assertRaisesRegex(ValueError, "leaves shared traffic lane"):
            module.construction(self.survey, case)


if __name__ == "__main__":
    unittest.main()
