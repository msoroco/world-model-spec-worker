import subprocess
import sys
import unittest
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from ray_inventory import sample_approaches, original_rays
from context_review import assemble, sha


class ExactPrimaryOffline(unittest.TestCase):
    def test_case_and_capture_contract(self):
        subprocess.run([sys.executable, "runner.py", "--check"], check=True)

    def test_source_bound_sight_speed(self):
        subprocess.run([sys.executable, "prove_sight_speed_measure.py"], check=True)

    def test_four_camera_saved_source(self):
        subprocess.run([sys.executable, "prove_saved_source.py"], check=True)

    def test_native_capture_source_is_cpu_parseable(self):
        source = Path("native_capture.py").read_text()
        ast.parse(source)
        assert "for i in range(600)" in source
        assert "world.tick()" in source
        assert "native-ego-readback.jsonl" in source

    def test_original_sight_ray_inventory_and_ambiguous_lane_rejection(self):
        def point(x):
            return SimpleNamespace(transform=SimpleNamespace(location=SimpleNamespace(x=x, y=0, z=0)))
        class Entry:
            def __init__(self, road):
                self.road_id, self.lane_id, self.transform = road, 1, point(0).transform
                self.ambiguous = False
            def previous(self, meters):
                return [point(-meters)] * (2 if self.ambiguous else 1)
        left, right = Entry(1), Entry(2)
        junction = SimpleNamespace(get_waypoints=lambda _: [(left, point(0)), (right, point(0))])
        samples = sample_approaches(junction, object())
        assert set(samples) == {"1:1", "2:1"}
        assert all([row["distance_from_intersection_ft"] for row in points] == [0, 50, 100]
                   for points in samples.values())
        native = SimpleNamespace(Location=lambda **kw: SimpleNamespace(**kw))
        world = SimpleNamespace(cast_ray=lambda eye, endpoint: [
            SimpleNamespace(location=endpoint, label="Buildings")])
        rays = original_rays(world, native, SimpleNamespace(x=0, y=0, z=1), [[3, 4, 1]])
        assert rays[0]["ray_length_m"] == 5
        assert rays[0]["hits"][0]["label"] == "Buildings"
        left.ambiguous = True
        with self.assertRaisesRegex(ValueError, "unresolved entering lane geometry"):
            sample_approaches(junction, object())

    def test_source_bound_review_assembly(self):
        root = Path(os.environ["TMPDIR"]).resolve()
        with tempfile.TemporaryDirectory(prefix="c24758-review-", dir=root) as td:
            attempt = Path(td)
            case = "training__C24758__LVMC-11-16-040__motor_vehicle_driver__reference"
            (attempt / "native-map-readback.xodr").write_text("<OpenDRIVE/>")
            context = {"assignment_id": case.rsplit("__", 1)[0], "case_id": case,
                       "native_map_sha256": sha(attempt / "native-map-readback.xodr"),
                       "junction_id": 1,
                       "entering_approach_ray_targets": {"2:1": [], "3:1": []}}
            (attempt / "native-context-readback.json").write_text(json.dumps(context))
            mapped, raw, reviewed = [], [], []
            rays = [{"target_xyz_m": [0, 0, 0], "ray_length_m": 1, "hits": []}] * 7
            ray_sha = hashlib.sha256(json.dumps(rays, sort_keys=True).encode()).hexdigest()
            rgb = {name: "a" * 64 for name in
                   ("overview", "approach", "reference_corner", "driver_reference")}
            for i in range(600):
                distance = 45 - 0.15 * i
                mapped.append({"video_frame": i, "native_frame": 1000 + i,
                               "time_s": i / 20, "original_rgb_sha256": rgb})
                raw.append({"video_frame": i, "native_frame": 1000 + i,
                            "ego_speed_mps": 6.2, "distance_to_boundary_euclidean_m": max(0, distance),
                            "ego_native_junction_id": 1 if i >= 300 else None,
                            "original_native_sight_rays": rays})
                reviewed.append({"frame": i, "native_frame": 1000 + i,
                                 "sight_ray_sha256": ray_sha, "camera_rgb_sha256": rgb,
                                 "distance_to_boundary_m": distance,
                                 "intersection_clear_100ft": False,
                                 "entering_approach_views": {
                                     key: {"clear_100ft": False, "traffic_visible_100ft": False}
                                     for key in ("2:1", "3:1")}})
            (attempt / "frame-map.json").write_text(json.dumps(mapped))
            (attempt / "native-ego-readback.jsonl").write_text(
                "\n".join(json.dumps(row) for row in raw) + "\n")
            names = ("frame-map.json", "native-ego-readback.jsonl",
                     "native-context-readback.json", "native-map-readback.xodr")
            review = {"assignment_id": context["assignment_id"], "case_id": case,
                      "source_sha256": {name: sha(attempt / name) for name in names},
                      "reviewer": {"id": "cpu_fixture_reviewer", "method": "source pixel and ray audit fixture"},
                      "exceptions": {key: {"value": False, "source": "native-map-readback.xodr",
                                           "reviewed_by": "cpu_fixture_reviewer"}
                                     for key in ("through_street", "traffic_controlled_intersection")},
                      "frames": reviewed}
            path = attempt / "review.json"
            path.write_text(json.dumps(review))
            result = assemble(attempt, path, attempt / "observation.json")
            assert result["frame_count"] == 600
            assert result["sight_limited_frame_count"] > 0
            review["frames"][300]["sight_ray_sha256"] = "0" * 64
            path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "review sight-ray binding mismatch"):
                assemble(attempt, path, attempt / "invalid.json")


if __name__ == "__main__":
    unittest.main()
