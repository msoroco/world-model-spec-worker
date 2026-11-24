import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_context import build
from yield_site import ROAD, ROAD_OTHER_STOP, validate_authored_site
from yield_stage import PREFIX, primary


class ContextTests(unittest.TestCase):
    def review(self, root, stage, native):
        path = ROAD_OTHER_STOP if stage.other_stop_sign else ROAD
        status = root / "site-status-source.txt"
        status.write_text("Synthetic source-contract fixture; no legal road classification proved.\n")
        review = {"authored_map_sha256": validate_authored_site(path,
                                           other_stop=stage.other_stop_sign)["road_sha256"],
                  "native_map_id": native["native_map_id"],
                  "native_yield_sign_id": native["native_yield_sign_id"],
                  "reviewer": "CPU source-contract fixture",
                  "road_status_source": "site-status-source.txt",
                  "road_status_source_sha256": hashlib.sha256(status.read_bytes()).hexdigest(),
                  "non_through_highway": True,
                  "police_control": stage.officer_control_source_required,
                  "traffic_signal_control": False,
                  "entrance_devices": {"158208": "yield",
                                       "158212": "stop" if stage.other_stop_sign else "none",
                                       "158214": "none"},
                  "intersection_polygon_xy_m": [[-8,-8],[8,-8],[8,8],[-8,8]]}
        source = root / "status-review.json"
        source.write_text(json.dumps(review))
        return source, review

    def test_all_three_entrances_and_selected_stop_variant_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kind in ("yield_other_inside", "yield_other_obligated", "officer_control_exception"):
                stage = primary(PREFIX + kind)
                native = {"native_map_id": "signed-map", "intersection_id": 158209,
                          "native_yield_sign_id": 88,
                          "native_other_stop_sign_id": 90 if stage.other_stop_sign else None}
                source, review = self.review(root, stage, native)
                context = build(stage, native, source)
                self.assertEqual(context["entrance_road_ids"], [158208,158212,158214])
                self.assertEqual(context["entrances"][1]["device"],
                                 "stop" if stage.other_stop_sign else "none")
                self.assertEqual(context["police_control"], stage.officer_control_source_required)
                review["entrance_devices"].pop("158214")
                source.write_text(json.dumps(review))
                with self.assertRaisesRegex(ValueError, "device inventory"):
                    build(stage, native, source)

    def test_status_review_cannot_assert_unsourced_road_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = primary(PREFIX + "yield_other_inside")
            native = {"native_map_id": "signed-map", "intersection_id": 158209,
                      "native_yield_sign_id": 88, "native_other_stop_sign_id": None}
            source, review = self.review(Path(tmp), stage, native)
            review["non_through_highway"] = None
            source.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "Non-through-highway"):
                build(stage, native, source)
            review["non_through_highway"] = True
            review["authored_map_sha256"] = "stale"
            source.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "authored/Native"):
                build(stage, native, source)
            review["authored_map_sha256"] = validate_authored_site()["road_sha256"]
            source.write_text(json.dumps(review))
            (Path(tmp) / "site-status-source.txt").write_text("changed source")
            with self.assertRaisesRegex(ValueError, "road-status source file"):
                build(stage, native, source)


if __name__ == "__main__":
    unittest.main()
