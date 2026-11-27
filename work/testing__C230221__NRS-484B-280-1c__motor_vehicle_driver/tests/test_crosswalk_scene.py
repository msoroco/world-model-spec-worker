"""Focused CPU checks of source binding and original observation separation."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from crosswalk_scene import author_from_native, load_site, measure, sha


ASSIGNMENT = "testing__C230221__NRS-484B-280-1c__motor_vehicle_driver"


def body(x, y, width):
    return [[x - width, y - width, 0], [x + width, y - width, 0],
            [x + width, y + width, 0], [x - width, y + width, 0]]


class CrosswalkSceneTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("SCENARIO_TEST_TMPDIR", "/tmp"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def site(self, kind):
        case_id = ASSIGNMENT + "__" + kind + "_crosswalk"
        marking = '<objects><object id="mark-1" type="crosswalk"/></objects>' if kind == "marked" else "<objects/>"
        map_path = self.root / "map.xodr"
        map_path.write_text('<OpenDRIVE><road id="main"/><road id="crossing">' + marking + '</road></OpenDRIVE>')
        site = {
            "case_id": case_id, "cell_id": "C230221", "layout": "road", "control": "crosswalk",
            "crosswalk_kind": kind, "map_source": {"path": "map.xodr", "sha256": sha(map_path)},
            "intersecting_road_ids": ["main", "crossing"],
            "intersection_review_source": "original Native map road-junction readback",
            "curb_review_source": "original Native map curb-edge readback",
            "crossing_polygon_xy_m": [[-1, -4], [1, -4], [1, 4], [-1, 4]],
            "near_curb_polygon_xy_m": [[-2, -7], [2, -7], [2, -4.1], [-2, -4.1]],
            "far_curb_polygon_xy_m": [[-2, 4.1], [2, 4.1], [2, 7], [-2, 7]],
            "pedestrian_route_xy_m": [[0, -5], [0, 0], [0, 5]],
            "ego_route_xy_m": [[-30, 0], [30, 0]],
            "marking_object_id": "mark-1" if kind == "marked" else None,
        }
        path = self.root / "site.json"
        path.write_text(json.dumps(site))
        return path, case_id

    def sample(self):
        return {"ego_class": "motor_vehicle", "pedestrian_class": "pedestrian",
                "driver_control_source": "original scripted driver input",
                "pedestrian_class_source": "original actor blueprint",
                "ego_body_vertices_m": body(-8, 0, 1),
                "pedestrian_body_vertices_m": body(0, 0, 0.2),
                "driver_observation_event": {"source": "original_driver_input", "observed": True},
                "ego_speed_mps": 5.0, "ego_brake": 0.0}

    def test_both_original_crossing_kinds_and_no_legal_verdict(self):
        for kind in ("marked", "unmarked"):
            path, case_id = self.site(kind)
            site = load_site(path, case_id)
            reading = measure(site, self.sample())
            self.assertEqual(reading["crosswalk_kind"], kind)
            self.assertIsNone(reading["legal_proper_caution_verdict"])

    def test_marking_must_match_original_map(self):
        path, case_id = self.site("marked")
        site = json.loads(path.read_text())
        site["marking_object_id"] = "invented"
        path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, "marking absent"):
            load_site(path, case_id)

    def test_unmarked_map_rejects_hidden_marking(self):
        path, case_id = self.site("unmarked")
        map_path = self.root / "map.xodr"
        map_path.write_text(map_path.read_text().replace("<objects/>", '<objects><object id="hidden" type="crosswalk"/></objects>'))
        site = json.loads(path.read_text())
        site["map_source"]["sha256"] = sha(map_path)
        path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, "contains a marking"):
            load_site(path, case_id)

    def test_map_hash_and_curb_continuity_required(self):
        path, case_id = self.site("marked")
        map_path = self.root / "map.xodr"
        map_path.write_text(map_path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "source absent or changed"):
            load_site(path, case_id)
        site = json.loads(path.read_text())
        site["map_source"]["sha256"] = sha(map_path)
        site["pedestrian_route_xy_m"][0] = [0, -20]
        path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, "curb continuity"):
            load_site(path, case_id)

    def test_camera_visibility_cannot_substitute_for_driver_input(self):
        path, case_id = self.site("marked")
        sample = self.sample()
        sample["driver_observation_event"] = {"source": "camera_visibility", "observed": True}
        with self.assertRaisesRegex(ValueError, "original input"):
            measure(load_site(path, case_id), sample)

    def test_native_author_requires_hash_join_and_fresh_output(self):
        path, case_id = self.site("marked")
        map_bytes = (self.root / "map.xodr").read_bytes()
        readback = json.loads(path.read_text())
        readback["source"] = "original_native_readback"
        readback["map_sha256"] = sha(self.root / "map.xodr")
        output = self.root / "native"
        output.mkdir()
        self.assertEqual(author_from_native(map_bytes, readback, output, case_id),
                         load_site(output / "crosswalk-site.json", case_id))
        with self.assertRaisesRegex(ValueError, "fresh"):
            author_from_native(map_bytes, readback, output, case_id)
        readback["map_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source binding"):
            author_from_native(map_bytes, readback, self.root, case_id)


if __name__ == "__main__":
    unittest.main()
