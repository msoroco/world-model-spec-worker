"""Exercise finalization and comparison from complete source-shaped diagnostic packets."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from compare_saved import compare
from delivery_audit import CAMERAS, audit_saved
from saved_finalizer import build_result
from test_saved_measurement import SavedMeasurementTests


class BoundSavedPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def packet(self, suffix, blocked):
        fixture = SavedMeasurementTests("test_blocked_intervening_lane_use_and_return")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.case_id = ROOT.name + "__" + suffix
        fixture.area_blocked = blocked
        fixture._write_fixture()
        for name in ("video_frames.jsonl", "pedestrian_history.jsonl",
                     "obstruction_history.jsonl", "traffic_history.jsonl"):
            old = [json.loads(line) for line in (fixture.root / name).read_text().splitlines()]
            rows = []
            for i in range(900):
                row = dict(old[min(6, i * 7 // 900)])
                row.update(time_s=1 + i * .05)
                if name == "video_frames.jsonl":
                    row.update(carla_frame=500 + i, video_frame=i)
                else:
                    row.update(frame=500 + i)
                rows.append(row)
            (fixture.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        fixture._seal()
        packet_path = fixture.root / "source-packet.json"
        packet = json.loads(packet_path.read_text())
        packet["camera_media"] = {}
        for name in CAMERAS:
            media = fixture.root / (name + ".mp4")
            shutil.copyfile(self.base / "diagnostic.mp4", media)
            packet["camera_media"][name] = {
                "path": media.name, "sha256": hashlib.sha256(media.read_bytes()).hexdigest(),
                "frame_count": 900, "fps": 20,
            }
        packet_path.write_text(json.dumps(packet) + "\n")
        return fixture.root, fixture.case_id

    def test_two_saved_attempts_finalize_audit_and_compare(self):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=16x16:r=20", "-frames:v", "900",
                        "-an", "-c:v", "mpeg4", str(self.base / "diagnostic.mp4")],
                       check=True, capture_output=True)
        first, first_id = self.packet("clear_intervening", False)
        second, second_id = self.packet("blocked_intervening", True)
        for root, case in ((first, first_id), (second, second_id)):
            audit = audit_saved(root, case, diagnostic=True, decode_media=True)
            self.assertTrue(audit["checks"]["full_video_decode"])
            self.assertFalse(audit["checks"]["physical_completion"])
            result = build_result(root, case, diagnostic=True, decode_media=True)
            self.assertEqual(result["source_kind"], "synthetic_fixture")
            self.assertTrue(all(item["matched"] for item in result["target_checks"]))
            with self.assertRaisesRegex(ValueError, "original saved acquisition"):
                build_result(root, case)
        receipt = compare(ROOT / "case-plan.json", "intervening_area_condition",
                          first, second, diagnostic=True)
        self.assertEqual(receipt["findings"][0]["observed_differences"],
                         ["designated_lane_used", "intervening_barrier_present"])
        self.assertFalse(receipt["delivery_acceptance_claimed"])
        with self.assertRaisesRegex(ValueError, "original saved acquisition"):
            compare(ROOT / "case-plan.json", "intervening_area_condition", first, second)


if __name__ == "__main__":
    unittest.main()
