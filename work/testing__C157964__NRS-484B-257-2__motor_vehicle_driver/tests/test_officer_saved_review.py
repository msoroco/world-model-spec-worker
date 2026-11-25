import hashlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import officer_saved_review as SAVED
from officer_direction import PREFIX


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root):
    bindings = {}
    for name in ("road", "sign_inventory", "officer_authority", "officer_control",
                 "other_route", "camera_sight_review"):
        path = root / (name + ".txt")
        path.write_text("reviewed CPU fixture " + name)
        bindings[name] = {"path": path.name, "sha256": sha(path)}
    return write(root / "packet.json", {
        "format": "worker-officer-subsection-2-source-review", "site_id": "test-site",
        "sources": bindings, "review": {
            "site_id": "test-site", "non_through_highway": True,
            "ego_entrance_id": "ego", "other_entrance_id": "other",
            "entrances": [{"entrance_id": "ego", "device": "stop", "sign_visible": True},
                          {"entrance_id": "other", "device": "none", "sign_visible": True}],
            "officer_authority_reviewed": True, "officer_control_reviewed": True,
            "original_camera_sight_reviewed": True,
            "intersection_polygon_xy_m": [[-5, -5], [5, -5], [5, 5], [-5, 5]]}})


def body(x):
    return [[x, -1], [x + 1, -1], [x + 1, 1], [x, 1]]


def capture_and_review(root, packet, case_id=PREFIX + "officer_controls_go",
                       ego_positions=(-9, -4, -3)):
    camera_names = ("overview", "approach", "reference_corner", "driver_reference")
    for name in camera_names:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=black:s=4x4:r=20",
                        "-frames:v", "3", "-c:v", "ffv1", "-level", "3",
                        "-pix_fmt", "bgr0", str(root / (name + ".mkv"))],
                       check=True, capture_output=True)
    rows, observations = [], []
    for index, x in enumerate(ego_positions):
        frame = 100 + index
        refs = {name: name + ".mkv#frame-" + str(index) for name in camera_names}
        rows.append({"carla_frame": frame, "native_actor_source": {
            "frame": frame, "time_s": frame * 0.05, "officer_actor_id": 12,
            "programmed_direction": "stop", "native_pose_applied": True,
            "camera_raw_sources": refs,
            "ego": {"actor_id": 11, "speed_mps": 1.0, "body_vertices_xy_m": body(x)},
            "other": {"actor_id": 33, "speed_mps": 0.0,
                      "body_vertices_xy_m": body(0)}}})
        observations.append({"carla_frame": frame, "officer_actor_id": 12,
                             "direction_frame_source": refs["approach"],
                             "uniform_frame_source": refs["overview"],
                             "control_frame_source": refs["reference_corner"],
                             "other_frame_source": refs["overview"],
                             "other_approaching_observed": False,
                             "officer_direction_observed": "go",
                             "traffic_control_observed": True})
    capture = write(root / "capture.json", {
        "format": "worker-officer-subsection-2-native-capture", "site_id": "test-site",
        "case_id": case_id, "source_packet_sha256": sha(packet),
        "frame_count": len(rows), "rows": rows})
    review = write(root / "review.json", {
        "format": "worker-officer-subsection-2-original-frame-review",
        "site_id": "test-site", "case_id": case_id, "reviewer": "CPU fixture reviewer",
        "capture_sha256": sha(capture), "source_packet_sha256": sha(packet),
        "camera_sha256": {name: sha(root / (name + ".mkv")) for name in camera_names},
        "frames": observations})
    return capture, review


