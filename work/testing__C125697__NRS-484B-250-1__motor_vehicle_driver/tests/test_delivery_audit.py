import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import delivery_audit
from test_saved_comparison import attempt


def staged(root, suffix="precedence", ego_entry=60):
    attempt(root, suffix, ego_entry)
    original = json.loads((root / "native_trace.json").read_text())
    rows = original["frames"]
    (root / "crossing_history.jsonl").write_text("".join(json.dumps({
        "frame": row["native_frame_id"], "time_s": row["native_elapsed_seconds"],
        "ego_vertices_m": row["ego"]["body_vertices_xy_m"]}) + "\n"
        for row in rows))
    (root / "original-source-manifest.json").write_text((root / "source-manifest.json").read_text())
    (root / "trace.jsonl").write_text("".join(json.dumps({
        "frame": row["native_frame_id"], "time_s": row["native_elapsed_seconds"]}) + "\n"
        for row in rows))
    (root / "video_frames.jsonl").write_text("".join(json.dumps({
        "video_frame": i, "carla_frame": row["native_frame_id"],
        "time_s": row["native_elapsed_seconds"]}) + "\n"
        for i, row in enumerate(rows)))
    return original["case_id"]


class DeliveryAuditTests(unittest.TestCase):
    def test_full_decode_and_original_png_pixel_join(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = []
            for index in range(3):
                image = Image.new("RGB", (32, 18))
                image.putdata([((x * 7 + index * 9) % 256,
                                (y * 13 + index * 11) % 256,
                                (x * 5 + y * 3) % 256)
                               for y in range(18) for x in range(32)])
                path = root / f"sample-overview-{index:06d}.png"
                image.save(path)
                samples.append(path)
            rows = [{"video_frame": index, "carla_frame": 100 + index,
                     "time_s": index / 20} for index in range(3)]
            (root / "frame-map-overview.json").write_text(json.dumps(rows) + "\n")
            (root / "video_frames.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-framerate", "20", "-i", str(root / "sample-overview-%06d.png"),
                            "-c:v", "ffv1", str(root / "overview.mkv")], check=True)
            value = delivery_audit._pixels(root, "overview", 3, (32, 18))
            self.assertEqual(value["frame_count"], 3)
            image = Image.open(samples[1]).convert("RGB")
            image.putpixel((10, 10), (0, 0, 0))
            image.save(samples[1])
            with self.assertRaisesRegex(ValueError, "PNG/video pixel join differs"):
                delivery_audit._pixels(root, "overview", 3, (32, 18))
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-framerate", "20", "-i", str(root / "sample-overview-%06d.png"),
                            "-frames:v", "2", "-c:v", "ffv1", str(root / "short.mkv")],
                           check=True)
            (root / "overview.mkv").write_bytes((root / "short.mkv").read_bytes())
            with self.assertRaisesRegex(ValueError, "full decode incomplete"):
                delivery_audit._pixels(root, "overview", 3, (32, 18))
            samples[1].unlink()
            with self.assertRaisesRegex(ValueError, "sealed original missing or changed"):
                delivery_audit._pixels(root, "overview", 3, (32, 18))

    def test_independent_original_source_join_and_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "attempt"
            case = staged(root)
            proof = delivery_audit.audit_sources(root, case)
            self.assertTrue(proof["observations"]["ego_waited_until_other_exit"])
            (root / "overview.mkv").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "sealed original missing or changed"):
                delivery_audit.audit_sources(root, case)
            (root / "overview.mkv").write_bytes(b"overview")
            highway = json.loads((root / "highway_identity.json").read_text())
            highway["ego_highway"] = "changed"
            (root / "highway_identity.json").write_text(json.dumps(highway))
            with self.assertRaisesRegex(ValueError, "public-highway source differs"):
                delivery_audit.audit_sources(root, case)

    def test_diagnostic_never_passes_native_delivery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "attempt"
            case = staged(root)
            (root / "fixture-provenance.json").write_text(json.dumps({
                "diagnostic_fixture": True}))
            with self.assertRaisesRegex(ValueError, "diagnostic fixture cannot"):
                delivery_audit.audit_delivery(root, root / "missing.json", case)


if __name__ == "__main__":
    unittest.main()
