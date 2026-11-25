import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from media_audit import audit_media
from overpass_source import sha


SPECS = {name: (16, 16) for name in
         ("overview", "approach", "reference_corner", "driver_reference")}


def fixture(root):
    frames = [{"frame": 100 + i, "time_s": i * .05} for i in range(2)]
    joins = [{**row, "case_id": "testing__C188132__LVMC-11-30-060-B__pedestrian__yield_before_vehicle",
              "cameras": {name: {"frame": row["frame"], "width": 16, "height": 16,
                                   "pixel_format": "bgra", "bytes": 1024} for name in SPECS}}
             for row in frames]
    (root / "video_frames.jsonl").write_text(''.join(json.dumps(row) + '\n' for row in frames))
    (root / "camera-frame-joins.jsonl").write_text(''.join(json.dumps(row) + '\n' for row in joins))
    sources = {"frame_map": "video_frames.jsonl", "camera_joins": "camera-frame-joins.jsonl"}
    for name in SPECS:
        path = root / (name + ".mkv")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                        "-i", "color=c=red:s=16x16:r=20", "-frames:v", "2",
                        "-c:v", "ffv1", str(path)], check=True)
        sources["video_" + name] = path.name
    manifest = {"format": "c188132-original-sources-v1",
                **{key: {"path": value, "sha256": sha(root / value)}
                   for key, value in sources.items()}}
    (root / "original-sources.json").write_text(json.dumps(manifest))


class MediaAuditTests(unittest.TestCase):
    def test_four_complete_decodes_and_stale_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            result = audit_media(root, expected_frames=2, specs=SPECS)
            self.assertEqual(set(result["cameras"]), set(SPECS))
            self.assertTrue(all(row["full_decode_passed"] for row in result["cameras"].values()))
            (root / "overview.mkv").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "stale original camera source"):
                audit_media(root, expected_frames=2, specs=SPECS)

    def test_reject_incomplete_join_and_wrong_frame_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            with self.assertRaisesRegex(ValueError, "frame count differs"):
                audit_media(root, expected_frames=3, specs=SPECS)
            joins = root / "camera-frame-joins.jsonl"
            lines = [json.loads(line) for line in joins.read_text().splitlines()]
            del lines[0]["cameras"]["approach"]
            joins.write_text(''.join(json.dumps(row) + '\n' for row in lines))
            manifest_path = root / "original-sources.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["camera_joins"]["sha256"] = sha(joins)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "four original camera"):
                audit_media(root, expected_frames=2, specs=SPECS)


if __name__ == "__main__":
    unittest.main()
