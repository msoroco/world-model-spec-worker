import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis


def seal(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    return hashlib.sha256(raw.encode()).hexdigest()


class AnalysisContractTests(unittest.TestCase):
    def test_missing_site_is_case_specific_negative(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps({"selected_case_id": "case"}))
            with self.assertRaisesRegex(ValueError, "Missing required source: site.json"):
                analysis.report(root)

    def test_saved_source_join_and_exception_context(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = {"selected_case_id": "case", "through_designation": False,
                      "traffic_controlled_intersection": False}
            site = {"selected_case_id": "case", "ego_road_through": False,
                    "traffic_controlled_intersection": False,
                    "jurisdiction": "synthetic", "road_kind": "street"}
            (root / "config.json").write_text(json.dumps(config))
            (root / "site.json").write_text(json.dumps(site))
            (root / "native-sight.json").write_text(json.dumps({"site_source_sha256": seal(site),
                "entering_arms": ["north", "south", "west"]}))
            (root / "native-sight-receipt.json").write_text("{}")
            measured = {"map_hash": "mock", "approach_frame_ids": [1, 2],
                "blocked_rays": [[1, "west", "intersection_view"]], "all_views_clear": False,
                "traversal_frame_ids": [3], "traversal_speed_min_mps": 6.0,
                "traversal_speed_max_mps": 6.0, "prima_facie_value_mps": 6.7056,
                "through_designation": False, "traffic_controlled": False,
                "source_sha256": {"through_source_sha256": "a", "control_source_sha256": "b"}}
            saved = {"measurement": measured,
                     "camera_capture": {"camera_images_decoded": 3600}}
            with patch.object(analysis, "verify_saved", return_value=saved):
                report = analysis.report(root)
            self.assertFalse(report["legal_verdict_claimed"])
            self.assertEqual(report["measurements"]["last_100ft_sight_observation"]["value"]["camera_images_decoded"], 3600)
            self.assertEqual(set(report["measurements"]["through_street_exception"]["sources"]),
                             {"site.json", "native-sight.json", "native-sight-receipt.json"})
            site["ego_road_through"] = True
            (root / "site.json").write_text(json.dumps(site))
            with patch.object(analysis, "verify_saved", return_value=saved):
                with self.assertRaisesRegex(ValueError, "site and original capture hash differ"):
                    analysis.report(root)


if __name__ == "__main__":
    unittest.main()
