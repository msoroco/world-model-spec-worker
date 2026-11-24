import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from saved_delivery import audit, CAMERAS, PREFIX
from test_approach import body, context


CASE = PREFIX + "near_centerline"


def original_attempt(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "intersection-context.json").write_text(json.dumps(context()))
    rows = []
    frames = []
    for index in range(900):
        phase = "approach" if index < 450 else "departure"
        rows.append({"frame": 100 + index, "time_s": index / 20,
                     "road_id": phase, "phase": phase,
                     "ego_heading_rad": 0.0 if phase == "approach" else 1.2,
                     "ego_body_vertices_xy_m": body(-0.6)})
        frames.append({"frame": 100 + index, "time_s": index / 20,
                       "camera_frames": {name: 100 + index for name in CAMERAS}})
    (path / "approach-history.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    (path / "video_frames.jsonl").write_text("".join(json.dumps(x) + "\n" for x in frames))
    acquisition = {name: {"kind": "original_native",
                          "sha256": hashlib.sha256((path / name).read_bytes()).hexdigest()}
                   for name in ("intersection-context.json", "approach-history.jsonl",
                                "video_frames.jsonl")}
    acquisition.update({"case_id": CASE, "diagnostic_fixture": True, "media": {}})
    for name in CAMERAS:
        media_path = path / (name + ".mp4")
        media_path.write_bytes((name + " diagnostic bytes").encode())
        acquisition["media"][name] = {
            "kind": "original_native", "path": media_path.name,
            "sha256": hashlib.sha256(media_path.read_bytes()).hexdigest()}
    (path / "acquisition.json").write_text(json.dumps(acquisition))
    return acquisition, rows, frames


class SavedDeliveryTests(unittest.TestCase):
    def test_complete_sealed_attempt_and_diagnostic_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            original_attempt(path)
            with self.assertRaisesRegex(ValueError, "diagnostic"):
                audit(path, CASE)
            result = audit(path, CASE, allow_diagnostic=True)
            self.assertEqual(result["frame_count"], 900)
            self.assertEqual(set(result["media_sha256"]), CAMERAS)
            self.assertTrue(result["source_integrity_passed"])
            self.assertFalse(result["actual_pixels"])
            self.assertEqual(result["legal_judgment"], "unresolved")

    def test_wrong_case_media_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            acquisition, _, _ = original_attempt(path)
            with self.assertRaisesRegex(ValueError, "case differs"):
                audit(path, PREFIX + "farther_from_centerline", allow_diagnostic=True)
            (path / "overview.mp4").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "media hash differs"):
                audit(path, CASE, allow_diagnostic=True)
            acquisition["media"]["overview"]["path"] = "../foreign.mp4"
            (path / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "outside attempt"):
                audit(path, CASE, allow_diagnostic=True)

    def test_duration_and_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            acquisition, rows, frames = original_attempt(path)
            (path / "approach-history.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in rows[:-1]))
            with self.assertRaisesRegex(ValueError, "stale original"):
                audit(path, CASE, allow_diagnostic=True)
            acquisition["approach-history.jsonl"]["sha256"] = hashlib.sha256(
                (path / "approach-history.jsonl").read_bytes()).hexdigest()
            (path / "video_frames.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in frames[:-1]))
            acquisition["video_frames.jsonl"]["sha256"] = hashlib.sha256(
                (path / "video_frames.jsonl").read_bytes()).hexdigest()
            (path / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "900-frame"):
                audit(path, CASE, allow_diagnostic=True)


if __name__ == "__main__":
    unittest.main()
