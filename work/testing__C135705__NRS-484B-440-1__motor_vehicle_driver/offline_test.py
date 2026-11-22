"""Materialized Native construction checks; executed by runtime.py offline."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from runner import check_scene
from standing_geometry import measure


class OfflineCase(unittest.TestCase):
    def test_source_bound_road_actors_and_sight(self):
        scene,source=check_scene(Path("scene.json"))
        self.assertEqual(source,Path("road.xodr").resolve())
        self.assertEqual(scene["other_vehicle_centers_xy_m"][0][0],65)
        self.assertEqual(scene["other_vehicle_centers_xy_m"][-1][0],-65)
        result=measure(scene)
        suffix=scene["case_id"].rsplit("__",1)[1]
        expected={"passage_clear_view":(True,True),
                  "passage_blocked":(False,True),
                  "view_occluded_both":(True,False)}[suffix]
        self.assertEqual(result["physical_passage_observed"],expected[0])
        for side in ("negative_x","positive_x"):
            self.assertEqual(result["sight_probes"][f"{side}:60.960m"]["visible"],expected[1])
        self.assertEqual(scene["disabled_physical_mechanism"],"engine_off_brake_locked")
        self.assertEqual(scene["capture_rate_hz"],20)


if __name__=="__main__":unittest.main()
