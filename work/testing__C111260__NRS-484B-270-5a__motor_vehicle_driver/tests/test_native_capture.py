import hashlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from zipfile import ZIP_STORED, ZipFile

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
CASE = ROOT.name + "__bicycle_brake"


def waypoint(x, y, junction=None):
    return {"x_m": x, "y_m": y, "road_id": 1, "lane_id": 1,
            "junction_id": junction, "source_ref": "original-map#waypoint"}


SITE = {"map_sha256": "a" * 64, "map_source_ref": "original-map", "junction_id": 7,
        "ego_route": [waypoint(-20, 0), waypoint(0, 0, 7), waypoint(20, 0)],
        "rider_route": [waypoint(0, -20), waypoint(0, 0, 7), waypoint(0, 20)],
        "motor_vehicle": {"source_ref": "original-blueprint#ego", "blueprint_id": "vehicle.sedan",
                          "rail_bound": False},
        "rider": {"source_ref": "original-blueprint#rider", "blueprint_id": "vehicle.bicycle",
                  "person_actor_id": 42, "kind": "bicycle", "moped": False, "motorized": False,
                  "wheel_diameters_in": [26, 26]}}
BUFFER = io.BytesIO()
Image.new("RGB", (2, 2), (10, 20, 30)).save(BUFFER, format="PNG")
PIXEL = BUFFER.getvalue()


def callbacks(*, missing=None, frame_jump=False):
    count = iter(range(900))

    def tick():
        index = next(count)
        return 100 + index + (1 if frame_jump and index == 10 else 0)

    def sample(frame):
        return {"source": "original_native", "case_id": CASE, "map_sha256": "a" * 64,
                "frame": frame, "time_s": (frame - 100) * 0.05,
                "ego_actor_id": 1, "rider_actor_id": 2,
                "rider_kind_observed": "bicycle", "rider_mounted_observed": True,
                "surface_gap_m": 3.0, "ego_speed_mps": 8.0, "rider_speed_mps": 3.0,
                "ego_brake_observed": 0.7, "conflict_window_observed": 300 <= frame < 400,
                "contact_observed": False}

    def camera_png(camera, frame):
        return None if (camera, frame) == missing else PIXEL

    return tick, sample, camera_png


class NativeCaptureTests(unittest.TestCase):
    def test_900_frame_source_and_pixel_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            tick, sample, camera_png = callbacks()
            packet = CAPTURE.capture_attempt(tmp, case_id=CASE, site=SITE,
                                             tick=tick, sample=sample, camera_png=camera_png)
            self.assertEqual(packet["capture_origin"], "unreviewed_adapter")
            saved = CAPTURE._SAVED.finalize_saved(tmp)
            self.assertEqual(saved["original_frames"], 900)
            pixels = CAPTURE.audit_original_pixels(tmp)
            self.assertEqual(pixels["decoded_images"], 3600)
            self.assertEqual(pixels["physical_review"], "pending")
            path = pathlib.Path(tmp) / "front.png.zip"
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "hash drift"):
                CAPTURE.audit_original_pixels(tmp)

    def test_missing_sensor_callback_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tick, sample, camera_png = callbacks(missing=("rear", 120))
            with self.assertRaisesRegex(ValueError, "camera PNG missing"):
                CAPTURE.capture_attempt(tmp, case_id=CASE, site=SITE,
                                        tick=tick, sample=sample, camera_png=camera_png)

    def test_world_frame_discontinuity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tick, sample, camera_png = callbacks(frame_jump=True)
            with self.assertRaisesRegex(ValueError, "tick discontinuity"):
                CAPTURE.capture_attempt(tmp, case_id=CASE, site=SITE,
                                        tick=tick, sample=sample, camera_png=camera_png)

    def test_reused_attempt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "existing.json").write_text("{}", encoding="utf-8")
            tick, sample, camera_png = callbacks()
            with self.assertRaisesRegex(ValueError, "empty"):
                CAPTURE.capture_attempt(tmp, case_id=CASE, site=SITE,
                                        tick=tick, sample=sample, camera_png=camera_png)

    def test_corrupt_pixel_rejected_even_with_updated_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tick, sample, camera_png = callbacks()
            CAPTURE.capture_attempt(tmp, case_id=CASE, site=SITE,
                                    tick=tick, sample=sample, camera_png=camera_png)
            root = pathlib.Path(tmp)
            media_path = root / "media.json"
            media = json.loads(media_path.read_text(encoding="utf-8"))
            archive_path = root / media["front"]["path"]
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
                contents = {name: archive.read(name) for name in names}
            contents[names[20]] = b"\x89PNG\r\n\x1a\ncorrupt"
            with ZipFile(archive_path, "w", compression=ZIP_STORED) as archive:
                for name in names:
                    archive.writestr(name, contents[name])
            media["front"]["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            media_path.write_text(json.dumps(media), encoding="utf-8")
            packet_path = root / "encounter-packet.json"
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["media"]["sha256"] = hashlib.sha256(media_path.read_bytes()).hexdigest()
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "decode failed"):
                CAPTURE.audit_original_pixels(root)


if __name__ == "__main__":
    unittest.main()
