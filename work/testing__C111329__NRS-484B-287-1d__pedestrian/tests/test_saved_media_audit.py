import copy
import hashlib
import io
import pathlib
import sys
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import CAMERAS, acquire
from native_crossing import digest
from saved_media_audit import audit_camera_sources, inventory_camera_sources
from test_native_acquisition import Adapter, site


class SavedMediaAuditTests(unittest.TestCase):
    def make_sources(self, root, packet):
        sources = []
        for row in packet["rows"]:
            frame = row["original_frame"]
            for camera in CAMERAS:
                rel = f"{camera}/{frame:06d}.png"
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                image = Image.new("RGB", (4, 3), (frame * 20, len(camera) * 25, 80))
                image.putpixel((1, 1), (255, frame * 10, len(camera)))
                image.save(path, format="PNG")
                sources.append({"original_frame": frame, "camera": camera,
                                "path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return {"format": "crossing-original-camera-png-v1", "case_id": packet["case_id"],
                "native_rows_sha256": packet["rows_sha256"], "sources": sources}

    def setUp(self):
        s = site()
        self.packet = acquire(Adapter(), site=s, site_sha256=digest(s), case_id="diagnostic-exact-case",
                              route_kind="opposite", authorization=True,
                              blueprint_id="walker.pedestrian.0001", frames=3)

    def test_full_decode_all_original_images(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            manifest = self.make_sources(root, self.packet)
            self.assertEqual(inventory_camera_sources(self.packet, root), manifest)
            receipt = audit_camera_sources(self.packet, manifest, root, allow_diagnostic=True)
            self.assertEqual(receipt["decoded_png_count"], 12)
            self.assertEqual(receipt["frame_count"], 3)
            self.assertEqual(receipt["camera_dimensions"], {name: [4, 3] for name in CAMERAS})
            self.assertEqual(len(receipt["decoded_pixel_sha256"]), 64)
            with self.assertRaisesRegex(ValueError, "diagnostic"):
                audit_camera_sources(self.packet, manifest, root)

    def test_native_png_writer_binds_saved_bytes(self):
        class PNGAdapter(Adapter):
            def camera_png(self, camera, frame):
                image = Image.new("RGB", (4, 3), (frame * 20, len(camera) * 25, 80))
                image.putpixel((1, 1), (255, frame * 10, len(camera)))
                out = io.BytesIO()
                image.save(out, format="PNG")
                return out.getvalue()

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            s = site()
            packet = acquire(PNGAdapter(), site=s, site_sha256=digest(s), case_id="diagnostic-exact-case",
                             route_kind="opposite", authorization=True,
                             blueprint_id="walker.pedestrian.0001", frames=3, capture_root=root)
            manifest = inventory_camera_sources(packet, root)
            receipt = audit_camera_sources(packet, manifest, root, allow_diagnostic=True)
            self.assertEqual(receipt["decoded_png_count"], 12)
            path = root / manifest["sources"][0]["path"]
            path.write_bytes(path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "Native source hash"):
                inventory_camera_sources(packet, root)

    def test_rejects_missing_duplicate_and_cross_frame_images(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            original = self.make_sources(root, self.packet)
            for mutation, expected in (("missing", "count"), ("duplicate", "coverage"),
                                       ("frame", "coverage"), ("native", "binding")):
                manifest = copy.deepcopy(original)
                if mutation == "missing": manifest["sources"].pop()
                if mutation == "duplicate": manifest["sources"][1] = manifest["sources"][0]
                if mutation == "frame": manifest["sources"][1]["original_frame"] = 99
                if mutation == "native": manifest["native_rows_sha256"] = "0" * 64
                with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, expected):
                    audit_camera_sources(self.packet, manifest, root, allow_diagnostic=True)

    def test_rejects_tamper_and_bad_pixels(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            manifest = self.make_sources(root, self.packet)
            path = root / manifest["sources"][0]["path"]
            path.write_bytes(b"not an image")
            with self.assertRaisesRegex(ValueError, "hash"):
                audit_camera_sources(self.packet, manifest, root, allow_diagnostic=True)
            manifest["sources"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "decode"):
                audit_camera_sources(self.packet, manifest, root, allow_diagnostic=True)


if __name__ == "__main__": unittest.main()
