import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from PIL import Image


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from saved_delivery import audit, CAMERAS, PREFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.map_path = self.root / "map.json"
        self.source_map_path = self.root / "source-map.json"
        self.pose_path = self.root / "pose.jsonl"
        self.measurement_path = self.root / "measurement.json"
        self.frame_map_path = self.root / "frames.jsonl"
        self.context_path = self.root / "context.jsonl"
        self.attempt_path = self.root / "attempt.json"
        self.source_map_path.write_text(json.dumps({
            "map_name": "diagnostic-map", "opendrive_sha256": "a" * 64,
            "case_ids": [PREFIX + "stop_14ft", PREFIX + "stop_16ft"]}))
        self.map_path.write_text(json.dumps({
            "map_id": "diagnostic-map", "geometry_provenance": "CPU fixture only",
            "opendrive_sha256": "a" * 64,
            "map_source_sha256": sha(self.source_map_path),
            "intersection_boundary_local_m": {
                "west": -8, "south": -8, "east": 8, "north": 8}}))
        with self.pose_path.open("w") as out:
            for frame in range(900):
                out.write(json.dumps({
                    "frame": frame, "world_frame": 1200 + frame,
                    "time_s": frame / 20, "actor_id": "ego",
                    "x_m": 8 + 14 * 0.3048 + 2.25, "y_m": 0,
                    "heading_deg": 180, "speed_mps": 0 if frame >= 800 else 5,
                    "halt_state": frame >= 800}) + "\n")
        self.measurement_path.write_text(json.dumps({
            "actor_id": "ego", "vehicle_length_m": 4.5, "vehicle_width_m": 1.8,
            "map_source": {"path": "map.json", "sha256": sha(self.map_path)},
            "pose_source": {"path": "pose.jsonl", "sha256": sha(self.pose_path)}}))
        with self.frame_map_path.open("w") as out:
            for frame in range(900):
                out.write(json.dumps({"frame": frame, "world_frame": 1200 + frame,
                                      "time_s": frame / 20}) + "\n")
        with self.context_path.open("w") as out:
            for frame in range(900):
                out.write(json.dumps({"frame": frame, "world_frame": 1200 + frame,
                                      "participants": [], "directions": {}}) + "\n")
        cameras = {}
        for camera in CAMERAS:
            frame_template = self.root / (camera + "-template.png")
            Image.new("RGB", (2, 2), (23, 41, 59)).save(frame_template)
            png_bytes = frame_template.read_bytes()
            path = self.root / (camera + ".jsonl")
            with path.open("w") as out:
                for frame in range(900):
                    frame_path = self.root / f"{camera}-{frame:06d}.png"
                    frame_path.write_bytes(png_bytes)
                    out.write(json.dumps({"frame": frame, "world_frame": 1200 + frame,
                                          "camera": camera,
                                          "original_frame_path": frame_path.name,
                                          "original_frame_sha256": sha(frame_path)}) + "\n")
            cameras[camera] = {"path": path.name, "sha256": sha(path)}
        self.packet = {
            "case_id": PREFIX + "stop_14ft", "attempt_id": "diagnostic-attempt",
            "recording_id": "diagnostic-recording", "acquisition_kind": "diagnostic_fixture",
            "requested_front_body_gap_ft": 14,
            "measurement_packet": {"path": "measurement.json", "sha256": sha(self.measurement_path)},
            "map_packet": {"path": "source-map.json", "sha256": sha(self.source_map_path)},
            "frame_map": {"path": "frames.jsonl", "sha256": sha(self.frame_map_path)},
            "context": {"path": "context.jsonl", "sha256": sha(self.context_path)},
            "cameras": cameras}
        self.save()

    def save(self):
        self.attempt_path.write_text(json.dumps(self.packet))

    def test_full_source_join_is_explicitly_diagnostic(self):
        result = audit(self.attempt_path, allow_diagnostic=True)
        self.assertTrue(result["time_join"])
        self.assertEqual(result["original_frame_count"], 900)
        self.assertEqual(result["decoded_original_images"], 3600)
        self.assertTrue(result["original_pixels_decoded"])
        self.assertAlmostEqual(result["measurement"]["minimum_halt_body_gap_m"],
                               14 * 0.3048)
        self.assertFalse(result["physical_completion"])
        self.assertFalse(result["actual_pixels"])
        with self.assertRaisesRegex(ValueError, "Diagnostic source"):
            audit(self.attempt_path)

    def test_missing_camera_and_identity_change_rejected(self):
        del self.packet["cameras"]["approach"]
        self.save()
        with self.assertRaisesRegex(ValueError, "Four named camera"):
            audit(self.attempt_path, allow_diagnostic=True)
        self.packet["cameras"]["approach"] = {
            "path": "approach.jsonl", "sha256": sha(self.root / "approach.jsonl")}
        self.packet["case_id"] = PREFIX + "stop_16ft"
        self.save()
        with self.assertRaisesRegex(ValueError, "requested gap mismatch"):
            audit(self.attempt_path, allow_diagnostic=True)

    def test_tampered_source_and_frame_join_rejected(self):
        path = self.root / "overview.jsonl"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            audit(self.attempt_path, allow_diagnostic=True)
        self.packet["cameras"]["overview"]["sha256"] = sha(path)
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        rows[42]["world_frame"] += 1
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.packet["cameras"]["overview"]["sha256"] = sha(path)
        self.save()
        with self.assertRaisesRegex(ValueError, "world frame join"):
            audit(self.attempt_path, allow_diagnostic=True)

    def test_duplicate_frame_path_rejected_even_with_matching_hashes(self):
        path = self.root / "overview.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["original_frame_path"] = rows[0]["original_frame_path"]
        rows[1]["original_frame_sha256"] = rows[0]["original_frame_sha256"]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.packet["cameras"]["overview"]["sha256"] = sha(path)
        self.save()
        with self.assertRaisesRegex(ValueError, "reuses an original camera frame"):
            audit(self.attempt_path, allow_diagnostic=True)

    def test_corrupt_png_rejected_after_matching_hash_rebind(self):
        frame_path = self.root / "overview-000000.png"
        frame_path.write_bytes(b"\x89PNG\r\n\x1a\nnot an image")
        path = self.root / "overview.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["original_frame_sha256"] = sha(frame_path)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.packet["cameras"]["overview"]["sha256"] = sha(path)
        self.save()
        with self.assertRaisesRegex(ValueError, "cannot be decoded"):
            audit(self.attempt_path, allow_diagnostic=True)


if __name__ == "__main__":
    unittest.main()
