"""Synthetic byte streams exercise source joins; no Native run is claimed."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_source import analyze, CAMERAS, ASSIGNMENT
from overtake_finalizer import finalize
from test_overtake_geometry import frame


def put(root, name, value):
    path = root / name
    path.write_text(value)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(rows):
    return "".join(json.dumps(row) + "\n" for row in rows)


class SourceTests(unittest.TestCase):
    def fixture(self, root):
        case_id = ASSIGNMENT + "__observed_gives_way_holds_speed"
        put(root, "config.json", json.dumps({"selected_case_id": case_id,
            "law_id": "NRS-484B-207-2", "cell_id": "C230259", "actor": "motor_vehicle_driver"}))
        bodies = [frame(i, x) for i, x in enumerate((-2., 0., 2.))]
        digests = {}
        digests["overtake_site_original.json"] = put(root, "overtake_site_original.json", "synthetic site test")
        digests["overtake_bodies_original.jsonl"] = put(root, "overtake_bodies_original.jsonl", jsonl(bodies))
        digests["trace.jsonl"] = put(root, "trace.jsonl", jsonl(
            {"frame": row["frame"], "time_s": row["time_s"]} for row in bodies))
        digests["video_frames.jsonl"] = put(root, "video_frames.jsonl", jsonl(
            {"video_frame": i, "native_frame": row["frame"], "time_s": row["time_s"]}
            for i, row in enumerate(bodies)))
        for name in CAMERAS:
            digests[name + ".mkv"] = put(root, name + ".mkv", "synthetic bytes; never a recording")
            digests[name + "-frames.jsonl"] = put(root, name + "-frames.jsonl", jsonl(
                {"video_frame": i, "native_frame": row["frame"], "time_s": row["time_s"]}
                for i, row in enumerate(bodies)))
        put(root, "overtake_source_receipt.json", json.dumps({"case_id": case_id,
            "source_kind": "original_native_capture", "source_sha256": digests,
            "site_sha256": digests["overtake_site_original.json"],
            "ego_actor_id": "ego", "overtaker_actor_id": "passing"}))
        return bodies

    def test_original_sources_join_to_geometry_without_perception_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            result = analyze(root)
            self.assertEqual(result["geometry"]["first_complete_frame"], 102)
            self.assertIsNone(result["source_notice"])
            self.assertFalse(result["physical_acceptance_claimed"])

    def test_saved_finalizer_derives_source_bound_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            report = finalize(root)
            self.assertEqual(set(report["measurements"]), {
                "full_body_pass_gap_m", "ego_right_shift_m", "ego_speed_mps",
                "overtaker_lateral_offset_right_m", "notice_source_context",
                "right_pass_permission_context"})
            source = json.loads((root / "notice_source_context.jsonl").read_text().splitlines()[0])
            self.assertIsNone(source["value"]["subjective_observation_confirmed"])
            self.assertIsNone(source["value"]["subjective_hearing_confirmed"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                finalize(root)

    def test_rejects_changed_camera_bytes_and_frame_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / "overview.mkv").write_text("changed")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                analyze(root)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "overview-frames.jsonl").read_text().splitlines()]
            rows[1]["native_frame"] = 999
            receipt = json.loads((root / "overtake_source_receipt.json").read_text())
            receipt["source_sha256"]["overview-frames.jsonl"] = put(root, "overview-frames.jsonl", jsonl(rows))
            put(root, "overtake_source_receipt.json", json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "camera frame join differs"):
                analyze(root)

    def test_rejects_missing_original_and_changed_participant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bodies = self.fixture(root)
            (root / "driver_reference.mkv").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                analyze(root)
            self.fixture(root)
            bodies[1]["overtaker"]["id"] = "different"
            receipt = json.loads((root / "overtake_source_receipt.json").read_text())
            receipt["source_sha256"]["overtake_bodies_original.jsonl"] = put(
                root, "overtake_bodies_original.jsonl", jsonl(bodies))
            put(root, "overtake_source_receipt.json", json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "identity changed"):
                analyze(root)


if __name__ == "__main__":
    unittest.main()