class SavedReviewTests(unittest.TestCase):
    def test_reviewed_original_frames_drive_entry_observation(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet)
            result = SAVED.process(capture, review, root, packet, root / "saved",
                                   native_map_id="CPU-map", intersection_id=1)
            self.assertEqual(result["first_ego_entry"]["frame"], 101)
            self.assertEqual(result["first_ego_entry"]["officer_direction_observed"], "go")
            self.assertEqual(result["subsection_2_applicability"],
                             "officer_control_exception_candidate")
            self.assertEqual(result["legal_conclusion"], "unresolved")
            self.assertFalse(result["other_approaching_observed_at_ego_entry"])
            self.assertEqual(result["capture_sha256"], sha(capture))
            self.assertEqual([check["matched"] for check in result["target_checks"]],
                             [True, True])
            context = json.loads((root / "saved" / "officer_context.json").read_text())
            self.assertEqual(context["direction_video_source"], "approach.mkv#frame-0")
            history = [json.loads(line) for line in
                       (root / "saved" / "officer_history.jsonl").read_text().splitlines()]
            self.assertEqual([row["officer_direction_observed"] for row in history],
                             ["go", "go", "go"])

    def test_changed_capture_and_unbound_camera_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet)
            value = json.loads(capture.read_text())
            value["rows"][0]["native_actor_source"]["programmed_direction"] = "go"
            write(capture, value)
            with self.assertRaisesRegex(ValueError, "review binding missing"):
                SAVED.process(capture, review, root, packet, root / "saved",
                              native_map_id="CPU-map", intersection_id=1)
            self.assertFalse((root / "saved").exists())
            capture, review = capture_and_review(root, packet)
            value = json.loads(review.read_text())
            value["frames"][1]["direction_frame_source"] = "unbound.mkv#frame-1"
            write(review, value)
            with self.assertRaisesRegex(ValueError, "differs from Native sources"):
                SAVED.process(capture, review, root, packet, root / "saved",
                              native_map_id="CPU-map", intersection_id=1)
            self.assertFalse((root / "saved").exists())

    def test_changed_site_source_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet)
            (root / "road.txt").write_text("changed")
            with self.assertRaisesRegex(ValueError, "Changed source file: road"):
                SAVED.process(capture, review, root, packet, root / "saved",
                              native_map_id="CPU-map", intersection_id=1)

    def test_changed_camera_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet)
            with (root / "approach.mkv").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "Original camera bytes differ: approach"):
                SAVED.process(capture, review, root, packet, root / "saved",
                              native_map_id="CPU-map", intersection_id=1)
            self.assertFalse((root / "saved").exists())

    def test_approaching_vehicle_review_keeps_hazard_judgment_open(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet)
            value = json.loads(review.read_text())
            value["frames"][1]["other_approaching_observed"] = True
            write(review, value)
            result = SAVED.process(capture, review, root, packet, root / "saved",
                                   native_map_id="CPU-map", intersection_id=1)
            self.assertTrue(result["other_approaching_observed_at_ego_entry"])
            self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_missing_other_frame_review_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet)
            value = json.loads(review.read_text())
            del value["frames"][1]["other_frame_source"]
            write(review, value)
            with self.assertRaisesRegex(ValueError, "differs from Native sources"):
                SAVED.process(capture, review, root, packet, root / "saved",
                              native_map_id="CPU-map", intersection_id=1)

    def test_inactive_officer_keeps_signed_entrance_candidate(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet,
                                                 PREFIX + "officer_present_inactive")
            value = json.loads(review.read_text())
            for frame in value["frames"]:
                frame["traffic_control_observed"] = False
                frame["officer_direction_observed"] = "none"
            write(review, value)
            result = SAVED.process(capture, review, root, packet, root / "saved",
                                   native_map_id="CPU-map", intersection_id=1)
            self.assertEqual(result["subsection_2_applicability"],
                             "signed_entrance_candidate")
            self.assertFalse(result["officer_control_observed_at_entry"])
            self.assertEqual(result["legal_conclusion"], "unresolved")
            self.assertEqual([check["matched"] for check in result["target_checks"]],
                             [True, True])

    def test_hold_mismatch_is_reported_as_observation(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet,
                                                 PREFIX + "officer_controls_hold")
            result = SAVED.process(capture, review, root, packet, root / "saved",
                                   native_map_id="CPU-map", intersection_id=1)
            self.assertEqual(result["target_checks"][1]["requested"], "stop")
            self.assertEqual(result["target_checks"][1]["measured"], "go")
            self.assertFalse(result["target_checks"][1]["matched"])
            self.assertFalse(result["target_checks"][2]["matched"])
            self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_source_reviewed_hold_without_ego_entry(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = sources(root)
            capture, review = capture_and_review(root, packet,
                                                 PREFIX + "officer_controls_hold",
                                                 ego_positions=(-9, -9, -9))
            value = json.loads(review.read_text())
            for frame in value["frames"]:
                frame["officer_direction_observed"] = "stop"
            write(review, value)
            result = SAVED.process(capture, review, root, packet, root / "saved",
                                   native_map_id="CPU-map", intersection_id=1)
            self.assertIsNone(result["first_ego_entry"])
            self.assertEqual(result["first_hold_observation"]["frame"], 100)
            self.assertEqual(result["subsection_2_applicability"],
                             "officer_hold_no_entry_candidate")
            self.assertEqual([check["matched"] for check in result["target_checks"]],
                             [True, True, True])


if __name__ == "__main__":
    unittest.main()
