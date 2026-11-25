import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_uturn import CaptureError, capture

CASE = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver__intersection_vehicle_near"


class Actor:
    def __init__(self, identity, x):
        self.id, self.x, self.controls = identity, x, []
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda transform: [
            SimpleNamespace(x=self.x + dx, y=dy) for dx, dy in
            ((-.1, -.1), (.1, -.1), (.1, .1), (-.1, .1))])

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=0),
                               rotation=SimpleNamespace(yaw=0))

    def apply_control(self, value):
        self.controls.append(value)

    def make_brake_control(self):
        return "brake"


class World:
    def __init__(self, bad_interval=False):
        self.frame, self.bad_interval = 99, bad_interval

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=.05)

    def get_map(self):
        return SimpleNamespace(name="reviewed-map", get_waypoint=lambda loc, project_to_road:
                               SimpleNamespace(road_id=7, lane_id=1, is_junction=True,
                                               get_junction=lambda: SimpleNamespace(id=4)))

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame, timestamp=SimpleNamespace(
            elapsed_seconds=self.frame * (.1 if self.bad_interval else .05)))


class CaptureTest(unittest.TestCase):
    def invoke(self, *, world=None, mutate=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = {"case_id": CASE, "map_name": "reviewed-map", "map_sha256": "map-seal",
                    "route_sha256": "route-seal", "district_source_sha256": "district-seal",
                    "intersection_boundary": {"source_sha256": "boundary-seal",
                                              "polygon_xy_m": [[0, 0], [1, 0], [1, 1]]}}
            if mutate:
                mutate(site)
            site_path = root / "site.json"
            site_path.write_text(json.dumps(site), encoding="utf-8")
            ego, other = Actor("ego", 0), Actor("other", 5)
            out = root / "native.json"
            seal = hashlib.sha256(site_path.read_bytes()).hexdigest()
            result = capture(world or World(), ego, other, site_path, seal, CASE, out,
                             lambda a, i: a.apply_control("ego-drive"),
                             lambda a, i: a.apply_control("other-drive"),
                             lambda a: a.apply_control("brake"))
            packet = json.loads(out.read_text())
            self.assertEqual(result["sha256"], hashlib.sha256(out.read_bytes()).hexdigest())
            self.assertEqual(packet["frames"][0]["frame"], 100)
            self.assertEqual(packet["frames"][-1]["frame"], 999)
            self.assertEqual(len(packet["frames"]), 900)
            self.assertEqual(packet["site_sha256"], seal)
            self.assertEqual(ego.controls[-1], "brake")
            self.assertEqual(other.controls[-1], "brake")
            return result

    def test_original_acquisition_and_source_seal(self):
        self.invoke()

    def test_rejects_wrong_case(self):
        with self.assertRaisesRegex(CaptureError, "case identity"):
            self.invoke(mutate=lambda site: site.update(case_id="other"))

    def test_rejects_interval_drift_and_brakes(self):
        with self.assertRaisesRegex(CaptureError, "tick interval"):
            self.invoke(world=World(bad_interval=True))

    def test_rejects_unreviewed_boundary(self):
        with self.assertRaisesRegex(CaptureError, "boundary source"):
            self.invoke(mutate=lambda site: site.update(intersection_boundary={}))

    def test_camera_failure_brakes_and_does_not_publish_native(self):
        class FailedCollector:
            def read_frame(self, frame, time_s):
                raise RuntimeError("missing original camera")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = {"case_id": CASE, "map_name": "reviewed-map", "map_sha256": "map-seal",
                    "route_sha256": "route-seal", "district_source_sha256": "district-seal",
                    "intersection_boundary": {"source_sha256": "boundary-seal",
                                              "polygon_xy_m": [[0, 0], [1, 0], [1, 1]]}}
            path = root / "site.json"
            path.write_text(json.dumps(site))
            ego, other = Actor("ego", 0), Actor("other", 5)
            output = root / "native.json"
            with self.assertRaisesRegex(RuntimeError, "missing original camera"):
                capture(World(), ego, other, path, hashlib.sha256(path.read_bytes()).hexdigest(),
                        CASE, output, lambda a, i: a.apply_control("drive"),
                        lambda a, i: a.apply_control("drive"),
                        lambda a: a.apply_control("brake"), camera_collector=FailedCollector())
            self.assertFalse(output.exists())
            self.assertEqual(ego.controls[-1], "brake")
            self.assertEqual(other.controls[-1], "brake")

    def test_generic_pipeline_observes_same_900_original_ticks(self):
        class Pipeline:
            def __init__(self):
                self.frames = []
                self.confirmed = None

            def capture(self, frame, time_s):
                self.frames.append((frame, time_s))

            def close(self, confirmed):
                self.confirmed = confirmed

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = {"case_id": CASE, "map_name": "reviewed-map", "map_sha256": "map-seal",
                    "route_sha256": "route-seal", "district_source_sha256": "district-seal",
                    "intersection_boundary": {"source_sha256": "boundary-seal",
                                              "polygon_xy_m": [[0, 0], [1, 0], [1, 1]]}}
            path = root / "site.json"
            path.write_text(json.dumps(site))
            ego, other = Actor("ego", 0), Actor("other", 5)
            pipeline = Pipeline()
            capture(World(), ego, other, path, hashlib.sha256(path.read_bytes()).hexdigest(),
                    CASE, root / "native.json", lambda a, i: a.apply_control("drive"),
                    lambda a, i: a.apply_control("drive"), lambda a: a.apply_control("brake"),
                    pipeline_capture=pipeline)
            self.assertEqual([frame for frame, _ in pipeline.frames], list(range(100, 1000)))
            self.assertTrue(pipeline.confirmed)

            failed = Pipeline()
            with self.assertRaisesRegex(CaptureError, "tick interval"):
                capture(World(bad_interval=True), ego, other, path,
                        hashlib.sha256(path.read_bytes()).hexdigest(), CASE,
                        root / "failed.json", lambda a, i: a.apply_control("drive"),
                        lambda a, i: a.apply_control("drive"),
                        lambda a: a.apply_control("brake"), pipeline_capture=failed)
            self.assertFalse(failed.confirmed)
