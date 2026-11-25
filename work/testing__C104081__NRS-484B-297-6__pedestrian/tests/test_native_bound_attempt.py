"""Bind exact original survey, camera profile and traffic roster before capture."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from native_bound_attempt import run_bound_attempt


def write(path, value):
    path.write_text(json.dumps(value) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BoundAttemptTest(unittest.TestCase):
    def test_exact_source_binding_and_changed_roster_rejection(self):
        with TemporaryDirectory(dir=REPO / ".runtime-work") as scratch:
            base = Path(scratch)
            camera = base / "camera.json"
            profile_sha = write(camera, {"cameras": {
                "overview": [1920, 1080], "approach": [1280, 720],
                "reference_corner": [1280, 720], "driver_reference": [1280, 720]},
                "rate_hz": 20})
            traffic = base / "traffic.json"
            traffic_sha = write(traffic, {"actor_ids": [42]})
            survey = base / "survey.json"
            opendrive = "<OpenDRIVE><header name='surveyed-hill-road'/></OpenDRIVE>"
            (base / "synthetic-map.xodr").write_text(opendrive)
            write(survey, {"source_kind": "original_native_map_survey",
                "cell_id": "C104081", "map_id": "surveyed-hill-road",
                "layout": "hill_crest", "surfaces": {key: {"surveyed": True} for key in
                ("sidewalk", "intervening_area", "designated_bicycle_lane",
                 "immediately_adjacent_highway")},
                "local_to_world": {"x": 0, "y": 0, "yaw_degrees": 0},
                "pedestrian_blueprint": "walker.pedestrian.0001",
                "map_opendrive_sha256": hashlib.sha256(opendrive.encode()).hexdigest(),
                "reviewed_original_site": {"reviewer": "CPU test fixture only",
                    "method": "Synthetic review-field shape for hash-join test",
                    "source_refs": [{"path": "synthetic-map.xodr",
                                     "sha256": hashlib.sha256(opendrive.encode()).hexdigest()}]},
                "camera_profile_sha256": profile_sha,
                "traffic_plan_sha256": traffic_sha,
                "traffic_actor_ids": [42]})
            world = NS(get_map=lambda: NS(name="surveyed-hill-road",
                                        to_opendrive=lambda: opendrive))
            client = NS(get_world=lambda: world)
            with patch("native_bound_attempt.run_native_attempt", return_value={"bound": True}) as run:
                result = run_bound_attempt(client, object(), {}, "exact", survey,
                    camera, traffic, base / "capture", restore_api=object())
            self.assertEqual(result, {"bound": True})
            self.assertEqual(run.call_args.kwargs["camera_profile_sha256"], profile_sha)
            self.assertEqual(run.call_args.kwargs["traffic_plan_sha256"], traffic_sha)
            self.assertTrue(callable(run.call_args.kwargs["camera_rig_factory"]))
            self.assertIsNone(run.call_args.args[8])
            write(traffic, {"actor_ids": [43]})
            with self.assertRaisesRegex(ValueError, "differs from site survey"):
                run_bound_attempt(client, object(), {}, "exact", survey,
                    camera, traffic, base / "capture", restore_api=object())
            write(traffic, {"actor_ids": [42]})
            wrong_world = NS(get_map=lambda: NS(name="surveyed-hill-road",
                                               to_opendrive=lambda: opendrive + "changed"))
            with self.assertRaisesRegex(ValueError, "OpenDRIVE bytes differ"):
                run_bound_attempt(NS(get_world=lambda: wrong_world), object(), {},
                    "exact", survey, camera, traffic, base / "capture",
                    restore_api=object())


if __name__ == "__main__":
    unittest.main()
