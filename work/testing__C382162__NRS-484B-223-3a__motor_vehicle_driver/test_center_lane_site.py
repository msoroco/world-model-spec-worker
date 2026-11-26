"""Source-shaped CPU tests; these do not establish a real highway designation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from center_lane_site import inspect_site, verify_reviewed_site


def packet(kind="turn_from_highway"):
    relationship = "onto_highway" if kind == "turn_onto_highway" else "from_highway"
    return {
        "public_highway_confirmed": True, "highway_road_id": "H",
        "native_map_source": {"path": "map.json", "sha256": "example"},
        "highway_review_source": {"path": "review.json", "sha256": "example"},
        "lanes": [
            {"id": "C", "road_id": "H", "center_turn_lane": True,
             "exclusive_turn_use": True,
             "permitted_turn_directions": ["negative", "positive"],
             "centreline_xy_m": [[0, 0], [40, 0]]},
            {"id": "E", "road_id": "H", "highway_through": True,
             "centreline_xy_m": [[0, 4], [40, 4]]},
            {"id": "W", "road_id": "H", "highway_through": True,
             "centreline_xy_m": [[40, -4], [0, -4]]}],
        "junction": {"id": "J", "kind": "alley" if kind == "alley_junction_rejection"
                     else "street_intersection"},
        "route": {"center_lane_id": "C", "relationship": relationship,
                  "approach_road_id": "S" if relationship == "onto_highway" else "H",
                  "departure_road_id": "H" if relationship == "onto_highway" or
                  kind == "through_travel" else "S",
                  "waypoints_xy_m": [[-20, 0], [0, 0], [20, 0]]}}


class CenterLaneSiteTests(unittest.TestCase):
    def test_onto_from_and_alley_are_distinct(self):
        for kind in ("turn_from_highway", "turn_onto_highway", "through_travel",
                     "right_turn_purpose", "alley_junction_rejection"):
            self.assertEqual(inspect_site(packet(kind), kind)["center_lane_id"], "C")
        with self.assertRaisesRegex(ValueError, "junction classification"):
            inspect_site(packet("alley_junction_rejection"), "turn_from_highway")

    def test_reject_nonshared_and_wrong_route(self):
        p = packet()
        p["lanes"][0]["permitted_turn_directions"] = ["positive"]
        with self.assertRaisesRegex(ValueError, "bidirectional"):
            inspect_site(p, "turn_from_highway")
        p = packet("turn_onto_highway")
        p["route"]["departure_road_id"] = "S"
        with self.assertRaisesRegex(ValueError, "road identity|departure road"):
            inspect_site(p, "turn_onto_highway")

    def test_original_map_and_review_bytes_must_match(self):
        scratch = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c382162-owner"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            root = Path(tmp)
            p = packet()
            native = "original OpenDRIVE"
            sources = {
                "map.json": {"opendrive_sha256": hashlib.sha256(native.encode()).hexdigest()},
                "review.json": {"public_highway_confirmed": True,
                                "single_bidirectional_turn_only_center_lane": True,
                                "highway_road_id": "H"}}
            for name, value in sources.items():
                path = root / name
                path.write_text(json.dumps(value) + "\n")
            p["native_map_source"] = {"path": "map.json", "sha256": hashlib.sha256((root / "map.json").read_bytes()).hexdigest()}
            p["highway_review_source"] = {"path": "review.json", "sha256": hashlib.sha256((root / "review.json").read_bytes()).hexdigest()}
            self.assertEqual(verify_reviewed_site(root, p, "turn_from_highway", native)["highway_road_id"], "H")
            with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
                verify_reviewed_site(root, p, "turn_from_highway", native + " changed")
            (root / "review.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_reviewed_site(root, p, "turn_from_highway", native)


if __name__ == "__main__":
    unittest.main()
