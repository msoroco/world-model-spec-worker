import tempfile
import json
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from acquire_lane_use import actor_footprint, lane_polygon, sample, append_source
from finalize_lane_use import finalize, finalize_bound


def actor(identity, x, y, yaw=0, width=2, length=4):
    return N(id=identity,
             bounding_box=N(extent=N(x=length / 2, y=width / 2),
                            location=N(x=0, y=0), rotation=N(yaw=0)),
             get_transform=lambda: N(location=N(x=x, y=y), rotation=N(yaw=yaw)))


def road():
    transform = N(location=N(x=0, y=0),
                  get_forward_vector=lambda: N(x=1, y=0),
                  get_right_vector=lambda: N(x=0, y=1))
    waypoint = N(lane_width=4, transform=transform, road_id=12,
                 section_id=0, lane_id=-1)
    return N(get_waypoint=lambda location, project_to_road: waypoint)


class AcquisitionTest(unittest.TestCase):
    def test_actor_rotation_and_lane_map(self):
        footprint = actor_footprint(actor(1, 5, 3, yaw=90))
        self.assertAlmostEqual(min(point[0] for point in footprint), 4)
        self.assertAlmostEqual(max(point[1] for point in footprint), 5)
        polygon, source = lane_polygon(road(), actor(2, 0, 0))
        self.assertEqual(polygon, [[-15.0, -2.0], [15.0, -2.0],
                                   [15.0, 2.0], [-15.0, 2.0]])
        self.assertEqual(source["lane_id"], -1)

    def test_native_samples_flow_into_saved_finalizer(self):
        references = {"actor_trace": "trace.jsonl", "actor_bounds": "lane-use-source.jsonl",
                      "lane_map": "lane-use-source.jsonl"}
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "lane-use-source.jsonl"
            measured = Path(directory) / "lane-use-measured.jsonl"
            for frame in range(2):
                row = sample(road(), actor(1, frame, 1.5), actor(2, frame, 0, width=1),
                             frame=frame, time_s=frame / 20, source_refs=references)
                append_source(original, row)
            self.assertEqual(finalize(original, measured), 2)
            self.assertIn('"mapped_lane"', original.read_text())
            self.assertIn('"footprint_surface_gap_m"', measured.read_text())

    def test_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "source references"):
            sample(road(), actor(1, 0, 0), actor(2, 0, 0), frame=0,
                   time_s=0, source_refs={})
        with self.assertRaisesRegex(ValueError, "distinct"):
            sample(road(), actor(1, 0, 0), actor(1, 0, 0), frame=0,
                   time_s=0, source_refs={})
        with self.assertRaisesRegex(ValueError, "source mapped"):
            lane_polygon(N(get_waypoint=lambda *a, **k: None), actor(2, 0, 0))

    def test_bound_saved_join_and_negative_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            citation = root / "road-authority.json"
            citation.write_text('{"source":"operator_survey_pending_review"}\n')
            digest = hashlib.sha256(citation.read_bytes()).hexdigest()
            survey = {"source_kind": "original_native_context_survey",
                      "map_name": "Town01", "citations": [{"path": citation.name, "sha256": digest}]}
            for name in ("highway_public_maintenance_source",
                         "highway_public_vehicular_access_source",
                         "protected_vehicle_seat_source", "protected_vehicle_wheels_source",
                         "protected_vehicle_exclusions_source",
                         "subject_motor_vehicle_class_source"):
                survey[name] = citation.name
            (root / "lane-use-context.json").write_text(json.dumps(survey) + "\n")
            references = {"actor_trace": "trace.jsonl", "actor_bounds": "lane-use-source.jsonl",
                          "lane_map": "lane-use-source.jsonl"}
            sample_row = sample(road(), actor(1, 0, 1.5), actor(2, 0, 0, width=1),
                                frame=0, native_frame=25, time_s=0, source_refs=references)
            append_source(root / "lane-use-source.jsonl", sample_row)
            frame_map = {"video_frame": 0, "native_frame": 25, "time_s": 0,
                         "camera_native_frames": {name: 25 for name in
                                                  ("overview", "approach", "reference_corner",
                                                   "driver_reference")}}
            (root / "video_frames.jsonl").write_text(json.dumps(frame_map) + "\n")
            report = finalize_bound(root, root / "measured.jsonl")
            self.assertEqual(report["measured_frames"], 1)
            self.assertTrue(report["chapter_486_context_unreviewed"])
            citation.unlink()
            with self.assertRaisesRegex(ValueError, "citation missing or changed"):
                finalize_bound(root, root / "negative.jsonl")


if __name__ == "__main__":
    unittest.main()
