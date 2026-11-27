"""Original-source direction measurement and rejection tests."""

import copy
import hashlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import direction


def packet():
    routes = {}
    for name, sign in (("counterclockwise", 1), ("clockwise", -1)):
        ring = [{"x": 7*math.cos(sign*math.radians(n)),
                 "y": 7*math.sin(sign*math.radians(n)),
                 "lane_id": "ring", "section": "ring"}
                for n in (0, 30, 60, 90, 120, 150)]
        routes[name] = ([{"x": 10, "y": 0, "lane_id": "entry", "section": "entry"}]
                        + ring + [{"x": ring[-1]["x"]-1,
                                   "y": ring[-1]["y"]+sign,
                                   "lane_id": "exit", "section": "exit"}])
    return {"source_kind": "native_map_readback", "jurisdiction": "Las Vegas, Nevada",
            "layout": "roundabout", "map_name": "surveyed-roundabout",
            "opendrive_sha256": "a"*64, "central_island": {"polygon": "source-bound"},
            "entry_yield_control": {"kind": "yield"},
            "outer_boundary": {"polygon": "source-bound"},
            "circulatory_roadway": {"lane_ids": ["ring"]},
            "island_center": {"x": 0, "y": 0}, "connected_routes": routes}


def history(sign, case_id):
    frames = []
    for i in range(900):
        ring = 100 <= i <= 500
        angle = sign*math.radians(150)*max(0, min(1, (i-100)/400))
        frames.append({"frame": i, "time_s": i*.05, "actor_id": 17,
                       "x": 7*math.cos(angle), "y": 7*math.sin(angle),
                       "section": "ring" if ring else ("entry" if i < 100 else "exit"),
                       "lane_id": "ring" if ring else ("entry" if i < 100 else "exit")})
    return {"source_kind": "sealed_native_original_history", "case_id": case_id,
            "map_name": "surveyed-roundabout", "opendrive_sha256": "a"*64,
            "actor_role": "motor_vehicle_driver", "actor_id": 17, "frames": frames}


class DirectionTests(unittest.TestCase):
    def test_source_and_actual_direction(self):
        scratch = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c238432"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            path = Path(tmp)/"map.json"
            path.write_text(json.dumps(packet()))
            data = direction.load_source(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                                         direction.ASSIGNMENT+"__counterclockwise")
            ccw = direction.measure_history(data, history(1,direction.ASSIGNMENT+"__counterclockwise"),
                                            direction.ASSIGNMENT+"__counterclockwise")
            cw = direction.measure_history(data, history(-1,direction.ASSIGNMENT+"__clockwise"),
                                           direction.ASSIGNMENT+"__clockwise")
            self.assertEqual(ccw["observed_direction"], "counterclockwise")
            self.assertEqual(cw["observed_direction"], "clockwise")
            self.assertEqual(direction.compare(ccw,cw)["legal_judgment"], "unresolved")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                direction.load_source(path, "f"*64, ccw["case_id"])

    def test_missing_and_changed_original_rejected(self):
        p = packet()
        case = direction.ASSIGNMENT+"__counterclockwise"
        original = history(1,case)
        missing = copy.deepcopy(original)
        del missing["frames"][400]
        with self.assertRaisesRegex(ValueError, "complete original"):
            direction.measure_history(p,missing,case)
        wrong_map = copy.deepcopy(original)
        wrong_map["opendrive_sha256"] = "b"*64
        with self.assertRaisesRegex(ValueError, "map binding"):
            direction.measure_history(p,wrong_map,case)
        wrong_role = copy.deepcopy(original)
        wrong_role["actor_role"] = "pedestrian"
        with self.assertRaisesRegex(ValueError, "operator identity"):
            direction.measure_history(p,wrong_role,case)

    def test_requested_label_does_not_control_measurement(self):
        p = packet()
        case = direction.ASSIGNMENT+"__counterclockwise"
        measured = direction.measure_history(p,history(-1,case),case)
        self.assertEqual(measured["requested_direction"],"counterclockwise")
        self.assertEqual(measured["observed_direction"],"clockwise")

    def test_original_native_frame_offset(self):
        p=packet()
        case=direction.ASSIGNMENT+"__clockwise"
        original=history(-1,case)
        for row in original["frames"]:
            row["frame"] += 38033
            row["time_s"] += 20.0
        measured=direction.measure_history(p,original,case)
        self.assertEqual(measured["observed_direction"],"clockwise")


if __name__ == "__main__":
    unittest.main()
