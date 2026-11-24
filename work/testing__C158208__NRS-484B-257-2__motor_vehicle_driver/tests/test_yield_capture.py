import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("yield_capture", ROOT / "yield_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
measure_spec = importlib.util.spec_from_file_location("yield_entry_measurements", ROOT / "yield_entry_measurements.py")
measure = importlib.util.module_from_spec(measure_spec)
measure_spec.loader.exec_module(measure)
review_spec = importlib.util.spec_from_file_location("prepare_review", ROOT / "prepare_review.py")
prepare = importlib.util.module_from_spec(review_spec)
review_spec.loader.exec_module(prepare)


class Body:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.x = x
        self.bounding_box = NS(get_world_vertices=self.vertices)

    def vertices(self, transform):
        return [NS(x=self.x + dx, y=dy, z=z)
                for dx, dy in ((-1, -1), (-1, 1), (1, 1), (1, -1)) for z in (0, 1)]

    def get_transform(self):
        return None

    def get_velocity(self):
        return NS(x=3.0, y=0.0, z=0.0)


class CaptureTests(unittest.TestCase):
    def inputs(self):
        context = {"native_yield_sign_id": 25, "ego_entrance_device": "yield",
                   "non_through_highway": True, "ego_approach_road_id": 7}
        review = {"method": "original_source_camera_frame_review",
                  "reviewer": "CPU diagnostic fixture, no physical claim",
                  "native_yield_sign_id": 25, "sign_face_observed": "yield",
                  "proper_sign_judgment": "unresolved",
                  "marked_stop_line_observed": True, "near_crosswalk_observed": False,
                  "reference_boundary": {"source": "marked_stop_line",
                                         "origin_xy_m": [10, 0], "ego_forward_xy": [1, 0]}}
        return context, review

    def test_native_body_and_all_cameras_share_same_tick(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context, review = self.inputs()
            ego, other, sign = Body(1, 5), Body(2, 12), NS(id=25)
            writer = capture.EntrySourceWriter(root, context, review, ego, other, sign)
            snapshot = NS(frame=100)
            world = NS(get_snapshot=lambda: snapshot)
            cameras = {name: 100 for name in capture.CAMERAS}
            writer.add(world, 100, 1.0, cameras)
            ego.x = 12
            snapshot.frame = 101
            with self.assertRaisesRegex(ValueError, "Camera callback frame"):
                writer.add(world, 101, 1.05, cameras)
            cameras = {name: 101 for name in capture.CAMERAS}
            writer.add(world, 101, 1.05, cameras)
            rows = [json.loads(line) for line in (root / "entry_history.jsonl").read_text().splitlines()]
            joins = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertTrue(rows[0]["ego_body_before_yield_reference"])
            self.assertFalse(rows[1]["ego_body_before_yield_reference"])
            self.assertEqual([row["carla_frame"] for row in joins], [100, 101])
            with self.assertRaisesRegex(ValueError, "monotone"):
                writer.add(world, 101, 1.1, cameras)
            for name in capture.CAMERAS:
                (root / (name + ".mkv")).write_text("synthetic hash-binding fixture " + name)
            draft = prepare.template(root)
            self.assertEqual(draft["reviewed_carla_frames"], [100, 101])
            with self.assertRaisesRegex(ValueError, "explicit original-camera sign review"):
                capture.bind_site_review(root, draft)
            review["intersection_context_sha256"] = hashlib.sha256((root / "intersection_context.json").read_bytes()).hexdigest()
            review["camera_sha256"] = {name: hashlib.sha256((root / (name + ".mkv")).read_bytes()).hexdigest()
                                       for name in capture.CAMERAS}
            review["reviewed_carla_frames"] = [100, 101]
            review["reviewed_frame_count"] = 2
            review["camera_sha256"]["overview"] = "stale"
            with self.assertRaisesRegex(ValueError, "source or frame coverage"):
                capture.bind_site_review(root, review)
            review["camera_sha256"] = draft["camera_sha256"]
            bound = capture.bind_site_review(root, review)
            self.assertEqual(bound["reviewed_carla_frames"], [100, 101])
            self.assertEqual(set(bound["camera_sha256"]), set(capture.CAMERAS))

    def test_reference_boundary_must_match_ordered_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            context, review = self.inputs()
            review["marked_stop_line_observed"] = False
            with self.assertRaisesRegex(ValueError, "ordered source review"):
                capture.EntrySourceWriter(tmp, context, review, Body(1, 5), Body(2, 12), NS(id=25))
            review["reference_boundary"]["source"] = "nearest_view_point"
            review["nearest_view_point_xy_m"] = [9, 0]
            with self.assertRaisesRegex(ValueError, "differs from reviewed point"):
                capture.EntrySourceWriter(tmp, context, review, Body(1, 5), Body(2, 12), NS(id=25))

    def test_capture_sources_feed_saved_measurement_without_reconstructed_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context, review = self.inputs()
            context.update(native_map_id="TownX", intersection_id=44, other_approach_road_id=9,
                           sign_governance_source="native-trigger-and-camera",
                           entrance_inventory_source="all-entrance-map-and-camera",
                           yield_reference_source="reviewed-original-camera-boundary",
                           highway_status_source="reviewed-road-status",
                           police_control=False, traffic_signal_control=False,
                           entrance_road_ids=[7, 9, 11],
                           entrances=[{"road_id": 7, "device": "yield"},
                                      {"road_id": 9, "device": "none"},
                                      {"road_id": 11, "device": "none"}],
                           intersection_polygon_xy_m=[[10, -5], [20, -5], [20, 5], [10, 5]])
            ego, other = Body(1, 4), Body(2, 12)
            writer = capture.EntrySourceWriter(root, context, review, ego, other, NS(id=25))
            snapshot = NS(frame=100)
            world = NS(get_snapshot=lambda: snapshot)
            for frame, x in ((100, 4), (101, 8), (102, 12)):
                snapshot.frame, ego.x = frame, x
                writer.add(world, frame, frame / 20, {name: frame for name in capture.CAMERAS})
            for name in capture.CAMERAS:
                (root / (name + ".mkv")).write_text("synthetic join fixture " + name)
            review["intersection_context_sha256"] = hashlib.sha256((root / "intersection_context.json").read_bytes()).hexdigest()
            review["camera_sha256"] = {name: hashlib.sha256((root / (name + ".mkv")).read_bytes()).hexdigest()
                                       for name in capture.CAMERAS}
            review["reviewed_carla_frames"] = [100, 101, 102]
            review["reviewed_frame_count"] = 3
            capture.bind_site_review(root, review)
            observed = measure.analyze(root)
            self.assertEqual(observed["first_ego_entry"]["frame"], 102)
            self.assertTrue(observed["other_inside_at_ego_entry"])
            self.assertEqual(observed["subsection_one_reference"]["reference_kind"], "marked_stop_line")
            self.assertEqual(observed["legal_conclusion"], "unresolved")


if __name__ == "__main__":
    unittest.main()
